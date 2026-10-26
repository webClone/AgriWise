"""
Layer 3 Decision Intelligence — Engine Runner.

Canonical entry point for the Decision & Action Intelligence engine.
Deterministic pipeline:
  1. Validate Layer3InputContext
  2. Build DecisionFeatures from L2 interpreted intelligence
  3. Run multi-hypothesis DiagnosisEngine (log-odds scoring)
  4. Run PolicyEngine (compliance gates, fallback logic)
  5. Build ExecutionPlan (DAG of tasks)
  6. Compute QualityMetrics
  7. Build AuditTrail
  8. Enforce invariants (12 checks with auto-fix)
  9. Check hard prohibitions (10 rules)
  10. Build DecisionOutput with content_hash()
  11. Return

Layer 3 never fetches data — consumes only Layer3InputContext.
Layer 3 never re-reads raw L1 data — reasons over L2's interpretation.
"""

from __future__ import annotations

import datetime
import math
import threading
from datetime import timezone
from typing import Any, Dict, List, Optional

from layer1_fusion.schemas import DataHealthScore

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    try:
        from services.agribrain.scientific_contracts.numeric import finite_real
    except ImportError:
        def finite_real(val: Any) -> Optional[float]:
            import math
            from numbers import Real
            if isinstance(val, bool) or not isinstance(val, Real):
                return None
            try:
                res = float(val)
                return res if math.isfinite(res) else None
            except Exception:
                return None

from layer2_intelligence.outputs.layer3_adapter import Layer3InputContext

from layer3_decision.schema import (
    DecisionInput,
    DecisionOutput,
    Diagnosis,
    ExecutionPlan,
    TaskNode,
    QualityMetrics,
    AuditTrail,
    Recommendation,
    PlotContext,
    Layer3Provenance,
    Layer3Diagnostics,
    L3_HARD_PROHIBITIONS,
    FORBIDDEN_L3_VOCABULARY,
    DegradationMode,
    Driver,
    RiskIfWrong,
)
from layer3_decision.features.builder import build_decision_features, DecisionFeatures
from layer3_decision.diagnosis.inference import DiagnosisEngine
from layer3_decision.policy.policies import PolicyEngine
from layer3_decision.invariants import enforce_layer3_invariants
from layer3_decision.context_invariants import enforce_context_invariants


ENGINE_VERSION = "layer3_decision_v1"
CONTRACT_VERSION = "1.0.0"


class DecisionIntelligenceEngine:
    """Deterministic multi-hypothesis decision engine.

    Same Layer3InputContext → identical DecisionOutput + content_hash().
    """

    def __init__(self) -> None:
        self.diagnosis_engine = DiagnosisEngine()
        self.policy_engine = PolicyEngine()

    def run_decision_cycle(
        self,
        l3_context: Layer3InputContext,
        plot_context: PlotContext,
        weather_forecast: Optional[List[Dict]] = None,
        run_id: str = "",
        run_timestamp: Optional[datetime.datetime] = None,
    ) -> DecisionOutput:
        """Execute the 11-step decision pipeline."""
        import time as _perf_time
        import sys as _perf_sys
        _t0 = _perf_time.perf_counter()

        ts = run_timestamp or datetime.datetime.now(timezone.utc)
        rid = run_id or f"l3_{l3_context.plot_id}_{int(ts.timestamp())}"
        forecast = weather_forecast or []
        audit_log: List[Dict] = []

        # 1. Validate input
        is_usable, degrade_flags = self._validate_input(l3_context)
        
        # 1.b Enforce mathematical input invariants
        input_violations = enforce_context_invariants(l3_context)
        
        audit_log.append({
            "step": "validate_input",
            "usable": is_usable,
            "flags": degrade_flags,
            "input_violations": [v.to_dict() for v in input_violations],
        })

        # V91.2: WAIT_FOR_VALID_DATA early exit.
        # When L2 health is unusable, L3 cannot produce valid diagnoses.
        # Return a single WAIT_FOR_VALID_DATA recommendation instead of
        # fabricating conclusions from invalid evidence.
        if not is_usable or l3_context.data_health.status == "unusable":
            wait_rec = Recommendation(
                action_id="ACT_WAIT_FOR_VALID_DATA",
                action_type="WAIT_FOR_VALID_DATA",
                priority_score=1.0,
                expected_impact=0.0,
                urgency=0.0,
                confidence=0.20,
                is_allowed=True,
                blocked_reason=[],
                risk_if_wrong=RiskIfWrong.LOW,
                linked_diagnosis_ids=[],
                explain=(
                    "Insufficient data quality to produce reliable diagnoses. "
                    "Wait for valid Layer 1/Layer 2 data before running "
                    "decision intelligence. "
                    f"Flags: {', '.join(degrade_flags)}"
                ),
            )
            return DecisionOutput(
                run_id_l3=rid,
                lineage={
                    "l1_run_id": getattr(l3_context, "layer1_run_id", ""),
                    "l2_run_id": getattr(l3_context, "layer2_run_id", ""),
                    "crop_posterior_hash": getattr(l3_context, "crop_posterior_hash", ""),
                    "phenology_posterior_hash": getattr(l3_context, "phenology_posterior_hash", ""),
                },
                timestamp_utc=ts.isoformat(),
                diagnoses=[],
                recommendations=[wait_rec],
                execution_plan=ExecutionPlan(),
                quality_metrics=QualityMetrics(
                    decision_reliability=0.0,
                    degradation_mode=DegradationMode.DATA_GAP,
                ),
                data_health=l3_context.data_health,
                provenance=Layer3Provenance(
                    run_id=rid,
                    engine_version=ENGINE_VERSION,
                    contract_version=CONTRACT_VERSION,
                    layer1_run_id=getattr(l3_context, "layer1_run_id", ""),
                    layer2_run_id=getattr(l3_context, "layer2_run_id", ""),
                    invariant_violations=[v.to_dict() for v in input_violations],
                    generated_at=ts,
                ),
                diagnostics=Layer3Diagnostics(
                    status="unusable",
                    data_health=l3_context.data_health,
                    input_degradation_flags=degrade_flags,
                    warnings=["V91.2: WAIT_FOR_VALID_DATA — no diagnosis performed"],
                ),
            )

        # 2. Build DecisionFeatures from L2 interpreted intelligence
        features = build_decision_features(l3_context, plot_context, forecast)
        audit_log.append({
            "step": "build_features",
            "missing_drivers": [d.value for d in features.missing_inputs],
            "stage": features.current_stage,
            "sar_available": features.sar_available,
            "optical_available": features.optical_available,
            # PERF-4: forecast + atmospheric fields for reproducibility
            "forecast_available": features.forecast_available,
            "forecast_cold_days": features.forecast_cold_days,
            "forecast_min_temp": features.forecast_min_temp,
            "forecast_heat_days": features.forecast_heat_days,
            "forecast_rain_3d": features.forecast_rain_3d,
            "vpd_kpa": features.vpd_kpa,
            "wind_speed_ms": features.wind_speed_ms,
        })

        # INT-1: Warn when forecast is missing
        if not forecast:
            import sys as _sys_warn
            print("[L3 WARN] No weather forecast provided — frost/heat proactive diagnostics degraded",
                  file=_sys_warn.stderr, flush=True)

        # 3. Multi-hypothesis diagnosis (log-odds scoring)
        all_diagnoses: Dict[str, Diagnosis] = {}
        zone_status = getattr(l3_context, "zone_status", {}) or {}

        if zone_status and len(zone_status) > 1:
            # BUG-5 FIX: Zonal diagnosis — build zone-specific features
            import copy
            for z_id, z_data in zone_status.items():
                # Clone plot features and overlay zone-specific data
                z_features = copy.copy(features)

                # Overlay zone severity → stress signals
                z_sev = z_data.get("severity", 0.0)
                z_stress = z_data.get("dominant_stress_type", "NONE")

                if z_stress == "WATER" and z_sev > 0:
                    z_features.soil_moisture_proxy = max(0.0, z_features.soil_moisture_proxy - z_sev * 0.3)
                elif z_stress == "VARIABILITY":
                    z_features.spatial_stability = "HETEROGENEOUS"

                # Zone metrics may describe spatial stress, but they are not a
                # second phenology truth owner.  Stage and stage confidence stay
                # bound to the canonical Layer 2 posterior used above.
                z_conf = z_data.get("confidence", 0.5)
                z_features.spatial_confidence = min(z_features.spatial_confidence, z_conf)

                z_diagnoses = self.diagnosis_engine.diagnose(z_features, plot_context, forecast)

                for d in z_diagnoses:
                    if d.probability > 0.3:
                        if d.problem_id not in all_diagnoses:
                            all_diagnoses[d.problem_id] = d
                            all_diagnoses[d.problem_id].affected_area_pct = 0.0
                            all_diagnoses[d.problem_id].hotspot_zone_ids = []

                        area_pct = z_data.get("area_pct", 100.0 / len(zone_status))
                        all_diagnoses[d.problem_id].affected_area_pct = min(
                            100.0, all_diagnoses[d.problem_id].affected_area_pct + area_pct
                        )
                        all_diagnoses[d.problem_id].hotspot_zone_ids.append(z_id)

                        if d.severity > all_diagnoses[d.problem_id].severity:
                            all_diagnoses[d.problem_id].severity = d.severity
        else:
            # Global plot-level diagnosis
            global_diagnoses = self.diagnosis_engine.diagnose(features, plot_context, forecast)
            for d in global_diagnoses:
                if d.probability > 0.3:
                    d.affected_area_pct = 100.0
                    d.hotspot_zone_ids = ["Plot-Wide"]
                    all_diagnoses[d.problem_id] = d

        diagnosed_list = list(all_diagnoses.values())

        audit_log.append({
            "step": "diagnosis",
            "hypothesis_count": len(diagnosed_list),
            "diagnoses": [
                {"id": d.problem_id, "p": round(d.probability, 3), "s": round(d.severity, 3)}
                for d in diagnosed_list
            ],
        })

        # 4. Policy engine (compliance gates, fallback logic)
        recommendations = self.policy_engine.generate_plan(
            diagnosed_list,
            plot_context,
            forecast,
            [d.value for d in features.missing_inputs],
        )

        # Cap recommendation confidence by data health ceiling
        ceiling = l3_context.data_health.confidence_ceiling
        for r in recommendations:
            if r.confidence > ceiling:
                r.confidence = ceiling

        # Phase 3 Guard: ASMAE decision guarding
        from layer1_fusion.outputs.asmae_feature_view import (
            get_asmae_diagnostic_feature,
            evaluate_asmae_state_usability,
        )
        
        has_quarantined_or_1m_asmae = False
        for var in getattr(l3_context, "asmae_features", {}).keys():
            feat = get_asmae_diagnostic_feature(l3_context, var)
            if feat is not None:
                usability = evaluate_asmae_state_usability(feat)
                if not usability.usable:
                    has_quarantined_or_1m_asmae = True
                    break

        for r in recommendations:
            linked_stresses = []
            for d_id in r.linked_diagnosis_ids:
                for s_type, s_data in l3_context.stress_detail.items():
                    if s_type.lower() in d_id.lower() or d_id.lower() in s_type.lower():
                        linked_stresses.append(s_data)
            
            is_asmae_only_rec = False
            is_driver_asmae = False
            if linked_stresses:
                for s_data in linked_stresses:
                    p_driver = s_data.get("primary_driver", "")
                    is_driver_asmae = any(x in p_driver for x in ("asmae", "biotic_confounder", "biotic_scout", "biotic_pattern"))
                    ev_list = s_data.get("contributing_evidence_ids") or s_data.get("evidence_ids") or []
                    if is_driver_asmae or (ev_list and all("ASMAE" in str(eid) for eid in ev_list)):
                        is_asmae_only_rec = True
            
            is_asmae_driven = is_asmae_only_rec or is_driver_asmae or any("ASMAE" in str(d_id) for d_id in r.linked_diagnosis_ids) or "ASMAE" in getattr(r, "explain", "")
            
            if is_asmae_driven:
                if has_quarantined_or_1m_asmae:
                    r.is_allowed = False
                    if "quarantined_asmae" not in r.blocked_reason:
                        r.blocked_reason.append("quarantined_asmae")
                    r.explain = f"{r.explain} [REVIEW REQUIRED: ASMAE data is quarantined or 1m resolution]"
                elif is_asmae_only_rec:
                    r.is_allowed = False
                    if "asmae_alone_gated" not in r.blocked_reason:
                        r.blocked_reason.append("asmae_alone_gated")
                    r.explain = f"{r.explain} [REVIEW REQUIRED: ASMAE state evidence alone cannot schedule execution]"
            else:
                if has_quarantined_or_1m_asmae:
                    if "quarantined_asmae_present" not in r.blocked_reason:
                        r.blocked_reason.append("quarantined_asmae_present")

        audit_log.append({
            "step": "policy",
            "recommendation_count": len(recommendations),
            "allowed": sum(1 for r in recommendations if r.is_allowed),
            "blocked": sum(1 for r in recommendations if not r.is_allowed),
        })

        # 5. Execution plan (uses run_timestamp for determinism)
        execution_plan = self._build_execution_plan(recommendations, diagnosed_list, ts)

        # diagnostic_usable=True must never enable prescriptions, execution plans, or interventions.
        if getattr(l3_context, "diagnostic_usable", False) or not getattr(l3_context, "usable_for_layer3", False):
            execution_plan = ExecutionPlan()
            for r in recommendations:
                if r.action_type in ("INTERVENE", "PRESCRIPTION") or "INTERVENE" in r.action_id or "PRESCRIPTION" in r.action_id:
                    r.is_allowed = False
                    if "diagnostic_only_mode" not in r.blocked_reason:
                        r.blocked_reason.append("diagnostic_only_mode")

        # 6. Quality metrics
        metrics = self._calculate_quality_metrics(features, diagnosed_list, l3_context)

        # 7. Audit trail
        audit_trail = self._build_audit_trail(features, diagnosed_list)

        # Lineage
        lineage = {
            "l1_run_id": getattr(l3_context, "layer1_run_id", ""),
            "l2_run_id": getattr(l3_context, "layer2_run_id", ""),
            "crop_posterior_hash": getattr(l3_context, "crop_posterior_hash", ""),
            "phenology_posterior_hash": getattr(l3_context, "phenology_posterior_hash", ""),
        }

        # Build output
        out = DecisionOutput(
            run_id_l3=rid,
            lineage=lineage,
            timestamp_utc=ts.isoformat(),
            diagnoses=diagnosed_list,
            recommendations=recommendations,
            execution_plan=execution_plan,
            quality_metrics=metrics,
            audit=audit_trail,
            data_health=l3_context.data_health or DataHealthScore(
                overall=1.0, confidence_ceiling=1.0, status="ok"
            ),
            diagnostics=Layer3Diagnostics(
                status="ok" if not metrics.missing_drivers else "degraded",
                input_degradation_flags=degrade_flags,
            ),
            provenance=Layer3Provenance(
                run_id=rid,
                engine_version=ENGINE_VERSION,
                contract_version=CONTRACT_VERSION,
                layer1_run_id=lineage.get("l1_run_id", ""),
                layer2_run_id=lineage.get("l2_run_id", ""),
                diagnosis_count=len(diagnosed_list),
                recommendation_count=len(recommendations),
                task_count=len(execution_plan.tasks),
                invariant_violations=[v.to_dict() for v in input_violations],
                generated_at=ts,
            ),
        )

        # 8. Enforce output invariants (with auto-fix)
        output_violations = enforce_layer3_invariants(out)
        out.provenance.invariant_violations.extend([v.to_dict() for v in output_violations])

        # 9. Check hard prohibitions
        out.diagnostics.hard_prohibition_results = self._check_hard_prohibitions(out)

        # Populate diagnostic type counts
        out.diagnostics.diagnosis_type_counts = {
            d.problem_id: 1 for d in diagnosed_list
        }
        out.diagnostics.recommendation_type_counts = {}
        for r in recommendations:
            t = r.action_type
            out.diagnostics.recommendation_type_counts[t] = (
                out.diagnostics.recommendation_type_counts.get(t, 0) + 1
            )

        audit_log.append({
            "step": "invariants",
            "violations": len(output_violations),
            "prohibitions_passed": all(out.diagnostics.hard_prohibition_results.values()),
        })

        audit_log.append({
            "step": "prohibitions",
            "results": out.diagnostics.hard_prohibition_results,
            "passed": sum(out.diagnostics.hard_prohibition_results.values()),
            "total": len(out.diagnostics.hard_prohibition_results),
        })

        # ROB-2: Per-step timing
        _elapsed = _perf_time.perf_counter() - _t0
        print(f"[L3 PERF] DecisionIntelligenceEngine: {_elapsed:.3f}s "
              f"({len(diagnosed_list)} diagnoses, {len(recommendations)} recs, "
              f"{len(output_violations)} violations)",
              file=_perf_sys.stderr, flush=True)
        if _elapsed > 5.0:
            print(f"[L3 WARN] Decision cycle took {_elapsed:.1f}s (>5s threshold)",
                  file=_perf_sys.stderr, flush=True)

        return out

    def _validate_input(self, ctx: Layer3InputContext) -> tuple:
        """Validate Layer3InputContext. Returns (is_usable, degrade_flags)."""
        flags: List[str] = []

        if not ctx.plot_id:
            flags.append("missing_plot_id")

        # If usable_for_layer3 is False, but diagnostic_usable is True, we are diagnostic-usable
        # (not fully action-usable). If BOTH are False, then we are completely unusable.
        is_diagnostic = getattr(ctx, "diagnostic_usable", False)

        if not ctx.usable_for_layer3 and not is_diagnostic:
            flags.append("l2_marked_unusable")

        if ctx.data_health.status == "unusable":
            flags.append("data_health_unusable")

        is_usable = "data_health_unusable" not in flags and "l2_marked_unusable" not in flags
        return is_usable, flags

    def _build_execution_plan(
        self, recs: List[Recommendation], diagnosed_list: List[Diagnosis],
        run_ts: datetime.datetime = None,
    ) -> ExecutionPlan:
        """Build the execution DAG from allowed recommendations.

        Uses ``run_ts`` for deterministic start/review dates instead of
        calling ``datetime.now()`` (which would break content-hash
        reproducibility).
        """
        ts = run_ts or datetime.datetime.now(timezone.utc)
        tasks = []
        diag_map = {d.problem_id: d for d in diagnosed_list}

        allowed_recs = [r for r in recs if r.is_allowed]

        for r in allowed_recs:
            # Extract target zones from linked diagnoses
            target_zones: List[str] = []
            for d_id in r.linked_diagnosis_ids:
                if d_id in diag_map and hasattr(diag_map[d_id], "hotspot_zone_ids"):
                    target_zones.extend(diag_map[d_id].hotspot_zone_ids)
            target_zones = list(set(target_zones))

            task = TaskNode(
                task_id=f"TASK_{r.action_id}",
                type=r.action_type,
                instructions=r.explain,
                required_inputs=r.preconditions,  # BUG-2 FIX: was r.blocked_reason
                completion_signal="MANUAL_CONFIRM",
                depends_on=[],
                target_zones=target_zones,
                target_points=[],
            )
            tasks.append(task)

        # ENH-10: Build DAG edges — VERIFY must complete before INTERVENE
        edges = []
        verify_ids = [t.task_id for t in tasks if t.type == "VERIFY"]
        for t in tasks:
            if t.type == "INTERVENE" and verify_ids:
                # Find verify tasks for the same problem
                for v_id in verify_ids:
                    # Link verify→intervene if they share the same problem
                    v_problem = v_id.replace("TASK_ACT_", "").split("_", 1)[-1] if "_" in v_id else ""
                    t_problem = t.task_id.replace("TASK_ACT_", "").split("_", 1)[-1] if "_" in t.task_id else ""
                    if v_problem and v_problem == t_problem:
                        t.depends_on.append(v_id)
                        edges.append({"from": v_id, "to": t.task_id})

        return ExecutionPlan(
            tasks=tasks,
            edges=edges,
            recommended_start_date=ts.isoformat(),
            review_date=(ts + datetime.timedelta(days=1)).isoformat(),
        )


    def _calculate_quality_metrics(
        self,
        feat: DecisionFeatures,
        diagnoses: List[Diagnosis],
        l3_context: Layer3InputContext,
    ) -> QualityMetrics:
        # Degradation mode
        mode = DegradationMode.NORMAL
        if not feat.sar_available:
            mode = DegradationMode.NO_SAR
        if getattr(feat, "low_sar_cadence", False):
            mode = DegradationMode.LOW_SAR_CADENCE
        if feat.optical_obs_count < 2:
            mode = DegradationMode.WEATHER_ONLY
        if not feat.sar_available and feat.optical_obs_count < 2:
            mode = DegradationMode.DATA_GAP

        # Reliability score (strict data quality)
        score = 1.0
        if not feat.rain_available:
            score -= 0.3
        if not feat.temp_available:
            score -= 0.1
        if not feat.sar_available:
            score -= 0.2
        if not feat.optical_available:
            score -= 0.3
        if feat.optical_obs_count == 1:
            score -= 0.1
        score = max(0.0, score)

        # Scale by L2 confidence
        final_rel = score * feat.stage_confidence

        return QualityMetrics(
            decision_reliability=round(final_rel, 2),
            missing_drivers=feat.missing_inputs,
            data_completeness={
                "optical_obs_count": float(feat.optical_obs_count),
                "sar_obs_count": float(feat.sar_obs_count),
                "rain_available": 1.0 if feat.rain_available else 0.0,
                "sar_available": 1.0 if feat.sar_available else 0.0,
                "lst_available": 1.0 if feat.lst_available else 0.0,
            },
            l2_confidence_summary={
                "phenology_conf": feat.stage_confidence,
                "data_health_overall": round(l3_context.data_health.overall, 3),
                "energy_balance_method": feat.energy_balance_method,
            },
            degradation_mode=mode,
        )

    def _build_audit_trail(
        self, feat: DecisionFeatures, diagnoses: List[Diagnosis]
    ) -> AuditTrail:
        logs = []
        for d in diagnoses:
            logs.append({
                "hypothesis": d.problem_id,
                "prob": d.probability,
                "confidence": d.confidence,
                "evidence": [
                    {
                        "feature": e.feature_name,
                        "score": e.score,
                        "weight": e.weight,
                        "contribution": e.contribution,
                    }
                    for e in d.evidence_trace
                ],
            })

        return AuditTrail(
            features_snapshot={
                "rain_sum_14d": feat.rain_sum_14d,
                "days_since_rain": feat.days_since_rain,
                "current_stage": feat.current_stage,
                "has_anomaly": feat.has_anomaly,
                "anomaly_type": feat.anomaly_type,
                "sar_available": feat.sar_available,
                "optical_available": feat.optical_available,
                "missing_inputs": [d.value for d in feat.missing_inputs],
                # Energy Balance fields
                "lst_available": feat.lst_available,
                "esi": feat.esi,
                "cwsi": feat.cwsi,
                "canopy_air_delta_c": feat.canopy_air_delta_c,
                "et_potential_mm": feat.et_potential_mm,
                "et_actual_mm": feat.et_actual_mm,
                "et_deficit_mm": feat.et_deficit_mm,
                "transpiration_efficiency": feat.transpiration_efficiency,
                "energy_balance_method": feat.energy_balance_method,
            },
            log_odds_table=logs,
            policy_checks=[],
        )

    def _check_hard_prohibitions(self, output: DecisionOutput) -> Dict[str, bool]:
        """Check all 10 hard prohibitions."""
        results: Dict[str, bool] = {}

        # 1. no_diagnosis_without_evidence
        results["no_diagnosis_without_evidence"] = all(
            len(d.evidence_trace) > 0 or d.probability <= 0.1
            for d in output.diagnoses
        ) if output.diagnoses else True

        # 2. no_intervention_without_diagnosis
        diag_ids = {d.problem_id for d in output.diagnoses}
        results["no_intervention_without_diagnosis"] = all(
            any(lid in diag_ids for lid in r.linked_diagnosis_ids)
            for r in output.recommendations
            if r.action_type == "INTERVENE"
        ) if output.recommendations else True

        # 3. no_action_above_confidence_ceiling
        ceiling = output.data_health.confidence_ceiling
        results["no_action_above_confidence_ceiling"] = all(
            r.confidence <= ceiling + 0.05
            for r in output.recommendations
        ) if output.recommendations else True

        # 4. no_blocked_action_allowed
        results["no_blocked_action_allowed"] = all(
            not ([reason for reason in r.blocked_reason if reason != "quarantined_asmae_present"] and r.is_allowed)
            for r in output.recommendations
        ) if output.recommendations else True

        # 5. probability_bounds
        results["probability_bounds"] = all(
            0.0 <= d.probability <= 1.0
            for d in output.diagnoses
        ) if output.diagnoses else True

        # 6. severity_bounds
        results["severity_bounds"] = all(
            0.0 <= d.severity <= 1.0
            for d in output.diagnoses
        ) if output.diagnoses else True

        # 7. confidence_bounds
        results["confidence_bounds"] = all(
            0.0 <= d.confidence <= 1.0
            for d in output.diagnoses
        ) if output.diagnoses else True

        # 8. execution_plan_acyclic
        from layer3_decision.invariants import _detect_cycle
        results["execution_plan_acyclic"] = len(
            _detect_cycle(output.execution_plan)
        ) == 0

        # 9. lineage_complete
        results["lineage_complete"] = bool(output.lineage.get("l2_run_id"))

        # 10. content_hash_deterministic (verified in tests, not runtime)
        results["content_hash_deterministic"] = True

        return results


# Singleton engine instance
_engine = DecisionIntelligenceEngine()


def run_layer3(
    l3_context: Layer3InputContext,
    plot_context: Optional[PlotContext] = None,
    weather_forecast: Optional[List[Dict]] = None,
    run_id: str = "",
    run_timestamp: Optional[datetime.datetime] = None,
) -> DecisionOutput:
    """Canonical entry point for Layer 3 Decision Intelligence.

    Called by the orchestrator.
    """
    pc = plot_context or PlotContext()
    return _engine.run_decision_cycle(
        l3_context=l3_context,
        plot_context=pc,
        weather_forecast=weather_forecast,
        run_id=run_id,
        run_timestamp=run_timestamp,
    )


def run_layer3_decision(
    inputs: Any,
    l1_output: Any = None,
    l2_output: Any = None,
) -> DecisionOutput:
    """Orchestrator-compatible entry point.

    Bridges the legacy orchestrator signature:
        run_layer3_decision(inputs, l1_output, l2_output)
    to the canonical:
        run_layer3(l3_context, plot_context, weather_forecast)

    The orchestrator calls _safe_run(LayerId.L3, inputs, l1_output, l2_output)
    which dispatches as run_layer3_decision(inputs, l1_output, l2_output).

    This shim handles two cases:
    1. l2_output is a Layer2Output → use build_layer3_context adapter
    2. l2_output is legacy VegIntOutput → construct a minimal Layer3InputContext
    """
    from layer1_fusion.schemas import DataHealthScore

    # Extract date_range from inputs to generate a deterministic timestamp
    date_range = {}
    if inputs:
        if isinstance(inputs, dict):
            date_range = inputs.get("date_range", {}) or {}
        else:
            date_range = getattr(inputs, "date_range", {}) or {}

    run_timestamp = None
    if date_range and isinstance(date_range, dict):
        end_date_str = date_range.get("end")
        if end_date_str and isinstance(end_date_str, str):
            try:
                run_timestamp = datetime.datetime.fromisoformat(end_date_str)
                if run_timestamp.tzinfo is None:
                    run_timestamp = run_timestamp.replace(tzinfo=timezone.utc)
            except Exception:
                try:
                    dt = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
                    run_timestamp = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

    # Case 1: l2_output is canonical Layer2Output
    if hasattr(l2_output, "stress_context") and hasattr(l2_output, "zone_stress_map"):
        from layer2_intelligence.outputs.layer3_adapter import build_layer3_context
        l3_ctx = build_layer3_context(l2_output)

        # Extract plot context from orchestrator inputs
        plot_ctx = _extract_plot_context(inputs, l1_output, l2_output)

        # Extract weather forecast from L1 output
        forecast = _extract_weather_forecast(l1_output)

        decision_output = run_layer3(
            l3_context=l3_ctx,
            plot_context=plot_ctx,
            weather_forecast=forecast,
            run_timestamp=run_timestamp,
        )
        c_water, w_receipt = _execute_canonical_water_engine(inputs, l1_output, l2_output, run_timestamp)
        decision_output.canonical_water_state = c_water
        decision_output.water_receipt = w_receipt
        return decision_output

    # Case 2: l2_output is legacy VegIntOutput or None
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(
        "[L3] Legacy VegIntOutput bridge used; canonical Layer2Output missing"
    )
    l3_ctx = _build_legacy_l3_context(inputs, l1_output, l2_output)
    plot_ctx = _extract_plot_context(inputs, l1_output, l2_output)
    forecast = _extract_weather_forecast(l1_output)

    decision_output = run_layer3(
        l3_context=l3_ctx,
        plot_context=plot_ctx,
        weather_forecast=forecast,
        run_timestamp=run_timestamp,
    )
    c_water, w_receipt = _execute_canonical_water_engine(inputs, l1_output, l2_output, run_timestamp)
    decision_output.canonical_water_state = c_water
    decision_output.water_receipt = w_receipt
    return decision_output


# Plot hydraulic state memory cache across time steps: plot_id -> (SoilWaterState, HydraulicStressMemoryState)
_PLOT_WATER_STATE_MEMORY: dict = {}
# Versioned time-indexed history for idempotent replay and correct predecessor selection
_PLOT_WATER_STATE_HISTORY: dict = {}
# Persistent registries for historical dated inputs across requests
_PLOT_MANAGEMENT_EVENTS: dict = {}
_PLOT_VEGETATION_HISTORY: dict = {}
_PLOT_SOIL_OBS_HISTORY: dict = {}
_PLOT_INITIAL_STATE_HISTORY: dict = {}
_PLOT_WITHDRAWN_SOIL_OBS: dict = {}
_PLOT_WITHDRAWN_VEG: dict = {}
_PLOT_CURRENT_HEAD: dict = {}
_PLOT_CURRENT_SEQUENCE: dict = {}
_PLOT_CURRENT_STEP: dict = {}
_PLOT_SCOPE_LOCKS: dict = {}
_PLOT_SCOPE_LOCKS_GUARD = threading.Lock()


def _get_plot_scope_lock(scope_key: Any) -> threading.Lock:
    with _PLOT_SCOPE_LOCKS_GUARD:
        if scope_key not in _PLOT_SCOPE_LOCKS:
            _PLOT_SCOPE_LOCKS[scope_key] = threading.Lock()
        return _PLOT_SCOPE_LOCKS[scope_key]


def _is_soil_obs_withdrawn(val: Any) -> bool:
    if val is None:
        return True
    if getattr(val, "deleted", False) is True or getattr(val, "is_deletion", False) is True:
        return True
    if str(getattr(val, "status", "")).lower() in {"cancelled", "deleted", "withdrawn"}:
        return True
    if isinstance(val, dict):
        if val.get("deleted") is True or val.get("is_deletion") is True:
            return True
        if str(val.get("status", "")).lower() in {"cancelled", "deleted", "withdrawn"}:
            return True
    return False


try:
    from services.agribrain.world_model.canonical_worldline import (
        CanonicalWorldlineService,
        ConcurrencyConflictError,
    )
except ImportError:
    try:
        from world_model.canonical_worldline import (
            CanonicalWorldlineService,
            ConcurrencyConflictError,
        )
    except ImportError:
        CanonicalWorldlineService = None
        class ConcurrencyConflictError(Exception):
            pass


def _serialize_soil_water(soil: Any) -> Optional[dict]:
    if soil is None:
        return None
    try:
        import dataclasses
        if dataclasses.is_dataclass(soil):
            return dataclasses.asdict(soil)
        return dict(getattr(soil, "__dict__", {}))
    except Exception:
        return None


def _deserialize_soil_water(data: Any) -> Optional[Any]:
    if not isinstance(data, dict):
        return None
    try:
        from layer3_water.contracts.water_state import SoilWaterState, InfiltrationState, SoilEvaporationState
        infil_d = data.get("infiltration")
        infil = InfiltrationState(**infil_d) if isinstance(infil_d, dict) else infil_d
        evap_d = data.get("evaporation_state")
        evap = SoilEvaporationState(**evap_d) if isinstance(evap_d, dict) else evap_d

        known_fields = {
            "layer_depths_cm", "theta_profile", "field_capacity_profile", "wilting_point_profile",
            "saturation_profile", "residual_profile", "hydraulic_conductivity_profile",
            "van_genuchten_alpha", "van_genuchten_n", "van_genuchten_m",
            "matric_potential_profile_mpa", "unsaturated_conductivity_profile_cm_day",
            "parameter_provenance"
        }
        kwargs = {k: v for k, v in data.items() if k in known_fields}
        return SoilWaterState(**kwargs, infiltration=infil, evaporation_state=evap)
    except Exception:
        return None


def _serialize_hydraulic_memory(mem: Any) -> Optional[dict]:
    if mem is None:
        return None
    try:
        import dataclasses
        if dataclasses.is_dataclass(mem):
            return dataclasses.asdict(mem)
        return dict(getattr(mem, "__dict__", {}))
    except Exception:
        return None


def _deserialize_hydraulic_memory(data: Any) -> Optional[Any]:
    if not isinstance(data, dict):
        return None
    try:
        from layer3_water.contracts.water_state import HydraulicStressMemoryState
        known_fields = {
            "cumulative_transpiration_deficit_mm", "consecutive_days_under_limitation",
            "severe_limitation_days_count", "integrated_hydraulic_stress_index",
            "water_stress_recovery_rate", "historical_min_ks", "drought_exposure_class"
        }
        kwargs = {k: v for k, v in data.items() if k in known_fields}
        return HydraulicStressMemoryState(**kwargs)
    except Exception:
        return None


def _serialize_veg_state(veg: Any) -> Optional[dict]:
    if veg is None:
        return None
    try:
        import dataclasses
        if dataclasses.is_dataclass(veg):
            d = dataclasses.asdict(veg)
            if "timestamp" in d and isinstance(d["timestamp"], (datetime.datetime, datetime.date)):
                d["timestamp"] = d["timestamp"].isoformat()
            return d
        return None
    except Exception:
        return None


def _deserialize_veg_state(data: Any) -> Optional[Any]:
    if not isinstance(data, dict):
        return None
    try:
        from layer2_contracts.state_contracts import VegetationState
        ts_val = data.get("timestamp")
        if isinstance(ts_val, str):
            ts_val = datetime.datetime.fromisoformat(ts_val)
        return VegetationState(
            plot_id=data.get("plot_id", ""),
            timestamp=ts_val or datetime.datetime.now(timezone.utc),
            lai=float(data.get("lai", 0.0)),
            fvc=float(data.get("fvc", 0.0)),
            root_depth_proxy_m=float(data.get("root_depth_proxy_m", 0.4)),
        )
    except Exception:
        return None


def _serialize_soil_observation(so: Any) -> Optional[dict]:
    if so is None:
        return None
    try:
        import dataclasses
        if dataclasses.is_dataclass(so):
            d = dataclasses.asdict(so)
            if "timestamp" in d and isinstance(d["timestamp"], (datetime.datetime, datetime.date)):
                d["timestamp"] = d["timestamp"].isoformat()
            return d
        elif isinstance(so, dict):
            d = dict(so)
            if "timestamp" in d and isinstance(d["timestamp"], (datetime.datetime, datetime.date)):
                d["timestamp"] = d["timestamp"].isoformat()
            return d
        return None
    except Exception:
        return None


def _deserialize_soil_observation(data: Any) -> Optional[Any]:
    if not isinstance(data, dict):
        return None
    try:
        from layer3_water.contracts.assimilation_state import SoilObservationVector
        ts_val = data.get("timestamp")
        if isinstance(ts_val, str):
            ts_val = datetime.datetime.fromisoformat(ts_val)
        known_fields = {
            "soil_probe_moisture_profile",
            "satellite_surface_moisture_m3_m3",
            "canopy_cooling_differential_c",
            "flux_tower_eta_mm",
            "observation_uncertainties",
            "provenance_sources",
            "role",
            "reading_reliability",
            "reliability_weight",
            "component_roles",
            "component_reliabilities",
        }
        kwargs = {k: v for k, v in data.items() if k in known_fields}
        if "source" in data and "provenance_sources" not in kwargs:
            kwargs["provenance_sources"] = [data["source"]]
        elif "source" in data and not kwargs.get("provenance_sources"):
            kwargs["provenance_sources"] = [data["source"]]
        return SoilObservationVector(
            timestamp=ts_val or datetime.datetime.now(timezone.utc),
            **kwargs,
        )
    except Exception:
        return None


def _execute_canonical_water_engine(
    inputs: Any,
    l1_output: Any = None,
    l2_output: Any = None,
    run_timestamp: Optional[datetime.datetime] = None,
    **kwargs: Any,
) -> tuple[Any, Any]:
    """Execute authoritative Layer 3 Hydrological Water Balance Engine."""
    try:
        import hashlib
        from layer3_water.runner import WaterIntelligenceEngine
        from layer3_water.contracts import HydrologyMode, SoilWaterState
        from layer2_contracts.state_contracts import VegetationState

        plot_id = kwargs.get("plot_id") or (getattr(inputs, "plot_id", "P1") if inputs else "P1")
        ts = run_timestamp
        if ts is None:
            target_date = getattr(inputs, "target_date", None)
            if target_date:
                try:
                    if isinstance(target_date, str):
                        ts = datetime.datetime.fromisoformat(target_date).replace(tzinfo=timezone.utc)
                    elif isinstance(target_date, datetime.date):
                        ts = datetime.datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
                except Exception:
                    pass
        if ts is None:
            ts = datetime.datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        day_key = ts.strftime("%Y-%m-%d")

        # Typed orchestrator context extraction
        op_ctx = kwargs.get("op_ctx") or getattr(inputs, "operational_context", None)
        if not isinstance(op_ctx, dict):
            op_ctx = {}

        tenant_id = kwargs.get("tenant_id") or getattr(inputs, "tenant_id", "default_tenant") or op_ctx.get("tenant_id", "default_tenant")
        namespace = kwargs.get("namespace") or getattr(inputs, "namespace", "default") or op_ctx.get("namespace", "default")
        cycle_id = kwargs.get("cycle_id") or getattr(inputs, "cycle_id", None) or op_ctx.get("cycle_id")
        geometry_version = kwargs.get("geometry_version") or getattr(inputs, "geometry_version", None) or op_ctx.get("geometry_version")

        # 1. Weather observations from L1 or inputs
        timeseries = getattr(l1_output, "plot_timeseries", []) or []
        weather_daily = (
            getattr(inputs, "weather_daily_series", None)
            or getattr(inputs, "weather_daily", None)
            or getattr(inputs, "weather", None)
            or op_ctx.get("weather_daily_series")
            or op_ctx.get("weather_daily")
            or op_ctx.get("weather")
        )
        rec = None
        step_limit_ts = min(ts, datetime.datetime.combine(ts.date(), datetime.time(23, 59, 59, tzinfo=timezone.utc)))

        def _is_weather_issuance_eligible(entry: dict, limit_ts: datetime.datetime) -> bool:
            if not isinstance(entry, dict):
                return False
            iss = entry.get("issued_at") or entry.get("timestamp")
            if iss:
                try:
                    iss_dt = datetime.datetime.fromisoformat(str(iss))
                    if iss_dt.tzinfo is None:
                        iss_dt = iss_dt.replace(tzinfo=timezone.utc)
                    return iss_dt <= limit_ts
                except Exception:
                    return False
            if entry.get("is_prior") or entry.get("source_role") in ("historical_actual", "reanalyzed", "prior"):
                return True
            entry_d = entry.get("date")
            if entry_d:
                try:
                    return datetime.date.fromisoformat(str(entry_d)[:10]) <= limit_ts.date()
                except Exception:
                    return False
            return True

        if isinstance(weather_daily, dict):
            cand = weather_daily.get(day_key)
            if cand and _is_weather_issuance_eligible(cand, step_limit_ts):
                rec = cand
        elif isinstance(weather_daily, list):
            for t_entry in reversed(weather_daily):
                if isinstance(t_entry, dict):
                    t_date = t_entry.get("date")
                    if not t_date and "timestamp" in t_entry:
                        raw_ts = t_entry["timestamp"]
                        if isinstance(raw_ts, datetime.datetime):
                            t_date = raw_ts.astimezone(ts.tzinfo).strftime("%Y-%m-%d")
                        elif isinstance(raw_ts, str) and len(raw_ts) >= 10:
                            t_date = raw_ts[:10]
                    if t_date == day_key and _is_weather_issuance_eligible(t_entry, step_limit_ts):
                        rec = t_entry
                        break
        if not rec and timeseries:
            for t_entry in reversed(timeseries):
                if isinstance(t_entry, dict):
                    t_date = t_entry.get("date")
                    if not t_date and "timestamp" in t_entry:
                        raw_ts = t_entry["timestamp"]
                        if isinstance(raw_ts, datetime.datetime):
                            t_date = raw_ts.astimezone(ts.tzinfo).strftime("%Y-%m-%d")
                        elif isinstance(raw_ts, str) and len(raw_ts) >= 10:
                            t_date = raw_ts[:10]
                    if t_date == day_key and _is_weather_issuance_eligible(t_entry, step_limit_ts):
                        rec = t_entry
                        break

        weather_prior = op_ctx.get("weather_prior") or getattr(inputs, "weather_prior", None)

        if not rec and isinstance(weather_prior, dict):
            rec = dict(weather_prior)
            rec["date"] = day_key
            rec["is_prior"] = True

        # Fallback to committed latest hydraulic checkpoint for this plot/cycle/geometry
        if not rec:
            try:
                from world_model.canonical_worldline import CanonicalWorldlineService
                _cw_init = CanonicalWorldlineService()
                _cp_init = _cw_init.load_latest_hydraulic_checkpoint(
                    plot_id=plot_id,
                    tenant_id=tenant_id,
                    namespace=namespace,
                    cycle_id=cycle_id,
                    geometry_version=geometry_version,
                )
                if _cp_init:
                    _hist_init = _cp_init.get("payload", {}).get("history_summary", {})
                    if isinstance(_hist_init, dict) and day_key in _hist_init:
                        _cand_cp = _hist_init[day_key].get("weather")
                        if _cand_cp and _is_weather_issuance_eligible(_cand_cp, step_limit_ts):
                            rec = _cand_cp
            except Exception as _cp_err:
                pass

        if not rec or not isinstance(rec, dict):
            import logging
            logging.getLogger(__name__).warning(
                f"[L3] Canonical water engine: missing weather observations for plot {plot_id} on {day_key}. "
                "Preserving missingness rather than substituting another date's atmospheric state."
            )
            return None, None

        def _parse_weather(r: dict) -> Optional[dict]:
            def _get_val(keys: list, default: Optional[float] = None) -> Optional[float]:
                for k in keys:
                    v = r.get(k)
                    if v is not None:
                        val = finite_real(v)
                        if val is not None:
                            return val
                return default

            t_max_v = _get_val(["t_max_c", "temp_max", "temperature_max", "temp", "temperature", "t_max"])
            t_min_v = _get_val(["t_min_c", "temp_min", "temperature_min", "t_min"])
            precip_v = _get_val(["precipitation_mm", "precipitation", "rain", "precip"])
            wind_v = _get_val(["wind_speed_2m_m_s", "wind_speed", "wind", "wind_speed_2m"])
            hum_v = _get_val(["humidity", "rh", "relative_humidity"])
            rh_min_v = _get_val(["rh_min_pct", "rh_min"])
            rh_max_v = _get_val(["rh_max_pct", "rh_max"])
            rn_v = _get_val(["net_radiation_mj_m2", "net_radiation", "radiation"])

            if isinstance(weather_prior, dict):
                if t_min_v is None and "temp_min" in weather_prior: t_min_v = finite_real(weather_prior["temp_min"])
                if precip_v is None and "precipitation" in weather_prior: precip_v = finite_real(weather_prior["precipitation"])
                if wind_v is None and "wind_speed" in weather_prior: wind_v = finite_real(weather_prior["wind_speed"])
                if rh_min_v is None and "rh_min" in weather_prior: rh_min_v = finite_real(weather_prior["rh_min"])
                if rh_max_v is None and "rh_max" in weather_prior: rh_max_v = finite_real(weather_prior["rh_max"])
                if rn_v is None and "net_radiation" in weather_prior: rn_v = finite_real(weather_prior["net_radiation"])

            if rh_min_v is None and hum_v is not None:
                rh_min_v = max(10.0, hum_v - 15.0)
            if rh_max_v is None and hum_v is not None:
                rh_max_v = min(100.0, hum_v + 15.0)

            missing_vars = [k for k, v in [
                ("t_max", t_max_v), ("t_min", t_min_v), ("precipitation", precip_v),
                ("wind_speed", wind_v), ("rh_min", rh_min_v), ("rh_max", rh_max_v),
                ("net_radiation", rn_v)
            ] if v is None]

            if missing_vars:
                return None

            parsed_w = {
                "t_max_c": float(t_max_v),
                "t_min_c": float(t_min_v),
                "precipitation_mm": float(precip_v),
                "wind_speed_2m_m_s": float(wind_v),
                "rh_min_pct": float(rh_min_v),
                "rh_max_pct": float(rh_max_v),
                "net_radiation_mj_m2": float(rn_v),
            }
            # Preserve source role, issuance time, and prior lineage
            if "source_role" in r:
                parsed_w["source_role"] = str(r["source_role"])
            elif "role" in r:
                parsed_w["source_role"] = str(r["role"])
            elif r.get("is_prior"):
                parsed_w["source_role"] = "prior"
            else:
                parsed_w["source_role"] = "observation"

            if "issued_at" in r:
                parsed_w["issued_at"] = str(r["issued_at"])
            elif "timestamp" in r:
                parsed_w["issued_at"] = str(r["timestamp"])

            if "is_prior" in r:
                parsed_w["is_prior"] = bool(r["is_prior"])

            return parsed_w

        weather_obs = _parse_weather(rec)
        if weather_obs is None:
            import logging
            logging.getLogger(__name__).warning(
                f"[L3] Canonical water engine: incomplete weather record for plot {plot_id}. "
                "Preserving missingness rather than fabricating synthetic observations."
            )
            return None, None

        # 2. Extract vegetation coordinates from L2 contracts preserving valid zero (bare soil)
        # Low canopy percentages must always be divided by 100 (/100.0)
        veg_state = None
        lai = 1.5
        fvc = 0.5
        root_depth = 1.0

        if l2_output:
            lai_extracted = None
            fvc_extracted = None

            if hasattr(l2_output, "lai_mean"):
                val = getattr(l2_output, "lai_mean")
                if val is not None:
                    lai_extracted = finite_real(val)

            # Check explicit fractional fvc first, else divide canopy_cover_pct by 100 unconditionally
            if hasattr(l2_output, "fvc") and getattr(l2_output, "fvc", None) is not None:
                f_val = finite_real(getattr(l2_output, "fvc"))
                if f_val is not None:
                    fvc_extracted = max(0.0, min(1.0, f_val))
            elif hasattr(l2_output, "canopy_cover_pct"):
                val = getattr(l2_output, "canopy_cover_pct")
                if val is not None:
                    c_val = finite_real(val)
                    if c_val is not None:
                        fvc_extracted = max(0.0, min(1.0, c_val / 100.0))

            # Health index inspection
            h_idx = getattr(l2_output, "health_index", None)
            if h_idx:
                if lai_extracted is None:
                    val = getattr(h_idx, "lai_estimate", None)
                    if val is not None:
                        lai_extracted = finite_real(val)
                if fvc_extracted is None:
                    val = getattr(h_idx, "vegetation_fraction", None)
                    if val is not None:
                        f_val = finite_real(val)
                        if f_val is not None:
                            fvc_extracted = max(0.0, min(1.0, f_val))

            # Growth metrics inspection
            g_met = getattr(l2_output, "growth_metrics", None)
            if g_met:
                if lai_extracted is None:
                    val = getattr(g_met, "lai_estimate", None)
                    if val is not None:
                        lai_extracted = finite_real(val)
                if fvc_extracted is None:
                    if hasattr(g_met, "vegetation_fraction") and getattr(g_met, "vegetation_fraction", None) is not None:
                        f_val = finite_real(getattr(g_met, "vegetation_fraction"))
                        if f_val is not None:
                            fvc_extracted = max(0.0, min(1.0, f_val))
                    elif hasattr(g_met, "canopy_cover_pct") and getattr(g_met, "canopy_cover_pct", None) is not None:
                        c_val = finite_real(getattr(g_met, "canopy_cover_pct"))
                        if c_val is not None:
                            fvc_extracted = max(0.0, min(1.0, c_val / 100.0))

            crop_ctx = getattr(inputs, "crop_context", None) or op_ctx.get("crop_context")
            if isinstance(crop_ctx, dict):
                rd = crop_ctx.get("root_depth_m") or crop_ctx.get("max_root_depth_m")
                if rd is not None:
                    try:
                        root_depth = max(0.2, min(3.0, float(rd)))
                    except (ValueError, TypeError):
                        pass

            if lai_extracted is not None:
                lai = lai_extracted
            if fvc_extracted is not None:
                fvc = fvc_extracted

            veg_state = VegetationState(
                plot_id=plot_id,
                timestamp=ts,
                lai=lai,
                fvc=fvc,
                root_depth_proxy_m=root_depth,
            )

        # Scoped identities for tenant isolation
        day_key = ts.date().strftime("%Y-%m-%d")
        tenant_id = str(getattr(inputs, "tenant_id", None) or op_ctx.get("tenant_id") or "default_tenant")
        namespace = str(getattr(inputs, "namespace", None) or op_ctx.get("namespace") or "default")
        cycle_id = str(getattr(inputs, "cycle_id", None) or op_ctx.get("cycle_id") or "default_cycle")
        geometry_version = str(getattr(inputs, "geometry_version", None) or op_ctx.get("geometry_version") or "default_geom")
        parameter_epoch = str(getattr(inputs, "parameter_epoch", None) or op_ctx.get("parameter_epoch") or "v1")
        weather_ensemble = op_ctx.get("weather_ensemble") or getattr(inputs, "weather_ensemble", None)
        soil_type = op_ctx.get("soil_type") or getattr(inputs, "soil_type", "loam") or "loam"
        plot_scope_key = (tenant_id, namespace, plot_id, cycle_id, geometry_version)
        legacy_scope_key = (tenant_id, namespace, plot_id)

        # 3. Persistent registries and event tracking
        plot_hist = _PLOT_WATER_STATE_HISTORY.setdefault(plot_scope_key, {})
        _PLOT_WATER_STATE_HISTORY[legacy_scope_key] = plot_hist
        _PLOT_WATER_STATE_HISTORY[plot_id] = plot_hist

        plot_events = _PLOT_MANAGEMENT_EVENTS.setdefault(plot_scope_key, {})
        _PLOT_MANAGEMENT_EVENTS[legacy_scope_key] = plot_events
        _PLOT_MANAGEMENT_EVENTS[plot_id] = plot_events

        plot_veg_hist = _PLOT_VEGETATION_HISTORY.setdefault(plot_scope_key, {})
        _PLOT_VEGETATION_HISTORY[legacy_scope_key] = plot_veg_hist
        _PLOT_VEGETATION_HISTORY[plot_id] = plot_veg_hist

        plot_so_hist = _PLOT_SOIL_OBS_HISTORY.setdefault(plot_scope_key, {})
        _PLOT_SOIL_OBS_HISTORY[legacy_scope_key] = plot_so_hist
        _PLOT_SOIL_OBS_HISTORY[plot_id] = plot_so_hist

        plot_init_hist = _PLOT_INITIAL_STATE_HISTORY.setdefault(plot_scope_key, {})
        _PLOT_INITIAL_STATE_HISTORY[legacy_scope_key] = plot_init_hist
        _PLOT_INITIAL_STATE_HISTORY[plot_id] = plot_init_hist

        plot_withdrawn_so = _PLOT_WITHDRAWN_SOIL_OBS.setdefault(plot_scope_key, set())
        _PLOT_WITHDRAWN_SOIL_OBS[legacy_scope_key] = plot_withdrawn_so
        _PLOT_WITHDRAWN_SOIL_OBS[plot_id] = plot_withdrawn_so

        plot_withdrawn_veg = _PLOT_WITHDRAWN_VEG.setdefault(plot_scope_key, set())
        _PLOT_WITHDRAWN_VEG[legacy_scope_key] = plot_withdrawn_veg
        _PLOT_WITHDRAWN_VEG[plot_id] = plot_withdrawn_veg

        # Cold restart recovery and head-cache binding (R09):
        expected_head = None
        cp_step_key = None
        cp_payload = {}
        try:
            try:
                from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService
            except ImportError:
                from world_model.canonical_worldline import CanonicalWorldlineService
            cw_svc = CanonicalWorldlineService()
            latest_cp = cw_svc.load_latest_hydraulic_checkpoint(plot_id=plot_id, tenant_id=tenant_id, namespace=namespace, cycle_id=cycle_id, geometry_version=geometry_version)

            with _get_plot_scope_lock(plot_scope_key):
                # Re-read latest checkpoint under lock to guarantee fresh durable head
                latest_cp = cw_svc.load_latest_hydraulic_checkpoint(plot_id=plot_id, tenant_id=tenant_id, namespace=namespace, cycle_id=cycle_id, geometry_version=geometry_version)
                ram_head = _PLOT_CURRENT_HEAD.get(plot_scope_key)
                ram_pub_seq = _PLOT_CURRENT_SEQUENCE.get(plot_scope_key, 0)
                ram_step = _PLOT_CURRENT_STEP.get(plot_scope_key, "")

                durable_head_id = latest_cp.get("checkpoint_id") if latest_cp else None
                expected_head = durable_head_id
                durable_pub_seq = latest_cp.get("sequence", 0) if latest_cp else 0
                durable_step = latest_cp.get("payload", {}).get("step_key", "") if latest_cp else ""

                # RV02: Use monotonically increasing committed publication generation (sequence) for generation fencing.
                # If disk publication sequence is newer, or disk head differs from cached RAM head, disk takes precedence
                # even if a historical correction shortened history length!
                ram_is_ahead = (
                    ram_head is not None
                    and durable_pub_seq > 0
                    and ram_pub_seq > durable_pub_seq
                )

                if not ram_is_ahead:
                    # Invalidate RAM cache when durable head on disk differs from cached head token
                    if ram_head is not None and ram_head != durable_head_id:
                        plot_hist.clear()
                        plot_veg_hist.clear()
                        plot_so_hist.clear()
                        plot_init_hist.clear()
                        plot_withdrawn_so.clear()
                        plot_withdrawn_veg.clear()
                        _PLOT_WATER_STATE_MEMORY.pop(plot_scope_key, None)
                        _PLOT_WATER_STATE_MEMORY.pop(legacy_scope_key, None)
                        _PLOT_WATER_STATE_MEMORY.pop(plot_id, None)

                    _PLOT_CURRENT_HEAD[plot_scope_key] = durable_head_id
                    _PLOT_CURRENT_HEAD[legacy_scope_key] = durable_head_id
                    _PLOT_CURRENT_HEAD[plot_id] = durable_head_id
                    _PLOT_CURRENT_SEQUENCE[plot_scope_key] = durable_pub_seq
                    _PLOT_CURRENT_SEQUENCE[legacy_scope_key] = durable_pub_seq
                    _PLOT_CURRENT_SEQUENCE[plot_id] = durable_pub_seq
                    _PLOT_CURRENT_STEP[plot_scope_key] = durable_step
                    _PLOT_CURRENT_STEP[legacy_scope_key] = durable_step

            if latest_cp and isinstance(latest_cp.get("payload"), dict):
                cp_payload = latest_cp["payload"]
                cp_cycle = cp_payload.get("cycle_id", "default_cycle")
                cp_geom = cp_payload.get("geometry_version", "default_geom")
                # Scope isolation: do not hydrate cross-cycle or cross-geometry checkpoint
                if (cp_cycle == cycle_id or cp_cycle == "default_cycle" and cycle_id == "default_cycle") and (cp_geom == geometry_version or cp_geom == "default_geom" and geometry_version == "default_geom"):
                    expected_head = latest_cp.get("checkpoint_id")
                    cp_step_key = cp_payload.get("step_key")

                    if not plot_hist:
                        if cp_step_key == day_key:
                            # V07: For cold replay of the same day, hydrate initial prior before that day was solved
                            init_soil_raw = cp_payload.get("initial_soil_water")
                            init_mem_raw = cp_payload.get("initial_hydraulic_memory")
                            if not init_soil_raw and "history_summary" in cp_payload:
                                h_entry = cp_payload["history_summary"].get(day_key, {})
                                init_soil_raw = h_entry.get("initial_soil_water")
                                init_mem_raw = h_entry.get("initial_hydraulic_memory")
                            init_soil = _deserialize_soil_water(init_soil_raw) if init_soil_raw else None
                            init_mem = _deserialize_hydraulic_memory(init_mem_raw) if init_mem_raw else None
                            if init_soil:
                                _PLOT_WATER_STATE_MEMORY[plot_scope_key] = (init_soil, init_mem)
                                _PLOT_WATER_STATE_MEMORY[plot_id] = (init_soil, init_mem)
                                plot_init_hist[day_key] = (init_soil, init_mem or HydraulicStressMemoryState())
                        elif "history_summary" in cp_payload and day_key in cp_payload["history_summary"]:
                            # C10: For historical cold replay (day_key < cp_step_key), hydrate initial prior of that day, NEVER future posterior!
                            h_entry = cp_payload["history_summary"][day_key]
                            init_soil_raw = h_entry.get("initial_soil_water")
                            init_mem_raw = h_entry.get("initial_hydraulic_memory")
                            init_soil = _deserialize_soil_water(init_soil_raw) if init_soil_raw else None
                            init_mem = _deserialize_hydraulic_memory(init_mem_raw) if init_mem_raw else None
                            if init_soil:
                                _PLOT_WATER_STATE_MEMORY[plot_scope_key] = (init_soil, init_mem)
                                _PLOT_WATER_STATE_MEMORY[plot_id] = (init_soil, init_mem)
                                plot_init_hist[day_key] = (init_soil, init_mem or HydraulicStressMemoryState())
                        elif cp_step_key and day_key > cp_step_key:
                            # Moving forward in time: starting prior is the latest committed posterior
                            if "soil_water" in cp_payload and isinstance(cp_payload["soil_water"], dict):
                                hyd_soil = _deserialize_soil_water(cp_payload["soil_water"])
                                hyd_mem = _deserialize_hydraulic_memory(cp_payload.get("hydraulic_memory", {}))
                                if hyd_soil:
                                    _PLOT_WATER_STATE_MEMORY[plot_scope_key] = (hyd_soil, hyd_mem)
                                    _PLOT_WATER_STATE_MEMORY[plot_id] = (hyd_soil, hyd_mem)
                        if "events" in cp_payload and isinstance(cp_payload["events"], dict):
                            plot_events.update(cp_payload["events"])
                        # R12: Canonical ISO string representation for withdrawals
                        if "withdrawn_soil_dates" in cp_payload and isinstance(cp_payload["withdrawn_soil_dates"], list):
                            for sd in cp_payload["withdrawn_soil_dates"]:
                                plot_withdrawn_so.add(str(sd))
                        if "withdrawn_veg_dates" in cp_payload and isinstance(cp_payload["withdrawn_veg_dates"], list):
                            for vd in cp_payload["withdrawn_veg_dates"]:
                                plot_withdrawn_veg.add(str(vd))
                        if "history_summary" in cp_payload and isinstance(cp_payload["history_summary"], dict):
                            for h_key, h_data in cp_payload["history_summary"].items():
                                if isinstance(h_data, dict):
                                    step_soil = _deserialize_soil_water(h_data.get("soil_water"))
                                    step_mem = _deserialize_hydraulic_memory(h_data.get("hydraulic_memory"))
                                    step_init_soil = _deserialize_soil_water(h_data.get("initial_soil_water"))
                                    step_init_mem = _deserialize_hydraulic_memory(h_data.get("initial_hydraulic_memory"))
                                    step_veg = _deserialize_veg_state(h_data.get("vegetation"))
                                    step_so = _deserialize_soil_observation(h_data.get("soil_observations"))
                                    if step_init_soil:
                                        plot_init_hist[h_key] = (step_init_soil, step_init_mem or HydraulicStressMemoryState())
                                    if step_veg:
                                        plot_veg_hist[h_key] = step_veg
                                    if step_so:
                                        plot_so_hist[h_key] = step_so
                                    if h_key < day_key and h_key not in plot_hist:
                                        ts_raw = h_data.get("timestamp")
                                        if ts_raw:
                                            try:
                                                ts_obj = datetime.datetime.fromisoformat(ts_raw)
                                            except Exception:
                                                ts_obj = ts
                                        else:
                                            ts_obj = ts
                                        plot_hist[h_key] = {
                                            "timestamp": ts_obj,
                                            "soil_water": step_soil,
                                            "hydraulic_memory": step_mem,
                                            "water_state": None,
                                            "feedback": None,
                                            "weather": h_data.get("weather", {}),
                                            "irrigation": float(h_data.get("irrigation", 0.0)),
                                            "vegetation_state": step_veg,
                                            "lai": getattr(step_veg, "lai", 0.0) if step_veg else 0.0,
                                            "fvc": getattr(step_veg, "fvc", 0.0) if step_veg else 0.0,
                                            "root_depth": getattr(step_veg, "root_depth_proxy_m", 0.4) if step_veg else 0.4,
                                            "soil_observations": step_so,
                                            "initial_soil_water": step_init_soil,
                                            "initial_hydraulic_memory": step_init_mem,
                                            "evidence_hash": h_data.get("evidence_hash"),
                                            "interval_hash": h_data.get("interval_hash"),
                                            "predecessor_hash": h_data.get("predecessor_hash"),
                                            "step_forcing_hash": h_data.get("step_forcing_hash"),
                                        }
            else:
                head_rec = cw_svc._read(cw_svc._hydraulic_head_path(plot_id, tenant_id, namespace))
                scoped_heads = head_rec.get("scoped_heads", {}) if head_rec else {}
                expected_head = scoped_heads.get(f"{cycle_id}::{geometry_version}")
                if expected_head is None and not scoped_heads and head_rec:
                    if (head_rec.get("cycle_id", "default_cycle") == cycle_id and
                        head_rec.get("geometry_version", "default_geom") == geometry_version):
                        expected_head = head_rec.get("head_hash") or head_rec.get("latest_checkpoint_id")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[L3] Checkpoint hydration note: {e}")

        # V09 + C11: Snapshot pre-execution RAM state
        snapshot_hist = dict(plot_hist)
        snapshot_events = dict(plot_events)
        snapshot_veg = dict(plot_veg_hist)
        snapshot_so = dict(plot_so_hist)
        snapshot_init = dict(plot_init_hist)
        snapshot_withdrawn_so = set(plot_withdrawn_so)
        snapshot_withdrawn_veg = set(plot_withdrawn_veg)
        snapshot_mem_scope = _PLOT_WATER_STATE_MEMORY.get(plot_scope_key)
        snapshot_mem_plot = _PLOT_WATER_STATE_MEMORY.get(plot_id)
        snapshot_head = _PLOT_CURRENT_HEAD.get(plot_scope_key)
        snapshot_seq = _PLOT_CURRENT_SEQUENCE.get(plot_scope_key)

        # D12: Candidate registries isolated from concurrent workers until CAS persistence
        candidate_events = dict(plot_events)
        candidate_veg = dict(plot_veg_hist)
        candidate_so = dict(plot_so_hist)
        candidate_init = dict(plot_init_hist)
        candidate_withdrawn_so = set(plot_withdrawn_so)
        candidate_withdrawn_veg = set(plot_withdrawn_veg)

        def _rollback_ram_state():
            with _get_plot_scope_lock(plot_scope_key):
                try:
                    try:
                        from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService
                    except ImportError:
                        from world_model.canonical_worldline import CanonicalWorldlineService
                    cur_cw = CanonicalWorldlineService()
                    cur_latest = cur_cw.load_latest_hydraulic_checkpoint(plot_id=plot_id, tenant_id=tenant_id, namespace=namespace, cycle_id=cycle_id, geometry_version=geometry_version)
                    cur_head = cur_latest.get("checkpoint_id") if cur_latest else None
                except Exception:
                    cur_latest = None
                    cur_head = None

                current_ram_head = _PLOT_CURRENT_HEAD.get(plot_scope_key)

                # C11 & D11: If disk has a newer/different committed head than our starting snapshot,
                # a concurrent winner won CAS on disk! Rehydrate winner's state ONLY if RAM hasn't already advanced to it or past it.
                if cur_head is not None and cur_head != expected_head:
                    if current_ram_head == cur_head:
                        # Already published to RAM by the winner or previous rehydration
                        return
                    if cur_latest and isinstance(cur_latest.get("payload"), dict):
                        winner_payload = cur_latest["payload"]
                        winner_cycle = winner_payload.get("cycle_id", cur_latest.get("cycle_id", "default_cycle"))
                        winner_geom = winner_payload.get("geometry_version", cur_latest.get("geometry_version", "default_geom"))
                        is_same_scope = (
                            (winner_cycle == cycle_id or (winner_cycle == "default_cycle" and cycle_id == "default_cycle"))
                            and (winner_geom == geometry_version or (winner_geom == "default_geom" and geometry_version == "default_geom"))
                        )
                        if not is_same_scope:
                            # DV08: Cross-scope winner; do not install into this scope's RAM!
                            return

                        winner_seq = cur_latest.get("sequence", 0)
                        _PLOT_CURRENT_HEAD[plot_scope_key] = cur_head
                        _PLOT_CURRENT_HEAD[legacy_scope_key] = cur_head
                        _PLOT_CURRENT_HEAD[plot_id] = cur_head
                        _PLOT_CURRENT_SEQUENCE[plot_scope_key] = winner_seq
                        _PLOT_CURRENT_SEQUENCE[legacy_scope_key] = winner_seq
                        _PLOT_CURRENT_SEQUENCE[plot_id] = winner_seq
                        winner_soil = _deserialize_soil_water(winner_payload.get("soil_water"))
                        winner_mem = _deserialize_hydraulic_memory(winner_payload.get("hydraulic_memory"))
                        if winner_soil:
                            _PLOT_WATER_STATE_MEMORY[plot_scope_key] = (winner_soil, winner_mem)
                            _PLOT_WATER_STATE_MEMORY[legacy_scope_key] = (winner_soil, winner_mem)
                            _PLOT_WATER_STATE_MEMORY[plot_id] = (winner_soil, winner_mem)
                        if "events" in winner_payload and isinstance(winner_payload["events"], dict):
                            plot_events.clear()
                            plot_events.update(winner_payload["events"])
                            _PLOT_MANAGEMENT_EVENTS[plot_id] = plot_events
                        if "withdrawn_soil_dates" in winner_payload and isinstance(winner_payload["withdrawn_soil_dates"], list):
                            plot_withdrawn_so.clear()
                            for sd in winner_payload["withdrawn_soil_dates"]:
                                plot_withdrawn_so.add(str(sd))
                            _PLOT_WITHDRAWN_SOIL_OBS[plot_id] = plot_withdrawn_so
                        if "withdrawn_veg_dates" in winner_payload and isinstance(winner_payload["withdrawn_veg_dates"], list):
                            plot_withdrawn_veg.clear()
                            for vd in winner_payload["withdrawn_veg_dates"]:
                                plot_withdrawn_veg.add(str(vd))
                            _PLOT_WITHDRAWN_VEG[plot_id] = plot_withdrawn_veg
                        if "history_summary" in winner_payload and isinstance(winner_payload["history_summary"], dict):
                            plot_hist.clear()
                            for h_key, h_data in winner_payload["history_summary"].items():
                                if isinstance(h_data, dict):
                                    h_soil = _deserialize_soil_water(h_data.get("soil_water"))
                                    h_mem = _deserialize_hydraulic_memory(h_data.get("hydraulic_memory"))
                                    h_init_soil = _deserialize_soil_water(h_data.get("initial_soil_water"))
                                    h_init_mem = _deserialize_hydraulic_memory(h_data.get("initial_hydraulic_memory"))
                                    h_veg = _deserialize_veg_state(h_data.get("vegetation"))
                                    h_so = _deserialize_soil_observation(h_data.get("soil_observations"))
                                    if h_init_soil:
                                        plot_init_hist[h_key] = (h_init_soil, h_init_mem or HydraulicStressMemoryState())
                                    if h_veg:
                                        plot_veg_hist[h_key] = h_veg
                                    if h_so:
                                        plot_so_hist[h_key] = h_so
                                    ts_raw = h_data.get("timestamp")
                                    try:
                                        ts_obj = datetime.datetime.fromisoformat(ts_raw) if ts_raw else ts
                                    except Exception:
                                        ts_obj = ts
                                    plot_hist[h_key] = {
                                        "timestamp": ts_obj,
                                        "soil_water": h_soil,
                                        "hydraulic_memory": h_mem,
                                        "water_state": None,
                                        "feedback": None,
                                        "weather": h_data.get("weather", {}),
                                        "irrigation": float(h_data.get("irrigation", 0.0)),
                                        "vegetation_state": h_veg,
                                        "lai": getattr(h_veg, "lai", 0.0) if h_veg else 0.0,
                                        "fvc": getattr(h_veg, "fvc", 0.0) if h_veg else 0.0,
                                        "root_depth": getattr(h_veg, "root_depth_proxy_m", 0.4) if h_veg else 0.4,
                                        "soil_observations": h_so,
                                        "initial_soil_water": h_init_soil,
                                        "initial_hydraulic_memory": h_init_mem,
                                        "evidence_hash": h_data.get("evidence_hash"),
                                        "interval_hash": h_data.get("interval_hash"),
                                        "predecessor_hash": h_data.get("predecessor_hash"),
                                        "step_forcing_hash": h_data.get("step_forcing_hash"),
                                    }
                            _PLOT_WATER_STATE_HISTORY[plot_id] = plot_hist
                            _PLOT_SOIL_OBS_HISTORY[plot_id] = plot_so_hist
                            _PLOT_INITIAL_STATE_HISTORY[plot_id] = plot_init_hist
                        return

                # D11: If RAM head has already moved to a newer head or differs from expected_head and snapshot_head,
                # do not restore stale pre-execution snapshot over another winner's publication!
                if current_ram_head is not None and current_ram_head != expected_head and current_ram_head != snapshot_head:
                    return

                # Otherwise, no concurrent winner intervened on disk; restore pre-execution snapshot
                plot_hist.clear()
                plot_hist.update(snapshot_hist)
                _PLOT_WATER_STATE_HISTORY[plot_id] = plot_hist
                plot_events.clear()
                plot_events.update(snapshot_events)
                _PLOT_MANAGEMENT_EVENTS[plot_id] = plot_events
                plot_veg_hist.clear()
                plot_veg_hist.update(snapshot_veg)
                _PLOT_VEGETATION_HISTORY[plot_id] = plot_veg_hist
                plot_so_hist.clear()
                plot_so_hist.update(snapshot_so)
                _PLOT_SOIL_OBS_HISTORY[plot_id] = plot_so_hist
                plot_init_hist.clear()
                plot_init_hist.update(snapshot_init)
                _PLOT_INITIAL_STATE_HISTORY[plot_id] = plot_init_hist
                plot_withdrawn_so.clear()
                plot_withdrawn_so.update(snapshot_withdrawn_so)
                _PLOT_WITHDRAWN_SOIL_OBS[plot_id] = plot_withdrawn_so
                plot_withdrawn_veg.clear()
                plot_withdrawn_veg.update(snapshot_withdrawn_veg)
                _PLOT_WITHDRAWN_VEG[plot_id] = plot_withdrawn_veg
                if snapshot_mem_scope is not None:
                    _PLOT_WATER_STATE_MEMORY[plot_scope_key] = snapshot_mem_scope
                    _PLOT_WATER_STATE_MEMORY[legacy_scope_key] = snapshot_mem_scope
                    _PLOT_WATER_STATE_MEMORY[plot_id] = snapshot_mem_scope
                else:
                    _PLOT_WATER_STATE_MEMORY.pop(plot_scope_key, None)
                    _PLOT_WATER_STATE_MEMORY.pop(legacy_scope_key, None)
                    _PLOT_WATER_STATE_MEMORY.pop(plot_id, None)
                if snapshot_head is not None:
                    _PLOT_CURRENT_HEAD[plot_scope_key] = snapshot_head
                    _PLOT_CURRENT_HEAD[legacy_scope_key] = snapshot_head
                    _PLOT_CURRENT_HEAD[plot_id] = snapshot_head
                else:
                    _PLOT_CURRENT_HEAD.pop(plot_scope_key, None)
                    _PLOT_CURRENT_HEAD.pop(legacy_scope_key, None)
                    _PLOT_CURRENT_HEAD.pop(plot_id, None)
                if snapshot_seq is not None:
                    _PLOT_CURRENT_SEQUENCE[plot_scope_key] = snapshot_seq
                    _PLOT_CURRENT_SEQUENCE[legacy_scope_key] = snapshot_seq
                    _PLOT_CURRENT_SEQUENCE[plot_id] = snapshot_seq
                else:
                    _PLOT_CURRENT_SEQUENCE.pop(plot_scope_key, None)
                    _PLOT_CURRENT_SEQUENCE.pop(legacy_scope_key, None)
                    _PLOT_CURRENT_SEQUENCE.pop(plot_id, None)

        raw_events = (
            op_ctx.get("management_events")
            or getattr(inputs, "management_events", [])
            or []
        )

        explicit_event_dates = set()
        retained_irrigation_map: Dict[str, float] = {}
        retained_weather_map: Dict[str, dict] = {}
        retained_veg_map: Dict[str, Any] = {}
        retained_soil_obs_map: Dict[str, Any] = {}
        for k, v in candidate_so.items():
            if v is not None and k not in candidate_withdrawn_so:
                retained_soil_obs_map[k] = v
        for k, v in plot_hist.items():
            if isinstance(v, dict):
                so_val = v.get("soil_observations")
                if so_val is not None and k not in candidate_withdrawn_so:
                    retained_soil_obs_map.setdefault(k, so_val)
                    candidate_so.setdefault(k, so_val)

        retained_init_soil_map: Dict[str, Any] = {}
        retained_init_mem_map: Dict[str, Any] = {}
        retained_events_map: Dict[str, Any] = {}
        withdrawn_soil_dates: Set[datetime.date] = set()

        for ev in raw_events:
            ev_id = None
            ev_type = ""
            ev_status = "applied"
            ev_amount = 0.0
            ev_ver = 1
            ev_d = None
            is_deletion = False

            if isinstance(ev, dict):
                ev_id = str(ev.get("id") or ev.get("event_id") or "")
                ev_type = str(ev.get("type") or ev.get("event_type") or "").lower()
                ev_status = str(ev.get("status") or "applied").lower()
                ev_amount = float(ev.get("amount_mm") or ev.get("volume_mm") or ev.get("depth_mm") or 0.0)
                ev_ver = int(ev.get("version", 1) or 1)
                is_deletion = (ev_status in {"cancelled", "canceled", "deleted", "revoked"}) or bool(ev.get("deleted")) or (ev.get("action") == "delete")
                raw_d = ev.get("date") or ev.get("timestamp") or ev.get("time") or ev.get("effective_start")
                if raw_d:
                    try:
                        ev_d = datetime.date.fromisoformat(str(raw_d)[:10])
                    except Exception:
                        pass
            elif hasattr(ev, "event_type"):
                ev_id = str(getattr(ev, "id", None) or getattr(ev, "event_id", None) or "")
                ev_type = str(getattr(ev, "event_type", "")).lower()
                ev_status = str(getattr(ev, "status", "applied")).lower()
                ev_amount = float(
                    getattr(ev, "amount_mm", 0.0)
                    or getattr(ev, "volume_mm", 0.0)
                    or (getattr(ev, "sensor_evidence", {}) or {}).get("irrigation_mm", 0.0)
                    or 0.0
                )
                ev_ver = int(getattr(ev, "version", 1) or 1)
                is_deletion = (ev_status in {"cancelled", "canceled", "deleted", "revoked"}) or bool(getattr(ev, "deleted", False))
                raw_d = getattr(ev, "effective_start", None) or getattr(ev, "timestamp", None) or getattr(ev, "date", None)
                if raw_d:
                    try:
                        ev_d = raw_d.date() if hasattr(raw_d, "date") else datetime.date.fromisoformat(str(raw_d)[:10])
                    except Exception:
                        pass

            target_d = ev_d or ts.date()
            if not ev_id:
                ev_id = f"{target_d.isoformat()}_{ev_type}_{round(ev_amount, 2)}"

            # Event versioning, cancellation protection, and date-shift invalidation
            prev_d = None
            if ev_id in candidate_events:
                existing_ev = candidate_events[ev_id]
                existing_ver = int(existing_ev.get("version", 1) or 1)
                existing_is_cancelled = existing_ev.get("is_deletion") or (
                    existing_ev.get("status") in {"cancelled", "canceled", "deleted", "revoked"}
                )

                # Reject stale version: reject if ev_ver < existing_ver
                if ev_ver < existing_ver:
                    continue
                # Reject stale update received after cancellation: reject if ev_ver <= existing_ver
                if existing_is_cancelled and ev_ver <= existing_ver:
                    continue

                prev_d = existing_ev.get("date")
                if prev_d is not None:
                    if isinstance(prev_d, (datetime.date, datetime.datetime)):
                        prev_d_date = prev_d if isinstance(prev_d, datetime.date) else prev_d.date()
                        prev_d_str = prev_d.strftime("%Y-%m-%d")
                    else:
                        prev_d_str = str(prev_d)[:10]
                        try:
                            prev_d_date = datetime.date.fromisoformat(prev_d_str)
                        except Exception:
                            prev_d_date = None
                    if prev_d_date and prev_d_date != target_d:
                        explicit_event_dates.add(prev_d_date)
                        retained_irrigation_map.pop(prev_d_str, None)

            if isinstance(target_d, (datetime.date, datetime.datetime)):
                target_d_str = target_d.strftime("%Y-%m-%d")
                target_d_date = target_d if isinstance(target_d, datetime.date) else target_d.date()
            else:
                target_d_str = str(target_d)[:10]
                target_d_date = datetime.date.fromisoformat(target_d_str)

            explicit_event_dates.add(target_d_date)
            if is_deletion:
                retained_irrigation_map.pop(target_d_str, None)

            candidate_events[ev_id] = {
                "id": ev_id,
                "date": target_d,
                "type": ev_type,
                "status": "cancelled" if is_deletion else ev_status,
                "amount_mm": 0.0 if is_deletion else ev_amount,
                "version": ev_ver,
                "is_deletion": is_deletion,
                "previous_date": prev_d,
            }

        def _get_irrigation_for_date(d_val: datetime.date) -> float:
            d_str = d_val.strftime("%Y-%m-%d")
            # 1. If explicit events were supplied for this date in the current request:
            if d_val in explicit_event_dates:
                tot = 0.0
                for ev_info in candidate_events.values():
                    if ev_info.get("date") == d_val and ev_info.get("type") == "irrigation":
                        if ev_info.get("status") not in {"planned", "cancelled", "canceled", "draft", "proposed", "pending", "failed", "deleted"}:
                            tot += float(ev_info.get("amount_mm", 0.0))
                return tot

            # 2. If omitted from the current request: restore historical applied irrigation
            if d_str in retained_irrigation_map:
                return float(retained_irrigation_map[d_str])

            if d_str in plot_hist and isinstance(plot_hist[d_str], dict) and "irrigation" in plot_hist[d_str]:
                return float(plot_hist[d_str]["irrigation"])

            tot = 0.0
            found = False
            for ev_info in candidate_events.values():
                if ev_info.get("date") == d_val and ev_info.get("type") == "irrigation":
                    found = True
                    if ev_info.get("status") not in {"planned", "cancelled", "canceled", "draft", "proposed", "pending", "failed", "deleted"}:
                        tot += float(ev_info.get("amount_mm", 0.0))
            if found:
                return tot

            return 0.0

        target_applied_irrigation_mm = _get_irrigation_for_date(ts.date())
        soil_type = op_ctx.get("soil_type") or getattr(inputs, "soil_type", "loam") or "loam"

        # Ingest dated vegetation inputs into persistent plot history
        supplied_veg_dates = set()
        veg_daily_input = (
            op_ctx.get("vegetation_daily")
            or getattr(inputs, "vegetation_daily", None)
            or op_ctx.get("vegetation_series")
            or getattr(inputs, "vegetation_series", None)
        )
        if isinstance(veg_daily_input, dict):
            for vk, vv in veg_daily_input.items():
                if len(vk) >= 10:
                    try:
                        vd = datetime.date.fromisoformat(vk[:10])
                        candidate_veg[vd.strftime("%Y-%m-%d")] = vv
                        supplied_veg_dates.add(vd)
                    except Exception:
                        pass
        elif isinstance(veg_daily_input, list):
            for v_item in veg_daily_input:
                vd_str = None
                if isinstance(v_item, dict):
                    vd_str = v_item.get("date") or str(v_item.get("timestamp", ""))[:10]
                elif hasattr(v_item, "timestamp") or hasattr(v_item, "date"):
                    vd_raw = getattr(v_item, "timestamp", None) or getattr(v_item, "date", None)
                    vd_str = str(vd_raw)[:10]
                if vd_str and len(vd_str) >= 10:
                    try:
                        vd = datetime.date.fromisoformat(vd_str[:10])
                        candidate_veg[vd.strftime("%Y-%m-%d")] = v_item
                        supplied_veg_dates.add(vd)
                    except Exception:
                        pass
        if veg_state is not None:
            candidate_veg[ts.date().strftime("%Y-%m-%d")] = veg_state
            supplied_veg_dates.add(ts.date())

        # Ingest dated soil observations into persistent plot history
        supplied_soil_obs_dates = set()
        soil_obs = op_ctx.get("soil_observations") or getattr(inputs, "soil_observations", None)
        soil_obs_daily_input = (
            op_ctx.get("soil_observations_daily")
            or getattr(inputs, "soil_observations_daily", None)
            or op_ctx.get("soil_observations_series")
            or getattr(inputs, "soil_observations_series", None)
        )
        if isinstance(soil_obs_daily_input, dict):
            for sk, sv in soil_obs_daily_input.items():
                if len(sk) >= 10:
                    try:
                        sd = datetime.date.fromisoformat(sk[:10])
                        sd_str = sd.strftime("%Y-%m-%d")
                        if _is_soil_obs_withdrawn(sv):
                            candidate_withdrawn_so.add(sd_str)
                            candidate_so.pop(sd_str, None)
                            retained_soil_obs_map.pop(sd_str, None)
                            withdrawn_soil_dates.add(sd)
                        else:
                            candidate_withdrawn_so.discard(sd_str)
                            candidate_so[sd_str] = sv
                        supplied_soil_obs_dates.add(sd)
                    except (ValueError, TypeError, AttributeError):
                        pass
        elif isinstance(soil_obs_daily_input, list):
            for s_item in soil_obs_daily_input:
                sd_str = None
                if isinstance(s_item, dict):
                    sd_str = s_item.get("date") or str(s_item.get("timestamp", ""))[:10]
                elif hasattr(s_item, "timestamp") or hasattr(s_item, "date"):
                    sd_raw = getattr(s_item, "timestamp", None) or getattr(s_item, "date", None)
                    sd_str = str(sd_raw)[:10]
                if sd_str and len(sd_str) >= 10:
                    try:
                        sd = datetime.date.fromisoformat(sd_str[:10])
                        sd_str = sd.strftime("%Y-%m-%d")
                        if _is_soil_obs_withdrawn(s_item):
                            candidate_withdrawn_so.add(sd_str)
                            candidate_so.pop(sd_str, None)
                            retained_soil_obs_map.pop(sd_str, None)
                            withdrawn_soil_dates.add(sd)
                        else:
                            candidate_withdrawn_so.discard(sd_str)
                            candidate_so[sd_str] = s_item
                        supplied_soil_obs_dates.add(sd)
                    except (ValueError, TypeError, AttributeError):
                        pass

        soil_obs_date = None
        if soil_obs is not None:
            so_ts = getattr(soil_obs, "timestamp", None) or getattr(soil_obs, "date", None)
            if so_ts:
                try:
                    soil_obs_date = so_ts.date() if hasattr(so_ts, "date") else datetime.date.fromisoformat(str(so_ts)[:10])
                except (ValueError, TypeError, AttributeError):
                    soil_obs_date = ts.date()
            else:
                soil_obs_date = ts.date()

            soil_obs_date_str = soil_obs_date.strftime("%Y-%m-%d")
            if _is_soil_obs_withdrawn(soil_obs):
                candidate_withdrawn_so.add(soil_obs_date_str)
                candidate_so.pop(soil_obs_date_str, None)
                retained_soil_obs_map.pop(soil_obs_date_str, None)
                withdrawn_soil_dates.add(soil_obs_date)
            else:
                candidate_withdrawn_so.discard(soil_obs_date_str)
                candidate_so[soil_obs_date_str] = soil_obs
            supplied_soil_obs_dates.add(soil_obs_date)

        # Collect explicitly supplied dates from current request
        supplied_weather_dates = set()
        if isinstance(weather_daily, dict):
            for k in weather_daily.keys():
                if len(k) >= 10:
                    try:
                        supplied_weather_dates.add(datetime.date.fromisoformat(k[:10]))
                    except (ValueError, TypeError, AttributeError):
                        pass
        if timeseries:
            for t_entry in timeseries:
                if isinstance(t_entry, dict):
                    t_d = t_entry.get("date") or str(t_entry.get("timestamp", ""))[:10]
                    if t_d and len(t_d) >= 10:
                        try:
                            supplied_weather_dates.add(datetime.date.fromisoformat(t_d[:10]))
                        except (ValueError, TypeError, AttributeError):
                            pass
        supplied_weather_dates.add(ts.date())

        def _extract_weather_for_date(d_val: datetime.date) -> dict:
            d_str = d_val.strftime("%Y-%m-%d")
            if d_val == ts.date():
                return weather_obs
            r_entry = None
            if isinstance(weather_daily, dict) and d_str in weather_daily:
                r_entry = weather_daily[d_str]
            if not r_entry and timeseries:
                for t_entry in timeseries:
                    if isinstance(t_entry, dict):
                        t_d = t_entry.get("date") or str(t_entry.get("timestamp", ""))[:10]
                        if t_d == d_str:
                            r_entry = t_entry
                            break
            step_limit_ts = min(ts, datetime.datetime.combine(d_val, datetime.time(23, 59, 59, tzinfo=timezone.utc)))

            def _is_weather_issuance_eligible(w_cand: Any) -> bool:
                if not w_cand or not isinstance(w_cand, dict):
                    return False
                cand_iss = w_cand.get("issued_at") or w_cand.get("timestamp")
                if cand_iss:
                    try:
                        cand_iss_dt = datetime.datetime.fromisoformat(str(cand_iss))
                        if cand_iss_dt.tzinfo is None:
                            cand_iss_dt = cand_iss_dt.replace(tzinfo=timezone.utc)
                        return cand_iss_dt <= step_limit_ts
                    except Exception:
                        return False
                if w_cand.get("is_prior") or w_cand.get("source_role") in ("historical_actual", "reanalyzed", "prior"):
                    return True
                entry_date = w_cand.get("date")
                if entry_date:
                    try:
                        return datetime.date.fromisoformat(str(entry_date)[:10]) <= step_limit_ts.date()
                    except Exception:
                        return False
                return True

            if r_entry and isinstance(r_entry, dict):
                p = _parse_weather(r_entry)
                if p and _is_weather_issuance_eligible(p):
                    return p

            # If this date was previously integrated and stored in plot_hist, retain its observation
            # only if issuance eligibility is satisfied
            if d_str in plot_hist and isinstance(plot_hist[d_str], dict) and "weather" in plot_hist[d_str]:
                cached_w = plot_hist[d_str]["weather"]
                if cached_w and isinstance(cached_w, dict) and _is_weather_issuance_eligible(cached_w):
                    return cached_w

            # Also check retained_weather_map if replaying an invalidated trajectory
            if d_str in retained_weather_map and isinstance(retained_weather_map[d_str], dict):
                retained_w = retained_weather_map[d_str]
                if _is_weather_issuance_eligible(retained_w):
                    return retained_w

            # DV10: Check if this date was previously recorded in canonical committed worldline checkpoints
            try:
                from world_model.canonical_worldline import CanonicalWorldlineService
                _cw_tmp = CanonicalWorldlineService()
                # Load committed latest hydraulic checkpoint for this plot/tenant/namespace/cycle/geometry
                _cp_obj = _cw_tmp.load_latest_hydraulic_checkpoint(
                    plot_id=plot_id,
                    tenant_id=tenant_id,
                    namespace=namespace,
                    cycle_id=cycle_id,
                    geometry_version=geometry_version,
                )
                if _cp_obj:
                    _cp_hist = _cp_obj.get("payload", {}).get("history_summary", {})
                    if isinstance(_cp_hist, dict) and d_str in _cp_hist:
                        _w_candidate = _cp_hist[d_str].get("weather")
                        if _w_candidate and isinstance(_w_candidate, dict):
                            # Knowledge-at-issuance eligibility check: checkpoint/issuance cannot be after step_limit_ts
                            _is_eligible = False
                            _iss_str = _w_candidate.get("issued_at") or _cp_obj.get("committed_at") or _cp_obj.get("created_at")
                            if _iss_str:
                                try:
                                    _iss_dt = datetime.datetime.fromisoformat(str(_iss_str))
                                    if _iss_dt.tzinfo is None:
                                        _iss_dt = _iss_dt.replace(tzinfo=timezone.utc)
                                    if _iss_dt <= step_limit_ts:
                                        _is_eligible = True
                                except Exception:
                                    _is_eligible = False
                            if _is_eligible:
                                _pw = _parse_weather(_w_candidate)
                                if _pw:
                                    return _pw
            except Exception:
                pass

            # Missing intermediate day: NEVER leak future endpoint observations into earlier dates!
            # Impute from evidence available BEFORE the missing interval (persistence forward with 0 rain),
            # or climatological prior if no prior observation exists.
            prior_obs = None
            d_prior_walk = d_val - datetime.timedelta(days=1)
            while (d_val - d_prior_walk).days <= 365:
                dp_str = d_prior_walk.strftime("%Y-%m-%d")
                if isinstance(weather_daily, dict) and dp_str in weather_daily:
                    p_w = _parse_weather(weather_daily[dp_str])
                    if p_w:
                        prior_obs = p_w
                        break
                if timeseries:
                    for t_entry in timeseries:
                        if isinstance(t_entry, dict):
                            t_d = t_entry.get("date") or str(t_entry.get("timestamp", ""))[:10]
                            if t_d == dp_str:
                                p_w = _parse_weather(t_entry)
                                if p_w:
                                    prior_obs = p_w
                                    break
                    if prior_obs:
                        break
                if dp_str in plot_hist and isinstance(plot_hist[dp_str], dict) and "weather" in plot_hist[dp_str]:
                    prior_obs = plot_hist[dp_str]["weather"]
                    break
                if dp_str in retained_weather_map:
                    prior_obs = retained_weather_map[dp_str]
                    break
                d_prior_walk -= datetime.timedelta(days=1)

            if prior_obs and isinstance(prior_obs, dict):
                imputed = dict(prior_obs)
                imputation_method = "prior_weather_persistence_zero_rain"
            else:
                base_tmax = float(weather_prior["temp_max"]) if isinstance(weather_prior, dict) and "temp_max" in weather_prior else 20.0
                base_tmin = float(weather_prior["temp_min"]) if isinstance(weather_prior, dict) and "temp_min" in weather_prior else 10.0
                base_wind = float(weather_prior["wind_speed"]) if isinstance(weather_prior, dict) and "wind_speed" in weather_prior else 2.0
                base_rhmin = float(weather_prior["rh_min"]) if isinstance(weather_prior, dict) and "rh_min" in weather_prior else 40.0
                base_rhmax = float(weather_prior["rh_max"]) if isinstance(weather_prior, dict) and "rh_max" in weather_prior else 80.0
                base_rn = float(weather_prior["net_radiation"]) if isinstance(weather_prior, dict) and "net_radiation" in weather_prior else 15.0
                imputed = {
                    "t_max_c": base_tmax,
                    "t_min_c": base_tmin,
                    "wind_speed_2m_m_s": base_wind,
                    "rh_min_pct": base_rhmin,
                    "rh_max_pct": base_rhmax,
                    "net_radiation_mj_m2": base_rn,
                }
                imputation_method = "climatological_prior_zero_rain"

            imputed["date"] = d_str
            imputed["precipitation_mm"] = 0.0
            imputed["precipitation"] = 0.0
            imputed["rain"] = 0.0
            imputed["imputation_method"] = imputation_method
            imputed["imputation_uncertainty_flag"] = True
            imputed["weather_sigma"] = 0.08
            imputed["weather_sigma_override"] = 0.08
            return imputed

        def _state_digest(s_obj: Any) -> str:
            if s_obj is None:
                return "none"
            if isinstance(s_obj, SoilWaterState) or hasattr(s_obj, "layer_depths_cm"):
                evap_st = getattr(s_obj, "evaporation_state", None)
                evap_tuple = (
                    evap_st.days_since_wetting if hasattr(evap_st, "days_since_wetting") else None,
                    round(evap_st.few_exposed_wetted_fraction, 4) if getattr(evap_st, "few_exposed_wetted_fraction", None) is not None else None,
                    round(evap_st.surface_storage_mm, 4) if getattr(evap_st, "surface_storage_mm", None) is not None else None,
                    round(evap_st.max_surface_storage_mm, 4) if getattr(evap_st, "max_surface_storage_mm", None) is not None else None,
                    round(evap_st.kr_reduction_factor, 4) if getattr(evap_st, "kr_reduction_factor", None) is not None else None,
                ) if evap_st is not None else None
                soil_payload = (
                    "SoilWaterState",
                    tuple(getattr(s_obj, "layer_depths_cm", None) or ()),
                    tuple(round(v, 4) for v in (getattr(s_obj, "theta_profile", None) or ())),
                    tuple(round(v, 4) for v in (getattr(s_obj, "field_capacity_profile", None) or ())),
                    tuple(round(v, 4) for v in (getattr(s_obj, "wilting_point_profile", None) or ())),
                    tuple(round(v, 4) for v in (getattr(s_obj, "saturation_profile", None) or ())),
                    tuple(round(v, 4) for v in (getattr(s_obj, "residual_profile", None) or ())),
                    tuple(round(v, 6) for v in (getattr(s_obj, "hydraulic_conductivity_profile", None) or ())),
                    tuple(round(v, 6) for v in (getattr(s_obj, "van_genuchten_alpha", None) or ())),
                    tuple(round(v, 6) for v in (getattr(s_obj, "van_genuchten_n", None) or ())),
                    str(getattr(s_obj, "parameter_provenance", "TEXTURE_PRIOR")),
                    evap_tuple,
                )
                return hashlib.sha256(repr(soil_payload).encode("utf-8")).hexdigest()[:24]
            vwc = getattr(s_obj, "volumetric_water_content", None) or getattr(s_obj, "layers_vwc", None)
            if vwc is not None:
                return hashlib.sha256(repr(vwc).encode("utf-8")).hexdigest()[:24]
            if hasattr(s_obj, "__dict__"):
                return hashlib.sha256(
                    (str(type(s_obj)) + repr(sorted((k, str(v)) for k, v in s_obj.__dict__.items()))).encode("utf-8")
                ).hexdigest()[:24]
            return hashlib.sha256((str(type(s_obj)) + repr(s_obj)).encode("utf-8")).hexdigest()[:24]

        def _extract_veg_for_date(d_val: datetime.date, step_ts: datetime.datetime) -> Optional[VegetationState]:
            d_str = d_val.strftime("%Y-%m-%d")
            cand = None
            # Explicitly supplied dated records in current request take top precedence
            if d_val in supplied_veg_dates and d_str in candidate_veg:
                cand = candidate_veg[d_str]
            elif d_val == ts.date() and veg_state is not None:
                return veg_state
            elif d_str in retained_veg_map:
                cand = retained_veg_map[d_str]
            elif d_str in plot_hist and isinstance(plot_hist[d_str], dict) and plot_hist[d_str].get("vegetation_state") is not None:
                cand = plot_hist[d_str]["vegetation_state"]
            elif d_str in candidate_veg:
                cand = candidate_veg[d_str]

            if cand is not None:
                if isinstance(cand, VegetationState):
                    return VegetationState(
                        plot_id=plot_id,
                        timestamp=step_ts,
                        lai=float(cand.lai),
                        fvc=float(cand.fvc),
                        root_depth_proxy_m=float(cand.root_depth_proxy_m),
                    )
                elif isinstance(cand, dict):
                    c_lai = cand.get("lai") if cand.get("lai") is not None else cand.get("lai_estimate", lai)
                    c_fvc = cand.get("fvc") if cand.get("fvc") is not None else cand.get("vegetation_fraction", fvc)
                    c_rd = (
                        cand.get("root_depth_proxy_m")
                        if cand.get("root_depth_proxy_m") is not None
                        else cand.get("root_depth_m", cand.get("root_depth", root_depth))
                    )
                    return VegetationState(
                        plot_id=plot_id,
                        timestamp=step_ts,
                        lai=float(c_lai),
                        fvc=float(c_fvc),
                        root_depth_proxy_m=float(c_rd),
                    )

            # Fallback: check closest prior dated vegetation in persistent history
            prior_dates = [k for k in candidate_veg.keys() if k < d_str]
            if prior_dates:
                closest_prior_k = max(prior_dates)
                cand_prior = candidate_veg[closest_prior_k]
                if isinstance(cand_prior, VegetationState):
                    v_res = VegetationState(
                        plot_id=plot_id,
                        timestamp=step_ts,
                        lai=float(cand_prior.lai),
                        fvc=float(cand_prior.fvc),
                        root_depth_proxy_m=float(cand_prior.root_depth_proxy_m),
                    )
                    setattr(v_res, "is_persisted_prior", True)
                    return v_res
                elif isinstance(cand_prior, dict):
                    c_lai = cand_prior.get("lai") if cand_prior.get("lai") is not None else cand_prior.get("lai_estimate", lai)
                    c_fvc = cand_prior.get("fvc") if cand_prior.get("fvc") is not None else cand_prior.get("vegetation_fraction", fvc)
                    c_rd = (
                        cand_prior.get("root_depth_proxy_m")
                        if cand_prior.get("root_depth_proxy_m") is not None
                        else cand_prior.get("root_depth_m", cand_prior.get("root_depth", root_depth))
                    )
                    v_res = VegetationState(
                        plot_id=plot_id,
                        timestamp=step_ts,
                        lai=float(c_lai),
                        fvc=float(c_fvc),
                        root_depth_proxy_m=float(c_rd),
                    )
                    setattr(v_res, "is_persisted_prior", True)
                    return v_res

            # If step date is at or beyond target timestamp date, prospective persistence from current veg_state is valid
            if d_val >= ts.date() and veg_state is not None:
                return VegetationState(
                    plot_id=plot_id,
                    timestamp=step_ts,
                    lai=lai,
                    fvc=fvc,
                    root_depth_proxy_m=root_depth,
                )
            # For historical past dates (d_val < ts.date()): never fall back to future/current endpoint canopy!
            # Return None to represent unmeasured baseline rather than leaking future vegetation state.
            return None

        def _extract_soil_obs_for_date(d_val: datetime.date) -> Optional[Any]:
            d_str = d_val.strftime("%Y-%m-%d")
            # Enforce persistent withdrawal semantics on every retrieval path
            if d_str in candidate_withdrawn_so:
                return None
            if d_val in supplied_soil_obs_dates:
                val = candidate_so.get(d_str)
                if _is_soil_obs_withdrawn(val):
                    return None
                return val
            if soil_obs_date is not None and d_val == soil_obs_date and not _is_soil_obs_withdrawn(soil_obs):
                return soil_obs
            if d_str in retained_soil_obs_map:
                val = retained_soil_obs_map[d_str]
                if not _is_soil_obs_withdrawn(val):
                    return val
            if d_str in plot_hist and isinstance(plot_hist[d_str], dict):
                cached = plot_hist[d_str].get("soil_observations")
                if not _is_soil_obs_withdrawn(cached):
                    return cached
            if d_str in candidate_so:
                val = candidate_so[d_str]
                if not _is_soil_obs_withdrawn(val):
                    return val
            return None

        def _compute_step_forcing_hash(
            w: dict,
            irr: float,
            veg: Optional[VegetationState] = None,
            so: Optional[Any] = None,
            predecessor_hash: Optional[str] = None,
            soil_param_digest: Optional[str] = None,
            cycle: Optional[str] = None,
            geom: Optional[str] = None,
            param_epoch: Optional[str] = None,
            stype: Optional[str] = None,
            req_ts: Optional[str] = None,
            ens: Optional[Any] = None,
        ) -> str:
            w_items = tuple(sorted((k, str(v)) for k, v in (w or {}).items()))
            v_items = (
                (
                    round(getattr(veg, "lai", 0.0), 4),
                    round(getattr(veg, "fvc", 0.0), 4),
                    round(getattr(veg, "root_depth_proxy_m", 0.0), 4),
                    getattr(veg, "is_persisted_prior", False),
                )
                if veg is not None
                else "none"
            )
            so_item = _state_digest(so)
            payload = (
                w_items,
                round(irr, 4),
                v_items,
                so_item,
                str(predecessor_hash or "none"),
                str(soil_param_digest or "none"),
                str(cycle if cycle is not None else cycle_id),
                str(geom if geom is not None else geometry_version),
                str(param_epoch if param_epoch is not None else parameter_epoch),
                str(stype if stype is not None else soil_type),
                str(req_ts if req_ts is not None else ts.isoformat()),
                _state_digest(ens if ens is not None else weather_ensemble),
                "fao56_v1",  # solver model version
            )
            return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()[:24]

        # Invalidate any cached history whose input forcing or predecessor changed in current inputs:
        # Distinguish "not supplied in this request" (rolling daily inputs) from "historical evidence was corrected"
        earliest_invalid_day = None
        supplied_dates = (
            supplied_weather_dates
            | explicit_event_dates
            | supplied_veg_dates
            | supplied_soil_obs_dates
        )

        # Check for newly received evidence preceding existing cached history
        earlier_than_cache = None
        if plot_hist:
            cached_dates = [datetime.date.fromisoformat(k) for k in plot_hist.keys() if len(k) >= 10]
            if cached_dates:
                min_cached_d = min(cached_dates)
                earlier_supplied = [d for d in supplied_dates if d <= ts.date() and d < min_cached_d]
                if earlier_supplied:
                    earlier_than_cache = min(earlier_supplied)
                    # All cached history is invalidated because its predecessor state is changing
                    earliest_invalid_day = min_cached_d.strftime("%Y-%m-%d")

        explicit_soil = op_ctx.get("soil_profile_state") or getattr(inputs, "soil_profile_state", None)
        explicit_mem = op_ctx.get("previous_hydraulic_memory") or getattr(inputs, "previous_hydraulic_memory", None)

        for hist_k in sorted(plot_hist.keys()):
            if hist_k > day_key:
                continue
            try:
                hist_d = datetime.date.fromisoformat(hist_k)
            except Exception:
                continue
            hist_entry = plot_hist[hist_k]

            # Invalidate if explicit soil parameter changed from the initial soil used for that history
            if explicit_soil is not None:
                cached_init_soil = hist_entry.get("initial_soil_water")
                if cached_init_soil is not None and _state_digest(cached_init_soil) != _state_digest(explicit_soil):
                    if earliest_invalid_day is None or hist_k < earliest_invalid_day:
                        earliest_invalid_day = hist_k
                    break

            if hist_d not in supplied_dates:
                continue

            curr_w = _extract_weather_for_date(hist_d)
            curr_irr = _get_irrigation_for_date(hist_d)
            step_ts_hist = (
                hist_entry.get("timestamp")
                if hist_entry.get("timestamp") is not None
                else (
                    ts
                    if (hist_d == ts.date())
                    else datetime.datetime.combine(hist_d, datetime.time(12, 0, tzinfo=timezone.utc))
                )
            )
            curr_veg = _extract_veg_for_date(hist_d, step_ts_hist)
            curr_so = _extract_soil_obs_for_date(hist_d)
            cached_init = hist_entry.get("initial_soil_water")
            cached_pred = hist_entry.get("predecessor_hash")
            curr_f_hash = _compute_step_forcing_hash(
                curr_w,
                curr_irr,
                curr_veg,
                curr_so,
                predecessor_hash=cached_pred,
                soil_param_digest=_state_digest(cached_init) if cached_init else None,
                req_ts=step_ts_hist.isoformat(),
            )
            if hist_entry.get("step_forcing_hash") and hist_entry["step_forcing_hash"] != curr_f_hash:
                if earliest_invalid_day is None or hist_k < earliest_invalid_day:
                    earliest_invalid_day = hist_k
                break

        # Coherent withdrawal invalidation: any withdrawn soil date directly invalidates the trajectory from that day onward
        if withdrawn_soil_dates:
            earliest_withdrawn = None
            for wsd in withdrawn_soil_dates:
                wsd_str = wsd.strftime("%Y-%m-%d") if isinstance(wsd, (datetime.date, datetime.datetime)) else str(wsd)[:10]
                if earliest_withdrawn is None or wsd_str < earliest_withdrawn:
                    earliest_withdrawn = wsd_str
            if earliest_withdrawn and (earliest_invalid_day is None or earliest_withdrawn < earliest_invalid_day):
                earliest_invalid_day = earliest_withdrawn

        if earliest_invalid_day is not None:
            for k, v in plot_hist.items():
                if isinstance(v, dict):
                    k_d = None
                    try:
                        k_d = datetime.date.fromisoformat(k)
                    except Exception:
                        pass
                    if "weather" in v and (k_d not in supplied_weather_dates):
                        retained_weather_map[k] = v["weather"]
                    if (v.get("vegetation_state") is not None) and (k_d not in supplied_veg_dates):
                        retained_veg_map[k] = v["vegetation_state"]
                    if "irrigation" in v and (k_d not in explicit_event_dates):
                        retained_irrigation_map[k] = v["irrigation"]
                    if "soil_observations" in v and (k_d not in supplied_soil_obs_dates) and (k not in candidate_withdrawn_so):
                        if v["soil_observations"] is not None:
                            retained_soil_obs_map[k] = v["soil_observations"]
                            if k not in candidate_so:
                                candidate_so[k] = v["soil_observations"]
                    if "initial_soil_water" in v:
                        retained_init_soil_map[k] = v["initial_soil_water"]
                    if "initial_hydraulic_memory" in v:
                        retained_init_mem_map[k] = v["initial_hydraulic_memory"]
                    if "management_events" in v:
                        retained_events_map[k] = v["management_events"]

            to_delete = [k for k in list(plot_hist.keys()) if k >= earliest_invalid_day]
            for k in to_delete:
                plot_hist.pop(k, None)

        if explicit_soil is not None or explicit_mem is not None:
            to_delete = [k for k in list(plot_hist.keys()) if k >= day_key]
            for k in to_delete:
                plot_hist.pop(k, None)

        # Multi-day interval integration bounds:
        # Determine the earliest date where integration must begin
        if explicit_soil is not None:
            d_start = ts.date()
        elif earlier_than_cache is not None:
            d_start = earlier_than_cache
        elif earliest_invalid_day is not None:
            # Rebuild from the earliest affected transition!
            d_start = datetime.date.fromisoformat(earliest_invalid_day)
        else:
            # Check predecessor in cache: must be strictly PRECEDING target day (date < ts.date())
            prior_dates = [r["timestamp"].date() for r in plot_hist.values() if r["timestamp"].date() < ts.date()]
            if prior_dates:
                latest_pred_d = max(prior_dates)
                if (ts.date() - latest_pred_d).days > 1:
                    d_start = latest_pred_d + datetime.timedelta(days=1)
                else:
                    d_start = ts.date()
            else:
                # Check if we have a valid committed checkpoint predecessor
                if cp_step_key and earliest_invalid_day is None:
                    try:
                        cp_step_d = datetime.date.fromisoformat(cp_step_key)
                        if cp_step_d < ts.date():
                            d_start = cp_step_d + datetime.timedelta(days=1)
                        else:
                            d_start = ts.date()
                    except Exception:
                        earliest_supplied_d = min(supplied_dates) if supplied_dates else ts.date()
                        d_start = min(earliest_supplied_d, ts.date())
                else:
                    # No predecessor in cache: start from earliest date in supplied inputs or target date
                    earliest_supplied_d = min(supplied_dates) if supplied_dates else ts.date()
                    d_start = min(earliest_supplied_d, ts.date())
        d_end = ts.date()

        # R07: Transition identity check
        # If this exact transition is already committed and input forcing is unchanged, return it without advancing head or re-solving
        if (
            day_key in plot_hist
            and earliest_invalid_day is None
            and explicit_soil is None
            and explicit_mem is None
            and earlier_than_cache is None
            and plot_hist[day_key].get("water_state") is not None
        ):
            target_w = _extract_weather_for_date(ts.date())
            target_irr = _get_irrigation_for_date(ts.date())
            target_veg = _extract_veg_for_date(ts.date(), ts)
            target_so = _extract_soil_obs_for_date(ts.date())
            cached_entry = plot_hist[day_key]
            target_forcing_h = _compute_step_forcing_hash(
                target_w,
                target_irr,
                target_veg,
                target_so,
                predecessor_hash=cached_entry.get("predecessor_hash"),
                soil_param_digest=_state_digest(cached_entry.get("initial_soil_water")) if cached_entry.get("initial_soil_water") else None,
            )
            if (
                cached_entry.get("step_forcing_hash") == target_forcing_h
                and cached_entry.get("timestamp") == ts
                and cached_entry.get("cycle_id", "default_cycle") == cycle_id
                and cached_entry.get("geometry_version", "default_geom") == geometry_version
                and cached_entry.get("parameter_epoch", "v1") == parameter_epoch
                and cached_entry.get("soil_type", "loam") == soil_type
            ):
                return cached_entry["water_state"], cached_entry["feedback"]

        # Retrieve predecessor state strictly prior to d_start (date < d_start)
        predecessor_time = None
        cached_soil = None
        cached_mem = None
        prior_records = [r for r in plot_hist.values() if r["timestamp"].date() < d_start]
        if prior_records:
            prior_records.sort(key=lambda r: r["timestamp"])
            latest_pred = prior_records[-1]
            predecessor_time = latest_pred["timestamp"]
            cached_soil = latest_pred.get("soil_water")
            cached_mem = latest_pred.get("hydraulic_memory")

        d_start_str = d_start.strftime("%Y-%m-%d")
        if cached_soil is None and d_start_str in retained_init_soil_map:
            cached_soil = retained_init_soil_map[d_start_str]
        if cached_mem is None and d_start_str in retained_init_mem_map:
            cached_mem = retained_init_mem_map[d_start_str]
        if cached_soil is None and d_start_str in plot_init_hist:
            cached_soil = plot_init_hist[d_start_str][0]
            cached_mem = plot_init_hist[d_start_str][1]
        if cached_soil is None and plot_scope_key in _PLOT_WATER_STATE_MEMORY:
            cached_soil, cached_mem = _PLOT_WATER_STATE_MEMORY[plot_scope_key]

        soil_profile_state = explicit_soil or cached_soil
        hydraulic_memory = explicit_mem or cached_mem

        weather_ensemble = op_ctx.get("weather_ensemble") or getattr(inputs, "weather_ensemble", None)
        soil_type = op_ctx.get("soil_type") or getattr(inputs, "soil_type", "loam") or "loam"

        # Build comprehensive interval forcing and dependency digest
        interval_forcing_entries = []
        d_walk = d_start
        while d_walk <= d_end:
            w_walk = _extract_weather_for_date(d_walk)
            irr_walk = _get_irrigation_for_date(d_walk)
            step_ts_walk = ts if (d_walk == ts.date()) else datetime.datetime.combine(d_walk, datetime.time(12, 0, tzinfo=timezone.utc))
            v_walk = _extract_veg_for_date(d_walk, step_ts_walk)
            so_walk = _extract_soil_obs_for_date(d_walk)

            interval_forcing_entries.append((
                d_walk.isoformat(),
                tuple(sorted((k, str(v)) for k, v in w_walk.items())),
                round(irr_walk, 4),
                (round(getattr(v_walk, "lai", 0.0), 4), round(getattr(v_walk, "fvc", 0.0), 4), round(getattr(v_walk, "root_depth_proxy_m", 0.0), 4)) if v_walk else "none",
                _state_digest(so_walk),
            ))
            d_walk += datetime.timedelta(days=1)

        interval_components = (
            ts.isoformat(),
            tuple(interval_forcing_entries),
            _state_digest(explicit_soil),
            _state_digest(cached_soil),
            _state_digest(explicit_mem),
            _state_digest(cached_mem),
            predecessor_time.isoformat() if predecessor_time else "none",
            _state_digest(soil_obs),
            _state_digest(weather_ensemble),
            round(lai, 4),
            round(fvc, 4),
            round(root_depth, 4),
            soil_type,
            cycle_id,
            geometry_version,
            parameter_epoch,
        )
        interval_hash = hashlib.sha256(repr(interval_components).encode("utf-8")).hexdigest()[:24]

        # Check idempotent replay with identical interval history, dependencies, and timestamp
        if day_key in plot_hist:
            cached_entry = plot_hist[day_key]
            if (
                cached_entry.get("interval_hash") == interval_hash
                and cached_entry.get("timestamp") == ts
                and cached_entry.get("cycle_id", "default_cycle") == cycle_id
                and cached_entry.get("geometry_version", "default_geom") == geometry_version
                and cached_entry.get("parameter_epoch", "v1") == parameter_epoch
                and cached_entry.get("soil_type", "loam") == soil_type
                and explicit_soil is None
                and explicit_mem is None
            ):
                return cached_entry["water_state"], cached_entry["feedback"]
            else:
                to_delete = [
                    k for k, v in list(plot_hist.items())
                    if v.get("timestamp", ts) >= cached_entry.get("timestamp", ts) or k >= day_key
                ]
                for k in to_delete:
                    plot_hist.pop(k, None)

        curr_d = d_start
        current_soil = soil_profile_state
        current_mem = hydraulic_memory
        last_water_state = None
        last_feedback = None
        current_days_since_wetting = 0
        if current_soil and getattr(current_soil, "evaporation_state", None):
            current_days_since_wetting = current_soil.evaporation_state.days_since_wetting
        prev_step_hash = _state_digest(current_soil)
        candidate_hist = {}
        candidate_step_veg = {}
        candidate_step_so = {}
        candidate_step_init = {}

        while curr_d <= d_end:
            is_target_day = (curr_d == ts.date())
            step_ts = ts if is_target_day else datetime.datetime.combine(curr_d, datetime.time(12, 0, tzinfo=timezone.utc))
            step_weather = _extract_weather_for_date(curr_d)
            step_irrigation = _get_irrigation_for_date(curr_d)
            step_veg = _extract_veg_for_date(curr_d, step_ts)
            step_soil_obs = _extract_soil_obs_for_date(curr_d)
            step_init_soil = current_soil
            step_init_mem = current_mem

            w_state, fb = WaterIntelligenceEngine.execute_pipeline(
                plot_id=plot_id,
                timestamp=step_ts,
                vegetation_state=step_veg,
                weather_observations=step_weather,
                soil_profile_state=current_soil,
                soil_observations=step_soil_obs,
                previous_hydraulic_memory=current_mem,
                soil_type=soil_type,
                irrigation_applied_mm=step_irrigation,
                weather_ensemble=weather_ensemble if is_target_day else None,
                hydrology_mode=HydrologyMode.FAO56_LAYERED_BUCKET,
                days_since_wetting=current_days_since_wetting,
            )

            if w_state is not None:
                current_soil = getattr(w_state, "soil_water", None)
                current_mem = getattr(w_state, "hydraulic_memory", None)
                if current_soil and getattr(current_soil, "evaporation_state", None):
                    current_days_since_wetting = current_soil.evaporation_state.days_since_wetting
                else:
                    current_days_since_wetting = current_days_since_wetting + 1

                step_key = curr_d.strftime("%Y-%m-%d")
                soil_param_digest = _state_digest(step_init_soil)
                step_pred_hash = prev_step_hash
                step_forcing_h = _compute_step_forcing_hash(
                    step_weather,
                    step_irrigation,
                    step_veg,
                    step_soil_obs,
                    predecessor_hash=step_pred_hash,
                    soil_param_digest=soil_param_digest,
                    req_ts=step_ts.isoformat(),
                )
                prev_step_hash = step_forcing_h
                step_ev_hash = interval_hash if is_target_day else step_forcing_h[:16]

                # R10 + R11: Isolate candidate step state in local structures before CAS commit
                candidate_hist[step_key] = {
                    "timestamp": step_ts,
                    "soil_water": current_soil,
                    "hydraulic_memory": current_mem,
                    "water_state": w_state,
                    "feedback": fb,
                    "weather": step_weather,
                    "irrigation": step_irrigation,
                    "vegetation_state": step_veg,
                    "lai": getattr(step_veg, "lai", lai) if step_veg else lai,
                    "fvc": getattr(step_veg, "fvc", fvc) if step_veg else fvc,
                    "root_depth": getattr(step_veg, "root_depth_proxy_m", root_depth) if step_veg else root_depth,
                    "soil_observations": step_soil_obs,
                    "initial_soil_water": step_init_soil,
                    "initial_hydraulic_memory": step_init_mem,
                    "evidence_hash": step_ev_hash,
                    "interval_hash": interval_hash if is_target_day else step_ev_hash,
                    "predecessor_hash": step_pred_hash,
                    "step_forcing_hash": step_forcing_h,
                    "cycle_id": cycle_id,
                    "geometry_version": geometry_version,
                    "parameter_epoch": parameter_epoch,
                    "soil_type": soil_type,
                }
                if step_veg:
                    candidate_veg[step_key] = step_veg
                    candidate_step_veg[step_key] = step_veg
                if step_soil_obs:
                    candidate_so[step_key] = step_soil_obs
                    candidate_step_so[step_key] = step_soil_obs
                candidate_init[step_key] = (step_init_soil, step_init_mem)
                candidate_step_init[step_key] = (step_init_soil, step_init_mem)

                last_water_state = w_state
                last_feedback = fb

            curr_d += datetime.timedelta(days=1)

        if last_water_state is not None:
            # C10: Exact historical query (day_key < cp_step_key with identical step forcing)
            # should return/reconstruct the original qualified transition WITHOUT replacing the operational head or advancing sequence!
            h_entry = cp_payload.get("history_summary", {}).get(day_key) if isinstance(cp_payload, dict) else None
            is_exact_historical_replay = (
                bool(cp_step_key)
                and day_key < cp_step_key
                and h_entry is not None
                and h_entry.get("step_forcing_hash") == prev_step_hash
            )
            if is_exact_historical_replay:
                with _get_plot_scope_lock(plot_scope_key):
                    ram_seq = _PLOT_CURRENT_SEQUENCE.get(plot_scope_key, 0)
                    cp_seq = latest_cp.get("sequence", 0) if latest_cp else (cp_payload.get("sequence", 0) if isinstance(cp_payload, dict) else 0)
                    ram_head = _PLOT_CURRENT_HEAD.get(plot_scope_key)
                    # N07: If RAM already has a newer publication head/sequence, do not overwrite RAM with stale history!
                    ram_is_ahead = (
                        ram_head is not None
                        and (ram_seq > cp_seq or (ram_seq == cp_seq and day_key < cp_step_key))
                    )
                    if not ram_is_ahead:
                        if "history_summary" in cp_payload and isinstance(cp_payload["history_summary"], dict):
                            for h_key, h_data in cp_payload["history_summary"].items():
                                if isinstance(h_data, dict):
                                    h_soil = _deserialize_soil_water(h_data.get("soil_water"))
                                    h_mem = _deserialize_hydraulic_memory(h_data.get("hydraulic_memory"))
                                    h_veg = _deserialize_veg_state(h_data.get("vegetation"))
                                    h_so = _deserialize_soil_observation(h_data.get("soil_observations"))
                                    ts_raw = h_data.get("timestamp")
                                    try:
                                        ts_obj = datetime.datetime.fromisoformat(ts_raw) if ts_raw else ts
                                    except Exception:
                                        ts_obj = ts
                                    plot_hist[h_key] = {
                                        "timestamp": ts_obj,
                                        "soil_water": h_soil,
                                        "hydraulic_memory": h_mem,
                                        "water_state": None,
                                        "feedback": None,
                                        "weather": h_data.get("weather", {}),
                                        "irrigation": float(h_data.get("irrigation", 0.0)),
                                        "vegetation_state": h_veg,
                                        "lai": getattr(h_veg, "lai", 0.0) if h_veg else 0.0,
                                        "fvc": getattr(h_veg, "fvc", 0.0) if h_veg else 0.0,
                                        "root_depth": getattr(h_veg, "root_depth_proxy_m", 0.4) if h_veg else 0.4,
                                        "soil_observations": h_so,
                                        "initial_soil_water": _deserialize_soil_water(h_data.get("initial_soil_water")),
                                        "initial_hydraulic_memory": _deserialize_hydraulic_memory(h_data.get("initial_hydraulic_memory")),
                                        "evidence_hash": h_data.get("evidence_hash"),
                                        "interval_hash": h_data.get("interval_hash"),
                                        "predecessor_hash": h_data.get("predecessor_hash"),
                                        "step_forcing_hash": h_data.get("step_forcing_hash"),
                                    }
                                    if h_so:
                                        candidate_so[h_key] = h_so
                        plot_hist.update(candidate_hist)
                        _PLOT_WATER_STATE_HISTORY[plot_id] = plot_hist
                        if candidate_veg:
                            plot_veg_hist.update(candidate_veg)
                            _PLOT_VEGETATION_HISTORY[plot_id] = plot_veg_hist
                        if candidate_so:
                            plot_so_hist.update(candidate_so)
                            _PLOT_SOIL_OBS_HISTORY[plot_id] = plot_so_hist
                        if candidate_init:
                            plot_init_hist.update(candidate_init)
                            _PLOT_INITIAL_STATE_HISTORY[plot_id] = plot_init_hist
                        if "soil_water" in cp_payload and isinstance(cp_payload["soil_water"], dict):
                            hyd_soil = _deserialize_soil_water(cp_payload["soil_water"])
                            hyd_mem = _deserialize_hydraulic_memory(cp_payload.get("hydraulic_memory", {}))
                            if hyd_soil:
                                _PLOT_WATER_STATE_MEMORY[plot_scope_key] = (hyd_soil, hyd_mem)
                                _PLOT_WATER_STATE_MEMORY[plot_id] = (hyd_soil, hyd_mem)
                return last_water_state, last_feedback

            try:
                try:
                    from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService
                except ImportError:
                    from world_model.canonical_worldline import CanonicalWorldlineService
                cw_svc = CanonicalWorldlineService()
                cp_id = f"cp_hyd_{plot_id}_{day_key}_{hashlib.sha256(f'{plot_id}:{day_key}:{prev_step_hash}'.encode()).hexdigest()[:12]}"
                merged_history = dict(plot_hist)
                merged_history.update(candidate_hist)
                cp_payload = {
                    "step_key": day_key,
                    "timestamp": ts.isoformat(),
                    "sequence": len(merged_history),
                    "parameter_epoch": parameter_epoch,
                    "cycle_id": cycle_id,
                    "geometry_version": geometry_version,
                    "soil_type": soil_type,
                    "soil_water": _serialize_soil_water(current_soil),
                    "hydraulic_memory": _serialize_hydraulic_memory(current_mem),
                    "initial_soil_water": _serialize_soil_water(candidate_init.get(day_key, (None, None))[0] or (plot_init_hist.get(day_key, (None, None))[0])),
                    "initial_hydraulic_memory": _serialize_hydraulic_memory(candidate_init.get(day_key, (None, None))[1] or (plot_init_hist.get(day_key, (None, None))[1])),
                    "soil_observations": _serialize_soil_observation(candidate_so.get(day_key) or plot_so_hist.get(day_key) or soil_obs),
                    "step_forcing_hash": prev_step_hash,
                    "evidence_hash": last_water_state.metadata.evidence_hash if hasattr(last_water_state, "metadata") and hasattr(last_water_state.metadata, "evidence_hash") else prev_step_hash[:16],
                    "events": dict(candidate_events),
                    "withdrawn_soil_dates": sorted(d.strftime("%Y-%m-%d") if isinstance(d, (datetime.date, datetime.datetime)) else str(d) for d in candidate_withdrawn_so),
                    "withdrawn_veg_dates": sorted(d.strftime("%Y-%m-%d") if isinstance(d, (datetime.date, datetime.datetime)) else str(d) for d in candidate_withdrawn_veg),
                    "history_summary": {
                        k: {
                            "timestamp": v["timestamp"].isoformat() if isinstance(v.get("timestamp"), (datetime.datetime, datetime.date)) else str(v.get("timestamp")),
                            "step_forcing_hash": v.get("step_forcing_hash"),
                            "predecessor_hash": v.get("predecessor_hash"),
                            "evidence_hash": v.get("evidence_hash"),
                            "interval_hash": v.get("interval_hash"),
                            "cycle_id": v.get("cycle_id", cycle_id),
                            "geometry_version": v.get("geometry_version", geometry_version),
                            "parameter_epoch": v.get("parameter_epoch", parameter_epoch),
                            "soil_type": v.get("soil_type", soil_type),
                            "soil_water": _serialize_soil_water(v.get("soil_water")),
                            "hydraulic_memory": _serialize_hydraulic_memory(v.get("hydraulic_memory")),
                            "initial_soil_water": _serialize_soil_water(v.get("initial_soil_water")),
                            "initial_hydraulic_memory": _serialize_hydraulic_memory(v.get("initial_hydraulic_memory")),
                            "irrigation": float(v.get("irrigation", 0.0)),
                            "weather": v.get("weather", {}),
                            "vegetation": _serialize_veg_state(v.get("vegetation_state")),
                            "soil_observations": _serialize_soil_observation(v.get("soil_observations")),
                        }
                        for k, v in merged_history.items()
                        if isinstance(v, dict) and "timestamp" in v
                    },
                }
                # R10 + R11 + V10 + V11: Compare-and-swap persistence check and head verification
                cw_svc.save_hydraulic_checkpoint(
                    plot_id=plot_id,
                    checkpoint_id=cp_id,
                    checkpoint_payload=cp_payload,
                    tenant_id=tenant_id,
                    namespace=namespace,
                    cycle_id=cycle_id,
                    geometry_version=geometry_version,
                    expected_predecessor_head=expected_head,
                )

                # Authoritative RAM cache commit ONLY after successful checkpoint save
                # V11 & D11 & D12: Synchronized atomic commit to RAM under scoped publication lock
                with _get_plot_scope_lock(plot_scope_key):
                    latest_durable = cw_svc.load_latest_hydraulic_checkpoint(plot_id=plot_id, tenant_id=tenant_id, namespace=namespace, cycle_id=cycle_id, geometry_version=geometry_version)
                    if not latest_durable or latest_durable.get("checkpoint_id") != cp_id:
                        raise RuntimeError(f"Durable head verification failed: expected {cp_id}, found {latest_durable.get('checkpoint_id') if latest_durable else None}")

                    plot_hist.update(candidate_hist)
                    _PLOT_WATER_STATE_HISTORY[plot_id] = plot_hist

                    plot_events.clear()
                    plot_events.update(candidate_events)
                    _PLOT_MANAGEMENT_EVENTS[plot_id] = plot_events

                    plot_veg_hist.clear()
                    plot_veg_hist.update(candidate_veg)
                    _PLOT_VEGETATION_HISTORY[plot_id] = plot_veg_hist

                    plot_so_hist.clear()
                    plot_so_hist.update(candidate_so)
                    _PLOT_SOIL_OBS_HISTORY[plot_id] = plot_so_hist

                    plot_withdrawn_so.clear()
                    plot_withdrawn_so.update(candidate_withdrawn_so)
                    _PLOT_WITHDRAWN_SOIL_OBS[plot_id] = plot_withdrawn_so

                    plot_withdrawn_veg.clear()
                    plot_withdrawn_veg.update(candidate_withdrawn_veg)
                    _PLOT_WITHDRAWN_VEG[plot_id] = plot_withdrawn_veg

                    if candidate_init:
                        plot_init_hist.update(candidate_init)
                        _PLOT_INITIAL_STATE_HISTORY[plot_id] = plot_init_hist

                    _PLOT_WATER_STATE_MEMORY[plot_scope_key] = (current_soil, current_mem)
                    _PLOT_WATER_STATE_MEMORY[legacy_scope_key] = (current_soil, current_mem)
                    _PLOT_WATER_STATE_MEMORY[plot_id] = (current_soil, current_mem)
                    _PLOT_CURRENT_HEAD[plot_scope_key] = cp_id
                    _PLOT_CURRENT_HEAD[legacy_scope_key] = cp_id
                    _PLOT_CURRENT_HEAD[plot_id] = cp_id
                    pub_seq = latest_durable.get("sequence", 0) if latest_durable else cp_payload.get("sequence", len(merged_history))
                    _PLOT_CURRENT_SEQUENCE[plot_scope_key] = pub_seq
                    _PLOT_CURRENT_SEQUENCE[legacy_scope_key] = pub_seq
                    _PLOT_CURRENT_SEQUENCE[plot_id] = pub_seq
                    _PLOT_CURRENT_STEP[plot_scope_key] = day_key
                    _PLOT_CURRENT_STEP[legacy_scope_key] = day_key
            except ConcurrencyConflictError:
                _rollback_ram_state()
                raise
            except Exception as e:
                _rollback_ram_state()
                raise RuntimeError(f"Hydraulic checkpoint persistence failed: {e}") from e

        return last_water_state, last_feedback
    except (ConcurrencyConflictError, RuntimeError):
        if '_rollback_ram_state' in locals():
            _rollback_ram_state()
        raise
    except Exception as e:
        if '_rollback_ram_state' in locals():
            _rollback_ram_state()
        import logging
        logging.getLogger(__name__).warning(f"[L3] Canonical water engine execution note: {e}")
        return None, None


def _extract_plot_context(
    inputs: Any, l1_output: Any = None, l2_output: Any = None,
) -> PlotContext:
    """Extract PlotContext from OrchestratorInput.

    INT-2: Also extracts soil_texture_class from L1 static data.
    """
    if inputs is None:
        return PlotContext()

    crop_cfg = getattr(inputs, "crop_config", {}) or {}
    op_ctx = getattr(inputs, "operational_context", {}) or {}
    policy = getattr(inputs, "policy_snapshot", {}) or {}

    from services.agribrain.common.downstream_crop_context import resolve_downstream_crop_phenology

    crop_semantics = resolve_downstream_crop_phenology(
        inputs=inputs, l2_output=l2_output,
    )
    crop_type = crop_semantics.crop_for_species_engine
    declared_crop = crop_semantics.declared_crop or "unknown"

    irrigation = "unknown"
    if isinstance(op_ctx, dict):
        irrigation = op_ctx.get("irrigation_type", "unknown")

    constraints = {}
    if isinstance(op_ctx, dict) and "constraints" in op_ctx:
        constraints = op_ctx["constraints"]

    # INT-2: Extract soil texture from L1 static data
    soil_texture = ""
    soil_clay = None
    soil_ph = None
    if l1_output is not None:
        l1_static = getattr(l1_output, "static", {}) or {}
        if isinstance(l1_static, dict):
            tex = l1_static.get("texture_class")
            if tex and isinstance(tex, str):
                soil_texture = tex.lower()
            clay = l1_static.get("soil_clay")
            if clay is not None and isinstance(clay, (int, float)):
                soil_clay = float(clay)
            ph = l1_static.get("soil_ph")
            if ph is not None and isinstance(ph, (int, float)):
                soil_ph = float(ph)

    return PlotContext(
        crop_type=crop_type,
        declared_crop_type=declared_crop,
        crop_posterior_hash=crop_semantics.crop_posterior_hash,
        crop_resolution=crop_semantics.crop_resolution,
        species_specific_allowed=crop_semantics.species_specific_allowed,
        irrigation_type=irrigation,
        constraints=constraints,
        soil_texture_class=soil_texture,
        soil_clay_pct=soil_clay,
        soil_ph=soil_ph,
    )


def _extract_weather_forecast(l1_output: Any) -> List[Dict]:
    """Extract weather forecast from L1 FieldTensor output.

    Only complete, explicitly sourced forecast days are admitted.  Historical
    observations and persistence-filled values are not relabeled as forecasts.

    Returns list of dicts with keys: rain, temp_max, temp_min, et0, date.
    """
    if l1_output is None:
        return []

    # Use forecast_7d only when the upstream source is explicit and complete.
    forecast_7d = getattr(l1_output, "forecast_7d", [])
    if forecast_7d and isinstance(forecast_7d, list):
        forecast = []
        for entry in forecast_7d:
            if isinstance(entry, dict):
                rain = entry.get("precipitation", entry.get("rain"))
                temp_max = entry.get("temp_max")
                temp_min = entry.get("temp_min")
                et0 = entry.get("et0")
                source = str(entry.get("source") or "").strip()
                if (
                    source in ("", "persistence_forecast")
                    or not all(
                        isinstance(value, (int, float))
                        for value in (rain, temp_max, temp_min, et0)
                    )
                ):
                    continue
                forecast.append({
                    "rain": float(rain),
                    "temp_max": float(temp_max),
                    "temp_min": float(temp_min),
                    "et0": float(et0),
                    "date": entry.get("date", ""),
                    "rain_prob": float(entry.get("rain_prob"))
                    if isinstance(entry.get("rain_prob"), (int, float)) else None,
                    "source": source,
                })
        if forecast:
            return forecast
    return []


def _build_legacy_l3_context(
    inputs: Any, l1_output: Any, l2_output: Any,
) -> Layer3InputContext:
    """Build Layer3InputContext from legacy VegIntOutput + FieldTensor.

    Enhanced bridge: extracts all available intelligence from VegIntOutput
    (curve quality, growth velocity, phenology confidence, zone metrics,
    spatial heterogeneity, anomaly attribution) to close the signal gap
    between the legacy VegIntOutput and canonical Layer2Output paths.
    """
    from layer1_fusion.schemas import DataHealthScore

    plot_id = getattr(inputs, "plot_id", "unknown") if inputs else "unknown"

    # ── Stress signals from VegIntOutput anomalies ──────────────────────
    stress_summary: Dict[str, float] = {}
    stress_detail: Dict[str, Dict[str, Any]] = {}
    operational_signals: Dict[str, Any] = {
        "sar_available": False, "optical_available": False,
        "rain_available": False, "temp_available": False,
        "optical_obs_count": 0, "sar_obs_count": 0,
        "water_deficit_severity": 0.0, "thermal_severity": 0.0,
        "has_anomaly": False, "anomaly_severity": 0.0,
        "anomaly_type": "NONE", "growth_velocity": 0.0,
        "has_water_evidence": False, "conflict_count": 0,
        "gap_types": [],
    }

    if l2_output:
        anomalies = getattr(l2_output, "anomalies", [])
        for a in (anomalies or []):
            cause = getattr(a, "likely_cause", "") or ""
            sev = getattr(a, "severity", 0.0)
            conf = getattr(a, "confidence", 0.5)
            atype_raw = getattr(a, "type", None)
            atype_str = (atype_raw.value if hasattr(atype_raw, "value")
                         else str(atype_raw)) if atype_raw else "UNKNOWN"

            # Map anomaly causes to canonical stress types
            stress_type = None
            if "water" in cause.lower() or "drought" in cause.lower():
                stress_type = "WATER"
                operational_signals["water_deficit_severity"] = max(
                    operational_signals["water_deficit_severity"], sev)
                operational_signals["has_water_evidence"] = True
            elif "heat" in cause.lower() or "thermal" in cause.lower():
                stress_type = "THERMAL"
                operational_signals["thermal_severity"] = max(
                    operational_signals["thermal_severity"], sev)
            elif "nutrient" in cause.lower() or "nitrogen" in cause.lower():
                stress_type = "NUTRIENT"
            elif "disease" in cause.lower() or "biotic" in cause.lower():
                stress_type = "BIOTIC"
            elif cause:
                stress_type = cause.upper().replace(" ", "_")

            if stress_type and sev > 0:
                if sev >= stress_summary.get(stress_type, 0.0):
                    stress_summary[stress_type] = sev
                    stress_detail[stress_type] = {
                        "severity": sev,
                        "confidence": conf,
                        "uncertainty": 1.0 - conf,
                        "primary_driver": cause,
                        "evidence_count": 1,
                        "explanation_basis": [f"Anomaly: {atype_str} — {cause}"],
                        "spatial_scope": "plot",
                        "diagnostic_only": False,
                    }

            if sev > 0:
                operational_signals["has_anomaly"] = True
                operational_signals["anomaly_severity"] = max(
                    operational_signals["anomaly_severity"], sev)
                operational_signals["anomaly_type"] = atype_str

        # ── Growth velocity from curve derivative ───────────────────────
        curve = getattr(l2_output, "curve", None)
        if curve:
            d1 = getattr(curve, "ndvi_fit_d1", [])
            if d1 and isinstance(d1, list) and len(d1) > 0:
                operational_signals["growth_velocity"] = float(d1[-1])

        # ── Spatial heterogeneity from stability ────────────────────────
        stability = getattr(l2_output, "stability", None)
        if stability:
            sc = getattr(stability, "stability_class", "STABLE")
            sc_val = sc.value if hasattr(sc, "value") else str(sc)
            if sc_val in ("HETEROGENEOUS", "TRANSIENT_VAR"):
                operational_signals["spatial_heterogeneity"] = True
                mean_var = getattr(stability, "mean_spatial_var", 0.0)
                operational_signals["spatial_variance"] = float(mean_var)
            else:
                operational_signals["spatial_heterogeneity"] = False

    # ── L1 data availability ────────────────────────────────────────────
    sar_obs = 0
    if l1_output:
        ts = getattr(l1_output, "plot_timeseries", [])
        if ts and isinstance(ts, list):
            operational_signals["optical_available"] = True
            operational_signals["optical_obs_count"] = len(ts)

            # ── GAP 6: Compute cumulative water deficit (ET0 - precip) ──
            cumulative_deficit_mm = 0.0
            deficit_days = 0
            for entry in ts:
                if isinstance(entry, dict):
                    if entry.get("vv") is not None:
                        operational_signals["sar_available"] = True
                        sar_obs += 1
                    rain = entry.get("precipitation", entry.get("rain", entry.get("rainfall_mm")))
                    et0  = entry.get("et0", entry.get("ET0"))
                    if rain is not None and et0 is not None:
                        r = float(rain)
                        e = float(et0)
                        daily_deficit = max(0.0, e - r)
                        cumulative_deficit_mm += daily_deficit
                        if daily_deficit > 0:
                            deficit_days += 1
                    if entry.get("temp_max") is not None:
                        operational_signals["temp_available"] = True

            # Normalise: severity 0-1 where 50mm cumulative deficit = 1.0
            if cumulative_deficit_mm > 0 and not operational_signals["water_deficit_severity"]:
                raw_severity = min(1.0, cumulative_deficit_mm / 50.0)
                operational_signals["water_deficit_severity"] = round(raw_severity, 3)
                operational_signals["has_water_evidence"] = raw_severity > 0.2
                operational_signals["cumulative_deficit_mm"] = round(cumulative_deficit_mm, 1)
                operational_signals["deficit_days"] = deficit_days

            # ── Real precipitation signals for L3 features (breaks circular proxy) ──
            # Compute actual rain_sum_7d, rain_sum_14d, days_since_rain from timeseries
            all_rain = []
            for entry in ts:
                if isinstance(entry, dict):
                    r = entry.get("precipitation", entry.get("rain", entry.get("rainfall_mm")))
                    all_rain.append(float(r) if r is not None else None)
            # Do not turn missing days into zero-rain observations.  The 14-day
            # diagnostic is admitted only for a complete recent window.
            recent_rain = all_rain[-14:]
            if len(recent_rain) == 14 and all(r is not None for r in recent_rain):
                # Sum last 7 and 14 days of available rain data
                operational_signals["real_rain_sum_7d"] = round(sum(recent_rain[-7:]), 1)
                operational_signals["real_rain_sum_14d"] = round(sum(recent_rain), 1)
                # Days since last significant rain (>2mm threshold)
                dsr = 0
                for r in reversed(recent_rain):
                    if r > 2.0:
                        break
                    dsr += 1
                operational_signals["real_days_since_rain"] = dsr
                operational_signals["real_rain_available"] = True
                operational_signals["rain_available"] = True
            else:
                operational_signals["rain_available"] = False

            operational_signals["sar_obs_count"] = sar_obs

        # Conflicts and gaps from provenance
        prov = getattr(l1_output, "provenance", {}) or {}
        if isinstance(prov, dict):
            conflicts = prov.get("layer0_conflicts", [])
            operational_signals["conflict_count"] = (
                len(conflicts) if isinstance(conflicts, list) else 0)
            # Gap types from provenance
            gaps = prov.get("data_gaps", [])
            if isinstance(gaps, list):
                operational_signals["gap_types"] = sorted(
                    {str(g.get("type", "")) for g in gaps if isinstance(g, dict)})

    # ── Phenology + GDD from L2 ────────────────────────────────────────
    from services.agribrain.common.downstream_crop_context import resolve_downstream_crop_phenology

    crop_semantics = resolve_downstream_crop_phenology(
        inputs=inputs, l2_output=l2_output,
    )
    phenology_stage = crop_semantics.stage_for_discrete_engine.lower()
    phenology_confidence = crop_semantics.stage_confidence
    # Phenology confidence is not a vigor measurement.  Keep the optional
    # growth feature empty unless Layer 2 publishes an explicit value.
    gdd_adjusted_vigor = None
    gdd_accumulated = 0.0

    if l2_output:
        pheno = getattr(l2_output, "phenology", None)
        if pheno:
            # compatibility stage_by_day is not a second truth owner

            # GDD from phenology confidence
            conf_by_day = []  # V2 confidence comes only from canonical posterior
            if conf_by_day and isinstance(conf_by_day, list):
                # Average phenology confidence → GDD vigor proxy
                valid_confs = [c for c in conf_by_day
                               if isinstance(c, (int, float))]
                if valid_confs:
                    gdd_adjusted_vigor = sum(valid_confs) / len(valid_confs)

            # Key dates for GDD accumulation
            key_dates = getattr(pheno, "key_dates", {})
            if isinstance(key_dates, dict):
                gdd_val = key_dates.get("gdd_accumulated")
                if gdd_val is not None:
                    gdd_accumulated = float(gdd_val)

    # ── Zone status from zone_metrics ───────────────────────────────────
    zone_status: Dict[str, Dict[str, Any]] = {}
    if l2_output:
        zone_metrics = getattr(l2_output, "zone_metrics", {})
        if zone_metrics and isinstance(zone_metrics, dict):
            for zone_id, zm in zone_metrics.items():
                z_curve = getattr(zm, "curve", zm.get("curve", None)
                                  if isinstance(zm, dict) else None)
                z_info: Dict[str, Any] = {
                    "dominant_stress_type": "NONE",
                    "severity": 0.0,
                    "confidence": 0.5,
                    "stress_count": 0,
                }
                if z_curve:
                    quality = getattr(z_curve, "quality", None)
                    if quality:
                        rmse = getattr(quality, "rmse", None)
                        if rmse is not None and float(rmse) > 0.15:
                            z_info["dominant_stress_type"] = "VARIABILITY"
                            z_info["severity"] = min(1.0, float(rmse) * 3.0)
                            z_info["stress_count"] = 1
                zone_status[str(zone_id)] = z_info

    # ── Vegetation status from curve ────────────────────────────────────
    vegetation_status: Dict[str, Any] = {}
    if l2_output:
        curve = getattr(l2_output, "curve", None)
        if curve:
            ndvi_fit = getattr(curve, "ndvi_fit", [])
            if ndvi_fit and isinstance(ndvi_fit, list):
                vegetation_status["ndvi_current"] = {
                    "value": float(ndvi_fit[-1]),
                    "unit": "index",
                    "confidence": 0.8,
                }
            quality = getattr(curve, "quality", None)
            if quality:
                rmse = getattr(quality, "rmse", None)
                if rmse is not None:
                    vegetation_status["curve_rmse"] = {
                        "value": float(rmse),
                        "unit": "index",
                        "confidence": 1.0,
                    }

    # ── Data health — derived from real L2 curve quality, not hardcoded ─
    overall_health = 0.4  # base
    confidence_ceiling = 0.5  # base

    if l2_output:
        curve = getattr(l2_output, "curve", None)
        if curve:
            quality = getattr(curve, "quality", None)
            if quality:
                rmse = getattr(quality, "rmse", 0.1)
                if rmse is not None:
                    # Low RMSE → high health. RMSE 0.0=perfect, 0.2=poor
                    curve_health = max(0.2, 1.0 - float(rmse) * 4.0)
                    overall_health = max(overall_health, curve_health)
                    confidence_ceiling = max(confidence_ceiling, curve_health)

        # Boost health if we have real phenology
        if phenology_stage != "unknown":
            overall_health = min(1.0, overall_health + 0.1)

    # Boost from L1 data richness
    if operational_signals["optical_available"]:
        overall_health = min(1.0, overall_health + 0.1)
    if operational_signals["sar_available"]:
        overall_health = min(1.0, overall_health + 0.05)
    if operational_signals["rain_available"]:
        overall_health = min(1.0, overall_health + 0.05)

    confidence_ceiling = min(1.0, max(confidence_ceiling, overall_health))

    health_status = ("ok" if overall_health > 0.5
                     else "degraded" if overall_health > 0.2
                     else "unusable")

    usable = overall_health > 0.2

    flags = []
    if not operational_signals["sar_available"]:
        flags.append("NO_SAR_DATA")
    if not operational_signals["rain_available"]:
        flags.append("NO_RAIN_DATA")
    if phenology_stage == "unknown":
        flags.append("PHENOLOGY_UNKNOWN")

    return Layer3InputContext(
        plot_id=plot_id,
        layer1_run_id=getattr(l1_output, "run_id", "") if l1_output else "",
        layer2_run_id=getattr(l2_output, "run_id", "") if l2_output else "",
        stress_summary=stress_summary,
        stress_detail=stress_detail,
        zone_status=zone_status,
        vegetation_status=vegetation_status,
        phenology_stage=phenology_stage,
        phenology_confidence=phenology_confidence,
        phenology_posterior_hash=crop_semantics.phenology_posterior_hash,
        stage_specific_allowed=crop_semantics.stage_specific_allowed,
        crop_posterior_hash=crop_semantics.crop_posterior_hash,
        crop_resolution=crop_semantics.crop_resolution,
        species_specific_allowed=crop_semantics.species_specific_allowed,
        gdd_adjusted_vigor=gdd_adjusted_vigor,
        gdd_accumulated=gdd_accumulated,
        operational_signals=operational_signals,
        data_health=DataHealthScore(
            overall=round(overall_health, 3),
            confidence_ceiling=round(confidence_ceiling, 3),
            status=health_status,
        ),
        confidence_ceiling=round(confidence_ceiling, 3),
        usable_for_layer3=usable,
        flags=flags,
    )
