"""B2B-04A weather dataset-role and historical/forecast isolation probes.

Synthetic normalized API objects only: no proof of provider transport,
physical station identity, actual model-run provenance or scientific issuance.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from services.agribrain.layer0.environment.engine import EnvironmentalEngine
from services.agribrain.layer0.environment.weather.consensus import build_daily_consensus
from services.agribrain.layer0.environment.weather.normalizer import (
    build_weather_timeseries,
)
from services.agribrain.layer0.environment.weather.openweather import (
    normalize_openweather_daily,
)
from services.agribrain.layer0.environment.weather.open_meteo import (
    normalize_open_meteo_daily,
)
from services.agribrain.layer0.environment.weather.schemas import WeatherDailyRecord
from services.agribrain.layer0.environment.weather.source_roles import (
    WeatherSourceRole, record_role_is_consistent, role_for_data_kind,
)
from services.agribrain.layer0.wrappers import _canonical_weather_records
from services.agribrain.layer05_asmae.history.weather_archive_adapter import (
    normalize_weather_archive,
)

DAY = "2026-11-02"
EPOCH = int(datetime(2026, 11, 2, 12, tzinfo=timezone.utc).timestamp())


def _record(provider="open_meteo",kind="historical_reanalysis",rain=0.0):
    return WeatherDailyRecord(
        date=DAY,provider=provider,data_kind=kind,
        temp_mean=13.0,temp_min=9.0,temp_max=19.0,
        precipitation_sum=rain,et0_mm=1.0,
        source_role=role_for_data_kind(kind).value,
        source_qualified=False,
    )


def _openweather_daily(rain=50.0):
    return {"daily":[{
        "dt":EPOCH,"date":DAY,
        "temp":{"min":8.0,"max":28.0,"day":20.0},
        "rain":rain,
    }]}


def _openweather_current(rain=0.0):
    return {
        "dt":EPOCH,"date":DAY,
        "main":{"temp_min":280.15,"temp_max":293.15,"temp":287.15},
        "rain":{"1h":rain},
    }


def test_openweather_one_call_daily_default_is_forecast_not_current():
    r=normalize_openweather_daily(_openweather_daily())[0]
    assert r.data_kind=="forecast"
    assert r.source_role==WeatherSourceRole.FORECAST_MODEL.value
    assert r.source_qualified is False
    assert r.precipitation_sum==50.0


@pytest.mark.parametrize("bad_kind",[
    "current","historical_reanalysis","historical_forecast",
    "statistical_climatology",
])
def test_openweather_forecast_payload_cannot_claim_historical_truth(bad_kind):
    with pytest.raises(ValueError,match="source_time_role_conflicts"):
        normalize_openweather_daily(_openweather_daily(),data_kind=bad_kind)


def test_openweather_current_payload_is_unverified_context_not_station_observation():
    r=normalize_openweather_daily(_openweather_current())[0]
    assert r.data_kind=="current"
    assert r.source_role==WeatherSourceRole.CURRENT_PROVIDER_CONTEXT.value
    assert r.source_qualified is False
    assert r.precipitation_sum==0.0


def test_openweather_current_payload_cannot_claim_forecast_or_reanalysis():
    for kind in ("forecast","historical_reanalysis"):
        with pytest.raises(ValueError,match="source_time_role_conflicts"):
            normalize_openweather_daily(_openweather_current(),data_kind=kind)


def test_openweather_unix_valid_time_is_used_when_date_omitted():
    current=_openweather_current()
    del current["date"]
    result=normalize_openweather_daily(current)[0]
    assert result.date==DAY


@pytest.mark.parametrize("bad_payload",[
    {},
    {"daily":[],"main":{}},
    {"daily":{}},
    {"daily":[None]},
    {"daily":[{"temp":{"day":12.0}}]},
])
def test_ambiguous_or_malformed_openweather_source_is_rejected(bad_payload):
    with pytest.raises(ValueError):
        normalize_openweather_daily(bad_payload)


def test_forecast_plus_reanalysis_does_not_average_rain_or_temperature():
    historical=_record(rain=0.0)
    forecast=normalize_openweather_daily(_openweather_daily(99.0))[0]
    result=build_daily_consensus(
        {"open_meteo":historical,"openweather":forecast},DAY,
    )
    assert result.data_kind=="unqualified"
    assert result.source_role=="REJECTED"
    assert "FORECAST_MIXED_WITH_HISTORICAL" in result.flags
    assert "WEATHER_SOURCE_ROLE_MIXING_DENIED" in result.flags
    assert result.variable_consensus=={}
    assert result.overall_confidence==0.0


@pytest.mark.parametrize("kind",[
    "forecast","historical_forecast","statistical_climatology","unknown",
])
def test_forecast_hindcast_climatology_unknown_never_enter_historical_consensus(kind):
    rec=_record(kind=kind)
    result=build_daily_consensus({"open_meteo":rec},DAY)
    assert result.variable_consensus=={}
    assert result.overall_confidence==0
    assert result.source_role=="REJECTED"


def test_current_and_reanalysis_are_not_combined_into_observed_truth():
    result=build_daily_consensus({
        "open_meteo":_record(),
        "openweather":_record(provider="openweather",kind="current",rain=250.0),
    },DAY)
    assert "WEATHER_SOURCE_ROLE_MIXING_DENIED" in result.flags
    assert result.variable_consensus=={}


def test_only_reanalysis_context_preserves_genuine_zero_rain_and_et0():
    r=_record(rain=0.0)
    result=build_daily_consensus({"open_meteo":r},DAY)
    assert result.data_kind=="historical_reanalysis"
    assert result.source_role=="REANALYSIS_MODEL"
    assert result.source_qualified is False
    assert result.variable_consensus["precipitation_sum"].selected_value==0.0
    assert result.variable_consensus["et0_mm"].selected_value==1.0


def test_current_only_is_context_not_verified_station():
    r=_record(provider="openweather",kind="current",rain=0.0)
    result=build_daily_consensus({"openweather":r},DAY)
    assert result.source_role=="CURRENT_PROVIDER_CONTEXT"
    assert result.source_qualified is False
    assert result.variable_consensus["precipitation_sum"].selected_value==0.0


@pytest.mark.parametrize("invalid",[
    "MEASURED_STATION","REANALYSIS_MODEL", "FORECAST_MODEL",
])
def test_forged_source_role_cannot_override_declared_forecast_data_kind(invalid):
    forecast=_record(provider="openweather",kind="forecast")
    forecast.source_role=invalid
    result=build_daily_consensus({"openweather":forecast},DAY)
    assert "INVALID_WEATHER_SOURCE_ROLE_OR_IDENTITY" in result.flags
    assert result.variable_consensus=={}


def test_claimed_source_qualification_is_not_from_data_kind():
    r=_record()
    r.source_qualified=True
    assert record_role_is_consistent(r) is False
    assert build_daily_consensus({"open_meteo":r},DAY).variable_consensus=={}


def test_provider_identity_mismatch_rejects():
    r=_record()
    result=build_daily_consensus({"openweather":r},DAY)
    assert "INVALID_WEATHER_SOURCE_ROLE_OR_IDENTITY" in result.flags
    assert result.variable_consensus=={}


@pytest.mark.parametrize("invalid_day",["", "2026-02-30", "02-11-2026",None])
def test_invalid_or_noncanonical_weather_date_rejects(invalid_day):
    r=_record()
    r.date=invalid_day
    assert record_role_is_consistent(r) is False


def test_malformed_unhashable_kind_is_rejected_without_crash():
    r=_record()
    r.data_kind=["forecast"]
    result=build_daily_consensus({"open_meteo":r},DAY)
    assert result.variable_consensus=={}
    assert result.source_role=="REJECTED"


def test_engine_excludes_openweather_daily_forecast_from_historical_process_forcing():
    engine=EnvironmentalEngine()
    records=normalize_openweather_daily(_openweather_daily(200.0))
    assert engine._build_consensus(records)==[]


def test_engine_excludes_mixed_current_and_reanalysis_from_process_forcing():
    engine=EnvironmentalEngine()
    records=[_record(),_record(provider="openweather",kind="current",rain=300.0)]
    assert engine._build_consensus(records)==[]


def test_engine_keeps_good_historical_reanalysis_when_unrelated_forecast_is_present():
    engine=EnvironmentalEngine()
    records=[_record(rain=0.0),normalize_openweather_daily(_openweather_daily(99.0))[0]]
    days=engine._build_consensus(records)
    assert len(days)==1
    assert days[0].variable_consensus["precipitation_sum"].selected_value==0.0


def test_historical_forecast_counts_as_forecast_lineage_not_history():
    ts=build_weather_timeseries([
        _record(kind="historical_forecast"),
        _record(provider="openweather",kind="forecast"),
    ])
    assert ts.historical_days==0
    assert ts.forecast_days==1


def test_weather_wrapper_marks_provider_context_as_estimated_not_observed():
    source=_record(provider="openweather",kind="current")
    day=build_daily_consensus({"openweather":source},DAY)
    rows=_canonical_weather_records(
        SimpleNamespace(weather_consensus=[day],forecast_consensus=[]),
        packets=[],
    )
    assert len(rows)==1
    assert rows[0]["source_role"]=="CURRENT_PROVIDER_CONTEXT"
    assert rows[0]["data_status"]=="estimated"
    assert rows[0]["state_update_allowed"] is False
    assert rows[0]["source_qualified"] is False


def test_asmae_archive_does_not_mislabel_openweather_current_as_observed_archive():
    source=_record(provider="openweather",kind="current")
    day=build_daily_consensus({"openweather":source},DAY)
    rows=_canonical_weather_records(
        SimpleNamespace(weather_consensus=[day],forecast_consensus=[]),
        packets=[],
    )
    result=normalize_weather_archive(rows)
    assert result["weather_daily_series"]=={}
    assert result["weather_archive_status"]=="unavailable"
    assert result["weather_source_reality"]=="missing"


def test_asmae_archive_keeps_reanalysis_context_and_zero_weather_values():
    record=_record()
    result=build_daily_consensus({"open_meteo":record},DAY)
    rows=_canonical_weather_records(
        SimpleNamespace(weather_consensus=[result],forecast_consensus=[]),
        packets=[],
    )
    archive=normalize_weather_archive(rows)
    assert archive["weather_source_reality"]=="reanalysis_archive"
    assert archive["weather_daily_series"][DAY]["precipitation_mm"]==0.0


def test_open_meteo_adapter_labels_reanalysis_as_model_not_station():
    r=normalize_open_meteo_daily({
        "daily":{"time":[DAY],"precipitation_sum":[0.0]}
    })[0]
    assert r.data_kind=="historical_reanalysis"
    assert r.source_role=="REANALYSIS_MODEL"
    assert r.source_qualified is False
