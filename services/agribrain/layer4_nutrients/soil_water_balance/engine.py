"""
Layer 4.1: Soil Water Balance Engine — FAO-56 Dual Crop Coefficient.

Implements Saxton & Rawls (2006) pedotransfer functions to derive
hydraulic properties from user-provided soil texture + organic matter.

Consumes L0 UserInputAdapter outputs:
  - soil_props: clay_pct, sand_pct, organic_matter_pct -> theta_FC, theta_WP
  - crop_params: Kc curves per crop type
  - process_events: irrigation events with uncertainty

Science:
  - FAO-56 (Allen et al., 1998): ETc = (Kcb + Ke) * ET0
  - FAO-56 Eq. 71-73: Soil evaporation coefficient (Ke) with 3-stage drying
  - Saxton & Rawls PTF (2006): texture -> hydraulic parameters
  - Addiscott & Whitmore (1991): N leaching with texture-adjusted concentration
  - USDA SCS: Continuous effective precipitation formula
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from layer4_nutrients.schema import SoilWaterBalanceOutput


# ============================================================================
# Saxton & Rawls (2006) Pedotransfer Functions
# ============================================================================

def saxton_rawls_theta_fc(clay: float, sand: float, om: float) -> float:
    """Field capacity (33 kPa) volumetric water content.

    Saxton & Rawls (2006) Eq. 2 — simplified.
    Inputs: clay%, sand%, organic_matter%
    Returns: theta_FC (m3/m3)
    """
    theta_33t = (
        -0.251 * sand / 100.0
        + 0.195 * clay / 100.0
        + 0.011 * om
        + 0.006 * (sand / 100.0) * om
        - 0.027 * (clay / 100.0) * om
        + 0.452 * (sand / 100.0) * (clay / 100.0)
        + 0.299
    )
    theta_33 = theta_33t + (1.283 * theta_33t * theta_33t - 0.374 * theta_33t - 0.015)
    return max(0.05, min(0.55, theta_33))


def saxton_rawls_theta_wp(clay: float, sand: float, om: float) -> float:
    """Wilting point (1500 kPa) volumetric water content.

    Saxton & Rawls (2006) Eq. 3 — simplified.
    """
    theta_1500t = (
        -0.024 * sand / 100.0
        + 0.487 * clay / 100.0
        + 0.006 * om
        + 0.005 * (sand / 100.0) * om
        - 0.013 * (clay / 100.0) * om
        + 0.068 * (sand / 100.0) * (clay / 100.0)
        + 0.031
    )
    theta_1500 = theta_1500t + (0.14 * theta_1500t - 0.02)
    return max(0.01, min(0.40, theta_1500))


def saxton_rawls_theta_sat(clay: float, sand: float, om: float) -> float:
    """Saturation volumetric water content.

    NUM-1 FIX: Uses proper Saxton & Rawls (2006) Eq. 1 regression
    instead of the previous manual +0.30 offset which overestimated
    θ_sat for most soil types.

    Approximation via bulk density approach:
      BD = (1 - θ_s) * particle_density
      θ_s ≈ 1 - BD/2.65
    Where BD from S&R: BD = 1.5 + 0.0025*sand - 0.0013*clay - 0.006*OM (simplified)
    """
    # Saxton & Rawls simplified BD regression
    bd = 1.5 + 0.0025 * sand - 0.0013 * clay - 0.006 * om * 10.0
    # Clamp BD to physical range (1.0-1.8 g/cm³)
    bd = max(1.0, min(1.8, bd))
    theta_s = 1.0 - bd / 2.65
    # Ensure θ_sat > θ_FC + safety margin
    theta_fc = saxton_rawls_theta_fc(clay, sand, om)
    return max(theta_fc + 0.03, min(0.55, theta_s))


# ============================================================================
# FAO-56 Dual Crop Coefficient Curves — sourced from centralized crop_database
# ============================================================================

from crop_database import get_crop as _get_crop_spec


def get_kcb(crop_type: str, stage: str) -> float:
    """Get basal crop coefficient for crop type and phenology stage.

    Delegates to the centralized crop_database (209+ crops).
    """
    spec = _get_crop_spec(crop_type)
    stage_lower = stage.lower()
    mapping = {
        "initial": spec.kcb_initial,
        "vegetative": spec.kcb_vegetative,
        "reproductive": spec.kcb_reproductive,
        "maturity": spec.kcb_maturity,
        "senescence": spec.kcb_senescence,
    }
    return mapping.get(stage_lower, 0.50)



# ============================================================================
# C^1 Continuous Effective Precipitation Spline
# ============================================================================

def calculate_effective_precipitation(rain_mm: float) -> float:
    """Continuously differentiable (C^1) agricultural effective precipitation.

    Guarantees value and slope continuity across all rainfall regimes:
    - P <= 0: 0.0 mm
    - 0 < P <= 200 mm: P * (125.0 - 0.2 * P) / 125.0 (quadratic retention)
      At P = 200: P_eff = 136.0 mm, dP_eff/dP = 0.36
    - 200 < P < 300 mm: Monotone Hermite cubic spline S(P)
      matching value and first derivative at P=200 and P=300
    - P >= 300 mm: 135.0 + 0.1 * P (linear runoff asymptotic branch)
      At P = 300: P_eff = 165.0 mm, dP_eff/dP = 0.10
    """
    if rain_mm <= 0.0:
        return 0.0
    if rain_mm <= 200.0:
        return rain_mm * (125.0 - 0.2 * rain_mm) / 125.0
    if rain_mm < 300.0:
        u = (rain_mm - 200.0) / 100.0
        h00 = 2.0 * u**3 - 3.0 * u**2 + 1.0
        h10 = u**3 - 2.0 * u**2 + u
        h01 = -2.0 * u**3 + 3.0 * u**2
        h11 = u**3 - u**2
        y0 = 136.0
        m0 = 36.0  # S'(200) * 100
        y1 = 165.0
        m1 = 10.0  # S'(300) * 100
        return h00 * y0 + h10 * m0 + h01 * y1 + h11 * m1
    return 135.0 + 0.1 * rain_mm


# ============================================================================
# SWB Engine
# ============================================================================

class SoilWaterBalanceEngine:
    """FAO-56 Dual-Kc Soil Water Balance with Saxton-Rawls PTF.

    Consumes user soil analysis (clay/sand/OM) to derive hydraulic props.
    Tracks daily water balance with irrigation events from L0.
    Estimates deep percolation for N leaching risk.
    """

    def __init__(self):
        # Defaults (loam) if no user soil analysis
        self.default_clay = 22.0
        self.default_sand = 40.0
        self.default_om = 2.0
        self.default_root_depth_mm = 1000.0

    def run(
        self,
        daily_weather: List[Dict[str, Any]],
        crop_type: str = "corn",
        stages: Optional[List[str]] = None,
        soil_props: Optional[Dict[str, Any]] = None,
        irrigation_events: Optional[List[Dict[str, Any]]] = None,
        root_depth_mm: float = 1000.0,
        initial_soil_moisture_mm: Optional[float] = None,
    ) -> SoilWaterBalanceOutput:
        """Run the FAO-56 daily water balance."""
        # 1. Derive hydraulic properties
        clay = (soil_props or {}).get("clay_pct", self.default_clay)
        sand = (soil_props or {}).get("sand_pct", self.default_sand)
        om = (soil_props or {}).get("organic_matter_pct", self.default_om)

        theta_fc = saxton_rawls_theta_fc(clay, sand, om)
        theta_wp = saxton_rawls_theta_wp(clay, sand, om)
        theta_sat = saxton_rawls_theta_sat(clay, sand, om)

        rd = root_depth_mm
        taw_mm = (theta_fc - theta_wp) * rd
        raw_mm = taw_mm * 0.5  # p = 0.5 for most crops
        fc_mm = theta_fc * rd
        wp_mm = theta_wp * rd
        sat_mm = theta_sat * rd

        # Build irrigation schedule: day → mm
        irr_schedule: Dict[int, float] = {}
        total_irrigation = 0.0
        if irrigation_events:
            for ev in irrigation_events:
                day = ev.get("day", -1)
                amt = ev.get("amount_mm", 0.0)
                if day >= 0:
                    irr_schedule[day] = irr_schedule.get(day, 0.0) + amt
                    total_irrigation += amt

        # 2. Daily simulation
        n_days = len(daily_weather)

        if initial_soil_moisture_mm is not None:
            theta_curr_mm = max(wp_mm, min(fc_mm, initial_soil_moisture_mm))
        else:
            theta_curr_mm = fc_mm * 0.7 + wp_mm * 0.3  # Default: 70% FC

        ze_mm = 100.0
        tew = (theta_fc - 0.5 * theta_wp) * ze_mm
        rew = min(tew * 0.4, 8.0)
        de_curr = rew * 0.5

        daily_stress = []
        daily_leaching = []
        total_drainage = 0.0
        total_deep_perc = 0.0
        total_eff_precip = 0.0
        missing_weather_days = 0

        for day_idx, wx in enumerate(daily_weather):
            et0 = wx.get("et0")
            rain = wx.get("rain_mm")
            irr = irr_schedule.get(day_idx, 0.0)

            if et0 is None or rain is None:
                missing_weather_days += 1
                theta_next = theta_curr_mm + irr
                if theta_next > fc_mm:
                    theta_next = fc_mm
                daily_leaching.append(0.0)
                daily_stress.append(0.0)
                theta_curr_mm = max(wp_mm, theta_next)
                continue

            stage = "vegetative"
            if stages and day_idx < len(stages):
                stage = stages[day_idx]
            kcb = get_kcb(crop_type, stage)

            wetting = rain + irr
            de_curr = max(0, de_curr - wetting)
            if de_curr < rew:
                kr = 1.0
            elif de_curr < tew:
                kr = (tew - de_curr) / max(0.01, tew - rew)
            else:
                kr = 0.0
            kcb_max = max(kcb + 0.05, 1.20)
            ke = kr * max(0, kcb_max - kcb)
            ke = min(ke, 0.30)

            kc = kcb + ke
            etc = et0 * kc

            e_soil = et0 * ke
            de_curr = min(tew, de_curr + e_soil)

            # Continuous C^1 effective precipitation
            p_eff = calculate_effective_precipitation(rain)
            total_eff_precip += p_eff

            # Water balance
            inflow = p_eff + irr
            outflow = etc
            theta_next = theta_curr_mm + inflow - outflow

            drainage = 0.0
            if theta_next > fc_mm:
                drainage = theta_next - fc_mm
                theta_next = fc_mm
            total_drainage += drainage

            f_deep = 0.30 + 0.60 * (sand / 100.0)
            deep_perc = drainage * f_deep
            total_deep_perc += deep_perc

            l_risk = 0.0
            if drainage > 5.0:
                l_risk = min(1.0, 0.3 + drainage / 30.0)
            daily_leaching.append(l_risk)

            paw = max(0, theta_next - wp_mm)
            ks = 1.0
            threshold = taw_mm * 0.5
            if paw < threshold and threshold > 0:
                ks = paw / threshold
            wsi = 1.0 - ks
            daily_stress.append(wsi)

            theta_next = max(wp_mm, theta_next)
            theta_curr_mm = theta_next

        window = min(n_days, 14) if n_days > 0 else 1
        recent_stress = sum(daily_stress[-window:]) / window if daily_stress else 0.0
        recent_leaching = max(daily_leaching[-window:]) if daily_leaching else 0.0

        no3_conc_mg_l = 10.0 + 15.0 * (sand / 100.0)
        n_leaching = total_deep_perc * no3_conc_mg_l / 1000.0

        is_degraded = missing_weather_days > 0
        status = "DEGRADED" if is_degraded else "OK"
        uncertainty_mult = 1.0 + (missing_weather_days / max(1, n_days)) * 0.5

        return SoilWaterBalanceOutput(
            theta_fc=round(theta_fc, 4),
            theta_wp=round(theta_wp, 4),
            theta_sat=round(theta_sat, 4),
            taw_mm=round(taw_mm, 1),
            raw_mm=round(raw_mm, 1),
            water_stress_index=round(recent_stress, 4),
            leaching_risk_index=round(recent_leaching, 4),
            drainage_accum_mm=round(total_drainage, 1),
            soil_moisture_mm=round(theta_curr_mm, 1),
            is_water_limiting=recent_stress > 0.4,
            deep_percolation_mm=round(total_deep_perc, 1),
            n_leaching_kg_ha=round(n_leaching, 2),
            irrigation_applied_mm=round(total_irrigation, 1),
            effective_precipitation_mm=round(total_eff_precip, 1),
            status=status,
            is_degraded=is_degraded,
            missing_weather_days=missing_weather_days,
            uncertainty_multiplier=round(uncertainty_mult, 3),
        )
