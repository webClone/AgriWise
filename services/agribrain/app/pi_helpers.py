"""
Plot Intelligence Helpers
Extracted from the monolithic api_plot_intelligence endpoint.
Each function is independently fault-tolerant.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Standardised pool timeout (individual calls capped at 15s by EO_REQUEST_TIMEOUT)
_POOL_TIMEOUT = 35


def fetch_all_sources(lat: float, lng: float, days_past: int, days_future: int) -> Dict[str, Any]:
    """Run all L0 data fetches in parallel. Returns dict of results."""
    from eo.sentinel import (
        fetch_openweather_data, fetch_openweather_forecast,
        fetch_vegetation_indices, fetch_soil_moisture_proxy,
        fetch_soil_properties, fetch_water_balance,
        fetch_historical_weather, fetch_ndvi_timeseries,
        fetch_sar_timeseries,
    )

    now = datetime.now(timezone.utc)
    past_start = now - timedelta(days=days_past)

    def _fetch(name, fn, *args):
        try:
            return name, fn(*args)
        except Exception as e:
            print(f"[PI] {name} failed: {e}")
            return name, None

    _tasks = [
        ("weather",   fetch_openweather_data,    lat, lng),
        ("forecast",  fetch_openweather_forecast, lat, lng),
        ("indices",   fetch_vegetation_indices,   lat, lng),
        ("sar_ts",    fetch_sar_timeseries,       lat, lng, days_past),
        ("sar",       fetch_soil_moisture_proxy,  lat, lng),
        ("soil",      fetch_soil_properties,      lat, lng),
        ("water",     fetch_water_balance,        lat, lng, days_past, days_future),
        ("hist",      fetch_historical_weather,   lat, lng,
                      past_start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")),
        ("ndvi_ts",   fetch_ndvi_timeseries,      lat, lng, days_past + days_future),
    ]

    results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch, t[0], t[1], *t[2:]): t[0] for t in _tasks}
        try:
            for fut in as_completed(futures, timeout=_POOL_TIMEOUT):
                name, val = fut.result()
                results[name] = val
        except TimeoutError:
            # Graceful degradation: collect whatever finished, skip the rest
            finished = {futures[f] for f in futures if f.done()}
            pending = {futures[f] for f in futures if not f.done()}
            print(f"[PI] Pool timeout: {len(pending)} sources still pending: {pending}")
            for f in futures:
                if not f.done():
                    f.cancel()
                    results[futures[f]] = None
                elif futures[f] not in results:
                    try:
                        name, val = f.result(timeout=0)
                        results[name] = val
                    except Exception:
                        results[futures[f]] = None

    return results


def hargreaves_et0(t_max: float, t_min: float, lat_deg: float, doy: int) -> float:
    """Hargreaves-Samani reference ET0 in mm/day."""
    try:
        import math
        lat_rad = math.radians(lat_deg)
        dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
        delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
        ws = math.acos(-math.tan(lat_rad) * math.tan(delta))
        Ra = (24 * 60 / math.pi) * 0.0820 * dr * (
            ws * math.sin(lat_rad) * math.sin(delta)
            + math.cos(lat_rad) * math.cos(delta) * math.sin(ws)
        )
        t_mean = (t_max + t_min) / 2
        et0 = 0.0023 * Ra * (t_mean + 17.8) * math.sqrt(max(0, t_max - t_min))
        return round(max(0.0, et0), 2)
    except Exception:
        return 0.0  # Don't fabricate ET0 on error


def build_timeline(results: Dict, lat: float, days_past: int, days_future: int) -> tuple:
    """Build timeline dict + ndvi_records from raw results. Returns (timeline, ndvi_records)."""
    now = datetime.now(timezone.utc)
    hist_weather = results.get("hist")
    forecast_data = results.get("forecast")
    indices_data = results.get("indices")
    ndvi_ts = results.get("ndvi_ts")
    water_data = results.get("water")
    sar_ts_data = results.get("sar_ts")

    # Historical records
    hist_records = []
    if hist_weather:
        raw_records = hist_weather.get("records") or hist_weather.get("daily") or []
        for r in raw_records:
            t_max = r.get("temp_max") if r.get("temp_max") is not None else r.get("temp")
            t_min = r.get("temp_min")
            try:
                fdate = r.get("date", "")
                doy = datetime.strptime(fdate, "%Y-%m-%d").timetuple().tm_yday if fdate else now.timetuple().tm_yday
            except Exception:
                doy = now.timetuple().tm_yday
            # Preserve real 0.0 ET0 values (rainy days) — only fallback on None
            et0_raw = r.get("et0")
            if et0_raw is not None:
                et0_val = et0_raw
            elif t_max is not None and t_min is not None:
                et0_val = hargreaves_et0(t_max, t_min, lat, doy)
            else:
                et0_val = None
            hist_records.append({
                "date": r.get("date"), "timestamp": r.get("date"),
                "temp": r.get("temp_mean") or r.get("temp"),
                "temp_max": t_max, "temp_min": t_min,
                "rain": r.get("rain") or r.get("precipitation") or 0,
                "et0": et0_val, "humidity": r.get("humidity"),
                "wind_max": r.get("wind_max"), "solar_radiation": r.get("solar_radiation"),
            })

    # Forecast records
    forecast_records = []
    if forecast_data:
        raw_forecast = forecast_data.get("forecast") or forecast_data.get("daily") or []
        for f in raw_forecast:
            t_max = f.get("temp_max") if f.get("temp_max") is not None else f.get("temp")
            t_min = f.get("temp_min")
            try:
                fdate = f.get("date", "")
                doy = datetime.strptime(fdate, "%Y-%m-%d").timetuple().tm_yday if fdate else now.timetuple().tm_yday
            except Exception:
                doy = now.timetuple().tm_yday
            et0_raw = f.get("et0")
            if et0_raw is not None:
                et0_fc = et0_raw
            elif t_max is not None and t_min is not None:
                et0_fc = hargreaves_et0(t_max, t_min, lat, doy)
            else:
                et0_fc = None
            forecast_records.append({
                "date": f.get("date"), "temp": f.get("temp") or t_max,
                "temp_min": t_min, "temp_max": t_max,
                "humidity": f.get("humidity"),
                "rain_mm": f.get("rain") or f.get("precipitation") or 0,
                "rain_prob": f.get("pop") or 0,
                "description": f.get("description") or f.get("weather") or "",
                "et0": et0_fc, "wind_speed": f.get("wind_speed"),
            })

    # Kalman NDVI assimilation
    ndvi_records = []
    try:
        from layer0.kalman_engine import DailyAssimilationEngine, KalmanObservation
        import math

        start_d = now - timedelta(days=days_past)
        end_d = now + timedelta(days=days_future)
        start_str_kf = start_d.strftime("%Y-%m-%d")
        end_str_kf = end_d.strftime("%Y-%m-%d")

        daily_weather_kf: Dict[str, Dict[str, float]] = {}
        for rec in hist_records:
            d = rec.get("date", "")
            if d:
                _kf_tmax = rec.get("temp_max") if rec.get("temp_max") is not None else 20.0
                _kf_tmin = rec.get("temp_min") if rec.get("temp_min") is not None else 10.0
                _kf_et0 = rec.get("et0") if rec.get("et0") is not None else 3.0
                daily_weather_kf[d] = {"temp_max": _kf_tmax, "temp_min": _kf_tmin,
                                       "precipitation": rec.get("rain") or 0.0, "et0": _kf_et0}
        for rec in forecast_records:
            d = rec.get("date", "")
            if d:
                _kf_tmax = rec.get("temp_max") if rec.get("temp_max") is not None else 20.0
                _kf_tmin = rec.get("temp_min") if rec.get("temp_min") is not None else 10.0
                _kf_et0 = rec.get("et0") if rec.get("et0") is not None else 3.0
                daily_weather_kf[d] = {"temp_max": _kf_tmax, "temp_min": _kf_tmin,
                                       "precipitation": rec.get("rain_mm") or 0.0, "et0": _kf_et0}

        ndvi_obs_by_date: Dict[str, float] = {}
        if ndvi_ts and isinstance(ndvi_ts, dict):
            for obs in ndvi_ts.get("data", []):
                d = obs.get("date", ""); v = obs.get("ndvi")
                if d and v is not None: ndvi_obs_by_date[d] = v
        if indices_data and isinstance(indices_data, dict):
            today_str = now.strftime("%Y-%m-%d")
            ndvi_cur = indices_data.get("ndvi")
            if ndvi_cur is not None and today_str not in ndvi_obs_by_date:
                ndvi_obs_by_date[today_str] = ndvi_cur

        all_observations: Dict[str, Dict[str, list]] = {}
        for obs_date, ndvi_val in ndvi_obs_by_date.items():
            all_observations[obs_date] = {"plot": [KalmanObservation(obs_type="ndvi", value=ndvi_val, sigma=0.03, reliability=0.9, source="sentinel2")]}

        soil_data = results.get("soil")
        engine = DailyAssimilationEngine()
        engine.add_zone("plot", soil_props=soil_data if soil_data and isinstance(soil_data, dict) else None, start_day=start_str_kf)
        kalman_results = engine.run_period(start_date=start_str_kf, end_date=end_str_kf, daily_weather=daily_weather_kf, all_observations=all_observations)

        NDVI_MAX, NDVI_SOIL, K_EXT = 0.9, 0.15, 0.5
        for day_result in kalman_results:
            day_str = day_result.get("day", "")
            zone_data = day_result.get("zones", {}).get("plot", {})
            state = zone_data.get("state", {}); uncertainty = zone_data.get("uncertainty", {}); provenance = zone_data.get("provenance", {})
            lai = state.get("lai_proxy", 0.2); lai_sigma = uncertainty.get("lai_proxy", 0.5)
            ndvi_est = NDVI_SOIL + (NDVI_MAX - NDVI_SOIL) * (1 - math.exp(-K_EXT * lai))
            dndvi_dlai = (NDVI_MAX - NDVI_SOIL) * K_EXT * math.exp(-K_EXT * lai)
            ndvi_sigma = abs(dndvi_dlai) * lai_sigma
            has_obs = day_str in ndvi_obs_by_date
            ndvi_records.append({
                "date": day_str, "timestamp": day_str, "ndvi": round(ndvi_est, 4), "ndvi_mean": round(ndvi_est, 4),
                "ndvi_sigma": round(ndvi_sigma, 4), "confidence": round(max(0, 1.0 - ndvi_sigma * 2), 3),
                "lai": round(lai, 4), "source": "observed" if has_obs else "kalman",
                "days_since_obs": provenance.get("days_since_obs", 0),
            })
        print(f"[PI] Kalman assimilation: {len(ndvi_records)} daily NDVI, {len(ndvi_obs_by_date)} S2 obs, {sum(1 for r in ndvi_records if r['source']=='observed')} update days")
    except Exception as e:
        print(f"[PI] Kalman NDVI assimilation failed: {e}")
        import traceback; traceback.print_exc()
        if ndvi_ts and isinstance(ndvi_ts, dict):
            for obs in ndvi_ts.get("data", []):
                ndvi_records.append({"date": obs.get("date"), "timestamp": obs.get("date"), "ndvi": obs.get("ndvi"), "ndvi_mean": obs.get("ndvi"), "source": "observed"})

    # Water balance records
    wb_records = []
    if water_data and isinstance(water_data, dict):
        for r in water_data.get("records", []):
            wb_records.append({"date": r.get("date"), "et0": r.get("et0"), "precip": r.get("precip"), "balance": r.get("balance"), "cumulative_deficit": r.get("cumulative_deficit"), "type": r.get("type")})

    # SAR timeline
    sar_timeline = []
    if sar_ts_data and isinstance(sar_ts_data, dict):
        raw_sar_ts = sar_ts_data.get("data") or sar_ts_data.get("timeseries") or []
        for r in raw_sar_ts:
            d = r.get("date") or r.get("timestamp", "")[:10]
            if d:
                sar_timeline.append({"date": d, "timestamp": d, "vv": r.get("vv"), "vh": r.get("vh"), "ratio": r.get("ratio") or r.get("vv_vh_ratio"), "source": r.get("source", "sentinel1")})

    timeline = {
        "weather": hist_records, "forecast": forecast_records, "ndvi": ndvi_records,
        "sar": sar_timeline, "waterBalance": wb_records,
        "dateRange": {
            "from": (now - timedelta(days=days_past)).strftime("%Y-%m-%d"),
            "to": (now + timedelta(days=days_future)).strftime("%Y-%m-%d"),
            "today": now.strftime("%Y-%m-%d"),
        },
    }
    return timeline, ndvi_records, hist_records, forecast_records


def compute_phenology(plant_date: Optional[str], crop_stage_label: Optional[str], ndvi_val: float) -> Optional[Dict]:
    """Compute crop phenology from plant_date + NDVI."""
    now = datetime.now(timezone.utc)
    if plant_date:
        try:
            plant_dt = datetime.strptime(plant_date[:10], "%Y-%m-%d")
            dap = (now.replace(tzinfo=None) - plant_dt).days
            if dap < 15: pheno_stage = "Establishment"
            elif dap < 40: pheno_stage = "Vegetative"
            elif dap < 75: pheno_stage = "Reproductive"
            elif dap < 110: pheno_stage = "Grain Fill"
            else: pheno_stage = "Maturation"
            if ndvi_val > 0.6: pheno_stage = "Reproductive" if dap > 30 else "Vegetative"
            elif ndvi_val < 0.25 and dap > 60: pheno_stage = "Maturation"
            return {"stage": pheno_stage, "dap": dap, "plant_date": plant_date[:10], "basis": "fao_dap_ndvi"}
        except Exception as e:
            print(f"[PI] Phenology computation failed: {e}")
            if crop_stage_label:
                return {"stage": crop_stage_label, "dap": None, "basis": "db_label"}
    elif crop_stage_label:
        return {"stage": crop_stage_label, "dap": None, "basis": "db_label"}
    return None
