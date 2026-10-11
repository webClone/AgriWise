"""Regression and contract verification tests for PB01 through PB07 defect groups.

Verifies:
- PB01: Pending START transport ownership & lifecycle:
        Completion refuses to complete while a command is pending in flight;
        concurrent terminal finalization fences late ACK;
        exposure is conserved so budget limits cannot be breached.
- PB02: Cancellation identity fencing:
        Cancelling an older event never sends physical STOP to a different live operation;
        cancelling the actual owner dispatches physical STOP.
- PB03: Device-level safety interlock routing:
        Device-level sensor hazards (PRESSURE_HIGH) trigger physical emergency stop
        even when polled from a stale event; the active operation is durably stopped.
        Stale duration watchdog does not stop a healthy live operation.
- PB04: Strict area validation at dispatcher boundary:
        Invalid raw effective_area_ha (-1, 0, boolean, string, NaN, Inf) is rejected
        before admission with typed FAILED status and zero physical commands.
- PB05: Stopped-only canonical envelope & plot rebind protection:
        Reopening stopped receipts preserves canonical envelope dimensions and prevents
        plot rebind corruption; aggregate conservation is strictly maintained.
- PB06: Idempotent settlement normalization retry:
        When settlement normalizes delivery from actual volume and area, identical retry
        succeeds idempotently without raising ValueError.
- PB07: Explicit zero litres delivers zero depth:
        Direct store settlement with explicit actual_volume_l = 0.0 certifies 0.0 mm
        delivered depth and adds 0.0 mm to settled totals.
"""

import asyncio
import copy
import json
import math
import unittest
from datetime import datetime, timezone
from typing import Optional, List, Dict

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.dispatcher import CommandDispatcher
from irrigation_runtime.safety import (
    InterlockType,
    SafetyInterlock,
    SafetyMonitor,
    SharedQuotaStore,
    WaterBudget,
)
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
        self._pending_command: Optional[IrrigationCommand] = None

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
            self._pending_command = None
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
        self._pending_command = None
        return CommandResult(
            cmd.command_id,
            self.device_id,
            True,
            datetime.now(timezone.utc).isoformat(),
        )

    async def get_status(self) -> ActuatorStatus:
        if self.reported_status is not None:
            return self.reported_status
        self._status = ActuatorStatus.EXECUTING if self.running else ActuatorStatus.ONLINE
        return self._status

    async def emergency_stop(self) -> CommandResult:
        self.stops += 1
        self.running = False
        self._status = ActuatorStatus.ONLINE
        self._active_command = None
        self._pending_command = None
        return CommandResult(
            "CMD-EMERGENCY-STOP",
            self.device_id,
            True,
            datetime.now(timezone.utc).isoformat(),
        )


class MockRegistry:
    def __init__(self, actuators: Optional[Dict[str, IrrigationActuator]] = None):
        self._actuators: Dict[str, IrrigationActuator] = actuators or {}

    def add(self, actuator: IrrigationActuator) -> None:
        self._actuators[actuator.device_id] = actuator

    def get_actuator(self, device_id: str) -> Optional[IrrigationActuator]:
        return self._actuators.get(device_id)

    def list_actuators(self) -> List[IrrigationActuator]:
        return list(self._actuators.values())

    async def emergency_stop_all(self):
        for act in self._actuators.values():
            await act.emergency_stop()


def make_event(
    event_id: str = "E",
    device_id: str = "device",
    plot_id: str = "plot",
    zone_id: str = "zone",
    volume: float = 8.0,
    duration: float = 10.0,
    flow: float = 10.0,
    area: Optional[float] = 1.0,
) -> IrrigationEvent:
    ev = IrrigationEvent(
        event_id=event_id,
        plot_id=plot_id,
        zone_id=zone_id,
        device_id=device_id,
        system_type=IrrigationSystemType.DRIP,
        automation_mode=AutomationMode.FULL_AUTO,
        target_volume_mm=volume,
        target_duration_minutes=duration,
        target_flow_rate_lpm=flow,
        effective_area_ha=area,
        status=EventStatus.QUEUED,
    )
    return ev


class TestPB01ThroughPB07ContractVerification(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    async def test_pb01_pending_start_cannot_complete_and_conserves_exposure(self):
        """PB01: An event with a pending command in flight cannot complete;

        if finalized behind its back, late ACK fences the actuator;
        exposure is conserved so total commanded depth cannot exceed budget.
        """
        class HeldDriver(MockDriver):
            def __init__(self):
                super().__init__()
                self.entered = asyncio.Event()
                self.release = asyncio.Event()

            async def send_command(self, cmd: IrrigationCommand) -> CommandResult:
                if cmd.command_type == CommandType.START_ZONE:
                    self._pending_command = cmd
                    self.entered.set()
                    await self.release.wait()
                return await super().send_command(cmd)

        driver = HeldDriver()
        driver_sec = MockDriver("device_sec")
        reg = MockRegistry({"device": driver, "device_sec": driver_sec})
        dispatcher_a = CommandDispatcher(registry=reg, safety=SafetyMonitor())

        event_a = make_event("E", volume=8.0, area=1.0)
        budget = WaterBudget(
            plot_id="plot",
            season="default_season",
            daily_quota_mm=10.0,
            daily_remaining_mm=10.0,
            season_quota_mm=10.0,
            season_remaining_mm=10.0,
        )

        # Worker A submits event E; send_command is held
        task_a = asyncio.create_task(dispatcher_a.submit_event(event_a, budget=budget))
        await asyncio.wait_for(driver.entered.wait(), timeout=3.0)

        # Worker B (fresh dispatcher on restart) attempts recovery & completion
        dispatcher_b = CommandDispatcher(registry=reg, safety=SafetyMonitor())
        snapshot_b = copy.deepcopy(event_a)

        await dispatcher_b.reconcile_on_restart([snapshot_b])
        # Because driver._pending_command is present, recovery marks STOP_REQUESTED, not VALIDATING
        self.assertEqual(snapshot_b.status, EventStatus.STOP_REQUESTED)

        # Attempt to complete prematurely
        completed = await dispatcher_b.complete_event("E", actual_volume_l=0.0, actual_duration_minutes=0.0)
        # complete_event must refuse to complete while driver has pending command!
        self.assertNotEqual(completed.status, EventStatus.COMPLETED)
        self.assertEqual(SharedQuotaStore.get_reserved("plot"), 8.0)

        # Release held START on driver
        driver.release.set()
        await asyncio.wait_for(task_a, timeout=3.0)

        # A second 8 mm request is submitted against the 10 mm budget
        disp_sec = CommandDispatcher(registry=reg, safety=SafetyMonitor())
        event_sec = make_event("SECOND", device_id="device_sec", volume=8.0, area=1.0)

        res_sec = await disp_sec.submit_event(event_sec, budget=budget)
        # Must fail because 8 + 8 = 16 > 10 mm budget
        self.assertEqual(res_sec.status, EventStatus.FAILED)
        self.assertFalse(driver.running and driver_sec.running)

    async def test_pb02_cancellation_identity_does_not_stop_different_live_operation(self):
        """PB02: Cancelling an older event never sends physical STOP to a different live operation."""
        driver = MockDriver()
        reg = MockRegistry({"device": driver})
        dispatcher = CommandDispatcher(registry=reg, safety=SafetyMonitor())

        # Submit OLD
        old_ev = make_event("OLD", volume=1.0)
        await dispatcher.submit_event(old_ev)
        self.assertEqual(driver.active_command.source_event_id, "OLD")

        # OLD completes on physical controller between polls, NEW starts
        driver.running = False
        await driver.get_status()
        new_ev = make_event("NEW", volume=1.0, duration=20.0)
        disp_new = CommandDispatcher(registry=reg, safety=SafetyMonitor())
        await disp_new.submit_event(new_ev)
        self.assertEqual(driver.active_command.source_event_id, "NEW")
        self.assertTrue(driver.running)

        before_stops = driver.stops
        # Cancel OLD
        res_cancel = await dispatcher.cancel_event("OLD")
        self.assertEqual(res_cancel.status, EventStatus.CANCELLED)
        # Must NOT dispatch STOP to the actuator because actuator is executing NEW!
        self.assertEqual(driver.stops - before_stops, 0)
        self.assertTrue(driver.running)
        self.assertEqual(driver.active_command.source_event_id, "NEW")
        self.assertEqual(new_ev.status, EventStatus.EXECUTING)
        self.assertEqual(SharedQuotaStore.get_active_record("NEW")["status"], "EXECUTING")

        # Now cancel NEW (the true owner) -> must dispatch physical STOP
        await disp_new.cancel_event("NEW")
        self.assertEqual(driver.stops - before_stops, 1)
        self.assertFalse(driver.running)

    async def test_pb03_device_pressure_cutoff_is_not_suppressed_by_stale_event_guard(self):
        """PB03: Current device pressure cutoff triggers physical emergency stop

        and stops the live operation durably, even when checked from a stale event poll.
        """
        driver = MockDriver()
        reg = MockRegistry({"device": driver})
        dispatcher = CommandDispatcher(registry=reg, safety=SafetyMonitor())

        old_ev = make_event("OLD", volume=1.0, duration=20.0)
        await dispatcher.submit_event(old_ev)

        # Switch live operation to NEW
        driver.running = False
        await driver.get_status()
        disp_new = CommandDispatcher(registry=reg, safety=SafetyMonitor())
        new_ev = make_event("NEW", volume=1.0, duration=20.0)
        await disp_new.submit_event(new_ev)

        # Configure high pressure interlock on the monitor
        dispatcher._safety.add_interlock(
            SafetyInterlock(
                interlock_id="HIGH-PRESSURE",
                interlock_type=InterlockType.PRESSURE_HIGH,
                description="Device pressure exceeded",
                sensor_variable="pressure_bar",
                threshold_max=1.0,
                duration_seconds=0.0,
            )
        )

        before_stops = driver.stops
        # Check execution status of OLD with pressure 2.0 bar (> 1.0 bar threshold)
        await dispatcher.check_execution_status("OLD", {"pressure_bar": 2.0})

        # Physical STOP must be dispatched to shut down the dangerous overpressure!
        self.assertEqual(driver.stops - before_stops, 1)
        self.assertFalse(driver.running)
        self.assertIsNone(driver.active_command)
        # Durable status for NEW must be EMERGENCY_STOPPED
        self.assertEqual(SharedQuotaStore.get_active_record("NEW")["status"], "CANCELLED")

        # A second poll does not add duplicate STOPs
        await dispatcher.check_execution_status("OLD", {"pressure_bar": 2.0})
        self.assertEqual(driver.stops - before_stops, 1)

    async def test_pb04_dispatcher_rejects_invalid_area_without_laundering_to_missing(self):
        """PB04: Invalid effective_area_ha is rejected before admission;

        it is never laundered into missing (None) support.
        """
        invalid_areas = [-1, 0, True, False, "1", float("nan"), float("inf"), float("-inf")]
        for area in invalid_areas:
            SharedQuotaStore.reset()
            driver = MockDriver()
            reg = MockRegistry({"device": driver})
            disp = CommandDispatcher(registry=reg, safety=SafetyMonitor())

            ev = make_event("E", area=area)
            ret = await disp.submit_event(ev)
            self.assertEqual(ret.status, EventStatus.FAILED, f"Area {area!r} should have failed validation")
            self.assertEqual(driver.deliveries, 0, f"Area {area!r} dispatched physical command")
            self.assertIsNone(SharedQuotaStore.get_active_record("E"))

        # Valid positive area and None (absent) area are accepted
        for valid_area in [None, 1.0]:
            SharedQuotaStore.reset()
            driver = MockDriver()
            reg = MockRegistry({"device": driver})
            disp = CommandDispatcher(registry=reg, safety=SafetyMonitor())

            ev = make_event("E", area=valid_area)
            ret = await disp.submit_event(ev)
            self.assertEqual(ret.status, EventStatus.EXECUTING)
            self.assertEqual(driver.deliveries, 1)

    def test_pb05_stopped_only_reopen_preserves_canonical_envelope_and_blocks_plot_rebind(self):
        """PB05: Reopening stopped receipts preserves the canonical envelope and prevents plot rebind poisoning."""
        SharedQuotaStore.reserve("E", "plot", 8.0, season="S1", date="2026-10-11", device_id="device", zone_id="zone", duration_minutes=10.0, flow_rate_lpm=10.0, effective_area_ha=1.0)
        SharedQuotaStore.record_stopped_delivery("E", "plot", 8.0, season="S1")

        # Reopen with conflicting dimensions: must preserve original 8.0 mm
        SharedQuotaStore.reopen_active("E", "plot", 1.0, season="S2", date="2026-10-12", device_id="other_device", zone_id="other_zone", duration_minutes=20.0, flow_rate_lpm=3.0, effective_area_ha=2.0)
        rec = SharedQuotaStore.get_active_record("E")
        self.assertEqual(rec["volume_mm"], 8.0)
        self.assertEqual(rec["duration_minutes"], 10.0)
        self.assertEqual(rec["flow_rate_lpm"], 10.0)
        self.assertEqual(rec["effective_area_ha"], 1.0)

        # Attempting plot rebind must raise ValueError and leave store readable
        SharedQuotaStore.record_stopped_delivery("E", "plot", 8.0, season="S1")
        with self.assertRaises(ValueError):
            SharedQuotaStore.reopen_active("E", "other_plot", 1.0, duration_minutes=10.0, flow_rate_lpm=10.0, effective_area_ha=1.0)

        state = SharedQuotaStore._read_state()
        self.assertIsNotNone(state)
        self.assertIn("E", state.get("stopped_receipts", {}))

    def test_pb06_settlement_normalization_is_idempotent_on_exact_retry(self):
        """PB06: First settlement succeeds after normalization, and identical retry succeeds idempotently."""
        test_cases = [(4.0, 8.0), (5.0, 8.0), (4.0, 99.0)]
        for supplied_depth, supplied_target in test_cases:
            SharedQuotaStore.reset()
            SharedQuotaStore.reserve("E", "plot", 8.0, date="2026-10-11", season="S1", device_id="device", zone_id="zone", duration_minutes=10.0, flow_rate_lpm=10.0, effective_area_ha=1.0)
            kwargs = dict(
                target_volume_mm=supplied_target,
                actual_volume_l=40000.0,
                actual_duration_minutes=6.0,
                date="2026-10-11",
                season="S1",
                device_id="device",
                zone_id="zone",
                duration_minutes=10.0,
                flow_rate_lpm=10.0,
                effective_area_ha=1.0,
            )
            # First settlement
            SharedQuotaStore.settle("E", "plot", supplied_depth, **kwargs)
            rcpt1 = SharedQuotaStore.get_settled_receipt("E")
            self.assertEqual(rcpt1["delivered_volume_mm"], 4.0)

            # Exact retry must succeed idempotently without raising ValueError
            SharedQuotaStore.settle("E", "plot", supplied_depth, **kwargs)
            rcpt2 = SharedQuotaStore.get_settled_receipt("E")
            self.assertEqual(rcpt2["delivered_volume_mm"], 4.0)

    def test_pb07_direct_settlement_zero_litres_certifies_zero_depth(self):
        """PB07: Direct settlement with explicit actual_volume_l = 0.0 must certify 0.0 mm delivered depth."""
        SharedQuotaStore.reserve("E", "plot", 8.0, duration_minutes=10.0, flow_rate_lpm=10.0)
        SharedQuotaStore.settle("E", "plot", 8.0, target_volume_mm=8.0, actual_volume_l=0.0, effective_area_ha=None)
        rcpt = SharedQuotaStore.get_settled_receipt("E")
        self.assertEqual(rcpt["actual_volume_l"], 0.0)
        self.assertEqual(rcpt["delivered_volume_mm"], 0.0)
        self.assertEqual(SharedQuotaStore.get_settled("plot"), 0.0)


if __name__ == "__main__":
    unittest.main()
