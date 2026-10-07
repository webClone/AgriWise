"""
Unit and regression tests for Stage 03 Work Packages F06, F07, and F08:
- F06: Weather forcing alignment & exact date matching without synthetic or future date leakage.
- F07: Canopy date eligibility, removal of future canopy fallback, evaporation memory continuity,
       and actual layer thickness surface storage with method-specific wetting fractions.
- F08: Comprehensive soil parameter state digests, predecessor hashing, and trajectory invalidation.
"""

from __future__ import annotations

import datetime
from datetime import timezone
import pytest

from services.agribrain.layer3_water.contracts import (
    SoilWaterState,
    WaterStateFactory,
    HydrologyMode,
    IrrigationMethod,
)
from services.agribrain.layer3_water.soil import SoilProfileDatabase
from services.agribrain.layer3_water.runner import WaterIntelligenceEngine
from services.agribrain.layer2_contracts.state_contracts import VegetationState
from services.agribrain.layer3_decision.runner import _execute_canonical_water_engine, _PLOT_WATER_STATE_HISTORY


def _make_base_weather(precip: float = 0.0) -> dict:
    return {
        "t_max_c": 28.0,
        "t_min_c": 15.0,
        "precipitation_mm": precip,
        "wind_speed_2m_m_s": 2.1,
        "rh_min_pct": 35.0,
        "rh_max_pct": 85.0,
        "net_radiation_mj_m2": 18.5,
    }


class DummyInputs:
    def __init__(self, plot_id: str = "P_TEST_F06_08", op_ctx: dict | None = None):
        self.plot_id = plot_id
        self.operational_context = op_ctx or {}


# ============================================================================
# F06 Tests: Weather Forcing Alignment & Exact Date Matching
# ============================================================================

def test_f06_weather_matching_exact_date_no_future_leakage():
    """Verify that Jan 2 step receives exact Jan 2 weather and does NOT leak Jan 3 weather."""
    plot_id = "PLOT_F06_EXACT"
    _PLOT_WATER_STATE_HISTORY.pop(plot_id, None)

    # Context with weather on 2026-06-01 (dry) and 2026-06-02 (rain 50mm)
    w_june1 = _make_base_weather(precip=0.0)
    w_june1["date"] = "2026-06-01"
    w_june2 = _make_base_weather(precip=50.0)
    w_june2["date"] = "2026-06-02"

    op_ctx = {
        "weather_daily": {
            "2026-06-01": w_june1,
            "2026-06-02": w_june2,
        }
    }
    inputs = DummyInputs(plot_id=plot_id, op_ctx=op_ctx)

    # Request run for June 1: must match June 1 (precip=0.0), NOT June 2 rain
    run_ts = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    w_state, _ = _execute_canonical_water_engine(inputs, None, None, run_timestamp=run_ts)

    assert w_state is not None
    assert w_state.fluxes.actual.precipitation_mm == 0.0


def test_f06_missing_weather_preserves_missingness():
    """Verify that if requested day has no weather observation, missingness is preserved (returns None)."""
    plot_id = "PLOT_F06_MISSING"
    _PLOT_WATER_STATE_HISTORY.pop(plot_id, None)

    # Weather provided only for June 5, but run is for June 1
    w_june5 = _make_base_weather(precip=10.0)
    w_june5["date"] = "2026-06-05"

    op_ctx = {
        "weather_daily": {
            "2026-06-05": w_june5,
        }
    }
    inputs = DummyInputs(plot_id=plot_id, op_ctx=op_ctx)
    run_ts = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    # Must preserve missingness and return None, None
    w_state, receipt = _execute_canonical_water_engine(inputs, None, None, run_timestamp=run_ts)
    assert w_state is None
    assert receipt is None


# ============================================================================
# F07 Tests: Canopy Eligibility, Evaporation Memory, Top Storage Thickness
# ============================================================================

def test_f07_top_storage_derived_from_actual_layer_thickness():
    """Verify that top surface storage uses layer_depths_cm[0] rather than hardcoded 100mm."""
    loam = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam")
    theta_top = loam.theta_profile[0]

    # Standard loam has layer_depths_cm[0] = 10.0 (100 mm)
    # top_storage = theta_top * 100.0
    w_state_100, _ = WaterIntelligenceEngine.execute_pipeline(
        plot_id="PLOT_F07_THICK_10",
        timestamp=datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        weather_observations=_make_base_weather(),
        soil_profile_state=loam,
    )

    # Create soil with a thin 5 cm (50 mm) top layer: [5.0, 30.0, 60.0, 100.0, 200.0]
    thin_soil = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=[5.0, 30.0, 60.0, 100.0, 200.0],
        theta_profile=loam.theta_profile,
        field_capacity_profile=loam.field_capacity_profile,
        wilting_point_profile=loam.wilting_point_profile,
        saturation_profile=loam.saturation_profile,
        residual_profile=loam.residual_profile,
        hydraulic_conductivity_profile=loam.hydraulic_conductivity_profile,
        van_genuchten_alpha=loam.van_genuchten_alpha,
        van_genuchten_n=loam.van_genuchten_n,
    )

    w_state_50, _ = WaterIntelligenceEngine.execute_pipeline(
        plot_id="PLOT_F07_THICK_5",
        timestamp=datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        weather_observations=_make_base_weather(),
        soil_profile_state=thin_soil,
    )

    assert w_state_100 is not None
    assert w_state_50 is not None
    # Maximum REW on thin soil must be smaller than 10cm soil
    assert (
        w_state_50.soil_water.evaporation_state.max_surface_storage_mm
        < w_state_100.soil_water.evaporation_state.max_surface_storage_mm
    )


def test_f07_historical_steps_do_not_leak_future_canopy():
    """Verify that earlier historical steps never consume later observed canopy."""
    plot_id = "PLOT_F07_CANOPY"
    _PLOT_WATER_STATE_HISTORY.pop(plot_id, None)

    # Multi-day weather: June 1, June 2, June 3
    weather_dict = {
        "2026-06-01": {**_make_base_weather(), "date": "2026-06-01"},
        "2026-06-02": {**_make_base_weather(), "date": "2026-06-02"},
        "2026-06-03": {**_make_base_weather(), "date": "2026-06-03"},
    }

    # Today is June 3, with a lush canopy LAI=4.0
    future_veg = VegetationState(
        plot_id=plot_id,
        timestamp=datetime.datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
        lai=4.0,
        fvc=0.9,
        root_depth_proxy_m=1.2,
    )

    op_ctx = {
        "weather_daily": weather_dict,
        "vegetation_state": future_veg,
    }
    inputs = DummyInputs(plot_id=plot_id, op_ctx=op_ctx)

    # Run for June 3 (which backfills June 1, June 2)
    run_ts = datetime.datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    w_state, _ = _execute_canonical_water_engine(inputs, None, None, run_timestamp=run_ts)

    assert w_state is not None
    # Check history in _PLOT_WATER_STATE_HISTORY[plot_id]
    hist = _PLOT_WATER_STATE_HISTORY.get(plot_id, {})
    june1_entry = hist.get("2026-06-01")
    assert june1_entry is not None
    # Historical June 1 had no past observation, so step_veg should be None (not future_veg with LAI=4.0)
    assert june1_entry.get("vegetation_state") is None


def test_f07_evaporation_memory_advances_across_dry_days():
    """Verify that days_since_wetting accumulates across dry steps in trajectory rollout."""
    plot_id = "PLOT_F07_EVAP_MEM"
    _PLOT_WATER_STATE_HISTORY.pop(plot_id, None)

    # 3 dry days
    weather_dict = {
        "2026-06-01": {**_make_base_weather(precip=0.0), "date": "2026-06-01"},
        "2026-06-02": {**_make_base_weather(precip=0.0), "date": "2026-06-02"},
        "2026-06-03": {**_make_base_weather(precip=0.0), "date": "2026-06-03"},
    }
    op_ctx = {"weather_daily": weather_dict}
    inputs = DummyInputs(plot_id=plot_id, op_ctx=op_ctx)

    run_ts = datetime.datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    w_state, _ = _execute_canonical_water_engine(inputs, None, None, run_timestamp=run_ts)

    assert w_state is not None
    hist = _PLOT_WATER_STATE_HISTORY[plot_id]
    d1_days = hist["2026-06-01"]["water_state"].soil_water.evaporation_state.days_since_wetting
    d2_days = hist["2026-06-02"]["water_state"].soil_water.evaporation_state.days_since_wetting
    d3_days = hist["2026-06-03"]["water_state"].soil_water.evaporation_state.days_since_wetting

    # Evaporation memory advances strictly: 1 -> 2 -> 3
    assert d1_days == 1
    assert d2_days == 2
    assert d3_days == 3


def test_f07_method_specific_wetted_fraction():
    """Verify that drip irrigation produces localized wetting (fw=0.35) while rain wets fully (fw=1.0)."""
    soil = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam")
    weather = _make_base_weather(precip=0.0)

    # Apply 10 mm via DRIP
    w_drip, _ = WaterIntelligenceEngine.execute_pipeline(
        plot_id="PLOT_F07_DRIP",
        timestamp=datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        weather_observations=weather,
        soil_profile_state=soil,
        irrigation_applied_mm=10.0,
        irrigation_method=IrrigationMethod.DRIP,
    )
    assert w_drip.soil_water.evaporation_state.few_exposed_wetted_fraction == pytest.approx(0.35, abs=0.05)

    # Apply 10 mm via SPRINKLER
    w_sprinkler, _ = WaterIntelligenceEngine.execute_pipeline(
        plot_id="PLOT_F07_SPRINKLER",
        timestamp=datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        weather_observations=weather,
        soil_profile_state=soil,
        irrigation_applied_mm=10.0,
        irrigation_method=IrrigationMethod.SPRINKLER,
    )
    assert w_sprinkler.soil_water.evaporation_state.few_exposed_wetted_fraction == pytest.approx(1.0, abs=0.05)


# ============================================================================
# F08 Tests: Parameter Invalidation & Predecessor Trajectory Hashing
# ============================================================================

def test_f08_identical_moisture_with_different_conductivity_produces_different_digest():
    """Verify that two soil states with identical moisture but different Ks produce distinct digests."""
    loam = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam")

    # Soil A: Ks = [25.0, 25.0, ...]
    soil_a = loam

    # Soil B: identical depths and theta, but Ks = [5.0, 5.0, ...]
    soil_b = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=loam.layer_depths_cm,
        theta_profile=loam.theta_profile,
        field_capacity_profile=loam.field_capacity_profile,
        wilting_point_profile=loam.wilting_point_profile,
        saturation_profile=loam.saturation_profile,
        residual_profile=loam.residual_profile,
        hydraulic_conductivity_profile=[5.0] * len(loam.layer_depths_cm),
        van_genuchten_alpha=loam.van_genuchten_alpha,
        van_genuchten_n=loam.van_genuchten_n,
    )

    from services.agribrain.layer3_decision.runner import _execute_canonical_water_engine
    # Digest can be tested via trajectory execution or helper
    plot_id = "PLOT_F08_DIGEST"
    _PLOT_WATER_STATE_HISTORY.pop(plot_id, None)

    weather_dict = {"2026-06-01": {**_make_base_weather(), "date": "2026-06-01"}}
    run_ts = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    # Run with Soil A
    inputs_a = DummyInputs(plot_id=plot_id, op_ctx={"weather_daily": weather_dict, "soil_profile_state": soil_a})
    _execute_canonical_water_engine(inputs_a, None, None, run_timestamp=run_ts)
    hash_a = _PLOT_WATER_STATE_HISTORY[plot_id]["2026-06-01"]["step_forcing_hash"]

    # Clear cache and run with Soil B
    _PLOT_WATER_STATE_HISTORY.pop(plot_id, None)
    inputs_b = DummyInputs(plot_id=plot_id, op_ctx={"weather_daily": weather_dict, "soil_profile_state": soil_b})
    _execute_canonical_water_engine(inputs_b, None, None, run_timestamp=run_ts)
    hash_b = _PLOT_WATER_STATE_HISTORY[plot_id]["2026-06-01"]["step_forcing_hash"]

    # They MUST have different hashes
    assert hash_a != hash_b


def test_f08_soil_parameter_change_invalidates_cached_trajectory():
    """Verify that updating soil parameter invalidates previously cached transitions and triggers recomputation."""
    plot_id = "PLOT_F08_INVALIDATION"
    _PLOT_WATER_STATE_HISTORY.pop(plot_id, None)

    weather_dict = {
        "2026-06-01": {**_make_base_weather(), "date": "2026-06-01"},
        "2026-06-02": {**_make_base_weather(), "date": "2026-06-02"},
    }
    loam = SoilProfileDatabase.get_canonical_soil_profile(soil_type="loam")
    # Step 1: Run June 1 with standard loam
    run_ts1 = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    inputs_1 = DummyInputs(plot_id=plot_id, op_ctx={"weather_daily": weather_dict, "soil_profile_state": loam})
    w1, _ = _execute_canonical_water_engine(inputs_1, None, None, run_timestamp=run_ts1)
    initial_h1 = _PLOT_WATER_STATE_HISTORY[plot_id]["2026-06-01"]["step_forcing_hash"]

    # Step 2: Run June 2 advancing from June 1 predecessor
    run_ts2 = datetime.datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    inputs_2 = DummyInputs(plot_id=plot_id, op_ctx={"weather_daily": weather_dict})
    w2, _ = _execute_canonical_water_engine(inputs_2, None, None, run_timestamp=run_ts2)
    initial_h2 = _PLOT_WATER_STATE_HISTORY[plot_id]["2026-06-02"]["step_forcing_hash"]

    # Step 3: Soil parameter correction on June 1 (Ks changed from 25 to 5 cm/day)
    corrected_soil = WaterStateFactory.create_soil_water_state(
        layer_depths_cm=loam.layer_depths_cm,
        theta_profile=loam.theta_profile,
        field_capacity_profile=loam.field_capacity_profile,
        wilting_point_profile=loam.wilting_point_profile,
        saturation_profile=loam.saturation_profile,
        residual_profile=loam.residual_profile,
        hydraulic_conductivity_profile=[5.0] * len(loam.layer_depths_cm),
        van_genuchten_alpha=loam.van_genuchten_alpha,
        van_genuchten_n=loam.van_genuchten_n,
    )
    inputs_corr = DummyInputs(plot_id=plot_id, op_ctx={"weather_daily": weather_dict, "soil_profile_state": corrected_soil})
    w_corr1, _ = _execute_canonical_water_engine(inputs_corr, None, None, run_timestamp=run_ts1)

    new_h1 = _PLOT_WATER_STATE_HISTORY[plot_id]["2026-06-01"]["step_forcing_hash"]
    assert new_h1 != initial_h1

    # Step 4: Advancing June 2 now consumes corrected June 1 predecessor hash
    w_corr2, _ = _execute_canonical_water_engine(inputs_2, None, None, run_timestamp=run_ts2)
    new_h2 = _PLOT_WATER_STATE_HISTORY[plot_id]["2026-06-02"]["step_forcing_hash"]
    assert new_h2 != initial_h2
