"""Multiprocess integration tests for atomic plot head supersession and race condition protection."""

from __future__ import annotations

import concurrent.futures
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
from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash


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
            "crop_posterior_lineage": f"lineage-{job_id}",
            "crop_worldline_event_id": f"evt-{job_id}",
            "phenology_worldline_event_id": f"evt-p{job_id}",
        },
        "surface_pack": [
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

    # B) F01: Missing commits.jsonl must NOT admit orphan candidate
    commits_file.unlink()
    assert not commits_file.exists()
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(orphan_snap_id, namespace=ns) is None

    # But head snap1_id remains valid via legacy head rule
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is not None

    # C) F01: Empty commits.jsonl must NOT admit orphan candidate
    commits_file.write_text("", encoding="utf-8")
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(orphan_snap_id, namespace=ns) is None

    # D) F03: Malformed JSON in commits.jsonl fails closed
    commits_file.write_text("{malformed json line", encoding="utf-8")
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is None
    assert plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True) is None

    # E) F03: Tampered commit_hash fails closed
    rec = json.loads(original_commits_text.strip())
    rec["commit_hash"] = "0" * 64
    commits_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is None

    # F) F03: Broken parent link fails closed
    rec = json.loads(original_commits_text.strip())
    rec["parent_commit_hash"] = "f" * 64
    commits_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is None

    # G) F03: Duplicate snapshot_id fails closed
    commits_file.write_text(original_commits_text + original_commits_text, encoding="utf-8")
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is None

    # Restore original commits.jsonl -> healthy retrieval resumes
    commits_file.write_text(original_commits_text, encoding="utf-8")
    assert plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns) is not None


def test_crash_recovery_between_ledger_append_and_head_update(tmp_path):
    """P1 (F02): Verify deterministic crash recovery when writer dies between ledger fsync and head update.

    Simulates process termination after appending and fsyncing commits.jsonl, but before atomically replacing head.json.
    Verifies:
    1. Latest reader deterministically reconciles head.json to the validated ledger tip.
    2. Exact reader successfully retrieves the new snapshot.
    3. Latest and exact readers agree 100% on the committed snapshot.
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

    # 2. Stage Commit 2 artifacts on disk
    snap2_id = f"L10-CRASH2-{uuid.uuid4().hex[:8]}"
    job_id_2 = f"job-crash-2-{snap2_id}"
    safe_job_id_2 = hashlib.sha256(job_id_2.encode("utf-8")).hexdigest()[:32]
    node_dir = directory / "nodes"
    pub_dir = directory / "publications"
    rcpt_dir = directory / "receipts"

    node2 = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap2_id,
        "supersedes_snapshot_id": snap1_id,
        "job_id": job_id_2,
        "manifest_hash": "manifest-hash-crash-2",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    hashable_node2 = {k: v for k, v in node2.items() if not k.endswith("_ref")}
    node2["node_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_node2)).hexdigest()
    (node_dir / f"{snap2_id}.json").write_bytes(plot_snapshot_store._json_bytes(node2))

    pub2 = {
        "contract_version": plot_snapshot_store.PLOT_PUBLICATION_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap2_id,
        "job_id": job_id_2,
        "manifest_hash": "manifest-hash-crash-2",
        "node_ref": str(node_dir / f"{snap2_id}.json"),
        "node_hash": node2["node_hash"],
        "frontend_payload": {"surfaces": [], "version": "v1"},
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    hashable_pub2 = {k: v for k, v in pub2.items() if not k.endswith("_ref")}
    pub2["publication_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_pub2)).hexdigest()
    (pub_dir / f"{safe_job_id_2}.json").write_bytes(plot_snapshot_store._json_bytes(pub2))

    rcpt2 = {
        "contract_version": plot_snapshot_store.PLOT_SNAPSHOT_RECEIPT_CONTRACT_VERSION,
        "snapshot_kind": "layer10_terminal",
        "publication_authority": "DIAGNOSTIC_ONLY",
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "plot_id": plot_id,
        "geometry_hash": geom_hash,
        "snapshot_id": snap2_id,
        "job_id": job_id_2,
        "manifest_hash": "manifest-hash-crash-2",
        "node_ref": str(node_dir / f"{snap2_id}.json"),
        "node_hash": node2["node_hash"],
        "frontend_publication_hash": pub2["publication_hash"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    hashable_rcpt2 = {k: v for k, v in rcpt2.items() if not k.endswith("_ref")}
    rcpt2["receipt_hash"] = hashlib.sha256(plot_snapshot_store._json_bytes(hashable_rcpt2)).hexdigest()
    (rcpt_dir / f"{safe_job_id_2}.json").write_bytes(plot_snapshot_store._json_bytes(rcpt2))

    # 3. Simulate crash: Append Commit 2 to commits.jsonl, but leave head.json pointing to Commit 1
    commits_file = directory / "commits.jsonl"
    lines = [json.loads(l) for l in commits_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    parent_hash = lines[-1]["commit_hash"]
    commit2_record = {
        "commit_seq": 2,
        "snapshot_id": snap2_id,
        "node_hash": node2["node_hash"],
        "frontend_publication_hash": pub2["publication_hash"],
        "publication_receipt_hash": rcpt2["receipt_hash"],
        "publication_job_id": job_id_2,
        "committed_at": datetime.now(timezone.utc).isoformat(),
        "parent_commit_hash": parent_hash,
    }
    commit2_hash = hashlib.sha256(plot_snapshot_store._json_bytes({k: v for k, v in commit2_record.items() if k != "commit_hash"})).hexdigest()
    commit2_record["commit_hash"] = commit2_hash

    with open(commits_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(commit2_record, separators=(",", ":")) + "\n")
        f.flush()
        os.fsync(f.fileno())

    # Verify state of disk before recovery: head still points to snap1, but ledger has snap2
    raw_head = plot_snapshot_store._read(plot_snapshot_store._head_path(ns))
    assert raw_head["snapshot_id"] == snap1_id
    assert raw_head["commit_seq"] == 1

    # 4. In a fresh read, call load_latest_plot_snapshot -> triggers deterministic reconciliation
    reconciled_latest = plot_snapshot_store.load_latest_plot_snapshot(ns, force_verify=True)
    assert reconciled_latest is not None
    assert reconciled_latest["snapshot_id"] == snap2_id, "Latest reader must deterministically reconcile to ledger tip"

    # 5. Exact retrieval for snap2_id succeeds and agrees with latest reader
    exact_snap2 = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap2_id, namespace=ns)
    assert exact_snap2 is not None
    assert exact_snap2["snapshot_id"] == snap2_id

    # 6. Historical retrieval for snap1_id still succeeds
    exact_snap1 = plot_snapshot_store.load_and_validate_plot_snapshot_by_id(snap1_id, namespace=ns)
    assert exact_snap1 is not None
    assert exact_snap1["snapshot_id"] == snap1_id


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

