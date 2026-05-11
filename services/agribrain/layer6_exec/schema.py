"""
Layer 6 Schema — Strategic Execution & Intervention Intelligence (v7.0)

Production-grade data contracts for the Execution Intelligence engine.
Follows L4/L5 architecture standard: strict typing, full provenance,
belief/trust separation, deterministic content_hash().

Architecture:
  L1-L5 Intelligence Stack
    → InterventionSynthesisEngine (cross-layer fusion + conflict resolution)
    → ResourceFeasibilityEngine (operational constraint gating)
    → DAGExecutionEngine (state machine)
    → OutcomeEvaluationEngine (multi-metric causal assessment)
    → CalibrationEngine (prediction-vs-outcome learning loop)
    → Layer6Output (with content_hash)

Contract version: 7.0.0
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

# Upstream Contracts
from layer1_fusion.schema import FieldTensor
from layer1_fusion.schemas import DataHealthScore
from layer2_veg_int.schema import VegIntOutput
from layer3_decision.schema import (
    DecisionOutput, PlotContext, TaskNode, Driver, DegradationMode,
    ExecutionPlan, Diagnosis, Recommendation,
)
from layer4_nutrients.schema import NutrientIntelligenceOutput
from layer5_bio.schema import BioThreatIntelligenceOutput


# ============================================================================
# Enums (Locked)
# ============================================================================

class InterventionDomain(str, Enum):
    """What class of agronomic action."""
    IRRIGATION = "IRRIGATION"
    NUTRIENT = "NUTRIENT"
    PHYTOSANITARY = "PHYTOSANITARY"
    MECHANICAL = "MECHANICAL"
    MONITORING = "MONITORING"
    HARVEST_TIMING = "HARVEST_TIMING"


class ResourceType(str, Enum):
    """Operational resource categories."""
    EQUIPMENT = "EQUIPMENT"
    LABOR = "LABOR"
    CHEMICAL = "CHEMICAL"
    WATER = "WATER"
    BUDGET = "BUDGET"


class FeasibilityGrade(str, Enum):
    """Feasibility assessment grade (A = fully feasible → F = impossible)."""
    A = "A"  # Fully feasible, no constraints violated
    B = "B"  # Feasible with minor scheduling adjustments
    C = "C"  # Feasible but tight on resources/timing
    D = "D"  # Partially feasible, significant constraints
    F = "F"  # Infeasible, blocked by hard constraints


class ConflictType(str, Enum):
    """Cross-layer recommendation conflict categories."""
    IRRIGATION_VS_FUNGAL = "IRRIGATION_VS_FUNGAL"    # L3 says irrigate, L5 says high LWD risk
    NITROGEN_VS_LODGING = "NITROGEN_VS_LODGING"      # L4 says apply N, L3 says lodging risk
    HERBICIDE_VS_CROP_STAGE = "HERBICIDE_VS_CROP_STAGE"  # L5 says treat weeds, phenology says too late
    BUDGET_CONFLICT = "BUDGET_CONFLICT"              # Multiple interventions exceed budget
    TIMING_CONFLICT = "TIMING_CONFLICT"              # Overlapping equipment needs
    WATER_QUOTA_CONFLICT = "WATER_QUOTA_CONFLICT"    # Irrigation demand exceeds quota


class ConflictResolutionStrategy(str, Enum):
    """How the conflict was resolved."""
    PRIORITIZE_SAFETY = "PRIORITIZE_SAFETY"      # Chose the safer option
    PRIORITIZE_YIELD = "PRIORITIZE_YIELD"        # Chose yield-maximizing option
    COMPROMISE = "COMPROMISE"                     # Modified both recommendations
    DEFER_TO_FARMER = "DEFER_TO_FARMER"          # Flagged for human decision
    SUPPRESS_LOWER = "SUPPRESS_LOWER"            # Lower-confidence recommendation suppressed


class EvidenceType(str, Enum):
    SCOUT_FORM = "SCOUT_FORM"
    PHOTO = "PHOTO"
    TRAP_COUNT = "TRAP_COUNT"
    LAB_RESULT = "LAB_RESULT"
    MACHINE_LOG = "MACHINE_LOG"
    SENSOR_PUSH = "SENSOR_PUSH"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    EXPIRED = "EXPIRED"


class TaskKind(str, Enum):
    VERIFY = "VERIFY"
    INTERVENE = "INTERVENE"
    MONITOR = "MONITOR"
    ESCALATE = "ESCALATE"


class OutcomeMetricId(str, Enum):
    NDVI_RECOVERY = "NDVI_RECOVERY"
    GROWTH_VELOCITY_RECOVERY = "GROWTH_VELOCITY_RECOVERY"
    RISK_REDUCTION_DELTA = "RISK_REDUCTION_DELTA"
    YIELD_PROXY_DELTA = "YIELD_PROXY_DELTA"
    STRESS_INDEX_CHANGE = "STRESS_INDEX_CHANGE"


class CausalMethod(str, Enum):
    PRE_POST = "PRE_POST"
    DIFF_IN_DIFF = "DIFF_IN_DIFF"
    SYNTHETIC_BASELINE = "SYNTHETIC_BASELINE"
    NONE = "NONE"


class ApprovalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ============================================================================
# Operational Context (expanded)
# ============================================================================

@dataclass
class ResourceConstraint:
    """Single operational guardrail."""
    resource_type: ResourceType
    total_capacity: float         # Total available (e.g., budget in €, water in mm)
    consumed: float               # Already used this season
    remaining: float              # = total - consumed
    unit: str = ""                # "EUR", "mm", "hours", etc.


@dataclass
class OperationalContext:
    """Full operational constraints and resources for intervention planning."""
    equipment_ids: List[str] = field(default_factory=list)
    workforce_available: bool = True
    labor_hours_available: float = 40.0         # Weekly labor budget
    water_quota_remaining: float = 1000.0       # mm for the season
    budget_remaining: float = 5000.0            # EUR
    permissions: List[str] = field(default_factory=list)

    # Agronomic context
    season_stage: str = "MID"                   # EARLY, MID, LATE, POST_HARVEST
    days_since_planting: int = 60
    regulatory_zone: str = "STANDARD"           # NVZ, BUFFER_STRIP, ORGANIC, STANDARD

    # Plot geometry (GAP 9: real area from polygon instead of hardcoded default)
    plot_area_ha: float = 10.0                  # Computed from polygon via Shoelace formula

    # Resource breakdown (detailed)
    resource_constraints: List[ResourceConstraint] = field(default_factory=list)



# ============================================================================
# Evidence (unchanged — functional as-is)
# ============================================================================

@dataclass(frozen=True)
class NormalizedEvidence:
    """Immutable, hashed evidence record."""
    evidence_id: str              # EV-{sha256}
    type: EvidenceType
    timestamp: str                # ISO
    plot_id: str
    payload: Dict[str, Any]

    # Spatial extensions
    zone_id: Optional[str] = None
    location: Optional[Dict[str, float]] = None

    source_refs: Dict[str, str] = field(default_factory=dict)
    attachment_hashes: List[str] = field(default_factory=list)


# ============================================================================
# Upstream Intelligence Digest (farmer explainability)
# ============================================================================

@dataclass
class UpstreamDigest:
    """Condensed intelligence from L1-L5 for farmer-facing explanations.

    This is the key data structure for downstream explainability.
    Every intervention recommendation must trace back through this digest
    to the original evidence that triggered it.
    """
    # L1: Environmental conditions
    rain_7d_mm: float = 0.0
    tmean_7d_c: float = 20.0
    heat_days: int = 0
    frost_risk: bool = False
    soil_moisture_status: str = "ADEQUATE"       # DRY, ADEQUATE, WET, SATURATED

    # L2: Crop state
    ndvi_current: float = 0.7
    ndvi_trend: str = "STABLE"                   # RISING, STABLE, DECLINING, CRASH
    growth_velocity: float = 0.01
    phenology_stage: str = "VEGETATIVE"
    canopy_cover_pct: float = 70.0

    # L3: Decision diagnoses (top 3)
    active_diagnoses: List[Dict[str, Any]] = field(default_factory=list)
    # [{problem_id, probability, severity, confidence, explain}]

    # L4: Nutrient state
    nutrient_deficiencies: List[Dict[str, Any]] = field(default_factory=list)
    # [{nutrient, probability_deficient, severity, recommended_kg_ha}]
    water_balance_status: str = "BALANCED"       # DEFICIT, BALANCED, SURPLUS

    # L5: BioThreat state
    active_threats: List[Dict[str, Any]] = field(default_factory=list)
    # [{threat_id, probability, confidence, severity, threat_class}]
    leaf_wetness_hours: float = 0.0
    fungal_pressure: float = 0.0
    insect_pressure: float = 0.0

    # Cross-layer confidence floor
    min_upstream_confidence: float = 0.5


# ============================================================================
# Intervention Candidate
# ============================================================================

@dataclass
class InterventionCandidate:
    """Scored, traceable intervention recommendation.

    Separates WHAT to do (action) from WHY (evidence trace)
    and WHETHER we can (feasibility).
    """
    intervention_id: str                          # INV-{hash}
    domain: InterventionDomain
    action_type: str                              # VERIFY, INTERVENE, MONITOR, ESCALATE
    title: str                                    # Human-readable: "Apply foliar fungicide"
    instructions: str                             # Detailed farmer instructions

    # Scoring
    utility_score: float                          # Combined score: impact × urgency × conf / cost
    expected_impact: float                        # 0.0-1.0: expected improvement
    urgency: float                                # 0.0-1.0: time pressure
    confidence: float                             # 0.0-1.0: how much we trust this recommendation

    # Economics
    estimated_cost_eur: float = 0.0
    estimated_roi: float = 0.0                    # Return on investment ratio
    cost_of_inaction_eur: float = 0.0             # What happens if farmer does nothing

    # Timing
    timing_window: Dict[str, str] = field(default_factory=dict)  # {start, end}
    optimal_day: str = ""                         # Best single day to execute

    # Traceability (farmer explainability)
    source_layer: str = ""                        # "L3", "L4", "L5"
    linked_diagnosis_ids: List[str] = field(default_factory=list)
    linked_threat_ids: List[str] = field(default_factory=list)
    evidence_summary: str = ""                    # Plain-language: "Based on 45mm rain and NDVI drop..."

    # Feasibility (filled by ResourceFeasibilityEngine)
    feasibility_grade: FeasibilityGrade = FeasibilityGrade.A
    blocked_reasons: List[str] = field(default_factory=list)
    resource_requirements: List[Dict[str, Any]] = field(default_factory=list)
    # [{resource_type, quantity, unit}]

    # Spatial targeting
    target_zones: List[str] = field(default_factory=list)

    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Other intervention_ids


# ============================================================================
# Conflict Resolution
# ============================================================================

@dataclass
class ConflictRecord:
    """Record of a cross-layer recommendation conflict and its resolution.

    Critical for farmer trust: "We noticed X said one thing and Y said another.
    Here's how we resolved it."
    """
    conflict_id: str
    conflict_type: ConflictType
    description: str                              # Human-readable explanation

    # The conflicting sources
    source_a: Dict[str, Any] = field(default_factory=dict)
    # {layer, recommendation_id, action, confidence}
    source_b: Dict[str, Any] = field(default_factory=dict)

    # Resolution
    resolution: ConflictResolutionStrategy = ConflictResolutionStrategy.DEFER_TO_FARMER
    resolution_rationale: str = ""
    winning_source: str = ""                      # Which layer's recommendation won
    suppressed_intervention_ids: List[str] = field(default_factory=list)


# ============================================================================
# Outcome Evaluation
# ============================================================================

@dataclass
class OutcomeMetric:
    """Evaluated result of an action or event."""
    metric_id: OutcomeMetricId
    delta_value: float
    confidence: float                             # 0.0-1.0 (method reliability)
    method: CausalMethod
    baseline_window: Dict[str, str] = field(default_factory=dict)
    eval_window: Dict[str, str] = field(default_factory=dict)
    confounders_present: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class OutcomeProjection:
    """Forward-looking projection of expected intervention effect."""
    intervention_id: str
    projected_ndvi_delta: float = 0.0
    projected_risk_reduction: float = 0.0
    projected_yield_impact_pct: float = 0.0
    projection_confidence: float = 0.5
    projection_horizon_days: int = 14
    assumptions: List[str] = field(default_factory=list)


# ============================================================================
# Calibration (Learning Loop)
# ============================================================================

@dataclass
class CalibrationProposal:
    """Proposed update to upstream system parameters."""
    target_layer: str
    parameter_key: str
    current_value: float
    proposed_value: float
    reason: str
    evidence_support: List[str] = field(default_factory=list)
    confidence: float = 0.5
    magnitude: float = 0.0                        # |proposed - current|
    status: ApprovalStatus = ApprovalStatus.PROPOSED


# ============================================================================
# Execution State (DAG)
# ============================================================================

@dataclass
class TaskState:
    """Rich state for a single task in the DAG."""
    task_id: str
    status: TaskStatus
    assigned_at: str = ""                         # ISO timestamp
    started_at: str = ""
    completed_at: str = ""
    blocked_reason: str = ""
    evidence_ids: List[str] = field(default_factory=list)  # Evidence that drove completion


@dataclass
class ExecutionState:
    """Persistable state of the execution DAG."""
    tasks: Dict[str, TaskStatus] = field(default_factory=dict)
    task_details: Dict[str, TaskState] = field(default_factory=dict)
    last_updated: str = ""
    logs: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================================
# Input Contract
# ============================================================================

@dataclass
class Layer6Input:
    """Strict input from L1-L5 + Ops + Evidence + State."""
    tensor: Any                                   # FieldTensor (Any for resilience)
    veg_int: Any                                  # VegIntOutput
    decision_l3: Any                              # DecisionOutput
    nutrient_l4: Any = None                       # NutrientIntelligenceOutput (optional)
    bio_l5: Any = None                            # BioThreatIntelligenceOutput (optional)

    op_context: OperationalContext = field(default_factory=OperationalContext)
    evidence_batch: List[Dict[str, Any]] = field(default_factory=list)
    current_state: ExecutionState = field(default_factory=ExecutionState)


# ============================================================================
# Quality Metrics
# ============================================================================

@dataclass
class QualityMetricsL6:
    """Governance and reliability metrics for Layer 6 output."""
    decision_reliability: float = 0.0
    missing_drivers: List[str] = field(default_factory=list)
    data_completeness: Dict[str, float] = field(default_factory=dict)
    task_completion_rate: float = 0.0

    # L6-specific
    upstream_confidence_floor: float = 0.0        # Min confidence across L1-L5
    intervention_feasibility_score: float = 0.0   # Mean feasibility of portfolio
    confounder_count: int = 0
    conflict_count: int = 0
    penalties_applied: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================================
# Audit Trail
# ============================================================================

@dataclass
class AuditSnapshot:
    """Full reproducibility trace for Layer 6."""
    features_snapshot: Dict[str, Any] = field(default_factory=dict)
    policy_snapshot: Dict[str, Any] = field(default_factory=dict)
    model_versions: Dict[str, str] = field(default_factory=dict)

    # L6-specific audit
    upstream_digest: Optional[UpstreamDigest] = None
    intervention_count: int = 0
    conflict_count: int = 0
    calibration_count: int = 0
    dag_task_count: int = 0


# ============================================================================
# Run Meta
# ============================================================================

@dataclass
class RunMeta:
    """Layer 6 run metadata."""
    layer: str = "L6"
    run_id: str = ""
    parent_run_ids: Dict[str, str] = field(default_factory=dict)
    generated_at: str = ""
    degradation_mode: DegradationMode = DegradationMode.NORMAL
    engine_version: str = "7.0.0"


# ============================================================================
# Layer 6 Output (the canonical output package)
# ============================================================================

@dataclass
class Layer6Output:
    """The canonical output of the Layer 6 Strategic Execution engine.

    Deterministic: same upstream inputs → same Layer6Output + content_hash().
    """
    run_meta: RunMeta

    # Core outputs
    intervention_portfolio: List[InterventionCandidate] = field(default_factory=list)
    conflict_log: List[ConflictRecord] = field(default_factory=list)
    updated_state: ExecutionState = field(default_factory=ExecutionState)
    evidence_registry: List[NormalizedEvidence] = field(default_factory=list)

    # Outcome intelligence
    outcome_report: List[OutcomeMetric] = field(default_factory=list)
    outcome_projections: List[OutcomeProjection] = field(default_factory=list)

    # Learning loop
    calibration_proposals: List[CalibrationProposal] = field(default_factory=list)

    # Farmer explainability
    upstream_digest: Optional[UpstreamDigest] = None

    # Governance
    quality_metrics: QualityMetricsL6 = field(default_factory=QualityMetricsL6)
    data_health: DataHealthScore = field(default_factory=DataHealthScore)
    audit: AuditSnapshot = field(default_factory=AuditSnapshot)

    def content_hash(self) -> str:
        """Deterministic hash for reproducibility verification."""
        payload = {
            "run_id": self.run_meta.run_id,
            "intervention_count": len(self.intervention_portfolio),
            "conflict_count": len(self.conflict_log),
            "task_count": len(self.updated_state.tasks),
            "outcome_count": len(self.outcome_report),
            "calibration_count": len(self.calibration_proposals),
            "intervention_ids": sorted(c.intervention_id for c in self.intervention_portfolio),
            "utility_scores": [round(c.utility_score, 4) for c in self.intervention_portfolio],
            "reliability": round(self.quality_metrics.decision_reliability, 4),
            "health_status": self.data_health.status,
        }
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
