#!/usr/bin/env python
import os
import glob
import json
import markdown

HELP_FILE = "readme.markdown"

def main_first_sort_key(f):
    if f['name'] == 'main.bro':
        return (0, '')
    else:
        return (1, f['name'])

def pack(example):
    sources = []
    for fn in os.listdir(example):
        if fn == HELP_FILE: continue
        full = os.path.join(example, fn)
        with open(full) as f:
            sources.append({
                "name": fn,
                "content": f.read(),
            })

    sources.sort(key=main_first_sort_key)

    packed_example = {
        'sources': sources,
    }

    full_help_filename = os.path.join(example, HELP_FILE)
    if os.path.exists(full_help_filename):
        md = markdown.Markdown(extensions = ['markdown.extensions.meta'])
        with open(full_help_filename) as f:
            source = f.read()
        html = md.convert(source)
        packed_example['html'] = html
        for k, vs in md.Meta.items():
            packed_example[k] = vs[0]

    return packed_example

def main():
    examples = []
    for x in sorted(glob.glob("*/main.bro")):
        example = os.path.dirname(x)
        jsfile = example + ".json"
        examples.append(example)
        with open(jsfile, 'w') as f:
            json.dump(pack(example), f)

    with open("examples.json", 'w') as f:
        json.dump(examples, f)

if __name__ == "__main__":
    main()
