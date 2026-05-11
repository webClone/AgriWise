
# Evidence Weights Configuration (Calibration Hook)

# Calibrated evidence weights (logit_delta)
# Positive = Supports Threat
# Negative = Contra-Evidence

EVIDENCE_WEIGHTS = {
    # ── WDP Signals ──────────────────────────────────────────────────────
    "fungal_pressure_high": 1.6,
    "bacterial_pressure_high": 1.2,
    "insect_pressure_high": 1.5,

    # ── Leaf Wetness Duration (New Science) ──────────────────────────────
    "lwd_extended": 1.8,           # LWD > 8h — strong fungal/bacterial signal
    "lwd_moderate": 1.0,           # LWD 4-8h — moderate signal
    "lwd_dew_point_depression": 1.4,  # Narrow dew-point depression → prolonged leaf wetness

    # ── Mildew Signals ───────────────────────────────────────────────────
    "downy_mildew_wetness": 1.4,   # Prolonged wetness + moderate temps + clay
    "powdery_mildew_dry_oscillation": 1.1,  # Dry + temp oscillation
    "powdery_mildew_humidity_moderate": 0.8,  # Moderate humidity without rain

    # ── Borer / Insect Signals ───────────────────────────────────────────
    "borer_degree_day": 1.3,       # Cumulative degree-days above base
    "borer_structural_damage": 1.5,  # Structural anomaly from L2

    # ── Weed Spatial ─────────────────────────────────────────────────────
    "weed_heterogeneity": 0.9,     # Spatial heterogeneity → weed patchiness
    "weed_growth_stall": 0.7,      # Growth stall in crop (weed competition)

    # ── Spatial Signals ──────────────────────────────────────────────────
    "ndvi_drop_patchy": 0.9,
    "patchy_spread_signature": 0.8,

    # ── Spore Dispersal (New Science) ────────────────────────────────────
    "downwind_spore_risk": 1.2,    # Adjacent field infection + downwind vector
    "upwind_safe": -0.6,           # Upwind from source → lower risk

    # ── Contra-Evidence (Confounders) ────────────────────────────────────
    "water_stress_uniform": -1.5,
    "n_def_uniform": -1.2,

    # ── L3 Structural Confounders ────────────────────────────────────────
    "l3_water_stress_confounder": -1.3,  # L3 water stress explains NDVI drop
    "l3_weed_competition_confounder": -0.8,  # L3 weed already diagnosed
    "l3_mechanical_damage_confounder": -1.0,  # Mechanical damage mimics biotic
}
