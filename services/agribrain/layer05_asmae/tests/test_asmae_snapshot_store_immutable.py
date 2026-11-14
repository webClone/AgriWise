from __future__ import annotations

import json
from pathlib import Path

import pytest


def _result(*, plot_id: str = "plot-a", content_hash: str = "content-a"):
    return {
        "plot_id": plot_id,
        "content_hash": content_hash,
        "crop_posterior_lineage": "crop-lineage",
        "crop_worldline_event_id": "crop-event-a",
        "phenology_worldline_event_id": "phenology-event-a",
        "crop_influence_manifest_hash": "manifest-hash",
        "crop_evidence_ledger_hash": "ledger-hash",
        "plot_state_artifact": {"as_of": "2026-08-21T00:00:00+00:00"},
        "raster_maps": {"asmae_vigor": [[0.4]]},
    }


@pytest.fixture
def snapshot_store(tmp_path, monkeypatch):
    from services.agribrain.layer05_asmae import snapshot_store as store

    root = tmp_path / "asmae_snapshots"
    monkeypatch.setattr(store, "SNAPSHOT_DIR", root)
    monkeypatch.setattr(store, "SNAPSHOT_NODE_DIR", root / "nodes")
    return store


def test_publication_returns_immutable_node_and_later_head_cannot_mutate_it(
    snapshot_store,
):
    first = _result(content_hash="content-a")
    first_ref = snapshot_store.publish_latest_snapshot(
        first, context_hash="ctx-a", geometry_hash="geometry-a"
    )
    first_node = snapshot_store._node_path_for(first["snapshot_id"])
    assert first_ref == str(first_node)
    first_contents = first_node.read_text(encoding="utf-8")

    second = _result(content_hash="content-b")
    second_ref = snapshot_store.publish_latest_snapshot(
        second, context_hash="ctx-b", geometry_hash="geometry-a"
    )

    assert second_ref != first_ref
    assert first_node.read_text(encoding="utf-8") == first_contents
    exact_first = snapshot_store.load_snapshot_exact(
        plot_id="plot-a",
        geometry_hash="geometry-a",
        snapshot_ref=first_ref,
    )
    assert exact_first is not None
    assert exact_first["content_hash"] == "content-a"
    assert exact_first["snapshot_ref"] == first_ref
    latest = snapshot_store.load_latest_snapshot("plot-a", "geometry-a")
    assert latest is not None
    assert latest["content_hash"] == "content-b"
    assert latest["snapshot_ref"] == second_ref


def test_existing_immutable_node_is_validated_and_never_overwritten(snapshot_store):
    first = _result()
    ref = snapshot_store.publish_latest_snapshot(
        first, context_hash="ctx-a", geometry_hash="geometry-a"
    )
    node_path = snapshot_store._node_path_for(first["snapshot_id"])
    corrupted = json.loads(node_path.read_text(encoding="utf-8"))
    corrupted["output_content_hash"] = "tampered"
    node_path.write_text(json.dumps(corrupted), encoding="utf-8")

    with pytest.raises(
        snapshot_store.SnapshotIntegrityError,
        match="existing immutable ASMAE snapshot node failed validation",
    ):
        snapshot_store.publish_latest_snapshot(
            _result(), context_hash="ctx-b", geometry_hash="geometry-a"
        )
    assert node_path.read_text(encoding="utf-8") != ""
    assert ref == str(node_path)


def test_exact_loader_rejects_mutable_or_mismatched_identity(snapshot_store):
    result = _result()
    ref = snapshot_store.publish_latest_snapshot(
        result, context_hash="ctx-a", geometry_hash="geometry-a"
    )

    assert snapshot_store.load_snapshot_exact(
        plot_id="plot-a",
        geometry_hash="geometry-b",
        snapshot_ref=ref,
    ) is None
    with pytest.raises(snapshot_store.SnapshotIntegrityError, match="do not agree"):
        snapshot_store.load_snapshot_exact(
            plot_id="plot-a",
            geometry_hash="geometry-a",
            snapshot_ref=ref,
            snapshot_id="ASMAE-SNAPSHOT-not-the-same",
        )
    with pytest.raises(
        snapshot_store.SnapshotIntegrityError,
        match="does not identify an immutable node",
    ):
        snapshot_store.load_snapshot_exact(
            plot_id="plot-a",
            geometry_hash="geometry-a",
            snapshot_ref=str(snapshot_store._path("plot-a")),
        )


def test_canonical_publication_uses_stable_immutable_science_on_retry(
    snapshot_store, monkeypatch, tmp_path
):
    from services.agribrain.common.plot_namespace import PlotNamespace
    from services.agribrain.layer05_asmae import plot_snapshot_store

    monkeypatch.setattr(
        plot_snapshot_store, "PLOT_SNAPSHOT_ROOT", tmp_path / "plot_snapshots"
    )
    result = _result()
    snapshot_ref = snapshot_store.publish_latest_snapshot(
        result, context_hash="ctx-a", geometry_hash="geometry-a"
    )
    result.update({
        "snapshot_ref": snapshot_ref,
        "snapshot_status": "published",
        "worldline_event_id": "event-first",
        "archive_refresh": {"status": "created"},
    })
    frontend = {
        "intelligence_snapshot_id": result["snapshot_id"],
        "surfaces": [],
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": result["crop_posterior_lineage"],
            "crop_worldline_event_id": result["crop_worldline_event_id"],
            "phenology_worldline_event_id": result[
                "phenology_worldline_event_id"
            ],
        },
    }
    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")

    first = plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=namespace,
        geometry_hash="geometry-a",
        snapshot_id=result["snapshot_id"],
        asmae_result=result,
        frontend_payload=frontend,
        job_id="job-a",
        manifest_hash="manifest-a",
    )
    loaded = plot_snapshot_store.load_latest_plot_snapshot(
        namespace, geometry_hash="geometry-a"
    )
    assert loaded is not None
    assert loaded["validation"]["lineageValid"] is True
    assert loaded["crop_worldline_event_id"] == "crop-event-a"
    assert loaded["phenology_worldline_event_id"] == "phenology-event-a"
    retry = snapshot_store.load_snapshot_exact(
        plot_id="plot-a",
        geometry_hash="geometry-a",
        snapshot_ref=snapshot_ref,
        snapshot_id=result["snapshot_id"],
    )
    assert retry is not None
    retry["archive_refresh_error"] = "later operational diagnostic"
    second = plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=namespace,
        geometry_hash="geometry-a",
        snapshot_id=result["snapshot_id"],
        asmae_result=retry,
        frontend_payload=frontend,
        job_id="job-a",
        manifest_hash="manifest-a",
    )

    assert second["node_hash"] == first["node_hash"]
    node = json.loads(Path(first["node_ref"]).read_text(encoding="utf-8"))
    assert "worldline_event_id" not in node["asmae"]
    assert "archive_refresh" not in node["asmae"]
    assert "snapshot_ref" not in node["asmae"]


def test_canonical_publication_binds_job_frozen_lineage_missing_from_science_node(
    snapshot_store, monkeypatch, tmp_path
):
    from services.agribrain.common.plot_namespace import PlotNamespace
    from services.agribrain.layer05_asmae import plot_snapshot_store

    monkeypatch.setattr(
        plot_snapshot_store, "PLOT_SNAPSHOT_ROOT", tmp_path / "plot_snapshots"
    )
    science = _result()
    for key in (
        "crop_worldline_event_id",
        "phenology_worldline_event_id",
    ):
        science.pop(key)
    snapshot_ref = snapshot_store.publish_latest_snapshot(
        science, context_hash="ctx-a", geometry_hash="geometry-a"
    )
    result = _result()
    result["snapshot_id"] = science["snapshot_id"]
    result["snapshot_ref"] = snapshot_ref
    frontend = {
        "intelligence_snapshot_id": result["snapshot_id"],
        "surfaces": [],
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": result["crop_posterior_lineage"],
            "crop_worldline_event_id": result["crop_worldline_event_id"],
            "phenology_worldline_event_id": result[
                "phenology_worldline_event_id"
            ],
        },
    }

    head = plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=PlotNamespace("tenant-a", "farm-a", "plot-a"),
        geometry_hash="geometry-a",
        snapshot_id=result["snapshot_id"],
        asmae_result=result,
        frontend_payload=frontend,
        job_id="job-a",
        manifest_hash="manifest-a",
    )

    assert head["crop_worldline_event_id"] == "crop-event-a"
    assert head["phenology_worldline_event_id"] == "phenology-event-a"
    loaded = plot_snapshot_store.load_latest_plot_snapshot(
        PlotNamespace("tenant-a", "farm-a", "plot-a"),
        geometry_hash="geometry-a",
    )
    assert loaded is not None
    assert loaded["validation"]["lineageValid"] is True


def test_canonical_publication_rejects_conflicting_frozen_lineage(
    snapshot_store, monkeypatch, tmp_path
):
    from services.agribrain.common.plot_namespace import PlotNamespace
    from services.agribrain.layer05_asmae import plot_snapshot_store

    monkeypatch.setattr(
        plot_snapshot_store, "PLOT_SNAPSHOT_ROOT", tmp_path / "plot_snapshots"
    )
    science = _result()
    snapshot_ref = snapshot_store.publish_latest_snapshot(
        science, context_hash="ctx-a", geometry_hash="geometry-a"
    )
    conflicting = _result()
    conflicting["snapshot_id"] = science["snapshot_id"]
    conflicting["snapshot_ref"] = snapshot_ref
    conflicting["crop_worldline_event_id"] = "crop-event-b"
    frontend = {
        "intelligence_snapshot_id": conflicting["snapshot_id"],
        "surfaces": [],
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": conflicting["crop_posterior_lineage"],
            "crop_worldline_event_id": "crop-event-b",
            "phenology_worldline_event_id": conflicting[
                "phenology_worldline_event_id"
            ],
        },
    }

    with pytest.raises(
        ValueError,
        match="immutable crop_worldline_event_id mismatch",
    ):
        plot_snapshot_store.publish_canonical_plot_snapshot(
            namespace=PlotNamespace("tenant-a", "farm-a", "plot-a"),
            geometry_hash="geometry-a",
            snapshot_id=conflicting["snapshot_id"],
            asmae_result=conflicting,
            frontend_payload=frontend,
            job_id="job-a",
            manifest_hash="manifest-a",
        )


def test_canonical_publication_rejects_empty_surface_inventory_for_visual_asmae(
    snapshot_store, monkeypatch, tmp_path
):
    from services.agribrain.common.plot_namespace import PlotNamespace
    from services.agribrain.layer05_asmae import plot_snapshot_store

    monkeypatch.setattr(
        plot_snapshot_store, "PLOT_SNAPSHOT_ROOT", tmp_path / "plot_snapshots"
    )
    result = _result()
    result["visual_allowed"] = True
    snapshot_ref = snapshot_store.publish_latest_snapshot(
        result, context_hash="ctx-a", geometry_hash="geometry-a"
    )
    result["snapshot_ref"] = snapshot_ref
    frontend = {
        "intelligence_snapshot_id": result["snapshot_id"],
        "surfaces": [],
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": result["crop_posterior_lineage"],
            "crop_worldline_event_id": result["crop_worldline_event_id"],
            "phenology_worldline_event_id": result[
                "phenology_worldline_event_id"
            ],
        },
    }

    with pytest.raises(ValueError, match="raster evidence but no surfaces"):
        plot_snapshot_store.publish_canonical_plot_snapshot(
            namespace=PlotNamespace("tenant-a", "farm-a", "plot-a"),
            geometry_hash="geometry-a",
            snapshot_id=result["snapshot_id"],
            asmae_result=result,
            frontend_payload=frontend,
            job_id="job-a",
            manifest_hash="manifest-a",
        )


def test_canonical_snapshot_cache_deep_copy_isolation_adversarial_mutation(
    snapshot_store, tmp_path, monkeypatch
) -> None:
    """Batch A verification: mutating returned snapshot nested fields cannot taint cache or subsequent callers."""
    from services.agribrain.layer05_asmae import plot_snapshot_store
    from services.agribrain.common.plot_namespace import PlotNamespace

    monkeypatch.setattr(
        plot_snapshot_store, "PLOT_SNAPSHOT_ROOT", tmp_path / "plot_snapshots"
    )

    result = _result()
    snapshot_ref = snapshot_store.publish_latest_snapshot(
        result, context_hash="ctx-a", geometry_hash="geometry-a"
    )
    result["snapshot_ref"] = snapshot_ref

    frontend = {
        "intelligence_snapshot_id": result["snapshot_id"],
        "surfaces": [],
        "phenology_stage": "flowering",
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": result["crop_posterior_lineage"],
            "crop_worldline_event_id": result["crop_worldline_event_id"],
            "phenology_worldline_event_id": result["phenology_worldline_event_id"],
        },
    }

    ns = PlotNamespace("tenant-a", "farm-a", "plot-a")
    published = plot_snapshot_store.publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash="geometry-a",
        snapshot_id=result["snapshot_id"],
        asmae_result=result,
        frontend_payload=frontend,
        job_id="job-a",
        manifest_hash="manifest-a",
    )
    assert published is not None

    # Caller 1: Cold read (populates cache)
    caller1 = plot_snapshot_store.load_latest_plot_snapshot(namespace=ns)
    assert caller1 is not None
    orig_lineage = caller1["frontend_payload"]["scientific_evidence_lineage"]["crop_posterior_lineage"]
    orig_snap_id = caller1["snapshot_id"]

    # Adversarially mutate caller 1's scientific and validation metadata
    caller1["frontend_payload"]["scientific_evidence_lineage"]["crop_posterior_lineage"] = "ADVERSARIAL_MUTATION_TAINT"
    caller1["frontend_payload"]["tampered_nested_key"] = 99999.99
    if "validation" not in caller1 or caller1["validation"] is None:
        caller1["validation"] = {}
    caller1["validation"]["injected_exploit_state"] = "POISONED"
    caller1["snapshot_id"] = "FORGED_SNAPSHOT_ID"

    # Caller 2: Warm read (from cache)
    caller2 = plot_snapshot_store.load_latest_plot_snapshot(namespace=ns)
    assert caller2 is not None

    # Assert Caller 2 is completely isolated and pristine
    assert caller2["snapshot_id"] == orig_snap_id
    assert caller2["frontend_payload"]["scientific_evidence_lineage"]["crop_posterior_lineage"] == orig_lineage
    assert "tampered_nested_key" not in caller2["frontend_payload"]
    assert "injected_exploit_state" not in (caller2.get("validation") or {})

    # Mutate Caller 2 and assert Caller 3 remains pristine
    caller2["frontend_payload"]["scientific_evidence_lineage"]["crop_posterior_lineage"] = "SECOND_TAINT"
    caller3 = plot_snapshot_store.load_latest_plot_snapshot(namespace=ns)
    assert caller3 is not None
    assert caller3["frontend_payload"]["scientific_evidence_lineage"]["crop_posterior_lineage"] == orig_lineage

