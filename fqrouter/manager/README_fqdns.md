fqdns
=====

DNS proxy (./fqdns serve):

* anti-GFW: query non-standard port (--upstream 208.67.222.222:5353)
* anti-GFW: pick the right answer, with a list of wrong answers builtin (--strategy pick-right)
* anti-GFW: pick the right answer and favors the later one (--strategy pick-right-later --timeout 1)
* anti-GFW: query private hosted domain google.com => google.com.fqrouter.com (--hosted-domain google.com --hosted-at fqrouter.com --enable-hosted-domain)
* anti-GFW: fallback from udp to tcp when udp not working (--fallback-timeout 3)
* query multiple upstreams, the fastest one wins (--upstream 8.8.8.8 --upstream 8.8.4.4)
* query china domain using china upstreams, with a list of china domains builtin (--china-upstream 114.114.114.114 --china-upstream 114.114.115.115 --enable-china-domain)

DNS client (./fqdns resolve):

* anti-GFW: query non-standard port (--at 208.67.222.222:5353)
* anti-GFW: pick the right answer, with a list of wrong answers builtin (--strategy pick-right)
* anti-GFW: pick the right answer and favors the later one (--strategy pick-right-later --timeout 1)
* anti-GFW: query over tcp (--at 8.8.8.8 --server-type tcp)
* query multiple dns servers, the fastest one wins (--at 8.8.8.8 --at 8.8.4.4)
* query multiple domains at the same time (./fqdns resolve twitter.com facebook.com)
* query txt records (./fqdns resolve proxy1.fqrouter.com --record-type TXT)
* retry multiple times (--retry 3)

Discover GFW Wrong Answers (./fqdns discover)

* query multiple domains (--domain youtube.com --domain plus.google.com)
* repeat multiple times (--repeat 30)
* only discover new wrong answers (--only-new)

Blog Post: http://fqrouter.tumblr.com/post/51783097591/dns


[![Bitdeli Badge](https://d2weczhvl823v0.cloudfront.net/fqrouter/fqdns/trend.png)](https://bitdeli.com/free "Bitdeli Badge")

