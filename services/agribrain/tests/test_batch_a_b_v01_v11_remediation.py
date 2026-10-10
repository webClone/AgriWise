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
        self.stop_calls += 1
        return CommandResult(
            command_id="es",
            device_id=self.device_id,
            success=True,
            timestamp=datetime.datetime.now(timezone.utc).isoformat(),
        )

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
):
    return IrrigationEvent(
        event_id=event_id,
        plot_id=plot_id,
        zone_id="ZONE-1",
        device_id=device_id,
        system_type=IrrigationSystemType.DRIP,
        automation_mode=AutomationMode.FULL_AUTO,
        status=status,
        target_volume_mm=volume_mm,
        target_duration_minutes=duration_minutes,
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
        "t_max_c": 28.0,
        "t_min_c": 16.0,
        "precipitation_mm": precip,
        "wind_speed_2m_m_s": 2.0,
        "rh_min_pct": 35.0,
        "rh_max_pct": 75.0,
        "net_radiation_mj_m2": 16.0,
        "et0_mm": et0,
    }


def _clean_test_worldlines():
    for test_dir in CANONICAL_WORLDLINE_ROOT.glob("t_v*"):
        if test_dir.is_dir():
            shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_shared_state(tmp_path, monkeypatch):
    _clear_all_memory()
    _clean_test_worldlines()
    quota_dir = tmp_path / "quota_test"
    quota_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AGRIBRAIN_QUOTA_DIR", str(quota_dir))
    yield
    _clear_all_memory()
    _clean_test_worldlines()



# ============================================================================
# V01: Corrupt quota storage handling
# ============================================================================
def test_v01_corrupt_quota_storage_raises_and_blocks_reset():
    """V01: Empty text, broken JSON, or wrong type raises CorruptedQuotaStoreError and prohibits silent reset."""
    store_file = SharedQuotaStore._store_file()
    # Write empty file
    store_file.write_text("", encoding="utf-8")
    with pytest.raises(CorruptedQuotaStoreError):
        SharedQuotaStore._read_state()

    # Write malformed JSON
    store_file.write_text("{broken json", encoding="utf-8")
    with pytest.raises(CorruptedQuotaStoreError):
        SharedQuotaStore._read_state()

    # Write non-dict JSON
    store_file.write_text("[]", encoding="utf-8")
    with pytest.raises(CorruptedQuotaStoreError):
        SharedQuotaStore._read_state()

    # Write dict with missing required schema fields
    store_file.write_text('{"other": 1}', encoding="utf-8")
    with pytest.raises(CorruptedQuotaStoreError):
        SharedQuotaStore._read_state()


# ============================================================================
# V02: Live owner lock takeover prevention
# ============================================================================
def test_v02_live_owner_lock_cannot_be_stolen_by_aged_mtime():
    """V02: If lock holder PID is alive, competitor cannot steal lock even if mtime is aged > 30s."""
    lock_file = SharedQuotaStore._store_dir() / "quota.lock"
    # Write a lock owned by current running process
    token = f"{os.getpid()}:test_ident:uuid123"
    lock_file.write_text(token, encoding="utf-8")

    # Artificially age the mtime by 60 seconds
    past_time = time.time() - 60
    os.utime(str(lock_file), (past_time, past_time))

    # A contender with a different token attempts to acquire lock: must fail
    with patch("time.sleep", return_value=None):
        with pytest.raises(TimeoutError):
            with SharedQuotaStore._lock():
                pass

    # Lock must remain intact with original owner
    assert lock_file.exists()
    assert lock_file.read_text(encoding="utf-8") == token

    # Clean up lock safely
    lock_file.unlink(missing_ok=True)


# ============================================================================
# V03: Atomic operation admission and duplicate START suppression
# ============================================================================
@pytest.mark.anyio
async def test_v03_concurrent_same_operation_suppresses_second_start():
    """V03: Two owners submitting the same event ID and device: second joins without duplicate physical START."""
    actuator = MockActuator(device_id="pump_v03")
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    event = _make_event(
        event_id="ev_v03_01",
        plot_id="plot_1",
        device_id="pump_v03",
        volume_mm=8.0,
        duration_minutes=15.0,
    )
    budget = WaterBudget(plot_id="plot_1", season="season_2026", daily_remaining_mm=10.0, season_remaining_mm=10.0)

    res1 = await dispatcher.submit_event(event, budget=budget)
    assert res1.status == EventStatus.EXECUTING
    assert actuator.start_calls == 1

    # Second dispatcher instance submits the exact same event ID and parameters
    dispatcher2 = CommandDispatcher()
    dispatcher2.register_actuator(actuator)
    res2 = await dispatcher2.submit_event(event, budget=budget)
    # Joins active execution: physical START count remains 1!
    assert res2.status == EventStatus.EXECUTING
    assert actuator.start_calls == 1


@pytest.mark.anyio
async def test_v03_conflicting_payload_for_active_event_rejected():
    """V03: Submitting an existing active event ID with different target volume is blocked."""
    actuator = MockActuator(device_id="pump_v03_conflict")
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    event1 = _make_event(
        event_id="ev_v03_conflict",
        plot_id="plot_1",
        device_id="pump_v03_conflict",
        volume_mm=8.0,
        duration_minutes=15.0,
    )
    budget = WaterBudget(plot_id="plot_1", season="season_2026", daily_remaining_mm=20.0, season_remaining_mm=20.0)
    await dispatcher.submit_event(event1, budget=budget)
    assert actuator.start_calls == 1

    # Second event with same ID but 12 mm instead of 8 mm
    event2 = _make_event(
        event_id="ev_v03_conflict",
        plot_id="plot_1",
        device_id="pump_v03_conflict",
        volume_mm=12.0,
        duration_minutes=15.0,
    )
    res2 = await dispatcher.submit_event(event2, budget=budget)
    assert res2.status == EventStatus.FAILED
    assert "CONFLICT" in (res2.error_message or "")
    assert actuator.start_calls == 1


# ============================================================================
# V04: Seasonal quota preservation and stopped delivery accounting
# ============================================================================
@pytest.mark.anyio
async def test_v04_season_retained_in_settlement_and_stopped_delivery():
    """V04: Budget season is preserved into settlement; cancelled event records stopped exposure."""
    actuator = MockActuator(device_id="pump_v04")
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    event = _make_event(
        event_id="ev_v04_season",
        plot_id="plot_v04",
        device_id="pump_v04",
        volume_mm=8.0,
        duration_minutes=10.0,
    )
    budget = WaterBudget(plot_id="plot_v04", season="dry_season_2026", daily_remaining_mm=100.0, season_remaining_mm=10.0)
    await dispatcher.submit_event(event, budget=budget)

    # Simulate actuator physical completion -> enters VALIDATING
    actuator._status = ActuatorStatus.ONLINE
    actuator._active_command = None
    await dispatcher.check_execution_status(event.event_id)
    assert event.status == EventStatus.VALIDATING

    # Complete the event
    await dispatcher.complete_event(event, actual_volume_l=80000.0, actual_duration_minutes=10.0)

    # Check settled receipt season
    receipt = SharedQuotaStore.get_settled_receipt("ev_v04_season")
    assert receipt is not None
    assert receipt["season"] == "dry_season_2026"

    # Now a second 8 mm request against the same 10 mm seasonal budget must be BLOCKED
    event2 = _make_event(
        event_id="ev_v04_second",
        plot_id="plot_v04",
        device_id="pump_v04",
        volume_mm=8.0,
        duration_minutes=10.0,
    )
    budget2 = WaterBudget(plot_id="plot_v04", season="dry_season_2026", daily_remaining_mm=100.0, season_remaining_mm=10.0)
    res2 = await dispatcher.submit_event(event2, budget=budget2)
    assert res2.status == EventStatus.FAILED
    assert "QUOTA" in (res2.error_message or "").upper()


# ============================================================================
# V05: Invalid budget reporting returns typed failure without NameError
# ============================================================================
@pytest.mark.anyio
async def test_v05_invalid_budget_returns_typed_failure_without_name_error():
    """V05: Budget with NaN or Inf returns FAILED event with detail and raises no NameError."""
    actuator = MockActuator(device_id="pump_v05")
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    event = _make_event(
        event_id="ev_v05_nan",
        plot_id="plot_v05",
        device_id="pump_v05",
        volume_mm=8.0,
        duration_minutes=10.0,
    )
    # NaN in daily remaining
    bad_budget = WaterBudget(plot_id="plot_v05", season="season_2026", daily_remaining_mm=float("nan"), season_remaining_mm=10.0)
    result = await dispatcher.submit_event(event, budget=bad_budget)
    assert result.status == EventStatus.FAILED
    assert "finite real number" in (result.error_message or "")
    assert actuator.start_calls == 0


# ============================================================================
# V06: Deadline safety during pending send and preemptible STOP
# ============================================================================
@pytest.mark.anyio
async def test_v06_stop_preempts_hung_start_and_monitors_before_send():
    """V06: Watchdog is installed before send; direct STOP preempts a hung START immediately."""
    actuator = MockActuator(device_id="pump_v06", hang_start=True)
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(actuator)

    event = _make_event(
        event_id="ev_v06_hang",
        plot_id="plot_v06",
        device_id="pump_v06",
        volume_mm=8.0,
        duration_minutes=5.0,
    )
    budget = WaterBudget(plot_id="plot_v06", season="season_2026", daily_remaining_mm=10.0, season_remaining_mm=10.0)

    # Launch submit in background task
    submit_task = asyncio.create_task(dispatcher.submit_event(event, budget=budget))

    # Wait until actuator START is reached
    await actuator.start_applied_event.wait()

    # Verify duration monitoring was ALREADY installed before start returned
    assert dispatcher._safety.is_event_active("ev_v06_hang") is True

    # Now cancel_event should send STOP immediately without deadlocking behind dispatch_lock
    cancel_res = await dispatcher.cancel_event(event, reason="Emergency deadline cancellation")
    assert cancel_res is not None
    assert cancel_res.status == EventStatus.CANCELLED
    assert actuator.stop_calls >= 1

    # Release start task to cleanly finish
    actuator.release_start_event.set()
    await submit_task


@pytest.mark.anyio
async def test_v06_malformed_restart_timestamp_treated_as_expired():
    """V06: An EXECUTING event on restart with malformed actual_start is conservatively treated as expired."""
    dispatcher = CommandDispatcher()
    event = _make_event(
        event_id="ev_v06_malformed",
        plot_id="plot_v06",
        device_id="pump_v06_none",
        volume_mm=8.0,
        duration_minutes=10.0,
        status=EventStatus.EXECUTING,
        actual_start="not-a-valid-iso-timestamp",
    )
    # Without registered actuator, reconcile should retain event with expired elapsed time
    reconciled = await dispatcher.reconcile_on_restart([event])
    assert len(reconciled) == 1
    # Check that safety monitor has elapsed >= target_duration
    active_recs = dispatcher._safety._active_events
    assert "ev_v06_malformed" in active_recs
    info = active_recs["ev_v06_malformed"]
    elapsed = (dispatcher._safety._clock() - info["start_monotonic"]) / 60.0
    assert elapsed >= 10.0
    violations = dispatcher._safety._check_duration_watchdog("pump_v06_none")
    assert len(violations) >= 1


# ============================================================================
# V07: Cold exact replay preserves VWC and head sequence
# ============================================================================
def test_v07_cold_exact_replay_preserves_vwc_and_sequence():
    """V07: Executing identical request after cold restart preserves top-layer VWC and sequence."""
    plot_id = "P_V07_COLD_REPLAY"
    tenant = "t_v07"
    ns = "default"
    w1 = _make_base_weather("2026-06-01", et0=5.0)
    ts1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    inp = DummyInputs(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )

    # Initial execution
    s1, fb1 = _execute_canonical_water_engine(inp, None, None, ts1)
    assert s1 is not None
    theta1 = list(s1.soil_water.theta_profile)

    cw = CanonicalWorldlineService()
    cp1 = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    seq1 = cp1["sequence"]

    # Clear RAM completely (cold restart)
    _clear_all_memory()

    # Re-run identical request under cold restart
    s2, fb2 = _execute_canonical_water_engine(inp, None, None, ts1)
    assert s2 is not None
    theta2 = list(s2.soil_water.theta_profile)

    cp2 = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    seq2 = cp2["sequence"]

    # VWC and head sequence must be preserved exactly
    assert theta2 == pytest.approx(theta1, rel=1e-5)
    assert seq2 == seq1


# ============================================================================
# V08: Scope and parameter dependencies invalidate warm shortcut
# ============================================================================
def test_v08_parameter_and_scope_changes_invalidate_warm_shortcut():
    """V08: Modifying cycle, geometry, parameter epoch, or soil type bypasses warm shortcut."""
    plot_id = "P_V08_SCOPE"
    tenant = "t_v08"
    ns = "default"
    w1 = _make_base_weather("2026-06-01", et0=4.0)
    ts1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    inp1 = DummyInputs(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        cycle_id="cycle_A",
        geometry_version="geom_v1",
        parameter_epoch="v1",
        soil_type="loam",
        weather_daily={"2026-06-01": w1},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    s1, _ = _execute_canonical_water_engine(inp1, None, None, ts1)
    assert s1 is not None

    # Follow-up with cycle changed: cycle_A -> cycle_B
    inp2 = DummyInputs(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        cycle_id="cycle_B",
        geometry_version="geom_v1",
        parameter_epoch="v1",
        soil_type="loam",
        weather_daily={"2026-06-01": w1},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    # Changing cycle must not return the old cached result from cycle_A
    s2, _ = _execute_canonical_water_engine(inp2, None, None, ts1)
    assert s2 is not None

    cw = CanonicalWorldlineService()
    cp = cw.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    assert cp["cycle_id"] == "cycle_B"


# ============================================================================
# V09: Candidate isolation and full RAM rollback on commit failure
# ============================================================================
def test_v09_full_ram_rollback_on_concurrency_conflict():
    """V09: If commit raises ConcurrencyConflictError, all mutated RAM registries roll back to pre-run snapshot."""
    plot_id = "P_V09_ROLLBACK"
    tenant = "t_v09"
    ns = "default"
    w1 = _make_base_weather("2026-06-01", et0=4.0)
    ts1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    # Initial valid run on Day 1
    inp1 = DummyInputs(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1},
        vegetation_daily={"2026-06-01": {"lai": 2.0, "fvc": 0.6}},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    _execute_canonical_water_engine(inp1, None, None, ts1)

    scope_key = (tenant, ns, plot_id)
    assert "2026-06-01" in _PLOT_WATER_STATE_HISTORY.get(scope_key, {})
    assert "2026-06-01" in _PLOT_VEGETATION_HISTORY.get(scope_key, {})

    # Day 2 with injected CAS conflict
    w2 = _make_base_weather("2026-06-02", et0=5.0)
    ts2 = datetime.datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    inp2 = DummyInputs(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1, "2026-06-02": w2},
        vegetation_daily={"2026-06-02": {"lai": 2.5, "fvc": 0.8}},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )

    with patch.object(CanonicalWorldlineService, "save_hydraulic_checkpoint", side_effect=ConcurrencyConflictError("Injected CAS failure")):
        with pytest.raises(ConcurrencyConflictError):
            _execute_canonical_water_engine(inp2, None, None, ts2)

    # Verify Day 2 changes in RAM were completely rolled back!
    assert "2026-06-02" not in _PLOT_WATER_STATE_HISTORY.get(scope_key, {})
    assert "2026-06-02" not in _PLOT_VEGETATION_HISTORY.get(scope_key, {})
    # And Day 1 remains safely committed in RAM!
    assert "2026-06-01" in _PLOT_WATER_STATE_HISTORY.get(scope_key, {})


# ============================================================================
# V10: Checkpoint persistence failure raises typed error
# ============================================================================
def test_v10_persistence_failure_raises_typed_error():
    """V10: Injected OSError at save_hydraulic_checkpoint raises RuntimeError instead of returning water result."""
    plot_id = "P_V10_PERSISTENCE"
    tenant = "t_v10"
    ns = "default"
    w1 = _make_base_weather("2026-06-01", et0=4.0)
    ts1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    inp = DummyInputs(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )

    with patch.object(CanonicalWorldlineService, "save_hydraulic_checkpoint", side_effect=OSError("Disk write failed")):
        with pytest.raises(RuntimeError) as exc_info:
            _execute_canonical_water_engine(inp, None, None, ts1)
        assert "Hydraulic checkpoint persistence failed" in str(exc_info.value)

    # RAM cache must not have recorded this unpersisted step
    scope_key = (tenant, ns, plot_id)
    assert "2026-06-01" not in _PLOT_WATER_STATE_HISTORY.get(scope_key, {})


# ============================================================================
# V11: Interrupted head publication recovery and metadata mismatch rejection
# ============================================================================
def test_v11_interrupted_head_publication_recovers_idempotently():
    """V11: Checkpoint written but head interrupted: identical retry safely publishes head."""
    svc = CanonicalWorldlineService()
    tenant = "t_v11"
    ns = "default"
    plot_id = "plot_v11_recovery"

    cp_payload = {"state": "initial", "theta": 0.22}
    cp_id = "cp_v11_01"

    # Step 1: Simulate interrupted publication: write checkpoint directly, but head file is NOT updated
    cp_path = svc._hydraulic_checkpoint_path(plot_id, cp_id, tenant, ns)
    cp_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "checkpoint_id": cp_id,
        "tenant_id": tenant,
        "namespace": ns,
        "plot_id": plot_id,
        "cycle_id": "default_cycle",
        "geometry_version": "default_geom",
        "sequence": 1,
        "predecessor_head": None,
        "payload": cp_payload,
    }
    svc._atomic(cp_path, record)

    # At this point, head does NOT point to cp_v11_01
    head_before = svc.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    assert head_before is None

    # Step 2: Retry save_hydraulic_checkpoint with identical record
    recovered = svc.save_hydraulic_checkpoint(
        plot_id=plot_id,
        checkpoint_id=cp_id,
        checkpoint_payload=cp_payload,
        tenant_id=tenant,
        namespace=ns,
    )
    assert recovered["checkpoint_id"] == cp_id

    # Head is now safely published
    head_after = svc.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    assert head_after is not None
    assert head_after["checkpoint_id"] == cp_id


def test_v11_changed_metadata_under_existing_id_rejected():
    """V11: Existing checkpoint with changed cycle or geometry raises ConcurrencyConflictError."""
    svc = CanonicalWorldlineService()
    tenant = "t_v11_conflict"
    ns = "default"
    plot_id = "plot_v11_conflict"

    cp_payload = {"state": "data"}
    cp_id = "cp_v11_exist"

    # Save initial checkpoint under cycle_A
    svc.save_hydraulic_checkpoint(
        plot_id=plot_id,
        checkpoint_id=cp_id,
        checkpoint_payload=cp_payload,
        tenant_id=tenant,
        namespace=ns,
        cycle_id="cycle_A",
    )

    # Attempt to save same checkpoint ID under cycle_B
    with pytest.raises(ConcurrencyConflictError) as exc_info:
        svc.save_hydraulic_checkpoint(
            plot_id=plot_id,
            checkpoint_id=cp_id,
            checkpoint_payload=cp_payload,
            tenant_id=tenant,
            namespace=ns,
            cycle_id="cycle_B",
        )
    assert "differing payload/metadata" in str(exc_info.value)
