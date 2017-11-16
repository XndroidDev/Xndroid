import logging
import httplib
import cgi
import os
from gevent.wsgi import WSGIServer

LOGGER = logging.getLogger(__name__)
HANDLERS = {}
server_greenlet = None
LISTEN_IP = None
LISTEN_PORT = None


def handle_request(environ, start_response):
    method = environ.get('REQUEST_METHOD')
    path = environ.get('PATH_INFO', '').strip('/')
    environ['REQUEST_ARGUMENTS'] = cgi.FieldStorage(
        fp=environ['wsgi.input'],
        environ=environ,
        keep_blank_values=True)
    accept_language = environ.get('HTTP_ACCEPT_LANGUAGE', None)
    if accept_language and 'zh' in accept_language:
        environ['select_text'] = select_zh_text
    else:
        environ['select_text'] = select_en_text
    handler = HANDLERS.get((method, path))
    if handler:
        try:
            lines = handler(environ, lambda status, headers: start_response(get_http_response(status), headers))
        except:
            LOGGER.exception('failed to handle request: %s %s' % (method, path))
            raise
    else:
        start_response(get_http_response(httplib.NOT_FOUND), [('Content-Type', 'text/plain')])
        lines = []
    for line in lines:
        yield line


def select_en_text(en_txt, zh_txt):
    return en_txt


def select_zh_text(en_txt, zh_txt):
    return zh_txt


def get_http_response(code):
    return '%s %s' % (code, httplib.responses[code])


def http_handler(method, url):
    def decorator(func):
        HANDLERS[(method, url)] = func
        return func

    return decorator


def serve_forever():
    try:
        server = WSGIServer((LISTEN_IP, LISTEN_PORT), handle_request)
        LOGGER.info('serving HTTP on port %s:%s...' % (LISTEN_IP, LISTEN_PORT))
    except:
        LOGGER.exception('failed to start HTTP server on port %s:%s' % (LISTEN_IP, LISTEN_PORT))
        os._exit(1)
    server.serve_forever()