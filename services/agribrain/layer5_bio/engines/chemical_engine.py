"""
Layer 5 Chemical Engine — Translocation, Degradation, & Spray Drift AI Model (v7.0)

Models systemic and contact chemical treatment kinetics, wash-off, and UV degradation.
Uses a simulated ML regression model (feature mapping + linear combination) to predict
the remaining active chemical concentration and a simulated Random Forest Regressor to
predict Spray Drift Risk and zone-based off-target deposition.

Scientific References:
1. Bromilow, R. H., & Chamberlain, K. (1995). Principles governing uptake and translocation of xenobiotics by plants. Plant Contamination, 37-68.
   - Outlines apoplastic (xylem) and symplastic (phloem) mobility dynamics of agrochemicals.
2. Katagi, T. (2004). Photodegradation of pesticides on plant and soil surfaces. Reviews of Environmental Contamination and Toxicology, 182, 1-189.
   - Details non-linear UV solar photolysis degradation kinetics and canopy shading effects.
3. Holterman, H. J., et al. (1997). Method for calculate spray drift. Journal of Agricultural Engineering Research, 67(4), 255-265.
   - Models droplets trajectory, evaporation, wind drift, and off-target deposition dynamics.
4. Kleier, D. A. (1988). A phloem-systemicity model. Plant Physiology, 86(3), 803-810.
   - Provides physical mathematical models linking plant transpiration to systemic pesticide absorption.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import math
from datetime import datetime
from layer5_bio.schema import ThreatId, EvidenceLogit, ThreatClass
from layer3_decision.schema import Driver

# ── Chemical Spec Repository ─────────────────────────────────────────────

@dataclass(frozen=True)
class ChemicalSpec:
    chemical_id: str
    chemical_class: str          # "FUNGICIDE" | "INSECTICIDE" | "HERBICIDE"
    translocation: str           # "SYSTEMIC" | "CONTACT"
    half_life_days_ref: float    # Base half-life under standard conditions (20°C, moderate light)
    wash_off_threshold_mm: float # Rain amount that washes off 50% of surface contact residues
    base_efficacy: float         # Base threat suppression rate [0, 1]
    photolysis_sensitivity: float = 0.05 # Sensitivity to UV degradation

CHEMICAL_REGISTRY: Dict[str, ChemicalSpec] = {
    # Fungicides
    "azoxystrobin": ChemicalSpec(
        chemical_id="azoxystrobin", chemical_class="FUNGICIDE", translocation="SYSTEMIC",
        half_life_days_ref=14.0, wash_off_threshold_mm=40.0, base_efficacy=0.90, photolysis_sensitivity=0.03
    ),
    "tebuconazole": ChemicalSpec(
        chemical_id="tebuconazole", chemical_class="FUNGICIDE", translocation="SYSTEMIC",
        half_life_days_ref=18.0, wash_off_threshold_mm=50.0, base_efficacy=0.88, photolysis_sensitivity=0.02
    ),
    "copper_hydroxide": ChemicalSpec(
        chemical_id="copper_hydroxide", chemical_class="FUNGICIDE", translocation="CONTACT",
        half_life_days_ref=7.0, wash_off_threshold_mm=10.0, base_efficacy=0.75, photolysis_sensitivity=0.08
    ),
    
    # Insecticides
    "chlorantraniliprole": ChemicalSpec(
        chemical_id="chlorantraniliprole", chemical_class="INSECTICIDE", translocation="SYSTEMIC",
        half_life_days_ref=21.0, wash_off_threshold_mm=60.0, base_efficacy=0.92, photolysis_sensitivity=0.01
    ),
    "cypermethrin": ChemicalSpec(
        chemical_id="cypermethrin", chemical_class="INSECTICIDE", translocation="CONTACT",
        half_life_days_ref=5.0, wash_off_threshold_mm=15.0, base_efficacy=0.80, photolysis_sensitivity=0.12
    ),
    "imidacloprid": ChemicalSpec(
        chemical_id="imidacloprid", chemical_class="INSECTICIDE", translocation="SYSTEMIC",
        half_life_days_ref=12.0, wash_off_threshold_mm=30.0, base_efficacy=0.85, photolysis_sensitivity=0.06
    ),
    
    # Herbicides
    "glyphosate": ChemicalSpec(
        chemical_id="glyphosate", chemical_class="HERBICIDE", translocation="SYSTEMIC",
        half_life_days_ref=30.0, wash_off_threshold_mm=45.0, base_efficacy=0.95, photolysis_sensitivity=0.005
    ),
    "clethodim": ChemicalSpec(
        chemical_id="clethodim", chemical_class="HERBICIDE", translocation="SYSTEMIC",
        half_life_days_ref=10.0, wash_off_threshold_mm=30.0, base_efficacy=0.90, photolysis_sensitivity=0.10
    ),
}

# ── Simulated AI Degradation Regression Model ────────────────────────────

class ChemicalDegradationPredictor:
    """Simulated non-linear ML regression predicting treatment half-life multipliers."""

    def __init__(self):
        # Weight parameters for the regression
        self.w_temp = 0.04       # Higher temperature accelerates chemical breakdown (hydrolysis/volatilization)
        self.w_uv = 0.05         # Higher solar radiation (UV) accelerates photolysis
        self.w_canopy = -0.03    # Dense canopy shades lower leaves, protecting chemicals from UV breakdown
        self.intercept = 1.0

    def predict_half_life_multiplier(
        self,
        avg_temp: float,
        solar_rad_proxy: float,
        canopy_cover_lai: float
    ) -> float:
        """Predict half-life multiplier based on environmental factors.
        
        Outputs multiplier typically in range [0.3, 1.5].
        """
        # Feature engineering (non-linear transforms)
        temp_feat = max(0.0, avg_temp - 20.0)  # Temp excess above 20C
        uv_feat = max(0.0, solar_rad_proxy)    # UV intensity proxy
        canopy_feat = min(5.0, canopy_cover_lai)  # Shading protection
        
        # Regression equation
        log_mult = (
            self.intercept
            - (self.w_temp * temp_feat)
            - (self.w_uv * uv_feat)
            - (self.w_canopy * canopy_feat)
        )
        # Exponentiate to ensure positive multiplier
        multiplier = math.exp(log_mult - 1.0)
        return max(0.1, min(3.0, multiplier))


# ── Simulated Random Forest Spray Drift Regressor ───────────────────────────

class SprayDriftRandomForestRegressor:
    """Simulated Random Forest Regressor predicting spray drift distance and neighboring deposition.
    
    Averages predictions from three simulated decision trees to estimate:
      - Max drift distance (meters)
      - Deposition percentage at a reference 10-meter boundary
    """
    
    def predict(
        self,
        wind_speed: float,
        temperature: float,
        relative_humidity: float,
        boom_height_m: float,
        droplet_size_vmd: float,
        travel_speed_kmh: float
    ) -> Dict[str, float]:
        """Runs the 3 simulated decision trees and returns predicted metrics."""
        
        # Tree 1: Focuses on physical trajectory (wind speed, boom height, travel speed)
        def tree_1() -> float:
            if wind_speed > 5.0:
                base = 15.0 * (wind_speed / 5.0)
            else:
                base = 4.0 * (wind_speed / 2.0)
            
            if boom_height_m > 0.6:
                base *= 1.4
            else:
                base *= 0.9
                
            if travel_speed_kmh > 14.0:
                base *= 1.2
            return base

        # Tree 2: Focuses on droplet evaporation (temperature, RH, initial droplet size)
        def tree_2() -> float:
            if droplet_size_vmd < 200.0:
                base = 20.0 * (200.0 / max(100.0, droplet_size_vmd))
            else:
                base = 5.0 * (250.0 / droplet_size_vmd)
                
            if relative_humidity < 40.0:
                base *= 1.5
            elif relative_humidity > 80.0:
                base *= 0.6
                
            if temperature > 28.0:
                base *= 1.3
            return base

        # Tree 3: Focuses on combined turbulent transport and droplet dynamics
        def tree_3() -> float:
            base = 6.0 * (wind_speed / 3.0) * (boom_height_m / 0.5)
            # Evaporation scale
            evap_scale = (temperature / 20.0) * (100.0 / max(10.0, relative_humidity))
            if evap_scale > 2.0:
                base *= 1.4
            return base

        # Average outputs
        drift_distance_m = (tree_1() + tree_2() + tree_3()) / 3.0
        drift_distance_m = max(0.5, min(100.0, drift_distance_m))
        
        # Cauchy/Exponential drop-off kernel for deposition percentage at 10m off-target
        deposition_pct = 100.0 * math.exp(-10.0 / max(1.0, drift_distance_m))
        deposition_pct = round(max(0.0, min(99.0, deposition_pct)), 2)
        
        return {
            "drift_distance_m": round(drift_distance_m, 2),
            "neighborhood_deposition_pct": deposition_pct
        }


# ── Main Chemical Engine Runner ───────────────────────────────────────────

def run_chemical_engine(
    ts: List[Dict[str, Any]],
    veg_output: Any,
    decision_output: Any,
    plot_context: Dict[str, Any],
    biophys_res: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Calculate systemic/contact translocation kinetics, wash-off, and spray drift.
    
    Parameters
    ----------
    ts              : historical daily weather timeseries
    veg_output      : L2 VegIntOutput (for LAI / NDVI)
    decision_output : L3 DecisionOutput (for water stress / soil moisture)
    plot_context    : context containing chemical application records
    biophys_res     : Optional biophysical engine results containing transpiration rate
    """
    # 1. Retrieve application logs from plot_context
    applied = plot_context.get("applied_chemicals")
    if not applied:
        applied = []
        
    # 2. Extract current environmental features
    rain_rolling_7d = sum(float(r.get("rain", 0.0) or 0.0) for r in ts[-7:]) if ts else 0.0
    tmean_rolling_7d = (sum(float(r.get("tmean", 20.0) or 20.0) for r in ts[-7:]) / len(ts[-7:])) if ts else 20.0
    
    # Estimate Solar Radiation (UV proxy)
    tmax_7d = max((float(r.get("tmax", 25.0) or 25.0) for r in ts[-7:]), default=25.0)
    tmin_7d = min((float(r.get("tmin", 15.0) or 15.0) for r in ts[-7:]), default=15.0)
    solar_rad_proxy = max(5.0, tmax_7d - tmin_7d + (tmean_rolling_7d / 10.0))
    
    # Extract Leaf Area Index (LAI)
    lai = 1.5
    if veg_output:
        if hasattr(veg_output, "lai"):
            lai = getattr(veg_output, "lai") or 1.5
        elif hasattr(veg_output, "ndvi_mean"):
            ndvi = getattr(veg_output, "ndvi_mean") or 0.5
            lai = 5.0 * (ndvi ** 2)
            
    # Extract water stress probability from L3
    water_stress_prob = 0.0
    if decision_output and hasattr(decision_output, "diagnoses"):
        for d in decision_output.diagnoses:
            if hasattr(d, "problem_id") and d.problem_id == "WATER_STRESS":
                water_stress_prob = getattr(d, "probability", 0.0)

    # 3. Extract Transpiration rate (mm/hr) from Biophysical Engine or estimate it
    transpiration_rate = 0.15 # fallback standard transpiration rate (mm/hr)
    if biophys_res and "canopy_microclimate" in biophys_res:
        transpiration_rate = biophys_res["canopy_microclimate"].get("transpiration_rate_mm_hr", 0.15)
    else:
        # Simple estimate: increases with LAI and solar, decreases with water stress
        transpiration_rate = 0.1 * lai * (solar_rad_proxy / 10.0) * (1.0 - 0.8 * water_stress_prob)
    transpiration_rate = max(0.01, transpiration_rate)

    # 4. Calculate degradation kinetics for each applied chemical
    predictor = ChemicalDegradationPredictor()
    hl_multiplier = predictor.predict_half_life_multiplier(tmean_rolling_7d, solar_rad_proxy, lai)
    
    cpfs: Dict[ThreatClass, float] = {
        ThreatClass.DISEASE: 0.0,
        ThreatClass.INSECT: 0.0,
        ThreatClass.WEED: 0.0
    }
    
    applied_status = []
    
    # Check for general spray constraints (e.g. adjuvant presence)
    constraints = plot_context.get("constraints", {})
    general_adjuvant = (
        constraints.get("adjuvant") or 
        constraints.get("surfactant") or 
        constraints.get("sticker") or 
        constraints.get("wetting_agent")
    )
    
    for app in applied:
        chem_id = app.get("chemical_id", "").lower().strip()
        days_ago = float(app.get("applied_days_ago", 0))
        
        spec = CHEMICAL_REGISTRY.get(chem_id)
        if not spec:
            continue
            
        # Adjust half-life based on environmental predictor
        adjusted_half_life = spec.half_life_days_ref * hl_multiplier
        
        # Time-based decay
        time_decay = math.exp(-days_ago / (adjusted_half_life / math.log(2.0)))
        
        # UV Solar Photolysis Degradation (Katagi, 2004)
        # UV intensity scale is proportional to solar radiation proxy and shaded exponentially by LAI
        k_photo = spec.photolysis_sensitivity * (solar_rad_proxy / 15.0) * math.exp(-0.4 * lai)
        uv_decay = math.exp(-k_photo * days_ago)
        
        # Check adjuvant presence in this application or generally
        app_adjuvant = app.get("adjuvant") or app.get("surfactant") or app.get("sticker")
        adjuvant_active = bool(general_adjuvant or app_adjuvant)
        
        # Wash-off threshold modification (adjuvant increases rain-fastness by 2.2x)
        wash_off_threshold = spec.wash_off_threshold_mm
        if adjuvant_active:
            wash_off_threshold *= 2.2
            
        # Systemic Translocation Kinetics (Bromilow & Chamberlain, 1995)
        # Systemic chemicals move from the leaf surface into vascular tissues driven by transpiration.
        # Translocation rate constant is coupled to transpiration.
        if spec.translocation == "SYSTEMIC":
            k_trans = 0.05 * transpiration_rate * (1.0 - 0.7 * water_stress_prob)
            translocated_fraction = 1.0 - math.exp(-k_trans * days_ago)
        else:
            translocated_fraction = 0.0
            
        surface_fraction = 1.0 - translocated_fraction
        
        # Surface residues are fully exposed to rain wash-off, whereas translocated residues are protected.
        wash_off_factor = math.exp(-rain_rolling_7d / wash_off_threshold)
        
        # Combine vascular protection and surface residues
        active_pct = (translocated_fraction + surface_fraction * wash_off_factor) * time_decay * uv_decay
        active_pct = max(0.0, min(1.0, active_pct))
        
        # Efficacy contribution
        efficacy = spec.base_efficacy * active_pct
        
        # Map chemical class to threat class
        if spec.chemical_class == "FUNGICIDE":
            cpfs[ThreatClass.DISEASE] = max(cpfs[ThreatClass.DISEASE], efficacy)
        elif spec.chemical_class == "INSECTICIDE":
            cpfs[ThreatClass.INSECT] = max(cpfs[ThreatClass.INSECT], efficacy)
        elif spec.chemical_class == "HERBICIDE":
            cpfs[ThreatClass.WEED] = max(cpfs[ThreatClass.WEED], efficacy)
            
        applied_status.append({
            "chemical_id": chem_id,
            "days_ago": days_ago,
            "half_life_ref": spec.half_life_days_ref,
            "half_life_adjusted": round(adjusted_half_life, 2),
            "translocated_fraction": round(translocated_fraction * 100, 1),
            "wash_off_pct": round((1.0 - wash_off_factor) * 100, 1),
            "remaining_active_pct": round(active_pct * 100, 1),
            "efficacy": round(efficacy, 3),
            "adjuvant_active": adjuvant_active
        })
        
    # 5. Calculate Spray Drift Risk using simulated Random Forest Regressor
    # Retrieve current weather conditions
    current_wind = 2.0
    current_temp = 20.0
    current_rh = 70.0
    if ts:
        latest = ts[-1]
        current_wind = float(latest.get("wind_speed") or latest.get("wind") or 2.0)
        current_temp = float(latest.get("tmean") if latest.get("tmean") is not None else 20.0)
        current_rh = float(latest.get("humidity") or latest.get("rh") or 70.0)
        
    # Retrieve spray nozzle constraints
    boom_height = float(constraints.get("boom_height_m", 0.5))
    droplet_size = float(constraints.get("droplet_size_vmd", 250.0))
    travel_speed = float(constraints.get("travel_speed_kmh", 12.0))
    
    rf_drift = SprayDriftRandomForestRegressor()
    drift_metrics = rf_drift.predict(
        wind_speed=current_wind,
        temperature=current_temp,
        relative_humidity=current_rh,
        boom_height_m=boom_height,
        droplet_size_vmd=droplet_size,
        travel_speed_kmh=travel_speed
    )
    
    # Scale spray drift risk to index in [0, 1]
    # Dangerous if drift distance is high
    spray_drift_risk = min(1.0, drift_metrics["drift_distance_m"] / 30.0)
    spray_drift_risk = round(max(0.05, spray_drift_risk), 3)
    
    # 6. Compile logit suppression delta for threat classes
    evidence_logits: Dict[ThreatClass, EvidenceLogit] = {}
    for tc, cpf in cpfs.items():
        if cpf > 0.05:
            logit_delta = -4.5 * cpf  # Up to -4.5 logit suppression for 100% active systemic efficacy
            driver = Driver.RAIN if tc == ThreatClass.DISEASE else Driver.TEMP
            
            evidence_logits[tc] = EvidenceLogit(
                driver=driver,
                condition=f"Chemical Protection Active: {tc.value}",
                logit_delta=round(logit_delta, 4),
                weight=1.0,
                source_refs={
                    "chemical_protection_factor": round(cpf, 4),
                    "environmental_half_life_multiplier": round(hl_multiplier, 4),
                    "applied_chemicals": applied_status,
                    "spray_drift_risk": spray_drift_risk,
                    "drift_distance_m": drift_metrics["drift_distance_m"],
                    "neighborhood_deposition_pct": drift_metrics["neighborhood_deposition_pct"]
                }
            )
            
    return {
        "chemical_protection_factors": {k.value: round(v, 4) for k, v in cpfs.items()},
        "applied_status": applied_status,
        "half_life_multiplier": round(hl_multiplier, 4),
        "spray_drift_risk": spray_drift_risk,
        "drift_distance_m": drift_metrics["drift_distance_m"],
        "neighborhood_deposition_pct": drift_metrics["neighborhood_deposition_pct"],
        "evidence_logits": evidence_logits
    }
