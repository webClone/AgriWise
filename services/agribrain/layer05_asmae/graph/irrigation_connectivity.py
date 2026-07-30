"""
V71: Irrigation connectivity weights for microzone graph edges.

Microzones sharing the same irrigation sector/group (e.g., pivot sector,
drip zone) get a connectivity boost, reflecting that water application
patterns are correlated within the same irrigation infrastructure.

Important for Algeria/MENA irrigated contexts (pivots, drip, flood).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..config import GRAPH_IRRIGATION_CONNECTIVITY_WEIGHT


def compute_irrigation_weights(
    edges: List[Tuple[str, str, float]],
    graph,  # MicrozoneGraph (avoid circular import)
    irrigation_groups: Optional[Dict[str, str]] = None,
    same_group_weight: float = 1.0,
    different_group_weight: float = GRAPH_IRRIGATION_CONNECTIVITY_WEIGHT,
) -> List[float]:
    """Compute irrigation connectivity weight for each edge.

    Same irrigation group: full smoothing (1.0).
    Different groups: reduced smoothing (0.6) to preserve
    irrigation boundary discontinuities.

    Args:
        edges: List of (source_id, target_id, dist_weight) tuples.
        graph: MicrozoneGraph with node irrigation_connectivity_group.
        irrigation_groups: Optional {mz_id: group_id} override.
        same_group_weight: Weight for same-group edges.
        different_group_weight: Weight for different-group edges.

    Returns:
        List of irrigation_connectivity_weight values, one per edge.
    """
    weights: List[float] = []

    for src_id, tgt_id, _ in edges:
        src_group = _get_irr_group(src_id, graph, irrigation_groups)
        tgt_group = _get_irr_group(tgt_id, graph, irrigation_groups)

        if src_group == "unknown" or tgt_group == "unknown":
            # Unknown irrigation: neutral weight
            weights.append(1.0)
        elif src_group == tgt_group:
            weights.append(same_group_weight)
        else:
            weights.append(different_group_weight)

    return weights


def _get_irr_group(
    mz_id: str,
    graph,
    irrigation_groups: Optional[Dict[str, str]],
) -> str:
    """Look up irrigation group for a microzone."""
    if irrigation_groups and mz_id in irrigation_groups:
        return irrigation_groups[mz_id]
    node = graph.get_node(mz_id)
    if node is not None:
        return node.irrigation_connectivity_group
    return "unknown"
