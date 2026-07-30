"""
Layer 8 Engine: Nutrient Interaction Model v8.2.0
=================================================
Liebig's Law of the Minimum + antagonism/synergy matrix.

Scientific basis:
  - Liebig (1840): growth is limited by the scarcest nutrient
  - K-Mg antagonism: excess K suppresses Mg uptake via competitive inhibition
  - P-Zn antagonism: high P induces Zn deficiency in calcareous soils
  - N-P synergy: adequate P enhances N use efficiency by 15-25%
  - N-S synergy: S deficiency reduces N recovery by up to 30%
"""
import logging
from typing import Dict, List, Optional, Tuple
from layer8_prescriptive.schema import (
    ActionCard, ActionType, NutrientInteractionResult, RateRange,
)

logger = logging.getLogger(__name__)

# Antagonism matrix: (A, B) means excess A suppresses B uptake
# Severity: 0-1 (strength of antagonism)
_ANTAGONISMS = [
    ("K",  "Mg", 0.65),   # competitive cation exchange
    ("K",  "Ca", 0.40),   # competitive cation exchange
    ("P",  "Zn", 0.70),   # phosphate-zinc interaction (calcareous soils)
    ("Ca", "B",  0.50),   # calcium-boron antagonism
    ("Fe", "Mn", 0.55),   # iron-manganese competition
    ("N",  "K",  0.25),   # high N can delay K uptake
    ("NH4","K",  0.60),   # ammonium competes with K at root surface
]

# Synergy matrix: (A, B) means adequate A enhances B use efficiency
_SYNERGIES = [
    ("N",  "P",  0.55),   # NUE increases with adequate P
    ("N",  "S",  0.60),   # S deficiency limits N metabolism
    ("P",  "Mo", 0.40),   # Mo needed for N fixation with adequate P
    ("K",  "Mg", 0.30),   # at BALANCED levels, co-transport benefits
    ("Ca", "Mg", 0.25),   # cation balance in soil CEC
]


class NutrientInteractionEngine:
    """
    Applies Liebig's minimum + antagonism/synergy corrections.

    If multiple nutrients are deficient, identifies the most limiting
    one and reorders fertilization to fix it first. Adjusts rates
    up/down based on known interactions.
    """

    def analyze(self,
                action_cards: List[ActionCard],
                nutrient_states: Dict[str, dict]) -> NutrientInteractionResult:
        """Analyze nutrient interactions and return adjustment guidance."""
        # Find deficient nutrients and their severity
        deficiencies = {}
        for nutrient, state in nutrient_states.items():
            prob = state.get("probability_deficient", 0) if isinstance(state, dict) else 0
            if prob > 0.2:
                deficiencies[nutrient.upper()] = prob

        if not deficiencies:
            return NutrientInteractionResult(
                limiting_nutrient=None, limiting_severity=0.0,
                interaction_adjustments={}, antagonisms_detected=[],
                synergies_detected=[], recommended_order=[],
                explain="No significant nutrient deficiencies detected",
            )

        # Liebig's Law: find the most limiting nutrient
        limiting = max(deficiencies.items(), key=lambda x: x[1])
        limiting_nutrient = limiting[0]
        limiting_severity = limiting[1]

        # Check for active antagonisms
        antagonisms_active = []
        adjustments = {n: 1.0 for n in deficiencies}

        for a, b, severity in _ANTAGONISMS:
            # If we are applying A and B is deficient, warn
            a_up = a.upper()
            b_up = b.upper()
            if a_up in deficiencies and b_up in deficiencies:
                antagonisms_active.append((a_up, b_up, severity))
                # Reduce rate of A to avoid suppressing B
                adjustments[a_up] = adjustments.get(a_up, 1.0) * (1.0 - severity * 0.3)

        # Check for synergies
        synergies_active = []
        for a, b, benefit in _SYNERGIES:
            a_up = a.upper()
            b_up = b.upper()
            if a_up in deficiencies and b_up in deficiencies:
                synergies_active.append((a_up, b_up, benefit))
                # Boost rate of A slightly since fixing both is synergistic
                adjustments[a_up] = adjustments.get(a_up, 1.0) * (1.0 + benefit * 0.15)

        # Application order: fix limiting nutrient first
        order = sorted(deficiencies.keys(),
                       key=lambda n: deficiencies[n], reverse=True)

        # Build explanation
        parts = ["Limiting: {} (p={:.0%})".format(limiting_nutrient, limiting_severity)]
        if antagonisms_active:
            pairs = ["{}-{}".format(a, b) for a, b, _ in antagonisms_active]
            parts.append("Antagonisms: {}".format(", ".join(pairs)))
        if synergies_active:
            pairs = ["{}-{}".format(a, b) for a, b, _ in synergies_active]
            parts.append("Synergies: {}".format(", ".join(pairs)))

        result = NutrientInteractionResult(
            limiting_nutrient=limiting_nutrient,
            limiting_severity=limiting_severity,
            interaction_adjustments=adjustments,
            antagonisms_detected=antagonisms_active,
            synergies_detected=synergies_active,
            recommended_order=order,
            explain="; ".join(parts),
        )

        logger.debug("Nutrient interaction: limiting=%s sev=%.2f antag=%d syn=%d",
                     limiting_nutrient, limiting_severity,
                     len(antagonisms_active), len(synergies_active))
        return result

    def apply_adjustments(self,
                          action_cards: List[ActionCard],
                          result: NutrientInteractionResult) -> List[ActionCard]:
        """Apply interaction adjustments to FERTILIZE action rates."""
        if not result.interaction_adjustments:
            return action_cards

        for card in action_cards:
            if card.action_type != ActionType.FERTILIZE or card.rate is None:
                continue
            nutrient = self._infer_nutrient(card)
            adj = result.interaction_adjustments.get(nutrient, 1.0)
            if abs(adj - 1.0) > 0.01:
                orig = card.rate.recommended
                new_rate = round(orig * adj, 1)
                card.rate = RateRange(
                    recommended=new_rate,
                    min_safe=max(0, round(new_rate * 0.7, 1)),
                    max_safe=card.rate.max_safe,
                    unit=card.rate.unit,
                )
                card.nutrient_interaction = result
                card.explain += " [nutrient-adj x{:.2f}]".format(adj)

        return action_cards

    @staticmethod
    def _infer_nutrient(card):
        for ev in card.evidence:
            ref = ev.reference_id.upper()
            if "N_DEF" in ref or "NITROGEN" in ref: return "N"
            if "P_DEF" in ref or "PHOSPH" in ref: return "P"
            if "K_DEF" in ref or "POTASS" in ref: return "K"
            if "S_DEF" in ref: return "S"
            if "ZN" in ref: return "ZN"
            if "MG" in ref: return "MG"
        return "N"


nutrient_engine = NutrientInteractionEngine()
