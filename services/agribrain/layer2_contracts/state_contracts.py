"""
Layer 2 Canonical State Contracts.

Immutable definitions for Layer 2 vegetation state estimation:
- StressMagnitudeState: Physical stress state S_k with UncertaintyBudget.
- StressHypothesisState: Full continuous diagnostic simplex P(H | E).
- StressImpactEstimate: Crop- and stage-conditioned biological consequence I_k.
- VegetationState: Unified latent state vector X_t^L2.
- UncertaintyBudget: Quad-component variance breakdown (sensor, retrieval, conflict, model).
- CropKnowledgeAuthority: Explicit epistemic gating for crop context.
- InferenceProvenance: Audit trail and provenance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple


# =============================================================================
# Epistemic & Authority Enums
# =============================================================================

class CropKnowledgeAuthority(str, Enum):
    """Authority level of crop identification and physiological knowledge."""
    UNKNOWN = "UNKNOWN"                    # Unclassified / generic vegetation
    PRIOR_ONLY = "PRIOR_ONLY"              # Broad global priors only
    TRANSFERRED = "TRANSFERRED"            # Species-level literature defaults
    CALIBRATED = "CALIBRATED"              # Cultivar / regional calibration
    FIELD_VALIDATED = "FIELD_VALIDATED"    # Local in-situ agronomist validated


class InferenceMode(str, Enum):
    """Execution mode of the state estimator."""
    ONLINE = "ONLINE"                      # Causal filtering [1:t], zero future leakage
    RETROSPECTIVE = "RETROSPECTIVE"        # Full-cycle smoothing [1:T]


class PhysicalSourceType(str, Enum):
    """Source authority for physical state variables."""
    OBSERVED = "OBSERVED"                  # Direct instrument observation
    DERIVED = "DERIVED"                    # Biophysical retrieval / inversion


# =============================================================================
# Uncertainty Budget Contract
# =============================================================================

@dataclass(frozen=True)
class UncertaintyBudget:
    """Rigorous 4-component uncertainty budget for state variables.
    
    sigma_total = sqrt(sigma_sensor^2 + sigma_retrieval^2 + sigma_conflict^2 + sigma_model^2)
    """
    sensor_sigma: float = 0.02             # Instrument radiometric / thermal noise
    retrieval_sigma: float = 0.03          # Jacobian-propagated retrieval variance
    conflict_sigma: float = 0.00           # Cross-sensor / multi-modal conflict penalty
    model_sigma: float = 0.03              # Empirical transfer function structural variance

    @property
    def total_sigma(self) -> float:
        """Composite total standard deviation via quadratic quadrature."""
        var = (
            self.sensor_sigma ** 2 +
            self.retrieval_sigma ** 2 +
            self.conflict_sigma ** 2 +
            self.model_sigma ** 2
        )
        return round(math.sqrt(max(1e-8, var)), 4)

    def to_dict(self) -> Dict[str, float]:
        return {
            "sensor_sigma": self.sensor_sigma,
            "retrieval_sigma": self.retrieval_sigma,
            "conflict_sigma": self.conflict_sigma,
            "model_sigma": self.model_sigma,
            "total_sigma": self.total_sigma,
        }


# =============================================================================
# 1. Physical Stress Magnitude State (Crop-Independent)
# =============================================================================

@dataclass
class StressMagnitudeState:
    """Physical state deficit S_k in [0.0, 1.0].
    
    Exists and is calculated independently of crop identity or phenology.
    Consumed by downstream physical/hydraulic models (e.g. Layer 3 irrigation).
    """
    stress_type: str                       # WATER | THERMAL | NUTRIENT | SALINITY | BIOTIC | PHOTOSYNTHETIC_SHUTDOWN | MECHANICAL | UNKNOWN
    value: float = 0.0                     # S_k normalized [0.0, 1.0]
    uncertainty: UncertaintyBudget = field(default_factory=UncertaintyBudget)
    source: PhysicalSourceType = PhysicalSourceType.DERIVED
    primary_sensor_evidence: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)


# =============================================================================
# 2. Diagnostic Hypothesis Simplex P(H | E)
# =============================================================================

CANONICAL_HYPOTHESES = (
    "WATER",
    "THERMAL",
    "NUTRIENT",
    "SALINITY",
    "BIOTIC",
    "UNRESOLVED",
)

@dataclass
class StressHypothesisState:
    """Full continuous probability simplex over competing diagnostic hypotheses.
    
    Guarantees sum_{H} P(H | E) = 1.0.
    H_UNRESOLVED is continuously active from timestep zero to absorb unexplained residuals.
    """
    posteriors: Dict[str, float] = field(default_factory=lambda: {
        "WATER": 0.15,
        "THERMAL": 0.15,
        "NUTRIENT": 0.15,
        "SALINITY": 0.10,
        "BIOTIC": 0.15,
        "UNRESOLVED": 0.30,
    })
    dominant_hypothesis: str = "UNRESOLVED"
    dominant_probability: float = 0.30
    epistemic_entropy: float = 1.70        # Shannon entropy H(P) in nats
    evidence_lineage: Dict[str, List[str]] = field(default_factory=dict)

    def __post_init__(self):
        # Normalize posteriors to strict simplex if non-empty
        if self.posteriors:
            total = sum(self.posteriors.values())
            if total > 0:
                self.posteriors = {k: round(v / total, 4) for k, v in self.posteriors.items()}
            self.dominant_hypothesis = max(self.posteriors.items(), key=lambda x: x[1])[0]
            self.dominant_probability = self.posteriors[self.dominant_hypothesis]
            # Compute Shannon entropy
            self.epistemic_entropy = round(-sum(p * math.log(max(1e-10, p)) for p in self.posteriors.values()), 3)


# =============================================================================
# 3. Biological Consequence & Impact State (Crop-Conditioned)
# =============================================================================

@dataclass
class StressImpactEstimate:
    """Crop- and stage-conditioned biological consequence I_k.
    
    Requires crop context and developmental stage.
    """
    stress_type: str
    raw_impact: float = 0.0                # I_raw = S_k * s_k(c, z) * beta(c, z, env) (unclipped)
    normalized_impact: float = 0.0         # min(1.0, raw_impact) bounded [0.0, 1.0] index
    damage_probability: float = 0.0        # P_damage in [0.0, 1.0] via sigmoid mapping
    impact_uncertainty: float = 0.0        # Propagated biological uncertainty
    compound_synergy_factor: float = 1.0  # beta factor in [1.0, 1.95]
    compound_partner: str = ""
    stage_sensitivity_multiplier: float = 1.0
    crop_authority: CropKnowledgeAuthority = CropKnowledgeAuthority.TRANSFERRED
    impact_authority: Literal["CALIBRATED", "TRANSFERRED", "PRIOR_ONLY", "UNAVAILABLE"] = "TRANSFERRED"
    explanation_basis: List[str] = field(default_factory=list)

    @property
    def biological_impact(self) -> float:
        """Backwards compatibility alias for normalized_impact."""
        return self.normalized_impact


# =============================================================================
# 4. Inference Provenance Contract
# =============================================================================

@dataclass
class InferenceProvenance:
    """Complete lineage and execution metadata for research-grade reproducibility."""
    model_version: str = "4.2.0"
    crop_profile_version: str = "4.0.0"
    data_sources: List[str] = field(default_factory=list)
    observation_count: int = 0
    missing_modalities: List[str] = field(default_factory=list)
    authority_level: CropKnowledgeAuthority = CropKnowledgeAuthority.TRANSFERRED
    inference_mode: InferenceMode = InferenceMode.ONLINE
    execution_timestamp: Optional[datetime] = None


# =============================================================================
# 5. Unified Latent Vegetation State Vector (X_t^L2)
# =============================================================================

@dataclass
class VegetationState:
    """Unified latent vegetation state vector X_t^L2.
    
    Consolidated state consumed directly by Layer 3 process models.
    """
    plot_id: str
    timestamp: datetime
    
    # Biological development coordinate
    development_time: float = 0.0          # D_t = tau_t * D_cycle
    phenology_stage: str = "VEGETATIVE"
    stage_progress_fraction: float = 0.0   # [0.0, 1.0] relative to cycle
    crop_authority: CropKnowledgeAuthority = CropKnowledgeAuthority.TRANSFERRED
    
    # Physical canopy & root boundary state
    lai: float = 0.0                       # Leaf Area Index (m2/m2)
    fvc: float = 0.0                       # Fractional Vegetation Cover [0, 1]
    fpar: float = 0.0                      # Fraction of Absorbed PAR [0, 1]
    biomass_proxy: float = 0.0             # Accumulated dry matter proxy (g/m2)
    canopy_water_index: Optional[float] = None
    root_depth_proxy_m: Optional[float] = None       # Vegetation-side estimated active rooting depth (m)
    root_zone_accessibility: str = "MODERATE"       # SHALLOW | MODERATE | DEEP | PERENNIAL_DEEP
    
    # Multi-tier stress states
    physical_stress_states: Dict[str, StressMagnitudeState] = field(default_factory=dict)
    diagnostic_hypothesis_state: StressHypothesisState = field(default_factory=StressHypothesisState)
    biological_impact_states: Dict[str, StressImpactEstimate] = field(default_factory=dict)
    
    # Quality & Provenance
    data_health_score: float = 1.0
    provenance: InferenceProvenance = field(default_factory=InferenceProvenance)


# =============================================================================
# 6. Canonical State Factory
# =============================================================================

class StressStateFactory:
    """Canonical factory for constructing fully verified Layer 2 State Objects."""

    @staticmethod
    def create_magnitude_state(
        stress_type: str,
        value: float,
        uncertainty: UncertaintyBudget,
        source: PhysicalSourceType = PhysicalSourceType.DERIVED,
        primary_sensor_evidence: Optional[List[str]] = None,
    ) -> StressMagnitudeState:
        return StressMagnitudeState(
            stress_type=stress_type.upper(),
            value=round(min(1.0, max(0.0, value)), 3),
            uncertainty=uncertainty,
            source=source,
            primary_sensor_evidence=primary_sensor_evidence or [],
        )

    @staticmethod
    def create_hypothesis_state(
        posteriors: Optional[Dict[str, float]] = None,
    ) -> StressHypothesisState:
        return StressHypothesisState(posteriors=posteriors or {})

    @staticmethod
    def create_impact_estimate(
        stress_type: str,
        raw_impact: float,
        damage_probability: float,
        impact_uncertainty: float,
        compound_synergy_factor: float = 1.0,
        compound_partner: str = "",
        stage_sensitivity_multiplier: float = 1.0,
        crop_authority: CropKnowledgeAuthority = CropKnowledgeAuthority.TRANSFERRED,
        impact_authority: Literal["CALIBRATED", "TRANSFERRED", "PRIOR_ONLY", "UNAVAILABLE"] = "TRANSFERRED",
        explanation_basis: Optional[List[str]] = None,
    ) -> StressImpactEstimate:
        return StressImpactEstimate(
            stress_type=stress_type.upper(),
            raw_impact=round(raw_impact, 3),
            normalized_impact=round(min(1.0, max(0.0, raw_impact)), 3),
            damage_probability=round(min(1.0, max(0.0, damage_probability)), 3),
            impact_uncertainty=round(impact_uncertainty, 4),
            compound_synergy_factor=round(compound_synergy_factor, 3),
            compound_partner=compound_partner,
            stage_sensitivity_multiplier=round(stage_sensitivity_multiplier, 3),
            crop_authority=crop_authority,
            impact_authority=impact_authority,
            explanation_basis=explanation_basis or [],
        )
