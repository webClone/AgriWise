# -*- coding: utf-8 -*-
"""
RasterEvidence Accessor — BC.10.13

Centralises validation of every raster grid before it is consumed by ASMAE
composite generators or experimental visual generators.

RULE: No surface may be emitted from a raster that fails `is_spatially_meaningful`.
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Thresholds for spatial meaningfulness
_MIN_FINITE_RATIO = 0.30   # at least 30 % of cells must be non-NaN
_MIN_STD = 0.005            # standard deviation must exceed 0.005 (not constant)


@dataclass
class RasterEvidence:
    array: Optional[np.ndarray]          # 2-D float32 array, or None if unavailable
    source_name: str                     # e.g. "NDVI_CLEAN", "l1_raster_ndvi"
    source_reality: str                  # "real_raster" | "raster_composite_proxy" | "unavailable"
    grounding_class: str                 # passed through to surface provenance
    finite_ratio: float                  # fraction of non-NaN/non-inf cells  (0–1)
    std: float                           # spatial std of finite cells
    is_constant: bool                    # True when std < _MIN_STD
    is_spatially_meaningful: bool        # True when finite_ratio >= threshold AND not constant
    provenance: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def unavailable(source_name: str = "none", reason: str = "no_spatial_signal") -> "RasterEvidence":
        return RasterEvidence(
            array=None,
            source_name=source_name,
            source_reality="unavailable",
            grounding_class="unavailable",
            finite_ratio=0.0,
            std=0.0,
            is_constant=True,
            is_spatially_meaningful=False,
            provenance={"reason": reason},
        )


def assess_raster_evidence(
    array: Optional[np.ndarray],
    source_name: str,
    source_reality: str,
    grounding_class: str = "raster",
    provenance: Optional[Dict[str, Any]] = None,
) -> RasterEvidence:
    """
    Assess a candidate numpy array and return a RasterEvidence descriptor.

    Parameters
    ----------
    array:
        2-D float32 array.  May be None.
    source_name:
        Human-readable name of the source (e.g. "NDVI_CLEAN").
    source_reality:
        One of "real_raster", "raster_composite_proxy", "unavailable".
    grounding_class:
        Layer 10 grounding class string forwarded to surface provenance.
    provenance:
        Optional extra provenance dict.
    """
    if array is None:
        return RasterEvidence.unavailable(source_name, reason="array_is_none")

    if not isinstance(array, np.ndarray) or array.ndim != 2:
        return RasterEvidence.unavailable(source_name, reason="not_2d_array")

    finite_mask = np.isfinite(array)
    n_total = array.size
    n_finite = int(finite_mask.sum())
    finite_ratio = n_finite / max(1, n_total)

    if n_finite == 0:
        return RasterEvidence(
            array=array,
            source_name=source_name,
            source_reality=source_reality,
            grounding_class=grounding_class,
            finite_ratio=0.0,
            std=0.0,
            is_constant=True,
            is_spatially_meaningful=False,
            provenance={**(provenance or {}), "reason": "all_nan"},
        )

    finite_vals = array[finite_mask]
    std = float(np.std(finite_vals))
    is_constant = std < _MIN_STD
    is_meaningful = (finite_ratio >= _MIN_FINITE_RATIO) and (not is_constant)

    return RasterEvidence(
        array=array,
        source_name=source_name,
        source_reality=source_reality,
        grounding_class=grounding_class,
        finite_ratio=finite_ratio,
        std=std,
        is_constant=is_constant,
        is_spatially_meaningful=is_meaningful,
        provenance={
            **(provenance or {}),
            "finite_ratio": round(finite_ratio, 4),
            "std": round(std, 6),
        },
    )


def resolve_ndvi_evidence(
    base_surfaces: Optional[List[Any]],
    l10_input: Optional[Any],
    l1_data: Optional[Any],
    H: int,
    W: int,
) -> RasterEvidence:
    """
    Priority-ordered NDVI evidence resolver.

    Priority:
      1. Layer 05 ASMAE real/proxy raster maps
      2. Layer 1 raster_maps (NDVI_CLEAN, NDVI)
      3. raster_composites (NDVI_CLEAN, NDVI)
      4. RasterEvidence.unavailable

    A candidate is only accepted if it passes the spatially-meaningful test.
    Constant arrays (std < 0.005) are REJECTED regardless of source.
    """
    from layer10_sire.surfaces.grid_access import extract_surface_grid, resample_to

    _NDVI_NAMES_BASE = [
        "NDVI_CLEAN",
        "NDVI",
    ]

    # 1. Base surfaces (L05/L10 derived)
    if base_surfaces:
        base_dict = {}
        for s in base_surfaces:
            stype = getattr(s, "semantic_type", None)
            stype_val = getattr(stype, "value", str(stype)) if stype else ""
            base_dict[stype_val] = s
        for name in _NDVI_NAMES_BASE:
            surf = base_dict.get(name)
            if surf:
                arr = extract_surface_grid(surf)
                if arr is not None:
                    arr = resample_to(arr, (H, W), method="bilinear")
                    ev = assess_raster_evidence(
                        arr, name, "raster_composite_proxy",
                        grounding_class="SPATIAL_RASTER",
                        provenance={"layer": "base_surfaces"},
                    )
                    if ev.is_spatially_meaningful:
                        return ev

    # 2. Layer 1 raster maps
    if l1_data:
        rm = getattr(l1_data, "raster_maps", {}) or {}
        for name in ["NDVI_CLEAN", "NDVI", "ndvi_clean", "ndvi"]:
            if name in rm:
                arr = extract_surface_grid(rm[name])
                if arr is not None:
                    arr_np = np.asarray(arr, dtype=np.float32)
                    if arr_np.ndim == 2:
                        arr_np = resample_to(arr_np, (H, W), method="bilinear")
                        ev = assess_raster_evidence(
                            arr_np, f"l1_{name}", "raster_composite_proxy",
                            grounding_class="SPATIAL_RASTER",
                            provenance={"layer": "l1_raster_maps"},
                        )
                        if ev.is_spatially_meaningful:
                            return ev

    # 3. raster_composites from l10_input
    rc = {}
    if l10_input:
        rc = getattr(l10_input, "raster_composites", {}) or {}
    for name in ["NDVI_CLEAN", "NDVI"]:
        comp = rc.get(name) or {}
        vals = comp.get("values") or comp.get("pixel_array")
        if vals and isinstance(vals, list) and len(vals) > 0:
            arr_np = np.asarray(vals, dtype=np.float32)
            if arr_np.ndim == 2:
                arr_np = resample_to(arr_np, (H, W), method="bilinear")
                ev = assess_raster_evidence(
                    arr_np, f"composite_{name}", "raster_composite_proxy",
                    grounding_class="COMPOSITE_RASTER",
                    provenance={"layer": "raster_composites"},
                )
                if ev.is_spatially_meaningful:
                    return ev

    return RasterEvidence.unavailable("ndvi", reason="no_valid_ndvi_signal")
