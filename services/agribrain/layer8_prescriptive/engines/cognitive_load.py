"""
Layer 8 Engine: Cognitive Load Manager v8.2.0
=============================================
Decision fatigue modeling + action grouping.

Scientific basis:
  - Baumeister (1998): ego depletion reduces decision quality after ~5 choices
  - Hick's Law: reaction time increases logarithmically with choices
  - Miller (1956): working memory capacity is 7 +/- 2 items
  - Action grouping reduces perceived complexity (Tversky, 1977)

Implementation:
  - Complexity score per action type (MONITOR=1 ... SPRAY=5)
  - Maximum concurrent recommendation cap (default: 5)
  - Total complexity budget per session (default: 15)
  - Group related actions (same zone, same pest, same nutrient)
  - Suppress low-delta actions (diminishing marginal value)
"""
import logging
from typing import Dict, List, Any
from layer8_prescriptive.schema import (
    ActionCard, ActionType, CognitiveLoadProfile,
)

logger = logging.getLogger(__name__)

# Complexity score per action type (subjective cognitive load)
_COMPLEXITY = {
    ActionType.MONITOR: 1,
    ActionType.WAIT: 1,
    ActionType.SCOUT: 2,
    ActionType.IRRIGATE: 3,
    ActionType.HARVEST_PLAN: 3,
    ActionType.FERTILIZE: 4,
    ActionType.SPRAY: 5,
    ActionType.REPLANT: 5,
}

# Defaults
_MAX_ACTIONS = 5           # max actions presented simultaneously
_MAX_COMPLEXITY = 15       # total complexity budget
_MIN_SCORE_DELTA = 0.03    # suppress actions with < this delta from previous


class CognitiveLoadEngine:
    """
    Manages farmer decision fatigue by pruning, grouping, and capping
    the number of simultaneous recommendations.

    Psychology: showing 8 actions with similar scores causes choice paralysis.
    Better to show 3-5 high-confidence, clearly differentiated actions.
    """

    def __init__(self, max_actions=_MAX_ACTIONS, max_complexity=_MAX_COMPLEXITY):
        self.max_actions = max_actions
        self.max_complexity = max_complexity

    def manage_load(self, action_cards: List[ActionCard]) -> tuple:
        """
        Prune and group actions for cognitive relief.

        Returns:
            (filtered_cards, CognitiveLoadProfile)
        """
        if not action_cards:
            return action_cards, CognitiveLoadProfile(
                total_complexity=0, max_complexity_budget=self.max_complexity,
                actions_presented=0, actions_suppressed=0,
                action_groups=[], fatigue_warning=False,
            )

        # Sort by priority (should already be sorted, but enforce)
        sorted_cards = sorted(action_cards, key=lambda c: c.priority_score, reverse=True)

        # Phase 1: Suppress low-delta actions
        filtered = [sorted_cards[0]]
        suppressed = 0
        for i in range(1, len(sorted_cards)):
            delta = filtered[-1].priority_score - sorted_cards[i].priority_score
            if delta < _MIN_SCORE_DELTA and len(filtered) >= 3:
                # Similar score to previous + we already have enough
                suppressed += 1
                continue
            filtered.append(sorted_cards[i])

        # Phase 2: Apply complexity budget
        kept = []
        total_complexity = 0.0
        for card in filtered:
            c = _COMPLEXITY.get(card.action_type, 3)
            if total_complexity + c > self.max_complexity and len(kept) >= 2:
                suppressed += 1
                continue
            if len(kept) >= self.max_actions:
                suppressed += 1
                continue
            kept.append(card)
            total_complexity += c

        # Phase 3: Group related actions
        groups = self._group_actions(kept)

        fatigue = total_complexity > self.max_complexity * 0.8

        profile = CognitiveLoadProfile(
            total_complexity=total_complexity,
            max_complexity_budget=self.max_complexity,
            actions_presented=len(kept),
            actions_suppressed=suppressed,
            action_groups=groups,
            fatigue_warning=fatigue,
        )

        logger.debug("Cognitive load: %d presented, %d suppressed, complexity=%.0f/%d",
                     len(kept), suppressed, total_complexity, self.max_complexity)
        return kept, profile

    def _group_actions(self, cards: List[ActionCard]) -> List[Dict[str, Any]]:
        """Group related actions by type and zone."""
        groups = {}
        for card in cards:
            key = card.action_type.value
            if key not in groups:
                groups[key] = {
                    "action_type": key,
                    "count": 0,
                    "action_ids": [],
                    "zones": set(),
                    "total_score": 0.0,
                }
            groups[key]["count"] += 1
            groups[key]["action_ids"].append(card.action_id)
            groups[key]["zones"].update(card.zone_targets)
            groups[key]["total_score"] += card.priority_score

        result = []
        for g in groups.values():
            g["zones"] = list(g["zones"])
            g["avg_score"] = round(g["total_score"] / max(1, g["count"]), 4)
            result.append(g)
        return sorted(result, key=lambda x: x["total_score"], reverse=True)


cognitive_engine = CognitiveLoadEngine()
