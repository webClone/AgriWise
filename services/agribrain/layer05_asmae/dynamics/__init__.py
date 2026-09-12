"""ASMAE Dynamics — Biophysical Transition Models.

Provides degree-day plant growth curves and hydraulic soil drying dynamics.
"""

from .plant_growth import (
    CropGrowthParameters,
    calculate_daily_gdd,
    step_plant_growth,
    temperature_inhibition_factor,
)
from .soil_drying import (
    SoilHydraulicParameters,
    compute_transpiration_reduction_ks,
    step_soil_drying,
)

__all__ = [
    "CropGrowthParameters",
    "calculate_daily_gdd",
    "step_plant_growth",
    "temperature_inhibition_factor",
    "SoilHydraulicParameters",
    "compute_transpiration_reduction_ks",
    "step_soil_drying",
]

