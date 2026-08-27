"""
Layer 3.0 Atmospheric Quality and Thermal Diagnostic Contracts
Tracks meteorological input authority and canopy surface temperature cooling deficit.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import math


class HumiditySourceType(str, Enum):
    """Hierarchy of vapor pressure and humidity data sources."""
    DEW_POINT = "DEW_POINT"                 # Highest fidelity (direct psychrometric measurement)
    RH_MIN_MAX = "RH_MIN_MAX"               # Diurnal extremum range (FAO-56 standard)
    RH_MEAN = "RH_MEAN"                     # Daily average approximation (moderate error in arid zones)
    DEFAULT_ESTIMATE = "DEFAULT_ESTIMATE"   # T_min assumption (lowest fidelity)


class RadiationSourceType(str, Enum):
    """Hierarchy of solar irradiance data sources."""
    PYRANOMETER = "PYRANOMETER"             # Direct solar radiation measurement (Rs)
    SOLAR_HOURS = "SOLAR_HOURS"             # Angstrom-Prescott formula from sunshine duration
    TEMPERATURE_DIURNAL = "TEMPERATURE_DIURNAL" # Hargreaves-Samani temperature difference fallback
    SATELLITE_DERIVED = "SATELLITE_DERIVED" # Gridded geostationary / ECMWF reanalysis


class WindSourceType(str, Enum):
    """Hierarchy of anemometer wind speed measurements."""
    ANEMOMETER_2M = "ANEMOMETER_2M"         # Direct measurement at standard 2m height
    ANEMOMETER_10M_SCALED = "ANEMOMETER_10M_SCALED" # Logarithmic wind profile reduction from 10m to 2m
    REGIONAL_REANALYSIS = "REGIONAL_REANALYSIS" # ECMWF / GFS grid output
    DEFAULT_CONSTANT = "DEFAULT_CONSTANT"   # Global standard 2.0 m/s assumption


class TemperatureSourceType(str, Enum):
    """Hierarchy of air temperature measurements."""
    CALIBRATED_STATION = "CALIBRATED_STATION" # On-farm calibrated thermocouple / thermistor
    OFF_SITE_STATION = "OFF_SITE_STATION"   # Nearby public airport / METAR station
    SATELLITE_THERMAL = "SATELLITE_THERMAL" # MODIS / Landsat surface-air inversion
    WEATHER_MODEL = "WEATHER_MODEL"         # Numerical weather prediction


@dataclass(frozen=True)
class AtmosphericInputQuality:
    """Provenance and authority metadata for meteorological drivers."""
    humidity_source: HumiditySourceType = HumiditySourceType.RH_MIN_MAX
    radiation_source: RadiationSourceType = RadiationSourceType.PYRANOMETER
    wind_source: WindSourceType = WindSourceType.ANEMOMETER_2M
    temperature_source: TemperatureSourceType = TemperatureSourceType.CALIBRATED_STATION
    overall_confidence: float = 0.90
    missing_elements: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CanopyTemperatureState:
    """Thermal observation and evaporative cooling deficit contract.
    
    Represents physical surface temperature status without circular biological assumption.
    """
    canopy_temperature_c: float              # Tc measured by thermal infrared sensor
    air_temperature_c: float                 # Ta measured at reference height
    vapor_pressure_deficit_kpa: float        # VPD (es - ea) in kPa
    evaporative_cooling_deficit_c: float     # ECD = (Tc - Ta) - (Tc - Ta)_well_watered_baseline
    thermal_authority: str = "THERMAL_OBSERVATION_NOT_CAUSAL_DIAGNOSIS"
    observation_uncertainty_c: float = 0.5   # Uncertainty in thermal differential

    @property
    def temperature_differential_c(self) -> float:
        """Raw thermal differential Delta T = Tc - Ta."""
        return round(self.canopy_temperature_c - self.air_temperature_c, 2)
