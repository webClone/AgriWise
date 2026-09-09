from datetime import datetime
from types import SimpleNamespace
import pytest

from layer7_planning.engines.ccl_crop_library import get_crop_profile, CROP_DATABASE, CropProfile
from layer7_planning.engines.pwe_planting_window import compute_planting_window
from layer7_planning.engines.ste_seedbed import compute_soil_workability
from layer7_planning.schema import SuitabilityState, SuitabilityDriver


def test_crop_library_retrieval():
    """Verify crop profile retrieval, case-insensitivity, and fallback."""
    wheat = get_crop_profile("wheat")
    assert wheat is not None
    assert wheat.display_name == "Wheat"
    assert wheat.base_temp_c == 0.0
    assert wheat.frost_sensitivity_c == -8.0
    assert "loam" in [s.lower() for s in wheat.preferred_soil_type]
    assert wheat.default_price_per_ton > 0
    assert wheat.base_production_cost_per_ha > 0

    # Case and whitespace normalization
    assert get_crop_profile("  WhEaT  ") is not None
    assert get_crop_profile("potato") is not None
    assert get_crop_profile("olive") is not None
    assert get_crop_profile("tomato") is not None

    # Unknown crop returns None
    assert get_crop_profile("unsupported_alien_crop_xyz") is None


def test_crop_database_integrity():
    """Ensure all crops in library have valid physical and economic priors."""
    assert len(CROP_DATABASE) >= 40
    for crop_id, prof in CROP_DATABASE.items():
        assert prof.id == crop_id
        assert prof.optimal_temp_min_c <= prof.optimal_temp_max_c
        assert prof.frost_sensitivity_c <= prof.optimal_temp_min_c
        assert prof.target_gdd > 0
        assert len(prof.preferred_soil_type) > 0
        assert prof.default_price_per_ton > 0
        assert prof.base_production_cost_per_ha > 0
        assert len(prof.varieties) > 0


def test_planting_window_in_season_vs_out_of_season():
    """Test planting window engine for in-season vs out-of-season month."""
    wheat = get_crop_profile("wheat")
    assert wheat is not None

    # Wheat with default north_africa window [1..12] is in season
    dt = datetime(2026, 3, 15)
    l1_out = SimpleNamespace(
        plot_timeseries=[{"t_min": 12.0, "rain": 5.0}] * 7,
        forecast_7d=[{"temp_min": 14.0, "rain_prob": 0.1}] * 7,
    )
    state = compute_planting_window(dt, wheat, l1_out, region="north_africa")
    assert isinstance(state, SuitabilityState)
    assert 0.0 <= state.probability_ok <= 1.0
    assert state.probability_ok > 0.5
    assert state.severity == "LOW"

    # Profile with restricted season (e.g. month 10 to 12) tested in March (month 3)
    custom_crop = CropProfile(
        id="winter_special", display_name="Winter Special",
        base_temp_c=0.0, optimal_temp_min_c=10.0, optimal_temp_max_c=20.0,
        frost_sensitivity_c=-5.0, flowering_heat_stress_c=30.0, target_gdd=1200.0,
        preferred_soil_type=["loam"], max_planting_rain_7d_mm=50.0, min_planting_temp_c=5.0,
        planting_windows={"north_africa": [{"start_month": 10, "end_month": 12}]},
        varieties=[], default_price_per_ton=300.0, base_production_cost_per_ha=1000.0,
    )
    state_out = compute_planting_window(datetime(2026, 3, 15), custom_crop, l1_out, region="north_africa")
    # Out of season produces lower probability
    assert state_out.probability_ok < state.probability_ok
    assert any("OUTSIDE" in l.condition for l in state_out.evidence_trace)


def test_planting_window_frost_and_germination_risks():
    """Verify frost warning and cold soil temperature detection."""
    tomato = get_crop_profile("tomato")
    assert tomato is not None  # frost_sensitivity_c = 0.0, min_planting_temp_c = 15.0

    # Cold conditions: min temp near 1.0C (frost risk and below min germination)
    dt = datetime(2026, 4, 1)
    l1_cold = SimpleNamespace(
        plot_timeseries=[{"t_min": 1.0, "rain": 0.0}] * 7,
        forecast_7d=[{"temp_min": 1.0, "rain_prob": 0.0}] * 7,
    )
    cold_state = compute_planting_window(dt, tomato, l1_cold)
    assert cold_state.probability_ok < 0.3
    assert cold_state.severity == "CRITICAL"
    drivers = [l.driver for l in cold_state.evidence_trace]
    assert SuitabilityDriver.FROST_RISK in drivers
    assert SuitabilityDriver.TEMP in drivers


def test_planting_window_missing_weather_penalty():
    """Missing L1 weather telemetry drops confidence and defaults to calendar normals."""
    potato = get_crop_profile("potato")
    dt = datetime(2026, 3, 1)
    state_missing = compute_planting_window(dt, potato, None)
    assert state_missing.confidence <= 0.6
    assert any("Missing weather telemetry" in l.condition for l in state_missing.evidence_trace)


def test_soil_workability_texture_and_wetness():
    """Verify trafficability on wet clay vs well-drained loam."""
    potato = get_crop_profile("potato")  # preferred: loam, sandy loam; max_rain_7d = 40mm
    dt = datetime(2026, 3, 1)

    # 1. Optimal conditions on loam
    l1_optimal = SimpleNamespace(
        plot_timeseries=[{"rain": 1.0}] * 7,
        forecast_7d=[{"rain_prob": 0.1}] * 7,
    )
    state_opt = compute_soil_workability(potato, l1_optimal, soil_texture="loam", soil_moisture="OPTIMAL")
    assert state_opt.probability_ok > 0.6
    assert state_opt.severity == "LOW"

    # 2. Wet clay soil: high compaction risk
    l1_rainy = SimpleNamespace(
        plot_timeseries=[{"rain": 15.0}] * 7,
        forecast_7d=[{"rain_prob": 0.8}] * 7,
    )
    state_clay = compute_soil_workability(potato, l1_rainy, soil_texture="clay", soil_moisture="HIGH")
    assert state_clay.probability_ok < 0.2
    assert state_clay.severity == "CRITICAL"
    assert any("compaction machinery on wet clay" in l.condition for l in state_clay.evidence_trace)


def test_soil_workability_drought_and_missing_l1():
    """Verify dry soil penalty and complete lack of environmental data."""
    wheat = get_crop_profile("wheat")

    # Missing L1
    state_none = compute_soil_workability(wheat, None)
    assert state_none.probability_ok == 0.5
    assert state_none.confidence == 0.1

    # Extremely dry with unknown moisture
    l1_bone_dry = SimpleNamespace(
        plot_timeseries=[{"rain": 0.0}] * 7,
        forecast_7d=[{"rain_prob": 0.0}] * 7,
    )
    state_dry = compute_soil_workability(wheat, l1_bone_dry, soil_texture="loam", soil_moisture="unknown")
    assert any("powdery/dry" in l.condition for l in state_dry.evidence_trace)
