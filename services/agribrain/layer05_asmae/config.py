"""
ASMAE Configuration.

Central configuration for the Adaptive Scientific MicroZone Assimilation Engine.
All runtime parameters, feature flags, and physical bounds defined here.
"""

from __future__ import annotations

# ── Version ──────────────────────────────────────────────────────────────────

ASMAE_VERSION = "0.5.0"
ASMAE_SCHEMA_VERSION = "asmae_v4_always_on_worldline"

# ── R5.0: State Schema Version ──────────────────────────────────────────────
# Frozen state schema. Must enter every run identity, cache key,
# and serialized artifact. Changing state ordering or count is a
# dedicated migration release, not combined with other changes.

STATE_SCHEMA_VERSION = "asmae_state_v1_13"

STATE_ORDER = (
    "vigor", "lai", "chlorophyll", "canopy_water", "root_zone_water",
    "surface_wetness_event", "structure", "bare_soil_fraction",
    "salinity_stress", "thermal_stress", "biotic_confounder_risk",
    "phenology_progress", "stress_memory",
)

# R5.0: Authority Contract Version
AUTHORITY_CONTRACT_VERSION = "authority_v1"

# R5.0: Resolution Contract Version
RESOLUTION_CONTRACT_VERSION = "resolution_v1"

# R5.0: Observation Contract Version
OBSERVATION_CONTRACT_VERSION = "observation_v1"

# R5.0: Forecast Contract Version
FORECAST_CONTRACT_VERSION = "forecast_v1"

# Cross-check: STATE_ORDER must match STATE_NAMES
assert tuple(STATE_ORDER) == tuple(STATE_NAMES) if 'STATE_NAMES' in dir() else True

# ── Feature Flag ─────────────────────────────────────────────────────────────
# Computation is always diagnostic for a valid plot unless the emergency kill
# switch is active. This legacy key now controls production/visual authority,
# not whether evidence can be inspected.

ASMAE_FEATURE_FLAG = "asmae_enabled"

# ── Candidate Resolutions ────────────────────────────────────────────────────

CANDIDATE_RESOLUTIONS_M = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
DEFAULT_RESOLUTION_M = 10
MIN_CERTIFICATION_RESOLUTION_M = 1

# ── State Vector ─────────────────────────────────────────────────────────────

N_STATES = 13

STATE_NAMES = [
    "vigor",                    # 0  — canopy photosynthetic activity
    "lai",                      # 1  — leaf area index
    "chlorophyll",              # 2  — foliar chlorophyll content
    "canopy_water",             # 3  — canopy water content (NDMI-driven)
    "root_zone_water",          # 4  — root-zone soil moisture
    "surface_wetness_event",    # 5  — event-based surface water (SAR/NDWI)
    "structure",                # 6  — canopy/biomass structure (SAR VH)
    "bare_soil_fraction",       # 7  — exposed soil fraction
    "salinity_stress",          # 8  — salinity-induced stress
    "thermal_stress",           # 9  — thermal stress
    "biotic_confounder_risk",   # 10 — biotic pressure confounding risk
    "phenology_progress",       # 11 — phenological stage progress
    "stress_memory",            # 12 — EWMA stress accumulator
]

# State indices (for readable matrix operations)
IDX_VIGOR = 0
IDX_LAI = 1
IDX_CHLOROPHYLL = 2
IDX_CANOPY_WATER = 3
IDX_ROOT_ZONE_WATER = 4
IDX_SURFACE_WETNESS = 5
IDX_STRUCTURE = 6
IDX_BARE_SOIL = 7
IDX_SALINITY = 8
IDX_THERMAL = 9
IDX_BIOTIC = 10
IDX_PHENOLOGY = 11
IDX_STRESS_MEMORY = 12

# ── Physical Bounds ──────────────────────────────────────────────────────────
# [min, max] for each state variable. Kalman updates are clamped to these.

STATE_BOUNDS = {
    "vigor":                   (0.0, 1.0),
    "lai":                     (0.0, 8.0),
    "chlorophyll":             (0.0, 80.0),   # μg/cm²
    "canopy_water":            (0.0, 1.0),
    "root_zone_water":         (0.0, 1.0),    # volumetric fraction
    "surface_wetness_event":   (0.0, 1.0),
    "structure":               (0.0, 1.0),
    "bare_soil_fraction":      (0.0, 1.0),
    "salinity_stress":         (0.0, 1.0),
    "thermal_stress":          (0.0, 1.0),
    "biotic_confounder_risk":  (0.0, 1.0),
    "phenology_progress":      (0.0, 1.0),    # 0 = bare soil, 1 = harvest
    "stress_memory":           (0.0, 1.0),
}

# ── Ensemble / EnKF ──────────────────────────────────────────────────────────

DEFAULT_ENSEMBLE_SIZE = 50
MAX_ENSEMBLE_SIZE = 200
MIN_ENSEMBLE_SIZE = 20

# ── Scene Stack ──────────────────────────────────────────────────────────────

MIN_S2_SCENES_OPTICAL_MODE = 3
MIN_S1_SCENES_SAR_ASSISTED = 2
SCENE_QUALITY_THRESHOLD = 0.3    # Below this, scene is excluded

# ── Radiometric Consistency ──────────────────────────────────────────────────

RADIOMETRIC_CONSISTENCY_THRESHOLD = 0.15  # RMSE threshold for pass
RADIOMETRIC_HARD_REJECT = 0.30            # Above this, hard reject

# ── Retrovalidation ─────────────────────────────────────────────────────────

RETRO_SCORE_1M_THRESHOLD = 0.75   # Minimum for 1m certification
RETRO_SCORE_5M_THRESHOLD = 0.50   # Minimum for 5m+ resolution

# ── BMA ──────────────────────────────────────────────────────────────────────

BMA_TEMPERATURE = 0.5
BMA_DISAGREEMENT_DEMOTION_THRESHOLD = 0.20

# ── Weak Labels ──────────────────────────────────────────────────────────────

WEAK_LABEL_MAX_WEIGHT = 0.3       # Weak labels are never treated as ground truth
WEAK_LABEL_MIN_RETRO_SCORE = 0.5  # Minimum retrovalidation to export

# ── Modes ────────────────────────────────────────────────────────────────────

ASMAE_MODES = (
    "shadow",           # Run alongside production, no output used
    "visual",           # Generate visual surfaces only
    "state_update",     # Full state estimation
    "training_export",  # Export weak labels for learning
    "certification",    # Full certification pipeline
    "quick_visual",     # Fast visual-only rendering
    "standard",         # Standard production execution
    "scientific_refresh", # Force full recomputation
    "retrovalidation",  # Deep retrovalidation evaluation
)

# ── V71: Graph Smoothing (Conservative Defaults) ────────────────────────────

GRAPH_BASE_LAPLACIAN_STRENGTH = 0.12
GRAPH_ROW_ALIGNED_MULTIPLIER = 1.8        # Stronger along crop rows
GRAPH_CROSS_ROW_MULTIPLIER = 0.5          # Weaker across crop rows
GRAPH_EDGE_PENALTY_MULTIPLIER = 0.0       # Zero across field boundary
GRAPH_SOIL_DISCONTINUITY_MULTIPLIER = 0.3
GRAPH_IRRIGATION_CONNECTIVITY_WEIGHT = 0.6

# ── V72: Observation Model Constants ────────────────────────────────────────

# Per-observation-type radiometric thresholds (not one global 0.15)
RADIOMETRIC_THRESHOLDS_BY_OBS = {
    "ndvi":     {"pass": 0.15, "reject": 0.30},
    "evi":      {"pass": 0.12, "reject": 0.25},
    "ndre":     {"pass": 0.15, "reject": 0.30},
    "reip":     {"pass": 0.15, "reject": 0.30},
    "ndmi":     {"pass": 0.15, "reject": 0.30},
    "ndwi":     {"pass": 0.20, "reject": 0.40},
    "bsi":      {"pass": 0.18, "reject": 0.35},
    "nbr":      {"pass": 0.18, "reject": 0.35},
    "sar_vv":   {"pass": 0.25, "reject": 0.45},
    "sar_vh":   {"pass": 0.20, "reject": 0.40},
    "sar_ratio": {"pass": 0.25, "reject": 0.45},
    "stress_memory_index": {"pass": 0.20, "reject": 0.35},
}

# ── V74: Adaptive Ensemble Size Policy ──────────────────────────────────────

ENSEMBLE_SIZE_SHADOW = 20
ENSEMBLE_SIZE_STANDARD = 30             # Interactive standard profile
ENSEMBLE_SIZE_CERTIFICATION = 50        # Certification / calibration / reference
ENSEMBLE_SIZE_LARGE_PLOT = 30           # + localization required
ENSEMBLE_SIZE_OFFLINE = 80              # training_export / certification
LARGE_PLOT_MICROZONE_THRESHOLD = 5000   # Above this, use large-plot policy

# Gaspari-Cohn localization half-width (in microzone-grid units)
LOCALIZATION_HALF_WIDTH = 10

# ── V76: Retrovalidation Tier Thresholds ────────────────────────────────────

RETRO_SCORE_1M_ADVISORY = 0.75         # Advisory / research display
RETRO_SCORE_1M_CERTIFIED_DISPLAY = 0.85  # Plot-certified 1m display
# 1m state update requires external validation — no numeric threshold alone

# ── V77: Causal Vocabulary ──────────────────────────────────────────────────

CAUSAL_STATUS_VOCABULARY = (
    "suspected",
    "supported",
    "contradicted",
    "unknown",
    "externally_confirmed",
)

CAUSE_HYPOTHESES = (
    "water_stress",
    "nutrient_stress",
    "surface_wetness_event",
    "salinity_constraint",
    "thermal_stress",
    "biotic_confounder_possible",
    "harvest_reset",
    "tillage_reset",
    "mechanical_damage",
    "soil_constraint",
    "unknown",
)

# ── V79A: Retrovalidation Component Weights ─────────────────────────────────

RETRO_WEIGHTS = {
    "future": 0.30,
    "radiometric": 0.20,
    "temporal": 0.15,
    "spatial": 0.15,
    "causal": 0.10,
    "calibration": 0.10,
}

# Alias for tier threshold
RETRO_SCORE_1M_CERTIFIED = RETRO_SCORE_1M_CERTIFIED_DISPLAY

# ── V79A: BMA Expert Registry ───────────────────────────────────────────────

BMA_EXPERTS = (
    "optical_physiology",
    "sar_structure",
    "water_balance",
    "spatial_smooth",
    "phenology_memory",
)

# ── V88: ML Experts BMA Configuration ────────────────────────────────────────

import os

ASMAE_ML_EXPERTS_ENABLED = os.environ.get("ASMAE_ML_EXPERTS_ENABLED", "false").lower() == "true"
ASMAE_ML_EXPERTS_SHADOW_ONLY = os.environ.get("ASMAE_ML_EXPERTS_SHADOW_ONLY", "true").lower() == "true"

ML_EXPERT_MAX_WEIGHT = 0.15
COMBINED_ML_EXPERT_MAX_WEIGHT = 0.30
PHYSICS_EXPERT_MIN_COMBINED_WEIGHT = 0.70


def archive_status_ok(status: str | None) -> bool:
    if not status:
        return False
    return status.lower() in ("success", "available", "completed")
