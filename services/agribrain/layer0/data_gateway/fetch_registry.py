"""
Fetch Registry — Maps source names to lazy-loaded fetch functions.

This is the ONLY file that imports from `eo.*` and `layer0.sentinel5p.*`.
No other module in the gateway (or any other layer) should import
fetch functions directly.

Each registry entry maps a source name (matching TTL_REGISTRY keys)
to a callable: (lat, lng, *args, **kwargs) -> dict | None

Usage:
    from layer0.data_gateway.fetch_registry import get_fetch_fn, FETCH_REGISTRY

    fn = get_fetch_fn("soilgrids")
    data = fn(33.5, -7.6)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("agribrain.gateway.fetch_registry")

# ── Lazy import wrappers ───────────────────────────────────────────────
#
# We use functions that import on first call to avoid loading heavy
# EO modules at startup. Each wrapper has the same signature as the
# underlying fetch function.

def _fetch_openweather_current(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_openweather_data
    res = fetch_openweather_data(lat, lng)
    if isinstance(res, dict) and "native_acquisition_id" in kw:
        res["native_acquisition_id"] = kw["native_acquisition_id"]
    return res


def _fetch_openweather_forecast(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_openweather_forecast
    res = fetch_openweather_forecast(lat, lng)
    if isinstance(res, dict) and "native_acquisition_id" in kw:
        res["native_acquisition_id"] = kw["native_acquisition_id"]
    return res


def _fetch_sentinel2_indices(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_vegetation_indices
    return fetch_vegetation_indices(lat, lng)


def _fetch_sentinel2_ndvi_ts(lat: float, lng: float, days: int = 180, **kw):
    from eo.sentinel import fetch_ndvi_timeseries
    return fetch_ndvi_timeseries(lat, lng, days)


def _fetch_sentinel1_sar(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_soil_moisture_proxy
    return fetch_soil_moisture_proxy(lat, lng)


def _fetch_sentinel1_sar_ts(lat: float, lng: float, days: int = 30, **kw):
    from eo.sentinel import fetch_sar_timeseries
    return fetch_sar_timeseries(lat, lng, days)


def _fetch_soilgrids(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_soil_properties
    return fetch_soil_properties(lat, lng)


def _fetch_water_balance(lat: float, lng: float, days_past: int = 30, days_future: int = 7, **kw):
    from eo.sentinel import fetch_water_balance
    return fetch_water_balance(lat, lng, days_past, days_future)


def _fetch_open_meteo_archive(lat: float, lng: float, start_date: str = "", end_date: str = "", **kw):
    """Registered historical fetch: native evidence when configured, never ID pass-through."""
    import json
    import os
    from services.agribrain.layer0.native_issuer.weather_acquisition_evidence import (
        NativeWeatherEvidenceStore,
    )
    from services.agribrain.layer0.native_issuer.weather_acquisition_boundary import (
        execute_and_capture_weather_get,
    )
    from services.agribrain.layer0.native_issuer.weather_qualifier import (
        screen_native_weather_receipt, WeatherScreenStatus,
    )

    root = (
        os.getenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", "").strip()
        or os.getenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", "").strip()
    )
    if not root:
        if os.getenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "").lower() in ("1", "true", "yes"):
            raise RuntimeError("native_weather_evidence_root_required")
        # Compatibility does not confer native provenance.
        from eo.sentinel import fetch_historical_weather
        result = fetch_historical_weather(lat, lng, start_date, end_date)
        if isinstance(result, dict):
            result = dict(result)
            result.pop("native_acquisition_id", None)
            result["native_capture_status"] = "unattested_legacy"
        return result

    store = NativeWeatherEvidenceStore(root)
    params = {
        "latitude": lat, "longitude": lng,
        "start_date": start_date, "end_date": end_date,
        "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum,et0_fao_evapotranspiration",
        "timezone": "UTC",
        "temperature_unit": "celsius", "precipitation_unit": "mm",
        "wind_speed_unit": "ms",
    }
    receipt = execute_and_capture_weather_get(
        endpoint="https://archive-api.open-meteo.com/v1/archive",
        params=params,
        store=store,
    )
    screen = screen_native_weather_receipt(
        receipt, store, expected_coordinates=(lat, lng),
    )
    if screen.status is not WeatherScreenStatus.SCREENED_NATIVE_QA:
        raise ValueError("native_weather_screen_rejected: " + screen.reason)
    payload = json.loads(store.read_response_bytes(receipt.object_id).decode("utf-8"))
    return {
        "native_capture_status": "screened_native_qa",
        "native_acquisition_id": receipt.acquisition_id,
        "native_product_id": receipt.product_id,
        "native_payload": payload,
    }


def _fetch_fire_risk(lat: float, lng: float, radius_km: int = 50, **kw):
    from eo.sentinel import fetch_fire_risk
    return fetch_fire_risk(lat, lng, radius_km)


def _fetch_soil_moisture_layers(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_soil_moisture_layers
    return fetch_soil_moisture_layers(lat, lng)


def _fetch_solar_radiation(lat: float, lng: float, days: int = 7, **kw):
    from eo.sentinel import fetch_solar_radiation
    return fetch_solar_radiation(lat, lng, days)


def _fetch_elevation(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_elevation
    return fetch_elevation(lat, lng)


def _fetch_air_quality(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_air_quality
    return fetch_air_quality(lat, lng)


def _fetch_land_cover(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_land_cover
    return fetch_land_cover(lat, lng)


def _fetch_biomass_estimate(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_biomass_estimate
    return fetch_biomass_estimate(lat, lng)


def _fetch_open_meteo_agri(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_open_meteo_agri_data
    return fetch_open_meteo_agri_data(lat, lng)


def _fetch_nasa_power(lat: float, lng: float, **kw):
    from eo.sentinel import fetch_nasa_power_data
    return fetch_nasa_power_data(lat, lng)



def _fetch_raster_composite_ndvi(lat: float, lng: float, start_date: str = "", end_date: str = "", **kw):
    from eo.sentinel import fetch_ndvi_raster_composite
    return fetch_ndvi_raster_composite(
        lat, lng, start_date, end_date,
        polygon_coords=kw.get("polygon_coords"),
        target_resolution_m=kw.get("target_resolution_m", 10.0),
        raster_contract_version=kw.get("raster_contract_version", ""),
    )


def _fetch_raster_composite_ndmi(lat: float, lng: float, start_date: str = "", end_date: str = "", **kw):
    from eo.sentinel import fetch_ndmi_raster_composite
    return fetch_ndmi_raster_composite(
        lat, lng, start_date, end_date,
        polygon_coords=kw.get("polygon_coords"),
        target_resolution_m=kw.get("target_resolution_m", 10.0),
        raster_contract_version=kw.get("raster_contract_version", ""),
    )


def _fetch_raster_composite_sar(lat: float, lng: float, start_date: str = "", end_date: str = "", **kw):
    from eo.sentinel import fetch_sar_raster_composite
    return fetch_sar_raster_composite(
        lat, lng, start_date, end_date,
        polygon_coords=kw.get("polygon_coords"),
        target_resolution_m=kw.get("target_resolution_m", 10.0),
        raster_contract_version=kw.get("raster_contract_version", ""),
    )


def _fetch_raster_quality_mask(lat: float, lng: float, start_date: str = "", end_date: str = "", **kw):
    from eo.sentinel import fetch_quality_mask
    return fetch_quality_mask(
        lat, lng, start_date, end_date,
        polygon_coords=kw.get("polygon_coords"),
        target_resolution_m=kw.get("target_resolution_m", 10.0),
        raster_contract_version=kw.get("raster_contract_version", ""),
    )


def _fetch_rainfall_climatology(lat: float, lng: float, **kw):
    from eo.water import fetch_rainfall_climatology
    return fetch_rainfall_climatology(lat, lng)


def _fetch_rainfall_history(lat: float, lng: float, years: int = 30, **kw):
    from eo.water import fetch_rainfall_history
    return fetch_rainfall_history(lat, lng, years)


# ── Sentinel-5P (TROPOMI SIF) ─────────────────────────────────────────

def _fetch_sentinel5p_sif(lat: float, lng: float, **kw):
    """Fetch latest Sentinel-5P TROPOMI SIF data.
    Note: S5P data is typically pre-fetched at the orchestrator level
    and passed into the engine. This wrapper exists for gateway
    consistency but may delegate to stored data."""
    # S5P uses pre-fetched packages, not a direct API call.
    # The fetch registry entry exists for completeness — the actual
    # acquisition happens via the orchestrator's EO pipeline.
    return None  # Placeholder — populated by orchestrator pipeline


def _fetch_sentinel5p_sif_ts(lat: float, lng: float, days: int = 90, **kw):
    """Fetch Sentinel-5P SIF timeseries (historical)."""
    return None  # Placeholder — populated by orchestrator pipeline


# ── Bulk Historical (for DNA Sequencing / Generative Inversion) ────────

def _fetch_bulk_historical_weather(lat: float, lng: float, days: int = 1800, **kw):
    from eo.sentinel import fetch_historical_weather
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    return fetch_historical_weather(lat, lng, start, end)


def _fetch_sentinel2_rgb_tile(lat: float, lng: float, plot_id: str = "", polygon_coords: Any = None, **kw):
    from layer0.perception.satellite_rgb.tile_runtime import fetch_rgb_tile
    import base64
    image_bytes = fetch_rgb_tile(plot_id=plot_id, lat=lat, lng=lng, polygon_coords=polygon_coords, force=True)
    if image_bytes:
        return {
            "image_bytes_base64": base64.b64encode(image_bytes).decode("utf-8")
        }
    return None


def _fetch_bulk_historical_ndvi(lat: float, lng: float, days: int = 1800, **kw):
    from eo.sentinel import fetch_ndvi_timeseries
    return fetch_ndvi_timeseries(lat, lng, days)



# ── Registry ──────────────────────────────────────────────────────────

FETCH_REGISTRY: Dict[str, Callable] = {
    # Sentinel-2 (Optical)
    "sentinel2_indices":        _fetch_sentinel2_indices,
    "sentinel2_ndvi_ts":        _fetch_sentinel2_ndvi_ts,

    # Sentinel-1 (SAR)
    "sentinel1_sar":            _fetch_sentinel1_sar,
    "sentinel1_sar_ts":         _fetch_sentinel1_sar_ts,

    # Sentinel-5P (TROPOMI)
    "sentinel5p_sif":           _fetch_sentinel5p_sif,
    "sentinel5p_sif_ts":        _fetch_sentinel5p_sif_ts,

    # Raster Composites
    "raster_composite_ndvi":    _fetch_raster_composite_ndvi,
    "raster_composite_ndmi":    _fetch_raster_composite_ndmi,
    "raster_composite_sar":     _fetch_raster_composite_sar,
    "raster_quality_mask":      _fetch_raster_quality_mask,

    # Weather
    "openweather_current":      _fetch_openweather_current,
    "openweather_forecast":     _fetch_openweather_forecast,
    "open_meteo_archive":       _fetch_open_meteo_archive,
    "water_balance":            _fetch_water_balance,
    "open_meteo_agri":          _fetch_open_meteo_agri,
    "nasa_power":               _fetch_nasa_power,

    # Static / Semi-Static
    "soilgrids":                _fetch_soilgrids,
    "elevation":                _fetch_elevation,
    "land_cover":               _fetch_land_cover,

    # Alerts
    "fire_risk":                _fetch_fire_risk,
    "air_quality":              _fetch_air_quality,
    "solar_radiation":          _fetch_solar_radiation,

    # Bulk Historical
    "bulk_historical_weather":  _fetch_bulk_historical_weather,
    "bulk_historical_ndvi":     _fetch_bulk_historical_ndvi,

    # Derived
    "soil_moisture_layers":     _fetch_soil_moisture_layers,
    "biomass_estimate":         _fetch_biomass_estimate,
    "sentinel2_rgb_tile":       _fetch_sentinel2_rgb_tile,
}


def get_fetch_fn(source: str) -> Optional[Callable]:
    """Get the fetch function for a registered source.

    Returns None if the source is not registered (user data
    types are handled by UserDataEngine, not fetch functions).
    """
    fn = FETCH_REGISTRY.get(source)
    if fn is None:
        logger.debug("No fetch function for source: %s", source)
    return fn


def get_registered_sources() -> list:
    """Return all source names with registered fetch functions."""
    return sorted(FETCH_REGISTRY.keys())


def is_fetchable(source: str) -> bool:
    """Check if a source has a fetch function (vs user/sensor data)."""
    return source in FETCH_REGISTRY
