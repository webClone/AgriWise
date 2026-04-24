"""
Layer 2 Invariants — Vegetation Intelligence

Enforced on VegIntOutput:
  1. NDVI fit values in [-1, 1]
  2. Phenology stage sequence monotonic (no impossible jumps backward)
  3. AUC non-negative
  4. Anomaly severity/confidence in [0, 1]
  5. Curve quality RMSE >= 0, obs_coverage in [0, 1]
  6. Run ID and layer1_run_id present
"""

from typing import List
from dataclasses import dataclass

VALID_STAGES = ["BARE_SOIL", "EMERGENCE", "VEGETATIVE", "REPRODUCTIVE", "SENESCENCE", "HARVESTED", "UNKNOWN"]
STAGE_ORDER = {s: i for i, s in enumerate(VALID_STAGES[:-1])}  # UNKNOWN excluded


@dataclass
class InvariantViolation:
    check_name: str
    severity: str
    description: str
    auto_fixed: bool = False


def enforce_layer2_invariants(output) -> List[InvariantViolation]:
    violations: List[InvariantViolation] = []

    # 1. NDVI fit range
    for i, v in enumerate(output.curve.ndvi_fit):
        if v < -1.0 or v > 1.0:
            violations.append(InvariantViolation(
                "ndvi_fit_range", "warning",
                f"ndvi_fit[{i}]={v:.3f} outside [-1,1]"))
            break  # report once

    # 2. Phenology monotonic
    stages = output.phenology.stage_by_day
    if stages:
        last_idx = -1
        for i, s in enumerate(stages):
            if s == "UNKNOWN":
                continue
            idx = STAGE_ORDER.get(s, -1)
            if idx >= 0:
                if idx < last_idx and last_idx != STAGE_ORDER.get("HARVESTED", 99):
                    violations.append(InvariantViolation(
                        "phenology_monotonic", "warning",
                        f"Stage regression at day {i}: {stages[i-1] if i>0 else '?'} -> {s}"))
                    break
                last_idx = max(last_idx, idx)

    # 3. AUC non-negative
    growth = getattr(output, "growth_metrics", None)
    if growth and hasattr(growth, "auc_season"):
        if growth.auc_season < 0:
            violations.append(InvariantViolation(
                "auc_non_negative", "error",
                f"AUC season = {growth.auc_season} < 0"))

    # 4. Anomaly bounds
    for a in output.anomalies:
        if a.severity < 0 or a.severity > 1:
            violations.append(InvariantViolation(
                "anomaly_severity_range", "warning",
                f"Anomaly '{a.anomaly_id}' severity={a.severity} not in [0,1]"))
        if a.confidence < 0 or a.confidence > 1:
            violations.append(InvariantViolation(
                "anomaly_confidence_range", "warning",
                f"Anomaly '{a.anomaly_id}' confidence={a.confidence} not in [0,1]"))

    # 5. Curve quality
    q = output.curve.quality
    if q.rmse < 0:
        violations.append(InvariantViolation(
            "rmse_non_negative", "error", f"RMSE={q.rmse} < 0"))
    if q.obs_coverage < 0 or q.obs_coverage > 1:
        violations.append(InvariantViolation(
            "obs_coverage_range", "warning",
            f"obs_coverage={q.obs_coverage} not in [0,1]"))

    # 6. Run IDs
    if not output.run_id:
        violations.append(InvariantViolation(
            "run_id_present", "warning", "Missing run_id"))
    if not output.layer1_run_id:
        violations.append(InvariantViolation(
            "layer1_run_id_present", "warning", "Missing layer1_run_id"))

    return violations
