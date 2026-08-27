"""Governance and feedback-lineage contracts for crop inference.

These contracts deliberately do not make a model scientific by themselves.
They make the absence of a released artifact explicit and prevent ASMAE output
derived from the same EO acquisitions from being counted as new evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from services.agribrain.common.plot_namespace import PlotNamespace, namespace_payload


CROP_MODEL_RECEIPT_CONTRACT_VERSION = "crop-model-receipt-v1"
CROP_INFLUENCE_MANIFEST_CONTRACT_VERSION = "crop-influence-manifest-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _namespace(value: Any) -> PlotNamespace:
    if isinstance(value, PlotNamespace):
        result = value
    elif isinstance(value, Mapping):
        result = PlotNamespace(
            tenant_id=str(value.get("tenant_id") or "").strip(),
            farm_id=str(value.get("farm_id") or "").strip(),
            plot_id=str(value.get("plot_id") or "").strip(),
        )
    else:
        result = PlotNamespace(
            tenant_id=str(getattr(value, "tenant_id", "") or "").strip(),
            farm_id=str(getattr(value, "farm_id", "") or "").strip(),
            plot_id=str(getattr(value, "plot_id", "") or "").strip(),
        )
    if not result.is_valid():
        raise ValueError("A complete PlotNamespace is required")
    return result


def _sorted_unique(values: Iterable[Any]) -> Tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _compatibility_rows(value: Any) -> Tuple[Tuple[str, str], ...]:
    if isinstance(value, Mapping):
        rows = ((str(key).strip(), str(item).strip()) for key, item in value.items())
    else:
        rows = (
            (str(row[0]).strip(), str(row[1]).strip())
            for row in (value or ())
            if isinstance(row, (tuple, list)) and len(row) == 2
        )
    normalized = tuple(sorted({row for row in rows if row[0] and row[1]}))
    return normalized


def _validate_optional_sha256(name: str, value: str) -> None:
    if value and not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class CropModelReceiptV1:
    """Immutable receipt binding inference to a governed model release."""

    model_family: str
    semantic_version: str
    artifact_sha256: str
    feature_schema_version: str
    feature_schema_hash: str
    class_hierarchy_version: str
    training_dataset_manifest_hash: str
    calibration_artifact_hash: str
    validation_report_hash: str
    region_domain_compatibility: Tuple[Tuple[str, str], ...]
    production_eligible: bool
    inference_device: str
    runtime_version: str
    deterministic_preprocessing_version: str
    eligibility_reasons: Tuple[str, ...] = field(default_factory=tuple)
    contract_version: str = CROP_MODEL_RECEIPT_CONTRACT_VERSION
    content_hash: str = ""

    def __post_init__(self) -> None:
        for name in (
            "model_family",
            "semantic_version",
            "feature_schema_version",
            "class_hierarchy_version",
            "inference_device",
            "runtime_version",
            "deterministic_preprocessing_version",
        ):
            value = str(getattr(self, name) or "").strip()
            if not value:
                raise ValueError(f"{name} is required")
            object.__setattr__(self, name, value)

        digest_names = (
            "artifact_sha256",
            "feature_schema_hash",
            "training_dataset_manifest_hash",
            "calibration_artifact_hash",
            "validation_report_hash",
        )
        for name in digest_names:
            value = str(getattr(self, name) or "").strip().lower()
            _validate_optional_sha256(name, value)
            object.__setattr__(self, name, value)

        compatibility = _compatibility_rows(self.region_domain_compatibility)
        object.__setattr__(self, "region_domain_compatibility", compatibility)
        reasons = _sorted_unique(self.eligibility_reasons)
        object.__setattr__(self, "eligibility_reasons", reasons)

        if self.production_eligible:
            missing = [name for name in digest_names if not getattr(self, name)]
            if missing:
                raise ValueError(
                    "Production crop model receipt is missing: " + ", ".join(missing)
                )
            if not compatibility:
                raise ValueError(
                    "Production crop model receipt requires explicit domain compatibility"
                )
            if reasons:
                raise ValueError(
                    "Production crop model receipt cannot carry eligibility failures"
                )
        elif not reasons:
            object.__setattr__(
                self,
                "eligibility_reasons",
                ("production_release_not_validated",),
            )

        expected = _canonical_hash(self._payload_without_hash())
        if self.content_hash and str(self.content_hash).lower() != expected:
            raise ValueError("Crop model receipt content_hash mismatch")
        object.__setattr__(self, "content_hash", expected)

    @property
    def receipt_id(self) -> str:
        return "CROP-MODEL-" + self.content_hash[:24]

    def _payload_without_hash(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "model_family": self.model_family,
            "semantic_version": self.semantic_version,
            "artifact_sha256": self.artifact_sha256,
            "feature_schema_version": self.feature_schema_version,
            "feature_schema_hash": self.feature_schema_hash,
            "class_hierarchy_version": self.class_hierarchy_version,
            "training_dataset_manifest_hash": self.training_dataset_manifest_hash,
            "calibration_artifact_hash": self.calibration_artifact_hash,
            "validation_report_hash": self.validation_report_hash,
            "region_domain_compatibility": {
                key: value for key, value in self.region_domain_compatibility
            },
            "production_eligible": bool(self.production_eligible),
            "inference_device": self.inference_device,
            "runtime_version": self.runtime_version,
            "deterministic_preprocessing_version": (
                self.deterministic_preprocessing_version
            ),
            "eligibility_reasons": list(self.eligibility_reasons),
        }

    def to_dict(self) -> Dict[str, Any]:
        result = self._payload_without_hash()
        result.update({"receipt_id": self.receipt_id, "content_hash": self.content_hash})
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CropModelReceiptV1":
        if not isinstance(value, Mapping):
            raise ValueError("Crop model receipt must be an object")
        receipt = cls(
            model_family=str(value.get("model_family") or ""),
            semantic_version=str(value.get("semantic_version") or ""),
            artifact_sha256=str(value.get("artifact_sha256") or ""),
            feature_schema_version=str(value.get("feature_schema_version") or ""),
            feature_schema_hash=str(value.get("feature_schema_hash") or ""),
            class_hierarchy_version=str(value.get("class_hierarchy_version") or ""),
            training_dataset_manifest_hash=str(
                value.get("training_dataset_manifest_hash") or ""
            ),
            calibration_artifact_hash=str(
                value.get("calibration_artifact_hash") or ""
            ),
            validation_report_hash=str(value.get("validation_report_hash") or ""),
            region_domain_compatibility=_compatibility_rows(
                value.get("region_domain_compatibility") or {}
            ),
            production_eligible=value.get("production_eligible") is True,
            inference_device=str(value.get("inference_device") or ""),
            runtime_version=str(value.get("runtime_version") or ""),
            deterministic_preprocessing_version=str(
                value.get("deterministic_preprocessing_version") or ""
            ),
            eligibility_reasons=tuple(value.get("eligibility_reasons") or ()),
            contract_version=str(
                value.get("contract_version") or CROP_MODEL_RECEIPT_CONTRACT_VERSION
            ),
            content_hash=str(value.get("content_hash") or ""),
        )
        supplied_id = str(value.get("receipt_id") or "")
        if supplied_id and supplied_id != receipt.receipt_id:
            raise ValueError("Crop model receipt_id mismatch")
        return receipt


@dataclass(frozen=True)
class CropInfluenceManifestV1:
    """Bound and audit one crop -> ASMAE -> crop refinement cycle."""

    namespace: PlotNamespace
    independent_evidence_ids: Tuple[str, ...]
    asmae_source_observation_ids: Tuple[str, ...]
    dependent_refinement_features: Tuple[str, ...]
    maximum_allowed_posterior_influence: float
    actual_posterior_change: float
    lineage_parent_id: str
    lineage_child_id: Optional[str]
    child_asmae_run_scheduled: bool
    crop_posterior_parent_hash: str = ""
    crop_posterior_child_hash: str = ""
    crop_cycle_id: Optional[str] = None
    asmae_run_id: Optional[str] = None
    refinement_iteration: int = 0
    overlap_set: Tuple[str, ...] = field(default_factory=tuple)
    contract_version: str = CROP_INFLUENCE_MANIFEST_CONTRACT_VERSION
    content_hash: str = ""

    def __post_init__(self) -> None:
        namespace = _namespace(self.namespace)
        object.__setattr__(self, "namespace", namespace)
        independent = _sorted_unique(self.independent_evidence_ids)
        sources = _sorted_unique(self.asmae_source_observation_ids)
        dependent = _sorted_unique(self.dependent_refinement_features)
        overlap = tuple(sorted(set(independent).intersection(sources)))
        supplied_overlap = _sorted_unique(self.overlap_set)
        if supplied_overlap and supplied_overlap != overlap:
            raise ValueError("Crop influence overlap_set is not the exact intersection")
        object.__setattr__(self, "independent_evidence_ids", independent)
        object.__setattr__(self, "asmae_source_observation_ids", sources)
        object.__setattr__(self, "dependent_refinement_features", dependent)
        object.__setattr__(self, "overlap_set", overlap)

        maximum = float(self.maximum_allowed_posterior_influence)
        actual = float(self.actual_posterior_change)
        if not math.isfinite(maximum) or not 0.0 <= maximum <= 1.0:
            raise ValueError("maximum_allowed_posterior_influence must be in [0, 1]")
        if not math.isfinite(actual) or not 0.0 <= actual <= 1.0:
            raise ValueError("actual_posterior_change must be in [0, 1]")
        if actual > maximum + 1e-12:
            raise ValueError("Crop refinement exceeded its declared influence cap")
        object.__setattr__(self, "maximum_allowed_posterior_influence", maximum)
        object.__setattr__(self, "actual_posterior_change", actual)

        parent_id = str(self.lineage_parent_id or "").strip()
        child_id = str(self.lineage_child_id or "").strip() or None
        if not parent_id:
            raise ValueError("lineage_parent_id is required")
        if child_id == parent_id:
            raise ValueError("Crop lineage child cannot equal its parent")
        if self.child_asmae_run_scheduled and not child_id:
            raise ValueError("A scheduled ASMAE child requires lineage_child_id")
        if self.refinement_iteration not in {0, 1}:
            raise ValueError("At most one crop-refinement ASMAE child is allowed")
        if self.child_asmae_run_scheduled and self.refinement_iteration != 1:
            raise ValueError("Scheduled ASMAE child must be refinement_iteration=1")
        object.__setattr__(self, "lineage_parent_id", parent_id)
        object.__setattr__(self, "lineage_child_id", child_id)

        for name in ("crop_posterior_parent_hash", "crop_posterior_child_hash"):
            value = str(getattr(self, name) or "").strip().lower()
            _validate_optional_sha256(name, value)
            object.__setattr__(self, name, value)

        expected = _canonical_hash(self._payload_without_hash())
        if self.content_hash and str(self.content_hash).lower() != expected:
            raise ValueError("Crop influence manifest content_hash mismatch")
        object.__setattr__(self, "content_hash", expected)

    @property
    def manifest_id(self) -> str:
        return "CROP-INFLUENCE-" + self.content_hash[:24]

    def _payload_without_hash(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "namespace": namespace_payload(self.namespace),
            "crop_cycle_id": self.crop_cycle_id,
            "independent_evidence_ids": list(self.independent_evidence_ids),
            "asmae_source_observation_ids": list(self.asmae_source_observation_ids),
            "overlap_set": list(self.overlap_set),
            "dependent_refinement_features": list(self.dependent_refinement_features),
            "maximum_allowed_posterior_influence": (
                self.maximum_allowed_posterior_influence
            ),
            "actual_posterior_change": self.actual_posterior_change,
            "lineage_parent_id": self.lineage_parent_id,
            "lineage_child_id": self.lineage_child_id,
            "crop_posterior_parent_hash": self.crop_posterior_parent_hash,
            "crop_posterior_child_hash": self.crop_posterior_child_hash,
            "asmae_run_id": self.asmae_run_id,
            "child_asmae_run_scheduled": bool(self.child_asmae_run_scheduled),
            "refinement_iteration": self.refinement_iteration,
            "double_count_policy": "overlap_is_dependent_not_new_evidence",
        }

    def to_dict(self) -> Dict[str, Any]:
        result = self._payload_without_hash()
        result.update({"manifest_id": self.manifest_id, "content_hash": self.content_hash})
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CropInfluenceManifestV1":
        if not isinstance(value, Mapping):
            raise ValueError("Crop influence manifest must be an object")
        manifest = cls(
            namespace=_namespace(value.get("namespace") or {}),
            crop_cycle_id=value.get("crop_cycle_id"),
            independent_evidence_ids=tuple(value.get("independent_evidence_ids") or ()),
            asmae_source_observation_ids=tuple(
                value.get("asmae_source_observation_ids") or ()
            ),
            overlap_set=tuple(value.get("overlap_set") or ()),
            dependent_refinement_features=tuple(
                value.get("dependent_refinement_features") or ()
            ),
            maximum_allowed_posterior_influence=float(
                value.get("maximum_allowed_posterior_influence") or 0.0
            ),
            actual_posterior_change=float(value.get("actual_posterior_change") or 0.0),
            lineage_parent_id=str(value.get("lineage_parent_id") or ""),
            lineage_child_id=value.get("lineage_child_id"),
            crop_posterior_parent_hash=str(
                value.get("crop_posterior_parent_hash") or ""
            ),
            crop_posterior_child_hash=str(
                value.get("crop_posterior_child_hash") or ""
            ),
            asmae_run_id=value.get("asmae_run_id"),
            child_asmae_run_scheduled=(
                value.get("child_asmae_run_scheduled") is True
            ),
            refinement_iteration=int(value.get("refinement_iteration") or 0),
            contract_version=str(
                value.get("contract_version")
                or CROP_INFLUENCE_MANIFEST_CONTRACT_VERSION
            ),
            content_hash=str(value.get("content_hash") or ""),
        )
        supplied_id = str(value.get("manifest_id") or "")
        if supplied_id and supplied_id != manifest.manifest_id:
            raise ValueError("Crop influence manifest_id mismatch")
        return manifest


__all__ = [
    "CROP_MODEL_RECEIPT_CONTRACT_VERSION",
    "CROP_INFLUENCE_MANIFEST_CONTRACT_VERSION",
    "CropModelReceiptV1",
    "CropInfluenceManifestV1",
]
