"""
Orchard Analysis Module.

Detects individual tree canopies from orthomosaic canopy maps using flood-fill,
estimates missing trees from a regular grid template, and computes canopy
diameter and uniformity statistics.
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
import math


@dataclass
class TreeCluster:
    """A detected tree canopy cluster."""
    center_y: float      # Grid-block Y of centroid
    center_x: float      # Grid-block X of centroid
    area_blocks: int      # Number of blocks in the cluster
    diameter_blocks: float  # Approximate diameter (sqrt(area) * 1.13)


def _flood_fill(
    grid: List[List[float]],
    visited: List[List[bool]],
    start_y: int, start_x: int,
    threshold: float,
) -> List[Tuple[int, int]]:
    """Flood-fill from (start_y, start_x), returning all connected blocks > threshold."""
    h, w = len(grid), len(grid[0])
    stack = [(start_y, start_x)]
    cells = []
    while stack:
        y, x = stack.pop()
        if y < 0 or y >= h or x < 0 or x >= w:
            continue
        if visited[y][x]:
            continue
        if grid[y][x] < threshold:
            continue
        visited[y][x] = True
        cells.append((y, x))
        stack.append((y - 1, x))
        stack.append((y + 1, x))
        stack.append((y, x - 1))
        stack.append((y, x + 1))
    return cells


def detect_tree_clusters(
    canopy_map: List[List[float]],
    min_cluster_size: int = 3,
    canopy_threshold: float = 0.3,
) -> List[TreeCluster]:
    """Detect individual tree canopies via flood-fill on the canopy map.
    
    Args:
        canopy_map: 2D grid of canopy fraction per block.
        min_cluster_size: Minimum blocks to count as a tree.
        canopy_threshold: Minimum canopy fraction to be considered vegetation.
    
    Returns:
        List of TreeCluster objects.
    """
    if not canopy_map or not canopy_map[0]:
        return []

    h, w = len(canopy_map), len(canopy_map[0])
    visited = [[False] * w for _ in range(h)]
    clusters = []

    for y in range(h):
        for x in range(w):
            if visited[y][x] or canopy_map[y][x] < canopy_threshold:
                visited[y][x] = True
                continue
            cells = _flood_fill(canopy_map, visited, y, x, canopy_threshold)
            if len(cells) >= min_cluster_size:
                cy = sum(c[0] for c in cells) / len(cells)
                cx = sum(c[1] for c in cells) / len(cells)
                area = len(cells)
                # Approximate diameter assuming circular canopy
                diameter = math.sqrt(area) * 1.128  # sqrt(4*area/pi)
                clusters.append(TreeCluster(
                    center_y=cy, center_x=cx,
                    area_blocks=area, diameter_blocks=diameter,
                ))

    return clusters


def estimate_tree_spacing(clusters: List[TreeCluster]) -> float:
    """Auto-estimate inter-tree spacing from mean nearest-neighbour distance.
    
    Returns spacing in grid-block units, or 0 if insufficient clusters.
    """
    if len(clusters) < 3:
        return 0.0

    nn_dists = []
    for i, c1 in enumerate(clusters):
        min_d = float("inf")
        for j, c2 in enumerate(clusters):
            if i == j:
                continue
            d = math.sqrt((c1.center_y - c2.center_y) ** 2 + (c1.center_x - c2.center_x) ** 2)
            if d < min_d:
                min_d = d
        nn_dists.append(min_d)

    return sum(nn_dists) / len(nn_dists)


def estimate_missing_trees(
    canopy_map: List[List[float]],
    clusters: List[TreeCluster],
    spacing_blocks: float,
    canopy_threshold: float = 0.3,
) -> Tuple[List[List[float]], int]:
    """Detect missing trees by overlaying a regular grid template.
    
    A grid point that falls in a low-canopy area (no nearby cluster) is "missing."
    
    Returns:
        (missing_tree_map, missing_count)
        missing_tree_map: 2D grid where 1.0 = expected tree missing
    """
    if not canopy_map or not canopy_map[0] or spacing_blocks < 1:
        return [], 0

    h, w = len(canopy_map), len(canopy_map[0])
    missing_map = [[0.0] * w for _ in range(h)]

    # Build a regular grid over the field
    half = spacing_blocks / 2.0
    expected_positions = []
    gy = half
    while gy < h:
        gx = half
        while gx < w:
            expected_positions.append((gy, gx))
            gx += spacing_blocks
        gy += spacing_blocks

    # For each expected position, check if a cluster exists nearby
    match_radius = spacing_blocks * 0.4  # 40% of spacing tolerance
    cluster_positions = [(c.center_y, c.center_x) for c in clusters]

    missing_count = 0
    for ey, ex in expected_positions:
        found = False
        for cy, cx in cluster_positions:
            if math.sqrt((ey - cy) ** 2 + (ex - cx) ** 2) < match_radius:
                found = True
                break
        if not found:
            # Mark the missing position on the map
            my, mx = int(ey), int(ex)
            if 0 <= my < h and 0 <= mx < w:
                missing_map[my][mx] = 1.0
                missing_count += 1

    return missing_map, missing_count


def compute_canopy_diameters(
    clusters: List[TreeCluster],
    block_size_cm: float,
) -> List[float]:
    """Convert cluster diameters from block units to centimetres."""
    return [c.diameter_blocks * block_size_cm for c in clusters]


def compute_canopy_uniformity(diameters_cm: List[float]) -> float:
    """Compute coefficient of variation of canopy diameters.
    
    Returns 0.0 for <= 1 tree (undefined).
    """
    if len(diameters_cm) < 2:
        return 0.0

    mean = sum(diameters_cm) / len(diameters_cm)
    if mean < 1e-6:
        return 0.0
    var = sum((d - mean) ** 2 for d in diameters_cm) / len(diameters_cm)
    std = math.sqrt(var)
    return std / mean
