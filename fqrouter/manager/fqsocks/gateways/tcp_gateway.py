import logging
import gevent.server
from .. import networking
from .proxy_client import ProxyClient
from .proxy_client import handle_client

LOGGER = logging.getLogger(__name__)
LISTEN_IP = None
LISTEN_PORT = None
server_greenlet = None


def handle(downstream_sock, address):
    src_ip, src_port = address
    try:
        dst_ip, dst_port = networking.get_original_destination(downstream_sock, src_ip, src_port)
        client = ProxyClient(downstream_sock, src_ip, src_port, dst_ip, dst_port)
        handle_client(client)
    except:
        LOGGER.exception('failed to handle %s:%s' % (src_ip, src_port))


def serve_forever():
    server = gevent.server.StreamServer((LISTEN_IP, LISTEN_PORT), handle)
    LOGGER.info('started fqsocks tcp gateway at %s:%s' % (LISTEN_IP, LISTEN_PORT))
    try:
        server.serve_forever()
    except:
        LOGGER.exception('failed to start tcp gateway')
    finally:
        LOGGER.info('tcp gateway stopped')