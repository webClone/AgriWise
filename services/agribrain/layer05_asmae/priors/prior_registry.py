"""
V73: Prior registry — ingest and manage priors from Layers 2–8.

Design rules:
  1. Every prior carries anti-leakage fields
  2. Missing/degraded priors return explicit status, never None
  3. Layer 8 is constraints-only, never recommendations as state evidence
  4. All priors versioned and traceable
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

from .layer2_vegetation_priors import extract_layer2_priors
from .layer3_water_priors import extract_layer3_priors
from .layer4_nutrient_priors import extract_layer4_priors
from .layer5_bio_confounders import extract_layer5_priors
from .layer6_yield_sensitivity import extract_layer6_priors
from .layer7_risk_priors import extract_layer7_priors
from .layer8_constraints import extract_layer8_constraints


# ── Prior Builder Registry ──────────────────────────────────────────────────

PRIOR_BUILDERS = {
    "layer2": extract_layer2_priors,
    "layer3": extract_layer3_priors,
    "layer4": extract_layer4_priors,
    "layer5": extract_layer5_priors,
    "layer6": extract_layer6_priors,
    "layer7": extract_layer7_priors,
    "layer8": extract_layer8_constraints,
}


def ingest_all_priors(
    coarse_outputs: dict,
    crop_context: dict,
    plot_id: Optional[str] = None,
    geometry_hash: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Ingest priors from all registered layers.

    Returns a dict keyed by layer name, each containing
    the prior dict with anti-leakage fields.

    Never returns None for any layer — always returns at least
    a degraded prior with explicit status.
    """
    priors: Dict[str, Dict[str, Any]] = {}

    for layer_name, builder in PRIOR_BUILDERS.items():
        try:
            if layer_name == "layer2":
                # Layer 2 needs crop_context
                prior = builder(coarse_outputs, crop_context)
            elif layer_name == "layer8":
                prior = builder(coarse_outputs)
            else:
                prior = builder(coarse_outputs)

            priors[layer_name] = prior

        except Exception as e:
            logger.warning(
                "Failed to extract %s priors: %s", layer_name, e,
            )
            priors[layer_name] = _make_degraded_prior(
                layer_name, reason=f"extraction_error: {e}",
            )

    # Ingest learning memory prior
    p_id = plot_id or crop_context.get("plot_id") or coarse_outputs.get("plot_id")
    g_hash = geometry_hash or crop_context.get("geometry_hash") or coarse_outputs.get("geometry_hash")
    crop_season_id = crop_context.get("crop_season_id") or coarse_outputs.get("crop_season_id") or "default_season"

    learning_memory_prior = _make_degraded_prior("learning_memory", reason="no_memory_found")
    if p_id and g_hash:
        try:
            from asmae_learn.plot_memory import load_plot_memory
            memory_data = load_plot_memory(p_id, g_hash, crop_season_id)
            if memory_data and memory_data.memory_status != "revoked":
                status = memory_data.memory_status
                status_caps = {
                    "candidate": 0.2,
                    "provisional": 0.4,
                    "validated": 0.7,
                    "certified_plot_memory": 0.9,
                    "revoked": 0.0
                }
                status_cap = status_caps.get(status, 0.0)
                
                # Retrieve variable trust and confidence
                variables = getattr(memory_data, "variables", {}) or {}
                if variables:
                    trusts = [v.get("trust", 0.0) for v in variables.values()]
                    confidences = [v.get("confidence", 0.0) for v in variables.values()]
                    mean_trust = sum(trusts) / len(trusts) if trusts else 0.0
                    mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                else:
                    mean_trust = 0.0
                    mean_confidence = 0.0
                    
                evidence_count = getattr(memory_data, "evidence_count", 0)
                evidence_factor = min(1.0, evidence_count / 5.0)
                
                prior_conf = min(
                    status_cap,
                    mean_trust,
                    mean_confidence,
                    evidence_factor
                )
                prior_conf = round(prior_conf, 4)

                learning_memory_prior = {
                    "source_layer": "learning_memory",
                    "source_run_id": "",
                    "source_timestamp": "",
                    "valid_time_window": "",
                    "uses_future_holdout": False,
                    "status": "available",
                    "confidence": prior_conf,
                    "usable_as_prior": True,
                    "memory_data": memory_data.to_dict(),
                }
            elif memory_data and memory_data.memory_status == "revoked":
                learning_memory_prior = _make_degraded_prior("learning_memory", reason="memory_revoked")
        except Exception as e:
            logger.warning("Failed to load plot memory prior: %s", e)
            learning_memory_prior = _make_degraded_prior("learning_memory", reason=f"load_error: {e}")

    priors["learning_memory"] = learning_memory_prior

    # Summary logging
    available = sum(1 for p in priors.values() if p.get("status") == "available")
    degraded = sum(1 for p in priors.values() if p.get("status") == "degraded")
    logger.info(
        "V73 priors: %d available, %d degraded (of %d total)",
        available, degraded, len(priors),
    )

    return priors


def _make_degraded_prior(layer_name: str, reason: str = "") -> Dict[str, Any]:
    """Create an explicit degraded prior (never None).

    This prevents ASMAE from silently treating absent priors
    as neutral truth.
    """
    return {
        "source_layer": layer_name,
        "source_run_id": "",
        "source_timestamp": "",
        "valid_time_window": "",
        "uses_future_holdout": False,
        "status": "degraded",
        "confidence": 0.0,
        "usable_as_prior": False,
        "reason": reason or f"missing_{layer_name}_output",
    }


def get_prior_status_summary(
    priors: Dict[str, Dict[str, Any]],
) -> Dict[str, str]:
    """Return a quick status summary: {layer_name: status}."""
    return {k: v.get("status", "unknown") for k, v in priors.items()}
