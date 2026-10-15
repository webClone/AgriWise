"""
Layer 8.2: Constraint-Driven Scheduler v8.1.0

Places ranked ActionCards onto a calendar respecting:
  - Weather constraints (spray: wind < 15 km/h, no rain; fertilize: no heavy rain)
  - Phenology stage constraints
  - Legal windows (stubbed, always open)
  - Resource constraints (stubbed, always available)

Output: List[ScheduledAction] with ScheduleStatus (CONFIRMED / TENTATIVE / BLOCKED)
"""

import logging
import math
from typing import List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from layer8_prescriptive.schema import (
    ActionCard, ActionType, ScheduledAction, ScheduleStatus,
)


# ============================================================================
# Constraint Definitions
# ============================================================================

# Action → required weather conditions
WEATHER_CONSTRAINTS = {
    ActionType.SPRAY: {
        "max_wind_kmh": 15,
        "max_rain_mm": 0.5,
        "min_temp_c": 5,
        "max_temp_c": 38,
    },
    ActionType.FERTILIZE: {
        "max_rain_mm": 20,
        "min_temp_c": 0,
    },
    ActionType.IRRIGATE: {
        "max_rain_mm": 5,  # don't irrigate if rain coming
    },
    ActionType.HARVEST_PLAN: {
        "max_rain_mm": 2,
        "max_wind_kmh": 30,
    },
}

# Phenology stages where action is inappropriate
PHENOLOGY_BLOCKS = {
    ActionType.REPLANT: ["REPRODUCTIVE", "SENESCENCE", "HARVESTED"],
    ActionType.FERTILIZE: ["SENESCENCE", "HARVESTED"],
    ActionType.HARVEST_PLAN: ["BARE_SOIL", "EMERGENCE", "VEGETATIVE"],
}


def _parse_weather_val(val, multiplier=1.0):
    if val is None:
        return None, None
    if isinstance(val, bool):
        return None, "boolean"
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return None, "empty_string"
        try:
            fv = float(val_str) * multiplier
            if not math.isfinite(fv):
                return None, "non_finite"
            return fv, None
        except (ValueError, TypeError):
            return None, "invalid_format"
    if isinstance(val, (int, float)):
        fv = float(val) * multiplier
        if not math.isfinite(fv):
            return None, "non_finite"
        return fv, None
    return None, "invalid_type"


# ============================================================================
# Core Scheduler
# ============================================================================

class ConstraintScheduler:
    """
    Assigns calendar slots to ranked actions.
    
    Scans a configurable horizon (default 7 days) and finds the first
    feasible day for each action. Returns ScheduledAction with status
    and blocking reasons.
    """
    
    def schedule_actions(self,
                         action_cards: List[ActionCard],
                         forecast: List[Dict[str, Any]],
                         start_date: datetime,
                         horizon_days: int = 7,
                         phenology_stage: str = "VEGETATIVE") -> List[ScheduledAction]:
        """
        Schedule ranked actions onto the calendar.
        
        Args:
            action_cards: Ranked list of ActionCards
            forecast: Weather forecast dicts (one per day)
            start_date: Planning start date
            horizon_days: How far ahead to scan
            phenology_stage: Current crop stage from L2/L0
            
        Returns:
            List of ScheduledAction (one per input card)
        """
        scheduled: List[ScheduledAction] = []
        
        # Sort forecast rows chronologically if dated
        def _get_row_date(row):
            if isinstance(row, dict):
                return str(row.get("date") or row.get("timestamp") or "")
            return ""

        try:
            sorted_forecast = sorted(forecast, key=_get_row_date) if forecast else []
        except Exception:
            sorted_forecast = list(forecast) if forecast else []

        for card in action_cards:
            if not card.is_allowed:
                # Blocked actions cannot be scheduled
                scheduled.append(ScheduledAction(
                    action_id=card.action_id,
                    action_type=card.action_type,
                    scheduled_date=None,
                    status=ScheduleStatus.BLOCKED,
                    blocking_constraints=list(card.blocked_reason),
                    priority_score=card.priority_score,
                ))
                continue

            # Validate card rate attributes
            if card.rate is not None:
                rate_invalid = False
                rec = card.rate.recommended
                if isinstance(rec, bool) or not isinstance(rec, (int, float)) or not math.isfinite(rec) or rec < 0:
                    rate_invalid = True
                
                c_max = card.rate.max_safe
                if c_max is not None:
                    if isinstance(c_max, bool) or not isinstance(c_max, (int, float)) or not math.isfinite(c_max) or c_max < 0:
                        rate_invalid = True
                
                c_min = card.rate.min_safe
                if c_min is not None:
                    if isinstance(c_min, bool) or not isinstance(c_min, (int, float)) or not math.isfinite(c_min) or c_min < 0:
                        rate_invalid = True
                
                if c_min is not None and c_max is not None and c_min > c_max:
                    rate_invalid = True

                if rate_invalid:
                    card.is_allowed = False
                    reason = "Invalid rate envelope: non-finite, boolean, negative, or inconsistent bounds"
                    if reason not in card.blocked_reason:
                        card.blocked_reason.append(reason)
                    scheduled.append(ScheduledAction(
                        action_id=card.action_id,
                        action_type=card.action_type,
                        scheduled_date=None,
                        status=ScheduleStatus.BLOCKED,
                        blocking_constraints=[reason],
                        priority_score=card.priority_score,
                    ))
                    continue
            
            # Check phenology constraints
            pheno_blocks = PHENOLOGY_BLOCKS.get(card.action_type, [])
            if phenology_stage.upper() in [p.upper() for p in pheno_blocks]:
                scheduled.append(ScheduledAction(
                    action_id=card.action_id,
                    action_type=card.action_type,
                    scheduled_date=None,
                    status=ScheduleStatus.BLOCKED,
                    blocking_constraints=[f"phenology_stage={phenology_stage} incompatible"],
                    priority_score=card.priority_score,
                    phenology_ok=False,
                ))
                continue
            
            # Safe actions (SCOUT, WAIT, MONITOR) don't need weather windows
            if card.action_type in {ActionType.SCOUT, ActionType.WAIT, ActionType.MONITOR}:
                date_str = start_date.strftime("%Y-%m-%d")
                status = ScheduleStatus.CONFIRMED
                if card.requires_confirmation:
                    status = ScheduleStatus.TENTATIVE
                
                scheduled.append(ScheduledAction(
                    action_id=card.action_id,
                    action_type=card.action_type,
                    scheduled_date=date_str,
                    status=status,
                    priority_score=card.priority_score,
                ))
                continue
            
            # Scan forecast for feasible day
            constraints = WEATHER_CONSTRAINTS.get(card.action_type, {})
            best_date = None
            block_reasons: List[str] = []
            
            scan_days = min(horizon_days, len(sorted_forecast)) if sorted_forecast else 0
            
            for i in range(scan_days):
                day_fc = sorted_forecast[i] if i < len(sorted_forecast) else {}
                if not isinstance(day_fc, dict) or not day_fc:
                    day_blocked = True
                    day_reasons = ["Empty weather forecast record"]
                    block_reasons = day_reasons
                    continue

                row_date = day_fc.get("date") or day_fc.get("timestamp")
                if row_date:
                    candidate_date = str(row_date)
                else:
                    candidate_date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
                
                day_blocked = False
                day_reasons = []

                unit = str(day_fc.get("wind_speed_unit") or day_fc.get("wind_unit") or day_fc.get("unit") or "").lower().strip()
                wind_mult = 3.6 if unit in ("m/s", "mps") else 1.0

                raw_wind_speed = day_fc.get("wind_speed") if day_fc.get("wind_speed") is not None else day_fc.get("wind_kmh")
                raw_wind_gust = day_fc.get("wind_gust")
                raw_rain = day_fc.get("precip_mm") if day_fc.get("precip_mm") is not None else day_fc.get("precipitation")
                raw_temp_max = day_fc.get("temp_max") if day_fc.get("temp_max") is not None else day_fc.get("t_max_c")
                raw_temp_min = day_fc.get("temp_min") if day_fc.get("temp_min") is not None else day_fc.get("t_min_c")

                spd_val, spd_err = _parse_weather_val(raw_wind_speed, wind_mult)
                gst_val, gst_err = _parse_weather_val(raw_wind_gust, wind_mult)
                rain_val, rain_err = _parse_weather_val(raw_rain)
                tmax_val, tmax_err = _parse_weather_val(raw_temp_max)
                tmin_val, tmin_err = _parse_weather_val(raw_temp_min)

                if constraints:
                    if card.action_type == ActionType.SPRAY:
                        # Wind: both speed and gust checked
                        if spd_err or gst_err:
                            day_blocked = True
                            day_reasons.append(f"Unqualified wind forecast: speed={spd_err or 'ok'}, gust={gst_err or 'ok'}")
                        elif spd_val is None and gst_val is None:
                            day_blocked = True
                            day_reasons.append("Missing required wind forecast for spray")
                        else:
                            winds = [w for w in (spd_val, gst_val) if w is not None]
                            eff_wind = max(winds)
                            if eff_wind > constraints.get("max_wind_kmh", 15):
                                day_blocked = True
                                day_reasons.append(f"wind={eff_wind:.1f}km/h > {constraints['max_wind_kmh']}km/h")
                        
                        # Rain
                        if rain_err:
                            day_blocked = True
                            day_reasons.append(f"Unqualified rain forecast: {rain_err}")
                        elif rain_val is None:
                            day_blocked = True
                            day_reasons.append("Missing required rain forecast for spray")
                        elif rain_val > constraints.get("max_rain_mm", 0.5):
                            day_blocked = True
                            day_reasons.append(f"rain={rain_val:.1f}mm > {constraints['max_rain_mm']}mm")

                        # Temp
                        if tmax_err or tmin_err:
                            day_blocked = True
                            day_reasons.append(f"Unqualified temperature forecast: tmax={tmax_err or 'ok'}, tmin={tmin_err or 'ok'}")
                        elif tmax_val is None or tmin_val is None:
                            day_blocked = True
                            day_reasons.append("Missing required temperature forecast for spray")
                        else:
                            if "min_temp_c" in constraints and tmin_val < constraints["min_temp_c"]:
                                day_blocked = True
                                day_reasons.append(f"temp_min={tmin_val:.0f}°C < {constraints['min_temp_c']}°C")
                            if "max_temp_c" in constraints and tmax_val > constraints["max_temp_c"]:
                                day_blocked = True
                                day_reasons.append(f"temp_max={tmax_val:.0f}°C > {constraints['max_temp_c']}°C")

                    else:
                        # Other constrained actions (IRRIGATE, FERTILIZE, HARVEST_PLAN)
                        if "max_rain_mm" in constraints:
                            if rain_err:
                                day_blocked = True
                                day_reasons.append(f"Unqualified rain forecast: {rain_err}")
                            elif rain_val is not None and rain_val > constraints["max_rain_mm"]:
                                day_blocked = True
                                day_reasons.append(f"rain={rain_val:.1f}mm > {constraints['max_rain_mm']}mm")
                        
                        if "max_wind_kmh" in constraints:
                            if spd_err or gst_err:
                                day_blocked = True
                                day_reasons.append(f"Unqualified wind forecast: speed={spd_err or 'ok'}, gust={gst_err or 'ok'}")
                            else:
                                winds = [w for w in (spd_val, gst_val) if w is not None]
                                if winds:
                                    eff_wind = max(winds)
                                    if eff_wind > constraints["max_wind_kmh"]:
                                        day_blocked = True
                                        day_reasons.append(f"wind={eff_wind:.1f}km/h > {constraints['max_wind_kmh']}km/h")

                        if "min_temp_c" in constraints:
                            if tmin_err:
                                day_blocked = True
                                day_reasons.append(f"Unqualified temperature forecast: {tmin_err}")
                            elif tmin_val is not None and tmin_val < constraints["min_temp_c"]:
                                day_blocked = True
                                day_reasons.append(f"temp_min={tmin_val:.0f}°C < {constraints['min_temp_c']}°C")

                        if "max_temp_c" in constraints:
                            if tmax_err:
                                day_blocked = True
                                day_reasons.append(f"Unqualified temperature forecast: {tmax_err}")
                            elif tmax_val is not None and tmax_val > constraints["max_temp_c"]:
                                day_blocked = True
                                day_reasons.append(f"temp_max={tmax_val:.0f}°C > {constraints['max_temp_c']}°C")

                if not day_blocked:
                    best_date = candidate_date
                    break
                else:
                    block_reasons = day_reasons

            if best_date:
                status = ScheduleStatus.CONFIRMED
                if card.requires_confirmation:
                    status = ScheduleStatus.TENTATIVE
                
                scheduled.append(ScheduledAction(
                    action_id=card.action_id,
                    action_type=card.action_type,
                    scheduled_date=best_date,
                    status=status,
                    priority_score=card.priority_score,
                ))
            else:
                scheduled.append(ScheduledAction(
                    action_id=card.action_id,
                    action_type=card.action_type,
                    scheduled_date=None,
                    status=ScheduleStatus.BLOCKED,
                    blocking_constraints=block_reasons or ["no_feasible_day_in_horizon"],
                    priority_score=card.priority_score,
                    weather_ok=False,
                ))
        
        logger.debug("Scheduled %d actions: %d confirmed, %d tentative, %d blocked",
                     len(scheduled),
                     sum(1 for s in scheduled if s.status == ScheduleStatus.CONFIRMED),
                     sum(1 for s in scheduled if s.status == ScheduleStatus.TENTATIVE),
                     sum(1 for s in scheduled if s.status == ScheduleStatus.BLOCKED))
        return scheduled


# Singleton
scheduler = ConstraintScheduler()
