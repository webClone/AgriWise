"""V73: Layer 5 biotic confounder priors — disease risk, outbreak probability."""

from __future__ import annotations
from typing import Any, Dict


def extract_layer5_priors(coarse_outputs: dict) -> Dict[str, Any]:
    l5 = coarse_outputs.get("layer5_biotic", {})
    available = bool(l5) and l5.get("status") in ("available", "partial")
    return {
        "source_layer": "layer5_biotic",
        "source_run_id": l5.get("run_id", ""),
        "source_timestamp": l5.get("timestamp", ""),
        "valid_time_window": l5.get("valid_window", ""),
        "uses_future_holdout": False,
        "status": "available" if available else "degraded",
        "confidence": l5.get("confidence", 0.0),
        "usable_as_prior": available,
        "reason": "" if available else l5.get("reason", "missing_layer5_output"),
        "biotic_threat_risk": l5.get("biotic_threat_risk"),
        "weather_disease_suitability": l5.get("weather_disease_suitability"),
        "outbreak_probability": l5.get("outbreak_probability"),
    }
