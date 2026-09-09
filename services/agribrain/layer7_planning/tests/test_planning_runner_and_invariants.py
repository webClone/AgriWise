from datetime import datetime
from types import SimpleNamespace
import math
import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from orchestrator_v2.schema import OrchestratorInput, LayerResult, LayerStatus
from layer7_planning.runner import run, _compute_soil_health_trajectory
from layer7_planning.schema import Layer7Output, YieldDistribution, EconomicOutcome, SuitabilityState, EvidenceLogit, SuitabilityDriver
from layer7_planning.invariants import enforce_layer7_invariants
from layer7_planning.engines.ccl_crop_library import CROP_DATABASE


def _build_valid_l1_fixture(num_days: int = 14):
    ts = []
    for i in range(num_days):
        ts.append({
            "is_observed": True,
            "ndvi_mean": 0.45,
            "rain": 5.0,
            "precipitation": 5.0,
            "tmean": 18.0,
            "t_mean": 18.0,
            "temp_max": 25.0,
            "temp_min": 12.0,
            "t_min": 12.0,
            "et0": 3.5,
            "solar_radiation": 500.0,
            "rh": 50.0,
            "wind_speed": 2.5,
            "vv": -12.0,
        })
    forecast_7d = [
        {
            "source": "ecmwf",
            "temp_max": 24.0,
            "temp_min": 11.0,
            "precipitation": 2.0,
            "rain_prob": 0.1,
        }
        for _ in range(7)
    ]
    static = {"texture_class": "loam"}
    return SimpleNamespace(
        plot_timeseries=ts,
        forecast_7d=forecast_7d,
        static=static,
        spatial_zone_stats=[],
    )


def test_sar_soil_health_trajectory():
    """Verify tillage detection and degradation scoring from Sentinel-1 VV backscatter."""
    # 1. Missing or empty L1 returns neutral prior
    res_empty = _compute_soil_health_trajectory(None)
    assert res_empty["soil_health_score"] == 0.7
    assert res_empty["trajectory"] == "STABLE"

    # 2. Stable no-till series (15 observations, constant VV = -12.0 dB)
    ts_clean = [{"vv": -12.0} for _ in range(15)]
    l1_clean = SimpleNamespace(plot_timeseries=ts_clean)
    res_clean = _compute_soil_health_trajectory(l1_clean)
    assert res_clean["tillage_events"] == 0
    assert res_clean["soil_health_score"] == 1.0
    assert res_clean["trajectory"] == "IMPROVING"

    # 3. Series with multiple sudden VV spikes (> 3 dB) indicating repeated tillage
    vv_spiky = [-12.0] * 5 + [-8.0] + [-12.0] * 5 + [-8.0] + [-12.0] * 5 + [-7.0] + [-12.0] * 5 + [-7.0]
    ts_spiky = [{"vv": v} for v in vv_spiky]
    l1_spiky = SimpleNamespace(plot_timeseries=ts_spiky)
    res_spiky = _compute_soil_health_trajectory(l1_spiky)
    assert res_spiky["tillage_events"] >= 3
    assert res_spiky["soil_health_score"] <= 0.6


def test_layer7_runner_end_to_end():
    """Verify full end-to-end execution of Layer 7 with deterministic run_id and DAG."""
    ns = PlotNamespace(tenant_id="T01", farm_id="FARM01", plot_id="P01")
    inputs = OrchestratorInput(
        plot_id="P01",
        plot_namespace=ns,
        date_range={"start": "2026-03-01", "end": "2026-03-15"},
        crop_config={"crop": "wheat", "crop_type": "wheat", "declared_crop_code": "wheat"},
        geometry_hash="geo_hash_123",
    )
    l1_res = _build_valid_l1_fixture(14)

    result = run(inputs, l1_res)
    # The runner returns a LayerResult wrapping Layer7Output
    assert result is not None
    assert result.status in ("SUCCESS", LayerStatus.OK)

    output = result.output if hasattr(result, "output") else result
    assert isinstance(output, Layer7Output)

    # Deterministic run_id
    assert output.run_meta.run_id.startswith("L7-")
    assert output.run_id == output.run_meta.run_id

    # Evaluated target crop and alternatives
    assert len(output.options) >= 2
    target_opt = next((o for o in output.options if o.crop.lower() == "wheat"), None)
    assert target_opt is not None
    assert 0.0 <= target_opt.suitability_percentage <= 100.0
    assert target_opt.overall_rank_score >= 0.0

    # Chosen plan & Execution plan DAG
    assert output.chosen_plan is not None
    assert output.chosen_plan.decision_id is not None
    assert output.execution_plan is not None
    assert len(output.execution_plan.tasks) > 0

    # Content hash
    h = output.content_hash()
    assert isinstance(h, str) and len(h) >= 16


def test_layer7_invariants_clean_and_violations():
    """Verify production invariant suite passes on valid output and flags corruptions."""
    ns = PlotNamespace(tenant_id="T01", farm_id="FARM01", plot_id="P01")
    inputs = OrchestratorInput(
        plot_id="P01",
        plot_namespace=ns,
        date_range={"start": "2026-03-01", "end": "2026-03-15"},
        crop_config={"crop": "wheat"},
        geometry_hash="geo_123",
    )
    l1_res = _build_valid_l1_fixture(14)
    res = run(inputs, l1_res)
    output: Layer7Output = res.output if hasattr(res, "output") else res

    # 1. Clean output has 0 error violations
    violations = enforce_layer7_invariants(output, CROP_DATABASE)
    errors = [v for v in violations if v.severity == "error"]
    assert len(errors) == 0

    # 2. Corrupt yield percentile order (p10 > p50)
    opt = output.options[0]
    opt.yield_dist.p10 = 10.0
    opt.yield_dist.p50 = 5.0
    v_order = enforce_layer7_invariants(output, CROP_DATABASE)
    assert any(v.check_name == "yield_percentile_order" for v in v_order)
    # Restore
    opt.yield_dist.p10 = 3.0
    opt.yield_dist.p50 = 5.0

    # 3. Corrupt profit with infinity
    opt.econ.expected_profit = math.inf
    v_inf = enforce_layer7_invariants(output, CROP_DATABASE)
    assert any(v.check_name == "profit_finite" for v in v_inf)
    opt.econ.expected_profit = 700.0


def test_layer7_tier0_blockers():
    """Verify runner halts gracefully when Tier 0 required evidence is missing."""
    ns = PlotNamespace(tenant_id="T01", farm_id="FARM01", plot_id="P01")
    inputs = OrchestratorInput(
        plot_id="P01",
        plot_namespace=ns,
        date_range={"start": "2026-03-01", "end": "2026-03-15"},
        crop_config={"crop": "wheat"},
    )

    # 1. L1 lacks observed NDVI
    l1_no_ndvi = SimpleNamespace(
        plot_timeseries=[{"is_observed": False, "rain": 5.0, "tmean": 15.0}],
        forecast_7d=[{"source": "ecmwf", "temp_max": 20, "temp_min": 10, "precipitation": 1}],
        static={"texture_class": "loam"},
    )
    res_blocked = run(inputs, l1_no_ndvi)
    assert res_blocked.status == "DEGRADED"
    assert any("no_observed_ndvi" in err for err in res_blocked.errors)

    # 2. Unsupported crop identity
    inputs_bad_crop = OrchestratorInput(
        plot_id="P01",
        plot_namespace=ns,
        date_range={"start": "2026-03-01", "end": "2026-03-15"},
        crop_config={"crop": "unknown_crypto_tree_123"},
    )
    l1_valid = _build_valid_l1_fixture(14)
    res_bad = run(inputs_bad_crop, l1_valid)
    assert res_bad.status in (LayerStatus.FAILED, "FAILED")
