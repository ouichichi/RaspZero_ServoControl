class ServoController {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.servos = new Map();
        this.emergencyStop = false;
        
        this.init();
    }
    
    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.generateServoControls();
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.socket = io();
        
        this.socket.on('connect', () => {
            this.connected = true;
            this.updateConnectionStatus(true);
            this.log('✅ Connected to server');
            this.socket.emit('get_status');
        });
        
        this.socket.on('disconnect', () => {
            this.connected = false;
            this.updateConnectionStatus(false);
            this.log('❌ Disconnected from server');
        });
        
        this.socket.on('status', (data) => {
            this.updateServoStatus(data);
        });
        
        this.socket.on('servo_update', (data) => {
            this.handleServoUpdate(data);
        });
        
        this.socket.on('emergency_stop', (data) => {
            this.handleEmergencyStop(data);
        });
        
        this.socket.on('servo_enabled', (data) => {
            this.handleServoEnabled(data);
        });
        
        this.socket.on('servo_disabled', (data) => {
            this.handleServoDisabled(data);
        });
        
        this.socket.on('error', (data) => {
            this.log(`❌ Error: ${data.message}`);
        });
        
        this.socket.on('connect_error', (error) => {
            this.log(`❌ Connection error: ${error.message}`);
        });
    }
    
    setupEventListeners() {
        document.getElementById('emergencyBtn').addEventListener('click', () => {
            this.emergencyStop();
        });
        
        document.getElementById('resetAllBtn').addEventListener('click', () => {
            this.resetAllServos();
        });
        
        document.getElementById('enableAllBtn').addEventListener('click', () => {
            this.enableAllServos();
        });
        
        document.getElementById('disableAllBtn').addEventListener('click', () => {
            this.disableAllServos();
        });
    }
    
    generateServoControls() {
        const servoGrid = document.getElementById('servoGrid');
        servoGrid.innerHTML = '';
        
        for (let i = 0; i < 16; i++) {
            const servoCard = this.createServoCard(i);
            servoGrid.appendChild(servoCard);
        }
    }
    
    createServoCard(channel) {
        const card = document.createElement('div');
        card.className = 'card servo-card';
        card.id = `servo-${channel}`;
        
        card.innerHTML = `
            <div class="servo-header">
                <div class="servo-title">Servo ${channel}</div>
                <div class="servo-channel">CH ${channel}</div>
            </div>
            
            <div class="servo-controls">
                <div class="angle-display" id="angle-${channel}">90°</div>
                <input type="range" 
                       class="slider" 
                       id="slider-${channel}"
                       min="0" 
                       max="180" 
                       value="90"
                       oninput="servoController.setServoAngle(${channel}, this.value)">
                
                <div class="servo-actions">
                    <button class="btn btn-small" onclick="servoController.toggleServo(${channel})">
                        <span id="toggle-text-${channel}">Disable</span>
                    </button>
                    <button class="btn btn-small btn-secondary" onclick="servoController.openConfigModal(${channel})">
                        ⚙️ Config
                    </button>
                </div>
            </div>
        `;
        
        return card;
    }
    
    setServoAngle(channel, angle) {
        if (this.emergencyStop) {
            this.log(`❌ Cannot control servo ${channel}: Emergency stop active`);
            return;
        }
        
        const angleValue = parseInt(angle);
        document.getElementById(`angle-${channel}`).textContent = `${angleValue}°`;
        
        this.socket.emit('set_servo_angle', {
            channel: channel,
            angle: angleValue
        });
    }
    
    toggleServo(channel) {
        const servo = this.servos.get(channel);
        if (servo && servo.active) {
            this.socket.emit('disable_servo', { channel: channel });
        } else {
            this.socket.emit('enable_servo', { channel: channel });
        }
    }
    
    emergencyStop() {
        this.socket.emit('emergency_stop');
    }
    
    resetAllServos() {
        for (let i = 0; i < 16; i++) {
            this.setServoAngle(i, 90);
            document.getElementById(`slider-${i}`).value = 90;
        }
        this.log('🔄 All servos reset to 90°');
    }
    
    enableAllServos() {
        for (let i = 0; i < 16; i++) {
            this.socket.emit('enable_servo', { channel: i });
        }
        this.log('✅ All servos enabled');
    }
    
    disableAllServos() {
        for (let i = 0; i < 16; i++) {
            this.socket.emit('disable_servo', { channel: i });
        }
        this.log('❌ All servos disabled');
    }
    
    updateConnectionStatus(connected) {
        const indicator = document.getElementById('connectionStatus');
        const statusText = document.getElementById('statusText');
        const systemStatus = document.getElementById('systemStatus');
        
        if (connected) {
            indicator.classList.add('connected');
            statusText.textContent = 'Connected';
            systemStatus.textContent = 'Online';
            systemStatus.className = 'status-ok';
        } else {
            indicator.classList.remove('connected');
            statusText.textContent = 'Disconnected';
            systemStatus.textContent = 'Offline';
            systemStatus.className = 'status-error';
        }
        
        this.updateLastUpdate();
    }
    
    updateServoStatus(data) {
        if (data.servos) {
            let activeCount = 0;
            
            data.servos.forEach(servo => {
                this.servos.set(servo.channel, servo);
                
                if (servo.active) {
                    activeCount++;
                    document.getElementById(`servo-${servo.channel}`).classList.remove('disabled');
                    document.getElementById(`toggle-text-${servo.channel}`).textContent = 'Disable';
                } else {
                    document.getElementById(`servo-${servo.channel}`).classList.add('disabled');
                    document.getElementById(`toggle-text-${servo.channel}`).textContent = 'Enable';
                }
                
                document.getElementById(`angle-${servo.channel}`).textContent = `${Math.round(servo.angle)}°`;
                document.getElementById(`slider-${servo.channel}`).value = servo.angle;
            });
            
            document.getElementById('activeServos').textContent = `${activeCount}/16`;
        }
        
        this.updateLastUpdate();
    }
    
    handleServoUpdate(data) {
        const servo = this.servos.get(data.channel) || {};
        servo.angle = data.angle;
        this.servos.set(data.channel, servo);
        
        document.getElementById(`angle-${data.channel}`).textContent = `${Math.round(data.angle)}°`;
        document.getElementById(`slider-${data.channel}`).value = data.angle;
        
        this.updateLastUpdate();
        this.log(`🎛️ Servo ${data.channel}: ${Math.round(data.angle)}°`);
    }
    
    handleEmergencyStop(data) {
        this.emergencyStop = true;
        document.getElementById('systemStatus').textContent = 'Emergency Stop';
        document.getElementById('systemStatus').className = 'status-error';
        
        // Disable all sliders
        for (let i = 0; i < 16; i++) {
            document.getElementById(`slider-${i}`).disabled = true;
            document.getElementById(`servo-${i}`).classList.add('disabled');
        }
        
        this.log('🛑 EMERGENCY STOP ACTIVATED');
        
        // Re-enable after 3 seconds
        setTimeout(() => {
            this.emergencyStop = false;
            document.getElementById('systemStatus').textContent = 'Normal';
            document.getElementById('systemStatus').className = 'status-ok';
            
            for (let i = 0; i < 16; i++) {
                document.getElementById(`slider-${i}`).disabled = false;
            }
            
            this.log('✅ Emergency stop cleared');
        }, 3000);
    }
    
    handleServoEnabled(data) {
        document.getElementById(`servo-${data.channel}`).classList.remove('disabled');
        document.getElementById(`toggle-text-${data.channel}`).textContent = 'Disable';
        this.log(`✅ Servo ${data.channel} enabled`);
    }
    
    handleServoDisabled(data) {
        document.getElementById(`servo-${data.channel}`).classList.add('disabled');
        document.getElementById(`toggle-text-${data.channel}`).textContent = 'Enable';
        this.log(`❌ Servo ${data.channel} disabled`);
    }
    
    openConfigModal(channel) {
        document.getElementById('configServoChannel').textContent = channel;
        document.getElementById('configModal').style.display = 'block';
        
        const servo = this.servos.get(channel);
        if (servo) {
            document.getElementById('servoName').value = servo.name || `Servo ${channel}`;
            document.getElementById('minPulse').value = servo.min_pulse || 750;
            document.getElementById('maxPulse').value = servo.max_pulse || 2250;
        }
    }
    
    saveServoConfig() {
        const channel = parseInt(document.getElementById('configServoChannel').textContent);
        const name = document.getElementById('servoName').value;
        const minPulse = parseInt(document.getElementById('minPulse').value);
        const maxPulse = parseInt(document.getElementById('maxPulse').value);
        
        fetch(`/api/servo/${channel}/config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: name,
                min_pulse: minPulse,
                max_pulse: maxPulse
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.log(`⚙️ Servo ${channel} configuration updated`);
                closeConfigModal();
            } else {
                this.log(`❌ Failed to update servo ${channel} config: ${data.error}`);
            }
        })
        .catch(error => {
            this.log(`❌ Error updating servo config: ${error.message}`);
        });
    }
    
    updateLastUpdate() {
        const now = new Date();
        const timeString = now.toLocaleTimeString();
        document.getElementById('lastUpdate').textContent = timeString;
    }
    
    log(message) {
        const logArea = document.getElementById('logArea');
        const now = new Date();
        const timestamp = now.toLocaleTimeString();
        
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.innerHTML = `<span class="log-timestamp">[${timestamp}]</span> ${message}`;
        
        logArea.appendChild(logEntry);
        logArea.scrollTop = logArea.scrollHeight;
        
        // Keep only last 100 log entries
        while (logArea.children.length > 100) {
            logArea.removeChild(logArea.firstChild);
        }
    }
}

// Global functions
function closeConfigModal() {
    document.getElementById('configModal').style.display = 'none';
}

function saveServoConfig() {
    servoController.saveServoConfig();
}

function clearLog() {
    document.getElementById('logArea').innerHTML = '';
}

// Initialize the controller when page loads
let servoController;
document.addEventListener('DOMContentLoaded', () => {
    servoController = new ServoController();
});

// Close modal when clicking outside
window.addEventListener('click', (event) => {
    const modal = document.getElementById('configModal');
    if (event.target === modal) {
        closeConfigModal();
    }
});