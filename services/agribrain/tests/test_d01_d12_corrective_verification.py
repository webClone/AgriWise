import asyncio
import datetime
from datetime import timezone
import math
import os
import shutil
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from services.agribrain.irrigation_runtime.actuator import (
    CommandResult,
    CommandType,
    IrrigationActuator,
    IrrigationCommand,
    ActuatorStatus,
)
from services.agribrain.irrigation_runtime.dispatcher import (
    CommandDispatcher,
    IrrigationEvent,
    EventStatus,
    WaterBudget,
)
from services.agribrain.irrigation_runtime.safety import (
    SafetyMonitor,
    SharedQuotaStore,
    CorruptedQuotaStoreError,
    safety_monitor,
)
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    ConcurrencyConflictError,
    CANONICAL_WORLDLINE_ROOT,
)
from services.agribrain.layer3_decision.runner import (
    _execute_canonical_water_engine,
    _PLOT_WATER_STATE_HISTORY,
    _PLOT_WATER_STATE_MEMORY,
    _PLOT_VEGETATION_HISTORY,
    _PLOT_MANAGEMENT_EVENTS,
    _PLOT_CURRENT_HEAD,
)
from services.agribrain.tests.test_hydraulic_persistence_and_concurrency_f09 import (
    _clear_all_memory,
)
from services.agribrain.irrigation_runtime.schemas import (
    IrrigationSystemType,
    AutomationMode,
    ActuatorRegistration,
    ActuatorCapabilities,
    DriverProtocol,
    VendorId,
    FailSafeState,
)


class MockActuatorD(IrrigationActuator):
    def __init__(self, device_id="mock_device_d", fail_fence=False, hang_start=False):
        reg = ActuatorRegistration(
            device_id=device_id,
            zone_ids=["ZONE-1"],
            plot_id="plot_1",
            farm_id="farm-1",
            protocol=DriverProtocol.MQTT,
            vendor=VendorId.GENERIC,
            model="MockModelD",
            firmware_version="1.0.0",
            capabilities=ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=50.0,
                max_duration_minutes=120.0,
            ),
            fail_safe_state=FailSafeState.NORMALLY_CLOSED,
        )
        super().__init__(reg)
        self.fail_fence = fail_fence
        self.hang_start = hang_start
        self.start_calls = 0
        self.stop_calls = 0
        self.start_applied_event = asyncio.Event()
        self.release_start_event = asyncio.Event()

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> bool:
        return True

    async def emergency_stop(self) -> CommandResult:
        if self.fail_fence:
            self._status = ActuatorStatus.ERROR
            return CommandResult(
                command_id=f"CMD-ES-{int(time.time()*1000)}",
                device_id=self.device_id,
                success=False,
                error_code="STOP_FAILED",
                error_message="Emergency stop rejected",
                timestamp=datetime.datetime.now(timezone.utc).isoformat(),
            )
        cmd = IrrigationCommand(
            command_id=f"CMD-ES-{int(time.time()*1000)}",
            command_type=CommandType.EMERGENCY_STOP,
            device_id=self.device_id,
            zone_id="ZONE-1",
            plot_id="plot_1",
        )
        return await self._execute_stop_direct(cmd)

    async def get_status(self) -> ActuatorStatus:
        return self._status

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        if command.command_type == CommandType.START_ZONE:
            self.start_calls += 1
            self.start_applied_event.set()
            if self.hang_start:
                await self.release_start_event.wait()
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=True,
                timestamp=datetime.datetime.now(timezone.utc).isoformat(),
            )
        elif command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
            self.stop_calls += 1
            if self.fail_fence and "FENCE" in command.command_id:
                return CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=False,
                    error_code="FENCE_REJECTED",
                    error_message="Fence stop was rejected by hardware",
                    timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                )
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=True,
                timestamp=datetime.datetime.now(timezone.utc).isoformat(),
            )
        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=True,
            timestamp=datetime.datetime.now(timezone.utc).isoformat(),
        )


def _make_event_d(
    event_id,
    plot_id="plot_1",
    device_id="mock_device_d",
    volume_mm=8.0,
    duration_minutes=15.0,
    status=EventStatus.QUEUED,
    actual_start=None,
    flow_rate_lpm=10.0,
    zone_id="ZONE-1",
    effective_area_ha=1.0,
):
    ev = IrrigationEvent(
        event_id=event_id,
        plot_id=plot_id,
        zone_id=zone_id,
        device_id=device_id,
        system_type=IrrigationSystemType.DRIP,
        automation_mode=AutomationMode.FULL_AUTO,
        status=status,
        target_volume_mm=volume_mm,
        target_duration_minutes=duration_minutes,
        target_flow_rate_lpm=flow_rate_lpm,
        actual_start=actual_start,
    )
    ev.effective_area_ha = effective_area_ha
    return ev


class DummyInputsD:
    def __init__(self, plot_id="P_D_TEST", operational_context=None, **kwargs):
        self.plot_id = plot_id
        self.operational_context = operational_context or {}
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_base_weather_d(d_str="2026-06-01", et0=4.5, precip=0.0):
    return {
        "date": d_str,
        "reference_et0_mm": et0,
        "et0_mm": et0,
        "t_max_c": 28.0,
        "t_min_c": 16.0,
        "precipitation_mm": precip,
        "wind_speed_2m_m_s": 2.0,
        "rh_min_pct": 35.0,
        "rh_max_pct": 75.0,
        "net_radiation_mj_m2": 16.0,
    }


def _clean_test_worldlines_d():
    wl_dir = Path(CANONICAL_WORLDLINE_ROOT)
    if wl_dir.exists():
        try:
            shutil.rmtree(wl_dir)
        except Exception:
            pass


@pytest.fixture(autouse=True)
def clean_environment():
    SharedQuotaStore.reset()
    safety_monitor.reset()
    try:
        from irrigation_runtime.safety import safety_monitor as ir_sm, SharedQuotaStore as ir_sq
        ir_sm.reset()
        ir_sq.reset()
    except Exception:
        pass
    _clean_test_worldlines_d()
    _clear_all_memory()
    yield
    SharedQuotaStore.reset()
    safety_monitor.reset()
    try:
        from irrigation_runtime.safety import safety_monitor as ir_sm, SharedQuotaStore as ir_sq
        ir_sm.reset()
        ir_sq.reset()
    except Exception:
        pass
    _clean_test_worldlines_d()
    _clear_all_memory()


# ============================================================================
# D01: Failed late STOP fencing discards live ownership
# ============================================================================
@pytest.mark.anyio
async def test_d01_failed_late_stop_fencing_retains_stop_requested_and_exposure():
    """D01: Rejected fence stop transitions actuator to ERROR, dispatcher retains STOP_REQUESTED ownership and exposure."""
    actuator = MockActuatorD("mock_device_d", fail_fence=True, hang_start=True)
    await actuator.connect()
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    event = _make_event_d("EV-D01-FENCE", volume_mm=8.0)
    dispatch_task = asyncio.create_task(dispatcher.submit_event(event))

    await actuator.start_applied_event.wait()
    # Cancel while START is in flight
    await dispatcher.cancel_event(event.event_id)

    # Now release START. Actuator sees gen incremented, sends fence stop, which fails!
    actuator.release_start_event.set()
    res = await dispatch_task

    # D01: Failed late fence stop must fail-closed to STOP_REQUESTED, retaining active monitoring & quota!
    assert res.status == EventStatus.STOP_REQUESTED
    assert event.event_id in dispatcher._active_events
    assert actuator.status == ActuatorStatus.ERROR
    state = SharedQuotaStore._read_state()
    assert state["reservations"][event.event_id]["status"] == "STOP_REQUESTED"


# ============================================================================
# D02: complete_event guarded against physically executing actuator & phase
# ============================================================================
@pytest.mark.anyio
async def test_d02_complete_event_guarded_against_executing_actuator_and_phase():
    """D02: complete_event fails closed while actuator is EXECUTING or event is not VALIDATING."""
    actuator = MockActuatorD("mock_device_d")
    await actuator.connect()
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    event = _make_event_d("EV-D02-PREMATURE", volume_mm=8.0)
    await dispatcher.submit_event(event)
    assert actuator.status == ActuatorStatus.EXECUTING
    assert event.status == EventStatus.EXECUTING

    # Premature completion attempt: must fail closed without releasing exposure
    res_premature = await dispatcher.complete_event(event.event_id, actual_volume_l=0.0)
    assert res_premature.status == EventStatus.EXECUTING
    assert not SharedQuotaStore.is_settled(event.event_id)
    res_map = SharedQuotaStore._read_state()["reservations"]
    assert event.event_id in res_map
    assert res_map[event.event_id]["volume_mm"] == 8.0

    # Actuator completes physically
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    await dispatcher.check_execution_status(event.event_id)
    assert event.status == EventStatus.VALIDATING

    # Now completion succeeds and releases reservation
    res_completed = await dispatcher.complete_event(event.event_id, actual_volume_l=80000.0, actual_duration_minutes=15.0)
    assert res_completed.status == EventStatus.COMPLETED
    assert SharedQuotaStore.is_settled(event.event_id)
    res_map_after = SharedQuotaStore._read_state()["reservations"]
    assert event.event_id not in res_map_after


# ============================================================================
# D03: The ERROR-stop path still releases unmeasured delivery
# ============================================================================
@pytest.mark.anyio
async def test_d03_error_stop_path_records_stopped_delivery_and_preserves_exposure():
    """D03: Actuator ERROR path transitions to FAILED and records stopped delivery rather than releasing quota."""
    actuator = MockActuatorD("mock_device_d")
    await actuator.connect()
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    event = _make_event_d("EV-D03-ERROR", volume_mm=8.0)
    budget = WaterBudget(plot_id="plot_1", season="2026-S", season_remaining_mm=10.0, daily_remaining_mm=10.0)
    await dispatcher.submit_event(event, budget=budget)

    # Inject actuator ERROR state during execution
    actuator._status = ActuatorStatus.ERROR
    await dispatcher.check_execution_status(event.event_id)
    assert event.status == EventStatus.FAILED

    # Stopped delivery exposure must be recorded (not zeroed out)
    assert SharedQuotaStore.is_stopped(event.event_id)
    stopped_rec = SharedQuotaStore.get_stopped_receipt(event.event_id)
    assert stopped_rec is not None
    assert stopped_rec["target_volume_mm"] == 8.0

    # A subsequent 8 mm event against the remaining 10 mm budget must be BLOCKED
    event2 = _make_event_d("EV-D03-SECOND", volume_mm=8.0)
    res2 = await dispatcher.submit_event(event2, budget=budget)
    assert res2.status == EventStatus.FAILED
    assert "QUOTA" in (res2.failure_reason or "").upper()


# ============================================================================
# D04: Quota integrity validates schema, aggregates, and markers
# ============================================================================
def test_d04_quota_integrity_rollups_scalar_types_and_markers():
    """D04: Contradictory rollups and invalid scalar types (negative, bool, NaN) raise CorruptedQuotaStoreError."""
    # Probe A: Valid receipt with cleared aggregates fails closed
    SharedQuotaStore.settle("EV-D04-A", "plot_1", 8.0, season="2026", actual_duration_minutes=15.0, effective_area_ha=1.0)
    state = SharedQuotaStore._read_state()
    # Clear aggregate maps
    state["settled_daily"] = {}
    state["settled_season"] = {}
    state["settled_plot_total"] = {}
    SharedQuotaStore._write_state(state)

    with pytest.raises(CorruptedQuotaStoreError):
        SharedQuotaStore._read_state()

    SharedQuotaStore.reset()

    # Probe B: Reservation duration = -1 or flow = True fails closed
    state = SharedQuotaStore._read_state()
    state["reservations"]["EV-D04-B"] = {
        "plot_id": "plot_1",
        "device_id": "d1",
        "zone_id": "z1",
        "volume_mm": 5.0,
        "duration_minutes": -1.0,
        "flow_rate_lpm": True,
        "status": "DISPATCHING",
        "date": "2026-06-01",
        "season": "2026",
    }
    SharedQuotaStore._write_state(state)
    with pytest.raises(CorruptedQuotaStoreError):
        SharedQuotaStore._read_state()

    SharedQuotaStore.reset()

    # Probe C: Established marker write failure is not swallowed; established loss fails closed
    marker = SharedQuotaStore._established_marker_file()
    marker.unlink(missing_ok=True)
    with patch.object(Path, "write_text", side_effect=OSError("Disk write error")):
        with pytest.raises(OSError):
            SharedQuotaStore._write_state(SharedQuotaStore._read_state())

    # And if marker exists but ledger is missing, it raises CorruptedQuotaStoreError rather than silently creating empty state
    SharedQuotaStore.reset()
    assert marker.exists()
    store_file = SharedQuotaStore._store_file()
    store_file.unlink(missing_ok=True)
    with pytest.raises(CorruptedQuotaStoreError, match="disappeared/deleted"):
        SharedQuotaStore._read_state()


# ============================================================================
# D05: Durable operation admission remains unconditional when budget=None
# ============================================================================
@pytest.mark.anyio
async def test_d05_durable_admission_unconditional_when_budget_none():
    """D05: Submitting with budget=None calls atomic_check_and_reserve; concurrent submission joins active execution."""
    actuator = MockActuatorD("mock_device_d")
    await actuator.connect()
    dispatcher1 = CommandDispatcher()
    dispatcher1.register_actuator(actuator)

    event = _make_event_d("EV-D05-NOBUDGET", volume_mm=0.0)
    res1 = await dispatcher1.submit_event(event, budget=None)
    assert res1.status == EventStatus.EXECUTING
    assert actuator.start_calls == 1

    # Second dispatcher submits exact same event with budget=None
    dispatcher2 = CommandDispatcher()
    dispatcher2.register_actuator(actuator)
    res2 = await dispatcher2.submit_event(event, budget=None)
    # Joins active execution: physical START count remains 1
    assert res2.status == EventStatus.EXECUTING
    assert actuator.start_calls == 1


# ============================================================================
# D06: Incomplete payload binding (zero values and effective area)
# ============================================================================
@pytest.mark.anyio
async def test_d06_payload_binding_checks_zero_values_and_effective_area():
    """D06: Changed duration/flow and changed effective area cannot evade conflict checks."""
    actuator = MockActuatorD("mock_device_d")
    await actuator.connect()
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    event1 = _make_event_d("EV-D06-PAYLOAD", volume_mm=8.0, duration_minutes=15.0, flow_rate_lpm=10.0, effective_area_ha=1.0)
    await dispatcher.submit_event(event1)
    assert actuator.start_calls == 1

    # Second submission with changed effective area (2.0 ha vs 1.0 ha) must be REJECTED as payload conflict
    event2 = _make_event_d("EV-D06-PAYLOAD", volume_mm=8.0, duration_minutes=15.0, flow_rate_lpm=10.0, effective_area_ha=2.0)
    res2 = await dispatcher.submit_event(event2)
    assert res2.status == EventStatus.FAILED
    assert "CONFLICT" in (res2.failure_reason or "").upper()
    assert actuator.start_calls == 1


# ============================================================================
# D07: Stale durable phases and mark_unsettled
# ============================================================================
def test_d07_durable_phases_and_mark_unsettled():
    """D07: mark_unsettled records VALIDATING and UNSETTLED; update_status synchronizes phases."""
    SharedQuotaStore.reserve("EV-D07", "plot_1", 8.0, season="2026")
    state = SharedQuotaStore._read_state()
    assert state["reservations"]["EV-D07"]["status"] == "RESERVED"

    SharedQuotaStore.update_status("EV-D07", "STOP_REQUESTED")
    state = SharedQuotaStore._read_state()
    assert state["reservations"]["EV-D07"]["status"] == "STOP_REQUESTED"

    SharedQuotaStore.mark_unsettled("EV-D07")
    state = SharedQuotaStore._read_state()
    res = state["reservations"]["EV-D07"]
    assert res["status"] == "VALIDATING"
    assert res["accounting_status"] == "UNSETTLED"


# ============================================================================
# D08: Receipt reconciliation preserves period and prevents double counting
# ============================================================================
def test_d08_receipt_reconciliation_stopped_then_settled_no_double_count():
    """D08: Stopped 8 mm followed by settled 3 mm reconciles prior stopped exposure so aggregate is 3 mm."""
    # 1. Record stopped delivery of 8 mm
    SharedQuotaStore.record_stopped_delivery("EV-D08", "plot_1", 8.0, season="2026", date="2026-06-01")
    state = SharedQuotaStore._read_state()
    assert state["stopped_receipts"]["EV-D08"]["target_volume_mm"] == 8.0
    assert SharedQuotaStore.get_settled("plot_1") == 8.0
    assert state["settled_season"]["plot_1:2026"] == 8.0

    # 2. Subsequent settlement of 3 mm delivery for same event reconciles prior stopped exposure
    SharedQuotaStore.settle("EV-D08", "plot_1", 3.0, season="2026", date="2026-06-01", actual_duration_minutes=10.0, effective_area_ha=1.0)
    assert SharedQuotaStore.is_settled("EV-D08")
    # Total aggregate must be 3.0 mm (not 11.0 mm!)
    assert SharedQuotaStore.get_settled("plot_1") == 3.0
    state2 = SharedQuotaStore._read_state()
    assert state2["settled_season"]["plot_1:2026"] == 3.0

    # 3. Conflicting settlement retry with different amount is rejected
    with pytest.raises(ValueError, match="Conflicting settlement retry"):
        SharedQuotaStore.settle("EV-D08", "plot_1", 5.0, season="2026")


# ============================================================================
# D09: Measurement missingness (explicit 0 L & invalid duration)
# ============================================================================
@pytest.mark.anyio
async def test_d09_explicit_zero_litres_and_invalid_duration():
    """D09: Explicit 0 L settles 0.0 mm without area; invalid duration fails closed without coercion to 0.0."""
    actuator = MockActuatorD("mock_device_d")
    await actuator.connect()
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    # Test 1: Explicit 0 L with missing effective_area_ha settles 0.0 mm
    ev_zero = _make_event_d("EV-D09-ZERO", volume_mm=8.0, effective_area_ha=None)
    await dispatcher.submit_event(ev_zero)
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    await dispatcher.check_execution_status(ev_zero.event_id)
    assert ev_zero.status == EventStatus.VALIDATING
    res_zero = await dispatcher.complete_event(ev_zero.event_id, actual_volume_l=0.0)
    assert res_zero.status == EventStatus.COMPLETED
    assert res_zero.delivered_volume_mm == 0.0

    # Test 2: Invalid duration (NaN, Inf, bool) fails closed
    ev_nan = _make_event_d("EV-D09-NAN-DUR", volume_mm=8.0, effective_area_ha=1.0)
    await dispatcher.submit_event(ev_nan)
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    await dispatcher.check_execution_status(ev_nan.event_id)
    assert ev_nan.status == EventStatus.VALIDATING
    res_nan = await dispatcher.complete_event(ev_nan.event_id, actual_volume_l=40000.0, actual_duration_minutes=float("nan"))
    assert res_nan.status == EventStatus.FAILED
    assert "Invalid settlement duration" in res_nan.failure_reason


# ============================================================================
# D10: Incomplete receipt replay restores duration and support
# ============================================================================
def test_d10_receipt_replay_restores_duration_and_support():
    """D10: Settled receipt replay preserves actual_duration_minutes and effective_area_ha."""
    SharedQuotaStore.settle(
        "EV-D10",
        "plot_1",
        5.0,
        season="2026",
        actual_duration_minutes=25.0,
        effective_area_ha=1.5,
    )
    rcpt = SharedQuotaStore.get_settled_receipt("EV-D10")
    assert rcpt is not None
    assert rcpt["actual_duration_minutes"] == 25.0
    assert rcpt["effective_area_ha"] == 1.5
    assert rcpt["volume_mm"] == 5.0


# ============================================================================
# D11: Rollback publication race protection
# ============================================================================
def test_d11_rollback_race_does_not_overwrite_newer_winner():
    """D11: If a newer winner commits to disk/RAM, older worker's rollback does not overwrite newer RAM state."""
    plot_id = "P_D11_ROLLBACK"
    tenant = "t_d11"
    ns = "default"
    w1 = _make_base_weather_d("2026-06-01", et0=4.0)
    w2 = _make_base_weather_d("2026-06-02", et0=4.0)
    ts1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    ts2 = datetime.datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)

    # Base commit Day 1
    inp1 = DummyInputsD(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1, "2026-06-02": w2},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    _execute_canonical_water_engine(inp1, None, None, ts1)

    cw = CanonicalWorldlineService()
    base_head = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    base_head_id = base_head["checkpoint_id"]

    # Winner commits Day 2 to disk and RAM
    inp_winner = DummyInputsD(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1, "2026-06-02": {**w2, "precipitation_mm": 10.0}},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    s_win, _ = _execute_canonical_water_engine(inp_winner, None, None, ts2)
    win_head = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    win_head_id = win_head["checkpoint_id"]
    win_theta = list(s_win.soil_water.theta_profile)

    # Loser was running concurrently, having read base_head before winner committed win_head.
    call_count = 0
    orig_load = CanonicalWorldlineService.load_latest_hydraulic_checkpoint

    def load_base_first_call(self_svc, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return base_head
        return orig_load(self_svc, *args, **kwargs)

    with patch.object(CanonicalWorldlineService, "load_latest_hydraulic_checkpoint", new=load_base_first_call):
        with patch.object(
            CanonicalWorldlineService,
            "save_hydraulic_checkpoint",
            side_effect=ConcurrencyConflictError("CAS mismatch: competitor committed"),
        ):
            inp_loser = DummyInputsD(
                plot_id=plot_id,
                tenant_id=tenant,
                namespace=ns,
                weather_daily={"2026-06-01": w1, "2026-06-02": {**w2, "precipitation_mm": 5.0}},
                operational_context={"tenant_id": tenant, "namespace": ns},
            )
            with pytest.raises(ConcurrencyConflictError):
                _execute_canonical_water_engine(inp_loser, None, None, ts2)

    # After loser's rollback, RAM must NOT be reset to Day 1: it must preserve Winner's Day 2!
    scope_key = (tenant, ns, plot_id)
    cached_head = _PLOT_CURRENT_HEAD.get(scope_key)
    assert cached_head == win_head_id

    cached_soil, _ = _PLOT_WATER_STATE_MEMORY.get(scope_key, (None, None))
    assert cached_soil is not None
    assert list(cached_soil.theta_profile) == pytest.approx(win_theta, rel=1e-4)


# ============================================================================
# D12: Candidate evidence isolation
# ============================================================================
def test_d12_candidate_evidence_isolation_before_cas_commit():
    """D12: Uncommitted candidate events do not leak into shared registries before CAS commit."""
    plot_id = "P_D12_ISOLATE"
    tenant = "t_d12"
    ns = "default"
    w1 = _make_base_weather_d("2026-06-01", et0=4.0)
    w2 = _make_base_weather_d("2026-06-02", et0=4.0)
    ts1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    ts2 = datetime.datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)

    # Base commit Day 1
    inp1 = DummyInputsD(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    _execute_canonical_water_engine(inp1, None, None, ts1)

    scope_key = (tenant, ns, plot_id)
    events_before = dict(_PLOT_MANAGEMENT_EVENTS.get(scope_key, {}))

    # Day 2 with an uncommitted 15 mm irrigation event where save fails CAS
    irr_event = {
        "id": "EV-D12-IRR",
        "date": "2026-06-02",
        "type": "irrigation",
        "amount_mm": 15.0,
        "status": "applied",
    }
    inp2 = DummyInputsD(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1, "2026-06-02": w2},
        management_events=[irr_event],
        operational_context={"tenant_id": tenant, "namespace": ns, "management_events": [irr_event]},
    )

    with patch.object(
        CanonicalWorldlineService,
        "save_hydraulic_checkpoint",
        side_effect=ConcurrencyConflictError("Injected CAS failure"),
    ):
        with pytest.raises(ConcurrencyConflictError):
            _execute_canonical_water_engine(inp2, None, None, ts2)

    # The uncommitted 15 mm event must NOT be in _PLOT_MANAGEMENT_EVENTS
    events_after = _PLOT_MANAGEMENT_EVENTS.get(scope_key, {})
    assert "EV-D12-IRR" not in events_after


# ============================================================================
# Q01: Historical query preserves downstream calculation identity
# ============================================================================
def test_q01_historical_query_preserves_downstream_checkpoint_identity():
    """Q01: Intervening historical query rehydrates full history so subsequent run preserves checkpoint ID."""
    plot_id = "P_Q01_REPLAY"
    tenant = "t_q01"
    ns = "default"
    w1 = _make_base_weather_d("2026-06-01", et0=4.0)
    w2 = _make_base_weather_d("2026-06-02", et0=4.0)
    ts1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    ts2 = datetime.datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)

    # Day 1
    inp1 = DummyInputsD(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1, "2026-06-02": w2},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    s1, _ = _execute_canonical_water_engine(inp1, None, None, ts1)
    cw = CanonicalWorldlineService()
    cp1 = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    cp1_id = cp1["checkpoint_id"]

    # Day 2
    inp2 = DummyInputsD(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1, "2026-06-02": w2},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    s2, _ = _execute_canonical_water_engine(inp2, None, None, ts2)
    cp2 = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    cp2_id = cp2["checkpoint_id"]
    theta2 = list(s2.soil_water.theta_profile)

    # Historical query for Day 1
    s_q, _ = _execute_canonical_water_engine(inp1, None, None, ts1)
    head_after_q = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    assert head_after_q["checkpoint_id"] == cp2_id

    # Subsequent re-evaluation of Day 2: must yield identical theta2 and preserve cp2_id
    s2_again, _ = _execute_canonical_water_engine(inp2, None, None, ts2)
    assert list(s2_again.soil_water.theta_profile) == pytest.approx(theta2, rel=1e-5)
    head_after_again = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    assert head_after_again["checkpoint_id"] == cp2_id
