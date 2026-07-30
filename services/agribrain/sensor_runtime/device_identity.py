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
        """Verify device credentials against structure, length, and prefix constraints."""
        if not self.device_id or not isinstance(self.device_id, str):
            return False
        if len(self.device_id) < 3:
            return False
        lower_id = self.device_id.lower()
        valid_prefixes = ("sens", "node", "dev", "unknown", "test", "lora", "gateway")
        return any(lower_id.startswith(p) for p in valid_prefixes)
