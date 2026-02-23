from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional

# --- Enums (Strict Taxonomy) ---

class PlanningDecisionId(str, Enum):
    PLANT_NOW = "PLANT_NOW"
    DELAY_PLANTING = "DELAY_PLANTING"
    SWITCH_CROP = "SWITCH_CROP"
    PLANT_COVER_CROP = "PLANT_COVER_CROP"
    WAIT_FOR_DATA = "WAIT_FOR_DATA"

class SuitabilityDriver(str, Enum):
    TEMP = "TEMP"
    FROST_RISK = "FROST_RISK"
    RAIN_7D = "RAIN_7D"
    SOIL_TEXTURE = "SOIL_TEXTURE"
    WATER_QUOTA = "WATER_QUOTA"
    DISEASE_PRESSURE = "DISEASE_PRESSURE"
    SEASON_LENGTH = "SEASON_LENGTH"
    MARKET_PRICE = "MARKET_PRICE"

class PlanningDegradationMode(str, Enum):
    NORMAL = "NORMAL"
    NO_FORECAST = "NO_FORECAST"
    NO_SOIL = "NO_SOIL"
    NO_HISTORY = "NO_HISTORY"
    WEATHER_ONLY = "WEATHER_ONLY"

class OptionRankReason(str, Enum):
    MAX_PROFIT = "MAX_PROFIT"
    MIN_RISK = "MIN_RISK"
    BEST_WINDOW = "BEST_WINDOW"
    WATER_SAFE = "WATER_SAFE"
    LOW_DISEASE_RISK = "LOW_DISEASE_RISK"


# --- Core Data Structures (Probability vs Confidence Doctrine) ---

@dataclass
class EvidenceLogit:
    driver: SuitabilityDriver
    condition: str
    logit_delta: float
    weight: float
    source_refs: List[str]

@dataclass
class SuitabilityState:
    id: str # e.g. "WINDOW_STATE", "WORKABILITY_STATE"
    probability_ok: float # Derived from evidence logits (0.0 to 1.0)
    confidence: float # Trust score based on data quality (0.0 to 1.0)
    severity: str # "CRITICAL", "MODERATE", "LOW"
    drivers_used: List[str]
    evidence_trace: List[EvidenceLogit]
    notes: List[str]

    def __post_init__(self):
        if self.evidence_trace:
            self.evidence_trace.sort(key=lambda e: (getattr(e.driver, 'value', str(e.driver)), e.condition))

@dataclass
class YieldDistribution:
    mean: float
    p10: float # Downside risk 
    p50: float # Median
    p90: float # Upside potential
    contributors: List[str] # e.g. "Water constraint limited p90", "Biotic risk lowered p10"

@dataclass
class EconomicOutcome:
    expected_profit: float
    profit_p10: float
    profit_p50: float
    profit_p90: float
    break_even_yield: float
    sensitivities: Dict[str, str] # e.g. {"price_-10%": "-$200", "yield_drop": "-$400"}

@dataclass
class CropOptionEvaluation:
    crop: str
    window: SuitabilityState
    soil: SuitabilityState
    water: SuitabilityState
    biotic: SuitabilityState
    yield_dist: YieldDistribution
    econ: EconomicOutcome
    overall_rank_score: float

@dataclass
class PlanningRecommendation:
    decision_id: PlanningDecisionId
    crop: str
    is_allowed: bool
    blocked_reason: Optional[str]
    risk_if_wrong: str
    preconditions: List[str]

# --- Master Output Container ---

@dataclass
class Layer7Output:
    run_meta: Dict[str, str] # Run ID, execution time
    options: List[CropOptionEvaluation]
    chosen_plan: PlanningRecommendation
    quality_metrics: Dict[str, str] # Degradation modes, global confidence
    audit_snapshot: Dict[str, Any] # Retain intermediate matrices
