"""
Akaloris / AgriBrain — Package P2-B Cryptographic Temporal Binding & Cutoff Tests

Verifies:
1. Proof that missing scientific evidence cutoff is never silently replaced with publication time.
2. Proof that mutating any head temporal field (published_at, evidence_cutoff_at, observation_window)
   causes canonical publication validation failure (temporalBindingValid == False, bindingValid == False).
"""

import json
from pathlib import Path
from unittest.mock import patch
import pytest

from services.agribrain.layer05_asmae.plot_snapshot_store import (
    PlotNamespace,
    publish_canonical_plot_snapshot,
    load_latest_plot_snapshot,
    _head_path,
    _CANONICAL_SNAPSHOT_CACHE,
    _SNAPSHOT_CACHE_LOCK,
)


@pytest.fixture(autouse=True)
def clear_cache():
    with _SNAPSHOT_CACHE_LOCK:
        _CANONICAL_SNAPSHOT_CACHE.clear()
    yield
    with _SNAPSHOT_CACHE_LOCK:
        _CANONICAL_SNAPSHOT_CACHE.clear()


def _make_asmae_test_payload(snapshot_id: str, plot_id: str, cutoff=None, window=None):
    asmae_result = {
        "status": "OK",
        "plot_id": plot_id,
        "snapshot_id": snapshot_id,
        "crop_posterior_lineage": f"crop-{snapshot_id}",
        "crop_worldline_event_id": f"worldline-{snapshot_id}",
        "phenology_worldline_event_id": f"pheno-{snapshot_id}",
    }
    if cutoff is not None:
        asmae_result["evidence_cutoff_at"] = cutoff
    if window is not None:
        asmae_result["observation_window"] = window

    frontend_payload = {
        "status": "fresh",
        "available": True,
        "intelligence_snapshot_id": snapshot_id,
        "plot_id": plot_id,
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": f"crop-{snapshot_id}",
            "crop_worldline_event_id": f"worldline-{snapshot_id}",
            "phenology_worldline_event_id": f"pheno-{snapshot_id}",
        },
        "surfaces": [
            {
                "surface_type": "WATER_ASMAE_CANOPY_WATER",
                "surface_id": "surf-w1",
                "mode": "water_stress",
                "raster_id": "rast-w1",
            }
        ],
        "surface_schema_version": "v92.3",
    }
    if cutoff is not None:
        frontend_payload["evidence_cutoff_at"] = cutoff
    if window is not None:
        frontend_payload["observation_window"] = window

    return asmae_result, frontend_payload


def test_missing_evidence_cutoff_not_replaced_with_publication_time(tmp_path: Path):
    """Scientific Provenance Guarantee:
    If a publication has no validated evidence cutoff or observation window,
    evidence_cutoff_at and observation_window must remain None, NEVER fabricated from published_at.
    """
    namespace = PlotNamespace("tenant-test", "farm-test", "plot-temporal-01")
    snapshot_id = "ASMAE-SNAPSHOT-scientific-provenance-01"

    asmae_result, frontend_payload = _make_asmae_test_payload(
        snapshot_id, "plot-temporal-01", cutoff=None, window=None
    )

    with patch("services.agribrain.layer05_asmae.plot_snapshot_store.PLOT_SNAPSHOT_ROOT", tmp_path):
        published = publish_canonical_plot_snapshot(
            namespace=namespace,
            geometry_hash="geometry-hash-01",
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend_payload,
            job_id="job-provenance-01",
            manifest_hash="manifest-hash-01",
            execution_identity={"worker": "test", "plan": "test"},
        )

        loaded = load_latest_plot_snapshot(namespace, "geometry-hash-01")

    assert loaded is not None
    # Authoritative published_at exists
    assert loaded.get("published_at") is not None
    # But evidence_cutoff_at and observation_window were NOT fabricated
    assert loaded.get("evidence_cutoff_at") is None, "Missing evidence cutoff must remain None"
    assert loaded.get("observation_window") is None, "Missing observation window must remain None"


def test_mutating_head_evidence_cutoff_causes_validation_failure(tmp_path: Path):
    """Integrity Guarantee:
    Tampering with head.json evidence_cutoff_at without re-hashing publication
    causes temporalBindingValid == False and bindingValid == False.
    """
    namespace = PlotNamespace("tenant-test", "farm-test", "plot-temporal-02")
    snapshot_id = "ASMAE-SNAPSHOT-tamper-02"

    cutoff_truth = "2026-10-28T06:00:00Z"
    obs_truth = {"start": "2026-10-20T00:00:00Z", "end": "2026-10-28T06:00:00Z"}

    asmae_result, frontend_payload = _make_asmae_test_payload(
        snapshot_id, "plot-temporal-02", cutoff=cutoff_truth, window=obs_truth
    )

    with patch("services.agribrain.layer05_asmae.plot_snapshot_store.PLOT_SNAPSHOT_ROOT", tmp_path):
        published = publish_canonical_plot_snapshot(
            namespace=namespace,
            geometry_hash="geometry-hash-02",
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend_payload,
            job_id="job-tamper-02",
            manifest_hash="manifest-hash-02",
            execution_identity={"worker": "test", "plan": "test"},
        )

        # Baseline: untampered snapshot validates cleanly
        clean_load = load_latest_plot_snapshot(namespace, "geometry-hash-02")
        assert clean_load["validation"]["temporalBindingValid"] is True
        assert clean_load["validation"]["bindingValid"] is True

        # Clear cache to force disk re-read
        with _SNAPSHOT_CACHE_LOCK:
            _CANONICAL_SNAPSHOT_CACHE.clear()

        # Deliberately tamper with ONLY head.json evidence_cutoff_at (e.g. advancing it to 12:00)
        head_path = _head_path(namespace)
        head_data = json.loads(head_path.read_text(encoding="utf-8"))
        head_data["evidence_cutoff_at"] = "2026-10-28T12:00:00Z"
        head_path.write_text(json.dumps(head_data), encoding="utf-8")

        # Re-load: must fail temporal binding validation!
        tampered_load = load_latest_plot_snapshot(namespace, "geometry-hash-02")
        assert tampered_load is not None
        assert tampered_load["validation"]["temporalBindingValid"] is False, "Tampered head cutoff must fail temporal binding"
        assert tampered_load["validation"]["bindingValid"] is False, "Tampered head cutoff must fail overall binding"


def test_mutating_head_published_at_causes_validation_failure(tmp_path: Path):
    """Integrity Guarantee:
    Tampering with head.json published_at causes validation failure.
    """
    namespace = PlotNamespace("tenant-test", "farm-test", "plot-temporal-03")
    snapshot_id = "ASMAE-SNAPSHOT-tamper-03"

    asmae_result, frontend_payload = _make_asmae_test_payload(
        snapshot_id, "plot-temporal-03", cutoff="2026-10-28T06:00:00Z", window={"start": "2026-10-20T00:00:00Z", "end": "2026-10-28T06:00:00Z"}
    )

    with patch("services.agribrain.layer05_asmae.plot_snapshot_store.PLOT_SNAPSHOT_ROOT", tmp_path):
        published = publish_canonical_plot_snapshot(
            namespace=namespace,
            geometry_hash="geometry-hash-03",
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend_payload,
            job_id="job-tamper-03",
            manifest_hash="manifest-hash-03",
            execution_identity={"worker": "test", "plan": "test"},
        )

        with _SNAPSHOT_CACHE_LOCK:
            _CANONICAL_SNAPSHOT_CACHE.clear()

        # Tamper with head.json published_at
        head_path = _head_path(namespace)
        head_data = json.loads(head_path.read_text(encoding="utf-8"))
        head_data["published_at"] = "1999-01-01T00:00:00Z"
        head_path.write_text(json.dumps(head_data), encoding="utf-8")

        tampered_load = load_latest_plot_snapshot(namespace, "geometry-hash-03")
        assert tampered_load["validation"]["temporalBindingValid"] is False
        assert tampered_load["validation"]["bindingValid"] is False


def test_missing_evidence_cutoff_with_observation_window_remains_none(tmp_path: Path):
    """Scientific Provenance Guarantee:
    An absent evidence cutoff must NEVER be inferred from an observation-window end.
    A requested data window is not automatically a verified evidence-admission cutoff.
    """
    namespace = PlotNamespace("tenant-test", "farm-test", "plot-temporal-04")
    snapshot_id = "ASMAE-SNAPSHOT-window-no-cutoff-04"
    obs_truth = {"start": "2026-10-01T00:00:00Z", "end": "2026-10-28T00:00:00Z"}

    asmae_result, frontend_payload = _make_asmae_test_payload(
        snapshot_id, "plot-temporal-04", cutoff=None, window=obs_truth
    )

    with patch("services.agribrain.layer05_asmae.plot_snapshot_store.PLOT_SNAPSHOT_ROOT", tmp_path):
        published = publish_canonical_plot_snapshot(
            namespace=namespace,
            geometry_hash="geometry-hash-04",
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend_payload,
            job_id="job-window-no-cutoff-04",
            manifest_hash="manifest-hash-04",
            execution_identity={"worker": "test", "plan": "test"},
        )

        loaded = load_latest_plot_snapshot(namespace, "geometry-hash-04")

    assert loaded is not None
    assert loaded.get("observation_window") == obs_truth
    # Even though observation_window exists with an 'end', evidence_cutoff_at MUST remain None
    assert loaded.get("evidence_cutoff_at") is None, "Missing evidence cutoff must NOT be inferred from observation_window['end']"


def test_deleting_head_temporal_fields_causes_validation_failure(tmp_path: Path):
    """Integrity Guarantee:
    Deleting head.json temporal fields (published_at, evidence_cutoff_at, observation_window)
    causes temporalBindingValid == False and bindingValid == False.
    """
    namespace = PlotNamespace("tenant-test", "farm-test", "plot-temporal-05")
    snapshot_id = "ASMAE-SNAPSHOT-tamper-deletion-05"

    cutoff_truth = "2026-10-28T06:00:00Z"
    obs_truth = {"start": "2026-10-20T00:00:00Z", "end": "2026-10-28T06:00:00Z"}

    asmae_result, frontend_payload = _make_asmae_test_payload(
        snapshot_id, "plot-temporal-05", cutoff=cutoff_truth, window=obs_truth
    )

    with patch("services.agribrain.layer05_asmae.plot_snapshot_store.PLOT_SNAPSHOT_ROOT", tmp_path):
        published = publish_canonical_plot_snapshot(
            namespace=namespace,
            geometry_hash="geometry-hash-05",
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend_payload,
            job_id="job-tamper-del-05",
            manifest_hash="manifest-hash-05",
            execution_identity={"worker": "test", "plan": "test"},
        )

        # Case A: Delete evidence_cutoff_at
        with _SNAPSHOT_CACHE_LOCK:
            _CANONICAL_SNAPSHOT_CACHE.clear()
        head_path = _head_path(namespace)
        orig_head_text = head_path.read_text(encoding="utf-8")
        head_data = json.loads(orig_head_text)
        del head_data["evidence_cutoff_at"]
        head_path.write_text(json.dumps(head_data), encoding="utf-8")

        load_del_cutoff = load_latest_plot_snapshot(namespace, "geometry-hash-05")
        assert load_del_cutoff["validation"]["temporalBindingValid"] is False, "Deleted head cutoff must fail temporal binding"

        # Case B: Delete observation_window
        with _SNAPSHOT_CACHE_LOCK:
            _CANONICAL_SNAPSHOT_CACHE.clear()
        head_data = json.loads(orig_head_text)
        del head_data["observation_window"]
        head_path.write_text(json.dumps(head_data), encoding="utf-8")

        load_del_window = load_latest_plot_snapshot(namespace, "geometry-hash-05")
        assert load_del_window["validation"]["temporalBindingValid"] is False, "Deleted head observation_window must fail temporal binding"

        # Case C: Mutate observation_window bounds
        with _SNAPSHOT_CACHE_LOCK:
            _CANONICAL_SNAPSHOT_CACHE.clear()
        head_data = json.loads(orig_head_text)
        head_data["observation_window"] = {"start": "2020-01-01T00:00:00Z", "end": "2020-01-02T00:00:00Z"}
        head_path.write_text(json.dumps(head_data), encoding="utf-8")

        load_mut_window = load_latest_plot_snapshot(namespace, "geometry-hash-05")
        assert load_mut_window["validation"]["temporalBindingValid"] is False, "Mutated head observation_window must fail temporal binding"


def test_crop_cycle_id_propagated_to_published_snapshot_and_head(tmp_path: Path):
    """Scientific Context Guarantee:
    When a crop_cycle_id is present in the publication context, it is explicitly published
    into the immutable envelope, the frontend publication payload, and the plot head.
    """
    namespace = PlotNamespace("tenant-test", "farm-test", "plot-crop-cycle-01")
    snapshot_id = "ASMAE-SNAPSHOT-cycle-prop-01"

    asmae_result, frontend_payload = _make_asmae_test_payload(
        snapshot_id, "plot-crop-cycle-01", cutoff="2026-10-28T06:00:00Z", window={"start": "2026-10-20T00:00:00Z", "end": "2026-10-28T06:00:00Z"}
    )
    frontend_payload["crop_cycle_id"] = "cycle-2026-autumn"

    with patch("services.agribrain.layer05_asmae.plot_snapshot_store.PLOT_SNAPSHOT_ROOT", tmp_path):
        published = publish_canonical_plot_snapshot(
            namespace=namespace,
            geometry_hash="geometry-hash-cycle",
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend_payload,
            job_id="job-cycle-prop-01",
            manifest_hash="manifest-hash-cycle",
            execution_identity={"worker": "test", "plan": "test", "crop_cycle_id": "cycle-2026-autumn"},
        )

        loaded = load_latest_plot_snapshot(namespace, "geometry-hash-cycle")

    assert loaded is not None
    assert loaded.get("crop_cycle_id") == "cycle-2026-autumn"
    assert loaded.get("frontend_payload", {}).get("crop_cycle_id") == "cycle-2026-autumn"
