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
    """Serializable surface entry preserving full scientific export receipt."""
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
    # Scientific export receipt fields
    grid_spec: Optional[Dict[str, Any]] = None
    source_grid_spec: Optional[Dict[str, Any]] = None
    display_grid_spec: Optional[Dict[str, Any]] = None
    display_resolution_m: float = 1.0
    effective_resolution_m: float = 10.0
    confidence: Optional[List[List[Optional[float]]]] = None
    uncertainty: Optional[float] = None
    observed_mask: Optional[List[List[bool]]] = None
    inferred_mask: Optional[List[List[bool]]] = None
    valid_mask: Optional[List[List[bool]]] = None
    grounding_class: Optional[str] = None
    state_update_allowed: bool = False
    prescription_driver_allowed: bool = False
    block_reasons: Optional[List[str]] = None
    provenance: Dict[str, Any] = field(default_factory=dict)
    canonical_metadata: Dict[str, Any] = field(default_factory=dict)


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
    """Export all surfaces as serializable raster entries preserving scientific receipt and canonical parity."""
    import math
    from ..surface_contract import serialize_surface_artifact

    entries = []
    for s in output.surface_pack:
        canon_doc = serialize_surface_artifact(s)
        prov = s.provenance if isinstance(s.provenance, dict) else {}

        # Compute quick stats over strictly finite, numeric non-boolean values
        vals = [
            float(v) for row in s.values for v in row
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        ]
        stats = {}
        if vals:
            mean_val = sum(vals) / len(vals)
            stats = {
                "mean": round(mean_val, 4),
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
                "std": round((sum((v - mean_val) ** 2 for v in vals) / len(vals)) ** 0.5, 4),
                "valid_pixels": len(vals),
                "total_pixels": len(s.values) * (len(s.values[0]) if s.values else 0),
            }
        canon_doc["stats"] = stats

        valid_mask = [
            [
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for v in row
            ]
            for row in s.values
        ]

        g_spec_dict = canon_doc.get("grid_spec")
        source_g_spec_dict = canon_doc.get("source_grid_spec")
        display_g_spec_dict = canon_doc.get("display_grid_spec")
        display_res = float(canon_doc.get("display_resolution_m") or 1.0)
        eff_res = float(canon_doc.get("effective_resolution_m") or 10.0)
        conf_val = canon_doc.get("confidence")
        unc_val = canon_doc.get("uncertainty")
        obs_mask = canon_doc.get("observed_mask")
        inf_mask = canon_doc.get("inferred_mask")

        # Canonical permissions and block reasons take precedence
        state_update_allowed = canon_doc.get("state_update_allowed", False)
        prescription_driver_allowed = canon_doc.get("prescription_driver_allowed", False)
        block_reasons = canon_doc.get("block_reasons")

        entries.append(RasterEntry(
            surface_id=s.surface_id,
            surface_type=s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type),
            grid_ref=s.grid_ref,
            units=s.units,
            resolution_m=s.native_resolution_m,
            render_range=s.render_range,
            palette=s.palette_id.value if hasattr(s.palette_id, "value") else str(s.palette_id),
            source_layers=s.source_layers,
            values=s.values,
            stats=stats,
            grid_spec=g_spec_dict,
            source_grid_spec=source_g_spec_dict,
            display_grid_spec=display_g_spec_dict,
            display_resolution_m=display_res,
            effective_resolution_m=eff_res,
            confidence=conf_val,
            uncertainty=unc_val,
            observed_mask=obs_mask,
            inferred_mask=inf_mask,
            valid_mask=valid_mask,
            grounding_class=s.grounding_class,
            state_update_allowed=state_update_allowed,
            prescription_driver_allowed=prescription_driver_allowed,
            block_reasons=list(block_reasons) if block_reasons else None,
            provenance=prov,
            canonical_metadata=canon_doc,
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
