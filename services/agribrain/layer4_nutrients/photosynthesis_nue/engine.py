"""
Layer 4.21: Photosynthesis-NUE Coupling Engine — N Dilution Curve & NNI.

Connects L2 biophysical products (fPAR, NPP, LAI) to nutrient demand
via the critical N dilution curve and N Nutrition Index (NNI).

Science:
  As crops accumulate biomass, whole-plant N concentration decreases
  following a power law (the "critical N dilution curve"):

    N_critical (%) = a × W^(-b)

  where W = above-ground biomass (t DM/ha), a and b are crop-specific
  parameters. The N Nutrition Index (NNI) is:

    NNI = N_actual / N_critical

  NNI < 1.0 → N deficiency (crop N below critical for maximum growth)
  NNI = 1.0 → optimal N status
  NNI > 1.0 → luxury N consumption (excess N, risk of lodging/pollution)

  Maximum N uptake rate is bounded by photosynthetic capacity:
    N_sink = GPP × internal_NUE / (1 + exp(-k × (LAI - LAI_half)))

References:
  - Lemaire & Gastal (1997): N uptake and distribution in plant canopies,
    Diagnosis of the Nitrogen Status in Crops, Springer, pp.3-43
  - Greenwood et al. (1990): Decline in % N of C3 and C4 crops with
    increasing plant mass, Annals of Botany 66:425-436
  - Sinclair & Horie (1989): Leaf nitrogen, photosynthesis, and crop
    radiation use efficiency, Crop Science 29:90-98
  - Gastal & Lemaire (2002): N uptake and distribution in crops,
    J Experimental Botany 53:789-799
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from crop_database.registry import get_crop, CropSpec


# ============================================================================
# N dilution curve and RUE now sourced from centralized crop_database (209+)
# CropSpec fields: n_dilution_a, n_dilution_b, rue_g_mj, photosynthetic_pathway
# ============================================================================



@dataclass
class PhotoNUEResult:
    """Photosynthesis-NUE coupling analysis output."""
    # N dilution curve
    critical_n_pct: float = 0.0           # Critical N concentration (%)
    actual_n_pct: float = 0.0             # Actual/estimated N (%)
    nni: float = 1.0                      # N Nutrition Index [0-2+]
    nni_status: str = "OPTIMAL"           # DEFICIENT, SUB_OPTIMAL, OPTIMAL, LUXURY

    # Biomass and canopy
    estimated_biomass_t_ha: float = 0.0   # From L2 fPAR/NPP or LAI
    lai_current: float = 0.0
    fpar_current: float = 0.0

    # N sink capacity
    max_n_uptake_kg_ha_day: float = 0.0   # Physiological ceiling
    season_n_sink_kg_ha: float = 0.0      # Season total N sink capacity
    n_excess_kg_ha: float = 0.0           # Applied N beyond sink capacity

    # Radiation use efficiency
    rue_actual: float = 0.0               # g DM / MJ PAR
    rue_potential: float = 0.0            # Under optimal N
    rue_ratio: float = 1.0               # Actual/potential

    # WUE-NUE tradeoff
    wue_from_l2: float = 0.0             # Water Use Efficiency from L2
    n_limited_wue_reduction: float = 0.0  # WUE reduction due to N deficiency

    # Recommendations
    optimal_n_rate_kg_ha: float = 0.0     # N rate to reach NNI = 1.0
    notes: str = ""


class PhotosynthesisNUEEngine:
    """Couples photosynthetic capacity with nitrogen use efficiency."""

    def analyze(
        self,
        crop_type: str = "wheat",
        lai_current: float = 3.0,
        fpar_current: float = 0.5,
        npp_g_c_m2_day: float = 5.0,
        wue_from_l2: float = 0.0,
        n_applied_kg_ha: float = 0.0,
        soil_n_supply_kg_ha: float = 30.0,
        growth_stage: str = "vegetative",
        days_in_season: int = 120,
        daily_par_mj_m2: float = 10.0,
    ) -> PhotoNUEResult:
        """Analyze photosynthesis-NUE coupling.

        Args:
            crop_type: Crop code
            lai_current: Current Leaf Area Index (from L2)
            fpar_current: Current fPAR (from L2)
            npp_g_c_m2_day: Net Primary Productivity (g C/m²/day, from L2)
            wue_from_l2: Water Use Efficiency (from L2 health_index)
            n_applied_kg_ha: Total N applied so far (kg/ha)
            soil_n_supply_kg_ha: Soil N supply (mineralization + residual)
            growth_stage: Current phenology stage
            days_in_season: Total growing season length
            daily_par_mj_m2: Daily PAR (MJ/m²/day)
        """
        crop_lower = crop_type.lower()

        # 1. Estimate biomass from NPP or LAI
        biomass = self._estimate_biomass(
            npp_g_c_m2_day, lai_current, fpar_current, crop_lower,
            days_in_season, growth_stage,
        )

        # 2. Critical N dilution curve
        critical_n = self._critical_n_concentration(biomass, crop_lower)

        # 3. Estimate actual N concentration
        total_n_available = n_applied_kg_ha + soil_n_supply_kg_ha
        # Plant N = total available × recovery efficiency (~0.6)
        plant_n_kg_ha = total_n_available * 0.60
        # biomass is t/ha.  Converting to kg/ha and then to percent gives
        # plant_N / (biomass * 1000) * 100 == plant_N / (biomass * 10).
        actual_n_pct = plant_n_kg_ha / max(0.1, biomass * 10) if biomass > 0 else 0

        # 4. N Nutrition Index
        nni = actual_n_pct / max(0.1, critical_n)
        nni = max(0.0, min(3.0, nni))
        nni_status = self._classify_nni(nni)

        # 5. N sink capacity (physiological ceiling)
        max_daily = self._max_n_uptake_rate(lai_current, fpar_current, daily_par_mj_m2, crop_lower)
        season_sink = max_daily * days_in_season * 0.5  # Active uptake ~50% of season

        # 6. N excess
        n_excess = max(0, total_n_available - season_sink)

        # 7. Radiation use efficiency
        spec = get_crop(crop_lower)
        rue_pot = spec.rue_g_mj
        # N deficiency reduces RUE linearly
        rue_ratio = min(1.0, nni)
        rue_actual = rue_pot * rue_ratio

        # 8. WUE-NUE tradeoff
        wue_reduction = 0.0
        if nni < 0.8:
            # N deficiency reduces stomatal conductance → reduces WUE
            wue_reduction = (0.8 - nni) * 0.3

        # 9. Optimal N rate
        if nni < 1.0 and biomass > 0:
            n_deficit_pct = critical_n - actual_n_pct
            n_needed_kg_ha = n_deficit_pct * biomass * 10.0 / 0.60
            optimal_n = max(0.0, n_needed_kg_ha)
        else:
            optimal_n = 0.0

        notes_parts = []
        if nni < 0.7:
            notes_parts.append(
                f"Severe N deficiency: NNI={nni:.2f}. Crop N ({actual_n_pct:.2f}%) "
                f"far below critical ({critical_n:.2f}%). RUE reduced to {rue_ratio:.0%}."
            )
        elif nni < 1.0:
            notes_parts.append(
                f"Sub-optimal N: NNI={nni:.2f}. Consider {optimal_n:.0f} kg N/ha "
                f"to reach NNI=1.0."
            )
        elif nni > 1.3:
            notes_parts.append(
                f"Luxury N consumption: NNI={nni:.2f}. {n_excess:.0f} kg N/ha "
                f"exceeds crop sink capacity — risk of leaching/lodging."
            )
        else:
            notes_parts.append(f"N status optimal: NNI={nni:.2f}")

        if n_excess > 20:
            notes_parts.append(
                f"N excess: {n_excess:.0f} kg N/ha above physiological sink. "
                f"Environmental loss risk elevated."
            )

        return PhotoNUEResult(
            critical_n_pct=round(critical_n, 3),
            actual_n_pct=round(actual_n_pct, 3),
            nni=round(nni, 4),
            nni_status=nni_status,
            estimated_biomass_t_ha=round(biomass, 3),
            lai_current=round(lai_current, 2),
            fpar_current=round(fpar_current, 3),
            max_n_uptake_kg_ha_day=round(max_daily, 3),
            season_n_sink_kg_ha=round(season_sink, 2),
            n_excess_kg_ha=round(n_excess, 2),
            rue_actual=round(rue_actual, 3),
            rue_potential=round(rue_pot, 3),
            rue_ratio=round(rue_ratio, 4),
            wue_from_l2=round(wue_from_l2, 3),
            n_limited_wue_reduction=round(wue_reduction, 4),
            optimal_n_rate_kg_ha=round(optimal_n, 2),
            notes="; ".join(notes_parts),
        )

    def _estimate_biomass(
        self, npp: float, lai: float, fpar: float,
        crop: str, days: int, stage: str,
    ) -> float:
        """Estimate above-ground biomass (t DM/ha) from L2 products.

        Priority: NPP > fPAR > LAI (decreasing reliability).
        """
        # Method 1: From NPP (most reliable if available)
        if npp > 0:
            # NPP is in g C / m² / day
            # Cumulative C = NPP × stage_days × above-ground fraction
            stage_fracs = {
                "bare_soil": 0.05, "emergence": 0.10, "vegetative": 0.40,
                "reproductive": 0.75, "senescence": 0.90, "maturity": 0.95,
            }
            frac = stage_fracs.get(stage.lower(), 0.50)
            cumul_c_g_m2 = npp * days * frac
            # Convert: g C → g DM (÷ 0.45), m² → ha (× 10000), g → t (÷ 1e6)
            biomass = cumul_c_g_m2 / 0.45 * 10000 / 1e6
            return max(0.1, min(30.0, biomass))

        # Method 2: From LAI using SLA relationship
        if lai > 0:
            # SLA ≈ 20-25 m²/kg for most crops
            sla = 22.0  # m² leaf / kg DM
            leaf_mass = lai / sla * 10  # t/ha
            # Total biomass ≈ leaf mass / leaf fraction
            leaf_fraction = 0.30 if stage.lower() == "vegetative" else 0.20
            return max(0.1, leaf_mass / leaf_fraction)

        return 2.0  # Conservative default

    def _critical_n_concentration(self, biomass_t_ha: float, crop: str) -> float:
        """Critical N concentration from dilution curve.

        N_critical (%) = a × W^(-b)
        """
        spec = get_crop(crop)
        a = spec.n_dilution_a
        b = spec.n_dilution_b
        w = max(0.5, biomass_t_ha)  # Avoid division issues at very low biomass
        return a * (w ** (-b))

    def _classify_nni(self, nni: float) -> str:
        """Classify N Nutrition Index status."""
        if nni < 0.7:
            return "DEFICIENT"
        elif nni < 0.9:
            return "SUB_OPTIMAL"
        elif nni <= 1.1:
            return "OPTIMAL"
        else:
            return "LUXURY"

    def _max_n_uptake_rate(
        self, lai: float, fpar: float, par: float, crop: str,
    ) -> float:
        """Maximum daily N uptake rate (kg N/ha/day).

        Bounded by photosynthetic capacity:
        N_uptake_max = APAR × RUE × N_content / biomass_increment

        Typical max: 3-5 kg N/ha/day during rapid growth phase.

        Reference: Gastal & Lemaire (2002).
        """
        spec = get_crop(crop)
        rue = spec.rue_g_mj
        apar = fpar * par  # Absorbed PAR (MJ/m²/day)

        # Biomass increment = APAR × RUE (g DM / m² / day)
        dm_increment = apar * rue  # g DM / m² / day

        # N demand = biomass × N concentration (≈ 3% during active growth)
        n_demand_g_m2 = dm_increment * 0.03

        # Convert g/m² → kg/ha (× 10)
        return min(6.0, n_demand_g_m2 * 10)
