from typing import Dict, Optional
from .schemas import CalibrationModel

class CalibrationManager:
    """
    Manages fixed camera geometry calibrations.
    The perception engine relies heavily on this for registration quality.
    """
    
    def __init__(self):
        self._calibrations: Dict[str, CalibrationModel] = {}
        
    def store_calibration(self, calibration: CalibrationModel) -> None:
        self._calibrations[calibration.camera_id] = calibration
        
    def get_calibration(self, camera_id: str) -> Optional[CalibrationModel]:
        return self._calibrations.get(camera_id)
        
    def is_calibration_usable(self, camera_id: str, min_quality_score: float = 0.5) -> bool:
        """Hard gate for perception trust."""
        cal = self.get_calibration(camera_id)
        if not cal:
            return False
        return cal.registration_quality_score >= min_quality_score
