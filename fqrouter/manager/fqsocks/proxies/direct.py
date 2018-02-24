import logging
import socket
import time
from .. import networking

LOGGER = logging.getLogger(__name__)
on_proxy_died = None


def to_bool(s):
    if isinstance(s, bool):
        return s
    return 'True' == s


class Proxy(object):
    def __init__(self):
        super(Proxy, self).__init__()
        self.died = False
        self.flags = set()
        self.priority = 0
        self.proxy_id = None
        self._proxy_ip = None
        self.latency_records_total = 0
        self.latency_records_count = 0
        self.failed_times = 0
        self.auto_relive = False
        self.die_time = None

    def increase_failed_time(self):
        LOGGER.error('failed once/%s: %s' % (self.failed_times, self))
        self.failed_times += 1
        if self.failed_times > 3:
            self.died = True
            self.die_time = time.time()
            LOGGER.fatal('!!! proxy died !!!: %s' % self)

    def record_latency(self, latency):
        self.latency_records_total += latency
        self.latency_records_count += 1
        if self.latency_records_count > 100:
            self.latency_records_total = self.latency
            self.latency_records_count = 1

    def clear_latency_records(self):
        self.latency_records_total = 0
        self.latency_records_count = 0

    def clear_failed_times(self):
        self.failed_times = 0

    @property
    def latency(self):
        if self.latency_records_count:
            return self.latency_records_total / self.latency_records_count
        else:
            return 0

    @property
    def proxy_ip(self):
        if self._proxy_ip:
            return self._proxy_ip
        ips = networking.resolve_ips(self.proxy_host)
        if not ips:
            LOGGER.critical('!!! failed to resolve proxy ip: %s' % self.proxy_host)
            self._proxy_ip = '0.0.0.0'
            self.died = True
            self.die_time = time.time()
            return self._proxy_ip
        self._proxy_ip = ips[0]
        return self._proxy_ip

    def forward(self, client):
        client.forwarding_by = self
        try:
            self.do_forward(client)
        finally:
            if self.died:
                LOGGER.fatal('[%s] !!! proxy died !!!: %s' % (repr(client), self))
                client.dump_proxies()
                if on_proxy_died:
                    on_proxy_died(self)

    def do_forward(self, client):
        raise NotImplementedError()

    @classmethod
    def refresh(cls, proxies):
        for proxy in proxies:
            proxy.died = False
        return True

    def is_protocol_supported(self, protocol, client=None):
        return False

    def __eq__(self, other):
        return repr(self) == repr(other)

    def __hash__(self):
        return hash(repr(self))

    @property
    def public_name(self):
        return None


class DirectProxy(Proxy):
    DEFAULT_CONNECT_TIMEOUT = 5

    def __init__(self, connect_timeout=DEFAULT_CONNECT_TIMEOUT):
        super(DirectProxy, self).__init__()
        self.flags.add('DIRECT')
        self.connect_timeout = connect_timeout

    def do_forward(self, client):
        try:
            upstream_sock = self.create_upstream_sock(client)
        except socket.timeout:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] %s connect upstream socket timed out' % (repr(client), self.__repr__()), exc_info=1)
            client.fall_back(reason='direct connect upstream socket timed out')
            return
        except:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] %s connect upstream socket fail' % (repr(client), self.__repr__()), exc_info=1)
            client.fall_back(reason='direct connect upstream socket fail')
            return
        upstream_sock.settimeout(None)
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('[%s] direct upstream connected' % repr(client))
        upstream_sock.counter.sending(len(client.peeked_data))
        upstream_sock.sendall(client.peeked_data)
        client.forward(upstream_sock, timeout=60, after_started_timeout=60 * 60)

    def create_upstream_sock(self, client):
        return client.create_tcp_socket(client.dst_ip, client.dst_port, self.connect_timeout)

    def is_protocol_supported(self, protocol, client=None):
        return True

    def __repr__(self):
        return 'DirectProxy'


class NoneProxy(Proxy):
    def do_forward(self, client):
        return

    def is_protocol_supported(self, protocol, client=None):
        return True

    def __repr__(self):
        return 'NoneProxy'


DIRECT_PROXY = DirectProxy()
NONE_PROXY = NoneProxy()
