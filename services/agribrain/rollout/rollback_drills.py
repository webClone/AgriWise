"""
Rollback Drill System.
Automates Drill A (Backend rollback), Drill B (Visual rollback), and
Drill C (Plot-level registry rollback) to verify pipeline safety controls.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from rollout.rollout_policy import should_run_asmae, should_render_l10_asmae
from rollout.asmae_rollout_registry import record_rollout_decision, get_rollout_phase

REPORT_PATH = Path(__file__).parent.parent / "artifacts" / "rollback_drill_report.json"

def run_rollback_drills() -> Dict[str, Any]:
    """Execute all rollback drills and verify constraints."""
    original_env = {
        "ASMAE_ENABLED": os.environ.get("ASMAE_ENABLED"),
        "L10_ASMAE_SURFACES_ENABLED": os.environ.get("L10_ASMAE_SURFACES_ENABLED"),
    }
    
    results = {}
    
    try:
        # ── Drill A: Backend rollback ──────────────────────────────
        os.environ["ASMAE_ENABLED"] = "false"
        os.environ["L10_ASMAE_SURFACES_ENABLED"] = "true"
        
        # Test registered plot
        drill_a_ok = (not should_run_asmae("test_plot")) and (not should_render_l10_asmae("test_plot"))
        results["Drill_A_Backend_Rollback"] = {
            "status": "PASS" if drill_a_ok else "FAIL",
            "notes": "Verified that setting ASMAE_ENABLED=false blocks backend and visuals globally."
        }
        
        # ── Drill B: Visual rollback only ──────────────────────────
        os.environ["ASMAE_ENABLED"] = "true"
        os.environ["L10_ASMAE_SURFACES_ENABLED"] = "false"
        
        # Backend should run, visuals should be blocked
        drill_b_ok = should_run_asmae("test_plot") and (not should_render_l10_asmae("test_plot"))
        results["Drill_B_Visual_Rollback_Only"] = {
            "status": "PASS" if drill_b_ok else "FAIL",
            "notes": "Verified that setting L10_ASMAE_SURFACES_ENABLED=false blocks visuals but keeps backend."
        }
        
        # ── Drill C: Plot-level rollback ───────────────────────────
        os.environ["ASMAE_ENABLED"] = "true"
        os.environ["L10_ASMAE_SURFACES_ENABLED"] = "true"
        
        # Disable specifically a test plot
        record_rollout_decision("test_plot_rollback_drill", "disabled", "Rollback drill activation", operator="drill_operator")
        
        drill_c_ok = (not should_run_asmae("test_plot_rollback_drill")) and should_run_asmae("test_plot")
        results["Drill_C_Plot_Level_Rollback"] = {
            "status": "PASS" if drill_c_ok else "FAIL",
            "notes": "Verified that disabling a plot in the registry blocks only that plot."
        }
        
    finally:
        # Restore original environment
        for k, v in original_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
                
    # Rollback drill report
    all_passed = all(v["status"] == "PASS" for v in results.values())
    report = {
        "timestamp": datetime_now_iso(),
        "all_drills_passed": all_passed,
        "results": results
    }
    
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    return report

def datetime_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
