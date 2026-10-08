"""
Irrigation Runtime — Safety Monitor v1.0.0

Fail-safe interlock system that continuously evaluates sensor telemetry
against configured safety thresholds. Triggers emergency stops, alerts,
and audit records when violations are detected.

Interlock Categories:
  - PRESSURE_LOW:  Pipe burst detection (flow sensor + pressure drop)
  - PRESSURE_HIGH: Over-pressure protection
  - FLOW_ZERO:     Clog or stuck-closed valve detection
  - FLOW_EXCESSIVE: Leak or stuck-open valve detection
  - OVER_DELIVERY:  Volume exceeded target by >20%
  - DURATION_EXCEEDED: Max runtime watchdog
  - FROST_RISK:    Air temperature < 2°C → defer irrigation
  - WATER_QUOTA_EXCEEDED: Season/daily quota enforcement
  - SENSOR_OFFLINE: Critical sensor lost during irrigation
  - ELECTRICAL_FAULT: Actuator power anomaly

All violations are logged with full provenance for the L6 audit trail.
"""

from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from datetime import datetime, timezone
from numbers import Real
from typing import Any, Callable, Dict, List, Optional

from irrigation_runtime.schemas import (
    ActuatorRegistration,
    CommandType,
    InterlockType,
    IrrigationCommand,
    IrrigationEvent,
    EventStatus,
    SafetyInterlock,
    SafetyViolation,
    WaterBudget,
)

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    try:
        from services.agribrain.scientific_contracts.numeric import finite_real
    except ImportError:
        def finite_real(val: Any) -> Optional[float]:
            if isinstance(val, bool) or not isinstance(val, Real):
                return None
            try:
                res = float(val)
                return res if math.isfinite(res) else None
            except Exception:
                return None

logger = logging.getLogger(__name__)


class SharedQuotaStore:
    """Thread-safe / multi-instance shared quota reservation and settlement store.

    Ensures that independent SafetyMonitor and CommandDispatcher instances share
    active reservations and cumulative settled deliveries per plot scope.
    """
    _lock = threading.Lock()
    _reservations: Dict[str, Dict[str, Any]] = {}
    _settled_deliveries: Dict[str, float] = {}

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._reservations.clear()
            cls._settled_deliveries.clear()

    @classmethod
    def reserve(cls, event_id: str, plot_id: str, volume_mm: float) -> None:
        val = finite_real(volume_mm)
        if val is None or val <= 0:
            return
        with cls._lock:
            cls._reservations[event_id] = {
                "plot_id": plot_id,
                "volume_mm": val,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    @classmethod
    def release(cls, event_id: str) -> None:
        with cls._lock:
            cls._reservations.pop(event_id, None)

    @classmethod
    def settle(cls, event_id: str, plot_id: str, volume_mm: float) -> None:
        with cls._lock:
            cls._reservations.pop(event_id, None)
            val = finite_real(volume_mm)
            if val is not None and val > 0:
                cls._settled_deliveries[plot_id] = cls._settled_deliveries.get(plot_id, 0.0) + val

    @classmethod
    def get_reserved(cls, plot_id: str, exclude_event_id: Optional[str] = None) -> float:
        with cls._lock:
            total = 0.0
            for eid, res in cls._reservations.items():
                if eid != exclude_event_id and res.get("plot_id") == plot_id:
                    total += res.get("volume_mm", 0.0)
            return total

    @classmethod
    def get_settled(cls, plot_id: str) -> float:
        with cls._lock:
            return cls._settled_deliveries.get(plot_id, 0.0)


# ============================================================================
# Default Interlock Definitions
# ============================================================================

DEFAULT_INTERLOCKS: List[SafetyInterlock] = [
    SafetyInterlock(
        interlock_id="INT-PRESSURE-LOW",
        interlock_type=InterlockType.PRESSURE_LOW,
        description="Pipe burst detection: pressure drops below safe minimum during operation",
        sensor_variable="irrigation_pressure_bar",
        threshold_min=0.5,
        duration_seconds=15,
        action_on_trigger=CommandType.EMERGENCY_STOP,
        requires_manual_reset=True,
    ),
    SafetyInterlock(
        interlock_id="INT-PRESSURE-HIGH",
        interlock_type=InterlockType.PRESSURE_HIGH,
        description="Over-pressure protection: pressure exceeds system maximum",
        sensor_variable="irrigation_pressure_bar",
        threshold_max=8.0,
        duration_seconds=5,
        action_on_trigger=CommandType.EMERGENCY_STOP,
        requires_manual_reset=True,
    ),
    SafetyInterlock(
        interlock_id="INT-FLOW-ZERO",
        interlock_type=InterlockType.FLOW_ZERO,
        description="Clog detection: no flow detected while valve is commanded open",
        sensor_variable="irrigation_flow_l_min",
        threshold_min=0.1,
        duration_seconds=60,
        action_on_trigger=CommandType.STOP_ZONE,
        requires_manual_reset=False,
    ),
    SafetyInterlock(
        interlock_id="INT-FLOW-EXCESSIVE",
        interlock_type=InterlockType.FLOW_EXCESSIVE,
        description="Leak detection: flow exceeds 200% of commanded rate",
        sensor_variable="irrigation_flow_l_min",
        threshold_max=None,  # Set dynamically based on commanded flow
        duration_seconds=30,
        action_on_trigger=CommandType.EMERGENCY_STOP,
        requires_manual_reset=True,
    ),
    SafetyInterlock(
        interlock_id="INT-FROST",
        interlock_type=InterlockType.FROST_RISK,
        description="Frost protection: air temperature below 2°C",
        sensor_variable="air_temperature_c",
        threshold_min=2.0,
        duration_seconds=300,
        action_on_trigger=CommandType.STOP_ZONE,
        auto_reset=True,
        requires_manual_reset=False,
    ),
    SafetyInterlock(
        interlock_id="INT-DURATION",
        interlock_type=InterlockType.DURATION_EXCEEDED,
        description="Runtime watchdog: zone running beyond maximum allowed duration",
        sensor_variable="",  # Timer-based, not sensor-based
        duration_seconds=0,  # Checked against command duration
        action_on_trigger=CommandType.STOP_ZONE,
        requires_manual_reset=False,
    ),
]


class SafetyMonitor:
    """Continuous safety evaluation engine for irrigation operations.

    Monitors real-time sensor telemetry against configured interlocks
    and triggers appropriate protective actions when violations occur.

    Architecture:
      sensor_runtime telemetry → SafetyMonitor.evaluate()
        → check pressure, flow, temperature, duration
        → if violation: trigger emergency_stop + log violation
        → feed SafetyViolation to L6 ConflictRecord
    """

    def __init__(self, clock: Optional[Callable[[], float]] = None):
        self._interlocks: List[SafetyInterlock] = list(DEFAULT_INTERLOCKS)
        # Active violations indexed by stable key: f"{interlock_id}:{device_id}"
        self._active_violations: Dict[str, SafetyViolation] = {}
        self._violation_history: List[SafetyViolation] = []
        self._violation_callbacks: List[Callable] = []

        # Duration tracking: event_id → {start_time, start_monotonic, max_duration_minutes, device_id, plot_id, volume_mm}
        self._active_events: Dict[str, Dict[str, Any]] = {}
        # Quota reservation: event_id → {plot_id, volume_mm}
        self._reserved_quota: Dict[str, Dict[str, Any]] = {}

        # Debounce breach tracking: active_key -> {first_breach_monotonic, last_breach_monotonic, ...}
        self._breach_tracking: Dict[str, Dict[str, Any]] = {}

        # Monotonic clock source (injected for deterministic testing)
        self._clock: Callable[[], float] = clock if clock is not None else time.monotonic

    # ================================================================
    # Interlock Management
    # ================================================================

    def add_interlock(self, interlock: SafetyInterlock) -> None:
        """Register a custom safety interlock."""
        self._interlocks.append(interlock)
        logger.info("Added safety interlock: %s (%s)",
                     interlock.interlock_id, interlock.interlock_type.value)

    def remove_interlock(self, interlock_id: str) -> None:
        """Remove an interlock by ID."""
        self._interlocks = [i for i in self._interlocks
                            if i.interlock_id != interlock_id]

    def set_interlocks(self, interlocks: List[SafetyInterlock]) -> None:
        """Replace all interlocks with a new set."""
        self._interlocks = list(interlocks)

    def on_violation(self, callback: Callable) -> None:
        """Register a callback for safety violations.

        Callback signature: callback(violation: SafetyViolation) -> None
        """
        self._violation_callbacks.append(callback)

    # ================================================================
    # Event Tracking (for duration watchdog)
    # ================================================================

    def track_event_start(
        self,
        event_id: str,
        device_id: str,
        max_duration_minutes: float,
        plot_id: str = "",
        volume_mm: float = 0.0,
        elapsed_minutes: float = 0.0,
    ) -> None:
        """Register an active irrigation event for duration monitoring and quota reservation."""
        now_dt = datetime.now(timezone.utc)
        start_mono = self._clock() - (max(0.0, elapsed_minutes) * 60.0)
        self._active_events[event_id] = {
            "start_time": now_dt,
            "start_monotonic": start_mono,
            "max_duration_minutes": max_duration_minutes,
            "device_id": device_id,
            "plot_id": plot_id,
            "volume_mm": volume_mm,
        }
        if plot_id and volume_mm > 0:
            self.reserve_quota(event_id, plot_id, volume_mm)
        logger.debug("Tracking event %s (max %.0f min, elapsed %.1f min, reserved %.1f mm)",
                     event_id, max_duration_minutes, elapsed_minutes, volume_mm)

    def track_event_end(self, event_id: str) -> None:
        """Remove an event from duration tracking and release any reservation."""
        self._active_events.pop(event_id, None)
        self.release_quota(event_id)

    def reserve_quota(self, event_id: str, plot_id: str, volume_mm: float) -> None:
        """Explicitly record a quota reservation in the shared store."""
        SharedQuotaStore.reserve(event_id, plot_id, volume_mm)
        if volume_mm > 0:
            self._reserved_quota[event_id] = {
                "plot_id": plot_id,
                "volume_mm": volume_mm,
            }

    def release_quota(self, event_id: str) -> None:
        """Explicitly release a quota reservation in the shared store."""
        SharedQuotaStore.release(event_id)
        self._reserved_quota.pop(event_id, None)

    def settle_quota(self, event_id: str, plot_id: str, volume_mm: float) -> None:
        """Settle a delivered event: release reservation and debit cumulative budget."""
        SharedQuotaStore.settle(event_id, plot_id, volume_mm)
        self._reserved_quota.pop(event_id, None)

    def get_reserved_quota(self, plot_id: str, exclude_event_id: Optional[str] = None) -> float:
        """Calculate total reserved volume (mm) for a plot across all active uncommitted events."""
        shared_total = SharedQuotaStore.get_reserved(plot_id, exclude_event_id=exclude_event_id)
        local_total = 0.0
        for eid, res in self._reserved_quota.items():
            if eid != exclude_event_id and res.get("plot_id") == plot_id:
                local_total += res.get("volume_mm", 0.0)
        return max(shared_total, local_total)

    # ================================================================
    # Core Evaluation
    # ================================================================

    def evaluate(
        self,
        device_id: str,
        sensor_readings: Optional[Dict[str, float]] = None,
        active_command: Optional[IrrigationCommand] = None,
    ) -> List[SafetyViolation]:
        """Evaluate all interlocks against current sensor data.

        Monitors duration watchdog independently and evaluates sensor telemetry.
        Runs unconditionally whether sensor telemetry is present, empty, or None.

        Args:
            device_id: The actuator being monitored
            sensor_readings: Optional dict of CanonicalVariable → current value
            active_command: The currently executing command (for flow limits)

        Returns:
            List of newly detected SafetyViolation records
        """
        new_violations = []

        # 1. Independent duration watchdog check (runs on monotonic timer)
        duration_violations = self._check_duration_watchdog(device_id)
        new_violations.extend(duration_violations)

        # 2. Telemetry sensor interlocks
        readings = sensor_readings if sensor_readings is not None else {}
        for interlock in self._interlocks:
            if not interlock.enabled:
                continue

            # Skip if interlock is device-specific and doesn't apply
            if (interlock.applies_to_devices
                    and device_id not in interlock.applies_to_devices):
                continue

            violation = self._check_interlock(
                interlock, device_id, readings, active_command
            )
            if violation:
                new_violations.append(violation)
                active_key = f"{violation.interlock_id}:{device_id}"
                self._active_violations[active_key] = violation
                self._violation_history.append(violation)

                # Notify callbacks
                for cb in self._violation_callbacks:
                    try:
                        cb(violation)
                    except Exception as exc:
                        logger.error("Violation callback error: %s", exc)

        return new_violations

    def _check_interlock(
        self,
        interlock: SafetyInterlock,
        device_id: str,
        sensor_readings: Dict[str, float],
        active_command: Optional[IrrigationCommand],
    ) -> Optional[SafetyViolation]:
        """Check a single interlock against sensor data with debounce and recovery."""

        # Skip timer-based interlocks (handled by _check_duration_watchdog)
        if not interlock.sensor_variable:
            return None

        active_key = f"{interlock.interlock_id}:{device_id}"

        # If sensor reading is missing or non-finite:
        # "Missing or nonfinite readings cannot count as normal pressure."
        if interlock.sensor_variable not in sensor_readings:
            return None

        raw_val = sensor_readings[interlock.sensor_variable]
        if raw_val is None or isinstance(raw_val, bool) or not isinstance(raw_val, Real):
            return None

        val_float = float(raw_val)
        if math.isnan(val_float) or math.isinf(val_float):
            return None

        value = val_float

        # Dynamic threshold for flow excessive (based on commanded flow)
        threshold_max = interlock.threshold_max
        if (interlock.interlock_type == InterlockType.FLOW_EXCESSIVE
                and active_command
                and active_command.flow_rate_lpm > 0):
            threshold_max = active_command.flow_rate_lpm * 2.0  # 200% of commanded

        # Check thresholds
        breached = False
        threshold_type = ""
        threshold_val = 0.0

        if interlock.threshold_min is not None and value < interlock.threshold_min:
            breached = True
            threshold_type = "min"
            threshold_val = interlock.threshold_min

        if threshold_max is not None and value > threshold_max:
            breached = True
            threshold_type = "max"
            threshold_val = threshold_max

        now_mono = self._clock()

        if breached:
            # Check if this breach already triggered an active violation
            if active_key in self._active_violations:
                # Sustained breach emits only ONE active violation until qualifying reset
                return None

            # Debounce tracking
            if active_key not in self._breach_tracking:
                self._breach_tracking[active_key] = {
                    "first_breach_monotonic": now_mono,
                    "last_breach_monotonic": now_mono,
                    "last_breach_value": value,
                    "threshold_type": threshold_type,
                    "threshold_val": threshold_val,
                }
            else:
                self._breach_tracking[active_key]["last_breach_monotonic"] = now_mono
                self._breach_tracking[active_key]["last_breach_value"] = value

            elapsed = now_mono - self._breach_tracking[active_key]["first_breach_monotonic"]
            if elapsed < interlock.duration_seconds:
                # Debounce period has not elapsed yet
                return None

            # Debounce duration elapsed! Emit violation
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id=interlock.interlock_id,
                interlock_type=interlock.interlock_type,
                device_id=device_id,
                zone_id=active_command.zone_id if active_command else "",
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=value,
                threshold_breached=threshold_type,
                threshold_value=threshold_val,
                action_taken=interlock.action_on_trigger.value,
                event_id_affected=(
                    active_command.source_event_id if active_command else ""
                ),
            )

            logger.warning(
                "🚨 SAFETY VIOLATION: %s on device %s — %s=%s "
                "(threshold %s=%s) → action: %s",
                interlock.interlock_type.value, device_id,
                interlock.sensor_variable, value,
                threshold_type, threshold_val,
                interlock.action_on_trigger.value,
            )

            return violation
        else:
            # Reading is valid, finite, and within nominal bounds
            # 1. Clear un-triggered debounce tracking
            self._breach_tracking.pop(active_key, None)

            # 2. Check for auto-reset qualifying condition
            if active_key in self._active_violations:
                if interlock.auto_reset and not interlock.requires_manual_reset:
                    violation = self._active_violations.pop(active_key)
                    violation.resolved_at = datetime.now(timezone.utc).isoformat()
                    violation.notes = "Auto-reset: telemetry returned to normal range"
                    logger.info(
                        "✅ Interlock %s on device %s auto-reset (value %.2f in normal range)",
                        interlock.interlock_id, device_id, value,
                    )
            return None

    def _check_duration_watchdog(self, device_id: str) -> List[SafetyViolation]:
        """Check if any active events on this device have exceeded max duration."""
        violations = []
        now_dt = datetime.now(timezone.utc)
        now_mono = self._clock()

        expired_events = []
        for event_id, info in list(self._active_events.items()):
            if info["device_id"] != device_id:
                continue

            if "start_monotonic" in info:
                elapsed = (now_mono - info["start_monotonic"]) / 60.0
            else:
                elapsed = (now_dt - info["start_time"]).total_seconds() / 60.0

            if elapsed > info["max_duration_minutes"]:
                active_key = f"INT-DURATION:{device_id}"
                if active_key in self._active_violations:
                    continue

                violation = SafetyViolation(
                    violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                    interlock_id="INT-DURATION",
                    interlock_type=InterlockType.DURATION_EXCEEDED,
                    device_id=device_id,
                    zone_id="",
                    detected_at=now_dt.isoformat(),
                    sensor_value=elapsed,
                    threshold_breached="max",
                    threshold_value=info["max_duration_minutes"],
                    action_taken=CommandType.STOP_ZONE.value,
                    event_id_affected=event_id,
                )
                violations.append(violation)
                self._active_violations[active_key] = violation
                self._violation_history.append(violation)
                expired_events.append(event_id)

                logger.warning(
                    "🚨 DURATION WATCHDOG: Event %s on device %s exceeded "
                    "max duration (%.1f > %.1f min)",
                    event_id, device_id, elapsed, info["max_duration_minutes"]
                )

                for cb in self._violation_callbacks:
                    try:
                        cb(violation)
                    except Exception as exc:
                        logger.error("Violation callback error: %s", exc)

        # R01: Do NOT remove expired events or release quota here before confirmed stop!
        # The dispatcher will attempt stop, and only on confirmed stop will quota/tracking be released.
        return violations

    # ================================================================
    # Water Quota Enforcement
    # ================================================================

    def check_water_quota(
        self,
        budget: WaterBudget,
        requested_volume_mm: float,
        event_id: Optional[str] = None,
    ) -> Optional[SafetyViolation]:
        """Check if an irrigation request would exceed water quota.

        Accounts for baseline budget limits as well as active concurrent reservations.

        Args:
            budget: Current water budget for the plot
            requested_volume_mm: Volume requested in mm
            event_id: Optional event ID being evaluated

        Returns:
            SafetyViolation if quota would be exceeded, None otherwise
        """
        can_irrigate, reason = budget.can_irrigate(requested_volume_mm)
        if not can_irrigate:
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id="",
                zone_id="",
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=requested_volume_mm,
                threshold_breached="max",
                threshold_value=budget.season_remaining_mm,
                action_taken="BLOCK",
                notes=reason,
            )
            logger.warning("🚨 WATER QUOTA VIOLATION: %s", reason)
            self._violation_history.append(violation)
            return violation

        # Account for concurrent uncommitted reservations and cumulative settled deliveries on the same plot
        already_reserved = self.get_reserved_quota(budget.plot_id, exclude_event_id=event_id)
        settled_on_plot = SharedQuotaStore.get_settled(budget.plot_id)
        untracked_settled = max(0.0, settled_on_plot - budget.daily_consumed_mm)

        effective_season_remaining = budget.season_remaining_mm - already_reserved - untracked_settled
        effective_daily_remaining = budget.daily_remaining_mm - already_reserved - untracked_settled

        if requested_volume_mm > effective_season_remaining:
            reason = (
                f"Season quota exceeded by concurrent reservations: need {requested_volume_mm:.1f}mm, "
                f"remaining unreserved {effective_season_remaining:.1f}mm "
                f"({already_reserved:.1f}mm reserved, {untracked_settled:.1f}mm untracked settled)"
            )
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id="",
                zone_id="",
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=requested_volume_mm,
                threshold_breached="max",
                threshold_value=effective_season_remaining,
                action_taken="BLOCK",
                notes=reason,
            )
            logger.warning("🚨 WATER QUOTA CONCURRENT VIOLATION: %s", reason)
            self._violation_history.append(violation)
            return violation

        if requested_volume_mm > effective_daily_remaining:
            reason = (
                f"Daily quota exceeded by concurrent reservations: need {requested_volume_mm:.1f}mm, "
                f"remaining unreserved {effective_daily_remaining:.1f}mm "
                f"({already_reserved:.1f}mm reserved, {untracked_settled:.1f}mm untracked settled)"
            )
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id="",
                zone_id="",
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=requested_volume_mm,
                threshold_breached="max",
                threshold_value=effective_daily_remaining,
                action_taken="BLOCK",
                notes=reason,
            )
            logger.warning("🚨 WATER QUOTA CONCURRENT VIOLATION: %s", reason)
            self._violation_history.append(violation)
            return violation

        return None

    # ================================================================
    # Pre-flight Safety Assessment
    # ================================================================

    def pre_flight_check(
        self,
        command: IrrigationCommand,
        sensor_readings: Optional[Dict[str, float]] = None,
        budget: Optional[WaterBudget] = None,
    ) -> List[SafetyViolation]:
        """Comprehensive pre-dispatch safety assessment.

        Runs all checks before a command is sent to hardware:
          1. Sensor-based interlocks (frost, existing pressure issues)
          2. Water quota check (evaluated unconditionally whenever budget is provided)
          3. Environmental conditions

        Args:
            command: The command about to be dispatched
            sensor_readings: Optional latest sensor data for the zone
            budget: Optional water budget for quota enforcement

        Returns:
            List of blocking violations (empty = safe to proceed)
        """
        violations = []
        readings = sensor_readings if sensor_readings is not None else {}

        # Sensor interlocks (pre-existing conditions)
        sensor_violations = self.evaluate(
            command.device_id, readings, command
        )
        violations.extend(sensor_violations)

        # Water quota check - ALWAYS executed when budget is provided
        if budget is not None and command.volume_mm > 0:
            quota_violation = self.check_water_quota(
                budget, command.volume_mm, event_id=command.source_event_id
            )
            if quota_violation:
                violations.append(quota_violation)

        # Frost check
        air_temp = readings.get("air_temperature_c")
        if air_temp is not None and air_temp < 2.0:
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-FROST",
                interlock_type=InterlockType.FROST_RISK,
                device_id=command.device_id,
                zone_id=command.zone_id,
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=air_temp,
                threshold_breached="min",
                threshold_value=2.0,
                action_taken="DEFER",
                notes=f"Air temperature {air_temp:.1f}°C — frost risk",
            )
            violations.append(violation)

        return violations

    # ================================================================
    # Resolution & Reporting
    # ================================================================

    def resolve_violation(
        self,
        identifier: str,
        acknowledged_by: str,
        notes: str = "",
    ) -> bool:
        """Mark a safety violation as resolved/acknowledged.

        Supports resolving either by violation_id (e.g. VIO-...) or active_key (e.g. INT-PRESSURE-HIGH:DEV-01).
        """
        matched_key = None
        violation = None

        if identifier in self._active_violations:
            matched_key = identifier
            violation = self._active_violations.pop(identifier)
        else:
            for k, v in self._active_violations.items():
                if v.violation_id == identifier:
                    matched_key = k
                    violation = self._active_violations.pop(k)
                    break

        if violation is None:
            return False

        if matched_key:
            self._breach_tracking.pop(matched_key, None)

        violation.resolved_at = datetime.now(timezone.utc).isoformat()
        violation.acknowledged_by = acknowledged_by
        violation.acknowledged_at = violation.resolved_at
        violation.notes = notes

        logger.info("Violation %s resolved by %s", violation.violation_id, acknowledged_by)
        return True

    def rehydrate_active_violations(
        self,
        violations: List[SafetyViolation],
    ) -> None:
        """Rehydrate active violations on process restart."""
        for v in violations:
            if not v.resolved_at:
                active_key = f"{v.interlock_id}:{v.device_id}"
                self._active_violations[active_key] = v
                if v not in self._violation_history:
                    self._violation_history.append(v)

    def get_active_violations(self) -> List[SafetyViolation]:
        """Get all unresolved safety violations."""
        return list(self._active_violations.values())

    def get_violation_history(
        self,
        device_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[SafetyViolation]:
        """Get historical violations, optionally filtered by device."""
        history = self._violation_history
        if device_id:
            history = [v for v in history if v.device_id == device_id]
        return history[-limit:]

    def get_safety_score(self) -> float:
        """Compute a 0-1 safety score for the irrigation system.

        1.0 = no violations, all systems nominal
        0.0 = critical violations present
        """
        active = len(self._active_violations)
        if active == 0:
            return 1.0

        critical_types = {
            InterlockType.PRESSURE_LOW,
            InterlockType.PRESSURE_HIGH,
            InterlockType.ELECTRICAL_FAULT,
        }
        critical_count = sum(
            1 for v in self._active_violations.values()
            if v.interlock_type in critical_types
        )

        if critical_count > 0:
            return 0.0

        # Degrade linearly for non-critical violations
        return max(0.0, 1.0 - (active * 0.2))


# Singleton
safety_monitor = SafetyMonitor()
