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

from __future__ import annotations

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
        retro_score = retro_info.get("retro_score", 0.0)
        bma_dis = bma_disagreement_map.get(nid, 0.0)

        for s_idx in range(min(N_STATES, len(state))):
            s_name = STATE_NAMES[s_idx] if s_idx < len(STATE_NAMES) else f"state_{s_idx}"
            s_val = state[s_idx]
            s_sigma = sigma[s_idx] if s_idx < len(sigma) else 0.1

            # Collect ALL zero-weight reasons for this label
            reasons = list(global_reasons)  # Copy global reasons

            # Gate 1: retro_score < 0.5
            if retro_score < 0.5:
                reasons.append(f"retro_score_low:{retro_score:.3f}")

            # Gate 2: uncertainty > 0.5
            if s_sigma > 0.5:
                reasons.append(f"uncertainty_too_high:{s_sigma:.3f}")

            # Gate 3: BMA disagreement > 0.20
            if bma_dis > 0.20:
                reasons.append(f"bma_disagreement_too_high:{bma_dis:.3f}")

            # Gate 4: 1m without certification
            if resolution_m <= 1 and certification_level not in ("certified", "retrovalidated"):
                reasons.append("1m_without_certification")

            # Compute weight: 0 if any reason, else capped at WEAK_LABEL_MAX_WEIGHT
            if reasons:
                training_weight = 0.0
            else:
                # Weight based on confidence (retro_score * (1 - uncertainty))
                confidence = retro_score * max(0.0, 1.0 - s_sigma)
                training_weight = min(confidence, WEAK_LABEL_MAX_WEIGHT)
                training_weight = round(training_weight, 4)

            labels.append({
                "microzone_id": nid,
                "state_name": s_name,
                "state_index": s_idx,
                "estimate": round(s_val, 6),
                "uncertainty": round(s_sigma, 6),
                "retro_score": round(retro_score, 4),
                "bma_disagreement": round(bma_dis, 6),
                "certification_level": certification_level,
                "resolution_m": resolution_m,
                "training_weight": training_weight,
                "label_type": "weak_assimilated_reference",  # NEVER "ground_truth"
                "confidence": round(retro_score * max(0.0, 1.0 - s_sigma), 4),
                "plot_id": plot_id,
                "run_id": run_id,
                "zero_weight_reasons": reasons,  # All reasons, not just first
            })

    n_positive = sum(1 for l in labels if l["training_weight"] > 0)
    logger.info(
        "V79 weak labels: %d total, %d positive-weight, %d zero-weight",
        len(labels), n_positive, len(labels) - n_positive,
    )

    return labels
