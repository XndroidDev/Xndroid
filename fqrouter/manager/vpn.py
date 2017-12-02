import gevent.monkey

gevent.monkey.patch_all(ssl=False, thread=True)

import logging
import logging.handlers
import sys
import os
import _multiprocessing
import socket
import httplib
import fqdns
import fqsocks.fqsocks
import fqsocks.config_file
import fqsocks.gateways.proxy_client
import fqsocks.networking
import contextlib
import gevent
import gevent.socket
import dpkt
import config
import traceback
import urllib2
import fqsocks.httpd
import teredo
import json


current_path = os.path.dirname(os.path.abspath(__file__))
home_path = os.path.abspath(current_path + "/..")
FQROUTER_VERSION = 'ultimate'
LOGGER = logging.getLogger('fqrouter')
LOG_DIR = home_path + "/log"
MANAGER_LOG_FILE = os.path.join(LOG_DIR, 'manager.log')
FQDNS_LOG_FILE = os.path.join(LOG_DIR, 'fqdns.log')
TUN_IP = None
FAKE_USER_MODE_NAT_IP = None
nat_map = {} # sport => (dst, dport), src always be 10.25.1.1
default_dns_server = config.get_default_dns_server()

default_loacl_teredo_ip = '2001:0:53aa:64c:0:1234:1234:1234'

def setup_logging():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if os.getenv('DEBUG') else logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    handler = logging.handlers.RotatingFileHandler(
        MANAGER_LOG_FILE, maxBytes=1024 * 256, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logging.getLogger('fqrouter').addHandler(handler)
    handler = logging.handlers.RotatingFileHandler(
        FQDNS_LOG_FILE, maxBytes=1024 * 256, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logging.getLogger('fqdns').addHandler(handler)
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, 'teredo.log'), maxBytes=1024 * 256, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logging.getLogger('teredo').addHandler(handler)

setup_logging()

def send_message(message):
    fdsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    with contextlib.closing(fdsock):
        fdsock.connect('\0fdsock2')
        fdsock.sendall('%s\n' % message)


def create_udp_socket(keep_alive=False):
    fdsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    with contextlib.closing(fdsock):
        fdsock.connect('\0fdsock2')
        if keep_alive:
            fdsock.sendall('OPEN PERSIST UDP\n')
        else:
            fdsock.sendall('OPEN UDP\n')
        gevent.socket.wait_read(fdsock.fileno())
        fd = _multiprocessing.recvfd(fdsock.fileno())
        if fd <= 2:
            LOGGER.error('failed to create udp socket')
            raise socket.error('failed to create udp socket')
        sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_DGRAM)
        os.close(fd)
        return sock

def create_tcp_socket(server_ip, server_port, connect_timeout):
    fdsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    with contextlib.closing(fdsock):
        fdsock.connect('\0fdsock2')
        fdsock.sendall('OPEN TCP,%s,%s,%s\n' % (server_ip, server_port, connect_timeout * 1000))
        gevent.socket.wait_read(fdsock.fileno())
        fd = _multiprocessing.recvfd(fdsock.fileno())
        if fd <=2 :
            LOGGER.error('failed to create tcp socket: %s:%s' % (server_ip, server_port))
            raise socket.error('failed to create tcp socket: %s:%s' % (server_ip, server_port))
        sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
        os.close(fd)
        return sock

def create_teredo_sock_until_ready():
    while True:
        try:
            sock = create_udp_socket(True)
            return sock
        except:
            LOGGER.info('create_teredo_sock_until_ready:get fd fail, retry in 1 seconds')
        gevent.sleep(1)


teredo_sock = create_teredo_sock_until_ready()
teredo_client = teredo.teredo_client(teredo_sock)

fqsocks.networking.SPI['create_tcp_socket'] = create_tcp_socket
fqdns.SPI['create_udp_socket'] = create_udp_socket
fqdns.SPI['create_tcp_socket'] = create_tcp_socket


def read_tun_fd_until_ready():
    while True:
        tun_fd = read_tun_fd()
        if tun_fd:
            return tun_fd
        else:
            LOGGER.info('read_tun_fd_until_ready: get fd fail, retry in 1 seconds')
            gevent.sleep(1)


def read_tun_fd():
    fdsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    with contextlib.closing(fdsock):
        try:
            fdsock.connect('\0fdsock2')
            fdsock.sendall('TUN\n')
            gevent.socket.wait_read(fdsock.fileno(), timeout=3)
            tun_fd = _multiprocessing.recvfd(fdsock.fileno())
            if tun_fd == 1 or tun_fd < 0:
                LOGGER.error('received invalid tun fd:%d' % tun_fd)
                return None
            return tun_fd
        except:
            return None

def handle_ping(environ, start_response):
    try:
        LOGGER.info('VPN PONG/%s' % FQROUTER_VERSION)
    except:
        traceback.print_exc()
        os._exit(1)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    yield 'VPN PONG/%s' % FQROUTER_VERSION


fqsocks.httpd.HANDLERS[('GET', 'ping')] = handle_ping


def handle_exit(environ, start_response):
    gevent.spawn(exit_later)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return ['EXITING']


fqsocks.httpd.HANDLERS[('POST', 'exit')] = handle_exit


def redirect_tun_traffic(tun_fd):
    while True:
        try:
            redirect_ip_packet(tun_fd)
        except:
            LOGGER.exception('failed to handle ip packet')


def redirect_ip_packet(tun_fd):
    gevent.socket.wait_read(tun_fd)
    try:
        data = os.read(tun_fd, 8192)
    except OSError, e:
        LOGGER.error('read packet failed: %s' % e)
        gevent.sleep(3)
        return
    if ord(data[0]) & 0xf0 == 0x60:
        return teredo_client.transmit(data)
    ip_packet = dpkt.ip.IP(data)
    src = socket.inet_ntoa(ip_packet.src)
    dst = socket.inet_ntoa(ip_packet.dst)
    if hasattr(ip_packet, 'udp'):
        l4_packet = ip_packet.udp
    elif hasattr(ip_packet, 'tcp'):
        l4_packet = ip_packet.tcp
    else:
        return
    # if LOGGER.isEnabledFor(logging.DEBUG):
    #         LOGGER.debug('redirect:receive ip packet src=%s,dst=%s,sport=%d,dport=%d,pro=%s'
    #         % (src, dst, l4_packet.sport, l4_packet.dport,'udp' if hasattr(ip_packet, 'udp') else 'tcp'))
    if src != TUN_IP:
        return
    if dst == FAKE_USER_MODE_NAT_IP:
        orig_dst_addr = nat_map.get(l4_packet.dport)
        if not orig_dst_addr:
            raise Exception('failed to get original destination')
        orig_dst, orig_dport = orig_dst_addr
        ip_packet.src = socket.inet_aton(orig_dst)
        ip_packet.dst = socket.inet_aton(TUN_IP)
        ip_packet.sum = 0
        l4_packet.sport = orig_dport
        l4_packet.sum = 0
    else:
        nat_map[l4_packet.sport] = (dst, l4_packet.dport)
        ip_packet.src = socket.inet_aton(FAKE_USER_MODE_NAT_IP)
        ip_packet.dst = socket.inet_aton(TUN_IP)
        ip_packet.sum = 0
        l4_packet.dport = 12345
        l4_packet.sum = 0
    gevent.socket.wait_write(tun_fd)
    os.write(tun_fd, str(ip_packet))


def get_original_destination(sock, src_ip, src_port):
    if src_ip != FAKE_USER_MODE_NAT_IP: # fake connection from 10.25.1.100
        raise Exception('unexpected src ip: %s' % src_ip)
    return nat_map.get(src_port)


fqsocks.networking.SPI['get_original_destination'] = get_original_destination


def exit_later():
    gevent.sleep(0.5)
    os._exit(1)


class VpnUdpHandler(fqdns.DnsHandler):
    def __call__(self, sendto, request, address):
        try:
            src_ip, src_port = address
            dst_ip, dst_port = get_original_destination(None, src_ip, src_port)
            if 53 ==  get_original_destination(None, src_ip, src_port)[1]:
                super(VpnUdpHandler, self).__call__( sendto, request, address)
            else:
                sock = fqdns.create_udp_socket()
                try:
                    sock.sendto(request, (dst_ip, dst_port))
                    response = sock.recv(8192)
                    sendto(response, address)
                finally:
                    sock.close()
        except:
            LOGGER.exception('failed to handle udp')

DNS_HANDLER = VpnUdpHandler(
    enable_china_domain=True, enable_hosted_domain=True,
    original_upstream=('udp', default_dns_server, 53) if default_dns_server else None)

fqsocks.networking.DNS_HANDLER = DNS_HANDLER

@fqsocks.httpd.http_handler('GET', 'teredo-state')
def handle_teredo_state(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/json')])
    return [json.dumps({'qualified': teredo_client.qualified,
                        'nat_type': teredo_client.nat_type,
                        'teredo_ip': socket.inet_ntop(socket.AF_INET6,teredo_client.teredo_ip) if teredo_client.teredo_ip else 'None',
                        'local_teredo_ip': socket.inet_ntop(socket.AF_INET6,teredo_client.local_teredo_ip)})]


if '__main__' == __name__:
    LOGGER.info('environment: %s' % os.environ.items())
    LOGGER.info('default dns server: %s' % default_dns_server)
    # FQROUTER_VERSION = os.getenv('FQROUTER_VERSION')
    try:
        gevent.monkey.patch_ssl()
    except:
        LOGGER.exception('failed to patch ssl')

    teredo_ip = None
    try:
        teredo_ip = teredo_client.start()
    except:
        LOGGER.exception('start teredo fail')
    if not teredo_ip:
        LOGGER.error('start teredo client fail, use default:%s' % default_loacl_teredo_ip)
        teredo_client.server_forever(default_loacl_teredo_ip)
        send_message('TEREDO FAIL,%s' % default_loacl_teredo_ip)
    else:
        LOGGER.info('teredo start succeed, teredo ip:%s' % teredo_ip)
        teredo_client.server_forever(teredo_ip)
        send_message('TEREDO READY,%s' % teredo_ip)

    TUN_IP = sys.argv[1]
    FAKE_USER_MODE_NAT_IP = sys.argv[2]
    args = [
        '--log-level', 'DEBUG' if os.getenv('DEBUG') else 'INFO',
        '--log-file', LOG_DIR + '/fqsocks.log',
        '--tcp-gateway-listen', '%s:12345' % TUN_IP,
        '--dns-server-listen', '%s:12345' % TUN_IP,
        '--no-http-manager', # already started before
        '--no-tcp-scrambler', # no root permission
    ]
    args = config.configure_fqsocks(args)
    fqsocks.fqsocks.init_config(args)
    fqsocks.config_file.path = home_path + '/etc/fqsocks.json'
    http_manager_port = fqsocks.config_file.read_config()['http_manager']['port']
    try:
        response = urllib2.urlopen('http://127.0.0.1:%s/exit' % http_manager_port, '').read()
        if 'EXITING' == response:
            LOGGER.critical('!!! find previous instance, exiting !!!')
            gevent.sleep(3)
    except:
        LOGGER.warning('try to exit previous fail')

    fqsocks.httpd.LISTEN_IP, fqsocks.httpd.LISTEN_PORT = '', http_manager_port
    fqsocks.httpd.server_greenlet = gevent.spawn(fqsocks.httpd.serve_forever)
    try:
        tun_fd = read_tun_fd_until_ready()
        LOGGER.info('tun fd: %s' % tun_fd)
    except:
        LOGGER.exception('failed to get tun fd')
        sys.exit(1)

    teredo.tun_fd = tun_fd

    gevent.spawn(fqsocks.fqsocks.main)
    greenlet = gevent.spawn(redirect_tun_traffic, tun_fd)
    greenlet.join()
