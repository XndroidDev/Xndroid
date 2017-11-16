import select
import tlslite

import gevent
import gevent.queue
import gevent.event
import spdy.context
import spdy.frames
import sys
import logging
import socket
from .. import networking
from .. import stat


LOGGER = logging.getLogger(__name__)

LOCAL_INITIAL_WINDOW_SIZE = 65536
WORKING = 'working'
SPDY_3 = 3
SPDY_2 = 2


class SpdyClient(object):
    def __init__(self, ip, port, requested_spdy_version):
        self.sock = networking.create_tcp_socket(ip, port, 3)
        self.tls_conn = tlslite.TLSConnection(self.sock)
        if 'auto' == requested_spdy_version:
            nextProtos=['spdy/3', 'spdy/2']
        elif 'spdy/2' == requested_spdy_version:
            nextProtos=['spdy/2']
        elif 'spdy/3' == requested_spdy_version:
            nextProtos=['spdy/3']
        else:
            raise Exception('unknown requested spdy version: %s' % requested_spdy_version)
        self.tls_conn.handshakeClientCert(nextProtos=nextProtos)
        LOGGER.info('negotiated protocol: %s' % self.tls_conn.next_proto)
        if 'spdy/2' == self.tls_conn.next_proto:
            self.spdy_version = SPDY_2
        elif 'spdy/3' == self.tls_conn.next_proto:
            self.spdy_version = SPDY_3
        else:
            raise Exception('not spdy')
        self.spdy_context = spdy.context.Context(spdy.context.CLIENT, version=self.spdy_version)
        self.remote_initial_window_size = 65536
        self.streams = {}
        self.send(spdy.frames.Settings(1, {spdy.frames.INITIAL_WINDOW_SIZE: (0, LOCAL_INITIAL_WINDOW_SIZE)}))

    def open_stream(self, headers, client):
        stream_id = self.spdy_context.next_stream_id
        stream = SpdyStream(
            stream_id, client,
            upstream_window_size=self.remote_initial_window_size,
            downstream_window_size=LOCAL_INITIAL_WINDOW_SIZE,
            send_cb=self.send,
            spdy_version=self.spdy_version)
        self.streams[stream_id] = stream
        self.send(spdy.frames.SynStream(stream_id, headers, version=self.spdy_version, flags=0))
        if client.payload:
            stream.counter.sending(len(client.payload))
            self.send(spdy.frames.DataFrame(stream_id, client.payload, flags=0))
        gevent.spawn(stream.poll_from_downstream)
        return stream_id

    def end_stream(self, stream_id):
        self.send(spdy.frames.RstStream(stream_id, error_code=spdy.frames.CANCEL, version=self.spdy_version))
        if stream_id in self.streams:
            self.streams[stream_id].close()
            del self.streams[stream_id]

    def poll_stream(self, stream_id, on_frame_cb):
        stream = self.streams[stream_id]
        try:
            while not stream.done:
                try:
                    frame = stream.upstream_frames.get(timeout=10)
                except gevent.queue.Empty:
                    if stream.client.forward_started:
                        return
                    else:
                        return stream.client.fall_back('no response from proxy')
                if WORKING == frame:
                    continue
                elif isinstance(frame, spdy.frames.RstStream):
                    LOGGER.info('[%s] rst: %s' % (repr(stream.client), frame))
                    return
                else:
                    on_frame_cb(stream, frame)
        finally:
            self.end_stream(stream_id)

    def loop(self):
        while True:
            data = self.tls_conn.read()
            if not data:
                return
            self.spdy_context.incoming(data)
            self.consume_frames()


    def consume_frames(self):
        while True:
            frame = self.spdy_context.get_frame()
            if not frame:
                return
            try:
                if isinstance(frame, spdy.frames.Settings):
                    all_settings = dict(frame.id_value_pairs)
                    LOGGER.info('received spdy settings: %s' % all_settings)
                    initial_window_size_settings = all_settings.get(spdy.frames.INITIAL_WINDOW_SIZE)
                    if initial_window_size_settings:
                        self.remote_initial_window_size = initial_window_size_settings[1]
                elif isinstance(frame, spdy.frames.DataFrame):
                    if frame.stream_id in self.streams:
                        stream = self.streams[frame.stream_id]
                        stream.send_to_downstream(frame.data)
                elif isinstance(frame, spdy.frames.WindowUpdate):
                    if frame.stream_id in self.streams:
                        stream = self.streams[frame.stream_id]
                        stream.update_upstream_window(frame.delta_window_size)
                elif hasattr(frame, 'stream_id'):
                    if frame.stream_id in self.streams:
                        stream = self.streams[frame.stream_id]
                        stream.upstream_frames.put(frame)
                else:
                    LOGGER.warn('!!! unknown frame: %s %s !!!' % (frame, getattr(frame, 'frame_type')))
            except:
                LOGGER.exception('failed to handle frame: %s' % frame)

    def send(self, frame):
        self.spdy_context.put_frame(frame)
        data = self.spdy_context.outgoing()
        self.tls_conn.write(data)


    def close(self):
        try:
            self.tls_conn.close()
            self.tls_conn = None
        except:
            pass
        try:
            self.sock.close()
            self.sock = None
        except:
            pass


class SpdyStream(object):
    def __init__(self, stream_id, client, upstream_window_size, downstream_window_size, send_cb, spdy_version):
        self.stream_id = stream_id
        self.upstream_frames = gevent.queue.Queue()
        self.client = client
        self.upstream_window_size = upstream_window_size
        self.downstream_window_size = downstream_window_size
        self.remote_ready = gevent.event.Event()
        self.send_cb = send_cb
        self.sent_bytes = len(client.payload)
        self.received_bytes = 0
        self.request_content_length = sys.maxint
        self.response_content_length = sys.maxint
        self.spdy_version = spdy_version
        self._done = False
        self.counter = stat.opened(self, client.forwarding_by, client.host, client.dst_ip)

    def send_to_downstream(self, data):
        try:
            if not self.client.forward_started:
                gevent.sleep(0)
            self.client.downstream_sock.sendall(data)
            self.upstream_frames.put(WORKING)
            self.counter.received(len(data))
            self.received_bytes += len(data)
            if self.spdy_version == SPDY_3:
                self.downstream_window_size -= len(data)
                if self.downstream_window_size < 65536 / 2:
                    self.send_cb(spdy.frames.WindowUpdate(
                        self.stream_id, 65536 - self.downstream_window_size, version=SPDY_3))
                    self.downstream_window_size = 65536
        except socket.error:
            self._done = True
        except:
            self._done = True
            LOGGER.exception('[%s] failed to send to downstream' % repr(self.client))

    def update_upstream_window(self, delta_window_size):
        if self.spdy_version == SPDY_3:
            self.upstream_window_size += delta_window_size
            if self.upstream_window_size > 0:
                self.remote_ready.set()

    def poll_from_downstream(self):
        try:
            while not self.done:
                ins, _, _ = select.select([self.client.downstream_sock], [], [], 2)
                if self.done:
                    return
                if self.client.downstream_sock in ins:
                    data = self.client.downstream_sock.recv(8192)
                    if data:
                        self.upstream_frames.put(WORKING)
                        self.send_cb(spdy.frames.DataFrame(self.stream_id, data, flags=0))
                        self.counter.sending(len(data))
                        self.sent_bytes += len(data)
                        if self.spdy_version == SPDY_3:
                            self.upstream_window_size -= len(data)
                            if self.upstream_window_size <= 0:
                                self.remote_ready.clear()
                                self.remote_ready.wait()
                    else:
                        self._done = True
                        return
        except select.error:
            self._done = True
        except socket.error:
            self._done = True
        except:
            self._done = True
            LOGGER.exception('[%s] failed to poll from downstream' % repr(self.client))

    @property
    def done(self):
        if self.received_bytes >= self.response_content_length and self.sent_bytes >= self.request_content_length:
            self._done = True
        return self._done

    def close(self):
        pass
