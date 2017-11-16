# -*- coding: utf-8 -*-
import time
import logging

LOGGER = logging.getLogger(__name__)

counters = [] # not closed or closed within 5 minutes

MAX_TIME_RANGE = 60 * 10

def opened(attached_to_resource, proxy, host, ip):
    if hasattr(proxy, 'resolved_by_dynamic_proxy'):
        proxy = proxy.resolved_by_dynamic_proxy
    counter = Counter(proxy, host, ip)
    orig_close = attached_to_resource.close

    def new_close():
        try:
            orig_close()
        finally:
            counter.close()

    attached_to_resource.close = new_close
    if '127.0.0.1' != counter.ip:
        counters.append(counter)
    clean_counters()
    return counter


def clean_counters():
    global counters
    try:
        expired_counters = find_expired_counters()
        for counter in expired_counters:
            counters.remove(counter)
    except:
        LOGGER.exception('failed to clean counters')
        counters = []


def find_expired_counters():
    now = time.time()
    expired_counters = []
    for counter in counters:
        counter_time = counter.closed_at or counter.opened_at
        if now - counter_time > MAX_TIME_RANGE:
            expired_counters.append(counter)
        else:
            return expired_counters
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
        self.events.append(('tx', time.time(), bytes_count))


    def received(self, bytes_count):
        self.events.append(('rx', time.time(), bytes_count))

    def total_rx(self, after=0):
        if not self.events:
            return 0, 0, 0
        bytes = 0
        seconds = 0
        last_event_time = self.opened_at
        for event_type, event_time, event_bytes in self.events:
            if event_time > after and 'rx' == event_type:
                seconds += (event_time - last_event_time)
                bytes += event_bytes
            last_event_time = event_time
        if not bytes:
            return 0, 0, 0
        return bytes, seconds, bytes / (seconds * 1000)

    def total_tx(self, after=0):
        if not self.events:
            return 0, 0, 0
        bytes = 0
        seconds = 0
        pending_tx_events = []
        for event_type, event_time, event_bytes in self.events:
            if event_time > after:
                if 'tx' == event_type:
                    pending_tx_events.append((event_time, event_bytes))
                else:
                    if pending_tx_events:
                        seconds += (event_time - pending_tx_events[-1][0])
                        bytes += sum(b for _, b in pending_tx_events)
                    pending_tx_events = []
        if pending_tx_events:
            seconds += ((self.closed_at or time.time()) - pending_tx_events[0][0])
            bytes += sum(b for _, b in pending_tx_events)
        if not bytes:
            return 0, 0, 0
        return bytes, seconds, bytes / (seconds * 1000)

    def close(self):
        if not self.closed_at:
            self.closed_at = time.time()

    def __str__(self):
        rx_bytes, rx_seconds, rx_speed = self.total_rx()
        tx_bytes, tx_seconds, tx_speed = self.total_tx()
        return '[%s~%s] %s%s via %s rx %0.2fKB/s(%s/%s) tx %0.2fKB/s(%s/%s)' % (
            self.opened_at, self.closed_at or '',
            self.ip, '(%s)' % self.host if self.host else '', self.proxy,
            rx_speed, rx_bytes, rx_seconds,
            tx_speed, tx_bytes, tx_seconds)