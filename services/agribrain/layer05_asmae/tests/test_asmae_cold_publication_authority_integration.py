"""Cold publication & snapshot store authority integration tests.

Verifies:
1. Complete posterior (finite states + sigmas) publishes with verified numerical authority.
2. Missing sigma does NOT fabricate sigma=0: claims_numerical_authority=False, diagnostic only.
3. Tampered numerical vector hash fails closed (numericalBindingValid=False).
4. Immutable node collision with mismatched numerical vector hash is rejected.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import pytest

from services.agribrain.layer05_asmae import plot_snapshot_store
from services.agribrain.layer05_asmae.plot_snapshot_store import (
    PlotNamespace,
    publish_canonical_plot_snapshot,
    load_plot_snapshot_by_id,
    load_and_validate_plot_snapshot_by_id,
)
from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash
from services.agribrain.layer10_sire.surface_contract import RENDER_AUTHORIZATION_VERSION, SURFACES_SCHEMA_VERSION


@pytest.fixture
def clean_store(tmp_path, monkeypatch):
    root = tmp_path / "plot_snapshots"
    monkeypatch.setattr(plot_snapshot_store, "PLOT_SNAPSHOT_ROOT", root)
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()
    return plot_snapshot_store


def _build_payloads(
    snapshot_id: str,
    *,
    states: dict | None = None,
    sigmas: dict | None = None,
    tampered_hash: str | None = None,
    claims_authority: bool = False,
):
    plot_id = "plot-afroun"
    tenant_id = "tenant-001"
    farm_id = "farm-mitidja"
    geometry_hash = "f" * 64
    job_id = f"job-{snapshot_id}"
    manifest_hash = "m" * 64

    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)

    num_rec = None
    vec_hash = None
    if states is not None and sigmas is not None:
        real_hash = compute_asmae_vector_numerical_hash(states, sigmas)
        vec_hash = tampered_hash if tampered_hash is not None else real_hash
        num_rec = {
            "states": states,
            "sigmas": sigmas,
            "numerical_vector_hash": vec_hash,
        }

    asmae_result = {
        "plot_id": plot_id,
        "snapshot_id": snapshot_id,
        "content_hash": hashlib.sha256(f"content-{snapshot_id}".encode()).hexdigest(),
        "crop_posterior_lineage": "lineage-001",
        "crop_worldline_event_id": "crop-ev-1",
        "phenology_worldline_event_id": "phen-ev-1",
        "crop_influence_manifest_hash": manifest_hash,
        "crop_evidence_ledger_hash": "l" * 64,
        "claims_numerical_authority": claims_authority,
        "state_means": states or {},
        "sigmas": sigmas or {},
        "raster_maps": {},
    }
    if num_rec is not None:
        asmae_result["asmae_posterior_numerical_record"] = num_rec
        asmae_result["asmae_numerical_digest"] = vec_hash

    scientific_evidence_lineage = {
        "crop_posterior_lineage": "lineage-001",
        "crop_worldline_event_id": "crop-ev-1",
        "phenology_worldline_event_id": "phen-ev-1",
        "replay_mode": "exact_frozen_worldline_events",
    }
    if vec_hash is not None:
        scientific_evidence_lineage["asmae_posterior_vector_hash"] = vec_hash

    frontend = {
        "version": SURFACES_SCHEMA_VERSION,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "intelligence_snapshot_id": snapshot_id,
        "plot_id": plot_id,
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "publication_id": f"pub-{snapshot_id}",
        "publication_run_id": f"run-{snapshot_id}",
        "run_id": f"run-{snapshot_id}",
        "pipeline_state": "terminal_layer10_published",
        "publication_status": "VALID_NORMAL",
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "mode_display_state": {"mode": "scientific", "canopy": {"canRenderPixels": True}},
        "claims_numerical_authority": claims_authority,
        "scientific_evidence_lineage": scientific_evidence_lineage,
        "surfaces": [
            {
                "surface_id": "surface-canopy-vigor",
                "surface_type": "canopy_vigor",
                "values": [[0.615]],
                "resolution_m": 10.0,
                "content_hash": hashlib.sha256(b"surf-vigor").hexdigest(),
            }
        ],
        "zones": [],
        "recommendations": [],
    }
    if num_rec is not None:
        frontend["asmae_posterior_numerical_record"] = num_rec
        frontend["asmae_proof"] = {
            "proof_id": f"proof-{snapshot_id}",
            "status": "valid",
            "numerical_vector_hash": vec_hash,
        }
    elif claims_authority:
        frontend["asmae_proof"] = {
            "proof_id": f"proof-{snapshot_id}",
            "status": "valid",
        }

    return ns, geometry_hash, job_id, manifest_hash, asmae_result, frontend


def test_complete_posterior_publishes_with_verified_numerical_authority(clean_store):
    states = {"vigor": 0.72, "root_zone_water": 0.28}
    sigmas = {"vigor": 0.05, "root_zone_water": 0.03}
    ns, geom_hash, job_id, manifest_hash, asmae_res, frontend = _build_payloads(
        "ASMAE-SNAPSHOT-VERIFIED-01",
        states=states,
        sigmas=sigmas,
        claims_authority=True,
    )

    head = publish_canonical_plot_snapshot(
        namespace=ns,
        plot_id=ns.plot_id,
        tenant_id=ns.tenant_id,
        farm_id=ns.farm_id,
        geometry_hash=geom_hash,
        snapshot_id="ASMAE-SNAPSHOT-VERIFIED-01",
        asmae_result=asmae_res,
        frontend_payload=frontend,
        job_id=job_id,
        manifest_hash=manifest_hash,
        execution_identity={"crop_cycle_id": "cycle-001"},
    )
    assert head["snapshot_id"] == "ASMAE-SNAPSHOT-VERIFIED-01"

    # Cold read
    with clean_store._SNAPSHOT_CACHE_LOCK:
        clean_store._CANONICAL_SNAPSHOT_CACHE.clear()

    # Cold load via load_latest_plot_snapshot
    latest = clean_store.load_latest_plot_snapshot(ns, geom_hash)
    assert latest is not None
    assert latest["snapshot_id"] == "ASMAE-SNAPSHOT-VERIFIED-01"
    validation = latest.get("validation", {})
    assert validation.get("nodeValid") is True
    assert validation.get("publicationValid") is True
    assert validation.get("receiptValid") is True
    assert validation.get("temporalBindingValid") is True
    assert validation.get("numericalBindingValid") is True
    assert validation.get("nodeAgreementValid") is True
    contract_val = latest.get("contract_validation", {})
    assert contract_val.get("numerical_authority_verified") is True

    # Cold exact node read
    exact = load_plot_snapshot_by_id(snapshot_id="ASMAE-SNAPSHOT-VERIFIED-01", namespace=ns)
    assert exact is not None
    assert exact["snapshot_id"] == "ASMAE-SNAPSHOT-VERIFIED-01"


def test_missing_uncertainty_publishes_as_diagnostic_without_numerical_authority(clean_store):
    ns, geom_hash, job_id, manifest_hash, asmae_res, frontend = _build_payloads(
        "ASMAE-SNAPSHOT-DIAGNOSTIC-02",
        states={"vigor": 0.72},
        sigmas=None,
        claims_authority=False,
    )

    head = publish_canonical_plot_snapshot(
        namespace=ns,
        plot_id=ns.plot_id,
        tenant_id=ns.tenant_id,
        farm_id=ns.farm_id,
        geometry_hash=geom_hash,
        snapshot_id="ASMAE-SNAPSHOT-DIAGNOSTIC-02",
        asmae_result=asmae_res,
        frontend_payload=frontend,
        job_id=job_id,
        manifest_hash=manifest_hash,
        execution_identity={"crop_cycle_id": "cycle-001"},
    )
    assert head["snapshot_id"] == "ASMAE-SNAPSHOT-DIAGNOSTIC-02"

    with clean_store._SNAPSHOT_CACHE_LOCK:
        clean_store._CANONICAL_SNAPSHOT_CACHE.clear()

    exact = load_and_validate_plot_snapshot_by_id("ASMAE-SNAPSHOT-DIAGNOSTIC-02", namespace=ns)
    assert exact is not None
    contract_val = exact.get("contract_validation", {})
    assert contract_val.get("numerical_authority_verified") is False


def test_tampered_numerical_vector_hash_fails_closed(clean_store):
    states = {"vigor": 0.72, "root_zone_water": 0.28}
    sigmas = {"vigor": 0.05, "root_zone_water": 0.03}
    tampered = "0" * 64
    ns, geom_hash, job_id, manifest_hash, asmae_res, frontend = _build_payloads(
        "ASMAE-SNAPSHOT-TAMPERED-03",
        states=states,
        sigmas=sigmas,
        tampered_hash=tampered,
        claims_authority=True,
    )

    head = publish_canonical_plot_snapshot(
        namespace=ns,
        plot_id=ns.plot_id,
        tenant_id=ns.tenant_id,
        farm_id=ns.farm_id,
        geometry_hash=geom_hash,
        snapshot_id="ASMAE-SNAPSHOT-TAMPERED-03",
        asmae_result=asmae_res,
        frontend_payload=frontend,
        job_id=job_id,
        manifest_hash=manifest_hash,
        execution_identity={"crop_cycle_id": "cycle-001"},
    )

    with clean_store._SNAPSHOT_CACHE_LOCK:
        clean_store._CANONICAL_SNAPSHOT_CACHE.clear()

    exact = load_and_validate_plot_snapshot_by_id("ASMAE-SNAPSHOT-TAMPERED-03", namespace=ns)
    assert exact is not None
    validation = exact.get("validation", {})
    assert validation.get("numericalBindingValid") is False
    assert validation.get("contractValid") is False
    contract_val = exact.get("contract_validation", {})
    assert contract_val.get("derived_publication_status") == "INVALID_NUMERICAL_BINDING"
    assert "contradicts" in str(contract_val.get("contract_reason", ""))


def test_immutable_collision_on_numerical_record_mismatch_raises(clean_store):
    states1 = {"vigor": 0.72, "root_zone_water": 0.28}
    sigmas1 = {"vigor": 0.05, "root_zone_water": 0.03}
    ns, geom_hash, job_id, manifest_hash, asmae_res1, frontend1 = _build_payloads(
        "ASMAE-SNAPSHOT-COLLISION-04",
        states=states1,
        sigmas=sigmas1,
        claims_authority=True,
    )

    publish_canonical_plot_snapshot(
        namespace=ns,
        plot_id=ns.plot_id,
        tenant_id=ns.tenant_id,
        farm_id=ns.farm_id,
        geometry_hash=geom_hash,
        snapshot_id="ASMAE-SNAPSHOT-COLLISION-04",
        asmae_result=asmae_res1,
        frontend_payload=frontend1,
        job_id=job_id,
        manifest_hash=manifest_hash,
        execution_identity={"crop_cycle_id": "cycle-001"},
    )

    # Different states/sigmas with identical snapshot_id
    states2 = {"vigor": 0.30, "root_zone_water": 0.10}
    sigmas2 = {"vigor": 0.02, "root_zone_water": 0.01}
    _, _, _, _, asmae_res2, frontend2 = _build_payloads(
        "ASMAE-SNAPSHOT-COLLISION-04",
        states=states2,
        sigmas=sigmas2,
        claims_authority=True,
    )

    with pytest.raises(ValueError, match="numerical record mismatch"):
        publish_canonical_plot_snapshot(
            namespace=ns,
            plot_id=ns.plot_id,
            tenant_id=ns.tenant_id,
            farm_id=ns.farm_id,
            geometry_hash=geom_hash,
            snapshot_id="ASMAE-SNAPSHOT-COLLISION-04",
            asmae_result=asmae_res2,
            frontend_payload=frontend2,
            job_id=job_id,
            manifest_hash=manifest_hash,
            execution_identity={"crop_cycle_id": "cycle-001"},
        )
