"""
ESA WorldCover normalizer.

Parses 10 m land-cover class raster (11 classes), computes per-class
fractions using alpha-weighted summaries (Revision 2).
Tracks unknown/unmapped fractions (Revision 5).
Categorical downsampling uses mode, not mean.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from layer0.geo_context.schemas import RasterInput
from layer0.geo_context.landcover.schemas import (
    ESA_WORLDCOVER_CLASSES,
    WorldCoverContext,
)


def normalize_worldcover(
    raster: RasterInput,
) -> WorldCoverContext:
    """Compute alpha-weighted land-cover fractions from ESA WorldCover raster.

    Args:
        raster: RasterInput with integer class IDs as data.

    Returns:
        WorldCoverContext with per-class fractions and unknown handling.
    """
    data = raster.data.astype(int)
    valid = raster.valid_mask
    alpha = raster.alpha_mask if raster.alpha_mask is not None else np.ones_like(raster.data, dtype=np.float64)
    
    plot_alpha_weight = alpha.sum()
    valid_alpha_weight = (alpha * valid).sum()
    invalid_alpha_weight = (alpha * ~valid).sum()

    if plot_alpha_weight == 0:
        return WorldCoverContext(
            landcover_valid_fraction=0.0,
            unknown_fraction=0.0,
            unmapped_fraction=1.0,
        )

    # Compute per-class fractions
    fractions: Dict[str, float] = {}
    known_alpha_weight = 0.0

    for class_id, class_name in ESA_WORLDCOVER_CLASSES.items():
        class_mask = (data == class_id) & valid
        class_weight = (alpha * class_mask.astype(float)).sum()
        frac = float(class_weight / plot_alpha_weight)
        fractions[class_name] = round(frac, 6)
        known_alpha_weight += class_weight

    # Unknown = valid but not matching any known class (Revision 5)
    known_ids = set(ESA_WORLDCOVER_CLASSES.keys())
    unknown_mask = valid & ~np.isin(data, list(known_ids))
    unknown_alpha_weight = (alpha * unknown_mask.astype(float)).sum()
    
    unknown_frac = float(unknown_alpha_weight / plot_alpha_weight)
    unmapped_frac = float(invalid_alpha_weight / plot_alpha_weight)
    valid_frac = float(known_alpha_weight / plot_alpha_weight)

    # Non-ag fraction
    non_ag = (
        fractions.get("tree_cover", 0) +
        fractions.get("built_up", 0) +
        fractions.get("permanent_water", 0) +
        fractions.get("shrubland", 0) +
        fractions.get("herbaceous_wetland", 0) +
        fractions.get("mangrove", 0) +
        fractions.get("moss_lichen", 0) +
        fractions.get("snow_ice", 0)
    )

    # Majority class
    majority = max(fractions, key=fractions.get) if fractions else "unknown"

    # Purity = fraction of dominant class
    purity = max(fractions.values()) if fractions else 0.0

    # Confidence = valid fraction * purity
    confidence = round(valid_frac * purity, 4)

    flags: List[str] = []
    if unknown_frac > 0.05:
        flags.append("LANDCOVER_UNMAPPED_CLASS")
    if valid_frac < 0.8:
        flags.append("LANDCOVER_LOW_VALID_FRACTION")

    return WorldCoverContext(
        cropland_fraction=fractions.get("cropland", 0.0),
        tree_cover_fraction=fractions.get("tree_cover", 0.0),
        grassland_fraction=fractions.get("grassland", 0.0),
        shrubland_fraction=fractions.get("shrubland", 0.0),
        builtup_fraction=fractions.get("built_up", 0.0),
        water_fraction=fractions.get("permanent_water", 0.0),
        bare_sparse_fraction=fractions.get("bare_sparse", 0.0),
        wetland_fraction=fractions.get("herbaceous_wetland", 0.0),
        unknown_fraction=round(unknown_frac, 6),
        unmapped_fraction=round(unmapped_frac, 6),
        landcover_valid_fraction=round(valid_frac, 6),
        non_ag_fraction=round(non_ag, 6),
        landcover_majority_class=majority,
        landcover_purity_score=round(purity, 4),
        landcover_confidence=confidence,
    )
