"""
Row Analysis Module.

Computes per-row continuity profiles, detects row breaks (stand gaps),
estimates stand density, and separates in-row vs inter-row weeds.
"""

from typing import List, Tuple
from dataclasses import dataclass
import math

from .schemas import RowBreak


def _build_row_mask(
    grid_h: int, grid_w: int,
    row_azimuth_deg: float,
    row_spacing_px: float,
    row_width_px: float,
    block_size: int,
) -> List[List[bool]]:
    """Build a boolean mask identifying which grid cells fall within a row strip.
    
    Returns a grid_h x grid_w boolean grid.  True = inside a row strip.
    """
    theta = math.radians(row_azimuth_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    half_width = row_width_px / (2.0 * block_size)
    spacing = row_spacing_px / block_size

    mask = [[False] * grid_w for _ in range(grid_h)]
    for gy in range(grid_h):
        for gx in range(grid_w):
            # Project block centre onto the row-normal axis
            rho = gx * cos_t + gy * sin_t
            dist = rho % spacing
            if dist > spacing / 2:
                dist = spacing - dist
            mask[gy][gx] = dist < half_width
    return mask


def compute_row_profiles(
    canopy_map: List[List[float]],
    row_azimuth_deg: float,
    row_spacing_px: float,
    block_size: int,
    row_width_px: float = 10,
) -> Tuple[List[float], int]:
    """Compute per-row continuity scores (0-1).
    
    Only blocks within the row strip width are considered, preventing
    inter-row soil from artificially lowering continuity scores.
    
    Returns:
        (continuity_scores, row_count)
    """
    if not canopy_map or not canopy_map[0]:
        return [], 0

    h, w = len(canopy_map), len(canopy_map[0])
    theta = math.radians(row_azimuth_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    spacing = row_spacing_px / block_size
    if spacing < 1:
        spacing = 1
    half_width = row_width_px / (2.0 * block_size)

    # Assign each block to the nearest row index, but only if it's
    # within the row strip width
    row_bins: dict = {}  # row_index -> list of canopy values along that row
    for gy in range(h):
        for gx in range(w):
            rho = gx * cos_t + gy * sin_t
            row_idx = round(rho / spacing)
            dist = abs(rho - row_idx * spacing)
            if dist > half_width:
                continue  # Skip inter-row blocks
            if row_idx not in row_bins:
                row_bins[row_idx] = []
            row_bins[row_idx].append(canopy_map[gy][gx])

    # Compute continuity per row (fraction of in-strip blocks with canopy > threshold)
    threshold = 0.2
    scores = []
    for idx in sorted(row_bins.keys()):
        vals = row_bins[idx]
        if len(vals) < 3:
            continue
        green_count = sum(1 for v in vals if v > threshold)
        scores.append(green_count / len(vals))

    return scores, len(scores)


def detect_row_breaks(
    canopy_map: List[List[float]],
    row_azimuth_deg: float,
    row_spacing_px: float,
    row_width_px: float,
    block_size: int,
    gap_threshold: float = 0.15,
    min_gap_blocks: int = 2,
) -> List[RowBreak]:
    """Detect contiguous gap segments within each row.
    
    A gap is a run of >= min_gap_blocks consecutive blocks along a row
    where canopy fraction < gap_threshold.
    """
    if not canopy_map or not canopy_map[0]:
        return []

    h, w = len(canopy_map), len(canopy_map[0])
    theta = math.radians(row_azimuth_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    spacing = row_spacing_px / block_size
    if spacing < 1:
        spacing = 1
    half_width = row_width_px / (2.0 * block_size)

    # Build per-row ordered block lists
    # For each block, compute (row_index, position_along_row, canopy_value)
    row_blocks: dict = {}  # row_index -> list of (along_pos, canopy_val)
    for gy in range(h):
        for gx in range(w):
            rho = gx * cos_t + gy * sin_t
            row_idx = round(rho / spacing)
            dist = rho - row_idx * spacing
            if abs(dist) > half_width:
                continue  # Not inside a row strip
            # Position along the row (perpendicular to the normal)
            along = -gx * sin_t + gy * cos_t
            if row_idx not in row_blocks:
                row_blocks[row_idx] = []
            row_blocks[row_idx].append((along, canopy_map[gy][gx]))

    breaks = []
    for row_idx in sorted(row_blocks.keys()):
        blocks = sorted(row_blocks[row_idx], key=lambda b: b[0])
        if len(blocks) < 3:
            continue
        # Scan for gap runs
        gap_start = None
        gap_count = 0
        for pos_idx, (along, val) in enumerate(blocks):
            if val < gap_threshold:
                if gap_start is None:
                    gap_start = pos_idx
                gap_count += 1
            else:
                if gap_start is not None and gap_count >= min_gap_blocks:
                    breaks.append(RowBreak(
                        row_index=row_idx,
                        start_block=gap_start,
                        end_block=gap_start + gap_count - 1,
                        gap_length_blocks=gap_count,
                    ))
                gap_start = None
                gap_count = 0
        # Handle gap at end of row
        if gap_start is not None and gap_count >= min_gap_blocks:
            breaks.append(RowBreak(
                row_index=row_idx,
                start_block=gap_start,
                end_block=gap_start + gap_count - 1,
                gap_length_blocks=gap_count,
            ))

    return breaks


def compute_stand_density(
    canopy_map: List[List[float]],
    row_azimuth_deg: float,
    row_spacing_px: float,
    row_width_px: float,
    block_size: int,
    presence_threshold: float = 0.3,
) -> List[float]:
    """Compute stand density (number of vegetation segments per row).
    
    A "stand" is a contiguous run of blocks with canopy > threshold within a row.
    Returns one value per detected row.
    """
    if not canopy_map or not canopy_map[0]:
        return []

    h, w = len(canopy_map), len(canopy_map[0])
    theta = math.radians(row_azimuth_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    spacing = row_spacing_px / block_size
    if spacing < 1:
        spacing = 1
    half_width = row_width_px / (2.0 * block_size)

    row_blocks: dict = {}
    for gy in range(h):
        for gx in range(w):
            rho = gx * cos_t + gy * sin_t
            row_idx = round(rho / spacing)
            dist = rho - row_idx * spacing
            if abs(dist) > half_width:
                continue
            along = -gx * sin_t + gy * cos_t
            if row_idx not in row_blocks:
                row_blocks[row_idx] = []
            row_blocks[row_idx].append((along, canopy_map[gy][gx]))

    densities = []
    for row_idx in sorted(row_blocks.keys()):
        blocks = sorted(row_blocks[row_idx], key=lambda b: b[0])
        if len(blocks) < 2:
            densities.append(0.0)
            continue
        # Count distinct green runs
        segment_count = 0
        in_segment = False
        for _, val in blocks:
            if val > presence_threshold:
                if not in_segment:
                    segment_count += 1
                    in_segment = True
            else:
                in_segment = False
        densities.append(float(segment_count))

    return densities


def classify_weed_location(
    weed_map: List[List[float]],
    row_mask: List[List[bool]],
) -> Tuple[List[List[float]], List[List[float]], float, float]:
    """Split weed map into in-row and inter-row components.
    
    Returns:
        (in_row_weed_map, inter_row_weed_map, in_row_fraction, inter_row_fraction)
    """
    if not weed_map or not weed_map[0]:
        return [], [], 0.0, 0.0

    h, w = len(weed_map), len(weed_map[0])
    in_row = [[0.0] * w for _ in range(h)]
    inter_row = [[0.0] * w for _ in range(h)]

    in_row_total = 0.0
    inter_row_total = 0.0
    in_row_count = 0
    inter_row_count = 0

    for gy in range(h):
        for gx in range(w):
            val = weed_map[gy][gx]
            if row_mask[gy][gx]:
                in_row[gy][gx] = val
                in_row_total += val
                in_row_count += 1
            else:
                inter_row[gy][gx] = val
                inter_row_total += val
                inter_row_count += 1

    in_frac = in_row_total / in_row_count if in_row_count > 0 else 0.0
    inter_frac = inter_row_total / inter_row_count if inter_row_count > 0 else 0.0

    return in_row, inter_row, in_frac, inter_frac
