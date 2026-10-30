"""Pilot: published ASMAE authority is valid only within its geometry/cycle scope."""
from unittest.mock import patch

from services.agribrain.layer05_asmae import plot_snapshot_store as store
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer10_sire.surface_contract import (
    SURFACES_SCHEMA_VERSION,
    RENDER_AUTHORIZATION_VERSION,
    classify_surface_publication,
)


def payload(snapshot_id, cycle):
    value = {
        "intelligence_snapshot_id": snapshot_id,
        "surfaces": [],
        "status": "degraded",
        "placeholder_only": True,
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": False}},
        "asmae_proof": {"status": "unavailable"},
        "mode_display_state": {"canopy": {"status": "unavailable"}},
        "source_policy_display_state": {"status": "unavailable"},
        "core_asmae_evidence_state": {"status": "unavailable"},
        "publication_surface_state": {"status": "unavailable"},
        "publication_id": "PUB-" + snapshot_id,
        "publication_run_id": "RUN-" + snapshot_id,
        "run_id": "RUN-" + snapshot_id,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "crop_cycle_id": cycle,
        "published_at": "2026-10-30T12:00:00Z",
        "evidence_cutoff_at": "2026-10-30T11:00:00Z",
        "observation_window": {
            "start": "2026-10-01T00:00:00Z",
            "end": "2026-10-30T11:00:00Z",
        },
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": "lineage",
            "crop_worldline_event_id": "crop-event",
            "phenology_worldline_event_id": "phenology-event",
        },
    }
    value["publication_status"] = classify_surface_publication(value)[0]
    return value


def test_valid_old_asmae_stays_immutable_but_cannot_block_new_context(tmp_path):
    ns = PlotNamespace(tenant_id="T", farm_id="F", plot_id="P")
    old = payload("ASMAE-SNAPSHOT-old", "CYCLE-A")
    lineage = old["scientific_evidence_lineage"]
    science = {
        "snapshot_id": old["intelligence_snapshot_id"],
        "content_hash": "old-content",
        **lineage,
        "crop_cycle_id": "CYCLE-A",
        "evidence_cutoff_at": old["evidence_cutoff_at"],
    }
    with patch.object(store, "PLOT_SNAPSHOT_ROOT", tmp_path):
        store.publish_canonical_plot_snapshot(
            namespace=ns,
            geometry_hash="GEOM-A",
            snapshot_id=old["intelligence_snapshot_id"],
            asmae_result=science,
            frontend_payload=old,
            job_id="JOB-OLD",
            manifest_hash="manifest-old",
        )
        accepted_old = store.load_latest_plot_snapshot(ns)
        assert accepted_old is not None
        assert all(accepted_old["validation"].values())

        # Same scientific context: do not weaken a valid ASMAE head with L10.
        same = payload("L10-same", "CYCLE-A")
        retained = store.publish_canonical_layer10_snapshot(
            namespace=ns, geometry_hash="GEOM-A",
            frontend_payload=same, request_run_id="JOB-SAME",
            crop_cycle_id="CYCLE-A",
        )
        assert retained["snapshot_id"] == "ASMAE-SNAPSHOT-old"

        # Changed geometry and crop cycle: new L10 can become the current
        # head while the old immutable ASMAE node remains in history.
        new = payload("L10-new", "CYCLE-B")
        published = store.publish_canonical_layer10_snapshot(
            namespace=ns, geometry_hash="GEOM-B",
            frontend_payload=new, request_run_id="JOB-NEW",
            crop_cycle_id="CYCLE-B",
        )
        assert published["snapshot_id"] == "L10-new"
        current = store.load_latest_plot_snapshot(ns)
        assert current is not None
        assert current["snapshot_id"] == "L10-new"
        assert current["geometry_hash"] == "GEOM-B"
        assert current["crop_cycle_id"] == "CYCLE-B"
        historical = store.load_plot_snapshot_by_id("ASMAE-SNAPSHOT-old", namespace=ns)
        assert historical is not None
        assert historical["crop_cycle_id"] == "CYCLE-A"
        assert historical["geometry_hash"] == "GEOM-A"
