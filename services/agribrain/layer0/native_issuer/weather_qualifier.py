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
    
    Ensures that:
    1. Caller receipt strictly matches the stored immutable CAS manifest (no receipt substitution).
    2. Raw CAS response bytes match receipt SHA-256 and byte count.
    3. Stored request replay matches receipt request_sha256 and registry spec.
    4. Coordinates match requested location within provider grid tolerance (<= 0.05 deg).
    5. Dates match requested interval, with mandatory product-specific payload structures.
    6. True measured zeros in precipitation are preserved and distinguish dry days from missing data.
    """
    # 1. Basic Receipt Type and Non-Authorizing Invariants
    if not isinstance(receipt, NativeWeatherAcquisitionReceipt):
        return _deny("invalid_receipt_type")

    if receipt.qualification_status != "NOT_QUALIFIED" or receipt.provider_signature_verified is not False:
        return _deny("unauthorized_authority_self_promotion", receipt.product_id, receipt.authoritative_role)

    # 2. Strict Stored Manifest Verification (Anti-Substitution Rule)
    # The caller-supplied receipt MUST be identical to the immutable manifest on disk for receipt.acquisition_id.
    try:
        stored_receipt = store.verified_cache_receipt(receipt.acquisition_id)
    except NativeWeatherEvidenceError as exc:
        return _deny(f"stored_acquisition_manifest_invalid: {exc}", receipt.product_id, receipt.authoritative_role)

    if (
        receipt.acquisition_id != stored_receipt.acquisition_id
        or receipt.request_sha256 != stored_receipt.request_sha256
        or receipt.response_sha256 != stored_receipt.response_sha256
        or receipt.response_bytes != stored_receipt.response_bytes
        or receipt.object_id != stored_receipt.object_id
        or receipt.endpoint != stored_receipt.endpoint
        or receipt.product_id != stored_receipt.product_id
        or receipt.authoritative_role != stored_receipt.authoritative_role
        or receipt.coordinate_requested != stored_receipt.coordinate_requested
        or receipt.valid_interval != stored_receipt.valid_interval
        or receipt.canonical_query_params != stored_receipt.canonical_query_params
    ):
        return _deny("acquisition_receipt_manifest_mismatch", receipt.product_id, receipt.authoritative_role)

    # 3. Product Registry Specification Verification
    try:
        spec = get_weather_product_spec(receipt.product_id)
    except (WeatherRegistryError, ValueError):
        return _deny("unregistered_weather_product", receipt.product_id, receipt.authoritative_role)

    if receipt.endpoint not in spec.allowed_endpoints:
        return _deny("disallowed_weather_endpoint", receipt.product_id, receipt.authoritative_role)

    if receipt.authoritative_role != spec.authoritative_role.value:
        return _deny("contradictory_authoritative_role", receipt.product_id, receipt.authoritative_role)

    # 4. Read and Verify Raw CAS Response Bytes
    try:
        raw_bytes = store.read_response_bytes(receipt.object_id)
    except NativeWeatherEvidenceError as exc:
        return _deny(f"cas_byte_verification_failed: {exc}", receipt.product_id, receipt.authoritative_role)

    if _sha(raw_bytes) != receipt.response_sha256 or receipt.object_id != receipt.response_sha256:
        return _deny("tampered_response_bytes", receipt.product_id, receipt.authoritative_role)

    if len(raw_bytes) != receipt.response_bytes:
        return _deny("response_bytes_count_mismatch", receipt.product_id, receipt.authoritative_role)

    # 5. Request Replay Verification
    try:
        replayed_params = store.verified_request_params(receipt.acquisition_id)
        validate_weather_product_request(spec, "GET", replayed_params)
    except (NativeWeatherEvidenceError, WeatherRegistryError) as exc:
        return _deny(f"invalid_or_missing_request_replay: {exc}", receipt.product_id, receipt.authoritative_role)

    if _sha(_json_bytes(replayed_params)) != receipt.request_sha256:
        return _deny("request_replay_hash_mismatch", receipt.product_id, receipt.authoritative_role)

    # 6. Parse Response JSON
    try:
        payload = json.loads(raw_bytes.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        if not isinstance(payload, dict):
            return _deny("non_object_json_response", receipt.product_id, receipt.authoritative_role)
    except (json.JSONDecodeError, UnicodeDecodeError, NativeWeatherEvidenceError) as exc:
        return _deny(f"malformed_response_json: {exc}", receipt.product_id, receipt.authoritative_role)

    # 7. Spatial Reconciliation
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

    # 8. Mandatory Product-Specific Structural & Temporal Validation
    dates_found: list[str] = []
    precip_values: list[float] = []
    zero_precip_count = 0

    if receipt.product_id in (
        WeatherProductId.OPEN_METEO_HISTORICAL_REANALYSIS.value,
        WeatherProductId.OPEN_METEO_HISTORICAL_FORECAST.value,
    ):
        # Open-Meteo Historical products REQUIRE top-level latitude, longitude, and non-empty daily.time
        if "latitude" not in payload or "longitude" not in payload:
            return _deny("missing_required_coordinates_in_payload", receipt.product_id, receipt.authoritative_role)

        if "daily" not in payload or not isinstance(payload["daily"], dict):
            return _deny("missing_daily_payload_block", receipt.product_id, receipt.authoritative_role)

        daily = payload["daily"]
        times = daily.get("time")
        if not isinstance(times, list) or len(times) == 0:
            return _deny("missing_daily_time_series", receipt.product_id, receipt.authoritative_role)

        dates_found = [str(t) for t in times]
        # Validate date string formats
        for d_str in dates_found:
            if len(d_str) != 10 or d_str[4] != '-' or d_str[7] != '-':
                return _deny("invalid_daily_date_format", receipt.product_id, receipt.authoritative_role)

        # Check that requested start/end dates are covered
        req_start, req_end = receipt.valid_interval
        if req_start and req_end:
            min_date = min(dates_found)
            max_date = max(dates_found)
            if min_date > req_start or max_date < req_end or req_start not in dates_found or req_end not in dates_found:
                return _deny("weather_temporal_range_mismatch", receipt.product_id, receipt.authoritative_role)

        if expected_dates is not None:
            for exp_d in expected_dates:
                if exp_d not in dates_found:
                    return _deny("weather_temporal_range_mismatch", receipt.product_id, receipt.authoritative_role)

        # Validate variables exist in daily
        has_daily_var = any(
            k in daily for k in (
                "precipitation_sum", "rain_sum", "temperature_2m_max",
                "temperature_2m_min", "temperature_2m_mean",
            )
        )
        if not has_daily_var:
            return _deny("missing_daily_variable_series", receipt.product_id, receipt.authoritative_role)

        # Validate precipitation sum
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

    elif receipt.product_id == WeatherProductId.OPEN_METEO_LIVE_FORECAST.value:
        # Live forecast must contain hourly or daily with non-empty time
        has_hourly = isinstance(payload.get("hourly"), dict) and bool(payload["hourly"].get("time"))
        has_daily = isinstance(payload.get("daily"), dict) and bool(payload["daily"].get("time"))
        if not has_hourly and not has_daily:
            return _deny("missing_forecast_time_series", receipt.product_id, receipt.authoritative_role)

    elif receipt.product_id == WeatherProductId.OPENWEATHER_ONECALL_3_0.value:
        if "lat" not in payload or "lon" not in payload:
            return _deny("missing_required_coordinates_in_payload", receipt.product_id, receipt.authoritative_role)
        has_daily = isinstance(payload.get("daily"), list) and len(payload["daily"]) > 0
        has_hourly = isinstance(payload.get("hourly"), list) and len(payload["hourly"]) > 0
        has_current = isinstance(payload.get("current"), dict)
        if not has_daily and not has_hourly and not has_current:
            return _deny("missing_openweather_forecast_data", receipt.product_id, receipt.authoritative_role)

    elif receipt.product_id == WeatherProductId.OPENWEATHER_CURRENT_2_5.value:
        if "coord" not in payload or not isinstance(payload["coord"], dict):
            return _deny("missing_current_coordinates_block", receipt.product_id, receipt.authoritative_role)
        if "main" not in payload or not isinstance(payload["main"], dict):
            return _deny("missing_current_main_block", receipt.product_id, receipt.authoritative_role)
        if "dt" not in payload:
            return _deny("missing_current_timestamp", receipt.product_id, receipt.authoritative_role)

    elif receipt.product_id == WeatherProductId.OPENWEATHER_TIMEMACHINE_3_0.value:
        if "lat" not in payload or "lon" not in payload:
            return _deny("missing_required_coordinates_in_payload", receipt.product_id, receipt.authoritative_role)
        data_records = payload.get("data")
        if not isinstance(data_records, list) or len(data_records) == 0:
            return _deny("missing_timemachine_data_records", receipt.product_id, receipt.authoritative_role)
        first_rec = data_records[0]
        if not isinstance(first_rec, dict) or "dt" not in first_rec:
            return _deny("missing_timemachine_timestamp", receipt.product_id, receipt.authoritative_role)
        # Reconcile dt against requested dt from replay params
        if "dt" in replayed_params:
            try:
                req_dt = int(replayed_params["dt"])
                resp_dt = int(first_rec["dt"])
                if abs(resp_dt - req_dt) > 3600:
                    return _deny("weather_temporal_range_mismatch", receipt.product_id, receipt.authoritative_role)
            except (ValueError, TypeError):
                return _deny("non_numeric_timemachine_timestamp", receipt.product_id, receipt.authoritative_role)

    # 9. Diagnostic Metrics and Deterministic Proof Hash
    metrics: dict[str, Any] = {
        "dates_count": len(dates_found),
        "start_date": dates_found[0] if dates_found else receipt.valid_interval[0],
        "end_date": dates_found[-1] if dates_found else receipt.valid_interval[1],
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
