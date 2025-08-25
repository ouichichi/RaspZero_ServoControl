from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import json
import time
import threading
from servo_controller import ServoController
from servo_registry import ServoRegistry, ServoOrientation
from safety_system import SafetySystem, EmergencyMode, SafetyState
from preset_engine import PresetEngine, PresetType, PresetParams
from timeline_system import TimelineEngine, EaseType

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.config['SECRET_KEY'] = 'servo_control_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

print("Starting Raspberry Pi Servo Control Server...")
print("Initializing systems...")

# Initialize all systems
servo_controller = ServoController()
servo_registry = ServoRegistry()
safety_system = SafetySystem(servo_controller, servo_registry)
preset_engine = PresetEngine(servo_controller, servo_registry)
timeline_engine = TimelineEngine(servo_controller, servo_registry)

# Start safety watchdog
safety_system.watchdog_start(timeout_ms=10000)  # 10 second timeout

print("All systems initialized successfully!")
print("Access the web interface at: http://localhost:5000")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    safety_system.watchdog_pet()  # Pet watchdog on API access
    
    return jsonify({
        'servo_registry': servo_registry.get_all_servos(),
        'safety_status': safety_system.get_safety_status(),
        'timeline_status': timeline_engine.get_timeline_status(),
        'running_presets': preset_engine.get_running_presets(),
        'preset_definitions': preset_engine.get_preset_definitions(),
        'system_time': time.time()
    })


# Enhanced API endpoints
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


@app.route('/api/servo/<identifier>/calibrate', methods=['POST'])
def calibrate_servo(identifier):
    data = request.json
    success = servo_registry.calibrate_servo(
        id=identifier,
        min_us=data['min_us'],
        max_us=data['max_us'],
        center_deg=data.get('center_deg', 90.0)
    )
    return jsonify({'success': success})


@app.route('/api/servo/<identifier>/limits', methods=['POST'])
def set_servo_limits(identifier):
    data = request.json
    success = servo_registry.set_soft_limits(
        id=identifier,
        min_deg=data['min_deg'],
        max_deg=data['max_deg']
    )
    return jsonify({'success': success})


@app.route('/api/safety/safe_pose', methods=['POST'])
def go_safe_pose():
    data = request.json
    pose_name = data.get('pose_name')
    success = safety_system.go_safe_pose(pose_name)
    return jsonify({'success': success})


@app.route('/api/safety/preflight', methods=['POST'])
def run_preflight():
    results = safety_system.preflight_check()
    return jsonify(results)


@app.route('/api/preset/<name>/play', methods=['POST'])
def play_preset(name):
    data = request.json or {}
    success = preset_engine.preset_play(
        name=name,
        targets=data.get('targets'),
        rate=data.get('rate', 1.0),
        loop=data.get('loop', True)
    )
    return jsonify({'success': success})


@app.route('/api/preset/<name>/stop', methods=['POST'])
def stop_preset(name):
    success = preset_engine.preset_stop(name)
    return jsonify({'success': success})


@app.route('/api/timeline', methods=['POST'])
def create_timeline():
    data = request.json
    success = timeline_engine.timeline_new(
        name=data['name'],
        fps=data.get('fps'),
        bpm=data.get('bpm'),
        duration_ms=data.get('duration_ms', 10000)
    )
    return jsonify({'success': success})


@app.route('/api/timeline/<name>/play', methods=['POST'])
def play_timeline(name):
    success = timeline_engine.play(name)
    return jsonify({'success': success})


@app.route('/api/timeline/<name>/stop', methods=['POST'])
def stop_timeline(name):
    success = timeline_engine.stop()
    return jsonify({'success': success})


@app.route('/api/timeline/<name>/track', methods=['POST'])
def add_track(name):
    data = request.json
    success = timeline_engine.track_add(
        timeline_name=name,
        track_name=data['track_name'],
        target=data['target']
    )
    return jsonify({'success': success})


@app.route('/api/timeline/<timeline_name>/<track_name>/keyframe', methods=['POST'])
def add_keyframe(timeline_name, track_name):
    data = request.json
    success = timeline_engine.keyframe_add(
        timeline_name=timeline_name,
        track_name=track_name,
        time_ms=data['time_ms'],
        value=data['value'],
        ease=EaseType(data.get('ease', 'linear')),
        tension=data.get('tension', 0.0)
    )
    return jsonify({'success': success})


# WebSocket events
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', {
        'servo_registry': servo_registry.get_all_servos(),
        'safety_status': safety_system.get_safety_status(),
        'timeline_status': timeline_engine.get_timeline_status(),
        'running_presets': preset_engine.get_running_presets()
    })


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('set_servo_angle')
def handle_servo_angle(data):
    safety_system.watchdog_pet()  # Pet watchdog
    
    identifier = data.get('identifier') or data.get('channel')  # Support both ID and channel
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
    safety_system.watchdog_pet()
    
    identifier = data.get('identifier') or data.get('channel')
    servo_meta = servo_registry.resolve_servo(str(identifier))
    
    if servo_meta:
        servo_controller.enable_servo(servo_meta.channel)
        servo_meta.enabled = True
        emit('servo_enabled', {'id': servo_meta.id, 'channel': servo_meta.channel}, broadcast=True)


@socketio.on('disable_servo')
def handle_disable_servo(data):
    safety_system.watchdog_pet()
    
    identifier = data.get('identifier') or data.get('channel')
    servo_meta = servo_registry.resolve_servo(str(identifier))
    
    if servo_meta:
        servo_controller.disable_servo(servo_meta.channel)
        servo_meta.enabled = False
        emit('servo_disabled', {'id': servo_meta.id, 'channel': servo_meta.channel}, broadcast=True)


@socketio.on('emergency_stop')
def handle_emergency_stop(data=None):
    mode = EmergencyMode.SAFE_POSE
    if data and 'mode' in data:
        try:
            mode = EmergencyMode(data['mode'])
        except ValueError:
            pass
    
    success = safety_system.emergency_stop(mode)
    emit('emergency_stop', {
        'message': f'Emergency stop activated - mode: {mode.value}',
        'success': success
    }, broadcast=True)


@socketio.on('register_servo')
def handle_register_servo(data):
    safety_system.watchdog_pet()
    
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


@socketio.on('play_preset')
def handle_play_preset(data):
    safety_system.watchdog_pet()
    
    success = preset_engine.preset_play(
        name=data['name'],
        targets=data.get('targets'),
        rate=data.get('rate', 1.0),
        loop=data.get('loop', True)
    )
    
    emit('preset_status', {
        'name': data['name'],
        'playing': success
    }, broadcast=True)


@socketio.on('timeline_transport')
def handle_timeline_transport(data):
    safety_system.watchdog_pet()
    
    action = data['action']
    timeline_name = data.get('timeline')
    
    if action == 'play':
        success = timeline_engine.play(timeline_name)
    elif action == 'pause':
        success = timeline_engine.pause()
    elif action == 'stop':
        success = timeline_engine.stop()
    elif action == 'scrub':
        success = timeline_engine.scrub(data['time_ms'])
    else:
        success = False
    
    if success:
        emit('timeline_status', timeline_engine.get_timeline_status(), broadcast=True)


# Periodic status updates
def send_status_updates():
    """Send periodic status updates to connected clients"""
    while True:
        try:
            with app.app_context():
                status = {
                    'servo_registry': servo_registry.get_all_servos(),
                    'safety_status': safety_system.get_safety_status(),
                    'timeline_status': timeline_engine.get_timeline_status(),
                    'running_presets': preset_engine.get_running_presets(),
                    'timestamp': time.time()
                }
                socketio.emit('status_update', status)
        except Exception as e:
            print(f"Status update error: {e}")
        
        time.sleep(2.0)  # Update every 2 seconds


# Start status update thread
status_thread = threading.Thread(target=send_status_updates, daemon=True)
status_thread.start()


# Cleanup handler
def cleanup_systems():
    print("Shutting down systems...")
    timeline_engine.cleanup()
    preset_engine.cleanup()
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