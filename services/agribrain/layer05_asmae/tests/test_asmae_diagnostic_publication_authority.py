"""End-to-end regression suite for Advisory Pilot Diagnostic Publication Authority.

Verifies:
1. Legitimate diagnostic ASMAE results without posterior uncertainty vectors
   are admitted and published with publication_authority="DIAGNOSTIC_ONLY".
2. Unified evaluate_snapshot_admission predicate is shared identically across
   latest and exact endpoints.
3. Diagnostic results pass worker reintegration and commit worldline event
   with authority="DIAGNOSTIC_NO_STATE_UPDATE".
4. Latest and exact API endpoints serve diagnostic snapshots (200 OK) across cold restarts.
5. Negative controls: Certified numerical results missing uncertainty vectors or
   containing non-finite/tampered numbers are quarantined and fail closed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer05_asmae import plot_snapshot_store, snapshot_store, reintegration
from services.agribrain.layer10_sire.surface_contract import (
    RENDER_AUTHORIZATION_VERSION,
    SURFACES_SCHEMA_VERSION,
)
from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash
from services.agribrain.app.main import (
    app,
    require_internal_service_request,
    _SNAPSHOT_RESPONSE_CACHE,
    _SNAPSHOT_RESPONSE_CACHE_LOCK,
)


def _base_diagnostic_asmae_result(plot_id: str = "plot-diag-1"):
    return {
        "plot_id": plot_id,
        "content_hash": "content-hash-diag-1",
        "crop_posterior_lineage": "crop-lineage-diag-1",
        "crop_worldline_event_id": "crop-event-diag-1",
        "phenology_worldline_event_id": "phenology-event-diag-1",
        "crop_influence_manifest_hash": "manifest-hash-diag-1",
        "crop_evidence_ledger_hash": "ledger-hash-diag-1",
        "plot_state_artifact": {
            "as_of": "2026-08-21T00:00:00+00:00",
            "authority_level": "DIAGNOSTIC_NO_STATE_UPDATE",
        },
        "claims_numerical_authority": False,
        "publication_authority": "DIAGNOSTIC_ONLY",
        "raster_maps": {},
    }


def _base_diagnostic_frontend_payload(snapshot_id: str, plot_id: str = "plot-diag-1"):
    return {
        "version": SURFACES_SCHEMA_VERSION,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "intelligence_snapshot_id": snapshot_id,
        "plot_id": plot_id,
        "publication_id": f"pub-{snapshot_id}",
        "publication_run_id": f"run-{snapshot_id}",
        "run_id": f"run-{snapshot_id}",
        "pipeline_state": "terminal_layer10_published",
        "publication_status": "VALID_NORMAL",
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "claims_numerical_authority": False,
        "publication_authority": "DIAGNOSTIC_ONLY",
        "asmae_proof": {
            "proof_id": f"proof-{snapshot_id}",
            "status": "valid",
            "publication_authority": "DIAGNOSTIC_ONLY",
        },
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": "crop-lineage-diag-1",
            "crop_worldline_event_id": "crop-event-diag-1",
            "phenology_worldline_event_id": "phenology-event-diag-1",
        },
        "mode_display_state": {"canopy": {"canRenderPixels": True}},
        "source_policy_display_state": {"requested_policy": "satellite"},
        "core_asmae_evidence_state": {"state": "nominal", "content_hash": "dummy_content_hash"},
        "publication_surface_state": {"state": "provider_surface"},
        "surfaces": [{
            "surface_id": "surface-canopy-ndvi",
            "surface_type": "canopy_vigor",
            "values": [[0.52]],
            "resolution_m": 10.0,
            "content_hash": "dummy_hash_diag",
        }],
    }


def _make_certified_numerical_record(val: float = 0.38):
    states = {"root_zone_moisture": float(val), "canopy_vigor": 0.58}
    sigmas = {"root_zone_moisture": 0.012, "canopy_vigor": 0.018}
    vec_hash = compute_asmae_vector_numerical_hash(states, sigmas)
    return {
        "states": states,
        "sigmas": sigmas,
        "numerical_vector_hash": vec_hash,
    }, vec_hash


@pytest.fixture(autouse=True)
def setup_stores(tmp_path, monkeypatch):
    monkeypatch.setattr(plot_snapshot_store, "PLOT_SNAPSHOT_ROOT", tmp_path / "plot_snapshots")
    monkeypatch.setattr(snapshot_store, "SNAPSHOT_DIR", tmp_path / "asmae_snapshots")
    monkeypatch.setattr(snapshot_store, "SNAPSHOT_NODE_DIR", tmp_path / "asmae_snapshots" / "nodes")
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()
    with _SNAPSHOT_RESPONSE_CACHE_LOCK:
        _SNAPSHOT_RESPONSE_CACHE.clear()
    yield
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()
    with _SNAPSHOT_RESPONSE_CACHE_LOCK:
        _SNAPSHOT_RESPONSE_CACHE.clear()


def test_diagnostic_asmae_result_published_and_admitted_without_numerical_record(tmp_path):
    """P1 Resolution: Diagnostic ASMAE result without numerical record is cleanly admitted."""
    plot_id = "parcel-diag-001"
    ns = PlotNamespace(tenant_id="tenant-d1", farm_id="farm-d1", plot_id=plot_id)

    res = _base_diagnostic_asmae_result(plot_id=plot_id)
    ref = snapshot_store.publish_latest_snapshot(res, context_hash="ctx-d1", geometry_hash="geom-d1")
    res["snapshot_ref"] = ref
    snap_id = res["snapshot_id"]

    fe_payload = _base_diagnostic_frontend_payload(snap_id, plot_id=plot_id)

    head = plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash="geom-d1",
        snapshot_id=snap_id,
        asmae_result=res,
        frontend_payload=fe_payload,
        job_id="job-diag-001",
        manifest_hash="manifest-diag-001",
        publication_authority="DIAGNOSTIC_ONLY",
    )

    assert head["publication_authority"] == "DIAGNOSTIC_ONLY"
    assert head["snapshot_id"] == snap_id

    # 1. Verify latest snapshot loader returns diagnostic authority
    latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert latest is not None
    assert latest["publication_authority"] == "DIAGNOSTIC_ONLY"
    assert latest["contract_validation"]["publication_authority"] == "DIAGNOSTIC_ONLY"
    assert latest["validation"]["bindingValid"] is True
    assert latest["validation"]["numericalBindingValid"] is None

    # 2. Verify shared admission predicate admits the diagnostic snapshot
    admission = plot_snapshot_store.evaluate_snapshot_admission(latest, ns)
    assert admission["is_valid"] is True
    assert admission["status"] == "admitted"
    assert admission["quarantined"] is False
    assert admission["publication_authority"] == "DIAGNOSTIC_ONLY"
    assert admission["invalid_integrity_flags"] == []

    # 3. Verify exact snapshot loader returns identical diagnostic authority
    exact = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap_id, namespace=ns)
    assert exact is not None
    assert exact["publication_authority"] == "DIAGNOSTIC_ONLY"
    assert exact["contract_validation"]["publication_authority"] == "DIAGNOSTIC_ONLY"
    assert exact["validation"]["bindingValid"] is True


def test_diagnostic_asmae_result_latest_and_exact_api_retrieval(tmp_path):
    """API admission: Latest and Exact endpoints serve diagnostic results (200 OK) without quarantine."""
    plot_id = "parcel-diag-api"
    ns = PlotNamespace(tenant_id="tenant-api", farm_id="farm-api", plot_id=plot_id)

    res = _base_diagnostic_asmae_result(plot_id=plot_id)
    ref = snapshot_store.publish_latest_snapshot(res, context_hash="ctx-api-1", geometry_hash="geom-api")
    res["snapshot_ref"] = ref
    snap_id = res["snapshot_id"]

    fe_payload = _base_diagnostic_frontend_payload(snap_id, plot_id=plot_id)

    plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash="geom-api",
        snapshot_id=snap_id,
        asmae_result=res,
        frontend_payload=fe_payload,
        job_id="job-api-1",
        manifest_hash="manifest-api-1",
        publication_authority="DIAGNOSTIC_ONLY",
    )

    app.dependency_overrides[require_internal_service_request] = lambda: ns
    try:
        client = TestClient(app)

        # 1. Warm Latest read
        resp_latest = client.get(f"/v2/plots/{plot_id}/snapshot")
        assert resp_latest.status_code == 200
        data_latest = resp_latest.json()
        assert data_latest["available"] is True
        assert data_latest["snapshot_id"] == snap_id
        assert data_latest["publication_authority"] == "DIAGNOSTIC_ONLY"
        assert not data_latest.get("quarantined")

        # 2. Warm Exact read
        resp_exact = client.get(f"/v2/snapshots/{snap_id}")
        assert resp_exact.status_code == 200
        data_exact = resp_exact.json()
        assert data_exact["available"] is True
        assert data_exact["snapshot_id"] == snap_id
        assert data_exact["publication_authority"] == "DIAGNOSTIC_ONLY"

        # 3. Cold restart: clear caches
        with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
            plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()
        with _SNAPSHOT_RESPONSE_CACHE_LOCK:
            _SNAPSHOT_RESPONSE_CACHE.clear()

        # 4. Cold Latest read
        resp_latest_cold = client.get(f"/v2/plots/{plot_id}/snapshot")
        assert resp_latest_cold.status_code == 200
        assert resp_latest_cold.json()["available"] is True
        assert resp_latest_cold.json()["publication_authority"] == "DIAGNOSTIC_ONLY"

        # 5. Cold Exact read
        resp_exact_cold = client.get(f"/v2/snapshots/{snap_id}")
        assert resp_exact_cold.status_code == 200
        assert resp_exact_cold.json()["available"] is True
        assert resp_exact_cold.json()["publication_authority"] == "DIAGNOSTIC_ONLY"
    finally:
        app.dependency_overrides.pop(require_internal_service_request, None)


def test_diagnostic_asmae_worker_reintegration(monkeypatch):
    """Worker reintegration: Diagnostic ASMAE result successfully reuses publication and commits worldline event."""
    from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService

    plot_id = "parcel-reint-001"
    ns = PlotNamespace(tenant_id="tenant-reint", farm_id="farm-reint", plot_id=plot_id)
    job_id = "job-reint-001"
    manifest_hash = "manifest-reint-001"

    res = _base_diagnostic_asmae_result(plot_id=plot_id)
    ref = snapshot_store.publish_latest_snapshot(res, context_hash="ctx-reint", geometry_hash="geom-reint")
    res["snapshot_ref"] = ref
    snap_id = res["snapshot_id"]

    fe_payload = _base_diagnostic_frontend_payload(snap_id, plot_id=plot_id)

    plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash="geom-reint",
        snapshot_id=snap_id,
        asmae_result=res,
        frontend_payload=fe_payload,
        job_id=job_id,
        manifest_hash=manifest_hash,
        publication_authority="DIAGNOSTIC_ONLY",
    )

    committed_events = []
    def mock_commit_event(*args, **kwargs):
        committed_events.append(kwargs)
        return {"event_id": "event-canonical-reint-001"}

    monkeypatch.setattr(CanonicalWorldlineService, "commit_event", mock_commit_event)

    context = {
        "worldline_namespace": "farm-reint",
        "plot_id": plot_id,
        "tenant_id": "tenant-reint",
        "farm_id": "farm-reint",
        "geometry_hash": "geom-reint",
        "plot_namespace": {"tenant_id": ns.tenant_id, "farm_id": ns.farm_id, "plot_id": ns.plot_id},
        "crop_worldline_event_id": "crop-event-diag-1",
        "phenology_worldline_event_id": "phenology-event-diag-1",
        "orchestrator_reintegration": {
            "contract_version": reintegration.REINTEGRATION_CONTRACT_VERSION,
            "input": {
                "plot_id": plot_id,
                "tenant_id": "tenant-reint",
                "farm_id": "farm-reint",
                "plot_namespace": {"tenant_id": ns.tenant_id, "farm_id": ns.farm_id, "plot_id": ns.plot_id},
                "geometry_hash": "geom-reint",
                "date_range": {"start": "2026-08-01", "end": "2026-08-21"},
                "crop_config": {},
                "operational_context": {},
                "policy_snapshot": {},
            },
        },
    }

    reint_resp = reintegration.rebuild_canonical_plot_snapshot(
        asmae_result=res,
        context=context,
        job_id=job_id,
        manifest_hash=manifest_hash,
        parent_event_id="parent-event-001",
    )

    assert reint_resp["status"] == "completed"
    assert reint_resp["publication_reused"] is True
    assert reint_resp["worldline_event_id"] == "event-canonical-reint-001"
    assert len(committed_events) == 1
    assert committed_events[0]["authority"] == "DIAGNOSTIC_NO_STATE_UPDATE"


def test_certified_numerical_snapshot_with_missing_record_rejected():
    """Negative control: CERTIFIED_NUMERICAL authority with missing numerical record fails admission."""
    plot_id = "parcel-neg-missing"
    ns = PlotNamespace(tenant_id="tenant-neg", farm_id="farm-neg", plot_id=plot_id)

    res = _base_diagnostic_asmae_result(plot_id=plot_id)
    res["publication_authority"] = "CERTIFIED_NUMERICAL"
    res["claims_numerical_authority"] = True
    ref = snapshot_store.publish_latest_snapshot(res, context_hash="ctx-neg-1", geometry_hash="geom-neg")
    res["snapshot_ref"] = ref
    snap_id = res["snapshot_id"]

    fe_payload = _base_diagnostic_frontend_payload(snap_id, plot_id=plot_id)
    fe_payload["publication_authority"] = "CERTIFIED_NUMERICAL"
    fe_payload["claims_numerical_authority"] = True

    head = plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash="geom-neg",
        snapshot_id=snap_id,
        asmae_result=res,
        frontend_payload=fe_payload,
        job_id="job-neg-1",
        manifest_hash="manifest-neg-1",
        publication_authority="CERTIFIED_NUMERICAL",
    )

    latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert latest is not None

    admission = plot_snapshot_store.evaluate_snapshot_admission(latest, ns)
    assert admission["is_valid"] is False
    assert admission["status"] == "quarantined"
    assert "numericalBindingValid" in admission["invalid_integrity_flags"]

    app.dependency_overrides[require_internal_service_request] = lambda: ns
    try:
        client = TestClient(app)
        resp_latest = client.get(f"/v2/plots/{plot_id}/snapshot")
        assert resp_latest.status_code == 200
        data = resp_latest.json()
        assert data["available"] is False
        assert data["status"] == "quarantined"
        assert "numericalBindingValid" in data["invalidIntegrityFlags"]

        resp_exact = client.get(f"/v2/snapshots/{snap_id}")
        assert resp_exact.status_code == 409
    finally:
        app.dependency_overrides.pop(require_internal_service_request, None)


def test_certified_numerical_snapshot_with_non_finite_states_rejected():
    """Negative control: CERTIFIED_NUMERICAL authority with negative uncertainty sigma fails admission."""
    plot_id = "parcel-neg-nan"
    ns = PlotNamespace(tenant_id="tenant-neg2", farm_id="farm-neg2", plot_id=plot_id)

    num_rec = {
        "states": {"root_zone_moisture": 0.38, "canopy_vigor": 0.5},
        "sigmas": {"root_zone_moisture": -0.05, "canopy_vigor": 0.02},  # Negative sigma
        "numerical_vector_hash": "dummy_invalid_hash",
    }

    res = _base_diagnostic_asmae_result(plot_id=plot_id)
    res["publication_authority"] = "CERTIFIED_NUMERICAL"
    res["claims_numerical_authority"] = True
    res["asmae_posterior_numerical_record"] = num_rec
    res["asmae_numerical_digest"] = "dummy_invalid_hash"
    ref = snapshot_store.publish_latest_snapshot(res, context_hash="ctx-neg-2", geometry_hash="geom-neg2")
    res["snapshot_ref"] = ref
    snap_id = res["snapshot_id"]

    fe_payload = _base_diagnostic_frontend_payload(snap_id, plot_id=plot_id)
    fe_payload["publication_authority"] = "CERTIFIED_NUMERICAL"
    fe_payload["claims_numerical_authority"] = True
    fe_payload["asmae_posterior_numerical_record"] = num_rec

    plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash="geom-neg2",
        snapshot_id=snap_id,
        asmae_result=res,
        frontend_payload=fe_payload,
        job_id="job-neg-2",
        manifest_hash="manifest-neg-2",
        publication_authority="CERTIFIED_NUMERICAL",
    )

    latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert latest is not None

    admission = plot_snapshot_store.evaluate_snapshot_admission(latest, ns)
    assert admission["is_valid"] is False
    assert admission["status"] == "quarantined"
    assert "numericalBindingValid" in admission["invalid_integrity_flags"]


def test_contained_proposal_authority_admission():
    """CONTAINED_PROPOSAL authority admits simulation proposals without state mutation."""
    plot_id = "parcel-prop-001"
    ns = PlotNamespace(tenant_id="tenant-prop", farm_id="farm-prop", plot_id=plot_id)

    res = _base_diagnostic_asmae_result(plot_id=plot_id)
    res["publication_authority"] = "CONTAINED_PROPOSAL"
    ref = snapshot_store.publish_latest_snapshot(res, context_hash="ctx-prop", geometry_hash="geom-prop")
    res["snapshot_ref"] = ref
    snap_id = res["snapshot_id"]

    fe_payload = _base_diagnostic_frontend_payload(snap_id, plot_id=plot_id)
    fe_payload["publication_authority"] = "CONTAINED_PROPOSAL"

    head = plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash="geom-prop",
        snapshot_id=snap_id,
        asmae_result=res,
        frontend_payload=fe_payload,
        job_id="job-prop-1",
        manifest_hash="manifest-prop-1",
        publication_authority="CONTAINED_PROPOSAL",
    )

    assert head["publication_authority"] == "CONTAINED_PROPOSAL"

    latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert latest is not None
    assert latest["publication_authority"] == "CONTAINED_PROPOSAL"

    admission = plot_snapshot_store.evaluate_snapshot_admission(latest, ns)
    assert admission["is_valid"] is True
    assert admission["status"] == "admitted"
    assert admission["publication_authority"] == "CONTAINED_PROPOSAL"


def test_negative_control_tampered_numerical_hash_rejected():
    """Negative control: CERTIFIED_NUMERICAL authority with tampered numerical hash fails admission."""
    plot_id = "parcel-neg-tamper"
    ns = PlotNamespace(tenant_id="tenant-tamper", farm_id="farm-tamper", plot_id=plot_id)

    # Valid states and sigmas, but tampered hash
    num_rec = {
        "states": {"root_zone_moisture": 0.38, "canopy_vigor": 0.5},
        "sigmas": {"root_zone_moisture": 0.01, "canopy_vigor": 0.02},
        "numerical_vector_hash": "deadbeef" * 8,  # Does not match recomputed hash
    }

    res = _base_diagnostic_asmae_result(plot_id=plot_id)
    res["publication_authority"] = "CERTIFIED_NUMERICAL"
    res["claims_numerical_authority"] = True
    res["asmae_posterior_numerical_record"] = num_rec
    res["asmae_numerical_digest"] = "deadbeef" * 8
    ref = snapshot_store.publish_latest_snapshot(res, context_hash="ctx-tamper", geometry_hash="geom-tamper")
    res["snapshot_ref"] = ref
    snap_id = res["snapshot_id"]

    fe_payload = _base_diagnostic_frontend_payload(snap_id, plot_id=plot_id)
    fe_payload["publication_authority"] = "CERTIFIED_NUMERICAL"
    fe_payload["claims_numerical_authority"] = True
    fe_payload["asmae_posterior_numerical_record"] = num_rec

    plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash="geom-tamper",
        snapshot_id=snap_id,
        asmae_result=res,
        frontend_payload=fe_payload,
        job_id="job-tamper-1",
        manifest_hash="manifest-tamper-1",
        publication_authority="CERTIFIED_NUMERICAL",
    )

    latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert latest is not None

    admission = plot_snapshot_store.evaluate_snapshot_admission(latest, ns)
    assert admission["is_valid"] is False
    assert admission["status"] == "quarantined"
    assert "numericalBindingValid" in admission["invalid_integrity_flags"]
