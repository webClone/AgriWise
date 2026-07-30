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
import uuid
from datetime import datetime, timezone
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

logger = logging.getLogger(__name__)


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

    def __init__(self):
        self._interlocks: List[SafetyInterlock] = list(DEFAULT_INTERLOCKS)
        self._active_violations: Dict[str, SafetyViolation] = {}
        self._violation_history: List[SafetyViolation] = []
        self._violation_callbacks: List[Callable] = []

        # Duration tracking
        self._active_events: Dict[str, Dict[str, Any]] = {}
        # event_id → {start_time, max_duration_minutes, device_id}

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
    ) -> None:
        """Register an active irrigation event for duration monitoring."""
        self._active_events[event_id] = {
            "start_time": datetime.now(timezone.utc),
            "max_duration_minutes": max_duration_minutes,
            "device_id": device_id,
        }
        logger.debug("Tracking event %s (max %.0f min)", event_id, max_duration_minutes)

    def track_event_end(self, event_id: str) -> None:
        """Remove an event from duration tracking."""
        self._active_events.pop(event_id, None)

    # ================================================================
    # Core Evaluation
    # ================================================================

    def evaluate(
        self,
        device_id: str,
        sensor_readings: Dict[str, float],
        active_command: Optional[IrrigationCommand] = None,
    ) -> List[SafetyViolation]:
        """Evaluate all interlocks against current sensor data.

        This method should be called each time new sensor telemetry
        arrives for a device that has active irrigation.

        Args:
            device_id: The actuator being monitored
            sensor_readings: Dict of CanonicalVariable → current value
            active_command: The currently executing command (for flow limits)

        Returns:
            List of newly detected SafetyViolation records
        """
        new_violations = []

        for interlock in self._interlocks:
            if not interlock.enabled:
                continue

            # Skip if interlock is device-specific and doesn't apply
            if (interlock.applies_to_devices
                    and device_id not in interlock.applies_to_devices):
                continue

            violation = self._check_interlock(
                interlock, device_id, sensor_readings, active_command
            )
            if violation:
                new_violations.append(violation)
                self._active_violations[violation.violation_id] = violation
                self._violation_history.append(violation)

                # Notify callbacks
                for cb in self._violation_callbacks:
                    try:
                        cb(violation)
                    except Exception as exc:
                        logger.error("Violation callback error: %s", exc)

        # Check duration watchdog
        duration_violations = self._check_duration_watchdog(device_id)
        new_violations.extend(duration_violations)

        return new_violations

    def _check_interlock(
        self,
        interlock: SafetyInterlock,
        device_id: str,
        sensor_readings: Dict[str, float],
        active_command: Optional[IrrigationCommand],
    ) -> Optional[SafetyViolation]:
        """Check a single interlock against sensor data."""

        # Skip timer-based interlocks (handled by _check_duration_watchdog)
        if not interlock.sensor_variable:
            return None

        if interlock.sensor_variable not in sensor_readings:
            return None

        value = sensor_readings[interlock.sensor_variable]

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

        if not breached:
            return None

        # Check if already in active violations (avoid duplicates)
        active_key = f"{interlock.interlock_id}:{device_id}"
        if active_key in self._active_violations:
            return None

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

    def _check_duration_watchdog(self, device_id: str) -> List[SafetyViolation]:
        """Check if any active events on this device have exceeded max duration."""
        violations = []
        now = datetime.now(timezone.utc)

        expired_events = []
        for event_id, info in self._active_events.items():
            if info["device_id"] != device_id:
                continue

            elapsed = (now - info["start_time"]).total_seconds() / 60.0
            if elapsed > info["max_duration_minutes"]:
                violation = SafetyViolation(
                    violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                    interlock_id="INT-DURATION",
                    interlock_type=InterlockType.DURATION_EXCEEDED,
                    device_id=device_id,
                    zone_id="",
                    detected_at=now.isoformat(),
                    sensor_value=elapsed,
                    threshold_breached="max",
                    threshold_value=info["max_duration_minutes"],
                    action_taken=CommandType.STOP_ZONE.value,
                    event_id_affected=event_id,
                )
                violations.append(violation)
                self._active_violations[violation.violation_id] = violation
                self._violation_history.append(violation)
                expired_events.append(event_id)

                logger.warning(
                    "🚨 DURATION WATCHDOG: Event %s on device %s exceeded "
                    "max duration (%.0f > %.0f min)",
                    event_id, device_id, elapsed, info["max_duration_minutes"]
                )

        for eid in expired_events:
            self._active_events.pop(eid, None)

        return violations

    # ================================================================
    # Water Quota Enforcement
    # ================================================================

    def check_water_quota(
        self,
        budget: WaterBudget,
        requested_volume_mm: float,
    ) -> Optional[SafetyViolation]:
        """Check if an irrigation request would exceed water quota.

        Args:
            budget: Current water budget for the plot
            requested_volume_mm: Volume requested in mm

        Returns:
            SafetyViolation if quota would be exceeded, None otherwise
        """
        can_irrigate, reason = budget.can_irrigate(requested_volume_mm)
        if can_irrigate:
            return None

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

    # ================================================================
    # Pre-flight Safety Assessment
    # ================================================================

    def pre_flight_check(
        self,
        command: IrrigationCommand,
        sensor_readings: Dict[str, float],
        budget: Optional[WaterBudget] = None,
    ) -> List[SafetyViolation]:
        """Comprehensive pre-dispatch safety assessment.

        Runs all checks before a command is sent to hardware:
          1. Sensor-based interlocks (frost, existing pressure issues)
          2. Water quota check
          3. Environmental conditions

        Args:
            command: The command about to be dispatched
            sensor_readings: Latest sensor data for the zone
            budget: Optional water budget for quota enforcement

        Returns:
            List of blocking violations (empty = safe to proceed)
        """
        violations = []

        # Sensor interlocks (pre-existing conditions)
        sensor_violations = self.evaluate(
            command.device_id, sensor_readings, command
        )
        violations.extend(sensor_violations)

        # Water quota
        if budget and command.volume_mm > 0:
            quota_violation = self.check_water_quota(budget, command.volume_mm)
            if quota_violation:
                violations.append(quota_violation)

        # Frost check
        air_temp = sensor_readings.get("air_temperature_c")
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
        violation_id: str,
        acknowledged_by: str,
        notes: str = "",
    ) -> bool:
        """Mark a safety violation as resolved/acknowledged."""
        violation = self._active_violations.pop(violation_id, None)
        if violation is None:
            return False

        violation.resolved_at = datetime.now(timezone.utc).isoformat()
        violation.acknowledged_by = acknowledged_by
        violation.acknowledged_at = violation.resolved_at
        violation.notes = notes

        logger.info("Violation %s resolved by %s", violation_id, acknowledged_by)
        return True

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
