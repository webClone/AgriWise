"""
VPD Spray Window Engine — 3D Lagrangian Droplet Evaporation & Drift Solver (v7.0)

Simulates 3D Lagrangian flight trajectories for agricultural spray droplets:
  m * d2x/dt2 = F_drag + F_gravity + F_buoyancy
under a logarithmic wind velocity profile, incorporating droplet evaporation driven by VPD.
"""

from typing import Any, Dict, List
import math
from layer6_exec.schema import Layer6Input, InterventionCandidate, InterventionDomain, FeasibilityGrade

def safe_getattr(obj: Any, attr: str, default: Any) -> Any:
    if obj is None:
        return default
    val = getattr(obj, attr, default)
    if val is None:
        return default
    if hasattr(val, "__class__") and ("mock" in val.__class__.__name__.lower()):
        return default
    return val

def run_vpd_spray_window(inputs: Layer6Input, candidates: List[InterventionCandidate]) -> Dict[str, float]:
    # 1. Ingest L1 Air Temp, RH, Wind Speed, and Wind Direction
    temp = 20.0        # °C
    rh = 60.0          # %
    wind_speed = 3.0   # m/s
    wind_dir = 180.0   # degrees (from North)
    
    if inputs.tensor:
        ts = safe_getattr(inputs.tensor, "plot_timeseries", []) or []
        if ts:
            last = ts[-1]
            if isinstance(last, dict):
                temp = float(last.get("temp") if last.get("temp") is not None else temp)
                rh = float(last.get("humidity") if last.get("humidity") is not None else rh)
                wind_speed = float(last.get("wind_speed") if last.get("wind_speed") is not None else wind_speed)
                wind_dir = float(last.get("wind_dir") if last.get("wind_dir") is not None else wind_dir)

    # Calculate VPD (Vapor Pressure Deficit) in kPa
    # Tetens equation for saturation vapor pressure
    e_sat = 0.61078 * math.exp((17.27 * temp) / (temp + 237.3))  # kPa
    e_act = e_sat * (rh / 100.0)
    vpd = max(0.01, e_sat - e_act)

    # 2. Ingest L2 Canopy Cover
    canopy_cover = 50.0  # %
    if inputs.veg_int:
        canopy_cover = safe_getattr(inputs.veg_int, "canopy_cover_pct", 50.0)

    # 3. 3D Lagrangian Droplet Simulation
    # Physical Constants
    g = 9.81           # m/s^2
    rho_w = 1000.0     # kg/m^3 (water density)
    rho_a = 1.2        # kg/m^3 (air density)
    mu_a = 1.8e-5      # Pa s (dynamic viscosity of air)
    
    # Simulation settings
    dt = 0.005         # Time step (seconds)
    z_spray = 1.5      # Spray height (meters)
    z0 = 0.05          # Soil/canopy roughness length (meters)
    z_ref = 2.0        # Reference wind height (meters)
    
    # Friction velocity for logarithmic wind profile
    # u(z) = u_star / k * ln(z/z0) => u_star = u(z_ref) * k / ln(z_ref/z0)
    k_vk = 0.4         # von Karman constant
    if wind_speed < 0.1:
        u_star = 0.0
    else:
        u_star = wind_speed * k_vk / math.log(z_ref / z0)
        
    # Wind vector components (meteorological wind direction -> direction wind is blowing to)
    wind_rad = math.radians(wind_dir + 180.0)
    wind_dx = math.sin(wind_rad)
    wind_dy = math.cos(wind_rad)
    
    # Evaporation rate constant (increases with temperature and VPD)
    # d(D_p^2)/dt = -lambda_evap * VPD
    lambda_evap = 1e-10 * (1.0 + 0.05 * temp) * vpd  # m^2/s/kPa
    
    # We run trajectories for a spectrum of droplet sizes (100, 200, 300, 400 microns)
    droplet_sizes = [100e-6, 200e-6, 300e-6, 400e-6]  # meters
    droplet_weights = [0.1, 0.4, 0.3, 0.2]  # Volume fraction
    
    total_drift_fraction = 0.0
    total_evap_fraction = 0.0
    total_interception_fraction = 0.0
    
    for d0, weight in zip(droplet_sizes, droplet_weights):
        # Droplet state: positions (x, y, z) and velocities (vx, vy, vz)
        x, y, z = 0.0, 0.0, z_spray
        
        # Spray initial velocity: tractor speed = 4.0 m/s in x, downward spray = -12.0 m/s in z
        vx, vy, vz = 4.0, 0.0, -12.0
        
        d = d0
        t = 0.0
        max_time = 10.0  # safety timeout (seconds)
        
        while z > 0.0 and d > 10e-6 and t < max_time:
            # 1. Logarithmic Wind speed at height z
            if z > z0:
                u_z = (u_star / k_vk) * math.log(z / z0)
            else:
                u_z = 0.0
            
            w_x = u_z * wind_dx
            w_y = u_z * wind_dy
            
            # Relative velocity
            v_rel_x = vx - w_x
            v_rel_y = vy - w_y
            v_rel_z = vz
            v_rel = math.sqrt(v_rel_x**2 + v_rel_y**2 + v_rel_z**2)
            
            # Droplet properties
            vol = (math.pi / 6.0) * (d**3)
            mass = rho_w * vol
            area = (math.pi / 4.0) * (d**2)
            
            # Drag coefficient Cd using Schiller-Naumann correlation for spheres
            re = rho_a * v_rel * d / mu_a
            if re < 0.1:
                Cd = 24.0 / max(re, 1e-6)
            else:
                Cd = (24.0 / re) * (1.0 + 0.15 * (re**0.687))
            
            # Forces
            # Drag
            Fd_x = -0.5 * Cd * rho_a * area * v_rel * v_rel_x
            Fd_y = -0.5 * Cd * rho_a * area * v_rel * v_rel_y
            Fd_z = -0.5 * Cd * rho_a * area * v_rel * v_rel_z
            
            # Gravity & Buoyancy
            Fg_z = -mass * g
            Fb_z = rho_a * vol * g
            
            # Acceleration
            ax = Fd_x / mass
            ay = Fd_y / mass
            az = (Fd_z + Fg_z + Fb_z) / mass
            
            # Update velocities
            vx += ax * dt
            vy += ay * dt
            vz += az * dt
            
            # Update positions
            x += vx * dt
            y += vy * dt
            z += vz * dt
            
            # Evaporation: update diameter
            # d(D^2) = -lambda * VPD * dt => D_new = sqrt(D_old^2 - lambda * VPD * dt)
            d_sq = max(0.0, d**2 - lambda_evap * dt)
            d = math.sqrt(d_sq)
            
            t += dt

        # Determine outcome of this droplet size class
        horizontal_drift = math.sqrt(x**2 + y**2)
        
        if d <= 10e-6:
            # Droplet evaporated completely
            total_evap_fraction += weight
        else:
            # Droplet reached ground/canopy boundary
            if horizontal_drift > 5.0:  # consider drift if horizontal movement > 5 meters
                total_drift_fraction += weight
            else:
                # Interception by canopy
                interception_prob = canopy_cover / 100.0
                total_interception_fraction += weight * interception_prob

    # 4. Mutate Spray Candidates
    # If drift fraction is high (> 30%) or VPD is extremely high (> 2.0 kPa), penalize
    # PHYTOSANITARY interventions (e.g. chemical spraying) or shift optimal timing.
    for c in candidates:
        if c.domain == InterventionDomain.PHYTOSANITARY and "spray" in c.title.lower():
            if total_drift_fraction > 0.25 or vpd > 2.0:
                penalty = max(0.2, 1.0 - (total_drift_fraction * 0.8 + (vpd - 1.0) * 0.2))
                c.utility_score = round(c.utility_score * penalty, 3)
                c.expected_impact = round(c.expected_impact * penalty, 3)
                c.evidence_summary += (
                    f" [Drift fraction calculated at {total_drift_fraction:.2%} (VPD={vpd:.2f} kPa, wind={wind_speed:.1f} m/s). "
                    f"Spraying efficiency downgraded to prevent environmental cross-contamination.]"
                )
                if total_drift_fraction > 0.4:
                    c.feasibility_grade = FeasibilityGrade.C
                    c.blocked_reasons.append("High drift risk. Consider nozzle modification or rescheduling.")
            else:
                c.evidence_summary += f" [Ideal spraying conditions: drift risk is {total_drift_fraction:.1%}, VPD is {vpd:.2f} kPa.]"

    return {
        "vapor_pressure_deficit_kpa": round(vpd, 4),
        "total_drift_fraction": round(total_drift_fraction, 4),
        "total_evap_fraction": round(total_evap_fraction, 4)
    }
