import gevent.monkey
import socket
import dpkt
import struct
import random
import time
import logging
import os
import subprocess
import shlex
from binascii import hexlify

try:
    import win_inet_pton
    gevent.monkey.patch_all(ssl=False, thread=True)
except:
    pass

LOGGER = logging.getLogger('teredo')
random.seed(time.time())

class ip_buffer_list(object):
    def __init__(self, max_buff_len, list_num=256):
        if list_num < 1:
            self.list_num = 1
        elif list_num > 2048:
            self.list_num = 2048
        else:
            self.list_num = list_num
        self.list = [[] for i in range(self.list_num)]
        self.max_buff_len = max_buff_len

    def move_to_top(self, item):
        item_p = item.copy()
        item['valid'] = False
        self.append(item_p)
        return item_p

    def _get_list_index(self, id):
        return hash(id) % self.list_num

    def append(self, dict):
        dict['valid'] = True
        _index = self._get_list_index(dict['id'])
        _list = self.list[_index]
        _list.append(dict)
        if len(_list) > max(1.2*self.max_buff_len, self.max_buff_len + 20):
            self.list[_index] = _list[len(_list)-self.max_buff_len:]

    def _find(self, id, test_func=None):
        result = None
        i = 0
        for item in reversed(self.list[self._get_list_index(id)]):
            i += 1
            if item['valid'] and item['id'] == id:
                if test_func:
                    if test_func(item):
                        result = item
                        break
                else:
                    result = item
                    break
        space = self.max_buff_len - i
        return result,space

    def find(self, id, test_func=None):
        return self._find(id, test_func)[0]

    def find_save(self, id, test_func=None, deadline=5):
        result,space = self._find(id, test_func)
        if not result:
            return None
        if space <= deadline:
            return self.move_to_top(result)
        return result


    def findall(self, id, test_func=None, do_func=None):
        result = []
        for item in reversed(self.list[self._get_list_index(id)]):
            if item['valid'] and item['id'] == id:
                if test_func:
                    if test_func(item):
                        result.append(item)
                        if do_func:
                            do_func(item)
                        break
                else:
                    result.append(item)
                    if do_func:
                        do_func(item)
                    break
        return result

    def remove(self, item):
        item['valid'] = False

    # def getall(self):
    #     result = []
    #     for i in self.list:
    #         result += i
    #     return result

    def doall(self, do_func):
        for i in self.list:
            for item in i:
                if item['valid']:
                    do_func(item)


# link_local_addr = socket.inet_pton(socket.AF_INET6, 'fe80::ffff:ffff:fffe')
# all_router_multicast = socket.inet_pton(socket.AF_INET6, 'ff02::2')
icmpv6 = 58
teredo_port = 3544
global_teredo_prefix = b'\x20\x01\x00\x00'#2001:0000:/32
blank_echo_packet = b'\x60\x00\x00\x00\x00\x0c\x3a\x20\x20\x01\x00\x00\x53\xaa\x06\x4c\
\x14\xb9\x00\x00\x00\x00\x00\x00\x26\x07\xf8\xb0\x40\x1d\x00\x05\
\x00\x00\x00\x00\x00\x00\x00\x12\x80\x00\x00\x00\x00\x00\x36\x14\
\x00\x00\x00\x00'
blank_rs_packet = b'\x60\x00\x00\x00\x00\x08\x3a\xff\xfe\x80\x00\x00\x00\x00\x00\x00\
\x00\x00\xff\xff\xff\xff\xff\xfe\xff\x02\x00\x00\x00\x00\x00\x00\
\x00\x00\x00\x00\x00\x00\x00\x02\x85\x00\x7d\x38\x00\x00\x00\x00'
teredo_servers = ['157.56.106.184','83.170.6.76','195.140.195.140','217.17.192.217']
tun_fd = None
default_teredo_client = None

import fqsocks.config_file
import config as configure
import fqsocks.httpd
import httplib
import json


@fqsocks.httpd.http_handler('GET', 'teredo-state')
def handle_teredo_state(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/json')])
    if default_teredo_client == None:
        return [json.dumps({'qualified':False,'nat_type':'DISABLED',
                            'teredo_ip':'DISABLED','local_teredo_ip':'DISABLED'})]
    return [json.dumps({'qualified': default_teredo_client.qualified,
                        'nat_type': default_teredo_client.nat_type,
                        'teredo_ip': socket.inet_ntop(socket.AF_INET6,default_teredo_client.teredo_ip) if default_teredo_client.teredo_ip else 'None',
                        'local_teredo_ip': socket.inet_ntop(socket.AF_INET6,default_teredo_client.local_teredo_ip) if default_teredo_client.local_teredo_ip else 'None'})]


@fqsocks.httpd.http_handler('POST', 'teredo-set-server')
def handle_teredo_set_server(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    server = environ['REQUEST_ARGUMENTS']['server'].value
    if not server:
        if not default_teredo_client:
            return
        server = teredo_servers[(default_teredo_client.server_index + 1) % len(teredo_servers)]
    if server not in teredo_servers:
        teredo_servers.insert(0, server)
    if default_teredo_client:
        try:
            default_teredo_client.server_ip = server
            default_teredo_client.server_index = teredo_servers.index(server)
            default_teredo_client.qualify_fail_time = 0
            default_teredo_client.send_qualify(server)
        except:
            LOGGER.exception('teredo_set_server fail')
    LOGGER.info('set teredo server to %s' % server)
    def apply(config):
        config['teredo_server'] = server
    fqsocks.config_file.update_config(apply)
    return []


def get_default_teredo_server():
    config = fqsocks.config_file._read_config()
    server = config['teredo_server']
    if not server:
        server = teredo_servers[0]
    else:
        if server in teredo_servers:
            teredo_servers.remove(server)
        teredo_servers.insert(0, server)
    LOGGER.info('default teredo server is %s' % server)
    return server

# def check_network():
#     try:
#         output = subprocess.check_output(shlex.split('ping -c 4 -W 2 -w 6 114.114.114.114'), stderr=subprocess.STDOUT)
#         if output and output.find('time=') > 0:
#             return True
#         else:
#             return False
#     except subprocess.CalledProcessError, e:
#         return False
#     except:
#         LOGGER.exception('check_network fail')
#         return True


class teredo_client(object):
    def __init__(self, sock, server_ip='157.56.106.184', server_second_ip='157.56.106.185', refresh_interval=10):
        global default_teredo_client
        default_teredo_client = self
        self.server_ip = server_ip
        self.server_second_ip = server_second_ip
        self.refresh_interval = refresh_interval
        self.random_refresh_interval = self.refresh_interval*(random.random()*0.25+0.75)
        self.last_time_with_server = time.time() - refresh_interval -1
        self.nat_type = 'UNKNOWN'
        self.old_teredo_ip = ''
        self.local_teredo_ip = ''
        self.teredo_ip = ''
        self.obfuscated_port = ''
        self.obfuscated_ip = ''
        self.wait_check_qualified = True
        self.qualify_fail_time = 0
        self.server_index = 0
        self.qualified = False
        self.packet_list = ip_buffer_list(15, 128)
        self.trusted_peer_list = ip_buffer_list(20, 256)
        self.untrusted_peer_list = ip_buffer_list(16, 8)
        self.teredo_sock = sock
        self.rs_packet,self.rs_nonce = self.create_rs_packet()


    def write_packet(self, data):
        if not tun_fd:
            LOGGER.error('tun_fd is None')
        else:
            gevent.socket.wait_write(tun_fd)
            if self.teredo_ip == self.local_teredo_ip:
                return os.write(tun_fd, data)
            src,dst = self.getaddr_ipv6(data)
            if dst == self.teredo_ip and dst != self.local_teredo_ip:
                pkt = dpkt.ip6.IP6(data)
                pkt.dst = self.local_teredo_ip
                if hasattr(pkt, 'tcp'):
                    pkt.tcp.sum = 0
                elif hasattr(pkt, 'udp'):
                    pkt.udp.sum = 0
                elif hasattr(pkt, 'icmp6'):
                    pkt.icmp6.sum = 0
                return os.write(tun_fd, str(pkt))
            return os.write(tun_fd, data)


    def stopself(self):
        raise Exception('stopself called')


    def maintain_forever(self):
        while True:
            try:
                if self.wait_check_qualified:
                    self.wait_check_qualified = False
                    if time.time() - self.last_time_with_server < 7:
                        # qualify succeed
                        self.qualified = True
                        self.qualify_fail_time = 0
                        self.random_refresh_interval = self.refresh_interval*(random.random()*0.25+0.75)
                        gevent.sleep(self.last_time_with_server + self.random_refresh_interval - time.time() + 1)
                        continue
                    else:
                        if self.qualified:
                            self.qualified = False
                            LOGGER.warning('teredo offline')
                        self.qualify_fail_time += 1
                        if self.qualify_fail_time >= 4:
                            self.server_index += 1
                            self.server_ip = teredo_servers[self.server_index % len(teredo_servers)]
                            self.qualify_fail_time = 0
                            LOGGER.warning('qualify fail for many times, change server to %s' % self.server_ip)
                if time.time() > self.last_time_with_server + self.random_refresh_interval:
                    self.wait_check_qualified = True
                    self.send_qualify(self.server_ip)
                    if LOGGER.isEnabledFor(logging.DEBUG):
                        LOGGER.debug('refresh time is up, send_qualify')
                    gevent.sleep(3)
                    continue
                self.random_refresh_interval = self.refresh_interval*(random.random()*0.25+0.75)
                gevent.sleep(self.last_time_with_server + self.random_refresh_interval - time.time() + 1)
            except Exception, e:
                LOGGER.error('maintain fail:%s' % str(e))
                gevent.sleep(3)


    def receive_forever(self):
        while True:
            try:
                self.receive()
            except:
                LOGGER.exception('teredo receive fail')


    def create_rs_packet(self):
        '''sending a Router Solicitation message'''
        default_auth_head = b'\x00\x01\x00\x00\x8a\xde\xb0\xd0\x2e\xea\x0b\xfc\x00'
        nonce = random.randint(0, 1<<62)
        nonce = struct.pack('!d', nonce)
        auth_head = bytearray(default_auth_head)
        auth_head[4:12] = nonce
        return str(auth_head) + str(blank_rs_packet),nonce

    def check_split_teredo_packet(self, data):
        auth_pkt = None
        indicate_pkt = None
        ipv6_pkt = None
        if len(data) < 40:
            raise Exception("wrong packet format when qualify, too small length")
        if data[0:2] == b'\x00\x00':
            indicate_pkt = data[0:8]
            ipv6_pkt = data[8:]
        elif data[0:2] == b'\x00\x01':
            auth_len = 13 + struct.unpack('!B', data[2])[0] + struct.unpack('!B', data[3])[0]
            auth_pkt = data[0:auth_len]
            if data[auth_len:auth_len + 2] == b'\x00\x00':
                indicate_pkt = data[auth_len:auth_len + 8]
                ipv6_pkt = data[auth_len + 8:]
            else:
                ipv6_pkt = data[auth_len:]
        else:
            ipv6_pkt = data[:]
        if auth_pkt:
            if auth_pkt[4:12] != self.rs_nonce:
                raise Exception('invalid nonce value')
        if ord(ipv6_pkt[0]) & 0xf0 != 0x60:
            raise Exception('wrong ipv6 packet')
        if struct.unpack('!H', ipv6_pkt[4:6])[0]+40 != len(ipv6_pkt):
            raise Exception('wrong ipv6 packet length')
        return auth_pkt,indicate_pkt,ipv6_pkt


    def unpack_indication(self, data):
        return struct.unpack('!2s4s', data[2:8])

    def get_addr_indication(self, data):
        data = data[2:8]
        reverse_data = bytearray()
        for c in data:
            reverse_data.append(chr(ord(c)^0xff))
        port,ip = struct.unpack('!H4s', str(reverse_data))
        ip = socket.inet_ntoa(ip)
        return port,ip

    def handle_qualify(self, indicate_pkt, ipv6_pkt):
        if not indicate_pkt:
            raise Exception('no indication packet')
        obfuscated_port,obfuscated_ip = self.unpack_indication(indicate_pkt)
        ipv6_pkt = dpkt.ip6.IP6(ipv6_pkt)
        if not hasattr(ipv6_pkt, 'icmp6') or ipv6_pkt.icmp6.type != 134:
            raise Exception('not a Router Advertisement packet')
        teredo_ip = bytearray(struct.unpack('!16s', str(ipv6_pkt)[72:72 +16])[0])
        rnd = random.randint(0,1<<16-1)
        flag = bytearray(struct.pack('!H', rnd))
        flag[0] = flag[0] & 0x3c
        teredo_ip[8:10] = flag
        teredo_ip[10:12] = obfuscated_port
        teredo_ip[12:16] = obfuscated_ip
        LOGGER.info('qualify succeed, teredo_ip:%s obfuscated_port:%s obfuscated_ip:%s'
                     % (hexlify(teredo_ip),hexlify(obfuscated_port),hexlify(obfuscated_ip)))
        self.last_time_with_server = time.time()
        return str(teredo_ip),obfuscated_port,obfuscated_ip


    def send_qualify(self, dst_ip):
        self.teredo_sock.sendto(self.rs_packet, (dst_ip, teredo_port))


    def qualify(self, dst_ip):
        self.send_qualify(dst_ip)
        self.teredo_sock.settimeout(1.5)
        begin_recv = time.time()
        data = ''
        while time.time() < 2 + begin_recv:
            data,addr = self.teredo_sock.recvfrom(8192)
            ip,port = addr
            if ip == dst_ip and port == teredo_port:
                break
        self.teredo_sock.settimeout(None)
        auth_pkt,indicate_pkt,ipv6_pkt = self.check_split_teredo_packet(data)
        return self.handle_qualify(indicate_pkt, ipv6_pkt)


    def qualify_retry(self, dst_ip):
        for i in range(4):
            try:
                return self.qualify(dst_ip)
            except:
                LOGGER.exception('qualify procedure fail once')
        return None

    def inet_ntop(self, addr):
        '''like socket.inet_ntop(socket.AF_INET6,...)
        ,AF_INET6 may be not supported when call socket.inet_ntop'''
        addr_str = bytearray()
        for i in range(0, 16, 2):
            addr_str += hexlify(addr[i:i+2])
            addr_str.append(':')
        addr_str.pop(len(addr_str) - 1)
        return str(addr_str)

    def start(self):
        res = self.qualify_retry(self.server_ip)
        self.teredo_sock.settimeout(None)
        if not res:
            self.qualified = False
            LOGGER.error('teredo qualify fail, local_addr %s:%s' % self.teredo_sock.getsockname())
            return None
        t_ip, port, ip = res
        self.teredo_ip = t_ip
        self.obfuscated_port = port
        self.obfuscated_ip = ip
        self.server_ip = socket.inet_ntoa(t_ip[4:8])
        self.qualified = True
        res = self.qualify_retry(self.server_second_ip)
        self.teredo_sock.settimeout(None)
        if not res:
            LOGGER.error('teredo second ip qualify fail, local_addr %s:%s' % self.teredo_sock.getsockname())
            return socket.inet_ntop(socket.AF_INET6, self.teredo_ip)
        t,p,i = res
        if ip == i and port == p:
            self.nat_type = 'Cone NAT'
            LOGGER.info('this device is behind one or more cone NAT')
        else:
            self.nat_type = 'Symmetric NAT'
            LOGGER.warning('this device is behind one or more Symmetric NAT')


        LOGGER.info('teredo qualify succeed, local_addr %s:%s' % self.teredo_sock.getsockname())
        # return self.inet_ntop(self.teredo_ip)
        return socket.inet_ntop(socket.AF_INET6, self.teredo_ip)


    def server_forever(self, local_teredo_ip):
        self.local_teredo_ip = socket.inet_pton(socket.AF_INET6, local_teredo_ip)
        gevent.spawn(teredo_client.receive_forever, self)
        gevent.spawn(teredo_client.maintain_forever, self)
        gevent.spawn(teredo_client.retry_connectivity_test_forever, self)


    def getaddr_ipv6(self, data):
        return struct.unpack('!16s16s', data[8:40])

    def receive(self):
        data,addr = self.teredo_sock.recvfrom(10240)
        ip,port = addr
        # if LOGGER.isEnabledFor(logging.DEBUG):
        #     LOGGER.debug('receive a packet from %s:%s' % (ip,port))
        auth_pkt,indicate_pkt,ipv6_pkt = self.check_split_teredo_packet(data)

        if ip == self.server_ip and port == teredo_port:
            self.last_time_with_server = time.time()
            if indicate_pkt:
                if len(ipv6_pkt) > 80 and ord(ipv6_pkt[6]) == icmpv6:
                    # router advertisement
                    teredo_ip,obfuscated_port,obfuscated_ip = self.handle_qualify(indicate_pkt, ipv6_pkt)
                    self.qualified = True
                    if obfuscated_ip != self.obfuscated_ip or obfuscated_port != self.obfuscated_port \
                            or self.teredo_ip[4:8] != teredo_ip[4:8]:
                        LOGGER.warning('mapped ip and port changed')
                        self.old_teredo_ip = self.teredo_ip
                        self.teredo_ip = teredo_ip
                        self.obfuscated_port = obfuscated_port
                        self.obfuscated_ip = obfuscated_ip
                else:
                    # a bubble from repeat
                    indic_port,indic_ip = self.get_addr_indication(indicate_pkt)
                    bubble_pkt = dpkt.ip6.IP6(ipv6_pkt)
                    bubble_pkt.dst = bubble_pkt.src
                    bubble_pkt.src = self.teredo_ip
                    self.teredo_sock.sendto(str(bubble_pkt), (indic_ip,indic_port))
                    if LOGGER.isEnabledFor(logging.DEBUG):
                        LOGGER.debug('receive a bubble %s:%s' % (indic_ip, indic_port))
            return

        src,dst = self.getaddr_ipv6(ipv6_pkt)
        if dst != self.teredo_ip and dst != self.old_teredo_ip:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug("receive a packet who's destination(%s) is not this device, drop it" % hexlify(dst))
            return

        if ord(ipv6_pkt[6]) == icmpv6:
            nonce = struct.unpack('!H', ipv6_pkt[44:46])[0]
            peer = self.untrusted_peer_list.find(src,lambda peer:nonce == peer['nonce'])
            if peer:
                # a icmpv6 packet for a ipv6_connectivity_test
                if LOGGER.isEnabledFor(logging.DEBUG):
                    LOGGER.debug('connectivity_test:%s OK, from %s:%s' % (hexlify(src), ip, port))
                self.untrusted_peer_list.remove(peer)
                self.trusted_peer_list.append({'id':src, 'ip':ip, 'port':port, 'last_recv':time.time()})
                return self.deque_packet(src, ip, port)

        peer = self.trusted_peer_list.find_save(src,lambda peer: peer['ip'] == ip and peer['port'] == port)
        if peer:
            # a ipv6 packet forwarded by a trusted repeat
            peer['last_recv'] = time.time()
            return self.write_packet(ipv6_pkt)

        # TODO rfc4380 5.2.3 3)If the source IPv6 address is a Teredo address
        # TODO rfc4380 5.2.3 4)If the IPv4 destination address is the Teredo IPv4 Discovery Address
        # TODO rfc4380 5.2.3 5)If the source IPv6 address is a Teredo address, and the mapped IPv4 in address do not match the source IPv4 address
        # accept the ipv6 packet by default
        return self.write_packet(ipv6_pkt)

    def is_teredo_ip(self, ip):
        return ip[0:4] == global_teredo_prefix


    def send_ipv6_packet(self, data, addr):
        if self.local_teredo_ip == self.teredo_ip:
            return self.teredo_sock.sendto(data, addr)
        src,dst = self.getaddr_ipv6(data)
        if src == self.local_teredo_ip and src != self.teredo_ip:
            pkt = dpkt.ip6.IP6(data)
            pkt.src = self.teredo_ip
            if hasattr(pkt, 'tcp'):
                pkt.tcp.sum = 0
            elif hasattr(pkt, 'udp'):
                pkt.udp.sum = 0
            elif hasattr(pkt, 'icmp6'):
                pkt.icmp6.sum = 0
            return self.teredo_sock.sendto(str(pkt), addr)
        return self.teredo_sock.sendto(data, addr)


    def transmit(self, data):
        if not self.teredo_ip:
            return
        src,dst = self.getaddr_ipv6(data)
        # if LOGGER.isEnabledFor(logging.DEBUG):
        #     LOGGER.debug('transmit, dst=%s' % hexlify(dst))
        peer = self.trusted_peer_list.find(dst)
        if peer:
            if time.time() < peer['last_recv'] + 30:
                # peer['last_send'] = time.time()
                return self.send_ipv6_packet(data, (peer['ip'], peer['port']))
                # return self.teredo_sock.sendto(data, (peer['ip'], peer['port']))
            # else:
            #     self.trusted_peer_list.remove(peer)
        if not self.is_teredo_ip(dst):
            self.packet_list.append({'id':dst, 'data':data})
            peer = {'id':dst, 'try_time':0, 'nonce':random.randint(0, 65535)}
            self.untrusted_peer_list.append(peer)
            return self.ipv6_connectivity_test(peer)
        # TODO rfc4380 5.2.4 3) If the destination is the Teredo IPv6 address of a local peer
        # TODO rfc4380 5.2.4 4) If the destination is a Teredo IPv6 address in which the cone bit 1
        # TODO rfc4380 5.2.4 5) If the destination is a Teredo IPv6 address in which the cone bit 0


    def ipv6_connectivity_test(self, peer):
        # if LOGGER.isEnabledFor(logging.DEBUG):
        #     LOGGER.debug('ipv6_connectivity_test,dst:%s try_time:%d' % (hexlify(peer['id']), peer['try_time']))
        try_time = peer['try_time'] + 1
        if try_time > 3:
            self.untrusted_peer_list.remove(peer)
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('ipv6_connectivity_test fail for %s' % hexlify(peer['id']))
            return
        if not self.qualified:
            return
        peer['try_time'] = try_time
        ip6_pkt = dpkt.ip6.IP6(blank_echo_packet)
        ip6_pkt.icmp6.echo.id = peer['nonce']
        ip6_pkt.icmp6.sum = 0
        ip6_pkt.src = self.teredo_ip
        ip6_pkt.dst = peer['id']
        self.teredo_sock.sendto(str(ip6_pkt), (self.server_ip, teredo_port))


    def retry_connectivity_test_forever(self):
        while True:
            if self.qualified:
                try:
                    self.untrusted_peer_list.doall(lambda peer:self.ipv6_connectivity_test(peer))
                except:
                    LOGGER.exception('ipv6_connectivity_test fail')
                gevent.sleep(2)
            else:
                gevent.sleep(1)


    def deque_packet(self, id, ip, port):
        def deque_send(peer):
            # self.teredo_sock.sendto(peer['data'], (ip, port))
            self.send_ipv6_packet(peer['data'], (ip, port))
            self.packet_list.remove(peer)
        self.packet_list.findall(id, do_func=deque_send)


def test_task():
    while True:
        gevent.sleep(1)

def test():
    import sys
    import logging.handlers
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
    # handler = logging.handlers.RotatingFileHandler(
    #     'teredo.log', maxBytes=1024 * 256, backupCount=0)
    # handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    # logging.getLogger('teredo').addHandler(handler)

    # import _multiprocessing
    # fdsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # fdsock.connect('\0fdsock2')
    # fd = _multiprocessing.recvfd(fdsock.fileno())
    # sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_DGRAM)
    # client = teredo_client(sock)

    client = teredo_client(socket.socket(socket.AF_INET, socket.SOCK_DGRAM), server_ip='210.225.196.89', server_second_ip='210.225.196.90')
    ip = client.start()
    if not ip:
        client.server_forever('2001:0:53aa:64c:0:1234:1234:1234')
        print('teredo start fail')
    else:
        print('teredo start succeed %s' % ip)
        client.server_forever(ip)
    greenlet = gevent.spawn(test_task)
    gevent.sleep(1)
    test_pkt = b'\x60\x00\x00\x00\x00\x20\x06\x80\x20\x01\x00\x00\x53\xaa\x06\x4c\
\x14\xb9\x00\x00\x00\x00\x00\x00\x26\x07\xf8\xb0\x40\x02\x00\x22\
\x00\x00\x00\x00\x00\x00\x00\x09\x72\x62\x01\xbb\x70\x26\x5b\x17\
\x00\x00\x00\x00\x80\x02\x80\x00\x9b\x8a\x00\x00\x02\x04\x04\xc4\
\x01\x03\x03\x00\x01\x01\x04\x02'
    ip6_pkt = dpkt.ip6.IP6(test_pkt)
    ip6_pkt.src = client.teredo_ip
    ip6_pkt.sum = 0
    ip6_pkt.tcp.sum = 0
    client.transmit(str(ip6_pkt))
    gevent.sleep(1)
    test_pkt = b'\x60\x00\x00\x00\x00\x20\x06\x80\x20\x01\x00\x00\x53\xaa\x06\x4c\
\x14\xb9\x00\x00\x00\x00\x00\x00\x26\x07\xf8\xb0\x40\x1c\x00\x0f\
\x00\x00\x00\x00\x00\x00\x00\x0c\x72\xff\x01\xbb\x3f\x29\xff\x2c\
\x00\x00\x00\x00\x80\x02\x80\x00\x27\xcb\x00\x00\x02\x04\x04\xc4\
\x01\x03\x03\x00\x01\x01\x04\x02'
    ip6_pkt = dpkt.ip6.IP6(test_pkt)
    ip6_pkt.src = client.teredo_ip
    ip6_pkt.sum = 0
    ip6_pkt.tcp.sum = 0
    client.transmit(str(ip6_pkt))
    gevent.sleep(5)
    test_pkt = b'\x60\x00\x00\x00\x00\x20\x06\x80\x20\x01\x00\x00\x53\xaa\x06\x4c\
\x14\xb9\x00\x00\x00\x00\x00\x00\x26\x07\xf8\xb0\x40\x1c\x00\x0f\
\x00\x00\x00\x00\x00\x00\x00\x0c\x72\xff\x01\xbb\x3f\x29\xff\x2c\
\x00\x00\x00\x00\x80\x02\x80\x00\x27\xcb\x00\x00\x02\x04\x04\xc4\
\x01\x03\x03\x00\x01\x01\x04\x02'
    ip6_pkt = dpkt.ip6.IP6(test_pkt)
    ip6_pkt.src = client.teredo_ip
    ip6_pkt.sum = 0
    ip6_pkt.tcp.sum = 0
    client.transmit(str(ip6_pkt))
    greenlet.join()

if '__main__' == __name__:
    test()

