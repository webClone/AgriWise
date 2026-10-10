import asyncio
import datetime
from datetime import timezone
import math
import os
import shutil
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

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


class MockActuator(IrrigationActuator):
    def __init__(self, device_id="mock_device", hang_start=False):
        reg = ActuatorRegistration(
            device_id=device_id,
            zone_ids=["ZONE-1"],
            plot_id="plot_1",
            farm_id="farm-1",
            protocol=DriverProtocol.MQTT,
            vendor=VendorId.GENERIC,
            model="MockModel",
            firmware_version="1.0.0",
            capabilities=ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=50.0,
                max_duration_minutes=120.0,
            ),
            fail_safe_state=FailSafeState.NORMALLY_CLOSED,
        )
        super().__init__(reg)
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


def _make_event(
    event_id,
    plot_id="plot_1",
    device_id="mock_device",
    volume_mm=8.0,
    duration_minutes=15.0,
    status=EventStatus.QUEUED,
    actual_start=None,
    flow_rate_lpm=10.0,
    zone_id="ZONE-1",
):
    return IrrigationEvent(
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


class DummyInputs:
    def __init__(self, plot_id="P_V_TEST", operational_context=None, **kwargs):
        self.plot_id = plot_id
        self.operational_context = operational_context or {}
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_base_weather(d_str="2026-06-01", et0=4.5, precip=0.0):
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


def _clean_test_worldlines():
    for test_dir in CANONICAL_WORLDLINE_ROOT.glob("t_c*"):
        if test_dir.is_dir():
            shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_shared_quota():
    SharedQuotaStore.reset()
    safety_monitor.reset()
    try:
        from irrigation_runtime.safety import safety_monitor as ir_sm, SharedQuotaStore as ir_sq
        ir_sm.reset()
        ir_sq.reset()
    except Exception:
        pass
    _clean_test_worldlines()
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
    _clean_test_worldlines()
    _clear_all_memory()


# ============================================================================
# C01: Pending START cancellation sends physical STOP
# ============================================================================
@pytest.mark.anyio
async def test_c01_pending_start_cancellation_sends_physical_stop():
    """C01: While START awaits ACK, cancellation must send physical STOP rather than returning ALREADY_STOPPED."""
    actuator = MockActuator(hang_start=True)
    await actuator.connect()
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    event = _make_event("EV-C01", volume_mm=8.0)
    dispatch_task = asyncio.create_task(dispatcher.submit_event(event))

    await actuator.start_applied_event.wait()
    assert actuator.start_calls == 1
    assert actuator.pending_command is not None

    # Cancel while START is still in flight
    cancelled_event = await dispatcher.cancel_event(event.event_id)
    assert cancelled_event is not None
    assert cancelled_event.status == EventStatus.CANCELLED
    # STOP must have been physically sent!
    assert actuator.stop_calls >= 1

    # Release delayed START
    actuator.release_start_event.set()
    await dispatch_task

    # Event must NOT be revived to EXECUTING
    assert event.status == EventStatus.CANCELLED
    assert actuator.status == ActuatorStatus.ONLINE


# ============================================================================
# C02: Late START completion does not revive finalized operation
# ============================================================================
@pytest.mark.anyio
async def test_c02_late_start_completion_does_not_revive_executing():
    """C02: A delayed START completion after watchdog/cancel must return PREEMPTED_BY_STOP and not revive EXECUTING."""
    actuator = MockActuator(hang_start=True)
    await actuator.connect()

    start_cmd = IrrigationCommand(
        command_id="CMD-START-C02",
        command_type=CommandType.START_ZONE,
        device_id=actuator.device_id,
        zone_id="ZONE-1",
        plot_id="plot_1",
        volume_mm=8.0,
        duration_minutes=15.0,
    )
    start_task = asyncio.create_task(actuator.execute_with_safety(start_cmd))
    await actuator.start_applied_event.wait()

    # Preempt with emergency stop
    stop_res = await actuator.emergency_stop()
    assert stop_res.success
    assert actuator.status == ActuatorStatus.ONLINE

    # Now release late START completion
    actuator.release_start_event.set()
    res = await start_task

    # Late completion is preempted and does not revive EXECUTING
    assert res.error_code == "PREEMPTED_BY_STOP"
    assert actuator.status == ActuatorStatus.ONLINE
    assert actuator.active_command is None


# ============================================================================
# C03: Quota-store schema validation and established-store loss
# ============================================================================
def test_c03_quota_store_integrity_validates_amounts_and_missing_store():
    """C03: Corrupt values (NaN, negative, bool) or loss of established file raise CorruptedQuotaStoreError."""
    budget = WaterBudget(plot_id="p1", season="season_2026", daily_remaining_mm=10.0, season_remaining_mm=50.0)

    # Establish store first
    vio = SharedQuotaStore.atomic_check_and_reserve(
        plot_id="p1", requested_volume_mm=4.0, budget=budget, event_id="E-INIT"
    )
    assert vio is None

    # Test nested negative amount
    state = SharedQuotaStore._read_state()
    state["reservations"]["E-INIT"]["volume_mm"] = -8.0
    SharedQuotaStore._write_state(state)
    with pytest.raises(CorruptedQuotaStoreError):
        SharedQuotaStore._read_state()
    vio_neg = SharedQuotaStore.atomic_check_and_reserve(
        plot_id="p1", requested_volume_mm=4.0, budget=budget, event_id="E-2"
    )
    assert vio_neg is not None
    assert vio_neg.action_taken == "BLOCK"

    # Test nested NaN amount (write raw JSON string with NaN)
    p = SharedQuotaStore._store_file()
    with open(p, "w", encoding="utf-8") as f:
        f.write('{"reservations": {"E-INIT": {"volume_mm": NaN, "plot_id": "p1"}}, "settled_daily": {}}')
    with pytest.raises(CorruptedQuotaStoreError):
        SharedQuotaStore._read_state()
    vio_nan = SharedQuotaStore.atomic_check_and_reserve(
        plot_id="p1", requested_volume_mm=4.0, budget=budget, event_id="E-2"
    )
    assert vio_nan is not None
    assert vio_nan.action_taken == "BLOCK"

    # Test missing established store file
    SharedQuotaStore.reset()
    SharedQuotaStore.atomic_check_and_reserve(
        plot_id="p1", requested_volume_mm=4.0, budget=budget, event_id="E-INIT2"
    )
    # Remove only the store json file while established marker remains
    if p.exists():
        p.unlink()
    with pytest.raises(CorruptedQuotaStoreError):
        SharedQuotaStore._read_state()
    vio_lost = SharedQuotaStore.atomic_check_and_reserve(
        plot_id="p1", requested_volume_mm=4.0, budget=budget, event_id="E-3"
    )
    assert vio_lost is not None
    assert vio_lost.action_taken == "BLOCK"


# ============================================================================
# C04: Stopped delivery accounting conserves unmeasured exposure
# ============================================================================
@pytest.mark.anyio
async def test_c04_stopped_delivery_accounting_conserves_unmeasured_exposure():
    """C04: When an operation is stopped without delivered measurement, conservative target exposure is retained."""
    actuator = MockActuator()
    await actuator.connect()
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    budget = WaterBudget(plot_id="plot_1", season="season_2026", daily_remaining_mm=10.0, season_remaining_mm=50.0)
    event1 = _make_event("EV-C04-1", volume_mm=8.0)
    await dispatcher.submit_event(event1, budget=budget)
    assert event1.status == EventStatus.EXECUTING

    # Cancel without delivered depth measurement
    await dispatcher.cancel_event(event1.event_id)
    assert event1.status == EventStatus.CANCELLED

    # Check that conservative target volume (8 mm) was accounted in settled total
    settled_p = SharedQuotaStore.get_settled("plot_1")
    assert settled_p >= 8.0

    # Another 8 mm command must be blocked against the 10 mm budget
    event2 = _make_event("EV-C04-2", volume_mm=8.0)
    await dispatcher.submit_event(event2, budget=budget)
    assert event2.status == EventStatus.FAILED
    assert actuator.start_calls == 1  # No second START was issued!


# ============================================================================
# C05: Stopped receipts provide terminal idempotency
# ============================================================================
@pytest.mark.anyio
async def test_c05_stopped_receipts_terminal_idempotency():
    """C05: Exact retries of stopped events issue 0 new STARTs, and retrying stopped receipts does not double debit."""
    actuator = MockActuator()
    await actuator.connect()
    disp1 = CommandDispatcher()
    disp1.register_actuator(actuator)

    event = _make_event("EV-C05", volume_mm=8.0)
    await disp1.submit_event(event)
    await disp1.cancel_event(event.event_id)
    assert actuator.start_calls == 1

    # Fresh dispatcher replaying the cancelled event
    disp2 = CommandDispatcher()
    disp2.register_actuator(actuator)
    replay_event = _make_event("EV-C05", volume_mm=8.0)
    res = await disp2.submit_event(replay_event)
    assert res.status == EventStatus.CANCELLED
    assert actuator.start_calls == 1  # ZERO duplicate STARTs!

    # Idempotent record_stopped_delivery retry
    SharedQuotaStore.record_stopped_delivery(
        event_id="E-STOPPED",
        plot_id="plot_1",
        target_volume_mm=8.0,
        delivered_volume_mm=3.0,
    )
    s1 = SharedQuotaStore.get_settled("plot_1")
    # Retry identical record
    SharedQuotaStore.record_stopped_delivery(
        event_id="E-STOPPED",
        plot_id="plot_1",
        target_volume_mm=8.0,
        delivered_volume_mm=3.0,
    )
    s2 = SharedQuotaStore.get_settled("plot_1")
    assert s1 == s2  # Does NOT double debit to 6.0 mm!


# ============================================================================
# C06: Payload binding and zero-depth claims
# ============================================================================
@pytest.mark.anyio
async def test_c06_payload_binding_and_zero_depth_claims():
    """C06: Conflict on duration, zone, or flow rate is rejected; zero-depth operations claim atomic reservation."""
    actuator = MockActuator()
    await actuator.connect()
    disp1 = CommandDispatcher()
    disp1.register_actuator(actuator)

    event1 = _make_event("EV-C06", volume_mm=8.0, duration_minutes=15.0, flow_rate_lpm=10.0, zone_id="ZONE-1")
    await disp1.submit_event(event1)

    # Fresh dispatcher with conflicting zone
    disp2 = CommandDispatcher()
    disp2.register_actuator(actuator)
    ev_conflict_zone = _make_event("EV-C06", volume_mm=8.0, duration_minutes=15.0, flow_rate_lpm=10.0, zone_id="OTHER-ZONE")
    res_zone = await disp2.submit_event(ev_conflict_zone)
    assert res_zone.status == EventStatus.FAILED

    # Fresh dispatcher with conflicting duration
    ev_conflict_dur = _make_event("EV-C06", volume_mm=8.0, duration_minutes=30.0, flow_rate_lpm=10.0, zone_id="ZONE-1")
    res_dur = await disp2.submit_event(ev_conflict_dur)
    assert res_dur.status == EventStatus.FAILED

    # Fresh dispatcher with conflicting flow rate
    ev_conflict_flow = _make_event("EV-C06", volume_mm=8.0, duration_minutes=15.0, flow_rate_lpm=25.0, zone_id="ZONE-1")
    res_flow = await disp2.submit_event(ev_conflict_flow)
    assert res_flow.status == EventStatus.FAILED

    # Finish event1 so actuator is idle for zero-depth testing
    await disp1.complete_event(event1.event_id)
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None

    # Zero-depth claim: two dispatchers submit identical zero-depth event
    budget = WaterBudget(plot_id="plot_1", season="season_2026", daily_remaining_mm=10.0, season_remaining_mm=50.0)
    ev_zero1 = _make_event("EV-ZERO", volume_mm=0.0)
    ev_zero2 = _make_event("EV-ZERO", volume_mm=0.0)
    starts_before = actuator.start_calls
    await disp1.submit_event(ev_zero1, budget=budget)
    await disp2.submit_event(ev_zero2, budget=budget)
    assert actuator.start_calls == starts_before + 1  # Only 1 START issued!


# ============================================================================
# C07: Duplicate reservation does not report false EXECUTING before ACK
# ============================================================================
@pytest.mark.anyio
async def test_c07_reservation_does_not_promote_to_executing_before_ack():
    """C07: Duplicate arriving before ACK returns DISPATCHING; if original fails, duplicate observes STOP_REQUESTED."""
    actuator = MockActuator(hang_start=True)
    await actuator.connect()
    disp1 = CommandDispatcher()
    disp1.register_actuator(actuator)

    ev1 = _make_event("EV-C07", volume_mm=8.0)
    t1 = asyncio.create_task(disp1.submit_event(ev1))
    await actuator.start_applied_event.wait()

    # Duplicate submission from fresh dispatcher before ACK
    disp2 = CommandDispatcher()
    disp2.register_actuator(actuator)
    ev_dup = _make_event("EV-C07", volume_mm=8.0)
    res_dup = await disp2.submit_event(ev_dup)

    # Must NOT report EXECUTING before ACK!
    assert res_dup.status == EventStatus.DISPATCHING

    # Release delayed START
    actuator.release_start_event.set()
    await t1


# ============================================================================
# C08: Settlement validation and valid zero litres conversion
# ============================================================================
@pytest.mark.anyio
async def test_c08_settlement_validation_and_zero_litres_conversion():
    """C08: Invalid settlement inputs (Inf, NaN, bool) fail closed; explicit 0 L settles 0.0 mm with area."""
    actuator = MockActuator()
    await actuator.connect()
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    # Test 1: Premature completion while actuator is executing fails closed (D02)
    ev_premature = _make_event("EV-PREMATURE", volume_mm=8.0)
    ev_premature.effective_area_ha = 1.0
    await dispatcher.submit_event(ev_premature)
    res_premature = await dispatcher.complete_event(ev_premature.event_id, actual_volume_l=0.0)
    assert res_premature.status == EventStatus.EXECUTING
    assert not SharedQuotaStore.is_settled(ev_premature.event_id)

    # Test 2: Infinite litres in VALIDATING fails closed
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    ev_inf = _make_event("EV-INF", volume_mm=8.0)
    ev_inf.effective_area_ha = 1.0
    await dispatcher.submit_event(ev_inf)
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    await dispatcher.check_execution_status(ev_inf.event_id)
    assert ev_inf.status == EventStatus.VALIDATING
    res_inf = await dispatcher.complete_event(ev_inf.event_id, actual_volume_l=float("inf"))
    assert res_inf.status == EventStatus.FAILED
    assert not SharedQuotaStore.is_settled(ev_inf.event_id)

    # Test 3: Boolean area in VALIDATING fails closed
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    ev_bool_area = _make_event("EV-BOOL-A", volume_mm=8.0)
    ev_bool_area.effective_area_ha = True
    await dispatcher.submit_event(ev_bool_area)
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    await dispatcher.check_execution_status(ev_bool_area.event_id)
    assert ev_bool_area.status == EventStatus.VALIDATING
    res_bool = await dispatcher.complete_event(ev_bool_area.event_id, actual_volume_l=80000.0)
    assert res_bool.status == EventStatus.FAILED

    # Test 4: Explicit 0 L settles 0.0 mm
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    ev_zero_l = _make_event("EV-ZERO-L", volume_mm=8.0)
    ev_zero_l.effective_area_ha = 1.0
    await dispatcher.submit_event(ev_zero_l)
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    await dispatcher.check_execution_status(ev_zero_l.event_id)
    assert ev_zero_l.status == EventStatus.VALIDATING
    res_zero = await dispatcher.complete_event(ev_zero_l.event_id, actual_volume_l=0.0)
    assert res_zero.status == EventStatus.COMPLETED
    assert res_zero.delivered_volume_mm == 0.0
    rcpt = SharedQuotaStore.get_settled_receipt(ev_zero_l.event_id)
    assert rcpt["volume_mm"] == 0.0

    # Test 5: 160,000 L / 1 ha produces 16.0 mm
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    ev_16 = _make_event("EV-16MM", volume_mm=8.0)
    ev_16.effective_area_ha = 1.0
    await dispatcher.submit_event(ev_16)
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    await dispatcher.check_execution_status(ev_16.event_id)
    assert ev_16.status == EventStatus.VALIDATING
    res_16 = await dispatcher.complete_event(ev_16.event_id, actual_volume_l=160000.0)
    assert res_16.status == EventStatus.COMPLETED
    assert res_16.delivered_volume_mm == 16.0


# ============================================================================
# C09: Settled identity compares commanded target and restores observations
# ============================================================================
@pytest.mark.anyio
async def test_c09_command_vs_outcome_identity_and_observation_rehydration():
    """C09: An 8 mm command delivering 4 mm can be retried idempotently, restoring original litre measurement."""
    actuator = MockActuator()
    await actuator.connect()
    disp1 = CommandDispatcher()
    disp1.register_actuator(actuator)

    ev = _make_event("EV-C09", volume_mm=8.0)
    ev.effective_area_ha = 1.0
    await disp1.submit_event(ev)
    actuator._status = ActuatorStatus.ONLINE
    await disp1.check_execution_status(ev.event_id)
    assert ev.status == EventStatus.VALIDATING
    await disp1.complete_event(ev.event_id, actual_volume_l=40000.0)

    # Receipt records target=8mm, delivered=4mm, actual_l=40000
    rcpt = SharedQuotaStore.get_settled_receipt(ev.event_id)
    assert rcpt["target_volume_mm"] == 8.0
    assert rcpt["volume_mm"] == 4.0
    assert rcpt["actual_volume_l"] == 40000.0

    # Fresh dispatcher retrying the original 8 mm command
    disp2 = CommandDispatcher()
    disp2.register_actuator(actuator)
    retry_ev = _make_event("EV-C09", volume_mm=8.0)
    res = await disp2.submit_event(retry_ev)

    assert res.status == EventStatus.COMPLETED
    assert res.target_volume_mm == 8.0
    assert res.delivered_volume_mm == 4.0
    assert res.actual_volume_l == 40000.0


# ============================================================================
# C10: Cold historical replay preserves theta and head sequence
# ============================================================================
def test_c10_cold_historical_replay_preserves_state_and_head_sequence():
    """C10: Replaying Day 1 after Day 2 exists integrates from Day 1 prior, preserves theta, and does not advance head."""
    plot_id = "P_C10_HISTORICAL"
    tenant = "t_c10"
    ns = "default"

    w1 = _make_base_weather("2026-06-01", et0=5.0)
    w2 = _make_base_weather("2026-06-02", et0=3.0)
    ts1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    ts2 = datetime.datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)

    inp1 = DummyInputs(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1, "2026-06-02": w2},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )

    # Step 1: Day 1
    s1, _ = _execute_canonical_water_engine(inp1, None, None, ts1)
    assert s1 is not None
    theta1 = list(s1.soil_water.theta_profile)

    # Step 2: Day 2
    inp2 = DummyInputs(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1, "2026-06-02": w2},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    s2, _ = _execute_canonical_water_engine(inp2, None, None, ts2)
    assert s2 is not None

    cw = CanonicalWorldlineService()
    head_before = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    assert head_before["payload"]["step_key"] == "2026-06-02"
    seq_before = head_before["sequence"]
    assert seq_before == 2

    # Clear RAM completely (cold restart)
    _clear_all_memory()

    # Replay Day 1 (June 1)
    s_replay, _ = _execute_canonical_water_engine(inp1, None, None, ts1)
    assert s_replay is not None
    theta_replay = list(s_replay.soil_water.theta_profile)

    # Top-layer VWC must match original Day 1 theta!
    assert theta_replay == pytest.approx(theta1, rel=1e-4)

    # Durable head must NOT be replaced by historical query, sequence must NOT advance!
    head_after = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    assert head_after["payload"]["step_key"] == "2026-06-02"
    assert head_after["sequence"] == 2


# ============================================================================
# C11: Concurrent RAM rollback preserves winning worker's RAM state
# ============================================================================
def test_c11_concurrent_ram_rollback_preserves_winning_worker_ram():
    """C11: A losing CAS worker's rollback must not wipe out the concurrent winning worker's RAM state."""
    plot_id = "P_C11_ROLLBACK"
    tenant = "t_c11"
    ns = "default"
    w1 = _make_base_weather("2026-06-01", et0=4.0)
    w2 = _make_base_weather("2026-06-02", et0=4.0)
    ts1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    ts2 = datetime.datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)

    # Base commit Day 1
    inp1 = DummyInputs(plot_id=plot_id, tenant_id=tenant, namespace=ns,
                       weather_daily={"2026-06-01": w1, "2026-06-02": w2},
                       operational_context={"tenant_id": tenant, "namespace": ns})
    _execute_canonical_water_engine(inp1, None, None, ts1)

    cw = CanonicalWorldlineService()
    base_head = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    base_head_id = base_head["checkpoint_id"]

    # Winner commits Day 2 to disk and RAM
    inp_winner = DummyInputs(plot_id=plot_id, tenant_id=tenant, namespace=ns,
                              weather_daily={"2026-06-01": w1, "2026-06-02": {**w2, "precipitation_mm": 10.0}},
                              operational_context={"tenant_id": tenant, "namespace": ns})
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
        with patch.object(CanonicalWorldlineService, "save_hydraulic_checkpoint",
                          side_effect=ConcurrencyConflictError("CAS mismatch: competitor committed")):
            inp_loser = DummyInputs(plot_id=plot_id, tenant_id=tenant, namespace=ns,
                                    weather_daily={"2026-06-01": w1, "2026-06-02": {**w2, "precipitation_mm": 5.0}},
                                    operational_context={"tenant_id": tenant, "namespace": ns})
            with pytest.raises(ConcurrencyConflictError):
                _execute_canonical_water_engine(inp_loser, None, None, ts2)

    # After loser's rollback, RAM must NOT be reset to Day 1: it must preserve or agree with Winner's Day 2!
    scope_key = (tenant, ns, plot_id)
    cached_head = _PLOT_CURRENT_HEAD.get(scope_key)
    assert cached_head == win_head_id

    cached_soil, _ = _PLOT_WATER_STATE_MEMORY.get(scope_key, (None, None))
    assert cached_soil is not None
    assert list(cached_soil.theta_profile) == pytest.approx(win_theta, rel=1e-4)
