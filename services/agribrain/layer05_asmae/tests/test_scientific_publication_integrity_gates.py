from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer05_asmae import plot_snapshot_store
from services.agribrain.layer05_asmae import snapshot_store
from services.agribrain.layer10_sire.runner import validate_spatial_grid_spec
from services.agribrain.layer10_sire.surface_contract import (
    RENDER_AUTHORIZATION_VERSION,
    SURFACES_SCHEMA_VERSION,
)
from services.agribrain.layer1_fusion import temporal_alignment as ta
from services.agribrain.layer1_fusion.schemas import EvidenceItem
from services.agribrain.layer1_fusion.tests.trust_fixtures import create_signed_sensor_receipt
from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash


def _make_numerical_record(val: float = 0.365):
    states = {"root_zone_moisture": float(val), "canopy_vigor": 0.55}
    sigmas = {"root_zone_moisture": 0.015, "canopy_vigor": 0.02}
    vec_hash = compute_asmae_vector_numerical_hash(states, sigmas)
    return {
        "states": states,
        "sigmas": sigmas,
        "numerical_vector_hash": vec_hash,
    }, vec_hash


def _base_asmae_result(plot_id: str = "plot-a", num_val: float = 0.365):
    num_rec, vec_hash = _make_numerical_record(num_val)
    return {
        "plot_id": plot_id,
        "content_hash": "content-hash-nominal",
        "crop_posterior_lineage": "crop-lineage-nominal",
        "crop_worldline_event_id": "crop-event-nominal",
        "phenology_worldline_event_id": "phenology-event-nominal",
        "crop_influence_manifest_hash": "manifest-hash-nominal",
        "crop_evidence_ledger_hash": "ledger-hash-nominal",
        "plot_state_artifact": {"as_of": "2026-08-21T00:00:00+00:00"},
        "asmae_posterior_numerical_record": num_rec,
        "asmae_numerical_digest": vec_hash,
        "claims_numerical_authority": True,
        "raster_maps": {},
    }


def _base_frontend_payload(snapshot_id: str, num_val: float = 0.365):
    num_rec, vec_hash = _make_numerical_record(num_val)
    return {
        "version": SURFACES_SCHEMA_VERSION,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "intelligence_snapshot_id": snapshot_id,
        "plot_id": "plot-a",
        "publication_id": f"pub-{snapshot_id}",
        "publication_run_id": f"run-{snapshot_id}",
        "run_id": f"run-{snapshot_id}",
        "pipeline_state": "terminal_layer10_published",
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "asmae_proof": {"proof_id": f"proof-{snapshot_id}", "status": "valid", "numerical_vector_hash": vec_hash},
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": "crop-lineage-nominal",
            "crop_worldline_event_id": "crop-event-nominal",
            "phenology_worldline_event_id": "phenology-event-nominal",
            "asmae_posterior_vector_hash": vec_hash,
        },
        "mode_display_state": {"canopy": {"canRenderPixels": True}},
        "source_policy_display_state": {"requested_policy": "satellite"},
        "core_asmae_evidence_state": {"state": "nominal", "content_hash": "dummy_content_hash"},
        "publication_surface_state": {"state": "provider_surface"},
        "surfaces": [{
            "surface_id": "surface-canopy-ndvi",
            "surface_type": "canopy_vigor",
            "values": [[0.55]],
            "resolution_m": 10.0,
            "content_hash": "dummy_hash",
        }],
        "claims_numerical_authority": True,
        "asmae_posterior_numerical_record": num_rec,
    }


@pytest.fixture(autouse=True)
def setup_stores(tmp_path, monkeypatch):
    monkeypatch.setattr(plot_snapshot_store, "PLOT_SNAPSHOT_ROOT", tmp_path / "plot_snapshots")
    monkeypatch.setattr(snapshot_store, "SNAPSHOT_DIR", tmp_path / "asmae_snapshots")
    monkeypatch.setattr(snapshot_store, "SNAPSHOT_NODE_DIR", tmp_path / "asmae_snapshots" / "nodes")
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()
    yield
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()


# ── TEST 1: Snapshot Identity Reuse Rejection (Collision) ────────────────────

def test_snapshot_identity_reuse_with_differing_numerical_vector_fails_closed():
    """Attempting to publish a differing numerical vector under the same snapshot ID raises collision error."""
    ns = PlotNamespace("tenant-a", "farm-a", "plot-a")
    geom_hash = "geometry-nominal-hash"

    science = _base_asmae_result(num_val=0.365)
    ref = snapshot_store.publish_latest_snapshot(science, context_hash="ctx-1", geometry_hash=geom_hash)
    science["snapshot_ref"] = ref
    snap_id = science["snapshot_id"]

    frontend = _base_frontend_payload(snap_id, num_val=0.365)

    head1 = plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=snap_id,
        asmae_result=science,
        frontend_payload=frontend,
        job_id="job-1",
        manifest_hash="manifest-1",
    )
    assert head1 is not None

    # Attempt to reuse snapshot_id with a conflicting numerical value (0.800)
    conflicting_science = _base_asmae_result(num_val=0.800)
    conflicting_science["snapshot_id"] = snap_id
    conflicting_science["snapshot_ref"] = ref
    conflicting_frontend = _base_frontend_payload(snap_id, num_val=0.800)

    with pytest.raises(ValueError, match="immutable plot snapshot collision: numerical record mismatch"):
        plot_snapshot_store.publish_canonical_plot_snapshot(
            namespace=ns,
            geometry_hash=geom_hash,
            snapshot_id=snap_id,
            asmae_result=conflicting_science,
            frontend_payload=conflicting_frontend,
            job_id="job-2",
            manifest_hash="manifest-2",
        )


# ── TEST 2: Cross-Artifact Mismatch Rejection ────────────────────────────────

def test_cross_artifact_mismatch_fails_numerical_binding_validation():
    """If the published frontend record diverges from the node's numerical record, binding is invalid."""
    ns = PlotNamespace("tenant-a", "farm-a", "plot-a")
    geom_hash = "geometry-nominal-hash"

    science = _base_asmae_result(num_val=0.365)
    ref = snapshot_store.publish_latest_snapshot(science, context_hash="ctx-1", geometry_hash=geom_hash)
    science["snapshot_ref"] = ref
    snap_id = science["snapshot_id"]

    frontend = _base_frontend_payload(snap_id, num_val=0.365)

    plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=snap_id,
        asmae_result=science,
        frontend_payload=frontend,
        job_id="job-1",
        manifest_hash="manifest-1",
    )

    # Tamper with the published frontend payload directly in the publication file (0.365 -> 0.800)
    directory = plot_snapshot_store._plot_dir(ns)
    safe_job_id = hashlib.sha256(b"job-1").hexdigest()[:32]
    pub_path = directory / "publications" / f"{safe_job_id}.json"
    pub_data = json.loads(pub_path.read_text(encoding="utf-8"))

    tampered_rec, tampered_hash = _make_numerical_record(0.800)
    pub_data["frontend_payload"]["asmae_posterior_numerical_record"] = tampered_rec
    pub_data["frontend_payload"]["asmae_proof"]["numerical_vector_hash"] = tampered_hash
    pub_data["frontend_payload"]["scientific_evidence_lineage"]["asmae_posterior_vector_hash"] = tampered_hash

    # Recompute publication hash so that publication envelope itself is valid
    hashable_pub = {k: v for k, v in pub_data.items() if not k.endswith("_ref") and k != "publication_hash"}
    new_pub_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_pub)).hexdigest()
    pub_data["publication_hash"] = new_pub_hash
    pub_path.write_text(json.dumps(pub_data), encoding="utf-8")

    # Update head pointer to match new publication hash
    head_path = plot_snapshot_store._head_path(ns)
    head_data = json.loads(head_path.read_text(encoding="utf-8"))
    head_data["frontend_publication_hash"] = new_pub_hash
    head_path.write_text(json.dumps(head_data), encoding="utf-8")

    # Clear cache to force reload from disk
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()

    loaded = plot_snapshot_store.load_latest_plot_snapshot(ns, geom_hash)
    assert loaded is not None
    # Cross-artifact agreement fails because node has 0.365 hash while publication has 0.800 hash!
    assert loaded["validation"]["nodeAgreementValid"] is False
    assert loaded["validation"]["numericalBindingValid"] is False
    assert loaded["validation"]["bindingValid"] is False
    assert loaded["contract_validation"]["numerical_authority_verified"] is False
    assert loaded["contract_validation"]["derived_publication_status"] == "INVALID_NUMERICAL_BINDING"


# ── TEST 3: Numerical Authority Claimed But Record Missing ───────────────────

def test_numerical_authority_claimed_without_record_fails_closed():
    """If numerical authority is claimed but the record is missing or empty, numericalBindingValid must be False."""
    ns = PlotNamespace("tenant-a", "farm-a", "plot-a")
    geom_hash = "geometry-nominal-hash"

    science = _base_asmae_result(num_val=0.365)
    # Remove the numerical record from science result and unset numerical digest
    science["asmae_posterior_numerical_record"] = None
    science["asmae_numerical_digest"] = None
    ref = snapshot_store.publish_latest_snapshot(science, context_hash="ctx-1", geometry_hash=geom_hash)
    science["snapshot_ref"] = ref
    snap_id = science["snapshot_id"]

    frontend = _base_frontend_payload(snap_id, num_val=0.365)
    frontend["asmae_posterior_numerical_record"] = None
    frontend["claims_numerical_authority"] = True

    plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=snap_id,
        asmae_result=science,
        frontend_payload=frontend,
        job_id="job-1",
        manifest_hash="manifest-1",
    )

    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()
    loaded = plot_snapshot_store.load_latest_plot_snapshot(ns, geom_hash)
    assert loaded is not None
    assert loaded["validation"]["numericalBindingValid"] is False
    assert loaded["validation"]["bindingValid"] is False
    assert loaded["contract_validation"]["derived_publication_status"] == "INVALID_NUMERICAL_BINDING"


# ── TEST 4: Provider-Only Publication Without Numerical Claim ─────────────────

def test_provider_only_publication_without_numerical_claim_remains_available():
    """Provider-only publication that does not claim numerical authority retains numericalBindingValid: None."""
    ns = PlotNamespace("tenant-a", "farm-a", "plot-a")
    geom_hash = "geometry-nominal-hash"

    science = _base_asmae_result(num_val=0.365)
    science["claims_numerical_authority"] = False
    science["asmae_numerical_digest"] = None
    science.pop("asmae_posterior_numerical_record", None)
    ref = snapshot_store.publish_latest_snapshot(science, context_hash="ctx-1", geometry_hash=geom_hash)
    science["snapshot_ref"] = ref
    snap_id = science["snapshot_id"]

    frontend = {
        "version": SURFACES_SCHEMA_VERSION,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "intelligence_snapshot_id": snap_id,
        "plot_id": "plot-a",
        "publication_id": f"pub-{snap_id}",
        "publication_run_id": f"run-{snap_id}",
        "run_id": f"run-{snap_id}",
        "pipeline_state": "terminal_layer10_published",
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "asmae_proof": {"proof_id": f"proof-{snap_id}", "status": "valid"},
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": "crop-lineage-nominal",
            "crop_worldline_event_id": "crop-event-nominal",
            "phenology_worldline_event_id": "phenology-event-nominal",
        },
        "mode_display_state": {"canopy": {"canRenderPixels": True}},
        "source_policy_display_state": {"requested_policy": "satellite"},
        "core_asmae_evidence_state": {"state": "nominal", "content_hash": "dummy_content_hash"},
        "publication_surface_state": {"state": "provider_surface"},
        "surfaces": [{
            "surface_id": "surface-canopy-ndvi",
            "surface_type": "canopy_vigor",
            "values": [[0.55]],
            "resolution_m": 10.0,
            "content_hash": "dummy_hash",
        }],
        "claims_numerical_authority": False,
    }

    plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=snap_id,
        asmae_result=science,
        frontend_payload=frontend,
        job_id="job-1",
        manifest_hash="manifest-1",
    )

    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()
    loaded = plot_snapshot_store.load_latest_plot_snapshot(ns, geom_hash)
    assert loaded is not None
    assert loaded["validation"]["numericalBindingValid"] is None
    assert loaded["validation"]["bindingValid"] is True
    assert loaded["contract_validation"]["derived_publication_status"] in ("VALID_NORMAL", "VALID_DEGRADED")


# ── TEST 5: Cache Deep-Copy Isolation ────────────────────────────────────────

def test_snapshot_cache_deep_copy_isolation():
    """Mutating a returned snapshot dictionary must not mutate the cached instance."""
    ns = PlotNamespace("tenant-a", "farm-a", "plot-a")
    geom_hash = "geometry-nominal-hash"

    science = _base_asmae_result(num_val=0.365)
    ref = snapshot_store.publish_latest_snapshot(science, context_hash="ctx-1", geometry_hash=geom_hash)
    science["snapshot_ref"] = ref
    snap_id = science["snapshot_id"]
    frontend = _base_frontend_payload(snap_id, num_val=0.365)

    plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=snap_id,
        asmae_result=science,
        frontend_payload=frontend,
        job_id="job-1",
        manifest_hash="manifest-1",
    )

    first_load = plot_snapshot_store.load_latest_plot_snapshot(ns, geom_hash)
    assert first_load is not None
    first_load["asmae"]["asmae_posterior_numerical_record"]["states"]["root_zone_moisture"] = 999.99
    first_load["validation"]["tampered_key"] = "hacked"

    second_load = plot_snapshot_store.load_latest_plot_snapshot(ns, geom_hash)
    assert second_load is not None
    assert second_load["asmae"]["asmae_posterior_numerical_record"]["states"]["root_zone_moisture"] == 0.365
    assert "tampered_key" not in second_load["validation"]


# ── TEST 6: Historical Sensor Availability Receipt Binding ───────────────────

def test_hashless_sensor_publication_receipt_cannot_supply_historical_availability():
    """A sensor publication receipt lacking a matching content hash cannot grant historical availability."""
    t_obs = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    t_cutoff = datetime(2026, 8, 15, 12, 30, 0, tzinfo=timezone.utc)
    t_pub = datetime(2026, 8, 15, 12, 10, 0, tzinfo=timezone.utc)

    meas_digest = hashlib.sha256(b"measurement-data-001").hexdigest()

    # Sensor receipt without early first_available_at (passes first_available_at=False)
    sensor_receipt = create_signed_sensor_receipt(
        receipt_id="rcpt_sensor_001",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_001",
        plot_id="plot-a",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal_001",
        content_digest=meas_digest,
        observation_instant=t_obs.isoformat(),
        first_available_at=False,
    )

    # 1. Item with mismatched/hashless publication receipt
    item_without_hash = EvidenceItem(
        evidence_id="ev_sensor_unbound",
        plot_id="plot-a",
        variable="soil_moisture_vwc",
        value=0.35,
        source_family="sensor",
        source_id="sensor_001",
        observation_type="measurement",
        spatial_scope="point",
        observed_at=t_obs,
        content_hash=meas_digest,
        truth_class="observed_sensor",
        receipt=sensor_receipt,
        publication_receipt_verified=True,
        state_update_allowed=True,
        diagnostic_only=False,
    )
    item_without_hash.publication_receipt = {
        "receipt_id": "rcpt_unbound",
        "published_at": t_pub.isoformat(),
        "content_hash": "mismatched_hash_000",
    }

    avail_unbound, reason = ta.is_available_at_cutoff(
        item_without_hash,
        as_of_cutoff=t_cutoff,
        is_historical_replay=True,
    )
    # Must NOT be allowed for state update because publication receipt did not bind measurement digest
    assert item_without_hash.state_update_allowed is False
    assert item_without_hash.diagnostic_only is True
    assert "NO_AUTHENTICATED_AVAILABILITY_ON_HISTORICAL_REPLAY" in item_without_hash.flags

    # 2. Item with matching content hash in publication receipt
    item_with_matching_hash = EvidenceItem(
        evidence_id="ev_sensor_bound",
        plot_id="plot-a",
        variable="soil_moisture_vwc",
        value=0.35,
        source_family="sensor",
        source_id="sensor_001",
        observation_type="measurement",
        spatial_scope="point",
        observed_at=t_obs,
        content_hash=meas_digest,
        truth_class="observed_sensor",
        receipt=sensor_receipt,
        publication_receipt_verified=True,
        state_update_allowed=True,
        diagnostic_only=False,
    )
    item_with_matching_hash.publication_receipt = {
        "receipt_id": "rcpt_bound",
        "published_at": t_pub.isoformat(),
        "content_hash": meas_digest,  # Matching content hash!
    }

    avail_bound, reason = ta.is_available_at_cutoff(
        item_with_matching_hash,
        as_of_cutoff=t_cutoff,
        is_historical_replay=True,
    )
    assert avail_bound is True
    assert item_with_matching_hash.state_update_allowed is True
    assert "NO_AUTHENTICATED_AVAILABILITY_ON_HISTORICAL_REPLAY" not in item_with_matching_hash.flags
    assert avail_bound is True
    assert item_with_matching_hash.state_update_allowed is True
    assert "NO_AUTHENTICATED_AVAILABILITY_ON_HISTORICAL_REPLAY" not in item_with_matching_hash.flags


# ── TEST 7: Display-Grid Orientation Normalization ───────────────────────────

def test_sire_rejects_non_north_up_or_westward_grid_orientations():
    """SIRE rejects south-up (dy > 0) and westward (dx < 0) transforms fail-closed."""
    # North-up, eastward: Valid (Affine convention: a=1.0 > 0, e=-1.0 < 0, b=0, d=0)
    valid_spec = {
        "bounds": [0.0, 0.0, 100.0, 100.0],
        "width": 100,
        "height": 100,
        "transform": [1.0, 0.0, 0.0, 0.0, -1.0, 100.0],
        "crs": "EPSG:4326",
    }
    ok, reason = validate_spatial_grid_spec(valid_spec, 100, 100)
    assert ok is True, f"Expected valid spec, got error: {reason}"

    # South-up: dy > 0 (transform[4] = 1.0)
    south_up_spec = copy.deepcopy(valid_spec)
    south_up_spec["transform"][4] = 1.0
    ok, reason = validate_spatial_grid_spec(south_up_spec, 100, 100)
    assert ok is False
    assert reason == "unsupported_grid_orientation_not_north_up"

    # Westward: dx < 0 (transform[0] = -1.0)
    westward_spec = copy.deepcopy(valid_spec)
    westward_spec["transform"][0] = -1.0
    ok, reason = validate_spatial_grid_spec(westward_spec, 100, 100)
    assert ok is False
    assert reason == "unsupported_grid_orientation_not_north_up"

    # Rotated grid (non-zero cross-terms: b=0.5)
    rotated_spec = copy.deepcopy(valid_spec)
    rotated_spec["transform"][1] = 0.5
    ok, reason = validate_spatial_grid_spec(rotated_spec, 100, 100)
    assert ok is False
    assert reason == "unsupported_grid_orientation_not_north_up"
