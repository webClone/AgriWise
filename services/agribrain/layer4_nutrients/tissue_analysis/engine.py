"""
Layer 4.12: Plant Tissue Analysis Integration Engine.

Interprets plant tissue test results using:
  1. Sufficiency Range Approach (SRA): compare vs. critical levels
  2. DRIS (Diagnosis and Recommendation Integrated System): nutrient ratios
  3. Stage-specific critical concentrations

Plant tissue analysis is the STRONGEST evidence for nutrient status
because it directly measures what the plant has absorbed, unlike:
  - Soil tests (which measure availability, not uptake)
  - Spectral indices (which measure canopy reflectance, not nutrition)

Critical tissue sampling rules:
  - Correct plant part (ear leaf for corn, flag leaf for wheat)
  - Correct growth stage (V6-VT for corn, flag leaf for wheat)
  - Clean samples (no dust, no dead tissue)
  - Sufficient sample size (20+ plants)

All tissue norms and DRIS ratios are sourced from the centralized
crop_database (209+ crops).  Per-crop overrides exist for corn, wheat,
rice, soybean, potato, tomato, citrus, olive, cotton.  All other crops
inherit scientifically appropriate norms from their architecture class
(cereal, legume, vegetable, perennial, tropical_tree, cotton).

References:
  - Walworth & Sumner (1987): DRIS system for interpreting plant analyses,
    Advances in Soil Science, 6:149-188
  - Havlin et al. (2014): Soil Fertility and Fertilizers, 8th ed.
  - Mills & Jones (1996): Plant Analysis Handbook II
  - Reuter & Robinson (1997): Plant Analysis: An Interpretation Manual
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from crop_database import get_crop
from layer4_nutrients.schema import Nutrient, Severity


class TissueStatus(str, Enum):
    DEFICIENT = "DEFICIENT"       # Below critical level
    LOW = "LOW"                   # Below sufficiency range
    SUFFICIENT = "SUFFICIENT"     # Within normal range
    HIGH = "HIGH"                 # Above normal but not toxic
    EXCESSIVE = "EXCESSIVE"       # Potential toxicity / luxury consumption


@dataclass
class TissueNutrientResult:
    """Interpretation of one nutrient from tissue test."""
    nutrient: str = ""
    concentration: float = 0.0
    unit: str = "%"
    status: TissueStatus = TissueStatus.SUFFICIENT
    severity: Severity = Severity.LOW

    critical_level: float = 0.0
    sufficiency_range: str = ""  # "3.0-4.5%"

    # DRIS
    dris_index: float = 0.0  # Negative = deficient, positive = excess
    dris_order: int = 0      # 1 = most limiting

    logit_contribution: float = 0.0  # For inference engine integration
    notes: str = ""


@dataclass
class TissueAnalysisOutput:
    """Full tissue analysis interpretation."""
    crop_type: str = ""
    growth_stage: str = ""
    sampling_quality: str = "unknown"  # "good", "acceptable", "poor"

    nutrient_results: List[TissueNutrientResult] = field(default_factory=list)

    # DRIS summary
    dris_order: List[str] = field(default_factory=list)  # Most limiting first
    most_limiting: str = ""
    nutrient_balance_index: float = 0.0  # NBI: sum of absolute DRIS indices

    # Integration with inference
    logit_adjustments: Dict[str, float] = field(default_factory=dict)

    notes: str = ""


class TissueAnalysisEngine:
    """Interprets plant tissue test results for nutrient diagnosis.

    Two complementary approaches:
    1. Sufficiency Range: simple threshold comparison
    2. DRIS: ratio-based, identifies relative imbalances

    All norms are sourced from the centralized crop_database (209+ crops).
    The output produces strong logit adjustments for the L4 inference
    engine (weight = 3.5, highest after soil lab).
    """

    def interpret(
        self,
        tissue_data: Dict[str, float],
        crop_type: str = "corn",
        growth_stage: str = "vegetative",
    ) -> TissueAnalysisOutput:
        """Interpret tissue test results.

        Args:
            tissue_data: {nutrient: concentration}
                Example: {"N": 2.8, "P": 0.22, "K": 1.6, "S": 0.15, "Zn": 18.0}
                Macros in %, micros in ppm
            crop_type: Crop for norm lookup (any of 209+ crops supported)
            growth_stage: Growth stage for stage-specific norms
        """
        spec = get_crop(crop_type)
        stage_lower = growth_stage.lower()

        norms = spec.tissue_norms  # {nutrient: {stage: (def, low, suf, high)}}
        results = []
        logit_adj = {}

        for nutrient_key, concentration in tissue_data.items():
            nut_upper = nutrient_key.upper()
            nut_norms = norms.get(nut_upper, norms.get(nutrient_key, {}))
            if not nut_norms:
                continue

            # Get stage-specific norms (fall back to vegetative)
            stage_norms = nut_norms.get(stage_lower, nut_norms.get("vegetative"))
            if not stage_norms:
                continue

            deficient_below, low_below, sufficient_max, high_above = stage_norms

            # Classify
            if concentration < deficient_below:
                status = TissueStatus.DEFICIENT
                severity = Severity.CRITICAL
            elif concentration < low_below:
                status = TissueStatus.LOW
                severity = Severity.HIGH
            elif concentration <= sufficient_max:
                status = TissueStatus.SUFFICIENT
                severity = Severity.LOW
            elif concentration <= high_above:
                status = TissueStatus.HIGH
                severity = Severity.LOW
            else:
                status = TissueStatus.EXCESSIVE
                severity = Severity.MODERATE

            # Logit contribution for inference integration
            # Tissue test is strong evidence (weight ~3.5)
            if status == TissueStatus.DEFICIENT:
                logit = 4.0  # Very strong deficiency signal
            elif status == TissueStatus.LOW:
                logit = 2.5
            elif status == TissueStatus.SUFFICIENT:
                logit = -2.5  # Strong adequacy signal
            elif status == TissueStatus.HIGH:
                logit = -3.5
            else:  # EXCESSIVE
                logit = -4.0

            unit = "ppm" if nut_upper in ("Zn", "B", "Fe", "Mn", "Cu", "Mo") else "%"

            results.append(TissueNutrientResult(
                nutrient=nut_upper,
                concentration=concentration,
                unit=unit,
                status=status,
                severity=severity,
                critical_level=deficient_below,
                sufficiency_range=f"{low_below}-{sufficient_max}{unit}",
                logit_contribution=logit,
                notes=f"{nut_upper}={concentration}{unit}: {status.value}",
            ))

            logit_adj[nut_upper] = logit

        # DRIS analysis
        dris_indices = self._compute_dris(tissue_data, spec)
        dris_order = sorted(dris_indices.keys(), key=lambda k: dris_indices[k])
        most_limiting = dris_order[0] if dris_order else ""

        # Update results with DRIS indices
        for i, nut in enumerate(dris_order):
            for r in results:
                if r.nutrient == nut:
                    r.dris_index = round(dris_indices[nut], 2)
                    r.dris_order = i + 1

        # Nutrient Balance Index
        nbi = sum(abs(v) for v in dris_indices.values()) if dris_indices else 0.0

        # Sampling quality assessment
        quality = "good"
        if len(tissue_data) < 3:
            quality = "poor"
        elif len(tissue_data) < 5:
            quality = "acceptable"

        return TissueAnalysisOutput(
            crop_type=spec.code,
            growth_stage=stage_lower,
            sampling_quality=quality,
            nutrient_results=results,
            dris_order=dris_order,
            most_limiting=most_limiting,
            nutrient_balance_index=round(nbi, 2),
            logit_adjustments=logit_adj,
            notes=f"DRIS most-limiting: {most_limiting}. NBI={nbi:.1f}.",
        )

    def _compute_dris(
        self,
        tissue_data: Dict[str, float],
        spec,
    ) -> Dict[str, float]:
        """Compute DRIS indices for nutrient balance assessment.

        DRIS index for nutrient A:
          I(A) = mean of all f(A/B) functions where A appears

        f(A/B) = ((A/B - norm_mean) / norm_cv) × (1000/norm_mean)

        Negative index = most limiting (relative deficiency)
        Positive index = relative excess

        Norms sourced from crop_database CropSpec.dris_norms.
        """
        dris_norms = spec.dris_norms
        if not dris_norms:
            return {}

        # Compute all ratio functions
        ratio_functions: Dict[str, List[float]] = {}

        for ratio_name, (norm_mean, norm_cv) in dris_norms.items():
            parts = ratio_name.split("/")
            if len(parts) != 2:
                continue
            a_key, b_key = parts

            a_val = tissue_data.get(a_key, tissue_data.get(a_key.lower()))
            b_val = tissue_data.get(b_key, tissue_data.get(b_key.lower()))

            if a_val is None or b_val is None or b_val == 0:
                continue

            observed_ratio = a_val / b_val

            # DRIS function
            f_val = ((observed_ratio - norm_mean) / max(0.01, norm_cv)) * (1000.0 / norm_mean)

            # A gets +f, B gets -f
            ratio_functions.setdefault(a_key, []).append(f_val)
            ratio_functions.setdefault(b_key, []).append(-f_val)

        # Average functions per nutrient
        indices = {}
        for nut, funcs in ratio_functions.items():
            if funcs:
                indices[nut] = sum(funcs) / len(funcs)

        return indices
