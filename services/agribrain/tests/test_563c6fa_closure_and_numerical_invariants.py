"""Verification test suite for 563c6fa closure and numerical invariants.

Covers:
1. Scale-relative PSD covariance validation and nonfinite eigenvalue rejection.
2. Covariance symmetry and micro-scale negative eigenvalue rejection.
3. Exact canonical root_zone_water V90 variable resolution and conflicting declaration rejection.
4. State ensemble rollback on negligible-influence assimilation exclusion (Ht and proxy).
5. Mixed target state updates: rollback of uninfluenced target slices while preserving influenced updates.
6. Fail-closed invariant uncertainty normalization (missing/NaN -> high uncertainty).
7. Fail-closed display trust policy for NaN / nonfinite quality inputs.
8. Layer 5 v3 and Layer 10 v2 cache policy coexistence with live Layer 10 execution.
"""
import copy
import math
import os
import random
import uuid
from datetime import date
from types import SimpleNamespace as NS

import numpy as np
import pytest

from services.agribrain.layer10_sire.schema import SurfaceType, SurfaceArtifact, Layer10Output
from services.agribrain.layer10_sire.surfaces.asmae import (
    _validate_covariance,
    get_standard_variable_name,
    get_surface_display_policy,
)
from services.agribrain.layer10_sire.invariants import enforce_layer10_invariants
from services.agribrain.layer10_sire.runner import save_layer10_to_cache, load_layer10_from_cache
from services.agribrain.layer10_sire.surface_contract import (
    RENDER_AUTHORIZATION_VERSION,
    SURFACES_SCHEMA_VERSION,
    PublicationStatus,
)
from services.agribrain.scientific_contracts import LAYER10_PUBLICATION_SCHEMA_VERSION
from services.agribrain.layer05_asmae.cache import (
    STATE_SUPPORT_POLICY_VERSION,
    get_asmae_cache_key,
)
from services.agribrain.layer05_asmae.schema import ASMAEInput
from services.agribrain.layer05_asmae.config import STATE_NAMES
from services.agribrain.layer05_asmae.geometry.support_contract import build_scene_valid_support
from services.agribrain.layer05_asmae.assimilation.filter import (
    update_step_ht,
    update_step_proxy,
    _predict_observation_array,
)


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

    # Counterexample 1: Nonsymmetric at small scale (diff = 5e-5, scale = 5e-5)
    nonsym_small = [[1e-8, 5e-5], [0, 1e-8]]
    is_valid, is_malformed = _validate_covariance(nonsym_small)
    assert is_valid is False
    assert is_malformed is True

    # Counterexample 2: Small scale indefinite matrix with negative eigenvalue -9.9e-14
    indef_micro = [[1e-15, 1e-13], [1e-13, 1e-15]]
    is_valid, is_malformed = _validate_covariance(indef_micro)
    assert is_valid is False
    assert is_malformed is True


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
    """Root-zone water must resolve to root_zone_water, never canopy_water, and reject conflicting canonical declarations."""
    rz_type = getattr(SurfaceType, "ASMAE_ROOT_ZONE_WATER", None)
    if rz_type is not None:
        assert get_standard_variable_name(rz_type) == "root_zone_water"
        assert get_standard_variable_name(rz_type, "root_zone_water") == "root_zone_water"
        assert get_standard_variable_name(rz_type, "water") == "root_zone_water"
        # Conflicting canonical declarations must be rejected
        assert get_standard_variable_name(rz_type, "canopy_water") == "conflict_rejected"
        assert get_standard_variable_name(rz_type, "vigor") == "conflict_rejected"

    cw_type = getattr(SurfaceType, "ASMAE_CANOPY_WATER", None)
    if cw_type is not None:
        assert get_standard_variable_name(cw_type) == "canopy_water"
        assert get_standard_variable_name(cw_type, "canopy_water") == "canopy_water"
        # Conflicting canonical declarations must be rejected
        assert get_standard_variable_name(cw_type, "root_zone_water") == "conflict_rejected"


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
    """Layer 5 v3 cache policy and Layer 10 cache execute and coexist without interference."""
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
    key_l5 = get_asmae_cache_key(inp)
    assert isinstance(key_l5, str) and len(key_l5) == 64

    # Execute Layer 10 cache write and read
    l10_key = f"coexist_test_{uuid.uuid4().hex[:12]}"
    surface = SurfaceArtifact(
        surface_id="S_COEXIST",
        semantic_type=SurfaceType.NDVI_CLEAN,
        grid_ref="2x2",
        values=[[0.25, 0.35], [0.45, 0.55]],
        units="index",
        native_resolution_m=10.0,
    )
    prov = {
        "publication_run_id": "test_coexist_run",
        "request_run_id": "test_coexist_run",
        "publication_id": f"pub_{l10_key[:16]}",
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "layer10_publication_schema_version": LAYER10_PUBLICATION_SCHEMA_VERSION,
        "publication_status": PublicationStatus.VALID_NORMAL.value,
    }
    l10_out = Layer10Output(
        run_id="test_coexist_run",
        timestamp="2026-10-26T12:00:00Z",
        surface_pack=[surface],
        render_authorizations={"satellite": {"canopy": {"base": {}}}},
        render_authorization_version=RENDER_AUTHORIZATION_VERSION,
        asmae_proof={"proof": "ok"},
        mode_display_state={"canopy": {"display": "ok"}},
        source_policy_display_state={"policy": "ok"},
        core_asmae_evidence_state={"state": "ok"},
        publication_surface_state={"state": "ok"},
        publication_id=f"pub_{l10_key[:16]}",
        publication_run_id="test_coexist_run",
        surface_schema_version=SURFACES_SCHEMA_VERSION,
        publication_status=PublicationStatus.VALID_NORMAL.value,
        provenance=dict(prov),
    )

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cache_dir = os.path.join(base_dir, "artifacts", "surfaces_cache")
    cache_json = os.path.join(cache_dir, f"{l10_key}.json")
    try:
        written_bytes = save_layer10_to_cache(l10_key, l10_out)
        assert written_bytes > 0

        # Verify Layer 10 cache hit
        loaded_l10 = load_layer10_from_cache(l10_key)
        assert loaded_l10 is not None
        assert loaded_l10.surface_pack[0].values[0][0] == pytest.approx(0.25)

        # Verify Layer 5 cache key is invariant to Layer 10 cache execution
        key_l5_after = get_asmae_cache_key(inp)
        assert key_l5 == key_l5_after
    finally:
        if os.path.exists(cache_json):
            try:
                os.remove(cache_json)
            except OSError:
                pass
        if os.path.exists(cache_dir):
            for fname in os.listdir(cache_dir):
                if l10_key in fname:
                    try:
                        os.remove(os.path.join(cache_dir, fname))
                    except OSError:
                        pass


def test_negligible_influence_ensemble_rollback():
    """Rejected negligible-influence update must roll back state_cube without mutation in Ht."""
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


def test_proxy_negligible_influence_rollback():
    """Rejected negligible-influence update must roll back ensemble without mutation in proxy path."""
    idx = {s: i for i, s in enumerate(STATE_NAMES)}
    ens = {"mz1": [[0.4] * 13 for _ in range(6)]}
    for m in ens["mz1"]:
        m[idx["vigor"]] = 0.4
        m[idx["lai"]] = 2.0
    prior_copy = copy.deepcopy(ens)

    scene = NS(
        scene_id="PROXY_ZERO_INNOVATION",
        width=1,
        height=1,
        bands={"NDVI": [[0.7]]},
        masks={},
        cloud_fraction=0.0,
        crop_stage="vegetative",
        source_reality="real_raster",
        real_provider_product=True,
    )
    final, reports = update_step_proxy(ens, scene, None, random.Random(0))

    assert len(reports) == 1
    assert reports[0]["update_applied"] is False
    assert reports[0]["mode"] == "excluded_negligible_influence"
    assert final == prior_copy


def test_mixed_target_influence_rollback_ht():
    """Mixed target Ht update must update influenced target states and roll back uninfluenced slices."""
    idx = {s: i for i, s in enumerate(STATE_NAMES)}
    a = np.full((2, 8, 13), 0.2)
    a[:, :, idx["lai"]] = 2.0
    a[:, :, idx["chlorophyll"]] = 30.0
    a[:, :, idx["stress_memory"]] = np.linspace(0.1, 0.5, 8)
    a[:, :, idx["vigor"]] = np.linspace(0.3, 0.5, 8)

    pred = _predict_observation_array("ndvi", a, "S2").mean(axis=1)
    scene = NS(
        scene_id="MIXED_TARGET_HT",
        width=2,
        height=1,
        bands={"NDVI": [[float(pred[0]) + 0.15, float(pred[1]) + 0.15]]},
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

    assert len(reports) == 1
    assert reports[0]["update_applied"] is True
    assert "vigor" in reports[0]["accepted_target_states"]
    assert "lai" in reports[0]["excluded_target_states"]
    # Vigor received update
    assert not np.allclose(final[:, :, idx["vigor"]], prior_copy[:, :, idx["vigor"]])
    # Uninfluenced lai was rolled back to exact prior slice
    np.testing.assert_array_equal(final[:, :, idx["lai"]], prior_copy[:, :, idx["lai"]])


def test_mixed_target_influence_rollback_proxy():
    """Mixed target proxy update must update influenced target states and roll back uninfluenced columns."""
    idx = {s: i for i, s in enumerate(STATE_NAMES)}
    ens = {
        "mz1": [
            [(0.35 + 0.02 * j if i == idx["vigor"] else (2.0 if i == idx["lai"] else 0.2)) for i in range(13)]
            for j in range(8)
        ]
    }
    prior_copy = copy.deepcopy(ens)
    scene = NS(
        scene_id="MIXED_TARGET_PROXY",
        width=1,
        height=1,
        bands={"NDVI": [[0.7]]},
        masks={},
        cloud_fraction=0.0,
        crop_stage="vegetative",
        source_reality="real_raster",
        real_provider_product=True,
    )
    final, reports = update_step_proxy(ens, scene, None, random.Random(0))

    assert len(reports) == 1
    assert reports[0]["update_applied"] is True
    assert "vigor" in reports[0]["accepted_target_states"]
    assert "lai" in reports[0]["excluded_target_states"]
    # Vigor received update
    assert any(final["mz1"][j][idx["vigor"]] != prior_copy["mz1"][j][idx["vigor"]] for j in range(8))
    # Uninfluenced lai was rolled back to exact prior column
    assert all(final["mz1"][j][idx["lai"]] == prior_copy["mz1"][j][idx["lai"]] for j in range(8))
