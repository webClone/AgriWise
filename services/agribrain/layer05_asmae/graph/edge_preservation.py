"""
V71: Edge preservation — suppress smoothing across field boundaries.

This module ensures that no smoothing occurs across the field polygon
boundary (edge_penalty = 1.0) and applies distance-based boundary
proximity penalties for cells near edges (partial suppression).

Key invariant:
    GRAPH_EDGE_PENALTY_MULTIPLIER = 0.0 (zero smoothing across boundary)
    Cells within 1 microzone of the boundary get reduced smoothing.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from ..config import GRAPH_EDGE_PENALTY_MULTIPLIER


def compute_edge_penalties(
    edges: List[Tuple[str, str, float]],
    polygon_points: Optional[List[Tuple[float, float]]],
    origin_x: float,
    origin_y: float,
    resolution_m: int,
    graph,  # MicrozoneGraph
    boundary_proximity_cells: int = 1,
) -> List[float]:
    """Compute edge preservation penalty for each edge.

    Returns a list of penalty values in [0.0, 1.0]:
        0.0 = no penalty (interior, full smoothing allowed)
        1.0 = full penalty (boundary, zero smoothing)

    An edge gets penalty = 1.0 if:
        - Either endpoint is outside the field polygon
        - The edge midpoint is outside the field polygon
        - dist_weight was already set to 0.0 by neighborhoods.py

    Edges near the boundary (within `boundary_proximity_cells`)
    get a partial penalty proportional to proximity.

    Args:
        edges: List of (source_id, target_id, dist_weight) tuples.
        polygon_points: Field boundary polygon vertices.
        origin_x: Target grid origin X.
        origin_y: Target grid origin Y.
        resolution_m: Microzone cell size.
        graph: MicrozoneGraph with node attributes.
        boundary_proximity_cells: Number of cells from boundary
            to start applying partial penalty.

    Returns:
        List of edge_preservation_penalty values, one per edge.
    """
    penalties: List[float] = []

    # Pre-compute field edge distances for all nodes
    edge_distances: Dict[str, float] = {}
    if polygon_points:
        for node in graph.nodes():
            edge_distances[node.microzone_id] = _min_distance_to_polygon(
                node.centroid[0], node.centroid[1], polygon_points,
            )

    threshold_m = boundary_proximity_cells * resolution_m

    for src_id, tgt_id, dist_w in edges:
        # If neighborhoods.py already killed this edge
        if dist_w <= 0.0:
            penalties.append(1.0)
            continue

        if not polygon_points:
            # No polygon: no boundary penalty
            penalties.append(0.0)
            continue

        # Get distances to boundary
        src_dist = edge_distances.get(src_id, float("inf"))
        tgt_dist = edge_distances.get(tgt_id, float("inf"))
        min_dist = min(src_dist, tgt_dist)

        if min_dist <= 0.0:
            # On or outside boundary
            penalties.append(1.0)
        elif min_dist < threshold_m:
            # Near boundary: partial penalty
            penalty = 1.0 - (min_dist / threshold_m)
            penalties.append(round(max(0.0, min(1.0, penalty)), 4))
        else:
            penalties.append(0.0)

    return penalties


def _min_distance_to_polygon(
    x: float, y: float,
    polygon: List[Tuple[float, float]],
) -> float:
    """Minimum distance from point (x, y) to any polygon edge.

    Returns 0.0 if outside the polygon (treated by boundary crossing check).
    """
    n = len(polygon)
    if n < 2:
        return float("inf")

    min_d = float("inf")
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        d = _point_to_segment_distance(x, y, x1, y1, x2, y2)
        min_d = min(min_d, d)

    return min_d


def _point_to_segment_distance(
    px: float, py: float,
    x1: float, y1: float,
    x2: float, y2: float,
) -> float:
    """Distance from point (px, py) to line segment (x1,y1)-(x2,y2)."""
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq < 1e-12:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)

    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy

    return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)
