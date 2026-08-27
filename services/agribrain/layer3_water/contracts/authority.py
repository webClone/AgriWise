"""
Layer 3.0 Water Physics Authority Contract
Defines source fidelity, epistemic authority, and numerical modeling mode of hydrological states.
"""

from enum import Enum


class WaterPhysicsAuthority(str, Enum):
    """Authority level of water state estimates."""
    OBSERVED = "OBSERVED"        # Direct in-situ sensor measurement (e.g. soil probe, lysimeter, flux tower)
    ASSIMILATED = "ASSIMILATED"  # Fused state from forward model constrained by Layer 2 biological evidence
    MODELLED = "MODELLED"        # Pure forward prognostic simulation (FAO-56 dual Kc + layered water balance)
    FORECAST = "FORECAST"        # Projected future trajectory across weather forecast ensembles


class HydrologyMode(str, Enum):
    """Numerical physical solver fidelity for soil water movement."""
    FAO56_LAYERED_BUCKET = "FAO56_LAYERED_BUCKET"  # Multi-layer cascading tipping-bucket with percolation
    RICHARDS_1D = "RICHARDS_1D"                    # 1D finite-difference Richards equation with Van Genuchten retention


class SolverFidelity(str, Enum):
    """Physical solver execution fidelity self-reported by hydrological engine."""
    EMPIRICAL_BUCKET = "EMPIRICAL_BUCKET"          # FAO-56 cascading storage solver
    HYDRAULIC_NUMERICAL = "HYDRAULIC_NUMERICAL"    # Continuous differential Richards solver
