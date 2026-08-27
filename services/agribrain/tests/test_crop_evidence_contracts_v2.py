from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from services.agribrain.scientific_contracts.crop_evidence import (
    CROP_EVIDENCE_LEDGER_CONTRACT_VERSION,
    CROP_OBSERVATION_CONTRACT_VERSION,
    CanonicalCropObservationV2,
    CropEvidenceLedgerV2,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation


NAMESPACE = {
    "tenant_id": "tenant-a",
    "farm_id": "farm-a",
    "plot_id": "plot-a",
}


def _observation(
    *,
    physical_key: str = "S2ACQ-a",
    product_id: str = "S2B_product_a",
    processing_timestamp: str = "2026-08-06T14:24:06+00:00",
    content_hash: str = "content-a",
) -> dict:
    return {
        "contract_version": "legacy-input-is-upgraded",
        "record_type": "CanonicalCropObservation",
        "observation_id": f"crop-{physical_key}",
        "timestamp": "2026-08-06T10:25:59+00:00",
        "date": "2026-08-06",
        "physical_acquisition_key": physical_key,
        "physical_identity_complete": True,
        "independence_identity_available": True,
        "source_family": "sentinel2",
        "provider": "copernicus",
        "mission": "S2B",
        "sensor": "MSI",
        "tile_id": "T31SDA",
        "relative_orbit": "R108",
        "plot_geometry_hash": "geometry-a",
        "quality_admitted": True,
        "quality_class": "good",
        "quality_rejection_reasons": [],
        "valid_pixel_count": 8,
        "field_pixel_count": 9,
        "valid_fraction": 8 / 9,
        "cloud_fraction": 1 / 9,
        "shadow_fraction": 0.0,
        "snow_fraction": 0.0,
        "nodata_fraction": 0.0,
        "reading_reliability": 0.8,
        "pixel_support_contract": {
            "support_hash": "support-a",
            "support_definition": "plot&DATAMASK&SCL&finite",
            "grid_identity": {
                "shape": [3, 3],
                "transform": [0, 1, 0, 3, 0, -1],
                "scene_crs": "EPSG:4326",
                "plot_geometry_crs": "EPSG:4326",
                "plot_geometry_hash": "geometry-a",
            },
        },
        "band_statistics": {
            "B08": {"valid_count": 8, "mean": 0.2, "median": 0.19},
            "B04": {"valid_count": 8, "mean": 0.1, "median": 0.09},
        },
        "index_statistics": {
            "ndvi": {"valid_count": 8, "mean": 1 / 3, "median": 0.34},
            "cired": {"valid_count": 8, "mean": 0.47},
        },
        "ndvi_mean": 1 / 3,
        "environmental_context": {
            "day_of_year": 218,
            "gdd_accumulated": 420.0,
            "season_progress_fraction": 0.25,
        },
        "calibration_domain_compatibility": "compatible",
        "geographical_domain_compatibility": "compatible",
        "direct_observation": True,
        "provider_product_id": product_id,
        "content_hash": content_hash,
        "processing_lineage": [{
            "provider_product_id": product_id,
            "catalog_item_id": product_id,
            "processing_timestamp": processing_timestamp,
            "processing_baseline": "N0512",
            "content_hash": content_hash,
            "process_request_hash": "request-a",
            "provider_response_hash": "response-a",
        }],
    }


def test_observation_v2_is_namespace_complete_immutable_and_hash_stable() -> None:
    raw = _observation()
    reordered = dict(reversed(list(raw.items())))
    reordered["index_statistics"] = dict(
        reversed(list(raw["index_statistics"].items()))
    )

    first = CanonicalCropObservationV2.from_mapping(
        raw, plot_namespace=NAMESPACE,
    )
    second = CanonicalCropObservationV2.from_mapping(
        reordered, plot_namespace=NAMESPACE,
    )

    assert first.observation_hash == second.observation_hash
    assert first.to_dict()["contract_version"] == CROP_OBSERVATION_CONTRACT_VERSION
    assert first.to_dict()["namespace"] == NAMESPACE
    assert first.to_dict()["plot_namespace"] == NAMESPACE
    assert first.to_dict()["tenant_id"] == "tenant-a"
    assert first.to_dict()["feature_contributions"]
    assert first.to_dict()["quality_assessment"]["grid_identity_hash"].startswith("GRID-")
    assert first.namespace.to_tuple() == ("tenant-a", "farm-a", "plot-a")
    assert first.spectral_summary["index_statistics"]["ndvi"]["mean"] == pytest.approx(1 / 3)
    with pytest.raises(FrozenInstanceError):
        first.observation_id = "mutated"  # type: ignore[misc]

    detached = first.to_dict()
    detached["index_statistics"]["ndvi"]["mean"] = 0.99
    assert first.to_dict()["index_statistics"]["ndvi"]["mean"] == pytest.approx(1 / 3)


def test_observation_round_trip_validates_hash_and_rejects_incomplete_namespace() -> None:
    observation = CanonicalCropObservationV2.from_mapping(
        _observation(), plot_namespace=NAMESPACE,
    )
    restored = CanonicalCropObservationV2.from_mapping(observation.to_dict())
    assert restored.observation_hash == observation.observation_hash

    tampered = observation.to_dict()
    tampered["ndvi_mean"] = 0.99
    with pytest.raises(ContractViolation, match="crop_observation_hash_mismatch"):
        CanonicalCropObservationV2.from_mapping(tampered)
    with pytest.raises(ContractViolation, match="full_plot_namespace"):
        CanonicalCropObservationV2.from_mapping(
            _observation(),
            plot_namespace={"tenant_id": "tenant-a", "plot_id": "plot-a"},
        )


def test_ledger_clusters_processing_versions_without_counting_new_evidence() -> None:
    first = CanonicalCropObservationV2.from_mapping(
        _observation(), plot_namespace=NAMESPACE,
    )
    reprocessed = CanonicalCropObservationV2.from_mapping(
        _observation(
            product_id="S2B_product_b",
            processing_timestamp="2026-08-06T14:56:01+00:00",
            content_hash="content-b",
        ),
        plot_namespace=NAMESPACE,
    )
    later = CanonicalCropObservationV2.from_mapping(
        _observation(
            physical_key="S2ACQ-b",
            product_id="S2B_product_c",
            processing_timestamp="2026-08-11T14:24:06+00:00",
            content_hash="content-c",
        ),
        plot_namespace=NAMESPACE,
    )

    ledger = CropEvidenceLedgerV2.from_observations(
        NAMESPACE, [first, reprocessed, later],
    )
    reversed_ledger = CropEvidenceLedgerV2.from_observations(
        NAMESPACE, [later, reprocessed, first],
    )
    payload = ledger.to_dict()

    assert payload["contract_version"] == CROP_EVIDENCE_LEDGER_CONTRACT_VERSION
    assert payload["observation_count"] == 3
    assert payload["independence_cluster_count"] == 2
    assert payload["admitted_independent_cluster_count"] == 2
    assert payload["namespace"] == NAMESPACE
    assert payload["evidence_counts"]["admitted_physical_observations"] == 2
    assert payload["evidence_counts"]["admitted_optical_acquisitions"] == 2
    assert payload["evidence_counts"]["admitted_sar_acquisitions"] == 0
    assert payload["evidence_counts"]["independent_feature_family_count"] >= 1
    assert payload["temporal_span"]["observation_time_count"] == 2
    assert payload["crop_season_coverage"]["early"] is True
    assert ledger.ledger_hash == reversed_ledger.ledger_hash
    duplicate_cluster = next(
        item for item in payload["independence_clusters"]
        if item["cluster_id"] == "S2ACQ-a"
    )
    assert len(duplicate_cluster["observation_hashes"]) == 2
    assert len(duplicate_cluster["processing_lineage"]) == 2
    assert duplicate_cluster["independent_evidence_count"] == 1
    duplicate_items = [
        item for item in payload["evidence_items"]
        if item["independence_cluster_id"] == "S2ACQ-a"
    ]
    assert len(duplicate_items) == 2
    assert sum(item["model_use_eligible"] for item in duplicate_items) == 1
    assert sum(item["species_level_eligible"] for item in duplicate_items) == 1
    assert any(
        "superseded_processing_lineage" in item["rejection_or_demotion_reasons"]
        for item in duplicate_items
    )
    ndvi_contribution = next(
        item for item in payload["feature_contribution_index"]
        if item["feature_key"] == "ndvi:mean"
    )
    assert ndvi_contribution["admitted_independent_cluster_count"] == 2


def test_ledger_serialization_is_self_validating_and_namespace_scoped() -> None:
    observation = CanonicalCropObservationV2.from_mapping(
        _observation(), plot_namespace=NAMESPACE,
    )
    ledger = CropEvidenceLedgerV2.from_observations(NAMESPACE, [observation])
    restored = CropEvidenceLedgerV2.from_dict(ledger.to_dict())
    assert restored.ledger_hash == ledger.ledger_hash

    tampered = ledger.to_dict()
    tampered["independence_cluster_count"] = 99
    with pytest.raises(ContractViolation, match="derived_fields_mismatch"):
        CropEvidenceLedgerV2.from_dict(tampered)

    with pytest.raises(ContractViolation, match="namespace_mismatch"):
        CropEvidenceLedgerV2.from_observations(
            {**NAMESPACE, "plot_id": "plot-b"}, [observation],
        )


def test_derived_observation_is_lineage_but_not_independent_model_support() -> None:
    raw = _observation(physical_key="S2ACQ-derived")
    raw["direct_observation"] = False
    raw["parent_observation_ids"] = ["CROPOBS-parent"]
    observation = CanonicalCropObservationV2.from_mapping(
        raw, plot_namespace=NAMESPACE,
    )
    ledger = CropEvidenceLedgerV2.from_observations(NAMESPACE, [observation])
    payload = ledger.to_dict()
    item = payload["evidence_items"][0]

    assert observation.independent_evidence is False
    assert payload["admitted_independent_cluster_count"] == 0
    assert payload["evidence_counts"]["admitted_physical_observations"] == 0
    assert item["direct_or_derived"] == "derived"
    assert item["model_use_eligible"] is False
    assert item["group_level_eligible"] is False
    assert "derived_observation_not_independent" in (
        item["rejection_or_demotion_reasons"]
    )
