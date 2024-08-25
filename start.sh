#!/bin/bash
#chmod +x start.sh

# Block all outgoing traffic by default
iptables -P OUTPUT DROP

# Allow traffic through the loopback interface
iptables -A OUTPUT -o lo -j ACCEPT

# Allow traffic through the VPN interface (tun0)
iptables -A OUTPUT -o tun0 -j ACCEPT

# Allow DNS queries to the VPN DNS servers (modify with your VPN's DNS IP if needed)
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT

# Allow UDP traffic for VPN connection
iptables -A OUTPUT -p udp --dport 1194 -j ACCEPT

# Path to the credentials file in the $HOME/secrets folder (mounted via Docker Compose)
CREDENTIALS_FILE="/secrets/surfshark_credentials.txt"
OVPN_FILE="/vpn-servers/us-dal.prod.surfshark.com_udp.ovpn"

# Start OpenVPN in the background using the credentials file from /secrets
openvpn --config "$OVPN_FILE" --auth-user-pass "$CREDENTIALS_FILE" &

# Wait for OpenVPN to connect
sleep 10

# Check if the VPN interface (tun0) is up
if ip a show dev tun0 > /dev/null 2>&1; then
    echo "VPN connected successfully. Starting Tinyproxy..."
    # Start Tinyproxy in the foreground
    tinyproxy -d
else
    echo "VPN connection failed. Exiting..."
    # If VPN connection fails, exit
    exit 1
fi
