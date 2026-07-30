"""
ASMAE Scene Coregistration.

Aligns multi-temporal scenes to a common reference frame. This is
critical for the H_t operator — sub-pixel mis-registration between
scenes creates false shift diversity that defeats super-resolution.

Implements:
  1. Phase correlation for sub-pixel shift estimation
  2. Same-tile reference alignment
  3. Edge/texture matching (simplified gradient correlation)
  4. Bad-scene rejection (high residual shift variance)
  5. Shift cluster classification
  6. Registration uncertainty estimation

Pure-Python implementation using only standard library math.
Full FFT-based phase correlation would require numpy — when available,
it is used automatically. Otherwise, falls back to gradient correlation.
"""

from __future__ import annotations

import hashlib
import math
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .spatial_reference import affine_from_gdal, crs_is_projected_metre, pixel_size_xy

logger = logging.getLogger(__name__)


@dataclass
class CoregistrationResult:
    """Result of coregistering a scene to the reference frame.

    Shift values are in meters (sub-pixel).
    """
    scene_id: str
    reference_scene_id: str

    # Estimated shift (scene → reference)
    shift_x_m: float = 0.0
    shift_y_m: float = 0.0

    # Uncertainty
    shift_uncertainty_m: float = 0.0
    confidence: float = 0.0   # 0-1, higher = more reliable

    # Quality flags
    method: str = "identity"    # identity | gradient | phase | manual
    accepted: bool = True
    rejection_reason: str = ""

    # Diagnostics
    peak_ratio: float = 0.0    # Phase correlation peak sharpness
    residual_rms: float = 0.0  # RMS of tie-point residuals

    def shift_magnitude_m(self) -> float:
        return math.sqrt(self.shift_x_m ** 2 + self.shift_y_m ** 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "reference": self.reference_scene_id,
            "shift_x_m": round(self.shift_x_m, 3),
            "shift_y_m": round(self.shift_y_m, 3),
            "shift_mag_m": round(self.shift_magnitude_m(), 3),
            "uncertainty_m": round(self.shift_uncertainty_m, 3),
            "confidence": round(self.confidence, 4),
            "method": self.method,
            "accepted": self.accepted,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class ShiftCluster:
    """A cluster of similar registration shifts.

    If multiple scenes have similar shifts, they likely share the same
    orbital track / tile alignment. Outlier scenes may have genuine
    different geometry or registration errors.
    """
    cluster_id: int
    member_scene_ids: List[str] = field(default_factory=list)
    mean_shift_x_m: float = 0.0
    mean_shift_y_m: float = 0.0
    std_shift_m: float = 0.0
    is_primary: bool = False   # Largest cluster


# ── Coregistration Engine ────────────────────────────────────────────────────

# Maximum acceptable shift before rejection (meters)
MAX_SHIFT_THRESHOLD_M = 15.0

# Maximum acceptable uncertainty (meters)
MAX_UNCERTAINTY_M = 10.0


def _legacy_coregister_scene_to_reference(
    scene: Any,
    reference: Any,
    method: str = "auto",
) -> CoregistrationResult:
    """Estimate registration shift between a scene and a reference.

    When pixel arrays are not available (current L0 provides means only),
    falls back to metadata-based alignment:
      - Same CRS → zero shift (identity)
      - Different CRS → coordinate transformation offset

    Args:
        scene: ASMAESceneRuntime for the target scene.
        reference: ASMAESceneRuntime for the reference scene.
        method: "auto", "identity", "gradient", "phase".

    Returns:
        CoregistrationResult with estimated shift.
    """
    result = CoregistrationResult(
        scene_id=scene.scene_id,
        reference_scene_id=reference.scene_id,
    )

    # ── Same-CRS fast path ───────────────────────────────────────────
    if scene.crs == reference.crs:
        # Same CRS: estimate shift from transform difference
        shift_x, shift_y = _shift_from_transforms(
            scene.transform, reference.transform,
        )
        result.shift_x_m = shift_x
        result.shift_y_m = shift_y
        result.method = "transform_diff"
        result.confidence = 0.9
        result.shift_uncertainty_m = 1.0  # ~1m from transform precision

    else:
        # Different CRS: cannot align without reprojection
        # Mark as identity with lower confidence
        result.method = "identity"
        result.confidence = 0.5
        result.shift_uncertainty_m = 5.0

    # ── Rejection checks ─────────────────────────────────────────────
    mag = result.shift_magnitude_m()
    if mag > MAX_SHIFT_THRESHOLD_M:
        result.accepted = False
        result.rejection_reason = (
            f"Shift magnitude {mag:.1f}m exceeds threshold "
            f"{MAX_SHIFT_THRESHOLD_M}m"
        )
        result.confidence = max(0.0, result.confidence - 0.3)

    if result.shift_uncertainty_m > MAX_UNCERTAINTY_M:
        result.accepted = False
        result.rejection_reason = (
            f"Uncertainty {result.shift_uncertainty_m:.1f}m exceeds "
            f"{MAX_UNCERTAINTY_M}m"
        )

    return result


def _common_registration_band(scene: Any, reference: Any) -> Tuple[Optional[Any], Optional[Any], str]:
    import numpy as np

    scene_bands = dict(getattr(scene, 'bands', {}) or {})
    reference_bands = dict(getattr(reference, 'bands', {}) or {})
    preferred = ('NDVI', 'B08', 'B04', 'NDRE', 'VV', 'VH', 'ndvi', 'vv', 'vh')
    common = list(dict.fromkeys([*preferred, *scene_bands.keys()]))
    for name in common:
        if name not in scene_bands or name not in reference_bands:
            continue
        moving = np.asarray(scene_bands[name])
        fixed = np.asarray(reference_bands[name])
        if moving.ndim == 2 and fixed.ndim == 2 and moving.size and fixed.size:
            return moving, fixed, str(name)
    return None, None, ''


def _warp_to_reference_grid(values: Any, scene: Any, reference: Any) -> Any:
    import numpy as np
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    destination = np.full(
        (int(reference.height), int(reference.width)),
        np.nan,
        dtype=np.float32,
    )
    reproject(
        source=np.asarray(values, dtype=np.float32),
        destination=destination,
        src_transform=affine_from_gdal(scene.transform),
        src_crs=scene.crs,
        dst_transform=affine_from_gdal(reference.transform),
        dst_crs=reference.crs,
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )
    return destination


def _subpixel_peak_offset(left: float, centre: float, right: float) -> float:
    denominator = left - 2.0 * centre + right
    if abs(denominator) < 1e-12:
        return 0.0
    return max(-0.5, min(0.5, 0.5 * (left - right) / denominator))


def _phase_registration(moving: Any, fixed: Any) -> Tuple[float, float, float, float]:
    import numpy as np

    moving = np.asarray(moving, dtype=float)
    fixed = np.asarray(fixed, dtype=float)
    valid = np.isfinite(moving) & np.isfinite(fixed)
    if int(np.count_nonzero(valid)) < max(64, int(valid.size * 0.05)):
        raise ValueError('insufficient_common_image_support')

    moving_work = np.where(valid, moving, np.nan)
    fixed_work = np.where(valid, fixed, np.nan)
    moving_work = np.where(valid, moving_work - np.nanmean(moving_work), 0.0)
    fixed_work = np.where(valid, fixed_work - np.nanmean(fixed_work), 0.0)

    # Gradients make the registration less sensitive to seasonal radiometry.
    moving_y, moving_x = np.gradient(moving_work)
    fixed_y, fixed_x = np.gradient(fixed_work)
    moving_work = np.hypot(moving_x, moving_y)
    fixed_work = np.hypot(fixed_x, fixed_y)
    moving_work -= float(np.mean(moving_work))
    fixed_work -= float(np.mean(fixed_work))

    window = np.outer(np.hanning(fixed.shape[0]), np.hanning(fixed.shape[1]))
    moving_fft = np.fft.fft2(moving_work * window)
    fixed_fft = np.fft.fft2(fixed_work * window)
    cross_power = fixed_fft * np.conj(moving_fft)
    magnitude = np.abs(cross_power)
    cross_power /= np.where(magnitude > 1e-12, magnitude, 1.0)
    correlation = np.abs(np.fft.ifft2(cross_power))
    peak_index = np.unravel_index(int(np.argmax(correlation)), correlation.shape)
    peak_value = float(correlation[peak_index])

    excluded = correlation.copy()
    row, col = int(peak_index[0]), int(peak_index[1])
    excluded[max(0, row - 1):row + 2, max(0, col - 1):col + 2] = 0.0
    second = float(np.max(excluded)) if excluded.size else 0.0
    peak_ratio = peak_value / max(second, 1e-12)

    row_offset = _subpixel_peak_offset(
        float(correlation[(row - 1) % correlation.shape[0], col]),
        peak_value,
        float(correlation[(row + 1) % correlation.shape[0], col]),
    )
    col_offset = _subpixel_peak_offset(
        float(correlation[row, (col - 1) % correlation.shape[1]]),
        peak_value,
        float(correlation[row, (col + 1) % correlation.shape[1]]),
    )
    row_shift = float(row) + row_offset
    col_shift = float(col) + col_offset
    if row_shift > correlation.shape[0] / 2.0:
        row_shift -= correlation.shape[0]
    if col_shift > correlation.shape[1] / 2.0:
        col_shift -= correlation.shape[1]
    confidence = max(0.0, min(1.0, (peak_ratio - 1.0) / 2.0))
    return row_shift, col_shift, peak_ratio, confidence


def coregister_scene_to_reference(
    scene: Any,
    reference: Any,
    method: str = 'auto',
) -> CoregistrationResult:
    result = CoregistrationResult(
        scene_id=scene.scene_id,
        reference_scene_id=reference.scene_id,
    )
    if str(getattr(scene, 'crs', '')) != str(getattr(reference, 'crs', '')):
        result.accepted = False
        result.method = 'crs_mismatch'
        result.confidence = 0.0
        result.shift_uncertainty_m = float('inf')
        result.rejection_reason = 'scenes_must_be_reprojected_to_one_crs_before_coregistration'
        return result
    if not crs_is_projected_metre(getattr(scene, 'crs', None)):
        result.accepted = False
        result.method = 'non_metric_crs'
        result.confidence = 0.0
        result.shift_uncertainty_m = float('inf')
        result.rejection_reason = 'coregistration_requires_projected_metre_crs'
        return result

    moving, fixed, band_name = _common_registration_band(scene, reference)
    x_size, y_size = pixel_size_xy(reference.transform)
    if moving is None or fixed is None or method == 'identity':
        result.method = 'geospatial_grid_only'
        result.confidence = 0.25
        result.shift_uncertainty_m = max(x_size, y_size)
        return result

    try:
        moving_on_reference = _warp_to_reference_grid(moving, scene, reference)
        row_shift, col_shift, peak_ratio, confidence = _phase_registration(
            moving_on_reference,
            fixed,
        )
        result.shift_x_m = col_shift * x_size
        result.shift_y_m = -row_shift * y_size
        result.peak_ratio = peak_ratio
        result.confidence = confidence
        result.method = 'phase_gradient:' + band_name
        result.shift_uncertainty_m = max(x_size, y_size) * max(0.1, 1.0 - confidence)
        result.residual_rms = result.shift_uncertainty_m
    except Exception as exc:
        result.method = 'phase_unavailable'
        result.confidence = 0.0
        result.shift_uncertainty_m = max(x_size, y_size)
        result.accepted = False
        result.rejection_reason = str(exc)
        return result

    magnitude = result.shift_magnitude_m()
    if magnitude > MAX_SHIFT_THRESHOLD_M:
        result.accepted = False
        result.rejection_reason = 'registration_shift_exceeds_threshold'
    elif result.confidence < 0.1:
        result.accepted = False
        result.rejection_reason = 'registration_peak_not_distinct'
    elif result.shift_uncertainty_m > MAX_UNCERTAINTY_M:
        result.accepted = False
        result.rejection_reason = 'registration_uncertainty_exceeds_threshold'
    return result


def coregister_stack(
    scenes: List[Any],
    reference_index: int = 0,
) -> List[CoregistrationResult]:
    """Coregister all scenes in a stack to a reference scene.

    Args:
        scenes: List of ASMAESceneRuntime objects.
        reference_index: Index of the reference scene (default: first).

    Returns:
        List of CoregistrationResult, one per scene.
    """
    if not scenes:
        return []

    reference = scenes[reference_index]
    results = []

    for i, scene in enumerate(scenes):
        if i == reference_index:
            # Reference scene: zero shift
            results.append(CoregistrationResult(
                scene_id=scene.scene_id,
                reference_scene_id=reference.scene_id,
                method="reference",
                confidence=1.0,
                accepted=True,
            ))
        else:
            result = coregister_scene_to_reference(scene, reference)
            results.append(result)

    return results


def classify_shift_clusters(
    results: List[CoregistrationResult],
    cluster_threshold_m: float = 3.0,
) -> List[ShiftCluster]:
    """Classify coregistration results into shift clusters.

    Scenes with similar shifts likely share the same orbital geometry.
    Outliers may indicate registration errors or genuine different tiles.

    Simple single-pass clustering: assign each scene to the nearest
    existing cluster or create a new one.
    """
    clusters: List[ShiftCluster] = []

    for result in results:
        if not result.accepted:
            continue

        # Find nearest cluster
        best_cluster = None
        best_dist = float("inf")

        for cluster in clusters:
            dx = result.shift_x_m - cluster.mean_shift_x_m
            dy = result.shift_y_m - cluster.mean_shift_y_m
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < best_dist:
                best_dist = dist
                best_cluster = cluster

        if best_cluster is not None and best_dist < cluster_threshold_m:
            # Merge into existing cluster (running mean)
            n = len(best_cluster.member_scene_ids)
            best_cluster.mean_shift_x_m = (
                (best_cluster.mean_shift_x_m * n + result.shift_x_m) / (n + 1)
            )
            best_cluster.mean_shift_y_m = (
                (best_cluster.mean_shift_y_m * n + result.shift_y_m) / (n + 1)
            )
            best_cluster.member_scene_ids.append(result.scene_id)
        else:
            # New cluster
            clusters.append(ShiftCluster(
                cluster_id=len(clusters),
                member_scene_ids=[result.scene_id],
                mean_shift_x_m=result.shift_x_m,
                mean_shift_y_m=result.shift_y_m,
            ))

    # Mark primary cluster (largest)
    if clusters:
        primary = max(clusters, key=lambda c: len(c.member_scene_ids))
        primary.is_primary = True

    return clusters


# ── Helpers ──────────────────────────────────────────────────────────────────

def _shift_from_transforms(
    target_transform: List[float],
    reference_transform: List[float],
) -> Tuple[float, float]:
    """Estimate shift from affine transform difference.

    Affine transform format is canonical GDAL:
    [origin_x, pixel_size_x, rotation_x, origin_y, rotation_y, pixel_size_y].

    Shift = target_origin - reference_origin (in CRS units, assumed meters).
    """
    if len(target_transform) < 6 or len(reference_transform) < 6:
        return (0.0, 0.0)

    dx = target_transform[0] - reference_transform[0]
    dy = target_transform[3] - reference_transform[3]

    return (dx, dy)


def compute_registration_uncertainty(
    results: List[CoregistrationResult],
) -> float:
    """Compute overall registration uncertainty from all coregistration results.

    Returns the RMS of all shift uncertainties (meters).
    """
    if not results:
        return 0.0

    sum_sq = sum(r.shift_uncertainty_m ** 2 for r in results if r.accepted)
    n = sum(1 for r in results if r.accepted)
    if n == 0:
        return 0.0

    return math.sqrt(sum_sq / n)
