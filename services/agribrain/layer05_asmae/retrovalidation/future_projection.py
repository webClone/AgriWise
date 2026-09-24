"""V79B: Forward prediction on held-out scenes using Hₜ and per-pixel obs.

Replaces mean-level holdout scoring with:
  y_pred = H_holdout @ h(x_training)
  y_obs  = real per-pixel observation vector from held-out scene
  error  = RMSE(y_pred[valid], y_obs[valid])
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def predict_held_out_scene(
    training_state: Dict[str, List[float]],
    holdout_scene: Any,
    operator: Optional[Any] = None,
) -> Dict[str, Any]:
    import math
    import numpy as np

    from ..observation.index_state_mapping import INDEX_STATE_REGISTRY
    from ..observation.pixel_extraction import extract_pixel_observations
    from ..observation.s1_sar_model import predict_sar_observation
    from ..observation.s2_forward_model import predict_observation

    scene_id = str(getattr(holdout_scene, 'scene_id', ''))
    if operator is None or str(getattr(operator, 'scene_id', '')) != scene_id:
        return {
            'status': 'operator_identity_unavailable',
            'errors': {},
            'mean_error': None,
            'prediction_mode': 'none',
        }
    if str(getattr(operator, 'valid_support_hash', '') or '') != str(
        getattr(holdout_scene, 'valid_support_hash', '') or ''
    ):
        return {
            'status': 'support_contract_mismatch',
            'errors': {},
            'mean_error': None,
            'prediction_mode': 'none',
        }
    h_matrix = getattr(operator, 'H_matrix', None)
    node_ids = sorted(training_state)
    if h_matrix is None or h_matrix.shape[1] != len(node_ids):
        return {
            'status': 'holdout_geometry_unavailable',
            'errors': {},
            'mean_error': None,
            'prediction_mode': 'none',
        }

    observations = extract_pixel_observations(holdout_scene)
    errors: Dict[str, float] = {}
    node_errors_by_obs: Dict[str, np.ndarray] = {}
    for obs_name in sorted(observations):
        pixel_observation = observations[obs_name]
        mapping = INDEX_STATE_REGISTRY.get(obs_name)
        if mapping is None or not pixel_observation.is_per_pixel:
            continue
        if pixel_observation.n_pixels != h_matrix.shape[0]:
            continue
        zone_prediction = []
        for node_id in node_ids:
            state = training_state.get(node_id)
            if not isinstance(state, list):
                zone_prediction = []
                break
            try:
                prediction = (
                    predict_sar_observation(obs_name, state)
                    if mapping.sensor == 'S1'
                    else predict_observation(obs_name, state)
                )
            except (TypeError, ValueError, IndexError, OverflowError):
                prediction = None
            if prediction is None or not math.isfinite(float(prediction)):
                zone_prediction = []
                break
            zone_prediction.append(float(prediction))
        if not zone_prediction:
            continue
        predicted = np.asarray(h_matrix @ np.asarray(zone_prediction), dtype=float)
        observed = np.asarray(pixel_observation.values, dtype=float)
        valid = np.asarray(pixel_observation.valid_mask, dtype=bool)
        valid &= np.isfinite(observed) & np.isfinite(predicted)
        if not np.any(valid):
            continue
        diff_sq = np.zeros_like(observed)
        diff_sq[valid] = (predicted[valid] - observed[valid]) ** 2
        errors[obs_name] = float(np.sqrt(np.mean(diff_sq[valid])))
        try:
            h_trans = h_matrix.T if hasattr(h_matrix, "T") else h_matrix.transpose()
            valid_float = valid.astype(float)
            node_weight = np.asarray(h_trans @ valid_float).reshape(-1)
            node_diff_sum = np.asarray(h_trans @ diff_sq).reshape(-1)
            node_mse = np.where(node_weight > 1e-9, node_diff_sum / np.maximum(node_weight, 1e-9), errors[obs_name] ** 2)
            node_errors_by_obs[obs_name] = np.sqrt(np.maximum(0.0, node_mse))
        except Exception as exc:
            logger.debug("Node error back-projection failed for %s: %s", obs_name, exc)

    if not errors:
        return {
            'status': 'no_compatible_forward_prediction',
            'errors': {},
            'mean_error': None,
            'n_observations': len(observations),
        }

    per_microzone_error: Dict[str, float] = {}
    if node_errors_by_obs:
        try:
            all_obs_node_err = np.mean(list(node_errors_by_obs.values()), axis=0)
            per_microzone_error = {
                node_id: round(float(err), 6)
                for node_id, err in zip(node_ids, all_obs_node_err)
            }
        except Exception as exc:
            logger.debug("Per-microzone error aggregation failed: %s", exc)
            per_microzone_error = {}

    return {
        'status': 'predicted',
        'errors': errors,
        'mean_error': round(sum(errors.values()) / len(errors), 6),
        'per_microzone_error': per_microzone_error,
        'n_observations': len(errors),
        'prediction_mode': 'ht_per_pixel_exact_support',
    }


persistence_baseline_held_out_scene = predict_held_out_scene


def forecast_held_out_scene(
    training_state: Dict[str, List[float]],
    holdout_scene: Any,
    operator: Optional[Any] = None,
    weather_day: Optional[dict] = None,
    crop_context: Optional[dict] = None,
    soil_context: Optional[dict] = None,
    delta_days: float = 1.0,
    rng: Optional[Any] = None,
) -> Dict[str, Any]:
    """Propagate training state forward to holdout time and evaluate closure against H_holdout.

    Computes both persistence_rmse (baseline) and prospective_forecast_rmse (dynamic model),
    reporting the comparative forecast_skill_score = 1 - (forecast_rmse / persistence_rmse).
    """
    import random
    from ..assimilation.filter import forecast_step

    # 1. Baseline: Frozen persistence
    persistence_result = predict_held_out_scene(
        training_state=training_state,
        holdout_scene=holdout_scene,
        operator=operator,
    )
    persistence_rmse = persistence_result.get("mean_error")

    # If persistence evaluation already failed (e.g. geometry mismatch or operator unavailable), return immediately
    if persistence_result.get("status") != "predicted":
        return persistence_result

    # 2. Dynamic Forward Propagation via ASMAE transition equations
    if delta_days > 0.0 and training_state:
        ensemble_in = {
            node: [list(state)]
            for node, state in training_state.items()
            if isinstance(state, (list, tuple))
        }
        if ensemble_in:
            from ..deterministic import make_rng
            generator = rng or make_rng(
                "retrovalidation_forecast",
                str(getattr(holdout_scene, "scene_id", "holdout_scene")),
                str(int(delta_days * 100)),
            )
            propagated_ens = forecast_step(
                ensemble=ensemble_in,
                priors={},
                crop_context=crop_context or {},
                rng=generator,
                weather_day=weather_day or {},
                soil_context=soil_context or {},
                delta_days=delta_days,
            )
            propagated_state = {
                node: propagated_ens[node][0]
                for node in propagated_ens
            }
        else:
            propagated_state = training_state
    else:
        propagated_state = training_state

    # 3. Evaluate Holdout Operator on Propagated State
    forecast_result = predict_held_out_scene(
        training_state=propagated_state,
        holdout_scene=holdout_scene,
        operator=operator,
    )
    forecast_rmse = forecast_result.get("mean_error")

    skill_score = None
    if (
        persistence_rmse is not None
        and forecast_rmse is not None
        and persistence_rmse > 0.0
    ):
        skill_score = round(1.0 - (forecast_rmse / persistence_rmse), 6)

    return {
        "status": forecast_result.get("status", "predicted"),
        "errors": forecast_result.get("errors", {}),
        "mean_error": forecast_rmse,
        "per_microzone_error": forecast_result.get("per_microzone_error") or persistence_result.get("per_microzone_error") or {},
        "prospective_forecast_rmse": forecast_rmse,
        "persistence_rmse": persistence_rmse,
        "forecast_skill_score": skill_score,
        "forecast_state": propagated_state,
        "n_observations": forecast_result.get("n_observations", 0),
        "prediction_mode": "dynamic_forecast_propagation",
        "delta_days": delta_days,
    }

