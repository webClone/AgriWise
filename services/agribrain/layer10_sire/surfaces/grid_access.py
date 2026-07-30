# -*- coding: utf-8 -*-
import numpy as np
from typing import Any, List, Tuple

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

def resample_to(arr: np.ndarray, target_shape: Tuple[int, int], method: str = "bilinear") -> np.ndarray:
    """
    Resamples a 2D numpy array to target (height, width).
    """
    target_H, target_W = target_shape
    if arr is None or not isinstance(arr, np.ndarray) or arr.ndim != 2 or arr.size == 0:
        return np.full((target_H, target_W), np.nan, dtype=np.float32)
    if arr.shape == (target_H, target_W):
        return arr
    old_h, old_w = arr.shape
    if method == "nearest":
        ys = np.clip(np.round((np.arange(target_H) + 0.5) * old_h / target_H - 0.5).astype(int), 0, old_h - 1)
        xs = np.clip(np.round((np.arange(target_W) + 0.5) * old_w / target_W - 0.5).astype(int), 0, old_w - 1)
        return arr[np.ix_(ys, xs)]
    else:
        # Bilinear interpolation
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
