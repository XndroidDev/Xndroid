import logging
import os
import shell

current_path = os.path.dirname(os.path.abspath(__file__))
home_path = os.path.abspath(current_path + "/..")
LOGGER = logging.getLogger(__name__)

def get_default_dns_server():
    try:
        default_dns_server = shell.check_output(['getprop', 'net.dns1']).strip()
        if default_dns_server:
            return default_dns_server
        else:
            return ''
    except:
        LOGGER.exception('failed to get default dns server')
        return ''

def configure_fqsocks(args):
    args += ['--config-file', home_path + '/etc/fqsocks.json']
    args += ['--ip-command', home_path + '/../busybox']
    args += ['--ifconfig-command', home_path + '/../busybox']
    # args += ['--google-host', 'goagent-google-ip.fqrouter.com']
    # args += ['--google-host', 'goagent-google-ip2.fqrouter.com']
    return args
