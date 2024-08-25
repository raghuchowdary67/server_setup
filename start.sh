#!/bin/bash
#chmod +x start.sh

# Block all outgoing traffic by default
sudo iptables -P OUTPUT DROP

# Allow traffic through the loopback interface
sudo iptables -A OUTPUT -o lo -j ACCEPT

# Allow traffic through the VPN interface (tun0)
sudo iptables -A OUTPUT -o tun0 -j ACCEPT

# Allow DNS queries to the VPN DNS servers (modify with your VPN's DNS IP if needed)
sudo iptables -A OUTPUT -p udp --dport 53 -j ACCEPT

# Path to the credentials file in the $HOME/secrets folder
CREDENTIALS_FILE="$HOME/secrets/surfshark_credentials.txt"

# Start OpenVPN in the background using the credentials file from $HOME/secrets
sudo openvpn --config /etc/openvpn/us-slc.prod.surfshark.com_udp.ovpn --auth-user-pass "$CREDENTIALS_FILE" &

# Wait for OpenVPN to connect
sleep 10

# Check if the VPN interface (tun0) is up
if ip a show dev tun0 > /dev/null 2>&1; then
    echo "VPN connected successfully. Starting Tinyproxy..."
    # Start Tinyproxy in the foreground
    sudo tinyproxy -d
else
    echo "VPN connection failed. Exiting..."
    # If VPN connection fails, exit
    exit 1
fi
