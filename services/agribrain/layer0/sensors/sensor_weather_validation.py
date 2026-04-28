from typing import List, Dict

def validate_against_weather(sensor_aggregates: List, weather_context: dict) -> List[Dict]:
    events = []
    
    forecast_rain = weather_context.get("forecast_rainfall_mm", 0.0)
    rain_aggs = [a for a in sensor_aggregates if a.variable == "rainfall_mm" and a.aggregate_type == "rain_event_total"]
    
    if rain_aggs:
        sensor_rain = max(a.value for a in rain_aggs)
        if sensor_rain > 0 and forecast_rain == 0:
            events.append({"type": "UNFORECASTED_RAIN", "reason": "Sensor detected rain not in forecast."})
        elif sensor_rain == 0 and forecast_rain > 5.0:
            events.append({"type": "FORECAST_RAIN_MISSED", "reason": "Forecasted rain not detected by gauge."})
            
    return events
