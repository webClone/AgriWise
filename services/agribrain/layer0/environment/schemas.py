"""
Environmental Context Engine V1 — Top-level schemas.

Defines EnvironmentalContextPackage, ProcessForcing, ProcessParameters,
EnvironmentalQA, and WeakKalmanObservation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


class EnvironmentalQualityClass(Enum):
    """Overall environmental context quality."""
    GOOD = "good"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


@dataclass
class EnvironmentalQA:
    """Overall quality assessment for the environmental context package."""
    quality_class: EnvironmentalQualityClass = EnvironmentalQualityClass.GOOD

    soil_provider_available: bool = False
    fao_provider_available: bool = False
    weather_provider_count: int = 0
    weather_consensus_available: bool = False

    soil_quality: Optional[str] = None  # GOOD/DEGRADED/UNUSABLE
    fao_quality: Optional[str] = None
    weather_temporal_completeness: float = 0.0

    flags: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class ProcessForcing:
    """Typed daily process-model forcing from environmental context.

    V1 produces this; V1.1 wires it into ProcessModel.predict().
    to_process_model_weather_dict() converts to existing ProcessModel format.
    """
    date: str = ""  # ISO YYYY-MM-DD

    # Core forcing
    gdd: float = 0.0
    precipitation_mm: float = 0.0
    effective_precipitation_mm: float = 0.0
    et0_mm: float = 0.0
    vpd_kpa: Optional[float] = None
    radiation_mj_m2: Optional[float] = None

    # Temperature
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    temp_mean: Optional[float] = None

    # Stress flags
    thermal_stress_flag: bool = False
    frost_flag: bool = False

    # Water balance
    water_balance_mm: float = 0.0

    # Confidence
    rainfall_confidence: float = 0.5
    weather_confidence: float = 0.5

    # ET₀ source
    et0_source: Literal["open_meteo", "hargreaves", "unknown"] = "unknown"

    def to_process_model_weather_dict(self) -> Dict[str, float]:
        """Convert to the existing ProcessModel.predict() weather format."""
        d: Dict[str, float] = {
            "precipitation": self.precipitation_mm,
            "et0": self.et0_mm,
        }
        if self.temp_max is not None:
            d["temp_max"] = self.temp_max
        if self.temp_min is not None:
            d["temp_min"] = self.temp_min
        if self.vpd_kpa is not None:
            d["vpd"] = self.vpd_kpa
        if self.radiation_mj_m2 is not None:
            d["radiation"] = self.radiation_mj_m2
        return d


@dataclass
class ProcessParameters:
    """Soil-prior-derived process model parameters.

    V1 produces this; V1.1 uses it to override DEFAULT_CROP_PARAMS
    in ProcessModel for field-specific water bucket sizing.
    """
    # Water-holding capacity
    field_capacity_vol_pct: Optional[float] = None
    wilting_point_vol_pct: Optional[float] = None
    whc_mm_per_m: Optional[float] = None  # overrides DEFAULT_CROP_PARAMS

    # Root zone
    root_zone_awc_mm_0_30: Optional[float] = None
    root_zone_awc_mm_0_60: Optional[float] = None
    root_zone_awc_mm_0_100: Optional[float] = None

    # Drainage / infiltration
    drainage_coefficient: Optional[float] = None
    infiltration_capacity: Optional[float] = None
    root_zone_storage_mm: Optional[float] = None

    # Source
    soil_source: Literal["soilgrids", "fao_fallback", "default"] = "default"
    coarse_fragment_correction_applied: bool = False


@dataclass
class WeakKalmanObservation:
    """A weak environmental observation for the Kalman update step.

    Only Open-Meteo modelled soil moisture qualifies in V1.
    """
    obs_type: str = ""  # e.g., "open_meteo_sm_0_1"
    value: float = 0.0
    sigma: float = 0.15
    reliability: float = 0.30
    state_maps_to: str = ""  # e.g., "sm_0_10"

    source: str = "open_meteo"
    data_kind: Literal[
        "current", "historical_reanalysis", "modelled"
    ] = "modelled"
    label: str = "modelled_soil_moisture"  # NEVER "soil_moisture_observation"

    timestamp: Optional[str] = None


@dataclass
class EnvironmentalContextPackage:
    """Complete environmental context output — NOT a single scene."""
    plot_id: str = ""

    # Time window
    timestamp_window: Dict[str, str] = field(default_factory=dict)
    # {window_start, window_end, historical_days, forecast_days, timezone}

    # Soil
    soilgrids_profile: Optional[Any] = None   # SoilGridsProfile
    fao_context: Optional[Any] = None         # FAOSoilContext

    # Weather (V1 historical/current)
    weather_timeseries: Optional[Any] = None  # WeatherTimeSeries
    weather_consensus: List[Any] = field(default_factory=list)  # WeatherConsensusDaily

    # Derived (V1)
    derived_features: Dict[str, Any] = field(default_factory=dict)
    process_forcing: List[ProcessForcing] = field(default_factory=list)
    process_parameters: Optional[ProcessParameters] = None

    # V1.1 Forecast
    forecast_timeseries: Optional[Any] = None         # ForecastTimeSeries
    forecast_consensus: List[Any] = field(default_factory=list)  # ForecastConsensusDaily
    forecast_derived: Optional[Any] = None             # Forecast7DaySummary
    risk_windows: List[Any] = field(default_factory=list)  # WeatherRiskWindow
    forecast_process_forcing: List[Any] = field(default_factory=list)  # ForecastProcessForcing
    forecast_diagnostics: Dict[str, Any] = field(default_factory=dict)

    # QA
    qa: EnvironmentalQA = field(default_factory=EnvironmentalQA)

    # Outputs
    packets: List[Dict[str, Any]] = field(default_factory=list)
    weak_kalman_observations: List[WeakKalmanObservation] = field(default_factory=list)

    # Audit
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

