
"""
Layer 2 Schema: Vegetation Intelligence Data Structures
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import hashlib

# --- Enums ---

class PhenologyStage(str, Enum):
    BARE_SOIL = "BARE_SOIL"
    EMERGENCE = "EMERGENCE"
    VEGETATIVE = "VEGETATIVE" # Early growth
    REPRODUCTIVE = "REPRODUCTIVE" # Flowering/Grain Fill
    SENESCENCE = "SENESCENCE"
    HARVESTED = "HARVESTED"
    UNKNOWN = "UNKNOWN"

class AnomalyType(str, Enum):
    STALL = "STALL" # Growth slower than expected
    DROP = "DROP" # Sudden loss of vigor (not harvest)
    EARLY_SENESCENCE = "EARLY_SENESCENCE"
    DELAYED_EMERGENCE = "DELAYED_EMERGENCE"
    SPATIAL_The = "SPATIAL_PATCHINESS"

# --- Data Structures ---

@dataclass
class GrowthMetrics:
    """Summary of the biological growth curve"""
    peak_ndvi: float = 0.0
    peak_date: str = "" # ISO date
    auc_season: float = 0.0 # Area Under Curve (Biomass proxy)
    max_growth_rate: float = 0.0
    senescence_rate: float = 0.0

@dataclass
class VegetationAnomaly:
    """A detected issue in time or space"""
    anomaly_id: str
    type: AnomalyType
    date_range: List[str] # [start, end]
    severity: float # 0.0 to 1.0
    confidence: float
    description: str
    likely_cause: str = "UNKNOWN"

@dataclass
class SpatialMetrics:
    """
    Summary of spatial behavior over time.
    """
    mean_spatial_var: float # Average spatial std dev (Persistent heterogeneity)
    std_spatial_var: float # Volatility of spatial std dev (Transient issues)
    stability_class: str # STABLE, HETEROGENEOUS, TRANSIENT_VAR
    confidence: float = 1.0 # NEW: Reliability of the classification

@dataclass
class VegIntInput:
    """
    Strict Input Contract from Layer 1.
    """
    date: str
    ndvi_obs: Optional[float] # Raw observed NDVI (if observed)
    ndvi_unc_obs: float # Observation uncertainty (0.1 observed, 0.5 interpolated)
    is_observed: bool
    
    # Context (Optional but recommended)
    rain: float = 0.0
    tmean: float = 20.0
    gdd: float = 0.0
    vv: Optional[float] = None
    vh: Optional[float] = None


@dataclass
class CurveQuality:
    rmse: float
    outlier_frac: float
    obs_coverage: float

@dataclass
class ModeledCurveOutput:
    ndvi_fit: List[float]
    ndvi_fit_d1: List[float] # Velocity
    quality: CurveQuality
    ndvi_fit_unc: List[float] = field(default_factory=list) # NEW: Uncertainty (1-sigma) of the modeled curve

@dataclass
class PhenologyOutput:
    stage_by_day: List[str]
    key_dates: Dict[str, str] # {Stage -> Date}
    confidence_by_day: List[float] = field(default_factory=list) # NEW: Confidence (0.0-1.0)

@dataclass
class VegIntOutput:
    """
    Strict Output Contract for Layer 2.
    """
    run_id: str
    layer1_run_id: str
    
    # Structured Outputs
    curve: ModeledCurveOutput
    phenology: PhenologyOutput
    anomalies: List[VegetationAnomaly]
    stability: SpatialMetrics
    
    # --- SPATIAL EXTENSIONS (Phase 11) ---
    zone_metrics: Dict[str, Any] = field(default_factory=dict) # zone_id -> {curve, phenology}
    
    # Provenance
    provenance: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self):
        return {
            "run_id": self.run_id,
            "layer1_run_id": self.layer1_run_id,
            "curve": {
                # "ndvi_fit": self.curve.ndvi_fit, # Omitted for summary brevity
                "quality": self.curve.quality.__dict__
            },
            "phenology": {
                "key_dates": self.phenology.key_dates,
                # "stage_by_day": self.phenology.stage_by_day # Omitted 
            },
            "anomalies": [a.__dict__ for a in self.anomalies],
            "stability": self.stability.__dict__,
            "zone_metrics": {k: {"quality": v.get("curve", {}).get("quality")} for k, v in self.zone_metrics.items()},
            "provenance": self.provenance
        }
