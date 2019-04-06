import gevent.monkey

gevent.monkey.patch_all(ssl=False, thread=True)

import logging
import logging.handlers
import sys
import os
import config
import traceback
import httplib
import fqsocks.httpd
import fqsocks.fqsocks
import wifi
import shell
import iptables
import shutdown_hook
import shlex
import subprocess
import functools
import comp_scrambler
import comp_shortcut
import fqsocks.pages.downstream
import fqsocks.config_file
import fqsocks.networking
import fqsocks.pages.home
import fqsocks.gateways.proxy_client
import fqsocks.proxies.ipv6_direct
import fqdns
import struct
import fcntl
import socket
import teredo

# https://www.kernel.org/doc/Documentation/networking/tuntap.txt
# struct ifreq {
# #define IFHWADDRLEN	6
# 	union
# 	{
# 		char	ifrn_name[IFNAMSIZ];		/* if name, e.g. "en0" */
# 	} ifr_ifrn;
#
# 	union {
# 		struct	sockaddr ifru_addr;
# 		struct	sockaddr ifru_dstaddr;
# 		struct	sockaddr ifru_broadaddr;
# 		struct	sockaddr ifru_netmask;
# 		struct  sockaddr ifru_hwaddr;
# 		short	ifru_flags;
# 		int	ifru_ivalue;
# 		int	ifru_mtu;
# 		struct  ifmap ifru_map;
# 		char	ifru_slave[IFNAMSIZ];	/* Just fits the size */
# 		char	ifru_newname[IFNAMSIZ];
# 		void __user *	ifru_data;
# 		struct	if_settings ifru_settings;
# 	} ifr_ifru;
# };
#
# #define	IFNAMSIZ	16
# #define TUNSETIFF     _IOW('T', 202, int)   0x4004 54CA
# define IFF_TUN		0x0001
# define IFF_TAP		0x0002
# define IFF_NO_PI	0x1000

# IFF_NO_PI tells the kernel to not provide packet information.
# The purpose of IFF_NO_PI is to tell the kernel that packets will be "pure" IP packets,
# with no added bytes. Otherwise (if IFF_NO_PI is unset),
# 4 extra bytes are added to the beginning of the packet (2 flag bytes and 2 protocol bytes).
# IFF_NO_PI need not match between interface creation and reconnection time.
# Also note that when capturing traffic on the interface with Wireshark, those 4 bytes are never shown.

fqsocks.pages.home.is_root_mode = True
default_loacl_teredo_ip = '2001:0:53aa:64c:0:1234:1234:1234'

comp_shortcut_enabled = False
current_path = os.path.dirname(os.path.abspath(__file__))
home_path = os.path.abspath(current_path + "/..")
BUSYBOX_PATH = home_path + '/../busybox'
FQROUTER_VERSION = 'ULTIMATE'
LOGGER = logging.getLogger('fqrouter')
LOG_DIR = home_path + "/log"
MANAGER_LOG_FILE = os.path.join(LOG_DIR, 'manager.log')
WIFI_LOG_FILE = os.path.join(LOG_DIR, 'wifi.log')
FQDNS_LOG_FILE = os.path.join(LOG_DIR, 'fqdns.log')
FQLAN_LOG_FILE = os.path.join(LOG_DIR, 'fqlan.log')
DNS_RULES = [
    (
        {'target': 'ACCEPT', 'extra': 'udp dpt:53 mark match 0xcafe', 'optional': True},
        ('nat', 'OUTPUT', '-p udp --dport 53 -m mark --mark 0xcafe -j ACCEPT')
    ), (
        {'target': 'DNAT', 'extra': 'udp dpt:53 to:10.1.2.3:12345'},
        ('nat', 'OUTPUT', '-p udp ! -s 10.1.2.3 --dport 53 -j DNAT --to-destination 10.1.2.3:12345')
    ), (
        {'target': 'DNAT', 'extra': 'udp dpt:53 to:10.1.2.3:12345'},
        ('nat', 'PREROUTING', '-p udp ! -s 10.1.2.3 --dport 53 -j DNAT --to-destination 10.1.2.3:12345')
    )]
SOCKS_RULES = [
    (
        {'target': 'DROP', 'extra': 'icmp type 5'},
        ('filter', 'OUTPUT', '-p icmp --icmp-type 5 -j DROP')
    ), (
        {'target': 'ACCEPT', 'destination': '127.0.0.1'},
        ('nat', 'OUTPUT', '-p tcp -d 127.0.0.1 -j ACCEPT')
    ), (
        {'target': 'DNAT', 'extra': 'to:10.1.2.3:12345'},
        ('nat', 'PREROUTING', '-p tcp ! -s 10.1.2.3 -j DNAT --to-destination 10.1.2.3:12345')
    )]
default_dns_server = config.get_default_dns_server()
DNS_HANDLER = fqdns.DnsHandler(
    enable_china_domain=True, enable_hosted_domain=False,
    original_upstream=('udp', default_dns_server, 53) if default_dns_server else None)
# fqsocks.fqsocks.DNS_HANDLER = DNS_HANDLER
fqsocks.networking.DNS_HANDLER = DNS_HANDLER

def handle_ping(environ, start_response):
    try:
        LOGGER.info('PONG/%s' % FQROUTER_VERSION)
    except:
        traceback.print_exc()
        os._exit(1)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    yield 'PONG/%s' % FQROUTER_VERSION


fqsocks.httpd.HANDLERS[('GET', 'ping')] = handle_ping

def exit_later():
    LOGGER.info('exit later')
    if fqsocks.gateways.proxy_client.ipv6_direct_enable:
        fqsocks.proxies.ipv6_direct.save_ipv6_host()
    shutdown_hook.execute()
    gevent.sleep(0.5)
    os._exit(1)

def handle_exit(environ, start_response):
    gevent.spawn(exit_later)
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    return ['EXITING']


fqsocks.httpd.HANDLERS[('POST', 'exit')] = handle_exit


def setup_logging():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if os.getenv('DEBUG') else (logging.CRITICAL + 1), format='%(asctime)s %(levelname)s %(message)s')
    log_level = logging.DEBUG if os.getenv('DEBUG') else logging.INFO
    handler = logging.handlers.RotatingFileHandler(
        MANAGER_LOG_FILE, maxBytes=1024 * 512, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    handler.setLevel(log_level)
    logging.getLogger('fqrouter').addHandler(handler)
    handler = logging.handlers.RotatingFileHandler(
        FQDNS_LOG_FILE, maxBytes=1024 * 256, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    handler.setLevel(log_level)
    logging.getLogger('fqdns').addHandler(handler)
    handler = logging.handlers.RotatingFileHandler(
        FQLAN_LOG_FILE, maxBytes=1024 * 256, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    handler.setLevel(log_level)
    logging.getLogger('fqlan').addHandler(handler)
    handler = logging.handlers.RotatingFileHandler(
        WIFI_LOG_FILE, maxBytes=1024 * 512, backupCount=1)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    handler.setLevel(log_level)
    logging.getLogger('wifi').addHandler(handler)
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, 'teredo.log'), maxBytes=1024 * 256, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    handler.setLevel(log_level)
    logging.getLogger('teredo').addHandler(handler)


def shell_execute(command):
    LOGGER.info('execute: %s' % command)
    output = ''
    try:
        output = shell.check_output(shlex.split(command) if isinstance(command, basestring) else command)
        LOGGER.info('succeed, output: %s' % output)
    except subprocess.CalledProcessError, e:
        LOGGER.error('failed, output: %s' % e.output)
    return output

def shell_execute_busybox(command):
    return shell_execute('%s %s' % (BUSYBOX_PATH, command))

def init_tun(teredo_ip):
    # show device configure
    shell_execute('ip rule')
    shell_execute('ip addr')
    shell_execute('ip -f inet6 route list')
    shell_execute_busybox('ifconfig')
    shell_execute_busybox('route -A inet6')
    # prepare environment
    shell_execute_busybox('mkdir /dev/net')
    shell_execute_busybox('ln -s /dev/tun /dev/net/tun')
    shell_execute_busybox('chmod 666 /dev/net/tun')
    shell_execute_busybox('chmod 666 /dev/tun')
    output = shell_execute('ip tuntap')
    if output:
        index = output.find('tun')
        if index >= 0 and len(output) >= index+4:
            shell_execute('ip tuntap del dev %s mode tun' % output[index:index+4])

    # shell_execute('ip tuntap del dev tun1 mode tun')
    # open tun1
    try:
        if os.path.exists('/dev/tun'):
            fd = os.open('/dev/tun', os.O_RDWR)
        elif os.path.exists('/dev/net/tun'):
            fd = os.open('/dev/net/tun', os.O_RDWR)
        else:
            LOGGER.error('tun not exist')
            return
        if fd < 0:
            LOGGER.error('open tun fail')
            return
        output = fcntl.ioctl(fd, 0x400454CA, struct.pack('16sH', 'tun1\0', 0x0001|0x1000))
        name,iff = struct.unpack('16sH', output)
    except:
        LOGGER.exception('tun ioctl or open fail')
        return
    LOGGER.debug('ioctl:%s' % str(output))
    if not name or name.find('tun1') != 0:
        LOGGER.error('tun ioctl fail, wrong ifr_name')
        return
    # config route and tun1
    shell_execute('ip addr add %s dev tun1' % teredo_ip)
    shell_execute('ip link set tun1 up')
    # It doesn't work adding a route to table main or table in number even after a new rule added in Android.
    shell_execute('ip -f inet6 route add default dev tun1 mtu 1280 table local')
    try:
        mtu = open('/sys/class/net/tun1/mtu', 'w')
        mtu.write('1280')
        mtu.close()
    except:
        LOGGER.exception("set mtu fail")
    output = shell_execute('ip route get 2607:f8b0:401d:14::13')
    if not output or output.find('tun1') == -1:
        LOGGER.error('config tun fail')
        return
    return fd


def redirect_ipv6_packet(tun_fd, teredo_client):
    gevent.socket.wait_read(tun_fd)
    try:
        data = os.read(tun_fd, 8192)
    except OSError, e:
        LOGGER.error('read packet failed: %s' % e)
        gevent.sleep(3)
        return
    return teredo_client.transmit(data)


def redirect_tun_traffic(tun_fd, teredo_client):
    while True:
        try:
            redirect_ipv6_packet(tun_fd, teredo_client)
        except:
            LOGGER.exception('failed to handle ipv6 packet')


def needs_su():
    if os.getuid() == 0:
        return False
    else:
        return True

def setup_nat():
    proxy_mode = os.getenv('PROXY_MODE')
    if not proxy_mode:
        proxy_mode = '0'
    proxy_list = os.getenv('PROXY_LIST')
    if not proxy_list:
        proxy_list = ''
    proxy_list = proxy_list.split()

    if proxy_mode == '1':
        pass
    elif proxy_mode == '2':
        for uid in proxy_list:
            SOCKS_RULES.append((
                {'target': 'DNAT', 'extra': 'owner UID match ' + uid + ' to:10.1.2.3:12345'},
                ('nat', 'OUTPUT', '-p tcp ! -s 10.1.2.3 -j DNAT --to-destination 10.1.2.3:12345  -m owner --uid-owner ' + uid)
            ))
    elif proxy_mode == '3':
        for uid in proxy_list:
            SOCKS_RULES.append((
                {'target': 'RETURN', 'extra': 'owner UID match ' + uid},
                ('nat', 'OUTPUT', '-j RETURN -m owner --uid-owner ' + uid)
            ))

        SOCKS_RULES.append((
            {'target': 'DNAT', 'extra': 'to:10.1.2.3:12345'},
            ('nat', 'OUTPUT', '-p tcp ! -s 10.1.2.3 -j DNAT --to-destination 10.1.2.3:12345')
        ))
    else:
        SOCKS_RULES.append((
            {'target': 'DNAT', 'extra': 'to:10.1.2.3:12345'},
            ('nat', 'OUTPUT', '-p tcp ! -s 10.1.2.3 -j DNAT --to-destination 10.1.2.3:12345')
        ))


def run():
    iptables.tables = {}
    iptables.init_fq_chains()
    shutdown_hook.add(iptables.flush_fq_chain)
    if not os.getenv('NO_FQDNS'):
        iptables.insert_rules(DNS_RULES)
        shutdown_hook.add(functools.partial(iptables.delete_rules, DNS_RULES))
    setup_nat()
    iptables.insert_rules(SOCKS_RULES)
    shutdown_hook.add(functools.partial(iptables.delete_rules, SOCKS_RULES))
    wifi.setup_lo_alias()

    if not os.getenv('NO_TEREDO'):
        LOGGER.info('init teredo and tun')
        sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        sock.bind(('10.1.2.3', 0))
        teredo_client = teredo.teredo_client(sock, teredo.get_default_teredo_server())
        teredo_ip = None
        try:
            teredo_ip = teredo_client.start()
        except:
            LOGGER.exception('start teredo fail')
        if not teredo_ip:
            LOGGER.error('start teredo client fail, use default:%s' % default_loacl_teredo_ip)
            teredo_ip = default_loacl_teredo_ip
        else:
            LOGGER.info('teredo start succeed, teredo ip:%s' % teredo_ip)

        tun_fd = init_tun(teredo_ip)
        if not tun_fd:
            LOGGER.error('init tun fail!')
        else:
            teredo.tun_fd = tun_fd
            teredo_client.server_forever(teredo_ip)
            gevent.spawn(redirect_tun_traffic, tun_fd, teredo_client)


    args = [
        '--log-level', 'DEBUG' if os.getenv('DEBUG') else 'INFO',
        '--log-file', LOG_DIR + '/fqsocks.log',
        '--ifconfig-command', home_path + '/../busybox',
        #'--ip-command', 'ip',
        '--outbound-ip', '10.1.2.3',
        '--tcp-gateway-listen', '10.1.2.3:12345',
        '--dns-server-listen', '10.1.2.3:12345'
    ]
    if shell.USE_SU:
        args.append('--no-tcp-scrambler')
    args = config.configure_fqsocks(args)
    fqsocks.fqsocks.init_config(args)
    if fqsocks.config_file.read_config()['tcp_scrambler_enabled']:
        try:
            comp_scrambler.start()
            shutdown_hook.add(comp_scrambler.stop)
        except:
            LOGGER.exception('failed to start comp_scrambler')
            comp_scrambler.stop()
    if fqsocks.config_file.read_config()['china_shortcut_enabled'] and comp_shortcut_enabled:
        try:
            comp_shortcut.start()
            shutdown_hook.add(comp_shortcut.stop)
        except:
            LOGGER.exception('failed to start comp_shortcut')
            comp_shortcut.stop()
    iptables.tables = {}
    fqsocks.fqsocks.main()


def clean():
    LOGGER.info('clean...')
    iptables.tables = {}
    try:
        iptables.flush_fq_chain()
        try:
            LOGGER.info('iptables -L -v -n')
            LOGGER.info(shell.check_output(shlex.split('iptables -L -v -n')))
        except subprocess.CalledProcessError, e:
            LOGGER.error('failed to dump filter table: %s' % (sys.exc_info()[1]))
            LOGGER.error(e.output)
        try:
            LOGGER.info('iptables -t nat -L -v -n')
            LOGGER.info(shell.check_output(shlex.split('iptables -t nat -L -v -n')))
        except subprocess.CalledProcessError, e:
            LOGGER.error('failed to dump nat table: %s' % (sys.exc_info()[1]))
            LOGGER.error(e.output)
    except:
        LOGGER.exception('clean failed')


def wifi_reset():
    wifi.enable_wifi_p2p_service()
    wifi.restore_config_files()
    wifi.stop_hotspot()

_is_wifi_repeater_supported = None


def check_wifi_repeater_supported():
    try:
        api_version = wifi.shell_execute('getprop ro.build.version.sdk').strip()
        if api_version:
            return int(api_version) >= 14
        else:
            return True
    except:
        LOGGER.exception('failed to get api version')
        return True


def is_wifi_repeater_supported():
    global _is_wifi_repeater_supported
    if _is_wifi_repeater_supported is None:
        _is_wifi_repeater_supported = check_wifi_repeater_supported()
    return _is_wifi_repeater_supported


def is_wifi_repeater_started():
    if wifi.has_started_before:
        return wifi.get_working_hotspot_iface()
    return False


fqsocks.pages.downstream.spi_wifi_repeater = {
    'is_supported': is_wifi_repeater_supported,
    'is_started': is_wifi_repeater_started,
    'start': wifi.start_hotspot,
    'stop': wifi.stop_hotspot,
    'reset': wifi_reset
}

if '__main__' == __name__:
    setup_logging()
    LOGGER.info('running main.py')
    LOGGER.info('environment: %s' % os.environ.items())
    LOGGER.info('default dns server: %s' % default_dns_server)
    if len(sys.argv) > 1:
        action = sys.argv[1]
    else:
        action = 'run'
    if 'clean' == action:
        shell.USE_SU = needs_su()
        clean()
    elif 'run' == action:
        shell.USE_SU = needs_su()
        run()
    elif 'netd-execute' == action:
        wifi.netd_execute(sys.argv[2])
    else:
        raise Exception('unknown action: %s' % action)
