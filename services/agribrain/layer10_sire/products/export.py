"""
Product Export — Raster pack, vector pack, tile manifest
=========================================================

Exports Layer 10 outputs into frontend-consumable formats:
  - RasterPack: all surfaces as serializable grids
  - VectorPack: zones as GeoJSON-like features
  - TileManifest: metadata for map tile rendering
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from services.agribrain.layer10_sire.schema import (
    Layer10Output, SurfaceArtifact, ZoneArtifact, MicroObjectArtifact,
    HistogramBundle, RenderManifest, QualityReport,
)


@dataclass
class RasterEntry:
    """Serializable surface entry."""
    surface_id: str
    surface_type: str
    grid_ref: str
    units: str
    resolution_m: float
    render_range: tuple
    palette: str
    source_layers: List[str]
    values: List[List[Optional[float]]]
    stats: Dict[str, float] = field(default_factory=dict)


@dataclass
class VectorFeature:
    """GeoJSON-like zone feature."""
    feature_id: str
    feature_type: str  # ZoneType value
    family: str  # ZoneFamily value
    geometry_type: str  # "Polygon" (cell grid)
    cell_indices: List[tuple]
    bbox: tuple
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TileManifest:
    """Manifest for map tile rendering."""
    run_id: str
    grid_height: int
    grid_width: int
    resolution_m: float
    available_layers: List[str]
    available_modes: List[Dict[str, Any]]
    style_pack: str
    quality: Dict[str, Any] = field(default_factory=dict)


def export_raster_pack(output: Layer10Output) -> List[RasterEntry]:
    """Export all surfaces as serializable raster entries."""
    entries = []
    for s in output.surface_pack:
        # Compute quick stats
        vals = [v for row in s.values for v in row if v is not None]
        stats = {}
        if vals:
            stats = {
                "mean": round(sum(vals) / len(vals), 4),
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
                "std": round((sum((v - sum(vals)/len(vals))**2 for v in vals) / len(vals))**0.5, 4),
                "valid_pixels": len(vals),
                "total_pixels": len(s.values) * (len(s.values[0]) if s.values else 0),
            }

        entries.append(RasterEntry(
            surface_id=s.surface_id,
            surface_type=s.semantic_type.value,
            grid_ref=s.grid_ref,
            units=s.units,
            resolution_m=s.native_resolution_m,
            render_range=s.render_range,
            palette=s.palette_id.value,
            source_layers=s.source_layers,
            values=s.values,
            stats=stats,
        ))

    return entries


def export_vector_pack(output: Layer10Output) -> List[VectorFeature]:
    """Export zones + micro-objects as vector features."""
    features = []

    for z in output.zone_pack:
        features.append(VectorFeature(
            feature_id=z.zone_id,
            feature_type=z.zone_type.value,
            family=z.zone_family.value,
            geometry_type="CellGrid",
            cell_indices=z.cell_indices,
            bbox=z.bbox,
            properties={
                "severity": z.severity,
                "confidence": z.confidence,
                "area_m2": z.area_m2,
                "area_pct": z.area_pct,
                "top_drivers": z.top_drivers,
                "linked_actions": z.linked_actions,
                "surface_stats": z.surface_stats,
            },
        ))

    for o in output.micro_objects:
        features.append(VectorFeature(
            feature_id=o.object_id,
            feature_type=o.object_type.value,
            family="STRUCTURAL",
            geometry_type="Point",
            cell_indices=o.cell_indices,
            bbox=(o.centroid[0], o.centroid[1], o.centroid[0], o.centroid[1]),
            properties={
                "score": o.score,
                "confidence": o.confidence,
                "area_m2": o.area_m2,
                "measurements": o.measurements,
                "derived_from": o.derived_from,
            },
        ))

    return features


def export_tile_manifest(output: Layer10Output, H: int, W: int, resolution_m: float) -> TileManifest:
    """Build tile manifest for frontend consumption."""
    layers = [s.semantic_type.value for s in output.surface_pack]
    modes = []
    for m in output.render_manifest.available_modes:
        modes.append({
            "mode": m.mode.value,
            "display_name": m.display_name,
            "enabled": m.enabled,
            "palette": m.palette_id.value,
            "surface_ids": m.surface_ids,
            "requires_resolution_m": m.requires_resolution_m,
        })

    quality = {
        "degradation": output.quality_report.degradation_mode.value,
        "reliability": output.quality_report.reliability_score,
        "surfaces": output.quality_report.surfaces_generated,
        "zones": output.quality_report.zones_generated,
        "objects": output.quality_report.micro_objects_detected,
        "grid_ok": output.quality_report.grid_alignment_ok,
        "detail_ok": output.quality_report.detail_conservation_ok,
    }

    return TileManifest(
        run_id=output.run_id,
        grid_height=H,
        grid_width=W,
        resolution_m=resolution_m,
        available_layers=layers,
        available_modes=modes,
        style_pack=output.render_manifest.style_pack,
        quality=quality,
    )


def export_full_product(output: Layer10Output, H: int, W: int, resolution_m: float) -> Dict[str, Any]:
    """Export complete Layer 10 product as a serializable dict."""
    raster_pack = export_raster_pack(output)
    vector_pack = export_vector_pack(output)
    tile_manifest = export_tile_manifest(output, H, W, resolution_m)

    return {
        "run_id": output.run_id,
        "timestamp": output.timestamp,
        "input_run_ids": output.input_run_ids,
        "raster_pack": [asdict(r) for r in raster_pack],
        "vector_pack": [asdict(f) for f in vector_pack],
        "tile_manifest": asdict(tile_manifest),
        "histogram_bundle": {
            "field_count": len(output.histogram_bundle.field_histograms),
            "zone_count": len(output.histogram_bundle.zone_histograms),
        },
        "quality": {
            "degradation": output.quality_report.degradation_mode.value,
            "reliability": output.quality_report.reliability_score,
            "warnings": output.quality_report.warnings,
        },
        "provenance": output.provenance,
    }
