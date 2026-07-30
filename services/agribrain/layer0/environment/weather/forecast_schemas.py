"""
Weather Forecast V1.1 Schemas.

Forecast-specific dataclasses for 7-day operational forecast intelligence.

Convention:
  - Forecast horizon = 7 calendar dates including today
  - lead_day = 0..6  (Day 0 = today, Day 6 = 6 days ahead)
  - lead_hour = 0..167 (168 hourly records)
  - All timestamps in plot-local time for daily summaries / risk windows
  - Canonical units: °C, mm, m/s, kPa, hPa, MJ/m²/day, W/m², degrees (0-360)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FORECAST_HORIZON_V11 = 7  # calendar days including today
MAX_FORECAST_HOURS_V11 = 168  # 7 * 24

COMPASS_SECTORS_8 = [
    "N", "NE", "E", "SE", "S", "SW", "W", "NW",
]

COMPASS_SECTORS_16 = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


# ---------------------------------------------------------------------------
# Unit conversion helpers
# ---------------------------------------------------------------------------

def ms_to_kmh(speed_ms: float) -> float:
    """Convert wind speed from m/s to km/h."""
    return round(speed_ms * 3.6, 2)


def kmh_to_ms(speed_kmh: float) -> float:
    """Convert wind speed from km/h to m/s."""
    return round(speed_kmh / 3.6, 2)


def deg_to_compass_sector(degrees: float, bins: int = 8) -> str:
    """Convert meteorological degrees (0-360) to compass sector.

    bins: 8 for N/NE/E/... or 16 for N/NNE/NE/ENE/...
    """
    sectors = COMPASS_SECTORS_8 if bins == 8 else COMPASS_SECTORS_16
    step = 360.0 / len(sectors)
    idx = int((degrees + step / 2) % 360 / step)
    return sectors[idx % len(sectors)]


def normalize_wind_direction(degrees: float) -> float:
    """Normalize wind direction to 0-360 range."""
    return degrees % 360.0


# ---------------------------------------------------------------------------
# Forecast Hourly Record
# ---------------------------------------------------------------------------

@dataclass
class ForecastHourlyRecord:
    """Hourly forecast record from a single provider.

    All fields use canonical AgriBrain units.
    """
    # Identity
    provider: str = ""
    data_kind: Literal["forecast"] = "forecast"
    timestamp: str = ""         # ISO datetime in provider timezone
    local_timestamp: str = ""   # ISO datetime in plot-local timezone
    date: str = ""              # ISO YYYY-MM-DD (local date)
    lead_hour: int = 0          # 0..167
    lead_day: int = 0           # 0..6
    timezone: str = "UTC"
    utc_offset_seconds: int = 0

    # Provenance
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    model_run_time: Optional[str] = None
    retrieval_time: Optional[str] = None

    # Temperature (°C)
    temperature_2m_c: Optional[float] = None
    relative_humidity_2m_pct: Optional[float] = None
    dew_point_2m_c: Optional[float] = None

    # Precipitation (mm)
    precipitation_mm: Optional[float] = None
    rain_mm: Optional[float] = None
    precipitation_probability_pct: Optional[float] = None

    # Cloud & radiation
    cloud_cover_pct: Optional[float] = None
    shortwave_radiation_w_m2: Optional[float] = None
    reference_et0_mm: Optional[float] = None

    # VPD (kPa)
    vapour_pressure_deficit_kpa: Optional[float] = None

    # Wind (m/s canonical, degrees meteorological 0-360)
    wind_speed_10m_ms: Optional[float] = None
    wind_direction_10m_deg: Optional[float] = None
    wind_gusts_10m_ms: Optional[float] = None

    # Pressure (hPa)
    surface_pressure_hpa: Optional[float] = None

    # Soil temperature (°C)
    soil_temperature_0cm_c: Optional[float] = None
    soil_temperature_6cm_c: Optional[float] = None
    soil_temperature_18cm_c: Optional[float] = None
    soil_temperature_54cm_c: Optional[float] = None

    # Soil moisture (m³/m³ volumetric fraction)
    soil_moisture_0_1cm: Optional[float] = None
    soil_moisture_1_3cm: Optional[float] = None
    soil_moisture_3_9cm: Optional[float] = None
    soil_moisture_9_27cm: Optional[float] = None
    soil_moisture_27_81cm: Optional[float] = None

    # Weather code
    weather_code: Optional[int] = None

    # Raw provider payload reference (for debugging)
    raw_provider_payload_ref: Optional[str] = None


# ---------------------------------------------------------------------------
# Forecast Daily Record
# ---------------------------------------------------------------------------

@dataclass
class ForecastDailyRecord:
    """Daily forecast record from a single provider."""
    # Identity
    provider: str = ""
    date: str = ""              # ISO YYYY-MM-DD (local date)
    local_date: str = ""        # Explicit plot-local date
    lead_day: int = 0           # 0..6
    data_kind: Literal["forecast"] = "forecast"
    timezone: str = "UTC"
    utc_offset_seconds: int = 0

    # Provenance
    model_run_time: Optional[str] = None
    retrieval_time: Optional[str] = None

    # Temperature (°C)
    tmin_c: Optional[float] = None
    tmax_c: Optional[float] = None
    tmean_c: Optional[float] = None

    # Precipitation (mm)
    precipitation_sum_mm: Optional[float] = None
    rain_sum_mm: Optional[float] = None
    precipitation_probability_max_pct: Optional[float] = None

    # ET₀ and VPD
    et0_sum_mm: Optional[float] = None
    vpd_max_kpa: Optional[float] = None
    vpd_mean_kpa: Optional[float] = None

    # Radiation
    shortwave_radiation_sum_mj_m2: Optional[float] = None

    # Wind (m/s canonical)
    wind_speed_mean_10m_ms: Optional[float] = None
    wind_speed_max_10m_ms: Optional[float] = None
    wind_gusts_max_10m_ms: Optional[float] = None
    dominant_wind_direction_deg: Optional[float] = None
    wind_direction_variability_deg: Optional[float] = None

    # Cloud
    cloud_cover_mean_pct: Optional[float] = None

    # Soil layers (means)
    soil_moisture_layer_means: Dict[str, float] = field(default_factory=dict)
    soil_temperature_layer_means: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Forecast Time Series
# ---------------------------------------------------------------------------

@dataclass
class ForecastTimeSeries:
    """Combined forecast time series from multiple providers."""
    hourly_records: List[ForecastHourlyRecord] = field(default_factory=list)
    daily_records: List[ForecastDailyRecord] = field(default_factory=list)

    # Horizon metadata
    horizon_calendar_days: int = 0  # actual days present
    lead_day_range: List[int] = field(default_factory=lambda: [0, 6])
    date_range_start: str = ""
    date_range_end: str = ""
    hourly_count: int = 0
    daily_count: int = 0

    # Provider metadata
    providers: List[str] = field(default_factory=list)
    timezone: str = "UTC"

    # Staleness
    model_run_time: Optional[str] = None
    retrieval_time: Optional[str] = None
    forecast_age_hours: Optional[float] = None
    stale_forecast_flag: bool = False


# ---------------------------------------------------------------------------
# Forecast Consensus
# ---------------------------------------------------------------------------

@dataclass
class ForecastVariableConsensus:
    """Per-variable, per-day, per-lead-day consensus for forecast data."""
    variable: str = ""
    date: str = ""
    lead_day: int = 0
    provider_values: Dict[str, Any] = field(default_factory=dict)
    selected_value: Any = None
    selected_provider: Optional[str] = None
    provider_agreement_score: float = 0.0
    variable_confidence: float = 0.0
    decision_confidence: float = 0.0
    flags: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class ForecastConsensusDaily:
    """Per-day forecast consensus envelope."""
    date: str = ""
    lead_day: int = 0
    variable_consensus: Dict[str, ForecastVariableConsensus] = field(
        default_factory=dict
    )
    overall_forecast_confidence: float = 0.0
    rainfall_confidence: float = 0.0
    wind_confidence: float = 0.0
    temperature_confidence: float = 0.0
    provider_count: int = 0
    flags: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Forecast Confidence
# ---------------------------------------------------------------------------

# Base lead-time confidence: lead_day 0..6
BASE_LEAD_CONFIDENCE = {
    0: 0.90,
    1: 0.85,
    2: 0.75,
    3: 0.65,
    4: 0.55,
    5: 0.45,
    6: 0.38,
}

# Variable-specific decay modifiers
VARIABLE_DECAY_MODIFIERS = {
    "temperature": 1.00,
    "wind_speed": 0.85,
    "wind_gusts": 0.70,
    "precipitation": 0.65,
    "precip_probability": 0.70,
    "et0": 0.85,
    "vpd": 0.85,
    "radiation": 0.75,
    "cloud_cover": 0.75,
    "soil_moisture_modelled": 0.40,
}


# ---------------------------------------------------------------------------
# Risk Windows
# ---------------------------------------------------------------------------

RISK_WINDOW_TYPES = [
    "SPRAY_WINDOW",
    "IRRIGATION_WINDOW",
    "HARVEST_WINDOW",
    "FIELD_ACCESS_WINDOW",
    "HEAT_STRESS_WINDOW",
    "FROST_WINDOW",
    "HIGH_WIND_WINDOW",
    "HOT_DRY_WIND_WINDOW",
    "DISEASE_WEATHER_WINDOW",
    "RAIN_EVENT_WINDOW",
    "DRYDOWN_WINDOW",
]


@dataclass
class WeatherRiskWindow:
    """A weather-driven risk or opportunity window."""
    window_type: str = ""
    start_time: str = ""        # ISO datetime in plot-local time
    end_time: str = ""          # ISO datetime in plot-local time
    date: str = ""              # ISO YYYY-MM-DD (local date)

    # Score polarity (Revision 6)
    opportunity_score: Optional[float] = None  # 0-1, high = good for the activity
    risk_score: Optional[float] = None         # 0-1, high = dangerous

    confidence: float = 0.0
    window_confidence: float = 0.0    # decision-level confidence (Revision 8)
    severity: Literal["low", "moderate", "high", "severe"] = "low"
    window_basis: Literal["hourly", "daily_approximation"] = "hourly"

    drivers: Dict[str, Any] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)
    recommendation_hint: str = ""


# ---------------------------------------------------------------------------
# Forecast Risk Configuration (Revision 7)
# ---------------------------------------------------------------------------

@dataclass
class ForecastRiskConfig:
    """Crop/stage-aware threshold configuration for risk windows.

    V1.1 uses defaults. Schema supports overrides per crop/stage.
    """
    crop_type: str = "generic"
    phenology_stage: str = "vegetative"

    # Spray thresholds
    spray_wind_max_ms: float = 4.2
    spray_gust_max_ms: float = 7.0

    # High wind
    high_wind_ms: float = 8.3
    gust_damage_ms: float = 12.5
    severe_gust_ms: float = 18.0

    # Hot dry wind
    hot_dry_wind_temp_c: float = 30.0
    hot_dry_wind_rh_pct: float = 30.0
    hot_dry_wind_speed_ms: float = 5.6

    # Frost
    frost_threshold_c: float = 2.0
    frost_calm_wind_ms: float = 1.5

    # Heat stress
    heat_stress_temp_c: float = 35.0
    vpd_high_kpa: float = 2.5

    # Irrigation
    irrigation_method: str = "drip"  # drip / sprinkler / furrow
    soil_water_capacity_mm: Optional[float] = None

    # Spray rain/VPD
    spray_rain_prob_threshold_pct: float = 50.0
    spray_rain_amount_threshold_mm: float = 1.0
    spray_temp_max_c: float = 30.0
    spray_vpd_max_kpa: float = 2.5


# ---------------------------------------------------------------------------
# Forecast Derived Features
# ---------------------------------------------------------------------------

@dataclass
class Forecast7DaySummary:
    """Seven-day aggregated forecast features."""
    forecast_7d_precip_sum_mm: float = 0.0
    forecast_7d_et0_sum_mm: float = 0.0
    forecast_7d_water_balance_mm: float = 0.0
    forecast_7d_gdd: float = 0.0
    forecast_max_vpd_kpa: float = 0.0
    forecast_mean_vpd_kpa: float = 0.0
    forecast_heat_stress_hours: int = 0
    forecast_frost_hours: int = 0
    forecast_high_wind_hours: int = 0
    forecast_hot_dry_wind_hours: int = 0
    forecast_sprayable_hours: int = 0
    forecast_irrigation_need_score: float = 0.0
    forecast_rain_event_count: int = 0
    forecast_drydown_score: float = 0.0
    forecast_confidence_mean: float = 0.0
    forecast_confidence_min: float = 0.0


@dataclass
class ForecastDailyAgSummary:
    """Per-day operational agronomic summary from forecast."""
    date: str = ""
    lead_day: int = 0
    precip_sum_mm: float = 0.0
    et0_sum_mm: float = 0.0
    water_balance_mm: float = 0.0
    gdd: float = 0.0
    vpd_max: float = 0.0
    tmax: Optional[float] = None
    tmin: Optional[float] = None
    wind_max: Optional[float] = None
    gust_max: Optional[float] = None
    spray_window_best_hours: int = 0
    irrigation_window_score: float = 0.0
    field_access_score: float = 0.0
    risk_flags: List[str] = field(default_factory=list)
    variable_confidence: float = 0.0
    decision_confidence: float = 0.0


# ---------------------------------------------------------------------------
# Forecast Process Forcing
# ---------------------------------------------------------------------------

@dataclass
class ForecastProcessForcing:
    """Future process-model forcing from forecast.

    HARD RULE: This is FUTURE forcing only.
    It must NEVER create a current Kalman update.
    """
    date: str = ""
    lead_day: int = 0

    # Core forcing
    temperature_min_c: Optional[float] = None
    temperature_max_c: Optional[float] = None
    temperature_mean_c: Optional[float] = None
    precipitation_mm: float = 0.0
    effective_precipitation_mm: float = 0.0
    et0_mm: float = 0.0
    vpd_kpa: Optional[float] = None
    radiation_mj_m2: Optional[float] = None

    # Wind
    wind_speed_mean_ms: Optional[float] = None
    wind_gust_max_ms: Optional[float] = None

    # Derived
    water_balance_mm: float = 0.0
    gdd: float = 0.0

    # Confidence
    forcing_confidence: float = 0.0

    # Safety label
    data_kind: Literal["forecast"] = "forecast"


# ---------------------------------------------------------------------------
# Staleness thresholds (Revision 5)
# ---------------------------------------------------------------------------

STALENESS_WARNING_HOURS = 12.0
STALENESS_DEGRADE_HOURS = 24.0
STALENESS_UNUSABLE_HOURS = 48.0
