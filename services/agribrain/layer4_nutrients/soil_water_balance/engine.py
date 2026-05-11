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
  - Saxton & Rawls PTF (2006): texture -> hydraulic parameters
  - Deep percolation -> N leaching estimate (Addiscott model)
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
    """Saturation volumetric water content."""
    theta_fc = saxton_rawls_theta_fc(clay, sand, om)
    theta_s = theta_fc + (0.636 * (sand / 100.0) - 0.107)
    # Ensure saturation > FC
    return max(theta_fc + 0.05, min(0.60, theta_s + 0.30))


# ============================================================================
# FAO-56 Dual Crop Coefficient Curves
# ============================================================================

# Kcb (basal) by crop × phenology stage
# From FAO-56 Table 12 and local calibration
KCB_TABLE = {
    "corn":     {"initial": 0.15, "vegetative": 0.50, "reproductive": 1.15, "maturity": 0.50, "senescence": 0.15},
    "wheat":    {"initial": 0.15, "vegetative": 0.50, "reproductive": 1.10, "maturity": 0.25, "senescence": 0.15},
    "soybean":  {"initial": 0.15, "vegetative": 0.50, "reproductive": 1.10, "maturity": 0.30, "senescence": 0.15},
    "rice":     {"initial": 1.00, "vegetative": 1.10, "reproductive": 1.15, "maturity": 0.90, "senescence": 0.60},
    "cotton":   {"initial": 0.15, "vegetative": 0.45, "reproductive": 1.10, "maturity": 0.50, "senescence": 0.15},
    "barley":   {"initial": 0.15, "vegetative": 0.50, "reproductive": 1.05, "maturity": 0.25, "senescence": 0.15},
    "potato":   {"initial": 0.15, "vegetative": 0.50, "reproductive": 1.05, "maturity": 0.70, "senescence": 0.15},
    "sorghum":  {"initial": 0.15, "vegetative": 0.50, "reproductive": 1.05, "maturity": 0.40, "senescence": 0.15},
    "alfalfa":  {"initial": 0.30, "vegetative": 0.90, "reproductive": 1.15, "maturity": 1.10, "senescence": 0.30},
    "canola":   {"initial": 0.15, "vegetative": 0.50, "reproductive": 1.05, "maturity": 0.25, "senescence": 0.15},
    "sunflower": {"initial": 0.15, "vegetative": 0.50, "reproductive": 1.00, "maturity": 0.35, "senescence": 0.15},
}


def get_kcb(crop_type: str, stage: str) -> float:
    """Get basal crop coefficient for crop type and phenology stage."""
    crop_lower = crop_type.lower()
    stage_lower = stage.lower()
    crop_kcb = KCB_TABLE.get(crop_lower, KCB_TABLE.get("corn", {}))
    return crop_kcb.get(stage_lower, 0.50)


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
    ) -> SoilWaterBalanceOutput:
        """Run the FAO-56 daily water balance.

        Args:
            daily_weather: List of {et0, rain_mm, t_max} per day
            crop_type: Crop name for Kc lookup
            stages: Phenology stage per day
            soil_props: {clay_pct, sand_pct, organic_matter_pct} from user
            irrigation_events: List of {day, amount_mm} from user
            root_depth_mm: Effective root zone depth
        """
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
        theta_curr_mm = fc_mm * 0.7 + wp_mm * 0.3  # Start at 70% FC

        daily_stress = []
        daily_leaching = []
        total_drainage = 0.0
        total_deep_perc = 0.0
        total_eff_precip = 0.0

        for day_idx, wx in enumerate(daily_weather):
            et0 = wx.get("et0", 4.0)
            rain = wx.get("rain_mm", 0.0)
            irr = irr_schedule.get(day_idx, 0.0)

            # Stage-aware Kc
            stage = "vegetative"
            if stages and day_idx < len(stages):
                stage = stages[day_idx]
            kcb = get_kcb(crop_type, stage)
            ke = 0.10 if rain > 2.0 or irr > 0 else 0.05  # Soil evaporation component
            kc = kcb + ke
            etc = et0 * kc

            # Effective precipitation (USDA SCS method simplified)
            if rain <= 0:
                p_eff = 0.0
            elif rain <= 25:
                p_eff = rain * 0.9
            elif rain <= 75:
                p_eff = rain * 0.8
            else:
                p_eff = rain * 0.6
            total_eff_precip += p_eff

            # Water balance
            inflow = p_eff + irr
            outflow = etc
            theta_next = theta_curr_mm + inflow - outflow

            # Drainage (excess above FC)
            drainage = 0.0
            if theta_next > fc_mm:
                drainage = theta_next - fc_mm
                theta_next = fc_mm
            total_drainage += drainage

            # Deep percolation (drainage below root zone)
            deep_perc = drainage * 0.7  # ~70% of excess drains deep
            total_deep_perc += deep_perc

            # Leaching risk
            l_risk = 0.0
            if drainage > 5.0:
                l_risk = min(1.0, 0.3 + drainage / 30.0)
            daily_leaching.append(l_risk)

            # Water stress factor (Ks)
            paw = max(0, theta_next - wp_mm)
            ks = 1.0
            threshold = taw_mm * 0.5
            if paw < threshold and threshold > 0:
                ks = paw / threshold
            wsi = 1.0 - ks
            daily_stress.append(wsi)

            # Floor at wilting point
            theta_next = max(wp_mm, theta_next)
            theta_curr_mm = theta_next

        # 3. Aggregate
        window = min(n_days, 14) if n_days > 0 else 1
        recent_stress = sum(daily_stress[-window:]) / window if daily_stress else 0.0
        recent_leaching = max(daily_leaching[-window:]) if daily_leaching else 0.0

        # N leaching estimate (Addiscott simplified: 20 mg/L NO3-N in drainage)
        n_leaching = total_deep_perc * 0.020  # 20 mg/L * mm → kg/ha

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
        )
