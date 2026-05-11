
from typing import Optional
from layer1_fusion.schema import FieldTensor

from orchestrator_v2.schema import OrchestratorInput

# New Layer 1 Fusion Engine (V1 deterministic context engine)
from layer1_fusion.engine import Layer1FusionEngine
from layer1_fusion.schemas import Layer1InputBundle, Layer1ContextPackage
from layer1_fusion.outputs.legacy_compat import build_legacy_fieldtensor

from datetime import datetime, timezone


# Singleton V1 engine
_v1_engine = Layer1FusionEngine()


def run_layer1_fusion(inputs: OrchestratorInput) -> FieldTensor:
    """
    Standard Entry Point for Layer 1.

    Temporarily reverted to run_layer1_fusion_legacy to restore full
    plot_timeseries array and Layer 0 Kalman assimilation data.
    """
    return run_layer1_fusion_legacy(inputs)


def run_layer1_fusion_legacy(inputs: OrchestratorInput) -> FieldTensor:
    """
    DEPRECATED Legacy Entry Point for Layer 1 (pre-V1 data_fusion path).

    Retained only for emergency fallback. Should NOT be used in production.
    """
    from layer1_fusion.data_fusion import fusion_engine  # lazy import

    plot_id = inputs.plot_id
    lat = float(inputs.operational_context.get("lat", 0.0))
    lng = float(inputs.operational_context.get("lng", 0.0))
    polygon_coords = inputs.operational_context.get("polygon_coords")
    start_date = inputs.date_range.get("start", "")
    end_date = inputs.date_range.get("end", "")
    user_evidence = inputs.operational_context.get("user_evidence", [])

    output = fusion_engine.fuse_data(
        plot_id=plot_id,
        lat=lat,
        lng=lng,
        start_date=start_date,
        end_date=end_date,
        polygon_coords=polygon_coords,
        user_evidence=user_evidence
    )

    tensor = output.tensor
    if output.raster_composites:
        tensor.raster_composites = output.raster_composites
    if output.observation_products:
        tensor.observation_products = output.observation_products

    # ── Inject IoT sensor data into FieldTensor ─────────────────────────
    # Sensor data arrives from Next.js route as operational_context.sensors
    # (array of per-device objects) and sensor_summary (flat averages).
    # We inject into tensor.static for L3 feature access and tensor.maps
    # for L10 spatial engine (water.py v3) to consume.
    _inject_sensor_data(tensor, inputs)

    # ── Populate forecast_7d from real Open-Meteo API (GAP 3 fix) ───────
    # Prefer real 7-day forecast over persistence model so L7/L8 see
    # actual precipitation events, not smoothed seasonal averages.
    if not tensor.forecast_7d:
        real_forecast = _fetch_real_forecast(lat, lng)
        if real_forecast:
            tensor.forecast_7d = real_forecast
        elif tensor.plot_timeseries:
            # Fallback: persistence model if network unavailable
            tensor.forecast_7d = _build_persistence_forecast(
                tensor.plot_timeseries, end_date
            )

    return tensor


def _inject_sensor_data(tensor: FieldTensor, inputs: OrchestratorInput) -> None:
    """
    Inject IoT sensor readings from operational_context into the FieldTensor.

    This bridges the gap between the Next.js sensor ingestion (Prisma DB)
    and the AgriBrain pipeline. Injected data flows to:
      - tensor.static['iot_sensors'] → L3 feature builder reads static dict
      - tensor.static['sensor_summary'] → backward-compat flat dict
      - tensor.maps['soil_moisture'] → L10 water.py v3 reads via L1 adapter
    """
    op_ctx = inputs.operational_context
    sensors = op_ctx.get("sensors", [])
    sensor_summary = op_ctx.get("sensor_summary", {})

    if not sensors and not sensor_summary:
        return

    # 1. Inject per-sensor array into tensor.static for L3 feature extraction
    if isinstance(sensors, list) and sensors:
        tensor.static['iot_sensors'] = sensors
        sensor_count = len(sensors)
        moisture_vals = []
        temp_vals = []
        humidity_vals = []
        ec_vals = []

        for s in sensors:
            if not isinstance(s, dict):
                continue
            sm = s.get("soilMoisture") or s.get("soil_moisture")
            if sm is not None:
                moisture_vals.append(float(sm))
            t = s.get("temperature")
            if t is not None:
                temp_vals.append(float(t))
            h = s.get("humidity")
            if h is not None:
                humidity_vals.append(float(h))
            ec = s.get("ec")
            if ec is not None:
                ec_vals.append(float(ec))

        # Build sensor summary if not already provided
        if not sensor_summary:
            sensor_summary = {}
        if moisture_vals:
            sensor_summary['soil_moisture'] = sum(moisture_vals) / len(moisture_vals)
            sensor_summary['soil_moisture_min'] = min(moisture_vals)
            sensor_summary['soil_moisture_max'] = max(moisture_vals)
            sensor_summary['soil_moisture_count'] = len(moisture_vals)
        if temp_vals:
            sensor_summary['temperature'] = sum(temp_vals) / len(temp_vals)
        if humidity_vals:
            sensor_summary['humidity'] = sum(humidity_vals) / len(humidity_vals)
        if ec_vals:
            sensor_summary['ec'] = sum(ec_vals) / len(ec_vals)

        print(f"[IoT] Injected {sensor_count} sensors into FieldTensor "
              f"(moisture: {len(moisture_vals)}, temp: {len(temp_vals)}, "
              f"ec: {len(ec_vals)})")

    # 2. Inject flat summary for backward compatibility
    if sensor_summary:
        tensor.static['sensor_summary'] = sensor_summary

    # 3. Inject soil moisture as a raster map entry for L10 spatial engine
    # L10 L1 adapter reads tensor.maps → raster_maps, so the water.py v3
    # engine can pick up 'soil_moisture' as a real moisture source.
    sm_value = sensor_summary.get('soil_moisture')
    if sm_value is not None:
        # Convert percentage (0-100) to fraction (0-1) for consistency
        sm_fraction = sm_value / 100.0 if sm_value > 1.0 else sm_value
        
        # Build a uniform raster (IoT is point-level, broadcast to field)
        # If multiple sensors exist with spatial info, this could be interpolated
        # but for now we broadcast the average to all pixels
        gs = getattr(tensor, 'grid_spec', None)
        h = getattr(gs, 'height', 10) if gs else 10
        w = getattr(gs, 'width', 10) if gs else 10

        # Add slight spatial variation around sensor mean for visual interest
        # Use deterministic noise based on grid position
        import hashlib
        seed_str = f"{inputs.plot_id}_{sm_fraction:.4f}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16) % 10000

        moisture_raster = []
        for r in range(h):
            row = []
            for c in range(w):
                # Deterministic micro-variation: ±5% around the sensor mean
                noise_seed = (seed + r * 131 + c * 97) % 10000
                noise = (noise_seed / 10000.0 - 0.5) * 0.10  # ±5%
                pixel_val = max(0.0, min(1.0, sm_fraction + noise))
                row.append(round(pixel_val, 4))
            moisture_raster.append(row)

        if not hasattr(tensor, 'maps') or tensor.maps is None:
            tensor.maps = {}
        tensor.maps['soil_moisture'] = moisture_raster
        print(f"[IoT] Injected soil_moisture raster ({h}x{w}) into tensor.maps "
              f"(mean={sm_fraction:.3f})")


def _fetch_real_forecast(lat: float, lng: float) -> list:
    """Fetch real 7-day Open-Meteo forecast and normalise to L1 forecast_7d format.

    Returns list of dicts with keys: date, temp_max, temp_min, precipitation,
    et0, rain_prob, source.  Returns [] on any failure so caller can fall back.
    """
    try:
        import requests
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lng,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "et0_fao_evapotranspiration",
            ],
            "timezone": "auto",
            "forecast_days": 7,
        }
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code != 200:
            return []
        data = resp.json()
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        if not dates:
            return []

        result = []
        for i, date_str in enumerate(dates[:7]):
            tmax = daily.get("temperature_2m_max", [None])[i]
            tmin = daily.get("temperature_2m_min", [None])[i]
            precip = daily.get("precipitation_sum", [0.0])[i] or 0.0
            rain_prob = (daily.get("precipitation_probability_max", [0])[i] or 0) / 100.0
            et0 = daily.get("et0_fao_evapotranspiration", [4.0])[i] or 4.0
            result.append({
                "date": date_str,
                "temp_max": float(tmax) if tmax is not None else 25.0,
                "temp_min": float(tmin) if tmin is not None else 12.0,
                "precipitation": float(precip),
                "et0": float(et0),
                "rain_prob": round(float(rain_prob), 2),
                "source": "open-meteo-forecast",
            })
        return result
    except Exception:
        return []


def _build_persistence_forecast(
    timeseries: list, end_date_str: str
) -> list:
    """Build a 7-day persistence forecast from recent timeseries.

    Strategy: average the last 7 days of weather, then project forward
    with slight regression toward seasonal means (prevents extremes
    from persisting indefinitely).

    Returns list of 7 forecast dicts with keys:
        date, temp_max, temp_min, precipitation, et0, rain_prob
    """
    from datetime import datetime, timedelta

    if not timeseries:
        return []

    # Collect recent weather from last 7 entries
    recent = timeseries[-7:] if len(timeseries) >= 7 else timeseries
    recent_dicts = [e for e in recent if isinstance(e, dict)]
    if not recent_dicts:
        return []

    # Compute averages from recent window
    def _avg(key, fallback):
        vals = [float(d[key]) for d in recent_dicts
                if d.get(key) is not None]
        return sum(vals) / len(vals) if vals else fallback

    avg_tmax = _avg("temp_max", _avg("tmax", 25.0))
    avg_tmin = _avg("temp_min", _avg("tmin", 12.0))
    avg_precip = _avg("precipitation", _avg("rain", 2.0))
    avg_et0 = _avg("et0", _avg("ET0", 4.0))

    # Seasonal means for regression (mild temperate defaults)
    seasonal_tmax = 22.0
    seasonal_tmin = 10.0
    seasonal_precip = 2.5
    seasonal_et0 = 3.5

    # Regression factor: 20% per day toward seasonal mean
    alpha = 0.2

    # Parse end date for date generation
    try:
        base_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        base_date = datetime.now()

    forecast = []
    for day_offset in range(1, 8):
        frac = alpha * day_offset
        frac = min(frac, 1.0)

        f_tmax = avg_tmax + (seasonal_tmax - avg_tmax) * frac
        f_tmin = avg_tmin + (seasonal_tmin - avg_tmin) * frac
        f_precip = max(0.0, avg_precip + (seasonal_precip - avg_precip) * frac)
        f_et0 = max(0.5, avg_et0 + (seasonal_et0 - avg_et0) * frac)

        # Rain probability from precipitation amount
        rain_prob = min(1.0, f_precip / 10.0) if f_precip > 0.5 else 0.1

        forecast_date = base_date + timedelta(days=day_offset)
        forecast.append({
            "date": forecast_date.strftime("%Y-%m-%d"),
            "temp_max": round(f_tmax, 1),
            "temp_min": round(f_tmin, 1),
            "precipitation": round(f_precip, 1),
            "et0": round(f_et0, 2),
            "rain_prob": round(rain_prob, 2),
            "source": "persistence_forecast",
        })

    return forecast


def run_layer1_fusion_v1(
    inputs: OrchestratorInput,
    layer0_packages: Optional[dict] = None,
    run_id: Optional[str] = None,
    run_timestamp: Optional[datetime] = None,
) -> Layer1ContextPackage:
    """
    V1 Entry Point for the deterministic Layer 1 Fusion Context Engine.

    This is the PREFERRED path. Legacy run_layer1_fusion() exists only
    for backward compatibility during migration. New orchestrator code
    should call this directly.

    Returns Layer1ContextPackage — the new canonical output.

    Args:
        inputs: OrchestratorInput from the V2 orchestrator.
        layer0_packages: Optional dict of pre-fetched Layer 0 packages.
            Keys: sentinel2_packages, sentinel1_packages, environment_package,
                  geo_context_package, sensor_context_package, etc.
        run_id: Explicit run ID for deterministic replay. If None, auto-generated.
        run_timestamp: Explicit timestamp for deterministic replay. If None, uses UTC now.
    """
    ts = run_timestamp or datetime.now(timezone.utc)
    rid = run_id or f"l1_run_{inputs.plot_id}_{ts.strftime('%Y%m%d%H%M%S')}"
    l0 = layer0_packages or {}

    bundle = Layer1InputBundle(
        plot_id=inputs.plot_id,
        run_id=rid,
        run_timestamp=ts,
        window_start=_parse_date(inputs.date_range.get("start", ""), ts),
        window_end=_parse_date(inputs.date_range.get("end", ""), ts),
        layer0_state_package=l0.get("layer0_state_package"),
        sentinel2_packages=l0.get("sentinel2_packages", []),
        sentinel1_packages=l0.get("sentinel1_packages", []),
        environment_package=l0.get("environment_package"),
        weather_forecast_package=l0.get("weather_forecast_package"),
        geo_context_package=l0.get("geo_context_package"),
        sensor_context_package=l0.get("sensor_context_package"),
        perception_packages=l0.get("perception_packages", []),
        user_events=l0.get("user_events", []),
        historical_layer1_package=l0.get("historical_layer1_package"),
        # Previously missing — these sources were silently dropped
        sentinel5p_packages=l0.get("sentinel5p_packages", []),
        drone_structural_packages=l0.get("drone_structural_packages", []),
        user_input_package=l0.get("user_input_package"),
        raster_composites=l0.get("raster_composites", {}),
        eo_model_path=l0.get("eo_model_path"),
    )

    return _v1_engine.fuse(bundle)


def _parse_date(date_str: str, fallback: datetime) -> datetime:
    """Parse date string to datetime.

    Falls back to the provided timestamp (not datetime.now) so that
    deterministic replay with explicit run_timestamp stays deterministic.
    """
    if not date_str:
        return fallback
    try:
        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return fallback
