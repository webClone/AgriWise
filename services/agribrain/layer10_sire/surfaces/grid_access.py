# -*- coding: utf-8 -*-
import numpy as np
from typing import Any, List, Tuple, Sequence, Optional

def extract_surface_grid(src: Any) -> np.ndarray:
    """
    Extracts a 2D numpy array from any grid representation:
    - SurfaceArtifact (using s.values or s.pixel_array)
    - dict (with 'values' or 'pixel_array')
    - list of lists
    - numpy ndarray
    - callables returning any of the above
    """
    if src is None:
        return None
    grid = None
    if isinstance(src, dict):
        grid = src.get("values") or src.get("pixel_array")
    elif hasattr(src, "values"):
        grid = src.values
        if callable(grid):
            try:
                grid = grid()
            except Exception:
                grid = None
    elif hasattr(src, "pixel_array"):
        grid = src.pixel_array
        if callable(grid):
            try:
                grid = grid()
            except Exception:
                grid = None
    else:
        grid = src

    if grid is None:
        return None

    try:
        arr = np.asarray(grid, dtype=np.float32)
        if arr.ndim != 2:
            return None
        return arr
    except Exception:
        return None

def extract_named_grid(name: str, base_surfaces: List[Any], l10_input: Any = None, l1_data: Any = None) -> np.ndarray:
    """
    Extracts grid array by name from inputs, composites, or base surfaces.
    """
    # 1. Search in base_surfaces first (they are artifacts)
    if base_surfaces:
        for s in base_surfaces:
            s_type = getattr(s, "semantic_type", None)
            s_type_val = getattr(s_type, "value", str(s_type)) if s_type else ""
            s_id = getattr(s, "surface_id", "")
            if s_type_val == name or s_id == name:
                arr = extract_surface_grid(s)
                if arr is not None:
                    return arr

    # 2. Search in l10_input.raster_composites
    if l10_input:
        rc = getattr(l10_input, "raster_composites", {}) or {}
        if name in rc:
            arr = extract_surface_grid(rc[name])
            if arr is not None:
                return arr
        for k, v in rc.items():
            if k.lower() == name.lower():
                arr = extract_surface_grid(v)
                if arr is not None:
                    return arr

        if getattr(l10_input, "field_tensor", None):
            ft_rc = getattr(l10_input.field_tensor, "raster_composites", {}) or {}
            if name in ft_rc:
                arr = extract_surface_grid(ft_rc[name])
                if arr is not None:
                    return arr
            for k, v in ft_rc.items():
                if k.lower() == name.lower():
                    arr = extract_surface_grid(v)
                    if arr is not None:
                        return arr

    # 3. Search in l1_data.raster_maps
    if l1_data:
        rm = getattr(l1_data, "raster_maps", {}) or {}
        if name in rm:
            arr = extract_surface_grid(rm[name])
            if arr is not None:
                return arr
        for k, v in rm.items():
            if k.lower() == name.lower():
                arr = extract_surface_grid(v)
                if arr is not None:
                    return arr

    return None

def resample_to(
    arr: np.ndarray,
    target_shape: Tuple[int, int],
    method: str = "bilinear",
    src_transform: Optional[Sequence[float]] = None,
    src_crs: Optional[str] = None,
    target_transform: Optional[Sequence[float]] = None,
    target_crs: Optional[str] = None,
) -> np.ndarray:
    """
    Resamples or reprojects a 2D numpy array to target (height, width).
    Uses transform-aware reproject_scientific_grid if transforms/CRS are supplied.
    """
    target_H, target_W = target_shape
    if arr is None or not isinstance(arr, np.ndarray) or arr.ndim != 2 or arr.size == 0:
        return np.full((target_H, target_W), np.nan, dtype=np.float32)

    src_tf = src_transform or getattr(arr, "transform", None) or getattr(arr, "_transform", None)
    src_c = src_crs or getattr(arr, "crs", None) or getattr(arr, "_crs", None)
    tgt_tf = target_transform or getattr(arr, "target_transform", None)
    tgt_c = target_crs or getattr(arr, "target_crs", None)

    if src_tf and src_c and tgt_tf and tgt_c:
        try:
            return reproject_scientific_grid(
                src_grid=arr,
                src_transform=src_tf,
                src_crs=src_c,
                target_shape=target_shape,
                target_transform=tgt_tf,
                target_crs=tgt_c,
                product_type=method,
            )
        except Exception:
            pass

    if arr.shape == (target_H, target_W):
        return arr
    old_h, old_w = arr.shape
    if method == "nearest":
        ys = np.clip(np.round((np.arange(target_H) + 0.5) * old_h / target_H - 0.5).astype(int), 0, old_h - 1)
        xs = np.clip(np.round((np.arange(target_W) + 0.5) * old_w / target_W - 0.5).astype(int), 0, old_w - 1)
        return arr[np.ix_(ys, xs)]
    else:
        ys = (np.arange(target_H, dtype=float) + 0.5) * old_h / target_H - 0.5
        xs = (np.arange(target_W, dtype=float) + 0.5) * old_w / target_W - 0.5
        y0 = np.clip(np.floor(ys).astype(int), 0, old_h - 1)
        y1 = np.clip(y0 + 1, 0, old_h - 1)
        x0 = np.clip(np.floor(xs).astype(int), 0, old_w - 1)
        x1 = np.clip(x0 + 1, 0, old_w - 1)
        wy = np.clip(ys - y0, 0.0, 1.0)[:, np.newaxis]
        wx = np.clip(xs - x0, 0.0, 1.0)[np.newaxis, :]
        result = (arr[np.ix_(y0, x0)] * (1 - wy) * (1 - wx) +
                  arr[np.ix_(y0, x1)] * (1 - wy) * wx +
                  arr[np.ix_(y1, x0)] * wy * (1 - wx) +
                  arr[np.ix_(y1, x1)] * wy * wx)
        nan_mask = np.isnan(result)
        if np.any(nan_mask):
            ny = np.clip(np.round(ys).astype(int), 0, old_h - 1)
            nx = np.clip(np.round(xs).astype(int), 0, old_w - 1)
            result[nan_mask] = arr[np.ix_(ny, nx)][nan_mask]
        return result

def reproject_scientific_grid(
    src_grid: np.ndarray,
    src_transform: Sequence[float],
    src_crs: str,
    target_shape: Tuple[int, int],
    target_transform: Sequence[float],
    target_crs: str,
    product_type: str = "continuous",
) -> np.ndarray:
    """
    Transforms a scientific grid using affine metadata and CRS bounds.
    Fails closed if affine metadata or CRS is missing.
    """
    target_H, target_W = target_shape
    if (
        src_grid is None or not isinstance(src_grid, np.ndarray) or src_grid.ndim != 2
        or not src_transform or len(src_transform) != 6
        or not target_transform or len(target_transform) != 6
        or not src_crs or not target_crs
    ):
        raise ValueError("reproject_scientific_grid requires valid 2D array, 6-element affine transforms, and CRS metadata")

    src_dx, _, src_x0, _, src_dy, src_y0 = [float(v) for v in src_transform]
    tgt_dx, _, tgt_x0, _, tgt_dy, tgt_y0 = [float(v) for v in target_transform]

    if abs(src_dx) < 1e-9 or abs(src_dy) < 1e-9:
        raise ValueError("Invalid source transform resolution")

    target_cols = np.arange(target_W, dtype=np.float64) + 0.5
    target_rows = np.arange(target_H, dtype=np.float64) + 0.5

    target_x_map = tgt_x0 + target_cols * tgt_dx
    target_y_map = tgt_y0 + target_rows * tgt_dy

    src_cols = (target_x_map - src_x0) / src_dx - 0.5
    src_rows = (target_y_map - src_y0) / src_dy - 0.5

    old_h, old_w = src_grid.shape
    prod_lower = str(product_type).lower()

    if any(k in prod_lower for k in ("mask", "categorical", "discrete", "class")):
        ys = np.clip(np.round(src_rows).astype(int), 0, old_h - 1)
        xs = np.clip(np.round(src_cols).astype(int), 0, old_w - 1)
        return src_grid[np.ix_(ys, xs)]
    elif any(k in prod_lower for k in ("probability", "confidence", "reliability")):
        ys = np.clip(np.round(src_rows).astype(int), 0, old_h - 1)
        xs = np.clip(np.round(src_cols).astype(int), 0, old_w - 1)
        result = src_grid[np.ix_(ys, xs)].copy()
        return result
    else:
        y0 = np.clip(np.floor(src_rows).astype(int), 0, old_h - 1)
        y1 = np.clip(y0 + 1, 0, old_h - 1)
        x0 = np.clip(np.floor(src_cols).astype(int), 0, old_w - 1)
        x1 = np.clip(x0 + 1, 0, old_w - 1)
        wy = np.clip(src_rows - y0, 0.0, 1.0)[:, np.newaxis]
        wx = np.clip(src_cols - x0, 0.0, 1.0)[np.newaxis, :]
        return (src_grid[np.ix_(y0, x0)] * (1 - wy) * (1 - wx) +
                src_grid[np.ix_(y0, x1)] * (1 - wy) * wx +
                src_grid[np.ix_(y1, x0)] * wy * (1 - wx) +
                src_grid[np.ix_(y1, x1)] * wy * wx)

def finite_ratio(arr: np.ndarray) -> float:
    if arr is None or arr.size == 0:
        return 0.0
    return float(np.sum(np.isfinite(arr)) / arr.size)

def nanstd_safe(arr: np.ndarray) -> float:
    if arr is None or arr.size == 0:
        return 0.0
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return 0.0
    return float(np.std(finite))

def entropy_score(arr: np.ndarray) -> float:
    """
    Computes a simplified Shannon entropy score for spatial distribution.
    """
    if arr is None or arr.size == 0:
        return 0.0
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return 0.0
    # Discretize into 10 bins
    counts, _ = np.histogram(finite, bins=10)
    probs = counts / float(finite.size)
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log2(probs)))

def is_spatially_meaningful(arr: np.ndarray, min_std: float = 0.01, min_unique: int = 4) -> bool:
    if arr is None:
        return False
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return False
    if np.std(finite) <= min_std:
        return False
    if len(np.unique(finite)) < min_unique:
        return False
    return True
