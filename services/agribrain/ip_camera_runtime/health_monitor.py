from datetime import datetime, timezone
from typing import Dict, Optional

from .schemas import CameraHealthState

class HealthMonitor:
    """
    Tracks stream status, dropped frames, tampering/movement, and lens obstruction risk.
    """
    
    def __init__(self):
        self._states: Dict[str, CameraHealthState] = {}
        
    def get_state(self, camera_id: str) -> CameraHealthState:
        if camera_id not in self._states:
            self._states[camera_id] = CameraHealthState(camera_id=camera_id)
        return self._states[camera_id]
        
    def update_frame_received(self, camera_id: str) -> None:
        state = self.get_state(camera_id)
        state.online = True
        state.last_frame_at = datetime.now(tz=timezone.utc)
        
    def record_dropped_frame(self, camera_id: str) -> None:
        state = self.get_state(camera_id)
        state.dropped_frames_count += 1
        
    def update_metrics(self, camera_id: str, bitrate: float, jitter: float) -> None:
        state = self.get_state(camera_id)
        state.bitrate_kbps = bitrate
        state.stream_jitter_ms = jitter
