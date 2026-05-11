def extract_layer1_detailed_data(data: dict) -> list:
    """
    Extracts rich metrics from the L1 (Data Fusion) payload.
    Computes a confidence score for each metric and sorts them descending.
    """
    metrics = []

    sources_active = data.get("sources_active", 0)
    sources = data.get("sources", {})
    ndvi_records = data.get("ndvi_records", [])
    sar_data = data.get("sar_data", {})
    weather_data = data.get("weather_data", {})

    # 1. Fusion State Overview
    metrics.append({
        "name": "Fusion Engine Status",
        "value": f"{sources_active}/3 Active",
        "confidence": 0.95 if sources_active >= 2 else 0.5,
        "reason": "Kalman filter is successfully merging multiple sensory inputs." if sources_active >= 2 else "Degraded fusion state. Limited sensory overlap."
    })

    # 2. Kalman Filter Stability
    if ndvi_records:
        latest_kf = ndvi_records[-1]
        kf_conf = latest_kf.get("confidence", 0)
        days_since = latest_kf.get("days_since_obs", 0)
        
        metrics.append({
            "name": "Kalman Filter Certainty",
            "value": f"{(kf_conf * 100):.1f}%",
            "confidence": kf_conf,
            "reason": f"Derived from state estimation variance. Last direct satellite observation was {days_since} days ago."
        })
    else:
        metrics.append({
            "name": "Kalman Filter Certainty",
            "value": "Unavailable",
            "confidence": 0.1,
            "reason": "No Kalman state vectors available in current assimilation window."
        })

    # 3. Optical Sensor (Sentinel-2) Status
    if sources.get("optical"):
        metrics.append({
            "name": "Optical (Sentinel-2)",
            "value": "Active",
            "confidence": 0.9,
            "reason": "Clear canopy signal. Primary driver for vegetation indexes."
        })
    else:
        metrics.append({
            "name": "Optical (Sentinel-2)",
            "value": "Offline / Cloudy",
            "confidence": 0.3,
            "reason": "Cloud cover obscured the plot. Kalman state relies on SAR and phenology models."
        })

    # 4. SAR Sensor (Sentinel-1) Status
    if sources.get("sar"):
        vv = sar_data.get("vv", -15.0)
        metrics.append({
            "name": "SAR (Sentinel-1)",
            "value": f"Active (VV: {vv:.1f})",
            "confidence": 0.85,
            "reason": "Radar backscatter provides structural and soil moisture proxies independent of clouds."
        })
    else:
        metrics.append({
            "name": "SAR (Sentinel-1)",
            "value": "Awaiting Pass",
            "confidence": 0.4,
            "reason": "No recent orbital pass over the plot bounding box."
        })

    # 5. Weather Assimilation
    if sources.get("weather"):
        metrics.append({
            "name": "Meteorological Input",
            "value": "Synched",
            "confidence": 0.9,
            "reason": "Weather telemetry actively feeding evapotranspiration and biotic pressure models."
        })
    else:
        metrics.append({
            "name": "Meteorological Input",
            "value": "Fallback",
            "confidence": 0.5,
            "reason": "Local station unavailable. Using Hargreaves equations and historical grid approximations."
        })

    # Sort descending by confidence
    metrics.sort(key=lambda x: x["confidence"], reverse=True)
    return metrics
