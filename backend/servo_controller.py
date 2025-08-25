import time
import json
from typing import Dict, List
from dataclasses import dataclass
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo


@dataclass
class ServoConfig:
    channel: int
    min_pulse: int = 750
    max_pulse: int = 2250
    current_angle: float = 90.0
    active: bool = True
    name: str = ""


class ServoController:
    def __init__(self):
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.pca = PCA9685(self.i2c)
        self.pca.frequency = 50
        
        self.servos: Dict[int, servo.Servo] = {}
        self.servo_configs: Dict[int, ServoConfig] = {}
        
        for channel in range(16):
            self.servo_configs[channel] = ServoConfig(
                channel=channel,
                name=f"Servo {channel}"
            )
    
    def initialize_servo(self, channel: int, min_pulse: int = 750, max_pulse: int = 2250):
        if 0 <= channel <= 15:
            try:
                self.servos[channel] = servo.Servo(
                    self.pca.channels[channel],
                    min_pulse=min_pulse,
                    max_pulse=max_pulse
                )
                self.servo_configs[channel].min_pulse = min_pulse
                self.servo_configs[channel].max_pulse = max_pulse
                self.servo_configs[channel].active = True
                return True
            except Exception as e:
                print(f"Error initializing servo {channel}: {e}")
                return False
        return False
    
    def set_servo_angle(self, channel: int, angle: float) -> bool:
        if channel not in self.servos:
            self.initialize_servo(channel)
        
        if channel in self.servos and self.servo_configs[channel].active:
            try:
                angle = max(0, min(180, angle))
                self.servos[channel].angle = angle
                self.servo_configs[channel].current_angle = angle
                return True
            except Exception as e:
                print(f"Error setting servo {channel} to angle {angle}: {e}")
                return False
        return False
    
    def get_servo_angle(self, channel: int) -> float:
        return self.servo_configs[channel].current_angle
    
    def disable_servo(self, channel: int) -> bool:
        if channel in self.servos:
            try:
                self.pca.channels[channel].duty_cycle = 0
                self.servo_configs[channel].active = False
                return True
            except Exception as e:
                print(f"Error disabling servo {channel}: {e}")
                return False
        return False
    
    def enable_servo(self, channel: int) -> bool:
        if channel in self.servo_configs:
            self.servo_configs[channel].active = True
            return self.set_servo_angle(channel, self.servo_configs[channel].current_angle)
        return False
    
    def get_all_servos_status(self) -> Dict:
        return {
            "servos": [
                {
                    "channel": config.channel,
                    "name": config.name,
                    "angle": config.current_angle,
                    "active": config.active,
                    "min_pulse": config.min_pulse,
                    "max_pulse": config.max_pulse
                }
                for config in self.servo_configs.values()
            ]
        }
    
    def update_servo_config(self, channel: int, name: str = None, min_pulse: int = None, max_pulse: int = None):
        if channel in self.servo_configs:
            config = self.servo_configs[channel]
            
            if name is not None:
                config.name = name
            
            if min_pulse is not None or max_pulse is not None:
                config.min_pulse = min_pulse or config.min_pulse
                config.max_pulse = max_pulse or config.max_pulse
                
                if channel in self.servos:
                    del self.servos[channel]
                    self.initialize_servo(channel, config.min_pulse, config.max_pulse)
    
    def emergency_stop(self):
        for channel in range(16):
            self.disable_servo(channel)
    
    def cleanup(self):
        self.emergency_stop()
        self.pca.deinit()