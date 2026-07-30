"""
Drone Capability Profiles.

Pre-defined hardware abstractions for standard commercial drones
to enable accurate flight planning and feasibility checks.
"""

from typing import Dict
from .schemas import DroneCapabilityProfile

# Standard profiles for common agricultural drones
PROFILES: Dict[str, DroneCapabilityProfile] = {
    "dji_mavic_3_m": DroneCapabilityProfile(
        name="DJI Mavic 3 Multispectral",
        camera_fov_horizontal_deg=84.0,
        camera_fov_vertical_deg=62.0,  # Approx 4:3 ratio
        sensor_width_mm=17.3,          # 4/3 CMOS
        focal_length_mm=12.28,         # 24mm equivalent
        image_width_px=5280,
        image_height_px=3956,
        max_flight_time_min=43.0,
        max_speed_m_s=15.0,
        min_safe_altitude_m=5.0,
        max_safe_altitude_m=120.0,
        return_home_reserve_pct=20.0,
        wind_resistance_m_s=12.0
    ),
    "dji_phantom_4_rtk": DroneCapabilityProfile(
        name="DJI Phantom 4 RTK",
        camera_fov_horizontal_deg=84.0,
        camera_fov_vertical_deg=62.0,
        sensor_width_mm=13.2,          # 1-inch CMOS
        focal_length_mm=8.8,           # 24mm equivalent
        image_width_px=5472,
        image_height_px=3648,
        max_flight_time_min=30.0,
        max_speed_m_s=13.0,
        min_safe_altitude_m=5.0,
        max_safe_altitude_m=120.0,
        return_home_reserve_pct=25.0,
        wind_resistance_m_s=10.0
    ),
    "standard_prosumer": DroneCapabilityProfile(
        name="Generic Prosumer Drone (e.g. Mavic Air 2)",
        camera_fov_horizontal_deg=84.0,
        camera_fov_vertical_deg=62.0,
        sensor_width_mm=6.4,           # 1/2-inch CMOS
        focal_length_mm=4.5,           # 24mm equivalent
        image_width_px=4000,
        image_height_px=3000,
        max_flight_time_min=25.0,
        max_speed_m_s=12.0,
        min_safe_altitude_m=5.0,
        max_safe_altitude_m=120.0,
        return_home_reserve_pct=30.0,
        wind_resistance_m_s=8.0
    )
}

def get_profile(profile_name: str) -> DroneCapabilityProfile:
    """Get a drone profile by name, defaulting to standard_prosumer."""
    return PROFILES.get(profile_name, PROFILES["standard_prosumer"])
