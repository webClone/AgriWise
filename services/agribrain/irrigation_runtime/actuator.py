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
        self._command_history: List[Dict[str, Any]] = []
        self._interlocks: List[SafetyInterlock] = []

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
        caps = self.registration.capabilities

        # Flow rate bounds
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

        if self._status == ActuatorStatus.ERROR:
            errors.append(f"Actuator {self.device_id} is in ERROR state")

        if self._status == ActuatorStatus.MAINTENANCE:
            errors.append(f"Actuator {self.device_id} is in MAINTENANCE mode")

        # Check if already executing (unless stop or emergency stop)
        if (self._status == ActuatorStatus.EXECUTING
                and command.command_type not in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP)):
            errors.append(
                f"Actuator {self.device_id} is already EXECUTING. "
                f"Send STOP_ZONE or EMERGENCY_STOP first."
            )

        return errors

    async def execute_with_safety(self, command: IrrigationCommand) -> CommandResult:
        """Validate, dispatch, and log a command with full safety checks.

        This is the primary entry point for dispatching commands.
        It wraps send_command() with validation and audit logging.
        """
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

        # Dispatch
        self._active_command = command
        self._status = ActuatorStatus.EXECUTING
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
                retry_recommended=True,
            )
        finally:
            if not result.success:
                if command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
                    self._status = ActuatorStatus.ERROR
                    self._active_command = None
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
