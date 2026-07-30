"""
Layer 4.17: Salinity Engine — Maas-Hoffman Threshold Model + Ion Toxicity.

Models the impact of soil salinity on crop yield and nutrient uptake using:
  - Maas-Hoffman (1977) piecewise linear threshold model
  - Sodium Adsorption Ratio (SAR) for sodicity/structural degradation
  - Ion-specific toxicity (Na⁺, Cl⁻, B) on nutrient uptake
  - Leaching requirement computation

Science:
  Y_relative = 1.0 - b × max(0, EC - EC_threshold)
  where EC_threshold and slope b are crop-specific parameters from
  FAO Irrigation & Drainage Paper 29 (Ayers & Westcot, 1985).

  Salinity reduces nutrient uptake via:
  1. Osmotic stress: reduces water uptake → reduces mass-flow nutrient delivery
  2. Ion competition: Na⁺ displaces K⁺/Ca²⁺; Cl⁻ inhibits NO₃⁻ uptake
  3. Toxicity: direct cellular damage from Na⁺ and Cl⁻

References:
  - Maas & Hoffman (1977): Crop salt tolerance — current assessment,
    J Irrigation & Drainage Div, ASCE 103:115-134
  - Ayers & Westcot (1985): Water quality for agriculture,
    FAO Irrigation & Drainage Paper 29 (Rev. 1)
  - Grattan & Grieve (1999): Salinity–mineral nutrient relations in
    horticultural crops, Scientia Horticulturae 78:127-157
  - Munns & Tester (2008): Mechanisms of salinity tolerance,
    Annu Rev Plant Biol 59:651-681
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from crop_database.registry import get_crop, CropSpec


# ============================================================================
# Salt tolerance now sourced from centralized crop_database (209+ crops)
# Architecture defaults + species overrides from FAO-29 Table 4
# ============================================================================


# Ion-specific toxicity thresholds (mmol/L in soil saturation extract)
_ION_TOXICITY = {
    "Na": {"threshold_mmol": 40.0, "sensitive_crops": 25.0},
    "Cl": {"threshold_mmol": 30.0, "sensitive_crops": 10.0},
    "B":  {"threshold_mg_l": 2.0,  "sensitive_crops": 0.5},
}


@dataclass
class SalinityResult:
    """Salinity assessment output."""
    # Classification
    ec_ds_m: float = 0.0                  # Measured or estimated EC (dS/m)
    severity_class: str = "NONE"          # NONE, LOW, MODERATE, HIGH, CRITICAL
    salinity_source: str = "measured_ec"  # measured_ec | inferred_asmae | corroborated_asmae
    inferred_salinity_pressure: float = 0.0

    # Maas-Hoffman yield impact
    relative_yield: float = 1.0           # [0-1], 1.0 = no yield loss
    yield_loss_pct: float = 0.0           # Percentage yield loss from salinity
    ec_threshold: float = 3.0             # Crop-specific threshold (dS/m)
    ec_slope: float = 10.0                # Yield loss rate (%/dS·m⁻¹)

    # Sodicity (SAR)
    sar: float = 0.0                      # Sodium Adsorption Ratio
    sodicity_risk: str = "LOW"            # LOW, MODERATE, HIGH
    structural_degradation: bool = False  # Clay dispersion risk

    # Ion toxicity
    na_toxicity_risk: float = 0.0         # [0-1]
    cl_toxicity_risk: float = 0.0         # [0-1]
    b_toxicity_risk: float = 0.0          # [0-1]

    # Nutrient uptake reduction
    nutrient_uptake_factors: Dict[str, float] = field(default_factory=dict)
    # {N: 0.85, P: 0.90, K: 0.70, Ca: 0.75, Mg: 0.80}

    # Management
    leaching_requirement: float = 0.0     # Fraction of applied water for leaching
    leaching_depth_mm: float = 0.0        # Leaching water depth (mm)
    notes: str = ""


class SalinityEngine:
    """Assesses salinity impact on crop yield and nutrient uptake."""

    def assess_salinity_impact(
        self,
        ec_ds_m: float = 0.0,
        crop_type: str = "wheat",
        irrigation_water_ec: float = 0.0,
        na_mmol: Optional[float] = None,
        ca_mmol: Optional[float] = None,
        mg_mmol: Optional[float] = None,
        cl_mmol: Optional[float] = None,
        boron_mg_l: Optional[float] = None,
        irrigation_efficiency: float = 0.80,
        inferred_salinity_pressure: float = 0.0,
        historical_salinity_zones: bool = False,
        farmer_validation: bool = False,
        persistent_retrovalidation: bool = False,
    ) -> SalinityResult:
        """Full salinity assessment.

        Args:
            ec_ds_m: Soil saturated paste EC (dS/m). 0 = not measured.
            crop_type: Crop code from crop_database
            irrigation_water_ec: Irrigation water EC (dS/m)
            na_mmol: Sodium concentration in soil extract (mmol/L)
            ca_mmol: Calcium concentration (mmol/L)
            mg_mmol: Magnesium concentration (mmol/L)
            cl_mmol: Chloride concentration (mmol/L)
            boron_mg_l: Boron concentration (mg/L)
            irrigation_efficiency: Irrigation application efficiency [0-1]
            inferred_salinity_pressure: ASMAE inferred salinity pressure [0-1]
            historical_salinity_zones: Whether plot is in a historically saline zone
            farmer_validation: Whether farmer has manually validated salinity
            persistent_retrovalidation: Whether multi-season ASMAE validation is persistent
        """
        crop_lower = crop_type.lower()

        # 1. Get crop-specific Maas-Hoffman parameters from central registry
        spec = get_crop(crop_lower)
        ec_thresh = spec.ec_threshold_ds_m
        slope = spec.ec_slope_pct

        # 2. Determine salinity source and effective EC
        salinity_source = "measured_ec"
        effective_ec = ec_ds_m

        if effective_ec <= 0:
            if inferred_salinity_pressure > 0.0:
                corroborated = (
                    irrigation_water_ec > 0.0
                    or historical_salinity_zones
                    or farmer_validation
                    or persistent_retrovalidation
                )
                if corroborated:
                    salinity_source = "corroborated_asmae"
                else:
                    salinity_source = "inferred_asmae"
                
                if irrigation_water_ec > 0.0:
                    effective_ec = irrigation_water_ec * 1.5
                else:
                    # Map 0.0-1.0 pressure to 0.0-8.0 EC dS/m
                    effective_ec = inferred_salinity_pressure * 8.0
            elif irrigation_water_ec > 0.0:
                effective_ec = irrigation_water_ec * 1.5

        # 3. Maas-Hoffman yield response
        rel_yield, yield_loss = self._maas_hoffman_yield(
            effective_ec, ec_thresh, slope,
        )

        if salinity_source == "inferred_asmae":
            yield_loss = min(35.0, yield_loss)
            rel_yield = 1.0 - yield_loss / 100.0

        # 4. Severity classification
        severity = self._classify_severity(effective_ec)

        # 5. SAR and sodicity
        sar_val = 0.0
        sodicity_risk = "LOW"
        structural_deg = False
        if na_mmol is not None and ca_mmol is not None:
            mg_val = mg_mmol or 0.0
            sar_val = self._sodium_adsorption_ratio(na_mmol, ca_mmol, mg_val)
            sodicity_risk, structural_deg = self._classify_sodicity(
                sar_val, effective_ec,
            )

        # 6. Ion toxicity
        na_tox = self._ion_toxicity_risk(na_mmol, "Na", crop_lower)
        cl_tox = self._ion_toxicity_risk(cl_mmol, "Cl", crop_lower)
        b_tox = self._boron_toxicity_risk(boron_mg_l, crop_lower)

        # 7. Nutrient uptake reduction
        uptake_factors = self._nutrient_uptake_reduction(effective_ec)

        # 8. Leaching requirement
        lr, lr_depth = self._leaching_requirement(
            irrigation_water_ec, ec_thresh, irrigation_efficiency,
        )

        notes_parts = []
        if effective_ec <= 0:
            notes_parts.append("No salinity data available — assuming non-saline")
        elif yield_loss > 5:
            notes_parts.append(
                f"Salinity EC={effective_ec:.1f} dS/m causes {yield_loss:.0f}% yield loss "
                f"(threshold={ec_thresh:.1f} dS/m for {crop_lower})"
            )
        if structural_deg:
            notes_parts.append(
                f"Sodicity risk: SAR={sar_val:.1f} with EC={effective_ec:.1f} — "
                f"clay dispersion and infiltration problems likely"
            )
        if na_tox > 0.5:
            notes_parts.append(f"Sodium toxicity risk: {na_tox:.0%}")
        if b_tox > 0.5:
            notes_parts.append(f"Boron toxicity risk: {b_tox:.0%}")
        if not notes_parts:
            notes_parts.append("Salinity conditions are within safe limits")

        return SalinityResult(
            ec_ds_m=round(effective_ec, 2),
            severity_class=severity,
            salinity_source=salinity_source,
            inferred_salinity_pressure=inferred_salinity_pressure,
            relative_yield=round(rel_yield, 4),
            yield_loss_pct=round(yield_loss, 2),
            ec_threshold=ec_thresh,
            ec_slope=slope,
            sar=round(sar_val, 2),
            sodicity_risk=sodicity_risk,
            structural_degradation=structural_deg,
            na_toxicity_risk=round(na_tox, 3),
            cl_toxicity_risk=round(cl_tox, 3),
            b_toxicity_risk=round(b_tox, 3),
            nutrient_uptake_factors=uptake_factors,
            leaching_requirement=round(lr, 4),
            leaching_depth_mm=round(lr_depth, 1),
            notes="; ".join(notes_parts),
        )

    # ------------------------------------------------------------------
    # Core models
    # ------------------------------------------------------------------

    def _maas_hoffman_yield(
        self, ec: float, threshold: float, slope: float,
    ) -> tuple:
        """Maas-Hoffman piecewise linear model.

        Y_rel = max(0, 1.0 - slope/100 × max(0, EC - threshold))
        """
        if ec <= threshold:
            return 1.0, 0.0
        loss_pct = slope * (ec - threshold)
        loss_pct = min(100.0, loss_pct)
        rel_yield = max(0.0, 1.0 - loss_pct / 100.0)
        return rel_yield, loss_pct

    def _sodium_adsorption_ratio(
        self, na: float, ca: float, mg: float,
    ) -> float:
        """SAR = Na⁺ / sqrt((Ca²⁺ + Mg²⁺) / 2)

        All concentrations in mmol/L (or meq/L for monovalent).
        """
        denom = math.sqrt(max(0.01, (ca + mg) / 2.0))
        return na / denom

    def _classify_sodicity(self, sar: float, ec: float) -> tuple:
        """Classify sodicity risk using SAR × EC diagram.

        Reference: USSL (1954), USDA Handbook 60.
        """
        if sar < 6:
            return "LOW", False
        elif sar < 12:
            # Moderate — but structural problems only at low EC
            structural = ec < 2.0
            return "MODERATE", structural
        elif sar < 18:
            structural = ec < 4.0
            return "HIGH", structural
        else:
            return "CRITICAL", True

    def _classify_severity(self, ec: float) -> str:
        """EC-based severity classification (USDA salinity labs)."""
        if ec <= 0:
            return "NONE"
        elif ec <= 2.0:
            return "LOW"
        elif ec <= 4.0:
            return "MODERATE"
        elif ec <= 8.0:
            return "HIGH"
        else:
            return "CRITICAL"

    def _ion_toxicity_risk(
        self, concentration: Optional[float], ion: str, crop: str,
    ) -> float:
        """Ion-specific toxicity risk [0-1]."""
        if concentration is None:
            return 0.0
        params = _ION_TOXICITY.get(ion, {})
        threshold = params.get("threshold_mmol", 999.0)
        # Use salt_tolerance_class from registry for sensitivity classification
        spec = get_crop(crop)
        is_sensitive = spec.salt_tolerance_class == "sensitive"
        if is_sensitive:
            threshold = params.get("sensitive_crops", threshold)
        if concentration <= threshold * 0.5:
            return 0.0
        return min(1.0, (concentration - threshold * 0.5) / threshold)

    def _boron_toxicity_risk(
        self, b_mg_l: Optional[float], crop: str,
    ) -> float:
        """Boron toxicity risk [0-1]."""
        if b_mg_l is None:
            return 0.0
        params = _ION_TOXICITY["B"]
        threshold = params["threshold_mg_l"]
        spec = get_crop(crop)
        is_sensitive = spec.salt_tolerance_class == "sensitive"
        if is_sensitive:
            threshold = params["sensitive_crops"]
        if b_mg_l <= threshold * 0.5:
            return 0.0
        return min(1.0, (b_mg_l - threshold * 0.5) / threshold)

    def _nutrient_uptake_reduction(self, ec: float) -> Dict[str, float]:
        """Compute nutrient uptake reduction factors due to salinity.

        Salinity reduces nutrient uptake through:
        1. Osmotic stress → reduced transpiration → less mass-flow delivery
        2. Ion competition: Na⁺ competes with K⁺/Ca²⁺; Cl⁻ with NO₃⁻

        Reference: Grattan & Grieve (1999), Scientia Hort 78:127-157.
        """
        if ec <= 1.0:
            return {"N": 1.0, "P": 1.0, "K": 1.0, "Ca": 1.0, "Mg": 1.0}

        # Each nutrient has different sensitivity to salinity
        # K and Ca are most affected (Na competition)
        osmotic_factor = max(0.3, 1.0 - 0.06 * ec)  # General osmotic reduction
        return {
            "N":  round(max(0.3, 1.0 - 0.04 * ec), 3),   # Cl⁻ inhibits NO₃⁻ uptake
            "P":  round(max(0.4, 1.0 - 0.03 * ec), 3),   # P relatively less affected
            "K":  round(max(0.2, 1.0 - 0.08 * ec), 3),   # Na⁺ strongly competes with K⁺
            "Ca": round(max(0.2, 1.0 - 0.07 * ec), 3),   # Na⁺ competes with Ca²⁺
            "Mg": round(max(0.3, 1.0 - 0.05 * ec), 3),   # Moderate competition
        }

    def _leaching_requirement(
        self, ec_water: float, ec_threshold: float, efficiency: float,
    ) -> tuple:
        """Compute leaching requirement to maintain soil EC below threshold.

        LR = EC_w / (5 × EC_e - EC_w)
        where EC_e = target soil extract EC (= crop threshold)

        Reference: Ayers & Westcot (1985), FAO-29.
        """
        if ec_water <= 0 or ec_threshold <= 0:
            return 0.0, 0.0
        denom = 5.0 * ec_threshold - ec_water
        if denom <= 0:
            return 0.30, 150.0  # Extreme: 30% leaching fraction
        lr = ec_water / denom
        lr = min(0.30, max(0.0, lr))
        # Convert to depth assuming 500mm seasonal irrigation
        lr_depth = 500.0 * lr / max(0.5, efficiency)
        return lr, lr_depth
