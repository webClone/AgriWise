"""
Observation Promoter — Archives EO cache entries as permanent PlotObservation records.

Called after each successful cache_put() when a plot_id is known.
Uses pymongo to write directly to the PlotObservation collection
(the same MongoDB instance that Prisma uses).

Design:
  - Extracts pre-computed ML features from raw API responses
  - Deduplicates by [plotId, source, obsDate, obsType]
  - Writes individual observation records for the ML training dataset
  - Updates PlotDNA observation counts
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def promote_to_observation(db, plot_id: str, source: str, lat: float, lng: float,
                           data: Any, fetched_at: Optional[datetime] = None) -> bool:
    """
    Promote a cached EO response to a permanent PlotObservation record.
    
    Args:
        db: pymongo database instance
        plot_id: MongoDB ObjectId string for the plot
        source: EO source identifier (e.g., "sentinel2_indices", "soilgrids")
        lat, lng: Plot coordinates
        data: Raw API response data
        fetched_at: When the data was fetched (defaults to now)
    
    Returns:
        True if a new observation was inserted, False if duplicate or error
    """
    if db is None or data is None or not plot_id:
        return False
    
    try:
        from bson import ObjectId
    except ImportError:
        # bson comes with pymongo
        return False
    
    now = fetched_at or datetime.now(timezone.utc)
    
    # Extract features based on source type
    obs_records = _extract_observations(source, data, now)
    
    if not obs_records:
        return False
    
    inserted = 0
    for obs in obs_records:
        try:
            doc = {
                "plotId": plot_id,
                "source": obs["source"],
                "obsType": obs["obs_type"],
                "obsDate": obs["obs_date"],
                "data": data if obs.get("include_raw", True) else {},
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "fetchedAt": now,
                "isReliable": True,
                **obs.get("features", {}),
            }
            
            # Upsert: skip if this exact observation already exists
            result = db.PlotObservation.update_one(
                {
                    "plotId": plot_id,
                    "source": obs["source"],
                    "obsDate": obs["obs_date"],
                    "obsType": obs["obs_type"],
                },
                {"$setOnInsert": doc},
                upsert=True,
            )
            
            if result.upserted_id:
                inserted += 1
                
        except Exception as e:
            print(f"[OBS_PROMOTER] Failed to insert {obs['source']}/{obs['obs_type']}: {e}")
            continue
    
    if inserted > 0:
        print(f"[OBS_PROMOTER] Archived {inserted} observation(s) for plot {plot_id[:8]}... ({source})")
        _update_observation_counts(db, plot_id, source, inserted)
    
    return inserted > 0


def _extract_observations(source: str, data: Any, fetch_time: datetime) -> list:
    """Extract one or more observation records from raw API data."""
    if not isinstance(data, dict):
        return []
    
    today = fetch_time.strftime("%Y-%m-%d")
    today_dt = datetime(fetch_time.year, fetch_time.month, fetch_time.day, tzinfo=timezone.utc)
    
    # ── Sentinel-2 Vegetation Indices ──────────────────────────────
    if source == "sentinel2_indices":
        obs_date_str = data.get("date", today)
        try:
            obs_date = datetime.strptime(obs_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            obs_date = today_dt
        
        return [{
            "source": "sentinel2",
            "obs_type": "indices",
            "obs_date": obs_date,
            "features": {
                "ndvi": data.get("ndvi"),
                "evi": data.get("evi"),
                "ndwi": data.get("ndwi"),
                "ndmi": data.get("ndmi"),
                "quality": 0.9 if data.get("ndvi") else 0.0,
            },
        }]
    
    # ── Sentinel-2 NDVI Timeseries ─────────────────────────────────
    if source == "sentinel2_ndvi_ts":
        observations = []
        ts_data = data.get("data", [])
        for obs in ts_data:
            obs_date_str = obs.get("date", "")
            if not obs_date_str:
                continue
            try:
                obs_date = datetime.strptime(obs_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            
            observations.append({
                "source": "sentinel2",
                "obs_type": "ndvi",
                "obs_date": obs_date,
                "include_raw": False,  # Don't store full timeseries payload per point
                "features": {
                    "ndvi": obs.get("ndvi"),
                    "cloudCover": obs.get("cloud_cover"),
                    "quality": max(0, 1.0 - (obs.get("cloud_cover", 0) / 100.0)),
                },
            })
        return observations
    
    # ── Sentinel-1 SAR (current) ───────────────────────────────────
    if source == "sentinel1_sar":
        return [{
            "source": "sentinel1",
            "obs_type": "sar_backscatter",
            "obs_date": today_dt,
            "features": {
                "vv": data.get("vv_db") or data.get("vv"),
                "vh": data.get("vh_db") or data.get("vh"),
                "vvVhRatio": data.get("vv_vh_ratio") or data.get("ratio"),
                "soilMoisture": data.get("estimated_moisture_pct"),
                "quality": 0.85,
            },
        }]
    
    # ── Sentinel-1 SAR Timeseries ──────────────────────────────────
    if source == "sentinel1_sar_ts":
        observations = []
        ts_data = data.get("data", data.get("timeseries", []))
        for obs in (ts_data if isinstance(ts_data, list) else []):
            d = obs.get("date") or obs.get("timestamp", "")[:10]
            if not d:
                continue
            try:
                obs_date = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            observations.append({
                "source": "sentinel1",
                "obs_type": "sar_backscatter",
                "obs_date": obs_date,
                "include_raw": False,
                "features": {
                    "vv": obs.get("vv"),
                    "vh": obs.get("vh"),
                    "vvVhRatio": obs.get("ratio") or obs.get("vv_vh_ratio"),
                    "quality": 0.85,
                },
            })
        return observations
    
    # ── SoilGrids ──────────────────────────────────────────────────
    if source == "soilgrids":
        return [{
            "source": "soilgrids",
            "obs_type": "soil_properties",
            "obs_date": today_dt,
            "features": {
                "soilPh": data.get("ph"),
                "soilOC": data.get("organic_carbon"),
                "soilN": data.get("nitrogen"),
                "soilClay": data.get("clay"),
                "soilSand": data.get("sand"),
                "quality": 0.3 if data.get("is_generic_fallback") else 0.85,
                "isReliable": not data.get("is_generic_fallback", False),
            },
        }]
    
    # ── OpenWeather Current ────────────────────────────────────────
    if source == "openweather_current":
        temp_data = data.get("temperature", {})
        temp_current = temp_data.get("current") if isinstance(temp_data, dict) else temp_data
        return [{
            "source": "weather",
            "obs_type": "current_weather",
            "obs_date": today_dt,
            "features": {
                "tempC": temp_current,
                "tempMin": temp_data.get("min") if isinstance(temp_data, dict) else None,
                "tempMax": temp_data.get("max") if isinstance(temp_data, dict) else None,
                "humidity": data.get("humidity"),
                "windMs": data.get("wind", {}).get("speed_ms") if isinstance(data.get("wind"), dict) else None,
                "quality": 0.95,
            },
        }]
    
    # ── OpenWeather Forecast ───────────────────────────────────────
    if source == "openweather_forecast":
        observations = []
        forecast_list = data.get("forecast", data.get("daily", []))
        for f in (forecast_list if isinstance(forecast_list, list) else []):
            d = f.get("date", "")
            if not d:
                continue
            try:
                obs_date = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            observations.append({
                "source": "forecast",
                "obs_type": "weather_forecast",
                "obs_date": obs_date,
                "include_raw": False,
                "features": {
                    "tempC": f.get("temp"),
                    "tempMin": f.get("temp_min"),
                    "tempMax": f.get("temp_max"),
                    "precipMm": f.get("rain") or f.get("precipitation") or 0,
                    "humidity": f.get("humidity"),
                    "windMs": f.get("wind_speed"),
                    "et0": f.get("et0"),
                    "quality": 0.7,  # Forecast = lower quality than observation
                },
            })
        return observations
    
    # ── Open-Meteo Archive ─────────────────────────────────────────
    if source == "open_meteo_archive":
        observations = []
        records = data.get("records", data.get("daily", []))
        for r in (records if isinstance(records, list) else []):
            d = r.get("date", "")
            if not d:
                continue
            try:
                obs_date = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            observations.append({
                "source": "weather",
                "obs_type": "historical_weather",
                "obs_date": obs_date,
                "include_raw": False,
                "features": {
                    "tempC": r.get("temp_mean") or r.get("temp"),
                    "tempMin": r.get("temp_min"),
                    "tempMax": r.get("temp_max"),
                    "precipMm": r.get("rain") or r.get("precipitation") or 0,
                    "humidity": r.get("humidity"),
                    "et0": r.get("et0"),
                    "solarRad": r.get("solar_radiation"),
                    "quality": 0.9,
                },
            })
        return observations
    
    # ── Water Balance ──────────────────────────────────────────────
    if source == "water_balance":
        observations = []
        records = data.get("records", [])
        for r in (records if isinstance(records, list) else []):
            d = r.get("date", "")
            if not d:
                continue
            try:
                obs_date = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            observations.append({
                "source": "weather",
                "obs_type": "water_balance",
                "obs_date": obs_date,
                "include_raw": False,
                "features": {
                    "et0": r.get("et0"),
                    "precipMm": r.get("precip"),
                    "quality": 0.85,
                },
            })
        return observations
    
    return []


def _update_observation_counts(db, plot_id: str, source: str, count: int):
    """Increment observation counts in PlotDNA."""
    try:
        # Map cache source names to PlotDNA counter keys
        source_map = {
            "sentinel2_indices": "sentinel2",
            "sentinel2_ndvi_ts": "sentinel2",
            "sentinel1_sar": "sentinel1",
            "sentinel1_sar_ts": "sentinel1",
            "soilgrids": "soilgrids",
            "openweather_current": "weather",
            "openweather_forecast": "weather",
            "open_meteo_archive": "weather",
            "water_balance": "weather",
        }
        counter_key = source_map.get(source, "other")
        
        db.PlotDNA.update_one(
            {"plotId": plot_id},
            {
                "$inc": {
                    f"observationCounts.{counter_key}": count,
                    "observationCounts.total": count,
                },
                "$set": {
                    "lastSeen": datetime.now(timezone.utc),
                },
            },
        )
    except Exception as e:
        # Non-critical — don't fail the main flow
        print(f"[OBS_PROMOTER] PlotDNA count update failed: {e}")
