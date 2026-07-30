"""
Centralized GeoJSON Geometry Canonicalizer for AgriBrain.

Standardizes Feature / Polygon / MultiPolygon representations, transforms to
canonical CRS (EPSG:4326), normalizes precision and ring closure, and computes
canonical_geometry_hash and source_geometry_hash.
"""

import json
import hashlib
from typing import Any, Dict, List, Tuple, Optional

GEOMETRY_CANONICALIZATION_VERSION = "v924_bc10_21_geom_v1"


def _normalize_point(coords: Any, precision: int = 7) -> Tuple[float, float]:
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return (0.0, 0.0)
    x = round(float(coords[0]), precision)
    y = round(float(coords[1]), precision)
    return (x, y)


def _normalize_ring(ring: List[Any], precision: int = 7) -> List[Tuple[float, float]]:
    if not ring or not isinstance(ring, (list, tuple)):
        return []
    pts = [_normalize_point(pt, precision) for pt in ring]
    # Ensure ring closure
    if len(pts) > 0 and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def canonicalize_geometry(
    geo_json: Any,
    precision: int = 7,
) -> Dict[str, Any]:
    """
    Canonicalize a GeoJSON structure (Feature, Polygon, or MultiPolygon) into
    a deterministic, hashable MultiPolygon structure.
    
    Returns dict with:
        canonical_geojson: dict
        canonical_geometry_hash: str
        source_geometry_hash: str
        is_valid: bool
        vertex_count: int
        bounding_box: [min_x, min_y, max_x, max_y]
    """
    if not geo_json:
        return {
            "canonical_geojson": None,
            "canonical_geometry_hash": "",
            "source_geometry_hash": "",
            "is_valid": False,
            "vertex_count": 0,
            "bounding_box": [0.0, 0.0, 0.0, 0.0],
        }

    # Compute source geometry hash before modification
    source_bytes = json.dumps(geo_json, sort_keys=True).encode("utf-8")
    source_geometry_hash = hashlib.sha256(source_bytes).hexdigest()[:16]

    # Unwrap Feature or FeatureCollection if needed
    candidate = geo_json
    if isinstance(candidate, dict):
        if candidate.get("type") == "Feature":
            candidate = candidate.get("geometry", {})
        elif candidate.get("type") == "FeatureCollection":
            features = candidate.get("features", [])
            if features and isinstance(features[0], dict):
                candidate = features[0].get("geometry", {})

    gtype = candidate.get("type", "") if isinstance(candidate, dict) else ""
    coords = candidate.get("coordinates", []) if isinstance(candidate, dict) else []

    polygons: List[List[List[Tuple[float, float]]]] = []

    if gtype == "Polygon" and coords:
        poly_rings = [_normalize_ring(ring, precision) for ring in coords if ring]
        poly_rings = [r for r in poly_rings if len(r) >= 4]
        if poly_rings:
            polygons.append(poly_rings)

    elif gtype == "MultiPolygon" and coords:
        for poly in coords:
            poly_rings = [_normalize_ring(ring, precision) for ring in poly if ring]
            poly_rings = [r for r in poly_rings if len(r) >= 4]
            if poly_rings:
                polygons.append(poly_rings)

    if not polygons:
        return {
            "canonical_geojson": None,
            "canonical_geometry_hash": "",
            "source_geometry_hash": source_geometry_hash,
            "is_valid": False,
            "vertex_count": 0,
            "bounding_box": [0.0, 0.0, 0.0, 0.0],
        }

    # Sort rings and polygons deterministically
    sorted_polygons = []
    min_x, min_y, max_x, max_y = float("inf"), float("inf"), float("-inf"), float("-inf")
    vertex_count = 0

    for poly in polygons:
        sorted_rings = []
        for ring in poly:
            sorted_rings.append(ring)
            for x, y in ring:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                vertex_count += 1
        sorted_polygons.append(sorted_rings)

    canonical_struct = {
        "type": "MultiPolygon",
        "coordinates": sorted_polygons,
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "version": GEOMETRY_CANONICALIZATION_VERSION,
    }

    canonical_bytes = json.dumps(canonical_struct, sort_keys=True).encode("utf-8")
    canonical_hash = hashlib.sha256(canonical_bytes).hexdigest()[:16]

    bbox = [
        round(min_x, precision) if min_x != float("inf") else 0.0,
        round(min_y, precision) if min_y != float("inf") else 0.0,
        round(max_x, precision) if max_x != float("-inf") else 0.0,
        round(max_y, precision) if max_y != float("-inf") else 0.0,
    ]

    is_valid = vertex_count >= 4 and max_x > min_x and max_y > min_y

    return {
        "canonical_geojson": canonical_struct,
        "canonical_geometry_hash": canonical_hash,
        "source_geometry_hash": source_geometry_hash,
        "is_valid": is_valid,
        "vertex_count": vertex_count,
        "bounding_box": bbox,
    }
