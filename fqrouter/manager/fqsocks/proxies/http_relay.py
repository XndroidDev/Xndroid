import logging
import base64
import sys
import time

import ssl

from .direct import Proxy
from .direct import to_bool
from .http_try import try_receive_response_header
from .http_try import try_receive_response_body
from .http_try import recv_and_parse_request
from .. import config_file

LOGGER = logging.getLogger(__name__)


class HttpRelayProxy(Proxy):
    def __init__(self, proxy_host, proxy_port, username=None, password=None, is_secured=False, priority=0, **ignore):
        super(HttpRelayProxy, self).__init__()
        self.proxy_host = proxy_host
        if not self.proxy_host:
            self.died = True
        self.proxy_port = int(proxy_port)
        self.username = username
        self.password = password
        self.failed_times = 0
        self.is_secured = to_bool(is_secured)
        self.priority = int(priority)

    def do_forward(self, client):
        LOGGER.info('[%s] http relay %s:%s' % (repr(client), self.proxy_ip, self.proxy_port))
        begin_at = time.time()
        try:
            if config_file.multi_proxy:
                upstream_sock = client.create_tcp_socket(self.proxy_ip, self.proxy_port, 5)
            else:
                upstream_sock = client.create_tcp_socket(self.proxy_ip, self.proxy_port, 30)
            if self.is_secured:
                counter = upstream_sock.counter
                upstream_sock = ssl.wrap_socket(upstream_sock)
                upstream_sock.counter = counter
                client.add_resource(upstream_sock)
        except:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] http-relay upstream socket connect timed out' % (repr(client)), exc_info=1)
            return client.fall_back(
                reason='http-relay upstream socket connect timed out',
                delayed_penalty=self.increase_failed_time)
        if config_file.multi_proxy:
            upstream_sock.settimeout(5)
        else:
            upstream_sock.settimeout(36)
        is_payload_complete = recv_and_parse_request(client)
        request_data = '%s %s HTTP/1.1\r\n' % (client.method, client.url)
        client.headers['Connection'] = 'close' # no keep-alive
        request_data += ''.join('%s: %s\r\n' % (k, v) for k, v in client.headers.items())
        if self.username and self.password:
            auth = base64.b64encode('%s:%s' % (self.username, self.password)).strip()
            request_data += 'Proxy-Authorization: Basic %s\r\n' % auth
        request_data += '\r\n'
        try:
            request_data = request_data + client.payload
            upstream_sock.counter.sending(len(request_data))
            upstream_sock.sendall(request_data)
        except:
            client.fall_back(
                reason='send to upstream failed: %s' % sys.exc_info()[1],
                delayed_penalty=self.increase_failed_time)
        if is_payload_complete:
            try:
                response = try_receive_response_body(try_receive_response_header(client, upstream_sock))
            except:
                return client.fall_back(reason='bad response', delayed_penalty=self.increase_failed_time)
            upstream_sock.counter.received(len(response))
            client.forward_started = True
            client.downstream_sock.sendall(response)
        self.record_latency(time.time() - begin_at)
        client.forward(upstream_sock)
        self.failed_times = 0

    def is_protocol_supported(self, protocol, client=None):
        return protocol == 'HTTP'

    def __repr__(self):
        return 'HttpRelayProxy[%s:%s %0.2f]' % (self.proxy_host, self.proxy_port, self.latency)

    @property
    def public_name(self):
        return 'HTTP\t%s:%d' % (self.proxy_host, self.proxy_port)

