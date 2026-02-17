
# Evidence Weights Configuration (Calibration Hook)

# Calibrated evidence weights (logit_delta)
# Positive = Supports Threat
# Negative = Contra-Evidence

EVIDENCE_WEIGHTS = {
    # WDP Signals
    "fungal_pressure_high": 1.6,   # Was 1.4 -> Tuned to 1.6
    "bacterial_pressure_high": 1.2,
    "insect_pressure_high": 1.5,   # Was 1.2 -> Tuned to 1.5
    
    # Spatial Signals
    "ndvi_drop_patchy": 0.9,
    "patchy_spread_signature": 0.8,
    
    # Contra-Evidence (Confounders)
    "water_stress_uniform": -1.5,
    "n_def_uniform": -1.2,
}
