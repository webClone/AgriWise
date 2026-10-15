"""Unit and integration tests for F16: Irrigation safety watchdog and quota enforcement.

Acceptance criteria:
- Zero remaining budget produces zero physical start calls with None, empty, or present telemetry.
- Duration expiration stops a running event without new sensor messages.
- Two reservations cannot jointly exceed the remaining budget.
"""

import asyncio
import time
import unittest
from datetime import datetime, timezone
from typing import Dict, List, Optional

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.dispatcher import CommandDispatcher
from irrigation_runtime.safety import SafetyMonitor, SharedQuotaStore
from irrigation_runtime.schemas import (
    ActuatorCapabilities,
    ActuatorRegistration,
    ActuatorStatus,
    AutomationMode,
    CommandResult,
    CommandType,
    DriverProtocol,
    EventStatus,
    InterlockType,
    IrrigationCommand,
    IrrigationEvent,
    IrrigationSystemType,
    VendorId,
    WaterBudget,
)


class MockActuator(IrrigationActuator):
    """Mock actuator tracking physical calls for safety verification."""

    def __init__(self, registration: ActuatorRegistration):
        super().__init__(registration)
        self.start_calls: List[IrrigationCommand] = []
        self.stop_calls: List[IrrigationCommand] = []
        self.emergency_stop_calls: int = 0
        self._active_command: Optional[IrrigationCommand] = None

    async def connect(self) -> bool:
        self._connected = True
        self._status = ActuatorStatus.ONLINE
        return True

    async def disconnect(self) -> bool:
        self._connected = False
        return True

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        if command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.start_calls.append(command)
            self._active_command = command
            self._status = ActuatorStatus.EXECUTING
        elif command.command_type in (CommandType.STOP_ZONE,):
            self.stop_calls.append(command)
            self._active_command = None
            self._status = ActuatorStatus.ONLINE
        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def get_status(self) -> ActuatorStatus:
        return self._status

    async def emergency_stop(self) -> CommandResult:
        self.emergency_stop_calls += 1
        self._active_command = None
        self._status = ActuatorStatus.ONLINE
        return CommandResult(
            command_id="EMERGENCY-STOP",
            device_id=self.device_id,
            success=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


class MockActuatorRegistry:
    def __init__(self, actuator: IrrigationActuator):
        self._actuator = actuator

    def get_actuator(self, device_id: str) -> Optional[IrrigationActuator]:
        if self._actuator.device_id == device_id:
            return self._actuator
        return None

    async def emergency_stop_all(self):
        await self._actuator.emergency_stop()


class TestIrrigationSafetyF16(unittest.TestCase):
    def setUp(self):
        SharedQuotaStore.reset()
        self.reg = ActuatorRegistration(
            device_id="VALVE-01",
            vendor=VendorId.NETAFIM,
            model="Solenoid-24V",
            protocol=DriverProtocol.MODBUS_TCP,
            farm_id="farm-1",
            plot_id="plot-1",
            zone_ids=["zone-1"],
            capabilities=ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=50.0,
                min_flow_rate_lpm=1.0,
                max_duration_minutes=120.0,
            ),
        )
        self.actuator = MockActuator(self.reg)
        self.actuator._connected = True
        self.actuator._status = ActuatorStatus.ONLINE
        self.registry = MockActuatorRegistry(self.actuator)
        self.safety = SafetyMonitor()
        self.dispatcher = CommandDispatcher(registry=self.registry, safety=self.safety)

    def tearDown(self):
        SharedQuotaStore.reset()

    def _make_event(self, event_id: str = "EVT-01", volume_mm: float = 10.0, duration_min: float = 30.0, effective_area_ha: float = 1.0) -> IrrigationEvent:
        return IrrigationEvent(
            event_id=event_id,
            plot_id="plot-1",
            zone_id="zone-1",
            device_id="VALVE-01",
            system_type=IrrigationSystemType.DRIP,
            target_volume_mm=volume_mm,
            target_duration_minutes=duration_min,
            target_flow_rate_lpm=15.0,
            automation_mode=AutomationMode.SEMI_AUTO,
            status=EventStatus.QUEUED,
            effective_area_ha=effective_area_ha,
        )

    def test_zero_budget_produces_zero_physical_start_calls_across_telemetry_states(self):
        """Zero remaining budget produces zero physical start calls with None, empty, or present telemetry."""
        zero_budget = WaterBudget(
            plot_id="plot-1",
            season="2026-SPRING",
            season_remaining_mm=0.0,
            daily_remaining_mm=0.0,
        )

        telemetry_cases = [
            ("none_telemetry", None),
            ("empty_telemetry", {}),
            ("present_telemetry", {"air_temperature_c": 22.0, "irrigation_pressure_bar": 2.5}),
        ]

        for name, telemetry in telemetry_cases:
            with self.subTest(case=name):
                event = self._make_event(f"EVT-{name}", volume_mm=10.0)
                result_event = asyncio.run(
                    self.dispatcher.submit_event(event, sensor_readings=telemetry, budget=zero_budget)
                )

                self.assertEqual(result_event.status, EventStatus.FAILED)
                self.assertIn("WATER_QUOTA_EXCEEDED", result_event.failure_reason)
                self.assertEqual(len(self.actuator.start_calls), 0, f"Expected 0 start calls for {name}")

    def test_duration_expiration_stops_running_event_without_sensor_messages(self):
        """Duration expiration stops a running event without new sensor messages."""
        budget = WaterBudget(
            plot_id="plot-1",
            season="2026-SPRING",
            season_remaining_mm=100.0,
            daily_remaining_mm=50.0,
        )
        # Event with 10 minute planned duration
        event = self._make_event("EVT-DURATION-TEST", volume_mm=5.0, duration_min=10.0)

        # Submit and begin execution
        submitted = asyncio.run(self.dispatcher.submit_event(event, sensor_readings=None, budget=budget))
        self.assertEqual(submitted.status, EventStatus.EXECUTING)
        self.assertEqual(len(self.actuator.start_calls), 1)

        # Check status immediately without sensor readings - should still be executing
        checked = asyncio.run(self.dispatcher.check_execution_status("EVT-DURATION-TEST", sensor_readings=None))
        self.assertEqual(checked.status, EventStatus.EXECUTING)
        self.assertFalse(checked.emergency_stopped)

        # Simulate monotonic time expiration: fast-forward start_monotonic to 15 minutes ago
        self.safety._active_events["EVT-DURATION-TEST"]["start_monotonic"] -= (15.0 * 60.0)

        # Check execution status with completely empty / None sensor readings
        expired_check = asyncio.run(self.dispatcher.check_execution_status("EVT-DURATION-TEST", sensor_readings=None))

        # Event must be emergency stopped and actuator halted
        self.assertEqual(expired_check.status, EventStatus.EMERGENCY_STOPPED)
        self.assertTrue(expired_check.emergency_stopped)
        self.assertIn("DURATION_EXCEEDED", expired_check.emergency_stop_reason)
        self.assertGreaterEqual(self.actuator.emergency_stop_calls, 1)

    def test_two_reservations_cannot_jointly_exceed_remaining_budget(self):
        """Two reservations cannot jointly exceed the remaining budget."""
        budget = WaterBudget(
            plot_id="plot-1",
            season="2026-SPRING",
            season_remaining_mm=50.0,
            daily_remaining_mm=50.0,
        )

        # First event requests 30mm out of 50mm
        event1 = self._make_event("EVT-RES-1", volume_mm=30.0)
        res1 = asyncio.run(self.dispatcher.submit_event(event1, sensor_readings=None, budget=budget))
        self.assertEqual(res1.status, EventStatus.EXECUTING)

        # Check active reservation
        self.assertEqual(self.safety.get_reserved_quota("plot-1"), 30.0)

        # Second concurrent event also requests 30mm (30 + 30 = 60 > 50)
        event2 = self._make_event("EVT-RES-2", volume_mm=30.0)
        res2 = asyncio.run(self.dispatcher.submit_event(event2, sensor_readings=None, budget=budget))

        # Second event must fail pre-flight check due to concurrent quota reservation
        self.assertEqual(res2.status, EventStatus.FAILED)
        self.assertIn("WATER_QUOTA_EXCEEDED", res2.failure_reason)

        # Actuator should only have received 1 start call from event 1
        self.assertEqual(len(self.actuator.start_calls), 1)
        self.assertEqual(self.actuator.start_calls[0].source_event_id, "EVT-RES-1")

        # Simulate actuator physical completion -> enters VALIDATING
        self.actuator._status = ActuatorStatus.ONLINE
        self.actuator._active_command = None
        asyncio.run(self.dispatcher.check_execution_status("EVT-RES-1"))
        self.assertEqual(event1.status, EventStatus.VALIDATING)

        # Completing event 1 releases its reservation
        asyncio.run(self.dispatcher.complete_event("EVT-RES-1", actual_volume_l=30000.0, actual_duration_minutes=30.0))
        self.assertEqual(self.safety.get_reserved_quota("plot-1"), 0.0)


if __name__ == "__main__":
    unittest.main()
