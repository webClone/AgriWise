"""
V79B: Per-pixel observation extraction from raster scenes.

Replaces scalar mean observations with full pixel-space vectors.
Used by EnKF (P0-3) and radiometric consistency (P0-4).

For real raster scenes:
  - Extract 2D band arrays
  - Compute per-pixel vegetation indices
  - Return flattened pixel observation vectors

For mean-only scenes:
  - Fall back to scalar value repeated (flagged as mean-level)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _canonical_band_mapping(scene: Any) -> Dict[str, Any]:
    mapping: Dict[str, Any] = {}
    for name, value in dict(getattr(scene, 'bands', {}) or {}).items():
        key = str(name).strip()
        upper = key.upper()
        if (
            upper == 'EXPERIMENTAL_VISUAL_CANOPY_HIGHRES'
            or upper.startswith('ASMAE_COMPOSITE_')
            or upper.startswith('FALLBACK_')
        ):
            logger.warning('Circular input band %s rejected from ASMAE pipeline', key)
            continue
        mapping[key] = value
        mapping.setdefault(upper, value)
        mapping.setdefault(key.lower(), value)
    return mapping


def _numeric_grid(value: Any) -> Optional[Any]:
    try:
        import numpy as np

        array = np.asarray(value, dtype=float)
        if array.ndim in (0, 1, 2) and array.size:
            return array
    except Exception:
        return None
    return None


def _first_grid(bands: Dict[str, Any], names: Tuple[str, ...]) -> Optional[Any]:
    for name in names:
        if name in bands:
            array = _numeric_grid(bands[name])
            if array is not None:
                return array
    return None


def _ratio_index(left: Any, right: Any) -> Optional[Any]:
    import numpy as np

    if left is None or right is None or np.shape(left) != np.shape(right):
        return None
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    denominator = left + right
    result = np.full(left.shape, np.nan, dtype=float)
    valid = np.isfinite(left) & np.isfinite(right) & (np.abs(denominator) > 1e-10)
    np.divide(left - right, denominator, out=result, where=valid)
    return result


def extract_pixel_observations(scene: Any) -> Dict[str, 'PixelObservation']:
    import numpy as np

    from ..geometry.support_contract import build_scene_valid_support, feature_support

    width = int(getattr(scene, 'width', 0) or 0)
    height = int(getattr(scene, 'height', 0) or 0)
    if width > 0 and height > 0 and getattr(scene, 'valid_support', None) is None:
        build_scene_valid_support(scene)

    bands = _canonical_band_mapping(scene)
    result: Dict[str, PixelObservation] = {}

    def emit(name: str, values: Any) -> None:
        if values is None:
            return
        array = np.asarray(values, dtype=float)
        if not array.size:
            return
        support = feature_support(scene, array)
        result[name] = PixelObservation(
            values=array.reshape(-1).astype(float).tolist(),
            is_per_pixel=bool(array.ndim == 2 and array.size > 1),
            n_pixels=int(array.size),
            valid_mask=support.reshape(-1).astype(bool).tolist(),
        )

    red = _first_grid(bands, ('B04', 'B4'))
    nir = _first_grid(bands, ('B08', 'B8'))
    red_edge = _first_grid(bands, ('B05', 'B5'))
    ndre_nir = _first_grid(bands, ('B06', 'B6', 'B07', 'B7'))
    swir = _first_grid(bands, ('B11',))
    narrow_nir = _first_grid(bands, ('B8A', 'B08', 'B8'))

    swir2 = _first_grid(bands, ('B12',))

    emit('ndvi', _ratio_index(nir, red))
    emit('ndre', _ratio_index(ndre_nir, red_edge))
    emit('ndmi', _ratio_index(narrow_nir, swir))
    if swir is not None and swir2 is not None:
        emit('ndsi', _ratio_index(swir, swir2))
    if ndre_nir is not None and red_edge is not None:
        emit('phenology_index', _ratio_index(ndre_nir, red_edge))

    if 'ndvi' in result and 'ndmi' in result:
        ndvi_arr = np.asarray(result['ndvi'].values, dtype=float)
        ndmi_arr = np.asarray(result['ndmi'].values, dtype=float)
        cwsi_arr = np.clip(1.0 - (ndmi_arr + 0.2) / np.maximum(ndvi_arr, 0.05), 0.0, 1.0)
        if result['ndvi'].is_per_pixel and width > 0 and height > 0:
            emit('cwsi', cwsi_arr.reshape(height, width))
        else:
            emit('cwsi', cwsi_arr)

    if 'ndvi' in result and result['ndvi'].is_per_pixel and width > 2 and height > 2:
        try:
            from scipy.ndimage import uniform_filter
            ndvi_2d = np.asarray(result['ndvi'].values, dtype=float).reshape(height, width)
            local_mean = uniform_filter(ndvi_2d, size=3, mode='reflect')
            local_sq_mean = uniform_filter(ndvi_2d**2, size=3, mode='reflect')
            local_std = np.sqrt(np.maximum(0.0, local_sq_mean - local_mean**2))
            biotic_risk = np.clip(local_std * 3.0, 0.0, 1.0)
            emit('biotic_anomaly', biotic_risk)
        except Exception:
            pass

    precomputed = {
        'ndvi': ('NDVI', 'ndvi'),
        'evi': ('EVI', 'evi'),
        'ndre': ('NDRE', 'ndre'),
        'ndmi': ('NDMI', 'ndmi'),
        'ndwi': ('NDWI', 'ndwi'),
        'bsi': ('BSI', 'bsi'),
        'nbr': ('NBR', 'nbr'),
        'ndsi': ('NDSI', 'ndsi', 'salinity_index'),
        'cwsi': ('CWSI', 'cwsi', 'thermal_stress_proxy'),
        'phenology_index': ('PHENOLOGY_INDEX', 'phenology_index', 'crop_stage_proxy'),
        'stress_memory_index': ('STRESS_MEMORY', 'stress_memory_index', 'stress_memory'),
        'biotic_anomaly': ('BIOTIC_ANOMALY', 'biotic_anomaly', 'biotic_risk'),
        # Assimilation forward models operate on the loader's bounded
        # normalized features. Raw calibrated provider bands remain available
        # under uppercase names for explicitly unit-aware physics experts.
        'sar_vv': ('sar_vv', 'vv'),
        'sar_vh': ('sar_vh', 'vh'),
        'sar_ratio': ('VV_VH_RATIO', 'sar_ratio', 'vv_vh_ratio', 'ratio'),
        'sar_wetness_proxy': (
            'SAR_WETNESS_PROXY', 'sar_wetness_proxy', 'surface_wetness_proxy',
        ),
        'delta_sar': ('DELTA_SAR', 'delta_sar'),
    }
    for name, candidates in precomputed.items():
        if name not in result:
            emit(name, _first_grid(bands, candidates))

    if 'sar_vh' in result and 'ndvi' in result and 'stress_memory_index' not in result:
        vh_arr = np.asarray(result['sar_vh'].values, dtype=float)
        ndvi_arr = np.asarray(result['ndvi'].values, dtype=float)
        if vh_arr.shape == ndvi_arr.shape:
            divergence = np.clip(np.maximum(0.0, vh_arr - ndvi_arr), 0.0, 1.0)
            if result['ndvi'].is_per_pixel and width > 0 and height > 0:
                emit('stress_memory_index', divergence.reshape(height, width))
            else:
                emit('stress_memory_index', divergence)
    elif 'stress_memory_index' not in result and 'ndvi' in result and 'cwsi' in result:
        ndvi_arr = np.asarray(result['ndvi'].values, dtype=float)
        cwsi_arr = np.asarray(result['cwsi'].values, dtype=float)
        mem = np.clip(cwsi_arr * np.clip(1.0 - ndvi_arr, 0.1, 0.95), 0.0, 1.0)
        if result['ndvi'].is_per_pixel and width > 0 and height > 0:
            emit('stress_memory_index', mem.reshape(height, width))
        else:
            emit('stress_memory_index', mem)

    return result


class PixelObservation:
    """Per-pixel observation container."""

    __slots__ = ("values", "is_per_pixel", "n_pixels", "valid_mask")

    def __init__(self, values: List[float], is_per_pixel: bool,
                 n_pixels: int, valid_mask: List[bool]):
        self.values = values
        self.is_per_pixel = is_per_pixel
        self.n_pixels = n_pixels
        self.valid_mask = valid_mask

    @property
    def mean(self) -> float:
        """Scalar mean of valid pixels."""
        import math

        valid_vals = [
            float(v) for v, m in zip(self.values, self.valid_mask)
            if m and math.isfinite(float(v))
        ]
        return sum(valid_vals) / len(valid_vals) if valid_vals else float('nan')

    @property
    def n_valid(self) -> int:
        return sum(self.valid_mask)
