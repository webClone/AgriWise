from dataclasses import dataclass
from typing import Optional


@dataclass
class DeviceIdentity:
    """Authentication and identity resolution for a device."""
    device_id: str
    network_id: Optional[str] = None       # e.g. LoRaWAN DevEUI
    application_key: Optional[str] = None  # AppKey or API key mapping
    gateway_id: Optional[str] = None       # Receiving gateway

    def is_authenticated(self) -> bool:
        """Verify device credentials against runtime constraints."""
        # V1: Mock authentication check
        return True
