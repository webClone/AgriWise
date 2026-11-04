"""Native provider issuance domain.

B2B-01 provides acquisition traces only. No signing, scientific qualification,
state-input grants, or pilot publication permission originate in this package.
"""
from services.agribrain.layer0.native_issuer.weather_product_registry import (
    WeatherProductId,
    WeatherProductSpec,
    WeatherProvider,
    WeatherRegistryError,
    WEATHER_PRODUCT_REGISTRY,
    get_weather_product_spec,
    identify_weather_product,
    validate_weather_product_request,
)
from services.agribrain.layer0.native_issuer.weather_acquisition_evidence import (
    WEATHER_EVIDENCE_DOMAIN,
    WEATHER_REQUEST_REPLAY_DOMAIN,
    MAX_WEATHER_RESPONSE_BYTES,
    NativeWeatherAcquisitionReceipt,
    NativeWeatherEvidenceError,
    NativeWeatherEvidenceStore,
    OriginClass,
    capture_backend_weather_response,
)
from services.agribrain.layer0.native_issuer.weather_qualifier import (
    WEATHER_QUALIFIER_DOMAIN,
    WeatherNativeQAScreen,
    WeatherScreenStatus,
    screen_native_weather_receipt,
)

__all__ = [
    # Weather registry
    "WeatherProductId",
    "WeatherProductSpec",
    "WeatherProvider",
    "WeatherRegistryError",
    "WEATHER_PRODUCT_REGISTRY",
    "get_weather_product_spec",
    "identify_weather_product",
    "validate_weather_product_request",
    # Weather evidence & CAS
    "WEATHER_EVIDENCE_DOMAIN",
    "WEATHER_REQUEST_REPLAY_DOMAIN",
    "MAX_WEATHER_RESPONSE_BYTES",
    "NativeWeatherAcquisitionReceipt",
    "NativeWeatherEvidenceError",
    "NativeWeatherEvidenceStore",
    "OriginClass",
    "capture_backend_weather_response",
    # Weather qualifier
    "WEATHER_QUALIFIER_DOMAIN",
    "WeatherNativeQAScreen",
    "WeatherScreenStatus",
    "screen_native_weather_receipt",
]
