from typing import List, Dict

def validate_against_satellite(sensor_aggregates: List, satellite_context: dict) -> List[Dict]:
    events = []
    # Mock V1 rule: If SAR wetness is high and soil moisture is low -> mismatch
    # If SAR wetness is high and soil moisture is high -> confirmed
    
    sar_wetness = satellite_context.get("sar_wetness")
    
    soil_moisture_aggs = [a for a in sensor_aggregates if a.variable == "soil_moisture_vwc" and a.aggregate_type == "daily_mean"]
    
    if sar_wetness and soil_moisture_aggs:
        avg_sm = sum(a.value for a in soil_moisture_aggs) / len(soil_moisture_aggs)
        if sar_wetness > 0.7 and avg_sm < 0.2:
            events.append({"type": "SAR_SURFACE_MISMATCH", "reason": "SAR indicates wet but sensors are dry."})
        elif sar_wetness > 0.7 and avg_sm > 0.4:
            events.append({"type": "SAR_WETNESS_CONFIRMED", "reason": "SAR and sensors both indicate wet."})
            
    return events
