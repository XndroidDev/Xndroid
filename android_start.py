#!/usr/bin/kivy

import os, sys
import zipfile
import _multiprocessing
import socket
import _socket
import ssl
import _ssl
import OpenSSL.SSL as SSL
import contextlib
import logging
import logging.handlers


LOGGER = logging.getLogger('xxnet_start')
current_path = os.path.dirname(os.path.abspath(__file__))
original_socket_connect = socket.socket.connect
original_socket_connect_ex = socket.socket.connect_ex
original_socket_init = socket.socket.__init__
original_ssl_real_connect = ssl.SSLSocket._real_connect
original_openssl_connect = SSL.Connection.connect
OUTBOUND_IP = '10.1.2.3'
protect_socket = True
vpn_mode = True


def sock_connect_main(self, addr):
    if protect_socket and not vpn_mode:
        self.bind((OUTBOUND_IP, 0))
    original_socket_connect(self, addr)

def sock_connect_ex_main(self, addr):
    try:
        sock_connect_main(self, addr)
    except:
        return -1
    return 0

MAX_SOCK_OPTION_LEN = 64
_sock_options = {socket.SO_REUSEADDR, socket.SO_LINGER, socket.SO_RCVBUF,
                 socket.TCP_NODELAY, socket.SO_KEEPALIVE, socket.SO_SNDBUF}

def sock_connect_vpn(self, addr):
    # if LOGGER.isEnabledFor(logging.DEBUG):
    #     LOGGER.info('vpn socket connect %s' % str(addr))
    if protect_socket == False or vpn_mode == False or self.type != socket.SOCK_STREAM:
        return original_socket_connect(self, addr)
    if self.family != socket.AF_INET:
        return original_socket_connect(self, addr)
    host,port = addr
    if host == '127.0.0.1':
        return original_socket_connect(self, addr)
    # if LOGGER.isEnabledFor(logging.DEBUG):
    #         LOGGER.debug("vpn tcp %s:%s" % (host, port))
    fdsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    with contextlib.closing(fdsock):
        timeout = self.gettimeout()
        fdsock.connect('\0fdsock2')
        fdsock.sendall('OPEN TCP,%s,%s,%s\n' %
                       (host, port,int(timeout * 1000) if timeout else 5000))
        fd = _multiprocessing.recvfd(fdsock.fileno())
        # if LOGGER.isEnabledFor(logging.DEBUG):
        #     LOGGER.debug("vpn tcp %s:%s,rev fd, fd=%s, timeout=%s" % (host, port, fd, timeout))
        if fd <= 2:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.error('vpn fail to create tcp socket: %s:%s, wrong fd' % (host, port))
            raise socket.error('vpn fail to create tcp socket: %s:%s' % (host, port))
        sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
        os.close(fd)
        sock.settimeout(timeout)
        for option in _sock_options:
            val = socket.socket.getsockopt(self, socket.SOL_SOCKET, option, MAX_SOCK_OPTION_LEN)
            if val:
                _socket.socket.setsockopt(sock, socket.SOL_SOCKET, option, val)
        self._sock = sock
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('vpn create tcp socket OK: %s:%s' % (host, port))


def sock_connect_ex_vpn(self, addr):
    try:
        sock_connect_vpn(self, addr)
    except:
        return -1
    return 0

def sock_init_vpn(self, family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, _sock=None):
    # if LOGGER.isEnabledFor(logging.DEBUG):
    #     LOGGER.debug("!")
    if protect_socket == False or vpn_mode == False or type != socket.SOCK_DGRAM:
        original_socket_init(self, family, type, proto, _sock)
        return
    if family != socket.AF_INET:
        original_socket_init(self, family, type, proto, _sock)
        return
    fdsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    with contextlib.closing(fdsock):
        fdsock.connect('\0fdsock2')
        fdsock.sendall('OPEN UDP\n')
        fd = _multiprocessing.recvfd(fdsock.fileno())
        if fd <= 2:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.error('vpn fail to create udp socket')
            raise socket.error('vpn fail to create udp socket')
        sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_DGRAM)
        os.close(fd)
        self._sock = sock
    if LOGGER.isEnabledFor(logging.DEBUG):
        LOGGER.debug("vpn create udp socket OK")


def ssl_real_connect(self, addr, return_errno):
    if isinstance(addr, basestring):
        addr = (addr, 443)
    if LOGGER.isEnabledFor(logging.DEBUG):
        LOGGER.debug("vpn ssl connect %s:%s" % addr)
    if self._connected:
        raise ValueError('attempt to connect already-connected SSLSocket!')
    try:
        socket.socket.connect(self, addr)
        self._sslobj = _ssl.sslwrap(self._sock, False, self.keyfile, self.certfile, self.cert_reqs, self.ssl_version, self.ca_certs, self.ciphers)
        if self.do_handshake_on_connect:
            self.do_handshake()
    except socket.error as e:
        if return_errno:
            return e.errno
        self._sslobj = None
        raise e

    self._connected = True
    return 0

def openssl_connect(self, addr):
    self._socket.connect(addr)
    set_result = SSL._lib.SSL_set_fd(self._ssl, SSL._asFileDescriptor(self._socket))
    if not set_result:
        raise socket.error('OpenSSL set fd fail %s:%s' % addr)
    SSL._lib.SSL_set_connect_state(self._ssl)

def patch_socket():
    LOGGER.info('patch_socket,protect_socket=%s,vpn_mode=%s' % (protect_socket, vpn_mode))
    socket.socket.connect = original_socket_connect
    socket.socket.connect_ex = original_socket_connect_ex
    socket.socket.__init__ = original_socket_init
    ssl.SSLSocket._real_connect = original_ssl_real_connect
    SSL.Connection.connect = original_openssl_connect
    if not protect_socket:
        return
    if vpn_mode:
        socket.socket.connect = sock_connect_vpn
        socket.socket.connect_ex = sock_connect_ex_vpn
        socket.socket.__init__ = sock_init_vpn
        ssl.SSLSocket._real_connect = ssl_real_connect
        SSL.Connection.connect = openssl_connect
    else:
        socket.socket.connect = sock_connect_main
        socket.socket.connect_ex = sock_connect_ex_main



def load_xxnet():
    xxnet_path = current_path
    version_fn = os.path.join(xxnet_path, "code", "version.txt")
    LOGGER.info("load_xxnet on:%s" % xxnet_path)
    version = "default"
    if os.path.exists(version_fn):
        with open(version_fn, "rt") as fd:
            version = fd.readline().strip()

    if not os.path.exists(os.path.join(xxnet_path, "code", version, "launcher")):
        LOGGER.error("version %s not exist, use default." % version)
        version = "default"
    else:
        LOGGER.info("launch version:%s" % version)

    launcher_path = os.path.join(xxnet_path, "code", version, "launcher")
    sys.path.insert(0, launcher_path)

    from start import main as launcher_main
    launcher_main()

def setup_logging():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
    handler = logging.handlers.RotatingFileHandler(
        current_path + "/xxnet_start.log", maxBytes=1024 * 256, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s [android_start]%(levelname)s %(message)s'))
    logging.getLogger('xxnet_start').addHandler(handler)


def main():
    arg = sys.argv
    setup_logging()
    global protect_socket, vpn_mode
    if len(arg) >= 3:
        if cmp(arg[1], 'protect_sock') == 0:
            protect_socket = True
            if cmp(arg[2], 'vpn_mode') == 0:
                vpn_mode = True
        else:
            protect_socket = False
    if protect_socket:
        patch_socket()
    load_xxnet()


if __name__ == '__main__':
    main()





