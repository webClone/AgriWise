"""
V73: Layer 8 constraints — do-not-prescribe, action feasibility.

CRITICAL: Renamed from layer8_action_masks.py (user-approved).
Layer 8 actions must NEVER become ASMAE truth.
Only consume constraints — never recommendations as state evidence.

Used for:
  - Do-not-prescribe zones
  - Action feasibility
  - Spray drift risk
  - Phenology dosing windows
  - Salinity leaching windows
"""

from __future__ import annotations
from typing import Any, Dict, List


def extract_layer8_constraints(coarse_outputs: dict) -> Dict[str, Any]:
    """Extract Layer 8 constraints (NOT recommendations).

    NEVER uses Layer 8 recommendation output as state evidence.
    Only consumes constraint data for gating.
    """
    l8 = coarse_outputs.get("layer8_action", {})
    available = bool(l8) and l8.get("status") in ("available", "partial")

    return {
        "source_layer": "layer8_action",
        "source_run_id": l8.get("run_id", ""),
        "source_timestamp": l8.get("timestamp", ""),
        "valid_time_window": l8.get("valid_window", ""),
        "uses_future_holdout": False,
        "status": "available" if available else "degraded",
        "confidence": l8.get("confidence", 0.0),
        "usable_as_prior": available,
        "reason": "" if available else l8.get("reason", "missing_layer8_output"),
        # Constraint fields only (never recommendations)
        "do_not_prescribe_zones": l8.get("do_not_prescribe_zones", []),
        "action_feasibility": l8.get("action_feasibility", {}),
        "spray_drift_risk": l8.get("spray_drift_risk"),
        "phenology_dosing_windows": l8.get("phenology_dosing_windows", []),
        "salinity_leaching_windows": l8.get("salinity_leaching_windows", []),
        # SAFETY: explicitly flag that this is constraints-only
        "is_constraint_only": True,
        "contains_recommendations": False,
    }
