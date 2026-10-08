"""
Unit tests for F18 (actuator command retry reconciliation) and F19 (interlock debounce and stable keys).
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from typing import Dict, List, Optional

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.dispatcher import CommandDispatcher
from irrigation_runtime.registry import ActuatorRegistry
from irrigation_runtime.safety import SafetyMonitor, SharedQuotaStore
from irrigation_runtime.schemas import (
    ActuatorCapabilities,
    ActuatorRegistration,
    ActuatorStatus,
    AutomationMode,
    CommandPriority,
    CommandResult,
    CommandType,
    DriverProtocol,
    EventStatus,
    FailSafeState,
    InterlockType,
    IrrigationCommand,
    IrrigationEvent,
    IrrigationSystemType,
    SafetyInterlock,
    SafetyViolation,
    VendorId,
    WaterBudget,
)


class MockReconciliationActuator(IrrigationActuator):
    """Test actuator capable of simulating transient ACK timeouts and hardware state."""

    def __init__(self, device_id: str = "VALVE-RECON-01"):
        reg = ActuatorRegistration(
            device_id=device_id,
            zone_ids=["ZONE-1"],
            plot_id="PLOT-1",
            farm_id="farm-1",
            protocol=DriverProtocol.MQTT,
            vendor=VendorId.GENERIC,
            model="SimValve-Pro",
            firmware_version="1.0.0",
            capabilities=ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=100.0,
                min_flow_rate_lpm=1.0,
                max_duration_minutes=120.0,
                supports_operation_reconciliation=True,
            ),
            fail_safe_state=FailSafeState.NORMALLY_CLOSED,
            connection_config={},
        )
        super().__init__(reg)
        self._connected = True
        self._status = ActuatorStatus.ONLINE
        self.sent_commands: List[IrrigationCommand] = []
        self.simulated_hardware_status: ActuatorStatus = ActuatorStatus.ONLINE
        self.fail_send_with_ack_timeout: bool = False
        self.fail_first_send_only: bool = False

    async def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        if self.simulated_hardware_status == ActuatorStatus.EXECUTING:
            return {"executing": True}
        if self.simulated_hardware_status == ActuatorStatus.ONLINE:
            if self.fail_first_send_only and len(self.sent_commands) == 1:
                return {"not_applied": True}
            return {"completed": True}
        return None

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def get_status(self) -> ActuatorStatus:
        return self.simulated_hardware_status

    async def emergency_stop(self) -> CommandResult:
        self.simulated_hardware_status = ActuatorStatus.ONLINE
        self._status = ActuatorStatus.ONLINE
        self._active_command = None
        return CommandResult(
            command_id="ESTOP-01",
            device_id=self.device_id,
            success=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        self.sent_commands.append(command)

        if self.fail_send_with_ack_timeout or (self.fail_first_send_only and len(self.sent_commands) == 1):
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_code="ACK_TIMEOUT",
                error_message="No ACK received within timeout",
                retry_recommended=True,
            )

        if command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.simulated_hardware_status = ActuatorStatus.EXECUTING
        elif command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
            self.simulated_hardware_status = ActuatorStatus.ONLINE

        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
            actual_flow_rate_lpm=command.flow_rate_lpm,
            actual_pressure_bar=2.5,
        )


class MockRegistry:
    def __init__(self, actuator: IrrigationActuator):
        self._actuator = actuator

    def get_actuator(self, device_id: str) -> Optional[IrrigationActuator]:
        if device_id == self._actuator.device_id:
            return self._actuator
        return None

    async def emergency_stop_all(self):
        await self._actuator.emergency_stop()


class TestIrrigationF18Reconciliation(unittest.IsolatedAsyncioTestCase):
    """Test suite for F18: Command retry reconciliation & controller state queries."""

    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    async def test_ack_timeout_reconciled_when_controller_is_executing_no_duplicate_dose(self):
        """When ACK times out but controller confirms EXECUTING, command is reconciled as success without duplicate send."""
        actuator = MockReconciliationActuator("VALVE-F18-01")
        # Simulate that hardware actually started despite ACK timeout
        actuator.fail_send_with_ack_timeout = True
        actuator.simulated_hardware_status = ActuatorStatus.EXECUTING

        safety = SafetyMonitor()
        registry = MockRegistry(actuator)
        dispatcher = CommandDispatcher(registry=registry, safety=safety, max_retries=2, retry_base_delay=0.01)

        event = IrrigationEvent(
            event_id="EVT-F18-RECON-1",
            plot_id="PLOT-F18",
            zone_id="ZONE-1",
            device_id="VALVE-F18-01",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=10.0,
            target_duration_minutes=20.0,
            target_flow_rate_lpm=15.0,
        )

        res_event = await dispatcher.submit_event(event)

        # 1. Event succeeded and entered EXECUTING
        self.assertEqual(res_event.status, EventStatus.EXECUTING)
        # 2. Only ONE physical send command was dispatched (never duplicated dose)
        self.assertEqual(len(actuator.sent_commands), 1)
        # 3. Actuator maintained EXECUTING status
        self.assertEqual(actuator.status, ActuatorStatus.EXECUTING)
        self.assertIsNotNone(actuator.active_command)

    async def test_ack_timeout_retried_safely_when_controller_is_online(self):
        """When ACK times out and controller confirms ONLINE (not applied), retry proceeds with stable operation identity."""
        actuator = MockReconciliationActuator("VALVE-F18-02")
        # First send fails with ACK timeout, controller is ONLINE. Second send succeeds.
        actuator.fail_first_send_only = True
        actuator.simulated_hardware_status = ActuatorStatus.ONLINE

        safety = SafetyMonitor()
        registry = MockRegistry(actuator)
        dispatcher = CommandDispatcher(registry=registry, safety=safety, max_retries=2, retry_base_delay=0.01)

        event = IrrigationEvent(
            event_id="EVT-F18-RETRY-1",
            plot_id="PLOT-F18",
            zone_id="ZONE-1",
            device_id="VALVE-F18-02",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=10.0,
            target_duration_minutes=20.0,
            target_flow_rate_lpm=15.0,
        )

        res_event = await dispatcher.submit_event(event)

        self.assertEqual(res_event.status, EventStatus.EXECUTING)
        # Exactly two sends occurred: initial attempt (A1) and retry (A2)
        self.assertEqual(len(actuator.sent_commands), 2)

        cmd1, cmd2 = actuator.sent_commands
        # Stable operation identity across retries
        self.assertEqual(cmd1.operation_id, cmd2.operation_id)
        self.assertEqual(cmd1.source_event_id, cmd2.source_event_id)
        self.assertEqual(cmd1.attempt_number, 1)
        self.assertEqual(cmd2.attempt_number, 2)

    async def test_restart_reconciliation_restores_active_event_and_completed_states(self):
        """Process restart reconciles hardware EXECUTING and ONLINE states correctly."""
        actuator = MockReconciliationActuator("VALVE-F18-03")
        safety = SafetyMonitor()
        registry = MockRegistry(actuator)
        dispatcher = CommandDispatcher(registry=registry, safety=safety)

        # 1. Hardware is EXECUTING on restart
        actuator.simulated_hardware_status = ActuatorStatus.EXECUTING
        event_running = IrrigationEvent(
            event_id="EVT-RESTART-RUNNING",
            plot_id="PLOT-1",
            zone_id="ZONE-1",
            device_id="VALVE-F18-03",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.DISPATCHING,
            target_duration_minutes=30.0,
            target_volume_mm=15.0,
        )

        reconciled = await dispatcher.reconcile_on_restart([event_running])
        self.assertEqual(len(reconciled), 1)
        self.assertEqual(reconciled[0].status, EventStatus.EXECUTING)
        self.assertIn("EVT-RESTART-RUNNING", dispatcher.get_active_events()[0].event_id)

        # 2. Hardware is ONLINE (stopped) on restart
        actuator.simulated_hardware_status = ActuatorStatus.ONLINE
        event_stopped = IrrigationEvent(
            event_id="EVT-RESTART-STOPPED",
            plot_id="PLOT-1",
            zone_id="ZONE-1",
            device_id="VALVE-F18-03",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.EXECUTING,
            target_duration_minutes=30.0,
            target_volume_mm=15.0,
        )

        reconciled2 = await dispatcher.reconcile_on_restart([event_stopped])
        self.assertEqual(len(reconciled2), 1)
        self.assertEqual(reconciled2[0].status, EventStatus.COMPLETED)


class TestIrrigationF19DebounceAndStableKeys(unittest.TestCase):
    """Test suite for F19: Debounce, monotonic timing, stable violation keys, and reset rules."""

    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    def test_configured_debounce_is_honored_with_fake_clock(self):
        """Pressure spike emits violation ONLY after configured duration_seconds (5s) has elapsed."""
        fake_time = 1000.0
        monitor = SafetyMonitor(clock=lambda: fake_time)

        interlock = SafetyInterlock(
            interlock_id="INT-PRESSURE-HIGH",
            interlock_type=InterlockType.PRESSURE_HIGH,
            description="Over-pressure protection",
            sensor_variable="irrigation_pressure_bar",
            threshold_max=8.0,
            duration_seconds=5,
            action_on_trigger=CommandType.EMERGENCY_STOP,
            requires_manual_reset=True,
        )
        monitor.set_interlocks([interlock])

        # t = 1000.0: Initial breach (9.0 bar > 8.0 bar)
        v0 = monitor.evaluate("DEV-01", {"irrigation_pressure_bar": 9.0})
        self.assertEqual(v0, [], "Initial breach must not emit immediately due to 5s debounce")

        # t = 1004.0: Elapsed 4.0s < 5.0s debounce
        fake_time = 1004.0
        v4 = monitor.evaluate("DEV-01", {"irrigation_pressure_bar": 9.0})
        self.assertEqual(v4, [], "Debounce period not elapsed (4s < 5s)")

        # t = 1005.1: Elapsed 5.1s >= 5.0s debounce -> triggers!
        fake_time = 1005.1
        v5 = monitor.evaluate("DEV-01", {"irrigation_pressure_bar": 9.0})
        self.assertEqual(len(v5), 1, "Violation must trigger once debounce period elapses")
        self.assertEqual(v5[0].interlock_id, "INT-PRESSURE-HIGH")
        self.assertEqual(v5[0].sensor_value, 9.0)

    def test_sustained_breach_emits_one_active_violation_until_reset(self):
        """A sustained breach continues to emit zero duplicate violations while active."""
        fake_time = 100.0
        monitor = SafetyMonitor(clock=lambda: fake_time)

        interlock = SafetyInterlock(
            interlock_id="INT-PRESSURE-HIGH",
            interlock_type=InterlockType.PRESSURE_HIGH,
            description="Over-pressure protection",
            sensor_variable="irrigation_pressure_bar",
            threshold_max=8.0,
            duration_seconds=5,
            action_on_trigger=CommandType.EMERGENCY_STOP,
            requires_manual_reset=True,
        )
        monitor.set_interlocks([interlock])

        # Step through debounce to trigger
        monitor.evaluate("DEV-01", {"irrigation_pressure_bar": 9.0})
        fake_time = 106.0
        v_initial = monitor.evaluate("DEV-01", {"irrigation_pressure_bar": 9.0})
        self.assertEqual(len(v_initial), 1)

        # Subsequent evaluations while breach is sustained
        fake_time = 110.0
        v_subsequent1 = monitor.evaluate("DEV-01", {"irrigation_pressure_bar": 9.2})
        self.assertEqual(v_subsequent1, [], "Sustained breach must not emit duplicate violations")

        fake_time = 120.0
        v_subsequent2 = monitor.evaluate("DEV-01", {"irrigation_pressure_bar": 9.5})
        self.assertEqual(v_subsequent2, [], "Sustained breach must not emit duplicate violations")

        # Total active violations remains exactly 1
        self.assertEqual(len(monitor.get_active_violations()), 1)

    def test_missing_or_nonfinite_readings_cannot_count_as_normal_pressure(self):
        """Missing, NaN, Inf, or boolean values cannot clear ongoing breach tracking or reset active violations."""
        fake_time = 200.0
        monitor = SafetyMonitor(clock=lambda: fake_time)

        interlock = SafetyInterlock(
            interlock_id="INT-PRESSURE-HIGH",
            interlock_type=InterlockType.PRESSURE_HIGH,
            description="Over-pressure protection",
            sensor_variable="irrigation_pressure_bar",
            threshold_max=8.0,
            duration_seconds=5,
            action_on_trigger=CommandType.EMERGENCY_STOP,
            requires_manual_reset=True,
        )
        monitor.set_interlocks([interlock])

        # Breach onset at t=200.0
        monitor.evaluate("DEV-01", {"irrigation_pressure_bar": 9.0})

        # At t=202.0, non-finite / missing readings arrive
        fake_time = 202.0
        monitor.evaluate("DEV-01", {})
        monitor.evaluate("DEV-01", {"irrigation_pressure_bar": float("nan")})
        monitor.evaluate("DEV-01", {"irrigation_pressure_bar": float("inf")})
        monitor.evaluate("DEV-01", {"irrigation_pressure_bar": True})

        # At t=206.0, high pressure reading arrives. Breach tracking was NOT wiped out by invalid readings!
        fake_time = 206.0
        v = monitor.evaluate("DEV-01", {"irrigation_pressure_bar": 9.0})
        self.assertEqual(len(v), 1, "Elapsed debounce must be preserved despite missing/non-finite readings")

    def test_auto_reset_interlock_recovers_when_reading_returns_to_normal(self):
        """Auto-resetting interlock (requires_manual_reset=False) clears active violation when reading returns to normal."""
        fake_time = 300.0
        monitor = SafetyMonitor(clock=lambda: fake_time)

        interlock = SafetyInterlock(
            interlock_id="INT-FROST",
            interlock_type=InterlockType.FROST_RISK,
            description="Frost protection",
            sensor_variable="air_temperature_c",
            threshold_min=2.0,
            duration_seconds=10,
            action_on_trigger=CommandType.STOP_ZONE,
            auto_reset=True,
            requires_manual_reset=False,
        )
        monitor.set_interlocks([interlock])

        # Trigger frost violation (temperature -1°C < 2.0°C)
        monitor.evaluate("DEV-01", {"air_temperature_c": -1.0})
        fake_time = 311.0
        v = monitor.evaluate("DEV-01", {"air_temperature_c": -1.0})
        self.assertEqual(len(v), 1)
        self.assertEqual(len(monitor.get_active_violations()), 1)

        # Temperature returns to normal (+15°C) -> Auto-resets
        fake_time = 320.0
        monitor.evaluate("DEV-01", {"air_temperature_c": 15.0})
        self.assertEqual(len(monitor.get_active_violations()), 0, "Active violation must auto-reset on normal temperature")

    def test_idempotent_stop_when_actuator_is_already_online(self):
        """STOP_ZONE on an idle/online actuator succeeds idempotently without error."""
        actuator = MockReconciliationActuator("VALVE-STOP-01")
        stop_cmd = IrrigationCommand(
            command_id="CMD-STOP-IDEM",
            command_type=CommandType.STOP_ZONE,
            device_id=actuator.device_id,
            zone_id="ZONE-1",
            plot_id="PLOT-1",
        )

        res = asyncio.run(actuator.execute_with_safety(stop_cmd))
        self.assertTrue(res.success)
        self.assertEqual(res.error_code, "ALREADY_STOPPED")
        self.assertEqual(actuator.status, ActuatorStatus.ONLINE)


if __name__ == "__main__":
    unittest.main()
