"""
Drone Control — Runtime Schemas.

All typed contracts for the drone execution layer. These sit between
drone_mission/ (planning) and drone_photogrammetry/ + drone_rgb/ (perception).

Design rules:
  - All runtime objects are typed dataclasses, never loose dicts.
  - DispatchRequest works for both Mapping and Command missions.
  - CompiledMission carries full mission provenance.
  - ExecutionReport is produced for every mission, including failures.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import datetime


# ============================================================================
# Enums
# ============================================================================

class LiveMissionState(str, Enum):
    """Formal mission execution states."""
    PLANNED = "planned"
    UPLOADED = "uploaded"
    READY = "ready"
    ARMING = "arming"
    IN_FLIGHT = "in_flight"
    PAUSED = "paused"
    RETURNING = "returning"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class ControlMode(str, Enum):
    """How the vehicle is being controlled."""
    WAYPOINT_AUTO = "waypoint_auto"        # Fully autonomous waypoint mission
    GUIDED = "guided"                       # Manual guided with assist
    RTL = "rtl"                             # Return to launch


class FailsafeAction(str, Enum):
    """Actions the failsafe controller can take."""
    CONTINUE = "continue"
    PAUSE = "pause"
    RESUME = "resume"
    SKIP_SEGMENT = "skip_segment"
    RTL = "rtl"
    LAND_NOW = "land_now"
    ABORT = "abort"


class HealthSeverity(str, Enum):
    """Severity of runtime health warnings."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CommandStatus(str, Enum):
    """Status of a command sent to the vehicle."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    ERROR = "error"


# ============================================================================
# Failsafe Policy
# ============================================================================

@dataclass
class FailsafePolicy:
    """Policy-driven runtime safety rules.
    
    These are evaluated by the health monitor and failsafe controller
    during flight. The policy is set at dispatch time and cannot be
    changed in flight (safety invariant).
    """
    # Battery
    battery_warn_pct: float = 30.0         # Warn threshold
    battery_critical_pct: float = 20.0     # RTL threshold
    battery_emergency_pct: float = 10.0    # Land now threshold
    
    # Wind
    max_wind_m_s: float = 10.0             # Pause threshold
    max_wind_gust_m_s: float = 15.0        # RTL threshold
    
    # Link
    link_loss_timeout_s: float = 30.0      # RTL after this duration
    link_warn_quality_pct: float = 40.0    # Warn when below
    
    # Navigation
    max_drift_m: float = 5.0               # Off-track drift → pause
    max_altitude_deviation_m: float = 10.0 # Altitude deviation → warn
    
    # Capture
    max_missed_captures: int = 5           # Warn after N missed
    max_missed_captures_abort: int = 15    # Abort if too many missed
    
    # Storage
    min_storage_mb: int = 500              # Warn when below
    
    # Lost GPS
    min_gps_satellites: int = 6            # Warn below
    min_gps_fix_quality: float = 2.0       # Minimum HDOP


# ============================================================================
# Weather
# ============================================================================

@dataclass
class WeatherSnapshot:
    """Weather conditions at dispatch time."""
    wind_speed_m_s: float = 0.0
    wind_gust_m_s: float = 0.0
    wind_direction_deg: float = 0.0
    temperature_c: float = 20.0
    humidity_pct: float = 50.0
    visibility_km: float = 10.0
    precipitation: bool = False
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


# ============================================================================
# Vehicle State
# ============================================================================

@dataclass
class VehicleState:
    """Current state of the drone vehicle."""
    armed: bool = False
    battery_pct: float = 100.0
    battery_voltage_v: float = 0.0
    gps_fix: bool = False
    gps_satellites: int = 0
    gps_hdop: float = 99.0                 # Horizontal dilution of precision
    rtk_fix: bool = False
    wind_estimate_m_s: float = 0.0
    link_quality_pct: float = 100.0
    mode: str = "idle"                     # Vehicle flight mode string
    storage_available_mb: int = 128000
    
    # Position
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0               # AGL
    altitude_msl_m: float = 0.0           # Above sea level
    heading_deg: float = 0.0
    groundspeed_m_s: float = 0.0
    
    # Camera
    camera_ready: bool = True
    capture_count: int = 0
    
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


# ============================================================================
# Telemetry
# ============================================================================

@dataclass
class TelemetryPacket:
    """Timestamped runtime state snapshot from the vehicle.
    
    Streamed at regular intervals during flight. Persisted for
    post-mission audit, planned-vs-flown reconstruction, and
    refly planning.
    """
    execution_id: str = ""
    sequence: int = 0                      # Monotonic packet counter
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    # Vehicle state
    state: VehicleState = field(default_factory=VehicleState)
    
    # Mission progress
    current_waypoint_index: int = 0
    total_waypoints: int = 0
    mission_progress_pct: float = 0.0
    capture_count: int = 0
    expected_captures: int = 0
    
    # Derived
    off_track_m: float = 0.0              # Distance from planned path
    altitude_deviation_m: float = 0.0     # Deviation from planned altitude


# ============================================================================
# Command Acknowledgement
# ============================================================================

@dataclass
class CommandAck:
    """Typed acknowledgement for each command sent to vehicle."""
    command: str = ""                      # e.g., "arm", "start_mission"
    status: CommandStatus = CommandStatus.ACCEPTED
    message: str = ""
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


# ============================================================================
# Media Manifest
# ============================================================================

@dataclass
class CaptureRecord:
    """A single captured image/frame record."""
    capture_index: int = 0
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0
    heading_deg: float = 0.0
    file_ref: str = ""                     # URI to captured file
    file_size_bytes: int = 0
    waypoint_index: int = 0


@dataclass
class MediaManifest:
    """Post-mission media inventory from the vehicle."""
    execution_id: str = ""
    mission_id: str = ""
    captures: List[CaptureRecord] = field(default_factory=list)
    total_captures: int = 0
    total_size_bytes: int = 0
    storage_path: str = ""
    complete: bool = True                  # False if captures are missing


# ============================================================================
# Compiled Mission
# ============================================================================

@dataclass
class CompiledWaypoint:
    """A single executable waypoint in a compiled mission."""
    index: int = 0
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0               # AGL
    speed_m_s: float = 5.0
    
    # Actions at this waypoint
    action: str = "flythrough"             # "flythrough", "stop_and_capture", "start_capture", "stop_capture", "hover"
    capture: bool = False                  # Trigger camera at this waypoint
    
    # Heading
    heading_deg: float = 0.0
    heading_mode: str = "course"           # "course", "fixed", "poi"
    
    # Gimbal
    gimbal_pitch_deg: float = -90.0        # -90 = nadir
    
    # Segment metadata
    segment_type: str = "pass"             # "pass", "turn", "transit", "orbit"
    pass_index: int = 0                    # Which pass this belongs to


@dataclass
class CompiledMission:
    """Vendor-neutral executable mission.
    
    This is what gets uploaded to the vehicle. Contains the full
    waypoint sequence with capture actions, speed/altitude/overlap
    metadata, and mission provenance.
    """
    mission_id: str = ""
    execution_id: str = ""
    
    # Waypoint sequence
    waypoints: List[CompiledWaypoint] = field(default_factory=list)
    
    # Mission parameters
    flight_altitude_m: float = 50.0
    cruise_speed_m_s: float = 5.0
    capture_cadence_s: float = 2.0         # Camera trigger interval
    target_overlap_pct: float = 75.0
    target_gsd_cm: float = 2.0
    
    # Heading / gimbal
    heading_policy: str = "course"         # "course", "fixed", "poi"
    gimbal_pitch_deg: float = -90.0
    
    # Coverage pattern
    pattern: str = "boustrophedon"
    total_passes: int = 0
    estimated_captures: int = 0
    estimated_distance_m: float = 0.0
    estimated_duration_s: float = 0.0
    
    # Mission intent (preserved from planner)
    flight_mode: str = "mapping_mode"      # "mapping_mode" or "command_revisit"
    mission_type: str = "full_plot_map"
    plot_id: str = ""
    intent_id: str = ""
    
    # Provenance
    source_plan_id: str = ""
    drone_profile: str = ""
    compiler_version: str = "v1"
    compiled_at: datetime.datetime = field(default_factory=datetime.datetime.now)


# ============================================================================
# Dispatch Request
# ============================================================================

@dataclass
class DispatchRequest:
    """Request to dispatch a drone mission.
    
    Works for both Mapping and Command missions — the flight_plan
    and mission_type determine runtime behavior.
    """
    mission_id: str = ""
    execution_id: str = ""                 # Unique per execution attempt
    
    # What to fly
    flight_plan_id: str = ""
    flight_plan: Any = None                # FlightPlan from drone_mission
    intent: Any = None                     # MissionIntent from drone_mission
    
    # Vehicle
    vehicle_id: str = ""
    vehicle_profile: str = "standard_prosumer"
    driver_type: str = "mock"              # "mock", "dji_wayline", "mavsdk"
    
    # Control
    control_mode: ControlMode = ControlMode.WAYPOINT_AUTO
    
    # Launch
    launch_lat: float = 0.0
    launch_lon: float = 0.0
    launch_alt_m: float = 0.0
    
    # Operator
    operator_id: str = ""
    
    # Environment
    weather: WeatherSnapshot = field(default_factory=WeatherSnapshot)
    
    # Safety
    failsafe_policy: FailsafePolicy = field(default_factory=FailsafePolicy)
    
    # Timing
    requested_at: datetime.datetime = field(default_factory=datetime.datetime.now)


# ============================================================================
# Dispatch Result
# ============================================================================

@dataclass
class DispatchResult:
    """Result of a dispatch attempt."""
    execution_id: str = ""
    mission_id: str = ""
    
    success: bool = False
    state: LiveMissionState = LiveMissionState.PLANNED
    
    # If failed
    failure_reason: str = ""
    failure_stage: str = ""                # "preflight", "compile", "upload", "arm", "start"
    
    # If succeeded
    compiled_mission: Optional[CompiledMission] = None
    vehicle_state: Optional[VehicleState] = None
    
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


# ============================================================================
# Health Warning
# ============================================================================

@dataclass
class HealthWarning:
    """A runtime safety warning from the health monitor."""
    condition: str = ""                    # e.g., "low_battery", "drift", "lost_link"
    severity: HealthSeverity = HealthSeverity.LOW
    message: str = ""
    recommended_action: FailsafeAction = FailsafeAction.CONTINUE
    telemetry_sequence: int = 0
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


# ============================================================================
# Execution Report
# ============================================================================

@dataclass
class ExecutionReport:
    """Post-mission audit report.
    
    Produced for EVERY mission, including failed ones. Contains
    planned-vs-flown summary, quality metrics, and handoff status.
    """
    execution_id: str = ""
    mission_id: str = ""
    plot_id: str = ""
    
    # Status
    final_state: LiveMissionState = LiveMissionState.FAILED
    success: bool = False
    
    # Timing
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    duration_s: float = 0.0
    
    # Planned vs flown
    planned_distance_m: float = 0.0
    flown_distance_m: float = 0.0
    planned_waypoints: int = 0
    completed_waypoints: int = 0
    mean_off_track_m: float = 0.0
    max_off_track_m: float = 0.0
    
    # Coverage
    coverage_estimate_pct: float = 0.0
    overlap_estimate_pct: float = 0.0
    
    # Battery
    battery_start_pct: float = 0.0
    battery_end_pct: float = 0.0
    battery_used_pct: float = 0.0
    
    # Captures
    expected_captures: int = 0
    actual_captures: int = 0
    capture_completeness_pct: float = 0.0
    
    # Failures
    segment_failures: int = 0
    warnings_triggered: List[HealthWarning] = field(default_factory=list)
    failsafe_actions_taken: List[str] = field(default_factory=list)
    
    # Media handoff
    media_handoff_status: str = ""         # "pending", "completed", "failed"
    media_handoff_target: str = ""         # "photogrammetry", "farmer_photo"
    media_manifest: Optional[MediaManifest] = None
    
    # Mission provenance
    flight_mode: str = ""
    mission_type: str = ""
    driver_type: str = ""
    vehicle_profile: str = ""
    compiler_version: str = ""
    
    # Downstream refs
    photogrammetry_output_ref: str = ""
    perception_output_ref: str = ""
