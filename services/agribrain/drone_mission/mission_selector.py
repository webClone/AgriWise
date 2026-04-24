"""
Mission Selector.

Decides the optimal mission type, mode, and GSD based on 
the target anomaly or user command.
"""

from typing import Dict, Any, Tuple
from .schemas import MissionType, FlightMode, MissionIntent

def select_mission_for_anomaly(
    plot_id: str, 
    polygon_geojson: Dict[str, Any], 
    anomaly_type: str, 
    crop_type: str,
    zone_id: str = None
) -> MissionIntent:
    """
    Selects the right drone mission given an anomaly trigger from Sentinel/Layer 0.
    """
    if anomaly_type == "missing_plants":
        # Missing plants require structural row auditing
        if crop_type in ("orchard", "citrus", "olive"):
            m_type = MissionType.ORCHARD_AUDIT
            mode = FlightMode.MAPPING_MODE
            gsd = 2.5
        else:
            m_type = MissionType.ROW_AUDIT
            mode = FlightMode.MAPPING_MODE
            gsd = 2.0
            
    elif anomaly_type == "weed_pressure_high":
        m_type = MissionType.WEED_MAP
        mode = FlightMode.MAPPING_MODE
        gsd = 1.5
        
    elif anomaly_type == "disease_suspected" or anomaly_type == "chlorosis_patch":
        # Suspected disease needs point-scope symptom validation
        m_type = MissionType.CONCERN_ZONE_COMMAND
        mode = FlightMode.COMMAND_REVISIT_MODE
        gsd = 0.5  # Need < 1cm for disease symptoms
        
    else:
        # Default fallback
        m_type = MissionType.RAPID_SCOUT
        mode = FlightMode.MAPPING_MODE
        gsd = 5.0
        
    intent = MissionIntent(
        intent_id=f"auto_{plot_id}_{anomaly_type}",
        plot_id=plot_id,
        mission_type=m_type,
        flight_mode=mode,
        polygon_geojson=polygon_geojson,
        target_zone_id=zone_id,
        target_gsd_cm=gsd,
        required_overlap_pct=75.0 if mode == FlightMode.MAPPING_MODE else 60.0,
        trigger_source=f"anomaly_{anomaly_type}",
        crop_type=crop_type
    )
    return intent
