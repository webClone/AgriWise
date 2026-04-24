
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from services.agribrain.layer6_exec.schema import (
    Layer6Input, Layer6Output, RunMeta, QualityMetricsL6, AuditSnapshot,
    ExecutionState, TaskStatus, OperationalContext
)
from services.agribrain.layer3_decision.schema import Driver, DegradationMode, ExecutionPlan

# Engines
from services.agribrain.layer6_exec.evidence.normalizer import normalize_evidence_batch
from services.agribrain.layer6_exec.execution.dag_runner import update_execution_state
from services.agribrain.layer6_exec.outcomes.metrics import compute_outcomes
from services.agribrain.layer6_exec.governance.calibration import propose_calibration

CODE_VERSION = "6.0.0"

def _stable_hash(obj: Dict[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]

def run_layer6(inputs: Layer6Input) -> Layer6Output:
    """
    Research-Grade Layer 6 Execution Loop.
    """
    ts_now = datetime.now(timezone.utc).isoformat()
    
    # 1. Normalize Evidence
    plot_id = inputs.tensor.plot_id if hasattr(inputs.tensor, "plot_id") else "UNKNOWN"
    norm_evidence = normalize_evidence_batch(inputs.evidence_batch, plot_id)
    
    # 2. Execute DAG (State Transition)
    # Phase 11 SPATIAL EXTENSION: Consolidate execution plans from all modules (L3, L4, L5)
    global_tasks = []
    
    if inputs.decision_l3 and hasattr(inputs.decision_l3, "execution_plan"):
        if inputs.decision_l3.execution_plan:
            global_tasks.extend(inputs.decision_l3.execution_plan.tasks)
            
    if hasattr(inputs, "nutrient_l4") and inputs.nutrient_l4 and hasattr(inputs.nutrient_l4, "verification_plan"):
        if inputs.nutrient_l4.verification_plan:
            global_tasks.extend(inputs.nutrient_l4.verification_plan.tasks)
            
    if hasattr(inputs, "bio_l5") and inputs.bio_l5 and hasattr(inputs.bio_l5, "execution_plan"):
        if inputs.bio_l5.execution_plan:
            global_tasks.extend(inputs.bio_l5.execution_plan.tasks)
            
    unified_plan = ExecutionPlan(
        tasks=global_tasks, 
        edges=[], 
        recommended_start_date=ts_now, 
        review_date=ts_now
    )
    
    new_state = update_execution_state(
        plan=unified_plan,
        current_state=inputs.current_state,
        op_context=inputs.op_context,
        normalized_evidence=norm_evidence,
        current_time=ts_now
    )
    
    # 3. Outcome Scoring
    # Needs L1 timeseries
    # Needs completed tasks
    completed = []
    if unified_plan and unified_plan.tasks:
        for t in unified_plan.tasks:
            if new_state.tasks.get(t.task_id) == TaskStatus.COMPLETED:
                completed.append(t)
    
    l1_ts = inputs.tensor.plot_timeseries if hasattr(inputs.tensor, "plot_timeseries") else []
    confounders = [] # Extract from L3/L4/L5 if needed
    
    outcomes = compute_outcomes(new_state, completed, l1_ts, confounders)
    
    # 4. Learning Loop (Calibration)
    proposals = propose_calibration(norm_evidence, {})
    
    # 5. Deterministic ID
    parent_ids = {
        "L1": getattr(inputs.tensor, "run_id", ""),
        "L3": getattr(getattr(inputs.decision_l3, "run_meta", None), "run_id", getattr(inputs.decision_l3, "run_id_l3", "")),
        "PrevState": _stable_hash(asdict(inputs.current_state))
    }
    
    run_hash = _stable_hash({
        "parents": parent_ids,
        "evidence_digest": _stable_hash([asdict(e) for e in norm_evidence]),
        "code": CODE_VERSION
    })
    run_id = f"L6-{run_hash}"
    
    # 6. Metrics & Audit
    quality = QualityMetricsL6(
        decision_reliability=1.0,
        missing_drivers=[],
        data_completeness={},
        task_completion_rate=0.0 # Calculate real rate
    )
    
    audit = AuditSnapshot(
        features_snapshot={},
        policy_snapshot={},
        model_versions={"exec": CODE_VERSION}
    )
    
    run_meta = RunMeta(
        run_id=run_id,
        parent_run_ids=parent_ids,
        generated_at=ts_now,
        degradation_mode=DegradationMode.NORMAL
    )
    
    return Layer6Output(
        run_meta=run_meta,
        updated_state=new_state,
        evidence_registry=norm_evidence,
        outcome_report=outcomes,
        calibration_proposals=proposals,
        quality_metrics=quality,
        audit=audit
    )

from services.agribrain.orchestrator_v2.schema import OrchestratorInput
from services.agribrain.layer5_bio.schema import BioThreatIntelligenceOutput

def run_layer6_exec(inputs: OrchestratorInput, *args) -> Layer6Output:
    # DEBUG: Inspect args matching
    # Map args assuming order: tensor, veg_int, decision_l3, nutrient_l4, bio_l5
    tensor = args[0] if len(args) > 0 else None
    veg_int = args[1] if len(args) > 1 else None
    decision_l3 = args[2] if len(args) > 2 else None
    nutrient_l4 = args[3] if len(args) > 3 else None
    bio_l5 = args[4] if len(args) > 4 else None

    # Map Inputs to Layer6Input object
    current_state_dict = inputs.operational_context.get("current_state", {})
    current_state = ExecutionState(
        tasks={},
        logs=[],
        last_updated=""
    )
    
    op = inputs.operational_context
    resources = op.get("resources", {})
    constraints = op.get("constraints", {})
    
    l6_in = Layer6Input(
        current_state=current_state,
        op_context=OperationalContext(
            equipment_ids=resources.get("equipment", []),
            workforce_available=resources.get("workforce", True),
            water_quota_remaining=constraints.get("water_quota", 1000.0),
            budget_remaining=constraints.get("budget", 1000.0),
            permissions=[]
        ),
        evidence_batch=[], 
        decision_l3=decision_l3,
        tensor=tensor,
        nutrient_l4=nutrient_l4,
        bio_l5=bio_l5,
        veg_int=veg_int
    )
    
    return run_layer6(l6_in)
