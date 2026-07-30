"""
Layer 5 Biophysical Engine — Canopy Microclimate & Spore Dispersal AI Model (v7.0)

Translates ambient weather into leaf-level canopy temperature, relative humidity, and transpiration.
Models wind shear-driven spore release and leaf resonant fluttering detachment.
Uses an iterative Canopy Energy Balance solver and Cauchy spatial dispersal kernels.

Scientific References:
1. Monteith, J. L., & Unsworth, M. H. (2013). Principles of Environmental Physics. Academic Press.
   - Foundation for leaf-level Canopy Energy Balance (Rn = H + LE).
2. Campbell, G. S., & Norman, J. M. (1998). An Introduction to Environmental Biophysics. Springer.
   - Provides equations for stomatal resistance, boundary layer resistance, and latent heat fluxes.
3. Aylor, D. E. (1990). The role of wind in dispersing fungal spores. Phytopathology, 80(3), 277-283.
   - Details aerodynamic drag and lift forces required for wind-shear spore release.
4. Grace, J. (1977). Plant Response to Wind. Academic Press.
   - Outlines resonant leaf fluttering frequency, amplitude, and mechanical acceleration forces under wind stress.
5. Mundt, C. C. (2020). Pyramiding genes for disease resistance. Annual Review of Phytopathology, 58, 25-45.
   - Standardizes spatial spore dispersal Cauchy kernels for localized plant epidemiology.
"""

from typing import Dict, List, Any, Optional
import math
from layer5_bio.schema import ThreatId, EvidenceLogit
from layer3_decision.schema import Driver

# ── Simulated AI Canopy Energy Balance Solver ──────────────────────────────

class BiophysicalCanopyEnergyBalanceSolver:
    """Iterative leaf-level energy balance solver calculating leaf temperature, fluxes, and transpiration.
    
    Solves:
      R_n = H + lambda_E
      
    Where:
      R_n = shortwave net + longwave net radiation
      H = sensible heat flux (density * cp * (T_leaf - T_air) / r_a)
      lambda_E = latent heat flux (density * cp * (e_s(T_leaf) - e_a) / (gamma * (r_a + r_s)))
    """
    
    def __init__(self):
        self.sigma = 5.67e-8       # Stefan-Boltzmann constant (W / m^2 K^4)
        self.epsilon_leaf = 0.97   # Leaf emissivity
        self.alpha_leaf = 0.23     # Leaf albedo
        self.rho_air = 1.2         # Air density (kg / m^3)
        self.cp_air = 1012.0       # Specific heat of air (J / kg K)
        self.gamma = 0.066         # Psychrometric constant (kPa / K)
        self.latent_heat = 2.45e6  # Latent heat of vaporization (J / kg)
        
    def _sat_vapor_pressure(self, temp: float) -> float:
        """Tetens equation for saturation vapor pressure in kPa."""
        return 0.61078 * math.exp((17.27 * temp) / (temp + 237.3))

    def solve(
        self,
        t_ambient: float,
        rh_ambient: float,
        wind_speed: float,
        lai: float,
        solar_rad: float,
        water_stress_prob: float
    ) -> Dict[str, float]:
        """Iteratively solves leaf temperature and returns microclimate parameters."""
        # 1. Boundary layer resistance r_a (s/m)
        u_clamped = max(0.1, wind_speed)
        r_a = 200.0 / math.sqrt(u_clamped) # Standard agricultural formula
        r_a = max(10.0, min(1000.0, r_a))
        
        # 2. Stomatal resistance r_s (s/m) (Campbell & Norman, 1998)
        r_s_min = 100.0 # Standard minimum stomatal resistance for well-watered C3 crop
        r_s = r_s_min / (1.0 - 0.95 * water_stress_prob)
        r_s = max(r_s_min, min(8000.0, r_s))
        
        # 3. Ambient vapor pressure e_a (kPa)
        e_sat_air = self._sat_vapor_pressure(t_ambient)
        e_a = e_sat_air * (rh_ambient / 100.0)
        
        # 4. Net shortwave radiation (intercepted by canopy top/shading)
        r_ns = (1.0 - self.alpha_leaf) * solar_rad * math.exp(-0.4 * max(0.1, lai))
        
        # 5. Iterative Newton-Raphson Solver for T_leaf
        t_leaf = t_ambient
        for _ in range(8): # 8 iterations is highly convergent
            e_sat_leaf = self._sat_vapor_pressure(t_leaf)
            
            # Net longwave radiation
            t_leaf_k = t_leaf + 273.15
            t_air_k = t_ambient + 273.15
            # Sky/ground radiation exchange
            r_nl = self.epsilon_leaf * self.sigma * (t_leaf_k**4 - t_air_k**4 * (0.56 + 0.08 * math.sqrt(e_a)))
            
            r_n = r_ns - r_nl
            
            # Sensible heat flux (H)
            h = self.rho_air * self.cp_air * (t_leaf - t_ambient) / r_a
            
            # Latent heat flux (lambda * E)
            le = (self.rho_air * self.cp_air / self.gamma) * (e_sat_leaf - e_a) / (r_a + r_s)
            
            # Residual f(T_leaf) = Rn - H - LE
            residual = r_n - h - le
            
            # Numerical derivative df/dT_leaf
            dt = 0.01
            e_sat_dt = self._sat_vapor_pressure(t_leaf + dt)
            r_nl_dt = self.epsilon_leaf * self.sigma * ((t_leaf + dt + 273.15)**4 - t_air_k**4 * (0.56 + 0.08 * math.sqrt(e_a)))
            r_n_dt = r_ns - r_nl_dt
            h_dt = self.rho_air * self.cp_air * (t_leaf + dt - t_ambient) / r_a
            le_dt = (self.rho_air * self.cp_air / self.gamma) * (e_sat_dt - e_a) / (r_a + r_s)
            
            residual_dt = r_n_dt - h_dt - le_dt
            df_dt = (residual_dt - residual) / dt
            
            if abs(df_dt) < 1e-5:
                break
            
            t_leaf_next = t_leaf - residual / df_dt
            # Clamp change to avoid divergence
            t_leaf = max(t_ambient - 10.0, min(t_ambient + 15.0, t_leaf_next))
            
        # Recompute final fluxes
        e_sat_leaf = self._sat_vapor_pressure(t_leaf)
        t_leaf_k = t_leaf + 273.15
        t_air_k = t_ambient + 273.15
        r_nl = self.epsilon_leaf * self.sigma * (t_leaf_k**4 - t_air_k**4 * (0.56 + 0.08 * math.sqrt(e_a)))
        r_n = r_ns - r_nl
        h = self.rho_air * self.cp_air * (t_leaf - t_ambient) / r_a
        le = (self.rho_air * self.cp_air / self.gamma) * (e_sat_leaf - e_a) / (r_a + r_s)
        le = max(0.0, le)
        
        # Calculate transpiration rate (mm/hr)
        transpiration_rate_mm_hr = (le / self.latent_heat) * 3600.0
        
        # Microclimate Relative Humidity inside canopy
        delta_rh = 15.0 * transpiration_rate_mm_hr / math.sqrt(u_clamped) * (lai / 1.5)
        rh_leaf = min(99.5, rh_ambient + delta_rh)
        
        # Calculate leaf dew point
        alpha = ((17.27 * t_leaf) / (t_leaf + 237.3)) + math.log(rh_leaf / 100.0)
        t_dew_leaf = (237.3 * alpha) / (17.27 - alpha)
        
        return {
            "t_leaf": round(t_leaf, 2),
            "rh_leaf": round(rh_leaf, 1),
            "t_dew_leaf": round(t_dew_leaf, 2),
            "transpiration_rate_mm_hr": round(transpiration_rate_mm_hr, 4),
            "sensible_heat_flux": round(h, 2),
            "latent_heat_flux": round(le, 2),
            "net_radiation": round(r_n, 2),
            "microclimate_rh_offset": round(rh_leaf - rh_ambient, 1),
            "microclimate_temp_offset": round(t_leaf - t_ambient, 2)
        }


# ── Main Biophysical Engine Runner ───────────────────────────────────────

def run_biophysical_engine(
    ts: List[Dict[str, Any]],
    veg_output: Any,
    decision_output: Any,
    plot_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute the biophysical canopy microclimate and spore dispersal calculations.
    
    Parameters
    ----------
    ts              : historical daily weather timeseries
    veg_output      : L2 VegIntOutput
    decision_output : L3 DecisionOutput (used to extract water stress probability)
    plot_context    : plot metadata
    """
    # 1. Sourcing inputs
    latest_record = ts[-1] if ts else {}
    t_ambient = float(latest_record.get("tmean", 20.0) or 20.0)
    rh_ambient = float(latest_record.get("humidity") or latest_record.get("rh", 70.0) or 70.0)
    wind_speed = float(latest_record.get("wind_speed") or latest_record.get("wind", 2.0) or 2.0)
    
    # Estimate solar radiation (W/m^2)
    tmax_7d = max((float(r.get("tmax", 25.0) or 25.0) for r in ts[-7:]), default=25.0)
    tmin_7d = min((float(r.get("tmin", 15.0) or 15.0) for r in ts[-7:]), default=15.0)
    solar_rad = max(100.0, 35.0 * (tmax_7d - tmin_7d) + 150.0) # Solar radiation proxy (W/m^2)

    # Extract LAI from L2
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
                
    # 2. Run canopy energy balance solver
    solver = BiophysicalCanopyEnergyBalanceSolver()
    microclimate = solver.solve(
        t_ambient=t_ambient,
        rh_ambient=rh_ambient,
        wind_speed=wind_speed,
        lai=lai,
        solar_rad=solar_rad,
        water_stress_prob=water_stress_prob
    )
    
    t_leaf = microclimate["t_leaf"]
    rh_leaf = microclimate["rh_leaf"]
    t_dew = microclimate["t_dew_leaf"]
    transpiration_rate = microclimate["transpiration_rate_mm_hr"]
    
    # 3. Model Leaf Wetness Duration (LWD)
    # Dew occurs if leaf temperature is at or below the dew point
    dew_occurring = t_leaf <= (t_dew + 0.5)
    rain_occurring = float(latest_record.get("rain", 0.0) or 0.0) > 0.1
    
    # Estimate daily leaf wetness hours from historical timeseries
    leaf_wetness_hours = 0.0
    for r in ts[-7:]:
        r_rain = float(r.get("rain", 0.0) or 0.0)
        r_rh = float(r.get("humidity") or r.get("rh", 70.0) or 70.0)
        r_wind = float(r.get("wind_speed") or r.get("wind", 2.0) or 2.0)
        
        # High RH overnight (>85%) or rain creates leaf wetness hours
        if r_rain > 1.0:
            leaf_wetness_hours += 8.0 # rainfall interception
        elif r_rh > 85.0:
            # Low wind allows condensation to build
            wet_hrs = 4.0 + (r_rh - 85.0) * 0.3 - min(2.0, r_wind)
            leaf_wetness_hours += max(0.0, wet_hrs)
            
    leaf_wetness_hours = round(max(0.0, min(24.0, leaf_wetness_hours)), 1)
    microclimate["leaf_wetness_hours"] = leaf_wetness_hours
    
    # 4. Spore Detachment model (Aerodynamic Drag vs Adhesion)
    # Adhesion increases with relative humidity due to surface tension / sticky mucilages
    f_adh_ref = 1.0 # normalized reference adhesion
    f_adh = f_adh_ref * (1.0 + 8.0 * ((rh_leaf / 100.0) ** 3))
    if dew_occurring or rain_occurring:
        f_adh *= 2.5 # wet film further binds spores by capillary force
        
    # Aerodynamic drag and lift forces scale with wind speed squared
    f_drag = 0.06 * (wind_speed ** 2)
    
    # Resonant leaf fluttering frequency & acceleration (Grace, 1977)
    # Wind makes leaves flutter, creating mechanical acceleration forces on spores
    flutter_amplitude = 0.05 * (wind_speed ** 1.5) / math.sqrt(max(0.5, lai))
    flutter_freq = min(15.0, 2.5 * wind_speed) # frequency in Hz
    omega = 2.0 * math.pi * flutter_freq
    flutter_accel = (omega ** 2) * flutter_amplitude # a = omega^2 * A
    
    # Mechanical resonance amplication in moderate wind range [3.0 - 7.0 m/s]
    resonance = 1.0
    if 3.0 <= wind_speed <= 7.0:
        resonance += 2.0 * math.exp(-((wind_speed - 5.0) / 1.5) ** 2)
        
    f_inertial = 0.003 * flutter_accel * resonance
    
    # Spore release probability based on total dislodging forces vs cell wall adhesion
    total_force = f_drag + f_inertial
    spore_release_logit = 2.0 * (total_force - f_adh)
    spore_release_prob = 1.0 / (1.0 + math.exp(-max(-10.0, min(10.0, spore_release_logit))))
    
    # 5. Spatial Spore Dispersal Kernel (Mundt, 2020)
    # Cauchy distribution modeling localized spore deposition
    # Scale parameter L (meters) is proportional to wind speed
    L_cauchy = 2.0 + 1.5 * wind_speed
    # Estimate percentage of spores deposited in neighboring zone (at 15m distance)
    neighbor_deposition_pct = 100.0 / (math.pi * L_cauchy * (1.0 + (15.0 / L_cauchy) ** 2))
    neighbor_deposition_pct = round(max(0.1, min(40.0, neighbor_deposition_pct)), 2)
    
    # 6. Compute biophysical risk logits for foliar diseases
    biophysical_logits: Dict[ThreatId, EvidenceLogit] = {}
    
    # Rust risk: favored by microclimate humidity (incubation) but released by wind
    rust_suitability = (rh_leaf / 100.0) * (1.0 - abs(t_leaf - 20.0) / 10.0)
    rust_suitability = max(0.0, rust_suitability)
    rust_logit = 2.0 * rust_suitability + 1.2 * spore_release_prob - 1.5
    biophysical_logits[ThreatId.FUNGAL_RUST] = EvidenceLogit(
        driver=Driver.TEMP,
        condition="Canopy Microclimate & Spore Dispersal: FUNGAL_RUST",
        logit_delta=round(rust_logit, 4),
        weight=0.9,
        source_refs={
            "t_leaf": t_leaf,
            "rh_leaf": rh_leaf,
            "spore_release_probability": round(spore_release_prob, 4),
            "canopy_microclimate_suitability": round(rust_suitability, 4),
            "neighbor_deposition_pct": neighbor_deposition_pct,
            "leaf_wetness_hours": leaf_wetness_hours
        }
    )
    
    # Powdery Mildew risk: dry canopy + moderate temp + wind dispersal
    pm_suitability = (1.0 - rh_leaf / 100.0) * (1.0 - abs(t_leaf - 21.0) / 7.0)
    pm_suitability = max(0.0, pm_suitability)
    pm_logit = 2.5 * pm_suitability + 1.5 * spore_release_prob - 1.8
    biophysical_logits[ThreatId.POWDERY_MILDEW] = EvidenceLogit(
        driver=Driver.TEMP,
        condition="Canopy Microclimate & Spore Dispersal: POWDERY_MILDEW",
        logit_delta=round(pm_logit, 4),
        weight=0.9,
        source_refs={
            "t_leaf": t_leaf,
            "rh_leaf": rh_leaf,
            "spore_release_probability": round(spore_release_prob, 4),
            "canopy_microclimate_suitability": round(pm_suitability, 4),
            "neighbor_deposition_pct": neighbor_deposition_pct,
            "leaf_wetness_hours": leaf_wetness_hours
        }
    )
    
    # Downy Mildew risk: wet canopy + moderate temp (no wind dispersal requirement)
    dm_suitability = (rh_leaf / 100.0) * (1.0 - abs(t_leaf - 18.0) / 8.0)
    dm_suitability = max(0.0, dm_suitability)
    dm_logit = 3.2 * dm_suitability - 1.4
    biophysical_logits[ThreatId.DOWNY_MILDEW] = EvidenceLogit(
        driver=Driver.RAIN,
        condition="Canopy Microclimate & Spore Dispersal: DOWNY_MILDEW",
        logit_delta=round(dm_logit, 4),
        weight=0.9,
        source_refs={
            "t_leaf": t_leaf,
            "rh_leaf": rh_leaf,
            "spore_release_probability": 0.0,
            "canopy_microclimate_suitability": round(dm_suitability, 4),
            "leaf_wetness_hours": leaf_wetness_hours
        }
    )
    
    return {
        "canopy_microclimate": microclimate,
        "spore_release_probability": round(spore_release_prob, 4),
        "biophysical_logits": biophysical_logits
    }
