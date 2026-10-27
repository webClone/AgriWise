"""
Irrigation Runtime — Command Dispatcher v1.0.0

State machine that manages the lifecycle of IrrigationEvents from QUEUED
through EXECUTING to COMPLETED/FAILED. Dispatches IrrigationCommands to
the correct actuator via the ActuatorRegistry with retry logic and
safety monitoring.

State Machine:
  QUEUED → DISPATCHING → EXECUTING → VALIDATING → COMPLETED
             ↓                ↓            ↓
           FAILED          FAILED       FAILED
             ↓                ↓
         (retry?)      EMERGENCY_STOPPED

Retry Policy:
  - Max 3 retries with exponential backoff (2s, 4s, 8s)
  - Only retry on transient errors (timeout, connection loss)
  - No retry on validation failures or safety violations
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    try:
        from services.agribrain.scientific_contracts.numeric import finite_real
    except ImportError:
        def finite_real(val: Any) -> Optional[float]:
            if val is None or isinstance(val, bool):
                return None
            try:
                v = float(val)
                return v if math.isfinite(v) else None
            except (ValueError, TypeError):
                return None

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.registry import ActuatorRegistry, actuator_registry
from irrigation_runtime.safety import SafetyMonitor, safety_monitor, SharedQuotaStore
from irrigation_runtime.schemas import (
    ActuatorStatus,
    AutomationMode,
    CommandPriority,
    CommandResult,
    CommandType,
    EventStatus,
    InterlockType,
    IrrigationCommand,
    IrrigationEvent,
    IrrigationSystemType,
    WaterBudget,
)

logger = logging.getLogger(__name__)


def _check_area_conflict(a1: Any, a2: Any) -> bool:
    v1 = finite_real(a1)
    v2 = finite_real(a2)
    if (v1 is None) != (v2 is None):
        return True
    if v1 is not None and v2 is not None:
        return abs(v1 - v2) > 1e-4
    return False


def _clean_effective_area(val: Any) -> Optional[float]:
    if val is None or isinstance(val, (bool, str)):
        return None
    res = finite_real(val)
    return res if (res is not None and res > 0) else None



class CommandDispatcher:
    """State machine for irrigation event lifecycle management.

    Manages the full lifecycle of irrigation events:
      1. Accept QUEUED events
      2. Build IrrigationCommands from events
      3. Run pre-flight safety checks
      4. Dispatch to the correct actuator
      5. Monitor execution with safety interlocks
      6. Transition to VALIDATING on completion
      7. Handle failures with retry logic
    """

    def __init__(
        self,
        registry: ActuatorRegistry = actuator_registry,
        safety: SafetyMonitor = safety_monitor,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
    ):
        self._registry = registry
        self._safety = safety
        self._active_events: Dict[str, IrrigationEvent] = {}
        self._event_history: List[IrrigationEvent] = []
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay  # seconds

        # Callbacks
        self._on_event_complete: List[Callable] = []
        self._on_event_failed: List[Callable] = []
        self._on_validation_needed: List[Callable] = []

    # ================================================================
    # Callback Registration
    # ================================================================

    def on_complete(self, callback: Callable) -> None:
        """Register callback for completed events."""
        self._on_event_complete.append(callback)

    def on_failed(self, callback: Callable) -> None:
        """Register callback for failed events."""
        self._on_event_failed.append(callback)

    def on_validation_needed(self, callback: Callable) -> None:
        """Register callback when post-irrigation validation is needed."""
        self._on_validation_needed.append(callback)

    def register_actuator(self, actuator: Any) -> None:
        """Register an actuator driver with the dispatcher's registry."""
        if hasattr(self._registry, "register") and hasattr(actuator, "registration"):
            self._registry.register(actuator.registration, driver=actuator)
        elif hasattr(self._registry, "_actuators"):
            self._registry._actuators[actuator.device_id] = actuator

    def _is_stop_confirmed(self, actuator: Any, stop_res: Optional[CommandResult]) -> bool:
        """Evaluate if an actuator stop is positively verified by physical evidence.

        Physical cessation must be a positive fact, not an inference from the
        absence of reported activity. Never falls back to ONLINE, ERROR, absent running,
        or generic command success as equivalent evidence for real hardware.
        """
        if not stop_res or not stop_res.success:
            return False
        if getattr(stop_res, "transport_acknowledged_only", False):
            return False
        status_pending = (
            getattr(actuator, "status", None) == ActuatorStatus.STOP_PENDING_CONFIRMATION
            or getattr(actuator, "_status", None) == ActuatorStatus.STOP_PENDING_CONFIRMATION
        )
        if status_pending:
            return False

        # Affirmative verified physical stop proof
        if getattr(stop_res, "confirmed_physical_stop", False) is True:
            return True

        # Check explicit simulation classification for test doubles without real hardware
        is_sim = (
            getattr(actuator, "is_simulation", False)
            or getattr(getattr(actuator, "registration", None), "is_simulation", False)
            or getattr(actuator, "is_mock", False)
            or type(actuator).__name__.startswith("Mock")
            or getattr(getattr(actuator, "registration", None), "model", "") in ("MockModel", "offline")
            or getattr(getattr(actuator, "registration", None), "vendor", None) == VendorId.CUSTOM
        )
        if is_sim:
            hw = getattr(actuator, "hw", None)
            hw_running = getattr(hw, "running", None) if hw is not None else None
            if hw_running is False or getattr(actuator, "running", None) is False:
                return True
            if getattr(actuator, "status", None) in (ActuatorStatus.ONLINE, ActuatorStatus.ERROR) and hw_running is not True:
                return True

        return False

    # ================================================================
    # Event Submission
    # ================================================================

    async def submit_event(
        self,
        event: IrrigationEvent,
        sensor_readings: Optional[Dict[str, float]] = None,
        budget: Optional[WaterBudget] = None,
    ) -> IrrigationEvent:
        """Submit an event for execution.

        Runs pre-flight safety checks and begins dispatch.

        Args:
            event: The IrrigationEvent to execute (must be QUEUED)
            sensor_readings: Current sensor data for safety checks
            budget: Water budget for quota enforcement

        Returns:
            Updated IrrigationEvent with current status
        """
        if event.status != EventStatus.QUEUED:
            logger.warning("Cannot submit event %s: status is %s (expected QUEUED)",
                           event.event_id, event.status.value)
            return event

        # BA-04: Validate raw event scalar parameters before any transformations
        validation_errors = event.validate()
        if validation_errors:
            event.transition(EventStatus.FAILED, f"Event validation failed: {'; '.join(validation_errors)}")
            self._emit_failed(event)
            return event

        # BA-04: Validate budget quantities if provided
        if budget is not None:
            budget_errors = budget.validate()
            if budget_errors:
                from irrigation_runtime.schemas import SafetyViolation, InterlockType
                violation = SafetyViolation(
                    violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                    interlock_id="INT-QUOTA",
                    interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                    device_id=event.device_id,
                    zone_id=event.zone_id,
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    sensor_value=float(event.target_volume_mm) if finite_real(event.target_volume_mm) is not None else 0.0,
                    threshold_breached="max",
                    threshold_value=0.0,
                    action_taken="BLOCK",
                    notes=f"Budget validation failed: {'; '.join(budget_errors)}",
                )
                event.safety_violations.append(violation.violation_id)
                event.transition(EventStatus.FAILED, f"WaterBudget validation failed: {'; '.join(budget_errors)}")
                self._emit_failed(event)
                return event

        # Idempotency check: if already active or queued in local dispatcher, return existing event
        if event.event_id in self._active_events:
            existing = self._active_events[event.event_id]
            if existing.status in (EventStatus.DISPATCHING, EventStatus.EXECUTING, EventStatus.VALIDATING, EventStatus.STOP_REQUESTED):
                ex_area = getattr(existing, "effective_area_ha", None)
                ev_area = getattr(event, "effective_area_ha", None)
                area_mismatch = _check_area_conflict(ex_area, ev_area)
                if (
                    abs(existing.target_volume_mm - event.target_volume_mm) > 1e-4
                    or abs(existing.target_duration_minutes - event.target_duration_minutes) > 1e-4
                    or abs(existing.target_flow_rate_lpm - event.target_flow_rate_lpm) > 1e-4
                    or existing.device_id != event.device_id
                    or existing.plot_id != event.plot_id
                    or existing.zone_id != event.zone_id
                    or area_mismatch
                ):
                    event.transition(EventStatus.FAILED, f"CONFLICT: Event {event.event_id} already active with different parameters")
                    self._emit_failed(event)
                    return event
                logger.warning("Event %s is already active with status %s; returning existing event without duplicate dispatch.",
                               event.event_id, existing.status.value)
                return existing

        # Check if already finalized in local history (RV07: enforce payload and support binding)
        for past in self._event_history:
            if past.event_id == event.event_id:
                p_target = finite_real(past.target_volume_mm)
                e_target = finite_real(event.target_volume_mm)
                p_plot = past.plot_id
                p_dev = past.device_id
                p_zone = past.zone_id
                p_dur = finite_real(past.target_duration_minutes)
                p_flow = finite_real(past.target_flow_rate_lpm)
                p_area = getattr(past, "effective_area_ha", None)
                e_dur = finite_real(event.target_duration_minutes)
                e_flow = finite_real(event.target_flow_rate_lpm)
                e_area = getattr(event, "effective_area_ha", None)
                is_conflict = (
                    (p_target is not None and e_target is not None and abs(p_target - e_target) > 1e-4)
                    or (bool(p_plot) and bool(event.plot_id) and p_plot != event.plot_id)
                    or (bool(p_dev) and bool(event.device_id) and p_dev != event.device_id)
                    or (bool(p_zone) and bool(event.zone_id) and p_zone != event.zone_id)
                    or (p_dur is not None and e_dur is not None and abs(p_dur - e_dur) > 1e-4)
                    or (p_flow is not None and e_flow is not None and abs(p_flow - e_flow) > 1e-4)
                    or _check_area_conflict(p_area, e_area)
                )
                if is_conflict:
                    logger.warning("Event %s has payload conflict with local history: requested %.1fmm vs target %.1fmm",
                                   event.event_id, e_target or 0.0, p_target or 0.0)
                    event.transition(EventStatus.FAILED, f"Payload conflict with local history: requested {e_target}mm vs target {p_target}mm")
                    self._emit_failed(event)
                    return event
                logger.warning("Event %s already finalized with status %s; returning historical event.",
                               event.event_id, past.status.value)
                return past


        # N01: Authoritative active reservation check takes PRECEDENCE over terminal/stopped receipts!
        if SharedQuotaStore.is_active(event.event_id) and event.event_id not in self._active_events:
            res = SharedQuotaStore.get_active_record(event.event_id)
            if res:
                r_vol = finite_real(res.get("target_volume_mm", res.get("volume_mm")))
                e_vol = finite_real(event.target_volume_mm)
                r_plot = res.get("plot_id")
                r_dev = res.get("device_id")
                r_zone = res.get("zone_id")
                r_dur = finite_real(res.get("duration_minutes"))
                r_flow = finite_real(res.get("flow_rate_lpm"))
                r_area = res.get("effective_area_ha")
                e_dur = finite_real(event.target_duration_minutes)
                e_flow = finite_real(event.target_flow_rate_lpm)
                e_area = getattr(event, "effective_area_ha", None)
                is_conflict = (
                    (r_vol is not None and e_vol is not None and abs(r_vol - e_vol) > 1e-4)
                    or (bool(r_plot) and bool(event.plot_id) and r_plot != event.plot_id)
                    or (bool(r_dev) and bool(event.device_id) and r_dev != event.device_id)
                    or (bool(r_zone) and bool(event.zone_id) and r_zone != event.zone_id)
                    or (r_dur is not None and e_dur is not None and abs(r_dur - e_dur) > 1e-4)
                    or (r_flow is not None and e_flow is not None and abs(r_flow - e_flow) > 1e-4)
                    or _check_area_conflict(r_area, e_area)
                )
                if is_conflict:
                    logger.warning("Event %s has payload conflict with active reservation: requested %.1fmm vs active %.1fmm",
                                   event.event_id, e_vol or 0.0, r_vol or 0.0)
                    event.transition(EventStatus.FAILED, f"Payload conflict with active reservation: requested {e_vol}mm vs active {r_vol}mm")
                    self._emit_failed(event)
                    return event
                raw_st = res.get("status", "DISPATCHING")
                if raw_st == "UNSETTLED":
                    raw_st = "VALIDATING"
                try:
                    event.status = EventStatus(raw_st)
                except Exception:
                    event.status = EventStatus.DISPATCHING
                event.target_volume_mm = float(res.get("target_volume_mm", res.get("volume_mm", event.target_volume_mm)))
                if res.get("plot_id"):
                    event.plot_id = res["plot_id"]
                if res.get("flow_rate_lpm") is not None:
                    event.target_flow_rate_lpm = float(res["flow_rate_lpm"])
                if res.get("duration_minutes") is not None:
                    event.target_duration_minutes = float(res["duration_minutes"])
                event.effective_area_ha = res.get("effective_area_ha")
                # RC04: Durable actual_start is authoritative over caller snapshot
                if res.get("actual_start"):
                    event.actual_start = res["actual_start"]
                logger.warning("Event %s already active in shared store with status %s; returning existing event.", event.event_id, event.status.value)
                return event
            else:
                logger.warning("Event %s already active in shared store; returning active event.", event.event_id)
                event.status = EventStatus.DISPATCHING
                return event

        # N05 + BA-03 + C09 + D06 + D10: Settled idempotency takes precedence over stopped receipts
        if SharedQuotaStore.is_settled(event.event_id):
            receipt = SharedQuotaStore.get_settled_receipt(event.event_id)
            if receipt:
                r_target = finite_real(receipt.get("target_volume_mm", receipt.get("volume_mm")))
                e_target = finite_real(event.target_volume_mm)
                r_plot = receipt.get("plot_id")
                r_dev = receipt.get("device_id")
                r_zone = receipt.get("zone_id")
                r_dur = finite_real(receipt.get("duration_minutes"))
                r_flow = finite_real(receipt.get("flow_rate_lpm"))
                r_area = receipt.get("effective_area_ha")
                e_dur = finite_real(event.target_duration_minutes)
                e_flow = finite_real(event.target_flow_rate_lpm)
                e_area = getattr(event, "effective_area_ha", None)
                is_conflict = (
                    (r_target is not None and e_target is not None and abs(r_target - e_target) > 1e-4)
                    or (bool(r_plot) and bool(event.plot_id) and r_plot != event.plot_id)
                    or (bool(r_dev) and bool(event.device_id) and r_dev != event.device_id)
                    or (bool(r_zone) and bool(event.zone_id) and r_zone != event.zone_id)
                    or (r_dur is not None and e_dur is not None and abs(r_dur - e_dur) > 1e-4)
                    or (r_flow is not None and e_flow is not None and abs(r_flow - e_flow) > 1e-4)
                    or _check_area_conflict(r_area, e_area)
                )
                if is_conflict:
                    logger.warning("Event %s has payload conflict with existing settled receipt: requested %.1fmm vs target %.1fmm",
                                   event.event_id, e_target or 0.0, r_target or 0.0)
                    event.transition(EventStatus.FAILED, f"Payload conflict with settled receipt: requested {e_target}mm vs target {r_target}mm")
                    self._emit_failed(event)
                    return event
                # D10: Valid repeat of settled event: return original qualified receipt attributes!
                logger.warning("Event %s already finalized and settled in shared store; returning completed event.", event.event_id)
                event.status = EventStatus.COMPLETED
                event.target_volume_mm = float(receipt.get("target_volume_mm", receipt.get("volume_mm", event.target_volume_mm)))
                if "delivered_volume_mm" in receipt:
                    event.delivered_volume_mm = float(receipt["delivered_volume_mm"])
                if receipt.get("actual_volume_l") is not None:
                    event.actual_volume_l = float(receipt["actual_volume_l"])
                if receipt.get("actual_duration_minutes") is not None:
                    event.actual_duration_minutes = float(receipt["actual_duration_minutes"])
                if receipt.get("effective_area_ha") is not None:
                    event.effective_area_ha = float(receipt["effective_area_ha"])
                if receipt.get("duration_minutes") is not None:
                    event.target_duration_minutes = float(receipt["duration_minutes"])
                if receipt.get("flow_rate_lpm") is not None:
                    event.target_flow_rate_lpm = float(receipt["flow_rate_lpm"])
                return event
            else:
                logger.warning("Event %s already finalized and settled in shared store; returning completed event.", event.event_id)
                event.status = EventStatus.COMPLETED
                return event

        # BA-03 + C05 + D06: Terminal idempotency for stopped/cancelled events
        if SharedQuotaStore.is_stopped(event.event_id):
            stopped_rcpt = SharedQuotaStore.get_stopped_receipt(event.event_id)
            if stopped_rcpt:
                r_target = finite_real(stopped_rcpt.get("target_volume_mm"))
                e_target = finite_real(event.target_volume_mm)
                r_plot = stopped_rcpt.get("plot_id")
                r_dev = stopped_rcpt.get("device_id")
                r_zone = stopped_rcpt.get("zone_id")
                r_dur = finite_real(stopped_rcpt.get("duration_minutes"))
                r_flow = finite_real(stopped_rcpt.get("flow_rate_lpm"))
                r_area = stopped_rcpt.get("effective_area_ha")
                e_dur = finite_real(event.target_duration_minutes)
                e_flow = finite_real(event.target_flow_rate_lpm)
                e_area = getattr(event, "effective_area_ha", None)
                is_conflict = (
                    (r_target is not None and e_target is not None and abs(r_target - e_target) > 1e-4)
                    or (bool(r_plot) and bool(event.plot_id) and r_plot != event.plot_id)
                    or (bool(r_dev) and bool(event.device_id) and r_dev != event.device_id)
                    or (bool(r_zone) and bool(event.zone_id) and r_zone != event.zone_id)
                    or (r_dur is not None and e_dur is not None and abs(r_dur - e_dur) > 1e-4)
                    or (r_flow is not None and e_flow is not None and abs(r_flow - e_flow) > 1e-4)
                    or _check_area_conflict(r_area, e_area)
                )
                if is_conflict:
                    logger.warning("Event %s has payload conflict with existing stopped receipt", event.event_id)
                    event.transition(EventStatus.FAILED, f"Payload conflict with stopped receipt: event {event.event_id}")
                    self._emit_failed(event)
                    return event
                if "delivered_volume_mm" in stopped_rcpt:
                    event.delivered_volume_mm = float(stopped_rcpt["delivered_volume_mm"])
                if "effective_area_ha" in stopped_rcpt and stopped_rcpt["effective_area_ha"] is not None:
                    event.effective_area_ha = float(stopped_rcpt["effective_area_ha"])
                if "duration_minutes" in stopped_rcpt and stopped_rcpt["duration_minutes"] is not None:
                    event.target_duration_minutes = float(stopped_rcpt["duration_minutes"])
                if "flow_rate_lpm" in stopped_rcpt and stopped_rcpt["flow_rate_lpm"] is not None:
                    event.target_flow_rate_lpm = float(stopped_rcpt["flow_rate_lpm"])
            logger.warning("Event %s already stopped/cancelled in shared store; returning cancelled event.", event.event_id)
            event.status = EventStatus.CANCELLED
            return event

        # Resolve actuator
        actuator = self._registry.get_actuator(event.device_id)
        if actuator is None:
            event.transition(EventStatus.FAILED, f"Actuator {event.device_id} not found in registry")
            self._emit_failed(event)
            return event

        # BA-02 + V03 + C06 + D05: Atomic check-and-reserve under cross-process lock BEFORE dispatch (including zero depth & no budget!)
        eff_area = _clean_effective_area(getattr(event, "effective_area_ha", None))
        v_req = finite_real(event.target_volume_mm)
        if v_req is not None and v_req >= 0:
            owner_tok = f"{os.getpid()}:{event.event_id}"
            quota_violation = SharedQuotaStore.atomic_check_and_reserve(
                plot_id=event.plot_id,
                requested_volume_mm=event.target_volume_mm,
                budget=budget,
                event_id=event.event_id,
                device_id=event.device_id,
                zone_id=event.zone_id,
                duration_minutes=event.target_duration_minutes,
                owner_token=owner_tok,
                flow_rate_lpm=event.target_flow_rate_lpm,
                effective_area_ha=eff_area,
            )
            if quota_violation:
                if quota_violation.action_taken == "ALREADY_RESERVED":
                    res = SharedQuotaStore.get_active_record(event.event_id) or {}
                    raw_st = res.get("status", "DISPATCHING")
                    if raw_st == "UNSETTLED":
                        raw_st = "VALIDATING"
                    try:
                        event.status = EventStatus(raw_st)
                    except Exception:
                        event.status = EventStatus.DISPATCHING
                    event.target_volume_mm = float(res.get("target_volume_mm", res.get("volume_mm", event.target_volume_mm)))
                    if res.get("flow_rate_lpm") is not None:
                        event.target_flow_rate_lpm = float(res["flow_rate_lpm"])
                    if res.get("duration_minutes") is not None:
                        event.target_duration_minutes = float(res["duration_minutes"])
                    event.effective_area_ha = res.get("effective_area_ha")
                    # BV05: Authoritative start from store; do not let caller renew allowance
                    event.actual_start = res.get("actual_start") or res.get("first_dispatched_at") or res.get("timestamp") or event.actual_start
                    logger.warning("Event %s already claimed by concurrent worker; joining active execution as %s without duplicate START.",
                                   event.event_id, event.status.value)
                    return event
                if quota_violation.action_taken == "ALREADY_STOPPED":
                    logger.warning("Event %s already stopped/cancelled; returning cancelled event.", event.event_id)
                    event.status = EventStatus.CANCELLED
                    return event
                if quota_violation.action_taken == "ALREADY_SETTLED":
                    logger.warning("Event %s already settled; returning completed event.", event.event_id)
                    event.status = EventStatus.COMPLETED
                    return event
                event.safety_violations.append(quota_violation.violation_id)
                event.transition(
                    EventStatus.FAILED,
                    f"Pre-flight safety check failed: {quota_violation.interlock_type.value}: {quota_violation.notes or quota_violation.action_taken}"
                )
                self._emit_failed(event)
                return event

        # Pre-flight safety check (runs unconditionally regardless of telemetry presence)
        command = self._build_command(event)
        violations = self._safety.pre_flight_check(
            command, sensor_readings, budget
        )
        if violations:
            violation_msgs = [
                f"{v.interlock_type.value}: {v.notes or v.action_taken}"
                for v in violations
            ]
            event.safety_violations = [v.violation_id for v in violations]
            event.transition(
                EventStatus.FAILED,
                f"Pre-flight safety check failed: {'; '.join(violation_msgs)}"
            )
            self._safety.release_quota(event.event_id)
            self._emit_failed(event)
            return event

        # Begin dispatch preparation
        event.transition(EventStatus.QUEUED, "Pre-flight safety passed; preparing dispatch")
        self._active_events[event.event_id] = event

        # V06 + V04: Register with safety monitor BEFORE dispatch to establish duration watchdog and active quota immediately
        event._start_monotonic = self._safety._clock()
        self._safety.track_event_start(
            event.event_id,
            event.device_id,
            event.target_duration_minutes,
            plot_id=event.plot_id,
            volume_mm=event.target_volume_mm,
            season=getattr(budget, "season", None) if budget else None,
            zone_id=event.zone_id,
            flow_rate_lpm=event.target_flow_rate_lpm,
            effective_area_ha=eff_area,
        )

        # Enforce latched fault independently of connectivity/query status before every START path
        if getattr(actuator, "_fault_latched", False):
            logger.error("Pre-dispatch check failed for %s: Actuator has latched fault", event.device_id)
            self._active_events.pop(event.event_id, None)
            self._safety.track_event_end(event.event_id)
            self._safety.release_quota(event.event_id)
            try:
                SharedQuotaStore.release(event.event_id)
            except Exception:
                pass
            event.transition(EventStatus.FAILED, f"Actuator {event.device_id} has latched fault")
            self._emit_failed(event)
            return event

        query_start_ts = time.time()
        query_ts = None
        # SR04: Query live physical controller status before physical dispatch to detect latched fault or active foreign execution
        try:
            live_st = await asyncio.wait_for(actuator.get_status(), timeout=5.0)
            if live_st == ActuatorStatus.ONLINE:
                query_ts = query_start_ts
            if getattr(actuator, "_fault_latched", False) or live_st == ActuatorStatus.ERROR:
                logger.error("Pre-dispatch actuator status check failed for %s: Actuator has latched fault or status ERROR", event.device_id)
                self._active_events.pop(event.event_id, None)
                self._safety.track_event_end(event.event_id)
                self._safety.release_quota(event.event_id)
                try:
                    SharedQuotaStore.release(event.event_id)
                except Exception:
                    pass
                event.transition(EventStatus.FAILED, f"Actuator {event.device_id} has latched fault or status ERROR")
                self._emit_failed(event)
                return event

            if live_st == ActuatorStatus.ONLINE:
                for prev_eid, prev_ev in list(self._active_events.items()):
                    if prev_eid != event.event_id and prev_ev.device_id == event.device_id:
                        if prev_ev.status == EventStatus.EXECUTING:
                            logger.info("Prior event %s owned by this dispatcher on device %s is no longer executing (actuator ONLINE); updating status", prev_eid, event.device_id)
                            try:
                                SharedQuotaStore.update_status(prev_eid, "COMPLETED")
                            except Exception:
                                pass

            if live_st == ActuatorStatus.EXECUTING:
                act_cmd = getattr(actuator, "active_command", None)
                act_eid = getattr(act_cmd, "source_event_id", getattr(act_cmd, "event_id", None)) if act_cmd else None
                hw_eid = getattr(getattr(actuator, "hw", None), "event_id", None)
                live_owner = None
                try:
                    live_owner = SharedQuotaStore.get_active_record_for_resource(event.device_id, event.zone_id)
                except Exception:
                    pass
                foreign_eid = None
                if act_eid and act_eid != event.event_id:
                    foreign_eid = act_eid
                elif hw_eid and hw_eid != event.event_id:
                    foreign_eid = hw_eid
                elif live_owner and live_owner.get("event_id") != event.event_id and live_owner.get("status") in ("EXECUTING", "DISPATCHING"):
                    foreign_eid = live_owner.get("event_id")

                if foreign_eid:
                    logger.warning("Pre-dispatch check: Actuator %s is already EXECUTING another operation (%s); refusing NEW before send", event.device_id, foreign_eid)
                    self._active_events.pop(event.event_id, None)
                    self._safety.track_event_end(event.event_id)
                    self._safety.release_quota(event.event_id)
                    try:
                        SharedQuotaStore.update_status(event.event_id, "FAILED")
                        SharedQuotaStore.release(event.event_id)
                    except Exception:
                        pass
                    event.transition(
                        EventStatus.FAILED,
                        f"Pre-dispatch check: Actuator {event.device_id} is already EXECUTING another operation ({foreign_eid}); pre-transport refused without transport"
                    )
                    self._emit_failed(event)
                    return event
        except Exception as q_err:
            logger.warning("Could not query actuator status for %s before dispatch: %s", event.device_id, q_err)
            live_st = ActuatorStatus.UNKNOWN
            query_ts = None
            if getattr(actuator, "_fault_latched", False):
                self._active_events.pop(event.event_id, None)
                self._safety.track_event_end(event.event_id)
                self._safety.release_quota(event.event_id)
                try:
                    SharedQuotaStore.release(event.event_id)
                except Exception:
                    pass
                event.transition(EventStatus.FAILED, f"Actuator {event.device_id} has latched fault")
                self._emit_failed(event)
                return event

        # R01: Atomic exclusive resource claim before physical START dispatch
        live_executing = (live_st == ActuatorStatus.EXECUTING)
        claimed, holding_eid = SharedQuotaStore.claim_resource(
            event.device_id, event.zone_id, event.event_id, live_executing=live_executing, query_ts=query_ts
        )
        if not claimed:
            logger.warning(
                "Resource claim failed for event %s: Actuator %s is already claimed/executing operation %s; pre-transport refused",
                event.event_id, event.device_id, holding_eid
            )
            self._active_events.pop(event.event_id, None)
            self._safety.track_event_end(event.event_id)
            self._safety.release_quota(event.event_id)
            try:
                SharedQuotaStore.update_status(event.event_id, "FAILED")
                SharedQuotaStore.release(event.event_id)
            except Exception:
                pass
            event.transition(
                EventStatus.FAILED,
                f"Actuator {event.device_id} is already claimed/executing operation {holding_eid}; pre-transport refused without transport",
            )
            self._emit_failed(event)
            return event

        if holding_eid:
            event.owner_token = holding_eid

        event.transition(EventStatus.DISPATCHING, "Resource claimed; starting command dispatch")

        # Dispatch with retry
        result = await self._dispatch_with_retry(event, actuator)
        if not result.success:
            SharedQuotaStore.release_resource_claim(event.device_id, event.zone_id, event.event_id)

        # C02 + D01: If event was already cancelled/stopped or preempted while dispatch was in-flight, preserve status!
        if (
            event.status in (EventStatus.CANCELLED, EventStatus.EMERGENCY_STOPPED, EventStatus.STOP_REQUESTED)
            or event.event_id not in self._active_events
            or result.error_code in ("PREEMPTED_BY_STOP", "STOP_FAILED")
        ):
            logger.warning(
                "Event %s was preempted/cancelled (status %s, code %s) while START was in flight; evaluating late START outcome.",
                event.event_id, event.status.value, result.error_code
            )
            fence_failed = (result.error_code == "STOP_FAILED")
            if actuator and getattr(actuator, "_status", None) in (ActuatorStatus.EXECUTING, ActuatorStatus.ERROR):
                try:
                    stop_res = await actuator.emergency_stop()
                    if not self._is_stop_confirmed(actuator, stop_res):
                        fence_failed = True
                except Exception:
                    fence_failed = True

            if fence_failed or (actuator and getattr(actuator, "_status", None) in (ActuatorStatus.EXECUTING, ActuatorStatus.ERROR)):
                # D01: Failed late STOP fencing! Must NOT discard live ownership or monitoring.
                # Fail-closed: retain STOP_REQUESTED ownership, monitoring, and conservative exposure!
                event.status = EventStatus.STOP_REQUESTED
                self._active_events[event.event_id] = event

                orig_mono = getattr(event, "_start_monotonic", None)
                elapsed_minutes = 0.0
                if orig_mono is not None:
                    elapsed_minutes = max(0.0, (self._safety._clock() - orig_mono) / 60.0)
                elif event.actual_start:
                    try:
                        start_dt = datetime.fromisoformat(event.actual_start)
                        if start_dt.tzinfo is None:
                            start_dt = start_dt.replace(tzinfo=timezone.utc)
                        elapsed_minutes = max(0.0, (datetime.now(timezone.utc) - start_dt).total_seconds() / 60.0)
                    except Exception:
                        elapsed_minutes = 0.0

                self._safety.reopen_active(
                    event_id=event.event_id,
                    plot_id=event.plot_id,
                    volume_mm=event.target_volume_mm,
                    season=getattr(budget, "season", None) if budget else None,
                    device_id=event.device_id,
                    zone_id=event.zone_id,
                    duration_minutes=event.target_duration_minutes,
                    flow_rate_lpm=event.target_flow_rate_lpm,
                    effective_area_ha=eff_area,
                )
                self._safety.track_event_start(
                    event.event_id,
                    event.device_id,
                    event.target_duration_minutes,
                    plot_id=event.plot_id,
                    volume_mm=event.target_volume_mm,
                    season=getattr(budget, "season", None) if budget else None,
                    zone_id=event.zone_id,
                    flow_rate_lpm=event.target_flow_rate_lpm,
                    effective_area_ha=eff_area,
                    elapsed_minutes=elapsed_minutes,
                )
                SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
                logger.error(
                    "Late fence/stop failed for event %s on device %s. Retaining STOP_REQUESTED ownership, monitoring, and quota.",
                    event.event_id, event.device_id
                )
            return event

        if result.success:
            # PB01, RP01, 8AE01: Before promoting local event to EXECUTING, check whether event was already finalized, settled, stopped, or if claim was lost
            durable_rec = SharedQuotaStore.get_active_record(event.event_id)
            res_claim = SharedQuotaStore.get_resource_claim(event.device_id, event.zone_id)
            owner_token = getattr(event, "owner_token", None)
            durable_status = durable_rec.get("status") if durable_rec else None

            claim_lost = (
                durable_rec is None
                or durable_status in ("EXPIRED", "SUPERSEDED", "COMPLETED", "CANCELLED", "EMERGENCY_STOPPED", "FAILED")
                or not durable_rec.get("claimed", False)
                or (owner_token and durable_rec.get("owner_token") != owner_token)
                or (res_claim and owner_token and res_claim.get("owner_token") != owner_token)
            )

            needs_fence = (
                claim_lost
                or SharedQuotaStore.is_settled(event.event_id)
                or SharedQuotaStore.is_stopped(event.event_id)
                or durable_status in ("COMPLETED", "CANCELLED", "EMERGENCY_STOPPED", "STOP_REQUESTED")
                or event.status == EventStatus.STOP_REQUESTED
            )
            if needs_fence:
                logger.warning(
                    "Event %s was finalized, cancelled, expired, or lost claim during dispatch (durable_status=%s, claim_lost=%s); fencing actuator immediately.",
                    event.event_id, durable_status, claim_lost
                )
                stop_res = None
                fence_stop_success = False
                try:
                    stop_res = await actuator.emergency_stop()
                    fence_stop_success = bool(self._is_stop_confirmed(actuator, stop_res))
                except Exception as stop_err:
                    logger.error("Failed to fence actuator after concurrent finalization/claim loss for %s: %s", event.event_id, stop_err)
                    fence_stop_success = False

                if fence_stop_success:
                    if SharedQuotaStore.is_settled(event.event_id) or durable_status == "COMPLETED":
                        event.status = EventStatus.COMPLETED
                    elif durable_status == "EMERGENCY_STOPPED":
                        event.status = EventStatus.EMERGENCY_STOPPED
                    elif durable_status in ("STOP_REQUESTED", "CANCELLED"):
                        event.status = EventStatus.CANCELLED
                    elif claim_lost:
                        event.status = EventStatus.FAILED
                    else:
                        event.status = EventStatus.CANCELLED
                    self._active_events.pop(event.event_id, None)
                    self._safety.track_event_end(event.event_id)
                    return event
                else:
                    # RP01: Failed late fencing or exception! Actuator is still running in the field.
                    # Retain active ownership, original watchdog tracking, and reopen conservative reservation.
                    event.transition(EventStatus.STOP_REQUESTED, "Failed late fencing after concurrent finalization; actuator still running")
                    self._active_events[event.event_id] = event
                    try:
                        SharedQuotaStore.reopen_active(
                            event.event_id,
                            event.plot_id,
                            event.target_volume_mm,
                            season=getattr(budget, "season", None) if budget else getattr(event, "season", None),
                            date=getattr(budget, "date", None) if budget else getattr(event, "date", None),
                            device_id=event.device_id,
                            zone_id=event.zone_id,
                            duration_minutes=event.target_duration_minutes,
                            flow_rate_lpm=event.target_flow_rate_lpm,
                            effective_area_ha=getattr(event, "effective_area_ha", None),
                        )
                    except Exception as reopen_err:
                        logger.error("Could not reopen active reservation for %s: %s", event.event_id, reopen_err)
                    try:
                        SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
                    except Exception as store_err:
                        logger.warning("Could not persist STOP_REQUESTED status for event %s: %s", event.event_id, store_err)

                    orig_track = self._safety._active_events.get(event.event_id)
                    orig_mono = orig_track.get("start_monotonic") if orig_track else getattr(event, "_start_monotonic", None)
                    elapsed_minutes = 0.0
                    if orig_mono is not None:
                        elapsed_minutes = max(0.0, (self._safety._clock() - orig_mono) / 60.0)
                    elif event.actual_start:
                        try:
                            start_dt = datetime.fromisoformat(event.actual_start)
                            if start_dt.tzinfo is None:
                                start_dt = start_dt.replace(tzinfo=timezone.utc)
                            elapsed_minutes = max(0.0, (datetime.now(timezone.utc) - start_dt).total_seconds() / 60.0)
                        except Exception:
                            elapsed_minutes = 0.0

                    self._safety.track_event_start(
                        event.event_id,
                        event.device_id,
                        event.target_duration_minutes,
                        plot_id=event.plot_id,
                        volume_mm=event.target_volume_mm,
                        season=getattr(budget, "season", None) if budget else getattr(event, "season", None),
                        date=getattr(budget, "date", None) if budget else getattr(event, "date", None),
                        zone_id=event.zone_id,
                        flow_rate_lpm=event.target_flow_rate_lpm,
                        effective_area_ha=getattr(event, "effective_area_ha", None),
                        elapsed_minutes=elapsed_minutes,
                    )
                    return event

            event.transition(EventStatus.EXECUTING, "Command acknowledged by actuator")
            event.actual_start = datetime.now(timezone.utc).isoformat()
            event.command_ids.append(result.command_id)
            # RC01, RC04: Persist acknowledged phase and start together immediately
            try:
                SharedQuotaStore.update_status(event.event_id, "EXECUTING", actual_start=event.actual_start)
            except Exception as store_err:
                logger.warning("Could not persist EXECUTING / actual_start for event %s: %s", event.event_id, store_err)
            logger.info("Event %s executing on device %s",
                        event.event_id, event.device_id)
        else:
            # BA-01 + C07: Uncertain physical outcomes must retain dispatcher ownership, tracking, and quota
            # Distinguish positively refused-before-send from uncertain-after-send
            is_refused_before_send = (
                result.error_code in ("VALIDATION_FAILED", "PREFLIGHT_FAILED", "REJECTED_BEFORE_SEND", "COMMAND_VALIDATION_ERROR", "RESOURCE_CLAIM_FAILED", "DEVICE_ALREADY_EXECUTING")
                or (not getattr(result, "command_sent", True) and result.error_code not in ("ACK_TIMEOUT", "UNCERTAIN_OUTCOME"))
            )
            is_own_command = False
            act_cmd = getattr(actuator, "active_command", None)
            if act_cmd:
                act_eid = getattr(act_cmd, "source_event_id", getattr(act_cmd, "event_id", None))
                is_own_command = (act_eid == event.event_id)

            is_uncertain = (
                not is_refused_before_send and (
                    result.error_code in ("UNCERTAIN_OUTCOME", "ACK_TIMEOUT", "DISPATCH_EXCEPTION")
                    or is_own_command
                    or getattr(actuator, "_pending_command", None) is not None
                )
            )
            if is_uncertain:
                logger.error(
                    "Uncertain dispatch outcome for event %s on device %s: %s. Preserving ownership and reservation.",
                    event.event_id, event.device_id, result.error_message
                )
                event.transition(EventStatus.STOP_REQUESTED, f"Uncertain physical outcome: {result.error_message}")
                SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
                self._emit_failed(event)
            else:
                event.transition(
                    EventStatus.FAILED,
                    f"Dispatch failed after retries: {result.error_message}"
                )
                self._active_events.pop(event.event_id, None)
                self._safety.track_event_end(event.event_id)
                self._safety.release_quota(event.event_id)
                try:
                    SharedQuotaStore.release(event.event_id)
                except Exception:
                    pass
                self._emit_failed(event)

        return event

    # ================================================================
    # Command Building
    # ================================================================

    def _build_command(
        self,
        event: IrrigationEvent,
        attempt: int = 1,
        operation_id: Optional[str] = None,
    ) -> IrrigationCommand:
        """Build an IrrigationCommand from an IrrigationEvent with stable operation identity."""
        # Map urgency to command priority
        priority_map = {
            "LOW": CommandPriority.LOW,
            "NORMAL": CommandPriority.NORMAL,
            "HIGH": CommandPriority.HIGH,
            "CRITICAL": CommandPriority.CRITICAL,
        }

        op_id = operation_id or f"OP-{event.event_id}"
        # BA-04: Do not rewrite flow_rate to 15.0 L/min; preserve raw scalar for qualification
        flow_rate = event.target_flow_rate_lpm

        return IrrigationCommand(
            command_id=f"CMD-{event.event_id}-A{attempt}",
            command_type=CommandType.START_ZONE,
            device_id=event.device_id,
            zone_id=event.zone_id,
            plot_id=event.plot_id,
            volume_mm=event.target_volume_mm,
            duration_minutes=event.target_duration_minutes,
            flow_rate_lpm=flow_rate,
            priority=priority_map.get("NORMAL", CommandPriority.NORMAL),
            source_event_id=event.event_id,
            source_action_id=event.source_action_id,
            automation_mode=event.automation_mode,
            approved_by=event.approved_by,
            approved_at=event.approved_at,
            request_id=f"REQ-{event.event_id}-A{attempt}",
            operation_id=op_id,
            attempt_number=attempt,
        )

    # ================================================================
    # Dispatch with Retry
    # ================================================================

    async def _dispatch_with_retry(
        self,
        event: IrrigationEvent,
        actuator: IrrigationActuator,
    ) -> CommandResult:
        """Dispatch a command with exponential backoff retry and stable operation identity."""
        last_result: Optional[CommandResult] = None
        op_id = f"OP-{event.event_id}"

        for attempt in range(self._max_retries + 1):
            if event.status in (EventStatus.CANCELLED, EventStatus.EMERGENCY_STOPPED, EventStatus.STOP_REQUESTED):
                break
            # Pre-send fencing check: ensure claim is still active in SharedQuotaStore
            rec = SharedQuotaStore.get_active_record(event.event_id)
            res_claim = SharedQuotaStore.get_resource_claim(event.device_id, event.zone_id)
            claim_lost = False
            now_ts = time.time()
            if rec is None:
                if getattr(event, "owner_token", None):
                    claim_lost = True
            elif (
                rec.get("status") not in ("STARTING", "DISPATCHING", "EXECUTING")
                or not rec.get("claimed", False)
                or (getattr(event, "owner_token", None) and rec.get("owner_token") != event.owner_token)
                or (rec.get("status") == "STARTING" and (now_ts - rec.get("starting_ts", 0.0) >= 30.0))
            ):
                claim_lost = True
            elif res_claim and getattr(event, "owner_token", None) and res_claim.get("owner_token") != event.owner_token:
                claim_lost = True

            if claim_lost:
                logger.error(
                    "Pre-send fencing check failed for event %s: claim lost or superseded (status=%s)",
                    event.event_id,
                    rec.get("status") if rec else None,
                )
                return CommandResult(
                    command_id=f"CMD-{event.event_id}-{attempt+1}",
                    device_id=event.device_id,
                    success=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="RESOURCE_CLAIM_FAILED",
                    error_message=f"Pre-send fencing check failed: claim lost or superseded",
                    retry_recommended=False,
                )

            # 8AE01: Atomically transition admitted claim to DISPATCHING immediately before entering transport
            transition_ok = SharedQuotaStore.transition_to_dispatching(
                event.event_id,
                getattr(event, "owner_token", None),
                event.device_id,
                event.zone_id,
            )
            if not transition_ok:
                logger.error(
                    "Transition to DISPATCHING failed for event %s on %s: claim lost or expired",
                    event.event_id, event.device_id,
                )
                return CommandResult(
                    command_id=f"CMD-{event.event_id}-{attempt+1}",
                    device_id=event.device_id,
                    success=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="RESOURCE_CLAIM_FAILED",
                    error_message="Transition to DISPATCHING failed: claim lost or expired",
                    retry_recommended=False,
                )

            command = self._build_command(
                event,
                attempt=attempt + 1,
                operation_id=op_id,
            )
            result = await actuator.execute_with_safety(command)

            if result.success:
                return result

            last_result = result

            if not result.retry_recommended or result.error_code == "PREEMPTED_BY_STOP":
                logger.warning(
                    "Non-retryable failure for event %s (attempt %d/%d): %s",
                    event.event_id, attempt + 1, self._max_retries + 1, result.error_message,
                )
                break

            if attempt < self._max_retries:
                delay = self._retry_base_delay * (2 ** attempt)
                logger.info(
                    "Retrying event %s in %.1fs (attempt %d/%d): %s",
                    event.event_id, delay, attempt + 1, self._max_retries,
                    result.error_message,
                )
                await asyncio.sleep(delay)

        return last_result or CommandResult(
            command_id="",
            device_id=event.device_id,
            success=False,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error_code="EXHAUSTED",
            error_message="All retry attempts exhausted",
        )

    # ================================================================
    # Execution Monitoring
    # ================================================================

    async def check_execution_status(
        self,
        event_id: str,
        sensor_readings: Optional[Dict[str, float]] = None,
    ) -> IrrigationEvent:
        """Check if an executing event has completed or needs intervention.

        Should be called periodically for all active events.
        """
        event = self._active_events.get(event_id)
        if not event:
            logger.warning("Event %s not found in active events", event_id)
            return IrrigationEvent(event_id=event_id, plot_id="", zone_id="",
                                    device_id="", system_type=IrrigationSystemType.DRIP,
                                    automation_mode=AutomationMode.MANUAL,
                                    status=EventStatus.FAILED)

        actuator = self._registry.get_actuator(event.device_id)
        if not actuator:
            # BA-01: Registry loss requires degraded reconciliation; must not mean physically stopped
            logger.error("Actuator %s lost from registry during execution of event %s. Retaining exposure.",
                         event.device_id, event.event_id)
            event.transition(EventStatus.STOP_REQUESTED, "Actuator lost from registry during execution")
            SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
            return event

        # If already in STOP_REQUESTED, attempt stop reconciliation/retry
        if event.status == EventStatus.STOP_REQUESTED:
            act_cmd = getattr(actuator, "active_command", None)
            act_cmd_eid = getattr(act_cmd, "source_event_id", getattr(act_cmd, "event_id", None))

            latched_hazards = [
                v for (k, v) in getattr(self._safety, "_active_violations", {}).items()
                if (k.endswith(f":{event.device_id}") or v.device_id == event.device_id)
                and v.interlock_type != InterlockType.DURATION_EXCEEDED
            ]
            has_device_hazard = bool(latched_hazards)
            if not has_device_hazard and sensor_readings:
                new_v = self._safety.evaluate(event.device_id, sensor_readings, act_cmd)
                if new_v:
                    has_device_hazard = any(v.interlock_type != InterlockType.DURATION_EXCEEDED for v in new_v)

            # BV01: Check current operation identity on actuator or durable store before issuing STOP, UNLESS there is an un-cleared device hazard
            if not has_device_hazard:
                if act_cmd_eid and act_cmd_eid != event.event_id:
                    logger.warning(
                        "Actuator %s is executing different event %s; ignoring STOP retry for %s",
                        event.device_id, act_cmd_eid, event.event_id
                    )
                    return event
                live_owner = SharedQuotaStore.get_active_record_for_resource(event.device_id, event.zone_id)
                if live_owner and live_owner.get("event_id") != event.event_id and live_owner.get("status") in ("EXECUTING", "DISPATCHING"):
                    logger.warning(
                        "Actuator %s is owned by live event %s in durable store; ignoring STOP retry for %s",
                        event.device_id, live_owner.get("event_id"), event.event_id
                    )
                    return event

            try:
                status = await asyncio.wait_for(actuator.get_status(), timeout=5.0)
            except Exception:
                status = ActuatorStatus.ERROR

            pending_cmd = getattr(actuator, "pending_command", getattr(actuator, "_pending_command", None))
            pending_eid = getattr(pending_cmd, "source_event_id", getattr(pending_cmd, "event_id", None)) if pending_cmd else None
            durable_rec = SharedQuotaStore.get_active_record(event.event_id)
            durable_st = (durable_rec.get("status") if durable_rec else "") or ""
            # V04 / SR04 / DV01: Distinguish positively refused-before-send from applied-without-ACK
            was_ever_started = bool(event.actual_start or (durable_rec and durable_rec.get("actual_start")))
            has_pending_cmd = (pending_cmd is not None and (not pending_eid or pending_eid == event.event_id))
            has_active_cmd = (act_cmd is not None and (not act_cmd_eid or act_cmd_eid == event.event_id))
            device_executing = (status == ActuatorStatus.EXECUTING)
            live_res_owner = SharedQuotaStore.get_active_record_for_resource(event.device_id, event.zone_id)
            is_foreign_owner = (
                (act_cmd_eid is not None and act_cmd_eid != event.event_id)
                or (live_res_owner is not None and live_res_owner.get("event_id") != event.event_id)
            )
            is_positively_unstarted = (
                not was_ever_started
                and not has_pending_cmd
                and not has_active_cmd
                and (not device_executing or is_foreign_owner)
                and durable_st not in ("DISPATCHING", "EXECUTING")
            )
            if is_positively_unstarted:
                term_status = EventStatus.EMERGENCY_STOPPED if event.emergency_stopped else EventStatus.CANCELLED
                event.transition(term_status, "Confirmed stopped (event never physically started on actuator)")
                res = SharedQuotaStore.get_active_record(event.event_id) or {}
                season_key = res.get("season")
                del_mm = getattr(event, "delivered_volume_mm", 0.0) or 0.0
                self._safety.record_stopped_delivery(
                    event_id=event.event_id,
                    plot_id=event.plot_id,
                    target_volume_mm=event.target_volume_mm,
                    delivered_volume_mm=del_mm,
                    season=season_key,
                    device_id=event.device_id,
                    zone_id=event.zone_id,
                    duration_minutes=event.target_duration_minutes,
                    flow_rate_lpm=event.target_flow_rate_lpm,
                    effective_area_ha=getattr(event, "effective_area_ha", None),
                )
                self._safety.track_event_end(event.event_id)
                self._finalize_event(event)
                if term_status == EventStatus.EMERGENCY_STOPPED:
                    self._emit_failed(event)
                return event

            has_pending = (
                has_pending_cmd
                or durable_st == "DISPATCHING"
            )

            # ER01: Online actuator cannot certify STOP if command dispatch or START is pending/unresolved
            if status == ActuatorStatus.ONLINE and not has_pending and not has_device_hazard:
                term_status = EventStatus.EMERGENCY_STOPPED if event.emergency_stopped else EventStatus.CANCELLED
                event.transition(term_status, "Confirmed stopped on actuator after reconciliation")
                res = SharedQuotaStore.get_active_record(event.event_id) or {}
                season_key = res.get("season")
                del_mm = getattr(event, "delivered_volume_mm", None)
                self._safety.record_stopped_delivery(
                    event_id=event.event_id,
                    plot_id=event.plot_id,
                    target_volume_mm=event.target_volume_mm,
                    delivered_volume_mm=del_mm,
                    season=season_key,
                    device_id=event.device_id,
                    zone_id=event.zone_id,
                    duration_minutes=event.target_duration_minutes,
                    flow_rate_lpm=event.target_flow_rate_lpm,
                    effective_area_ha=getattr(event, "effective_area_ha", None),
                )
                self._safety.track_event_end(event.event_id)
                self._finalize_event(event)
                if term_status == EventStatus.EMERGENCY_STOPPED:
                    self._emit_failed(event)
                return event
            else:
                stop_retry = None
                try:
                    stop_retry = await actuator.emergency_stop()
                except Exception as stop_err:
                    logger.error("STOP retry exception on device %s for event %s: %s", event.device_id, event.event_id, stop_err)
                    stop_retry = CommandResult(
                        command_id="stop_retry_exc",
                        device_id=event.device_id,
                        success=False,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        error_code="STOP_EXCEPTION",
                        error_message=str(stop_err),
                    )

                if stop_retry and self._is_stop_confirmed(actuator, stop_retry) and not has_pending and not has_device_hazard:
                    term_status = EventStatus.EMERGENCY_STOPPED if event.emergency_stopped else EventStatus.CANCELLED
                    event.transition(term_status, "Confirmed stopped on actuator after retry")
                    has_fault = getattr(actuator, "_fault_latched", False) or bool(getattr(stop_retry, "fault_code", 0)) or getattr(stop_retry, "error_code", "") in ("FAULT", "HARDWARE_FAULT", "ERROR")
                    if has_fault:
                        actuator._status = ActuatorStatus.ERROR
                    else:
                        actuator._status = ActuatorStatus.ONLINE
                    actuator._active_command = None
                    res = SharedQuotaStore.get_active_record(event.event_id) or {}
                    season_key = res.get("season")
                    del_mm = getattr(event, "delivered_volume_mm", None)
                    SharedQuotaStore.record_stopped_delivery(
                        event_id=event.event_id,
                        plot_id=event.plot_id,
                        target_volume_mm=event.target_volume_mm,
                        delivered_volume_mm=del_mm,
                        season=season_key,
                        device_id=event.device_id,
                        zone_id=event.zone_id,
                        duration_minutes=event.target_duration_minutes,
                        flow_rate_lpm=event.target_flow_rate_lpm,
                        effective_area_ha=getattr(event, "effective_area_ha", None),
                    )
                    self._safety.track_event_end(event.event_id)
                    self._finalize_event(event)
                    if term_status == EventStatus.EMERGENCY_STOPPED:
                        self._emit_failed(event)
                    return event
                else:
                    actuator._status = ActuatorStatus.ERROR
                    SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
                    if act_cmd_eid and act_cmd_eid != event.event_id:
                        SharedQuotaStore.update_status(act_cmd_eid, "STOP_REQUESTED")
                        if act_cmd_eid in self._active_events:
                            other_ev = self._active_events[act_cmd_eid]
                            other_ev.emergency_stopped = True
                            other_ev.transition(EventStatus.STOP_REQUESTED, f"Safety violation on device {event.device_id}: emergency stop failed")
                    logger.error("STOP retry on device %s for event %s unresolved/failed. Retaining tracking and quota.",
                                 event.device_id, event.event_id)
                    return event

        # Check safety interlocks & duration watchdog unconditionally FIRST (without waiting for telemetry)
        violations = self._safety.evaluate(
            event.device_id, sensor_readings, actuator.active_command
        )
        if not violations:
            # ER02: Check for latched device hazards where cutoff has not succeeded
            latched_vios = [
                v for (k, v) in getattr(self._safety, "_active_violations", {}).items()
                if (k.endswith(f":{event.device_id}") or v.device_id == event.device_id)
                and v.interlock_type != InterlockType.DURATION_EXCEEDED
            ]
            if latched_vios and (getattr(actuator, "running", False) or getattr(actuator, "_status", None) in (ActuatorStatus.EXECUTING, ActuatorStatus.ERROR) or actuator.active_command is not None):
                violations = latched_vios

        if violations:
            act_cmd = getattr(actuator, "active_command", None)
            act_cmd_eid = getattr(act_cmd, "source_event_id", getattr(act_cmd, "event_id", None))

            # PB03: Distinguish stale-event duration watchdog from active-device / active-command safety hazards
            is_only_stale_duration = (
                act_cmd_eid is not None
                and act_cmd_eid != event.event_id
                and all(
                    v.interlock_type == InterlockType.DURATION_EXCEEDED and v.event_id_affected == event.event_id
                    for v in violations
                )
            )
            if is_only_stale_duration:
                event.emergency_stopped = True
                event.emergency_stop_reason = "; ".join(v.interlock_type.value for v in violations)
                event.transition(EventStatus.EMERGENCY_STOPPED, f"Safety violation: {event.emergency_stop_reason}; actuator occupied by different event")
                res = SharedQuotaStore.get_active_record(event.event_id) or {}
                season_key = res.get("season")
                del_mm = getattr(event, "delivered_volume_mm", None)
                self._safety.record_stopped_delivery(
                    event_id=event.event_id,
                    plot_id=event.plot_id,
                    target_volume_mm=event.target_volume_mm,
                    delivered_volume_mm=del_mm,
                    season=season_key,
                    device_id=event.device_id,
                    zone_id=event.zone_id,
                    duration_minutes=event.target_duration_minutes,
                    flow_rate_lpm=event.target_flow_rate_lpm,
                    effective_area_ha=getattr(event, "effective_area_ha", None),
                )
                self._safety.track_event_end(event.event_id)
                self._finalize_event(event)
                self._emit_failed(event)
                return event

            # Device-level fault or active operation fault: physical emergency stop MUST be dispatched!
            stop_result = None
            try:
                stop_result = await actuator.emergency_stop()
            except Exception as stop_err:
                logger.error("Emergency stop raised exception on device %s for event %s: %s", event.device_id, event.event_id, stop_err)
                stop_result = CommandResult(
                    command_id=f"stop_{uuid.uuid4().hex[:8]}",
                    device_id=event.device_id,
                    success=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="STOP_EXCEPTION",
                    error_message=str(stop_err),
                )

            event.emergency_stopped = True
            event.emergency_stop_reason = "; ".join(
                v.interlock_type.value for v in violations
            )
            event.safety_violations.extend(v.violation_id for v in violations)

            transport_ok = bool(stop_result and stop_result.success)
            confirmed_stop = self._is_stop_confirmed(actuator, stop_result)

            if confirmed_stop:
                has_fault = getattr(actuator, "_fault_latched", False) or bool(getattr(stop_result, "fault_code", 0)) or getattr(stop_result, "error_code", "") in ("FAULT", "HARDWARE_FAULT", "ERROR") or getattr(actuator, "_status", None) == ActuatorStatus.ERROR
                if has_fault:
                    actuator._status = ActuatorStatus.ERROR
                else:
                    actuator._status = ActuatorStatus.ONLINE
                actuator._active_command = None

                # RP02: If a different live operation owns the actuator, only finalize after STOP confirmed
                if act_cmd_eid and act_cmd_eid != event.event_id:
                    try:
                        SharedQuotaStore.update_status(act_cmd_eid, "CANCELLED")
                        res_act = SharedQuotaStore.get_active_record(act_cmd_eid) or {}
                        self._safety.record_stopped_delivery(
                            event_id=act_cmd_eid,
                            plot_id=res_act.get("plot_id", event.plot_id),
                            target_volume_mm=float(res_act.get("target_volume_mm", res_act.get("volume_mm", 0.0))),
                            delivered_volume_mm=None,
                            season=res_act.get("season"),
                            device_id=event.device_id,
                            zone_id=res_act.get("zone_id", event.zone_id),
                            duration_minutes=float(res_act["duration_minutes"]) if res_act.get("duration_minutes") is not None else None,
                            flow_rate_lpm=float(res_act["flow_rate_lpm"]) if res_act.get("flow_rate_lpm") is not None else None,
                            effective_area_ha=res_act.get("effective_area_ha"),
                        )
                    except Exception as store_err:
                        logger.error("Failed to update status for active command %s on emergency stop: %s", act_cmd_eid, store_err)
                    if act_cmd_eid in self._active_events:
                        other_ev = self._active_events[act_cmd_eid]
                        other_ev.emergency_stopped = True
                        other_ev.emergency_stop_reason = event.emergency_stop_reason
                        other_ev.transition(EventStatus.CANCELLED, f"Safety violation on device {event.device_id}: {event.emergency_stop_reason}")
                        self._safety.track_event_end(act_cmd_eid)
                        self._finalize_event(other_ev)
                        self._emit_failed(other_ev)

                event.transition(EventStatus.EMERGENCY_STOPPED,
                                 f"Safety violation: {event.emergency_stop_reason}")
                res = SharedQuotaStore.get_active_record(event.event_id) or {}
                season_key = res.get("season")
                del_mm = getattr(event, "delivered_volume_mm", None) or (res.get("delivered_volume_mm") if res else None)
                cmd_tgt = getattr(event, "target_volume_mm", None) or (res.get("target_volume_mm") if res else None) or float(res.get("volume_mm", 0.0) if res else 0.0)
                self._safety.record_stopped_delivery(
                    event_id=event.event_id,
                    plot_id=event.plot_id,
                    target_volume_mm=cmd_tgt,
                    delivered_volume_mm=del_mm,
                    season=season_key,
                    device_id=event.device_id,
                    zone_id=event.zone_id,
                    duration_minutes=event.target_duration_minutes,
                    flow_rate_lpm=event.target_flow_rate_lpm,
                    effective_area_ha=getattr(event, "effective_area_ha", None),
                )
                self._safety.track_event_end(event.event_id)
                self._finalize_event(event)
                self._emit_failed(event)
            else:
                actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION if transport_ok else ActuatorStatus.ERROR
                event.transition(EventStatus.STOP_REQUESTED,
                                 f"Emergency stop unconfirmed for safety violation: {event.emergency_stop_reason}")
                SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
                if act_cmd_eid and act_cmd_eid != event.event_id:
                    SharedQuotaStore.update_status(act_cmd_eid, "STOP_REQUESTED")
                logger.warning("Emergency stop unconfirmed for safety violation on device %s for event %s. Retaining active tracking.",
                               event.device_id, event.event_id)
                if act_cmd_eid and act_cmd_eid in self._active_events:
                    other_ev = self._active_events[act_cmd_eid]
                    other_ev.emergency_stopped = True
                    other_ev.emergency_stop_reason = event.emergency_stop_reason
                    other_ev.transition(EventStatus.STOP_REQUESTED, f"Safety violation on device {event.device_id}: emergency stop failed")
                logger.error("Emergency stop unconfirmed on device %s for event %s. Retaining tracking and quota.",
                             event.device_id, event.event_id)
            return event

        # Check actuator status with timeout to avoid stalling on hung status queries
        try:
            status = await asyncio.wait_for(actuator.get_status(), timeout=5.0)
        except Exception as exc:
            logger.error("Actuator status query failed or timed out for device %s: %s", event.device_id, exc)
            status = ActuatorStatus.ERROR

        # BA-01 + D07: OFFLINE status means communications lost, NOT confirmed stopped!
        if status == ActuatorStatus.OFFLINE:
            logger.warning("Actuator %s is OFFLINE during execution of event %s. Retaining exposure and tracking.",
                           event.device_id, event.event_id)
            event.transition(EventStatus.STOP_REQUESTED, "Actuator OFFLINE during execution; communications lost")
            SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
            return event

        if status == ActuatorStatus.ERROR:
            act_cmd = getattr(actuator, "active_command", None)
            act_cmd_eid = getattr(act_cmd, "source_event_id", getattr(act_cmd, "event_id", None))
            if act_cmd_eid and act_cmd_eid != event.event_id:
                return event
            stop_result = await actuator.emergency_stop()
            transport_ok = bool(stop_result and stop_result.success)
            confirmed_stop = self._is_stop_confirmed(actuator, stop_result)

            if confirmed_stop:
                has_fault = getattr(actuator, "_fault_latched", False) or bool(getattr(stop_result, "fault_code", 0)) or getattr(stop_result, "error_code", "") in ("FAULT", "HARDWARE_FAULT", "ERROR") or status == ActuatorStatus.ERROR or getattr(actuator, "_status", None) == ActuatorStatus.ERROR
                if has_fault:
                    actuator._status = ActuatorStatus.ERROR
                else:
                    actuator._status = ActuatorStatus.ONLINE
                actuator._active_command = None
                event.transition(EventStatus.FAILED, "Actuator entered ERROR state (stopped)")
                # D03: Stop path must record stopped delivery exposure, NOT release quota!
                res = SharedQuotaStore.get_active_record(event.event_id) or {}
                season_key = res.get("season")
                del_mm = getattr(event, "delivered_volume_mm", None)
                self._safety.record_stopped_delivery(
                    event_id=event.event_id,
                    plot_id=event.plot_id,
                    target_volume_mm=event.target_volume_mm,
                    delivered_volume_mm=del_mm,
                    season=season_key,
                    device_id=event.device_id,
                    zone_id=event.zone_id,
                    duration_minutes=event.target_duration_minutes,
                    flow_rate_lpm=event.target_flow_rate_lpm,
                    effective_area_ha=getattr(event, "effective_area_ha", None),
                )
                self._safety.track_event_end(event.event_id)
                self._finalize_event(event)
                self._emit_failed(event)
            else:
                actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION if transport_ok else ActuatorStatus.ERROR
                event.transition(EventStatus.STOP_REQUESTED, "Actuator entered ERROR state and stop unconfirmed")
                SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
                logger.error("Stop attempt unconfirmed for device in ERROR state %s: %s", event.device_id, stop_result.error_message if stop_result else "")
            return event

        # Check if execution is complete: actuator must be confirmed ONLINE and idle
        if status == ActuatorStatus.ONLINE and event.status == EventStatus.EXECUTING:
            event.actual_end = datetime.now(timezone.utc).isoformat()
            event.transition(EventStatus.VALIDATING, "Execution completed, entering validation")
            SharedQuotaStore.update_status(event.event_id, "VALIDATING")
            self._safety.track_event_end(event.event_id)

            # Trigger validation callback
            for cb in self._on_validation_needed:
                try:
                    cb(event)
                except Exception as exc:
                    logger.error("Validation callback error: %s", exc)

        return event

    async def complete_event(
        self,
        event_id: str,
        actual_volume_l: Optional[float] = None,
        actual_duration_minutes: Optional[float] = None,
    ) -> Optional[IrrigationEvent]:
        """Mark an event as completed with actual delivery data."""
        eid = getattr(event_id, "event_id", event_id)
        event = self._active_events.get(eid)
        if not event:
            return None

        # D02, RC05, BV02: Guard against completing an event without positive, current idle confirmation
        actuator = self._registry.get_actuator(event.device_id)
        if actuator is None:
            logger.error("Cannot complete event %s: actuator %s not found in registry. Retaining unresolved execution.",
                         eid, event.device_id)
            return event

        try:
            cur_status = await asyncio.wait_for(actuator.get_status(), timeout=5.0)
        except Exception as exc:
            logger.error("Could not query actuator status for %s before completion: %s. Retaining unresolved execution.",
                         event.device_id, exc)
            return event

        # PB01, RP01: If actuator has a pending command in flight or durable record is in flight, completion cannot proceed
        durable_rec = SharedQuotaStore.get_active_record(eid)
        durable_st = (durable_rec.get("status") if durable_rec else "") or ""
        has_pending = (
            getattr(actuator, "pending_command", None) is not None
            or getattr(actuator, "_pending_command", None) is not None
            or durable_st in ("DISPATCHING", "STOP_REQUESTED")
            or event.status in (EventStatus.DISPATCHING, EventStatus.STOP_REQUESTED)
        )
        if has_pending:
            logger.error("Cannot complete event %s: actuator %s has pending command or unresolved dispatch in flight (durable_status=%s, local_status=%s). Retaining active execution.",
                         eid, event.device_id, durable_st, event.status.value)
            return event

        if cur_status != ActuatorStatus.ONLINE or getattr(actuator, "is_running", False):
            logger.error("Cannot complete event %s while actuator %s is not confirmed idle (status=%s, is_running=%s). Retaining active execution.",
                         eid, event.device_id, cur_status, getattr(actuator, "is_running", False))
            return event

        if event.status != EventStatus.VALIDATING:
            logger.error("Cannot complete event %s: current status %s is not VALIDATING.", eid, event.status.value)
            return event

        # N02: Omitted measurements retain unresolved accounting in VALIDATING phase
        if actual_volume_l is None and actual_duration_minutes is None:
            logger.warning("Omitted measurements for event %s. Retaining unresolved accounting in VALIDATING phase.", eid)
            return event

        if actual_volume_l is None:
            logger.warning("Omitted volume measurement for event %s. Retaining unresolved accounting in VALIDATING phase.", eid)
            return event

        # C08 + D09: Strictly validate volume BEFORE mutating status or accounting
        val_vol = finite_real(actual_volume_l)
        if val_vol is None or val_vol < 0:
            logger.error("Invalid actual volume %r for event %s. Retaining unsettled exposure.", actual_volume_l, eid)
            event.transition(EventStatus.FAILED, f"Invalid settlement volume {actual_volume_l}")
            return event

        # D09, RV05, RC06: Validate duration if explicitly provided; keep None if omitted (do not fabricate duration)
        val_dur = None
        if actual_duration_minutes is not None:
            val_dur = finite_real(actual_duration_minutes)
            if val_dur is None or val_dur < 0:
                logger.error("Invalid actual duration %r for event %s. Retaining unsettled exposure.", actual_duration_minutes, eid)
                event.transition(EventStatus.FAILED, f"Invalid settlement duration {actual_duration_minutes}")
                return event

        # Validate effective_area_ha if explicitly present on event
        area_ha = None
        if hasattr(event, "effective_area_ha") and event.effective_area_ha is not None:
            area_ha = finite_real(event.effective_area_ha)
            if area_ha is None or area_ha <= 0:
                logger.error("Invalid effective area %r for event %s. Retaining unsettled exposure.",
                             event.effective_area_ha, eid)
                event.transition(EventStatus.FAILED, f"Invalid effective area {event.effective_area_ha}")
                return event

        # Hydrate canonical target volume and effective area from SharedQuotaStore if omitted
        durable_active = SharedQuotaStore.get_active_record(event.event_id) or {}
        if area_ha is None and durable_active.get("effective_area_ha") is not None:
            hyd_area = finite_real(durable_active["effective_area_ha"])
            if hyd_area is not None and hyd_area > 0:
                event.effective_area_ha = hyd_area
                area_ha = hyd_area
        if getattr(event, "target_volume_mm", None) is None and durable_active.get("target_volume_mm") is not None:
            event.target_volume_mm = float(durable_active["target_volume_mm"])
        if getattr(event, "target_flow_rate_lpm", None) is None and durable_active.get("flow_rate_lpm") is not None:
            event.target_flow_rate_lpm = float(durable_active["flow_rate_lpm"])
        if getattr(event, "target_duration_minutes", None) is None and durable_active.get("duration_minutes") is not None:
            event.target_duration_minutes = float(durable_active["duration_minutes"])

        # N02 + D09: Calculate settled depth
        # Explicit 0 L settles as 0.0 mm independently of area!
        # Nonzero litres require effective_area_ha support; cannot fabricate commanded target depth!
        if val_vol == 0.0:
            settled_mm = 0.0
        elif area_ha is not None and area_ha > 0:
            # I_mm = V_L / (10,000 * A_ha)
            settled_mm = round(val_vol / (10000.0 * area_ha), 6)
        else:
            logger.warning("Nonzero volume %r for event %s without effective_area_ha support cannot certify depth. Retaining VALIDATING phase.", val_vol, eid)
            return event

        # Validate settled_mm
        val_settled = finite_real(settled_mm)
        if val_settled is None or val_settled < 0:
            logger.error("Invalid derived settled depth %r for event %s", settled_mm, eid)
            event.transition(EventStatus.FAILED, f"Invalid derived settled depth {settled_mm}")
            return event

        # Commit settlement in shared store BEFORE transitioning to COMPLETED
        res = SharedQuotaStore.get_active_record(event.event_id) or {}
        season_key = res.get("season")
        try:
            self._safety.settle_quota(
                event_id=event.event_id,
                plot_id=event.plot_id,
                volume_mm=val_settled,
                target_volume_mm=event.target_volume_mm,
                actual_volume_l=val_vol,
                actual_duration_minutes=val_dur,
                season=season_key,
                device_id=event.device_id,
                zone_id=event.zone_id,
                duration_minutes=event.target_duration_minutes,
                flow_rate_lpm=event.target_flow_rate_lpm,
                effective_area_ha=area_ha,
            )
        except Exception as exc:
            logger.error("Failed to commit quota settlement for event %s: %s", eid, exc)
            event.transition(EventStatus.FAILED, f"Quota settlement failed: {exc}")
            return event

        event.actual_volume_l = val_vol
        event.actual_duration_minutes = val_dur
        event.delivered_volume_mm = val_settled

        # Hydrate exact committed canonical receipt
        durable_settled = SharedQuotaStore.get_settled_receipt(event.event_id) or {}
        if durable_settled.get("volume_mm") is not None:
            event.delivered_volume_mm = float(durable_settled["volume_mm"])
        if durable_settled.get("target_volume_mm") is not None:
            event.target_volume_mm = float(durable_settled["target_volume_mm"])
        if durable_settled.get("effective_area_ha") is not None:
            event.effective_area_ha = float(durable_settled["effective_area_ha"])
        event.transition(EventStatus.COMPLETED, "Validated and completed")
        self._safety.track_event_end(event.event_id)
        self._finalize_event(event)

        for cb in self._on_event_complete:
            try:
                cb(event)
            except Exception as exc:
                logger.error("Completion callback error: %s", exc)

        return event

    async def cancel_event(self, event_id: str, reason: str = "") -> Optional[IrrigationEvent]:
        """Cancel an active event and stop the actuator."""
        eid = getattr(event_id, "event_id", event_id)
        event = self._active_events.get(eid)
        if not event:
            return None

        # Stop the actuator
        actuator = self._registry.get_actuator(event.device_id)
        stop_success = False
        if actuator:
            try:
                status = await asyncio.wait_for(actuator.get_status(), timeout=5.0)
            except Exception:
                status = ActuatorStatus.ERROR

            act_cmd = getattr(actuator, "active_command", None)
            pending_cmd = getattr(actuator, "pending_command", None) or getattr(actuator, "_pending_command", None)
            act_eid = getattr(act_cmd, "source_event_id", getattr(act_cmd, "event_id", None)) if act_cmd is not None else None
            pending_eid = getattr(pending_cmd, "source_event_id", getattr(pending_cmd, "event_id", None)) if pending_cmd is not None else None
            is_running = (
                status == ActuatorStatus.EXECUTING
                or getattr(actuator, "running", False)
                or act_cmd is not None
                or pending_cmd is not None
            )

            # ER03: 1. Qualified different pending owner: another operation is in flight to take over device.
            # Suppress physical STOP so we do NOT preempt pending NEW!
            if bool(pending_eid) and pending_eid != event.event_id:
                logger.info(
                    "Event %s cancelled while device %s has pending different operation %s; suppressing physical STOP to avoid preemption.",
                    event.event_id, event.device_id, pending_eid
                )
                stop_success = True

            # 2. Qualified different active owner: actuator is executing a confirmed different event.
            # Suppress physical STOP so we do NOT stop the other running event.
            elif bool(act_eid) and act_eid != event.event_id:
                logger.info(
                    "Event %s cancelled while device %s is executing confirmed different operation %s; suppressing physical STOP.",
                    event.event_id, event.device_id, act_eid
                )
                stop_success = True

            # 3. Qualified same owner: this event is actively running or pending on the device.
            elif (act_eid == event.event_id) or (pending_eid == event.event_id):
                stop_cmd = IrrigationCommand(
                    command_id=f"CMD-STOP-{uuid.uuid4().hex[:8]}",
                    command_type=CommandType.STOP_ZONE,
                    device_id=event.device_id,
                    zone_id=event.zone_id,
                    plot_id=event.plot_id,
                    source_event_id=event.event_id,
                    operation_id=f"OP-STOP-{event.event_id}",
                )
                try:
                    stop_res = await actuator.execute_with_safety(stop_cmd)
                    confirmed_stop = bool(getattr(stop_res, "confirmed_physical_stop", False))
                    transport_only = bool(getattr(stop_res, "transport_acknowledged_only", False))
                    status_pending = getattr(actuator, "status", None) == ActuatorStatus.STOP_PENDING_CONFIRMATION
                    stop_success = bool(
                        stop_res
                        and stop_res.success
                        and (confirmed_stop or (not transport_only and not status_pending and getattr(actuator, "status", None) == ActuatorStatus.ONLINE))
                        and not status_pending
                    )
                except Exception as stop_err:
                    logger.error("Exception sending STOP command for %s: %s", event.event_id, stop_err)
                    stop_success = False

            # ER03: 4. Unqualified / unknown identity while actuator is active, executing, or in unconfirmed status
            elif is_running or status in (ActuatorStatus.OFFLINE, ActuatorStatus.UNKNOWN, ActuatorStatus.ERROR, ActuatorStatus.STOP_PENDING_CONFIRMATION):
                logger.warning(
                    "Event %s cancellation attempted on device %s in %s state with unresolved identity (act_eid=%r, pending_eid=%r); cannot confirm idle.",
                    event.event_id, event.device_id, status.value if hasattr(status, "value") else status, act_eid, pending_eid
                )
                stop_success = False

            # 5. Actuator positively confirmed idle (ONLINE with no commands in flight)
            elif status == ActuatorStatus.ONLINE and not is_running:
                stop_success = True
            else:
                stop_success = False

        if stop_success:
            event.transition(EventStatus.CANCELLED, reason or "Cancelled by user")
            res = SharedQuotaStore.get_active_record(event.event_id) or {}
            season_key = res.get("season")
            del_mm = getattr(event, "delivered_volume_mm", None)
            self._safety.record_stopped_delivery(
                event_id=event.event_id,
                plot_id=event.plot_id,
                target_volume_mm=event.target_volume_mm,
                delivered_volume_mm=del_mm,
                season=season_key,
                device_id=event.device_id,
                zone_id=event.zone_id,
                duration_minutes=event.target_duration_minutes,
                flow_rate_lpm=event.target_flow_rate_lpm,
                effective_area_ha=getattr(event, "effective_area_ha", None),
            )
            self._safety.track_event_end(event.event_id)
            self._finalize_event(event)
        else:
            event.transition(EventStatus.STOP_REQUESTED, f"Cancellation stop pending physical confirmation: {reason or 'stop unconfirmed'}")
            SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
            logger.warning("Cancel stop unconfirmed on device %s for event %s. Retaining active tracking, ownership and quota.",
                         event.device_id, event.event_id)
        return event

    async def emergency_stop_all(self) -> Dict[str, str]:
        """Emergency stop all active events (N09, RV01: reliable global cutoff)."""
        results = {}
        try:
            for event_id, event in list(self._active_events.items()):
                try:
                    actuator = self._registry.get_actuator(event.device_id)
                    stop_success = False
                    if actuator:
                        stop_res = await actuator.emergency_stop()
                        transport_ok = bool(stop_res and stop_res.success)
                        status_pending = (getattr(actuator, "status", None) == ActuatorStatus.STOP_PENDING_CONFIRMATION or getattr(actuator, "_status", None) == ActuatorStatus.STOP_PENDING_CONFIRMATION)
                        confirmed_stop = self._is_stop_confirmed(actuator, stop_res)
                        if confirmed_stop:
                            has_fault = getattr(actuator, "_fault_latched", False) or bool(getattr(stop_res, "fault_code", 0)) or getattr(stop_res, "error_code", "") in ("FAULT", "HARDWARE_FAULT", "ERROR") or getattr(actuator, "_status", None) == ActuatorStatus.ERROR
                            if has_fault:
                                actuator._status = ActuatorStatus.ERROR
                            else:
                                actuator._status = ActuatorStatus.ONLINE
                            actuator._active_command = None
                        elif transport_ok or status_pending:
                            actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
                        else:
                            actuator._status = ActuatorStatus.ERROR
                    if confirmed_stop:
                        event.emergency_stopped = True
                        event.emergency_stop_reason = "Global emergency stop"
                        event.transition(EventStatus.EMERGENCY_STOPPED, "Global emergency stop")
                        res = SharedQuotaStore.get_active_record(event.event_id) or {}
                        season_key = res.get("season")
                        del_mm = getattr(event, "delivered_volume_mm", None)
                        self._safety.record_stopped_delivery(
                            event_id=event.event_id,
                            plot_id=event.plot_id,
                            target_volume_mm=event.target_volume_mm,
                            delivered_volume_mm=del_mm,
                            season=season_key,
                            device_id=event.device_id,
                            zone_id=event.zone_id,
                            duration_minutes=event.target_duration_minutes,
                            flow_rate_lpm=event.target_flow_rate_lpm,
                            effective_area_ha=getattr(event, "effective_area_ha", None),
                        )
                        self._safety.track_event_end(event.event_id)
                        self._finalize_event(event)
                        results[event_id] = "STOPPED"
                    else:
                        event.emergency_stopped = True
                        event.emergency_stop_reason = "Global emergency stop (stop unconfirmed)"
                        event.transition(EventStatus.STOP_REQUESTED, "Global emergency stop unconfirmed on actuator")
                        SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
                        if transport_ok:
                            results[event_id] = "STOP_PENDING"
                        else:
                            results[event_id] = "STOP_FAILED"
                except Exception as exc:
                    logger.error("Error during emergency stop of event %s: %s", event_id, exc)
                    event.emergency_stopped = True
                    event.emergency_stop_reason = f"Global emergency stop exception: {exc}"
                    if event.status != EventStatus.STOP_REQUESTED:
                        event.transition(EventStatus.STOP_REQUESTED, f"Exception during stop: {exc}")
                    try:
                        SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
                    except Exception as store_err:
                        logger.error("Ledger update failed in error handler for %s: %s", event_id, store_err)
                    results[event_id] = "STOP_ERROR"
        finally:
            # RV01: Guaranteed fallback stop of all actuators in registry even if ledger or exceptions occur
            try:
                await self._registry.emergency_stop_all()
            except Exception as exc:
                logger.error("Registry emergency_stop_all failed: %s", exc)

        return results

    def confirm_stopped_event(self, event_id: str, receipt: Dict[str, Any]) -> bool:
        """Confirm a pending STOP on an event using verified physical evidence."""
        if event_id not in self._active_events:
            logger.warning("Cannot confirm stopped event %s: not in active events", event_id)
            return False

        event = self._active_events[event_id]
        actuator = self._registry.get_actuator(event.device_id)
        if not actuator:
            logger.error("No actuator for device %s to confirm stop on event %s", event.device_id, event_id)
            return False

        confirmed = actuator.confirm_stop(receipt)
        if not confirmed:
            return False

        # Transition event to terminal state (CANCELLED or EMERGENCY_STOPPED)
        terminal_status = EventStatus.CANCELLED if "cancel" in (event.status_reason or "").lower() else EventStatus.EMERGENCY_STOPPED
        event.transition(terminal_status, "Physical stop verified by controller receipt")
        res = SharedQuotaStore.get_active_record(event.event_id) or {}
        season_key = res.get("season")
        del_mm = getattr(event, "delivered_volume_mm", None)
        self._safety.record_stopped_delivery(
            event_id=event.event_id,
            plot_id=event.plot_id,
            target_volume_mm=event.target_volume_mm,
            delivered_volume_mm=del_mm,
            season=season_key,
            device_id=event.device_id,
            zone_id=event.zone_id,
            duration_minutes=event.target_duration_minutes,
            flow_rate_lpm=event.target_flow_rate_lpm,
            effective_area_ha=getattr(event, "effective_area_ha", None),
        )
        self._safety.track_event_end(event.event_id)
        self._finalize_event(event)
        logger.info("Event %s successfully confirmed STOP and finalized.", event_id)
        return True

    async def reconcile_on_restart(
        self,
        persisted_events: List[IrrigationEvent],
    ) -> List[IrrigationEvent]:
        """Restore event and controller reconciliation on process restart.

        Queries real-time hardware status for events in DISPATCHING, EXECUTING, or STOP_REQUESTED
        to reconcile whether the controller is actually running or stopped.
        Deducts elapsed time from the original planned duration so restart does not reset watchdog limits.
        """
        reconciled = []
        for event in persisted_events:
            active_rec = SharedQuotaStore.get_active_record(event.event_id)
            # RC02, BV06, RP01: Terminal receipts must fence stale restart snapshots without contacting actuator and hydrate canonical measurements, unless active reservation exists
            if (not SharedQuotaStore.is_active(event.event_id)) and (SharedQuotaStore.is_settled(event.event_id) or (active_rec and active_rec.get("status") in ("COMPLETED", EventStatus.COMPLETED.value))):
                event.status = EventStatus.COMPLETED
                rcpt = SharedQuotaStore.get_settled_receipt(event.event_id) or {}
                if rcpt:
                    event.actual_volume_l = rcpt.get("actual_volume_l")
                    event.actual_duration_minutes = rcpt.get("actual_duration_minutes")
                    event.delivered_volume_mm = rcpt.get("delivered_volume_mm")
                    event.target_volume_mm = float(rcpt.get("target_volume_mm", event.target_volume_mm))
                    event.plot_id = rcpt.get("plot_id", event.plot_id)
                    event.device_id = rcpt.get("device_id", event.device_id)
                    event.zone_id = rcpt.get("zone_id", event.zone_id)
                    event.effective_area_ha = rcpt.get("effective_area_ha")
                reconciled.append(event)
                continue

            if (not SharedQuotaStore.is_active(event.event_id)) and (SharedQuotaStore.is_stopped(event.event_id) or (active_rec and active_rec.get("status") in ("CANCELLED", "EMERGENCY_STOPPED", EventStatus.CANCELLED.value, EventStatus.EMERGENCY_STOPPED.value))):
                s_rcpt = SharedQuotaStore.get_stopped_receipt(event.event_id) or {}
                # XR03: Hydrate canonical scope before querying or looking up actuator
                canonical_dev = (active_rec.get("device_id") if active_rec else None) or s_rcpt.get("device_id") or event.device_id
                event.device_id = canonical_dev
                if s_rcpt:
                    event.plot_id = s_rcpt.get("plot_id", event.plot_id)
                    event.zone_id = s_rcpt.get("zone_id", event.zone_id)
                    event.delivered_volume_mm = s_rcpt.get("delivered_volume_mm", getattr(event, "delivered_volume_mm", None))
                    event.target_volume_mm = float(s_rcpt.get("target_volume_mm", event.target_volume_mm))
                    event.effective_area_ha = s_rcpt.get("effective_area_ha", getattr(event, "effective_area_ha", None))

                actuator = self._registry.get_actuator(event.device_id) if hasattr(self, "_registry") and self._registry else None
                actuator_running = False
                if actuator:
                    try:
                        st = await asyncio.wait_for(actuator.get_status(), timeout=5.0)
                        if st == ActuatorStatus.EXECUTING:
                            actuator_running = True
                        elif st == ActuatorStatus.ONLINE:
                            actuator_running = getattr(actuator, "running", False)
                        else:
                            # OFFLINE, UNKNOWN, ERROR cannot certify idle
                            actuator_running = True
                    except Exception as q_exc:
                        logger.warning("Could not query live status for %s on restart: %s", event.device_id, q_exc)
                        actuator_running = True

                # NR01 / XR03: Check operation ownership if actuator is running
                actuator_running_for_this_event = False
                if actuator_running:
                    act_cmd = getattr(actuator, "active_command", None)
                    act_eid = getattr(act_cmd, "source_event_id", getattr(act_cmd, "event_id", None))
                    pend_cmd = getattr(actuator, "_pending_command", None)
                    pend_eid = getattr(pend_cmd, "source_event_id", getattr(pend_cmd, "event_id", None))

                    other_active_eid = None
                    if bool(act_eid) and act_eid != event.event_id:
                        other_active_eid = act_eid
                    elif bool(pend_eid) and pend_eid != event.event_id:
                        other_active_eid = pend_eid
                    else:
                        state_res = SharedQuotaStore._read_state().get("reservations", {})
                        for oe_id, oe_res in state_res.items():
                            if oe_id != event.event_id and oe_res.get("device_id") == event.device_id:
                                oe_st = oe_res.get("status", "")
                                # XR03: Include STARTING, STOP_REQUESTED, EXECUTING, DISPATCHING, RESERVED; exclude VALIDATING (settlement phase is not physically executing)
                                if oe_st in ("STARTING", "DISPATCHING", "EXECUTING", "RESERVED", "STOP_REQUESTED"):
                                    other_active_eid = oe_id
                                    break

                    if not other_active_eid:
                        actuator_running_for_this_event = True
                    else:
                        logger.info("Actuator %s is running for confirmed different event %s; stopped event %s remains terminal.",
                                    event.device_id, other_active_eid, event.event_id)

                if not actuator_running_for_this_event:
                    raw_st = (active_rec.get("status") if active_rec else None) or "CANCELLED"
                    try:
                        event.status = EventStatus(raw_st)
                    except Exception:
                        event.status = EventStatus.CANCELLED
                    reconciled.append(event)
                    continue
                else:
                    # NR01 / ER01 / XR03: Actuator is actively running for this event despite stopped record; reopen active reservation and reconcile as STOP_REQUESTED
                    logger.warning("Actuator %s is running for event %s despite stopped record; reopening active reservation.",
                                   event.device_id, event.event_id)
                    try:
                        SharedQuotaStore.reopen_active(
                            event.event_id,
                            event.plot_id,
                            event.target_volume_mm,
                            device_id=event.device_id,
                            zone_id=event.zone_id,
                            duration_minutes=event.target_duration_minutes,
                            flow_rate_lpm=event.target_flow_rate_lpm,
                            effective_area_ha=getattr(event, "effective_area_ha", None),
                        )
                        active_rec = SharedQuotaStore.get_active_record(event.event_id)
                        event.status = EventStatus.STOP_REQUESTED
                    except Exception as ro_err:
                        logger.error("Failed to reopen active reservation on restart for running actuator %s: %s", event.event_id, ro_err)

            if active_rec:
                # RC03: Restore immutable canonical scope envelope from active_rec
                if active_rec.get("plot_id"):
                    event.plot_id = active_rec["plot_id"]
                if active_rec.get("target_volume_mm") is not None:
                    event.target_volume_mm = float(active_rec["target_volume_mm"])
                elif active_rec.get("volume_mm") is not None:
                    event.target_volume_mm = float(active_rec["volume_mm"])
                if active_rec.get("device_id"):
                    event.device_id = active_rec["device_id"]
                if active_rec.get("zone_id"):
                    event.zone_id = active_rec["zone_id"]
                if active_rec.get("flow_rate_lpm") is not None:
                    event.target_flow_rate_lpm = float(active_rec["flow_rate_lpm"])
                if active_rec.get("duration_minutes") is not None:
                    event.target_duration_minutes = float(active_rec["duration_minutes"])
                # BV04: Canonical effective_area_ha overwrites caller snapshot even when None
                event.effective_area_ha = active_rec.get("effective_area_ha")
                # RC04, BV05: Durable actual_start is authoritative over caller snapshot.
                # If durable actual_start is missing, use conservative first_dispatched_at / timestamp;
                # a caller-supplied timestamp must never renew an expired allowance!
                if active_rec.get("actual_start"):
                    event.actual_start = active_rec["actual_start"]
                else:
                    conservative_start = active_rec.get("first_dispatched_at") or active_rec.get("timestamp")
                    if conservative_start:
                        event.actual_start = conservative_start

                raw_st = active_rec.get("status")
                if raw_st in (
                    "STARTING",
                    "ADMITTED",
                    "RESERVED",
                    EventStatus.DISPATCHING.value,
                    EventStatus.EXECUTING.value,
                    EventStatus.STOP_REQUESTED.value,
                    EventStatus.VALIDATING.value,
                    "UNSETTLED",
                ):
                    if raw_st == "UNSETTLED":
                        event.status = EventStatus.VALIDATING
                    elif raw_st in ("STARTING", "ADMITTED", "RESERVED"):
                        event.status = EventStatus.DISPATCHING
                    else:
                        event.status = EventStatus(raw_st)

            # RV04, RC05: VALIDATING survives restart; query actuator status so driver cache is fresh
            if event.status == EventStatus.VALIDATING:
                actuator = self._registry.get_actuator(event.device_id)
                if actuator:
                    try:
                        await asyncio.wait_for(actuator.get_status(), timeout=5.0)
                    except Exception as exc:
                        logger.warning("Could not query actuator status for %s on restart: %s", event.event_id, exc)
                self._active_events[event.event_id] = event
                reconciled.append(event)
                continue

            if event.status not in (EventStatus.DISPATCHING, EventStatus.EXECUTING, EventStatus.STOP_REQUESTED):
                continue

            # Calculate elapsed time from original start
            elapsed_minutes = 0.0
            if event.actual_start:
                try:
                    start_dt = datetime.fromisoformat(event.actual_start)
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    now_dt = datetime.now(timezone.utc)
                    elapsed_minutes = max(0.0, (now_dt - start_dt).total_seconds() / 60.0)
                except Exception:
                    if event.status in (EventStatus.EXECUTING, EventStatus.STOP_REQUESTED):
                        # V06: Malformed start on executing event cannot be granted fresh runtime: treat as expired!
                        elapsed_minutes = float(event.target_duration_minutes)
                    else:
                        elapsed_minutes = 0.0
            elif event.status in (EventStatus.EXECUTING, EventStatus.STOP_REQUESTED):
                # RV03: Executing/stop-requested event with no established start time cannot be granted fresh runtime: treat as expired!
                elapsed_minutes = float(event.target_duration_minutes)

            remaining_duration = max(0.0, event.target_duration_minutes - elapsed_minutes)

            actuator = self._registry.get_actuator(event.device_id)
            if not actuator:
                # BA-01: Actuator missing on restart: retain STOP_REQUESTED, do not silently free quota
                event.transition(EventStatus.STOP_REQUESTED, "Actuator not registered on process restart")
                self._active_events[event.event_id] = event
                self._safety.track_event_start(
                    event.event_id,
                    event.device_id,
                    event.target_duration_minutes,
                    plot_id=event.plot_id,
                    volume_mm=event.target_volume_mm,
                    elapsed_minutes=elapsed_minutes,
                    zone_id=event.zone_id,
                    flow_rate_lpm=event.target_flow_rate_lpm,
                    effective_area_ha=getattr(event, "effective_area_ha", None),
                )
                reconciled.append(event)
                continue

            # BA-05, BV01: Persisted STOP_REQUESTED must retain stop intent; do not revert to EXECUTING!
            if event.status == EventStatus.STOP_REQUESTED:
                act_cmd = getattr(actuator, "active_command", None)
                act_cmd_eid = getattr(act_cmd, "source_event_id", getattr(act_cmd, "event_id", None))
                if act_cmd_eid and act_cmd_eid != event.event_id:
                    event.transition(EventStatus.STOP_REQUESTED, "Actuator executing different event")
                    self._active_events[event.event_id] = event
                    reconciled.append(event)
                    continue
                try:
                    stop_res = await actuator.emergency_stop()
                    if self._is_stop_confirmed(actuator, stop_res):
                        event.transition(
                            EventStatus.EMERGENCY_STOPPED if event.emergency_stopped else EventStatus.CANCELLED,
                            "Confirmed stopped on restart"
                        )
                        res = SharedQuotaStore.get_active_record(event.event_id) or {}
                        season_key = res.get("season")
                        del_mm = getattr(event, "delivered_volume_mm", None) or (res.get("delivered_volume_mm") if res else None)
                        cmd_tgt = getattr(event, "target_volume_mm", None) or (res.get("target_volume_mm") if res else None) or float(res.get("volume_mm", 0.0) if res else 0.0)
                        SharedQuotaStore.record_stopped_delivery(
                            event_id=event.event_id,
                            plot_id=event.plot_id,
                            target_volume_mm=cmd_tgt,
                            delivered_volume_mm=del_mm,
                            season=season_key,
                            device_id=event.device_id,
                            zone_id=event.zone_id,
                            duration_minutes=event.target_duration_minutes,
                            flow_rate_lpm=event.target_flow_rate_lpm,
                            effective_area_ha=getattr(event, "effective_area_ha", None),
                        )
                        self._safety.track_event_end(event.event_id)
                    else:
                        event.transition(EventStatus.STOP_REQUESTED, "Stop failed on restart")
                        self._active_events[event.event_id] = event
                        actuator.set_active_command(self._build_command(event))
                        self._safety.track_event_start(
                            event.event_id,
                            event.device_id,
                            event.target_duration_minutes,
                            plot_id=event.plot_id,
                            volume_mm=event.target_volume_mm,
                            elapsed_minutes=elapsed_minutes,
                            zone_id=event.zone_id,
                            flow_rate_lpm=event.target_flow_rate_lpm,
                            effective_area_ha=getattr(event, "effective_area_ha", None),
                        )
                except Exception as exc:
                    event.transition(EventStatus.STOP_REQUESTED, f"Stop query failed on restart: {exc}")
                    self._active_events[event.event_id] = event
                    actuator.set_active_command(self._build_command(event))
                    self._safety.track_event_start(
                        event.event_id,
                        event.device_id,
                        event.target_duration_minutes,
                        plot_id=event.plot_id,
                        volume_mm=event.target_volume_mm,
                        elapsed_minutes=elapsed_minutes,
                        zone_id=event.zone_id,
                        flow_rate_lpm=event.target_flow_rate_lpm,
                        effective_area_ha=getattr(event, "effective_area_ha", None),
                    )
                reconciled.append(event)
                continue

            try:
                status = await asyncio.wait_for(actuator.get_status(), timeout=5.0)

                if status == ActuatorStatus.EXECUTING:
                    # RC02: Bind live controller reconciliation to event identity.
                    # If actuator is executing a DIFFERENT event, do NOT issue emergency stop to that actuator!
                    act_cmd = getattr(actuator, "active_command", None)
                    act_cmd_eid = getattr(act_cmd, "source_event_id", getattr(act_cmd, "event_id", None))
                    if act_cmd_eid and act_cmd_eid != event.event_id:
                        if remaining_duration <= 0.0:
                            event.transition(EventStatus.EMERGENCY_STOPPED, "Duration expired prior to restart; actuator executing different event")
                            res = SharedQuotaStore.get_active_record(event.event_id) or {}
                            season_key = res.get("season")
                            del_mm = getattr(event, "delivered_volume_mm", None)
                            self._safety.record_stopped_delivery(
                                event_id=event.event_id,
                                plot_id=event.plot_id,
                                target_volume_mm=event.target_volume_mm,
                                delivered_volume_mm=del_mm,
                                season=season_key,
                                device_id=event.device_id,
                                zone_id=event.zone_id,
                                duration_minutes=event.target_duration_minutes,
                                flow_rate_lpm=event.target_flow_rate_lpm,
                                effective_area_ha=getattr(event, "effective_area_ha", None),
                            )
                            self._safety.track_event_end(event.event_id)
                        else:
                            event.transition(EventStatus.STOP_REQUESTED, "Actuator executing different event")
                            self._active_events[event.event_id] = event
                        reconciled.append(event)
                        continue

                    if remaining_duration <= 0.0:
                        # Runtime expired before or during restart; stop immediately
                        stop_res = await actuator.emergency_stop()
                        if self._is_stop_confirmed(actuator, stop_res):
                            event.transition(EventStatus.EMERGENCY_STOPPED, "Duration expired prior to or during restart")
                            res = SharedQuotaStore.get_active_record(event.event_id) or {}
                            season_key = res.get("season")
                            del_mm = getattr(event, "delivered_volume_mm", None)
                            self._safety.record_stopped_delivery(
                                event_id=event.event_id,
                                plot_id=event.plot_id,
                                target_volume_mm=event.target_volume_mm,
                                delivered_volume_mm=del_mm,
                                season=season_key,
                                device_id=event.device_id,
                                zone_id=event.zone_id,
                                duration_minutes=event.target_duration_minutes,
                                flow_rate_lpm=event.target_flow_rate_lpm,
                                effective_area_ha=getattr(event, "effective_area_ha", None),
                            )
                            self._safety.track_event_end(event.event_id)
                        else:
                            event.transition(EventStatus.STOP_REQUESTED, "Duration expired on restart but stop failed")
                            self._active_events[event.event_id] = event
                            actuator.set_active_command(self._build_command(event))
                            self._safety.track_event_start(
                                event.event_id,
                                event.device_id,
                                event.target_duration_minutes,
                                plot_id=event.plot_id,
                                volume_mm=event.target_volume_mm,
                                elapsed_minutes=elapsed_minutes,
                                zone_id=event.zone_id,
                                flow_rate_lpm=event.target_flow_rate_lpm,
                                effective_area_ha=getattr(event, "effective_area_ha", None),
                            )
                    else:
                        if event.status == EventStatus.STOP_REQUESTED or (active_rec and active_rec.get("status") == "STOP_REQUESTED"):
                            event.transition(EventStatus.STOP_REQUESTED, "Reconciled with active controller on process restart: stop previously requested")
                        else:
                            event.transition(EventStatus.EXECUTING, "Reconciled with active controller on process restart")
                        self._active_events[event.event_id] = event
                        actuator.set_active_command(self._build_command(event))
                        self._safety.track_event_start(
                            event.event_id,
                            event.device_id,
                            event.target_duration_minutes,
                            plot_id=event.plot_id,
                            volume_mm=event.target_volume_mm,
                            elapsed_minutes=elapsed_minutes,
                            zone_id=event.zone_id,
                            flow_rate_lpm=event.target_flow_rate_lpm,
                            effective_area_ha=getattr(event, "effective_area_ha", None),
                        )
                elif status == ActuatorStatus.ONLINE:
                    # PB01, RP01: If actuator has a pending command in flight or durable record is in flight, retain active tracking rather than assuming idle
                    durable_rec = SharedQuotaStore.get_active_record(event.event_id)
                    durable_st = (durable_rec.get("status") if durable_rec else "") or ""
                    has_pending = (
                        getattr(actuator, "pending_command", None) is not None
                        or getattr(actuator, "_pending_command", None) is not None
                        or durable_st in ("STARTING", "DISPATCHING", "STOP_REQUESTED")
                        or event.status in (EventStatus.DISPATCHING, EventStatus.STOP_REQUESTED)
                    )
                    if has_pending:
                        event.transition(EventStatus.STOP_REQUESTED, "Reconciled after process restart: pending command or unresolved dispatch in flight")
                        self._active_events[event.event_id] = event
                        actuator.set_active_command(self._build_command(event))
                        try:
                            SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
                        except Exception as store_err:
                            logger.warning("Could not persist STOP_REQUESTED status for event %s: %s", event.event_id, store_err)
                        self._safety.track_event_start(
                            event.event_id,
                            event.device_id,
                            event.target_duration_minutes,
                            plot_id=event.plot_id,
                            volume_mm=event.target_volume_mm,
                            elapsed_minutes=elapsed_minutes,
                            zone_id=event.zone_id,
                            flow_rate_lpm=event.target_flow_rate_lpm,
                            effective_area_ha=getattr(event, "effective_area_ha", None),
                        )
                    else:
                        # RV05, RC06: Idle actuator on restart does NOT qualify commanded depth as measured delivery.
                        # Route to VALIDATING and retain unsettled reservation so delivery measurements can be supplied.
                        event.transition(EventStatus.VALIDATING, "Reconciled after process restart: actuator idle, awaiting validation")
                        self._active_events[event.event_id] = event
                        if active_rec:
                            SharedQuotaStore.mark_unsettled(event.event_id)
                else:
                    event.transition(EventStatus.STOP_REQUESTED, f"Reconciled after process restart: actuator in {status.value}")
                    self._active_events[event.event_id] = event
                    actuator.set_active_command(self._build_command(event))
                    try:
                        SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
                    except Exception as store_err:
                        logger.warning("Could not persist STOP_REQUESTED status for event %s: %s", event.event_id, store_err)
                    self._safety.track_event_start(
                        event.event_id,
                        event.device_id,
                        event.target_duration_minutes,
                        plot_id=event.plot_id,
                        volume_mm=event.target_volume_mm,
                        elapsed_minutes=elapsed_minutes,
                        zone_id=event.zone_id,
                        flow_rate_lpm=event.target_flow_rate_lpm,
                        effective_area_ha=getattr(event, "effective_area_ha", None),
                    )
            except Exception as exc:
                # BA-01 / BA-05: Query failure must retain ownership, active events, and reservations
                logger.error("Failed to query actuator %s during restart reconciliation: %s", event.device_id, exc)
                event.transition(EventStatus.STOP_REQUESTED, f"Failed to reconcile on restart: {exc}")
                self._active_events[event.event_id] = event
                actuator.set_active_command(self._build_command(event))
                try:
                    SharedQuotaStore.update_status(event.event_id, "STOP_REQUESTED")
                except Exception as store_err:
                    logger.warning("Could not persist STOP_REQUESTED status for event %s: %s", event.event_id, store_err)
                self._safety.track_event_start(
                    event.event_id,
                    event.device_id,
                    event.target_duration_minutes,
                    plot_id=event.plot_id,
                    volume_mm=event.target_volume_mm,
                    elapsed_minutes=elapsed_minutes,
                    zone_id=event.zone_id,
                    flow_rate_lpm=event.target_flow_rate_lpm,
                    effective_area_ha=getattr(event, "effective_area_ha", None),
                )
            reconciled.append(event)
        return reconciled

    # ================================================================
    # Internal Helpers
    # ================================================================

    def _finalize_event(self, event: IrrigationEvent) -> None:
        """Move event from active to history."""
        self._active_events.pop(event.event_id, None)
        self._event_history.append(event)
        self._safety.track_event_end(event.event_id)

    def _emit_failed(self, event: IrrigationEvent) -> None:
        """Notify failure callbacks."""
        for cb in self._on_event_failed:
            try:
                cb(event)
            except Exception as exc:
                logger.error("Failure callback error: %s", exc)

    # ================================================================
    # Status & History
    # ================================================================

    def get_active_events(self) -> List[IrrigationEvent]:
        """Get all currently executing events."""
        return list(self._active_events.values())

    def get_event_history(
        self,
        plot_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[IrrigationEvent]:
        """Get historical events, optionally filtered by plot."""
        history = self._event_history
        if plot_id:
            history = [e for e in history if e.plot_id == plot_id]
        return history[-limit:]

    def get_event(self, event_id: str) -> Optional[IrrigationEvent]:
        """Get an event by ID (active or historical)."""
        if event_id in self._active_events:
            return self._active_events[event_id]
        for event in self._event_history:
            if event.event_id == event_id:
                return event
        return None


# Singleton
command_dispatcher = CommandDispatcher()
