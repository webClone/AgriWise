"""Public DTO construction for the canonical crop-identify endpoint.

The crop posterior is an internal scientific record.  In particular,
``species_ranking`` contains ranking diagnostics, not calibrated species
probabilities and not registry display metadata.  This module is the single
boundary that converts those records into the stable API shape consumed by
the browser.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional

from services.agribrain.crop_database import CROP_REGISTRY


CROP_IDENTIFY_DTO_VERSION = "crop-identify-dto-v2"

_AUTHORITATIVE_DECLARATIONS = {
    "USER_CONFIRMED",
    "FARMER_CONFIRMED",
    "AGRONOMIST_CONFIRMED",
    "REGISTRY_DECLARED",
    "OFFICIAL_PARCEL_LABEL",
}

_GENERIC_DECLARATIONS = {
    "annual",
    "cereal",
    "fallow",
    "forage",
    "industrial",
    "legume",
    "mixed",
    "orchard",
    "perennial",
    "tuber",
    "vegetable",
}

_GROUP_LABELS = {
    "solanaceae_veg": "Solanaceae vegetables",
    "winter_cereal": "Winter cereals",
    "summer_cereal": "Summer cereals",
    "orchard_tree": "Orchard trees",
    "pulse_legume": "Pulse legumes",
}


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _share(value: Any) -> Optional[float]:
    parsed = _finite(value)
    if parsed is None:
        return None
    return max(0.0, min(1.0, parsed))


def _display_name(code: str) -> str:
    return " ".join(part.capitalize() for part in code.split("_") if part)


def _group_label(code: str) -> str:
    return _GROUP_LABELS.get(code, _display_name(code))


def _distribution_leader(distribution: Mapping[str, Any]) -> tuple[str, Optional[float]]:
    parsed = {
        str(code): share
        for code, value in distribution.items()
        if (share := _share(value)) is not None
    }
    if not parsed:
        return "unknown", None
    return max(parsed.items(), key=lambda item: item[1])


def normalize_crop_candidate(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize one internal species-ranking row into the public DTO.

    ``ranking_share`` is deliberately retained under that exact name.  It is
    a normalized ranking diagnostic and must not be renamed to probability.
    """

    code = str(row.get("code") or "unknown").strip().lower() or "unknown"
    spec = CROP_REGISTRY.get(code)
    ranking_share = _share(
        row.get("ranking_share", row.get("softmax_candidate_share"))
    )
    score = _finite(row.get("score"))
    crop_group = str(row.get("crop_group") or "unknown").strip() or "unknown"

    return {
        "code": code,
        "name": spec.name if spec is not None else _display_name(code),
        "name_ar": spec.name_ar if spec is not None else "",
        "architecture": spec.architecture if spec is not None else "unknown",
        "crop_group": crop_group,
        "score": score if score is not None else 0.0,
        "ranking_share": ranking_share,
        "data_quality_tier": row.get("data_quality_tier"),
        "breakdown": row.get("breakdown") if isinstance(
            row.get("breakdown"), Mapping
        ) else None,
    }


def _registry_crop(code: Any) -> Optional[Dict[str, Any]]:
    normalized = str(code or "").strip().lower()
    if not normalized:
        return None
    spec = CROP_REGISTRY.get(normalized)
    return {
        "code": normalized,
        "name": spec.name if spec is not None else _display_name(normalized),
        "name_ar": spec.name_ar if spec is not None else "",
        "architecture": spec.architecture if spec is not None else "unknown",
    }


def build_crop_identify_dto(canonical: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the truthful public crop-identification contract."""

    authority = str(canonical.get("authority") or "UNKNOWN").strip().upper()
    declared_code = str(
        canonical.get("declared_crop_normalized") or ""
    ).strip().lower()
    declared_is_species = bool(
        declared_code
        and declared_code not in _GENERIC_DECLARATIONS
        and authority in _AUTHORITATIVE_DECLARATIONS
    )
    declared_crop = _registry_crop(declared_code) if declared_is_species else None

    raw_ranking = canonical.get("species_ranking")
    candidates = [
        normalize_crop_candidate(row)
        for row in (raw_ranking if isinstance(raw_ranking, list) else [])
        if isinstance(row, Mapping)
    ]

    group_distribution = canonical.get("crop_group_posterior")
    if not isinstance(group_distribution, Mapping):
        group_distribution = {}
    top_group = str(canonical.get("top_group") or "unknown").strip() or "unknown"
    top_group_share = _share(
        canonical.get("top_group_probability", group_distribution.get(top_group))
    )
    if top_group_share is None:
        top_group_share = _share(group_distribution.get(top_group))
    conditioned_available = (
        top_group.lower() != "unknown" and top_group_share is not None
    )
    temporal_prior = canonical.get("temporal_prior")
    context_conditioned_group_ranking = {
        "available": conditioned_available,
        "code": top_group if conditioned_available else None,
        "label": _group_label(top_group) if conditioned_available else None,
        "ranking_share": top_group_share if conditioned_available else None,
        "calibrated": False,
        "calibration_status": str(
            canonical.get("calibration_status") or "not_calibrated"
        ),
        "includes_registry_declaration": bool(declared_code),
        "includes_temporal_prior": bool(
            isinstance(temporal_prior, Mapping)
            and temporal_prior.get("applied") is True
        ),
        "role": "asmae_conditioning_not_independent_eo_evidence",
    }

    # Only an explicitly separated, declaration-free model distribution may
    # be described as EO-informed support.  The primary crop_group_posterior
    # includes registry/context priors and is never reused for this claim.
    model_distribution = canonical.get("model_context_group_posterior")
    model_support = canonical.get("model_context_support")
    if not isinstance(model_distribution, Mapping):
        model_distribution = {}
    if not isinstance(model_support, Mapping):
        model_support = {}
    quality = canonical.get("evidence_quality")
    if not isinstance(quality, Mapping):
        quality = {}
    physical_count = int(
        _finite(
            model_support.get(
                "admitted_physical_acquisition_count",
                quality.get("physical_acquisition_count", 0),
            )
        )
        or 0
    )
    admitted_ndvi_count = int(
        _finite(
            model_support.get(
                "admitted_ndvi_count", quality.get("admitted_ndvi_count", 0)
            )
        )
        or 0
    )
    model_status = str(model_support.get("status") or "unavailable").lower()
    model_group, model_share = _distribution_leader(model_distribution)
    model_available = bool(
        model_distribution
        and physical_count > 0
        and model_status not in {"unavailable", "insufficient", "no_support"}
        and model_group.lower() != "unknown"
        and model_share is not None
        and model_support.get("registry_declaration_included") is not True
        and model_support.get("temporal_prior_included") is not True
    )
    group_support = {
        "available": model_available,
        "code": model_group if model_available else None,
        "label": _group_label(model_group) if model_available else None,
        "ranking_share": model_share if model_available else None,
        "calibrated": False,
        "calibration_status": "uncalibrated_model_context_ranking",
        "deepest_supported_level": "CROP_GROUP" if model_available else "UNKNOWN",
        "status": model_status if model_available else "unavailable",
        "source_class": "model_context_eo_informed" if model_available else None,
        "admitted_physical_acquisition_count": physical_count,
        "admitted_ndvi_count": admitted_ndvi_count,
        "context_features_may_be_included": (
            model_support.get("context_features_may_be_included") is True
        ),
    }

    raw_species_posterior = (
        canonical.get("l3_species_posterior")
        or canonical.get("species_posterior")
    )
    if not isinstance(raw_species_posterior, Mapping):
        raw_species_posterior = {}
    confirmed_species, confirmed_share = _distribution_leader(
        raw_species_posterior
    )
    species_published = bool(
        canonical.get("species_probability_published") is True
        and confirmed_species != "unknown"
        and confirmed_share is not None
    )
    species_confirmation = {
        "available": species_published,
        # Never promote the heuristic species-ranking leader into a confirmed
        # species. Confirmation names the independently published posterior.
        "code": confirmed_species if species_published else None,
        "reason": (
            "A validated species posterior is available."
            if species_published
            else (
                "The species publication flag has no compatible species posterior."
                if canonical.get("species_probability_published") is True
                else "Satellite evidence has not independently confirmed a crop species."
            )
        ),
    }

    if declared_crop and model_available:
        summary = (
            f"{declared_crop['name']} is registry declared. Satellite evidence "
            f"informs a model ranking led by the {_group_label(model_group)} "
            "group only; independent "
            "species confirmation is unavailable."
        )
    elif declared_crop:
        summary = (
            f"{declared_crop['name']} is registry declared. Satellite evidence "
            "is insufficient for independent species confirmation."
        )
    elif model_available:
        summary = (
            f"Satellite evidence informs a model ranking led by the "
            f"{_group_label(model_group)} group; "
            "exact species is unresolved."
        )
    else:
        summary = "Crop identity is unresolved from the currently admitted evidence."

    return {
        "crop_identify_dto_version": CROP_IDENTIFY_DTO_VERSION,
        "identity_authority": authority,
        "declared_crop": declared_crop,
        "eo_group_support": group_support,
        "context_conditioned_group_ranking": context_conditioned_group_ranking,
        "independent_species_confirmation": species_confirmation,
        "identity_summary": summary,
        "top_crop": declared_crop["code"] if declared_crop else None,
        "top_confidence": None,
        "confidence_label": "NOT_CALIBRATED",
        "candidates": candidates,
    }


def build_crop_identify_publication(
    canonical: Mapping[str, Any],
    *,
    plot_id: str,
    status: str,
    canonical_snapshot: bool,
    worldline_event_id: Any = None,
    snapshot_ref: Any = None,
    reason: Any = None,
) -> Dict[str, Any]:
    """Return the public DTO without leaking internal diagnostic mixtures."""

    publication = {
        **build_crop_identify_dto(canonical),
        "status": str(status),
        "plot_id": str(plot_id),
        "canonical_snapshot": bool(canonical_snapshot),
        "worldline_event_id": worldline_event_id,
        "snapshot_ref": snapshot_ref,
    }
    if reason:
        publication["reason"] = str(reason)
    return publication


__all__ = [
    "CROP_IDENTIFY_DTO_VERSION",
    "build_crop_identify_dto",
    "build_crop_identify_publication",
    "normalize_crop_candidate",
]
