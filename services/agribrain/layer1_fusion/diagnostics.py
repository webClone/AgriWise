"""
Layer 1 Diagnostics Builder.

Builds Layer1Diagnostics from engine state.
No diagnosis vocabulary — data health only.

RC4: Every prohibition is STRICTLY computed from actual package
contents with no vacuous-truth fallbacks.
"""

from __future__ import annotations
import math

import json
from typing import Any, Dict, List, Optional, Tuple

from .conflict_resolver import ConflictResolverDiagnostics

from .schemas import (
    CANONICAL_UNITS,
    DataHealthScore,
    EvidenceConflict,
    EvidenceGap,
    EvidenceItem,
    FusedFeature,
    FusedFeatureSet,
    FORBIDDEN_DIAGNOSIS_TERMS,
    Layer1Diagnostics,
    QuarantinedEvidence,
    SourceEnvelope,
    SPATIAL_SCOPES,
    CORE_SOURCE_FAMILIES,
    OPTIONAL_SOURCE_FAMILIES,
)


# 22 prohibitions (13 baseline + 9 ASMAE safety checks)
HARD_PROHIBITIONS = [
    "no_fake_fallback_evidence",
    "no_diagnosis_or_recommendation",
    "no_forecast_as_observation",
    "no_point_sensor_to_plot_truth_without_scope",
    "no_geo_context_as_crop_state",
    "no_weather_as_crop_diagnosis",
    "no_wapor_as_plot_truth",
    "no_unprovenanced_fused_feature",
    "no_conflict_suppression",
    "no_unit_mismatch_allowed",
    "no_spatial_scope_collapse",
    "no_temporal_leakage_future_to_present",
    "no_simulated_data_in_user_facing_context",
    "no_asmae_state_update_from_shadow_mode",
    "no_asmae_state_update_from_mean_only_mode",
    "no_1m_state_update_without_external_ground_truth",
    "no_training_label_without_weak_label_export_allowed",
    "no_diagnostic_raster_as_state_evidence",
    "no_asmae_without_layer1_export_allowed",
    "no_asmae_without_observation_operator_refs",
    "no_asmae_state_update_without_retrovalidation",
    "no_low_confidence_asmae_to_layer2",
]

_DATA_QUALITY_FEATURES = frozenset({
    "source_completeness",
    "core_source_completeness",
    "optional_source_completeness",
    "overall_source_completeness",
    "average_freshness",
})


def compute_hard_prohibitions(
    evidence: List[EvidenceItem],
    fused: FusedFeatureSet,
    conflicts: List[EvidenceConflict],
    quarantined: List[QuarantinedEvidence],
    resolver_diag: Optional[ConflictResolverDiagnostics] = None,
) -> Dict[str, bool]:
    """Compute hard prohibition results from actual package contents.

    Final freeze: Strictly computed — no vacuous truth for required data.
    - Evidence is REQUIRED: empty evidence → fail (prohibitions 1, 10)
    - Fused features are REQUIRED: empty features → fail (prohibition 8)
    - Resolver diagnostics are REQUIRED: missing → fail (prohibition 9)
    - Optional sources (forecast, geo, wapor): absence is not violation
    """
    all_features = _all_fused(fused)
    # State features exclude data-quality meta-features
    state_features = [
        f for f in all_features if f.name not in _DATA_QUALITY_FEATURES
    ]

    # Build evidence lookup by id for provenance tracing
    ev_by_id: Dict[str, EvidenceItem] = {e.evidence_id: e for e in evidence}

    results: Dict[str, bool] = {}

    # ── 1. no_fake_fallback_evidence ─────────────────────────────────────
    # Every evidence item must have a non-empty provenance_ref.
    # Empty evidence → fail (engine must produce evidence for a valid package).
    if not evidence:
        results["no_fake_fallback_evidence"] = False
    else:
        results["no_fake_fallback_evidence"] = all(
            bool(e.provenance_ref) for e in evidence
        )

    # ── 2. no_diagnosis_or_recommendation ────────────────────────────────
    # No forbidden diagnosis/recommendation terms in any fused feature
    # name or string value. Checked across ALL features including DQ.
    all_text = " ".join(
        f"{f.name} {str(f.value)}".lower() for f in all_features
    )
    results["no_diagnosis_or_recommendation"] = not any(
        term in all_text for term in FORBIDDEN_DIAGNOSIS_TERMS
    )

    # ── 3. no_forecast_as_observation ────────────────────────────────────
    # Weather forecast evidence must ALWAYS be typed as forecast/model_estimate.
    # Never as "measurement" or "observation".
    forecast_ev = [e for e in evidence if e.source_family == "weather_forecast"]
    results["no_forecast_as_observation"] = all(
        e.observation_type in ("forecast", "model_estimate", "static_prior")
        for e in forecast_ev
    ) if forecast_ev else True

    # ── 4. no_point_sensor_to_plot_truth_without_scope ───────────────────
    # Point-scope sensor evidence must not appear as source for plot-scope
    # STATE features. DQ features are excluded (they summarize the ledger).
    point_sensor_ids = frozenset(
        e.evidence_id for e in evidence
        if e.source_family == "sensor" and e.spatial_scope == "point"
    )
    results["no_point_sensor_to_plot_truth_without_scope"] = not any(
        f.spatial_scope == "plot"
        and any(sid in point_sensor_ids for sid in f.source_evidence_ids)
        for f in state_features
    )

    # ── 5. no_geo_context_as_crop_state ──────────────────────────────────
    # Geo context evidence must be diagnostic_only or static_prior.
    # Also: no geo_context-sourced fused state feature may have
    # state_update_allowed semantics via the source evidence.
    geo_ev = [e for e in evidence if e.source_family == "geo_context"]
    results["no_geo_context_as_crop_state"] = all(
        e.diagnostic_only or e.observation_type == "static_prior"
        for e in geo_ev
    ) if geo_ev else True

    # ── 6. no_weather_as_crop_diagnosis ──────────────────────────────────
    # Weather/forecast evidence must not produce crop diagnosis terms.
    weather_ev = [e for e in evidence if e.source_family in ("environment", "weather_forecast")]
    weather_text = " ".join(f"{e.variable} {str(e.value)}".lower() for e in weather_ev)
    results["no_weather_as_crop_diagnosis"] = not any(
        term in weather_text
        for term in ("disease", "deficiency", "prescription", "diagnosis", "blight")
    )

    # ── 7. no_wapor_as_plot_truth ────────────────────────────────────────
    # WaPOR evidence must be diagnostic or static — never plot-level truth.
    wapor_ev = [e for e in evidence if "wapor" in e.variable.lower()]
    results["no_wapor_as_plot_truth"] = all(
        e.diagnostic_only or e.observation_type == "static_prior"
        for e in wapor_ev
    ) if wapor_ev else True

    # ── 8. no_unprovenanced_fused_feature ────────────────────────────────
    # Every fused feature (including DQ) must have ≥1 source evidence ID.
    # Empty features → fail (engine must produce features for a valid package).
    if not all_features:
        results["no_unprovenanced_fused_feature"] = False
    else:
        results["no_unprovenanced_fused_feature"] = all(
            len(f.source_evidence_ids) > 0 for f in all_features
        )

    # ── 9. no_conflict_suppression ───────────────────────────────────────
    # Proven from resolver diagnostics. No fallback — resolver_diag is
    # required by the engine contract.
    if resolver_diag is None:
        results["no_conflict_suppression"] = False
    else:
        results["no_conflict_suppression"] = (
            resolver_diag.suppressed_conflicts == 0
            and resolver_diag.candidate_conflicts == resolver_diag.emitted_conflicts
        )

    # ── 10. no_unit_mismatch_allowed ─────────────────────────────────────
    # Every accepted evidence item must have a canonical unit (or None).
    # Empty evidence → fail (same rationale as prohibition 1).
    if not evidence:
        results["no_unit_mismatch_allowed"] = False
    else:
        results["no_unit_mismatch_allowed"] = all(
            e.unit is None or e.unit in CANONICAL_UNITS
            for e in evidence
        )

    # ── 11. no_spatial_scope_collapse ────────────────────────────────────
    # State features must preserve source spatial scope. A fused feature
    # with scope X must only have source evidence with scope X (or
    # compatible: zone→zone, plot→plot, point→point).
    # DQ features are excluded (they aggregate across scopes).
    scope_ok = True
    for f in state_features:
        for sid in f.source_evidence_ids:
            src = ev_by_id.get(sid)
            if src is not None and src.spatial_scope != f.spatial_scope:
                scope_ok = False
                break
        if not scope_ok:
            break
    results["no_spatial_scope_collapse"] = scope_ok

    # ── 12. no_temporal_leakage_future_to_present ────────────────────────
    # Fused state features with non-forecast temporal_scope must not
    # contain forecast evidence in their source_evidence_ids.
    forecast_ids = frozenset(
        e.evidence_id for e in evidence
        if e.observation_type == "forecast"
    )
    temporal_ok = True
    for f in state_features:
        if f.temporal_scope.startswith("forecast_"):
            continue  # forecast features may contain forecast evidence
        for sid in f.source_evidence_ids:
            if sid in forecast_ids:
                temporal_ok = False
                break
        if not temporal_ok:
            break
    results["no_temporal_leakage_future_to_present"] = temporal_ok

    # ── 13. no_simulated_data_in_user_facing_context ─────────────────────
    # No fused feature may carry SIMULATED or SYNTHETIC flags.
    # Also check evidence for simulated flags.
    feature_simulated = any(
        "SIMULATED" in f or "SYNTHETIC" in f
        for feat in all_features
        for f in feat.flags
    )
    evidence_simulated = any(
        "SIMULATED" in f or "SYNTHETIC" in f
        for e in evidence
        for f in e.flags
    )
    results["no_simulated_data_in_user_facing_context"] = not (
        feature_simulated or evidence_simulated
    )

    # ── ASMAE Safety Prohibitions (graduated severity) ───────────────────
    asmae_diag_item = next((e for e in evidence if e.variable == "ASMAE_DIAGNOSTICS"), None)
    asmae_diag = {}
    if asmae_diag_item and asmae_diag_item.value:
        try:
            asmae_diag = json.loads(asmae_diag_item.value)
        except Exception:
            pass

    # Check if any ASMAE state variables are attempting state update
    # (i.e. they are allowed to update state and not diagnostic only)
    asmae_state_vars = (
        "ASMAE_VIGOR", "ASMAE_LAI", "ASMAE_CHLOROPHYLL", "ASMAE_CANOPY_WATER",
        "ASMAE_ROOT_ZONE_WATER", "ASMAE_SURFACE_WETNESS_EVENT", "ASMAE_STRUCTURE",
        "ASMAE_BARE_SOIL", "ASMAE_SALINITY_STRESS", "ASMAE_THERMAL_STRESS",
        "ASMAE_BIOTIC_CONFOUNDER_RISK"
    )
    asmae_state_items = [
        e for e in evidence
        if e.source_family == "asmae" and e.variable in asmae_state_vars
    ]
    any_state_update = any(
        e.state_update_allowed and not e.diagnostic_only for e in asmae_state_items
    )

    # Hard prohibitions:
    mode = asmae_diag.get("mode", "")
    results["no_asmae_state_update_from_shadow_mode"] = not (mode == "shadow" and any_state_update)

    scene_mode = asmae_diag.get("scene_stack_mode", "")
    results["no_asmae_state_update_from_mean_only_mode"] = not (scene_mode == "degraded_mean_only" and any_state_update)

    resolution_item = next((e for e in evidence if e.variable == "ASMAE_EFFECTIVE_RESOLUTION"), None)
    res_m = float(resolution_item.value) if resolution_item else 10.0
    results["no_1m_state_update_without_external_ground_truth"] = not (res_m <= 1.0 and any_state_update)

    training_weight_item = next((e for e in evidence if e.variable == "ASMAE_TRAINING_WEIGHT"), None)
    training_allowed = asmae_diag.get("weak_label_export_allowed", False)
    training_ok = True
    if training_weight_item:
        # 1) training labels must NEVER update state
        if training_weight_item.state_update_allowed or not training_weight_item.diagnostic_only:
            training_ok = False
        # 2) training label present but weak label export not allowed
        elif not training_allowed:
            training_ok = False
    results["no_training_label_without_weak_label_export_allowed"] = training_ok

    diag_vars = (
        "ASMAE_EFFECTIVE_RESOLUTION", "ASMAE_CONFIDENCE", "ASMAE_UNCERTAINTY",
        "ASMAE_RETROVALIDATION_SCORE", "ASMAE_BMA_DISAGREEMENT", "ASMAE_EXPORT_ELIGIBILITY",
        "ASMAE_TRAINING_WEIGHT", "ASMAE_RUN_STATUS", "ASMAE_CONTENT_HASH",
        "ASMAE_ARTIFACT_INSTANCE_HASH", "ASMAE_DIAGNOSTICS", "ASMAE_SOURCE_REALITY"
    )
    diag_items = [
        e for e in evidence
        if e.source_family == "asmae" and e.variable in diag_vars
    ]
    results["no_diagnostic_raster_as_state_evidence"] = not any(
        e.state_update_allowed or not e.diagnostic_only for e in diag_items
    )

    # Warning / quarantine prohibitions (only trigger failure if state update is attempted):
    layer1_export = asmae_diag.get("layer1_export_allowed", False)
    results["no_asmae_without_layer1_export_allowed"] = not (not layer1_export and any_state_update)

    op_count = asmae_diag.get("operator_count", 0)
    results["no_asmae_without_observation_operator_refs"] = not (op_count == 0 and any_state_update)

    retro_status = asmae_diag.get("retro_status")
    results["no_asmae_state_update_without_retrovalidation"] = not (retro_status != "success_with_holdouts" and any_state_update)

    scientific_pass_val = 1.0 if asmae_diag.get("scientific_pass") is True else 0.0
    radiometric_pass_val = 1.0 if asmae_diag.get("radiometric_overall_pass") is True else 0.0
    retro_score = float(asmae_diag.get("retro_mean_score") or 0.0)
    bma_disagreement = float(asmae_diag.get("bma_mean_disagreement") or 0.0)
    source_reality_score = 1.0 if scene_mode == "real_raster" else (0.5 if scene_mode == "degraded_mean_only" else 0.0)
    
    # Note: Uncalibrated posterior concentration is excluded from trust score calculation
    trust_score = (
        0.30 * scientific_pass_val
        + 0.25 * radiometric_pass_val
        + 0.25 * retro_score
        + 0.10 * (1.0 - bma_disagreement)
        + 0.10 * source_reality_score
    )
    results["no_low_confidence_asmae_to_layer2"] = not (trust_score < 0.25 and any_state_update)

    return results


def _all_fused(fused: FusedFeatureSet) -> List[FusedFeature]:
    return (
        fused.water_context +
        fused.vegetation_context +
        fused.phenology_context +
        fused.stress_evidence_context +
        fused.soil_site_context +
        fused.operational_context +
        fused.data_quality_context
    )


def build_diagnostics(
    evidence: List[EvidenceItem],
    envelopes: List[SourceEnvelope],
    conflicts: List[EvidenceConflict],
    gaps: List[EvidenceGap],
    quarantined: List[QuarantinedEvidence],
    *,
    fused: FusedFeatureSet,
    resolver_diag: ConflictResolverDiagnostics,
    spatial_fidelity: float = 0.5,
    provenance_completeness: float = 0.5,
) -> Layer1Diagnostics:
    """Build comprehensive diagnostics.

    Final freeze: fused and resolver_diag are required keyword arguments.
    The engine always provides them — no fallback needed.
    spatial_fidelity and provenance_completeness are computed by the engine
    and passed in to avoid hardcoded placeholder values.
    """

    # Source counts
    source_counts: Dict[str, int] = {}
    for e in evidence:
        source_counts[e.source_family] = source_counts.get(e.source_family, 0) + 1

    # Source health
    source_health: Dict[str, str] = {}
    for env in envelopes:
        source_health[env.source_family] = env.source_status

    # Confidence distribution (computed from non-diagnostic, state-updating evidence when available)
    conf_dist: Dict[str, float] = {}
    usable_evidence = [e for e in evidence if not e.diagnostic_only and e.state_update_allowed]
    eval_evidence = usable_evidence if usable_evidence else evidence
    for e in eval_evidence:
        if e.source_family not in conf_dist:
            conf_dist[e.source_family] = e.confidence
        else:
            conf_dist[e.source_family] = (conf_dist[e.source_family] + e.confidence) / 2.0

    # Conflict summary
    conflict_summary: Dict[str, int] = {}
    for c in conflicts:
        conflict_summary[c.conflict_type] = conflict_summary.get(c.conflict_type, 0) + 1

    # Gap summary
    gap_summary: Dict[str, int] = {}
    for g in gaps:
        gap_summary[g.gap_type] = gap_summary.get(g.gap_type, 0) + 1

    # Data health computed from envelopes status or fallback to usable evidence (F11/F12)
    if envelopes:
        usable_families = {
            env.source_family
            for env in envelopes
            if env.source_status in ("ok", "degraded")
        }
    else:
        usable_families = {
            e.source_family
            for e in evidence
            if not e.diagnostic_only
            and e.state_update_allowed
            and e.data_status not in ("unavailable", "simulated", "fallback")
        }
    core_present = usable_families.intersection(CORE_SOURCE_FAMILIES)
    optional_present = usable_families.intersection(OPTIONAL_SOURCE_FAMILIES)
    
    denominator = len(CORE_SOURCE_FAMILIES) + len(OPTIONAL_SOURCE_FAMILIES)
    source_completeness = (len(core_present) + len(optional_present)) / denominator if denominator > 0 else 0.0

    freshness_avg = (
        sum(e.freshness_score for e in evidence) / len(evidence)
    ) if evidence else 0.0

    conflict_penalty = min(1.0, len(conflicts) * 0.1)
    gap_penalty = min(1.0, sum(1 for g in gaps if g.severity == "blocking") * 0.3 +
                       sum(1 for g in gaps if g.severity == "warning") * 0.1)

    overall = max(0.0, min(1.0,
        source_completeness * 0.3 +
        freshness_avg * 0.3 +
        (1.0 - conflict_penalty) * 0.2 +
        (1.0 - gap_penalty) * 0.2
    ))

    status = "ok" if overall >= 0.5 else ("degraded" if overall >= 0.25 else "unusable")

    data_health = DataHealthScore(
        overall=round(overall, 3),
        source_completeness=round(source_completeness, 3),
        provenance_completeness=round(provenance_completeness, 3),
        freshness=round(freshness_avg, 3),
        spatial_fidelity=round(spatial_fidelity, 3),
        conflict_penalty=round(conflict_penalty, 3),
        gap_penalty=round(gap_penalty, 3),
        confidence_ceiling=min(conf_dist.values()) if conf_dist else 0.0,
        status=status,
    )

    # Compile warnings for quarantined ASMAE issues
    warnings: List[str] = []
    asmae_diag_item = next((e for e in evidence if e.variable == "ASMAE_DIAGNOSTICS"), None)
    if asmae_diag_item and asmae_diag_item.value:
        try:
            asmae_diag = json.loads(asmae_diag_item.value)
            
            # calculate trust score
            scientific_pass_val = 1.0 if asmae_diag.get("scientific_pass") is True else 0.0
            radiometric_pass_val = 1.0 if asmae_diag.get("radiometric_overall_pass") is True else 0.0
            retro_score = float(asmae_diag.get("retro_mean_score") or 0.0)
            bma_disagreement = float(asmae_diag.get("bma_mean_disagreement") or 0.0)
            confidence_item = next((e for e in evidence if e.variable == "ASMAE_CONFIDENCE"), None)
            confidence_val = float(confidence_item.value) if confidence_item else 0.5
            
            scene_mode = asmae_diag.get("scene_stack_mode", "")
            source_reality_score = 1.0 if scene_mode == "real_raster" else (0.5 if scene_mode == "degraded_mean_only" else 0.0)
            
            trust_score = (
                0.25 * scientific_pass_val
                + 0.20 * radiometric_pass_val
                + 0.20 * retro_score
                + 0.15 * (1.0 - bma_disagreement)
                + 0.10 * confidence_val
                + 0.10 * source_reality_score
            )
            
            # Warn if quarantined
            # Check if any state update is attempted
            asmae_state_items = [
                e for e in evidence
                if e.source_family == "asmae"
                and e.variable in (
                    "ASMAE_VIGOR", "ASMAE_LAI", "ASMAE_CHLOROPHYLL", "ASMAE_CANOPY_WATER",
                    "ASMAE_ROOT_ZONE_WATER", "ASMAE_SURFACE_WETNESS_EVENT", "ASMAE_STRUCTURE",
                    "ASMAE_BARE_SOIL", "ASMAE_SALINITY_STRESS", "ASMAE_THERMAL_STRESS",
                    "ASMAE_BIOTIC_CONFOUNDER_RISK"
                )
            ]
            any_state_update = any(e.state_update_allowed and not e.diagnostic_only for e in asmae_state_items)
            
            if not any_state_update:
                if not asmae_diag.get("layer1_export_allowed"):
                    warnings.append("ASMAE run is ineligible for Layer 1 state update (layer1_export_allowed is False). Quarantined.")
                if asmae_diag.get("operator_count", 0) == 0:
                    warnings.append("ASMAE run has no observation operator references. Quarantined.")
                if asmae_diag.get("retro_status") != "success_with_holdouts":
                    warnings.append("ASMAE run has no valid retrovalidation. Quarantined.")
                if trust_score < 0.25:
                    warnings.append(f"ASMAE run has low trust score ({trust_score:.4f}). Quarantined.")
                if scene_mode != "real_raster":
                    has_asmae_rasters = any(
                        e.source_family == "asmae"
                        and e.variable in (
                            "ASMAE_VIGOR", "ASMAE_LAI", "ASMAE_CHLOROPHYLL", "ASMAE_CANOPY_WATER",
                            "ASMAE_ROOT_ZONE_WATER", "ASMAE_SURFACE_WETNESS_EVENT", "ASMAE_STRUCTURE",
                            "ASMAE_BARE_SOIL", "ASMAE_SALINITY_STRESS", "ASMAE_THERMAL_STRESS",
                            "ASMAE_BIOTIC_CONFOUNDER_RISK"
                        )
                        for e in evidence
                    )
                    if has_asmae_rasters:
                        warnings.append("Mean-only quarantined: ASMAE scene_stack_mode is not real_raster.")
        except Exception:
            pass

    # Hard prohibition results — computed against fused features (required)
    prohibition_results = compute_hard_prohibitions(
        evidence, fused, conflicts, quarantined,
        resolver_diag=resolver_diag,
    )

    return Layer1Diagnostics(
        status=status,
        source_counts=source_counts,
        source_health=source_health,
        confidence_distribution={k: round(v, 3) for k, v in conf_dist.items()},
        quarantined_evidence=quarantined,
        quarantined_evidence_count=len(quarantined),
        conflict_summary=conflict_summary,
        gap_summary=gap_summary,
        hard_prohibition_results=prohibition_results,
        warnings=warnings,
        data_health=data_health,
    )



def validate_covariance_matrix(matrix: List[List[float]], tol: float = 1e-6) -> Tuple[bool, str]:
    """Validate full covariance matrix: must be symmetric and positive semi-definite (SPEC-D/T37)."""
    if not matrix or not isinstance(matrix, list):
        return False, "EMPTY_OR_INVALID_MATRIX"
    n = len(matrix)
    for row in matrix:
        if not isinstance(row, list) or len(row) != n:
            return False, "NON_SQUARE_MATRIX"
        for v in row:
            if not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
                return False, "NON_FINITE_COVARIANCE_VALUE"
    # 1. Symmetry
    for i in range(n):
        for j in range(i + 1, n):
            if abs(matrix[i][j] - matrix[j][i]) > tol:
                return False, f"ASYMMETRIC_COVARIANCE: |P[{i}][{j}] - P[{j}][{i}]| = {abs(matrix[i][j] - matrix[j][i])} > {tol}"
    # 2. Positive Semi-Definiteness (all diagonal elements non-negative)
    for i in range(n):
        if matrix[i][i] < -tol:
            return False, f"NEGATIVE_VARIANCE_ON_DIAGONAL: P[{i}][{i}] = {matrix[i][i]} < 0"
    # Check 2x2 determinant
    if n == 2:
        det = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
        if det < -tol:
            return False, f"NON_PSD_COVARIANCE_NEGATIVE_DETERMINANT: det={det} < 0"
    elif n > 2:
        # Check PSD using numpy if present, otherwise pure Python Cholesky decomposition
        try:
            import numpy as np
            eigs = np.linalg.eigvalsh(np.array(matrix, dtype=float))
            if any(e < -tol for e in eigs):
                return False, f"NON_PSD_COVARIANCE_NEGATIVE_EIGENVALUE: min_eig={min(eigs)}"
        except ImportError:
            # Pure Python Cholesky decomposition on A + tol*I to test PSD
            A = [[float(matrix[i][j]) for j in range(n)] for i in range(n)]
            for i in range(n):
                A[i][i] += tol
            L = [[0.0] * n for _ in range(n)]
            for i in range(n):
                for j in range(i + 1):
                    s = sum(L[i][k] * L[j][k] for k in range(j))
                    if i == j:
                        val = A[i][i] - s
                        if val < -1e-9:
                            return False, f"NON_PSD_COVARIANCE_NEGATIVE_PIVOT: pivot={val} at {i}"
                        L[i][j] = math.sqrt(max(0.0, val))
                    else:
                        if L[j][j] == 0.0:
                            if abs(A[i][j] - s) > 1e-7:
                                return False, f"NON_PSD_COVARIANCE_SINGULAR_MISMATCH: off-diagonal nonzero at ({i},{j})"
                            L[i][j] = 0.0
                        else:
                            L[i][j] = (A[i][j] - s) / L[j][j]
        except Exception as ex:
            # Fail closed on any computational error
            return False, f"COVARIANCE_EVALUATION_ERROR: {ex}"
    return True, "valid_psd_covariance"


def extract_covariance_matrices_recursive(
    data: Any,
    max_depth: int = 10,
    current_depth: int = 0,
    prefix: str = "",
) -> List[Tuple[str, Any]]:
    """Recursively extract covariance matrices from nested structures up to max_depth (R8-01, R8-03, R8-G05)."""
    if current_depth > max_depth or data is None:
        return []
    matrices: List[Tuple[str, Any]] = []
    if isinstance(data, dict):
        for k, v in data.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if k in ("covariance", "P", "cov", "uncertainty_matrix") and isinstance(v, list):
                matrices.append((path, v))
            elif isinstance(v, (dict, list)):
                matrices.extend(extract_covariance_matrices_recursive(v, max_depth, current_depth + 1, path))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            path = f"{prefix}[{idx}]"
            if isinstance(item, (dict, list)):
                matrices.extend(extract_covariance_matrices_recursive(item, max_depth, current_depth + 1, path))
    else:
        cov = getattr(data, "covariance", None) or getattr(data, "P", None)
        if cov is not None and isinstance(cov, list):
            path = f"{prefix}.covariance" if prefix else "covariance"
            matrices.append((path, cov))
        if hasattr(data, "__dict__") and isinstance(data.__dict__, dict):
            matrices.extend(extract_covariance_matrices_recursive(data.__dict__, max_depth, current_depth + 1, prefix))
    return matrices

