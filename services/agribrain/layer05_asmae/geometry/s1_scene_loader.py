"""
Sentinel-1 Scene Loader for ASMAE.

Converts Layer 0 Sentinel-1 GRD source packages into ASMAESceneRuntime objects.
Preserves per-scene CRS, transform, and acquisition time.

Bands:
  VV — co-polarization (soil moisture, surface water)
  VH — cross-polarization (biomass, structure)
  RVI — radar vegetation index (derived)

SAR-specific metadata:
  - Incidence angle (affects backscatter interpretation)
  - Orbit direction (ascending/descending)
  - Surface wetness proxy
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..schema import ASMAESceneRuntime
from ..scene_admission import scene_quality_admission
from .scene_quality import (
    SceneQualityResult,
    compute_clear_pixel_fraction,
    compute_metadata_completeness,
    compute_polygon_coverage,
    compute_radiometric_quality,
    compute_sensor_specific_quality,
    compute_temporal_spacing_score,
)

logger = logging.getLogger(__name__)


def _normalized_backscatter_feature(values: Any, polarization: str, is_db: bool):
    """Map calibrated SAR backscatter to the forward-model [0, 1] domain.

    Provider rasters may be either sigma0 linear power or dB.  The EnKF and
    radiometric forward models operate on a bounded agricultural-backscatter
    feature, so raw provider units must never be compared to them directly.
    The ranges are intentionally broad Sentinel-1 agricultural envelopes; a
    value outside them is clipped and the raw calibrated band is still kept.
    """
    import numpy as np

    arr = np.asarray(values, dtype=np.float64)
    if is_db:
        db = arr
    else:
        db = 10.0 * np.log10(np.maximum(arr, 1e-10))
    low, high = (-25.0, 0.0) if polarization == "VV" else (-32.0, -5.0)
    return np.clip((db - low) / (high - low), 0.0, 1.0).astype(np.float32)


def load_s1_scenes(
    s1_packages: List[Any],
    previous_acquisition_times: Optional[List[datetime]] = None,
) -> List[Dict[str, Any]]:
    """Convert Layer 0 Sentinel-1 packages into scene dicts.

    Args:
        s1_packages: List of Layer 0 S1 source packages (SimpleNamespace).
        previous_acquisition_times: For temporal spacing computation.

    Returns:
        List of dicts with "runtime", "quality", "packets".
    """
    results = []
    sorted_times = sorted(previous_acquisition_times or [])

    for pkg in s1_packages:
        try:
            result = _process_s1_package(pkg, sorted_times)
            if result is not None:
                results.append(result)
                acq = result["runtime"].acquisition_time
                if acq not in sorted_times:
                    sorted_times.append(acq)
                    sorted_times.sort()
        except Exception as e:
            logger.warning("Failed to load S1 package: %s", e)

    return results


def _process_s1_package(
    candidate: Any,
    sorted_times: List[datetime],
) -> Optional[Dict[str, Any]]:
    """Process a single S1 candidate."""
    import os
    if candidate.reality in ["unavailable"]:
        if os.environ.get("ASMAE_TEST_OVERRIDE") != "true":
            return None

    admitted, admission_reason, _ = scene_quality_admission(candidate)
    if not admitted:
        logger.warning("S1 candidate rejected by shared scene admission: %s", admission_reason)
        return None

    scene_id = candidate.scene_id or ""
    acq_dt = candidate.acquisition_datetime
    if acq_dt is None:
        return None
    if not isinstance(acq_dt, datetime):
        try:
            acq_dt = datetime.fromisoformat(str(acq_dt)).replace(tzinfo=timezone.utc)
        except Exception:
            return None

    crs = candidate.crs or "EPSG:4326"

    qa_metrics = candidate.qa_metrics or {}
    data_status = qa_metrics.get("data_status", "observed")
    usable = qa_metrics.get("usable", True)
    quality_class = qa_metrics.get("quality_class", "good")
    valid_fraction = qa_metrics.get("valid_fraction", 1.0)
    orbit_direction = qa_metrics.get("orbit_direction")

    scalar_obs = candidate.scalar_observations or {}
    vv_db_mean = scalar_obs.get("vv_db_mean")
    vh_db_mean = scalar_obs.get("vh_db_mean")
    rvi_mean = scalar_obs.get("rvi_mean")
    surface_wetness = scalar_obs.get("surface_wetness_proxy_mean")

    # Temporal spacing
    days_since_prev = None
    if sorted_times:
        for prev_time in reversed(sorted_times):
            if prev_time < acq_dt:
                days_since_prev = (acq_dt - prev_time).total_seconds() / 86400.0
                break

    # Build bands dict
    import os
    import numpy as np
    from layer0.archive.raster_store import RasterStore
    raster_store = RasterStore()

    def normalize_band_key(key: str) -> str:
        k = key.lower().strip()
        if k in ("vv", "sar_vv"):
            return "VV"
        if k in ("vh", "sar_vh"):
            return "VH"
        if k in ("datamask", "data_mask", "data-mask"):
            return "DATAMASK"
        return key

    raw_cache_refs = {
        **dict(candidate.band_refs or {}),
        **dict(getattr(candidate, "mask_refs", {}) or {}),
    }
    local_cache_refs = {normalize_band_key(k): v for k, v in raw_cache_refs.items()}
    
    raw_band_arrays = getattr(candidate, "band_arrays", {}) or {}
    band_arrays = {normalize_band_key(k): v for k, v in raw_band_arrays.items()} if isinstance(raw_band_arrays, dict) else {}

    loaded_bands = {}
    loaded_masks = {}

    def is_2d_array(arr: Any) -> bool:
        try:
            a = np.asarray(arr)
            return a.ndim == 2
        except Exception:
            return False

    # 1. Prefer candidate.band_arrays if present
    if band_arrays:
        for band, arr in band_arrays.items():
            if is_2d_array(arr):
                if band == "DATAMASK":
                    loaded_masks[band] = np.asarray(arr, dtype=np.float32)
                else:
                    loaded_bands[band] = np.asarray(arr, dtype=np.float32)

    # 2. Then load candidate.band_refs from RasterStore if not already loaded
    for b_name in ["VV", "VH"]:
        if b_name not in loaded_bands:
            b_path = local_cache_refs.get(b_name)
            if b_path and os.path.exists(b_path):
                try:
                    loaded_bands[b_name] = raster_store.load_band(b_path)
                except Exception as e:
                    logger.warning("Failed to load S1 band %s: %s", b_name, e)

    datamask_path = local_cache_refs.get("DATAMASK")
    if datamask_path and os.path.exists(datamask_path):
        try:
            loaded_masks["DATAMASK"] = raster_store.load_band(datamask_path)
        except Exception as exc:
            logger.warning("Failed to load S1 DATAMASK: %s", exc)

    # Verify loaded bands share shape
    target_shape = None
    if "VV" in loaded_bands:
        target_shape = loaded_bands["VV"].shape
    elif "VH" in loaded_bands:
        target_shape = loaded_bands["VH"].shape

    if target_shape is not None:
        for b_name, arr in list(loaded_bands.items()):
            if arr.shape != target_shape:
                # Resample using nearest-neighbor
                h_in, w_in = arr.shape[:2]
                h_out, w_out = target_shape
                row_indices = np.clip((np.arange(h_out) * (h_in / h_out)).astype(np.int32), 0, h_in - 1)
                col_indices = np.clip((np.arange(w_out) * (w_in / w_out)).astype(np.int32), 0, w_in - 1)
                loaded_bands[b_name] = arr[np.ix_(row_indices, col_indices)]
        for mask_name, arr in list(loaded_masks.items()):
            if arr.shape != target_shape:
                h_in, w_in = arr.shape[:2]
                h_out, w_out = target_shape
                row_indices = np.clip((np.arange(h_out) * (h_in / h_out)).astype(np.int32), 0, h_in - 1)
                col_indices = np.clip((np.arange(w_out) * (w_in / w_out)).astype(np.int32), 0, w_in - 1)
                loaded_masks[mask_name] = arr[np.ix_(row_indices, col_indices)]

    # Compute RVI and a bounded cross-polarization fraction dynamically if
    # both bands exist.  Raw VV/VH is unbounded and cannot be compared with
    # the normalized SAR forward model.
    rvi_arr = None
    ratio_arr = None
    vv_feature_arr = None
    vh_feature_arr = None
    eps = 1e-6

    declared_units = {
        str(name).upper(): str(unit).strip().lower()
        for name, unit in dict(getattr(candidate, "band_units", {}) or {}).items()
    }

    def unit_is_db(polarization: str):
        unit = declared_units.get(polarization, "")
        if unit in {"db", "decibel", "decibels"}:
            return True
        if unit in {
            "linear_power", "linear_sigma0", "sigma0", "gamma0",
            "linear", "power",
        }:
            return False
        return None

    vv_is_db = unit_is_db("VV")
    vh_is_db = unit_is_db("VH")
    if "VV" in loaded_bands:
        if vv_is_db is not None:
            vv_feature_arr = _normalized_backscatter_feature(
                loaded_bands["VV"], "VV", vv_is_db,
            )
    if "VH" in loaded_bands:
        if vh_is_db is not None:
            vh_feature_arr = _normalized_backscatter_feature(
                loaded_bands["VH"], "VH", vh_is_db,
            )

    if "VV" in loaded_bands and "VH" in loaded_bands:
        vv = loaded_bands["VV"]
        vh = loaded_bands["VH"]

        if vv_is_db is not None and vh_is_db is not None:
            vv_lin = 10.0 ** (vv / 10.0) if vv_is_db else vv
            vh_lin = 10.0 ** (vh / 10.0) if vh_is_db else vh
            rvi_arr = (4.0 * vh_lin) / (vv_lin + vh_lin + eps)
            # VH / (VV + VH) is a bounded, monotonic representation of the
            # cross/co-polarization ratio and retains a stable unit contract.
            ratio_arr = vh_lin / (vv_lin + vh_lin + eps)
        else:
            logger.warning(
                "S1 scene %s: calibrated VV/VH units are missing; "
                "derived features are blocked", scene_id,
            )
    else:
        if local_cache_refs:
            logger.warning("S1 scene %s: required bands VV or VH missing — degrading scene", scene_id)

    bands: Dict[str, Any] = {}
    if "VV" in loaded_bands:
        # Uppercase bands are the calibrated provider measurements.
        bands["VV"] = loaded_bands["VV"]
        if vv_feature_arr is not None:
            bands["vv"] = vv_feature_arr
    if "VH" in loaded_bands:
        bands["VH"] = loaded_bands["VH"]
        if vh_feature_arr is not None:
            bands["vh"] = vh_feature_arr
    if rvi_arr is not None:
        bands["rvi"] = rvi_arr
    if ratio_arr is not None:
        bands["vv_vh_ratio"] = ratio_arr

    # Fallback to means if no arrays loaded
    if "vv" not in bands and vv_db_mean is not None:
        bands["vv"] = float(_normalized_backscatter_feature(
            [vv_db_mean], "VV", is_db=True,
        )[0])
    if "vh" not in bands and vh_db_mean is not None:
        bands["vh"] = float(_normalized_backscatter_feature(
            [vh_db_mean], "VH", is_db=True,
        )[0])
    if "rvi" not in bands and rvi_mean is not None:
        bands["rvi"] = rvi_mean
    if surface_wetness is not None:
        bands["surface_wetness_proxy"] = surface_wetness

    if target_shape is not None:
        declared_shape = (int(candidate.height or 0), int(candidate.width or 0))
        if all(declared_shape) and declared_shape != tuple(target_shape):
            logger.warning(
                "S1 scene %s: declared shape %s does not match raster shape %s",
                scene_id, declared_shape, tuple(target_shape),
            )
            return None
    width = int(target_shape[1]) if target_shape is not None else 0
    height = int(target_shape[0]) if target_shape is not None else 0

    transform = candidate.transform or [10.0, 0.0, 0.0, 0.0, -10.0, 0.0]
    if not isinstance(transform, list) and not isinstance(transform, tuple):
        transform = [10.0, 0.0, 0.0, 0.0, -10.0, 0.0]

    transform = list(candidate.transform or [])
    runtime = ASMAESceneRuntime(
        scene_id=scene_id,
        sensor="S1",
        acquisition_time=acq_dt,
        crs=crs,
        transform=transform,
        width=width,
        height=height,
        bands=bands,
        masks=loaded_masks,
        cloud_fraction=None,  # SAR is cloud-independent
        qa_score=0.0,
        provenance_ref=f"s1_loader_{scene_id}",
    )
    runtime.source_reality = getattr(candidate, "reality", "unknown")
    runtime.test_override = getattr(candidate, "test_override", False)
    runtime.production_usable = getattr(candidate, "production_usable", False)
    runtime.real_provider_product = getattr(candidate, "real_provider_product", False)
    runtime.diagnostic_only = getattr(candidate, "diagnostic_only", True)
    runtime.provider_product_id = getattr(candidate, "provider_product_id", None)
    runtime.catalog_item_id = getattr(candidate, "catalog_item_id", None)
    runtime.provider_tile_id = getattr(candidate, "provider_tile_id", None)
    runtime.provider_orbit_id = getattr(candidate, "provider_orbit_id", None)
    runtime.provider_orbit_pass = getattr(candidate, "provider_orbit_pass", None)
    runtime.product_binding = getattr(candidate, "product_binding", "unknown")
    runtime.binding_proof = dict(getattr(candidate, "binding_proof", {}) or {})
    if runtime.production_usable and runtime.product_binding != "exact_catalog_item":
        runtime.production_usable = False
        runtime.real_provider_product = False
        runtime.diagnostic_only = True
    units_contract_valid = all(
        value is not None
        for name, value in (("VV", vv_is_db), ("VH", vh_is_db))
        if name in loaded_bands
    )
    if loaded_bands and not units_contract_valid:
        runtime.production_usable = False
        runtime.diagnostic_only = True
    runtime.sar_units = {
        'VV': ('db' if vv_is_db is True else 'linear_sigma0' if vv_is_db is False else 'unknown'),
        'VH': ('db' if vh_is_db is True else 'linear_sigma0' if vh_is_db is False else 'unknown'),
        'vv': 'normalized_0_1',
        'vh': 'normalized_0_1',
    }

    # Quality
    quality = SceneQualityResult(scene_id=scene_id, sensor="S1")
    quality.clear_pixel_fraction = 1.0  # SAR is cloud-independent
    quality.valid_polygon_coverage = compute_polygon_coverage(
        valid_fraction, usable,
    )
    quality.radiometric_quality = compute_radiometric_quality(
        data_status, quality_class,
    )
    quality.temporal_spacing_score = compute_temporal_spacing_score(
        days_since_prev, sensor="S1",
    )
    quality.metadata_completeness = compute_metadata_completeness(
        has_crs=bool(crs),
        has_transform=True,
        has_acquisition_time=True,
        has_incidence_angle=False,
    )
    quality.sensor_specific_quality = compute_sensor_specific_quality(
        sensor="S1",
        vv_db_mean=vv_db_mean,
        vh_db_mean=vh_db_mean,
    )
    quality.compute()
    runtime.qa_score = quality.overall

    return {
        "runtime": runtime,
        "quality": quality,
        "packets": [],
        "metadata": {
            "band_list": ["VV", "VH"],
            "orbit_direction": orbit_direction,
            "provider_backscatter_units": dict(runtime.sar_units),
            "units_contract_valid": units_contract_valid,
            "assimilation_feature_contract": "sar_normalized_backscatter_v1",
            "sar_ratio_definition": "vh_linear_over_vv_plus_vh",
        },
    }
