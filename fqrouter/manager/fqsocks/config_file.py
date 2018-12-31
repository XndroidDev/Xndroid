import os
import json
from uuid import uuid4
import shutil
import logging

LOGGER = logging.getLogger(__name__)
DEFAULT_PUBLIC_SERVERS_SOURCE = 'no_available_source!'
current_path = os.path.dirname(os.path.abspath(__file__))
home_path = os.path.abspath(current_path + "/../..")
multi_proxy = True

def DEFAULT_CONFIG():
    return {
        'teredo_server': '',
        'config_file': None,
        'china_shortcut_enabled': True,
        'direct_access_enabled': True,
        'google_scrambler_enabled': False,
        'tcp_scrambler_enabled': False,
        'https_enforcer_enabled': False,
        'access_check_enabled': True,
        'hosted_domain_enabled': False,
        'prefers_private_proxy': True,
        'ipv6_direct_enable' : True,
        'ipv6_direct_try_first' : False,
        'http_manager': {
            'enabled': True,
            'ip': '',
            'port': 2515
        },
        'http_gateway': {
            'enabled': False,
            'ip': '',
            'port': 2516
        },
        'dns_server': {
            'enabled': False,
            'ip': '',
            'port': 12345
        },
        'tcp_gateway': {
            'enabled': False,
            'ip': '',
            'port': 12345
        },
        'wifi_repeater': {
            'ssid': 'fqrouter',
            'chipset': '',
            'password': '12345678'
        },
        'upnp': {
            'port': 25,
            'is_password_protected': False,
            'username': '',
            'password': ''
        },
        'public_servers': {
            'source': DEFAULT_PUBLIC_SERVERS_SOURCE,
            'goagent_enabled': False,
            'ss_enabled': False
        },
        'private_servers': {
            '00000000-eeee-4444-8888-999999999999': {
                "username": "",
                "proxy_type": "HTTP",
                "host": "127.0.0.1",
                "transport_type": "HTTP",
                "traffic_type": "HTTP/HTTPS",
                "password": "",
                "port": 8087,
                "priority": 200,
                "enabled": 1
            }
        }
    }

cli_args = None


def read_config():
    config = _read_config()
    migrate_config(config)
    config['log_level'] = cli_args.log_level
    config['log_file'] = cli_args.log_file
    config['ip_command'] = cli_args.ip_command
    config['ifconfig_command'] = cli_args.ifconfig_command
    config['outbound_ip'] = cli_args.outbound_ip
    config['google_host'] = cli_args.google_host
    for props in cli_args.proxy:
        props = props.split(',')
        prop_dict = dict(p.split('=') for p in props[1:])
        n = int(prop_dict.pop('n', 0))
        add_proxy(config, props[0], n, **prop_dict)
    if cli_args.china_shortcut_enabled is not None:
        config['china_shortcut_enabled'] = cli_args.china_shortcut_enabled
    if cli_args.direct_access_enabled is not None:
        config['direct_access_enabled'] = cli_args.direct_access_enabled
    if cli_args.google_scrambler_enabled is not None:
        config['google_scrambler_enabled'] = cli_args.google_scrambler_enabled
    if cli_args.tcp_scrambler_enabled is not None:
        config['tcp_scrambler_enabled'] = cli_args.tcp_scrambler_enabled
    if cli_args.access_check_enabled is not None:
        config['access_check_enabled'] = cli_args.access_check_enabled
    if cli_args.no_http_manager:
        config['http_manager']['enabled'] = False
    if cli_args.http_manager_listen:
        config['http_manager']['enabled'] = True
        config['http_manager']['ip'], config['http_manager']['port'] = parse_ip_colon_port(cli_args.http_manager_listen)
    if cli_args.http_gateway_listen:
        config['http_gateway']['enabled'] = True
        config['http_gateway']['ip'], config['http_gateway']['port'] = parse_ip_colon_port(cli_args.http_gateway_listen)
    if cli_args.no_dns_server:
        config['dns_server']['enabled'] = False
    if cli_args.dns_server_listen:
        config['dns_server']['enabled'] = True
        config['dns_server']['ip'], config['dns_server']['port'] = parse_ip_colon_port(cli_args.dns_server_listen)
    if cli_args.tcp_gateway_listen:
        config['tcp_gateway']['enabled'] = True
        config['tcp_gateway']['ip'], config['tcp_gateway']['port'] = parse_ip_colon_port(cli_args.tcp_gateway_listen)
    return config


def add_proxy(config, proxy_type, n=0, **kwargs):
    if n:
        for i in range(1, 1 + n):
            private_server = {k: v.replace('#n#', str(i)) for k, v in kwargs.items()}
            private_server['proxy_type'] = proxy_type
            config['private_servers'][str(uuid4())] = private_server
    else:
        kwargs['proxy_type'] = proxy_type
        config['private_servers'][str(uuid4())] = kwargs


def _read_config():
    config = DEFAULT_CONFIG()
    if not cli_args or not hasattr(cli_args, 'config_file'):
        config['config_file'] = home_path + '/etc/fqsocks.json'
    else:
        config['config_file'] = cli_args.config_file
    if os.path.exists(config['config_file']):
        with open(config['config_file']) as f:
            content = f.read()
            if content:
                config.update(json.loads(content))
            return config
    else:
        return config


def migrate_config(config):
    if 'proxies.fqrouter.com' == config['public_servers']['source']:
        config['public_servers']['source'] = DEFAULT_PUBLIC_SERVERS_SOURCE
    if not config['config_file']:
        return
    config_dir = os.path.dirname(config['config_file'])
    migrate_goagent_config(config, config_dir)
    migrate_shadowsocks_config(config, config_dir)
    migrate_http_proxy_config(config, config_dir)
    migrate_ssh_config(config, config_dir)


def migrate_goagent_config(config, config_dir):
    goagent_json_file = os.path.join(config_dir, 'goagent.json')
    if os.path.exists(goagent_json_file):
        try:
            with open(goagent_json_file) as f:
                for server in json.loads(f.read()):
                    add_proxy(config, 'GoAgent', path=server['path'],
                              goagent_password=server['password'], appid=server['appid'])
            with open(cli_args.config_file, 'w') as f:
                f.write(json.dumps(config))
        except:
            LOGGER.exception('failed to migrate goagent config')
        finally:
            shutil.move(goagent_json_file, os.path.join(config_dir, 'goagent.json.bak'))


def migrate_shadowsocks_config(config, config_dir):
    shadowsocks_json_file = os.path.join(config_dir, 'shadowsocks.json')
    if os.path.exists(shadowsocks_json_file):
        try:
            with open(shadowsocks_json_file) as f:
                for server in json.loads(f.read()):
                    add_proxy(config, 'Shadowsocks', host=server['host'],
                              password=server['password'], port=server['port'],
                              encrypt_method=server['encryption_method'])
            with open(cli_args.config_file, 'w') as f:
                f.write(json.dumps(config))
        except:
            LOGGER.exception('failed to migrate shadowsocks config')
        finally:
            shutil.move(shadowsocks_json_file, os.path.join(config_dir, 'shadowsocks.json.bak'))


def migrate_http_proxy_config(config, config_dir):
    http_proxy_json_file = os.path.join(config_dir, 'http-proxy.json')
    if os.path.exists(http_proxy_json_file):
        try:
            with open(http_proxy_json_file) as f:
                for server in json.loads(f.read()):
                    if 'spdy (webvpn)' == server['transport_type']:
                        add_proxy(config, 'SPDY', host=server['host'],
                                  password=server['password'], port=server['port'],
                                  username=server['username'],
                                  traffic_type=server['traffic_type'].upper().replace(' ', ''),
                                  connections_count=server['spdy_connections_count'])
                    else:
                        add_proxy(config, 'HTTP', host=server['host'],
                                  password=server['password'], port=server['port'],
                                  username=server['username'],
                                  transport_type='SSL' if 'ssl' == server['transport_type'] else 'HTTP',
                                  traffic_type=server['traffic_type'].upper().replace(' ', ''))
            with open(cli_args.config_file, 'w') as f:
                f.write(json.dumps(config))
        except:
            LOGGER.exception('failed to migrate http proxy config')
        finally:
            shutil.move(http_proxy_json_file, os.path.join(config_dir, 'http-proxy.json.bak'))


def migrate_ssh_config(config, config_dir):
    ssh_json_file = os.path.join(config_dir, 'ssh.json')
    if os.path.exists(ssh_json_file):
        try:
            with open(ssh_json_file) as f:
                for server in json.loads(f.read()):
                    add_proxy(config, 'SSH', host=server['host'],
                              password=server['password'], port=server['port'],
                              username=server['username'], connections_count=server['connections_count'])
            with open(cli_args.config_file, 'w') as f:
                f.write(json.dumps(config))
        except:
            LOGGER.exception('failed to migrate ssh config')
        finally:
            shutil.move(ssh_json_file, os.path.join(config_dir, 'ssh.json.bak'))


def update_config(apply=None, **kwargs):
    if not cli_args:
        return
    config = _read_config()
    config.update(kwargs)
    if apply:
        apply(config)
    with open(cli_args.config_file, 'w') as f:
        f.write(json.dumps(config))


def parse_ip_colon_port(ip_colon_port):
    if not isinstance(ip_colon_port, basestring):
        return ip_colon_port
    if ':' in ip_colon_port:
        server_ip, server_port = ip_colon_port.split(':')
        server_port = int(server_port)
    else:
        server_ip = ip_colon_port
        server_port = 53
    return '' if '*' == server_ip else server_ip, server_port
