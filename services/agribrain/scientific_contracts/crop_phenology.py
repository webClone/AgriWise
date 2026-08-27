"""Canonical Layer-2 phenology publication contract.

The contract is deliberately separate from administrative crop-cycle status
and from downstream visualization.  Layer 2 is the only component allowed to
construct it; later layers may consume or demote it but may not infer a
replacement stage.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

from services.agribrain.common.plot_namespace import PlotNamespace, namespace_payload


PHENOLOGY_POSTERIOR_CONTRACT_VERSION = "canonical-phenology-posterior-v2"
PHENOLOGY_STAGES = frozenset({
    "BARE_SOIL",
    "EMERGENCE",
    "VEGETATIVE",
    "REPRODUCTIVE",
    "SENESCENCE",
    "HARVESTED",
    "DORMANCY",
    "UNKNOWN",
})
PLANT_DATE_STATUSES = frozenset({"confirmed", "estimated", "interval", "unknown"})
PHENOLOGY_AUTHORITIES = frozenset({"unavailable", "diagnostic", "calibrated"})
PUBLISHED_PHENOLOGY_AUTHORITIES = frozenset({"diagnostic", "calibrated"})
CANONICAL_PHENOLOGY_SOURCE = "layer2_canonical_phenology"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CROP_EVIDENCE_LEDGER_PATTERN = re.compile(r"^CROPLEDGERV2-[0-9a-f]{64}$")


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({
            str(key): _freeze(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        })
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


def _sorted_unique(values: Any) -> Tuple[str, ...]:
    return tuple(sorted({
        str(value).strip() for value in (values or ()) if str(value).strip()
    }))


@dataclass(frozen=True)
class CanonicalPhenologyPosteriorV2:
    namespace: PlotNamespace
    effective_at: str
    current_stage: str
    stage_posterior: Tuple[Tuple[str, float], ...]
    authority: str
    calibration_status: str
    season_anchor_status: str
    stage_confidence: float = 0.0
    stage_authority: str = ""
    planting_date_posterior: Mapping[str, Any] = field(default_factory=dict)
    biological_age_gdd: Mapping[str, Any] = field(default_factory=dict)
    season_progress: Mapping[str, Any] = field(default_factory=dict)
    transition_date_posteriors: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    stage_duration_consistency: float = 0.0
    crop_identity_posterior_hash: str = ""
    evidence_ledger_hash: str = ""
    weather_forcing_hash: str = ""
    previous_phenology_event_id: Optional[str] = None
    model_receipt_id: str = "phenology-hmm-v3.2-diagnostic"
    plant_date_status: str = "unknown"
    crop_cycle_id: Optional[str] = None
    plant_date_min: Optional[str] = None
    plant_date_max: Optional[str] = None
    candidate_stage: Optional[str] = None
    independent_evidence_count: int = 0
    evidence_observation_ids: Tuple[str, ...] = field(default_factory=tuple)
    degradation_reasons: Tuple[str, ...] = field(default_factory=tuple)
    contract_version: str = PHENOLOGY_POSTERIOR_CONTRACT_VERSION
    content_hash: str = ""

    def __post_init__(self) -> None:
        if self.contract_version != PHENOLOGY_POSTERIOR_CONTRACT_VERSION:
            raise ValueError("Unsupported canonical phenology contract version")
        if not str(self.effective_at or "").strip():
            raise ValueError("Canonical phenology effective_at is required")
        namespace = self.namespace
        if not isinstance(namespace, PlotNamespace):
            if isinstance(namespace, Mapping):
                namespace = PlotNamespace(
                    tenant_id=str(namespace.get("tenant_id") or ""),
                    farm_id=str(namespace.get("farm_id") or ""),
                    plot_id=str(namespace.get("plot_id") or ""),
                )
            else:
                namespace = PlotNamespace(
                    tenant_id=str(getattr(namespace, "tenant_id", "") or ""),
                    farm_id=str(getattr(namespace, "farm_id", "") or ""),
                    plot_id=str(getattr(namespace, "plot_id", "") or ""),
                )
            object.__setattr__(self, "namespace", namespace)
        if not namespace.is_valid():
            raise ValueError("Canonical phenology requires a complete PlotNamespace")
        stage = str(self.current_stage or "").upper()
        if stage not in PHENOLOGY_STAGES:
            raise ValueError(f"Unsupported phenology stage: {stage}")
        object.__setattr__(self, "current_stage", stage)

        authority = str(self.authority or "").lower()
        if authority not in PHENOLOGY_AUTHORITIES:
            raise ValueError(f"Unsupported phenology authority: {authority}")
        object.__setattr__(self, "authority", authority)
        stage_authority = str(self.stage_authority or authority).lower()
        if stage_authority not in PHENOLOGY_AUTHORITIES:
            raise ValueError(f"Unsupported stage authority: {stage_authority}")
        object.__setattr__(self, "stage_authority", stage_authority)

        try:
            stage_confidence = float(self.stage_confidence)
        except (TypeError, ValueError) as exc:
            raise ValueError("stage_confidence must be numeric") from exc
        if not math.isfinite(stage_confidence) or not 0.0 <= stage_confidence <= 1.0:
            raise ValueError("stage_confidence must be in [0, 1]")
        object.__setattr__(self, "stage_confidence", stage_confidence)

        try:
            duration_consistency = float(self.stage_duration_consistency)
        except (TypeError, ValueError) as exc:
            raise ValueError("stage_duration_consistency must be numeric") from exc
        if not math.isfinite(duration_consistency) or not 0.0 <= duration_consistency <= 1.0:
            raise ValueError("stage_duration_consistency must be in [0, 1]")
        object.__setattr__(self, "stage_duration_consistency", duration_consistency)

        plant_status = str(self.plant_date_status or "unknown").lower()
        if plant_status not in PLANT_DATE_STATUSES:
            raise ValueError(f"Unsupported plant-date status: {plant_status}")
        object.__setattr__(self, "plant_date_status", plant_status)

        normalized = []
        for raw_name, raw_probability in self.stage_posterior:
            name = str(raw_name or "").upper()
            if name not in PHENOLOGY_STAGES:
                raise ValueError(f"Unsupported posterior stage: {name}")
            probability = float(raw_probability)
            if not math.isfinite(probability) or probability < 0.0 or probability > 1.0:
                raise ValueError(f"Invalid stage probability for {name}: {raw_probability}")
            normalized.append((name, probability))
        normalized.sort(key=lambda item: item[0])
        total = sum(item[1] for item in normalized)
        if not normalized or abs(total - 1.0) > 1e-6:
            raise ValueError(f"Stage posterior must sum to one, got {total}")
        object.__setattr__(self, "stage_posterior", tuple(normalized))
        maximum_probability = max(probability for _, probability in normalized)
        if not any(
            name == stage and abs(probability - maximum_probability) <= 1e-12
            for name, probability in normalized
        ):
            raise ValueError("current_stage must be a most-likely posterior stage")
        if stage == "UNKNOWN" and stage_authority != "unavailable":
            raise ValueError("UNKNOWN stage cannot carry published phenology authority")
        if stage != "UNKNOWN" and stage_authority not in PUBLISHED_PHENOLOGY_AUTHORITIES:
            raise ValueError("Known stage requires diagnostic or calibrated authority")
        if authority == "calibrated" and "uncalibrated" in str(
            self.calibration_status or ""
        ).lower():
            raise ValueError("Calibrated authority requires a calibration artifact")

        if self.candidate_stage is not None:
            candidate = str(self.candidate_stage).upper()
            if candidate not in PHENOLOGY_STAGES:
                raise ValueError(f"Unsupported candidate stage: {candidate}")
            object.__setattr__(self, "candidate_stage", candidate)

        if self.independent_evidence_count < 0:
            raise ValueError("independent_evidence_count cannot be negative")
        evidence_ids = _sorted_unique(self.evidence_observation_ids)
        if evidence_ids and len(evidence_ids) != self.independent_evidence_count:
            raise ValueError(
                "independent_evidence_count must match unique evidence observations"
            )
        object.__setattr__(self, "evidence_observation_ids", evidence_ids)
        object.__setattr__(
            self,
            "degradation_reasons",
            _sorted_unique(self.degradation_reasons),
        )

        for name in (
            "crop_identity_posterior_hash",
            "weather_forcing_hash",
        ):
            value = str(getattr(self, name) or "").strip().lower()
            if value and not _SHA256_PATTERN.fullmatch(value):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
            object.__setattr__(self, name, value)

        # CropEvidenceLedgerV2 publishes a typed, domain-separated identity
        # rather than a bare digest. Preserve that full identity so phenology
        # is cryptographically bound to the exact verified ledger contract.
        evidence_ledger_hash = str(self.evidence_ledger_hash or "").strip()
        if (
            evidence_ledger_hash
            and not _CROP_EVIDENCE_LEDGER_PATTERN.fullmatch(evidence_ledger_hash)
        ):
            raise ValueError(
                "evidence_ledger_hash must identify a verified CropEvidenceLedgerV2"
            )
        object.__setattr__(self, "evidence_ledger_hash", evidence_ledger_hash)

        object.__setattr__(self, "planting_date_posterior", _freeze(
            self.planting_date_posterior
        ))
        object.__setattr__(self, "biological_age_gdd", _freeze(
            self.biological_age_gdd
        ))
        object.__setattr__(self, "season_progress", _freeze(
            self.season_progress
        ))
        object.__setattr__(self, "transition_date_posteriors", _freeze(
            self.transition_date_posteriors
        ))

        expected_hash = _canonical_hash(self._payload_without_hash())
        if self.content_hash and self.content_hash != expected_hash:
            raise ValueError("Canonical phenology content_hash mismatch")
        object.__setattr__(self, "content_hash", expected_hash)

    def _payload_without_hash(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "namespace": namespace_payload(self.namespace),
            "crop_cycle_id": self.crop_cycle_id,
            "effective_at": self.effective_at,
            "valid_time": self.effective_at,
            "current_stage": self.current_stage,
            "most_likely_stage": self.current_stage,
            "candidate_stage": self.candidate_stage,
            "stage_posterior": {
                name: probability for name, probability in self.stage_posterior
            },
            "authority": self.authority,
            "stage_authority": self.stage_authority,
            "stage_confidence": self.stage_confidence,
            "calibration_status": self.calibration_status,
            "season_anchor_status": self.season_anchor_status,
            "planting_date_posterior": _thaw(self.planting_date_posterior),
            "biological_age_gdd": _thaw(self.biological_age_gdd),
            "season_progress": _thaw(self.season_progress),
            "transition_date_posteriors": _thaw(
                self.transition_date_posteriors
            ),
            "stage_duration_consistency": self.stage_duration_consistency,
            "crop_identity_posterior_hash": self.crop_identity_posterior_hash,
            "evidence_ledger_hash": self.evidence_ledger_hash,
            "weather_forcing_hash": self.weather_forcing_hash,
            "previous_phenology_event_id": self.previous_phenology_event_id,
            "model_receipt_id": self.model_receipt_id,
            "plant_date_status": self.plant_date_status,
            "plant_date_min": self.plant_date_min,
            "plant_date_max": self.plant_date_max,
            "independent_evidence_count": self.independent_evidence_count,
            "evidence_observation_ids": list(self.evidence_observation_ids),
            "degradation_reasons": list(self.degradation_reasons),
        }

    def to_dict(self) -> Dict[str, Any]:
        payload = self._payload_without_hash()
        payload["content_hash"] = self.content_hash
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CanonicalPhenologyPosteriorV2":
        namespace = value.get("namespace") or {}
        posterior = value.get("stage_posterior") or {}
        if not isinstance(posterior, Mapping):
            raise ValueError("stage_posterior must be an object")
        current_stage = str(value.get("current_stage") or "UNKNOWN").upper()
        most_likely_stage = str(
            value.get("most_likely_stage") or current_stage
        ).upper()
        if current_stage != most_likely_stage:
            raise ValueError("Phenology stage aliases disagree")
        effective_at = str(value.get("effective_at") or "")
        valid_time = str(value.get("valid_time") or effective_at)
        if effective_at != valid_time:
            raise ValueError("Phenology valid-time aliases disagree")
        return cls(
            namespace=PlotNamespace(
                tenant_id=str(namespace.get("tenant_id") or ""),
                farm_id=str(namespace.get("farm_id") or ""),
                plot_id=str(namespace.get("plot_id") or ""),
            ),
            crop_cycle_id=value.get("crop_cycle_id"),
            effective_at=effective_at,
            current_stage=current_stage,
            candidate_stage=value.get("candidate_stage"),
            stage_posterior=tuple((str(k), float(v)) for k, v in posterior.items()),
            authority=str(value.get("authority") or "unavailable"),
            stage_authority=str(
                value.get("stage_authority")
                or value.get("authority")
                or "unavailable"
            ),
            stage_confidence=float(value.get("stage_confidence") or 0.0),
            calibration_status=str(value.get("calibration_status") or "unavailable"),
            season_anchor_status=str(value.get("season_anchor_status") or "unknown"),
            planting_date_posterior=dict(value.get("planting_date_posterior") or {}),
            biological_age_gdd=dict(value.get("biological_age_gdd") or {}),
            season_progress=dict(value.get("season_progress") or {}),
            transition_date_posteriors=dict(
                value.get("transition_date_posteriors") or {}
            ),
            stage_duration_consistency=float(
                value.get("stage_duration_consistency") or 0.0
            ),
            crop_identity_posterior_hash=str(
                value.get("crop_identity_posterior_hash") or ""
            ),
            evidence_ledger_hash=str(value.get("evidence_ledger_hash") or ""),
            weather_forcing_hash=str(value.get("weather_forcing_hash") or ""),
            previous_phenology_event_id=value.get("previous_phenology_event_id"),
            model_receipt_id=str(
                value.get("model_receipt_id") or "phenology-hmm-v3.2-diagnostic"
            ),
            plant_date_status=str(value.get("plant_date_status") or "unknown"),
            plant_date_min=value.get("plant_date_min"),
            plant_date_max=value.get("plant_date_max"),
            independent_evidence_count=int(value.get("independent_evidence_count") or 0),
            evidence_observation_ids=tuple(value.get("evidence_observation_ids") or ()),
            degradation_reasons=tuple(value.get("degradation_reasons") or ()),
            contract_version=str(
                value.get("contract_version") or PHENOLOGY_POSTERIOR_CONTRACT_VERSION
            ),
            content_hash=str(value.get("content_hash") or ""),
        )


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def unavailable_phenology_publication(reason: str) -> Dict[str, Any]:
    """Return the only truthful downstream shape when Layer 2 has no valid receipt."""
    return {
        "resolved_crop_stage": "UNKNOWN",
        "phenology_evidence_class": "unavailable",
        "phenology_authority": "unavailable",
        "phenology_source": "unavailable",
        "required_phenology_source": CANONICAL_PHENOLOGY_SOURCE,
        "phenology_confidence": 0.0,
        "phenology_posterior_hash": "",
        "phenology_receipt_valid": False,
        "phenology_evidence_needed_reason": str(reason or "canonical_layer2_phenology_receipt_required"),
        "stage_available": False,
        "contract_version": "phenology_authority_v2_consumer",
    }


def consume_canonical_phenology_output(
    veg_int: Any,
    *,
    expected_namespace: Optional[PlotNamespace] = None,
) -> Dict[str, Any]:
    """Consume a Layer-2 canonical posterior without inventing a replacement stage.

    Raw ``stage_by_day`` values and administrative crop-cycle status are deliberately
    ignored.  Downstream layers may display a stage only after the canonical receipt
    has passed its content-hash and optional namespace checks.
    """
    temporal = _field(veg_int, "veg_temporal", veg_int)
    phenology = _field(temporal, "phenology", None)
    raw_receipt = _field(phenology, "canonical_posterior", None)
    if not isinstance(raw_receipt, Mapping):
        return unavailable_phenology_publication(
            "canonical_layer2_phenology_receipt_required"
        )
    try:
        receipt = CanonicalPhenologyPosteriorV2.from_dict(raw_receipt)
    except (TypeError, ValueError, KeyError):
        return unavailable_phenology_publication(
            "canonical_layer2_phenology_receipt_invalid"
        )
    if expected_namespace is not None and receipt.namespace.to_tuple() != expected_namespace.to_tuple():
        return unavailable_phenology_publication(
            "canonical_layer2_phenology_namespace_mismatch"
        )
    if (
        receipt.current_stage == "UNKNOWN"
        or receipt.stage_authority not in PUBLISHED_PHENOLOGY_AUTHORITIES
    ):
        reason = next(
            (str(item) for item in receipt.degradation_reasons if str(item).strip()),
            "additional_independent_phenology_evidence_required",
        )
        result = unavailable_phenology_publication(reason)
        result.update({
            "phenology_posterior_hash": receipt.content_hash,
            "phenology_authority": receipt.stage_authority,
            "phenology_evidence_class": receipt.stage_authority,
            "phenology_source": CANONICAL_PHENOLOGY_SOURCE,
            "phenology_receipt_valid": True,
            "season_anchor_status": receipt.season_anchor_status,
            "calibration_status": receipt.calibration_status,
            "effective_at": receipt.effective_at,
            "crop_cycle_id": receipt.crop_cycle_id,
        })
        return result
    return {
        "resolved_crop_stage": receipt.current_stage,
        "phenology_evidence_class": receipt.stage_authority,
        "phenology_authority": receipt.stage_authority,
        "phenology_source": CANONICAL_PHENOLOGY_SOURCE,
        "phenology_confidence": receipt.stage_confidence,
        "phenology_posterior_hash": receipt.content_hash,
        "phenology_receipt_valid": True,
        "phenology_evidence_needed_reason": "",
        "stage_available": True,
        "season_anchor_status": receipt.season_anchor_status,
        "calibration_status": receipt.calibration_status,
        "effective_at": receipt.effective_at,
        "crop_cycle_id": receipt.crop_cycle_id,
        "contract_version": "phenology_authority_v2_consumer",
    }


def normalize_published_phenology(
    resolved_crop_stage: Any,
    phenology_context: Any,
) -> Tuple[str, Dict[str, Any]]:
    """Fail closed when serializing an already-produced Layer-10 envelope."""
    context = dict(phenology_context) if isinstance(phenology_context, Mapping) else {}
    stage = str(
        resolved_crop_stage or context.get("resolved_crop_stage") or "UNKNOWN"
    ).strip().upper().replace(" ", "_")
    authority = str(
        context.get("phenology_authority")
        or context.get("phenology_evidence_class")
        or "unavailable"
    ).strip().lower()
    source = str(context.get("phenology_source") or "").strip()
    receipt_hash = str(context.get("phenology_posterior_hash") or "").strip().lower()
    receipt_valid = (
        authority in PHENOLOGY_AUTHORITIES
        and source == CANONICAL_PHENOLOGY_SOURCE
        and bool(_SHA256_PATTERN.fullmatch(receipt_hash))
        and context.get("phenology_receipt_valid") is not False
    )
    stage_valid = (
        stage in PHENOLOGY_STAGES
        and stage != "UNKNOWN"
        and authority in PUBLISHED_PHENOLOGY_AUTHORITIES
        and receipt_valid
    )
    if not stage_valid:
        reason = str(
            context.get("phenology_evidence_needed_reason")
            or "canonical_layer2_phenology_receipt_required"
        )
        if receipt_valid:
            context.update({
                "resolved_crop_stage": "UNKNOWN",
                "phenology_authority": authority,
                "phenology_evidence_class": authority,
                "phenology_source": CANONICAL_PHENOLOGY_SOURCE,
                "phenology_posterior_hash": receipt_hash,
                "phenology_receipt_valid": True,
                "phenology_evidence_needed_reason": reason,
                "stage_available": False,
                "contract_version": "phenology_authority_v2_consumer",
            })
            return "UNKNOWN", context
        return "UNKNOWN", unavailable_phenology_publication(reason)
    context.update({
        "resolved_crop_stage": stage,
        "phenology_authority": authority,
        "phenology_evidence_class": authority,
        "phenology_source": CANONICAL_PHENOLOGY_SOURCE,
        "phenology_posterior_hash": receipt_hash,
        "phenology_receipt_valid": True,
        "phenology_evidence_needed_reason": "",
        "stage_available": True,
        "contract_version": "phenology_authority_v2_consumer",
    })
    return stage, context
