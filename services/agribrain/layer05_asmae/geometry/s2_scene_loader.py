"""
Sentinel-2 Scene Loader for ASMAE.

Converts Layer 0 Sentinel-2 source packages into ASMAESceneRuntime objects.
Preserves per-scene CRS, transform, acquisition time, and masks.
Does NOT force a fixed grid — each scene keeps its native geometry.

Bands loaded:
  10m: B02 (Blue), B03 (Green), B04 (Red), B08 (NIR)
  20m: B05, B06, B07 (Red Edge), B8A, B11, B12 (SWIR)
  60m: B01 (Coastal), B09 (Water Vapour), B10 (Cirrus)

ASMAE uses B02-B08 as primary, B05-B8A for red-edge, B11-B12 for SWIR.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..schema import ASMAESceneRuntime
from ..scene_admission import scene_quality_admission
from .mask_builder import build_mask_set
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

# Sentinel-2 band resolution mapping
S2_BAND_RESOLUTION_M = {
    "B01": 60, "B02": 10, "B03": 10, "B04": 10,
    "B05": 20, "B06": 20, "B07": 20, "B08": 10,
    "B8A": 20, "B09": 60, "B10": 60,
    "B11": 20, "B12": 20,
}


def load_s2_scenes(
    s2_packages: List[Any],
    previous_acquisition_times: Optional[List[datetime]] = None,
) -> List[Dict[str, Any]]:
    """Convert Layer 0 Sentinel-2 packages into scene dicts.

    Args:
        s2_packages: List of Layer 0 S2 source packages (SimpleNamespace).
        previous_acquisition_times: Sorted list of acquisition times for
            temporal spacing computation.

    Returns:
        List of dicts containing:
            - "runtime": ASMAESceneRuntime
            - "quality": SceneQualityResult
            - "packets": raw packet data
    """
    results = []
    sorted_times = sorted(previous_acquisition_times or [])

    for pkg in s2_packages:
        try:
            result = _process_s2_package(pkg, sorted_times)
            if result is not None:
                results.append(result)
                # Update sorted times for spacing computation
                acq = result["runtime"].acquisition_time
                if acq not in sorted_times:
                    sorted_times.append(acq)
                    sorted_times.sort()
        except Exception as e:
            logger.warning("Failed to load S2 package: %s", e)

    return results


def _process_s2_package(
    candidate: Any,
    sorted_times: List[datetime],
) -> Optional[Dict[str, Any]]:
    """Process a single S2 candidate into a scene dict."""
    import os
    if candidate.reality in ["unavailable"]:
        if os.environ.get("ASMAE_TEST_OVERRIDE") != "true":
            logger.warning("S2 candidate is %s — skipping loader", candidate.reality)
            return None

    admitted, admission_reason, _ = scene_quality_admission(candidate)
    if not admitted:
        logger.warning("S2 candidate rejected by shared scene admission: %s", admission_reason)
        return None

    scene_id = candidate.scene_id or ""
    acq_dt = candidate.acquisition_datetime
    if acq_dt is None:
        logger.warning("S2 scene %s has no acquisition_datetime", scene_id)
        return None
    if not isinstance(acq_dt, datetime):
        try:
            acq_dt = datetime.fromisoformat(str(acq_dt)).replace(tzinfo=timezone.utc)
        except Exception:
            logger.warning("S2 scene %s: unparseable datetime %s", scene_id, acq_dt)
            return None

    crs = candidate.crs or "EPSG:4326"

    qa_metrics = candidate.qa_metrics or {}
    cloud_cover = qa_metrics.get("cloud_cover")
    data_status = qa_metrics.get("data_status", "observed")
    usable = qa_metrics.get("usable", True)
    quality_class = qa_metrics.get("quality_class", "good")
    valid_fraction = qa_metrics.get("valid_fraction", 1.0)
    
    scalar_obs = candidate.scalar_observations or {}
    ndvi_mean = scalar_obs.get("ndvi_mean")

    # Temporal spacing
    days_since_prev = None
    if sorted_times:
        for prev_time in reversed(sorted_times):
            if prev_time < acq_dt:
                delta = (acq_dt - prev_time).total_seconds() / 86400.0
                days_since_prev = delta
                break

    # ── Build ASMAESceneRuntime ──────────────────────────────────────
    import os
    import numpy as np
    from layer0.archive.raster_store import RasterStore
    raster_store = RasterStore()

    def normalize_band_key(key: str) -> str:
        k = key.lower().strip()
        if k in ("b04", "red"):
            return "B04"
        if k in ("b08", "nir"):
            return "B08"
        if k in ("b02", "blue"):
            return "B02"
        if k in ("b03", "green"):
            return "B03"
        if k in ("b05", "rededge1"):
            return "B05"
        if k in ("b06", "rededge2"):
            return "B06"
        if k in ("b07", "rededge3"):
            return "B07"
        if k in ("b8a", "b8a"):
            return "B8A"
        if k in ("b11", "swir1"):
            return "B11"
        if k in ("b12", "swir2"):
            return "B12"
        if k in ("scl", "qa"):
            return "SCL"
        if k in ('datamask', 'data_mask', 'data-mask'):
            return 'DATAMASK'
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
                if band == 'DATAMASK':
                    loaded_masks[band] = np.asarray(arr, dtype=np.float32)
                    continue
                if band in ["SCL"]:
                    loaded_masks[band] = np.asarray(arr, dtype=np.float32)
                else:
                    loaded_bands[band] = np.asarray(arr, dtype=np.float32)

    # Helper nearest-neighbor resampler
    def resample_array(arr: np.ndarray, target_shape: tuple[int, int]) -> np.ndarray:
        if arr.shape == target_shape:
            return arr
        h_in, w_in = arr.shape[:2]
        h_out, w_out = target_shape
        row_indices = np.clip((np.arange(h_out) * (h_in / h_out)).astype(np.int32), 0, h_in - 1)
        col_indices = np.clip((np.arange(w_out) * (w_in / w_out)).astype(np.int32), 0, w_in - 1)
        return arr[np.ix_(row_indices, col_indices)]

    # 2. Then load candidate.band_refs from RasterStore if not already loaded
    for b_name in ["B02", "B03", "B04", "B08", "B05", "B06", "B07", "B8A", "B11", "B12"]:
        if b_name not in loaded_bands:
            b_path = local_cache_refs.get(b_name)
            if b_path and os.path.exists(b_path):
                try:
                    loaded_bands[b_name] = raster_store.load_band(b_path)
                except Exception as e:
                    logger.warning("Failed to load band %s: %s", b_name, e)

    # Aggregate composite observations carry indices directly. They are
    # diagnostic proxy inputs, not fabricated reflectance bands.
    if candidate.reality == "raster_composite_proxy":
        for index_name in ("ndvi", "ndmi"):
            if index_name not in loaded_bands:
                index_path = local_cache_refs.get(index_name)
                if index_path and os.path.exists(index_path):
                    try:
                        loaded_bands[index_name] = raster_store.load_band(index_path)
                    except Exception as e:
                        logger.warning("Failed to load composite index %s: %s", index_name, e)

    for m_name in ["SCL"]:
        if m_name not in loaded_masks:
            m_path = local_cache_refs.get(m_name)
            if m_path and os.path.exists(m_path):
                try:
                    loaded_masks[m_name] = raster_store.load_band(m_path)
                except Exception as e:
                    logger.warning("Failed to load mask %s: %s", m_name, e)

    if 'DATAMASK' not in loaded_masks:
        datamask_path = local_cache_refs.get('DATAMASK')
        if datamask_path and os.path.exists(datamask_path):
            try:
                loaded_masks['DATAMASK'] = raster_store.load_band(datamask_path)
            except Exception as exc:
                logger.warning('Failed to load DATAMASK: %s', exc)

    # Establish target shape from 10m bands
    target_shape = None
    for b_name in ["B02", "B03", "B04", "B08"]:
        if b_name in loaded_bands:
            target_shape = loaded_bands[b_name].shape
            break
    if target_shape is None and loaded_bands:
        target_shape = next(iter(loaded_bands.values())).shape

    # Resample all loaded arrays to target shape
    if target_shape is not None:
        for b_name, arr in list(loaded_bands.items()):
            if arr.shape != target_shape:
                loaded_bands[b_name] = resample_array(arr, target_shape)
        for m_name, arr in list(loaded_masks.items()):
            if arr.shape != target_shape:
                loaded_masks[m_name] = resample_array(arr, target_shape)

    # Calculate NDVI and EVI dynamically if required bands present, otherwise degrade
    ndvi_arr = None
    evi_arr = None
    ndre_arr = None
    reip_arr = None
    ndmi_arr = None
    ndwi_arr = None
    bsi_arr = None
    nbr_arr = None
    eps = 1e-6

    feature_formula_versions = {}

    if "B04" in loaded_bands and "B08" in loaded_bands:
        b04 = loaded_bands["B04"]
        b08 = loaded_bands["B08"]
        ndvi_arr = (b08 - b04) / (b08 + b04 + eps)
        
        if "B02" in loaded_bands:
            b02 = loaded_bands["B02"]
            evi_arr = 2.5 * (b08 - b04) / (b08 + 6.0 * b04 - 7.5 * b02 + 1.0 + eps)

    # NDRE: requires B05 and (B06 or B07)
    if "B05" in loaded_bands:
        nir_for_ndre = loaded_bands.get("B06", loaded_bands.get("B07"))
        if nir_for_ndre is not None:
            ndre_arr = (nir_for_ndre - loaded_bands["B05"]) / (nir_for_ndre + loaded_bands["B05"] + eps)
            feature_formula_versions["NDRE"] = "B06_B05_v1" if "B06" in loaded_bands else "B07_B05_v1"

    # REIP: requires B05, B06, B07, B08
    if all(k in loaded_bands for k in ("B05", "B06", "B07", "B08")):
        reip_arr = 700.0 + 40.0 * (((loaded_bands["B05"] + loaded_bands["B08"]) / 2.0 - loaded_bands["B06"]) / (loaded_bands["B07"] - loaded_bands["B06"] + eps))
        feature_formula_versions["REIP"] = "reip_B05_B06_B07_B08_v1"

    # NDMI: requires B11, and (B8A or B08)
    if "B11" in loaded_bands:
        nir_for_ndmi = loaded_bands.get("B8A", loaded_bands.get("B08"))
        if nir_for_ndmi is not None:
            ndmi_arr = (nir_for_ndmi - loaded_bands["B11"]) / (nir_for_ndmi + loaded_bands["B11"] + eps)
            feature_formula_versions["NDMI"] = "B8A_B11_v1" if "B8A" in loaded_bands else "B08_B11_v1"

    # NDWI: McFeeters NDWI = (B03 - B08) / (B03 + B08)
    if "B03" in loaded_bands and "B08" in loaded_bands:
        ndwi_arr = (loaded_bands["B03"] - loaded_bands["B08"]) / (loaded_bands["B03"] + loaded_bands["B08"] + eps)
        feature_formula_versions["NDWI"] = "mcfeeters_B03_B08_v1"

    # BSI: requires B04, B08, B11, B02
    if all(k in loaded_bands for k in ("B04", "B08", "B11", "B02")):
        bsi_arr = ((loaded_bands["B11"] + loaded_bands["B04"]) - (loaded_bands["B08"] + loaded_bands["B02"])) / \
                  ((loaded_bands["B11"] + loaded_bands["B04"]) + (loaded_bands["B08"] + loaded_bands["B02"]) + eps)
        feature_formula_versions["BSI"] = "bsi_B04_B08_B11_B02_v1"

    # NBR: requires B12, and (B08 or B8A)
    if "B12" in loaded_bands:
        nir_for_nbr = loaded_bands.get("B08", loaded_bands.get("B8A"))
        if nir_for_nbr is not None:
            nbr_arr = (nir_for_nbr - loaded_bands["B12"]) / (nir_for_nbr + loaded_bands["B12"] + eps)
            feature_formula_versions["NBR"] = "B08_B12_v1" if "B08" in loaded_bands else "B8A_B12_v1"

    # Clip values to [-1.0, 1.0]
    if ndvi_arr is not None:
        ndvi_arr = np.clip(ndvi_arr, -1.0, 1.0)
    if evi_arr is not None:
        evi_arr = np.clip(evi_arr, -1.0, 1.0)
    if ndre_arr is not None:
        ndre_arr = np.clip(ndre_arr, -1.0, 1.0)
    if ndmi_arr is not None:
        ndmi_arr = np.clip(ndmi_arr, -1.0, 1.0)
    if ndwi_arr is not None:
        ndwi_arr = np.clip(ndwi_arr, -1.0, 1.0)
    if bsi_arr is not None:
        bsi_arr = np.clip(bsi_arr, -1.0, 1.0)
    if nbr_arr is not None:
        nbr_arr = np.clip(nbr_arr, -1.0, 1.0)

    bands: Dict[str, Any] = {}
    masks: Dict[str, Any] = {}

    # Store loaded arrays in bands dict
    for b_name, arr in loaded_bands.items():
        bands[b_name] = arr
    for m_name, arr in loaded_masks.items():
        masks[m_name] = arr

    if ndvi_arr is not None:
        bands["ndvi"] = ndvi_arr
    if evi_arr is not None:
        bands["evi"] = evi_arr
    if ndre_arr is not None:
        bands["ndre"] = ndre_arr
    if reip_arr is not None:
        bands["reip"] = reip_arr
    if ndmi_arr is not None:
        bands["ndmi"] = ndmi_arr
    if ndwi_arr is not None:
        bands["ndwi"] = ndwi_arr
    if bsi_arr is not None:
        bands["bsi"] = bsi_arr
    if nbr_arr is not None:
        bands["nbr"] = nbr_arr

    # Populate index means from scalar_obs as fallbacks if arrays are not loaded
    for key in ("ndvi_mean", "evi_mean", "ndmi_mean", "ndre_mean", "bsi_mean"):
        b_key = key.replace("_mean", "")
        if b_key not in bands:
            val = scalar_obs.get(key)
            if val is not None:
                bands[b_key] = val

    if target_shape is not None:
        declared_shape = (int(candidate.height or 0), int(candidate.width or 0))
        if all(declared_shape) and declared_shape != tuple(target_shape):
            logger.warning(
                "S2 scene %s: declared shape %s does not match raster shape %s",
                scene_id, declared_shape, tuple(target_shape),
            )
            return None
    width = int(target_shape[1]) if target_shape is not None else 0
    height = int(target_shape[0]) if target_shape is not None else 0
    if target_shape is None:
        # Mean-only evidence is plot-level and must not masquerade as a grid.
        width = 0
        height = 0

    # Reconstruct transform from candidate if available
    transform = candidate.transform or [10.0, 0.0, 0.0, 0.0, -10.0, 0.0]
    if not isinstance(transform, list) and not isinstance(transform, tuple):
        transform = [10.0, 0.0, 0.0, 0.0, -10.0, 0.0]

    # Never invent a grid for a mean-only or incomplete package.
    transform = list(candidate.transform or [])
    sun_angles = None  # Not yet available from L0

    runtime = ASMAESceneRuntime(
        scene_id=scene_id,
        sensor="S2",
        acquisition_time=acq_dt,
        crs=crs,
        transform=transform,
        width=width,
        height=height,
        bands=bands,
        masks=masks,
        sun_angles=sun_angles,
        cloud_fraction=float(cloud_cover) if cloud_cover is not None else None,
        qa_score=0.0,  # Computed below
        provenance_ref=f"s2_loader_{scene_id}",
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
    if (runtime.production_usable and runtime.product_binding != "exact_catalog_item") or (valid_fraction is not None and valid_fraction <= 0.0) or (cloud_cover is not None and cloud_cover >= 1.0):
        runtime.production_usable = False
        runtime.real_provider_product = False
        runtime.diagnostic_only = True

    # ── Compute Quality ──────────────────────────────────────────────
    quality = SceneQualityResult(scene_id=scene_id, sensor="S2")
    quality.clear_pixel_fraction = compute_clear_pixel_fraction(
        cloud_cover, valid_fraction,
    )
    quality.valid_polygon_coverage = compute_polygon_coverage(
        valid_fraction, usable,
    )
    quality.radiometric_quality = compute_radiometric_quality(
        data_status, quality_class,
    )
    quality.temporal_spacing_score = compute_temporal_spacing_score(
        days_since_prev, sensor="S2",
    )
    quality.metadata_completeness = compute_metadata_completeness(
        has_crs=bool(crs),
        has_transform=True,
        has_acquisition_time=True,
        has_sun_angles=False,
    )
    quality.sensor_specific_quality = compute_sensor_specific_quality(
        sensor="S2",
        cloud_cover=cloud_cover,
        ndvi_mean=ndvi_mean,
    )
    quality.compute()
    runtime.qa_score = quality.overall

    band_list = sorted(list(loaded_bands.keys())) if loaded_bands else ["B02", "B03", "B04", "B08"]

    return {
        "runtime": runtime,
        "quality": quality,
        "packets": [],
        "feature_formula_versions": feature_formula_versions,
        "metadata": {
            "band_list": band_list,
            "band_resolutions": {
                b: S2_BAND_RESOLUTION_M.get(b, 10) for b in band_list
            },
        },
    }
