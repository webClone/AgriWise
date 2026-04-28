"""
Layer 1 Spatial Alignment.

Preserves spatial scopes (point, zone, edge, raster, plot, farm).
Builds the SpatialIndex for the context package.

Rules:
- Point evidence stays point unless representativeness explicitly permits promotion
- Zone evidence stays zone-specific
- Edge evidence stays edge (never collapsed to plot)
- Raster refs are preserved (never collapsed to plot summary)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .schemas import (
    EvidenceItem,
    EdgeRegionRef,
    IrrigationBlockRef,
    PointRef,
    RasterRef,
    SpatialIndex,
    ZoneRef,
    SPATIAL_SCOPES,
)


def build_spatial_index(
    evidence: List[EvidenceItem], plot_id: str
) -> SpatialIndex:
    """Build a SpatialIndex from all evidence items."""
    zones: Dict[str, ZoneRef] = {}
    points: Dict[str, PointRef] = {}
    edges: Dict[str, EdgeRegionRef] = {}
    blocks: Dict[str, IrrigationBlockRef] = {}
    rasters: Dict[str, RasterRef] = {}

    for e in evidence:
        if e.spatial_scope == "zone" and e.scope_id:
            if e.scope_id not in zones:
                zones[e.scope_id] = ZoneRef(zone_id=e.scope_id)

        elif e.spatial_scope == "point" and e.scope_id:
            if e.scope_id not in points:
                points[e.scope_id] = PointRef(
                    point_id=e.scope_id,
                    device_id=e.source_id if e.source_family == "sensor" else None,
                )

        elif e.spatial_scope == "edge" and e.scope_id:
            if e.scope_id not in edges:
                edges[e.scope_id] = EdgeRegionRef(edge_id=e.scope_id)

        elif e.spatial_scope == "irrigation_block" and e.scope_id:
            if e.scope_id not in blocks:
                blocks[e.scope_id] = IrrigationBlockRef(block_id=e.scope_id)

        elif e.spatial_scope == "raster":
            raster_id = e.scope_id or e.evidence_id
            if raster_id not in rasters:
                rasters[raster_id] = RasterRef(
                    raster_id=raster_id,
                    variable=e.variable,
                )

    return SpatialIndex(
        plot_id=plot_id,
        zones=list(zones.values()),
        points=list(points.values()),
        edge_regions=list(edges.values()),
        irrigation_blocks=list(blocks.values()),
        raster_refs=list(rasters.values()),
    )


def validate_scope_preservation(evidence: List[EvidenceItem]) -> List[str]:
    """Verify that no evidence has an invalid scope. Returns violations."""
    violations: List[str] = []
    for e in evidence:
        if e.spatial_scope not in SPATIAL_SCOPES:
            violations.append(
                f"Evidence {e.evidence_id} has invalid scope: {e.spatial_scope}"
            )
    return violations
