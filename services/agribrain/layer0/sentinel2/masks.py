"""
Sentinel-2 SCL Mask Engine — Multi-layer mask generation from Scene Classification.

Produces 7 separate mask layers from SCL, each with clear crop-inference semantics.
SCL 7 (low cloud) and SCL 10 (cirrus) are marginal, not rejected outright.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# SCL class constants
SCL_NO_DATA = 0
SCL_SATURATED = 1
SCL_DARK_SHADOW = 2
SCL_CLOUD_SHADOW = 3
SCL_VEGETATION = 4
SCL_BARE_SOIL = 5
SCL_WATER = 6
SCL_CLOUD_LOW_PROB = 7
SCL_CLOUD_MEDIUM_PROB = 8
SCL_CLOUD_HIGH_PROB = 9
SCL_THIN_CIRRUS = 10
SCL_SNOW_ICE = 11


@dataclass
class Sentinel2MaskSet:
    """Complete set of derived masks from SCL + dataMask."""
    valid_for_index: List[List[int]] = field(default_factory=list)
    valid_for_crop_inference: List[List[int]] = field(default_factory=list)
    cloud_like: List[List[int]] = field(default_factory=list)
    shadow_like: List[List[int]] = field(default_factory=list)
    marginal: List[List[int]] = field(default_factory=list)
    water: List[List[int]] = field(default_factory=list)
    snow: List[List[int]] = field(default_factory=list)

    # Per-pixel sigma inflation factor from marginal classification
    sigma_inflation: List[List[float]] = field(default_factory=list)


def compute_masks(
    scl_raster: List[List[Optional[float]]],
    datamask_raster: Optional[List[List[int]]] = None,
    height: int = 0,
    width: int = 0,
) -> Sentinel2MaskSet:
    """
    Derive 7 mask layers from SCL raster.

    SCL semantics:
      4 (vegetation), 5 (bare soil) → valid crop inference
      6 (water) → valid surface, NOT crop inference
      7 (low cloud prob) → marginal (sigma × 1.3)
      10 (thin cirrus) → marginal (sigma × 1.5)
      8, 9 (medium/high cloud) → cloud
      2, 3 (shadow) → shadow
      11 (snow/ice) → snow
      0, 1 → invalid
    """
    if not scl_raster:
        return Sentinel2MaskSet()

    h = height or len(scl_raster)
    w = width or (len(scl_raster[0]) if scl_raster else 0)

    valid_for_index = [[0] * w for _ in range(h)]
    valid_for_crop = [[0] * w for _ in range(h)]
    cloud_like = [[0] * w for _ in range(h)]
    shadow_like = [[0] * w for _ in range(h)]
    marginal = [[0] * w for _ in range(h)]
    water = [[0] * w for _ in range(h)]
    snow = [[0] * w for _ in range(h)]
    sigma_inf = [[1.0] * w for _ in range(h)]

    for r in range(h):
        for c in range(w):
            scl_val = scl_raster[r][c] if r < len(scl_raster) and c < len(scl_raster[r]) else None
            if scl_val is None:
                continue

            scl = int(scl_val)

            # Check dataMask if provided
            if datamask_raster and r < len(datamask_raster) and c < len(datamask_raster[r]):
                if datamask_raster[r][c] == 0:
                    continue  # No data according to dataMask

            if scl in (SCL_VEGETATION, SCL_BARE_SOIL):
                valid_for_index[r][c] = 1
                valid_for_crop[r][c] = 1
            elif scl == SCL_WATER:
                valid_for_index[r][c] = 1
                water[r][c] = 1
                # Water is valid surface but not crop
            elif scl == SCL_CLOUD_LOW_PROB:
                valid_for_index[r][c] = 1
                marginal[r][c] = 1
                sigma_inf[r][c] = 1.3
            elif scl == SCL_THIN_CIRRUS:
                marginal[r][c] = 1
                sigma_inf[r][c] = 1.5
                # Cirrus is more uncertain — still marginal for index
                valid_for_index[r][c] = 1
            elif scl in (SCL_CLOUD_MEDIUM_PROB, SCL_CLOUD_HIGH_PROB):
                cloud_like[r][c] = 1
            elif scl in (SCL_DARK_SHADOW, SCL_CLOUD_SHADOW):
                shadow_like[r][c] = 1
            elif scl == SCL_SNOW_ICE:
                snow[r][c] = 1
            # SCL 0 (no data), 1 (saturated) → all masks stay 0

    return Sentinel2MaskSet(
        valid_for_index=valid_for_index,
        valid_for_crop_inference=valid_for_crop,
        cloud_like=cloud_like,
        shadow_like=shadow_like,
        marginal=marginal,
        water=water,
        snow=snow,
        sigma_inflation=sigma_inf,
    )
