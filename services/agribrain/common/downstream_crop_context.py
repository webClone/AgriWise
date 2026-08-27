"""Fail-closed crop and phenology semantics for Layers 3-8.

Downstream scientific engines historically accepted a single ``crop`` string and
single ``stage`` string.  Those values can be registry declarations or
administrative status, neither of which is sufficient authority for a
species/stage-specific scientific calculation.  This module is the migration
boundary: it consumes canonical Layer 2 posteriors when present, preserves
their hashes, and otherwise exposes only declaration/group/unknown context.

It deliberately does *not* infer crop identity or phenology from NDVI, crop
status, dates, or downstream outputs.  Layer 2 remains the sole scientific
owner.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from services.agribrain.scientific_contracts.crop_governance import (
    CropModelReceiptV1,
)
from services.agribrain.scientific_contracts.crop_phenology import (
    CanonicalPhenologyPosteriorV2,
)


_CONFIRMED_SPECIES_AUTHORITIES = {
    "FARMER_CONFIRMED",
    "USER_CONFIRMED",  # legacy compatibility alias
    "AGRONOMIST_CONFIRMED",
    "OFFICIAL_PARCEL_LABEL",
}
_CALIBRATED_SPECIES_AUTHORITIES = {
    "EO_SPECIES_CALIBRATED",
    "MULTIMODAL_SPECIES_CALIBRATED",
}
_FORBIDDEN_STAGE_AUTHORITIES = {
    "",
    "UNKNOWN",
    "ADMINISTRATIVE",
    "ADMINISTRATIVE_STATUS",
    "CROP_STATUS",
    "PRIOR_ONLY",
}
_UNKNOWN_TOKENS = {"", "NONE", "NULL", "UNKNOWN", "OTHER", "UNRESOLVED"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CROP_POSTERIOR_CONTRACT_VERSION = "crop_identity_posterior_v3"


def _mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return {}
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            result = to_dict()
            return dict(result) if isinstance(result, Mapping) else {}
        except Exception:
            return {}
    data = getattr(value, "__dict__", None)
    return dict(data) if isinstance(data, Mapping) else {}


def _finite_probability(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return default
    return max(0.0, min(1.0, parsed))


def _normalise_distribution(value: Any) -> Dict[str, float]:
    raw = _mapping(value)
    cleaned: Dict[str, float] = {}
    for key, probability in raw.items():
        token = str(key or "").strip()
        if not token:
            continue
        parsed = _finite_probability(probability, -1.0)
        if parsed >= 0.0:
            cleaned[token] = parsed
    total = sum(cleaned.values())
    if total <= 0.0:
        return {}
    return {key: value / total for key, value in cleaned.items()}


def _first_mapping(*values: Any) -> Dict[str, Any]:
    for value in values:
        result = _mapping(value)
        if result:
            return result
    return {}


def _get_attr_or_key(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default) if value is not None else default


def _crop_posterior_hash(value: Mapping[str, Any]) -> str:
    """Reproduce Layer 2's scientific hash without trusting its envelope."""
    payload = {
        key: item
        for key, item in value.items()
        if key not in {"content_hash", "generated_at"}
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _validated_crop_posterior(
    value: Any,
    *,
    expected_plot_id: str = "",
    expected_cycle_id: str = "",
) -> Dict[str, Any]:
    """Return an immutable Layer-2 crop posterior only when identity is valid."""
    payload = _mapping(value)
    if not payload:
        return {}
    supplied_hash = str(payload.get("content_hash") or "").strip().lower()
    if (
        payload.get("contract_version") != _CROP_POSTERIOR_CONTRACT_VERSION
        or not _SHA256.fullmatch(supplied_hash)
        or supplied_hash != _crop_posterior_hash(payload)
    ):
        return {}
    plot_id = str(payload.get("plot_id") or "").strip()
    if expected_plot_id and plot_id != expected_plot_id:
        return {}
    cycle_id = str(payload.get("crop_cycle_identity") or "").strip()
    if expected_cycle_id and cycle_id != expected_cycle_id:
        return {}
    return payload


def _production_model_receipt_valid(crop: Mapping[str, Any]) -> bool:
    raw_receipt = crop.get("crop_model_receipt")
    if not isinstance(raw_receipt, Mapping):
        return False
    try:
        receipt = CropModelReceiptV1.from_dict(raw_receipt)
    except (TypeError, ValueError, KeyError):
        return False
    declared_hash = str(crop.get("crop_model_receipt_hash") or "").strip()
    return (
        receipt.production_eligible
        and declared_hash == receipt.content_hash
        and crop.get("ml_production_eligible") is True
    )


@dataclass(frozen=True)
class DownstreamCropPhenologyContext:
    """Resolved uncertainty/authority contract used by Layers 3-8."""

    declared_crop: Optional[str] = None
    selected_crop: Optional[str] = None
    selected_group: Optional[str] = None
    crop_mixture: Dict[str, float] = field(default_factory=dict)
    crop_resolution: str = "unknown"
    crop_authority: str = "UNKNOWN"
    crop_posterior_hash: str = ""
    species_specific_allowed: bool = False

    phenology_stage: str = "UNKNOWN"
    stage_posterior: Dict[str, float] = field(default_factory=dict)
    stage_confidence: float = 0.0
    phenology_authority: str = "UNKNOWN"
    phenology_posterior_hash: str = ""
    stage_specific_allowed: bool = False

    demotion_reasons: Tuple[str, ...] = ()

    @property
    def crop_for_species_engine(self) -> str:
        return self.selected_crop if self.species_specific_allowed and self.selected_crop else "unknown"

    @property
    def stage_for_discrete_engine(self) -> str:
        return self.phenology_stage if self.stage_specific_allowed else "UNKNOWN"

    @property
    def prescriptive_ready(self) -> bool:
        # A diagnostic Layer-2 stage may condition scouting calculations, but
        # it cannot authorize an irreversible crop/stage-specific action.
        # Prescriptive use remains default-deny until phenology is calibrated.
        return (
            self.species_specific_allowed
            and self.stage_specific_allowed
            and self.phenology_authority == "CALIBRATED"
        )

    @property
    def uncertainty_multiplier(self) -> float:
        if self.prescriptive_ready:
            return 1.0
        if self.species_specific_allowed or self.stage_specific_allowed:
            return 0.60
        if self.crop_resolution == "group_only":
            return 0.40
        return 0.25

    def lineage(self) -> Dict[str, Any]:
        return {
            "crop_posterior_hash": self.crop_posterior_hash,
            "phenology_posterior_hash": self.phenology_posterior_hash,
            "crop_resolution": self.crop_resolution,
            "crop_authority": self.crop_authority,
            "phenology_authority": self.phenology_authority,
            "species_specific_allowed": self.species_specific_allowed,
            "stage_specific_allowed": self.stage_specific_allowed,
            "demotion_reasons": list(self.demotion_reasons),
        }


def resolve_downstream_crop_phenology(
    *,
    inputs: Any = None,
    l2_output: Any = None,
    crop_posterior: Any = None,
    phenology_posterior: Any = None,
    declared_crop: Optional[str] = None,
    minimum_stage_probability: float = 0.50,
    minimum_stage_confidence: float = 0.50,
) -> DownstreamCropPhenologyContext:
    """Resolve canonical downstream context without inventing certainty.

    ``crop_config.crop`` is retained only as ``declared_crop``.  It never
    authorizes a species-specific engine by itself.  Phenology is accepted
    only from Layer 2's canonical posterior; administrative/config stage values
    are intentionally ignored.
    """

    crop_cfg = _mapping(_get_attr_or_key(inputs, "crop_config", {}))
    cycle_ctx = _mapping(_get_attr_or_key(inputs, "crop_cycle_context", None))
    input_namespace = _mapping(_get_attr_or_key(inputs, "plot_namespace", None))
    cycle_namespace = _mapping(cycle_ctx.get("plot_namespace"))
    expected_plot_id = str(
        cycle_namespace.get("plot_id")
        or input_namespace.get("plot_id")
        or _get_attr_or_key(inputs, "plot_id", "")
        or ""
    ).strip()
    expected_cycle_id = str(
        cycle_ctx.get("crop_cycle_id")
        or crop_cfg.get("crop_cycle_id")
        or ""
    ).strip()

    if declared_crop is None:
        declared_crop = (
            cycle_ctx.get("declared_crop_code")
            or crop_cfg.get("declared_crop_code")
            or crop_cfg.get("crop")
            or crop_cfg.get("crop_type")
        )
    declared = str(declared_crop or "").strip().lower() or None

    l2_provenance = _mapping(_get_attr_or_key(l2_output, "provenance", {}))
    raw_crop = _first_mapping(
        crop_posterior,
        _get_attr_or_key(inputs, "crop_identity_posterior", None),
        _get_attr_or_key(inputs, "crop_posterior", None),
        crop_cfg.get("crop_identity_posterior"),
        crop_cfg.get("crop_posterior"),
        l2_provenance.get("crop_identity_posterior"),
        l2_provenance.get("crop_posterior"),
    )
    crop = _validated_crop_posterior(
        raw_crop,
        expected_plot_id=expected_plot_id,
        expected_cycle_id=expected_cycle_id,
    )

    crop_authority = str(
        crop.get("authority")
        or crop.get("crop_identity_authority")
        or "UNKNOWN"
    ).upper()
    selected_level = str(
        crop.get("selected_level")
        or crop.get("deepest_publishable_level")
        or crop.get("deepest_calibrated_level")
        or crop.get("deepest_supported_level")
        or "UNKNOWN"
    ).upper()
    selected_identity = str(
        crop.get("selected_identity")
        or crop.get("selected_crop")
        or crop.get("top_species")
        or ""
    ).strip().lower() or None
    calibrated = bool(crop.get("calibrated", False))
    species_published = bool(crop.get("species_probability_published", False))
    species_distribution = _normalise_distribution(
        crop.get("l3_species_posterior")
        or crop.get("species_posterior")
    )
    if selected_identity is None and species_distribution:
        selected_identity = max(species_distribution, key=species_distribution.get).lower()

    species_specific_allowed = (
        selected_identity is not None
        and selected_identity.upper() not in _UNKNOWN_TOKENS
        and (
            crop_authority in _CONFIRMED_SPECIES_AUTHORITIES
            or (
                crop_authority in _CALIBRATED_SPECIES_AUTHORITIES
                and calibrated
                and species_published
                and "SPECIES" in selected_level
                and _production_model_receipt_valid(crop)
            )
        )
    )

    group_distribution = _normalise_distribution(
        crop.get("l2_group_posterior")
        or crop.get("crop_group_posterior")
        or crop.get("model_context_group_posterior")
    )
    selected_group = str(
        crop.get("selected_group") or crop.get("top_group") or ""
    ).strip().lower() or None
    non_unknown_groups = {
        key: value for key, value in group_distribution.items()
        if key.upper() not in _UNKNOWN_TOKENS
    }
    if selected_group is None and non_unknown_groups:
        selected_group = max(non_unknown_groups, key=non_unknown_groups.get).lower()

    if species_specific_allowed:
        crop_resolution = "species_confirmed" if crop_authority in _CONFIRMED_SPECIES_AUTHORITIES else "species_calibrated"
        crop_mixture = species_distribution or {selected_identity: 1.0}
    elif selected_group and selected_group.upper() not in _UNKNOWN_TOKENS:
        crop_resolution = "group_only"
        crop_mixture = group_distribution or {selected_group: 1.0}
    elif declared:
        crop_resolution = "declared_only"
        crop_mixture = {}
    else:
        crop_resolution = "unknown"
        crop_mixture = {}

    crop_hash = str(
        crop.get("content_hash")
        or crop.get("crop_posterior_hash")
        or crop_cfg.get("crop_posterior_hash")
        or l2_provenance.get("crop_posterior_hash")
        or l2_provenance.get("crop_posterior_lineage")
        or ""
    )

    pheno_obj = _get_attr_or_key(l2_output, "phenology", None)
    raw_pheno = _first_mapping(
        phenology_posterior,
        _get_attr_or_key(pheno_obj, "canonical_posterior", None),
        _get_attr_or_key(l2_output, "phenology_posterior", None),
    )
    pheno: Dict[str, Any] = {}
    if raw_pheno:
        try:
            receipt = CanonicalPhenologyPosteriorV2.from_dict(raw_pheno)
            namespace_matches = (
                not expected_plot_id
                or receipt.namespace.plot_id == expected_plot_id
            )
            cycle_matches = (
                not expected_cycle_id
                or str(receipt.crop_cycle_id or "") == expected_cycle_id
            )
            if namespace_matches and cycle_matches:
                pheno = receipt.to_dict()
        except (TypeError, ValueError, KeyError):
            pheno = {}
    stage_distribution = _normalise_distribution(pheno.get("stage_posterior"))
    stage = str(
        pheno.get("most_likely_stage")
        or pheno.get("current_stage")
        or "UNKNOWN"
    ).upper()
    if stage in _UNKNOWN_TOKENS and stage_distribution:
        stage = str(max(stage_distribution, key=stage_distribution.get)).upper()
    stage_probability = stage_distribution.get(stage, stage_distribution.get(stage.lower(), 0.0))
    if not stage_distribution and stage not in _UNKNOWN_TOKENS:
        stage_probability = _finite_probability(pheno.get("stage_confidence"), 0.0)
    stage_confidence = _finite_probability(
        pheno.get("stage_confidence", pheno.get("confidence", 0.0)),
        0.0,
    )
    phenology_authority = str(
        pheno.get("stage_authority") or pheno.get("authority") or "UNKNOWN"
    ).upper()
    stage_specific_allowed = (
        bool(pheno)
        and stage not in _UNKNOWN_TOKENS
        and phenology_authority not in _FORBIDDEN_STAGE_AUTHORITIES
        and stage_confidence >= minimum_stage_confidence
        and stage_probability >= minimum_stage_probability
    )
    if not stage_specific_allowed:
        stage = "UNKNOWN"

    phenology_hash = str(
        pheno.get("content_hash")
        or pheno.get("phenology_posterior_hash")
        or l2_provenance.get("phenology_posterior_hash")
        or ""
    )

    reasons = []
    if not species_specific_allowed:
        reasons.append(
            "crop_group_only" if crop_resolution == "group_only"
            else "crop_declaration_not_species_evidence" if crop_resolution == "declared_only"
            else "crop_identity_unknown"
        )
    if not pheno:
        reasons.append("canonical_phenology_missing")
    elif not stage_specific_allowed:
        reasons.append("phenology_uncertain_or_unknown")

    return DownstreamCropPhenologyContext(
        declared_crop=declared,
        selected_crop=selected_identity if species_specific_allowed else None,
        selected_group=selected_group,
        crop_mixture=crop_mixture,
        crop_resolution=crop_resolution,
        crop_authority=crop_authority,
        crop_posterior_hash=crop_hash,
        species_specific_allowed=species_specific_allowed,
        phenology_stage=stage,
        stage_posterior=stage_distribution,
        stage_confidence=stage_confidence,
        phenology_authority=phenology_authority,
        phenology_posterior_hash=phenology_hash,
        stage_specific_allowed=stage_specific_allowed,
        demotion_reasons=tuple(reasons),
    )
