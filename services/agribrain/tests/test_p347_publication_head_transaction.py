"""P347-PUB-01: deterministic two-writer publication-head transaction regressions.

Runs the real native file-store publisher and both attachment helpers against
temporary plot storage. Uses threading events to force the previously failing
C→D and E→F schedules; no sleeps or fabricated head documents.

The newer publication MUST remain latest, and prior immutable node, frontend
publication and canonical receipt bytes MUST remain unchanged.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer05_asmae import plot_snapshot_store as store
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.proof_attestation import create_proof_attestation
from services.agribrain.scientific_contracts.prescription_authorization import CANONICAL_PUBLICATION_VALIDATION_FLAGS
from services.agribrain.tests.test_pilot_producer_publication_roots import (
    _make_valid_frontend_payload, SHA,
)

SECRET = "P347-native-test-attestation-key-32bytes"
SCOPE = PlotNamespace("tenant-p347", "farm-p347", "plot-p347")
GEOM = SHA("P347 geometry")
CYCLE = "P347-cycle"
CUTOFF = "2026-10-30T17:44:46Z"
WINDOW = {"start": "2026-10-29T00:00:00Z", "end": "2026-10-30T16:00:00Z"}


@pytest.fixture
def native_store(tmp_path, monkeypatch):
    root = tmp_path / "canonical-plot-store"
    root.mkdir()
    monkeypatch.setattr(store, "PLOT_SNAPSHOT_ROOT", root)
    monkeypatch.setenv("AGRIBRAIN_INTERNAL_SERVICE_SECRET", SECRET)
    with store._SNAPSHOT_CACHE_LOCK:
        store._CANONICAL_SNAPSHOT_CACHE.clear()
    yield root
    with store._SNAPSHOT_CACHE_LOCK:
        store._CANONICAL_SNAPSHOT_CACHE.clear()


def publish(label: str):
    snapshot = "ASMAE-SNAPSHOT-P347-" + label
    science = {
        "status": "OK",
        "plot_id": SCOPE.plot_id,
        "snapshot_id": snapshot,
        "crop_posterior_lineage": "crop-" + snapshot,
        "crop_worldline_event_id": "event-" + snapshot,
        "phenology_worldline_event_id": "phenology-" + snapshot,
        "evidence_cutoff_at": CUTOFF,
        "observation_window": WINDOW,
    }
    payload = _make_valid_frontend_payload(snapshot, SCOPE.plot_id, CYCLE, CUTOFF, WINDOW)
    return store.publish_canonical_plot_snapshot(
        namespace=SCOPE,
        geometry_hash=GEOM,
        snapshot_id=snapshot,
        asmae_result=science,
        frontend_payload=payload,
        job_id="job-P347-" + label,
        manifest_hash=SHA("P347 job " + label),
    )


def attestation_for(head):
    return create_proof_attestation(
        tenant_id=SCOPE.tenant_id,
        farm_id=SCOPE.farm_id,
        plot_id=SCOPE.plot_id,
        geometry_hash=GEOM,
        crop_cycle_id=CYCLE,
        snapshot_id=head["snapshot_id"],
        canonical_publication_receipt_hash=head["publication_receipt_hash"],
        admitted_evidence_root_hash=SHA("P347 admitted"),
        bounded_uncertainty_receipt_hash=SHA("P347 uncertainty"),
        scientific_posterior_hash=SHA("P347 posterior"),
        issued_at="2026-10-30T18:20:00Z",
        secret=SECRET,
    )


def cold_latest():
    with store._SNAPSHOT_CACHE_LOCK:
        store._CANONICAL_SNAPSHOT_CACHE.clear()
    return store.load_latest_plot_snapshot(SCOPE)


def freeze_parents(head):
    return {str(head[name]): open(head[name], "rb").read()
            for name in ("node_ref", "frontend_publication_ref", "publication_receipt_ref")}


def assert_parents_unchanged(frozen):
    for path, original in frozen.items():
        with open(path, "rb") as source:
            assert source.read() == original


def _race(attacher, publisher, pause_atomic, monkeypatch):
    """An attachment pauses while holding the plot lock; publisher runs concurrently."""
    original = store._atomic
    paused, release, publisher_started = (threading.Event() for _ in range(3))

    def intercepted(path, payload):
        return pause_atomic(original, path, payload, paused, release)

    monkeypatch.setattr(store, "_atomic", intercepted)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_attach = pool.submit(attacher)
        try:
            assert paused.wait(10), "Attachment never reached the deterministic pause point"

            def publish_concurrently():
                publisher_started.set()
                return publisher()

            future_publish = pool.submit(publish_concurrently)
            assert publisher_started.wait(5), "Publisher thread did not start"
            # The publication must await the same plot-scoped transaction.
            assert not future_publish.done(), "Concurrent publisher bypassed the plot transaction"
        finally:
            release.set()
        result_attach = future_attach.result(timeout=20)
        result_publish = future_publish.result(timeout=20)
    monkeypatch.setattr(store, "_atomic", original)
    return result_attach, result_publish


def test_signed_attachment_cannot_restore_C_after_D_publishes(native_store, monkeypatch):
    old = publish("C")
    parents = freeze_parents(old)
    att = attestation_for(old)

    def pause_after_child_write(original, path, payload, paused, release):
        result = original(path, payload)
        if path.parent.name == "attestations" and not paused.is_set():
            paused.set()
            assert release.wait(15), "Timed out releasing signed attachment pause"
        return result

    attached, newer = _race(
        lambda: store.attach_canonical_proof_attestation(SCOPE, att, secret=SECRET),
        lambda: publish("D"),
        pause_after_child_write, monkeypatch,
    )
    assert attached["snapshot_id"] == old["snapshot_id"]
    assert newer["snapshot_id"] == "ASMAE-SNAPSHOT-P347-D"
    latest = cold_latest()
    assert latest["snapshot_id"] == newer["snapshot_id"]
    assert latest["publication_receipt_hash"] == newer["publication_receipt_hash"]
    assert latest.get("proof_attestation_valid") is not True  # No forged carry-over
    assert all(latest["validation"][k] is True for k in CANONICAL_PUBLICATION_VALIDATION_FLAGS)
    assert_parents_unchanged(parents)


def test_unsigned_attachment_cannot_restore_E_after_F_publishes(native_store, monkeypatch):
    old = publish("E")
    att = attestation_for(old)
    store.attach_canonical_proof_attestation(SCOPE, att, secret=SECRET)
    parents = freeze_parents(old)
    target_head_path = store._head_path(SCOPE)

    def pause_before_old_head_replace(original, path, payload, paused, release):
        if path == target_head_path and payload.get("snapshot_id") == old["snapshot_id"] and not paused.is_set():
            paused.set()
            assert release.wait(15), "Timed out releasing unsigned attachment pause"
        return original(path, payload)

    attached, newer = _race(
        lambda: store.attach_canonical_proof_roots(
            SCOPE, scientific_posterior_hash=att.scientific_posterior_hash,
        ),
        lambda: publish("F"),
        pause_before_old_head_replace, monkeypatch,
    )
    assert attached["snapshot_id"] == old["snapshot_id"]
    assert newer["snapshot_id"] == "ASMAE-SNAPSHOT-P347-F"
    latest = cold_latest()
    assert latest["snapshot_id"] == newer["snapshot_id"]
    assert latest["publication_receipt_hash"] == newer["publication_receipt_hash"]
    assert all(latest["validation"][k] is True for k in CANONICAL_PUBLICATION_VALIDATION_FLAGS)
    assert_parents_unchanged(parents)


def test_ordinary_attachment_and_stale_before_start_preserve_new_head(native_store):
    c = publish("ordinary-C")
    immutable = freeze_parents(c)
    signed_c = attestation_for(c)
    store.attach_canonical_proof_attestation(SCOPE, signed_c, secret=SECRET)
    verified = cold_latest()
    assert verified["proof_attestation_valid"] is True
    assert verified["snapshot_id"] == c["snapshot_id"]
    assert_parents_unchanged(immutable)

    d = publish("ordinary-D")
    with pytest.raises(ContractViolation, match="receipt hash mismatch"):
        store.attach_canonical_proof_attestation(SCOPE, signed_c, secret=SECRET)
    latest = cold_latest()
    assert latest["snapshot_id"] == d["snapshot_id"]
    assert latest["publication_receipt_hash"] == d["publication_receipt_hash"]
    assert_parents_unchanged(immutable)


def test_nested_layer10_publish_uses_same_reentrant_plot_transaction(native_store):
    # The lock API is purposefully reentrant because terminal L10 publication
    # delegates into publish_canonical_plot_snapshot. Do not deadlock.
    with store._plot_head_transaction(SCOPE):
        head = publish("nested")
        assert head["snapshot_id"] == "ASMAE-SNAPSHOT-P347-nested"
    assert cold_latest()["snapshot_id"] == head["snapshot_id"]



def test_plot_lock_serializes_real_separate_process(native_store, tmp_path):
    """The OS lock, not only the Python RLock, must fence another process."""
    started = tmp_path / "child-started"
    acquired = tmp_path / "child-acquired"
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from services.agribrain.common.plot_namespace import PlotNamespace\n"
        "from services.agribrain.layer05_asmae import plot_snapshot_store as store\n"
        "store.PLOT_SNAPSHOT_ROOT=Path(sys.argv[1])\n"
        "namespace=PlotNamespace('tenant-p347','farm-p347','plot-p347')\n"
        "Path(sys.argv[2]).write_text('attempted')\n"
        "with store._plot_head_transaction(namespace):\n"
        "    Path(sys.argv[3]).write_text('acquired')\n"
    )
    with store._plot_head_transaction(SCOPE):
        proc = subprocess.Popen(
            [sys.executable, "-c", code, str(native_store), str(started), str(acquired)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline = time.monotonic() + 15
            while not started.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            assert started.exists(), "Child process never reached the lock attempt"
            # Child must not acquire while the parent holds the same plot lock.
            # Give a short scheduling window after it explicitly signalled entry.
            time.sleep(0.15)
            assert not acquired.exists(), "Different process bypassed plot head file lock"
        finally:
            # The parent lock exits before waiting for the child below.
            pass
    try:
        output, err = proc.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise
    assert proc.returncode == 0, (output, err)
    assert acquired.read_text() == "acquired"
