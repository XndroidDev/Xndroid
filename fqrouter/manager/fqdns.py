#!/usr/bin/env python
# thanks @phuslu https://github.com/phus/dnsproxy/blob/master/dnsproxy.py
# thanks @ofmax https://github.com/madeye/gaeproxy/blob/master/assets/modules/python.mp3
import argparse
import socket
import logging
import logging.handlers
import sys
import select
import contextlib
import time
import struct
import json
import random
import os

import dpkt
import gevent.server
import gevent.queue
import gevent.monkey
import fqsocks.china_ip


LOGGER = logging.getLogger('fqdns')

ERROR_NO_DATA = 11
SO_MARK = 36
OUTBOUND_MARK = 0
OUTBOUND_IP = None
SPI = {}


def main():
    global OUTBOUND_MARK
    global OUTBOUND_IP
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--log-file')
    argument_parser.add_argument('--log-level', choices=['INFO', 'DEBUG'], default='INFO')
    argument_parser.add_argument('--outbound-mark', help='for example 0xcafe, set to every packet send out',
                                 default='0')
    argument_parser.add_argument('--outbound-ip', help='the ip address for every packet send out')
    sub_parsers = argument_parser.add_subparsers()
    resolve_parser = sub_parsers.add_parser('resolve', help='start as dns client')
    resolve_parser.add_argument('domain')
    resolve_parser.add_argument(
        '--at', help='one or more dns servers', default=[], action='append')
    resolve_parser.add_argument(
        '--strategy', help='anti-GFW strategy, for UDP only', default='pick-right',
        choices=['pick-first', 'pick-later', 'pick-right', 'pick-right-later', 'pick-all'])
    resolve_parser.add_argument('--timeout', help='in seconds', default=1, type=float)
    resolve_parser.add_argument('--record-type', default='A', choices=['A', 'TXT'])
    resolve_parser.add_argument('--retry', default=1, type=int)
    resolve_parser.set_defaults(handler=resolve)
    discover_parser = sub_parsers.add_parser('discover', help='resolve black listed domain to discover wrong answers')
    discover_parser.add_argument('--at', help='dns server', default='8.8.8.8:53')
    discover_parser.add_argument('--timeout', help='in seconds', default=1, type=float)
    discover_parser.add_argument('--repeat', help='repeat query for each domain many times', default=30, type=int)
    discover_parser.add_argument('--only-new', help='only show the new wrong answers', action='store_true')
    discover_parser.add_argument(
        '--domain', help='black listed domain such as twitter.com', default=[], action='append')
    discover_parser.set_defaults(handler=discover)
    serve_parser = sub_parsers.add_parser('serve', help='start as dns server')
    serve_parser.add_argument('--listen', help='local address bind to', default='*:53')
    serve_parser.add_argument(
        '--upstream', help='upstream dns server forwarding to for non china domain', default=[], action='append')
    serve_parser.add_argument(
        '--china-upstream', help='upstream dns server forwarding to for china domain', default=[], action='append')
    serve_parser.add_argument(
        '--original-upstream', help='the original dns server')
    serve_parser.add_argument(
        '--hosted-domain', help='the domain a.com will be transformed to a.com.b.com', default=[], action='append')
    serve_parser.add_argument(
        '--hosted-at', help='the domain b.com will host a.com.b.com')
    serve_parser.add_argument(
        '--enable-china-domain', help='otherwise china domain will not query against china-upstreams',
        action='store_true')
    serve_parser.add_argument(
        '--enable-hosted-domain', help='otherwise hosted domain will not query with suffix hosted-at',
        action='store_true')
    serve_parser.add_argument(
        '--fallback-timeout', help='fallback from udp to tcp after timeout, in seconds')
    serve_parser.add_argument(
        '--strategy', help='anti-GFW strategy, for UDP only', default='pick-right',
        choices=['pick-first', 'pick-later', 'pick-right', 'pick-right-later', 'pick-all'])
    serve_parser.set_defaults(handler=serve)
    args = argument_parser.parse_args()
    OUTBOUND_MARK = eval(args.outbound_mark)
    OUTBOUND_IP = args.outbound_ip
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(stream=sys.stdout, level=log_level, format='%(asctime)s %(levelname)s %(message)s')
    if args.log_file:
        handler = logging.handlers.RotatingFileHandler(
            args.log_file, maxBytes=1024 * 256, backupCount=0)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        handler.setLevel(log_level)
        logging.getLogger('fqdns').addHandler(handler)
    gevent.monkey.patch_all(thread=False, ssl=False)
    try:
        gevent.monkey.patch_ssl()
    except:
        LOGGER.exception('failed to patch ssl')
    return_value = args.handler(**{k: getattr(args, k) for k in vars(args) \
                                   if k not in {'handler', 'log_file', 'log_level', 'outbound_mark', 'outbound_ip'}})
    sys.stderr.write(json.dumps(return_value))
    sys.stderr.write('\n')


def DnsHandler(listen, upstream, china_upstream, hosted_domain, hosted_at,
          enable_china_domain, enable_hosted_domain, fallback_timeout,
          strategy, original_upstream):
    address = parse_ip_colon_port(listen)
    upstreams = [parse_ip_colon_port(e) for e in upstream]
    china_upstreams = [parse_ip_colon_port(e) for e in china_upstream]
    if original_upstream:
        original_upstream = parse_ip_colon_port(original_upstream)
    handler = DnsHandler(
        upstreams, enable_china_domain, china_upstreams, original_upstream,
        enable_hosted_domain, hosted_domain, hosted_at, fallback_timeout, strategy)
    server = HandlerDatagramServer(address, handler)
    LOGGER.info('dns server started at %r, forwarding to %r', address, upstreams)
    try:
        server.serve_forever()
    except:
        LOGGER.exception('dns server failed')
    finally:
        LOGGER.info('dns server stopped')


class HandlerDatagramServer(gevent.server.DatagramServer):
    def __init__(self, address, handler):
        super(HandlerDatagramServer, self).__init__(address)
        self.handler = handler

    def serve_forever(self, stop_timeout=None):
        LOGGER.info('serving udp at %s:%s' % (self.address[0], self.address[1]))
        try:
            super(HandlerDatagramServer, self).serve_forever(stop_timeout)
        finally:
            LOGGER.info('stopped udp at %s:%s' % (self.address[0], self.address[1]))

    def handle(self, request, address):
        self.handler(self.sendto, request, address)


class DnsHandler(object):
    def __init__(
            self, upstreams=(), enable_china_domain=True, china_upstreams=(), original_upstream=None,
            enable_hosted_domain=False, hosted_domains=(), hosted_at='no_available_host!',
            fallback_timeout=None, strategy=None):
        super(DnsHandler, self).__init__()
        self.upstreams = []
        if upstreams:
            for ip, port in upstreams:
                self.upstreams.append(('udp', ip, port))
            for ip, port in upstreams:
                self.upstreams.append(('tcp', ip, port))
        else:
            self.upstreams.append(('udp', '80.90.43.162', 5678))
            self.upstreams.append(('udp', '77.66.84.233', 443))
            self.upstreams.append(('udp', '176.56.237.171', 443))
            self.upstreams.append(('udp', '208.67.220.123', 443))
            self.upstreams.append(('udp', '142.4.204.111', 443))
            self.upstreams.append(('udp', '142.4.205.47', 443))
            self.upstreams.append(('udp', '146.185.134.104', 54))
            self.upstreams.append(('udp', '178.216.201.222', 2053))
            random.shuffle(self.upstreams)
            self.upstreams.append(('udp', '208.67.222.222', 443))
            self.upstreams.append(('udp', '208.67.220.220', 443))
            self.upstreams.append(('tcp', '208.67.222.222', 443))
            self.upstreams.append(('tcp', '208.67.220.220', 443))
            self.upstreams.append(('tcp', '80.90.43.162', 5678))
            self.upstreams.append(('tcp', '113.20.8.17', 443))
            self.upstreams.append(('tcp', '95.141.34.162', 5678))
            self.upstreams.append(('tcp', '77.66.84.233', 443))
            self.upstreams.append(('tcp', '176.56.237.171', 443))
            self.upstreams.append(('tcp', '208.67.220.123', 443))
            self.upstreams.append(('tcp', '142.4.204.111', 443))
            self.upstreams.append(('tcp', '142.4.205.47', 443))
            self.upstreams.append(('tcp', '146.185.134.104', 54))
            self.upstreams.append(('tcp', '178.216.201.222', 2053))
        self.china_upstreams = []
        if enable_china_domain:
            if china_upstreams:
                for ip, port in china_upstreams:
                    self.china_upstreams.append(('udp', ip, port))
                for ip, port in china_upstreams:
                    self.china_upstreams.append(('tcp', ip, port))
            else:
                self.china_upstreams.append(('udp', '114.114.114.114', 53))
                self.china_upstreams.append(('udp', '182.254.116.116', 53))
                self.china_upstreams.append(('udp', '182.254.118.118', 53))
                self.china_upstreams.append(('udp', '223.5.5.5', 53))
                self.china_upstreams.append(('udp', '114.114.115.115', 53))
        self.original_upstream = original_upstream
        self.failed_times = {}
        self.enable_hosted_domain = enable_hosted_domain
        self.hosted_at = hosted_at
        self.fallback_timeout = fallback_timeout or 2
        self.strategy = strategy or 'pick-right'

    def test_upstreams(self):
        LOGGER.info('!!! test upstreams: %s' % self.upstreams)
        greenlets = []
        queue = gevent.queue.Queue()
        good_upstreams = []
        try:
            for server in self.upstreams:
                server_type, server_ip, server_port = server
                greenlets.append(gevent.spawn(
                    resolve_one, dpkt.dns.DNS_A, 'facebook.com', server_type,
                    server_ip, server_port, 3, 'pick-right', queue))
            while True:
                try:
                    server, answers = queue.get(timeout=2)
                    if isinstance(answers, NoSuchDomain):
                        LOGGER.error('%s test failed: no such domain' % str(server))
                        continue
                    if len(answers) == 0:
                        LOGGER.error('%s test failed: 0 answer' % str(server))
                        continue
                    if len(answers) > 1:
                        LOGGER.error('%s test failed: more than 1 answer' % str(server))
                        continue
                    # if '1.2.3.4' != answers[0]:
                    #     LOGGER.error('%s test failed: wrong answer' % str(server))
                    #     continue
                    LOGGER.info('%s is good' % str(server))
                    good_upstreams.append(server)
                    if len(good_upstreams) > 3:
                        self.upstreams = good_upstreams
                        return
                except gevent.queue.Empty:
                    return
        finally:
            # for greenlet in greenlets:
            #     greenlet.kill(block=False)
            if not good_upstreams:
                LOGGER.warn('!!! no good upstream !!!')
                # sys.exit(1)


    def __call__(self, sendto, raw_request, address):
        request = dpkt.dns.DNS(raw_request)
        request.raw_request = raw_request
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('received downstream request from %s: %s' % (str(address), repr(request)))
        try:
            response = self.query(request, raw_request)
        except:
            report_error('failed to query %s' % repr(request))
            return
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('forward response to downstream %s: %s' % (str(address), repr(response)))
        try:
            serialized_response = str(response)
        except:
            report_error('failed to serialize response to query %s' % repr(request))
            return
        sendto(serialized_response, address)

    def query(self, request, raw_request):
        response = dpkt.dns.DNS(raw_request)
        response.set_qr(True)
        if request.qd and dpkt.dns.DNS_AAAA == request.qd[0].type: # IPV6 not supported
            response.set_rcode(dpkt.dns.DNS_RCODE_NXDOMAIN)
            return response
        domains = [question.name for question in request.qd if dpkt.dns.DNS_A == question.type]
        if len(domains) != 1:
            return self.query_directly(request)
        domain = domains[0]
        if '.' not in domain or domain.endswith('.lan') or domain.endswith('.localdomain'):
            response.set_rcode(dpkt.dns.DNS_RCODE_NXDOMAIN)
            if self.original_upstream:
                response = query_directly_once(request, self.original_upstream, self.fallback_timeout) or response
            return response
        else:
            try:
                if self.enable_hosted_domain and is_hosted_domain(domain):
                    query_hosted_greenlet = gevent.spawn(self.query_hosted, domain)
                    answers = self.query_smartly(domain)
                    answers = query_hosted_greenlet.get() or answers
                else:
                    answers = self.query_smartly(domain)
                response.an = []
                for answer in answers:
                    rdata = socket.inet_aton(answer)
                    rr = dpkt.dns.DNS.RR(
                        name=domain, type=dpkt.dns.DNS_A, ttl=3600,
                        rlen=len(rdata),
                        rdata=rdata)
                    rr.ip = rdata
                    response.an.append(rr)
                return response
            except NoSuchDomain:
                response.set_rcode(dpkt.dns.DNS_RCODE_NXDOMAIN)
                return response

    def query_hosted(self, domain):
        try:
            first_upstream = self.upstreams[0]
            _, answers = resolve_once(
                dpkt.dns.DNS_A, '%s.%s' % (domain, self.hosted_at),
                [first_upstream], self.fallback_timeout, strategy=self.strategy)
            LOGGER.info('hosted %s => %s' % (domain, answers))
            return answers
        except:
            return None

    def query_smartly(self, domain):
        first_china_upstream = self.china_upstreams[0]
        if self.china_upstreams and is_china_domain(domain):
            try:
                if self.original_upstream:
                    picked_upstreams = [first_china_upstream, self.original_upstream]
                else:
                    picked_upstreams = [first_china_upstream]
                _, answers = resolve_once(
                    dpkt.dns.DNS_A, domain, picked_upstreams, self.fallback_timeout, strategy=self.strategy)
                return answers
            except ResolveFailure:
                pass # try following
            sample_china_upstreams = pick_three(self.china_upstreams[1:]) + [random.choice(self.upstreams)]
            try:
                _, answers = resolve_once(
                    dpkt.dns.DNS_A, domain, sample_china_upstreams, self.fallback_timeout, strategy=self.strategy)
                self.demote_china_upstream(first_china_upstream)
                return answers
            except ResolveFailure:
                pass # try following
        else:
            first_upstream = self.upstreams[0]
            try:
                picked_upstreams = [first_upstream, first_china_upstream]
                if is_blocked_domain(domain):
                    picked_upstreams = [first_upstream]
                _, answers = resolve_once(
                    dpkt.dns.DNS_A, domain, picked_upstreams, self.fallback_timeout, strategy=self.strategy)
                return answers
            except ResolveFailure:
                pass # try following
            sample_upstreams = pick_three(self.upstreams[1:])
            try:
                _, answers = resolve_once(
                    dpkt.dns.DNS_A, domain, sample_upstreams, self.fallback_timeout, strategy=self.strategy)
                self.demote_upstream(first_upstream)
                return answers
            except ResolveFailure:
                pass # try following
        if self.original_upstream:
            _, answers = resolve_once(
                dpkt.dns.DNS_A, domain, [self.original_upstream], self.fallback_timeout, strategy=self.strategy)
            LOGGER.critical('WTF! this network is doomed')
        raise ResolveFailure('no upstream can resolve: %s' % domain)

    def query_directly(self, request):
        if self.original_upstream and any(True for question in request.qd if dpkt.dns.DNS_PTR == question.type):
            response = query_directly_once(request, self.original_upstream, self.fallback_timeout)
            if response:
                return response
        random_upstream = random.choice(self.upstreams)
        response = query_directly_once(request, random_upstream, self.fallback_timeout)
        if response:
            return response
        random_upstream = random.choice(self.upstreams)
        response = query_directly_once(request, random_upstream, self.fallback_timeout * 2)
        if response:
            return response
        if self.original_upstream:
            response = query_directly_once(request, self.original_upstream, self.fallback_timeout)
            if response:
                LOGGER.critical('WTF! this network is doomed')
        raise ResolveFailure('no upstream can query directly: %s' % repr(request))

    def demote_upstream(self, first_upstream):
        if first_upstream == self.upstreams[0]:
            LOGGER.error('!!! put %s %s:%s to tail' % first_upstream)
            self.upstreams.remove(first_upstream)
            self.upstreams.append(first_upstream)

    def demote_china_upstream(self, first_upstream):
        if not first_upstream:
            return
        if first_upstream == self.china_upstreams[0]:
            LOGGER.error('!!! put %s %s:%s to tail' % first_upstream)
            self.china_upstreams.remove(first_upstream)
            self.china_upstreams.append(first_upstream)


def pick_three(full_list):
    return random.sample(full_list, min(len(full_list), 3))


def query_directly_once(request, upstream, timeout):
    server_type, server_ip, server_port = upstream
    begin_time = time.time()
    try:
        if 'udp' == server_type:
            response = query_directly_over_udp(request, server_ip, server_port, timeout)
        elif 'tcp' == server_type:
            response = query_directly_over_udp(request, server_ip, server_port, timeout)
        else:
            LOGGER.error('unsupported server type: %s' % server_type)
            return None
        elapsed_seconds = time.time() - begin_time
        LOGGER.info('%s://%s:%s query %s directly => %s, took %0.2f'
                    % (server_type, server_ip, server_port, repr(request), repr(response), elapsed_seconds))
        return response
    except:
        elapsed_seconds = time.time() - begin_time
        report_error('%s://%s:%s query %s directly failed, took %0.2f'
                     % (server_type, server_ip, server_port, repr(request), elapsed_seconds))
        return None


def query_directly_over_udp(request, server_ip, server_port, timeout):
    if hasattr(request, 'raw_request'):
        raw_request = request.raw_request
    else:
        raw_request = str(request)
    sock = create_udp_socket()
    with contextlib.closing(sock):
        sock.settimeout(timeout)
        sock.sendto(raw_request, (server_ip, server_port))
        response = dpkt.dns.DNS(sock.recv(2048))
        if request.qd and request.qd[0].type != dpkt.dns.DNS_TXT and response.get_rcode() & dpkt.dns.DNS_RCODE_NXDOMAIN:
            return response
        for i in range(5):
            if 0 == len(response.an):
                response = dpkt.dns.DNS(sock.recv(2048))
            elif request.qd[0].type == dpkt.dns.DNS_TXT and response.an[0].type != dpkt.dns.DNS_TXT:
                response = dpkt.dns.DNS(sock.recv(2048))
            else:
                return response
        raise Exception('udp://%s:%s query directly returned type with bad type response: %s'
                        % (server_ip, server_port, repr(response)))


def query_directly_over_tcp(request, server_ip, server_port, timeout):
    if hasattr(request, 'raw_request'):
        raw_request = request.raw_request
    else:
        raw_request = str(request)
    sock = create_tcp_socket(server_ip, server_port, connect_timeout=3)
    with contextlib.closing(sock):
        sock.settimeout(timeout)
        data = raw_request
        sock.send(struct.pack('>h', len(data)) + data)
        data = sock.recv(8192)
        if len(data) < 3:
            raise Exception('response incomplete')
        data = data[2:]
        response = dpkt.dns.DNS(data)
        if request.qd and request.qd[0].type != dpkt.dns.DNS_TXT and response.get_rcode() & dpkt.dns.DNS_RCODE_NXDOMAIN:
            return response
        if 0 == len(response.an):
            raise Exception('tcp://%s:%s query directly returned empty response: %s'
                            % (server_ip, server_port, repr(response)))
        return response


def resolve(record_type, domain, at, timeout, strategy='pick-right', retry=1):
    record_type = getattr(dpkt.dns, 'DNS_%s' % record_type)
    servers = [parse_dns_server_specifier(e) for e in at] or [('udp', '8.8.8.8', 53)]
    for i in range(retry):
        try:
            return resolve_once(record_type, domain, servers, timeout, strategy)[1]
        except ResolveFailure:
            LOGGER.warn('did not finish resolving %s via %s' % (domain, at))
        except NoSuchDomain:
            LOGGER.warn('no such domain: %s' % domain)


def resolve_once(record_type, domain, servers, timeout, strategy):
    greenlets = []
    queue = gevent.queue.Queue()
    try:
        for server in servers:
            server_type, server_ip, server_port = server
            greenlets.append(gevent.spawn(
                resolve_one, record_type, domain, server_type,
                server_ip, server_port, timeout, strategy, queue))
        try:
            server, answers = queue.get(timeout=timeout)
            if isinstance(answers, NoSuchDomain):
                raise answers
            return server, answers
        except gevent.queue.Empty:
            raise ResolveFailure()
    finally:
        for greenlet in greenlets:
            greenlet.kill(block=False)


class ResolveFailure(Exception):
    pass


def parse_dns_server_specifier(dns_server_specifier):
    if '://' in dns_server_specifier:
        server_type, _, ip_and_port = dns_server_specifier.partition('://')
        ip, port = parse_ip_colon_port(ip_and_port)
        return server_type, ip, port
    else:
        ip, port = parse_ip_colon_port(dns_server_specifier)
        return 'udp', ip, port


def parse_ip_colon_port(ip_colon_port):
    if ':' in ip_colon_port:
        server_ip, server_port = ip_colon_port.split(':')
        server_port = int(server_port)
    else:
        server_ip = ip_colon_port
        server_port = 53
    return '' if '*' == server_ip else server_ip, server_port


def resolve_one(record_type, domain, server_type, server_ip, server_port, timeout, strategy, queue):
    server = (server_type, server_ip, server_port)
    begin_time = time.time()
    answers = []
    try:
        if 'udp' == server_type:
            answers = resolve_over_udp(record_type, domain, server_ip, server_port, timeout, strategy)
        elif 'tcp' == server_type:
            answers = resolve_over_tcp(record_type, domain, server_ip, server_port, timeout)
        else:
            LOGGER.error('unsupported server type: %s' % server_type)
    except NoSuchDomain as e:
        queue.put((server, e))
        return
    except:
        LOGGER.exception('failed to resolve one: %s' % domain)
    if answers:
        if answers[0] in WRONG_ANSWERS:
            LOGGER.info('%s://%s:%s resolved %s => %s' % (server_type, server_ip, server_port, domain, answers))
            LOGGER.critical('!!! should not resolve wrong answer')
            return
        queue.put((server, answers))
        elapsed_seconds = time.time() - begin_time
        LOGGER.info('%s://%s:%s resolved %s => %s, took %0.2f' % (server_type, server_ip, server_port, domain, answers, elapsed_seconds))


def resolve_over_tcp(record_type, domain, server_ip, server_port, timeout):
    try:
        sock = create_tcp_socket(server_ip, server_port, connect_timeout=3)
    except gevent.GreenletExit:
        return []
    except:
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.exception('failed to connect to %s:%s' % (server_ip, server_port))
        else:
            report_error('failed to connect to %s:%s' % (server_ip, server_port))
        return []
    try:
        with contextlib.closing(sock):
            sock.settimeout(timeout)
            request = dpkt.dns.DNS(id=get_transaction_id(), qd=[dpkt.dns.DNS.Q(name=domain, type=record_type)])
            LOGGER.debug('send request: %s' % repr(request))
            data = str(request)
            sock.send(struct.pack('>h', len(data)) + data)
            data = sock.recv(8192)
            data = data[2:]
            response = dpkt.dns.DNS(data)
            if response.get_rcode() & dpkt.dns.DNS_RCODE_NXDOMAIN:
                raise NoSuchDomain()
            if not is_right_response(server_ip, response): # filter opendns "nxdomain"
                response = None
            if response:
                if dpkt.dns.DNS_A == record_type:
                    return list_ipv4_addresses(response)
                elif dpkt.dns.DNS_TXT == record_type:
                    return [answer.text[0] for answer in response.an]
                else:
                    LOGGER.error('unsupported record type: %s' % record_type)
                    return []
            else:
                return []
    except gevent.GreenletExit:
        return []
    except NoSuchDomain:
        raise
    except:
        report_error('failed to resolve %s via tcp://%s:%s' % (domain, server_ip, server_port))
        return []


def report_error(msg):
    if LOGGER.isEnabledFor(logging.DEBUG):
        LOGGER.exception(msg)
    else:
        if str(sys.exc_info()[1]):
            LOGGER.error('%s due to %s' % (msg, sys.exc_info()[1]))
        else:
            LOGGER.exception(msg)

def resolve_over_udp(record_type, domain, server_ip, server_port, timeout, strategy):
    sock = create_udp_socket()
    try:
        with contextlib.closing(sock):
            sock.settimeout(timeout)
            request = dpkt.dns.DNS(id=get_transaction_id(), qd=[dpkt.dns.DNS.Q(name=domain, type=record_type)])
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('send request: %s' % repr(request))
            sock.sendto(str(request), (server_ip, server_port))
            if dpkt.dns.DNS_A == record_type:
                responses = pick_responses(server_ip, sock, timeout, strategy)
                if 'pick-all' == strategy:
                    return [list_ipv4_addresses(response) for response in responses]
                if len(responses) == 1:
                    return list_ipv4_addresses(responses[0])
                elif len(responses) > 1:
                    ips = []
                    for response in responses:
                        ips.extend(list_ipv4_addresses(response))
                    return ips
                else:
                    return []
            elif dpkt.dns.DNS_TXT == record_type:
                response = dpkt.dns.DNS(sock.recv(8192))
                LOGGER.debug('received response: %s' % repr(response))
                return [answer.text[0] for answer in response.an]
            else:
                LOGGER.error('unsupported record type: %s' % record_type)
                return []
    except gevent.GreenletExit:
        return []
    except NoSuchDomain:
        raise
    except:
        report_error('failed to resolve %s via udp://%s:%s' % (domain, server_ip, server_port))
        return []


def get_transaction_id():
    return random.randint(1, 65535)


def pick_responses(server_ip, sock, timeout, strategy):
    picked_responses = []
    started_at = time.time()
    deadline = started_at + timeout
    remaining_timeout = deadline - time.time()
    try:
        while remaining_timeout > 0:
            sock.settimeout(remaining_timeout)
            response = dpkt.dns.DNS(sock.recv(8192))
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('received response: %s' % repr(response))
            if response.get_rcode() & dpkt.dns.DNS_RCODE_NXDOMAIN:
                raise NoSuchDomain()
            if 'pick-first' == strategy:
                return [response]
            if 'pick-later' == strategy:
                picked_responses = [response]
            elif 'pick-right' == strategy:
                if is_right_response(server_ip, response):
                    return [response]
                else:
                    if LOGGER.isEnabledFor(logging.DEBUG):
                        LOGGER.debug('drop wrong answer: %s' % repr(response))
            elif 'pick-right-later' == strategy:
                if is_right_response(server_ip, response):
                    picked_responses = [response]
                else:
                    if LOGGER.isEnabledFor(logging.DEBUG):
                        LOGGER.debug('drop wrong answer: %s' % repr(response))
            elif 'pick-all' == strategy:
                picked_responses.append(response)
            else:
                raise Exception('unsupported strategy: %s' % strategy)
            remaining_timeout = deadline - time.time()
        return picked_responses
    except socket.timeout:
        return picked_responses


class NoSuchDomain(Exception):
    pass


def is_right_response(server_ip, response):
    answers = list_ipv4_addresses(response)
    if not answers: # GFW can forge empty response
        return False
    if any(is_wrong_answer(answer) for answer in answers):
        return False
    if fqsocks.china_ip.is_china_ip(server_ip):
        if not all(fqsocks.china_ip.is_china_ip(answer) for answer in answers):
            return False # we do not trust china dns to resolve non-china ips
    return True


def list_ipv4_addresses(response):
    return [socket.inet_ntoa(answer.ip) for answer in response.an if dpkt.dns.DNS_A == answer.type]


def discover(domain, at, timeout, repeat, only_new):
    server_ip, server_port = parse_ip_colon_port(at)
    domains = domain or [
        'facebook.com', 'youtube.com', 'twitter.com', 'plus.google.com', 'drive.google.com']
    wrong_answers = set()
    greenlets = []
    for domain in domains:
        right_answers = resolve_over_tcp(dpkt.dns.DNS_A, domain, server_ip, server_port, timeout * 2)
        right_answer = right_answers[0] if right_answers else None
        for i in range(repeat):
            greenlets.append(gevent.spawn(
                discover_one, domain, server_ip, server_port, timeout, right_answer))
    for greenlet in greenlets:
        wrong_answers |= greenlet.get()
    if only_new:
        return list(wrong_answers - list_wrong_answers())
    else:
        return list(wrong_answers)


def discover_one(domain, server_ip, server_port, timeout, right_answer):
    wrong_answers = set()
    responses_answers = resolve_over_udp(
        dpkt.dns.DNS_A, domain, server_ip, server_port, timeout, 'pick-all')
    contains_right_answer = any(len(answers) > 1 for answers in responses_answers)
    if right_answer or contains_right_answer:
        for answers in responses_answers:
            if len(answers) == 1 and answers[0] != right_answer:
                wrong_answers |= set(answers)
    return wrong_answers


def create_tcp_socket(server_ip, server_port, connect_timeout):
    return SPI['create_tcp_socket'](server_ip, server_port, connect_timeout)

def _create_tcp_socket(server_ip, server_port, connect_timeout):
    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    if OUTBOUND_MARK:
        sock.setsockopt(socket.SOL_SOCKET, SO_MARK, OUTBOUND_MARK)
    if OUTBOUND_IP:
        sock.bind((OUTBOUND_IP, 0))
    sock.settimeout(connect_timeout)
    try:
        sock.connect((server_ip, server_port))
    except:
        sock.close()
        raise
    sock.settimeout(None)
    return sock

SPI['create_tcp_socket'] = _create_tcp_socket


def create_udp_socket():
    return SPI['create_udp_socket']()


def _create_udp_socket():
    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    if OUTBOUND_MARK:
        sock.setsockopt(socket.SOL_SOCKET, SO_MARK, OUTBOUND_MARK)
    if OUTBOUND_IP:
        sock.bind((OUTBOUND_IP, 0))
    return sock


SPI['create_udp_socket'] = _create_udp_socket


class SocketTimeout(BaseException):
    pass


WRONG_ANSWERS = {
    '4.36.66.178',
    '8.7.198.45',
    '23.89.5.60',
    '37.61.54.158',
    '46.82.174.68',
    '49.2.123.56',
    '54.76.135.1',
    '59.24.3.173',
    '64.33.88.161',
    '64.33.99.47',
    '64.66.163.251',
    '65.104.202.252',
    '65.160.219.113',
    '66.45.252.237',
    '72.14.205.99',
    '72.14.205.104',
    '77.4.7.92',
    '78.16.49.15',
    '93.46.8.89',
    '118.5.49.6',
    '128.121.126.139',
    '159.106.121.75',
    '159.24.3.173',
    '169.132.13.103',
    '188.5.4.96',
    '189.163.17.5',
    '192.67.198.6',
    '197.4.4.12',
    '202.106.1.2',
    '202.181.7.85',
    '203.161.230.171',
    '203.98.7.65',
    '207.12.88.98',
    '208.56.31.43',
    '209.36.73.33',
    '209.145.54.50',
    '209.220.30.174',
    '211.94.66.147',
    '213.169.251.35',
    '216.221.188.182',
    '216.234.179.13',
    '220.250.64.24',
    '243.185.187.39',
    '243.185.187.30',
    '253.157.14.165',
    '249.129.46.48',
    # plus.google.com
    '74.125.127.102',
    '74.125.155.102',
    '74.125.39.113',
    '74.125.39.102',
    '209.85.229.138',
    # opendns
    '67.215.65.132',
    # https://github.com/fqrouter/fqdns/issues/2
    '69.55.52.253',
    # www.googleapis.com.fqrouter.com WTF
    '198.105.254.11',
    # 2014.1.21
    '65.49.2.178'
}


def is_wrong_answer(answer):
    if answer.startswith('183.207.229.') or answer.startswith('183.207.232.'):
        return True
    return answer in WRONG_ANSWERS


def list_wrong_answers():
    return WRONG_ANSWERS

user_whitelist = '/sdcard/domain_whitelist.txt'
china_domains_txt = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'china_domains.txt')
if os.path.exists(china_domains_txt):
    with open(china_domains_txt) as f:
        CHINA_DOMAINS = set(f.read().splitlines(False))
    try:
        if os.path.exists(user_whitelist):
            with open(user_whitelist) as uf:
                CHINA_DOMAINS.update(uf.read().splitlines(False))
    except:
        LOGGER.exception('read user whitelist fail')
else:
    print('%s not found' % china_domains_txt)
    CHINA_DOMAINS = set()

def is_china_domain(domain):
    if domain.endswith('.cn'):
        return True
    parts = domain.split('.')
    if '.'.join(parts[-2:]) in CHINA_DOMAINS:
        return True
    if '.'.join(parts[-3:]) in CHINA_DOMAINS:
        return True
    return False

def is_hosted_domain(domain):
    return not is_china_domain(domain)

BLOCKED_DOMAINS = {
    'fqrouter.com',
    'f-q.co',
    'f-q.me',
    'blogspot.com',
    'xvideos.com',
    'blogger.com',
    'netflix.com',
    'dailymotion.com',
    'youporn.com',
    'nytimes.com',
    'wsj.com',
    'pixnet.net',
    'vimeo.com',
    'soundcloud.com',
    'slideshare.net',
    'wordpress.com',
    'pornhub.com',
    'xhamster.com',
    'redtube.com',
    'flickr.com',
    'foursquare.com',
    'dropbox.com',

    'google.com.hk',
    'google.cn',
    'google.com',
    'gmail.com',
    'googleusercontent.com',
    'gstatic.com',
    'appspot.com',
    'ggpht.com',
    'blogger.com',
    'blogspot.com',
    'googleapis.com',
    'gvt1.com',
    'gvt2.com',
    'android.com',
    'googlecode.com',
    'youtube.com',
    'googlevideo.com',
    'ytimg.com',
    'facebook.com',
    'instagram.com',
    'fbcdn.net',
    't.co',
    'twitter.com',
    'twimg.com',
}

def is_blocked_domain(domain):
    parts = domain.split('.')
    if '.'.join(parts[-2:]) in BLOCKED_DOMAINS:
        return True
    if '.'.join(parts[-3:]) in BLOCKED_DOMAINS:
        return True
    return False

# TODO use original dns for PTR query, http://stackoverflow.com/questions/5615579/how-to-get-original-destination-port-of-redirected-udp-message
# TODO cache
# TODO PTR support, check cache then check remote
# TODO IPV6
# TODO complete record types
# TODO --recursive

if '__main__' == __name__:
    main()
