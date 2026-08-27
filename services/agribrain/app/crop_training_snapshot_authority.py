"""Fail-closed authority checks for crop-training feature snapshots.

Training and inference must use the same admitted physical observations and
the same feature tensor. A generic PlotObservation/Layer-1 snapshot is not a
training input, even when paired with a trusted crop label.
"""

from __future__ import annotations

import math
import re
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

CROP_MODEL_INPUT_RECEIPT_VERSION = "crop-model-input-receipt-v1"
_LEDGER_HASH = re.compile(r"^CROPLEDGERV2-[0-9a-f]{64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _canonical(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite crop training receipt value")
        return 0.0 if value == 0.0 else value
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    raise ValueError(f"unsupported crop training receipt type: {type(value).__name__}")


def _sha256(value: Any) -> str:
    encoded = json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CropTrainingSnapshotAssessment:
    eligible: bool
    reasons: tuple[str, ...]
    crop_model_input_receipt_hash: Optional[str]
    crop_evidence_ledger_hash: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "crop_model_input_receipt_hash": self.crop_model_input_receipt_hash,
            "crop_evidence_ledger_hash": self.crop_evidence_ledger_hash,
        }


def _flat_features(snapshot: Any) -> Optional[Mapping[str, Any]]:
    if not isinstance(snapshot, Mapping):
        return None
    candidate = snapshot.get("flat_features", snapshot)
    return candidate if isinstance(candidate, Mapping) else None


def _same_numeric(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    try:
        left_value = float(left)
        right_value = float(right)
    except (TypeError, ValueError):
        return False
    return (
        math.isfinite(left_value)
        and math.isfinite(right_value)
        and left_value == right_value
    )


def _rebuild_receipt_contract(receipt: Mapping[str, Any]) -> Any:
    """Reconstruct the canonical contract instead of trusting a shape/hash.

    A self-consistent JSON hash alone does not prove that a document was ever
    a ``CropModelInputReceiptV1``. Rebuilding the typed contract re-derives
    observation identities, family partitions, temporal coordinates, tensor
    hashes, and the final receipt hash from the immutable tokens.
    """

    from services.agribrain.common.plot_namespace import PlotNamespace
    from services.agribrain.scientific_contracts.crop_model_input import (
        CropModelInputReceiptV1,
        CropModelObservationTokenV1,
    )

    namespace = receipt.get("plot_namespace")
    if not isinstance(namespace, Mapping):
        raise ValueError("plot_namespace is required")
    raw_tokens = receipt.get("observation_tokens")
    if not isinstance(raw_tokens, Sequence) or isinstance(
        raw_tokens, (str, bytes)
    ):
        raise ValueError("observation_tokens must be a sequence")
    tokens = []
    for raw in raw_tokens:
        if not isinstance(raw, Mapping):
            raise ValueError("observation token must be an object")
        feature_values = raw.get("feature_values")
        if not isinstance(feature_values, Sequence) or isinstance(
            feature_values, (str, bytes)
        ):
            raise ValueError("observation feature_values must be a sequence")
        feature_rows = []
        for feature in feature_values:
            if not isinstance(feature, Mapping):
                raise ValueError("observation feature value must be an object")
            feature_rows.append((
                str(feature.get("name") or ""),
                str(feature.get("statistic") or ""),
                float(feature.get("value")),
            ))
        gdd = raw.get("gdd_coordinates") or {}
        if not isinstance(gdd, Mapping):
            raise ValueError("gdd_coordinates must be an object")
        s1 = raw.get("s1_geometry") or {}
        if not isinstance(s1, Mapping):
            raise ValueError("s1_geometry must be an object")
        tokens.append(CropModelObservationTokenV1(
            observation_id=str(raw.get("observation_id") or ""),
            observation_hash=str(raw.get("observation_hash") or ""),
            physical_acquisition_key=str(
                raw.get("physical_acquisition_key") or ""
            ),
            source_family=str(raw.get("source_family") or ""),
            sensing_time=str(raw.get("sensing_time") or ""),
            feature_values=tuple(feature_rows),
            quality_admitted=raw.get("quality_admitted") is True,
            quality_class=str(raw.get("quality_class") or ""),
            support_hash=str(raw.get("support_hash") or ""),
            day_of_year=(
                float(raw["day_of_year"])
                if raw.get("day_of_year") is not None
                else None
            ),
            gdd_coordinates=tuple(
                (str(key), float(value)) for key, value in gdd.items()
            ),
            primary_gdd_basis=(
                str(raw["primary_gdd_basis"])
                if raw.get("primary_gdd_basis") is not None
                else None
            ),
            orbit_direction=(
                str(s1["orbit_direction"])
                if s1.get("orbit_direction") is not None
                else None
            ),
            relative_orbit=(
                str(s1["relative_orbit"])
                if s1.get("relative_orbit") is not None
                else None
            ),
            incidence_angle=(
                float(s1["incidence_angle"])
                if s1.get("incidence_angle") is not None
                else None
            ),
            polarizations=tuple(s1.get("polarizations") or ()),
        ))
    sensor_mask = receipt.get("sensor_availability_mask")
    if not isinstance(sensor_mask, Mapping):
        raise ValueError("sensor_availability_mask must be an object")
    return CropModelInputReceiptV1(
        plot_namespace=PlotNamespace(
            tenant_id=str(namespace.get("tenant_id") or ""),
            farm_id=str(namespace.get("farm_id") or ""),
            plot_id=str(namespace.get("plot_id") or ""),
        ),
        crop_cycle_hypothesis_id=str(
            receipt.get("crop_cycle_hypothesis_id") or ""
        ),
        crop_evidence_ledger_hash=str(
            receipt.get("crop_evidence_ledger_hash") or ""
        ),
        observation_tokens=tuple(tokens),
        feature_schema_hash=str(receipt.get("feature_schema_hash") or ""),
        feature_transform_hash=str(
            receipt.get("feature_transform_hash") or ""
        ),
        normalization_artifact_hash=str(
            receipt.get("normalization_artifact_hash") or ""
        ),
        feature_order=tuple(receipt.get("feature_order") or ()),
        input_values=tuple(receipt.get("input_values") or ()),
        missingness_mask=tuple(receipt.get("missingness_mask") or ()),
        sensor_availability_mask=tuple(sensor_mask.items()),
        quality_mask=tuple(receipt.get("quality_mask") or ()),
        feature_completeness=float(receipt.get("feature_completeness")),
        physical_evidence_sufficiency=str(
            receipt.get("physical_evidence_sufficiency") or ""
        ),
        phase_coverage=tuple(receipt.get("phase_coverage") or ()),
        domain_compatibility=str(
            receipt.get("domain_compatibility") or ""
        ),
        calibration_validity=str(
            receipt.get("calibration_validity") or ""
        ),
        model_execution_eligible=(
            receipt.get("model_execution_eligible") is True
        ),
        publication_eligible=receipt.get("publication_eligible") is True,
        publication_blockers=tuple(
            receipt.get("publication_blockers") or ()
        ),
        input_tensor_hash=str(receipt.get("input_tensor_hash") or ""),
        content_hash=str(receipt.get("content_hash") or ""),
    )


def assess_crop_training_snapshot(
    *,
    feature_vector_snapshot: Any,
    crop_model_input_receipt: Any,
    tenant_id: Optional[str],
    farm_id: Optional[str],
    plot_id: str,
    crop_cycle_id: Optional[str] = None,
    expected_receipt_hash: Optional[str] = None,
) -> CropTrainingSnapshotAssessment:
    """Verify exact tensor, ledger and authenticated namespace binding."""

    reasons: list[str] = []
    features = _flat_features(feature_vector_snapshot)
    if features is None:
        reasons.append("missing_feature_vector")
    if not isinstance(crop_model_input_receipt, Mapping):
        reasons.append("missing_crop_model_input_receipt")
        return CropTrainingSnapshotAssessment(False, tuple(reasons), None, None)

    receipt = dict(crop_model_input_receipt)
    receipt_hash = str(receipt.get("content_hash") or "").strip()
    ledger_hash = str(receipt.get("crop_evidence_ledger_hash") or "").strip()
    if receipt.get("contract_version") != CROP_MODEL_INPUT_RECEIPT_VERSION:
        reasons.append("unsupported_crop_model_input_receipt_version")
    try:
        _rebuild_receipt_contract(receipt)
    except (TypeError, ValueError):
        reasons.append("invalid_crop_model_input_receipt_contract")
    if not _SHA256.fullmatch(receipt_hash):
        reasons.append("invalid_crop_model_input_receipt_hash")
    else:
        payload = {
            key: value for key, value in receipt.items()
            if key not in {"receipt_id", "content_hash"}
        }
        try:
            if _sha256(payload) != receipt_hash:
                reasons.append("crop_model_input_receipt_hash_mismatch")
        except (TypeError, ValueError):
            reasons.append("crop_model_input_receipt_not_canonical")
    stored_receipt_hash = str(expected_receipt_hash or "").strip()
    if not stored_receipt_hash:
        reasons.append("missing_stored_crop_model_input_receipt_hash")
    elif not _SHA256.fullmatch(stored_receipt_hash):
        reasons.append("invalid_stored_crop_model_input_receipt_hash")
    elif stored_receipt_hash != receipt_hash:
        reasons.append("stored_crop_model_input_receipt_hash_mismatch")
    if not _LEDGER_HASH.fullmatch(ledger_hash):
        reasons.append("invalid_crop_evidence_ledger_hash")
    for field_name in (
        "feature_schema_hash",
        "feature_transform_hash",
        "normalization_artifact_hash",
    ):
        if not _SHA256.fullmatch(str(receipt.get(field_name) or "")):
            reasons.append(f"invalid_{field_name}")
    receipt_id = str(receipt.get("receipt_id") or "")
    if receipt_hash and receipt_id != "CROP-MODEL-INPUT-" + receipt_hash[:24]:
        reasons.append("crop_model_input_receipt_id_mismatch")

    namespace = receipt.get("plot_namespace")
    expected_namespace = {
        "tenant_id": str(tenant_id or "").strip(),
        "farm_id": str(farm_id or "").strip(),
        "plot_id": str(plot_id or "").strip(),
    }
    if any(not value for value in expected_namespace.values()):
        reasons.append("missing_training_plot_namespace")
    if not isinstance(namespace, Mapping) or any(
        str(namespace.get(key) or "").strip() != value
        for key, value in expected_namespace.items()
    ):
        reasons.append("crop_model_input_namespace_mismatch")

    expected_cycle = str(crop_cycle_id or "").strip()
    receipt_cycle = str(
        receipt.get("crop_cycle_hypothesis_id") or ""
    ).strip()
    if not expected_cycle:
        reasons.append("missing_training_crop_cycle_identity")
    elif not (
        receipt_cycle == expected_cycle
        or receipt_cycle.startswith(expected_cycle + ":")
    ):
        reasons.append("crop_model_input_cycle_mismatch")

    feature_order = receipt.get("feature_order")
    values = receipt.get("input_values")
    missing = receipt.get("missingness_mask")
    if not all(isinstance(item, Sequence) and not isinstance(item, (str, bytes)) for item in (
        feature_order, values, missing,
    )) or not (
        len(feature_order) == len(values) == len(missing) and len(feature_order) > 0
    ):
        reasons.append("crop_model_input_tensor_misaligned")
    else:
        tensor_payload = {
            "feature_order": list(feature_order),
            "input_values": list(values),
            "missingness_mask": list(missing),
        }
        if _sha256(tensor_payload) != receipt.get("input_tensor_hash"):
            reasons.append("crop_model_input_tensor_hash_mismatch")
        if features is not None:
            if set(map(str, features.keys())) != set(map(str, feature_order)):
                reasons.append("feature_snapshot_schema_mismatch")
            for name, value, is_missing in zip(feature_order, values, missing):
                if bool(is_missing) != (value is None):
                    reasons.append("crop_model_input_missingness_mismatch")
                    break
                if name not in features or not _same_numeric(features.get(name), value):
                    reasons.append("feature_snapshot_tensor_mismatch")
                    break

    observation_ids = receipt.get("observation_ids")
    physical_keys = receipt.get("physical_acquisition_keys")
    observation_tokens = receipt.get("observation_tokens")
    quality_mask = receipt.get("quality_mask")
    if not isinstance(observation_ids, Sequence) or isinstance(
        observation_ids, (str, bytes)
    ) or not observation_ids:
        reasons.append("crop_model_input_has_no_physical_observations")
    if not isinstance(quality_mask, Sequence) or isinstance(
        quality_mask, (str, bytes)
    ) or not quality_mask or not all(value is True for value in quality_mask):
        reasons.append("crop_model_input_contains_unadmitted_observations")
    elif (
        isinstance(observation_ids, Sequence)
        and not isinstance(observation_ids, (str, bytes))
        and len(quality_mask) != len(observation_ids)
    ):
        reasons.append("crop_model_input_quality_mask_misaligned")
    if (
        isinstance(observation_ids, Sequence)
        and not isinstance(observation_ids, (str, bytes))
        and (
            not isinstance(physical_keys, Sequence)
            or isinstance(physical_keys, (str, bytes))
            or len(physical_keys) != len(observation_ids)
            or any(not str(value or "").strip() for value in physical_keys)
        )
    ):
        reasons.append("physical_acquisition_identity_misaligned")
    if (
        isinstance(observation_ids, Sequence)
        and not isinstance(observation_ids, (str, bytes))
        and (
            not isinstance(observation_tokens, Sequence)
            or isinstance(observation_tokens, (str, bytes))
            or [
                str(item.get("observation_id") or "")
                for item in observation_tokens
                if isinstance(item, Mapping)
            ] != list(observation_ids)
        )
    ):
        reasons.append("observation_token_identity_mismatch")
    if receipt.get("model_execution_eligible") is not True:
        reasons.append("crop_model_input_not_execution_eligible")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return CropTrainingSnapshotAssessment(
        eligible=not unique_reasons,
        reasons=unique_reasons,
        crop_model_input_receipt_hash=receipt_hash or None,
        crop_evidence_ledger_hash=ledger_hash or None,
    )


__all__ = [
    "CropTrainingSnapshotAssessment",
    "assess_crop_training_snapshot",
]
