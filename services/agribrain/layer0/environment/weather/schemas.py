"""
Weather V1 Schemas.

Common schemas for weather data from any provider.
Every record has a data_kind separating current/forecast/reanalysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


@dataclass
class WeatherDailyRecord:
    """Common daily weather record from any provider."""
    date: str = ""  # ISO YYYY-MM-DD
    provider: str = ""

    data_kind: Literal[
        "current", "forecast", "historical_reanalysis",
        "historical_forecast", "statistical_climatology",
    ] = "current"
    lead_time_hours: Optional[int] = None
    model_run_time: Optional[str] = None
    retrieval_time: Optional[str] = None

    # Temperature (°C)
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    temp_mean: Optional[float] = None

    # Precipitation (mm)
    precipitation_sum: Optional[float] = None
    rain_sum: Optional[float] = None
    precipitation_hours: Optional[float] = None

    # ET and VPD
    et0_mm: Optional[float] = None
    vpd_mean: Optional[float] = None       # kPa

    # Radiation
    shortwave_radiation_sum: Optional[float] = None  # MJ/m²
    sunshine_duration_hours: Optional[float] = None

    # Wind
    wind_speed_max: Optional[float] = None   # m/s
    wind_gusts_max: Optional[float] = None

    # Humidity
    relative_humidity_mean: Optional[float] = None  # %
    dew_point_mean: Optional[float] = None  # °C

    # Pressure
    surface_pressure_mean: Optional[float] = None  # hPa

    # Cloud
    cloud_cover_mean: Optional[float] = None  # %

    # Soil (modelled — from Open-Meteo)
    soil_temperature_0_7cm: Optional[float] = None   # °C
    soil_temperature_7_28cm: Optional[float] = None
    soil_moisture_0_1cm: Optional[float] = None    # m³/m³
    soil_moisture_1_3cm: Optional[float] = None
    soil_moisture_3_9cm: Optional[float] = None
    soil_moisture_9_27cm: Optional[float] = None
    soil_moisture_27_81cm: Optional[float] = None  # deep context, not V1 Kalman


@dataclass
class WeatherTimeSeries:
    """Time series of daily weather records from one or more providers."""
    daily_records: List[WeatherDailyRecord] = field(default_factory=list)

    # Window metadata
    window_start: str = ""
    window_end: str = ""
    historical_days: int = 0
    forecast_days: int = 0
    timezone: str = "UTC"

    providers: List[str] = field(default_factory=list)


@dataclass
class VariableConsensus:
    """Per-variable consensus result between weather providers."""
    variable: str = ""
    provider_values: Dict[str, Optional[float]] = field(default_factory=dict)
    selected_value: Optional[float] = None
    confidence: float = 0.5
    agreement_score: float = 0.0
    source: str = ""  # which provider was selected
    flags: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class WeatherConsensusDaily:
    """Per-day, per-variable weather consensus."""
    date: str = ""
    data_kind: str = ""  # what kind of data was used (current/reanalysis)

    variable_consensus: Dict[str, VariableConsensus] = field(default_factory=dict)

    # Convenience accessors
    overall_confidence: float = 0.5
    flags: List[str] = field(default_factory=list)
