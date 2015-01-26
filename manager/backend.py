import codecs
import os
import sys
import shutil
import tempfile
import time
import json
import hashlib
import traceback

import docker
from redis import Redis
from celery import Celery
from celery.result import AsyncResult

import bro_ascii_reader

app = Celery('trybro', broker="redis://localhost:6379/0")
app.conf.update(
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0',
    CELERY_TASK_RESULT_EXPIRES = 60, #1 minute
    CELERY_DISABLE_RATE_LIMITS=True,
    CELERY_TASK_SERIALIZER='json',
    CELERY_ACCEPT_CONTENT=['json'],  # Ignore other content
    CELERY_RESULT_SERIALIZER='json',
)


def get_bro_versions():
    c = docker.Client(version='1.11')
    images = c.images(name='bro')
    tags = [i['RepoTags'][0] for i in images]
    versions = [t.replace("bro:", "") for t in tags if '_' not in t]
    return sorted(versions)

CACHE_EXPIRE = 60*10
SOURCES_EXPIRE = 60*60*24*3

BRO_VERSIONS = get_bro_versions()
#Set the default bro version to the most recent version, unless that is master
BRO_VERSION = BRO_VERSIONS[-1]
if BRO_VERSION == 'master' and len(BRO_VERSION) > 1:
    BRO_VERSION = BRO_VERSIONS[-2]

print "Available Bro versions %r. Using %r as default" % (BRO_VERSIONS, BRO_VERSION)


r = Redis()

@app.task(ignore_result=True)
def remove_container(container):
    time.sleep(1)
    with r.lock("docker", 5) as lck:
        c = docker.Client(version='1.11')
        for x in range(5):
            try :
                c.remove_container(container)
                return "removed %r" % container
            except:
                time.sleep(1)

def queue_run_code(sources, pcap, version=BRO_VERSION):
    cache_key = hashlib.sha1(json.dumps([sources,pcap,version])).hexdigest()
    job_id = r.get(cache_key)
    if job_id:
        with r.pipeline() as pipe:
            pipe.expire(cache_key, CACHE_EXPIRE)
            pipe.expire('stdout:%s' % job_id, CACHE_EXPIRE + 5)
            pipe.expire('files:%s' % job_id, CACHE_EXPIRE + 5)
            pipe.expire('sources:%s' % job_id, SOURCES_EXPIRE)
            pipe.execute()
        return AsyncResult(job_id)
    job = run_code.delay(sources, pcap, version)
    return job

def run_code_simple(stdin, version=BRO_VERSION):
    sources = [
        {"name": "main.bro", "content": stdin}
    ]
    job = queue_run_code(sources, pcap=None, version=version)
    stdout = get_stdout(job.id)
    if stdout is None:
        stdout = job.get(timeout=5)
    files = get_files_json(job.id)
    return files

def read_fn(fn):
    with open(fn) as f:
        return f.read()

@app.task
def run_code(sources, pcap=None, version=BRO_VERSION):
    if version not in BRO_VERSIONS:
        version = BRO_VERSION
    cache_key = hashlib.sha1(json.dumps([sources,pcap,version])).hexdigest()
    sys.stdout = sys.stderr
    job = run_code.request
    stdout_key = 'stdout:%s' % job.id
    files_key = 'files:%s' % job.id
    sources_key = 'sources:%s' % job.id

    try :
        file_output = really_run_code(sources, pcap, version)
    except Exception, e:
        traceback.print_exc()
        file_output = None

    if not file_output:
        return "Something went wrong :("

    for f, txt in file_output.items():
        if not f.endswith(".log"): continue
        r.hset(files_key, f, txt)
        if f == 'stdout.log':
            stdout = txt
    r.expire(files_key, CACHE_EXPIRE+5)

    r.set(stdout_key, stdout)
    r.expire(stdout_key, CACHE_EXPIRE+5)

    r.set(sources_key, json.dumps(dict(sources=sources, pcap=pcap, version=version)))
    r.expire(sources_key, SOURCES_EXPIRE)

    r.set(cache_key, job.id)
    r.expire(cache_key, CACHE_EXPIRE)
    return stdout



def really_run_code(sources, pcap=None, version=BRO_VERSION):
    if version not in BRO_VERSIONS:
        version = BRO_VERSION

    for s in sources:
        s['content'] = s['content'].replace("\r\n", "\n")
        s['content'] = s['content'].rstrip() + "\n"

    work_dir = tempfile.mkdtemp(dir="/brostuff")
    runbro_path = os.path.join(work_dir, "runbro")
    for s in sources:
        code_fn = os.path.join(work_dir, s['name'])
        with codecs.open(code_fn, 'w', encoding="utf-8") as f:
            f.write(s['content'])

    runbro_src = "./runbro"
    runbro_src_version_specific = "%s-%s" % (runbro_src, version)
    if os.path.exists(runbro_src_version_specific):
        runbro_src = runbro_src_version_specific

    shutil.copy(runbro_src, runbro_path)
    os.chmod(runbro_path, 0755)

    binds = {work_dir: {"bind": work_dir, "ro": False}}
    if pcap:
        dst = os.path.join(work_dir, "file.pcap")
        if '.' in pcap:
            src = os.path.join(os.getcwd(), "static/pcaps", pcap)
            #FIXME: Work out a better way to share pcaps around
            #binds[src]={"bind": dst, "ro": True}
            shutil.copy(src, dst)
        else:
            contents = get_pcap_with_retry(pcap)
            if contents:
                with open(dst, 'w') as f:
                    f.write(contents)

    #docker run -v /brostuff/tmpWh0k1x:/brostuff/ -n --rm -t -i  bro_worker /bro/bin/bro /brostuff/code.bro

    print "Connecting to docker...."
    with r.lock("docker", 5) as lck:
        c = docker.Client(version='1.11')

        print "Creating container.."
        container = c.create_container('bro:' + version,
            working_dir=work_dir,
            command=runbro_path,
            mem_limit="128m",
            network_disabled=True,
        )
        print "Starting container.."
        try :
            c.start(container, dns="127.0.0.1", binds=binds)
        except Exception, e:
            shutil.rmtree(work_dir)
            remove_container.delay(container)
            raise

    print "Waiting.."
    c.wait(container)

    print "Removing Container"
    remove_container.delay(container)

    files = {}
    for f in os.listdir(work_dir):
        if not f.endswith(".log"): continue
        full = os.path.join(work_dir, f)
        txt = read_fn(full)
        if txt.strip() or 'stdout' in f:
            files[f] = txt
    shutil.rmtree(work_dir)
    return files

def get_stdout(job):
    stdout_key = 'stdout:%s' % job
    stdout = r.get(stdout_key)
    if stdout:
        r.expire(stdout_key, SOURCES_EXPIRE+5)
    return stdout

def get_files(job):
    files_key = 'files:%s' % job
    files = r.hgetall(files_key)
    return files

def get_files_json(job):
    files = get_files(job)
    return parse_tables(files)

def get_saved(job):
    sources_key = 'sources:%s' % job
    return r.get(sources_key)

def parse_tables(files):
    for fn, contents in files.items():
        if contents.startswith("#sep"):
            files[fn] = bro_ascii_reader.reader(contents.splitlines(), max_rows=200)
    return files

def save_pcap(checksum, contents):
    pcap_key = "pcaps:%s" % checksum
    r.set(pcap_key, contents)
    r.expire(pcap_key, 60*60)
    return True

def get_pcap(checksum):
    pcap_key = "pcaps:%s" % checksum
    r.expire(pcap_key, 60*60)
    return r.get(pcap_key)

def get_pcap_with_retry(checksum):
    """There is an annoying race condition where POST /pcap/upload is returning as soon as the pcap is sent, but before
    the request is complete and redis has actually saved it. then run_code
    doesn't find it. so for now, retry here and see if it shows up"""

    for x in range(10):
        contents = get_pcap(checksum)
        if contents:
            return contents
        time.sleep(0.1)
    return None

def check_pcap(checksum):
    pcap_key = "pcaps:%s" % checksum
    exists = r.exists(pcap_key)

    if exists:
        r.expire(pcap_key, 60*60)
    return exists
