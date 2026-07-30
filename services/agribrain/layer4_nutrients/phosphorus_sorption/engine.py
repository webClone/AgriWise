"""
Layer 4.16: Phosphorus Sorption Engine — Langmuir Isotherm + Al/Fe/Ca Fixation.

Models soil P availability using the Langmuir adsorption isotherm and
pH-dependent fixation by Al/Fe oxides (acid soils) and Ca precipitation
(calcareous soils).

Science:
  - Langmuir isotherm: P_solution = (P_max × K × P_total) / (1 + K × P_total)
  - Acid soils (pH < 5.5): Al³⁺/Fe³⁺ oxides adsorb H₂PO₄⁻ → insoluble AlPO₄/FePO₄
  - Calcareous soils (pH > 7.5): Ca²⁺ precipitates P as hydroxyapatite
  - Organic matter competes with P for adsorption sites → increases P availability
  - Clay content increases P buffer capacity (more exchange surfaces)

References:
  - Barrow (1978): A mechanistic model for describing the sorption
    and desorption of phosphate by soil, J Soil Sci 29:447-462
  - Bache & Williams (1971): A phosphate sorption index for soils,
    J Soil Sci 22:289-301
  - Sims & Pierzynski (2005): Chemistry of Phosphorus in Soils,
    Chemical Processes in Soils, SSSA Book Series 8
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class PSorptionResult:
    """Phosphorus sorption analysis output."""
    # Availability
    plant_available_p_ppm: float = 0.0        # Equilibrium solution P
    fixation_fraction: float = 0.0            # Fraction of applied P that gets fixed [0-1]
    p_buffer_capacity: float = 0.0            # dP_adsorbed / dP_solution (mg/kg per mg/L)

    # Fixation mechanisms
    al_fe_fixation: float = 0.0               # Al/Fe oxide fixation fraction (acid soils)
    ca_precipitation: float = 0.0             # Ca precipitation fraction (calcareous)
    organic_competition: float = 0.0          # OM competition reducing fixation

    # Langmuir parameters
    p_max_mg_kg: float = 0.0                  # Maximum adsorption capacity
    k_constant: float = 0.0                   # Bonding energy constant

    # Recommendations
    placement_recommendation: str = ""        # "BAND" or "BROADCAST"
    efficiency_gain_from_banding: float = 0.0 # Expected P efficiency gain from banding [0-1]
    notes: str = ""


class PhosphorusSorptionEngine:
    """Models phosphorus availability using soil chemistry.

    Two-step approach:
    1. Estimate Langmuir isotherm parameters from soil properties
    2. Compute plant-available P and fixation losses
    """

    def compute_p_availability(
        self,
        soil_ph: float = 6.5,
        clay_pct: float = 22.0,
        organic_matter_pct: float = 2.0,
        soil_p_ppm: Optional[float] = None,
        p_applied_kg_ha: float = 0.0,
        fe_oxide_proxy: Optional[float] = None,
        ca_saturation_pct: Optional[float] = None,
    ) -> PSorptionResult:
        """Compute P availability accounting for sorption and fixation.

        Args:
            soil_ph: Soil pH (water extraction)
            clay_pct: Clay content (%)
            organic_matter_pct: Organic matter (%)
            soil_p_ppm: Measured Olsen or Mehlich-3 P (ppm)
            p_applied_kg_ha: Freshly applied P fertilizer (kg P/ha)
            fe_oxide_proxy: Dithionite-extractable Fe (g/kg), optional
            ca_saturation_pct: Base saturation with Ca (%), optional
        """
        # 1. Estimate Langmuir parameters from pedotransfer
        p_max = self._estimate_p_max(clay_pct, organic_matter_pct, soil_ph, fe_oxide_proxy)
        k_const = self._estimate_k_constant(soil_ph, clay_pct)

        # 2. Compute fixation by mechanism
        al_fe = self._al_fe_fixation_factor(soil_ph, clay_pct, fe_oxide_proxy)
        ca_precip = self._ca_precipitation_factor(soil_ph, ca_saturation_pct)
        om_competition = self._organic_matter_competition(organic_matter_pct, soil_ph)

        # 3. Net fixation fraction
        # Fixation is the weighted sum of mechanisms, reduced by OM competition
        gross_fixation = max(al_fe, ca_precip)  # Dominant mechanism by pH
        net_fixation = gross_fixation * (1.0 - om_competition)
        net_fixation = max(0.0, min(0.95, net_fixation))  # Cap at 95%

        # 4. Plant-available P
        total_p = (soil_p_ppm or 15.0) + p_applied_kg_ha * 0.5  # rough ppm equivalent
        available_p = self._langmuir_equilibrium(total_p, p_max, k_const)
        available_p *= (1.0 - net_fixation)

        # 5. P buffer capacity
        pbc = self._p_buffer_capacity(clay_pct, organic_matter_pct, soil_ph)

        # 6. Placement recommendation
        placement, efficiency_gain = self._recommend_placement(net_fixation, soil_ph)

        notes_parts = []
        if al_fe > 0.3:
            notes_parts.append(
                f"High Al/Fe fixation risk ({al_fe:.0%}): acid soil pH {soil_ph:.1f} "
                f"binds P as insoluble Al/Fe phosphates"
            )
        if ca_precip > 0.3:
            notes_parts.append(
                f"Ca precipitation risk ({ca_precip:.0%}): calcareous soil pH {soil_ph:.1f} "
                f"precipitates P as apatite"
            )
        if om_competition > 0.2:
            notes_parts.append(
                f"Organic matter ({organic_matter_pct:.1f}%) competes for sorption sites, "
                f"improving P availability by {om_competition:.0%}"
            )
        if not notes_parts:
            notes_parts.append("P availability conditions are favorable (pH 6.0-7.0 range)")

        return PSorptionResult(
            plant_available_p_ppm=round(available_p, 2),
            fixation_fraction=round(net_fixation, 4),
            p_buffer_capacity=round(pbc, 2),
            al_fe_fixation=round(al_fe, 4),
            ca_precipitation=round(ca_precip, 4),
            organic_competition=round(om_competition, 4),
            p_max_mg_kg=round(p_max, 1),
            k_constant=round(k_const, 4),
            placement_recommendation=placement,
            efficiency_gain_from_banding=round(efficiency_gain, 3),
            notes="; ".join(notes_parts),
        )

    def _estimate_p_max(
        self, clay_pct: float, om_pct: float, ph: float,
        fe_oxide: Optional[float],
    ) -> float:
        """Estimate maximum P adsorption capacity (mg P / kg soil).

        Pedotransfer from Borggaard et al. (2004):
          P_max ≈ 0.15 × clay + 0.10 × OM + Fe_oxide_contribution
        Typical range: 50-800 mg/kg.
        """
        base = clay_pct * 6.0 + om_pct * 15.0  # mg/kg
        if fe_oxide is not None:
            base += fe_oxide * 2.5  # Fe oxide contribution
        # Acid soils have more reactive surfaces
        if ph < 5.5:
            base *= 1.4
        elif ph > 7.5:
            base *= 1.2  # Ca-P precipitation adds capacity
        return max(50.0, min(800.0, base))

    def _estimate_k_constant(self, ph: float, clay_pct: float) -> float:
        """Estimate Langmuir bonding energy constant.

        Higher K = stronger binding = less available P.
        Acid and high-clay soils bind P more strongly.
        """
        k = 0.05 + clay_pct * 0.001
        if ph < 5.5:
            k *= 1.5  # Strong binding in acid soils
        elif ph > 7.5:
            k *= 1.3  # Strong binding in calcareous soils
        return max(0.01, min(0.5, k))

    def _langmuir_equilibrium(
        self, p_total: float, p_max: float, k: float,
    ) -> float:
        """Langmuir isotherm: equilibrium solution P concentration.

        P_solution = (P_max × K × P_total) / (1 + K × P_total)

        This gives the plant-available fraction in soil solution.
        """
        if p_total <= 0:
            return 0.0
        return (p_max * k * p_total) / (1.0 + k * p_total)

    def _al_fe_fixation_factor(
        self, ph: float, clay_pct: float,
        fe_oxide: Optional[float],
    ) -> float:
        """Al/Fe oxide fixation fraction for acid soils.

        Below pH 5.5, Al³⁺ and Fe³⁺ oxides strongly adsorb phosphate.
        Fixation increases sharply below pH 5.0.

        Reference: Sanchez (1976), Properties and Management of Soils
        in the Tropics.
        """
        if ph >= 6.5:
            return 0.0  # Negligible above pH 6.5

        # Sigmoidal increase in fixation as pH drops below 6.5
        fixation = 1.0 / (1.0 + math.exp(3.0 * (ph - 5.0)))

        # Clay amplifies fixation (more oxide surfaces)
        clay_factor = min(1.5, clay_pct / 30.0)
        fixation *= clay_factor

        # Fe oxide contribution
        if fe_oxide is not None and fe_oxide > 10.0:
            fixation *= min(1.5, fe_oxide / 20.0)

        return min(0.90, fixation)

    def _ca_precipitation_factor(
        self, ph: float, ca_saturation: Optional[float],
    ) -> float:
        """Ca precipitation fraction for calcareous soils.

        Above pH 7.5, dissolved Ca²⁺ precipitates P as calcium phosphates
        (dicalcium phosphate → eventually apatite).

        Reference: Lindsay (1979), Chemical Equilibria in Soils.
        """
        if ph < 7.0:
            return 0.0

        # Sigmoidal increase above pH 7.0
        precip = 1.0 / (1.0 + math.exp(-3.0 * (ph - 7.8)))

        # High Ca saturation amplifies precipitation
        if ca_saturation is not None:
            ca_factor = min(1.5, ca_saturation / 60.0)
            precip *= ca_factor

        return min(0.85, precip)

    def _organic_matter_competition(
        self, om_pct: float, ph: float,
    ) -> float:
        """Organic anion competition for sorption sites.

        Organic acids (humic/fulvic) compete with phosphate for Al/Fe
        binding sites, effectively releasing P into solution.

        Reference: Hue (1991), Soil Sci Soc Am J 55:1508-1511.
        """
        if om_pct < 1.0:
            return 0.0
        # Logarithmic effect — diminishing returns above ~5% OM
        competition = 0.08 * math.log(om_pct + 0.5)
        # More effective in acid soils where Al/Fe fixation dominates
        if ph < 5.5:
            competition *= 1.5
        return min(0.40, max(0.0, competition))

    def _p_buffer_capacity(
        self, clay_pct: float, om_pct: float, ph: float,
    ) -> float:
        """P buffer capacity: resistance of soil P to depletion.

        High PBC means the soil releases P slowly — needs higher
        application rates but maintains P longer.

        Units: mg P adsorbed per kg soil per mg/L change in solution P.
        """
        pbc = clay_pct * 1.5 + om_pct * 5.0
        if ph < 5.5 or ph > 7.5:
            pbc *= 1.3  # Higher buffer in fixation-prone soils
        return max(10.0, min(300.0, pbc))

    def _recommend_placement(
        self, fixation_fraction: float, ph: float,
    ) -> tuple:
        """Recommend P placement method based on fixation risk.

        Banding (concentrating P in a narrow strip) reduces the soil
        volume that contacts P, minimizing fixation. Effective when
        fixation > 30%.

        Reference: Randall & Hoeft (1988), Soil Sci Soc Am J.
        """
        if fixation_fraction > 0.50:
            return "BAND", 0.40  # Banding recovers ~40% of fixed P
        elif fixation_fraction > 0.30:
            return "BAND", 0.25
        elif fixation_fraction > 0.15:
            return "BAND_OR_BROADCAST", 0.10
        else:
            return "BROADCAST", 0.0  # Low fixation — broadcast is fine
