import logging
import re
import sys
import base64
import socket
import time

import ssl

import struct

from .direct import to_bool
from .direct import Proxy
from .http_try import recv_till_double_newline


LOGGER = logging.getLogger(__name__)


class Sock5Proxy(Proxy):
    def __init__(self, proxy_host, proxy_port, username=None, password=None, priority=0, **ignore):
        super(Sock5Proxy, self).__init__()
        self.proxy_host = proxy_host
        self.auto_relive = True
        if not self.proxy_host:
            self.died = True
            self.auto_relive = False
        self.proxy_port = int(proxy_port)
        self.username = username
        self.password = password
        self.failed_times = 0
        self.priority = int(priority)

    def do_forward(self, client):
        LOGGER.info('[%s] sock5 connect %s:%s' % (repr(client), self.proxy_ip, self.proxy_port))
        begin_at = time.time()
        try:
            upstream_sock = client.create_tcp_socket(self.proxy_ip, self.proxy_port, 3)
        except:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] sock5 upstream socket connect fail' % (repr(client)), exc_info=1)
            return client.fall_back(
                reason='sock5 upstream socket connect fail',
                delayed_penalty=self.increase_failed_time)
        request_to_send = '\x05\x01\x00'
        upstream_sock.settimeout(3)
        upstream_sock.sendall(request_to_send)
        try:
            response = upstream_sock.recv(16)
        except socket.timeout:
            return client.fall_back(
                reason='sock5 request connect timed out',
                delayed_penalty=self.increase_failed_time)
        except:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] sock5 request connect failed' % (repr(client)), exc_info=1)
            return client.fall_back(
                reason='sock5 request connect failed: %s:%s'
                       % (self.proxy_ip, self.proxy_port),
                delayed_penalty=self.increase_failed_time)
        if not response.startswith(b'\x05\x00') :
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] sock5 request connect response error' % repr(client))
            self.died = True
            self.die_time = time.time()
            client.fall_back(
                '[%s] sock5 request connect response error' % repr(client),
                delayed_penalty=self.increase_failed_time)

        addr_to_send = '\x05\x01\x00\x01'
        addr_to_send += socket.inet_aton(client.dst_ip)
        addr_to_send += struct.pack('>H', client.dst_port)
        upstream_sock.sendall(addr_to_send)
        upstream_sock.settimeout(7)
        try:
            response = upstream_sock.recv(16)
        except socket.timeout:
            return client.fall_back(
                reason='sock5 server setup connection timed out',
                delayed_penalty=self.increase_failed_time)
        except:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] sock5 server setup connection failed' % (repr(client)), exc_info=1)
            return client.fall_back(
                reason='sock5 server setup connection failed: %s:%s'
                       % (self.proxy_ip, self.proxy_port),
                delayed_penalty=self.increase_failed_time)
        if not response.startswith(b'\x05\x00'):
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] sock5 server setup connection respond error' % (repr(client)))
            # self.died = True
            # self.die_time = time.time()
            client.fall_back(
                '[%s] sock5 server setup connection respond error' % (repr(client)),
                delayed_penalty=self.increase_failed_time)
        self.died = False
        self.record_latency(time.time() - begin_at)
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('[%s] upstream connected' % repr(client))
        upstream_sock.sendall(client.peeked_data)
        client.forward(upstream_sock)

        self.failed_times = 0

    def is_protocol_supported(self, protocol, client=None):
        return True

    def __repr__(self):
        return 'Sock5Proxy[%s:%s %0.2f]' % (self.proxy_host, self.proxy_port, self.latency)

    @property
    def public_name(self):
        return 'Sock5\t%s' % self.proxy_host

