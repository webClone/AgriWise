"""
Layer 8.3: Zone Prioritization Engine.
Maps actions to specific Zones (Precision Agriculture).
"""

from typing import Dict, Any, List

class ZonePrioritizer:
    
    def prioritize_zones(self, 
                         zone_scenarios: Dict[str, Any], # zone_id -> scenario_result
                         action_type: str,
                         roi_threshold: float = 20.0) -> Dict[str, Any]:
        """
        Decide which zones get the input.
        Result: 'Variable Rate' map logic (Binary for now: Apply / Skip).
        """
        prescription = {}
        total_profit = 0
        zones_treated = []
        
        for zone_id, scen in zone_scenarios.items():
            roi = scen.get("roi_pct", 0)
            
            if roi > roi_threshold:
                prescription[zone_id] = {
                    "action": "apply",
                    "reason": f"High ROI ({roi:.0f}%)",
                    "priority": "High" if roi > 100 else "Medium"
                }
                total_profit += scen.get("profit_delta_usd", 0)
                zones_treated.append(zone_id)
            else:
                prescription[zone_id] = {
                    "action": "skip",
                    "reason": f"Low ROI ({roi:.0f}%)",
                    "priority": "None"
                }
                
        return {
            "action_type": action_type,
            "zones_treated_count": len(zones_treated),
            "zones_treated_ids": zones_treated,
            "prescription_map": prescription,
            "total_expected_profit": total_profit
        }

# Singleton
zone_engine = ZonePrioritizer()
