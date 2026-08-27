"""
Layer 3.0 Dual Kc Evaporative Partitioning Engine
Implements FAO-56 dual crop coefficient methodology (Kcb basal transpiration + Ke soil evaporation).
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

from layer3_water.contracts.water_state import (
    SoilEvaporationState,
    PotentialWaterFlux,
    ActualWaterFlux,
    WaterFluxState,
)


class DualKcEngine:
    """Computes canopy basal transpiration Kcb and surface evaporation Ke from Layer 2 state."""

    @staticmethod
    def estimate_kcb_from_canopy(
        lai: float,
        fvc: float,
        kcb_min: float = 0.15,
        kcb_full: float = 1.15,
        plant_height_m: float = 1.0,
        wind_speed_2m_m_s: float = 2.0,
        rh_min_pct: float = 45.0,
    ) -> float:
        """Estimate basal crop coefficient Kcb from Layer 2 LAI and FVC with bidirectional climate correction.
        
        Kcb = Kcb_min + (Kcb_full - Kcb_min) * (1 - exp(-0.65 * LAI)) + Delta_Kc
        """
        lai_eff = max(0.0, lai)
        fvc_eff = max(0.0, min(1.0, fvc))
        
        # Canopy light extinction scaling
        canopy_expansion = 1.0 - math.exp(-0.65 * lai_eff)
        # Continuous weighted fusion of Beer-Lambert canopy expansion and fractional cover
        effective_cover = min(1.0, max(0.0, 0.60 * canopy_expansion + 0.40 * fvc_eff))
        
        kcb_base = kcb_min + (kcb_full - kcb_min) * effective_cover
        
        # Bidirectional FAO-56 climate adjustment for mid/full season (FAO-56 Eq. 70)
        # Delta_Kc = [0.04 * (u2 - 2) - 0.004 * (RH_min - 45)] * (h / 3)^0.3
        h_norm = max(0.1, min(5.0, plant_height_m))
        delta_kc = (0.04 * (wind_speed_2m_m_s - 2.0) - 0.004 * (rh_min_pct - 45.0)) * ((h_norm / 3.0) ** 0.3)
        
        # Apply adjustment proportionally to canopy cover
        kcb_adj = kcb_base + delta_kc * effective_cover
        return round(max(kcb_min, min(1.40, kcb_adj)), 3)

    @staticmethod
    def calculate_kc_max(
        kcb: float,
        plant_height_m: float = 1.0,
        wind_speed_2m_m_s: float = 2.0,
        rh_min_pct: float = 45.0,
    ) -> float:
        """Calculate upper limit of crop coefficient Kc_max per FAO-56 Eq. 72.
        
        Kc_max = max(1.2 + [0.04*(u2 - 2) - 0.004*(RH_min - 45)]*(h/3)^0.3, Kcb + 0.05)
        """
        h_norm = max(0.1, min(5.0, plant_height_m))
        climate_term = (0.04 * (wind_speed_2m_m_s - 2.0) - 0.004 * (rh_min_pct - 45.0)) * ((h_norm / 3.0) ** 0.3)
        kc_max = max(1.20 + climate_term, kcb + 0.05)
        return round(min(1.50, max(1.05, kc_max)), 3)

    @staticmethod
    def calculate_soil_evaporation_ke(
        kcb: float,
        kc_max: float,
        fvc: float,
        surface_storage_mm: float,
        max_surface_storage_mm: float = 12.0, # Readily Evaporable Water (REW)
        fraction_wetted_by_irrigation: float = 1.0,
        days_since_wetting: int = 0,
    ) -> Tuple[float, SoilEvaporationState]:
        """Compute soil evaporation coefficient Ke and evaporation memory state per FAO-56 Eq. 71.
        
        Ke = min(Kr * (Kc_max - Kcb), f_ew * Kc_max)
        """
        # Exposed and wetted soil fraction f_ew per FAO-56 Eq. 75
        f_c = max(0.0, min(0.99, fvc))
        f_w = max(0.1, min(1.0, fraction_wetted_by_irrigation))
        f_ew = max(0.01, min(1.0 - f_c, f_w))
        
        # Evaporation reduction factor Kr (Stage 1 energy-limited = 1.0; Stage 2 falling rate)
        if surface_storage_mm >= max_surface_storage_mm * 0.5:
            kr = 1.0
        elif surface_storage_mm > 0.0:
            kr = max(0.0, min(1.0, surface_storage_mm / (max_surface_storage_mm * 0.5)))
        else:
            # Stage 2 decay with time
            kr = max(0.0, math.exp(-0.35 * days_since_wetting))
            
        coefficient_headroom = max(0.0, kc_max - kcb)
        ke = max(
            0.0,
            min(kr * coefficient_headroom, f_ew * kc_max, coefficient_headroom),
        )
        
        evap_state = SoilEvaporationState(
            surface_storage_mm=round(surface_storage_mm, 2),
            max_surface_storage_mm=round(max_surface_storage_mm, 2),
            days_since_wetting=days_since_wetting,
            kr_reduction_factor=round(kr, 3),
            few_exposed_wetted_fraction=round(f_ew, 3),
        )
        return ke, evap_state

    @classmethod
    def partition_evapotranspiration(
        cls,
        et0_mm: float,
        kcb: float,
        ke: float,
        ks: float,
        precipitation_mm: float = 0.0,
        irrigation_mm: float = 0.0,
        deep_drainage_mm: float = 0.0,
        runoff_mm: float = 0.0,
        capillary_rise_mm: float = 0.0,
    ) -> WaterFluxState:
        """Partition potential demand and actual realized hydrological fluxes."""
        et0 = max(0.0, round(et0_mm, 2))
        kcb_val = max(0.0, round(kcb, 3))
        ke_val = max(0.0, round(ke, 3))
        ks_val = min(1.0, max(0.0, round(ks, 3)))
        
        pot = PotentialWaterFlux(
            et0_mm=et0,
            kcb=kcb_val,
            ke=ke_val,
        )
        
        tpot = pot.tpot_mm
        tact = round(ks_val * tpot, 2)
        esact = pot.espot_mm
        eta = round(tact + esact, 2)
        tdef = round(max(0.0, tpot - tact), 2)
        
        act = ActualWaterFlux(
            ks=ks_val,
            precipitation_mm=max(0.0, round(precipitation_mm, 2)),
            irrigation_mm=max(0.0, round(irrigation_mm, 2)),
            deep_drainage_mm=max(0.0, round(deep_drainage_mm, 2)),
            runoff_mm=max(0.0, round(runoff_mm, 2)),
            capillary_rise_mm=max(0.0, round(capillary_rise_mm, 2)),
            actual_transpiration_mm=tact,
            actual_soil_evaporation_mm=esact,
            actual_eta_mm=eta,
            transpiration_deficit_mm=tdef,
        )
        
        return WaterFluxState(potential=pot, actual=act)
