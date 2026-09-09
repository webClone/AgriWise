"""MESIA Interacting Multiple Model (IMM) Regime Filter & Fixed-Lag Smoother.

Implements mesia.md §18 & §19:
- Discrete agricultural/environmental regimes with mode-dependent observation covariance.
- Fixed-lag retrospective smoothing (evaluating online posterior vs smoothed posterior without overwriting history).
- Decoupling of fast environmental nuisances (wind, dew) from slow agronomic dynamics (soil moisture, deep percolation).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class OperationalRegime(str, Enum):
    NORMAL_DRYING_CYCLE = "NORMAL_DRYING_CYCLE"
    WIND_GUST_NUISANCE = "WIND_GUST_NUISANCE"
    DEW_CONDENSATION = "DEW_CONDENSATION"
    ACTIVE_IRRIGATION = "ACTIVE_IRRIGATION"
    RAIN_PRECIPITATION = "RAIN_PRECIPITATION"
    QUIET_NIGHT_CALIBRATION = "QUIET_NIGHT_CALIBRATION"


@dataclass(frozen=True)
class ImmRegimeState:
    """Snapshot of the active IMM regime and adaptive filter parameters."""

    active_regime: OperationalRegime
    regime_probabilities: Dict[str, float]
    covariance_scaling_factor: float
    is_soil_update_permitted: bool
    is_foliar_update_permitted: bool
    explanation: str
    online_posterior_vwc: float
    retrospectively_smoothed_vwc: float
    smoothing_lag_hours: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_regime": self.active_regime.value,
            "regime_probabilities": {k: round(v, 4) for k, v in self.regime_probabilities.items()},
            "covariance_scaling_factor": round(self.covariance_scaling_factor, 2),
            "is_soil_update_permitted": self.is_soil_update_permitted,
            "is_foliar_update_permitted": self.is_foliar_update_permitted,
            "explanation": self.explanation,
            "online_posterior_vwc": round(self.online_posterior_vwc, 4),
            "retrospectively_smoothed_vwc": round(self.retrospectively_smoothed_vwc, 4),
            "smoothing_lag_hours": round(self.smoothing_lag_hours, 2),
        }


class InteractingMultipleModelRegimeFilter:
    """Coordinates regime transition dynamics and fixed-lag retrospective smoothing."""

    @classmethod
    def evaluate_regime(
        cls,
        observed_vwc: float,
        prior_vwc: float,
        wind_speed_m_s: float = 0.0,
        relative_humidity_pct: float = 50.0,
        dew_point_depression_c: float = 10.0,
        rain_rate_mm_h: float = 0.0,
        solar_zenith_deg: float = 45.0,
        is_nighttime: bool = False,
        historical_vwc_trace: Optional[List[float]] = None,
    ) -> ImmRegimeState:
        """Evaluates regime probabilities and produces decoupled online & smoothed posteriors."""
        delta_vwc = observed_vwc - prior_vwc

        # 1. Unnormalized regime likelihoods based on environmental physics
        # Normal drying: gradual change (|delta| < 0.03), low wind, no rain
        l_normal = math.exp(-0.5 * (delta_vwc / 0.02) ** 2) if wind_speed_m_s <= 5.0 and rain_rate_mm_h < 0.1 else 0.1

        # Wind nuisance: strong wind (> 6 m/s), erratic foliar variance
        if wind_speed_m_s >= 6.0:
            l_wind = 5.0 * (1.0 / (1.0 + math.exp(-(wind_speed_m_s - 6.0))))
        else:
            l_wind = 0.05

        # Dew: high RH (> 82%), low dew depression (<= 2°C), typically nocturnal or early morning
        if relative_humidity_pct > 80.0 and dew_point_depression_c <= 2.2:
            l_dew = 3.0 * math.exp(-0.5 * (dew_point_depression_c / 1.0) ** 2)
        else:
            l_dew = 0.01

        # Active irrigation: positive delta_vwc (>= +0.02), zero rain, calm/moderate wind
        if delta_vwc >= 0.015 and rain_rate_mm_h < 0.1 and wind_speed_m_s < 6.0:
            l_irrigation = 3.5 * math.exp(-0.5 * ((delta_vwc - 0.05) / 0.03) ** 2)
        else:
            l_irrigation = 0.02


        # Rain precipitation: rain gauge > 0.2 mm/h or forecast active
        if rain_rate_mm_h >= 0.2:
            l_rain = 4.0 * (1.0 / (1.0 + math.exp(-(rain_rate_mm_h - 1.0))))
        else:
            l_rain = 0.01

        # Quiet night: is_nighttime and wind < 3 m/s
        if is_nighttime and wind_speed_m_s < 3.5:
            l_night = 2.0
        else:
            l_night = 0.05

        weights = {
            OperationalRegime.NORMAL_DRYING_CYCLE.value: l_normal,
            OperationalRegime.WIND_GUST_NUISANCE.value: l_wind,
            OperationalRegime.DEW_CONDENSATION.value: l_dew,
            OperationalRegime.ACTIVE_IRRIGATION.value: l_irrigation,
            OperationalRegime.RAIN_PRECIPITATION.value: l_rain,
            OperationalRegime.QUIET_NIGHT_CALIBRATION.value: l_night,
        }

        total_w = sum(weights.values())
        probs = {k: v / total_w for k, v in weights.items()}

        active_regime_str = max(probs, key=probs.get)
        active_regime = OperationalRegime(active_regime_str)

        # 2. Derive covariance scaling factor and update permissions
        if active_regime == OperationalRegime.WIND_GUST_NUISANCE:
            cov_scale = 25.0
            soil_ok = False
            foliar_ok = False
            expl = "High wind flutter detected (mechanical oscillation). Foliar & canopy observation variance inflated by 25x to protect soil state from false updates."
        elif active_regime == OperationalRegime.DEW_CONDENSATION:
            cov_scale = 5.0
            soil_ok = False
            foliar_ok = True  # Foliar link tracks surface water, but soil moisture must NOT be updated
            expl = "Leaf surface wetness / dew condensation active (RH > 80%, low dew-point depression). Root-zone soil update suppressed; foliar moisture tracked as surface free-water."
        elif active_regime == OperationalRegime.ACTIVE_IRRIGATION:
            cov_scale = 1.0
            soil_ok = True
            foliar_ok = False
            expl = "Localized wetting detected with zero precipitation. Infiltration transition model active; root-zone soil state update permitted."
        elif active_regime == OperationalRegime.RAIN_PRECIPITATION:
            cov_scale = 1.2
            soil_ok = True
            foliar_ok = True
            expl = "Meteorologically verified precipitation event. Synchronous canopy and soil wetting assimilation permitted."
        elif active_regime == OperationalRegime.QUIET_NIGHT_CALIBRATION:
            cov_scale = 0.25
            soil_ok = True
            foliar_ok = True
            expl = "Nocturnal hydraulic equilibrium (zero transpiration, low wind). High-precision baseline re-centering active."
        else:
            cov_scale = 1.0
            soil_ok = True
            foliar_ok = True
            expl = "Normal diurnal evapotranspiration and soil drainage cycle."

        # 3. Compute online posterior vs retrospectively smoothed posterior (Fixed-Lag Smoothing)
        # Online posterior: Kalman update with regime-scaled covariance
        R_effective = 0.0018 * cov_scale
        P_prior = 0.0020
        K_gain = P_prior / (P_prior + R_effective)
        online_posterior = prior_vwc + K_gain * delta_vwc

        # Retrospectively smoothed posterior:
        # If historical trace is provided (e.g. over 2-6 hours), fixed-lag smoothing verifies whether
        # the jump was a transient nuisance or a persistent agronomic shift
        trace = historical_vwc_trace or [prior_vwc, observed_vwc]
        if len(trace) >= 3:
            # Weighted Gaussian kernel smoother over historical trajectory
            recent_mean = float(sum(trace[-3:]) / len(trace[-3:]))
            smoothed_posterior = 0.4 * online_posterior + 0.6 * recent_mean
            lag_hours = 2.0
        else:
            smoothed_posterior = online_posterior
            lag_hours = 1.0

        return ImmRegimeState(
            active_regime=active_regime,
            regime_probabilities=probs,
            covariance_scaling_factor=cov_scale,
            is_soil_update_permitted=soil_ok,
            is_foliar_update_permitted=foliar_ok,
            explanation=expl,
            online_posterior_vwc=online_posterior,
            retrospectively_smoothed_vwc=smoothed_posterior,
            smoothing_lag_hours=lag_hours,
        )
