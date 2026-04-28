from typing import Any, Dict, Literal

def parse_geo_context_placement(
    sensor_placement_type: str, 
    geo_context: Dict[str, Any] | None
) -> Literal[
    "representative_zone",
    "known_wet_spot",
    "known_dry_spot",
    "edge",
    "irrigation_line",
    "weather_station",
    "control_point",
    "unknown"
]:
    """
    Combines the registered placement type with Geo Context validations.
    If Geo Context flags an 'edge' sensor as 'interior', we might adjust, but for V1 we trust
    the physical registry mapping, just augmenting with Geo Context flags.
    """
    if not sensor_placement_type:
        return "unknown"
    return sensor_placement_type
