# -*- coding: utf-8 -*-
"""Verification tests for F37, F39, F11, F15, and World Model forecast repairs."""

import concurrent.futures
import datetime
from datetime import timezone
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import pytest

from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.authority import AuthorityScope


# ============================================================================
# F37: Clean Imports, Package Identity & Capability Execution
# ============================================================================

def test_f37_zonal_segmentation_clustering():
    from services.agribrain.layer1_fusion.segmentation import ZonalSegmentationEngine
    engine = ZonalSegmentationEngine(n_zones=3)
    pixels = [{"mean_ndvi": 0.1 * i, "std_ndvi": 0.05} for i in range(20)]
    results = engine.segment_field(pixels)
    assert len(results) == 20
    assert all("zone_name" in r and "zone_id" in r for r in results)


def test_f37_entrypoint_imports():
    import services.agribrain.layer1_fusion.engine as l1_engine
    import services.agribrain.drone_control.dispatcher as dc_disp
    import services.agribrain.drone_mission as dm
    assert l1_engine is not None
    assert dc_disp is not None
    assert dm is not None


def test_f37_unified_namespace_drone_mission_import_orders():
    """Verify both import orders for drone_mission.schemas.MissionType produce identical class identity."""
    code_order_1 = "import sys; sys.path.insert(0, 'services/agribrain'); import drone_mission.schemas as s1; import services.agribrain.drone_mission.schemas as s2; assert s1.MissionType is s2.MissionType"
    res1 = subprocess.run([sys.executable, "-c", code_order_1], capture_output=True, text=True)
    assert res1.returncode == 0, f"Order 1 failed: {res1.stderr}"

    code_order_2 = "import sys; sys.path.insert(0, 'services/agribrain'); import services.agribrain.drone_mission.schemas as s2; import drone_mission.schemas as s1; assert s1.MissionType is s2.MissionType"
    res2 = subprocess.run([sys.executable, "-c", code_order_2], capture_output=True, text=True)
    assert res2.returncode == 0, f"Order 2 failed: {res2.stderr}"


def test_f37_unified_namespace_sensor_runtime_import_orders():
    """Verify both import orders for sensor_runtime.registry.SensorDeviceRegistration produce identical class identity."""
    code_order_1 = "import sys; sys.path.insert(0, 'services/agribrain'); import sensor_runtime.registry as s1; import services.agribrain.sensor_runtime.registry as s2; assert s1.SensorDeviceRegistration is s2.SensorDeviceRegistration"
    res1 = subprocess.run([sys.executable, "-c", code_order_1], capture_output=True, text=True)
    assert res1.returncode == 0, f"Order 1 failed: {res1.stderr}"

    code_order_2 = "import sys; sys.path.insert(0, 'services/agribrain'); import services.agribrain.sensor_runtime.registry as s2; import sensor_runtime.registry as s1; assert s1.SensorDeviceRegistration is s2.SensorDeviceRegistration"
    res2 = subprocess.run([sys.executable, "-c", code_order_2], capture_output=True, text=True)
    assert res2.returncode == 0, f"Order 2 failed: {res2.stderr}"


def test_f37_unified_namespace_sensor_runtime_schemas_import_orders():
    """Verify both import orders for sensor_runtime.schemas.NormalizedSensorReading produce identical class identity."""
    code_order_1 = "import sys; sys.path.insert(0, 'services/agribrain'); import sensor_runtime.schemas as s1; import services.agribrain.sensor_runtime.schemas as s2; assert s1.NormalizedSensorReading is s2.NormalizedSensorReading; assert s1.RawSensorMessage is s2.RawSensorMessage"
    res1 = subprocess.run([sys.executable, "-c", code_order_1], capture_output=True, text=True)
    assert res1.returncode == 0, f"Order 1 failed: {res1.stderr}"

    code_order_2 = "import sys; sys.path.insert(0, 'services/agribrain'); import services.agribrain.sensor_runtime.schemas as s2; import sensor_runtime.schemas as s1; assert s1.NormalizedSensorReading is s2.NormalizedSensorReading; assert s1.RawSensorMessage is s2.RawSensorMessage"
    res2 = subprocess.run([sys.executable, "-c", code_order_2], capture_output=True, text=True)
    assert res2.returncode == 0, f"Order 2 failed: {res2.stderr}"


def test_f37_unified_namespace_irrigation_runtime_import_orders():
    """Verify both import orders for irrigation_runtime.schemas.ActuatorRegistration produce identical class identity."""
    code_order_1 = "import sys; sys.path.insert(0, 'services/agribrain'); import irrigation_runtime.schemas as s1; import services.agribrain.irrigation_runtime.schemas as s2; assert s1.ActuatorRegistration is s2.ActuatorRegistration"
    res1 = subprocess.run([sys.executable, "-c", code_order_1], capture_output=True, text=True)
    assert res1.returncode == 0, f"Order 1 failed: {res1.stderr}"

    code_order_2 = "import sys; sys.path.insert(0, 'services/agribrain'); import services.agribrain.irrigation_runtime.schemas as s2; import irrigation_runtime.schemas as s1; assert s1.ActuatorRegistration is s2.ActuatorRegistration"
    res2 = subprocess.run([sys.executable, "-c", code_order_2], capture_output=True, text=True)
    assert res2.returncode == 0, f"Order 2 failed: {res2.stderr}"


def test_f37_unified_namespace_irrigation_runtime_actuator_import_orders():
    """Verify both import orders for irrigation_runtime.actuator.IrrigationActuator and DurableStopReceiptStore."""
    code_order_1 = "import sys; sys.path.insert(0, 'services/agribrain'); import irrigation_runtime.actuator as s1; import services.agribrain.irrigation_runtime.actuator as s2; assert s1.IrrigationActuator is s2.IrrigationActuator; assert s1.DurableStopReceiptStore is s2.DurableStopReceiptStore"
    res1 = subprocess.run([sys.executable, "-c", code_order_1], capture_output=True, text=True)
    assert res1.returncode == 0, f"Order 1 failed: {res1.stderr}"

    code_order_2 = "import sys; sys.path.insert(0, 'services/agribrain'); import services.agribrain.irrigation_runtime.actuator as s2; import irrigation_runtime.actuator as s1; assert s1.IrrigationActuator is s2.IrrigationActuator; assert s1.DurableStopReceiptStore is s2.DurableStopReceiptStore"
    res2 = subprocess.run([sys.executable, "-c", code_order_2], capture_output=True, text=True)
    assert res2.returncode == 0, f"Order 2 failed: {res2.stderr}"


def test_f37_cold_start_entrypoints_runtime_qualification():
    """Validate cold-start runtime qualification for API (200), background worker, and CLI (--help)."""
    code = (
        "import sys\n"
        "from starlette.testclient import TestClient\n"
        "from services.agribrain.app.main import app\n"
        "client = TestClient(app)\n"
        "resp = client.get('/')\n"
        "assert resp.status_code == 200, f'Status {resp.status_code}: {resp.text}'\n"
        "data = resp.json()\n"
        "assert data.get('status') == 'healthy'\n"
        "from services.agribrain.layer0.data_gateway.refresh_worker import DataRefreshWorker\n"
        "from services.agribrain.layer0.data_gateway import get_broker\n"
        "worker = DataRefreshWorker(get_broker())\n"
        "assert worker is not None\n"
        "from services.agribrain.orchestrator_v2 import run_entrypoint\n"
        "sys.argv = ['run_entrypoint.py', '--help']\n"
        "try:\n"
        "    run_entrypoint.main()\n"
        "except SystemExit as e:\n"
        "    assert e.code == 0\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, f"Cold-start qualification failed: {res.stderr}\nStdout: {res.stdout}"


def test_f37_optional_backend_isolation_eo_fallback():
    """Validate optional-backend isolation: with ONNX disabled, falls back to spectral_basis_v2 while other services work."""
    code = (
        "import sys\n"
        "sys.modules['onnxruntime'] = None\n"
        "from services.agribrain.layer1_fusion.eo_foundation_model import EOFoundationModel\n"
        "model = EOFoundationModel()\n"
        "bands = {\n"
        "    'B2': [[0.1, 0.2], [0.3, 0.4]],\n"
        "    'B3': [[0.1, 0.2], [0.3, 0.4]],\n"
        "    'B4': [[0.1, 0.2], [0.3, 0.4]],\n"
        "    'B8': [[0.4, 0.5], [0.6, 0.7]],\n"
        "}\n"
        "res = model.infer(bands)\n"
        "assert res is not None\n"
        "assert res.model_id == 'spectral_basis_v2', f'Expected spectral_basis_v2, got {res.model_id}'\n"
        "assert res.confidence > 0.0\n"
        "from services.agribrain.layer0.data_gateway import broker\n"
        "from services.agribrain.layer1_fusion.segmentation import ZonalSegmentationEngine\n"
        "from services.agribrain.drone_mission.planner import DroneMissionPlanner\n"
        "from services.agribrain.irrigation_runtime.dispatcher import CommandDispatcher\n"
        "from services.agribrain.irrigation_runtime.safety import SafetyMonitor, SharedQuotaStore\n"
        "assert broker is not None\n"
        "seg = ZonalSegmentationEngine(n_zones=2)\n"
        "assert seg is not None\n"
        "planner = DroneMissionPlanner()\n"
        "assert planner is not None\n"
        "dispatcher = CommandDispatcher()\n"
        "assert dispatcher is not None\n"
        "safety = SafetyMonitor()\n"
        "assert safety is not None\n"
        "assert SharedQuotaStore is not None\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, f"Optional backend isolation failed: {res.stderr}\nStdout: {res.stdout}"


# ============================================================================
# F39: Sensor Nonce Atomic Concurrency & Replay Protection
# ============================================================================

def test_f39_sequential_nonce_replay(tmp_path):
    from services.agribrain.sensor_runtime.security import detect_replay
    os.environ["AGRIWISE_SENSOR_NONCE_STORE_PATH"] = str(tmp_path / "replay_nonces.json")
    try:
        seen = set()
        test_nonce = f"test_seq_{uuid.uuid4().hex}"
        # First attempt: not a replay
        assert detect_replay(test_nonce, seen) is False
        # Second attempt: replay detected
        assert detect_replay(test_nonce, seen) is True
    finally:
        os.environ.pop("AGRIWISE_SENSOR_NONCE_STORE_PATH", None)


def test_f39_concurrent_nonce_single_winner(tmp_path):
    from services.agribrain.sensor_runtime.security import detect_replay
    os.environ["AGRIWISE_SENSOR_NONCE_STORE_PATH"] = str(tmp_path / "replay_nonces.json")
    try:
        seen = set()
        test_nonce = f"test_race_{uuid.uuid4().hex}"

        def worker():
            return detect_replay(test_nonce, seen)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(lambda _: worker(), range(10)))

        # Exactly 1 winner admitted (False), 9 rejected (True)
        assert results.count(False) == 1
        assert results.count(True) == 9
    finally:
        os.environ.pop("AGRIWISE_SENSOR_NONCE_STORE_PATH", None)


def test_f39_concurrent_distinct_nonces_no_lost_updates(tmp_path):
    from services.agribrain.sensor_runtime.security import detect_replay, load_nonces
    store_file = tmp_path / "replay_nonces.json"
    os.environ["AGRIWISE_SENSOR_NONCE_STORE_PATH"] = str(store_file)
    try:
        seen = set()
        num_nonces = 30
        distinct_ids = [f"distinct_{uuid.uuid4().hex}" for _ in range(num_nonces)]

        def worker(nonce_id):
            return detect_replay(nonce_id, seen)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(worker, distinct_ids))

        # All 30 must be newly admitted
        assert results.count(False) == num_nonces

        # Store on disk must contain all 30 nonces without any lost updates
        stored = load_nonces()
        for nid in distinct_ids:
            assert nid in stored
    finally:
        os.environ.pop("AGRIWISE_SENSOR_NONCE_STORE_PATH", None)


# ============================================================================
# World Model / Forecast Archive Contamination & Scoring Gaps
# ============================================================================

def test_forecast_empty_quantiles_crps_rejects_zero_score():
    from services.agribrain.world_model.forecast_archive import compute_crps_quantiles
    with pytest.raises(ContractViolation, match="Cannot compute CRPS"):
        compute_crps_quantiles({}, 0.25)


def test_forecast_archive_rejects_contaminated_forecast(tmp_path):
    from services.agribrain.world_model.forecast_archive import ImmutableForecastArchive, ForecastRecord
    archive = ImmutableForecastArchive(root=tmp_path)
    now = datetime.datetime.now(timezone.utc)
    target = now + datetime.timedelta(days=3)

    rejected_fc = ForecastRecord(
        forecast_id="fc-rejected-001",
        plot_id="plot_test",
        target_variable="soil_vwc",
        issued_at_knowledge_time=now,
        target_epoch=target,
        horizon_days=3.0,
        predicted_quantiles={"p50": 0.25},
        metadata={"status": "rejected", "rejection_reason": "bad_model_divergence"},
    )
    with pytest.raises(ContractViolation, match="Rejected forecast"):
        archive.store_forecast(rejected_fc)


def test_asmae_cache_refuses_rejected_spatial_results():
    from services.agribrain.layer05_asmae.cache import serialize_and_cache_asmae
    from services.agribrain.layer05_asmae.schema import ASMAEInput

    inp = ASMAEInput(
        run_id="run_rej_01",
        plot_id="plot_rej_01",
        polygon_geojson={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
        geometry_hash="hash_rej_01",
        start_date="2026-07-01",
        end_date="2026-07-31",
        layer0_source_packages={},
    )
    output_rejected = {
        "result_status": "rejected",
        "reason": "quality_floor_violation",
        "is_rejected": True,
    }
    assert serialize_and_cache_asmae(inp, output_rejected) is False


# ============================================================================
# F11 & F15 Remediation Verifications
# ============================================================================

def test_f11_residual_nitrogen_fixture_matches_canonical_86_67():
    from services.agribrain.layer4_nutrients.photosynthesis_nue.engine import PhotosynthesisNUEEngine
    engine = PhotosynthesisNUEEngine()
    # In the plan's fixture: 5 t/ha biomass, 2.0% critical N, 50 kg applied, 30 kg soil supply, 0.60 recovery
    engine._estimate_biomass = lambda *args, **kwargs: 5.0
    engine._critical_n_concentration = lambda *args, **kwargs: 2.0
    res = engine.analyze(
        crop_type="wheat",
        n_applied_kg_ha=50.0,
        soil_n_supply_kg_ha=30.0,
    )
    # Total available = 50 + 30 = 80 kg. Recovered plant N = 80 * 0.60 = 48 kg.
    # actual_n_pct = 48 / (5 * 10) = 0.96%.
    # Deficit = 2.0% - 0.96% = 1.04%.
    # Additional N needed = 1.04 * 5.0 * 10.0 / 0.60 = 52.0 / 0.60 = 86.67 kg/ha
    assert res.optimal_n_rate_kg_ha == pytest.approx(86.67, abs=0.01)


def test_f15_leaching_safety_cap_does_not_expand_past_ceiling():
    from services.agribrain.layer8_prescriptive.engines.salinity_leaching import SalinityLeachingEngine
    from services.agribrain.layer8_prescriptive.schema import (
        ActionCard, ActionType, RateRange, PriorityBreakdown, PrescriptiveEvidence, ConfidenceLevel
    )
    engine = SalinityLeachingEngine()
    card = ActionCard(
        action_id="CARD_LEACH_01",
        action_type=ActionType.IRRIGATE,
        priority_score=0.8,
        priority_breakdown=PriorityBreakdown(
            impact_score=0.8, urgency_score=0.7, risk_score=0.2, cost_score=0.3, confidence_score=0.9
        ),
        zone_targets=["zone_1"],
        zone_allocation={"zone_1": 1.0},
        rate=RateRange(recommended=20.0, min_safe=5.0, max_safe=21.0, unit="mm"),
        evidence=[
            PrescriptiveEvidence(
                source_layer="L3", evidence_type="diagnosis", reference_id="REF1", contribution=0.8, description="Leaching required"
            )
        ],
        confidence=ConfidenceLevel.HIGH,
        explain="Salinity leaching test",
    )
    # Soil EC = 8.0 dS/m (above threshold 1.7 for corn), water EC = 1.0 -> LR required
    res_cards = engine.adjust_irrigation_for_salinity([card], crop="corn", soil_salinity_ece=8.0, water_salinity_ecw=1.0)
    res = res_cards[0]
    # The max_safe hard cap of 21.0 must not expand to 27.7 mm!
    assert res.rate.recommended <= 21.0
    assert res.rate.max_safe == 21.0


def test_f15_spray_drift_gate_blocks_on_missing_weather_forecast():
    from services.agribrain.layer8_prescriptive.engines.spray_drift_gate import SprayDriftGateEngine
    from services.agribrain.layer8_prescriptive.schema import (
        ActionCard, ActionType, RateRange, PriorityBreakdown, PrescriptiveEvidence, ConfidenceLevel
    )
    engine = SprayDriftGateEngine()
    card = ActionCard(
        action_id="CARD_SPRAY_01",
        action_type=ActionType.SPRAY,
        priority_score=0.8,
        priority_breakdown=PriorityBreakdown(
            impact_score=0.8, urgency_score=0.7, risk_score=0.2, cost_score=0.3, confidence_score=0.9
        ),
        zone_targets=["zone_1"],
        zone_allocation={"zone_1": 1.0},
        rate=RateRange(recommended=2.0, min_safe=1.0, max_safe=5.0, unit="L/ha"),
        evidence=[
            PrescriptiveEvidence(
                source_layer="L5", evidence_type="threat", reference_id="REF_PEST", contribution=0.8, description="Pest threat"
            )
        ],
        confidence=ConfidenceLevel.HIGH,
        explain="Spray action",
    )
    # Missing/empty wind forecast must fail closed
    res_cards = engine.enforce_drift_limits([card], forecast=[{}])
    assert res_cards[0].is_allowed is False
    assert any("Spray blocked" in r for r in res_cards[0].blocked_reason)


def test_f15_salinity_hard_envelopes():
    import math
    from services.agribrain.layer8_prescriptive.engines.salinity_leaching import SalinityLeachingEngine
    from services.agribrain.layer8_prescriptive.schema import (
        ActionCard, ActionType, RateRange, PriorityBreakdown, PrescriptiveEvidence, ConfidenceLevel
    )
    from services.agribrain.layer8_prescriptive.invariants import enforce_layer8_invariants
    from services.agribrain.layer8_prescriptive.schema import Layer8Output, ScheduledAction, ScheduleStatus, OutcomeForecast

    engine = SalinityLeachingEngine()

    def make_card(rec=20.0, min_s=0.0, max_s=21.0):
        return ActionCard(
            action_id="CARD_TEST",
            action_type=ActionType.IRRIGATE,
            priority_score=0.5,
            priority_breakdown=PriorityBreakdown(0.5, 0.5, 0.5, 0.5, 0.5),
            zone_targets=["zone_1"],
            zone_allocation={"zone_1": 1.0},
            rate=RateRange(recommended=rec, min_safe=min_s, max_safe=max_s, unit="mm"),
            evidence=[PrescriptiveEvidence("L3", "diagnosis", "REF1", 0.8, "salinity", source_type="sensor"),
                      PrescriptiveEvidence("L2", "observation", "REF2", 0.5, "satellite", source_type="satellite")],
            confidence=ConfidenceLevel.HIGH,
            explain="salinity test",
        )

    # 1. Negative cap (-1.0) -> clamped safely to 0.0, never negative
    c = make_card(rec=20.0, min_s=0.0, max_s=-1.0)
    res = engine.adjust_irrigation_for_salinity([c], crop="potato", soil_salinity_ece=3.0)[0]
    assert res.rate.recommended >= 0.0
    assert res.rate.max_safe == 0.0

    # 2. None cap -> no TypeError, recommended rate adjusted
    c = make_card(rec=20.0, min_s=0.0, max_s=None)
    res = engine.adjust_irrigation_for_salinity([c], crop="potato", soil_salinity_ece=3.0)[0]
    assert res.rate.recommended > 20.0
    assert res.rate.max_safe is None

    # 3. NaN cap -> clamped safely to 0.0
    c = make_card(rec=20.0, min_s=0.0, max_s=float("nan"))
    res = engine.adjust_irrigation_for_salinity([c], crop="potato", soil_salinity_ece=3.0)[0]
    assert res.rate.recommended >= 0.0
    assert res.rate.max_safe == 0.0

    # 4. Inf cap -> clamped safely to 0.0
    c = make_card(rec=20.0, min_s=0.0, max_s=float("inf"))
    res = engine.adjust_irrigation_for_salinity([c], crop="potato", soil_salinity_ece=3.0)[0]
    assert res.rate.recommended >= 0.0
    assert res.rate.max_safe == 0.0

    # 5. Bool cap (True) -> clamped safely to 0.0, not boolean
    c = make_card(rec=20.0, min_s=0.0, max_s=True)
    res = engine.adjust_irrigation_for_salinity([c], crop="potato", soil_salinity_ece=3.0)[0]
    assert res.rate.recommended == 0.0
    assert not isinstance(res.rate.recommended, bool)

    # 6. Inconsistent min_safe > max_safe (min 25, max 21) -> clamped min_safe = 21, recommended = 21
    c = make_card(rec=20.0, min_s=25.0, max_s=21.0)
    res = engine.adjust_irrigation_for_salinity([c], crop="potato", soil_salinity_ece=3.0)[0]
    assert res.rate.min_safe == 21.0
    assert res.rate.max_safe == 21.0
    assert res.rate.recommended == 21.0

    # 7. Negative recommended (-2.0) with min_safe (5.0) -> adjusted to min_safe (5.0)
    c = make_card(rec=-2.0, min_s=5.0, max_s=21.0)
    res = engine.adjust_irrigation_for_salinity([c], crop="potato", soil_salinity_ece=3.0)[0]
    assert res.rate.recommended == 5.0
    assert res.rate.min_safe == 5.0

    # 8. Positive rate zero cap (rec=20.0, max_safe=0.0) -> clamped to 0.0
    c = make_card(rec=20.0, min_s=0.0, max_s=0.0)
    res = engine.adjust_irrigation_for_salinity([c], crop="potato", soil_salinity_ece=3.0)[0]
    assert res.rate.recommended == 0.0
    assert res.rate.max_safe == 0.0


def test_f15_scheduler_weather_and_envelope_qualification():
    from datetime import datetime
    from services.agribrain.layer8_prescriptive.scheduler import ConstraintScheduler
    from services.agribrain.layer8_prescriptive.schema import (
        ActionCard, ActionType, RateRange, PriorityBreakdown, PrescriptiveEvidence, ConfidenceLevel, ScheduleStatus
    )

    scheduler = ConstraintScheduler()

    def make_spray_card(rec=2.0, min_s=1.0, max_s=5.0):
        return ActionCard(
            action_id="CARD_SPRAY_TEST",
            action_type=ActionType.SPRAY,
            priority_score=0.8,
            priority_breakdown=PriorityBreakdown(0.8, 0.7, 0.2, 0.3, 0.9),
            zone_targets=["zone_1"],
            zone_allocation={"zone_1": 1.0},
            rate=RateRange(recommended=rec, min_safe=min_s, max_safe=max_s, unit="L/ha"),
            evidence=[PrescriptiveEvidence("L5", "threat", "REF_PEST", 0.8, "Pest", source_type="sensor"),
                      PrescriptiveEvidence("L2", "observation", "REF2", 0.5, "satellite", source_type="satellite")],
            confidence=ConfidenceLevel.HIGH,
            explain="Spray action",
        )

    base_date = datetime(2026, 10, 13)

    # 1. Invalid rate envelope (NaN / Inf) blocks action card in scheduler
    c_nan = make_spray_card(rec=float("nan"))
    sched = scheduler.schedule_actions([c_nan], [{"date": "2026-10-14", "wind_speed": 5.0, "precip_mm": 0.0, "temp_max": 25.0, "temp_min": 10.0}], base_date)[0]
    assert sched.status == ScheduleStatus.BLOCKED
    assert not c_nan.is_allowed

    # 2. String numeric wind ('5') converts cleanly and confirms
    c = make_spray_card()
    sched = scheduler.schedule_actions([c], [{"date": "2026-10-14", "wind_speed": "5", "precip_mm": 0.0, "temp_max": 25.0, "temp_min": 10.0}], base_date)[0]
    assert sched.status == ScheduleStatus.CONFIRMED

    # 3. Empty string wind ('') blocks without TypeError
    c = make_spray_card()
    sched = scheduler.schedule_actions([c], [{"date": "2026-10-14", "wind_speed": "", "precip_mm": 0.0, "temp_max": 25.0, "temp_min": 10.0}], base_date)[0]
    assert sched.status == ScheduleStatus.BLOCKED

    # 4. m/s units conversion (10 m/s = 36 km/h) blocks spray (> 15 km/h)
    c = make_spray_card()
    sched = scheduler.schedule_actions([c], [{"date": "2026-10-14", "wind_speed": 10.0, "wind_speed_unit": "m/s", "precip_mm": 0.0, "temp_max": 25.0, "temp_min": 10.0}], base_date)[0]
    assert sched.status == ScheduleStatus.BLOCKED

    # 5. Wind gust higher than speed (speed 5, gust 20) blocks spray (> 15 km/h)
    c = make_spray_card()
    sched = scheduler.schedule_actions([c], [{"date": "2026-10-14", "wind_speed": 5.0, "wind_gust": 20.0, "precip_mm": 0.0, "temp_max": 25.0, "temp_min": 10.0}], base_date)[0]
    assert sched.status == ScheduleStatus.BLOCKED

    # 6. Chronological ordering: dated_forward vs dated_reverse both select safe day (2026-10-15)
    fc_forward = [
        {"date": "2026-10-15", "wind_speed": 5.0, "precip_mm": 0.0, "temp_max": 25.0, "temp_min": 10.0},
        {"date": "2026-10-14", "wind_speed": 20.0, "precip_mm": 0.0, "temp_max": 25.0, "temp_min": 10.0},
    ]
    fc_reverse = [
        {"date": "2026-10-14", "wind_speed": 20.0, "precip_mm": 0.0, "temp_max": 25.0, "temp_min": 10.0},
        {"date": "2026-10-15", "wind_speed": 5.0, "precip_mm": 0.0, "temp_max": 25.0, "temp_min": 10.0},
    ]
    c1 = make_spray_card()
    c2 = make_spray_card()
    s1 = scheduler.schedule_actions([c1], fc_forward, base_date)[0]
    s2 = scheduler.schedule_actions([c2], fc_reverse, base_date)[0]
    assert s1.status == ScheduleStatus.CONFIRMED and s1.scheduled_date == "2026-10-15"
    assert s2.status == ScheduleStatus.CONFIRMED and s2.scheduled_date == "2026-10-15"

