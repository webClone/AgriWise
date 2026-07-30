"""
V71: Row alignment weights for crop-row-aware anisotropic smoothing.

Crop rows run at a given direction (0–180 degrees from N).
Smoothing is stronger along the row direction and weaker across it.

Defaults (conservative, user-approved):
  row_aligned_multiplier: 1.8   (stronger along crop rows)
  cross_row_multiplier:   0.5   (weaker across crop rows)
"""

from __future__ import annotations

import math
from typing import List, Tuple

from ..config import (
    GRAPH_CROSS_ROW_MULTIPLIER,
    GRAPH_ROW_ALIGNED_MULTIPLIER,
)


def compute_row_alignment_weights(
    edges: List[Tuple[str, str, float]],
    row_direction_deg: float,
    resolution_m: int,
    along_row_multiplier: float = GRAPH_ROW_ALIGNED_MULTIPLIER,
    across_row_multiplier: float = GRAPH_CROSS_ROW_MULTIPLIER,
) -> List[float]:
    """Compute row-alignment weight for each edge.

    The weight is interpolated between `along_row_multiplier` and
    `across_row_multiplier` based on how aligned the edge direction
    is with the crop row direction.

    Args:
        edges: List of (source_id, target_id, dist_weight) tuples.
        row_direction_deg: Crop row direction (0 = North, 90 = East).
        resolution_m: Microzone cell size.
        along_row_multiplier: Weight boost for along-row edges.
        across_row_multiplier: Weight reduction for across-row edges.

    Returns:
        List of row_alignment_weight values, one per edge.
    """
    row_dir_rad = math.radians(row_direction_deg)
    row_dx = math.sin(row_dir_rad)
    row_dy = math.cos(row_dir_rad)

    weights: List[float] = []

    for src_id, tgt_id, _ in edges:
        # Parse row/col from IDs like "mz_003_012"
        sr, sc = _parse_mz_id(src_id)
        tr, tc = _parse_mz_id(tgt_id)

        if sr is None or tr is None:
            weights.append(1.0)
            continue

        # Edge direction in grid space (columns ~ X, rows ~ -Y)
        edge_dx = float(tc - sc)
        edge_dy = float(sr - tr)  # Row increases downward → negate for Y

        edge_len = math.sqrt(edge_dx * edge_dx + edge_dy * edge_dy)
        if edge_len < 1e-8:
            weights.append(1.0)
            continue

        # Normalize
        edge_dx /= edge_len
        edge_dy /= edge_len

        # Cosine of angle between edge and row direction
        cos_angle = abs(edge_dx * row_dx + edge_dy * row_dy)
        cos_angle = min(1.0, max(0.0, cos_angle))

        # Interpolate between along-row and across-row multipliers
        # cos_angle = 1.0 → perfectly aligned with row → along_row_multiplier
        # cos_angle = 0.0 → perpendicular to row → across_row_multiplier
        w = (
            cos_angle * along_row_multiplier
            + (1.0 - cos_angle) * across_row_multiplier
        )
        weights.append(round(w, 4))

    return weights


def _parse_mz_id(mz_id: str):
    """Parse 'mz_003_012' into (row=3, col=12)."""
    parts = mz_id.split("_")
    if len(parts) >= 3:
        try:
            return int(parts[1]), int(parts[2])
        except ValueError:
            pass
    return None, None
