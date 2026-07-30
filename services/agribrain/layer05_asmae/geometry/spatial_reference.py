"""Canonical spatial-reference handling for ASMAE.

Layer 0 publishes GDAL geotransforms::

    [origin_x, pixel_width, row_rotation,
     origin_y, column_rotation, pixel_height]

Historically ASMAE consumed those values as Rasterio ``Affine`` constructor
arguments.  That swaps the origin and scale terms and, for geographic CRS,
also mistakes degrees for metres.  This module is the only place where an
upstream transform is decoded.  Spatial assimilation is performed only in a
projected metre CRS.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


class SpatialReferenceError(ValueError):
    """Raised when a scene cannot be placed on a metric spatial grid."""


def affine_from_gdal(transform: Iterable[float]):
    """Return a Rasterio Affine from a six-value GDAL geotransform."""
    try:
        from rasterio.transform import Affine

        values = [float(value) for value in transform]
        if len(values) != 6 or not all(math.isfinite(value) for value in values):
            raise SpatialReferenceError("transform_must_be_six_finite_gdal_values")
        return Affine.from_gdal(*values)
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise SpatialReferenceError("rasterio_is_required_for_spatial_assimilation") from exc


def gdal_from_affine(affine: Any) -> List[float]:
    """Serialize a Rasterio Affine in the canonical upstream GDAL order."""
    return [float(value) for value in affine.to_gdal()]


def crs_is_projected_metre(crs_value: Any) -> bool:
    try:
        from rasterio.crs import CRS

        crs = CRS.from_user_input(crs_value)
        if not crs.is_projected:
            return False
        units = str(getattr(crs, "linear_units", "") or "").lower()
        if units in {"metre", "meter", "metres", "meters", "m"}:
            return True
        factor = getattr(crs, "linear_units_factor", None)
        if isinstance(factor, tuple) and len(factor) > 1:
            factor = factor[1]
        return isinstance(factor, (int, float)) and abs(float(factor) - 1.0) < 1e-9
    except Exception:
        return False


def require_projected_metric_crs(crs_value: Any) -> str:
    """Return the normalized CRS string or fail closed for non-metric grids."""
    if not crs_is_projected_metre(crs_value):
        raise SpatialReferenceError("crs_is_not_projected_metre")
    from rasterio.crs import CRS

    return CRS.from_user_input(crs_value).to_string()


def pixel_size_xy(transform: Iterable[float]) -> Tuple[float, float]:
    affine = affine_from_gdal(transform)
    x_size = math.hypot(float(affine.a), float(affine.d))
    y_size = math.hypot(float(affine.b), float(affine.e))
    if x_size <= 0.0 or y_size <= 0.0:
        raise SpatialReferenceError("non_positive_pixel_size")
    return x_size, y_size


def pixel_size_m(scene: Any) -> float:
    """Return mean native pixel size, rejecting non-metric scene CRS."""
    if not crs_is_projected_metre(getattr(scene, "crs", None)):
        raise SpatialReferenceError("scene_crs_is_not_projected_metre")
    x_size, y_size = pixel_size_xy(getattr(scene, "transform", []))
    return (x_size + y_size) / 2.0


def origin_xy(transform: Iterable[float]) -> Tuple[float, float]:
    affine = affine_from_gdal(transform)
    return float(affine.c), float(affine.f)


def _flatten_coordinate_pairs(value: Any) -> List[Tuple[float, float]]:
    result: List[Tuple[float, float]] = []
    if isinstance(value, (list, tuple)):
        if (
            len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            result.append((float(value[0]), float(value[1])))
        else:
            for child in value:
                result.extend(_flatten_coordinate_pairs(child))
    return result


def coerce_polygon_geojson(value: Any) -> Optional[Dict[str, Any]]:
    """Accept GeoJSON geometry/feature or the orchestrator's coordinate list."""
    if not value:
        return None
    if isinstance(value, dict):
        if value.get("type") == "Feature" and isinstance(value.get("geometry"), dict):
            return dict(value["geometry"])
        if value.get("type") in {"Polygon", "MultiPolygon"}:
            return dict(value)
        if "coordinates" in value:
            coordinates = value.get("coordinates")
            pairs = _flatten_coordinate_pairs(coordinates)
            if len(pairs) >= 3:
                ring = list(pairs)
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                return {"type": "Polygon", "coordinates": [ring]}
    pairs = _flatten_coordinate_pairs(value)
    if len(pairs) >= 3:
        if pairs[0] != pairs[-1]:
            pairs.append(pairs[0])
        return {"type": "Polygon", "coordinates": [pairs]}
    return None


def _scene_center_lon_lat(scene: Any) -> Tuple[float, float]:
    from rasterio.crs import CRS
    from rasterio.transform import array_bounds
    from rasterio.warp import transform as warp_points

    width = int(getattr(scene, "width", 0) or 0)
    height = int(getattr(scene, "height", 0) or 0)
    if width <= 0 or height <= 0:
        raise SpatialReferenceError("scene_dimensions_missing")
    affine = affine_from_gdal(getattr(scene, "transform", []))
    west, south, east, north = array_bounds(height, width, affine)
    x = (west + east) / 2.0
    y = (south + north) / 2.0
    source = CRS.from_user_input(getattr(scene, "crs", None))
    if source.is_geographic:
        return float(x), float(y)
    xs, ys = warp_points(source, "EPSG:4326", [x], [y])
    return float(xs[0]), float(ys[0])


def choose_metric_crs(scenes: List[Any], polygon_geojson: Any = None) -> str:
    """Choose a shared metre CRS, preferring an existing valid scene CRS."""
    for scene in scenes:
        value = getattr(scene, "crs", None)
        if crs_is_projected_metre(value):
            from rasterio.crs import CRS

            return CRS.from_user_input(value).to_string()

    polygon = coerce_polygon_geojson(polygon_geojson)
    points = _flatten_coordinate_pairs(polygon.get("coordinates")) if polygon else []
    if points:
        lon = sum(point[0] for point in points) / len(points)
        lat = sum(point[1] for point in points) / len(points)
    elif scenes:
        lon, lat = _scene_center_lon_lat(scenes[0])
    else:
        raise SpatialReferenceError("no_scene_or_polygon_for_metric_crs")
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        raise SpatialReferenceError("cannot_derive_lon_lat_for_metric_crs")
    zone = max(1, min(60, int(math.floor((lon + 180.0) / 6.0)) + 1))
    epsg = (32600 if lat >= 0.0 else 32700) + zone
    return f"EPSG:{epsg}"


def _is_mask_name(name: str) -> bool:
    key = str(name).lower()
    return any(token in key for token in ("mask", "scl", "qa", "cloud", "snow", "data"))


def reproject_scene_to_metric(scene: Any, target_crs: str) -> Any:
    """Return a shallow-cloned scene reprojected into ``target_crs``.

    Scalar observations remain scalar.  Every two-dimensional raster matching
    the declared scene shape is warped with the same geometry.  Masks use
    nearest-neighbour resampling; continuous bands use bilinear resampling.
    """
    from rasterio.crs import CRS
    from rasterio.transform import array_bounds
    from rasterio.warp import Resampling, calculate_default_transform, reproject
    import numpy as np

    source_crs = CRS.from_user_input(getattr(scene, "crs", None))
    destination_crs = CRS.from_user_input(target_crs)
    width = int(getattr(scene, "width", 0) or 0)
    height = int(getattr(scene, "height", 0) or 0)
    if width <= 0 or height <= 0:
        raise SpatialReferenceError("scene_dimensions_missing")
    source_affine = affine_from_gdal(getattr(scene, "transform", []))

    if source_crs == destination_crs and crs_is_projected_metre(source_crs):
        cloned = copy.copy(scene)
        cloned.transform = gdal_from_affine(source_affine)
        cloned.transform_convention = "gdal"
        cloned.spatial_normalization = {
            "status": "already_metric",
            "source_crs": source_crs.to_string(),
            "target_crs": destination_crs.to_string(),
        }
        return cloned

    bounds = array_bounds(height, width, source_affine)
    destination_affine, destination_width, destination_height = calculate_default_transform(
        source_crs,
        destination_crs,
        width,
        height,
        *bounds,
    )
    if destination_width <= 0 or destination_height <= 0:
        raise SpatialReferenceError("reprojection_produced_empty_grid")

    def warp_mapping(mapping: Any, *, masks: bool) -> Dict[str, Any]:
        warped: Dict[str, Any] = {}
        for name, value in dict(mapping or {}).items():
            array = np.asarray(value)
            if array.ndim != 2 or array.shape != (height, width):
                warped[name] = value
                continue
            mask_like = masks or _is_mask_name(name)
            if mask_like:
                destination = np.zeros((destination_height, destination_width), dtype=array.dtype)
                resampling = Resampling.nearest
                destination_nodata = 0
            else:
                destination = np.full((destination_height, destination_width), np.nan, dtype=np.float32)
                resampling = Resampling.bilinear
                destination_nodata = np.nan
            reproject(
                source=array,
                destination=destination,
                src_transform=source_affine,
                src_crs=source_crs,
                dst_transform=destination_affine,
                dst_crs=destination_crs,
                src_nodata=np.nan if np.issubdtype(array.dtype, np.floating) else None,
                dst_nodata=destination_nodata,
                resampling=resampling,
            )
            warped[name] = destination
        return warped

    cloned = copy.copy(scene)
    cloned.crs_original = str(getattr(scene, "crs", ""))
    cloned.transform_original = list(getattr(scene, "transform", []) or [])
    cloned.crs = destination_crs.to_string()
    cloned.transform = gdal_from_affine(destination_affine)
    cloned.transform_convention = "gdal"
    cloned.width = int(destination_width)
    cloned.height = int(destination_height)
    cloned.bands = warp_mapping(getattr(scene, "bands", {}), masks=False)
    cloned.masks = warp_mapping(getattr(scene, "masks", {}), masks=True)
    cloned.spatial_normalization = {
        "status": "reprojected",
        "source_crs": source_crs.to_string(),
        "target_crs": destination_crs.to_string(),
        "source_transform_convention": "gdal",
    }
    return cloned


def normalize_scene_stack_to_metric(
    scenes: List[Any],
    polygon_geojson: Any = None,
) -> Tuple[List[Any], str, List[Dict[str, Any]]]:
    """Reproject a scene stack to one metric CRS or raise fail-closed."""
    if not scenes:
        return [], "", []
    target_crs = choose_metric_crs(scenes, polygon_geojson)
    normalized: List[Any] = []
    proof: List[Dict[str, Any]] = []
    for scene in scenes:
        result = reproject_scene_to_metric(scene, target_crs)
        normalized.append(result)
        proof.append({
            "scene_id": str(getattr(result, "scene_id", "")),
            **dict(getattr(result, "spatial_normalization", {}) or {}),
            "transform_convention": "gdal",
        })
    return normalized, target_crs, proof


@dataclass(frozen=True)
class TargetMicrozoneGrid:
    crs: str
    origin_x: float
    origin_y: float
    width_m: float
    height_m: float
    n_rows: int
    n_cols: int
    resolution_m: int

    @property
    def transform_gdal(self) -> List[float]:
        return [
            self.origin_x,
            float(self.resolution_m),
            0.0,
            self.origin_y,
            0.0,
            -float(self.resolution_m),
        ]


def target_grid_from_reference(scene: Any, resolution_m: int) -> TargetMicrozoneGrid:
    """Build the fixed microzone grid from the reference scene's bounds."""
    from rasterio.transform import array_bounds

    if not crs_is_projected_metre(getattr(scene, "crs", None)):
        raise SpatialReferenceError("reference_scene_not_metric")
    width = int(getattr(scene, "width", 0) or 0)
    height = int(getattr(scene, "height", 0) or 0)
    if width <= 0 or height <= 0:
        raise SpatialReferenceError("reference_scene_dimensions_missing")
    affine = affine_from_gdal(getattr(scene, "transform", []))
    west, south, east, north = array_bounds(height, width, affine)
    width_m = max(0.0, float(east - west))
    height_m = max(0.0, float(north - south))
    if width_m <= 0.0 or height_m <= 0.0:
        raise SpatialReferenceError("reference_scene_empty_bounds")
    return TargetMicrozoneGrid(
        crs=str(getattr(scene, "crs", "")),
        origin_x=float(west),
        origin_y=float(north),
        width_m=width_m,
        height_m=height_m,
        n_rows=int(math.ceil(height_m / float(resolution_m))),
        n_cols=int(math.ceil(width_m / float(resolution_m))),
        resolution_m=int(resolution_m),
    )
