"""
DJI Cloud Gateway Simulator — Device State Machine.

Models the state of a DJI gateway + aircraft during mission lifecycle.
This is the core brain of the simulator — it determines how the
fake gateway responds to commands.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DeviceMissionState(str, Enum):
    """Simulated device mission lifecycle states."""
    IDLE = "idle"
    PREPARING = "preparing"       # flighttask_prepare received
    READY = "ready"               # mission uploaded
    EXECUTING = "executing"       # mission in progress
    PAUSED = "paused"             # mission paused
    RETURNING = "returning"       # RTL in progress
    COMPLETED = "completed"       # mission done
    FAILED = "failed"             # mission failed


@dataclass
class SimulatedVehicle:
    """Simulated aircraft state."""
    latitude: float = 31.850
    longitude: float = 34.720
    altitude_m: float = 0.0
    heading_deg: float = 0.0
    groundspeed_m_s: float = 0.0
    battery_pct: float = 100.0
    gps_fix: bool = True
    gps_satellites: int = 18
    gps_hdop: float = 0.7
    mode: str = "idle"
    
    # Mission progress
    current_waypoint: int = 0
    total_waypoints: int = 0
    capture_count: int = 0
    
    # Timing
    flight_time_s: float = 0.0


@dataclass
class FailureInjection:
    """Injectable failures for testing."""
    reject_prepare: bool = False
    reject_execute: bool = False
    fail_at_waypoint: int = -1             # -1 = no failure
    low_battery_at_waypoint: int = -1      # Trigger low battery
    lost_link_at_waypoint: int = -1        # Trigger link loss
    upload_timeout: bool = False
    no_media: bool = False
    initial_battery_pct: float = 100.0


class DeviceStateMachine:
    """State machine for the simulated DJI gateway/aircraft.
    
    Tracks mission state and vehicle state. Used by the gateway
    simulator to produce correct responses and telemetry.
    """
    
    def __init__(self, failure: Optional[FailureInjection] = None):
        self.state = DeviceMissionState.IDLE
        self.vehicle = SimulatedVehicle()
        self.failure = failure or FailureInjection()
        self._waypoints = []
        self._mission_id = ""
        
        # Apply initial failure conditions
        self.vehicle.battery_pct = self.failure.initial_battery_pct
    
    def prepare_mission(self, mission_data: dict) -> dict:
        """Handle flighttask_prepare command.
        
        Returns result dict: {"result": 0} on success, {"result": error_code} on failure.
        """
        if self.failure.reject_prepare:
            return {"result": 1, "output": {"status": "rejected", "reason": "Prepare rejected by sim"}}
        
        if self.failure.upload_timeout:
            # Simulate timeout by not responding (caller handles)
            return None
        
        self.state = DeviceMissionState.PREPARING
        self._mission_id = mission_data.get("flight_id", "sim_mission")
        
        # Extract waypoint count from mission data
        wp_count = mission_data.get("waypoint_count", 20)
        self.vehicle.total_waypoints = wp_count
        self.vehicle.current_waypoint = 0
        self.vehicle.capture_count = 0
        
        self.state = DeviceMissionState.READY
        
        return {
            "result": 0,
            "output": {
                "status": "ok",
                "flight_id": self._mission_id,
            },
        }
    
    def execute_mission(self) -> dict:
        """Handle flighttask_execute command."""
        if self.state != DeviceMissionState.READY:
            return {"result": 1, "output": {"status": "rejected", "reason": f"Not ready, state={self.state.value}"}}
        
        if self.failure.reject_execute:
            return {"result": 1, "output": {"status": "rejected", "reason": "Execute rejected by sim"}}
        
        self.state = DeviceMissionState.EXECUTING
        self.vehicle.mode = "mission"
        self.vehicle.altitude_m = 50.0
        self.vehicle.groundspeed_m_s = 5.0
        
        return {
            "result": 0,
            "output": {"status": "ok"},
        }
    
    def pause_mission(self) -> dict:
        """Handle pause command."""
        if self.state != DeviceMissionState.EXECUTING:
            return {"result": 1, "output": {"status": "rejected", "reason": "Not executing"}}
        
        self.state = DeviceMissionState.PAUSED
        self.vehicle.groundspeed_m_s = 0.0
        self.vehicle.mode = "pause"
        
        return {"result": 0, "output": {"status": "ok"}}
    
    def resume_mission(self) -> dict:
        """Handle resume command."""
        if self.state != DeviceMissionState.PAUSED:
            return {"result": 1, "output": {"status": "rejected", "reason": "Not paused"}}
        
        self.state = DeviceMissionState.EXECUTING
        self.vehicle.groundspeed_m_s = 5.0
        self.vehicle.mode = "mission"
        
        return {"result": 0, "output": {"status": "ok"}}
    
    def return_home(self) -> dict:
        """Handle RTL command."""
        if self.state not in (DeviceMissionState.EXECUTING, DeviceMissionState.PAUSED):
            return {"result": 1, "output": {"status": "rejected", "reason": "Cannot RTL from current state"}}
        
        self.state = DeviceMissionState.RETURNING
        self.vehicle.mode = "return_home"
        
        return {"result": 0, "output": {"status": "ok"}}
    
    def abort_mission(self) -> dict:
        """Handle emergency stop / abort."""
        self.state = DeviceMissionState.FAILED
        self.vehicle.mode = "emergency"
        self.vehicle.groundspeed_m_s = 0.0
        
        return {"result": 0, "output": {"status": "ok"}}
    
    def advance_waypoint(self) -> bool:
        """Advance to next waypoint. Returns False if mission complete or failed."""
        if self.state != DeviceMissionState.EXECUTING:
            return False
        
        wp = self.vehicle.current_waypoint
        
        # Check failure injections
        if wp == self.failure.fail_at_waypoint:
            self.state = DeviceMissionState.FAILED
            self.vehicle.mode = "error"
            return False
        
        if wp == self.failure.low_battery_at_waypoint:
            self.vehicle.battery_pct = 8.0
        
        if wp == self.failure.lost_link_at_waypoint:
            self.vehicle.gps_fix = False
            self.vehicle.gps_satellites = 2
        
        # Normal progression
        self.vehicle.current_waypoint += 1
        self.vehicle.capture_count += 1
        self.vehicle.battery_pct -= 1.5       # ~1.5% per waypoint
        self.vehicle.flight_time_s += 3.0     # ~3s per waypoint
        
        # Update simulated position (drift east)
        self.vehicle.longitude += 0.00005
        self.vehicle.latitude += 0.00002
        
        if self.vehicle.current_waypoint >= self.vehicle.total_waypoints:
            self.state = DeviceMissionState.RETURNING
            self.vehicle.mode = "return_home"
            return False
        
        return True
    
    def complete_return(self):
        """Complete the return-to-home."""
        if self.state == DeviceMissionState.RETURNING:
            self.state = DeviceMissionState.COMPLETED
            self.vehicle.mode = "idle"
            self.vehicle.altitude_m = 0.0
            self.vehicle.groundspeed_m_s = 0.0
    
    def get_osd_payload(self) -> dict:
        """Generate an OSD telemetry payload in DJI Cloud API format."""
        return {
            "data": {
                "latitude": self.vehicle.latitude,
                "longitude": self.vehicle.longitude,
                "height": self.vehicle.altitude_m,
                "heading": self.vehicle.heading_deg,
                "horizontal_speed": self.vehicle.groundspeed_m_s,
                "battery": {
                    "capacity_percent": self.vehicle.battery_pct,
                    "voltage": 22.8 - (100 - self.vehicle.battery_pct) * 0.05,
                },
                "position_state": {
                    "is_fixed": 1 if self.vehicle.gps_fix else 0,
                    "quality": 5 if self.vehicle.gps_fix else 0,
                    "rtk_number": self.vehicle.gps_satellites,
                    "gps_number": self.vehicle.gps_satellites,
                },
                "mode_code": self._mode_code(),
                "wayline_progress": {
                    "current_waypoint": self.vehicle.current_waypoint,
                    "total_waypoints": self.vehicle.total_waypoints,
                    "progress": int(
                        self.vehicle.current_waypoint / max(self.vehicle.total_waypoints, 1) * 100
                    ),
                },
                "storage": {
                    "total": 128000,
                    "used": self.vehicle.capture_count * 8,
                },
            },
            "timestamp": int(self.vehicle.flight_time_s * 1000),
        }
    
    def _mode_code(self) -> int:
        """Map state to DJI mode_code."""
        return {
            DeviceMissionState.IDLE: 0,
            DeviceMissionState.PREPARING: 1,
            DeviceMissionState.READY: 1,
            DeviceMissionState.EXECUTING: 14,       # Waypoint mode
            DeviceMissionState.PAUSED: 15,           # Pause mode
            DeviceMissionState.RETURNING: 6,         # RTL
            DeviceMissionState.COMPLETED: 0,
            DeviceMissionState.FAILED: 0,
        }.get(self.state, 0)
