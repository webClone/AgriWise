"""
Land Cover schemas.

ESA WorldCover + Dynamic World + Boundary Contamination.
Includes unknown/unmapped fraction tracking (Revision 5)
and probability validation (Revision 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# ESA WorldCover class mapping (all 11 classes)
# ---------------------------------------------------------------------------

ESA_WORLDCOVER_CLASSES = {
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse",
    80: "permanent_water",
    90: "herbaceous_wetland",
    95: "mangrove",
    100: "moss_lichen",
    110: "snow_ice",
}

# Dynamic World classes
DYNAMIC_WORLD_CLASSES = [
    "water", "trees", "grass", "flooded_vegetation",
    "crops", "shrub_scrub", "built", "bare", "snow_ice",
]

# Confidence cap for Dynamic World (Revision 6)
DYNAMIC_WORLD_MAX_CONFIDENCE = 0.75


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

class LandCoverQualityClass(Enum):
    GOOD = "good"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


# ---------------------------------------------------------------------------
# WorldCover context (Revision 5 — unknown/unmapped fractions)
# ---------------------------------------------------------------------------

@dataclass
class WorldCoverContext:
    """ESA WorldCover classification results for a plot."""
    cropland_fraction: float = 0.0
    tree_cover_fraction: float = 0.0
    grassland_fraction: float = 0.0
    shrubland_fraction: float = 0.0
    builtup_fraction: float = 0.0
    water_fraction: float = 0.0
    bare_sparse_fraction: float = 0.0
    wetland_fraction: float = 0.0

    # Revision 5: unknown/unmapped tracking
    unknown_fraction: float = 0.0
    unmapped_fraction: float = 0.0
    landcover_valid_fraction: float = 1.0

    # Aggregates
    non_ag_fraction: float = 0.0
    landcover_majority_class: str = "unknown"
    landcover_purity_score: float = 0.0
    landcover_confidence: float = 0.0


# ---------------------------------------------------------------------------
# Dynamic World context (Revision 6 — probability validation)
# ---------------------------------------------------------------------------

@dataclass
class DynamicWorldContext:
    """Dynamic World probability-based land cover context."""
    crop_probability_mean: float = 0.0
    tree_probability_mean: float = 0.0
    water_probability_mean: float = 0.0
    built_probability_mean: float = 0.0
    bare_probability_mean: float = 0.0
    flooded_vegetation_probability_mean: float = 0.0

    # QA
    class_entropy: float = 0.0
    dynamic_landcover_confidence: float = 0.0  # capped at 0.75 (Rev 6)
    recent_non_crop_alert: bool = False

    # Metadata
    probability_sum_valid: bool = True
    acquisition_date: Optional[str] = None


# ---------------------------------------------------------------------------
# Boundary contamination (Revision 7 — interior/edge/neighbor masks)
# ---------------------------------------------------------------------------

@dataclass
class BoundaryContamination:
    """Boundary contamination assessment from land cover analysis."""
    # Interior analysis
    interior_cropland_fraction: float = 0.0

    # Edge analysis
    edge_tree_fraction: float = 0.0
    edge_water_fraction: float = 0.0
    edge_builtup_fraction: float = 0.0

    # Neighbor buffer analysis
    neighbor_tree_fraction: float = 0.0
    neighbor_water_fraction: float = 0.0
    neighbor_builtup_fraction: float = 0.0
    neighbor_cropland_continuity_score: float = 0.0

    # Contamination scores [0, 1]
    tree_edge_contamination_score: float = 0.0
    water_edge_contamination_score: float = 0.0
    builtup_edge_contamination_score: float = 0.0
    boundary_mismatch_score: float = 0.0

    # Flags
    flags: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Unified land-cover context
# ---------------------------------------------------------------------------

@dataclass
class LandCoverContext:
    """Unified land-cover context combining all sources."""
    worldcover: Optional[WorldCoverContext] = None
    dynamic_world: Optional[DynamicWorldContext] = None
    contamination: Optional[BoundaryContamination] = None

    # WorldCover vs Dynamic World comparison
    worldcover_dynamic_world_agreement: Optional[float] = None
    disagrees: bool = False


# ---------------------------------------------------------------------------
# QA
# ---------------------------------------------------------------------------

@dataclass
class LandCoverQAResult:
    """Quality assessment for land cover inputs."""
    quality_class: LandCoverQualityClass = LandCoverQualityClass.GOOD
    worldcover_available: bool = False
    dynamic_world_available: bool = False
    valid_fraction: float = 0.0
    unknown_fraction: float = 0.0
    flags: List[str] = field(default_factory=list)
