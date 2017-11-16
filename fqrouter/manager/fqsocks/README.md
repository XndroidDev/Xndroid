Motivation
==========

* improve speed and lower the cost by per-connection proxy selection, only if GFW jammed us we fallback to proxy for just that connection
* improve reliability by fall back from a pool of proxies
* improve speed by using a pool of proxies in a load balanced way

So, fqsocks is a transparent socks redirector, just like http://darkk.net.ru/redsocks/

* redirect tcp traffic to fqsocks using iptables, fqsocks will select upstream and proxy for the tcp connection
* goagent proxy (--proxy goagent,appid=abcd), ripped out from original goagent client
* http-connect proxy (--proxy http-connect,proxy_ip=1.2.3.4,proxy_port=8080)
* dynamic proxy (--proxy dynamic,type=goagent,dns_record=goagent1.fqrouter.com), change the proxy via dns

Unique Features
===============

* detect the traffic protocol (HTTP/HTTPS), not just based on port
* for http, the first request/response will be tried with proxy, if anything goes wrong fallback to another proxy.
so, it is effective against GFW full text filtering.
the page http://zh.wikipedia.org/zh/防火长城‎ is a typical example of full text filtering (the url does not trigger to RST)
* for https, socket connect and full ssl handshake will be tried, if anything goes wrong (https certificate filtering for example), fallback to another proxy.
* built-in support goagent as proxy, without starting an seperate goagent process
* resolve proxy info from TXT dns record

Basic Usage
===========

* start fqsocks: ./fqsocks.py --outbound-ip 10.1.2.3 --listen *:1984
* redirect tcp traffic: iptables -t nat -I OUTPUT -p tcp -j REDIRECT --to-ports 1984
* key issue: how to avoid fqsocks outbound being redirected by iptables again?
* answer is outbound from 10.1.2.3 and masquerade from it: iptables -t nat -I POSTROUTING -s 10.1.2.3 -j MASQUERADE
* 10.1.2.3 is a lo alias: ifconfig lo:1 10.1.2.3 netmask 255.255.255.255

Alternatively, you can use --mark or --owner module to distinguish the fqsocks outbound traffic from others.
But use outbound ip is the most portable way, especially for android.

Proxy Selection Logic
=====================

* china ip: go directly
* dport is 80 or protocol is http: direct => http only proxy => http/https proxy
* dport is 443 or protocol is https: direct => https proxy
* direct connection failed will blacklist that ip:port for 1 minute
* blacklisted ip:port will use proxy


[![Bitdeli Badge](https://d2weczhvl823v0.cloudfront.net/fqrouter/fqsocks/trend.png)](https://bitdeli.com/free "Bitdeli Badge")

