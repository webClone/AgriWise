"""V73: Layer 3 water priors — ET0, water balance, irrigation response."""

from __future__ import annotations
from typing import Any, Dict


def extract_layer3_priors(coarse_outputs: dict) -> Dict[str, Any]:
    l3 = coarse_outputs.get("layer3_water", {})
    available = bool(l3) and l3.get("status") in ("available", "partial")
    return {
        "source_layer": "layer3_water",
        "source_run_id": l3.get("run_id", ""),
        "source_timestamp": l3.get("timestamp", ""),
        "valid_time_window": l3.get("valid_window", ""),
        "uses_future_holdout": False,
        "status": "available" if available else "degraded",
        "confidence": l3.get("confidence", 0.0),
        "usable_as_prior": available,
        "reason": "" if available else l3.get("reason", "missing_layer3_output"),
        "et0": l3.get("et0", None),
        "water_balance": l3.get("water_balance", None),
        "irrigation_response_rate": l3.get("irrigation_response_rate"),
        "root_zone_transition_rate": l3.get("root_zone_transition_rate"),
    }
