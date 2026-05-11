"""
Layer 8 Engine: Adoption Probability Model v8.2.0
=================================================
Farmer adoption likelihood using Technology Acceptance Model (TAM).

Scientific basis:
  - Davis (1989) TAM: adoption = f(perceived_usefulness, perceived_ease_of_use)
  - Rogers (2003) Diffusion of Innovations: familiarity + observability
  - Precision ag adoption research: ~60% of DSS recommendations ignored
    (Lowenberg-DeBoer, 2019)
  - Cost sensitivity: recommendations >5% of expected revenue rejected 3x more
  - Nudge theory (Thaler & Sunstein, 2008): simplify + reframe to boost adoption

Implementation:
  - TAM-based composite adoption score per action
  - Cost sensitivity gate (% of expected crop revenue)
  - Familiarity boost (common actions adopted more easily)
  - Nudge strategy selection for low-adoption actions
"""
import logging
from typing import Dict, List
from layer8_prescriptive.schema import (
    ActionCard, ActionType, AdoptionProfile, ConfidenceLevel,
)

logger = logging.getLogger(__name__)

# Perceived ease of use by action type (0=hard, 1=easy)
# Based on precision ag survey data
_EASE_BY_TYPE = {
    ActionType.MONITOR: 0.95,     # just watch
    ActionType.WAIT: 0.98,        # do nothing
    ActionType.SCOUT: 0.80,       # walk the field
    ActionType.IRRIGATE: 0.70,    # requires equipment
    ActionType.HARVEST_PLAN: 0.65,# planning complexity
    ActionType.FERTILIZE: 0.55,   # calibration, timing, equipment
    ActionType.SPRAY: 0.40,       # PPE, calibration, timing, wind
    ActionType.REPLANT: 0.25,     # major disruption, high effort
}

# Perceived usefulness multiplier by confidence level
_USEFULNESS_BY_CONFIDENCE = {
    ConfidenceLevel.HIGH: 0.90,
    ConfidenceLevel.MODERATE: 0.65,
    ConfidenceLevel.LOW: 0.35,
}

# Familiarity: how common this action is in typical farm operations
_FAMILIARITY = {
    ActionType.MONITOR: 0.95,
    ActionType.WAIT: 0.90,
    ActionType.SCOUT: 0.75,
    ActionType.IRRIGATE: 0.80,
    ActionType.HARVEST_PLAN: 0.70,
    ActionType.FERTILIZE: 0.85,   # farmers fertilize often
    ActionType.SPRAY: 0.65,       # less frequent
    ActionType.REPLANT: 0.20,     # rare decision
}

# Cost per action type (relative $/ha for cost sensitivity)
_COST_PER_HA = {
    ActionType.MONITOR: 0,
    ActionType.WAIT: 0,
    ActionType.SCOUT: 5,
    ActionType.IRRIGATE: 30,
    ActionType.HARVEST_PLAN: 10,
    ActionType.FERTILIZE: 80,
    ActionType.SPRAY: 60,
    ActionType.REPLANT: 500,
}

# Expected crop revenue $/ha (rough average, should come from L7)
_DEFAULT_REVENUE_PER_HA = 1200.0

# Cost threshold: actions costing >5% of revenue have adoption penalty
_COST_THRESHOLD_PCT = 0.05


class AdoptionModelEngine:
    """
    Estimates probability a farmer will follow each recommendation.

    Uses TAM (perceived usefulness x perceived ease of use) weighted
    by familiarity and cost sensitivity. Low-adoption actions get
    a nudge strategy to improve compliance.
    """

    def score_adoption(self,
                       action_cards: List[ActionCard],
                       expected_revenue_per_ha: float = _DEFAULT_REVENUE_PER_HA
                       ) -> List[ActionCard]:
        """Score adoption probability for each action card."""
        for card in action_cards:
            ease = _EASE_BY_TYPE.get(card.action_type, 0.5)
            usefulness_mult = _USEFULNESS_BY_CONFIDENCE.get(card.confidence, 0.65)
            # Perceived usefulness = priority_score * confidence multiplier
            usefulness = min(1.0, card.priority_score * 2.0 * usefulness_mult)
            familiarity = _FAMILIARITY.get(card.action_type, 0.5)

            # Cost sensitivity
            action_cost = _COST_PER_HA.get(card.action_type, 50)
            if card.rate and card.action_type == ActionType.FERTILIZE:
                action_cost = card.rate.recommended * 0.5  # rough $/ha from rate
            cost_ratio = action_cost / max(1, expected_revenue_per_ha)
            cost_sensitivity = min(1.0, cost_ratio / _COST_THRESHOLD_PCT)

            # TAM composite: adoption = usefulness * ease * familiarity * (1 - cost_penalty)
            cost_penalty = min(0.5, cost_sensitivity * 0.4)
            adoption_raw = usefulness * ease * (0.6 + 0.4 * familiarity) * (1.0 - cost_penalty)
            adoption_prob = max(0.05, min(0.99, adoption_raw))

            # Identify barriers
            barriers = []
            if ease < 0.5:
                barriers.append("HIGH_COMPLEXITY")
            if cost_sensitivity > 0.7:
                barriers.append("HIGH_COST")
            if familiarity < 0.4:
                barriers.append("UNFAMILIAR_ACTION")
            if usefulness < 0.3:
                barriers.append("LOW_PERCEIVED_VALUE")

            # Select nudge strategy
            if adoption_prob > 0.65:
                nudge = "NONE"
            elif "HIGH_COMPLEXITY" in barriers:
                nudge = "SIMPLIFY"
            elif "HIGH_COST" in barriers:
                nudge = "REFRAME"  # frame cost relative to potential loss
            elif "UNFAMILIAR_ACTION" in barriers:
                nudge = "SOCIAL_PROOF"
            elif "LOW_PERCEIVED_VALUE" in barriers:
                nudge = "REFRAME"
            else:
                nudge = "SIMPLIFY"

            card.adoption = AdoptionProfile(
                adoption_probability=round(adoption_prob, 3),
                perceived_usefulness=round(usefulness, 3),
                perceived_ease=round(ease, 3),
                cost_sensitivity=round(cost_sensitivity, 3),
                familiarity_score=round(familiarity, 3),
                barriers=barriers,
                nudge_strategy=nudge,
            )

        logger.debug("Adoption model: scored %d actions, avg P(adopt)=%.2f",
                     len(action_cards),
                     sum(c.adoption.adoption_probability for c in action_cards
                         if c.adoption) / max(1, len(action_cards)))
        return action_cards


adoption_engine = AdoptionModelEngine()
