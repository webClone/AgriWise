"""
DJI Cloud API — Telemetry Mapper.

Converts DJI Cloud API OSD telemetry payloads into AgriWise
TelemetryPacket objects. This is the bridge between DJI's
JSON telemetry format and our typed runtime schema.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import datetime
import logging

from ...schemas import TelemetryPacket, VehicleState

logger = logging.getLogger(__name__)


class TelemetryMapper:
    """Maps DJI Cloud API OSD payloads to AgriWise TelemetryPackets."""
    
    def __init__(self, execution_id: str = ""):
        self._execution_id = execution_id
        self._sequence = 0
    
    def map(self, osd_payload: Dict[str, Any]) -> TelemetryPacket:
        """Convert a DJI OSD payload to a TelemetryPacket.
        
        Args:
            osd_payload: Raw DJI Cloud API OSD data
            
        Returns:
            TelemetryPacket with all available fields mapped
        """
        data = osd_payload.get("data", {})
        
        self._sequence += 1
        
        # Extract battery
        battery = data.get("battery", {})
        battery_pct = battery.get("capacity_percent", 0.0)
        battery_voltage = battery.get("voltage", 0.0)
        
        # Extract position
        position = data.get("position_state", {})
        gps_fix = position.get("is_fixed", 0) == 1
        gps_sats = position.get("gps_number", 0) or position.get("rtk_number", 0)
        
        # Extract wayline progress
        progress = data.get("wayline_progress", {})
        current_wp = progress.get("current_waypoint", 0)
        total_wp = progress.get("total_waypoints", 0)
        progress_pct = progress.get("progress", 0.0)
        
        # Extract storage
        storage = data.get("storage", {})
        storage_total = storage.get("total", 128000)
        storage_used = storage.get("used", 0)
        
        # Build vehicle state
        vehicle_state = VehicleState(
            armed=data.get("mode_code", 0) != 0,
            battery_pct=battery_pct,
            battery_voltage_v=battery_voltage,
            gps_fix=gps_fix,
            gps_satellites=gps_sats,
            gps_hdop=1.0 if gps_fix else 99.0,
            latitude=data.get("latitude", 0.0),
            longitude=data.get("longitude", 0.0),
            altitude_m=data.get("height", 0.0),
            heading_deg=data.get("heading", 0.0),
            groundspeed_m_s=data.get("horizontal_speed", 0.0),
            mode=self._decode_mode(data.get("mode_code", 0)),
            storage_available_mb=max(0, storage_total - storage_used),
            camera_ready=True,
            capture_count=current_wp,  # Approximate
        )
        
        packet = TelemetryPacket(
            execution_id=self._execution_id,
            sequence=self._sequence,
            state=vehicle_state,
            current_waypoint_index=current_wp,
            total_waypoints=total_wp,
            mission_progress_pct=float(progress_pct),
            capture_count=current_wp,
            expected_captures=total_wp,
        )
        
        return packet
    
    @staticmethod
    def _decode_mode(mode_code: int) -> str:
        """Decode DJI mode_code to human-readable string."""
        return {
            0: "idle",
            1: "standby",
            6: "return_home",
            12: "manual",
            14: "waypoint_mission",
            15: "pause",
            17: "atti",
        }.get(mode_code, f"unknown_{mode_code}")
