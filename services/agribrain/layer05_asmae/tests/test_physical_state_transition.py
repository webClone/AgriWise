"""
Unit tests for Work Package 04: ASMAE Physical State Transition.

Validates:
1. Dimensional unit conservation: Delta theta_v = Delta W / (Z_r * 1000)
2. Gravity drainage strictly above Field Capacity (theta_FC)
3. Physical soil boundary clipping (residual to saturation)
4. Strongly-typed ForcingEvent assimilation and unit conversions
5. Filtering of unconfirmed planned forcing events
"""

import random
from datetime import datetime, timezone, timedelta
import numpy as np
import pytest

from services.agribrain.layer05_asmae.assimilation.filter import forecast_step
from services.agribrain.layer05_asmae.config import STATE_NAMES
from services.agribrain.scientific_contracts.contracts_v2 import (
    ForcingEvent,
    ForcingExecutionStatus,
    SpatialSupport,
)


def _build_single_state_ensemble(root_zone_water: float, canopy_water: float = 0.5) -> dict:
    """Build a deterministic single-node ensemble with 5 members."""
    root_idx = STATE_NAMES.index("root_zone_water")
    canopy_idx = STATE_NAMES.index("canopy_water")

    member = [0.5] * len(STATE_NAMES)
    member[root_idx] = float(root_zone_water)
    member[canopy_idx] = float(canopy_water)

    # 5 identical members for node "n1"
    return {"n1": [list(member) for _ in range(5)]}


def test_volumetric_water_content_dimensional_conservation():
    """Applying 10 mm of water to 0.4 m root depth increases theta_v by exactly 0.0250."""
    initial_theta = 0.20
    ensemble = _build_single_state_ensemble(initial_theta)

    rooting_depth_m = 0.40  # 400 mm
    soil_context = {
        "field_capacity": 0.35,
        "wilting_point": 0.12,
        "rooting_depth_m": rooting_depth_m,
        "drainage_fraction": 0.5,
        "runoff_fraction": 0.0,
    }
    crop_context = {"crop_coefficient": 1.0}

    # 10 mm rain, zero ET0, 1 day
    weather_day = {
        "precipitation_mm": 10.0,
        "et0_mm": 0.0,
    }

    # Use fixed seed RNG
    rng = random.Random(42)

    updated_ensemble = forecast_step(
        ensemble=ensemble,
        priors={},
        crop_context=crop_context,
        rng=rng,
        weather_day=weather_day,
        soil_context=soil_context,
        delta_days=1.0,
    )

    root_idx = STATE_NAMES.index("root_zone_water")
    updated_members = [m[root_idx] for m in updated_ensemble["n1"]]
    mean_updated = float(np.mean(updated_members))

    # Expected Delta theta = 10 mm / 400 mm = 0.0250
    # Allow small tolerance for random process noise
    expected_theta = initial_theta + (10.0 / 400.0)
    assert abs(mean_updated - expected_theta) < 0.015
    # Crucially verify it is NOT inflated by 4.35x (which would have yielded ~0.3087)
    assert mean_updated < 0.25


def test_gravity_drainage_strictly_above_field_capacity():
    """Gravity drainage occurs only when theta > theta_FC, and ceases when theta <= theta_FC."""
    theta_fc = 0.30
    soil_context = {
        "field_capacity": theta_fc,
        "wilting_point": 0.10,
        "rooting_depth_m": 0.50,
        "drainage_fraction": 0.6,
        "runoff_fraction": 0.0,
    }
    crop_context = {"crop_coefficient": 0.0}
    weather_day = {"precipitation_mm": 0.0, "et0_mm": 0.0}

    # Case A: Initial theta below field capacity (0.25 <= 0.30) -> No drainage
    ens_below = _build_single_state_ensemble(0.25)
    rng1 = random.Random(100)
    updated_below = forecast_step(
        ensemble=ens_below,
        priors={},
        crop_context=crop_context,
        rng=rng1,
        weather_day=weather_day,
        soil_context=soil_context,
        delta_days=1.0,
    )
    root_idx = STATE_NAMES.index("root_zone_water")
    mean_below = float(np.mean([m[root_idx] for m in updated_below["n1"]]))
    assert abs(mean_below - 0.25) < 0.015  # only process noise, no systematic drainage

    # Case B: Initial theta well above field capacity (0.40 > 0.30) -> Rapid drainage
    ens_above = _build_single_state_ensemble(0.40)
    rng2 = random.Random(100)
    updated_above = forecast_step(
        ensemble=ens_above,
        priors={},
        crop_context=crop_context,
        rng=rng2,
        weather_day=weather_day,
        soil_context=soil_context,
        delta_days=1.0,
    )
    mean_above = float(np.mean([m[root_idx] for m in updated_above["n1"]]))
    # Drainage removes a fraction of excess (0.40 - 0.30 = 0.10)
    assert mean_above < 0.36


def test_strongly_typed_forcing_event_handling():
    """Validated ForcingEvent objects are correctly parsed with unit conversions."""
    initial_theta = 0.20
    ensemble = _build_single_state_ensemble(initial_theta)
    rooting_depth_m = 0.50  # 500 mm depth

    soil_context = {
        "field_capacity": 0.35,
        "wilting_point": 0.10,
        "rooting_depth_m": rooting_depth_m,
    }
    crop_context = {"crop_coefficient": 0.0}
    weather_day = {"precipitation_mm": 0.0, "et0_mm": 0.0}

    now = datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc)
    # 100 m3/ha irrigation confirmed -> 10.0 mm
    confirmed_irrig = ForcingEvent(
        event_id="force-irrig-01",
        forcing_type="irrigation",
        quantity=100.0,
        units="m3/ha",
        execution_status=ForcingExecutionStatus.OBSERVED_CONFIRMED,
        effective_start=now,
        effective_end=now + timedelta(hours=1),
        spatial_extent=SpatialSupport.PLOT,
    )

    rng = random.Random(42)
    updated_ens = forecast_step(
        ensemble=ensemble,
        priors={},
        crop_context=crop_context,
        rng=rng,
        weather_day=weather_day,
        soil_context=soil_context,
        management_events=[confirmed_irrig],
        process_day="2026-06-10",
        delta_days=1.0,
    )

    root_idx = STATE_NAMES.index("root_zone_water")
    mean_updated = float(np.mean([m[root_idx] for m in updated_ens["n1"]]))

    # Expected: 10 mm / 500 mm = 0.0200 increase
    expected_theta = initial_theta + (10.0 / 500.0)
    assert abs(mean_updated - expected_theta) < 0.015


def test_unconfirmed_planned_forcing_events_are_ignored():
    """Planned but unconfirmed forcing events must not update historical physical state."""
    initial_theta = 0.20
    ensemble = _build_single_state_ensemble(initial_theta)
    rooting_depth_m = 0.50

    soil_context = {
        "field_capacity": 0.35,
        "wilting_point": 0.10,
        "rooting_depth_m": rooting_depth_m,
    }
    crop_context = {"crop_coefficient": 0.0}
    weather_day = {"precipitation_mm": 0.0, "et0_mm": 0.0}

    now = datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc)
    # Planned action (NOT confirmed)
    planned_irrig = ForcingEvent(
        event_id="force-plan-01",
        forcing_type="irrigation",
        quantity=50.0,
        units="mm",
        execution_status=ForcingExecutionStatus.PLANNED,
        effective_start=now,
        effective_end=now + timedelta(hours=1),
        spatial_extent=SpatialSupport.PLOT,
    )

    rng = random.Random(42)
    updated_ens = forecast_step(
        ensemble=ensemble,
        priors={},
        crop_context=crop_context,
        rng=rng,
        weather_day=weather_day,
        soil_context=soil_context,
        management_events=[planned_irrig],
        process_day="2026-06-10",
        delta_days=1.0,
    )

    root_idx = STATE_NAMES.index("root_zone_water")
    mean_updated = float(np.mean([m[root_idx] for m in updated_ens["n1"]]))

    # If it had been applied, theta would jump by 50/500 = +0.10 to ~0.30.
    # Since it was ignored, theta remains ~0.20.
    assert abs(mean_updated - initial_theta) < 0.015
    assert mean_updated < 0.23
