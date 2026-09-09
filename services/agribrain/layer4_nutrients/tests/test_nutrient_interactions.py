"""Tests for NutrientInteractionEngine in Layer 4 Nutrients."""

from layer4_nutrients.nutrient_interactions.engine import NutrientInteractionEngine
from layer4_nutrients.schema import Nutrient, NutrientState, Severity


def _make_state(nutrient: Nutrient, prob: float, sev: Severity) -> NutrientState:
    return NutrientState(
        nutrient=nutrient,
        state_index=1.0 - prob,
        probability_deficient=prob,
        confidence=0.85,
        severity=sev,
        drivers_used=[],
        evidence_trace=[],
        confounders=[],
    )


def test_liebig_minimum_detection():
    engine = NutrientInteractionEngine()
    states = {
        Nutrient.N: _make_state(Nutrient.N, 0.20, Severity.LOW),
        Nutrient.P: _make_state(Nutrient.P, 0.85, Severity.CRITICAL),
        Nutrient.K: _make_state(Nutrient.K, 0.30, Severity.LOW),
    }
    result = engine.analyze(states)
    assert result.limiting_factor.limiting_nutrient == Nutrient.P


def test_antagonism_effects():
    engine = NutrientInteractionEngine()
    # High P supply with marginal Zn
    states = {
        Nutrient.N: _make_state(Nutrient.N, 0.10, Severity.LOW),
        Nutrient.P: _make_state(Nutrient.P, 0.05, Severity.LOW),
        Nutrient.K: _make_state(Nutrient.K, 0.10, Severity.LOW),
        Nutrient.Zn: _make_state(Nutrient.Zn, 0.40, Severity.MODERATE),
    }
    result = engine.analyze(states)
    assert isinstance(result.interactions, list)
    assert isinstance(result.adjusted_states, dict)
