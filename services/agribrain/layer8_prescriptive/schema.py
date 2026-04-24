"""
Layer 8 Schema: Prescriptive Intelligence — Research-Grade Contracts

Strict typed I/O with evidence trace, reliability-aware behavior,
audit trail, and degradation modes.

Outputs:
  - ActionCard: ranked intervention with priority breakdown + evidence
  - ScheduledAction: calendar placement with constraint status
  - ZoneActionPlan: per-zone allocation
  - Layer8Output: full prescriptive plan

Invariants:
  - rates >= 0, <= max safe limits
  - zone allocations sum <= 1.0 per action
  - schedule dates within horizon
  - blocked -> no CONFIRMED schedule
  - every ActionCard has >= 1 evidence item
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class ActionType(str, Enum):
    IRRIGATE = "IRRIGATE"
    FERTILIZE = "FERTILIZE"
    SCOUT = "SCOUT"
    SPRAY = "SPRAY"
    WAIT = "WAIT"
    REPLANT = "REPLANT"
    HARVEST_PLAN = "HARVEST_PLAN"
    MONITOR = "MONITOR"


class ScheduleStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    TENTATIVE = "TENTATIVE"
    BLOCKED = "BLOCKED"


class PrescriptiveDegradation(str, Enum):
    NORMAL = "NORMAL"
    LOW_TRUST = "LOW_TRUST"           # audit grade C
    VERY_LOW_TRUST = "VERY_LOW_TRUST" # audit grade D/F
    DATA_GAP = "DATA_GAP"
    CONFLICT_FLAG = "CONFLICT_FLAG"    # unresolved upstream conflicts


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"       # grade A/B, uncertainty low
    MODERATE = "MODERATE"  # grade C or moderate uncertainty
    LOW = "LOW"         # grade D/F or high uncertainty


# ============================================================================
# Evidence
# ============================================================================

@dataclass
class PrescriptiveEvidence:
    """One piece of evidence supporting/opposing an action."""
    source_layer: str           # "L3", "L4", "L5", "L0"
    evidence_type: str          # "diagnosis", "nutrient_state", "threat", "audit"
    reference_id: str           # upstream problem_id / threat_id / audit flag
    contribution: float         # -1 to +1 (negative = contra)
    description: str            # human-readable reason


# ============================================================================
# Action Card
# ============================================================================

@dataclass
class PriorityBreakdown:
    """Multi-objective score decomposition."""
    impact_score: float       # 0–1: expected benefit magnitude
    urgency_score: float      # 0–1: time sensitivity
    risk_score: float         # 0–1: risk reduction value
    cost_score: float         # 0–1: inverse cost penalty (high = cheap)
    confidence_score: float   # 0–1: derived from L0 trust + upstream confidence


@dataclass
class RateRange:
    """Application rate with uncertainty bounds."""
    recommended: float          # kg/ha, mm, L/ha
    min_safe: float
    max_safe: float
    unit: str                   # "kg_N/ha", "mm", "L/ha"


@dataclass
class TimeWindow:
    """Feasible execution window."""
    earliest: str               # ISO date
    latest: str                 # ISO date
    optimal: Optional[str] = None


@dataclass
class ActionCard:
    """
    Ranked intervention with full evidence trace.
    
    Invariants:
      - priority_score = weighted sum of breakdown components
      - is_allowed=False → never scheduled as CONFIRMED
      - evidence must have >= 1 item (or heuristic=True)
    """
    action_id: str
    action_type: ActionType
    priority_score: float
    priority_breakdown: PriorityBreakdown
    
    zone_targets: List[str]              # zone IDs
    zone_allocation: Dict[str, float]    # zone_id → fraction (0–1)
    
    rate: Optional[RateRange] = None
    time_window: Optional[TimeWindow] = None
    
    evidence: List[PrescriptiveEvidence] = field(default_factory=list)
    
    is_allowed: bool = True
    blocked_reason: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    heuristic: bool = False              # True if no evidence, just a rule
    
    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE
    explain: str = ""                    # one-line reason for UI


# ============================================================================
# Schedule
# ============================================================================

@dataclass
class ScheduledAction:
    """Calendar placement with constraint validation."""
    action_id: str
    action_type: ActionType
    scheduled_date: Optional[str]        # ISO date, None if BLOCKED
    status: ScheduleStatus
    blocking_constraints: List[str] = field(default_factory=list)
    priority_score: float = 0.0
    weather_ok: bool = True
    phenology_ok: bool = True


# ============================================================================
# Zone Plan
# ============================================================================

@dataclass
class ZoneActionPlan:
    """Per-zone prescription."""
    zone_id: str
    actions: List[str]                   # action_ids assigned to this zone
    allocation_fraction: float           # 0–1
    priority: str                        # "HIGH", "MEDIUM", "LOW", "SKIP"
    reason: str = ""


# ============================================================================
# Outcome Forecast
# ============================================================================

@dataclass
class OutcomeForecast:
    """Expected results if plan is executed."""
    yield_delta_pct: float       # expected yield change
    risk_reduction_pct: float    # expected risk reduction
    cost_total: float            # total cost estimate
    roi_pct: float               # return on investment
    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE


@dataclass
class Tradeoff:
    """Why action A was chosen over action B."""
    chosen_action_id: str
    rejected_action_id: str
    reason: str
    score_delta: float


# ============================================================================
# Quality / Audit
# ============================================================================

@dataclass
class PrescriptiveQuality:
    """Governance metrics."""
    decision_reliability: float          # 0–1
    degradation_mode: PrescriptiveDegradation
    audit_grade: str                     # from L0
    upstream_confidence: Dict[str, float] = field(default_factory=dict)
    missing_inputs: List[str] = field(default_factory=list)


@dataclass
class PrescriptiveAudit:
    """Full reproducibility trace."""
    upstream_run_ids: Dict[str, str] = field(default_factory=dict)
    evidence_snapshot: List[Dict[str, Any]] = field(default_factory=list)
    policy_checks: List[Dict[str, Any]] = field(default_factory=list)
    invariant_violations: List[str] = field(default_factory=list)


# ============================================================================
# Master Output
# ============================================================================

@dataclass
class Layer8Input:
    """Strict input contract from upstream layers."""
    diagnoses: List[Dict[str, Any]]       # from L3
    nutrient_states: Dict[str, Any]       # from L4
    bio_threats: Dict[str, Any]           # from L5
    weather_forecast: List[Dict[str, Any]]
    zone_ids: List[str]
    audit_grade: str = "B"
    source_reliability: Dict[str, float] = field(default_factory=dict)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    phenology_stage: str = "VEGETATIVE"
    horizon_days: int = 7


@dataclass
class Layer8Output:
    """
    Research-grade prescriptive output.
    
    Invariants enforced before emission:
      - rates >= 0
      - zone allocations sum <= 1.0 per action
      - schedule dates within horizon
      - blocked -> no CONFIRMED
      - every action has evidence or heuristic=True
    """
    run_id: str
    timestamp: str
    
    actions: List[ActionCard]
    schedule: List[ScheduledAction]
    zone_plan: Dict[str, ZoneActionPlan]
    
    outcome_forecast: OutcomeForecast
    tradeoffs: List[Tradeoff] = field(default_factory=list)
    
    quality: PrescriptiveQuality = field(default_factory=lambda: PrescriptiveQuality(
        decision_reliability=0.5,
        degradation_mode=PrescriptiveDegradation.NORMAL,
        audit_grade="B"
    ))
    audit: PrescriptiveAudit = field(default_factory=PrescriptiveAudit)
