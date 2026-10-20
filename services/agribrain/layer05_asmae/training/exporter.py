from __future__ import annotations
try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real
"""
V79A Phase 9: Weak-label exporter with 10-gate safety system.

Every weak label collects ALL zero-weight reasons (not just the first).

10 Gates (zero-weight conditions):
  Gate 1: retro_score < 0.5
  Gate 2: uncertainty > 0.5
  Gate 3: BMA disagreement > 0.20
  Gate 4: 1m without certification
  Gate 5: scene_stack_mode == "no_scenes"
  Gate 6: n_scenes_processed == 0
  Gate 7: retro_status != "success_with_holdouts"
  Gate 8: bma_status != "success"
  Gate 9: radiometric_overall_pass != true
  Gate 10: production_usable != true

Max weight capped at 0.3. Labels are always 'weak_assimilated_reference'.
"""


import logging
from typing import Any, Dict, List, Optional

from ..config import (
    N_STATES,
    STATE_NAMES,
    WEAK_LABEL_MAX_WEIGHT,
)

logger = logging.getLogger(__name__)


def export_weak_labels(
    state_result: Dict[str, Any],
    retro_result: Dict[str, Any],
    bma_result: Dict[str, Any],
    consistency_result: Dict[str, Any],
    scene_stack_mode: str,
    resolution_m: int,
    plot_id: str,
    run_id: str,
    production_usable: bool,
    n_scenes_processed: int = 0,
    certification_level: str = "provisional",
    mode: str = "training_export",
    biophysical_profiles: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Export weak labels with 10-gate safety system.

    Every label collects all zero-weight reasons.
    No label ever gets type 'ground_truth'.

    Args:
        state_result: EnKF output.
        retro_result: From V76 retrovalidation.
        bma_result: From V78 BMA.
        consistency_result: From V75 radiometric.
        scene_stack_mode: "real_raster" | "degraded_mean_only" | "no_scenes".
        resolution_m: Selected resolution.
        plot_id: Plot identifier.
        run_id: Run identifier.
        production_usable: Overall gate flag.
        n_scenes_processed: Number of scenes processed.
        certification_level: Certification level.

    Returns:
        List of weak label dicts, each with training_weight and zero_weight_reasons.
    """
    means = state_result.get("raster_maps", {})
    sigmas = state_result.get("uncertainty_maps", {})

    if not means:
        return []

    # ── Pre-compute global gate results ────────────────────────────
    retro_status = retro_result.get("status", "none")
    retro_agg = retro_result.get("aggregate", {})
    bma_status = bma_result.get("status", "none")
    bma_disagreement_map = bma_result.get("per_microzone_disagreement", {})
    radiometric_pass = consistency_result.get("overall_pass", False)
    blocked_states = set(consistency_result.get("blocked_states", []))
    for act in consistency_result.get("actions", []):
        if act.startswith("block_state_export:"):
            blocked_states.add(act.split(":", 1)[1])
        elif act.startswith("block_state_update:"):
            obs = act.split(":", 1)[1]
            if obs in STATE_NAMES:
                blocked_states.add(obs)
            elif obs == "evi":
                blocked_states.add("vigor")
            elif obs in ("sar_vv", "sar_vh"):
                blocked_states.add("structure")
                blocked_states.add("surface_wetness_event")

    # Global gates (apply to every label)
    global_reasons: List[str] = []

    # Gate 5: no scenes
    if scene_stack_mode == "no_scenes":
        global_reasons.append("no_real_scene_stack")

    # Gate 6: n_scenes_processed == 0
    if n_scenes_processed == 0:
        global_reasons.append("n_scenes_processed_is_zero")

    # Gate 7: retro status
    if retro_status != "success_with_holdouts":
        global_reasons.append(f"retro_status_not_success_with_holdouts:{retro_status}")

    # Gate 8: bma status
    if bma_status != "success":
        global_reasons.append(f"bma_status_not_success:{bma_status}")

    # Gate 9: radiometric
    if not radiometric_pass:
        global_reasons.append("radiometric_overall_pass_false")

    # Gate 10: production_usable
    if not production_usable:
        global_reasons.append("production_not_usable")

    # Gate 11: mode export gate (P0: V79B.1)
    if mode not in ("training_export", "certification"):
        global_reasons.append(f"mode_not_exportable:{mode}")

    # ── Export per-microzone labels ─────────────────────────────────
    labels: List[Dict[str, Any]] = []
    retro_per_mz = retro_result.get("per_microzone", {})

    for nid, state in means.items():
        if not isinstance(state, list):
            continue

        sigma = sigmas.get(nid, [0.1] * N_STATES)
        retro_info = retro_per_mz.get(nid, {})
        retro_score = retro_info.get("retro_score", retro_result.get("aggregate", {}).get("retro_score", 0.0))
        bma_dis = bma_disagreement_map.get(nid, 0.0)

        for s_idx in range(min(N_STATES, len(state))):
            s_name = STATE_NAMES[s_idx] if s_idx < len(STATE_NAMES) else f"state_{s_idx}"
            s_val = state[s_idx]
            s_sigma = sigma[s_idx] if s_idx < len(sigma) else 0.1

            # Collect ALL zero-weight reasons for this label
            reasons = list(global_reasons)  # Copy global reasons

            fin_val = finite_real(s_val)
            fin_sigma = finite_real(s_sigma)
            fin_retro = finite_real(retro_score)
            fin_bma = finite_real(bma_dis)

            if fin_val is None:
                reasons.append(f"invalid_state_estimate:{s_name}={s_val!r}")
            if fin_sigma is None or fin_sigma <= 0.0:
                reasons.append(f"invalid_uncertainty:{s_sigma!r}")
            if fin_retro is None or not (0.0 <= fin_retro <= 1.0):
                reasons.append(f"invalid_retro_score:{retro_score!r}")
            if fin_bma is None or fin_bma < 0.0:
                reasons.append(f"invalid_bma_disagreement:{bma_dis!r}")

            # Gate 1: retro_score < 0.5
            if fin_retro is not None and fin_retro < 0.5:
                reasons.append(f"retro_score_low:{fin_retro:.3f}")

            # Gate 2: uncertainty > 0.5
            if fin_sigma is not None and fin_sigma > 0.5:
                reasons.append(f"uncertainty_too_high:{fin_sigma:.3f}")

            # Gate 3: BMA disagreement > 0.20
            if fin_bma is not None and fin_bma > 0.20:
                reasons.append(f"bma_disagreement_too_high:{fin_bma:.3f}")

            # Gate 4: 1m without certification
            if resolution_m <= 1 and certification_level not in ("certified", "retrovalidated"):
                reasons.append("1m_without_certification")

            # Gate 4b: radiometric observation failure blocked this state
            if s_name in blocked_states:
                reasons.append(f"radiometric_state_blocked:{s_name}")

            # Compute weight: 0 if any reason, else capped at WEAK_LABEL_MAX_WEIGHT
            if reasons or fin_val is None or fin_sigma is None or fin_retro is None:
                training_weight = 0.0
                confidence_val = 0.0
            else:
                confidence_val = fin_retro * max(0.0, 1.0 - fin_sigma)
                training_weight = min(confidence_val, WEAK_LABEL_MAX_WEIGHT)
                training_weight = round(training_weight, 4)

            label_entry = {
                "microzone_id": nid,
                "state_name": s_name,
                "state_index": s_idx,
                "estimate": round(fin_val, 6) if fin_val is not None else s_val,
                "uncertainty": round(fin_sigma, 6) if fin_sigma is not None else s_sigma,
                "retro_score": round(fin_retro, 4) if fin_retro is not None else retro_score,
                "bma_disagreement": round(fin_bma, 6) if fin_bma is not None else bma_dis,
                "certification_level": certification_level,
                "resolution_m": resolution_m,
                "training_weight": training_weight,
                "label_type": "weak_assimilated_reference",  # NEVER "ground_truth"
                "confidence": round(confidence_val, 4),
                "plot_id": plot_id,
                "run_id": run_id,
                "zero_weight_reasons": reasons,  # All reasons, not just first
            }
            if biophysical_profiles and nid in biophysical_profiles:
                bp = biophysical_profiles[nid]
                bp_d = bp.to_dict() if hasattr(bp, "to_dict") else bp
                label_entry["biophysical_cluster"] = bp_d.get("biophysical_cluster_id", "unknown")
                label_entry["water_retention_index"] = bp_d.get("water_retention_index", 0.5)
                label_entry["nutrient_response_index"] = bp_d.get("nutrient_response_index", 0.5)

            labels.append(label_entry)

    n_positive = sum(1 for l in labels if l["training_weight"] > 0)
    logger.info(
        "V79 weak labels: %d total, %d positive-weight, %d zero-weight",
        len(labels), n_positive, len(labels) - n_positive,
    )

    return labels
