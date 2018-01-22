import socket
import struct
import math
import os
import logging
import bisect

LOGGER = logging.getLogger(__name__)


def load_china_ip_ranges():
    with open(os.path.join(os.path.dirname(__file__), 'china_ip.txt')) as f:
        for line in f.readlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            _, _, _, start_ip, ip_count, _, _ = line.split('|')
            start_ip_as_int = ip_to_int(start_ip)
            end_ip_as_int = start_ip_as_int + int(ip_count)
            yield start_ip_as_int, end_ip_as_int


def translate_ip_range(ip, netmask):
    return ip_to_int(ip), ip_to_int(ip) + int(math.pow(2, 32 - netmask))


def ip_to_int(ip):
    return struct.unpack('!i', socket.inet_aton(ip))[0]


CHINA_IP_RANGES = sorted(list(load_china_ip_ranges()))
CHINA_IP_RANGES_I = [a for a, b in CHINA_IP_RANGES]


def is_china_ip(ip):
    ip_as_int = ip_to_int(ip)
    index = bisect.bisect(CHINA_IP_RANGES_I, ip_as_int) - 1
    start_ip_as_int, end_ip_as_int = CHINA_IP_RANGES[index]
    if start_ip_as_int <= ip_as_int < end_ip_as_int:
        return True
    return False

if __name__ == '__main__':
    print is_china_ip('101.226.200.226')
    print is_china_ip('74.125.224.100')
