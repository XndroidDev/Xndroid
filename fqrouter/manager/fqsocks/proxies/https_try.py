from .direct import DirectProxy
from .. import ip_substitution
import logging
import gevent
import time
import sys

LOGGER = logging.getLogger(__name__)


class HttpsTryProxy(DirectProxy):

    INITIAL_TIMEOUT = 1

    def __init__(self):
        super(HttpsTryProxy, self).__init__()
        self.timeout = HttpsTryProxy.INITIAL_TIMEOUT
        self.slow_ip_list = set()
        self.dst_black_list = {}

    def do_forward(self, client):
        dst = (client.dst_ip, client.dst_port)
        try:
            super(HttpsTryProxy, self).do_forward(client)
            if dst in self.dst_black_list:
                LOGGER.error('HttpsTryProxy removed dst %s:%s from blacklist' % dst)
                del self.dst_black_list[dst]
        except client.ProxyFallBack:
            if dst not in self.dst_black_list:
                LOGGER.error('HttpsTryProxy blacklist dst %s:%s' % dst)
            self.dst_black_list[dst] = self.dst_black_list.get(dst, 0) + 1
            raise

    def create_upstream_sock(self, client):
        success, upstream_sock = gevent.spawn(self.try_connect, client).get(timeout=self.timeout)
        if not success:
            raise upstream_sock
        return upstream_sock

    def try_connect(self, client):
        try:
            begin_time = time.time()
            upstream_sock = client.create_tcp_socket(
                client.dst_ip, client.dst_port,
                connect_timeout=max(5, HTTPS_TRY_PROXY.timeout * 2))
            elapsed_seconds = time.time() - begin_time
            if elapsed_seconds > self.timeout:
                self.slow_ip_list.add(client.dst_ip)
                self.dst_black_list.clear()
                if len(self.slow_ip_list) > 3:
                    LOGGER.critical('!!! increase http timeout %s=>%s' % (self.timeout, self.timeout + 1))
                    self.timeout += 1
                    self.slow_ip_list.clear()
            return True, upstream_sock
        except:
            return False, sys.exc_info()[1]

    def is_protocol_supported(self, protocol, client=None):
        if self.died:
            return False
        if client and self in client.tried_proxies:
            return False
        if 'HTTPS' != protocol:
            return False
        dst = (client.dst_ip, client.dst_port)
        if ip_substitution.substitute_ip(client, self.dst_black_list):
            return True # there is new ip to try
        is_ip_blacklisted = self.dst_black_list.get(dst, 0) % 16 # retry every 16 times
        return not is_ip_blacklisted

    def __repr__(self):
        return 'HttpsTryProxy'


HTTPS_TRY_PROXY = HttpsTryProxy()

