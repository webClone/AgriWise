"""
Sensor Placement Logic.

Combines DEM zones, land-cover contamination, and source confidence
to produce placement recommendations with confidence + scope (Revision 10).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.geo_context.schemas import (
    SensorPlacementGuidance,
    SensorZoneRecommendation,
)
from layer0.geo_context.dem.schemas import DEMContext
from layer0.geo_context.landcover.schemas import BoundaryContamination, LandCoverContext


def compute_sensor_placement(
    dem: Optional[DEMContext] = None,
    landcover: Optional[LandCoverContext] = None,
) -> SensorPlacementGuidance:
    """Compute sensor placement guidance from DEM and land cover.

    Returns guidance with confidence, scope, reason_codes, source_drivers
    for each recommendation (Revision 10).
    """
    recommended: List[SensorZoneRecommendation] = []
    avoid: List[SensorZoneRecommendation] = []
    wet_candidates: List[SensorZoneRecommendation] = []
    dry_candidates: List[SensorZoneRecommendation] = []
    representative: List[SensorZoneRecommendation] = []
    reasoning: List[str] = []

    # Base confidence from DEM quality
    dem_confidence = 1.0
    if dem is not None:
        dem_confidence = dem.qa.placement_confidence_factor

    # --------------- Representative zone ---------------
    rep_confidence = 0.6 * dem_confidence
    rep_reasons: List[str] = []
    rep_drivers: List[str] = []

    if dem is not None:
        rep_reasons.append("MID_SLOPE")
        rep_drivers.append("DEM")

        if dem.slope_mean is not None and dem.slope_mean < 5:
            rep_reasons.append("LOW_SLOPE")
            rep_confidence = min(rep_confidence + 0.1, 1.0)

    if landcover is not None and landcover.contamination is not None:
        contam = landcover.contamination
        if contam.interior_cropland_fraction > 0.8:
            rep_reasons.append("STABLE_CROPLAND")
            rep_drivers.append("WorldCover")
            rep_confidence = min(rep_confidence + 0.1, 1.0)

        if contam.tree_edge_contamination_score < 0.2:
            rep_reasons.append("LOW_EDGE_CONTAMINATION")
            rep_confidence = min(rep_confidence + 0.05, 1.0)

    rep = SensorZoneRecommendation(
        zone_id="representative_mid_slope",
        sensor_type="soil_moisture",
        placement_confidence=round(rep_confidence, 4),
        representativeness_scope="zone" if dem is not None else "point",
        recommended_depths_cm=[15, 45],
        reason_codes=rep_reasons,
        source_drivers=rep_drivers,
        reason="Representative mid-slope zone for soil moisture monitoring",
    )
    recommended.append(rep)
    representative.append(rep)
    reasoning.append("Representative zone placed at mid-slope with low edge contamination")

    # --------------- Wet zone (low-spot candidate) ---------------
    if dem is not None and dem.low_spot_fraction > 0.05:
        wet_conf = 0.5 * dem_confidence
        wet = SensorZoneRecommendation(
            zone_id="wet_lowspot",
            sensor_type="soil_moisture",
            placement_confidence=round(wet_conf, 4),
            representativeness_scope="zone",
            recommended_depths_cm=[15, 45],
            reason_codes=["LOW_SPOT", "DRAINAGE_RISK", "WATERLOGGING_RISK"],
            source_drivers=["DEM"],
            reason="Low-spot zone to capture drainage/waterlogging risk",
        )
        wet_candidates.append(wet)
        reasoning.append("Wet zone at low-spot for waterlogging monitoring")

    # --------------- Dry zone (ridge candidate) ---------------
    if dem is not None and dem.ridge_fraction > 0.05:
        dry_conf = 0.5 * dem_confidence
        dry = SensorZoneRecommendation(
            zone_id="dry_upper_slope",
            sensor_type="soil_moisture",
            placement_confidence=round(dry_conf, 4),
            representativeness_scope="zone",
            recommended_depths_cm=[15, 45],
            reason_codes=["RIDGE", "EARLY_STRESS_DETECTION"],
            source_drivers=["DEM"],
            reason="Upper-slope zone to capture early water stress",
        )
        dry_candidates.append(dry)
        reasoning.append("Dry zone at ridge for early stress detection")

    # --------------- Avoid zones ---------------
    # Avoid tree-edge areas
    if landcover is not None and landcover.contamination is not None:
        contam = landcover.contamination
        if contam.tree_edge_contamination_score > 0.3:
            avoid.append(SensorZoneRecommendation(
                zone_id="tree_edge_avoid",
                sensor_type="soil_moisture",
                placement_confidence=0.0,
                representativeness_scope="point",
                reason_codes=["HIGH_TREE_EDGE_CONTAMINATION"],
                source_drivers=["WorldCover"],
                reason="High tree-edge contamination — sensor not representative",
            ))
            reasoning.append("Avoid tree-edge zone due to contamination")

    # Avoid extreme slope
    if dem is not None and dem.slope_max is not None and dem.slope_max > 20:
        avoid.append(SensorZoneRecommendation(
            zone_id="extreme_slope_avoid",
            sensor_type="soil_moisture",
            placement_confidence=0.0,
            representativeness_scope="point",
            reason_codes=["EXTREME_SLOPE", "RUNOFF_CHANNEL_RISK"],
            source_drivers=["DEM"],
            reason="Extreme slope — runoff channel risk, not representative",
        ))
        reasoning.append("Avoid extreme slope zone due to runoff risk")

    # Avoid water-contaminated edges
    if landcover is not None and landcover.contamination is not None:
        if landcover.contamination.water_edge_contamination_score > 0.3:
            avoid.append(SensorZoneRecommendation(
                zone_id="water_edge_avoid",
                sensor_type="soil_moisture",
                placement_confidence=0.0,
                representativeness_scope="point",
                reason_codes=["WATER_CONTAMINATION"],
                source_drivers=["WorldCover"],
                reason="Water contamination at edge — not representative",
            ))

    return SensorPlacementGuidance(
        recommended_zones=recommended,
        avoid_zones=avoid,
        wet_zone_candidates=wet_candidates,
        dry_zone_candidates=dry_candidates,
        representative_zone_candidates=representative,
        reasoning=reasoning,
    )
