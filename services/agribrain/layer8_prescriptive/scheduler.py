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
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta, timezone

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


def _parse_row_date_and_instant(row: Dict[str, Any]) -> Tuple[Optional[str], Optional[datetime], Optional[str]]:
    """Returns (date_str_yyyy_mm_dd, utc_datetime, error_string)"""
    if not isinstance(row, dict):
        return None, None, "not_a_dict"
    raw = row.get("date") or row.get("timestamp")
    if raw is None:
        return None, None, "missing_date"
    s = str(raw).strip()
    if not s:
        return None, None, "empty_date"
    
    try:
        if len(s) == 10 and s[4] == '-' and s[7] == '-':
            parts = [int(p) for p in s.split('-')]
            dt = datetime(parts[0], parts[1], parts[2], tzinfo=timezone.utc)
            return s, dt, None
        norm_s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(norm_s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        return date_str, dt, None
    except Exception:
        return None, None, f"invalid_date_format: {s}"


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
        
        # Sort forecast rows chronologically by UTC instant if dated
        def _get_row_instant(row):
            if isinstance(row, dict):
                _, dt, _ = _parse_row_date_and_instant(row)
                if dt is not None:
                    return dt
            return datetime.max.replace(tzinfo=timezone.utc)

        try:
            sorted_forecast = sorted(forecast, key=_get_row_instant) if forecast else []
        except Exception:
            sorted_forecast = list(forecast) if forecast else []

        # Detect conflicting duplicate same-day rows and deduplicate
        conflicted_dates = set()
        seen_dates: Dict[str, Dict[str, Any]] = {}
        deduped_forecast = []
        # Group forecast rows by date to enforce order-invariant conflict and boundary checking
        date_groups: Dict[str, List[Dict[str, Any]]] = {}
        for row in sorted_forecast:
            if not isinstance(row, dict):
                deduped_forecast.append(row)
                continue
            d_str, _, d_err = _parse_row_date_and_instant(row)
            if d_str is None or d_err is not None:
                deduped_forecast.append(row)
                continue
            date_groups.setdefault(d_str, []).append(row)

        for d_str, group in date_groups.items():
            if len(group) == 1:
                seen_dates[d_str] = group[0]
                deduped_forecast.append(group[0])
                continue

            # Multi-row support for same date: evaluate conflicts and action feasibility boundaries symmetrically
            p_vals: List[float] = []
            w_vals: List[float] = []
            g_vals: List[float] = []
            tmax_vals: List[float] = []
            tmin_vals: List[float] = []

            for r in group:
                u = str(r.get("wind_speed_unit") or r.get("wind_unit") or r.get("unit") or "").lower().strip()
                m = 3.6 if u in ("m/s", "mps") else (1.852 if u in ("knots", "knot", "kt", "kts") else (1.60934 if u in ("mph", "mi/h") else 1.0))
                p_raw = r.get("precip_mm") if r.get("precip_mm") is not None else r.get("precipitation")
                p, _ = _parse_weather_val(p_raw)
                if p is not None:
                    p_vals.append(p)
                w_raw = r.get("wind_speed") if r.get("wind_speed") is not None else r.get("wind_kmh")
                w, _ = _parse_weather_val(w_raw, m)
                if w is not None:
                    w_vals.append(w)
                g_raw = r.get("wind_gust")
                g, _ = _parse_weather_val(g_raw, m)
                if g is not None:
                    g_vals.append(g)
                tmax_raw = r.get("temp_max") if r.get("temp_max") is not None else r.get("t_max_c")
                tmax, _ = _parse_weather_val(tmax_raw)
                if tmax is not None:
                    tmax_vals.append(tmax)
                tmin_raw = r.get("temp_min") if r.get("temp_min") is not None else r.get("t_min_c")
                tmin, _ = _parse_weather_val(tmin_raw)
                if tmin is not None:
                    tmin_vals.append(tmin)

            has_conflict = False
            # Check numerical discrepancies (>= 0.5mm rain, >= 2.0km/h wind/gust, >= 3.0°C temp)
            if p_vals and (max(p_vals) - min(p_vals) >= 0.5):
                has_conflict = True
            if w_vals and (max(w_vals) - min(w_vals) >= 2.0):
                has_conflict = True
            if g_vals and (max(g_vals) - min(g_vals) >= 2.0):
                has_conflict = True
            if tmax_vals and (max(tmax_vals) - min(tmax_vals) >= 3.0):
                has_conflict = True
            if tmin_vals and (max(tmin_vals) - min(tmin_vals) >= 3.0):
                has_conflict = True

            # Check action feasibility boundary crossings across duplicates
            if p_vals and (min(p_vals) <= 0.5 and max(p_vals) > 0.5):
                has_conflict = True
            if w_vals and (min(w_vals) <= 15.0 and max(w_vals) > 15.0):
                has_conflict = True
            if g_vals and (min(g_vals) <= 15.0 and max(g_vals) > 15.0):
                has_conflict = True
            if tmax_vals and (min(tmax_vals) <= 38.0 and max(tmax_vals) > 38.0):
                has_conflict = True
            if tmin_vals and (min(tmin_vals) < 5.0 and max(tmin_vals) >= 5.0):
                has_conflict = True

            if has_conflict:
                conflicted_dates.add(d_str)

            # Build conservative representative row for the date
            merged_row = dict(group[0])
            if p_vals:
                merged_row["precip_mm"] = max(p_vals)
            if w_vals:
                merged_row["wind_speed"] = max(w_vals)
            if g_vals:
                merged_row["wind_gust"] = max(g_vals)
            if w_vals or g_vals:
                merged_row["wind_speed_unit"] = "km/h"
                if "wind_unit" in merged_row:
                    merged_row["wind_unit"] = "km/h"
                if "unit" in merged_row:
                    merged_row["unit"] = "km/h"
            if tmax_vals:
                merged_row["temp_max"] = max(tmax_vals)
            if tmin_vals:
                merged_row["temp_min"] = min(tmin_vals)

            seen_dates[d_str] = merged_row
            deduped_forecast.append(merged_row)

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

                if c_min is not None and rec < c_min:
                    rate_invalid = True

                if c_max is not None and rec > c_max:
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
            
            scan_days = min(horizon_days, len(deduped_forecast)) if deduped_forecast else 0
            start_instant = start_date if isinstance(start_date, datetime) else datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
            if start_instant.tzinfo is None:
                start_instant = start_instant.replace(tzinfo=timezone.utc)
            else:
                start_instant = start_instant.astimezone(timezone.utc)
            start_d = start_instant.date()
            end_horizon_d = start_d + timedelta(days=horizon_days)
            
            for i in range(scan_days):
                day_fc = deduped_forecast[i] if i < len(deduped_forecast) else {}
                if not isinstance(day_fc, dict) or not day_fc:
                    day_blocked = True
                    day_reasons = ["Empty weather forecast record"]
                    block_reasons = day_reasons
                    continue

                d_str, cand_dt, date_err = _parse_row_date_and_instant(day_fc)
                if date_err:
                    day_blocked = True
                    day_reasons = [f"Unqualified forecast date: {date_err}"]
                    block_reasons = day_reasons
                    continue

                if d_str is None:
                    day_blocked = True
                    day_reasons = ["Missing forecast date"]
                    block_reasons = day_reasons
                    continue

                candidate_date = d_str
                cand_d_pre = cand_dt.date() if cand_dt else None
                candidate_instant = cand_dt if cand_dt is not None else datetime.combine(cand_d_pre, datetime.min.time(), tzinfo=timezone.utc)
                if candidate_instant.tzinfo is None:
                    candidate_instant = candidate_instant.replace(tzinfo=timezone.utc)
                else:
                    candidate_instant = candidate_instant.astimezone(timezone.utc)
                cand_d = candidate_instant.date()

                day_blocked = False
                day_reasons = []

                # Check planning horizon interval and start instant
                if cand_dt is not None and candidate_instant < start_instant:
                    day_blocked = True
                    day_reasons.append(f"Candidate instant {candidate_instant.isoformat()} precedes planning start {start_instant.isoformat()}")
                elif cand_d and (cand_d < start_d or cand_d >= end_horizon_d):
                    day_blocked = True
                    day_reasons.append(f"Date {candidate_date} is outside planning horizon [{start_d}, {end_horizon_d})")

                # Check conflicting same-day forecast
                if candidate_date in conflicted_dates:
                    day_blocked = True
                    day_reasons.append(f"Conflicting same-day forecast records for {candidate_date}")

                # Check expiration / validity window
                valid_until_raw = day_fc.get("valid_until") or day_fc.get("expires_at")
                if valid_until_raw is not None:
                    _, v_until_dt, v_err = _parse_row_date_and_instant({"date": valid_until_raw})
                    if v_err is not None or v_until_dt is None:
                        day_blocked = True
                        day_reasons.append(f"Unqualified forecast valid_until: {valid_until_raw}")
                    else:
                        ref_dt = max(start_instant, candidate_instant)
                        if ref_dt > v_until_dt:
                            day_blocked = True
                            day_reasons.append(f"Forecast expired: valid_until={valid_until_raw} passed")

                unit = str(day_fc.get("wind_speed_unit") or day_fc.get("wind_unit") or day_fc.get("unit") or "").lower().strip()
                wind_mult = 3.6 if unit in ("m/s", "mps") else (1.852 if unit in ("knots", "knot", "kt", "kts") else (1.60934 if unit in ("mph", "mi/h") else 1.0))

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
