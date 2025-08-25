import time
import json
import bisect
import threading
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import math


class EaseType(Enum):
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    CUBIC_BEZIER = "cubic_bezier"
    BOUNCE = "bounce"
    ELASTIC = "elastic"


class TimelineState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    RECORDING = "recording"


@dataclass
class Keyframe:
    """Individual keyframe with timing and easing"""
    time_ms: float          # Time position in milliseconds
    value: float            # Target value (angle for servos)
    ease: EaseType = EaseType.LINEAR
    tension: float = 0.0    # Tension for spline curves (0-1)
    
    # Cubic bezier control points (if ease == CUBIC_BEZIER)
    bezier_cp1: Tuple[float, float] = (0.25, 0.1)
    bezier_cp2: Tuple[float, float] = (0.25, 1.0)


@dataclass
class Track:
    """Animation track for a single servo or group"""
    name: str
    target: str             # Servo ID or group name
    keyframes: List[Keyframe]
    enabled: bool = True
    solo: bool = False      # Solo this track (mute others)
    muted: bool = False
    
    def __post_init__(self):
        if not self.keyframes:
            self.keyframes = []
        # Keep keyframes sorted by time
        self.keyframes.sort(key=lambda kf: kf.time_ms)


@dataclass
class Marker:
    """Timeline marker for navigation"""
    time_ms: float
    label: str
    color: str = "#FF6B6B"  # Default red color


@dataclass
class Timeline:
    """Complete timeline with tracks and metadata"""
    name: str
    fps: Optional[float] = None     # Film-style timing
    bpm: Optional[float] = None     # Music-style timing
    duration_ms: float = 10000      # Total duration
    tracks: List[Track] = None
    markers: List[Marker] = None
    
    # Playback settings
    loop: bool = False
    loop_start_ms: float = 0
    loop_end_ms: Optional[float] = None
    
    def __post_init__(self):
        if self.tracks is None:
            self.tracks = []
        if self.markers is None:
            self.markers = []
        if self.loop_end_ms is None:
            self.loop_end_ms = self.duration_ms
        
        # Set default timebase
        if self.fps is None and self.bpm is None:
            self.fps = 30.0  # Default to 30 FPS
    
    def get_timebase_ms(self) -> float:
        """Get timebase interval in milliseconds"""
        if self.fps:
            return 1000.0 / self.fps
        elif self.bpm:
            return 60000.0 / (self.bpm * 4)  # Assume 4/4 time, 16th note resolution
        return 1000.0 / 30.0  # Fallback


class EasingFunctions:
    """Collection of easing functions"""
    
    @staticmethod
    def linear(t: float) -> float:
        return t
    
    @staticmethod
    def ease_in_quad(t: float) -> float:
        return t * t
    
    @staticmethod
    def ease_out_quad(t: float) -> float:
        return t * (2 - t)
    
    @staticmethod
    def ease_in_out_quad(t: float) -> float:
        if t < 0.5:
            return 2 * t * t
        return -1 + (4 - 2 * t) * t
    
    @staticmethod
    def ease_in_cubic(t: float) -> float:
        return t * t * t
    
    @staticmethod
    def ease_out_cubic(t: float) -> float:
        t -= 1
        return t * t * t + 1
    
    @staticmethod
    def ease_in_out_cubic(t: float) -> float:
        if t < 0.5:
            return 4 * t * t * t
        t -= 1
        return 1 + t * (2 * t) * (2 * t)
    
    @staticmethod
    def bounce_out(t: float) -> float:
        if t < 1/2.75:
            return 7.5625 * t * t
        elif t < 2/2.75:
            t -= 1.5/2.75
            return 7.5625 * t * t + 0.75
        elif t < 2.5/2.75:
            t -= 2.25/2.75
            return 7.5625 * t * t + 0.9375
        else:
            t -= 2.625/2.75
            return 7.5625 * t * t + 0.984375
    
    @staticmethod
    def elastic_out(t: float) -> float:
        if t == 0 or t == 1:
            return t
        return math.pow(2, -10 * t) * math.sin((t - 0.1) * 5 * math.pi) + 1
    
    @staticmethod
    def cubic_bezier(t: float, cp1: Tuple[float, float], cp2: Tuple[float, float]) -> float:
        """Cubic bezier easing with control points"""
        x1, y1 = cp1
        x2, y2 = cp2
        
        # Simplified cubic bezier approximation
        # In a full implementation, this would solve for t given x
        return (1-t)**3 * 0 + 3*(1-t)**2*t*y1 + 3*(1-t)*t**2*y2 + t**3 * 1
    
    @staticmethod
    def apply_easing(ease_type: EaseType, t: float, tension: float = 0.0, 
                    bezier_cp1: Tuple[float, float] = None, 
                    bezier_cp2: Tuple[float, float] = None) -> float:
        """Apply the specified easing function"""
        t = max(0, min(1, t))  # Clamp to 0-1
        
        if ease_type == EaseType.LINEAR:
            return EasingFunctions.linear(t)
        elif ease_type == EaseType.EASE_IN:
            # Use tension to blend between quad and cubic
            quad = EasingFunctions.ease_in_quad(t)
            cubic = EasingFunctions.ease_in_cubic(t)
            return quad * (1 - tension) + cubic * tension
        elif ease_type == EaseType.EASE_OUT:
            quad = EasingFunctions.ease_out_quad(t)
            cubic = EasingFunctions.ease_out_cubic(t)
            return quad * (1 - tension) + cubic * tension
        elif ease_type == EaseType.EASE_IN_OUT:
            quad = EasingFunctions.ease_in_out_quad(t)
            cubic = EasingFunctions.ease_in_out_cubic(t)
            return quad * (1 - tension) + cubic * tension
        elif ease_type == EaseType.BOUNCE:
            return EasingFunctions.bounce_out(t)
        elif ease_type == EaseType.ELASTIC:
            return EasingFunctions.elastic_out(t)
        elif ease_type == EaseType.CUBIC_BEZIER:
            if bezier_cp1 and bezier_cp2:
                return EasingFunctions.cubic_bezier(t, bezier_cp1, bezier_cp2)
            return EasingFunctions.linear(t)
        
        return EasingFunctions.linear(t)


class TimelineEngine:
    """Main timeline playback and editing engine"""
    
    def __init__(self, servo_controller, servo_registry):
        self.servo_controller = servo_controller
        self.servo_registry = servo_registry
        
        # Timeline storage
        self.timelines: Dict[str, Timeline] = {}
        self.active_timeline: Optional[str] = None
        
        # Playback state
        self.state = TimelineState.STOPPED
        self.current_time_ms = 0.0
        self.playback_speed = 1.0
        self.start_time = 0.0
        self.pause_time = 0.0
        
        # Transport thread
        self.transport_thread = None
        self.should_stop = False
        self.update_interval = 1.0 / 60.0  # 60 FPS playback
        
        # Live recording
        self.recording_tracks: Dict[str, Track] = {}  # target -> track
        self.recording_start_time = 0.0
        
        # Callbacks
        self.position_callbacks: List[Callable[[float], None]] = []
        self.marker_callbacks: List[Callable[[Marker], None]] = []
        self.state_callbacks: List[Callable[[TimelineState], None]] = []
        
        # Quantization
        self.quantize_enabled = False
        self.quantize_grid_ms = 100.0  # Default 100ms grid
    
    def timeline_new(self, name: str, fps: Optional[float] = None, bpm: Optional[float] = None, 
                    duration_ms: float = 10000) -> bool:
        """Create a new timeline"""
        if name in self.timelines:
            print(f"Warning: Timeline '{name}' already exists")
            return False
        
        timeline = Timeline(name=name, fps=fps, bpm=bpm, duration_ms=duration_ms)
        self.timelines[name] = timeline
        
        # Set as active if it's the first timeline
        if not self.active_timeline:
            self.active_timeline = name
        
        print(f"Created timeline '{name}' - Duration: {duration_ms}ms")
        if fps:
            print(f"  Timebase: {fps} FPS")
        elif bpm:
            print(f"  Timebase: {bpm} BPM")
        
        return True
    
    def track_add(self, timeline_name: str, track_name: str, target: str) -> bool:
        """Add a track to a timeline"""
        if timeline_name not in self.timelines:
            print(f"Error: Timeline '{timeline_name}' not found")
            return False
        
        # Verify target exists
        if not self.servo_registry.resolve_servo(target):
            print(f"Warning: Target '{target}' not found in servo registry")
        
        timeline = self.timelines[timeline_name]
        
        # Check for duplicate track names
        if any(track.name == track_name for track in timeline.tracks):
            print(f"Error: Track '{track_name}' already exists in timeline '{timeline_name}'")
            return False
        
        track = Track(name=track_name, target=target, keyframes=[])
        timeline.tracks.append(track)
        
        print(f"Added track '{track_name}' for target '{target}' to timeline '{timeline_name}'")
        return True
    
    def keyframe_add(self, timeline_name: str, track_name: str, time_ms: float, value: float,
                    ease: EaseType = EaseType.LINEAR, tension: float = 0.0) -> bool:
        """Add a keyframe to a track"""
        timeline = self.timelines.get(timeline_name)
        if not timeline:
            print(f"Error: Timeline '{timeline_name}' not found")
            return False
        
        # Find track
        track = None
        for t in timeline.tracks:
            if t.name == track_name:
                track = t
                break
        
        if not track:
            print(f"Error: Track '{track_name}' not found in timeline '{timeline_name}'")
            return False
        
        # Apply quantization if enabled
        if self.quantize_enabled:
            time_ms = self.quantize_time(time_ms)
        
        # Validate value for servo targets
        if self.servo_registry.resolve_servo(track.target):
            if not self.servo_registry.is_angle_safe(track.target, value):
                value = self.servo_registry.clamp_angle(track.target, value)
                print(f"Warning: Keyframe value clamped to safe range: {value}")
        
        # Create keyframe
        keyframe = Keyframe(time_ms=time_ms, value=value, ease=ease, tension=tension)
        
        # Insert in correct position (maintaining time order)
        bisect.insort(track.keyframes, keyframe, key=lambda kf: kf.time_ms)
        
        print(f"Added keyframe at {time_ms}ms, value {value} to track '{track_name}'")
        return True
    
    def quantize_time(self, time_ms: float) -> float:
        """Quantize time to grid"""
        if not self.quantize_enabled:
            return time_ms
        
        return round(time_ms / self.quantize_grid_ms) * self.quantize_grid_ms
    
    def set_quantize(self, enabled: bool, grid_ms: float = 100.0):
        """Enable/disable quantization with grid size"""
        self.quantize_enabled = enabled
        self.quantize_grid_ms = grid_ms
        print(f"Quantization: {'enabled' if enabled else 'disabled'} (grid: {grid_ms}ms)")
    
    def simplify_track(self, timeline_name: str, track_name: str, tolerance_deg: float = 1.0) -> int:
        """Remove redundant keyframes within tolerance"""
        timeline = self.timelines.get(timeline_name)
        if not timeline:
            return 0
        
        track = None
        for t in timeline.tracks:
            if t.name == track_name:
                track = t
                break
        
        if not track or len(track.keyframes) < 3:
            return 0
        
        original_count = len(track.keyframes)
        simplified_keyframes = [track.keyframes[0]]  # Always keep first
        
        for i in range(1, len(track.keyframes) - 1):
            prev_kf = simplified_keyframes[-1]
            curr_kf = track.keyframes[i]
            next_kf = track.keyframes[i + 1]
            
            # Interpolate between prev and next
            time_ratio = (curr_kf.time_ms - prev_kf.time_ms) / (next_kf.time_ms - prev_kf.time_ms)
            interpolated_value = prev_kf.value + (next_kf.value - prev_kf.value) * time_ratio
            
            # Keep keyframe if it deviates significantly from interpolation
            if abs(curr_kf.value - interpolated_value) > tolerance_deg:
                simplified_keyframes.append(curr_kf)
        
        # Always keep last
        if len(track.keyframes) > 1:
            simplified_keyframes.append(track.keyframes[-1])
        
        track.keyframes = simplified_keyframes
        removed_count = original_count - len(simplified_keyframes)
        
        print(f"Simplified track '{track_name}': removed {removed_count} keyframes")
        return removed_count
    
    def markers_set(self, timeline_name: str, markers: List[Dict[str, Any]]) -> bool:
        """Set timeline markers"""
        timeline = self.timelines.get(timeline_name)
        if not timeline:
            return False
        
        timeline.markers = []
        for marker_data in markers:
            marker = Marker(
                time_ms=marker_data["time_ms"],
                label=marker_data["label"],
                color=marker_data.get("color", "#FF6B6B")
            )
            timeline.markers.append(marker)
        
        # Sort by time
        timeline.markers.sort(key=lambda m: m.time_ms)
        print(f"Set {len(markers)} markers in timeline '{timeline_name}'")
        return True
    
    def jump(self, timeline_name: str, label: str) -> bool:
        """Jump to a marker by label"""
        timeline = self.timelines.get(timeline_name)
        if not timeline:
            return False
        
        for marker in timeline.markers:
            if marker.label == label:
                self.scrub(marker.time_ms)
                return True
        
        print(f"Error: Marker '{label}' not found")
        return False
    
    # Transport Controls
    def play(self, timeline_name: Optional[str] = None) -> bool:
        """Start playback"""
        if timeline_name:
            if timeline_name not in self.timelines:
                print(f"Error: Timeline '{timeline_name}' not found")
                return False
            self.active_timeline = timeline_name
        
        if not self.active_timeline:
            print("Error: No active timeline")
            return False
        
        if self.state == TimelineState.PAUSED:
            # Resume from pause
            self.start_time = time.time() - (self.pause_time - self.start_time)
        else:
            # Start from current position
            self.start_time = time.time() - (self.current_time_ms / 1000.0)
        
        self.state = TimelineState.PLAYING
        
        # Start transport thread if needed
        if not self.transport_thread or not self.transport_thread.is_alive():
            self._start_transport_thread()
        
        print(f"Playing timeline '{self.active_timeline}' from {self.current_time_ms}ms")
        self._trigger_state_callbacks(TimelineState.PLAYING)
        return True
    
    def pause(self) -> bool:
        """Pause playback"""
        if self.state != TimelineState.PLAYING:
            return False
        
        self.state = TimelineState.PAUSED
        self.pause_time = time.time()
        
        print(f"Paused at {self.current_time_ms}ms")
        self._trigger_state_callbacks(TimelineState.PAUSED)
        return True
    
    def stop(self) -> bool:
        """Stop playback and reset to beginning"""
        self.state = TimelineState.STOPPED
        self.current_time_ms = 0.0
        
        print("Stopped playback")
        self._trigger_state_callbacks(TimelineState.STOPPED)
        return True
    
    def scrub(self, time_ms: float) -> bool:
        """Jump to specific time position"""
        if not self.active_timeline:
            return False
        
        timeline = self.timelines[self.active_timeline]
        self.current_time_ms = max(0, min(timeline.duration_ms, time_ms))
        
        # Update servo positions for current time
        if self.state != TimelineState.PLAYING:
            self._update_servo_positions(self.current_time_ms)
        
        self._trigger_position_callbacks(self.current_time_ms)
        return True
    
    def set_speed(self, rate: float) -> bool:
        """Set playback speed multiplier"""
        if rate <= 0:
            return False
        
        self.playback_speed = rate
        
        # Adjust start time to maintain current position
        if self.state == TimelineState.PLAYING:
            current_real_time = time.time()
            elapsed_timeline = (current_real_time - self.start_time) * self.playback_speed
            self.start_time = current_real_time - (elapsed_timeline / rate)
        
        print(f"Playback speed: {rate}x")
        return True
    
    def loop_set(self, timeline_name: str, enabled: bool, start_ms: float = 0, 
                end_ms: Optional[float] = None) -> bool:
        """Set loop parameters"""
        timeline = self.timelines.get(timeline_name)
        if not timeline:
            return False
        
        timeline.loop = enabled
        timeline.loop_start_ms = start_ms
        timeline.loop_end_ms = end_ms or timeline.duration_ms
        
        print(f"Loop {'enabled' if enabled else 'disabled'} ({start_ms}-{timeline.loop_end_ms}ms)")
        return True
    
    def record_live_start(self, targets: List[str]) -> bool:
        """Start live recording for specified targets"""
        if not self.active_timeline:
            print("Error: No active timeline for recording")
            return False
        
        timeline = self.timelines[self.active_timeline]
        
        # Create or find tracks for each target
        self.recording_tracks = {}
        for target in targets:
            # Find existing track or create new one
            track_name = f"{target}_live"
            existing_track = None
            for track in timeline.tracks:
                if track.target == target:
                    existing_track = track
                    break
            
            if not existing_track:
                # Create new track
                if not self.track_add(self.active_timeline, track_name, target):
                    continue
                # Find the newly created track
                for track in timeline.tracks:
                    if track.name == track_name:
                        existing_track = track
                        break
            
            if existing_track:
                self.recording_tracks[target] = existing_track
        
        self.state = TimelineState.RECORDING
        self.recording_start_time = time.time()
        
        print(f"Started live recording for {len(self.recording_tracks)} targets")
        self._trigger_state_callbacks(TimelineState.RECORDING)
        return True
    
    def record_live_stop(self) -> bool:
        """Stop live recording"""
        if self.state != TimelineState.RECORDING:
            return False
        
        self.state = TimelineState.STOPPED
        recorded_keyframes = 0
        
        for target, track in self.recording_tracks.items():
            recorded_keyframes += len(track.keyframes)
        
        self.recording_tracks = {}
        
        print(f"Stopped recording - captured {recorded_keyframes} keyframes")
        self._trigger_state_callbacks(TimelineState.STOPPED)
        return True
    
    def _record_current_positions(self):
        """Record current servo positions as keyframes (called during live recording)"""
        if self.state != TimelineState.RECORDING:
            return
        
        current_time = time.time()
        record_time_ms = (current_time - self.recording_start_time) * 1000.0
        
        for target, track in self.recording_tracks.items():
            servo_meta = self.servo_registry.resolve_servo(target)
            if servo_meta:
                # Record current angle
                current_angle = servo_meta.current_angle
                keyframe = Keyframe(time_ms=record_time_ms, value=current_angle)
                
                # Insert keyframe
                bisect.insort(track.keyframes, keyframe, key=lambda kf: kf.time_ms)
    
    def _start_transport_thread(self):
        """Start the transport/playback thread"""
        self.should_stop = False
        self.transport_thread = threading.Thread(target=self._transport_worker, daemon=True)
        self.transport_thread.start()
    
    def _transport_worker(self):
        """Transport thread - handles playback and recording"""
        while not self.should_stop:
            if self.state == TimelineState.PLAYING and self.active_timeline:
                # Update timeline position
                current_real_time = time.time()
                elapsed = (current_real_time - self.start_time) * self.playback_speed
                self.current_time_ms = elapsed * 1000.0
                
                timeline = self.timelines[self.active_timeline]
                
                # Handle looping
                if timeline.loop:
                    if self.current_time_ms >= timeline.loop_end_ms:
                        loop_duration = timeline.loop_end_ms - timeline.loop_start_ms
                        if loop_duration > 0:
                            # Reset to loop start
                            self.current_time_ms = timeline.loop_start_ms
                            self.start_time = current_real_time - (timeline.loop_start_ms / 1000.0) / self.playback_speed
                
                # Stop at end if not looping
                elif self.current_time_ms >= timeline.duration_ms:
                    self.stop()
                    continue
                
                # Update servo positions
                self._update_servo_positions(self.current_time_ms)
                
                # Trigger position callbacks
                self._trigger_position_callbacks(self.current_time_ms)
            
            elif self.state == TimelineState.RECORDING:
                # Record current positions
                self._record_current_positions()
            
            time.sleep(self.update_interval)
    
    def _update_servo_positions(self, time_ms: float):
        """Update all servo positions based on timeline"""
        if not self.active_timeline:
            return
        
        timeline = self.timelines[self.active_timeline]
        
        for track in timeline.tracks:
            if not track.enabled or track.muted:
                continue
            
            # Skip if soloing other tracks
            solo_tracks = [t for t in timeline.tracks if t.solo and t.enabled]
            if solo_tracks and not track.solo:
                continue
            
            # Calculate interpolated value at current time
            value = self._interpolate_track_value(track, time_ms)
            if value is None:
                continue
            
            # Apply to servo
            servo_meta = self.servo_registry.resolve_servo(track.target)
            if servo_meta and servo_meta.enabled:
                # Apply safety limits and orientation
                safe_value = self.servo_registry.clamp_angle(track.target, value)
                oriented_value = self.servo_registry.apply_orientation(track.target, safe_value)
                
                # Set servo position
                self.servo_controller.set_servo_angle(servo_meta.channel, oriented_value)
                servo_meta.current_angle = safe_value
                servo_meta.target_angle = safe_value
    
    def _interpolate_track_value(self, track: Track, time_ms: float) -> Optional[float]:
        """Interpolate value from track keyframes at given time"""
        if not track.keyframes:
            return None
        
        # Find surrounding keyframes
        if time_ms <= track.keyframes[0].time_ms:
            return track.keyframes[0].value
        
        if time_ms >= track.keyframes[-1].time_ms:
            return track.keyframes[-1].value
        
        # Find keyframes to interpolate between
        for i in range(len(track.keyframes) - 1):
            kf1 = track.keyframes[i]
            kf2 = track.keyframes[i + 1]
            
            if kf1.time_ms <= time_ms <= kf2.time_ms:
                # Interpolate between kf1 and kf2
                if kf2.time_ms == kf1.time_ms:
                    return kf2.value
                
                # Calculate time ratio (0-1)
                time_ratio = (time_ms - kf1.time_ms) / (kf2.time_ms - kf1.time_ms)
                
                # Apply easing to the time ratio
                eased_ratio = EasingFunctions.apply_easing(
                    kf2.ease, 
                    time_ratio, 
                    kf2.tension,
                    kf2.bezier_cp1,
                    kf2.bezier_cp2
                )
                
                # Linear interpolation with eased ratio
                return kf1.value + (kf2.value - kf1.value) * eased_ratio
        
        return None
    
    def _trigger_position_callbacks(self, time_ms: float):
        """Trigger position update callbacks"""
        for callback in self.position_callbacks:
            try:
                callback(time_ms)
            except Exception as e:
                print(f"Position callback error: {e}")
    
    def _trigger_state_callbacks(self, state: TimelineState):
        """Trigger state change callbacks"""
        for callback in self.state_callbacks:
            try:
                callback(state)
            except Exception as e:
                print(f"State callback error: {e}")
    
    def add_position_callback(self, callback: Callable[[float], None]):
        """Add callback for position updates"""
        self.position_callbacks.append(callback)
    
    def add_state_callback(self, callback: Callable[[TimelineState], None]):
        """Add callback for state changes"""
        self.state_callbacks.append(callback)
    
    def get_timeline_status(self) -> Dict[str, Any]:
        """Get current timeline system status"""
        status = {
            "state": self.state.value,
            "active_timeline": self.active_timeline,
            "current_time_ms": self.current_time_ms,
            "playback_speed": self.playback_speed,
            "quantize_enabled": self.quantize_enabled,
            "quantize_grid_ms": self.quantize_grid_ms,
            "timelines": {}
        }
        
        for name, timeline in self.timelines.items():
            status["timelines"][name] = {
                "duration_ms": timeline.duration_ms,
                "fps": timeline.fps,
                "bpm": timeline.bpm,
                "tracks": len(timeline.tracks),
                "markers": len(timeline.markers),
                "loop": timeline.loop,
                "loop_start_ms": timeline.loop_start_ms,
                "loop_end_ms": timeline.loop_end_ms
            }
        
        return status
    
    def cleanup(self):
        """Clean shutdown of timeline system"""
        print("Shutting down timeline system...")
        self.should_stop = True
        self.state = TimelineState.STOPPED
        
        if self.transport_thread and self.transport_thread.is_alive():
            self.transport_thread.join(timeout=2.0)
        
        print("Timeline system stopped")