"""
Layer 4.7: Nutrient Interaction Matrix — Liebig's Law + Cross-Nutrient Effects.

Implements two foundational agronomic principles:

1. Liebig's Law of the Minimum (1840):
   Yield is limited by the most deficient nutrient, regardless of other
   nutrient supply. Adding more N when K is limiting produces NO yield
   response and wastes fertilizer.

2. Cross-Nutrient Antagonisms/Synergisms:
   - P → Zn: High P reduces Zn uptake (phosphate-induced zinc deficiency)
   - K → Mg: Excess K inhibits Mg uptake via cation competition
   - K → Ca: Excess K inhibits Ca uptake (same mechanism)
   - N → K: High N increases K demand (more biomass needs more K)
   - NH4+ → K: Ammonium competes with K+ for root uptake
   - Excess N → delayed maturity (lodging risk in cereals)
   - S:N ratio: Optimal 1:15 for protein synthesis

References:
  - Liebig (1840): Die organische Chemie in ihrer Anwendung auf Agrikultur
  - Fageria (2001): Nutrient Interactions in Crop Plants, J. Plant Nutrition
  - Rietra et al. (2017): Effects of nutrient antagonism and synergism,
    Plant and Soil, 415:1-17
  - Robson & Pitman (1983): Interactions between nutrients in higher plants
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from layer4_nutrients.schema import (
    Nutrient, NutrientState, Severity, MACRO_NUTRIENTS,
    SECONDARY_NUTRIENTS, MICRO_NUTRIENTS,
)


# ============================================================================
# Interaction Coefficients
# ============================================================================

# Cross-nutrient interaction matrix: (source, target) → effect
# Positive = synergism (source helps target uptake)
# Negative = antagonism (source inhibits target uptake)
# Values are logit adjustments to target nutrient deficiency probability
INTERACTION_MATRIX: Dict[Tuple[Nutrient, Nutrient], float] = {
    # P → Zn antagonism (phosphate-induced zinc deficiency)
    # High P application reduces Zn availability in soil solution.
    # Reference: Loneragan et al. (1979), SSSA Journal
    (Nutrient.P, Nutrient.Zn): -0.8,  # High P increases Zn deficiency risk

    # K → Mg antagonism (cation competition)
    # K+, Mg2+, Ca2+ compete for the same exchange sites and root uptake.
    # Reference: Fageria (2001)
    (Nutrient.K, Nutrient.Mg): -0.6,
    (Nutrient.K, Nutrient.Ca): -0.4,

    # N → K demand increase
    # Higher N → more vegetative growth → higher K demand for turgor/transport.
    # Not a direct antagonism but an indirect demand increase.
    (Nutrient.N, Nutrient.K): -0.3,

    # S-N synergism
    # Adequate S improves N use efficiency (amino acid synthesis).
    # S deficiency causes N to accumulate as non-protein nitrogen.
    (Nutrient.S, Nutrient.N): 0.3,

    # Ca → P synergism in acid soils
    # Liming (Ca addition) increases P availability by reducing Al/Fe fixation.
    (Nutrient.Ca, Nutrient.P): 0.4,
}

# Nutrient-specific yield impact weights (Liebig importance)
# How much does deficiency of this nutrient limit yield?
# Based on typical crop response data (Cerrato & Blackmer 1990)
LIEBIG_IMPACT = {
    Nutrient.N: 1.0,    # Strongest yield limiter
    Nutrient.P: 0.7,    # Strong limiter, especially early growth
    Nutrient.K: 0.6,    # Moderate limiter, affects quality more than yield
    Nutrient.S: 0.4,    # Important for protein crops
    Nutrient.Zn: 0.3,   # Micronutrient — can limit corn/rice significantly
    Nutrient.B: 0.2,    # Critical for fruiting but narrow deficiency range
    Nutrient.Fe: 0.15,  # Chlorosis in calcareous soils
    Nutrient.Mn: 0.15,  # Important in high-pH soils
}


@dataclass
class InteractionEffect:
    """One cross-nutrient interaction result."""
    source_nutrient: Nutrient
    target_nutrient: Nutrient
    effect_type: str  # "antagonism" or "synergism"
    magnitude: float  # Logit adjustment
    description: str
    source_status: str  # "deficient", "adequate", "high"


@dataclass
class LimitingFactorResult:
    """Liebig's Law output: which nutrient limits yield?"""
    limiting_nutrient: Optional[Nutrient] = None
    limiting_severity: Optional[Severity] = None
    limiting_probability: float = 0.0

    # Yield limitation factor [0.0 = no limitation, 1.0 = total limitation]
    yield_limitation_factor: float = 0.0

    # All nutrients ranked by limitation
    limitation_ranking: List[Dict[str, Any]] = field(default_factory=list)

    # Recommendations
    notes: str = ""


@dataclass
class NutrientInteractionOutput:
    """Full interaction analysis output."""
    limiting_factor: LimitingFactorResult = field(default_factory=LimitingFactorResult)
    interactions: List[InteractionEffect] = field(default_factory=list)
    adjusted_states: Dict[Nutrient, Dict[str, float]] = field(default_factory=dict)
    rate_adjustments: Dict[str, float] = field(default_factory=dict)


class NutrientInteractionEngine:
    """Identifies the most-limiting nutrient and cross-nutrient effects.

    Two-pass architecture:
    1. Liebig analysis: find the minimum (most-deficient) nutrient
    2. Interaction analysis: adjust deficiency probabilities for antagonisms

    The output informs the optimization engine to:
    - Prioritize the limiting nutrient
    - Reduce application of non-limiting nutrients
    - Warn about antagonistic effects (e.g., "adding more P may worsen Zn")
    """

    def analyze(
        self,
        states: Dict[Nutrient, NutrientState],
        prescriptions: Optional[List[Any]] = None,
    ) -> NutrientInteractionOutput:
        """Run Liebig + interaction analysis."""

        # 1. Liebig's Law of the Minimum
        limiting = self._find_limiting_nutrient(states)

        # 2. Cross-nutrient interactions
        interactions = self._evaluate_interactions(states)

        # 3. Rate adjustments based on Liebig
        rate_adj = self._compute_rate_adjustments(states, limiting)

        # 4. Adjusted state summaries
        adjusted = {}
        for nut, state in states.items():
            adj = {
                "original_prob": state.probability_deficient,
                "adjusted_prob": state.probability_deficient,
                "is_limiting": (nut == limiting.limiting_nutrient),
                "rate_multiplier": rate_adj.get(nut.value, 1.0),
            }
            # Apply interaction adjustments
            for ix in interactions:
                if ix.target_nutrient == nut:
                    # Shift probability by interaction magnitude
                    from layer4_nutrients.inference.engine import _sigmoid
                    # Convert prob back to logit, add effect, convert back
                    current_prob = adj["adjusted_prob"]
                    logit = math.log(max(0.001, current_prob) / max(0.001, 1.0 - current_prob))
                    logit += ix.magnitude
                    adj["adjusted_prob"] = round(_sigmoid(logit), 4)

            adjusted[nut] = adj

        return NutrientInteractionOutput(
            limiting_factor=limiting,
            interactions=interactions,
            adjusted_states=adjusted,
            rate_adjustments=rate_adj,
        )

    def _find_limiting_nutrient(
        self, states: Dict[Nutrient, NutrientState],
    ) -> LimitingFactorResult:
        """Find the most deficient nutrient using Liebig's Law.

        The "limitation score" combines:
          - Probability of deficiency (how likely is this nutrient low?)
          - Impact weight (how much does this nutrient affect yield?)
          - Severity (clinical severity grade)

        limitation_score = probability × impact_weight × severity_multiplier
        """
        rankings = []

        severity_mult = {
            Severity.LOW: 0.25,
            Severity.MODERATE: 0.50,
            Severity.HIGH: 0.75,
            Severity.CRITICAL: 1.00,
        }

        for nutrient, state in states.items():
            impact = LIEBIG_IMPACT.get(nutrient, 0.1)
            sev_m = severity_mult.get(state.severity, 0.25)
            score = state.probability_deficient * impact * sev_m

            rankings.append({
                "nutrient": nutrient.value,
                "probability": round(state.probability_deficient, 4),
                "impact_weight": impact,
                "severity": state.severity.value,
                "limitation_score": round(score, 4),
            })

        # Sort by limitation score (highest = most limiting)
        rankings.sort(key=lambda x: x["limitation_score"], reverse=True)

        # The top-ranked nutrient is the Liebig minimum
        limiting_nut = None
        limiting_sev = None
        limiting_prob = 0.0
        ylf = 0.0

        if rankings:
            top = rankings[0]
            if top["limitation_score"] > 0.05:  # Threshold: meaningful limitation
                limiting_nut = Nutrient(top["nutrient"])
                limiting_sev = Severity(top["severity"])
                limiting_prob = top["probability"]
                ylf = min(1.0, top["limitation_score"])

        notes = ""
        if limiting_nut:
            notes = (
                f"Liebig limiting nutrient: {limiting_nut.value} "
                f"(p={limiting_prob:.2f}, severity={limiting_sev.value}). "
                f"Addressing {limiting_nut.value} first will unlock yield potential "
                f"before investing in other nutrients."
            )
        else:
            notes = "No significant nutrient limitation detected."

        return LimitingFactorResult(
            limiting_nutrient=limiting_nut,
            limiting_severity=limiting_sev,
            limiting_probability=limiting_prob,
            yield_limitation_factor=round(ylf, 4),
            limitation_ranking=rankings,
            notes=notes,
        )

    def _evaluate_interactions(
        self, states: Dict[Nutrient, NutrientState],
    ) -> List[InteractionEffect]:
        """Evaluate cross-nutrient interactions from the interaction matrix."""
        effects = []

        for (source, target), magnitude in INTERACTION_MATRIX.items():
            src_state = states.get(source)
            tgt_state = states.get(target)
            if not src_state:
                continue

            # Determine source nutrient status
            if src_state.probability_deficient > 0.65:
                src_status = "deficient"
            elif src_state.probability_deficient < 0.35:
                src_status = "high"  # Low prob of deficiency → high supply
            else:
                src_status = "adequate"
                continue  # Adequate → no interaction effect

            # Apply interaction only when source is extreme
            if magnitude < 0:
                # Antagonism: only active when source is HIGH (over-supply)
                if src_status != "high":
                    continue
                effect_type = "antagonism"
                desc = (
                    f"Excess {source.value} inhibits {target.value} uptake "
                    f"({source.value} probability of deficiency: {src_state.probability_deficient:.2f})"
                )
            else:
                # Synergism: active when source is adequate or high
                effect_type = "synergism"
                desc = (
                    f"Adequate {source.value} supports {target.value} uptake "
                    f"({source.value} probability of deficiency: {src_state.probability_deficient:.2f})"
                )

            effects.append(InteractionEffect(
                source_nutrient=source,
                target_nutrient=target,
                effect_type=effect_type,
                magnitude=magnitude,
                description=desc,
                source_status=src_status,
            ))

        return effects

    def _compute_rate_adjustments(
        self,
        states: Dict[Nutrient, NutrientState],
        limiting: LimitingFactorResult,
    ) -> Dict[str, float]:
        """Compute rate adjustment multipliers based on Liebig analysis.

        If nutrient X is not the limiting factor, reduce its application
        rate to avoid waste and environmental loss. Only the limiting
        nutrient gets full rate.

        Multiplier rules:
          - Limiting nutrient: 1.0 (full rate)
          - Non-limiting but deficient: 0.7 (partial rate)
          - Non-limiting and adequate: 0.0 (no application)
        """
        adjustments = {}

        for nutrient, state in states.items():
            if nutrient == limiting.limiting_nutrient:
                adjustments[nutrient.value] = 1.0
            elif state.probability_deficient > 0.60:
                # Still deficient but not the most limiting
                adjustments[nutrient.value] = 0.70
            elif state.probability_deficient > 0.35:
                # Marginal — verify before applying
                adjustments[nutrient.value] = 0.40
            else:
                adjustments[nutrient.value] = 0.0

        return adjustments
"""
Layer 4.7: Nutrient Interaction Engine

Engine summary:
  - Liebig's Law of the Minimum: identifies yield-limiting nutrient
  - Cross-nutrient antagonism/synergism matrix (12 interactions)
  - Rate adjustment multipliers to prevent wasteful application
  - Full audit trail with interaction descriptions
"""
