"""
Cross-source Validation Rules.

Produces conflict/consistency evidence from geo context sources.
Does NOT produce state mutations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.geo_context.dem.schemas import DEMContext
from layer0.geo_context.landcover.schemas import LandCoverContext
from layer0.geo_context.wapor.schemas import WaPORContext


def run_validation_rules(
    dem: Optional[DEMContext] = None,
    landcover: Optional[LandCoverContext] = None,
    wapor: Optional[WaPORContext] = None,
) -> List[Dict[str, Any]]:
    """Run all cross-source validation rules.

    Returns list of evidence dicts, each with:
        rule, status (consistent|conflict|inconclusive), details, sources
    """
    evidence: List[Dict[str, Any]] = []

    # Rule 1: LANDCOVER_vs_DECLARED_PLOT
    if landcover is not None and landcover.worldcover is not None:
        wc = landcover.worldcover
        status = "consistent" if wc.cropland_fraction > 0.5 else "conflict"
        evidence.append({
            "rule": "LANDCOVER_vs_DECLARED_PLOT",
            "status": status,
            "details": f"cropland_fraction={wc.cropland_fraction:.2f}",
            "sources": ["WorldCover"],
        })

    # Rule 2: DEM_SLOPE_vs_SOIL_MOISTURE_SENSOR_PLACEMENT
    if dem is not None and dem.slope_mean is not None:
        status = "consistent" if dem.slope_mean < 10 else "conflict"
        evidence.append({
            "rule": "DEM_SLOPE_vs_SOIL_MOISTURE_SENSOR_PLACEMENT",
            "status": status,
            "details": f"slope_mean={dem.slope_mean:.1f}°",
            "sources": ["DEM"],
        })

    # Rule 3: DEM_LOWSPOT_vs_SAR_WETNESS
    if dem is not None:
        status = "consistent" if dem.low_spot_fraction < 0.3 else "conflict"
        evidence.append({
            "rule": "DEM_LOWSPOT_vs_SAR_WETNESS",
            "status": status,
            "details": f"low_spot_fraction={dem.low_spot_fraction:.2f}",
            "sources": ["DEM"],
        })

    # Rule 4: WAPOR_ET_vs_OPEN_METEO_ET0
    if wapor is not None and wapor.wapor_available and wapor.et_ratio is not None:
        status = "consistent" if 0.5 < wapor.et_ratio < 1.2 else "conflict"
        evidence.append({
            "rule": "WAPOR_ET_vs_OPEN_METEO_ET0",
            "status": status,
            "details": f"et_ratio={wapor.et_ratio:.2f}",
            "sources": ["WaPOR"],
        })

    # Rule 5: WAPOR_BIOMASS_vs_SENTINEL2_VIGOR
    if wapor is not None and wapor.wapor_available and wapor.biomass_trend is not None:
        evidence.append({
            "rule": "WAPOR_BIOMASS_vs_SENTINEL2_VIGOR",
            "status": "inconclusive",  # needs S2 data to compare
            "details": f"biomass_trend={wapor.biomass_trend}",
            "sources": ["WaPOR"],
        })

    # Rule 6: LANDCOVER_vs_SENTINEL2_EDGE_NDVI
    if landcover is not None and landcover.contamination is not None:
        c = landcover.contamination
        if c.tree_edge_contamination_score > 0.3:
            evidence.append({
                "rule": "LANDCOVER_vs_SENTINEL2_EDGE_NDVI",
                "status": "conflict",
                "details": f"tree_edge_contamination={c.tree_edge_contamination_score:.2f}",
                "sources": ["WorldCover"],
            })

    # Rule 7: WAPOR_WATER_PRODUCTIVITY_vs_IRRIGATION_SENSOR
    if wapor is not None and wapor.wapor_available and wapor.water_productivity_score is not None:
        evidence.append({
            "rule": "WAPOR_WATER_PRODUCTIVITY_vs_IRRIGATION_SENSOR",
            "status": "inconclusive",  # needs sensor data
            "details": f"water_productivity={wapor.water_productivity_score}",
            "sources": ["WaPOR"],
        })

    return evidence
