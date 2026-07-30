"""
ASMAE Resolution Reason Codes.

Structured reason codes for resolution promotion, demotion, and gating.

Categories:
  - promote: Evidence that justifies a finer resolution.
  - demote:  Evidence that degrades confidence at this resolution.
  - gate:    Hard pass/fail — no partial credit.
  - info:    Informational annotation (no score impact).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# ── Promote Codes ───────────────────────────────────────────────────────────

PROMOTE_HIGH_SUPPORT = "PROMOTE_HIGH_SUPPORT"
PROMOTE_WELL_CONDITIONED = "PROMOTE_WELL_CONDITIONED"
PROMOTE_SHIFT_DIVERSITY = "PROMOTE_SHIFT_DIVERSITY"
PROMOTE_TEMPORAL_SPREAD = "PROMOTE_TEMPORAL_SPREAD"
PROMOTE_SCENE_COUNT = "PROMOTE_SCENE_COUNT"
PROMOTE_SAR_DIVERSITY = "PROMOTE_SAR_DIVERSITY"
PROMOTE_IDENTIFIABILITY = "PROMOTE_IDENTIFIABILITY"

# ── Demote Codes ────────────────────────────────────────────────────────────

DEMOTE_LOW_SUPPORT = "DEMOTE_LOW_SUPPORT"
DEMOTE_ILL_CONDITIONED = "DEMOTE_ILL_CONDITIONED"
DEMOTE_INSUFFICIENT_SCENES = "DEMOTE_INSUFFICIENT_SCENES"
DEMOTE_NO_SHIFT_DIVERSITY = "DEMOTE_NO_SHIFT_DIVERSITY"
DEMOTE_TEMPORAL_GAP = "DEMOTE_TEMPORAL_GAP"
DEMOTE_REGISTRATION_UNCERTAINTY = "DEMOTE_REGISTRATION_UNCERTAINTY"
DEMOTE_CLOUD_COVERAGE = "DEMOTE_CLOUD_COVERAGE"
DEMOTE_LOW_SNR = "DEMOTE_LOW_SNR"
DEMOTE_IDENTIFIABILITY_FAIL = "DEMOTE_IDENTIFIABILITY_FAIL"
DEMOTE_RETROVALIDATION_FAIL = "DEMOTE_RETROVALIDATION_FAIL"

# ── Gate Codes ──────────────────────────────────────────────────────────────

GATE_1M_CERTIFICATION_REQUIRED = "GATE_1M_CERTIFICATION_REQUIRED"
GATE_1M_RETRO_PASS = "GATE_1M_RETRO_PASS"
GATE_1M_RETRO_FAIL = "GATE_1M_RETRO_FAIL"
GATE_MIN_SCENES = "GATE_MIN_SCENES"
GATE_MIN_SUPPORT = "GATE_MIN_SUPPORT"
GATE_NYQUIST_EXCEEDED = "GATE_NYQUIST_EXCEEDED"

# ── Info Codes ──────────────────────────────────────────────────────────────

INFO_DEFAULT_RESOLUTION = "INFO_DEFAULT_RESOLUTION"
INFO_BEST_CANDIDATE = "INFO_BEST_CANDIDATE"
INFO_RESEARCH_ONLY = "INFO_RESEARCH_ONLY"
INFO_VISUAL_OVERRIDE = "INFO_VISUAL_OVERRIDE"


# ── Category Classifier ────────────────────────────────────────────────────

_CATEGORY_MAP: Dict[str, str] = {
    code: "promote"
    for code in [
        PROMOTE_HIGH_SUPPORT,
        PROMOTE_WELL_CONDITIONED,
        PROMOTE_SHIFT_DIVERSITY,
        PROMOTE_TEMPORAL_SPREAD,
        PROMOTE_SCENE_COUNT,
        PROMOTE_SAR_DIVERSITY,
        PROMOTE_IDENTIFIABILITY,
    ]
}

_CATEGORY_MAP.update({
    code: "demote"
    for code in [
        DEMOTE_LOW_SUPPORT,
        DEMOTE_ILL_CONDITIONED,
        DEMOTE_INSUFFICIENT_SCENES,
        DEMOTE_NO_SHIFT_DIVERSITY,
        DEMOTE_TEMPORAL_GAP,
        DEMOTE_REGISTRATION_UNCERTAINTY,
        DEMOTE_CLOUD_COVERAGE,
        DEMOTE_LOW_SNR,
        DEMOTE_IDENTIFIABILITY_FAIL,
        DEMOTE_RETROVALIDATION_FAIL,
    ]
})

_CATEGORY_MAP.update({
    code: "gate"
    for code in [
        GATE_1M_CERTIFICATION_REQUIRED,
        GATE_1M_RETRO_PASS,
        GATE_1M_RETRO_FAIL,
        GATE_MIN_SCENES,
        GATE_MIN_SUPPORT,
        GATE_NYQUIST_EXCEEDED,
    ]
})

_CATEGORY_MAP.update({
    code: "info"
    for code in [
        INFO_DEFAULT_RESOLUTION,
        INFO_BEST_CANDIDATE,
        INFO_RESEARCH_ONLY,
        INFO_VISUAL_OVERRIDE,
    ]
})


def classify_code(code: str) -> str:
    """Return the category for a reason code."""
    return _CATEGORY_MAP.get(code, "info")


# ── Structured Reason Detail ───────────────────────────────────────────────

@dataclass
class ReasonCodeDetail:
    """Structured reason code with numeric evidence.

    Carries the code, category, metric value, threshold, and
    optional human-readable message.
    """
    code: str
    category: str = ""          # promote | demote | gate | info
    resolution_m: int = 0
    value: Optional[float] = None
    threshold: Optional[float] = None
    message: str = ""

    def __post_init__(self) -> None:
        if not self.category:
            self.category = classify_code(self.code)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "code": self.code,
            "category": self.category,
            "resolution_m": self.resolution_m,
        }
        if self.value is not None:
            d["value"] = round(self.value, 4)
        if self.threshold is not None:
            d["threshold"] = round(self.threshold, 4)
        if self.message:
            d["message"] = self.message
        return d
