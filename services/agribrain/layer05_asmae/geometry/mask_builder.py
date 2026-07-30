"""
ASMAE Mask Builder.

Constructs quality masks for scenes from various sources:
  - SCL (Scene Classification Layer) for S2
  - Cloud probability masks
  - SAR noise masks
  - Valid pixel masks
  - Snow/ice masks
  - Plot boundary masks

All masks are boolean (True = valid pixel, False = masked).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── SCL Class Codes (Sentinel-2 Scene Classification) ────────────────────────

SCL_NO_DATA = 0
SCL_SATURATED = 1
SCL_DARK_AREA = 2
SCL_CLOUD_SHADOW = 3
SCL_VEGETATION = 4
SCL_BARE_SOIL = 5
SCL_WATER = 6
SCL_CLOUD_LOW = 7
SCL_CLOUD_MEDIUM = 8
SCL_CLOUD_HIGH = 9
SCL_THIN_CIRRUS = 10
SCL_SNOW_ICE = 11

# Valid SCL classes for optical analysis
VALID_SCL_CLASSES = frozenset({
    SCL_VEGETATION,
    SCL_BARE_SOIL,
})

# No marginal SCL class is assimilated. Water, dark-area/shadow candidates and
# thin cirrus may be useful to a specialised classifier, but they are not valid
# support for vegetation reflectance observations.
MARGINAL_SCL_CLASSES = frozenset()

# Always excluded
EXCLUDED_SCL_CLASSES = frozenset({
    SCL_NO_DATA,
    SCL_SATURATED,
    SCL_DARK_AREA,
    SCL_CLOUD_SHADOW,
    SCL_CLOUD_LOW,
    SCL_CLOUD_MEDIUM,
    SCL_CLOUD_HIGH,
    SCL_THIN_CIRRUS,
    SCL_SNOW_ICE,
    SCL_WATER,
})


@dataclass
class MaskSet:
    """Set of boolean masks for a scene.

    Convention: True = VALID pixel, False = MASKED pixel.
    """
    scene_id: str
    height: int
    width: int

    # Individual mask channels
    cloud_mask: Optional[List[List[bool]]] = None
    shadow_mask: Optional[List[List[bool]]] = None
    nodata_mask: Optional[List[List[bool]]] = None
    snow_mask: Optional[List[List[bool]]] = None
    water_mask: Optional[List[List[bool]]] = None
    polygon_mask: Optional[List[List[bool]]] = None
    quality_mask: Optional[List[List[bool]]] = None

    # Combined mask (intersection of all individual masks)
    combined_mask: Optional[List[List[bool]]] = None

    # Statistics
    valid_pixel_count: int = 0
    total_pixel_count: int = 0
    valid_fraction: float = 0.0

    def compute_combined(self) -> None:
        """Compute combined mask as intersection of all available masks."""
        if self.height == 0 or self.width == 0:
            self.combined_mask = []
            return

        # Start with all-valid
        combined = [[True] * self.width for _ in range(self.height)]

        # Intersect all available masks
        for mask in [
            self.cloud_mask,
            self.shadow_mask,
            self.nodata_mask,
            self.snow_mask,
            self.polygon_mask,
            self.quality_mask,
        ]:
            if mask is None:
                continue
            for r in range(min(self.height, len(mask))):
                for c in range(min(self.width, len(mask[r]))):
                    if not mask[r][c]:
                        combined[r][c] = False

        self.combined_mask = combined

        # Compute statistics
        self.total_pixel_count = self.height * self.width
        self.valid_pixel_count = sum(
            1 for row in combined for val in row if val
        )
        self.valid_fraction = (
            self.valid_pixel_count / self.total_pixel_count
            if self.total_pixel_count > 0 else 0.0
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "height": self.height,
            "width": self.width,
            "valid_pixel_count": self.valid_pixel_count,
            "total_pixel_count": self.total_pixel_count,
            "valid_fraction": round(self.valid_fraction, 4),
            "masks_available": [
                name for name, mask in [
                    ("cloud", self.cloud_mask),
                    ("shadow", self.shadow_mask),
                    ("nodata", self.nodata_mask),
                    ("snow", self.snow_mask),
                    ("water", self.water_mask),
                    ("polygon", self.polygon_mask),
                    ("quality", self.quality_mask),
                ] if mask is not None
            ],
        }


# ── Mask Construction Functions ──────────────────────────────────────────────

def build_cloud_mask_from_scl(
    scl_grid: List[List[int]],
) -> List[List[bool]]:
    """Build cloud mask from SCL classification grid.

    True = CLEAR pixel, False = CLOUDY pixel.
    """
    return [
        [
            scl_val in VALID_SCL_CLASSES or scl_val in MARGINAL_SCL_CLASSES
            for scl_val in row
        ]
        for row in scl_grid
    ]


def build_cloud_mask_from_probability(
    probability_grid: List[List[float]],
    threshold: float = 0.40,
) -> List[List[bool]]:
    """Build cloud mask from cloud probability grid.

    True = CLEAR pixel (probability < threshold).
    """
    return [
        [val < threshold for val in row]
        for row in probability_grid
    ]


def build_nodata_mask(
    band_grid: List[List[float]],
    nodata_value: float = 0.0,
) -> List[List[bool]]:
    """Build nodata mask from a band grid.

    True = HAS DATA, False = NODATA.
    """
    return [
        [
            val is not None and val != nodata_value and val == val  # NaN check
            for val in row
        ]
        for row in band_grid
    ]


def build_polygon_mask(
    height: int,
    width: int,
    polygon_pixels: Optional[List[List[int]]] = None,
) -> List[List[bool]]:
    """Build polygon boundary mask.

    If polygon_pixels is provided, only those pixels are valid.
    If None, all pixels are valid (no polygon clipping).
    """
    if polygon_pixels is None:
        return [[True] * width for _ in range(height)]

    mask = [[False] * width for _ in range(height)]
    for r in range(min(height, len(polygon_pixels))):
        for c in range(min(width, len(polygon_pixels[r]))):
            if polygon_pixels[r][c] == 1:
                mask[r][c] = True
    return mask


def build_mask_set(
    scene_id: str,
    height: int,
    width: int,
    cloud_cover: Optional[float] = None,
    scl_grid: Optional[List[List[int]]] = None,
    cloud_prob_grid: Optional[List[List[float]]] = None,
    reference_band: Optional[List[List[float]]] = None,
    polygon_pixels: Optional[List[List[int]]] = None,
    usable: bool = True,
) -> MaskSet:
    """Build a complete MaskSet from available inputs.

    Constructs individual masks from whatever data is available,
    then computes the combined mask.
    """
    masks = MaskSet(scene_id=scene_id, height=height, width=width)

    if not usable:
        # Entire scene marked unusable → all masked
        masks.combined_mask = [[False] * width for _ in range(height)]
        masks.valid_pixel_count = 0
        masks.total_pixel_count = height * width
        masks.valid_fraction = 0.0
        return masks

    # Cloud mask from SCL (preferred) or probability
    if scl_grid is not None and len(scl_grid) > 0:
        masks.cloud_mask = build_cloud_mask_from_scl(scl_grid)
    elif cloud_prob_grid is not None and len(cloud_prob_grid) > 0:
        masks.cloud_mask = build_cloud_mask_from_probability(cloud_prob_grid)
    elif cloud_cover is not None:
        # Synthetic uniform cloud mask
        is_clear = float(cloud_cover) < 0.80
        if cloud_cover > 1.0:
            is_clear = float(cloud_cover) / 100.0 < 0.80
        masks.cloud_mask = [[is_clear] * width for _ in range(height)]

    # Nodata mask from reference band
    if reference_band is not None and len(reference_band) > 0:
        masks.nodata_mask = build_nodata_mask(reference_band)

    # Polygon mask
    masks.polygon_mask = build_polygon_mask(height, width, polygon_pixels)

    # Compute combined
    masks.compute_combined()

    return masks
