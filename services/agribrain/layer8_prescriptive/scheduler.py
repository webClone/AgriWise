"""
Layer 8.2: Constraint-Aware Scheduler.
Converts prioritized actions into a feasible schedule (Wind/Rain/Heat blocks).
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta

class ConstraintScheduler:
    
    def schedule_actions(self, 
                         ranked_actions: List[Dict[str, Any]], 
                         forecast: List[Dict[str, Any]], 
                         start_date: datetime) -> List[Dict[str, Any]]:
        """
        Assign time slots.
        Constraint: Spraying requires Wind < 15km/h, No Rain.
        Constraint: Fertilizing requires No Heavy Rain (>20mm).
        """
        schedule = []
        
        for action_item in ranked_actions[:5]: # Top 5 only
            action_type = action_item.get("action", "").lower()
            
            found_slot = False
            best_slot = None
            block_reason = None
            
            # Scan next 3 days
            for i in range(3): 
                if found_slot: break
                
                day_forecast = forecast[i] if i < len(forecast) else {}
                date_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
                
                rain = day_forecast.get("precip_mm", 0)
                wind = day_forecast.get("wind_speed", 0)
                temp = day_forecast.get("temp_max", 25)
                
                # Check Constraints
                is_blocked = False
                
                if "spray" in action_type:
                    if wind > 15: 
                        is_blocked = True
                        block_reason = "High Wind"
                    elif rain > 0.5:
                        is_blocked = True
                        block_reason = "Rain"
                        
                elif "fertilize" in action_type:
                    if rain > 20:
                        is_blocked = True
                        block_reason = "Leaching Rain (>20mm)"
                        
                elif "irrigate" in action_type:
                    if rain > 5:
                        is_blocked = True
                        block_reason = "Rain Forecast (>5mm)"
                        
                if not is_blocked:
                    found_slot = True
                    best_slot = date_str
                    
            if best_slot:
                schedule.append({
                    "action": action_type,
                    "scheduled_date": best_slot,
                    "status": "scheduled",
                    "priority": action_item.get("rank_score")
                })
            else:
                 schedule.append({
                    "action": action_type,
                    "status": "blocked",
                    "reason": block_reason or "Constraint check failed",
                    "next_viable": "Check >3 days"
                })
                
        return schedule

# Singleton
scheduler = ConstraintScheduler()
