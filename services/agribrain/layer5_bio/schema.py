
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

from services.agribrain.layer1_fusion.schema import FieldTensor
from services.agribrain.layer2_veg_int.schema import VegIntOutput
from services.agribrain.layer3_decision.schema import (
    Driver, DegradationMode, RiskIfWrong, TaskNode, ExecutionPlan, PlotContext, DecisionOutput
)
from services.agribrain.layer4_nutrients.schema import NutrientIntelligenceOutput

# --- Enums (Locked) ---

class ThreatClass(str, Enum):
    DISEASE = "DISEASE"
    INSECT = "INSECT"
    WEED = "WEED"
    SYSTEM = "SYSTEM"

class ThreatId(str, Enum):
    # Disease families (don’t overfit to specific species early)
    FUNGAL_LEAF_SPOT = "FUNGAL_LEAF_SPOT"
    FUNGAL_RUST = "FUNGAL_RUST"
    DOWNY_MILDEW = "DOWNY_MILDEW"
    POWDERY_MILDEW = "POWDERY_MILDEW"
    BACTERIAL_BLIGHT = "BACTERIAL_BLIGHT"

    # Insects (functional groups)
    CHEWING_INSECTS = "CHEWING_INSECTS"
    SUCKING_INSECTS = "SUCKING_INSECTS"
    BORERS = "BORERS"

    # Weeds
    WEED_PRESSURE = "WEED_PRESSURE"

    # System
    DATA_GAP = "DATA_GAP"

class Severity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ActionId(str, Enum):
    VERIFY_SCOUT = "VERIFY_SCOUT"
    VERIFY_PHOTOS = "VERIFY_PHOTOS"
    VERIFY_TRAPS = "VERIFY_TRAPS"
    VERIFY_LAB = "VERIFY_LAB"
    INTERVENE_TREAT = "INTERVENE_TREAT"      # treatment category only
    INTERVENE_CULTURAL = "INTERVENE_CULTURAL"
    MONITOR = "MONITOR"

class SpreadPattern(str, Enum):
    UNIFORM = "UNIFORM"
    PATCHY = "PATCHY"
    EDGE_DRIVEN = "EDGE_DRIVEN"
    RANDOM = "RANDOM"
    UNKNOWN = "UNKNOWN"

class Confounder(str, Enum):
    WATER_STRESS = "WATER_STRESS"
    WATERLOGGING = "WATERLOGGING"
    N_DEFICIENCY = "N_DEFICIENCY"
    SALINITY_RISK = "SALINITY_RISK"
    OTHER = "OTHER"

# --- Input Hand-off ---

@dataclass(frozen=True)
class Layer5Input:
    """
    Locked Handoff from L1-L4. 
    L5 MUST NOT re-derive L1/L2/L3/L4 data, only consume it.
    """
    tensor: FieldTensor
    veg_int: VegIntOutput
    decision_l3: DecisionOutput
    nutrient_l4: NutrientIntelligenceOutput
    context: PlotContext

# --- Evidence / Logits ---

@dataclass(frozen=True)
class EvidenceLogit:
    driver: Driver
    condition: str
    logit_delta: float
    weight: float
    source_refs: Dict[str, Any] = field(default_factory=dict)  # exact feature values used

@dataclass
class BioThreatState:
    threat_id: ThreatId
    threat_class: ThreatClass

    probability: float        # belief from logits only
    confidence: float         # trust from data quality only
    severity: Severity

    drivers_used: List[Driver]
    evidence_trace: List[EvidenceLogit]

    spread_pattern: SpreadPattern
    confounders: List[Confounder]
    notes: str = ""

@dataclass(frozen=True)
class BioRecommendation:
    action_id: ActionId
    threat_id: ThreatId

    is_allowed: bool
    blocked_reason: List[str]
    risk_if_wrong: RiskIfWrong

    timing_window: Dict[str, str]  # {start, end}
    method: str                    # e.g., "scout", "photo", "trap", "treat_category"

    depends_on: List[str] = field(default_factory=list)

@dataclass
class RunMeta:
    layer: str = "L5"
    run_id: str = ""
    parent_run_ids: Dict[str, str] = field(default_factory=dict)
    generated_at: str = ""
    degradation_mode: DegradationMode = DegradationMode.NORMAL

@dataclass
class QualityMetricsL5:
    decision_reliability: float
    missing_drivers: List[Driver]
    data_completeness: Dict[str, float]
    penalties_applied: List[Dict[str, Any]]

@dataclass
class AuditSnapshot:
    features_snapshot: Dict[str, Any]
    policy_snapshot: Dict[str, Any]
    model_versions: Dict[str, str]

@dataclass
class BioThreatIntelligenceOutput:
    run_meta: RunMeta

    threat_states: Dict[str, BioThreatState]
    recommendations: List[BioRecommendation]
    execution_plan: Optional[ExecutionPlan]

    quality_metrics: QualityMetricsL5
    audit: AuditSnapshot

# Export commonly used items
PestIntelligenceOutput = BioThreatIntelligenceOutput 
