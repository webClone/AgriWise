from typing import List, Any
from layer0.sensors.schemas import SensorQAResult, SensorAggregate, SensorRepresentativeness
from layer0.sensors.representativeness import map_depth_overlap

def map_to_kalman_observations(
    variable: str,
    value: float,
    qa: SensorQAResult,
    rep: SensorRepresentativeness,
    depth_interval: tuple[float, float] | None
) -> List[Any]:
    """
    Returns actual Kalman State updates if allowed.
    """
    # 1. Output-specific thresholds
    if qa.reliability_weight < 0.60:
        return [] # Too weak for any Kalman state observation
        
    if rep.update_scope == "none":
        return []
        
    if rep.update_scope == "plot" and qa.reliability_weight < 0.80:
        return [] # Block plot-wide update if not extremely high trust

    # 2. Sigma derived from reliability (inverse mapping)
    # E.g., 1.0 rel -> 1.0 sigma, 0.6 rel -> 5.0 sigma
    dynamic_sigma = qa.sigma_multiplier * (1.0 + ((1.0 - qa.reliability_weight) * 10.0))

    obs = []
    if variable == "soil_moisture_vwc" and depth_interval:
        # Proper depth overlap mapping
        sm_0_10_frac = map_depth_overlap(depth_interval, (0, 10))
        sm_10_40_frac = map_depth_overlap(depth_interval, (10, 40))
        
        if sm_0_10_frac > 0.3:
            obs.append({"state_var": "sm_0_10", "value": value, "sigma": dynamic_sigma / sm_0_10_frac})
        if sm_10_40_frac > 0.3:
            obs.append({"state_var": "root_zone_moisture", "value": value, "sigma": dynamic_sigma / sm_10_40_frac})

    # soil_temperature_c: No Kalman state observation.
    # The 9-variable state vector has no soil temperature state.
    # Soil temp is available as process forcing via map_to_process_forcing()
    # and through the environment package's reanalysis data.
        
    return obs


def map_to_process_forcing(
    variable: str,
    value: float,
    qa: SensorQAResult,
    rep: SensorRepresentativeness
) -> List[Any]:
    if qa.reliability_weight < 0.50:
        return [] # Too weak for process forcing
        
    forces = []
    if variable in ["rainfall_mm", "rain_rate_mm_h"]:
        forces.append({"forcing_type": "precipitation", "value": value})
    elif variable in ["air_temperature_c", "relative_humidity_pct", "wind_speed_ms", "solar_radiation_w_m2"]:
        forces.append({"forcing_type": "local_weather", "variable": variable, "value": value})
    # irrigation_flow_l_min handled exclusively by irrigation_event_detector to prevent double-counting
        
    return forces
