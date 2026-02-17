
from typing import Dict, Any
from services.agribrain.layer5_bio.schema import SpreadPattern

def infer_spread_signature(field_tensor, veg_output, plot_context: Dict[str, Any]) -> Dict[str, Any]:
    # Use L2 stability outputs if present; fallback using heuristics if needed
    spread = SpreadPattern.UNKNOWN
    strength = 0.3

    stability = getattr(veg_output, "stability", None)
    if stability:
        cls = getattr(stability, "class_label", None) or getattr(stability, "stability_class", None)
        mean_var = getattr(stability, "mean_spatial_variance", None)
        std_var = getattr(stability, "std_spatial_variance", None)

        # very typical: hetero/transient -> patchy spread signature
        # Check against L2 string enums (STABLE, HETEROGENEOUS, etc)
        if cls and str(cls).upper().find("HETER") >= 0:
            spread = SpreadPattern.PATCHY
            strength = 0.75
        elif cls and str(cls).upper().find("TRANS") >= 0:
            spread = SpreadPattern.PATCHY
            strength = 0.65
        elif cls and str(cls).upper().find("STABLE") >= 0:
            spread = SpreadPattern.UNIFORM
            strength = 0.55

        # numeric refinement if present
        if mean_var is not None and std_var is not None:
            if float(mean_var) > 0.25 and float(std_var) > 0.10:
                spread = SpreadPattern.PATCHY
                strength = max(strength, 0.8)

    return {"pattern": spread, "strength": float(strength)}
