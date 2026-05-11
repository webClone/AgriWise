"""
Layer 3.1: Evapotranspiration Engine
Computes Reference ET (ET0) and Crop ET (ETc).

Methods:
  - FAO-56 Penman-Monteith (primary — uses L0 et0 module)
  - Hargreaves-Samani (fallback when wind/RH missing)
  - Dynamic Kc from NDVI (canopy cover proxy)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import math

# Re-export the canonical ET₀ calculators from L0
from layer0.environment.weather.et0 import (
    penman_monteith_et0,
    hargreaves_et0 as _hargreaves_scalar,
    select_et0 as _select_et0_scalar,
    wind_speed_at_2m,
    _extraterrestrial_radiation,
    _saturation_vapour_pressure,
)


class ETEngine:

    def __init__(self):
        # FAO-56 Kc values by growth stage (generic grass-reference)
        self.kc_defaults = {
            "initial": 0.3,
            "mid": 1.15,
            "end": 0.4,
        }

    # ================================================================
    # Penman-Monteith (vectorized over a DataFrame)
    # ================================================================

    def calculate_et0_penman_monteith(
        self,
        t_min: pd.Series,
        t_max: pd.Series,
        rh_mean: pd.Series,
        wind_2m: pd.Series,
        lat_deg: float,
        dates: pd.DatetimeIndex,
        rs: Optional[pd.Series] = None,
        elevation_m: float = 100.0,
    ) -> Tuple[pd.Series, pd.Series]:
        """FAO-56 Penman-Monteith ET₀ — vectorized over a daily DataFrame.

        Args:
            t_min:        Daily minimum temperature (°C)
            t_max:        Daily maximum temperature (°C)
            rh_mean:      Mean relative humidity (%)
            wind_2m:      Wind speed at 2 m (m/s)
            lat_deg:      Latitude in degrees
            dates:        DatetimeIndex of the series
            rs:           Incoming shortwave radiation (MJ/m²/day).
                          If None, estimated from temperature range.
            elevation_m:  Station elevation (m)

        Returns:
            (et0_series, method_series) — ET₀ mm/day and method used per day
        """
        doy = dates.dayofyear
        T = (t_min + t_max) / 2.0

        # Atmospheric pressure (Eq. 7)
        P = 101.3 * ((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26
        gamma = 0.000665 * P  # Psychrometric constant

        # Saturation vapour pressure
        es_min = 0.6108 * np.exp((17.27 * t_min) / (t_min + 237.3))
        es_max = 0.6108 * np.exp((17.27 * t_max) / (t_max + 237.3))
        es = (es_min + es_max) / 2.0

        # Actual vapour pressure
        ea = es * (rh_mean / 100.0)

        # Slope of saturation curve
        es_T = 0.6108 * np.exp((17.27 * T) / (T + 237.3))
        delta = (4098.0 * es_T) / ((T + 237.3) ** 2)

        # Extraterrestrial radiation Ra
        lat_rad = math.radians(lat_deg)
        dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
        dec = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
        ws = np.arccos(
            np.clip(-np.tan(lat_rad) * np.tan(dec), -1.0, 1.0)
        )
        Ra = (24 * 60 / np.pi) * 0.0820 * dr * (
            ws * np.sin(lat_rad) * np.sin(dec) +
            np.cos(lat_rad) * np.cos(dec) * np.sin(ws)
        )
        Ra = Ra.clip(lower=0.0)

        # Incoming solar radiation Rs
        if rs is not None:
            Rs = rs.clip(lower=0.0)
            method = pd.Series("penman_monteith", index=dates)
        else:
            # Hargreaves radiation estimate (Eq. 50)
            kRs = 0.16
            Rs = kRs * np.sqrt((t_max - t_min).clip(lower=0.0)) * Ra
            method = pd.Series("penman_monteith_reduced", index=dates)

        # Clear-sky radiation Rso (Eq. 37)
        Rso = (0.75 + 2e-5 * elevation_m) * Ra
        Rso = Rso.clip(lower=0.001)

        # Net shortwave Rns (albedo = 0.23)
        Rns = 0.77 * Rs

        # Net longwave Rnl (Eq. 39)
        sigma = 4.903e-9
        Tmin_K4 = (t_min + 273.16) ** 4
        Tmax_K4 = (t_max + 273.16) ** 4

        Rs_Rso = (Rs / Rso).clip(0.25, 1.0)

        Rnl = sigma * ((Tmin_K4 + Tmax_K4) / 2.0) * \
            (0.34 - 0.14 * np.sqrt(ea.clip(lower=0.0))) * \
            (1.35 * Rs_Rso - 0.35)

        Rn = Rns - Rnl
        G = 0.0  # Negligible for daily steps

        # FAO-56 PM equation (Eq. 6)
        numerator = (0.408 * delta * (Rn - G) +
                     gamma * (900.0 / (T + 273.0)) * wind_2m * (es - ea))
        denominator = delta + gamma * (1.0 + 0.34 * wind_2m)

        et0 = (numerator / denominator).clip(lower=0.0).round(2)
        return et0, method

    # ================================================================
    # Hargreaves-Samani (vectorized)
    # ================================================================

    def calculate_et0_hargreaves(
        self,
        t_min: pd.Series,
        t_max: pd.Series,
        lat_deg: float,
        dates: pd.DatetimeIndex,
    ) -> pd.Series:
        """Hargreaves-Samani Method (Temperature + Lat only).

        Good fallback when Radiation/Wind/Humidity are missing.
        Formula: 0.0023 × Ra × (Tmean + 17.8) × √(Tmax − Tmin)
        """
        ra = self._calculate_ra(lat_deg, dates)
        t_mean = (t_max + t_min) / 2.0
        tr = (t_max - t_min).clip(lower=0)
        et0 = 0.0023 * ra * (t_mean + 17.8) * np.sqrt(tr)
        return et0

    def _calculate_ra(self, lat_deg: float, dates: pd.DatetimeIndex) -> pd.Series:
        """Extraterrestrial Radiation (Ra) [mm/day equivalent]."""
        lat_rad = math.radians(lat_deg)
        doy = dates.dayofyear

        dr = 1 + 0.033 * np.cos(2 * math.pi * doy / 365)
        dec = 0.409 * np.sin(2 * math.pi * doy / 365 - 1.39)
        ws = np.arccos(
            np.clip(-np.tan(lat_rad) * np.tan(dec), -1.0, 1.0)
        )

        # Ra in MJ/m²/day, then × 0.408 to convert to mm
        ra_mj = (24 * 60 / math.pi) * 0.0820 * dr * (
            ws * np.sin(lat_rad) * np.sin(dec) +
            np.cos(lat_rad) * np.cos(dec) * np.sin(ws)
        )
        return pd.Series(ra_mj * 0.408, index=dates)

    # ================================================================
    # Smart ET₀ Selection (auto-detects best method from available data)
    # ================================================================

    def calculate_et0_auto(
        self,
        df: pd.DataFrame,
        lat_deg: float,
        dates: pd.DatetimeIndex,
        elevation_m: float = 100.0,
    ) -> Tuple[pd.Series, pd.Series]:
        """Automatically select the best ET₀ method based on available columns.

        Expected columns (all optional, more = better):
            t_min, t_max          — Required (minimum)
            rh_mean               — Enables Penman-Monteith
            wind_speed_2m         — Enables full PM (estimated if missing)
            shortwave_radiation   — Enables full PM (estimated if missing)

        Returns:
            (et0_series, method_series)
        """
        t_min = df["t_min"]
        t_max = df["t_max"]
        has_rh = "rh_mean" in df.columns and df["rh_mean"].notna().any()
        has_wind = "wind_speed_2m" in df.columns and df["wind_speed_2m"].notna().any()
        has_rs = "shortwave_radiation" in df.columns and df["shortwave_radiation"].notna().any()

        if has_rh:
            rh = df["rh_mean"]
            wind = df["wind_speed_2m"] if has_wind else pd.Series(2.0, index=dates)
            rs = df["shortwave_radiation"] if has_rs else None
            return self.calculate_et0_penman_monteith(
                t_min, t_max, rh, wind, lat_deg, dates,
                rs=rs, elevation_m=elevation_m,
            )
        else:
            et0 = self.calculate_et0_hargreaves(t_min, t_max, lat_deg, dates)
            method = pd.Series("hargreaves", index=dates)
            return et0, method

    # ================================================================
    # Crop Coefficient Kc (NDVI-dynamic)
    # ================================================================

    def calculate_dynamic_kc(
        self,
        ndvi_series: pd.Series,
        stage_label: str = "vegetative",
    ) -> pd.Series:
        """Adjust Kc based on NDVI (Canopy Cover Proxy).

        Baseline Kc from stage, modified by fractional cover estimated from NDVI.
        FAO-56 approach: Kc = Kc_min + (Kc_full − Kc_min) × Fc
        where Fc ≈ 1.2 × NDVI − 0.2 (clipped [0, 1])
        """
        # Base Kc from stage
        base_kc = self.kc_defaults["mid"]
        if "emergence" in stage_label or "initial" in stage_label:
            base_kc = self.kc_defaults["initial"]
        elif "maturity" in stage_label or "harvest" in stage_label:
            base_kc = self.kc_defaults["end"]

        kc_min = 0.15  # Bare soil evaporation
        fc = (1.2 * ndvi_series - 0.2).clip(0, 1)
        kc_dynamic = kc_min + (base_kc - kc_min) * fc
        return kc_dynamic

    # ================================================================
    # Crop Evapotranspiration (ETc)
    # ================================================================

    def compute_etc(self, et0: pd.Series, kc: pd.Series) -> pd.Series:
        """ETc = ET₀ × Kc (FAO-56 Eq. 58)."""
        return et0 * kc


# Singleton
et_engine = ETEngine()
