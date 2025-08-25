# 🔧 Portable Troubleshooting Guide

## Quick Solutions for Field Deployment

### **🚨 Emergency Access Methods**

#### **1. Phone Hotspot (Fastest)**
1. Enable hotspot on your phone
2. Connect Pi to your hotspot network  
3. Find Pi IP: Check hotspot client list
4. Access: `http://PI_IP:5000`

#### **2. Direct Ethernet (Most Reliable)**  
1. Connect Pi to laptop via Ethernet cable
2. Enable internet sharing on laptop
3. Pi gets IP automatically (usually 192.168.x.x)
4. Check Pi IP: `arp -a` on laptop

#### **3. Access Point Mode (Independent)**
Run the portable setup script:
```bash
cd ~/RaspZero_ServoControl/scripts
chmod +x portable_setup.sh
sudo ./portable_setup.sh
```
- Choose option 1 (Full portable setup)
- Pi becomes WiFi hotspot: **"ServoControl-[hostname]"**
- Password: **"servocontrol123"** 
- Access: **http://192.168.4.1:5000**

---

## **🔍 Diagnostic Commands**

### **Network Status**
```bash
# Check all network info
sudo servo-network-info

# Check servo system status
sudo servo-status

# Manual IP check
hostname -I
```

### **WiFi Troubleshooting**
```bash
# Check WiFi connection
iwconfig wlan0

# Restart WiFi
sudo systemctl restart wpa_supplicant

# Check available networks  
sudo iwlist wlan0 scan | grep ESSID
```

### **Service Management**
```bash
# Check if servo service is running
pgrep -f "backend/app.py"

# Start servo service manually
cd ~/RaspZero_ServoControl
source venv/bin/activate  
python backend/app.py

# Check system services
sudo systemctl status hostapd dnsmasq wpa_supplicant
```

---

## **⚡ Quick Mode Switching**

After running portable setup:

```bash
# Switch to Access Point mode (creates hotspot)
sudo servo-ap-mode

# Switch to WiFi Client mode (connects to networks)
sudo servo-client-mode

# Check current network status
sudo servo-network-info
```

---

## **🌐 Connection Priority Order**

The system tries connections in this order:

1. **Known WiFi networks** (home, office, etc.)
2. **Phone hotspot** (if configured)  
3. **Access Point mode** (fallback - creates own hotspot)

---

## **📱 Mobile Workflow**

### **Option A: Use Phone Hotspot**
1. Enable hotspot on phone
2. Pi connects automatically (if pre-configured)
3. Control servos through phone browser

### **Option B: Connect to Pi Hotspot**  
1. Pi creates hotspot automatically if no WiFi found
2. Connect phone to "ServoControl-[name]" network
3. Open browser: `http://192.168.4.1:5000`

---

## **🔧 Common Issues & Fixes**

### **"Can't connect to Pi"**
```bash
# Check Pi is powered and booted (LED activity)
# Wait 2-3 minutes for full boot

# Try all possible IPs:
http://raspberry.local:5000
http://raspberrypi.local:5000  
http://192.168.4.1:5000        # AP mode
http://192.168.1.xxx:5000      # Your router range
```

### **"Servo control not working"**
```bash
# Check hardware connections
sudo i2cdetect -y 1    # Should show 40

# Restart servo service
cd ~/RaspZero_ServoControl
source venv/bin/activate
python backend/app.py
```

### **"WiFi not connecting"**  
```bash
# Check credentials
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf

# Force AP mode
sudo servo-ap-mode

# Restart network  
sudo systemctl restart dhcpcd
```

---

## **🎒 Portable Kit Checklist**

### **Essential Items**
- ✅ Raspberry Pi with SD card
- ✅ Power bank (5V, 2A minimum)
- ✅ Ethernet cable (backup connection)
- ✅ USB-to-Ethernet adapter (if needed)
- ✅ Phone with hotspot capability

### **Optional Items**
- ✅ Portable monitor + HDMI cable
- ✅ USB keyboard (for direct Pi access)
- ✅ SD card backup (emergency restore)

---

## **🚀 Pre-Deployment Checklist**

### **Before Leaving Home**
1. ✅ Test all connections (WiFi, AP mode, Ethernet)
2. ✅ Verify servo control works on all interfaces
3. ✅ Configure phone hotspot as backup network
4. ✅ Charge power bank and devices
5. ✅ Test portable setup script

### **At New Location**
1. ✅ Power on Pi and wait for boot
2. ✅ Check connection: `sudo servo-network-info`
3. ✅ If no connection: `sudo servo-ap-mode`
4. ✅ Test servo control interface
5. ✅ Run preflight check in safety panel

---

## **📞 Emergency Recovery**

If all else fails:

1. **Direct HDMI connection** to monitor
2. **USB keyboard** for direct control
3. **Reset network**: `sudo systemctl restart networking`
4. **Manual service start**: `cd ~/RaspZero_ServoControl && python backend/app.py`
5. **Factory reset**: Restore SD card backup

---

## **💡 Pro Tips**

- **Pre-configure multiple WiFi networks** in wpa_supplicant.conf
- **Use memorable AP password** for easy field access
- **Test everything before important demos**
- **Keep SD card backup** for quick recovery
- **Document local network details** (IP ranges, passwords)
- **Use QR codes** for easy WiFi sharing with team members