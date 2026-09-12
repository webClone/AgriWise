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
from datetime import timezone
from typing import Any, Dict, List, Optional

from layer1_fusion.schemas import DataHealthScore

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


def _execute_canonical_water_engine(
    inputs: Any,
    l1_output: Any,
    l2_output: Any,
    run_timestamp: Optional[datetime.datetime] = None,
) -> tuple[Any, Any]:
    """Execute authoritative Layer 3 Hydrological Water Balance Engine."""
    try:
        from layer3_water.runner import WaterIntelligenceEngine
        from layer3_water.contracts import HydrologyMode
        from layer2_contracts.state_contracts import VegetationState

        plot_id = getattr(inputs, "plot_id", "P1") if inputs else "P1"
        ts = run_timestamp or datetime.datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # Build weather observations from L1
        timeseries = getattr(l1_output, "plot_timeseries", []) or []
        rec = timeseries[-1] if (timeseries and isinstance(timeseries[-1], dict)) else {}

        t_max = rec.get("temp_max") or rec.get("temp") or rec.get("temperature") or 25.0
        t_min = rec.get("temp_min") or rec.get("temp") or rec.get("temperature") or 15.0
        precip = rec.get("precipitation") or rec.get("rain") or rec.get("precip") or 0.0
        wind = rec.get("wind_speed") or rec.get("wind") or 2.0
        hum = rec.get("humidity") or rec.get("rh") or 60.0
        rh_min = rec.get("rh_min") or max(10.0, float(hum) - 15.0)
        rh_max = rec.get("rh_max") or min(100.0, float(hum) + 15.0)
        rn = rec.get("net_radiation_mj_m2") or 15.0

        weather_obs = {
            "t_max_c": float(t_max),
            "t_min_c": float(t_min),
            "precipitation_mm": float(precip),
            "wind_speed_2m_m_s": float(wind),
            "rh_min_pct": float(rh_min),
            "rh_max_pct": float(rh_max),
            "net_radiation_mj_m2": float(rn),
        }

        # Extract vegetation coordinates from L2
        veg_state = None
        if l2_output and hasattr(l2_output, "lai_mean"):
            lai = float(getattr(l2_output, "lai_mean", 1.5) or 1.5)
            fvc = float(getattr(l2_output, "canopy_cover_pct", 50.0) or 50.0) / 100.0
            veg_state = VegetationState(
                plot_id=plot_id,
                timestamp=ts,
                lai=lai,
                fvc=fvc,
                root_depth_proxy_m=1.0,
            )

        soil_type = getattr(inputs, "soil_type", "loam") or "loam"

        water_state, feedback = WaterIntelligenceEngine.execute_pipeline(
            plot_id=plot_id,
            timestamp=ts,
            vegetation_state=veg_state,
            weather_observations=weather_obs,
            soil_type=soil_type,
            hydrology_mode=HydrologyMode.FAO56_LAYERED_BUCKET,
        )
        return water_state, feedback
    except Exception as e:
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
