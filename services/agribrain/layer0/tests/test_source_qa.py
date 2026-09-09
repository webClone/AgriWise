"""Unit tests for Layer 0 Source QA screening factories."""

import pytest
from services.agribrain.layer0.source_qa import (
    Sentinel2QA,
    Sentinel1QA,
    WeatherQA,
    SoilQA,
)
from services.agribrain.layer0.observation_packet import (
    ObservationSource,
    ObservationType,
    QAFlag,
)


def test_sentinel2_qa_cloud_detection():
    """Verify S2 QA flags invalid pixels when cloud classes are present in SCL."""
    width, height = 3, 3
    # Band values (NDVI raster)
    pixel_values = {
        "ndvi": [[0.4, 0.4, 0.4], [0.4, 0.1, 0.4], [0.4, 0.4, 0.4]],
        "evi": [[0.3, 0.3, 0.3], [0.3, 0.1, 0.3], [0.3, 0.3, 0.3]],
    }
    # Center pixel is SCL_CLOUD_HIGH (9)
    scl_map = [
        [4, 4, 4],
        [4, 9, 4],
        [4, 4, 4],
    ]
    alpha_mask = [[1.0] * width for _ in range(height)]

    packet = Sentinel2QA.assess(
        pixel_values=pixel_values,
        scl_map=scl_map,
        alpha_mask=alpha_mask,
    )

    assert packet.source == ObservationSource.SENTINEL2
    assert packet.qa.cloud_probability is not None
    assert packet.qa.cloud_probability > 0.0
    assert packet.qa.valid_pixel_fraction is not None
    assert packet.qa.valid_pixel_fraction < 1.0
    assert "valid_mask" in packet.payload
    assert "cloud_prob" in packet.payload
    assert "ndvi" in packet.uncertainty.sigmas


def test_sentinel1_qa_backscatter_and_incidence():
    """Verify S1 QA checks incidence angle and computes ratio payload."""
    vv = [[-14.0, -15.0], [-13.0, -14.0]]
    vh = [[-21.0, -22.0], [-20.0, -21.0]]

    # Normal incidence angle
    packet_normal = Sentinel1QA.assess(
        vv_db=vv,
        vh_db=vh,
        incidence_angle=35.0,
    )
    assert packet_normal.source == ObservationSource.SENTINEL1
    assert "vv" in packet_normal.payload
    assert "vh" in packet_normal.payload
    assert "vv_vh_ratio" in packet_normal.payload
    assert QAFlag.HIGH_INCIDENCE_ANGLE not in packet_normal.qa.flags

    # High incidence angle (> 45 deg)
    packet_high_angle = Sentinel1QA.assess(
        vv_db=vv,
        vh_db=vh,
        incidence_angle=48.0,
    )
    assert QAFlag.HIGH_INCIDENCE_ANGLE in packet_high_angle.qa.flags
    # Noise sigma should be inflated for steep angles
    assert packet_high_angle.uncertainty.sigmas["vv"] > packet_normal.uncertainty.sigmas["vv"]


def test_weather_qa_uncertainty_and_source():
    """Verify WeatherQA handles local station and coarse NASA POWER sources."""
    dates = ["2026-07-01", "2026-07-02"]
    daily_data = {
        "precipitation": [0.0, 12.0],
        "temperature_2m_max": [25.0, 27.0],
        "temperature_2m_min": [14.0, 15.0],
        "et0": [3.5, 3.8],
    }

    # High quality local reanalysis / close station
    packet_close = WeatherQA.assess(
        daily_data=daily_data,
        dates=dates,
        source_name="open_meteo",
        station_distance_km=5.0,
    )
    assert packet_close.qa.scene_score >= 0.8
    assert QAFlag.LOW_CONFIDENCE not in packet_close.qa.flags

    # Coarse NASA POWER source
    packet_nasa = WeatherQA.assess(
        daily_data=daily_data,
        dates=dates,
        source_name="nasa_power",
    )
    assert QAFlag.LOW_CONFIDENCE in packet_nasa.qa.flags
    assert packet_nasa.qa.scene_score <= 0.65
    assert packet_nasa.uncertainty.sigmas["precipitation"] > packet_close.uncertainty.sigmas["precipitation"]


def test_soil_qa_priors_and_uncertainty():
    """Verify SoilQA tags soil property maps as prior evidence with proper uncertainty."""
    props = {
        "clay_pct": 28.0,
        "sand_pct": 40.0,
        "silt_pct": 32.0,
        "ph_water": 6.8,
        "org_carbon_gkg": 18.0,
    }
    packet = SoilQA.assess(
        properties=props,
        source_name="soilgrids",
        depth_cm="0-30",
    )

    assert packet.source == ObservationSource.SOILGRIDS
    assert packet.obs_type == ObservationType.TABULAR
    assert packet.payload["is_prior"] is True
    assert packet.payload["properties"]["clay_pct"] == 28.0
    assert packet.uncertainty.sigmas["clay_pct"] == 8.0
    assert QAFlag.STALE in packet.qa.flags
