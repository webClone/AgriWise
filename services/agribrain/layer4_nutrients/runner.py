
import hashlib
import json
from typing import Dict, Any
from datetime import datetime

from services.agribrain.layer1_fusion.schema import FieldTensor
from services.agribrain.layer2_veg_int.schema import VegIntOutput
from services.agribrain.layer3_decision.schema import DecisionOutput, PlotContext, DegradationMode

from services.agribrain.layer4_nutrients.schema import (
    NutrientIntelligenceOutput, RunMeta, QualityMetricsL4, AuditSnapshot, ParentRunIds, Nutrient
)

from services.agribrain.layer4_nutrients.soil_water_balance.engine import SoilWaterBalanceEngine
from services.agribrain.layer4_nutrients.crop_demand.engine import CropDemandUptakeEngine
from services.agribrain.layer4_nutrients.proxies.engine import NutrientObservationProxyEngine
from services.agribrain.layer4_nutrients.inference.engine import NutrientInferenceEngine
from services.agribrain.layer4_nutrients.optimization.engine import OptimizationEngine
from services.agribrain.layer4_nutrients.planner.engine import PlanningEngine

L4_CODE_VERSION = "4.0.0"
ENGINE_VERSIONS = {
    "swb": "1.0.0",
    "cdu": "1.0.0",
    "proxies": "1.0.0",
    "inference": "4.0.0",
    "optimization": "4.0.0",
    "planner": "4.0.0"
}

def _generate_deterministic_run_id(
    plot_id: str, 
    l1_id: str, 
    l2_id: str, 
    l3_id: str, 
    policy_snapshot: Dict[str, Any]
) -> str:
    """
    Generates a deterministic hash for reproducibility.
    """
    # Canonical string representation of policy
    policy_str = json.dumps(policy_snapshot, sort_keys=True)
    
    raw = f"{plot_id}|{l1_id}|{l2_id}|{l3_id}|{policy_str}|{L4_CODE_VERSION}"
    hash_obj = hashlib.sha256(raw.encode("utf-8"))
    return f"L4-{hash_obj.hexdigest()[:12]}"

from services.agribrain.orchestrator_v2.schema import OrchestratorInput

def run_layer4_nutrients(
    inputs: OrchestratorInput,
    tensor: FieldTensor,
    veg_int: VegIntOutput,
    decision_l3: DecisionOutput
) -> NutrientIntelligenceOutput:
    
    # Map Context
    cc = inputs.crop_config
    oc = inputs.operational_context
    
    context = PlotContext(
        crop_type=cc.get("crop", "unknown"),
        variety=cc.get("variety"),
        planting_date=cc.get("planting_date", ""),
        irrigation_type=oc.get("irrigation_type", "rainfed"),
        management_goal=oc.get("management_goal", "yield_max"),
        constraints=oc.get("constraints", {})
    )
    """
    Layer 4 Orchestrator (Locked v4.0 Hardened)
    """
    
    # Instantiate Engines
    swb_engine = SoilWaterBalanceEngine()
    cdu_engine = CropDemandUptakeEngine()
    nop_engine = NutrientObservationProxyEngine()
    nie_engine = NutrientInferenceEngine()
    opt_engine = OptimizationEngine()
    plan_engine = PlanningEngine()
    
    # 1. SWB
    swb_out = swb_engine.run(tensor, context)
    
    # 2. CDU
    demands = cdu_engine.compute_demand(veg_int.phenology, context)
    
    # 3. Proxies
    evidence = nop_engine.extract_features(tensor, veg_int)
    
    # 4. Inference
    states = nie_engine.infer_states(evidence, swb_out, demands, decision_l3)
    
    # 5. Optimization
    prescriptions = opt_engine.optimize(states, swb_out, context)
    
    # 6. Planning
    execution_plan = plan_engine.create_plan(states, prescriptions)
    
    # 7. Quality & Audit
    metrics = QualityMetricsL4(
        decision_reliability=states[Nutrient.N].confidence if Nutrient.N in states else 0.0,
        missing_drivers=[],
        data_completeness={},
        penalties_applied=[]
    )
    
    audit = AuditSnapshot(
        features_snapshot={"swb": swb_out, "proxies": evidence},
        policy_snapshot=context.constraints,
        model_versions=ENGINE_VERSIONS
    )
    
    parent_ids = ParentRunIds(l1=tensor.run_id, l2=veg_int.run_id, l3=decision_l3.run_id_l3)
    
    # Deterministic Run ID
    run_id = _generate_deterministic_run_id(
        tensor.plot_id, 
        tensor.run_id, 
        veg_int.run_id, 
        decision_l3.run_id_l3, 
        context.constraints
    )
    
    meta = RunMeta(
        layer="L4",
        run_id=run_id,
        parent_run_ids=parent_ids,
        generated_at=datetime.utcnow().isoformat() + "Z",
        degradation_mode=DegradationMode.NORMAL
    )
    
    return NutrientIntelligenceOutput(
        run_meta=meta,
        nutrient_states=states,
        prescriptions=prescriptions,
        verification_plan=execution_plan,
        quality_metrics=metrics,
        audit=audit
    )
