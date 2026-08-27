from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.common.surface_hashing import compute_surface_inventory_hash
from services.agribrain.scientific_contracts.state_support import (
    StateEvidenceClass,
    resolve_state_evidence_class,
)


def test_state_support_classification_uses_updates_and_relationship():
    assert resolve_state_evidence_class({
        "support_status": "assimilated",
        "accepted_update_count": 3,
        "observation_relationship": "proxy",
    }) is StateEvidenceClass.PROXY_ASSIMILATED
    assert resolve_state_evidence_class({
        "support_status": "assimilated",
        "accepted_update_count": 2,
        "observation_relationship": "direct",
    }) is StateEvidenceClass.DIRECTLY_ASSIMILATED
    assert resolve_state_evidence_class({
        "support_status": "prior_constrained",
        "accepted_update_count": 0,
        "observation_relationship": "none",
    }) is StateEvidenceClass.PRIOR_CONSTRAINED


def test_reintegration_loads_exact_frozen_crop_event_and_fails_closed_on_drift():
    from services.agribrain.orchestrator_v2.runner import (
        _load_frozen_reintegration_event,
    )

    inputs = SimpleNamespace(
        tenant_id="tenant-a",
        farm_id="farm-a",
        plot_id="plot-a",
    )
    event = {
        "event_id": "crop-event-a",
        "event_type": "CROP_POSTERIOR",
        "tenant_id": "tenant-a",
        "namespace": "farm-a",
        "plot_id": "plot-a",
        "effective_at": "2026-08-20T12:00:00+00:00",
        "payload": {
            "plot_namespace": {
                "tenant_id": "tenant-a",
                "farm_id": "farm-a",
                "plot_id": "plot-a",
            },
            "crop_posterior": {
                "content_hash": "crop-hash-a",
                "lineage_id": "crop-lineage-a",
            },
        },
    }

    class ExactEventService:
        def __init__(self, stored):
            self.stored = stored

        def load_event(self, **coordinates):
            assert coordinates == {
                "plot_id": "plot-a",
                "event_id": "crop-event-a",
                "tenant_id": "tenant-a",
                "namespace": "farm-a",
            }
            return deepcopy(self.stored)

    scientific = _load_frozen_reintegration_event(
        ExactEventService(event),
        inputs=inputs,
        event_id="crop-event-a",
        event_type="CROP_POSTERIOR",
        payload_key="crop_posterior",
        expected_content_hash="crop-hash-a",
    )
    assert scientific["lineage_id"] == "crop-lineage-a"

    rehydrated = _load_frozen_reintegration_event(
        ExactEventService(event),
        inputs=inputs,
        event_id="crop-event-a",
        event_type="CROP_POSTERIOR",
        payload_key="crop_posterior",
        expected_content_hash="crop-hash-a",
        rehydrate_generated_at=True,
    )
    assert rehydrated["generated_at"] == "2026-08-20T12:00:00+00:00"

    drifted = deepcopy(event)
    drifted["payload"]["crop_posterior"]["content_hash"] = "newer-crop-hash"
    with pytest.raises(ValueError, match="content hash mismatch"):
        _load_frozen_reintegration_event(
            ExactEventService(drifted),
            inputs=inputs,
            event_id="crop-event-a",
            event_type="CROP_POSTERIOR",
            payload_key="crop_posterior",
            expected_content_hash="crop-hash-a",
        )


def test_pre_asmae_reuses_only_an_exact_as_of_phenology_event():
    from services.agribrain.orchestrator_v2.runner import (
        _freeze_previous_phenology_event,
    )

    event = {
        "event_id": "phenology-event-a",
        "event_type": "PHENOLOGY_POSTERIOR",
        "effective_at": "2026-08-19",
        "observation_or_valid_time": "2026-08-19",
        "payload": {
            "phenology_posterior": {
                "content_hash": "phenology-hash-a",
                "current_stage": "UNKNOWN",
                "authority": "unavailable",
            },
        },
    }

    frozen = _freeze_previous_phenology_event(event, as_of="2026-08-25")
    assert frozen["phenology_worldline_event_id"] == "phenology-event-a"
    assert frozen["phenology_posterior_hash"] == "phenology-hash-a"
    assert frozen["phenology_evidence_reuse"] == "exact_as_of_worldline_event"

    with pytest.raises(ValueError, match="later than the run as-of date"):
        _freeze_previous_phenology_event(event, as_of="2026-08-18")


def test_reintegration_payload_comparison_uses_worldline_canonical_form():
    from services.agribrain.orchestrator_v2.runner import (
        _worldline_scientific_payload_matches,
    )

    persisted = {
        "content_hash": "crop-hash-a",
        "ranked_candidates": [{"crop": "tomato", "probability": 0.7}],
    }
    declared = {
        **persisted,
        "generated_at": "2026-08-25T10:00:00+00:00",
    }
    assert _worldline_scientific_payload_matches(declared, persisted) is True
    drifted = deepcopy(declared)
    drifted["ranked_candidates"][0]["probability"] = 0.8
    assert _worldline_scientific_payload_matches(drifted, persisted) is False


def test_scientific_digest_covers_downstream_reintegration_layers():
    from services.agribrain.layer05_asmae.code_lineage import (
        REPO_ROOT,
        _scientific_source_files,
    )

    covered = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in _scientific_source_files()
    }
    assert "services/agribrain/layer2_veg_int/runner.py" in covered
    assert "services/agribrain/layer10_sire/runner.py" in covered
    assert not any("/tests/" in path for path in covered)


def test_state_alias_resolver_prevents_bare_soil_authority_fallback():
    from services.agribrain.layer10_sire.schema import SurfaceType
    from services.agribrain.layer10_sire.surfaces.asmae import (
        compute_asmae_support_classification,
    )
    from services.agribrain.scientific_contracts.state_schema_ref import (
        canonical_state_key,
    )

    assert canonical_state_key("asmae_bare_soil") == "bare_soil_fraction"
    classification = compute_asmae_support_classification(
        real_ev=True,
        source_reality="real_raster",
        meta={},
        stype=SurfaceType.ASMAE_BARE_SOIL,
        state_support_ledger={
            "bare_soil_fraction": {
                "support_status": "proxy_assimilated",
                "accepted_update_count": 4,
                "observation_relationship": "proxy",
            }
        },
        feature_name="asmae_bare_soil",
    )
    assert classification["support_class"] == "proxy_assimilated"
    assert classification["evidence_class"] == "Proxy-Assimilated"
    assert classification["direct_observation"] is False
    assert classification["management_zone_eligible"] is False


def test_asmae_process_diagnostics_never_inherit_observed_authority():
    from services.agribrain.layer10_sire.schema import SurfaceType
    from services.agribrain.layer10_sire.surfaces.asmae import (
        compute_asmae_support_classification,
    )

    for surface_type in (
        SurfaceType.ASMAE_POSTERIOR_CONCENTRATION,
        SurfaceType.ASMAE_UNCERTAINTY,
        SurfaceType.ASMAE_ML_AGREEMENT,
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION_MAP,
        SurfaceType.ASMAE_RADIOMETRIC_SUPPORT,
    ):
        classification = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={},
            stype=surface_type,
            state_support_ledger={},
            feature_name=surface_type.value.lower(),
        )
        assert classification["support_class"] == "derived_diagnostic"
        assert classification["evidence_class"] == "Derived diagnostic"
        assert classification["direct_observation"] is False
        assert classification["management_zone_eligible"] is False
        assert classification["zone_statistics_eligible"] is False


def test_surface_inventory_requires_unique_producer_identity():
    valid = {
        "surface_id": "surface-a",
        "surface_type": "NDVI_CLEAN",
        "values": [[0.2]],
    }
    assert len(compute_surface_inventory_hash([valid])) == 64
    with pytest.raises(ValueError, match="missing mandatory surface_id"):
        compute_surface_inventory_hash([{**valid, "surface_id": ""}])
    with pytest.raises(ValueError, match="Duplicate surface_id"):
        compute_surface_inventory_hash([
            valid,
            {**valid, "surface_type": "CANOPY_ASMAE_VIGOR"},
        ])


def test_reintegration_serializer_preserves_surface_identity():
    from services.agribrain.orchestrator_v2.run_entrypoint import _serialize_l10_output

    surface = SimpleNamespace(
        surface_id="producer-surface-a",
        semantic_type="NDVI_CLEAN",
        values=[[0.2, 0.4]],
        grounding_class="RASTER_GROUNDED",
        units="index",
        render_range=(0.0, 1.0),
        palette_id="viridis",
        source_layers=["L1"],
        provenance={},
        grid_spec=None,
    )
    output = SimpleNamespace(
        run_id="science-run-a",
        publication_run_id="science-run-a",
        publication_id="publication-a",
        surface_pack=[surface],
        zone_pack=[],
        explainability_pack={},
        render_authorizations={"satellite": {"canopy": {"base": {}}}},
        mode_display_state={"canopy": {"canRenderPixels": True}},
        source_policy_display_state={"requested_policy": "satellite"},
        asmae_proof={"sentinel_proof": {"s2_real_scene_count": 1}},
        resolved_crop_stage="VEGETATIVE",
        phenology_context={
            "resolved_crop_stage": "VEGETATIVE",
            "phenology_evidence_class": "ndvi_reconciled",
            "phenology_source": "l10_ndvi_surface_mean",
            "phenology_confidence": 0.6,
            "ndvi_mean": 0.41,
            "crop": "tomato",
            "crop_known": True,
            "stage_available": True,
            "contract_version": "phenology_authority_v1",
        },
    )

    payload = _serialize_l10_output(output)

    assert payload["surfaces"][0]["surface_id"] == "producer-surface-a"
    assert payload["surfaces"][0]["semantic_type"] == "NDVI_CLEAN"
    assert payload["resolved_crop_stage"] == "VEGETATIVE"
    assert payload["phenology_context"]["ndvi_mean"] == pytest.approx(0.41)


def test_reintegration_worldline_uses_the_authenticated_farm_namespace():
    from services.agribrain.layer05_asmae.reintegration import (
        _canonical_worldline_namespace,
    )

    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
    assert _canonical_worldline_namespace({}, namespace) == "farm-a"
    assert _canonical_worldline_namespace(
        {"worldline_namespace": "farm-a"}, namespace
    ) == "farm-a"
    with pytest.raises(ValueError, match="worldline namespace mismatch"):
        _canonical_worldline_namespace(
            {"worldline_namespace": "default"}, namespace
        )


def test_reintegration_retry_reuses_the_valid_job_bound_publication(monkeypatch):
    from services.agribrain.layer05_asmae import plot_snapshot_store
    from services.agribrain.layer05_asmae import reintegration

    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
    snapshot_id = "ASMAE-SNAPSHOT-retry-a"
    job_id = "job-a"
    manifest_hash = "manifest-a"
    existing = {
        "snapshot_kind": "asmae",
        "snapshot_id": snapshot_id,
        "job_id": job_id,
        "manifest_hash": manifest_hash,
        "node_ref": "nodes/retry-a.json",
        "publication_receipt_ref": "receipts/job-a.json",
        "publication_receipt_hash": "receipt-a",
        "validation": {
            "nodeValid": True,
            "publicationValid": True,
            "receiptValid": True,
            "inventoryValid": True,
            "bindingValid": True,
            "lineageValid": True,
            "schemaValid": True,
            "contractValid": True,
            "publicationStatusValid": True,
        },
        "frontend_payload": {
            "audit": {
                "orchestrator_run_id": "orchestrator-a",
                "artifact_hash": "artifact-a",
                "lineage_map": {"L1": "l1-a", "L10": "l10-a"},
            }
        },
    }
    monkeypatch.setattr(
        plot_snapshot_store,
        "load_latest_plot_snapshot",
        lambda supplied_namespace, geometry_hash: existing,
    )
    committed = []

    def commit_event(**kwargs):
        committed.append(kwargs)
        return {"event_id": "canonical-event-a"}

    monkeypatch.setattr(
        reintegration, "_commit_canonical_snapshot_event", commit_event
    )
    context = {
        "tenant_id": namespace.tenant_id,
        "farm_id": namespace.farm_id,
        "plot_id": namespace.plot_id,
        "geometry_hash": "geometry-a",
        "worldline_namespace": namespace.farm_id,
        "plot_namespace": {
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "plot_id": namespace.plot_id,
        },
        "orchestrator_reintegration": {
            "contract_version": reintegration.REINTEGRATION_CONTRACT_VERSION,
            "input": {
                "plot_id": namespace.plot_id,
                "tenant_id": namespace.tenant_id,
                "farm_id": namespace.farm_id,
                "plot_namespace": {
                    "tenant_id": namespace.tenant_id,
                    "farm_id": namespace.farm_id,
                    "plot_id": namespace.plot_id,
                },
                "geometry_hash": "geometry-a",
                "date_range": {"start": "2026-08-01", "end": "2026-08-21"},
                "crop_config": {},
                "operational_context": {},
                "policy_snapshot": {},
            },
        },
    }

    response = reintegration.rebuild_canonical_plot_snapshot(
        asmae_result={
            "snapshot_id": snapshot_id,
            "plot_id": namespace.plot_id,
            "plot_state_artifact": {
                "as_of": "2026-08-21T00:00:00+00:00",
                "authority_level": "DIAGNOSTIC_NO_STATE_UPDATE",
            },
        },
        context=context,
        job_id=job_id,
        manifest_hash=manifest_hash,
        parent_event_id="evidence-event-a",
    )

    assert response["status"] == "completed"
    assert response["publication_reused"] is True
    assert response["snapshot_ref"] == "nodes/retry-a.json"
    assert response["worldline_event_id"] == "canonical-event-a"
    assert response["orchestrator_run_id"] == "orchestrator-a"
    assert response["layer_run_ids"] == {"L1": "l1-a", "L10": "l10-a"}
    assert committed[0]["parent_event_id"] == "evidence-event-a"
    assert committed[0]["worldline_namespace"] == "farm-a"


def test_run_entrypoint_freezes_field_geometry_for_worker_reintegration():
    from services.agribrain.orchestrator_v2.run_entrypoint import _build_inputs

    geometry = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[[2.9, 36.5], [2.91, 36.5], [2.91, 36.51], [2.9, 36.5]]]
            ],
        },
    }
    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")

    inputs = _build_inputs(
        {
            "plot_id": namespace.plot_id,
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "field_geometry": geometry,
            "geometry_hash": "geometry-a",
        },
        authenticated_namespace=namespace,
    )

    assert inputs.field_geometry == geometry
    assert inputs.polygon_geojson == geometry
    assert inputs.operational_context["polygon_coords"] == geometry


def test_layer10_preserves_unknown_l2_stage_and_never_reinfers_from_surface_ndvi():
    from services.agribrain.layer10_sire.runner import _resolve_phenology_context

    veg_int = SimpleNamespace(
        phenology=SimpleNamespace(stage_by_day=["UNKNOWN"]),
        ndvi_records=[],
    )
    context = _resolve_phenology_context(veg_int, 0.41, crop="tomato")

    assert context["resolved_crop_stage"] == "UNKNOWN"
    assert context["raw_l2_crop_stage"] == "UNKNOWN"
    assert context["phenology_evidence_class"] == "unavailable"
    assert context["phenology_source"] == "unavailable"
    assert context["ndvi_source"] == "not_used_by_layer10"
    assert context["crop_known"] is True
    assert context["stage_available"] is False


def test_publication_allows_truthful_unknown_stage_without_downstream_inference():
    from services.agribrain.layer10_sire.surface_contract import (
        PublicationStatus,
        RENDER_AUTHORIZATION_VERSION,
        SURFACES_SCHEMA_VERSION,
        classify_surface_publication,
    )

    payload = {
        "run_id": "science-run-a",
        "publication_run_id": "science-run-a",
        "publication_id": "publication-a",
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "surfaces": [{"surface_id": "surface-a"}],
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"satellite": {"canopy": {"base": {}}}},
        "asmae_proof": {"sentinel_proof": {}},
        "mode_display_state": {"canopy": {"canRenderPixels": True}},
        "source_policy_display_state": {"requested_policy": "satellite"},
        "core_asmae_evidence_state": {"state": "unavailable"},
        "publication_surface_state": {"state": "provider_surface"},
        "resolved_crop_stage": "UNKNOWN",
        "phenology_context": {
            "resolved_crop_stage": "UNKNOWN",
            "ndvi_mean": 0.41,
            "crop": "tomato",
            "crop_known": True,
        },
    }

    status, reason = classify_surface_publication(payload)
    # A declared crop and a vegetated surface are not phenology observations.
    # Publishing UNKNOWN is therefore the truthful result when Layer 2 has no
    # canonical stage receipt; Layer 10 must not infer a stage from NDVI.
    assert status == PublicationStatus.VALID_NORMAL.value
    assert reason == "normal_authoritative_envelope"


def test_surface_serializers_reject_missing_identity():
    from services.agribrain.layer10_sire.surface_contract import (
        PublicationStatus,
        classify_surface_publication,
        serialize_surface_artifact,
    )

    with pytest.raises(ValueError, match="missing mandatory surface_id"):
        serialize_surface_artifact(SimpleNamespace(semantic_type="NDVI_CLEAN"))
    status, reason = classify_surface_publication({"surfaces": [{"type": "NDVI_CLEAN"}]})
    assert status == PublicationStatus.INVALID_PUBLICATION.value
    assert reason == "surface_id_missing"


def test_production_nonce_store_absence_fails_closed(monkeypatch):
    from services.agribrain.app import internal_service_auth as auth

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("NODE_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(auth, "_mongo_nonces_collection", None)
    auth._in_memory_nonces.clear()
    assert auth.verify_and_store_nonce("v1", "nonce-production") is False
    assert "v1::nonce-production" not in auth._in_memory_nonces


def test_durable_terminal_job_overrides_stale_request_progress(monkeypatch):
    from services.agribrain.app import main
    from services.agribrain.layer05_asmae import background_jobs as jobs
    from services.agribrain.layer05_asmae import plot_snapshot_store as snapshots

    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
    run_id = "request-run-a"
    monkeypatch.setitem(main._plot_run_map, namespace.to_tuple(), run_id)
    monkeypatch.setitem(main._progress_store, run_id, {
        "namespace": namespace,
        "status": "queued",
        "active": True,
        "terminal": False,
        "stages": [],
    })
    monkeypatch.setattr(jobs, "recover_all_pending_jobs", lambda namespace: 0)
    monkeypatch.setattr(jobs, "latest_job_for_plot", lambda namespace, run_id=None: {
        "job_id": "job-failed-current",
        "plot_namespace": {
            "tenant_id": "tenant-a",
            "farm_id": "farm-a",
            "plot_id": "plot-a",
        },
        "tenant_id": "tenant-a",
        "farm_id": "farm-a",
        "plot_id": "plot-a",
        "status": "failed",
        "stage": "reintegration_failed",
        "error": "PlotNamespace mismatch",
    })
    monkeypatch.setattr(snapshots, "load_latest_plot_snapshot", lambda namespace: {
        "snapshot_id": "ASMAE-SNAPSHOT-last-known-good",
    })

    response = main.api_v2_progress("plot-a", namespace=namespace)

    assert response["status"] == "failed"
    assert response["terminal"] is True
    assert response["active"] is False
    assert response["publicationRelation"] == "failed"
    assert response["canonical_head_snapshot_id"] == "ASMAE-SNAPSHOT-last-known-good"
    assert response["asmae_job"]["job_id"] == "job-failed-current"


def test_durable_running_job_overrides_stale_terminal_request_progress(monkeypatch):
    from services.agribrain.app import main
    from services.agribrain.layer05_asmae import background_jobs as jobs
    from services.agribrain.layer05_asmae import plot_snapshot_store as snapshots

    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
    run_id = "request-run-running"
    monkeypatch.setitem(main._plot_run_map, namespace.to_tuple(), run_id)
    monkeypatch.setitem(main._progress_store, run_id, {
        "namespace": namespace,
        "status": "done",
        "active": False,
        "terminal": True,
        "stages": [{"stage": "Complete", "status": "done"}],
    })
    monkeypatch.setattr(jobs, "recover_all_pending_jobs", lambda namespace: 0)
    monkeypatch.setattr(jobs, "latest_job_for_plot", lambda namespace, run_id=None: {
        "job_id": "job-running-current",
        "plot_namespace": {
            "tenant_id": "tenant-a",
            "farm_id": "farm-a",
            "plot_id": "plot-a",
        },
        "tenant_id": "tenant-a",
        "farm_id": "farm-a",
        "plot_id": "plot-a",
        "status": "running",
        "stage": "scientific_execution",
        "progress_pct": 15,
    })
    monkeypatch.setattr(snapshots, "load_latest_plot_snapshot", lambda namespace: None)

    response = main.api_v2_progress("plot-a", namespace=namespace)

    assert response["status"] == "running"
    assert response["active"] is True
    assert response["terminal"] is False
    assert response["publicationRelation"] == "in_progress"
    assert response["durable_job"]["progress_pct"] == 15


def test_old_failed_job_is_retry_eligible_after_scientific_source_change(monkeypatch):
    from services.agribrain.app import main
    from services.agribrain.layer05_asmae import background_jobs as jobs
    from services.agribrain.layer05_asmae import code_lineage
    from services.agribrain.layer05_asmae import plot_snapshot_store as snapshots

    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
    stored_job = {
        "job_id": "job-failed-old-source",
        "plot_namespace": {
            "tenant_id": "tenant-a",
            "farm_id": "farm-a",
            "plot_id": "plot-a",
        },
        "tenant_id": "tenant-a",
        "farm_id": "farm-a",
        "plot_id": "plot-a",
        "status": "failed",
        "retry_eligible": False,
        "scientific_identity": {
            "scientific_source_digest": "old-source-digest",
        },
    }
    original_job = deepcopy(stored_job)
    monkeypatch.setattr(jobs, "recover_all_pending_jobs", lambda namespace: 0)
    monkeypatch.setattr(
        jobs,
        "latest_job_for_plot",
        lambda namespace, run_id=None: stored_job,
    )
    monkeypatch.setattr(
        code_lineage,
        "scientific_source_digest",
        lambda: "current-source-digest",
    )
    monkeypatch.setattr(snapshots, "load_latest_plot_snapshot", lambda namespace: None)

    response = main.api_v2_progress("plot-a", namespace=namespace)

    assert response["durable_job"]["retry_eligible"] is True
    assert response["durable_job"]["current_scientific_source_digest"] == (
        "current-source-digest"
    )
    assert stored_job == original_job


def test_failed_job_progress_survives_source_digest_read_failure(monkeypatch):
    from services.agribrain.app import main
    from services.agribrain.layer05_asmae import background_jobs as jobs
    from services.agribrain.layer05_asmae import code_lineage
    from services.agribrain.layer05_asmae import plot_snapshot_store as snapshots

    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
    stored_job = {
        "job_id": "job-failed-source-unavailable",
        "tenant_id": "tenant-a",
        "farm_id": "farm-a",
        "plot_id": "plot-a",
        "status": "failed",
        "retry_eligible": False,
        "scientific_identity": {
            "scientific_source_digest": "old-source-digest",
        },
    }
    monkeypatch.setattr(jobs, "recover_all_pending_jobs", lambda namespace: 0)
    monkeypatch.setattr(
        jobs,
        "latest_job_for_plot",
        lambda namespace, run_id=None: stored_job,
    )

    def source_digest_unavailable():
        raise OSError("source tree temporarily unavailable")

    monkeypatch.setattr(
        code_lineage,
        "scientific_source_digest",
        source_digest_unavailable,
    )
    monkeypatch.setattr(snapshots, "load_latest_plot_snapshot", lambda namespace: None)

    response = main.api_v2_progress("plot-a", namespace=namespace)

    assert response["status"] == "failed"
    assert response["terminal"] is True
    assert response["active"] is False
    assert response["durable_job"]["retry_eligible"] is False


def test_terminal_layer10_result_publishes_valid_canonical_head_without_faking_asmae(
    monkeypatch, tmp_path
):
    from services.agribrain.layer05_asmae import plot_snapshot_store as snapshots

    monkeypatch.setattr(snapshots, "PLOT_SNAPSHOT_ROOT", tmp_path / "plot_snapshots")
    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
    payload = {
        "plot_id": "plot-a",
        "intelligence_snapshot_id": "L10-terminal-a",
        "publication_id": "pub-terminal-a",
        "publication_status": "VALID_DEGRADED",
        "surface_schema_version": "surface-v1",
        "render_authorization_version": "render-v1",
        "source_policy": "canonical",
        "surfaces": [{
            "surface_id": "surface-ndvi",
            "surface_type": "NDVI_CLEAN",
            "values": [[0.2, 0.4]],
            "units": "index",
        }],
        "source_policy_display_state": {
            "asmaePlotState": {
                "available": False,
                "activeSpatialJobStatus": None,
            }
        },
        "asmae_evidence_state": {
            "state": "asmae_unavailable",
            "reason": "execution_error",
        },
    }

    snapshots.publish_canonical_layer10_snapshot(
        namespace=namespace,
        geometry_hash="geometry-a",
        frontend_payload=payload,
        request_run_id="run-terminal-a",
    )
    loaded = snapshots.load_latest_plot_snapshot(namespace, "geometry-a")

    assert loaded is not None
    assert loaded["snapshot_kind"] == "layer10_terminal"
    assert loaded["snapshot_id"] == "L10-terminal-a"
    for key in (
        "nodeValid", "publicationValid", "receiptValid", "inventoryValid",
        "bindingValid", "lineageValid",
    ):
        assert loaded["validation"][key] is True
    assert loaded["validation"]["schemaValid"] is False
    assert loaded["validation"]["contractValid"] is False
    assert loaded["refresh_required"] is True
    published = loaded["frontend_payload"]
    assert published["asmae_evidence_state"]["state"] == "asmae_unavailable"
    assert (
        published["source_policy_display_state"]["asmaePlotState"]
        ["activeSpatialJobStatus"] is None
    )


def test_stale_integrity_valid_head_requests_refresh_instead_of_becoming_authority(
    monkeypatch,
):
    from services.agribrain.app import main
    from services.agribrain.layer10_sire.surface_contract import (
        SURFACES_SCHEMA_VERSION,
    )

    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
    monkeypatch.setattr(
        "services.agribrain.layer05_asmae.plot_snapshot_store.load_latest_plot_snapshot",
        lambda namespace: {
            "snapshot_id": "old-head-a",
            "validation": {
                "nodeValid": True,
                "publicationValid": True,
                "receiptValid": True,
                "inventoryValid": True,
                "bindingValid": True,
                "lineageValid": True,
                "schemaValid": False,
                "contractValid": False,
                "publicationStatusValid": True,
            },
            "contract_validation": {
                "current_surface_schema_version": SURFACES_SCHEMA_VERSION,
                "published_surface_schema_version": "v22",
            },
        },
    )

    response = main.api_v2_canonical_plot_snapshot(
        "plot-a", namespace=namespace
    )

    assert response["available"] is False
    assert response["reason"] == "canonical_head_schema_stale"
    assert response["refreshRequired"] is True
    assert response["snapshot_id"] == "old-head-a"


def test_snapshot_endpoint_quarantines_integrity_invalid_head_and_retains_last_good(
    monkeypatch,
):
    """The HTTP endpoint must never publish a head with a failed hash/binding."""
    from services.agribrain.app import main
    from services.agribrain.layer05_asmae import plot_snapshot_store as snapshots

    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
    monkeypatch.setattr(
        snapshots,
        "load_latest_plot_snapshot",
        lambda namespace: {
            "snapshot_id": "ASMAE-SNAPSHOT-corrupt-a",
            "frontend_payload": {
                "intelligence_snapshot_id": "ASMAE-SNAPSHOT-corrupt-a",
                "surfaces": [{"surface_id": "must-not-be-served"}],
            },
            "validation": {
                "nodeValid": False,
                "publicationValid": True,
                "receiptValid": True,
                "inventoryValid": False,
                "bindingValid": True,
                "lineageValid": True,
                "schemaValid": True,
                "contractValid": True,
                "publicationStatusValid": True,
            },
            "contract_validation": {
                "current_surface_schema_version": "surface-v-current",
                "published_surface_schema_version": "surface-v-current",
            },
        },
    )
    main.app.dependency_overrides[main.require_internal_service_request] = (
        lambda: namespace
    )
    try:
        response = TestClient(main.app).get("/v2/plots/plot-a/snapshot")
    finally:
        main.app.dependency_overrides.pop(
            main.require_internal_service_request, None
        )

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["reason"] == "canonical_head_integrity_invalid"
    assert body["status"] == "quarantined"
    assert body["quarantined"] is True
    assert body["refreshRequired"] is True
    assert body["retainLastKnownGood"] is True
    assert body["invalidIntegrityFlags"] == ["nodeValid", "inventoryValid"]
    assert body["snapshot_id"] == "ASMAE-SNAPSHOT-corrupt-a"
    assert "frontend_payload" not in body


def test_snapshot_endpoint_keeps_schema_stale_distinct_from_integrity_quarantine(
    monkeypatch,
):
    """A cryptographically valid old contract is refreshable, not corrupt."""
    from services.agribrain.app import main
    from services.agribrain.layer05_asmae import plot_snapshot_store as snapshots

    namespace = PlotNamespace("tenant-a", "farm-a", "plot-a")
    monkeypatch.setattr(
        snapshots,
        "load_latest_plot_snapshot",
        lambda namespace: {
            "snapshot_id": "ASMAE-SNAPSHOT-stale-a",
            "validation": {
                "nodeValid": True,
                "publicationValid": True,
                "receiptValid": True,
                "inventoryValid": True,
                "bindingValid": True,
                "lineageValid": True,
                "schemaValid": False,
                "contractValid": True,
                "publicationStatusValid": True,
            },
            "contract_validation": {
                "current_surface_schema_version": "surface-v-current",
                "published_surface_schema_version": "surface-v-old",
            },
        },
    )
    main.app.dependency_overrides[main.require_internal_service_request] = (
        lambda: namespace
    )
    try:
        response = TestClient(main.app).get("/v2/plots/plot-a/snapshot")
    finally:
        main.app.dependency_overrides.pop(
            main.require_internal_service_request, None
        )

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["reason"] == "canonical_head_schema_stale"
    assert body["status"] == "stale"
    assert body["quarantined"] is False
    assert body["retainLastKnownGood"] is True
    assert "invalidIntegrityFlags" not in body


def test_asmae_worldline_commit_preserves_authenticated_tenant_namespace(tmp_path):
    from services.agribrain.layer05_asmae.history.worldline_service import (
        PlotWorldlineService,
    )

    service = PlotWorldlineService(root=tmp_path / "worldlines")
    event = service.commit_asmae_result(
        {
            "plot_id": "plot-a",
            "content_hash": "content-a",
            "diagnostics": {"scientific_production_usable": False},
            "plot_state_artifact": {
                "as_of": "2026-08-10T00:00:00+00:00",
                "authority_level": "DIAGNOSTIC_NO_STATE_UPDATE",
            },
        },
        geometry_hash="geometry-a",
        tenant_id="tenant-a",
        namespace="worldline-a",
    )

    event_id = event["event_id"]
    assert service.load_event(
        "plot-a", event_id, "tenant-a", "worldline-a"
    )["event_id"] == event_id
    assert service.load_head(
        "plot-a", "tenant-a", "worldline-a"
    )["latest_event_id"] == event_id
    assert service.load_event("plot-a", event_id) == {}

    acquisition = service.commit_acquisition_plan(
        plot_id="plot-a",
        geometry_hash="geometry-a",
        reason="test-acquisition",
        tenant_id="tenant-a",
        namespace="worldline-a",
    )
    assert service.load_event(
        "plot-a", acquisition["event_id"], "tenant-a", "worldline-a"
    )["event_type"] == "ARCHIVE_ACQUISITION_PLAN"
    assert service.load_event("plot-a", acquisition["event_id"]) == {}
