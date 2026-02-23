
import datetime
from typing import List, Dict, Any

from services.agribrain.layer1_fusion.schema import FieldTensor
from services.agribrain.layer3_decision.schema import (
    DecisionInput, DecisionOutput, PlotContext, 
    ExecutionPlan, TaskNode, QualityMetrics, AuditTrail, Recommendation
)
from services.agribrain.layer3_decision.features.builder import build_decision_features, DecisionFeatures
from services.agribrain.layer3_decision.diagnosis.inference import DiagnosisEngine
from services.agribrain.layer3_decision.policy.policies import PolicyEngine

class DecisionIntelligenceEngine:
    
    def __init__(self):
        self.diagnosis_engine = DiagnosisEngine()
        self.policy_engine = PolicyEngine()
        
    def run_decision_cycle(self, inputs: DecisionInput) -> DecisionOutput:
        """
        Orchestrates the Research-Grade decision loop.
        """
        
        # 1. Feature Engineering
        features = build_decision_features(inputs.tensor, inputs.veg_int, inputs.context)
        
        # 2. Diagnosis (Probabilistic + Trace)
        diagnoses = self.diagnosis_engine.diagnose(features, inputs.context)
        
        # 3. Policy Generation (Compliance + Feasibility)
        recommendations = self.policy_engine.generate_plan(
            diagnoses, 
            inputs.context, 
            inputs.weather_forecast,
            features.missing_inputs
        )
        
        # 4. Execution Graph Construction
        execution_plan = self._build_execution_plan(recommendations)
        
        # 5. Governance & Output Construction
        metrics = self._calculate_quality_metrics(features, diagnoses)
        audit = self._build_audit_trail(features, diagnoses)
        
        return DecisionOutput(
            run_id_l3=f"l3_{inputs.veg_int.run_id}",
            lineage={
                "l1_run_id": inputs.veg_int.layer1_run_id,
                "l2_run_id": inputs.veg_int.run_id
            },
            timestamp_utc=datetime.datetime.utcnow().isoformat(),
            
            diagnoses=diagnoses,
            recommendations=recommendations,
            execution_plan=execution_plan,
            
            quality_metrics=metrics,
            audit=audit
        )

    def _build_execution_plan(self, recs: List[Recommendation]) -> ExecutionPlan:
        tasks = []
        edges = []
        
        # Filter strictly allowed actions for execution
        allowed_recs = [r for r in recs if r.is_allowed]
        
        for i, r in enumerate(allowed_recs):
            # Create Task Node
            task = TaskNode(
                task_id=f"TASK_{r.action_id}",
                type=r.action_type,
                instructions=r.explain,
                required_inputs=r.blocked_reason, # Should be empty if allowed, but maybe drivers?
                completion_signal="MANUAL_CONFIRM", # Placeholder
                depends_on=[] # Flat DAG for now, logic to be expanded if sequence needed
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
            recommended_start_date=datetime.datetime.utcnow().isoformat(),
            review_date=(datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat()
        )

    def _calculate_quality_metrics(
        self, 
        feat: DecisionFeatures, 
        diagnoses: List
    ) -> QualityMetrics:
        
        # Degradation Mode
        from services.agribrain.layer3_decision.schema import DegradationMode
        
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

from services.agribrain.orchestrator_v2.schema import OrchestratorInput

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
