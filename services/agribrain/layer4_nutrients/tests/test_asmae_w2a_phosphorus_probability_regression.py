"""W2-A regression: phosphorus inference must produce a probability without ASMAE.

The phosphorus logit-to-probability conversion must survive removal of any
uncalibrated chlorophyll-to-P heuristic. This is a focused code regression,
not a field-calibrated phosphorus diagnostic qualification.
"""
import math

from layer4_nutrients.inference.engine import NutrientInferenceEngine
from layer4_nutrients.schema import Nutrient


def _p(evidence):
    return NutrientInferenceEngine()._infer_phosphorus(evidence, swb=None, l3_decision=None)


def test_phosphorus_inference_produces_finite_probability_after_chlorophyll_removal():
    result = _p({})
    assert result.nutrient == Nutrient.P
    assert math.isfinite(result.probability_deficient)
    assert 0.0 <= result.probability_deficient <= 1.0
    assert result.state_index == -result.probability_deficient


def test_independent_soil_phosphorus_measurements_have_correct_direction():
    baseline = _p({})
    deficient = _p({"soil_p_status": "deficient", "soil_p_ppm": 7.0})
    high = _p({"soil_p_status": "high", "soil_p_ppm": 120.0})
    assert deficient.probability_deficient > baseline.probability_deficient
    assert high.probability_deficient < baseline.probability_deficient


def test_untagged_chlorophyll_cannot_change_phosphorus_inference():
    baseline = _p({"soil_p_status": "adequate", "soil_p_ppm": 27.0})
    injected = _p({
        "soil_p_status": "adequate", "soil_p_ppm": 27.0,
        "asmae_chlorophyll": 0.1,
        "asmae_water_stress": 0.95,
    })
    assert injected.probability_deficient == baseline.probability_deficient
    assert injected.confidence == baseline.confidence
