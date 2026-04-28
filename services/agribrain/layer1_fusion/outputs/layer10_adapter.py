"""
Layer 1 → Layer 10 Output Adapter.

Builds the spatial payload for the Layer 10 SIRE interface.
Preserves zone overlays, point sensor markers, edge contamination,
confidence heatmaps, conflict markers, and missing-data overlays.
"""

from __future__ import annotations

from typing import Any, Dict, List

from layer1_fusion.schemas import (
    FusedFeature,
    Layer1ContextPackage,
    SpatialIndex,
)


def build_layer10_payload(pkg: Layer1ContextPackage) -> Dict[str, Any]:
    """Build the Layer 10 spatial intelligence payload."""
    return {
        "plot_id": pkg.plot_id,
        "run_id": pkg.run_id,

        # Spatial index for map rendering
        "spatial_index": _serialize_spatial_index(pkg.spatial_index),

        # Zone overlays
        "zone_overlays": _build_zone_overlays(pkg),

        # Point sensor markers
        "sensor_markers": _build_sensor_markers(pkg),

        # Edge contamination regions
        "edge_regions": [
            {"edge_id": e.edge_id, "contamination_score": e.contamination_score}
            for e in pkg.spatial_index.edge_regions
        ],

        # Confidence heatmap data
        "confidence_data": _build_confidence_data(pkg),

        # Conflict markers for map
        "conflict_markers": [
            {
                "conflict_id": c.conflict_id,
                "type": c.conflict_type,
                "severity": c.severity,
                "spatial_scope": c.spatial_scope,
                "scope_id": c.scope_id,
                "description": c.description,
            }
            for c in pkg.conflicts
        ],

        # Missing-data overlays
        "gap_markers": [
            {
                "gap_type": g.gap_type,
                "severity": g.severity,
                "affected_features": g.affected_features,
            }
            for g in pkg.gaps
        ],

        # Source freshness badges
        "source_freshness": {
            env.source_family: {
                "status": env.source_status,
                "trust_score": env.trust_score,
            }
            for env in pkg.source_health.envelopes
        },

        # Data health summary
        "data_health": {
            "overall": pkg.diagnostics.data_health.overall,
            "status": pkg.diagnostics.data_health.status,
            "confidence_ceiling": pkg.diagnostics.data_health.confidence_ceiling,
        },

        # Raster references (for rendering NDVI/SAR overlays)
        "raster_refs": [
            {
                "raster_id": r.raster_id,
                "variable": r.variable,
                "resolution_m": r.resolution_m,
                "content_hash": r.content_hash,
            }
            for r in pkg.spatial_index.raster_refs
        ],
    }


def _serialize_spatial_index(si: SpatialIndex) -> Dict[str, Any]:
    return {
        "plot_id": si.plot_id,
        "zone_count": len(si.zones),
        "point_count": len(si.points),
        "edge_count": len(si.edge_regions),
        "raster_count": len(si.raster_refs),
    }


def _build_zone_overlays(pkg: Layer1ContextPackage) -> List[Dict[str, Any]]:
    """Build zone-level feature overlays."""
    overlays = []
    for z in pkg.spatial_index.zones:
        zone_features = {}
        for group in [
            pkg.fused_features.water_context,
            pkg.fused_features.vegetation_context,
        ]:
            for ff in group:
                if ff.spatial_scope == "zone" and ff.scope_id == z.zone_id:
                    zone_features[ff.name] = {
                        "value": ff.value,
                        "confidence": ff.confidence,
                    }
        overlays.append({
            "zone_id": z.zone_id,
            "label": z.label,
            "features": zone_features,
        })
    return overlays


def _build_sensor_markers(pkg: Layer1ContextPackage) -> List[Dict[str, Any]]:
    """Build point sensor markers for map."""
    markers = []
    for p in pkg.spatial_index.points:
        point_features = {}
        for group in [
            pkg.fused_features.water_context,
            pkg.fused_features.vegetation_context,
        ]:
            for ff in group:
                if ff.spatial_scope == "point" and ff.scope_id == p.point_id:
                    point_features[ff.name] = {
                        "value": ff.value,
                        "confidence": ff.confidence,
                    }
        markers.append({
            "point_id": p.point_id,
            "device_id": p.device_id,
            "placement": p.placement,
            "features": point_features,
        })
    return markers


def _build_confidence_data(pkg: Layer1ContextPackage) -> Dict[str, Any]:
    """Build confidence data for heatmap rendering."""
    return {
        "plot_level": pkg.state_summary.confidence_ceiling,
        "per_zone": {
            z.zone_id: 0.0  # populated when zone-level confidence is computed
            for z in pkg.spatial_index.zones
        },
    }
