"""
Layer 3 Input Context Invariants.

Runtime safety checks on the incoming Layer3InputContext BEFORE inference.
Mirrors L1 and L2 pattern of validating context payloads to prevent
"Garbage In, Garbage Out" scenarios.

Checks:
  1. bounds_check — Ensure numeric fields are in [0, 1]
  2. operational_consistency — Check for paradoxical boolean/count pairs
  3. confidence_ceiling_validity — Validate data_health ceiling
  4. zone_variance_check — Ensure zone_status is mathematically coherent
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List

from layer2_intelligence.outputs.layer3_adapter import Layer3InputContext


@dataclass
class InputViolation:
    """A single input invariant violation result."""
    check_name: str
    severity: str          # warning | error
    description: str
    auto_fixed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "severity": self.severity,
            "description": self.description,
            "auto_fixed": self.auto_fixed,
        }


def enforce_context_invariants(ctx: Layer3InputContext) -> List[InputViolation]:
    """Run all input invariants. Auto-fixes safe cases in-place."""
    violations: List[InputViolation] = []

    violations.extend(_check_numeric_bounds(ctx))
    violations.extend(_check_operational_consistency(ctx))
    violations.extend(_check_confidence_ceiling(ctx))
    violations.extend(_check_zone_variance(ctx))

    return violations


def _check_numeric_bounds(ctx: Layer3InputContext) -> List[InputViolation]:
    violations = []
    
    # Check stress summary
    for k, v in list(ctx.stress_summary.items()):
        if not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
            ctx.stress_summary[k] = 0.0
            violations.append(InputViolation(
                "stress_summary_bounds", "warning",
                f"Stress {k} had invalid value {v}, clamped to 0.0",
                auto_fixed=True,
            ))
        elif v < 0.0 or v > 1.0:
            clamped = max(0.0, min(1.0, v))
            ctx.stress_summary[k] = clamped
            violations.append(InputViolation(
                "stress_summary_bounds", "warning",
                f"Stress {k} severity {v} out of bounds, clamped to {clamped}",
                auto_fixed=True,
            ))
            
    # Check operational signals
    op = ctx.operational_signals
    if isinstance(op, dict):
        for key in ["water_deficit_severity", "thermal_severity", "anomaly_severity"]:
            val = op.get(key, 0.0)
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                op[key] = 0.0
                violations.append(InputViolation(
                    "operational_bounds", "warning",
                    f"{key} was invalid, clamped to 0.0", auto_fixed=True,
                ))
            elif val < 0.0 or val > 1.0:
                op[key] = max(0.0, min(1.0, val))
                violations.append(InputViolation(
                    "operational_bounds", "warning",
                    f"{key} {val} out of bounds, clamped to {op[key]}", auto_fixed=True,
                ))
                
        # Growth velocity might be slightly outside [-1, 1], let's bound it loosely [-10, 10]
        vel = op.get("growth_velocity", 0.0)
        if not isinstance(vel, (int, float)) or math.isnan(vel) or math.isinf(vel):
            op["growth_velocity"] = 0.0
            violations.append(InputViolation(
                "operational_bounds", "warning",
                "growth_velocity was invalid, clamped to 0.0", auto_fixed=True,
            ))
        elif vel < -10.0 or vel > 10.0:
            op["growth_velocity"] = max(-10.0, min(10.0, vel))
            violations.append(InputViolation(
                "operational_bounds", "warning",
                f"growth_velocity {vel} out of bounds, clamped", auto_fixed=True,
            ))

    return violations


def _check_operational_consistency(ctx: Layer3InputContext) -> List[InputViolation]:
    violations = []
    op = ctx.operational_signals
    if not isinstance(op, dict):
        return violations

    # Paradox 1: Available = False, but count > 0
    if not op.get("optical_available", False) and op.get("optical_obs_count", 0) > 0:
        op["optical_available"] = True
        violations.append(InputViolation(
            "operational_consistency", "warning",
            "optical_available=False but count > 0. Forced to True.", auto_fixed=True,
        ))
        
    if not op.get("sar_available", False) and op.get("sar_obs_count", 0) > 0:
        op["sar_available"] = True
        violations.append(InputViolation(
            "operational_consistency", "warning",
            "sar_available=False but count > 0. Forced to True.", auto_fixed=True,
        ))

    # Paradox 2: Anomaly severity > 0 but has_anomaly = False
    if op.get("anomaly_severity", 0.0) > 0.0 and not op.get("has_anomaly", False):
        op["has_anomaly"] = True
        violations.append(InputViolation(
            "operational_consistency", "warning",
            "anomaly_severity > 0 but has_anomaly=False. Forced to True.", auto_fixed=True,
        ))

    return violations


def _check_confidence_ceiling(ctx: Layer3InputContext) -> List[InputViolation]:
    violations = []
    
    # Ensure ceiling is strictly in [0.05, 1.0] (0.05 minimum floor for math safety)
    if not isinstance(ctx.confidence_ceiling, (int, float)) or math.isnan(ctx.confidence_ceiling):
        ctx.confidence_ceiling = 0.05
        violations.append(InputViolation(
            "confidence_ceiling_bounds", "error",
            "confidence_ceiling was invalid. Forced to 0.05.", auto_fixed=True,
        ))
    elif ctx.confidence_ceiling < 0.05 or ctx.confidence_ceiling > 1.0:
        old = ctx.confidence_ceiling
        ctx.confidence_ceiling = max(0.05, min(1.0, ctx.confidence_ceiling))
        violations.append(InputViolation(
            "confidence_ceiling_bounds", "warning",
            f"confidence_ceiling {old} clamped to {ctx.confidence_ceiling}", auto_fixed=True,
        ))
        
    # Check data_health object sync
    if ctx.data_health:
        dh_ceil = ctx.data_health.confidence_ceiling
        if not isinstance(dh_ceil, (int, float)) or math.isnan(dh_ceil) or dh_ceil < 0.05 or dh_ceil > 1.0:
            ctx.data_health.confidence_ceiling = ctx.confidence_ceiling
            violations.append(InputViolation(
                "data_health_sync", "warning",
                "data_health.confidence_ceiling synced with context ceiling", auto_fixed=True,
            ))
            
    return violations


def _check_zone_variance(ctx: Layer3InputContext) -> List[InputViolation]:
    violations = []
    if not ctx.zone_status or not isinstance(ctx.zone_status, dict):
        return violations

    for z_id, z_data in list(ctx.zone_status.items()):
        if not isinstance(z_data, dict):
            continue

        # --- Severity ---
        sev = z_data.get("severity", 0.0)
        if not isinstance(sev, (int, float)) or math.isnan(sev) or math.isinf(sev):
            z_data["severity"] = 0.0
            violations.append(InputViolation(
                "zone_bounds", "warning",
                f"Zone {z_id} severity was invalid ({sev}), reset to 0.0", auto_fixed=True,
            ))
        elif sev < 0.0 or sev > 1.0:
            z_data["severity"] = max(0.0, min(1.0, sev))
            violations.append(InputViolation(
                "zone_bounds", "warning",
                f"Zone {z_id} severity {sev} clamped to {z_data['severity']}", auto_fixed=True,
            ))

        # --- Confidence ---
        conf = z_data.get("confidence", 0.0)
        if not isinstance(conf, (int, float)) or math.isnan(conf) or math.isinf(conf):
            z_data["confidence"] = 0.0
            violations.append(InputViolation(
                "zone_bounds", "warning",
                f"Zone {z_id} confidence was invalid ({conf}), reset to 0.0", auto_fixed=True,
            ))
        elif conf < 0.0 or conf > 1.0:
            z_data["confidence"] = max(0.0, min(1.0, conf))
            violations.append(InputViolation(
                "zone_bounds", "warning",
                f"Zone {z_id} confidence {conf} clamped to {z_data['confidence']}", auto_fixed=True,
            ))

    return violations

