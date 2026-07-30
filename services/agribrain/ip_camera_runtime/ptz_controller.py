class PTZController:
    """
    Controller for PTZ movements.
    For V1, PTZ is supported structurally but frames are only used 
    for validation if they match a known 'validation preset'.
    """
    
    def __init__(self):
        self._presets = {}
        
    def move_to_preset(self, camera_id: str, preset_name: str) -> bool:
        """Moves the camera to a predefined preset position."""
        # Simulated move
        return True
        
    def is_validation_preset(self, camera_id: str, preset_name: str) -> bool:
        """Returns True if this preset is known to be the fixed validation ROI."""
        return preset_name == "validation_home"
