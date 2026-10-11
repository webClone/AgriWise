"""Regression and contract verification tests for BV01 through BV06 defect groups.

Verifies:
- BV01: Operation fencing: Per-operation STOP eligibility is preserved across restart, polling, and retry;
        live operations running on the same actuator are never stopped by old/different operations.
- BV02: Unknown controller state: Positive, current idle confirmation is required for completion;
        query failure, OFFLINE, or missing registry keeps event in VALIDATING with ownership.
- BV03: Area validation: Explicitly supplied non-positive or non-numeric effective_area_ha is rejected across all writers.
- BV04: Immutable payload/support: Admitted volume, envelope, and missing support cannot be mutated across restart or settlement.
- BV05: Failed ACK persistence: Missing durable start falls back conservatively to admission timestamp; caller timestamp cannot renew allowance.
- BV06: Terminal measurements: Stale restart snapshots of settled events hydrate actual volume, duration, and delivered depth from receipt.
"""

import asyncio
import copy
import math
import unittest
from datetime import datetime, timezone, timedelta
from typing import Optional

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.dispatcher import CommandDispatcher
from irrigation_runtime.safety import SafetyMonitor, SharedQuotaStore, WaterBudget
from irrigation_runtime.schemas import (
    ActuatorCapabilities,
    ActuatorRegistration,
    ActuatorStatus,
    AutomationMode,
    CommandResult,
    CommandType,
    DriverProtocol,
    IrrigationCommand,
    IrrigationEvent,
    EventStatus,
    IrrigationSystemType,
    VendorId,
)


class MockDriver(IrrigationActuator):
    def __init__(self, device: str = "device", running: bool = False):
        super().__init__(
            ActuatorRegistration(
                device,
                VendorId.CUSTOM,
                "offline",
                DriverProtocol.MQTT,
                capabilities=ActuatorCapabilities(IrrigationSystemType.DRIP),
            )
        )
        self._status = ActuatorStatus.ONLINE
        self.running = running
        self.stops = 0
        self.deliveries = 0
        self.reported_status: Optional[ActuatorStatus] = None
        self.fail_query = False

    async def connect(self) -> bool:
        self._status = ActuatorStatus.ONLINE
        return True

    async def disconnect(self) -> None:
        pass

    async def send_command(self, cmd: IrrigationCommand) -> CommandResult:
        if cmd.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.deliveries += 1
            self.running = True
            self._status = ActuatorStatus.EXECUTING
            self.set_active_command(cmd)
            return CommandResult(
                cmd.command_id,
                self.device_id,
                True,
                datetime.now(timezone.utc).isoformat(),
            )
        self.stops += 1
        self.running = False
        self._status = ActuatorStatus.ONLINE
        self._active_command = None
        return CommandResult(
            cmd.command_id,
            self.device_id,
            True,
            datetime.now(timezone.utc).isoformat(),
        )

    async def get_status(self) -> ActuatorStatus:
        if self.fail_query:
            raise OSError("simulated controller query unavailable")
        if self.reported_status is not None:
            return self.reported_status
        self._status = ActuatorStatus.EXECUTING if self.running else ActuatorStatus.ONLINE
        return self._status

    async def emergency_stop(self) -> CommandResult:
        self.stops += 1
        self.running = False
        self._status = ActuatorStatus.ONLINE
        self._active_command = None
        return CommandResult(
            "stop_cmd",
            self.device_id,
            True,
            datetime.now(timezone.utc).isoformat(),
        )


class MockRegistry:
    def __init__(self, actuator: IrrigationActuator):
        self._actuator = actuator

    def get_actuator(self, device_id: str) -> Optional[IrrigationActuator]:
        if self._actuator and self._actuator.device_id == device_id:
            return self._actuator
        return None

    def list_actuators(self):
        return [self._actuator] if self._actuator else []

    async def emergency_stop_all(self):
        if self._actuator:
            await self._actuator.emergency_stop()


def _make_event(
    event_id: str,
    device_id: str = "mock_device",
    volume: float = 8.0,
    duration: float = 10.0,
    plot: str = "plot_1",
) -> IrrigationEvent:
    return IrrigationEvent(
        event_id,
        plot,
        "zone_1",
        device_id,
        IrrigationSystemType.DRIP,
        AutomationMode.FULL_AUTO,
        status=EventStatus.QUEUED,
        target_volume_mm=volume,
        target_duration_minutes=duration,
        target_flow_rate_lpm=10.0,
    )


def _make_budget(daily: float = 50.0, season: float = 500.0) -> WaterBudget:
    return WaterBudget(
        plot_id="plot_1",
        season="default_season",
        daily_quota_mm=daily,
        daily_remaining_mm=daily,
        season_quota_mm=season,
        season_remaining_mm=season,
    )


class TestBV01ThroughBV06Contracts(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    async def test_bv01_operation_identity_fencing_protects_other_live_event(self):
        """BV01: Polling and restart for old/stale event never issues emergency stop against different live operation."""
        driver = MockDriver("device")
        monitor = SafetyMonitor()
        disp = CommandDispatcher(registry=MockRegistry(driver), safety=monitor)

        old_ev = _make_event("OLD", "device", volume=1.0, duration=10.0)
        await disp.submit_event(old_ev, budget=_make_budget())

        # OLD ends on controller; NEW admitted on the same device
        driver.running = False
        await driver.get_status()
        new_ev = _make_event("NEW", "device", volume=1.0, duration=20.0)
        await disp.submit_event(new_ev, budget=_make_budget())
        self.assertTrue(driver.running)
        self.assertEqual(driver.active_command.source_event_id, "NEW")
        stops_before = driver.stops

        # Fresh worker restores OLD while NEW is active
        snapshot = copy.deepcopy(old_ev)
        fresh_disp = CommandDispatcher(registry=MockRegistry(driver), safety=monitor)
        await fresh_disp.reconcile_on_restart([snapshot])

        self.assertEqual(driver.stops, stops_before)
        self.assertTrue(driver.running)

        # Polling OLD does not stop NEW
        await fresh_disp.check_execution_status("OLD", {})
        self.assertEqual(driver.stops, stops_before)
        self.assertTrue(driver.running)
        self.assertEqual(driver.active_command.source_event_id, "NEW")

    async def test_bv02_unknown_controller_status_prevents_completion(self):
        """BV02: Query failure, OFFLINE, or missing registry prevents premature completion and retains VALIDATING ownership."""
        driver = MockDriver("device")
        monitor = SafetyMonitor()
        disp = CommandDispatcher(registry=MockRegistry(driver), safety=monitor)

        ev = _make_event("E", "device", volume=8.0, duration=10.0)
        ev.effective_area_ha = 1.0
        await disp.submit_event(ev, budget=_make_budget())
        driver.running = False
        await disp.check_execution_status("E", {})
        self.assertEqual(ev.status, EventStatus.VALIDATING)

        # 1. Query failure
        driver.fail_query = True
        done = await disp.complete_event("E", actual_volume_l=40000.0, actual_duration_minutes=6.0)
        self.assertEqual(done.status, EventStatus.VALIDATING)
        self.assertEqual(SharedQuotaStore.get_reserved("plot_1"), 8.0)
        self.assertEqual(SharedQuotaStore.get_settled("plot_1"), 0.0)

        # 2. OFFLINE status
        driver.fail_query = False
        driver.reported_status = ActuatorStatus.OFFLINE
        done = await disp.complete_event("E", actual_volume_l=40000.0, actual_duration_minutes=6.0)
        self.assertEqual(done.status, EventStatus.VALIDATING)

        # 3. Missing registry
        disp_no_reg = CommandDispatcher(registry=MockRegistry(None), safety=monitor)
        disp_no_reg._active_events["E"] = ev
        done = await disp_no_reg.complete_event("E", actual_volume_l=40000.0, actual_duration_minutes=6.0)
        self.assertEqual(done.status, EventStatus.VALIDATING)

        # 4. Healthy idle completes
        driver.reported_status = None
        driver.running = False
        done = await disp.complete_event("E", actual_volume_l=40000.0, actual_duration_minutes=6.0)
        self.assertEqual(done.status, EventStatus.COMPLETED)
        self.assertEqual(SharedQuotaStore.get_settled("plot_1"), 4.0)

    def test_bv03_area_validation_rejects_invalid_scalars(self):
        """BV03: Non-positive, non-numeric, or boolean effective_area_ha raises ValueError across all writers."""
        invalid_areas = [-1, 0, True, "1", float("nan"), float("inf")]
        for area in invalid_areas:
            with self.assertRaises(ValueError):
                SharedQuotaStore.reserve("B1", "plot_1", 1.0, duration_minutes=5, flow_rate_lpm=10, effective_area_ha=area)
            with self.assertRaises(ValueError):
                SharedQuotaStore.reopen_active("B2", "plot_1", 1.0, duration_minutes=5, flow_rate_lpm=10, effective_area_ha=area)
            with self.assertRaises(ValueError):
                SharedQuotaStore.atomic_check_and_reserve("plot_1", 1.0, event_id="B3", duration_minutes=5, flow_rate_lpm=10, effective_area_ha=area)

        # Valid area and omitted area are accepted
        SharedQuotaStore.reserve("SAFE1", "plot_1", 1.0, duration_minutes=5, flow_rate_lpm=10, effective_area_ha=1.0)
        SharedQuotaStore.reserve("SAFE2", "plot_1", 1.0, duration_minutes=5, flow_rate_lpm=10, effective_area_ha=None)
        state = SharedQuotaStore._read_state()
        self.assertEqual(state["reservations"]["SAFE1"]["effective_area_ha"], 1.0)
        self.assertIsNone(state["reservations"]["SAFE2"]["effective_area_ha"])

    async def test_bv04_immutable_admitted_envelope_and_support(self):
        """BV04: Admitted volume and missing support cannot be mutated across restart or settlement."""
        driver = MockDriver("device")
        monitor = SafetyMonitor()
        disp = CommandDispatcher(registry=MockRegistry(driver), safety=monitor)

        # 1. Missing support remains missing across restart; cannot certify depth
        ev_no_area = _make_event("E_NO_AREA", "device", volume=8.0, duration=10.0)
        ev_no_area.effective_area_ha = None
        await disp.submit_event(ev_no_area, budget=_make_budget())

        snap_with_area = copy.deepcopy(ev_no_area)
        snap_with_area.effective_area_ha = 1.0
        fresh_disp = CommandDispatcher(registry=MockRegistry(driver), safety=monitor)
        await fresh_disp.reconcile_on_restart([snap_with_area])
        self.assertIsNone(snap_with_area.effective_area_ha)

        driver.running = False
        await fresh_disp.check_execution_status("E_NO_AREA", {})
        done = await fresh_disp.complete_event("E_NO_AREA", actual_volume_l=40000.0, actual_duration_minutes=6.0)
        self.assertEqual(done.status, EventStatus.VALIDATING)
        self.assertIsNone(SharedQuotaStore.get_settled_receipt("E_NO_AREA"))

        # 2. Immutable volume prevents quota bypass
        SharedQuotaStore.reset()
        driver2 = MockDriver("device")
        monitor2 = SafetyMonitor()
        disp2 = CommandDispatcher(registry=MockRegistry(driver2), safety=monitor2)
        ev1 = _make_event("FIRST", "device", volume=8.0, duration=10.0)
        ev1.effective_area_ha = 1.0
        await disp2.submit_event(ev1, budget=_make_budget(daily=10.0))
        SharedQuotaStore.reserve("FIRST", "plot_1", volume_mm=1.0, duration_minutes=20, flow_rate_lpm=3, effective_area_ha=2.0)
        self.assertEqual(SharedQuotaStore.get_reserved("plot_1"), 8.0)

        ev2 = _make_event("SECOND", "device", volume=8.0, duration=10.0)
        ev2.effective_area_ha = 1.0
        res2 = await disp2.submit_event(ev2, budget=_make_budget(daily=10.0))
        self.assertEqual(res2.status, EventStatus.FAILED)

    async def test_bv05_failed_ack_persistence_conservatively_expires(self):
        """BV05: When ACK persistence fails, restart conservatively expires based on admission timestamp rather than fresh caller timing."""
        driver = MockDriver("device")
        monitor = SafetyMonitor()
        disp = CommandDispatcher(registry=MockRegistry(driver), safety=monitor)

        ev = _make_event("E_EXP", "device", volume=8.0, duration=10.0)
        SharedQuotaStore.atomic_check_and_reserve("plot_1", 8.0, event_id="E_EXP", device_id="device")
        # Simulate admission 11 minutes ago with no actual_start
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
        with SharedQuotaStore._lock():
            st = SharedQuotaStore._read_state()
            st["reservations"]["E_EXP"]["first_dispatched_at"] = old_time
            st["reservations"]["E_EXP"]["timestamp"] = old_time
            SharedQuotaStore._write_state(st)

        driver.running = True
        driver._status = ActuatorStatus.EXECUTING
        caller_ev = copy.deepcopy(ev)
        caller_ev.actual_start = datetime.now(timezone.utc).isoformat()

        fresh_disp = CommandDispatcher(registry=MockRegistry(driver), safety=monitor)
        await fresh_disp.reconcile_on_restart([caller_ev])

        self.assertEqual(caller_ev.status, EventStatus.EMERGENCY_STOPPED)
        self.assertFalse(driver.running)
        self.assertEqual(driver.stops, 1)

    async def test_bv06_terminal_recovery_hydrates_measurements(self):
        """BV06: Restored snapshot of completed operation hydrates actual volume, duration, and delivered depth."""
        driver = MockDriver("device")
        monitor = SafetyMonitor()
        disp = CommandDispatcher(registry=MockRegistry(driver), safety=monitor)

        ev = _make_event("E_TERM", "device", volume=8.0, duration=10.0)
        ev.effective_area_ha = 1.0
        await disp.submit_event(ev, budget=_make_budget())
        snapshot = copy.deepcopy(ev)

        driver.running = False
        await disp.check_execution_status("E_TERM", {})
        await disp.complete_event("E_TERM", actual_volume_l=40000.0, actual_duration_minutes=6.0)

        # Snapshot before completion has 0.0 defaults
        self.assertEqual(snapshot.actual_volume_l, 0.0)
        self.assertEqual(snapshot.actual_duration_minutes, 0.0)

        fresh_disp = CommandDispatcher(registry=MockRegistry(driver), safety=monitor)
        stops_before = driver.stops
        await fresh_disp.reconcile_on_restart([snapshot])

        self.assertEqual(snapshot.status, EventStatus.COMPLETED)
        self.assertEqual(snapshot.actual_volume_l, 40000.0)
        self.assertEqual(snapshot.actual_duration_minutes, 6.0)
        self.assertEqual(snapshot.delivered_volume_mm, 4.0)
        self.assertEqual(driver.stops, stops_before)


if __name__ == "__main__":
    unittest.main()
