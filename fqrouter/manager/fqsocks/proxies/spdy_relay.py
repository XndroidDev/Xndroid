import logging
import sys
import base64

import gevent
import spdy.context
import spdy.frames

from .http_try import recv_and_parse_request
from .direct import Proxy
from .spdy_client import SpdyClient
from .spdy_client import SPDY_3


LOGGER = logging.getLogger(__name__)


class SpdyRelayProxy(Proxy):
    def __init__(self, proxy_host, proxy_port, requested_spdy_version='auto',
                 username=None, password=None, priority=0, **ignore):
        super(SpdyRelayProxy, self).__init__()
        self.proxy_host = proxy_host
        self.proxy_port = int(proxy_port)
        self.username = username
        self.password = password
        self.spdy_client = None
        self.requested_spdy_version = requested_spdy_version
        self.died = True
        self.loop_greenlet = None
        self.priority = int(priority)

    def connect(self):
        try:
            try:
                if self.loop_greenlet:
                    self.loop_greenlet.kill()
            except:
                pass
            self.loop_greenlet = gevent.spawn(self.loop)
        except:
            LOGGER.exception('failed to connect spdy-relay proxy: %s' % self)
            self.died = True

    def loop(self):
        try:
            while True:
                self.close()
                if '0.0.0.0' == self.proxy_ip:
                    return
                try:
                    self.spdy_client = SpdyClient(self.proxy_ip, self.proxy_port, self.requested_spdy_version)
                except:
                    LOGGER.exception('failed to connect spdy relay: %s' % self)
                    gevent.sleep(10)
                    self.spdy_client = SpdyClient(self.proxy_ip, self.proxy_port, self.requested_spdy_version)
                self.died = False
                try:
                    self.spdy_client.loop()
                except:
                    LOGGER.exception('spdy client loop failed')
                finally:
                    LOGGER.info('spdy client loop quit')
                self.died = True
        except:
            LOGGER.exception('spdy relay loop failed')
            self.died = True

    def close(self):
        if self.spdy_client:
            self.spdy_client.close()
            self.spdy_client = None
        self.died = True

    def do_forward(self, client):
        if not self.spdy_client:
            self.died = True
            client.fall_back(reason='not connected yet')
        recv_and_parse_request(client)
        if SPDY_3 == self.spdy_client.spdy_version:
            headers = {
                ':method': client.method,
                ':scheme': 'http',
                ':path': client.url,
                ':version': 'HTTP/1.1',
                ':host': client.host
            }
        else:
            headers = {
                'method': client.method,
                'scheme': 'http',
                'url': client.url,
                'version': 'HTTP/1.1',
                'host': client.host
            }
        if self.username and self.password:
            auth = base64.b64encode('%s:%s' % (self.username, self.password)).strip()
            headers['proxy-authorization'] = 'Basic %s' % auth
        for k, v in client.headers.items():
            headers[k.lower()] = v
        headers['connection'] = 'close'
        stream_id = self.spdy_client.open_stream(headers, client)
        stream = self.spdy_client.streams[stream_id]
        stream.request_content_length = int(headers.get('content-length', 0))
        self.spdy_client.poll_stream(stream_id, self.on_frame)

    def on_frame(self, stream, frame):
        if isinstance(frame, spdy.frames.SynReply):
            stream.response_content_length = self.on_syn_reply_frame(stream, frame)
        else:
            LOGGER.warn('!!! [%s] unknown frame: %s %s !!!'
                        % (repr(stream.client), frame, getattr(frame, 'frame_type')))

    def on_syn_reply_frame(self, stream, frame):
        client = stream.client
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('[%s] syn reply: %s' % (repr(client), frame.headers))
        headers = dict(frame.headers)
        if SPDY_3 == self.spdy_client.spdy_version:
            http_version = headers.pop(':version')
            status = headers.pop(':status')
        else:
            http_version = headers.pop('version')
            status = headers.pop('status')
        client.forward_started = True
        client.downstream_sock.sendall('%s %s\r\n' % (http_version, status))
        for k, v in headers.items():
            client.downstream_sock.sendall('%s: %s\r\n' % (k, v))
        client.downstream_sock.sendall('\r\n')
        if status.startswith('304'):
            return 0
        else:
            return int(headers.pop('content-length', sys.maxint))


    @classmethod
    def refresh(cls, proxies):
        for proxy in proxies:
            proxy.connect()
        return True

    def is_protocol_supported(self, protocol, client=None):
        return protocol == 'HTTP'

    def __repr__(self):
        return 'SpdyRelayProxy[%s:%s]' % (self.proxy_host, self.proxy_port)

    @property
    def public_name(self):
        return 'SPDY\t%s' % self.proxy_host

