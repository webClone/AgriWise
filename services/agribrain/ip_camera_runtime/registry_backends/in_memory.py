from typing import Dict, List, Optional
from ..schemas import IPCameraRegistration
from ..registry_repository import IPCameraRegistryRepository

class InMemoryCameraRegistry(IPCameraRegistryRepository):
    """
    In-memory storage backend for IPCameraRegistry.
    Used for testing and local development where persistence across restarts is not required.
    """
    
    def __init__(self):
        # camera_id -> IPCameraRegistration
        self._cameras: Dict[str, IPCameraRegistration] = {}
        
    def register_camera(self, config: IPCameraRegistration) -> None:
        self._cameras[config.camera_id] = config
        
    def get_camera(self, camera_id: str) -> Optional[IPCameraRegistration]:
        return self._cameras.get(camera_id)
        
    def get_cameras_for_plot(self, plot_id: str) -> List[IPCameraRegistration]:
        return [c for c in self._cameras.values() if c.plot_id == plot_id]

    def list_all(self) -> List[IPCameraRegistration]:
        return list(self._cameras.values())
