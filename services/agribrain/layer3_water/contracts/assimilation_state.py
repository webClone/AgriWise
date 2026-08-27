"""
Layer 3.0 Closed-Loop Assimilation and Boundary Contracts
Defines receipts and observation vectors exchanged between Layer 2 (Vegetation), Layer 3 (Water), and Layer 4 (Bio Processes).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

from layer2_contracts.state_contracts import VegetationState, CropKnowledgeAuthority


class WaterSignalType(str, Enum):
    """Classification of biological water response signals from Layer 2."""
    TRANSPIRATION_RESPONSE = "TRANSPIRATION_RESPONSE"   # Canopy conductance / stomatal closure signal
    CANOPY_COOLING_RESPONSE = "CANOPY_COOLING_RESPONSE" # Thermal infrared evaporative cooling anomaly
    SPECTRAL_WATER_RESPONSE = "SPECTRAL_WATER_RESPONSE" # SWIR/NIR canopy water thickness index anomaly
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SoilObservationVector:
    """Multi-source observation vector for Layer 3 data assimilation filter."""
    timestamp: datetime
    soil_probe_moisture_profile: Optional[List[float]] = None     # In-situ TDR/capacitance probe profile (m3/m3)
    satellite_surface_moisture_m3_m3: Optional[float] = None      # SMAP/Sentinel-1 surface soil moisture (m3/m3)
    canopy_cooling_differential_c: Optional[float] = None         # (Tc - Ta) thermal radiometer constraint
    flux_tower_eta_mm: Optional[float] = None                     # In-situ lysimeter / eddy covariance ETa (mm)
    observation_uncertainties: Dict[str, float] = field(default_factory=dict)
    provenance_sources: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Layer3HydrologicalConstraintReceipt:
    """Hydrological boundary constraint feedback emitted by Layer 3 to Layer 2."""
    plot_id: str
    timestamp: datetime
    transpiration_constraint_factor: float       # Ks ∈ [0.0, 1.0] (1.0 = no restriction, 0.0 = total shutdown)
    transpiration_deficit_mm: float              # T_pot - T_act (mm/day)
    soil_water_availability_ratio: float         # (Theta - Theta_wp) / (Theta_fc - Theta_wp)
    root_zone_depletion_fraction: float          # Dr / TAW ∈ [0.0, 1.0]
    ks_uncertainty_sigma: float                  # Uncertainty on Ks
    authority: str = "HYDROLOGICAL_PROCESS_CONSTRAINT"


# Backward compatibility alias
Layer3ToLayer2Receipt = Layer3HydrologicalConstraintReceipt


@dataclass(frozen=True)
class Layer3ToLayer4BoundaryReceipt:
    """Canonical biophysical boundary contract emitted by Layer 3 Water Engine to Layer 4 Biological Engine.
    
    Contains exclusively physical water availability, transpiration limitation, and historical stress memory,
    without raw remote sensing, soil hydraulic mechanics, or irrigation hardware actuation details.
    """
    plot_id: str
    timestamp: datetime
    
    # 1. Immediate physical state & limitation
    stress_factor_ks: float                     # Ks ∈ [0.0, 1.0] (Stomatal & transpiration limitation factor)
    transpiration_deficit_mm: float             # T_deficit = (1 - Ks) * T_pot (mm/day)
    transpiration_deficit_sigma_mm: float       # Quadrature uncertainty on T_deficit (mm/day)
    total_available_water_mm: float             # TAW = (Theta_fc - Theta_wp) * Zr * 10 (mm)
    readily_available_water_mm: float           # RAW = p * TAW (mm)
    root_zone_depletion_mm: float               # Dr from closed soil moisture storage (mm)
    water_availability_ratio: float             # (Theta - Theta_wp) / (Theta_fc - Theta_wp) ∈ [0.0, 1.0]
    
    # 2. Historical hydraulic stress memory (drives biological lag & senescence)
    cumulative_transpiration_deficit_mm: float = 0.0     # Sum(Tdeficit) over current growth cycle (mm)
    consecutive_days_under_limitation: int = 0          # Continuous days with Ks < 0.95
    severe_limitation_days_count: int = 0               # Total days with Ks < 0.50
    integrated_hydraulic_stress_index: float = 0.0      # Sum((1 - Ks) * VPD) in kPa*days
    water_stress_recovery_rate: float = 1.0             # dKs/dt post-irrigation/rain
    drought_exposure_class: str = "NONE"                # "NONE", "ACUTE_MILD", "CHRONIC_MODERATE", "SEVERE_PROLONGED"

    # 3. Provenance, Authority & Confidence
    physics_authority: str = "MODELLED"         # Epistemic authority
    solver_fidelity: str = "EMPIRICAL_BUCKET"   # Numerical solver fidelity
    water_confidence_score: float = 0.92        # Multi-source simulation confidence
    assimilation_status: str = "NONE"           # "ASSIMILATED_IN_SITU", "ASSIMILATED_SATELLITE", "PROGNOSTIC_MODEL"
