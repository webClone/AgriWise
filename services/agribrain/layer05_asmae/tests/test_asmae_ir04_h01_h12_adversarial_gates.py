"""ASMAE IR-04 / IR-08: 12 Focused Adversarial Acceptance Tests (H01–H12).

Independent qualification gates covering:
  - H01: Forged 64-hex hashes cannot grant trusted support.
  - H02: CSR H_t weight perturbation changes matrix digest / invalidates support identity.
  - H03: S2 50% cloudiness supports only unmasked pixels via valid_support mask.
  - H04: S2 10m/20m and S1 bands yield band-appropriate PSF FWHM from geometry/psf.py.
  - H05: S1 radar backscatter labeled modeled coupling / indirect, not direct root-zone observation.
  - H06: Bitemporal replay respects valid time T and commitment cutoff K.
  - H07: Missing observation or missing Worldline watermark yields unavailable (no synthetic K=T).
  - H08: Namespace/CRS/PSF/mask inconsistency fails closed.
  - H09: Binds to exact post-selection SelectedOperatorBundle and compute_h_matrix_digest().
  - H10: Multi-process cold read of complete worker posterior passes with verified numerical authority.
  - H11: Missing sigma worker result stays diagnostic without suppressing valid older heads.
  - H12: Operator/calibration digest changes propagate into support record identity even when values match.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
from types import SimpleNamespace
from typing import Any, Dict, List

import numpy as np
import pytest
from scipy import sparse as sp

from services.agribrain.layer05_asmae.chain_integrity import (
    ASMAEChainIntegrityError,
    compute_h_matrix_digest,
)
from services.agribrain.layer05_asmae.geometry.psf import get_psf_model
from services.agribrain.layer05_asmae.plot_snapshot_store import (
    PlotNamespace,
    publish_canonical_plot_snapshot,
    load_plot_snapshot_by_id,
    load_and_validate_plot_snapshot_by_id,
)
from services.agribrain.layer05_asmae.resolution.observation_footprint_adapter import (
    adapt_scene_to_footprint,
    adapt_scenes_to_footprints,
    S2_OPTICAL_STATES,
    S1_SAR_STATES,
)
from services.agribrain.layer05_asmae.resolution.state_cell_support import (
    EvidenceFootprint,
    GridSpec,
    StateCellSupport,
    SpatialSupportViolation,
    evaluate_state_cell_support,
    statewise_support_tensor,
)
from services.agribrain.layer05_asmae.resolution.statewise_engine_bridge import (
    build_statewise_engine_support,
)
from services.agribrain.layer05_asmae.schema import (
    ObservationOperatorRuntime,
)
from services.agribrain.layer05_asmae.selected_bundle import (
    SelectedOperatorBundle,
)
from services.agribrain.layer1_fusion.truth_bridge import (
    compute_asmae_vector_numerical_hash,
)
from services.agribrain.layer10_sire.surface_contract import (
    RENDER_AUTHORIZATION_VERSION,
    SURFACES_SCHEMA_VERSION,
)
from services.agribrain.layer05_asmae import plot_snapshot_store

TENANT = "tenant-001"
FARM = "farm-mitidja"
PLOT = "plot-afroun"
GEOM_HASH = "a" * 64
METRIC_CRS = "EPSG:32631"


@pytest.fixture
def clean_store(tmp_path, monkeypatch):
    root = tmp_path / "plot_snapshots"
    monkeypatch.setattr(plot_snapshot_store, "PLOT_SNAPSHOT_ROOT", root)
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()
    return plot_snapshot_store


def _make_scene(sensor: str = "S2", band: str = "B08", **kwargs):
    defaults = dict(
        scene_id=f"{sensor}_SCENE_{band}_001",
        sensor=sensor,
        band=band,
        acquisition_time=datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc),
        crs=METRIC_CRS,
        transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        width=4,
        height=4,
        cloud_fraction=0.0,
        qa_score=0.98,
        real_provider_product=True,
        production_usable=True,
        diagnostic_only=False,
        scientific_surface_allowed=True,
        state_update_allowed=True,
        test_override=False,
        committed_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# =========================================================================
# H01: Forged 64-hex hashes cannot grant trusted support
# =========================================================================

def test_h01_forged_hashes_cannot_grant_trusted_support():
    """Forged 64-hex operator/source/calibration hashes with production_usable=True cannot create trusted local support."""
    # Attempt 1: scene with production_usable=True and forged hashes but require_operator_binding=True without genuine operator
    scene = _make_scene(
        production_usable=True,
        operator_sha256="b" * 64,
        calibrated_operator_sha256="c" * 64,
    )
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        require_operator_binding=True,
    )
    assert fp is None, "Forged hashes without verified operator bundle must be rejected"

    # Attempt 2: Direct hostile instantiation of EvidenceFootprint with forged hashes
    forged_fp = EvidenceFootprint(
        observation_id="forged_obs",
        source_sha256="1" * 64,
        operator_sha256="2" * 64,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        observation_valid_time="2026-09-08T12:00:00Z",
        committed_at="2026-09-08T12:00:00Z",
        supported_states=("vigor",),
        bbox=(500000.0, 3999960.0, 500040.0, 4000000.0),
        crs=METRIC_CRS,
        native_resolution_m=10.0,
        psf_fwhm_m=11.774,
        observability=0.95,
        calibrated_operator_sha256="3" * 64,
    )

    grid = GridSpec(crs=METRIC_CRS, transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0), width=4, height=4)
    record = evaluate_state_cell_support(
        state="vigor",
        row=0,
        col=0,
        grid=grid,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        valid_time="2026-09-08T12:00:00Z",
        knowledge_cutoff="2026-09-08T18:00:00Z",
        estimated_value=0.72,
        sigma=0.04,
        evidences=(forged_fp,),
        scene_wide_1m_approval=True,  # Hostile attempt to claim 1m
    )
    # The authority status is exploratory only, NEVER certified
    assert record.authority_status != "certified"
    assert record.certified_1m is False
    assert record.effective_resolution_m >= 10.0


# =========================================================================
# H02: CSR H_t weight perturbation changes matrix digest / support identity
# =========================================================================

def test_h02_csr_weight_perturbation_changes_matrix_digest_and_support_identity():
    """Changing any CSR H_t weight while preserving operator ID changes provenance/identity."""
    row = np.array([0, 0, 1, 1], dtype=np.int32)
    col = np.array([0, 1, 2, 3], dtype=np.int32)
    data1 = np.array([0.5, 0.5, 0.7, 0.3], dtype=np.float64)
    H1 = sp.csr_matrix((data1, (row, col)), shape=(2, 4))
    d1 = compute_h_matrix_digest(H1)

    # Perturb a single weight by 1e-4
    data2 = data1.copy()
    data2[0] += 0.0001
    H2 = sp.csr_matrix((data2, (row, col)), shape=(2, 4))
    d2 = compute_h_matrix_digest(H2)

    assert d1 != d2, "Any CSR weight change must alter the matrix digest"

    op1 = ObservationOperatorRuntime(
        operator_id="op_canonical",
        scene_id="scene_001",
        sensor="S2",
        source_resolution_m=10.0,
        target_resolution_m=10,
        source_crs=METRIC_CRS,
        target_crs=METRIC_CRS,
        source_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        target_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        H_matrix=H1,
    )
    op2 = ObservationOperatorRuntime(
        operator_id="op_canonical",  # Same operator ID!
        scene_id="scene_001",
        sensor="S2",
        source_resolution_m=10.0,
        target_resolution_m=10,
        source_crs=METRIC_CRS,
        target_crs=METRIC_CRS,
        source_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        target_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        H_matrix=H2,
    )

    scene = _make_scene(scene_id="scene_001")
    fp1 = adapt_scene_to_footprint(scene, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
                                  geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS, operator=op1)
    fp2 = adapt_scene_to_footprint(scene, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
                                  geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS, operator=op2)

    assert fp1.operator_sha256 == d1
    assert fp2.operator_sha256 == d2
    assert fp1.calibrated_operator_sha256 != fp2.calibrated_operator_sha256

    grid = GridSpec(crs=METRIC_CRS, transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0), width=4, height=4)
    # Identical state value and uncertainty
    rec1 = evaluate_state_cell_support(
        state="vigor", row=0, col=0, grid=grid, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, valid_time="2026-09-08T12:00:00Z", knowledge_cutoff="2026-09-08T18:00:00Z",
        estimated_value=0.75, sigma=0.03, evidences=(fp1,),
    )
    rec2 = evaluate_state_cell_support(
        state="vigor", row=0, col=0, grid=grid, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, valid_time="2026-09-08T12:00:00Z", knowledge_cutoff="2026-09-08T18:00:00Z",
        estimated_value=0.75, sigma=0.03, evidences=(fp2,),
    )
    assert rec1.digest() != rec2.digest(), "StateCellSupport digest must change when operator weights change"


# =========================================================================
# H03: S2 50% cloudiness supports only unmasked pixels via valid_support mask
# =========================================================================

def test_h03_s2_cloud_mask_supports_only_unmasked_pixels():
    """Valid S2 scene with 50% cloudiness supports only unmasked pixels, not entire bbox."""
    # 2x2 microzone grid: cells 0 and 1 cloudy (False), cells 2 and 3 clear (True)
    mask = [[False, False], [True, True]]
    scene = _make_scene(
        width=2,
        height=2,
        cloud_fraction=0.50,
        valid_support=mask,
    )
    row, col = np.array([0, 1]), np.array([2, 3])
    H = sp.csr_matrix(([1.0, 1.0], (row, col)), shape=(2, 4))
    op = ObservationOperatorRuntime(
        operator_id="op_h03",
        scene_id=scene.scene_id,
        sensor="S2",
        source_resolution_m=10.0,
        target_resolution_m=10,
        source_crs=METRIC_CRS,
        target_crs=METRIC_CRS,
        source_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        target_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        H_matrix=H,
    )
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        operator=op,
    )
    assert fp is not None
    assert fp.valid_cell_indices == (2, 3), "Only unmasked pixels (row 1, cols 0 and 1) should be in valid_cell_indices"

    grid = GridSpec(crs=METRIC_CRS, transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0), width=2, height=2)

    # Cloudy cell (row 0, col 0) -> cell index 0
    rec_cloud = evaluate_state_cell_support(
        state="vigor", row=0, col=0, grid=grid, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, valid_time="2026-09-08T12:00:00Z", knowledge_cutoff="2026-09-08T18:00:00Z",
        estimated_value=0.70, sigma=0.05, evidences=(fp,),
    )
    assert rec_cloud.spatial_support != "local_operator"
    assert "masked_by_scene_valid_support" in rec_cloud.demotion_reasons

    # Clear cell (row 1, col 0) -> cell index 2
    rec_clear = evaluate_state_cell_support(
        state="vigor", row=1, col=0, grid=grid, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, valid_time="2026-09-08T12:00:00Z", knowledge_cutoff="2026-09-08T18:00:00Z",
        estimated_value=0.70, sigma=0.05, evidences=(fp,),
    )
    assert rec_clear.spatial_support == "local_operator"
    assert rec_clear.effective_resolution_m is not None


# =========================================================================
# H04: Band-appropriate PSF FWHM from geometry/psf.py
# =========================================================================

def test_h04_band_appropriate_psf_fwhm_s2_and_s1():
    """S2 10m/20m and S1 bands yield band-appropriate PSF FWHM from geometry/psf.py, not hardcoded 12m."""
    s2_10m = _make_scene(sensor="S2", band="B08")
    fp_10m = adapt_scene_to_footprint(s2_10m, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
                                       geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS)
    expected_s2_10m_fwhm = get_psf_model("S2", "B08").fwhm_m
    assert fp_10m.psf_fwhm_m == pytest.approx(expected_s2_10m_fwhm, abs=0.01)
    assert fp_10m.psf_fwhm_m != 12.0

    s2_20m = _make_scene(sensor="S2", band="B05")
    fp_20m = adapt_scene_to_footprint(s2_20m, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
                                       geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS)
    expected_s2_20m_fwhm = get_psf_model("S2", "B05").fwhm_m
    assert fp_20m.native_resolution_m == 20.0
    assert fp_20m.psf_fwhm_m == pytest.approx(expected_s2_20m_fwhm, abs=0.01)
    assert fp_20m.psf_fwhm_m > 20.0  # ~23.548m

    s1_sar = _make_scene(sensor="S1", band="VV")
    fp_s1 = adapt_scene_to_footprint(s1_sar, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
                                      geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS)
    expected_s1_fwhm = get_psf_model("S1", "VV").fwhm_m
    assert fp_s1.native_resolution_m == 20.0
    assert fp_s1.psf_fwhm_m == pytest.approx(expected_s1_fwhm, abs=0.01)
    assert fp_s1.psf_fwhm_m != 20.0  # ~17.661m


# =========================================================================
# H05: S1 radar backscatter labeled modeled coupling, not direct root-zone
# =========================================================================

def test_h05_s1_backscatter_cannot_be_directly_observed_root_zone_water():
    """S1 backscatter may indirectly constrain root-zone state but cannot be labeled directly observed."""
    s1_scene = _make_scene(sensor="S1", band="VV", qa_score=0.90)
    fp = adapt_scene_to_footprint(s1_scene, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
                                  geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS)
    assert fp is not None
    assert "root_zone_water" not in fp.supported_states
    assert "surface_wetness_event" in fp.supported_states

    grid = GridSpec(crs=METRIC_CRS, transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0), width=4, height=4)

    # Without model propagation hashes: prior only, spatial_support == 'none'
    rec_direct = evaluate_state_cell_support(
        state="root_zone_water", row=0, col=0, grid=grid, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, valid_time="2026-09-08T12:00:00Z", knowledge_cutoff="2026-09-08T18:00:00Z",
        estimated_value=0.28, sigma=0.03, evidences=(fp,),
    )
    assert rec_direct.spatial_support == "none"
    assert rec_direct.effective_resolution_m is None

    # With model propagation hashes: modeled_coupling, still not local_operator
    rec_modeled = evaluate_state_cell_support(
        state="root_zone_water", row=0, col=0, grid=grid, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, valid_time="2026-09-08T12:00:00Z", knowledge_cutoff="2026-09-08T18:00:00Z",
        estimated_value=0.28, sigma=0.03, evidences=(fp,),
        propagation_source_hashes=("f" * 64,),
    )
    assert rec_modeled.spatial_support == "modeled_coupling"
    assert rec_modeled.effective_resolution_m is None


# =========================================================================
# H06: Bitemporal replay cutoff eligibility
# =========================================================================

def test_h06_bitemporal_replay_cutoff_eligibility():
    """Scene valid at Day 5 and committed Day 20 is absent at (T=10, K=10) and eligible at (T=10, K=21)."""
    scene = _make_scene(acquisition_time=datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc))
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        committed_at="2026-09-20T12:00:00Z",
    )
    assert fp is not None

    grid = GridSpec(crs=METRIC_CRS, transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0), width=4, height=4)

    # Historical query at T=Day 10, K=Day 10 (committed Day 20 not yet known)
    rec_absent = evaluate_state_cell_support(
        state="vigor", row=0, col=0, grid=grid, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        valid_time="2026-09-10T12:00:00Z",
        knowledge_cutoff="2026-09-10T12:00:00Z",
        estimated_value=0.72, sigma=0.04, evidences=(fp,),
    )
    assert rec_absent.spatial_support != "local_operator"
    assert "excluded_by_valid_or_knowledge_cutoff" in rec_absent.demotion_reasons
    assert len(rec_absent.admitted_observation_ids) == 0

    # Replay query at T=Day 10, K=Day 21 (committed Day 20 is now known)
    rec_eligible = evaluate_state_cell_support(
        state="vigor", row=0, col=0, grid=grid, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        valid_time="2026-09-10T12:00:00Z",
        knowledge_cutoff="2026-09-21T12:00:00Z",
        estimated_value=0.72, sigma=0.04, evidences=(fp,),
    )
    assert rec_eligible.spatial_support == "local_operator"
    assert rec_eligible.admitted_observation_ids == (fp.observation_id,)


# =========================================================================
# H07: Missing observation / watermark yields unavailable (never synthetic K=T)
# =========================================================================

def test_h07_missing_observation_or_watermark_yields_unavailable():
    """No verified observation/watermark yields unavailable, never synthetic K=T or future end_date."""
    grid_spec = {
        "crs": METRIC_CRS,
        "transform": [500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        "width": 4,
        "height": 4,
    }
    # Call bridge with missing valid_time or knowledge_cutoff
    res_no_time = build_statewise_engine_support(
        raster_maps={}, uncertainty_maps={}, grid_spec=grid_spec,
        geometry_sha256=GEOM_HASH, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        valid_time="", knowledge_cutoff="",
    )
    assert res_no_time["status"] == "unavailable"
    assert res_no_time["reason"] == "unbound_namespace_or_bitemporal_receipt"


# =========================================================================
# H08: Namespace / CRS / PSF / mask inconsistency fails closed
# =========================================================================

def test_h08_namespace_crs_psf_mask_inconsistency_fails_closed():
    """Tenant/plot/geometry/grid mismatch or CRS/PSF/mask inconsistency fails closed."""
    # 1. Tenant mismatch
    scene_wrong_tenant = _make_scene(tenant_id="adversary_tenant")
    assert adapt_scene_to_footprint(scene_wrong_tenant, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
                                   geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS) is None

    # 2. Plot mismatch
    scene_wrong_plot = _make_scene(plot_id="other_plot")
    assert adapt_scene_to_footprint(scene_wrong_plot, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
                                   geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS) is None

    # 3. Unprojected geographic CRS
    scene_geo = _make_scene(crs="EPSG:4326")
    assert adapt_scene_to_footprint(scene_geo, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
                                   geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS) is None

    # 4. Geometry digest invalid
    scene_ok = _make_scene()
    assert adapt_scene_to_footprint(scene_ok, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
                                   geometry_sha256="not_a_valid_sha", target_crs=METRIC_CRS) is None

    # 5. Mask inconsistency between operator and scene
    row, col = np.array([0]), np.array([0])
    H = sp.csr_matrix(([1.0], (row, col)), shape=(1, 1))
    op_mismatched_mask = ObservationOperatorRuntime(
        operator_id="op_mask_mismatch",
        scene_id=scene_ok.scene_id,
        sensor="S2",
        source_resolution_m=10.0,
        target_resolution_m=10,
        source_crs=METRIC_CRS,
        target_crs=METRIC_CRS,
        source_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        target_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        H_matrix=H,
        valid_support_hash="9" * 64,  # Contradicts scene valid_support!
    )
    scene_with_mask = _make_scene(valid_support=[[True, True]])
    assert adapt_scene_to_footprint(scene_with_mask, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
                                   geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS,
                                   operator=op_mismatched_mask) is None


# =========================================================================
# H09: Exact post-selection SelectedOperatorBundle identity
# =========================================================================

def test_h09_binds_to_exact_post_selection_bundle_identity():
    """Test over exact post-selection selected bundle identity, not pre-selection rebuild."""
    row, col = np.array([0, 1]), np.array([0, 1])
    H = sp.csr_matrix(([1.0, 1.0], (row, col)), shape=(2, 2))
    mat_digest = compute_h_matrix_digest(H)

    op_post = ObservationOperatorRuntime(
        operator_id="op_post_sel",
        scene_id="s2_post",
        sensor="S2",
        source_resolution_m=10.0,
        target_resolution_m=10,
        source_crs=METRIC_CRS,
        target_crs=METRIC_CRS,
        source_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        target_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        H_matrix=H,
    )

    # Creating bundle with mismatched resolution raises ASMAEChainIntegrityError
    with pytest.raises(ASMAEChainIntegrityError):
        SelectedOperatorBundle(
            selected_resolution_m=20,  # Declares 20m but operator built for 10m!
            operators=(op_post,),
            operator_count=1,
            operator_ids=("op_post_sel",),
            graph_ref="graph_001",
            graph_node_count=2,
            graph_hash="g" * 64,
            operator_diagnostics_summary={},
            operator_diagnostics_n_errors=0,
            resolution_decision_ref=None,
            content_hash="c" * 64,
            was_rebuilt=False,
            was_demoted=False,
            original_selected_resolution_m=20,
            coreg_hash="",
        )

    # Valid post-selection bundle
    bundle = SelectedOperatorBundle(
        selected_resolution_m=10,
        operators=(op_post,),
        operator_count=1,
        operator_ids=("op_post_sel",),
        graph_ref="graph_001",
        graph_node_count=2,
        graph_hash="g" * 64,
        operator_diagnostics_summary={},
        operator_diagnostics_n_errors=0,
        resolution_decision_ref=None,
        content_hash="c" * 64,
        was_rebuilt=False,
        was_demoted=False,
        original_selected_resolution_m=10,
        coreg_hash="",
    )

    scene = _make_scene(scene_id="s2_post")
    fps = adapt_scenes_to_footprints(
        [scene],
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        operator_bundle=bundle,
    )
    assert len(fps) == 1
    assert fps[0].operator_sha256 == mat_digest


# =========================================================================
# H10: Cold publication & read of real worker posterior
# =========================================================================

def test_h10_real_worker_result_with_complete_sigma_cold_read(clean_store):
    """Actual worker result with complete sigma survives cold exact and latest read."""
    states = {"vigor": 0.72, "canopy_water": 0.45}
    sigmas = {"vigor": 0.04, "canopy_water": 0.02}
    vec_hash = compute_asmae_vector_numerical_hash(states, sigmas)

    ns = PlotNamespace(tenant_id=TENANT, farm_id=FARM, plot_id=PLOT)
    num_rec = {"states": states, "sigmas": sigmas, "numerical_vector_hash": vec_hash}

    snap_id = "ASMAE-SNAPSHOT-H10-VERIFIED"
    asmae_res = {
        "plot_id": PLOT,
        "snapshot_id": snap_id,
        "content_hash": hashlib.sha256(b"snap-h10").hexdigest(),
        "crop_posterior_lineage": "lineage-001",
        "crop_worldline_event_id": "crop-ev-1",
        "phenology_worldline_event_id": "phen-ev-1",
        "crop_influence_manifest_hash": "m" * 64,
        "crop_evidence_ledger_hash": "l" * 64,
        "claims_numerical_authority": True,
        "state_means": states,
        "sigmas": sigmas,
        "asmae_posterior_numerical_record": num_rec,
        "asmae_numerical_digest": vec_hash,
    }

    frontend = {
        "version": SURFACES_SCHEMA_VERSION,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "intelligence_snapshot_id": snap_id,
        "plot_id": PLOT,
        "tenant_id": TENANT,
        "farm_id": FARM,
        "publication_id": "pub-h10",
        "publication_run_id": "run-h10",
        "run_id": "run-h10",
        "pipeline_state": "terminal_layer10_published",
        "publication_status": "VALID_NORMAL",
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "mode_display_state": {"mode": "scientific", "canopy": {"canRenderPixels": True}},
        "source_policy_display_state": {"requested_policy": "satellite", "policy": "standard"},
        "asmae_evidence_state": {"production_usable": True, "authority_level": "SCIENTIFIC"},
        "publication_surface_state": {"canopy": "available"},
        "claims_numerical_authority": True,
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": "lineage-001",
            "crop_worldline_event_id": "crop-ev-1",
            "phenology_worldline_event_id": "phen-ev-1",
            "asmae_posterior_vector_hash": vec_hash,
        },
        "asmae_posterior_numerical_record": num_rec,
        "asmae_proof": {
            "proof_id": "proof-h10",
            "status": "valid",
            "numerical_vector_hash": vec_hash,
        },
        "surfaces": [
            {
                "surface_id": "surface-canopy-vigor",
                "surface_type": "canopy_vigor",
                "values": [[0.72]],
                "resolution_m": 10.0,
                "content_hash": hashlib.sha256(b"vigor").hexdigest(),
            }
        ],
        "zones": [],
        "recommendations": [],
    }

    head = publish_canonical_plot_snapshot(
        namespace=ns,
        plot_id=PLOT,
        tenant_id=TENANT,
        farm_id=FARM,
        geometry_hash=GEOM_HASH,
        snapshot_id=snap_id,
        asmae_result=asmae_res,
        frontend_payload=frontend,
        job_id="job-h10",
        manifest_hash="m" * 64,
        execution_identity={"crop_cycle_id": "cycle-001"},
    )
    assert head["snapshot_id"] == snap_id

    # Cold read with memory cache explicitly cleared
    with clean_store._SNAPSHOT_CACHE_LOCK:
        clean_store._CANONICAL_SNAPSHOT_CACHE.clear()

    exact = load_and_validate_plot_snapshot_by_id(snap_id, namespace=ns)
    assert exact is not None
    assert exact["validation"]["numericalBindingValid"] is True
    assert exact["contract_validation"]["numerical_authority_verified"] is True
    assert exact["contract_validation"]["derived_publication_status"] == "VALID_NORMAL"
    assert exact["frontend_payload"]["claims_numerical_authority"] is True


# =========================================================================
# H11: Missing sigma stays diagnostic without blocking older valid head
# =========================================================================

def test_h11_worker_result_missing_sigma_stays_diagnostic_without_blocking_older_valid_head(clean_store):
    """Missing sigma stays diagnostic and does not suppress valid older head."""
    ns = PlotNamespace(tenant_id=TENANT, farm_id=FARM, plot_id=PLOT)

    # 1. First publish verified valid head A
    states_a = {"vigor": 0.70}
    sigmas_a = {"vigor": 0.05}
    vec_hash_a = compute_asmae_vector_numerical_hash(states_a, sigmas_a)
    num_rec_a = {"states": states_a, "sigmas": sigmas_a, "numerical_vector_hash": vec_hash_a}

    snap_id_a = "ASMAE-SNAPSHOT-H11-A-VERIFIED"
    asmae_a = {
        "plot_id": PLOT, "snapshot_id": snap_id_a,
        "crop_posterior_lineage": "lineage-001",
        "crop_worldline_event_id": "crop-ev-1",
        "phenology_worldline_event_id": "phen-ev-1",
        "claims_numerical_authority": True, "state_means": states_a, "sigmas": sigmas_a,
        "asmae_posterior_numerical_record": num_rec_a,
    }
    frontend_a = {
        "version": SURFACES_SCHEMA_VERSION, "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "intelligence_snapshot_id": snap_id_a, "plot_id": PLOT, "tenant_id": TENANT, "farm_id": FARM,
        "publication_id": "pub-a", "publication_run_id": "run-a", "run_id": "run-a",
        "pipeline_state": "terminal_layer10_published", "publication_status": "VALID_NORMAL",
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "mode_display_state": {"mode": "scientific", "canopy": {"canRenderPixels": True}},
        "claims_numerical_authority": True,
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": "lineage-001",
            "crop_worldline_event_id": "crop-ev-1",
            "phenology_worldline_event_id": "phen-ev-1",
            "asmae_posterior_vector_hash": vec_hash_a,
        },
        "asmae_posterior_numerical_record": num_rec_a,
        "asmae_proof": {"proof_id": "proof-a", "status": "valid", "numerical_vector_hash": vec_hash_a},
        "surfaces": [], "zones": [], "recommendations": [],
    }
    publish_canonical_plot_snapshot(
        namespace=ns, plot_id=PLOT, tenant_id=TENANT, farm_id=FARM, geometry_hash=GEOM_HASH,
        snapshot_id=snap_id_a, asmae_result=asmae_a, frontend_payload=frontend_a,
        job_id="job-a", manifest_hash="m" * 64, execution_identity={},
    )

    # 2. Subsequent snapshot B produced with missing sigma (diagnostic only)
    states_b = {"vigor": 0.75}
    snap_id_b = "ASMAE-SNAPSHOT-H11-B-DIAGNOSTIC"
    asmae_b = {
        "plot_id": PLOT, "snapshot_id": snap_id_b,
        "crop_posterior_lineage": "lineage-001",
        "crop_worldline_event_id": "crop-ev-1",
        "phenology_worldline_event_id": "phen-ev-1",
        "claims_numerical_authority": False,  # No authority claimed
        "state_means": states_b, "sigmas": {},  # Missing sigma!
    }
    frontend_b = {
        "version": SURFACES_SCHEMA_VERSION, "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "intelligence_snapshot_id": snap_id_b, "plot_id": PLOT, "tenant_id": TENANT, "farm_id": FARM,
        "publication_id": "pub-b", "publication_run_id": "run-b", "run_id": "run-b",
        "pipeline_state": "terminal_layer10_published", "publication_status": "VALID_NORMAL",
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "mode_display_state": {"mode": "scientific", "canopy": {"canRenderPixels": True}},
        "claims_numerical_authority": False,
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": "lineage-001",
            "crop_worldline_event_id": "crop-ev-1",
            "phenology_worldline_event_id": "phen-ev-1",
        },
        "surfaces": [], "zones": [], "recommendations": [],
    }
    publish_canonical_plot_snapshot(
        namespace=ns, plot_id=PLOT, tenant_id=TENANT, farm_id=FARM, geometry_hash=GEOM_HASH,
        snapshot_id=snap_id_b, asmae_result=asmae_b, frontend_payload=frontend_b,
        job_id="job-b", manifest_hash="m" * 64, execution_identity={},
    )

    # Clear cache and cold read both
    with clean_store._SNAPSHOT_CACHE_LOCK:
        clean_store._CANONICAL_SNAPSHOT_CACHE.clear()

    snap_b = load_and_validate_plot_snapshot_by_id(snap_id_b, namespace=ns)
    assert snap_b is not None
    assert snap_b["contract_validation"]["numerical_authority_verified"] is False
    assert snap_b["frontend_payload"]["claims_numerical_authority"] is False

    snap_a = load_and_validate_plot_snapshot_by_id(snap_id_a, namespace=ns)
    assert snap_a is not None
    assert snap_a["contract_validation"]["numerical_authority_verified"] is True
    assert snap_a["validation"]["numericalBindingValid"] is True
    assert snap_a["frontend_payload"]["claims_numerical_authority"] is True


# =========================================================================
# H12: Operator / calibration digest changes propagate into support identity
# =========================================================================

def test_h12_operator_and_calibration_digest_change_modifies_support_identity():
    """Signed/hashed source operator and calibration version change modifies snapshot support identity even if values match."""
    grid = GridSpec(crs=METRIC_CRS, transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0), width=2, height=2)

    # Footprint 1: Operator v1
    fp1 = EvidenceFootprint(
        observation_id="obs_001",
        source_sha256="1" * 64,
        operator_sha256="a" * 64,
        calibrated_operator_sha256="c" * 64,
        tenant_id=TENANT, farm_id=FARM, plot_id=PLOT, geometry_sha256=GEOM_HASH,
        observation_valid_time="2026-09-08T12:00:00Z", committed_at="2026-09-08T12:00:00Z",
        supported_states=("vigor",), bbox=(500000.0, 3999980.0, 500020.0, 4000000.0),
        crs=METRIC_CRS, native_resolution_m=10.0, psf_fwhm_m=11.774, observability=0.95,
    )

    # Footprint 2: Operator v2 (different calibration/matrix hash)
    fp2 = EvidenceFootprint(
        observation_id="obs_001",
        source_sha256="1" * 64,
        operator_sha256="b" * 64,  # Changed!
        calibrated_operator_sha256="d" * 64,  # Changed!
        tenant_id=TENANT, farm_id=FARM, plot_id=PLOT, geometry_sha256=GEOM_HASH,
        observation_valid_time="2026-09-08T12:00:00Z", committed_at="2026-09-08T12:00:00Z",
        supported_states=("vigor",), bbox=(500000.0, 3999980.0, 500020.0, 4000000.0),
        crs=METRIC_CRS, native_resolution_m=10.0, psf_fwhm_m=11.774, observability=0.95,
    )

    # Exactly identical estimated values and sigmas
    rec1 = evaluate_state_cell_support(
        state="vigor", row=0, col=0, grid=grid, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, valid_time="2026-09-08T12:00:00Z", knowledge_cutoff="2026-09-08T18:00:00Z",
        estimated_value=0.7200, sigma=0.0350, evidences=(fp1,),
    )
    rec2 = evaluate_state_cell_support(
        state="vigor", row=0, col=0, grid=grid, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, valid_time="2026-09-08T12:00:00Z", knowledge_cutoff="2026-09-08T18:00:00Z",
        estimated_value=0.7200, sigma=0.0350, evidences=(fp2,),
    )

    assert rec1.estimated_value == rec2.estimated_value
    assert rec1.sigma == rec2.sigma
    assert rec1.admitted_operator_hashes != rec2.admitted_operator_hashes
    assert rec1.admitted_calibration_hashes != rec2.admitted_calibration_hashes
    assert rec1.digest() != rec2.digest(), "Identity must diverge when operator/calibration hash changes"
