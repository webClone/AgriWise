"""Test suite for RC01-RC07 boundary defect groups remediation.

Verifies:
- RC01: Storage failure during poll cannot abort ordinary duration watchdog; physical cutoff executes.
- RC02: Authoritative terminal receipts fence stale restart snapshots; stale event cannot stop a live operation.
- RC03: Immutable operation envelope (plot, device, target) is preserved on restart and first settlement; budget protected.
- RC04: Durable verified start timing is authoritative over caller timestamps; ACK start is immediately durable.
- RC05: Restored VALIDATING requires fresh controller qualification; running controller prevents premature completion.
- RC06: Zero volume preserves None duration; idle recovery without store record stays VALIDATING without certifying commanded depth.
- RC07: Strict scalar validation on all public writers (reserve, reopen_active, atomic_check_and_reserve) prevents corrupted ledger.
"""

import asyncio
import copy
from datetime import datetime, timezone, timedelta
import os
import unittest

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.dispatcher import CommandDispatcher
from irrigation_runtime.safety import SafetyMonitor, SharedQuotaStore, InterlockType
from irrigation_runtime.schemas import (
    ActuatorCapabilities,
    ActuatorRegistration,
    ActuatorStatus,
    AutomationMode,
    CommandResult,
    CommandType,
    DriverProtocol,
    EventStatus,
    IrrigationEvent,
    IrrigationSystemType,
    VendorId,
    WaterBudget,
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
        self.status_queries = 0

    async def connect(self):
        return True

    async def disconnect(self):
        pass

    async def send_command(self, cmd):
        if cmd.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.deliveries += 1
            self.running = True
            self.set_active_command(cmd)
            return CommandResult(
                cmd.command_id,
                self.device_id,
                True,
                datetime.now(timezone.utc).isoformat(),
            )
        self.stops += 1
        self.running = False
        self._active_command = None
        return CommandResult(
            cmd.command_id,
            self.device_id,
            True,
            datetime.now(timezone.utc).isoformat(),
        )

    async def get_status(self):
        self.status_queries += 1
        self._status = ActuatorStatus.EXECUTING if self.running else ActuatorStatus.ONLINE
        return self._status

    async def emergency_stop(self):
        self.stops += 1
        self.running = False
        self._active_command = None
        return CommandResult(
            "stop",
            self.device_id,
            True,
            datetime.now(timezone.utc).isoformat(),
        )


class MockRegistry:
    def __init__(self, actuator: MockDriver):
        self._actuator = actuator

    def get_actuator(self, device_id: str):
        if self._actuator.device_id == device_id:
            return self._actuator
        return None

    async def emergency_stop_all(self):
        return {self._actuator.device_id: await self._actuator.emergency_stop()}


def _make_event(eid: str = "E", device: str = "device", volume: float = 8.0, duration: float = 10.0, plot: str = "plot") -> IrrigationEvent:
    return IrrigationEvent(
        eid,
        plot,
        "zone",
        device,
        IrrigationSystemType.DRIP,
        AutomationMode.FULL_AUTO,
        status=EventStatus.QUEUED,
        target_volume_mm=volume,
        target_duration_minutes=duration,
        target_flow_rate_lpm=10.0,
    )


def _make_budget(daily: float = 10.0, season: float = 100.0) -> WaterBudget:
    return WaterBudget(
        plot_id="plot",
        season="season",
        daily_quota_mm=daily,
        daily_remaining_mm=daily,
        season_quota_mm=season,
        season_remaining_mm=season,
    )


class TestRC01ToRC07Remediation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    async def test_rc01_watchdog_unshielded_write_failure_still_cuts_off_actuator(self):
        """RC01: Storage failure during poll does not prevent duration watchdog from halting actuator."""
        dr = MockDriver("device")
        clock_now = 0.0
        monitor = SafetyMonitor(clock=lambda: clock_now)
        disp = CommandDispatcher(registry=MockRegistry(dr), safety=monitor)

        ev = _make_event("E", "device", volume=8.0, duration=10.0)
        await disp.submit_event(ev, budget=_make_budget())
        self.assertTrue(dr.running)

        # Advance injected clock past 10 minutes (661 seconds)
        clock_now = 661.0

        # Simulate broken _write_state on quota store during poll
        orig_write = SharedQuotaStore._write_state
        def broken(cls, data):
            raise OSError("simulated start-time publication failure")
        SharedQuotaStore._write_state = classmethod(broken)

        try:
            with self.assertRaises(OSError):
                await disp.check_execution_status("E", {})
        finally:
            SharedQuotaStore._write_state = orig_write

        # Physical cutoff must have been executed despite store write failure!
        self.assertFalse(dr.running)
        self.assertEqual(dr.stops, 1)
        self.assertEqual(ev.status, EventStatus.EMERGENCY_STOPPED)
        # Owner remains tracked in dispatcher because bookkeeping could not finalize
        self.assertIn("E", disp.get_active_events()[0].event_id)

    async def test_rc02_terminal_record_fences_stale_restart_and_does_not_stop_live_operation(self):
        """RC02: Canonical terminal receipts fence stale restart snapshots; stale event does not stop newer live event."""
        dr = MockDriver("device")
        monitor = SafetyMonitor()
        disp = CommandDispatcher(registry=MockRegistry(dr), safety=monitor)

        # Complete event E
        ev_e = _make_event("E", "device", volume=8.0, duration=10.0)
        ev_e.effective_area_ha = 1.0
        await disp.submit_event(ev_e, budget=_make_budget())
        stale_e = copy.deepcopy(ev_e)
        dr.running = False
        await disp.check_execution_status("E", {})
        await disp.complete_event("E", actual_volume_l=40000, actual_duration_minutes=6.0)

        # Start live event NEW on the same device
        ev_new = _make_event("NEW", "device", volume=3.0, duration=20.0)
        ev_new.effective_area_ha = 1.0
        await disp.submit_event(ev_new, budget=_make_budget())
        self.assertTrue(dr.running)
        stops_before = dr.stops

        # Stale snapshot of E with an expired timestamp enters restart reconciliation
        stale_e.actual_start = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
        recovery_disp = CommandDispatcher(registry=MockRegistry(dr), safety=monitor)
        await recovery_disp.reconcile_on_restart([stale_e])

        # NEW must remain live and running, receiving 0 stop commands
        self.assertTrue(dr.running)
        self.assertEqual(dr.stops, stops_before)
        self.assertEqual(ev_new.status, EventStatus.EXECUTING)
        self.assertEqual(stale_e.status, EventStatus.COMPLETED)
        self.assertEqual(len(recovery_disp.get_active_events()), 0)

    async def test_rc03_scope_identity_immutable_across_restart_and_first_settlement(self):
        """RC03: Restart restores canonical plot envelope; conflicting plot on first settlement is rebound to reserved plot."""
        dr = MockDriver("device")
        monitor = SafetyMonitor()
        disp = CommandDispatcher(registry=MockRegistry(dr), safety=monitor)

        ev_e = _make_event("E", "device", volume=8.0, duration=10.0, plot="plot")
        ev_e.effective_area_ha = 1.0
        await disp.submit_event(ev_e, budget=_make_budget(daily=10.0))

        # Restart with conflicting snapshot claiming different_plot and 12mm
        stale_e = copy.deepcopy(ev_e)
        stale_e.plot_id = "different_plot"
        stale_e.target_volume_mm = 12.0

        fresh_disp = CommandDispatcher(registry=MockRegistry(dr), safety=monitor)
        await fresh_disp.reconcile_on_restart([stale_e])

        # Canonical envelope restored to plot with 8mm exposure
        rec = SharedQuotaStore.get_active_record("E")
        self.assertEqual(rec["plot_id"], "plot")
        self.assertEqual(rec["volume_mm"], 8.0)
        self.assertEqual(SharedQuotaStore.get_reserved("plot"), 8.0)
        self.assertEqual(SharedQuotaStore.get_reserved("different_plot"), 0.0)

        # Second event on plot for 8mm is blocked under 10mm budget (8 + 8 = 16 > 10)
        second_dr = MockDriver("second_device")
        second_disp = CommandDispatcher(registry=MockRegistry(second_dr), safety=monitor)
        second_ev = _make_event("SECOND", "second_device", volume=8.0, duration=10.0, plot="plot")
        second_ev.effective_area_ha = 1.0
        res_ev = await second_disp.submit_event(second_ev, budget=_make_budget(daily=10.0))
        self.assertEqual(res_ev.status, EventStatus.FAILED)
        self.assertFalse(second_dr.running)

        # First settlement with different_plot binds to canonical reserved plot
        SharedQuotaStore.settle(
            "E", "different_plot", volume_mm=4.0, target_volume_mm=8.0,
            actual_volume_l=40000, actual_duration_minutes=6.0,
            device_id="device", zone_id="zone", duration_minutes=10, flow_rate_lpm=10, effective_area_ha=1.0,
        )
        self.assertEqual(SharedQuotaStore.get_settled("plot"), 4.0)
        self.assertEqual(SharedQuotaStore.get_settled("different_plot"), 0.0)
        receipt = SharedQuotaStore.get_settled_receipt("E")
        self.assertEqual(receipt["plot_id"], "plot")

    async def test_rc04_deadline_authority_durable_start_supersedes_caller(self):
        """RC04: Verified durable start time is authoritative over caller snapshot; ACK start is durable immediately."""
        dr = MockDriver("device")
        monitor = SafetyMonitor()
        disp = CommandDispatcher(registry=MockRegistry(dr), safety=monitor)

        ev = _make_event("E", "device", volume=8.0, duration=10.0)
        ret = await disp.submit_event(ev, budget=_make_budget())

        # ACK phase immediately persisted actual_start before first poll
        rec = SharedQuotaStore.get_active_record("E")
        self.assertIsNotNone(rec.get("actual_start"))
        self.assertEqual(rec["actual_start"], ret.actual_start)

        # Simulate established start 11 minutes ago
        orig_start = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
        SharedQuotaStore.set_actual_start("E", orig_start)

        # Caller provides fresh now() timestamp on retry/restart
        dup = _make_event("E", "device", volume=8.0, duration=10.0)
        dup.actual_start = datetime.now(timezone.utc).isoformat()

        fresh_disp = CommandDispatcher(registry=MockRegistry(dr), safety=monitor)
        ret_dup = await fresh_disp.submit_event(dup, budget=_make_budget())
        await fresh_disp.reconcile_on_restart([ret_dup])

        # Caller timestamp ignored; verified durable start authoritative; expired operation stopped
        self.assertEqual(ret_dup.actual_start, orig_start)
        self.assertEqual(ret_dup.status, EventStatus.EMERGENCY_STOPPED)
        self.assertFalse(dr.running)
        self.assertEqual(dr.stops, 1)

    async def test_rc05_completion_queries_realtime_controller_before_certifying_terminal(self):
        """RC05: Completion qualifies physical controller status; running simulation prevents premature settlement."""
        dr = MockDriver("device", running=True)
        monitor = SafetyMonitor()
        disp = CommandDispatcher(registry=MockRegistry(dr), safety=monitor)

        # Event in VALIDATING phase
        ev = _make_event("E", "device", volume=8.0, duration=10.0)
        ev.status = EventStatus.VALIDATING
        ev.effective_area_ha = 1.0
        SharedQuotaStore.reserve("E", "plot", 8.0, duration_minutes=10, flow_rate_lpm=10, effective_area_ha=1.0)
        SharedQuotaStore.mark_unsettled("E")

        # Driver cache is initially ONLINE, but real controller is running
        self.assertEqual(dr._status, ActuatorStatus.ONLINE)
        await disp.reconcile_on_restart([ev])

        # Complete event queries hardware; sees controller still running and stays VALIDATING
        completed = await disp.complete_event("E", actual_volume_l=40000, actual_duration_minutes=6.0)
        self.assertEqual(completed.status, EventStatus.VALIDATING)
        self.assertEqual(SharedQuotaStore.get_reserved("plot"), 8.0)
        self.assertEqual(SharedQuotaStore.get_settled("plot"), 0.0)

    async def test_rc06_measurement_missingness_zero_volume_preserves_none_duration(self):
        """RC06: Zero volume preserves None duration; idle restart without store record does not certify commanded depth."""
        dr = MockDriver("device")
        monitor = SafetyMonitor()
        disp = CommandDispatcher(registry=MockRegistry(dr), safety=monitor)

        ev = _make_event("E", "device", volume=8.0, duration=10.0)
        ev.effective_area_ha = 1.0
        await disp.submit_event(ev, budget=_make_budget())
        dr.running = False
        await disp.check_execution_status("E", {})

        # Complete with explicit 0 L volume and omitted duration
        await disp.complete_event("E", actual_volume_l=0.0)
        receipt = SharedQuotaStore.get_settled_receipt("E")
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["actual_volume_l"], 0.0)
        self.assertIsNone(receipt["actual_duration_minutes"])

        # Idle restart without durable store record stays VALIDATING without certifying commanded depth
        SharedQuotaStore.reset()
        legacy = _make_event("LEGACY", "device", volume=8.0, duration=10.0)
        legacy.status = EventStatus.EXECUTING
        legacy.actual_start = datetime.now(timezone.utc).isoformat()
        legacy.effective_area_ha = 1.0

        fresh_dr = MockDriver("device")
        fresh_disp = CommandDispatcher(registry=MockRegistry(fresh_dr), safety=monitor)
        await fresh_disp.reconcile_on_restart([legacy])

        self.assertEqual(legacy.status, EventStatus.VALIDATING)
        self.assertIsNone(SharedQuotaStore.get_settled_receipt("LEGACY"))
        self.assertEqual(SharedQuotaStore.get_settled("plot"), 0.0)

    def test_rc07_candidate_writer_integrity_rejects_negative_scalars(self):
        """RC07: reserve, reopen_active, and atomic_check_and_reserve reject invalid negative scalars without corrupting store."""
        SharedQuotaStore.reserve("SAFE", "plot", 2.0, duration_minutes=5, flow_rate_lpm=10, effective_area_ha=1.0)
        raw_before = SharedQuotaStore._store_file().read_bytes()

        # reserve with duration_minutes = -1
        with self.assertRaises(ValueError):
            SharedQuotaStore.reserve("BAD1", "plot", 1.0, duration_minutes=-1, flow_rate_lpm=10, effective_area_ha=1.0)
        self.assertEqual(SharedQuotaStore._store_file().read_bytes(), raw_before)

        # reopen_active with duration_minutes = -1
        with self.assertRaises(ValueError):
            SharedQuotaStore.reopen_active("BAD2", "plot", 1.0, duration_minutes=-1, flow_rate_lpm=10, effective_area_ha=1.0)
        self.assertEqual(SharedQuotaStore._store_file().read_bytes(), raw_before)

        # atomic_check_and_reserve with duration_minutes = -1
        with self.assertRaises(ValueError):
            SharedQuotaStore.atomic_check_and_reserve("plot", 1.0, event_id="BAD3", duration_minutes=-1, flow_rate_lpm=10, effective_area_ha=1.0)
        self.assertEqual(SharedQuotaStore._store_file().read_bytes(), raw_before)

        # Existing store remains valid and readable
        state = SharedQuotaStore._read_state()
        self.assertIn("SAFE", state["reservations"])


if __name__ == "__main__":
    unittest.main()
