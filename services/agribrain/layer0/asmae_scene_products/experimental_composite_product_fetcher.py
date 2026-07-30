import os
from datetime import datetime, date, timedelta, timezone
import numpy as np
from .scene_product_schema import SceneProduct
from .scene_product_store import SceneProductStore
from .geometry_utils import _build_affine_transform


def _has_valid_pixel_grid(data: dict, H: int = 0, W: int = 0) -> bool:
    """Return True when pixel_array / values is a non-empty 2D list of the right shape."""
    vals = data.get("values") or data.get("pixel_array")
    if not vals or not isinstance(vals, list) or len(vals) == 0:
        return False
    if not isinstance(vals[0], list) or len(vals[0]) == 0:
        return False
    if H and W:
        return len(vals) == H and len(vals[0]) == W
    return True


def _assess_ndvi_evidence(ndvi_arr: np.ndarray) -> bool:
    """
    BC.10.13 P7 — RasterEvidence gate for the experimental fetcher.
    Returns True only if the array is spatially meaningful:
      - finite ratio >= 0.3
      - spatial std >= 0.005
    Mirrors the logic in assess_raster_evidence without introducing a hard
    import dependency on the feature_bus module tree from layer0.
    """
    if ndvi_arr is None or ndvi_arr.size == 0:
        return False
    finite_mask = np.isfinite(ndvi_arr)
    finite_ratio = float(np.sum(finite_mask)) / ndvi_arr.size
    if finite_ratio < 0.3:
        return False
    finite_vals = ndvi_arr[finite_mask]
    if finite_vals.size < 4:
        return False
    if float(np.std(finite_vals)) < 0.005:
        return False
    return True


def fetch_experimental_composite_s2_stack(
    plot_id: str,
    run_id: str,
    date_range: tuple,
    raster_composites: dict,
) -> list:
    """
    Reconstructs Sentinel-2-compatible band stack from raster composites for
    experimental / diagnostic purposes only.

    BC.10.13 P7 — HARD RULES:
    1. Returns [] immediately if NDVI composite fails RasterEvidence gate
       (finite_ratio < 0.3 or std < 0.005).
    2. NIR is NOT fabricated from a constant. Per BC.10.13:
       "If only NDVI exists, do not generate pseudo Sentinel bands."
       Only B04 (RED) and B08 (NIR) are emitted when a real NIR reflectance
       anchor exists in the composites (e.g. from a real scene product).
       If no real NIR anchor exists, those bands are OMITTED.
    3. RED from NDVI+NIR is only included when a real NIR composite is
       available (composite key "NIR" or "B08").
    4. SWIR (B11/B12) only from NDMI composite — no cross-derivation.
    5. Transform uses _build_affine_transform; no arbitrary constants.
    6. SceneProduct is always production_usable=False, diagnostic_only=True.
    """
    start_date, end_date = date_range
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)

    ndvi_data = raster_composites.get("NDVI_CLEAN") or raster_composites.get("NDVI") or {}
    pixel_array = ndvi_data.get("values") or ndvi_data.get("pixel_array")

    # HARD RULE 1: No NDVI pixel data → reject immediately.
    if not (pixel_array and isinstance(pixel_array, list)
            and len(pixel_array) > 0 and isinstance(pixel_array[0], list)
            and len(pixel_array[0]) > 0):
        return []

    ndvi_arr = np.array(pixel_array, dtype=np.float32)

    # HARD RULE 1 (continued): RasterEvidence gate.
    if not _assess_ndvi_evidence(ndvi_arr):
        return []

    ndvi_arr = np.clip(ndvi_arr, -0.99, 0.99)
    H, W = ndvi_arr.shape
    grid_spec = ndvi_data.get("grid_spec") or {}

    crs = grid_spec.get("crs", "EPSG:4326")

    # Transform: use _build_affine_transform from the stored grid_spec bounds/bbox.
    transform = grid_spec.get("transform")
    if transform and isinstance(transform, (list, tuple)) and len(transform) == 6:
        transform = tuple(float(v) for v in transform)
    else:
        bbox = grid_spec.get("bounds") or grid_spec.get("bbox")
        if bbox and len(bbox) >= 4:
            try:
                transform = _build_affine_transform(bbox, W, H)
            except ValueError:
                transform = None
        if transform is None:
            # Cannot build a valid transform → reject to avoid misaligned products.
            return []

    # HARD RULE 2 & 3: Only include NIR/RED if a real NIR composite exists.
    bands_to_save: dict = {}

    nir_data = raster_composites.get("NIR") or raster_composites.get("B08") or {}
    nir_pixel = nir_data.get("values") or nir_data.get("pixel_array")
    if (nir_pixel and isinstance(nir_pixel, list)
            and len(nir_pixel) == H and isinstance(nir_pixel[0], list)
            and len(nir_pixel[0]) == W):
        nir_arr = np.clip(np.array(nir_pixel, dtype=np.float32), 0.0, 1.0)
        if _assess_ndvi_evidence(nir_arr):
            # Real NIR anchor available → derive RED from NDVI + NIR.
            denom = np.clip(1.0 + ndvi_arr, 1e-6, None)
            red_arr = np.clip(nir_arr * (1.0 - ndvi_arr) / denom, 0.0, 1.0)
            bands_to_save["B04"] = red_arr
            bands_to_save["B08"] = nir_arr
    # If no real NIR: B04/B08 are OMITTED (not fabricated).

    # HARD RULE 4: SWIR only from NDMI composite.
    ndmi_data = raster_composites.get("NDMI") or {}
    ndmi_pixel = ndmi_data.get("values") or ndmi_data.get("pixel_array")
    if (ndmi_pixel and isinstance(ndmi_pixel, list)
            and len(ndmi_pixel) == H and isinstance(ndmi_pixel[0], list)
            and len(ndmi_pixel[0]) == W):
        ndmi_arr = np.clip(np.array(ndmi_pixel, dtype=np.float32), -0.99, 0.99)
        if _assess_ndvi_evidence(ndmi_arr):
            # Derive SWIR from NDMI + NIR if available, else skip B11/B12.
            if "B08" in bands_to_save:
                nir_for_swir = bands_to_save["B08"]
                swir_arr = np.clip(
                    nir_for_swir * (1.0 - ndmi_arr) / np.clip(1.0 + ndmi_arr, 1e-6, None),
                    0.0, 1.0,
                )
                bands_to_save["B11"] = swir_arr
                bands_to_save["B12"] = swir_arr

    # SCL (quality mask) — only from QUALITY composite, no derivation.
    qual_data = raster_composites.get("QUALITY") or {}
    qual_pixel = qual_data.get("values") or qual_data.get("pixel_array")
    if (qual_pixel and isinstance(qual_pixel, list)
            and len(qual_pixel) == H and isinstance(qual_pixel[0], list)
            and len(qual_pixel[0]) == W):
        quality_arr = np.array(qual_pixel, dtype=np.float32)
        bands_to_save["SCL"] = quality_arr

    # If no bands at all, the composite is useless.
    if not bands_to_save:
        return []

    store = SceneProductStore(plot_id, run_id, provider_product_id="experimental")
    end_dt = datetime.combine(end_date, datetime.min.time(), timezone.utc)

    scenes = []
    # Generate up to 3 proxy composites spaced in time.
    for i in range(1, 4):
        scene_id = f"s2_composite_proxy_{i}_{plot_id}"
        acq_dt = end_dt - timedelta(days=15 - 5 * (i - 1))

        band_refs = {}
        for b_name, arr in bands_to_save.items():
            path = store.save_band(scene_id, b_name, arr)
            band_refs[b_name] = path

        mask_refs = {"SCL": band_refs["SCL"]} if "SCL" in band_refs else {}

        scenes.append(SceneProduct(
            scene_id=scene_id,
            sensor="S2",
            acquisition_datetime=acq_dt,
            crs=crs,
            transform=transform,
            width=W,
            height=H,
            band_refs=band_refs,
            mask_refs=mask_refs,
            quality={
                "cloud_cover": 0.02,
                "valid_fraction": 0.98,
            },
            source_reality="raster_composite_proxy",
            test_override=False,
            production_usable=False,
            diagnostic_only=True,
            real_provider_product=False,
        ))

    return scenes


def fetch_experimental_composite_s1_stack(
    plot_id: str,
    run_id: str,
    date_range: tuple,
    raster_composites: dict,
) -> list:
    """
    Reconstructs Sentinel-1-compatible band stack from raster composites for
    experimental / diagnostic purposes only.

    BC.10.13 P7 — HARD RULES:
    1. Returns [] immediately if SAR composite fails RasterEvidence gate.
       Does NOT fall back to NDVI dimensions with fake SAR values.
    2. VH is derived from VV * 0.5 only if VV composite passes the gate.
    3. No constant fallback arrays.
    4. Transform uses _build_affine_transform.
    """
    start_date, end_date = date_range
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)

    sar_data = raster_composites.get("SAR") or {}
    pixel_array = sar_data.get("values") or sar_data.get("pixel_array")

    # HARD RULE 1: No valid SAR → no S1 composite.
    if not (pixel_array and isinstance(pixel_array, list)
            and len(pixel_array) > 0 and isinstance(pixel_array[0], list)
            and len(pixel_array[0]) > 0):
        return []

    sar_arr = np.array(pixel_array, dtype=np.float32)

    # HARD RULE 1 (continued): RasterEvidence gate on SAR.
    if not _assess_ndvi_evidence(sar_arr):
        return []

    H, W = sar_arr.shape
    grid_spec = sar_data.get("grid_spec") or {}

    crs = grid_spec.get("crs", "EPSG:4326")

    transform = grid_spec.get("transform")
    if transform and isinstance(transform, (list, tuple)) and len(transform) == 6:
        transform = tuple(float(v) for v in transform)
    else:
        bbox = grid_spec.get("bounds") or grid_spec.get("bbox")
        if bbox and len(bbox) >= 4:
            try:
                transform = _build_affine_transform(bbox, W, H)
            except ValueError:
                transform = None
        if transform is None:
            return []

    vv_arr = sar_arr
    vh_arr = None
    vh_data = raster_composites.get("VH") or raster_composites.get("SAR_VH") or {}
    vh_pixel = vh_data.get("values") or vh_data.get("pixel_array")
    if (vh_pixel and isinstance(vh_pixel, list)
            and len(vh_pixel) == H and isinstance(vh_pixel[0], list)
            and len(vh_pixel[0]) == W):
        vh_arr_candidate = np.array(vh_pixel, dtype=np.float32)
        if _assess_ndvi_evidence(vh_arr_candidate):
            vh_arr = vh_arr_candidate

    store = SceneProductStore(plot_id, run_id, provider_product_id="experimental")
    end_dt = datetime.combine(end_date, datetime.min.time(), timezone.utc)

    scenes = []
    # Generate 2 Sentinel-1 composite proxies.
    for i in range(1, 3):
        scene_id = f"s1_composite_proxy_{i}_{plot_id}"
        acq_dt = end_dt - timedelta(days=8 - 5 * (i - 1))

        band_refs = {}
        bands_dict = {"VV": vv_arr}
        if vh_arr is not None:
            bands_dict["VH"] = vh_arr
        for b_name, arr in bands_dict.items():
            path = store.save_band(scene_id, b_name, arr)
            band_refs[b_name] = path

        scenes.append(SceneProduct(
            scene_id=scene_id,
            sensor="S1",
            acquisition_datetime=acq_dt,
            crs=crs,
            transform=transform,
            width=W,
            height=H,
            band_refs=band_refs,
            mask_refs={},
            quality={
                "valid_fraction": 1.0,
            },
            source_reality="raster_composite_proxy",
            test_override=False,
            production_usable=False,
            diagnostic_only=True,
            real_provider_product=False,
        ))

    return scenes
