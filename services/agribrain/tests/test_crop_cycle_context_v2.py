from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from services.agribrain.common.crop_cycle_context import (
    CROP_CYCLE_CONTEXT_CONTRACT_VERSION,
    CanonicalCropCycleContextV2,
)
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.orchestrator_v2.run_entrypoint import _build_inputs
from services.agribrain.scientific_contracts import (
    CanonicalCropCycleContextV2 as ExportedCropCycleContextV2,
)


def _context(*, refs=("task:b", "input:a", "task:b"), **overrides):
    values = {
        "plot_namespace": PlotNamespace(
            tenant_id="tenant-1", farm_id="farm-1", plot_id="plot-1"
        ),
        "crop_cycle_id": "cycle-1",
        "geometry_version": "sha256:geometry-1",
        "effective_at": "2026-06-02T12:30:00.000Z",
        "declared_crop_code": "Tomato",
        "declared_crop_authority": "farmer_confirmed",
        "declared_crop_at": "2026-06-02T12:00:00.000Z",
        "declared_crop_source": "authenticated_farmer_crop_identity",
        "variety": "Roma",
        "irrigation_type": "DRIP",
        "plant_date_status": "confirmed",
        "plant_date_source": "crop_cycle_registry",
        "plant_date_confidence": 1.0,
        "plant_date_nominal": "2026-06-01T00:00:00.000Z",
        "plant_date_range_start": "2026-06-01T00:00:00.000Z",
        "plant_date_range_end": "2026-06-01T00:00:00.000Z",
        "expected_harvest_date": "2026-09-15T00:00:00.000Z",
        "actual_harvest_date": None,
        "administrative_status": "growing",
        "management_event_refs": refs,
    }
    values.update(overrides)
    return CanonicalCropCycleContextV2(**values)


def test_crop_cycle_context_is_frozen_normalized_and_hash_stable():
    first = _context()
    reordered = _context(refs=("input:a", "task:b"))

    assert first.contract_version == CROP_CYCLE_CONTEXT_CONTRACT_VERSION
    assert first.declared_crop_code == "tomato"
    assert ExportedCropCycleContextV2 is CanonicalCropCycleContextV2
    assert first.declared_crop_authority == "FARMER_CONFIRMED"
    assert first.declared_crop_at == "2026-06-02T12:00:00.000Z"
    assert first.declared_crop_source == "authenticated_farmer_crop_identity"
    assert first.effective_at == "2026-06-02T12:30:00.000Z"
    assert first.irrigation_type == "drip"
    assert first.administrative_status == "GROWING"
    assert first.management_event_refs == ("input:a", "task:b")
    assert first.content_hash == reordered.content_hash
    assert first.content_hash == (
        "7c3c905f3ff6139d1ff9c3c23f6aa7fb4560e95da86fb7f67201e26ab982d8b3"
    )
    assert first.to_dict()["plant_date"] == "2026-06-01T00:00:00.000Z"
    assert first.to_dict()["planting_date"] == first.to_dict()["plant_date"]
    assert first.to_dict()["plant_date_status"] == "confirmed"
    assert first.to_dict()["plant_date_min"] == first.to_dict()["plant_date"]
    assert first.to_dict()["plant_date_max"] == first.to_dict()["plant_date"]
    assert first.to_dict()["administrative_status_role"] == (
        "workflow_only_not_phenology_evidence"
    )
    assert first.to_dict()[
        "phenology_from_administrative_status_allowed"
    ] is False
    with pytest.raises(FrozenInstanceError):
        first.crop_cycle_id = "different"  # type: ignore[misc]


def test_crop_cycle_context_mapping_verifies_hash_and_rejects_phenology():
    payload = _context().to_dict()
    restored = CanonicalCropCycleContextV2.from_mapping(payload)
    assert restored == _context(refs=("input:a", "task:b"))

    tampered = {**payload, "administrative_status": "HARVESTED"}
    with pytest.raises(ValueError, match="content_hash"):
        CanonicalCropCycleContextV2.from_mapping(tampered)

    phenology_coercion = {**payload, "stage": "FLOWERING"}
    with pytest.raises(ValueError, match="phenology"):
        CanonicalCropCycleContextV2.from_mapping(
            phenology_coercion, verify_hash=False
        )


@pytest.mark.parametrize(
    "authority",
    ["FARMER_CONFIRMED", "OFFICIAL_PARCEL_LABEL"],
)
def test_crop_cycle_context_accepts_release_authority_taxonomy(authority):
    assert _context(declared_crop_authority=authority).declared_crop_authority == authority


@pytest.mark.parametrize("status", ["confirmed", "estimated", "interval", "unknown"])
def test_crop_cycle_context_uses_closed_plant_date_status_taxonomy(status):
    overrides = {"plant_date_status": status}
    if status == "unknown":
        overrides.update({
            "plant_date_nominal": None,
            "plant_date_range_start": None,
            "plant_date_range_end": None,
            "plant_date_confidence": None,
            "plant_date_source": "unknown",
        })
    value = _context(**overrides)
    assert value.plant_date_status == status

    with pytest.raises(ValueError, match="plant_date_status"):
        _context(plant_date_status="registry_declared")


def test_run_entrypoint_transports_full_cycle_without_status_to_phenology():
    cycle = _context()
    inputs = _build_inputs(
        {
            "tenant_id": "tenant-1",
            "farm_id": "farm-1",
            "plot_id": "plot-1",
            "geometry_hash": "sha256:geometry-1",
            "crop": "tomato",
            "stage": "FLOWERING",  # legacy administrative alias is ignored
            "administrative_status": "GROWING",
            "crop_cycle_context": cycle.to_dict(),
            "polygon": {
                "type": "Polygon",
                "coordinates": [
                    [[2.0, 36.0], [2.1, 36.0], [2.0, 36.1], [2.0, 36.0]]
                ],
            },
        },
        authenticated_namespace=cycle.plot_namespace,
    )

    assert inputs.crop_cycle_context == cycle
    assert inputs.crop_config["crop_cycle_context_hash"] == cycle.content_hash
    assert inputs.crop_config["crop_cycle_id"] == "cycle-1"
    assert inputs.crop_config["crop"] == "tomato"
    assert inputs.crop_config["plant_date"] == "2026-06-01T00:00:00.000Z"
    assert inputs.crop_config["planting_date"] == "2026-06-01T00:00:00.000Z"
    assert inputs.crop_config["plant_date_status"] == "confirmed"
    assert inputs.crop_config["plant_date_min"] == "2026-06-01T00:00:00.000Z"
    assert inputs.crop_config["plant_date_max"] == "2026-06-01T00:00:00.000Z"
    assert inputs.crop_config["irrigation_type"] == "drip"
    assert inputs.crop_config["crop_cycle_effective_at"] == (
        "2026-06-02T12:30:00.000Z"
    )
    assert inputs.crop_config["declared_crop_authority"] == "FARMER_CONFIRMED"
    assert inputs.crop_config["declared_crop_at"] == "2026-06-02T12:00:00.000Z"
    assert inputs.crop_config["declared_crop_source"] == (
        "authenticated_farmer_crop_identity"
    )
    assert inputs.crop_config["administrative_status"] == "GROWING"
    assert inputs.crop_config["administrative_status_is_phenology"] is False
    assert inputs.crop_config["stage"] == "unknown"
    assert inputs.operational_context["crop_cycle_context"] == cycle.to_dict()


def test_run_entrypoint_rejects_cycle_namespace_and_status_phenology_source():
    cycle = _context()
    with pytest.raises(ValueError, match="namespace"):
        _build_inputs(
            {
                "tenant_id": "tenant-1",
                "farm_id": "farm-1",
                "plot_id": "plot-other",
                "crop_cycle_context": cycle.to_dict(),
            },
            authenticated_namespace=PlotNamespace(
                tenant_id="tenant-1",
                farm_id="farm-1",
                plot_id="plot-other",
            ),
        )

    with pytest.raises(ValueError, match="cannot supply phenology"):
        _build_inputs(
            {
                "tenant_id": "tenant-1",
                "farm_id": "farm-1",
                "plot_id": "plot-1",
                "crop_cycle_context": cycle.to_dict(),
                "phenology_stage": "FLOWERING",
                "phenology_stage_source": "administrative_status",
            },
            authenticated_namespace=cycle.plot_namespace,
        )
