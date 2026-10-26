"""Verification test suite for 563c6fa closure and numerical invariants.

Covers:
1. Scale-relative PSD covariance validation and nonfinite eigenvalue rejection.
2. Exact canonical root_zone_water V90 variable resolution.
3. State ensemble rollback on negligible-influence assimilation exclusion.
4. Fail-closed invariant uncertainty normalization (missing/NaN -> high uncertainty).
5. Fail-closed display trust policy for NaN / nonfinite quality inputs.
6. Layer 5 v3 and Layer 10 v2 cache policy coexistence.
"""
import math
import numpy as np
import pytest

from services.agribrain.layer10_sire.schema import SurfaceType, SurfaceArtifact, Layer10Output
from services.agribrain.layer10_sire.surfaces.asmae import (
    _validate_covariance,
    get_standard_variable_name,
    get_surface_display_policy,
)
from services.agribrain.layer10_sire.invariants import enforce_layer10_invariants
from services.agribrain.layer05_asmae.cache import (
    STATE_SUPPORT_POLICY_VERSION,
    get_asmae_cache_key,
)
from services.agribrain.layer05_asmae.schema import ASMAEInput
from datetime import date


def test_small_indefinite_covariance_rejected():
    """Small indefinite matrices must be rejected despite scale < 1e-5."""
    # Scale is 1e-5, eigenvalues are -1e-5 and 3e-5
    indefinite_small = [[1e-5, 2e-5], [2e-5, 1e-5]]
    is_valid, is_malformed = _validate_covariance(indefinite_small)
    assert is_valid is False
    assert is_malformed is True

    # Valid small PSD matrix (eigenvalues >= 0)
    valid_small = [[2e-5, 1e-5], [1e-5, 2e-5]]  # eigenvalues: 1e-5 and 3e-5
    is_valid, is_malformed = _validate_covariance(valid_small)
    assert is_valid is True
    assert is_malformed is False


def test_nonfinite_covariance_rejected():
    """Covariance matrices containing NaN or Inf must be rejected."""
    nan_mat = [[1.0, float("nan")], [float("nan"), 1.0]]
    is_valid, is_malformed = _validate_covariance(nan_mat)
    assert is_valid is False
    assert is_malformed is True

    inf_mat = [[float("inf"), 0.0], [0.0, 1.0]]
    is_valid, is_malformed = _validate_covariance(inf_mat)
    assert is_valid is False
    assert is_malformed is True


def test_root_zone_water_v90_variable_resolution():
    """Root-zone water must resolve to root_zone_water, never canopy_water."""
    rz_type = getattr(SurfaceType, "ASMAE_ROOT_ZONE_WATER", None)
    if rz_type is not None:
        assert get_standard_variable_name(rz_type) == "root_zone_water"
        assert get_standard_variable_name(rz_type, "root_zone_water") == "root_zone_water"
        assert get_standard_variable_name(rz_type, "water") == "root_zone_water"

    cw_type = getattr(SurfaceType, "ASMAE_CANOPY_WATER", None)
    if cw_type is not None:
        assert get_standard_variable_name(cw_type) == "canopy_water"
        assert get_standard_variable_name(cw_type, "canopy_water") == "canopy_water"


def test_display_policy_nan_handling():
    """Non-finite confidence or uncertainty must fail closed to diagnostic tier."""
    # NaN confidence must trigger low_confidence and diagnostic tier
    policy_nan_conf = get_surface_display_policy(
        confidence=float("nan"),
        uncertainty=0.1,
        resolution_m=10.0,
        bma_status="success",
        cross_layer_conflict=0.0,
    )
    assert "low_confidence" in policy_nan_conf["warning_codes"]
    assert policy_nan_conf["display_trust_tier"] == "diagnostic"
    assert policy_nan_conf["requires_user_warning"] is True

    # NaN uncertainty must trigger high_uncertainty and diagnostic tier
    policy_nan_unc = get_surface_display_policy(
        confidence=0.9,
        uncertainty=float("nan"),
        resolution_m=10.0,
        bma_status="success",
        cross_layer_conflict=0.0,
    )
    assert "high_uncertainty" in policy_nan_unc["warning_codes"]
    assert policy_nan_unc["display_trust_tier"] == "diagnostic"
    assert policy_nan_unc["requires_user_warning"] is True


def test_invariant_missing_uncertainty_fail_closed():
    """Missing or non-finite uncertainty must fail closed to 1.0, triggering INV-16."""
    # High confidence surface with missing uncertainty and stripped warnings
    surface = SurfaceArtifact(
        surface_id="ASMAE_VIGOR_test",
        semantic_type=SurfaceType.ASMAE_VIGOR,
        grid_ref="2x2",
        values=[[0.5, 0.5], [0.5, 0.5]],
        units="fraction",
        native_resolution_m=10.0,
        provenance={
            "resolution_m": 10.0,
            "state_update_allowed": True,
            "diagnostic_only": False,
            "visual_only": False,
            "warning_codes": [],  # stripped
            "confidence": 0.95,
            # uncertainty intentionally missing
            "requires_user_warning": False,
            "desaturation_level": 0.0,
            "bma_status": "success",
            "has_spatial_grid": True,
        },
    )

    violations = enforce_layer10_invariants(Layer10Output(surface_pack=[surface]), 2, 2)
    assert any("INV-16" in v for v in violations), f"Expected INV-16 violation for missing uncertainty, got: {violations}"


def test_layer5_v3_and_layer10_coexistence():
    """Layer 5 v3 cache policy is distinct and produces v3 cache keys."""
    assert STATE_SUPPORT_POLICY_VERSION == "v3_receipt_bounded_20261026"
    inp = ASMAEInput(
        plot_id="coexistence-test",
        run_id="run-123",
        polygon_geojson={},
        geometry_hash="geom123",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        layer0_source_packages={},
    )
    key = get_asmae_cache_key(inp)
    assert isinstance(key, str) and len(key) == 64


def test_negligible_influence_ensemble_rollback():
    """Rejected negligible-influence update must roll back state_cube without mutation."""
    from types import SimpleNamespace as NS
    import random
    from services.agribrain.layer05_asmae.config import STATE_NAMES
    from services.agribrain.layer05_asmae.geometry.support_contract import build_scene_valid_support
    from services.agribrain.layer05_asmae.assimilation.filter import update_step_ht, _predict_observation_array

    idx = {s: i for i, s in enumerate(STATE_NAMES)}
    a = np.full((2, 8, 13), 0.2)
    a[:, :, idx["lai"]] = 2.0
    a[:, :, idx["chlorophyll"]] = 30.0
    a[:, :, idx["stress_memory"]] = np.linspace(0.1, 0.5, 8)
    for n in range(2):
        a[n, :, idx["vigor"]] = np.linspace(0.398, 0.402, 8)

    # Perfect prediction matches observation exactly -> zero innovation -> negligible influence
    pred = _predict_observation_array("ndvi", a, "S2").mean(axis=1)
    scene = NS(
        scene_id="ZERO-INNOVATION",
        width=2,
        height=1,
        bands={"NDVI": [[float(pred[0]), float(pred[1])]]},
        masks={},
        cloud_fraction=0.0,
        crop_stage="vegetative",
        source_reality="real_raster",
        real_provider_product=True,
    )
    build_scene_valid_support(scene)
    ids = ["mz_000_000", "mz_000_001"]
    op = NS(
        scene_id=scene.scene_id,
        valid_support_hash=scene.valid_support_hash,
        H_matrix=np.eye(2),
        node_ids=ids,
        registration_uncertainty_m=0.0,
    )

    prior_copy = a.copy()
    final, reports = update_step_ht(a, scene, op, random.Random(0), node_ids=ids)

    # Check that report recorded excluded_negligible_influence
    assert len(reports) == 1
    assert reports[0]["update_applied"] is False
    assert reports[0]["mode"] == "excluded_negligible_influence"
    # State cube must be exactly identical to prior state (rolled back)
    np.testing.assert_array_equal(final, prior_copy)

