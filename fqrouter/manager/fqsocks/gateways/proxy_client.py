import logging
import sys
import socket
import errno
import select
import random
import re
import math
import traceback
import time
import contextlib
import fqdns
import ssl
import urlparse
import gevent
import dpkt

from ..proxies.xxnet_gae import XXnetGAE
from ..proxies.sock5 import Sock5Proxy
from .. import networking
from .. import stat
from ..proxies.http_try import recv_and_parse_request
from ..proxies.http_try import NotHttp
from ..proxies.http_try import HTTP_TRY_PROXY
from ..proxies.http_try import TCP_SCRAMBLER
from ..proxies.google_http_try import GOOGLE_SCRAMBLER
from ..proxies.google_http_try import HTTPS_ENFORCER
from ..proxies.tcp_smuggler import TCP_SMUGGLER
from ..proxies.http_relay import HttpRelayProxy
from ..proxies.http_connect import HttpConnectProxy
from ..proxies import direct
from ..proxies.goagent import GoAgentProxy
from ..proxies.dynamic import DynamicProxy
from ..proxies.dynamic import proxy_types
from ..proxies.shadowsocks import ShadowSocksProxy
from ..proxies.ssh import SshProxy
from .. import us_ip
from .. import lan_ip
from .. import china_ip
from ..proxies.direct import DIRECT_PROXY
from ..proxies.direct import NONE_PROXY
from ..proxies.https_try import HTTPS_TRY_PROXY
from .. import ip_substitution
from .. import config_file
import os.path

TLS1_1_VERSION = 0x0302
RE_HTTP_HOST = re.compile('Host: (.+)\r\n')
LOGGER = logging.getLogger(__name__)

proxies = []
dns_polluted_at = 0
china_shortcut_enabled = True
direct_access_enabled = True
tcp_scrambler_enabled = True
google_scrambler_enabled = True
prefers_private_proxy = True
https_enforcer_enabled = True
goagent_public_servers_enabled = False
ss_public_servers_enabled = True
last_refresh_started_at = -1
refresh_timestamps = []
goagent_group_exhausted = False
force_us_ip = False
on_clear_states = None
preferred_proxies = {} # (dst_ip, dst_port) => proxy


class ProxyClient(object):
    def __init__(self, downstream_sock, src_ip, src_port, dst_ip, dst_port):
        super(ProxyClient, self).__init__()
        self.downstream_sock = downstream_sock
        self.downstream_rfile = downstream_sock.makefile('rb', 8192)
        self.downstream_wfile = downstream_sock.makefile('wb', 0)
        self.forward_started = False
        self.resources = [self.downstream_sock, self.downstream_rfile, self.downstream_wfile]
        self.src_ip = src_ip
        self.src_port = src_port
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.peeked_data = ''
        self.host = ''
        self.protocol = None
        self.tried_proxies = {}
        self.forwarding_by = None
        self.us_ip_only = force_us_ip
        self.delayed_penalties = []
        self.ip_substituted = False

    def create_tcp_socket(self, server_ip, server_port, connect_timeout):
        upstream_sock = networking.create_tcp_socket(server_ip, server_port, connect_timeout)
        upstream_sock.counter = stat.opened(upstream_sock, self.forwarding_by, self.host, self.dst_ip)
        self.resources.append(upstream_sock)
        self.resources.append(upstream_sock.counter)
        return upstream_sock

    def add_resource(self, res):
        self.resources.append(res)

    def forward(self, upstream_sock, timeout=7, after_started_timeout=360, encrypt=None, decrypt=None,
                delayed_penalty=None, on_forward_started=None):

        if self.forward_started:
            if self.dst_port in [5228, 8883]: # Google Service and MQTT
                upstream_sock.settimeout(None)
            else: # More than 5 minutes
                upstream_sock.settimeout(after_started_timeout)
        else:
            upstream_sock.settimeout(timeout)
        self.downstream_sock.settimeout(None)

        def from_upstream_to_downstream():
            try:
                while True:
                    data = upstream_sock.recv(8192)
                    upstream_sock.counter.received(len(data))
                    if data:
                        if not self.forward_started:
                            self.forward_started = True
                            if self.dst_port in [5228, 8883]: # Google Service and MQTT
                                upstream_sock.settimeout(None)
                            else: # More than 5 minutes
                                upstream_sock.settimeout(after_started_timeout)
                            self.apply_delayed_penalties()
                            if on_forward_started:
                                on_forward_started()
                        if decrypt:
                            data = decrypt(data)
                        self.downstream_sock.sendall(data)
                    else:
                        return
            except socket.error:
                return
            except gevent.GreenletExit:
                return
            except:
                LOGGER.exception('forward u2d failed')
                return sys.exc_info()[1]

        def from_downstream_to_upstream():
            try:
                while True:
                    data = self.downstream_sock.recv(8192)
                    if data:
                        if encrypt:
                            data = encrypt(data)
                        upstream_sock.counter.sending(len(data))
                        upstream_sock.sendall(data)
                    else:
                        return
            except socket.error:
                return
            except gevent.GreenletExit:
                return
            except:
                LOGGER.exception('forward d2u failed')
                return sys.exc_info()[1]
            finally:
                upstream_sock.close()

        u2d = gevent.spawn(from_upstream_to_downstream)
        d2u = gevent.spawn(from_downstream_to_upstream)
        try:
            for greenlet in gevent.iwait([u2d, d2u]):
                e = greenlet.get()
                if e:
                    raise e
                break
            try:
                upstream_sock.close()
            except:
                pass
            if not self.forward_started:
                self.fall_back(reason='forward does not receive any response', delayed_penalty=delayed_penalty)
        finally:
            try:
                u2d.kill()
            except:
                pass
            try:
                d2u.kill()
            except:
                pass

    def apply_delayed_penalties(self):
        if self.delayed_penalties:
            LOGGER.info('[%s] apply delayed penalties' % repr(self))
        for delayed_penalty in self.delayed_penalties:
            try:
                delayed_penalty()
            except:
                LOGGER.exception('failed to apply delayed penalty: %s' % delayed_penalty)


    def close(self):
        for res in self.resources:
            try:
                res.close()
            except:
                pass

    def fall_back(self, reason, delayed_penalty=None, silently=False):
        if self.forward_started:
            LOGGER.fatal('[%s] fall back can not happen after forward started:\n%s' %
                         (repr(self), traceback.format_stack()))
            raise Exception('!!! fall back can not happen after forward started !!!')
        if delayed_penalty:
            self.delayed_penalties.append(delayed_penalty)
        raise ProxyFallBack(reason, silently=silently)

    def dump_proxies(self):
        LOGGER.info('dump proxies: %s' % [p for p in proxies if not p.died])

    def has_tried(self, proxy):
        if proxy in self.tried_proxies:
            return True
        if isinstance(proxy, DynamicProxy):
            proxy = proxy.delegated_to
        if self.us_ip_only:
            if hasattr(proxy, 'proxy_ip') and not us_ip.is_us_ip(proxy.proxy_ip):
                LOGGER.info('skip %s' % proxy.proxy_ip)
                return True
        return proxy in self.tried_proxies

    def __repr__(self):
        description = '%s:%s => %s:%s' % (self.src_ip, self.src_port, self.dst_ip, self.dst_port)
        if self.host:
            description = '%s %s' % (description, self.host)
        if self.forwarding_by:
            description = '%s %s' % (description, repr(self.forwarding_by))
        return description


class ProxyFallBack(Exception):
    def __init__(self, reason, silently):
        super(ProxyFallBack, self).__init__(reason)
        self.reason = reason
        self.silently = silently


ProxyClient.ProxyFallBack = ProxyFallBack


def handle_client(client):
    if goagent_group_exhausted:
        gevent.spawn(load_more_goagent_proxies)
    try:
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('[%s] downstream connected' % repr(client))
        pick_proxy_and_forward(client)
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('[%s] done' % repr(client))
    except NoMoreProxy:
        if HTTP_TRY_PROXY.host_slow_detection_enabled and client.host in HTTP_TRY_PROXY.host_slow_list:
            LOGGER.critical('!!! disable host slow detection !!!')
            HTTP_TRY_PROXY.host_slow_list.clear()
            HTTP_TRY_PROXY.host_slow_detection_enabled = False
        return
    except:
        err_msg = str(sys.exc_info()[1])
        if 'ascii' in err_msg or LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.exception('[%s] done with error' % repr(client))
        else:
            LOGGER.exception('[%s] done with error: %s' % (repr(client), err_msg))
    finally:
        client.close()


def pick_proxy_and_forward(client):
    global dns_polluted_at
    if lan_ip.is_lan_ip(client.dst_ip):
        try:
            DIRECT_PROXY.forward(client)
        except ProxyFallBack:
            pass
        return
    if client.dst_ip in fqdns.WRONG_ANSWERS:
        LOGGER.error('[%s] destination is GFW wrong answer' % repr(client))
        dns_polluted_at = time.time()
        NONE_PROXY.forward(client)
        return
    data_peeked = False
    if china_shortcut_enabled:
        china_dst = False
        if china_ip.is_china_ip(client.dst_ip):
            china_dst =True
        else:
            peek_data(client)
            data_peeked = True
            if client.host:
                china_dst = fqdns.is_china_domain(client.host)
        if china_dst:
            try:
                DIRECT_PROXY.forward(client)
            except ProxyFallBack:
                pass
            return
    if not data_peeked:
        peek_data(client)
    for i in range(3):
        try:
            proxy = pick_proxy(client)
        except NotHttp:
            return # give up
        if not proxy:
            raise NoMoreProxy()
        if 'DIRECT' in proxy.flags:
            LOGGER.debug('[%s] picked proxy: %s' % (repr(client), repr(proxy)))
        else:
            LOGGER.info('[%s] picked proxy: %s' % (repr(client), repr(proxy)))
        try:
            proxy.forward(client)
            return
        except ProxyFallBack as e:
            if not e.silently:
                LOGGER.error('[%s] fall back to other proxy due to %s: %s' % (repr(client), e.reason, repr(proxy)))
            client.tried_proxies[proxy] = e.reason
        except NotHttp:
            return # give up
    raise NoMoreProxy()


def is_china_dst(client):
    if china_ip.is_china_ip(client.dst_ip):
        return True
    if client.host and fqdns.is_china_domain(client.host):
        return True
    return False


def peek_data(client):
    if not client.peeked_data:
        ins, _, errors = select.select([client.downstream_sock], [], [client.downstream_sock], 0.1)
        if errors:
            LOGGER.error('[%s] peek data failed' % repr(client))
            return DIRECT_PROXY
        if not ins:
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug('[%s] peek data timed out' % repr(client))
        else:
            client.peeked_data = client.downstream_sock.recv(8192)
    protocol, domain = analyze_protocol(client.peeked_data)
    if LOGGER.isEnabledFor(logging.DEBUG):
        LOGGER.debug('[%s] analyzed traffic: %s %s' % (repr(client), protocol, domain))
    client.host = domain
    client.protocol = protocol
    if 'UNKNOWN' == client.protocol:
        if client.dst_port == 80:
            client.protocol = 'HTTP'
        elif client.dst_port == 443:
            client.protocol = 'HTTPS'


class NoMoreProxy(Exception):
    pass


def on_proxy_died(proxy):
    if isinstance(proxy, DynamicProxy):
        proxy = proxy.delegated_to
    else:
        return
    # if isinstance(proxy, GoAgentProxy):
    #     gevent.spawn(load_more_goagent_proxies)
direct.on_proxy_died = on_proxy_died


def load_more_goagent_proxies():
    '''not available anymore'''
    pass
    # global goagent_group_exhausted
    # global last_refresh_started_at
    # if time.time() - last_refresh_started_at < get_refresh_interval():
    #     return
    # last_refresh_started_at = time.time()
    # goagent_groups = {}
    # for proxy in proxies:
    #     if proxy.died:
    #         continue
    #     if isinstance(proxy, DynamicProxy):
    #         proxy = proxy.delegated_to
    #     else:
    #         continue
    #     if isinstance(proxy, GoAgentProxy):
    #         proxy.query_version()
    #         if proxy.died:
    #             continue
    #         goagent_groups.setdefault(proxy.group, set()).add(proxy.appid)
    # if goagent_group_exhausted:
    #     goagent_groups.setdefault(goagent_group_exhausted, set())
    # for group, appids in goagent_groups.items():
    #     LOGGER.critical('current %s appids count: %s' % (group, len(appids)))
    #     if len(appids) < 3:
    #         goagent_group_exhausted = group
    #         config = config_file.read_config()
    #         if len(proxies) < 50:
    #             load_public_proxies({
    #                 'source': config['public_servers']['source'],
    #                 'goagent_enabled': True
    #             })
    #         refresh_proxies(force=True)
    #         return
    # goagent_group_exhausted = False


def pick_proxy(client):
    picks_public = None
    if not direct_access_enabled:
        picks_public = False
    if not china_shortcut_enabled:
        picks_public = False
    if client.protocol == 'HTTP':
        return pick_preferred_private_proxy(client) or \
               pick_http_try_proxy(client) or \
               pick_tcp_smuggler(client) or \
               pick_proxy_supports(client, picks_public)
    elif client.protocol == 'HTTPS':
        return pick_preferred_private_proxy(client) or \
               pick_https_try_proxy(client) or \
               pick_proxy_supports(client, picks_public)
    else:
        return pick_preferred_private_proxy(client) or DIRECT_PROXY


def pick_preferred_private_proxy(client):
    if prefers_private_proxy:
        return pick_proxy_supports(client, picks_public=False)
    else:
        return None


def analyze_protocol(peeked_data):
    try:
        match = RE_HTTP_HOST.search(peeked_data)
        if match:
            return 'HTTP', match.group(1).strip()
        try:
            ssl3 = dpkt.ssl.SSL3(peeked_data)
        except dpkt.NeedData:
            return 'UNKNOWN', ''
        if ssl3.version in (dpkt.ssl.SSL3_VERSION, dpkt.ssl.TLS1_VERSION, TLS1_1_VERSION):
            return 'HTTPS', parse_sni_domain(peeked_data).strip()
    except:
        LOGGER.exception('failed to analyze protocol')
    return 'UNKNOWN', ''


domain_pattern = re.compile(r'\x00\x00(.)([\w\.-]{1,220}\.\w{2,25})', re.S)

def parse_sni_domain(data):
    domain = ''
    try:
        # extrace SNI from ClientHello packet, quick and dirty.
        domain = (m.group(2) for m in re.finditer(domain_pattern, data)
                  if ord(m.group(1)) == len(m.group(2))).next()
    except StopIteration:
        pass
    return domain


def pick_direct_proxy(client):
    return None if DIRECT_PROXY in client.tried_proxies else DIRECT_PROXY


def pick_http_try_proxy(client):
    if getattr(client, 'http_proxy_tried', False):
        return None
    try:
        if client.us_ip_only:
            return None
        if not direct_access_enabled:
            return None
        if not hasattr(client, 'is_payload_complete'): # only parse it once
            client.is_payload_complete = recv_and_parse_request(client)
        if tcp_scrambler_enabled and \
                not TCP_SMUGGLER.is_protocol_supported('HTTP', client) and \
                TCP_SCRAMBLER.is_protocol_supported('HTTP', client):
            return TCP_SCRAMBLER
        if https_enforcer_enabled and HTTPS_ENFORCER.is_protocol_supported('HTTP', client):
            return HTTPS_ENFORCER
        if google_scrambler_enabled and GOOGLE_SCRAMBLER.is_protocol_supported('HTTP', client):
            return GOOGLE_SCRAMBLER
        return HTTP_TRY_PROXY if HTTP_TRY_PROXY.is_protocol_supported('HTTP', client) else None
    finally:
        # one shot
        client.http_proxy_tried = True


def pick_tcp_smuggler(client):
    if not hasattr(client, 'is_payload_complete'): # only parse it once
        client.is_payload_complete = recv_and_parse_request(client)
    if tcp_scrambler_enabled and TCP_SMUGGLER.is_protocol_supported('HTTP', client):
        return TCP_SMUGGLER
    return None


def pick_https_try_proxy(client):
    if client.us_ip_only:
        client.tried_proxies[HTTPS_TRY_PROXY] = 'us ip only'
        return None
    if not direct_access_enabled:
        client.tried_proxies[HTTPS_TRY_PROXY] = 'direct access disabled'
        return None
    return HTTPS_TRY_PROXY if HTTPS_TRY_PROXY.is_protocol_supported('HTTPS', client) else None


def pick_proxy_supports(client, picks_public=None):
    key = (client.dst_ip, client.dst_port)
    preferred_proxy = preferred_proxies.get(key)
    if preferred_proxy and preferred_proxy not in client.tried_proxies:
        return preferred_proxy
    preferred_proxy = _pick_proxy_supports(client, picks_public)
    preferred_proxies[key] = preferred_proxy
    return preferred_proxy

def _pick_proxy_supports(client, picks_public=None):
    supported_proxies = [proxy for proxy in proxies if should_pick(proxy, client, picks_public)]
    if not supported_proxies:
        if False is not picks_public and (goagent_public_servers_enabled or ss_public_servers_enabled):
            gevent.spawn(refresh_proxies)
        return None
    prioritized_proxies = {}
    for proxy in supported_proxies:
        prioritized_proxies.setdefault(proxy.priority, []).append(proxy)
    highest_priority = sorted(prioritized_proxies.keys())[0]
    picked_proxy = random.choice(sorted(prioritized_proxies[highest_priority], key=lambda proxy: proxy.latency)[:3])
    if picked_proxy.latency == 0:
        return random.choice(prioritized_proxies[highest_priority])
    return picked_proxy


def should_pick(proxy, client, picks_public):
    if proxy.died:
        if proxy.auto_relive and time.time() > proxy.die_time + 3:
            proxy.died = False
            return True
        return False
    if client.has_tried(proxy):
        return False
    if not proxy.is_protocol_supported(client.protocol, client):
        return False
    if not china_shortcut_enabled and isinstance(proxy, DynamicProxy):
        return False
    if picks_public is not None:
        is_public = isinstance(proxy, DynamicProxy)
        return is_public == picks_public
    else:
        return True


def refresh_proxies(force=False):
    global proxies
    global last_refresh_started_at
    if not force:
        if last_refresh_started_at == -1: # wait for proxy directories to load
            return False
        if time.time() - last_refresh_started_at < get_refresh_interval():
            return False
    last_refresh_started_at = time.time()
    refresh_timestamps.append(time.time())
    LOGGER.info('refresh proxies: %s' % proxies)
    socks = []
    type_to_proxies = {}
    if https_enforcer_enabled:
        type_to_proxies.setdefault(HTTPS_ENFORCER.__class__, []).append(HTTPS_ENFORCER)
    for proxy in proxies:
        type_to_proxies.setdefault(proxy.__class__, []).append(proxy)
    success = True
    for proxy_type, instances in type_to_proxies.items():
        try:
            success = success and proxy_type.refresh(instances)
        except:
            LOGGER.exception('failed to refresh proxies %s' % instances)
            success = False
    for sock in socks:
        try:
            sock.close()
        except:
            pass
    LOGGER.info('%s, refreshed proxies: %s' % (success, proxies))
    return success


def get_refresh_interval():
    if not refresh_timestamps:
        return 360
    while refresh_timestamps:
        if refresh_timestamps[0] < (time.time() - 30 * 60):
            refresh_timestamps.remove(refresh_timestamps[0])
        else:
            break
    return len(refresh_timestamps) * 30 + 360


def init_private_proxies(config):
    for proxy_id, private_server in config['private_servers'].items():
        try:
            proxy_type = private_server.pop('proxy_type')
            if 'GoAgent' == proxy_type:
                for appid in private_server['appid'].split('|'):
                    if not appid.strip():
                        continue
                    is_rc4_enabled = False
                    is_obfuscate_enabled = False
                    if 'rc4_obfuscate' == private_server.get('goagent_options'):
                        is_rc4_enabled = True
                        is_obfuscate_enabled = True
                    elif 'rc4' == private_server.get('goagent_options'):
                        is_rc4_enabled = True
                        is_obfuscate_enabled = False
                    elif 'obfuscate' == private_server.get('goagent_options'):
                        is_rc4_enabled = False
                        is_obfuscate_enabled = True
                    proxy = GoAgentProxy(
                        appid.strip(), private_server.get('path'),
                        private_server.get('goagent_password'),
                        is_rc4_enabled=is_rc4_enabled,
                        is_obfuscate_enabled=is_obfuscate_enabled,
                        goagent_version=private_server.get('goagent_version') or 'auto')
                    proxy.proxy_id = proxy_id
                    proxies.append(proxy)
            elif 'SSH' == proxy_type:
                for i in range(private_server.get('connections_count') or 4):
                    proxy = SshProxy(
                        private_server['host'], private_server['port'],
                        private_server['username'], private_server.get('password'))
                    proxy.proxy_id = proxy_id
                    proxies.append(proxy)
            elif 'Sock5' == proxy_type:
                proxy = Sock5Proxy(
                    private_server['host'], private_server['port'])
                proxy.proxy_id = proxy_id
                proxies.append(proxy)
            elif 'XXnetGAE' == proxy_type:
                proxy = XXnetGAE()
                proxy.proxy_id = proxy_id
                proxies.append(proxy)
            elif 'Shadowsocks' == proxy_type:
                proxy = ShadowSocksProxy(
                    private_server['host'], private_server['port'],
                    private_server['password'], private_server['encrypt_method'])
                proxy.proxy_id = proxy_id
                proxies.append(proxy)
            elif 'HTTP' == proxy_type:
                is_secured = 'SSL' == private_server.get('transport_type')
                if 'HTTP' in private_server.get('traffic_type'):
                    proxy = HttpRelayProxy(
                        private_server['host'], private_server['port'],
                        private_server['username'], private_server['password'],
                        is_secured=is_secured)
                    proxy.proxy_id = proxy_id
                    proxies.append(proxy)
                if 'HTTPS' in private_server.get('traffic_type'):
                    proxy = HttpConnectProxy(
                        private_server['host'], private_server['port'],
                        private_server['username'], private_server['password'],
                        is_secured=is_secured)
                    proxy.proxy_id = proxy_id
                    proxies.append(proxy)
            elif 'SPDY' == proxy_type:
                from ..proxies.spdy_relay import SpdyRelayProxy
                from ..proxies.spdy_connect import SpdyConnectProxy

                for i in range(private_server.get('connections_count') or 4):
                    if 'HTTP' in private_server.get('traffic_type'):
                        proxy = SpdyRelayProxy(
                            private_server['host'], private_server['port'], 'auto',
                            private_server['username'], private_server['password'])
                        proxy.proxy_id = proxy_id
                        proxies.append(proxy)
                    if 'HTTPS' in private_server.get('traffic_type'):
                        proxy = SpdyConnectProxy(
                            private_server['host'], private_server['port'], 'auto',
                            private_server['username'], private_server['password'])
                        proxy.proxy_id = proxy_id
                        proxies.append(proxy)
            else:
                raise NotImplementedError('proxy type: %s' % proxy_type)
        except:
            LOGGER.exception('failed to init %s' % private_server)


def init_proxies(config):
    global last_refresh_started_at
    last_refresh_started_at = -1
    init_private_proxies(config)
    if tcp_scrambler_enabled:
        TCP_SMUGGLER.try_start_if_network_is_ok()
        TCP_SCRAMBLER.try_start_if_network_is_ok()
    # try:
    #     success = False
    #     for i in range(8):
    #         if load_public_proxies(config['public_servers']):
    #             last_refresh_started_at = 0
    #             if refresh_proxies():
    #                 success = True
    #                 break
    #         retry_interval = math.pow(2, i)
    #         LOGGER.error('refresh failed, will retry %s seconds later' % retry_interval)
    #         gevent.sleep(retry_interval)
    #     if success:
    #         LOGGER.critical('proxies init successfully')
    #         us_ip_cache_file = None
    #         if config['config_file']:
    #             us_ip_cache_file = os.path.join(os.path.dirname(config['config_file']), 'us_ip')
    #         us_ip.load_cache(us_ip_cache_file)
    #         for proxy in proxies:
    #             if isinstance(proxy, DynamicProxy):
    #                 proxy = proxy.delegated_to
    #             if hasattr(proxy, 'proxy_ip'):
    #                 us_ip.is_us_ip(proxy.proxy_ip)
    #         us_ip.save_cache(us_ip_cache_file)
    #     else:
    #         LOGGER.critical('proxies init failed')
    # except:
    #     LOGGER.exception('failed to init proxies')


def load_public_proxies(public_servers):
    '''not available anymore'''
    pass
    # try:
    #     more_proxies = []
    #     results = networking.resolve_txt(public_servers['source'])
    #     for an in results:
    #         priority, proxy_type, count, partial_dns_record = an.text[0].split(':')[:4]
    #         count = int(count)
    #         priority = int(priority)
    #         if public_servers.get('%s_enabled' % proxy_type, True) and proxy_type in proxy_types:
    #             for i in range(count):
    #                 dns_record = '%s.fqrouter.com' % partial_dns_record.replace('#', str(i + 1))
    #                 dynamic_proxy = DynamicProxy(dns_record=dns_record, type=proxy_type, priority=priority)
    #                 if dynamic_proxy not in proxies:
    #                     more_proxies.append(dynamic_proxy)
    #     LOGGER.info('loaded public servers: %s' % more_proxies)
    #     proxies.extend(more_proxies)
    #     return True
    # except:
    #     LOGGER.exception('failed to load proxy from directory')
    #     return False


def clear_proxy_states():
    global last_refresh_started_at
    last_refresh_started_at = 0
    HTTP_TRY_PROXY.timeout = HTTP_TRY_PROXY.INITIAL_TIMEOUT
    HTTP_TRY_PROXY.slow_ip_list.clear()
    HTTP_TRY_PROXY.host_black_list.clear()
    HTTP_TRY_PROXY.host_slow_list.clear()
    HTTP_TRY_PROXY.host_slow_detection_enabled = True
    TCP_SCRAMBLER.bad_requests.clear()
    # http proxies black list
    HTTP_TRY_PROXY.dst_black_list.clear()
    TCP_SCRAMBLER.dst_black_list.clear()
    GOOGLE_SCRAMBLER.dst_black_list.clear()
    HTTPS_ENFORCER.dst_black_list.clear()
    TCP_SMUGGLER.dst_black_list.clear()
    HTTPS_TRY_PROXY.timeout = HTTPS_TRY_PROXY.INITIAL_TIMEOUT
    HTTPS_TRY_PROXY.slow_ip_list.clear()
    HTTPS_TRY_PROXY.dst_black_list.clear()
    ip_substitution.sub_map.clear()
    for proxy in proxies:
        proxy.clear_latency_records()
        proxy.clear_failed_times()
    GoAgentProxy.global_gray_list = set()
    GoAgentProxy.global_black_list = set()
    GoAgentProxy.google_ip_failed_times = {}
    GoAgentProxy.google_ip_latency_records = {}
    stat.counters = []
    preferred_proxies.clear()
    if tcp_scrambler_enabled:
        TCP_SMUGGLER.try_start_if_network_is_ok()
        TCP_SCRAMBLER.try_start_if_network_is_ok()
    if on_clear_states:
        on_clear_states()
