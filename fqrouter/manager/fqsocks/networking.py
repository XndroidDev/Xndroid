import socket
import struct
import dpkt
import logging
import random
import re
import fqlan

LOGGER = logging.getLogger(__name__)
SO_ORIGINAL_DST = 80
SO_MARK = 36
OUTBOUND_IP = None
SPI = {}
RE_IP = re.compile(r'^\d+\.\d+\.\d+\.\d+$')
DNS_HANDLER = None

default_interface_ip_cache = None

def get_default_interface_ip():
    global default_interface_ip_cache
    if not default_interface_ip_cache:
        default_interface_ip_cache = fqlan.get_default_interface_ip()
    return default_interface_ip_cache


def create_tcp_socket(server_ip, server_port, connect_timeout):
    sock = SPI['create_tcp_socket'](server_ip, server_port, connect_timeout)
    # set reuseaddr option to avoid 10048 socket error
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # resize socket recv buffer 8K->32K to improve browser releated application performance
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32*1024)
    # disable negal algorithm to send http request quickly.
    sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, True)
    return sock


def create_ipv6_tcp_socket(server_ip, server_port, connect_timeout):
    sock = socket.socket(family=socket.AF_INET6, type=socket.SOCK_STREAM)
    sock.setblocking(0)
    sock.settimeout(connect_timeout)
    try:
        sock.connect((server_ip, server_port))
    except:
        sock.close()
        raise
    sock.settimeout(None)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32*1024)
    sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, True)
    return sock

def _create_tcp_socket(server_ip, server_port, connect_timeout):
    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    if OUTBOUND_IP and server_ip != '127.0.0.1':
        sock.bind((OUTBOUND_IP, 0))
    sock.setblocking(0)
    sock.settimeout(connect_timeout)
    try:
        sock.connect((server_ip, server_port))
    except:
        sock.close()
        raise
    sock.settimeout(None)
    return sock


SPI['create_tcp_socket'] = _create_tcp_socket


def get_original_destination(sock, src_ip, src_port):
    return SPI['get_original_destination'](sock, src_ip, src_port)


def _get_original_destination(sock, src_ip, src_port):
    dst = sock.getsockopt(socket.SOL_IP, SO_ORIGINAL_DST, 16)
    dst_port, dst_ip = struct.unpack("!2xH4s8x", dst)
    dst_ip = socket.inet_ntoa(dst_ip)
    return dst_ip, dst_port


SPI['get_original_destination'] = _get_original_destination


def resolve_ips(host):
    if ':' in host:
        return [host]
    if RE_IP.match(host):
        return [host]
    request = dpkt.dns.DNS(
        id=random.randint(1, 65535), qd=[dpkt.dns.DNS.Q(name=str(host), type=dpkt.dns.DNS_A)])
    response = DNS_HANDLER.query(request, str(request))
    ips = [socket.inet_ntoa(an.ip) for an in response.an if hasattr(an, 'ip')]
    return ips


def resolve_txt(domain):
    request = dpkt.dns.DNS(
        id=random.randint(1, 65535), qd=[dpkt.dns.DNS.Q(name=str(domain), type=dpkt.dns.DNS_TXT)])
    return DNS_HANDLER.query(request, str(request)).an

def is_ipv6(ip):
    return ':' in ip
