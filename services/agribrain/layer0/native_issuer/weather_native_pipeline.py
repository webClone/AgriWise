"""Resolve a native weather payload strictly from verified CAS, never caller metadata.

The normal broker cache may hold a transport bundle; any native evidence claim
must be independently reloaded, screened, and bound to the stored raw payload.
"""
from __future__ import annotations

import json
import os
from typing import Any, Mapping

from services.agribrain.layer0.native_issuer.weather_acquisition_evidence import (
    NativeWeatherEvidenceStore, NativeWeatherEvidenceError,
)
from services.agribrain.layer0.native_issuer.weather_qualifier import (
    screen_native_weather_receipt, WeatherScreenStatus,
)
from services.agribrain.layer0.native_issuer.weather_product_registry import WeatherProductId


def resolve_verified_open_meteo_payload(
    bundle: Mapping[str, Any], *, latitude: float, longitude: float,
) -> tuple[dict[str, Any], str]:
    """Reject forged IDs, altered cached payloads or disallowed dataset roles."""
    if not isinstance(bundle, Mapping):
        raise NativeWeatherEvidenceError("invalid_native_weather_bundle")
    acquisition_id = bundle.get("native_acquisition_id")
    if (
        not isinstance(acquisition_id, str)
        or bundle.get("native_capture_status") != "screened_native_qa"
        or bundle.get("native_product_id") != WeatherProductId.OPEN_METEO_HISTORICAL_REANALYSIS.value
    ):
        raise NativeWeatherEvidenceError("invalid_native_weather_capture_claim")
    root = (
        os.getenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", "").strip()
        or os.getenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", "").strip()
    )
    if not root:
        raise NativeWeatherEvidenceError("missing_native_weather_evidence_root")

    store = NativeWeatherEvidenceStore(root)
    receipt = store.verified_cache_receipt(acquisition_id)
    if receipt.product_id != WeatherProductId.OPEN_METEO_HISTORICAL_REANALYSIS.value:
        raise NativeWeatherEvidenceError("wrong_native_weather_product")
    screen = screen_native_weather_receipt(
        receipt, store, expected_coordinates=(latitude, longitude),
    )
    if screen.status is not WeatherScreenStatus.SCREENED_NATIVE_QA:
        raise NativeWeatherEvidenceError("native_weather_screen_rejected: " + screen.reason)

    # Treat CAS as the only raw payload authority, never the cached body.
    payload = json.loads(store.read_response_bytes(receipt.object_id).decode("utf-8"))
    if not isinstance(payload, dict) or bundle.get("native_payload") != payload:
        raise NativeWeatherEvidenceError("native_weather_cached_payload_mismatch")
    return payload, acquisition_id
