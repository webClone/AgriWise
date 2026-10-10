"""
Comprehensive verification test suite for Batch A (Physical Command Safety).

Exercises the 7 counterexamples and findings identified in the deep review:
- R06: Numeric parameter validation (rejects NaN, Inf, bool, string, negative)
- R15: Weather and vegetation adapter qualification (rejects bool, NaN, malformed types before coercion)
- R01: Failed stop finalization (unconfirmed stops transition to STOP_REQUESTED, retain tracking and quota)
- R02: Logical operation admission and idempotency (no duplicate START on re-submission or bare ONLINE)
- R03: Conflicting operation rejection with default/empty source_event_id
- R04: Shared durable quota enforcement across independent worker/monitor instances and settlement
- R05: Monotonic watchdog limits and elapsed time deduction on restart
"""

from __future__ import annotations

import asyncio
import math
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.dispatcher import CommandDispatcher
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
    VendorId,
    WaterBudget,
)
from layer3_decision.runner import _execute_canonical_water_engine


class MockFailingStopActuator(IrrigationActuator):
    """Actuator that starts successfully but fails all stop operations."""

    def __init__(self, device_id: str = "VALVE-FAIL-STOP-01"):
        reg = ActuatorRegistration(
            device_id=device_id,
            zone_ids=["ZONE-1"],
            plot_id="PLOT-1",
            farm_id="farm-1",
            protocol=DriverProtocol.MQTT,
            vendor=VendorId.GENERIC,
            model="SimValve-FailStop",
            firmware_version="1.0.0",
            capabilities=ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=100.0,
                min_flow_rate_lpm=1.0,
                max_duration_minutes=120.0,
                supports_operation_reconciliation=False,
            ),
            fail_safe_state=FailSafeState.NORMALLY_CLOSED,
        )
        super().__init__(reg)
        self._connected = True
        self._status = ActuatorStatus.ONLINE
        self.start_calls: List[IrrigationCommand] = []
        self.stop_calls: List[IrrigationCommand] = []
        self.emergency_stop_calls: int = 0

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def get_status(self) -> ActuatorStatus:
        return self._status

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        if command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.start_calls.append(command)
            self._status = ActuatorStatus.EXECUTING
            self._active_command = command
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=True,
                timestamp=datetime.now(timezone.utc).isoformat(),
                actual_flow_rate_lpm=command.flow_rate_lpm,
            )
        elif command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
            self.stop_calls.append(command)
            # Simulated hardware failure: stop rejected/timed out! Valve still spraying!
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_code="VALVE_STUCK_OPEN",
                error_message="Physical solenoid failed to close",
            )
        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=False,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def emergency_stop(self) -> CommandResult:
        self.emergency_stop_calls += 1
        # Explicitly fails emergency stop
        return CommandResult(
            command_id="ESTOP-FAIL",
            device_id=self.device_id,
            success=False,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error_code="ESTOP_FAILED",
            error_message="Emergency stop contactor open circuit",
        )


class MockSimpleActuator(IrrigationActuator):
    """Standard mock actuator tracking all command dispatches."""

    def __init__(self, device_id: str = "VALVE-STD-01", supports_reconciliation: bool = False):
        reg = ActuatorRegistration(
            device_id=device_id,
            zone_ids=["ZONE-1"],
            plot_id="PLOT-1",
            farm_id="farm-1",
            protocol=DriverProtocol.MODBUS_TCP,
            vendor=VendorId.GENERIC,
            model="SimValve-Standard",
            firmware_version="1.0.0",
            capabilities=ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=100.0,
                min_flow_rate_lpm=1.0,
                max_duration_minutes=120.0,
                supports_operation_reconciliation=supports_reconciliation,
            ),
            fail_safe_state=FailSafeState.NORMALLY_CLOSED,
        )
        super().__init__(reg)
        self._connected = True
        self._status = ActuatorStatus.ONLINE
        self.sent_commands: List[IrrigationCommand] = []

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def get_status(self) -> ActuatorStatus:
        return self._status

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        self.sent_commands.append(command)
        if command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self._status = ActuatorStatus.EXECUTING
            self._active_command = command
        elif command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
            self._status = ActuatorStatus.ONLINE
            self._active_command = None
        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
            actual_flow_rate_lpm=command.flow_rate_lpm,
        )

    async def emergency_stop(self) -> CommandResult:
        self._status = ActuatorStatus.ONLINE
        self._active_command = None
        return CommandResult(
            command_id="ESTOP-OK",
            device_id=self.device_id,
            success=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


class MockRegistry:
    def __init__(self, actuator: IrrigationActuator):
        self._actuators = {actuator.device_id: actuator}

    def get_actuator(self, device_id: str) -> Optional[IrrigationActuator]:
        return self._actuators.get(device_id)

    async def emergency_stop_all(self):
        for act in self._actuators.values():
            await act.emergency_stop()


class TestBatchAPhysicalCommandSafety(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    # ------------------------------------------------------------------------
    # R06: Numeric parameter admission
    # ------------------------------------------------------------------------
    def test_r06_nonfinite_and_boolean_command_parameters_rejected(self):
        """IrrigationCommand.validate() must reject NaN, Inf, bool, string, and negative numbers."""
        invalid_cases = [
            ("nan_volume", {"volume_mm": float("nan")}),
            ("inf_volume", {"volume_mm": float("inf")}),
            ("bool_volume", {"volume_mm": True}),
            ("string_volume", {"volume_mm": "10.0"}),
            ("negative_volume", {"volume_mm": -5.0}),
            ("nan_duration", {"duration_minutes": float("nan")}),
            ("zero_duration_start", {"duration_minutes": 0.0}),
            ("negative_duration", {"duration_minutes": -10.0}),
            ("bool_duration", {"duration_minutes": True}),
            ("nan_flow_rate", {"flow_rate_lpm": float("nan")}),
            ("negative_flow_rate", {"flow_rate_lpm": -2.0}),
            ("nan_pivot_speed", {"pivot_speed_pct": float("nan")}),
            ("excess_pivot_speed", {"pivot_speed_pct": 120.0}),
            ("negative_pivot_speed", {"pivot_speed_pct": -1.0}),
        ]

        for case_name, override_kwargs in invalid_cases:
            with self.subTest(case=case_name):
                kwargs = {
                    "command_id": f"CMD-{case_name}",
                    "command_type": CommandType.START_ZONE,
                    "device_id": "VALVE-01",
                    "zone_id": "Z1",
                    "plot_id": "P1",
                    "volume_mm": 10.0,
                    "duration_minutes": 30.0,
                    "flow_rate_lpm": 15.0,
                    "pressure_bar": 2.5,
                }
                kwargs.update(override_kwargs)
                cmd = IrrigationCommand(**kwargs)
                errors = cmd.validate()
                self.assertGreater(len(errors), 0, f"Case {case_name} should have validation errors, got none")

    def test_r06_valid_zero_and_positive_command_parameters_accepted(self):
        """IrrigationCommand.validate() accepts valid positive numbers and valid zeros."""
        cmd = IrrigationCommand(
            command_id="CMD-VALID-01",
            command_type=CommandType.START_ZONE,
            device_id="VALVE-01",
            zone_id="Z1",
            plot_id="P1",
            volume_mm=10.0,
            duration_minutes=30.0,
            flow_rate_lpm=15.0,
            pressure_bar=2.0,
            pivot_speed_pct=50.0,
        )
        self.assertEqual(cmd.validate(), [])

        # STOP command with 0 volume and 0 duration is valid
        stop_cmd = IrrigationCommand(
            command_id="CMD-STOP-01",
            command_type=CommandType.STOP_ZONE,
            device_id="VALVE-01",
            zone_id="Z1",
            plot_id="P1",
            volume_mm=0.0,
            duration_minutes=0.0,
        )
        self.assertEqual(stop_cmd.validate(), [])

    # ------------------------------------------------------------------------
    # R15 & R13: Weather and vegetation adapter qualification
    # ------------------------------------------------------------------------
    def test_r15_weather_adapter_rejects_boolean_and_preserves_missingness(self):
        """_execute_canonical_water_engine rejects weather records with bool precipitation (e.g. True)."""
        bad_weather = [
            {
                "date": "2026-05-01",
                "t_max_c": 25.0,
                "t_min_c": 12.0,
                "precipitation_mm": True,  # Boolean must NOT be coerced to 1.0 mm!
                "wind_speed_2m_m_s": 2.0,
                "rh_min_pct": 30.0,
                "rh_max_pct": 70.0,
                "net_radiation_mj_m2": 15.0,
            }
        ]
        class DummyInputs:
            weather_daily = bad_weather
            soil_observations_daily = {}
            target_date = "2026-05-01"
            crop_context = None

        state, feedback = _execute_canonical_water_engine(
            plot_id="PLOT-TEST-BOOL",
            inputs=DummyInputs(),
            op_ctx={},
        )
        # Because precipitation was True (not a finite real), it is rejected as incomplete weather
        self.assertIsNone(state, "Boolean precipitation must be rejected, returning None")
        self.assertIsNone(feedback)

    def test_r13_runner_malformed_l2_does_not_raise_unbound_local(self):
        """Malformed L2 output does not trigger UnboundLocalError for ConcurrencyConflictError."""
        good_weather = [
            {
                "date": "2026-05-01",
                "t_max_c": 25.0,
                "t_min_c": 12.0,
                "precipitation_mm": 0.0,
                "wind_speed_2m_m_s": 2.0,
                "rh_min_pct": 30.0,
                "rh_max_pct": 70.0,
                "net_radiation_mj_m2": 15.0,
            }
        ]
        class BadL2Output:
            lai_mean = "bad_string_value"

        class DummyInputs:
            weather_daily = good_weather
            soil_observations_daily = {}
            target_date = "2026-05-01"
            crop_context = None

        # Should execute cleanly without UnboundLocalError
        state, feedback = _execute_canonical_water_engine(
            plot_id="PLOT-TEST-L2",
            inputs=DummyInputs(),
            op_ctx={},
            l2_output=BadL2Output(),
        )
        # Successfully processed without crashing or throwing UnboundLocalError
        # (It falls back to default LAI 1.5 safely)

    # ------------------------------------------------------------------------
    # R01: Failed stop finalization
    # ------------------------------------------------------------------------
    async def test_r01_failed_emergency_stop_transitions_to_stop_requested_and_retains_tracking(self):
        """When emergency stop fails, event transitions to STOP_REQUESTED, retaining active tracking and quota."""
        actuator = MockFailingStopActuator("VALVE-FAIL-STOP-01")
        registry = MockRegistry(actuator)
        safety = SafetyMonitor()
        dispatcher = CommandDispatcher(registry=registry, safety=safety)

        budget = WaterBudget(plot_id="PLOT-1", season="2026", season_remaining_mm=50.0, daily_remaining_mm=50.0)

        event = IrrigationEvent(
            event_id="EVT-FAIL-STOP-01",
            plot_id="PLOT-1",
            zone_id="ZONE-1",
            device_id="VALVE-FAIL-STOP-01",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=10.0,
            target_duration_minutes=10.0,
            target_flow_rate_lpm=15.0,
        )

        submitted = await dispatcher.submit_event(event, budget=budget)
        self.assertEqual(submitted.status, EventStatus.EXECUTING)
        self.assertEqual(safety.get_reserved_quota("PLOT-1"), 10.0)

        # Simulate duration timeout: fast-forward monotonic clock
        safety._active_events["EVT-FAIL-STOP-01"]["start_monotonic"] -= 15 * 60.0

        # Trigger check_execution_status
        checked = await dispatcher.check_execution_status("EVT-FAIL-STOP-01")

        # R01 Core: Because stop failed, status MUST NOT be EMERGENCY_STOPPED!
        self.assertEqual(checked.status, EventStatus.STOP_REQUESTED)
        self.assertTrue(checked.emergency_stopped)

        # Quota MUST NOT be released while stop is unconfirmed!
        self.assertEqual(safety.get_reserved_quota("PLOT-1"), 10.0)

        # Active tracking MUST NOT be cleared while stop is unconfirmed!
        active_events = dispatcher.get_active_events()
        self.assertEqual(len(active_events), 1)
        self.assertEqual(active_events[0].event_id, "EVT-FAIL-STOP-01")

        # Actuator status must be ERROR and retain active command
        self.assertEqual(actuator.status, ActuatorStatus.ERROR)
        self.assertIsNotNone(actuator.active_command)

    async def test_r01_failed_cancellation_transitions_to_stop_requested_and_retains_quota(self):
        """When cancellation stop fails, event transitions to STOP_REQUESTED, retaining quota and tracking."""
        actuator = MockFailingStopActuator("VALVE-FAIL-STOP-02")
        registry = MockRegistry(actuator)
        safety = SafetyMonitor()
        dispatcher = CommandDispatcher(registry=registry, safety=safety)

        budget = WaterBudget(plot_id="PLOT-1", season="2026", season_remaining_mm=50.0, daily_remaining_mm=50.0)
        event = IrrigationEvent(
            event_id="EVT-CANCEL-FAIL-01",
            plot_id="PLOT-1",
            zone_id="ZONE-1",
            device_id="VALVE-FAIL-STOP-02",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=12.0,
            target_duration_minutes=20.0,
            target_flow_rate_lpm=15.0,
        )

        await dispatcher.submit_event(event, budget=budget)
        self.assertEqual(safety.get_reserved_quota("PLOT-1"), 12.0)

        cancelled = await dispatcher.cancel_event("EVT-CANCEL-FAIL-01", reason="Operator cancel")
        self.assertEqual(cancelled.status, EventStatus.STOP_REQUESTED)
        self.assertEqual(safety.get_reserved_quota("PLOT-1"), 12.0)
        self.assertEqual(len(dispatcher.get_active_events()), 1)

    # ------------------------------------------------------------------------
    # R02 & R03: Logical operation admission and mutex
    # ------------------------------------------------------------------------
    async def test_r02_re_submitting_active_event_does_not_duplicate_physical_start(self):
        """Re-submitting an active or queued event returns the active event idempotently without duplicate START."""
        actuator = MockSimpleActuator("VALVE-IDEMP-01")
        registry = MockRegistry(actuator)
        safety = SafetyMonitor()
        dispatcher = CommandDispatcher(registry=registry, safety=safety)

        event1 = IrrigationEvent(
            event_id="EVT-SAME-01",
            plot_id="PLOT-1",
            zone_id="ZONE-1",
            device_id="VALVE-IDEMP-01",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=8.0,
            target_duration_minutes=15.0,
            target_flow_rate_lpm=15.0,
        )
        res1 = await dispatcher.submit_event(event1)
        self.assertEqual(res1.status, EventStatus.EXECUTING)
        self.assertEqual(len(actuator.sent_commands), 1)

        # Second submission of an event with the exact same event_id
        event2 = IrrigationEvent(
            event_id="EVT-SAME-01",
            plot_id="PLOT-1",
            zone_id="ZONE-1",
            device_id="VALVE-IDEMP-01",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=8.0,
            target_duration_minutes=15.0,
            target_flow_rate_lpm=15.0,
        )
        res2 = await dispatcher.submit_event(event2)
        self.assertEqual(res2.status, EventStatus.EXECUTING)
        # MUST NOT send a second physical START command!
        self.assertEqual(len(actuator.sent_commands), 1)

    async def test_r03_empty_source_event_ids_do_not_defeat_conflict_rejection(self):
        """Two commands with default empty source_event_id and different operation_id are rejected, not permitted as retry."""
        actuator = MockSimpleActuator("VALVE-CONFLICT-01")

        cmd_a = IrrigationCommand(
            command_id="CMD-A",
            command_type=CommandType.START_ZONE,
            device_id="VALVE-CONFLICT-01",
            zone_id="Z1",
            plot_id="P1",
            operation_id="operation-A",
            source_event_id="",  # Default empty!
            volume_mm=5.0,
            duration_minutes=10.0,
            flow_rate_lpm=15.0,
        )
        res_a = await actuator.execute_with_safety(cmd_a)
        self.assertTrue(res_a.success)
        self.assertEqual(actuator.status, ActuatorStatus.EXECUTING)
        self.assertEqual(len(actuator.sent_commands), 1)

        # Incoming command B with different operation_id and default empty source_event_id
        cmd_b = IrrigationCommand(
            command_id="CMD-B",
            command_type=CommandType.START_ZONE,
            device_id="VALVE-CONFLICT-01",
            zone_id="Z1",
            plot_id="P1",
            operation_id="operation-B",
            source_event_id="",  # Default empty!
            volume_mm=5.0,
            duration_minutes=10.0,
            flow_rate_lpm=15.0,
        )
        res_b = await actuator.execute_with_safety(cmd_b)

        # R03 Core: Must be REJECTED!
        self.assertFalse(res_b.success)
        self.assertEqual(res_b.error_code, "VALIDATION_FAILED")
        self.assertIn("already EXECUTING", res_b.error_message)
        # Exactly 1 physical START dispatch, not 2!
        self.assertEqual(len(actuator.sent_commands), 1)

    async def test_r02_unreconciled_bare_online_after_ack_timeout_does_not_blindly_retry(self):
        """Driver lacking operation reconciliation reporting bare ONLINE after ACK timeout retains uncertainty without retry."""
        class MockAckTimeoutNoReconActuator(IrrigationActuator):
            def __init__(self):
                reg = ActuatorRegistration(
                    device_id="VALVE-NO-RECON-01",
                    zone_ids=["Z1"],
                    plot_id="P1",
                    farm_id="F1",
                    protocol=DriverProtocol.MQTT,
                    vendor=VendorId.GENERIC,
                    model="M",
                    capabilities=ActuatorCapabilities(
                        system_type=IrrigationSystemType.DRIP,
                        max_flow_rate_lpm=100.0,
                        min_flow_rate_lpm=1.0,
                        max_duration_minutes=120.0,
                        supports_operation_reconciliation=False,  # Does NOT support operation query!
                    ),
                    fail_safe_state=FailSafeState.NORMALLY_CLOSED,
                )
                super().__init__(reg)
                self._connected = True
                self._status = ActuatorStatus.ONLINE
                self.sent_count = 0

            async def connect(self): return True
            async def disconnect(self): pass
            async def get_status(self): return ActuatorStatus.ONLINE  # Bare ONLINE/idle

            async def send_command(self, cmd):
                self.sent_count += 1
                # Simulates ACK timeout
                return CommandResult(
                    command_id=cmd.command_id,
                    device_id=self.device_id,
                    success=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="ACK_TIMEOUT",
                )

            async def emergency_stop(self):
                return CommandResult(command_id="S", device_id=self.device_id, success=True, timestamp="")

        actuator = MockAckTimeoutNoReconActuator()
        registry = MockRegistry(actuator)
        safety = SafetyMonitor()
        dispatcher = CommandDispatcher(registry=registry, safety=safety, max_retries=2, retry_base_delay=0.01)

        event = IrrigationEvent(
            event_id="EVT-NO-RECON-01",
            plot_id="P1",
            zone_id="Z1",
            device_id="VALVE-NO-RECON-01",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=10.0,
            target_duration_minutes=15.0,
            target_flow_rate_lpm=15.0,
        )

        res = await dispatcher.submit_event(event)
        # BA-01: Retains STOP_REQUESTED ownership and tracking under uncertain outcome
        self.assertEqual(res.status, EventStatus.STOP_REQUESTED)
        self.assertIn("EVT-NO-RECON-01", dispatcher._active_events)
        # R02: Because the driver could not confirm whether the dose occurred, it did NOT send a second dose!
        self.assertEqual(actuator.sent_count, 1)

    # ------------------------------------------------------------------------
    # R04: Shared durable quota enforcement across independent instances
    # ------------------------------------------------------------------------
    async def test_r04_independent_workers_share_quota_and_prevent_over_reservation(self):
        """Two independent CommandDispatcher / SafetyMonitor instances share reservation store and reject joint excess."""
        actuator1 = MockSimpleActuator("VALVE-W1")
        reg1 = MockRegistry(actuator1)
        safety1 = SafetyMonitor()
        dispatcher1 = CommandDispatcher(registry=reg1, safety=safety1)

        actuator2 = MockSimpleActuator("VALVE-W2")
        reg2 = MockRegistry(actuator2)
        safety2 = SafetyMonitor()
        dispatcher2 = CommandDispatcher(registry=reg2, safety=safety2)

        budget = WaterBudget(
            plot_id="PLOT-SHARED-01",
            season="2026",
            season_remaining_mm=10.0,
            daily_remaining_mm=10.0,
        )

        # Worker 1 requests 8.0 mm out of 10.0 mm
        event1 = IrrigationEvent(
            event_id="EVT-W1-01",
            plot_id="PLOT-SHARED-01",
            zone_id="Z1",
            device_id="VALVE-W1",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=8.0,
            target_duration_minutes=20.0,
            target_flow_rate_lpm=15.0,
        )
        res1 = await dispatcher1.submit_event(event1, budget=budget)
        self.assertEqual(res1.status, EventStatus.EXECUTING)

        # Worker 2 independently requests 8.0 mm for the same plot against the same 10.0 mm budget
        event2 = IrrigationEvent(
            event_id="EVT-W2-01",
            plot_id="PLOT-SHARED-01",
            zone_id="Z2",
            device_id="VALVE-W2",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=8.0,
            target_duration_minutes=20.0,
            target_flow_rate_lpm=15.0,
        )
        res2 = await dispatcher2.submit_event(event2, budget=budget)

        # R04 Core: Worker 2 MUST fail due to concurrent shared reservation (8 + 8 = 16 > 10)
        self.assertEqual(res2.status, EventStatus.FAILED)
        self.assertIn("WATER_QUOTA_EXCEEDED", res2.failure_reason)
        self.assertEqual(len(actuator2.sent_commands), 0)

    async def test_r04_settled_delivery_debits_cumulative_budget_and_blocks_second_event(self):
        """Completed event settles delivery; subsequent event against un-debited budget is rejected."""
        actuator = MockSimpleActuator("VALVE-SETTLE-01")
        reg = MockRegistry(actuator)
        safety = SafetyMonitor()
        dispatcher = CommandDispatcher(registry=reg, safety=safety)

        budget = WaterBudget(
            plot_id="PLOT-SETTLE-01",
            season="2026",
            season_remaining_mm=10.0,
            daily_remaining_mm=10.0,
        )

        event1 = IrrigationEvent(
            event_id="EVT-SETTLE-01",
            plot_id="PLOT-SETTLE-01",
            zone_id="Z1",
            device_id="VALVE-SETTLE-01",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=8.0,
            target_duration_minutes=15.0,
            target_flow_rate_lpm=15.0,
        )
        await dispatcher.submit_event(event1, budget=budget)

        # Simulate actuator physical completion -> enters VALIDATING
        actuator._status = ActuatorStatus.ONLINE
        actuator._active_command = None
        await dispatcher.check_execution_status("EVT-SETTLE-01")
        self.assertEqual(event1.status, EventStatus.VALIDATING)

        # Complete event 1
        await dispatcher.complete_event("EVT-SETTLE-01", actual_volume_l=8000.0, actual_duration_minutes=15.0)

        # Reservation is released
        self.assertEqual(safety.get_reserved_quota("PLOT-SETTLE-01"), 0.0)

        # Caller presents un-debited budget (reporting 10.0 mm remaining).
        # Event 2 requests 8.0 mm.
        event2 = IrrigationEvent(
            event_id="EVT-SETTLE-02",
            plot_id="PLOT-SETTLE-01",
            zone_id="Z1",
            device_id="VALVE-SETTLE-01",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=8.0,
            target_duration_minutes=15.0,
            target_flow_rate_lpm=15.0,
        )
        res2 = await dispatcher.submit_event(event2, budget=budget)

        # R04 Core: Must be rejected because 8.0 mm has already been settled on this plot!
        self.assertEqual(res2.status, EventStatus.FAILED)
        self.assertIn("WATER_QUOTA_EXCEEDED", res2.failure_reason)

    # ------------------------------------------------------------------------
    # R05: Restart deadline recovery and monotonic limits
    # ------------------------------------------------------------------------
    async def test_r05_restart_deducts_elapsed_time_and_does_not_grant_fresh_allowance(self):
        """Restarting an event with 9 minutes elapsed of a 10-minute limit deducts elapsed time and stops on time."""
        actuator = MockSimpleActuator("VALVE-RESTART-01")
        reg = MockRegistry(actuator)
        safety = SafetyMonitor()
        dispatcher = CommandDispatcher(registry=reg, safety=safety)

        # Event was started 9 minutes ago with a 10 minute planned duration
        start_time_iso = (datetime.now(timezone.utc) - timedelta(minutes=9)).isoformat()
        event = IrrigationEvent(
            event_id="EVT-RESTART-01",
            plot_id="PLOT-1",
            zone_id="Z1",
            device_id="VALVE-RESTART-01",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.EXECUTING,
            target_volume_mm=5.0,
            target_duration_minutes=10.0,
            actual_start=start_time_iso,
        )
        actuator._status = ActuatorStatus.EXECUTING

        reconciled = await dispatcher.reconcile_on_restart([event])
        self.assertEqual(len(reconciled), 1)
        self.assertEqual(reconciled[0].status, EventStatus.EXECUTING)

        # Check safety tracking: elapsed time was deducted (start_monotonic is set 9 minutes in the past)
        tracking_info = safety._active_events["EVT-RESTART-01"]
        elapsed_seconds = safety._clock() - tracking_info["start_monotonic"]
        self.assertAlmostEqual(elapsed_seconds, 9.0 * 60.0, delta=5.0)

        # Advance clock by 2 minutes (total 11 minutes > 10 minute limit)
        safety._active_events["EVT-RESTART-01"]["start_monotonic"] -= (2.0 * 60.0)

        # Explicit poll triggers watchdog stop
        checked = await dispatcher.check_execution_status("EVT-RESTART-01")
        self.assertEqual(checked.status, EventStatus.EMERGENCY_STOPPED)
        self.assertTrue(checked.emergency_stopped)
        self.assertIn("DURATION_EXCEEDED", checked.emergency_stop_reason)


if __name__ == "__main__":
    unittest.main()
