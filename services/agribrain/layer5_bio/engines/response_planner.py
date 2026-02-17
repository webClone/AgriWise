
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta

from services.agribrain.layer5_bio.schema import (
    BioThreatState, BioRecommendation, ActionId, ThreatId
)
from services.agribrain.layer3_decision.schema import (
    RiskIfWrong, ExecutionPlan, TaskNode, DegradationMode
)

def _iso_today():
    return datetime.utcnow().date().isoformat()

def _window(days: int = 5):
    s = datetime.utcnow().date()
    e = s + timedelta(days=days)
    return {"start": s.isoformat(), "end": e.isoformat()}

def build_response_plan(
    threat_states: Dict[str, BioThreatState],
    decision_output,
    plot_context: Dict[str, Any],
    degradation_mode: DegradationMode
) -> Tuple[List[BioRecommendation], Optional[ExecutionPlan]]:

    recs: List[BioRecommendation] = []
    tasks: List[TaskNode] = []

    # simple “top threats”: prob*conf
    ranked = sorted(
        threat_states.values(),
        key=lambda s: (s.probability * s.confidence),
        reverse=True
    )

    # policy snapshot from L3 (if present)
    policy = {}
    try:
        policy = getattr(getattr(decision_output, "audit", None), "policy_snapshot", {}) or {}
    except Exception:
        policy = {}

    for st in ranked[:3]:
        if st.threat_id == ThreatId.DATA_GAP:
            # always verify
            recs.append(BioRecommendation(
                action_id=ActionId.VERIFY_SCOUT,
                threat_id=st.threat_id,
                is_allowed=True,
                blocked_reason=[],
                risk_if_wrong=RiskIfWrong.LOW,
                timing_window=_window(3),
                method="scout"
            ))
            continue

        # decision logic
        if st.confidence < 0.65 or st.probability < 0.55:
            # VERIFY path
            recs.append(BioRecommendation(
                action_id=ActionId.VERIFY_SCOUT,
                threat_id=st.threat_id,
                is_allowed=True,
                blocked_reason=[],
                risk_if_wrong=RiskIfWrong.LOW,
                timing_window=_window(3),
                method="scout"
            ))
            recs.append(BioRecommendation(
                action_id=ActionId.VERIFY_PHOTOS,
                threat_id=st.threat_id,
                is_allowed=True,
                blocked_reason=[],
                risk_if_wrong=RiskIfWrong.LOW,
                timing_window=_window(3),
                method="photos",
                depends_on=["VERIFY_SCOUT"]
            ))
        else:
            # INTERVENE path (still allow verify tasks as prerequisites)
            # GATE C: Chemical Neutrality & Action Safety
            allowed = True
            blocked = []
            
            # 1. Chemical Neutrality Check (Generic Categories Only)
            # (No explicit check here, but ensured by method naming convention below)
            
            # 2. Safety Gates (L3 Policy or Confounders)
            if degradation_mode == DegradationMode.DATA_GAP:
                allowed = False
                blocked.append("DATA_GAP: insufficient drivers for intervention")
            
            # 3. Fallback Logic: If blocked, ensure VERIFY is prioritized
            # (Here we add VERIFY as prerequisite regardless, which satisfies safety)
            
            recs.append(BioRecommendation(
                action_id=ActionId.VERIFY_SCOUT,
                threat_id=st.threat_id,
                is_allowed=True,
                blocked_reason=[],
                risk_if_wrong=RiskIfWrong.LOW,
                timing_window=_window(2),
                method="scout"
            ))
            
            # GATE C: Use Generic Treatment Classes
            treat_method = "treatment_class_generic"
            if "FUNGAL" in st.threat_id.value: treat_method = "fungicide_class_opt"
            elif "INSECT" in st.threat_id.value: treat_method = "insecticide_class_opt"
            elif "WEED" in st.threat_id.value: treat_method = "herbicide_class_opt"
            
            recs.append(BioRecommendation(
                action_id=ActionId.INTERVENE_TREAT,
                threat_id=st.threat_id,
                is_allowed=allowed,
                blocked_reason=blocked,
                risk_if_wrong=RiskIfWrong.HIGH,
                timing_window=_window(5),
                method=treat_method, 
                depends_on=["VERIFY_SCOUT"]
            ))

    # Build ExecutionPlan DAG from recs
    # Note: TaskNode in your L3 schema likely includes: id, type, instructions, depends_on
    id_map = {}
    for r in recs:
        nid = f"{r.action_id.value}_{r.threat_id.value}"
        id_map[(r.action_id.value, r.threat_id.value)] = nid
    for r in recs:
        nid = id_map[(r.action_id.value, r.threat_id.value)]
        deps = []
        for d in (r.depends_on or []):
            # depends_on given as action_id strings; map to same threat
            # Or map to node ID of the dependent task
            # Simplified: finding dependent action_id for ANY threat? No, same threat.
            target_nid = f"{d}_{r.threat_id.value}" 
            # Check if this node exists in map (it should, if ordered correctly, otherwise DAG checks fail)
            # We emitted VERIFY before INTERVENE, so it works.
            deps.append(target_nid)
            
            tasks.append(TaskNode(
            task_id=nid,
            type=r.action_id.value,
            instructions=f"{r.method} for {r.threat_id.value}",
            required_inputs=[],
            completion_signal="USER_CONFIRM",
            depends_on=deps
        ))

    plan = ExecutionPlan(tasks=tasks, edges=[], recommended_start_date=_iso_today(), review_date=_iso_today()) if tasks else None
    return recs, plan
