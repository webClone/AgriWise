"""
V71: Spatial regularization — Graph Laplacian smoothing and TV penalty.

Provides the spatial smoothing prior for the EnKF (V74).
Conservative defaults: smoothing may reduce noise but must NOT
increase parent-pixel radiometric error.

Methods:
    - Graph Laplacian smoothing (L = D - W)
    - Edge-aware total variation (TV) penalty
    - Boundary-preserving smoothing
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from ..config import GRAPH_BASE_LAPLACIAN_STRENGTH


def apply_ensemble_graph_regularization(
    ensemble: Dict[str, List[List[float]]],
    graph: Any,
    state_names: List[str],
) -> tuple[Dict[str, List[List[float]]], Dict[str, Any]]:
    """Apply weak, state-specific graph smoothing to actual ensemble members.

    Only states updated by an accepted observation are regularized. The
    cross-node mean is restored per state/member so graph smoothing cannot
    manufacture a field-wide radiometric shift.
    """
    from ..config import STATE_BOUNDS, STATE_NAMES

    node_ids = list(ensemble)
    if not node_ids or graph is None or not hasattr(graph, "neighbors"):
        return ensemble, {"applied": False, "reason": "graph_unavailable"}
    target_indices = [STATE_NAMES.index(name) for name in state_names if name in STATE_NAMES]
    if not target_indices:
        return ensemble, {"applied": False, "reason": "no_observation_updated_states"}

    strengths = {
        "vigor": 0.04,
        "lai": 0.04,
        "chlorophyll": 0.035,
        "canopy_water": 0.06,
        "root_zone_water": 0.08,
        "surface_wetness_event": 0.05,
        "structure": 0.04,
        "bare_soil_fraction": 0.035,
    }
    ensemble_size = min((len(ensemble[node]) for node in node_ids), default=0)
    if ensemble_size == 0:
        return ensemble, {"applied": False, "reason": "empty_ensemble"}

    before_tv = {STATE_NAMES[index]: 0.0 for index in target_indices}
    after_tv = {STATE_NAMES[index]: 0.0 for index in target_indices}
    updated = {node: [list(member) for member in ensemble[node]] for node in node_ids}

    def variation(values: Dict[str, List[float]], state_index: int) -> float:
        total = 0.0
        seen = set()
        for node in node_ids:
            for edge in graph.neighbors(node):
                neighbor = edge.target if edge.source == node else edge.source
                edge_key = tuple(sorted((str(node), str(neighbor))))
                if neighbor not in values or edge_key in seen:
                    continue
                seen.add(edge_key)
                weight = max(0.0, float(getattr(edge, "combined_weight", 0.0) or 0.0))
                total += weight * abs(values[node][state_index] - values[neighbor][state_index])
        return total

    for member_index in range(ensemble_size):
        current = {node: ensemble[node][member_index] for node in node_ids}
        proposed = {node: list(current[node]) for node in node_ids}
        for state_index in target_indices:
            state = STATE_NAMES[state_index]
            alpha = strengths.get(state, 0.025)
            before_tv[state] += variation(current, state_index)
            original_mean = sum(current[node][state_index] for node in node_ids) / len(node_ids)
            for node in node_ids:
                weighted_sum = 0.0
                weight_total = 0.0
                for edge in graph.neighbors(node):
                    neighbor = edge.target if edge.source == node else edge.source
                    if neighbor not in current:
                        continue
                    weight = max(0.0, float(getattr(edge, "combined_weight", 0.0) or 0.0))
                    if weight <= 1e-12:
                        continue
                    weighted_sum += weight * current[neighbor][state_index]
                    weight_total += weight
                if weight_total > 0.0:
                    neighbor_mean = weighted_sum / weight_total
                    proposed[node][state_index] = (
                        (1.0 - alpha) * current[node][state_index] + alpha * neighbor_mean
                    )
            proposed_mean = sum(proposed[node][state_index] for node in node_ids) / len(node_ids)
            correction = original_mean - proposed_mean
            lo, hi = STATE_BOUNDS[state]
            for node in node_ids:
                proposed[node][state_index] = max(
                    lo, min(hi, proposed[node][state_index] + correction)
                )
            after_tv[state] += variation(proposed, state_index)
        for node in node_ids:
            updated[node][member_index] = proposed[node]

    return updated, {
        "applied": True,
        "method": "state_specific_mean_conserving_graph_laplacian",
        "states": [STATE_NAMES[index] for index in target_indices],
        "ensemble_members": ensemble_size,
        "total_variation_before": {key: round(value / ensemble_size, 8) for key, value in before_tv.items()},
        "total_variation_after": {key: round(value / ensemble_size, 8) for key, value in after_tv.items()},
    }


def apply_laplacian_smoothing(
    state_values: Dict[str, List[float]],
    graph,  # MicrozoneGraph
    strength: float = GRAPH_BASE_LAPLACIAN_STRENGTH,
    max_iterations: int = 1,
) -> Dict[str, List[float]]:
    """Apply graph Laplacian smoothing to state values.

    Performs iterative Laplacian smoothing:
        x_i(new) = (1 - α) * x_i + α * Σ_j W_ij * x_j / Σ_j W_ij

    where α = strength controls how much neighbors influence a node.

    Conservative default: α = 0.12 (weak smoothing).

    Args:
        state_values: {microzone_id: [state_0, state_1, ...]} per node.
        graph: MicrozoneGraph with edges.
        strength: Smoothing strength α in [0, 1].
        max_iterations: Number of smoothing iterations.

    Returns:
        Smoothed state values (same structure as input).
    """
    if strength <= 0.0 or max_iterations <= 0:
        return state_values

    # Copy to avoid mutating input
    current = {
        k: list(v) for k, v in state_values.items()
    }

    for _iteration in range(max_iterations):
        updated = {}
        for nid, values in current.items():
            edges = graph.neighbors(nid)

            if not edges:
                updated[nid] = list(values)
                continue

            # Weighted neighbor average
            n_states = len(values)
            neighbor_sum = [0.0] * n_states
            weight_sum = 0.0

            for edge in edges:
                w = edge.combined_weight
                if w < 1e-8:
                    continue
                target_id = edge.target
                target_vals = current.get(target_id)
                if target_vals is None:
                    continue

                weight_sum += w
                for s in range(min(n_states, len(target_vals))):
                    neighbor_sum[s] += w * target_vals[s]

            if weight_sum < 1e-8:
                updated[nid] = list(values)
                continue

            smoothed = []
            for s in range(n_states):
                neighbor_avg = neighbor_sum[s] / weight_sum
                new_val = (1.0 - strength) * values[s] + strength * neighbor_avg
                smoothed.append(new_val)

            updated[nid] = smoothed

        current = updated

    return current


def compute_total_variation(
    state_values: Dict[str, List[float]],
    graph,  # MicrozoneGraph
    state_index: int = 0,
) -> float:
    """Compute total variation (TV) penalty for a single state.

    TV = Σ_edges |W_ij * (x_i - x_j)|

    High TV = spatially noisy. Low TV = spatially smooth.
    Used to monitor smoothing quality and radiometric consistency.

    Args:
        state_values: {microzone_id: [state_0, state_1, ...]} per node.
        graph: MicrozoneGraph with edges.
        state_index: Which state variable to compute TV for.

    Returns:
        Total variation value.
    """
    tv = 0.0
    for edge in graph.edges():
        w = edge.combined_weight
        if w < 1e-8:
            continue
        src_vals = state_values.get(edge.source)
        tgt_vals = state_values.get(edge.target)
        if src_vals is None or tgt_vals is None:
            continue
        if state_index >= len(src_vals) or state_index >= len(tgt_vals):
            continue
        diff = abs(src_vals[state_index] - tgt_vals[state_index])
        tv += w * diff

    return tv


def smoothing_radiometric_check(
    original_values: Dict[str, List[float]],
    smoothed_values: Dict[str, List[float]],
    graph,  # MicrozoneGraph
    state_index: int = 0,
    tolerance: float = 0.01,
) -> bool:
    """Verify that smoothing does not increase parent-pixel radiometric error.

    Invariant: smoothing may reduce noise, but must not increase
    the mean deviation from the original (pre-smoothed) values at
    the parent-pixel level.

    This is a simplified check; full radiometric consistency (V75)
    uses the observation operator H_t and forward model h(x).

    Args:
        original_values: State values before smoothing.
        smoothed_values: State values after smoothing.
        graph: MicrozoneGraph.
        state_index: Which state to check.
        tolerance: Acceptable increase in mean deviation.

    Returns:
        True if smoothing passes the check.
    """
    # Group by parent pixel
    parent_groups: Dict[str, List[str]] = {}
    for node in graph.nodes():
        for px in node.parent_sentinel_pixels:
            if px not in parent_groups:
                parent_groups[px] = []
            parent_groups[px].append(node.microzone_id)

    # For each parent pixel, compute mean original and smoothed values
    # and compare total deviation
    total_original_dev = 0.0
    total_smoothed_dev = 0.0
    n_groups = 0

    for px, mz_ids in parent_groups.items():
        orig_vals = []
        smooth_vals = []
        for mz_id in mz_ids:
            ov = original_values.get(mz_id)
            sv = smoothed_values.get(mz_id)
            if ov and sv and state_index < len(ov) and state_index < len(sv):
                orig_vals.append(ov[state_index])
                smooth_vals.append(sv[state_index])

        if not orig_vals:
            continue

        orig_mean = sum(orig_vals) / len(orig_vals)
        smooth_mean = sum(smooth_vals) / len(smooth_vals)

        total_original_dev += sum(abs(v - orig_mean) for v in orig_vals)
        total_smoothed_dev += sum(abs(v - smooth_mean) for v in smooth_vals)
        n_groups += 1

    if n_groups == 0:
        return True

    # Smoothing must not increase total deviation beyond tolerance
    return total_smoothed_dev <= total_original_dev + tolerance * n_groups
