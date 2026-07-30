"""
DJI Cloud API — Configuration.

All DJI-specific settings for Cloud API integration.
Separated from driver logic so credentials / endpoints
can be swapped between dev, staging, and production.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DJIDroneModel(str, Enum):
    """DJI enterprise drone model enumerations (droneEnumValue)."""
    M3E = "77"          # Mavic 3 Enterprise
    M3T = "77"          # Mavic 3 Thermal (same enum, payload differs)
    M30 = "67"          # Matrice 30
    M30T = "67"         # Matrice 30T
    M350 = "89"         # Matrice 350 RTK
    M300 = "60"         # Matrice 300 RTK (legacy)


class DJIPayloadModel(str, Enum):
    """DJI camera/payload enumerations (payloadEnumValue)."""
    M3E_CAM = "66"      # M3E wide camera
    M30_CAM = "52"      # M30 wide camera
    M30T_IR = "53"      # M30T thermal
    H20 = "42"          # Zenmuse H20
    H20T = "43"         # Zenmuse H20T
    P1 = "50"           # Zenmuse P1 (photogrammetry)
    L2 = "90"           # Zenmuse L2 (LiDAR)


class DJIGatewayType(str, Enum):
    """Gateway device type."""
    RC_PLUS = "rc_plus"        # DJI RC Plus running Pilot 2
    DOCK = "dock"              # DJI Dock (autonomous)
    DOCK_2 = "dock_2"         # DJI Dock 2


@dataclass
class DJICloudConfig:
    """Configuration for DJI Cloud API integration.
    
    This is the single config object passed to the DJI driver
    and MQTT bridge. All connection and device parameters live here.
    """
    # MQTT broker
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_tls: bool = False
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_client_id: str = "agriwise_cloud"
    
    # Device identity
    gateway_sn: str = ""                   # Gateway serial number (RC Plus / Dock)
    device_sn: str = ""                    # Aircraft serial number
    
    # Drone model
    drone_model: DJIDroneModel = DJIDroneModel.M3E
    payload_model: DJIPayloadModel = DJIPayloadModel.M3E_CAM
    payload_position: int = 0              # 0 = main gimbal
    
    # Gateway type
    gateway_type: DJIGatewayType = DJIGatewayType.RC_PLUS
    
    # Object storage for KMZ upload
    storage_endpoint: str = ""             # S3/MinIO endpoint
    storage_bucket: str = "waylines"
    storage_region: str = ""
    storage_access_key: str = ""
    storage_secret_key: str = ""
    
    # Timeouts (seconds)
    connect_timeout_s: float = 10.0
    upload_timeout_s: float = 30.0
    execute_timeout_s: float = 15.0
    telemetry_timeout_s: float = 5.0       # Max gap between telem packets
    command_timeout_s: float = 10.0
    
    # Retry policy
    max_retries: int = 3
    retry_backoff_s: float = 2.0           # Exponential backoff base
    
    # Telemetry
    telemetry_rate_hz: float = 1.0         # Expected OSD update rate
    
    # Safety
    finish_action: str = "goHome"          # goHome, autoLand, hover
    exit_on_rc_lost: str = "goBack"        # goBack, hover, executeMission
    takeoff_security_height_m: float = 20.0
    
    # WPML
    wpml_version: str = "1.0.0"
    
    @property
    def services_topic(self) -> str:
        """Topic for sending commands to the gateway."""
        return f"thing/product/{self.gateway_sn}/services"
    
    @property
    def services_reply_topic(self) -> str:
        """Topic for receiving command acknowledgements."""
        return f"thing/product/{self.gateway_sn}/services_reply"
    
    @property
    def events_topic(self) -> str:
        """Topic for receiving device events."""
        return f"thing/product/{self.gateway_sn}/events"
    
    @property
    def state_topic(self) -> str:
        """Topic for device state updates."""
        return f"thing/product/{self.gateway_sn}/state"
    
    @property
    def osd_topic(self) -> str:
        """Topic for OSD telemetry (position, battery, etc)."""
        return f"thing/product/{self.device_sn}/osd"


# ============================================================================
# Preset configs for common setups
# ============================================================================

def dev_config(gateway_sn: str = "SIM_GATEWAY_001", device_sn: str = "SIM_DRONE_001") -> DJICloudConfig:
    """Development config with local MQTT broker."""
    return DJICloudConfig(
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_tls=False,
        gateway_sn=gateway_sn,
        device_sn=device_sn,
        drone_model=DJIDroneModel.M3E,
        payload_model=DJIPayloadModel.M3E_CAM,
        gateway_type=DJIGatewayType.RC_PLUS,
    )
