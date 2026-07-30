"""
Layer 4.20: Soil Respiration Engine — Dynamic N Mineralization from Temperature & Moisture.

Replaces the static SOC-based N mineralization estimate with a process-based
model driven by daily weather. Uses:
  1. Lloyd-Taylor temperature function (non-linear Q10)
  2. Moyano moisture function (optimal at ~60% WFPS)
  3. Dual-pool carbon model (labile + recalcitrant)
  4. Tillage disturbance effect on decomposition rate

Science:
  Heterotrophic soil respiration (R_h) is the primary driver of N
  mineralization. The rate depends on:
    R_h = R_ref × f(T) × f(θ) × f(clay) × f(tillage)
  where:
    f(T) = exp(E0 × (1/T_ref - 1/T)) — Lloyd-Taylor (1994)
    f(θ) = normalized water-filled pore space function — Moyano (2013)

  N mineralization = R_h × (1/CN_ratio) × N_fraction_released

References:
  - Lloyd & Taylor (1994): On the temperature dependence of soil
    respiration, Functional Ecology 8:315-323
  - Moyano et al. (2013): Responses of soil heterotrophic respiration
    to moisture availability, Biogeosciences 10:3999-4018
  - Parton et al. (1987): Analysis of factors controlling SOM levels
    in Great Plains grasslands, SSSA J 51:1173-1179
  - Stanford & Smith (1972): Nitrogen mineralization potentials of soils,
    SSSA J 36:465-472
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SoilRespirationResult:
    """Soil respiration and dynamic N mineralization output."""
    # Daily respiration (most recent day)
    daily_respiration_g_c_m2: float = 0.0  # g C / m² / day
    daily_n_mineralization_kg_ha: float = 0.0  # kg N / ha / day

    # Cumulative season totals
    cumulative_respiration_g_c_m2: float = 0.0
    cumulative_n_mineralization_kg_ha: float = 0.0

    # Breakdown by pool
    labile_contribution_pct: float = 0.0   # % from labile pool
    recalcitrant_contribution_pct: float = 0.0

    # Environmental factors (most recent day)
    temperature_factor: float = 1.0        # Lloyd-Taylor
    moisture_factor: float = 1.0           # Moyano
    clay_protection_factor: float = 1.0
    tillage_disturbance_factor: float = 1.0

    # Comparison to static model
    static_model_kg_ha: float = 0.0        # Old SOC*15 estimate
    dynamic_vs_static_ratio: float = 1.0   # >1 = dynamic predicts more N

    # Quality
    n_days_modeled: int = 0
    notes: str = ""


# Lloyd-Taylor (1994) parameters
_E0 = 308.56      # Activation energy parameter (K)
_T_REF = 283.15   # Reference temperature (10°C in K)
_T0 = 227.13      # Lower asymptote (K) — below this, respiration → 0

# Reference respiration rates by SOC class (g C / m² / day at T_ref, optimal moisture)
_R_REF_BY_SOC = {
    # SOC%: R_ref
    0.5: 0.8,
    1.0: 1.5,
    1.5: 2.2,
    2.0: 3.0,
    3.0: 4.5,
    5.0: 6.0,
}


class SoilRespirationEngine:
    """Dynamic soil respiration model for N mineralization prediction."""

    def compute_seasonal_mineralization(
        self,
        daily_weather: List[Dict],
        soc_pct: float = 1.5,
        clay_pct: float = 22.0,
        organic_matter_pct: float = 2.6,
        tillage_class: str = "UNKNOWN",
        theta_fc: float = 0.30,
        theta_wp: float = 0.15,
        cn_ratio: float = 10.0,
        soil_bulk_density: float = 1.3,
    ) -> SoilRespirationResult:
        """Compute cumulative N mineralization over a weather series.

        Args:
            daily_weather: [{t_max, rain_mm, et0, ...}] from SWB or L1
            soc_pct: Soil organic carbon (%)
            clay_pct: Clay content (%)
            organic_matter_pct: Organic matter (%) [= SOC / 0.58]
            tillage_class: CONVENTIONAL, REDUCED, NO_TILL, UNKNOWN
            theta_fc: Field capacity (volumetric, m³/m³)
            theta_wp: Wilting point (volumetric, m³/m³)
            cn_ratio: Soil C:N ratio (default 10:1)
            soil_bulk_density: Bulk density (g/cm³)
        """
        # 1. Derive pool sizes
        labile_frac = self._labile_fraction(clay_pct, organic_matter_pct)
        r_ref = self._reference_respiration(soc_pct)

        # 2. Clay protection factor
        clay_f = self._clay_protection(clay_pct)

        # 3. Tillage disturbance
        tillage_f = self._tillage_factor(tillage_class)

        # 4. Run daily model
        cumul_resp = 0.0
        cumul_n_min = 0.0
        daily_resp = 0.0
        daily_n_min = 0.0
        temp_f_last = 1.0
        moist_f_last = 1.0

        # Track soil moisture (simple bucket model for respiration)
        soil_moisture_mm = theta_fc * 300  # Start at FC (300mm depth)
        taw_mm = (theta_fc - theta_wp) * 300

        for day in daily_weather:
            t_max = day.get("t_max")
            if t_max is None:
                t_max = 22.0
            rain = day.get("rain_mm")
            if rain is None:
                rain = 0.0
            et0 = day.get("et0")
            if et0 is None:
                et0 = 4.0

            # Approximate daily mean T from max (crude but common)
            t_mean = t_max * 0.75  # Night cooling approximation

            # Update soil moisture
            soil_moisture_mm += rain - et0 * 0.5  # Simplified ET
            soil_moisture_mm = max(theta_wp * 300, min(theta_fc * 300 * 1.1, soil_moisture_mm))

            # Volumetric water content
            vwc = soil_moisture_mm / 300.0

            # Temperature function (Lloyd-Taylor)
            temp_f = self._lloyd_taylor(t_mean)

            # Moisture function (Moyano)
            moist_f = self._moyano_moisture(vwc, theta_fc, theta_wp)

            # Daily heterotrophic respiration (g C / m² / day)
            r_daily = r_ref * temp_f * moist_f * clay_f * tillage_f

            # Partition between labile and recalcitrant pools
            labile_resp = r_daily * labile_frac * 3.0  # Labile decomposes 3x faster
            recalcitrant_resp = r_daily * (1.0 - labile_frac)
            r_daily = labile_resp + recalcitrant_resp

            # N mineralization = C respired / C:N ratio × immobilization factor
            # Not all mineralized N is available — some is re-immobilized
            immob_factor = 0.60 if cn_ratio > 15 else 0.80  # High C:N → more immobilization
            n_min_g_m2 = (r_daily / max(5.0, cn_ratio)) * immob_factor

            # Convert g N/m² → kg N/ha (1 g/m² = 10 kg/ha)
            n_min_kg_ha = n_min_g_m2 * 10.0

            cumul_resp += r_daily
            cumul_n_min += n_min_kg_ha
            daily_resp = r_daily
            daily_n_min = n_min_kg_ha
            temp_f_last = temp_f
            moist_f_last = moist_f

        # 5. Static model comparison
        static_n = soc_pct * 15.0  # Old static model (kg N/ha/yr)
        # Scale to season length
        season_fraction = len(daily_weather) / 365.0
        static_season = static_n * season_fraction

        ratio = cumul_n_min / max(0.1, static_season) if static_season > 0 else 1.0

        # 6. Pool contributions
        labile_pct = labile_frac * 3.0 / (labile_frac * 3.0 + (1 - labile_frac))
        recalcitrant_pct = 1.0 - labile_pct

        notes_parts = []
        notes_parts.append(
            f"Dynamic model: {cumul_n_min:.1f} kg N/ha over {len(daily_weather)} days "
            f"(static model: {static_season:.1f} kg N/ha)"
        )
        if ratio > 1.3:
            notes_parts.append(
                "Dynamic model predicts significantly more mineralization — "
                "warm/moist conditions accelerating decomposition"
            )
        elif ratio < 0.7:
            notes_parts.append(
                "Dynamic model predicts less mineralization — "
                "cool/dry conditions limiting decomposition"
            )

        return SoilRespirationResult(
            daily_respiration_g_c_m2=round(daily_resp, 4),
            daily_n_mineralization_kg_ha=round(daily_n_min, 4),
            cumulative_respiration_g_c_m2=round(cumul_resp, 2),
            cumulative_n_mineralization_kg_ha=round(cumul_n_min, 2),
            labile_contribution_pct=round(labile_pct * 100, 1),
            recalcitrant_contribution_pct=round(recalcitrant_pct * 100, 1),
            temperature_factor=round(temp_f_last, 4),
            moisture_factor=round(moist_f_last, 4),
            clay_protection_factor=round(clay_f, 4),
            tillage_disturbance_factor=round(tillage_f, 4),
            static_model_kg_ha=round(static_season, 2),
            dynamic_vs_static_ratio=round(ratio, 3),
            n_days_modeled=len(daily_weather),
            notes="; ".join(notes_parts),
        )

    # ------------------------------------------------------------------
    # Lloyd-Taylor Temperature Function
    # ------------------------------------------------------------------

    def _lloyd_taylor(self, temp_c: float) -> float:
        """Lloyd-Taylor (1994) temperature response.

        f(T) = exp(E0 × (1/(T_ref - T0) - 1/(T - T0)))

        This is a non-linear Arrhenius-type function that better fits
        observed soil respiration than the simple Q10 model, especially
        at low temperatures.

        At T_ref (10°C), f(T) = 1.0.
        At 20°C, f(T) ≈ 2.0 (equivalent Q10 ≈ 2.0).
        At 30°C, f(T) ≈ 3.5.
        """
        t_k = temp_c + 273.15

        # Guard against division by zero or negative denominator
        if t_k <= _T0 + 1.0:
            return 0.01  # Near-zero respiration below ~-46°C

        try:
            exponent = _E0 * (1.0 / (_T_REF - _T0) - 1.0 / (t_k - _T0))
            return math.exp(exponent)
        except OverflowError:
            return 5.0  # Cap at very high temperatures

    # ------------------------------------------------------------------
    # Moyano Moisture Function
    # ------------------------------------------------------------------

    def _moyano_moisture(
        self, vwc: float, theta_fc: float, theta_wp: float,
    ) -> float:
        """Moyano et al. (2013) moisture response function.

        Optimal respiration at ~60% water-filled pore space (WFPS).
        Too dry → substrate diffusion limited.
        Too wet → O₂ diffusion limited (anaerobic).

        We use a simplified parabolic function:
        f(θ) = 4 × RSWC × (1 - RSWC)
        where RSWC = (θ - θ_wp) / (θ_fc - θ_wp)
        """
        if theta_fc <= theta_wp:
            return 0.5

        rswc = (vwc - theta_wp) / (theta_fc - theta_wp)
        rswc = max(0.0, min(1.5, rswc))  # Allow slight super-saturation

        if rswc <= 0:
            return 0.05  # Minimal respiration at wilting point
        elif rswc <= 1.0:
            # Parabolic — peaks at RSWC = 0.5 (= ~60% WFPS)
            return max(0.05, 4.0 * rswc * (1.0 - rswc) + 0.1)
        else:
            # Waterlogged — declining O₂ availability
            return max(0.1, 1.0 - 0.4 * (rswc - 1.0))

    # ------------------------------------------------------------------
    # Support functions
    # ------------------------------------------------------------------

    def _labile_fraction(self, clay_pct: float, om_pct: float) -> float:
        """Fraction of SOC in the labile (active) pool.

        Labile C = recently deposited organic matter (crop residues,
        root exudates, microbial biomass). Typically 5-20% of total SOC.

        Clay protects organic matter from decomposition by physical
        sorption and aggregate occlusion.

        Reference: Parton et al. (1987), CENTURY model.
        """
        base_labile = 0.15  # 15% base
        # High OM → higher absolute labile pool but lower fraction
        if om_pct > 3.0:
            base_labile = 0.12
        # Clay protection reduces labile fraction
        clay_protection = max(0.5, 1.0 - clay_pct * 0.005)
        return max(0.05, min(0.25, base_labile * clay_protection))

    def _reference_respiration(self, soc_pct: float) -> float:
        """Reference respiration rate at T_ref and optimal moisture.

        Interpolated from empirical data (g C / m² / day).
        """
        # Linear interpolation in _R_REF_BY_SOC
        soc_points = sorted(_R_REF_BY_SOC.items())
        if soc_pct <= soc_points[0][0]:
            return soc_points[0][1]
        if soc_pct >= soc_points[-1][0]:
            return soc_points[-1][1]
        for i in range(len(soc_points) - 1):
            s_lo, r_lo = soc_points[i]
            s_hi, r_hi = soc_points[i + 1]
            if s_lo <= soc_pct <= s_hi:
                frac = (soc_pct - s_lo) / (s_hi - s_lo)
                return r_lo + frac * (r_hi - r_lo)
        return 2.0  # Fallback

    def _clay_protection(self, clay_pct: float) -> float:
        """Clay protection factor — high clay slows decomposition.

        Reference: Hassink (1997), Plant & Soil 191:77-87.
        """
        factor = 1.0 - 0.004 * max(0, clay_pct - 15)
        return max(0.60, min(1.0, factor))

    def _tillage_factor(self, tillage_class: str) -> float:
        """Tillage disturbance acceleration of decomposition.

        Conventional tillage breaks aggregates, exposing protected
        OM to microbial attack → increased respiration.

        Reference: Six et al. (2000), SSSA J 64:1042-1049.
        """
        factors = {
            "CONVENTIONAL": 1.30,
            "REDUCED": 1.10,
            "NO_TILL": 0.90,
            "UNKNOWN": 1.00,
        }
        return factors.get(tillage_class.upper(), 1.00)
