import logging
import re
import sys
import base64
import socket
import time

import ssl

from .direct import to_bool
from .direct import Proxy
from .http_try import recv_till_double_newline


LOGGER = logging.getLogger(__name__)

RE_STATUS = re.compile(r'HTTP/1.\d (\d+) ')


class HttpConnectProxy(Proxy):
    def __init__(self, proxy_host, proxy_port, username=None, password=None, is_secured=False, priority=0, **ignore):
        super(HttpConnectProxy, self).__init__()
        self.proxy_host = proxy_host
        self.auto_relive = True
        if not self.proxy_host:
            self.died = True
            self.auto_relive = False
        self.proxy_port = int(proxy_port)
        self.username = username
        self.password = password
        self.failed_times = 0
        self.is_secured = to_bool(is_secured)
        self.priority = int(priority)

    def do_forward(self, client):
        LOGGER.info('[%s] http connect %s:%s' % (repr(client), self.proxy_ip, self.proxy_port))
        begin_at = time.time()
        try:
            upstream_sock = client.create_tcp_socket(self.proxy_ip, self.proxy_port, 3)
            if self.is_secured:
                counter = upstream_sock.counter
                upstream_sock = ssl.wrap_socket(upstream_sock)
                upstream_sock.counter = counter
                client.add_resource(upstream_sock)
        except:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] http-connect upstream socket connect fail' % (repr(client)), exc_info=1)
            return client.fall_back(
                reason='http-connect upstream socket connect fail',
                delayed_penalty=self.increase_failed_time)
        upstream_sock.settimeout(3)
        upstream_sock.sendall('CONNECT %s:%s HTTP/1.0\r\n' % (client.host if client.host else client.dst_ip, client.dst_port))
        if self.username and self.password:
            auth = base64.b64encode('%s:%s' % (self.username, self.password)).strip()
            upstream_sock.sendall('Proxy-Authorization: Basic %s\r\n' % auth)
        upstream_sock.sendall('\r\n')
        try:
            response, _ = recv_till_double_newline('', upstream_sock)
        except socket.timeout:
            return client.fall_back(
                reason='http-connect upstream connect command timed out',
                delayed_penalty=self.increase_failed_time)
        except:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] http-connect upstream connect command failed' % (repr(client)), exc_info=1)
            return client.fall_back(
                reason='http-connect upstream connect command failed: %s,%s'
                       % (sys.exc_info()[0], sys.exc_info()[1]),
                delayed_penalty=self.increase_failed_time)
        match = RE_STATUS.search(response)
        if match and '200' == match.group(1):
            self.record_latency(time.time() - begin_at)
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] upstream connected' % repr(client))
            self.died = False
            upstream_sock.sendall(client.peeked_data)
            client.forward(upstream_sock)
        else:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] http connect response: %s' % (repr(client), response.strip()))
            LOGGER.error('[%s] http connect rejected: %s' %
                         (repr(client), response.splitlines()[0] if response.splitlines() else 'unknown'))
            self.died = True
            self.die_time = time.time()
            client.fall_back(
                response.splitlines()[0] if response.splitlines() else 'unknown',
                delayed_penalty=self.increase_failed_time)
        self.failed_times = 0

    def is_protocol_supported(self, protocol, client=None):
        return protocol == 'HTTPS'

    def __repr__(self):
        return 'HttpConnectProxy[%s:%s %0.2f]' % (self.proxy_host, self.proxy_port, self.latency)

    @property
    def public_name(self):
        return 'HTTP\t%s:%d' % (self.proxy_host, self.proxy_port)

