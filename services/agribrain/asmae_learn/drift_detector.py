from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from asmae_learn.model_registry import ModelRegistry

DRIFT_THRESHOLDS = {
    "vigor": 0.25,
    "canopy_water_response": 0.25,  # also check canopy_water
    "canopy_water": 0.25,
    "salinity_stress": 0.20,
    "biotic_confounder": 0.30,
    "lai": 0.30,
    "chlorophyll": 0.25
}

DEFAULT_DRIFT_THRESHOLD = 0.35

def check_model_drift(
    model_id: str,
    variable: str,
    evaluations: List[Dict[str, Any]],
    ledger_path: Optional[Path] = None
) -> Optional[str]:
    """Check for model prediction drift.
    
    Each evaluation should contain:
      - plot_id
      - predicted_value
      - actual_value
    """
    if len(evaluations) < 3:
        # Minimum sample count not met
        return "insufficient_samples"

    threshold = DRIFT_THRESHOLDS.get(variable, DEFAULT_DRIFT_THRESHOLD)
    
    # Calculate MAE per plot
    plot_errors: Dict[str, List[float]] = {}
    for ev in evaluations:
        p_id = ev.get("plot_id", "default")
        pred = ev.get("predicted_value", 0.0)
        act = ev.get("actual_value", 0.0)
        err = abs(pred - act)
        plot_errors.setdefault(p_id, []).append(err)
        
    plot_maes = {pid: sum(errs)/len(errs) for pid, errs in plot_errors.items()}
    drifting_plots = [pid for pid, mae in plot_maes.items() if mae > threshold]
    
    # Overall MAE
    all_errors = [abs(ev["predicted_value"] - ev["actual_value"]) for ev in evaluations]
    overall_mae = sum(all_errors) / len(all_errors)
    
    action = None
    reason = ""
    
    # Check for critical contradiction (e.g. error spike > 0.6)
    max_error = max(all_errors) if all_errors else 0.0
    if max_error > 0.60:
        action = "revoke"
        reason = f"critical_drift_spike: max_error={max_error:.2f}"
    elif len(drifting_plots) == 1:
        action = "quarantine"
        reason = f"plot_level_quarantine: plots={drifting_plots}"
    elif len(drifting_plots) >= 2 or overall_mae > threshold:
        action = "demote"
        reason = f"global_drift_detected: overall_mae={overall_mae:.2f} > threshold={threshold} drifting_plots={drifting_plots}"
        
    if action:
        # Perform Model Registry demotion/revocation if applicable
        try:
            manifest = ModelRegistry.load_manifest(model_id)
            current_status = manifest.get("status", "candidate")
            
            if action == "revoke":
                ModelRegistry.transition_status(model_id, "revoked")
            elif action == "demote":
                # transition from approved to shadow/evaluation
                if current_status == "approved_shadow_expert":
                    ModelRegistry.transition_status(model_id, "evaluation", metrics={"mae": overall_mae})
                elif current_status == "evaluation":
                    ModelRegistry.transition_status(model_id, "shadow")
        except Exception:
            pass
            
        # Write audit log to ledger
        from rollout.rollout_config import VALIDATION_LEDGER_PATH
        l_path = Path(ledger_path) if ledger_path else VALIDATION_LEDGER_PATH
        l_path.parent.mkdir(parents=True, exist_ok=True)
        
        from datetime import datetime, timezone
        audit_record = {
            "record_type": "model_drift_audit",
            "model_id": model_id,
            "target_variable": variable,
            "action": action,
            "reason": reason,
            "overall_mae": round(overall_mae, 4),
            "drifting_plots": drifting_plots,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        with open(l_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_record) + "\n")
            
    return action
