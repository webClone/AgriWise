"""Immutable valid-pixel support shared by H_t and observation extraction."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional, Tuple

import numpy as np

from .mask_builder import VALID_SCL_CLASSES, MARGINAL_SCL_CLASSES
from .spatial_reference import affine_from_gdal, coerce_polygon_geojson


SUPPORT_CONTRACT_VERSION = "asmae_pixel_support_v2"


def _as_shape(value: Any, shape: Tuple[int, int]) -> Optional[np.ndarray]:
    try:
        array = np.asarray(value)
        return array if array.ndim == 2 and array.shape == shape else None
    except Exception:
        return None


def _polygon_mask(scene: Any, polygon_geojson: Any) -> Optional[np.ndarray]:
    geometry = coerce_polygon_geojson(polygon_geojson)
    if geometry is None:
        return None
    try:
        from rasterio.features import rasterize
        from rasterio.warp import transform_geom

        scene_crs = str(getattr(scene, "crs", ""))
        projected = transform_geom("EPSG:4326", scene_crs, geometry, precision=9)
        return rasterize(
            [(projected, 1)],
            out_shape=(int(scene.height), int(scene.width)),
            transform=affine_from_gdal(scene.transform),
            fill=0,
            dtype="uint8",
            all_touched=False,
        ).astype(bool)
    except Exception:
        return None


def build_scene_valid_support(scene: Any, polygon_geojson: Any = None) -> Dict[str, Any]:
    """Attach and return the canonical valid-pixel support for ``scene``.

    The support is the intersection of SCL/DATAMASK, declared valid masks,
    field geometry, and finite raster coverage.  ``True`` always means valid.
    The resulting array is read-only so H_t and feature extraction cannot
    silently diverge by mutating it later.
    """
    height = int(getattr(scene, "height", 0) or 0)
    width = int(getattr(scene, "width", 0) or 0)
    if height <= 0 or width <= 0:
        scene.valid_support = None
        scene.valid_support_hash = ""
        scene.valid_fraction = 0.0
        return {
            "contract_version": SUPPORT_CONTRACT_VERSION,
            "status": "unavailable",
            "reason": "scene_dimensions_missing",
        }

    shape = (height, width)
    support = np.ones(shape, dtype=bool)
    reasons = []
    masks = dict(getattr(scene, "masks", {}) or {})
    bands = dict(getattr(scene, "bands", {}) or {})

    scl = next((masks[key] for key in ("SCL", "scl") if key in masks), None)
    scl_array = _as_shape(scl, shape) if scl is not None else None
    if scl_array is not None:
        allowed = np.isin(scl_array.astype(np.int16), list(VALID_SCL_CLASSES | MARGINAL_SCL_CLASSES))
        support &= allowed
        reasons.append("scl")

    datamask = next(
        (masks[key] for key in ("DATAMASK", "datamask", "data_mask") if key in masks),
        None,
    )
    datamask_array = _as_shape(datamask, shape) if datamask is not None else None
    if datamask_array is not None:
        support &= np.isfinite(datamask_array.astype(float)) & (datamask_array.astype(float) > 0.0)
        reasons.append("datamask")

    valid_names = (
        "valid_support", "combined_mask", "valid_mask", "quality_mask",
        "polygon_mask", "nodata_mask", "clear_mask", "cloud_mask",
    )
    for name in valid_names:
        if name not in masks:
            continue
        array = _as_shape(masks[name], shape)
        if array is not None:
            support &= array.astype(bool)
            reasons.append(name)

    polygon = _polygon_mask(scene, polygon_geojson)
    if polygon is not None:
        support &= polygon
        reasons.append("field_polygon")

    finite_coverage = None
    for value in bands.values():
        array = _as_shape(value, shape)
        if array is None or not np.issubdtype(array.dtype, np.number):
            continue
        current = np.isfinite(array.astype(float))
        finite_coverage = current if finite_coverage is None else (finite_coverage | current)
    if finite_coverage is not None:
        support &= finite_coverage
        reasons.append("finite_raster_coverage")

    support = np.ascontiguousarray(support, dtype=bool)
    support.setflags(write=False)
    digest = hashlib.sha256(support.astype(np.uint8).tobytes()).hexdigest()
    scene.valid_support = support
    scene.valid_support_hash = digest
    scene.valid_fraction = float(np.mean(support)) if support.size else 0.0
    scene.masks = {**masks, "valid_support": support}
    return {
        "contract_version": SUPPORT_CONTRACT_VERSION,
        "status": "available",
        "support_hash": digest,
        "shape": [height, width],
        "valid_pixel_count": int(np.count_nonzero(support)),
        "total_pixel_count": int(support.size),
        "valid_fraction": scene.valid_fraction,
        "components": list(dict.fromkeys(reasons)),
    }


def feature_support(scene: Any, values: Any) -> np.ndarray:
    """Return base support intersected with feature finiteness."""
    array = np.asarray(values, dtype=float)
    base = getattr(scene, "valid_support", None)
    if array.ndim == 2 and base is not None and np.asarray(base).shape == array.shape:
        return np.asarray(base, dtype=bool) & np.isfinite(array)
    return np.isfinite(array)
