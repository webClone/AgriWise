"""B2B-04B Native HTTP Weather Acquisition Boundary.

Ensures that live HTTP GET requests to weather providers are executed with
fail-closed TLS enforcement, no redirects (allow_redirects=False), timeout
guardrails, secret scrubbing, and content-addressed retention in CAS.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional
import os

from services.agribrain.layer0.native_issuer.weather_acquisition_evidence import (
    NativeWeatherAcquisitionReceipt,
    NativeWeatherEvidenceError,
    NativeWeatherEvidenceStore,
    capture_backend_weather_response,
)
from services.agribrain.layer0.native_issuer.weather_product_registry import (
    WeatherRegistryError,
    identify_weather_product,
    normalize_and_validate_endpoint,
    validate_weather_product_request,
)


def execute_and_capture_weather_get(
    *,
    endpoint: str,
    params: Mapping[str, Any],
    store: NativeWeatherEvidenceStore,
    timeout: float = 30.0,
    credential_reference: str = "open_access",
) -> NativeWeatherAcquisitionReceipt:
    """Execute live HTTP GET request to approved weather endpoint and record evidence in CAS.
    
    Refuses HTTP redirects, enforces strict HTTPS, scrubs secrets from the stored
    canonical parameters, and returns an immutable NativeWeatherAcquisitionReceipt.
    """
    import requests

    try:
        normalized_endpoint = normalize_and_validate_endpoint(endpoint)
        spec = identify_weather_product(normalized_endpoint, params)
        validate_weather_product_request(spec, "GET", params)
    except WeatherRegistryError as exc:
        raise NativeWeatherEvidenceError(f"unapproved weather request: {exc}") from exc

    headers = {
        "Accept": "application/json",
        "User-Agent": "AgriWise-Akaloris-Layer0/1.0",
    }

    try:
        resp = requests.get(
            normalized_endpoint,
            params=dict(params),
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise NativeWeatherEvidenceError(f"weather network request failed: {exc}") from exc

    return store.capture_http_response(
        response=resp,
        endpoint=normalized_endpoint,
        query_params=params,
        credential_reference=credential_reference,
    )
