from typing import List, Dict

from layer0.sensors.sensor_satellite_validation import validate_against_satellite
from layer0.sensors.sensor_weather_validation import validate_against_weather

def run_cross_validation(
    sensor_aggregates: List,
    satellite_context: dict | None,
    weather_context: dict | None
) -> List[Dict]:
    events = []
    
    if satellite_context:
        events.extend(validate_against_satellite(sensor_aggregates, satellite_context))
        
    if weather_context:
        events.extend(validate_against_weather(sensor_aggregates, weather_context))
        
    return events
