"""
V73: Layer 2 vegetation priors for ASMAE.

Extracts from Layer 2 (Vegetation Intelligence):
  - Phenology stage and growth curve position
  - Crop identity probability
  - Stage-specific observation noise modifiers
  - Growth trajectory priors
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def extract_layer2_priors(
    coarse_outputs: dict,
    crop_context: dict,
) -> Dict[str, Any]:
    """Extract vegetation priors from Layer 2 outputs.

    Returns a standardized prior dict with anti-leakage fields.
    """
    l2 = coarse_outputs.get("layer2_intelligence", {})
    available = bool(l2) and l2.get("status") in ("available", "partial")

    # Extract phenology stage
    phenology_stage = l2.get("phenology_stage", "unknown")
    growth_position = l2.get("growth_position")
    crop_type = (
        crop_context.get("crop")
        or crop_context.get("crop_type")
        or "unknown"
    )
    crop_group_posterior = dict(
        crop_context.get("crop_group_posterior") or {}
    )
    known_mass = max(
        0.0,
        1.0 - float(crop_group_posterior.get("unknown", 1.0)),
    ) if crop_group_posterior else 0.0
    crop_confidence = min(
        known_mass,
        float(crop_context.get("confidence", known_mass) or 0.0),
    )

    # Stage-specific noise modifiers
    stage_noise = _stage_noise_modifiers(phenology_stage)

    prior = {
        "source_layer": "layer2_intelligence",
        "source_run_id": l2.get("run_id", ""),
        "source_timestamp": l2.get("timestamp", ""),
        "valid_time_window": l2.get("valid_window", ""),
        "uses_future_holdout": False,
        "status": "available" if available else "degraded",
        "confidence": crop_confidence,
        "usable_as_prior": available,
        "reason": "" if available else l2.get("reason", "missing_layer2_output"),
        "phenology_stage": phenology_stage,
        "growth_position": growth_position,
        "crop_type": crop_type,
        "crop_group_posterior": crop_group_posterior,
        "crop_mixture_used": bool(crop_group_posterior),
        "crop_mixture_known_mass": known_mass,
        "crop_posterior_hash": crop_context.get("crop_posterior_hash"),
        "stage_noise_modifiers": stage_noise,
    }

    if not available:
        prior["status"] = "degraded"
        prior["usable_as_prior"] = False
        prior["reason"] = "missing_layer2_output"

    return prior


def _stage_noise_modifiers(stage: str) -> Dict[str, float]:
    """Return noise multipliers for each phenology stage."""
    modifiers = {
        "bare_soil":      {"ndvi": 1.5, "ndre": 2.0, "ndmi": 1.2},
        "emergence":      {"ndvi": 1.3, "ndre": 1.5, "ndmi": 1.1},
        "vegetative":     {"ndvi": 1.0, "ndre": 1.0, "ndmi": 1.0},
        "reproductive":   {"ndvi": 1.0, "ndre": 1.0, "ndmi": 1.0},
        "senescence":     {"ndvi": 1.3, "ndre": 1.5, "ndmi": 1.2},
        "harvest":        {"ndvi": 1.8, "ndre": 2.0, "ndmi": 1.5},
    }
    return modifiers.get(stage, {"ndvi": 1.0, "ndre": 1.0, "ndmi": 1.0})
