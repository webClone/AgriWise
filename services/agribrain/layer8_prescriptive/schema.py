"""
Layer 8 Schema: Prescriptive Intelligence -- Research-Grade Contracts v8.2.0

Strict typed I/O with evidence trace, reliability-aware behavior,
audit trail, degradation modes, and advanced intelligence engine contracts.

Core Outputs:
  - ActionCard: ranked intervention with priority breakdown + evidence
  - ScheduledAction: calendar placement with constraint status
  - ZoneActionPlan: per-zone allocation
  - Layer8Output: full prescriptive plan

Intelligence Engine Contracts:
  - BBCHStageInfo: phenology-aware dosing parameters
  - NutrientInteractionResult: Liebig's law + antagonism analysis
  - IPMDecision: Integrated Pest Management cascade output
  - EnvironmentalRiskScore: leaching/runoff/compliance scoring
  - CognitiveLoadProfile: decision fatigue management
  - AdoptionProfile: farmer adoption probability
  - FramedMessage: prospect-theory message framing

Invariants:
  - rates >= 0, <= max safe limits
  - zone allocations sum <= 1.0 per action
  - schedule dates within horizon
  - blocked -> no CONFIRMED schedule
  - every ActionCard has >= 1 evidence item
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
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


class IPMLevel(str, Enum):
    """Integrated Pest Management escalation ladder."""
    MONITOR = "MONITOR"
    SCOUT = "SCOUT"
    BIOLOGICAL = "BIOLOGICAL"
    CHEMICAL_TARGETED = "CHEMICAL_TARGETED"
    CHEMICAL_BROAD = "CHEMICAL_BROAD"


class FrameType(str, Enum):
    """Prospect-theory message framing."""
    LOSS = "LOSS"
    GAIN = "GAIN"
    NEUTRAL = "NEUTRAL"


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
# Intelligence Engine Contracts
# ============================================================================

@dataclass
class BBCHStageInfo:
    """Phenology-aware dosing parameters from BBCH scale lookup."""
    bbch_code: int                       # 0-99 BBCH code
    stage_name: str                      # e.g. "V6", "R1", "TILLERING"
    crop: str                            # crop identifier
    absorption_coefficients: Dict[str, float]  # nutrient -> 0-1 fraction of total uptake
    critical_period: bool                # True if crop is in critical growth window
    water_demand_factor: float           # multiplier for irrigation rate (0.5-2.0)
    growth_rate_factor: float            # relative growth rate at this stage


@dataclass
class NutrientInteractionResult:
    """Liebig's Law analysis + synergy/antagonism matrix output."""
    limiting_nutrient: Optional[str]     # most limiting nutrient (Liebig's minimum)
    limiting_severity: float             # 0-1 severity of limitation
    interaction_adjustments: Dict[str, float]  # nutrient -> rate multiplier
    antagonisms_detected: List[Tuple[str, str, float]]  # (nutrient_A, nutrient_B, severity)
    synergies_detected: List[Tuple[str, str, float]]    # (nutrient_A, nutrient_B, benefit)
    recommended_order: List[str]         # application order (fix limiting first)
    explain: str                         # human-readable summary


@dataclass
class IPMDecision:
    """IPM cascade output for a single threat."""
    threat_id: str
    escalation_level: IPMLevel           # which rung on the IPM ladder
    economic_injury_level: float         # EIL threshold (0-1)
    action_threshold: float              # AT = EIL * safety_factor
    current_pressure: float              # observed/estimated pest pressure
    above_threshold: bool                # True if current_pressure > AT
    pre_harvest_interval_days: int       # minimum days before harvest (PHI)
    resistance_risk: str                 # "LOW", "MODERATE", "HIGH"
    recommended_mode_of_action: str      # chemical class rotation
    explain: str


@dataclass
class EnvironmentalRiskScore:
    """Leaching, runoff, and buffer zone compliance scoring."""
    leaching_index: float                # 0-1 (0=safe, 1=extreme risk)
    runoff_potential: float              # 0-1
    buffer_compliance: bool              # True if meets buffer zone requirements
    storm_event_risk: bool               # True if heavy rain forecast within 48h
    environmental_penalty: float         # 0-1 penalty applied to action score
    risk_factors: List[str]              # human-readable risk factors
    recommendation: str                  # "PROCEED", "DELAY", "REDUCE_RATE", "PROHIBIT"


@dataclass
class CognitiveLoadProfile:
    """Decision fatigue management output."""
    total_complexity: float              # sum of action complexity scores
    max_complexity_budget: float         # per-session cap
    actions_presented: int               # number of actions shown to farmer
    actions_suppressed: int              # number pruned for cognitive relief
    action_groups: List[Dict[str, Any]]  # grouped related actions
    fatigue_warning: bool                # True if near or over budget


@dataclass
class AdoptionProfile:
    """Farmer adoption probability from behavioral model."""
    adoption_probability: float          # 0-1 likelihood farmer follows recommendation
    perceived_usefulness: float          # 0-1 TAM factor
    perceived_ease: float                # 0-1 TAM factor
    cost_sensitivity: float              # 0-1 (1=very cost-sensitive)
    familiarity_score: float             # 0-1 (1=very familiar with this action)
    barriers: List[str]                  # adoption barriers identified
    nudge_strategy: str                  # "SIMPLIFY", "REFRAME", "SOCIAL_PROOF", "NONE"


@dataclass
class FramedMessage:
    """Prospect-theory framed recommendation message."""
    frame_type: FrameType
    primary_message: str                 # main recommendation text
    loss_frame: str                      # loss-framed version
    gain_frame: str                      # gain-framed version
    anchor_value: str                    # anchoring reference (e.g. "$50 to protect $800/ha")
    social_proof: str                    # regional adoption stat
    temporal_urgency: str                # "ACT_WITHIN_3_DAYS", "CONSIDER_2_WEEKS", etc.
    urgency_justified: bool              # True if urgency is backed by data (prevents crying wolf)


# ============================================================================
# Action Card
# ============================================================================

@dataclass
class PriorityBreakdown:
    """Multi-objective score decomposition."""
    impact_score: float       # 0-1: expected benefit magnitude
    urgency_score: float      # 0-1: time sensitivity
    risk_score: float         # 0-1: risk reduction value
    cost_score: float         # 0-1: inverse cost penalty (high = cheap)
    confidence_score: float   # 0-1: derived from L0 trust + upstream confidence


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
    Ranked intervention with full evidence trace + intelligence engine metadata.

    Invariants:
      - priority_score = weighted sum of breakdown components
      - is_allowed=False -> never scheduled as CONFIRMED
      - evidence must have >= 1 item (or heuristic=True)
    """
    action_id: str
    action_type: ActionType
    priority_score: float
    priority_breakdown: PriorityBreakdown

    zone_targets: List[str]              # zone IDs
    zone_allocation: Dict[str, float]    # zone_id -> fraction (0-1)

    rate: Optional[RateRange] = None
    time_window: Optional[TimeWindow] = None

    evidence: List[PrescriptiveEvidence] = field(default_factory=list)

    is_allowed: bool = True
    blocked_reason: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    heuristic: bool = False              # True if no evidence, just a rule

    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE
    explain: str = ""                    # one-line reason for UI

    # --- Intelligence engine outputs (populated by pipeline) ---
    phenology_info: Optional[BBCHStageInfo] = None
    nutrient_interaction: Optional[NutrientInteractionResult] = None
    ipm_decision: Optional[IPMDecision] = None
    env_risk: Optional[EnvironmentalRiskScore] = None
    adoption: Optional[AdoptionProfile] = None
    framed_message: Optional[FramedMessage] = None


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
    crop: str = "corn"                    # crop identifier for phenology engine
    soil_static: Dict[str, float] = field(default_factory=lambda: {
        "soil_clay": 22.0, "soil_ph": 6.5, "soil_org_carbon": 1.8,
    })


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
    cognitive_load: Optional[CognitiveLoadProfile] = None
    
    quality: PrescriptiveQuality = field(default_factory=lambda: PrescriptiveQuality(
        decision_reliability=0.5,
        degradation_mode=PrescriptiveDegradation.NORMAL,
        audit_grade="B"
    ))
    audit: PrescriptiveAudit = field(default_factory=PrescriptiveAudit)
