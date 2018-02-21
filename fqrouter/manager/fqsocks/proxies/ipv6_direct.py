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
from teredo import ip_buffer_list

LOGGER = logging.getLogger(__name__)



class Ipv6DirectProxy(DirectProxy):

    def __init__(self, connect_timeout=4, dns_timeout=4, retry_time=3):
        super(Ipv6DirectProxy, self).__init__(connect_timeout)
        self.dns_timeout = dns_timeout
        self.retry_time = retry_time
        self.AAAA_record_list = ip_buffer_list(20, 256)
        self.dns_server = []
        self.dns_server.append(('tcp', '2001:4860:4860::8888', 53))
        self.dns_server.append(('tcp', '2620:0:ccc::2', 53))
        self.dns_server.append(('tcp', '2620:0:ccd::2', 53))
        self.dns_server.append(('tcp', '2001:4860:4860::8844', 53))
        random.shuffle(self.dns_server)


    def create_upstream_sock(self, client):
        if not client.host:
            LOGGER.error('unknow the host of [%s]' % repr(client))
            raise Exception('ipv6 direct unknow host')
        record = self.AAAA_record_list.find(client.host)
        return self.query_connect(client, record)


    def is_domain_supported(self, client):
        if not client.host:
            return False
        record = self.AAAA_record_list.find(client.host)
        if record and isinstance(record['ipv6'], basestring):
            return True
        if not record or record['ipv6'] != -1:
            gevent.spawn(Ipv6DirectProxy.query_silent, self, client, record)
        return False


    def query_AAAA(self, domain):
        server, answers = fqdns.resolve_once(dpkt.dns.DNS_AAAA, domain, self.dns_server, self.dns_timeout)
        if len(answers) == 0:
            # LOGGER.debug('query the AAAA record of %s fail' % domain)
            raise Exception('dns resolve AAAA fail')
        return random.choice(answers)


    def query_silent(self, client, record):
        try:
            self.query_connect(client, record, True)
        except:
            pass


    def query_connect(self, client, record=None, only_query=False):
        if record:
            ipv6 = record['ipv6']
            if isinstance(ipv6, basestring):
                if not only_query:
                    return client.create_tcp_socket(ipv6, client.dst_port, self.connect_timeout)
                else:
                    return ipv6
            tryed_time = ipv6
        else:
            tryed_time = 0
        if not client.host:
            LOGGER.error('unknow the host of [%s]' % repr(client))
            raise Exception('ipv6 direct unknow host')
        domain = client.host
        if tryed_time == -1:
            raise Exception('ipv6 direct really fail')
        try:
            ipv6 = self.query_AAAA(domain)
            if not only_query:
                sock = client.create_tcp_socket(ipv6, client.dst_port, self.connect_timeout)
            else:
                sock = None
        except Exception, e:
            LOGGER.debug('query (and connect) for %s fail:%s' % (domain, str(e)))
            if not record:
                self.AAAA_record_list.append({'id':domain, 'ipv6': 1})
            elif tryed_time + 1 >= self.retry_time:
                LOGGER.error('ipv6 direct really fail for %s' % domain)
                record['ipv6'] = -1
            else:
                record['ipv6'] = tryed_time + 1
            raise e

        LOGGER.debug('ipv6 direct resolve %s to %s succeed' % (domain, ipv6))
        if not record:
            self.AAAA_record_list.append({'id':client.host, 'ipv6':ipv6})
        else:
            record['ipv6'] = ipv6
        if not only_query:
            return sock
        else:
            return ipv6


    def __repr__(self):
        return 'Ipv6DirectProxy'


IPV6_DIRECT_PROXY = Ipv6DirectProxy()
