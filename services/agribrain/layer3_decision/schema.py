from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Import Upstream Contracts
from services.agribrain.layer1_fusion.schema import FieldTensor
from services.agribrain.layer2_veg_int.schema import VegIntOutput

@dataclass
class PlotContext:
    """Static metadata and constraints for the plot."""
    crop_type: str # e.g. "corn", "wheat", "soy"
    variety: Optional[str] = None
    planting_date: str = "" # YYYY-MM-DD
    irrigation_type: str = "rainfed" # "drip", "pivot", "rainfed"
    management_goal: str = "yield_max" # "yield_max", "cost_min", "sustainable"
    constraints: Dict[str, Any] = field(default_factory=dict)
    # e.g. {"water_quota_mm": 500, "budget_limit": 1000}

@dataclass
class DecisionInput:
    """Strict ingestion contract for Layer 3."""
    tensor: FieldTensor
    veg_int: VegIntOutput
    context: PlotContext
    weather_forecast: List[Dict] = field(default_factory=list) # Optional

# --- v4.0 Contract Enums ---
from enum import Enum

class ProblemClass(Enum):
    DIAGNOSIS = "DIAGNOSIS" # Actionable
    RISK = "RISK" # Verify-first
    EVENT = "EVENT" # Observational / Critical
    SYSTEM = "SYSTEM" # Pipeline Health

class RiskIfWrong(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class DegradationMode(Enum):
    NORMAL = "NORMAL"
    NO_SAR = "NO_SAR" # Missing SAR channels entirely (count == 0)
    LOW_SAR_CADENCE = "LOW_SAR_CADENCE" # Count > 0 but <= 5
    WEATHER_ONLY = "WEATHER_ONLY" # Missing Optical
    DATA_GAP = "DATA_GAP" # Critical Missing Drivers

class Driver(Enum):
    NDVI = "NDVI"
    RAIN = "RAIN"
    TEMP = "TEMP"
    SAR_VV = "SAR_VV"
    SAR_VH = "SAR_VH"
    GDD = "GDD"
    NDVI_UNC = "NDVI_UNC"

@dataclass
class EvidenceTerm:
    """
    Calibrated evidence unit.
    Follows: delta_logit = weight * normalized_score
    """
    feature_name: str # e.g. "rain_sum_14d"
    window: str # e.g. "14d", "current"
    value: float # Raw value
    score: float # [-1.0, 1.0]
    weight: float # [0.0, 5.0+]
    contribution: float # The actual logit delta

@dataclass
class Diagnosis:
    """
    Research-grade probabilistic conclusion.
    Separates BELIEF (Probability) from TRUST (Confidence).
    """
    problem_id: str # WATER_STRESS, WATERLOGGING, etc.
    probability: float # 0.0 - 1.0 (Derived from Logits)
    severity: float # 0.0 - 1.0 (Impact magnitude)
    confidence: float # 0.0 - 1.0 (Data quality / Trust)
    
    evidence_trace: List[EvidenceTerm]
    contra_trace: List[EvidenceTerm]
    supports: Dict[str, List[str]] # {signals_used: [], windows: []}
    
    # v4.0 Strict Contract
    problem_class: ProblemClass = ProblemClass.DIAGNOSIS
    drivers_used: List[Driver] = field(default_factory=list)
    drivers_missing: List[Driver] = field(default_factory=list)

    # --- SPATIAL EXTENSIONS (Phase 11) ---
    affected_area_pct: float = 100.0 # Percentage of plot affected
    hotspot_zone_ids: List[str] = field(default_factory=list) # Zones where this is acute

@dataclass
class Recommendation:
    """
    Actionable advice with compliance gates.
    """
    action_id: str
    action_type: str # "VERIFY" | "INTERVENE" | "ALERT"
    priority_score: float
    
    expected_impact: float # 0.0 - 1.0
    urgency: float # 0.0 - 1.0
    confidence: float # 0.0 - 1.0
    
    is_allowed: bool
    blocked_reason: List[str]
    risk_if_wrong: RiskIfWrong # Enum
    
    linked_diagnosis_ids: List[str]
    explain: str
    
    # v4.0 Strict Contract
    preconditions: List[str] = field(default_factory=list)
    
    # Execution Details (kept for compat, though Graph is better)
    timing: Dict[str, str] = field(default_factory=dict)
    resource_est: Dict[str, float] = field(default_factory=dict)

@dataclass
class TaskNode:
    """Node in the Execution Graph."""
    task_id: str
    type: str # VERIFY | INTERVENE | ALERT
    instructions: str
    required_inputs: List[str]
    completion_signal: str # e.g. "USER_CONFIRM", "SENSOR_READING"
    depends_on: List[str] = field(default_factory=list) # IDs of parent tasks
    
    # --- SPATIAL EXTENSIONS (Phase 11) ---
    target_zones: List[str] = field(default_factory=list) # Specific zones to target (e.g. ['Zone C'])
    target_points: List[Dict[str, float]] = field(default_factory=list) # [{lat, lng}] for scouting routes

@dataclass
class ExecutionPlan:
    """DAG of tasks."""
    tasks: List[TaskNode]
    edges: List[Dict[str, str]] # [{from: id, to: id, condition: ?}]
    recommended_start_date: str
    review_date: str

@dataclass
class QualityMetrics:
    """Governance and Reliability Metrics."""
    decision_reliability: float # 0.0 - 1.0
    missing_drivers: List[Driver]
    data_completeness: Dict[str, float] # {optical_obs_frac: 0.8, sar_coverage: 1.0}
    l2_confidence_summary: Dict[str, float] # {phenology_mean: 0.9}
    degradation_mode: DegradationMode # Enum

@dataclass
class AuditTrail:
    """Full reproducibility trace."""
    features_snapshot: Dict[str, Any]
    log_odds_table: List[Dict[str, Any]] # {hypothesis, prior, final}
    policy_checks: List[Dict[str, Any]]

@dataclass
class DecisionOutput:
    """
    The final product of Layer 3 (Research Grade).
    """
    run_id_l3: str
    lineage: Dict[str, str] # {l1: ..., l2: ...}
    timestamp_utc: str
    
    diagnoses: List[Diagnosis]
    recommendations: List[Recommendation]
    execution_plan: ExecutionPlan
    
    quality_metrics: QualityMetrics
    audit: AuditTrail

    def to_json(self):
        # Helper for JSON serialization if needed
        return self.__dict__
