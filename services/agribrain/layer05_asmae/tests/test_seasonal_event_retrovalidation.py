"""
Unit and Integration Tests for ASMAE Intra-Seasonal Event-Driven Diagnostic Retrovalidation.
Asserts:
  1. Seasonal segmentation of multi-year archive stacks into crop cycles.
  2. Multi-event detection (Irrigation, Rain, Drought, Fertilization, Nutrient Deficiency, Disease Risk).
  3. Diagnostic anomaly prediction & symptom cascade tracking.
  4. Event-targeted holdout evaluation and seasonal scorecard generation.
"""
import pytest
from datetime import datetime, timedelta
import numpy as np

from layer05_asmae.schema import ASMAESceneRuntime
from layer05_asmae.history.history_schema import CropSeasonSegment
from layer05_asmae.history.crop_season_segmenter import CropSeasonSegmenter
from layer05_asmae.history.event_detector import IntraSeasonalEventDetector, SeasonalEventRecord
from layer05_asmae.retrovalidation.event_retrovalidation import EventRetrovalidator, EventRetrovalidationResult
from layer05_asmae.retrovalidation.yearly_backtest import YearlyBacktest
from layer05_asmae.history.historical_assimilation_runner import HistoricalAssimilationRunner


def _create_mock_scene(scene_id: str, sensor: str, dt: datetime, ndvi: float = 0.5, vv: float = -12.0, ndmi: float = 0.2):
    return {
        "runtime": ASMAESceneRuntime(
            scene_id=scene_id,
            sensor=sensor,
            acquisition_time=dt,
            crs="EPSG:32631",
            transform=[10.0, 0.0, 500000.0, 0.0, -10.0, 4000000.0],
            width=10,
            height=10,
            bands={
                "ndvi": np.full((10, 10), ndvi, dtype=float),
                "vv": np.full((10, 10), vv, dtype=float),
                "vh": np.full((10, 10), vv - 6.0, dtype=float),
                "ndmi": np.full((10, 10), ndmi, dtype=float),
                "ndre": np.full((10, 10), ndvi * 0.8, dtype=float),
            },
            masks={"clear": np.ones((10, 10), dtype=bool)},
            cloud_fraction=0.0,
            qa_score=1.0,
        ),
        "quality": type("Quality", (), {"clear_pixel_fraction": 1.0, "overall": 1.0})()
    }


def test_crop_season_segmentation():
    """Verify multi-year scenes are segmented into active crop cycles and fallow periods."""
    scenes = []
    base_dt = datetime(2023, 1, 1, 12, 0, 0)

    # Season 1: Active crop (NDVI 0.5 - 0.8)
    for i in range(6):
        scenes.append(_create_mock_scene(f"s1_{i}", "S2", base_dt + timedelta(days=i * 15), ndvi=0.4 + i * 0.08))

    # Fallow period: (NDVI 0.15)
    fallow_start = base_dt + timedelta(days=120)
    for i in range(4):
        scenes.append(_create_mock_scene(f"fallow_{i}", "S2", fallow_start + timedelta(days=i * 20), ndvi=0.15))

    # Season 2: Active crop (NDVI 0.6)
    s2_start = fallow_start + timedelta(days=100)
    for i in range(6):
        scenes.append(_create_mock_scene(f"s2_{i}", "S2", s2_start + timedelta(days=i * 15), ndvi=0.55))

    segmenter = CropSeasonSegmenter(ndvi_threshold=0.25)
    segments = segmenter.segment_scenes(scenes)

    assert len(segments) >= 3, f"Expected at least 3 segments (active, fallow, active), got {len(segments)}"
    assert segments[0].is_active_crop is True
    assert segments[1].is_active_crop is False
    assert segments[2].is_active_crop is True

    # Assert peak metrics recorded
    assert segments[0].peak_ndvi >= 0.70
    assert segments[0].peak_date is not None


def test_intra_seasonal_event_detection_all_classes():
    """Verify detection of irrigation, rain, drought, fertilization, nutrient deficiency, and disease risk."""
    detector = IntraSeasonalEventDetector()
    start_dt = datetime(2024, 3, 1, 12, 0, 0)
    end_dt = datetime(2024, 6, 1, 12, 0, 0)

    # 1. Weather series with a rain pulse, drought window, and high humidity disease risk streak
    weather = {}
    curr = start_dt
    day_idx = 0
    while curr.date() <= end_dt.date():
        d_str = curr.strftime("%Y-%m-%d")
        precip = 0.0
        et0 = 4.0
        rh = 55.0

        # Day 15: Rain event (18mm)
        if day_idx == 15:
            precip = 18.0
        # Days 30 to 45: Drought (15 days no rain, et0=4.5)
        elif 30 <= day_idx <= 45:
            et0 = 4.5
        # Days 60 to 65: Disease risk pre-conditions (high humidity 88%, mild temp 20C)
        elif 60 <= day_idx <= 65:
            rh = 88.0

        weather[d_str] = {
            "temp_max": 25.0,
            "temp_min": 15.0,
            "precipitation": precip,
            "et0": et0,
            "rh_mean": rh
        }
        curr += timedelta(days=1)
        day_idx += 1

    # 2. Scene list with SAR irrigation event and optical fertilization event
    scenes = [
        # Baseline S1
        _create_mock_scene("sar_1", "S1", start_dt + timedelta(days=5), vv=-14.0),
        # Irrigation spike on Day 10 (SAR jumps from -14 to -10 dB without rain)
        _create_mock_scene("sar_2", "S1", start_dt + timedelta(days=10), vv=-10.5),

        # S2 scenes for Fertilization (NDVI jumps by 0.15 in 10 days)
        _create_mock_scene("opt_1", "S2", start_dt + timedelta(days=20), ndvi=0.45, ndmi=0.25),
        _create_mock_scene("opt_2", "S2", start_dt + timedelta(days=28), ndvi=0.62, ndmi=0.25),

        # S2 scene for Nutrient deficiency (NDVI drops while NDMI remains high)
        _create_mock_scene("opt_3", "S2", start_dt + timedelta(days=50), ndvi=0.60, ndmi=0.25),
        _create_mock_scene("opt_4", "S2", start_dt + timedelta(days=58), ndvi=0.48, ndmi=0.24),
    ]

    events = detector.detect_events(
        season_id="test_season",
        start_date=start_dt,
        end_date=end_dt,
        scenes=scenes,
        daily_weather=weather
    )

    event_types = {e.event_type for e in events}

    assert "rain" in event_types, "Failed to detect Rain event"
    assert "drought" in event_types, "Failed to detect Drought event"
    assert "irrigation" in event_types, "Failed to detect Irrigation event"
    assert "fertilization" in event_types, "Failed to detect Fertilization event"
    assert "nutrient_deficiency" in event_types, "Failed to detect Nutrient Deficiency event"
    assert "disease_risk" in event_types, "Failed to detect Disease Risk event"


def test_event_retrovalidation_holdout_evaluation():
    """Verify EventRetrovalidator evaluates prediction error against held-out scenes across an event window."""
    validator = EventRetrovalidator(error_threshold_rmse=0.10, min_r2_threshold=0.40)

    start_dt = datetime(2024, 4, 1, 12, 0, 0)
    event = SeasonalEventRecord(
        event_id="test_irrigation_1",
        event_type="irrigation",
        start_date=start_dt + timedelta(days=10),
        end_date=start_dt + timedelta(days=15),
        peak_date=start_dt + timedelta(days=12),
        severity=0.8,
        confidence=0.9,
        sensor_evidence={"source": "mock"},
        symptom_progression=["surface_wetting", "vigor_acceleration"]
    )

    # Scenes: 3 training scenes outside window, 1 holdout scene inside window
    scenes = [
        _create_mock_scene("pre_1", "S2", start_dt + timedelta(days=2), ndvi=0.40),
        _create_mock_scene("pre_2", "S2", start_dt + timedelta(days=6), ndvi=0.45),
        _create_mock_scene("event_holdout", "S2", start_dt + timedelta(days=12), ndvi=0.55), # Event holdout
        _create_mock_scene("post_1", "S2", start_dt + timedelta(days=25), ndvi=0.60),
    ]

    weather = {}
    curr = start_dt
    while curr.date() <= (start_dt + timedelta(days=30)).date():
        weather[curr.strftime("%Y-%m-%d")] = {
            "temp_max": 24.0, "temp_min": 14.0, "precipitation": 0.0, "et0": 4.0
        }
        curr += timedelta(days=1)

    runner = HistoricalAssimilationRunner(workspace_root=".")
    res = validator.evaluate_event_retrovalidation(
        event=event,
        seasonal_scenes=scenes,
        assimilation_runner=runner,
        plot_id="plot_test_001",
        geometry_hash="geom_test_001",
        daily_weather=weather
    )

    assert isinstance(res, EventRetrovalidationResult)
    assert res.event_id == "test_irrigation_1"
    assert "event_holdout" in res.holdout_scene_ids
    assert res.status in ("passed", "degraded")
    assert res.symptom_accuracy >= 0.0


def test_yearly_backtest_with_seasonal_matrix():
    """Verify YearlyBacktest outputs a complete seasonal scorecard with detected events."""
    runner = HistoricalAssimilationRunner(workspace_root=".")
    backtester = YearlyBacktest(runner)

    start_dt = datetime(2023, 4, 1, 12, 0, 0)
    scenes = [
        _create_mock_scene("sc_1", "S2", start_dt + timedelta(days=5), ndvi=0.35),
        _create_mock_scene("sc_2", "S2", start_dt + timedelta(days=20), ndvi=0.50),
        _create_mock_scene("sc_3", "S2", start_dt + timedelta(days=35), ndvi=0.65),
        _create_mock_scene("sc_4", "S2", start_dt + timedelta(days=50), ndvi=0.60),
    ]

    weather = {}
    curr = start_dt
    while curr.date() <= (start_dt + timedelta(days=60)).date():
        weather[curr.strftime("%Y-%m-%d")] = {
            "temp_max": 24.0, "temp_min": 14.0, "precipitation": 0.0, "et0": 3.5
        }
        curr += timedelta(days=1)

    res = backtester.run_backtest(
        plot_id="plot_test_001",
        geometry_hash="geom_test_001",
        scenes=scenes,
        daily_weather=weather
    )

    assert res["status"] == "success"
    assert "seasonal_matrix" in res
    assert "events_detected" in res
    assert "event_retrovalidation_results" in res
    assert res["seasons_evaluated"] >= 1
