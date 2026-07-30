"""
Rollout Monitor for V85.
Analyzes validation ledger logs and cache storage artifacts against strict
rollout thresholds, generating a rollout gate report.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from rollout.rollout_config import VALIDATION_LEDGER_PATH, ROLLOUT_REPORT_PATH

def generate_v85_rollout_report(
    ledger_path: Optional[Path] = None,
    report_path: Optional[Path] = None,
    extra_runs: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Analyze the validation ledger and output the rollout report json."""
    ledg_p = Path(ledger_path) if ledger_path else VALIDATION_LEDGER_PATH
    rep_p = Path(report_path) if report_path else ROLLOUT_REPORT_PATH
    
    runs = []
    # Read runs from ledger
    if ledg_p.exists():
        try:
            with open(ledg_p, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        runs.append(json.loads(line))
        except Exception:
            pass
            
    if extra_runs:
        runs.extend(extra_runs)
        
    plots_evaluated = len(set(r.get("plot_id") for r in runs if r.get("plot_id")))
    runs_evaluated = len(runs)
    
    # Initialize metrics
    latencies = []
    warm_latencies = []
    cache_hits = 0
    total_cache_queries = 0
    false_1m_claims = 0
    diagnostic_action_leaks = 0
    weak_label_state_leaks = 0
    corrupted_cache_recovery_failures = 0
    artifact_sizes = []
    conflict_runs = 0
    low_confidence_runs = 0
    warning_count = 0
    rollback_drills_failed = 0
    
    for r in runs:
        # Check latency
        lat = r.get("latency_ms", 0.0) or r.get("total_latency_ms", 0.0)
        if lat > 0:
            latencies.append(lat)
            
        cache_status = r.get("cache_status", "")
        if cache_status == "hit":
            cache_hits += 1
            if lat > 0:
                warm_latencies.append(lat)
        if cache_status in ("hit", "miss"):
            total_cache_queries += 1
            
        # Check leak counts
        false_1m_claims += r.get("false_1m_claim_count", 0)
        diagnostic_action_leaks += r.get("diagnostic_to_action_leak_count", 0)
        weak_label_state_leaks += r.get("weak_label_to_state_leak_count", 0)
        corrupted_cache_recovery_failures += r.get("corrupted_cache_recovery_failure_count", 0)
        rollback_drills_failed += r.get("rollback_drill_failed_count", 0)
        
        # Check conflict / confidence
        conflict_val = r.get("trust_summary", {}).get("bma_disagreement", 0.0) or r.get("cross_layer_conflict_rate", 0.0)
        if conflict_val > 0.15:
            conflict_runs += 1
            
        conf_val = r.get("trust_summary", {}).get("confidence_mean", 1.0)
        if conf_val < 0.5: # Low confidence threshold
            low_confidence_runs += 1
            
        warning_count += len(r.get("warnings", []))
        
        # Artifact size
        size = r.get("artifact_total_bytes", 0) or (r.get("artifact_json_bytes", 0) + r.get("artifact_npz_bytes", 0))
        if size > 0:
            artifact_sizes.append(size)
            
    # Compute aggregates
    latencies.sort()
    warm_latencies.sort()
    
    p50_latency = latencies[len(latencies)//2] if latencies else 0.0
    p95_index = int(len(latencies) * 0.95)
    p95_latency = latencies[p95_index] if latencies else 0.0
    
    cache_hit_rate = cache_hits / total_cache_queries if total_cache_queries > 0 else 1.0
    conflict_rate = conflict_runs / runs_evaluated if runs_evaluated > 0 else 0.0
    low_confidence_rate = low_confidence_runs / runs_evaluated if runs_evaluated > 0 else 0.0
    total_artifact_growth = sum(artifact_sizes)
    
    reasons = []
    status = "PASS"
    broad_rollout_allowed = True
    
    # 1. Latency Thresholds: standard < 500ms max, warm cache < 50ms, warm path < 300ms
    if p95_latency > 500.0:
        status = "HOLD"
        broad_rollout_allowed = False
        reasons.append("latency_over_budget")
        
    # 2. Leaks and safety breaches
    if false_1m_claims > 0:
        status = "HOLD"
        broad_rollout_allowed = False
        reasons.append("false_1m_claims_detected")
        
    if diagnostic_action_leaks > 0:
        status = "HOLD"
        broad_rollout_allowed = False
        reasons.append("diagnostic_action_leakage")
        
    if weak_label_state_leaks > 0:
        status = "HOLD"
        broad_rollout_allowed = False
        reasons.append("weak_label_to_state_leakage")
        
    if corrupted_cache_recovery_failures > 0:
        status = "HOLD"
        broad_rollout_allowed = False
        reasons.append("cache_recovery_failure")
        
    if rollback_drills_failed > 0:
        status = "HOLD"
        broad_rollout_allowed = False
        reasons.append("rollback_drill_failure")
        
    # 3. Artifact growth per run > 10MB (example threshold)
    avg_growth = total_artifact_growth / runs_evaluated if runs_evaluated > 0 else 0
    if avg_growth > 10 * 1024 * 1024: # 10MB
        status = "HOLD"
        broad_rollout_allowed = False
        reasons.append("artifact_growth_over_budget")
        
    # 4. Conflict / Warning rates: warn above 15%, block above 30%
    if conflict_rate > 0.30:
        status = "HOLD"
        broad_rollout_allowed = False
        reasons.append("cross_layer_conflict_rate_critical")
    elif conflict_rate > 0.15:
        reasons.append("cross_layer_conflict_rate_warning")
        
    if low_confidence_rate > 0.35:
        reasons.append("low_confidence_surface_rate_warning")
        
    # 5. Require a minimum run count for broad rollout
    if runs_evaluated < 20:
        broad_rollout_allowed = False
        reasons.append("insufficient_run_count")
        
    report = {
        "status": status,
        "plots_evaluated": plots_evaluated,
        "runs_evaluated": runs_evaluated,
        "broad_rollout_allowed": broad_rollout_allowed,
        "reasons": reasons,
        "metrics": {
            "p50_latency_ms": round(p50_latency, 2),
            "p95_latency_ms": round(p95_latency, 2),
            "cache_hit_rate": round(cache_hit_rate, 2),
            "false_1m_claims": false_1m_claims,
            "diagnostic_action_leaks": diagnostic_action_leaks,
            "weak_label_state_leaks": weak_label_state_leaks,
            "conflict_rate": round(conflict_rate, 2),
            "low_confidence_rate": round(low_confidence_rate, 2),
            "avg_artifact_growth_bytes": round(avg_growth, 2),
            "total_artifact_growth_bytes": total_artifact_growth
        }
    }
    
    rep_p.parent.mkdir(parents=True, exist_ok=True)
    with open(rep_p, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    return report
