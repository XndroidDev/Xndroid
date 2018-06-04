import logging
import sys
import os
import contextlib
import functools
import time

import paramiko
import gevent
import gevent.event

from .direct import Proxy
from .. import networking
from .. import stat


LOGGER = logging.getLogger(__name__)


class SshProxy(Proxy):
    def __init__(self, proxy_host, proxy_port=22, username=None, password=None, key_filename=None, priority=0, **ignore):
        super(SshProxy, self).__init__()
        self.proxy_host = proxy_host
        if not self.proxy_host:
            self.died = True
        self.proxy_port = int(proxy_port)
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.ssh_client = None
        self.connection_failed = gevent.event.Event()
        self.failed_times = 0
        self.priority = int(priority)
        self.connect()

    def connect(self):
        if '0.0.0.0' == self._proxy_ip:
            return False
        try:
            self.close()
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.load_system_host_keys()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            sock = networking.create_tcp_socket(self.proxy_ip, self.proxy_port, 3)
            self.key_filename = self.key_filename or '/sdcard/%s' % self.proxy_host
            if not os.path.exists(self.key_filename):
                self.key_filename = None
            self.ssh_client.connect(
                self.proxy_ip, self.proxy_port,
                username=self.username, password=self.password,
                key_filename=self.key_filename,
                sock=sock,
                look_for_keys=True if self.key_filename else False)
            return True
        except:
            LOGGER.exception('failed to connect ssh proxy: %s' % self)
            self.increase_failed_time()
            return False

    def guard(self):
        while not self.died:
            self.connection_failed.wait()
            LOGGER.critical('!!! %s reconnect' % self)
            if not self.connect():
                continue
            self.connection_failed.clear()
            gevent.sleep(1)
        LOGGER.critical('!!! %s gurad loop exit !!!' % self)


    def close(self):
        if self.ssh_client:
            self.ssh_client.close()

    def do_forward(self, client):
        begin_at = time.time()
        try:
            upstream_socket = self.open_channel(client)
        except:
            LOGGER.info('[%s] failed to open channel: %s' % (repr(client), sys.exc_info()[1]))
            gevent.sleep(1)
            self.connection_failed.set()
            return client.fall_back(reason='ssh open channel failed', delayed_penalty=self.increase_failed_time)
        with contextlib.closing(upstream_socket):
            upstream_socket.counter = stat.opened(upstream_socket, self, client.host, client.dst_ip)
            LOGGER.info('[%s] channel opened: %s' % (repr(client), upstream_socket))
            client.add_resource(upstream_socket)
            upstream_socket.sendall(client.peeked_data)
            client.forward(
                upstream_socket, delayed_penalty=self.increase_failed_time,
                on_forward_started=functools.partial(self.on_forward_started, begin_at=begin_at))
            self.failed_times = 0

    def on_forward_started(self, begin_at):
        self.record_latency(time.time() - begin_at)

    def open_channel(self, client):
        return self.ssh_client.get_transport().open_channel(
            'direct-tcpip', (client.dst_ip, client.dst_port), (client.src_ip, client.src_port))

    @classmethod
    def refresh(cls, proxies):
        for proxy in proxies:
            proxy.connection_failed.set()
            gevent.spawn(proxy.guard)
        return True

    def is_protocol_supported(self, protocol, client=None):
        return True

    def __repr__(self):
        return 'SshProxy[%s:%s]' % (self.proxy_host, self.proxy_port)

    @property
    def public_name(self):
        return 'SSH\t%s' % self.proxy_host
