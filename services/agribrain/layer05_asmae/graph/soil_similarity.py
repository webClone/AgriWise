"""
V71: Soil similarity weights for microzone graph edges.

Edges between microzones in the same soil cluster get higher smoothing
weight; edges between different soil clusters get reduced weight to
preserve soil discontinuities.

Default: soil_discontinuity_multiplier = 0.3
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..config import GRAPH_SOIL_DISCONTINUITY_MULTIPLIER


def compute_soil_similarity_weights(
    edges: List[Tuple[str, str, float]],
    graph,  # MicrozoneGraph (avoid circular import)
    soil_clusters: Optional[Dict[str, str]] = None,
    same_cluster_weight: float = 1.0,
    different_cluster_weight: float = GRAPH_SOIL_DISCONTINUITY_MULTIPLIER,
) -> List[float]:
    """Compute soil similarity weight for each edge.

    If two adjacent microzones belong to the same soil cluster,
    weight = 1.0 (full smoothing allowed).
    If different clusters, weight = 0.3 (reduced smoothing to
    preserve soil discontinuities).

    Args:
        edges: List of (source_id, target_id, dist_weight) tuples.
        graph: MicrozoneGraph with node soil_cluster_id attributes.
        soil_clusters: Optional {mz_id: cluster_id} override.
        same_cluster_weight: Weight for same-cluster edges.
        different_cluster_weight: Weight for different-cluster edges.

    Returns:
        List of soil_similarity_weight values, one per edge.
    """
    weights: List[float] = []

    for src_id, tgt_id, _ in edges:
        src_cluster = _get_soil_cluster(src_id, graph, soil_clusters)
        tgt_cluster = _get_soil_cluster(tgt_id, graph, soil_clusters)

        if src_cluster == "unknown" or tgt_cluster == "unknown":
            # Unknown soil: use neutral weight (neither boost nor suppress)
            weights.append(1.0)
        elif src_cluster == tgt_cluster:
            weights.append(same_cluster_weight)
        else:
            weights.append(different_cluster_weight)

    return weights


def _get_soil_cluster(
    mz_id: str,
    graph,
    soil_clusters: Optional[Dict[str, str]],
) -> str:
    """Look up soil cluster for a microzone."""
    # Explicit override takes priority
    if soil_clusters and mz_id in soil_clusters:
        return soil_clusters[mz_id]
    # Fall back to graph node attribute
    node = graph.get_node(mz_id)
    if node is not None:
        return node.soil_cluster_id
    return "unknown"
