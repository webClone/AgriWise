from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from sklearn.impute import SimpleImputer

from services.agribrain.layer2_veg_int.labels.classifier import (
    PRODUCTION_VALIDATION_CONTRACT_VERSION,
    HierarchicalCropClassifier,
    TrivialClassifier,
    _release_validation_hash,
)
from services.agribrain.layer2_veg_int.features.crop_feature_vector import (
    crop_feature_schema_receipt,
)


ARTIFACT_HASH = "a" * 64


def _base_metadata() -> dict:
    feature_names = ["feature_a", "feature_b"]
    return {
        "model_version": "test-model",
        "feature_vector_version": "test-features",
        "label_schema_version": "test-labels",
        "feature_order_hash": hashlib.sha256(
            ",".join(sorted(feature_names)).encode("utf-8")
        ).hexdigest(),
        "feature_schema_hash": crop_feature_schema_receipt().content_hash,
        "level_status": {"L2": "trained"},
        "validation_reports": {
            "L2": {
                "validation_status": "evaluated",
                "folds_used": 3,
                "internal_validation_accuracy": 0.99,
            }
        },
        "training_dataset_type": "real_world",
        "production_eligible": True,
        "allowed_for": ["production_inference"],
        "artifact_sha256": ARTIFACT_HASH,
        "class_hierarchy_version": "crop-hierarchy-v1",
        "training_dataset_manifest_hash": "b" * 64,
        "calibration_artifact_hash": "c" * 64,
        "region_domain_compatibility": {"region": "dz-north"},
        "inference_device": "cpu",
        "runtime_version": "python-3.13-sklearn-test",
        "deterministic_preprocessing_version": "crop-preprocessor-v1",
    }


def _classifier(metadata: dict) -> HierarchicalCropClassifier:
    classifier = HierarchicalCropClassifier(model_dir="unused")
    classifier.feature_names = ["feature_a", "feature_b"]
    classifier.models = {"L2": object()}
    classifier.imputer = object()
    classifier.metadata = metadata
    return classifier


def test_high_internal_accuracy_cannot_self_authorize_production() -> None:
    classifier = _classifier(_base_metadata())
    status = classifier._post_load_eligibility(
        actual_artifact_sha256=ARTIFACT_HASH
    )
    assert not status
    assert status["blocked_reason"] == "invalid_model_deployment_contract"
    assert "deployment_validation_missing" in status["missing_or_invalid"]
    assert classifier.production_eligible is False


def test_complete_external_release_contract_is_required_for_eligibility() -> None:
    metadata = _base_metadata()
    release = {
        "contract_version": PRODUCTION_VALIDATION_CONTRACT_VERSION,
        "release_gate_passed": True,
        "split_contract": {
            "farm_disjoint": True,
            "year_disjoint": True,
            "region_transfer_evaluated": True,
            "observation_leakage_checked": True,
        },
        "metrics_by_level": {
            "L2": {
                "macro_f1": 0.8,
                "balanced_accuracy": 0.81,
                "brier_score": 0.12,
                "expected_calibration_error": 0.04,
                "log_loss": 0.3,
                "open_set_unknown_recall": 0.75,
                "accepted_coverage": 0.7,
                "accepted_accuracy": 0.9,
                "per_class_precision_recall": {"vegetable": {"precision": 0.8, "recall": 0.8}},
                "confusion_matrix": [[8, 2], [1, 9]],
                "confidence_coverage_curve": [{"threshold": 0.8, "coverage": 0.7}],
                "thresholds_passed": True,
                "probability_calibrated": True,
            }
        },
    }
    metadata["deployment_validation"] = release
    metadata["validation_report_hash"] = _release_validation_hash(release)
    classifier = _classifier(metadata)
    status = classifier._post_load_eligibility(
        actual_artifact_sha256=ARTIFACT_HASH
    )
    assert status
    assert status["production_eligible"] is True
    assert status["crop_model_receipt"]["artifact_sha256"] == ARTIFACT_HASH
    assert classifier.production_eligible is True


def test_missing_open_set_metric_blocks_release_even_with_other_metrics() -> None:
    metadata = _base_metadata()
    release = {
        "contract_version": PRODUCTION_VALIDATION_CONTRACT_VERSION,
        "release_gate_passed": True,
        "split_contract": {
            "farm_disjoint": True,
            "season_disjoint": True,
            "region_transfer_evaluated": True,
            "observation_leakage_checked": True,
        },
        "metrics_by_level": {
            "L2": {
                "macro_f1": 0.8,
                "balanced_accuracy": 0.8,
                "brier_score": 0.1,
                "expected_calibration_error": 0.03,
                "log_loss": 0.2,
                "accepted_coverage": 0.7,
                "accepted_accuracy": 0.9,
                "per_class_precision_recall": {"crop": {"precision": 0.8, "recall": 0.8}},
                "confusion_matrix": [[10]],
                "confidence_coverage_curve": [{"threshold": 0.8, "coverage": 0.7}],
                "thresholds_passed": True,
                "probability_calibrated": True,
            }
        },
    }
    metadata["deployment_validation"] = release
    metadata["validation_report_hash"] = _release_validation_hash(release)
    status = _classifier(metadata)._post_load_eligibility(
        actual_artifact_sha256=ARTIFACT_HASH
    )
    assert not status
    assert "L2:open_set_unknown_recall_missing" in status["missing_or_invalid"]


def test_artifact_bytes_must_match_the_release_receipt() -> None:
    metadata = _base_metadata()
    release = {
        "contract_version": PRODUCTION_VALIDATION_CONTRACT_VERSION,
        "release_gate_passed": True,
        "split_contract": {
            "farm_disjoint": True,
            "year_disjoint": True,
            "region_transfer_evaluated": True,
            "observation_leakage_checked": True,
        },
        "metrics_by_level": {
            "L2": {
                "macro_f1": 0.8,
                "balanced_accuracy": 0.81,
                "brier_score": 0.12,
                "expected_calibration_error": 0.04,
                "log_loss": 0.3,
                "open_set_unknown_recall": 0.75,
                "accepted_coverage": 0.7,
                "accepted_accuracy": 0.9,
                "per_class_precision_recall": {"crop": {"precision": 0.8, "recall": 0.8}},
                "confusion_matrix": [[10]],
                "confidence_coverage_curve": [{"threshold": 0.8, "coverage": 0.7}],
                "thresholds_passed": True,
                "probability_calibrated": True,
            }
        },
    }
    metadata["deployment_validation"] = release
    metadata["validation_report_hash"] = _release_validation_hash(release)
    status = _classifier(metadata)._post_load_eligibility(
        actual_artifact_sha256="f" * 64
    )
    assert not status
    assert "artifact_sha256_mismatch" in status["missing_or_invalid"]


def test_validation_report_hash_is_recomputed_not_trusted() -> None:
    metadata = _base_metadata()
    metadata["deployment_validation"] = {
        "contract_version": PRODUCTION_VALIDATION_CONTRACT_VERSION,
        "release_gate_passed": True,
        "split_contract": {
            "farm_disjoint": True,
            "season_disjoint": True,
            "region_transfer_evaluated": True,
            "observation_leakage_checked": True,
        },
        "metrics_by_level": {},
    }
    metadata["validation_report_hash"] = "d" * 64
    status = _classifier(metadata)._post_load_eligibility(
        actual_artifact_sha256=ARTIFACT_HASH
    )
    assert not status
    assert "validation_report_hash_mismatch" in status["missing_or_invalid"]


def test_exact_saved_artifact_bytes_are_verified_on_every_load(tmp_path: Path) -> None:
    metadata = _base_metadata()
    release = {
        "contract_version": PRODUCTION_VALIDATION_CONTRACT_VERSION,
        "release_gate_passed": True,
        "split_contract": {
            "farm_disjoint": True,
            "year_disjoint": True,
            "region_transfer_evaluated": True,
            "observation_leakage_checked": True,
        },
        "metrics_by_level": {
            "L2": {
                "macro_f1": 0.8,
                "balanced_accuracy": 0.8,
                "brier_score": 0.1,
                "expected_calibration_error": 0.04,
                "log_loss": 0.3,
                "open_set_unknown_recall": 0.8,
                "accepted_coverage": 0.7,
                "accepted_accuracy": 0.9,
                "per_class_precision_recall": {"crop": {"precision": 0.8, "recall": 0.8}},
                "confusion_matrix": [[10]],
                "confidence_coverage_curve": [{"threshold": 0.8, "coverage": 0.7}],
                "thresholds_passed": True,
                "probability_calibrated": True,
            }
        },
    }
    metadata["deployment_validation"] = release
    metadata["validation_report_hash"] = _release_validation_hash(release)

    classifier = HierarchicalCropClassifier(str(tmp_path))
    classifier.models = {"L2": TrivialClassifier("crop")}
    classifier.feature_names = ["feature_a", "feature_b"]
    classifier.imputer = SimpleImputer(strategy="median").fit(
        np.asarray([[1.0, 2.0], [2.0, 3.0]])
    )
    classifier.metadata = metadata
    classifier.save()

    loaded = HierarchicalCropClassifier(str(tmp_path)).load()
    assert loaded
    assert loaded["production_eligible"] is True
    assert loaded["crop_model_receipt"]["artifact_sha256"] == (
        classifier.metadata["artifact_sha256"]
    )

    manifest_path = tmp_path / "model_manifest.json"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    tampered = HierarchicalCropClassifier(str(tmp_path)).load()
    assert not tampered
    assert "artifact_sha256_mismatch" in tampered["missing_or_invalid"]
