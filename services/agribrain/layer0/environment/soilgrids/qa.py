"""
SoilGrids QA.

Evaluates profile completeness, texture consistency, uncertainty, and water
property availability. Produces SoilGridsQAResult.
"""

from __future__ import annotations

from typing import List

from layer0.environment.soilgrids.schemas import (
    SOILGRIDS_CORE_PROPERTIES,
    SOILGRIDS_DEPTH_LABELS,
    SoilGridsProfile,
    SoilGridsQAResult,
    SoilGridsQualityClass,
)

# Texture tolerance: clay + silt + sand should be ~100% (±5%)
TEXTURE_SUM_TOLERANCE = 5.0
UNCERTAINTY_RATIO_THRESHOLD = 0.5  # (Q95-Q05)/mean


def evaluate_soilgrids_qa(
    profile: SoilGridsProfile,
    provider_status: str = "available",
) -> SoilGridsQAResult:
    """Evaluate SoilGrids profile quality."""
    flags: List[str] = []
    reason_parts: List[str] = []

    # No profile at all
    if not profile.depth_layers:
        return SoilGridsQAResult(
            quality_class=SoilGridsQualityClass.UNUSABLE,
            provider_status=provider_status,
            flags=["NO_PROFILE"],
            reason="No depth layers present",
        )

    # Depth completeness
    depths_present = sum(
        1 for d in SOILGRIDS_DEPTH_LABELS if d in profile.depth_layers
    )
    depth_completeness = depths_present / len(SOILGRIDS_DEPTH_LABELS)

    # Property completeness (averaged across present depths)
    total_props = 0
    total_possible = 0
    for depth_label, layer in profile.depth_layers.items():
        for prop_id in SOILGRIDS_CORE_PROPERTIES:
            total_possible += 1
            if prop_id in layer.properties and layer.properties[prop_id].mean is not None:
                total_props += 1
    property_completeness = total_props / max(total_possible, 1)

    has_all = property_completeness >= 0.95

    # Texture sum consistency (check each depth)
    texture_consistent = True
    for depth_label, layer in profile.depth_layers.items():
        clay = layer.get("clay")
        silt = layer.get("silt")
        sand = layer.get("sand")
        if clay is not None and silt is not None and sand is not None:
            texture_sum = clay + silt + sand
            if abs(texture_sum - 100.0) > TEXTURE_SUM_TOLERANCE:
                texture_consistent = False
                flags.append(f"TEXTURE_SUM_INVALID_{depth_label}")

            # Impossible values
            if clay < 0 or silt < 0 or sand < 0:
                return SoilGridsQAResult(
                    quality_class=SoilGridsQualityClass.UNUSABLE,
                    provider_status=provider_status,
                    flags=["IMPOSSIBLE_TEXTURE_VALUES"],
                    reason=f"Negative texture fraction at {depth_label}",
                )

    # Water property availability
    water_available = False
    for depth_label, layer in profile.depth_layers.items():
        wv003 = layer.get("wv003")
        wv1500 = layer.get("wv1500")
        if wv003 is not None and wv1500 is not None:
            water_available = True
            break

    if not water_available:
        flags.append("MISSING_WATER_PROPERTIES")

    # Uncertainty ratio check (across all properties)
    uncertainty_ok = True
    high_uncertainty_count = 0
    for depth_label, layer in profile.depth_layers.items():
        for prop_id, pv in layer.properties.items():
            if pv.mean is not None and pv.q005 is not None and pv.q095 is not None:
                if pv.mean != 0:
                    ratio = (pv.q095 - pv.q005) / abs(pv.mean)
                    if ratio > UNCERTAINTY_RATIO_THRESHOLD:
                        high_uncertainty_count += 1

    if high_uncertainty_count > 5:
        uncertainty_ok = False
        flags.append("HIGH_UNCERTAINTY")

    # Quality classification
    if not texture_consistent:
        quality_class = SoilGridsQualityClass.UNUSABLE
        reason_parts.append("Impossible texture values")
    elif not water_available or not uncertainty_ok:
        quality_class = SoilGridsQualityClass.DEGRADED
        if not water_available:
            reason_parts.append("Missing wv003/wv1500 water properties")
        if not uncertainty_ok:
            reason_parts.append("High uncertainty across multiple properties")
    elif depth_completeness >= 0.8 and has_all:
        quality_class = SoilGridsQualityClass.GOOD
    else:
        quality_class = SoilGridsQualityClass.DEGRADED
        reason_parts.append(f"Incomplete: {depth_completeness:.0%} depths, {property_completeness:.0%} properties")

    return SoilGridsQAResult(
        quality_class=quality_class,
        has_all_required_properties=has_all,
        depth_completeness=round(depth_completeness, 4),
        property_completeness=round(property_completeness, 4),
        texture_sum_consistent=texture_consistent,
        uncertainty_ratio_ok=uncertainty_ok,
        water_property_available=water_available,
        provider_status=provider_status,
        resolution_m=profile.source_resolution_m,
        flags=flags,
        reason="; ".join(reason_parts) if reason_parts else "OK",
    )
