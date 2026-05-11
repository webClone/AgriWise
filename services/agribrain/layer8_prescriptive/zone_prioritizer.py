"""
Layer 8.3: Zone Prioritization Engine v8.1.0

Maps ActionCards to specific management zones with allocation fractions.
Uses per-zone reliability from L0 to avoid prescribing into unreliable zones.

Output: Dict[zone_id, ZoneActionPlan]
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

from layer8_prescriptive.schema import (
    ActionCard, ZoneActionPlan, ActionType,
)


class ZonePrioritizer:
    """
    Allocates actions to zones based on upstream evidence + zone reliability.
    
    Rules:
      - High-ROI zones get priority
      - Low-reliability zones get SCOUT, not heavy interventions
      - Allocation fractions sum <= 1.0 per action
    """
    
    def prioritize_zones(self,
                          action_cards: List[ActionCard],
                          zone_reliability: Dict[str, float],
                          zone_ids: List[str]) -> Dict[str, ZoneActionPlan]:
        """
        Assign actions to zones with reliability-aware allocation.
        
        Args:
            action_cards: Ranked list of ActionCards
            zone_reliability: zone_id → reliability score (0–1) from L0
            zone_ids: All management zone IDs
            
        Returns:
            zone_id → ZoneActionPlan
        """
        plans: Dict[str, ZoneActionPlan] = {}
        
        for zone_id in zone_ids:
            rel = zone_reliability.get(zone_id, 0.8)
            assigned_actions: List[str] = []
            
            for card in action_cards:
                if zone_id not in card.zone_targets:
                    continue
                
                alloc = card.zone_allocation.get(zone_id, 0.0)
                if alloc <= 0:
                    continue
                
                # Low-reliability zone: only allow safe actions
                if rel < 0.5 and card.action_type not in {
                    ActionType.SCOUT, ActionType.MONITOR, ActionType.WAIT
                }:
                    continue  # skip heavy actions in unreliable zones
                
                assigned_actions.append(card.action_id)
            
            # Priority based on reliability + number of actions
            if rel >= 0.8 and assigned_actions:
                priority = "HIGH"
            elif rel >= 0.5 and assigned_actions:
                priority = "MEDIUM"
            elif assigned_actions:
                priority = "LOW"
            else:
                priority = "SKIP"
            
            reason = ""
            if rel < 0.5:
                reason = f"low reliability ({rel:.2f}) — restricted to monitoring"
            elif not assigned_actions:
                reason = "no actions assigned"
            
            plans[zone_id] = ZoneActionPlan(
                zone_id=zone_id,
                actions=assigned_actions,
                allocation_fraction=1.0 / max(1, len(zone_ids)),
                priority=priority,
                reason=reason,
            )
        
        logger.debug("Zone plan: %d zones (%s)",
                     len(plans),
                     ", ".join(f"{z}={p.priority}" for z, p in plans.items()))
        return plans


# Singleton
zone_engine = ZonePrioritizer()
