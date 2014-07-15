#!/bin/sh -e 
echo "2014-07-15"

wget -N http://geolite.maxmind.com/download/geoip/database/GeoLiteCity.dat.gz
zcat GeoLiteCity.dat.gz > GeoIP.dat.new
mv GeoIP.dat.new /usr/share/GeoIP/GeoIPCity.dat

wget -N http://geolite.maxmind.com/download/geoip/database/GeoLiteCityv6-beta/GeoLiteCityv6.dat.gz
zcat GeoLiteCityv6.dat.gz > GeoIPCityv6.dat
mv GeoIPCityv6.dat /usr/share/GeoIP/GeoIPCityv6.dat
