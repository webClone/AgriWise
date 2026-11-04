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
