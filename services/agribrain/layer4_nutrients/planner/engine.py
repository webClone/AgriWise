
from typing import Dict, Any, List, Optional
from services.agribrain.layer4_nutrients.schema import ExecutionPlan, Prescription, NutrientState, ActionId, TaskNode, Nutrient
from services.agribrain.layer3_decision.schema import TaskNode


class PlanningEngine:
    """
    Layer 4.6: Execution & Verification Planner (Locked v4.0 Hardened)
    Objective: Generate Operational DAG.
    """
    
    def create_plan(self, 
                    states: Dict[Nutrient, NutrientState], 
                    prescriptions: List[Prescription]) -> ExecutionPlan: # Required return
        
        tasks = []
        n_state = states.get(Nutrient.N)
        
        # 1. Verification Tasks
        needs_verification = False
        
        for rx in prescriptions:
            if rx.action_id == ActionId.VERIFY_ONLY:
                needs_verification = True
        
        if n_state and n_state.confidence < 0.6:
            needs_verification = True
            
        if needs_verification:
            t1 = TaskNode(
                task_id="TASK_VERIFY_SOIL_Sample",
                type="VERIFY",
                instructions="Collect soil samples (0-30cm) to verify N-nitrate levels.",
                required_inputs=["soil_lab_report"],
                completion_signal="UPLOAD_LAB_REPORT",
                depends_on=[]
            )
            tasks.append(t1)
            
        # 2. Intervention Tasks
        for rx in prescriptions:
            if rx.action_id in [ActionId.APPLY_N, ActionId.APPLY_P, ActionId.APPLY_K] and rx.is_allowed:
                 apply_task_id = f"TASK_{rx.action_id.value}_{rx.rate_kg_ha}"
                 
                 t_app = TaskNode(
                    task_id=apply_task_id,
                    type="INTERVENE",
                    instructions=f"Apply {rx.rate_kg_ha} kg/ha via {rx.method.value}",
                    required_inputs=["application_log"],
                    completion_signal="USER_CONFIRM",
                    depends_on=[] 
                 )
                 tasks.append(t_app)
                 
                 t_mon = TaskNode(
                    task_id=f"TASK_MONITOR_RESPONSE",
                    type="MONITOR",
                    instructions="Check spectral response 7-14 days post-app",
                    required_inputs=["satellite_ndvi"],
                    completion_signal="AUTOMATED_CHECK",
                    depends_on=[apply_task_id]
                 )
                 tasks.append(t_mon)

        # Always return plan object even if empty tasks, strict requirement
        return ExecutionPlan(
            tasks=tasks,
            edges=[],
            recommended_start_date="2025-06-15",
            review_date="2025-06-22"
        )
