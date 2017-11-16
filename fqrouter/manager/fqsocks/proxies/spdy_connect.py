import logging
import base64

import gevent
import spdy.context
import spdy.frames

from .direct import Proxy
from .spdy_client import SpdyClient
from .spdy_client import SPDY_3


LOGGER = logging.getLogger(__name__)


class SpdyConnectProxy(Proxy):
    def __init__(self, proxy_host, proxy_port, requested_spdy_version='auto',
                 username=None, password=None, priority=0, **ignore):
        super(SpdyConnectProxy, self).__init__()
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
            LOGGER.exception('failed to connect spdy-connect proxy: %s' % self)
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
                    LOGGER.exception('failed to connect spdy connect: %s' % self)
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
            LOGGER.exception('spdy connect loop failed')
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
        if SPDY_3 == self.spdy_client.spdy_version:
            headers = {
                ':method': 'CONNECT',
                ':scheme': 'https',
                ':path': '%s:%s' % (client.dst_ip, client.dst_port),
                ':version': 'HTTP/1.1',
                ':host': '%s:%s' % (client.dst_ip, client.dst_port)
            }
        else:
            headers = {
                'method': 'CONNECT',
                'scheme': 'https',
                'url': '%s:%s' % (client.dst_ip, client.dst_port),
                'version': 'HTTP/1.1',
                'host': '%s:%s' % (client.dst_ip, client.dst_port)
            }
        if self.username and self.password:
            auth = base64.b64encode('%s:%s' % (self.username, self.password)).strip()
            headers['proxy-authorization'] = 'Basic %s' % auth
        client.payload = client.peeked_data
        stream_id = self.spdy_client.open_stream(headers, client)
        self.spdy_client.poll_stream(stream_id, self.on_frame)

    def on_frame(self, stream, frame):
        if isinstance(frame, spdy.frames.SynReply):
            self.on_syn_reply_frame(stream, frame)
            return
        else:
            LOGGER.warn('!!! [%s] unknown frame: %s %s !!!'
                        % (repr(stream.client), frame, getattr(frame, 'frame_type')))

    def on_syn_reply_frame(self, stream, frame):
        client = stream.client
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('[%s] syn reply: %s' % (repr(client), frame.headers))
        headers = dict(frame.headers)
        if SPDY_3 == self.spdy_client.spdy_version:
            status = headers.pop(':status')
        else:
            status = headers.pop('status')
        if status.startswith('200'):
            client.forward_started = True
        else:
            LOGGER.error('[%s] proxy rejected CONNECT: %s' % (repr(client), status))
            self.died = True
            self.loop_greenlet.kill()


    @classmethod
    def refresh(cls, proxies):
        for proxy in proxies:
            proxy.connect()
        return True

    def is_protocol_supported(self, protocol, client=None):
        return protocol == 'HTTPS'

    def __repr__(self):
        return 'SpdyConnectProxy[%s:%s]' % (self.proxy_host, self.proxy_port)

    @property
    def public_name(self):
        return 'SPDY\t%s' % self.proxy_host

