"""B2B-04B Immutable Weather Provider Product Registry.

Establishes approved provider endpoints, products, HTTP methods, required
parameters, and authoritative dataset-role bindings.

This registry prevents role-spoofing and unauthorized endpoint access:
roles are derived strictly from the verified provider endpoint and product
contract, never from unauthenticated JSON labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional
from urllib.parse import urlsplit

from services.agribrain.layer0.environment.weather.source_roles import WeatherSourceRole


class WeatherProvider(str, Enum):
    OPEN_METEO = "open_meteo"
    OPENWEATHER = "openweather"


class WeatherProductId(str, Enum):
    # Open-Meteo Products
    OPEN_METEO_HISTORICAL_REANALYSIS = "open_meteo_historical_reanalysis"
    OPEN_METEO_LIVE_FORECAST = "open_meteo_live_forecast"
    OPEN_METEO_HISTORICAL_FORECAST = "open_meteo_historical_forecast"

    # OpenWeather Products (One Call 2.5 was discontinued June 2024; One Call 3.0 is required)
    OPENWEATHER_ONECALL_3_0 = "openweather_onecall_3_0"
    OPENWEATHER_CURRENT_2_5 = "openweather_current_2_5"
    OPENWEATHER_TIMEMACHINE_3_0 = "openweather_timemachine_3_0"


class WeatherRegistryError(ValueError):
    """Raised when an unapproved weather endpoint, product, or parameter is encountered."""


@dataclass(frozen=True)
class WeatherProductSpec:
    """Immutable specification for an approved weather provider product."""
    product_id: WeatherProductId
    provider: WeatherProvider
    allowed_endpoints: frozenset[str]
    allowed_methods: frozenset[str]
    authoritative_role: WeatherSourceRole
    required_params: frozenset[str]
    supports_date_range: bool
    spatial_tolerance_deg: float
    description: str


_OPEN_METEO_REANALYSIS_ENDPOINTS = frozenset({
    "https://archive-api.open-meteo.com/v1/archive",
})

_OPEN_METEO_FORECAST_ENDPOINTS = frozenset({
    "https://api.open-meteo.com/v1/forecast",
})

_OPENWEATHER_ONECALL_3_ENDPOINTS = frozenset({
    "https://api.openweathermap.org/data/3.0/onecall",
})

_OPENWEATHER_CURRENT_2_5_ENDPOINTS = frozenset({
    "https://api.openweathermap.org/data/2.5/weather",
})

_OPENWEATHER_TIMEMACHINE_3_ENDPOINTS = frozenset({
    "https://api.openweathermap.org/data/3.0/onecall/timemachine",
})

# Forbidden legacy/deprecated endpoints (One Call 2.5 was sunset in June 2024)
DISCONTINUED_ENDPOINTS = frozenset({
    "https://api.openweathermap.org/data/2.5/onecall",
    "http://api.openweathermap.org/data/2.5/onecall",
    "http://api.openweathermap.org/data/3.0/onecall",
    "http://api.openweathermap.org/data/2.5/weather",
    "http://archive-api.open-meteo.com/v1/archive",
    "http://api.open-meteo.com/v1/forecast",
})

WEATHER_PRODUCT_REGISTRY: Mapping[WeatherProductId, WeatherProductSpec] = {
    WeatherProductId.OPEN_METEO_HISTORICAL_REANALYSIS: WeatherProductSpec(
        product_id=WeatherProductId.OPEN_METEO_HISTORICAL_REANALYSIS,
        provider=WeatherProvider.OPEN_METEO,
        allowed_endpoints=_OPEN_METEO_REANALYSIS_ENDPOINTS,
        allowed_methods=frozenset({"GET"}),
        authoritative_role=WeatherSourceRole.REANALYSIS_MODEL,
        required_params=frozenset({"latitude", "longitude", "start_date", "end_date", "daily"}),
        supports_date_range=True,
        spatial_tolerance_deg=0.05,
        description="Open-Meteo ERA5 / ERA5-Land historical reanalysis archive",
    ),
    WeatherProductId.OPEN_METEO_LIVE_FORECAST: WeatherProductSpec(
        product_id=WeatherProductId.OPEN_METEO_LIVE_FORECAST,
        provider=WeatherProvider.OPEN_METEO,
        allowed_endpoints=_OPEN_METEO_FORECAST_ENDPOINTS,
        allowed_methods=frozenset({"GET"}),
        authoritative_role=WeatherSourceRole.FORECAST_MODEL,
        required_params=frozenset({"latitude", "longitude"}),
        supports_date_range=False,
        spatial_tolerance_deg=0.05,
        description="Open-Meteo numerical weather prediction live forecast",
    ),
    WeatherProductId.OPEN_METEO_HISTORICAL_FORECAST: WeatherProductSpec(
        product_id=WeatherProductId.OPEN_METEO_HISTORICAL_FORECAST,
        provider=WeatherProvider.OPEN_METEO,
        allowed_endpoints=_OPEN_METEO_FORECAST_ENDPOINTS,
        allowed_methods=frozenset({"GET"}),
        authoritative_role=WeatherSourceRole.HISTORICAL_FORECAST_MODEL,
        required_params=frozenset({"latitude", "longitude", "start_date", "end_date"}),
        supports_date_range=True,
        spatial_tolerance_deg=0.05,
        description="Open-Meteo previous runs / historical forecast archive (stitched runs cannot claim single initialization)",
    ),
    WeatherProductId.OPENWEATHER_ONECALL_3_0: WeatherProductSpec(
        product_id=WeatherProductId.OPENWEATHER_ONECALL_3_0,
        provider=WeatherProvider.OPENWEATHER,
        allowed_endpoints=_OPENWEATHER_ONECALL_3_ENDPOINTS,
        allowed_methods=frozenset({"GET"}),
        authoritative_role=WeatherSourceRole.FORECAST_MODEL,
        required_params=frozenset({"lat", "lon"}),
        supports_date_range=False,
        spatial_tolerance_deg=0.05,
        description="OpenWeather One Call API 3.0 daily/hourly forecast",
    ),
    WeatherProductId.OPENWEATHER_CURRENT_2_5: WeatherProductSpec(
        product_id=WeatherProductId.OPENWEATHER_CURRENT_2_5,
        provider=WeatherProvider.OPENWEATHER,
        allowed_endpoints=_OPENWEATHER_CURRENT_2_5_ENDPOINTS,
        allowed_methods=frozenset({"GET"}),
        authoritative_role=WeatherSourceRole.CURRENT_PROVIDER_CONTEXT,
        required_params=frozenset({"lat", "lon"}),
        supports_date_range=False,
        spatial_tolerance_deg=0.05,
        description="OpenWeather Current Weather API 2.5 (snapshot context only, never daily total)",
    ),
    WeatherProductId.OPENWEATHER_TIMEMACHINE_3_0: WeatherProductSpec(
        product_id=WeatherProductId.OPENWEATHER_TIMEMACHINE_3_0,
        provider=WeatherProvider.OPENWEATHER,
        allowed_endpoints=_OPENWEATHER_TIMEMACHINE_3_ENDPOINTS,
        allowed_methods=frozenset({"GET"}),
        authoritative_role=WeatherSourceRole.REANALYSIS_MODEL,
        required_params=frozenset({"lat", "lon", "dt"}),
        supports_date_range=False,
        spatial_tolerance_deg=0.05,
        description="OpenWeather One Call 3.0 Timemachine historical weather data",
    ),
}

ALL_ALLOWED_WEATHER_ENDPOINTS: frozenset[str] = frozenset(
    endpoint for spec in WEATHER_PRODUCT_REGISTRY.values() for endpoint in spec.allowed_endpoints
)


def get_weather_product_spec(product_id: WeatherProductId | str) -> WeatherProductSpec:
    """Retrieve product specification by product ID or fail closed."""
    if isinstance(product_id, str):
        try:
            product_id = WeatherProductId(product_id)
        except ValueError:
            raise WeatherRegistryError(f"unrecognized_weather_product_id: {product_id}") from None
    if product_id not in WEATHER_PRODUCT_REGISTRY:
        raise WeatherRegistryError(f"unregistered_weather_product: {product_id}")
    return WEATHER_PRODUCT_REGISTRY[product_id]


def _normalize_endpoint(url: str) -> str:
    """Normalize URL by stripping query strings and trailing slashes."""
    parts = urlsplit(url)
    if parts.scheme.lower() != "https":
        raise WeatherRegistryError(f"insecure_weather_endpoint_scheme: {parts.scheme} (HTTPS required)")
    normalized = f"{parts.scheme.lower()}://{parts.netloc.lower()}{parts.path.rstrip('/')}"
    return normalized


def identify_weather_product(endpoint: str, params: Mapping[str, Any]) -> WeatherProductSpec:
    """Identify product specification from endpoint and query parameters."""
    normalized_url = _normalize_endpoint(endpoint)

    if normalized_url in DISCONTINUED_ENDPOINTS:
        raise WeatherRegistryError(
            f"discontinued_or_forbidden_endpoint: {endpoint} "
            "(OpenWeather One Call 2.5 was sunset in June 2024; use One Call 3.0)"
        )

    # 1. Open-Meteo Historical Reanalysis
    if normalized_url in _OPEN_METEO_REANALYSIS_ENDPOINTS:
        return WEATHER_PRODUCT_REGISTRY[WeatherProductId.OPEN_METEO_HISTORICAL_REANALYSIS]

    # 2. Open-Meteo Forecast vs Historical Forecast
    if normalized_url in _OPEN_METEO_FORECAST_ENDPOINTS:
        # If explicit historical start_date/end_date or past_days requested, it's historical forecast archive
        if "start_date" in params or "past_days" in params or "historical" in params:
            return WEATHER_PRODUCT_REGISTRY[WeatherProductId.OPEN_METEO_HISTORICAL_FORECAST]
        return WEATHER_PRODUCT_REGISTRY[WeatherProductId.OPEN_METEO_LIVE_FORECAST]

    # 3. OpenWeather Products
    if normalized_url in _OPENWEATHER_ONECALL_3_ENDPOINTS:
        return WEATHER_PRODUCT_REGISTRY[WeatherProductId.OPENWEATHER_ONECALL_3_0]

    if normalized_url in _OPENWEATHER_CURRENT_2_5_ENDPOINTS:
        return WEATHER_PRODUCT_REGISTRY[WeatherProductId.OPENWEATHER_CURRENT_2_5]

    if normalized_url in _OPENWEATHER_TIMEMACHINE_3_ENDPOINTS:
        return WEATHER_PRODUCT_REGISTRY[WeatherProductId.OPENWEATHER_TIMEMACHINE_3_0]

    raise WeatherRegistryError(f"unregistered_or_disallowed_weather_endpoint: {endpoint}")


def validate_weather_product_request(
    spec: WeatherProductSpec,
    method: str,
    params: Mapping[str, Any],
) -> None:
    """Validate that HTTP method and required parameters conform to the product spec."""
    method_upper = method.upper().strip()
    if method_upper not in spec.allowed_methods:
        raise WeatherRegistryError(
            f"disallowed_weather_http_method: {method} for product {spec.product_id} "
            f"(allowed: {sorted(spec.allowed_methods)})"
        )

    param_keys = set(params.keys())
    missing = spec.required_params - param_keys
    if missing:
        raise WeatherRegistryError(
            f"missing_required_weather_params: {sorted(missing)} for product {spec.product_id}"
        )

    # Validate coordinate finite ranges
    lat_key = "latitude" if "latitude" in params else ("lat" if "lat" in params else None)
    lon_key = "longitude" if "longitude" in params else ("lon" if "lon" in params else None)

    if lat_key is not None:
        try:
            lat = float(params[lat_key])
            if not (-90.0 <= lat <= 90.0):
                raise WeatherRegistryError(f"invalid_latitude_range: {lat}")
        except (ValueError, TypeError):
            raise WeatherRegistryError(f"non_numeric_latitude: {params[lat_key]}")

    if lon_key is not None:
        try:
            lon = float(params[lon_key])
            if not (-180.0 <= lon <= 180.0):
                raise WeatherRegistryError(f"invalid_longitude_range: {lon}")
        except (ValueError, TypeError):
            raise WeatherRegistryError(f"non_numeric_longitude: {params[lon_key]}")
