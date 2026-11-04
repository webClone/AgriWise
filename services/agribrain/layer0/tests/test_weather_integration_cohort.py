"""B2B-04B integration completion: actual registered capture to ASMAE archive.

Tests use a fully prepared requests.Request (no provider network). Only CAS
retrieval can furnish weather provenance. All authority flags remain false.
"""
import copy
import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
import requests

from services.agribrain.layer0.data_gateway.fetch_registry import get_fetch_fn
from services.agribrain.layer0.environment.engine import EnvironmentalEngine
from services.agribrain.layer0.native_issuer.weather_acquisition_evidence import (
    NativeWeatherEvidenceError, NativeWeatherEvidenceStore,
)
from services.agribrain.layer0.native_issuer.weather_acquisition_boundary import (
    execute_and_capture_weather_get,
)
from services.agribrain.layer0.native_issuer.weather_qualifier import (
    screen_native_weather_receipt, WeatherScreenStatus,
)
from services.agribrain.layer0.environment.weather.source_roles import (
    classify_weather_record_admission,
)
from services.agribrain.layer0.environment.weather.derived import (
    compute_daily_forcing,
)
from services.agribrain.layer0.environment.weather.schemas import WeatherConsensusDaily
from services.agribrain.layer0.wrappers import wrap_environment
from services.agribrain.layer05_asmae.history.weather_archive_adapter import (
    normalize_weather_archive,
)


ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"


def payload():
    return {
        "latitude": 35.0,
        "longitude": 3.0,
        "timezone": "UTC",
        "daily_units": {
            "time": "iso8601",
            "temperature_2m_min": "°C",
            "temperature_2m_max": "°C",
            "precipitation_sum": "mm",
            "et0_fao_evapotranspiration": "mm",
        },
        "daily": {
            "time": ["2026-11-01", "2026-11-02", "2026-11-03"],
            "temperature_2m_min": [5.0, 5.0, 6.0],
            "temperature_2m_max": [15.0, 15.0, 16.0],
            "precipitation_sum": [0.0, 3.5, 0.0],
            "et0_fao_evapotranspiration": [2.0, 2.0, 2.1],
        },
    }


def params():
    return {
        "latitude": 35.0, "longitude": 3.0,
        "start_date": "2026-11-01", "end_date": "2026-11-03",
        "daily": "precipitation_sum", "timezone": "UTC",
    }


def wire_response(data=None, query=None, endpoint=ENDPOINT, request_scheme=None, response_scheme=None):
    query = params() if query is None else query
    prepared = requests.Request("GET", endpoint, params=query).prepare()
    if request_scheme:
        prepared.url = prepared.url.replace("https://", request_scheme + "://", 1)
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(payload() if data is None else data).encode()
    response.url = prepared.url.replace(
        (request_scheme or "https") + "://", response_scheme + "://", 1
    ) if response_scheme else prepared.url
    response.request = prepared
    response.headers["Content-Type"] = "application/json"
    return response


def capture(store, data=None, query=None):
    q = params() if query is None else query
    return store.capture_http_response(
        response=wire_response(data, q), endpoint=ENDPOINT, query_params=q,
    )


def test_registered_weather_gateway_to_archive_native_lineage(monkeypatch, tmp_path):
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    captured = []
    def fake_get(url, params, headers, timeout, allow_redirects):
        assert url == ENDPOINT
        assert allow_redirects is False
        assert params["temperature_unit"] == "celsius"
        assert params["precipitation_unit"] == "mm"
        assert params["wind_speed_unit"] == "ms"
        captured.append(1)
        return wire_response(payload(), params)
    monkeypatch.setattr(requests, "get", fake_get)

    # The actual fetch registry entry is the application's broker dispatch target.
    result = get_fetch_fn("open_meteo_archive")(
        35.0, 3.0, start_date="2026-11-01", end_date="2026-11-03",
    )
    assert captured == [1]
    assert result["native_capture_status"] == "screened_native_qa"
    acquisition_id = result["native_acquisition_id"]

    store = NativeWeatherEvidenceStore(tmp_path)
    assert store.verified_cache_receipt(acquisition_id).response_sha256
    env = EnvironmentalEngine().process(
        latitude=35.0, longitude=3.0, plot_id="weather-test",
        open_meteo_data=result, expected_dates=payload()["daily"]["time"],
    )
    assert len(env.weather_timeseries.daily_records) == 3
    assert {r.evidence_id for r in env.weather_timeseries.daily_records} == {acquisition_id}
    assert [r.precipitation_sum for r in env.weather_timeseries.daily_records] == [0.0, 3.5, 0.0]
    assert any(p.precipitation_mm == 0.0 for p in env.process_forcing)
    package = wrap_environment(env)
    archive = normalize_weather_archive(package)
    assert archive["weather_archive_status"] == "available"
    assert acquisition_id in archive["weather_evidence_ids"]
    assert archive["weather_daily_series"]["2026-11-01"]["precipitation_mm"] == 0.0


def test_native_bundle_payload_substitution_fails_before_normalization(monkeypatch, tmp_path):
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    store = NativeWeatherEvidenceStore(tmp_path)
    rec = capture(store)
    altered = payload()
    altered["daily"]["precipitation_sum"][0] = 50.0
    from services.agribrain.layer0.native_issuer.weather_native_pipeline import resolve_verified_open_meteo_payload
    with pytest.raises(NativeWeatherEvidenceError, match="native_weather_cached_payload_mismatch"):
        resolve_verified_open_meteo_payload({
            "native_capture_status": "screened_native_qa",
            "native_acquisition_id": rec.acquisition_id,
            "native_product_id": rec.product_id,
            "native_payload": altered,
        }, latitude=35.0, longitude=3.0)


@pytest.mark.parametrize("carrier", [
    {"data_role": "FORECAST_MODEL"},
    {"role": "EXCLUDED"},
    {"payload": {"source_role": "FORECAST_MODEL"}},
    {"payload": {"role": "EXCLUDED"}},
])
def test_conflicting_alias_never_enters_historical_archive(carrier):
    row = {
        "date": "2026-11-01", "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL", "precipitation_mm": 0.0,
        "temp_min_c": 5.0, "temp_max_c": 15.0, "et0_mm": 2.0,
    }
    row.update(carrier)
    assert classify_weather_record_admission(row) not in ("reanalysis_archive",)
    archive = normalize_weather_archive([row])
    assert not archive["weather_daily_series"]


def test_invalid_calendar_day_never_archived():
    row = {
        "date": "2026-99-99", "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL", "precipitation_mm": 0.0,
    }
    assert classify_weather_record_admission(row) == "rejected"
    assert normalize_weather_archive([row])["weather_daily_series"] == {}


@pytest.mark.parametrize("mutation,expected", [
    (lambda p: p["daily_units"].update(precipitation_sum="inch"), "unsupported_or_mismatched_weather_unit"),
    (lambda p: p["daily"].update(precipitation_sum=[None, None, None]), "weather_requested_variable_unavailable"),
    (lambda p: p["daily"].update(precipitation_sum=[False, 1.0, 2.0]), "boolean_weather_measurement"),
    (lambda p: p["daily"].update(temperature_2m_min=["bad", 5, 6]), "non_numeric_weather_measurement"),
    (lambda p: p.update(latitude="NaN"), "non_finite_response_coordinates"),
    (lambda p: p.update(longitude=None), "missing_response_coordinates"),
    (lambda p: p["daily"].update(time=["2026-11-01", "2026-11-03"]), "weather_daily_interior_date_gap"),
    (lambda p: p["daily"].update(time=["2026-11-01", "2026-11-03", "2026-11-04"]), "weather_daily_interior_date_gap"),
    (lambda p: p["daily"].update(precipitation_sum=[0.0, 3.5]), "weather_daily_variable_support_mismatch"),
    (lambda p: p["daily"].update(time=["2026-11-03", "2026-11-02", "2026-11-01"]), "weather_daily_dates_not_sorted_unique"),
])
def test_native_screen_refuses_unsupported_science(mutation, expected, tmp_path):
    p = payload()
    mutation(p)
    store = NativeWeatherEvidenceStore(tmp_path)
    receipt = capture(store, data=p)
    result = screen_native_weather_receipt(receipt, store)
    assert result.status is WeatherScreenStatus.REJECTED
    assert result.reason == expected


@pytest.mark.parametrize("request_scheme,response_scheme", [
    ("http", "http"), (None, "http"), ("http", None),
])
def test_http_repr_never_gets_authenticated_origin(tmp_path, request_scheme, response_scheme):
    store = NativeWeatherEvidenceStore(tmp_path)
    with pytest.raises(NativeWeatherEvidenceError):
        store.capture_http_response(
            response=wire_response(request_scheme=request_scheme, response_scheme=response_scheme),
            endpoint=ENDPOINT, query_params=params(),
        )


def test_provider_exception_message_never_exposes_api_key(monkeypatch, tmp_path):
    def fake_get(*args, **kwargs):
        raise requests.ConnectionError("https://api.openweathermap.org/data/3.0/onecall?appid=SECRET_IN_ERROR")
    monkeypatch.setattr(requests, "get", fake_get)
    with pytest.raises(NativeWeatherEvidenceError) as exc:
        execute_and_capture_weather_get(
            endpoint=ENDPOINT, params=params(), store=NativeWeatherEvidenceStore(tmp_path),
        )
    assert str(exc.value) == "weather_network_request_failed"
    assert "SECRET_IN_ERROR" not in str(exc.value)


def test_missing_precipitation_cannot_generate_zero_rain_forcing():
    with pytest.raises(ValueError, match="weather_precipitation_unavailable_for_process_forcing"):
        compute_daily_forcing(WeatherConsensusDaily(date="2026-11-01"))


def test_broker_revalidates_stale_legacy_cache_against_native_cas(monkeypatch, tmp_path):
    """Normal DataRequestBroker.get must not return a stale unattributed weather cache."""
    from services.agribrain.layer0.data_gateway.request_broker import DataRequestBroker
    from services.agribrain.layer0.data_gateway import request_broker

    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    captured = []
    def fake_get(url, params, headers, timeout, allow_redirects):
        captured.append(1)
        return wire_response(payload(), params)
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(request_broker.external_provider_circuit, "before_request", lambda source: None)
    monkeypatch.setattr(request_broker.external_provider_circuit, "record_success", lambda source: None)

    class Cache:
        calls = []
        result = {"daily": payload()["daily"], "native_capture_status": "unattested_legacy"}
        def get_or_fetch(self, *, source, plot_id, lat, lng, fetch_fn,
                         force_refresh=False, context=None, param_hash="",
                         candidate_validator=None):
            self.calls.append(force_refresh)
            if force_refresh:
                updated = fetch_fn(lat, lng)
                if candidate_validator and not candidate_validator(updated):
                    return None
                self.result = updated
            return self.result

    broker = DataRequestBroker.__new__(DataRequestBroker)
    broker._storage = Cache()
    broker._consolidator = SimpleNamespace(should_consolidate=lambda src: False)
    result = broker.get(
        "open_meteo_archive", "weather-plot", 35.0, 3.0,
        start_date="2026-11-01", end_date="2026-11-03",
    )
    assert broker._storage.calls == [False, True]
    assert captured == [1]
    assert result["native_capture_status"] == "screened_native_qa"
    # A later normal cache read must verify CAS and must not re-fetch.
    cached = broker.get(
        "open_meteo_archive", "weather-plot", 35.0, 3.0,
        start_date="2026-11-01", end_date="2026-11-03",
    )
    assert cached["native_acquisition_id"] == result["native_acquisition_id"]
    assert captured == [1]


def test_requested_noncanonical_units_are_rejected(tmp_path):
    store = NativeWeatherEvidenceStore(tmp_path)
    q = params()
    q["precipitation_unit"] = "inch"
    p = payload()
    receipt = capture(store, p, q)
    screen = screen_native_weather_receipt(receipt, store)
    assert screen.status is WeatherScreenStatus.REJECTED
    assert screen.reason == "unsupported_requested_weather_units"


def test_broker_consolidation_isolates_different_date_windows(monkeypatch, tmp_path):
    """W4-06 counterexample: Same coordinates with different date windows must not cross-consolidate."""
    from services.agribrain.layer0.data_gateway.request_broker import DataRequestBroker
    from services.agribrain.layer0.data_gateway.request_consolidator import RequestConsolidator

    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    requests_log = []

    def fake_get(url, params, headers, timeout, allow_redirects):
        requests_log.append(params["start_date"])
        p = payload()
        p["daily"]["time"] = [params["start_date"]]
        p["daily"]["precipitation_sum"] = [1.0]
        p["daily"]["temperature_2m_min"] = [5.0]
        p["daily"]["temperature_2m_max"] = [15.0]
        p["daily"]["et0_fao_evapotranspiration"] = [2.0]
        return wire_response(p, params)

    monkeypatch.setattr(requests, "get", fake_get)

    broker = DataRequestBroker.__new__(DataRequestBroker)
    broker._storage = SimpleNamespace(
        get_or_fetch=lambda *, source, plot_id, lat, lng, fetch_fn, force_refresh=False,
                            context=None, param_hash="", candidate_validator=None: fetch_fn(lat, lng),
        get_cached_evidence=lambda *a, **k: None,
    )
    broker._consolidator = RequestConsolidator(ttl_seconds=300)

    # Plot 1: Nov 1 to Nov 1
    res1 = broker.get(
        "open_meteo_archive", "plot-1", 35.0, 3.0,
        start_date="2026-11-01", end_date="2026-11-01",
    )
    # Plot 2: Nov 5 to Nov 5 (within 5km snap, but different date window)
    res2 = broker.get(
        "open_meteo_archive", "plot-2", 35.0001, 3.0001,
        start_date="2026-11-05", end_date="2026-11-05",
    )

    assert requests_log == ["2026-11-01", "2026-11-05"]
    assert res1["native_acquisition_id"] != res2["native_acquisition_id"]
    assert res1["native_payload"]["daily"]["time"] == ["2026-11-01"]
    assert res2["native_payload"]["daily"]["time"] == ["2026-11-05"]


def test_broker_strict_native_rejects_legacy_cache_hit_without_root(monkeypatch):
    """W4-07 counterexample: Strict mode rejects legacy cache hit when evidence root is missing."""
    from services.agribrain.layer0.data_gateway.request_broker import DataRequestBroker

    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "1")
    monkeypatch.delenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", raising=False)
    monkeypatch.delenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", raising=False)

    class LegacyCache:
        def get_or_fetch(self, *, source, plot_id, lat, lng, fetch_fn,
                         force_refresh=False, context=None, param_hash="",
                         candidate_validator=None):
            # Returns a cached legacy result without native acquisition proof
            return {"daily": payload()["daily"], "native_capture_status": "unattested_legacy"}

    broker = DataRequestBroker.__new__(DataRequestBroker)
    broker._storage = LegacyCache()
    broker._consolidator = SimpleNamespace(should_consolidate=lambda src: False)

    result = broker.get(
        "open_meteo_archive", "weather-plot", 35.0, 3.0,
        start_date="2026-11-01", end_date="2026-11-03",
    )
    # In strict-native mode, legacy cache output must be rejected
    assert result is None


def test_environmental_engine_strict_native_rejects_unattested_weather(monkeypatch):
    """W4-08 counterexample: Strict mode rejects raw unverified weather dictionaries at engine ingestion."""
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "1")

    # Plain open_meteo payload with NO native acquisition evidence fields
    raw_unattested = payload()

    env = EnvironmentalEngine().process(
        latitude=35.0, longitude=3.0, plot_id="unattested-plot",
        open_meteo_data=raw_unattested,
    )
    # Daily weather records must be empty (quarantined/rejected)
    assert len(env.weather_timeseries.daily_records) == 0
    failures = env.diagnostics.get("provider_failures", [])
    assert any(
        f.get("error") == "unattested_weather_input_rejected_in_strict_native_mode"
        for f in failures
    )


def test_asmae_normalization_rejects_arbitrary_acquisition_id(monkeypatch, tmp_path):
    """W4-09 counterexample: Arbitrary acquisition ID must not be labeled or exported as verified native evidence."""
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))

    forged_id = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    forged_record = {
        "date": "2026-11-01",
        "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL",
        "native_acquisition_ids": [forged_id],
        "evidence_ids": [forged_id],
        "precipitation_mm": 0.0,
        "temp_min_c": 5.0,
        "temp_max_c": 15.0,
        "et0_mm": 2.0,
    }

    archive = normalize_weather_archive([forged_record])
    assert forged_id not in archive.get("weather_native_evidence_ids", [])
    assert forged_id not in archive.get("weather_evidence_ids", [])
    assert archive.get("native_evidence_verified") is False



def test_asmae_normalization_rejects_altered_precipitation_with_valid_receipt(monkeypatch, tmp_path):
    """W4-09B: Valid CAS receipt cannot verify a record with altered precipitation."""
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    store = NativeWeatherEvidenceStore(tmp_path)
    receipt = capture(store)

    # Valid CAS receipt covers 2026-11-01 with precipitation 0.0, but record claims 999.0 mm
    altered_record = {
        "date": "2026-11-01",
        "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL",
        "native_acquisition_ids": [receipt.acquisition_id],
        "precipitation_mm": 999.0,
        "temp_min_c": 5.0,
        "temp_max_c": 15.0,
        "et0_mm": 2.0,
    }

    archive = normalize_weather_archive([altered_record])
    assert receipt.acquisition_id not in archive.get("weather_native_evidence_ids", [])
    assert archive.get("native_evidence_verified") is False


def test_asmae_normalization_rejects_mismatched_date_with_valid_receipt(monkeypatch, tmp_path):
    """W4-09B: Valid CAS receipt cannot verify a record for a date outside its interval."""
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    store = NativeWeatherEvidenceStore(tmp_path)
    q = params()
    q["start_date"] = "2026-11-01"
    q["end_date"] = "2026-11-01"
    p = payload()
    p["daily"]["time"] = ["2026-11-01"]
    p["daily"]["precipitation_sum"] = [0.0]
    p["daily"]["temperature_2m_min"] = [5.0]
    p["daily"]["temperature_2m_max"] = [15.0]
    p["daily"]["et0_fao_evapotranspiration"] = [2.0]
    receipt = capture(store, data=p, query=q)

    # Valid CAS receipt covers ONLY 2026-11-01, but record claims 2026-11-02
    mismatched_date_record = {
        "date": "2026-11-02",
        "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL",
        "native_acquisition_ids": [receipt.acquisition_id],
        "precipitation_mm": 0.0,
        "temp_min_c": 5.0,
        "temp_max_c": 15.0,
        "et0_mm": 2.0,
    }

    archive = normalize_weather_archive([mismatched_date_record])
    assert receipt.acquisition_id not in archive.get("weather_native_evidence_ids", [])
    assert archive.get("native_evidence_verified") is False


def test_asmae_normalization_rejects_unrelated_receipt_substitution(monkeypatch, tmp_path):
    """W4-09B: Valid CAS receipt cannot verify an unrelated record with conflicting values."""
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    store = NativeWeatherEvidenceStore(tmp_path)
    receipt = capture(store)

    # Valid CAS receipt has temps 5.0 and 15.0, but unrelated record claims 25.0 and 35.0
    unrelated_record = {
        "date": "2026-11-01",
        "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL",
        "native_acquisition_ids": [receipt.acquisition_id],
        "precipitation_mm": 0.0,
        "temp_min_c": 25.0,
        "temp_max_c": 35.0,
        "et0_mm": 2.0,
    }

    archive = normalize_weather_archive([unrelated_record])
    assert receipt.acquisition_id not in archive.get("weather_native_evidence_ids", [])
    assert archive.get("native_evidence_verified") is False


def test_asmae_normalization_rejects_wrong_product_role_with_valid_receipt(monkeypatch, tmp_path):
    """W4-09B: Valid CAS receipt cannot verify a record asserting a contradictory role."""
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    store = NativeWeatherEvidenceStore(tmp_path)
    receipt = capture(store)  # OPEN_METEO_HISTORICAL_REANALYSIS

    # Record claims forecast reality/role with a historical reanalysis receipt
    wrong_role_record = {
        "date": "2026-11-01",
        "data_kind": "forecast",
        "source_role": "FORECAST_MODEL",
        "native_acquisition_ids": [receipt.acquisition_id],
        "precipitation_mm": 0.0,
        "temp_min_c": 5.0,
        "temp_max_c": 15.0,
        "et0_mm": 2.0,
    }

    archive = normalize_weather_archive([wrong_role_record])
    assert receipt.acquisition_id not in archive.get("weather_native_evidence_ids", [])
    assert archive.get("native_evidence_verified") is False



def test_w4_09c_partial_receipt_merged_with_fabricated_fields(monkeypatch, tmp_path):
    """W4-09C counterexample 1: A partial native record (only precipitation) merged
    with fabricated temperature values must NOT claim full native verification.

    Record A: precipitation_mm=0.0 with valid CAS receipt (no temp values).
    Record B: fabricated temp_min_c=25.0, temp_max_c=35.0 (no receipt).
    After merge, the combined record has both precip and temp, but the temps
    have no CAS backing -> native_evidence_verified must be False.
    """
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    store = NativeWeatherEvidenceStore(tmp_path)
    receipt = capture(store)  # CAS has precip=0.0, tmin=5.0, tmax=15.0, et0=2.0

    # Record A: only precipitation, matching CAS
    record_a = {
        "date": "2026-11-01",
        "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL",
        "native_acquisition_ids": [receipt.acquisition_id],
        "precipitation_mm": 0.0,
        "et0_mm": 2.0,
        # temp_min_c and temp_max_c deliberately omitted
    }

    # Record B: fabricated temperatures, no receipt
    record_b = {
        "date": "2026-11-01",
        "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL",
        "temp_min_c": 25.0,  # fabricated (CAS has 5.0)
        "temp_max_c": 35.0,  # fabricated (CAS has 15.0)
    }

    archive = normalize_weather_archive([record_a, record_b])
    day = archive["weather_daily_series"].get("2026-11-01")
    assert day is not None, "merged day must exist"
    # Merged record has all four variables
    assert day["precipitation_mm"] == 0.0
    assert day["et0_mm"] == 2.0
    assert day["temp_min_c"] == 25.0
    assert day["temp_max_c"] == 35.0
    # But the fabricated temps have no CAS backing
    var_ev = day.get("variable_evidence", {})
    assert receipt.acquisition_id in var_ev.get("precipitation_mm", [])
    assert receipt.acquisition_id in var_ev.get("et0_mm", [])
    assert receipt.acquisition_id not in var_ev.get("temp_min_c", [])
    assert receipt.acquisition_id not in var_ev.get("temp_max_c", [])
    # Therefore full native verification must be False
    assert archive["native_evidence_verified"] is False
    assert day.get("all_variables_verified") is False


def test_w4_09c_same_day_merge_unsupported_precipitation(monkeypatch, tmp_path):
    """W4-09C counterexample 2: Record A has native CAS for temp_min and temp_max,
    but Record B provides unsupported precipitation. The merged record must NOT
    claim full native verification because precipitation has no CAS backing.
    """
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    store = NativeWeatherEvidenceStore(tmp_path)
    receipt = capture(store)  # CAS has precip=0.0, tmin=5.0, tmax=15.0, et0=2.0

    # Record A: matching temps from CAS
    record_a = {
        "date": "2026-11-01",
        "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL",
        "native_acquisition_ids": [receipt.acquisition_id],
        "temp_min_c": 5.0,
        "temp_max_c": 15.0,
        "et0_mm": 2.0,
        # precipitation deliberately omitted
    }

    # Record B: fabricated precipitation, no receipt
    record_b = {
        "date": "2026-11-01",
        "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL",
        "precipitation_mm": 999.0,  # fabricated value
    }

    archive = normalize_weather_archive([record_a, record_b])
    day = archive["weather_daily_series"].get("2026-11-01")
    assert day is not None
    # Merged record has all four core variables
    assert day["temp_min_c"] == 5.0
    assert day["temp_max_c"] == 15.0
    assert day["et0_mm"] == 2.0
    assert day["precipitation_mm"] == 999.0  # from record B
    # Precipitation has no CAS backing
    var_ev = day.get("variable_evidence", {})
    assert not var_ev.get("precipitation_mm", [])
    # Full native verification must be False
    assert archive["native_evidence_verified"] is False
    assert day.get("all_variables_verified") is False
    # But temps should still have per-variable evidence
    assert receipt.acquisition_id in var_ev.get("temp_min_c", [])
    assert receipt.acquisition_id in var_ev.get("temp_max_c", [])


def test_w4_09c_consensus_averaged_values_do_not_claim_exact_native(monkeypatch, tmp_path):
    """W4-09C counterexample 3: Multi-provider consensus averaging produces derived
    values (e.g., 5.5 from 5.0 + 6.0) that should NOT pass exact CAS reconciliation.

    A record whose temp_min_c = 5.5 (averaged from two providers) will not match
    any single CAS payload that stores 5.0 or 6.0. The evidence IDs from both
    providers may be present as contributors, but native_evidence_verified must be
    False because the derived value differs from the raw CAS value.
    """
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", str(tmp_path))
    store = NativeWeatherEvidenceStore(tmp_path)

    # Provider A CAS: tmin=5.0
    p_a = payload()
    p_a["daily"]["temperature_2m_min"] = [5.0, 5.0, 6.0]
    receipt_a = capture(store, data=p_a)

    # Provider B CAS: tmin=6.0 (different query params to get a different receipt)
    q_b = params()
    q_b["latitude"] = 35.001  # slightly different to produce different acquisition
    p_b = payload()
    p_b["daily"]["temperature_2m_min"] = [6.0, 6.0, 7.0]
    receipt_b = capture(store, data=p_b, query=q_b)

    # The consensus record has averaged temp_min = (5.0 + 6.0) / 2 = 5.5
    consensus_record = {
        "date": "2026-11-01",
        "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL",
        "native_acquisition_ids": [receipt_a.acquisition_id, receipt_b.acquisition_id],
        "temp_min_c": 5.5,   # averaged: does not match 5.0 or 6.0
        "temp_max_c": 15.0,  # matches both
        "precipitation_mm": 0.0,  # matches both
        "et0_mm": 2.0,       # matches both
    }

    archive = normalize_weather_archive([consensus_record])
    day = archive["weather_daily_series"].get("2026-11-01")
    assert day is not None
    # temp_min_c = 5.5 does not match any CAS source exactly
    var_ev = day.get("variable_evidence", {})
    assert not var_ev.get("temp_min_c", []), (
        "consensus-averaged temp_min must not have exact CAS backing"
    )
    # But precipitation and et0 match both providers
    assert var_ev.get("precipitation_mm", [])
    assert var_ev.get("et0_mm", [])
    # Full native verification must be False because temp_min has no backing
    assert archive["native_evidence_verified"] is False
    assert day.get("all_variables_verified") is False
