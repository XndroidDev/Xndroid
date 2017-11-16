import logging
import urlparse
import httplib
import os
import base64

import gevent.server
import jinja2

from .. import networking
from .proxy_client import ProxyClient
from .proxy_client import handle_client
from ..proxies.http_try import recv_till_double_newline
from ..proxies.http_try import parse_request
from ..proxies.http_try import is_no_direct_host
from .. import config_file
from .. import httpd
from .. import lan_ip


LOGGER = logging.getLogger(__name__)
WHITELIST_PAC_FILE = os.path.join(os.path.dirname(__file__), '..', 'templates', 'whitelist.pac')
dns_cache = {}
LISTEN_IP = None
LISTEN_PORT = None
UPNP_PORT = None
UPNP_AUTH = None
UPNP_AUTH_NONE = 'NONE'
server_greenlet = None
external_ip_address = None


@httpd.http_handler('GET', 'pac')
def pac_page(environ, start_response):
    with open(WHITELIST_PAC_FILE) as f:
        template = jinja2.Template(unicode(f.read(), 'utf8'))
    ip = networking.get_default_interface_ip()
    start_response(httplib.OK, [('Content-Type', 'application/x-ns-proxy-autoconfig')])
    return [template.render(http_gateway='%s:%s' % (ip, LISTEN_PORT)).encode('utf8')]


def handle(downstream_sock, address):
    src_ip, src_port = address
    request, payload = recv_till_double_newline('', downstream_sock)
    if not request:
        LOGGER.error('http gateway did not receive complete request')
        return
    method, path, headers = parse_request(request)
    if 'GET' == method.upper() and '/' == path and is_http_gateway_host(headers.get('Host')):
        with open(WHITELIST_PAC_FILE) as f:
            template = jinja2.Template(unicode(f.read(), 'utf8'))
        downstream_sock.sendall(
            'HTTP/1.1 200 OK\r\n\r\n%s' % template.render(http_gateway=headers.get('Host')).encode('utf8'))
        return
    if lan_ip.is_lan_ip(src_ip):
        authorized = True
    elif UPNP_AUTH_NONE == get_upnp_auth():
        authorized = True
    else:
        authorized = get_upnp_auth() == headers.get('Proxy-Authorization')
    if not authorized:
        downstream_sock.sendall(
"""HTTP/1.1 407 Proxy authentication required
Connection: close
Content-Type: text/html
Content-Length: 0
Proxy-Authenticate: Basic realm="fqrouter"

""")
        return
    if 'CONNECT' == method.upper():
        if ':' in path:
            dst_host, dst_port = path.split(':')
            dst_port = int(dst_port)
        else:
            dst_host = path
            dst_port = 443
        dst_ip = resolve_ip(dst_host)
        if not dst_ip:
            LOGGER.error('can not resolve host: %s' % dst_host)
            return
        if lan_ip.is_lan_ip(dst_ip):
            LOGGER.error('%s is lan ip' % dst_ip)
            return
        downstream_sock.sendall('HTTP/1.1 200 OK\r\n\r\n')
        client = ProxyClient(downstream_sock, src_ip, src_port, dst_ip, dst_port)
        client.us_ip_only = is_no_direct_host(dst_host)
        handle_client(client)
    else:
        dst_host = urlparse.urlparse(path)[1]
        if ':' in dst_host:
            dst_host, dst_port = dst_host.split(':')
            dst_port = int(dst_port)
        else:
            dst_port = 80
        dst_ip = resolve_ip(dst_host)
        if not dst_ip:
            LOGGER.error('can not resolve host: %s' % dst_host)
            return
        if lan_ip.is_lan_ip(dst_ip):
            LOGGER.error('%s is lan ip' % dst_ip)
            return
        client = ProxyClient(downstream_sock, src_ip, src_port, dst_ip, dst_port)
        client.us_ip_only = is_no_direct_host(dst_host)
        request_lines = ['%s %s HTTP/1.1\r\n' % (method, path[path.find(dst_host) + len(dst_host):])]
        headers.pop('Proxy-Connection', None)
        headers['Host'] = dst_host
        headers['Connection'] = 'close'
        for key, value in headers.items():
            request_lines.append('%s: %s\r\n' % (key, value))
        request = ''.join(request_lines)
        client.peeked_data = request + '\r\n' + payload
        handle_client(client)


def is_http_gateway_host(host):
    if '127.0.0.1:%s' % LISTEN_PORT == host:
        return True
    if '%s:%s' % (networking.get_default_interface_ip(), LISTEN_PORT) == host:
        return True
    if external_ip_address and '%s:%s' % (external_ip_address, get_upnp_port()) == host:
        return True
    return False


def get_upnp_auth():
    global UPNP_AUTH
    if not UPNP_AUTH:
        upnp_config = config_file.read_config()['upnp']
        if upnp_config['is_password_protected']:
            UPNP_AUTH = base64.b64encode('%s:%s' % (upnp_config['username'], upnp_config['password'])).strip()
            UPNP_AUTH = 'Basic %s' % UPNP_AUTH
        else:
            UPNP_AUTH = UPNP_AUTH_NONE
    return UPNP_AUTH


def get_upnp_port():
    global UPNP_PORT

    if UPNP_PORT:
        return UPNP_PORT
    UPNP_PORT = config_file.read_config()['upnp']['port']
    return UPNP_PORT


def resolve_ip(host):
    if host in dns_cache:
        return dns_cache[host]
    ips = networking.resolve_ips(host)
    if ips:
        ip = ips[0]
    else:
        ip = None
    dns_cache[host] = ip
    return dns_cache[host]


def serve_forever():
    server = gevent.server.StreamServer((LISTEN_IP, LISTEN_PORT), handle)
    LOGGER.info('started fqsocks http gateway at %s:%s' % (LISTEN_IP, LISTEN_PORT))
    try:
        server.serve_forever()
    except:
        LOGGER.exception('failed to start http gateway')
    finally:
        LOGGER.info('http gateway stopped')

