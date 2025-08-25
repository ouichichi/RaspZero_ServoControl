#!/bin/bash
# Portable Setup Script for Servo Control System
# Enables multiple connectivity options for field deployment

echo "🔧 Servo Control Portable Setup"
echo "================================"

# Function to setup WiFi Access Point mode
setup_ap_mode() {
    echo "📡 Setting up Access Point mode..."
    
    # Install required packages
    sudo apt update
    sudo apt install hostapd dnsmasq -y
    
    # Stop services
    sudo systemctl stop hostapd
    sudo systemctl stop dnsmasq
    
    # Configure static IP for AP
    sudo tee /etc/dhcpcd.conf.ap << EOF
interface wlan0
static ip_address=192.168.4.1/24
nohook wpa_supplicant
EOF
    
    # Configure hostapd
    sudo tee /etc/hostapd/hostapd.conf << EOF
interface=wlan0
driver=nl80211
ssid=ServoControl-$(hostname)
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=servocontrol123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF
    
    # Configure dnsmasq
    sudo tee /etc/dnsmasq.conf.ap << EOF
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
EOF
    
    echo "✅ Access Point configured!"
    echo "   SSID: ServoControl-$(hostname)"
    echo "   Password: servocontrol123" 
    echo "   IP: http://192.168.4.1:5000"
}

# Function to setup WiFi client mode
setup_client_mode() {
    echo "📶 Setting up WiFi client mode..."
    
    # Restore original dhcpcd.conf
    if [ -f /etc/dhcpcd.conf.orig ]; then
        sudo cp /etc/dhcpcd.conf.orig /etc/dhcpcd.conf
    fi
    
    # Configure wpa_supplicant for multiple networks
    sudo tee -a /etc/wpa_supplicant/wpa_supplicant.conf << EOF

# Home network
network={
    ssid="YOUR_HOME_WIFI"
    psk="YOUR_HOME_PASSWORD"
    priority=10
}

# Phone hotspot
network={
    ssid="YOUR_PHONE_HOTSPOT"
    psk="YOUR_PHONE_PASSWORD"
    priority=5
}

# Backup network
network={
    ssid="BACKUP_WIFI"
    psk="BACKUP_PASSWORD"
    priority=1
}
EOF
    
    echo "✅ Client mode configured!"
    echo "   Edit /etc/wpa_supplicant/wpa_supplicant.conf with your WiFi credentials"
}

# Function to create mode switching scripts
create_switch_scripts() {
    echo "🔄 Creating mode switching scripts..."
    
    # AP Mode script
    sudo tee /usr/local/bin/servo-ap-mode << 'EOF'
#!/bin/bash
echo "Switching to Access Point mode..."
sudo cp /etc/dhcpcd.conf.ap /etc/dhcpcd.conf
sudo cp /etc/dnsmasq.conf.ap /etc/dnsmasq.conf
sudo systemctl stop wpa_supplicant
sudo systemctl start hostapd
sudo systemctl start dnsmasq
sudo systemctl restart dhcpcd
echo "✅ AP Mode active - Connect to ServoControl-$(hostname)"
echo "   Password: servocontrol123"
echo "   Web interface: http://192.168.4.1:5000"
EOF
    
    # Client Mode script  
    sudo tee /usr/local/bin/servo-client-mode << 'EOF'
#!/bin/bash
echo "Switching to Client mode..."
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq
if [ -f /etc/dhcpcd.conf.orig ]; then
    sudo cp /etc/dhcpcd.conf.orig /etc/dhcpcd.conf
fi
sudo systemctl restart dhcpcd
sudo systemctl start wpa_supplicant
echo "✅ Client Mode active - Connecting to WiFi..."
sleep 5
echo "IP Address: $(hostname -I)"
EOF
    
    # Make scripts executable
    sudo chmod +x /usr/local/bin/servo-ap-mode
    sudo chmod +x /usr/local/bin/servo-client-mode
    
    echo "✅ Mode switching scripts created!"
    echo "   Switch to AP: sudo servo-ap-mode"
    echo "   Switch to Client: sudo servo-client-mode"
}

# Function to setup boot mode selection
setup_boot_selection() {
    echo "🚀 Setting up boot mode selection..."
    
    # Backup original dhcpcd.conf
    if [ ! -f /etc/dhcpcd.conf.orig ]; then
        sudo cp /etc/dhcpcd.conf /etc/dhcpcd.conf.orig
    fi
    
    # Create boot script that tries client mode first, falls back to AP
    sudo tee /etc/rc.local << 'EOF'
#!/bin/bash
# Auto-detect network and choose mode

echo "🔧 Servo Control Auto-Network Setup"

# Try to connect to known WiFi networks
timeout 30 sudo systemctl restart wpa_supplicant
sleep 10

# Check if we got an IP address
if ip route | grep default > /dev/null; then
    echo "✅ Connected to WiFi network"
    IP=$(hostname -I | cut -d' ' -f1)
    echo "   Access servo control at: http://$IP:5000"
else
    echo "❌ No WiFi connection, starting Access Point mode"
    /usr/local/bin/servo-ap-mode
fi

# Start servo control service
cd /home/pi/RaspZero_ServoControl
sudo -u pi /home/pi/RaspZero_ServoControl/venv/bin/python backend/app.py &

exit 0
EOF
    
    sudo chmod +x /etc/rc.local
    
    echo "✅ Auto-mode detection configured!"
}

# Function to create troubleshooting tools
create_troubleshooting_tools() {
    echo "🔍 Creating troubleshooting tools..."
    
    # Network diagnostic script
    sudo tee /usr/local/bin/servo-network-info << 'EOF'
#!/bin/bash
echo "🔍 Servo Control Network Diagnostics"
echo "===================================="
echo "Hostname: $(hostname)"
echo "IP Addresses: $(hostname -I)"
echo ""
echo "WiFi Status:"
iwconfig wlan0 2>/dev/null | grep -E "(ESSID|Mode|Frequency|Access Point)"
echo ""
echo "Network Interfaces:"
ip addr show | grep -E "(inet |wlan|eth)"
echo ""
echo "Active Services:"
systemctl is-active hostapd dnsmasq wpa_supplicant
echo ""
echo "Web Interface URLs:"
for ip in $(hostname -I); do
    echo "  http://$ip:5000"
done
echo "  http://192.168.4.1:5000 (if in AP mode)"
EOF
    
    sudo chmod +x /usr/local/bin/servo-network-info
    
    # Quick status script
    sudo tee /usr/local/bin/servo-status << 'EOF'
#!/bin/bash
echo "🎛️ Servo Control System Status"
echo "============================="
/usr/local/bin/servo-network-info
echo ""
echo "Servo Service Status:"
if pgrep -f "backend/app.py" > /dev/null; then
    echo "✅ Servo control service is running"
else
    echo "❌ Servo control service is NOT running"
    echo "   Start with: cd ~/RaspZero_ServoControl && source venv/bin/activate && python backend/app.py"
fi
echo ""
echo "I2C Status:"
if i2cdetect -y 1 | grep -q "40"; then
    echo "✅ PCA9685 detected at 0x40"
else
    echo "❌ PCA9685 not detected - check wiring"
fi
EOF
    
    sudo chmod +x /usr/local/bin/servo-status
    
    echo "✅ Troubleshooting tools created!"
    echo "   Network info: sudo servo-network-info"
    echo "   System status: sudo servo-status"
}

# Main menu
echo "Choose setup option:"
echo "1) Full portable setup (recommended)"
echo "2) Access Point mode only"
echo "3) WiFi client mode only" 
echo "4) Create switching scripts only"
echo "5) Troubleshooting tools only"
echo ""
read -p "Enter choice (1-5): " choice

case $choice in
    1)
        setup_ap_mode
        setup_client_mode
        create_switch_scripts
        setup_boot_selection
        create_troubleshooting_tools
        echo ""
        echo "🎉 Full portable setup complete!"
        echo ""
        echo "📋 Quick Reference:"
        echo "   • Auto-detects WiFi on boot, falls back to AP mode"
        echo "   • AP Mode: sudo servo-ap-mode"  
        echo "   • Client Mode: sudo servo-client-mode"
        echo "   • Status Check: sudo servo-status"
        echo "   • Network Info: sudo servo-network-info"
        echo ""
        echo "🔧 Next Steps:"
        echo "   1. Edit WiFi credentials in /etc/wpa_supplicant/wpa_supplicant.conf"
        echo "   2. Reboot to test: sudo reboot"
        ;;
    2)
        setup_ap_mode
        create_switch_scripts
        ;;
    3)
        setup_client_mode
        ;;
    4)
        create_switch_scripts
        ;;
    5)
        create_troubleshooting_tools
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Setup complete! Reboot recommended."