# -*- coding: utf-8 -*-
import time
import logging

# This module is discarded. And it's reserved for compatibility

LOGGER = logging.getLogger(__name__)

counters = []

MAX_TIME_RANGE = 60 * 10

def opened(attached_to_resource, proxy, host, ip):
    if hasattr(proxy, 'resolved_by_dynamic_proxy'):
        proxy = proxy.resolved_by_dynamic_proxy
    return Counter(proxy, host, ip)


def clean_counters():
    # discarded
    global counters
    counters = []


def find_expired_counters():
    # discarded
    return []


class Counter(object):
    def __init__(self, proxy, host, ip):
        self.proxy = proxy
        self.host = host
        self.ip = ip
        self.opened_at = time.time()
        self.closed_at = None
        self.events = []

    def sending(self, bytes_count):
        self.proxy.tx_bytes += bytes_count


    def received(self, bytes_count):
        self.proxy.rx_bytes += bytes_count

    def total_rx(self, after=0):
        # discarded
        return 0, 0, 0

    def total_tx(self, after=0):
        # discarded
        return 0, 0, 0

    def close(self):
        pass

    def __str__(self):
        proxy = self.proxy
        return '[%s] tx:%sB rx:%sB, last_time:%s tx:%sB rx:%sB' % (
            proxy.__repr__(), proxy.tx_bytes, proxy.rx_bytes,
            proxy.last_record_time, proxy.last_tx, proxy.last_rx)

