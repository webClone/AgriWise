"""Spray-drift safety enforcement for Layer 8 prescriptions."""

import logging
import math
from typing import Any, List, Optional

from layer8_prescriptive.schema import ActionType

logger = logging.getLogger(__name__)

_MAX_WIND_KMH = 20.0
_MAX_GUST_KMH = 15.0


class SprayDriftGateEngine:
    """Block pesticide spraying when forecast wind exceeds the safety limit."""

    def enforce_drift_limits(self, action_cards, forecast):
        has_spray = any(c.action_type == ActionType.SPRAY for c in action_cards)
        if not has_spray:
            return action_cards

        if not forecast:
            reason = "Spray blocked: missing qualified weather/wind forecast; cannot confirm spray-drift safety"
            return self._block_spray(action_cards, reason)

        # Sort dated forecast rows chronologically
        try:
            sorted_forecast = sorted(forecast, key=lambda d: str(d.get("date") or d.get("timestamp") or ""))
        except Exception:
            sorted_forecast = list(forecast)

        max_speed = 0.0
        max_gust = 0.0
        has_valid_wind = False

        for day in sorted_forecast:
            if not isinstance(day, dict) or not day:
                continue

            unit = str(day.get("wind_speed_unit") or day.get("wind_unit") or day.get("unit") or "").lower().strip()
            multiplier = 3.6 if unit in ("m/s", "mps") else 1.0

            # Validate wind speed, wind gust, precipitation, and temperature for non-finite or boolean values
            for var in ("wind_speed", "wind_gust", "wind_kmh", "precip_mm", "precipitation", "t_max_c", "t_min_c", "temp_max", "temp_min"):
                if var in day:
                    v = day[var]
                    if isinstance(v, bool):
                        return self._block_spray(action_cards, f"Spray blocked: unqualified weather forecast field {var} is boolean")
                    try:
                        fv = float(v)
                        if math.isnan(fv) or math.isinf(fv):
                            return self._block_spray(action_cards, f"Spray blocked: unqualified weather forecast field {var} is non-finite ({fv})")
                    except (TypeError, ValueError):
                        return self._block_spray(action_cards, f"Spray blocked: invalid numeric format for weather forecast field {var}")

            speed_val = day.get("wind_speed") if day.get("wind_speed") is not None else day.get("wind_kmh")
            gust_val = day.get("wind_gust")

            if speed_val is not None:
                has_valid_wind = True
                spd = float(speed_val) * multiplier
                if spd > max_speed:
                    max_speed = spd

            if gust_val is not None:
                has_valid_wind = True
                gst = float(gust_val) * multiplier
                if gst > max_gust:
                    max_gust = gst

        if not has_valid_wind:
            reason = "Spray blocked: missing qualified weather/wind forecast; cannot confirm spray-drift safety"
            return self._block_spray(action_cards, reason)

        if max_gust > _MAX_GUST_KMH:
            reason = f"Spray blocked: forecast wind gust {max_gust:.1f} km/h exceeds the {_MAX_GUST_KMH:.1f} km/h spray-drift safety limit"
            return self._block_spray(action_cards, reason)

        if max_speed > _MAX_WIND_KMH:
            reason = f"Spray blocked: forecast wind {max_speed:.1f} km/h exceeds the {_MAX_WIND_KMH:.1f} km/h spray-drift safety limit"
            return self._block_spray(action_cards, reason)

        return action_cards

    def _block_spray(self, action_cards, reason: str):
        for card in action_cards:
            if card.action_type == ActionType.SPRAY:
                card.is_allowed = False
                if reason not in card.blocked_reason:
                    card.blocked_reason.append(reason)
                card.explain += " [DRIFT: {}]".format(reason)
        logger.warning(reason)
        return action_cards


spray_drift_gate_engine = SprayDriftGateEngine()
