# -*- coding: utf-8 -*-
import httplib
import os
import json
from gevent import subprocess
import logging
import re

import gevent

from .. import httpd

from ..gateways import http_gateway
from .. import config_file
from .. import networking


LOGGER = logging.getLogger(__name__)
DOWNSTREAM_HTML_FILE = os.path.join(os.path.dirname(__file__), '..', 'templates', 'downstream.html')
RE_EXTERNAL_IP_ADDRESS = re.compile(r'ExternalIPAddress = (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
spi_wifi_repeater = None
spi_upnp = None


@httpd.http_handler('POST', 'http-gateway/enable')
def handle_enable_http_gateway(environ, start_response):
    if http_gateway.server_greenlet is None:
        http_gateway.server_greenlet = gevent.spawn(http_gateway.serve_forever)

    def apply(config):
        config['http_gateway']['enabled'] = True

    config_file.update_config(apply)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'http-gateway/disable')
def handle_disable_http_gateway(environ, start_response):
    if http_gateway.server_greenlet is not None:
        http_gateway.server_greenlet.kill()
        http_gateway.server_greenlet = None

    def apply(config):
        config['http_gateway']['enabled'] = False

    config_file.update_config(apply)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'http-manager/config/update')
def handle_update_http_manager_config(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    port = environ['REQUEST_ARGUMENTS']['port'].value
    try:
        httpd.LISTEN_PORT = int(port)
    except:
        return [environ['select_text']('must be a number', '只能是数字')]
    if httpd.server_greenlet is not None:
        httpd.server_greenlet.kill()
        httpd.server_greenlet = None
    httpd.server_greenlet = gevent.spawn(httpd.serve_forever)
    gevent.sleep(0.5)
    if httpd.server_greenlet.ready():
        httpd.server_greenlet = None
        return [environ['select_text']('failed to start on new port', '用新端口启动失败')]

    def apply(config):
        config['http_manager']['port'] = httpd.LISTEN_PORT

    config_file.update_config(apply)
    return []


@httpd.http_handler('POST', 'http-gateway/config/update')
def handle_update_http_gateway_config(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    port = environ['REQUEST_ARGUMENTS']['port'].value
    try:
        http_gateway.LISTEN_PORT = int(port)
    except:
        return [environ['select_text']('must be a number', '只能是数字')]
    if http_gateway.server_greenlet is not None:
        http_gateway.server_greenlet.kill()
        http_gateway.server_greenlet = None
    http_gateway.server_greenlet = gevent.spawn(http_gateway.serve_forever)
    gevent.sleep(0.5)
    if http_gateway.server_greenlet.ready():
        http_gateway.server_greenlet = None
        return [environ['select_text']('failed to start on new port', '用新端口启动失败')]

    def apply(config):
        config['http_gateway']['port'] = http_gateway.LISTEN_PORT

    config_file.update_config(apply)
    return []


@httpd.http_handler('POST', 'wifi-repeater/enable')
def handle_enable_wifi_repeater(environ, start_response):
    config = config_file.read_config()
    if spi_wifi_repeater:
        error = spi_wifi_repeater['start'](config['wifi_repeater']['ssid'], config['wifi_repeater']['password'])
    else:
        error = 'unsupported'
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return [error]


@httpd.http_handler('POST', 'wifi-repeater/disable')
def handle_enable_wifi_repeater(environ, start_response):
    if spi_wifi_repeater:
        error = spi_wifi_repeater['stop']()
    else:
        error = 'unsupported'
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return [error]


@httpd.http_handler('POST', 'wifi-repeater/reset')
def handle_reset_wifi_repeater(environ, start_response):
    if spi_wifi_repeater:
        spi_wifi_repeater['reset']()
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return []


@httpd.http_handler('POST', 'wifi-repeater/config/update')
def handle_update_wifi_repeater_config(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    if not spi_wifi_repeater:
        return ['Wifi repeater is unsupported']
    ssid = environ['REQUEST_ARGUMENTS']['ssid'].value
    password = environ['REQUEST_ARGUMENTS']['password'].value
    if not ssid:
        return [environ['select_text']('SSID must not be empty', 'SSID不能为空')]
    if not password:
        return [environ['select_text']('Password must not be empty', '密码不能为空')]
    if len(password) < 8:
        return [environ['select_text']('Password must not be shorter than 8 characters', '密码长度必须大于8位')]

    def apply(config):
        config['wifi_repeater']['ssid'] = ssid
        config['wifi_repeater']['password'] = password

    config_file.update_config(apply)
    if spi_wifi_repeater['is_started']():
        error = spi_wifi_repeater['stop']()
        if error:
            return [error]
        error = spi_wifi_repeater['start']()
        if error:
            return [error]
    return []


@httpd.http_handler('POST', 'wifi-p2p/enable')
def handle_enable_wifi_p2p(environ, start_response):
    if spi_wifi_repeater:
        error = spi_wifi_repeater['enable_wifi_p2p']()
    else:
        error = 'unsupported'
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return [error]


@httpd.http_handler('POST', 'wifi-p2p/disable')
def handle_enable_wifi_p2p(environ, start_response):
    if spi_wifi_repeater:
        error = spi_wifi_repeater['disable_wifi_p2p']()
    else:
        error = 'unsupported'
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return [error]


@httpd.http_handler('GET', 'upnp/status')
def handle_get_upnp_status(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/json')])
    try:
        upnp_status = get_upnp_status()
    except:
        LOGGER.exception('failed to get upnp status')
        upnp_status = {
            'external_ip_address': None,
            'port': None,
            'is_enabled': False
        }
    return [json.dumps(upnp_status)]


@httpd.http_handler('POST', 'upnp/enable')
def handle_enable_upnp(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/json')])
    upnp_port = int(environ['REQUEST_ARGUMENTS']['upnp_port'].value)
    upnp_username = environ['REQUEST_ARGUMENTS']['upnp_username'].value
    upnp_password = environ['REQUEST_ARGUMENTS']['upnp_password'].value
    upnp_is_password_protected = 'true' == environ['REQUEST_ARGUMENTS']['upnp_is_password_protected'].value
    def apply(config):
        config['upnp']['port'] = upnp_port
        config['upnp']['username'] = upnp_username
        config['upnp']['password'] = upnp_password
        config['upnp']['is_password_protected'] = upnp_is_password_protected

    config_file.update_config(apply)
    try:
        default_interface_ip = networking.get_default_interface_ip()
        if not default_interface_ip:
            return ['failed to get default interface ip']
        execute_upnpc('-a %s %s %s tcp' % (default_interface_ip, http_gateway.LISTEN_PORT, upnp_port))
    except:
        LOGGER.exception('failed to enable upnp')
        return ['failed to enable upnp']

    def apply(config):
        config['upnp']['port'] = upnp_port

    config_file.update_config(apply)
    status = get_upnp_status()
    if not status['is_enabled']:
        if upnp_port < 1024:
            upnp_port += 1100
            execute_upnpc('-a %s %s %s tcp' % (default_interface_ip, http_gateway.LISTEN_PORT, upnp_port))

            def apply(config):
                config['upnp']['port'] = upnp_port

            config_file.update_config(apply)
            status = get_upnp_status()
        else:
            return ['failed to enable upnp']
    http_gateway.UPNP_PORT = upnp_port
    http_gateway.UPNP_AUTH = None
    return [json.dumps(status)]


@httpd.http_handler('POST', 'upnp/disable')
def handle_disable_upnp(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    upnp_port = http_gateway.get_upnp_port()
    try:
        execute_upnpc('-d %s tcp' % upnp_port)
    except:
        LOGGER.exception('failed to disable upnp')
        return ['failed to disable upnp']
    return []


def get_upnp_status():
    output = execute_upnpc('-l')
    match = RE_EXTERNAL_IP_ADDRESS.search(output)
    if match:
        external_ip_address = match.group(1)
        http_gateway.external_ip_address = external_ip_address
    else:
        external_ip_address = None
    upnp_port = http_gateway.get_upnp_port()
    return {
        'external_ip_address': external_ip_address,
        'port': upnp_port,
        'is_enabled': (':%s' % http_gateway.LISTEN_PORT) in output
    }


def execute_upnpc(args):
    if spi_upnp:
        return spi_upnp['execute_upnpc'](args)
    LOGGER.info('upnpc %s' % args)
    try:
        output = subprocess.check_output('upnpc %s' % args, shell=True)
        LOGGER.info('succeed, output: %s' % output)
    except subprocess.CalledProcessError, e:
        LOGGER.error('failed, output: %s' % e.output)
        raise
    return output