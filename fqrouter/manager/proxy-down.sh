iptables -t filter -D OUTPUT -p tcp -j FQUNI
iptables -t filter -D OUTPUT -p udp -j FQUNI
iptables -t filter -F FQUNI
pkill -f "fquni_client.py"