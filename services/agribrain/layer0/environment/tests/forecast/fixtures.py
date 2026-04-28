"""Shared test fixtures for Weather Forecast V1.1 tests."""

# Open-Meteo 7-day forecast response (hourly + daily)
OPEN_METEO_FORECAST_RESPONSE = {
    "hourly": {
        "time": [f"2026-04-26T{h:02d}:00" for h in range(24)] * 7,
        "temperature_2m": [12 + (h % 12) for h in range(168)],
        "relative_humidity_2m": [70 - (h % 24) for h in range(168)],
        "dew_point_2m": [8 + (h % 6) for h in range(168)],
        "precipitation": [0.0] * 48 + [2.0, 5.0, 0.0] + [0.0] * 117,
        "rain": [0.0] * 48 + [2.0, 5.0, 0.0] + [0.0] * 117,
        "precipitation_probability": [10] * 48 + [60, 80, 20] + [10] * 117,
        "cloud_cover": [30] * 168,
        "shortwave_radiation": [400 if 6 <= h % 24 <= 18 else 0 for h in range(168)],
        "et0_fao_evapotranspiration": [0.3 if 6 <= h % 24 <= 18 else 0.0 for h in range(168)],
        "vapour_pressure_deficit": [1.2 + (h % 12) * 0.1 for h in range(168)],
        "wind_speed_10m": [3.5 + (h % 8) * 0.5 for h in range(168)],
        "wind_direction_10m": [350, 10, 5, 355, 0, 15, 340, 20] * 21,
        "wind_gusts_10m": [6.0 + (h % 8) * 0.8 for h in range(168)],
        "surface_pressure": [1013] * 168,
        "soil_temperature_0cm": [15] * 168,
        "soil_temperature_6cm": [14] * 168,
        "soil_temperature_18cm": [13] * 168,
        "soil_temperature_54cm": [12] * 168,
        "soil_moisture_0_to_1cm": [0.28] * 168,
        "soil_moisture_1_to_3cm": [0.30] * 168,
        "soil_moisture_3_to_9cm": [0.32] * 168,
        "soil_moisture_9_to_27cm": [0.34] * 168,
        "soil_moisture_27_to_81cm": [0.36] * 168,
        "weather_code": [0] * 168,
    },
    "daily": {
        "time": [f"2026-04-{26+d}" for d in range(7)],
        "temperature_2m_min": [8.5, 9.1, 7.2, 10.3, 11.0, 9.8, 8.0],
        "temperature_2m_max": [22.3, 23.1, 20.5, 24.0, 25.2, 22.0, 21.5],
        "temperature_2m_mean": [15.4, 16.1, 13.8, 17.2, 18.1, 15.9, 14.8],
        "precipitation_sum": [0.0, 0.0, 7.0, 0.0, 0.0, 0.0, 0.0],
        "rain_sum": [0.0, 0.0, 7.0, 0.0, 0.0, 0.0, 0.0],
        "et0_fao_evapotranspiration": [3.2, 3.5, 2.8, 3.8, 4.0, 3.4, 3.0],
        "vapour_pressure_deficit_max": [1.2, 1.4, 0.8, 1.6, 1.8, 1.3, 1.0],
        "shortwave_radiation_sum": [18.5, 20.0, 14.0, 22.0, 23.5, 19.0, 16.0],
        "windspeed_10m_max": [5.2, 4.8, 7.5, 3.2, 4.0, 5.5, 6.0],
        "windgusts_10m_max": [8.1, 7.5, 12.0, 5.5, 6.5, 9.0, 10.0],
        "cloudcover_mean": [30, 25, 80, 15, 10, 40, 55],
    },
}

# OpenWeather 8-day forecast (to test trimming to 7)
OPENWEATHER_FORECAST_RESPONSE = {
    "daily": [
        {"date": f"2026-04-{26+d}", "temp": {"min": 8.8 + d*0.2, "max": 22.0 + d*0.3, "day": 15.5 + d*0.2}, "humidity": 63, "pressure": 1015, "wind_speed": 5.0 + d*0.3, "wind_gust": 8.0 + d*0.5, "wind_deg": 350 + d*5, "clouds": 30, "rain": 0.0 if d != 2 else 10.0, "pop": 0.1 if d != 2 else 0.8}
        for d in range(8)
    ],
    "hourly": [
        {"timestamp": f"2026-04-26T{h:02d}:00", "date": "2026-04-26",
         "main": {"temp": 15 + h % 8, "humidity": 60, "pressure": 1013},
         "wind": {"speed": 4.0, "gust": 7.0, "deg": 10},
         "clouds": {"all": 30}, "rain": {"1h": 0}, "pop": 10}
        for h in range(48)
    ],
}

# CHIRPS mock data
CHIRPS_RESPONSE = {
    "records": [
        {"date": f"2026-04-{d:02d}", "precipitation": 2.5 if d % 3 == 0 else 0.0}
        for d in range(1, 26)
    ],
    "latitude": -1.23,
    "longitude": 36.82,
}

# NASA POWER mock data
NASA_POWER_RESPONSE = {
    "properties": {
        "parameter": {
            "ALLSKY_SFC_SW_DWN": {f"2026042{d}": 18.5 + d for d in range(6)},
            "T2M_MAX": {f"2026042{d}": 25.0 + d * 0.5 for d in range(6)},
            "T2M_MIN": {f"2026042{d}": 10.0 + d * 0.3 for d in range(6)},
            "T2M": {f"2026042{d}": 17.5 + d * 0.4 for d in range(6)},
            "RH2M": {f"2026042{d}": 60 for d in range(6)},
            "WS2M": {f"2026042{d}": 3.5 for d in range(6)},
            "PRECTOTCORR": {f"2026042{d}": 1.0 if d == 2 else 0.0 for d in range(6)},
        },
    },
    "geometry": {"coordinates": [36.82, -1.23]},
}

# ERA5-Land mock data
ERA5_RESPONSE = {
    "records": [
        {"date": f"2026-04-{d:02d}", "t2m_max": 25 + d * 0.2, "t2m_min": 10 + d * 0.1, "t2m_mean": 17.5, "swvl1": 0.28 - d * 0.002, "total_precipitation_mm": 0.0}
        for d in range(1, 11)
    ],
    "latitude": -1.23,
    "longitude": 36.82,
}
