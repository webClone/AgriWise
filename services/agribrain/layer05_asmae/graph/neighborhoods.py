"""
V71: Neighborhood discovery for microzone graphs.

Builds 8-connected neighborhood edges with distance-based weight decay.
Suppresses edges that cross field polygon boundaries.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple


def build_neighborhood_edges(
    n_rows: int,
    n_cols: int,
    polygon_points: Optional[List[Tuple[float, float]]],
    origin_x: float,
    origin_y: float,
    resolution_m: int,
) -> List[Tuple[str, str, float]]:
    """Build 8-connected neighborhood edges between microzone cells.

    Returns list of (source_id, target_id, distance_weight) tuples.
    Only creates edges where source < target to avoid duplicates.

    Edge suppression:
        - Edges crossing the field polygon boundary get distance_weight = 0.0.
        - These will be fully suppressed by edge_preservation_penalty = 1.0
          in the edge_preservation module.

    Distance weight:
        - Orthogonal neighbors (Δ=1): weight = 1.0
        - Diagonal neighbors (Δ=√2):  weight = 1.0 / √2 ≈ 0.707
    """
    edges: List[Tuple[str, str, float]] = []
    inv_sqrt2 = 1.0 / math.sqrt(2.0)

    # 8 neighbor offsets: (drow, dcol)
    offsets = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),            (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    ]

    for r in range(n_rows):
        for c in range(n_cols):
            src_id = f"mz_{r:03d}_{c:03d}"

            for dr, dc in offsets:
                nr, nc = r + dr, c + dc

                # Bounds check
                if nr < 0 or nr >= n_rows or nc < 0 or nc >= n_cols:
                    continue

                # Only emit one direction (src < tgt) to avoid duplicates
                tgt_id = f"mz_{nr:03d}_{nc:03d}"
                if src_id >= tgt_id:
                    continue

                # Distance weight
                is_diagonal = abs(dr) + abs(dc) == 2
                dist_w = inv_sqrt2 if is_diagonal else 1.0

                # Check boundary crossing
                if polygon_points and _crosses_boundary(
                    r, c, nr, nc, origin_x, origin_y, resolution_m, polygon_points,
                ):
                    dist_w = 0.0

                edges.append((src_id, tgt_id, dist_w))

    return edges


def _crosses_boundary(
    r1: int, c1: int, r2: int, c2: int,
    origin_x: float, origin_y: float,
    resolution_m: int,
    polygon_points: List[Tuple[float, float]],
) -> bool:
    """Check if the edge between two microzone centroids crosses
    the field polygon boundary.

    Uses a simplified ray-casting approach: if the midpoint of the
    edge is outside the polygon, the edge crosses the boundary.
    """
    # Compute centroids in CRS units
    cx1 = origin_x + (c1 + 0.5) * resolution_m
    cy1 = origin_y - (r1 + 0.5) * resolution_m
    cx2 = origin_x + (c2 + 0.5) * resolution_m
    cy2 = origin_y - (r2 + 0.5) * resolution_m

    # Midpoint
    mx = (cx1 + cx2) / 2.0
    my = (cy1 + cy2) / 2.0

    # Both centroids must be inside the polygon
    inside1 = _point_in_polygon(cx1, cy1, polygon_points)
    inside2 = _point_in_polygon(cx2, cy2, polygon_points)

    if not inside1 or not inside2:
        return True

    # Midpoint must also be inside
    if not _point_in_polygon(mx, my, polygon_points):
        return True

    return False


def _point_in_polygon(
    x: float, y: float,
    polygon: List[Tuple[float, float]],
) -> bool:
    """Ray-casting point-in-polygon test.

    Returns True if (x, y) is inside the polygon.
    """
    n = len(polygon)
    if n < 3:
        return True  # Degenerate polygon: treat as unbounded

    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
        ):
            inside = not inside
        j = i

    return inside
