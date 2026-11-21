"""W2-A: preserve physical units and deny uncalibrated cross-layer stress inference."""
from types import SimpleNamespace
import math

import pytest

from services.agribrain.scientific_contracts.asmae_physical_semantics import (
    calibrated_chlorophyll_deficit,
    authorized_chlorophyll_deficit,
    require_tagged_state_quantity,
    validate_canopy_water_content,
)
from services.agribrain.layer7_risk.trust_monitor import TrustMonitor


def _chlorophyll(value=35.0, **updates):
    result = {
        "value": value, "unit": "ug/cm2",
        "state_update_allowed": True, "diagnostic_only": False,
    }
    result.update(updates)
    return result


def _calibration(**updates):
    result = {
        "status": "qualified", "unit": "ug/cm2", "crop_type": "wheat",
        "calibration_ref": "independent-research-calibration-001",
        "low_chlorophyll": 20.0, "adequate_chlorophyll": 60.0,
    }
    result.update(updates)
    return result


@pytest.mark.parametrize("raw", [0.4, 40, {"value": 40.0},
                                  {"value": 40.0, "unit": "fraction"},
                                  {"value": 40.0, "unit": "fraction_content"}])
def test_w2a_untagged_or_wrong_chlorophyll_unit_rejected(raw):
    with pytest.raises(ValueError, match="asmae_chlorophyll_unit_missing_or_mismatched"):
        require_tagged_state_quantity(raw, "chlorophyll")


@pytest.mark.parametrize("raw", [
    0.7, {"value": 0.7}, {"value": 0.7, "unit": "ug/cm2"},
])
def test_w2a_untagged_or_wrong_canopy_content_unit_rejected(raw):
    with pytest.raises(ValueError, match="asmae_canopy_water_unit_missing_or_mismatched"):
        validate_canopy_water_content(raw)


@pytest.mark.parametrize("value", [-1, 81, float("nan"), float("inf"), True])
def test_w2a_chlorophyll_nonphysical_values_rejected(value):
    with pytest.raises(ValueError):
        require_tagged_state_quantity({"value": value, "unit": "ug/cm2"}, "chlorophyll")


def test_w2a_authentic_units_are_not_misread_as_fractions():
    assert require_tagged_state_quantity(_chlorophyll(45), "chlorophyll").value == 45
    assert validate_canopy_water_content(
        {"value": 0.75, "unit": "fraction_content"}
    ).value == 0.75
    with pytest.raises(ValueError):
        validate_canopy_water_content(_chlorophyll(45))


def test_w2a_no_crop_calibration_no_nitrogen_adjustment():
    assert calibrated_chlorophyll_deficit(
        _chlorophyll(), crop_type="wheat", calibration=None
    ) is None
    assert calibrated_chlorophyll_deficit(
        _chlorophyll(), crop_type="barley", calibration=_calibration()
    ) is None
    assert calibrated_chlorophyll_deficit(
        _chlorophyll(), crop_type="wheat", calibration=_calibration(status="unverified")
    ) is None


def test_w2a_calibrated_chlorophyll_maps_in_correct_physical_direction():
    low = calibrated_chlorophyll_deficit(
        _chlorophyll(18.0), crop_type="wheat", calibration=_calibration())
    middle = calibrated_chlorophyll_deficit(
        _chlorophyll(40.0), crop_type="wheat", calibration=_calibration())
    adequate = calibrated_chlorophyll_deficit(
        _chlorophyll(70.0), crop_type="wheat", calibration=_calibration())
    assert low == pytest.approx(1.0)
    assert middle == pytest.approx(0.5)
    assert adequate == pytest.approx(0.0)


def test_w2a_diagnostic_chlorophyll_never_changes_nutrient_index():
    assert calibrated_chlorophyll_deficit(
        _chlorophyll(18.0, state_update_allowed=False),
        crop_type="wheat", calibration=_calibration()
    ) is None
    assert calibrated_chlorophyll_deficit(
        _chlorophyll(18.0, diagnostic_only=True),
        crop_type="wheat", calibration=_calibration()
    ) is None


def test_w2a_healthy_wet_canopy_and_wet_soil_are_not_a_contradiction():
    result = TrustMonitor().evaluate_cross_layer_conflict(
        {"ASMAE_CANOPY_WATER": SimpleNamespace(
            value=0.8, unit="fraction_content", bma_disagreement=0.0
        )},
        {"soil_moisture_vwc": 0.37},
    )
    assert result["conflict_score"] == 0.0
    assert result["agreement"] is True


def test_w2a_legacy_untagged_canopy_is_blocked_without_false_stress():
    result = TrustMonitor().evaluate_cross_layer_conflict(
        {"ASMAE_CANOPY_WATER": SimpleNamespace(
            value=0.8, bma_disagreement=0.0
        )},
        {"soil_moisture_vwc": 0.37},
    )
    assert "canopy_water_semantic_unit_unqualified" in result["reasons"]
    assert result["conflict_score"] == 0.0


def test_w2a_downstream_nutrient_adapter_refuses_bare_evidence():
    from services.agribrain.layer4_nutrients.inference.engine import (
        _qualified_chlorophyll_deficit,
    )
    data = {
        "asmae_crop_type": "wheat",
        "asmae_chlorophyll_calibration": _calibration(),
        "asmae_chlorophyll": 0.4,
    }
    assert _qualified_chlorophyll_deficit(data) is None
    data["asmae_chlorophyll"] = _chlorophyll(value=30.0)
    # An untrusted JSON calibration cannot move Layer 4 science.
    assert _qualified_chlorophyll_deficit(data) is None
    data["_trusted_crop_calibration_verifier"] = lambda **kwargs: True
    assert _qualified_chlorophyll_deficit(data) == pytest.approx(0.75)



def test_w2a_untrusted_calibration_status_cannot_grant_scientific_influence():
    feature = _chlorophyll(18.0)
    calibration = _calibration()
    assert authorized_chlorophyll_deficit(
        feature, crop_type="wheat", calibration=calibration,
    ) is None
    assert authorized_chlorophyll_deficit(
        feature, crop_type="wheat", calibration=calibration,
        trusted_calibration_verifier=lambda **kwargs: False,
    ) is None


def test_w2a_calibration_verifier_exception_fails_closed():
    def unavailable_registry(**kwargs):
        raise RuntimeError("calibration_registry_offline")
    assert authorized_chlorophyll_deficit(
        _chlorophyll(18.0), crop_type="wheat",
        calibration=_calibration(),
        trusted_calibration_verifier=unavailable_registry,
    ) is None
