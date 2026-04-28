from typing import Tuple

from layer0.sensors.schemas import SensorRepresentativeness

# Maps placement type to (observation_scope, update_scope, max_reliability)
PLACEMENT_CEILINGS = {
    "representative_zone": ("zone", "plot", 0.85),  # Assuming it's validated to represent the plot
    "weather_station": ("plot", "plot", 0.85),
    "irrigation_line": ("irrigation_block", "zone", 0.60),
    "unknown": ("point", "none", 0.45),
    "known_wet_spot": ("zone", "none", 0.40), # Diagnostic only for plot mean
    "known_dry_spot": ("zone", "none", 0.40),
    "edge": ("point", "none", 0.35),
    "control_point": ("point", "none", 0.45)
}

def evaluate_representativeness(
    placement_type: str,
    geo_context_flags: list[str] | None = None
) -> SensorRepresentativeness:
    
    obs_scope, upd_scope, max_rel = PLACEMENT_CEILINGS.get(placement_type, ("point", "none", 0.45))
    
    flags = []
    reason = f"Placement is {placement_type}."
    
    # In V1, if geo_context says it's an edge but registry says representative, we penalize it
    if geo_context_flags and "PLOT_BOUNDARY_CONTAMINATION" in geo_context_flags:
        if placement_type == "representative_zone":
            upd_scope = "none"
            max_rel = min(max_rel, 0.35)
            obs_scope = "point"
            flags.append("DOWNGRADED_BY_GEO_CONTEXT_EDGE")
            reason += " Downgraded due to boundary contamination."
            
    return SensorRepresentativeness(
        observation_scope=obs_scope,
        update_scope=upd_scope,
        confidence=max_rel,
        placement_flags=flags,
        reason=reason
    )

def map_depth_overlap(sensor_interval: Tuple[float, float], target_layer: Tuple[float, float]) -> float:
    """
    Returns the overlap fraction of the sensor's measurement volume with the target soil layer.
    """
    s_top, s_bot = sensor_interval
    t_top, t_bot = target_layer
    
    overlap_top = max(s_top, t_top)
    overlap_bot = min(s_bot, t_bot)
    
    sensor_thickness = s_bot - s_top
    if sensor_thickness == 0:
        # Point sensor at s_top
        if t_top <= s_top <= t_bot:
            return 1.0
        return 0.0

    if overlap_bot <= overlap_top:
        return 0.0
        
    overlap_thickness = overlap_bot - overlap_top
    return overlap_thickness / sensor_thickness
