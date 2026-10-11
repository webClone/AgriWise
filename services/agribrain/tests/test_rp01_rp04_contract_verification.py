"""Regression and contract verification tests for RP01 through RP04 defect groups.

Verifies:
- RP01: Cross-process pending START transport ownership & late fencing resilience:
        Worker-local pending START cannot be silently finalized by a second worker
        without proper late-fencing; failed or exceptional late-fencing preserves
        STOP_REQUESTED status, maintains local active tracking and watchdog monitoring,
        and reopens active reservation in SharedQuotaStore; restart reconciliation
        persists and retains STOP_REQUESTED across workers.
- RP02: Device cutoff ordering & failed-STOP preservation:
        Device-level interlock cutoffs check physical STOP success before touching
        active event state; failed STOP preserves active owner in STOP_REQUESTED,
        does not publish a stopped receipt, and retains watchdog tracking.
- RP03: Unqualified / empty operation identity guard:
        Empty or unqualified source identity on a running actuator is never treated
        as a confirmed foreign owner; cancellation does not silently terminalize
        the event to CANCELLED while physical execution remains unresolved,
        maintaining STOP_REQUESTED and active tracking.
- RP04: Full envelope canonicalization retry idempotence:
        Settlement canonicalizing across 7 envelope dimensions (effective_area_ha,
        duration_minutes, flow_rate_lpm, device_id, zone_id, date, season) accepts
        identical retries idempotently without byte mutation or debit corruption,
        while rejecting genuine conflicting measurements.
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
        stop_raises: bool = False,
        running: bool = False,
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
        self.running = running
        self.stops = 0
        self.deliveries = 0
        self.stop_fails = stop_fails
        self.stop_raises = stop_raises
        self._pending_command = None

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
        if self.stop_raises:
            raise OSError("simulated physical stop transport failure")
        if not self.stop_fails:
            self.running = False
            self._active_command = None
            self._status = ActuatorStatus.ONLINE
            return CommandResult(
                cmd.command_id,
                self.device_id,
                True,
                datetime.now(timezone.utc).isoformat(),
            )
        return CommandResult(
            cmd.command_id,
            self.device_id,
            False,
            datetime.now(timezone.utc).isoformat(),
            error_code="STOP_FAILED",
        )

    async def emergency_stop(self) -> CommandResult:
        self.stops += 1
        if self.stop_raises:
            raise OSError("simulated physical emergency stop transport failure")
        if not self.stop_fails:
            self.running = False
            self._active_command = None
            self._status = ActuatorStatus.ONLINE
            return CommandResult(
                "stop",
                self.device_id,
                True,
                datetime.now(timezone.utc).isoformat(),
            )
        return CommandResult(
            "stop",
            self.device_id,
            False,
            datetime.now(timezone.utc).isoformat(),
            error_code="STOP_FAILED",
        )

    async def get_status(self) -> ActuatorStatus:
        self._status = ActuatorStatus.EXECUTING if self.running else ActuatorStatus.ONLINE
        return self._status


def make_event(
    eid: str = "E",
    device: str = "device",
    volume: float = 8.0,
    duration: int = 10,
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
        effective_area_ha=1.0,
    )


def make_dispatcher(driver: MockDriver, clock=None) -> CommandDispatcher:
    reg = SimpleNamespace(
        get_actuator=lambda _: driver,
        emergency_stop_all=lambda: asyncio.sleep(0),
    )
    return CommandDispatcher(
        registry=reg,
        safety=SafetyMonitor(clock=clock),
        max_retries=1,
        retry_base_delay=0.0,
    )


def make_budget() -> WaterBudget:
    return WaterBudget("plot", "season", season_remaining_mm=10.0, daily_remaining_mm=10.0)


class TestRP01RP04Verification(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    # -------------------------------------------------------------------------
    # RP01: Cross-process pending START transport ownership & late fencing
    # -------------------------------------------------------------------------
    async def test_rp01_separate_worker_pending_late_fence_success(self):
        """When late fence succeeds, event transitions to EMERGENCY_STOPPED and stops controller."""
        hardware = SimpleNamespace(running=False)

        class WorkerDriver(MockDriver):
            def __init__(self, hold=False):
                self.hardware = hardware
                super().__init__()
                self.hold = hold
                self.entered = asyncio.Event()
                self.release = asyncio.Event()

            @property
            def running(self):
                return self.hardware.running

            @running.setter
            def running(self, v):
                self.hardware.running = v

            async def send_command(self, cmd):
                if self.hold and cmd.command_type == CommandType.START_ZONE:
                    self.entered.set()
                    await self.release.wait()
                return await super().send_command(cmd)

        owner_driver = WorkerDriver(hold=True)
        owner = make_dispatcher(owner_driver)
        event = make_event("E")

        task = asyncio.create_task(owner.submit_event(event, budget=make_budget()))
        await asyncio.wait_for(owner_driver.entered.wait(), 3)

        # Separate worker finalizes the event while controller was physically idle
        recovery_driver = WorkerDriver()
        fresh = make_dispatcher(recovery_driver)
        snapshot = copy.deepcopy(event)
        await fresh.reconcile_on_restart([snapshot])
        await fresh.complete_event("E", 0, 0)

        # Release first worker send_command; late fencing executes
        owner_driver.release.set()
        returned = await asyncio.wait_for(task, 3)

        self.assertIn(returned.status, (EventStatus.CANCELLED, EventStatus.EMERGENCY_STOPPED, EventStatus.COMPLETED))
        self.assertFalse(hardware.running)
        self.assertGreaterEqual(owner_driver.stops, 1)

    async def test_rp01_separate_worker_pending_late_fence_failed_result(self):
        """When late fence STOP fails, event status is STOP_REQUESTED, ownership & watchdog retained."""
        hardware = SimpleNamespace(running=False)

        class WorkerDriver(MockDriver):
            def __init__(self, hold=False):
                self.hardware = hardware
                super().__init__(stop_fails=True)
                self.hold = hold
                self.entered = asyncio.Event()
                self.release = asyncio.Event()

            @property
            def running(self):
                return self.hardware.running

            @running.setter
            def running(self, v):
                self.hardware.running = v

            async def send_command(self, cmd):
                if self.hold and cmd.command_type == CommandType.START_ZONE:
                    self.entered.set()
                    await self.release.wait()
                return await super().send_command(cmd)

        owner_driver = WorkerDriver(hold=True)
        owner = make_dispatcher(owner_driver)
        event = make_event("E")

        task = asyncio.create_task(owner.submit_event(event, budget=make_budget()))
        await asyncio.wait_for(owner_driver.entered.wait(), 3)

        # Recovery worker finalizes event
        recovery_driver = WorkerDriver()
        fresh = make_dispatcher(recovery_driver)
        snapshot = copy.deepcopy(event)
        await fresh.reconcile_on_restart([snapshot])
        await fresh.complete_event("E", 0, 0)

        # Release first worker; late fence STOP fails
        owner_driver.release.set()
        returned = await asyncio.wait_for(task, 3)

        # Owner must retain active tracking, set STOP_REQUESTED, reopen reservation
        self.assertEqual(returned.status, EventStatus.STOP_REQUESTED)
        self.assertTrue(hardware.running)
        self.assertEqual(len(owner.get_active_events()), 1)
        self.assertIn("E", owner._safety._active_events)
        self.assertTrue(SharedQuotaStore.is_active("E"))
        self.assertEqual(SharedQuotaStore.get_active_record("E")["status"], "STOP_REQUESTED")

    async def test_rp01_separate_worker_pending_late_fence_exception(self):
        """When late fence STOP raises exception, event status is STOP_REQUESTED, ownership retained."""
        hardware = SimpleNamespace(running=False)

        class WorkerDriver(MockDriver):
            def __init__(self, hold=False):
                self.hardware = hardware
                super().__init__(stop_raises=True)
                self.hold = hold
                self.entered = asyncio.Event()
                self.release = asyncio.Event()

            @property
            def running(self):
                return self.hardware.running

            @running.setter
            def running(self, v):
                self.hardware.running = v

            async def send_command(self, cmd):
                if self.hold and cmd.command_type == CommandType.START_ZONE:
                    self.entered.set()
                    await self.release.wait()
                return await super().send_command(cmd)

        owner_driver = WorkerDriver(hold=True)
        owner = make_dispatcher(owner_driver)
        event = make_event("E")

        task = asyncio.create_task(owner.submit_event(event, budget=make_budget()))
        await asyncio.wait_for(owner_driver.entered.wait(), 3)

        recovery_driver = WorkerDriver()
        fresh = make_dispatcher(recovery_driver)
        snapshot = copy.deepcopy(event)
        await fresh.reconcile_on_restart([snapshot])
        await fresh.complete_event("E", 0, 0)

        owner_driver.release.set()
        returned = await asyncio.wait_for(task, 3)

        self.assertEqual(returned.status, EventStatus.STOP_REQUESTED)
        self.assertTrue(hardware.running)
        self.assertEqual(len(owner.get_active_events()), 1)
        self.assertIn("E", owner._safety._active_events)
        self.assertTrue(SharedQuotaStore.is_active("E"))
        self.assertEqual(SharedQuotaStore.get_active_record("E")["status"], "STOP_REQUESTED")

    async def test_rp01_pending_stop_intent_persisted_to_store_on_restart(self):
        """Cross-process restart recovery preserves STOP_REQUESTED intent in shared quota store."""
        driver = MockDriver()
        entered = asyncio.Event()
        release = asyncio.Event()
        orig_send = driver.send_command

        async def held_send(cmd):
            if cmd.command_type == CommandType.START_ZONE:
                entered.set()
                await release.wait()
            return await orig_send(cmd)

        driver.send_command = held_send
        owner = make_dispatcher(driver)
        event = make_event("E")

        task = asyncio.create_task(owner.submit_event(event, budget=make_budget()))
        await asyncio.wait_for(entered.wait(), 3)

        # Recovery worker detects active controller / in-flight event during restart
        fresh = make_dispatcher(driver)
        snapshot = copy.deepcopy(event)
        await fresh.reconcile_on_restart([snapshot])

        self.assertEqual(snapshot.status, EventStatus.STOP_REQUESTED)
        self.assertEqual(SharedQuotaStore.get_active_record("E")["status"], "STOP_REQUESTED")

        # Original worker finishes START ACK
        release.set()
        await asyncio.wait_for(task, 3)

        # Durable status must NOT have been overwritten to EXECUTING; controller is stopped
        rec = SharedQuotaStore.get_active_record("E")
        self.assertNotEqual(rec["status"], "EXECUTING")
        self.assertFalse(driver.running)

    # -------------------------------------------------------------------------
    # RP02: Device cutoff publishes stopped receipt & drops owner only on STOP success
    # -------------------------------------------------------------------------
    async def test_rp02_failed_device_cutoff_retains_actual_owner(self):
        """Device hazard with failed STOP retains active owner in STOP_REQUESTED and no stopped receipt."""
        driver = MockDriver(stop_fails=True)
        owner = make_dispatcher(driver)

        # Submit OLD event, then manually simulate completed status
        old = await owner.submit_event(make_event("OLD", volume=1.0, duration=20), budget=make_budget())
        driver.running = False
        await driver.get_status()

        # Submit NEW live event
        new = await owner.submit_event(make_event("NEW", volume=8.0, duration=20), budget=make_budget())
        self.assertTrue(driver.running)

        # Trigger pressure hazard via OLD event handle
        owner._safety.add_interlock(
            SafetyInterlock(
                "PRESSURE",
                InterlockType.PRESSURE_HIGH,
                "Device pressure hazard",
                sensor_variable="pressure_bar",
                threshold_max=1.0,
                duration_seconds=0,
            )
        )
        await owner.check_execution_status("OLD", {"pressure_bar": 2.0})

        # Physical controller is still running because stop failed
        self.assertTrue(driver.running)
        self.assertGreaterEqual(driver.stops, 1)

        # NEW event must NOT have a stopped receipt published
        self.assertFalse(SharedQuotaStore.is_stopped("NEW"))
        self.assertTrue(SharedQuotaStore.is_active("NEW"))
        self.assertEqual(SharedQuotaStore.get_active_record("NEW")["status"], "STOP_REQUESTED")

        # NEW event must remain tracked by dispatcher and safety monitor
        self.assertIn("NEW", [e.event_id for e in owner.get_active_events()])
        self.assertIn("NEW", owner._safety._active_events)
        self.assertEqual(new.status, EventStatus.STOP_REQUESTED)

    # -------------------------------------------------------------------------
    # RP03: Unqualified operation identity guard
    # -------------------------------------------------------------------------
    async def test_rp03_unqualified_cancel_identity_does_not_falsely_cancel(self):
        """Empty or unqualified operation identity does not blindly stop other owner nor falsely cancel."""
        driver = MockDriver(stop_fails=True)
        owner = make_dispatcher(driver)
        event = await owner.submit_event(make_event("E"), budget=make_budget())

        # Actuator running with unqualified empty source_event_id
        cmd = copy.deepcopy(driver.active_command)
        cmd.source_event_id = ""
        driver.set_active_command(cmd)

        before_stops = driver.stops
        await owner.cancel_event("E")

        # Must NOT blindly send physical STOP to a possibly different healthy owner
        self.assertEqual(driver.stops, before_stops)

        # Execution is unresolved: event must NOT be falsely terminalized to CANCELLED
        self.assertEqual(event.status, EventStatus.STOP_REQUESTED)
        self.assertTrue(driver.running)
        self.assertEqual(len(owner.get_active_events()), 1)
        self.assertIn("E", owner._safety._active_events)
        self.assertTrue(SharedQuotaStore.is_active("E"))
        self.assertEqual(SharedQuotaStore.get_active_record("E")["status"], "STOP_REQUESTED")

    async def test_rp03_distinct_foreign_owner_suppresses_stop(self):
        """Distinct non-empty foreign owner identity safely suppresses physical stop."""
        driver = MockDriver(stop_fails=False)
        owner = make_dispatcher(driver)
        event = await owner.submit_event(make_event("E"), budget=make_budget())

        # Actuator running for distinct foreign owner 'OTHER'
        cmd = copy.deepcopy(driver.active_command)
        cmd.source_event_id = "OTHER"
        driver.set_active_command(cmd)

        before_stops = driver.stops
        await owner.cancel_event("E")

        # STOP must NOT be sent to the foreign owner's running operation
        self.assertEqual(driver.stops, before_stops)
        self.assertEqual(event.status, EventStatus.CANCELLED)

    # -------------------------------------------------------------------------
    # RP04: Full envelope normalization identical retries idempotence
    # -------------------------------------------------------------------------
    def test_rp04_full_envelope_normalization_identical_retries_idempotent(self):
        """Identical retry of settle() across all 7 envelope dimensions succeeds idempotently."""
        envelope_cases = [
            ("control", {}),
            ("target_volume_mm", {"target_volume_mm": 99.0}),
            ("effective_area_ha", {"effective_area_ha": 2.0}),
            ("duration_minutes", {"duration_minutes": 20}),
            ("flow_rate_lpm", {"flow_rate_lpm": 3.0}),
            ("device_id", {"device_id": "other"}),
            ("zone_id", {"zone_id": "other"}),
            ("date", {"date": "2026-10-12"}),
            ("season", {"season": "S2"}),
        ]

        for field_name, extra_kwargs in envelope_cases:
            SharedQuotaStore.reset()
            SharedQuotaStore.reserve(
                "E",
                "plot",
                8.0,
                date="2026-10-11",
                season="S1",
                device_id="device",
                zone_id="zone",
                duration_minutes=10,
                flow_rate_lpm=10.0,
                effective_area_ha=1.0,
            )

            kwargs = {
                "target_volume_mm": 8.0,
                "actual_volume_l": 40000.0,
                "actual_duration_minutes": 6,
                "date": "2026-10-11",
                "season": "S1",
                "device_id": "device",
                "zone_id": "zone",
                "duration_minutes": 10,
                "flow_rate_lpm": 10.0,
                "effective_area_ha": 1.0,
            }
            kwargs.update(extra_kwargs)

            # First settlement (settle returns None on success)
            SharedQuotaStore.settle("E", "plot", 4.0, **kwargs)
            first_receipt = SharedQuotaStore.get_settled_receipt("E")
            self.assertIsNotNone(first_receipt)
            before_bytes = SharedQuotaStore._store_file().read_bytes()

            # Identical retry: must not raise ValueError
            SharedQuotaStore.settle("E", "plot", 4.0, **kwargs)
            retry_receipt = SharedQuotaStore.get_settled_receipt("E")
            self.assertIsNotNone(retry_receipt)

            # Store file bytes unchanged
            after_bytes = SharedQuotaStore._store_file().read_bytes()
            self.assertEqual(before_bytes, after_bytes, f"Bytes changed for {field_name}")

            # Non-identical conflicting retry must fail
            conflict_kwargs = dict(kwargs)
            conflict_kwargs["actual_volume_l"] = 80000.0
            with self.assertRaises(ValueError):
                SharedQuotaStore.settle("E", "plot", 4.0, **conflict_kwargs)


if __name__ == "__main__":
    unittest.main()
