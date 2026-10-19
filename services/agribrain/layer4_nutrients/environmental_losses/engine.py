"""
Layer 4.22: Environmental Loss Pathways Engine — Process-Based N Loss Models.

Replaces the simple fraction-based N loss estimates in the nutrient budget
with process-based models for each loss pathway:

1. Leaching (Burns 1974): N_leach = N_solution × drainage / (θ × depth)
2. Volatilization (Sommer 2004): NH3 = f(pH, temp, wind, urea_frac)
3. Denitrification (Del Grosso 2000): N2O = f(WFPS, NO3, T, C)
4. Surface runoff: N_runoff = f(slope, cover, rainfall_intensity, N_surface)

Each model produces:
  - Quantitative loss estimate (kg N/ha)
  - Risk index [0-1]
  - Mitigation recommendations

References:
  - Burns (1974): A model for predicting the redistribution of salts applied
    to fallow soils after excess rainfall or evaporation, J Soil Sci 25:165
  - Sommer et al. (2004): New empirical model for ammonia volatilization,
    Soil Use and Management 20:300-309
  - Del Grosso et al. (2000): General model for N2O and N2 gas emissions
    from soils due to denitrification, GBC 14:1045-1060
  - Sharpley (1985): Depth of surface soil-runoff interaction as affected
    by rainfall, soil slope, and management, SSSA J 49:1010
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class LossPathway:
    """One environmental loss pathway result."""
    pathway: str = ""                     # "leaching", "volatilization", etc.
    loss_kg_ha: float = 0.0               # Estimated N loss (kg/ha)
    risk_index: float = 0.0               # [0-1]
    risk_class: str = "LOW"               # LOW, MODERATE, HIGH, CRITICAL, UNAVAILABLE
    fraction_of_applied: float = 0.0      # Loss as fraction of applied N
    mitigation: List[str] = field(default_factory=list)
    availability: str = "AVAILABLE"       # AVAILABLE, UNAVAILABLE_UNSUPPORTED_ROOT
    is_supported: bool = True


@dataclass
class EnvLossResult:
    """Environmental loss pathways output."""
    # Individual pathways
    leaching: LossPathway = field(default_factory=lambda: LossPathway(pathway="leaching"))
    volatilization: LossPathway = field(default_factory=lambda: LossPathway(pathway="volatilization"))
    denitrification: LossPathway = field(default_factory=lambda: LossPathway(pathway="denitrification"))
    runoff: LossPathway = field(default_factory=lambda: LossPathway(pathway="runoff"))

    # Totals
    total_loss_kg_ha: float = 0.0
    total_loss_fraction: float = 0.0      # Total loss / applied N
    overall_risk: str = "LOW"

    # Environmental footprint
    n2o_emission_kg_ha: float = 0.0       # Direct N₂O (greenhouse gas)
    co2_equivalent_kg_ha: float = 0.0     # N₂O in CO₂ equivalents (×298 GWP)

    # Adjusted budget
    effective_n_available_kg_ha: float = 0.0  # Applied - losses
    notes: str = ""
    availability: str = "AVAILABLE"       # AVAILABLE, UNAVAILABLE_UNSUPPORTED_ROOT
    is_root_supported: bool = True


class EnvironmentalLossEngine:
    """Process-based N loss pathway models."""

    def compute_all_losses(
        self,
        n_applied_kg_ha: float = 100.0,
        application_method: str = "BROADCAST",
        product: str = "UREA",
        soil_ph: float = 6.5,
        clay_pct: float = 22.0,
        organic_matter_pct: float = 2.0,
        temperature_c: float = 22.0,
        wind_speed_m_s: float = 2.0,
        total_drainage_mm: float = 50.0,
        soil_moisture_vwc: float = 0.25,
        theta_fc: float = 0.30,
        theta_sat: float = 0.45,
        root_depth_cm: float = 60.0,
        slope_pct: float = 2.0,
        crop_cover_fraction: float = 0.5,
        rainfall_intensity_mm_hr: float = 5.0,
        incorporation_depth_cm: float = 0.0,
    ) -> EnvLossResult:
        """Compute all N loss pathways.

        Args:
            n_applied_kg_ha: Total N applied (kg/ha)
            application_method: BROADCAST, BANDED, FERTIGATION, etc.
            product: UREA, CAN, UAN_28, etc.
            soil_ph: Soil pH
            clay_pct: Clay content (%)
            organic_matter_pct: OM (%)
            temperature_c: Average temperature (°C)
            wind_speed_m_s: Wind speed (m/s)
            total_drainage_mm: Cumulative drainage below root zone (mm)
            soil_moisture_vwc: Current volumetric water content
            theta_fc: Field capacity
            theta_sat: Saturation
            root_depth_cm: Root depth (cm)
            slope_pct: Field slope (%)
            crop_cover_fraction: Canopy cover [0-1]
            rainfall_intensity_mm_hr: Peak rainfall intensity
            incorporation_depth_cm: Depth of fertilizer incorporation (cm)
        """
        # 1. Leaching
        leaching = self._leaching_burns(
            n_applied_kg_ha, total_drainage_mm, theta_fc,
            root_depth_cm, clay_pct,
        )

        # 2. Volatilization
        urea_fraction = self._urea_fraction(product)
        volatilization = self._volatilization_sommer(
            n_applied_kg_ha * urea_fraction, soil_ph, temperature_c,
            wind_speed_m_s, incorporation_depth_cm, application_method,
        )

        # 3. Denitrification
        if root_depth_cm <= 0.0:
            denitrification = LossPathway(
                pathway="denitrification",
                loss_kg_ha=0.0,
                risk_index=0.0,
                risk_class="UNAVAILABLE",
                fraction_of_applied=0.0,
                mitigation=["Root zone depth is zero or unsupported; denitrification pathway is physically unavailable."],
                availability="UNAVAILABLE_UNSUPPORTED_ROOT",
                is_supported=False,
            )
        else:
            wfps = self._water_filled_pore_space(soil_moisture_vwc, theta_sat)
            no3_proxy = n_applied_kg_ha * 0.3  # Rough: 30% of applied N as NO₃⁻
            denitrification = self._denitrification_daycent(
                wfps, no3_proxy, temperature_c, organic_matter_pct,
            )

        # 4. Runoff
        runoff = self._runoff_loss(
            n_applied_kg_ha, slope_pct, crop_cover_fraction,
            rainfall_intensity_mm_hr, application_method,
        )

        # 5. Totals
        total = (leaching.loss_kg_ha + volatilization.loss_kg_ha +
                 denitrification.loss_kg_ha + runoff.loss_kg_ha)
        total_frac = total / max(1.0, n_applied_kg_ha)

        # 6. N₂O emissions
        # IPCC Tier 1: 1% of applied N emitted as N₂O
        # Our model refines this using denitrification estimate
        n2o = denitrification.loss_kg_ha * 0.15  # ~15% of denitrif is N₂O
        n2o += n_applied_kg_ha * 0.005  # Background nitrification N₂O
        co2_eq = n2o * 298  # N₂O GWP = 298

        # 7. Overall risk
        max_risk = max(
            leaching.risk_index, volatilization.risk_index,
            denitrification.risk_index, runoff.risk_index,
        )
        if max_risk > 0.7:
            overall = "HIGH"
        elif max_risk > 0.4:
            overall = "MODERATE"
        else:
            overall = "LOW"

        effective_n = max(0, n_applied_kg_ha - total)

        notes_parts = []
        for pw in [leaching, volatilization, denitrification, runoff]:
            if pw.risk_class in ("HIGH", "CRITICAL"):
                notes_parts.append(
                    f"{pw.pathway}: {pw.loss_kg_ha:.1f} kg N/ha "
                    f"({pw.fraction_of_applied:.0%} of applied) — {pw.risk_class}"
                )
        if not notes_parts:
            notes_parts.append(
                f"Total N loss: {total:.1f} kg/ha ({total_frac:.0%} of applied). "
                f"All pathways within acceptable limits."
            )

        if root_depth_cm <= 0.0:
            notes_str = "Root boundary is unsupported (depth=0.0); water-dependent root-zone loss pathways (leaching, denitrification) are physically unavailable and excluded from loss debit."
            res_avail = "UNAVAILABLE_UNSUPPORTED_ROOT"
            is_supp = False
        else:
            notes_str = "; ".join(notes_parts)
            res_avail = "AVAILABLE"
            is_supp = True

        return EnvLossResult(
            leaching=leaching,
            volatilization=volatilization,
            denitrification=denitrification,
            runoff=runoff,
            total_loss_kg_ha=round(total, 2),
            total_loss_fraction=round(total_frac, 4),
            overall_risk=overall,
            n2o_emission_kg_ha=round(n2o, 3),
            co2_equivalent_kg_ha=round(co2_eq, 1),
            effective_n_available_kg_ha=round(effective_n, 2),
            notes=notes_str,
            availability=res_avail,
            is_root_supported=is_supp,
        )

    # ------------------------------------------------------------------
    # Leaching — Burns (1974) model
    # ------------------------------------------------------------------

    def _leaching_burns(
        self, n_applied: float, drainage_mm: float,
        theta_fc: float, root_depth_cm: float, clay_pct: float,
    ) -> LossPathway:
        """Burns (1974) leaching model.

        N_leach = N_solution × (drainage / soil_water_volume)

        N in soil solution moves with water. Drainage beyond root zone
        carries dissolved NO₃⁻ with it.
        """
        if root_depth_cm <= 0.0:
            return LossPathway(
                pathway="leaching",
                loss_kg_ha=0.0,
                risk_index=0.0,
                risk_class="UNAVAILABLE",
                fraction_of_applied=0.0,
                mitigation=["Root zone depth is zero or unsupported; root-zone leaching pathway is physically unavailable."],
                availability="UNAVAILABLE_UNSUPPORTED_ROOT",
                is_supported=False,
            )

        if drainage_mm <= 0 or n_applied <= 0:
            return LossPathway(
                pathway="leaching", loss_kg_ha=0.0, risk_index=0.0,
                risk_class="LOW", fraction_of_applied=0.0,
                mitigation=["No significant drainage — leaching risk is low"],
            )

        # Soil water volume in root zone (mm)
        soil_water_mm = theta_fc * root_depth_cm * 10  # cm → mm

        # N in solution: NO₃⁻ fraction of applied (ammonium adsorbed to clay)
        # Clay retains NH₄⁺ — only NO₃⁻ leaches
        no3_fraction = max(0.3, 0.8 - clay_pct * 0.01)  # Sandy soils leach more
        n_solution = n_applied * no3_fraction

        # Leaching fraction
        leach_frac = min(1.0, drainage_mm / max(1.0, soil_water_mm))
        n_leached = n_solution * leach_frac

        risk = min(1.0, n_leached / max(1.0, n_applied))

        mitigations = []
        if risk > 0.3:
            mitigations.append("Split N applications to reduce NO₃⁻ in soil solution")
            mitigations.append("Use nitrification inhibitors (DMPP, DCD) to retain N as NH₄⁺")
        if clay_pct < 15:
            mitigations.append("Sandy soil: frequent small applications preferred over single large dose")

        return LossPathway(
            pathway="leaching",
            loss_kg_ha=round(n_leached, 2),
            risk_index=round(risk, 4),
            risk_class="HIGH" if risk > 0.5 else "MODERATE" if risk > 0.2 else "LOW",
            fraction_of_applied=round(n_leached / max(1, n_applied), 4),
            mitigation=mitigations,
        )

    # ------------------------------------------------------------------
    # Volatilization — Sommer et al. (2004)
    # ------------------------------------------------------------------

    def _volatilization_sommer(
        self, n_urea: float, ph: float, temp_c: float,
        wind: float, incorporation_depth: float, method: str,
    ) -> LossPathway:
        """NH₃ volatilization from urea application.

        Sommer et al. (2004) empirical model:
        NH3_loss = N_urea × f(pH) × f(T) × f(wind) × f(incorporation)

        Urea hydrolysis produces NH₄⁺ → NH₃(g) at high pH.
        Volatilization is severe when urea is surface-applied on
        alkaline soils in hot, windy conditions.
        """
        if n_urea <= 0:
            return LossPathway(
                pathway="volatilization", loss_kg_ha=0.0, risk_index=0.0,
                risk_class="LOW", fraction_of_applied=0.0,
                mitigation=["No urea-based N applied — volatilization not a concern"],
            )

        # pH factor: exponential increase above pH 7
        ph_f = 0.02  # Base: 2% at neutral pH
        if ph > 7.0:
            ph_f = 0.02 * math.exp(0.7 * (ph - 7.0))
        elif ph < 6.0:
            ph_f = 0.01  # Very low at acid pH

        # Temperature factor: Q10 ≈ 3 for volatilization
        temp_f = 1.0
        if temp_c > 15:
            temp_f = 1.0 + 0.05 * (temp_c - 15)  # +5% per °C above 15
        temp_f = min(3.0, temp_f)

        # Wind factor
        wind_f = 1.0 + 0.1 * wind  # 10% increase per m/s

        # Incorporation factor: buried urea loses much less
        incorp_f = 1.0
        if incorporation_depth > 5:
            incorp_f = 0.10  # 90% reduction when incorporated > 5cm
        elif incorporation_depth > 2:
            incorp_f = 0.30
        elif incorporation_depth > 0:
            incorp_f = 0.60

        # Method factor
        method_f = 1.0
        if method.upper() == "FERTIGATION":
            incorp_f = 0.05  # Dissolved → minimal volatilization
        elif method.upper() in ("BANDED", "DEEP_PLACEMENT"):
            incorp_f = min(incorp_f, 0.20)

        # Total volatilization
        vol_frac = ph_f * temp_f * wind_f * incorp_f
        vol_frac = min(0.40, vol_frac)  # Cap at 40%
        n_vol = n_urea * vol_frac

        risk = vol_frac / 0.40  # Normalize to 0-1

        mitigations = []
        if vol_frac > 0.10:
            mitigations.append("Incorporate urea within 48 hours of application")
            mitigations.append("Consider switching to CAN or UAN (lower volatilization)")
        if ph > 7.5:
            mitigations.append("High pH soil: use ammonium sulfate instead of urea")
        if temp_c > 25:
            mitigations.append("Apply in cooler hours (early morning or evening)")

        return LossPathway(
            pathway="volatilization",
            loss_kg_ha=round(n_vol, 2),
            risk_index=round(min(1.0, risk), 4),
            risk_class="HIGH" if risk > 0.6 else "MODERATE" if risk > 0.3 else "LOW",
            fraction_of_applied=round(vol_frac, 4),
            mitigation=mitigations,
        )

    # ------------------------------------------------------------------
    # Denitrification — Del Grosso et al. (2000) DAYCENT
    # ------------------------------------------------------------------

    def _denitrification_daycent(
        self, wfps: float, no3_ppm: float, temp_c: float, om_pct: float,
    ) -> LossPathway:
        """DAYCENT-style denitrification model.

        Denitrification occurs when:
        - WFPS > 60% (anaerobic microsites form)
        - NO₃⁻ is available as electron acceptor
        - Temperature > 5°C
        - Available C for heterotrophic denitrifiers

        Del Grosso et al. (2000):
        D = f_WFPS × f_NO3 × f_T × f_C
        """
        if wfps < 0.4 or no3_ppm <= 0:
            return LossPathway(
                pathway="denitrification", loss_kg_ha=0.0, risk_index=0.0,
                risk_class="LOW", fraction_of_applied=0.0,
                mitigation=["Aerobic conditions — denitrification risk is low"],
            )

        # WFPS function: exponential increase above 60%
        if wfps < 0.6:
            f_wfps = 0.0
        elif wfps < 0.8:
            f_wfps = 0.5 * ((wfps - 0.6) / 0.2)
        else:
            f_wfps = 0.5 + 0.5 * min(1.0, (wfps - 0.8) / 0.2)

        # NO₃⁻ function: Michaelis-Menten
        km_no3 = 10.0  # Half-saturation (ppm)
        f_no3 = no3_ppm / (km_no3 + no3_ppm)

        # Temperature function: Q10 ≈ 2
        if temp_c < 5:
            f_temp = 0.0
        else:
            f_temp = min(1.0, (temp_c - 5) / 30.0)

        # Carbon availability (from OM decomposition)
        f_c = min(1.0, om_pct / 3.0)

        # Daily denitrification rate (fraction of soil NO₃⁻)
        d_frac = f_wfps * f_no3 * f_temp * f_c
        # Convert NO₃⁻ ppm to kg/ha (rough: 1 ppm ≈ 3 kg/ha in top 30cm)
        no3_kg_ha = no3_ppm * 3.0
        n_denitrif = no3_kg_ha * d_frac * 0.05  # 5% of susceptible pool per day

        risk = min(1.0, d_frac)

        mitigations = []
        if wfps > 0.7:
            mitigations.append("Improve drainage to reduce waterlogging")
            mitigations.append("Avoid N application during saturated soil conditions")
        if f_wfps > 0.3:
            mitigations.append("Use nitrification inhibitors to keep N as NH₄⁺ (non-denitrifiable)")

        return LossPathway(
            pathway="denitrification",
            loss_kg_ha=round(n_denitrif, 2),
            risk_index=round(risk, 4),
            risk_class="HIGH" if risk > 0.5 else "MODERATE" if risk > 0.2 else "LOW",
            fraction_of_applied=round(n_denitrif / max(1, no3_kg_ha), 4),
            mitigation=mitigations,
        )

    # ------------------------------------------------------------------
    # Surface Runoff
    # ------------------------------------------------------------------

    def _runoff_loss(
        self, n_applied: float, slope_pct: float,
        crop_cover: float, rainfall_intensity: float, method: str,
    ) -> LossPathway:
        """Surface runoff N loss.

        N loss via runoff depends on:
        - Surface N concentration (broadcasting → higher risk)
        - Slope (steeper → more runoff)
        - Crop cover (more cover → less runoff)
        - Rainfall intensity (intense rain → more runoff before infiltration)

        Reference: Sharpley (1985), SSSA J 49:1010.
        """
        if n_applied <= 0 or slope_pct < 0.5:
            return LossPathway(
                pathway="runoff", loss_kg_ha=0.0, risk_index=0.0,
                risk_class="LOW", fraction_of_applied=0.0,
                mitigation=["Flat terrain — runoff risk is minimal"],
            )

        # Surface N fraction depends on application method
        surface_fracs = {
            "BROADCAST": 0.80, "TOP_DRESS": 0.70,
            "BANDED": 0.30, "SIDE_DRESS": 0.30,
            "DEEP_PLACEMENT": 0.05, "FERTIGATION": 0.05,
            "FOLIAR": 0.10,
        }
        surface_frac = surface_fracs.get(method.upper(), 0.50)
        n_surface = n_applied * surface_frac

        # Slope factor: 2× risk per 5% slope
        slope_f = min(3.0, 1.0 + slope_pct / 5.0)

        # Cover factor: vegetation reduces runoff
        cover_f = max(0.1, 1.0 - crop_cover * 0.8)

        # Rainfall intensity factor
        intensity_f = min(2.0, rainfall_intensity / 10.0)

        # Runoff loss fraction
        runoff_frac = 0.02 * slope_f * cover_f * intensity_f
        runoff_frac = min(0.25, runoff_frac)
        n_runoff = n_surface * runoff_frac

        risk = min(1.0, runoff_frac / 0.15)

        mitigations = []
        if slope_pct > 5:
            mitigations.append("Consider contour application or buffer strips")
        if surface_frac > 0.5:
            mitigations.append("Incorporate fertilizer to reduce surface N")
        if crop_cover < 0.3:
            mitigations.append("Avoid application on bare soil — wait for canopy establishment")

        return LossPathway(
            pathway="runoff",
            loss_kg_ha=round(n_runoff, 2),
            risk_index=round(risk, 4),
            risk_class="HIGH" if risk > 0.5 else "MODERATE" if risk > 0.2 else "LOW",
            fraction_of_applied=round(n_runoff / max(1, n_applied), 4),
            mitigation=mitigations,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _urea_fraction(self, product: str) -> float:
        """Fraction of N that is urea-based (susceptible to volatilization)."""
        urea_products = {
            "UREA": 1.0, "UAN_28": 0.50, "UAN_32": 0.50,
            "NPK_15_15_15": 0.30,
        }
        return urea_products.get(product.upper(), 0.0)

    def _water_filled_pore_space(self, vwc: float, theta_sat: float) -> float:
        """Compute Water-Filled Pore Space (WFPS).

        WFPS = θ / θ_sat
        """
        if theta_sat <= 0:
            return 0.5
        return min(1.0, vwc / theta_sat)
