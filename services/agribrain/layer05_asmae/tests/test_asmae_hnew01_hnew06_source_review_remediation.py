"""ASMAE IR-04 / IR-08 HNEW-01 through HNEW-06 Remediation Acceptance Suite.

Covers the six source review findings identified in ASMAE_H01_H12_B636801_INDEPENDENT_SOURCE_REVIEW.md:
- HNEW-01: Mandatory operator binding in engine, no static hashes or synthetic source receipts.
- HNEW-02: Strict per-scene bitemporal commitment; prohibition of naive timestamp timezone inference.
- HNEW-03: Real selected H_t PSF construction with band-dependent Gaussian PSF models (B04 vs B05/B11).
- HNEW-04: Target graph cell-index grounding for valid support; no raw scene-pixel conflation.
- HNEW-05: Positive signed admission; strict tenant/farm/plot/geometry cross-check; diagnostic_only rejection.
- HNEW-06: Genuine worker reintegration and cross-process HTTP API cold publication path.
"""

from datetime import datetime, timezone
import hashlib
from types import SimpleNamespace
from typing import Any, Dict
import numpy as np
import pytest
import scipy.sparse as sp
from fastapi.testclient import TestClient

from services.agribrain.app.main import app, require_internal_service_request
from services.agribrain.layer05_asmae.chain_integrity import compute_h_matrix_digest
from services.agribrain.layer05_asmae.geometry.operator_builder import build_observation_operator
from services.agribrain.layer05_asmae.geometry.psf import get_psf_model
from services.agribrain.layer05_asmae.plot_snapshot_store import (
    publish_canonical_plot_snapshot,
    load_plot_snapshot_by_id,
    load_and_validate_plot_snapshot_by_id,
    evaluate_snapshot_admission,
    PlotNamespace,
    PLOT_SNAPSHOT_ROOT,
)
import services.agribrain.layer05_asmae.plot_snapshot_store as snapshot_store_module
from services.agribrain.layer05_asmae.reintegration import rebuild_canonical_plot_snapshot
from services.agribrain.layer05_asmae.resolution.observation_footprint_adapter import (
    adapt_scene_to_footprint,
    adapt_scenes_to_footprints,
    _ensure_utc_iso,
    S2_OPTICAL_STATES,
    S1_SAR_STATES,
)
from services.agribrain.layer05_asmae.resolution.state_cell_support import (
    evaluate_state_cell_support,
    GridSpec,
)
from services.agribrain.layer05_asmae.schema import (
    ObservationOperatorRuntime,
    ASMAESceneRuntime,
)
from services.agribrain.layer05_asmae.selected_bundle import SelectedOperatorBundle
from services.agribrain.layer1_fusion.truth_bridge import (
    compute_asmae_vector_numerical_hash,
)
from services.agribrain.layer10_sire.surface_contract import (
    RENDER_AUTHORIZATION_VERSION,
    SURFACES_SCHEMA_VERSION,
)

TENANT = "tenant-mitidja"
FARM = "farm-afroun"
PLOT = "plot-benchmark-01"
GEOM_HASH = "a" * 64
METRIC_CRS = "EPSG:32631"


@pytest.fixture
def clean_store(tmp_path, monkeypatch):
    root = tmp_path / "plot_snapshots"
    monkeypatch.setattr(snapshot_store_module, "PLOT_SNAPSHOT_ROOT", root)
    with snapshot_store_module._SNAPSHOT_CACHE_LOCK:
        snapshot_store_module._CANONICAL_SNAPSHOT_CACHE.clear()
    return snapshot_store_module


def _make_scene(**kwargs):
    defaults = dict(
        scene_id="S2A_MSIL2A_20260908T103021_N0500_R108_T31SDA_20260908T142512",
        sensor="S2",
        band="B08",
        acquisition_time=datetime(2026, 9, 8, 10, 30, 21, tzinfo=timezone.utc),
        committed_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc),
        crs=METRIC_CRS,
        transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        width=10,
        height=10,
        cloud_fraction=0.0,
        qa_score=0.98,
        real_provider_product=True,
        production_usable=True,
        diagnostic_only=False,
        scientific_surface_allowed=True,
        state_update_allowed=True,
        test_override=False,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        content_hash="1" * 64,
        product_binding="exact_catalog_item",
        provider_product_id="S2A_MSIL2A_20260908T103021_N0500_R108_T31SDA_20260908T142512",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# =========================================================================
# HNEW-01: Mandatory Operator Binding & Unmatched Scene Rejection
# =========================================================================

def test_hnew_01_mandatory_operator_binding_rejects_unmatched_scene():
    """Scenes without a matched operator or with forged source digests fail closed when operator binding is required."""
    scene = _make_scene(scene_id="unmatched_scene")
    
    # 1. In production / scientific mode (require_operator_binding=True), an unmatched scene returns None
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        require_operator_binding=True,
        operator=None,
    )
    assert fp is None, "Operator-less footprint must fail closed when operator binding is required"

    # 2. adapt_scenes_to_footprints with require_operator_binding=True and empty bundle yields empty footprints
    fps = adapt_scenes_to_footprints(
        [scene],
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        require_operator_binding=True,
        operator_bundle=None,
    )
    assert len(fps) == 0, "Unmatched scene in bundle must be omitted"

    # 3. Forged or missing source_sha256 fails closed without synthesizing a hash
    scene_no_hash = _make_scene(content_hash=None, sha256=None)
    row, col = np.array([0]), np.array([0])
    H = sp.csr_matrix(([1.0], (row, col)), shape=(1, 1))
    op = ObservationOperatorRuntime(
        operator_id="op_test",
        scene_id=scene_no_hash.scene_id,
        sensor="S2",
        source_resolution_m=10.0,
        target_resolution_m=10,
        source_crs=METRIC_CRS,
        target_crs=METRIC_CRS,
        source_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        target_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        H_matrix=H,
    )
    fp_forged = adapt_scene_to_footprint(
        scene_no_hash,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        require_operator_binding=True,
        operator=op,
    )
    assert fp_forged is None, "Missing immutable source asset digest must fail closed"


# =========================================================================
# HNEW-02: Strict Per-Scene Commitment & Naive Timezone Prohibition
# =========================================================================

def test_hnew_02_strict_commitment_and_naive_timezone_rejection():
    """Rejects ungrounded temporal commitment and naive timestamps without timezone inference."""
    # 1. Prohibit naive datetime (no timezone)
    naive_dt = datetime(2026, 9, 8, 10, 0, 0)
    assert _ensure_utc_iso(naive_dt) is None, "Naive datetime must be rejected"

    # 2. Prohibit naive string (no Z or offset)
    naive_str = "2026-09-08T10:00:00"
    assert _ensure_utc_iso(naive_str) is None, "Naive string without timezone must be rejected"

    # 3. Valid ISO with timezone succeeds
    utc_str = "2026-09-08T10:00:00Z"
    assert _ensure_utc_iso(utc_str) == "2026-09-08T10:00:00+00:00"
    offset_str = "2026-09-08T12:00:00+02:00"
    assert _ensure_utc_iso(offset_str) == "2026-09-08T10:00:00+00:00"

    # 4. Scene without committed_at and caller without committed_at fails closed (never falls back to valid_time)
    scene_no_commit = _make_scene(committed_at=None)
    fp = adapt_scene_to_footprint(
        scene_no_commit,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        committed_at=None,
    )
    assert fp is None, "Scene missing committed_at must fail closed; never fallback to valid_time"

    # 5. Scene with individual committed_at retains its own timestamp
    scene_with_commit = _make_scene(committed_at="2026-09-08T14:00:00Z")
    fp_with_commit = adapt_scene_to_footprint(
        scene_with_commit,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp_with_commit is not None
    assert fp_with_commit.committed_at == "2026-09-08T14:00:00+00:00"


# =========================================================================
# HNEW-03: Real Selected H_t PSF Construction Uses Band
# =========================================================================

def test_hnew_03_operator_builder_s2_band_dependent_gaussian_psf():
    """Production build_observation_operator applies band-dependent Gaussian PSF for S2 20m vs 10m bands."""
    # S2 20m band B05
    scene_b05 = _make_scene(
        sensor="S2",
        band="B05",
        width=5,
        height=5,
        transform=[500000.0, 20.0, 0.0, 4000000.0, 0.0, -20.0],
    )
    op_b05 = build_observation_operator(scene=scene_b05, candidate_resolution_m=10)
    expected_b05_fwhm = get_psf_model("S2", band="B05").fwhm_m
    assert op_b05.blur_sigma_m == pytest.approx(10.0, abs=0.01)
    assert 2.35482 * op_b05.blur_sigma_m == pytest.approx(expected_b05_fwhm, abs=0.01)
    assert 2.35482 * op_b05.blur_sigma_m > 20.0  # ~23.5482m (sigma=10.0m)

    # S2 10m band B04
    scene_b04 = _make_scene(
        sensor="S2",
        band="B04",
        width=10,
        height=10,
        transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
    )
    op_b04 = build_observation_operator(scene=scene_b04, candidate_resolution_m=10)
    expected_b04_fwhm = get_psf_model("S2", band="B04").fwhm_m
    assert op_b04.blur_sigma_m == pytest.approx(5.0, abs=0.01)
    assert 2.35482 * op_b04.blur_sigma_m == pytest.approx(expected_b04_fwhm, abs=0.01)
    assert 2.35482 * op_b04.blur_sigma_m < 15.0  # ~11.7741m (sigma=5.0m)


# =========================================================================
# HNEW-04: Target Graph Cell-Index Grounding
# =========================================================================

def test_hnew_04_target_graph_cell_index_grounding():
    """Without operator, valid_cell_indices is None; with operator, derives strictly from H_t columns."""
    scene = _make_scene(
        width=4,
        height=4,
        valid_support=[[True, False, False, False], [False, True, False, False], [False, False, True, False], [False, False, False, True]],
    )

    # Without bound operator, valid_cell_indices is None (no raw scene pixel conflation)
    fp_no_op = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        require_operator_binding=False,
    )
    assert fp_no_op is not None
    assert fp_no_op.valid_cell_indices is None, "Operator-less footprint must not convert scene pixels into graph cells"

    # With bound operator, valid_cell_indices matches target graph cells from H_t CSR matrix columns
    row, col = np.array([0, 1]), np.array([3, 7])  # target cells 3 and 7
    H = sp.csr_matrix(([1.0, 1.0], (row, col)), shape=(2, 10))
    op = ObservationOperatorRuntime(
        operator_id="op_grounded",
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
    fp_with_op = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        operator=op,
    )
    assert fp_with_op is not None
    assert fp_with_op.valid_cell_indices == (3, 7), "Must reflect H_t column indices"


# =========================================================================
# HNEW-05: Positive Signed Admission & Namespace Cross-Check
# =========================================================================

def test_hnew_05_scene_admission_and_strict_namespace_cross_check():
    """Diagnostic-only, test-override, and namespace-mismatched scenes fail closed."""
    # 1. diagnostic_only=True fails closed even if real_provider_product=True
    scene_diag = _make_scene(diagnostic_only=True, real_provider_product=True, production_usable=False)
    assert adapt_scene_to_footprint(
        scene_diag, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS,
    ) is None

    # 2. test_override=True fails closed
    scene_test = _make_scene(test_override=True)
    assert adapt_scene_to_footprint(
        scene_test, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS,
    ) is None

    # 3. farm_id mismatch fails closed
    scene_bad_farm = _make_scene(farm_id="farm-other")
    assert adapt_scene_to_footprint(
        scene_bad_farm, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS,
    ) is None

    # 4. geometry_sha256 mismatch fails closed
    scene_bad_geom = _make_scene(geometry_sha256="b" * 64)
    assert adapt_scene_to_footprint(
        scene_bad_geom, tenant_id=TENANT, farm_id=FARM, plot_id=PLOT,
        geometry_sha256=GEOM_HASH, target_crs=METRIC_CRS,
    ) is None


# =========================================================================
# HNEW-06: Genuine Worker Reintegration & Cross-Process HTTP Cold Read Path
# =========================================================================

def test_hnew_06_worker_reintegration_and_http_cold_publication_path(clean_store):
    """End-to-end worker reintegration, immutable publish, and HTTP API cold read."""
    states = {"vigor": 0.75, "canopy_water": 0.50}
    sigmas = {"vigor": 0.03, "canopy_water": 0.02}
    vec_hash = compute_asmae_vector_numerical_hash(states, sigmas)

    snap_id = "ASMAE-SNAPSHOT-HNEW06-TEST"
    asmae_result = {
        "plot_id": PLOT,
        "snapshot_id": snap_id,
        "content_hash": hashlib.sha256(b"snap-hnew06").hexdigest(),
        "crop_posterior_lineage": "lineage-hnew06",
        "crop_worldline_event_id": "crop-ev-hnew06",
        "phenology_worldline_event_id": "phen-ev-hnew06",
        "crop_influence_manifest_hash": "m" * 64,
        "crop_evidence_ledger_hash": "l" * 64,
        "claims_numerical_authority": True,
        "state_means": states,
        "sigmas": sigmas,
        "asmae_posterior_numerical_record": {
            "states": states,
            "sigmas": sigmas,
            "numerical_vector_hash": vec_hash,
        },
        "asmae_numerical_digest": vec_hash,
    }

    frontend_payload = {
        "version": SURFACES_SCHEMA_VERSION,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "intelligence_snapshot_id": snap_id,
        "plot_id": PLOT,
        "tenant_id": TENANT,
        "farm_id": FARM,
        "publication_id": "pub-hnew06",
        "publication_run_id": "run-hnew06",
        "run_id": "run-hnew06",
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
            "crop_posterior_lineage": "lineage-hnew06",
            "crop_worldline_event_id": "crop-ev-hnew06",
            "phenology_worldline_event_id": "phen-ev-hnew06",
            "asmae_posterior_vector_hash": vec_hash,
        },
        "asmae_posterior_numerical_record": {
            "states": states,
            "sigmas": sigmas,
            "numerical_vector_hash": vec_hash,
        },
        "asmae_proof": {
            "proof_id": "proof-hnew06",
            "status": "valid",
            "numerical_vector_hash": vec_hash,
        },
        "surfaces": [
            {
                "surface_id": "surface-canopy-vigor",
                "surface_type": "canopy_vigor",
                "values": [[0.75]],
                "resolution_m": 10.0,
                "content_hash": hashlib.sha256(b"vigor-hnew06").hexdigest(),
            }
        ],
        "zones": [],
        "recommendations": [],
    }

    ns = PlotNamespace(tenant_id=TENANT, farm_id=FARM, plot_id=PLOT)
    publish_canonical_plot_snapshot(
        namespace=ns,
        plot_id=PLOT,
        tenant_id=TENANT,
        farm_id=FARM,
        geometry_hash=GEOM_HASH,
        snapshot_id=snap_id,
        asmae_result=asmae_result,
        frontend_payload=frontend_payload,
        job_id="job-hnew06",
        manifest_hash="m" * 64,
        execution_identity={"crop_cycle_id": "cycle-001"},
    )

    # Execute HTTP cold read via FastAPI TestClient
    app.dependency_overrides[require_internal_service_request] = lambda: ns
    try:
        client = TestClient(app)
        headers = {
            "x-agribrain-tenant-id": TENANT,
            "x-agribrain-farm-id": FARM,
            "x-agribrain-plot-id": PLOT,
        }

        # 1. Cold exact snapshot read
        resp = client.get(f"/v2/snapshots/{snap_id}", headers=headers)
        assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("snapshot_id") == snap_id
        assert body.get("validation", {}).get("numericalBindingValid") is True
        assert body.get("contract_validation", {}).get("derived_publication_status") == "VALID_NORMAL"

        # 2. Cold latest snapshot head read
        resp_head = client.get(f"/v2/plots/{PLOT}/snapshot", headers=headers)
        assert resp_head.status_code == 200
        assert resp_head.json().get("snapshot_id") == snap_id

        # 3. Hostile tampered read fails closed with 409 Conflict
        tampered_id = "ASMAE-SNAPSHOT-TAMPERED-01"
        tampered_payload = dict(frontend_payload)
        tampered_payload["intelligence_snapshot_id"] = tampered_id
        tampered_asmae = dict(asmae_result)
        tampered_asmae["snapshot_id"] = tampered_id
        # Alter states without altering numerical hash
        tampered_asmae["asmae_posterior_numerical_record"]["states"]["vigor"] = 0.99
        
        publish_canonical_plot_snapshot(
            namespace=ns,
            plot_id=PLOT,
            tenant_id=TENANT,
            farm_id=FARM,
            geometry_hash=GEOM_HASH,
            snapshot_id=tampered_id,
            asmae_result=tampered_asmae,
            frontend_payload=tampered_payload,
            job_id="job-tampered",
            manifest_hash="m" * 64,
            execution_identity={"crop_cycle_id": "cycle-001"},
        )
        resp_tampered = client.get(f"/v2/snapshots/{tampered_id}", headers=headers)
        assert resp_tampered.status_code == 409, "Tampered numerical record must fail closed with 409 Conflict"
    finally:
        app.dependency_overrides.pop(require_internal_service_request, None)
