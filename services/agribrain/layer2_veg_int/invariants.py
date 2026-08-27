"""
Layer 2 Invariants — Vegetation Intelligence (v3.1)

Production-grade invariant suite enforced on VegIntOutput.
18 checks covering growth curve realism, phenology bounds, anomaly validity,
LAI/CWSI/fPAR/FVC/NPP ranges, ET deficit, and crop health index.

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
  11. lai_range               — All LAI values in [0, 10]
  12. cwsi_range              — All CWSI values in [0, 1]
  13. health_score_range      — overall_score in [0, 1]
  14. anomaly_type_valid      — All anomaly types are known enum values
  15. fpar_range              — All fPAR values in [0, 1]
  16. fvc_range               — All FVC values in [0, 1]
  17. npp_non_negative        — All NPP values >= 0
  18. et_deficit_non_negative — ET deficit >= 0
"""

from typing import List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

VALID_STAGES = [
    "BARE_SOIL", "EMERGENCE", "VEGETATIVE", "REPRODUCTIVE",
    "SENESCENCE", "HARVESTED", "DORMANCY", "UNKNOWN",
]
STAGE_ORDER = {s: i for i, s in enumerate(VALID_STAGES[:-1])}  # UNKNOWN excluded

# Valid anomaly type values
_VALID_ANOMALY_TYPES = {
    "STALL", "DROP", "EARLY_SENESCENCE", "DELAYED_EMERGENCE",
    "SPATIAL_PATCHINESS", "WATER_STRESS", "EXCESS_MOISTURE",
    "NUTRIENT_DEFICIENCY", "HEAT_STRESS", "POSITIVE_ANOMALY",
    "FROST_DAMAGE", "WIND_DAMAGE",
}


@dataclass
class InvariantViolation:
    check_name: str
    severity: str
    description: str
    auto_fixed: bool = False


def enforce_layer2_invariants(output) -> List[InvariantViolation]:
    """Enforce all 18 production invariants on a VegIntOutput instance.

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

    # 2. Phenology monotonic (with DORMANCY support)
    stages = pheno.stage_by_day
    if stages:
        last_idx = -1
        for i, s in enumerate(stages):
            if s == "UNKNOWN":
                continue
            idx = STAGE_ORDER.get(s, -1)
            if idx >= 0:
                # Allow DORMANCY -> EMERGENCE transition (perennial cycle)
                if s == "DORMANCY" and last_idx >= 0:
                    # DORMANCY can appear after SENESCENCE (idx=4 -> idx=6)
                    # This is not a regression — reset tracking
                    last_idx = idx
                    continue
                if idx < last_idx and VALID_STAGES[last_idx] != "HARVESTED":
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

    # 11. LAI range [0, 10]
    if curve.lai_series:
        for i, lai in enumerate(curve.lai_series):
            if lai < 0.0 or lai > 10.0:
                violations.append(InvariantViolation(
                    "lai_range", "warning",
                    f"lai_series[{i}]={lai:.2f} outside [0, 10]"))
                break

    # 12. CWSI range [0, 1] (or None if unobserved/missing)
    if curve.cwsi_series:
        for i, cwsi in enumerate(curve.cwsi_series):
            if cwsi is not None and (cwsi < 0.0 or cwsi > 1.0):
                violations.append(InvariantViolation(
                    "cwsi_range", "warning",
                    f"cwsi_series[{i}]={cwsi:.3f} outside [0, 1]"))
                break

    # 13. Health score range [0, 1]
    health = getattr(output, "health_index", None)
    if health:
        if health.overall_score < 0.0 or health.overall_score > 1.0:
            violations.append(InvariantViolation(
                "health_score_range", "error",
                f"health_index.overall_score={health.overall_score} not in [0, 1]"))
        if health.confidence < 0.0 or health.confidence > 1.0:
            violations.append(InvariantViolation(
                "health_confidence_range", "warning",
                f"health_index.confidence={health.confidence} not in [0, 1]"))

    # 14. Anomaly type validation
    for a in output.anomalies:
        type_val = a.type.value if hasattr(a.type, 'value') else str(a.type)
        if type_val not in _VALID_ANOMALY_TYPES:
            violations.append(InvariantViolation(
                "anomaly_type_valid", "warning",
                f"Unknown anomaly type: {type_val}"))

    # 15. fPAR range [0, 1]
    if curve.fpar_series:
        for i, fp in enumerate(curve.fpar_series):
            if fp < 0.0 or fp > 1.0:
                violations.append(InvariantViolation(
                    "fpar_range", "warning",
                    f"fpar_series[{i}]={fp:.3f} outside [0, 1]"))
                break

    # 16. FVC range [0, 1]
    if curve.fvc_series:
        for i, fvc in enumerate(curve.fvc_series):
            if fvc < 0.0 or fvc > 1.0:
                violations.append(InvariantViolation(
                    "fvc_range", "warning",
                    f"fvc_series[{i}]={fvc:.3f} outside [0, 1]"))
                break

    # 17. NPP non-negative
    if curve.npp_series:
        for i, npp in enumerate(curve.npp_series):
            if npp < 0.0:
                violations.append(InvariantViolation(
                    "npp_non_negative", "warning",
                    f"npp_series[{i}]={npp:.3f} < 0"))
                break

    # 18. ET deficit non-negative
    if health and hasattr(health, 'et_deficit'):
        if health.et_deficit < 0.0:
            violations.append(InvariantViolation(
                "et_deficit_non_negative", "warning",
                f"health_index.et_deficit={health.et_deficit} < 0"))

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
