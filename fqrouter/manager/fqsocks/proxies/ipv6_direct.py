import logging
import random
import dpkt
import gevent
from .direct import DirectProxy

# from ... import fqdns
# from ...teredo import ip_buffer_list
import os,sys
sys.path.append('%s/../..' % os.path.dirname(os.path.abspath(__file__)))
import fqdns

LOGGER = logging.getLogger(__name__)

host_path = '/sdcard/ipv6_host'
ipv6_stored_host = {}
ipv6_host = {}
ipv6_fail_domain = {}


if os.path.exists(host_path):
    try:
        with open(host_path) as f:
            ipv6_stored_host = dict([line.rsplit(' ', maxsplit=1) for line in \
                              f.read().splitlines(False) if not line.startswith('#')])
            print 'load %d ipv6 host item' % len(ipv6_stored_host)
    except Exception, e:
        print 'read ipv6 host fail:%s' % repr(e)
        ipv6_stored_host = {}
else:
    print 'ipv6 host file(%s) does not exit' % host_path
    ipv6_stored_host = {}

def save_ipv6_host():
    try:
        ipv6_stored_host.update(ipv6_host)
        with open(host_path, 'w+') as f:
            for domain in ipv6_stored_host:
                f.write('%s %s\n' % (ipv6_stored_host[domain], domain))
            LOGGER.info('saved %d ipv6 host record' % len(ipv6_stored_host))
    except:
        LOGGER.exception('write ipv6 host fail')


class Ipv6DirectProxy(DirectProxy):

    def __init__(self, connect_timeout=4, dns_timeout=4, retry_time=3):
        super(Ipv6DirectProxy, self).__init__(connect_timeout)
        self.dns_timeout = dns_timeout
        self.retry_time = retry_time
        self.dns_server = []
        self.dns_server.append(('tcp', '2001:4860:4860::8888', 53))
        self.dns_server.append(('tcp', '2620:0:ccc::2', 53))
        self.dns_server.append(('tcp', '2620:0:ccd::2', 53))
        self.dns_server.append(('tcp', '2001:4860:4860::8844', 53))
        random.shuffle(self.dns_server)


    def create_upstream_sock(self, client):
        if not client.host:
            LOGGER.error('unknown the host of [%s]' % repr(client))
            raise Exception('ipv6 direct unknown host')
        domain = client.host
        ip6 = self.query_and_record(domain)
        if not ip6:
            raise Exception('ipv6 can not resolve AAAA')
        try:
            sock = client.create_tcp_socket(ip6, client.dst_port, self.connect_timeout)
        except Exception, e:
            LOGGER.debug('ipv6 tcp connect fail for %s(%s)' % (domain, ip6))
            failed_time = ipv6_fail_domain.get(domain, 0)
            failed_time += 1
            if failed_time >= self.retry_time:
                LOGGER.error('ipv6 tcp connect really fail for %s(%s)' % (domain, ip6))
                if domain in ipv6_stored_host:
                    del ipv6_stored_host[domain]
                if domain in ipv6_host:
                    ipv6_fail_domain[domain] = -1
                    del ipv6_host[domain]
                else:
                    if domain in ipv6_fail_domain:
                        del ipv6_fail_domain[domain]
            else:
                ipv6_fail_domain[domain] = failed_time
            raise e
        LOGGER.debug('ipv6 tcp connect to %s(%s) succeed' % (domain, ip6))
        if domain in ipv6_fail_domain:
            del ipv6_fail_domain[domain]
        ipv6_host[domain] = ip6
        return sock



    def is_domain_supported(self, client):
        if not client.host:
            return False
        if client.host in ipv6_host or client.host in ipv6_stored_host:
            return True
        if client.host not in ipv6_fail_domain or ipv6_fail_domain[client.host] != -1:
            gevent.spawn(Ipv6DirectProxy.query_and_record, self, client.host)
        return False


    def query_AAAA(self, domain):
        server, answers = fqdns.resolve_once(dpkt.dns.DNS_AAAA, domain, self.dns_server, self.dns_timeout)
        if len(answers) == 0:
            # LOGGER.debug('query the AAAA record of %s fail' % domain)
            raise Exception('dns resolve AAAA fail')
        return random.choice(answers)


    def query_and_record(self, domain):
        if domain in ipv6_host:
            return ipv6_host[domain]
        if domain in ipv6_stored_host:
            return ipv6_stored_host[domain]
        if domain in ipv6_fail_domain:
            failed_time = ipv6_fail_domain[domain]
            if failed_time == -1:
                return None
        else:
            failed_time = 0
        try:
            ip6 = self.query_AAAA(domain)
        except Exception, e:
            LOGGER.debug('ipv6 query AAAA for %s fail:%s' % (domain, repr(e)))
            failed_time += 1
            if failed_time >= self.retry_time:
                LOGGER.error('ipv6 resolve really fail for %s' % domain)
                ipv6_fail_domain[domain] = -1
            else:
                ipv6_fail_domain[domain] = failed_time
            return None
        LOGGER.debug('ipv6 resolve %s to %s succeed' % (domain, ip6))
        ipv6_host[domain] = ip6
        if domain in ipv6_fail_domain:
            del ipv6_fail_domain[domain]
        return ip6


    def __repr__(self):
        return 'Ipv6DirectProxy'


IPV6_DIRECT_PROXY = Ipv6DirectProxy()
