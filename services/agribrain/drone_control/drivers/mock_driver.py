"""
Drone Control — Mock Driver.

Deterministic simulation driver for CI, tests, and benchmarks.
Supports both Mapping and Command execution paths. Can inject
configurable failure modes for testing failsafe logic.

V2: Supports stepped mode for mid-flight control testing.
    When stepped=True, stream_telemetry() blocks at each waypoint
    until step() is called externally — allowing pause/resume/abort/RTL
    to be tested during active execution windows.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterator, List, Optional
import datetime
import math
import threading
import uuid

from ..driver_base import DroneDriverBase
from ..schemas import (
    CommandAck,
    CommandStatus,
    CompiledMission,
    CompiledWaypoint,
    CaptureRecord,
    LiveMissionState,
    MediaManifest,
    TelemetryPacket,
    VehicleState,
)


@dataclass
class MockFailureConfig:
    """Configurable failure injection for testing."""
    # Battery drain per waypoint (pct)
    battery_drain_per_waypoint: float = 1.5
    # Fail after N waypoints (0 = no failure)
    fail_at_waypoint: int = 0
    # Simulate link loss at waypoint N (0 = no loss)
    link_loss_at_waypoint: int = 0
    link_loss_duration_packets: int = 5
    # GPS degradation at waypoint N
    gps_degrade_at_waypoint: int = 0
    # Capture failure at waypoint N (skips capture)
    capture_fail_at_waypoint: int = 0
    # Wind gust at waypoint N
    wind_gust_at_waypoint: int = 0
    wind_gust_m_s: float = 18.0
    # Reject arm
    reject_arm: bool = False
    # Reject upload
    reject_upload: bool = False
    # Start with low battery
    initial_battery_pct: float = 100.0
    # Initial GPS satellites
    initial_gps_satellites: int = 14
    # Off-track drift per waypoint (meters)
    drift_per_waypoint_m: float = 0.0


class MockDriver(DroneDriverBase):
    """Deterministic simulation driver.
    
    Simulates:
    - Mission upload, ready, arm, fly, complete, abort
    - Flight along waypoints with configurable speed
    - Battery drain over time
    - Deterministic telemetry stream
    - Capture events at waypoints with capture=True
    - Configurable failure injection
    
    Stepped mode:
    - When stepped=True, stream_telemetry() blocks at each waypoint
      until step() is called. This allows external threads to issue
      pause/resume/abort/RTL commands during active execution.
    """
    
    def __init__(self, failure_config: Optional[MockFailureConfig] = None, stepped: bool = False):
        self._failure = failure_config or MockFailureConfig()
        self._connected = False
        self._armed = False
        self._mission: Optional[CompiledMission] = None
        self._state = LiveMissionState.PLANNED
        self._vehicle_id = ""
        self._captures: List[CaptureRecord] = []
        self._battery = self._failure.initial_battery_pct
        self._position = (0.0, 0.0, 0.0)  # lat, lon, alt
        self._heading = 0.0
        self._capture_count = 0
        self._current_wp = 0
        self._telemetry_seq = 0
        self._paused = False
        
        # Stepped mode support
        self._stepped = stepped
        self._step_event = threading.Event()    # Set by step() to advance one waypoint
        self._stop_event = threading.Event()    # Set by stop() to terminate telemetry
        self._at_waypoint = threading.Event()   # Set when driver is waiting at a waypoint
    
    @property
    def driver_type(self) -> str:
        return "mock"
    
    @property
    def connected(self) -> bool:
        return self._connected
    
    @property
    def current_waypoint(self) -> int:
        """Current waypoint index (for test inspection)."""
        return self._current_wp
    
    def step(self):
        """Advance one waypoint in stepped mode. No-op if not stepped."""
        self._step_event.set()
    
    def stop(self):
        """Terminate the telemetry stream (for abort/RTL from external thread)."""
        self._stop_event.set()
        self._step_event.set()  # Unblock if waiting
    
    def wait_at_waypoint(self, timeout: float = 5.0) -> bool:
        """Wait until the driver is blocked at a waypoint (stepped mode).
        
        Returns True if the driver reached a waypoint, False on timeout.
        """
        result = self._at_waypoint.wait(timeout=timeout)
        self._at_waypoint.clear()
        return result
    
    def connect(self, vehicle_id: str = "") -> CommandAck:
        self._vehicle_id = vehicle_id or f"mock_{uuid.uuid4().hex[:6]}"
        self._connected = True
        return CommandAck(
            command="connect",
            status=CommandStatus.ACCEPTED,
            message=f"Connected to mock vehicle {self._vehicle_id}",
        )
    
    def disconnect(self) -> CommandAck:
        self._connected = False
        self._armed = False
        return CommandAck(
            command="disconnect",
            status=CommandStatus.ACCEPTED,
            message="Disconnected",
        )
    
    def upload_mission(self, compiled: CompiledMission) -> CommandAck:
        if not self._connected:
            return CommandAck(
                command="upload_mission",
                status=CommandStatus.ERROR,
                message="Not connected",
            )
        
        if self._failure.reject_upload:
            return CommandAck(
                command="upload_mission",
                status=CommandStatus.REJECTED,
                message="Upload rejected (simulated failure)",
            )
        
        self._mission = compiled
        self._state = LiveMissionState.UPLOADED
        self._current_wp = 0
        self._capture_count = 0
        self._captures = []
        
        return CommandAck(
            command="upload_mission",
            status=CommandStatus.ACCEPTED,
            message=f"Uploaded {len(compiled.waypoints)} waypoints",
        )
    
    def validate_vehicle_ready(self) -> VehicleState:
        return VehicleState(
            armed=self._armed,
            battery_pct=self._battery,
            gps_fix=True,
            gps_satellites=self._failure.initial_gps_satellites,
            gps_hdop=1.2,
            rtk_fix=False,
            wind_estimate_m_s=3.0,
            link_quality_pct=100.0,
            mode="ready" if self._connected else "disconnected",
            storage_available_mb=64000,
            latitude=self._position[0],
            longitude=self._position[1],
            altitude_m=0.0,
            heading_deg=0.0,
            groundspeed_m_s=0.0,
            camera_ready=True,
            capture_count=0,
        )
    
    def arm(self) -> CommandAck:
        if not self._connected:
            return CommandAck(command="arm", status=CommandStatus.ERROR, message="Not connected")
        
        if self._failure.reject_arm:
            return CommandAck(command="arm", status=CommandStatus.REJECTED, message="Arm rejected (simulated)")
        
        self._armed = True
        self._state = LiveMissionState.ARMING
        return CommandAck(command="arm", status=CommandStatus.ACCEPTED, message="Armed")
    
    def start_mission(self) -> CommandAck:
        if not self._armed or not self._mission:
            return CommandAck(command="start_mission", status=CommandStatus.ERROR, message="Not armed or no mission")
        
        self._state = LiveMissionState.IN_FLIGHT
        
        # Set initial position to first waypoint
        if self._mission.waypoints:
            wp0 = self._mission.waypoints[0]
            self._position = (wp0.latitude, wp0.longitude, wp0.altitude_m)
            self._heading = wp0.heading_deg
        
        return CommandAck(command="start_mission", status=CommandStatus.ACCEPTED, message="Mission started")
    
    def pause_mission(self) -> CommandAck:
        if self._state != LiveMissionState.IN_FLIGHT:
            return CommandAck(command="pause_mission", status=CommandStatus.REJECTED, message="Not in flight")
        
        self._state = LiveMissionState.PAUSED
        self._paused = True
        return CommandAck(command="pause_mission", status=CommandStatus.ACCEPTED, message="Paused")
    
    def resume_mission(self) -> CommandAck:
        if self._state != LiveMissionState.PAUSED:
            return CommandAck(command="resume_mission", status=CommandStatus.REJECTED, message="Not paused")
        
        self._state = LiveMissionState.IN_FLIGHT
        self._paused = False
        return CommandAck(command="resume_mission", status=CommandStatus.ACCEPTED, message="Resumed")
    
    def abort_mission(self) -> CommandAck:
        self._state = LiveMissionState.ABORTED
        self._armed = False
        return CommandAck(command="abort_mission", status=CommandStatus.ACCEPTED, message="Aborted")
    
    def rtl(self) -> CommandAck:
        self._state = LiveMissionState.RETURNING
        return CommandAck(command="rtl", status=CommandStatus.ACCEPTED, message="Returning to launch")
    
    def land_now(self) -> CommandAck:
        self._state = LiveMissionState.RETURNING
        self._armed = False
        return CommandAck(command="land_now", status=CommandStatus.ACCEPTED, message="Landing now")
    
    def get_vehicle_state(self) -> VehicleState:
        return VehicleState(
            armed=self._armed,
            battery_pct=self._battery,
            gps_fix=True,
            gps_satellites=self._failure.initial_gps_satellites,
            gps_hdop=1.2,
            wind_estimate_m_s=3.0,
            link_quality_pct=100.0,
            mode=self._state.value,
            latitude=self._position[0],
            longitude=self._position[1],
            altitude_m=self._position[2],
            heading_deg=self._heading,
            groundspeed_m_s=5.0 if self._state == LiveMissionState.IN_FLIGHT else 0.0,
            camera_ready=True,
            capture_count=self._capture_count,
        )
    
    def stream_telemetry(self) -> Iterator[TelemetryPacket]:
        """Simulate flight along waypoints, yielding telemetry at each.
        
        Stepped mode:
            When self._stepped is True, the loop blocks at each waypoint
            until step() is called. This allows external threads to:
            - Inspect state at each waypoint
            - Issue pause/resume/abort/RTL commands
            - Verify mid-flight state transitions
        """
        if not self._mission or not self._mission.waypoints:
            return
        
        wps = self._mission.waypoints
        total = len(wps)
        link_loss_remaining = 0
        
        for i, wp in enumerate(wps):
            # --- Stepped mode: block until step() is called ---
            if self._stepped:
                self._step_event.clear()
                self._at_waypoint.set()           # Signal: "I'm at waypoint i"
                self._step_event.wait()           # Block until step() or stop()
                
                if self._stop_event.is_set():
                    return
            
            # --- Check if externally stopped or state changed ---
            if self._state in (LiveMissionState.ABORTED, LiveMissionState.FAILED):
                yield self._make_telemetry(i, total, wp)
                return
            
            # --- If paused, yield paused state and wait ---
            if self._stepped and self._state == LiveMissionState.PAUSED:
                yield self._make_telemetry(i, total, wp)
                # Stay paused: block again until step() resumes us
                self._step_event.clear()
                self._at_waypoint.set()
                self._step_event.wait()
                
                if self._stop_event.is_set():
                    return
                if self._state in (LiveMissionState.ABORTED, LiveMissionState.FAILED):
                    yield self._make_telemetry(i, total, wp)
                    return
            
            self._current_wp = i
            
            # Battery drain
            self._battery -= self._failure.battery_drain_per_waypoint
            self._battery = max(0.0, self._battery)
            
            # Position update
            drift = self._failure.drift_per_waypoint_m * (i + 1) / 111000.0
            self._position = (wp.latitude + drift, wp.longitude + drift, wp.altitude_m)
            self._heading = wp.heading_deg
            
            # Failure injection: hard failure
            if self._failure.fail_at_waypoint > 0 and i >= self._failure.fail_at_waypoint:
                self._state = LiveMissionState.FAILED
                yield self._make_telemetry(i, total, wp)
                return
            
            # Failure injection: link loss
            gps_sats = self._failure.initial_gps_satellites
            link_quality = 100.0
            wind = 3.0
            
            if self._failure.link_loss_at_waypoint > 0 and i == self._failure.link_loss_at_waypoint:
                link_loss_remaining = self._failure.link_loss_duration_packets
            
            if link_loss_remaining > 0:
                link_quality = 0.0
                link_loss_remaining -= 1
            
            # Failure injection: GPS degradation
            if self._failure.gps_degrade_at_waypoint > 0 and i >= self._failure.gps_degrade_at_waypoint:
                gps_sats = 3
            
            # Failure injection: wind gust
            if self._failure.wind_gust_at_waypoint > 0 and i == self._failure.wind_gust_at_waypoint:
                wind = self._failure.wind_gust_m_s
            
            # Capture
            if wp.capture:
                if not (self._failure.capture_fail_at_waypoint > 0 and i == self._failure.capture_fail_at_waypoint):
                    self._capture_count += 1
                    self._captures.append(CaptureRecord(
                        capture_index=self._capture_count,
                        timestamp=datetime.datetime.now(),
                        latitude=wp.latitude,
                        longitude=wp.longitude,
                        altitude_m=wp.altitude_m,
                        heading_deg=wp.heading_deg,
                        file_ref=f"mock://capture_{self._capture_count:04d}.jpg",
                        file_size_bytes=8_000_000,
                        waypoint_index=i,
                    ))
            
            # Build telemetry packet
            off_track = self._failure.drift_per_waypoint_m * (i + 1)
            
            pkt = TelemetryPacket(
                execution_id=self._mission.execution_id,
                sequence=self._telemetry_seq,
                timestamp=datetime.datetime.now(),
                state=VehicleState(
                    armed=self._armed,
                    battery_pct=self._battery,
                    gps_fix=gps_sats >= 4,
                    gps_satellites=gps_sats,
                    gps_hdop=1.2 if gps_sats >= 8 else 5.0,
                    wind_estimate_m_s=wind,
                    link_quality_pct=link_quality,
                    mode=self._state.value,
                    latitude=self._position[0],
                    longitude=self._position[1],
                    altitude_m=self._position[2],
                    heading_deg=self._heading,
                    groundspeed_m_s=wp.speed_m_s,
                    capture_count=self._capture_count,
                ),
                current_waypoint_index=i,
                total_waypoints=total,
                mission_progress_pct=(i + 1) / total * 100.0,
                capture_count=self._capture_count,
                expected_captures=self._mission.estimated_captures,
                off_track_m=off_track,
                altitude_deviation_m=0.0,
            )
            
            self._telemetry_seq += 1
            yield pkt
        
        # Mission complete
        self._state = LiveMissionState.RETURNING
        self._armed = False
    
    def _make_telemetry(self, wp_idx: int, total: int, wp: CompiledWaypoint) -> TelemetryPacket:
        """Build a telemetry packet for the current state."""
        pkt = TelemetryPacket(
            execution_id=self._mission.execution_id if self._mission else "",
            sequence=self._telemetry_seq,
            timestamp=datetime.datetime.now(),
            state=self.get_vehicle_state(),
            current_waypoint_index=wp_idx,
            total_waypoints=total,
            mission_progress_pct=(wp_idx + 1) / max(total, 1) * 100.0,
            capture_count=self._capture_count,
        )
        self._telemetry_seq += 1
        return pkt
    
    def fetch_media_manifest(self) -> MediaManifest:
        return MediaManifest(
            execution_id=self._mission.execution_id if self._mission else "",
            mission_id=self._mission.mission_id if self._mission else "",
            captures=list(self._captures),
            total_captures=len(self._captures),
            total_size_bytes=sum(c.file_size_bytes for c in self._captures),
            storage_path="mock://sd_card/DCIM/",
            complete=True,
        )
