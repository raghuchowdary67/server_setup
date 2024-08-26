#!/bin/bash
#chmod +x start.sh

# Set up DNS to ensure VPN DNS is used instead of Docker DNS
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf

# Block all outgoing traffic by default
iptables -P OUTPUT DROP

# Allow traffic through the loopback interface
iptables -A OUTPUT -o lo -j ACCEPT

# Allow traffic through the VPN interface (tun0)
iptables -A OUTPUT -o tun0 -j ACCEPT

# Allow DNS queries to the VPN DNS servers
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# Allow UDP traffic for VPN connection
iptables -A OUTPUT -p udp --dport 1194 -j ACCEPT

# Path to the credentials file in the /secrets folder (mounted via Docker Compose)
CREDENTIALS_FILE="/secrets/surfshark_credentials.txt"
OVPN_FILE="/vpn-servers/us-dal.prod.surfshark.com_udp.ovpn"

# Start OpenVPN in the background using the credentials file
openvpn --config "$OVPN_FILE" --auth-user-pass "$CREDENTIALS_FILE" &

# Save the OpenVPN process ID
VPN_PID=$!

# Wait for OpenVPN to connect
sleep 10

# Check if the VPN interface (tun0) is up
if ip a show dev tun0 > /dev/null 2>&1; then
    echo "VPN connected successfully. Starting Tinyproxy..."

    # Configure Tinyproxy to route traffic directly, but fail if the VPN is down
    cat <<EOF >> /etc/tinyproxy/tinyproxy.conf

# No upstream proxy for any domain or network
upstream none "."
EOF

    # Start Tinyproxy in the foreground
    tinyproxy -d &

    # Monitor VPN connection
    while kill -0 $VPN_PID 2> /dev/null; do
        if ! ip a show dev tun0 > /dev/null 2>&1; then
            echo "VPN connection lost. Blocking all traffic..."
            iptables -P OUTPUT DROP
        fi
        sleep 5
    done

    echo "VPN process exited. Blocking all traffic..."
    iptables -P OUTPUT DROP
    exit 1
else
    echo "VPN connection failed. Exiting..."
    exit 1
fi
