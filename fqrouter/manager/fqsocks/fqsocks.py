#!/usr/bin/env python
# thanks @phuslu https://github.com/phus/sniproxy/blob/master/sniproxy.py
# thanks @ofmax https://github.com/madeye/gaeproxy/blob/master/assets/modules/python.mp3
import logging
import logging.handlers
import sys
import argparse
import httplib
import fqlan
import fqdns

import gevent.server
import gevent.monkey

from .proxies.goagent import GoAgentProxy
import httpd
import networking
from .gateways import proxy_client
from .gateways import tcp_gateway
from .gateways import http_gateway
from .pages import lan_device
from .pages import upstream
from . import config_file


__import__('fqsocks.pages')
LOGGER = logging.getLogger(__name__)

dns_pollution_ignored = False
networking.DNS_HANDLER = fqdns.DnsHandler()
reset_force_us_ip_greenlet = None

@httpd.http_handler('GET', 'dns-polluted-at')
def get_dns_polluted_at(environ, start_response):
    global dns_pollution_ignored
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    if not dns_pollution_ignored and proxy_client.dns_polluted_at > 0:
        dns_pollution_ignored = True
        yield str(proxy_client.dns_polluted_at)
    else:
        yield '0'


@httpd.http_handler('POST', 'force-us-ip')
def handle_force_us_ip(environ, start_response):
    global reset_force_us_ip_greenlet
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    if reset_force_us_ip_greenlet is not None:
        reset_force_us_ip_greenlet.kill()
    reset_force_us_ip_greenlet = gevent.spawn(reset_force_us_ip)
    LOGGER.info('force_us_ip set to True')
    proxy_client.force_us_ip = True
    yield 'OK'


def reset_force_us_ip():
    global reset_force_us_ip_greenlet
    gevent.sleep(30)
    reset_force_us_ip_greenlet = None
    LOGGER.info('force_us_ip reset to False')
    proxy_client.force_us_ip = False



@httpd.http_handler('POST', 'clear-states')
def handle_clear_states(environ, start_response):
    proxy_client.clear_proxy_states()
    http_gateway.dns_cache = {}
    networking.default_interface_ip_cache = None
    lan_device.lan_devices = {}
    if lan_device.forge_greenlet is not None:
        lan_device.forge_greenlet.kill()
    LOGGER.info('cleared states upon request')
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    yield 'OK'


def setup_logging(log_level, log_file=None):
    logging.basicConfig(
        stream=sys.stdout, level=log_level, format='%(asctime)s %(levelname)s %(message)s')
    if log_file:
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=1024 * 512, backupCount=1)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        handler.setLevel(log_level)
        logging.getLogger('fqsocks').setLevel(log_level)
        logging.getLogger('fqsocks').addHandler(handler)


def init_config(argv):
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--tcp-gateway-listen')
    argument_parser.add_argument('--http-gateway-listen')
    argument_parser.add_argument('--dns-server-listen')
    argument_parser.add_argument('--no-dns-server', action='store_true')
    argument_parser.add_argument('--http-manager-listen')
    argument_parser.add_argument('--no-http-manager', action='store_true')
    argument_parser.add_argument('--outbound-ip')
    argument_parser.add_argument('--ip-command')
    argument_parser.add_argument('--ifconfig-command')
    argument_parser.add_argument('--config-file')
    argument_parser.add_argument('--log-level', default='INFO')
    argument_parser.add_argument('--log-file')
    argument_parser.add_argument('--proxy', action='append', default=[], help='for example --proxy goagent,appid=abcd')
    argument_parser.add_argument('--google-host', action='append', default=[])
    argument_parser.add_argument('--access-check', dest='access_check_enabled', action='store_true')
    argument_parser.add_argument('--no-access-check', dest='access_check_enabled', action='store_false')
    argument_parser.set_defaults(access_check_enabled=None)
    argument_parser.add_argument('--direct-access', dest='direct_access_enabled', action='store_true')
    argument_parser.add_argument('--no-direct-access', dest='direct_access_enabled', action='store_false')
    argument_parser.set_defaults(direct_access_enabled=None)
    argument_parser.add_argument('--china-shortcut', dest='china_shortcut_enabled', action='store_true')
    argument_parser.add_argument('--no-china-shortcut', dest='china_shortcut_enabled', action='store_false')
    argument_parser.set_defaults(china_shortcut_enabled=None)
    argument_parser.add_argument('--tcp-scrambler', dest='tcp_scrambler_enabled', action='store_true')
    argument_parser.add_argument('--no-tcp-scrambler', dest='tcp_scrambler_enabled', action='store_false')
    argument_parser.set_defaults(tcp_scrambler_enabled=None)
    argument_parser.add_argument('--google-scrambler', dest='google_scrambler_enabled', action='store_true')
    argument_parser.add_argument('--no-google-scrambler', dest='google_scrambler_enabled', action='store_false')
    argument_parser.set_defaults(google_scrambler_enabled=None)
    args = argument_parser.parse_args(argv)
    config_file.cli_args = args
    config = config_file.read_config()
    log_level = getattr(logging, config['log_level'])
    setup_logging(log_level, config['log_file'])
    LOGGER.info('config: %s' % config)
    if config['ip_command']:
        fqlan.IP_COMMAND = config['ip_command']
    if config['ifconfig_command']:
        fqlan.IFCONFIG_COMMAND = config['ifconfig_command']
    networking.OUTBOUND_IP = config['outbound_ip']
    fqdns.OUTBOUND_IP = config['outbound_ip']
    if config['google_host']:
        GoAgentProxy.GOOGLE_HOSTS = config['google_host']
    proxy_client.china_shortcut_enabled = config['china_shortcut_enabled']
    proxy_client.direct_access_enabled = config['direct_access_enabled']
    proxy_client.tcp_scrambler_enabled = config['tcp_scrambler_enabled']
    proxy_client.google_scrambler_enabled = config['google_scrambler_enabled']
    proxy_client.https_enforcer_enabled = config['https_enforcer_enabled']
    proxy_client.goagent_public_servers_enabled = config['public_servers']['goagent_enabled']
    proxy_client.ss_public_servers_enabled = config['public_servers']['ss_enabled']
    proxy_client.prefers_private_proxy = config['prefers_private_proxy']
    networking.DNS_HANDLER.enable_hosted_domain = config['hosted_domain_enabled']
    http_gateway.LISTEN_IP, http_gateway.LISTEN_PORT = config['http_gateway']['ip'], config['http_gateway']['port']
    tcp_gateway.LISTEN_IP, tcp_gateway.LISTEN_PORT = config['tcp_gateway']['ip'], config['tcp_gateway']['port']
    httpd.LISTEN_IP, httpd.LISTEN_PORT = config['http_manager']['ip'], config['http_manager']['port']
    networking.DNS_HANDLER.test_upstreams()

def main(argv=None):
    if argv:
        init_config(argv)
    config = config_file.read_config()
    gevent.monkey.patch_all(ssl=False, thread=True)
    try:
        gevent.monkey.patch_ssl()
    except:
        LOGGER.exception('failed to patch ssl')
    greenlets = []
    if config['dns_server']['enabled']:
        dns_server_address = (config['dns_server']['ip'], config['dns_server']['port'])
        dns_server = fqdns.HandlerDatagramServer(dns_server_address, networking.DNS_HANDLER)
        greenlets.append(gevent.spawn(dns_server.serve_forever))
    if config['http_gateway']['enabled']:
        http_gateway.server_greenlet = gevent.spawn(http_gateway.serve_forever)
        greenlets.append(http_gateway.server_greenlet)
    if config['tcp_gateway']['enabled']:
        tcp_gateway.server_greenlet = gevent.spawn(tcp_gateway.serve_forever)
        greenlets.append(tcp_gateway.server_greenlet)
    if config['http_manager']['enabled']:
        httpd.server_greenlet = gevent.spawn(httpd.serve_forever)
        greenlets.append(httpd.server_greenlet)
    greenlets.append(gevent.spawn(proxy_client.init_proxies, config))
    for greenlet in greenlets:
        try:
            greenlet.join()
        except KeyboardInterrupt:
            return
        except:
            LOGGER.exception('greenlet join failed')
            return


# TODO add socks4 proxy
# TODO add socks5 proxy
# TODO === future ===
# TODO add vpn as proxy (setup vpn, mark packet, mark based routing)

if '__main__' == __name__:
    main(sys.argv[1:])