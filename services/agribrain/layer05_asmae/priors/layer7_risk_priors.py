"""V73: Layer 7 risk priors — climate shock risk, forecast uncertainty."""

from __future__ import annotations
from typing import Any, Dict


def extract_layer7_priors(coarse_outputs: dict) -> Dict[str, Any]:
    l7 = coarse_outputs.get("layer7_risk", {})
    available = bool(l7) and l7.get("status") in ("available", "partial")
    return {
        "source_layer": "layer7_risk",
        "source_run_id": l7.get("run_id", ""),
        "source_timestamp": l7.get("timestamp", ""),
        "valid_time_window": l7.get("valid_window", ""),
        "uses_future_holdout": False,
        "status": "available" if available else "degraded",
        "confidence": l7.get("confidence", 0.0),
        "usable_as_prior": available,
        "reason": "" if available else l7.get("reason", "missing_layer7_output"),
        "climate_shock_risk": l7.get("climate_shock_risk"),
        "forecast_uncertainty": l7.get("forecast_uncertainty"),
        "future_stress_windows": l7.get("future_stress_windows", []),
    }
