"""
One-Meter Policy Summary Builder and Enforcer (V90.10)
======================================================

Enforces that high-resolution (<=1.0m) inferred details are never accepted as
state updates, training labels, or prescription drivers.
"""

from typing import List, Dict, Any

def build_one_meter_policy_summary(surfaces: List[Any]) -> Dict[str, int]:
    """Iterates through generated surfaces and compiles counts for 1m policy variables."""
    total_1m_surfaces = 0
    display_certified = 0
    visual_only = 0
    state_update_allowed = 0
    training_label_allowed = 0
    prescription_driver_allowed = 0

    for s in surfaces:
        res = getattr(s, "native_resolution_m", 10.0)
        provenance = getattr(s, "provenance", {}) or {}
        res_prov = provenance.get("resolution_m", res)

        if res_prov <= 1.0:
            total_1m_surfaces += 1
            if provenance.get("display_certified", False):
                display_certified += 1
            if provenance.get("visual_only", False):
                visual_only += 1
            if provenance.get("state_update_allowed", False):
                state_update_allowed += 1
            if provenance.get("training_label_allowed", False):
                training_label_allowed += 1
            if provenance.get("prescription_driver_allowed", False):
                prescription_driver_allowed += 1

    return {
        "total_1m_surfaces": total_1m_surfaces,
        "display_certified": display_certified,
        "visual_only": visual_only,
        "state_update_allowed": state_update_allowed,
        "training_label_allowed": training_label_allowed,
        "prescription_driver_allowed": prescription_driver_allowed
    }

def enforce_one_meter_policy(summary: Dict[str, int]) -> None:
    """Raises a RuntimeError if any 1m details were allowed for downstream mutation/logic."""
    if summary.get("state_update_allowed", 0) > 0:
        raise RuntimeError("one_meter_state_update_policy_violation")
    if summary.get("training_label_allowed", 0) > 0:
        raise RuntimeError("one_meter_training_label_policy_violation")
    if summary.get("prescription_driver_allowed", 0) > 0:
        raise RuntimeError("one_meter_prescription_driver_policy_violation")
