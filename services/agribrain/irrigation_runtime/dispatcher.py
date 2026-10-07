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
    ):
        self._registry = registry
        self._safety = safety
        self._active_events: Dict[str, IrrigationEvent] = {}
        self._event_history: List[IrrigationEvent] = []
        self._max_retries = 3
        self._retry_base_delay = 2.0  # seconds

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

        # Resolve actuator
        actuator = self._registry.get_actuator(event.device_id)
        if actuator is None:
            event.transition(EventStatus.FAILED, f"Actuator {event.device_id} not found in registry")
            self._emit_failed(event)
            return event

        # Pre-flight safety check
        if sensor_readings:
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

            # Register with safety monitor for duration watchdog
            self._safety.track_event_start(
                event.event_id,
                event.device_id,
                event.target_duration_minutes,
            )

            logger.info("Event %s executing on device %s",
                        event.event_id, event.device_id)
        else:
            event.transition(
                EventStatus.FAILED,
                f"Dispatch failed after retries: {result.error_message}"
            )
            self._active_events.pop(event.event_id, None)
            self._emit_failed(event)

        return event

    # ================================================================
    # Command Building
    # ================================================================

    def _build_command(self, event: IrrigationEvent) -> IrrigationCommand:
        """Build an IrrigationCommand from an IrrigationEvent."""
        # Map urgency to command priority
        priority_map = {
            "LOW": CommandPriority.LOW,
            "NORMAL": CommandPriority.NORMAL,
            "HIGH": CommandPriority.HIGH,
            "CRITICAL": CommandPriority.CRITICAL,
        }

        return IrrigationCommand(
            command_id=f"CMD-{uuid.uuid4().hex[:12]}",
            command_type=CommandType.START_ZONE,
            device_id=event.device_id,
            zone_id=event.zone_id,
            plot_id=event.plot_id,
            volume_mm=event.target_volume_mm,
            duration_minutes=event.target_duration_minutes,
            flow_rate_lpm=event.target_flow_rate_lpm,
            priority=priority_map.get("NORMAL", CommandPriority.NORMAL),
            source_event_id=event.event_id,
            source_action_id=event.source_action_id,
            automation_mode=event.automation_mode,
            approved_by=event.approved_by,
            approved_at=event.approved_at,
            request_id=str(uuid.uuid4()),
        )

    # ================================================================
    # Dispatch with Retry
    # ================================================================

    async def _dispatch_with_retry(
        self,
        event: IrrigationEvent,
        actuator: IrrigationActuator,
    ) -> CommandResult:
        """Dispatch a command with exponential backoff retry."""
        last_result: Optional[CommandResult] = None

        for attempt in range(self._max_retries + 1):
            command = self._build_command(event)
            result = await actuator.execute_with_safety(command)

            if result.success:
                return result

            last_result = result

            if not result.retry_recommended:
                logger.warning(
                    "Non-retryable failure for event %s: %s",
                    event.event_id, result.error_message,
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
            event.transition(EventStatus.FAILED, "Actuator lost during execution")
            self._finalize_event(event)
            return event

        # Check actuator status
        from irrigation_runtime.schemas import ActuatorStatus
        status = await actuator.get_status()

        if status == ActuatorStatus.ERROR:
            event.transition(EventStatus.FAILED, "Actuator entered ERROR state")
            self._finalize_event(event)
            self._emit_failed(event)
            return event

        # Check safety interlocks
        if sensor_readings:
            violations = self._safety.evaluate(
                event.device_id, sensor_readings, actuator.active_command
            )
            if violations:
                # Emergency stop
                await actuator.emergency_stop()
                event.emergency_stopped = True
                event.emergency_stop_reason = "; ".join(
                    v.interlock_type.value for v in violations
                )
                event.safety_violations.extend(v.violation_id for v in violations)
                event.transition(EventStatus.EMERGENCY_STOPPED,
                                 f"Safety violation: {event.emergency_stop_reason}")
                self._finalize_event(event)
                self._emit_failed(event)
                return event

        # Check if execution is complete (actuator no longer running)
        if status != ActuatorStatus.EXECUTING and event.status == EventStatus.EXECUTING:
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
        if actuator:
            stop_cmd = IrrigationCommand(
                command_id=f"CMD-STOP-{uuid.uuid4().hex[:8]}",
                command_type=CommandType.STOP_ZONE,
                device_id=event.device_id,
                zone_id=event.zone_id,
                plot_id=event.plot_id,
            )
            await actuator.execute_with_safety(stop_cmd)

        event.transition(EventStatus.CANCELLED, reason or "Cancelled by user")
        self._finalize_event(event)
        return event

    async def emergency_stop_all(self) -> Dict[str, str]:
        """Emergency stop all active events."""
        results = {}
        for event_id, event in list(self._active_events.items()):
            event.emergency_stopped = True
            event.emergency_stop_reason = "Global emergency stop"
            event.transition(EventStatus.EMERGENCY_STOPPED, "Global emergency stop")
            self._finalize_event(event)
            results[event_id] = "STOPPED"

        # Also stop all actuators
        await self._registry.emergency_stop_all()
        return results

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
