"""MESIA Bayesian Nuisance Attribution Model — R6 §9.4 / P7.4.

Estimates cause probabilities: P(soil), P(instrument), P(geometry), P(network),
P(coexistence), P(weather) to ensure instrument errors are never absorbed into soil models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class NuisanceAttributionReport:
    """Posterior probabilities over candidate cause hypotheses."""

    p_soil_water_change: float
    p_instrument_nuisance: float
    p_geometry_nuisance: float
    p_network_nuisance: float
    p_coexistence_nuisance: float
    p_weather_motion_nuisance: float
    p_unknown_nuisance: float
    dominant_cause: str
    is_safe_for_soil_assimilation: bool
    p_canopy_water_change: float = 0.0
    p_dew_condensation: float = 0.0
    is_safe_for_agronomic_assimilation: bool = False
    recommended_covariance_multiplier: float = 1.0
    rejection_reason: Optional[str] = None
    instrument_state_flags: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "p_soil_water_change": round(self.p_soil_water_change, 4),
            "p_canopy_water_change": round(self.p_canopy_water_change, 4),
            "p_canopy_hydraulic_change": round(self.p_canopy_water_change, 4),
            "p_dew_condensation": round(self.p_dew_condensation, 4),
            "p_weather_motion_nuisance": round(self.p_weather_motion_nuisance, 4),
            "p_wind_aerodynamic_flutter": round(self.p_weather_motion_nuisance, 4),
            "p_instrument_nuisance": round(self.p_instrument_nuisance, 4),
            "p_instrument_thermal_drift": round(self.p_instrument_nuisance, 4),
            "p_geometry_nuisance": round(self.p_geometry_nuisance, 4),
            "p_geometry_displacement": round(self.p_geometry_nuisance, 4),
            "p_network_nuisance": round(self.p_network_nuisance, 4),
            "p_network_handover": round(self.p_network_nuisance, 4),
            "p_coexistence_nuisance": round(self.p_coexistence_nuisance, 4),
            "p_coexistence_interference": round(self.p_coexistence_nuisance, 4),
            "p_unknown_nuisance": round(self.p_unknown_nuisance, 4),
            "dominant_cause": self.dominant_cause,
            "is_safe_for_soil_assimilation": self.is_safe_for_soil_assimilation,
            "is_safe_for_agronomic_assimilation": self.is_safe_for_agronomic_assimilation,
            "recommended_covariance_multiplier": round(self.recommended_covariance_multiplier, 2),
            "rejection_reason": self.rejection_reason,
            "instrument_state_flags": self.instrument_state_flags,
        }


class BayesianNuisanceModel:
    """Evaluates multi-hypothesis nuisance attribution on candidate signal changes conforming to mesia.md §7, §14, §15, §24."""

    @staticmethod
    def attribute_cause(
        signal_delta_db: float = 0.0,
        temperature_delta_c: float = 0.0,
        antenna_displacement_m: float = 0.0,
        is_cell_handover: bool = False,
        is_machinery_active: bool = False,
        wind_speed_m_s: float = 0.0,
        relative_humidity_pct: float = 50.0,
        dew_point_depression_c: float = 10.0,
        is_foliar_link: bool = False,
        rain_rate_mm_h: float = 0.0,
        priors: Optional[Dict[str, float]] = None,
    ) -> NuisanceAttributionReport:
        """Calculate posterior cause probabilities using Bayesian updates across physical hypotheses."""
        import math

        # Default uninformative priors if not provided
        if not priors:
            priors = {
                "SOIL_WATER_CHANGE": 0.20,
                "CANOPY_HYDRAULIC_CHANGE": 0.15,
                "DEW_CONDENSATION": 0.10,
                "WIND_AERODYNAMIC_FLUTTER": 0.15,
                "INSTRUMENT_THERMAL_DRIFT": 0.10,
                "GEOMETRY_NUISANCE": 0.10,
                "NETWORK_NUISANCE": 0.10,
                "COEXISTENCE_NUISANCE": 0.05,
                "UNKNOWN_NUISANCE": 0.05,
            }

        def gaussian_likelihood(val: float, mu: float, sigma: float) -> float:
            return (1.0 / (sigma * math.sqrt(2 * math.pi))) * math.exp(-0.5 * ((val - mu) / sigma) ** 2)

        # 1. Soil change: Significant delta, calm wind, stable antenna, stable temp
        soil_mu = 1.8
        l_soil = gaussian_likelihood(abs(signal_delta_db), mu=soil_mu, sigma=1.2)
        if antenna_displacement_m > 0.02 or is_cell_handover or is_machinery_active:
            l_soil *= 0.05
        if wind_speed_m_s > 8.0:
            l_soil *= 0.25

        # 2. Canopy hydraulic change: Foliar link or daytime transpiration
        l_canopy = gaussian_likelihood(abs(signal_delta_db), mu=1.2, sigma=0.8)
        if is_foliar_link:
            l_canopy *= 2.0
        if is_cell_handover or antenna_displacement_m > 0.02:
            l_canopy *= 0.05

        # 3. Dew condensation: High RH (>80%), low dew depression (<=2°C), foliar link
        if relative_humidity_pct > 80.0 and dew_point_depression_c <= 2.5:
            l_dew = gaussian_likelihood(dew_point_depression_c, mu=0.5, sigma=1.0) * 3.0
            if is_foliar_link:
                l_dew *= 2.5
        else:
            l_dew = 0.005

        # 4. Wind flutter: High mechanical frequency / high wind speed
        if wind_speed_m_s > 4.0:
            l_wind = gaussian_likelihood(wind_speed_m_s, mu=12.0, sigma=5.0) * 2.5
            if is_foliar_link:
                l_wind *= 2.0
        else:
            l_wind = 0.01

        # 5. Instrument thermal drift: Temperature swings (|dT| > 5°C)
        if abs(temperature_delta_c) > 3.0:
            l_inst = gaussian_likelihood(abs(temperature_delta_c), mu=12.0, sigma=6.0) * 2.0
        else:
            l_inst = 0.02

        # 6. Geometry nuisance: Antenna displacement
        if antenna_displacement_m > 0.005:
            l_geom = gaussian_likelihood(antenna_displacement_m, mu=0.04, sigma=0.02) * 5.0
        else:
            l_geom = 0.01

        # 7. Network nuisance: Cell tower handover
        l_net = 0.98 if is_cell_handover else 0.01

        # 8. Coexistence: Agricultural machinery presence / transient RF interference
        l_coex = 0.95 if is_machinery_active else 0.01

        # 9. Unknown
        l_unknown = 0.01

        posteriors_unnorm = {
            "SOIL_WATER_CHANGE": priors.get("SOIL_WATER_CHANGE", 0.2) * l_soil,
            "CANOPY_HYDRAULIC_CHANGE": priors.get("CANOPY_HYDRAULIC_CHANGE", 0.15) * l_canopy,
            "DEW_CONDENSATION": priors.get("DEW_CONDENSATION", 0.10) * l_dew,
            "WIND_AERODYNAMIC_FLUTTER": priors.get("WIND_AERODYNAMIC_FLUTTER", 0.15) * l_wind,
            "INSTRUMENT_THERMAL_DRIFT": priors.get("INSTRUMENT_THERMAL_DRIFT", 0.10) * l_inst,
            "GEOMETRY_NUISANCE": priors.get("GEOMETRY_NUISANCE", 0.10) * l_geom,
            "NETWORK_NUISANCE": priors.get("NETWORK_NUISANCE", 0.10) * l_net,
            "COEXISTENCE_NUISANCE": priors.get("COEXISTENCE_NUISANCE", 0.05) * l_coex,
            "UNKNOWN_NUISANCE": priors.get("UNKNOWN_NUISANCE", 0.05) * l_unknown,
        }

        total = sum(posteriors_unnorm.values())
        if total <= 0:
            posteriors = priors
        else:
            posteriors = {k: v / total for k, v in posteriors_unnorm.items()}

        dominant = max(posteriors, key=posteriors.get)

        # Evaluation of safety for soil & agronomic assimilation
        p_soil = posteriors.get("SOIL_WATER_CHANGE", 0.0)
        p_canopy = posteriors.get("CANOPY_HYDRAULIC_CHANGE", 0.0)
        p_dew = posteriors.get("DEW_CONDENSATION", 0.0)
        p_wind = posteriors.get("WIND_AERODYNAMIC_FLUTTER", 0.0)
        p_inst = posteriors.get("INSTRUMENT_THERMAL_DRIFT", 0.0)
        p_geom = posteriors.get("GEOMETRY_NUISANCE", 0.0)
        p_net = posteriors.get("NETWORK_NUISANCE", 0.0)
        p_coex = posteriors.get("COEXISTENCE_NUISANCE", 0.0)
        p_unk = posteriors.get("UNKNOWN_NUISANCE", 0.0)

        # Legacy boolean compatibility: soil is safe if soil probability is dominant and high
        safe_soil = bool(p_soil >= 0.70 and p_geom < 0.15 and p_net < 0.15 and p_wind < 0.20)
        # Agronomic assimilation safe if soil or canopy is dominant
        safe_agronomic = bool((p_soil + p_canopy) >= 0.65 and p_geom < 0.15 and p_net < 0.15 and p_wind < 0.25)

        # Covariance inflation factor to protect ASMAE
        cov_mult = 1.0
        reason = None

        if p_wind >= 0.35 or wind_speed_m_s > 8.0:
            cov_mult = max(cov_mult, 25.0)
            reason = "WIND_AERODYNAMIC_FLUTTER_SUPPRESSED"
            safe_soil = False
            safe_agronomic = False
        elif p_geom >= 0.30 or antenna_displacement_m > 0.02:
            cov_mult = max(cov_mult, 100.0)
            reason = "ANTENNA_GEOMETRY_DISPLACEMENT_DETECTED"
            safe_soil = False
            safe_agronomic = False
        elif p_net >= 0.40 or is_cell_handover:
            cov_mult = max(cov_mult, 50.0)
            reason = "CELLULAR_NETWORK_HANDOVER_DETECTED"
            safe_soil = False
            safe_agronomic = False
        elif p_inst >= 0.40 or abs(temperature_delta_c) > 10.0:
            cov_mult = max(cov_mult, 10.0)
            reason = "INSTRUMENT_THERMAL_DRIFT_COMPENSATED"
            safe_soil = False
        elif p_dew >= 0.40:
            cov_mult = max(cov_mult, 5.0)
            reason = "DEW_CONDENSATION_SURFACE_FREE_WATER"
            safe_soil = False  # Dew does not change root-zone soil water!

        inst_flags = {
            "temperature_delta_c": round(temperature_delta_c, 1),
            "antenna_displacement_m": round(antenna_displacement_m, 4),
            "is_cell_handover": is_cell_handover,
            "is_machinery_active": is_machinery_active,
            "wind_speed_m_s": round(wind_speed_m_s, 1),
            "relative_humidity_pct": round(relative_humidity_pct, 1),
            "dew_point_depression_c": round(dew_point_depression_c, 2),
        }

        return NuisanceAttributionReport(
            p_soil_water_change=p_soil,
            p_instrument_nuisance=p_inst,
            p_geometry_nuisance=p_geom,
            p_network_nuisance=p_net,
            p_coexistence_nuisance=p_coex,
            p_weather_motion_nuisance=p_wind,
            p_unknown_nuisance=p_unk,
            dominant_cause=dominant,
            is_safe_for_soil_assimilation=safe_soil,
            p_canopy_water_change=p_canopy,
            p_dew_condensation=p_dew,
            is_safe_for_agronomic_assimilation=safe_agronomic,
            recommended_covariance_multiplier=cov_mult,
            rejection_reason=reason,
            instrument_state_flags=inst_flags,
        )
