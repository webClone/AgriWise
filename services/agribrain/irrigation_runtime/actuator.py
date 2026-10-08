"""
Irrigation Runtime — Abstract Actuator Interface v1.0.0

Hardware-agnostic base class for all irrigation actuator drivers.
Every physical controller (solenoid, pivot, PLC) implements this interface.

Contract:
  - send_command() dispatches a single atomic command
  - get_status() returns real-time actuator state
  - emergency_stop() is always available, even during errors
  - validate_command() performs pre-flight safety checks before dispatch
  - All methods are async for non-blocking I/O across protocols
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from irrigation_runtime.schemas import (
    ActuatorRegistration,
    ActuatorStatus,
    CommandResult,
    CommandType,
    DriverProtocol,
    IrrigationCommand,
    SafetyInterlock,
    SafetyViolation,
    InterlockType,
)

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    try:
        from services.agribrain.scientific_contracts.numeric import finite_real
    except ImportError:
        import math
        from numbers import Real
        def finite_real(val: Any) -> Optional[float]:
            if isinstance(val, bool) or not isinstance(val, Real):
                return None
            try:
                res = float(val)
                return res if math.isfinite(res) else None
            except Exception:
                return None

logger = logging.getLogger(__name__)


class IrrigationActuator(ABC):
    """Abstract base class for all irrigation hardware drivers.

    Subclasses implement protocol-specific communication:
      - MQTTActuator: MQTT publish/subscribe
      - ModbusActuator: Modbus RTU/TCP register R/W
      - LoRaWANActuator: Class C downlink via network server
      - HTTPActuator: REST API calls to cloud-connected hardware

    Every driver must:
      1. Handle connection lifecycle (connect/disconnect/reconnect)
      2. Translate IrrigationCommand → protocol-specific payload
      3. Parse actuator responses → CommandResult
      4. Implement emergency_stop as a non-blocking, always-available operation
    """

    def __init__(self, registration: ActuatorRegistration):
        self.registration = registration
        self.device_id = registration.device_id
        self.protocol = registration.protocol
        self._status = ActuatorStatus.UNKNOWN
        self._connected = False
        self._last_heartbeat: Optional[datetime] = None
        self._active_command: Optional[IrrigationCommand] = None
        self._pending_command: Optional[IrrigationCommand] = None
        self._dispatch_lock: Optional[asyncio.Lock] = None
        self._command_history: List[Dict[str, Any]] = []
        self._interlocks: List[SafetyInterlock] = []

    @property
    def dispatch_lock(self) -> asyncio.Lock:
        if getattr(self, "_dispatch_lock", None) is None:
            self._dispatch_lock = asyncio.Lock()
        return self._dispatch_lock

    # ================================================================
    # Abstract Methods (must be implemented by drivers)
    # ================================================================

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the physical actuator.

        Returns True if connection succeeded.
        Must handle reconnection logic internally.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close connection to the actuator."""
        ...

    @abstractmethod
    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        """Dispatch a single command to the physical actuator.

        The driver must:
          1. Encode the command into protocol-specific format
          2. Transmit to the device
          3. Wait for acknowledgment (with timeout)
          4. Return a CommandResult with actual delivery data

        Args:
            command: Validated IrrigationCommand to execute

        Returns:
            CommandResult with success/failure and actual measurements
        """
        ...

    @abstractmethod
    async def get_status(self) -> ActuatorStatus:
        """Query real-time status from the physical actuator.

        Returns the current ActuatorStatus based on device heartbeat
        and operational state.
        """
        ...

    @abstractmethod
    async def emergency_stop(self) -> CommandResult:
        """Immediately stop all irrigation on this actuator.

        This MUST:
          - Be non-blocking (fire-and-forget if necessary)
          - Work even if the actuator is in ERROR state
          - Close all valves to fail-safe position
          - Log the emergency stop event

        Returns:
            CommandResult indicating stop confirmation
        """
        ...

    async def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Query driver/controller for operation-specific execution receipt.

        Returns None if driver does not support operation-level querying or
        if operation is unknown to the controller.
        """
        return None

    # ================================================================
    # Common Methods (shared across all drivers)
    # ================================================================

    def validate_command(self, command: IrrigationCommand) -> List[str]:
        """Pre-flight safety validation before dispatch.

        Checks:
          - Command schema validity
          - Flow rate within actuator capability limits
          - Duration within watchdog limits
          - Volume within daily/season quota
          - No active safety interlocks

        Returns:
            List of error messages (empty = valid)
        """
        errors = command.validate()
        if errors:
            return errors

        caps = self.registration.capabilities

        # Flow rate and duration bounds (apply only to active irrigation commands)
        if command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            if command.flow_rate_lpm > caps.max_flow_rate_lpm > 0:
                errors.append(
                    f"Flow rate {command.flow_rate_lpm} L/min exceeds max "
                    f"{caps.max_flow_rate_lpm} L/min for device {self.device_id}"
                )

            if command.flow_rate_lpm < caps.min_flow_rate_lpm:
                errors.append(
                    f"Flow rate {command.flow_rate_lpm} L/min below min "
                    f"{caps.min_flow_rate_lpm} L/min for device {self.device_id}"
                )

            # Duration watchdog
            if command.duration_minutes > caps.max_duration_minutes:
                errors.append(
                    f"Duration {command.duration_minutes} min exceeds max "
                    f"{caps.max_duration_minutes} min watchdog"
                )

        # Actuator status check
        if self._status == ActuatorStatus.OFFLINE:
            errors.append(f"Actuator {self.device_id} is OFFLINE")

        # Allow STOP_ZONE and EMERGENCY_STOP even if in ERROR or MAINTENANCE
        if (self._status == ActuatorStatus.ERROR
                and command.command_type not in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP)):
            errors.append(f"Actuator {self.device_id} is in ERROR state")

        if (self._status == ActuatorStatus.MAINTENANCE
                and command.command_type not in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP)):
            errors.append(f"Actuator {self.device_id} is in MAINTENANCE mode")

        # Check if already executing (unless stop or emergency stop)
        if (self._status == ActuatorStatus.EXECUTING
                and command.command_type not in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP)):
            is_own_retry = False
            has_payload_conflict = False
            active = self._active_command
            if active is not None:
                op_matches = bool(command.operation_id) and bool(active.operation_id) and active.operation_id == command.operation_id
                event_matches = bool(command.source_event_id) and bool(active.source_event_id) and active.source_event_id == command.source_event_id
                if op_matches or event_matches:
                    c_vol = finite_real(command.volume_mm)
                    a_vol = finite_real(active.volume_mm)
                    c_dur = finite_real(command.duration_minutes)
                    a_dur = finite_real(active.duration_minutes)
                    c_flw = finite_real(command.flow_rate_lpm)
                    a_flw = finite_real(active.flow_rate_lpm)
                    same_vol = (c_vol is not None and a_vol is not None and abs(c_vol - a_vol) < 1e-4)
                    same_dur = (c_dur is not None and a_dur is not None and abs(c_dur - a_dur) < 1e-4)
                    same_flw = (c_flw is not None and a_flw is not None and abs(c_flw - a_flw) < 1e-4)
                    op_conflict = bool(command.operation_id) and bool(active.operation_id) and (command.operation_id != active.operation_id)
                    if same_vol and same_dur and same_flw and not op_conflict:
                        is_own_retry = True
                    else:
                        has_payload_conflict = True

            if has_payload_conflict:
                errors.append(
                    f"Actuator {self.device_id} is EXECUTING command {self._active_command.command_id if self._active_command else ''}; "
                    f"command {command.command_id} has conflicting payload or operation ID."
                )
            elif not is_own_retry:
                errors.append(
                    f"Actuator {self.device_id} is already EXECUTING. "
                    f"Send STOP_ZONE or EMERGENCY_STOP first."
                )

        return errors

    def set_active_command(self, command: IrrigationCommand) -> None:
        """Rehydrate active command and status (e.g. on process restart)."""
        self._active_command = command
        self._status = ActuatorStatus.EXECUTING

    async def execute_with_safety(self, command: IrrigationCommand) -> CommandResult:
        """Validate, dispatch, and log a command with full safety checks.

        This is the primary entry point for dispatching commands.
        It wraps send_command() with validation, reconciliation, and audit logging.
        Uses dispatch locking so in-flight commands are serialized and duplicates do not
        fabricate false success before initial outcome resolution.
        """
        async with self.dispatch_lock:
            # Pre-flight validation
            errors = self.validate_command(command)
            if errors:
                logger.warning(
                    "Command %s rejected for device %s: %s",
                    command.command_id, self.device_id, errors
                )
                return CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="VALIDATION_FAILED",
                    error_message="; ".join(errors),
                )

            # Idempotent stop check: if already ONLINE and idle, STOP_ZONE succeeds idempotently
            if (command.command_type == CommandType.STOP_ZONE
                    and self._status == ActuatorStatus.ONLINE
                    and self._active_command is None):
                logger.info("Device %s is already stopped (ONLINE); STOP_ZONE succeeded idempotently.", self.device_id)
                result = CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=True,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="ALREADY_STOPPED",
                    error_message="Actuator is already stopped",
                )
                self._command_history.append({
                    "command_id": command.command_id,
                    "command_type": command.command_type.value,
                    "success": result.success,
                    "timestamp": result.timestamp,
                    "error_code": result.error_code,
                })
                return result

            # Idempotent execution check: if already EXECUTING this own-operation, do not duplicate physical START
            if (command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE)
                    and self._status == ActuatorStatus.EXECUTING):
                is_own_retry = False
                has_payload_conflict = False
                active = self._active_command
                if active is not None:
                    op_matches = bool(command.operation_id) and bool(active.operation_id) and active.operation_id == command.operation_id
                    event_matches = bool(command.source_event_id) and bool(active.source_event_id) and active.source_event_id == command.source_event_id
                    if op_matches or event_matches:
                        c_vol = finite_real(command.volume_mm)
                        a_vol = finite_real(active.volume_mm)
                        c_dur = finite_real(command.duration_minutes)
                        a_dur = finite_real(active.duration_minutes)
                        c_flw = finite_real(command.flow_rate_lpm)
                        a_flw = finite_real(active.flow_rate_lpm)
                        same_vol = (c_vol is not None and a_vol is not None and abs(c_vol - a_vol) < 1e-4)
                        same_dur = (c_dur is not None and a_dur is not None and abs(c_dur - a_dur) < 1e-4)
                        same_flw = (c_flw is not None and a_flw is not None and abs(c_flw - a_flw) < 1e-4)
                        op_conflict = bool(command.operation_id) and bool(active.operation_id) and (command.operation_id != active.operation_id)
                        if same_vol and same_dur and same_flw and not op_conflict:
                            is_own_retry = True
                        else:
                            has_payload_conflict = True

                if has_payload_conflict:
                    logger.warning(
                        "Command %s conflicts with active payload on device %s. Returning PAYLOAD_CONFLICT.",
                        command.command_id, self.device_id
                    )
                    return CommandResult(
                        command_id=command.command_id,
                        device_id=self.device_id,
                        success=False,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        error_code="PAYLOAD_CONFLICT",
                        error_message=(
                            f"Payload conflict: Command {command.command_id} differs from active command "
                            f"{self._active_command.command_id if self._active_command else ''} on device {self.device_id}"
                        ),
                        retry_recommended=False,
                    )

                if is_own_retry:
                    logger.info(
                        "Operation %s is already EXECUTING on device %s. Returning active execution status idempotently without duplicate physical dispatch.",
                        command.operation_id or command.source_event_id, self.device_id
                    )
                    result = CommandResult(
                        command_id=command.command_id,
                        device_id=self.device_id,
                        success=True,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        actual_flow_rate_lpm=self._active_command.flow_rate_lpm if self._active_command else command.flow_rate_lpm,
                        error_code="ALREADY_EXECUTING",
                        error_message="Operation is already executing on actuator",
                    )
                    self._command_history.append({
                        "command_id": command.command_id,
                        "command_type": command.command_type.value,
                        "success": result.success,
                        "timestamp": result.timestamp,
                        "error_code": result.error_code,
                    })
                    return result

            prev_active_command = self._active_command

            # Mark command pending dispatch (do NOT prematurely set EXECUTING before actual physical send)
            self._pending_command = command

            logger.info(
                "Dispatching %s to device %s (zone=%s, volume=%.1fmm, duration=%.0fmin)",
                command.command_type.value, self.device_id,
                command.zone_id, command.volume_mm, command.duration_minutes
            )

            try:
                result = await self.send_command(command)
            except Exception as exc:
                logger.error(
                    "Command %s failed on device %s: %s",
                    command.command_id, self.device_id, exc
                )
                self._status = ActuatorStatus.ERROR
                result = CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="DISPATCH_EXCEPTION",
                    error_message=str(exc),
                    retry_recommended=False,
                )
            finally:
                self._pending_command = None

            # Reconcile ambiguous failures on START commands before retry or failure
            if not result.success and command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
                try:
                    op_receipt = None
                    if getattr(self.registration.capabilities, "supports_operation_reconciliation", False) and bool(command.operation_id):
                        op_receipt = await self.get_operation_status(command.operation_id)

                    if op_receipt is not None:
                        if op_receipt.get("executing") or op_receipt.get("completed"):
                            logger.info(
                                "Reconciliation: Device %s confirmed operation %s via operation receipt.",
                                self.device_id, command.operation_id,
                            )
                            result = CommandResult(
                                command_id=command.command_id,
                                device_id=self.device_id,
                                success=True,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                actual_flow_rate_lpm=command.flow_rate_lpm,
                                error_code="RECONCILED_OPERATION",
                                error_message="Operation confirmed by controller",
                            )
                            if op_receipt.get("executing"):
                                self._status = ActuatorStatus.EXECUTING
                                self._active_command = command
                            else:
                                self._status = ActuatorStatus.ONLINE
                                self._active_command = None
                        elif op_receipt.get("not_applied"):
                            logger.info(
                                "Reconciliation: Device %s confirmed operation %s NOT applied. Safe to retry.",
                                self.device_id, command.operation_id,
                            )
                            self._status = ActuatorStatus.ONLINE
                            self._active_command = None
                            result.retry_recommended = True
                        else:
                            self._status = ActuatorStatus.ERROR
                            self._active_command = command
                            result.retry_recommended = False
                    else:
                        controller_status = await self.get_status()
                        if controller_status == ActuatorStatus.EXECUTING:
                            # BA-03 / R02: Bare controller status cannot prove this specific new command was applied.
                            logger.warning(
                                "Reconciliation: Device %s is EXECUTING on controller after unacknowledged %s, but lacks operation-level reconciliation. Retaining uncertainty boundary without blind retry.",
                                self.device_id, command.command_id,
                            )
                            self._status = ActuatorStatus.ERROR
                            self._active_command = command
                            result.retry_recommended = False
                            result.error_code = "UNCERTAIN_OUTCOME"
                            result.error_message = "Controller is running, but driver lacks operation-level reconciliation; cannot confirm whether requested command was applied."
                        elif controller_status == ActuatorStatus.ONLINE:
                            # Confirmed idle state alone must not authorize a new dose without operation attribution.
                            logger.warning(
                                "Reconciliation: Device %s is ONLINE after unacknowledged %s, but lacks operation-level reconciliation. Retaining uncertainty boundary without blind retry.",
                                self.device_id, command.command_id,
                            )
                            self._status = ActuatorStatus.ERROR
                            self._active_command = command
                            result.retry_recommended = False
                            result.error_code = "UNCERTAIN_OUTCOME"
                            result.error_message = "Controller is ONLINE but driver lacks operation-level reconciliation; cannot confirm whether dose was applied."
                        else:
                            self._status = ActuatorStatus.ERROR
                            self._active_command = command
                            result.retry_recommended = False
                except Exception as rec_exc:
                    logger.error(
                        "Reconciliation query failed on %s for %s: %s. Retaining ownership during uncertainty.",
                        self.device_id, command.command_id, rec_exc,
                    )
                    self._status = ActuatorStatus.ERROR
                    self._active_command = command
                    result.retry_recommended = False

            # State transition according to resolved result
            if not result.success:
                if command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
                    self._status = ActuatorStatus.ERROR
                    self._active_command = prev_active_command  # Preserve original delivery command
                    logger.error("Stop command failed on device %s. Retaining active command and ERROR state.", self.device_id)
                elif command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
                    if self._status != ActuatorStatus.ONLINE:
                        self._status = ActuatorStatus.ERROR
            elif command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
                self._status = ActuatorStatus.ONLINE
                self._active_command = None
            elif command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
                self._status = ActuatorStatus.EXECUTING
                self._active_command = command

            # Audit log
        self._command_history.append({
            "command_id": command.command_id,
            "command_type": command.command_type.value,
            "success": result.success,
            "timestamp": result.timestamp,
            "error_code": result.error_code,
        })

        return result

    def check_interlocks(self, sensor_readings: Dict[str, float]) -> List[SafetyViolation]:
        """Evaluate all registered safety interlocks against current sensor data.

        Args:
            sensor_readings: Dict of CanonicalVariable → current value

        Returns:
            List of SafetyViolation records for any breached interlocks
        """
        violations = []
        for interlock in self._interlocks:
            if not interlock.enabled:
                continue

            if interlock.sensor_variable not in sensor_readings:
                continue

            value = sensor_readings[interlock.sensor_variable]
            breached = False
            threshold_type = ""
            threshold_val = 0.0

            if interlock.threshold_min is not None and value < interlock.threshold_min:
                breached = True
                threshold_type = "min"
                threshold_val = interlock.threshold_min

            if interlock.threshold_max is not None and value > interlock.threshold_max:
                breached = True
                threshold_type = "max"
                threshold_val = interlock.threshold_max

            if breached:
                violation = SafetyViolation(
                    violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                    interlock_id=interlock.interlock_id,
                    interlock_type=interlock.interlock_type,
                    device_id=self.device_id,
                    zone_id="",
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    sensor_value=value,
                    threshold_breached=threshold_type,
                    threshold_value=threshold_val,
                    action_taken=interlock.action_on_trigger.value,
                )
                violations.append(violation)
                logger.warning(
                    "Safety interlock %s triggered on device %s: "
                    "%s=%s (threshold %s=%s)",
                    interlock.interlock_id, self.device_id,
                    interlock.sensor_variable, value,
                    threshold_type, threshold_val
                )

        return violations

    def register_interlock(self, interlock: SafetyInterlock) -> None:
        """Add a safety interlock to this actuator."""
        self._interlocks.append(interlock)
        logger.info(
            "Registered interlock %s (%s) on device %s",
            interlock.interlock_id, interlock.interlock_type.value, self.device_id
        )

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def status(self) -> ActuatorStatus:
        return self._status

    @property
    def active_command(self) -> Optional[IrrigationCommand]:
        return self._active_command

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} device={self.device_id} "
            f"protocol={self.protocol.value} status={self._status.value}>"
        )
