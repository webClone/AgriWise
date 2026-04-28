"""Shared test fixtures for environment engine tests."""

# Complete SoilGrids response for a clay loam soil
SOILGRIDS_COMPLETE = {
    "0-5cm": {
        "bdod": {"mean": 135, "Q0.05": 120, "Q0.5": 134, "Q0.95": 150},
        "clay": {"mean": 280, "Q0.05": 240, "Q0.5": 275, "Q0.95": 320},
        "silt": {"mean": 350, "Q0.05": 310, "Q0.5": 348, "Q0.95": 390},
        "sand": {"mean": 370, "Q0.05": 330, "Q0.5": 368, "Q0.95": 410},
        "cfvo": {"mean": 50, "Q0.05": 30, "Q0.5": 48, "Q0.95": 80},
        "phh2o": {"mean": 65, "Q0.05": 58, "Q0.5": 64, "Q0.95": 72},
        "soc": {"mean": 150, "Q0.05": 100, "Q0.5": 145, "Q0.95": 200},
        "cec": {"mean": 200, "Q0.05": 150, "Q0.5": 195, "Q0.95": 250},
        "nitrogen": {"mean": 150, "Q0.05": 100, "Q0.5": 145, "Q0.95": 200},
        "wv003": {"mean": 350, "Q0.05": 300, "Q0.5": 345, "Q0.95": 400},
        "wv1500": {"mean": 180, "Q0.05": 140, "Q0.5": 175, "Q0.95": 220},
    },
    "5-15cm": {
        "bdod": {"mean": 140}, "clay": {"mean": 290}, "silt": {"mean": 340},
        "sand": {"mean": 370}, "cfvo": {"mean": 55}, "phh2o": {"mean": 64},
        "soc": {"mean": 120}, "cec": {"mean": 190}, "nitrogen": {"mean": 130},
        "wv003": {"mean": 340}, "wv1500": {"mean": 185},
    },
    "15-30cm": {
        "bdod": {"mean": 145}, "clay": {"mean": 300}, "silt": {"mean": 330},
        "sand": {"mean": 370}, "cfvo": {"mean": 60}, "phh2o": {"mean": 63},
        "soc": {"mean": 90}, "cec": {"mean": 180}, "nitrogen": {"mean": 100},
        "wv003": {"mean": 330}, "wv1500": {"mean": 190},
    },
    "30-60cm": {
        "bdod": {"mean": 150}, "clay": {"mean": 320}, "silt": {"mean": 320},
        "sand": {"mean": 360}, "cfvo": {"mean": 70}, "phh2o": {"mean": 62},
        "soc": {"mean": 60}, "cec": {"mean": 170}, "nitrogen": {"mean": 80},
        "wv003": {"mean": 320}, "wv1500": {"mean": 195},
    },
    "60-100cm": {
        "bdod": {"mean": 155}, "clay": {"mean": 330}, "silt": {"mean": 310},
        "sand": {"mean": 360}, "cfvo": {"mean": 80}, "phh2o": {"mean": 61},
        "soc": {"mean": 40}, "cec": {"mean": 160}, "nitrogen": {"mean": 60},
        "wv003": {"mean": 310}, "wv1500": {"mean": 200},
    },
    "100-200cm": {
        "bdod": {"mean": 160}, "clay": {"mean": 340}, "silt": {"mean": 300},
        "sand": {"mean": 360}, "cfvo": {"mean": 90}, "phh2o": {"mean": 60},
        "soc": {"mean": 20}, "cec": {"mean": 150}, "nitrogen": {"mean": 40},
        "wv003": {"mean": 300}, "wv1500": {"mean": 205},
    },
}

# FAO/HWSD context for a typical Mediterranean field
FAO_COMPLETE = {
    "soil_mapping_unit": "Lv12-2b",
    "dominant_soil_type": "Luvisol",
    "secondary_soil_type": "Calcisol",
    "ipcc_soil_group": "HAC",
    "topsoil_texture": "medium",
    "subsoil_texture": "fine",
    "soil_depth_class": "deep",
    "salinity_risk": "none",
    "sodicity_risk": "none",
    "calcareous_lime_risk": "moderate",
    "gypsum_risk": "none",
    "drainage_limitation": "none",
    "agro_ecological_flags": ["irrigated_possible", "rainfed_suitable"],
}

# Open-Meteo 7-day historical + 3-day forecast response
OPEN_METEO_RESPONSE = {
    "daily": {
        "time": [
            "2026-04-20", "2026-04-21", "2026-04-22", "2026-04-23",
            "2026-04-24", "2026-04-25", "2026-04-26",
        ],
        "temperature_2m_min": [8.5, 9.1, 7.2, 10.3, 11.0, 9.8, 8.0],
        "temperature_2m_max": [22.3, 23.1, 20.5, 24.0, 25.2, 22.0, 21.5],
        "temperature_2m_mean": [15.4, 16.1, 13.8, 17.2, 18.1, 15.9, 14.8],
        "precipitation_sum": [0.0, 2.5, 15.0, 0.0, 0.0, 0.0, 8.0],
        "rain_sum": [0.0, 2.5, 15.0, 0.0, 0.0, 0.0, 8.0],
        "et0_fao_evapotranspiration": [3.2, 3.5, 2.8, 3.8, 4.0, 3.4, 3.0],
        "vapour_pressure_deficit_max": [1.2, 1.4, 0.8, 1.6, 1.8, 1.3, 1.0],
        "shortwave_radiation_sum": [18.5, 20.0, 14.0, 22.0, 23.5, 19.0, 16.0],
        "windspeed_10m_max": [5.2, 4.8, 7.5, 3.2, 4.0, 5.5, 6.0],
        "relative_humidity_2m_mean": [65, 60, 78, 55, 50, 62, 70],
        "soil_moisture_0_to_1cm_mean": [0.28, 0.27, 0.35, 0.30, 0.28, 0.26, 0.32],
        "soil_moisture_1_to_3cm_mean": [0.30, 0.29, 0.36, 0.31, 0.29, 0.28, 0.33],
        "soil_moisture_3_to_9cm_mean": [0.32, 0.31, 0.35, 0.33, 0.31, 0.30, 0.34],
        "soil_moisture_9_to_27cm_mean": [0.34, 0.33, 0.35, 0.34, 0.33, 0.32, 0.35],
        "soil_moisture_27_to_81cm_mean": [0.36, 0.35, 0.36, 0.36, 0.35, 0.34, 0.36],
    },
    "timezone": "Europe/Berlin",
}

# OpenWeather 7-day response (same dates)
OPENWEATHER_RESPONSE = {
    "daily": [
        {"date": "2026-04-20", "temp": {"min": 8.8, "max": 22.0, "day": 15.5}, "humidity": 63, "pressure": 1015, "wind_speed": 5.0, "clouds": 30, "rain": 0.0},
        {"date": "2026-04-21", "temp": {"min": 9.5, "max": 22.8, "day": 16.0}, "humidity": 58, "pressure": 1013, "wind_speed": 4.5, "clouds": 25, "rain": 3.0},
        {"date": "2026-04-22", "temp": {"min": 7.5, "max": 20.0, "day": 13.5}, "humidity": 75, "pressure": 1008, "wind_speed": 7.0, "clouds": 80, "rain": 18.0},
        {"date": "2026-04-23", "temp": {"min": 10.0, "max": 24.5, "day": 17.0}, "humidity": 53, "pressure": 1016, "wind_speed": 3.5, "clouds": 15, "rain": 0.0},
        {"date": "2026-04-24", "temp": {"min": 11.5, "max": 25.0, "day": 18.0}, "humidity": 48, "pressure": 1018, "wind_speed": 4.2, "clouds": 10, "rain": 0.0},
        {"date": "2026-04-25", "temp": {"min": 10.0, "max": 21.5, "day": 15.5}, "humidity": 60, "pressure": 1014, "wind_speed": 5.8, "clouds": 40, "rain": 0.0},
        {"date": "2026-04-26", "temp": {"min": 8.5, "max": 21.0, "day": 14.5}, "humidity": 68, "pressure": 1012, "wind_speed": 6.2, "clouds": 55, "rain": 0.0},
    ],
}
