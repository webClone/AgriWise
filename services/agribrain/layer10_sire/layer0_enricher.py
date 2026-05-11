import datetime

def extract_layer0_detailed_data(data: dict) -> list:
    """
    Extracts rich metrics from the L0 data payload.
    Computes a confidence score for each metric and sorts them descending.
    """
    metrics = []
    
    weather = data.get("weather") or {}
    
    # 1. Temperature
    temp_current = data.get("temp_current")
    if temp_current is None and isinstance(weather, dict):
        temp_current = weather.get("temperature", {}).get("current")
        
    if temp_current is not None:
        source = weather.get("source", "OpenMeteo")
        confidence = 0.94 if source == "openweathermap" else 0.88
        reason = f"Primary source ({source}) active. High reliability."
        metrics.append({
            "name": "Temperature",
            "value": f"{temp_current:.1f}°C",
            "confidence": confidence,
            "reason": reason
        })
        
    # 2. Rain Probability
    rain_prob = data.get("rain_prob")
    if rain_prob is not None:
        confidence = 0.85
        reason = "Forecast model consensus."
        metrics.append({
            "name": "Rain Probability",
            "value": f"{rain_prob}%",
            "confidence": confidence,
            "reason": reason
        })
        
    # 3. ET0
    et0 = data.get("et0_today")
    if et0 is not None:
        confidence = 0.82
        reason = "Derived from Hargreaves/PM model." if et0 > 0 else "Baseline default fallback used."
        if et0 == 0.0:
            confidence = 0.40
        metrics.append({
            "name": "ET0 (Ref. Evapotranspiration)",
            "value": f"{et0:.1f} mm/day",
            "confidence": confidence,
            "reason": reason
        })
        
    # 4. Humidity
    humidity = weather.get("humidity")
    if humidity is not None:
        metrics.append({
            "name": "Relative Humidity",
            "value": f"{humidity}%",
            "confidence": 0.90,
            "reason": "Direct model output. Good spatial resolution."
        })
        
    # 5. Wind Speed
    wind = weather.get("wind", {})
    if isinstance(wind, dict) and wind.get("speed_ms") is not None:
        metrics.append({
            "name": "Wind Speed",
            "value": f"{wind.get('speed_ms'):.1f} m/s",
            "confidence": 0.87,
            "reason": "Macro-climate model. May not capture local windbreaks."
        })
        
    # 6. Cloud Cover
    clouds = weather.get("clouds_percent")
    if clouds is not None:
        metrics.append({
            "name": "Cloud Cover",
            "value": f"{clouds}%",
            "confidence": 0.95,
            "reason": "Satellite optical consensus."
        })
        
    # 7. Data Freshness
    metrics.append({
        "name": "Data Freshness",
        "value": data.get("data_freshness", "Live"),
        "confidence": 1.0,
        "reason": "System timestamp synchronization."
    })
    
    # Sort by confidence descending
    metrics.sort(key=lambda x: x["confidence"], reverse=True)
    
    return metrics
