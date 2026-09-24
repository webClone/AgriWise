"""
V71: Microzone Graph — Spatial awareness structure.

Nodes represent micro-zone grid cells at a given resolution.
Edges encode adjacency relationships weighted by:
  - Euclidean distance
  - Crop row alignment
  - Soil similarity
  - Irrigation connectivity
  - Edge preservation penalty (field boundary suppression)

The graph is deterministic for a given (geometry_hash, resolution_m).

Key invariants:
  - No edges cross field polygon boundaries
  - Row smoothing stronger along crop rows than across
  - Soil/water discontinuities preserved
  - Graph Laplacian is symmetric
  - Parent pixel references preserved on every node
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..config import (
    GRAPH_BASE_LAPLACIAN_STRENGTH,
    GRAPH_CROSS_ROW_MULTIPLIER,
    GRAPH_EDGE_PENALTY_MULTIPLIER,
    GRAPH_IRRIGATION_CONNECTIVITY_WEIGHT,
    GRAPH_ROW_ALIGNED_MULTIPLIER,
    GRAPH_SOIL_DISCONTINUITY_MULTIPLIER,
)

logger = logging.getLogger(__name__)


# ── Node ────────────────────────────────────────────────────────────────────


@dataclass
class MicrozoneNode:
    """A single microzone in the spatial graph.

    Attributes:
        microzone_id: Unique ID (e.g. "mz_003_012" = row 3, col 12).
        row: Grid row index.
        col: Grid column index.
        resolution_m: Microzone cell size in meters.
        centroid: (x, y) centroid in CRS units.
        area_m2: Cell area in square meters.
        parent_sentinel_pixels: List of parent pixel IDs that overlap this zone.
        field_edge_distance_m: Distance to nearest field polygon boundary.
        row_direction_deg: Estimated crop row direction (0–180 degrees).
        soil_cluster_id: Soil similarity cluster this zone belongs to.
        irrigation_connectivity_group: Irrigation sector group.
    """
    microzone_id: str
    row: int
    col: int
    resolution_m: int

    centroid: Tuple[float, float] = (0.0, 0.0)
    area_m2: float = 0.0
    parent_sentinel_pixels: List[str] = field(default_factory=list)
    field_edge_distance_m: float = 0.0
    row_direction_deg: float = 0.0
    soil_cluster_id: str = "unknown"
    irrigation_connectivity_group: str = "unknown"
    biophysical_profile: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "microzone_id": self.microzone_id,
            "row": self.row,
            "col": self.col,
            "resolution_m": self.resolution_m,
            "centroid": list(self.centroid),
            "area_m2": self.area_m2,
            "parent_sentinel_pixels": self.parent_sentinel_pixels,
            "field_edge_distance_m": round(self.field_edge_distance_m, 2),
            "row_direction_deg": round(self.row_direction_deg, 2),
            "soil_cluster_id": self.soil_cluster_id,
            "irrigation_connectivity_group": self.irrigation_connectivity_group,
        }
        if self.biophysical_profile:
            d["biophysical_profile"] = self.biophysical_profile
        return d


# ── Edge ────────────────────────────────────────────────────────────────────


@dataclass
class MicrozoneEdge:
    """Weighted edge between two adjacent microzones.

    The combined weight controls spatial smoothing strength.
    Edge preservation penalty suppresses smoothing across boundaries.
    """
    source: str
    target: str

    distance_weight: float = 1.0
    row_alignment_weight: float = 1.0
    soil_similarity_weight: float = 1.0
    irrigation_connectivity_weight: float = 1.0
    edge_preservation_penalty: float = 0.0

    @property
    def combined_weight(self) -> float:
        """Combined edge weight for graph Laplacian.

        W_ij = w_dist * w_row * w_soil * w_irr * (1 - p_edge)
        """
        return (
            self.distance_weight
            * self.row_alignment_weight
            * self.soil_similarity_weight
            * self.irrigation_connectivity_weight
            * (1.0 - self.edge_preservation_penalty)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "distance_weight": round(self.distance_weight, 4),
            "row_alignment_weight": round(self.row_alignment_weight, 4),
            "soil_similarity_weight": round(self.soil_similarity_weight, 4),
            "irrigation_connectivity_weight": round(self.irrigation_connectivity_weight, 4),
            "edge_preservation_penalty": round(self.edge_preservation_penalty, 4),
            "combined_weight": round(self.combined_weight, 4),
        }


# ── Graph ───────────────────────────────────────────────────────────────────


class MicrozoneGraph:
    """Spatial graph of micro-zones at a given resolution.

    Deterministic for a given (geometry_hash, resolution_m).
    The graph Laplacian L = D - W is used for spatial smoothing priors
    in the EnKF (V74).

    Usage:
        graph = MicrozoneGraph(resolution_m=6, geometry_hash="abc123")
        graph.add_node(node)
        graph.add_edge(edge)
        L = graph.laplacian()
    """

    def __init__(
        self,
        resolution_m: int,
        geometry_hash: str = "",
        n_rows: int = 0,
        n_cols: int = 0,
        crs: str = "EPSG:4326",
        transform: Optional[Tuple[float, float, float, float, float, float]] = None,
        bounds: Optional[Tuple[float, float, float, float]] = None,
    ):
        self.resolution_m = resolution_m
        self.geometry_hash = geometry_hash
        self.n_rows = n_rows
        self.n_cols = n_cols
        self.crs = crs
        self.transform = transform
        self.bounds = bounds

        self._nodes: Dict[str, MicrozoneNode] = {}
        self._edges: List[MicrozoneEdge] = []
        self._adjacency: Dict[str, List[MicrozoneEdge]] = {}

    @property
    def grid_spec(self) -> Dict[str, Any]:
        return {
            "crs": self.crs,
            "transform": self.transform or (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            "bounds": self.bounds or (0.0, 0.0, 0.0, 0.0),
            "width": self.n_cols,
            "height": self.n_rows,
            "resolution_m": self.resolution_m,
        }

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def add_node(self, node: MicrozoneNode) -> None:
        self._nodes[node.microzone_id] = node

    def get_node(self, microzone_id: str) -> Optional[MicrozoneNode]:
        return self._nodes.get(microzone_id)

    def nodes(self) -> List[MicrozoneNode]:
        return list(self._nodes.values())

    def add_edge(self, edge: MicrozoneEdge) -> None:
        """Add a weighted edge (undirected — stored both ways)."""
        self._edges.append(edge)
        if edge.source not in self._adjacency:
            self._adjacency[edge.source] = []
        if edge.target not in self._adjacency:
            self._adjacency[edge.target] = []
        self._adjacency[edge.source].append(edge)
        # Symmetric: reverse edge with same weights
        reverse = MicrozoneEdge(
            source=edge.target,
            target=edge.source,
            distance_weight=edge.distance_weight,
            row_alignment_weight=edge.row_alignment_weight,
            soil_similarity_weight=edge.soil_similarity_weight,
            irrigation_connectivity_weight=edge.irrigation_connectivity_weight,
            edge_preservation_penalty=edge.edge_preservation_penalty,
        )
        self._adjacency[edge.target].append(reverse)

    def edges(self) -> List[MicrozoneEdge]:
        return list(self._edges)

    def neighbors(self, microzone_id: str) -> List[MicrozoneEdge]:
        """Get all edges from a node."""
        return self._adjacency.get(microzone_id, [])

    def node_ids_ordered(self) -> List[str]:
        """Return node IDs in deterministic row-major order."""
        return sorted(
            self._nodes.keys(),
            key=lambda k: (self._nodes[k].row, self._nodes[k].col),
        )

    def laplacian(self) -> Dict[str, Dict[str, float]]:
        """Compute the graph Laplacian L = D - W as a sparse dict-of-dicts.

        L_ii = sum of weights of edges incident to node i
        L_ij = -W_ij for adjacent nodes i, j
        L_ij = 0 for non-adjacent nodes

        The Laplacian is symmetric by construction (edges are undirected).

        Returns:
            Dict mapping node_id -> {neighbor_id: -weight, self: degree}.
        """
        L: Dict[str, Dict[str, float]] = {}

        for nid in self._nodes:
            L[nid] = {}

        for nid, adj_edges in self._adjacency.items():
            degree = 0.0
            for e in adj_edges:
                w = e.combined_weight * GRAPH_BASE_LAPLACIAN_STRENGTH
                if w > 1e-8:
                    target = e.target if e.source == nid else e.source
                    L[nid][target] = L[nid].get(target, 0.0) - w
                    degree += w
            L[nid][nid] = degree

        return L

    def laplacian_dense(self) -> list:
        """Compute Laplacian as a dense 2D list (for small graphs / tests).

        Row/col order follows node_ids_ordered().
        """
        ids = self.node_ids_ordered()
        n = len(ids)
        idx_map = {nid: i for i, nid in enumerate(ids)}

        dense = [[0.0] * n for _ in range(n)]
        L_sparse = self.laplacian()

        for nid, neighbors_dict in L_sparse.items():
            i = idx_map[nid]
            for target_id, val in neighbors_dict.items():
                j = idx_map.get(target_id)
                if j is not None:
                    dense[i][j] = val

        return dense

    def graph_hash(self) -> str:
        """Deterministic hash for reproducibility verification."""
        payload = {
            "geometry_hash": self.geometry_hash,
            "resolution_m": self.resolution_m,
            "n_rows": self.n_rows,
            "n_cols": self.n_cols,
            "nodes": sorted(self._nodes.keys()),
            "edges": [
                (e.source, e.target, round(e.combined_weight, 6))
                for e in sorted(self._edges, key=lambda e: (e.source, e.target))
            ],
        }
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def summary(self) -> Dict[str, Any]:
        return {
            "resolution_m": self.resolution_m,
            "geometry_hash": self.geometry_hash,
            "n_rows": self.n_rows,
            "n_cols": self.n_cols,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "graph_hash": self.graph_hash(),
        }


# ── Graph Builder ───────────────────────────────────────────────────────────


def build_microzone_graph(
    resolution_m: int,
    n_pixel_rows: int,
    n_pixel_cols: int,
    pixel_size_m: float,
    target_origin_x: float,
    target_origin_y: float,
    geometry_hash: str = "",
    polygon_points: Optional[List[Tuple[float, float]]] = None,
    row_direction_deg: float = 0.0,
    soil_clusters: Optional[Dict[str, str]] = None,
    irrigation_groups: Optional[Dict[str, str]] = None,
    biophysical_profiles: Optional[Dict[str, Any]] = None,
    crs: str = "EPSG:4326",
    n_zone_rows: Optional[int] = None,
    n_zone_cols: Optional[int] = None,
) -> MicrozoneGraph:
    """Build a MicrozoneGraph for a plot at a given resolution.

    Args:
        resolution_m: Target micro-zone resolution.
        n_pixel_rows: Number of parent pixel rows.
        n_pixel_cols: Number of parent pixel columns.
        pixel_size_m: Parent pixel size (e.g. 10m).
        target_origin_x: Fixed target grid origin X.
        target_origin_y: Fixed target grid origin Y.
        geometry_hash: Plot geometry hash for determinism.
        polygon_points: Field boundary polygon vertices [(x,y), ...].
        row_direction_deg: Estimated crop row direction.
        soil_clusters: {microzone_id: cluster_id} mapping.
        irrigation_groups: {microzone_id: group_id} mapping.
        biophysical_profiles: {microzone_id: profile} mapping.
        crs: Coordinate reference system.
        n_zone_rows: Optional fixed microzone row count from TargetMicrozoneGrid.
        n_zone_cols: Optional fixed microzone column count from TargetMicrozoneGrid.

    Returns:
        MicrozoneGraph with nodes and weighted edges.
    """
    from .neighborhoods import build_neighborhood_edges
    from .row_alignment import compute_row_alignment_weights
    from .soil_similarity import compute_soil_similarity_weights
    from .irrigation_connectivity import compute_irrigation_weights
    from .edge_preservation import compute_edge_penalties

    # Compute microzone grid dimensions
    if n_zone_cols is None or n_zone_rows is None:
        field_size_x = n_pixel_cols * pixel_size_m
        field_size_y = n_pixel_rows * pixel_size_m
        n_zone_cols = int(math.ceil(field_size_x / resolution_m))
        n_zone_rows = int(math.ceil(field_size_y / resolution_m))
    else:
        n_zone_cols = int(n_zone_cols)
        n_zone_rows = int(n_zone_rows)

    transform = (
        float(target_origin_x), float(resolution_m), 0.0,
        float(target_origin_y), 0.0, -float(resolution_m),
    )
    xmin = target_origin_x
    ymax = target_origin_y
    xmax = target_origin_x + n_zone_cols * resolution_m
    ymin = target_origin_y - n_zone_rows * resolution_m
    bounds = (xmin, ymin, xmax, ymax)

    graph = MicrozoneGraph(
        resolution_m=resolution_m,
        geometry_hash=geometry_hash,
        n_rows=n_zone_rows,
        n_cols=n_zone_cols,
        crs=crs,
        transform=transform,
        bounds=bounds,
    )

    # ── Create nodes ────────────────────────────────────────────────
    for zr in range(n_zone_rows):
        for zc in range(n_zone_cols):
            mz_id = f"mz_{zr:03d}_{zc:03d}"
            cx = target_origin_x + (zc + 0.5) * resolution_m
            cy = target_origin_y - (zr + 0.5) * resolution_m
            area = float(resolution_m * resolution_m)

            # Compute parent sentinel pixel references
            parents = _compute_parent_pixels(
                zr, zc, resolution_m, pixel_size_m, n_pixel_rows, n_pixel_cols,
            )

            # Soil and irrigation lookups
            soil_id = (soil_clusters or {}).get(mz_id, "unknown")
            irr_group = (irrigation_groups or {}).get(mz_id, "unknown")
            bio_prof = (biophysical_profiles or {}).get(mz_id)
            bio_dict = bio_prof.to_dict() if hasattr(bio_prof, "to_dict") else bio_prof

            node = MicrozoneNode(
                microzone_id=mz_id,
                row=zr,
                col=zc,
                resolution_m=resolution_m,
                centroid=(cx, cy),
                area_m2=area,
                parent_sentinel_pixels=parents,
                row_direction_deg=row_direction_deg,
                soil_cluster_id=soil_id,
                irrigation_connectivity_group=irr_group,
                biophysical_profile=bio_dict,
            )
            graph.add_node(node)

    # ── Create edges ────────────────────────────────────────────────
    # Step 1: Base neighborhood edges (8-connected)
    raw_edges = build_neighborhood_edges(
        n_zone_rows, n_zone_cols, polygon_points,
        target_origin_x, target_origin_y, resolution_m,
    )

    # Step 2: Compute row alignment weights
    row_weights = compute_row_alignment_weights(
        raw_edges, row_direction_deg, resolution_m,
    )

    # Step 3: Compute soil similarity weights
    soil_weights = compute_soil_similarity_weights(
        raw_edges, graph, soil_clusters,
    )

    # Step 4: Compute irrigation connectivity weights
    irr_weights = compute_irrigation_weights(
        raw_edges, graph, irrigation_groups,
    )

    # Step 5: Compute edge preservation penalties
    edge_penalties = compute_edge_penalties(
        raw_edges, polygon_points,
        target_origin_x, target_origin_y, resolution_m, graph,
    )

    # Step 6: Assemble final weighted edges
    for i, (src, tgt, dist_w) in enumerate(raw_edges):
        edge = MicrozoneEdge(
            source=src,
            target=tgt,
            distance_weight=dist_w,
            row_alignment_weight=row_weights[i],
            soil_similarity_weight=soil_weights[i],
            irrigation_connectivity_weight=irr_weights[i],
            edge_preservation_penalty=edge_penalties[i],
        )
        graph.add_edge(edge)

    logger.info(
        "V71 graph: %d nodes, %d edges, resolution=%dm, hash=%s",
        graph.node_count, graph.edge_count,
        resolution_m, graph.graph_hash()[:12],
    )

    return graph


def _compute_parent_pixels(
    zone_row: int,
    zone_col: int,
    zone_size_m: int,
    pixel_size_m: float,
    n_pixel_rows: int,
    n_pixel_cols: int,
) -> List[str]:
    """Find which parent Sentinel pixels overlap this microzone."""
    z_left = zone_col * zone_size_m
    z_right = z_left + zone_size_m
    z_top = zone_row * zone_size_m
    z_bottom = z_top + zone_size_m

    pr_start = max(0, int(math.floor(z_top / pixel_size_m)))
    pr_end = min(n_pixel_rows, int(math.ceil(z_bottom / pixel_size_m)))
    pc_start = max(0, int(math.floor(z_left / pixel_size_m)))
    pc_end = min(n_pixel_cols, int(math.ceil(z_right / pixel_size_m)))

    parents = []
    for pr in range(pr_start, pr_end):
        for pc in range(pc_start, pc_end):
            parents.append(f"px_{pr:03d}_{pc:03d}")

    return parents
