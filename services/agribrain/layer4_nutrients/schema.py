
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union
from enum import Enum
import datetime

# Strict Import of Enums from Lower Layers
from services.agribrain.layer3_decision.schema import Driver, DegradationMode, RiskIfWrong, TaskNode, ExecutionPlan

# --- Enums (v4.0 Locked & Hardened) ---

class Severity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"

class ActionId(str, Enum):
    APPLY_N = "APPLY_N"
    APPLY_P = "APPLY_P"
    APPLY_K = "APPLY_K"
    APPLY_LIME = "APPLY_LIME"
    VERIFY_ONLY = "VERIFY_ONLY"
    MONITOR = "MONITOR"

class ApplicationMethod(str, Enum):
    BROADCAST = "BROADCAST"
    BANDED = "BANDED"
    FERTIGATION = "FERTIGATION"
    FOLIAR = "FOLIAR"
    NONE = "NONE"

class Nutrient(str, Enum):
    N = "N"
    P = "P"
    K = "K"
    
class Confounder(str, Enum):
    WATER_STRESS = "WATER_STRESS"
    DISEASE_RISK = "DISEASE_RISK"
    DATA_GAP = "DATA_GAP"
    SALINITY = "SALINITY"
    SPATIAL_HETEROGENEITY = "SPATIAL_HETEROGENEITY"

# --- Data Structures (v4.0 Locked & Hardened) ---

@dataclass
class EvidenceLogit:
    """Rationale unit for Bayesian update."""
    driver: Driver
    condition: str
    logit_delta: float
    weight: float
    source_refs: Dict[str, Any] = field(default_factory=dict) # Traceability

@dataclass
class NutrientState:
    """
    Strict state definition.
    INVARIANTS:
    - Probability (Belief) independent of Confidence (Trust)
    - Severity derived from Probability x Impact
    """
    nutrient: Nutrient 
    state_index: float # [-1.0, +1.0]
    
    probability_deficient: float # [0.0 - 1.0]
    confidence: float # [0.0 - 1.0]
    severity: Severity
    
    drivers_used: List[Driver]
    evidence_trace: List[EvidenceLogit]
    
    confounders: List[Confounder]
    notes: str = ""

@dataclass(frozen=True)
class PrescriptionAudit:
    """Frozen inputs used for optimization."""
    crop_price: float
    product_cost: float
    constraints_active: List[str]
    response_model: str # e.g. "Mitscherlich", "Quadratic"
    response_params: Dict[str, float] # {ymax: 12.0, c: 0.015}
    objective: str # "ProfitMax"

@dataclass(frozen=True)
class TimingWindow:
    start_date: str # ISO
    end_date: str # ISO

@dataclass(frozen=True)
class SplitApplication:
    rate_kg_ha: float
    date: Optional[str] = None
    offset_days: Optional[int] = None

@dataclass(frozen=True)
class EnvironmentalRisk:
    leaching: float # [0.0 - 1.0]
    runoff: float   # [0.0 - 1.0]
    volatilization: float # [0.0 - 1.0]

@dataclass
class Prescription:
    """
    Actionable recommendation with strict constraints.
    """
    action_id: ActionId
    rate_kg_ha: float # Renamed from tm_rate_kg_ha
    
    timing_window: TimingWindow
    splits: List[SplitApplication]
    method: ApplicationMethod
    
    risk_if_wrong: RiskIfWrong
    preconditions: List[str] 
    
    is_allowed: bool
    blocked_reason: List[str]
    
    environmental_risk: EnvironmentalRisk
    audit: PrescriptionAudit

@dataclass(frozen=True)
class ParentRunIds:
    l1: str
    l2: str
    l3: str

@dataclass
class RunMeta:
    """Traceability metadata."""
    layer: str = "L4"
    run_id: str = ""
    parent_run_ids: Optional[ParentRunIds] = None
    generated_at: str = "" # ISO
    degradation_mode: DegradationMode = DegradationMode.NORMAL

@dataclass
class QualityMetricsL4:
    """Governance metrics."""
    decision_reliability: float
    missing_drivers: List[Driver]
    data_completeness: Dict[str, float]
    penalties_applied: List[Dict[str, Any]] 

@dataclass
class AuditSnapshot:
    """Full reproducibility freeze."""
    features_snapshot: Dict[str, Any]
    policy_snapshot: Dict[str, Any] 
    model_versions: Dict[str, str]

@dataclass
class NutrientIntelligenceOutput:
    """
    Layer 4 v4.0 Final Output Contract (Hardened).
    """
    run_meta: RunMeta
    
    nutrient_states: Dict[Nutrient, NutrientState] # Keyed by Enum
    prescriptions: List[Prescription]
    verification_plan: ExecutionPlan # Required
    
    quality_metrics: QualityMetricsL4
    audit: AuditSnapshot
