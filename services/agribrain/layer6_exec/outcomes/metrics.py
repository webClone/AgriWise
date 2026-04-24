
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from services.agribrain.layer6_exec.schema import (
    OutcomeMetric, OutcomeMetricId, CausalMethod, ExecutionState, TaskStatus
)
from services.agribrain.layer3_decision.schema import TaskNode

def _mean(vals: List[float]) -> float:
    if not vals: return 0.0
    return sum(vals) / len(vals)

def compute_outcomes(
    state: ExecutionState,
    completed_tasks: List[TaskNode],
    l1_timeseries: List[Dict[str, Any]],
    l3_confounders: List[str] # From L3 diagnosis or L5 threats
) -> List[OutcomeMetric]:
    """
    Evaluate success of COMPLETED interventions.
    """
    out = []
    
    # 1. Filter for Interventions
    interventions = [t for t in completed_tasks if "INTERVENE" in str(t.type)]
    
    for task in interventions:
        # Determine execution date from logs
        exec_dt = datetime.now(timezone.utc) # Fallback
        
        for log in reversed(state.logs):
            msg = log.get("msg", "")
            # Look for standard completion message from dag_runner or similar
            if f"Task {task.task_id} -> COMPLETED" in msg:
                ts = log.get("ts")
                if ts:
                    # Handle typical ISO formats
                    try:
                        exec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except:
                        pass
                    break

        
        # 2. Define Windows (Pre: -14 to -1, Post: +1 to +14)
        pre_start = (exec_dt - timedelta(days=14)).date().isoformat()
        pre_end = (exec_dt - timedelta(days=1)).date().isoformat()
        
        post_start = (exec_dt + timedelta(days=1)).date().isoformat()
        post_end = (exec_dt + timedelta(days=14)).date().isoformat()
        
        # 3. Extract Signals
        pre_ndvi = []
        post_ndvi = []
        
        for record in l1_timeseries:
            d = record.get("date", "")
            val = record.get("ndvi_smoothed")
            if val is None: continue
            
            if pre_start <= d <= pre_end:
                pre_ndvi.append(float(val))
            elif post_start <= d <= post_end:
                post_ndvi.append(float(val))
        
        if not pre_ndvi or not post_ndvi:
            continue # Insufficient data
            
        # 4. Compute Delta (Simple Pre-Post)
        delta = _mean(post_ndvi) - _mean(pre_ndvi)
        
        # 5. Check Confounders (Did it rain? Was there a heatwave?)
        # Only simple check for now
        c_list = []
        for cf in l3_confounders:
            c_list.append(cf)
            
        # DYNAMIC CONFOUNDER CHECK: Rain in Evaluation Window?
        # If recovering NDVI but also raining, it might just be green-up from rain, not the intervention.
        rain_event = False
        for record in l1_timeseries:
            d = record.get("date", "")
            r = record.get("rain", 0.0)
            if post_start <= d <= post_end and r and float(r) > 20.0:
                 rain_event = True
                 break
        
        if rain_event:
            c_list.append("EVAL_WINDOW_RAIN_EVENT")
            
        confidence = 0.5 # Default Pre-Post
        if len(c_list) > 0:
            confidence = 0.3 # Confounded
            
        out.append(OutcomeMetric(
            metric_id=OutcomeMetricId.NDVI_RECOVERY,
            delta_value=delta,
            confidence=confidence,
            method=CausalMethod.PRE_POST,
            baseline_window={"start": pre_start, "end": pre_end},
            eval_window={"start": post_start, "end": post_end},
            confounders_present=c_list
        ))
        
    return out
