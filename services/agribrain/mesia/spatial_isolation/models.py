"""MESIA Spatial Sensitivity & Causal Attribution Data Models.

Mathematical & physical models conforming to:
- Principle P-08: ASMAE owns biological posterior; MESIA provides radio channel evidence.
- Physical footprint containment: eta_sens,plot +/- sigma_eta.
- Conservative lower-bound gating: eta_lower = eta_sens,plot - k * sigma_eta.
- 5-Tier spatial classification (CORE_PROTECTED to EXT_QUARANTINED).
- Structured external nuisance vector x_ext.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SpatialClassificationTier(str, Enum):
    """5-Tier spatial gating classification for radio observations."""
    CORE_PROTECTED = "CORE_PROTECTED"                         # eta_lower,plot >= 0.95 and eta_lower,core >= 0.80
    PLOT_ADMITTED_GUARDED = "PLOT_ADMITTED_GUARDED"           # 0.80 <= eta_lower,plot < 0.95
    BOUNDARY_AMBIGUOUS = "BOUNDARY_AMBIGUOUS"                 # 0.60 <= eta_lower,plot < 0.80
    EXTERNAL_DOMINANT_CANDIDATE = "EXTERNAL_DOMINANT_CANDIDATE" # 0.50 <= eta_lower,plot < 0.60
    EXT_QUARANTINED = "EXT_QUARANTINED"                       # eta_lower,plot < 0.50


class FootprintGeometryType(str, Enum):
    """Underlying electromagnetic scattering footprint geometry."""
    FRESNEL_ELLIPSE_SPECULAR = "FRESNEL_ELLIPSE_SPECULAR"   # GNSS-R ground reflection
    BISTATIC_CHORD_CYLINDER = "BISTATIC_CHORD_CYLINDER"     # Cellular forward-scatter
    TERRAIN_SCATTER_SECTOR = "TERRAIN_SCATTER_SECTOR"       # Broadcast UHF ground wave
    MULTIPATH_SPATIAL_PROFILE = "MULTIPATH_SPATIAL_PROFILE" # Wi-Fi CSI subcarrier delay
    RADAR_ISORANGE_DOPPLER = "RADAR_ISORANGE_DOPPLER"       # Spaceborne SAR / CYGNSS track


@dataclass(frozen=True)
class ContainmentInterval:
    """Rigorous uncertainty interval for spatial sensitivity containment."""
    eta_hat: float           # Estimated nominal fraction [0.0, 1.0]
    sigma_eta: float         # Standard uncertainty of the containment fraction
    k_coverage: float        # Coverage factor (default k = 2.0 for ~95% confidence)
    eta_lower: float         # Conservative lower bound: max(0.0, eta_hat - k * sigma_eta)
    eta_upper: float         # Conservative upper bound: min(1.0, eta_hat + k * sigma_eta)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eta_hat": round(self.eta_hat, 4),
            "sigma_eta": round(self.sigma_eta, 4),
            "k_coverage": round(self.k_coverage, 2),
            "eta_lower": round(self.eta_lower, 4),
            "eta_upper": round(self.eta_upper, 4),
        }


@dataclass(frozen=True)
class StateSpecificSensitivity:
    """State-specific sensitivity containment intervals across biological and physical states."""
    theta_v_soil: ContainmentInterval       # Volumetric soil water content sensitivity
    vwc_vegetation: ContainmentInterval     # Canopy foliar water content sensitivity
    surface_roughness_s: ContainmentInterval # Micro-topography / roughness sensitivity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "theta_v_soil": self.theta_v_soil.to_dict(),
            "vwc_vegetation": self.vwc_vegetation.to_dict(),
            "surface_roughness_s": self.surface_roughness_s.to_dict(),
        }


@dataclass(frozen=True)
class StructuredExternalState:
    """Structured vector of candidate external physical nuisance sources x_ext."""
    x_road: float = 0.0          # Metallic vehicles, asphalt reflection / transmission
    x_neighbor: float = 0.0      # Adjacent parcel center-pivot irrigation or crop canopy
    x_infra: float = 0.0         # Solar arrays, farm buildings, metal fence reflections
    x_terrain: float = 0.0       # Surrounding ditches, hills, topographic slopes
    x_atm: float = 0.0           # Atmospheric refractivity variations, sirocco ducting
    x_rf: float = 0.0            # External radio frequency interference / adjacent emissions
    x_unexplained: float = 0.0   # Residual unmodeled out-of-plot variance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x_road": round(self.x_road, 4),
            "x_neighbor": round(self.x_neighbor, 4),
            "x_infra": round(self.x_infra, 4),
            "x_terrain": round(self.x_terrain, 4),
            "x_atm": round(self.x_atm, 4),
            "x_rf": round(self.x_rf, 4),
            "x_unexplained": round(self.x_unexplained, 4),
            "total_external_energy": round(
                self.x_road + self.x_neighbor + self.x_infra + self.x_terrain + self.x_atm + self.x_rf + self.x_unexplained,
                4
            ),
        }


@dataclass(frozen=True)
class SpatialAttributionConfidence:
    """Six-component spatial attribution confidence breakdown."""
    c_geometry: float   # Receiver/transmitter antenna 3D geodetic survey quality
    c_model: float      # Footprint scattering model fidelity (Fresnel/P.833/Oh)
    c_coherence: float  # Multi-temporal spatial track consistency
    c_reference: float  # Withheld reference sensor / calibration anchor agreement
    c_dem: float        # Digital Elevation Model resolution & slope accuracy
    c_tracking: float   # Ephemeris / orbit / mast bearing tracking confidence
    composite_score: float # Weighted composite spatial confidence [0.0, 1.0]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "c_geometry": round(self.c_geometry, 3),
            "c_model": round(self.c_model, 3),
            "c_coherence": round(self.c_coherence, 3),
            "c_reference": round(self.c_reference, 3),
            "c_dem": round(self.c_dem, 3),
            "c_tracking": round(self.c_tracking, 3),
            "composite_score": round(self.composite_score, 4),
            "meets_admission_threshold": bool(self.composite_score >= 0.70),
        }


@dataclass(frozen=True)
class SpatialIsolationReport:
    """Comprehensive spatial sensitivity and causal attribution report."""
    observation_id: str
    radio_modality: str
    geometry_type: FootprintGeometryType
    classification_tier: SpatialClassificationTier
    
    # Containment fractions
    containment_plot: ContainmentInterval
    containment_core: ContainmentInterval
    eta_external_leakage: float
    eta_geometric_diagnostic: float # eta_geom (cross-sectional area metric for audit)
    
    # State-specific sensitivity intervals
    state_sensitivities: StateSpecificSensitivity
    
    # Buffer and geometry specifications
    buffer_width_m: float
    footprint_major_axis_m: float
    footprint_minor_axis_m: float
    smearing_length_m: float
    
    # Causal attribution & nuisance state
    structured_external_state: StructuredExternalState
    attribution_confidence: SpatialAttributionConfidence
    
    # Covariance & identifiability
    base_covariance_r0: float
    effective_covariance_r_eff: float
    covariance_scale_factor: float
    jacobian_condition_number: float
    biophysical_identifiability_status: str # "HIGH", "ACCEPTABLE", "DEGRADED_COLLINEAR"
    
    # Action & audit notes
    is_safe_for_root_zone_update: bool
    is_safe_for_canopy_update: bool
    quarantine_reason: Optional[str]
    scientific_justification: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "radio_modality": self.radio_modality,
            "geometry_type": self.geometry_type.value,
            "classification_tier": self.classification_tier.value,
            "containment_plot": self.containment_plot.to_dict(),
            "containment_core": self.containment_core.to_dict(),
            "eta_external_leakage": round(self.eta_external_leakage, 4),
            "eta_geometric_diagnostic": round(self.eta_geometric_diagnostic, 4),
            "state_sensitivities": self.state_sensitivities.to_dict(),
            "buffer_width_m": round(self.buffer_width_m, 2),
            "footprint_major_axis_m": round(self.footprint_major_axis_m, 2),
            "footprint_minor_axis_m": round(self.footprint_minor_axis_m, 2),
            "smearing_length_m": round(self.smearing_length_m, 2),
            "structured_external_state": self.structured_external_state.to_dict(),
            "attribution_confidence": self.attribution_confidence.to_dict(),
            "base_covariance_r0": round(self.base_covariance_r0, 6),
            "effective_covariance_r_eff": round(self.effective_covariance_r_eff, 6),
            "covariance_scale_factor": round(self.covariance_scale_factor, 2),
            "jacobian_condition_number": round(self.jacobian_condition_number, 2),
            "biophysical_identifiability_status": self.biophysical_identifiability_status,
            "is_safe_for_root_zone_update": self.is_safe_for_root_zone_update,
            "is_safe_for_canopy_update": self.is_safe_for_canopy_update,
            "quarantine_reason": self.quarantine_reason,
            "scientific_justification": self.scientific_justification,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class ExternalAttributionVector:
    """Decomposition of external nuisance sources and Bayesian hypotheses."""
    dominant_hypothesis: str
    hypothesis_posteriors: Dict[str, float]
    attribution_entropy_bits: float
    adjacent_plot_irrigation_fraction: float
    road_metal_reflection_fraction: float
    windbreak_foliage_fraction: float
    canal_water_fraction: float
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dominant_hypothesis": self.dominant_hypothesis,
            "hypothesis_posteriors": {k: round(v, 4) for k, v in self.hypothesis_posteriors.items()},
            "attribution_entropy_bits": round(self.attribution_entropy_bits, 3),
            "adjacent_plot_irrigation_fraction": round(self.adjacent_plot_irrigation_fraction, 3),
            "road_metal_reflection_fraction": round(self.road_metal_reflection_fraction, 3),
            "windbreak_foliage_fraction": round(self.windbreak_foliage_fraction, 3),
            "canal_water_fraction": round(self.canal_water_fraction, 3),
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class SpatialAuditRecord:
    """Individual radio observation spatial gating and audit result."""
    observation_id: str
    modality: str
    carrier_freq_hz: float
    footprint_shape: str
    footprint_centroid_enu_m: Tuple[float, float]
    footprint_major_axis_m: float
    footprint_minor_axis_m: float
    containment_plot: ContainmentInterval
    containment_core: ContainmentInterval
    eta_external_leakage: float
    eta_geometric_diagnostic: float
    state_specific_sensitivities: StateSpecificSensitivity
    classification_tier: SpatialClassificationTier
    covariance_scale_factor: float
    is_safe_for_root_zone_update: bool
    is_safe_for_canopy_update: bool
    quarantine_reason: Optional[str]
    scientific_justification: str
    external_attribution: ExternalAttributionVector

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "modality": self.modality,
            "carrier_freq_hz": self.carrier_freq_hz,
            "footprint_shape": self.footprint_shape,
            "footprint_centroid_enu_m": list(self.footprint_centroid_enu_m),
            "footprint_major_axis_m": round(self.footprint_major_axis_m, 2),
            "footprint_minor_axis_m": round(self.footprint_minor_axis_m, 2),
            "containment_plot": self.containment_plot.to_dict(),
            "containment_core": self.containment_core.to_dict(),
            "eta_external_leakage": round(self.eta_external_leakage, 4),
            "eta_geometric_diagnostic": round(self.eta_geometric_diagnostic, 4),
            "state_specific_sensitivities": self.state_specific_sensitivities.to_dict(),
            "classification_tier": self.classification_tier.value,
            "covariance_scale_factor": round(self.covariance_scale_factor, 2),
            "is_safe_for_root_zone_update": self.is_safe_for_root_zone_update,
            "is_safe_for_canopy_update": self.is_safe_for_canopy_update,
            "quarantine_reason": self.quarantine_reason,
            "scientific_justification": self.scientific_justification,
            "external_attribution": self.external_attribution.to_dict(),
        }


@dataclass(frozen=True)
class PlotSpatialIsolationSummary:
    """Aggregated parcel-level spatial isolation health and audit summary."""
    plot_id: str
    origin_geodetic: Tuple[float, float]
    plot_area_m2: float
    core_area_m2: float
    buffer_width_m: float
    overall_isolation_status: str
    mean_plot_containment: float
    mean_external_leakage: float
    zero_external_leakage_verified: bool
    total_observables_evaluated: int
    classification_breakdown: Dict[str, int]
    audit_records: List[SpatialAuditRecord]
    recommended_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plot_id": self.plot_id,
            "origin_geodetic": list(self.origin_geodetic),
            "plot_area_m2": round(self.plot_area_m2, 1),
            "core_area_m2": round(self.core_area_m2, 1),
            "buffer_width_m": round(self.buffer_width_m, 2),
            "overall_isolation_status": self.overall_isolation_status,
            "mean_plot_containment": round(self.mean_plot_containment, 4),
            "mean_external_leakage": round(self.mean_external_leakage, 4),
            "zero_external_leakage_verified": self.zero_external_leakage_verified,
            "total_observables_evaluated": self.total_observables_evaluated,
            "classification_breakdown": self.classification_breakdown,
            "audit_records": [r.to_dict() for r in self.audit_records],
            "recommended_action": self.recommended_action,
        }

