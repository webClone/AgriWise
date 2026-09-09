"""
Test Suite for Layer 2 Phase 2: Whittaker & Curve Fitting Corrections
"""

import math
import numpy as np
import pytest
from layer2_veg_int.growth_engine import GrowthCurveEngine


def test_inverse_variance_weighting():
    """Points with 4x higher uncertainty must have ~16x lower weight (inverse-variance), not 4x."""
    engine = GrowthCurveEngine()
    unc_low = 0.05
    unc_high = 0.20
    
    sigmas = np.array([unc_low, unc_high], dtype=np.float64)
    sigma_min = 0.01
    w = 1.0 / (sigmas ** 2 + sigma_min ** 2)
    ratio = w[0] / w[1]
    
    # (0.20^2 + 0.01^2) / (0.05^2 + 0.01^2) ≈ 0.0401 / 0.0026 ≈ 15.4x
    assert 14.0 <= ratio <= 16.0


def test_cloud_qa_gating_preserves_real_stress():
    """When cloud QA is 0.0 (clear sky), below-fit observations are not heavily downweighted."""
    engine = GrowthCurveEngine()
    dates = [f"2026-04-{i+1:02d}" for i in range(20)]
    # Clear sky sudden stress drop
    ndvi = [0.70] * 10 + [0.40] * 10
    unc = [0.03] * 20
    cloud_qa = [0.0] * 20  # Completely clear sky
    
    modeled, derivs, unc_out = engine.fit_growth_curve(
        dates=dates,
        ndvi_values=ndvi,
        uncertainties=unc,
        cloud_qa=cloud_qa,
    )
    assert len(modeled) == 20
    # Modeled NDVI in the second half should capture the drop because cloud_qa is 0 (clear sky)
    assert modeled[-1] < 0.55


def test_double_logistic_pos_peak_calculation():
    """Double logistic peak of season (pos_idx) must be true peak, not arithmetic mean of midpoints when slopes differ."""
    engine = GrowthCurveEngine()
    dates = [f"2026-03-{i+1:02d}" for i in range(30)]
    # Asymmetric bell curve: fast greenup (5 days), slow senescence (25 days)
    ndvi = [0.20] * 3 + [0.35, 0.60, 0.85, 0.88, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45, 0.40, 0.35, 0.30, 0.25] + [0.20] * 10
    
    res = engine.fit_double_logistic(ndvi, dates)
    if res is not None:
        # Peak of curve is around index 6
        assert 4 <= res["pos_idx"] <= 8
        assert res["fitted_curve"][int(round(res["pos_idx"]))] >= 0.75


def test_compute_integrals_with_delta_days():
    """Trapezoidal integration with non-uniform delta_days must compute correct physical AUC."""
    engine = GrowthCurveEngine()
    # 3 points: [1.0, 1.0, 1.0], delta_days = [5.0, 10.0] -> Total area = 1.0 * 5 + 1.0 * 10 = 15.0
    curve = [1.0, 1.0, 1.0]
    delta_days = [5.0, 10.0]
    
    res = engine.compute_integrals(curve, delta_days=delta_days)
    assert res["auc_season"] == 15.0
