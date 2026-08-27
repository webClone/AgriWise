
from typing import Optional, Any
from layer1_fusion.schema import FieldTensor

from orchestrator_v2.schema import OrchestratorInput

# New Layer 1 Fusion Engine (V1 deterministic context engine)
from layer1_fusion.engine import Layer1FusionEngine
from layer1_fusion.schemas import Layer1InputBundle, Layer1ContextPackage
from layer1_fusion.outputs.legacy_compat import build_legacy_fieldtensor

from datetime import datetime, timezone


# Included in Gateway request kwargs so StorageManager's param hash changes
# whenever the raster response contract changes.  BC.10.20R2 must not reuse
# cached composites that predate CRS/bounds/affine preservation.
RASTER_GATEWAY_CONTRACT_VERSION = "bc10_24r5_provider_truth_v2"


def is_production() -> bool:
    import os
    env_vars = ["AGRIWISE_PRODUCTION", "AGRIWISE_ENV", "ENV", "ENVIRONMENT"]
    for var in env_vars:
        val = os.getenv(var, "").lower()
        if val in ("true", "production"):
            return True
    return False


# Singleton V1 engine
_v1_engine = Layer1FusionEngine()


def run_layer1_fusion(
    inputs: OrchestratorInput,
    layer0_output: Optional[Any] = None,
    raster_composites: Optional[dict] = None,
    asmae_output: Optional[dict] = None,
    asmae_run_record: Optional[dict] = None,
) -> FieldTensor:
    """
    Standard Entry Point for Layer 1.

    If layer0_output is provided, routes through the modern V1 path,
    building a legacy-compatible FieldTensor from the V1 context package.
    Otherwise, runs the legacy fallback.
    """
    import sys
    import time as _time

    _t0 = _time.perf_counter()

    if is_production() and layer0_output is None:
        raise RuntimeError("Legacy Layer 1 fallback is disabled in production")

    if layer0_output is not None:
        try:
            # 1. Run V1 from canonical L0 packages
            l0_packages = {
                "layer0_state_package": layer0_output.layer0_state_package,
                "layer0_source_packages": layer0_output.layer0_source_packages,
                "user_events": (inputs.operational_context or {}).get("user_evidence", []),
                "raster_composites": raster_composites or {},
                "asmae_output": asmae_output,
                "asmae_run_record": asmae_run_record,
            }

            pkg = run_layer1_fusion_v1(
                inputs,
                layer0_packages=l0_packages,
                asmae_output=asmae_output,
                asmae_run_record=asmae_run_record,
            )

            # 2. Build legacy-compatible FieldTensor from V1 context
            tensor = build_legacy_fieldtensor(pkg)
            tensor._context_package = pkg

            if hasattr(tensor, 'provenance') and isinstance(tensor.provenance, dict):
                tensor.provenance["v1_active"] = True
                tensor.provenance["v1_evidence_count"] = len(pkg.evidence_items) if pkg.evidence_items else 0
                tensor.provenance["v1_conflict_count"] = len(pkg.conflicts)
                tensor.provenance["v1_gap_count"] = len(pkg.gaps)
                tensor.provenance["v1_engine_version"] = pkg.provenance.engine_version
                tensor.provenance["v1_data_health"] = pkg.diagnostics.data_health.status

            _total = _time.perf_counter() - _t0
            print(f"[L1] Modern path run complete: {_total:.2f}s", file=sys.stderr, flush=True)
            return tensor

        except Exception as e:
            import traceback
            print(f"[L1] Modern path failed: {e}. Falling back to legacy.", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            if is_production():
                raise RuntimeError(f"Modern path failed in production: {e}") from e

    # Legacy fallback path
    tensor = run_layer1_fusion_legacy(inputs)
    _total = _time.perf_counter() - _t0
    print(f"[L1] Legacy fallback complete: {_total:.2f}s", file=sys.stderr, flush=True)
    return tensor


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

    # ── Inject drone structural spatial maps into FieldTensor ────────────
    # When drone missions complete, structural analysis produces spatial
    # maps (canopy cover, weed pressure, row gaps). These are injected
    # into tensor.maps so L10 surfaces can visualize them.
    _inject_drone_spatial_maps(tensor, inputs)

    # ── Populate forecast_7d from real Open-Meteo API (GAP 3 fix) ───────
    # Prefer real 7-day forecast over persistence model so L7/L8 see
    # actual precipitation events, not smoothed seasonal averages.
    if not tensor.forecast_7d:
        real_forecast = _fetch_real_forecast(lat, lng, plot_id=plot_id)
        if real_forecast:
            tensor.forecast_7d = real_forecast
        elif tensor.plot_timeseries:
            # Fallback: persistence model if network unavailable
            tensor.forecast_7d = _build_persistence_forecast(
                tensor.plot_timeseries, end_date, lat_deg=lat
            )

    if not is_production():
        if not hasattr(tensor, 'provenance') or tensor.provenance is None:
            tensor.provenance = {}
        tensor.provenance["legacy_fallback_used"] = True
        tensor.provenance["confidence_ceiling"] = 0.35
        tensor.provenance["diagnostic_only_spatial_outputs"] = True

    return tensor


def _inject_drone_spatial_maps(tensor: FieldTensor, inputs: OrchestratorInput) -> None:
    """Inject drone structural spatial maps into FieldTensor.maps.

    When a drone mission has completed, the DroneRGBEngine produces
    spatial_maps (dict of variable → 2D grid). If present in
    operational_context.drone_structural, we inject them into
    tensor.maps with 'drone_' prefix so L10 L1 adapter picks them up.

    Expected keys in drone_structural.spatial_maps:
      - canopy_cover → drone_canopy_cover
      - weed_pressure → drone_weed_pressure
      - row_gaps → drone_row_gaps
    """
    op_ctx = inputs.operational_context
    drone_data = op_ctx.get("drone_structural")
    if not drone_data or not isinstance(drone_data, dict):
        return

    spatial_maps = drone_data.get("spatial_maps", {})
    if not spatial_maps:
        return

    if not hasattr(tensor, 'maps') or tensor.maps is None:
        tensor.maps = {}

    gs = getattr(tensor, 'grid_spec', None)
    tensor_h = getattr(gs, 'height', 10) if gs else 10
    tensor_w = getattr(gs, 'width', 10) if gs else 10

    injected = 0
    for var_name, raster in spatial_maps.items():
        if not isinstance(raster, list) or not raster:
            continue

        map_key = f"drone_{var_name}" if not var_name.startswith("drone_") else var_name
        src_h = len(raster)
        src_w = len(raster[0]) if raster[0] else 0

        # Resample to tensor grid if dimensions differ
        if src_h == tensor_h and src_w == tensor_w:
            tensor.maps[map_key] = raster
        else:
            resampled = [[None] * tensor_w for _ in range(tensor_h)]
            for r in range(tensor_h):
                for c in range(tensor_w):
                    src_r = int(r * src_h / tensor_h)
                    src_c = int(c * src_w / tensor_w)
                    try:
                        resampled[r][c] = raster[src_r][src_c]
                    except (IndexError, TypeError):
                        pass
            tensor.maps[map_key] = resampled
        injected += 1

    if injected:
        print(f"[Drone] Injected {injected} spatial maps into tensor.maps: "
              f"{[k for k in tensor.maps if k.startswith('drone_')]}")




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
        if not hasattr(tensor, 'map_metadata') or tensor.map_metadata is None:
            tensor.map_metadata = {}
        tensor.map_metadata['soil_moisture'] = {
            "observed_spatial_surface": False,
            "visual_only": True,
            "state_update_allowed": False,
            "diagnostic_only": True,
            "source": "point_sensor_visual_proxy"
        }
        print(f"[IoT] Injected soil_moisture raster ({h}x{w}) into tensor.maps "
              f"(mean={sm_fraction:.3f})")


def _fetch_real_forecast(lat: float, lng: float, plot_id: str = "") -> list:
    """Fetch real 7-day Open-Meteo forecast and normalise to L1 forecast_7d format.

    Returns list of dicts with keys: date, temp_max, temp_min, precipitation,
    et0, rain_prob, source.  Returns [] on any failure so caller can fall back.
    """
    try:
        from layer0.data_gateway import broker
        data = broker.get("openweather_forecast", plot_id=plot_id, lat=lat, lng=lng)
        if not data or not isinstance(data, dict):
            return []
        forecast_list = data.get("forecast", [])
        if not forecast_list:
            return []
        result = []
        for item in forecast_list:
            def numeric(name):
                value = item.get(name)
                return float(value) if isinstance(value, (int, float)) else None

            temp_max = numeric("temp_max")
            temp_min = numeric("temp_min")
            precipitation = numeric("precipitation")
            if temp_max is None or temp_min is None or precipitation is None:
                continue
            result.append({
                "date": item.get("date"),
                "temp_max": temp_max,
                "temp_min": temp_min,
                "precipitation": precipitation,
                "et0": numeric("et0"),
                "rain_prob": round(numeric("pop"), 2) if numeric("pop") is not None else None,
                "source": "open-meteo-forecast",
            })
        return result
    except Exception:
        return []


def _build_persistence_forecast(
    timeseries: list, end_date_str: str, lat_deg: float = 35.0
) -> list:
    """Build a 7-day persistence forecast from recent timeseries.

    Strategy: average the last 7 days of weather, then project forward
    with slight regression toward seasonal means (prevents extremes
    from persisting indefinitely).

    INT-6: Seasonal means are now latitude-dependent instead of hardcoded
    temperate European defaults. This prevents arid-zone forecasts from
    being pulled toward cool/wet European averages.

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
    def _avg(key):
        vals = [float(d[key]) for d in recent_dicts
                if isinstance(d.get(key), (int, float))]
        return sum(vals) / len(vals) if vals else None

    avg_tmax = _avg("temp_max")
    if avg_tmax is None:
        avg_tmax = _avg("tmax")
    avg_tmin = _avg("temp_min")
    if avg_tmin is None:
        avg_tmin = _avg("tmin")
    avg_precip = _avg("precipitation")
    if avg_precip is None:
        avg_precip = _avg("rain")
    avg_et0 = _avg("et0")
    if avg_et0 is None:
        avg_et0 = _avg("ET0")
    if any(value is None for value in (avg_tmax, avg_tmin, avg_precip, avg_et0)):
        return []

    # ── INT-6: Location-dependent seasonal means ──────────────────────
    # Latitude-based climate zone classification:
    #   Tropical (0-15°): hot, wet year-round
    #   Arid/MENA (15-35°): very hot, very dry
    #   Mediterranean (35-45°): warm, moderate
    #   Temperate (45-60°): mild, moderate precip
    #   Boreal (60+°): cool, moderate precip
    #
    # These are approximate annual means for the regression target.
    # The forecast regresses toward these values at 20%/day.
    abs_lat = abs(lat_deg) if lat_deg is not None else 35.0

    if abs_lat < 15.0:
        # Tropical
        seasonal_tmax = 32.0
        seasonal_tmin = 22.0
        seasonal_precip = 5.0
        seasonal_et0 = 5.0
    elif abs_lat < 30.0:
        # Arid subtropical / deep MENA (Egypt, S. Iraq, Arabian Peninsula fringe)
        seasonal_tmax = 38.0
        seasonal_tmin = 22.0
        seasonal_precip = 0.5
        seasonal_et0 = 6.5
    elif abs_lat < 35.0:
        # Semi-arid MENA / Levant / Maghreb (N. Iraq, Jordan, Tunisia, Iran)
        seasonal_tmax = 36.0
        seasonal_tmin = 19.0
        seasonal_precip = 1.0
        seasonal_et0 = 5.5
    elif abs_lat < 45.0:
        # Mediterranean / warm temperate
        seasonal_tmax = 26.0
        seasonal_tmin = 13.0
        seasonal_precip = 2.0
        seasonal_et0 = 4.0
    elif abs_lat < 55.0:
        # Temperate (Western Europe, N. America)
        seasonal_tmax = 22.0
        seasonal_tmin = 10.0
        seasonal_precip = 2.5
        seasonal_et0 = 3.5
    else:
        # Boreal / high-latitude
        seasonal_tmax = 16.0
        seasonal_tmin = 4.0
        seasonal_precip = 2.0
        seasonal_et0 = 2.5

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
    asmae_output: Optional[dict] = None,
    asmae_run_record: Optional[dict] = None,
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
        run_id: Explicit run ID for replay. If None, auto-generated.
        run_timestamp: Explicit timestamp for replay. If None, uses UTC now.
        asmae_output: Optional dictionary containing ASMAE engine output.
        asmae_run_record: Optional dictionary containing ASMAE run status/meta.
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
        # Preserve the authoritative plot footprint independently of raster
        # bounds.  Raster bounds describe the rectangular grid extent; they
        # are not a substitute for a non-rectangular field boundary.
        plot_geometry=(inputs.operational_context or {}).get("polygon_coords"),
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
        # V61F: Pass canonical Layer 0 source packages through to the engine.
        # Without this, Layer0RunnerOutput.to_layer1_bundle_kwargs() packages
        # were silently dropped and the engine never received them.
        layer0_source_packages=l0.get("layer0_source_packages", {}),
        # V92.4-BC.6: Thread typed ASMAE output and run record
        asmae_output=asmae_output if asmae_output is not None else l0.get("asmae_output"),
        asmae_run_record=asmae_run_record if asmae_run_record is not None else l0.get("asmae_run_record"),
    )

    pkg = _v1_engine.fuse(bundle)
    pkg.asmae_run_record = bundle.asmae_run_record
    pkg.asmae_output = bundle.asmae_output
    return pkg


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


def _fetch_raster_composites_for_v1(
    plot_id: str = "", lat: float = 0.0, lng: float = 0.0,
    start_date: str = "", end_date: str = "",
    polygon_coords: any = None,
) -> dict:
    """Fetch raster composites for V1 engine.

    Legacy data_fusion.py fetches these internally (lines 240-290).
    V1 engine expects them as bundle.raster_composites, so we fetch
    them here before engine invocation.

    Uses concurrent ThreadPoolExecutor (same as legacy) for performance.
    Returns empty dict on any failure so V1 engine still runs.
    """
    import sys

    # Support callers that pass lat as the first positional argument
    if isinstance(plot_id, float):
        # Shift arguments: plot_id was actually lat, lat was lng, lng was start_date, etc.
        polygon_coords = end_date
        end_date = start_date
        start_date = lng
        lng = lat
        lat = plot_id
        plot_id = ""

    if not polygon_coords and (not lat or not lng):
        return {}

    try:
        from layer0.data_gateway import broker

        # Use broker.get_bulk for parallel raster composite fetch
        raster_sources = [
            "raster_composite_ndvi",
            "raster_composite_ndmi",
            "raster_composite_sar",
            "raster_quality_mask",
        ]

        extra_args = {
            src: {
                "start_date": start_date,
                "end_date": end_date,
                "polygon_coords": polygon_coords,
                "raster_contract_version": RASTER_GATEWAY_CONTRACT_VERSION,
            }
            for src in raster_sources
        }

        raw = broker.get_bulk(
            raster_sources, plot_id, lat, lng,
            extra_args=extra_args,
        )

        # Map broker source names to the old composites keys
        source_to_key = {
            "raster_composite_ndvi": "NDVI",
            "raster_composite_ndmi": "NDMI",
            "raster_composite_sar": "SAR",
            "raster_quality_mask": "QUALITY",
        }
        composites = {}
        for src, key in source_to_key.items():
            result = raw.get(src)
            if result:
                composites[key] = result
                vpc = result.get("valid_pixel_count", 0)
                dims = f"{result.get('height', '?')}x{result.get('width', '?')}"
                print(f"[L1-V1] [Raster] {key}: dims={dims}, valid_pixels={vpc}",
                      file=sys.stderr, flush=True)

        print(f"[L1-V1] [Raster] Fetched {len(composites)} composites via Gateway: "
              f"{list(composites.keys())}", file=sys.stderr, flush=True)
        return composites

    except ImportError:
        print("[L1-V1] [Raster] Data Gateway not available, skipping raster fetch",
              file=sys.stderr, flush=True)
        return {}
    except Exception as e:
        print(f"[L1-V1] [Raster] Fetch failed: {e}",
              file=sys.stderr, flush=True)
        return {}
