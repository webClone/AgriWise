from __future__ import annotations

import copy
from datetime import date

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.scientific_contracts.crop_governance import (
    CropInfluenceManifestV1,
    CropModelReceiptV1,
)


_HASH = "a" * 64


def _model_receipt(**updates):
    values = {
        "model_family": "parcel-transformer-ssm",
        "semantic_version": "1.0.0",
        "artifact_sha256": _HASH,
        "feature_schema_version": "crop-sequence-v2",
        "feature_schema_hash": "b" * 64,
        "class_hierarchy_version": "crop-taxonomy-v2",
        "training_dataset_manifest_hash": "c" * 64,
        "calibration_artifact_hash": "d" * 64,
        "validation_report_hash": "e" * 64,
        "region_domain_compatibility": {"region": "DZ-north", "sensor": "S1+S2"},
        "production_eligible": True,
        "inference_device": "cpu",
        "runtime_version": "onnxruntime-1.23",
        "deterministic_preprocessing_version": "crop-preprocess-v2",
    }
    values.update(updates)
    return CropModelReceiptV1(**values)


def test_model_receipt_round_trip_is_hash_stable_and_tamper_evident():
    receipt = _model_receipt()
    payload = receipt.to_dict()
    assert CropModelReceiptV1.from_dict(payload) == receipt
    tampered = copy.deepcopy(payload)
    tampered["semantic_version"] = "1.0.1"
    with pytest.raises(ValueError, match="content_hash mismatch"):
        CropModelReceiptV1.from_dict(tampered)


def test_production_model_receipt_fails_closed_without_release_artifacts():
    with pytest.raises(ValueError, match="missing"):
        _model_receipt(calibration_artifact_hash="")
    diagnostic = _model_receipt(
        production_eligible=False,
        artifact_sha256="",
        calibration_artifact_hash="",
        eligibility_reasons=("external_release_validation_missing",),
    )
    assert diagnostic.production_eligible is False
    assert diagnostic.eligibility_reasons == ("external_release_validation_missing",)


def _manifest(**updates):
    values = {
        "namespace": PlotNamespace("tenant", "farm", "plot"),
        "crop_cycle_id": "cycle-1",
        "independent_evidence_ids": ("scene-a", "scene-b"),
        "asmae_source_observation_ids": ("scene-b", "scene-c"),
        "dependent_refinement_features": ("structure", "phenology_progress"),
        "maximum_allowed_posterior_influence": 0.15,
        "actual_posterior_change": 0.04,
        "lineage_parent_id": "crop-parent",
        "lineage_child_id": None,
        "crop_posterior_parent_hash": "1" * 64,
        "crop_posterior_child_hash": "2" * 64,
        "asmae_run_id": "asmae-run",
        "child_asmae_run_scheduled": False,
        "refinement_iteration": 0,
    }
    values.update(updates)
    return CropInfluenceManifestV1(**values)


def test_influence_manifest_computes_overlap_and_never_counts_it_as_new_evidence():
    manifest = _manifest()
    assert manifest.overlap_set == ("scene-b",)
    assert manifest.to_dict()["double_count_policy"] == (
        "overlap_is_dependent_not_new_evidence"
    )
    assert CropInfluenceManifestV1.from_dict(manifest.to_dict()) == manifest


def test_influence_manifest_rejects_cap_violation_and_second_child_iteration():
    with pytest.raises(ValueError, match="exceeded"):
        _manifest(actual_posterior_change=0.16)
    with pytest.raises(ValueError, match="At most one"):
        _manifest(refinement_iteration=2)
    with pytest.raises(ValueError, match="requires lineage_child_id"):
        _manifest(child_asmae_run_scheduled=True, refinement_iteration=1)


def test_scheduled_child_is_explicit_and_hash_tampering_is_rejected():
    manifest = _manifest(
        child_asmae_run_scheduled=True,
        refinement_iteration=1,
        lineage_child_id="crop-child",
    )
    payload = manifest.to_dict()
    tampered = copy.deepcopy(payload)
    tampered["actual_posterior_change"] = 0.05
    with pytest.raises(ValueError, match="content_hash mismatch"):
        CropInfluenceManifestV1.from_dict(tampered)


def _asmae_input(manifest, **updates):
    from services.agribrain.layer05_asmae.schema import ASMAEInput

    values = {
        "plot_id": "plot",
        "run_id": "asmae-run",
        "polygon_geojson": {},
        "geometry_hash": "geometry",
        "start_date": date(2026, 8, 1),
        "end_date": date(2026, 8, 10),
        "layer0_source_packages": {},
        "crop_posterior": {"content_hash": "1" * 64},
        "crop_posterior_lineage": "1" * 64,
        "crop_influence_manifest": manifest.to_dict(),
        "crop_influence_manifest_hash": manifest.content_hash,
        "mode": "shadow",
    }
    values.update(updates)
    return ASMAEInput(**values)


def test_asmae_input_cache_job_and_snapshot_bind_influence_manifest():
    from services.agribrain.layer05_asmae.cache import get_asmae_cache_key
    from services.agribrain.layer05_asmae.job_manifest import build_job_identity
    from services.agribrain.layer05_asmae.snapshot_store import compute_snapshot_id

    first = _manifest(actual_posterior_change=0.0, crop_posterior_child_hash="")
    second = _manifest(
        actual_posterior_change=0.0,
        crop_posterior_child_hash="",
        independent_evidence_ids=("scene-a", "scene-b", "scene-d"),
    )
    first_input = _asmae_input(first)
    second_input = _asmae_input(second)
    assert get_asmae_cache_key(first_input) != get_asmae_cache_key(second_input)

    context = {
        "plot_namespace": {
            "tenant_id": "tenant", "farm_id": "farm", "plot_id": "plot"
        },
        "tenant_id": "tenant",
        "farm_id": "farm",
        "plot_id": "plot",
        "crop_posterior_lineage": "1" * 64,
        "crop_influence_manifest": first.to_dict(),
        "crop_influence_manifest_hash": first.content_hash,
    }
    identity = build_job_identity("plot", context, {})
    assert identity["crop_influence_manifest_hash"] == first.content_hash

    base_result = {
        "plot_id": "plot",
        "crop_posterior_lineage": "1" * 64,
        "crop_influence_manifest_hash": first.content_hash,
        "plot_state_artifact": {"content_hash": "state", "as_of": "2026-08-10"},
    }
    changed_result = dict(base_result)
    changed_result["crop_influence_manifest_hash"] = second.content_hash
    assert compute_snapshot_id(base_result, geometry_hash="geometry") != (
        compute_snapshot_id(changed_result, geometry_hash="geometry")
    )


def test_asmae_input_rejects_manifest_lineage_mismatch():
    manifest = _manifest(actual_posterior_change=0.0, crop_posterior_child_hash="")
    with pytest.raises(ValueError, match="posterior lineage mismatch"):
        _asmae_input(manifest, crop_posterior_lineage="f" * 64)


def test_influence_manifest_independence_is_derived_from_admitted_ledger_clusters():
    from services.agribrain.orchestrator_v2.runner import (
        _crop_influence_evidence_ids,
        _crop_ledger_independent_evidence_ids,
    )

    records = [
        {
            "observation_id": "daily-provider-stat",
            "independent_observation_count": 1,
            "usable": True,
        },
        {
            "observation_id": "physical-processing-product",
            "physical_acquisition_key": "physical-acquisition",
            "independent_evidence": True,
            "quality_admitted": True,
        },
    ]
    ledger = {
        "independence_clusters": [
            {
                "cluster_id": "physical-acquisition",
                "independence_eligible": True,
                "admitted": True,
            },
            {
                "cluster_id": "rejected-acquisition",
                "independence_eligible": True,
                "admitted": False,
            },
            {
                "cluster_id": "unresolved:daily-provider-stat",
                "independence_eligible": False,
                "admitted": False,
            },
        ]
    }

    # The compatibility helper demonstrates the regression: a legacy daily
    # provider statistic can look independent in the raw transport.
    assert _crop_influence_evidence_ids(
        records, independent_only=True
    ) == ("daily-provider-stat", "physical-acquisition")
    # The manifest must use the same admitted physical clusters that
    # ASMAEInput will verify from the canonical ledger.
    assert _crop_ledger_independent_evidence_ids(ledger) == (
        "physical-acquisition",
    )
