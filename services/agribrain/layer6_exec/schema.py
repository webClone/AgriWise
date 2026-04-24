
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime

# Upstream Contracts
from services.agribrain.layer1_fusion.schema import FieldTensor
from services.agribrain.layer2_veg_int.schema import VegIntOutput
from services.agribrain.layer3_decision.schema import DecisionOutput, PlotContext, TaskNode, Driver, DegradationMode
from services.agribrain.layer4_nutrients.schema import NutrientIntelligenceOutput
from services.agribrain.layer5_bio.schema import BioThreatIntelligenceOutput

# --- Enums (Locked) ---

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

class CausalMethod(str, Enum):
    PRE_POST = "PRE_POST"
    DIFF_IN_DIFF = "DIFF_IN_DIFF"
    SYNTHETIC_BASELINE = "SYNTHETIC_BASELINE"
    NONE = "NONE"

class ApprovalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

# --- Data Structures ---

@dataclass
class OperationalContext:
    """Operational constraints and resources."""
    equipment_ids: List[str]
    workforce_available: bool
    water_quota_remaining: float
    budget_remaining: float
    permissions: List[str]

@dataclass(frozen=True)
class NormalizedEvidence:
    """
    Immutable, hashed evidence record.
    """
    evidence_id: str # EV-{sha256}
    type: EvidenceType
    timestamp: str # ISO
    plot_id: str
    
    payload: Dict[str, Any]
    
    # --- SPATIAL EXTENSIONS (Phase 11) ---
    zone_id: Optional[str] = None # Which management zone this evidence belongs to
    location: Optional[Dict[str, float]] = None # {lat, lng} of the exact evidence point
    
    source_refs: Dict[str, str] = field(default_factory=dict) # {task_id: ..., diagnosis_id: ...}
    attachment_hashes: List[str] = field(default_factory=list)

@dataclass
class CalibrationProposal:
    """
    Proposed update to system logic (Learning Loop).
    """
    target_layer: str # L5, L4, etc.
    parameter_key: str # e.g. "wdp_fungal_weight"
    current_value: float
    proposed_value: float
    reason: str
    evidence_support: List[str] # List of evidence_ids
    status: ApprovalStatus = ApprovalStatus.PROPOSED

@dataclass
class OutcomeMetric:
    """
    Evaluated result of an action or event.
    """
    metric_id: OutcomeMetricId
    delta_value: float
    confidence: float # 0.0 - 1.0 (Method reliability)
    method: CausalMethod
    baseline_window: Dict[str, str] # {start, end}
    eval_window: Dict[str, str] # {start, end}
    confounders_present: List[str]

@dataclass
class ExecutionState:
    """
    Persistable state of the DAG.
    """
    tasks: Dict[str, TaskStatus] # task_id -> status
    last_updated: str
    logs: List[Dict[str, Any]]

@dataclass(frozen=True)
class Layer6Input:
    """
    Strict Input from L1-L5 + Ops + Evidence + State.
    """
    tensor: FieldTensor
    veg_int: VegIntOutput
    decision_l3: DecisionOutput
    nutrient_l4: Optional[NutrientIntelligenceOutput]
    bio_l5: Optional[BioThreatIntelligenceOutput]
    
    op_context: OperationalContext
    evidence_batch: List[Dict[str, Any]] # Raw Evidence
    current_state: ExecutionState 

@dataclass
class RunMeta:
    layer: str = "L6"
    run_id: str = ""
    parent_run_ids: Dict[str, str] = field(default_factory=dict)
    generated_at: str = ""
    degradation_mode: DegradationMode = DegradationMode.NORMAL

@dataclass
class QualityMetricsL6:
    decision_reliability: float
    missing_drivers: List[Driver]
    data_completeness: Dict[str, float]
    task_completion_rate: float

@dataclass
class AuditSnapshot:
    features_snapshot: Dict[str, Any]
    policy_snapshot: Dict[str, Any]
    model_versions: Dict[str, str]

@dataclass
class Layer6Output:
    """
    Final Output of Research-Grade Layer 6.
    """
    run_meta: RunMeta
    
    updated_state: ExecutionState
    evidence_registry: List[NormalizedEvidence]
    outcome_report: List[OutcomeMetric]
    calibration_proposals: List[CalibrationProposal]
    
    quality_metrics: QualityMetricsL6
    audit: AuditSnapshot
