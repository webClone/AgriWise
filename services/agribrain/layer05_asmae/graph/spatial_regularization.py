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
from typing import Any, Callable, Dict, List, Optional

from ..config import GRAPH_BASE_LAPLACIAN_STRENGTH


def apply_ensemble_graph_regularization(
    ensemble: Any,
    graph: Any,
    state_names: List[str],
    deadline_check: Optional[Callable[[], None]] = None,
) -> tuple[Any, Dict[str, Any]]:
    """Apply weak, state-specific graph smoothing to actual ensemble members.

    Only states updated by an accepted observation are regularized. The
    cross-node mean is restored per state/member so graph smoothing cannot
    manufacture a field-wide radiometric shift.
    """
    import numpy as np

    from ..config import STATE_BOUNDS, STATE_NAMES

    is_ndarray = isinstance(ensemble, np.ndarray)
    if is_ndarray:
        values = ensemble
        if hasattr(graph, "node_ids_ordered"):
            node_ids = graph.node_ids_ordered()
        elif hasattr(graph, "nodes"):
            node_ids = [n.microzone_id for n in graph.nodes()]
        else:
            node_ids = [f"mz_{i}" for i in range(values.shape[0])]
    else:
        node_ids = list(ensemble)
    if not node_ids or graph is None or not hasattr(graph, "neighbors"):
        return ensemble, {"applied": False, "reason": "graph_unavailable"}
    target_indices = list(dict.fromkeys(
        STATE_NAMES.index(name) for name in state_names if name in STATE_NAMES
    ))
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
    if is_ndarray:
        ensemble_size = values.shape[1]
    else:
        ensemble_size = min((len(ensemble[node]) for node in node_ids), default=0)
    if ensemble_size == 0:
        return ensemble, {"applied": False, "reason": "empty_ensemble"}

    if deadline_check is not None:
        deadline_check()

    if not is_ndarray:
        values = np.asarray([ensemble[node] for node in node_ids], dtype=float)
    if values.shape != (len(node_ids), ensemble_size, len(STATE_NAMES)):
        return ensemble, {"applied": False, "reason": "ensemble_shape_mismatch"}

    cached_edges = getattr(graph, "_cached_edge_arrays", None)
    if cached_edges is not None and len(cached_edges) == 3 and cached_edges[0].size > 0:
        source_array, target_array, weight_array = cached_edges
    else:
        node_positions = {node: position for position, node in enumerate(node_ids)}
        sources: List[int] = []
        targets: List[int] = []
        weights: List[float] = []
        for edge in graph.edges():
            source = node_positions.get(str(getattr(edge, "source", "")))
            target = node_positions.get(str(getattr(edge, "target", "")))
            weight = max(0.0, float(getattr(edge, "combined_weight", 0.0) or 0.0))
            if source is None or target is None or weight <= 1e-12:
                continue
            sources.append(source)
            targets.append(target)
            weights.append(weight)
        if not weights:
            return ensemble, {"applied": False, "reason": "graph_has_no_weighted_edges"}

        source_array = np.asarray(sources, dtype=int)
        target_array = np.asarray(targets, dtype=int)
        weight_array = np.asarray(weights, dtype=float)
        try:
            graph._cached_edge_arrays = (source_array, target_array, weight_array)
        except Exception:
            pass
    selected = values[:, :, target_indices]

    # Compute weighted neighbour means for every member and selected state in
    # one edge pass. MicrozoneGraph stores each undirected edge once in
    # ``edges()``; accumulate both directions to match ``neighbors()``.
    weighted_sum = np.zeros_like(selected)
    weighted_degree = np.zeros(len(node_ids), dtype=float)
    chunk_size = 50000
    n_edges = source_array.shape[0]
    for start_idx in range(0, n_edges, chunk_size):
        end_idx = min(start_idx + chunk_size, n_edges)
        s_chunk = source_array[start_idx:end_idx]
        t_chunk = target_array[start_idx:end_idx]
        w_chunk = weight_array[start_idx:end_idx, None, None]
        np.add.at(weighted_sum, s_chunk, w_chunk * selected[t_chunk])
        np.add.at(weighted_sum, t_chunk, w_chunk * selected[s_chunk])
    np.add.at(weighted_degree, source_array, weight_array)
    np.add.at(weighted_degree, target_array, weight_array)

    neighbour_mean = selected.copy()
    active = weighted_degree > 1e-12
    neighbour_mean[active] = (
        weighted_sum[active] / weighted_degree[active, None, None]
    )
    alpha = np.asarray(
        [strengths.get(STATE_NAMES[index], 0.025) for index in target_indices],
        dtype=float,
    )[None, None, :]
    proposed = (1.0 - alpha) * selected + alpha * neighbour_mean

    # Restore each state/member's cross-node mean exactly as the scalar
    # implementation did, then enforce physical state bounds.
    proposed += (
        np.mean(selected, axis=0, keepdims=True)
        - np.mean(proposed, axis=0, keepdims=True)
    )
    lows = np.asarray(
        [STATE_BOUNDS[STATE_NAMES[index]][0] for index in target_indices],
        dtype=float,
    )[None, None, :]
    highs = np.asarray(
        [STATE_BOUNDS[STATE_NAMES[index]][1] for index in target_indices],
        dtype=float,
    )[None, None, :]
    proposed = np.clip(proposed, lows, highs)

    before_totals = np.zeros(len(target_indices), dtype=float)
    after_totals = np.zeros(len(target_indices), dtype=float)
    for start_idx in range(0, n_edges, chunk_size):
        end_idx = min(start_idx + chunk_size, n_edges)
        s_chunk = source_array[start_idx:end_idx]
        t_chunk = target_array[start_idx:end_idx]
        w_chunk = weight_array[start_idx:end_idx, None, None]
        before_totals += np.sum(w_chunk * np.abs(selected[s_chunk] - selected[t_chunk]), axis=(0, 1))
        after_totals += np.sum(w_chunk * np.abs(proposed[s_chunk] - proposed[t_chunk]), axis=(0, 1))

    values[:, :, target_indices] = proposed
    if is_ndarray:
        updated = values
    else:
        updated = {
            node: values[position].tolist()
            for position, node in enumerate(node_ids)
        }
    if deadline_check is not None:
        deadline_check()

    return updated, {
        "applied": True,
        "method": "state_specific_mean_conserving_graph_laplacian",
        "states": [STATE_NAMES[index] for index in target_indices],
        "ensemble_members": ensemble_size,
        "total_variation_before": {
            STATE_NAMES[index]: round(float(before_totals[offset]) / ensemble_size, 8)
            for offset, index in enumerate(target_indices)
        },
        "total_variation_after": {
            STATE_NAMES[index]: round(float(after_totals[offset]) / ensemble_size, 8)
            for offset, index in enumerate(target_indices)
        },
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
