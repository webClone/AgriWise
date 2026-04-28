"""
FAO/HWSD QA.

Always sets spatial_resolution_warning = True because FAO is coarse (~1 km).
"""

from __future__ import annotations

from typing import List

from layer0.environment.fao.schemas import FAOQAResult, FAOQualityClass, FAOSoilContext


def evaluate_fao_qa(
    context: FAOSoilContext,
    provider_status: str = "available",
) -> FAOQAResult:
    """Evaluate FAO/HWSD context quality."""
    flags: List[str] = ["COARSE_RESOLUTION"]  # Always
    reason_parts: List[str] = []

    # No data
    if not context.dominant_soil_type and not context.soil_mapping_unit:
        return FAOQAResult(
            quality_class=FAOQualityClass.UNUSABLE,
            spatial_resolution_warning=True,
            flags=["COARSE_RESOLUTION", "NO_DATA"],
            reason="No FAO soil data available",
        )

    # Attribute completeness
    attrs = [
        context.dominant_soil_type,
        context.topsoil_texture,
        context.subsoil_texture,
        context.soil_depth_class,
        context.salinity_risk,
        context.drainage_limitation,
    ]
    present = sum(1 for a in attrs if a and a != "unknown")
    completeness = present / len(attrs)

    # Soil unit confidence — coarser data → lower confidence
    confidence = 0.6 if completeness > 0.7 else 0.4

    if completeness < 0.5:
        quality_class = FAOQualityClass.DEGRADED
        reason_parts.append(f"Low attribute completeness: {completeness:.0%}")
    else:
        quality_class = FAOQualityClass.GOOD

    return FAOQAResult(
        quality_class=quality_class,
        spatial_resolution_warning=True,
        soil_unit_confidence=round(confidence, 2),
        attribute_completeness=round(completeness, 2),
        flags=flags,
        reason="; ".join(reason_parts) if reason_parts else "OK",
    )
