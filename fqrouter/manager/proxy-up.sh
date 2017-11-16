iptables -t filter -F FQUNI
iptables -t filter -N FQUNI
iptables -t filter -A FQUNI -d 0.0.0.0/8 -j RETURN
iptables -t filter -A FQUNI -d 10.0.0.0/8 -j RETURN
iptables -t filter -A FQUNI -d 127.0.0.0/8 -j RETURN
iptables -t filter -A FQUNI -d 169.254.0.0/16 -j RETURN
iptables -t filter -A FQUNI -d 172.16.0.0/12 -j RETURN
iptables -t filter -A FQUNI -d 192.168.0.0/16 -j RETURN
iptables -t filter -A FQUNI -d 224.0.0.0/4 -j RETURN
iptables -t filter -A FQUNI -d 240.0.0.0/4 -j RETURN
iptables -t filter -A FQUNI -p tcp -j NFQUEUE --queue-num 0
iptables -t filter -A FQUNI -p udp -j NFQUEUE --queue-num 0
iptables -t filter -I OUTPUT -p tcp -j FQUNI
iptables -t filter -I OUTPUT -p udp -j FQUNI
iptables -t filter -D INPUT -p icmp --icmp-type 11 -j DROP
iptables -t filter -I INPUT -p icmp --icmp-type 11 -j DROP
python fquni_client.py $1:19842 > /tmp/fquni.log 2>&1 &