import logging
import socket
import sys

import gevent
import gevent.monkey
from gevent.server import DatagramServer
import dpkt.ip
import dpkt.dns
import dpkt.tcp
import resource
import signal
import os

resource.setrlimit(resource.RLIMIT_NOFILE, (8000, 8000))

LOGGER = logging.getLogger(__name__)

raw_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
raw_socket.setsockopt(socket.SOL_IP, socket.IP_HDRINCL, 1)


class HandlerDatagramServer(gevent.server.DatagramServer):
    def __init__(self, address, handler):
        super(HandlerDatagramServer, self).__init__(address)
        self.handler = handler

    def handle(self, request, address):
        self.handler(self.sendto, request, address)


def handle_udp(sendto, raw_request, address):
    try:
        ip_packet = dpkt.ip.IP(raw_request)
    except:
        LOGGER.error('%s invalid request' % repr(address))
        return
    l4_packet = getattr(ip_packet, 'tcp', None) or getattr(ip_packet, 'udp', None)
    if not l4_packet:
        LOGGER.error('%s not tcp or udp' % repr(address))
        return
    try:
        ip_packet.src = socket.inet_aton(address[0])
        l4_packet.sum = 0
        ip_packet.sum = 0
        dst_ip = socket.inet_ntoa(ip_packet.dst)
        if getattr(ip_packet, 'tcp', None) and dpkt.tcp.TH_SYN == ip_packet.tcp.flags:
            LOGGER.info('%s:%s =syn=> %s:%s' % (address[0], ip_packet.tcp.sport, dst_ip, ip_packet.tcp.dport))
        elif getattr(ip_packet, 'udp', None) and 53 == ip_packet.udp.dport:
            LOGGER.info('%s:%s =dns=> %s:%s' % (address[0], ip_packet.udp.sport, dst_ip, ip_packet.udp.dport))
        raw_socket.sendto(str(ip_packet), (dst_ip, 0))
    except:
        LOGGER.exception('failed to send')


def start_udp_server():
    LISTEN_IP = ''
    LISTEN_PORT = 19842
    server = HandlerDatagramServer((LISTEN_IP, LISTEN_PORT), handle_udp)
    LOGGER.info('serving fquni server %s:%s...' % (LISTEN_IP, LISTEN_PORT))
    server.serve_forever()


def main():
    logging.basicConfig(stream=sys.stdout, level='INFO', format='%(asctime)s %(levelname)s %(message)s')
    signal.signal(signal.SIGTERM, lambda signum, fame: os._exit(1))
    signal.signal(signal.SIGINT, lambda signum, fame: os._exit(1))
    gevent.monkey.patch_all()
    start_udp_server()


if '__main__' == __name__:
    main()
