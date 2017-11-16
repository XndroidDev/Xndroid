import signal
import socket
import logging
import os
import time
import argparse

import dpkt.ip

LOGGER = logging.getLogger(__name__)

udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
udp_socket.setblocking(False)
SO_MARK = 36
udp_socket.setsockopt(socket.SOL_SOCKET, SO_MARK, 0xcafe)
udp_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, 250)
SERVER_IP = None
SERVER_PORT = None

def main():
    global SERVER_IP, SERVER_PORT
    from netfilterqueue import NetfilterQueue

    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--log-file')
    argument_parser.add_argument('--log-level', choices=['INFO', 'DEBUG'], default='INFO')
    argument_parser.add_argument('--queue-number', default=0, type=int)
    argument_parser.add_argument('server', help='x.x.x.x:19842')
    args = argument_parser.parse_args()
    log_level = getattr(logging, args.log_level)
    logging.getLogger().setLevel(log_level)
    logging.getLogger().handlers = []
    if args.log_file:
        handler = logging.handlers.RotatingFileHandler(
            args.log_file, maxBytes=1024 * 16, backupCount=0)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        handler.setLevel(log_level)
        logging.getLogger().addHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    handler.setLevel(log_level)
    logging.getLogger().addHandler(handler)
    signal.signal(signal.SIGTERM, lambda signum, fame: os._exit(1))
    signal.signal(signal.SIGINT, lambda signum, fame: os._exit(1))
    SERVER_IP, SERVER_PORT = args.server.split(':')
    SERVER_PORT = int(SERVER_PORT)

    nfqueue = NetfilterQueue()
    nfqueue.bind(args.queue_number, handle_nfqueue_element)
    LOGGER.info('fquni client started')
    nfqueue.run()


def handle_nfqueue_element(nfqueue_element):
    try:
        raw_ip_packet = nfqueue_element.get_payload()
        try:
            ip_packet = dpkt.ip.IP(raw_ip_packet)
        except:
            LOGGER.error('not ip packet')
            nfqueue_element.accept()
            return
        l4_packet = getattr(ip_packet, 'tcp', None) or getattr(ip_packet, 'udp', None)
        if not l4_packet:
            LOGGER.error('%s not tcp or udp' % repr(ip_packet))
            nfqueue_element.accept()
            return
        ip_packet.src_ip = socket.inet_ntoa(ip_packet.src)
        ip_packet.dst_ip = socket.inet_ntoa(ip_packet.dst)
        if SERVER_IP == ip_packet.dst_ip:
            nfqueue_element.accept()
            return
        if getattr(ip_packet, 'tcp', None) and dpkt.tcp.TH_SYN == ip_packet.tcp.flags:
            LOGGER.info('%s:%s =syn=> %s:%s' % (ip_packet.src_ip, ip_packet.tcp.sport, ip_packet.dst_ip, ip_packet.tcp.dport))
        elif getattr(ip_packet, 'udp', None) and 53 == ip_packet.udp.dport:
            LOGGER.info('%s:%s =dns=> %s:%s' % (ip_packet.src_ip, ip_packet.udp.sport, ip_packet.dst_ip, ip_packet.udp.dport))
        udp_socket.sendto(raw_ip_packet, (SERVER_IP, SERVER_PORT))
        ip_packet.ttl = 3
        l4_packet.sum = 1
        ip_packet.sum = 0
        nfqueue_element.set_payload(str(ip_packet))
        nfqueue_element.accept()
    except:
        LOGGER.exception('failed to handle nfqueue element')
        time.sleep(3)

if '__main__' == __name__:
    main()