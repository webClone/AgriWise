"""
Layer 3 Decision & Action Intelligence — Canonical Schemas.

All data contracts for the Decision Intelligence engine.
Mirrors L1/L2 schema conventions: strict typing, full provenance,
uncertainty propagation, deterministic content_hash().

Architecture:
  L2 StressEvidence + VegetationFeature
    → Layer3InputContext (via L2→L3 adapter)
    → DecisionFeatures (via feature builder)
    → DiagnosisEngine (log-odds scoring)
    → PolicyEngine (compliance gates)
    → ExecutionPlan (DAG of tasks)
    → DecisionOutput (with content_hash)

Contract version: 1.0.0
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from layer1_fusion.schemas import DataHealthScore


# ============================================================================
# Vocabulary guardrails
# ============================================================================

FORBIDDEN_L3_VOCABULARY = (
    "guaranteed", "certain", "definitely", "always", "never",
    "100%", "impossible", "no risk", "safe to ignore",
    "skip verification", "override", "bypass",
)

ALLOWED_L3_VOCABULARY = (
    "probability", "confidence", "severity", "evidence",
    "indicates", "suggests", "risk", "verify", "intervene",
    "monitor", "alert", "recommend", "feasibility",
)


# ============================================================================
# Hard prohibitions
# ============================================================================

L3_HARD_PROHIBITIONS = (
    "no_diagnosis_without_evidence",       # every diagnosis p > 0.1 must have evidence trace
    "no_intervention_without_diagnosis",   # recommendations must link to diagnosis IDs
    "no_action_above_confidence_ceiling",  # action confidence ≤ data_health ceiling
    "no_blocked_action_allowed",           # blocked_reason → is_allowed must be False
    "probability_bounds",                  # all probabilities in [0, 1]
    "severity_bounds",                     # all severities in [0, 1]
    "confidence_bounds",                   # all confidences in [0, 1]
    "execution_plan_acyclic",              # DAG must have no cycles
    "lineage_complete",                    # lineage must reference L1 and L2 run IDs
    "content_hash_deterministic",          # same input → same hash
)


# ============================================================================
# Enums
# ============================================================================

class ProblemClass(Enum):
    DIAGNOSIS = "DIAGNOSIS"    # Actionable
    RISK = "RISK"              # Verify-first
    EVENT = "EVENT"            # Observational / Critical
    SYSTEM = "SYSTEM"          # Pipeline Health


class RiskIfWrong(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DegradationMode(Enum):
    NORMAL = "NORMAL"
    NO_SAR = "NO_SAR"                    # Missing SAR channels entirely
    LOW_SAR_CADENCE = "LOW_SAR_CADENCE"  # Count > 0 but <= 5
    WEATHER_ONLY = "WEATHER_ONLY"        # Missing Optical
    DATA_GAP = "DATA_GAP"               # Critical Missing Drivers


class Driver(Enum):
    NDVI = "NDVI"
    RAIN = "RAIN"
    TEMP = "TEMP"
    SAR_VV = "SAR_VV"
    SAR_VH = "SAR_VH"
    GDD = "GDD"
    NDVI_UNC = "NDVI_UNC"


# ============================================================================
# Plot context (static metadata)
# ============================================================================

@dataclass
class PlotContext:
    """Static metadata and constraints for the plot."""
    crop_type: str = "unknown"           # e.g. "corn", "wheat", "soy"
    variety: Optional[str] = None
    planting_date: str = ""              # YYYY-MM-DD
    irrigation_type: str = "rainfed"     # "drip", "pivot", "rainfed"
    management_goal: str = "yield_max"   # "yield_max", "cost_min", "sustainable"
    constraints: Dict[str, Any] = field(default_factory=dict)
    # e.g. {"water_quota_mm": 500, "budget_limit": 1000}


# ============================================================================
# Decision input (canonical — replaces legacy DecisionInput)
# ============================================================================

@dataclass
class DecisionInput:
    """Canonical ingestion contract for Layer 3.

    Consumes Layer3InputContext from the L2→L3 adapter,
    NOT raw FieldTensor or VegIntOutput.
    """
    l3_context: Any       # Layer3InputContext from L2 adapter
    context: PlotContext = field(default_factory=PlotContext)
    weather_forecast: List[Dict] = field(default_factory=list)


# ============================================================================
# Evidence term (log-odds atomic unit)
# ============================================================================

@dataclass
class EvidenceTerm:
    """Calibrated evidence unit.

    Follows: delta_logit = weight * normalized_score
    """
    feature_name: str       # e.g. "rain_sum_14d"
    window: str             # e.g. "14d", "current"
    value: float            # Raw value
    score: float            # [-1.0, 1.0]
    weight: float           # [0.0, 5.0+]
    contribution: float     # The actual logit delta


# ============================================================================
# Diagnosis (probabilistic conclusion)
# ============================================================================

@dataclass
class Diagnosis:
    """Research-grade probabilistic conclusion.

    Separates BELIEF (Probability from log-odds) from TRUST (Confidence from data quality).
    """
    problem_id: str            # WATER_STRESS, WATERLOGGING, etc.
    probability: float         # 0.0–1.0 (derived from logits)
    severity: float            # 0.0–1.0 (impact magnitude)
    confidence: float          # 0.0–1.0 (data quality / trust)

    evidence_trace: List[EvidenceTerm] = field(default_factory=list)
    contra_trace: List[EvidenceTerm] = field(default_factory=list)
    supports: Dict[str, List[str]] = field(default_factory=dict)

    # v4.0 Strict Contract
    problem_class: ProblemClass = ProblemClass.DIAGNOSIS
    drivers_used: List[Driver] = field(default_factory=list)
    drivers_missing: List[Driver] = field(default_factory=list)

    # Spatial extensions
    affected_area_pct: float = 100.0
    hotspot_zone_ids: List[str] = field(default_factory=list)


# ============================================================================
# Recommendation (actionable advice)
# ============================================================================

@dataclass
class Recommendation:
    """Actionable advice with compliance gates."""
    action_id: str
    action_type: str           # "VERIFY" | "INTERVENE" | "ALERT"
    priority_score: float

    expected_impact: float     # 0.0–1.0
    urgency: float             # 0.0–1.0
    confidence: float          # 0.0–1.0

    is_allowed: bool
    blocked_reason: List[str]
    risk_if_wrong: RiskIfWrong

    linked_diagnosis_ids: List[str]
    explain: str

    # v4.0 Strict Contract
    preconditions: List[str] = field(default_factory=list)

    # Execution Details
    timing: Dict[str, str] = field(default_factory=dict)
    resource_est: Dict[str, float] = field(default_factory=dict)


# ============================================================================
# Execution plan (DAG of tasks)
# ============================================================================

@dataclass
class TaskNode:
    """Node in the Execution Graph."""
    task_id: str
    type: str                  # VERIFY | INTERVENE | ALERT
    instructions: str
    required_inputs: List[str]
    completion_signal: str     # e.g. "USER_CONFIRM", "SENSOR_READING"
    depends_on: List[str] = field(default_factory=list)

    # Spatial extensions
    target_zones: List[str] = field(default_factory=list)
    target_points: List[Dict[str, float]] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    """DAG of tasks."""
    tasks: List[TaskNode] = field(default_factory=list)
    edges: List[Dict[str, str]] = field(default_factory=list)
    recommended_start_date: str = ""
    review_date: str = ""


# ============================================================================
# Quality metrics
# ============================================================================

@dataclass
class QualityMetrics:
    """Governance and Reliability Metrics."""
    decision_reliability: float = 0.0
    missing_drivers: List[Driver] = field(default_factory=list)
    data_completeness: Dict[str, float] = field(default_factory=dict)
    l2_confidence_summary: Dict[str, float] = field(default_factory=dict)
    degradation_mode: DegradationMode = DegradationMode.NORMAL


# ============================================================================
# Audit trail
# ============================================================================

@dataclass
class AuditTrail:
    """Full reproducibility trace."""
    features_snapshot: Dict[str, Any] = field(default_factory=dict)
    log_odds_table: List[Dict[str, Any]] = field(default_factory=list)
    policy_checks: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================================
# Provenance (mirrors L1/L2 pattern)
# ============================================================================

@dataclass
class Layer3Provenance:
    """Full provenance for Layer 3 output."""
    run_id: str = ""
    engine_version: str = "layer3_decision_v1"
    contract_version: str = "1.0.0"
    layer1_run_id: str = ""
    layer2_run_id: str = ""

    diagnosis_count: int = 0
    recommendation_count: int = 0
    task_count: int = 0

    invariant_violations: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: Optional[datetime] = None


# ============================================================================
# Diagnostics (mirrors L1/L2 pattern)
# ============================================================================

@dataclass
class Layer3Diagnostics:
    """Detailed diagnostics for Layer 3."""
    status: Literal["ok", "degraded", "unusable"] = "ok"

    data_health: DataHealthScore = field(default_factory=DataHealthScore)
    hard_prohibition_results: Dict[str, bool] = field(default_factory=dict)

    diagnosis_type_counts: Dict[str, int] = field(default_factory=dict)
    recommendation_type_counts: Dict[str, int] = field(default_factory=dict)

    input_degradation_flags: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ============================================================================
# Decision output (the canonical output package)
# ============================================================================

@dataclass
class DecisionOutput:
    """The canonical output of the Layer 3 Decision Intelligence engine.

    Deterministic: same Layer3InputContext → same DecisionOutput + content_hash().
    """
    schema_version: str = "layer3_v1"
    run_id_l3: str = ""
    lineage: Dict[str, str] = field(default_factory=dict)
    timestamp_utc: str = ""

    diagnoses: List[Diagnosis] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    execution_plan: ExecutionPlan = field(default_factory=ExecutionPlan)

    quality_metrics: QualityMetrics = field(default_factory=QualityMetrics)
    audit: AuditTrail = field(default_factory=AuditTrail)

    # Canonical provenance & diagnostics (mirrors L1/L2)
    data_health: DataHealthScore = field(default_factory=DataHealthScore)
    provenance: Layer3Provenance = field(default_factory=Layer3Provenance)
    diagnostics: Layer3Diagnostics = field(default_factory=Layer3Diagnostics)

    def content_hash(self) -> str:
        """Deterministic hash for reproducibility verification."""
        payload = {
            "schema_version": self.schema_version,
            "run_id": self.run_id_l3,
            "diagnosis_count": len(self.diagnoses),
            "recommendation_count": len(self.recommendations),
            "task_count": len(self.execution_plan.tasks),
            "diagnosis_probs": [round(d.probability, 4) for d in self.diagnoses],
            "diagnosis_ids": sorted(d.problem_id for d in self.diagnoses),
            "rec_ids": sorted(r.action_id for r in self.recommendations),
            "health_overall": round(self.data_health.overall, 4),
            "health_status": self.data_health.status,
            "reliability": round(self.quality_metrics.decision_reliability, 4),
        }
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def to_json(self):
        """Helper for JSON serialization."""
        return self.__dict__
