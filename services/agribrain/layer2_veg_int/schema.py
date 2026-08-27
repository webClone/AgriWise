"""
Layer 2 Schema: Vegetation Intelligence Data Structures (v3.1)

Enhanced with:
  - CropHealthIndex composite score (CWSI, LAI, vigor trend, ET deficit)
  - Extended anomaly types (water/heat/frost/wind/nutrient/excess moisture)
  - DORMANCY phenology stage for perennials
  - LAI/CWSI/fPAR/FVC/NPP series on ModeledCurveOutput
  - ET0-based water balance fields
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import hashlib

# --- Enums ---

class PhenologyStage(str, Enum):
    BARE_SOIL = "BARE_SOIL"
    EMERGENCE = "EMERGENCE"
    VEGETATIVE = "VEGETATIVE"       # Early growth
    REPRODUCTIVE = "REPRODUCTIVE"   # Flowering / Grain Fill
    SENESCENCE = "SENESCENCE"
    HARVESTED = "HARVESTED"
    DORMANCY = "DORMANCY"           # Perennial winter rest (olive, citrus, vine)
    UNKNOWN = "UNKNOWN"

class AnomalyType(str, Enum):
    # Negative deviations
    STALL = "STALL"                         # Growth slower than expected
    DROP = "DROP"                           # Sudden loss of vigor (not harvest)
    EARLY_SENESCENCE = "EARLY_SENESCENCE"
    DELAYED_EMERGENCE = "DELAYED_EMERGENCE"
    SPATIAL_PATCHINESS = "SPATIAL_PATCHINESS"
    # Multi-index anomalies (v3.0)
    WATER_STRESS = "WATER_STRESS"           # NDWI/NDMI decline without NDVI drop
    EXCESS_MOISTURE = "EXCESS_MOISTURE"     # Waterlogging / flooding signal
    NUTRIENT_DEFICIENCY = "NUTRIENT_DEFICIENCY"  # EVI drop faster than NDVI
    HEAT_STRESS = "HEAT_STRESS"             # Temperature-correlated NDVI decline
    # v3.1: Additional damage types
    FROST_DAMAGE = "FROST_DAMAGE"           # Sub-zero temperature during growth
    WIND_DAMAGE = "WIND_DAMAGE"             # SAR structural change without rain
    # Positive deviations
    POSITIVE_ANOMALY = "POSITIVE_ANOMALY"   # Unexpected greenup (algae, misclass)

# --- Data Structures ---

@dataclass
class GrowthMetrics:
    """Summary of the biological growth curve."""
    peak_ndvi: float = 0.0
    peak_date: str = ""                     # ISO date
    auc_season: float = 0.0                 # Area Under Curve — trapezoidal (biomass proxy)
    auc_small: float = 0.0                  # Small integral (above base NDVI)
    max_growth_rate: float = 0.0            # Max dNDVI/dt
    senescence_rate: float = 0.0            # Min dNDVI/dt (most negative)
    sos_date: str = ""                      # Start of Season (NDVI crosses 20% amplitude)
    eos_date: str = ""                      # End of Season
    los_days: int = 0                       # Length of Season

@dataclass
class CropHealthIndex:
    """Composite health score combining multiple vegetation indices.

    Provides a single actionable number for dashboard display, plus
    decomposed sub-scores for diagnostic drill-down.
    """
    overall_score: float = 0.5              # 0.0 (dead) to 1.0 (optimal)
    ndvi_health: float = 0.5                # NDVI vs crop-specific optimal range
    water_stress_index: Optional[float] = 0.0  # CWSI: 0=no stress, 1=severe, None if unknown
    lai_estimate: float = 0.0              # Leaf Area Index (current)
    lai_peak: float = 0.0                  # Peak LAI this season
    biomass_proxy: float = 0.0              # Normalized AUC (0-1)
    vigor_trend: str = "STABLE"             # IMPROVING, STABLE, DECLINING
    vigor_slope: float = 0.0                # Linear trend slope of recent NDVI (per day)
    anomaly_penalty: float = 0.0            # Accumulated anomaly severity (0-1)
    confidence: float = 0.5                 # 0-1 based on data availability
    # v3.1: ET-based water balance
    et_actual: float = 0.0                  # Actual ET estimate (mm/day)
    et_deficit: float = 0.0                 # ETc - ETa (mm/day, >0 = water deficit)
    vegetation_fraction: float = 0.0        # FVC: Fractional Vegetation Cover [0-1]
    fpar_current: float = 0.0               # Fraction of Absorbed PAR [0-1]
    # v3.2: AquaCrop-style water productivity (Steduto 2009)
    wue: float = 0.0                        # Water Use Efficiency (gC/m²/mm)
    crop_water_productivity: float = 0.0    # Yield / ET_total (kg/m³)
    # v3.2: Vernalization tracking (Richardson 1974)
    vernalization_progress: float = 0.0     # 0.0-1.0 (1.0 = fully vernalized)
    # v4.0: Dynamic component weighting and missingness coverage
    health_component_coverage: float = 1.0  # Weight fraction of available components [0, 1]
    component_state_mask: Dict[str, str] = field(default_factory=dict)  # {component: OBSERVED/UNKNOWN}

@dataclass
class AttributionEvidence:
    """Per-cause confidence scores for anomaly attribution.

    Each field represents the probability [0,1] that the cause explains
    the observed anomaly.  Multiple causes can have high probability
    (e.g. heat stress + water stress often co-occur).
    """
    water_stress: float = 0.0               # NDWI/NDMI decline
    excess_moisture: float = 0.0            # Rainfall surplus, NDWI spike
    heat_stress: float = 0.0                # T > crop optimal_temp_max
    frost_stress: float = 0.0               # v3.1: T_min < crop optimal_temp_min - 5
    nutrient_deficiency: float = 0.0        # EVI decline faster than NDVI
    structural_damage: float = 0.0          # SAR VH/VV ratio change
    disease_or_pest: float = 0.0            # Residual: no abiotic explanation
    primary_cause: str = "UNKNOWN_STRESS"   # Highest-probability cause label

@dataclass
class VegetationAnomaly:
    """A detected issue in time or space."""
    anomaly_id: str
    type: AnomalyType
    date_range: List[str]                   # [start, end]
    severity: float                         # 0.0 to 1.0
    confidence: float
    description: str
    likely_cause: str = "UNKNOWN"
    attribution: Optional[AttributionEvidence] = None  # v3.0: decomposed evidence

@dataclass
class SpatialMetrics:
    """Summary of spatial behavior over time."""
    mean_spatial_var: float                 # Average spatial std dev
    std_spatial_var: float                  # Volatility of spatial std dev
    stability_class: str                    # STABLE, HETEROGENEOUS, TRANSIENT_VAR
    confidence: float = 1.0
    morans_i: float = 0.0                  # Global Moran's I (-1 to 1)
    morans_p: float = 1.0                  # Pseudo-significance p-value
    morans_status: str = "AVAILABLE"       # AVAILABLE | UNAVAILABLE (no topology)
    spatial_trend: str = "STABLE"           # INCREASING, STABLE, DECREASING
    spatial_trend_p: float = 1.0            # Mann-Kendall p-value
    worst_zone_id: str = ""                 # Zone with lowest health
    best_zone_id: str = ""                  # Zone with highest health
    zone_health_scores: Dict[str, float] = field(default_factory=dict)
    # v3.1: CUSUM
    cusum_alarm: bool = False               # True if CUSUM crossed threshold
    cusum_value: float = 0.0                # Current CUSUM accumulator value
    zone_trends: Dict[str, str] = field(default_factory=dict)  # {zone: IMPROVING/STABLE/DECLINING}

@dataclass
class VegIntInput:
    """Strict Input Contract from Layer 1."""
    date: str
    ndvi_obs: Optional[float]               # Raw observed NDVI (if observed)
    ndvi_unc_obs: float                     # Observation uncertainty
    is_observed: bool

    # Context (Optional but recommended)
    rain: Optional[float] = None
    tmean: Optional[float] = None
    gdd: Optional[float] = None
    vv: Optional[float] = None
    vh: Optional[float] = None
    # Multi-spectral indices (v3.0)
    evi: Optional[float] = None
    ndwi: Optional[float] = None
    ndmi: Optional[float] = None
    # v3.1: Weather detail
    et0: Optional[float] = None             # Reference evapotranspiration (mm/day)
    temp_max: Optional[float] = None        # Daily maximum temperature (°C)
    temp_min: Optional[float] = None        # Daily minimum temperature (°C)


@dataclass
class CurveQuality:
    rmse: float
    outlier_frac: float
    obs_coverage: float

@dataclass
class ModeledCurveOutput:
    ndvi_fit: List[float]
    ndvi_fit_d1: List[float]                # Velocity (dNDVI/dt)
    quality: CurveQuality
    ndvi_fit_unc: List[float] = field(default_factory=list)
    ndvi_fit_d2: List[float] = field(default_factory=list)   # Acceleration
    lai_series: List[float] = field(default_factory=list)    # v3.0: LAI per timestep
    cwsi_series: List[float] = field(default_factory=list)   # v3.0: CWSI per timestep
    # v3.1: Additional biophysical products
    fpar_series: List[float] = field(default_factory=list)   # fPAR per timestep [0-1]
    fvc_series: List[float] = field(default_factory=list)    # Fractional Vegetation Cover [0-1]
    npp_series: List[float] = field(default_factory=list)    # NPP proxy (gC/m²/day)
    # Explicit NPP decomposition (Field et al. 1995, CASA)
    npp_light_temperature_series: List[float] = field(default_factory=list)      # Potential NPP (gC/m²/day)
    npp_spectral_water_adjusted_series: List[float] = field(default_factory=list) # Water-adjusted NPP
    water_constraint_source: str = "NONE"   # SPECTRAL_PROXY | MODEL_DERIVED | NONE
    water_constraint_applied: bool = False

@dataclass
class PhenologyOutput:
    stage_by_day: List[str]
    key_dates: Dict[str, str]               # {Stage -> Date}
    confidence_by_day: List[float] = field(default_factory=list)
    sub_stages_by_day: List[str] = field(default_factory=list)
    canonical_posterior: Optional[Dict[str, Any]] = None

@dataclass
class VegIntOutput:
    """Strict Output Contract for Layer 2."""
    run_id: str
    layer1_run_id: str

    # Structured Outputs
    curve: ModeledCurveOutput
    phenology: PhenologyOutput
    anomalies: List[VegetationAnomaly]
    stability: SpatialMetrics

    # v3.0: Composite health score
    health_index: CropHealthIndex = field(default_factory=CropHealthIndex)
    growth_metrics: GrowthMetrics = field(default_factory=GrowthMetrics)

    # --- SPATIAL EXTENSIONS (Phase 11) ---
    zone_metrics: Dict[str, Any] = field(default_factory=dict)

    # Scientific receipts
    crop_season_evidence_receipt: Optional[Dict[str, Any]] = None
    crop_active_acquisition_plan: Optional[Dict[str, Any]] = None

    # Provenance
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_json(self):
        return {
            "run_id": self.run_id,
            "layer1_run_id": self.layer1_run_id,
            "curve": {
                "quality": self.curve.quality.__dict__
            },
            "phenology": {
                "key_dates": self.phenology.key_dates,
                "canonical_posterior": self.phenology.canonical_posterior,
                "sub_stages_by_day": self.phenology.sub_stages_by_day,
            },
            "anomalies": [
                {
                    "anomaly_id": a.anomaly_id,
                    "type": a.type.value if isinstance(a.type, AnomalyType) else a.type,
                    "date_range": a.date_range,
                    "severity": a.severity,
                    "confidence": a.confidence,
                    "description": a.description,
                    "likely_cause": a.likely_cause,
                    "attribution": {
                        "water_stress": a.attribution.water_stress,
                        "heat_stress": a.attribution.heat_stress,
                        "frost_stress": a.attribution.frost_stress,
                        "nutrient_deficiency": a.attribution.nutrient_deficiency,
                        "disease_or_pest": a.attribution.disease_or_pest,
                        "primary_cause": a.attribution.primary_cause,
                    } if a.attribution else None,
                }
                for a in self.anomalies
            ],
            "stability": {
                "mean_spatial_var": self.stability.mean_spatial_var,
                "std_spatial_var": self.stability.std_spatial_var,
                "stability_class": self.stability.stability_class,
                "confidence": self.stability.confidence,
                "morans_i": self.stability.morans_i,
                "spatial_trend": self.stability.spatial_trend,
                "worst_zone": self.stability.worst_zone_id,
                "best_zone": self.stability.best_zone_id,
                "cusum_alarm": self.stability.cusum_alarm,
            },
            "health_index": {
                "overall_score": self.health_index.overall_score,
                "ndvi_health": self.health_index.ndvi_health,
                "water_stress": self.health_index.water_stress_index,
                "lai": self.health_index.lai_estimate,
                "vegetation_fraction": self.health_index.vegetation_fraction,
                "fpar": self.health_index.fpar_current,
                "et_deficit": self.health_index.et_deficit,
                "vigor_trend": self.health_index.vigor_trend,
                "vigor_slope": self.health_index.vigor_slope,
                "confidence": self.health_index.confidence,
                "wue": self.health_index.wue,
                "crop_water_productivity": self.health_index.crop_water_productivity,
                "vernalization_progress": self.health_index.vernalization_progress,
                "coverage": self.health_index.health_component_coverage,
                "component_state_mask": self.health_index.component_state_mask,
            },
            "growth_metrics": {
                "peak_ndvi": self.growth_metrics.peak_ndvi,
                "peak_date": self.growth_metrics.peak_date,
                "auc_season": self.growth_metrics.auc_season,
                "sos_date": self.growth_metrics.sos_date,
                "eos_date": self.growth_metrics.eos_date,
                "los_days": self.growth_metrics.los_days,
            },
            "zone_metrics": {k: {"quality": v.get("curve", {}).get("quality")} for k, v in self.zone_metrics.items()},
            "crop_season_evidence_receipt": self.crop_season_evidence_receipt,
            "crop_active_acquisition_plan": self.crop_active_acquisition_plan,
            "provenance": self.provenance
        }
