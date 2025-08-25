# Installation Guide

## Quick Start

### 1. Hardware Setup
Connect your PCA9685 to the Raspberry Pi:
```
Pi GPIO 2 (SDA) → PCA9685 SDA
Pi GPIO 3 (SCL) → PCA9685 SCL  
Pi 3.3V         → PCA9685 VCC
Pi GND          → PCA9685 GND
```

### 2. Enable I2C
```bash
sudo raspi-config
# Navigate to: Advanced Options → I2C → Enable
sudo reboot
```

### 3. Install Project
```bash
git clone <repo-url> pi-servo-control
cd pi-servo-control
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Run Server
```bash
python backend/run.py
```

### 5. Access Web Interface
Open browser to: `http://YOUR_PI_IP:5000`

## Detailed Installation

See README.md for complete installation instructions, wiring diagrams, and troubleshooting.