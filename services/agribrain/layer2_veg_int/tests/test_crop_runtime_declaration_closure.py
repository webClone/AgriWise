"""Focused tests for crop runtime declarations and training input authority."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from services.agribrain.app.crop_runtime_declaration import (
    FARMER_DECLARATION_AUTHORITY,
    FARMER_DECLARATION_SOURCE,
    persist_farmer_crop_declaration,
)
from services.agribrain.app.crop_training_snapshot_authority import (
    _sha256,
    assess_crop_training_snapshot,
)
from services.agribrain.common.plot_namespace import PlotNamespace


NAMESPACE = PlotNamespace(
    tenant_id="tenant-1",
    farm_id="farm-1",
    plot_id="plot-1",
)


def _matches(document, query):
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict) and "$ne" in expected:
            if actual == expected["$ne"]:
                return False
        elif isinstance(expected, dict) and "$nin" in expected:
            if actual in expected["$nin"]:
                return False
        elif isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif actual != expected:
            return False
    return True


class _Collection:
    def __init__(self, rows=None):
        self.rows = list(deepcopy(rows or []))

    def find_one(self, query, sort=None):
        matches = [row for row in self.rows if _matches(row, query)]
        if sort:
            for key, direction in reversed(sort):
                matches.sort(
                    key=lambda row: row.get(key) or datetime.min.replace(
                        tzinfo=timezone.utc
                    ),
                    reverse=direction < 0,
                )
        return deepcopy(matches[0]) if matches else None

    def insert_one(self, document):
        self.rows.append(deepcopy(document))

    def update_one(self, query, update):
        for row in self.rows:
            if _matches(row, query):
                row.update(deepcopy(update.get("$set") or {}))
                return


class _Database:
    def __init__(
        self,
        *,
        cycles=None,
        farm_id="farm-1",
        tenant_id="tenant-1",
    ):
        self.collections = {
            "Plot": _Collection([{"_id": "plot-1", "farmId": farm_id}]),
            "Farm": _Collection([{"_id": farm_id, "userId": tenant_id}]),
            "CropCycle": _Collection(cycles),
        }

    def __getitem__(self, name):
        return self.collections[name]


def test_declaration_updates_the_same_active_cycle_consumed_by_next_run():
    original_plant_date = datetime(2026, 4, 3, tzinfo=timezone.utc)
    database = _Database(cycles=[{
        "_id": "cycle-active",
        "plotId": "plot-1",
        "cropCode": "wheat",
        "status": "GROWING",
        "plantDate": original_plant_date,
        "plantDateStatus": "confirmed",
        "plantDateSource": "farmer_cycle_form",
        "updatedAt": datetime(2026, 5, 1, tzinfo=timezone.utc),
    }])

    receipt = persist_farmer_crop_declaration(
        database,
        namespace=NAMESPACE,
        crop_code="Fava Bean",
        declared_at=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
    )

    cycle = database["CropCycle"].rows[0]
    assert receipt.crop_cycle_id == "cycle-active"
    assert receipt.crop_code == "fava_bean"
    assert receipt.cycle_created is False
    assert receipt.plant_date_asserted is False
    assert cycle["cropCode"] == "fava_bean"
    assert cycle["declaredCropAuthority"] == FARMER_DECLARATION_AUTHORITY
    assert cycle["declaredCropSource"] == FARMER_DECLARATION_SOURCE
    assert cycle["plantDate"] == original_plant_date
    assert cycle["plantDateStatus"] == "confirmed"


def test_declaration_creates_unknown_date_cycle_when_no_active_cycle_exists():
    database = _Database(cycles=[{
        "_id": "cycle-harvested",
        "plotId": "plot-1",
        "cropCode": "wheat",
        "status": "HARVESTED",
        "updatedAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }])

    receipt = persist_farmer_crop_declaration(
        database,
        namespace=NAMESPACE,
        crop_code="tomato",
        declared_at=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
    )

    assert receipt.cycle_created is True
    created = next(
        cycle for cycle in database["CropCycle"].rows
        if str(cycle["_id"]) == receipt.crop_cycle_id
    )
    assert created["status"] == "PLANNED"
    assert created["plantDate"] is None
    assert created["plantDateStatus"] == "unknown"
    assert created["plantDateSource"] == "unknown"
    assert created["plantDateMin"] is None
    assert created["plantDateMax"] is None


def test_declaration_never_overwrites_a_newer_failed_cycle():
    database = _Database(cycles=[
        {
            "_id": "cycle-growing",
            "plotId": "plot-1",
            "cropCode": "wheat",
            "status": "GROWING",
            "updatedAt": datetime(2026, 6, 1, tzinfo=timezone.utc),
        },
        {
            "_id": "cycle-failed",
            "plotId": "plot-1",
            "cropCode": "maize",
            "status": "FAILED",
            "updatedAt": datetime(2026, 8, 1, tzinfo=timezone.utc),
        },
    ])

    receipt = persist_farmer_crop_declaration(
        database,
        namespace=NAMESPACE,
        crop_code="tomato",
        declared_at=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
    )

    growing, failed = database["CropCycle"].rows
    assert receipt.crop_cycle_id == "cycle-growing"
    assert growing["cropCode"] == "tomato"
    assert failed["cropCode"] == "maize"
    assert failed.get("declaredCropAuthority") is None


def test_declaration_fails_closed_on_farm_namespace_mismatch():
    with pytest.raises(PermissionError, match="plot_namespace_farm_mismatch"):
        persist_farmer_crop_declaration(
            _Database(farm_id="other-farm"),
            namespace=NAMESPACE,
            crop_code="tomato",
        )


def test_declaration_fails_closed_on_tenant_ownership_mismatch():
    with pytest.raises(
        PermissionError, match="plot_namespace_tenant_mismatch"
    ):
        persist_farmer_crop_declaration(
            _Database(tenant_id="another-tenant"),
            namespace=NAMESPACE,
            crop_code="tomato",
        )


def _receipt(snapshot, *, namespace=None):
    feature_order = ["peak_ndvi", "vv_mean_db"]
    input_values = [snapshot["peak_ndvi"], snapshot["vv_mean_db"]]
    tensor = {
        "feature_order": feature_order,
        "input_values": input_values,
        "missingness_mask": [False, False],
    }
    tokens = [
        {
            "observation_id": observation_id,
            "observation_hash": f"hash-{observation_id}",
            "physical_acquisition_key": physical_key,
            "source_family": "sentinel2",
            "sensing_time": sensing_time,
            "feature_values": [{
                "name": "ndvi",
                "statistic": "mean",
                "value": ndvi,
            }],
            "quality_admitted": True,
            "quality_class": "clear",
            "support_hash": f"support-{observation_id}",
            "day_of_year": day_of_year,
            "gdd_coordinates": {},
            "primary_gdd_basis": None,
            "s1_geometry": {
                "orbit_direction": None,
                "relative_orbit": None,
                "incidence_angle": None,
                "polarizations": [],
            },
        }
        for observation_id, physical_key, sensing_time, day_of_year, ndvi in (
            ("S2-A", "physical-a", "2026-07-01T10:00:00Z", 182.0, 0.6),
            ("S2-B", "physical-b", "2026-07-11T10:00:00Z", 192.0, 0.7),
        )
    ]
    payload = {
        "contract_version": "crop-model-input-receipt-v1",
        "plot_namespace": namespace or {
            "tenant_id": "tenant-1",
            "farm_id": "farm-1",
            "plot_id": "plot-1",
        },
        "crop_cycle_hypothesis_id": "cycle-2026:CROP-SEG-1",
        "crop_evidence_ledger_hash": "CROPLEDGERV2-" + "a" * 64,
        "observation_ids": ["S2-A", "S2-B"],
        "physical_acquisition_keys": ["physical-a", "physical-b"],
        "optical_observation_ids": ["S2-A", "S2-B"],
        "sar_observation_ids": [],
        "field_observation_ids": [],
        "observation_tokens": tokens,
        "feature_schema_hash": "b" * 64,
        "feature_transform_hash": "c" * 64,
        "normalization_artifact_hash": "d" * 64,
        **tensor,
        "temporal_coordinates": [
            {
                "observation_id": token["observation_id"],
                "sensing_time": token["sensing_time"],
                "day_of_year": token["day_of_year"],
            }
            for token in tokens
        ],
        "biological_time_coordinates": [
            {
                "observation_id": token["observation_id"],
                "gdd_coordinates": {},
                "primary_gdd_basis": None,
            }
            for token in tokens
        ],
        "sensor_availability_mask": {
            "field": False,
            "optical": True,
            "sar": False,
        },
        "quality_mask": [True, True],
        "input_tensor_hash": _sha256(tensor),
        "feature_completeness": 1.0,
        "physical_evidence_sufficiency": "sparse",
        "phase_coverage": ["early", "mid"],
        "domain_compatibility": "compatible",
        "calibration_validity": "unavailable",
        "model_execution_eligible": True,
        "publication_eligible": False,
        "publication_blockers": ["probability_calibration_not_validated"],
    }
    content_hash = _sha256(payload)
    return {
        **payload,
        "receipt_id": "CROP-MODEL-INPUT-" + content_hash[:24],
        "content_hash": content_hash,
    }


def test_training_snapshot_requires_exact_ledger_receipt_and_tensor_binding():
    snapshot = {"peak_ndvi": 0.71, "vv_mean_db": -12.4}
    receipt = _receipt(snapshot)

    assessment = assess_crop_training_snapshot(
        feature_vector_snapshot={"flat_features": snapshot},
        crop_model_input_receipt=receipt,
        tenant_id="tenant-1",
        farm_id="farm-1",
        plot_id="plot-1",
        crop_cycle_id="cycle-2026",
        expected_receipt_hash=receipt["content_hash"],
    )

    assert assessment.eligible is True
    assert assessment.reasons == ()


def test_generic_or_tampered_training_snapshot_is_refused():
    snapshot = {"peak_ndvi": 0.71, "vv_mean_db": -12.4}
    missing_receipt = assess_crop_training_snapshot(
        feature_vector_snapshot=snapshot,
        crop_model_input_receipt=None,
        tenant_id="tenant-1",
        farm_id="farm-1",
        plot_id="plot-1",
        crop_cycle_id="cycle-2026",
    )
    assert missing_receipt.eligible is False
    assert "missing_crop_model_input_receipt" in missing_receipt.reasons

    receipt = _receipt(snapshot)
    tampered = assess_crop_training_snapshot(
        feature_vector_snapshot={**snapshot, "peak_ndvi": 0.19},
        crop_model_input_receipt=receipt,
        tenant_id="tenant-1",
        farm_id="farm-1",
        plot_id="plot-1",
        crop_cycle_id="cycle-2026",
        expected_receipt_hash=receipt["content_hash"],
    )
    assert tampered.eligible is False
    assert "feature_snapshot_tensor_mismatch" in tampered.reasons


def test_training_receipt_requires_stored_hash_and_exact_crop_cycle():
    snapshot = {"peak_ndvi": 0.71, "vv_mean_db": -12.4}
    receipt = _receipt(snapshot)

    no_stored_hash = assess_crop_training_snapshot(
        feature_vector_snapshot=snapshot,
        crop_model_input_receipt=receipt,
        tenant_id="tenant-1",
        farm_id="farm-1",
        plot_id="plot-1",
        crop_cycle_id="cycle-2026",
    )
    assert no_stored_hash.eligible is False
    assert (
        "missing_stored_crop_model_input_receipt_hash"
        in no_stored_hash.reasons
    )

    wrong_cycle = assess_crop_training_snapshot(
        feature_vector_snapshot=snapshot,
        crop_model_input_receipt=receipt,
        tenant_id="tenant-1",
        farm_id="farm-1",
        plot_id="plot-1",
        crop_cycle_id="another-cycle",
        expected_receipt_hash=receipt["content_hash"],
    )
    assert wrong_cycle.eligible is False
    assert "crop_model_input_cycle_mismatch" in wrong_cycle.reasons


def test_training_receipt_requires_observation_aligned_quality_mask():
    snapshot = {"peak_ndvi": 0.71, "vv_mean_db": -12.4}
    receipt = _receipt(snapshot)
    receipt["quality_mask"] = [True]
    payload = {
        key: value
        for key, value in receipt.items()
        if key not in {"receipt_id", "content_hash"}
    }
    receipt["content_hash"] = _sha256(payload)
    receipt["receipt_id"] = (
        "CROP-MODEL-INPUT-" + receipt["content_hash"][:24]
    )

    assessment = assess_crop_training_snapshot(
        feature_vector_snapshot=snapshot,
        crop_model_input_receipt=receipt,
        tenant_id="tenant-1",
        farm_id="farm-1",
        plot_id="plot-1",
        crop_cycle_id="cycle-2026",
        expected_receipt_hash=receipt["content_hash"],
    )
    assert assessment.eligible is False
    assert "crop_model_input_quality_mask_misaligned" in assessment.reasons
