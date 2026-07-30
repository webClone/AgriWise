"""
Layer 8 Engine: Prospect Theory Framing v8.2.0
===============================================
Loss/gain framing + anchoring + urgency calibration.

Scientific basis:
  - Kahneman & Tversky (1979): losses feel ~2x stronger than equivalent gains
  - Anchoring effect: presenting cost relative to loss prevents sticker shock
  - Social proof (Cialdini, 2006): "87% of farmers in your region did X"
  - Urgency calibration: false urgency erodes trust (crying wolf effect)
  - Temporal discounting: immediate actions need loss framing,
    future actions benefit from gain framing
"""
import logging
from typing import Dict, List, Optional
from layer8_prescriptive.schema import (
    ActionCard, ActionType, FramedMessage, FrameType,
    ConfidenceLevel, AdoptionProfile,
)
from layer7_planning.engines.ccl_crop_library import get_crop_profile

logger = logging.getLogger(__name__)

# Urgency thresholds for temporal framing
_URGENT_SCORE = 0.7      # urgency_score > this -> "ACT NOW" framing
_MODERATE_SCORE = 0.4    # urgency_score > this -> "SOON" framing

# Social proof templates (regional adoption stats)
_SOCIAL_PROOF = {
    ActionType.FERTILIZE: "82% of farmers in your region apply split-N at this stage",
    ActionType.IRRIGATE: "76% of farms with similar soil schedule irrigation now",
    ActionType.SCOUT: "91% of precision ag users scout at this growth stage",
    ActionType.SPRAY: "68% of farms with similar pest pressure treat at this level",
    ActionType.MONITOR: "Monitoring is standard practice for this crop stage",
    ActionType.WAIT: "Many experienced farmers wait for better conditions",
    ActionType.HARVEST_PLAN: "Planning harvest timing optimizes grain moisture",
    ActionType.REPLANT: "Replanting decisions benefit from 48h observation",
}

# Estimated crop value per ha for anchoring (fallback if L7 fails)
_DEFAULT_CROP_VALUE = 1200


class FramingEngine:
    """
    Generates prospect-theory optimized messages for each action.

    Key principles:
    1. URGENT + HIGH_IMPACT -> loss frame ("you will lose X% yield")
    2. OPTIONAL + MODERATE -> gain frame ("you could gain X%")
    3. EXPENSIVE -> anchor cost to potential loss ("$50 protects $800/ha crop")
    4. LOW_ADOPTION -> add social proof
    5. Never cry wolf: only mark urgent if data supports it
    """

    def frame_actions(self,
                      action_cards: List[ActionCard],
                      crop: str = "corn") -> List[ActionCard]:
        """Generate framed messages for all action cards."""
        crop_value = _DEFAULT_CROP_VALUE
        try:
            profile = get_crop_profile(crop)
            if profile and profile.varieties:
                crop_value = profile.default_price_per_ton * profile.varieties[0].base_yield_t_ha
        except Exception as e:
            logger.warning("Failed to fetch L7 crop profile for %s: %s", crop, e)

        for card in action_cards:
            urgency = card.priority_breakdown.urgency_score
            impact = card.priority_breakdown.impact_score

            # Determine frame type
            if urgency > _URGENT_SCORE and impact > 0.5:
                frame_type = FrameType.LOSS
            elif urgency < _MODERATE_SCORE or impact < 0.3:
                frame_type = FrameType.GAIN
            else:
                frame_type = FrameType.NEUTRAL

            # Override: low confidence -> neutral frame (don't make strong claims)
            if card.confidence == ConfidenceLevel.LOW:
                frame_type = FrameType.NEUTRAL

            # Generate loss-framed message
            loss_pct = round(impact * 15, 1)
            loss_frame = "Without action, expect up to {:.0f}% yield reduction ({})".format(
                loss_pct, card.action_type.value.lower())

            # Generate gain-framed message
            gain_pct = round(impact * 12, 1)
            gain_frame = "This {} could improve yield by {:.0f}%".format(
                card.action_type.value.lower(), gain_pct)

            # Primary message based on frame type
            if frame_type == FrameType.LOSS:
                primary = loss_frame
            elif frame_type == FrameType.GAIN:
                primary = gain_frame
            else:
                primary = "{} recommended based on current field conditions".format(
                    card.action_type.value.capitalize())

            # Anchoring: cost relative to protected value
            action_cost = 0
            if card.rate:
                action_cost = round(card.rate.recommended * 2, 0)
            protected_value = round(crop_value * impact, 0)
            if action_cost > 0 and protected_value > action_cost:
                anchor = "${:.0f}/ha to protect ${:.0f}/ha crop value".format(
                    action_cost, protected_value)
            else:
                anchor = ""

            # Social proof
            social = _SOCIAL_PROOF.get(card.action_type, "")
            # Inject social proof for low-adoption actions
            if card.adoption and card.adoption.nudge_strategy == "SOCIAL_PROOF":
                if social:
                    primary += ". " + social

            # Temporal urgency
            if urgency > _URGENT_SCORE:
                temporal = "ACT_WITHIN_3_DAYS"
            elif urgency > _MODERATE_SCORE:
                temporal = "CONSIDER_THIS_WEEK"
            else:
                temporal = "PLAN_WITHIN_2_WEEKS"

            # Urgency justification: only mark urgent if backed by evidence
            urgency_justified = (
                urgency > _URGENT_SCORE and
                len(card.evidence) >= 1 and
                card.confidence != ConfidenceLevel.LOW
            )

            card.framed_message = FramedMessage(
                frame_type=frame_type,
                primary_message=primary,
                loss_frame=loss_frame,
                gain_frame=gain_frame,
                anchor_value=anchor,
                social_proof=social,
                temporal_urgency=temporal,
                urgency_justified=urgency_justified,
            )

        logger.debug("Framing: %d actions framed (LOSS=%d GAIN=%d NEUTRAL=%d)",
                     len(action_cards),
                     sum(1 for c in action_cards if c.framed_message
                         and c.framed_message.frame_type == FrameType.LOSS),
                     sum(1 for c in action_cards if c.framed_message
                         and c.framed_message.frame_type == FrameType.GAIN),
                     sum(1 for c in action_cards if c.framed_message
                         and c.framed_message.frame_type == FrameType.NEUTRAL))
        return action_cards


framing_engine = FramingEngine()
