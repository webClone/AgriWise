"""
FAO/HWSD Fallback Mapper.

Maps FAO classifications to AgriBrain risk flags.
Provides numeric fallback ONLY when SoilGrids is missing/UNUSABLE.
Never overrides good SoilGrids numeric properties.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from layer0.environment.fao.schemas import FAOSoilContext
from layer0.environment.soilgrids.schemas import SoilGridsQualityClass


# FAO texture to approximate numeric properties (coarse fallback)
FAO_TEXTURE_FALLBACK = {
    "coarse": {"clay_pct": 10, "sand_pct": 70, "silt_pct": 20, "whc_mm_per_m": 80},
    "medium": {"clay_pct": 25, "sand_pct": 40, "silt_pct": 35, "whc_mm_per_m": 150},
    "fine": {"clay_pct": 50, "sand_pct": 20, "silt_pct": 30, "whc_mm_per_m": 180},
    "organic": {"clay_pct": 20, "sand_pct": 20, "silt_pct": 40, "whc_mm_per_m": 200},
}


def should_use_fao_fallback(soilgrids_quality: Optional[str]) -> bool:
    """Determine if FAO numeric fallback should be used.

    Only used when SoilGrids is missing or UNUSABLE.
    """
    if soilgrids_quality is None:
        return True
    return soilgrids_quality == SoilGridsQualityClass.UNUSABLE.value


def get_fao_numeric_fallback(
    fao_context: FAOSoilContext,
) -> Dict[str, Any]:
    """Get coarse numeric fallback from FAO texture classification.

    Returns empty dict if no usable FAO texture data.
    """
    texture = fao_context.topsoil_texture.lower()
    fallback = FAO_TEXTURE_FALLBACK.get(texture, {})

    if not fallback:
        return {}

    return {
        **fallback,
        "source": "fao_fallback",
        "resolution_m": fao_context.resolution_m,
        "confidence": 0.4,  # Coarse fallback = low confidence
    }


def map_fao_risk_flags(fao_context: FAOSoilContext) -> Dict[str, Any]:
    """Map FAO classifications to AgriBrain risk flags.

    Always available regardless of SoilGrids quality.
    """
    flags: Dict[str, Any] = {}

    # Salinity
    if fao_context.salinity_risk in ("moderate", "high"):
        flags["salinity_warning"] = True
        flags["salinity_level"] = fao_context.salinity_risk

    # Sodicity
    if fao_context.sodicity_risk in ("moderate", "high"):
        flags["sodicity_warning"] = True

    # Drainage limitation
    if fao_context.drainage_limitation == "severe":
        flags["drainage_warning"] = True
        flags["waterlogging_risk"] = True

    # Lime/calcareous
    if fao_context.calcareous_lime_risk in ("moderate", "high"):
        flags["calcareous_warning"] = True

    # Gypsum
    if fao_context.gypsum_risk in ("moderate", "high"):
        flags["gypsum_warning"] = True

    # Depth
    if fao_context.soil_depth_class == "shallow":
        flags["shallow_soil_warning"] = True

    # Agro-ecological
    flags["agro_ecological_flags"] = fao_context.agro_ecological_flags

    return flags
