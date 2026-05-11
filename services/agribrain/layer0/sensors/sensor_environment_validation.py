from typing import List, Dict


def validate_against_environment(sensor_aggregates: List, env_context: dict) -> List[Dict]:
    """
    Cross-validate sensor readings against environment reanalysis data.

    Checks:
    - Soil temperature vs reanalysis soil temperature (large deviations
      suggest sensor burial depth mismatch or calibration drift).
    - Relative humidity consistency (sensor RH vs reanalysis RH —
      a >30% difference flags potential sensor enclosure issues).
    - Solar radiation sanity (sensor pyranometer vs reanalysis shortwave
      radiation — large deviations suggest sensor shadowing or fouling).
    """
    events = []

    if not env_context:
        return events

    # --- Soil temperature cross-check ---
    env_soil_temp = env_context.get("soil_temperature_c") or env_context.get("soil_temp_c")
    soil_temp_aggs = [
        a for a in sensor_aggregates
        if a.variable == "soil_temperature_c" and a.aggregate_type == "daily_mean"
    ]
    if env_soil_temp is not None and soil_temp_aggs:
        avg_sensor_temp = sum(a.value for a in soil_temp_aggs) / len(soil_temp_aggs)
        diff = abs(avg_sensor_temp - env_soil_temp)
        if diff > 8.0:
            events.append({
                "type": "SOIL_TEMP_REANALYSIS_MISMATCH",
                "reason": (
                    f"Sensor soil temp ({avg_sensor_temp:.1f}°C) differs from "
                    f"reanalysis ({env_soil_temp:.1f}°C) by {diff:.1f}°C. "
                    "Possible burial depth mismatch or calibration drift."
                ),
                "sensor_value": avg_sensor_temp,
                "reanalysis_value": env_soil_temp,
                "severity": "warning",
            })
        elif diff < 2.0:
            events.append({
                "type": "SOIL_TEMP_REANALYSIS_CONFIRMED",
                "reason": "Sensor soil temperature consistent with reanalysis.",
                "severity": "info",
            })

    # --- Relative humidity cross-check ---
    env_rh = env_context.get("relative_humidity_pct") or env_context.get("rh_pct")
    rh_aggs = [
        a for a in sensor_aggregates
        if a.variable == "relative_humidity_pct" and a.aggregate_type == "daily_mean"
    ]
    if env_rh is not None and rh_aggs:
        avg_sensor_rh = sum(a.value for a in rh_aggs) / len(rh_aggs)
        diff_rh = abs(avg_sensor_rh - env_rh)
        if diff_rh > 30.0:
            events.append({
                "type": "RH_REANALYSIS_MISMATCH",
                "reason": (
                    f"Sensor RH ({avg_sensor_rh:.0f}%) differs from "
                    f"reanalysis ({env_rh:.0f}%) by {diff_rh:.0f}%. "
                    "Possible sensor enclosure ventilation issue."
                ),
                "sensor_value": avg_sensor_rh,
                "reanalysis_value": env_rh,
                "severity": "warning",
            })

    # --- Solar radiation cross-check ---
    env_radiation = env_context.get("shortwave_radiation_w_m2") or env_context.get("solar_radiation_w_m2")
    rad_aggs = [
        a for a in sensor_aggregates
        if a.variable == "solar_radiation_w_m2" and a.aggregate_type == "daily_mean"
    ]
    if env_radiation is not None and rad_aggs:
        avg_sensor_rad = sum(a.value for a in rad_aggs) / len(rad_aggs)
        # Large negative deviation = sensor shadowing; large positive = calibration drift
        if env_radiation > 50 and avg_sensor_rad < env_radiation * 0.4:
            events.append({
                "type": "RADIATION_SENSOR_SHADOWING",
                "reason": (
                    f"Sensor radiation ({avg_sensor_rad:.0f} W/m²) is <40% of "
                    f"reanalysis ({env_radiation:.0f} W/m²). "
                    "Possible pyranometer shadowing or fouling."
                ),
                "sensor_value": avg_sensor_rad,
                "reanalysis_value": env_radiation,
                "severity": "warning",
            })

    return events
