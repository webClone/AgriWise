"""
Layer 4 Nutrient Intelligence — Research-Grade Schema v2.

Complete data contracts for the 4R Nutrient Stewardship engine:
  - Multi-nutrient state estimation (N/P/K + micronutrient diagnostics)
  - SAR-based tillage/SOC dynamics
  - 4 response curve models
  - EU Nitrate Directive compliance
  - Phenology-aware split-application prescriptions
  - Full provenance, uncertainty, deterministic content_hash

Contract version: 2.0.0
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from layer1_fusion.schemas import DataHealthScore
from layer3_decision.schema import Driver, DegradationMode, RiskIfWrong, TaskNode, ExecutionPlan


# ============================================================================
# Enums
# ============================================================================

class Nutrient(str, Enum):
    N = "N"
    P = "P"
    K = "K"
    S = "S"
    Ca = "Ca"
    Mg = "Mg"
    # Micronutrients (diagnostic-only in v2)
    Zn = "Zn"
    B = "B"
    Fe = "Fe"
    Mn = "Mn"


MACRO_NUTRIENTS = (Nutrient.N, Nutrient.P, Nutrient.K)
SECONDARY_NUTRIENTS = (Nutrient.S, Nutrient.Ca, Nutrient.Mg)
MICRO_NUTRIENTS = (Nutrient.Zn, Nutrient.B, Nutrient.Fe, Nutrient.Mn)


class Severity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionId(str, Enum):
    APPLY_N = "APPLY_N"
    APPLY_P = "APPLY_P"
    APPLY_K = "APPLY_K"
    APPLY_LIME = "APPLY_LIME"
    APPLY_GYPSUM = "APPLY_GYPSUM"
    VERIFY_SOIL_TEST = "VERIFY_SOIL_TEST"
    VERIFY_TISSUE_TEST = "VERIFY_TISSUE_TEST"
    MONITOR = "MONITOR"
    NO_ACTION = "NO_ACTION"


class ApplicationMethod(str, Enum):
    BROADCAST = "BROADCAST"
    BANDED = "BANDED"
    FERTIGATION = "FERTIGATION"
    FOLIAR = "FOLIAR"
    SIDE_DRESS = "SIDE_DRESS"
    TOP_DRESS = "TOP_DRESS"
    DEEP_PLACEMENT = "DEEP_PLACEMENT"
    NONE = "NONE"


class ResponseModel(str, Enum):
    MITSCHERLICH = "MITSCHERLICH"           # Y = Ymax * (1 - exp(-c*(x+b)))
    QUADRATIC_PLATEAU = "QUADRATIC_PLATEAU" # Y = a + bx + cx^2 until plateau
    LINEAR_PLATEAU = "LINEAR_PLATEAU"       # Y = a + bx until plateau
    SQUARE_ROOT = "SQUARE_ROOT"             # Y = a + bx^0.5 + cx


class FertilizerProduct(str, Enum):
    UREA = "UREA"               # 46-0-0
    CAN = "CAN"                 # 27-0-0 (Calcium Ammonium Nitrate)
    UAN_28 = "UAN_28"           # 28-0-0 (liquid)
    UAN_32 = "UAN_32"           # 32-0-0 (liquid)
    DAP = "DAP"                 # 18-46-0
    MAP = "MAP"                 # 11-52-0
    TSP = "TSP"                 # 0-46-0
    MOP = "MOP"                 # 0-0-60 (Muriate of Potash)
    SOP = "SOP"                 # 0-0-50 (Sulphate of Potash)
    NPK_15_15_15 = "NPK_15_15_15"
    AMMONIUM_SULFATE = "AS"     # 21-0-0-24S
    LIME = "LIME"               # CaCO3


# Fertilizer nutrient content (fraction)
PRODUCT_ANALYSIS = {
    FertilizerProduct.UREA:           {"N": 0.46},
    FertilizerProduct.CAN:            {"N": 0.27, "Ca": 0.08},
    FertilizerProduct.UAN_28:         {"N": 0.28},
    FertilizerProduct.UAN_32:         {"N": 0.32},
    FertilizerProduct.DAP:            {"N": 0.18, "P": 0.46},
    FertilizerProduct.MAP:            {"N": 0.11, "P": 0.52},
    FertilizerProduct.TSP:            {"P": 0.46},
    FertilizerProduct.MOP:            {"K": 0.60},
    FertilizerProduct.SOP:            {"K": 0.50, "S": 0.18},
    FertilizerProduct.NPK_15_15_15:   {"N": 0.15, "P": 0.15, "K": 0.15},
    FertilizerProduct.AMMONIUM_SULFATE: {"N": 0.21, "S": 0.24},
    FertilizerProduct.LIME:           {"Ca": 0.40},
}


class RegulationFramework(str, Enum):
    EU_NITRATE_DIRECTIVE = "EU_NITRATE_DIRECTIVE"
    USDA_NRCS = "USDA_NRCS"
    MOROCCO_ONSSA = "MOROCCO_ONSSA"
    NONE = "NONE"


class Confounder(str, Enum):
    WATER_STRESS = "WATER_STRESS"
    DISEASE_RISK = "DISEASE_RISK"
    DATA_GAP = "DATA_GAP"
    SALINITY = "SALINITY"
    SPATIAL_HETEROGENEITY = "SPATIAL_HETEROGENEITY"
    TILLAGE_DISTURBANCE = "TILLAGE_DISTURBANCE"
    PH_LOCKOUT = "PH_LOCKOUT"
    WEED_COMPETITION = "WEED_COMPETITION"          # L3 drone: weeds competing for nutrients
    MECHANICAL_DAMAGE = "MECHANICAL_DAMAGE"        # L3 drone: structural crop damage


class TillageClass(str, Enum):
    """SAR-derived tillage intensity classification."""
    CONVENTIONAL = "CONVENTIONAL"   # Full inversion tillage (>15 dB change)
    REDUCED = "REDUCED"             # Minimum tillage (8-15 dB change)
    NO_TILL = "NO_TILL"             # Conservation/no-till (<8 dB change)
    UNKNOWN = "UNKNOWN"


# ============================================================================
# Evidence & Inference
# ============================================================================

@dataclass
class EvidenceLogit:
    """Calibrated evidence unit for Bayesian log-odds update."""
    driver: Driver
    nutrient: Nutrient
    condition: str
    logit_delta: float
    weight: float
    source_refs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NutrientState:
    """Probabilistic nutrient state with full evidence trace.

    INVARIANTS:
      - Probability (Belief) is independent of Confidence (Trust)
      - Severity derived from Probability x Impact
      - All values bounded [0, 1]
    """
    nutrient: Nutrient
    state_index: float              # [-1.0, +1.0] : -1 = severe deficiency

    probability_deficient: float    # [0.0, 1.0]
    confidence: float               # [0.0, 1.0]
    severity: Severity

    drivers_used: List[Driver]
    evidence_trace: List[EvidenceLogit]

    confounders: List[Confounder]
    notes: str = ""

    # Nutrient balance (kg/ha)
    estimated_available_kg_ha: Optional[float] = None
    estimated_demand_kg_ha: Optional[float] = None
    balance_kg_ha: Optional[float] = None  # available - demand


# ============================================================================
# SAR Tillage & SOC Dynamics
# ============================================================================

@dataclass
class TillageDetection:
    """SAR-derived tillage event detection.

    Science: Sentinel-1 VV/VH backscatter changes with soil surface roughness.
    Tilled fields show:
      - VV increase of 2-6 dB (rough surface → higher backscatter)
      - VH increase of 1-4 dB
      - Temporal decorrelation of InSAR coherence
    After rain/settling: backscatter returns to pre-tillage baseline.

    References:
      - Satalino et al. (2014), Remote Sensing of Environment
      - Gao et al. (2017), ISPRS J. Photogrammetry & Remote Sensing
    """
    detected: bool = False
    tillage_class: TillageClass = TillageClass.UNKNOWN
    confidence: float = 0.0

    # SAR change metrics
    vv_change_db: float = 0.0      # Pre-till to post-till VV change
    vh_change_db: float = 0.0      # Pre-till to post-till VH change
    coherence_loss: float = 0.0    # InSAR temporal coherence drop [0-1]

    detection_date: Optional[str] = None
    days_since_detection: int = -1

    # Impact on nutrient cycling
    mineralization_multiplier: float = 1.0
    # Conventional: 1.3x (exposes organic N to oxidation)
    # Reduced: 1.1x
    # No-till: 0.9x (preserves SOC, slower mineralization)


@dataclass
class SOCDynamics:
    """Soil Organic Carbon tracking via SAR + user inputs.

    SOC drives N mineralization potential:
      - High SOC (>3%) → 30-60 kg N/ha/yr from mineralization
      - Low SOC (<1%) → 10-20 kg N/ha/yr
      - Tillage accelerates SOC decomposition (losing carbon to atmosphere)

    The SWB engine adjusts N supply based on:
      SOC_supply = SOC_pct * mineralization_rate * tillage_multiplier
    """
    soc_pct: Optional[float] = None         # From user soil analysis or SoilGrids
    soc_source: str = "unknown"              # "user_lab", "soilgrids", "estimated"

    mineralization_rate_kg_ha_yr: float = 0.0
    tillage_adjusted_mineralization: float = 0.0

    carbon_sequestration_potential: str = ""  # "high", "moderate", "low"
    tillage_history: TillageDetection = field(default_factory=TillageDetection)


# ============================================================================
# Soil Water Balance Output
# ============================================================================

@dataclass
class SoilWaterBalanceOutput:
    """Enhanced SWB output with Saxton-Rawls derived parameters."""
    # Derived soil hydraulic properties
    theta_fc: float = 0.30          # Field capacity (vol/vol)
    theta_wp: float = 0.15          # Wilting point (vol/vol)
    theta_sat: float = 0.45         # Saturation
    taw_mm: float = 150.0           # Total available water (mm)
    raw_mm: float = 75.0            # Readily available water (mm)

    # Daily state
    water_stress_index: float = 0.0  # 0=no stress, 1=full stress
    leaching_risk_index: float = 0.0
    drainage_accum_mm: float = 0.0
    soil_moisture_mm: float = 0.0
    is_water_limiting: bool = False

    # Nutrient transport
    deep_percolation_mm: float = 0.0  # Below root zone drainage
    n_leaching_kg_ha: float = 0.0     # Estimated N lost to leaching

    # Irrigation integration
    irrigation_applied_mm: float = 0.0
    effective_precipitation_mm: float = 0.0


# ============================================================================
# Crop Demand
# ============================================================================

@dataclass
class CropDemandOutput:
    """Multi-nutrient crop demand with phenology timing."""
    crop_type: str = ""
    yield_target_t_ha: float = 0.0

    # Total season demand (kg/ha)
    total_demand: Dict[str, float] = field(default_factory=dict)  # {N: 200, P: 40, K: 160}

    # Cumulative uptake curves (day → kg/ha)
    cumulative_uptake: Dict[str, List[float]] = field(default_factory=dict)

    # Critical windows
    critical_windows: List[Dict[str, Any]] = field(default_factory=list)
    # [{nutrient: "N", stage: "V6-VT", day_start: 35, day_end: 65, demand_pct: 0.50}]

    # Peak daily demand (kg/ha/day)
    peak_daily_demand: Dict[str, float] = field(default_factory=dict)


# ============================================================================
# Nutrient Budget
# ============================================================================

@dataclass
class NutrientBudget:
    """Explicit nutrient accounting: supply vs demand."""
    nutrient: Nutrient = Nutrient.N

    # Supply side (kg/ha)
    soil_test_available: float = 0.0    # From user lab analysis
    residual_credit: float = 0.0        # Previous crop residue
    mineralization: float = 0.0         # SOC decomposition → available N
    atmospheric_deposition: float = 0.0  # ~5-15 kg N/ha/yr
    biological_fixation: float = 0.0    # Legume N fixation
    irrigation_n: float = 0.0           # N in irrigation water

    # Demand side (kg/ha)
    crop_removal: float = 0.0          # Crop uptake at target yield
    immobilization: float = 0.0        # Microbial tie-up of N
    leaching_loss: float = 0.0         # From SWB deep percolation
    volatilization_loss: float = 0.0   # NH3 loss from surface-applied urea
    denitrification_loss: float = 0.0  # N2O in waterlogged soils

    @property
    def total_supply(self) -> float:
        return (self.soil_test_available + self.residual_credit +
                self.mineralization + self.atmospheric_deposition +
                self.biological_fixation + self.irrigation_n)

    @property
    def total_demand(self) -> float:
        return self.crop_removal

    @property
    def total_losses(self) -> float:
        return (self.immobilization + self.leaching_loss +
                self.volatilization_loss + self.denitrification_loss)

    @property
    def balance(self) -> float:
        """Positive = surplus, negative = deficit requiring fertilizer."""
        return self.total_supply - self.total_demand - self.total_losses

    @property
    def fertilizer_need_kg_ha(self) -> float:
        """Required fertilizer input to close the gap."""
        return max(0.0, -self.balance)


# ============================================================================
# 4R Prescription
# ============================================================================

@dataclass(frozen=True)
class TimingWindow:
    start_date: str = ""  # ISO YYYY-MM-DD
    end_date: str = ""
    phenology_stage: str = ""
    gdd_range: str = ""   # e.g. "800-1200"


@dataclass
class SplitApplication:
    """One application event in a multi-split plan."""
    split_id: int = 0
    rate_kg_ha: float = 0.0
    product: FertilizerProduct = FertilizerProduct.UREA
    method: ApplicationMethod = ApplicationMethod.BROADCAST
    timing: TimingWindow = field(default_factory=TimingWindow)
    fraction_of_total: float = 1.0  # e.g. 0.30 for 30% at planting


@dataclass(frozen=True)
class EnvironmentalRisk:
    """Environmental risk model scores [0-1]."""
    leaching: float = 0.0        # f(texture, drainage, rainfall)
    runoff: float = 0.0          # f(slope, cover, rainfall)
    volatilization: float = 0.0  # f(pH, temp, method, urea_fraction)
    denitrification: float = 0.0  # f(waterlogging, temperature)
    overall: float = 0.0         # max(leaching, runoff, volatilization, denitrification)


@dataclass
class RegulatoryCompliance:
    """Regulatory compliance check results."""
    framework: RegulationFramework = RegulationFramework.NONE
    is_compliant: bool = True
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # EU Nitrate Directive specifics
    nvz_limit_kg_ha: float = 170.0       # Max organic N
    total_n_ceiling_kg_ha: float = 250.0  # Total N (organic + mineral)
    proposed_n_total: float = 0.0
    closed_season_active: bool = False
    buffer_distance_m: float = 0.0


@dataclass(frozen=True)
class PrescriptionAudit:
    """Frozen optimization inputs for reproducibility."""
    crop_price_per_ton: float = 0.0
    product_cost_per_kg: float = 0.0
    constraints_active: List[str] = field(default_factory=list)
    response_model: str = ""
    response_params: Dict[str, float] = field(default_factory=dict)
    objective: str = "ProfitMax"
    nutrient_budget_balance: float = 0.0


@dataclass
class Prescription:
    """4R-compliant nutrient prescription."""
    action_id: ActionId = ActionId.NO_ACTION
    nutrient: Nutrient = Nutrient.N

    # Right Rate
    rate_kg_ha: float = 0.0              # Total nutrient rate
    product: FertilizerProduct = FertilizerProduct.UREA
    product_rate_kg_ha: float = 0.0      # Product application rate

    # Right Time
    timing_window: TimingWindow = field(default_factory=TimingWindow)
    splits: List[SplitApplication] = field(default_factory=list)

    # Right Place
    method: ApplicationMethod = ApplicationMethod.BROADCAST
    zone_rates: Dict[str, float] = field(default_factory=dict)  # VRA: zone_id → rate

    # Right Source (product selection rationale)
    source_rationale: str = ""

    # Risk & Compliance
    risk_if_wrong: RiskIfWrong = RiskIfWrong.LOW
    preconditions: List[str] = field(default_factory=list)
    is_allowed: bool = True
    blocked_reason: List[str] = field(default_factory=list)

    environmental_risk: EnvironmentalRisk = field(default_factory=EnvironmentalRisk)
    regulatory: RegulatoryCompliance = field(default_factory=RegulatoryCompliance)
    audit: PrescriptionAudit = field(default_factory=PrescriptionAudit)


# ============================================================================
# Quality & Provenance
# ============================================================================

@dataclass(frozen=True)
class ParentRunIds:
    l1: str = ""
    l2: str = ""
    l3: str = ""


@dataclass
class RunMeta:
    layer: str = "L4"
    run_id: str = ""
    parent_run_ids: Optional[ParentRunIds] = None
    generated_at: str = ""
    degradation_mode: DegradationMode = DegradationMode.NORMAL
    engine_version: str = "layer4_v2.0.0"
    contract_version: str = "2.0.0"


@dataclass
class QualityMetricsL4:
    decision_reliability: float = 0.0
    missing_drivers: List[Driver] = field(default_factory=list)
    data_completeness: Dict[str, float] = field(default_factory=dict)
    penalties_applied: List[Dict[str, Any]] = field(default_factory=list)
    user_soil_analysis_available: bool = False
    sar_tillage_available: bool = False


@dataclass
class AuditSnapshot:
    features_snapshot: Dict[str, Any] = field(default_factory=dict)
    policy_snapshot: Dict[str, Any] = field(default_factory=dict)
    model_versions: Dict[str, str] = field(default_factory=dict)
    nutrient_budgets: Dict[str, Any] = field(default_factory=dict)
    tillage_detection: Optional[TillageDetection] = None
    soc_dynamics: Optional[SOCDynamics] = None


# ============================================================================
# Layer 4 Output
# ============================================================================

@dataclass
class NutrientIntelligenceOutput:
    """Layer 4 v2.0 Final Output Contract.

    Deterministic: same inputs -> same output + content_hash().
    """
    run_meta: RunMeta = field(default_factory=RunMeta)

    nutrient_states: Dict[Nutrient, NutrientState] = field(default_factory=dict)
    nutrient_budgets: Dict[Nutrient, NutrientBudget] = field(default_factory=dict)
    prescriptions: List[Prescription] = field(default_factory=list)
    verification_plan: ExecutionPlan = field(default_factory=ExecutionPlan)

    # Soil & Water
    swb_output: SoilWaterBalanceOutput = field(default_factory=SoilWaterBalanceOutput)
    crop_demand: CropDemandOutput = field(default_factory=CropDemandOutput)

    # SAR Tillage & SOC
    tillage_detection: TillageDetection = field(default_factory=TillageDetection)
    soc_dynamics: SOCDynamics = field(default_factory=SOCDynamics)

    # Quality
    quality_metrics: QualityMetricsL4 = field(default_factory=QualityMetricsL4)
    data_health: DataHealthScore = field(default_factory=DataHealthScore)
    audit: AuditSnapshot = field(default_factory=AuditSnapshot)

    # Spatial extensions
    zone_metrics: Dict[str, Any] = field(default_factory=dict)

    def content_hash(self) -> str:
        """Deterministic hash for reproducibility."""
        payload = {
            "run_id": self.run_meta.run_id,
            "n_states": len(self.nutrient_states),
            "n_prescriptions": len(self.prescriptions),
            "state_probs": {
                k.value: round(v.probability_deficient, 4)
                for k, v in sorted(self.nutrient_states.items(), key=lambda x: x[0].value)
            },
            "total_rates": {
                p.nutrient.value: round(p.rate_kg_ha, 2)
                for p in self.prescriptions
            },
            "health": round(self.data_health.overall, 4),
            "tillage": self.tillage_detection.tillage_class.value,
        }
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
