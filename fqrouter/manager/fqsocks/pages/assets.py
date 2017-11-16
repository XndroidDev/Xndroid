# -*- coding: utf-8 -*-
import httplib
import os.path
import functools
from .. import httpd

ASSETS_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets')

def get_asset(file_path, content_type, environ, start_response):
    start_response(httplib.OK, [('Content-Type', content_type)])
    with open(file_path) as f:
        return [f.read()]


httpd.HANDLERS[('GET', 'assets/bootstrap/css/bootstrap.css')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'bootstrap', 'css', 'bootstrap.css'), 'text/css')

httpd.HANDLERS[('GET', 'assets/bootstrap/css/bootstrap-theme.css')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'bootstrap', 'css', 'bootstrap-theme.css'), 'text/css')

httpd.HANDLERS[('GET', 'assets/bootstrap/fonts/glyphicons-halflings-regular.eot')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'bootstrap', 'fonts', 'glyphicons-halflings-regular.eot'),
    'application/vnd.ms-fontobject')

httpd.HANDLERS[('GET', 'assets/bootstrap/fonts/glyphicons-halflings-regular.ttf')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'bootstrap', 'fonts', 'glyphicons-halflings-regular.ttf'), 'font/ttf')

httpd.HANDLERS[('GET', 'assets/bootstrap/fonts/glyphicons-halflings-regular.svg')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'bootstrap', 'fonts', 'glyphicons-halflings-regular.svg'), 'image/svg+xml')

httpd.HANDLERS[('GET', 'assets/bootstrap/fonts/glyphicons-halflings-regular.woff')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'bootstrap', 'fonts', 'glyphicons-halflings-regular.woff'), 'font/x-woff')

httpd.HANDLERS[('GET', 'assets/bootstrap/js/bootstrap.js')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'bootstrap', 'js', 'bootstrap.js'), 'text/javascript')

httpd.HANDLERS[('GET', 'assets/jquery.min.js')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'jquery.min.js'), 'text/javascript')

httpd.HANDLERS[('GET', 'assets/tablesort.min.js')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'tablesort.min.js'), 'text/javascript')

httpd.HANDLERS[('GET', 'assets/visibility.core.js')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'visibility.core.js'), 'text/javascript')

httpd.HANDLERS[('GET', 'assets/visibility.timer.js')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'visibility.timer.js'), 'text/javascript')

httpd.HANDLERS[('GET', 'assets/masonry.pkgd.min.js')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'masonry.pkgd.min.js'), 'text/javascript')

httpd.HANDLERS[('GET', 'assets/bootbox.min.js')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'bootbox.min.js'), 'text/javascript')

httpd.HANDLERS[('GET', 'assets/bootstrap-switch.css')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'bootstrap-switch.css'), 'text/css')

httpd.HANDLERS[('GET', 'assets/bootstrap-switch.js')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'bootstrap-switch.js'), 'text/javascript')

httpd.HANDLERS[('GET', 'assets/busy-indicator.gif')] = functools.partial(
    get_asset, os.path.join(ASSETS_DIR, 'busy-indicator.gif'), 'image/gif')