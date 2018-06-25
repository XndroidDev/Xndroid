import logging
import httplib
import socket
import sys
import StringIO
import gzip
import fnmatch
import time
import gevent
import ssl

from .direct import Proxy
from .. import networking
from .. import stat
from .. import ip_substitution

LOGGER = logging.getLogger(__name__)

NO_DIRECT_PROXY_HOSTS = {
    'hulu.com',
    '*.hulu.com',
    'huluim.com',
    '*.huluim.com',
    'netflix.com',
    '*.netflix.com',
    'skype.com',
    '*.skype.com',
    'radiotime.com',
    '*.radiotime.com'
    'myfreecams.com',
    '*.myfreecams.com'
    'pandora.com',
    '*.pandora.com'
}

WHITE_LIST = {
    'www.google.com',
    'google.com',
    'www.google.com.hk',
    'google.com.hk',
}


def is_no_direct_host(client_host):
    return any(fnmatch.fnmatch(client_host, host) for host in NO_DIRECT_PROXY_HOSTS)

REASON_HTTP_TRY_CONNECT_FAILED = 'http try connect failed'

class HttpTryProxy(Proxy):

    INITIAL_TIMEOUT = 1
    timeout = INITIAL_TIMEOUT
    slow_ip_list = set()
    host_black_list = {} # host => count
    host_slow_list = {}
    host_slow_detection_enabled = True
    connection_pool = {}

    def __init__(self):
        super(HttpTryProxy, self).__init__()
        self.flags.add('DIRECT')
        self.dst_black_list = {} # (ip, port) => count

    def do_forward(self, client):
        dst = (client.dst_ip, client.dst_port)
        try:
            self.try_direct(client)
            if dst in self.dst_black_list:
                LOGGER.error('%s remove dst %s:%s from blacklist' % (repr(self), dst[0], dst[1]))
                del self.dst_black_list[dst]
            if client.host in HttpTryProxy.host_black_list:
                if HttpTryProxy.host_black_list.get(client.host, 0) > 3:
                    LOGGER.error('HttpTryProxies remove host %s from blacklist' % client.host)
                del HttpTryProxy.host_black_list[client.host]
            if client.host in HTTP_TRY_PROXY.host_slow_list:
                if HttpTryProxy.host_slow_list.get(client.host, 0) > 3:
                    LOGGER.error('HttpTryProxies remove host %s from slowlist' % client.host)
                del HttpTryProxy.host_slow_list[client.host]
        except NotHttp:
            raise
        except client.ProxyFallBack as e:
            if REASON_HTTP_TRY_CONNECT_FAILED == e.reason:
                if dst not in self.dst_black_list:
                    LOGGER.error('%s blacklist dst %s:%s' % (repr(self), dst[0], dst[1]))
                self.dst_black_list[dst] = self.dst_black_list.get(dst, 0) + 1
            if client.host and client.host not in WHITE_LIST:
                HttpTryProxy.host_black_list[client.host] = HttpTryProxy.host_black_list.get(client.host, 0) + 1
                if HttpTryProxy.host_black_list[client.host] == 4:
                    LOGGER.error('HttpTryProxies blacklist host %s' % client.host)
            raise

    def try_direct(self, client, is_retrying=0):
        try:
            try:
                upstream_sock = self.get_or_create_upstream_sock(client)
            except gevent.Timeout:
                client.http_try_connect_timed_out = True
                raise
        except:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] http try connect failed' % (repr(client)), exc_info=1)
            client.fall_back(reason=REASON_HTTP_TRY_CONNECT_FAILED)
            return
        client.headers['Host'] = client.host
        request_data = self.before_send_request(client, upstream_sock, client.is_payload_complete)
        request_data += '%s %s HTTP/1.1\r\n' % (client.method, client.path)
        request_data += ''.join('%s: %s\r\n' % (k, v) for k, v in client.headers.items())
        request_data += '\r\n'
        try:
            upstream_sock.sendall(request_data + client.payload)
        except:
            client.fall_back(reason='send to upstream failed: %s' % sys.exc_info()[1])
        self.after_send_request(client, upstream_sock)
        if client.is_payload_complete:
            try:
                http_response = try_receive_response_header(
                    client, upstream_sock, rejects_error=('GET' == client.method))
            except httplib.BadStatusLine:
                if is_retrying > 3:
                    client.fall_back(reason='failed to read response: %s' % upstream_sock.history)
                LOGGER.info('[%s] retry with another connection' % repr(client))
                return self.try_direct(client, is_retrying=is_retrying + 1)
            response = self.detect_slow_host(client, http_response)
            # is_keep_alive = 'Connection: keep-alive' in response
            is_keep_alive = False # disable keep-alive as it is not stable
            try:
                fallback_if_youtube_unplayable(client, http_response)
                response = self.process_response(client, upstream_sock, response, http_response)
            except client.ProxyFallBack:
                raise
            except:
                LOGGER.exception('process response failed')
            client.forward_started = True
            client.downstream_sock.sendall(response)
            if is_keep_alive:
                self.forward_upstream_sock(client, http_response, upstream_sock)
            else:
                client.forward(upstream_sock)
        else:
            if client.method and 'GET' != client.method.upper():
                client.forward(upstream_sock, timeout=360)
            else:
                client.forward(upstream_sock)

    def detect_slow_host(self, client, http_response):
        if HttpTryProxy.host_slow_detection_enabled:
            greenlet = gevent.spawn(
                try_receive_response_body, http_response, reads_all='youtube.com/watch?' in client.url)
            try:
                return greenlet.get(timeout=5)
            except gevent.Timeout:
                slow_times = HttpTryProxy.host_slow_list.get(client.host, 0) + 1
                HttpTryProxy.host_slow_list[client.host] = slow_times
                LOGGER.error('[%s] host %s is too slow to direct access %s/3' % (repr(client), client.host, slow_times))
                client.fall_back('too slow')
            finally:
                greenlet.kill()
        else:
            return try_receive_response_body(http_response)

    def get_or_create_upstream_sock(self, client):
        return self.create_upstream_sock(client) # disable prefetch
        # if HttpTryProxy.connection_pool.get(client.dst_ip):
        #     upstream_sock = HttpTryProxy.connection_pool[client.dst_ip].pop()
        #     if not HttpTryProxy.connection_pool[client.dst_ip]:
        #         del HttpTryProxy.connection_pool[client.dst_ip]
        #     if upstream_sock.last_used_at - time.time() > 7:
        #         LOGGER.debug('[%s] close old connection %s' % (repr(client), upstream_sock.history))
        #         upstream_sock.close()
        #         return self.get_or_create_upstream_sock(client)
        #     client.add_resource(upstream_sock)
        #     if len(upstream_sock.history) > 5:
        #         return self.get_or_create_upstream_sock(client)
        #     LOGGER.debug('[%s] reuse connection %s' % (repr(client), upstream_sock.history))
        #     upstream_sock.history.append(client.src_port)
        #     upstream_sock.last_used_at = time.time()
        #     return upstream_sock
        # else:
        #     LOGGER.debug('[%s] open new connection' % repr(client))
        #     pool_size = len(HttpTryProxy.connection_pool.get(client.dst_ip, []))
        #     if pool_size <= 2:
        #         gevent.spawn(self.prefetch_to_connection_pool, client)
        #     return self.create_upstream_sock(client)

    def create_upstream_sock(self, client):
        success, upstream_sock = gevent.spawn(try_connect, client).get(timeout=HttpTryProxy.timeout)
        if not success:
            raise upstream_sock
        upstream_sock.last_used_at = time.time()
        upstream_sock.history = [client.src_port]
        return upstream_sock

    def prefetch_to_connection_pool(self, client):
        try:
            upstream_sock = self.create_upstream_sock(client)
            client.resources.remove(upstream_sock)
            HttpTryProxy.connection_pool.setdefault(client.dst_ip, []).append(upstream_sock)
            LOGGER.debug('[%s] prefetch success' % repr(client))
        except:
            LOGGER.debug('[%s] prefetch failed' % repr(client), exc_info=1)

    def forward_upstream_sock(self, client, http_response, upstream_sock):
        real_fp = http_response.capturing_sock.rfile.fp
        http_response.fp = ForwardingFile(real_fp, client.downstream_sock)
        while not http_response.isclosed() and (http_response.length > 0 or http_response.length is None):
            try:
                http_response.read(amt=8192)
            except:
                break
        if upstream_sock in client.resources:
            client.resources.remove(upstream_sock)
        HttpTryProxy.connection_pool.setdefault(client.dst_ip, []).append(upstream_sock)


    def before_send_request(self, client, upstream_sock, is_payload_complete):
        return ''

    def after_send_request(self, client, upstream_sock):
        pass

    def process_response(self, client, upstream_sock, response, http_response):
        return response

    def is_protocol_supported(self, protocol, client=None):
        if self.died:
            return False
        if client and self in client.tried_proxies:
            return False
        dst = (client.dst_ip, client.dst_port)
        if self.dst_black_list.get(dst, 0) % 16:
            if ip_substitution.substitute_ip(client, self.dst_black_list):
                return True
            self.dst_black_list[dst] = self.dst_black_list.get(dst, 0) + 1
            return False
        if is_no_direct_host(client.host):
            return False
        host_slow_times = HttpTryProxy.host_slow_list.get(client.host, 0)
        if host_slow_times > 3 and host_slow_times % 16:
            HttpTryProxy.host_slow_list[client.host] = host_slow_times + 1
            return False
        host_failed_times = HttpTryProxy.host_black_list.get(client.host, 0)
        if host_failed_times > 3 and host_failed_times % 16:
            HttpTryProxy.host_black_list[client.host] = host_failed_times + 1
            return False
        return 'HTTP' == protocol

    def __repr__(self):
        return 'HttpTryProxy'


class TcpScrambler(HttpTryProxy):
    def __init__(self):
        super(TcpScrambler, self).__init__()
        self.bad_requests = {} # host => count
        self.died = True
        self.is_trying = False

    def try_start_if_network_is_ok(self):
        if self.is_trying:
            return
        self.died = True
        self.is_trying = True
        gevent.spawn(self._try_start)

    def _try_start(self):
        try:
            LOGGER.info('will try start tcp scrambler in 30 seconds')
            gevent.sleep(5)
            LOGGER.info('try tcp scrambler')
            if not detect_if_ttl_being_ignored():
                self.died = False
        finally:
            self.is_trying = False

    def create_upstream_sock(self, client):
        upstream_sock = create_scrambled_sock(client.dst_ip, client.dst_port)
        upstream_sock.history = [client.src_port]
        upstream_sock.counter = stat.opened(upstream_sock, client.forwarding_by, client.host, client.dst_ip)
        client.add_resource(upstream_sock)
        client.add_resource(upstream_sock.counter)
        return upstream_sock

    def before_send_request(self, client, upstream_sock, is_payload_complete):
        if 'Referer' in client.headers:
            del client.headers['Referer']
        upstream_sock.setsockopt(socket.SOL_SOCKET, networking.SO_MARK, 0xbabe)
        return ''

    def after_send_request(self, client, upstream_sock):
        pass

    def process_response(self, client, upstream_sock, response, http_response):
        upstream_sock.setsockopt(socket.SOL_SOCKET, networking.SO_MARK, 0)
        if httplib.BAD_REQUEST == http_response.status:
            LOGGER.info('[%s] bad request to %s' % (repr(client), client.host))
            self.bad_requests[client.host] = self.bad_requests.get(client.host, 0) + 1
            if self.bad_requests[client.host] >= 3:
                LOGGER.critical('!!! too many bad requests, disable tcp scrambler !!!')
                self.died = True
            client.fall_back('tcp scrambler bad request')
        else:
            if client.host in self.bad_requests:
                LOGGER.info('[%s] reset bad request to %s' % (repr(client), client.host))
                del self.bad_requests[client.host]
            response = response.replace('Connection: keep-alive', 'Connection: close')
        return response

    def __repr__(self):
        return 'TcpScrambler'

def create_scrambled_sock(ip, port):
    upstream_sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    if networking.OUTBOUND_IP:
        upstream_sock.bind((networking.OUTBOUND_IP, 0))
    upstream_sock.setsockopt(socket.SOL_SOCKET, networking.SO_MARK, 0xbabe)
    upstream_sock.settimeout(3)
    try:
        upstream_sock.connect((ip, port))
    except:
        upstream_sock.close()
        raise
    upstream_sock.last_used_at = time.time()
    upstream_sock.settimeout(None)
    return upstream_sock

HTTP_TRY_PROXY = HttpTryProxy()
TCP_SCRAMBLER = TcpScrambler()



def detect_if_ttl_being_ignored():
    gevent.sleep(5)
    for i in range(2):
        try:
            LOGGER.info('detecting if ttl being ignored')
            baidu_ip = networking.resolve_ips('www.baidu.com')[0]
            sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
            if networking.OUTBOUND_IP:
                sock.bind((networking.OUTBOUND_IP, 0))
            sock.setblocking(0)
            sock.settimeout(2)
            sock.setsockopt(socket.SOL_IP, socket.IP_TTL, 3)
            try:
                sock.connect((baidu_ip, 80))
            finally:
                sock.close()
            LOGGER.info('ttl 3 should not connect baidu, disable fqting')
            return True
        except:
            LOGGER.exception('detected if ttl being ignored')
            gevent.sleep(1)
    return False



def try_connect(client):
    try:
        begin_time = time.time()
        upstream_sock = client.create_tcp_socket(
            client.dst_ip, client.dst_port,
            connect_timeout=max(5, HttpTryProxy.timeout * 2))
        elapsed_seconds = time.time() - begin_time
        if elapsed_seconds > HttpTryProxy.timeout:
            HttpTryProxy.slow_ip_list.add(client.dst_ip)
            HttpTryProxy.host_black_list.clear()
            if len(HttpTryProxy.slow_ip_list) > 3:
                LOGGER.critical('!!! increase http timeout %s=>%s' % (HttpTryProxy.timeout, HttpTryProxy.timeout + 1))
                HttpTryProxy.timeout += 1
                HttpTryProxy.slow_ip_list.clear()
        return True, upstream_sock
    except:
        return False, sys.exc_info()[1]

def fallback_if_youtube_unplayable(client, http_response):
    if not http_response:
        return
    if 'youtube.com/watch?' not in client.url:
        return
    if http_response.body and 'gzip' == http_response.msg.dict.get('content-encoding'):
        stream = StringIO.StringIO(http_response.body)
        gzipper = gzip.GzipFile(fileobj=stream)
        http_response.body = gzipper.read()
    if http_response.body and (
                'id="unavailable-message" class="message"' in http_response.body or 'UNPLAYABLE' in http_response.body):
        client.fall_back(reason='youtube player not available in China')



def try_receive_response_header(client, upstream_sock, rejects_error=False):
    try:
        upstream_rfile = upstream_sock.makefile('rb', 0)
        client.add_resource(upstream_rfile)
        capturing_sock = CapturingSock(upstream_rfile)
        http_response = httplib.HTTPResponse(capturing_sock)
        http_response.capturing_sock = capturing_sock
        http_response.body = None
        http_response.begin()
        content_length = http_response.msg.dict.get('content-length')
        if content_length:
            http_response.content_length = int(content_length)
        else:
            http_response.content_length = 0
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('[%s] http try read response header: %s %s' %
                         (repr(client), http_response.status, http_response.content_length))
        if http_response.chunked:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] skip try reading response due to chunked' % repr(client))
            return http_response
        if content_length == None:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] skip try reading response due to no content length' % repr(client))
            return http_response
        if rejects_error and http_response.status == 400:
            raise Exception('http try read response status is 400')
        return http_response
    except NotHttp:
        raise
    except httplib.BadStatusLine:
        raise
    except:
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('[%s] http try read response failed' % (repr(client)), exc_info=1)
        client.fall_back(reason='http try read response failed: %s' % sys.exc_info()[1])

def try_receive_response_body(http_response, reads_all=False):
    content_type = http_response.msg.dict.get('content-type')
    if content_type and 'text' in content_type:
        reads_all = True
    if reads_all:
        http_response.body = http_response.read(min(http_response.content_length, 2 * 1024 * 1024))
    else:
        http_response.body = http_response.read(min(http_response.content_length, 64 * 1024))
    return http_response.capturing_sock.rfile.captured

class CapturingSock(object):
    def __init__(self, rfile):
        self.rfile = CapturingFile(rfile)

    def makefile(self, mode='r', buffersize=-1):
        if 'rb' != mode:
            raise NotImplementedError()
        return self.rfile


class CapturingFile(object):
    def __init__(self, fp):
        self.fp = fp
        self.captured = ''

    def read(self, *args, **kwargs):
        chunk = self.fp.read(*args, **kwargs)
        self.captured += chunk
        return chunk

    def readline(self, *args, **kwargs):
        chunk = self.fp.readline(*args, **kwargs)
        self.captured += chunk
        return chunk

    def readlines(self,  *args, **kwargs):
        raise NotImplementedError()

    def close(self):
        self.fp.close()


class ForwardingFile(object):
    def __init__(self, fp, downstream_sock):
        self.fp = fp
        self.downstream_sock = downstream_sock

    def read(self, *args, **kwargs):
        chunk = self.fp.read(*args, **kwargs)
        self.downstream_sock.sendall(chunk)
        return chunk

    def readline(self, *args, **kwargs):
        chunk = self.fp.readline(*args, **kwargs)
        self.downstream_sock.sendall(chunk)
        return chunk

    def readlines(self, *args, **kwargs):
        raise NotImplementedError()

    def close(self):
        self.fp.close()

def recv_and_parse_request(client):
    client.peeked_data, client.payload = recv_till_double_newline(client.peeked_data, client.downstream_sock)
    if 'Host:' not in client.peeked_data:
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('[%s] not http' % (repr(client)))
        raise NotHttp()
    try:
        client.method, client.path, client.headers = parse_request(client.peeked_data)
        client.host = client.headers.pop('Host', '')
        if not client.host:
            raise Exception('missing host')
        if client.path[0] == '/':
            client.url = 'http://%s%s' % (client.host, client.path)
        else:
            client.url = client.path
        if 'youtube.com/watch' in client.url:
            LOGGER.info('[%s] %s' % (repr(client), client.url))
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('[%s] parsed http header: %s %s' % (repr(client), client.method, client.url))
        if 'Content-Length' in client.headers:
            more_payload_len = int(client.headers.get('Content-Length', 0)) - len(client.payload)
            if more_payload_len > 1024 * 1024:
                client.peeked_data += client.payload
                LOGGER.info('[%s] skip try reading request payload due to too large: %s' %
                            (repr(client), more_payload_len))
                return False
            if more_payload_len > 0:
                client.payload += client.downstream_rfile.read(more_payload_len)
        if client.payload:
            client.peeked_data += client.payload
        return True
    except:
        LOGGER.error('[%s] failed to parse http request:\n%s' % (repr(client), client.peeked_data))
        raise


def recv_till_double_newline(peeked_data, sock):
    for i in range(16):
        if peeked_data.find(b'\r\n\r\n') != -1:
            header, crlf, payload = peeked_data.partition(b'\r\n\r\n')
            return header + crlf, payload
        more_data = sock.recv(8192)
        if not more_data:
            return peeked_data, ''
        peeked_data += more_data
    raise Exception('http end not found')


class NotHttp(Exception):
    pass


def parse_request(request):
    lines = request.splitlines()
    method, path = lines[0].split()[:2]
    headers = dict()
    for line in lines[1:]:
        keyword, _, value = line.partition(b':')
        keyword = keyword.title()
        value = value.strip()
        if keyword and value:
            headers[keyword] = value
    return method, path, headers
