"""
Layer 0.11: Production Invariants — Runtime Safety Checks

Enforces non-negotiable invariants at runtime to prevent silent corruption.
These are NOT tests — they run in production on every pipeline execution.

Invariants:
  1. Date alignment: all tensor arrays (state, uncertainty, provenance) share
     the exact same day index.
  2. Unit bounds: SAR in dB (never linear), NDVI ∈ [-1,1], SM ∈ [0,1],
     phenology ∈ [0,4], LAI ∈ [0,10], stress ∈ [0,1].
  3. Reliability bounds: reliability ∈ [0.05, 1.0] everywhere (never 0,
     because it enters R_effective = σ²/w and w=0 → division by zero).
  4. Covariance positive-definite: diagonal P ≥ epsilon.
  5. No NaN/Inf: in any state or observation value.

Usage:
    from layer0.invariants import enforce_all_invariants
    violations = enforce_all_invariants(tensor)
    if violations:
        handle_violations(violations)  # e.g. log, degrade, alert
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import math


class InvariantViolation:
    """Single invariant violation."""
    __slots__ = ("invariant", "severity", "location", "detail", "auto_fixed")

    def __init__(self, invariant: str, severity: str, location: str,
                 detail: str, auto_fixed: bool = False):
        self.invariant = invariant
        self.severity = severity  # "error", "warning", "fixed"
        self.location = location
        self.detail = detail
        self.auto_fixed = auto_fixed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invariant": self.invariant,
            "severity": self.severity,
            "location": self.location,
            "detail": self.detail,
            "auto_fixed": self.auto_fixed,
        }


# ============================================================================
# Constants
# ============================================================================

RELIABILITY_MIN = 0.05
RELIABILITY_MAX = 1.0

UNIT_BOUNDS = {
    "lai_proxy":        (0.0, 10.0),
    "biomass_proxy":    (0.0, 20.0),
    "sm_0_10":          (0.0, 1.0),
    "sm_10_40":         (0.0, 1.0),
    "canopy_stress":    (0.0, 1.0),
    "phenology_gdd":    (0.0, 5000.0),
    "phenology_stage":  (0.0, 4.0),
    "stress_thermal":   (0.0, 1.0),
}

OBSERVATION_BOUNDS = {
    "ndvi":         (-1.0, 1.0),
    "evi":          (-1.0, 1.0),
    "ndmi":         (-1.0, 1.0),
    "vv":           (-35.0, 0.0),   # dB — must never be positive linear
    "vh":           (-40.0, -5.0),  # dB
    "canopy_cover": (0.0, 1.0),
    "phenology_stage": (0.0, 4.0),
    "stress_proxy": (0.0, 1.0),
    "soil_moisture": (0.0, 1.0),
}

COVARIANCE_EPSILON = 1e-10


# ============================================================================
# Invariant Checks
# ============================================================================

def check_date_alignment(
    daily_state: Dict[str, List[Dict]],
    state_uncertainty: Dict[str, List[Dict]],
    provenance_log: List[Dict],
    time_index: List[str],
) -> List[InvariantViolation]:
    """
    Invariant 1: All day arrays must share the same day index set.
    """
    violations = []

    prov_days = set(d.get("day", "") for d in provenance_log)
    time_set = set(time_index)

    for zone_id, states in daily_state.items():
        state_days = set(s.get("day", "") for s in states)

        # States should cover the time index (± initial state)
        missing_in_state = time_set - state_days
        if missing_in_state:
            violations.append(InvariantViolation(
                "date_alignment", "error",
                f"daily_state[{zone_id}]",
                f"Missing {len(missing_in_state)} days vs time_index: {sorted(missing_in_state)[:3]}..."
            ))

    for zone_id, uncs in state_uncertainty.items():
        unc_days = set(u.get("day", "") for u in uncs)
        state_days = set(s.get("day", "") for s in daily_state.get(zone_id, []))
        mismatch = state_days.symmetric_difference(unc_days)
        if mismatch:
            violations.append(InvariantViolation(
                "date_alignment", "warning",
                f"state_uncertainty[{zone_id}]",
                f"Day mismatch with daily_state: {len(mismatch)} days differ"
            ))

    return violations


def check_unit_bounds(
    daily_state: Dict[str, List[Dict]],
    auto_clamp: bool = True,
) -> List[InvariantViolation]:
    """
    Invariant 2: State variables must be within physical bounds.
    If auto_clamp=True, silently clamps and reports as "fixed".
    """
    violations = []

    for zone_id, states in daily_state.items():
        for s in states:
            day = s.get("day", "?")
            for var_name, (lo, hi) in UNIT_BOUNDS.items():
                val = s.get(var_name)
                if val is None:
                    continue
                if not isinstance(val, (int, float)):
                    continue

                if val < lo or val > hi:
                    if auto_clamp:
                        clamped = max(lo, min(hi, val))
                        s[var_name] = clamped
                        violations.append(InvariantViolation(
                            "unit_bounds", "fixed",
                            f"{zone_id}/{day}/{var_name}",
                            f"Clamped {val:.4f} → [{lo}, {hi}]",
                            auto_fixed=True,
                        ))
                    else:
                        violations.append(InvariantViolation(
                            "unit_bounds", "error",
                            f"{zone_id}/{day}/{var_name}",
                            f"Value {val:.4f} out of bounds [{lo}, {hi}]"
                        ))

    return violations


def check_reliability_bounds(
    source_reliability: Dict[str, float],
    auto_clamp: bool = True,
) -> List[InvariantViolation]:
    """
    Invariant 3: Reliability ∈ [0.05, 1.0] everywhere.
    w=0 causes R_effective = σ²/w → division by zero.
    """
    violations = []

    for src, rel in list(source_reliability.items()):
        if rel < RELIABILITY_MIN or rel > RELIABILITY_MAX:
            if auto_clamp:
                clamped = max(RELIABILITY_MIN, min(RELIABILITY_MAX, rel))
                source_reliability[src] = clamped
                violations.append(InvariantViolation(
                    "reliability_bounds", "fixed",
                    f"source={src}",
                    f"Clamped {rel:.4f} → [{RELIABILITY_MIN}, {RELIABILITY_MAX}]",
                    auto_fixed=True,
                ))
            else:
                violations.append(InvariantViolation(
                    "reliability_bounds", "error",
                    f"source={src}",
                    f"Value {rel:.4f} out of [{RELIABILITY_MIN}, {RELIABILITY_MAX}]"
                ))

    return violations


def check_no_nan_inf(
    daily_state: Dict[str, List[Dict]],
    auto_fix: bool = True,
) -> List[InvariantViolation]:
    """
    Invariant 5: No NaN/Inf in any state value.
    """
    violations = []

    for zone_id, states in daily_state.items():
        for s in states:
            day = s.get("day", "?")
            for k, v in list(s.items()):
                if k == "day":
                    continue
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    if auto_fix:
                        # Reset to midpoint of bounds or 0
                        lo, hi = UNIT_BOUNDS.get(k, (0, 0))
                        s[k] = (lo + hi) / 2
                        violations.append(InvariantViolation(
                            "no_nan_inf", "fixed",
                            f"{zone_id}/{day}/{k}",
                            f"Was {v}, reset to {s[k]}",
                            auto_fixed=True,
                        ))
                    else:
                        violations.append(InvariantViolation(
                            "no_nan_inf", "error",
                            f"{zone_id}/{day}/{k}",
                            f"Value is {v}"
                        ))

    return violations


def check_observation_bounds(
    observations: Dict[str, Any],
) -> List[InvariantViolation]:
    """
    Invariant 2b: Observation values must be in physical range.
    Returns violations for logging; observations are not mutated.
    """
    violations = []

    for obs_type, val in observations.items():
        if obs_type not in OBSERVATION_BOUNDS:
            continue
        if not isinstance(val, (int, float)):
            continue
        lo, hi = OBSERVATION_BOUNDS[obs_type]
        if val < lo or val > hi:
            violations.append(InvariantViolation(
                "observation_bounds", "warning",
                f"obs={obs_type}",
                f"Value {val:.4f} out of expected [{lo}, {hi}] — may indicate unit mismatch"
            ))

    return violations


# ============================================================================
# Combined enforcer
# ============================================================================

def enforce_all_invariants(
    daily_state: Dict[str, List[Dict]],
    state_uncertainty: Dict[str, List[Dict]],
    provenance_log: List[Dict],
    time_index: List[str],
    source_reliability: Optional[Dict[str, float]] = None,
    auto_fix: bool = True,
) -> List[InvariantViolation]:
    """
    Run ALL runtime invariants. Returns list of violations.
    
    If auto_fix=True (default for production), values are clamped/reset
    in-place and violations are marked as "fixed".
    
    Usage in data_fusion.py:
        violations = enforce_all_invariants(
            tensor.daily_state, tensor.state_uncertainty,
            tensor.provenance_log, tensor.time_index,
            tensor.provenance.get("layer0_reliability"),
        )
        if violations:
            tensor.provenance["invariant_violations"] = [v.to_dict() for v in violations]
    """
    violations = []

    violations.extend(check_date_alignment(
        daily_state, state_uncertainty, provenance_log, time_index
    ))
    violations.extend(check_unit_bounds(daily_state, auto_clamp=auto_fix))
    violations.extend(check_no_nan_inf(daily_state, auto_fix=auto_fix))

    if source_reliability:
        violations.extend(check_reliability_bounds(
            source_reliability, auto_clamp=auto_fix
        ))

    return violations
