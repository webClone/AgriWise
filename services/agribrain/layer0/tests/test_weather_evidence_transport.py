from types import SimpleNamespace

from services.agribrain.layer0.environment.weather.consensus import (
    build_daily_consensus,
)
from services.agribrain.layer0.environment.weather.schemas import WeatherDailyRecord
from services.agribrain.layer0.wrappers import wrap_environment
from services.agribrain.layer05_asmae.history.weather_archive_adapter import (
    normalize_weather_archive,
)


def _environment_package(day):
    packet = {
        "packet_type": "WEATHER_CONSENSUS_DAILY",
        "source": "environment_v1",
        "emitted_at": f"{day.date}T00:00:00+00:00",
        "payload": {
            "date": day.date,
            "data_kind": day.data_kind,
            "variables": {
                name: {"value": value.selected_value}
                for name, value in day.variable_consensus.items()
            },
        },
    }
    return SimpleNamespace(
        soilgrids_profile=None,
        fao_context=None,
        weather_consensus=[day],
        forecast_consensus=[],
        timestamp_window={"window_end": f"{day.date}T00:00:00Z"},
        packets=[packet],
        weak_kalman_observations=[],
        process_forcing=[],
        diagnostics={},
        provenance={},
        qa=SimpleNamespace(quality_class=SimpleNamespace(value="good")),
        plot_id="plot-weather",
    )


def test_layer0_wrapper_preserves_evidence_addressed_weather_and_zeroes():
    source = WeatherDailyRecord(
        date="2026-07-01",
        provider="open_meteo",
        data_kind="historical_reanalysis",
        temp_min=0.0,
        temp_max=10.0,
        temp_mean=5.0,
        precipitation_sum=0.0,
        et0_mm=0.0,
        relative_humidity_mean=55.0,
        wind_speed_max=0.0,
    )
    day = build_daily_consensus({"open_meteo": source}, source.date)
    package = wrap_environment(_environment_package(day))

    assert len(package.evidence_records) == 1
    assert package.evidence_records[0]["evidence_id"]
    assert package.evidence_records[0]["authority"] == "process_forcing_only"

    archive = normalize_weather_archive(package)
    row = archive["weather_daily_series"][source.date]
    assert archive["weather_archive_status"] == "available"
    assert archive["weather_source_reality"] == "reanalysis_archive"
    assert row["temp_min_c"] == 0.0
    assert row["precipitation_mm"] == 0.0
    assert row["et0_mm"] == 0.0
    assert row["wind_speed_m_s"] == 0.0
    assert row["humidity_mean_pct"] == 55.0


def test_forecast_is_not_mixed_into_historical_weather_truth():
    archive = normalize_weather_archive([
        {
            "date": "2026-07-02",
            "data_kind": "historical_reanalysis",
            "source_role": "REANALYSIS_MODEL",
            "evidence_id": "history-1",
            "temp_min_c": 11.0,
            "temp_max_c": 20.0,
            "precipitation_mm": 0.0,
            "et0_mm": 3.0,
        },
        {
            "date": "2026-07-02",
            "data_kind": "forecast",
            "source_role": "FORECAST_MODEL",
            "evidence_id": "forecast-1",
            "temp_min_c": 15.0,
            "temp_max_c": 31.0,
            "precipitation_mm": 40.0,
            "et0_mm": 8.0,
        },
    ])

    assert archive["weather_daily_series"]["2026-07-02"]["temp_max_c"] == 20.0
    assert archive["weather_forecast_series"]["2026-07-02"]["temp_max_c"] == 31.0
    assert archive["weather_source_reality"] == "reanalysis_archive"
    assert archive["weather_archive_status"] == "available"
