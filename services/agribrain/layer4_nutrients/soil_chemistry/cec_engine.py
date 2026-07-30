"""
Layer 4.8a: Cation Exchange Capacity & Base Saturation Engine.

Estimates CEC and base saturation from soil texture + organic matter
when user lab data is not available. Provides critical context for:
  - K/Ca/Mg recommendation accuracy (sandy soils can't hold cations)
  - Lime requirement calculation (CEC × desired base saturation)
  - Nutrient holding capacity assessment

Science:
  - CEC estimation: Breeuwsma & Wösten (1986) pedotransfer function
  - Base saturation: SLAN (Sufficiency Levels of Available Nutrients)
  - Ideal base saturation ratios (Bear & Prince 1945):
    Ca: 65-75%, Mg: 10-15%, K: 3-5%, H+Al: 10-15%

References:
  - Breeuwsma & Wösten (1986): Netherlands J. Agric. Science, 34:453-460
  - Mehlich (1984): Comm. in Soil Science & Plant Analysis, 15:1409-1416
  - Helmke & Sparks (1996): Methods of Soil Analysis Part 3
  - Hazelton & Murphy (2007): Interpreting Soil Test Results
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CECResult:
    """Cation Exchange Capacity analysis output."""
    # CEC (cmol(+)/kg or meq/100g)
    cec_estimated: float = 0.0
    cec_source: str = "estimated"  # "user_lab" or "estimated"

    # Base saturation (%)
    base_saturation_pct: float = 0.0
    k_saturation_pct: float = 0.0
    ca_saturation_pct: float = 0.0
    mg_saturation_pct: float = 0.0
    na_saturation_pct: float = 0.0
    h_al_saturation_pct: float = 0.0

    # Interpretation
    cec_class: str = ""  # "very_low", "low", "medium", "high", "very_high"
    nutrient_holding_capacity: str = ""  # "poor", "moderate", "good"
    k_leaching_risk: str = ""  # "high", "moderate", "low"

    # Flags
    k_luxury_consumption_risk: bool = False
    mg_deficiency_risk: bool = False
    ca_mg_ratio_warning: str = ""

    notes: str = ""


class CECEngine:
    """Estimates CEC from soil properties and interprets base saturation.

    CEC is the soil's ability to hold positively-charged nutrients (K+, Ca2+,
    Mg2+, NH4+). Low CEC soils (sandy) cannot hold nutrients and require:
      - Split applications (prevent leaching)
      - More frequent, lower rates
      - Careful timing relative to rainfall

    High CEC soils (clay, high OM) buffer nutrients well but may fixate K
    in clay interlayer positions (K fixation).
    """

    # CEC class boundaries (cmol(+)/kg)
    CEC_CLASSES = [
        (5.0,  "very_low"),
        (10.0, "low"),
        (20.0, "medium"),
        (30.0, "high"),
    ]

    def estimate_cec(
        self,
        clay_pct: float = 22.0,
        sand_pct: float = 40.0,
        organic_matter_pct: float = 2.0,
        ph: Optional[float] = None,
        user_cec: Optional[float] = None,
    ) -> CECResult:
        """Estimate CEC from soil texture + OM.

        Breeuwsma & Wösten (1986) pedotransfer:
          CEC ≈ 0.5 × clay_pct + 3.5 × OM_pct
          (clay contributes ~0.5 meq/100g per %, OM contributes ~3.5)

        This captures the two primary CEC sources:
          1. Clay mineral surfaces (permanent charge)
          2. Organic matter (pH-dependent charge)
        """
        if user_cec is not None:
            cec = user_cec
            source = "user_lab"
        else:
            # Breeuwsma & Wösten (1986) simplified
            clay_contribution = 0.50 * clay_pct
            om_contribution = 3.50 * organic_matter_pct

            # pH-dependent charge (OM CEC increases with pH)
            if ph is not None and ph > 5.5:
                ph_factor = 1.0 + 0.05 * (ph - 5.5)
                om_contribution *= min(ph_factor, 1.3)

            cec = clay_contribution + om_contribution
            source = "estimated"

        # CEC class
        cec_class = "very_high"
        for threshold, label in self.CEC_CLASSES:
            if cec < threshold:
                cec_class = label
                break

        # Nutrient holding capacity
        if cec < 8:
            holding = "poor"
        elif cec < 18:
            holding = "moderate"
        else:
            holding = "good"

        # K leaching risk (inverse of CEC for K+)
        if cec < 8:
            k_leach = "high"
        elif cec < 15:
            k_leach = "moderate"
        else:
            k_leach = "low"

        return CECResult(
            cec_estimated=round(cec, 1),
            cec_source=source,
            cec_class=cec_class,
            nutrient_holding_capacity=holding,
            k_leaching_risk=k_leach,
            notes=f"CEC={cec:.1f} cmol(+)/kg ({cec_class}). "
                  f"Nutrient holding: {holding}. K leaching risk: {k_leach}.",
        )

    def compute_base_saturation(
        self,
        cec: float,
        exchangeable_k_ppm: Optional[float] = None,
        exchangeable_ca_ppm: Optional[float] = None,
        exchangeable_mg_ppm: Optional[float] = None,
        exchangeable_na_ppm: Optional[float] = None,
        soil_ph: Optional[float] = None,
    ) -> CECResult:
        """Compute base saturation percentages from exchangeable cations.

        Conversion: ppm → cmol(+)/kg using equivalent weights
          K:  ppm / 390 = cmol(+)/kg
          Ca: ppm / 200 = cmol(+)/kg
          Mg: ppm / 121.5 = cmol(+)/kg
          Na: ppm / 230 = cmol(+)/kg
        """
        result = self.estimate_cec(user_cec=cec)

        if cec <= 0:
            return result

        # Convert ppm to cmol(+)/kg
        k_cmol = (exchangeable_k_ppm / 390.0) if exchangeable_k_ppm else 0.0
        ca_cmol = (exchangeable_ca_ppm / 200.0) if exchangeable_ca_ppm else 0.0
        mg_cmol = (exchangeable_mg_ppm / 121.5) if exchangeable_mg_ppm else 0.0
        na_cmol = (exchangeable_na_ppm / 230.0) if exchangeable_na_ppm else 0.0

        total_bases = k_cmol + ca_cmol + mg_cmol + na_cmol

        result.k_saturation_pct = round(100.0 * k_cmol / cec, 1)
        result.ca_saturation_pct = round(100.0 * ca_cmol / cec, 1)
        result.mg_saturation_pct = round(100.0 * mg_cmol / cec, 1)
        result.na_saturation_pct = round(100.0 * na_cmol / cec, 1)
        result.base_saturation_pct = round(100.0 * total_bases / cec, 1)
        result.h_al_saturation_pct = round(100.0 - result.base_saturation_pct, 1)

        # Interpret ratios (Bear & Prince 1945 ideal ratios)
        # K: 3-5%, Ca: 65-75%, Mg: 10-15%
        if result.k_saturation_pct > 6.0:
            result.k_luxury_consumption_risk = True
            result.notes += " WARNING: K saturation >6% — luxury consumption risk."
        if result.mg_saturation_pct < 8.0:
            result.mg_deficiency_risk = True
            result.notes += " WARNING: Mg saturation <8% — Mg deficiency risk."

        # Ca:Mg ratio (ideal 5:1 to 8:1)
        if mg_cmol > 0:
            ca_mg_ratio = ca_cmol / mg_cmol
            if ca_mg_ratio > 10:
                result.ca_mg_ratio_warning = f"Ca:Mg={ca_mg_ratio:.1f} (>10:1 — Mg may be suppressed)"
            elif ca_mg_ratio < 3:
                result.ca_mg_ratio_warning = f"Ca:Mg={ca_mg_ratio:.1f} (<3:1 — Ca may be suppressed)"

        return result
