"""
Layer 3.1: Evapotranspiration Engine
Computes Reference ET (ET0) and Crop ET (ETc).
Methods: Hargreaves (Baseline), Penman-Monteith (Placeholder).
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any
import math

class ETEngine:
    
    def __init__(self):
        # Default FAO Kc values (generic)
        self.kc_defaults = {
            "initial": 0.3,
            "mid": 1.15,
            "end": 0.4
        }
        
    def calculate_et0_hargreaves(self, 
                                 t_min: pd.Series, 
                                 t_max: pd.Series, 
                                 lat_deg: float, 
                                 dates: pd.DatetimeIndex) -> pd.Series:
        """
        Hargreaves-Samani Method (Temperature + Lat only).
        Good fallback when Radiation/Wind/Humidity missing.
        Formula: 0.0023 * Ra * (Tmean + 17.8) * sqrt(Tmax - Tmin)
        """
        # 1. Extraterrestrial Radiation (Ra) calculation based on Latitude & Day of Year
        ra = self._calculate_ra(lat_deg, dates)
        
        t_mean = (t_max + t_min) / 2.0
        
        # 0.0023 * Ra * (Tmean + 17.8) * (Tmax - Tmin)^0.5
        # Handle negative sqrt? Tmax should be > Tmin. Clip to 0.
        tr = (t_max - t_min).clip(lower=0)
        
        et0 = 0.0023 * ra * (t_mean + 17.8) * np.sqrt(tr)
        return et0

    def _calculate_ra(self, lat_deg: float, dates: pd.DatetimeIndex) -> pd.Series:
        """
        Estimate Extraterrestrial Radiation (Ra) [mm/day].
        """
        lat_rad = math.radians(lat_deg)
        doy = dates.dayofyear
        
        # Inverse relative distance Earth-Sun
        dr = 1 + 0.033 * np.cos(2 * math.pi * doy / 365)
        # Solar declination
        delta = 0.409 * np.sin(2 * math.pi * doy / 365 - 1.39)
        # Sunset hour angle
        ws = np.arccos(-np.tan(lat_rad) * np.tan(delta))
        
        # Ra
        ra = (24 * 60 / math.pi) * 0.0820 * dr * (
            ws * np.sin(lat_rad) * np.sin(delta) + 
            np.cos(lat_rad) * np.cos(delta) * np.sin(ws)
        )
        return pd.Series(ra, index=dates)

    def calculate_dynamic_kc(self, 
                             ndvi_series: pd.Series, 
                             stage_label: str = "vegetative") -> pd.Series:
        """
        Adjust Kc based on NDVI (Canopy Cover Proxy).
        Baseline Kc from stage, modified by NDVI.
        """
        # 1. Base Kc from Stage (Simple lookup)
        base_kc = self.kc_defaults["mid"]
        if "emergence" in stage_label or "initial" in stage_label:
            base_kc = self.kc_defaults["initial"]
        elif "maturity" in stage_label or "harvest" in stage_label:
            base_kc = self.kc_defaults["end"]
            
        # 2. NDVI Factor (0.2 -> 0.8 range mapping)
        # Low NDVI (<0.2) reduces Kc (bare soil)
        # High NDVI (>0.7) maximizes Kc
        # Simple linear scaler: f_ndvi = (NDVI - 0.2) / (0.8 - 0.2) clipped 0-1
        # Then Kc_adj = Kc_table * f_ndvi? Or Kc = Kc_min + (Kc_max - Kc_min) * f_ndvi
        
        # Using specific FAO-style adjustment:
        # Kc = Kc_min + (Kc_full - Kc_min) * F_c (fraction cover)
        # F_c approx ~ 1.2 * NDVI - 0.2
        
        kc_min = 0.15 # Bare soil evap
        kc_max = 1.2
        
        fc = (1.2 * ndvi_series - 0.2).clip(0, 1)
        
        # Blend: If we have stage info, use it as 'potential', scaled by actual cover
        kc_dynamic = kc_min + (base_kc - kc_min) * fc
        
        return kc_dynamic

    def compute_etc(self, et0: pd.Series, kc: pd.Series) -> pd.Series:
        return et0 * kc

# Singleton
et_engine = ETEngine()
