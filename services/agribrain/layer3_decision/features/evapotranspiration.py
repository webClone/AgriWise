"""
Surface Energy Balance & Evapotranspiration Module.

Fuses FAO-56 Penman-Monteith (ET0 x Kc) with satellite-derived
Land Surface Temperature (LST) to compute real evaporative stress.

The Old Science:  ET0 * Kc = "how much water should be there" (accounting)
The New Science:  LST - T_air = "the plant is overheating" (physics)

Key outputs:
  - ESI  (Evaporative Stress Index): 1 - ET_actual/ET_potential  [0=healthy, 1=shutdown]
  - CWSI (Crop Water Stress Index): canopy-air temperature differential
  - ET deficit: gap between potential and actual evapotranspiration

Data flow: L0 (Landsat/ECOSTRESS thermal) -> L1 (environment evidence) ->
           L2 (stress interpretation) -> L3 (this module, via feature builder)

Deterministic. Same inputs -> identical outputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# ============================================================================
# Constants (FAO-56 Table 2, Allen et al. 1998)
# ============================================================================

# Psychrometric constant (kPa/°C) at sea level
GAMMA = 0.0665

# Stefan-Boltzmann constant (MJ m-2 day-1 K-4)
SIGMA = 4.903e-9

# Dry-air baseline: canopy-air delta when stomata are fully closed
# This is crop-dependent; typical C3/C4 range is 10-15°C
DELTA_DRY_DEFAULT = 12.0  # °C

# Wet-air baseline: canopy-air delta when transpiration is maximal
# (well-watered crop, stomata fully open)
DELTA_WET_DEFAULT = -2.0  # °C


# ============================================================================
# Output dataclass
# ============================================================================

@dataclass
class WaterBudget:
    """Fused water balance from FAO-56 + Surface Energy Balance.

    et_potential_mm:         FAO-56 ET0 * Kc (what the crop should use)
    et_actual_mm:            Energy-balance adjusted actual ET
    esi:                     Evaporative Stress Index [0.0 = no stress, 1.0 = total shutdown]
    cwsi:                    Crop Water Stress Index [0.0 = well-watered, 1.0 = fully stressed]
    canopy_air_delta_c:      T_canopy - T_air (°C). Positive = plant overheating
    transpiration_efficiency: Fraction of potential transpiration achieved [0-1]
    deficit_mm:              et_potential - et_actual (water gap)
    confidence:              Signal quality [0-1]
    method:                  Computation method used
    """
    et_potential_mm: float = 0.0
    et_actual_mm: float = 0.0
    esi: float = 0.0
    cwsi: float = 0.0
    canopy_air_delta_c: float = 0.0
    transpiration_efficiency: float = 1.0
    deficit_mm: float = 0.0
    confidence: float = 0.5
    method: str = "fao56_only"


# ============================================================================
# Core computation
# ============================================================================

def compute_water_budget(
    et0_mm: Optional[float] = None,
    kc: float = 1.0,
    lst_canopy_c: Optional[float] = None,
    t_air_c: Optional[float] = None,
    vpd_kpa: Optional[float] = None,
    ndvi: Optional[float] = None,
    wind_speed_ms: Optional[float] = None,
    delta_dry: float = DELTA_DRY_DEFAULT,
    delta_wet: float = DELTA_WET_DEFAULT,
) -> WaterBudget:
    """Compute fused water budget from FAO-56 and satellite LST.

    Args:
        et0_mm:         Reference evapotranspiration (FAO-56 Penman-Monteith, mm/day)
        kc:             Crop coefficient for current growth stage
        lst_canopy_c:   Land Surface Temperature from satellite (°C)
        t_air_c:        Ambient air temperature (°C)
        vpd_kpa:        Vapor Pressure Deficit (kPa)
        ndvi:           Current NDVI (for fractional cover correction)
        wind_speed_ms:  Wind speed at 2m (m/s)
        delta_dry:      Dry-air baseline for CWSI (°C)
        delta_wet:      Wet-air baseline for CWSI (°C)

    Returns:
        WaterBudget with fused estimates.
    """
    # --- 1. FAO-56 baseline: ET_potential = ET0 * Kc ---
    et_potential = (et0_mm or 0.0) * max(0.0, min(2.0, kc))

    has_lst = (
        lst_canopy_c is not None
        and t_air_c is not None
        and lst_canopy_c == lst_canopy_c  # not NaN
        and t_air_c == t_air_c
    )

    if not has_lst:
        # ── FAO-56 only path ──
        # Without LST, we can only estimate stress from VPD as a proxy
        esi_proxy = _estimate_esi_from_vpd(vpd_kpa, ndvi) if vpd_kpa is not None else 0.0
        et_actual = et_potential * (1.0 - esi_proxy)
        deficit = max(0.0, et_potential - et_actual)

        return WaterBudget(
            et_potential_mm=round(et_potential, 3),
            et_actual_mm=round(et_actual, 3),
            esi=round(esi_proxy, 4),
            cwsi=0.0,
            canopy_air_delta_c=0.0,
            transpiration_efficiency=round(1.0 - esi_proxy, 4),
            deficit_mm=round(deficit, 3),
            confidence=0.35 if vpd_kpa is not None else 0.20,
            method="fao56_only",
        )

    # ── Energy Balance path (with satellite LST) ──

    # --- 2. Canopy-air temperature differential ---
    canopy_air_delta = lst_canopy_c - t_air_c

    # --- 3. CWSI (Crop Water Stress Index) ---
    # Jackson et al., 1981: CWSI = (Tc-Ta-Δwet) / (Δdry-Δwet)
    # Adjust dry baseline by VPD if available
    effective_delta_dry = delta_dry
    effective_delta_wet = delta_wet
    if vpd_kpa is not None and vpd_kpa > 0:
        # VPD correction: higher VPD → higher dry baseline
        # Empirical: Δdry ≈ base + 1.5 * VPD (Idso, 1982)
        effective_delta_dry = delta_dry + 1.5 * min(vpd_kpa, 5.0)
        # Wet baseline shifts slightly with VPD
        effective_delta_wet = delta_wet - 0.5 * min(vpd_kpa, 3.0)

    denom = effective_delta_dry - effective_delta_wet
    if abs(denom) < 0.01:
        denom = 0.01  # Prevent division by zero

    cwsi_raw = (canopy_air_delta - effective_delta_wet) / denom
    cwsi = max(0.0, min(1.0, cwsi_raw))

    # --- 4. LST-derived actual ET ---
    # ET_actual = ET_potential * (1 - CWSI)
    # When CWSI=0, plant is fully transpiring (ET_actual = ET_potential)
    # When CWSI=1, stomata are closed (ET_actual ≈ 0)
    et_actual_lst = et_potential * (1.0 - cwsi)

    # --- 5. Fractional cover correction ---
    # Bare soil contributes to LST but not transpiration
    fc = _fractional_cover(ndvi) if ndvi is not None else 0.8
    if fc < 0.3:
        # Low canopy cover: LST is dominated by soil, reduce weight
        lst_weight = max(0.2, fc)
    else:
        lst_weight = min(0.85, 0.5 + fc * 0.5)

    # --- 6. Fusion: weighted average of FAO-56 and LST estimates ---
    fao_weight = 1.0 - lst_weight
    et_actual_fused = fao_weight * et_potential + lst_weight * et_actual_lst

    # --- 7. ESI = 1 - ET_actual / ET_potential ---
    if et_potential > 0.01:
        esi = max(0.0, min(1.0, 1.0 - (et_actual_fused / et_potential)))
    else:
        esi = 0.0

    transpiration_eff = 1.0 - esi
    deficit = max(0.0, et_potential - et_actual_fused)

    # --- 8. Confidence ---
    # Higher confidence when we have more data sources
    confidence = 0.55  # base (LST available)
    if vpd_kpa is not None:
        confidence += 0.10
    if ndvi is not None:
        confidence += 0.05
    if wind_speed_ms is not None:
        confidence += 0.05
    if et0_mm is not None and et0_mm > 0:
        confidence += 0.10
    confidence = min(0.85, confidence)

    return WaterBudget(
        et_potential_mm=round(et_potential, 3),
        et_actual_mm=round(et_actual_fused, 3),
        esi=round(esi, 4),
        cwsi=round(cwsi, 4),
        canopy_air_delta_c=round(canopy_air_delta, 2),
        transpiration_efficiency=round(transpiration_eff, 4),
        deficit_mm=round(deficit, 3),
        confidence=round(confidence, 3),
        method="energy_balance_fused",
    )


# ============================================================================
# Helper functions
# ============================================================================

def _fractional_cover(ndvi: float) -> float:
    """Estimate fractional vegetation cover from NDVI.

    Carlson & Ripley (1997): fc = ((NDVI - NDVI_soil) / (NDVI_veg - NDVI_soil))^2
    Using NDVI_soil = 0.10, NDVI_veg = 0.85
    """
    ndvi_soil = 0.10
    ndvi_veg = 0.85
    if ndvi <= ndvi_soil:
        return 0.0
    if ndvi >= ndvi_veg:
        return 1.0
    ratio = (ndvi - ndvi_soil) / (ndvi_veg - ndvi_soil)
    return round(ratio ** 2, 4)


def _estimate_esi_from_vpd(vpd_kpa: float, ndvi: Optional[float] = None) -> float:
    """Estimate ESI proxy from VPD when LST is unavailable.

    High VPD with low NDVI → likely evaporative stress.
    This is a weak proxy (confidence is low).

    Empirical: ESI_proxy ≈ 0.15 * VPD for VPD > 1.5 kPa
    """
    if vpd_kpa < 1.0:
        return 0.0

    esi_proxy = min(0.6, (vpd_kpa - 1.0) * 0.15)

    # NDVI modulation: stressed canopy (low NDVI) amplifies VPD signal
    if ndvi is not None and ndvi < 0.4:
        esi_proxy = min(0.7, esi_proxy * 1.5)

    return max(0.0, esi_proxy)


def get_kc_for_stage(
    crop_type: str,
    stage: str,
    kc_init: float = 0.3,
    kc_mid: float = 1.15,
    kc_end: float = 0.4,
) -> float:
    """Map phenological stage to FAO-56 Kc coefficient.

    Stage mapping:
      BARE_SOIL, EMERGENCE → kc_init
      VEGETATIVE           → lerp(kc_init, kc_mid)
      REPRODUCTIVE         → kc_mid
      MATURITY             → lerp(kc_mid, kc_end)
      SENESCENCE           → kc_end
    """
    stage_upper = stage.upper()

    if stage_upper in ("BARE_SOIL", "EMERGENCE", "UNKNOWN"):
        return kc_init
    elif stage_upper == "VEGETATIVE":
        # Midpoint between init and mid
        return round((kc_init + kc_mid) / 2.0, 3)
    elif stage_upper == "REPRODUCTIVE":
        return kc_mid
    elif stage_upper == "MATURITY":
        return round((kc_mid + kc_end) / 2.0, 3)
    elif stage_upper == "SENESCENCE":
        return kc_end
    else:
        return kc_mid  # Default to peak demand
