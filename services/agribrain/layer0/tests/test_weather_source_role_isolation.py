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
from services.agribrain.layer0.environment.weather.schemas import (
    WeatherDailyRecord, WeatherConsensusDaily, VariableConsensus, WeatherTimeSeries,
)
from services.agribrain.layer0.environment.state_adapter import (
    create_weak_kalman_observations,
)
from services.agribrain.layer0.environment.weather.qa import evaluate_weather_qa
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
    assert r.precipitation_sum is None  # 1h/3h rain is not daily total


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


def test_current_only_cannot_claim_historical_daily_consensus():
    r=_record(provider="openweather",kind="current",rain=0.0)
    result=build_daily_consensus({"openweather":r},DAY)
    assert result.source_role=="REJECTED"
    assert result.source_qualified is False
    assert result.variable_consensus=={}
    assert "NON_HISTORICAL_WEATHER_ROLE_DENIED" in result.flags


@pytest.mark.parametrize("invalid",[
    "MEASURED_STATION","REANALYSIS_MODEL",
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


def _manually_supplied_current_day():
    # Defense in depth against a caller bypassing the engine's consensus gate.
    return WeatherConsensusDaily(
        date=DAY, data_kind="current", source_role="CURRENT_PROVIDER_CONTEXT",
        variable_consensus={
            "precipitation_sum": VariableConsensus(
                variable="precipitation_sum",selected_value=0.0,confidence=0.5
            ),
        },
    )


def test_weather_wrapper_marks_provider_context_as_estimated_not_observed():
    rows=_canonical_weather_records(
        SimpleNamespace(
            weather_consensus=[_manually_supplied_current_day()],
            forecast_consensus=[],
        ), packets=[],
    )
    assert len(rows)==1
    assert rows[0]["source_role"]=="CURRENT_PROVIDER_CONTEXT"
    assert rows[0]["data_status"]=="estimated"
    assert rows[0]["state_update_allowed"] is False
    assert rows[0]["source_qualified"] is False


def test_asmae_archive_does_not_mislabel_openweather_current_as_observed_archive():
    rows=_canonical_weather_records(
        SimpleNamespace(
            weather_consensus=[_manually_supplied_current_day()],
            forecast_consensus=[],
        ), packets=[],
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


def test_weak_modelled_soil_moisture_observation_excludes_current_context():
    snapshot=_record(provider="open_meteo",kind="current")
    snapshot.soil_moisture_0_1cm=0.30
    assert create_weak_kalman_observations([snapshot])==[]


def test_weak_modelled_soil_moisture_keeps_reanalysis_with_low_reliability():
    archival=_record(provider="open_meteo",kind="historical_reanalysis")
    archival.soil_moisture_0_1cm=0.30
    items=create_weak_kalman_observations([archival])
    assert len(items)==1
    assert items[0].value==0.30
    assert items[0].reliability<=0.35


def test_engine_current_openweather_context_has_no_daily_historical_forcing():
    engine=EnvironmentalEngine()
    records=normalize_openweather_daily(_openweather_current())
    assert engine._build_consensus(records)==[]


def test_historical_weather_qa_refuses_forecast_only_or_current_only():
    for kind in ("forecast","historical_forecast","current"):
        record=_record(provider="openweather",kind=kind)
        result=evaluate_weather_qa(build_weather_timeseries([record]))
        assert result["quality"]=="unusable"
        assert "NO_HISTORICAL_WEATHER_CONTEXT" in result["flags"]


def test_weather_qa_reanalysis_context_is_modelled_not_measured():
    result=evaluate_weather_qa(build_weather_timeseries([_record()]))
    assert "REANALYSIS_OR_MODEL_DATA" in result["flags"]
    assert result["quality"]!="unusable"


def test_unverified_weather_role_in_wrapper_cannot_receive_observed_status():
    # An unknown or unverified role must never receive 'observed' status in the wrapper
    unverified_day = SimpleNamespace(
        date=DAY,
        variable_consensus={"temp_mean": VariableConsensus(variable="temp_mean", selected_value=15.0)},
        data_kind="historical_reanalysis",
        source_role="UNVERIFIED",
        overall_confidence=0.5,
    )
    rows = _canonical_weather_records(
        SimpleNamespace(weather_consensus=[unverified_day], forecast_consensus=[]),
        packets=[],
    )
    assert len(rows) == 1
    assert rows[0]["data_status"] == "unverified"
    assert rows[0]["source_qualified"] is False

    # Even if an unverified dict explicitly declares data_status='observed', it must fail closed to 'unverified'
    spoofed_dict = {
        "date": DAY,
        "variable_consensus": {"temp_mean": VariableConsensus(variable="temp_mean", selected_value=15.0)},
        "data_kind": "historical_reanalysis",
        "source_role": "UNVERIFIED",
        "data_status": "observed",
        "overall_confidence": 0.5,
    }
    rows_spoofed = _canonical_weather_records(
        SimpleNamespace(weather_consensus=[spoofed_dict], forecast_consensus=[]),
        packets=[],
    )
    assert len(rows_spoofed) == 1
    assert rows_spoofed[0]["data_status"] == "unverified"


def test_unverified_weather_record_bypassing_engine_rejected_by_asmae_archive_adapter():
    # Direct caller bypass: passing a dict directly to ASMAE adapter with data_status='observed' but unverified role
    bypassed_record = {
        "date": DAY,
        "data_status": "observed",
        "source_role": "UNVERIFIED",
        "temp_mean_c": 18.0,
        "precipitation_mm": 5.0,
    }
    archive = normalize_weather_archive([bypassed_record])
    assert archive["weather_daily_series"] == {}
    assert archive["weather_archive_status"] == "unavailable"
    assert archive["weather_source_reality"] == "missing"

    # Missing role entirely with data_status='observed' must also fail closed
    missing_role_record = {
        "date": DAY,
        "data_status": "observed",
        "temp_mean_c": 18.0,
    }
    archive2 = normalize_weather_archive([missing_role_record])
    assert archive2["weather_daily_series"] == {}
    assert archive2["weather_archive_status"] == "unavailable"


def test_duplicate_provider_records_same_day_role_conflict_fails_closed_in_engine():
    engine = EnvironmentalEngine()
    rec_reanalysis = _record(provider="openweather", kind="historical_reanalysis", rain=0.0)
    rec_current = _record(provider="openweather", kind="current", rain=10.0)

    # Incompatible duplicates for same provider on same date must be detected and rejected
    consensus_list = engine._build_consensus([rec_reanalysis, rec_current])
    assert consensus_list == []


def test_duplicate_provider_records_same_day_in_build_daily_consensus_rejects():
    rec_reanalysis = _record(provider="openweather", kind="historical_reanalysis", rain=0.0)
    rec_current = _record(provider="openweather", kind="current", rain=10.0)

    result = build_daily_consensus([rec_reanalysis, rec_current], DAY)
    assert result.source_role == "REJECTED"
    assert result.data_kind == "unqualified"
    assert "DUPLICATE_PROVIDER_ROLE_CONFLICT" in result.flags
    assert result.variable_consensus == {}


def test_duplicate_provider_records_conflicting_values_fails_closed():
    engine = EnvironmentalEngine()
    rec1 = _record(provider="open_meteo", kind="historical_reanalysis", rain=0.0)
    rec2 = _record(provider="open_meteo", kind="historical_reanalysis", rain=15.0)

    # Conflicting values from same provider on same date must not silently overwrite
    consensus_list = engine._build_consensus([rec1, rec2])
    assert consensus_list == []


def test_duplicate_provider_records_identical_idempotent_passes():
    engine = EnvironmentalEngine()
    rec = _record(provider="open_meteo", kind="historical_reanalysis", rain=0.0)
    consensus_list = engine._build_consensus([rec, rec])
    assert len(consensus_list) == 1
    assert consensus_list[0].date == DAY


def test_historical_weather_qa_completeness_excludes_current_dates():
    # 1 reanalysis day + 1 current day when 1 historical day expected
    # The current day must not count in the numerator, avoiding completeness = 2.0
    rec_hist = _record(provider="open_meteo", kind="historical_reanalysis")
    rec_hist.date = "2026-11-01"
    rec_curr = _record(provider="openweather", kind="current")
    rec_curr.date = "2026-11-02"

    ts = WeatherTimeSeries(
        daily_records=[rec_hist, rec_curr],
        historical_days=1,
        forecast_days=0,
    )
    qa = evaluate_weather_qa(ts)
    assert qa["historical_completeness"] == 1.0
    assert qa["temporal_completeness"] == 1.0


def test_historical_weather_qa_completeness_current_day_cannot_mask_missing_historical_day():
    # 1 reanalysis day + 1 current day when 3 historical days expected
    # Completeness must be 0.3333 (1/3), not 0.6667 (2/3)
    rec_hist = _record(provider="open_meteo", kind="historical_reanalysis")
    rec_hist.date = "2026-11-01"
    rec_curr = _record(provider="openweather", kind="current")
    rec_curr.date = "2026-11-02"

    ts = WeatherTimeSeries(
        daily_records=[rec_hist, rec_curr],
        historical_days=3,
        forecast_days=0,
    )
    qa = evaluate_weather_qa(ts)
    assert qa["historical_completeness"] == round(1 / 3, 4)
    assert qa["temporal_completeness"] == round(1 / 3, 4)
    assert "LOW_TEMPORAL_COMPLETENESS" in qa["flags"]
    assert qa["quality"] == "degraded"


def test_unverified_reanalysis_rejected_by_asmae_archive_adapter():
    # A1: In weather_archive_adapter, unverified reanalysis must NOT enter reanalysis_archive
    unverified_reanalysis = {
        "date": DAY,
        "data_kind": "historical_reanalysis",
        "source_role": "UNVERIFIED",
        "data_status": "unverified",
        "temp_mean_c": 15.0,
        "precipitation_mm": 2.0,
    }
    archive1 = normalize_weather_archive([unverified_reanalysis])
    assert archive1["weather_daily_series"] == {}
    assert archive1["weather_archive_status"] == "unavailable"
    assert archive1["weather_source_reality"] == "missing"

    # Explicit UNVERIFIED role with implicit status
    archive2 = normalize_weather_archive([{
        "date": DAY,
        "data_kind": "historical_reanalysis",
        "source_role": "UNVERIFIED",
        "temp_mean_c": 15.0,
    }])
    assert archive2["weather_daily_series"] == {}
    assert archive2["weather_archive_status"] == "unavailable"

    # Inconsistent role (FORECAST_MODEL claimed on historical_reanalysis payload)
    # Must be rejected from BOTH historical series AND forecast series
    archive3 = normalize_weather_archive([{
        "date": DAY,
        "data_kind": "historical_reanalysis",
        "source_role": "FORECAST_MODEL",
        "temp_mean_c": 15.0,
    }])
    assert archive3["weather_daily_series"] == {}
    assert archive3["weather_forecast_series"] == {}
    assert archive3["weather_archive_status"] == "unavailable"
    assert archive3["weather_source_reality"] == "missing"

    # Missing source_role on historical_reanalysis payload is rejected
    archive4 = normalize_weather_archive([{
        "date": DAY,
        "data_kind": "historical_reanalysis",
        "temp_mean_c": 15.0,
    }])
    assert archive4["weather_daily_series"] == {}
    assert archive4["weather_forecast_series"] == {}
    assert archive4["weather_archive_status"] == "unavailable"


def test_observation_string_label_promotion_prohibited_in_wrapper_and_asmae():
    # A2: In B2B-04A, no authenticated station authority exists.
    # String-only promotion to observed_archive or rec_status='observed' is prohibited.
    obs_day = SimpleNamespace(
        date=DAY,
        variable_consensus={"temp_mean": VariableConsensus(variable="temp_mean", selected_value=20.0)},
        data_kind="historical_observation",
        source_role="OBSERVED_STATION",
        data_status="observed",
        overall_confidence=0.9,
    )
    rows = _canonical_weather_records(
        SimpleNamespace(weather_consensus=[obs_day], forecast_consensus=[]),
        packets=[],
    )
    assert len(rows) == 1
    # Wrapper fails closed to unverified
    assert rows[0]["data_status"] == "unverified"
    assert rows[0]["source_qualified"] is False

    # Direct ASMAE adapter bypass with OBSERVED_STATION and data_status='observed' fails closed
    archive = normalize_weather_archive([{
        "date": DAY,
        "data_kind": "historical_observation",
        "source_role": "OBSERVED_STATION",
        "data_status": "observed",
        "temp_mean_c": 20.0,
    }])
    assert archive["weather_daily_series"] == {}
    assert archive["weather_archive_status"] == "unavailable"
    assert archive["weather_source_reality"] == "missing"


def test_cross_provenance_daily_merge_prohibited_in_asmae_archive():
    # A3: _merge_day must NOT allow cross-reality merges where modelled variables
    # inherit observational status or cross-role provenance contamination.
    from services.agribrain.layer05_asmae.history.weather_archive_adapter import _merge_day

    day_observed = {
        "date": DAY,
        "source_reality": "observed_archive",
        "temp_mean_c": 22.0,
        "precipitation_mm": None,
    }
    day_reanalysis = {
        "date": DAY,
        "source_reality": "reanalysis_archive",
        "temp_mean_c": 20.0,
        "precipitation_mm": 5.0,
        "et0_mm": 4.0,
    }
    with pytest.raises(ValueError, match="cross_provenance_daily_merge_prohibited"):
        _merge_day(day_observed, day_reanalysis)

    with pytest.raises(ValueError, match="cross_provenance_daily_merge_prohibited"):
        _merge_day(day_reanalysis, day_observed)


def test_historical_weather_qa_independent_expected_window():
    # A4: Supply an independent requested date window for historical completeness,
    # distinguishing received-record coverage from true temporal completeness.
    rec_hist = _record(provider="open_meteo", kind="historical_reanalysis")
    rec_hist.date = "2026-11-01"

    # Requested 30 days, but only 1 day received
    ts = build_weather_timeseries([rec_hist], expected_historical_days=30)
    qa = evaluate_weather_qa(ts)

    # Historical completeness against expected window = 1/30
    assert qa["historical_completeness"] == round(1 / 30, 4)
    # Received historical coverage = 1.0 (1 eligible historical record / 1 received record)
    assert qa["received_historical_coverage"] == 1.0
    assert qa["expected_historical_days"] == 30
    assert "INCOMPLETE_HISTORICAL_WINDOW" in qa["flags"]
    assert "LOW_TEMPORAL_COMPLETENESS" in qa["flags"]
    assert qa["quality"] == "degraded"

    # Also verify expected_dates list
    expected_dates = ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"]
    ts_dates = build_weather_timeseries([rec_hist], expected_dates=expected_dates)
    qa_dates = evaluate_weather_qa(ts_dates)
    assert qa_dates["historical_completeness"] == 0.2  # 1/5
    assert qa_dates["expected_historical_days"] == 5
    assert "INCOMPLETE_HISTORICAL_WINDOW" in qa_dates["flags"]


def test_datastatus_from_value_unverified_maps_to_unavailable():
    # A4 contract check: 'unverified' is intentionally mapped to UNAVAILABLE
    from services.agribrain.layer0.observation_packet import DataStatus

    assert DataStatus.from_value("unverified") == DataStatus.UNAVAILABLE
    assert DataStatus.from_value("UNVERIFIED") == DataStatus.UNAVAILABLE
    assert DataStatus.from_value("observed") == DataStatus.OBSERVED
    assert DataStatus.from_value("estimated") == DataStatus.ESTIMATED


def test_historical_weather_qa_dates_outside_requested_window_fails_completeness():
    # Requested Nov 1-2, but received Nov 3-4 -> completeness must be 0.0, not 1.0!
    rec1 = _record(provider="open_meteo", kind="historical_reanalysis")
    rec1.date = "2026-11-03"
    rec2 = _record(provider="open_meteo", kind="historical_reanalysis")
    rec2.date = "2026-11-04"

    expected_dates = ["2026-11-01", "2026-11-02"]
    ts = build_weather_timeseries([rec1, rec2], expected_dates=expected_dates)
    qa = evaluate_weather_qa(ts)

    # 0 of the requested dates were covered
    assert qa["historical_completeness"] == 0.0
    assert qa["temporal_completeness"] == 0.0
    assert qa["expected_historical_days"] == 2
    # Received historical coverage is 1.0 (2 valid historical records / 2 received records)
    assert qa["received_historical_coverage"] == 1.0
    assert "WEATHER_DATES_OUTSIDE_EXPECTED_WINDOW" in qa["flags"]
    assert "INCOMPLETE_HISTORICAL_WINDOW" in qa["flags"]
    assert "LOW_TEMPORAL_COMPLETENESS" in qa["flags"]
    assert qa["quality"] == "degraded"


def test_source_qualified_true_rejected_by_classifier():
    # B2B-04A: No provider authority credentials exist.
    # Self-asserted source_qualified=True is an unauthorized privilege escalation and must be rejected.
    from services.agribrain.layer0.environment.weather.source_roles import (
        classify_weather_record_admission,
    )

    spoofed = {
        "date": DAY,
        "data_kind": "historical_reanalysis",
        "source_role": "REANALYSIS_MODEL",
        "source_qualified": True,
    }
    assert classify_weather_record_admission(spoofed) == "rejected"

    archive = normalize_weather_archive([spoofed])
    assert archive["weather_daily_series"] == {}
    assert archive["weather_forecast_series"] == {}
    assert archive["weather_archive_status"] == "unavailable"
