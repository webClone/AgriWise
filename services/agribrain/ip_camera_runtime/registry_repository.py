from abc import ABC, abstractmethod
from typing import List, Optional
from .schemas import IPCameraRegistration

class IPCameraRegistryRepository(ABC):
    """
    Abstract base class for IPCamera Registry storage backends.
    Allows persisting camera configurations across restarts.
    """
    
    @abstractmethod
    def register_camera(self, config: IPCameraRegistration) -> None:
        """Register or update a camera configuration."""
        pass
        
    @abstractmethod
    def get_camera(self, camera_id: str) -> Optional[IPCameraRegistration]:
        """Retrieve a camera configuration by ID."""
        pass
        
    @abstractmethod
    def get_cameras_for_plot(self, plot_id: str) -> List[IPCameraRegistration]:
        """Retrieve all cameras configured for a specific plot."""
        pass

    @abstractmethod
    def list_all(self) -> List[IPCameraRegistration]:
        """Retrieve all registered cameras."""
        pass

    def get_primary_validation_camera(self, plot_id: str) -> Optional[IPCameraRegistration]:
        """Convenience method to retrieve the primary validation camera for a plot."""
        cameras = self.get_cameras_for_plot(plot_id)
        for c in cameras:
            if c.is_primary_validation_camera:
                return c
        return None
