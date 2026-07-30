from datetime import datetime
from typing import List, Optional

from .schemas import FrameCapturePolicy

class FrameSampler:
    """
    Frame capture policy engine.
    Handles fixed cadence, anomaly burst triggers, and night-skipping.
    """
    
    def should_capture(self, policy: FrameCapturePolicy, last_capture_at: Optional[datetime], current_time: datetime, sun_elevation_deg: float) -> bool:
        if policy.night_skip_enabled and sun_elevation_deg < policy.sun_elevation_min_deg:
            return False
            
        if last_capture_at is None:
            return True
            
        delta = current_time - last_capture_at
        if delta.total_seconds() >= policy.cadence_minutes * 60:
            return True
            
        return False
        
    def trigger_burst(self, camera_id: str, reason: str) -> None:
        """Called externally when an anomaly requires high-frequency capture."""
        pass
