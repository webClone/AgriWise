"""
Layer 4.18: Biological N Fixation Engine — Rhizobium-Legume BNF + Free-Living.

Models atmospheric N₂ fixation by:
  1. Symbiotic fixation: Rhizobium-legume (50-300 kg N/ha/yr)
  2. Free-living fixation: Azotobacter, Azospirillum (5-25 kg N/ha/yr)
  3. Associative fixation: Endophytic bacteria in cereals (5-30 kg N/ha/yr)

Key factors controlling BNF rate:
  - Soil N inhibition: high mineral N (>50 ppm) suppresses nodule activity
  - Temperature: optimal 25-30°C, inhibited below 10°C and above 35°C
  - Soil pH: optimal 6.0-7.0 for Rhizobium; acid soils limit nodulation
  - Molybdenum: essential cofactor for nitrogenase enzyme
  - Water stress: reduces nodule O₂ regulation → less fixation
  - Plant carbohydrate supply: BNF costs ~6g C per g N fixed

References:
  - Peoples et al. (2009): Biological nitrogen fixation: an efficient
    source of N for sustainable agricultural production, Plant & Soil 311:1-18
  - Herridge et al. (2008): Global inputs of biological nitrogen fixation
    in agricultural systems, Plant & Soil 311:1-18
  - Unkovich et al. (2008): Measuring plant-associated nitrogen fixation
    in agricultural systems, ACIAR Monograph 136
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from crop_database.registry import get_crop, CropSpec


# ============================================================================
# BNF parameters now sourced from centralized crop_database (209+ crops)
# CropSpec fields: is_legume, bnf_ndfa_range, bnf_typical_kg_ha, bnf_type
# ============================================================================


@dataclass
class BNFResult:
    """Biological N fixation assessment output."""
    # Total fixation estimate
    total_bnf_kg_ha: float = 0.0          # Total BNF (kg N/ha/season)
    symbiotic_bnf_kg_ha: float = 0.0      # Rhizobium-legume fixation
    free_living_bnf_kg_ha: float = 0.0    # Azotobacter/Azospirillum
    associative_bnf_kg_ha: float = 0.0    # Endophytic (sugarcane, rice)

    # Ndfa (proportion of plant N from atmosphere)
    ndfa_fraction: float = 0.0            # [0-1]
    ndfa_source: str = ""                 # "literature" or "modeled"

    # Limiting factors
    soil_n_inhibition: float = 0.0        # [0-1] How much soil N suppresses BNF
    temperature_factor: float = 1.0       # [0-1] Temperature limitation
    ph_factor: float = 1.0               # [0-1] pH limitation
    moisture_factor: float = 1.0          # [0-1] Water stress limitation

    # Residual N for next crop
    residual_n_kg_ha: float = 0.0         # N remaining in soil from root/nodule turnover
    stover_n_kg_ha: float = 0.0           # N in above-ground residue (if incorporated)

    # Classification
    is_legume: bool = False
    crop_type: str = ""
    notes: str = ""


class BiologicalFixationEngine:
    """Estimates biological nitrogen fixation for legumes and non-legumes."""

    def estimate_bnf(
        self,
        crop_type: str = "wheat",
        yield_target_t_ha: float = 5.0,
        soil_n_ppm: float = 20.0,
        ph: float = 6.5,
        avg_temperature_c: float = 22.0,
        water_stress_index: float = 0.0,
        inoculated: bool = True,
        organic_matter_pct: float = 2.0,
    ) -> BNFResult:
        """Estimate BNF for a given crop and conditions.

        Args:
            crop_type: Crop code
            yield_target_t_ha: Expected yield (t/ha)
            soil_n_ppm: Available soil N (NO₃-N + NH₄-N, ppm)
            ph: Soil pH
            avg_temperature_c: Season average temperature (°C)
            water_stress_index: Water stress [0=none, 1=severe]
            inoculated: Whether legume was inoculated with Rhizobium
            organic_matter_pct: Soil OM (%) — drives free-living fixation
        """
        crop_lower = crop_type.lower()
        spec = get_crop(crop_lower)
        is_legume = spec.is_legume
        has_bnf = spec.bnf_typical_kg_ha > 0 or spec.bnf_type != "free_living_only"

        # 1. Symbiotic BNF (legumes only)
        symbiotic = 0.0
        ndfa = 0.0
        ndfa_source = "none"

        if is_legume and spec.bnf_typical_kg_ha > 0:
            ndfa_min, ndfa_max = spec.bnf_ndfa_range
            typical = spec.bnf_typical_kg_ha

            # Base Ndfa from literature
            ndfa = (ndfa_min + ndfa_max) / 2.0
            ndfa_source = "literature"

            # Soil N inhibition: high mineral N suppresses nodulation
            n_inhibition = self._soil_n_inhibition(soil_n_ppm)
            ndfa *= (1.0 - n_inhibition)

            # Environmental factors
            temp_f = self._temperature_factor(avg_temperature_c)
            ph_f = self._ph_factor(ph)
            moisture_f = max(0.2, 1.0 - water_stress_index * 0.7)

            # Inoculation effect
            inoc_f = 1.0 if inoculated else 0.65  # 35% reduction without inoculation

            # Compute symbiotic BNF
            # Total plant N = yield × grain N% / harvest index × 2 (whole plant)
            grain_n_pct = spec.grain_n_pct / 100.0  # CropSpec stores as %
            harvest_index_val = spec.harvest_index
            total_plant_n = yield_target_t_ha * 1000 * grain_n_pct / max(0.1, harvest_index_val)
            symbiotic = total_plant_n * ndfa * temp_f * ph_f * moisture_f * inoc_f

            # Cap at literature maximum
            symbiotic = min(symbiotic, typical * 1.5)
        else:
            n_inhibition = 0.0
            temp_f = 1.0
            ph_f = 1.0
            moisture_f = 1.0

        # 2. Free-living fixation (all soils)
        free_living = self._free_living_fixation(
            organic_matter_pct, avg_temperature_c, ph,
            max(0, 1.0 - water_stress_index),
        )

        # 3. Associative fixation (crops with bnf_type="associative")
        associative = 0.0
        if spec.bnf_type == "associative" and spec.bnf_typical_kg_ha > 0:
            associative = spec.bnf_typical_kg_ha * temp_f * moisture_f

        # 4. Total BNF
        total = symbiotic + free_living + associative

        # 5. Residual N for next crop
        # ~30% of legume N remains in roots and nodules
        residual_n = symbiotic * 0.30 if is_legume else 0.0
        # Stover N if crop residue is incorporated
        stover_n = symbiotic * 0.40 if is_legume else 0.0

        notes_parts = []
        if is_legume:
            notes_parts.append(
                f"{crop_lower} BNF: {symbiotic:.0f} kg N/ha (Ndfa={ndfa:.2f})"
            )
            if n_inhibition > 0.3:
                notes_parts.append(
                    f"Soil N inhibition: {n_inhibition:.0%} — high mineral N "
                    f"({soil_n_ppm:.0f} ppm) suppresses nodule activity"
                )
            if not inoculated:
                notes_parts.append(
                    "Not inoculated — 35% BNF reduction. "
                    "Consider inoculating with appropriate Rhizobium strain"
                )
        else:
            notes_parts.append(
                f"Non-legume: free-living fixation only ({free_living:.1f} kg N/ha)"
            )
        if free_living > 10:
            notes_parts.append(
                f"Free-living fixation: {free_living:.1f} kg N/ha "
                f"(OM={organic_matter_pct:.1f}%)"
            )

        return BNFResult(
            total_bnf_kg_ha=round(total, 2),
            symbiotic_bnf_kg_ha=round(symbiotic, 2),
            free_living_bnf_kg_ha=round(free_living, 2),
            associative_bnf_kg_ha=round(associative, 2),
            ndfa_fraction=round(ndfa, 4),
            ndfa_source=ndfa_source,
            soil_n_inhibition=round(n_inhibition, 4),
            temperature_factor=round(temp_f, 4),
            ph_factor=round(ph_f, 4),
            moisture_factor=round(moisture_f, 4),
            residual_n_kg_ha=round(residual_n, 2),
            stover_n_kg_ha=round(stover_n, 2),
            is_legume=is_legume,
            crop_type=crop_lower,
            notes="; ".join(notes_parts),
        )

    def _soil_n_inhibition(self, soil_n_ppm: float) -> float:
        """Soil mineral N inhibition of nodulation.

        High soil N (NO₃⁻ + NH₄⁺) suppresses nodule formation and
        nitrogenase activity. Inhibition starts at ~15 ppm and reaches
        maximum at ~60 ppm.

        Reference: Streeter (1988), CRC Crit Rev Plant Sci 7:1-23.
        """
        if soil_n_ppm < 10:
            return 0.0
        # Sigmoidal inhibition
        return min(0.90, 1.0 / (1.0 + math.exp(-0.1 * (soil_n_ppm - 35))))

    def _temperature_factor(self, temp_c: float) -> float:
        """Temperature factor for nitrogenase activity.

        Optimal: 25-30°C. Below 10°C and above 35°C, activity drops sharply.

        Reference: Hungria & Vargas (2000), Field Crops Res 65:151-164.
        """
        if temp_c < 5:
            return 0.05
        elif temp_c < 10:
            return 0.2 + 0.06 * (temp_c - 5)
        elif temp_c < 25:
            return 0.5 + 0.033 * (temp_c - 10)
        elif temp_c <= 30:
            return 1.0
        elif temp_c <= 35:
            return 1.0 - 0.1 * (temp_c - 30)
        else:
            return max(0.1, 0.5 - 0.05 * (temp_c - 35))

    def _ph_factor(self, ph: float) -> float:
        """pH factor for Rhizobium survival and nodulation.

        Optimal pH 6.0-7.0. Acid soils (pH < 5.5) strongly inhibit
        nodulation. Alkaline soils (pH > 8.0) reduce Mo availability.

        Reference: Graham (1992), Can J Microbiol 38:475-484.
        """
        if ph < 4.5:
            return 0.1
        elif ph < 5.5:
            return 0.3 + 0.14 * (ph - 4.5)
        elif ph < 6.0:
            return 0.7 + 0.6 * (ph - 5.5)
        elif ph <= 7.0:
            return 1.0
        elif ph <= 8.0:
            return 1.0 - 0.15 * (ph - 7.0)
        else:
            return max(0.3, 0.85 - 0.1 * (ph - 8.0))

    def _free_living_fixation(
        self,
        om_pct: float,
        temp_c: float,
        ph: float,
        moisture_index: float,
    ) -> float:
        """Free-living N fixation by Azotobacter, Azospirillum, etc.

        Driven by available carbon (from OM decomposition) and
        environmental conditions. Typically 5-25 kg N/ha/yr.

        Reference: Cleveland et al. (1999), Global Biogeochem Cycles 13:623-645.
        """
        # Base rate proportional to OM (carbon source for heterotrophs)
        base = om_pct * 4.0  # ~4 kg N/ha per % OM

        # Temperature
        temp_f = self._temperature_factor(temp_c)

        # pH — free-living fixers are less pH-sensitive than Rhizobium
        ph_f = 1.0
        if ph < 5.0:
            ph_f = 0.5
        elif ph < 5.5:
            ph_f = 0.7

        # Moisture — need aerobic/microaerobic conditions
        moist_f = min(1.0, moisture_index * 1.2)

        result = base * temp_f * ph_f * moist_f
        return max(0.0, min(25.0, result))
