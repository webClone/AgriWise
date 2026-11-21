"""W2-B RED tests: ASMAE values do not modify yield without scientific authority.

These are specification tests, not previously executed verification.
Run on the descendant of W2-A, after W2-A is separately qualified.
"""
from types import SimpleNamespace
import pytest

from layer6_yield.yield_forecast import YieldForecastEngine


def _forecast(asmae_features=None):
    return YieldForecastEngine().predict_yield(
        crop_type="wheat",
        final_biomass_kg_ha=6500,
        cumulative_stress={
            "water_loss_factor": 0.10,
            "nutrient_loss_factor": 0.02,
            "disease_loss_factor": 0.01,
        },
        confidence_scores={"biomass": 0.90, "stress": 0.85},
        input_hash="independent-baseline-hash",
        asmae_features=asmae_features,
    )


def _assert_no_unqualified_yield_change(features):
    base = _forecast()
    candidate = _forecast(features)
    for field in ("yield_mean_t_ha", "yield_p10", "yield_p90"):
        assert candidate[field] == pytest.approx(base[field]), (
            f"Unsupported ASMAE evidence changed {field}"
        )


@pytest.mark.parametrize("feature", [
    {"value": 0.98, "confidence": 0.99, "uncertainty": 0.01,
     "state_update_allowed": False, "diagnostic_only": True},
    {"value": 0.98, "confidence": 0.99, "uncertainty": 0.01,
     "state_update_allowed": False, "diagnostic_only": False},
    {"value": 0.98, "confidence": 0.99, "uncertainty": 0.01,
     "state_update_allowed": True, "diagnostic_only": True},
    {"value": 0.98, "confidence": 0.99,  # NEVER invent 0.1 sigma
     "state_update_allowed": False, "diagnostic_only": True},
])
def test_w2b_unqualified_vigor_cannot_modify_yield(feature):
    _assert_no_unqualified_yield_change({"ASMAE_VIGOR": feature})


@pytest.mark.parametrize("feature", [
    {"value": 6.4, "confidence": 0.99, "uncertainty": 0.01,
     "state_update_allowed": False, "diagnostic_only": True},
    {"value": 6.4, "confidence": 0.99,
     "state_update_allowed": False, "diagnostic_only": True},
    {"value": 6.4, "confidence": 0.99, "uncertainty": None,
     "state_update_allowed": False, "diagnostic_only": True},
])
def test_w2b_unqualified_lai_cannot_modify_yield(feature):
    _assert_no_unqualified_yield_change({"ASMAE_LAI": feature})


def test_w2b_missing_object_sigma_neither_crashes_nor_modifies_yield():
    feat = SimpleNamespace(
        value=0.98, confidence=0.99, uncertainty=None,
        state_update_allowed=False, diagnostic_only=True,
        asmae_channel="diagnostic", resolution_m=20.0,
    )
    _assert_no_unqualified_yield_change({"ASMAE_VIGOR": feat})


def test_w2b_fine_resolution_without_certification_cannot_modify_yield():
    feat = {
        "value": 0.98, "confidence": 0.99, "uncertainty": 0.01,
        "resolution_m": 1.0, "asmae_channel": "diagnostic",
        "state_update_allowed": False, "diagnostic_only": True,
    }
    _assert_no_unqualified_yield_change({"ASMAE_VIGOR": feat})
