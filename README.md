# Raspberry Pi Servo Controller

A complete servo control system for Raspberry Pi Zero with PCA9685 board, featuring a modern web interface and real-time WebSocket communication.

## Features

- 🎛️ **16-Channel Control**: Full support for PCA9685 16-channel servo driver
- 🌐 **Web Interface**: Modern, responsive web UI with real-time sliders
- ⚡ **Real-time Communication**: WebSocket-based instant updates
- 📱 **Mobile Friendly**: Responsive design works on all devices
- ⚙️ **Configurable**: Adjustable pulse widths and servo names
- 🛑 **Emergency Stop**: Safety feature to immediately disable all servos
- 📊 **Status Monitoring**: Live connection status and activity logging

## Hardware Requirements

- Raspberry Pi Zero/Zero W/Zero 2W (or any Pi model)
- PCA9685 16-Channel PWM Servo Driver Board
- Up to 16 servo motors
- External power supply for servos (5V recommended)
- Jumper wires for connections

## Wiring Diagram

```
Raspberry Pi    →    PCA9685 Board
GND            →    GND
3.3V           →    VCC
GPIO 2 (SDA)   →    SDA
GPIO 3 (SCL)   →    SCL

PCA9685 Board   →   External Power
V+              →   5V+ (Servo Power)
GND             →   GND (Common Ground)

Servos connect to channels 0-15 on PCA9685 board
```

## Installation

### 1. System Setup

Update your Raspberry Pi system:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git -y
```

Enable I2C interface:
```bash
sudo raspi-config
# Navigate to: Interfacing Options → I2C → Enable
sudo reboot
```

Verify I2C is working:
```bash
sudo i2cdetect -y 1
# Should show device at address 0x40 (default PCA9685 address)
```

### 2. Project Installation

Clone or download the project:
```bash
cd ~
git clone <your-repo-url> pi-servo-control
cd pi-servo-control
```

Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configuration

The system works out of the box, but you can modify settings in `backend/servo_controller.py`:

- **I2C Address**: Default is 0x40, change in `ServoController.__init__()`
- **PWM Frequency**: Default is 50Hz, suitable for most servos
- **Pulse Width Ranges**: Default 750-2250μs, adjustable per servo

## Usage

### Starting the Server

```bash
cd ~/pi-servo-control
source venv/bin/activate
python backend/app.py
```

The server will start on `http://0.0.0.0:5000`

### Accessing the Web Interface

- **Local access**: `http://localhost:5000`
- **Network access**: `http://YOUR_PI_IP:5000`
- **Find Pi IP**: `hostname -I`

### Web Interface Features

#### Main Controls
- **Emergency Stop**: Immediately disable all servos
- **Reset All**: Set all servos to 90° (center position)
- **Enable/Disable All**: Bulk servo control

#### Individual Servo Control
- **Angle Sliders**: Real-time 0-180° control
- **Live Angle Display**: Current servo position
- **Enable/Disable**: Individual servo control
- **Configuration**: Adjust pulse widths and names

#### System Status
- **Connection Status**: WebSocket connection indicator
- **Active Servos**: Count of enabled servos
- **Activity Log**: Real-time event logging

## API Reference

### REST Endpoints

```bash
# Get system status
GET /api/status

# Set servo angle
POST /api/servo/{channel}/angle
Content-Type: application/json
{"angle": 90}

# Update servo configuration
POST /api/servo/{channel}/config
Content-Type: application/json
{
  "name": "Base Rotation",
  "min_pulse": 750,
  "max_pulse": 2250
}

# Emergency stop
POST /api/emergency_stop
```

### WebSocket Events

```javascript
// Client to Server
socket.emit('set_servo_angle', {channel: 0, angle: 90});
socket.emit('emergency_stop');
socket.emit('enable_servo', {channel: 0});
socket.emit('disable_servo', {channel: 0});

// Server to Client
socket.on('servo_update', data => {...});
socket.on('emergency_stop', data => {...});
socket.on('status', data => {...});
```

## Auto-Start Setup

Create a systemd service for automatic startup:

```bash
sudo nano /etc/systemd/system/servo-controller.service
```

Add the following content:
```ini
[Unit]
Description=Raspberry Pi Servo Controller
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/pi-servo-control
Environment=PATH=/home/pi/pi-servo-control/venv/bin
ExecStart=/home/pi/pi-servo-control/venv/bin/python backend/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable servo-controller.service
sudo systemctl start servo-controller.service
```

Check service status:
```bash
sudo systemctl status servo-controller.service
```

## Troubleshooting

### I2C Issues
```bash
# Check I2C is enabled
sudo raspi-config

# Verify device detection
sudo i2cdetect -y 1

# Check I2C permissions
sudo usermod -a -G i2c pi
```

### Python Dependencies
```bash
# If pip install fails, try:
sudo apt install python3-dev libi2c-dev

# For older Pi models, use:
pip install --upgrade pip setuptools wheel
```

### Permission Issues
```bash
# Add user to gpio group
sudo usermod -a -G gpio pi

# Check group membership
groups pi
```

### Web Interface Not Loading
- Check firewall settings: `sudo ufw status`
- Verify server is running: `netstat -tlnp | grep :5000`
- Check logs: `journalctl -u servo-controller.service -f`

### Servo Not Moving
1. **Check Power**: Ensure external 5V supply is connected
2. **Check Wiring**: Verify I2C connections (SDA/SCL)
3. **Check Address**: Confirm PCA9685 address (default 0x40)
4. **Check Pulse Width**: Adjust min/max pulse settings per servo

## Safety Notes

⚠️ **Important Safety Guidelines:**

- Always use external power supply for servos (never power from Pi)
- Connect common ground between Pi and servo power supply
- Use emergency stop if servos behave unexpectedly
- Test individual servos before connecting mechanical loads
- Monitor servo current draw to prevent overheating

## Project Structure

```
pi-servo-control/
├── backend/
│   ├── app.py              # Flask web server & WebSocket handling
│   └── servo_controller.py # PCA9685 servo control logic
├── static/
│   ├── css/
│   │   └── style.css       # Modern UI styling
│   └── js/
│       └── app.js          # WebSocket client & UI logic
├── templates/
│   └── index.html          # Main web interface
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is open source and available under the MIT License.