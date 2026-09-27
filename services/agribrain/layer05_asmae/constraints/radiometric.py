"""
V79A Phase 4 / V922.2A: Hₜ-aware radiometric consistency.

Per-observation modes:
  - ht_per_pixel: exact H_t @ h(x̂) vs matching per-pixel y_obs
  - ht_support_mismatch: pixel vectors do not have the exact H_t row count
  - ht_shape_mismatch: H_t columns do not match the state graph
  - ht_scalar_observation_unsupported: no pixel-level evidence exists
  - ht_no_valid_support / ht_projection_failed: unusable proof paths
  - proxy_average: no H_t matrix available (never full scientific credit)

Top-level radiometric_mode:
  - "ht_per_pixel" only if ALL checked observations used true per-pixel mode
  - "mixed_ht_modes" if a mix of Hₜ-based modes was used
  - "proxy_average" if no H_t was used

Per-observation thresholds, aligned observation vectors, valid mask.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from ..config import RADIOMETRIC_THRESHOLDS_BY_OBS

logger = logging.getLogger(__name__)


def enforce_radiometric_consistency(
    state_estimates: Dict[str, List[float]],
    observations: Dict[str, float],
    graph: Any,
    operators: Optional[list] = None,
    scenes: Optional[list] = None,
    expected_resolution_m: Optional[int] = None,
    state_timeline: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Enforce H_t · h(x̂_t) ≈ y_t for all available observations.

    V79A: Uses real Hₜ projection when operators have H_matrix.
    Falls back to proxy_average otherwise (marked as non-scientific).
    V922: Asserts operators match expected resolution if provided.
    V922.2A: Truthful per-observation mode labeling (5 modes).
    Compares observation at time t with estimated state at time t using state_timeline.
    """
    # V922: Chain integrity assertion — operators must match resolution
    if expected_resolution_m is not None and operators:
        from ..chain_integrity import assert_operators_match_resolution
        assert_operators_match_resolution(
            operators, expected_resolution_m, stage_name="radiometric",
        )

    from ..observation.s2_forward_model import FORWARD_MODELS
    from ..observation.s1_sar_model import SAR_FORWARD_MODELS
    from ..observation.index_state_mapping import INDEX_STATE_REGISTRY

    all_forward = {**FORWARD_MODELS, **SAR_FORWARD_MODELS}

    # Try Hₜ-aware mode first
    has_real_ht = _check_operators_have_ht(operators)

    if has_real_ht and operators and scenes:
        result = _enforce_ht_per_pixel(
            state_estimates, operators, scenes, all_forward,
            state_timeline=state_timeline,
        )
    else:
        result = _enforce_proxy_average(
            state_estimates, observations, all_forward,
        )
        result["radiometric_mode"] = "proxy_average"
        result["has_shape_fallback"] = False
        result["has_scalar_observation_fallback"] = False
        result["has_resampled_observation"] = False
        result["full_radiometric_credit_allowed"] = False
        result["observation_mode_counts"] = {"proxy_average": result["n_checked"]}
        return result

    # V922.2A: Derive top-level mode from per-observation modes
    mode_counts: Dict[str, int] = {}
    has_shape_fallback = False
    has_scalar_fallback = False
    has_resampled = False
    has_missing_snapshot = False

    # A given observation type can occur in several scenes.  Derive authority
    # from the complete check ledger; ``per_index`` is only the worst-case
    # observation-type summary retained for backwards compatibility.
    checked_records = result.get("per_scene_observation")
    if not isinstance(checked_records, list):
        checked_records = list(result.get("per_index", {}).values())
    for obs_data in checked_records:
        method = obs_data.get("predicted_method", "proxy_average")
        mode_counts[method] = mode_counts.get(method, 0) + 1
        if method in ("ht_shape_fallback_average", "ht_shape_mismatch"):
            has_shape_fallback = True
        if method in (
            "ht_geometry_with_mean_observation",
            "ht_scalar_observation_unsupported",
        ):
            has_scalar_fallback = True
        if method == "ht_resampled_observation":
            has_resampled = True
        if method in ("ht_missing_state_snapshot", "ht_missing_node_state"):
            has_missing_snapshot = True

    # Top-level mode: ht_per_pixel ONLY if all observations used it
    if len(mode_counts) == 0:
        top_mode = "proxy_average"
    elif len(mode_counts) == 1 and "ht_per_pixel" in mode_counts:
        top_mode = "ht_per_pixel"
    elif has_missing_snapshot:
        top_mode = "degraded_missing_snapshot"
    else:
        top_mode = "mixed_ht_modes"

    # Full credit: only if ALL observations used true Hₜ per-pixel,
    # at least one primary observation was checked, the primary chain passed,
    # and no fallbacks occurred
    full_credit = (
        top_mode == "ht_per_pixel"
        and result.get("overall_pass", False) is True
        and result.get("primary_checked_count", 0) > 0
        and not has_shape_fallback
        and not has_scalar_fallback
        and not has_resampled
        and not has_missing_snapshot
    )

    result["radiometric_mode"] = top_mode
    result["has_shape_fallback"] = has_shape_fallback
    result["has_scalar_observation_fallback"] = has_scalar_fallback
    result["has_resampled_observation"] = has_resampled
    result["has_missing_snapshot"] = has_missing_snapshot
    result["has_alignment_rejection"] = any(
        method != "ht_per_pixel" for method in mode_counts
    )
    result["full_radiometric_credit_allowed"] = full_credit
    result["observation_mode_counts"] = mode_counts

    return result


def _check_operators_have_ht(operators: Optional[list]) -> bool:
    """Check if any operator has a real H_matrix."""
    if not operators:
        return False
    for op in operators:
        h_matrix = getattr(op, "H_matrix", None)
        if h_matrix is not None:
            return True
    return False



# Primary physical satellite observation channels whose rejection vetoes
# overall_pass.  Derived diagnostic proxies (cwsi, stress_memory_index,
# biotic_anomaly, phenology_index, evi, bsi, nbr, ndsi, sar_ratio) are
# auxiliary indices: their status and actions are recorded, but a rejection
# on an auxiliary index does not block certification of the primary sensor
# chain.
PRIMARY_OBSERVATIONS = {"ndvi", "ndre", "ndmi", "ndwi", "sar_vv", "sar_vh"}


def _enforce_ht_per_pixel(
    state_estimates: Dict[str, List[float]],
    operators: list,
    scenes: list,
    all_forward: dict,
    state_timeline: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """V79B: Real Hₜ-aware radiometric check with per-pixel y_obs.

    Only an exact scene/operator/support binding and equal pixel-vector length
    can produce a radiometric score. Mismatches are explicit rejections; no
    resampling, padding, scalar broadcasting, or mean fallback is permitted.

    For each scene/operator pair and each observation type:
      1. Compute h(x̂_t) per microzone from state estimated at time t → h_vector
      2. Project: y_pred = H_t @ h_vector
      3. Extract y_obs = real per-pixel observation vector from scene
      4. Compute RMSE over valid pixels: RMSE(y_pred[valid], y_obs[valid])

    overall_pass reflects primary sensor certification only.  Auxiliary proxy
    indices are recorded with full status but cannot veto the primary chain.
    """
    from ..observation.pixel_extraction import extract_pixel_observations
    from ..observation.index_state_mapping import INDEX_STATE_REGISTRY
    from ..config import STATE_NAMES

    results: Dict[str, Dict[str, Any]] = {}
    check_ledger: List[Dict[str, Any]] = []
    actions: List[str] = []
    n_primary_checked = 0
    n_primary_rejected = 0
    blocked_states: set[str] = set()
    blocked_observations: set[str] = set()

    node_ids = sorted(state_estimates.keys())
    from ..chain_integrity import assert_scene_operator_binding
    assert_scene_operator_binding(scenes, operators, stage_name="radiometric")

    # Map operators by scene_id for safe, non-positional binding
    op_by_scene_id = {
        str(getattr(op, "scene_id", "")): op
        for op in operators
        if getattr(op, "scene_id", None)
    }

    timeline_by_scene_id: Dict[str, Dict[str, List[float]]] = {}
    if state_timeline:
        for snap in state_timeline:
            if isinstance(snap, dict) and snap.get("scene_id") and snap.get("means"):
                timeline_by_scene_id[str(snap["scene_id"])] = snap["means"]

    for scene in scenes:
        scene_id = str(getattr(scene, "scene_id", ""))
        op = op_by_scene_id.get(scene_id)
        if op is None:
            continue
        h_matrix = getattr(op, "H_matrix", None)
        if h_matrix is None:
            continue

        snapshot_missing = False
        if state_timeline is not None:
            if scene_id in timeline_by_scene_id:
                scene_state_estimates = timeline_by_scene_id[scene_id]
            else:
                snapshot_missing = True
                scene_state_estimates = None
        else:
            scene_state_estimates = state_estimates

        # V79B: Per-pixel observation extraction
        pixel_obs = extract_pixel_observations(scene)

        for obs_name, pix_obs in pixel_obs.items():
            forward_fn = all_forward.get(obs_name)
            if forward_fn is None:
                continue

            thresholds = RADIOMETRIC_THRESHOLDS_BY_OBS.get(
                obs_name, {"pass": 0.15, "reject": 0.30}
            )

            actual_method = "ht_per_pixel"
            observation_source = "per_pixel"
            rejection_reason: Optional[str] = None
            rmse: Optional[float] = None
            n_valid_pixels = 0

            if snapshot_missing or scene_state_estimates is None:
                actual_method = "ht_missing_state_snapshot"
                observation_source = "none"
                rejection_reason = f"timeline_snapshot_missing_for_scene_{scene_id}"
            else:
                # Compute h(x̂_t) per microzone using estimated state at time t
                h_vector = []
                node_missing = False
                for nid in node_ids:
                    if nid not in scene_state_estimates:
                        node_missing = True
                        break
                    h_vector.append(forward_fn(scene_state_estimates[nid]))

                if node_missing:
                    actual_method = "ht_missing_node_state"
                    observation_source = "none"
                    rejection_reason = f"snapshot_missing_microzone_state_in_scene_{scene_id}"
                else:
                    try:
                        import numpy as np
                        h_vec = np.asarray(h_vector, dtype=float)

                        if h_matrix.shape[1] != len(h_vector):
                            actual_method = "ht_shape_mismatch"
                            observation_source = "none"
                            rejection_reason = "operator_columns_do_not_match_state_graph"
                        elif not pix_obs.is_per_pixel:
                            actual_method = "ht_scalar_observation_unsupported"
                            observation_source = "scalar_mean"
                            rejection_reason = "pixel_level_observation_required"
                        else:
                            y_pred = np.asarray(h_matrix @ h_vec, dtype=float).reshape(-1)
                            n_pixels = int(y_pred.size)
                            if pix_obs.n_pixels != n_pixels:
                                actual_method = "ht_support_mismatch"
                                observation_source = "misaligned_per_pixel"
                                rejection_reason = (
                                    f"observation_pixels={pix_obs.n_pixels},"
                                    f"operator_rows={n_pixels}"
                                )
                            else:
                                y_obs = np.asarray(pix_obs.values, dtype=float).reshape(-1)
                                valid_mask = np.asarray(
                                    pix_obs.valid_mask, dtype=bool,
                                ).reshape(-1)
                                valid_mask &= np.isfinite(y_obs) & np.isfinite(y_pred)
                                n_valid_pixels = int(np.count_nonzero(valid_mask))
                                if n_valid_pixels == 0:
                                    actual_method = "ht_no_valid_support"
                                    rejection_reason = "no_finite_shared_pixel_support"
                                else:
                                    residual = y_pred[valid_mask] - y_obs[valid_mask]
                                    rmse = float(np.sqrt(np.mean(residual ** 2)))
                    except ImportError:
                        actual_method = "ht_runtime_unavailable"
                        observation_source = "none"
                        rejection_reason = "numpy_unavailable"
                    except Exception as exc:
                        actual_method = "ht_projection_failed"
                        observation_source = "none"
                        rejection_reason = f"{type(exc).__name__}:{exc}"

            # Determine per-observation status
            is_primary = obs_name in PRIMARY_OBSERVATIONS
            if is_primary:
                n_primary_checked += 1

            if rmse is None:
                status = "reject"
                if is_primary:
                    n_primary_rejected += 1
                blocked_observations.add(obs_name)
                mapping = INDEX_STATE_REGISTRY.get(obs_name)
                if mapping:
                    for s_idx in mapping.target_state_indices:
                        if s_idx < len(STATE_NAMES):
                            blocked_states.add(STATE_NAMES[s_idx])
                elif obs_name in STATE_NAMES:
                    blocked_states.add(obs_name)
                if obs_name == "evi":
                    blocked_states.add("vigor")
                actions.append(f"demote_resolution:{obs_name}")
                actions.append(f"block_state_update:{obs_name}")
            elif rmse <= thresholds["pass"]:
                status = "pass"
            elif rmse <= thresholds["reject"]:
                status = "warning"
                actions.append(f"increase_uncertainty:{obs_name}")
            else:
                status = "reject"
                if is_primary:
                    n_primary_rejected += 1
                blocked_observations.add(obs_name)
                mapping = INDEX_STATE_REGISTRY.get(obs_name)
                if mapping:
                    for s_idx in mapping.target_state_indices:
                        if s_idx < len(STATE_NAMES):
                            blocked_states.add(STATE_NAMES[s_idx])
                elif obs_name in STATE_NAMES:
                    blocked_states.add(obs_name)
                if obs_name == "evi":
                    blocked_states.add("vigor")
                actions.append(f"demote_resolution:{obs_name}")
                actions.append(f"block_state_update:{obs_name}")

            scene_id = str(getattr(scene, "scene_id", "unknown_scene"))
            record = {
                "scene_id": scene_id,
                "observation_type": obs_name,
                "predicted_method": actual_method,
                "observation_source": observation_source,
                "n_valid_pixels": n_valid_pixels,
                "rmse": round(rmse, 6) if rmse is not None else None,
                "rejection_reason": rejection_reason,
                "threshold_pass": thresholds["pass"],
                "threshold_reject": thresholds["reject"],
                "status": status,
                "is_primary": is_primary,
            }
            check_ledger.append(record)

            # Keep the most severe (then largest-error) record as the compact
            # per-observation summary.  The previous implementation silently
            # overwrote failures when a later scene used the same index.
            previous = results.get(obs_name)
            severity = {"pass": 0, "warning": 1, "reject": 2}
            if (
                previous is None
                or severity.get(status, 3) > severity.get(previous.get("status"), 3)
                or (
                    severity.get(status, 3) == severity.get(previous.get("status"), 3)
                    and (
                        float("inf") if record["rmse"] is None else record["rmse"]
                    ) > (
                        float("inf")
                        if previous.get("rmse") is None
                        else previous.get("rmse", -1.0)
                    )
                )
            ):
                results[obs_name] = dict(record)

    overall_pass = bool(n_primary_checked > 0 and n_primary_rejected == 0)
    for s_name in sorted(blocked_states):
        actions.append(f"block_state_export:{s_name}")

    return {
        "per_index": results,
        "per_scene_observation": check_ledger,
        "overall_pass": overall_pass,
        "primary_checked_count": n_primary_checked,
        "primary_rejected_count": n_primary_rejected,
        "blocked_states": sorted(list(blocked_states)),
        "blocked_observations": sorted(list(blocked_observations)),
        "actions": actions,
        "n_checked": len(check_ledger),
    }


def _enforce_proxy_average(
    state_estimates: Dict[str, List[float]],
    observations: Dict[str, float],
    all_forward: dict,
) -> Dict[str, Any]:
    """Proxy average check (no Hₜ). Cannot pass for scientific purposes."""
    from ..observation.index_state_mapping import INDEX_STATE_REGISTRY
    from ..config import STATE_NAMES

    results: Dict[str, Dict[str, Any]] = {}
    actions: List[str] = []
    n_primary_checked = 0
    n_primary_rejected = 0
    blocked_states: set[str] = set()
    blocked_observations: set[str] = set()

    for obs_name, obs_value in observations.items():
        forward_fn = all_forward.get(obs_name)
        if forward_fn is None:
            continue

        thresholds = RADIOMETRIC_THRESHOLDS_BY_OBS.get(
            obs_name, {"pass": 0.15, "reject": 0.30}
        )

        predicted_values = [forward_fn(state) for state in state_estimates.values()]
        if not predicted_values:
            continue

        pred_mean = sum(predicted_values) / len(predicted_values)
        rmse = abs(pred_mean - obs_value)

        is_primary = obs_name in PRIMARY_OBSERVATIONS
        if is_primary:
            n_primary_checked += 1

        if rmse <= thresholds["pass"]:
            status = "pass"
        elif rmse <= thresholds["reject"]:
            status = "warning"
            actions.append(f"increase_uncertainty:{obs_name}")
        else:
            status = "reject"
            if is_primary:
                n_primary_rejected += 1
            blocked_observations.add(obs_name)
            mapping = INDEX_STATE_REGISTRY.get(obs_name)
            if mapping:
                for s_idx in mapping.target_state_indices:
                    if s_idx < len(STATE_NAMES):
                        blocked_states.add(STATE_NAMES[s_idx])
            elif obs_name in STATE_NAMES:
                blocked_states.add(obs_name)
            if obs_name == "evi":
                blocked_states.add("vigor")
            actions.append(f"demote_resolution:{obs_name}")
            actions.append(f"block_state_update:{obs_name}")

        results[obs_name] = {
            "predicted_method": "proxy_average",
            "observation_source": "scalar_mean",
            "rmse": round(rmse, 6),
            "threshold_pass": thresholds["pass"],
            "threshold_reject": thresholds["reject"],
            "status": status,
            "is_primary": is_primary,
        }

    overall_pass = bool(n_primary_checked > 0 and n_primary_rejected == 0)
    for s_name in sorted(blocked_states):
        actions.append(f"block_state_export:{s_name}")

    return {
        "per_index": results,
        "overall_pass": overall_pass,
        "primary_checked_count": n_primary_checked,
        "primary_rejected_count": n_primary_rejected,
        "blocked_states": sorted(list(blocked_states)),
        "blocked_observations": sorted(list(blocked_observations)),
        "actions": actions,
        "n_checked": len(results),
    }
