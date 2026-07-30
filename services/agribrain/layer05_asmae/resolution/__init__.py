"""
ASMAE Resolution Subsystem.

Adaptive resolution ladder from 10m to 1m.

Public API:
    select_resolution(...)  →  ResolutionDecision
    generate_report(...)    →  ResolutionReport (audit)
"""

from .selector import select_resolution
from .report import generate_report, ResolutionReport
from .candidates import CandidateSet, CandidateResolution, generate_candidates
from .evaluator import EvaluationResult, evaluate_all_candidates
from .policy import PolicyResult, apply_policies
from .reason_codes import (
    ReasonCodeDetail,
    classify_code,
    # Commonly referenced codes
    PROMOTE_SHIFT_DIVERSITY,
    PROMOTE_HIGH_SUPPORT,
    DEMOTE_LOW_SUPPORT,
    DEMOTE_ILL_CONDITIONED,
    GATE_1M_CERTIFICATION_REQUIRED,
    GATE_1M_RETRO_PASS,
    GATE_1M_RETRO_FAIL,
    INFO_BEST_CANDIDATE,
    INFO_DEFAULT_RESOLUTION,
)

__all__ = [
    "select_resolution",
    "generate_report",
    "ResolutionReport",
    "CandidateSet",
    "CandidateResolution",
    "generate_candidates",
    "EvaluationResult",
    "evaluate_all_candidates",
    "PolicyResult",
    "apply_policies",
    "ReasonCodeDetail",
    "classify_code",
]
