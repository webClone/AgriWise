# ASMAE — Adaptive Scientific MicroZone Assimilation Engine
# Layer 0.5: Scientific micro-zone state estimation

from .config import ASMAE_VERSION, ASMAE_FEATURE_FLAG
from .evidence_classifier import classify_asmae_evidence, ASMAEEvidenceClassification

__all__ = [
    "ASMAE_VERSION",
    "ASMAE_FEATURE_FLAG",
    "classify_asmae_evidence",
    "ASMAEEvidenceClassification"
]
__version__ = "0.1.0"
