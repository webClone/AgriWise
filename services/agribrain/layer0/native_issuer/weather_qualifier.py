"""B2B-04B Independent, Non-Authorizing Weather Native QA Screen.

Verifies captured weather provider response bytes, product identity, spatial coordinates,
temporal coverage, and true zero precipitation against immutable registry contracts.

This module NEVER signs an observation grant, mutates existing production flags,
or grants Kalman state-update or scientific publication authority.

Even a successful screen is NOT trusted physical ground station measurement:
an authenticated HTTP transport receipt is distinct from an independently calibrated
WMO surface weather station.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Sequence
import hashlib
import json
import math

from services.agribrain.layer0.native_issuer.weather_product_registry import (
    WeatherProductId,
    WeatherProductSpec,
    WeatherRegistryError,
    get_weather_product_spec,
    validate_weather_product_request,
)
from services.agribrain.layer0.native_issuer.weather_acquisition_evidence import (
    WEATHER_EVIDENCE_DOMAIN,
    NativeWeatherAcquisitionReceipt,
    NativeWeatherEvidenceError,
    NativeWeatherEvidenceStore,
    _json_bytes,
    _reject_duplicate_keys,
    _sha,
)


WEATHER_QUALIFIER_DOMAIN = "akaloris/layer0/weather-native-qa-screen/v1"


class WeatherScreenStatus(str, Enum):
    REJECTED = "REJECTED"
    SCREENED_NATIVE_QA = "SCREENED_NATIVE_QA"


@dataclass(frozen=True)
class WeatherNativeQAScreen:
    """Diagnostic outcome of native weather QA screening."""
    status: WeatherScreenStatus
    reason: str
    product_id: str = ""
    authoritative_role: str = ""
    proof_hash: str | None = None
    diagnostic_metrics: dict[str, Any] = field(default_factory=dict)
    source_qualified: bool = False
    eligible_for_state_grant: bool = False
    scientific_publication_authorized: bool = False


def _deny(reason: str, product_id: str = "", authoritative_role: str = "") -> WeatherNativeQAScreen:
    """Helper to return fail-closed rejection."""
    return WeatherNativeQAScreen(
        status=WeatherScreenStatus.REJECTED,
        reason=reason,
        product_id=product_id,
        authoritative_role=authoritative_role,
        proof_hash=None,
        diagnostic_metrics={},
        source_qualified=False,
        eligible_for_state_grant=False,
        scientific_publication_authorized=False,
    )


def screen_native_weather_receipt(
    receipt: NativeWeatherAcquisitionReceipt,
    store: NativeWeatherEvidenceStore,
    *,
    expected_coordinates: tuple[float, float] | None = None,
    expected_dates: Sequence[str] | None = None,
) -> WeatherNativeQAScreen:
    """Verify CAS response bytes, registry alignment, spatial coordinates, and temporal ranges.
    
    Ensures that raw response bytes match receipt SHA-256, coordinates match requested
    location within spatial tolerance, dates match requested interval, and true measured
    zeros in precipitation are preserved.
    """
    # 1. Basic Receipt Integrity
    if not isinstance(receipt, NativeWeatherAcquisitionReceipt):
        return _deny("invalid_receipt_type")

    if receipt.qualification_status != "NOT_QUALIFIED" or receipt.provider_signature_verified is not False:
        return _deny("unauthorized_authority_self_promotion", receipt.product_id, receipt.authoritative_role)

    # 2. Product Registry Specification Verification
    try:
        spec = get_weather_product_spec(receipt.product_id)
    except (WeatherRegistryError, ValueError):
        return _deny("unregistered_weather_product", receipt.product_id, receipt.authoritative_role)

    if receipt.endpoint not in spec.allowed_endpoints:
        return _deny("disallowed_weather_endpoint", receipt.product_id, receipt.authoritative_role)

    if receipt.authoritative_role != spec.authoritative_role.value:
        return _deny("contradictory_authoritative_role", receipt.product_id, receipt.authoritative_role)

    # 3. Read and Verify Raw CAS Response Bytes
    try:
        raw_bytes = store.read_response_bytes(receipt.object_id)
    except NativeWeatherEvidenceError as exc:
        return _deny(f"cas_byte_verification_failed: {exc}", receipt.product_id, receipt.authoritative_role)

    if _sha(raw_bytes) != receipt.response_sha256 or receipt.object_id != receipt.response_sha256:
        return _deny("tampered_response_bytes", receipt.product_id, receipt.authoritative_role)

    if len(raw_bytes) != receipt.response_bytes:
        return _deny("response_bytes_count_mismatch", receipt.product_id, receipt.authoritative_role)

    # 4. Request Replay Verification
    try:
        replayed_params = store.verified_request_params(receipt.acquisition_id)
        validate_weather_product_request(spec, "GET", replayed_params)
    except (NativeWeatherEvidenceError, WeatherRegistryError) as exc:
        return _deny(f"invalid_or_missing_request_replay: {exc}", receipt.product_id, receipt.authoritative_role)

    if _sha(_json_bytes(replayed_params)) != receipt.request_sha256:
        return _deny("request_replay_hash_mismatch", receipt.product_id, receipt.authoritative_role)

    # 5. Parse Response JSON
    try:
        payload = json.loads(raw_bytes.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        if not isinstance(payload, dict):
            return _deny("non_object_json_response", receipt.product_id, receipt.authoritative_role)
    except (json.JSONDecodeError, UnicodeDecodeError, NativeWeatherEvidenceError) as exc:
        return _deny(f"malformed_response_json: {exc}", receipt.product_id, receipt.authoritative_role)

    # 6. Spatial Reconciliation
    req_lat, req_lon = receipt.coordinate_requested
    tol = spec.spatial_tolerance_deg

    # Check caller expected coordinates if provided
    if expected_coordinates is not None:
        exp_lat, exp_lon = expected_coordinates
        if abs(exp_lat - req_lat) > tol or abs(exp_lon - req_lon) > tol:
            return _deny("weather_spatial_coordinate_mismatch", receipt.product_id, receipt.authoritative_role)

    # Extract coordinates from payload
    resp_lat: Optional[float] = None
    resp_lon: Optional[float] = None

    if "latitude" in payload and "longitude" in payload:
        resp_lat = payload.get("latitude")
        resp_lon = payload.get("longitude")
    elif "lat" in payload and "lon" in payload:
        resp_lat = payload.get("lat")
        resp_lon = payload.get("lon")
    elif "coord" in payload and isinstance(payload["coord"], dict):
        resp_lat = payload["coord"].get("lat")
        resp_lon = payload["coord"].get("lon")

    if resp_lat is not None and resp_lon is not None:
        try:
            resp_lat = float(resp_lat)
            resp_lon = float(resp_lon)
            if abs(resp_lat - req_lat) > tol or abs(resp_lon - req_lon) > tol:
                return _deny("weather_spatial_coordinate_mismatch", receipt.product_id, receipt.authoritative_role)
        except (ValueError, TypeError):
            return _deny("non_numeric_response_coordinates", receipt.product_id, receipt.authoritative_role)

    # 7. Temporal Reconciliation
    dates_found: list[str] = []
    if "daily" in payload and isinstance(payload["daily"], dict):
        times = payload["daily"].get("time", [])
        if isinstance(times, list):
            dates_found = [str(t) for t in times]

    # Verify requested start/end dates
    req_start, req_end = receipt.valid_interval
    if req_start and req_end and dates_found:
        if req_start not in dates_found or req_end not in dates_found:
            # Check range coverage
            min_date = min(dates_found)
            max_date = max(dates_found)
            if min_date > req_start or max_date < req_end:
                return _deny("weather_temporal_range_mismatch", receipt.product_id, receipt.authoritative_role)

    # Verify expected dates if caller provided them
    if expected_dates is not None and dates_found:
        for exp_d in expected_dates:
            if exp_d not in dates_found:
                return _deny("weather_temporal_range_mismatch", receipt.product_id, receipt.authoritative_role)

    # 8. True Zero Precipitation and Range Validation
    precip_values: list[float] = []
    zero_precip_count = 0

    if "daily" in payload and isinstance(payload["daily"], dict):
        daily = payload["daily"]
        p_sums = daily.get("precipitation_sum", [])
        if isinstance(p_sums, list):
            for val in p_sums:
                if val is not None:
                    try:
                        f_val = float(val)
                        if not math.isfinite(f_val):
                            return _deny("non_finite_precipitation_value", receipt.product_id, receipt.authoritative_role)
                        if f_val < 0.0:
                            return _deny("invalid_precipitation_value", receipt.product_id, receipt.authoritative_role)
                        precip_values.append(f_val)
                        if f_val == 0.0:
                            zero_precip_count += 1
                    except (ValueError, TypeError):
                        return _deny("non_numeric_precipitation_value", receipt.product_id, receipt.authoritative_role)

    # 9. Diagnostic Metrics and Deterministic Proof Hash
    metrics: dict[str, Any] = {
        "dates_count": len(dates_found),
        "start_date": dates_found[0] if dates_found else req_start,
        "end_date": dates_found[-1] if dates_found else req_end,
        "zero_precipitation_days": zero_precip_count,
        "total_precipitation_mm": round(sum(precip_values), 4) if precip_values else 0.0,
        "coordinate_reconciled": (resp_lat is not None and resp_lon is not None),
    }

    proof_material = {
        "domain": WEATHER_QUALIFIER_DOMAIN,
        "acquisition_id": receipt.acquisition_id,
        "product_id": receipt.product_id,
        "authoritative_role": receipt.authoritative_role,
        "response_sha256": receipt.response_sha256,
        "request_sha256": receipt.request_sha256,
        "coordinate_requested": list(receipt.coordinate_requested),
        "valid_interval": list(receipt.valid_interval),
        "diagnostic_metrics": metrics,
    }
    proof_hash = _sha(_json_bytes(proof_material))

    return WeatherNativeQAScreen(
        status=WeatherScreenStatus.SCREENED_NATIVE_QA,
        reason="qualified_native_weather_screen",
        product_id=receipt.product_id,
        authoritative_role=receipt.authoritative_role,
        proof_hash=proof_hash,
        diagnostic_metrics=metrics,
        source_qualified=False,
        eligible_for_state_grant=False,
        scientific_publication_authorized=False,
    )
