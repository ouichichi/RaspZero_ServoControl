/**
 * Enhanced Servo Control Studio JavaScript
 * Professional interface with all Phase 1 & 2 features
 */

class ServoControlStudio {
    constructor() {
        this.socket = io();
        this.servos = new Map();
        this.configurations = new Map();
        this.presets = new Map();
        this.timeline = null;
        this.timelineCanvas = null;
        this.timelineContext = null;
        
        this.init();
    }
    
    init() {
        this.setupSocket();
        this.setupEventListeners();
        this.setupTimeline();
        this.loadConfigurations();
        this.updateSystemTime();
        
        // Initialize panel collapse states
        this.initializePanels();
    }
    
    setupSocket() {
        this.socket.on('connect', () => {
            this.updateConnectionStatus(true);
            this.showToast('Connected to server', 'success');
        });
        
        this.socket.on('disconnect', () => {
            this.updateConnectionStatus(false);
            this.showToast('Disconnected from server', 'error');
        });
        
        this.socket.on('status', (data) => {
            this.updateSystemStatus(data);
        });
        
        this.socket.on('status_update', (data) => {
            this.updateSystemStatus(data);
        });
        
        this.socket.on('servo_update', (data) => {
            this.updateServoDisplay(data);
        });
        
        this.socket.on('servo_registered', (data) => {
            this.addServoToInterface(data.servo);
            this.showToast(`Servo "${data.servo.id}" registered`, 'success');
        });
        
        this.socket.on('emergency_stop', (data) => {
            this.showToast('Emergency stop activated!', 'warning');
            this.updateAllServoDisplays();
        });
        
        this.socket.on('error', (data) => {
            this.showToast(data.message, 'error');
        });
        
        this.socket.on('timeline_status', (data) => {
            this.updateTimelineStatus(data);
        });
        
        this.socket.on('preset_status', (data) => {
            this.updatePresetStatus(data);
        });
    }
    
    setupEventListeners() {
        // Emergency stop
        document.getElementById('emergency-stop').addEventListener('click', () => {
            if (confirm('Are you sure you want to activate emergency stop?')) {
                this.socket.emit('emergency_stop');
            }
        });
        
        // Configuration management
        document.getElementById('save-config').addEventListener('click', () => this.showConfigModal('save'));
        document.getElementById('load-config').addEventListener('click', () => this.showConfigModal('load'));
        
        // Add servo
        document.getElementById('add-servo').addEventListener('click', () => this.showAddServoModal());
        document.getElementById('confirm-add-servo').addEventListener('click', () => this.confirmAddServo());
        
        // Safety controls
        document.getElementById('safe-pose').addEventListener('click', () => {
            fetch('/api/safety/safe_pose', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        this.showToast('Moved to safe pose', 'success');
                    } else {
                        this.showToast('Failed to move to safe pose', 'error');
                    }
                });
        });
        
        document.getElementById('preflight-check').addEventListener('click', () => {
            fetch('/api/safety/preflight', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    const status = data.overall_status;
                    const message = `Preflight check: ${status} (${data.errors?.length || 0} errors, ${data.warnings?.length || 0} warnings)`;
                    this.showToast(message, status === 'pass' ? 'success' : 'warning');
                });
        });
        
        // Transport controls
        document.getElementById('play-btn').addEventListener('click', () => this.transportControl('play'));
        document.getElementById('pause-btn').addEventListener('click', () => this.transportControl('pause'));
        document.getElementById('stop-btn').addEventListener('click', () => this.transportControl('stop'));
        document.getElementById('record-btn').addEventListener('click', () => this.transportControl('record'));
        
        // Timeline scrubber
        document.getElementById('timeline-scrubber').addEventListener('input', (e) => {
            const timeMs = parseFloat(e.target.value);
            this.socket.emit('timeline_transport', { action: 'scrub', time_ms: timeMs });
        });
        
        // Configuration modal
        document.getElementById('confirm-config-action').addEventListener('click', () => this.confirmConfigAction());
    }
    
    setupTimeline() {
        this.timelineCanvas = document.getElementById('timeline-canvas');
        this.timelineContext = this.timelineCanvas.getContext('2d');
        
        // Set canvas size
        const resizeCanvas = () => {
            const rect = this.timelineCanvas.parentElement.getBoundingClientRect();
            this.timelineCanvas.width = rect.width;
            this.timelineCanvas.height = rect.height;
            this.drawTimeline();
        };
        
        window.addEventListener('resize', resizeCanvas);
        setTimeout(resizeCanvas, 100);
        
        // Timeline interaction
        this.timelineCanvas.addEventListener('click', (e) => {
            const rect = this.timelineCanvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const timeRatio = x / rect.width;
            const maxTime = 10000; // Default 10 seconds
            const timeMs = timeRatio * maxTime;
            
            this.socket.emit('timeline_transport', { action: 'scrub', time_ms: timeMs });
            document.getElementById('timeline-scrubber').value = timeMs;
        });
    }
    
    initializePanels() {
        // Load panel states from localStorage
        const panelStates = JSON.parse(localStorage.getItem('panelStates') || '{}');
        
        document.querySelectorAll('.panel').forEach(panel => {
            const panelId = panel.id;
            if (panelStates[panelId] === false) {
                panel.classList.add('collapsed');
            }
        });
    }
    
    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connection-status');
        statusEl.className = `connection-status ${connected ? 'connected' : 'disconnected'}`;
        statusEl.innerHTML = `<i class="fas fa-circle"></i><span>${connected ? 'Connected' : 'Disconnected'}</span>`;
    }
    
    updateSystemStatus(data) {
        // Update servo registry
        if (data.servo_registry) {
            this.updateServoRegistry(data.servo_registry);
        }
        
        // Update safety status
        if (data.safety_status) {
            this.updateSafetyStatus(data.safety_status);
        }
        
        // Update timeline status
        if (data.timeline_status) {
            this.updateTimelineStatus(data.timeline_status);
        }
        
        // Update presets
        if (data.preset_definitions) {
            this.updatePresetGrid(data.preset_definitions);
        }
        
        if (data.running_presets) {
            this.updateRunningPresets(data.running_presets);
        }
        
        // Update system status panel
        this.updateSystemStatusPanel(data);
    }
    
    updateServoRegistry(servoData) {
        const servoControls = document.getElementById('servo-controls');
        servoControls.innerHTML = '';
        
        Object.entries(servoData).forEach(([servoId, servo]) => {
            this.servos.set(servoId, servo);
            this.addServoToInterface(servo);
        });
        
        this.updateServoVisualization();
    }
    
    addServoToInterface(servo) {
        const servoControls = document.getElementById('servo-controls');
        
        const servoCard = document.createElement('div');
        servoCard.className = `servo-card ${servo.enabled ? 'active' : ''}`;
        servoCard.id = `servo-card-${servo.id}`;
        
        servoCard.innerHTML = `
            <div class="servo-header">
                <div>
                    <div class="servo-name">${servo.id}</div>
                    <div class="servo-channel">Channel ${servo.channel}</div>
                </div>
                <button class="servo-toggle ${servo.enabled ? 'active' : ''}" data-servo="${servo.id}">
                    ${servo.enabled ? 'Enabled' : 'Disabled'}
                </button>
            </div>
            <div class="servo-control">
                <input type="range" class="servo-slider" 
                       min="${servo.min_deg}" max="${servo.max_deg}" 
                       value="${servo.current_angle}" 
                       data-servo="${servo.id}"
                       ${servo.enabled ? '' : 'disabled'}>
                <div class="servo-angle-display">
                    <div class="servo-angle-value">${servo.current_angle.toFixed(1)}<span class="servo-angle-unit">°</span></div>
                </div>
                <div class="servo-limits">
                    <span>${servo.min_deg}°</span>
                    <span>${servo.max_deg}°</span>
                </div>
            </div>
            <div class="servo-info">
                <small class="text-muted">${servo.notes || 'No notes'}</small>
            </div>
        `;
        
        servoControls.appendChild(servoCard);
        
        // Add event listeners
        const toggle = servoCard.querySelector('.servo-toggle');
        const slider = servoCard.querySelector('.servo-slider');
        
        toggle.addEventListener('click', () => {
            const action = servo.enabled ? 'disable_servo' : 'enable_servo';
            this.socket.emit(action, { identifier: servo.id });
        });
        
        slider.addEventListener('input', (e) => {
            const angle = parseFloat(e.target.value);
            this.socket.emit('set_servo_angle', { identifier: servo.id, angle: angle });
            
            // Update display immediately for responsiveness
            const angleDisplay = servoCard.querySelector('.servo-angle-value');
            angleDisplay.innerHTML = `${angle.toFixed(1)}<span class="servo-angle-unit">°</span>`;
        });
    }
    
    updateServoDisplay(data) {
        const servoCard = document.getElementById(`servo-card-${data.id}`);
        if (!servoCard) return;
        
        const angleDisplay = servoCard.querySelector('.servo-angle-value');
        const slider = servoCard.querySelector('.servo-slider');
        
        if (angleDisplay) {
            angleDisplay.innerHTML = `${data.angle.toFixed(1)}<span class="servo-angle-unit">°</span>`;
        }
        
        if (slider && Math.abs(parseFloat(slider.value) - data.angle) > 0.1) {
            slider.value = data.angle;
        }
        
        // Update servo object
        if (this.servos.has(data.id)) {
            const servo = this.servos.get(data.id);
            servo.current_angle = data.angle;
        }
        
        this.updateServoMeter(data.id, data.angle);
    }
    
    updateServoVisualization() {
        const servoMeters = document.getElementById('servo-meters');
        servoMeters.innerHTML = '';
        
        this.servos.forEach((servo, servoId) => {
            if (!servo.enabled) return;
            
            const meterDiv = document.createElement('div');
            meterDiv.className = 'servo-meter';
            meterDiv.id = `meter-${servoId}`;
            
            const angle = servo.current_angle;
            const range = servo.max_deg - servo.min_deg;
            const percentage = ((angle - servo.min_deg) / range) * 100;
            
            meterDiv.innerHTML = `
                <div class="meter-header">
                    <span class="meter-name">${servo.id}</span>
                    <span class="meter-value">${angle.toFixed(1)}°</span>
                </div>
                <div class="meter-gauge">
                    <div class="meter-fill" style="width: ${percentage}%">
                        <div class="meter-indicator"></div>
                    </div>
                </div>
            `;
            
            servoMeters.appendChild(meterDiv);
        });
    }
    
    updateServoMeter(servoId, angle) {
        const meter = document.getElementById(`meter-${servoId}`);
        if (!meter) return;
        
        const servo = this.servos.get(servoId);
        if (!servo) return;
        
        const range = servo.max_deg - servo.min_deg;
        const percentage = ((angle - servo.min_deg) / range) * 100;
        
        const fill = meter.querySelector('.meter-fill');
        const value = meter.querySelector('.meter-value');
        
        if (fill) fill.style.width = `${percentage}%`;
        if (value) value.textContent = `${angle.toFixed(1)}°`;
    }
    
    updateSafetyStatus(safetyData) {
        document.getElementById('safety-state').textContent = safetyData.current_state || 'Unknown';
        document.getElementById('watchdog-status').textContent = safetyData.watchdog_enabled ? 'Active' : 'Inactive';
    }
    
    updateTimelineStatus(timelineData) {
        const state = timelineData.state || 'stopped';
        const currentTime = timelineData.current_time_ms || 0;
        
        document.getElementById('timeline-state').textContent = state;
        document.getElementById('timeline-status').textContent = state;
        
        // Update time display
        const timeStr = this.formatTime(currentTime);
        document.getElementById('time-display').textContent = timeStr;
        
        // Update scrubber
        document.getElementById('timeline-scrubber').value = currentTime;
        
        // Update transport button states
        this.updateTransportButtons(state);
        
        // Redraw timeline
        this.drawTimeline(currentTime);
    }
    
    updatePresetGrid(presetDefinitions) {
        const presetGrid = document.getElementById('preset-grid');
        presetGrid.innerHTML = '';
        
        Object.entries(presetDefinitions).forEach(([name, preset]) => {
            const presetBtn = document.createElement('div');
            presetBtn.className = 'preset-btn';
            presetBtn.dataset.preset = name;
            
            const icon = this.getPresetIcon(preset.type);
            
            presetBtn.innerHTML = `
                <div class="preset-icon"><i class="fas fa-${icon}"></i></div>
                <div class="preset-name">${name}</div>
            `;
            
            presetBtn.addEventListener('click', () => this.togglePreset(name));
            presetGrid.appendChild(presetBtn);
        });
    }
    
    updateRunningPresets(runningPresets) {
        document.querySelectorAll('.preset-btn').forEach(btn => {
            const presetName = btn.dataset.preset;
            const isRunning = runningPresets.includes(presetName);
            btn.classList.toggle('active', isRunning);
        });
        
        document.getElementById('running-preset-count').textContent = runningPresets.length;
    }
    
    updateSystemStatusPanel(data) {
        if (data.servo_registry) {
            const activeCount = Object.values(data.servo_registry)
                .filter(servo => servo.enabled).length;
            document.getElementById('active-servo-count').textContent = activeCount;
        }
    }
    
    updateSystemTime() {
        const updateTime = () => {
            const now = new Date();
            const timeStr = now.toLocaleTimeString();
            document.getElementById('system-time').textContent = timeStr;
        };
        
        updateTime();
        setInterval(updateTime, 1000);
    }
    
    // Timeline Drawing
    drawTimeline(currentTime = 0) {
        if (!this.timelineContext) return;
        
        const canvas = this.timelineCanvas;
        const ctx = this.timelineContext;
        const width = canvas.width;
        const height = canvas.height;
        
        // Clear canvas
        ctx.fillStyle = '#1E2328';
        ctx.fillRect(0, 0, width, height);
        
        // Draw grid
        ctx.strokeStyle = '#363B42';
        ctx.lineWidth = 1;
        
        // Vertical grid lines (time markers)
        const timeStep = 1000; // 1 second
        const maxTime = 10000; // 10 seconds
        for (let t = 0; t <= maxTime; t += timeStep) {
            const x = (t / maxTime) * width;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
            
            // Time labels
            ctx.fillStyle = '#B8BCC8';
            ctx.font = '10px Arial';
            ctx.fillText(`${t/1000}s`, x + 2, 12);
        }
        
        // Draw playhead
        const playheadX = (currentTime / maxTime) * width;
        ctx.strokeStyle = '#2196F3';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(playheadX, 0);
        ctx.lineTo(playheadX, height);
        ctx.stroke();
        
        // Draw servo tracks (if available)
        this.drawServoTracks();
    }
    
    drawServoTracks() {
        // This would draw keyframe data if available
        // Implementation would depend on timeline data structure
    }
    
    // Transport Controls
    transportControl(action) {
        switch (action) {
            case 'play':
                this.socket.emit('timeline_transport', { action: 'play' });
                break;
            case 'pause':
                this.socket.emit('timeline_transport', { action: 'pause' });
                break;
            case 'stop':
                this.socket.emit('timeline_transport', { action: 'stop' });
                break;
            case 'record':
                // Implement recording logic
                this.showToast('Recording not yet implemented', 'info');
                break;
        }
    }
    
    updateTransportButtons(state) {
        const playBtn = document.getElementById('play-btn');
        const pauseBtn = document.getElementById('pause-btn');
        const stopBtn = document.getElementById('stop-btn');
        const recordBtn = document.getElementById('record-btn');
        
        // Reset all states
        [playBtn, pauseBtn, stopBtn, recordBtn].forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Set active state
        switch (state) {
            case 'playing':
                playBtn.classList.add('active');
                break;
            case 'paused':
                pauseBtn.classList.add('active');
                break;
            case 'recording':
                recordBtn.classList.add('active');
                break;
        }
    }
    
    // Preset Management
    togglePreset(presetName) {
        const btn = document.querySelector(`[data-preset="${presetName}"]`);
        const isActive = btn.classList.contains('active');
        
        if (isActive) {
            // Stop preset
            fetch(`/api/preset/${presetName}/stop`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        btn.classList.remove('active');
                        this.showToast(`Stopped preset "${presetName}"`, 'info');
                    }
                });
        } else {
            // Start preset
            const enabledServos = Array.from(this.servos.values())
                .filter(servo => servo.enabled)
                .map(servo => servo.id);
            
            fetch(`/api/preset/${presetName}/play`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ targets: enabledServos })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    btn.classList.add('active');
                    this.showToast(`Started preset "${presetName}"`, 'success');
                }
            });
        }
    }
    
    // Modal Management
    showAddServoModal() {
        // Populate available channels
        const channelSelect = document.getElementById('servo-channel');
        channelSelect.innerHTML = '';
        
        const usedChannels = new Set(Array.from(this.servos.values()).map(s => s.channel));
        
        for (let i = 0; i < 16; i++) {
            if (!usedChannels.has(i)) {
                const option = document.createElement('option');
                option.value = i;
                option.textContent = `Channel ${i}`;
                channelSelect.appendChild(option);
            }
        }
        
        this.showModal('add-servo-modal');
    }
    
    confirmAddServo() {
        const servoData = {
            id: document.getElementById('servo-id').value,
            channel: parseInt(document.getElementById('servo-channel').value),
            pin: document.getElementById('servo-pin').value || null,
            orientation: document.getElementById('servo-orientation').value,
            notes: document.getElementById('servo-notes').value
        };
        
        if (!servoData.id) {
            this.showToast('Please enter a servo ID', 'error');
            return;
        }
        
        this.socket.emit('register_servo', servoData);
        this.closeModal('add-servo-modal');
        
        // Clear form
        document.getElementById('servo-id').value = '';
        document.getElementById('servo-pin').value = '';
        document.getElementById('servo-notes').value = '';
    }
    
    showConfigModal(action) {
        const modal = document.getElementById('config-modal');
        const title = document.getElementById('config-modal-title');
        const button = document.getElementById('confirm-config-action');
        
        if (action === 'save') {
            title.innerHTML = '<i class="fas fa-save"></i> Save Configuration';
            button.textContent = 'Save';
            button.dataset.action = 'save';
        } else {
            title.innerHTML = '<i class="fas fa-upload"></i> Load Configuration';
            button.textContent = 'Load';
            button.dataset.action = 'load';
        }
        
        this.loadConfigurationList();
        this.showModal('config-modal');
    }
    
    confirmConfigAction() {
        const action = document.getElementById('confirm-config-action').dataset.action;
        const configName = document.getElementById('config-name').value;
        
        if (!configName && action === 'save') {
            this.showToast('Please enter a configuration name', 'error');
            return;
        }
        
        if (action === 'save') {
            this.saveConfiguration(configName);
        } else {
            this.loadConfiguration(configName);
        }
        
        this.closeModal('config-modal');
    }
    
    // Configuration Management
    saveConfiguration(name) {
        const config = {
            name: name,
            timestamp: Date.now(),
            servos: Object.fromEntries(this.servos)
        };
        
        this.configurations.set(name, config);
        localStorage.setItem('servoConfigurations', JSON.stringify(Object.fromEntries(this.configurations)));
        
        this.showToast(`Configuration "${name}" saved`, 'success');
    }
    
    loadConfiguration(name) {
        const config = this.configurations.get(name);
        if (!config) {
            this.showToast(`Configuration "${name}" not found`, 'error');
            return;
        }
        
        // This would need to register servos with the backend
        this.showToast(`Loading configuration "${name}" not yet fully implemented`, 'info');
    }
    
    loadConfigurations() {
        const saved = localStorage.getItem('servoConfigurations');
        if (saved) {
            const configs = JSON.parse(saved);
            this.configurations = new Map(Object.entries(configs));
        }
    }
    
    loadConfigurationList() {
        const configList = document.getElementById('config-list');
        configList.innerHTML = '';
        
        this.configurations.forEach((config, name) => {
            const configItem = document.createElement('div');
            configItem.className = 'config-item';
            configItem.innerHTML = `
                <strong>${name}</strong>
                <small>${new Date(config.timestamp).toLocaleString()}</small>
            `;
            configItem.addEventListener('click', () => {
                document.getElementById('config-name').value = name;
            });
            configList.appendChild(configItem);
        });
    }
    
    // Utility Functions
    showModal(modalId) {
        document.getElementById(modalId).classList.add('show');
    }
    
    closeModal(modalId) {
        document.getElementById(modalId).classList.remove('show');
    }
    
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        }[type] || 'info-circle';
        
        toast.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <span>${message}</span>
        `;
        
        document.getElementById('toast-container').appendChild(toast);
        
        setTimeout(() => toast.remove(), 5000);
    }
    
    formatTime(ms) {
        const totalSeconds = Math.floor(ms / 1000);
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        const milliseconds = Math.floor((ms % 1000) / 10);
        
        return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}:${milliseconds.toString().padStart(2, '0')}`;
    }
    
    getPresetIcon(presetType) {
        const icons = {
            sine: 'wave-square',
            pingpong: 'arrows-alt-h',
            bounce: 'basketball-ball',
            random_walk: 'random',
            breath: 'lungs',
            twitch: 'bolt',
            ripple: 'water',
            swarm: 'bees'
        };
        return icons[presetType] || 'play';
    }
}

// Panel Toggle Functionality
function togglePanel(panelId) {
    const panel = document.getElementById(panelId);
    panel.classList.toggle('collapsed');
    
    // Save panel states
    const panelStates = JSON.parse(localStorage.getItem('panelStates') || '{}');
    panelStates[panelId] = !panel.classList.contains('collapsed');
    localStorage.setItem('panelStates', JSON.stringify(panelStates));
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.servoStudio = new ServoControlStudio();
});