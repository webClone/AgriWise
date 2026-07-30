
from layer5_bio.schema import ThreatId, ThreatClass

# Conservative priors; later calibrate by region/crop
THREAT_PRIORS = {
    ThreatId.FUNGAL_LEAF_SPOT: 0.10,
    ThreatId.FUNGAL_RUST: 0.08,
    ThreatId.DOWNY_MILDEW: 0.06,
    ThreatId.POWDERY_MILDEW: 0.06,
    ThreatId.BACTERIAL_BLIGHT: 0.05,
    ThreatId.CHEWING_INSECTS: 0.09,
    ThreatId.SUCKING_INSECTS: 0.08,
    ThreatId.BORERS: 0.04,
    ThreatId.WEED_PRESSURE: 0.07,
}

THREAT_CLASS = {
    ThreatId.FUNGAL_LEAF_SPOT: ThreatClass.DISEASE,
    ThreatId.FUNGAL_RUST: ThreatClass.DISEASE,
    ThreatId.DOWNY_MILDEW: ThreatClass.DISEASE,
    ThreatId.POWDERY_MILDEW: ThreatClass.DISEASE,
    ThreatId.BACTERIAL_BLIGHT: ThreatClass.DISEASE,
    ThreatId.CHEWING_INSECTS: ThreatClass.INSECT,
    ThreatId.SUCKING_INSECTS: ThreatClass.INSECT,
    ThreatId.BORERS: ThreatClass.INSECT,
    ThreatId.WEED_PRESSURE: ThreatClass.WEED,
}


# ── Phenology Susceptibility Multipliers ─────────────────────────────────
# Science: Different growth stages have different vulnerability profiles.
# Flowering/reproductive stages are peak susceptibility for fungal diseases.
# Vegetative stages are peak vulnerability for weed competition.
# Senescence has low susceptibility across the board.

PHENOLOGY_SUSCEPTIBILITY = {
    "BARE_SOIL": {
        ThreatClass.DISEASE: 0.3,
        ThreatClass.INSECT: 0.2,
        ThreatClass.WEED: 1.5,   # Weeds colonize bare soil
    },
    "EMERGENCE": {
        ThreatClass.DISEASE: 0.5,
        ThreatClass.INSECT: 0.8,
        ThreatClass.WEED: 1.4,   # Weed competition at seedling stage
    },
    "VEGETATIVE": {
        ThreatClass.DISEASE: 1.0,
        ThreatClass.INSECT: 1.0,
        ThreatClass.WEED: 1.2,   # Still competing for resources
    },
    "REPRODUCTIVE": {
        ThreatClass.DISEASE: 1.5,  # Peak: flowering → fungal susceptibility
        ThreatClass.INSECT: 1.3,   # Fruit/grain attracts pests
        ThreatClass.WEED: 0.8,     # Canopy closure suppresses weeds
    },
    "MATURITY": {
        ThreatClass.DISEASE: 0.7,
        ThreatClass.INSECT: 0.6,
        ThreatClass.WEED: 0.5,
    },
    "SENESCENCE": {
        ThreatClass.DISEASE: 0.4,
        ThreatClass.INSECT: 0.3,
        ThreatClass.WEED: 0.3,
    },
}

# Default fallback when phenology stage is unknown
DEFAULT_SUSCEPTIBILITY = {
    ThreatClass.DISEASE: 1.0,
    ThreatClass.INSECT: 1.0,
    ThreatClass.WEED: 1.0,
}


def get_phenology_multiplier(stage: str, threat_class: ThreatClass) -> float:
    """Return phenology susceptibility multiplier for a given stage + threat class.
    
    Returns 1.0 (neutral) if stage is unknown or not in the table.
    """
    stage_key = stage.upper().replace(" ", "_") if stage else ""
    entry = PHENOLOGY_SUSCEPTIBILITY.get(stage_key, DEFAULT_SUSCEPTIBILITY)
    return entry.get(threat_class, 1.0)
