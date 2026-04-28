"""
Layer 0.3: StateVector — Daily State Representation + Process Model

Defines:
  - StateVector: the 8-variable latent state estimated daily per zone/pixel
  - ProcessModel: physics-inspired daily evolution rules
  - StateCovariance: manages uncertainty propagation

The state vector represents "what we believe the field looks like today"
and evolves daily via the process model, corrected by observations.

State variables:
  0: lai_proxy        — Leaf Area Index (from NDVI/EVI/SAR)
  1: biomass_proxy    — Canopy structure (from SAR VH)  
  2: sm_0_10          — Soil moisture 0–10cm (from SAR VV + sensors + water balance)
  3: sm_10_40         — Soil moisture 10–40cm (from water balance + sensors)
  4: canopy_stress    — Water stress index 0–1 (from NDMI + deficit + VPD)
  5: phenology_gdd    — Accumulated GDD since sowing
  6: phenology_stage  — Discrete stage as float: 0=dormant, 1=veg, 2=flower, 3=ripen, 4=senescence
  7: stress_thermal   — Temperature stress index 0–1
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math


# ============================================================================
# Constants
# ============================================================================

# State variable indices
IDX_LAI = 0
IDX_BIOMASS = 1
IDX_SM_0_10 = 2
IDX_SM_10_40 = 3
IDX_CANOPY_STRESS = 4
IDX_PHENO_GDD = 5
IDX_PHENO_STAGE = 6
IDX_STRESS_THERMAL = 7

N_STATES = 8

STATE_NAMES = [
    "lai_proxy", "biomass_proxy", "sm_0_10", "sm_10_40",
    "canopy_stress", "phenology_gdd", "phenology_stage", "stress_thermal"
]

# Phenology stages (represented as float for smooth transitions)
STAGE_DORMANT = 0.0
STAGE_VEGETATIVE = 1.0
STAGE_FLOWERING = 2.0
STAGE_RIPENING = 3.0
STAGE_SENESCENCE = 4.0

# Default crop parameters (wheat-like, overrideable per crop)
DEFAULT_CROP_PARAMS = {
    "t_base": 5.0,           # °C — base temperature for GDD
    "t_opt": 25.0,            # °C — optimal temperature
    "t_max": 35.0,            # °C — maximum temperature (stress)
    "gdd_vegetative": 200,    # GDD to enter vegetative stage
    "gdd_flowering": 800,     # GDD to enter flowering
    "gdd_ripening": 1200,     # GDD to enter ripening
    "gdd_senescence": 1600,   # GDD to enter senescence
    "lai_max": 5.0,           # Maximum LAI
    "lai_growth_rate": 0.04,  # LAI units per GDD unit when growing
    "lai_decay_rate": 0.02,   # LAI units per GDD unit during senescence
    "root_depth_m": 0.4,      # Root zone depth (for sm_10_40 relevance)
    "kc_mid": 1.1,            # Crop coefficient at mid-season
    "whc_mm_per_m": 150.0,    # Water holding capacity (mm/m depth)
}


# ============================================================================
# State Vector
# ============================================================================

@dataclass
class StateVector:
    """
    The 8-variable daily latent state for a zone or pixel.
    
    This is what the Kalman filter estimates. It represents our best
    belief about the field state on a given day.
    """
    values: List[float] = field(default_factory=lambda: [0.0] * N_STATES)
    day: str = ""  # ISO date YYYY-MM-DD
    
    # Covariance diagonal (variance per variable)
    # Full covariance matrix is in StateCovariance for the Kalman filter
    variance: List[float] = field(default_factory=lambda: [0.1] * N_STATES)
    
    @property
    def lai(self) -> float: return self.values[IDX_LAI]
    @property
    def biomass(self) -> float: return self.values[IDX_BIOMASS]
    @property
    def sm_0_10(self) -> float: return self.values[IDX_SM_0_10]
    @property
    def sm_10_40(self) -> float: return self.values[IDX_SM_10_40]
    @property
    def canopy_stress(self) -> float: return self.values[IDX_CANOPY_STRESS]
    @property
    def phenology_gdd(self) -> float: return self.values[IDX_PHENO_GDD]
    @property
    def phenology_stage(self) -> float: return self.values[IDX_PHENO_STAGE]
    @property
    def stress_thermal(self) -> float: return self.values[IDX_STRESS_THERMAL]
    
    @classmethod
    def initial(cls, day: str, soil_props: Optional[Dict] = None) -> "StateVector":
        """
        Create an initial state (before any observations).
        Uses soil priors if available.
        """
        # Initial soil moisture from water holding capacity
        whc = DEFAULT_CROP_PARAMS["whc_mm_per_m"]
        initial_sm = 0.5  # fraction of field capacity
        
        if soil_props:
            clay = soil_props.get("clay_pct", 25)
            # Higher clay -> higher water holding capacity -> higher initial moisture
            initial_sm = min(0.8, 0.3 + clay * 0.01)
        
        state = cls(
            values=[
                0.2,           # LAI — low initial (bare/early)
                0.1,           # Biomass — low
                initial_sm,    # SM 0–10cm 
                initial_sm,    # SM 10–40cm
                0.0,           # No stress initially
                0.0,           # GDD = 0 (start)
                STAGE_DORMANT, # Dormant
                0.0,           # No thermal stress
            ],
            day=day,
            variance=[
                0.5,   # LAI — high uncertainty initially
                0.5,   # Biomass
                0.15,  # SM 0–10
                0.15,  # SM 10–40
                0.2,   # Stress
                10.0,  # GDD
                0.5,   # Stage
                0.2,   # Thermal stress
            ],
        )
        return state
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for FieldTensor storage."""
        d = {"day": self.day}
        for i, name in enumerate(STATE_NAMES):
            d[name] = round(self.values[i], 4)
        return d
    
    def uncertainty_dict(self) -> Dict[str, Any]:
        """Serialize variances as sigmas."""
        d = {"day": self.day}
        for i, name in enumerate(STATE_NAMES):
            d[name] = round(math.sqrt(max(0, self.variance[i])), 4)
        return d
    
    def clone(self) -> "StateVector":
        return StateVector(
            values=self.values[:],
            day=self.day,
            variance=self.variance[:],
        )


# ============================================================================
# State Covariance (for Kalman filter)
# ============================================================================

@dataclass
class StateCovariance:
    """
    Full N×N covariance matrix for the state vector.
    Tracks correlations between state variables.
    
    Pure Python: stored as List[List[float]] (8×8 matrix).
    """
    P: List[List[float]] = field(default_factory=lambda: 
        [[0.0] * N_STATES for _ in range(N_STATES)])
    
    @classmethod
    def from_diagonal(cls, variances: List[float]) -> "StateCovariance":
        """Initialize covariance from diagonal variances."""
        P = [[0.0] * N_STATES for _ in range(N_STATES)]
        for i in range(N_STATES):
            P[i][i] = variances[i] if i < len(variances) else 0.1
        return cls(P=P)
    
    def diagonal(self) -> List[float]:
        """Extract diagonal (variances)."""
        return [self.P[i][i] for i in range(N_STATES)]
    
    def get(self, i: int, j: int) -> float:
        return self.P[i][j]
    
    def set(self, i: int, j: int, val: float) -> None:
        self.P[i][j] = val
    
    def add_process_noise(self, Q: List[float]) -> None:
        """Add process noise (diagonal) to covariance."""
        for i in range(N_STATES):
            self.P[i][i] += Q[i] if i < len(Q) else 0.01


# ============================================================================
# Process Model — Daily State Evolution
# ============================================================================

class ProcessModel:
    """
    Physics-inspired daily evolution of the state vector.
    
    Given:
      - yesterday's state x(t-1)
      - today's weather drivers (temp, rain, ET0, wind, radiation)
      - management events (irrigation, sowing, harvest)
    
    Produces:
      - predicted state x_pred(t) = f(x(t-1), drivers)
      - process noise Q (how much uncertainty the prediction adds)
    
    This is a simplified agronomic model — not full crop simulation,
    but enough for state estimation with uncertainty.
    """
    
    def __init__(self, crop_params: Optional[Dict] = None):
        self.params = {**DEFAULT_CROP_PARAMS}
        if crop_params:
            self.params.update(crop_params)
    
    def predict(self, state: StateVector, 
                weather: Dict[str, float],
                events: Optional[List[Dict]] = None,
                dt_days: float = 1.0) -> Tuple[StateVector, List[float]]:
        """
        Predict next-day state from current state + weather drivers.
        
        Args:
            state: current state vector
            weather: {
                "temp_max": °C, "temp_min": °C,
                "precipitation": mm, "et0": mm,
                "wind_speed": m/s, "radiation": W/m²,
                "vpd": kPa (optional)
            }
            events: [{event_type: "irrigation", amount_mm: 20}, ...]
            dt_days: time step (normally 1.0)
            
        Returns:
            (predicted_state, process_noise_Q)
        """
        x = state.clone()
        p = self.params
        
        # Extract weather
        t_max = weather.get("temp_max", 20.0)
        t_min = weather.get("temp_min", 10.0)
        t_mean = (t_max + t_min) / 2.0
        rain_mm = weather.get("precipitation", 0.0)
        et0_mm = weather.get("et0", 3.0)
        
        # ---- 1. GDD accumulation ----
        gdd_today = max(0, t_mean - p["t_base"]) * dt_days
        new_gdd = x.values[IDX_PHENO_GDD] + gdd_today
        x.values[IDX_PHENO_GDD] = new_gdd
        
        # ---- 2. Phenology stage update ----
        if new_gdd < p["gdd_vegetative"]:
            x.values[IDX_PHENO_STAGE] = STAGE_DORMANT
        elif new_gdd < p["gdd_flowering"]:
            # Smooth transition: interpolate within vegetative
            frac = (new_gdd - p["gdd_vegetative"]) / max(1, p["gdd_flowering"] - p["gdd_vegetative"])
            x.values[IDX_PHENO_STAGE] = STAGE_VEGETATIVE + frac * (STAGE_FLOWERING - STAGE_VEGETATIVE)
        elif new_gdd < p["gdd_ripening"]:
            frac = (new_gdd - p["gdd_flowering"]) / max(1, p["gdd_ripening"] - p["gdd_flowering"])
            x.values[IDX_PHENO_STAGE] = STAGE_FLOWERING + frac * (STAGE_RIPENING - STAGE_FLOWERING)
        elif new_gdd < p["gdd_senescence"]:
            frac = (new_gdd - p["gdd_ripening"]) / max(1, p["gdd_senescence"] - p["gdd_ripening"])
            x.values[IDX_PHENO_STAGE] = STAGE_RIPENING + frac * (STAGE_SENESCENCE - STAGE_RIPENING)
        else:
            x.values[IDX_PHENO_STAGE] = STAGE_SENESCENCE
        
        # ---- 3. LAI evolution ----
        stage = x.values[IDX_PHENO_STAGE]
        current_lai = x.values[IDX_LAI]
        
        if stage < STAGE_SENESCENCE:
            # Growth: LAI increases with GDD, limited by water stress and max LAI
            stress_factor = 1.0 - x.values[IDX_CANOPY_STRESS] * 0.5
            growth = p["lai_growth_rate"] * gdd_today * stress_factor * dt_days
            new_lai = min(p["lai_max"], current_lai + growth)
        else:
            # Senescence: LAI decays
            decay = p["lai_decay_rate"] * gdd_today * dt_days
            new_lai = max(0.0, current_lai - decay)
        
        x.values[IDX_LAI] = max(0.0, new_lai)
        
        # ---- 4. Biomass proxy (tracks LAI * duration) ----
        x.values[IDX_BIOMASS] = max(0.0, x.values[IDX_LAI] * 0.3 + x.values[IDX_BIOMASS] * 0.7)
        
        # ---- 5. Soil moisture water balance ----
        # Simple bucket model per layer
        kc = self._crop_coefficient(stage)
        et_crop = et0_mm * kc * dt_days
        
        # Top layer (0–10cm): receives rain directly, loses to ET and percolation
        whc_top = p["whc_mm_per_m"] * 0.1  # 10cm depth -> mm
        sm_top = x.values[IDX_SM_0_10]
        
        # Add irrigation events
        irrigation_mm = 0.0
        if events:
            for evt in events:
                if evt.get("event_type") == "irrigation":
                    irrigation_mm += evt.get("amount_mm", 0.0)
        
        water_in = rain_mm + irrigation_mm
        sm_top_mm = sm_top * whc_top + water_in
        
        # ET extraction (weighted by layer)
        et_from_top = et_crop * 0.6  # 60% from top layer
        sm_top_mm = max(0, sm_top_mm - et_from_top)
        
        # Percolation (excess drains to deeper layer)
        percolation = max(0, sm_top_mm - whc_top)
        sm_top_mm = min(whc_top, sm_top_mm)
        x.values[IDX_SM_0_10] = sm_top_mm / max(whc_top, 0.01)
        
        # Root zone layer (10–40cm)
        whc_root = p["whc_mm_per_m"] * 0.3  # 30cm depth
        sm_root_mm = x.values[IDX_SM_10_40] * whc_root + percolation
        et_from_root = et_crop * 0.4  # 40% from root zone
        sm_root_mm = max(0, sm_root_mm - et_from_root)
        deep_drainage = max(0, sm_root_mm - whc_root)
        sm_root_mm = min(whc_root, sm_root_mm)
        x.values[IDX_SM_10_40] = sm_root_mm / max(whc_root, 0.01)
        
        # ---- 6. Canopy water stress ----
        # Stress increases when soil moisture is low relative to demand
        avg_sm = (x.values[IDX_SM_0_10] + x.values[IDX_SM_10_40]) / 2
        if avg_sm < 0.3:
            stress_water = (0.3 - avg_sm) / 0.3  # 0–1
        else:
            stress_water = 0.0
        
        # VPD contribution (if available)
        vpd = weather.get("vpd", None)
        if vpd and vpd > 2.0:
            stress_water = min(1.0, stress_water + (vpd - 2.0) * 0.2)
        
        # Smooth update (don't jump instantly)
        x.values[IDX_CANOPY_STRESS] = 0.7 * x.values[IDX_CANOPY_STRESS] + 0.3 * stress_water
        
        # ---- 7. Thermal stress ----
        stress_t = 0.0
        if t_max > p["t_max"]:
            stress_t = min(1.0, (t_max - p["t_max"]) / 10.0)
        elif t_min < 0:
            stress_t = min(1.0, abs(t_min) / 10.0)
        x.values[IDX_STRESS_THERMAL] = 0.8 * x.values[IDX_STRESS_THERMAL] + 0.2 * stress_t
        
        # ---- 8. Clamp all values ----
        x.values[IDX_LAI] = _clamp(x.values[IDX_LAI], 0, p["lai_max"])
        x.values[IDX_BIOMASS] = _clamp(x.values[IDX_BIOMASS], 0, 10)
        x.values[IDX_SM_0_10] = _clamp(x.values[IDX_SM_0_10], 0, 1)
        x.values[IDX_SM_10_40] = _clamp(x.values[IDX_SM_10_40], 0, 1)
        x.values[IDX_CANOPY_STRESS] = _clamp(x.values[IDX_CANOPY_STRESS], 0, 1)
        x.values[IDX_PHENO_STAGE] = _clamp(x.values[IDX_PHENO_STAGE], 0, 4)
        x.values[IDX_STRESS_THERMAL] = _clamp(x.values[IDX_STRESS_THERMAL], 0, 1)
        
        # ---- Process noise Q ----
        # Model uncertainty: how much we don't trust the prediction
        Q = [
            0.01,   # LAI: small noise if model is reasonable
            0.01,   # Biomass
            0.02,   # SM top: rain spatial variability adds noise
            0.01,   # SM root
            0.02,   # Stress
            1.0,    # GDD: temperature measurement uncertainty
            0.01,   # Stage
            0.01,   # Thermal stress
        ]
        
        # Higher process noise when weather uncertainty is high
        if rain_mm > 10:
            Q[IDX_SM_0_10] *= 2  # heavy rain -> uncertain infiltration
        
        return x, Q
    
    def _crop_coefficient(self, stage: float) -> float:
        """Estimate crop coefficient Kc from phenology stage."""
        p = self.params
        if stage < STAGE_VEGETATIVE:
            return 0.3
        elif stage < STAGE_FLOWERING:
            # Linear increase to Kc_mid
            frac = (stage - STAGE_VEGETATIVE) / max(0.01, STAGE_FLOWERING - STAGE_VEGETATIVE)
            return 0.3 + frac * (p["kc_mid"] - 0.3)
        elif stage < STAGE_RIPENING:
            return p["kc_mid"]
        elif stage < STAGE_SENESCENCE:
            frac = (stage - STAGE_RIPENING) / max(0.01, STAGE_SENESCENCE - STAGE_RIPENING)
            return p["kc_mid"] - frac * (p["kc_mid"] - 0.3)
        else:
            return 0.3


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
