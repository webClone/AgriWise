"""V73: Layer 4 nutrient priors — nutrient demand, chlorophyll proxy, salinity."""

from __future__ import annotations
from typing import Any, Dict


def extract_layer4_priors(coarse_outputs: dict) -> Dict[str, Any]:
    l4 = coarse_outputs.get("layer4_nutrients", {})
    available = bool(l4) and l4.get("status") in ("available", "partial")
    return {
        "source_layer": "layer4_nutrients",
        "source_run_id": l4.get("run_id", ""),
        "source_timestamp": l4.get("timestamp", ""),
        "valid_time_window": l4.get("valid_window", ""),
        "uses_future_holdout": False,
        "status": "available" if available else "degraded",
        "confidence": l4.get("confidence", 0.0),
        "usable_as_prior": available,
        "reason": "" if available else l4.get("reason", "missing_layer4_output"),
        "nutrient_demand": l4.get("nutrient_demand", None),
        "chlorophyll_proxy": l4.get("chlorophyll_proxy", None),
        "salinity_risk": l4.get("salinity_risk"),
        "fertilizer_response_delay_days": l4.get("fertilizer_response_delay_days"),
    }
