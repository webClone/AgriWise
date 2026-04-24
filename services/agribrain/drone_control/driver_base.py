"""
Drone Control — Vendor-Neutral Driver Interface.

Abstract base class for all drone drivers. The dispatcher, state machine,
and all runtime modules depend ONLY on this interface — never on vendor
SDK code directly.

Concrete implementations:
  - MockDriver: deterministic simulation for CI/tests
  - DJIWaylineDriver: DJI standard drones
  - MAVSDKDriver: PX4 / ArduPilot ecosystems
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterator

from .schemas import (
    CommandAck,
    CompiledMission,
    MediaManifest,
    TelemetryPacket,
    VehicleState,
)


class DroneDriverBase(ABC):
    """Abstract interface for drone vehicle drivers.
    
    All methods return typed contracts. No vendor-specific objects
    leak through this interface.
    """
    
    @property
    @abstractmethod
    def driver_type(self) -> str:
        """Identifier for this driver type (e.g., 'mock', 'dji_wayline', 'mavsdk')."""
        ...
    
    @property
    @abstractmethod
    def connected(self) -> bool:
        """Whether the driver is currently connected to a vehicle."""
        ...
    
    # --- Connection ---
    
    @abstractmethod
    def connect(self, vehicle_id: str = "") -> CommandAck:
        """Establish connection to the vehicle.
        
        Args:
            vehicle_id: Vehicle identifier (serial, IP, etc.)
        """
        ...
    
    @abstractmethod
    def disconnect(self) -> CommandAck:
        """Disconnect from the vehicle."""
        ...
    
    # --- Mission Upload ---
    
    @abstractmethod
    def upload_mission(self, compiled: CompiledMission) -> CommandAck:
        """Upload a compiled mission to the vehicle.
        
        The mission must be compiled by mission_compiler.py before upload.
        The driver translates CompiledMission into vendor-specific format.
        """
        ...
    
    # --- Vehicle Readiness ---
    
    @abstractmethod
    def validate_vehicle_ready(self) -> VehicleState:
        """Check if the vehicle is ready for flight.
        
        Returns current VehicleState. Caller checks fields for readiness.
        """
        ...
    
    # --- Flight Control ---
    
    @abstractmethod
    def arm(self) -> CommandAck:
        """Arm the vehicle motors."""
        ...
    
    @abstractmethod
    def start_mission(self) -> CommandAck:
        """Begin executing the uploaded mission."""
        ...
    
    @abstractmethod
    def pause_mission(self) -> CommandAck:
        """Pause mission execution (vehicle hovers)."""
        ...
    
    @abstractmethod
    def resume_mission(self) -> CommandAck:
        """Resume paused mission execution."""
        ...
    
    @abstractmethod
    def abort_mission(self) -> CommandAck:
        """Abort mission and stop motors (emergency)."""
        ...
    
    @abstractmethod
    def rtl(self) -> CommandAck:
        """Return to launch point."""
        ...
    
    @abstractmethod
    def land_now(self) -> CommandAck:
        """Land immediately at current position."""
        ...
    
    # --- Telemetry ---
    
    @abstractmethod
    def get_vehicle_state(self) -> VehicleState:
        """Get current vehicle state snapshot."""
        ...
    
    @abstractmethod
    def stream_telemetry(self) -> Iterator[TelemetryPacket]:
        """Stream telemetry packets during flight.
        
        Yields TelemetryPacket at regular intervals until mission
        completes or is aborted. The caller consumes this iterator
        during mission execution.
        """
        ...
    
    # --- Media ---
    
    @abstractmethod
    def fetch_media_manifest(self) -> MediaManifest:
        """Fetch the media manifest after mission completion.
        
        Returns a list of captured images/frames with metadata.
        """
        ...
