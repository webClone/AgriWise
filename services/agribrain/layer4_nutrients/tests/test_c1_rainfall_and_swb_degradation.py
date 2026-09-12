"""Tests for C^1 continuous rainfall effective precipitation spline and SWB degradation."""

import pytest
from services.agribrain.layer4_nutrients.soil_water_balance.engine import (
    calculate_effective_precipitation,
    SoilWaterBalanceEngine,
)


def test_effective_precipitation_boundaries_and_continuity():
    """Verify C^1 value continuity at P=200 and P=300 mm."""
    eps = 1e-6

    # 1. Zero and negative rain
    assert calculate_effective_precipitation(0.0) == 0.0
    assert calculate_effective_precipitation(-5.0) == 0.0

    # 2. Boundary at P = 200 mm
    p_left_200 = 200.0 * (125.0 - 0.2 * 200.0) / 125.0  # 136.0
    p_spline_200 = calculate_effective_precipitation(200.0)
    p_right_200 = calculate_effective_precipitation(200.0 + eps)

    assert p_spline_200 == pytest.approx(136.0, abs=1e-5)
    assert p_left_200 == pytest.approx(p_spline_200, abs=1e-5)
    assert p_right_200 == pytest.approx(p_spline_200, abs=1e-4)

    # 3. Boundary at P = 300 mm
    p_linear_300 = 135.0 + 0.1 * 300.0  # 165.0
    p_spline_300 = calculate_effective_precipitation(300.0)
    p_left_300 = calculate_effective_precipitation(300.0 - eps)

    assert p_spline_300 == pytest.approx(165.0, abs=1e-5)
    assert p_linear_300 == pytest.approx(p_spline_300, abs=1e-5)
    assert p_left_300 == pytest.approx(p_spline_300, abs=1e-4)


def test_effective_precipitation_c1_slope_continuity():
    """Verify C^1 slope continuity matching at P=200 and P=300."""
    h = 1e-4

    # Slope at P = 200: d/dP (P - 0.0016 P^2) = 1 - 0.0032(200) = 0.36
    slope_left_200 = (calculate_effective_precipitation(200.0) - calculate_effective_precipitation(200.0 - h)) / h
    slope_right_200 = (calculate_effective_precipitation(200.0 + h) - calculate_effective_precipitation(200.0)) / h
    assert slope_left_200 == pytest.approx(0.36, abs=1e-2)
    assert slope_right_200 == pytest.approx(0.36, abs=1e-2)

    # Slope at P = 300: d/dP (135 + 0.1P) = 0.10
    slope_left_300 = (calculate_effective_precipitation(300.0) - calculate_effective_precipitation(300.0 - h)) / h
    slope_right_300 = (calculate_effective_precipitation(300.0 + h) - calculate_effective_precipitation(300.0)) / h
    assert slope_left_300 == pytest.approx(0.10, abs=1e-2)
    assert slope_right_300 == pytest.approx(0.10, abs=1e-2)


def test_effective_precipitation_strict_monotonicity():
    """Ensure dP_eff/dP > 0 across the entire range [0, 500] mm."""
    prev_val = 0.0
    for p_int in range(1, 500):
        val = calculate_effective_precipitation(float(p_int))
        assert val > prev_val, f"Monotonicity violated at P={p_int}: {val} <= {prev_val}"
        prev_val = val


def test_swb_missing_weather_degradation_propagation():
    """Missing or partial weather data propagates degraded status and uncertainty."""
    engine = SoilWaterBalanceEngine()

    # Complete 5-day weather
    complete_weather = [
        {"et0": 4.5, "rain_mm": 10.0, "t_max": 25.0} for _ in range(5)
    ]
    out_complete = engine.run(complete_weather)
    assert out_complete.status == "OK"
    assert out_complete.is_degraded is False
    assert out_complete.missing_weather_days == 0
    assert out_complete.uncertainty_multiplier == 1.0

    # Incomplete weather with missing days
    incomplete_weather = [
        {"et0": 4.5, "rain_mm": 10.0, "t_max": 25.0},
        {"et0": None, "rain_mm": None, "t_max": 25.0},
        {"et0": 3.8, "rain_mm": 0.0, "t_max": 22.0},
        {"et0": None, "rain_mm": 5.0, "t_max": 24.0},
        {"et0": 4.0, "rain_mm": 2.0, "t_max": 26.0},
    ]
    out_incomplete = engine.run(incomplete_weather)
    assert out_incomplete.status == "DEGRADED"
    assert out_incomplete.is_degraded is True
    assert out_incomplete.missing_weather_days == 2
    assert out_incomplete.uncertainty_multiplier > 1.0
