"""V73: Layer 6 yield sensitivity priors."""

from __future__ import annotations
from typing import Any, Dict


def extract_layer6_priors(coarse_outputs: dict) -> Dict[str, Any]:
    l6 = coarse_outputs.get("layer6_yield", {})
    available = bool(l6) and l6.get("status") in ("available", "partial")
    return {
        "source_layer": "layer6_yield",
        "source_run_id": l6.get("run_id", ""),
        "source_timestamp": l6.get("timestamp", ""),
        "valid_time_window": l6.get("valid_window", ""),
        "uses_future_holdout": False,
        "status": "available" if available else "degraded",
        "confidence": l6.get("confidence", 0.0),
        "usable_as_prior": available,
        "reason": "" if available else l6.get("reason", "missing_layer6_output"),
        "yield_sensitivity": l6.get("yield_sensitivity"),
        "economic_value_of_confidence": l6.get("economic_value"),
        "scouting_priority": l6.get("scouting_priority"),
    }
