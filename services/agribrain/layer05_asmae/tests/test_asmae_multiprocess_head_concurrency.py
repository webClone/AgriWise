"""Multiprocess integration tests for atomic plot head supersession and race condition protection."""

from __future__ import annotations

import concurrent.futures
import copy
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer05_asmae import plot_snapshot_store, snapshot_store
from services.agribrain.layer05_asmae.plot_snapshot_store import SURFACES_SCHEMA_VERSION, evaluate_snapshot_admission
from services.agribrain.layer10_sire.surface_contract import RENDER_AUTHORIZATION_VERSION
from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash
from fastapi.testclient import TestClient
from services.agribrain.app.main import app, require_internal_service_request
from services.agribrain.app.internal_service_auth import compute_request_signature


def _publish_candidate(
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    geometry_hash: str,
    job_id: str,
    states: Dict[str, float],
    sigmas: Dict[str, float],
    allow_overwrite: bool = False,
    extra_entropy: str = "",
) -> Dict[str, Any]:
    vec_hash = compute_asmae_vector_numerical_hash(states, sigmas)
    num_rec = {
        "states": states,
        "sigmas": sigmas,
        "numerical_vector_hash": vec_hash,
    }
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    res = {
        "contract_version": "v1",
        "plot_id": plot_id,
        "job_id": job_id,
        "crop_cycle_id": "cycle-test",
        "states": states,
        "sigmas": sigmas,
        "content_hash": hashlib.sha256(f"{job_id}-{extra_entropy}".encode("utf-8")).hexdigest(),
        "crop_posterior_lineage": f"lineage-{job_id}",
        "crop_worldline_event_id": f"evt-{job_id}",
        "phenology_worldline_event_id": f"evt-p{job_id}",
        "crop_influence_manifest_hash": f"man-hash-{job_id}",
        "crop_evidence_ledger_hash": f"led-hash-{job_id}",
        "publication_authority": "CERTIFIED_NUMERICAL",
        "claims_numerical_authority": True,
        "asmae_posterior_numerical_record": num_rec,
        "asmae_numerical_digest": vec_hash,
    }
    ref = snapshot_store.publish_latest_snapshot(res, context_hash=f"ctx-{job_id}-{extra_entropy}", geometry_hash=geometry_hash)
    snap_id = res["snapshot_id"]
    res["snapshot_ref"] = ref

    fe_payload = {
        "version": SURFACES_SCHEMA_VERSION,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "intelligence_snapshot_id": snap_id,
        "contract_version": "v1",
        "plot_id": plot_id,
        "publication_id": f"pub-{snap_id}",
        "publication_run_id": f"run-{job_id}",
        "run_id": f"run-{job_id}",
        "crop_cycle_id": "cycle-test",
        "pipeline_state": "terminal_layer10_published",
        "publication_status": "VALID_NORMAL",
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "publication_authority": "CERTIFIED_NUMERICAL",
        "claims_numerical_authority": True,
        "asmae_posterior_numerical_record": num_rec,
        "asmae_proof": {"proof_id": f"proof-{snap_id}", "status": "valid", "numerical_vector_hash": vec_hash},
        "scientific_evidence_lineage": {
            "asmae_posterior_vector_hash": vec_hash,
            "crop_posterior_lineage": f"lineage-{job_id}",
            "crop_worldline_event_id": f"evt-{job_id}",
            "phenology_worldline_event_id": f"evt-p{job_id}",
        },
        "mode_display_state": {"canopy": {"canRenderPixels": True}},
        "source_policy_display_state": {"requested_policy": "satellite"},
        "core_asmae_evidence_state": {"state": "nominal", "content_hash": "dummy_content_hash"},
        "publication_surface_state": {"state": "provider_surface"},
        "surfaces": [
            {
                "surface_id": "surface-canopy-ndvi",
                "surface_type": "canopy_vigor",
                "values": [[0.52]],
                "resolution_m": 10.0,
                "content_hash": hashlib.sha256(f"surf-{snap_id}".encode("utf-8")).hexdigest(),
            }
        ],
    }
    return plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geometry_hash,
        snapshot_id=snap_id,
        asmae_result=res,
        frontend_payload=fe_payload,
        job_id=job_id,
        manifest_hash=f"manifest-{snap_id}",
        publication_authority="CERTIFIED_NUMERICAL",
        allow_overwrite=allow_overwrite,
    )


def _multiprocess_publish_worker(
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    geometry_hash: str,
    worker_idx: int,
    job_id: str,
    states: Dict[str, float],
    sigmas: Dict[str, float],
    ready_dir: str,
    barrier_path: str,
) -> Tuple[str, bool, Optional[str]]:
    """Top-level worker function for multiprocess concurrency testing on Windows/POSIX."""
    vec_hash = compute_asmae_vector_numerical_hash(states, sigmas)
    num_rec = {
        "states": states,
        "sigmas": sigmas,
        "numerical_vector_hash": vec_hash,
    }

    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)

    res = {
        "contract_version": "v1",
        "plot_id": plot_id,
        "worker_idx": worker_idx,
        "job_id": job_id,
        "crop_cycle_id": "cycle-test",
        "states": states,
        "sigmas": sigmas,
        "content_hash": f"hash-{worker_idx}-" + "a" * 56,
        "crop_posterior_lineage": f"lineage-{worker_idx}",
        "crop_worldline_event_id": f"evt-{worker_idx}",
        "phenology_worldline_event_id": f"evt-p{worker_idx}",
        "crop_influence_manifest_hash": f"man-hash-{worker_idx}",
        "crop_evidence_ledger_hash": f"led-hash-{worker_idx}",
        "publication_authority": "CERTIFIED_NUMERICAL",
        "claims_numerical_authority": True,
        "asmae_posterior_numerical_record": num_rec,
        "asmae_numerical_digest": vec_hash,
    }
    ref = snapshot_store.publish_latest_snapshot(res, context_hash=f"ctx-worker-{worker_idx}", geometry_hash=geometry_hash)
    snap_id = res["snapshot_id"]
    res["snapshot_ref"] = ref

    fe_payload = {
        "intelligence_snapshot_id": snap_id,
        "contract_version": "v1",
        "plot_id": plot_id,
        "crop_cycle_id": "cycle-test",
        "publication_authority": "CERTIFIED_NUMERICAL",
        "claims_numerical_authority": True,
        "asmae_posterior_numerical_record": num_rec,
        "asmae_proof": {"numerical_vector_hash": vec_hash},
        "scientific_evidence_lineage": {
            "asmae_posterior_vector_hash": vec_hash,
            "crop_posterior_lineage": f"lineage-{worker_idx}",
            "crop_worldline_event_id": f"evt-{worker_idx}",
            "phenology_worldline_event_id": f"evt-p{worker_idx}",
        },
        "surface_pack": [
            {
                "surface_id": "surface-canopy-ndvi",
                "surface_type": "canopy_vigor",
                "values": [[0.52]],
                "resolution_m": 10.0,
                "content_hash": f"dummy_hash_{worker_idx}",
            }
        ],
    }

    # Signal ready to main process
    ready_file = Path(ready_dir) / f"ready_{worker_idx}.flag"
    ready_file.write_text("ready", encoding="utf-8")

    # Spin waiting for barrier file
    while not os.path.exists(barrier_path):
        time.sleep(0.001)

    try:
        plot_snapshot_store.publish_canonical_plot_snapshot(
            namespace=ns,
            geometry_hash=geometry_hash,
            snapshot_id=snap_id,
            asmae_result=res,
            frontend_payload=fe_payload,
            job_id=job_id,
            manifest_hash=f"manifest-{snap_id}",
            publication_authority="CERTIFIED_NUMERICAL",
            allow_overwrite=False,
        )
        return (snap_id, True, None)
    except Exception as exc:
        return (snap_id, False, str(exc))


def test_multiprocess_concurrent_head_supersession_atomic(tmp_path):
    """P1: Verify cross-process atomic serialization on head supersession.

    Spawns 4 concurrent OS processes competing to supersede an existing head.
    Exactly 1 process wins and supersedes the head.
    The remaining 3 processes detect the supersession collision and fail closed with ValueError.
    """
    plot_id = f"parcel-mp-race-{int(time.time() * 1000)}"
    tenant_id = "tenant-mp-race"
    farm_id = "farm-mp-race"
    geom_hash = "geom-mp-race"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)

    states = {"root_zone_moisture": 0.28, "canopy_vigor": 0.72}
    sigmas = {"root_zone_moisture": 0.02, "canopy_vigor": 0.03}
    vec_hash = compute_asmae_vector_numerical_hash(states, sigmas)

    # 1. Establish initial head
    res_init = {
        "contract_version": "v1",
        "plot_id": plot_id,
        "worker_idx": -1,
        "job_id": "job-init",
        "crop_cycle_id": "cycle-test",
        "states": states,
        "sigmas": sigmas,
        "content_hash": "0" * 64,
        "crop_posterior_lineage": "lineage-init",
        "crop_worldline_event_id": "evt-init",
        "phenology_worldline_event_id": "evt-pinit",
        "crop_influence_manifest_hash": "man-init",
        "crop_evidence_ledger_hash": "led-init",
        "publication_authority": "CERTIFIED_NUMERICAL",
        "claims_numerical_authority": True,
        "asmae_posterior_numerical_record": {
            "states": states,
            "sigmas": sigmas,
            "numerical_vector_hash": vec_hash,
        },
        "asmae_numerical_digest": vec_hash,
    }
    ref_init = snapshot_store.publish_latest_snapshot(res_init, context_hash="ctx-init", geometry_hash=geom_hash)
    initial_snap_id = res_init["snapshot_id"]
    res_init["snapshot_ref"] = ref_init

    fe_init = {
        "intelligence_snapshot_id": initial_snap_id,
        "contract_version": "v1",
        "plot_id": plot_id,
        "crop_cycle_id": "cycle-test",
        "publication_authority": "CERTIFIED_NUMERICAL",
        "claims_numerical_authority": True,
        "asmae_posterior_numerical_record": {
            "states": states,
            "sigmas": sigmas,
            "numerical_vector_hash": vec_hash,
        },
        "asmae_proof": {"numerical_vector_hash": vec_hash},
        "scientific_evidence_lineage": {
            "asmae_posterior_vector_hash": vec_hash,
            "crop_posterior_lineage": "lineage-init",
            "crop_worldline_event_id": "evt-init",
            "phenology_worldline_event_id": "evt-pinit",
        },
        "surface_pack": [
            {
                "surface_id": "surface-canopy-ndvi",
                "surface_type": "canopy_vigor",
                "values": [[0.52]],
                "resolution_m": 10.0,
                "content_hash": "dummy_hash_init",
            }
        ],
    }

    plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=geom_hash,
        snapshot_id=initial_snap_id,
        asmae_result=res_init,
        frontend_payload=fe_init,
        job_id="job-init",
        manifest_hash="manifest-init",
        publication_authority="CERTIFIED_NUMERICAL",
    )
    assert plot_snapshot_store.load_latest_plot_snapshot(ns)["snapshot_id"] == initial_snap_id

    # 2. Setup 4 competing workers
    barrier_file = tmp_path / "start_supersession.barrier"
    ready_dir = tmp_path / "ready_supersession"
    ready_dir.mkdir(parents=True, exist_ok=True)

    num_workers = 4
    workers_args = [
        (
            tenant_id,
            farm_id,
            plot_id,
            geom_hash,
            i,
            f"job-competitor-{i}",
            states,
            sigmas,
            str(ready_dir),
            str(barrier_file),
        )
        for i in range(num_workers)
    ]

    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(_multiprocess_publish_worker, *args) for args in workers_args]
        # Wait until all workers signal ready
        deadline = time.time() + 15.0
        while len(list(ready_dir.glob("ready_*.flag"))) < num_workers and time.time() < deadline:
            time.sleep(0.01)

        # Release all workers at the exact same moment
        barrier_file.write_text("go", encoding="utf-8")
        results = [f.result(timeout=30) for f in futures]

    successes = [r for r in results if r[1] is True]
    failures = [r for r in results if r[1] is False]

    assert len(successes) == 1, f"Expected exactly 1 winner, got {len(successes)}: {results}"
    assert len(failures) == 3, f"Expected exactly 3 collisions, got {len(failures)}: {results}"

    winning_snap_id = successes[0][0]
    for fail_snap_id, _, err_msg in failures:
        assert "concurrent publication collision" in err_msg
        assert "superseded" in err_msg

    # Verify head on disk matches the winning worker's snapshot
    latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert latest is not None
    assert latest["snapshot_id"] == winning_snap_id
    assert latest["validation"]["numericalBindingValid"] is True

    # Winning snapshot is retrievable by exact ID
    exact_winner = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(winning_snap_id, namespace=ns)
    assert exact_winner is not None
    assert exact_winner["snapshot_id"] == winning_snap_id
    assert exact_winner["validation"]["numericalBindingValid"] is True

    # Acceptance Test 2: Exact API requests for the three losing snapshot IDs return unavailable/uncommitted
    for fail_snap_id, _, _ in failures:
        exact_loser = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(fail_snap_id, namespace=ns)
        assert exact_loser is None, f"Losing snapshot {fail_snap_id} must be uncommitted and unavailable via exact lookup"

    # Acceptance Test 3: Previously committed, genuinely superseded snapshot remains retrievable by exact ID
    exact_superseded = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(initial_snap_id, namespace=ns)
    assert exact_superseded is not None, "Genuinely superseded initial head must remain retrievable by exact ID"
    assert exact_superseded["snapshot_id"] == initial_snap_id
    assert exact_superseded["validation"]["numericalBindingValid"] is True


def test_multiprocess_concurrent_initial_head_race_atomic(tmp_path):
    """P1: Verify cross-process atomic serialization on initially empty plot head.

    Spawns 4 concurrent OS processes competing to publish the very first head to a fresh plot.
    Exactly 1 process wins and initializes the head.
    The remaining 3 processes detect the collision and fail closed with ValueError.
    """
    plot_id = f"parcel-mp-init-race-{int(time.time() * 1000)}"
    tenant_id = "tenant-mp-init"
    farm_id = "farm-mp-init"
    geom_hash = "geom-mp-init"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)

    states = {"root_zone_moisture": 0.35, "canopy_vigor": 0.65}
    sigmas = {"root_zone_moisture": 0.015, "canopy_vigor": 0.025}

    # Ensure no prior head exists
    assert plot_snapshot_store.load_latest_plot_snapshot(ns) is None

    barrier_file = tmp_path / "start_init_race.barrier"
    ready_dir = tmp_path / "ready_init"
    ready_dir.mkdir(parents=True, exist_ok=True)

    num_workers = 4
    workers_args = [
        (
            tenant_id,
            farm_id,
            plot_id,
            geom_hash,
            i,
            f"job-init-competitor-{i}",
            states,
            sigmas,
            str(ready_dir),
            str(barrier_file),
        )
        for i in range(num_workers)
    ]

    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(_multiprocess_publish_worker, *args) for args in workers_args]
        # Wait until all workers signal ready
        deadline = time.time() + 15.0
        while len(list(ready_dir.glob("ready_*.flag"))) < num_workers and time.time() < deadline:
            time.sleep(0.01)

        # Release all workers at the exact same moment
        barrier_file.write_text("go", encoding="utf-8")
        results = [f.result(timeout=30) for f in futures]

    successes = [r for r in results if r[1] is True]
    failures = [r for r in results if r[1] is False]

    assert len(successes) == 1, f"Expected exactly 1 winner, got {len(successes)}: {results}"
    assert len(failures) == 3, f"Expected exactly 3 collisions, got {len(failures)}: {results}"

    winning_snap_id = successes[0][0]
    for fail_snap_id, _, err_msg in failures:
        assert "concurrent publication collision" in err_msg
        assert "initialized by another process" in err_msg

    # Verify head on disk matches the winning worker's snapshot
    latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert latest is not None
    assert latest["snapshot_id"] == winning_snap_id
    assert latest["validation"]["numericalBindingValid"] is True

    # Winning snapshot is retrievable by exact ID
    exact_winner = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(winning_snap_id, namespace=ns)
    assert exact_winner is not None
    assert exact_winner["snapshot_id"] == winning_snap_id
    assert exact_winner["validation"]["numericalBindingValid"] is True

    # Acceptance Test 2: Exact API requests for the three losing snapshot IDs return unavailable/uncommitted
    for fail_snap_id, _, _ in failures:
        exact_loser = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(fail_snap_id, namespace=ns)
        assert exact_loser is None, f"Losing snapshot {fail_snap_id} must be uncommitted and unavailable via exact lookup"


def test_corrupt_or_malformed_ledger_fails_closed(tmp_path):
    """P1/P2 (F01, F03): Verify that orphan staging and malformed/tampered ledgers strictly fail closed.

    Enforces:
    1. Orphan candidate whose node references an ancestor fails closed (returns None) when uncommitted.
    2. Missing, empty, or truncated commits.jsonl never admits uncommitted staged candidates.
    3. Malformed JSON, sequence discontinuity, parent hash break, tampered commit_hash, or duplicate snapshot_id
       in commits.jsonl strictly fail closed for exact retrieval.
    """
    plot_id = f"parcel-ledger-audit-{int(time.time() * 1000)}"
    tenant_id = "tenant-ledger"
    farm_id = "farm-ledger"
    geom_hash = "geom-ledger"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)

    states = {"root_zone_moisture": 0.40, "canopy_vigor": 0.70}
    sigmas = {"root_zone_moisture": 0.02, "canopy_vigor": 0.03}

    # 1. Publish initial committed head
    published1 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-init", states, sigmas)
    snap1_id = published1["snapshot_id"]

    assert plot_snapshot_store.load_latest_plot_snapshot(ns) is not None
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is not None

    commits_file = directory / "commits.jsonl"
    assert commits_file.exists()
    original_commits_text = commits_file.read_text(encoding="utf-8")

    # 2. Stage an orphan candidate whose node references snap1_id as supersedes_snapshot_id
    # but which was NEVER committed into commits.jsonl or head.json
    orphan_snap_id = f"L10-ORPHAN-{uuid.uuid4().hex[:8]}"
    job_id = f"job-orphan-{orphan_snap_id}"
    safe_job_id = hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:32]
    node_dir = directory / "nodes"
    pub_dir = directory / "publications"
    rcpt_dir = directory / "receipts"
    node_dir.mkdir(parents=True, exist_ok=True)
    pub_dir.mkdir(parents=True, exist_ok=True)
    rcpt_dir.mkdir(parents=True, exist_ok=True)

    orphan_node = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": orphan_snap_id,
        "supersedes_snapshot_id": snap1_id, # Claims ancestor
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "job_id": job_id,
        "manifest_hash": "manifest-hash-orphan",
    }
    hashable_node = {k: v for k, v in orphan_node.items() if not k.endswith("_ref")}
    orphan_node["node_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_node)).hexdigest()
    (node_dir / f"{orphan_snap_id}.json").write_bytes(plot_snapshot_store._json_bytes(orphan_node))

    orphan_pub = {
        "contract_version": plot_snapshot_store.PLOT_PUBLICATION_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": orphan_snap_id,
        "job_id": job_id,
        "manifest_hash": "manifest-hash-orphan",
        "node_ref": str(node_dir / f"{orphan_snap_id}.json"),
        "node_hash": orphan_node["node_hash"],
        "frontend_payload": {"surfaces": [], "version": "v1"},
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    hashable_pub = {k: v for k, v in orphan_pub.items() if not k.endswith("_ref")}
    orphan_pub["publication_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_pub)).hexdigest()
    (pub_dir / f"{safe_job_id}.json").write_bytes(plot_snapshot_store._json_bytes(orphan_pub))

    orphan_rcpt = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_RECEIPT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": orphan_snap_id,
        "job_id": job_id,
        "manifest_hash": "manifest-hash-orphan",
        "node_ref": str(node_dir / f"{orphan_snap_id}.json"),
        "node_hash": orphan_node["node_hash"],
        "frontend_publication_hash": orphan_pub["publication_hash"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    hashable_rcpt = {k: v for k, v in orphan_rcpt.items() if not k.endswith("_ref")}
    orphan_rcpt["receipt_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_rcpt)).hexdigest()
    (rcpt_dir / f"{safe_job_id}.json").write_bytes(plot_snapshot_store._json_bytes(orphan_rcpt))

    # A) Orphan candidate is rejected when ledger is healthy
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(orphan_snap_id, namespace=ns) is None

    # B) R1: Missing commits.jsonl on post-ledger head must fail closed (withhold authority)
    commits_file.unlink()
    assert not commits_file.exists()
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(orphan_snap_id, namespace=ns) is None
    assert plot_snapshot_store.load_latest_plot_snapshot(ns) is None
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is None
    with pytest.raises(ValueError, match="committed ledger markers"):
        _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-blocked-1", states, sigmas)

    # C) R1: Empty commits.jsonl on post-ledger head must fail closed
    commits_file.write_text("", encoding="utf-8")
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(orphan_snap_id, namespace=ns) is None
    assert plot_snapshot_store.load_latest_plot_snapshot(ns) is None
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is None
    with pytest.raises(ValueError, match="committed ledger markers"):
        _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-blocked-2", states, sigmas)

    # D) R4: Strict 64-char lowercase hex validation in ledger
    rec = json.loads(original_commits_text.strip())
    for hex_field in ("node_hash", "frontend_publication_hash", "publication_receipt_hash"):
        tampered = dict(rec)
        tampered[hex_field] = "z" * 64  # Non-hex characters
        commits_file.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
        is_valid, _, err = plot_snapshot_store.validate_publication_commit_ledger(directory)
        assert is_valid is False
        assert f"Invalid {hex_field}" in err

    tampered = dict(rec)
    tampered["commit_hash"] = "z" * 64
    commits_file.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
    is_valid, _, err = plot_snapshot_store.validate_publication_commit_ledger(directory)
    assert is_valid is False
    assert "Invalid commit_hash" in err

    # E) F03: Malformed JSON in commits.jsonl fails closed
    commits_file.write_text("{malformed json line", encoding="utf-8")
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is None
    assert plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True) is None

    # F) F03: Tampered commit_hash fails closed
    rec = json.loads(original_commits_text.strip())
    rec["commit_hash"] = "0" * 64
    commits_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is None

    # G) F03: Broken parent link fails closed
    rec = json.loads(original_commits_text.strip())
    rec["parent_commit_hash"] = "f" * 64
    commits_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is None

    # H) F03: Duplicate snapshot_id fails closed
    commits_file.write_text(original_commits_text + original_commits_text, encoding="utf-8")
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is None

    # Restore original commits.jsonl -> healthy retrieval resumes
    commits_file.write_text(original_commits_text, encoding="utf-8")
    assert plot_snapshot_store.load_latest_plot_snapshot(ns) is not None
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is not None

    # I) R1 Multi-commit: publish commit 2, delete ledger -> authority withheld and publish blocked; restore ledger -> recovered
    published2 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-init-2", states, sigmas, extra_entropy="commit2")
    snap2_id = published2["snapshot_id"]
    two_commits_text = commits_file.read_text(encoding="utf-8")
    assert len(two_commits_text.strip().splitlines()) == 2

    commits_file.unlink()
    assert plot_snapshot_store.load_latest_plot_snapshot(ns) is None
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is None
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap2_id, namespace=ns) is None
    with pytest.raises(ValueError, match="committed ledger markers"):
        _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-blocked-3", states, sigmas)

    commits_file.write_text(two_commits_text, encoding="utf-8")
    recov_head = plot_snapshot_store.load_latest_plot_snapshot(ns)
    assert recov_head is not None
    assert recov_head["snapshot_id"] == snap2_id
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is not None
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap2_id, namespace=ns) is not None


def test_crash_recovery_between_ledger_append_and_head_update(tmp_path):
    """P1 (F02 / R2): Verify deterministic crash recovery when writer dies between ledger fsync and head update.

    Simulates process termination after appending and fsyncing commits.jsonl, but before atomically replacing head.json.
    Verifies:
    1. Latest reader deterministically reconciles head.json to the validated ledger tip.
    2. evaluate_snapshot_admission confirms candidate validity.
    3. FastAPI HTTP 200 verification for /v2/snapshots/{snap2_id} and /v2/plots/{plot_id}/snapshot.
    4. Exact reader successfully retrieves the new snapshot.
    5. Historical retrieval for earlier commit continues to work.
    6. Negative test: corrupted/unadmitted tip leaves head un-promoted and halts new publications.
    """
    plot_id = f"parcel-crash-recovery-{int(time.time() * 1000)}"
    tenant_id = "tenant-crash"
    farm_id = "farm-crash"
    geom_hash = "geom-crash"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)

    states = {"root_zone_moisture": 0.35, "canopy_vigor": 0.65}
    sigmas = {"root_zone_moisture": 0.015, "canopy_vigor": 0.025}

    # 1. Publish initial snapshot (Commit 1)
    published1 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-crash-1", states, sigmas)
    snap1_id = published1["snapshot_id"]

    head1 = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert head1["snapshot_id"] == snap1_id
    assert head1["commit_seq"] == 1

    head_file = plot_snapshot_store._head_path(ns)
    head1_bytes = head_file.read_bytes()

    # 2. Publish Commit 2 using _publish_candidate (ensures fully admitted CERTIFIED_NUMERICAL candidate)
    states2 = {"root_zone_moisture": 0.38, "canopy_vigor": 0.62}
    published2 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-crash-2", states2, sigmas, extra_entropy="crash2")
    snap2_id = published2["snapshot_id"]

    # 3. Simulate crash: revert head.json to Commit 1 state while leaving commits.jsonl at Commit 2
    head_file.write_bytes(head1_bytes)
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()

    raw_head = plot_snapshot_store._read(head_file)
    assert raw_head["snapshot_id"] == snap1_id
    assert raw_head["commit_seq"] == 1

    commits_file = directory / "commits.jsonl"
    lines = [json.loads(l) for l in commits_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2
    assert lines[-1]["snapshot_id"] == snap2_id

    # 4. In a fresh read, call load_latest_plot_snapshot -> triggers deterministic reconciliation
    reconciled_latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert reconciled_latest is not None
    assert reconciled_latest["snapshot_id"] == snap2_id, "Latest reader must deterministically reconcile to ledger tip"
    assert reconciled_latest["commit_seq"] == 2

    # Verify evaluate_snapshot_admission passes on reconciled candidate
    admission = evaluate_snapshot_admission(reconciled_latest, namespace=ns)
    assert admission["is_valid"] is True
    assert admission["status"] == "admitted"

    # 5. Exact retrieval for snap2_id succeeds and agrees with latest reader
    exact_snap2 = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap2_id, namespace=ns)
    assert exact_snap2 is not None
    assert exact_snap2["snapshot_id"] == snap2_id

    # 6. Historical retrieval for snap1_id still succeeds
    exact_snap1 = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns)
    assert exact_snap1 is not None
    assert exact_snap1["snapshot_id"] == snap1_id

    # 7. FastAPI HTTP API verification: HTTP 200 for latest plot snapshot and exact snapshot
    app.dependency_overrides[require_internal_service_request] = lambda: ns
    try:
        client = TestClient(app)
        resp_latest = client.get(f"/v2/plots/{plot_id}/snapshot")
        assert resp_latest.status_code == 200
        data_latest = resp_latest.json()
        assert data_latest["available"] is True
        assert data_latest["snapshot_id"] == snap2_id

        resp_exact = client.get(f"/v2/snapshots/{snap2_id}")
        assert resp_exact.status_code == 200
        data_exact = resp_exact.json()
        assert data_exact["available"] is True
        assert data_exact["snapshot_id"] == snap2_id
    finally:
        app.dependency_overrides.pop(require_internal_service_request, None)

    # 8. Negative R2 Test: Corrupted/unadmitted tip in commits.jsonl leaves head at snap2_id and halts publication
    corrupt_sid = f"L10-CORRUPT-{uuid.uuid4().hex[:8]}"
    corrupt_rec = {
        "commit_seq": 3,
        "snapshot_id": corrupt_sid,
        "node_hash": "a" * 64,
        "frontend_publication_hash": "b" * 64,
        "publication_receipt_hash": "c" * 64,
        "publication_job_id": "job-corrupt-3",
        "committed_at": datetime.now(timezone.utc).isoformat(),
        "parent_commit_hash": lines[-1]["commit_hash"],
    }
    corrupt_rec["commit_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes({k: v for k, v in corrupt_rec.items() if k != "commit_hash"})).hexdigest()
    with open(commits_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(corrupt_rec) + "\n")

    # Reconcile fails to promote corrupt tip (staged files missing or corrupt) -> head stays at snap2_id
    with plot_snapshot_store._plot_publication_lock(directory):
        rec_res = plot_snapshot_store.reconcile_publication_ledger_and_head(directory, ns)
    assert rec_res["snapshot_id"] == snap2_id

    # Attempting to publish new snapshot must fail closed with ValueError due to unreconciled tip
    with pytest.raises(ValueError, match="could not be reconciled with head"):
        _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-should-fail", states, sigmas)


def test_idempotent_republish_no_duplicate_commit(tmp_path):
    """Verify that republishing the same snapshot with identical hashes is idempotent and creates no duplicate commit."""
    plot_id = f"parcel-idempotent-{int(time.time() * 1000)}"
    tenant_id = "tenant-idem"
    farm_id = "farm-idem"
    geom_hash = "geom-idem"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)

    states = {"root_zone_moisture": 0.42, "canopy_vigor": 0.68}
    sigmas = {"root_zone_moisture": 0.018, "canopy_vigor": 0.022}

    published1 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-idem-1", states, sigmas)
    snap_id = published1["snapshot_id"]

    commits_file = directory / "commits.jsonl"
    lines1 = [l for l in commits_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines1) == 1

    # Re-publish identical candidate with allow_overwrite=True
    published2 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-idem-1", states, sigmas, allow_overwrite=True)
    assert published2["snapshot_id"] == snap_id

    lines2 = [l for l in commits_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines2) == 1, "Idempotent re-publish must not append an additional commit"


def test_genesis_crash_recovery_missing_head_reconciles_cleanly(tmp_path):
    """P1-01: Genesis crash recovery when head.json is missing but commits.jsonl has a valid first publication."""
    plot_id = f"parcel-genesis-rec-{int(time.time() * 1000)}"
    tenant_id = "tenant-genesis"
    farm_id = "farm-genesis"
    geom_hash = "geom-genesis"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)

    states = {"root_zone_moisture": 0.36, "canopy_vigor": 0.64}
    sigmas = {"root_zone_moisture": 0.016, "canopy_vigor": 0.024}

    # 1. Publish valid first candidate (genesis commit)
    published = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-genesis-1", states, sigmas)
    snap_id = published["snapshot_id"]

    head_file = plot_snapshot_store._head_path(ns)
    assert head_file.exists()

    # 2. Simulate crash immediately after ledger append & fsync, before head.json was created or retained
    head_file.unlink()
    assert not head_file.exists()
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()

    # 3. Direct call to load_latest_plot_snapshot without head.json must trigger genesis recovery
    reconciled = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert reconciled is not None, "load_latest_plot_snapshot must recover genesis commit when head.json is missing"
    assert reconciled["snapshot_id"] == snap_id
    assert reconciled["commit_seq"] == 1
    assert head_file.exists(), "Reconciliation must have atomically written head.json"

    # Verify scientific admission on recovered snapshot
    admission = evaluate_snapshot_admission(reconciled, namespace=ns)
    assert admission["is_valid"] is True
    assert admission["status"] == "admitted"

    # 4. Exact reader can also load the recovered snapshot
    exact = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap_id, namespace=ns)
    assert exact is not None
    assert exact["snapshot_id"] == snap_id

    # 5. Verify FastAPI endpoints return HTTP 200 for latest and exact queries
    app.dependency_overrides[require_internal_service_request] = lambda: ns
    try:
        client = TestClient(app)
        resp_latest = client.get(f"/v2/plots/{plot_id}/snapshot")
        assert resp_latest.status_code == 200
        assert resp_latest.json()["available"] is True
        assert resp_latest.json()["snapshot_id"] == snap_id

        resp_exact = client.get(f"/v2/snapshots/{snap_id}")
        assert resp_exact.status_code == 200
        assert resp_exact.json()["available"] is True
        assert resp_exact.json()["snapshot_id"] == snap_id
    finally:
        app.dependency_overrides.pop(require_internal_service_request, None)


def test_genesis_crash_recovery_corrupt_genesis_fails_closed(tmp_path):
    """P1-01 Negative: Corrupt genesis commit with missing head.json must fail closed, return None, and NOT create head.json."""
    plot_id = f"parcel-genesis-corrupt-{int(time.time() * 1000)}"
    tenant_id = "tenant-corrupt-gen"
    farm_id = "farm-corrupt-gen"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)
    directory.mkdir(parents=True, exist_ok=True)

    head_file = plot_snapshot_store._head_path(ns)
    assert not head_file.exists()

    commits_file = directory / "commits.jsonl"
    corrupt_sid = f"L10-GENESIS-CORRUPT-{uuid.uuid4().hex[:8]}"
    rec = {
        "commit_seq": 1,
        "snapshot_id": corrupt_sid,
        "node_hash": "a" * 64,
        "frontend_publication_hash": "b" * 64,
        "publication_receipt_hash": "c" * 64,
        "publication_job_id": "job-gen-corrupt",
        "committed_at": datetime.now(timezone.utc).isoformat(),
        "parent_commit_hash": "0" * 64,
    }
    rec["commit_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes({k: v for k, v in rec.items() if k != "commit_hash"})).hexdigest()
    commits_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")

    # 1. load_latest_plot_snapshot returns None and does NOT create head.json
    latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert latest is None
    assert not head_file.exists(), "Corrupt genesis must never create head.json"

    # 2. load_and_validate_plot_snapshot_by_id returns None
    exact = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(corrupt_sid, namespace=ns)
    assert exact is None

    # 3. FastAPI HTTP endpoint returns available=False for latest and 404 for exact
    app.dependency_overrides[require_internal_service_request] = lambda: ns
    try:
        client = TestClient(app)
        resp_latest = client.get(f"/v2/plots/{plot_id}/snapshot")
        assert resp_latest.status_code == 200
        assert resp_latest.json()["available"] is False
        assert resp_latest.json()["reason"] == "canonical_head_not_published"

        resp_exact = client.get(f"/v2/snapshots/{corrupt_sid}")
        assert resp_exact.status_code == 404
    finally:
        app.dependency_overrides.pop(require_internal_service_request, None)

    # 4. Attempting to publish new snapshot fails closed due to un-reconciled tip
    states = {"root_zone_moisture": 0.35, "canopy_vigor": 0.65}
    sigmas = {"root_zone_moisture": 0.015, "canopy_vigor": 0.025}
    with pytest.raises(ValueError, match="could not be reconciled with head"):
        _publish_candidate(tenant_id, farm_id, plot_id, "geom", "job-fail", states, sigmas)


def test_reconciliation_rejects_hash_consistent_but_unadmitted_tip(tmp_path):
    """P1-02: A fully hash-consistent ledger tip that fails semantic contracts must be rejected by reconciliation."""
    plot_id = f"parcel-semantic-rej-{int(time.time() * 1000)}"
    tenant_id = "tenant-sem"
    farm_id = "farm-sem"
    geom_hash = "geom-sem"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)

    states1 = {"root_zone_moisture": 0.33, "canopy_vigor": 0.67}
    sigmas1 = {"root_zone_moisture": 0.015, "canopy_vigor": 0.025}

    # 1. Publish valid initial snapshot (Commit 1)
    published1 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-sem-1", states1, sigmas1)
    snap1_id = published1["snapshot_id"]

    head_file = plot_snapshot_store._head_path(ns)
    head1_bytes = head_file.read_bytes()

    commits_file = directory / "commits.jsonl"
    lines1 = [json.loads(l) for l in commits_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    parent_hash = lines1[-1]["commit_hash"]

    # 2. Stage Commit 2: mathematically 100% hash-consistent on disk, but node has mismatched plot_id!
    snap2_id = f"L10-MISMATCH-{uuid.uuid4().hex[:8]}"
    job2_id = "job-mismatch-2"
    safe_job2 = hashlib.sha256(job2_id.encode("utf-8")).hexdigest()[:32]

    # Node artifact with CONFLICTING plot_id
    mismatched_plot_id = f"{plot_id}-INTRUDER"
    node_payload = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "snapshot_id": snap2_id,
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": mismatched_plot_id,  # <-- CONFLICTING IDENTITY
        "geometry_hash": geom_hash,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "evidence_cutoff_at": None,
        "observation_window": None,
        "crop_cycle_id": "cycle-test",
        "supersedes_snapshot_id": snap1_id,
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "crop_posterior_lineage": None,
        "crop_worldline_event_id": None,
        "phenology_worldline_event_id": None,
        "crop_evidence_ledger_hash": None,
        "crop_influence_manifest_hash": None,
        "scientific_result": {"content_hash": "sci-2"},
        "scientific_content_hash": "sci-2",
    }
    hashable_node = {k: v for k, v in node_payload.items() if not k.endswith("_ref")}
    node_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_node)).hexdigest()
    node_payload["node_hash"] = node_hash

    # Publication artifact
    frontend_payload = {
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "publication_authority": "DIAGNOSTIC_ONLY",
        "publication_status": "READY_DIAGNOSTIC_ONLY",
        "surfaces": [],
        "intelligence_snapshot_id": snap2_id,
    }
    pub_payload = {
        "contract_version": plot_snapshot_store.PLOT_PUBLICATION_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap2_id,
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "node_ref": f"nodes/{snap2_id}.json",
        "node_hash": node_hash,
        "frontend_payload": frontend_payload,
        "published_at": node_payload["published_at"],
        "evidence_cutoff_at": None,
        "observation_window": None,
        "crop_cycle_id": "cycle-test",
        "recorded_at": node_payload["recorded_at"],
    }
    hashable_pub = {k: v for k, v in pub_payload.items() if not k.endswith("_ref")}
    pub_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_pub)).hexdigest()
    pub_payload["publication_hash"] = pub_hash

    # Receipt artifact
    rcpt_payload = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_RECEIPT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap2_id,
        "node_ref": f"nodes/{snap2_id}.json",
        "node_hash": node_hash,
        "source_node_job_id": job2_id,
        "source_node_manifest_hash": "manifest-hash-2",
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "frontend_publication_ref": f"publications/{safe_job2}.json",
        "frontend_publication_hash": pub_hash,
        "equivalence_reason": "scientific_content_hash_equivalent",
        "recorded_at": node_payload["recorded_at"],
    }
    hashable_rcpt = {k: v for k, v in rcpt_payload.items() if not k.endswith("_ref")}
    rcpt_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_rcpt)).hexdigest()
    rcpt_payload["receipt_hash"] = rcpt_hash

    # Write all three artifacts
    (directory / "nodes" / f"{snap2_id}.json").write_bytes(plot_snapshot_store._json_bytes(node_payload))
    (directory / "publications" / f"{safe_job2}.json").write_bytes(plot_snapshot_store._json_bytes(pub_payload))
    (directory / "receipts" / f"{safe_job2}.json").write_bytes(plot_snapshot_store._json_bytes(rcpt_payload))

    # Append validly formatted commit 2 to commits.jsonl
    commit2_rec = {
        "commit_seq": 2,
        "snapshot_id": snap2_id,
        "node_hash": node_hash,
        "frontend_publication_hash": pub_hash,
        "publication_receipt_hash": rcpt_hash,
        "publication_job_id": job2_id,
        "committed_at": node_payload["recorded_at"],
        "parent_commit_hash": parent_hash,
    }
    commit2_rec["commit_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes({k: v for k, v in commit2_rec.items() if k != "commit_hash"})).hexdigest()
    with open(commits_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(commit2_rec) + "\n")

    # 3. Trigger reconciliation under publication lock
    with plot_snapshot_store._plot_publication_lock(directory):
        rec_res = plot_snapshot_store.reconcile_publication_ledger_and_head(directory, ns)

    # Must preserve Commit 1 and reject Commit 2 due to namespace mismatch
    assert rec_res["snapshot_id"] == snap1_id
    assert head_file.read_bytes() == head1_bytes, "head.json bytes must remain unaltered"

    # 4. Read contracts reject the unadmitted candidate and withhold scientific authority
    with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
        plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()

    # Latest reader detects unreconciled tip and fails closed (returns None, no authority issued)
    assert plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True) is None, \
        "Latest reader must withhold scientific authority when ledger tip is unreconciled"

    # Exact reader strictly rejects the unadmitted tip
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap2_id, namespace=ns) is None, \
        "Exact reader must reject the semantically mismatched tip"

    # 5. Subsequent publication fails closed due to unreconciled tip
    with pytest.raises(ValueError, match="could not be reconciled with head"):
        _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-should-fail", states1, sigmas1)


def test_authenticated_signed_retrieval_end_to_end(tmp_path):
    """P2: Verify real HMAC-SHA256 authenticated retrieval of /v2/plots/{plot_id}/snapshot without dependency overrides."""
    plot_id = f"parcel-signed-{int(time.time() * 1000)}"
    tenant_id = "tenant-signed"
    farm_id = "farm-signed"
    geom_hash = "geom-signed"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)

    states = {"root_zone_moisture": 0.40, "canopy_vigor": 0.60}
    sigmas = {"root_zone_moisture": 0.02, "canopy_vigor": 0.02}

    published = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-signed-1", states, sigmas)
    snap_id = published["snapshot_id"]

    client = TestClient(app)
    path = f"/v2/plots/{plot_id}/snapshot"
    ts = str(time.time())
    nonce = uuid.uuid4().hex

    sig = compute_request_signature(
        method="GET",
        path=path,
        query_string="",
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        body_bytes=b"",
        timestamp=ts,
        nonce=nonce,
        key_version="v1",
    )

    headers = {
        "X-AgriBrain-Signature": sig,
        "X-AgriBrain-Timestamp": ts,
        "X-AgriBrain-Nonce": nonce,
        "X-AgriBrain-Key-Version": "v1",
        "X-Tenant-Id": tenant_id,
        "X-Farm-Id": farm_id,
        "X-Plot-Id": plot_id,
    }

    # 1. Genuine signed GET succeeds through real require_internal_service_request
    resp = client.get(path, headers=headers)
    assert resp.status_code == 200, f"Signed retrieval failed: {resp.text}"
    assert resp.json()["available"] is True
    assert resp.json()["snapshot_id"] == snap_id

    # 2. Tampered signature fails closed (401 Unauthorized)
    headers_bad_sig = {**headers, "X-AgriBrain-Signature": "deadbeef" * 8, "X-AgriBrain-Nonce": uuid.uuid4().hex}
    resp_bad_sig = client.get(path, headers=headers_bad_sig)
    assert resp_bad_sig.status_code == 401

    # 3. Missing headers fails closed (401 Unauthorized)
    resp_no_headers = client.get(path)
    assert resp_no_headers.status_code == 401

    # 4. Replay attack with same nonce fails closed (401 Unauthorized)
    resp_replay = client.get(path, headers=headers)
    assert resp_replay.status_code == 401


def test_reconciliation_rejects_missing_namespace_fields(tmp_path):
    """P2-A: A candidate tip whose publication or receipt omits mandatory namespace fields must be rejected."""
    plot_id = f"parcel-missing-ns-{int(time.time() * 1000)}"
    tenant_id = "tenant-missing-ns"
    farm_id = "farm-missing-ns"
    geom_hash = "geom-missing-ns"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)

    states1 = {"root_zone_moisture": 0.31, "canopy_vigor": 0.69}
    sigmas1 = {"root_zone_moisture": 0.015, "canopy_vigor": 0.025}

    published1 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-ns-1", states1, sigmas1)
    snap1_id = published1["snapshot_id"]
    head_file = plot_snapshot_store._head_path(ns)
    head1_bytes = head_file.read_bytes()

    commits_file = directory / "commits.jsonl"
    lines1 = [json.loads(l) for l in commits_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    parent_hash = lines1[-1]["commit_hash"]

    # Stage Commit 2: valid node and receipt, but publication OMITS tenant_id and farm_id
    snap2_id = f"L10-MISSING-NS-{uuid.uuid4().hex[:8]}"
    job2_id = "job-missing-ns-2"
    safe_job2 = hashlib.sha256(job2_id.encode("utf-8")).hexdigest()[:32]
    now_ts = datetime.now(timezone.utc).isoformat()

    node_payload = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "snapshot_id": snap2_id,
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "recorded_at": now_ts,
        "published_at": now_ts,
        "evidence_cutoff_at": None,
        "observation_window": None,
        "crop_cycle_id": "cycle-test",
        "supersedes_snapshot_id": snap1_id,
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "crop_posterior_lineage": None,
        "crop_worldline_event_id": None,
        "phenology_worldline_event_id": None,
        "crop_evidence_ledger_hash": None,
        "crop_influence_manifest_hash": None,
        "scientific_result": {"content_hash": "sci-2"},
        "scientific_content_hash": "sci-2",
    }
    hashable_node = {k: v for k, v in node_payload.items() if not k.endswith("_ref")}
    node_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_node)).hexdigest()
    node_payload["node_hash"] = node_hash

    frontend_payload = {
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "publication_authority": "DIAGNOSTIC_ONLY",
        "publication_status": "READY_DIAGNOSTIC_ONLY",
        "surfaces": [],
        "intelligence_snapshot_id": snap2_id,
    }
    # Publication lacks tenant_id and farm_id
    pub_payload = {
        "contract_version": plot_snapshot_store.PLOT_PUBLICATION_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "plot_id": plot_id,
        # tenant_id and farm_id omitted!
        "geometry_hash": geom_hash,
        "snapshot_id": snap2_id,
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "node_ref": f"nodes/{snap2_id}.json",
        "node_hash": node_hash,
        "frontend_payload": frontend_payload,
        "published_at": now_ts,
        "evidence_cutoff_at": None,
        "observation_window": None,
        "crop_cycle_id": "cycle-test",
        "recorded_at": now_ts,
    }
    hashable_pub = {k: v for k, v in pub_payload.items() if not k.endswith("_ref")}
    pub_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_pub)).hexdigest()
    pub_payload["publication_hash"] = pub_hash

    rcpt_payload = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_RECEIPT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap2_id,
        "node_ref": f"nodes/{snap2_id}.json",
        "node_hash": node_hash,
        "source_node_job_id": job2_id,
        "source_node_manifest_hash": "manifest-hash-2",
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "frontend_publication_ref": f"publications/{safe_job2}.json",
        "frontend_publication_hash": pub_hash,
        "equivalence_reason": "scientific_content_hash_equivalent",
        "recorded_at": now_ts,
    }
    hashable_rcpt = {k: v for k, v in rcpt_payload.items() if not k.endswith("_ref")}
    rcpt_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_rcpt)).hexdigest()
    rcpt_payload["receipt_hash"] = rcpt_hash

    (directory / "nodes" / f"{snap2_id}.json").write_bytes(plot_snapshot_store._json_bytes(node_payload))
    (directory / "publications" / f"{safe_job2}.json").write_bytes(plot_snapshot_store._json_bytes(pub_payload))
    (directory / "receipts" / f"{safe_job2}.json").write_bytes(plot_snapshot_store._json_bytes(rcpt_payload))

    commit2_rec = {
        "commit_seq": 2,
        "snapshot_id": snap2_id,
        "node_hash": node_hash,
        "frontend_publication_hash": pub_hash,
        "publication_receipt_hash": rcpt_hash,
        "publication_job_id": job2_id,
        "committed_at": now_ts,
        "parent_commit_hash": parent_hash,
    }
    commit2_rec["commit_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes({k: v for k, v in commit2_rec.items() if k != "commit_hash"})).hexdigest()
    with open(commits_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(commit2_rec) + "\n")

    with plot_snapshot_store._plot_publication_lock(directory):
        rec_res = plot_snapshot_store.reconcile_publication_ledger_and_head(directory, ns)

    assert rec_res["snapshot_id"] == snap1_id
    assert head_file.read_bytes() == head1_bytes
    assert plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True) is None


def test_reconciliation_rejects_conflicting_authority_declarations(tmp_path):
    """P2-B: Conflicting authority declarations across node, publication, receipt, or frontend fail closed."""
    plot_id = f"parcel-conflict-auth-{int(time.time() * 1000)}"
    tenant_id = "tenant-conflict-auth"
    farm_id = "farm-conflict-auth"
    geom_hash = "geom-conflict-auth"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)

    states1 = {"root_zone_moisture": 0.31, "canopy_vigor": 0.69}
    sigmas1 = {"root_zone_moisture": 0.015, "canopy_vigor": 0.025}

    published1 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-auth-1", states1, sigmas1)
    snap1_id = published1["snapshot_id"]
    head_file = plot_snapshot_store._head_path(ns)
    head1_bytes = head_file.read_bytes()

    commits_file = directory / "commits.jsonl"
    lines1 = [json.loads(l) for l in commits_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    parent_hash = lines1[-1]["commit_hash"]

    # Stage Commit 2: node claims DIAGNOSTIC_ONLY, but publication claims CERTIFIED_NUMERICAL
    snap2_id = f"L10-CONFLICT-AUTH-{uuid.uuid4().hex[:8]}"
    job2_id = "job-conflict-auth-2"
    safe_job2 = hashlib.sha256(job2_id.encode("utf-8")).hexdigest()[:32]
    now_ts = datetime.now(timezone.utc).isoformat()

    node_payload = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "snapshot_id": snap2_id,
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "recorded_at": now_ts,
        "published_at": now_ts,
        "evidence_cutoff_at": None,
        "observation_window": None,
        "crop_cycle_id": "cycle-test",
        "supersedes_snapshot_id": snap1_id,
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "crop_posterior_lineage": None,
        "crop_worldline_event_id": None,
        "phenology_worldline_event_id": None,
        "crop_evidence_ledger_hash": None,
        "crop_influence_manifest_hash": None,
        "scientific_result": {"content_hash": "sci-2"},
        "scientific_content_hash": "sci-2",
    }
    hashable_node = {k: v for k, v in node_payload.items() if not k.endswith("_ref")}
    node_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_node)).hexdigest()
    node_payload["node_hash"] = node_hash

    frontend_payload = {
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "publication_authority": "CERTIFIED_NUMERICAL",
        "publication_status": "READY_DIAGNOSTIC_ONLY",
        "surfaces": [],
        "intelligence_snapshot_id": snap2_id,
    }
    pub_payload = {
        "contract_version": plot_snapshot_store.PLOT_PUBLICATION_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "CERTIFIED_NUMERICAL",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap2_id,
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "node_ref": f"nodes/{snap2_id}.json",
        "node_hash": node_hash,
        "frontend_payload": frontend_payload,
        "published_at": now_ts,
        "evidence_cutoff_at": None,
        "observation_window": None,
        "crop_cycle_id": "cycle-test",
        "recorded_at": now_ts,
    }
    hashable_pub = {k: v for k, v in pub_payload.items() if not k.endswith("_ref")}
    pub_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_pub)).hexdigest()
    pub_payload["publication_hash"] = pub_hash

    rcpt_payload = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_RECEIPT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap2_id,
        "node_ref": f"nodes/{snap2_id}.json",
        "node_hash": node_hash,
        "source_node_job_id": job2_id,
        "source_node_manifest_hash": "manifest-hash-2",
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "frontend_publication_ref": f"publications/{safe_job2}.json",
        "frontend_publication_hash": pub_hash,
        "equivalence_reason": "scientific_content_hash_equivalent",
        "recorded_at": now_ts,
    }
    hashable_rcpt = {k: v for k, v in rcpt_payload.items() if not k.endswith("_ref")}
    rcpt_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_rcpt)).hexdigest()
    rcpt_payload["receipt_hash"] = rcpt_hash

    (directory / "nodes" / f"{snap2_id}.json").write_bytes(plot_snapshot_store._json_bytes(node_payload))
    (directory / "publications" / f"{safe_job2}.json").write_bytes(plot_snapshot_store._json_bytes(pub_payload))
    (directory / "receipts" / f"{safe_job2}.json").write_bytes(plot_snapshot_store._json_bytes(rcpt_payload))

    commit2_rec = {
        "commit_seq": 2,
        "snapshot_id": snap2_id,
        "node_hash": node_hash,
        "frontend_publication_hash": pub_hash,
        "publication_receipt_hash": rcpt_hash,
        "publication_job_id": job2_id,
        "committed_at": now_ts,
        "parent_commit_hash": parent_hash,
    }
    commit2_rec["commit_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes({k: v for k, v in commit2_rec.items() if k != "commit_hash"})).hexdigest()
    with open(commits_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(commit2_rec) + "\n")

    with plot_snapshot_store._plot_publication_lock(directory):
        rec_res = plot_snapshot_store.reconcile_publication_ledger_and_head(directory, ns)

    assert rec_res["snapshot_id"] == snap1_id
    assert head_file.read_bytes() == head1_bytes
    assert plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True) is None


def test_reconciliation_rejects_missing_or_conflicting_replay_companion(tmp_path):
    """P2-C: Bitemporal replay receipt companion must be consistently present across node, pub, and rcpt."""
    plot_id = f"parcel-replay-comp-{int(time.time() * 1000)}"
    tenant_id = "tenant-replay-comp"
    farm_id = "farm-replay-comp"
    geom_hash = "geom-replay-comp"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)

    states1 = {"root_zone_moisture": 0.31, "canopy_vigor": 0.69}
    sigmas1 = {"root_zone_moisture": 0.015, "canopy_vigor": 0.025}

    published1 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-comp-1", states1, sigmas1)
    snap1_id = published1["snapshot_id"]
    head_file = plot_snapshot_store._head_path(ns)
    head1_bytes = head_file.read_bytes()

    commits_file = directory / "commits.jsonl"
    lines1 = [json.loads(l) for l in commits_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    parent_hash = lines1[-1]["commit_hash"]

    # Stage Commit 2: node and rcpt have replay receipt, but publication OMITS it
    snap2_id = f"L10-REPLAY-COMP-{uuid.uuid4().hex[:8]}"
    job2_id = "job-comp-2"
    safe_job2 = hashlib.sha256(job2_id.encode("utf-8")).hexdigest()[:32]
    now_ts = datetime.now(timezone.utc).isoformat()
    replay_receipt = {
        "receipt_id": "rr-test-1234",
        "evidence_set_digest": "digest-valid-1234",
    }

    node_payload = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "snapshot_id": snap2_id,
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "recorded_at": now_ts,
        "published_at": now_ts,
        "evidence_cutoff_at": None,
        "observation_window": None,
        "crop_cycle_id": "cycle-test",
        "supersedes_snapshot_id": snap1_id,
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "crop_posterior_lineage": None,
        "crop_worldline_event_id": None,
        "phenology_worldline_event_id": None,
        "crop_evidence_ledger_hash": None,
        "crop_influence_manifest_hash": None,
        "scientific_result": {"content_hash": "sci-2"},
        "scientific_content_hash": "sci-2",
        "bitemporal_replay_receipt": replay_receipt,
        "evidence_set_digest": "digest-valid-1234",
    }
    hashable_node = {k: v for k, v in node_payload.items() if not k.endswith("_ref")}
    node_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_node)).hexdigest()
    node_payload["node_hash"] = node_hash

    frontend_payload = {
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "publication_authority": "DIAGNOSTIC_ONLY",
        "publication_status": "READY_DIAGNOSTIC_ONLY",
        "surfaces": [],
        "intelligence_snapshot_id": snap2_id,
    }
    # Publication lacks bitemporal_replay_receipt
    pub_payload = {
        "contract_version": plot_snapshot_store.PLOT_PUBLICATION_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap2_id,
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "node_ref": f"nodes/{snap2_id}.json",
        "node_hash": node_hash,
        "frontend_payload": frontend_payload,
        "published_at": now_ts,
        "evidence_cutoff_at": None,
        "observation_window": None,
        "crop_cycle_id": "cycle-test",
        "recorded_at": now_ts,
    }
    hashable_pub = {k: v for k, v in pub_payload.items() if not k.endswith("_ref")}
    pub_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_pub)).hexdigest()
    pub_payload["publication_hash"] = pub_hash

    rcpt_payload = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_RECEIPT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap2_id,
        "node_ref": f"nodes/{snap2_id}.json",
        "node_hash": node_hash,
        "source_node_job_id": job2_id,
        "source_node_manifest_hash": "manifest-hash-2",
        "job_id": job2_id,
        "manifest_hash": "manifest-hash-2",
        "frontend_publication_ref": f"publications/{safe_job2}.json",
        "frontend_publication_hash": pub_hash,
        "bitemporal_replay_receipt": replay_receipt,
        "evidence_set_digest": "digest-valid-1234",
        "equivalence_reason": "scientific_content_hash_equivalent",
        "recorded_at": now_ts,
    }
    hashable_rcpt = {k: v for k, v in rcpt_payload.items() if not k.endswith("_ref")}
    rcpt_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_rcpt)).hexdigest()
    rcpt_payload["receipt_hash"] = rcpt_hash

    (directory / "nodes" / f"{snap2_id}.json").write_bytes(plot_snapshot_store._json_bytes(node_payload))
    (directory / "publications" / f"{safe_job2}.json").write_bytes(plot_snapshot_store._json_bytes(pub_payload))
    (directory / "receipts" / f"{safe_job2}.json").write_bytes(plot_snapshot_store._json_bytes(rcpt_payload))

    commit2_rec = {
        "commit_seq": 2,
        "snapshot_id": snap2_id,
        "node_hash": node_hash,
        "frontend_publication_hash": pub_hash,
        "publication_receipt_hash": rcpt_hash,
        "publication_job_id": job2_id,
        "committed_at": now_ts,
        "parent_commit_hash": parent_hash,
    }
    commit2_rec["commit_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes({k: v for k, v in commit2_rec.items() if k != "commit_hash"})).hexdigest()
    with open(commits_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(commit2_rec) + "\n")

    with plot_snapshot_store._plot_publication_lock(directory):
        rec_res = plot_snapshot_store.reconcile_publication_ledger_and_head(directory, ns)

    assert rec_res["snapshot_id"] == snap1_id
    assert head_file.read_bytes() == head1_bytes
    assert plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True) is None


def test_gate_a_same_publication_retry_fails_closed_on_deleted_or_empty_ledger(tmp_path):
    """Gate A: Verify same-publication retry strictly fails closed on missing, empty, or corrupt ledger."""
    plot_id = f"parcel-gate-a-{int(time.time() * 1000)}"
    tenant_id = "tenant-gate-a"
    farm_id = "farm-gate-a"
    geom_hash = "geom-gate-a"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)

    states = {"root_zone_moisture": 0.42, "canopy_vigor": 0.75}
    sigmas = {"root_zone_moisture": 0.02, "canopy_vigor": 0.03}

    # 1. First publish succeeds
    published = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-gate-a", states, sigmas)
    snap_id = published["snapshot_id"]
    commits_file = directory / "commits.jsonl"
    assert commits_file.exists()

    # 2. Identical re-publication succeeds idempotently when ledger is intact
    republished = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-gate-a", states, sigmas)
    assert republished["snapshot_id"] == snap_id

    # 3. Delete commits.jsonl -> identical re-publication must fail closed (ValueError)
    commits_file.unlink()
    with pytest.raises(ValueError, match="Cannot publish snapshot"):
        _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-gate-a", states, sigmas)

    # 4. Empty commits.jsonl -> identical re-publication must fail closed (ValueError)
    commits_file.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Cannot publish snapshot"):
        _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-gate-a", states, sigmas)

    # 5. Corrupted commits.jsonl -> identical re-publication must fail closed (ValueError)
    commits_file.write_text("{bad json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Cannot publish snapshot: commit ledger is corrupted"):
        _publish_candidate(tenant_id, farm_id, plot_id, geom_hash, "job-gate-a", states, sigmas)


def test_gate_b_geometry_filtering_after_recovery_fails_closed(tmp_path):
    """Gate B: Verify geometry filtering is re-evaluated after reconciliation and fails closed on mismatch."""
    plot_id = f"parcel-gate-b-{int(time.time() * 1000)}"
    tenant_id = "tenant-gate-b"
    farm_id = "farm-gate-b"
    geom_hash_1 = "geom-gate-b-1"
    geom_hash_2 = "geom-gate-b-2"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)

    states = {"root_zone_moisture": 0.40, "canopy_vigor": 0.65}
    sigmas = {"root_zone_moisture": 0.02, "canopy_vigor": 0.03}

    # 1. Publish snapshot 1 under geom_hash_1
    published1 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash_1, "job-b-1", states, sigmas)
    assert plot_snapshot_store.load_latest_plot_snapshot(ns, geometry_hash=geom_hash_1) is not None

    # 2. Publish snapshot 2 under geom_hash_2
    published2 = _publish_candidate(tenant_id, farm_id, plot_id, geom_hash_2, "job-b-2", states, sigmas)

    # 3. Requesting geom_hash_1 when latest is geom_hash_2 must return None (fail closed)
    res_mismatch = plot_snapshot_store.load_latest_plot_snapshot(ns, geometry_hash=geom_hash_1, force_verify=True)
    assert res_mismatch is None

    # 4. Requesting geom_hash_2 must succeed
    res_match = plot_snapshot_store.load_latest_plot_snapshot(ns, geometry_hash=geom_hash_2, force_verify=True)
    assert res_match is not None
    assert res_match["snapshot_id"] == published2["snapshot_id"]


def test_gate_c_certified_numerical_record_parity_and_conflict_rejection(tmp_path):
    """Gate C: Verify writer/reader parity and conflict rejection for certified numerical records."""
    plot_id = f"parcel-gate-c-{int(time.time() * 1000)}"
    tenant_id = "tenant-gate-c"
    farm_id = "farm-gate-c"
    geom_hash = "geom-gate-c"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)

    states = {"root_zone_moisture": 0.45, "canopy_vigor": 0.72}
    sigmas = {"root_zone_moisture": 0.02, "canopy_vigor": 0.03}
    num_hash = compute_asmae_vector_numerical_hash(states, sigmas)
    num_rec = {
        "states": states,
        "sigmas": sigmas,
        "numerical_vector_hash": num_hash,
    }

    # Construct payload with record ONLY in asmae_result (scientific_result)
    fe_payload = {
        "version": SURFACES_SCHEMA_VERSION,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "publication_authority": "CERTIFIED_NUMERICAL",
        "claims_numerical_authority": True,
        "publication_status": "VALID_NORMAL",
        "surfaces": [],
        "intelligence_snapshot_id": "L10-GATE-C-01",
        "asmae_proof": {
            "proof_id": "proof-c-1",
            "numerical_vector_hash": num_hash,
        },
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": "lineage-c",
            "crop_worldline_event_id": "event-crop-c",
            "phenology_worldline_event_id": "event-pheno-c",
            "asmae_posterior_vector_hash": num_hash,
        },
    }
    sci_result = {
        "snapshot_id": "L10-GATE-C-01",
        "content_hash": "sci-hash-c",
        "crop_posterior_lineage": "lineage-c",
        "crop_worldline_event_id": "event-crop-c",
        "phenology_worldline_event_id": "event-pheno-c",
        "asmae_posterior_numerical_record": num_rec,
        "asmae_numerical_digest": num_hash,
        "publication_authority": "CERTIFIED_NUMERICAL",
        "claims_numerical_authority": True,
    }

    # 1. Positive control: publication succeeds and copies num_rec into frontend payload
    head = plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        snapshot_id="L10-GATE-C-01",
        frontend_payload=fe_payload,
        asmae_result=sci_result,
        job_id="job-gate-c-1",
        manifest_hash="manifest-c-1",
        geometry_hash=geom_hash,
        publication_authority="CERTIFIED_NUMERICAL",
        snapshot_kind="layer10_terminal",
    )
    assert head["snapshot_id"] == "L10-GATE-C-01"

    # Both latest and exact readers certify the numerical authority
    latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert latest is not None
    assert latest["publication_authority"] == "CERTIFIED_NUMERICAL"
    assert latest["validation"]["numericalBindingValid"] is True

    exact = plot_snapshot_store.load_and_validate_plot_snapshot_by_id("L10-GATE-C-01", namespace=ns)
    assert exact is not None
    assert exact["publication_authority"] == "CERTIFIED_NUMERICAL"
    assert exact["validation"]["numericalBindingValid"] is True

    # 2. Negative control: conflicting numerical records reject publication
    conflicting_num_rec = copy.deepcopy(num_rec)
    conflicting_num_rec["numerical_vector_hash"] = "0" * 64
    fe_payload_conflict = copy.deepcopy(fe_payload)
    fe_payload_conflict["intelligence_snapshot_id"] = "L10-GATE-C-02"
    fe_payload_conflict["asmae_posterior_numerical_record"] = conflicting_num_rec
    sci_result_conflict = copy.deepcopy(sci_result)
    sci_result_conflict["snapshot_id"] = "L10-GATE-C-02"

    with pytest.raises(ValueError, match="Contradictory certified numerical records"):
        plot_snapshot_store.publish_canonical_plot_snapshot(
            namespace=ns,
            snapshot_id="L10-GATE-C-02",
            frontend_payload=fe_payload_conflict,
            asmae_result=sci_result_conflict,
            job_id="job-gate-c-2",
            manifest_hash="manifest-c-2",
            geometry_hash=geom_hash,
            publication_authority="CERTIFIED_NUMERICAL",
            snapshot_kind="layer10_terminal",
        )


def test_gate_f_exact_history_resolves_committed_publication_job(tmp_path):
    """Gate F: Exact reader resolves committed publication_job_id from commits.jsonl."""
    plot_id = f"parcel-gate-f-{int(time.time() * 1000)}"
    tenant_id = "tenant-gate-f"
    farm_id = "farm-gate-f"
    geom_hash = "geom-gate-f"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)
    node_dir = directory / "nodes"
    pub_dir = directory / "publications"
    rcpt_dir = directory / "receipts"
    node_dir.mkdir(parents=True, exist_ok=True)
    pub_dir.mkdir(parents=True, exist_ok=True)
    rcpt_dir.mkdir(parents=True, exist_ok=True)

    snap_id = f"L10-GATE-F-{uuid.uuid4().hex[:8]}"
    compute_job_id = "job-compute-original-1"
    pub_job_id = "job-publish-committed"
    safe_pub_job = hashlib.sha256(pub_job_id.encode("utf-8")).hexdigest()[:32]
    now_ts = datetime.now(timezone.utc).isoformat()

    # Node has job_id = compute_job_id
    node_payload = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "snapshot_id": snap_id,
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "recorded_at": now_ts,
        "published_at": now_ts,
        "evidence_cutoff_at": None,
        "observation_window": None,
        "crop_cycle_id": "cycle-test",
        "job_id": compute_job_id,
        "manifest_hash": "manifest-hash-f",
        "crop_posterior_lineage": None,
        "crop_worldline_event_id": None,
        "phenology_worldline_event_id": None,
        "crop_evidence_ledger_hash": None,
        "crop_influence_manifest_hash": None,
        "scientific_result": {"content_hash": "sci-f"},
        "scientific_content_hash": "sci-f",
    }
    hashable_node = {k: v for k, v in node_payload.items() if not k.endswith("_ref")}
    node_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_node)).hexdigest()
    node_payload["node_hash"] = node_hash

    # Publication has job_id = pub_job_id
    frontend_payload = {
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "publication_authority": "DIAGNOSTIC_ONLY",
        "publication_status": "READY_DIAGNOSTIC_ONLY",
        "surfaces": [],
        "intelligence_snapshot_id": snap_id,
    }
    pub_payload = {
        "contract_version": plot_snapshot_store.PLOT_PUBLICATION_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap_id,
        "job_id": pub_job_id,
        "manifest_hash": "manifest-hash-f",
        "node_ref": f"nodes/{snap_id}.json",
        "node_hash": node_hash,
        "frontend_payload": frontend_payload,
        "published_at": now_ts,
        "evidence_cutoff_at": None,
        "observation_window": None,
        "crop_cycle_id": "cycle-test",
        "recorded_at": now_ts,
    }
    hashable_pub = {k: v for k, v in pub_payload.items() if not k.endswith("_ref")}
    pub_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_pub)).hexdigest()
    pub_payload["publication_hash"] = pub_hash

    # Receipt has job_id = pub_job_id, source_node_job_id = compute_job_id
    rcpt_payload = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_RECEIPT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap_id,
        "node_ref": f"nodes/{snap_id}.json",
        "node_hash": node_hash,
        "source_node_job_id": compute_job_id,
        "source_node_manifest_hash": "manifest-hash-f",
        "job_id": pub_job_id,
        "manifest_hash": "manifest-hash-f",
        "frontend_publication_ref": f"publications/{safe_pub_job}.json",
        "frontend_publication_hash": pub_hash,
        "equivalence_reason": "scientific_content_hash_equivalent",
        "recorded_at": now_ts,
    }
    hashable_rcpt = {k: v for k, v in rcpt_payload.items() if not k.endswith("_ref")}
    rcpt_hash = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_rcpt)).hexdigest()
    rcpt_payload["receipt_hash"] = rcpt_hash

    # Write files to disk
    (node_dir / f"{snap_id}.json").write_bytes(plot_snapshot_store._json_bytes(node_payload))
    (pub_dir / f"{safe_pub_job}.json").write_bytes(plot_snapshot_store._json_bytes(pub_payload))
    (rcpt_dir / f"{safe_pub_job}.json").write_bytes(plot_snapshot_store._json_bytes(rcpt_payload))

    # Commit record has publication_job_id = pub_job_id
    commit_rec = {
        "commit_seq": 1,
        "snapshot_id": snap_id,
        "node_hash": node_hash,
        "frontend_publication_hash": pub_hash,
        "publication_receipt_hash": rcpt_hash,
        "publication_job_id": pub_job_id,
        "committed_at": now_ts,
        "parent_commit_hash": "0" * 64,
    }
    commit_rec["commit_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes({k: v for k, v in commit_rec.items() if k != "commit_hash"})).hexdigest()
    commits_file = directory / "commits.jsonl"
    commits_file.write_text(json.dumps(commit_rec) + "\n", encoding="utf-8")

    # Head points to this commit
    head = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap_id,
        "node_ref": str(node_dir / f"{snap_id}.json"),
        "node_hash": node_hash,
        "publication_job_id": pub_job_id,
        "publication_manifest_hash": "manifest-hash-f",
        "publication_receipt_ref": str(rcpt_dir / f"{safe_pub_job}.json"),
        "publication_receipt_hash": rcpt_hash,
        "frontend_publication_ref": str(pub_dir / f"{safe_pub_job}.json"),
        "frontend_publication_hash": pub_hash,
        "published_at": now_ts,
        "commit_seq": 1,
        "commit_hash": commit_rec["commit_hash"],
    }
    (directory / "head.json").write_bytes(plot_snapshot_store._json_bytes(head))

    # Exact lookup succeeds by resolving publication_job_id from commits.jsonl
    exact = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap_id, namespace=ns)
    assert exact is not None
    assert exact["snapshot_id"] == snap_id


def test_gate_g_commit_ledger_parser_type_safety_on_non_string_hashes(tmp_path):
    """Gate G: validate_publication_commit_ledger strictly validates hash types before set hashing."""
    plot_id = f"parcel-gate-g-{int(time.time() * 1000)}"
    tenant_id = "tenant-gate-g"
    farm_id = "farm-gate-g"
    ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    directory = plot_snapshot_store._plot_dir(ns)
    directory.mkdir(parents=True, exist_ok=True)
    commits_file = directory / "commits.jsonl"

    # Line with dict as publication_receipt_hash
    bad_line = {
        "commit_seq": 1,
        "snapshot_id": "snap-bad",
        "parent_commit_hash": "0" * 64,
        "node_hash": "a" * 64,
        "frontend_publication_hash": "b" * 64,
        "publication_receipt_hash": {"nested": "dict"},
        "commit_hash": "c" * 64,
    }
    commits_file.write_text(json.dumps(bad_line) + "\n", encoding="utf-8")

    is_valid, records, err = plot_snapshot_store.validate_publication_commit_ledger(directory)
    assert is_valid is False
    assert records == []
    assert "Invalid publication_receipt_hash at line 1" in err

