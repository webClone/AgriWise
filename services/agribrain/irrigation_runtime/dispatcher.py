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
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.registry import ActuatorRegistry, actuator_registry
from irrigation_runtime.safety import SafetyMonitor, safety_monitor
from irrigation_runtime.schemas import (
    AutomationMode,
    CommandPriority,
    CommandResult,
    CommandType,
    EventStatus,
    IrrigationCommand,
    IrrigationEvent,
    IrrigationSystemType,
    WaterBudget,
)

logger = logging.getLogger(__name__)


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
                logger.warning("Event %s is already active with status %s; returning existing event without duplicate dispatch.",
                               event.event_id, existing.status.value)
                return existing

        # Check if already finalized in local history
        for past in self._event_history:
            if past.event_id == event.event_id:
                logger.warning("Event %s already finalized with status %s; returning historical event.",
                               event.event_id, past.status.value)
                return past

        # BA-03: Durable idempotency across fresh dispatcher instances via shared store
        from irrigation_runtime.safety import SharedQuotaStore
        if SharedQuotaStore.is_settled(event.event_id):
            logger.warning("Event %s already finalized and settled in shared store; returning completed event.", event.event_id)
            event.status = EventStatus.COMPLETED
            return event
        if SharedQuotaStore.is_active(event.event_id) and event.event_id not in self._active_events:
            logger.warning("Event %s already active in shared store; returning active event.", event.event_id)
            event.status = EventStatus.EXECUTING
            return event

        # Resolve actuator
        actuator = self._registry.get_actuator(event.device_id)
        if actuator is None:
            event.transition(EventStatus.FAILED, f"Actuator {event.device_id} not found in registry")
            self._emit_failed(event)
            return event

        # BA-02: Atomic check-and-reserve under cross-process lock BEFORE dispatch
        if budget and event.target_volume_mm > 0:
            quota_violation = SharedQuotaStore.atomic_check_and_reserve(
                plot_id=event.plot_id,
                requested_volume_mm=event.target_volume_mm,
                budget=budget,
                event_id=event.event_id,
            )
            if quota_violation:
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

        # Begin dispatch
        event.transition(EventStatus.DISPATCHING, "Starting command dispatch")
        self._active_events[event.event_id] = event

        # Dispatch with retry
        result = await self._dispatch_with_retry(event, actuator)

        if result.success:
            event.transition(EventStatus.EXECUTING, "Command acknowledged by actuator")
            event.actual_start = datetime.now(timezone.utc).isoformat()
            event.command_ids.append(result.command_id)

            # Register with safety monitor for monotonic duration watchdog and active quota
            self._safety.track_event_start(
                event.event_id,
                event.device_id,
                event.target_duration_minutes,
                plot_id=event.plot_id,
                volume_mm=event.target_volume_mm,
            )

            logger.info("Event %s executing on device %s",
                        event.event_id, event.device_id)
        else:
            # BA-01: Uncertain physical outcomes must retain dispatcher ownership, tracking, and quota
            from irrigation_runtime.schemas import ActuatorStatus
            is_uncertain = (
                result.error_code in ("UNCERTAIN_OUTCOME", "ACK_TIMEOUT", "DISPATCH_EXCEPTION")
                or actuator.active_command is not None
                or getattr(actuator, "_status", None) == ActuatorStatus.ERROR
            )
            if is_uncertain:
                logger.error(
                    "Uncertain dispatch outcome for event %s on device %s: %s. Preserving ownership and reservation.",
                    event.event_id, event.device_id, result.error_message
                )
                event.transition(EventStatus.STOP_REQUESTED, f"Uncertain physical outcome: {result.error_message}")
                self._safety.track_event_start(
                    event.event_id,
                    event.device_id,
                    event.target_duration_minutes,
                    plot_id=event.plot_id,
                    volume_mm=event.target_volume_mm,
                )
                self._emit_failed(event)
            else:
                event.transition(
                    EventStatus.FAILED,
                    f"Dispatch failed after retries: {result.error_message}"
                )
                self._active_events.pop(event.event_id, None)
                self._safety.release_quota(event.event_id)
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
            command = self._build_command(
                event,
                attempt=attempt + 1,
                operation_id=op_id,
            )
            result = await actuator.execute_with_safety(command)

            if result.success:
                return result

            last_result = result

            if not result.retry_recommended:
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
            return event

        from irrigation_runtime.schemas import ActuatorStatus

        # If already in STOP_REQUESTED, attempt stop reconciliation/retry
        if event.status == EventStatus.STOP_REQUESTED:
            try:
                status = await asyncio.wait_for(actuator.get_status(), timeout=5.0)
            except Exception:
                status = ActuatorStatus.ERROR

            if status == ActuatorStatus.ONLINE:
                term_status = EventStatus.EMERGENCY_STOPPED if event.emergency_stopped else EventStatus.CANCELLED
                event.transition(term_status, "Confirmed stopped on actuator after reconciliation")
                self._safety.release_quota(event.event_id)
                self._finalize_event(event)
                if term_status == EventStatus.EMERGENCY_STOPPED:
                    self._emit_failed(event)
                return event
            else:
                stop_retry = await actuator.emergency_stop()
                if stop_retry.success:
                    term_status = EventStatus.EMERGENCY_STOPPED if event.emergency_stopped else EventStatus.CANCELLED
                    event.transition(term_status, "Confirmed stopped on actuator after retry")
                    self._safety.release_quota(event.event_id)
                    self._finalize_event(event)
                    if term_status == EventStatus.EMERGENCY_STOPPED:
                        self._emit_failed(event)
                    return event
                return event

        # Check safety interlocks & duration watchdog unconditionally FIRST (without waiting for telemetry)
        violations = self._safety.evaluate(
            event.device_id, sensor_readings, actuator.active_command
        )
        if violations:
            stop_result = await actuator.emergency_stop()
            event.emergency_stopped = True
            event.emergency_stop_reason = "; ".join(
                v.interlock_type.value for v in violations
            )
            event.safety_violations.extend(v.violation_id for v in violations)
            if stop_result.success:
                actuator._status = ActuatorStatus.ONLINE
                actuator._active_command = None
                event.transition(EventStatus.EMERGENCY_STOPPED,
                                 f"Safety violation: {event.emergency_stop_reason}")
                self._safety.release_quota(event.event_id)
                self._finalize_event(event)
                self._emit_failed(event)
            else:
                actuator._status = ActuatorStatus.ERROR
                event.transition(EventStatus.STOP_REQUESTED,
                                 f"Emergency stop attempt failed: {stop_result.error_message}")
                logger.error("Emergency stop failed on device %s for event %s. Retaining tracking and quota.",
                             event.device_id, event.event_id)
            return event

        # Check actuator status with timeout to avoid stalling on hung status queries
        try:
            status = await asyncio.wait_for(actuator.get_status(), timeout=5.0)
        except Exception as exc:
            logger.error("Actuator status query failed or timed out for device %s: %s", event.device_id, exc)
            status = ActuatorStatus.ERROR

        # BA-01: OFFLINE status means communications lost, NOT confirmed stopped!
        if status == ActuatorStatus.OFFLINE:
            logger.warning("Actuator %s is OFFLINE during execution of event %s. Retaining exposure and tracking.",
                           event.device_id, event.event_id)
            event.transition(EventStatus.STOP_REQUESTED, "Actuator OFFLINE during execution; communications lost")
            return event

        if status == ActuatorStatus.ERROR:
            stop_result = await actuator.emergency_stop()
            if stop_result.success:
                actuator._status = ActuatorStatus.ONLINE
                actuator._active_command = None
                event.transition(EventStatus.FAILED, "Actuator entered ERROR state (stopped)")
                self._safety.release_quota(event.event_id)
                self._finalize_event(event)
                self._emit_failed(event)
            else:
                actuator._status = ActuatorStatus.ERROR
                event.transition(EventStatus.STOP_REQUESTED, "Actuator entered ERROR state and stop failed")
                logger.error("Stop attempt failed for device in ERROR state %s: %s", event.device_id, stop_result.error_message)
            return event

        # Check if execution is complete: actuator must be confirmed ONLINE and idle
        if status == ActuatorStatus.ONLINE and event.status == EventStatus.EXECUTING:
            event.actual_end = datetime.now(timezone.utc).isoformat()
            event.transition(EventStatus.VALIDATING, "Execution completed, entering validation")
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
        actual_volume_l: float = 0.0,
        actual_duration_minutes: float = 0.0,
    ) -> Optional[IrrigationEvent]:
        """Mark an event as completed with actual delivery data."""
        event = self._active_events.get(event_id)
        if not event:
            return None

        event.actual_volume_l = actual_volume_l
        event.actual_duration_minutes = actual_duration_minutes
        event.transition(EventStatus.COMPLETED, "Validated and completed")
        # Settle quota in shared store
        self._safety.settle_quota(event.event_id, event.plot_id, event.target_volume_mm)
        self._finalize_event(event)

        for cb in self._on_event_complete:
            try:
                cb(event)
            except Exception as exc:
                logger.error("Completion callback error: %s", exc)

        return event

    async def cancel_event(self, event_id: str, reason: str = "") -> Optional[IrrigationEvent]:
        """Cancel an active event and stop the actuator."""
        event = self._active_events.get(event_id)
        if not event:
            return None

        # Stop the actuator
        actuator = self._registry.get_actuator(event.device_id)
        stop_success = False
        if actuator:
            stop_cmd = IrrigationCommand(
                command_id=f"CMD-STOP-{uuid.uuid4().hex[:8]}",
                command_type=CommandType.STOP_ZONE,
                device_id=event.device_id,
                zone_id=event.zone_id,
                plot_id=event.plot_id,
                source_event_id=event.event_id,
                operation_id=f"OP-STOP-{event.event_id}",
            )
            stop_res = await actuator.execute_with_safety(stop_cmd)
            stop_success = stop_res.success

        if stop_success:
            event.transition(EventStatus.CANCELLED, reason or "Cancelled by user")
            self._safety.release_quota(event.event_id)
            self._finalize_event(event)
        else:
            event.transition(EventStatus.STOP_REQUESTED, f"Cancellation stop failed: {reason or 'stop unconfirmed'}")
            logger.error("Cancel stop failed on device %s for event %s. Retaining active tracking and quota.",
                         event.device_id, event.event_id)
        return event

    async def emergency_stop_all(self) -> Dict[str, str]:
        """Emergency stop all active events."""
        results = {}
        for event_id, event in list(self._active_events.items()):
            actuator = self._registry.get_actuator(event.device_id)
            stop_success = False
            if actuator:
                stop_res = await actuator.emergency_stop()
                stop_success = stop_res.success
                if stop_success:
                    actuator._status = ActuatorStatus.ONLINE
                    actuator._active_command = None
                else:
                    actuator._status = ActuatorStatus.ERROR
            if stop_success:
                event.emergency_stopped = True
                event.emergency_stop_reason = "Global emergency stop"
                event.transition(EventStatus.EMERGENCY_STOPPED, "Global emergency stop")
                self._safety.release_quota(event.event_id)
                self._finalize_event(event)
                results[event_id] = "STOPPED"
            else:
                event.emergency_stopped = True
                event.emergency_stop_reason = "Global emergency stop (stop unconfirmed)"
                event.transition(EventStatus.STOP_REQUESTED, "Global emergency stop failed on actuator")
                results[event_id] = "STOP_FAILED"

        # Also stop all actuators in registry
        await self._registry.emergency_stop_all()
        return results

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
            if event.status not in (EventStatus.DISPATCHING, EventStatus.EXECUTING, EventStatus.STOP_REQUESTED):
                continue

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
                )
                reconciled.append(event)
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
                    elapsed_minutes = 0.0

            remaining_duration = max(0.0, event.target_duration_minutes - elapsed_minutes)

            # BA-05: Persisted STOP_REQUESTED must retain stop intent; do not revert to EXECUTING!
            if event.status == EventStatus.STOP_REQUESTED:
                try:
                    stop_res = await actuator.emergency_stop()
                    if stop_res.success:
                        event.transition(
                            EventStatus.EMERGENCY_STOPPED if event.emergency_stopped else EventStatus.CANCELLED,
                            "Confirmed stopped on restart"
                        )
                        self._safety.release_quota(event.event_id)
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
                    )
                reconciled.append(event)
                continue

            try:
                from irrigation_runtime.schemas import ActuatorStatus
                status = await asyncio.wait_for(actuator.get_status(), timeout=5.0)

                if status == ActuatorStatus.EXECUTING:
                    if remaining_duration <= 0.0:
                        # Runtime expired before or during restart; stop immediately
                        stop_res = await actuator.emergency_stop()
                        if stop_res.success:
                            event.transition(EventStatus.EMERGENCY_STOPPED, "Duration expired prior to or during restart")
                            self._safety.release_quota(event.event_id)
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
                            )
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
                        )
                elif status == ActuatorStatus.ONLINE:
                    event.transition(EventStatus.COMPLETED, "Reconciled after process restart: actuator is stopped/idle")
                    self._safety.settle_quota(event.event_id, event.plot_id, event.target_volume_mm)
                else:
                    event.transition(EventStatus.STOP_REQUESTED, f"Reconciled after process restart: actuator in {status.value}")
                    self._active_events[event.event_id] = event
                    actuator.set_active_command(self._build_command(event))
                    self._safety.track_event_start(
                        event.event_id,
                        event.device_id,
                        event.target_duration_minutes,
                        plot_id=event.plot_id,
                        volume_mm=event.target_volume_mm,
                        elapsed_minutes=elapsed_minutes,
                    )
            except Exception as exc:
                # BA-01 / BA-05: Query failure must retain ownership, active events, and reservations
                logger.error("Failed to query actuator %s during restart reconciliation: %s", event.device_id, exc)
                event.transition(EventStatus.STOP_REQUESTED, f"Failed to reconcile on restart: {exc}")
                self._active_events[event.event_id] = event
                actuator.set_active_command(self._build_command(event))
                self._safety.track_event_start(
                    event.event_id,
                    event.device_id,
                    event.target_duration_minutes,
                    plot_id=event.plot_id,
                    volume_mm=event.target_volume_mm,
                    elapsed_minutes=elapsed_minutes,
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
