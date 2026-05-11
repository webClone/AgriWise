"""
Layer 6 Runner — Strategic Execution Engine v7.0

Production runner wiring all 5 scientific engines:
  1. InterventionSynthesisEngine — Cross-layer fusion + conflict resolution
  2. ResourceFeasibilityEngine — Operational constraint gating
  3. DAGExecutionEngine — Task state machine
  4. OutcomeEvaluationEngine — Multi-metric causal assessment
  5. CalibrationEngine — Prediction-vs-outcome learning loop

Smart Routing:
  FAST path  — Synthesis + Feasibility + DAG only (low-latency)
  FULL path  — All 5 engines including Outcome + Calibration

The orchestrator chooses FAST when op_context hasn't changed significantly.
FULL runs for deeper causal evaluation after completed interventions.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import asdict

from layer6_exec.schema import (
    Layer6Input, Layer6Output, RunMeta, QualityMetricsL6, AuditSnapshot,
    ExecutionState, TaskStatus, OperationalContext, UpstreamDigest,
    FeasibilityGrade,
)
from layer1_fusion.schemas import DataHealthScore
from layer3_decision.schema import DegradationMode

# Engines
from layer6_exec.evidence.normalizer import normalize_evidence_batch
from layer6_exec.engines.intervention_synthesis import (
    build_upstream_digest, synthesize_interventions,
)
from layer6_exec.engines.resource_feasibility import assess_feasibility
from layer6_exec.execution.dag_runner import build_execution_state
from layer6_exec.outcomes.metrics import compute_outcomes, project_outcomes
from layer6_exec.engines.calibration import propose_calibration
from layer6_exec.invariants import enforce_layer6_invariants

import logging
logger = logging.getLogger(__name__)

CODE_VERSION = "7.0.0"


def _stable_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _should_run_full(
    current_state: ExecutionState,
    evidence_batch: List[Dict[str, Any]],
) -> bool:
    """Smart routing: decide FAST vs FULL execution path.

    FULL when:
      - Completed tasks exist (need outcome evaluation)
      - Evidence batch is non-empty (need calibration)
      - Previous DAG has >3 tasks (complex state)
    """
    completed = sum(1 for s in current_state.tasks.values()
                    if s == TaskStatus.COMPLETED)
    if completed > 0:
        return True
    if len(evidence_batch) > 0:
        return True
    if len(current_state.tasks) > 3:
        return True
    return False


# ============================================================================
# Production Runner
# ============================================================================

def run_layer6(inputs: Layer6Input) -> Layer6Output:
    """Production Layer 6 Execution Loop with Smart Routing.

    Pipeline:
      1. Normalize evidence
      2. Build upstream digest (farmer explainability)
      3. Synthesize interventions + detect conflicts
      4. Gate through feasibility constraints
      5. Build execution DAG state
      6. [FULL only] Outcome evaluation
      7. [FULL only] Calibration learning loop
      8. Compute quality metrics + audit
      9. Package output with content_hash
    """
    ts_now = _now_iso()
    plot_id = getattr(inputs.tensor, "plot_id", "UNKNOWN") if inputs.tensor else "UNKNOWN"

    # ── 1. Normalize Evidence ────────────────────────────────────────────
    norm_evidence = normalize_evidence_batch(inputs.evidence_batch, plot_id)

    # ── 2. Build Upstream Digest ─────────────────────────────────────────
    digest = build_upstream_digest(
        tensor=inputs.tensor,
        veg_int=inputs.veg_int,
        decision_l3=inputs.decision_l3,
        nutrient_l4=inputs.nutrient_l4,
        bio_l5=inputs.bio_l5,
    )

    # ── 3. Intervention Synthesis + Conflict Detection ───────────────────
    portfolio, conflict_log = synthesize_interventions(digest)

    # ── 4. Resource Feasibility Gating ───────────────────────────────────
    area_ha = getattr(inputs.op_context, "plot_area_ha", 10.0)
    if not hasattr(inputs.op_context, "plot_area_ha"):
        area_ha = 10.0
    portfolio = assess_feasibility(portfolio, inputs.op_context, area_ha)

    # ── 5. DAG Execution State ───────────────────────────────────────────
    updated_state = build_execution_state(
        portfolio=portfolio,
        previous_state=inputs.current_state,
        evidence=norm_evidence,
        current_time=ts_now,
    )

    # ── Smart Routing ────────────────────────────────────────────────────
    run_full = _should_run_full(inputs.current_state, inputs.evidence_batch)

    outcome_report = []
    outcome_projections = []
    calibration_proposals = []

    if run_full:
        # ── 6. Outcome Evaluation ────────────────────────────────────────
        l1_ts = (getattr(inputs.tensor, "plot_timeseries", [])
                 if inputs.tensor else [])
        completed_interventions = [
            c for c in portfolio
            if updated_state.tasks.get(c.intervention_id) == TaskStatus.COMPLETED
        ]
        confounders = []
        if digest.rain_7d_mm > 30:
            confounders.append("HIGH_RAINFALL_PERIOD")
        if digest.heat_days > 0:
            confounders.append(f"HEAT_STRESS_{digest.heat_days}_DAYS")

        outcome_report = compute_outcomes(l1_ts, completed_interventions, confounders)

        # ── Outcome Projections (always useful) ──────────────────────────
        outcome_projections = project_outcomes(portfolio, digest)

        # ── 7. Calibration Learning Loop ─────────────────────────────────
        calibration_proposals = propose_calibration(norm_evidence, outcome_report, digest)
    else:
        # FAST path: still generate projections for farmer UI
        outcome_projections = project_outcomes(portfolio, digest)

    # ── 8. Quality Metrics ───────────────────────────────────────────────
    total_tasks = len(updated_state.tasks)
    completed_count = sum(1 for s in updated_state.tasks.values()
                         if s == TaskStatus.COMPLETED)
    completion_rate = completed_count / max(total_tasks, 1)

    feasibility_scores = {
        FeasibilityGrade.A: 1.0, FeasibilityGrade.B: 0.8,
        FeasibilityGrade.C: 0.6, FeasibilityGrade.D: 0.4,
        FeasibilityGrade.F: 0.0,
    }
    feas_values = [feasibility_scores.get(c.feasibility_grade, 0.5) for c in portfolio]
    mean_feasibility = sum(feas_values) / max(len(feas_values), 1)

    # Reliability = upstream confidence floor × feasibility score
    reliability = digest.min_upstream_confidence * mean_feasibility

    quality = QualityMetricsL6(
        decision_reliability=round(reliability, 3),
        missing_drivers=[],
        data_completeness={
            "L1_tensor": 1.0 if inputs.tensor else 0.0,
            "L2_veg_int": 1.0 if inputs.veg_int else 0.0,
            "L3_decision": 1.0 if inputs.decision_l3 else 0.0,
            "L4_nutrient": 1.0 if inputs.nutrient_l4 else 0.0,
            "L5_bio": 1.0 if inputs.bio_l5 else 0.0,
        },
        task_completion_rate=round(completion_rate, 3),
        upstream_confidence_floor=round(digest.min_upstream_confidence, 3),
        intervention_feasibility_score=round(mean_feasibility, 3),
        confounder_count=len(confounders) if run_full else 0,
        conflict_count=len(conflict_log),
    )

    # ── Audit Snapshot ───────────────────────────────────────────────────
    audit = AuditSnapshot(
        features_snapshot={
            "ndvi_current": digest.ndvi_current,
            "ndvi_trend": digest.ndvi_trend,
            "rain_7d_mm": digest.rain_7d_mm,
            "phenology_stage": digest.phenology_stage,
            "fungal_pressure": digest.fungal_pressure,
        },
        policy_snapshot={
            "smart_routing": "FULL" if run_full else "FAST",
            "conflict_rules_applied": len(conflict_log),
            "feasibility_gates": len(portfolio),
        },
        model_versions={"exec": CODE_VERSION},
        upstream_digest=digest,
        intervention_count=len(portfolio),
        conflict_count=len(conflict_log),
        calibration_count=len(calibration_proposals),
        dag_task_count=total_tasks,
    )

    # ── 9. Deterministic Run ID ──────────────────────────────────────────
    parent_ids = {
        "L1": getattr(inputs.tensor, "run_id", "") if inputs.tensor else "",
        "L3": (getattr(getattr(inputs.decision_l3, "run_meta", None), "run_id", "")
               if inputs.decision_l3 else ""),
    }
    run_hash = _stable_hash({
        "parents": parent_ids,
        "portfolio_size": len(portfolio),
        "conflict_count": len(conflict_log),
        "code": CODE_VERSION,
    })
    run_id = f"L6-{run_hash}"

    run_meta = RunMeta(
        run_id=run_id,
        parent_run_ids=parent_ids,
        generated_at=ts_now,
        degradation_mode=DegradationMode.NORMAL,
        engine_version=CODE_VERSION,
    )

    # ── Data Health ──────────────────────────────────────────────────────
    completeness_values = list(quality.data_completeness.values())
    overall_health = sum(completeness_values) / max(len(completeness_values), 1)
    health_status = "ok" if overall_health > 0.7 else ("degraded" if overall_health > 0.3 else "unusable")
    data_health = DataHealthScore(
        overall=round(overall_health, 3),
        source_completeness=round(overall_health, 3),
        status=health_status,
    )

    output = Layer6Output(
        run_meta=run_meta,
        intervention_portfolio=portfolio,
        conflict_log=conflict_log,
        updated_state=updated_state,
        evidence_registry=norm_evidence,
        outcome_report=outcome_report,
        outcome_projections=outcome_projections,
        calibration_proposals=calibration_proposals,
        upstream_digest=digest,
        quality_metrics=quality,
        data_health=data_health,
        audit=audit,
    )

    # Invariant Enforcement (Mandatory Gate)
    violations = enforce_layer6_invariants(output)
    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]
    if errors:
        for v in errors:
            logger.error(f"[Layer 6] INVARIANT ERROR: {v.check_name} — {v.description}")
    if warnings:
        for v in warnings:
            logger.warning(f"[Layer 6] INVARIANT WARN: {v.check_name} — {v.description}")

    return output


# ============================================================================
# Orchestrator-Compatible Entry Point
# ============================================================================

from orchestrator_v2.schema import OrchestratorInput
import math as _math


def _compute_plot_area_ha(polygon_coords) -> float:
    """Compute polygon area in hectares using the Shoelace formula.

    polygon_coords: GeoJSON-style list of [lng, lat] or (lng, lat) pairs
    (the outer ring of a Polygon).  Returns 0.0 if coords are invalid.
    """
    try:
        if not polygon_coords or not isinstance(polygon_coords, (list, tuple)):
            return 0.0
        # Flatten if nested ([[lat,lng], ...] or [[[lng,lat],...]] GeoJSON)
        pts = polygon_coords
        if pts and isinstance(pts[0], (list, tuple)) and isinstance(pts[0][0], (list, tuple)):
            pts = pts[0]  # unwrap GeoJSON outer ring
        if len(pts) < 3:
            return 0.0
        # Convert [lng, lat] degrees -> approximate metres using equirectangular
        lat0 = sum(p[1] for p in pts) / len(pts)  # centroid lat
        R = 6371000.0  # Earth radius metres
        cos_lat = _math.cos(_math.radians(lat0))
        # Shoelace
        area_deg2 = 0.0
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i][0], pts[i][1]
            x1, y1 = pts[(i + 1) % n][0], pts[(i + 1) % n][1]
            area_deg2 += x0 * y1 - x1 * y0
        area_m2 = abs(area_deg2) / 2.0 * (R * cos_lat) * (_math.pi / 180.0) * R * (_math.pi / 180.0)
        return round(area_m2 / 10_000.0, 3)  # m² -> ha
    except Exception:
        return 0.0


def run_layer6_exec(inputs: OrchestratorInput, *args) -> Layer6Output:
    """Entry point called by orchestrator_v2 runner.

    Args mapping: inputs, tensor, veg_int, decision_l3, nutrient_l4, bio_l5
    """
    tensor = args[0] if len(args) > 0 else None
    veg_int = args[1] if len(args) > 1 else None
    decision_l3 = args[2] if len(args) > 2 else None
    nutrient_l4 = args[3] if len(args) > 3 else None
    bio_l5 = args[4] if len(args) > 4 else None

    # Build operational context from orchestrator inputs
    op = inputs.operational_context if isinstance(inputs.operational_context, dict) else {}
    resources = op.get("resources", {})
    constraints = op.get("constraints", {})

    # Wire evidence from both the 'evidence' key and 'user_evidence'
    # (user_evidence contains photos, soil analyses, sensor data from frontend)
    evidence = op.get("evidence", [])
    user_evidence = op.get("user_evidence", [])
    if isinstance(user_evidence, list) and user_evidence:
        evidence = (evidence or []) + user_evidence

    # GAP 9: Compute real plot area from polygon_coords using Shoelace formula
    # Fallback to 10 ha only when no polygon is available.
    plot_area_ha = _compute_plot_area_ha(op.get("polygon_coords")) or 10.0

    l6_in = Layer6Input(
        tensor=tensor,
        veg_int=veg_int,
        decision_l3=decision_l3,
        nutrient_l4=nutrient_l4,
        bio_l5=bio_l5,
        op_context=OperationalContext(
            equipment_ids=resources.get("equipment", []),
            workforce_available=resources.get("workforce", True),
            labor_hours_available=float(resources.get("labor_hours", 40.0)),
            water_quota_remaining=float(constraints.get("water_quota", 1000.0)),
            budget_remaining=float(constraints.get("budget", 5000.0)),
            permissions=[],
            season_stage=op.get("season_stage", "MID"),
            regulatory_zone=op.get("regulatory_zone", "STANDARD"),
            plot_area_ha=plot_area_ha,
        ),
        evidence_batch=evidence,
        current_state=ExecutionState(tasks={}, logs=[], last_updated=""),
    )

    return run_layer6(l6_in)
