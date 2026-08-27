"""
Layer 3.0 Reference Evapotranspiration (ET0) Engine
FAO-56 Penman-Monteith implementation with full atmospheric input quality and uncertainty tracking.
"""

import math
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

from layer3_water.contracts.atmospheric_state import (
    HumiditySourceType,
    RadiationSourceType,
    WindSourceType,
    TemperatureSourceType,
    AtmosphericInputQuality,
)
from layer3_water.contracts.water_uncertainty import WaterUncertaintyBudget
from layer3_water.et.humidity import (
    saturation_vapor_pressure,
    mean_saturation_vapor_pressure,
    slope_vapor_pressure_curve,
    compute_actual_vapor_pressure,
)


@dataclass(frozen=True)
class ET0Result:
    """Standardized Reference Evapotranspiration result container."""
    et0_mm_day: float
    vapor_pressure_deficit_kpa: float
    net_radiation_mj_m2: float
    soil_heat_flux_mj_m2: float
    atmospheric_quality: AtmosphericInputQuality
    uncertainty: WaterUncertaintyBudget


class PenmanMonteithET0:
    """FAO-56 Standard Reference Evapotranspiration Calculator."""

    @staticmethod
    def calculate_et0(
        t_max_c: float,
        t_min_c: float,
        net_radiation_mj_m2: float,
        wind_speed_2m_m_s: float = 2.0,
        elevation_m: float = 100.0,
        soil_heat_flux_mj_m2: float = 0.0,
        dew_point_c: Optional[float] = None,
        rh_max_pct: Optional[float] = None,
        rh_min_pct: Optional[float] = None,
        rh_mean_pct: Optional[float] = None,
        radiation_source: RadiationSourceType = RadiationSourceType.PYRANOMETER,
        wind_source: WindSourceType = WindSourceType.ANEMOMETER_2M,
        temperature_source: TemperatureSourceType = TemperatureSourceType.CALIBRATED_STATION,
        soil_sigma_override: Optional[float] = None,
        weather_sigma_override: Optional[float] = None,
    ) -> ET0Result:
        """Compute standard FAO-56 Penman-Monteith daily reference ET0 (mm/day).
        
        ET0 = (0.408 * Delta * (Rn - G) + gamma * (900 / (T_mean + 273)) * u2 * (es - ea)) / 
              (Delta + gamma * (1 + 0.34 * u2))

        GAP-3 FIX: soil_sigma and weather_sigma are now configurable via overrides.
        When not overridden, uncalibrated defaults are used (documented as such).
        """
        t_mean = (t_max_c + t_min_c) / 2.0
        
        # Atmospheric pressure P (kPa) per FAO-56 Eq. 7
        pressure_kpa = 101.3 * ((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26
        
        # Psychrometric constant gamma (kPa/°C) per FAO-56 Eq. 8
        gamma = 0.000665 * pressure_kpa
        
        # Slope of vapor pressure curve Delta (kPa/°C)
        delta = slope_vapor_pressure_curve(t_mean)
        
        # Mean saturation vapor pressure es (kPa)
        es = mean_saturation_vapor_pressure(t_max_c, t_min_c)
        
        # Actual vapor pressure ea (kPa) with hierarchy
        ea, hum_source, hum_conf = compute_actual_vapor_pressure(
            t_max_c=t_max_c,
            t_min_c=t_min_c,
            dew_point_c=dew_point_c,
            rh_max_pct=rh_max_pct,
            rh_min_pct=rh_min_pct,
            rh_mean_pct=rh_mean_pct,
        )
        
        vpd = max(0.0, es - ea)
        u2 = max(0.2, wind_speed_2m_m_s)
        rn = net_radiation_mj_m2
        g = soil_heat_flux_mj_m2
        
        # Numerator & Denominator
        num_rad = 0.408 * delta * (rn - g)
        num_aero = gamma * (900.0 / (t_mean + 273.0)) * u2 * vpd
        den = delta + gamma * (1.0 + 0.34 * u2)
        
        et0_val = max(0.0, (num_rad + num_aero) / den)
        
        # Determine overall atmospheric quality
        rad_conf = 0.95 if radiation_source == RadiationSourceType.PYRANOMETER else 0.80
        wind_conf = 0.95 if wind_source == WindSourceType.ANEMOMETER_2M else 0.85
        overall_conf = round((hum_conf * 0.4 + rad_conf * 0.4 + wind_conf * 0.2), 3)
        
        atmos_qual = AtmosphericInputQuality(
            humidity_source=hum_source,
            radiation_source=radiation_source,
            wind_source=wind_source,
            temperature_source=temperature_source,
            overall_confidence=overall_conf,
        )
        
        # GAP-3 FIX: Propagate uncertainty budget with configurable sigma values.
        # soil_sigma should come from assimilation posterior variance when available.
        # weather_sigma should come from ensemble forecast spread when available.
        # Defaults are uncalibrated placeholders documented as such.
        unc_sigma = round(0.03 + (1.0 - overall_conf) * 0.05, 4)
        _soil_sigma = soil_sigma_override if soil_sigma_override is not None else 0.04
        _weather_sigma = weather_sigma_override if weather_sigma_override is not None else 0.03
        uncertainty = WaterUncertaintyBudget(
            sensor_sigma=unc_sigma,
            soil_sigma=round(_soil_sigma, 4),
            weather_sigma=round(_weather_sigma, 4),
            model_sigma=0.03,  # Uncalibrated default — requires validation against historical mass balance errors
        )
        
        return ET0Result(
            et0_mm_day=round(et0_val, 2),
            vapor_pressure_deficit_kpa=round(vpd, 3),
            net_radiation_mj_m2=round(rn, 2),
            soil_heat_flux_mj_m2=round(g, 2),
            atmospheric_quality=atmos_qual,
            uncertainty=uncertainty,
        )
