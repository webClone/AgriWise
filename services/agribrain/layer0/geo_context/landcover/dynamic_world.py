"""
Dynamic World normalizer.

Parses probability bands, computes per-class mean probabilities
using alpha-weighted summaries (Revision 2).
Applies probability validation and confidence cap (Revision 6).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from layer0.geo_context.schemas import RasterInput, alpha_weighted_mean
from layer0.geo_context.landcover.schemas import (
    DYNAMIC_WORLD_CLASSES,
    DYNAMIC_WORLD_MAX_CONFIDENCE,
    DynamicWorldContext,
)


def normalize_dynamic_world(
    probability_bands: Dict[str, RasterInput],
    acquisition_date: Optional[str] = None,
) -> DynamicWorldContext:
    """Compute alpha-weighted probability means from Dynamic World bands.

    Args:
        probability_bands: dict mapping class name -> RasterInput with probabilities.
        acquisition_date: ISO date string of the DW acquisition.

    Each RasterInput.data should contain probability values [0, 1].
    """
    if not probability_bands:
        return DynamicWorldContext(
            dynamic_landcover_confidence=0.0,
            probability_sum_valid=False,
        )

    # Compute per-class probability means
    prob_means: Dict[str, float] = {}
    reference_band = None

    for cls_name in DYNAMIC_WORLD_CLASSES:
        band = probability_bands.get(cls_name)
        if band is not None:
            reference_band = reference_band or band
            mean_val = alpha_weighted_mean(band.data, band.valid_mask, band.alpha_mask)
            prob_means[cls_name] = round(mean_val if mean_val is not None else 0.0, 6)
        else:
            prob_means[cls_name] = 0.0

    # Validate probability sum ~= 1 (Revision 6)
    prob_sum = sum(prob_means.values())
    prob_sum_valid = 0.8 <= prob_sum <= 1.2  # tolerance for rounding

    # Entropy: -sum(p * log(p))
    probs = np.array(list(prob_means.values()))
    probs_safe = np.maximum(probs, 1e-10)
    entropy = float(-np.sum(probs_safe * np.log(probs_safe)))
    max_entropy = float(-len(probs) * (1.0 / len(probs)) * np.log(1.0 / len(probs)))
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

    # Confidence = (1 - normalized_entropy) capped at 0.75 (Revision 6)
    raw_confidence = 1.0 - normalized_entropy
    confidence = min(raw_confidence, DYNAMIC_WORLD_MAX_CONFIDENCE)

    # Further reduce confidence if prob sum is invalid
    if not prob_sum_valid:
        confidence *= 0.5

    # Recent non-crop alert: crop probability < 0.3 is a warning
    crop_prob = prob_means.get("crops", 0.0)
    non_crop_alert = crop_prob < 0.3

    return DynamicWorldContext(
        crop_probability_mean=prob_means.get("crops", 0.0),
        tree_probability_mean=prob_means.get("trees", 0.0),
        water_probability_mean=prob_means.get("water", 0.0),
        built_probability_mean=prob_means.get("built", 0.0),
        bare_probability_mean=prob_means.get("bare", 0.0),
        flooded_vegetation_probability_mean=prob_means.get("flooded_vegetation", 0.0),
        class_entropy=round(normalized_entropy, 4),
        dynamic_landcover_confidence=round(confidence, 4),
        recent_non_crop_alert=non_crop_alert,
        probability_sum_valid=prob_sum_valid,
        acquisition_date=acquisition_date,
    )
