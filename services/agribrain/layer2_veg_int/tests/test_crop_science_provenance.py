from __future__ import annotations

from crop_database import CROP_REGISTRY
from layer2_veg_int.crop_science_data import (
    CROP_DATA_QUALITY,
    CROP_NDVI_SIGNATURES,
    SPECTRAL_SIGNATURES,
    _CURATED_NDVI_CODES,
    get_crop_science_provenance,
)


def test_architecture_defaults_do_not_manufacture_crop_code_separation() -> None:
    # These crops have the same architecture, duration, water need, and
    # temperature bounds. Missing measured data must therefore produce the
    # same default instead of a crop-code-derived numerical fingerprint.
    left = CROP_REGISTRY["teff"]
    right = CROP_REGISTRY["oat_forage"]
    assert left.architecture == right.architecture
    assert left.growing_days == right.growing_days
    assert left.water_needs == right.water_needs
    assert left.optimal_temp_min == right.optimal_temp_min
    assert left.optimal_temp_max == right.optimal_temp_max
    assert "teff" not in _CURATED_NDVI_CODES
    assert "oat_forage" not in _CURATED_NDVI_CODES
    assert CROP_NDVI_SIGNATURES["teff"] == CROP_NDVI_SIGNATURES["oat_forage"]


def test_expanded_signatures_are_explicitly_non_discriminative() -> None:
    for code in ("teff", "oat_forage"):
        ndvi = CROP_NDVI_SIGNATURES[code]
        spectral = SPECTRAL_SIGNATURES[code]
        assert ndvi["_provenance"] == "architecture_default"
        assert ndvi["_species_discriminative"] is False
        assert spectral["_provenance"] == "architecture_default"
        assert spectral["_species_discriminative"] is False
        assert CROP_DATA_QUALITY[code]["ndvi_signature"] == "heuristic"


def test_provenance_summary_is_complete_and_never_claims_calibration() -> None:
    summary = get_crop_science_provenance()
    assert summary["registry_crop_count"] == len(CROP_REGISTRY)
    assert summary["calibrated_species_evidence"] is False
    assert summary["expanded_defaults_species_discriminative"] is False
    for tiers in summary["feature_coverage_by_provenance"].values():
        assert sum(tiers.values()) == len(CROP_REGISTRY)
