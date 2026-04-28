"""
Geo Context Fusion.

Combines DEM, LandCover, and WaPOR contexts into:
- PlotValidityAssessment
- SatelliteTrustModifiers

Handles partial provider failure (any source can be None).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.geo_context.schemas import (
    PlotValidityAssessment,
    SatelliteTrustModifiers,
)
from layer0.geo_context.dem.schemas import DEMContext
from layer0.geo_context.landcover.schemas import LandCoverContext
from layer0.geo_context.wapor.schemas import WaPORContext


def fuse_geo_context(
    dem: Optional[DEMContext] = None,
    landcover: Optional[LandCoverContext] = None,
    wapor: Optional[WaPORContext] = None,
) -> tuple:
    """Fuse available geo context sources into assessment outputs.

    Returns (PlotValidityAssessment, SatelliteTrustModifiers).
    """
    validity = _build_plot_validity(dem, landcover, wapor)
    trust = _build_satellite_trust_modifiers(dem, landcover)
    return validity, trust


def _build_plot_validity(
    dem: Optional[DEMContext],
    landcover: Optional[LandCoverContext],
    wapor: Optional[WaPORContext],
) -> PlotValidityAssessment:
    """Build plot validity assessment from available sources."""
    flags: List[str] = []
    cropland_conf = 0.5  # default neutral
    non_ag = 0.0
    boundary_mismatch = 0.0
    water_contam = 0.0
    builtup_contam = 0.0
    tree_edge_contam = 0.0

    if landcover is not None:
        # WorldCover-derived validity
        if landcover.worldcover is not None:
            wc = landcover.worldcover
            cropland_conf = wc.cropland_fraction
            non_ag = wc.non_ag_fraction

            if wc.cropland_fraction < 0.5:
                flags.append("PLOT_NON_AGRICULTURAL_RISK")
            if wc.cropland_fraction < 0.3:
                flags.append("LOW_CROPLAND_CONFIDENCE")

        # Contamination-derived
        if landcover.contamination is not None:
            c = landcover.contamination
            boundary_mismatch = c.boundary_mismatch_score
            water_contam = c.water_edge_contamination_score
            builtup_contam = c.builtup_edge_contamination_score
            tree_edge_contam = c.tree_edge_contamination_score
            flags.extend(c.flags)

        # Dynamic World disagreement
        if landcover.disagrees:
            flags.append("DYNAMIC_WORLD_DISAGREES_WITH_WORLD_COVER")

    # DEM-derived flags
    if dem is not None:
        if dem.runoff_risk_score > 0.7:
            flags.append("HIGH_RUNOFF_RISK")
        if dem.erosion_risk_score > 0.7:
            flags.append("HIGH_EROSION_RISK")

    # Deduplicate flags
    flags = sorted(set(flags))

    return PlotValidityAssessment(
        cropland_confidence=round(cropland_conf, 4),
        non_ag_contamination_score=round(non_ag, 4),
        boundary_mismatch_score=round(boundary_mismatch, 4),
        water_contamination_score=round(water_contam, 4),
        builtup_contamination_score=round(builtup_contam, 4),
        tree_edge_contamination_score=round(tree_edge_contam, 4),
        flags=flags,
    )


def _build_satellite_trust_modifiers(
    dem: Optional[DEMContext],
    landcover: Optional[LandCoverContext],
) -> SatelliteTrustModifiers:
    """Build satellite trust modifiers with explicit scope (Revision 9)."""
    flags: List[str] = []

    # Sentinel-2 boundary risk (edge scope)
    s2_boundary = 0.0
    if landcover is not None and landcover.contamination is not None:
        c = landcover.contamination
        s2_boundary = min(
            c.tree_edge_contamination_score * 0.5 +
            c.boundary_mismatch_score * 0.3 +
            c.water_edge_contamination_score * 0.2,
            1.0,
        )
        if s2_boundary > 0.3:
            flags.append("S2_EDGE_VEGETATION_RISK")

    # Sentinel-1 terrain risk (zone scope)
    s1_terrain = 0.0
    if dem is not None:
        slope_risk = min((dem.slope_max or 0) / 30.0, 1.0)
        s1_terrain = slope_risk * 0.7
        if s1_terrain > 0.3:
            flags.append("S1_TERRAIN_LAYOVER_RISK")

    # Sat RGB landcover risk (plot scope)
    rgb_risk = 0.0
    if landcover is not None and landcover.worldcover is not None:
        rgb_risk = min(landcover.worldcover.non_ag_fraction, 1.0)
        if rgb_risk > 0.3:
            flags.append("RGB_NON_CROP_CONTAMINATION")

    # Dynamic World disagreement (plot scope)
    dw_disagree = 0.0
    if landcover is not None and landcover.disagrees:
        dw_disagree = 0.5
        flags.append("DW_WORLDCOVER_DISAGREEMENT")

    return SatelliteTrustModifiers(
        sentinel2_boundary_risk=round(s2_boundary, 4),
        sentinel1_terrain_risk=round(s1_terrain, 4),
        sat_rgb_landcover_risk=round(rgb_risk, 4),
        dynamic_world_disagreement=round(dw_disagree, 4),
        sentinel2_boundary_risk_scope="edge",
        sentinel1_terrain_risk_scope="zone",
        sat_rgb_landcover_risk_scope="plot",
        dynamic_world_disagreement_scope="plot",
        flags=flags,
    )
