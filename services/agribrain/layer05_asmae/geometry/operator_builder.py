"""
ASMAE H_t Observation Operator Builder.

Constructs the sparse linear operator:

    y_t = H_t · x_t + ε_t

Where:
    y_t : observed pixel values (Sentinel-2 / SAR)
    H_t : geometry + PSF blur + fractional overlap operator
    x_t : micro-zone state vector
    ε_t : observation noise

Key design rules:
    1. Non-divisor resolutions ARE supported (3m, 7m in 10m pixel)
    2. NO reshape assumption (10m pixel ≠ exact equal subcells)
    3. Fractional overlap weights used for all resolutions
    4. Cloud masks reduce operator support
    5. Same scene + same resolution → deterministic H_t (content-addressed)
    6. Registration shifts are incorporated into geometry

When scipy is available, builds a real CSR sparse matrix.
When not available, stores the operator as a list-of-dicts
(functional but slower).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..config import CANDIDATE_RESOLUTIONS_M, N_STATES
from ..schema import ASMAESceneRuntime, ObservationOperatorRuntime
from .coregistration import CoregistrationResult
from .psf import PSFModel, get_default_psf_sigma, get_psf_model
from .spatial_reference import (
    TargetMicrozoneGrid,
    affine_from_gdal,
    origin_xy,
    pixel_size_m as canonical_pixel_size_m,
    target_grid_from_reference,
)

logger = logging.getLogger(__name__)

# Try scipy for real sparse matrices
try:
    from scipy import sparse as sp
    HAS_SCIPY = True
except ImportError:
    sp = None  # type: ignore[assignment]
    HAS_SCIPY = False


# ── Fractional Overlap Computation ──────────────────────────────────────────

@dataclass
class PixelMicrozoneOverlap:
    """Fractional overlap between a Sentinel pixel and a micro-zone.

    This is the core of H_t: each entry describes how much a
    micro-zone contributes to the observed pixel value.
    """
    pixel_row: int
    pixel_col: int
    microzone_row: int
    microzone_col: int
    microzone_id: str

    geometric_overlap: float   # Area overlap fraction [0, 1]
    psf_weight: float          # PSF kernel weight [0, 1]
    combined_weight: float     # geometric_overlap * psf_weight
    is_masked: bool = False    # True if cloud/shadow masked


def compute_fractional_overlaps(
    pixel_size_m: float,
    zone_size_m: float,
    source_origin_x: float,
    source_origin_y: float,
    target_origin_x: float,
    target_origin_y: float,
    n_pixel_rows: int,
    n_pixel_cols: int,
    shift_x_m: float = 0.0,
    shift_y_m: float = 0.0,
    psf_model: Optional[PSFModel] = None,
    cloud_mask: Optional[List[List[bool]]] = None,
    max_zone_rows: Optional[int] = None,
    max_zone_cols: Optional[int] = None,
) -> List[PixelMicrozoneOverlap]:
    """Compute fractional overlap weights for all pixel-zone pairs.

    This is the mathematical core of H_t construction.

    Key coordinate-frame rule (P0-4):
      - Source pixel footprints use scene transform origin + coreg shift.
      - Target microzone grid uses a FIXED reference origin.
      - The target grid does NOT move with each scene.

    For non-divisor resolutions (e.g., 7m zone in 10m pixel):
        A single 10m pixel may overlap 1-4 micro-zones.
        Each zone gets a weight proportional to its area overlap
        times the PSF kernel value at the zone-pixel distance.

    Args:
        pixel_size_m: Source pixel size (e.g., 10m for S2).
        zone_size_m: Target micro-zone size (candidate resolution).
        source_origin_x: X coordinate of source scene top-left pixel corner.
        source_origin_y: Y coordinate of source scene top-left pixel corner.
        target_origin_x: X coordinate of fixed target microzone grid origin.
        target_origin_y: Y coordinate of fixed target microzone grid origin.
        n_pixel_rows: Number of pixel rows.
        n_pixel_cols: Number of pixel columns.
        shift_x_m: Coregistration shift in X (scene → reference).
        shift_y_m: Coregistration shift in Y (scene → reference).
        psf_model: PSF model for blur weighting.
        cloud_mask: Boolean mask (True = valid).

    Returns:
        List of PixelMicrozoneOverlap entries (sparse representation).
    """
    if pixel_size_m <= 0 or zone_size_m <= 0:
        return []

    # Maximum valid zone grid extents (based on the pixel grid coverage)
    field_size_x = n_pixel_cols * pixel_size_m
    field_size_y = n_pixel_rows * pixel_size_m
    max_zone_cols = (
        int(max_zone_cols)
        if max_zone_cols is not None
        else int(math.ceil(field_size_x / zone_size_m))
    )
    max_zone_rows = (
        int(max_zone_rows)
        if max_zone_rows is not None
        else int(math.ceil(field_size_y / zone_size_m))
    )

    overlaps: List[PixelMicrozoneOverlap] = []

    for pr in range(n_pixel_rows):
        for pc in range(n_pixel_cols):
            # Check cloud mask
            is_masked = False
            if cloud_mask is not None:
                if pr < len(cloud_mask) and pc < len(cloud_mask[pr]):
                    if not cloud_mask[pr][pc]:
                        is_masked = True

            # Source pixel bounding box (scene origin + coreg shift)
            px_left = source_origin_x + pc * pixel_size_m + shift_x_m
            px_right = px_left + pixel_size_m
            px_top = source_origin_y - pr * pixel_size_m + shift_y_m
            px_bottom = px_top - pixel_size_m

            # Pixel center (for PSF distance computation)
            px_cx = (px_left + px_right) / 2.0
            px_cy = (px_top + px_bottom) / 2.0

            # Which target micro-zone rows/cols does this shifted pixel overlap?
            # Zone grid uses the FIXED target/reference origin, NOT the scene origin.
            zone_col_start = int(math.floor(
                (px_left - target_origin_x) / zone_size_m
            ))
            zone_col_end = int(math.ceil(
                (px_right - target_origin_x) / zone_size_m
            ))
            zone_row_start = int(math.floor(
                (target_origin_y - px_top) / zone_size_m
            ))
            zone_row_end = int(math.ceil(
                (target_origin_y - px_bottom) / zone_size_m
            ))

            # Clamp to valid grid range AFTER computing overlap indices.
            # This prevents silently dropping legitimate overlap area
            # before normalization (the bug that caused row-sum < 1.0).
            zone_col_start = max(0, zone_col_start)
            zone_col_end = min(zone_col_end, max_zone_cols)
            zone_row_start = max(0, zone_row_start)
            zone_row_end = min(zone_row_end, max_zone_rows)

            for zr in range(zone_row_start, zone_row_end):
                for zc in range(zone_col_start, zone_col_end):
                    # Zone bounding box (fixed target grid)
                    z_left = target_origin_x + zc * zone_size_m
                    z_right = z_left + zone_size_m
                    z_top = target_origin_y - zr * zone_size_m
                    z_bottom = z_top - zone_size_m

                    # Intersection area
                    inter_left = max(px_left, z_left)
                    inter_right = min(px_right, z_right)
                    inter_top = min(px_top, z_top)
                    inter_bottom = max(px_bottom, z_bottom)

                    if inter_right <= inter_left or inter_top <= inter_bottom:
                        continue  # No overlap

                    inter_area = (inter_right - inter_left) * (inter_top - inter_bottom)
                    pixel_area = pixel_size_m * pixel_size_m
                    geometric_overlap = inter_area / pixel_area

                    if geometric_overlap < 1e-6:
                        continue  # Negligible

                    # PSF weight
                    psf_weight = 1.0
                    if psf_model is not None:
                        z_cx = (z_left + z_right) / 2.0
                        z_cy = (z_top + z_bottom) / 2.0
                        psf_weight = psf_model.overlap_weight(
                            px_cx, px_cy, z_cx, z_cy, zone_size_m,
                        )
                        if psf_weight < 1e-6:
                            continue

                    combined = geometric_overlap * psf_weight
                    mz_id = f"mz_{zr}_{zc}"

                    overlaps.append(PixelMicrozoneOverlap(
                        pixel_row=pr,
                        pixel_col=pc,
                        microzone_row=zr,
                        microzone_col=zc,
                        microzone_id=mz_id,
                        geometric_overlap=geometric_overlap,
                        psf_weight=psf_weight,
                        combined_weight=combined,
                        is_masked=is_masked,
                    ))

    return overlaps


# ── Operator Construction ───────────────────────────────────────────────────

def build_observation_operator(
    scene: ASMAESceneRuntime,
    candidate_resolution_m: int,
    coreg: Optional[CoregistrationResult] = None,
    psf_model: Optional[PSFModel] = None,
    cloud_mask: Optional[List[List[bool]]] = None,
    reference_origin: Optional[Tuple[float, float]] = None,
    target_grid: Optional[TargetMicrozoneGrid] = None,
) -> ObservationOperatorRuntime:
    """Build H_t observation operator for a single scene.

    P0-4 coordinate-frame rule:
        - source_origin = scene transform origin (where this scene's pixels start)
        - target_origin = fixed reference grid origin (where microzones live)
        - shift = coregistration correction (scene → reference alignment)

        source pixel footprint = source_origin + pixel_index * pixel_size + shift
        target zone grid = fixed target_origin (does NOT move per scene)

    Steps:
        1. Parse scene geometry (CRS, transform, pixel grid)
        2. Determine reference origin (first scene or explicit)
        3. Apply coregistration shift to source pixel footprints
        4. Compute fractional overlaps against fixed target grid
        5. Normalize rows (each pixel's weights sum to 1)
        6. Assemble into sparse matrix (scipy) or weight list
        7. Compute quality metrics

    Args:
        scene: The observation scene.
        candidate_resolution_m: Target micro-zone resolution.
        coreg: Coregistration result (shift values).
        psf_model: PSF model for this sensor/band.
        cloud_mask: Boolean mask (True = valid pixel).
        reference_origin: Fixed (x, y) origin for the target microzone grid.
            If None, defaults to this scene's own transform origin
            (correct only for the reference/first scene).

    Returns:
        ObservationOperatorRuntime with H_t matrix.
    """
    # Defaults
    if psf_model is None:
        psf_model = get_psf_model(scene.sensor)

    shift_x = 0.0
    shift_y = 0.0
    reg_uncertainty = 0.0
    if coreg is not None:
        reg_uncertainty = coreg.shift_uncertainty_m
        if coreg.accepted:
            shift_x = coreg.shift_x_m
            shift_y = coreg.shift_y_m

    # Layer 0 publishes GDAL-order transforms. Decode them exactly once and
    # reject grids that have not been normalized into a north-up metre CRS.
    transform = list(scene.transform or [])
    affine = affine_from_gdal(transform)
    pixel_size_m = canonical_pixel_size_m(scene)
    if abs(float(affine.b)) > 1e-8 or abs(float(affine.d)) > 1e-8:
        raise ValueError('rotated_scene_requires_north_up_reprojection')
    if abs(abs(float(affine.a)) - abs(float(affine.e))) > max(1e-6, pixel_size_m * 0.01):
        raise ValueError('non_square_scene_pixels_not_supported')

    # P0-4: Explicit source vs target origin separation
    source_origin_x, source_origin_y = origin_xy(transform)

    # Target origin: fixed reference grid (same for ALL scenes in a stack)
    if target_grid is not None:
        target_origin_x = target_grid.origin_x
        target_origin_y = target_grid.origin_y
    elif reference_origin is not None:
        target_origin_x, target_origin_y = reference_origin
    else:
        # Default: use this scene's origin (only correct for reference scene)
        target_origin_x = source_origin_x
        target_origin_y = source_origin_y

    # Grid dimensions
    n_rows = max(scene.height, 1)
    n_cols = max(scene.width, 1)

    if n_rows <= 1 or n_cols <= 1:
        raise ValueError('spatial_operator_requires_real_raster_dimensions')

    # Compute micro-zone grid dimensions (based on target grid coverage)
    if target_grid is not None:
        if int(target_grid.resolution_m) != int(candidate_resolution_m):
            raise ValueError('target_grid_resolution_mismatch')
        n_zone_cols = int(target_grid.n_cols)
        n_zone_rows = int(target_grid.n_rows)
    else:
        field_size_x = n_cols * pixel_size_m
        field_size_y = n_rows * pixel_size_m
        n_zone_cols = int(math.ceil(field_size_x / candidate_resolution_m))
        n_zone_rows = int(math.ceil(field_size_y / candidate_resolution_m))
    n_zones = n_zone_rows * n_zone_cols
    n_pixels = n_rows * n_cols

    # Compute fractional overlaps with P0-4 separated origins
    overlaps = compute_fractional_overlaps(
        pixel_size_m=pixel_size_m,
        zone_size_m=float(candidate_resolution_m),
        source_origin_x=source_origin_x,
        source_origin_y=source_origin_y,
        target_origin_x=target_origin_x,
        target_origin_y=target_origin_y,
        n_pixel_rows=n_rows,
        n_pixel_cols=n_cols,
        shift_x_m=shift_x,
        shift_y_m=shift_y,
        psf_model=psf_model,
        cloud_mask=(cloud_mask if cloud_mask is not None else getattr(scene, 'valid_support', None)),
        max_zone_rows=n_zone_rows,
        max_zone_cols=n_zone_cols,
    )

    # ── Row normalization ────────────────────────────────────────────
    # Each pixel's weights should sum to 1.0
    row_sums: Dict[Tuple[int, int], float] = {}
    for ov in overlaps:
        if ov.is_masked:
            continue
        key = (ov.pixel_row, ov.pixel_col)
        row_sums[key] = row_sums.get(key, 0.0) + ov.combined_weight

    for ov in overlaps:
        if ov.is_masked:
            ov.combined_weight = 0.0
            continue
        key = (ov.pixel_row, ov.pixel_col)
        rs = row_sums.get(key, 1.0)
        if rs > 1e-8:
            ov.combined_weight /= rs

    # ── Build sparse matrix ──────────────────────────────────────────
    H_matrix = None
    nnz = 0

    if HAS_SCIPY and sp is not None and n_pixels > 0 and n_zones > 0:
        row_indices = []
        col_indices = []
        values = []

        for ov in overlaps:
            if ov.combined_weight < 1e-8:
                continue
            pixel_idx = ov.pixel_row * n_cols + ov.pixel_col
            zone_idx = ov.microzone_row * n_zone_cols + ov.microzone_col

            if pixel_idx < n_pixels and zone_idx < n_zones:
                row_indices.append(pixel_idx)
                col_indices.append(zone_idx)
                values.append(ov.combined_weight)

        if values:
            H_matrix = sp.csr_matrix(
                (values, (row_indices, col_indices)),
                shape=(n_pixels, n_zones),
            )
            nnz = H_matrix.nnz

    # ── Quality metrics ──────────────────────────────────────────────
    valid_pixels = sum(1 for k, v in row_sums.items() if v > 1e-8)
    support_score = valid_pixels / max(n_pixels, 1)

    # Condition number proxy: ratio of max/min row sums
    if row_sums:
        rs_vals = [v for v in row_sums.values() if v > 1e-8]
        if rs_vals:
            cond_proxy = max(rs_vals) / min(rs_vals) if min(rs_vals) > 0 else 1e6
        else:
            cond_proxy = 0.0
    else:
        cond_proxy = 0.0

    # ── Deterministic ID ─────────────────────────────────────────────
    id_payload = {
        "scene_id": scene.scene_id,
        "resolution_m": candidate_resolution_m,
        "pixel_size_m": pixel_size_m,
        "source_origin": [source_origin_x, source_origin_y],
        "target_origin": [target_origin_x, target_origin_y],
        "grid": [n_rows, n_cols],
        "shift": [round(shift_x, 3), round(shift_y, 3)],
        "psf_sigma": psf_model.sigma_m,
    }
    id_payload['source_crs'] = str(scene.crs)
    id_payload['target_crs'] = str(target_grid.crs if target_grid is not None else scene.crs)
    id_payload['valid_support_hash'] = str(getattr(scene, 'valid_support_hash', '') or '')
    id_hash = hashlib.sha256(
        json.dumps(id_payload, sort_keys=True).encode()
    ).hexdigest()[:16]
    operator_id = f"Ht_{scene.scene_id}_{candidate_resolution_m}m_{id_hash}"

    return ObservationOperatorRuntime(
        operator_id=operator_id,
        scene_id=scene.scene_id,
        sensor=scene.sensor,
        source_resolution_m=pixel_size_m,
        target_resolution_m=candidate_resolution_m,
        source_crs=scene.crs,
        target_crs=(target_grid.crs if target_grid is not None else scene.crs),
        source_transform=scene.transform,
        target_transform=(
            target_grid.transform_gdal
            if target_grid is not None
            else [
                target_origin_x, float(candidate_resolution_m), 0.0,
                target_origin_y, 0.0, -float(candidate_resolution_m),
            ]
        ),
        H_matrix=H_matrix,
        psf_model=psf_model.sensor + "_gaussian",
        blur_sigma_m=psf_model.sigma_m,
        support_score=round(support_score, 4),
        condition_number_proxy=round(cond_proxy, 4),
        registration_uncertainty_m=round(reg_uncertainty, 4),
        valid_support_hash=str(getattr(scene, 'valid_support_hash', '') or ''),
        transform_convention='gdal',
        valid_mask_ref='scene.valid_support',
    )


def build_operators_for_stack(
    scenes: List[ASMAESceneRuntime],
    candidate_resolution_m: int,
    coreg_results: Optional[List[CoregistrationResult]] = None,
    cloud_masks: Optional[Dict[str, List[List[bool]]]] = None,
) -> List[ObservationOperatorRuntime]:
    """Build H_t operators for an entire scene stack at a given resolution.

    P0-4: The first scene in the stack defines the reference origin.
    All subsequent scenes' operators use the same fixed target grid.

    Args:
        scenes: List of ASMAESceneRuntime objects.
        candidate_resolution_m: Target resolution.
        coreg_results: Optional coregistration results (one per scene).
        cloud_masks: Optional cloud masks keyed by scene_id.

    Returns:
        List of ObservationOperatorRuntime (one per scene).
    """
    operators = []

    target_grid = (
        target_grid_from_reference(scenes[0], candidate_resolution_m)
        if scenes
        else None
    )

    for i, scene in enumerate(scenes):
        coreg = None
        if coreg_results and i < len(coreg_results):
            coreg = coreg_results[i]

        mask = None
        if cloud_masks and scene.scene_id in cloud_masks:
            mask = cloud_masks[scene.scene_id]

        psf = get_psf_model(scene.sensor)

        try:
            op = build_observation_operator(
                scene=scene,
                candidate_resolution_m=candidate_resolution_m,
                coreg=coreg,
                psf_model=psf,
                cloud_mask=mask,
                target_grid=target_grid,
            )
            operators.append(op)
        except Exception as e:
            logger.warning(
                "Failed to build H_t for scene %s at %dm: %s",
                scene.scene_id, candidate_resolution_m, e,
            )

    return operators
