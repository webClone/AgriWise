"""B2B-04B Native Weather Provider HTTP Capture and CAS Binding Regression Tests.

Verifies:
1. Immutable Weather Product Registry and endpoint allowlists.
2. Credential scrubbing (API keys, tokens, secrets stripped before hashing or CAS storage).
3. Redirect prohibition and strict HTTPS enforcement.
4. Atomic Content-Addressed Store (CAS) byte retention and manifest verification.
5. Cache reverification returning PROVENANCE_VERIFIED_CACHE, never self-promoting to LIVE.
6. Weather Product Qualifier spatial, temporal, product, and true zero precipitation screening.
7. Non-authorizing invariant: source_qualified=False, eligible_for_state_grant=False.
8. Downstream evidence binding to WeatherDailyRecord, ObservationPacket, and consensus.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
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
)
from services.agribrain.layer0.environment.weather.open_meteo import normalize_open_meteo_daily
from services.agribrain.layer0.environment.weather.openweather import normalize_openweather_daily
from services.agribrain.layer0.environment.weather.consensus import build_daily_consensus
from services.agribrain.layer0.observation_packet import ObservationPacket, ObservationSource
from services.agribrain.layer0.wrappers import ensure_observation_packet


OPEN_METEO_REANALYSIS_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPENWEATHER_ONECALL_3_URL = "https://api.openweathermap.org/data/3.0/onecall"
OPENWEATHER_CURRENT_2_5_URL = "https://api.openweathermap.org/data/2.5/weather"
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
        "precipitation_sum": "mm",
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


def make_mock_response(
    payload: dict,
    endpoint: str,
    status_code: int = 200,
    history: list | None = None,
    method: str = "GET",
) -> SimpleNamespace:
    """Create a mock HTTP response simulating requests.Response."""
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = SimpleNamespace(
        method=method,
        url=endpoint,
        headers={"Accept": "application/json"},
    )
    return SimpleNamespace(
        status_code=status_code,
        url=endpoint,
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
# 2. Native HTTP Capture & Credential Scrubbing
# ============================================================================

def test_native_weather_capture_scrubs_api_keys(tmp_path):
    """Verify API keys and tokens in query parameters are completely scrubbed before hashing and storage."""
    store = NativeWeatherEvidenceStore(tmp_path)
    resp = make_mock_response(SAMPLE_OPENWEATHER_ONECALL_PAYLOAD, OPENWEATHER_ONECALL_3_URL)

    query_params_with_secret = {
        "lat": 45.0,
        "lon": 10.0,
        "appid": "secret_live_openweather_api_key_12345",
        "units": "metric",
    }

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
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL)

    with pytest.raises(NativeWeatherEvidenceError, match="embedded credential detected"):
        store.capture_http_response(
            response=resp,
            endpoint=OPEN_METEO_REANALYSIS_URL,
            query_params={
                "latitude": 45.0,
                "longitude": 10.0,
                "start_date": "2026-11-01",
                "end_date": "2026-11-03",
                "daily": "precipitation_sum",
                "custom_header": "Bearer dangerous_secret_token_leak",
            },
            credential_reference="public",
            retrieved_at=FIXED_TIME,
        )


def test_native_weather_capture_rejects_http_redirects(tmp_path):
    """Verify that HTTP redirects are rejected fail-closed."""
    store = NativeWeatherEvidenceStore(tmp_path)
    resp = make_mock_response(
        SAMPLE_OPEN_METEO_PAYLOAD,
        OPEN_METEO_REANALYSIS_URL,
        history=[SimpleNamespace(status_code=301, url="http://archive-api.open-meteo.com/v1/archive")],
    )

    with pytest.raises(NativeWeatherEvidenceError, match="HTTP redirects are prohibited"):
        store.capture_http_response(
            response=resp,
            endpoint=OPEN_METEO_REANALYSIS_URL,
            query_params={
                "latitude": 45.0,
                "longitude": 10.0,
                "start_date": "2026-11-01",
                "end_date": "2026-11-03",
                "daily": "precipitation_sum",
            },
            retrieved_at=FIXED_TIME,
        )


def test_native_weather_capture_rejects_non_200_status(tmp_path):
    """Verify non-200 HTTP responses fail closed."""
    store = NativeWeatherEvidenceStore(tmp_path)
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL, status_code=500)

    with pytest.raises(NativeWeatherEvidenceError, match="requires HTTP 200"):
        store.capture_http_response(
            response=resp,
            endpoint=OPEN_METEO_REANALYSIS_URL,
            query_params={
                "latitude": 45.0,
                "longitude": 10.0,
                "start_date": "2026-11-01",
                "end_date": "2026-11-03",
                "daily": "precipitation_sum",
            },
            retrieved_at=FIXED_TIME,
        )


# ============================================================================
# 3. CAS Storage & Idempotency
# ============================================================================

def test_same_weather_capture_is_content_addressed_and_idempotent(tmp_path):
    """Verify identical captures produce identical acquisition IDs and CAS objects without duplication."""
    store = NativeWeatherEvidenceStore(tmp_path)
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "precipitation_sum",
    }

    one = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)
    two = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    assert one.acquisition_id == two.acquisition_id
    assert one.response_sha256 == two.response_sha256
    assert len(list((tmp_path / "objects").rglob(one.response_sha256))) == 1


# ============================================================================
# 4. Cache Reverification Lineage Rule
# ============================================================================

def test_cache_reverification_never_promotes_weather_record_to_live(tmp_path):
    """Verify loading from cache returns PROVENANCE_VERIFIED_CACHE, never LIVE."""
    store = NativeWeatherEvidenceStore(tmp_path)
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "precipitation_sum",
    }
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
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "precipitation_sum",
    }
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
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "precipitation_sum",
    }
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    obj_path = store._path("objects", receipt.object_id)
    obj_path.write_bytes(b"corrupted_tampered_weather_payload_bytes")

    with pytest.raises(NativeWeatherEvidenceError, match="CAS object bytes corrupted or altered"):
        store.verified_cache_receipt(receipt.acquisition_id)


# ============================================================================
# 5. Weather Product Qualifier Screening
# ============================================================================

def test_screen_valid_open_meteo_receipt(tmp_path):
    """Verify valid Open-Meteo reanalysis capture screens successfully with deterministic proof hash."""
    store = NativeWeatherEvidenceStore(tmp_path)
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL)
    params = {
        "latitude": 45.0,
        "longitude": 10.0,
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
        "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum",
    }
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
    resp = make_mock_response(payload, OPEN_METEO_REANALYSIS_URL)
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-02", "daily": "precipitation_sum",
    }
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
    resp = make_mock_response(payload, OPEN_METEO_REANALYSIS_URL)
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-01", "daily": "precipitation_sum",
    }
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
    resp = make_mock_response(payload, OPEN_METEO_REANALYSIS_URL)
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "precipitation_sum",
    }
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
    resp = make_mock_response(payload, OPEN_METEO_REANALYSIS_URL)
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "precipitation_sum",
    }
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    screen = screen_native_weather_receipt(receipt, store)
    assert screen.status is WeatherScreenStatus.REJECTED
    assert "weather_temporal_range_mismatch" in screen.reason


def test_cold_cache_receipt_qualification(tmp_path):
    """Verify cold cache receipt can be screened with identical deterministic results."""
    store = NativeWeatherEvidenceStore(tmp_path)
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL)
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "precipitation_sum",
    }
    live_receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)
    cold_receipt = store.verified_cache_receipt(live_receipt.acquisition_id)

    screen_live = screen_native_weather_receipt(live_receipt, store)
    screen_cold = screen_native_weather_receipt(cold_receipt, store)

    assert screen_live.status is WeatherScreenStatus.SCREENED_NATIVE_QA
    assert screen_cold.status is WeatherScreenStatus.SCREENED_NATIVE_QA
    assert screen_live.proof_hash == screen_cold.proof_hash


# ============================================================================
# 6. Downstream Evidence Binding
# ============================================================================

def test_evidence_id_propagates_into_weather_daily_records_and_consensus(tmp_path):
    """Verify native acquisition evidence IDs bind into normalized records and consensus."""
    store = NativeWeatherEvidenceStore(tmp_path)
    resp = make_mock_response(SAMPLE_OPEN_METEO_PAYLOAD, OPEN_METEO_REANALYSIS_URL)
    params = {
        "latitude": 45.0, "longitude": 10.0, "start_date": "2026-11-01", "end_date": "2026-11-03", "daily": "precipitation_sum",
    }
    receipt = store.capture_http_response(response=resp, endpoint=OPEN_METEO_REANALYSIS_URL, query_params=params, retrieved_at=FIXED_TIME)

    # Normalize with evidence_id
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
        assert rec.source_role == "REANALYSIS_MODEL"
        assert rec.source_qualified is False

    # Consensus collects evidence_ids
    consensus = build_daily_consensus(
        date="2026-11-01",
        records_by_provider={"open_meteo": records[0]},
    )
    assert consensus.source_role == "REANALYSIS_MODEL"
    assert consensus.source_qualified is False
    assert consensus.evidence_ids == [receipt.acquisition_id]


def test_evidence_id_binds_into_observation_packet_provenance():
    """Verify evidence_id in weather record propagates into ObservationPacket.provenance."""
    rec = WeatherDailyRecord(
        date="2026-11-01",
        provider="open_meteo",
        data_kind="historical_reanalysis",
        source_role="REANALYSIS_MODEL",
        source_qualified=False,
        evidence_id="weather-test-acquisition-id-12345",
        temp_mean=12.5,
    )

    payload = {
        "date": rec.date,
        "provider": rec.provider,
        "data_kind": rec.data_kind,
        "source_role": rec.source_role,
        "evidence_id": rec.evidence_id,
        "temp_mean": rec.temp_mean,
    }

    packet = ensure_observation_packet(
        payload,
        plot_id="plot-test-1",
        geometry_hash="geom-hash-1",
        geometry_version=1,
        source=ObservationSource.WEATHER_REANALYSIS,
    )

    assert isinstance(packet, ObservationPacket)
    assert packet.provenance.native_evidence_id == "weather-test-acquisition-id-12345"
    assert packet.provenance.native_evidence_domain == WEATHER_EVIDENCE_DOMAIN
