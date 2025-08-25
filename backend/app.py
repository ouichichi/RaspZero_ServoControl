from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import json
import threading
import time
from servo_controller import ServoController

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.config['SECRET_KEY'] = 'servo-control-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

servo_controller = ServoController()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    return jsonify(servo_controller.get_all_servos_status())


@app.route('/api/servo/<int:channel>/angle', methods=['POST'])
def set_servo_angle(channel):
    try:
        data = request.get_json()
        angle = float(data.get('angle', 90))
        
        if servo_controller.set_servo_angle(channel, angle):
            socketio.emit('servo_update', {
                'channel': channel,
                'angle': angle,
                'timestamp': time.time()
            })
            return jsonify({'success': True, 'angle': angle})
        else:
            return jsonify({'success': False, 'error': 'Failed to set servo angle'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/servo/<int:channel>/config', methods=['POST'])
def update_servo_config(channel):
    try:
        data = request.get_json()
        name = data.get('name')
        min_pulse = data.get('min_pulse')
        max_pulse = data.get('max_pulse')
        
        servo_controller.update_servo_config(channel, name, min_pulse, max_pulse)
        
        socketio.emit('config_update', {
            'channel': channel,
            'config': servo_controller.servo_configs[channel].__dict__
        })
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/emergency_stop', methods=['POST'])
def emergency_stop():
    try:
        servo_controller.emergency_stop()
        socketio.emit('emergency_stop', {'timestamp': time.time()})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', servo_controller.get_all_servos_status())


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('set_servo_angle')
def handle_set_servo_angle(data):
    try:
        channel = int(data['channel'])
        angle = float(data['angle'])
        
        if servo_controller.set_servo_angle(channel, angle):
            emit('servo_update', {
                'channel': channel,
                'angle': angle,
                'timestamp': time.time()
            }, broadcast=True)
        else:
            emit('error', {'message': f'Failed to set servo {channel} to angle {angle}'})
    except Exception as e:
        emit('error', {'message': str(e)})


@socketio.on('get_status')
def handle_get_status():
    emit('status', servo_controller.get_all_servos_status())


@socketio.on('emergency_stop')
def handle_emergency_stop():
    try:
        servo_controller.emergency_stop()
        emit('emergency_stop', {'timestamp': time.time()}, broadcast=True)
    except Exception as e:
        emit('error', {'message': str(e)})


@socketio.on('enable_servo')
def handle_enable_servo(data):
    try:
        channel = int(data['channel'])
        if servo_controller.enable_servo(channel):
            emit('servo_enabled', {'channel': channel}, broadcast=True)
        else:
            emit('error', {'message': f'Failed to enable servo {channel}'})
    except Exception as e:
        emit('error', {'message': str(e)})


@socketio.on('disable_servo')
def handle_disable_servo(data):
    try:
        channel = int(data['channel'])
        if servo_controller.disable_servo(channel):
            emit('servo_disabled', {'channel': channel}, broadcast=True)
        else:
            emit('error', {'message': f'Failed to disable servo {channel}'})
    except Exception as e:
        emit('error', {'message': str(e)})


if __name__ == '__main__':
    try:
        print("Starting Raspberry Pi Servo Control Server...")
        print("Access the web interface at: http://localhost:5000")
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        servo_controller.cleanup()