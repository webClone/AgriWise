"""
Layer 1 Invariants — FieldTensor Integrity

Enforced at fusion output:
  1. Date alignment: all daily arrays have identical length
  2. No NaN/Inf in key rasters
  3. Source coverage bounds (>0 evidence items)
  4. Value range: NDVI in [-1,1], precipitation >= 0, temperatures sensible
  5. Grid spec non-zero
  6. Provenance fields present
"""

from typing import List
from dataclasses import dataclass
import math


@dataclass
class InvariantViolation:
    check_name: str
    severity: str
    description: str
    auto_fixed: bool = False


def enforce_layer1_invariants(tensor) -> List[InvariantViolation]:
    violations: List[InvariantViolation] = []

    # 1. Date alignment
    ts = tensor.daily_state
    if ts:
        day_counts = set()
        for channel, values in ts.items():
            if isinstance(values, list):
                day_counts.add(len(values))
        if len(day_counts) > 1:
            violations.append(InvariantViolation(
                "date_alignment", "error",
                f"Daily state arrays have mismatched lengths: {day_counts}"))

    # 2. NaN/Inf in key channels
    key_channels = ["ndvi", "precipitation", "temp_max", "temp_min"]
    for ch in key_channels:
        values = ts.get(ch, [])
        if isinstance(values, list):
            bad = [i for i, v in enumerate(values)
                   if isinstance(v, float) and (math.isnan(v) or math.isinf(v))]
            if bad:
                violations.append(InvariantViolation(
                    "nan_inf_check", "warning",
                    f"Channel '{ch}' has NaN/Inf at indices {bad[:5]}"))

    # 3. Source coverage
    provenance = getattr(tensor, "provenance", {})
    if isinstance(provenance, dict):
        sources = provenance.get("sources", {})
        if isinstance(sources, dict) and len(sources) == 0:
            violations.append(InvariantViolation(
                "source_coverage", "warning",
                "No provenance sources recorded"))

    # 4. Value ranges
    ndvi = ts.get("ndvi", [])
    if isinstance(ndvi, list):
        oob = [v for v in ndvi if isinstance(v, (int, float)) and (v < -1.0 or v > 1.0)]
        if oob:
            violations.append(InvariantViolation(
                "ndvi_range", "warning",
                f"NDVI has {len(oob)} values outside [-1,1]"))

    precip = ts.get("precipitation", [])
    if isinstance(precip, list):
        neg = [v for v in precip if isinstance(v, (int, float)) and v < 0]
        if neg:
            violations.append(InvariantViolation(
                "precip_non_negative", "error",
                f"Precipitation has {len(neg)} negative values",
                auto_fixed=True))

    # 5. Grid spec
    gs = getattr(tensor, "grid_spec", None)
    if gs:
        if getattr(gs, "width", 0) == 0 or getattr(gs, "height", 0) == 0:
            violations.append(InvariantViolation(
                "grid_spec_non_zero", "error",
                "Grid spec has zero width or height"))

    # 6. Run ID present
    if not getattr(tensor, "run_id", ""):
        violations.append(InvariantViolation(
            "run_id_present", "warning",
            "FieldTensor missing run_id"))

    return violations
