"""
Layer 8.2: Constraint-Driven Scheduler

Places ranked ActionCards onto a calendar respecting:
  - Weather constraints (spray: wind < 15 km/h, no rain; fertilize: no heavy rain)
  - Phenology stage constraints
  - Legal windows (stubbed, always open)
  - Resource constraints (stubbed, always available)

Output: List[ScheduledAction] with ScheduleStatus (CONFIRMED / TENTATIVE / BLOCKED)
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta

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
            
            scan_days = min(horizon_days, len(forecast)) if forecast else 0
            
            for i in range(scan_days):
                day_fc = forecast[i] if i < len(forecast) else {}
                candidate_date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
                
                day_blocked = False
                day_reasons: List[str] = []
                
                # Check weather constraints
                rain = day_fc.get("precip_mm", day_fc.get("precipitation", 0))
                wind = day_fc.get("wind_speed", day_fc.get("wind_kmh", 0))
                temp_max = day_fc.get("temp_max", 25)
                temp_min = day_fc.get("temp_min", 10)
                
                if "max_rain_mm" in constraints and rain > constraints["max_rain_mm"]:
                    day_blocked = True
                    day_reasons.append(f"rain={rain:.1f}mm > {constraints['max_rain_mm']}mm")
                
                if "max_wind_kmh" in constraints and wind > constraints["max_wind_kmh"]:
                    day_blocked = True
                    day_reasons.append(f"wind={wind:.0f}km/h > {constraints['max_wind_kmh']}km/h")
                
                if "min_temp_c" in constraints and temp_min < constraints["min_temp_c"]:
                    day_blocked = True
                    day_reasons.append(f"temp_min={temp_min:.0f}°C < {constraints['min_temp_c']}°C")
                
                if "max_temp_c" in constraints and temp_max > constraints["max_temp_c"]:
                    day_blocked = True
                    day_reasons.append(f"temp_max={temp_max:.0f}°C > {constraints['max_temp_c']}°C")
                
                if not day_blocked:
                    best_date = candidate_date
                    break
                else:
                    block_reasons = day_reasons  # keep last day's reasons
            
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
        
        return scheduled


# Singleton
scheduler = ConstraintScheduler()
