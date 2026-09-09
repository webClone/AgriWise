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
        errors[obs_name] = float(np.sqrt(np.mean((predicted[valid] - observed[valid]) ** 2)))

    if not errors:
        return {
            'status': 'no_compatible_forward_prediction',
            'errors': {},
            'mean_error': None,
            'n_observations': len(observations),
        }
    return {
        'status': 'predicted',
        'errors': errors,
        'mean_error': round(sum(errors.values()) / len(errors), 6),
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
            generator = rng or random.Random(42)
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
        "prospective_forecast_rmse": forecast_rmse,
        "persistence_rmse": persistence_rmse,
        "forecast_skill_score": skill_score,
        "forecast_state": propagated_state,
        "n_observations": forecast_result.get("n_observations", 0),
        "prediction_mode": "dynamic_forecast_propagation",
        "delta_days": delta_days,
    }


def _legacy_predict_held_out_scene(
    training_state: Dict[str, List[float]],
    holdout_scene: Any,
    operator: Optional[Any] = None,
) -> Dict[str, Any]:
    """V79B: Compute prediction error on held-out scene via Hₜ.

    Uses per-pixel observation extraction and Hₜ projection:
      y_pred = H_holdout @ h(x̂_training)
      y_obs  = real pixel obs from held-out scene
      error  = RMSE(y_pred, y_obs) over valid pixels

    Falls back to mean-level when no Hₜ or no per-pixel obs.
    """
    from ..observation.pixel_extraction import extract_pixel_observations
    from ..observation.s2_forward_model import predict_observation
    from ..observation.s1_sar_model import predict_sar_observation
    from ..observation.index_state_mapping import INDEX_STATE_REGISTRY

    # V79B: Per-pixel observation extraction
    pixel_obs = extract_pixel_observations(holdout_scene)
    if not pixel_obs:
        return {
            "status": "no_observations_in_holdout",
            "errors": {},
            "mean_error": 1.0,
            "prediction_mode": "none",
        }

    h_matrix = getattr(operator, "H_matrix", None) if operator else None
    node_ids = sorted(training_state.keys())

    errors: Dict[str, float] = {}
    has_per_pixel = False

    for obs_name, pix_obs in pixel_obs.items():
        mapping = INDEX_STATE_REGISTRY.get(obs_name)
        if mapping is None:
            continue

        # Predict observation from training state per microzone
        h_vector = []
        for nid in node_ids:
            state = training_state.get(nid)
            if not isinstance(state, list):
                h_vector = []
                break
            try:
                if mapping.sensor == "S1":
                    pred = predict_sar_observation(obs_name, state)
                else:
                    pred = predict_observation(obs_name, state)
            except (TypeError, ValueError, IndexError):
                pred = None
            if pred is None:
                h_vector = []
                break
            h_vector.append(pred)

        if not h_vector:
            continue

        # V79B: Try Hₜ projection for per-pixel error
        if h_matrix is not None and pix_obs.is_per_pixel:
            try:
                import numpy as np
                h_vec = np.array(h_vector)

                if hasattr(h_matrix, "shape") and h_matrix.shape[1] == len(h_vector):
                    # y_pred = H_holdout @ h(x̂_training)
                    y_pred = h_matrix @ h_vec
                    n_pixels = len(y_pred)

                    # y_obs = real per-pixel observation
                    if pix_obs.n_pixels == n_pixels:
                        y_obs = np.array(pix_obs.values[:n_pixels])
                        valid = np.array(pix_obs.valid_mask[:n_pixels])
                    elif pix_obs.n_pixels > 1:
                        stride = max(1, pix_obs.n_pixels // n_pixels)
                        y_obs = np.array(pix_obs.values[::stride][:n_pixels])
                        valid = np.array(pix_obs.valid_mask[::stride][:n_pixels])
                        if len(y_obs) < n_pixels:
                            pad = n_pixels - len(y_obs)
                            y_obs = np.concatenate([y_obs, np.full(pad, pix_obs.mean)])
                            valid = np.concatenate([valid, np.zeros(pad, dtype=bool)])
                    else:
                        y_obs = np.full(n_pixels, pix_obs.mean)
                        valid = np.ones(n_pixels, dtype=bool)

                    valid_idx = np.where(valid)[0]
                    if len(valid_idx) > 0:
                        rmse = float(np.sqrt(np.mean(
                            (y_pred[valid_idx] - y_obs[valid_idx]) ** 2
                        )))
                        errors[obs_name] = rmse
                        has_per_pixel = True
                        continue
            except (ImportError, Exception) as e:
                logger.debug("Hₜ projection failed in retro for %s: %s", obs_name, e)

        # Fallback: mean-level prediction error
        pred_mean = sum(h_vector) / max(len(h_vector), 1)
        errors[obs_name] = abs(pred_mean - pix_obs.mean)

    if errors:
        mean_error = sum(errors.values()) / len(errors)
    else:
        mean_error = 1.0

    prediction_mode = "ht_per_pixel" if has_per_pixel else "mean_level"

    return {
        "status": "predicted",
        "errors": errors,
        "mean_error": round(mean_error, 6),
        "n_observations": len(pixel_obs),
        "prediction_mode": prediction_mode,
    }
