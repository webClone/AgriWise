"""
Microdetail Fusion — Conservative detail redistribution
========================================================

Key principle: redistribute coarse truth across fine structures
WITHOUT inventing new average signal. Mean-preserving.

Takes:
  - Coarse field/zone-level values (from L3-L8)
  - Fine structural objects (canopy patches, rows, gaps)
  
Returns:
  - Refined values per structural object (conservative redistribution)
"""
from typing import List, Dict, Any
from services.agribrain.layer10_sire.schema import (
    SurfaceArtifact, MicroObjectArtifact, ZoneArtifact,
)


def redistribute_to_objects(
    surfaces: List[SurfaceArtifact],
    objects: List[MicroObjectArtifact],
    H: int, W: int,
) -> Dict[str, Dict[str, float]]:
    """
    For each micro-object, compute per-surface statistics
    within its cell footprint. Mean-preserving: no new values invented.

    Returns:
      {object_id: {surface_type: mean_value_in_footprint}}
    """
    result = {}

    for obj in objects:
        obj_stats = {}
        cells = obj.cell_indices

        if not cells:
            continue

        for surface in surfaces:
            vals = []
            for r, c in cells:
                if 0 <= r < H and 0 <= c < W:
                    v = surface.values[r][c]
                    if v is not None:
                        vals.append(v)

            if vals:
                obj_stats[surface.semantic_type.value] = {
                    "mean": round(sum(vals) / len(vals), 4),
                    "min": round(min(vals), 4),
                    "max": round(max(vals), 4),
                    "count": len(vals),
                }

        result[obj.object_id] = obj_stats

    return result


def redistribute_to_zones(
    surfaces: List[SurfaceArtifact],
    zones: List[ZoneArtifact],
    H: int, W: int,
) -> Dict[str, Dict[str, float]]:
    """
    For each zone, compute per-surface statistics within zone footprint.

    Returns:
      {zone_id: {surface_type: {mean, min, max, count}}}
    """
    result = {}

    for zone in zones:
        zone_stats = {}
        cells = zone.cell_indices

        if not cells:
            continue

        for surface in surfaces:
            vals = []
            for r, c in cells:
                if 0 <= r < H and 0 <= c < W:
                    v = surface.values[r][c]
                    if v is not None:
                        vals.append(v)

            if vals:
                zone_stats[surface.semantic_type.value] = {
                    "mean": round(sum(vals) / len(vals), 4),
                    "min": round(min(vals), 4),
                    "max": round(max(vals), 4),
                    "count": len(vals),
                }

        result[zone.zone_id] = zone_stats

    return result


def verify_conservation(
    surface: SurfaceArtifact,
    objects: List[MicroObjectArtifact],
    H: int, W: int,
    tolerance: float = 0.01,
) -> bool:
    """
    Verify that mean of surface within all objects ≈ field mean.
    Conservative: detail must not inflate or deflate average.
    """
    # Field mean
    field_vals = []
    for r in range(H):
        for c in range(W):
            v = surface.values[r][c]
            if v is not None:
                field_vals.append(v)

    if not field_vals:
        return True

    field_mean = sum(field_vals) / len(field_vals)

    # Object-weighted mean
    obj_vals = []
    for obj in objects:
        for r, c in obj.cell_indices:
            if 0 <= r < H and 0 <= c < W:
                v = surface.values[r][c]
                if v is not None:
                    obj_vals.append(v)

    if not obj_vals:
        return True

    obj_mean = sum(obj_vals) / len(obj_vals)

    return abs(obj_mean - field_mean) < tolerance
