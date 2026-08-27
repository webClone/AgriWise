"""
Plot Intelligence Helpers
Extracted from the monolithic api_plot_intelligence endpoint.
Each function is independently fault-tolerant.

Data fetching is now delegated to the DataRequestBroker (Layer 0 Gateway).
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any


def fetch_all_sources(lat: float, lng: float, days_past: int, days_future: int,
                      plot_id: str = "", context: Optional[Dict] = None) -> Dict[str, Any]:
    """Run all L0 data fetches in parallel via the DataRequestBroker.

    This function is the backwards-compatible bridge. Internally it
    delegates to the broker's get_bulk() which handles:
      - Cache-through (hot tier + filesystem fallback)
      - Spatial consolidation (~5km batching)
      - Adaptive TTL
      - Metrics tracking
      - Observation promotion (warm tier)

    No direct imports from eo.* happen here — the broker's FetchRegistry
    is the single place that knows how to reach external APIs.
    """
    from layer0.data_gateway import broker

    now = datetime.now(timezone.utc)
    past_start = (now - timedelta(days=days_past)).strftime("%Y-%m-%d")
    now_str = now.strftime("%Y-%m-%d")

    # Map the old result keys to broker source names
    sources = [
        "openweather_current",
        "openweather_forecast",
        "sentinel2_indices",
        "sentinel1_sar_ts",
        "sentinel1_sar",
        "soilgrids",
        "water_balance",
        "open_meteo_archive",
        "sentinel2_ndvi_ts",
        "open_meteo_agri",
        "nasa_power",
    ]

    extra_args = {
        "sentinel1_sar_ts": {"days": days_past},
        "water_balance": {"days_past": days_past, "days_future": days_future},
        "open_meteo_archive": {"start_date": past_start, "end_date": now_str},
        "sentinel2_ndvi_ts": {"days": days_past + days_future},
    }

    raw = broker.get_bulk(
        sources, plot_id, lat, lng,
        context=context,
        extra_args=extra_args,
    )

    # Map broker source names back to the old pi_helpers result keys
    # so downstream code (build_timeline, etc.) doesn't break
    return {
        "weather":  raw.get("openweather_current"),
        "forecast": raw.get("openweather_forecast"),
        "indices":  raw.get("sentinel2_indices"),
        "sar_ts":   raw.get("sentinel1_sar_ts"),
        "sar":      raw.get("sentinel1_sar"),
        "soil":     raw.get("soilgrids"),
        "water":    raw.get("water_balance"),
        "hist":     raw.get("open_meteo_archive"),
        "ndvi_ts":  raw.get("sentinel2_ndvi_ts"),
        "open_meteo_agri": raw.get("open_meteo_agri"),
        "nasa_power": raw.get("nasa_power"),
    }



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


def build_timeline(results: Dict, lat: float, days_past: int, days_future: int,
                   plant_date: Optional[str] = None,
                   plot_id: Optional[str] = None) -> tuple:
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
                if d and v is not None:
                    try:
                        ndvi_obs_by_date[d] = float(v)
                    except (ValueError, TypeError):
                        pass
        if indices_data and isinstance(indices_data, dict):
            today_str = now.strftime("%Y-%m-%d")
            ndvi_cur = indices_data.get("ndvi")
            if ndvi_cur is not None and today_str not in ndvi_obs_by_date:
                try:
                    ndvi_obs_by_date[today_str] = float(ndvi_cur)
                except (ValueError, TypeError):
                    pass

        all_observations: Dict[str, Dict[str, list]] = {}
        for obs_date, ndvi_val in ndvi_obs_by_date.items():
            all_observations[obs_date] = {"plot": [KalmanObservation(obs_type="ndvi", value=ndvi_val, sigma=0.03, reliability=0.9, source="sentinel2")]}

        soil_data = results.get("soil")

        # ── DNA 4.0: Inject biophysical trait overrides ──────────
        # When cached DNA exists for this plot, replace generic crop params
        # with plot-specific WHC, thermal ceiling, growth rate, and GDD thresholds.
        dna_crop_params = None
        dna_noise_factor = 1.0
        dna_meta = None
        if plot_id:
            try:
                from layer0.calibration.dna_cache import (
                    load_dna_cache, dna_to_crop_params, dna_quality_to_noise_inflation
                )
                dna = load_dna_cache(plot_id)
                if dna:
                    dna_crop_params = dna_to_crop_params(dna)
                    dna_noise_factor = dna_quality_to_noise_inflation(dna)
                    dna_meta = {
                        "source": "cache",
                        "traits": dna.get("traits", {}),
                        "data_quality_pct": dna.get("data_quality", {}).get("weather_null_fill_pct", 0),
                        "noise_inflation": dna_noise_factor,
                    }
                    print(f"[PI] DNA-calibrated Kalman: WHC={dna_crop_params.get('whc_mm_per_m')}mm/m "
                          f"t_max={dna_crop_params.get('t_max')}°C "
                          f"LAI_rate={dna_crop_params.get('lai_growth_rate')} "
                          f"noise_factor={dna_noise_factor:.2f}")
            except Exception as e:
                print(f"[PI] DNA cache lookup failed (non-critical): {e}")

        engine = DailyAssimilationEngine(crop_params=dna_crop_params)
        engine.dna_metadata = dna_meta
        engine.add_zone("plot", soil_props=soil_data if soil_data and isinstance(soil_data, dict) else None, start_day=start_str_kf)

        # Propagate DNA noise factor to process models
        if dna_noise_factor > 1.0:
            for filt in engine.filters.values():
                filt.process_model._dna_noise_factor = dna_noise_factor

        # ── DAP-aware LAI initialization ─────────────────────────
        # If we know the plant date, estimate initial LAI from crop age
        # using a logistic growth prior. This prevents the filter from
        # starting at LAI=0.2 for a crop that's 100 days old.
        if plant_date:
            try:
                plant_dt = datetime.strptime(plant_date[:10], "%Y-%m-%d")
                dap = (start_d.replace(tzinfo=None) - plant_dt).days
                if dap > 0:
                    # Logistic LAI prior: LAI = LAI_max / (1 + exp(-k*(DAP - inflection)))
                    # Inflection at ~50 DAP, LAI_max = 4.0 (prior, not ceiling)
                    lai_prior = 4.0 / (1.0 + math.exp(-0.06 * (dap - 50)))
                    lai_prior = max(0.2, min(4.5, lai_prior))
                    # Set initial state with lower variance (we have DAP info)
                    plot_filter = engine.filters.get("plot")
                    if plot_filter and plot_filter.state:
                        from layer0.state_vector import IDX_LAI
                        plot_filter.state.values[IDX_LAI] = lai_prior
                        plot_filter.state.variance[IDX_LAI] = 0.3  # Lower than default 0.5
                        plot_filter.covariance.P[IDX_LAI][IDX_LAI] = 0.3
                        print(f"[PI] Kalman DAP-aware init: DAP={dap}, LAI_prior={lai_prior:.2f}")
            except Exception as e:
                print(f"[PI] DAP-aware init failed (non-critical): {e}")

        kalman_results = engine.run_period(start_date=start_str_kf, end_date=end_str_kf, daily_weather=daily_weather_kf, all_observations=all_observations)

        # ── Extract ML recalibration state ───────────────────────
        plot_filter = engine.filters.get("plot")
        adaptive_rate = None
        recal_count = 0
        if plot_filter:
            adaptive_rate = getattr(plot_filter, '_adaptive_lai_rate', None)
            recal_count = getattr(plot_filter, '_recalibration_count', 0)
            if adaptive_rate:
                print(f"[PI] Kalman ML recalibrated: rate={adaptive_rate:.4f} "
                      f"(after {recal_count} S2 obs, "
                      f"EMA_error={getattr(plot_filter, '_ema_error', 0):.4f})")

        NDVI_MAX, NDVI_SOIL, K_EXT = 0.9, 0.15, 0.5

        # ── FIX: Track last observation-corrected LAI for forecast floor ──
        # When the Kalman filter propagates forward without observations,
        # the LAI can collapse because:
        #   1. GDD accumulation from 7 days ago doesn't reach vegetative threshold
        #   2. Process noise inflates uncertainty, pulling LAI toward prior (0.2)
        # This creates the physically impossible scenario of NDVI going from
        # 0.89 to 0.15 in one day. Fix: hold forward the last observed LAI
        # with a gentle daily decay (max 1.5%/day = natural leaf turnover).
        last_obs_lai = 0.2  # Initial fallback
        last_obs_day_str = None

        # First pass: find the last observation-corrected LAI
        today_str_kf = now.strftime("%Y-%m-%d")
        for day_result in kalman_results:
            day_str = day_result.get("day", "")
            if day_str in ndvi_obs_by_date:
                zone_data = day_result.get("zones", {}).get("plot", {})
                state = zone_data.get("state", {})
                last_obs_lai = max(last_obs_lai, state.get("lai_proxy", 0.2))
                last_obs_day_str = day_str

        for day_result in kalman_results:
            day_str = day_result.get("day", "")
            zone_data = day_result.get("zones", {}).get("plot", {})
            state = zone_data.get("state", {}); uncertainty = zone_data.get("uncertainty", {}); provenance = zone_data.get("provenance", {})
            lai = state.get("lai_proxy", 0.2); lai_sigma = uncertainty.get("lai_proxy", 0.5)
            has_obs = day_str in ndvi_obs_by_date
            days_since = provenance.get("days_since_obs", 0)

            # ── FIX: Apply LAI floor for forecast days ────────────
            # If we're past the last observation and the model LAI has
            # collapsed below the last corrected value, use the floor.
            # Allow gentle decay: 1.5% per day (typical leaf turnover rate)
            # unless phenology stage indicates senescence.
            if not has_obs and last_obs_day_str and day_str > last_obs_day_str:
                # Compute days since last observation
                try:
                    d_last = datetime.strptime(last_obs_day_str, "%Y-%m-%d")
                    d_curr = datetime.strptime(day_str, "%Y-%m-%d")
                    gap_days = (d_curr - d_last).days
                except Exception:
                    gap_days = days_since

                # Decay floor: last_obs_lai × (1 - 0.015)^gap_days
                # At 1.5%/day: after 7 days, floor = 90% of observed
                # This is generous — real crops don't lose 10% LAI in a week
                # unless stressed/harvested
                lai_floor = last_obs_lai * (0.985 ** gap_days)

                if lai < lai_floor:
                    lai = lai_floor
                    # Also reduce sigma: we're using a strong prior
                    lai_sigma = min(lai_sigma, 0.3 + gap_days * 0.02)

            ndvi_est = NDVI_SOIL + (NDVI_MAX - NDVI_SOIL) * (1 - math.exp(-K_EXT * lai))
            dndvi_dlai = (NDVI_MAX - NDVI_SOIL) * K_EXT * math.exp(-K_EXT * lai)
            ndvi_sigma = abs(dndvi_dlai) * lai_sigma

            # ── Fixed confidence formula ─────────────────────────
            # Old: confidence = 1 - ndvi_sigma*2 (hid LAI uncertainty at high LAI)
            # New: combines NDVI uncertainty, LAI uncertainty, and gap penalty
            ndvi_conf = max(0, 1.0 - ndvi_sigma * 2)
            lai_conf = max(0, 1.0 - lai_sigma * 0.5)  # LAI sigma matters too
            gap_penalty = max(0.4, 1.0 - days_since * 0.06)  # -6% per gap day, floor 40%
            if has_obs:
                confidence = ndvi_conf * 0.95  # Direct observation is high confidence
            else:
                confidence = min(ndvi_conf, lai_conf) * gap_penalty

            ndvi_records.append({
                "date": day_str, "timestamp": day_str, "ndvi": round(ndvi_est, 4), "ndvi_mean": round(ndvi_est, 4),
                "ndvi_sigma": round(ndvi_sigma, 4), "confidence": round(max(0, confidence), 3),
                "lai": round(lai, 4), "lai_sigma": round(lai_sigma, 4),
                "source": "observed" if has_obs else "kalman",
                "days_since_obs": days_since,
                "adaptive_rate": round(adaptive_rate, 5) if adaptive_rate else None,
                "recalibrations": recal_count,
            })
        print(f"[PI] Kalman assimilation: {len(ndvi_records)} daily NDVI, {len(ndvi_obs_by_date)} S2 obs, {sum(1 for r in ndvi_records if r['source']=='observed')} update days")
    except Exception as e:
        print(f"[PI] Kalman NDVI assimilation failed: {e}")
        import traceback; traceback.print_exc()
        if ndvi_ts and isinstance(ndvi_ts, dict):
            for obs in ndvi_ts.get("data", []):
                v_raw = obs.get("ndvi")
                try:
                    v_val = float(v_raw) if v_raw is not None else None
                except (ValueError, TypeError):
                    v_val = None
                ndvi_records.append({"date": obs.get("date"), "timestamp": obs.get("date"), "ndvi": v_val, "ndvi_mean": v_val, "source": "observed"})

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


def compute_phenology(plant_date: Optional[str], crop_administrative_status: Optional[str], ndvi_val: float) -> Optional[Dict]:
    """Return administrative context without inventing biological phenology.

    Layer 2 owns phenology inference.  This compatibility helper deliberately
    ignores NDVI and never converts CropStatus or days-after-planting into a
    replacement stage.
    """
    del ndvi_val
    if not plant_date and not crop_administrative_status:
        return None
    return {
        "stage": "UNKNOWN",
        "dap": None,
        "plant_date": plant_date[:10] if plant_date else None,
        "administrative_status": crop_administrative_status,
        "basis": "layer2_phenology_required",
        "scientific_authority": False,
    }
