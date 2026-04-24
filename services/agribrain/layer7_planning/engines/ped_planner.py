from datetime import timezone
from typing import List, Tuple
from services.agribrain.layer7_planning.schema import CropOptionEvaluation, PlanningDecisionId, PlanningRecommendation
from services.agribrain.layer3_decision.schema import TaskNode, ExecutionPlan

def generate_execution_plan(option: CropOptionEvaluation, plot_id: str) -> Tuple[PlanningRecommendation, ExecutionPlan]:
    """
    Engine H: Planner & Execution DAG Builder (PED)
    Converts option feasibility down into actionable DAG commands and final recommendation.
    """
    tasks: List[TaskNode] = []
    
    is_allowed = True
    blocked_reason = None
    decision_id = PlanningDecisionId.PLANT_NOW
    preconditions = []
    
    # 1. Gating Logic (Strict Rules)
    if option.window.severity == "CRITICAL" or option.window.probability_ok < 0.2:
        is_allowed = False
        decision_id = PlanningDecisionId.DELAY_PLANTING if option.window.probability_ok < 0.2 else PlanningDecisionId.SWITCH_CROP
        blocked_reason = "Out of acceptable planting window constraint."
        
    if option.water.severity == "CRITICAL" or option.water.probability_ok < 0.3:
        is_allowed = False
        decision_id = PlanningDecisionId.SWITCH_CROP
        blocked_reason = "Severe water availability constraint detected."
        
    if option.soil.severity == "CRITICAL":
        decision_id = PlanningDecisionId.DELAY_PLANTING
        blocked_reason = "Soil currently unworkable (compaction or moisture risk). Wait for optimal conditions."
        is_allowed = False

    if option.econ.expected_profit < 0:
        is_allowed = False
        decision_id = PlanningDecisionId.SWITCH_CROP
        blocked_reason = f"Negative expected profit margin at target yield (Break-even: {option.econ.break_even_yield}t/ha)."

    # 2. DAG Generation (if allowed or delayed)
    if decision_id in [PlanningDecisionId.PLANT_NOW, PlanningDecisionId.DELAY_PLANTING]:
        
        # Base Verification (Always required before heavy ops)
        v_temp = TaskNode(
            task_id=f"verify_temp_{option.crop}",
            type="VERIFY",
            instructions=f"Verify soil temperature at 10cm is above {option.crop} minimum threshold.",
            required_inputs=["L1_WEATHER", "SENSOR_OBY"],
            completion_signal="SENSOR_READING",
            depends_on=[]
        )
        tasks.append(v_temp)
        preconditions.append("Soil Temp Verified")
        
        v_traffic = TaskNode(
            task_id=f"verify_traffic_{option.crop}",
            type="VERIFY",
            instructions="Verify soil moisture allows for machinery traffic without compaction.",
            required_inputs=["L1_SAR", "VISUAL_OBS"],
            completion_signal="USER_CONFIRM",
            depends_on=[]
        )
        tasks.append(v_traffic)
        preconditions.append("Soil Trafficability Verified")
        
        # Contingency/Risk Verification
        deps = [v_temp.task_id, v_traffic.task_id]
        
        if option.biotic.severity in ["MODERATE", "CRITICAL"]:
            v_disease = TaskNode(
                task_id=f"prep_fungicide_{option.crop}",
                type="INTERVENE",
                instructions="Secure broad-spectrum fungicide due to elevated biotic risk forecast.",
                required_inputs=["L5_BIOTIC"],
                completion_signal="USER_CONFIRM",
                depends_on=[]
            )
            tasks.append(v_disease)
            deps.append(v_disease.task_id)
            preconditions.append("Fungicide Protocol Ready")

        if option.water.probability_ok < 0.7:
             v_irrigation = TaskNode(
                 task_id=f"verify_irrigation_{option.crop}",
                 type="VERIFY",
                 instructions="Verify irrigation system is fully operational and quota available before planting.",
                 required_inputs=["FARM_RECORD"],
                 completion_signal="USER_CONFIRM",
                 depends_on=[]
             )
             tasks.append(v_irrigation)
             deps.append(v_irrigation.task_id)
             preconditions.append("Irrigation Confirmed")

        # Action: Prep & Plant
        prep_seedbed = TaskNode(
            task_id=f"prep_seedbed_{option.crop}",
            type="INTERVENE",
            instructions=f"Prepare seedbed (tillage/ridging) for {option.crop}.",
            required_inputs=[],
            completion_signal="USER_CONFIRM",
            depends_on=deps # Waits for all verifications
        )
        tasks.append(prep_seedbed)
        
        plant_crop = TaskNode(
            task_id=f"plant_{option.crop}",
            type="INTERVENE",
            instructions=f"Plant {option.crop}.",
            required_inputs=["SEED_RECORD"],
            completion_signal="USER_CONFIRM",
            depends_on=[prep_seedbed.task_id]
        )
        tasks.append(plant_crop)
        
        monitor = TaskNode(
             task_id=f"monitor_{option.crop}",
             type="VERIFY",
             instructions=f"Monitor early emergence uniformity in 14 days.",
             required_inputs=["L2_PHENOLOGY"],
             completion_signal="OBSERVATION",
             depends_on=[plant_crop.task_id]
        )
        tasks.append(monitor)

    risk_if_wrong = (
        "Suboptimal yield and massive financial loss relative to production costs if planted into frost, "
        "drought, or outside the calendar window."
    )
    
    rec = PlanningRecommendation(
        decision_id=decision_id,
        crop=option.crop,
        is_allowed=is_allowed,
        blocked_reason=blocked_reason,
        risk_if_wrong=risk_if_wrong,
        preconditions=preconditions
    )
    
    # Generate mock edges (straight line DAG from depends_on)
    edges = []
    for t in tasks:
        for d in t.depends_on:
            edges.append({"from": d, "to": t.task_id})
            
    import datetime
    now_str = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%d")
    plan = ExecutionPlan(
        tasks=tasks, 
        edges=edges, 
        recommended_start_date=now_str, 
        review_date=now_str
    )
    
    return rec, plan
