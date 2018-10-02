import socket
import struct
import logging
import time
import functools
import gevent

from .direct import Proxy
from . import encrypt
from .. import networking


LOGGER = logging.getLogger(__name__)

ip_74_125 = []
for i in range(0, 16):
    ip_74_125.append('74.125.%s.0' % i)
for i in range(96, 112):
    ip_74_125.append('74.125.%s.0' % i)
for i in range(160, 176):
    if i in [164, 171]:
        continue
    ip_74_125.append('74.125.%s.0' % i)
for i in range(209, 219):
    if i in [210, 211, 217]:
        continue
    ip_74_125.append('74.125.%s.0' % i)
ip_173_194 = []
for i in range(0, 32):
    if i in [29, 30]:
        continue
    ip_173_194.append('173.194.%s.0' % i)
for i in range(48, 64):
    if i in [57]:
        continue
    ip_173_194.append('173.194.%s.0' % i)
for i in range(128, 153):
    if i in [143, 145]:
        continue
    ip_173_194.append('173.194.%s.0' % i)
ip_208_117 = [
    '208.117.236.0', '208.117.238.0', '208.117.240.0', '208.117.242.0', '208.117.250.0', '208.117.251.0',
    '208.117.252.0', '208.117.254.0']
ip_209_85 = ['209.85.225.0', '209.85.226.0', '209.85.228.0', '209.85.229.0', '209.85.239.0']
blocked_ip_ranges = set(['209.116.150.0'] + ip_209_85 + ip_208_117 + ip_173_194 + ip_74_125)

class ShadowSocksProxy(Proxy):
    def __init__(self, proxy_host, proxy_port, password, encrypt_method, supported_protocol=None, priority=0, **ignore):
        super(ShadowSocksProxy, self).__init__()
        self.proxy_host = proxy_host
        if not self.proxy_host:
            self.died = True
        self.proxy_port = int(proxy_port)
        self.password = password
        self.encrypt_method = encrypt_method
        self.supported_protocol = supported_protocol
        self.priority = int(priority)
        gevent.spawn(self.test_latency)

    def test_latency(self):
        gevent.sleep(5)
        elapsed_time = 0
        try:
            for i in range(3):
                gevent.sleep(1)
                begin_at = time.time()
                sock = networking.create_tcp_socket(self.proxy_ip, self.proxy_port, 5)
                sock.close()
                elapsed_time += time.time() - begin_at
        except:
            self.record_latency(10) # fixed penalty
            self.increase_failed_time()
            return
        LOGGER.info('%s => %s' % (self.proxy_ip, elapsed_time))
        self.record_latency(elapsed_time)

    def do_forward(self, client):
        encryptor = encrypt.Encryptor(self.password, self.encrypt_method)
        addr_to_send = '\x01'
        addr_to_send += socket.inet_aton(client.dst_ip)
        addr_to_send += struct.pack('>H', client.dst_port)
        begin_at = time.time()
        try:
            upstream_sock = client.create_tcp_socket(self.proxy_ip, self.proxy_port, 5)
        except:
            self.record_latency(10) # fixed penalty
            client.fall_back(reason='can not connect to proxy', delayed_penalty=self.increase_failed_time)
        encrypted_addr = encryptor.encrypt(addr_to_send)
        upstream_sock.counter.sending(len(encrypted_addr))
        upstream_sock.sendall(encrypted_addr)
        encrypted_peeked_data = encryptor.encrypt(client.peeked_data)
        upstream_sock.counter.sending(len(encrypted_peeked_data))
        upstream_sock.sendall(encrypted_peeked_data)
        client.forward(
            upstream_sock, timeout=5 + self.failed_times * 2,
            encrypt=encryptor.encrypt, decrypt=encryptor.decrypt,
            delayed_penalty=self.increase_failed_time if client.peeked_data else None,
            on_forward_started=functools.partial(self.on_forward_started, begin_at=begin_at))
        self.clear_failed_times()

    def on_forward_started(self, begin_at):
        self.record_latency(time.time() - begin_at)

    def is_protocol_supported(self, protocol, client=None):
        if hasattr(self, 'resolved_by_dynamic_proxy') and client:
            if 'youtube.com' in client.host or 'googlevideo.com' in client.host:
                return False
            dst_ip_range = '.'.join(client.dst_ip.split('.')[:3] + ['0'])
            if dst_ip_range in blocked_ip_ranges:
                return False
        if not self.supported_protocol:
            return True
        return self.supported_protocol == protocol

    def __repr__(self):
        return 'ShadowSocksProxy[%s:%s %0.2f]' % (self.proxy_host, self.proxy_port, self.latency)

    @property
    def public_name(self):
        return 'SS\t%s' % self.proxy_host
