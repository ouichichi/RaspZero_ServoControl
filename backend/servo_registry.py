import json
import time
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum


class ServoOrientation(Enum):
    NORMAL = "normal"
    INVERTED = "inverted"
    MIRRORED = "mirrored"


@dataclass
class ServoMetadata:
    """Enhanced servo configuration with physical metadata"""
    id: str                    # Human-readable ID (e.g., "left_eye", "head_tilt")
    channel: int              # Hardware channel (0-15)
    pin: Optional[int] = None # Physical pin number for documentation
    orientation: ServoOrientation = ServoOrientation.NORMAL
    gear_ratio: float = 1.0   # Mechanical advantage
    notes: str = ""           # Artist notes
    
    # Calibration data
    min_pulse_us: int = 750   # Minimum pulse width in microseconds
    max_pulse_us: int = 2250  # Maximum pulse width in microseconds
    center_deg: float = 90.0  # Physical center position in degrees
    
    # Soft limits (safety bounds)
    min_deg: float = 0.0      # Minimum allowed angle
    max_deg: float = 180.0    # Maximum allowed angle
    
    # Runtime state
    current_angle: float = 90.0
    target_angle: float = 90.0
    enabled: bool = False
    last_move_time: float = 0.0
    
    # Aliases for human-friendly naming
    aliases: List[str] = None
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


class ServoRegistry:
    """Enhanced servo management with metadata, calibration, and safety"""
    
    def __init__(self, config_file: str = "servo_config.json"):
        self.config_file = config_file
        self.servos: Dict[str, ServoMetadata] = {}
        self.channel_map: Dict[int, str] = {}  # channel -> servo_id mapping
        self.alias_map: Dict[str, str] = {}    # alias -> servo_id mapping
        
        # Load existing configuration
        self.load_config()
    
    def register_servo(self, id: str, channel: int, pin: Optional[int] = None, 
                      orientation: ServoOrientation = ServoOrientation.NORMAL,
                      gear_ratio: float = 1.0, notes: str = "") -> bool:
        """Register a new servo with physical metadata"""
        
        if id in self.servos:
            print(f"Warning: Servo ID '{id}' already exists. Use rename_servo() to change.")
            return False
        
        if channel in self.channel_map:
            print(f"Error: Channel {channel} already assigned to servo '{self.channel_map[channel]}'")
            return False
        
        if not (0 <= channel <= 15):
            print(f"Error: Channel {channel} out of range (0-15)")
            return False
        
        # Create servo metadata
        servo_meta = ServoMetadata(
            id=id,
            channel=channel,
            pin=pin,
            orientation=orientation,
            gear_ratio=gear_ratio,
            notes=notes
        )
        
        self.servos[id] = servo_meta
        self.channel_map[channel] = id
        
        print(f"Registered servo '{id}' on channel {channel}")
        self.save_config()
        return True
    
    def rename_servo(self, old_id: str, new_id: str) -> bool:
        """Rename an existing servo"""
        if old_id not in self.servos:
            print(f"Error: Servo '{old_id}' not found")
            return False
        
        if new_id in self.servos:
            print(f"Error: Servo ID '{new_id}' already exists")
            return False
        
        # Update servo record
        servo_meta = self.servos[old_id]
        servo_meta.id = new_id
        
        # Update mappings
        self.servos[new_id] = servo_meta
        del self.servos[old_id]
        self.channel_map[servo_meta.channel] = new_id
        
        # Update alias mappings
        for alias, mapped_id in self.alias_map.items():
            if mapped_id == old_id:
                self.alias_map[alias] = new_id
        
        print(f"Renamed servo '{old_id}' to '{new_id}'")
        self.save_config()
        return True
    
    def alias_servo(self, id: str, alias: str) -> bool:
        """Add a human-friendly alias for a servo"""
        if id not in self.servos:
            print(f"Error: Servo '{id}' not found")
            return False
        
        if alias in self.alias_map:
            print(f"Warning: Alias '{alias}' already exists for servo '{self.alias_map[alias]}'")
            return False
        
        self.servos[id].aliases.append(alias)
        self.alias_map[alias] = id
        
        print(f"Added alias '{alias}' for servo '{id}'")
        self.save_config()
        return True
    
    def set_soft_limits(self, id: str, min_deg: float, max_deg: float) -> bool:
        """Set safety limits for servo motion"""
        servo_meta = self.resolve_servo(id)
        if not servo_meta:
            return False
        
        if min_deg >= max_deg:
            print(f"Error: min_deg ({min_deg}) must be less than max_deg ({max_deg})")
            return False
        
        if not (0 <= min_deg <= 180) or not (0 <= max_deg <= 180):
            print(f"Error: Angles must be between 0-180 degrees")
            return False
        
        servo_meta.min_deg = min_deg
        servo_meta.max_deg = max_deg
        
        print(f"Set soft limits for '{id}': {min_deg}° - {max_deg}°")
        self.save_config()
        return True
    
    def calibrate_servo(self, id: str, min_us: int, max_us: int, center_deg: float = 90.0) -> bool:
        """Calibrate servo pulse width to angle mapping"""
        servo_meta = self.resolve_servo(id)
        if not servo_meta:
            return False
        
        if min_us >= max_us:
            print(f"Error: min_us ({min_us}) must be less than max_us ({max_us})")
            return False
        
        if not (500 <= min_us <= 2500) or not (500 <= max_us <= 2500):
            print(f"Warning: Pulse widths outside typical range (500-2500μs)")
        
        servo_meta.min_pulse_us = min_us
        servo_meta.max_pulse_us = max_us
        servo_meta.center_deg = center_deg
        
        print(f"Calibrated '{id}': {min_us}-{max_us}μs, center at {center_deg}°")
        self.save_config()
        return True
    
    def resolve_servo(self, identifier: str) -> Optional[ServoMetadata]:
        """Resolve servo by ID, alias, or channel"""
        # Direct ID lookup
        if identifier in self.servos:
            return self.servos[identifier]
        
        # Alias lookup
        if identifier in self.alias_map:
            return self.servos[self.alias_map[identifier]]
        
        # Channel lookup (if numeric)
        try:
            channel = int(identifier)
            if channel in self.channel_map:
                return self.servos[self.channel_map[channel]]
        except ValueError:
            pass
        
        print(f"Error: Servo '{identifier}' not found")
        return None
    
    def get_servo_id(self, identifier: str) -> Optional[str]:
        """Get the canonical servo ID from any identifier"""
        servo_meta = self.resolve_servo(identifier)
        return servo_meta.id if servo_meta else None
    
    def is_angle_safe(self, id: str, angle: float) -> bool:
        """Check if angle is within soft limits"""
        servo_meta = self.resolve_servo(id)
        if not servo_meta:
            return False
        
        return servo_meta.min_deg <= angle <= servo_meta.max_deg
    
    def clamp_angle(self, id: str, angle: float) -> float:
        """Clamp angle to servo's soft limits"""
        servo_meta = self.resolve_servo(id)
        if not servo_meta:
            return angle
        
        return max(servo_meta.min_deg, min(servo_meta.max_deg, angle))
    
    def apply_orientation(self, id: str, angle: float) -> float:
        """Apply orientation transformation to angle"""
        servo_meta = self.resolve_servo(id)
        if not servo_meta:
            return angle
        
        if servo_meta.orientation == ServoOrientation.INVERTED:
            return 180.0 - angle
        elif servo_meta.orientation == ServoOrientation.MIRRORED:
            return 180.0 - angle  # Same as inverted for single axis
        
        return angle
    
    def get_all_servos(self) -> Dict[str, Dict[str, Any]]:
        """Get all servo metadata as serializable dict"""
        return {
            servo_id: {
                **asdict(servo_meta),
                'orientation': servo_meta.orientation.value
            }
            for servo_id, servo_meta in self.servos.items()
        }
    
    def get_servo_info(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get detailed info for a specific servo"""
        servo_meta = self.resolve_servo(identifier)
        if not servo_meta:
            return None
        
        return {
            **asdict(servo_meta),
            'orientation': servo_meta.orientation.value,
            'aliases': servo_meta.aliases.copy()
        }
    
    def list_servos(self) -> List[str]:
        """Get list of all servo IDs"""
        return list(self.servos.keys())
    
    def list_channels(self) -> Dict[int, str]:
        """Get channel to servo ID mapping"""
        return self.channel_map.copy()
    
    def save_config(self):
        """Save configuration to file"""
        try:
            config_data = {
                'servos': {},
                'aliases': self.alias_map.copy()
            }
            
            for servo_id, servo_meta in self.servos.items():
                config_data['servos'][servo_id] = {
                    **asdict(servo_meta),
                    'orientation': servo_meta.orientation.value
                }
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            # Load servos
            for servo_id, servo_dict in config_data.get('servos', {}).items():
                # Handle orientation enum
                if 'orientation' in servo_dict:
                    orientation_str = servo_dict.pop('orientation')
                    orientation = ServoOrientation(orientation_str)
                else:
                    orientation = ServoOrientation.NORMAL
                
                servo_meta = ServoMetadata(**servo_dict, orientation=orientation)
                self.servos[servo_id] = servo_meta
                self.channel_map[servo_meta.channel] = servo_id
            
            # Load aliases
            self.alias_map = config_data.get('aliases', {})
            
            print(f"Loaded {len(self.servos)} servos from config")
            
        except FileNotFoundError:
            print(f"Config file {self.config_file} not found, starting with empty registry")
        except Exception as e:
            print(f"Error loading config: {e}")