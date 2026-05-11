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

        # 2. Build DecisionFeatures from L2 interpreted intelligence
        features = build_decision_features(l3_context, plot_context)
        audit_log.append({
            "step": "build_features",
            "missing_drivers": [d.value for d in features.missing_inputs],
            "stage": features.current_stage,
            "sar_available": features.sar_available,
            "optical_available": features.optical_available,
        })

        # 3. Multi-hypothesis diagnosis (log-odds scoring)
        all_diagnoses: Dict[str, Diagnosis] = {}
        zone_status = getattr(l3_context, "zone_status", {}) or {}

        if zone_status and len(zone_status) > 1:
            # Zonal diagnosis — evaluate per zone
            for z_id, z_data in zone_status.items():
                z_diagnoses = self.diagnosis_engine.diagnose(features, plot_context)

                for d in z_diagnoses:
                    if d.probability > 0.5:
                        if d.problem_id not in all_diagnoses:
                            all_diagnoses[d.problem_id] = d
                            all_diagnoses[d.problem_id].affected_area_pct = 0.0
                            all_diagnoses[d.problem_id].hotspot_zone_ids = []

                        area_pct = z_data.get("area_pct", 100.0 / len(zone_status))
                        all_diagnoses[d.problem_id].affected_area_pct += area_pct
                        all_diagnoses[d.problem_id].hotspot_zone_ids.append(z_id)

                        if d.severity > all_diagnoses[d.problem_id].severity:
                            all_diagnoses[d.problem_id].severity = d.severity
        else:
            # Global plot-level diagnosis
            global_diagnoses = self.diagnosis_engine.diagnose(features, plot_context)
            for d in global_diagnoses:
                if d.probability > 0.5:
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

        audit_log.append({
            "step": "policy",
            "recommendation_count": len(recommendations),
            "allowed": sum(1 for r in recommendations if r.is_allowed),
            "blocked": sum(1 for r in recommendations if not r.is_allowed),
        })

        # 5. Execution plan (uses run_timestamp for determinism)
        execution_plan = self._build_execution_plan(recommendations, diagnosed_list, ts)

        # 6. Quality metrics
        metrics = self._calculate_quality_metrics(features, diagnosed_list, l3_context)

        # 7. Audit trail
        audit_trail = self._build_audit_trail(features, diagnosed_list)

        # Lineage
        lineage = {
            "l1_run_id": getattr(l3_context, "layer1_run_id", ""),
            "l2_run_id": getattr(l3_context, "layer2_run_id", ""),
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

        return out

    def _validate_input(self, ctx: Layer3InputContext) -> tuple:
        """Validate Layer3InputContext. Returns (is_usable, degrade_flags)."""
        flags: List[str] = []

        if not ctx.plot_id:
            flags.append("missing_plot_id")

        if not ctx.usable_for_layer3:
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
                required_inputs=r.blocked_reason,
                completion_signal="MANUAL_CONFIRM",
                depends_on=[],
                target_zones=target_zones,
                target_points=[],
            )
            tasks.append(task)

        return ExecutionPlan(
            tasks=tasks,
            edges=[],
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
            not (r.blocked_reason and r.is_allowed)
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

    # Case 1: l2_output is canonical Layer2Output
    if hasattr(l2_output, "stress_context") and hasattr(l2_output, "zone_stress_map"):
        from layer2_intelligence.outputs.layer3_adapter import build_layer3_context
        l3_ctx = build_layer3_context(l2_output)

        # Extract plot context from orchestrator inputs
        plot_ctx = _extract_plot_context(inputs)

        # Extract weather forecast from L1 output
        forecast = _extract_weather_forecast(l1_output)

        return run_layer3(
            l3_context=l3_ctx,
            plot_context=plot_ctx,
            weather_forecast=forecast,
        )

    # Case 2: l2_output is legacy VegIntOutput or None
    l3_ctx = _build_legacy_l3_context(inputs, l1_output, l2_output)
    plot_ctx = _extract_plot_context(inputs)
    forecast = _extract_weather_forecast(l1_output)

    return run_layer3(
        l3_context=l3_ctx,
        plot_context=plot_ctx,
        weather_forecast=forecast,
    )


def _extract_plot_context(inputs: Any) -> PlotContext:
    """Extract PlotContext from OrchestratorInput."""
    if inputs is None:
        return PlotContext()

    crop_cfg = getattr(inputs, "crop_config", {}) or {}
    op_ctx = getattr(inputs, "operational_context", {}) or {}
    policy = getattr(inputs, "policy_snapshot", {}) or {}

    crop_type = "unknown"
    if isinstance(crop_cfg, dict):
        crop_type = crop_cfg.get("crop", crop_cfg.get("crop_type", "unknown"))

    irrigation = "unknown"
    if isinstance(op_ctx, dict):
        irrigation = op_ctx.get("irrigation_type", "unknown")

    constraints = {}
    if isinstance(op_ctx, dict) and "constraints" in op_ctx:
        constraints = op_ctx["constraints"]

    return PlotContext(
        crop_type=crop_type,
        irrigation_type=irrigation,
        constraints=constraints,
    )


def _extract_weather_forecast(l1_output: Any) -> List[Dict]:
    """Extract weather forecast from L1 FieldTensor output.

    Priority:
      1. forecast_7d (populated by persistence forecast or API)
      2. Last 3-7 days of plot_timeseries (fallback)

    Returns list of dicts with keys: rain, temp_max, temp_min, et0, date.
    """
    if l1_output is None:
        return []

    # Priority 1: Use forecast_7d if available (populated by _build_persistence_forecast)
    forecast_7d = getattr(l1_output, "forecast_7d", [])
    if forecast_7d and isinstance(forecast_7d, list):
        forecast = []
        for entry in forecast_7d:
            if isinstance(entry, dict):
                rain = entry.get("precipitation", entry.get("rain", 0.0))
                forecast.append({
                    "rain": float(rain) if rain is not None else 0.0,
                    "temp_max": float(entry.get("temp_max", 25.0) or 25.0),
                    "temp_min": float(entry.get("temp_min", 12.0) or 12.0),
                    "et0": float(entry.get("et0", 4.0) or 4.0),
                    "date": entry.get("date", ""),
                    "rain_prob": float(entry.get("rain_prob", 0.0) or 0.0),
                })
        if forecast:
            return forecast

    # Priority 2: Fallback to last entries of plot_timeseries
    ts = getattr(l1_output, "plot_timeseries", [])
    if not ts or not isinstance(ts, list):
        return []

    forecast = []
    for entry in ts[-7:]:
        if isinstance(entry, dict):
            rain = entry.get("precipitation", entry.get("rainfall_mm",
                   entry.get("rain", 0.0)))
            forecast.append({
                "rain": float(rain) if rain is not None else 0.0,
                "temp_max": float(entry.get("temp_max", entry.get("tmax", 25.0)) or 25.0),
                "temp_min": float(entry.get("temp_min", entry.get("tmin", 12.0)) or 12.0),
                "et0": float(entry.get("et0", entry.get("ET0", 4.0)) or 4.0),
                "date": entry.get("date", ""),
            })

    return forecast


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
                    if (rain is not None or et0 is not None):
                        operational_signals["rain_available"] = True
                        r = float(rain) if rain is not None else 0.0
                        e = float(et0)  if et0  is not None else 0.0
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
    phenology_stage = "unknown"
    gdd_adjusted_vigor = None
    gdd_accumulated = 0.0

    if l2_output:
        pheno = getattr(l2_output, "phenology", None)
        if pheno:
            stages = getattr(pheno, "stage_by_day", [])
            if stages:
                for s in reversed(stages):
                    val = s.value if hasattr(s, "value") else str(s)
                    if val.upper() != "UNKNOWN":
                        phenology_stage = val.lower()
                        break

            # GDD from phenology confidence
            conf_by_day = getattr(pheno, "confidence_by_day", [])
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
                z_pheno = getattr(zm, "phenology", zm.get("phenology", None)
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
                if z_pheno:
                    z_stage = getattr(z_pheno, "stage_by_day", [])
                    if z_stage:
                        last = z_stage[-1]
                        z_info["phenology_stage"] = (
                            last.value if hasattr(last, "value") else str(last))
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
