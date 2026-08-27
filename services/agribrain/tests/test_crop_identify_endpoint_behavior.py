from __future__ import annotations

from fastapi.testclient import TestClient

from services.agribrain.app import main
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.orchestrator_v2.pre_asmae_layer2a import (
    commit_crop_posterior_worldline,
)
from services.agribrain.world_model import canonical_worldline
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
)


NS = PlotNamespace("tenant-crop", "farm-crop", "plot-crop")


def _posterior() -> dict:
    return {
        "contract_version": "crop_identity_posterior_v3",
        "plot_id": NS.plot_id,
        "namespace": {
            "tenant_id": NS.tenant_id,
            "farm_id": NS.farm_id,
            "plot_id": NS.plot_id,
        },
        "authority": "FARMER_CONFIRMED",
        "declared_crop_normalized": "tomato",
        "crop_group_posterior": {
            "solanaceae_veg": 0.9,
            "unknown": 0.1,
        },
        "model_context_group_posterior": {"unknown": 1.0},
        "model_context_support": {
            "status": "unavailable",
            "admitted_physical_acquisition_count": 0,
            "registry_declaration_included": False,
        },
        "top_group": "solanaceae_veg",
        "top_group_probability": 0.9,
        "unknown_probability": 0.1,
        "species_probability_published": False,
        "evidence_quality": {
            "score": 0.0,
            "physical_acquisition_count": 0,
        },
        "content_hash": "crop-content-a",
    }


def _request(monkeypatch, service: CanonicalWorldlineService):
    monkeypatch.setattr(
        canonical_worldline,
        "CanonicalWorldlineService",
        lambda: service,
    )
    main.app.dependency_overrides[
        main.require_internal_service_request
    ] = lambda: NS
    try:
        return TestClient(main.app).post(
            "/v2/crop-identify",
            json={"plot_id": NS.plot_id},
        )
    finally:
        main.app.dependency_overrides.pop(
            main.require_internal_service_request,
            None,
        )


def test_http_endpoint_transports_the_exact_crop_worldline_event(monkeypatch, tmp_path):
    service = CanonicalWorldlineService(root=tmp_path)
    event = commit_crop_posterior_worldline(
        service,
        plot_namespace=NS,
        crop_posterior=_posterior(),
        geometry_version="geometry-a",
        effective_at="2026-08-21T12:00:00Z",
        observation_or_valid_time="2026-08-21T10:00:00Z",
        parent_orchestrator_run_id="run-a",
    )

    response = _request(monkeypatch, service)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "canonical"
    assert body["worldline_event_id"] == event["event_id"]
    assert body["snapshot_ref"] is None
    assert body["identity_authority"] == "FARMER_CONFIRMED"
    assert body["declared_crop"]["code"] == "tomato"


def test_http_endpoint_serves_legacy_snapshot_without_inventing_crop_event(
    monkeypatch, tmp_path,
):
    from services.agribrain.layer05_asmae import plot_snapshot_store

    service = CanonicalWorldlineService(root=tmp_path)
    monkeypatch.setattr(
        plot_snapshot_store,
        "load_latest_plot_snapshot",
        lambda _namespace: {
            "snapshot_id": "ASMAE-SNAPSHOT-legacy",
            "snapshot_ref": "nodes/ASMAE-SNAPSHOT-legacy.json",
            "asmae": {
                "worldline_event_id": "asmae-event-not-a-crop-event",
                "crop_posterior": _posterior(),
            },
        },
    )

    response = _request(monkeypatch, service)

    assert response.status_code == 200
    body = response.json()
    assert body["worldline_event_id"] is None
    assert body["snapshot_ref"] == "nodes/ASMAE-SNAPSHOT-legacy.json"
    assert body["declared_crop"]["code"] == "tomato"

