#!/usr/bin/env python3

import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, socketio, servo_controller

if __name__ == '__main__':
    print("=" * 50)
    print("🎛️  Raspberry Pi Servo Controller")
    print("=" * 50)
    print(f"🌐 Web Interface: http://localhost:5000")
    print(f"📡 WebSocket: ws://localhost:5000")
    print(f"⚙️  Servo Channels: 0-15 (PCA9685)")
    print("=" * 50)
    print("Press Ctrl+C to stop the server")
    print()
    
    try:
        # Initialize all servo channels
        print("🔧 Initializing servo channels...")
        for channel in range(16):
            servo_controller.initialize_servo(channel)
        print("✅ All servo channels initialized")
        print()
        
        # Start the server
        socketio.run(
            app, 
            host='0.0.0.0', 
            port=5000, 
            debug=False,
            allow_unsafe_werkzeug=True
        )
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        
    except Exception as e:
        print(f"❌ Server error: {e}")
        
    finally:
        print("🧹 Cleaning up servo controller...")
        servo_controller.cleanup()
        print("👋 Goodbye!")