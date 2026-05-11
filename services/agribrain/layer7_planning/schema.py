"""
Layer 7 Schema — Season Planning & Crop Suitability Intelligence (v7.1)

Production-grade data contracts for the Season Planning engine.
Follows L4/L5/L6 architecture standard: strict typing, full provenance,
belief/trust separation, deterministic content_hash().

Architecture:
  L1 FieldTensor (weather + soil)
  L5 BioThreatOutput (optional — biotic pressure)
  ChatMemory (optional — rotation / disease history)
    → CCL (Crop Library)
    → PWE (Planting Window)
    → STE (Seedbed / Workability)
    → WFE (Water Feasibility)
    → BRF (Biotic Risk Forecast)
    → YVE (Yield Distribution)
    → EOE (Economics)
    → PED (Planner & DAG Builder)
    → Layer7Output (with content_hash)

Contract version: 7.1.0
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional

from layer3_decision.schema import ExecutionPlan


# ============================================================================
# Enums (Locked)
# ============================================================================

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


# ============================================================================
# Core Data Structures (Probability vs Confidence Doctrine)
# ============================================================================

@dataclass
class EvidenceLogit:
    driver: SuitabilityDriver
    condition: str
    logit_delta: float
    weight: float
    source_refs: List[str]

@dataclass
class SuitabilityState:
    id: str                          # e.g. "WINDOW_STATE", "WORKABILITY_STATE"
    probability_ok: float            # Derived from evidence logits (0.0 to 1.0)
    confidence: float                # Trust score based on data quality (0.0 to 1.0)
    severity: str                    # "CRITICAL", "MODERATE", "LOW"
    drivers_used: List[str]
    evidence_trace: List[EvidenceLogit]
    notes: List[str]

    def __post_init__(self):
        if self.evidence_trace:
            self.evidence_trace.sort(key=lambda e: (getattr(e.driver, 'value', str(e.driver)), e.condition))

@dataclass
class YieldDistribution:
    mean: float
    p10: float                       # Downside risk
    p50: float                       # Median
    p90: float                       # Upside potential
    contributors: List[str]          # e.g. "Water constraint limited p90"

@dataclass
class EconomicOutcome:
    expected_profit: float
    profit_p10: float
    profit_p50: float
    profit_p90: float
    break_even_yield: float
    sensitivities: Dict[str, str]    # e.g. {"price_-10%": "-$200"}

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
    suitability_percentage: float = 0.0
    # L10 explainability fields (optional, populated by planning engine)
    name: str = ""
    strategy_id: str = ""
    description: str = ""
    expected_impacts: Dict[str, float] = field(default_factory=dict)

@dataclass
class PlanningRecommendation:
    decision_id: PlanningDecisionId
    crop: str
    is_allowed: bool
    blocked_reason: Optional[str]
    risk_if_wrong: str
    preconditions: List[str]


# ============================================================================
# Run Metadata (Production Standard)
# ============================================================================

@dataclass
class RunMetaL7:
    """Layer 7 run metadata — follows L6 RunMeta standard."""
    layer: str = "L7"
    run_id: str = ""
    parent_run_ids: Dict[str, str] = field(default_factory=dict)
    generated_at: str = ""
    degradation_mode: PlanningDegradationMode = PlanningDegradationMode.NORMAL
    engine_version: str = "7.1.0"


# ============================================================================
# Quality Metrics (Production Standard)
# ============================================================================

@dataclass
class QualityMetricsL7:
    """Governance and reliability metrics for Layer 7 output."""
    decision_reliability: float = 0.0
    data_completeness: Dict[str, float] = field(default_factory=dict)
    upstream_confidence_floor: float = 0.0
    missing_drivers: List[str] = field(default_factory=list)
    degradation_mode: PlanningDegradationMode = PlanningDegradationMode.NORMAL
    penalties_applied: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================================
# Audit Snapshot (Production Standard)
# ============================================================================

@dataclass
class AuditSnapshotL7:
    """Full reproducibility trace for Layer 7."""
    crop_profiles_evaluated: int = 0
    dag_task_count: int = 0
    economic_inputs: Dict[str, Any] = field(default_factory=dict)
    engine_versions: Dict[str, str] = field(default_factory=dict)
    upstream_digest: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Master Output Container (Production Standard)
# ============================================================================

@dataclass
class Layer7Output:
    """The canonical output of the Layer 7 Season Planning engine.

    Deterministic: same upstream inputs → same Layer7Output + content_hash().
    """
    run_meta: RunMetaL7

    # Core outputs
    options: List[CropOptionEvaluation] = field(default_factory=list)
    chosen_plan: Optional[PlanningRecommendation] = None
    execution_plan: Optional[ExecutionPlan] = None

    # Zone-aware suitability (populated when spatial data available)
    plot_suitability: Optional[Any] = None  # PlotSuitability from zone_suitability

    # Governance
    quality_metrics: QualityMetricsL7 = field(default_factory=QualityMetricsL7)
    audit: AuditSnapshotL7 = field(default_factory=AuditSnapshotL7)

    def content_hash(self) -> str:
        """Deterministic hash for reproducibility verification."""
        payload = {
            "run_id": self.run_meta.run_id,
            "options_count": len(self.options),
            "option_crops": sorted(o.crop for o in self.options),
            "option_scores": [round(o.overall_rank_score, 4) for o in self.options],
            "suitability_pcts": [round(o.suitability_percentage, 2) for o in self.options],
            "chosen_crop": self.chosen_plan.crop if self.chosen_plan else "",
            "chosen_decision": self.chosen_plan.decision_id.value if self.chosen_plan else "",
            "chosen_allowed": self.chosen_plan.is_allowed if self.chosen_plan else False,
            "dag_tasks": len(self.execution_plan.tasks) if self.execution_plan else 0,
            "reliability": round(self.quality_metrics.decision_reliability, 4),
            "degradation": self.quality_metrics.degradation_mode.value,
        }
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
