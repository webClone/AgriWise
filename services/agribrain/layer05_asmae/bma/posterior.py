"""
V79A Phase 7: BMA with holdout-based expert weights.

Key V79A changes:
  - Weights learned from holdout/retrovalidation errors, not current fit
  - Uniform fallback is NOT "success" and gives weak-label weight 0
  - bma_status: "success" | "no_holdout_available" | "insufficient_experts"
  - bma_weights_source: "holdout_performance" | "uniform_fallback"
  - No single BMA expert can certify 1m

5 physics experts:
  1. optical_physiology â€” optical indices
  2. sar_structure â€” SAR backscatter
  3. water_balance â€” soil/canopy water
  4. spatial_smooth â€” Laplacian smoothing
  5. phenology_memory â€” temporal persistence
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from .. import config as asmae_config

logger = logging.getLogger(__name__)


def _apply_caps_and_renormalize(
    raw_weights: Dict[str, float],
    active_ml_experts: List[str]
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Renormalize weights to satisfy V88 caps and constraints.
    
    Returns (bma_weights_production, bma_weights_shadow_raw)
    """
    physics_keys = [k for k in asmae_config.BMA_EXPERTS if k in raw_weights]
    ml_keys = [k for k in raw_weights if k not in physics_keys]
    
    raw_p_weights = {k: raw_weights.get(k, 0.0) for k in physics_keys}
    raw_ml_weights = {k: raw_weights.get(k, 0.0) for k in ml_keys}
    
    sum_ml_raw = sum(raw_ml_weights.values())
    
    # Target ML group sum cannot exceed COMBINED_ML_EXPERT_MAX_WEIGHT
    target_ml_sum = min(asmae_config.COMBINED_ML_EXPERT_MAX_WEIGHT, sum_ml_raw)
    target_p_sum = 1.0 - target_ml_sum
    
    # 1. Normalize ML group to target_ml_sum
    ml_weights = {}
    if ml_keys:
        if sum_ml_raw > 0:
            for k in ml_keys:
                ml_weights[k] = (raw_ml_weights[k] / sum_ml_raw) * target_ml_sum
        else:
            for k in ml_keys:
                ml_weights[k] = target_ml_sum / len(ml_keys)
                
        # Iterative clipping to individual ML cap (0.15)
        for _ in range(len(ml_keys)):
            excess = 0.0
            non_capped_sum = 0.0
            uncapped_keys = []
            for k, w in ml_weights.items():
                if w > asmae_config.ML_EXPERT_MAX_WEIGHT:
                    excess += w - asmae_config.ML_EXPERT_MAX_WEIGHT
                    ml_weights[k] = asmae_config.ML_EXPERT_MAX_WEIGHT
                elif w < asmae_config.ML_EXPERT_MAX_WEIGHT:
                    non_capped_sum += w
                    uncapped_keys.append(k)
            if excess <= 1e-9 or not uncapped_keys:
                break
            if non_capped_sum > 0:
                for k in uncapped_keys:
                    ml_weights[k] += excess * (ml_weights[k] / non_capped_sum)
            else:
                for k in uncapped_keys:
                    ml_weights[k] += excess / len(uncapped_keys)
                    
    # Update actual ml sum after clipping
    actual_ml_sum = sum(ml_weights.values())
    target_p_sum = 1.0 - actual_ml_sum
    
    # 2. Normalize Physics group to target_p_sum
    p_weights = {}
    sum_p_raw = sum(raw_p_weights.values())
    if sum_p_raw > 0:
        for k in physics_keys:
            p_weights[k] = (raw_p_weights[k] / sum_p_raw) * target_p_sum
    elif physics_keys:
        for k in physics_keys:
            p_weights[k] = target_p_sum / len(physics_keys)
            
    # 3. Construct bma_weights_shadow_raw
    bma_weights_shadow_raw = {**p_weights, **ml_weights}
    
    # 4. Construct bma_weights_production
    sum_p_final = sum(p_weights.values())
    prod_p_weights = {}
    if sum_p_final > 0:
        prod_p_weights = {k: w / sum_p_final for k, w in p_weights.items()}
    elif physics_keys:
        prod_p_weights = {k: 1.0 / len(physics_keys) for k in physics_keys}
        
    bma_weights_production = {**prod_p_weights}
    for k in ml_keys:
        bma_weights_production[k] = 0.0
        
    return bma_weights_production, bma_weights_shadow_raw


def run_bma(
    state_result: Dict[str, Any],
    priors: Dict[str, Any],
    graph: Any,
    retro_result: Optional[Dict[str, Any]] = None,
    evidence_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run Bayesian Model Averaging.

    V88: Hard guard on non-shadow ML, shadow-only ML integration.

    Args:
        state_result: EnKF output.
        priors: Layer priors.
        graph: Microzone graph.
        retro_result: From V76 retrovalidation (contains holdout errors).

    Returns:
        Dict with consensus, weights, disagreement, status, weights_source.
    """
    if asmae_config.ASMAE_ML_EXPERTS_ENABLED and not asmae_config.ASMAE_ML_EXPERTS_SHADOW_ONLY:
        raise RuntimeError("V88 forbids non-shadow ML expert influence")

    means = state_result.get("raster_maps", {})
    sigmas = state_result.get("uncertainty_maps", {})

    if not means:
        return {
            "status": "no_state_data",
            "bma_weights_source": "none",
            "consensus": {},
            "weights": {},
            "per_microzone_disagreement": {},
            "mean_disagreement": 0.0,
        }

    # â”€â”€ Active ML experts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    active_ml_experts = []
    if asmae_config.ASMAE_ML_EXPERTS_ENABLED:
        try:
            from asmae_learn.model_registry import ModelRegistry
            active_ml_experts = ModelRegistry.get_approved_models()
        except Exception as e:
            logger.error(f"Error loading active ML experts: {e}")

    # â”€â”€ Compute expert predictions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    from .physics_experts import compute_physics_experts

    expert_specs = compute_physics_experts(
        means,
        {
            **(evidence_context or {}),
            "graph": graph,
            "priors": priors,
        },
    )

    if asmae_config.ASMAE_ML_EXPERTS_ENABLED and active_ml_experts:
        try:
            from asmae_learn.model_registry import predict_expert
            for model_id in active_ml_experts:
                expert_specs[model_id] = {
                    "predictions": predict_expert(model_id, means),
                    "target_states": list(asmae_config.STATE_NAMES),
                    "input_evidence": [f"approved_ml_model:{model_id}"],
                    "independence_key": f"ml:{model_id}",
                    "model_version": model_id,
                }
        except Exception as e:
            logger.error(f"Error computing ML expert predictions: {e}")

    # â”€â”€ Compute expert weights â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    retro_status = retro_result.get("status", "none") if retro_result else "none"
    holdout_errors = retro_result.get("expert_holdout_errors", {}) if retro_result else {}

    # An expert is active only when it materially differs from the base state
    # and has its own holdout score. Names do not establish independence.
    candidate_proof = {
        name: {
            "active": False,
            "allowed_to_reduce_disagreement": False,
            "inactive_reason": "required_input_evidence_missing",
            "target_states": [],
            "input_evidence": [],
        }
        for name in asmae_config.BMA_EXPERTS
    }
    active_predictions = {}
    active_specs = {}
    active_independence_keys = set()
    for expert_name, spec in expert_specs.items():
        prediction = spec.get("predictions", {})
        target_states = [
            state for state in spec.get("target_states", [])
            if state in asmae_config.STATE_NAMES
        ]
        target_indices = [asmae_config.STATE_NAMES.index(state) for state in target_states]
        deltas = []
        for nid, pred_vec in prediction.items():
            base_vec = means.get(nid)
            if isinstance(base_vec, list) and isinstance(pred_vec, list):
                for index in target_indices:
                    if index >= len(pred_vec) or index >= len(base_vec):
                        continue
                    predicted = pred_vec[index]
                    if not isinstance(predicted, (int, float)):
                        continue
                    state = asmae_config.STATE_NAMES[index]
                    lo, hi = asmae_config.STATE_BOUNDS[state]
                    deltas.append(abs(float(predicted) - float(base_vec[index])) / max(hi - lo, 1e-9))
        delta = sum(deltas) / len(deltas) if deltas else 0.0
        holdout_value = holdout_errors.get(expert_name)
        has_holdout = bool(
            not isinstance(holdout_value, bool)
            and isinstance(holdout_value, (int, float))
            and math.isfinite(float(holdout_value))
        )
        independence_key = str(spec.get("independence_key", ""))
        active = bool(target_indices and independence_key and has_holdout)
        inactive_reason = ""
        if not active:
            if not has_holdout:
                inactive_reason = "no_independent_holdout_score"
            elif not (target_indices and independence_key):
                inactive_reason = "missing_target_indices_or_independence_key"

        candidate_proof[expert_name] = {
            "target_state_normalized_delta_from_base": round(delta, 6),
            "has_independent_holdout_score": has_holdout,
            "active": active,
            "allowed_to_reduce_disagreement": active,
            "target_states": target_states,
            "input_evidence": spec.get("input_evidence", []),
            "independence_key": independence_key,
            "model_version": spec.get("model_version"),
            "inactive_reason": inactive_reason,
        }
        if active:
            active_predictions[expert_name] = prediction
            active_specs[expert_name] = spec
            active_independence_keys.add(independence_key)

    expert_predictions = active_predictions
    all_expert_names = list(expert_predictions.keys())
    active_physics_names = [
        name for name in all_expert_names if name in asmae_config.BMA_EXPERTS
    ]
    active_physics_independence = {
        str(active_specs[name].get('independence_key', ''))
        for name in active_physics_names
    }
    if len(active_physics_names) < 2 or len(active_physics_independence) < 2:
        return {
            "status": "insufficient_experts",
            "bma_weights_source": "none",
            "consensus": {},
            "weights": {},
            "bma_weights_production": {},
            "bma_weights_shadow_raw": {},
            "per_microzone_disagreement": {},
            "mean_disagreement": 0.0,
            "n_experts": len(all_expert_names),
            "active_ml_experts": active_ml_experts,
            "expert_proof": candidate_proof,
            "active_independence_keys": sorted(active_independence_keys),
            'active_physics_experts': active_physics_names,
            'production_sufficiency_reason': 'two_independent_physics_experts_required',
        }

    if retro_status == "success_with_holdouts" and retro_result:
        raw_weights, weights_source = _compute_holdout_weights(
            expert_predictions, retro_result, means,
        )
        if weights_source == "holdout_performance":
            bma_status = "success"
        else:
            bma_status = "no_holdout_available"
    else:
        # Uniform fallback
        raw_weights = {name: 1.0 / len(all_expert_names) for name in all_expert_names}
        weights_source = "uniform_fallback"
        bma_status = "no_holdout_available"

    # â”€â”€ Apply caps and renorm â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    bma_weights_production, bma_weights_shadow_raw = _apply_caps_and_renormalize(
        raw_weights, active_ml_experts
    )

    # â”€â”€ Consensus prediction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    consensus: Dict[str, List[float]] = {}
    per_mz_disagreement: Dict[str, float] = {}

    for nid in means:
        base_state = means.get(nid, [0.0] * asmae_config.N_STATES)
        weighted_state = list(base_state)
        contributed_states = []
        for s in range(asmae_config.N_STATES):
            contributors = []
            for expert_name, weight in bma_weights_production.items():
                expert_state = expert_predictions.get(expert_name, {}).get(nid)
                if not isinstance(expert_state, list) or s >= len(expert_state):
                    continue
                value = expert_state[s]
                if isinstance(value, (int, float)):
                    contributors.append((weight, float(value)))
            total_weight = sum(weight for weight, _ in contributors)
            if total_weight > 0.0:
                weighted_state[s] = sum(weight * value for weight, value in contributors) / total_weight
                contributed_states.append(s)
        consensus[nid] = [round(v, 6) for v in weighted_state]

        # Disagreement uses only experts that target each state.
        disagreement = 0.0
        for s in contributed_states:
            contributors = []
            for expert_name, weight in bma_weights_production.items():
                expert_state = expert_predictions.get(expert_name, {}).get(nid)
                if isinstance(expert_state, list) and s < len(expert_state) and isinstance(expert_state[s], (int, float)):
                    contributors.append((weight, float(expert_state[s])))
            total_weight = sum(weight for weight, _ in contributors)
            if total_weight > 0.0:
                disagreement += sum(
                    (weight / total_weight) * (value - weighted_state[s]) ** 2
                    for weight, value in contributors
                )
        per_mz_disagreement[nid] = round(disagreement / max(len(contributed_states), 1), 6)

    mean_disagreement = (
        sum(per_mz_disagreement.values()) / max(len(per_mz_disagreement), 1)
    )

    return {
        "status": bma_status,
        "bma_weights_source": weights_source,
        "consensus": consensus,
        "weights": {k: round(v, 4) for k, v in bma_weights_production.items()},
        "bma_weights_production": {k: round(v, 4) for k, v in bma_weights_production.items()},
        "bma_weights_shadow_raw": {k: round(v, 4) for k, v in bma_weights_shadow_raw.items()},
        "per_microzone_disagreement": per_mz_disagreement,
        "mean_disagreement": round(mean_disagreement, 6),
        "n_experts": len(all_expert_names),
        "active_experts": all_expert_names,
        'active_physics_experts': active_physics_names,
        "active_independence_keys": sorted(active_independence_keys),
        "single_expert_cannot_certify_1m": True,
        "active_ml_experts": active_ml_experts,
        "expert_proof": candidate_proof,
    }


def _compute_holdout_weights(
    expert_predictions: Dict[str, Dict[str, List[float]]],
    retro_result: Dict[str, Any],
    means: Dict[str, Any],
    temperature: float = 0.5,
) -> tuple:
    """V79B: Compute BMA weights from retrovalidation expert holdout errors.

    Uses expert_predictions keys dynamically to support ML experts.
    """
    expert_holdout_errors = retro_result.get("expert_holdout_errors", {})
    retro_per_mz = retro_result.get("per_microzone", {})
    holdout_targets = retro_result.get("holdout_observation_targets", {})

    errors: Dict[str, float] = {}
    all_expert_names = list(expert_predictions.keys())

    if expert_holdout_errors:
        errors = {
            k: float(v) for k, v in expert_holdout_errors.items()
            if k in all_expert_names and isinstance(v, (int, float))
            and math.isfinite(float(v))
        }
    elif holdout_targets:
        for expert_name, predictions in expert_predictions.items():
            total_error = 0.0
            n_mz = 0
            for nid, expert_state in predictions.items():
                target = holdout_targets.get(nid)
                if target is None:
                    continue
                if not isinstance(target, list) or not isinstance(expert_state, list):
                    continue
                mz_error = 0.0
                for s in range(min(asmae_config.N_STATES, len(expert_state), len(target))):
                    mz_error += (expert_state[s] - target[s]) ** 2
                mz_error = math.sqrt(mz_error / max(asmae_config.N_STATES, 1))
                total_error += mz_error
                n_mz += 1
            errors[expert_name] = total_error / max(n_mz, 1)
    else:
        logger.warning(
            "BMA: No expert_holdout_errors or holdout_observation_targets. "
            "Falling back to uniform. This is NOT 'success'."
        )
        return {name: 1.0 / len(all_expert_names) for name in all_expert_names}, "uniform_fallback"

    # Validate: all experts must have errors
    for name in all_expert_names:
        if name not in errors:
            errors[name] = 1.0  # Penalize missing experts

    # Softmax
    if not errors:
        return {name: 1.0 / len(all_expert_names) for name in all_expert_names}, "uniform_fallback"

    min_error = min(errors.values())
    exp_weights = {}
    for name, err in errors.items():
        exp_weights[name] = math.exp(-(err - min_error) / max(temperature, 0.01))

    total_w = sum(exp_weights.values())
    if total_w < 1e-10:
        return {name: 1.0 / len(all_expert_names) for name in all_expert_names}, "uniform_fallback"

    weights = {name: w / total_w for name, w in exp_weights.items()}
    return weights, "holdout_performance"
