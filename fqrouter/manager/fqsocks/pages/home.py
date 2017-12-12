# -*- coding: utf-8 -*-
import httplib
import logging
import os.path
import fqdns
import time
import urllib2

import jinja2


from .. import httpd
from ..gateways import proxy_client
from .. import config_file
from ..gateways import http_gateway
from . import downstream
from .. import networking
from . import upstream
HOME_HTML_FILE = os.path.join(os.path.dirname(__file__), '..', 'templates', 'home.html')
LOGGER = logging.getLogger(__name__)
is_root_mode = 0 == os.getuid()

@httpd.http_handler('GET', '')
@httpd.http_handler('GET', 'home')
def home_page(environ, start_response):
    with open(HOME_HTML_FILE) as f:
        template = jinja2.Template(unicode(f.read(), 'utf8'))
    start_response(httplib.OK, [('Content-Type', 'text/html')])
    # is_root = 0 == os.getuid()
    is_root = is_root_mode
    args = dict(
        _=environ['select_text'],
        domain_name=environ.get('HTTP_HOST') or '127.0.0.1:2515',
        tcp_scrambler_enabled=proxy_client.tcp_scrambler_enabled,
        google_scrambler_enabled=proxy_client.google_scrambler_enabled,
        https_enforcer_enabled=proxy_client.https_enforcer_enabled,
        china_shortcut_enabled=proxy_client.china_shortcut_enabled,
        direct_access_enabled=proxy_client.direct_access_enabled,
        prefers_private_proxy=proxy_client.prefers_private_proxy,
        config=config_file.read_config(),
        is_root=is_root,
        default_interface_ip=networking.get_default_interface_ip(),
        http_gateway=http_gateway,
        httpd=httpd,
        spi_wifi_repeater=downstream.spi_wifi_repeater if is_root else None,
        now=time.time(),
        hosted_domain_enabled=networking.DNS_HANDLER.enable_hosted_domain)
    html = template.render(**args).encode('utf8')
    return [html]


# @httpd.http_handler('GET', 'notice')
# def get_notice_url(environ, start_response):
#     try:
#         domain = environ['select_text']('en.url.notice.fqrouter.com', 'cn.url.notice.fqrouter.com')
#         results = networking.resolve_txt(domain)
#         LOGGER.info('%s => %s' % (domain, results))
#         url = results[0].text[0]
#         start_response(httplib.FOUND, [
#             ('Content-Type', 'text/html'),
#             ('Cache-Control', 'no-cache, no-store, must-revalidate'),
#             ('Pragma', 'no-cache'),
#             ('Expires', '0'),
#             ('Location', url)])
#         return []
#     except:
#         LOGGER.exception('failed to resolve notice url')
#         start_response(httplib.FOUND, [
#             ('Content-Type', 'text/html'),
#             ('Cache-Control', 'no-cache, no-store, must-revalidate'),
#             ('Pragma', 'no-cache'),
#             ('Expires', '0'),
#             ('Location', 'https://s3.amazonaws.com/fqrouter-notice/index.html')])
#         return []
