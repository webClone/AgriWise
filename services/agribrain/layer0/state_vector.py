"""
Layer 0.3: StateVector — Daily State Representation + Process Model

Defines:
  - StateVector: the 9-variable latent state estimated daily per zone/pixel
  - ProcessModel: physics-inspired daily evolution rules
  - StateCovariance: manages uncertainty propagation

The state vector represents "what we believe the field looks like today"
and evolves daily via the process model, corrected by observations.

State variables:
  0: lai_proxy               — Leaf Area Index (from NDVI/EVI/SAR)
  1: biomass_proxy           — Canopy structure (from SAR VH)
  2: sm_0_10                 — Soil moisture 0–10cm (from SAR VV + sensors + water balance)
  3: sm_10_40                — Soil moisture 10–40cm (from water balance + sensors)
  4: canopy_stress           — Water stress index 0–1 (from NDMI + deficit + VPD)
  5: phenology_gdd           — Accumulated GDD since sowing
  6: phenology_stage         — Discrete stage as float: 0=dormant, 1=veg, 2=flower, 3=ripen, 4=senescence
  7: stress_thermal          — Temperature stress index 0–1
  8: photosynthetic_efficiency — Active photosynthesis 0–1 (from SIF + PRI)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math

from services.agribrain.layer0.temporal_process_noise import (
    NOMINAL_VARIANCE_RATE_PER_DAY, UNFORCED_DRIFT_VARIANCE_RATE_PER_DAY,
    scale_diagonal_variance_rates, validate_dt_days,
)


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
IDX_PHOTO_EFF = 8

N_STATES = 9

STATE_NAMES = [
    "lai_proxy", "biomass_proxy", "sm_0_10", "sm_10_40",
    "canopy_stress", "phenology_gdd", "phenology_stage", "stress_thermal",
    "photosynthetic_efficiency",
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
    "gdd_emergence": 100.0,   # PROVISIONAL onset; calibrate per crop and site
    "gdd_vegetative": 200,    # GDD to enter vegetative stage
    "gdd_flowering": 800,     # GDD to enter flowering
    "gdd_ripening": 1200,     # GDD to enter ripening
    "gdd_senescence": 1600,   # GDD to enter senescence
    "lai_max": 5.0,           # Maximum LAI
    "lai_growth_rate": 0.006, # LAI units per GDD unit (calibrated: ~0.09 LAI/day at 15 GDD)
    "lai_decay_rate": 0.004,  # LAI units per GDD unit during senescence
    "root_depth_m": 0.4,      # Root zone depth (for sm_10_40 relevance)
    "kc_mid": 1.1,            # Crop coefficient at mid-season
    "whc_mm_per_m": 150.0,    # Water holding capacity (mm/m depth)
    # Provisional smooth response interval for photosynthesis shutdown.
    # These are numerical model assumptions, NOT field-calibrated thresholds.
    "photo_shutdown_blend_start": 0.05,
    "photo_shutdown_blend_end": 0.15,
}


# ============================================================================
# State Vector
# ============================================================================

@dataclass
class StateVector:
    """
    The 9-variable daily latent state for a zone or pixel.
    
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
    @property
    def photosynthetic_efficiency(self) -> float: return self.values[IDX_PHOTO_EFF]
    
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
                0.8,           # Photosynthetic efficiency — moderate prior
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
                0.3,   # Photosynthetic efficiency — moderate uncertainty
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
    
    Pure Python: stored as List[List[float]] (9×9 matrix).
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
        """Identity-transition update through the same atomic PSD gate."""
        F = [[float(i == j) for j in range(N_STATES)] for i in range(N_STATES)]
        self.propagate(F, Q)

    def propagate(self, F: List[List[float]], Q: List[float]) -> None:
        """Apply P_next = F P F^T + diag(Q), atomically.

        The process model already supplies Q as *variance*, not standard
        deviation. No covariance data is replaced by an identity assumption.
        PSD of the original P remains an upstream invariant; this method
        checks shape, finiteness, symmetry and nonnegative diagonal but is not
        an eigenvalue-based PSD certification.
        """
        n = N_STATES
        if len(F) != n or any(len(row) != n for row in F):
            raise ValueError("transition Jacobian must be NxN")
        if len(Q) != n:
            raise ValueError("process noise vector must contain N variances")
        if len(self.P) != n or any(len(row) != n for row in self.P):
            raise ValueError("prior covariance must be NxN")
        if any(
            not isinstance(v, (int, float)) or isinstance(v, bool)
            or not math.isfinite(v)
            for row in F for v in row
        ):
            raise ValueError("nonfinite transition Jacobian")
        if any(
            not isinstance(v, (int, float)) or isinstance(v, bool)
            or not math.isfinite(v) or v < 0.0 for v in Q
        ):
            raise ValueError("invalid process noise variance")
        if any(not math.isfinite(v) for row in self.P for v in row):
            raise ValueError("nonfinite prior covariance")
        for i in range(n):
            if self.P[i][i] < 0:
                raise ValueError("negative prior variance")
            for j in range(i + 1, n):
                if not math.isclose(
                    self.P[i][j], self.P[j][i], rel_tol=1e-10, abs_tol=1e-12
                ):
                    raise ValueError("asymmetric prior covariance")

        # Symmetric, nonnegative diagonal is necessary but NOT sufficient
        # for positive semidefiniteness. Reject an indefinite prior before
        # making a new candidate. NumPy is already a scientific stack
        # dependency; eigvalsh is Hermitian-specific.
        import numpy as np
        try:
            prior_eigen = np.linalg.eigvalsh(np.asarray(self.P, dtype=float))
        except (ValueError, np.linalg.LinAlgError, OverflowError):
            raise ValueError("invalid prior covariance eigenspectrum") from None
        if not np.isfinite(prior_eigen).all() or prior_eigen[0] < -1e-10:
            raise ValueError("non-PSD prior covariance")

        fp = [
            [math.fsum(F[i][k] * self.P[k][j] for k in range(n))
             for j in range(n)] for i in range(n)
        ]
        candidate = [
            [math.fsum(fp[i][k] * F[j][k] for k in range(n))
             + (Q[i] if i == j else 0.0)
             for j in range(n)] for i in range(n)
        ]
        if any(not math.isfinite(v) for row in candidate for v in row):
            raise ValueError("nonfinite propagated covariance")

        # Small roundoff asymmetry may be removed; reject material asymmetry.
        for i in range(n):
            if candidate[i][i] < 0:
                raise ValueError("negative propagated variance")
            for j in range(i + 1, n):
                a, b = candidate[i][j], candidate[j][i]
                if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-11):
                    raise ValueError("asymmetric propagated covariance")
                candidate[i][j] = candidate[j][i] = (a + b) / 2.0
        try:
            candidate_eigen = np.linalg.eigvalsh(np.asarray(candidate, dtype=float))
        except (ValueError, np.linalg.LinAlgError, OverflowError):
            raise ValueError("invalid propagated covariance eigenspectrum") from None
        if not np.isfinite(candidate_eigen).all() or candidate_eigen[0] < -1e-10:
            raise ValueError("non-PSD propagated covariance")
        self.P = candidate


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
            # Older crop profiles specify vegetative GDD without an explicit
            # emergence threshold. Preserve their proportional schedule as a
            # *provisional model assumption*, never a measured crop property.
            if "gdd_vegetative" in crop_params and "gdd_emergence" not in crop_params:
                self.params["gdd_emergence"] = 0.5 * self.params["gdd_vegetative"]
        self._validate_phenology_params()
        self._validate_photosynthesis_params()

    def _validate_photosynthesis_params(self) -> None:
        p = self.params
        start = p["photo_shutdown_blend_start"]
        end = p["photo_shutdown_blend_end"]
        if (
            isinstance(start, bool) or isinstance(end, bool)
            or not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or not math.isfinite(start) or not math.isfinite(end)
            or not (0.0 <= start < end <= 1.0)
        ):
            raise ValueError("invalid photosynthesis shutdown transition interval")

    def _validate_phenology_params(self) -> None:
        p = self.params
        names = ("gdd_emergence", "gdd_vegetative", "gdd_flowering",
                 "gdd_ripening", "gdd_senescence")
        for name in names:
            value = p[name]
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise ValueError(f"invalid {name}: finite nonnegative GDD required")
        emergence, vegetative, flowering, ripening, senescence = (
            p[name] for name in names
        )
        if not (emergence < vegetative < flowering < ripening < senescence):
            raise ValueError("phenology GDD thresholds must be strictly ordered")
        # A C1 cubic Hermite emergence segment uses the slope of the next
        # stage. Guard against a pathologically short flowering interval.
        if (vegetative - emergence) / (flowering - vegetative) > 3.0:
            raise ValueError("emergence interval incompatible with flowering slope")
    
    def predict(self, state: StateVector, 
                weather: Dict[str, float],
                events: Optional[List[Dict]] = None,
                dt_days: float = 1.0,
                skip_weather_forcing: bool = False) -> Tuple[StateVector, List[float]]:
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
            skip_weather_forcing: if True, do not run weather-driven physics
            
        Returns:
            (predicted_state, process_noise_Q)
        """
        dt_days = validate_dt_days(dt_days)
        if skip_weather_forcing:
            # No synthetic weather or physical state motion. Only a declared
            # diagonal, uncalibrated drift variance accumulates with elapsed
            # time. The caller applies F=I to this process covariance.
            return state.clone(), scale_diagonal_variance_rates(
                UNFORCED_DRIFT_VARIANCE_RATE_PER_DAY, dt_days,
            )

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
        if new_gdd < p["gdd_emergence"]:
            x.values[IDX_PHENO_STAGE] = STAGE_DORMANT
        elif new_gdd < p["gdd_vegetative"]:
            # C1 continuous emergence. A cubic Hermite ramp matches stage=0
            # and zero slope at emergence, and stage=1 plus the following
            # vegetative-stage slope at its endpoint. The onset is a declared
            # provisional parameter, not an independently calibrated truth.
            width = p["gdd_vegetative"] - p["gdd_emergence"]
            u = (new_gdd - p["gdd_emergence"]) / width
            outgoing_slope = width / (p["gdd_flowering"] - p["gdd_vegetative"])
            x.values[IDX_PHENO_STAGE] = (
                (3.0 * u * u - 2.0 * u * u * u)
                + outgoing_slope * (u * u * u - u * u)
            )
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
        
        # ---- 3. LAI evolution (adaptive growth model) ----
        stage = x.values[IDX_PHENO_STAGE]
        current_lai = x.values[IDX_LAI]
        
        # Use adaptive growth rate if calibrated, else default
        effective_growth_rate = getattr(self, '_adaptive_lai_rate', p["lai_growth_rate"])
        
        # Continuous stage response replaces abrupt modulation switches at
        # stages 1, 2, 3 and 4. These coefficients remain empirical priors;
        # smoothness is a numerical contract, not agronomic calibration.
        if stage < STAGE_VEGETATIVE:
            stage_mod = 0.3 + 0.7 * stage
        elif stage < STAGE_FLOWERING:
            stage_mod = 1.0 - 0.6 * (stage - STAGE_VEGETATIVE)
        elif stage < STAGE_RIPENING:
            stage_mod = 0.4 - 0.3 * (stage - STAGE_FLOWERING)
        else:
            stage_mod = max(0.0, 0.1 * (STAGE_SENESCENCE - stage))

        stress_factor = 1.0 - x.values[IDX_CANOPY_STRESS] * 0.5
        ceiling_factor = max(0.0, 1.0 - (current_lai / p["lai_max"]) ** 2)
        # gdd_today already integrates over dt; a second multiplication by
        # dt incorrectly yields dt^2 growth for non-daily prediction steps.
        growth = effective_growth_rate * gdd_today * stress_factor * stage_mod * ceiling_factor
        # Gradual senescence replaces the on/off decay switch at stage=4.
        senescence_weight = max(0.0, min(1.0, stage - STAGE_RIPENING))
        decay = p["lai_decay_rate"] * gdd_today * senescence_weight
        new_lai = max(0.0, min(p["lai_max"], current_lai + growth - decay))
        
        x.values[IDX_LAI] = max(0.0, new_lai)
        
        # ---- 4. Biomass proxy (tracks LAI * duration) ----
        # A daily retention rho becomes rho**dt for irregular intervals.
        biomass_retention = 0.7 ** dt_days
        x.values[IDX_BIOMASS] = max(
            0.0,
            x.values[IDX_LAI] * (1.0 - biomass_retention)
            + x.values[IDX_BIOMASS] * biomass_retention,
        )
        
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
        stress_retention = 0.7 ** dt_days
        x.values[IDX_CANOPY_STRESS] = (
            stress_retention * x.values[IDX_CANOPY_STRESS]
            + (1.0 - stress_retention) * stress_water
        )
        
        # ---- 7. Thermal stress ----
        stress_t = 0.0
        if t_max > p["t_max"]:
            stress_t = min(1.0, (t_max - p["t_max"]) / 10.0)
        elif t_min < 0:
            stress_t = min(1.0, abs(t_min) / 10.0)
        thermal_retention = 0.8 ** dt_days
        x.values[IDX_STRESS_THERMAL] = (
            thermal_retention * x.values[IDX_STRESS_THERMAL]
            + (1.0 - thermal_retention) * stress_t
        )
        
        # ---- 8. Photosynthetic efficiency ----
        # Efficiency decays when stomata close (heat/water stress).
        # Recovers slowly when stress subsides. This gives the Kalman
        # filter a physics prior even without SIF/PRI observations.
        current_eff = x.values[IDX_PHOTO_EFF]
        thermal_shutdown = max(0.0, x.values[IDX_STRESS_THERMAL] - 0.3) / 0.7
        water_shutdown = max(0.0, x.values[IDX_CANOPY_STRESS] - 0.4) / 0.6
        shutdown_pressure = min(1.0, thermal_shutdown + water_shutdown)
        
        # The prior hard switch at pressure > 0.1 jumped for many valid
        # prior-efficiency values, giving a nonconvergent finite-difference
        # Jacobian and artificial full-P covariance amplification.
        # Preserve both existing response laws away from a *provisional*
        # finite transition interval, and blend them with a C1 smoothstep.
        # Smoothness is mathematical; the response interval is NOT calibrated.
        recovery_target = min(
            1.0, 0.9 + 0.1 * (1.0 - x.values[IDX_CANOPY_STRESS])
        )
        recovery_retention = 0.9 ** dt_days
        recovery_eff = (
            recovery_retention * current_eff
            + (1.0 - recovery_retention) * recovery_target
        )
        shutdown_target = max(0.0, 1.0 - shutdown_pressure)
        shutdown_retention = 0.6 ** dt_days
        shutdown_eff = (
            shutdown_retention * current_eff
            + (1.0 - shutdown_retention) * shutdown_target
        )
        blend_start = p["photo_shutdown_blend_start"]
        blend_end = p["photo_shutdown_blend_end"]
        blend_position = max(
            0.0, min(1.0, (shutdown_pressure - blend_start) / (blend_end - blend_start))
        )
        blend = blend_position * blend_position * (3.0 - 2.0 * blend_position)
        new_eff = (1.0 - blend) * recovery_eff + blend * shutdown_eff
        
        # Gradual loss of efficiency avoids a discontinuity at stage=4.
        new_eff *= 1.0 - (1.0 - 0.95 ** dt_days) * senescence_weight
        
        x.values[IDX_PHOTO_EFF] = new_eff
        
        # ---- 9. Clamp all values ----
        x.values[IDX_LAI] = _clamp(x.values[IDX_LAI], 0, p["lai_max"])
        x.values[IDX_BIOMASS] = _clamp(x.values[IDX_BIOMASS], 0, 10)
        x.values[IDX_SM_0_10] = _clamp(x.values[IDX_SM_0_10], 0, 1)
        x.values[IDX_SM_10_40] = _clamp(x.values[IDX_SM_10_40], 0, 1)
        x.values[IDX_CANOPY_STRESS] = _clamp(x.values[IDX_CANOPY_STRESS], 0, 1)
        x.values[IDX_PHENO_STAGE] = _clamp(x.values[IDX_PHENO_STAGE], 0, 4)
        x.values[IDX_STRESS_THERMAL] = _clamp(x.values[IDX_STRESS_THERMAL], 0, 1)
        x.values[IDX_PHOTO_EFF] = _clamp(x.values[IDX_PHOTO_EFF], 0, 1)
        
        # ---- Process noise Q ----
        # Model uncertainty: how much we don't trust the prediction
        # Higher Q = less trust in model = more weight to observations
        # Per-day *variance rates*, not sigmas or immutable daily Q.
        # These provisional priors preserve the baseline for dt=1 day.
        q_rate = list(NOMINAL_VARIANCE_RATE_PER_DAY)
        
        # Stage-dependent LAI noise: growth model is less reliable
        # during rapid transitions
        if stage >= STAGE_VEGETATIVE and stage < STAGE_FLOWERING:
            q_rate[IDX_LAI] = 0.06   # Uncalibrated peak-growth rate
        elif stage >= STAGE_SENESCENCE:
            q_rate[IDX_LAI] = 0.05   # Uncalibrated senescence rate
        
        # Higher process noise when weather uncertainty is high
        if rain_mm > 10:
            q_rate[IDX_SM_0_10] *= 2  # Provisional weather-response rate
            q_rate[IDX_SM_10_40] *= 1.5
        
        # If using adaptive rate and model error was high, inflate Q
        model_error = getattr(self, '_last_model_error', 0.0)
        if model_error > 0.3:
            q_rate[IDX_LAI] *= (1.0 + model_error)  # Provisional response
        
        # DNA data quality noise inflation:
        # When the DNA sequencing was based on degraded input data (null-filled
        # weather, sparse NDVI), inflate ALL process noise to express reduced
        # confidence in the DNA-derived crop parameters.
        dna_noise = getattr(self, '_dna_noise_factor', 1.0)
        if dna_noise > 1.0:
            q_rate = [q * dna_noise for q in q_rate]

        return x, scale_diagonal_variance_rates(q_rate, dt_days)
    
    def transition_jacobian(
        self, state: StateVector, weather: Dict[str, float],
        events: Optional[List[Dict]] = None, dt_days: float = 1.0,
        predicted_state: Optional[StateVector] = None,
    ) -> List[List[float]]:
        """Local Jacobian of the *actual* piecewise transition f(x,u).

        Central differences are used in the interior; one-sided differences
        stay inside the physical state domain. Each probe uses the identical
        weather, crop parameters and management events as the nominal step.
        This is an algorithmic derivative, not a calibrated physical law.
        Stage discontinuities cannot be represented by a local EKF Jacobian
        and are reported rather than disguised as extreme covariance.
        """
        if len(state.values) != N_STATES:
            raise ValueError("invalid prior state dimension")
        dt_days = validate_dt_days(dt_days)

        x0 = state.values
        bounds = [
            (0.0, float(self.params["lai_max"])),
            (0.0, 10.0),
            (0.0, 1.0), (0.0, 1.0), (0.0, 1.0),
            (0.0, None), (0.0, 4.0), (0.0, 1.0), (0.0, 1.0),
        ]
        for i, (low, high) in enumerate(bounds):
            value = x0[i]
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool) or not math.isfinite(value)
                or value < low or (high is not None and value > high)
            ):
                raise ValueError(f"state {STATE_NAMES[i]} outside derivative domain")

        nominal = (
            predicted_state if predicted_state is not None
            else self.predict(state, weather, events, dt_days=dt_days)[0]
        )
        y0 = nominal.values
        if len(y0) != N_STATES or any(not math.isfinite(v) for v in y0):
            raise ValueError("invalid nominal transition")

        F = [[0.0] * N_STATES for _ in range(N_STATES)]
        for j, (low, high) in enumerate(bounds):
            value = x0[j]
            step = 1e-5 * max(1.0, abs(value))
            can_plus = high is None or value + step <= high
            can_minus = value - step >= low
            if not (can_plus or can_minus):
                raise ValueError(f"no valid perturbation for {STATE_NAMES[j]}")

            plus = minus = None
            if can_plus:
                x_plus = state.clone()
                x_plus.values[j] += step
                plus = self.predict(
                    x_plus, weather, events, dt_days=dt_days
                )[0].values
            if can_minus:
                x_minus = state.clone()
                x_minus.values[j] -= step
                minus = self.predict(
                    x_minus, weather, events, dt_days=dt_days
                )[0].values
            if any(
                not math.isfinite(v)
                for values in (plus, minus) if values is not None
                for v in values
            ):
                raise ValueError("nonfinite perturbed transition")

            # Dormant -> vegetative is currently a discontinuous jump from
            # stage 0 to 1. A local linear covariance approximation is
            # invalid if a perturbation straddles that discrete boundary.
            if (
                plus is not None and minus is not None
                and abs(plus[IDX_PHENO_STAGE] - minus[IDX_PHENO_STAGE]) >= 0.5
            ):
                raise ValueError("discontinuous phenology stage transition")

            for i in range(N_STATES):
                if plus is not None and minus is not None:
                    derivative = (plus[i] - minus[i]) / (2.0 * step)
                elif plus is not None:
                    derivative = (plus[i] - y0[i]) / step
                else:
                    derivative = (y0[i] - minus[i]) / step
                if not math.isfinite(derivative):
                    raise ValueError("nonfinite transition derivative")
                F[i][j] = derivative
        return F

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
