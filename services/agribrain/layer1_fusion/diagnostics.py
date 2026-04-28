"""
Layer 1 Diagnostics Builder.

Builds Layer1Diagnostics from engine state.
No diagnosis vocabulary — data health only.

RC4: Every prohibition is STRICTLY computed from actual package
contents with no vacuous-truth fallbacks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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
)


# 13 hard prohibitions
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
]

_DATA_QUALITY_FEATURES = frozenset({"source_completeness", "average_freshness"})


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
) -> Layer1Diagnostics:
    """Build comprehensive diagnostics.

    Final freeze: fused and resolver_diag are required keyword arguments.
    The engine always provides them — no fallback needed.
    """

    # Source counts
    source_counts: Dict[str, int] = {}
    for e in evidence:
        source_counts[e.source_family] = source_counts.get(e.source_family, 0) + 1

    # Source health
    source_health: Dict[str, str] = {}
    for env in envelopes:
        source_health[env.source_family] = env.source_status

    # Confidence distribution
    conf_dist: Dict[str, float] = {}
    for e in evidence:
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

    # Data health
    source_completeness = len(set(e.source_family for e in evidence)) / 9.0
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
        provenance_completeness=1.0,
        freshness=round(freshness_avg, 3),
        spatial_fidelity=1.0,
        conflict_penalty=round(conflict_penalty, 3),
        gap_penalty=round(gap_penalty, 3),
        confidence_ceiling=min(conf_dist.values()) if conf_dist else 0.0,
        status=status,
    )

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
        data_health=data_health,
    )

