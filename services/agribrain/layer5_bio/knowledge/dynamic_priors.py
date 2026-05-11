"""
Dynamic Prior System — Crop/Region/Phenology-Aware Prior Computation

Replaces static THREAT_PRIORS with context-adjusted base rates using:
  - Crop type (rice → elevated fungal; cotton → elevated insect)
  - Climate indicators (temperature, humidity, rain)
  - Phenology stage (flowering → peak fungal susceptibility)
  - Latitude proxy for climate zone

Falls back to static THREAT_PRIORS if inputs are missing.
"""

from typing import Dict, Optional

from layer5_bio.schema import ThreatId, ThreatClass
from layer5_bio.knowledge.threats import (
    THREAT_PRIORS, THREAT_CLASS,
    get_phenology_multiplier,
)


# ── Crop-Specific Prior Adjustments ──────────────────────────────────────
# Multipliers applied to the static base prior for each threat.
# Science: certain crops have inherently higher/lower susceptibility profiles.

CROP_PRIOR_MULTIPLIERS = {
    "rice": {
        ThreatId.FUNGAL_LEAF_SPOT: 1.4,
        ThreatId.FUNGAL_RUST: 1.2,
        ThreatId.DOWNY_MILDEW: 1.5,   # Paddy conditions favor downy mildew
        ThreatId.BACTERIAL_BLIGHT: 1.6, # Xanthomonas in rice
        ThreatId.BORERS: 1.3,           # Stem borers common in rice
    },
    "wheat": {
        ThreatId.FUNGAL_RUST: 1.5,     # Puccinia triticina
        ThreatId.POWDERY_MILDEW: 1.3,
        ThreatId.CHEWING_INSECTS: 0.8,
    },
    "corn": {
        ThreatId.FUNGAL_LEAF_SPOT: 1.2,
        ThreatId.BORERS: 1.4,           # Corn borers
        ThreatId.WEED_PRESSURE: 1.2,
    },
    "cotton": {
        ThreatId.SUCKING_INSECTS: 1.5,  # Aphids, whitefly
        ThreatId.CHEWING_INSECTS: 1.3,  # Bollworm
        ThreatId.BACTERIAL_BLIGHT: 1.2,
    },
    "soybean": {
        ThreatId.FUNGAL_RUST: 1.6,      # Asian soybean rust
        ThreatId.WEED_PRESSURE: 1.3,
    },
    "olive": {
        ThreatId.FUNGAL_LEAF_SPOT: 1.2,
        ThreatId.SUCKING_INSECTS: 1.3,  # Olive fruit fly
        ThreatId.WEED_PRESSURE: 0.7,    # Orchards → less weed pressure
    },
    "potato": {
        ThreatId.DOWNY_MILDEW: 1.8,     # Phytophthora infestans
        ThreatId.BACTERIAL_BLIGHT: 1.0,
        ThreatId.CHEWING_INSECTS: 1.2,   # Colorado potato beetle
    },
}


# ── Climate Zone Adjustments ─────────────────────────────────────────────
# Based on weather indicators in the current period.

def _climate_multiplier(
    tmean_7d: float,
    rain_sum_7d: float,
    threat_class: ThreatClass,
) -> float:
    """Compute a climate-based multiplier for a threat class.
    
    Hot+Wet → amplified DISEASE/WEED
    Hot+Dry → amplified INSECT
    Cool → suppressed across the board
    """
    if threat_class == ThreatClass.DISEASE:
        # Fungal/bacterial thrive in warm, wet conditions
        temp_factor = _smooth_ramp(tmean_7d, 15.0, 25.0)  # 0→1 as temp rises
        rain_factor = _smooth_ramp(rain_sum_7d, 5.0, 30.0)
        return 0.5 + 0.5 * temp_factor + 0.3 * rain_factor  # [0.5, 1.3]
    
    elif threat_class == ThreatClass.INSECT:
        # Insects prefer warm, drier conditions (degree-day driven)
        temp_factor = _smooth_ramp(tmean_7d, 10.0, 30.0)
        dry_factor = 1.0 - _smooth_ramp(rain_sum_7d, 10.0, 50.0)
        return 0.5 + 0.5 * temp_factor + 0.2 * dry_factor  # [0.5, 1.2]
    
    elif threat_class == ThreatClass.WEED:
        # Weeds benefit from warmth + moisture
        temp_factor = _smooth_ramp(tmean_7d, 10.0, 25.0)
        rain_factor = _smooth_ramp(rain_sum_7d, 5.0, 25.0)
        return 0.6 + 0.3 * temp_factor + 0.2 * rain_factor  # [0.6, 1.1]
    
    return 1.0


def _smooth_ramp(value: float, low: float, high: float) -> float:
    """Smooth 0→1 ramp between low and high."""
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return (value - low) / (high - low)


# ── Main Entry Point ─────────────────────────────────────────────────────

def compute_dynamic_priors(
    crop_type: str = "",
    phenology_stage: str = "",
    climate_indicators: Optional[Dict[str, float]] = None,
    lat: float = 0.0,
) -> Dict[ThreatId, float]:
    """Compute context-adjusted priors for all threat types.
    
    Parameters
    ----------
    crop_type         : crop name (lowercase), e.g. "rice", "wheat", "corn"
    phenology_stage   : current growth stage, e.g. "VEGETATIVE", "REPRODUCTIVE"
    climate_indicators: dict with keys "tmean_7d", "rain_sum_7d"
    lat               : field latitude (used as climate zone proxy)
    
    Returns
    -------
    Dict[ThreatId, float] — adjusted priors in [0.01, 0.30] range
    """
    priors = dict(THREAT_PRIORS)  # Start from static base
    
    # 1. Crop-specific adjustments
    crop_key = (crop_type or "").lower().strip()
    crop_mults = CROP_PRIOR_MULTIPLIERS.get(crop_key, {})
    for tid in priors:
        if tid in crop_mults:
            priors[tid] *= crop_mults[tid]
    
    # 2. Phenology stage adjustments
    if phenology_stage:
        for tid in priors:
            tc = THREAT_CLASS.get(tid, ThreatClass.DISEASE)
            pheno_mult = get_phenology_multiplier(phenology_stage, tc)
            priors[tid] *= pheno_mult
    
    # 3. Climate indicator adjustments
    if climate_indicators:
        tmean = climate_indicators.get("tmean_7d", 20.0)
        rain = climate_indicators.get("rain_sum_7d", 10.0)
        for tid in priors:
            tc = THREAT_CLASS.get(tid, ThreatClass.DISEASE)
            clim_mult = _climate_multiplier(tmean, rain, tc)
            priors[tid] *= clim_mult
    
    # 4. Latitude-based tropical/temperate adjustment
    abs_lat = abs(lat)
    if abs_lat < 23.5:
        # Tropical: elevated insect + fungal
        for tid in priors:
            tc = THREAT_CLASS.get(tid, ThreatClass.DISEASE)
            if tc == ThreatClass.INSECT:
                priors[tid] *= 1.15
            elif tc == ThreatClass.DISEASE:
                priors[tid] *= 1.10
    elif abs_lat > 50:
        # Cool temperate: suppressed insect, elevated powdery mildew
        for tid in priors:
            tc = THREAT_CLASS.get(tid, ThreatClass.DISEASE)
            if tc == ThreatClass.INSECT:
                priors[tid] *= 0.75
        if ThreatId.POWDERY_MILDEW in priors:
            priors[ThreatId.POWDERY_MILDEW] *= 1.2
    
    # 5. Clamp all priors to [0.01, 0.30]
    for tid in priors:
        priors[tid] = max(0.01, min(0.30, priors[tid]))
    
    return priors
