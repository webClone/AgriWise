"""
FAO / HWSD V1 Schemas.

HWSD v2.0 uses 7 depth layers that do NOT align to SoilGrids 6 depths.
FAO provides classification/context, not numeric overrides of good SoilGrids.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Literal, Optional


# HWSD v2.0 depth layers (different from SoilGrids)
FAO_HWSD_DEPTH_LAYERS = [
    "0-20cm", "20-40cm", "40-60cm", "60-80cm",
    "80-100cm", "100-150cm", "150-200cm",
]


class FAOQualityClass(Enum):
    """FAO context quality."""
    GOOD = "good"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


@dataclass
class FAOSoilContext:
    """FAO/HWSD coarse soil and ecological context."""
    # Classification
    soil_mapping_unit: str = ""
    dominant_soil_type: str = ""     # WRB/FAO
    secondary_soil_type: str = ""
    ipcc_soil_group: str = ""

    # Texture
    topsoil_texture: str = ""        # coarse / medium / fine / organic
    subsoil_texture: str = ""
    soil_depth_class: str = ""       # shallow / moderate / deep

    # Risk flags
    salinity_risk: str = "unknown"   # none / low / moderate / high
    sodicity_risk: str = "unknown"
    calcareous_lime_risk: str = "unknown"
    gypsum_risk: str = "unknown"
    drainage_limitation: str = "unknown"  # none / moderate / severe

    # Ecological
    agro_ecological_flags: List[str] = field(default_factory=list)

    # Depth schema
    fao_depth_schema: str = "hwsd_v2_7_layers"
    depth_mapping_method: str = "none"  # none / interpolated / nearest
    depth_mapping_confidence: float = 0.0

    # Provenance
    resolution_m: float = 1000.0
    dataset_name: str = "HWSD"
    dataset_version: str = "v2.0"
    label: Literal["soil_context"] = "soil_context"
    access_method: Literal[
        "mocked_fixture", "local_database", "api"
    ] = "mocked_fixture"


@dataclass
class FAOQAResult:
    """FAO context quality assessment."""
    quality_class: FAOQualityClass = FAOQualityClass.GOOD

    spatial_resolution_warning: bool = True  # Always true — FAO is coarse
    soil_unit_confidence: float = 0.0
    attribute_completeness: float = 0.0
    fallback_only: bool = False  # True if used only because SoilGrids failed

    flags: List[str] = field(default_factory=list)
    reason: str = ""
