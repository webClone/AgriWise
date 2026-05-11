"""
Layer 2 Invariants — Vegetation Intelligence (v2.2)

Production-grade invariant suite enforced on VegIntOutput.
10 checks covering growth curve realism, phenology bounds, and anomaly validity.

  1.  ndvi_fit_range          — All modeled NDVI values in [-1, 1]
  2.  phenology_monotonic     — No impossible stage regressions
  3.  auc_non_negative        — AUC season >= 0
  4.  anomaly_severity_range  — All anomaly severities in [0, 1]
  5.  anomaly_confidence_range — All anomaly confidences in [0, 1]
  6.  rmse_non_negative       — RMSE >= 0
  7.  obs_coverage_range      — obs_coverage in [0, 1]
  8.  run_id_present          — run_id and layer1_run_id non-empty
  9.  ndvi_fit_length         — ndvi_fit, ndvi_fit_d1, ndvi_fit_unc same length
  10. confidence_range        — All phenology confidence values in [0, 1]
"""

from typing import List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

VALID_STAGES = ["BARE_SOIL", "EMERGENCE", "VEGETATIVE", "REPRODUCTIVE", "SENESCENCE", "HARVESTED", "UNKNOWN"]
STAGE_ORDER = {s: i for i, s in enumerate(VALID_STAGES[:-1])}  # UNKNOWN excluded


@dataclass
class InvariantViolation:
    check_name: str
    severity: str
    description: str
    auto_fixed: bool = False


def enforce_layer2_invariants(output) -> List[InvariantViolation]:
    """Enforce all 10 production invariants on a VegIntOutput instance.

    Returns:
        List of violations found.  Empty list == clean.
    """
    violations: List[InvariantViolation] = []

    curve = output.curve
    pheno = output.phenology

    # 1. NDVI fit range
    for i, v in enumerate(curve.ndvi_fit):
        if v < -1.0 or v > 1.0:
            violations.append(InvariantViolation(
                "ndvi_fit_range", "warning",
                f"ndvi_fit[{i}]={v:.3f} outside [-1,1]"))
            break  # report once

    # 2. Phenology monotonic
    stages = pheno.stage_by_day
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

    # 4. Anomaly severity bounds
    for a in output.anomalies:
        if a.severity < 0 or a.severity > 1:
            violations.append(InvariantViolation(
                "anomaly_severity_range", "warning",
                f"Anomaly '{a.anomaly_id}' severity={a.severity} not in [0,1]"))

    # 5. Anomaly confidence bounds
    for a in output.anomalies:
        if a.confidence < 0 or a.confidence > 1:
            violations.append(InvariantViolation(
                "anomaly_confidence_range", "warning",
                f"Anomaly '{a.anomaly_id}' confidence={a.confidence} not in [0,1]"))

    # 6. RMSE non-negative
    q = curve.quality
    if q.rmse < 0:
        violations.append(InvariantViolation(
            "rmse_non_negative", "error", f"RMSE={q.rmse} < 0"))

    # 7. Observation coverage range
    if q.obs_coverage < 0 or q.obs_coverage > 1:
        violations.append(InvariantViolation(
            "obs_coverage_range", "warning",
            f"obs_coverage={q.obs_coverage} not in [0,1]"))

    # 8. Run IDs
    if not output.run_id:
        violations.append(InvariantViolation(
            "run_id_present", "warning", "Missing run_id"))
    if not output.layer1_run_id:
        violations.append(InvariantViolation(
            "layer1_run_id_present", "warning", "Missing layer1_run_id"))

    # 9. Length consistency — fit, derivative, and uncertainty must match
    if len(curve.ndvi_fit) != len(curve.ndvi_fit_d1):
        violations.append(InvariantViolation(
            "ndvi_fit_length", "error",
            f"ndvi_fit({len(curve.ndvi_fit)}) != ndvi_fit_d1({len(curve.ndvi_fit_d1)})"))

    if curve.ndvi_fit_unc and len(curve.ndvi_fit_unc) != len(curve.ndvi_fit):
        violations.append(InvariantViolation(
            "ndvi_fit_length", "warning",
            f"ndvi_fit({len(curve.ndvi_fit)}) != ndvi_fit_unc({len(curve.ndvi_fit_unc)})"))

    # 10. Phenology confidence bounds
    for i, c in enumerate(pheno.confidence_by_day):
        if c < 0.0 or c > 1.0:
            violations.append(InvariantViolation(
                "confidence_range", "error",
                f"confidence_by_day[{i}]={c:.4f} outside [0, 1]"))
            break

    # Log summary
    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]
    if errors:
        for v in errors:
            logger.error(f"[Layer 2] INVARIANT ERROR: {v.check_name} — {v.description}")
    if warnings:
        for v in warnings:
            logger.warning(f"[Layer 2] INVARIANT WARN: {v.check_name} — {v.description}")

    return violations
