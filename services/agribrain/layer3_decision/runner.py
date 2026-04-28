from datetime import timezone

import datetime
from typing import List, Dict, Any

from layer1_fusion.schema import FieldTensor
from layer2_veg_int.schema import VegIntOutput
from layer3_decision.schema import (
    DecisionInput, DecisionOutput, PlotContext, Diagnosis,
    ExecutionPlan, TaskNode, QualityMetrics, AuditTrail, Recommendation
)
from layer3_decision.features.builder import build_decision_features, DecisionFeatures
from layer3_decision.diagnosis.inference import DiagnosisEngine
from layer3_decision.policy.policies import PolicyEngine

class DecisionIntelligenceEngine:
    
    def __init__(self):
        self.diagnosis_engine = DiagnosisEngine()
        self.policy_engine = PolicyEngine()
        
    def run_decision_cycle(self, inputs: DecisionInput) -> DecisionOutput:
        """
        Orchestrates the Research-Grade decision loop.
        """
        
        # 1. Feature Engineering (Global Plot Level)
        global_features = build_decision_features(inputs.tensor, inputs.veg_int, inputs.context)
        
        # 2. Zonal Diagnosis (Phase 11 Spatial Extension)
        all_diagnoses: Dict[str, Diagnosis] = {} # Deduplicated by problem_id
        
        # If we have zones, evaluate per zone
        zone_metrics = getattr(inputs.veg_int, "zone_metrics", {})
        zones = getattr(inputs.tensor, "zones", {})
        
        if zone_metrics and zones:
            for z_id, z_metric in zone_metrics.items():
                print(f"🌍 [Layer 3] Evaluating Diagnoses for {z_id}")
                
                # Mock a zonal feature set (ideally builder would take zone_metrics)
                # For now, we reuse global rules but we should map Zonal NDVI / Stage.
                # In a full refactor, `build_decision_features` would accept `z_metric`.
                # We will use the global features as a baseline, but ideally stage is zone-specific.
                
                # For Phase 11 MVP, we run the diagnosis engine (which currently expects global features).
                # To make it truly Zonal, we need to pass the zonal features. 
                # Since `build_decision_features` expects `inputs.veg_int`, we can mock it for the zone.
                import copy
                z_veg_int = copy.copy(inputs.veg_int)
                z_veg_int.curve = z_metric.get("curve", z_veg_int.curve)
                z_veg_int.phenology = z_metric.get("phenology", z_veg_int.phenology)
                
                z_features = build_decision_features(inputs.tensor, z_veg_int, inputs.context)
                z_diagnoses = self.diagnosis_engine.diagnose(z_features, inputs.context)
                
                area_pct = zones[z_id].get("area_pct", 0.0)
                
                for d in z_diagnoses:
                    # If probability is high enough to be a "hotspot" (e.g. > 50%)
                    if d.probability > 0.5:
                        if d.problem_id not in all_diagnoses:
                            all_diagnoses[d.problem_id] = d
                            all_diagnoses[d.problem_id].affected_area_pct = 0.0
                            all_diagnoses[d.problem_id].hotspot_zone_ids = []
                            
                        # Accumulate area and tag the zone
                        all_diagnoses[d.problem_id].affected_area_pct += area_pct
                        all_diagnoses[d.problem_id].hotspot_zone_ids.append(z_id)
                        
                        # Take the max severity across afflicted zones
                        if d.severity > all_diagnoses[d.problem_id].severity:
                            all_diagnoses[d.problem_id].severity = d.severity
        else:
            # Fallback to Global Plot Level
            global_diagnoses = self.diagnosis_engine.diagnose(global_features, inputs.context)
            for d in global_diagnoses:
                if d.probability > 0.5:
                    d.affected_area_pct = 100.0
                    d.hotspot_zone_ids = ["Plot-Wide"]
                    all_diagnoses[d.problem_id] = d
                    
        
        # Flatten deduced diagnoses back to list
        diagnosed_list = list(all_diagnoses.values())
        
        # 3. Policy Generation (Compliance + Feasibility)
        recommendations = self.policy_engine.generate_plan(
            diagnosed_list, 
            inputs.context, 
            inputs.weather_forecast,
            global_features.missing_inputs
        )
        
        # 4. Execution Graph Construction
        execution_plan = self._build_execution_plan(recommendations, diagnosed_list)
        
        # 5. Governance & Output Construction
        metrics = self._calculate_quality_metrics(global_features, diagnosed_list)
        audit = self._build_audit_trail(global_features, diagnosed_list)
        
        return DecisionOutput(
            run_id_l3=f"l3_{inputs.veg_int.run_id}",
            lineage={
                "l1_run_id": inputs.veg_int.layer1_run_id,
                "l2_run_id": inputs.veg_int.run_id
            },
            timestamp_utc=datetime.datetime.now(timezone.utc).isoformat(),
            
            diagnoses=diagnosed_list,
            recommendations=recommendations,
            execution_plan=execution_plan,
            
            quality_metrics=metrics,
            audit=audit
        )

    def _build_execution_plan(self, recs: List[Recommendation], diagnosed_list: List[Diagnosis]) -> ExecutionPlan:
        tasks = []
        edges = []
        
        # Filter strictly allowed actions for execution
        allowed_recs = [r for r in recs if r.is_allowed]
        
        # Map diagnoses for quick lookup
        diag_map = {d.problem_id: d for d in diagnosed_list}
        
        for i, r in enumerate(allowed_recs):
            
            # Extract target zones from linked diagnoses
            target_zones = []
            for d_id in r.linked_diagnosis_ids:
                if d_id in diag_map and hasattr(diag_map[d_id], 'hotspot_zone_ids'):
                    target_zones.extend(diag_map[d_id].hotspot_zone_ids)
            
            # Deduplicate zones
            target_zones = list(set(target_zones))
            
            # Create Task Node
            task = TaskNode(
                task_id=f"TASK_{r.action_id}",
                type=r.action_type,
                instructions=r.explain,
                required_inputs=r.blocked_reason, 
                completion_signal="MANUAL_CONFIRM", 
                depends_on=[],
                target_zones=target_zones,
                target_points=[]
            )
            tasks.append(task)
            
            # Simple sequencing: Verified fallbacks follow the primary (if primary was allowed? no, usually primary blocked)
            # If we have INTERVENE and VERIFY for same problem?
            # Implied: Verify first? 
            # For now, no complex edges unless explicitly linked.
            
            # Heuristic: If there is a Verify task and an Intervene task for same problem, Intervene depends on Verify.
            # But usually Policy Engine filters.
            
        return ExecutionPlan(
            tasks=tasks,
            edges=edges,
            recommended_start_date=datetime.datetime.now(timezone.utc).isoformat(),
            review_date=(datetime.datetime.now(timezone.utc) + datetime.timedelta(days=1)).isoformat()
        )

    def _calculate_quality_metrics(
        self, 
        feat: DecisionFeatures, 
        diagnoses: List
    ) -> QualityMetrics:
        
        # Degradation Mode
        from layer3_decision.schema import DegradationMode
        
        mode = DegradationMode.NORMAL
        if not feat.sar_available: mode = DegradationMode.NO_SAR
        if getattr(feat, 'low_sar_cadence', False): mode = DegradationMode.LOW_SAR_CADENCE
        if feat.optical_obs_count < 2: mode = DegradationMode.WEATHER_ONLY
        if not feat.sar_available and feat.optical_obs_count < 2: mode = DegradationMode.DATA_GAP
        
        # Reliability Score (Strict Data Quality)
        # Start at 1.0
        # Penalize Missing Drivers
        score = 1.0
        
        if not feat.rain_available: score -= 0.3
        if not feat.temp_available: score -= 0.1
        if not feat.sar_available: score -= 0.2
        if not feat.optical_available: score -= 0.3
        
        # Penalize Low Optical Count / High Uncertainty
        # (Using simple count proxy for now)
        if feat.optical_obs_count == 1: score -= 0.1
        
        # Bound
        score = max(0.0, score)
        
        # Link to Stage Confidence (L2 Interpretation Trust)
        # User said "Confidence from data quality only" but listed "L3 confidence" which usually includes L2 confidence.
        # But "Reliability" is usually system level. 
        # I'll multiply by stage_confidence as a final modifier, as L2 failure implies L3 failure.
        final_rel = score * feat.stage_confidence
        
        return QualityMetrics(
            decision_reliability=round(final_rel, 2),
            missing_drivers=feat.missing_inputs,
            data_completeness={
                "optical_obs_count": float(feat.optical_obs_count),
                "sar_obs_count": float(feat.sar_obs_count),
                "rain_available": 1.0 if feat.rain_available else 0.0,
                "sar_available": 1.0 if feat.sar_available else 0.0
            },
            l2_confidence_summary={"phenology_conf": feat.stage_confidence},
            degradation_mode=mode
        )

    def _build_audit_trail(self, feat: DecisionFeatures, diagnoses: List) -> AuditTrail:
        # Trace logs
        logs = []
        for d in diagnoses:
            logs.append({
                "hypothesis": d.problem_id,
                "prob": d.probability,
                "confidence": d.confidence,
                "evidence": [e.__dict__ for e in d.evidence_trace]
            })
            
        return AuditTrail(
            features_snapshot=feat.__dict__, # Frozen snapshot
            log_odds_table=logs,
            policy_checks=[] 
        )

# Singleton
_engine = DecisionIntelligenceEngine()

from orchestrator_v2.schema import OrchestratorInput

def run_layer3_decision(
    inputs: OrchestratorInput,
    tensor: FieldTensor, 
    veg_int: VegIntOutput
) -> DecisionOutput:
    
    # Map Context
    cc = inputs.crop_config
    oc = inputs.operational_context
    pc = inputs.policy_snapshot
    
    context = PlotContext(
        crop_type=cc.get("crop", "unknown"),
        variety=cc.get("variety"),
        planting_date=cc.get("planting_date", ""),
        irrigation_type=oc.get("irrigation_type", "rainfed"),
        management_goal=oc.get("management_goal", "yield_max"),
        constraints=oc.get("constraints", {})
    )
    
    # Weather Forecast (optional in operational context)
    weather_forecast = oc.get("weather_forecast", [])
    
    input_pack = DecisionInput(tensor, veg_int, context, weather_forecast)
    return _engine.run_decision_cycle(input_pack)
