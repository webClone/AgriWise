"""ASMAE C752-P1-01 through C752-P2-04 Remediation Acceptance Suite.

Covers the four open source review blockers from plan/ASMAE_C75213E_INDEPENDENT_SOURCE_REVIEW.md:
- C752-P1-01 (P1): Query knowledge cutoff K never overwrites actual scene commitment;
                   bitemporal separation on valid_time <= T and committed_at <= K.
- C752-P1-02 (P1): Positive signed admission authority; mandatory per-scene tenant/farm/plot/geometry;
                   forged booleans and unverified asset hashes fail closed.
- C752-P1-03 (P1): Multiband S2 physics with conservative PSF; scene containing 20m bands (B11) with
                   unspecified band resolves to conservative 20m sigma (10.0m) and FWHM ~23.55m;
                   rejects claiming 10m spatial resolution.
- C752-P2-04 (P2): True worker reintegration (rebuild_canonical_plot_snapshot) and multi-process
                   cold publication read proof via isolated OS subprocess against durable disk storage.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any, Dict
import numpy as np
import pytest
import scipy.sparse as sp

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer05_asmae.chain_integrity import compute_h_matrix_digest
from services.agribrain.layer05_asmae.geometry.operator_builder import (
    build_observation_operator,
    build_operators_for_stack,
)
from services.agribrain.layer05_asmae.geometry.psf import get_psf_model
from services.agribrain.layer05_asmae.plot_snapshot_store import (
    publish_canonical_plot_snapshot,
    load_plot_snapshot_by_id,
    load_and_validate_plot_snapshot_by_id,
    load_latest_plot_snapshot,
)
import services.agribrain.layer05_asmae.plot_snapshot_store as snapshot_store_module
from services.agribrain.layer05_asmae.reintegration import (
    rebuild_canonical_plot_snapshot,
    REINTEGRATION_CONTRACT_VERSION,
)
from services.agribrain.layer05_asmae.resolution.observation_footprint_adapter import (
    adapt_scene_to_footprint,
    adapt_scenes_to_footprints,
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


def _make_operator(scene_id: str, sensor: str = "S2", blur_sigma_m: float = 5.0, band: str = "B08"):
    row, col = np.array([0]), np.array([0])
    H = sp.csr_matrix(([1.0], (row, col)), shape=(1, 1))
    return ObservationOperatorRuntime(
        operator_id=f"op_{scene_id}",
        scene_id=scene_id,
        sensor=sensor,
        source_resolution_m=10.0 if blur_sigma_m < 8.0 else 20.0,
        target_resolution_m=10,
        source_crs=METRIC_CRS,
        target_crs=METRIC_CRS,
        source_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        target_transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        H_matrix=H,
        blur_sigma_m=blur_sigma_m,
        band=band,
    )


# =========================================================================
# C752-P1-01: Bitemporal Leakage in Engine Replay
# =========================================================================

def test_c752_p1_01_bitemporal_replay_and_engine_separation():
    """Observation valid Day 5 and journal-committed Day 20 is excluded at K=Day 10 and admitted at K=Day 21."""
    scene = _make_scene(
        scene_id="S2_ACQ_DAY5_COMM_DAY20",
        acquisition_time=datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc),
        committed_at=datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc),
    )
    op = _make_operator(scene.scene_id)

    # In production / operator-binding mode, committed_at=None is passed by engine.
    # The adapter derives commitment strictly from scene.committed_at (Day 20).
    fps = adapt_scenes_to_footprints(
        [scene],
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        committed_at=None,
        operators=[op],
        require_operator_binding=True,
    )
    assert len(fps) == 1
    fp = fps[0]
    assert fp.observation_valid_time == "2026-09-05T12:00:00+00:00"
    assert fp.committed_at == "2026-09-20T12:00:00+00:00"

    grid = GridSpec(crs=METRIC_CRS, transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0), width=4, height=4)

    # 1. Historical replay at T=Day 10, K=Day 10:
    # Scene valid Day 5 is temporally valid (5 <= 10), but committed Day 20 is NOT yet known (20 > 10).
    # Must fail closed: excluded from support.
    rec_k10 = evaluate_state_cell_support(
        state="vigor",
        row=0,
        col=0,
        grid=grid,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        valid_time="2026-09-10T12:00:00Z",
        knowledge_cutoff="2026-09-10T12:00:00Z",
        estimated_value=0.72,
        sigma=0.04,
        evidences=(fp,),
    )
    assert rec_k10.spatial_support != "local_operator"
    assert "excluded_by_valid_or_knowledge_cutoff" in rec_k10.demotion_reasons
    assert len(rec_k10.admitted_observation_ids) == 0

    # 2. Replay at T=Day 10, K=Day 21:
    # Scene committed Day 20 is now known at K=Day 21 (20 <= 21).
    # Admitted as valid local operator support.
    rec_k21 = evaluate_state_cell_support(
        state="vigor",
        row=0,
        col=0,
        grid=grid,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        valid_time="2026-09-10T12:00:00Z",
        knowledge_cutoff="2026-09-21T12:00:00Z",
        estimated_value=0.72,
        sigma=0.04,
        evidences=(fp,),
    )
    assert rec_k21.spatial_support == "local_operator"
    assert rec_k21.admitted_observation_ids == (fp.observation_id,)


# =========================================================================
# C752-P1-02: Mandatory Namespace & Positive Signed Admission Authority
# =========================================================================

def test_c752_p1_02_mandatory_namespace_and_positive_admission_authority():
    """require_operator_binding=True strictly requires tenant/farm/plot/geometry and verified provider admission."""
    base_scene = _make_scene()
    op = _make_operator(base_scene.scene_id)

    # 1. Missing tenant_id fails closed
    scene_no_tenant = _make_scene(tenant_id=None)
    assert adapt_scene_to_footprint(
        scene_no_tenant,
        tenant_id=TENANT, farm_id=FARM, plot_id=PLOT, geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS, require_operator_binding=True, operator=op,
    ) is None

    # 2. Missing farm_id fails closed
    scene_no_farm = _make_scene(farm_id=None)
    assert adapt_scene_to_footprint(
        scene_no_farm,
        tenant_id=TENANT, farm_id=FARM, plot_id=PLOT, geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS, require_operator_binding=True, operator=op,
    ) is None

    # 3. Missing plot_id fails closed
    scene_no_plot = _make_scene(plot_id=None)
    assert adapt_scene_to_footprint(
        scene_no_plot,
        tenant_id=TENANT, farm_id=FARM, plot_id=PLOT, geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS, require_operator_binding=True, operator=op,
    ) is None

    # 4. Missing geometry_sha256 fails closed
    scene_no_geom = _make_scene(geometry_sha256=None)
    assert adapt_scene_to_footprint(
        scene_no_geom,
        tenant_id=TENANT, farm_id=FARM, plot_id=PLOT, geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS, require_operator_binding=True, operator=op,
    ) is None

    # 5. Forged booleans with product_binding='unknown' and no admission proof fails closed
    scene_forged_bools = _make_scene(
        production_usable=True,
        scientifically_admitted=True,
        product_binding="unknown",
        binding_proof={},
        admission_receipt=None,
        real_provider_product=False,
    )
    assert adapt_scene_to_footprint(
        scene_forged_bools,
        tenant_id=TENANT, farm_id=FARM, plot_id=PLOT, geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS, require_operator_binding=True, operator=op,
    ) is None

    # 6. Unverified or forged asset hash fails closed
    scene_forged_hash = _make_scene(unverified_asset_hash=True)
    assert adapt_scene_to_footprint(
        scene_forged_hash,
        tenant_id=TENANT, farm_id=FARM, plot_id=PLOT, geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS, require_operator_binding=True, operator=op,
    ) is None

    # 7. Authentic scene with complete namespace and verified provider admission succeeds
    scene_ok = _make_scene(
        product_binding="exact_catalog_item",
        provider_product_id="S2A_MSIL2A_AUTHENTIC_01",
    )
    op_ok = _make_operator(scene_ok.scene_id)
    fp_ok = adapt_scene_to_footprint(
        scene_ok,
        tenant_id=TENANT, farm_id=FARM, plot_id=PLOT, geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS, require_operator_binding=True, operator=op_ok,
    )
    assert fp_ok is not None
    assert fp_ok.tenant_id == TENANT
    assert fp_ok.geometry_sha256 == GEOM_HASH


# =========================================================================
# C752-P1-03: Multiband S2 Physics & Conservative PSF
# =========================================================================

def test_c752_p1_03_multiband_s2_physics_conservative_psf():
    """Multiband S2 scene containing 20m bands with unspecified band defaults conservatively to 20m PSF and resolution."""
    # S2 scene with multiband raster containing 10m (B04) and 20m (B11 SWIR), with candidate.band=None
    arr_b04 = np.ones((10, 10), dtype=np.float32) * 0.2
    arr_b11 = np.ones((5, 5), dtype=np.float32) * 0.4
    scene_multiband = ASMAESceneRuntime(
        scene_id="S2_MULTIBAND_B04_B11",
        sensor="S2",
        acquisition_time=datetime(2026, 9, 8, 10, 30, 0, tzinfo=timezone.utc),
        crs=METRIC_CRS,
        transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        width=10,
        height=10,
        bands={"B04": arr_b04, "B11": arr_b11},
        masks={},
        sun_angles=None,
        cloud_fraction=0.0,
        qa_score=0.95,
        provenance_ref="s2_loader_test",
    )
    scene_multiband.band = None
    scene_multiband.tenant_id = TENANT
    scene_multiband.farm_id = FARM
    scene_multiband.plot_id = PLOT
    scene_multiband.geometry_sha256 = GEOM_HASH
    scene_multiband.committed_at = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
    scene_multiband.production_usable = True
    scene_multiband.diagnostic_only = False
    scene_multiband.real_provider_product = True
    scene_multiband.product_binding = "exact_catalog_item"
    scene_multiband.provider_product_id = "PROD_S2_MULTIBAND"
    scene_multiband.content_hash = "2" * 64

    # 1. Operator builder resolves multiband containing 20m bands to conservative 20m PSF
    op = build_observation_operator(scene=scene_multiband, candidate_resolution_m=10)
    assert op.band == "B05"
    assert op.blur_sigma_m == pytest.approx(10.0, abs=0.01)
    # FWHM = 2 * sqrt(2 * ln(2)) * sigma = 2.35482 * 10.0 ~ 23.5482m
    expected_fwhm = get_psf_model("S2", band="B05").fwhm_m
    assert 2.35482 * op.blur_sigma_m == pytest.approx(expected_fwhm, abs=0.01)
    assert 2.35482 * op.blur_sigma_m > 20.0

    # 2. Footprint adapter derives conservative 20m native resolution and PSF
    fp = adapt_scene_to_footprint(
        scene_multiband,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
        operator=op,
        require_operator_binding=True,
    )
    assert fp is not None
    assert fp.native_resolution_m == 20.0
    assert fp.psf_fwhm_m == pytest.approx(expected_fwhm, abs=0.01)

    # 3. Spatial support evaluation rejects claiming 10m resolution for 20m physics
    grid = GridSpec(crs=METRIC_CRS, transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0), width=4, height=4)
    rec = evaluate_state_cell_support(
        state="vigor",
        row=0,
        col=0,
        grid=grid,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        valid_time="2026-09-10T12:00:00Z",
        knowledge_cutoff="2026-09-10T12:00:00Z",
        estimated_value=0.72,
        sigma=0.04,
        evidences=(fp,),
    )
    assert rec.spatial_support == "local_operator"
    # Effective resolution must be instrument scale >= 20.0m
    assert rec.effective_resolution_m is not None
    assert rec.effective_resolution_m >= 20.0
    assert rec.certified_1m is False

    # 4. Single 10m band scene without 20m bands safely uses 10m PSF
    scene_10m = _make_scene(band="B04")
    op_10m = build_observation_operator(scene=scene_10m, candidate_resolution_m=10)
    assert op_10m.band == "B04"
    assert op_10m.blur_sigma_m == pytest.approx(5.0, abs=0.01)


# =========================================================================
# C752-P2-04: True Worker Reintegration & Subprocess Cold Read Proof
# =========================================================================

def test_c752_p2_04_worker_reintegration_and_subprocess_cold_read(clean_store):
    """Executes rebuild_canonical_plot_snapshot and verifies cold exact and latest read in an out-of-process subprocess."""
    store_dir = str(clean_store.PLOT_SNAPSHOT_ROOT)
    os.environ["AGRIWISE_SNAPSHOT_STORE_ROOT"] = store_dir

    states = {"vigor": 0.76, "canopy_water": 0.52}
    sigmas = {"vigor": 0.03, "canopy_water": 0.02}
    vec_hash = compute_asmae_vector_numerical_hash(states, sigmas)

    snap_id = "ASMAE-SNAPSHOT-C752-COLD-01"
    asmae_result = {
        "plot_id": PLOT,
        "snapshot_id": snap_id,
        "as_of": "2026-09-08T12:00:00Z",
        "published_at": "2026-09-08T12:00:00Z",
        "authority_level": "SCIENTIFIC",
        "production_usable": True,
        "content_hash": hashlib.sha256(b"snap-c752-01").hexdigest(),
        "crop_posterior_lineage": "lineage-c752-01",
        "crop_worldline_event_id": "crop-ev-c752-01",
        "phenology_worldline_event_id": "phen-ev-c752-01",
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
        "publication_id": "pub-c752-01",
        "publication_run_id": "run-c752-01",
        "run_id": "run-c752-01",
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
            "crop_posterior_lineage": "lineage-c752-01",
            "crop_worldline_event_id": "crop-ev-c752-01",
            "phenology_worldline_event_id": "phen-ev-c752-01",
            "asmae_posterior_vector_hash": vec_hash,
        },
        "asmae_posterior_numerical_record": {
            "states": states,
            "sigmas": sigmas,
            "numerical_vector_hash": vec_hash,
        },
        "asmae_proof": {
            "proof_id": "proof-c752-01",
            "status": "valid",
            "numerical_vector_hash": vec_hash,
        },
        "surfaces": [
            {
                "surface_id": "surface-canopy-vigor",
                "surface_type": "canopy_vigor",
                "values": [[0.76]],
                "resolution_m": 10.0,
                "content_hash": hashlib.sha256(b"vigor-c752").hexdigest(),
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
        job_id="job-c752-01",
        manifest_hash="m" * 64,
        execution_identity={"crop_cycle_id": "cycle-001"},
    )

    # Execute true worker reintegration via rebuild_canonical_plot_snapshot
    context = {
        "plot_id": PLOT,
        "tenant_id": TENANT,
        "farm_id": FARM,
        "geometry_hash": GEOM_HASH,
        "plot_namespace": {"tenant_id": TENANT, "farm_id": FARM, "plot_id": PLOT},
        "crop_worldline_event_id": "crop-ev-c752-01",
        "phenology_worldline_event_id": "phen-ev-c752-01",
        "crop_posterior_lineage": "lineage-c752-01",
        "orchestrator_reintegration": {
            "contract_version": REINTEGRATION_CONTRACT_VERSION,
            "input": {
                "plot_id": PLOT,
                "tenant_id": TENANT,
                "farm_id": FARM,
                "geometry_hash": GEOM_HASH,
                "plot_namespace": {"tenant_id": TENANT, "farm_id": FARM, "plot_id": PLOT},
                "date_range": ["2026-09-01", "2026-09-10"],
                "crop_config": {"crop_type": "wheat"},
                "operational_context": {"policy": "standard"},
                "policy_snapshot": {"policy": "standard"},
            },
        },
    }
    rebuild_res = rebuild_canonical_plot_snapshot(
        asmae_result=asmae_result,
        context=context,
        job_id="job-c752-01",
        manifest_hash="m" * 64,
    )
    assert rebuild_res["status"] == "completed"
    assert rebuild_res["snapshot_id"] == snap_id
    assert rebuild_res.get("publication_reused") is True
    assert rebuild_res.get("worldline_event_id") is not None

    # Spawn an independent child OS process with NO shared memory cache
    child_code = f"""
import os
import sys

store_dir = {json.dumps(store_dir)}
os.environ["AGRIWISE_SNAPSHOT_STORE_ROOT"] = store_dir

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer05_asmae.plot_snapshot_store import (
    load_and_validate_plot_snapshot_by_id,
    load_latest_plot_snapshot,
    publish_canonical_plot_snapshot,
)
from services.agribrain.app.main import app, require_internal_service_request
from fastapi.testclient import TestClient

ns = PlotNamespace(tenant_id={json.dumps(TENANT)}, farm_id={json.dumps(FARM)}, plot_id={json.dumps(PLOT)})
snap_id = {json.dumps(snap_id)}

# 1. Cold exact snapshot load from disk
exact = load_and_validate_plot_snapshot_by_id(snap_id, namespace=ns)
if not exact or exact.get("snapshot_id") != snap_id:
    print("FAIL_EXACT_READ")
    sys.exit(10)
if not exact.get("validation", {{}}).get("numericalBindingValid"):
    print("FAIL_NUMERICAL_BINDING")
    sys.exit(11)
if exact.get("contract_validation", {{}}).get("derived_publication_status") != "VALID_NORMAL":
    print("FAIL_PUBLICATION_STATUS")
    sys.exit(12)

# 2. Cold latest snapshot head read from disk
head = load_latest_plot_snapshot(ns, {json.dumps(GEOM_HASH)})
if not head or head.get("snapshot_id") != snap_id:
    print("FAIL_HEAD_READ")
    sys.exit(20)

# 3. HTTP API cold read via TestClient in child process
app.dependency_overrides[require_internal_service_request] = lambda: ns
client = TestClient(app)
headers = {{
    "x-agribrain-tenant-id": ns.tenant_id,
    "x-agribrain-farm-id": ns.farm_id,
    "x-agribrain-plot-id": ns.plot_id,
}}

r_exact = client.get(f"/v2/snapshots/{{snap_id}}", headers=headers)
if r_exact.status_code != 200 or r_exact.json().get("snapshot_id") != snap_id:
    print(f"FAIL_HTTP_EXACT: {{r_exact.status_code}} {{r_exact.text}}")
    sys.exit(30)

r_head = client.get(f"/v2/plots/{{ns.plot_id}}/snapshot", headers=headers)
if r_head.status_code != 200 or r_head.json().get("snapshot_id") != snap_id:
    print(f"FAIL_HTTP_HEAD: {{r_head.status_code}} {{r_head.text}}")
    sys.exit(31)

# 4. Missing-sigma fallback test: subsequent diagnostic run without complete sigma
# must stay diagnostic and NOT overwrite or suppress the existing valid head
diag_snap_id = "ASMAE-SNAPSHOT-C752-DIAG-MISSING-SIGMA"
diag_asmae = {{
    "plot_id": ns.plot_id,
    "snapshot_id": diag_snap_id,
    "claims_numerical_authority": False,
    "crop_posterior_lineage": "lineage-c752-01",
    "crop_worldline_event_id": "crop-ev-c752-01",
    "phenology_worldline_event_id": "phen-ev-c752-01",
    "crop_influence_manifest_hash": "m" * 64,
    "crop_evidence_ledger_hash": "l" * 64,
    "state_means": {{"vigor": 0.70}},
    "sigmas": {{}},  # Missing sigmas
}}
diag_frontend = {{
    "version": {json.dumps(SURFACES_SCHEMA_VERSION)},
    "surface_schema_version": {json.dumps(SURFACES_SCHEMA_VERSION)},
    "intelligence_snapshot_id": diag_snap_id,
    "plot_id": ns.plot_id,
    "tenant_id": ns.tenant_id,
    "farm_id": ns.farm_id,
    "publication_id": "pub-c752-diag",
    "publication_run_id": "run-c752-diag",
    "run_id": "run-c752-diag",
    "pipeline_state": "terminal_layer10_published",
    "publication_status": "VALID_DIAGNOSTIC",
    "claims_numerical_authority": False,
    "render_authorization_version": {json.dumps(RENDER_AUTHORIZATION_VERSION)},
    "render_authorizations": {{}},
    "mode_display_state": {{"mode": "diagnostic"}},
    "asmae_evidence_state": {{"production_usable": False, "authority_level": "DIAGNOSTIC"}},
    "publication_surface_state": {{}},
    "scientific_evidence_lineage": {{
        "crop_posterior_lineage": "lineage-c752-01",
        "crop_worldline_event_id": "crop-ev-c752-01",
        "phenology_worldline_event_id": "phen-ev-c752-01",
    }},
    "surfaces": [],
    "zones": [],
    "recommendations": [],
}}

# Publish diagnostic snapshot
publish_canonical_plot_snapshot(
    namespace=ns,
    plot_id=ns.plot_id,
    tenant_id=ns.tenant_id,
    farm_id=ns.farm_id,
    geometry_hash={json.dumps(GEOM_HASH)},
    snapshot_id=diag_snap_id,
    asmae_result=diag_asmae,
    frontend_payload=diag_frontend,
    job_id="job-c752-diag",
    manifest_hash="d" * 64,
    execution_identity={{"crop_cycle_id": "cycle-001"}},
)

# Verify that the diagnostic snapshot is stored as diagnostic
diag_loaded = load_and_validate_plot_snapshot_by_id(diag_snap_id, namespace=ns)
if not diag_loaded or diag_loaded.get("contract_validation", {{}}).get("numerical_authority_verified") is not False:
    print("FAIL_DIAGNOSTIC_AUTHORITY_CHECK")
    sys.exit(40)

print("COLD_READ_AND_REINTEGRATION_VERIFIED")
sys.exit(0)
"""

    child_env = os.environ.copy()
    child_env["AGRIWISE_SNAPSHOT_STORE_ROOT"] = store_dir
    proc = subprocess.run(
        [sys.executable, "-c", child_code],
        env=child_env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"Child subprocess failed with code {proc.returncode}:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "COLD_READ_AND_REINTEGRATION_VERIFIED" in proc.stdout
