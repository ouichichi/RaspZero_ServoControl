from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import json
import time
import threading
from servo_controller import ServoController
from servo_registry import ServoRegistry, ServoOrientation
from safety_system import SafetySystem, EmergencyMode, SafetyState

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.config['SECRET_KEY'] = 'servo_control_secret'
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

print("Starting Raspberry Pi Servo Control Server...")
print("Initializing systems...")

# Initialize systems
servo_controller = ServoController()
servo_registry = ServoRegistry()
safety_system = SafetySystem(servo_controller, servo_registry)

# Disabled watchdog for stability testing
# safety_system.watchdog_start(timeout_ms=30000)

print("All systems initialized successfully!")
print("Access the web interface at: http://localhost:5000")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    return jsonify({
        'servo_registry': servo_registry.get_all_servos(),
        'safety_status': safety_system.get_safety_status(),
        'system_time': time.time()
    })


@app.route('/api/servo/register', methods=['POST'])
def register_servo():
    data = request.json
    success = servo_registry.register_servo(
        id=data['id'],
        channel=data['channel'],
        pin=data.get('pin'),
        orientation=ServoOrientation(data.get('orientation', 'normal')),
        gear_ratio=data.get('gear_ratio', 1.0),
        notes=data.get('notes', '')
    )
    return jsonify({'success': success})


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', {
        'servo_registry': servo_registry.get_all_servos(),
        'safety_status': safety_system.get_safety_status()
    })


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('set_servo_angle')
def handle_servo_angle(data):
    identifier = data.get('identifier') or data.get('channel')
    angle = data['angle']
    
    # Resolve servo
    servo_meta = servo_registry.resolve_servo(str(identifier))
    if not servo_meta:
        emit('error', {'message': f'Servo "{identifier}" not found'})
        return
    
    # Apply safety checks
    safe_angle = servo_registry.clamp_angle(servo_meta.id, angle)
    oriented_angle = servo_registry.apply_orientation(servo_meta.id, safe_angle)
    
    # Set servo angle
    if servo_controller.set_servo_angle(servo_meta.channel, oriented_angle):
        servo_meta.current_angle = safe_angle
        servo_meta.target_angle = safe_angle
        
        emit('servo_update', {
            'id': servo_meta.id,
            'channel': servo_meta.channel,
            'angle': safe_angle,
            'success': True
        }, broadcast=True)
    else:
        emit('error', {'message': f'Failed to set servo "{servo_meta.id}" to {angle}°'})


@socketio.on('enable_servo')
def handle_enable_servo(data):
    identifier = data.get('identifier') or data.get('channel')
    servo_meta = servo_registry.resolve_servo(str(identifier))
    
    if servo_meta:
        servo_controller.enable_servo(servo_meta.channel)
        servo_meta.enabled = True
        emit('servo_enabled', {'id': servo_meta.id, 'channel': servo_meta.channel}, broadcast=True)


@socketio.on('disable_servo')
def handle_disable_servo(data):
    identifier = data.get('identifier') or data.get('channel')
    servo_meta = servo_registry.resolve_servo(str(identifier))
    
    if servo_meta:
        servo_controller.disable_servo(servo_meta.channel)
        servo_meta.enabled = False
        emit('servo_disabled', {'id': servo_meta.id, 'channel': servo_meta.channel}, broadcast=True)


@socketio.on('emergency_stop')
def handle_emergency_stop(data=None):
    success = safety_system.emergency_stop(EmergencyMode.SAFE_POSE)
    emit('emergency_stop', {
        'message': 'Emergency stop activated',
        'success': success
    }, broadcast=True)


@socketio.on('register_servo')
def handle_register_servo(data):
    success = servo_registry.register_servo(
        id=data['id'],
        channel=data['channel'],
        pin=data.get('pin'),
        orientation=ServoOrientation(data.get('orientation', 'normal')),
        gear_ratio=data.get('gear_ratio', 1.0),
        notes=data.get('notes', '')
    )
    
    if success:
        emit('servo_registered', {
            'servo': servo_registry.get_servo_info(data['id'])
        }, broadcast=True)
    else:
        emit('error', {'message': f'Failed to register servo {data["id"]}'})


# Cleanup handler
def cleanup_systems():
    print("Shutting down systems...")
    safety_system.cleanup()
    servo_controller.cleanup()


import atexit
atexit.register(cleanup_systems)


if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        cleanup_systems()