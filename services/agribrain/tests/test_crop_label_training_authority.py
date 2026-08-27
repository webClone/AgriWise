import pytest

from layer2_veg_int.labels.dataset_builder import TrainingDatasetBuilder
from layer2_veg_int.labels.label_schema import CropLabel
from layer2_veg_int.labels.label_store import InMemoryLabelStore
from services.agribrain.app.crop_training_snapshot_authority import _sha256


def _model_input_receipt(*, plot_id: str, snapshot: dict) -> dict:
    feature_order = list(snapshot)
    tensor = {
        "feature_order": feature_order,
        "input_values": [snapshot[name] for name in feature_order],
        "missingness_mask": [snapshot[name] is None for name in feature_order],
    }
    token = {
        "observation_id": "S2-fixture",
        "observation_hash": "hash-S2-fixture",
        "physical_acquisition_key": "physical-fixture",
        "source_family": "sentinel2",
        "sensing_time": "2026-07-10T10:00:00Z",
        "feature_values": [{
            "name": "ndvi",
            "statistic": "mean",
            "value": 0.7,
        }],
        "quality_admitted": True,
        "quality_class": "clear",
        "support_hash": "support-S2-fixture",
        "day_of_year": 191.0,
        "gdd_coordinates": {},
        "primary_gdd_basis": None,
        "s1_geometry": {
            "orbit_direction": None,
            "relative_orbit": None,
            "incidence_angle": None,
            "polarizations": [],
        },
    }
    payload = {
        "contract_version": "crop-model-input-receipt-v1",
        "plot_namespace": {
            "tenant_id": "tenant-1",
            "farm_id": "farm-1",
            "plot_id": plot_id,
        },
        "crop_cycle_hypothesis_id": "cycle-2026:CROP-SEG-fixture",
        "crop_evidence_ledger_hash": "CROPLEDGERV2-" + "a" * 64,
        "observation_ids": ["S2-fixture"],
        "physical_acquisition_keys": ["physical-fixture"],
        "optical_observation_ids": ["S2-fixture"],
        "sar_observation_ids": [],
        "field_observation_ids": [],
        "observation_tokens": [token],
        "feature_schema_hash": "b" * 64,
        "feature_transform_hash": "c" * 64,
        "normalization_artifact_hash": "d" * 64,
        **tensor,
        "temporal_coordinates": [{
            "observation_id": "S2-fixture",
            "sensing_time": "2026-07-10T10:00:00Z",
            "day_of_year": 191.0,
        }],
        "biological_time_coordinates": [{
            "observation_id": "S2-fixture",
            "gdd_coordinates": {},
            "primary_gdd_basis": None,
        }],
        "sensor_availability_mask": {
            "field": False,
            "optical": True,
            "sar": False,
        },
        "quality_mask": [True],
        "input_tensor_hash": _sha256(tensor),
        "feature_completeness": 1.0,
        "physical_evidence_sufficiency": "sparse",
        "phase_coverage": ["mid"],
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


def _label(
    *,
    source: str = "field_survey",
    confidence: str = "HIGH",
    authority_validated: bool = True,
    with_partitions: bool = True,
    with_receipt: bool = True,
) -> CropLabel:
    plot_id = f"plot-{source}-{confidence}-{with_partitions}"
    snapshot = {
        "data_completeness": 1.0,
        "peak_ndvi": 0.72,
        "ndre_mean": 0.31,
    }
    receipt = (
        _model_input_receipt(plot_id=plot_id, snapshot=snapshot)
        if with_receipt
        else None
    )
    partitions = {
        "farm_id": "farm-1",
        "crop_cycle_id": "cycle-2026",
        "region_partition": "dz-north",
        "season_partition": "2026-summer",
        "sensor_regime": "sentinel-2-l2a",
    }
    if not with_partitions:
        partitions = {}
    return CropLabel(
        label_id=f"label-{source}-{confidence}-{with_partitions}",
        plot_id=plot_id,
        geometry_hash="a" * 64,
        crop_code="tomato",
        crop_group="solanaceae_veg",
        label_source=source,
        label_confidence=confidence,
        authority_validated=authority_validated,
        tenant_id="tenant-1",
        layer1_run_id="l1-run-1",
        feature_vector_snapshot=snapshot,
        crop_model_input_receipt=receipt,
        crop_model_input_receipt_hash=(
            receipt["content_hash"] if receipt else None
        ),
        **partitions,
    )


def _build(label: CropLabel, *, include_historical: bool = False):
    store = InMemoryLabelStore()
    store.save_label(label)
    return TrainingDatasetBuilder(store).build_dataset(
        include_historical=include_historical,
        min_quality_tier="C",
    )


def test_farmer_confirmation_never_becomes_training_sample():
    dataset = _build(
        _label(source="farmer_confirmed", authority_validated=True)
    )

    assert dataset.samples == []
    assert dataset.exclusion_reasons["untrusted_label_source"] == 1


def test_authority_validated_field_survey_with_lineage_is_admitted():
    dataset = _build(_label())

    assert dataset.included_samples == 1
    assert dataset.samples[0].label.crop_code == "tomato"


def test_generic_snapshot_without_crop_model_receipt_is_refused():
    dataset = _build(_label(with_receipt=False))

    assert dataset.samples == []
    assert dataset.exclusion_reasons[
        "invalid_crop_model_input_receipt"
    ] == 1


def test_mutable_feature_attachment_requires_and_stores_exact_receipt():
    label = _label(with_receipt=False)
    snapshot = dict(label.feature_vector_snapshot)
    label.feature_vector_snapshot = None
    store = InMemoryLabelStore()
    store.save_label(label)

    with pytest.warns(UserWarning, match="CropModelInputReceipt"):
        assert store.attach_feature_vector(label.label_id, snapshot) is False
    assert label.feature_vector_snapshot is None

    receipt = _model_input_receipt(
        plot_id=label.plot_id,
        snapshot=snapshot,
    )
    assert store.attach_feature_vector(
        label.label_id,
        snapshot,
        crop_model_input_receipt=receipt,
    ) is True
    assert label.crop_model_input_receipt_hash == receipt["content_hash"]
    assert label.feature_vector_snapshot["flat_features"] == snapshot


def test_capable_source_still_requires_backend_authority_and_high_confidence():
    no_authority = _build(_label(authority_validated=False))
    low_confidence = _build(_label(confidence="LOW"))

    assert no_authority.exclusion_reasons["authority_not_validated"] == 1
    assert low_confidence.exclusion_reasons["label_confidence_not_high"] == 1


def test_training_sample_requires_leakage_control_partitions():
    dataset = _build(_label(with_partitions=False))

    assert dataset.samples == []
    assert dataset.exclusion_reasons["missing_partition_metadata"] == 1


def test_historical_records_remain_ineligible_even_when_inspected():
    dataset = _build(
        _label(source="historical_record"),
        include_historical=True,
    )

    assert dataset.samples == []
    assert dataset.exclusion_reasons["untrusted_label_source"] == 1


def test_authority_partition_metadata_round_trips_through_storage_shape():
    original = _label()
    restored = CropLabel.from_dict(original.to_dict())

    assert restored.authority_validated is True
    assert restored.farm_id == "farm-1"
    assert restored.crop_cycle_id == "cycle-2026"
    assert restored.region_partition == "dz-north"
    assert restored.season_partition == "2026-summer"
    assert restored.sensor_regime == "sentinel-2-l2a"


def test_legacy_label_without_hierarchy_receipt_has_no_trainable_targets():
    document = _label().to_dict()
    document.pop("supportedHierarchyLevels")

    restored = CropLabel.from_dict(document)

    assert restored.supported_hierarchy_levels == []
