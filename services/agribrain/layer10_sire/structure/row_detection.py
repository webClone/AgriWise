"""
Row Detection Engine — Detect crop row structures from NDVI raster
==================================================================

Uses directional variance analysis to detect planted rows:
  - Compute variance along 0°, 45°, 90°, 135° directions
  - Minimum variance direction = row direction
  - Extract row segments as elongated connected components
"""
from typing import List, Optional, Tuple
from services.agribrain.layer10_sire.schema import (
    Layer10Input, MicroObjectArtifact, ObjectType,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData

MIN_ROW_LENGTH = 3  # Minimum cells to count as row


def detect_rows(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
) -> List[MicroObjectArtifact]:
    """Detect crop row structures from NDVI raster."""
    if inp.resolution_m > 5.0:
        return []

    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)

    ndvi = l1_data.raster_maps.get('ndvi')
    if ndvi is None:
        return []

    # Step 1: Find dominant row direction via directional variance
    best_dir, directions = _find_row_direction(ndvi, H, W)

    # Step 2: Extract row segments along dominant direction
    objects = []
    threshold = _adaptive_threshold(ndvi, H, W)
    visited = [[False] * W for _ in range(H)]

    dr, dc = best_dir
    row_idx = 0

    # Scan perpendicular to row direction
    perp_dr, perp_dc = -dc, dr  # 90° rotation

    for start in range(max(H, W)):
        # Start from edges perpendicular to row direction
        sr = start if abs(perp_dr) == 0 else (start * perp_dr) % H
        sc = start if abs(perp_dc) == 0 else (start * perp_dc) % W

        # Walk along row direction
        cells = []
        cr, cc = int(sr) % H, int(sc) % W
        for step in range(max(H, W)):
            r = (cr + step * dr) % H
            c = (cc + step * dc) % W
            if 0 <= r < H and 0 <= c < W:
                if not visited[r][c] and ndvi[r][c] is not None and ndvi[r][c] > threshold:
                    cells.append((r, c))
                    visited[r][c] = True
                elif cells:
                    break

        if len(cells) >= MIN_ROW_LENGTH:
            ndvi_vals = [ndvi[r][c] for r, c in cells if ndvi[r][c] is not None]
            mean_ndvi = sum(ndvi_vals) / len(ndvi_vals) if ndvi_vals else 0.0
            cr_mean = sum(r for r, c in cells) / len(cells)
            cc_mean = sum(c for r, c in cells) / len(cells)

            objects.append(MicroObjectArtifact(
                object_id=f"ROW-{inp.plot_id}-{row_idx}",
                object_type=ObjectType.ROW_SEGMENT,
                centroid=(cr_mean, cc_mean),
                cell_indices=cells,
                area_m2=len(cells) * inp.resolution_m * inp.resolution_m,
                score=min(1.0, len(cells) / max(H, W)),
                confidence=0.6 if len(cells) >= MIN_ROW_LENGTH * 2 else 0.4,
                measurements={
                    "ndvi_mean": round(mean_ndvi, 3),
                    "length_cells": len(cells),
                    "direction": f"{dr},{dc}",
                },
                derived_from="L1_NDVI_DIRECTIONAL",
            ))
            row_idx += 1

    return objects


def _find_row_direction(ndvi, H, W) -> Tuple[Tuple[int, int], list]:
    """Find dominant row direction by minimum directional variance."""
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]  # horizontal, vertical, diag
    best_var = float('inf')
    best_dir = (0, 1)

    for dr, dc in directions:
        variances = []
        for start_r in range(H):
            for start_c in range(W):
                vals = []
                r, c = start_r, start_c
                for _ in range(min(H, W)):
                    if 0 <= r < H and 0 <= c < W and ndvi[r][c] is not None:
                        vals.append(ndvi[r][c])
                    r += dr
                    c += dc
                if len(vals) >= 3:
                    m = sum(vals) / len(vals)
                    v = sum((x - m) ** 2 for x in vals) / len(vals)
                    variances.append(v)

        if variances:
            mean_var = sum(variances) / len(variances)
            if mean_var < best_var:
                best_var = mean_var
                best_dir = (dr, dc)

    return best_dir, directions


def _adaptive_threshold(ndvi, H, W):
    """Adaptive NDVI threshold: mean - 0.5 * std."""
    vals = [ndvi[r][c] for r in range(H) for c in range(W) if ndvi[r][c] is not None]
    if not vals:
        return 0.3
    mean = sum(vals) / len(vals)
    std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
    return max(0.2, mean - 0.5 * std)
