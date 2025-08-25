#!/bin/bash
# Quick WiFi Network Configuration Helper

echo "📶 Servo Control - WiFi Network Setup"
echo "====================================="

# Function to add WiFi network
add_network() {
    echo ""
    read -p "Network Name (SSID): " ssid
    read -s -p "Password: " password
    echo ""
    read -p "Priority (1-10, higher = preferred): " priority
    
    # Backup original file
    sudo cp /etc/wpa_supplicant/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf.backup
    
    # Add network to wpa_supplicant
    sudo tee -a /etc/wpa_supplicant/wpa_supplicant.conf << EOF

network={
    ssid="$ssid"
    psk="$password"
    priority=$priority
}
EOF
    
    echo "✅ Added network: $ssid (priority: $priority)"
}

# Function to show current networks
show_networks() {
    echo ""
    echo "📋 Currently configured networks:"
    echo "================================"
    if [ -f /etc/wpa_supplicant/wpa_supplicant.conf ]; then
        grep -A 4 "network={" /etc/wpa_supplicant/wpa_supplicant.conf | grep -E "(ssid|priority)" | sed 's/^[ \t]*//'
    else
        echo "No networks configured yet."
    fi
}

# Function to scan available networks
scan_networks() {
    echo ""
    echo "🔍 Scanning for available networks..."
    sudo iwlist wlan0 scan | grep -E "(ESSID|Quality|Encryption)" | grep -A 2 "ESSID" | head -20
}

# Main menu
while true; do
    echo ""
    echo "Choose an option:"
    echo "1) Add new WiFi network"
    echo "2) Show configured networks"  
    echo "3) Scan available networks"
    echo "4) Test connection"
    echo "5) Exit"
    echo ""
    read -p "Enter choice (1-5): " choice
    
    case $choice in
        1)
            add_network
            echo ""
            read -p "Restart WiFi now? (y/n): " restart
            if [[ $restart =~ ^[Yy]$ ]]; then
                sudo systemctl restart wpa_supplicant
                sleep 3
                echo "Current IP: $(hostname -I)"
            fi
            ;;
        2)
            show_networks
            ;;
        3)
            scan_networks
            ;;
        4)
            echo ""
            echo "🔄 Testing connection..."
            sudo systemctl restart wpa_supplicant
            sleep 5
            if ip route | grep default > /dev/null; then
                echo "✅ Connected! IP: $(hostname -I)"
                echo "   Access servo control: http://$(hostname -I | cut -d' ' -f1):5000"
            else
                echo "❌ No connection. Try adding your network or use AP mode."
            fi
            ;;
        5)
            echo "👋 Done!"
            exit 0
            ;;
        *)
            echo "❌ Invalid choice"
            ;;
    esac
done