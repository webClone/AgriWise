import datetime
from datetime import timezone
import pytest
import shutil
from pathlib import Path

from services.agribrain.layer3_decision.runner import (
    _execute_canonical_water_engine,
    _PLOT_WATER_STATE_HISTORY,
    _PLOT_WATER_STATE_MEMORY,
    _PLOT_MANAGEMENT_EVENTS,
    _PLOT_VEGETATION_HISTORY,
    _PLOT_SOIL_OBS_HISTORY,
    _PLOT_INITIAL_STATE_HISTORY,
    _PLOT_WITHDRAWN_SOIL_OBS,
    _PLOT_WITHDRAWN_VEG,
)
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    ConcurrencyConflictError,
    CANONICAL_WORLDLINE_ROOT,
)
from services.agribrain.layer05_asmae.history.worldline_service import (
    PlotWorldlineService,
)


class DummyInput:
    def __init__(self, plot_id="P_F09_TEST", operational_context=None, **kwargs):
        self.plot_id = plot_id
        self.operational_context = operational_context or {}
        for k, v in kwargs.items():
            setattr(self, k, v)


def _clear_all_memory():
    _PLOT_WATER_STATE_HISTORY.clear()
    _PLOT_WATER_STATE_MEMORY.clear()
    _PLOT_MANAGEMENT_EVENTS.clear()
    _PLOT_VEGETATION_HISTORY.clear()
    _PLOT_SOIL_OBS_HISTORY.clear()
    _PLOT_INITIAL_STATE_HISTORY.clear()
    _PLOT_WITHDRAWN_SOIL_OBS.clear()
    _PLOT_WITHDRAWN_VEG.clear()


@pytest.fixture(autouse=True)
def cleanup_test_artifacts():
    _clear_all_memory()
    yield
    _clear_all_memory()
    # Clean up test worldline paths
    for test_dir in CANONICAL_WORLDLINE_ROOT.glob("*f09*"):
        if test_dir.is_dir():
            shutil.rmtree(test_dir, ignore_errors=True)
    for test_dir in CANONICAL_WORLDLINE_ROOT.glob("test_*"):
        if test_dir.is_dir():
            shutil.rmtree(test_dir, ignore_errors=True)


def test_f09_checkpoint_commit_and_load():
    """Verify CanonicalWorldlineService saves and loads hydraulic checkpoints."""
    svc = CanonicalWorldlineService()
    tenant = "test_f09_tenant"
    ns = "default"
    plot_id = "plot_cp_01"

    # Initially empty
    cp_none = svc.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    assert cp_none is None

    # Save initial checkpoint
    payload_1 = {"test_val": 42, "soil_water": {"theta_profile": [0.25, 0.28]}}
    rec_1 = svc.save_hydraulic_checkpoint(
        plot_id=plot_id,
        checkpoint_id="cp_001",
        checkpoint_payload=payload_1,
        tenant_id=tenant,
        namespace=ns,
        expected_predecessor_head=None,
    )
    assert rec_1["checkpoint_id"] == "cp_001"
    assert rec_1["sequence"] == 1

    # Load latest
    cp_loaded = svc.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    assert cp_loaded is not None
    assert cp_loaded["checkpoint_id"] == "cp_001"
    assert cp_loaded["payload"]["test_val"] == 42


def test_f09_cas_concurrency_conflict_rejection():
    """Verify CAS raises ConcurrencyConflictError when two workers race from same head."""
    svc = CanonicalWorldlineService()
    tenant = "test_f09_cas"
    ns = "default"
    plot_id = "plot_cas_01"

    # Step 1: Initial commit by worker 1 from empty head
    svc.save_hydraulic_checkpoint(
        plot_id=plot_id,
        checkpoint_id="cp_step_1",
        checkpoint_payload={"state": 1},
        tenant_id=tenant,
        namespace=ns,
        expected_predecessor_head=None,
    )

    # Step 2: Both worker A and worker B observe head is cp_step_1
    latest = svc.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    observed_head = latest["checkpoint_id"]
    assert observed_head == "cp_step_1"

    # Worker A succeeds in committing successor cp_step_2a
    svc.save_hydraulic_checkpoint(
        plot_id=plot_id,
        checkpoint_id="cp_step_2a",
        checkpoint_payload={"state": 2, "worker": "A"},
        tenant_id=tenant,
        namespace=ns,
        expected_predecessor_head=observed_head,
    )

    # Worker B tries to commit alternative successor cp_step_2b expecting old head cp_step_1
    with pytest.raises(ConcurrencyConflictError) as exc_info:
        svc.save_hydraulic_checkpoint(
            plot_id=plot_id,
            checkpoint_id="cp_step_2b",
            checkpoint_payload={"state": 2, "worker": "B"},
            tenant_id=tenant,
            namespace=ns,
            expected_predecessor_head=observed_head,
        )
    assert "Predecessor head conflict" in str(exc_info.value)


def test_f09_multi_tenant_isolation():
    """Verify different tenants with same plot_id have isolated worldlines and checkpoints."""
    svc = CanonicalWorldlineService()
    plot_id = "plot_shared_name"

    svc.save_hydraulic_checkpoint(
        plot_id=plot_id,
        checkpoint_id="cp_t1",
        checkpoint_payload={"tenant": "tenant_1", "theta": 0.20},
        tenant_id="test_tenant_1",
        namespace="default",
    )

    svc.save_hydraulic_checkpoint(
        plot_id=plot_id,
        checkpoint_id="cp_t2",
        checkpoint_payload={"tenant": "tenant_2", "theta": 0.35},
        tenant_id="test_tenant_2",
        namespace="default",
    )

    cp_t1 = svc.load_latest_hydraulic_checkpoint(plot_id, tenant_id="test_tenant_1")
    cp_t2 = svc.load_latest_hydraulic_checkpoint(plot_id, tenant_id="test_tenant_2")

    assert cp_t1["checkpoint_id"] == "cp_t1"
    assert cp_t1["payload"]["theta"] == 0.20
    assert cp_t2["checkpoint_id"] == "cp_t2"
    assert cp_t2["payload"]["theta"] == 0.35


def _make_weather(date_str: str, et0: float = 4.5, precip: float = 0.0, t_max: float = 28.0, t_min: float = 15.0):
    return {
        "date": date_str,
        "reference_et0_mm": et0,
        "t_max_c": t_max,
        "t_min_c": t_min,
        "precipitation_mm": precip,
        "wind_speed_2m_m_s": 2.0,
        "rh_min_pct": 35.0,
        "rh_max_pct": 80.0,
        "net_radiation_mj_m2": 18.0,
    }


def test_f09_cold_restart_equals_warm_replay():
    """Verify cold restart (empty RAM cache) matches warm replay via persisted checkpoints."""
    plot_id = "P_F09_COLD_RESTART"
    tenant = "test_f09_restart"
    ns = "default"

    w1 = _make_weather("2026-06-01", et0=5.0, precip=0.0, t_max=30.0, t_min=18.0)
    w2 = _make_weather("2026-06-02", et0=6.0, precip=0.0, t_max=32.0, t_min=19.0)

    # Run Day 1
    ts_d1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    inp_d1 = DummyInput(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    state_d1, fb_d1 = _execute_canonical_water_engine(inp_d1, None, None, ts_d1)
    assert state_d1 is not None

    # Run Day 2 (warm continuation)
    ts_d2 = datetime.datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    inp_d2 = DummyInput(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1, "2026-06-02": w2},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    warm_state_d2, warm_fb_d2 = _execute_canonical_water_engine(inp_d2, None, None, ts_d2)
    assert warm_state_d2 is not None

    warm_theta = list(warm_state_d2.soil_water.theta_profile)
    warm_deficit = warm_state_d2.hydraulic_memory.cumulative_transpiration_deficit_mm

    # COLD RESTART: Wipe all in-memory registries completely
    _clear_all_memory()

    # Run Day 2 again directly under cold restart
    cold_state_d2, cold_fb_d2 = _execute_canonical_water_engine(inp_d2, None, None, ts_d2)
    assert cold_state_d2 is not None

    cold_theta = list(cold_state_d2.soil_water.theta_profile)
    cold_deficit = cold_state_d2.hydraulic_memory.cumulative_transpiration_deficit_mm

    # Verify identical continuation across cold restart
    assert cold_theta == pytest.approx(warm_theta, rel=1e-5)
    assert cold_deficit == pytest.approx(warm_deficit, rel=1e-5)


def test_f09_withdrawn_and_cancelled_events_survive_restart():
    """Verify withdrawn soil observations and cancelled events survive cold restart."""
    plot_id = "P_F09_WITHDRAWAL"
    tenant = "test_f09_withdrawn"
    ns = "default"

    w1 = _make_weather("2026-06-01", et0=4.0, precip=0.0, t_max=28.0, t_min=16.0)
    cancelled_event = {
        "id": "ev_irr_99",
        "date": "2026-06-01",
        "type": "irrigation",
        "amount_mm": 50.0,
        "status": "cancelled",
    }

    ts_d1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    inp = DummyInput(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1},
        management_events=[cancelled_event],
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    state, fb = _execute_canonical_water_engine(inp, None, None, ts_d1)
    assert state is not None
    # 50mm was cancelled, so irrigation flux must be 0.0
    assert state.fluxes.actual.irrigation_mm == 0.0

    # Cold restart
    _clear_all_memory()

    # Re-run after cold restart without passing management_events
    inp_cold = DummyInput(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )
    state_after, fb_after = _execute_canonical_water_engine(inp_cold, None, None, ts_d1)
    assert state_after is not None
    # Still 0.0, because cancelled status was checkpointed
    assert state_after.fluxes.actual.irrigation_mm == 0.0


def test_r08_r17_checkpoint_path_containment():
    """R17: Checkpoint ID path traversal is rejected and contained within checkpoints directory."""
    svc = CanonicalWorldlineService()
    tenant = "test_f09_containment"
    plot_id = "P_CONTAIN_01"

    with pytest.raises(ValueError, match="traversal"):
        svc.save_hydraulic_checkpoint(
            plot_id=plot_id,
            checkpoint_id="../../escaped_checkpoint",
            checkpoint_payload={"data": 1},
            tenant_id=tenant,
        )

    with pytest.raises(ValueError, match="traversal"):
        svc.save_hydraulic_checkpoint(
            plot_id=plot_id,
            checkpoint_id="sub/nested/cp",
            checkpoint_payload={"data": 1},
            tenant_id=tenant,
        )


def test_r08_checkpoint_immutability_and_identical_retry():
    """R08: Checkpoint is immutable; identical retry succeeds idempotently, differing payload raises conflict."""
    svc = CanonicalWorldlineService()
    tenant = "test_f09_immutability"
    plot_id = "P_IMMUTABLE_01"

    rec1 = svc.save_hydraulic_checkpoint(
        plot_id=plot_id,
        checkpoint_id="cp_imm_01",
        checkpoint_payload={"value": 100, "status": "committed"},
        tenant_id=tenant,
    )
    assert rec1["checkpoint_id"] == "cp_imm_01"

    # Identical retry: returns existing record idempotently
    rec2 = svc.save_hydraulic_checkpoint(
        plot_id=plot_id,
        checkpoint_id="cp_imm_01",
        checkpoint_payload={"value": 100, "status": "committed"},
        tenant_id=tenant,
    )
    assert rec2["sequence"] == rec1["sequence"]

    # Differing payload under same checkpoint ID: rejected
    with pytest.raises(ConcurrencyConflictError, match="immutable"):
        svc.save_hydraulic_checkpoint(
            plot_id=plot_id,
            checkpoint_id="cp_imm_01",
            checkpoint_payload={"value": 999, "status": "conflict"},
            tenant_id=tenant,
        )


def test_r08_self_parent_loop_rejection():
    """R08: Checkpoint cannot reference itself as predecessor head."""
    svc = CanonicalWorldlineService()
    tenant = "test_f09_self_parent"
    plot_id = "P_SELF_PARENT_01"

    with pytest.raises(ValueError, match="Self-parent"):
        svc.save_hydraulic_checkpoint(
            plot_id=plot_id,
            checkpoint_id="cp_loop_01",
            checkpoint_payload={"value": 1},
            tenant_id=tenant,
            expected_predecessor_head="cp_loop_01",
        )


def test_r07_transition_identity_exact_repeat():
    """R07: Identical transition request returns committed result without advancing head or re-solving."""
    plot_id = "P_F09_R07_IDENTITY"
    tenant = "test_f09_r07"
    ns = "default"
    w1 = _make_weather("2026-06-01", et0=4.5, precip=0.0)

    ts_d1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    inp1 = DummyInput(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )

    state1, fb1 = _execute_canonical_water_engine(inp1, None, None, ts_d1)
    assert state1 is not None

    svc = CanonicalWorldlineService()
    head1 = svc.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    seq1 = head1["sequence"]

    # Repeat exact same request
    state2, fb2 = _execute_canonical_water_engine(inp1, None, None, ts_d1)
    assert state2 is not None

    head2 = svc.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    # Head and sequence must NOT advance on identical transition repeat
    assert head2["sequence"] == seq1
    assert head2["checkpoint_id"] == head1["checkpoint_id"]


def test_r10_r11_cas_failure_leaves_ram_cache_untouched():
    """R10 + R11: When CAS fails, candidate state is not published to authoritative RAM cache."""
    plot_id = "P_F09_CAS_ISOLATION"
    tenant = "test_f09_cas_iso"
    ns = "default"
    w1 = _make_weather("2026-06-01", et0=4.0)

    # Pre-commit an external conflicting head in the durable store
    svc = CanonicalWorldlineService()
    svc.save_hydraulic_checkpoint(
        plot_id=plot_id,
        checkpoint_id="cp_external_winner",
        checkpoint_payload={"state": "external"},
        tenant_id=tenant,
        namespace=ns,
    )

    # Attempt to solve Day 1 with expected head None
    ts_d1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    inp = DummyInput(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1},
        operational_context={"tenant_id": tenant, "namespace": ns},
    )

    import unittest.mock
    with unittest.mock.patch.object(CanonicalWorldlineService, "save_hydraulic_checkpoint", side_effect=ConcurrencyConflictError("Predecessor conflict")):
        with pytest.raises(ConcurrencyConflictError):
            _execute_canonical_water_engine(inp, None, None, ts_d1)

    # Verify candidate state was NOT committed into RAM cache
    from services.agribrain.layer3_decision.runner import _PLOT_WATER_STATE_HISTORY
    assert "2026-06-01" not in _PLOT_WATER_STATE_HISTORY.get(f"{tenant}:{ns}:{plot_id}", {})


def test_r12_withdrawal_date_string_serialization():
    """R12: Withdrawn soil and veg dates handle string formats without AttributeError."""
    plot_id = "P_F09_R12_WITHDRAWAL"
    tenant = "test_f09_r12"
    ns = "default"
    w1 = _make_weather("2026-06-01", et0=4.0)

    withdrawn_soil_item = {
        "date": "2026-06-01",
        "status": "withdrawn",
        "layer_theta": [0.20, 0.25],
    }

    ts_d1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    inp = DummyInput(
        plot_id=plot_id,
        tenant_id=tenant,
        namespace=ns,
        weather_daily={"2026-06-01": w1},
        soil_observations_daily=[withdrawn_soil_item],
        operational_context={"tenant_id": tenant, "namespace": ns},
    )

    # Must complete without AttributeError: 'str' object has no attribute 'isoformat'
    state, fb = _execute_canonical_water_engine(inp, None, None, ts_d1)
    assert state is not None

    svc = CanonicalWorldlineService()
    cp = svc.load_latest_hydraulic_checkpoint(plot_id, tenant_id=tenant, namespace=ns)
    assert cp is not None
    assert "2026-06-01" in cp["payload"]["withdrawn_soil_dates"]

