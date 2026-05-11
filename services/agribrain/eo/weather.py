"""
EO Weather Module
Handles weather data fetching from OpenWeatherMap and Open-Meteo.
Extracted from sentinel.py for separation of concerns.
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional

from eo.auth import EO_REQUEST_TIMEOUT

# ============================================================================
# Configuration
# ============================================================================

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_CURRENT_URL = "https://api.open-meteo.com/v1/forecast"


# ============================================================================
# Internal Helpers
# ============================================================================

def _fetch_open_meteo_weather(lat: float, lng: float) -> Optional[Dict]:
    """
    Fallback weather data from Open-Meteo (free, no API key required).
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lng,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m,surface_pressure,cloud_cover",
            "timezone": "auto"
        }
        response = requests.get(url, params=params, timeout=EO_REQUEST_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            current = data.get("current", {})
            
            # Map weather code to condition
            wmo_codes = {
                0: ("Clear", "clear sky"),
                1: ("Clear", "mainly clear"),
                2: ("Clouds", "partly cloudy"),
                3: ("Clouds", "overcast"),
                45: ("Fog", "fog"),
                48: ("Fog", "depositing rime fog"),
                51: ("Drizzle", "light drizzle"),
                53: ("Drizzle", "moderate drizzle"),
                55: ("Drizzle", "dense drizzle"),
                61: ("Rain", "slight rain"),
                63: ("Rain", "moderate rain"),
                65: ("Rain", "heavy rain"),
                71: ("Snow", "slight snow"),
                73: ("Snow", "moderate snow"),
                75: ("Snow", "heavy snow"),
                80: ("Rain", "rain showers"),
                95: ("Thunderstorm", "thunderstorm"),
            }
            code = current.get("weather_code", 0)
            condition, desc = wmo_codes.get(code, ("Clear", "unknown"))
            
            return {
                "location": f"Lat {lat:.2f}, Lng {lng:.2f}",
                "coordinates": {"lat": lat, "lng": lng},
                "weather": {
                    "condition": condition,
                    "description": desc,
                    "icon": "01d"
                },
                "temperature": {
                    "current": current.get("temperature_2m"),
                    "feels_like": current.get("apparent_temperature"),
                    "min": current.get("temperature_2m"),
                    "max": current.get("temperature_2m")
                },
                "humidity": current.get("relative_humidity_2m"),
                "pressure": current.get("surface_pressure"),
                "visibility_m": 10000,
                "wind": {
                    "speed_ms": current.get("wind_speed_10m"),
                    "direction_deg": current.get("wind_direction_10m"),
                    "gust_ms": None
                },
                "clouds_percent": current.get("cloud_cover"),
                "source": "open-meteo"
            }
    except Exception as e:
        print(f"Open-Meteo weather fetch error: {e}")
    return None


# ============================================================================
# Public API
# ============================================================================

def fetch_openweather_data(lat: float, lng: float) -> Optional[Dict]:
    """
    Fetches comprehensive weather data from OpenWeatherMap.
    Uses your existing OPENWEATHER_API_KEY from .env file.
    Returns: current weather, UV index, feels like, visibility, etc.
    """
    try:
        api_key = os.getenv("OPENWEATHER_API_KEY")
        
        if api_key:
            print(f"[KEY] OpenWeather API Key loaded: {api_key[:8]}...{api_key[-4:]}")
        else:
            print("[ERROR] OpenWeather API Key NOT FOUND in environment")
        
        if not api_key:
            return {
                "status": "api_key_required",
                "message": "Set OPENWEATHER_API_KEY environment variable"
            }
        
        # Strip quotes if present (common .env issue)
        api_key = api_key.strip().strip('"').strip("'")
        
        # Current weather + more details
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lng,
            "appid": api_key,
            "units": "metric"
        }
        
        response = requests.get(url, params=params, timeout=EO_REQUEST_TIMEOUT)
        
        if response.status_code != 200:
            print(f"OpenWeatherMap Error ({response.status_code}): {response.text}")
            print("Trying Open-Meteo fallback...")
            return _fetch_open_meteo_weather(lat, lng)
        
        data = response.json()
        main = data.get("main", {})
        wind = data.get("wind", {})
        weather = data.get("weather", [{}])[0]
        clouds = data.get("clouds", {})
        
        result = {
            "location": data.get("name"),
            "coordinates": {"lat": lat, "lng": lng},
            "weather": {
                "condition": weather.get("main"),
                "description": weather.get("description"),
                "icon": weather.get("icon")
            },
            "temperature": {
                "current": main.get("temp"),
                "feels_like": main.get("feels_like"),
                "min": main.get("temp_min"),
                "max": main.get("temp_max")
            },
            "humidity": main.get("humidity"),
            "pressure": main.get("pressure"),
            "visibility_m": data.get("visibility"),
            "wind": {
                "speed_ms": wind.get("speed"),
                "direction_deg": wind.get("deg"),
                "gust_ms": wind.get("gust")
            },
            "clouds_percent": clouds.get("all"),
            "source": "openweathermap"
        }
        
        # Try to get UV index (separate call)
        try:
            uv_url = "https://api.openweathermap.org/data/2.5/uvi"
            uv_params = {"lat": lat, "lon": lng, "appid": api_key}
            uv_response = requests.get(uv_url, params=uv_params, timeout=10)
            if uv_response.status_code == 200:
                uv_data = uv_response.json()
                result["uv_index"] = uv_data.get("value")
        except:
            pass  # UV index is optional
        
        return result

    except Exception as e:
        print(f"OpenWeatherMap fetch error: {e}")
        # Fallback to Open-Meteo (free, no API key needed)
        try:
            print("Trying Open-Meteo fallback...")
            return _fetch_open_meteo_weather(lat, lng)
        except Exception as e2:
            print(f"Open-Meteo fallback also failed: {e2}")
        return None


def fetch_openweather_forecast(lat: float, lng: float) -> Optional[Dict]:
    """
    Fetches 7-day weather forecast from Open-Meteo (Free, No API Key).
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lng,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max,precipitation_sum",
            "hourly": "relative_humidity_2m",
            "timezone": "auto",
            "forecast_days": 8
        }
        
        headers = {"Cache-Control": "no-cache"}
        response = requests.get(url, params=params, headers=headers, timeout=EO_REQUEST_TIMEOUT)
        
        if response.status_code != 200:
            print(f"Open-Meteo Forecast Error: {response.text}")
            return None
        
        data = response.json()
        daily = data.get("daily", {})
        hourly = data.get("hourly", {})
        
        if not daily.get("time"):
            return None

        # WMO Code Mapping
        wmo_map = {
            0: ("Clear", "سماء صافية", "01d"),
            1: ("Clear", "غائم جزئياً", "02d"),
            2: ("Clouds", "غائم جزئياً", "03d"),
            3: ("Clouds", "غائم", "04d"),
            45: ("Fog", "ضباب", "50d"),
            48: ("Fog", "ضباب جليدي", "50d"),
            51: ("Drizzle", "رذاذ خفيف", "09d"),
            53: ("Drizzle", "رذاذ متوسط", "09d"),
            55: ("Drizzle", "رذاذ كثيف", "09d"),
            61: ("Rain", "مطر خفيف", "10d"),
            63: ("Rain", "مطر متوسط", "10d"),
            65: ("Rain", "مطر غزير", "10d"),
            66: ("Rain", "مطر متجمد", "13d"),
            67: ("Rain", "مطر متجمد غزير", "13d"),
            71: ("Snow", "ثلوج خفيفة", "13d"),
            73: ("Snow", "ثلوج متوسطة", "13d"),
            75: ("Snow", "ثلوج كثيفة", "13d"),
            77: ("Snow", "حبيبات ثلجية", "13d"),
            80: ("Rain", "زخات مطر", "09d"),
            81: ("Rain", "زخات مطر متوسطة", "09d"),
            82: ("Rain", "زخات مطر غزيرة", "09d"),
            85: ("Snow", "زخات ثلج", "13d"),
            86: ("Snow", "زخات ثلج غزيرة", "13d"),
            95: ("Thunderstorm", "عاصفة رعدية", "11d"),
            96: ("Thunderstorm", "عاصفة رعدية مع برد", "11d"),
            99: ("Thunderstorm", "عاصفة رعدية شديدة", "11d"),
        }

        forecast_list = []
        timestamps = daily["time"]
        
        for i, date_str in enumerate(timestamps):
            if i >= 7: break
            
            code = daily["weather_code"][i]
            condition, desc, icon = wmo_map.get(code, ("Clouds", "غير معروف", "03d"))
            
            hum_idx = (i * 24) + 12
            humidity = 50
            if "relative_humidity_2m" in hourly and len(hourly["relative_humidity_2m"]) > hum_idx:
                humidity = hourly["relative_humidity_2m"][hum_idx]

            pop = daily.get("precipitation_probability_max", [])
            if i < len(pop) and pop[i] is not None:
                pop_val = pop[i] / 100.0
            else:
                pop_val = 0.0
                
            precip = daily.get("precipitation_sum", [])
            precip_val = precip[i] if i < len(precip) and precip[i] is not None else 0.0

            forecast_list.append({
                "date": date_str,
                "temp_min": daily["temperature_2m_min"][i],
                "temp_max": daily["temperature_2m_max"][i],
                "humidity": humidity,
                "weather": condition,
                "description": desc,
                "icon": icon,
                "wind_speed": daily["wind_speed_10m_max"][i],
                "pop": pop_val,
                "precipitation": precip_val
            })
        
        return {
            "location": {"lat": lat, "lng": lng},
            "forecast_days": len(forecast_list),
            "forecast": forecast_list,
            "source": "open-meteo-7day"
        }

    except Exception as e:
        print(f"Open-Meteo forecast error: {e}")
        return None


def fetch_historical_weather(lat: float, lng: float,
                              start_date: str, end_date: str) -> Optional[Dict]:
    """
    Fetches historical weather data from ERA5 via Open-Meteo.
    Note: Archive API only has data up to yesterday. We clamp end_date accordingly.
    """
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        clamped_end = min(end_date, yesterday)
        if clamped_end < start_date:
            print(f"[WARN] [Weather] Requested range ({start_date} to {end_date}) is entirely future. No archive data.")
            return None
        
        params = {
            "latitude": lat,
            "longitude": lng,
            "start_date": start_date,
            "end_date": clamped_end,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "temperature_2m_mean",
                "precipitation_sum",
                "rain_sum",
                "et0_fao_evapotranspiration",
                "shortwave_radiation_sum",
                "windspeed_10m_max"
            ],
            "timezone": "auto"
        }
        
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=EO_REQUEST_TIMEOUT)
        
        if response.status_code != 200:
            print(f"ERA5 API Error: {response.text}")
            return None
        
        data = response.json()
        daily = data.get("daily", {})
        
        if not daily.get("time"):
            return None
        
        records = []
        for i, date in enumerate(daily["time"]):
            records.append({
                "date": date,
                "temp_max": daily.get("temperature_2m_max", [None])[i],
                "temp_min": daily.get("temperature_2m_min", [None])[i],
                "temp_mean": daily.get("temperature_2m_mean", [None])[i],
                "precipitation": daily.get("precipitation_sum", [None])[i],
                "rain": daily.get("rain_sum", [None])[i],
                "et0": daily.get("et0_fao_evapotranspiration", [None])[i],
                "solar_radiation": daily.get("shortwave_radiation_sum", [None])[i],
                "wind_max": daily.get("windspeed_10m_max", [None])[i]
            })
        
        return {
            "location": {"lat": lat, "lng": lng},
            "period": {"start": start_date, "end": end_date},
            "record_count": len(records),
            "records": records,
            "source": "era5-open-meteo"
        }

    except Exception as e:
        print(f"Historical weather fetch error: {e}")
        return None
