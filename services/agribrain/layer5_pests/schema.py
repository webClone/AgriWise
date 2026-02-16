
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
import datetime

# Imports from Previous Layers (Strict Handoff)
from services.agribrain.layer1_fusion.schema import FieldTensor
from services.agribrain.layer2_veg_int.schema import VegIntOutput
from services.agribrain.layer3_decision.schema import DecisionOutput, PlotContext, Driver, ExecutionPlan, DegradationMode
from services.agribrain.layer4_nutrients.schema import NutrientIntelligenceOutput, Confounder, ApplicationMethod, Severity, EvidenceLogit, RunMeta, AuditSnapshot

# --- ENUMS ---

class BioThreat(str, Enum):
    # Fungal
    RUST = "RUST"
    BLIGHT_EARLY = "BLIGHT_EARLY"
    BLIGHT_LATE = "BLIGHT_LATE"
    MILDEW_POWDERY = "MILDEW_POWDERY"
    # Bacterial
    WILT_BACTERIAL = "WILT_BACTERIAL"
    # Insect
    INSECT_CHEWING = "INSECT_CHEWING" # Caterpillars, Beetles
    INSECT_SUCKING = "INSECT_SUCKING" # Aphids, Mites
    # Viral
    VIRUS_MOSAIC = "VIRUS_MOSAIC"
    # Generic
    UNKNOWN = "UNKNOWN"

class SpreadPattern(str, Enum):
    PATCHY = "PATCHY"           # Clusters, typical of soil-borne or early insects
    EDGE_DRIVEN = "EDGE_DRIVEN" # Coming from neighbors
    UNIFORM = "UNIFORM"         # Field-wide (often Abiotic/Nutrient, contra-indicator for disease)
    RANDOM = "RANDOM"           # Spores/Wind

class ActionType(str, Enum):
    SCOUT_VISUAL = "SCOUT_VISUAL"
    SCOUT_TRAP = "SCOUT_TRAP"
    SCOUT_TISSUE = "SCOUT_TISSUE"
    TREAT_FUNGICIDE = "TREAT_FUNGICIDE"
    TREAT_INSECTICIDE = "TREAT_INSECTICIDE"
    TREAT_BIOCONTROL = "TREAT_BIOCONTROL"
    CULTURAL_PRUNE = "CULTURAL_PRUNE"
    MONITOR = "MONITOR"

# --- INPUT CONTRACT ---

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

# --- OUTPUT STATES ---

@dataclass
class BioThreatState:
    threat: BioThreat
    
    probability: float # [0.0 - 1.0] Belief
    confidence: float  # [0.0 - 1.0] Trust
    severity: Severity # Impact
    
    spread_pattern: SpreadPattern
    
    drivers_used: List[Driver]
    evidence_trace: List[EvidenceLogit]
    
    confounders: List[Confounder] # e.g. WATER_STRESS (Validation Gate)

@dataclass
class BioRecommendation:
    action_type: ActionType
    target: BioThreat
    urgency: Severity
    method: ApplicationMethod
    treatment_window: Dict[str, str] # {start, end} - Frozen dataclass preferred but keeping simple for now? 
    # Actually, L4 used TimingWindow dataclass. We should reuse it or define strict one.
    # Let's reuse strict TimingWindow if possible or define locally strict one.
    # Keeping dict for now to match prompt "recommendations", but let's be strict.
    
    is_allowed: bool
    blocked_reason: List[str]

@dataclass
class PestIntelligenceOutput:
    """
    Layer 5 Output Contract.
    """
    run_meta: RunMeta
    
    threat_states: Dict[BioThreat, BioThreatState]
    recommendations: List[BioRecommendation]
    execution_plan: ExecutionPlan
    
    quality_metrics: Dict[str, Any] # Placeholder for strict quality
    audit: AuditSnapshot
