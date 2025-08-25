import time
import math
import random
import threading
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum


class PresetType(Enum):
    SINE = "sine"
    PINGPONG = "pingpong"
    BOUNCE = "bounce"
    RANDOM_WALK = "random_walk"
    BEZIER_PATH = "bezier_path"
    STEP = "step"
    RIPPLE = "ripple"
    SWARM = "swarm"
    BREATH = "breath"
    TWITCH = "twitch"
    GLITCH = "glitch"


@dataclass
class PresetParams:
    """Parameters for motion presets"""
    # Universal parameters
    rate: float = 1.0           # Speed multiplier
    depth: float = 45.0         # Motion range in degrees
    center: float = 90.0        # Center position
    loop: bool = True           # Whether to loop
    
    # Sine wave specific
    frequency: float = 0.5      # Hz for sine waves
    phase: float = 0.0          # Phase offset in radians
    
    # Pingpong/Bounce specific  
    min_angle: float = 45.0     # Minimum angle
    max_angle: float = 135.0    # Maximum angle
    
    # Random walk specific
    step_size: float = 5.0      # Max step size per update
    coherence: float = 0.8      # 0-1, higher = smoother
    seed: Optional[int] = None  # Random seed
    
    # Bezier path specific
    control_points: List[float] = None  # Bezier control points
    
    # Step sequence specific
    sequence: List[float] = None        # Angle sequence
    hold_time: float = 1.0              # Time per step
    
    # Ripple specific
    wave_speed: float = 1.0     # Propagation speed
    decay: float = 0.1          # Amplitude decay
    
    # Breath specific
    inhale_time: float = 2.0    # Inhale duration
    exhale_time: float = 3.0    # Exhale duration
    hold_time_breath: float = 0.5  # Hold at peak
    
    # Twitch specific
    intensity: float = 0.3      # 0-1 twitch intensity
    interval_min: float = 0.5   # Min time between twitches
    interval_max: float = 3.0   # Max time between twitches
    
    def __post_init__(self):
        if self.control_points is None:
            self.control_points = [0.0, 0.3, 0.7, 1.0]  # Default bezier
        if self.sequence is None:
            self.sequence = [45.0, 90.0, 135.0, 90.0]   # Default step sequence


class PresetInstance:
    """Running instance of a motion preset"""
    
    def __init__(self, name: str, targets: List[str], preset_type: PresetType, params: PresetParams):
        self.name = name
        self.targets = targets.copy()
        self.preset_type = preset_type
        self.params = params
        
        # Runtime state
        self.start_time = time.time()
        self.is_running = False
        self.is_paused = False
        self.current_positions: Dict[str, float] = {}
        
        # Type-specific state
        self.phase_offsets: Dict[str, float] = {}
        self.random_states: Dict[str, Any] = {}
        self.step_indices: Dict[str, int] = {}
        self.last_step_times: Dict[str, float] = {}
        self.twitch_next_times: Dict[str, float] = {}
        
        # Initialize per-target state
        self._initialize_target_states()
    
    def _initialize_target_states(self):
        """Initialize per-target runtime state"""
        for i, target in enumerate(self.targets):
            # Phase offsets for ripple effects
            if self.preset_type == PresetType.RIPPLE:
                self.phase_offsets[target] = i * 0.5  # 0.5 second ripple delay
            elif self.preset_type == PresetType.SWARM:
                self.phase_offsets[target] = random.uniform(0, 2 * math.pi)
            else:
                self.phase_offsets[target] = 0.0
            
            # Random walk state
            if self.preset_type == PresetType.RANDOM_WALK:
                rng = random.Random(self.params.seed)
                self.random_states[target] = {
                    'position': self.params.center,
                    'velocity': 0.0,
                    'rng': rng
                }
            
            # Step sequence state
            if self.preset_type in [PresetType.STEP]:
                self.step_indices[target] = 0
                self.last_step_times[target] = time.time()
            
            # Twitch state
            if self.preset_type == PresetType.TWITCH:
                next_time = time.time() + random.uniform(self.params.interval_min, self.params.interval_max)
                self.twitch_next_times[target] = next_time
            
            # Initialize position
            self.current_positions[target] = self.params.center
    
    def update(self, dt: float) -> Dict[str, float]:
        """Update preset and return new target positions"""
        if not self.is_running or self.is_paused:
            return self.current_positions.copy()
        
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Update each target
        for target in self.targets:
            new_angle = self._calculate_target_angle(target, elapsed, dt)
            self.current_positions[target] = new_angle
        
        return self.current_positions.copy()
    
    def _calculate_target_angle(self, target: str, elapsed: float, dt: float) -> float:
        """Calculate new angle for a specific target"""
        if self.preset_type == PresetType.SINE:
            return self._sine_wave(target, elapsed)
        
        elif self.preset_type == PresetType.PINGPONG:
            return self._pingpong(target, elapsed)
        
        elif self.preset_type == PresetType.BOUNCE:
            return self._bounce(target, elapsed)
        
        elif self.preset_type == PresetType.RANDOM_WALK:
            return self._random_walk(target, dt)
        
        elif self.preset_type == PresetType.BEZIER_PATH:
            return self._bezier_path(target, elapsed)
        
        elif self.preset_type == PresetType.STEP:
            return self._step_sequence(target)
        
        elif self.preset_type == PresetType.RIPPLE:
            return self._ripple(target, elapsed)
        
        elif self.preset_type == PresetType.SWARM:
            return self._swarm(target, elapsed)
        
        elif self.preset_type == PresetType.BREATH:
            return self._breath(target, elapsed)
        
        elif self.preset_type == PresetType.TWITCH:
            return self._twitch(target)
        
        elif self.preset_type == PresetType.GLITCH:
            return self._glitch(target, elapsed)
        
        return self.current_positions.get(target, self.params.center)
    
    def _sine_wave(self, target: str, elapsed: float) -> float:
        """Generate sine wave motion"""
        phase = self.params.phase + self.phase_offsets[target]
        angle_offset = math.sin((elapsed * self.params.frequency * self.params.rate) + phase)
        return self.params.center + (angle_offset * self.params.depth)
    
    def _pingpong(self, target: str, elapsed: float) -> float:
        """Generate ping-pong motion between min and max"""
        cycle_time = 2.0 / self.params.rate  # Time for one complete cycle
        t = (elapsed % cycle_time) / cycle_time  # Normalize to 0-1
        
        if t < 0.5:
            # Going from min to max
            progress = t * 2
        else:
            # Going from max to min
            progress = (1.0 - t) * 2
        
        return self.params.min_angle + (progress * (self.params.max_angle - self.params.min_angle))
    
    def _bounce(self, target: str, elapsed: float) -> float:
        """Generate bouncing motion with easing"""
        cycle_time = 2.0 / self.params.rate
        t = (elapsed % cycle_time) / cycle_time
        
        # Bounce easing function
        if t < 0.5:
            # Rising with acceleration
            progress = 2 * t * t
        else:
            # Falling with deceleration
            t = 1 - t
            progress = 1 - (2 * t * t)
        
        return self.params.min_angle + (progress * (self.params.max_angle - self.params.min_angle))
    
    def _random_walk(self, target: str, dt: float) -> float:
        """Generate smooth random walk"""
        state = self.random_states[target]
        rng = state['rng']
        
        # Add random velocity change
        velocity_change = rng.gauss(0, self.params.step_size * dt)
        state['velocity'] = state['velocity'] * self.params.coherence + velocity_change
        
        # Limit velocity
        max_velocity = self.params.step_size * 10
        state['velocity'] = max(-max_velocity, min(max_velocity, state['velocity']))
        
        # Update position
        state['position'] += state['velocity'] * dt * self.params.rate
        
        # Bounce off boundaries
        if state['position'] < self.params.min_angle:
            state['position'] = self.params.min_angle
            state['velocity'] = abs(state['velocity'])
        elif state['position'] > self.params.max_angle:
            state['position'] = self.params.max_angle
            state['velocity'] = -abs(state['velocity'])
        
        return state['position']
    
    def _bezier_path(self, target: str, elapsed: float) -> float:
        """Generate motion along bezier curve"""
        cycle_time = 4.0 / self.params.rate  # Time for complete path
        t = (elapsed % cycle_time) / cycle_time if self.params.loop else min(1.0, elapsed / cycle_time)
        
        # Cubic bezier interpolation
        cp = self.params.control_points
        if len(cp) >= 4:
            # Convert control points to actual angles
            p0 = self.params.min_angle + cp[0] * (self.params.max_angle - self.params.min_angle)
            p1 = self.params.min_angle + cp[1] * (self.params.max_angle - self.params.min_angle)
            p2 = self.params.min_angle + cp[2] * (self.params.max_angle - self.params.min_angle)
            p3 = self.params.min_angle + cp[3] * (self.params.max_angle - self.params.min_angle)
            
            # Cubic bezier formula
            inv_t = 1 - t
            return (inv_t**3 * p0 + 
                   3 * inv_t**2 * t * p1 + 
                   3 * inv_t * t**2 * p2 + 
                   t**3 * p3)
        
        return self.params.center
    
    def _step_sequence(self, target: str) -> float:
        """Generate step sequence motion"""
        current_time = time.time()
        
        if current_time - self.last_step_times[target] >= self.params.hold_time / self.params.rate:
            # Time to advance to next step
            self.step_indices[target] = (self.step_indices[target] + 1) % len(self.params.sequence)
            self.last_step_times[target] = current_time
        
        return self.params.sequence[self.step_indices[target]]
    
    def _ripple(self, target: str, elapsed: float) -> float:
        """Generate ripple wave motion"""
        # Apply time-based phase offset for ripple effect
        wave_phase = (elapsed * self.params.wave_speed * self.params.rate) - self.phase_offsets[target]
        
        # Calculate decay based on distance from start
        distance_decay = math.exp(-self.phase_offsets[target] * self.params.decay)
        
        # Generate wave
        wave = math.sin(wave_phase * 2 * math.pi) * distance_decay
        return self.params.center + (wave * self.params.depth)
    
    def _swarm(self, target: str, elapsed: float) -> float:
        """Generate swarm-like coordinated motion"""
        # Each target has its own frequency variation
        freq_variation = 1.0 + (self.phase_offsets[target] / (2 * math.pi)) * 0.3  # ±15% frequency variation
        
        # Multiple sine waves for complex motion
        primary = math.sin(elapsed * self.params.frequency * freq_variation * self.params.rate)
        secondary = 0.3 * math.sin(elapsed * self.params.frequency * freq_variation * 3 * self.params.rate + self.phase_offsets[target])
        
        combined = primary + secondary
        return self.params.center + (combined * self.params.depth * 0.7)  # Slightly reduce amplitude
    
    def _breath(self, target: str, elapsed: float) -> float:
        """Generate breathing motion"""
        cycle_time = (self.params.inhale_time + self.params.exhale_time + 2 * self.params.hold_time_breath) / self.params.rate
        t = (elapsed % cycle_time) * self.params.rate
        
        if t < self.params.inhale_time:
            # Inhaling (ease in)
            progress = t / self.params.inhale_time
            progress = progress * progress  # Quadratic ease in
        elif t < self.params.inhale_time + self.params.hold_time_breath:
            # Holding at peak
            progress = 1.0
        elif t < self.params.inhale_time + self.params.hold_time_breath + self.params.exhale_time:
            # Exhaling (ease out)
            exhale_start = self.params.inhale_time + self.params.hold_time_breath
            progress = 1.0 - ((t - exhale_start) / self.params.exhale_time)
            progress = 1.0 - ((1.0 - progress) * (1.0 - progress))  # Quadratic ease out
        else:
            # Holding at bottom
            progress = 0.0
        
        return self.params.center + (progress - 0.5) * self.params.depth * 2
    
    def _twitch(self, target: str) -> float:
        """Generate occasional twitching motion"""
        current_time = time.time()
        current_position = self.current_positions[target]
        
        if current_time >= self.twitch_next_times[target]:
            # Time for a twitch
            twitch_amplitude = random.uniform(-self.params.depth, self.params.depth) * self.params.intensity
            target_position = self.params.center + twitch_amplitude
            
            # Schedule next twitch
            next_interval = random.uniform(self.params.interval_min, self.params.interval_max)
            self.twitch_next_times[target] = current_time + next_interval / self.params.rate
            
            return target_position
        else:
            # Return to center gradually
            center_pull = (self.params.center - current_position) * 0.1  # 10% pull toward center
            return current_position + center_pull
    
    def _glitch(self, target: str, elapsed: float) -> float:
        """Generate glitch-like irregular motion"""
        # Base sine wave
        base = math.sin(elapsed * self.params.frequency * self.params.rate)
        
        # Add random glitches
        if random.random() < 0.05 * self.params.rate:  # 5% chance per second (scaled by rate)
            glitch = random.uniform(-1, 1) * self.params.intensity
        else:
            glitch = 0
        
        # Combine base motion with glitches
        combined = base + glitch
        return self.params.center + (combined * self.params.depth)


class PresetEngine:
    """Engine for managing and running motion presets"""
    
    def __init__(self, servo_controller, servo_registry):
        self.servo_controller = servo_controller
        self.servo_registry = servo_registry
        
        # Preset definitions and instances
        self.preset_definitions: Dict[str, Dict[str, Any]] = {}
        self.running_instances: Dict[str, PresetInstance] = {}
        
        # Update thread
        self.update_thread = None
        self.should_stop = False
        self.update_interval = 1.0 / 30.0  # 30 FPS update rate
        self.last_update_time = time.time()
        
        # Load preset definitions
        self.load_preset_definitions()
    
    def load_preset_definitions(self):
        """Load built-in preset definitions"""
        # Artist-friendly preset definitions
        self.preset_definitions = {
            "breathe": {
                "type": PresetType.BREATH,
                "params": PresetParams(
                    rate=0.3,
                    depth=15,
                    inhale_time=3.0,
                    exhale_time=4.0,
                    hold_time_breath=0.8
                ),
                "description": "Gentle breathing motion"
            },
            "twitch": {
                "type": PresetType.TWITCH,
                "params": PresetParams(
                    intensity=0.4,
                    interval_min=1.0,
                    interval_max=5.0,
                    depth=10
                ),
                "description": "Occasional nervous twitches"
            },
            "quiver": {
                "type": PresetType.SINE,
                "params": PresetParams(
                    frequency=8.0,
                    depth=2,
                    rate=1.0
                ),
                "description": "High-frequency micro-movements"
            },
            "nod": {
                "type": PresetType.PINGPONG,
                "params": PresetParams(
                    rate=0.5,
                    min_angle=75,
                    max_angle=105
                ),
                "description": "Gentle nodding motion"
            },
            "ripple": {
                "type": PresetType.RIPPLE,
                "params": PresetParams(
                    wave_speed=1.5,
                    depth=20,
                    decay=0.1
                ),
                "description": "Wave propagating across servos"
            },
            "swarm": {
                "type": PresetType.SWARM,
                "params": PresetParams(
                    frequency=0.7,
                    depth=25,
                    rate=0.8
                ),
                "description": "Coordinated group movement"
            }
        }
    
    def create_preset(self, name: str, targets: List[str], preset_type: Union[PresetType, str], 
                     params: Union[PresetParams, Dict[str, Any]]) -> bool:
        """Create a custom preset definition"""
        
        # Convert string type to enum
        if isinstance(preset_type, str):
            try:
                preset_type = PresetType(preset_type)
            except ValueError:
                print(f"Error: Unknown preset type '{preset_type}'")
                return False
        
        # Convert dict params to PresetParams
        if isinstance(params, dict):
            params = PresetParams(**params)
        
        # Validate targets exist
        for target in targets:
            if not self.servo_registry.resolve_servo(target):
                print(f"Warning: Servo '{target}' not found in registry")
        
        self.preset_definitions[name] = {
            "type": preset_type,
            "params": params,
            "default_targets": targets,
            "description": f"Custom preset: {preset_type.value}"
        }
        
        print(f"Created preset '{name}' for {len(targets)} targets")
        return True
    
    def preset_play(self, name: str, targets: Optional[List[str]] = None, 
                   rate: float = 1.0, loop: bool = True) -> bool:
        """Start playing a preset"""
        
        if name not in self.preset_definitions:
            print(f"Error: Preset '{name}' not found")
            return False
        
        # Use provided targets or default targets
        if targets is None:
            targets = self.preset_definitions[name].get("default_targets", [])
        
        if not targets:
            print(f"Error: No targets specified for preset '{name}'")
            return False
        
        # Stop existing instance if running
        if name in self.running_instances:
            self.preset_stop(name)
        
        # Create preset instance
        preset_def = self.preset_definitions[name]
        params = preset_def["params"]
        
        # Override rate and loop if specified
        if rate != 1.0:
            params.rate = rate
        params.loop = loop
        
        instance = PresetInstance(name, targets, preset_def["type"], params)
        instance.is_running = True
        
        self.running_instances[name] = instance
        
        # Start update thread if not running
        if self.update_thread is None or not self.update_thread.is_alive():
            self._start_update_thread()
        
        print(f"Started preset '{name}' on {len(targets)} targets (rate: {rate})")
        return True
    
    def preset_stop(self, name: str) -> bool:
        """Stop a running preset"""
        if name in self.running_instances:
            instance = self.running_instances[name]
            instance.is_running = False
            del self.running_instances[name]
            print(f"Stopped preset '{name}'")
            return True
        
        return False
    
    def preset_pause(self, name: str) -> bool:
        """Pause a running preset"""
        if name in self.running_instances:
            self.running_instances[name].is_paused = True
            print(f"Paused preset '{name}'")
            return True
        return False
    
    def preset_resume(self, name: str) -> bool:
        """Resume a paused preset"""
        if name in self.running_instances:
            self.running_instances[name].is_paused = False
            print(f"Resumed preset '{name}'")
            return True
        return False
    
    def stop_all_presets(self):
        """Stop all running presets"""
        for name in list(self.running_instances.keys()):
            self.preset_stop(name)
    
    def get_running_presets(self) -> List[str]:
        """Get list of currently running presets"""
        return [name for name, instance in self.running_instances.items() if instance.is_running]
    
    def get_preset_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get all available preset definitions"""
        result = {}
        for name, definition in self.preset_definitions.items():
            result[name] = {
                "type": definition["type"].value,
                "description": definition["description"],
                "default_targets": definition.get("default_targets", []),
                "params": asdict(definition["params"])
            }
        return result
    
    def _start_update_thread(self):
        """Start the preset update background thread"""
        self.should_stop = False
        self.update_thread = threading.Thread(target=self._update_worker, daemon=True)
        self.update_thread.start()
        print("Preset engine update thread started")
    
    def _update_worker(self):
        """Background thread that updates all running presets"""
        while not self.should_stop:
            current_time = time.time()
            dt = current_time - self.last_update_time
            self.last_update_time = current_time
            
            # Update all running instances
            for instance in list(self.running_instances.values()):
                if instance.is_running:
                    new_positions = instance.update(dt)
                    
                    # Apply new positions to servos
                    for target_id, angle in new_positions.items():
                        servo_meta = self.servo_registry.resolve_servo(target_id)
                        if servo_meta and servo_meta.enabled:
                            # Apply safety limits and orientation
                            safe_angle = self.servo_registry.clamp_angle(target_id, angle)
                            oriented_angle = self.servo_registry.apply_orientation(target_id, safe_angle)
                            
                            # Set servo angle
                            self.servo_controller.set_servo_angle(servo_meta.channel, oriented_angle)
                            servo_meta.current_angle = safe_angle
                            servo_meta.target_angle = safe_angle
            
            # Sleep until next update
            time.sleep(self.update_interval)
    
    def cleanup(self):
        """Clean shutdown of preset engine"""
        print("Shutting down preset engine...")
        self.should_stop = True
        self.stop_all_presets()
        
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)
        
        print("Preset engine stopped")