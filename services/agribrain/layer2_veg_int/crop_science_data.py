"""
Crop Identification Scientific Reference Data
=============================================
Per-crop NDVI signatures, regional crop calendars, multi-spectral
discriminators, Köppen affinity matrix, and agronomic rotation rules.

Scientific provenance is mixed and must remain explicit. A curated subset is
based on the references below; registry coverage missing from those tables is
filled with architecture-level agronomic defaults. Those defaults are useful
for coarse crop-group priors, but are not measured species signatures and
must never be presented as calibrated species evidence.

References used for the curated subset include:
  - Wardlow & Egbert (2008): MODIS NDVI time-series
  - Xiao et al. (2005): Spectral indices for rice/crop mapping
  - FAO Crop Calendar & ASAP-JRC dataset
  - Beck et al. (2018): Köppen-Geiger climate classification
  - Bolton & Friedl (2013): Phenology-based identification
  - Jonsson & Eklundh (2002): NDVI curve shape analysis
  - FAO (2012): North Africa crop statistics
"""

from typing import Dict, Optional, Tuple

# =============================================================================
# MODULE A: Per-Crop NDVI Reference Signatures
# =============================================================================
# Curated entries describe reference phenological envelopes. Expanded entries
# are shared agronomic defaults and are not unique crop fingerprints.
# Fields:
#   shape: "unimodal" | "bimodal" | "evergreen" | "stable" | "multi_cut"
#   peak_ndvi: typical maximum NDVI value
#   trough_ndvi: minimum NDVI during growing cycle
#   peak_frac: when peak occurs as fraction of growing season [0-1]
#   greenup_rate: NDVI units per day during green-up
#   amplitude: peak - trough
#   season_integral: normalized area under NDVI curve (relative to wheat=1.0)
#   los_frac: length of season as fraction of year (0-1); 1.0 = year-round (evergreen)

CROP_NDVI_SIGNATURES: Dict[str, dict] = {
    # ── CEREALS ──
    "wheat":         {"shape": "unimodal", "peak_ndvi": 0.75, "trough_ndvi": 0.12, "peak_frac": 0.45, "greenup_rate": 0.006, "amplitude": 0.63, "season_integral": 1.00, "n_peaks": 1},
    "durum_wheat":   {"shape": "unimodal", "peak_ndvi": 0.72, "trough_ndvi": 0.12, "peak_frac": 0.45, "greenup_rate": 0.006, "amplitude": 0.60, "season_integral": 0.95, "n_peaks": 1},
    "emmer":         {"shape": "unimodal", "peak_ndvi": 0.68, "trough_ndvi": 0.12, "peak_frac": 0.43, "greenup_rate": 0.005, "amplitude": 0.56, "season_integral": 0.88, "n_peaks": 1},
    "barley":        {"shape": "unimodal", "peak_ndvi": 0.70, "trough_ndvi": 0.12, "peak_frac": 0.40, "greenup_rate": 0.007, "amplitude": 0.58, "season_integral": 0.85, "n_peaks": 1},
    "oat":           {"shape": "unimodal", "peak_ndvi": 0.68, "trough_ndvi": 0.12, "peak_frac": 0.42, "greenup_rate": 0.006, "amplitude": 0.56, "season_integral": 0.82, "n_peaks": 1},
    "rye":           {"shape": "unimodal", "peak_ndvi": 0.66, "trough_ndvi": 0.10, "peak_frac": 0.42, "greenup_rate": 0.006, "amplitude": 0.56, "season_integral": 0.85, "n_peaks": 1},
    "triticale":     {"shape": "unimodal", "peak_ndvi": 0.72, "trough_ndvi": 0.12, "peak_frac": 0.44, "greenup_rate": 0.006, "amplitude": 0.60, "season_integral": 0.92, "n_peaks": 1},
    "spelt":         {"shape": "unimodal", "peak_ndvi": 0.70, "trough_ndvi": 0.12, "peak_frac": 0.45, "greenup_rate": 0.005, "amplitude": 0.58, "season_integral": 0.90, "n_peaks": 1},
    "sorghum":       {"shape": "unimodal", "peak_ndvi": 0.78, "trough_ndvi": 0.10, "peak_frac": 0.55, "greenup_rate": 0.008, "amplitude": 0.68, "season_integral": 1.05, "n_peaks": 1},
    "millet":        {"shape": "unimodal", "peak_ndvi": 0.65, "trough_ndvi": 0.10, "peak_frac": 0.50, "greenup_rate": 0.009, "amplitude": 0.55, "season_integral": 0.70, "n_peaks": 1},
    "canola":        {"shape": "unimodal", "peak_ndvi": 0.78, "trough_ndvi": 0.15, "peak_frac": 0.40, "greenup_rate": 0.007, "amplitude": 0.63, "season_integral": 0.95, "n_peaks": 1},
    "sunflower":     {"shape": "unimodal", "peak_ndvi": 0.72, "trough_ndvi": 0.12, "peak_frac": 0.50, "greenup_rate": 0.007, "amplitude": 0.60, "season_integral": 0.90, "n_peaks": 1},
    "quinoa":        {"shape": "unimodal", "peak_ndvi": 0.55, "trough_ndvi": 0.10, "peak_frac": 0.48, "greenup_rate": 0.005, "amplitude": 0.45, "season_integral": 0.60, "n_peaks": 1},
    "flax":          {"shape": "unimodal", "peak_ndvi": 0.60, "trough_ndvi": 0.12, "peak_frac": 0.45, "greenup_rate": 0.005, "amplitude": 0.48, "season_integral": 0.65, "n_peaks": 1},

    # ── MAIZE ──
    "corn":          {"shape": "unimodal", "peak_ndvi": 0.85, "trough_ndvi": 0.10, "peak_frac": 0.55, "greenup_rate": 0.010, "amplitude": 0.75, "season_integral": 1.15, "n_peaks": 1},
    "sweet_corn":    {"shape": "unimodal", "peak_ndvi": 0.80, "trough_ndvi": 0.10, "peak_frac": 0.50, "greenup_rate": 0.009, "amplitude": 0.70, "season_integral": 1.00, "n_peaks": 1},
    "popcorn":       {"shape": "unimodal", "peak_ndvi": 0.78, "trough_ndvi": 0.10, "peak_frac": 0.52, "greenup_rate": 0.009, "amplitude": 0.68, "season_integral": 0.95, "n_peaks": 1},

    # ── RICE ──
    "rice":          {"shape": "unimodal", "peak_ndvi": 0.72, "trough_ndvi": 0.05, "peak_frac": 0.55, "greenup_rate": 0.007, "amplitude": 0.67, "season_integral": 0.85, "n_peaks": 1},
    "wild_rice":     {"shape": "unimodal", "peak_ndvi": 0.60, "trough_ndvi": 0.05, "peak_frac": 0.50, "greenup_rate": 0.005, "amplitude": 0.55, "season_integral": 0.70, "n_peaks": 1},

    # ── LEGUMES ──
    "chickpea":      {"shape": "unimodal", "peak_ndvi": 0.55, "trough_ndvi": 0.12, "peak_frac": 0.48, "greenup_rate": 0.004, "amplitude": 0.43, "season_integral": 0.55, "n_peaks": 1},
    "lentil":        {"shape": "unimodal", "peak_ndvi": 0.50, "trough_ndvi": 0.12, "peak_frac": 0.45, "greenup_rate": 0.004, "amplitude": 0.38, "season_integral": 0.48, "n_peaks": 1},
    "fava_bean":     {"shape": "unimodal", "peak_ndvi": 0.65, "trough_ndvi": 0.12, "peak_frac": 0.45, "greenup_rate": 0.005, "amplitude": 0.53, "season_integral": 0.70, "n_peaks": 1},
    "pea":           {"shape": "unimodal", "peak_ndvi": 0.58, "trough_ndvi": 0.12, "peak_frac": 0.45, "greenup_rate": 0.005, "amplitude": 0.46, "season_integral": 0.58, "n_peaks": 1},
    "cowpea":        {"shape": "unimodal", "peak_ndvi": 0.60, "trough_ndvi": 0.10, "peak_frac": 0.50, "greenup_rate": 0.006, "amplitude": 0.50, "season_integral": 0.60, "n_peaks": 1},
    "vetch":         {"shape": "unimodal", "peak_ndvi": 0.55, "trough_ndvi": 0.10, "peak_frac": 0.45, "greenup_rate": 0.005, "amplitude": 0.45, "season_integral": 0.55, "n_peaks": 1},
    "soybean":       {"shape": "unimodal", "peak_ndvi": 0.82, "trough_ndvi": 0.12, "peak_frac": 0.55, "greenup_rate": 0.007, "amplitude": 0.70, "season_integral": 1.00, "n_peaks": 1},

    # ── VEGETABLES ──
    "tomato":        {"shape": "unimodal", "peak_ndvi": 0.65, "trough_ndvi": 0.15, "peak_frac": 0.50, "greenup_rate": 0.006, "amplitude": 0.50, "season_integral": 0.65, "n_peaks": 1},
    "potato":        {"shape": "unimodal", "peak_ndvi": 0.72, "trough_ndvi": 0.12, "peak_frac": 0.45, "greenup_rate": 0.007, "amplitude": 0.60, "season_integral": 0.75, "n_peaks": 1},
    "onion":         {"shape": "unimodal", "peak_ndvi": 0.45, "trough_ndvi": 0.12, "peak_frac": 0.40, "greenup_rate": 0.003, "amplitude": 0.33, "season_integral": 0.40, "n_peaks": 1},
    "garlic":        {"shape": "unimodal", "peak_ndvi": 0.42, "trough_ndvi": 0.12, "peak_frac": 0.40, "greenup_rate": 0.003, "amplitude": 0.30, "season_integral": 0.38, "n_peaks": 1},
    "pepper":        {"shape": "unimodal", "peak_ndvi": 0.60, "trough_ndvi": 0.15, "peak_frac": 0.50, "greenup_rate": 0.005, "amplitude": 0.45, "season_integral": 0.55, "n_peaks": 1},
    "eggplant":      {"shape": "unimodal", "peak_ndvi": 0.62, "trough_ndvi": 0.15, "peak_frac": 0.50, "greenup_rate": 0.005, "amplitude": 0.47, "season_integral": 0.58, "n_peaks": 1},
    "cucumber":      {"shape": "unimodal", "peak_ndvi": 0.55, "trough_ndvi": 0.15, "peak_frac": 0.45, "greenup_rate": 0.006, "amplitude": 0.40, "season_integral": 0.45, "n_peaks": 1},
    "watermelon":    {"shape": "unimodal", "peak_ndvi": 0.58, "trough_ndvi": 0.12, "peak_frac": 0.55, "greenup_rate": 0.006, "amplitude": 0.46, "season_integral": 0.52, "n_peaks": 1},
    "melon":         {"shape": "unimodal", "peak_ndvi": 0.55, "trough_ndvi": 0.12, "peak_frac": 0.50, "greenup_rate": 0.005, "amplitude": 0.43, "season_integral": 0.48, "n_peaks": 1},
    "zucchini":      {"shape": "unimodal", "peak_ndvi": 0.50, "trough_ndvi": 0.15, "peak_frac": 0.45, "greenup_rate": 0.005, "amplitude": 0.35, "season_integral": 0.40, "n_peaks": 1},
    "sugar_beet":    {"shape": "unimodal", "peak_ndvi": 0.80, "trough_ndvi": 0.12, "peak_frac": 0.50, "greenup_rate": 0.006, "amplitude": 0.68, "season_integral": 1.10, "n_peaks": 1},
    "carrot":        {"shape": "unimodal", "peak_ndvi": 0.48, "trough_ndvi": 0.12, "peak_frac": 0.50, "greenup_rate": 0.004, "amplitude": 0.36, "season_integral": 0.42, "n_peaks": 1},
    "cabbage":       {"shape": "unimodal", "peak_ndvi": 0.55, "trough_ndvi": 0.12, "peak_frac": 0.50, "greenup_rate": 0.004, "amplitude": 0.43, "season_integral": 0.55, "n_peaks": 1},
    "lettuce":       {"shape": "unimodal", "peak_ndvi": 0.45, "trough_ndvi": 0.12, "peak_frac": 0.40, "greenup_rate": 0.005, "amplitude": 0.33, "season_integral": 0.30, "n_peaks": 1},
    "spinach":       {"shape": "unimodal", "peak_ndvi": 0.50, "trough_ndvi": 0.12, "peak_frac": 0.40, "greenup_rate": 0.005, "amplitude": 0.38, "season_integral": 0.35, "n_peaks": 1},
    "artichoke":     {"shape": "bimodal",  "peak_ndvi": 0.60, "trough_ndvi": 0.20, "peak_frac": 0.35, "greenup_rate": 0.004, "amplitude": 0.40, "season_integral": 0.70, "n_peaks": 2},

    # ── PERENNIALS ──
    "olive":         {"shape": "evergreen", "peak_ndvi": 0.55, "trough_ndvi": 0.40, "peak_frac": 0.35, "greenup_rate": 0.001, "amplitude": 0.15, "season_integral": 1.80, "n_peaks": 0},
    "grape":         {"shape": "unimodal",  "peak_ndvi": 0.60, "trough_ndvi": 0.15, "peak_frac": 0.50, "greenup_rate": 0.004, "amplitude": 0.45, "season_integral": 0.80, "n_peaks": 1},
    "almond":        {"shape": "unimodal",  "peak_ndvi": 0.55, "trough_ndvi": 0.18, "peak_frac": 0.45, "greenup_rate": 0.003, "amplitude": 0.37, "season_integral": 0.75, "n_peaks": 1},
    "fig":           {"shape": "unimodal",  "peak_ndvi": 0.58, "trough_ndvi": 0.15, "peak_frac": 0.50, "greenup_rate": 0.003, "amplitude": 0.43, "season_integral": 0.78, "n_peaks": 1},
    "pomegranate":   {"shape": "unimodal",  "peak_ndvi": 0.55, "trough_ndvi": 0.18, "peak_frac": 0.48, "greenup_rate": 0.003, "amplitude": 0.37, "season_integral": 0.72, "n_peaks": 1},
    "pistachio":     {"shape": "unimodal",  "peak_ndvi": 0.50, "trough_ndvi": 0.15, "peak_frac": 0.50, "greenup_rate": 0.003, "amplitude": 0.35, "season_integral": 0.65, "n_peaks": 1},
    "walnut":        {"shape": "unimodal",  "peak_ndvi": 0.62, "trough_ndvi": 0.12, "peak_frac": 0.50, "greenup_rate": 0.003, "amplitude": 0.50, "season_integral": 0.85, "n_peaks": 1},
    "apricot":       {"shape": "unimodal",  "peak_ndvi": 0.58, "trough_ndvi": 0.15, "peak_frac": 0.45, "greenup_rate": 0.003, "amplitude": 0.43, "season_integral": 0.72, "n_peaks": 1},
    "peach":         {"shape": "unimodal",  "peak_ndvi": 0.60, "trough_ndvi": 0.15, "peak_frac": 0.45, "greenup_rate": 0.004, "amplitude": 0.45, "season_integral": 0.75, "n_peaks": 1},
    "cherry":        {"shape": "unimodal",  "peak_ndvi": 0.58, "trough_ndvi": 0.15, "peak_frac": 0.42, "greenup_rate": 0.004, "amplitude": 0.43, "season_integral": 0.70, "n_peaks": 1},
    "apple":         {"shape": "unimodal",  "peak_ndvi": 0.62, "trough_ndvi": 0.12, "peak_frac": 0.50, "greenup_rate": 0.004, "amplitude": 0.50, "season_integral": 0.85, "n_peaks": 1},
    "pear":          {"shape": "unimodal",  "peak_ndvi": 0.60, "trough_ndvi": 0.12, "peak_frac": 0.48, "greenup_rate": 0.004, "amplitude": 0.48, "season_integral": 0.80, "n_peaks": 1},
    "orange":         {"shape": "evergreen", "peak_ndvi": 0.62, "trough_ndvi": 0.45, "peak_frac": 0.40, "greenup_rate": 0.001, "amplitude": 0.17, "season_integral": 2.00, "n_peaks": 0},
    "lemon":          {"shape": "evergreen", "peak_ndvi": 0.60, "trough_ndvi": 0.42, "peak_frac": 0.40, "greenup_rate": 0.001, "amplitude": 0.18, "season_integral": 1.95, "n_peaks": 0},
    "mandarin":       {"shape": "evergreen", "peak_ndvi": 0.60, "trough_ndvi": 0.43, "peak_frac": 0.40, "greenup_rate": 0.001, "amplitude": 0.17, "season_integral": 1.98, "n_peaks": 0},
    "citrus":         {"shape": "evergreen", "peak_ndvi": 0.61, "trough_ndvi": 0.44, "peak_frac": 0.40, "greenup_rate": 0.001, "amplitude": 0.17, "season_integral": 1.97, "n_peaks": 0},
    "grapefruit":     {"shape": "evergreen", "peak_ndvi": 0.63, "trough_ndvi": 0.46, "peak_frac": 0.40, "greenup_rate": 0.001, "amplitude": 0.17, "season_integral": 2.05, "n_peaks": 0},
    # Aliases for backward compat
    "citrus_orange":  {"shape": "evergreen", "peak_ndvi": 0.62, "trough_ndvi": 0.45, "peak_frac": 0.40, "greenup_rate": 0.001, "amplitude": 0.17, "season_integral": 2.00, "n_peaks": 0},
    "citrus_lemon":   {"shape": "evergreen", "peak_ndvi": 0.60, "trough_ndvi": 0.42, "peak_frac": 0.40, "greenup_rate": 0.001, "amplitude": 0.18, "season_integral": 1.95, "n_peaks": 0},
    "citrus_group":   {"shape": "evergreen", "peak_ndvi": 0.61, "trough_ndvi": 0.44, "peak_frac": 0.40, "greenup_rate": 0.001, "amplitude": 0.17, "season_integral": 1.97, "n_peaks": 0},

    # ── TROPICAL TREES ──
    "date_palm":     {"shape": "stable",    "peak_ndvi": 0.72, "trough_ndvi": 0.58, "peak_frac": 0.40, "greenup_rate": 0.001, "amplitude": 0.14, "season_integral": 2.40, "n_peaks": 0},
    "banana":        {"shape": "stable",    "peak_ndvi": 0.78, "trough_ndvi": 0.60, "peak_frac": 0.45, "greenup_rate": 0.001, "amplitude": 0.18, "season_integral": 2.50, "n_peaks": 0},
    "mango":         {"shape": "evergreen", "peak_ndvi": 0.70, "trough_ndvi": 0.45, "peak_frac": 0.50, "greenup_rate": 0.002, "amplitude": 0.25, "season_integral": 2.20, "n_peaks": 0},
    "coconut":       {"shape": "stable",    "peak_ndvi": 0.75, "trough_ndvi": 0.60, "peak_frac": 0.50, "greenup_rate": 0.001, "amplitude": 0.15, "season_integral": 2.50, "n_peaks": 0},

    # ── FORAGE / MULTI-CUT ──
    "alfalfa":       {"shape": "multi_cut", "peak_ndvi": 0.70, "trough_ndvi": 0.15, "peak_frac": 0.30, "greenup_rate": 0.008, "amplitude": 0.55, "season_integral": 1.50, "n_peaks": 4},
    "clover":        {"shape": "multi_cut", "peak_ndvi": 0.65, "trough_ndvi": 0.20, "peak_frac": 0.30, "greenup_rate": 0.006, "amplitude": 0.45, "season_integral": 1.30, "n_peaks": 3},
    "ryegrass":      {"shape": "multi_cut", "peak_ndvi": 0.62, "trough_ndvi": 0.18, "peak_frac": 0.35, "greenup_rate": 0.005, "amplitude": 0.44, "season_integral": 1.20, "n_peaks": 3},

    # ── COTTON ──
    "cotton":        {"shape": "unimodal", "peak_ndvi": 0.72, "trough_ndvi": 0.10, "peak_frac": 0.50, "greenup_rate": 0.006, "amplitude": 0.62, "season_integral": 0.90, "n_peaks": 1},

    # ── HERBS/SPICES ──
    "saffron":       {"shape": "unimodal", "peak_ndvi": 0.40, "trough_ndvi": 0.08, "peak_frac": 0.35, "greenup_rate": 0.004, "amplitude": 0.32, "season_integral": 0.30, "n_peaks": 1},
    "cumin":         {"shape": "unimodal", "peak_ndvi": 0.42, "trough_ndvi": 0.10, "peak_frac": 0.45, "greenup_rate": 0.004, "amplitude": 0.32, "season_integral": 0.32, "n_peaks": 1},
    "coriander":     {"shape": "unimodal", "peak_ndvi": 0.45, "trough_ndvi": 0.10, "peak_frac": 0.45, "greenup_rate": 0.004, "amplitude": 0.35, "season_integral": 0.35, "n_peaks": 1},
}


# =============================================================================
# MODULE B: Regional Crop Calendar Windows (MENA focus, Algeria priority)
# =============================================================================
# Sowing and harvesting DOY ranges per climate region.
# DOY = day of year (1-365). Ranges wrap for winter crops (sow > harvest).

CROP_CALENDARS: Dict[str, Dict[str, dict]] = {
    # Algeria Mediterranean (Tell Atlas, Mitidja, Kabylie)
    "algeria_mediterranean": {
        "wheat":        {"sow_start": 244, "sow_end": 350, "harvest_start": 152, "harvest_end": 196},  # Sep-Dec → Jun-Jul
        "durum_wheat":  {"sow_start": 244, "sow_end": 335, "harvest_start": 152, "harvest_end": 196},  # Sep-Nov → Jun-Jul
        "emmer":        {"sow_start": 244, "sow_end": 350, "harvest_start": 152, "harvest_end": 196},
        "barley":       {"sow_start": 244, "sow_end": 335, "harvest_start": 152, "harvest_end": 182},  # Sep-Nov → Jun
        "oat":          {"sow_start": 274, "sow_end": 335, "harvest_start": 152, "harvest_end": 196},  # Oct-Nov → Jun-Jul
        "triticale":    {"sow_start": 274, "sow_end": 335, "harvest_start": 152, "harvest_end": 196},
        "canola":       {"sow_start": 274, "sow_end": 335, "harvest_start": 152, "harvest_end": 182},
        "chickpea":     {"sow_start": 1,   "sow_end": 60,  "harvest_start": 152, "harvest_end": 182},   # Jan-Feb → Jun
        "lentil":       {"sow_start": 1,   "sow_end": 60,  "harvest_start": 135, "harvest_end": 166},   # Jan-Feb → May-Jun
        "fava_bean":    {"sow_start": 274, "sow_end": 335, "harvest_start": 121, "harvest_end": 166},   # Oct-Nov → May-Jun
        "pea":          {"sow_start": 274, "sow_end": 335, "harvest_start": 121, "harvest_end": 152},   # Oct-Nov → May
        "vetch":        {"sow_start": 274, "sow_end": 335, "harvest_start": 121, "harvest_end": 166},
        "tomato":       {"sow_start": 60,  "sow_end": 120, "harvest_start": 152, "harvest_end": 274},   # Mar-Apr → Jun-Oct
        "potato":       {"sow_start": 32,  "sow_end": 91,  "harvest_start": 152, "harvest_end": 213},   # Feb-Mar → Jun-Jul
        "onion":        {"sow_start": 244, "sow_end": 305, "harvest_start": 121, "harvest_end": 182},   # Sep-Oct → May-Jun
        "garlic":       {"sow_start": 244, "sow_end": 305, "harvest_start": 152, "harvest_end": 196},   # Sep-Oct → Jun-Jul
        "pepper":       {"sow_start": 60,  "sow_end": 120, "harvest_start": 152, "harvest_end": 274},
        "eggplant":     {"sow_start": 60,  "sow_end": 120, "harvest_start": 152, "harvest_end": 274},
        "cucumber":     {"sow_start": 60,  "sow_end": 120, "harvest_start": 121, "harvest_end": 244},
        "watermelon":   {"sow_start": 60,  "sow_end": 120, "harvest_start": 182, "harvest_end": 274},   # Mar-Apr → Jul-Oct
        "melon":        {"sow_start": 60,  "sow_end": 120, "harvest_start": 182, "harvest_end": 274},
        "sugar_beet":   {"sow_start": 244, "sow_end": 335, "harvest_start": 152, "harvest_end": 244},   # Sep-Nov → Jun-Aug
        "carrot":       {"sow_start": 244, "sow_end": 60,  "harvest_start": 91,  "harvest_end": 182},   # Sep-Feb → Apr-Jun
        "olive":        {"sow_start": None, "sow_end": None, "harvest_start": 305, "harvest_end": 31},   # Nov-Jan
        "grape":        {"sow_start": None, "sow_end": None, "harvest_start": 213, "harvest_end": 305},  # Aug-Oct
        "almond":       {"sow_start": None, "sow_end": None, "harvest_start": 213, "harvest_end": 274},  # Aug-Sep
        "fig":          {"sow_start": None, "sow_end": None, "harvest_start": 182, "harvest_end": 274},  # Jul-Oct
        "pomegranate":  {"sow_start": None, "sow_end": None, "harvest_start": 244, "harvest_end": 335},  # Sep-Nov
        "orange":       {"sow_start": None, "sow_end": None, "harvest_start": 305, "harvest_end": 152},  # Nov-May
        "lemon":        {"sow_start": None, "sow_end": None, "harvest_start": 274, "harvest_end": 152},  # Oct-May
        "mandarin":     {"sow_start": None, "sow_end": None, "harvest_start": 305, "harvest_end": 91},   # Nov-Mar (clementine)
        "citrus":       {"sow_start": None, "sow_end": None, "harvest_start": 274, "harvest_end": 152},  # Oct-May
        "grapefruit":   {"sow_start": None, "sow_end": None, "harvest_start": 305, "harvest_end": 121},  # Nov-Apr
        "date_palm":    {"sow_start": None, "sow_end": None, "harvest_start": 244, "harvest_end": 335},  # Sep-Nov
        "cotton":       {"sow_start": 91,  "sow_end": 135, "harvest_start": 244, "harvest_end": 305},   # Apr-May → Sep-Oct
        "alfalfa":      {"sow_start": 60,  "sow_end": 120, "harvest_start": 121, "harvest_end": 335},   # Mar-Apr → May-Nov (multi-cut)
        "sunflower":    {"sow_start": 60,  "sow_end": 120, "harvest_start": 213, "harvest_end": 274},   # Mar-Apr → Aug-Sep
        "corn":         {"sow_start": 91,  "sow_end": 135, "harvest_start": 213, "harvest_end": 274},   # Apr-May → Aug-Sep
        "sorghum":      {"sow_start": 91,  "sow_end": 152, "harvest_start": 244, "harvest_end": 305},   # Apr-Jun → Sep-Oct
        "soybean":      {"sow_start": 91,  "sow_end": 152, "harvest_start": 244, "harvest_end": 305},
        "rice":         {"sow_start": 121, "sow_end": 152, "harvest_start": 244, "harvest_end": 305},   # May → Sep-Oct
    },

    # Algeria Saharan (Adrar, Biskra, El Oued, Ghardaia)
    "algeria_saharan": {
        "date_palm":    {"sow_start": None, "sow_end": None, "harvest_start": 244, "harvest_end": 335},
        "wheat":        {"sow_start": 305, "sow_end": 350, "harvest_start": 91,  "harvest_end": 135},   # Nov-Dec → Apr-May (irrigated)
        "barley":       {"sow_start": 305, "sow_end": 350, "harvest_start": 91,  "harvest_end": 121},
        "tomato":       {"sow_start": 244, "sow_end": 305, "harvest_start": 335, "harvest_end": 91},    # Sep-Oct → Dec-Mar (greenhouse)
        "pepper":       {"sow_start": 244, "sow_end": 305, "harvest_start": 335, "harvest_end": 91},
        "watermelon":   {"sow_start": 32,  "sow_end": 60,  "harvest_start": 121, "harvest_end": 182},
        "alfalfa":      {"sow_start": 244, "sow_end": 305, "harvest_start": 1,   "harvest_end": 335},   # Year-round multi-cut
        "corn":         {"sow_start": 60,  "sow_end": 91,  "harvest_start": 152, "harvest_end": 213},
        "olive":        {"sow_start": None, "sow_end": None, "harvest_start": 305, "harvest_end": 31},
    },

    # Broader MENA Mediterranean (Morocco, Tunisia, Libya coast)
    "mena_mediterranean": {
        "wheat":        {"sow_start": 305, "sow_end": 350, "harvest_start": 152, "harvest_end": 196},
        "barley":       {"sow_start": 305, "sow_end": 350, "harvest_start": 135, "harvest_end": 182},
        "olive":        {"sow_start": None, "sow_end": None, "harvest_start": 305, "harvest_end": 60},
        "orange":       {"sow_start": None, "sow_end": None, "harvest_start": 274, "harvest_end": 152},
        "lemon":        {"sow_start": None, "sow_end": None, "harvest_start": 274, "harvest_end": 152},
        "mandarin":     {"sow_start": None, "sow_end": None, "harvest_start": 305, "harvest_end": 91},
        "citrus":       {"sow_start": None, "sow_end": None, "harvest_start": 274, "harvest_end": 152},
        "grapefruit":   {"sow_start": None, "sow_end": None, "harvest_start": 305, "harvest_end": 121},
        "tomato":       {"sow_start": 60,  "sow_end": 121, "harvest_start": 152, "harvest_end": 274},
        "potato":       {"sow_start": 32,  "sow_end": 91,  "harvest_start": 152, "harvest_end": 213},
        "chickpea":     {"sow_start": 1,   "sow_end": 60,  "harvest_start": 152, "harvest_end": 182},
        "date_palm":    {"sow_start": None, "sow_end": None, "harvest_start": 244, "harvest_end": 335},
        "corn":         {"sow_start": 91,  "sow_end": 152, "harvest_start": 213, "harvest_end": 274},
    },

    # MENA Arid (Egypt Nile Valley, Iraq, Jordan, Gulf)
    "mena_arid": {
        "wheat":        {"sow_start": 305, "sow_end": 350, "harvest_start": 91,  "harvest_end": 135},
        "rice":         {"sow_start": 121, "sow_end": 182, "harvest_start": 244, "harvest_end": 305},
        "corn":         {"sow_start": 121, "sow_end": 182, "harvest_start": 244, "harvest_end": 305},
        "cotton":       {"sow_start": 60,  "sow_end": 121, "harvest_start": 244, "harvest_end": 305},
        "date_palm":    {"sow_start": None, "sow_end": None, "harvest_start": 244, "harvest_end": 335},
        "tomato":       {"sow_start": 244, "sow_end": 335, "harvest_start": 1,   "harvest_end": 121},
        "alfalfa":      {"sow_start": 274, "sow_end": 335, "harvest_start": 1,   "harvest_end": 335},
    },
}


# =============================================================================
# MODULE C: Multi-Spectral Index Reference Values
# =============================================================================
# Expected index values per crop at peak season.
# Used for discrimination when EVI, NDMI, NDWI data is available.

SPECTRAL_SIGNATURES: Dict[str, dict] = {
    # ── Crops with distinctive spectral signatures ──
    "rice":          {"evi_peak": (0.45, 0.70), "ndmi_transplant": (0.1, 0.4),  "ndwi_flood": (0.0, 0.3),   "lswi_indicator": "flood"},
    "corn":          {"evi_peak": (0.60, 0.90), "ndmi_peak": (0.2, 0.5),       "ndwi_peak": (-0.4, -0.1),  "lswi_indicator": "high_biomass"},
    "wheat":         {"evi_peak": (0.40, 0.70), "ndmi_peak": (0.1, 0.4),       "ndwi_peak": (-0.3, -0.05), "lswi_indicator": "moderate"},
    "barley":        {"evi_peak": (0.35, 0.65), "ndmi_peak": (0.1, 0.35),      "ndwi_peak": (-0.3, -0.05), "lswi_indicator": "moderate"},
    "soybean":       {"evi_peak": (0.55, 0.85), "ndmi_peak": (0.2, 0.5),       "ndwi_peak": (-0.35, -0.1), "lswi_indicator": "high_biomass"},
    "cotton":        {"evi_peak": (0.40, 0.70), "ndmi_peak": (0.15, 0.35),     "ndwi_peak": (-0.3, -0.05), "lswi_indicator": "moderate"},
    "olive":         {"evi_peak": (0.15, 0.35), "ndmi_peak": (0.05, 0.25),     "ndwi_peak": (-0.2, 0.0),   "lswi_indicator": "sparse_canopy"},
    "orange":        {"evi_peak": (0.30, 0.55), "ndmi_peak": (0.15, 0.40),     "ndwi_peak": (-0.25, -0.05),"lswi_indicator": "evergreen_canopy"},
    "lemon":         {"evi_peak": (0.28, 0.52), "ndmi_peak": (0.12, 0.38),     "ndwi_peak": (-0.25, -0.05),"lswi_indicator": "evergreen_canopy"},
    "mandarin":      {"evi_peak": (0.30, 0.52), "ndmi_peak": (0.14, 0.38),     "ndwi_peak": (-0.25, -0.05),"lswi_indicator": "evergreen_canopy"},
    "citrus":        {"evi_peak": (0.28, 0.55), "ndmi_peak": (0.12, 0.40),     "ndwi_peak": (-0.25, -0.05),"lswi_indicator": "evergreen_canopy"},
    "grapefruit":    {"evi_peak": (0.30, 0.55), "ndmi_peak": (0.15, 0.42),     "ndwi_peak": (-0.25, -0.05),"lswi_indicator": "evergreen_canopy"},
    "date_palm":     {"evi_peak": (0.30, 0.55), "ndmi_peak": (0.15, 0.40),     "ndwi_peak": (-0.3, -0.1),  "lswi_indicator": "irrigated"},
    "alfalfa":       {"evi_peak": (0.40, 0.70), "ndmi_peak": (0.15, 0.40),     "ndwi_peak": (-0.3, -0.05), "lswi_indicator": "multi_cut"},
    "potato":        {"evi_peak": (0.45, 0.70), "ndmi_peak": (0.2, 0.45),      "ndwi_peak": (-0.3, -0.1),  "lswi_indicator": "moderate"},
    "tomato":        {"evi_peak": (0.35, 0.55), "ndmi_peak": (0.1, 0.35),      "ndwi_peak": (-0.25, 0.0),  "lswi_indicator": "moderate"},
    "sunflower":     {"evi_peak": (0.45, 0.70), "ndmi_peak": (0.15, 0.35),     "ndwi_peak": (-0.3, -0.05), "lswi_indicator": "moderate"},
    "chickpea":      {"evi_peak": (0.25, 0.50), "ndmi_peak": (0.05, 0.25),     "ndwi_peak": (-0.2, 0.0),   "lswi_indicator": "sparse"},
    "lentil":        {"evi_peak": (0.20, 0.45), "ndmi_peak": (0.05, 0.20),     "ndwi_peak": (-0.2, 0.0),   "lswi_indicator": "sparse"},
    "fava_bean":     {"evi_peak": (0.35, 0.60), "ndmi_peak": (0.1, 0.35),      "ndwi_peak": (-0.25, -0.05),"lswi_indicator": "moderate"},
    "grape":         {"evi_peak": (0.25, 0.50), "ndmi_peak": (0.1, 0.30),      "ndwi_peak": (-0.2, 0.0),   "lswi_indicator": "sparse_canopy"},
}


# =============================================================================
# MODULE D: Köppen Climate Zone → Crop Affinity Matrix
# =============================================================================
# Score [0.0, 1.0] for how suitable a crop is in each climate zone.
# Auto-detected from lat/lng using simplified algorithmic classifier.

KOPPEN_ZONES = {
    "Csa": "Hot-summer Mediterranean",
    "Csb": "Warm-summer Mediterranean",
    "BSk": "Cold semi-arid steppe",
    "BSh": "Hot semi-arid steppe",
    "BWh": "Hot desert",
    "BWk": "Cold desert",
    "Cfa": "Humid subtropical",
    "Cfb": "Oceanic",
    "Dfa": "Hot-summer humid continental",
    "Aw":  "Tropical savanna",
    "Af":  "Tropical rainforest",
    "Am":  "Tropical monsoon",
}

# Crop → {zone: affinity_score}. Higher = more suitable.
KOPPEN_CROP_AFFINITY: Dict[str, Dict[str, float]] = {
    "wheat":        {"Csa": 1.0, "Csb": 0.9, "BSk": 0.8, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.7, "Cfb": 0.8, "Dfa": 0.7, "Aw": 0.2, "Af": 0.1},
    "durum_wheat":  {"Csa": 1.0, "Csb": 0.8, "BSk": 0.7, "BSh": 0.5, "BWh": 0.4, "Cfa": 0.5, "Cfb": 0.5, "Dfa": 0.4, "Aw": 0.1, "Af": 0.0},
    "barley":       {"Csa": 1.0, "Csb": 0.9, "BSk": 0.9, "BSh": 0.6, "BWh": 0.4, "Cfa": 0.6, "Cfb": 0.8, "Dfa": 0.7, "Aw": 0.2, "Af": 0.1},
    "oat":          {"Csa": 0.8, "Csb": 0.9, "BSk": 0.6, "BSh": 0.3, "BWh": 0.1, "Cfa": 0.7, "Cfb": 1.0, "Dfa": 0.8, "Aw": 0.1, "Af": 0.0},
    "rice":         {"Csa": 0.4, "Csb": 0.2, "BSk": 0.1, "BSh": 0.2, "BWh": 0.3, "Cfa": 0.8, "Cfb": 0.3, "Dfa": 0.5, "Aw": 0.9, "Af": 1.0, "Am": 1.0},
    "corn":         {"Csa": 0.7, "Csb": 0.6, "BSk": 0.4, "BSh": 0.5, "BWh": 0.3, "Cfa": 1.0, "Cfb": 0.7, "Dfa": 0.9, "Aw": 0.8, "Af": 0.6},
    "chickpea":     {"Csa": 1.0, "Csb": 0.7, "BSk": 0.9, "BSh": 0.7, "BWh": 0.4, "Cfa": 0.4, "Cfb": 0.3, "Dfa": 0.3, "Aw": 0.3, "Af": 0.1},
    "lentil":       {"Csa": 1.0, "Csb": 0.7, "BSk": 0.8, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.4, "Cfb": 0.4, "Dfa": 0.4, "Aw": 0.2, "Af": 0.1},
    "fava_bean":    {"Csa": 1.0, "Csb": 0.8, "BSk": 0.6, "BSh": 0.4, "BWh": 0.2, "Cfa": 0.6, "Cfb": 0.8, "Dfa": 0.5, "Aw": 0.3, "Af": 0.1},
    "olive":        {"Csa": 1.0, "Csb": 0.8, "BSk": 0.4, "BSh": 0.3, "BWh": 0.1, "Cfa": 0.3, "Cfb": 0.2, "Dfa": 0.1, "Aw": 0.0, "Af": 0.0},
    "grape":        {"Csa": 1.0, "Csb": 0.9, "BSk": 0.5, "BSh": 0.3, "BWh": 0.2, "Cfa": 0.6, "Cfb": 0.5, "Dfa": 0.4, "Aw": 0.1, "Af": 0.0},
    "orange":       {"Csa": 1.0, "Csb": 0.8, "BSk": 0.3, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.7, "Cfb": 0.3, "Dfa": 0.2, "Aw": 0.5, "Af": 0.4},
    "lemon":        {"Csa": 1.0, "Csb": 0.8, "BSk": 0.3, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.7, "Cfb": 0.3, "Dfa": 0.1, "Aw": 0.4, "Af": 0.3},
    "mandarin":     {"Csa": 1.0, "Csb": 0.8, "BSk": 0.3, "BSh": 0.4, "BWh": 0.2, "Cfa": 0.7, "Cfb": 0.3, "Dfa": 0.2, "Aw": 0.4, "Af": 0.3},
    "citrus":       {"Csa": 1.0, "Csb": 0.8, "BSk": 0.3, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.7, "Cfb": 0.3, "Dfa": 0.2, "Aw": 0.5, "Af": 0.4},
    "grapefruit":   {"Csa": 0.9, "Csb": 0.7, "BSk": 0.2, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.8, "Cfb": 0.3, "Dfa": 0.2, "Aw": 0.5, "Af": 0.4},
    "date_palm":    {"Csa": 0.3, "Csb": 0.1, "BSk": 0.3, "BSh": 0.8, "BWh": 1.0, "Cfa": 0.2, "Cfb": 0.0, "Dfa": 0.0, "Aw": 0.5, "Af": 0.2},
    "almond":       {"Csa": 1.0, "Csb": 0.8, "BSk": 0.5, "BSh": 0.3, "BWh": 0.2, "Cfa": 0.5, "Cfb": 0.3, "Dfa": 0.3, "Aw": 0.1, "Af": 0.0},
    "cotton":       {"Csa": 0.7, "Csb": 0.4, "BSk": 0.4, "BSh": 0.7, "BWh": 0.6, "Cfa": 0.9, "Cfb": 0.2, "Dfa": 0.5, "Aw": 0.8, "Af": 0.3},
    "tomato":       {"Csa": 0.9, "Csb": 0.7, "BSk": 0.5, "BSh": 0.6, "BWh": 0.5, "Cfa": 0.8, "Cfb": 0.5, "Dfa": 0.6, "Aw": 0.7, "Af": 0.5},
    "potato":       {"Csa": 0.8, "Csb": 0.9, "BSk": 0.5, "BSh": 0.3, "BWh": 0.2, "Cfa": 0.8, "Cfb": 1.0, "Dfa": 0.8, "Aw": 0.3, "Af": 0.2},
    "sunflower":    {"Csa": 0.9, "Csb": 0.7, "BSk": 0.6, "BSh": 0.4, "BWh": 0.2, "Cfa": 0.8, "Cfb": 0.6, "Dfa": 0.8, "Aw": 0.3, "Af": 0.1},
    "alfalfa":      {"Csa": 0.8, "Csb": 0.7, "BSk": 0.7, "BSh": 0.6, "BWh": 0.5, "Cfa": 0.8, "Cfb": 0.7, "Dfa": 0.8, "Aw": 0.5, "Af": 0.3},
    "sorghum":      {"Csa": 0.6, "Csb": 0.4, "BSk": 0.5, "BSh": 0.8, "BWh": 0.4, "Cfa": 0.8, "Cfb": 0.3, "Dfa": 0.6, "Aw": 1.0, "Af": 0.7},
    "banana":       {"Csa": 0.1, "Csb": 0.0, "BSk": 0.0, "BSh": 0.2, "BWh": 0.1, "Cfa": 0.4, "Cfb": 0.1, "Dfa": 0.0, "Aw": 0.9, "Af": 1.0, "Am": 1.0},
    "mango":        {"Csa": 0.1, "Csb": 0.0, "BSk": 0.0, "BSh": 0.3, "BWh": 0.2, "Cfa": 0.3, "Cfb": 0.0, "Dfa": 0.0, "Aw": 0.9, "Af": 1.0, "Am": 0.9},
    "coconut":      {"Csa": 0.0, "Csb": 0.0, "BSk": 0.0, "BSh": 0.1, "BWh": 0.0, "Cfa": 0.2, "Cfb": 0.0, "Dfa": 0.0, "Aw": 0.8, "Af": 1.0, "Am": 1.0},
    "pomegranate":  {"Csa": 1.0, "Csb": 0.7, "BSk": 0.6, "BSh": 0.7, "BWh": 0.5, "Cfa": 0.5, "Cfb": 0.3, "Dfa": 0.3, "Aw": 0.3, "Af": 0.1},
    "fig":          {"Csa": 1.0, "Csb": 0.8, "BSk": 0.5, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.5, "Cfb": 0.3, "Dfa": 0.2, "Aw": 0.2, "Af": 0.1},
    "quinoa":       {"Csa": 0.5, "Csb": 0.6, "BSk": 0.8, "BSh": 0.4, "BWh": 0.2, "Cfa": 0.4, "Cfb": 0.5, "Dfa": 0.3, "Aw": 0.3, "Af": 0.1},
    "sugar_beet":   {"Csa": 0.8, "Csb": 0.9, "BSk": 0.5, "BSh": 0.3, "BWh": 0.1, "Cfa": 0.7, "Cfb": 1.0, "Dfa": 0.8, "Aw": 0.1, "Af": 0.0},
}


# =============================================================================
# MODULE E: Aridity Classification Thresholds
# =============================================================================
# De Martonne Aridity Index (I_DM = P / (T + 10))
# Crops grouped by minimum aridity they require under rainfed conditions.

ARIDITY_CROP_THRESHOLDS: Dict[str, Tuple[float, float]] = {
    # (min_I_DM_rainfed, ideal_I_DM)
    # De Martonne Aridity Index: P / (T + 10)
    # <5 hyper-arid | 5-10 arid | 10-20 semi-arid | 20-30 sub-humid | 30-60 humid | >60 per-humid

    # -- Cereal --
    "pearl_millet":          (  5.0,  15.0),   # water=low
    "quinoa":                (  5.0,  15.0),   # water=low
    "safflower":             (  5.0,  15.0),   # water=low
    "finger_millet":         (  5.0,  15.0),   # water=low
    "bermuda_grass":         (  5.0,  15.0),   # water=low
    "fonio":                 (  8.0,  20.0),   # water=low
    "barley":                (  8.0,  20.0),   # water=medium (most drought-tolerant cereal)
    "sorghum":               ( 10.0,  25.0),   # water=medium (heat/drought tolerant)
    "teff":                  ( 10.0,  25.0),   # water=medium
    "durum_wheat":           ( 12.0,  25.0),   # water=medium
    "oat":                   ( 12.0,  28.0),   # water=medium
    "oat_forage":            ( 12.0,  28.0),   # water=medium
    "rye":                   ( 12.0,  28.0),   # water=medium
    "ryegrass":              ( 12.0,  28.0),   # water=medium
    "sorghum_forage":        ( 12.0,  28.0),   # water=medium
    "spelt":                 ( 12.0,  28.0),   # water=medium
    "sudan_grass":           ( 12.0,  28.0),   # water=medium
    "sunflower":             ( 12.0,  25.0),   # water=medium
    "triticale":             ( 12.0,  28.0),   # water=medium
    "wheat":                 ( 12.0,  25.0),   # water=medium
    "amaranth":              ( 12.0,  28.0),   # water=medium
    "buckwheat":             ( 12.0,  28.0),   # water=medium
    "canola":                ( 12.0,  28.0),   # water=medium
    "emmer":                 ( 12.0,  28.0),   # water=medium

    # -- Maize --
    "corn":                  ( 15.0,  35.0),   # water=high
    "maize":                 ( 15.0,  35.0),   # water=high
    "popcorn":               ( 15.0,  35.0),   # water=high
    "sweet_corn":            ( 15.0,  35.0),   # water=high
    "sugarcane":             ( 25.0,  50.0),   # water=high

    # -- Rice --
    "upland_rice":           ( 20.0,  40.0),   # water=medium
    "rice":                  ( 25.0,  50.0),   # water=high
    "wild_rice":             ( 25.0,  50.0),   # water=high
    "african_rice":          ( 25.0,  50.0),   # water=high

    # -- Legume --
    "castor":                (  5.0,  15.0),   # water=low
    "chickpea":              (  8.0,  18.0),   # water=medium (drought-tolerant)
    "cowpea":                (  8.0,  23.0),   # water=low
    "bambara_groundnut":     (  8.0,  20.0),   # water=low
    "lentil":                (  8.0,  18.0),   # water=medium
    "alfalfa":               (  5.0,  15.0),   # water=medium (adapted but needs irrigation)
    "vetch":                 ( 12.0,  28.0),   # water=medium
    "clover":                ( 12.0,  28.0),   # water=medium
    "fava_bean":             ( 12.0,  28.0),   # water=medium
    "kidney_bean":           ( 12.0,  28.0),   # water=medium
    "lablab":                ( 12.0,  28.0),   # water=medium
    "lima_bean":             ( 12.0,  28.0),   # water=medium
    "lupine":                ( 12.0,  28.0),   # water=medium
    "mung_bean":             ( 12.0,  28.0),   # water=medium
    "pea":                   ( 12.0,  28.0),   # water=medium
    "pigeon_pea":            ( 12.0,  28.0),   # water=medium
    "soybean":               ( 12.0,  28.0),   # water=medium
    "white_bean":            ( 12.0,  28.0),   # water=medium
    "groundnut":             ( 15.0,  33.0),   # water=medium
    "berseem":               ( 12.0,  28.0),   # water=medium
    "black_eyed_pea":        ( 12.0,  28.0),   # water=medium
    "green_bean":            ( 12.0,  28.0),   # water=medium

    # -- Vegetable --
    "nopal":                 (  2.0,   8.0),   # water=low (Cactaceae — extreme drought)
    "moringa":               (  8.0,  20.0),   # water=low
    "purslane":              (  8.0,  20.0),   # water=low
    "oregano":               (  5.0,  15.0),   # water=low (Lamiaceae herb)
    "rosemary":              (  5.0,  15.0),   # water=low (Lamiaceae herb)
    "sage":                  (  5.0,  15.0),   # water=low (Lamiaceae herb)
    "thyme":                 (  5.0,  15.0),   # water=low (Lamiaceae herb)
    "lavender":              (  5.0,  15.0),   # water=low (Lamiaceae herb)
    "saffron":               (  8.0,  20.0),   # water=low
    "sesame":                (  5.0,  15.0),   # water=low
    "cassava":               (  8.0,  20.0),   # water=low
    "sweet_potato":          ( 12.0,  28.0),   # water=medium
    "anise":                 ( 12.0,  28.0),   # water=medium
    "cumin":                 ( 12.0,  28.0),   # water=medium
    "hops":                  ( 12.0,  28.0),   # water=medium
    "tomato":                ( 15.0,  30.0),   # water=high
    "potato":                ( 15.0,  30.0),   # water=high
    "sugar_beet":            ( 15.0,  30.0),   # water=high
    "arugula":               ( 18.0,  38.0),   # water=high
    "basil":                 ( 18.0,  38.0),   # water=high
    "artichoke":             ( 18.0,  38.0),   # water=high
    "asparagus":             ( 18.0,  38.0),   # water=high
    "beetroot":              ( 18.0,  38.0),   # water=high
    "broccoli":              ( 18.0,  38.0),   # water=high
    "brussels_sprouts":      ( 18.0,  38.0),   # water=high
    "cabbage":               ( 18.0,  38.0),   # water=high
    "caraway":               ( 18.0,  38.0),   # water=high
    "carrot":                ( 18.0,  38.0),   # water=high
    "cauliflower":           ( 18.0,  38.0),   # water=high
    "celery":                ( 18.0,  38.0),   # water=high
    "chard":                 ( 18.0,  38.0),   # water=high
    "dill":                  ( 18.0,  38.0),   # water=high
    "endive":                ( 18.0,  38.0),   # water=high
    "fennel":                ( 18.0,  38.0),   # water=high
    "garlic":                ( 18.0,  38.0),   # water=high
    "kale":                  ( 18.0,  38.0),   # water=high
    "leek":                  ( 18.0,  38.0),   # water=high
    "lettuce":               ( 18.0,  38.0),   # water=high
    "melon":                 ( 18.0,  38.0),   # water=high
    "nigella":               ( 18.0,  38.0),   # water=high
    "parsley":               ( 18.0,  38.0),   # water=high
    "parsnip":               ( 18.0,  38.0),   # water=high
    "radish":                ( 18.0,  38.0),   # water=high
    "sorrel":                ( 18.0,  38.0),   # water=high
    "spinach":               ( 18.0,  38.0),   # water=high
    "squash":                ( 18.0,  38.0),   # water=high
    "tiger_nut":             ( 18.0,  38.0),   # water=high
    "tomatillo":             ( 18.0,  38.0),   # water=high
    "turnip":                ( 18.0,  38.0),   # water=high
    "vernonia":              ( 18.0,  38.0),   # water=high
    "zucchini":              ( 18.0,  38.0),   # water=high
    "mint":                  ( 12.0,  28.0),   # water=high (Lamiaceae herb)
    "bitter_gourd":          ( 21.0,  43.0),   # water=high (tropical)
    "black_pepper":          ( 21.0,  43.0),   # water=high (tropical)
    "bottle_gourd":          ( 21.0,  43.0),   # water=high (tropical)
    "chayote":               ( 21.0,  43.0),   # water=high (tropical)
    "cocoyam":               ( 21.0,  43.0),   # water=high (tropical)
    "coriander":             ( 21.0,  43.0),   # water=high (tropical)
    "cucumber":              ( 21.0,  43.0),   # water=high (tropical)
    "eggplant":              ( 21.0,  43.0),   # water=high (tropical)
    "fenugreek":             ( 21.0,  43.0),   # water=high (tropical)
    "ginger":                ( 21.0,  43.0),   # water=high (tropical)
    "hot_pepper":            ( 21.0,  43.0),   # water=high (tropical)
    "luffa":                 ( 21.0,  43.0),   # water=high (tropical)
    "okra":                  ( 21.0,  43.0),   # water=high (tropical)
    "onion":                 ( 21.0,  43.0),   # water=high (tropical)
    "pepper":                ( 21.0,  43.0),   # water=high (tropical)
    "pumpkin":               ( 21.0,  43.0),   # water=high (tropical)
    "roselle":               ( 21.0,  43.0),   # water=high (tropical)
    "taro":                  ( 21.0,  43.0),   # water=high (tropical)
    "tobacco":               ( 21.0,  43.0),   # water=high (tropical)
    "turmeric":              ( 21.0,  43.0),   # water=high (tropical)
    "watermelon":            ( 21.0,  43.0),   # water=high (tropical)
    "yam":                   ( 21.0,  43.0),   # water=high (tropical)

    # -- Cotton / Fiber --
    "sisal":                 (  3.0,  10.0),   # water=low (extreme drought fiber)
    "flax":                  ( 12.0,  25.0),   # water=high (temperate)
    "hemp":                  ( 12.0,  30.0),   # water=high
    "cotton":                ( 15.0,  30.0),   # water=high
    "kenaf":                 ( 20.0,  40.0),   # water=high (tropical)
    "jute":                  ( 25.0,  50.0),   # water=high (tropical)

    # -- Perennial --
    "date_palm":             (  2.0,   8.0),   # water=medium (thrives in extreme aridity, irrigated)
    "prickly_pear":          (  2.0,   8.0),   # water=low (Cactaceae)
    "jojoba":                (  3.0,  10.0),   # water=low (desert shrub)
    "acacia_gum":            (  6.0,  18.0),   # water=low
    "argan":                 (  6.0,  18.0),   # water=low
    "jujube":                (  6.0,  18.0),   # water=low
    "carob":                 (  8.0,  22.0),   # water=low (Mediterranean drought-tolerant)
    "fig":                   (  8.0,  25.0),   # water=low (drought-tolerant)
    "pistachio":             (  8.0,  20.0),   # water=low (very drought-tolerant)
    "pomegranate":           (  8.0,  25.0),   # water=medium (drought-tolerant)
    "henna":                 (  9.0,  23.0),   # water=low
    "almond":                ( 10.0,  25.0),   # water=medium (Mediterranean)
    "apricot":               ( 10.0,  25.0),   # water=medium (Mediterranean)
    "blackberry":            ( 10.0,  26.0),   # water=medium
    "blueberry":             ( 10.0,  26.0),   # water=medium
    "chestnut":              ( 10.0,  26.0),   # water=medium
    "cranberry":             ( 10.0,  26.0),   # water=medium
    "hazelnut":              ( 10.0,  26.0),   # water=medium
    "loquat":                ( 10.0,  26.0),   # water=medium
    "mulberry":              ( 10.0,  26.0),   # water=medium
    "olive":                 ( 10.0,  25.0),   # water=low (Mediterranean adapted)
    "persimmon":             ( 10.0,  26.0),   # water=medium
    "plum":                  ( 10.0,  26.0),   # water=medium
    "quince":                ( 10.0,  26.0),   # water=medium
    "raspberry":             ( 10.0,  26.0),   # water=medium
    "strawberry":            ( 10.0,  26.0),   # water=medium
    "grape":                 ( 12.0,  30.0),   # water=medium
    "peach":                 ( 12.0,  30.0),   # water=medium
    "pear":                  ( 12.0,  30.0),   # water=medium
    "lime":                  ( 13.0,  31.0),   # water=medium (Rutaceae)
    "apple":                 ( 15.0,  35.0),   # water=medium (temperate)
    "cherry":                ( 15.0,  35.0),   # water=medium
    "citrus":                ( 15.0,  35.0),   # water=medium (Rutaceae, irrigation-dependent)
    "clementine":            ( 15.0,  35.0),   # water=medium (Rutaceae)
    "grapefruit":            ( 15.0,  35.0),   # water=medium (Rutaceae)
    "lemon":                 ( 15.0,  35.0),   # water=medium (Rutaceae)
    "mandarin":              ( 15.0,  35.0),   # water=medium (Rutaceae)
    "orange":                ( 15.0,  35.0),   # water=medium (Rutaceae)
    "walnut":                ( 15.0,  35.0),   # water=medium
    "kiwi":                  ( 20.0,  40.0),   # water=medium (subtropical)
    "avocado":               ( 25.0,  50.0),   # water=high

    # -- Tropical Tree --
    "dragon_fruit":          (  2.0,   8.0),   # water=low (Cactaceae)
    "baobab":                ( 13.0,  28.0),   # water=low (semi-arid adapted)
    "locust_bean":           ( 13.0,  28.0),   # water=low
    "marula":                ( 13.0,  28.0),   # water=low
    "neem":                  ( 13.0,  28.0),   # water=low
    "shea":                  ( 13.0,  28.0),   # water=low
    "breadfruit":            ( 23.0,  46.0),   # water=high
    "cardamom":              ( 23.0,  46.0),   # water=high
    "cashew":                ( 23.0,  46.0),   # water=high
    "cinnamon":              ( 23.0,  46.0),   # water=high
    "clove":                 ( 23.0,  46.0),   # water=high
    "durian":                ( 23.0,  46.0),   # water=high
    "enset":                 ( 23.0,  46.0),   # water=high
    "guava":                 ( 23.0,  46.0),   # water=high
    "jackfruit":             ( 23.0,  46.0),   # water=high
    "longan":                ( 23.0,  46.0),   # water=high
    "lychee":                ( 23.0,  46.0),   # water=high
    "macadamia":             ( 23.0,  46.0),   # water=high
    "mango":                 ( 23.0,  46.0),   # water=high
    "mangosteen":            ( 23.0,  46.0),   # water=high
    "nutmeg":                ( 23.0,  46.0),   # water=high
    "papaya":                ( 23.0,  46.0),   # water=high
    "passion_fruit":         ( 23.0,  46.0),   # water=high
    "pineapple":             ( 23.0,  46.0),   # water=high
    "plantain":              ( 23.0,  46.0),   # water=high
    "rambutan":              ( 23.0,  46.0),   # water=high
    "star_fruit":            ( 23.0,  46.0),   # water=high
    "tamarind":              ( 23.0,  46.0),   # water=high
    "vanilla":               ( 23.0,  46.0),   # water=high
    "coconut":               ( 25.0,  50.0),   # water=high (tropical)
    "coffee":                ( 25.0,  50.0),   # water=high (tropical highland)
    "tea":                   ( 25.0,  50.0),   # water=high (tropical highland)
    "banana":                ( 30.0,  60.0),   # water=high (tropical, very high water)
    "cocoa":                 ( 30.0,  60.0),   # water=high (tropical rainforest)
    "oil_palm":              ( 30.0,  60.0),   # water=high (tropical rainforest)
    "rubber":                ( 30.0,  60.0),   # water=high (tropical rainforest)
}


# =============================================================================
# MODULE F: Agronomic Rotation Matrix
# =============================================================================
# Transition probability [0-1] from previous crop architecture to current.
# Based on agronomic succession science:
#   Cereal → Legume is ideal (N-fixation replenishment)
#   Same-family → Same-family is penalized (disease buildup)

ROTATION_MATRIX: Dict[str, Dict[str, float]] = {
    "cereal":       {"legume": 1.0, "vegetable": 0.7, "cotton": 0.6, "maize": 0.5, "cereal": 0.3, "perennial": 0.5, "rice": 0.4, "tropical_tree": 0.3},
    "legume":       {"cereal": 1.0, "maize": 0.9, "vegetable": 0.7, "cotton": 0.6, "rice": 0.5, "legume": 0.2, "perennial": 0.5, "tropical_tree": 0.3},
    "maize":        {"legume": 1.0, "cereal": 0.8, "vegetable": 0.6, "cotton": 0.5, "maize": 0.3, "perennial": 0.5, "rice": 0.4, "tropical_tree": 0.3},
    "vegetable":    {"cereal": 0.9, "legume": 0.8, "maize": 0.7, "cotton": 0.5, "vegetable": 0.4, "perennial": 0.5, "rice": 0.4, "tropical_tree": 0.3},
    "cotton":       {"cereal": 0.9, "legume": 0.8, "maize": 0.7, "vegetable": 0.5, "cotton": 0.2, "perennial": 0.5, "rice": 0.4, "tropical_tree": 0.3},
    "rice":         {"legume": 0.9, "cereal": 0.8, "vegetable": 0.6, "maize": 0.5, "rice": 0.6, "cotton": 0.4, "perennial": 0.5, "tropical_tree": 0.3},
    "perennial":    {"perennial": 1.0, "cereal": 0.1, "legume": 0.1, "vegetable": 0.1, "maize": 0.1, "cotton": 0.1, "rice": 0.1, "tropical_tree": 0.1},
    "tropical_tree":{"tropical_tree": 1.0, "perennial": 0.5, "cereal": 0.1, "legume": 0.1, "vegetable": 0.1, "maize": 0.1, "cotton": 0.1, "rice": 0.1},
}


# =============================================================================
# MODULE H: Botanical Family Grouping
# =============================================================================
# Crops in the same family share spectral/structural traits.
# Used as a tiebreaker within architecture classes.

BOTANICAL_FAMILIES: Dict[str, str] = {
    # Poaceae (grasses)
    "wheat": "Poaceae", "durum_wheat": "Poaceae", "emmer": "Poaceae",
    "barley": "Poaceae", "oat": "Poaceae", "rye": "Poaceae",
    "triticale": "Poaceae", "spelt": "Poaceae", "sorghum": "Poaceae",
    "millet": "Poaceae", "corn": "Poaceae", "sweet_corn": "Poaceae",
    "rice": "Poaceae", "ryegrass": "Poaceae", "sugarcane": "Poaceae",
    # Fabaceae (legumes)
    "chickpea": "Fabaceae", "lentil": "Fabaceae", "fava_bean": "Fabaceae",
    "pea": "Fabaceae", "cowpea": "Fabaceae", "vetch": "Fabaceae",
    "soybean": "Fabaceae", "alfalfa": "Fabaceae", "clover": "Fabaceae",
    "fenugreek": "Fabaceae", "lupin": "Fabaceae",
    # Solanaceae
    "tomato": "Solanaceae", "potato": "Solanaceae", "pepper": "Solanaceae",
    "eggplant": "Solanaceae", "hot_pepper": "Solanaceae", "tobacco": "Solanaceae",
    # Cucurbitaceae
    "cucumber": "Cucurbitaceae", "watermelon": "Cucurbitaceae",
    "melon": "Cucurbitaceae", "zucchini": "Cucurbitaceae",
    # Brassicaceae
    "canola": "Brassicaceae", "cabbage": "Brassicaceae",
    "cauliflower": "Brassicaceae", "kale": "Brassicaceae",
    # Asteraceae
    "sunflower": "Asteraceae", "lettuce": "Asteraceae", "artichoke": "Asteraceae",
    # Oleaceae
    "olive": "Oleaceae",
    # Rosaceae
    "almond": "Rosaceae", "apricot": "Rosaceae", "peach": "Rosaceae",
    "cherry": "Rosaceae", "apple": "Rosaceae", "pear": "Rosaceae",
    # Arecaceae (palms)
    "date_palm": "Arecaceae", "coconut": "Arecaceae",
    # Vitaceae
    "grape": "Vitaceae",
    # Rutaceae
    "orange": "Rutaceae", "lemon": "Rutaceae", "mandarin": "Rutaceae",
    "citrus": "Rutaceae", "grapefruit": "Rutaceae",
    "citrus_orange": "Rutaceae", "citrus_lemon": "Rutaceae",
    # Amaranthaceae
    "quinoa": "Amaranthaceae", "sugar_beet": "Amaranthaceae",
    "spinach": "Amaranthaceae", "beetroot": "Amaranthaceae",
    # Malvaceae
    "cotton": "Malvaceae",
    # Liliaceae / Amaryllidaceae
    "onion": "Amaryllidaceae", "garlic": "Amaryllidaceae",
    # Apiaceae
    "carrot": "Apiaceae", "celery": "Apiaceae", "cumin": "Apiaceae",
    "coriander": "Apiaceae", "parsley": "Apiaceae",
    # Moraceae
    "fig": "Moraceae",
    # Lythraceae
    "pomegranate": "Lythraceae",
    # Linaceae
    "flax": "Linaceae",
}


# =============================================================================
# Helper: Auto-detect Köppen zone from lat/lng
# =============================================================================

def detect_koppen_zone(lat: float, lng: float,
                       mean_temp_c: Optional[float] = None) -> str:
    """
    Simplified Köppen climate zone detection for MENA and Mediterranean.

    Based on Beck et al. (2018) 1km Köppen-Geiger classification,
    approximated for agricultural regions.
    """
    abs_lat = abs(lat)

    # ── Algeria-specific zones ──
    if 28 <= lat <= 37 and -2 <= lng <= 12:
        if lat >= 35:
            return "Csa"  # Coastal Mediterranean (Algiers, Oran, Bejaia)
        elif lat >= 33:
            return "BSk"  # High Plateaus (Djelfa, Msila, Batna)
        elif lat >= 30:
            return "BSh"  # Saharan steppe (Biskra, Ghardaia)
        else:
            return "BWh"  # Sahara proper

    # ── Broader MENA ──
    if 22 <= lat <= 37 and -10 <= lng <= 60:
        if abs_lat >= 35 and lng < 40:
            return "Csa"  # Mediterranean (Morocco, Tunisia, Turkey coast)
        elif abs_lat >= 30:
            return "BSk"  # Semi-arid steppe
        elif abs_lat >= 22:
            if lng > 40:
                return "BWh"  # Arabian desert
            elif mean_temp_c and mean_temp_c > 28:
                return "BWh"  # Hot desert
            else:
                return "BSh"  # Semi-arid

    # ── Tropical ──
    if abs_lat < 15:
        if mean_temp_c and mean_temp_c > 25:
            return "Af"
        return "Aw"

    # ── Subtropical ──
    if abs_lat < 30:
        return "Cfa"

    # ── Temperate ──
    if abs_lat < 45:
        return "Cfb"

    # ── Continental ──
    return "Dfa"


def detect_crop_calendar_region(lat: float, lng: float) -> str:
    """Detect which crop calendar region to use."""
    # Algeria
    if 28 <= lat <= 37 and -2 <= lng <= 12:
        if lat >= 33:
            return "algeria_mediterranean"
        else:
            return "algeria_saharan"

    # Broader MENA Mediterranean
    if 30 <= lat <= 38 and -10 <= lng <= 40:
        return "mena_mediterranean"

    # MENA Arid (Egypt, Iraq, Jordan, Gulf)
    if 22 <= lat <= 37 and 25 <= lng <= 60:
        return "mena_arid"

    # Default to Mediterranean
    return "mena_mediterranean"


# =============================================================================
# DEFAULT EXPANSION: Fill missing group-level context from CropSpec attributes
# =============================================================================
# This gives every registered crop a structurally complete record. Expanded
# values are architecture defaults derived from growing duration, water need,
# and temperature range. They are deliberately NOT made unique by crop code
# and are tagged non-discriminative so downstream products cannot mistake
# table completeness for measured species separability.

# Snapshot curated codes BEFORE auto-expansion so engine can prefer them
_CURATED_NDVI_CODES = frozenset(CROP_NDVI_SIGNATURES.keys())

# IMP-4: Add los_frac to curated entries that don't have it yet
# los_frac = length of season as fraction of year
_LOS_BY_SHAPE = {"evergreen": 1.0, "stable": 1.0, "multi_cut": 0.85, "bimodal": 0.60, "unimodal": 0.40}
for _code, _sig in CROP_NDVI_SIGNATURES.items():
    if "los_frac" not in _sig:
        _sig["los_frac"] = _LOS_BY_SHAPE.get(_sig.get("shape", "unimodal"), 0.40)


# =============================================================================
# Hierarchical Crop Groups — coarse-class predictions
# =============================================================================
# When fine crop separation is uncertain (wheat vs durum vs barley),
# the engine can report a reliable coarse group instead.
# Reference: hierarchical crop classification in Sentinel-2 literature.

CROP_GROUP_MAP: Dict[str, str] = {
    # Winter cereals
    "wheat": "winter_cereal", "durum_wheat": "winter_cereal", "barley": "winter_cereal",
    "oat": "winter_cereal", "rye": "winter_cereal", "triticale": "winter_cereal",
    "spelt": "winter_cereal", "emmer": "winter_cereal",
    # Summer cereals
    "corn": "summer_cereal", "maize": "summer_cereal", "sweet_corn": "summer_cereal",
    "popcorn": "summer_cereal", "sorghum": "summer_cereal",
    "pearl_millet": "summer_cereal", "finger_millet": "summer_cereal",
    "teff": "summer_cereal", "fonio": "summer_cereal", "amaranth": "summer_cereal",
    # Pseudo-cereals
    "quinoa": "pseudo_cereal", "buckwheat": "pseudo_cereal",
    # Rice
    "rice": "rice", "upland_rice": "rice", "wild_rice": "rice",
    # Evergreen orchards
    "olive": "evergreen_orchard", "orange": "evergreen_orchard",
    "lemon": "evergreen_orchard", "mandarin": "evergreen_orchard",
    "citrus": "evergreen_orchard", "grapefruit": "evergreen_orchard",
    "citrus_orange": "evergreen_orchard", "citrus_lemon": "evergreen_orchard",
    # Deciduous orchards
    "almond": "deciduous_orchard", "fig": "deciduous_orchard",
    "grape": "deciduous_orchard", "pomegranate": "deciduous_orchard",
    "apple": "deciduous_orchard", "pear": "deciduous_orchard",
    "cherry": "deciduous_orchard", "peach": "deciduous_orchard",
    "apricot": "deciduous_orchard", "walnut": "deciduous_orchard",
    "pistachio": "deciduous_orchard", "plum": "deciduous_orchard",
    "quince": "deciduous_orchard", "persimmon": "deciduous_orchard",
    "loquat": "deciduous_orchard", "mulberry": "deciduous_orchard",
    "carob": "deciduous_orchard", "jujube": "deciduous_orchard",
    "hazelnut": "deciduous_orchard", "chestnut": "deciduous_orchard",
    # Tropical palms
    "date_palm": "tropical_palm", "coconut": "tropical_palm", "oil_palm": "tropical_palm",
    # Cool-season legumes
    "chickpea": "cool_legume", "lentil": "cool_legume", "fava_bean": "cool_legume",
    "pea": "cool_legume", "vetch": "cool_legume", "lupin": "cool_legume",
    # Warm-season legumes
    "soybean": "warm_legume", "groundnut": "warm_legume", "cowpea": "warm_legume",
    "mung_bean": "warm_legume", "pigeon_pea": "warm_legume",
    "black_eyed_pea": "warm_legume", "lima_bean": "warm_legume",
    "kidney_bean": "warm_legume", "white_bean": "warm_legume",
    "common_bean": "warm_legume", "bambara_groundnut": "warm_legume",
    "lablab": "warm_legume",
    # Forage / multi-cut
    "alfalfa": "forage", "clover": "forage", "ryegrass": "forage",
    # Solanaceae vegetables
    "tomato": "solanaceae_veg", "pepper": "solanaceae_veg",
    "eggplant": "solanaceae_veg", "hot_pepper": "solanaceae_veg",
    # Cucurbit vegetables
    "watermelon": "cucurbit_veg", "melon": "cucurbit_veg",
    "cucumber": "cucurbit_veg", "zucchini": "cucurbit_veg",
    "squash": "cucurbit_veg", "pumpkin": "cucurbit_veg",
    # Root/tuber
    "potato": "root_tuber", "carrot": "root_tuber", "onion": "root_tuber",
    "garlic": "root_tuber", "beetroot": "root_tuber", "turnip": "root_tuber",
    "sweet_potato": "root_tuber", "cassava": "root_tuber",
    # Leafy vegetables
    "lettuce": "leafy_veg", "spinach": "leafy_veg", "cabbage": "leafy_veg",
    "kale": "leafy_veg", "chard": "leafy_veg", "arugula": "leafy_veg",
    # Oilseeds
    "sunflower": "oilseed", "canola": "oilseed", "flax": "oilseed",
    "sesame": "oilseed",
    # Cotton / fiber
    "cotton": "cotton_fiber", "hemp": "cotton_fiber", "jute": "cotton_fiber",
    # Sugar
    "sugar_beet": "sugar_crop", "sugarcane": "sugar_crop",
    # Herbs / spices
    "saffron": "herb_spice", "cumin": "herb_spice", "coriander": "herb_spice",
    "lavender": "herb_spice", "rosemary": "herb_spice", "thyme": "herb_spice",
    "oregano": "herb_spice", "sage": "herb_spice", "mint": "herb_spice",
    "basil": "herb_spice",
    # Non-crop classes (new — scored by fallow/bare detection)
    "fallow": "non_crop", "bare_soil": "non_crop",
    "post_harvest_residue": "non_crop", "recently_tilled": "non_crop",
    "mixed_unknown": "non_crop",
}


def get_crop_group(code: str) -> str:
    """Return the hierarchical crop group for a crop code.

    Falls back to ``{architecture}_other`` for crops not explicitly
    mapped, so every crop always has a group.
    """
    grp = CROP_GROUP_MAP.get(code)
    if grp:
        return grp
    # Auto-assign from architecture
    try:
        from crop_database import CROP_REGISTRY
        spec = CROP_REGISTRY.get(code)
        if spec:
            return f"{spec.architecture}_other"
    except ImportError:
        pass
    return "unknown"


# =============================================================================
# Curated Code Sets — per data source
# =============================================================================
# Snapshot curated codes for EACH data source so the quality tier system can
# distinguish hand-tuned literature values from auto-generated heuristics.
# These MUST be captured BEFORE _auto_expand_science_data() adds generated
# entries to the same dictionaries.

# _CURATED_NDVI_CODES already defined above (line 722)

_CURATED_SPECTRAL_CODES: frozenset = frozenset(SPECTRAL_SIGNATURES.keys())
_CURATED_KOPPEN_CODES: frozenset = frozenset(KOPPEN_CROP_AFFINITY.keys())

# Calendar regions: snapshot which crops appear in each curated calendar
_CURATED_CALENDAR_CODES: frozenset = frozenset()
for _region_cal in CROP_CALENDARS.values():
    _CURATED_CALENDAR_CODES = _CURATED_CALENDAR_CODES | frozenset(_region_cal.keys())

_CURATED_ARIDITY_CODES: frozenset = frozenset(ARIDITY_CROP_THRESHOLDS.keys())


# =============================================================================
# Data Quality Tiers — per crop, per feature
# =============================================================================
# Tags every crop's features with provenance:
#   "curated_literature" — hand-tuned from peer-reviewed sources
#   "curated"            — manually entered but not from published data
#   "architecture_default" — inherited from architecture class defaults
#   "heuristic"          — auto-generated by _auto_expand_science_data()
#
# The crop identification engine uses these tiers as trust multipliers:
#   curated_literature  → ×1.08
#   curated             → ×1.04
#   architecture_default → ×0.92
#   heuristic           → ×0.85

CROP_DATA_QUALITY: Dict[str, Dict[str, str]] = {}


def _assign_quality_tiers():
    """Tag every crop's features with quality tiers.

    Called after _auto_expand_science_data() so that auto-generated
    entries exist but are tagged as heuristic.
    """
    try:
        from crop_database import CROP_REGISTRY
    except ImportError:
        return

    for code in CROP_REGISTRY:
        CROP_DATA_QUALITY[code] = {
            "ndvi_signature": (
                "curated_literature" if code in _CURATED_NDVI_CODES
                else "heuristic"
            ),
            "spectral_signature": (
                "curated" if code in _CURATED_SPECTRAL_CODES
                else "heuristic"
            ),
            "koppen_affinity": (
                "curated" if code in _CURATED_KOPPEN_CODES
                else "architecture_default"
            ),
            "crop_calendar": (
                "curated" if code in _CURATED_CALENDAR_CODES
                else "architecture_default"
            ),
            "aridity_threshold": (
                "curated" if code in _CURATED_ARIDITY_CODES
                else "architecture_default"
            ),
        }

# =============================================================================
# MENA Regional Crop Prevalence (Algeria focus)
# =============================================================================
# Likelihood multiplier: how common is this crop in Algeria/MENA?
# 1.0 = very common, 0.5 = rare, 0.2 = almost never grown
# Affects the engine's family tiebreak module.
MENA_CROP_PREVALENCE = {
    # Top Algerian crops
    "wheat": 1.0, "durum_wheat": 1.0, "barley": 0.95, "oat": 0.80,
    "potato": 0.90, "tomato": 0.90, "onion": 0.85, "pepper": 0.80,
    "olive": 0.95, "date_palm": 0.90, "grape": 0.85, "fig": 0.85,
    "orange": 0.90, "lemon": 0.85, "mandarin": 0.85, "citrus": 0.85,
    "grapefruit": 0.70, "pomegranate": 0.80, "apricot": 0.80,
    "peach": 0.75, "apple": 0.75, "pear": 0.70, "cherry": 0.65,
    "almond": 0.85, "walnut": 0.65, "pistachio": 0.60,
    "chickpea": 0.85, "lentil": 0.80, "fava_bean": 0.90, "pea": 0.75,
    "watermelon": 0.80, "melon": 0.75, "zucchini": 0.80,
    "carrot": 0.75, "lettuce": 0.70, "artichoke": 0.70,
    "eggplant": 0.75, "cucumber": 0.70, "garlic": 0.70,
    "corn": 0.60, "sunflower": 0.55, "sugar_beet": 0.50,
    "cotton": 0.40, "tobacco": 0.35,
    "saffron": 0.45, "cumin": 0.55, "coriander": 0.50,
    # Less common in Algeria
    "carob": 0.50, "prickly_pear": 0.55, "quince": 0.50,
    "plum": 0.55, "loquat": 0.45, "mulberry": 0.40,
    # Rare / not typical in Algeria
    "jojoba": 0.15, "argan": 0.25, "acacia_gum": 0.10,
    "henna": 0.20, "jujube": 0.25,
    # Tropical — not grown in Algeria
    "coffee": 0.02, "cocoa": 0.02, "tea": 0.02, "rubber": 0.01,
    "oil_palm": 0.01, "banana": 0.15, "mango": 0.10,
    "coconut": 0.01, "cashew": 0.01, "papaya": 0.05,
}

def _auto_expand_science_data():
    """Fill missing fields with non-discriminative architecture defaults.

    These records support coarse agronomic compatibility checks only. They
    are not observations, learned parameters, or calibrated species
    signatures.
    """
    try:
        from crop_database import CROP_REGISTRY
    except ImportError:
        return  # Registry not available yet

    import math as _m

    # ── 1. NDVI Signature expansion ──
    for code, cr in CROP_REGISTRY.items():
        if code in CROP_NDVI_SIGNATURES:
            continue

        # Never manufacture per-species separation from the crop identifier.
        # Crops with identical agronomic attributes receive identical defaults
        # in the absence of measured crop-specific data.
        s = 0.0
        arch = cr.architecture
        days = cr.growing_days
        water = cr.water_needs

        if arch == "tropical_tree":
            pk = 0.70 + (0.08 if water == "high" else 0.03) + s
            tr = pk - 0.15
            shape = "stable" if water == "high" else "evergreen"
            n_p, gr, si = 0, 0.001, pk * 0.95 * 3.5
        elif arch == "perennial":
            if days >= 300 or code in ("carob", "argan", "jujube", "prickly_pear",
                                        "henna", "jojoba", "acacia_gum"):
                pk = 0.55 + (0.08 if water == "high" else 0.03) + s
                tr = pk - 0.14
                shape, n_p, gr = "evergreen", 0, 0.001
                si = pk * 0.9 * 2.8
            else:
                pk = 0.56 + (0.08 if water == "high" else 0.04 if water == "medium" else 0.0) + s
                tr = 0.12 + (0.04 if water == "high" else 0.0) + s * 0.3
                shape, n_p, gr = "unimodal", 1, 0.003
                si = (pk - tr) * days / 365 * 1.2
        elif arch == "cereal":
            if days >= 300:
                pk, tr, shape, n_p, gr, si = 0.55 + s, 0.20 + s * 0.3, "multi_cut", 3, 0.005, 1.20
            else:
                pk = 0.62 + min(0.18, days * 0.001) + s
                tr = 0.10
                shape, n_p, gr = "unimodal", 1, 0.006
                si = (pk - tr) * days / 365 * 1.5
        elif arch == "legume":
            pk = 0.52 + (0.08 if water == "high" else 0.04) + s
            tr, shape, n_p, gr = 0.10, "unimodal", 1, 0.005
            si = (pk - tr) * days / 365 * 1.3
        elif arch == "rice":
            pk = 0.65 + s
            tr, shape, n_p, gr, si = 0.05, "unimodal", 1, 0.007, 0.75
        elif arch == "cotton":
            if days >= 300:
                pk, tr, shape, n_p, gr, si = 0.50 + s, 0.30 + s * 0.3, "evergreen", 0, 0.001, 1.50
            else:
                pk = 0.65 + (0.05 if water == "high" else 0.0) + s
                tr, shape, n_p, gr, si = 0.10, "unimodal", 1, 0.006, 0.85
        elif arch == "maize":
            if days >= 300:
                pk, tr, shape, n_p, gr = 0.80 + s, 0.55, "stable", 0, 0.001
                si = 2.20
            else:
                pk = 0.83 + s
                tr, shape, n_p, gr, si = 0.10, "unimodal", 1, 0.008, 1.10
        else:  # vegetable
            # Only actual perennial herbs are evergreen, NOT asparagus/moringa
            _perennial_herbs = ("thyme", "rosemary", "oregano", "sage",
                                "lavender", "black_pepper")
            if days >= 300 and code in _perennial_herbs:
                pk = 0.48 + (0.08 if water == "high" else 0.0) + s
                tr = pk - 0.12
                shape, n_p, gr = "evergreen", 0, 0.001
                si = pk * 0.85 * 2.5
            elif days >= 300:
                # Long-lived vegetables like asparagus, moringa, nopal
                # These have strong seasonal patterns despite long lifespan
                pk = 0.55 + s
                tr = 0.15 + s * 0.3
                shape, n_p, gr = "unimodal", 1, 0.004
                si = (pk - tr) * 0.8
            elif days <= 60:
                pk = 0.40 + s
                tr, shape, n_p, gr, si = 0.08, "unimodal", 1, 0.008, 0.20
            else:
                pk = 0.50 + min(0.14, days * 0.001) + s
                tr, shape, n_p, gr = 0.10, "unimodal", 1, 0.005
                si = (pk - tr) * days / 365 * 1.2

        pk = round(min(0.92, max(0.30, pk)), 3)
        tr = round(min(pk - 0.05, max(0.02, tr)), 3)
        amp = round(pk - tr, 3)
        pf = 0.40 if shape in ("evergreen", "stable") else (0.50 if days > 120 else 0.45)

        # los_frac: length of season as fraction of year
        if shape in ("evergreen", "stable"):
            lf = 1.0
        elif shape == "multi_cut":
            lf = min(1.0, days / 365 * 1.2)  # Multi-cut spans most of year
        else:
            lf = round(min(1.0, max(0.15, days / 365)), 3)

        CROP_NDVI_SIGNATURES[code] = {
            "shape": shape, "peak_ndvi": pk, "trough_ndvi": tr,
            "peak_frac": pf, "greenup_rate": gr,
            "amplitude": amp, "season_integral": round(si, 2), "n_peaks": n_p,
            "los_frac": lf,
            "_auto_generated": True,  # Compatibility flag for existing callers
            "_provenance": "architecture_default",
            "_species_discriminative": False,
        }

    # ── 2. Köppen affinity expansion ──
    for code, cr in CROP_REGISTRY.items():
        if code in KOPPEN_CROP_AFFINITY:
            continue

        # Derive from optimal temperature range + water needs
        t_min, t_max = cr.optimal_temp_min, cr.optimal_temp_max
        water = cr.water_needs
        aff = {}

        # Mediterranean (Csa): 12-30°C mean
        aff["Csa"] = 1.0 if t_min <= 15 and t_max >= 25 else 0.6 if t_min <= 18 else 0.3
        aff["Csb"] = aff["Csa"] * 0.85
        # Semi-arid steppe
        aff["BSk"] = 0.6 if water != "high" else 0.3
        aff["BSh"] = 0.5 if water != "high" else 0.3
        # Desert
        aff["BWh"] = 0.2 if water == "low" else 0.1
        # Humid subtropical
        aff["Cfa"] = 0.7 if t_max >= 30 else 0.4
        aff["Cfb"] = 0.5 if t_min <= 12 else 0.3
        # Continental
        aff["Dfa"] = 0.4 if t_min <= 10 else 0.2
        # Tropical
        aff["Aw"] = 0.8 if t_min >= 18 else 0.3
        aff["Af"] = 0.9 if t_min >= 22 else 0.2

        # Special: tropical trees need heat
        if cr.architecture == "tropical_tree":
            aff["Csa"] = 0.05
            aff["Csb"] = 0.02
            aff["BSk"] = 0.02
            aff["Dfa"] = 0.01
            aff["Cfb"] = 0.02
            aff["Aw"] = 0.9
            aff["Af"] = 1.0
            aff["BSh"] = 0.15
            aff["BWh"] = 0.10
            aff["Cfa"] = 0.3

        KOPPEN_CROP_AFFINITY[code] = aff

    # ── 3. Spectral signature expansion ──
    for code, cr in CROP_REGISTRY.items():
        if code in SPECTRAL_SIGNATURES:
            continue

        ref = CROP_NDVI_SIGNATURES.get(code, {})
        pk = ref.get("peak_ndvi", 0.55)
        shape = ref.get("shape", "unimodal")

        if shape in ("evergreen", "stable"):
            evi_lo, evi_hi = pk * 0.45, pk * 0.85
            ndmi_lo, ndmi_hi = 0.10, 0.35
            ndwi_lo, ndwi_hi = -0.30, -0.05
            indicator = "evergreen_canopy"
        elif shape == "multi_cut":
            evi_lo, evi_hi = pk * 0.40, pk * 0.80
            ndmi_lo, ndmi_hi = 0.10, 0.35
            ndwi_lo, ndwi_hi = -0.30, -0.05
            indicator = "multi_cut"
        else:
            evi_lo, evi_hi = pk * 0.50, pk * 0.90
            ndmi_lo, ndmi_hi = 0.10 if cr.water_needs != "high" else 0.20, 0.40
            ndwi_lo, ndwi_hi = -0.35, -0.05
            indicator = "moderate" if cr.water_needs == "medium" else "high_biomass" if cr.water_needs == "high" else "sparse_canopy"

        SPECTRAL_SIGNATURES[code] = {
            "evi_peak": (round(evi_lo, 2), round(evi_hi, 2)),
            "ndmi_peak": (round(ndmi_lo, 2), round(ndmi_hi, 2)),
            "ndwi_peak": (round(ndwi_lo, 2), round(ndwi_hi, 2)),
            "lswi_indicator": indicator,
            "_provenance": "architecture_default",
            "_species_discriminative": False,
        }

    # ── 4. Botanical family expansion ──
    for code, cr in CROP_REGISTRY.items():
        if code not in BOTANICAL_FAMILIES and cr.family:
            BOTANICAL_FAMILIES[code] = cr.family

    # ── 5. MENA prevalence expansion ──
    # Auto-generate prevalence for crops missing from the curated table,
    # using region_tags and architecture as heuristics. This ensures the
    # Bayesian classifier has meaningful priors for all 209 crops instead
    # of the neutral 0.35 fallback.
    for code, cr in CROP_REGISTRY.items():
        if code in MENA_CROP_PREVALENCE:
            continue

        tags = set(t.lower() for t in (cr.region_tags or []))
        arch = cr.architecture

        # Tropical-only crops → very unlikely in Algeria
        if arch == "tropical_tree":
            MENA_CROP_PREVALENCE[code] = 0.03
            continue
        if tags & {"tropical", "subsaharan", "equatorial"}:
            if not tags & {"mediterranean", "mena", "north-africa", "subtropical"}:
                MENA_CROP_PREVALENCE[code] = 0.05
                continue

        # Mediterranean / MENA-tagged crops → likely
        if tags & {"mena", "north-africa", "algeria"}:
            MENA_CROP_PREVALENCE[code] = 0.65
        elif tags & {"mediterranean"}:
            MENA_CROP_PREVALENCE[code] = 0.55
        elif tags & {"subtropical"}:
            MENA_CROP_PREVALENCE[code] = 0.35
        elif tags & {"temperate"}:
            MENA_CROP_PREVALENCE[code] = 0.25
        elif not tags:
            # No tags at all — use architecture as proxy
            arch_prev = {
                "cereal": 0.40, "legume": 0.35, "vegetable": 0.30,
                "perennial": 0.30, "maize": 0.25, "cotton": 0.20,
                "rice": 0.15,
            }
            MENA_CROP_PREVALENCE[code] = arch_prev.get(arch, 0.20)
        else:
            MENA_CROP_PREVALENCE[code] = 0.15


# Run auto-expansion at import time
_auto_expand_science_data()

# Tag every crop's features with provenance tiers
_assign_quality_tiers()


def get_crop_science_provenance() -> Dict[str, object]:
    """Return auditable coverage counts for the rule-engine reference tables.

    The counts are derived from the active registry instead of being embedded
    in product copy, so adding a crop cannot silently make a fixed coverage
    claim stale. ``calibrated_species_evidence`` is intentionally false: these
    tables are reference priors, not a fitted probability model.
    """
    feature_families = (
        "ndvi_signature",
        "spectral_signature",
        "koppen_affinity",
        "crop_calendar",
        "aridity_threshold",
    )
    coverage: Dict[str, Dict[str, int]] = {}
    for feature in feature_families:
        tiers: Dict[str, int] = {}
        for crop_quality in CROP_DATA_QUALITY.values():
            tier = crop_quality.get(feature, "missing")
            tiers[tier] = tiers.get(tier, 0) + 1
        coverage[feature] = tiers
    return {
        "registry_crop_count": len(CROP_DATA_QUALITY),
        "feature_coverage_by_provenance": coverage,
        "expanded_defaults_species_discriminative": False,
        "calibrated_species_evidence": False,
        "intended_use": "coarse_group_prior_and_rule_ranking",
    }
