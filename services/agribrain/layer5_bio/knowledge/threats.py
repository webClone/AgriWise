
from services.agribrain.layer5_bio.schema import ThreatId, ThreatClass

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
