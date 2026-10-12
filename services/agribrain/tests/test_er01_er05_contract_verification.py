"""Contract verification tests for ER01 through ER05 defect groups.

Verifies:
- ER01: STOP polling during pending START does not publish terminal CANCELLED;
        failed late fence preserves watchdog elapsed age;
        restart recovery never skips a running controller.
- ER02: Device STOP transport exception (e.g. OSError) is safely normalized,
        records durable/local STOP_REQUESTED, and ensures cutoff is retried on
        subsequent polls even when sensor hazard is already latched.
- ER03: Cancellation queries live actuator status, rejects unconfirmed/unknown
        idle caches, and never preempts a pending NEW command when cancelling OLD.
- ER04: Reopening an active/settled operation preserves qualified delivered depth
        as an immutable lower bound on effective budget exposure (val >= delivered).
- ER05: Re-settlement with conflicting parameters is rejected before mutation;
        settlement replacing a prior receipt deducts prior delivery for net-delta conservation.
"""

import asyncio
import copy
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

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
    def __init__(
        self,
        device: str = "device",
        stop_fails: bool = False,
        ack_mode: str = "ok",
        reported_status: ActuatorStatus = None,
    ):
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
        self.running = False
        self.calls = []
        self.stops = 0
        self.deliveries = 0
        self.stop_fails = stop_fails
        self.ack_mode = ack_mode
        self.reported_status = reported_status
        self._pending_command = None
        self.get_status_calls = 0

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        pass

    async def send_command(self, cmd: IrrigationCommand) -> CommandResult:
        self.calls.append(cmd)
        if cmd.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.deliveries += 1
            self.running = self.ack_mode not in ("completed_ack_loss", "not_applied_ack_loss")
            self._pending_command = None
            return CommandResult(
                cmd.command_id,
                self.device_id,
                self.ack_mode == "ok",
                datetime.now(timezone.utc).isoformat(),
                error_code="ACK_TIMEOUT" if self.ack_mode != "ok" else "",
                retry_recommended=self.ack_mode != "ok",
            )
        self.stops += 1
        if not self.stop_fails:
            self.running = False
        self._pending_command = None
        return CommandResult(
            cmd.command_id,
            self.device_id,
            not self.stop_fails,
            datetime.now(timezone.utc).isoformat(),
            error_code="STOP_FAILED" if self.stop_fails else "",
        )

    async def get_status(self) -> ActuatorStatus:
        self.get_status_calls += 1
        self._status = self.reported_status or (
            ActuatorStatus.EXECUTING if self.running else ActuatorStatus.ONLINE
        )
        return self._status

    async def emergency_stop(self) -> CommandResult:
        self.stops += 1
        if not self.stop_fails:
            self.running = False
        return CommandResult(
            "stop",
            self.device_id,
            not self.stop_fails,
            datetime.now(timezone.utc).isoformat(),
            error_code="STOP_FAILED" if self.stop_fails else "",
        )


class ControllableClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now


def make_event(
    eid: str = "E",
    device: str = "device",
    volume: float = 8.0,
    duration: float = 10.0,
    flow: float = 10.0,
) -> IrrigationEvent:
    return IrrigationEvent(
        event_id=eid,
        plot_id="plot",
        zone_id="zone",
        device_id=device,
        system_type=IrrigationSystemType.DRIP,
        automation_mode=AutomationMode.FULL_AUTO,
        status=EventStatus.QUEUED,
        target_volume_mm=volume,
        target_duration_minutes=duration,
        target_flow_rate_lpm=flow,
    )


def make_dispatcher(driver: MockDriver, clock: ControllableClock = None) -> CommandDispatcher:
    reg = SimpleNamespace(
        get_actuator=lambda _: driver,
        emergency_stop_all=lambda: asyncio.sleep(0),
    )
    return CommandDispatcher(reg, SafetyMonitor(clock), max_retries=1, retry_base_delay=0)


class TestER01toER05ContractVerification(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        SharedQuotaStore.reset()

    async def asyncTearDown(self):
        SharedQuotaStore.reset()

    # =========================================================================
    # ER01: Pending-send protection, watchdog age preservation, running restart
    # =========================================================================

    async def test_er01_pending_stop_poll_retains_stop_requested_and_exposure(self):
        """ER01: STOP polling while START is in-flight must not publish CANCELLED."""
        driver = MockDriver()
        owner = make_dispatcher(driver)
        entered = asyncio.Event()
        release = asyncio.Event()
        real_send = driver.send_command

        async def held_send(cmd):
            if cmd.command_type == CommandType.START_ZONE:
                entered.set()
                await release.wait()
            return await real_send(cmd)

        driver.send_command = held_send
        ev = make_event("E")
        budget = WaterBudget("plot", "season", season_remaining_mm=10, daily_remaining_mm=10)

        # Launch submit_event in background, holds at START_ZONE
        task = asyncio.create_task(owner.submit_event(ev, budget=budget))
        await asyncio.wait_for(entered.wait(), 4.0)

        # Fresh worker polls execution status
        fresh = make_dispatcher(driver)
        snapshot = copy.deepcopy(ev)
        await fresh.reconcile_on_restart([snapshot])

        self.assertEqual(snapshot.status, EventStatus.STOP_REQUESTED)
        self.assertEqual(SharedQuotaStore.get_active_record("E")["status"], "STOP_REQUESTED")

        # Calling check_execution_status while START is pending must NOT terminalize to CANCELLED!
        await fresh.check_execution_status("E", {})

        self.assertEqual(snapshot.status, EventStatus.STOP_REQUESTED)
        self.assertEqual(SharedQuotaStore.get_active_record("E")["status"], "STOP_REQUESTED")
        self.assertIsNone(SharedQuotaStore.get_stopped_receipt("E"))
        self.assertEqual(len(fresh.get_active_events()), 1)
        self.assertEqual(len(fresh._safety._active_events), 1)
        self.assertEqual(SharedQuotaStore.get_reserved("plot"), 8.0)
        self.assertEqual(SharedQuotaStore.get_settled("plot"), 0.0)

        # Release the held START
        release.set()
        returned = await asyncio.wait_for(task, 4.0)
        self.assertEqual(returned.status, EventStatus.CANCELLED)
        self.assertFalse(driver.running)

    async def test_er01_failed_late_fence_preserves_watchdog_elapsed_time(self):
        """ER01: Failed late fence must not rebase original start monotonic clock."""
        clock = ControllableClock(0.0)
        driver = MockDriver(stop_fails=True)
        owner = make_dispatcher(driver, clock)
        entered = asyncio.Event()
        release = asyncio.Event()
        real_send = driver.send_command

        async def held_send(cmd):
            if cmd.command_type == CommandType.START_ZONE:
                entered.set()
                await release.wait()
            return await real_send(cmd)

        driver.send_command = held_send
        ev = make_event("E", duration=10.0)
        task = asyncio.create_task(owner.submit_event(ev))
        await asyncio.wait_for(entered.wait(), 4.0)

        old_start_mono = owner._safety._active_events["E"]["start_monotonic"]
        self.assertEqual(old_start_mono, 0.0)

        # Advance clock beyond 10 min (600s) to 661s and set durable STOP_REQUESTED
        clock.now = 661.0
        SharedQuotaStore.update_status("E", "STOP_REQUESTED")

        violations_before = owner._safety._check_duration_watchdog("device")
        self.assertTrue(any(v.interlock_type == InterlockType.DURATION_EXCEEDED for v in violations_before))

        # Release held START; late fence STOP fails
        release.set()
        await asyncio.wait_for(task, 4.0)

        # Watchdog origin must be preserved at 0.0, NOT reset to 661.0!
        new_start_mono = owner._safety._active_events["E"]["start_monotonic"]
        self.assertAlmostEqual(new_start_mono, 0.0, places=3)

    async def test_er01_restart_reconcile_does_not_skip_running_controller(self):
        """ER01: Reconcile on restart must not skip a running actuator even if stopped receipt exists."""
        # Case 1: Actuator is running; reconcile must issue emergency stop rather than skipping
        driver = MockDriver()
        driver.running = True
        dispatcher = make_dispatcher(driver)

        SharedQuotaStore.record_stopped_delivery("E1", "plot", target_volume_mm=8.0, delivered_volume_mm=8.0)
        self.assertTrue(SharedQuotaStore.is_stopped("E1"))

        snapshot1 = make_event("E1")
        snapshot1.status = EventStatus.DISPATCHING

        await dispatcher.reconcile_on_restart([snapshot1])

        # Emergency stop was issued to running controller
        self.assertEqual(driver.stops, 1)
        self.assertFalse(driver.running)
        self.assertEqual(snapshot1.status, EventStatus.CANCELLED)

        # Case 2: Actuator is running and stop fails; reconcile must retain STOP_REQUESTED and active tracking
        driver_failing = MockDriver(stop_fails=True)
        driver_failing.running = True
        dispatcher_failing = make_dispatcher(driver_failing)

        SharedQuotaStore.record_stopped_delivery("E2", "plot", target_volume_mm=8.0, delivered_volume_mm=8.0)
        self.assertTrue(SharedQuotaStore.is_stopped("E2"))

        snapshot2 = make_event("E2")
        snapshot2.status = EventStatus.DISPATCHING

        await dispatcher_failing.reconcile_on_restart([snapshot2])

        self.assertEqual(driver_failing.stops, 1)
        self.assertTrue(driver_failing.running)
        self.assertIn("E2", [e.event_id for e in dispatcher_failing.get_active_events()])
        self.assertIn("E2", dispatcher_failing._safety._active_events)
        self.assertEqual(snapshot2.status, EventStatus.STOP_REQUESTED)
        self.assertEqual(SharedQuotaStore.get_reserved("plot"), 8.0)

    # =========================================================================
    # ER02: Device STOP exception normalization and retry
    # =========================================================================

    async def test_er02_stop_exception_normalizes_to_stop_requested_and_retries(self):
        """ER02: Exception during emergency stop must record STOP_REQUESTED and retry on next poll."""
        driver = MockDriver()
        owner = make_dispatcher(driver)

        old_ev = await owner.submit_event(make_event("OLD", volume=1.0, duration=20.0))
        driver.running = False
        await driver.get_status()

        new_ev = await owner.submit_event(make_event("NEW", volume=8.0, duration=20.0))
        owner._safety.add_interlock(
            SafetyInterlock(
                "PRESSURE",
                InterlockType.PRESSURE_HIGH,
                "Pressure fault",
                sensor_variable="pressure",
                threshold_max=1.0,
                duration_seconds=0.0,
            )
        )

        async def exc_stop():
            driver.stops += 1
            raise OSError("simulated STOP transport failure")

        driver.emergency_stop = exc_stop

        # First poll with pressure breach: exception must be handled and stop intent recorded
        await owner.check_execution_status("OLD", {"pressure": 2.0})

        self.assertEqual(old_ev.status, EventStatus.STOP_REQUESTED)
        self.assertEqual(new_ev.status, EventStatus.STOP_REQUESTED)
        self.assertEqual(SharedQuotaStore.get_active_record("NEW")["status"], "STOP_REQUESTED")
        self.assertFalse(SharedQuotaStore.is_stopped("NEW"))

        stops_before = driver.stops

        # Second poll: since hazard remains latched and actuator running, STOP must be retried!
        await owner.check_execution_status("OLD", {"pressure": 2.0})

        self.assertGreaterEqual(driver.stops - stops_before, 1)
        self.assertEqual(new_ev.status, EventStatus.STOP_REQUESTED)

    # =========================================================================
    # ER03: Cancellation query verification and pending-command protection
    # =========================================================================

    async def test_er03_cancel_queries_status_and_rejects_unqueried_cache(self):
        """ER03: Cancellation must query live status and reject treating unconfirmed cache as idle."""
        for cached_status in (ActuatorStatus.ONLINE, ActuatorStatus.OFFLINE, ActuatorStatus.UNKNOWN):
            SharedQuotaStore.reset()
            init_driver = MockDriver()
            owner = make_dispatcher(init_driver)
            ev = await owner.submit_event(make_event("E"))

            fresh_driver = MockDriver()
            fresh_driver.running = True
            fresh_driver._status = cached_status

            owner._registry.get_actuator = lambda _: fresh_driver

            await owner.cancel_event("E")

            self.assertGreaterEqual(fresh_driver.get_status_calls, 1)
            self.assertEqual(ev.status, EventStatus.STOP_REQUESTED)
            self.assertEqual(SharedQuotaStore.get_active_record("E")["status"], "STOP_REQUESTED")
            self.assertEqual(len(owner.get_active_events()), 1)
            self.assertEqual(len(owner._safety._active_events), 1)
            self.assertEqual(SharedQuotaStore.get_reserved("plot"), 8.0)

    async def test_er03_cancel_old_does_not_preempt_different_pending_new(self):
        """ER03: Cancelling OLD with different NEW command pending must not send STOP and preempt NEW."""
        driver = MockDriver()
        owner = make_dispatcher(driver)

        old_ev = await owner.submit_event(make_event("OLD", volume=1.0, duration=20.0))
        driver.running = False
        await driver.get_status()

        entered = asyncio.Event()
        release = asyncio.Event()
        real_send = driver.send_command

        async def held_send(cmd):
            if cmd.command_type == CommandType.START_ZONE:
                entered.set()
                await release.wait()
            return await real_send(cmd)

        driver.send_command = held_send
        new_owner = make_dispatcher(driver)
        new_ev = make_event("NEW", volume=1.0, duration=20.0)

        task = asyncio.create_task(new_owner.submit_event(new_ev))
        await asyncio.wait_for(entered.wait(), 4.0)

        # Before cancelling OLD: active_command is OLD, pending is NEW
        stops_before = driver.stops

        # Cancelling OLD must NOT send STOP to driver or preempt NEW
        await owner.cancel_event("OLD")

        self.assertEqual(old_ev.status, EventStatus.CANCELLED)
        self.assertEqual(driver.stops, stops_before)  # Zero STOPs sent!
        self.assertIsNotNone(driver._pending_command)

        release.set()
        await asyncio.wait_for(task, 4.0)

        self.assertEqual(new_ev.status, EventStatus.EXECUTING)
        self.assertTrue(driver.running)

    # =========================================================================
    # ER04: Qualified delivered depth lower bound on reopening
    # =========================================================================

    def test_er04_reopen_preserves_qualified_delivery_lower_bound(self):
        """ER04: Reopening an operation must preserve qualified delivered depth as lower bound."""
        SharedQuotaStore.reserve("E", "plot", 8.0, duration_minutes=10, flow_rate_lpm=8, effective_area_ha=0.001)
        SharedQuotaStore.settle(
            "E",
            "plot",
            12.0,
            target_volume_mm=8.0,
            actual_volume_l=120.0,
            actual_duration_minutes=10.0,
            duration_minutes=10,
            flow_rate_lpm=8,
            effective_area_ha=0.001,
        )

        receipt = SharedQuotaStore.get_settled_receipt("E")
        self.assertEqual(receipt["delivered_volume_mm"], 12.0)

        # Reopen with canonical commanded target 8 mm
        SharedQuotaStore.reopen_active("E", "plot", 8.0, duration_minutes=10, flow_rate_lpm=8, effective_area_ha=0.001)

        # Effective exposure must be at least 12 mm!
        reserved = SharedQuotaStore.get_reserved("plot")
        settled = SharedQuotaStore.get_settled("plot")
        exposure = reserved + settled
        self.assertEqual(exposure, 12.0)

        # A second 10 mm command against a 20 mm budget must be BLOCKED (12 + 10 = 22 > 20)
        budget = WaterBudget("plot", "S1", season_remaining_mm=20.0, daily_remaining_mm=20.0)
        violation = SharedQuotaStore.atomic_check_and_reserve(
            "plot",
            10.0,
            budget,
            event_id="SECOND",
            device_id="second_device",
            duration_minutes=12.5,
            flow_rate_lpm=8,
            effective_area_ha=0.001,
        )
        self.assertIsNotNone(violation)
        self.assertEqual(violation.action_taken, "BLOCK")

    def test_er04_reopen_zero_and_partial_controls(self):
        """ER04: Zero and partial delivered receipts reopen with commanded exposure."""
        for measured in (0.0, 4.0):
            SharedQuotaStore.reset()
            SharedQuotaStore.reserve("E", "plot", 8.0, duration_minutes=10, flow_rate_lpm=10, effective_area_ha=1.0)
            SharedQuotaStore.settle("E", "plot", measured, target_volume_mm=8.0, effective_area_ha=1.0)
            SharedQuotaStore.reopen_active("E", "plot", 8.0, duration_minutes=10, flow_rate_lpm=10, effective_area_ha=1.0)

            exposure = SharedQuotaStore.get_reserved("plot") + SharedQuotaStore.get_settled("plot")
            self.assertEqual(exposure, 8.0)
            # Store must remain valid and readable
            state = SharedQuotaStore._read_state()
            self.assertIn("E", state["reservations"])

    # =========================================================================
    # ER05: Re-settlement ledger conservation and conflict rejection
    # =========================================================================

    def test_er05_active_plus_settled_resettlement_rejects_conflict_without_corrupting_ledger(self):
        """ER05: Conflicting settlement retry must raise ValueError without corrupting ledger."""
        SharedQuotaStore.reserve("E", "plot", 8.0, duration_minutes=10, flow_rate_lpm=10, effective_area_ha=1.0)
        SharedQuotaStore.settle("E", "plot", 4.0, target_volume_mm=8.0, actual_volume_l=40000.0, effective_area_ha=1.0)

        # Call reserve again so active and settled coexist
        SharedQuotaStore.reserve("E", "plot", 8.0, duration_minutes=10, flow_rate_lpm=10, effective_area_ha=1.0)
        state_before = SharedQuotaStore._read_state()
        self.assertEqual(state_before["settled_plot_total"]["plot"], 4.0)

        # Conflicting re-settlement for 3 mm must be rejected!
        with self.assertRaises(ValueError):
            SharedQuotaStore.settle("E", "plot", 3.0, target_volume_mm=8.0, actual_volume_l=30000.0, effective_area_ha=1.0)

        # Store must remain readable with consistent 4.0 mm aggregate
        state_after = SharedQuotaStore._read_state()
        self.assertEqual(state_after["settled_receipts"]["E"]["delivered_volume_mm"], 4.0)
        self.assertEqual(state_after["settled_plot_total"]["plot"], 4.0)


if __name__ == "__main__":
    unittest.main()
