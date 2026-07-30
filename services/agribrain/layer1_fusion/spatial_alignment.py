"""
Layer 1 Spatial Alignment.

Preserves spatial scopes (point, zone, edge, raster, plot, farm).
Builds the SpatialIndex for the context package.

Rules:
- Point evidence stays point unless representativeness explicitly permits promotion
- Zone evidence stays zone-specific
- Edge evidence stays edge (never collapsed to plot)
- Raster refs are preserved (never collapsed to plot summary)
- When Layer 0 state package is available, enriches zones with WSR labels,
  area fractions, and edge contamination scores
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
    raster_ref_has_geographic_authority,
)


def build_spatial_index(
    evidence: List[EvidenceItem],
    plot_id: str,
    layer0_state: Any = None,
) -> SpatialIndex:
    """Build a SpatialIndex from all evidence items.

    Optionally enriches zones and edges from Layer 0 state package
    (WSR zone labels, area fractions, edge contamination).
    """
    zones: Dict[str, ZoneRef] = {}
    points: Dict[str, PointRef] = {}
    edges: Dict[str, EdgeRegionRef] = {}
    blocks: Dict[str, IrrigationBlockRef] = {}
    rasters: Dict[str, RasterRef] = {}

    # Phase 1: Index from evidence items
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
            # Evidence identity and array dimensions cannot manufacture a map.
            # Concrete RasterRefs are admitted below from Layer 0, or by the
            # dedicated raster ingestion path after this index is built.
            continue

    # Phase 2: Enrich from Layer 0 state package (WSR zones, edges)
    if layer0_state is not None:
        _enrich_from_layer0(zones, edges, rasters, layer0_state)

    return SpatialIndex(
        plot_id=plot_id,
        zones=list(zones.values()),
        points=list(points.values()),
        edge_regions=list(edges.values()),
        irrigation_blocks=list(blocks.values()),
        raster_refs=list(rasters.values()),
    )


def _enrich_from_layer0(
    zones: Dict[str, ZoneRef],
    edges: Dict[str, EdgeRegionRef],
    rasters: Dict[str, RasterRef],
    l0_state: Any,
) -> None:
    """Extract WSR zone metadata and edge contamination from L0 state.

    Supports L0 packages that have:
    - zone_summaries: list of zone dicts with zone_id, label, area_fraction, geometry_ref
    - edge_contamination: list of edge dicts with edge_id, contamination_score
    - raster_refs: list of raster dicts with raster_id, variable, resolution_m, content_hash
    """
    # Zone enrichment
    zone_summaries = getattr(l0_state, "zone_summaries", None)
    if zone_summaries is None and isinstance(l0_state, dict):
        zone_summaries = l0_state.get("zone_summaries", [])

    if zone_summaries:
        for zs in zone_summaries:
            zid = _attr_or_key(zs, "zone_id", "")
            if not zid:
                continue
            label = _attr_or_key(zs, "label", "")
            area_frac = _attr_or_key(zs, "area_fraction", 0.0)
            geom_ref = _attr_or_key(zs, "geometry_ref", None)

            if zid in zones:
                # Enrich existing zone
                zones[zid].label = label or zones[zid].label
                zones[zid].area_fraction = area_frac or zones[zid].area_fraction
                zones[zid].geometry_ref = geom_ref or zones[zid].geometry_ref
            else:
                zones[zid] = ZoneRef(
                    zone_id=zid, label=label,
                    area_fraction=area_frac, geometry_ref=geom_ref,
                )

    # Edge contamination enrichment
    edge_contam = getattr(l0_state, "edge_contamination", None)
    if edge_contam is None and isinstance(l0_state, dict):
        edge_contam = l0_state.get("edge_contamination", [])

    if edge_contam:
        for ec in edge_contam:
            eid = _attr_or_key(ec, "edge_id", "")
            if not eid:
                continue
            score = _attr_or_key(ec, "contamination_score", 0.0)
            geom_ref = _attr_or_key(ec, "geometry_ref", None)

            if eid in edges:
                edges[eid].contamination_score = score
            else:
                edges[eid] = EdgeRegionRef(
                    edge_id=eid,
                    contamination_score=score,
                    geometry_ref=geom_ref,
                )

    # Raster ref enrichment
    l0_raster_refs = getattr(l0_state, "raster_refs", None)
    if l0_raster_refs is None and isinstance(l0_state, dict):
        l0_raster_refs = l0_state.get("raster_refs", [])

    if l0_raster_refs:
        for rr in l0_raster_refs:
            rid = _attr_or_key(rr, "raster_id", "")
            if not rid or rid in rasters:
                continue
            if isinstance(rr, RasterRef):
                if raster_ref_has_geographic_authority(rr):
                    rasters[rid] = rr
                continue

            raw_grid = _attr_or_key(rr, "grid_spec", {}) or {}

            def raster_field(name: str, default: Any = None) -> Any:
                direct = _attr_or_key(rr, name, None)
                if direct is not None:
                    return direct
                return _attr_or_key(raw_grid, name, default)

            candidate = RasterRef(
                raster_id=rid,
                variable=_attr_or_key(rr, "variable", ""),
                resolution_m=raster_field(
                    "resolution_m", raster_field("resolution", None)
                ),
                content_hash=_attr_or_key(rr, "content_hash", None),
                width=raster_field("width", 0),
                height=raster_field("height", 0),
                crs=raster_field("crs", None),
                bounds=raster_field("bounds", None),
                transform=raster_field("transform", raster_field("affine", None)),
                grid=_attr_or_key(rr, "grid", None),
                artifact_ref=_attr_or_key(rr, "artifact_ref", None),
                valid_pixel_count=_attr_or_key(rr, "valid_pixel_count", 0),
                observed_ratio=_attr_or_key(rr, "observed_ratio", 0.0),
                truth_class=_attr_or_key(rr, "truth_class", "unknown"),
                source_reality=_attr_or_key(rr, "source_reality", "unknown"),
                real_provider_product=_attr_or_key(rr, "real_provider_product", False),
                production_usable=_attr_or_key(rr, "production_usable", False),
                grounding_class=_attr_or_key(rr, "grounding_class", None),
                visualization_allowed=_attr_or_key(rr, "visualization_allowed", False),
                experimental_visual_allowed=_attr_or_key(
                    rr, "experimental_visual_allowed", False
                ),
                scientific_surface_allowed=_attr_or_key(
                    rr, "scientific_surface_allowed", False
                ),
                state_update_allowed=_attr_or_key(rr, "state_update_allowed", False),
                observed_spatial_surface=_attr_or_key(
                    rr, "observed_spatial_surface", False
                ),
                diagnostic_only=_attr_or_key(rr, "diagnostic_only", True),
                prescription_driver_allowed=_attr_or_key(
                    rr, "prescription_driver_allowed", False
                ),
                authority_block_reason=_attr_or_key(
                    rr, "authority_block_reason", None
                ),
            )
            if candidate.geographic_grid_valid:
                rasters[rid] = candidate


def _attr_or_key(obj: Any, name: str, default: Any = None) -> Any:
    """Read from attribute or dict key."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def validate_scope_preservation(evidence: List[EvidenceItem]) -> List[str]:
    """Verify that no evidence has an invalid scope. Returns violations."""
    violations: List[str] = []
    for e in evidence:
        if e.spatial_scope not in SPATIAL_SCOPES:
            violations.append(
                f"Evidence {e.evidence_id} has invalid scope: {e.spatial_scope}"
            )
    return violations
