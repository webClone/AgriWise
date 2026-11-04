"""B2B-04B Native Weather Provider HTTP Capture and CAS Binding Regression Tests.

Verifies:
1. Immutable Weather Product Registry and endpoint allowlists.
2. Separation of Open-Meteo Historical Forecast API host from live forecast.
3. Credential scrubbing and prohibition of secrets/queries in endpoint URLs.
4. Wire-request inspection: prepared GET request URL must match declared parameters.
5. Receipt substitution protection: qualifier verifies caller receipt against stored manifest.
6. Product-specific payload structural checks (missing daily series, timemachine dt, etc.).
7. Redirect prohibition and strict HTTPS enforcement.
8. Atomic Content-Addressed Store (CAS) byte retention and manifest verification.
9. Cache reverification returning PROVENANCE_VERIFIED_CACHE, never self-promoting to LIVE.
10. Weather Product Qualifier spatial, temporal, product, and true zero precipitation screening.
11. End-to-end downstream evidence lineage binding from CAS capture through packetizer,
    Layer 0 wrappers, and ASMAE weather archive adapter.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import urlencode
import hashlib
import json
import pytest

from services.agribrain.layer0.native_issuer.weather_product_registry import (
    WeatherProductId,
    WeatherProductSpec,
    WeatherProvider,
    WeatherRegistryError,
    WEATHER_PRODUCT_REGISTRY,
    get_weather_product_spec,
    identify_weather_product,
    normalize_and_validate_endpoint,
    validate_weather_product_request,
)
from services.agribrain.layer0.native_issuer.weather_acquisition_evidence import (
    WEATHER_EVIDENCE_DOMAIN,
    WEATHER_REQUEST_REPLAY_DOMAIN,
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
from services.agribrain.layer0.environment.weather.schemas import (
    WeatherDailyRecord,
    WeatherConsensusDaily,
    WeatherTimeSeries,
)
from services.agribrain.layer0.environment.weather.open_meteo import normalize_open_meteo_daily
from services.agribrain.layer0.environment.weather.openweather import normalize_openweather_daily
from services.agribrain.layer0.environment.weather.consensus import build_daily_consensus
from services.agribrain.layer0.environment.packetizer import emit_environment_packets
from services.agribrain.layer0.observation_packet import ObservationPacket, ObservationSource
from services.agribrain.layer0.wrappers import ensure_observation_packet, wrap_environment, _canonical_weather_records
from services.agribrain.layer05_asmae.history.weather_archive_adapter import _normalize_record


OPEN_METEO_REANALYSIS_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_HISTORICAL_FORECAST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
OPENWEATHER_ONECALL_3_URL = "https://api.openweathermap.org/data/3.0/onecall"
OPENWEATHER_CURRENT_2_5_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_TIMEMACHINE_3_URL = "https://api.openweathermap.org/data/3.0/onecall/timemachine"
OPENWEATHER_DISCONTINUED_2_5_URL = "https://api.openweathermap.org/data/2.5/onecall"

FIXED_TIME = datetime(2026, 11, 4, 2, 30, tzinfo=timezone.utc)

SAMPLE_OPEN_METEO_PAYLOAD = {
    "latitude": 45.0,
    "longitude": 10.0,
    "generationtime_ms": 1.23,
    "utc_offset_seconds": 0,
    "timezone": "UTC",
    "timezone_abbreviation": "UTC",
    "elevation": 50.0,
    "daily_units": {
        "time": "iso8601",
        "temperature_2m_min": "°C",
        "temperature_2m_max": "°C",
        "temperature_2m_mean": "°C",
        "precipitation_sum": "mm",
        "rain_sum": "mm",
    },
    "daily": {
        "time": ["2026-11-01", "2026-11-02", "2026-11-03"],
        "temperature_2m_min": [5.2, 6.1, 4.8],
        "temperature_2m_max": [16.4, 17.2, 15.0],
        "temperature_2m_mean": [10.8, 11.6, 9.9],
        "precipitation_sum": [0.0, 3.4, 0.0],
        "rain_sum": [0.0, 3.4, 0.0],
    },
}

SAMPLE_OPENWEATHER_ONECALL_PAYLOAD = {
    "lat": 45.0,
    "lon": 10.0,
    "timezone": "UTC",
    "timezone_offset": 0,
    "daily": [
        {
            "dt": 1762214400,
            "temp": {"day": 12.0, "min": 5.0, "max": 16.0},
            "pressure": 1015,
            "humidity": 60,
            "rain": 0.0,
        },
    ],
}

SAMPLE_TIMEMACHINE_PAYLOAD = {
    "lat": 45.0,
    "lon": 10.0,
    "timezone": "UTC",
    "timezone_offset": 0,
    "data": [
        {
            "dt": 1762214400,
            "temp": 12.5,
            "pressure": 1013,
            "humidity": 65,
            "clouds": 20,
            "wind_speed": 3.5,
            "weather": [{"id": 800, "main": "Clear"}],
        }
    ],
}


def make_mock_response(
    payload: dict,
    endpoint: str,
    status_code: int = 200,
    history: list | None = None,
    method: str = "GET",
    query_params: dict | None = None,
    wire_url: str | None = None,
) -> SimpleNamespace:
    """Create a mock HTTP response simulating requests.Response with exact request URL."""
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if wire_url is None:
        query_str = f"?{urlencode(query_params)}" if query_params else ""
        req_url = f"{endpoint}{query_str}"
    else:
        req_url = wire_url

    req = SimpleNamespace(
        method=method,
        url=req_url,
        headers={"Accept": "application/json"},
    )
    return SimpleNamespace(
        status_code=status_code,
        url=req_url,
        content=body,
        headers={"Content-Type": "application/json", "x-request-id": "mock-req-weather-123"},
        request=req,
        history=history or [],
    )


# ============================================================================
# 1. Weather Product Registry & Endpoint Allowlists
# ============================================================================

def test_registry_approved_endpoints_and_roles():
    """Verify approved endpoints map to correct product IDs and authoritative roles."""
    spec_om = identify_weather_product(OPEN_METEO_REANALYSIS_URL, {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "temperature_2m_max",
    })
    assert spec_om.product_id == WeatherProductId.OPEN_METEO_HISTORICAL_REANALYSIS
    assert spec_om.authoritative_role.value == "REANALYSIS_MODEL"
    assert spec_om.provider == WeatherProvider.OPEN_METEO

    spec_ow = identify_weather_product(OPENWEATHER_ONECALL_3_URL, {
        "lat": 45.0, "lon": 10.0,
    })
    assert spec_ow.product_id == WeatherProductId.OPENWEATHER_ONECALL_3_0
    assert spec_ow.authoritative_role.value == "FORECAST_MODEL"
    assert spec_ow.provider == WeatherProvider.OPENWEATHER


def test_registry_open_meteo_historical_forecast_host_delineation():
    """Verify Open-Meteo Historical Forecast API host is distinct from live forecast host."""
    spec_hist_fc = identify_weather_product(OPEN_METEO_HISTORICAL_FORECAST_URL, {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03",
    })
    assert spec_hist_fc.product_id == WeatherProductId.OPEN_METEO_HISTORICAL_FORECAST
    assert spec_hist_fc.authoritative_role.value == "HISTORICAL_FORECAST_MODEL"

    # Querying live forecast with historical dates fails closed
    with pytest.raises(WeatherRegistryError, match="live_forecast_endpoint_cannot_serve_historical_forecast"):
        identify_weather_product(OPEN_METEO_FORECAST_URL, {
            "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03",
        })


def test_registry_discontinued_endpoint_rejected_fail_closed():
    """Verify discontinued OpenWeather One Call 2.5 is rejected fail closed."""
    with pytest.raises(WeatherRegistryError, match="discontinued_or_forbidden_endpoint"):
        identify_weather_product(OPENWEATHER_DISCONTINUED_2_5_URL, {"lat": 45.0, "lon": 10.0})


def test_registry_insecure_scheme_rejected():
    """Verify non-HTTPS endpoints are rejected."""
    with pytest.raises(WeatherRegistryError, match="insecure_weather_endpoint_scheme"):
        identify_weather_product("http://archive-api.open-meteo.com/v1/archive", {"latitude": 45.0, "longitude": 10.0})


def test_registry_coordinate_validation():
    """Verify out-of-range coordinates are rejected."""
    spec = get_weather_product_spec(WeatherProductId.OPEN_METEO_HISTORICAL_REANALYSIS)
    with pytest.raises(WeatherRegistryError, match="invalid_latitude_range"):
        validate_weather_product_request(spec, "GET", {
            "latitude": 95.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "temp",
        })
    with pytest.raises(WeatherRegistryError, match="invalid_longitude_range"):
        validate_weather_product_request(spec, "GET", {
            "latitude": 45.0, "longitude": 190.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "temp",
        })


# ============================================================================
# 2. Endpoint Security & Wire-Request Parameter Binding
# ============================================================================

def test_endpoint_with_embedded_query_string_rejected(tmp_path):
    """Verify endpoints with embedded query strings or secrets fail closed before transmission."""
    store = NativeWeatherEvidenceStore(tmp_path)
    url_with_query = f"{OPENWEATHER_ONECALL_3_URL}?appid=secret_leak_123"
    resp = make_mock_response(SAMPLE_OPENWEATHER_ONECALL_PAYLOAD, url_with_query)

    with pytest.raises(NativeWeatherEvidenceError, match="endpoint_contains_embedded_query_string"):
        store.capture_http_response(
            response=resp,
            endpoint=url_with_query,
            query_params={"lat": 45.0, "lon": 10.0},
        )


def test_endpoint_with_userinfo_rejected(tmp_path):
    """Verify endpoints with embedded userinfo credentials fail closed."""
    store = NativeWeatherEvidenceStore(tmp_path)
    url_with_userinfo = "https://user:password@api.openweathermap.org/data/3.0/onecall"
    resp = make_mock_response(SAMPLE_OPENWEATHER_ONECALL_PAYLOAD, url_with_userinfo)

    with pytest.raises(NativeWeatherEvidenceError, match="endpoint_contains_embedded_userinfo_or_credentials"):
        store.capture_http_response(
            response=resp,
            endpoint=url_with_userinfo,
            query_params={"lat": 45.0, "lon": 10.0},
        )


def test_wire_request_mismatch_rejected(tmp_path):
    """Verify that mismatch between transmitted GET URL query and declared parameters fails closed."""
    store = NativeWeatherEvidenceStore(tmp_path)
    # The actual transmitted request was for latitude 10.0
    wire_params = {"latitude": 10.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "precipitation_sum"}
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL, query_params=wire_params)

    # Caller falsely claims acquisition was for latitude 45.0
    claimed_params = {"latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "precipitation_sum"}

    with pytest.raises(NativeWeatherEvidenceError, match="prepared provider request query differs from acquisition claim"):
        store.capture_http_response(
            response=resp,
            endpoint=OPEN_METEO_REANALYSIS_URL,
            query_params=claimed_params,
            retrieved_at=FIXED_TIME,
        )


def test_native_weather_capture_scrubs_api_keys(tmp_path):
    """Verify API keys and tokens in query parameters are completely scrubbed before hashing and storage."""
    store = NativeWeatherEvidenceStore(tmp_path)
    query_params_with_secret = {
        "lat": 45.0,
        "lon": 10.0,
        "appid": "secret_live_openweather_api_key_12345",
        "units": "metric",
    }
    resp = make_mock_response(
        SAMPLE_OPENWEATHER_ONECALL_PAYLOAD,
        OPENWEATHER_ONECALL_3_URL,
        query_params=query_params_with_secret,
    )

    receipt = store.capture_http_response(
        response=resp,
        endpoint=OPENWEATHER_ONECALL_3_URL,
        query_params=query_params_with_secret,
        credential_reference="env:OPENWEATHER_API_KEY",
        retrieved_at=FIXED_TIME,
    )

    assert isinstance(receipt, NativeWeatherAcquisitionReceipt)
    assert receipt.origin_class is OriginClass.LIVE_PROVIDER_AUTHENTICATED
    assert receipt.qualification_status == "NOT_QUALIFIED"
    assert receipt.provider_signature_verified is False
    assert receipt.authoritative_role == "FORECAST_MODEL"

    # Verify secret key is absent from canonical parameters in receipt
    assert "appid" not in receipt.canonical_query_params
    assert "secret_live_openweather_api_key_12345" not in json.dumps(receipt.canonical_query_params)

    # Verify secret key is absent from on-disk manifest
    manifest_bytes = store._path("manifests", receipt.acquisition_id).read_bytes()
    manifest_text = manifest_bytes.decode("utf-8")
    assert "appid" not in manifest_text
    assert "secret_live_openweather_api_key_12345" not in manifest_text

    # Verify secret key is absent from replayed request
    replayed = store.verified_request_params(receipt.acquisition_id)
    assert "appid" not in replayed


def test_native_weather_capture_rejects_embedded_credentials(tmp_path):
    """Verify parameters containing embedded tokens or secrets fail closed."""
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "precipitation_sum",
        "custom_header": "Bearer dangerous_secret_token_leak",
    }
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL, query_params=params)

    with pytest.raises(NativeWeatherEvidenceError, match="embedded credential detected"):
        store.capture_http_response(
            response=resp,
            endpoint=OPEN_METEO_REANALYSIS_URL,
            query_params=params,
            credential_reference="public",
            retrieved_at=FIXED_TIME,
        )


def test_native_weather_capture_rejects_http_redirects(tmp_path):
    """Verify that HTTP redirects are rejected fail-closed."""
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "precipitation_sum",
    }
    resp = make_mock_response(
        SAMPLE_OPEN_METEO_PAYLOAD,
        OPEN_METEO_REANALYSIS_URL,
        query_params=params,
        history=[SimpleNamespace(status_code=301, url="http://archive-api.open-meteo.com/v1/archive")],
    )

    with pytest.raises(NativeWeatherEvidenceError, match="HTTP redirects are prohibited"):
        store.capture_http_response(
            response=resp,
            endpoint=OPEN_METEO_REANALYSIS_URL,
            query_params=params,
            retrieved_at=FIXED_TIME,
        )


def test_native_weather_capture_rejects_non_200_status(tmp_path):
    """Verify non-200 HTTP responses fail closed."""
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "precipitation_sum",
    }
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL, query_params=params, status_code=500)

    with pytest.raises(NativeWeatherEvidenceError, match="requires HTTP 200"):
        store.capture_http_response(
            response=resp,
            endpoint=OPEN_METEO_REANALYSIS_URL,
            query_params=params,
            retrieved_at=FIXED_TIME,
        )


# ============================================================================
# 3. CAS Storage & Idempotency
# ============================================================================

def test_same_weather_capture_is_content_addressed_and_idempotent(tmp_path):
    """Verify identical captures produce identical acquisition IDs and CAS objects without duplication."""
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "precipitation_sum",
    }
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL, query_params=params)

    one = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)
    two = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    assert one.acquisition_id == two.acquisition_id
    assert one.response_sha256 == two.response_sha256
    assert len(list((tmp_path / "objects").rglob(one.response_sha256))) == 1


# ============================================================================
# 4. Cache Reverification Lineage Rule & Tamper Detection
# ============================================================================

def test_cache_reverification_never_promotes_weather_record_to_live(tmp_path):
    """Verify loading from cache returns PROVENANCE_VERIFIED_CACHE, never LIVE."""
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "precipitation_sum",
    }
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL, query_params=params)
    original = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)
    assert original.origin_class is OriginClass.LIVE_PROVIDER_AUTHENTICATED

    cached = store.verified_cache_receipt(original.acquisition_id)
    assert cached.origin_class is OriginClass.PROVENANCE_VERIFIED_CACHE
    assert cached.acquisition_id == original.acquisition_id
    assert cached.provider_signature_verified is False
    assert cached.qualification_status == "NOT_QUALIFIED"


def test_tampered_manifest_fails_closed(tmp_path):
    """Verify tampering with an on-disk manifest is detected and fails closed."""
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "precipitation_sum",
    }
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL, query_params=params)
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    manifest_path = store._path("manifests", receipt.acquisition_id)
    data = json.loads(manifest_path.read_text("utf-8"))
    data["authoritative_role"] = "UNAUTHORISED_PROMOTED_ROLE"
    manifest_path.write_text(json.dumps(data), "utf-8")

    with pytest.raises(NativeWeatherEvidenceError, match="tampered acquisition manifest digest"):
        store.verified_cache_receipt(receipt.acquisition_id)


def test_tampered_cas_object_fails_closed(tmp_path):
    """Verify modifying raw response bytes in CAS fails verification."""
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "precipitation_sum",
    }
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL, query_params=params)
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    obj_path = store._path("objects", receipt.object_id)
    obj_path.write_bytes(b"corrupted_tampered_weather_payload_bytes")

    with pytest.raises(NativeWeatherEvidenceError, match="CAS object bytes corrupted or altered"):
        store.verified_cache_receipt(receipt.acquisition_id)


# ============================================================================
# 5. Qualifier Screening, Anti-Substitution & Product Semantics
# ============================================================================

def test_screen_rejects_receipt_substitution(tmp_path):
    """Verify qualifier rejects forged receipt substituting Response B into Acquisition A."""
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum",
    }

    payload_a = dict(SAMPLE_OPEN_METEO_PAYLOAD)
    payload_b = dict(SAMPLE_OPEN_METEO_PAYLOAD)
    payload_b["daily"] = {
        "time": ["2026-11-01", "2026-11-02", "2026-11-03"],
        "temperature_2m_min": [9.0, 9.0, 9.0],
        "temperature_2m_max": [20.0, 20.0, 20.0],
        "precipitation_sum": [1.0, 2.0, 3.0],
    }

    resp_a = make_mock_response(payload_a, OPEN_METEO_REANALYSIS_URL, query_params=params)
    resp_b = make_mock_response(payload_b, OPEN_METEO_REANALYSIS_URL, query_params=params)

    receipt_a = store.capture_http_response(response=resp_a, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)
    receipt_b = store.capture_http_response(response=resp_b, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    # Adversarial substitution: construct receipt with A's ID and request fields, but B's response digest/object
    forged_receipt = NativeWeatherAcquisitionReceipt(
        acquisition_id=receipt_a.acquisition_id,
        origin_class=receipt_a.origin_class,
        provider=receipt_a.provider,
        product_id=receipt_a.product_id,
        endpoint=receipt_a.endpoint,
        request_sha256=receipt_a.request_sha256,
        response_sha256=receipt_b.response_sha256,
        response_bytes=receipt_b.response_bytes,
        object_id=receipt_b.object_id,
        retrieved_at=receipt_a.retrieved_at,
        provider_request_id=receipt_a.provider_request_id,
        credential_reference=receipt_a.credential_reference,
        http_status=receipt_a.http_status,
        coordinate_requested=receipt_a.coordinate_requested,
        valid_interval=receipt_a.valid_interval,
        authoritative_role=receipt_a.authoritative_role,
        canonical_query_params=receipt_a.canonical_query_params,
        qualification_status="NOT_QUALIFIED",
        provider_signature_verified=False,
    )

    screen = screen_native_weather_receipt(forged_receipt, store)
    assert screen.status is WeatherScreenStatus.REJECTED
    assert screen.reason == "acquisition_receipt_manifest_mismatch"


def test_screen_valid_open_meteo_receipt(tmp_path):
    """Verify valid Open-Meteo reanalysis capture screens successfully with deterministic proof hash."""
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum",
    }
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL, query_params=params)
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    screen = screen_native_weather_receipt(receipt, store)
    assert screen.status is WeatherScreenStatus.SCREENED_NATIVE_QA
    assert screen.reason == "qualified_native_weather_screen"
    assert screen.product_id == WeatherProductId.OPEN_METEO_HISTORICAL_REANALYSIS.value
    assert screen.authoritative_role == "REANALYSIS_MODEL"
    assert screen.proof_hash is not None and len(screen.proof_hash) == 64
    assert screen.diagnostic_metrics["dates_count"] == 3
    assert screen.diagnostic_metrics["zero_precipitation_days"] == 2
    assert screen.diagnostic_metrics["total_precipitation_mm"] == 3.4

    # Strict non-authorizing invariant checks
    assert screen.source_qualified is False
    assert screen.eligible_for_state_grant is False
    assert screen.scientific_publication_authorized is False


def test_screen_rejects_missing_daily_time_series(tmp_path):
    """Verify historical reanalysis response without daily.time is rejected fail-closed."""
    store = NativeWeatherEvidenceStore(tmp_path)
    payload_no_dates = {
        "latitude": 45.0,
        "longitude": 10.0,
        "daily": {"time": []},  # Empty date array
    }
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "precipitation_sum",
    }
    resp = make_mock_response(payload_no_dates, OPEN_METEO_REANALYSIS_URL, query_params=params)
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    screen = screen_native_weather_receipt(receipt, store)
    assert screen.status is WeatherScreenStatus.REJECTED
    assert screen.reason == "missing_daily_time_series"


def test_screen_openweather_timemachine_reconciliation(tmp_path):
    """Verify OpenWeather Timemachine 3.0 validates dt timestamp and coordinates."""
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {"lat": 45.0, "lon": 10.0, "dt": 1762214400}
    resp = make_mock_response(SAMPLE_TIMEMACHINE_PAYLOAD, OPENWEATHER_TIMEMACHINE_3_URL, query_params=params)
    receipt = store.capture_http_response(response=resp, endpoint=OPENWEATHER_TIMEMACHINE_3_URL, query_params=params, retrieved_at=FIXED_TIME)

    screen = screen_native_weather_receipt(receipt, store)
    assert screen.status is WeatherScreenStatus.SCREENED_NATIVE_QA
    assert screen.product_id == WeatherProductId.OPENWEATHER_TIMEMACHINE_3_0.value
    assert screen.authoritative_role == "REANALYSIS_MODEL"


def test_screen_preserves_true_zero_precipitation(tmp_path):
    """Verify precipitation 0.0 is preserved as a true measured zero, not confused with missing data."""
    store = NativeWeatherEvidenceStore(tmp_path)
    payload = dict(SAMPLE_OPEN_METEO_PAYLOAD)
    payload["daily"] = {
        "time": ["2026-11-01", "2026-11-02"],
        "temperature_2m_min": [5.0, 5.0],
        "temperature_2m_max": [15.0, 15.0],
        "precipitation_sum": [0.0, 0.0],  # Completely dry period
    }
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-02", "daily": "precipitation_sum",
    }
    resp = make_mock_response(payload, OPEN_METEO_REANALYSIS_URL, query_params=params)
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    screen = screen_native_weather_receipt(receipt, store)
    assert screen.status is WeatherScreenStatus.SCREENED_NATIVE_QA
    assert screen.diagnostic_metrics["zero_precipitation_days"] == 2
    assert screen.diagnostic_metrics["total_precipitation_mm"] == 0.0


def test_screen_rejects_negative_precipitation(tmp_path):
    """Verify negative precipitation in provider response fails qualification."""
    store = NativeWeatherEvidenceStore(tmp_path)
    payload = dict(SAMPLE_OPEN_METEO_PAYLOAD)
    payload["daily"] = {
        "time": ["2026-11-01"],
        "temperature_2m_min": [5.0],
        "temperature_2m_max": [15.0],
        "precipitation_sum": [-1.5],  # Corrupt negative rainfall
    }
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-01", "daily": "precipitation_sum",
    }
    resp = make_mock_response(payload, OPEN_METEO_REANALYSIS_URL, query_params=params)
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    screen = screen_native_weather_receipt(receipt, store)
    assert screen.status is WeatherScreenStatus.REJECTED
    assert "invalid_precipitation_value" in screen.reason


def test_screen_rejects_spatial_coordinate_mismatch(tmp_path):
    """Verify spatial mismatch between requested coordinates and payload coordinates is rejected."""
    store = NativeWeatherEvidenceStore(tmp_path)
    payload = dict(SAMPLE_OPEN_METEO_PAYLOAD)
    payload["latitude"] = 48.0  # Provider returned coordinate far away from requested 45.0
    payload["longitude"] = 10.0
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "precipitation_sum",
    }
    resp = make_mock_response(payload, OPEN_METEO_REANALYSIS_URL, query_params=params)
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    screen = screen_native_weather_receipt(receipt, store)
    assert screen.status is WeatherScreenStatus.REJECTED
    assert "weather_spatial_coordinate_mismatch" in screen.reason


def test_screen_rejects_temporal_range_mismatch(tmp_path):
    """Verify temporal mismatch between requested date range and returned dates is rejected."""
    store = NativeWeatherEvidenceStore(tmp_path)
    payload = dict(SAMPLE_OPEN_METEO_PAYLOAD)
    payload["daily"] = {
        "time": ["2026-11-01", "2026-11-02"],  # Missing 2026-11-03
        "temperature_2m_min": [5.0, 5.0],
        "temperature_2m_max": [15.0, 15.0],
        "precipitation_sum": [0.0, 0.0],
    }
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "precipitation_sum",
    }
    resp = make_mock_response(payload, OPEN_METEO_REANALYSIS_URL, query_params=params)
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    screen = screen_native_weather_receipt(receipt, store)
    assert screen.status is WeatherScreenStatus.REJECTED
    assert "weather_temporal_range_mismatch" in screen.reason


def test_cold_cache_receipt_qualification(tmp_path):
    """Verify cold cache receipt can be screened with identical deterministic results."""
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "precipitation_sum",
    }
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL, query_params=params)
    live_receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)
    cold_receipt = store.verified_cache_receipt(live_receipt.acquisition_id)

    screen_live = screen_native_weather_receipt(live_receipt, store)
    screen_cold = screen_native_weather_receipt(cold_receipt, store)

    assert screen_live.status is WeatherScreenStatus.SCREENED_NATIVE_QA
    assert screen_cold.status is WeatherScreenStatus.SCREENED_NATIVE_QA
    assert screen_live.proof_hash == screen_cold.proof_hash


# ============================================================================
# 6. End-to-End Downstream Evidence Lineage Binding
# ============================================================================

def test_downstream_end_to_end_acquisition_lineage(tmp_path, monkeypatch):
    """Verify native acquisition evidence IDs bind end-to-end from CAS through Layer 0 and ASMAE."""
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    store = NativeWeatherEvidenceStore(tmp_path)
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "precipitation_sum",
    }
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL, query_params=params)
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    # 1. Normalize records with authentic evidence_id
    records = normalize_open_meteo_daily(
        SAMPLE_OPEN_METEO_PAYLOAD,
        data_kind="historical_reanalysis",
        evidence_id=receipt.acquisition_id,
        evidence_domain=WEATHER_EVIDENCE_DOMAIN,
    )
    assert len(records) == 3
    for rec in records:
        assert rec.evidence_id == receipt.acquisition_id
        assert rec.evidence_domain == WEATHER_EVIDENCE_DOMAIN

    # 2. Consensus collects evidence_ids
    consensus_day = build_daily_consensus(
        date="2026-11-01",
        records_by_provider={"open_meteo": records[0]},
    )
    assert consensus_day.evidence_ids == [receipt.acquisition_id]

    # 3. Packetizer propagates consensus acquisition IDs into packet payload
    packets = emit_environment_packets(
        weather_consensus=[consensus_day],
        weather_timeseries=WeatherTimeSeries(daily_records=records, providers=["open_meteo"]),
    )
    consensus_pkt = next(p for p in packets if p["packet_type"] == "WEATHER_CONSENSUS_DAILY")
    assert consensus_pkt["payload"]["evidence_ids"] == [receipt.acquisition_id]
    assert consensus_pkt["payload"]["native_evidence_id"] == receipt.acquisition_id

    # 4. Layer 0 wrappers wrap packet into ObservationPacket and preserve acquisition_ids
    obs_packet = ensure_observation_packet(
        consensus_pkt,
        source=ObservationSource.WEATHER_REANALYSIS,
        plot_id="plot-1",
        geometry_hash="geom-1",
        geometry_version=1,
    )
    assert obs_packet.provenance.native_evidence_id == receipt.acquisition_id
    assert obs_packet.provenance.acquisition_ids == [receipt.acquisition_id]

    # 5. Canonical weather records retain native_acquisition_ids
    env_pkg = SimpleNamespace(
        weather_consensus=[consensus_day],
        forecast_consensus=[],
        packets=[consensus_pkt],
        plot_id="plot-1",
        timestamp_window={"window_end": "2026-11-03T00:00:00Z"},
        soilgrids_profile=None,
        fao_context=None,
        weak_kalman_observations=[],
        process_forcing=[],
        diagnostics={},
        provenance={},
        qa=None,
    )
    canonical_rows = _canonical_weather_records(env_pkg, [obs_packet])
    assert len(canonical_rows) == 1
    assert canonical_rows[0]["native_acquisition_ids"] == [receipt.acquisition_id]

    # 6. ASMAE weather archive adapter preserves verified native evidence_ids
    normalized_asmae = _normalize_record(canonical_rows[0])
    assert normalized_asmae is not None
    assert normalized_asmae["evidence_ids"] == [receipt.acquisition_id]


def test_forged_downstream_acquisition_id_fails_verification(tmp_path):
    """Verify an uncaptured/forged acquisition ID cannot be verified in CAS."""
    store = NativeWeatherEvidenceStore(tmp_path)
    forged_id = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    with pytest.raises(NativeWeatherEvidenceError, match="manifest not found for acquisition"):
        store.verified_cache_receipt(forged_id)
