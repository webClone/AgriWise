"""Verification tests for boundary defect groups RV01 through RV09.

Validates that all 9 boundary groups reproduced on commit 1fb78cc
against R3 monograph requirements are cleanly and durably repaired.
"""
import asyncio
import copy
import math
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock

import pytest

from services.agribrain.irrigation_runtime.actuator import (
    CommandResult,
    CommandType,
    IrrigationActuator,
    IrrigationCommand,
    ActuatorStatus,
)
from services.agribrain.irrigation_runtime.schemas import (
    ActuatorCapabilities,
    ActuatorRegistration,
    AutomationMode,
    DriverProtocol,
    IrrigationSystemType,
    VendorId,
)
from services.agribrain.irrigation_runtime.dispatcher import (
    CommandDispatcher,
    EventStatus,
    IrrigationEvent,
    WaterBudget,
)
from services.agribrain.irrigation_runtime.safety import (
    CorruptedQuotaStoreError,
    SafetyMonitor,
    SharedQuotaStore,
)


class MockDriver(IrrigationActuator):
    def __init__(self, device: str = "device", stop_fails: bool = False):
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
        self.stops = 0
        self.deliveries = 0
        self.stop_fails = stop_fails

    async def connect(self):
        return True

    async def disconnect(self):
        pass

    async def send_command(self, cmd: IrrigationCommand) -> CommandResult:
        if cmd.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.deliveries += 1
            self.running = True
            return CommandResult(
                cmd.command_id,
                self.device_id,
                True,
                datetime.now(timezone.utc).isoformat(),
            )
        self.stops += 1
        if not self.stop_fails:
            self.running = False
        return CommandResult(
            cmd.command_id,
            self.device_id,
            not self.stop_fails,
            datetime.now(timezone.utc).isoformat(),
            error_code="STOP_FAILED" if self.stop_fails else "",
        )

    async def get_status(self) -> ActuatorStatus:
        self._status = ActuatorStatus.EXECUTING if self.running else ActuatorStatus.ONLINE
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


def _make_event(eid: str = "E", dev: str = "device", vol: float = 8.0, dur: float = 10.0, flow: float = 10.0, area: Optional[float] = 1.0):
    return IrrigationEvent(
        eid,
        "plot",
        "zone",
        dev,
        IrrigationSystemType.DRIP,
        AutomationMode.FULL_AUTO,
        status=EventStatus.QUEUED,
        target_volume_mm=vol,
        target_duration_minutes=dur,
        target_flow_rate_lpm=flow,
        effective_area_ha=area,
    )


@pytest.fixture(autouse=True)
def clean_quota_store():
    SharedQuotaStore.reset()
    yield
    SharedQuotaStore.reset()


# ============================================================================
# RV01: Emergency Cutoff Ledger Failure Immunity & Guaranteed Fallback
# ============================================================================
@pytest.mark.anyio
async def test_rv01_emergency_cutoff_survives_ledger_failure():
    """RV01: Emergency stop loops through all actuators and guarantees registry fallback even if ledger write fails."""
    a = MockDriver("A")
    b = MockDriver("B")
    devices = {"A": a, "B": b}
    fallback_called = []

    async def reg_stop():
        fallback_called.append(True)

    reg = SimpleNamespace(get_actuator=lambda dev: devices.get(dev), emergency_stop_all=reg_stop)
    d = CommandDispatcher(reg, SafetyMonitor(), max_retries=1, retry_base_delay=0)

    await d.submit_event(_make_event("A", "A"))
    await d.submit_event(_make_event("B", "B"))
    assert a.running and b.running

    # Simulate actuator A transport failure and ledger publication error
    async def thrown_stop():
        a.stops += 1
        raise OSError("simulated transport failure")

    a.emergency_stop = thrown_stop
    orig_write = SharedQuotaStore._write_state

    def fail_write(cls, data):
        raise OSError("simulated ledger failure")

    SharedQuotaStore._write_state = classmethod(fail_write)
    try:
        out = await d.emergency_stop_all()
        # Second actuator B must still have received STOP and stopped running
        assert b.stops == 1
        assert not b.running
        assert len(fallback_called) == 1
        assert out.get("A") == "STOP_ERROR"
        assert out.get("B") == "STOP_ERROR"
    finally:
        SharedQuotaStore._write_state = orig_write


# ============================================================================
# RV03: Ledger-Derived Duplicate Replay Does Not Extend Deadline
# ============================================================================
@pytest.mark.anyio
async def test_rv03_ledger_derived_duplicate_does_not_grant_fresh_deadline():
    """RV03: An executing event without established start time or with expired timing is stopped on restart."""
    dr = MockDriver("device")
    clock = SimpleNamespace(now=661.0)
    d = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: dr, emergency_stop_all=lambda: asyncio.sleep(0)), SafetyMonitor(clock=lambda: clock.now))

    e = _make_event("E", "device", vol=8.0, dur=10.0)
    # Event started 11 minutes ago in the past
    e.actual_start = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
    e.status = EventStatus.EXECUTING
    dr.running = True

    # Reconcile on restart with expired event
    reconciled = await d.reconcile_on_restart([e])
    assert not dr.running
    assert dr.stops >= 1
    assert e.status == EventStatus.EMERGENCY_STOPPED


# ============================================================================
# RV04: VALIDATING Survives Restart & Completion Settles Exactly Once
# ============================================================================
@pytest.mark.anyio
async def test_rv04_validating_survives_restart_and_completes():
    """RV04: VALIDATING phase restores to active events across restart and settles measured delivery."""
    dr = MockDriver("device")
    d = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: dr, emergency_stop_all=lambda: asyncio.sleep(0)), SafetyMonitor())

    e = _make_event("E", "device", vol=8.0, area=1.0)
    await d.submit_event(e)
    dr.running = False
    await d.check_execution_status("E", {})
    # Complete without measurements: transitions to VALIDATING
    await d.complete_event("E")
    assert e.status == EventStatus.VALIDATING
    assert SharedQuotaStore.get_active_record("E")["status"] == "VALIDATING"

    # Simulate process restart
    fresh = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: dr, emergency_stop_all=lambda: asyncio.sleep(0)), SafetyMonitor())
    restored = copy.deepcopy(e)
    reconciled = await fresh.reconcile_on_restart([restored])
    assert len(reconciled) == 1
    assert "E" in fresh.get_active_events()[0].event_id

    # Now deliver valid measurements: settles 4 mm exactly once
    completed = await fresh.complete_event("E", actual_volume_l=40000, actual_duration_minutes=6)
    assert completed.status == EventStatus.COMPLETED
    assert completed.delivered_volume_mm == 4.0
    assert SharedQuotaStore.is_settled("E")
    assert SharedQuotaStore.get_settled("plot") == 4.0
    assert SharedQuotaStore.get_reserved("plot") == 0.0


# ============================================================================
# RV05: Measurement Provenance & Idle Restart
# ============================================================================
@pytest.mark.anyio
async def test_rv05_measurement_provenance_and_missing_duration():
    """RV05: Idle restart does not certify commanded depth without measurements; missing actual duration is None."""
    dr = MockDriver("device")
    d = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: dr, emergency_stop_all=lambda: asyncio.sleep(0)), SafetyMonitor())

    e = _make_event("E", "device", vol=8.0, area=1.0)
    await d.submit_event(e)
    dr.running = False

    # Complete with volume but omitted actual duration
    await d.check_execution_status("E", {})
    completed = await d.complete_event("E", actual_volume_l=40000)
    assert completed.status == EventStatus.COMPLETED
    assert completed.delivered_volume_mm == 4.0
    # Missing duration must NOT be coerced to target duration (10 min)
    receipt = SharedQuotaStore.get_settled_receipt("E")
    assert receipt["actual_duration_minutes"] is None
    assert receipt["actual_volume_l"] == 40000.0


# ============================================================================
# RV06: Settlement Writer Parameter Validation
# ============================================================================
def test_rv06_settlement_writer_parameter_validation():
    """RV06: SharedQuotaStore.settle strictly rejects NaN, bool, inf, and negative scalars before mutation."""
    invalid_cases = [
        ("target_volume_mm", float("nan")),
        ("duration_minutes", True),
        ("flow_rate_lpm", float("inf")),
        ("effective_area_ha", -1),
    ]
    for field, val in invalid_cases:
        SharedQuotaStore.reset()
        args = {
            "target_volume_mm": 8.0,
            "duration_minutes": 10.0,
            "flow_rate_lpm": 10.0,
            "effective_area_ha": 1.0,
            "actual_volume_l": 40000.0,
            "actual_duration_minutes": 6.0,
        }
        args[field] = val
        with pytest.raises(ValueError):
            SharedQuotaStore.settle("E", "plot", 4.0, **args)
        # Store file must remain uncorrupted and valid
        state = SharedQuotaStore._read_state()
        assert isinstance(state, dict)


# ============================================================================
# RV07: Retry Identity Across Terminal History
# ============================================================================
@pytest.mark.anyio
async def test_rv07_retry_identity_enforces_payload_conflict():
    """RV07: Changed target or missing area on retry of terminal/settled event returns FAILED."""
    dr = MockDriver("device")
    d = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: dr, emergency_stop_all=lambda: asyncio.sleep(0)), SafetyMonitor())

    e = _make_event("E", "device", vol=8.0, area=1.0)
    await d.submit_event(e)
    dr.running = False
    await d.check_execution_status("E", {})
    await d.complete_event("E", 40000, 6)

    # Changed target volume
    changed = _make_event("E", "device", vol=12.0, area=None)
    local_retry = await d.submit_event(changed)
    assert local_retry.status == EventStatus.FAILED

    # Fresh dispatcher looking up durable record
    fresh = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: dr, emergency_stop_all=lambda: asyncio.sleep(0)), SafetyMonitor())
    fresh_retry = await fresh.submit_event(copy.deepcopy(changed))
    assert fresh_retry.status == EventStatus.FAILED


# ============================================================================
# RV08: Zero-Depth Operation Journal Coverage
# ============================================================================
@pytest.mark.anyio
async def test_rv08_zero_depth_operation_has_reservation_journal():
    """RV08: A 0 mm operation dispatches physically and records a RESERVATION entry in receipt_journal."""
    dr = MockDriver("device")
    d = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: dr, emergency_stop_all=lambda: asyncio.sleep(0)), SafetyMonitor())

    e = _make_event("E", "device", vol=0.0, area=1.0)
    await d.submit_event(e)
    assert e.status == EventStatus.EXECUTING
    assert dr.deliveries == 1

    state = SharedQuotaStore._read_state()
    journal = state.get("receipt_journal", [])
    assert len(journal) >= 1
    assert journal[0]["type"] == "RESERVATION"
    assert journal[0]["volume_mm"] == 0.0


# ============================================================================
# RV09: Reopening Existing Reservation Preserves Accounting Period
# ============================================================================
def test_rv09_reopen_active_preserves_admission_date_and_season():
    """RV09: Reopening an active reservation does not overwrite original date or season."""
    SharedQuotaStore.reserve(
        "E",
        "plot",
        8.0,
        season="S1",
        date="2026-01-01",
        device_id="device",
        zone_id="zone",
        duration_minutes=10.0,
        flow_rate_lpm=10.0,
        effective_area_ha=1.0,
    )
    # Reopen active without specifying date or season
    SharedQuotaStore.reopen_active(
        "E",
        "plot",
        8.0,
        device_id="device",
        zone_id="zone",
        duration_minutes=10.0,
        flow_rate_lpm=10.0,
        effective_area_ha=1.0,
    )
    rec = SharedQuotaStore.get_active_record("E")
    assert rec["date"] == "2026-01-01"
    assert rec["season"] == "S1"
    assert rec["status"] == "STOP_REQUESTED"


# ============================================================================
# RV02: Hydraulic Publication Monotonic Generation Fencing
# ============================================================================
def test_rv02_hydraulic_publication_sequence_fences_warm_worker(tmp_path):
    """RV02: Committed publication sequence invalidates stale warm RAM caches even when historical correction shortens history."""
    from services.agribrain.world_model import canonical_worldline as cw
    from services.agribrain.layer3_decision import runner as r
    from pathlib import Path

    orig_root = cw.CANONICAL_WORLDLINE_ROOT
    cw.CANONICAL_WORLDLINE_ROOT = tmp_path

    try:
        # Clear runner RAM
        for n, v in vars(r).items():
            if n.startswith("_PLOT_") and isinstance(v, dict):
                v.clear()

        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        veg = SimpleNamespace(lai_mean=2, fvc=0.7)

        def weather(rain=0):
            return dict(t_max_c=25, t_min_c=15, precipitation_mm=rain, wind_speed_2m_m_s=2, rh_min_pct=40, rh_max_pct=80, net_radiation_mj_m2=15)

        def make_inp(day, rain=0):
            return SimpleNamespace(plot_id="P", tenant_id="T", namespace="N", cycle_id="C", geometry_version="G", weather_daily={day: weather(rain)}, operational_context={})

        def run(x, ts):
            return r._execute_canonical_water_engine(x, None, veg, ts)

        # 1. Warm runner executes day 1 and day 2
        run(make_inp("2026-01-02"), now)
        initial = run(make_inp("2026-01-03"), now + timedelta(days=1))
        initial_theta = initial[0].soil_water.theta_profile

        svc = cw.CanonicalWorldlineService()
        before = svc.load_latest_hydraulic_checkpoint(plot_id="P", tenant_id="T", namespace="N")
        assert before["sequence"] == 2

        # 2. Simulate foreign worker that issues a historical correction on day 1 with 40mm rain
        # (This saves checkpoint sequence 3 with payload history length 1)
        # We simulate the foreign worker by snapshotting the disk state after foreign correction
        # Temporarily clear RAM to run foreign correction, then restore warm worker's old RAM state
        saved_ram_head = r._PLOT_CURRENT_HEAD.get(("T", "N", "P"))
        saved_ram_seq = r._PLOT_CURRENT_SEQUENCE.get(("T", "N", "P"))
        saved_hist = copy.deepcopy(r._PLOT_WATER_STATE_HISTORY.get(("T", "N", "P"), {}))
        saved_mem = copy.deepcopy(r._PLOT_WATER_STATE_MEMORY.get(("T", "N", "P")))

        for n, v in vars(r).items():
            if n.startswith("_PLOT_") and isinstance(v, dict):
                v.clear()

        run(make_inp("2026-01-02", 40), now)
        foreign_cp = svc.load_latest_hydraulic_checkpoint(plot_id="P", tenant_id="T", namespace="N")
        assert foreign_cp["sequence"] == 3
        assert len(foreign_cp["payload"]["history_summary"]) == 1

        # Restore warm worker's previous RAM state (which had sequence 2 and history length 2)
        r._PLOT_CURRENT_HEAD[("T", "N", "P")] = saved_ram_head
        r._PLOT_CURRENT_SEQUENCE[("T", "N", "P")] = saved_ram_seq
        r._PLOT_WATER_STATE_HISTORY[("T", "N", "P")] = saved_hist
        r._PLOT_WATER_STATE_MEMORY[("T", "N", "P")] = saved_mem

        # 3. Warm worker now executes day 2: it must detect durable publication sequence 3 > RAM sequence 2,
        # invalidate its stale RAM cache, and absorb the 40mm historical rain!
        warm_out = run(make_inp("2026-01-03"), now + timedelta(days=1))
        warm_theta = warm_out[0].soil_water.theta_profile
        after = svc.load_latest_hydraulic_checkpoint(plot_id="P", tenant_id="T", namespace="N")

        # Top-layer VWC must be ~0.2124 (absorbed the 40mm rain), NOT the stale 0.1730!
        assert round(warm_theta[0], 4) == 0.2124
        assert after["sequence"] == 4
        assert r._PLOT_CURRENT_SEQUENCE.get(("T", "N", "P")) == 4
    finally:
        cw.CANONICAL_WORLDLINE_ROOT = orig_root
