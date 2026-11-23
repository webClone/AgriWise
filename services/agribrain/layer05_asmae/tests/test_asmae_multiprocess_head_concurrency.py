"""Multiprocess integration tests for atomic plot head supersession and race condition protection."""

from __future__ import annotations

import concurrent.futures
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer05_asmae import plot_snapshot_store, snapshot_store
from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash


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
