# -*- coding: utf-8 -*-
import httplib
import time
import logging
import os.path
import json
from datetime import datetime

import gevent
import jinja2

from .. import stat
from .. import httpd
from ..gateways import proxy_client
from ..proxies.http_try import HTTP_TRY_PROXY
from .. import config_file
from .. import networking


PROXIES_HTML_FILE = os.path.join(os.path.dirname(__file__), '..', 'templates', 'proxies.html')
UPSTREAM_HTML_FILE = os.path.join(os.path.dirname(__file__), '..', 'templates', 'upstream.html')
LOGGER = logging.getLogger(__name__)
MAX_TIME_RANGE = 5


@httpd.http_handler('POST', 'refresh-proxies')
def handle_refresh_proxies(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    proxy_client.auto_fix_enabled = True
    proxy_client.clear_proxy_states()
    proxy_client.refresh_proxies()
    return ['OK']


@httpd.http_handler('GET', 'proxies')
def handle_list_proxies(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/html')])
    proxies_stats = {}
    for proxy in proxy_client.proxies:
        proxy_public_name = proxy.public_name
        if not proxy_public_name:
            continue
        if proxy_public_name not in proxies_stats:
            proxies_stats[proxy_public_name] = {
                'proxy_id': proxy.proxy_id,
                'rx_bytes_value': 0,
                'tx_bytes_value': 0,
                'rx_bytes_last': 0,
                'tx_bytes_last': 0,
                'died': False,
                'time_elapse': time.time() - proxy.last_record_time
            }
        stat_item = proxies_stats[proxy_public_name]
        stat_item['died'] = stat_item['died'] or proxy.died
        stat_item['rx_bytes_value'] += proxy.rx_bytes
        stat_item['tx_bytes_value'] += proxy.tx_bytes
        stat_item['rx_bytes_last'] += proxy.last_rx
        stat_item['tx_bytes_last'] += proxy.last_tx
        proxy.last_record_time = time.time()
        proxy.last_rx = proxy.rx_bytes
        proxy.last_tx = proxy.tx_bytes

    for stat_item in proxies_stats.values():
        rx_bytes = stat_item['rx_bytes_value']
        tx_bytes = stat_item['tx_bytes_value']
        time_elapse = stat_item['time_elapse']
        stat_item['rx_bytes_label'] = to_human_readable_size(rx_bytes)
        stat_item['tx_bytes_label'] = to_human_readable_size(tx_bytes)
        rx_speed = (rx_bytes - stat_item['rx_bytes_last']) / (time_elapse * 1000)
        tx_speed = (tx_bytes - stat_item['tx_bytes_last']) / (time_elapse * 1000)
        stat_item['rx_speed_value'] = rx_speed
        stat_item['tx_speed_value'] = tx_speed
        stat_item['rx_speed_label'] = '%7.2f KB/s' % rx_speed
        stat_item['tx_speed_label'] = '%7.2f KB/s' % tx_speed

        del stat_item['rx_bytes_last']
        del stat_item['tx_bytes_last']
        del stat_item['time_elapse']

    with open(PROXIES_HTML_FILE) as f:
        template = jinja2.Template(f.read())
    return template.render(proxies_stats=proxies_stats).encode('utf8')


def enable_proxies():
    proxy_client.clear_proxy_states()
    gevent.spawn(proxy_client.init_proxies, config_file.read_config())


def disable_proxies():
    proxy_client.proxies = []
    proxy_client.clear_proxy_states()


@httpd.http_handler('POST', 'tcp-scrambler/enable')
def handle_enable_tcp_scrambler(environ, start_response):
    proxy_client.tcp_scrambler_enabled = True
    config_file.update_config(tcp_scrambler_enabled=True)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'tcp-scrambler/disable')
def handle_disable_tcp_scrambler(environ, start_response):
    proxy_client.tcp_scrambler_enabled = False
    config_file.update_config(tcp_scrambler_enabled=False)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'google-scrambler/enable')
def handle_enable_googlescrambler(environ, start_response):
    proxy_client.google_scrambler_enabled = True
    config_file.update_config(google_scrambler_enabled=True)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'google-scrambler/disable')
def handle_disable_google_scrambler(environ, start_response):
    proxy_client.google_scrambler_enabled = False
    config_file.update_config(google_scrambler_enabled=False)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'https-enforcer/enable')
def handle_enable_https_enforcer(environ, start_response):
    proxy_client.https_enforcer_enabled = True
    config_file.update_config(https_enforcer_enabled=True)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'https-enforcer/disable')
def handle_disable_https_enforcer(environ, start_response):
    proxy_client.https_enforcer_enabled = False
    config_file.update_config(https_enforcer_enabled=False)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'china-shortcut/enable')
def handle_enable_china_shortcut(environ, start_response):
    proxy_client.china_shortcut_enabled = True
    config_file.update_config(china_shortcut_enabled=True)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'china-shortcut/disable')
def handle_disable_china_shortcut(environ, start_response):
    proxy_client.china_shortcut_enabled = False
    config_file.update_config(china_shortcut_enabled=False)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'direct-access/enable')
def handle_enable_direct_access(environ, start_response):
    proxy_client.direct_access_enabled = True
    config_file.update_config(direct_access_enabled=True)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'direct-access/disable')
def handle_disable_direct_access(environ, start_response):
    proxy_client.direct_access_enabled = False
    config_file.update_config(direct_access_enabled=False)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'ipv6-direct-enable/enable')
def handle_enable_ipv6_direct(environ, start_response):
    proxy_client.ipv6_direct_enable = True
    config_file.update_config(ipv6_direct_enable=True)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'ipv6-direct-enable/disable')
def handle_disable_ipv6_direct(environ, start_response):
    proxy_client.ipv6_direct_enable = False
    config_file.update_config(ipv6_direct_enable=False)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'ipv6-direct-first/enable')
def handle_enable_ipv6_direct_try_first(environ, start_response):
    proxy_client.ipv6_direct_try_first = True
    config_file.update_config(ipv6_direct_try_first=True)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'ipv6-direct-first/disable')
def handle_disable_ipv6_direct_try_first(environ, start_response):
    proxy_client.ipv6_direct_try_first = False
    config_file.update_config(ipv6_direct_try_first=False)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'hosted-domain/enable')
def handle_enable_hosted_domain(environ, start_response):
    networking.DNS_HANDLER.enable_hosted_domain = True
    config_file.update_config(hosted_domain_enabled=True)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'hosted-domain/disable')
def handle_disable_hosted_domain(environ, start_response):
    networking.DNS_HANDLER.enable_hosted_domain = False
    config_file.update_config(hosted_domain_enabled=False)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'prefers-private-proxy/enable')
def handle_enable_prefers_private_proxy(environ, start_response):
    proxy_client.prefers_private_proxy = True
    config_file.update_config(prefers_private_proxy=True)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'prefers-private-proxy/disable')
def handle_disable_prefers_private_proxy(environ, start_response):
    proxy_client.prefers_private_proxy = False
    config_file.update_config(prefers_private_proxy=False)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'goagent-public-servers/enable')
def handle_enable_goagent_public_servers(environ, start_response):
    def apply(config):
        config['public_servers']['goagent_enabled'] = True

    proxy_client.goagent_public_servers_enabled = True
    config_file.update_config(apply)
    disable_proxies()
    enable_proxies()
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'goagent-public-servers/disable')
def handle_disable_goagent_public_servers(environ, start_response):
    def apply(config):
        config['public_servers']['goagent_enabled'] = False

    proxy_client.goagent_public_servers_enabled = False
    config_file.update_config(apply)
    disable_proxies()
    enable_proxies()
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'ss-public-servers/enable')
def handle_enable_ss_public_servers(environ, start_response):
    def apply(config):
        config['public_servers']['ss_enabled'] = True

    proxy_client.ss_public_servers_enabled = True
    config_file.update_config(apply)
    disable_proxies()
    enable_proxies()
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'ss-public-servers/disable')
def handle_disable_ss_public_servers(environ, start_response):
    def apply(config):
        config['public_servers']['ss_enabled'] = False

    proxy_client.ss_public_servers_enabled = False
    config_file.update_config(apply)
    disable_proxies()
    enable_proxies()
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'proxies/add')
def handle_add_proxy(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    private_server = to_private_server(environ)
    if isinstance(private_server, basestring):
        return [private_server]
    proxy_type = environ['REQUEST_ARGUMENTS']['proxy_type'].value

    def apply(config):
        config_file.add_proxy(config, proxy_type=proxy_type,**private_server)

    config_file.update_config(apply)
    disable_proxies()
    enable_proxies()
    return []


@httpd.http_handler('POST', 'proxies/update')
def handle_update_proxy(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    proxy_id = environ['REQUEST_ARGUMENTS']['proxy_id'].value
    proxy_type = environ['REQUEST_ARGUMENTS']['proxy_type'].value
    private_server = to_private_server(environ)
    if isinstance(private_server, basestring):
        return [private_server]
    private_server['proxy_type'] = proxy_type
    def apply(config):
        config['private_servers'][proxy_id] = private_server

    config_file.update_config(apply)
    disable_proxies()
    enable_proxies()
    return []


def to_private_server(environ):
    _ = environ['select_text']
    args = {key: environ['REQUEST_ARGUMENTS'][key].value for key in environ['REQUEST_ARGUMENTS'].keys()}
    args.pop('proxy_id', None)
    proxy_type = args['proxy_type']
    if 'GoAgent' == proxy_type:
        appid = args['appid']
        if not appid:
            return _('App Id must not be empty', 'App Id 必填')
        return {
            'appid': appid,
            'path': args.get('path') or '/2',
            'goagent_version': args.get('goagent_version') or 'auto',
            'goagent_options': args.get('goagent_options'),
            'goagent_password': args.get('goagent_password')
        }
    elif 'SSH' == proxy_type:
        host = args['host']
        if not host:
            return _('Host must not be empty', '主机必填')
        port = args['port']
        if not port:
            return _('Port must not be empty', '端口必填')
        try:
            port = int(port)
        except:
            return _('Port must be number', '端口必须是数字')
        username = args['username']
        if not username:
            return _('User name must not be empty', '用户名必填')
        password = args.get('password')
        connections_count = int(args.get('connections_count') or 4)
        return {
            'host': host,
            'port': port,
            'username': username,
            'password': password,
            'connections_count': connections_count
        }
    elif 'Shadowsocks' == proxy_type:
        host = args['host']
        if not host:
            return _('Host must not be empty', '主机必填')
        port = args['port']
        if not port:
            return _('Port must not be empty', '端口必填')
        password = args.get('password')
        if not password:
            return _('Password must not be empty', '密码必填')
        encrypt_method = args.get('encrypt_method')
        if not encrypt_method:
            return _('Encrypt method must not be empty', '加密方式必填')
        return {
            'host': host,
            'port': port,
            'password': password,
            'encrypt_method': encrypt_method
        }
    elif 'HTTP' == proxy_type:
        host = args['host']
        if not host:
            return _('Host must not be empty', '主机必填')
        port = args['port']
        if not port:
            return _('Port must not be empty', '端口必填')
        try:
            port = int(port)
        except:
            return _('Port must be number', '端口必须是数字')
        username = args['username']
        password = args.get('password')
        return {
            'host': host,
            'port': port,
            'username': username,
            'password': password,
            'traffic_type': args.get('traffic_type') or 'HTTP/HTTPS',
            'transport_type': args.get('transport_type') or 'HTTP'
        }
    elif 'SPDY' == proxy_type:
        host = args['host']
        if not host:
            return _('Host must not be empty', '主机必填')
        port = args['port']
        if not port:
            return _('Port must not be empty', '端口必填')
        try:
            port = int(port)
        except:
            return _('Port must be number', '端口必须是数字')
        username = args['username']
        if not username:
            return _('User name must not be empty', '用户名必填')
        password = args.get('password')
        if not password:
            return _('Password must not be empty', '密码必填')
        connections_count = int(args.get('connections_count') or 4)
        return {
            'host': host,
            'port': port,
            'username': username,
            'password': password,
            'traffic_type': args.get('traffic_type') or 'HTTP/HTTPS',
            'connections_count': connections_count
        }
    elif 'Sock5' == proxy_type:
        host = args['host']
        if not host:
            return _('Host must not be empty', '主机必填')
        port = args['port']
        if not port:
            return _('Port must not be empty', '端口必填')
        try:
            port = int(port)
        except:
            return _('Port must be number', '端口必须是数字')
        return {
            'host': host,
            'port': port
        }
    else:
        return _('Internal Error', '内部错误')


@httpd.http_handler('GET', 'proxy')
def handle_get_proxy(environ, start_response):
    proxy_id = environ['REQUEST_ARGUMENTS']['proxy_id'].value
    proxy = config_file.read_config()['private_servers'].get(proxy_id)
    start_response(httplib.OK, [('Content-Type', 'application/json')])
    if proxy:
        proxy_type = proxy.pop('proxy_type')
        yield json.dumps({
            'proxy_id': proxy_id,
            'proxy_type': proxy_type,
            'properties': proxy
        })
    else:
        yield json.dumps({})


@httpd.http_handler('POST', 'proxies/delete')
def handle_get_proxy(environ, start_response):
    proxy_id = environ['REQUEST_ARGUMENTS']['proxy_id'].value
    def apply(config):
        config['private_servers'].pop(proxy_id, None)

    config_file.update_config(apply)
    disable_proxies()
    enable_proxies()
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


def to_human_readable_size(num):
    for x in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return '%7.2f %s' % (num, x)
        num /= 1024.0

