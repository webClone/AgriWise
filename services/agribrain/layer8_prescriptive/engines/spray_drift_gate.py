"""Spray-drift safety enforcement for Layer 8 prescriptions."""

import logging

from layer8_prescriptive.schema import ActionType

logger = logging.getLogger(__name__)

_MAX_WIND_KMH = 25.0


class SprayDriftGateEngine:
    """Block pesticide spraying when forecast wind exceeds the safety limit."""

    def enforce_drift_limits(self, action_cards, forecast):
        wind_values = []
        for day in forecast or []:
            value = day.get("wind_gust")
            if value is None:
                value = day.get("wind_speed")
            if value is None:
                value = day.get("wind_kmh")
            if value is not None:
                try:
                    wind_values.append(float(value))
                except (TypeError, ValueError):
                    continue

        if not wind_values:
            has_spray = any(c.action_type == ActionType.SPRAY for c in action_cards)
            if has_spray:
                reason = "Spray blocked: missing qualified weather/wind forecast; cannot confirm spray-drift safety"
                for card in action_cards:
                    if card.action_type == ActionType.SPRAY:
                        card.is_allowed = False
                        if reason not in card.blocked_reason:
                            card.blocked_reason.append(reason)
                        card.explain += " [DRIFT: {}]".format(reason)
                logger.warning(reason)
            return action_cards

        max_wind = max(wind_values, default=0.0)
        if max_wind <= _MAX_WIND_KMH:
            return action_cards

        reason = (
            "Spray blocked: forecast wind {:.1f} km/h exceeds the {:.1f} km/h "
            "spray-drift safety limit"
        ).format(max_wind, _MAX_WIND_KMH)
        for card in action_cards:
            if card.action_type != ActionType.SPRAY:
                continue
            card.is_allowed = False
            if reason not in card.blocked_reason:
                card.blocked_reason.append(reason)
            card.explain += " [DRIFT: {}]".format(reason)

        logger.warning(reason)
        return action_cards


spray_drift_gate_engine = SprayDriftGateEngine()
