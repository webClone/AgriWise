"""
Environmental Fusion Engine.

Merges soil priors + FAO context + weather into unified context.
Produces ProcessParameters from soil data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.schemas import ProcessParameters
from layer0.environment.soilgrids.schemas import (
    SoilGridsDerivedHydraulics,
    SoilGridsProfile,
    SoilGridsQualityClass,
)
from layer0.environment.soilgrids.qa import SoilGridsQAResult
from layer0.environment.fao.schemas import FAOSoilContext
from layer0.environment.fao.fallback_mapper import (
    get_fao_numeric_fallback,
    should_use_fao_fallback,
)


def build_process_parameters(
    soilgrids_profile: Optional[SoilGridsProfile],
    soilgrids_qa: Optional[SoilGridsQAResult],
    derived_hydraulics: Optional[SoilGridsDerivedHydraulics],
    fao_context: Optional[FAOSoilContext],
) -> ProcessParameters:
    """Build process model parameters from soil priors.

    Uses SoilGrids if available and quality is GOOD/DEGRADED.
    Falls back to FAO if SoilGrids is UNUSABLE or missing.
    Falls back to defaults if nothing available.
    """
    sg_quality = soilgrids_qa.quality_class.value if soilgrids_qa else None
    use_fao = should_use_fao_fallback(sg_quality)

    if not use_fao and derived_hydraulics is not None:
        return _params_from_soilgrids(derived_hydraulics)

    if use_fao and fao_context is not None:
        return _params_from_fao(fao_context)

    return ProcessParameters(soil_source="default")


def _params_from_soilgrids(
    hydraulics: SoilGridsDerivedHydraulics,
) -> ProcessParameters:
    """Derive process parameters from SoilGrids hydraulics."""
    # Convert root-zone AWC to WHC per meter
    whc = None
    if hydraulics.root_zone_awc_mm_0_60 is not None:
        # AWC over 0-60cm → mm per meter equivalent
        whc = hydraulics.root_zone_awc_mm_0_60 / 0.6

    # Field capacity from wv003 (topsoil average)
    fc = None
    wp = None
    if hydraulics.awc_volumetric_proxy_by_depth:
        # Use first available depth layer values
        first_depth = next(iter(hydraulics.awc_volumetric_proxy_by_depth.keys()), None)
        if first_depth:
            awc_vol = hydraulics.awc_volumetric_proxy_by_depth[first_depth]
            # Approximate FC and WP from AWC
            # Typical: FC ≈ WP + AWC. Use typical WP range.
            wp = 10.0  # Approximate wilting point vol%
            fc = wp + awc_vol

    return ProcessParameters(
        field_capacity_vol_pct=round(fc, 2) if fc is not None else None,
        wilting_point_vol_pct=round(wp, 2) if wp is not None else None,
        whc_mm_per_m=round(whc, 2) if whc is not None else None,
        root_zone_awc_mm_0_30=hydraulics.root_zone_awc_mm_0_30,
        root_zone_awc_mm_0_60=hydraulics.root_zone_awc_mm_0_60,
        root_zone_awc_mm_0_100=hydraulics.root_zone_awc_mm_0_100,
        drainage_coefficient=_drainage_to_coefficient(hydraulics.drainage_risk),
        soil_source="soilgrids",
        coarse_fragment_correction_applied=hydraulics.coarse_fragment_correction_applied,
    )


def _params_from_fao(fao_context: FAOSoilContext) -> ProcessParameters:
    """Derive process parameters from FAO fallback."""
    fallback = get_fao_numeric_fallback(fao_context)
    if not fallback:
        return ProcessParameters(soil_source="default")

    return ProcessParameters(
        whc_mm_per_m=fallback.get("whc_mm_per_m"),
        soil_source="fao_fallback",
    )


def _drainage_to_coefficient(risk: str) -> Optional[float]:
    """Convert drainage risk class to a coefficient."""
    mapping = {"low": 0.3, "medium": 0.5, "high": 0.8}
    return mapping.get(risk)
