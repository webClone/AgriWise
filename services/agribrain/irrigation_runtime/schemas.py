"""
Irrigation Runtime Schema — Production-Grade Data Contracts v1.0.0

Strict typed I/O for the hardware-agnostic irrigation control system.
Follows the AgriWise layer architecture standard: strict typing, full provenance,
deterministic content_hash(), and complete audit trail.

Contracts:
  - IrrigationSystemType: hardware classification
  - CommandType: atomic actuator operations
  - IrrigationCommand: dispatched hardware instruction
  - CommandResult: actuator response
  - IrrigationEvent: full lifecycle record
  - ActuatorRegistration: device identity + capabilities
  - SafetyInterlock: fail-safe constraint definition
  - SafetyViolation: detected safety breach record
  - ValidationReport: closed-loop moisture verification
  - WaterBudget: season/daily quota tracking
  - IrrigationScheduleEntry: planned event with approval status

Invariants:
  - volume_mm >= 0
  - flow_rate_lpm >= 0, <= max_flow_rate
  - duration_minutes > 0, <= max_duration_minutes
  - EMERGENCY commands bypass all queues
  - FULL_AUTO events require safety_score >= 0.8
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple


# ============================================================================
# Enums (Locked)
# ============================================================================

class IrrigationSystemType(str, Enum):
    """Classification of physical irrigation hardware."""
    DRIP = "DRIP"
    SPRINKLER = "SPRINKLER"
    CENTER_PIVOT = "CENTER_PIVOT"
    LINEAR_MOVE = "LINEAR_MOVE"
    FLOOD = "FLOOD"
    MICRO_SPRAY = "MICRO_SPRAY"
    SUBSURFACE_DRIP = "SUBSURFACE_DRIP"


class CommandType(str, Enum):
    """Atomic actuator operations."""
    START_ZONE = "START_ZONE"
    STOP_ZONE = "STOP_ZONE"
    SET_FLOW_RATE = "SET_FLOW_RATE"
    SET_PRESSURE = "SET_PRESSURE"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    PULSE_IRRIGATE = "PULSE_IRRIGATE"
    FERTIGATION_START = "FERTIGATION_START"
    FERTIGATION_STOP = "FERTIGATION_STOP"
    SET_PIVOT_SPEED = "SET_PIVOT_SPEED"
    SET_PIVOT_ANGLE = "SET_PIVOT_ANGLE"
    SYSTEM_FLUSH = "SYSTEM_FLUSH"
    QUERY_STATUS = "QUERY_STATUS"


class CommandPriority(str, Enum):
    """Command dispatch priority (higher = preempts lower)."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"           # Bypasses all queues


class EventStatus(str, Enum):
    """Full lifecycle status of an irrigation event."""
    SCHEDULED = "SCHEDULED"           # Planned by scheduler
    APPROVED = "APPROVED"             # Confirmed by farmer (SEMI_AUTO)
    QUEUED = "QUEUED"                 # In dispatch queue
    DISPATCHING = "DISPATCHING"       # Command sent to actuator
    EXECUTING = "EXECUTING"           # Actuator confirmed running
    VALIDATING = "VALIDATING"         # Post-irrigation moisture check
    COMPLETED = "COMPLETED"           # Successfully finished
    FAILED = "FAILED"                 # Execution error
    CANCELLED = "CANCELLED"           # Farmer or system cancelled
    DEFERRED = "DEFERRED"             # Postponed (rain/frost/quota)
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"


class ActuatorStatus(str, Enum):
    """Real-time status of a physical actuator."""
    ONLINE = "ONLINE"                 # Ready to accept commands
    OFFLINE = "OFFLINE"               # No heartbeat received
    EXECUTING = "EXECUTING"           # Currently running an irrigation event
    ERROR = "ERROR"                   # Fault condition detected
    MAINTENANCE = "MAINTENANCE"       # Manually taken offline
    UNKNOWN = "UNKNOWN"               # Status not yet determined


class AutomationMode(str, Enum):
    """Irrigation automation level — farmer chooses."""
    MANUAL = "MANUAL"                 # Farmer triggers everything
    SEMI_AUTO = "SEMI_AUTO"           # L8 recommends → farmer confirms → execute
    FULL_AUTO = "FULL_AUTO"           # Critical events execute autonomously


class FailSafeState(str, Enum):
    """Physical valve default state on power/comms loss."""
    NORMALLY_CLOSED = "NORMALLY_CLOSED"   # Valve closes → safe for most systems
    NORMALLY_OPEN = "NORMALLY_OPEN"       # Valve opens → rare, flood gates


class DriverProtocol(str, Enum):
    """Communication protocol for actuator control."""
    MQTT = "MQTT"
    MODBUS_RTU = "MODBUS_RTU"
    MODBUS_TCP = "MODBUS_TCP"
    LORAWAN = "LORAWAN"
    HTTP_REST = "HTTP_REST"
    BLUETOOTH = "BLUETOOTH"
    CELLULAR_AT = "CELLULAR_AT"


class InterlockType(str, Enum):
    """Categories of safety interlocks."""
    PRESSURE_LOW = "PRESSURE_LOW"             # Pipe burst detection
    PRESSURE_HIGH = "PRESSURE_HIGH"           # Over-pressure
    FLOW_ZERO = "FLOW_ZERO"                   # Clog / valve stuck closed
    FLOW_EXCESSIVE = "FLOW_EXCESSIVE"         # Leak / valve stuck open
    OVER_DELIVERY = "OVER_DELIVERY"           # Volume exceeded target by >20%
    DURATION_EXCEEDED = "DURATION_EXCEEDED"   # Max runtime watchdog
    FROST_RISK = "FROST_RISK"                 # Air temp < 2°C
    WATER_QUOTA_EXCEEDED = "WATER_QUOTA_EXCEEDED"
    SENSOR_OFFLINE = "SENSOR_OFFLINE"         # Critical sensor lost
    ELECTRICAL_FAULT = "ELECTRICAL_FAULT"     # Actuator power issue


class ValidationOutcome(str, Enum):
    """Result of post-irrigation moisture verification."""
    CONFIRMED = "CONFIRMED"                   # Moisture rise matches expected
    UNDER_DELIVERY = "UNDER_DELIVERY"         # Actual < 50% of expected
    OVER_DELIVERY = "OVER_DELIVERY"           # Actual > 150% of expected
    NO_RESPONSE = "NO_RESPONSE"               # No moisture change detected
    SENSOR_OFFLINE = "SENSOR_OFFLINE"         # Validation impossible
    PENDING = "PENDING"                       # Validation window not yet closed


class VendorId(str, Enum):
    """Supported hardware vendor identifiers."""
    GENERIC = "GENERIC"
    HUNTER = "HUNTER"
    RAIN_BIRD = "RAIN_BIRD"
    NETAFIM = "NETAFIM"
    LINDSAY = "LINDSAY"
    VALLEY = "VALLEY"
    TORO = "TORO"
    JAIN = "JAIN"
    RIVULIS = "RIVULIS"
    GALCON = "GALCON"
    BACCARA = "BACCARA"
    BERMAD = "BERMAD"
    CUSTOM = "CUSTOM"


# ============================================================================
# Core Command & Response
# ============================================================================

@dataclass
class IrrigationCommand:
    """Atomic command dispatched to a physical actuator.

    Invariants:
      - volume_mm >= 0
      - duration_minutes > 0 for START/PULSE commands
      - EMERGENCY_STOP has no volume/duration requirements
    """
    command_id: str                           # CMD-{uuid}
    command_type: CommandType
    device_id: str                            # Target actuator device_id
    zone_id: str                              # Logical irrigation zone
    plot_id: str

    # Delivery parameters
    volume_mm: float = 0.0                    # Target application depth (mm)
    duration_minutes: float = 0.0             # Planned runtime
    flow_rate_lpm: float = 0.0                # Target flow rate (L/min)
    pressure_bar: float = 0.0                 # Target pressure (bar)

    # Pivot-specific
    pivot_speed_pct: float = 0.0              # 0-100% of max speed
    pivot_start_angle_deg: float = 0.0        # Start angle (0-360)
    pivot_end_angle_deg: float = 360.0        # End angle (0-360)

    # Pulse irrigation
    pulse_on_minutes: float = 0.0
    pulse_off_minutes: float = 0.0
    pulse_cycles: int = 0

    # Scheduling
    priority: CommandPriority = CommandPriority.NORMAL
    scheduled_at: str = ""                    # ISO timestamp — when to execute
    expires_at: str = ""                      # ISO timestamp — cancel if not started by then

    # Traceability
    source_event_id: str = ""                 # Parent IrrigationEvent ID
    source_action_id: str = ""                # L8 ActionCard ID
    source_layer: str = "L8"
    request_id: str = ""                      # For ACK correlation

    # Automation
    automation_mode: AutomationMode = AutomationMode.SEMI_AUTO
    approved_by: str = ""                     # Farmer ID (empty if FULL_AUTO)
    approved_at: str = ""                     # ISO timestamp

    # Operation Identity & Retry Sequence
    operation_id: str = ""                    # Logical operation ID (stable across retries)
    attempt_number: int = 1                   # Monotonic attempt sequence (1, 2, 3...)

    def validate(self) -> List[str]:
        """Pre-flight validation. Returns list of error messages."""
        errors = []
        if self.volume_mm < 0:
            errors.append(f"volume_mm must be >= 0, got {self.volume_mm}")
        if self.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            if self.duration_minutes <= 0:
                errors.append(f"duration_minutes must be > 0 for {self.command_type.value}")
        if self.flow_rate_lpm < 0:
            errors.append(f"flow_rate_lpm must be >= 0, got {self.flow_rate_lpm}")
        if self.pivot_speed_pct < 0 or self.pivot_speed_pct > 100:
            errors.append(f"pivot_speed_pct must be 0-100, got {self.pivot_speed_pct}")
        return errors


@dataclass
class CommandResult:
    """Response from an actuator after command dispatch."""
    command_id: str
    device_id: str
    success: bool
    timestamp: str                            # ISO — when actuator responded

    # Actual delivery (may differ from commanded)
    actual_volume_l: float = 0.0              # Measured total volume (liters)
    actual_duration_minutes: float = 0.0
    actual_flow_rate_lpm: float = 0.0
    actual_pressure_bar: float = 0.0

    # Error handling
    error_code: str = ""                      # Vendor-specific error code
    error_message: str = ""
    retry_recommended: bool = False
    retries_remaining: int = 3

    # Acknowledgment
    ack_latency_ms: int = 0                   # Time from send to ACK


# ============================================================================
# Irrigation Event (Full Lifecycle)
# ============================================================================

@dataclass
class IrrigationEvent:
    """Complete lifecycle record for one irrigation action.

    Tracks an event from scheduling through execution to validation.
    Immutable once status reaches COMPLETED or FAILED.
    """
    event_id: str                             # EVT-{uuid}
    plot_id: str
    zone_id: str
    device_id: str

    system_type: IrrigationSystemType
    automation_mode: AutomationMode

    # Status
    status: EventStatus = EventStatus.SCHEDULED

    # Commanded values
    target_volume_mm: float = 0.0
    target_duration_minutes: float = 0.0
    target_flow_rate_lpm: float = 0.0
    application_efficiency: float = 0.90      # System-specific (drip=0.95, sprinkler=0.80)

    # Actual delivery
    actual_volume_l: float = 0.0
    actual_duration_minutes: float = 0.0

    # Timing
    scheduled_start: str = ""                 # ISO
    scheduled_end: str = ""
    actual_start: str = ""
    actual_end: str = ""

    # Traceability
    source_action_id: str = ""                # L8 ActionCard
    source_schedule_id: str = ""              # IrrigationScheduleEntry
    approved_by: str = ""
    approved_at: str = ""

    # Validation
    validation_outcome: ValidationOutcome = ValidationOutcome.PENDING
    pre_irrigation_vwc: float = 0.0           # Soil moisture before
    post_irrigation_vwc: float = 0.0          # Soil moisture after
    expected_vwc_rise: float = 0.0
    actual_vwc_rise: float = 0.0

    # Safety
    safety_violations: List[str] = field(default_factory=list)
    emergency_stopped: bool = False
    emergency_stop_reason: str = ""

    # Water budget impact
    water_consumed_mm: float = 0.0
    water_budget_remaining_mm: float = 0.0

    # Commands dispatched
    command_ids: List[str] = field(default_factory=list)

    # Audit
    status_log: List[Dict[str, str]] = field(default_factory=list)
    # [{status, timestamp, reason}]

    def transition(self, new_status: EventStatus, reason: str = "") -> None:
        """Record a status transition with timestamp."""
        self.status_log.append({
            "from": self.status.value,
            "to": new_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        })
        self.status = new_status

    @property
    def failure_reason(self) -> str:
        """Convenience property returning the latest transition reason if failed."""
        if self.status in (EventStatus.FAILED, EventStatus.EMERGENCY_STOPPED) and self.status_log:
            return self.status_log[-1].get("reason", "")
        return ""

    def content_hash(self) -> str:
        """Deterministic hash for audit reproducibility."""
        payload = {
            "event_id": self.event_id,
            "status": self.status.value,
            "target_volume_mm": round(self.target_volume_mm, 2),
            "actual_volume_l": round(self.actual_volume_l, 2),
            "validation_outcome": self.validation_outcome.value,
            "command_count": len(self.command_ids),
        }
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


# ============================================================================
# Actuator Registration
# ============================================================================

@dataclass
class ActuatorCapabilities:
    """Hardware capability descriptor for an irrigation actuator."""
    system_type: IrrigationSystemType
    max_flow_rate_lpm: float = 0.0            # Max flow (L/min)
    min_flow_rate_lpm: float = 0.0
    max_pressure_bar: float = 0.0
    min_pressure_bar: float = 0.0
    max_duration_minutes: float = 240.0       # 4h default watchdog

    # Valve configuration
    valve_count: int = 1
    zone_valve_map: Dict[str, List[int]] = field(default_factory=dict)
    # zone_id → [valve_indices]

    # Pivot-specific
    pivot_radius_m: float = 0.0
    pivot_speed_range: Tuple[float, float] = (0.0, 100.0)
    pivot_nozzle_count: int = 0

    # Efficiency
    application_efficiency: float = 0.90
    uniformity_coefficient: float = 0.85      # Christiansen CU

    # Fertigation
    fertigation_capable: bool = False
    fertigation_injector_count: int = 0

    supports_pulse: bool = False
    supports_variable_rate: bool = False       # VRI for pivots


@dataclass
class ActuatorRegistration:
    """Identity + capabilities for a registered irrigation actuator.

    Extends the sensor_runtime device concept with irrigation-specific fields.
    """
    # Core identity (mirrors SensorDeviceRegistration)
    device_id: str
    vendor: VendorId
    model: str
    protocol: DriverProtocol
    firmware_version: str = ""

    # Geographic binding
    farm_id: str = ""
    plot_id: str = ""
    zone_ids: List[str] = field(default_factory=list)
    latitude: float = 0.0
    longitude: float = 0.0

    # Capabilities
    capabilities: ActuatorCapabilities = field(default_factory=ActuatorCapabilities)

    # Safety
    fail_safe_state: FailSafeState = FailSafeState.NORMALLY_CLOSED
    safety_interlocks: List[str] = field(default_factory=list)
    # interlock_ids referencing SafetyInterlock definitions

    # Status
    status: ActuatorStatus = ActuatorStatus.UNKNOWN
    last_seen: str = ""                       # ISO timestamp
    last_command_id: str = ""

    # Communication
    connection_config: Dict[str, Any] = field(default_factory=dict)
    # Protocol-specific: {broker, topic, register_map, api_url, api_key, ...}

    # Linked sensors (for closed-loop validation)
    linked_sensor_ids: List[str] = field(default_factory=list)
    # device_ids of soil moisture / flow sensors in this zone

    # Automation
    automation_mode: AutomationMode = AutomationMode.SEMI_AUTO

    installation_date: str = ""
    notes: str = ""

    def validate(self) -> List[str]:
        """Validate registration completeness."""
        errors = []
        if not self.device_id:
            errors.append("device_id is required")
        if not self.farm_id:
            errors.append("farm_id is required")
        if not self.plot_id:
            errors.append("plot_id is required")
        if not self.zone_ids:
            errors.append("At least one zone_id is required")
        if self.capabilities.max_flow_rate_lpm <= 0:
            errors.append("max_flow_rate_lpm must be > 0")
        return errors


# ============================================================================
# Safety Interlocks
# ============================================================================

@dataclass
class SafetyInterlock:
    """Definition of a safety constraint that triggers emergency action."""
    interlock_id: str
    interlock_type: InterlockType
    description: str

    # Thresholds
    sensor_variable: str = ""                 # CanonicalVariable to monitor
    threshold_min: Optional[float] = None     # Trigger if value < min
    threshold_max: Optional[float] = None     # Trigger if value > max
    duration_seconds: int = 10                # Must persist for N seconds

    # Action
    action_on_trigger: CommandType = CommandType.EMERGENCY_STOP
    auto_reset: bool = False                  # Auto-clear after condition resolves
    requires_manual_reset: bool = True

    # Context
    applies_to_devices: List[str] = field(default_factory=list)
    # Empty = applies to all devices
    enabled: bool = True


@dataclass
class SafetyViolation:
    """Record of a detected safety breach."""
    violation_id: str
    interlock_id: str
    interlock_type: InterlockType
    device_id: str
    zone_id: str

    detected_at: str = ""                     # ISO
    resolved_at: str = ""                     # ISO (empty if unresolved)

    sensor_value: float = 0.0
    threshold_breached: str = ""              # "min" or "max"
    threshold_value: float = 0.0

    action_taken: str = ""                    # EMERGENCY_STOP, ALERT, etc.
    event_id_affected: str = ""               # IrrigationEvent that was interrupted

    acknowledged_by: str = ""
    acknowledged_at: str = ""
    notes: str = ""


# ============================================================================
# Validation Report
# ============================================================================

@dataclass
class ValidationReport:
    """Post-irrigation closed-loop moisture verification report."""
    report_id: str
    event_id: str
    plot_id: str
    zone_id: str

    outcome: ValidationOutcome

    # Soil moisture data
    pre_irrigation_vwc: float = 0.0           # VWC before irrigation
    post_irrigation_vwc: float = 0.0          # VWC after validation window
    expected_vwc_rise: float = 0.0            # Predicted from volume + TAW
    actual_vwc_rise: float = 0.0              # post - pre

    # Timing
    irrigation_completed_at: str = ""
    validation_window_start: str = ""
    validation_window_end: str = ""
    sensor_readings_count: int = 0

    # Sensor sources
    sensor_device_ids: List[str] = field(default_factory=list)

    # Calibration feedback
    delivery_efficiency_actual: float = 0.0   # actual_rise / expected_rise
    calibration_adjustment: float = 0.0       # Proposed adjustment factor

    # Confidence
    confidence: float = 0.0                   # 0-1, based on sensor count + consistency
    notes: str = ""


# ============================================================================
# Water Budget
# ============================================================================

@dataclass
class WaterBudget:
    """Season and daily water quota tracking."""
    plot_id: str
    season: str                               # e.g. "2026-SPRING"

    # Season quota
    season_quota_mm: float = 1000.0
    season_consumed_mm: float = 0.0
    season_remaining_mm: float = 1000.0

    # Daily allocation
    daily_quota_mm: float = 50.0
    daily_consumed_mm: float = 0.0
    daily_remaining_mm: float = 50.0

    # Projections
    projected_season_total_mm: float = 0.0    # Based on ETc forecast
    days_remaining_in_season: int = 0
    avg_daily_rate_mm: float = 0.0

    # Cost
    water_cost_per_m3: float = 0.0            # EUR/m³
    season_cost_eur: float = 0.0

    last_updated: str = ""

    def can_irrigate(self, volume_mm: float) -> Tuple[bool, str]:
        """Check if a given volume can be allocated."""
        if volume_mm > self.season_remaining_mm:
            return False, f"Season quota exceeded: need {volume_mm:.1f}mm, remaining {self.season_remaining_mm:.1f}mm"
        if volume_mm > self.daily_remaining_mm:
            return False, f"Daily quota exceeded: need {volume_mm:.1f}mm, remaining {self.daily_remaining_mm:.1f}mm"
        return True, "OK"


# ============================================================================
# Schedule Entry
# ============================================================================

@dataclass
class IrrigationScheduleEntry:
    """Planned irrigation event with approval workflow."""
    schedule_id: str                          # SCH-{uuid}
    plot_id: str
    zone_id: str
    device_id: str

    # What
    system_type: IrrigationSystemType
    target_volume_mm: float = 0.0
    target_duration_minutes: float = 0.0

    # When
    scheduled_date: str = ""                  # ISO date
    scheduled_time: str = ""                  # ISO time (HH:MM)
    time_window_start: str = ""               # Earliest allowed
    time_window_end: str = ""                 # Latest allowed
    optimal_time: str = ""                    # Best time (e.g. early morning)

    # Why
    source_action_id: str = ""                # L8 ActionCard ID
    urgency: str = "NORMAL"                   # LOW, NORMAL, HIGH, CRITICAL
    reason: str = ""                          # Human-readable explanation

    # Approval
    automation_mode: AutomationMode = AutomationMode.SEMI_AUTO
    approval_status: str = "PENDING"          # PENDING, APPROVED, REJECTED
    approved_by: str = ""
    approved_at: str = ""

    # Weather gate
    weather_ok: bool = True
    rain_forecast_mm: float = 0.0
    deferred_reason: str = ""                 # "Rain >10mm forecast"

    # Constraints
    phenology_ok: bool = True
    quota_ok: bool = True
    safety_ok: bool = True

    # Generated event
    event_id: str = ""                        # Populated when event is created


# ============================================================================
# Irrigation Zone
# ============================================================================

@dataclass
class IrrigationZone:
    """Logical irrigation zone mapping to physical valve groups."""
    zone_id: str
    zone_name: str
    plot_id: str
    farm_id: str

    # Physical
    area_ha: float = 0.0
    system_type: IrrigationSystemType = IrrigationSystemType.DRIP
    valve_ids: List[str] = field(default_factory=list)       # device_ids of valve actuators
    sensor_ids: List[str] = field(default_factory=list)      # linked soil moisture sensors

    # Agronomic context
    soil_type: str = "loam"
    crop: str = ""
    root_depth_m: float = 0.6

    # Operational
    max_concurrent_zones: int = 1              # How many zones can run simultaneously
    watering_order: int = 0                    # Sequential order in multi-zone systems

    # Geometry (for pivot sectors)
    sector_start_deg: float = 0.0
    sector_end_deg: float = 360.0
    distance_from_pivot_m: float = 0.0

    enabled: bool = True
