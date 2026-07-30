"""
Layer 4.8b: Lime Requirement Engine — pH Management.

Computes lime requirement to reach target pH using the SMP buffer pH
method (Shoemaker, McLean & Pratt, 1961). Selects liming product
and calculates CaCO3 equivalence.

Why liming matters for nutrients:
  - pH < 5.5: Al/Fe toxicity fixes P, reduces Mo/B availability
  - pH > 7.5: Ca fixes P, reduces Zn/Fe/Mn availability
  - pH 6.0-7.0: Optimal for most nutrient availability
  - Liming raises pH AND adds Ca (may suppress Mg)

Science:
  - SMP buffer pH method (Shoemaker et al., 1961)
  - Adams & Evans buffer (1962) for low-CEC soils
  - Target pH from crop tolerance (from crop_database)
  - Lime rate = f(buffer_pH, target_pH, CEC_effective)
  - CaCO3 equivalence for different products

Products:
  - Agricultural lime (CaCO3): CCE = 100% (reference)
  - Dolomitic lime (CaMg(CO3)2): CCE = 109%, supplies Mg
  - Hydrated lime (Ca(OH)2): CCE = 135%, fast-acting
  - Wood ash: CCE = 40-60%, also supplies K

References:
  - Shoemaker, McLean & Pratt (1961): Ohio Agric. Experiment Station
  - Sims (1996): Lime requirement, SSSA Book Series 5
  - Havlin et al. (2014): Soil Fertility and Fertilizers, 8th ed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from crop_database import get_crop as _get_crop_spec


class LimeProduct(str, Enum):
    """Liming materials with CaCO3 equivalence."""
    AG_LIME = "AG_LIME"           # CaCO3, CCE=100%
    DOLOMITIC = "DOLOMITIC"       # CaMg(CO3)2, CCE=109%
    HYDRATED = "HYDRATED"         # Ca(OH)2, CCE=135%
    WOOD_ASH = "WOOD_ASH"         # Variable, CCE~50%
    PELLETIZED = "PELLETIZED"     # Fine AG_LIME, CCE=100%, fast


# CaCO3 equivalence (%)
CCE = {
    LimeProduct.AG_LIME: 100.0,
    LimeProduct.DOLOMITIC: 109.0,
    LimeProduct.HYDRATED: 135.0,
    LimeProduct.WOOD_ASH: 50.0,
    LimeProduct.PELLETIZED: 100.0,
}

# Fineness factor (ECCE adjustment for particle size)
# Fine lime reacts faster but costs more
FINENESS_FACTOR = {
    LimeProduct.AG_LIME: 0.65,        # 60-mesh standard grind
    LimeProduct.DOLOMITIC: 0.60,      # Dolomite is harder to grind
    LimeProduct.HYDRATED: 1.00,       # Already dissolved
    LimeProduct.WOOD_ASH: 0.90,       # Very fine
    LimeProduct.PELLETIZED: 0.95,     # Processed fine
}


@dataclass
class LimeRequirement:
    """Lime requirement output."""
    # Target pH
    current_ph: float = 0.0
    target_ph: float = 0.0
    ph_adjustment_needed: float = 0.0

    # Lime rates
    caco3_equivalent_kg_ha: float = 0.0      # Pure CaCO3 needed
    product_rate_kg_ha: float = 0.0          # Actual product amount
    product: LimeProduct = LimeProduct.AG_LIME
    product_cce_pct: float = 100.0

    # Application timing
    apply_months_before_planting: int = 3    # Lime takes 2-3 months to react
    split_recommendation: str = ""           # If rate > 4 t/ha, split

    # Soil chemistry context
    buffer_ph: float = 0.0                   # SMP buffer pH
    cec_effective: float = 0.0

    # Flags
    overliming_risk: bool = False
    mg_benefit: bool = False                 # Dolomitic lime also supplies Mg
    notes: str = ""


class LimingEngine:
    """Computes lime requirement from soil pH and buffer pH.

    The SMP buffer pH test measures the soil's resistance to pH change.
    Soils with high CEC (clay/OM) need MORE lime to change pH by 1 unit
    compared to sandy soils.

    SMP buffer pH interpretation:
      buffer_pH < 5.5 → very high lime requirement (> 6 t/ha CaCO3)
      buffer_pH 5.5-6.0 → high (4-6 t/ha)
      buffer_pH 6.0-6.5 → moderate (2-4 t/ha)
      buffer_pH > 6.5 → low (< 2 t/ha)
    """

    # SMP buffer pH → CaCO3 needed (t/ha) to reach pH 6.5
    # Calibrated from Ohio/Midwest data (Shoemaker et al., 1961)
    # Format: (buffer_pH_threshold, CaCO3_t_ha_to_pH_6.5)
    SMP_TABLE = [
        (7.0, 0.0),
        (6.8, 1.0),
        (6.6, 2.0),
        (6.4, 3.0),
        (6.2, 4.0),
        (6.0, 5.5),
        (5.8, 7.0),
        (5.6, 8.5),
        (5.4, 10.0),
        (5.2, 12.0),
        (5.0, 14.0),
    ]

    def compute_lime_requirement(
        self,
        current_ph: float,
        crop_type: str = "corn",
        buffer_ph: Optional[float] = None,
        cec: float = 15.0,
        clay_pct: float = 22.0,
        organic_matter_pct: float = 2.0,
        mg_saturation_low: bool = False,
    ) -> LimeRequirement:
        """Compute lime requirement.

        Args:
            current_ph: Current soil pH (water)
            crop_type: Crop type for target pH lookup
            buffer_ph: SMP buffer pH (if available from lab)
            cec: Cation exchange capacity (cmol(+)/kg)
            clay_pct: Soil clay percentage
            organic_matter_pct: Soil organic matter percentage
            mg_saturation_low: If True, recommend dolomitic lime
        """
        # 1. Target pH from crop tolerance
        spec = _get_crop_spec(crop_type)
        target_ph = getattr(spec, "optimal_ph", 6.5)
        # Ensure target is reasonable
        target_ph = max(5.5, min(7.5, target_ph))

        ph_gap = target_ph - current_ph

        # No liming needed if pH is already at or above target
        if ph_gap <= 0.1:
            return LimeRequirement(
                current_ph=current_ph,
                target_ph=target_ph,
                ph_adjustment_needed=0.0,
                notes="pH is at or above target — no liming needed.",
            )

        # 2. Estimate buffer pH if not provided
        if buffer_ph is None:
            # Estimate from CEC + current pH (simplified)
            # Higher CEC → lower buffer pH (more resistance to change)
            buffer_ph = min(7.0, current_ph + 0.5 + 0.02 * (30 - cec))
            buffer_ph = max(5.0, buffer_ph)

        # 3. Lookup CaCO3 requirement from SMP table
        caco3_to_6_5 = self._interpolate_smp(buffer_ph)

        # Adjust for actual target pH (table is calibrated to 6.5)
        # Linear scaling: each 0.1 pH unit difference from 6.5
        ph_ratio = max(0.3, ph_gap / max(0.1, 6.5 - current_ph))
        caco3_t_ha = caco3_to_6_5 * ph_ratio

        # Convert t/ha to kg/ha
        caco3_kg_ha = caco3_t_ha * 1000.0

        # 4. Select liming product
        if mg_saturation_low:
            product = LimeProduct.DOLOMITIC
            mg_benefit = True
        else:
            product = LimeProduct.AG_LIME
            mg_benefit = False

        cce = CCE[product]
        fineness = FINENESS_FACTOR[product]
        ecce = cce * fineness / 100.0  # Effective CCE fraction

        # Product rate = CaCO3 equivalent / ECCE
        product_rate = caco3_kg_ha / max(0.1, ecce)

        # 5. Application recommendations
        split_rec = ""
        if product_rate > 4000:
            split_rec = (
                f"Rate > 4 t/ha: split into 2 applications "
                f"({product_rate / 2000:.1f} t/ha each, 6 months apart) "
                f"to avoid over-saturation of topsoil."
            )

        overliming = target_ph > 7.0 and current_ph > 6.0

        notes = (
            f"Current pH={current_ph:.1f} → target pH={target_ph:.1f}. "
            f"Buffer pH={buffer_ph:.1f}. "
            f"CaCO3 equivalent: {caco3_t_ha:.1f} t/ha. "
            f"Product: {product.value} ({cce:.0f}% CCE). "
        )
        if mg_benefit:
            notes += "Dolomitic lime selected to also address low Mg. "
        if split_rec:
            notes += split_rec

        return LimeRequirement(
            current_ph=current_ph,
            target_ph=target_ph,
            ph_adjustment_needed=round(ph_gap, 1),
            caco3_equivalent_kg_ha=round(caco3_kg_ha, 0),
            product_rate_kg_ha=round(product_rate, 0),
            product=product,
            product_cce_pct=cce,
            apply_months_before_planting=3 if product != LimeProduct.HYDRATED else 1,
            split_recommendation=split_rec,
            buffer_ph=round(buffer_ph, 1),
            cec_effective=round(cec, 1),
            overliming_risk=overliming,
            mg_benefit=mg_benefit,
            notes=notes,
        )

    def _interpolate_smp(self, buffer_ph: float) -> float:
        """Interpolate SMP table for CaCO3 requirement (t/ha)."""
        if buffer_ph >= 7.0:
            return 0.0
        if buffer_ph <= 5.0:
            return 14.0

        # Linear interpolation between table entries
        for i in range(len(self.SMP_TABLE) - 1):
            ph_high, rate_low = self.SMP_TABLE[i]
            ph_low, rate_high = self.SMP_TABLE[i + 1]
            if buffer_ph <= ph_high and buffer_ph > ph_low:
                fraction = (ph_high - buffer_ph) / (ph_high - ph_low)
                return rate_low + fraction * (rate_high - rate_low)

        return 0.0
