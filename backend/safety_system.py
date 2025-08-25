import time
import threading
import json
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from enum import Enum


class EmergencyMode(Enum):
    DETACH = "detach"      # Turn off PWM completely
    HOLD = "hold"          # Maintain current position
    SAFE_POSE = "safe_pose"  # Move to predefined safe positions


class SafetyState(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    EMERGENCY = "emergency"
    FAULT = "fault"


@dataclass
class SafePose:
    """Defines a safe pose for servos"""
    name: str
    description: str
    servo_angles: Dict[str, float]  # servo_id -> angle
    priority: int = 0  # Higher priority poses override lower ones
    
    def __post_init__(self):
        if not self.servo_angles:
            self.servo_angles = {}


class SafetySystem:
    """Comprehensive safety system with watchdog, emergency stops, and monitoring"""
    
    def __init__(self, servo_controller, servo_registry):
        self.servo_controller = servo_controller
        self.servo_registry = servo_registry
        
        # Safety state
        self.current_state = SafetyState.NORMAL
        self.emergency_mode = EmergencyMode.SAFE_POSE
        
        # Watchdog system
        self.watchdog_enabled = False
        self.watchdog_timeout = 5.0  # seconds
        self.watchdog_thread = None
        self.watchdog_lock = threading.Lock()
        self.last_activity = time.time()
        self.on_timeout_callback: Optional[Callable] = None
        
        # Safe poses
        self.safe_poses: Dict[str, SafePose] = {}
        self.default_safe_pose = "park"
        
        # Monitoring
        self.fault_log: List[Dict[str, Any]] = []
        self.emergency_log: List[Dict[str, Any]] = []
        
        # Callbacks
        self.safety_callbacks: Dict[SafetyState, List[Callable]] = {
            state: [] for state in SafetyState
        }
        
        # Initialize default safe poses
        self._create_default_safe_poses()
    
    def _create_default_safe_poses(self):
        """Create standard safe poses"""
        # Park pose - all servos at 90 degrees (center)
        self.add_safe_pose(
            "park", 
            "Default park position - all servos centered",
            {servo_id: 90.0 for servo_id in self.servo_registry.list_servos()},
            priority=1
        )
        
        # Retract pose - servos at minimum safe angles
        retract_angles = {}
        for servo_id in self.servo_registry.list_servos():
            servo_meta = self.servo_registry.resolve_servo(servo_id)
            if servo_meta:
                # Use the middle of the safe range, biased toward minimum
                mid_angle = (servo_meta.min_deg + servo_meta.max_deg) / 2
                retract_angles[servo_id] = min(mid_angle, 45.0)  # Cap at 45° or mid-range
        
        self.add_safe_pose(
            "retract",
            "Retracted position - servos at safe minimums", 
            retract_angles,
            priority=2
        )
    
    def add_safe_pose(self, name: str, description: str, servo_angles: Dict[str, float], priority: int = 0) -> bool:
        """Add a new safe pose"""
        # Validate servo angles
        validated_angles = {}
        for servo_id, angle in servo_angles.items():
            if not self.servo_registry.is_angle_safe(servo_id, angle):
                clamped_angle = self.servo_registry.clamp_angle(servo_id, angle)
                print(f"Warning: Angle {angle}° for servo '{servo_id}' clamped to {clamped_angle}°")
                validated_angles[servo_id] = clamped_angle
            else:
                validated_angles[servo_id] = angle
        
        safe_pose = SafePose(name, description, validated_angles, priority)
        self.safe_poses[name] = safe_pose
        
        print(f"Added safe pose '{name}': {len(validated_angles)} servos")
        return True
    
    def go_safe_pose(self, pose_name: Optional[str] = None) -> bool:
        """Move all servos to a safe pose"""
        if pose_name is None:
            pose_name = self.default_safe_pose
        
        if pose_name not in self.safe_poses:
            print(f"Error: Safe pose '{pose_name}' not found")
            return False
        
        safe_pose = self.safe_poses[pose_name]
        success_count = 0
        
        print(f"Executing safe pose: {safe_pose.name}")
        
        for servo_id, angle in safe_pose.servo_angles.items():
            servo_meta = self.servo_registry.resolve_servo(servo_id)
            if servo_meta:
                # Apply safety checks
                safe_angle = self.servo_registry.clamp_angle(servo_id, angle)
                oriented_angle = self.servo_registry.apply_orientation(servo_id, safe_angle)
                
                # Set servo angle through controller
                if self.servo_controller.set_servo_angle(servo_meta.channel, oriented_angle):
                    servo_meta.target_angle = safe_angle
                    servo_meta.current_angle = safe_angle
                    success_count += 1
        
        self._log_event("safe_pose", {
            "pose_name": pose_name,
            "servos_moved": success_count,
            "total_servos": len(safe_pose.servo_angles)
        })
        
        return success_count > 0
    
    def emergency_stop(self, mode: Optional[EmergencyMode] = None) -> bool:
        """Execute emergency stop with specified mode"""
        if mode is None:
            mode = self.emergency_mode
        
        self.current_state = SafetyState.EMERGENCY
        
        print(f"EMERGENCY STOP - Mode: {mode.value}")
        
        success = False
        if mode == EmergencyMode.DETACH:
            # Turn off all PWM signals
            success = self._detach_all_servos()
        elif mode == EmergencyMode.HOLD:
            # Keep current positions (no action needed)
            success = True
        elif mode == EmergencyMode.SAFE_POSE:
            # Move to safe pose
            success = self.go_safe_pose()
        
        # Log emergency
        self._log_emergency({
            "mode": mode.value,
            "success": success,
            "active_servos": len([s for s in self.servo_registry.servos.values() if s.enabled])
        })
        
        # Trigger callbacks
        self._trigger_safety_callbacks(SafetyState.EMERGENCY)
        
        return success
    
    def _detach_all_servos(self) -> bool:
        """Detach all servos (turn off PWM)"""
        success_count = 0
        for servo_id in self.servo_registry.list_servos():
            servo_meta = self.servo_registry.resolve_servo(servo_id)
            if servo_meta and servo_meta.enabled:
                if self.servo_controller.disable_servo(servo_meta.channel):
                    servo_meta.enabled = False
                    success_count += 1
        
        print(f"Detached {success_count} servos")
        return success_count > 0
    
    def watchdog_start(self, timeout_ms: float = 5000, on_timeout: Optional[Callable] = None):
        """Start watchdog timer"""
        self.watchdog_timeout = timeout_ms / 1000.0  # Convert to seconds
        self.on_timeout_callback = on_timeout or self.go_safe_pose
        self.watchdog_enabled = True
        self.last_activity = time.time()
        
        if self.watchdog_thread is None or not self.watchdog_thread.is_alive():
            self.watchdog_thread = threading.Thread(target=self._watchdog_worker, daemon=True)
            self.watchdog_thread.start()
        
        print(f"Watchdog started: {timeout_ms}ms timeout")
    
    def watchdog_stop(self):
        """Stop watchdog timer"""
        self.watchdog_enabled = False
        print("Watchdog stopped")
    
    def watchdog_pet(self):
        """Reset watchdog timer (call this regularly to prevent timeout)"""
        with self.watchdog_lock:
            self.last_activity = time.time()
    
    def _watchdog_worker(self):
        """Watchdog background thread"""
        while self.watchdog_enabled:
            time.sleep(0.1)  # Check every 100ms
            
            with self.watchdog_lock:
                if time.time() - self.last_activity > self.watchdog_timeout:
                    print("WATCHDOG TIMEOUT - Executing safety callback")
                    
                    # Execute timeout callback
                    try:
                        if self.on_timeout_callback:
                            self.on_timeout_callback()
                    except Exception as e:
                        print(f"Watchdog callback error: {e}")
                    
                    # Set fault state
                    self.current_state = SafetyState.FAULT
                    self._trigger_safety_callbacks(SafetyState.FAULT)
                    
                    # Log fault
                    self._log_fault({
                        "type": "watchdog_timeout",
                        "timeout_seconds": self.watchdog_timeout,
                        "last_activity_ago": time.time() - self.last_activity
                    })
                    
                    # Reset watchdog for next cycle
                    self.last_activity = time.time()
    
    def preflight_check(self) -> Dict[str, Any]:
        """Perform pre-operation safety check"""
        results = {
            "overall_status": "pass",
            "warnings": [],
            "errors": [],
            "servo_checks": {},
            "timestamp": time.time()
        }
        
        print("Starting preflight check...")
        
        # Check each registered servo
        for servo_id in self.servo_registry.list_servos():
            servo_meta = self.servo_registry.resolve_servo(servo_id)
            if not servo_meta:
                continue
                
            servo_result = {
                "status": "pass",
                "tests": {}
            }
            
            # Test 1: Range sweep within safe bounds
            test_angles = [
                servo_meta.min_deg + 5,  # Near minimum
                (servo_meta.min_deg + servo_meta.max_deg) / 2,  # Center
                servo_meta.max_deg - 5   # Near maximum
            ]
            
            for test_angle in test_angles:
                try:
                    # Apply orientation and set angle
                    oriented_angle = self.servo_registry.apply_orientation(servo_id, test_angle)
                    success = self.servo_controller.set_servo_angle(servo_meta.channel, oriented_angle)
                    
                    servo_result["tests"][f"angle_{test_angle}"] = {
                        "success": success,
                        "oriented_angle": oriented_angle
                    }
                    
                    if not success:
                        servo_result["status"] = "fail"
                        results["errors"].append(f"Servo '{servo_id}' failed angle test at {test_angle}°")
                    
                    time.sleep(0.1)  # Brief pause between movements
                    
                except Exception as e:
                    servo_result["status"] = "error"
                    servo_result["tests"][f"angle_{test_angle}"] = {"error": str(e)}
                    results["errors"].append(f"Servo '{servo_id}' error at {test_angle}°: {e}")
            
            results["servo_checks"][servo_id] = servo_result
            
            # Return to center after test
            try:
                center_angle = self.servo_registry.apply_orientation(servo_id, servo_meta.center_deg)
                self.servo_controller.set_servo_angle(servo_meta.channel, center_angle)
            except Exception as e:
                results["warnings"].append(f"Could not return servo '{servo_id}' to center: {e}")
        
        # Set overall status
        if results["errors"]:
            results["overall_status"] = "fail"
        elif results["warnings"]:
            results["overall_status"] = "warning"
        
        print(f"Preflight check complete: {results['overall_status']}")
        print(f"  Errors: {len(results['errors'])}, Warnings: {len(results['warnings'])}")
        
        return results
    
    def add_safety_callback(self, state: SafetyState, callback: Callable):
        """Add callback for safety state changes"""
        self.safety_callbacks[state].append(callback)
    
    def _trigger_safety_callbacks(self, state: SafetyState):
        """Trigger callbacks for safety state"""
        for callback in self.safety_callbacks[state]:
            try:
                callback(state, self)
            except Exception as e:
                print(f"Safety callback error: {e}")
    
    def _log_event(self, event_type: str, data: Dict[str, Any]):
        """Log general safety events"""
        log_entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data
        }
        # In a full implementation, this would go to a proper logging system
        print(f"Safety Event: {event_type} - {data}")
    
    def _log_emergency(self, data: Dict[str, Any]):
        """Log emergency events"""
        log_entry = {
            "timestamp": time.time(),
            "data": data
        }
        self.emergency_log.append(log_entry)
        # Keep only last 100 emergency events
        if len(self.emergency_log) > 100:
            self.emergency_log = self.emergency_log[-100:]
    
    def _log_fault(self, data: Dict[str, Any]):
        """Log fault events"""
        log_entry = {
            "timestamp": time.time(),
            "data": data
        }
        self.fault_log.append(log_entry)
        # Keep only last 100 fault events
        if len(self.fault_log) > 100:
            self.fault_log = self.fault_log[-100:]
    
    def get_safety_status(self) -> Dict[str, Any]:
        """Get current safety system status"""
        return {
            "current_state": self.current_state.value,
            "emergency_mode": self.emergency_mode.value,
            "watchdog_enabled": self.watchdog_enabled,
            "watchdog_timeout": self.watchdog_timeout,
            "last_activity": self.last_activity,
            "time_since_activity": time.time() - self.last_activity,
            "safe_poses": list(self.safe_poses.keys()),
            "default_safe_pose": self.default_safe_pose,
            "recent_emergencies": len(self.emergency_log),
            "recent_faults": len(self.fault_log)
        }
    
    def reset_safety_state(self):
        """Reset safety state to normal (after resolving issues)"""
        if self.current_state in [SafetyState.EMERGENCY, SafetyState.FAULT]:
            print(f"Resetting safety state from {self.current_state.value} to normal")
            self.current_state = SafetyState.NORMAL
            self._trigger_safety_callbacks(SafetyState.NORMAL)
            return True
        return False
    
    def cleanup(self):
        """Clean shutdown of safety system"""
        self.watchdog_stop()
        if self.watchdog_thread and self.watchdog_thread.is_alive():
            self.watchdog_thread.join(timeout=1.0)
        
        # Final emergency stop
        self.emergency_stop(EmergencyMode.DETACH)