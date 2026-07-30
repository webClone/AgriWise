"""
Layer 4.10: Residual N Credit Engine — Previous Crop & Cover Crop Credits.

Estimates nitrogen credits from:
  1. Previous crop residue (legume N fixation, residue decomposition)
  2. Cover crop N release
  3. Manure/compost residual from prior seasons

These credits reduce the current season's fertilizer N requirement.
Ignoring credits leads to over-application (waste + environmental loss).

Science:
  - Legume N fixation: 40-250 kg N/ha depending on species
  - Only 30-60% of fixed N is available to the next crop
  - Release timing depends on residue C:N ratio and temperature
  - C:N < 20: net N release (mineralization)
  - C:N > 30: net N immobilization (microbes tie up soil N)
  - C:N 20-30: neutral

References:
  - Meisinger et al. (2008): Crop nitrogen requirement and fertilization,
    USDA-ARS
  - NRCS Conservation Practice Standard 590 (Nutrient Management)
  - Peoples et al. (2009): The contributions of nitrogen-fixing crop
    legumes to the productivity of agricultural systems, Symbiosis
  - Wagger (1989): Cover crop management effects on nitrogen availability,
    Agronomy Journal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from crop_database.registry import get_crop


# ============================================================================
# Legume fixation and residue credits now sourced from crop_database (209+)
# CropSpec fields: is_legume, bnf_typical_kg_ha, residue_cn_ratio
# ============================================================================

def _compute_non_legume_n_credit(crop_code: str) -> float:
    """Estimate N credit/debit from C:N ratio of crop residue.

    C:N < 20: net N release (mineralization) → positive credit
    C:N 20-30: neutral → ~0
    C:N > 30: net N immobilization → negative credit (microbes tie up soil N)

    Reference: NRCS Conservation Practice Standard 590
    """
    spec = get_crop(crop_code)
    cn = spec.residue_cn_ratio
    if cn < 20:
        return 20.0 - cn  # Max ~20 kg N/ha for very low C:N
    elif cn < 30:
        return 0.0
    else:
        return -(cn - 30) * 0.3  # Approx 0.3 kg immobilization per C:N unit above 30


# Fraction of fixed N available to next crop
# Depends on how much residue is returned to soil vs. harvested
AVAILABILITY_FRACTION = {
    "grain_harvest": 0.35,   # Pods/seeds removed → less residue
    "green_manure": 0.65,    # Entire plant incorporated
    "hay_harvest": 0.20,     # Most biomass removed
    "cover_crop": 0.55,      # Terminated and incorporated
}

# Cover crop N release (kg N/ha)
COVER_CROP_N_RELEASE = {
    "crimson_clover": 80.0,    # Legume cover
    "hairy_vetch": 100.0,      # Excellent N fixer
    "winter_rye": -15.0,       # High C:N → immobilizes N
    "oats": -10.0,             # Cover, moderate C:N
    "radish": 15.0,            # Daikon/tillage radish → rapid decomp
    "mustard": 10.0,           # Brassica cover
    "mixed_legume_grass": 40.0, # Typical mix
}


@dataclass
class ResidualCreditResult:
    """N credit from previous crop / cover crop / manure."""
    # Previous crop
    previous_crop: str = ""
    previous_crop_n_credit_kg_ha: float = 0.0
    previous_crop_fixation_total: float = 0.0
    harvest_type: str = "grain_harvest"
    availability_fraction: float = 0.35

    # Cover crop
    cover_crop: str = ""
    cover_crop_n_credit_kg_ha: float = 0.0
    cover_crop_termination_weeks_ago: int = 0

    # Manure/compost residual
    manure_residual_n_kg_ha: float = 0.0
    manure_years_since: int = 0

    # Total credit
    total_n_credit_kg_ha: float = 0.0

    # Temperature adjustment
    temperature_factor: float = 1.0  # Warmer → faster release

    notes: str = ""


class ResidualCreditEngine:
    """Computes N credits from previous crops, cover crops, and manure.

    These credits directly reduce the fertilizer N recommendation:
      N_fertilizer = N_demand - N_mineralization - N_credits

    Ignoring credits is one of the most common causes of N over-application
    in corn-after-soybean systems (Meisinger et al., 2008).
    """

    def compute_credits(
        self,
        previous_crop: str = "",
        harvest_type: str = "grain_harvest",
        cover_crop: str = "",
        cover_crop_termination_weeks: int = 4,
        manure_applied_kg_n_ha: float = 0.0,
        manure_years_since: int = 1,
        avg_temperature_c: float = 20.0,
    ) -> ResidualCreditResult:
        """Compute total N credits from all sources.

        Args:
            previous_crop: Previous season's crop (lowercase)
            harvest_type: How the previous crop was harvested
            cover_crop: Cover crop species (if any)
            cover_crop_termination_weeks: Weeks since cover crop kill
            manure_applied_kg_n_ha: Organic N applied in manure
            manure_years_since: Years since manure application
            avg_temperature_c: Average temperature for decomposition rate
        """
        prev_lower = previous_crop.lower()
        cover_lower = cover_crop.lower() if cover_crop else ""

        # 1. Temperature adjustment (Q10 = 2.0 from 20°C base)
        temp_factor = 2.0 ** ((avg_temperature_c - 20.0) / 10.0)
        temp_factor = max(0.3, min(2.0, temp_factor))

        # 2. Previous crop N credit
        prev_credit = 0.0
        fixation_total = 0.0

        if prev_lower in ("fallow", ""):
            # Fallow: mineralization of accumulated OM
            prev_credit = 20.0 * temp_factor
        else:
            spec = get_crop(prev_lower)
            if spec.is_legume and spec.bnf_typical_kg_ha > 0:
                # Legume previous crop
                fixation_total = spec.bnf_typical_kg_ha
                avail_frac = AVAILABILITY_FRACTION.get(harvest_type, 0.35)
                prev_credit = fixation_total * avail_frac * temp_factor
            else:
                # Non-legume: compute credit from C:N ratio
                prev_credit = _compute_non_legume_n_credit(prev_lower) * temp_factor

        # 3. Cover crop N credit
        cover_credit = 0.0
        if cover_lower:
            if cover_lower in COVER_CROP_N_RELEASE:
                base_release = COVER_CROP_N_RELEASE[cover_lower]
            else:
                cover_spec = get_crop(cover_lower)
                if cover_spec.is_legume and cover_spec.bnf_typical_kg_ha > 0:
                    base_release = cover_spec.bnf_typical_kg_ha * 0.50
                else:
                    base_release = _compute_non_legume_n_credit(cover_lower)

            # Release timing: older termination → more N released
            # Peak release at 4-6 weeks after termination
            if cover_crop_termination_weeks < 2:
                timing_factor = 0.3  # Not yet decomposed
            elif cover_crop_termination_weeks < 4:
                timing_factor = 0.6
            elif cover_crop_termination_weeks < 8:
                timing_factor = 1.0  # Peak release
            else:
                timing_factor = 0.8  # Some N already lost
            cover_credit = base_release * timing_factor * temp_factor

        # 4. Manure residual
        manure_residual = 0.0
        if manure_applied_kg_n_ha > 0 and manure_years_since > 0:
            # Year 1: 50% of organic N available
            # Year 2: 15% of remaining
            # Year 3: 5% of remaining
            if manure_years_since == 1:
                manure_residual = manure_applied_kg_n_ha * 0.50
            elif manure_years_since == 2:
                manure_residual = manure_applied_kg_n_ha * 0.15
            elif manure_years_since == 3:
                manure_residual = manure_applied_kg_n_ha * 0.05
            # Beyond 3 years: negligible
            manure_residual *= temp_factor

        # 5. Total
        total = max(0.0, prev_credit + cover_credit + manure_residual)
        # Note: allow negative prev_credit to reduce total (immobilization)
        # but total floor at 0 (can't have negative credit overall)

        notes_parts = []
        if prev_credit > 0:
            notes_parts.append(
                f"Previous {prev_lower}: {prev_credit:.0f} kg N/ha credit "
                f"(fixation={fixation_total:.0f}, availability={AVAILABILITY_FRACTION.get(harvest_type, 0.35)*100:.0f}%)"
            )
        elif prev_credit < 0:
            notes_parts.append(
                f"Previous {prev_lower}: {prev_credit:.0f} kg N/ha (net immobilization)"
            )
        if cover_credit != 0:
            notes_parts.append(
                f"Cover crop {cover_lower}: {cover_credit:.0f} kg N/ha"
            )
        if manure_residual > 0:
            notes_parts.append(
                f"Manure residual (year {manure_years_since}): {manure_residual:.0f} kg N/ha"
            )

        return ResidualCreditResult(
            previous_crop=prev_lower,
            previous_crop_n_credit_kg_ha=round(prev_credit, 1),
            previous_crop_fixation_total=round(fixation_total, 1),
            harvest_type=harvest_type,
            availability_fraction=AVAILABILITY_FRACTION.get(harvest_type, 0.35),
            cover_crop=cover_lower,
            cover_crop_n_credit_kg_ha=round(cover_credit, 1),
            cover_crop_termination_weeks_ago=cover_crop_termination_weeks,
            manure_residual_n_kg_ha=round(manure_residual, 1),
            manure_years_since=manure_years_since,
            total_n_credit_kg_ha=round(total, 1),
            temperature_factor=round(temp_factor, 2),
            notes="; ".join(notes_parts) if notes_parts else "No N credits applicable.",
        )
