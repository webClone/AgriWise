"""
Test Suite for Layer 2 Phase 3: Phenological Forcing & GDD Separation
"""

import pytest
from layer2_veg_int.phenology_engine import (
    PhenologyEngine,
    DevelopmentIncrement,
    compute_development_rate,
    compute_effective_gdd,
)
from layer2_veg_int.schema import PhenologyStage


def test_development_rate_decomposition():
    """Development increment must cleanly expose raw GDD, photoperiod factor, and heat penalty."""
    inc = compute_development_rate(
        t_mean=25.0,
        t_max=38.0,  # Heat stress > 35
        t_base=10.0,
        t_opt_max=35.0,
        day_length=15.0,
        is_short_day=True,  # Long days inhibit short-day crops
        p_critical=13.0,
    )
    assert isinstance(inc, DevelopmentIncrement)
    assert inc.raw_gdd == 15.0
    assert inc.heat_penalty == 0.7  # 1.0 - (38-35)/10 = 0.7
    assert inc.photo_factor < 0.15   # Sigmoid drop at 15h > 13h
    assert inc.delta_development == round(15.0 * inc.photo_factor * 0.7, 2)


def test_semi_markov_duration_penalties():
    """Viterbi HMM must penalize states exceeding reasonable physical durations."""
    engine = PhenologyEngine()
    # 120 days of flat NDVI=0.25 (emergence-like)
    n = 120
    ndvi = [0.25] * n
    vel = [0.0] * n
    dates = [f"2026-04-{i%28+1:02d}" for i in range(n)]
    gdd = [float(i * 15) for i in range(n)]

    stages, confs = engine.infer_daily_stages(
        modeled_ndvi=ndvi,
        velocity=vel,
        dates=dates,
        cumulative_gdd=gdd,
    )
    assert len(stages) == n
    # The engine should not stay in EMERGENCE forever (expected duration ~14 days)
    assert stages[-1] != PhenologyStage.EMERGENCE
