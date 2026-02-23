import logging
from datetime import datetime
from typing import Dict, Any, List

from services.agribrain.orchestrator_v2.schema import LayerResult, OrchestratorInput, GlobalDegradation
from services.agribrain.layer3_decision.schema import ExecutionPlan
from services.agribrain.layer7_planning.schema import Layer7Output, CropOptionEvaluation

# 8 Engines
from services.agribrain.layer7_planning.engines.ccl_crop_library import get_crop_profile
from services.agribrain.layer7_planning.engines.pwe_planting_window import compute_planting_window
from services.agribrain.layer7_planning.engines.ste_seedbed import compute_soil_workability
from services.agribrain.layer7_planning.engines.wfe_water_feasibility import compute_water_feasibility
from services.agribrain.layer7_planning.engines.brf_biotic_risk import compute_biotic_risk
from services.agribrain.layer7_planning.engines.yve_yield_distribution import compute_yield_distribution
from services.agribrain.layer7_planning.engines.eoe_economics import compute_economics
from services.agribrain.layer7_planning.engines.ped_planner import generate_execution_plan

logger = logging.getLogger(__name__)

def run(inputs: OrchestratorInput, l1_res: Any, l5_res: Any = None, chat_memory = None) -> Any:
    """
    Layer 7: Season Planning, Crop Suitability & Economics Intelligence (v7.0)
    Aggregates all 8 probabilistic engines.
    """
    logger.info("[Layer 7] Running advanced Planning Engine...")
    
    # 0. Deterministic Hashing (skipping logic for brevity of this module structure)
    run_meta = {
        "run_id": "L7_RUN_PENDING",
        "timestamp_utc": datetime.utcnow().isoformat(),
    }
    
    # 1. Inputs Gathering
    raw_crop = inputs.crop_config.get("crop")
    target_crop = (raw_crop or "potato").lower().strip()
    if target_crop == "unknown":
        target_crop = "potato"
        
    current_date = datetime.strptime(inputs.date_range["end"], "%Y-%m-%d")
    l1_out = l1_res
    l5_out = l5_res
        
    soil_texture = "unknown"
    irrigation_type = "unknown"
    if chat_memory and chat_memory.known_context:
        soil_texture = chat_memory.known_context.get("soil_type", "unknown")
        irrigation_type = chat_memory.known_context.get("irrigation_type", "unknown")
        
    # 2. Candidate Evaluation Loop (MVP: Evaluating just the target crop, could expand later)
    options: List[CropOptionEvaluation] = []
    
    # Engine A: CCL
    profile = get_crop_profile(target_crop)
    if not profile:
        return LayerResult(
            layer_id="L7",
            status="WARNING",
            message=f"No CCL profile for {target_crop}",
            output=None,
            errors=[f"Crop {target_crop} unsupported in library."]
        )
        
    # Engine B: PWE
    window_state = compute_planting_window(current_date, profile, l1_out)
    
    # Engine C: STE
    soil_state = compute_soil_workability(profile, l1_out, soil_texture)
    
    # Engine D: WFE
    water_state = compute_water_feasibility(profile, l1_out, irrigation_type)
    
    # Engine E: BRF
    biotic_state = compute_biotic_risk(profile, l1_out, l5_out, chat_memory)
    
    # Engine F: YVE
    yield_dist = compute_yield_distribution(profile, window_state, water_state, biotic_state)
    
    # Engine G: EOE
    # user_context dict to fetch localized prices
    user_context = {} 
    econ_outcome = compute_economics(profile, yield_dist, user_context)
    
    # 3. Overall Rank Score Synthesis 
    # w1*expected_profit + w2*profit_p10 + w3*window_probability - penalty
    score = (econ_outcome.expected_profit * 0.4) + (econ_outcome.profit_p10 * 0.3) + (window_state.probability_ok * 1000)
    if window_state.severity == "CRITICAL" or water_state.severity == "CRITICAL":
         score -= 5000
    if soil_state.severity == "CRITICAL":
         score -= 2000
         
    opt_eval = CropOptionEvaluation(
        crop=profile.display_name,
        window=window_state,
        soil=soil_state,
        water=water_state,
        biotic=biotic_state,
        yield_dist=yield_dist,
        econ=econ_outcome,
        overall_rank_score=round(score, 2)
    )
    options.append(opt_eval)
    
    # Engine H: PED
    # Convert best option into DAG
    # Deterministic sort for run_id stability (Rank first, then Crop ASCII)
    options.sort(key=lambda o: (o.overall_rank_score, o.crop), reverse=True)
    best_opt = options[0]
    rec, dag = generate_execution_plan(best_opt, inputs.plot_id)
    
    # Bundle Final Output Layer Result
    l7_output = Layer7Output(
        run_meta=run_meta,
        options=options,
        chosen_plan=rec,
        quality_metrics={
            "global_confidence": str(min([best_opt.window.probability_ok, best_opt.soil.probability_ok, best_opt.water.probability_ok, best_opt.biotic.probability_ok]))
        },
        audit_snapshot={
            "derived_DAG_length": len(dag.tasks),
            "economic_inputs": user_context
         }
    )
    
    # We duck-type the execution plan onto layer result so global merge knows where to pull from
    # Since RunArtifact treats L6/L7 differently
    logger.info(f"[Layer 7] Plan derived: {rec.decision_id} tasks: {len(dag.tasks)}")
    
    # Pack DAG into standard LayerResult container schema
    l7_output.execution_plan = dag
    return l7_output
