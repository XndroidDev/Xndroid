import httplib
import json
import fqlan
import logging
import os

import gevent
import jinja2

from .. import httpd


LAN_DEVICES_HTML_FILE = os.path.join(os.path.dirname(__file__), '..', 'templates', 'lan-devices.html')
LOGGER = logging.getLogger(__name__)
scan_greenlet = None
forge_greenlet = None
lan_devices = {}


@httpd.http_handler('POST', 'lan/scan')
def handle_lan_scan(environ, start_response):
    global scan_greenlet
    start_response(httplib.OK, [('Content-Type', 'application/json')])
    was_running = False
    if scan_greenlet is not None:
        if scan_greenlet.ready():
            scan_greenlet = gevent.spawn(lan_scan)
        else:
            was_running = True
    else:
        scan_greenlet = gevent.spawn(lan_scan)
    return [json.dumps({
        'was_running': was_running
    })]


@httpd.http_handler('GET', 'lan/devices')
def lan_devices_page(environ, start_response):
    with open(LAN_DEVICES_HTML_FILE) as f:
        template = jinja2.Template(unicode(f.read(), 'utf8'))
    start_response(httplib.OK, [('Content-Type', 'text/html')])
    is_scan_completed = scan_greenlet.ready() if scan_greenlet is not None else False
    return [template.render(
        _=environ['select_text'], lan_devices=lan_devices,
        is_scan_completed=is_scan_completed).encode('utf8')]


@httpd.http_handler('POST', 'lan/update')
def handle_lan_update(environ, start_response):
    global forge_greenlet
    start_response(httplib.OK, [('Content-Type', 'application/json')])
    ip = environ['REQUEST_ARGUMENTS']['ip'].value
    is_picked = 'true' == environ['REQUEST_ARGUMENTS']['is_picked'].value
    LOGGER.info('update %s %s' % (ip, is_picked))
    if ip not in lan_devices:
        return [json.dumps({'success': False})]
    lan_devices[ip]['is_picked'] = is_picked
    if forge_greenlet:
        forge_greenlet.kill()
    forge_greenlet = gevent.spawn(lan_forge)
    return [json.dumps({'success': True})]


@httpd.http_handler('GET', 'pick-and-play/is-started')
def is_pick_and_play_started(environ, start_response):
    start_response(httplib.OK, [('Content-Type', 'text/plain')])
    is_started = not forge_greenlet.ready() if forge_greenlet is not None else False
    return ['TRUE' if is_started else 'FALSE']


def lan_scan():
    for result in fqlan.scan(mark='0xcafe'):
        ip, mac, hostname = result
        if ip not in lan_devices:
            lan_devices[ip] = {
                'ip': ip,
                'mac': mac,
                'hostname': hostname,
                'is_picked': False
            }


def lan_forge():
    victims = []
    for lan_device in lan_devices.values():
        if lan_device['is_picked']:
            victims.append((lan_device['ip'], lan_device['mac']))
    if victims:
        fqlan.forge(victims)
    else:
        LOGGER.info('no devices picked')