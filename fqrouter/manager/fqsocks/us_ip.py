# coding=utf-8
import urllib2
import json
import logging
import httplib
import os.path
from . import networking

LOGGER = logging.getLogger(__name__)

US_IP_CACHE = {}
HOST_IP = {}

def load_cache(file):
    if not file:
        return
    if not os.path.exists(file):
        return
    with open(file) as f:
        US_IP_CACHE.update(json.loads(f.read()))

def save_cache(file):
    if not file:
        return
    with open(file, 'w') as f:
        f.write(json.dumps(US_IP_CACHE))

def is_us_ip(ip):
    if ip in US_IP_CACHE:
        return US_IP_CACHE[ip]
    try:
        return query_from_taobao(ip)
    except:
        LOGGER.exception('failed to query geoip from taobao')
        try:
            return query_from_sina(ip)
        except:
            LOGGER.exception('failed to query geoip from sina')
            try:
                return query_from_telize(ip)
            except:
                LOGGER.exception('failed to query from telize')
    return False


def query_from_taobao(ip):
    response = json.loads(http_get('http://ip.taobao.com/service/getIpInfo.php?ip=%s' % ip))
    yes = 'US' == response['data']['country_id']
    US_IP_CACHE[ip] = yes
    LOGGER.info('queried ip %s is us ip %s from taobao' % (ip, yes))
    return yes


def query_from_sina(ip):
    response = json.loads(http_get('http://int.dpool.sina.com.cn/iplookup/iplookup.php?ip=%s&format=json' % ip))
    yes = u'美国' == response['country']
    US_IP_CACHE[ip] = yes
    LOGGER.info('queried ip %s is us ip %s from sina' % (ip, yes))
    return yes


def query_from_telize(ip):
    response = json.loads(http_get('http://www.telize.com/geoip/%s' % ip))
    yes = 'US' == response['country_code']
    US_IP_CACHE[ip] = yes
    LOGGER.info('queried ip %s is us ip %s from telize' % (ip, yes))
    return yes


def http_get(url):
    class MyHTTPConnection(httplib.HTTPConnection):
        def connect(self):
            if self.host in HOST_IP:
                self.host = HOST_IP[self.host]
            else:
                ip = networking.resolve_ips(self.host)[0]
                HOST_IP[self.host] = ip
                self.host = ip
            return httplib.HTTPConnection.connect(self)

    class MyHTTPHandler(urllib2.HTTPHandler):
        def http_open(self, req):
            return self.do_open(MyHTTPConnection, req)

    opener = urllib2.build_opener(MyHTTPHandler)
    return opener.open(url).read()