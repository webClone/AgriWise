"""R5.0: State descriptors, roles, and decomposition metadata.

Design rules:
  1. The 13-state ordering from config.py is FROZEN. No reordering, removal,
     renaming, or insertion in R5.0.
  2. StateDescriptor carries semantic metadata ABOUT each state variable.
     It does not change the variable's runtime position or numerical behavior.
  3. A variable may legitimately have multiple roles.
  4. Parameter estimation mode is configurable, not permanently excluded.
  5. STATE_SCHEMA_VERSION must be included in every execution identity,
     cache key, and serialized artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple


# ── Schema Versioning ────────────────────────────────────────────────────────

STATE_SCHEMA_VERSION = "asmae_state_v1_13"
"""Frozen state schema version. Must enter every run identity and cache key."""


# ── Enums ────────────────────────────────────────────────────────────────────

class StateRole(Enum):
    """Semantic role a state variable may fulfil.

    A variable may have MULTIPLE roles. For example, ``structure`` is both
    ``LATENT_PHYSICAL`` (it represents a real physical property) and
    ``OBSERVATION_CONSTRAINED`` (it is directly informed by SAR VH).
    """
    DYNAMIC_PHYSICAL = "dynamic_physical"
    SLOWLY_VARYING_PARAMETER = "slowly_varying_parameter"
    MEMORY_ACCUMULATOR = "memory_accumulator"
    DIAGNOSTIC_HYPOTHESIS = "diagnostic_hypothesis"
    OBSERVATION_DERIVED = "observation_derived"
    OBSERVATION_CONSTRAINED = "observation_constrained"
    LATENT_PHYSICAL = "latent_physical"
    SPATIALLY_RECONSTRUCTED = "spatially_reconstructed"
    EVENT_INDICATOR = "event_indicator"
    EVIDENCE_METADATA = "evidence_metadata"


class TransitionPolicy(Enum):
    """How this variable evolves between observations."""
    PROCESS_MODEL = "process_model"
    DECAY_ACCUMULATOR = "decay_accumulator"
    EVENT_DRIVEN = "event_driven"
    SLOWLY_VARYING = "slowly_varying"
    DIFFUSION_ONLY = "diffusion_only"
    EXTERNAL_FORCING = "external_forcing"
    NONE = "none"


class AssimilationPolicy(Enum):
    """How this variable is updated by observations."""
    DIRECT_OBSERVATION = "direct_observation"
    INDIRECT_CONSTRAINT = "indirect_constraint"
    PROXY_DERIVED = "proxy_derived"
    HYPOTHESIS_INFERENCE = "hypothesis_inference"
    NOT_ASSIMILATED = "not_assimilated"


class IdentifiabilityClass(Enum):
    """Whether the variable is uniquely determined by available evidence."""
    DIRECTLY_OBSERVED = "directly_observed"
    INDIRECTLY_CONSTRAINED = "indirectly_constrained"
    PARTIALLY_IDENTIFIED = "partially_identified"
    HYPOTHESIS_ONLY = "hypothesis_only"
    NOT_IDENTIFIED = "not_identified"


class AuthorityCeiling(Enum):
    """Maximum authority this variable can achieve with current evidence."""
    VISUALIZATION = "visualization"
    MONITORING_ONLY = "monitoring_only"
    DIAGNOSTIC = "diagnostic"
    STATE_UPDATE = "state_update"
    TRAINING_EXPORT = "training_export"
    PRESCRIPTION_ELIGIBLE = "prescription_eligible"
    PRESCRIPTION_DRIVER = "prescription_driver"


class ParameterEstimationMode(Enum):
    """How slowly varying parameters are estimated.

    R5.0 default: FIXED_PRIOR or OFFLINE_CALIBRATED.
    Future versions may authorize ONLINE_AUGMENTED_STATE when
    identifiability and calibration support it.
    """
    FIXED_PRIOR = "fixed_prior"
    OFFLINE_CALIBRATED = "offline_calibrated"
    ONLINE_AUGMENTED_STATE = "online_augmented_state"
    HIERARCHICAL_POSTERIOR = "hierarchical_posterior"


# ── StateDescriptor ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StateDescriptor:
    """Immutable semantic description of one state variable.

    This is metadata ABOUT the variable. It does not change the variable's
    position in the state vector, its runtime bounds, or the EnKF update.
    """
    index: int
    canonical_name: str
    semantic_name: str
    units: str
    roles: Tuple[StateRole, ...]
    bounds: Tuple[float, float]
    transition_policy: TransitionPolicy
    assimilation_policy: AssimilationPolicy
    identifiability_class: IdentifiabilityClass
    authority_ceiling: AuthorityCeiling
    parameter_estimation_mode: ParameterEstimationMode = (
        ParameterEstimationMode.FIXED_PRIOR
    )
    notes: str = ""


# ── Frozen v941 State Order ──────────────────────────────────────────────────

STATE_ORDER: Tuple[str, ...] = (
    "vigor",
    "lai",
    "chlorophyll",
    "canopy_water",
    "root_zone_water",
    "surface_wetness_event",
    "structure",
    "bare_soil_fraction",
    "salinity_stress",
    "thermal_stress",
    "biotic_confounder_risk",
    "phenology_progress",
    "stress_memory",
)
"""Frozen state ordering. Must match config.STATE_NAMES exactly."""

assert len(STATE_ORDER) == 13, "STATE_ORDER must have exactly 13 entries"


# ── Descriptors for all 13 states ────────────────────────────────────────────

STATE_DESCRIPTORS: Tuple[StateDescriptor, ...] = (
    StateDescriptor(
        index=0,
        canonical_name="vigor",
        semantic_name="Canopy photosynthetic activity",
        units="unitless [0,1]",
        roles=(StateRole.DYNAMIC_PHYSICAL, StateRole.OBSERVATION_CONSTRAINED),
        bounds=(0.0, 1.0),
        transition_policy=TransitionPolicy.PROCESS_MODEL,
        assimilation_policy=AssimilationPolicy.INDIRECT_CONSTRAINT,
        identifiability_class=IdentifiabilityClass.INDIRECTLY_CONSTRAINED,
        authority_ceiling=AuthorityCeiling.PRESCRIPTION_ELIGIBLE,
        notes="Constrained by NDVI/EVI; confounded by canopy density and soil background.",
    ),
    StateDescriptor(
        index=1,
        canonical_name="lai",
        semantic_name="Leaf area index",
        units="m²/m²",
        roles=(StateRole.DYNAMIC_PHYSICAL, StateRole.OBSERVATION_CONSTRAINED),
        bounds=(0.0, 8.0),
        transition_policy=TransitionPolicy.PROCESS_MODEL,
        assimilation_policy=AssimilationPolicy.INDIRECT_CONSTRAINT,
        identifiability_class=IdentifiabilityClass.PARTIALLY_IDENTIFIED,
        authority_ceiling=AuthorityCeiling.DIAGNOSTIC,
        notes="NDVI/EVI constrain but saturate; not independently identified without crop-specific model.",
    ),
    StateDescriptor(
        index=2,
        canonical_name="chlorophyll",
        semantic_name="Foliar chlorophyll content",
        units="µg/cm²",
        roles=(StateRole.DYNAMIC_PHYSICAL, StateRole.OBSERVATION_CONSTRAINED),
        bounds=(0.0, 80.0),
        transition_policy=TransitionPolicy.PROCESS_MODEL,
        assimilation_policy=AssimilationPolicy.INDIRECT_CONSTRAINT,
        identifiability_class=IdentifiabilityClass.PARTIALLY_IDENTIFIED,
        authority_ceiling=AuthorityCeiling.DIAGNOSTIC,
        notes="Red-edge sensitive; confounded by water stress, phenology, canopy density.",
    ),
    StateDescriptor(
        index=3,
        canonical_name="canopy_water",
        semantic_name="Canopy water content",
        units="unitless [0,1]",
        roles=(StateRole.DYNAMIC_PHYSICAL, StateRole.OBSERVATION_CONSTRAINED),
        bounds=(0.0, 1.0),
        transition_policy=TransitionPolicy.PROCESS_MODEL,
        assimilation_policy=AssimilationPolicy.INDIRECT_CONSTRAINT,
        identifiability_class=IdentifiabilityClass.INDIRECTLY_CONSTRAINED,
        authority_ceiling=AuthorityCeiling.DIAGNOSTIC,
        notes="NDMI-driven; coupled with root-zone water through transpiration.",
    ),
    StateDescriptor(
        index=4,
        canonical_name="root_zone_water",
        semantic_name="Root-zone soil moisture",
        units="volumetric fraction [0,1]",
        roles=(StateRole.DYNAMIC_PHYSICAL,),
        bounds=(0.0, 1.0),
        transition_policy=TransitionPolicy.PROCESS_MODEL,
        assimilation_policy=AssimilationPolicy.INDIRECT_CONSTRAINT,
        identifiability_class=IdentifiabilityClass.INDIRECTLY_CONSTRAINED,
        authority_ceiling=AuthorityCeiling.DIAGNOSTIC,
        notes=(
            "S1 VV sensitive to surface only. Root-zone requires transition model, "
            "soil hydraulics, rainfall, irrigation, ET, root depth, and preferably probes."
        ),
    ),
    StateDescriptor(
        index=5,
        canonical_name="surface_wetness_event",
        semantic_name="Event-based surface water",
        units="unitless [0,1]",
        roles=(
            StateRole.EVENT_INDICATOR,
            StateRole.OBSERVATION_CONSTRAINED,
            StateRole.LATENT_PHYSICAL,
        ),
        bounds=(0.0, 1.0),
        transition_policy=TransitionPolicy.EVENT_DRIVEN,
        assimilation_policy=AssimilationPolicy.INDIRECT_CONSTRAINT,
        identifiability_class=IdentifiabilityClass.INDIRECTLY_CONSTRAINED,
        authority_ceiling=AuthorityCeiling.DIAGNOSTIC,
        notes="SAR/NDWI driven; transient event indicator, not a monotonic accumulator.",
    ),
    StateDescriptor(
        index=6,
        canonical_name="structure",
        semantic_name="Canopy/biomass structure",
        units="unitless [0,1]",
        roles=(
            StateRole.LATENT_PHYSICAL,
            StateRole.OBSERVATION_CONSTRAINED,
            StateRole.SPATIALLY_RECONSTRUCTED,
        ),
        bounds=(0.0, 1.0),
        transition_policy=TransitionPolicy.SLOWLY_VARYING,
        assimilation_policy=AssimilationPolicy.INDIRECT_CONSTRAINT,
        identifiability_class=IdentifiabilityClass.INDIRECTLY_CONSTRAINED,
        authority_ceiling=AuthorityCeiling.DIAGNOSTIC,
        notes="SAR VH driven; represents volumetric canopy structure.",
    ),
    StateDescriptor(
        index=7,
        canonical_name="bare_soil_fraction",
        semantic_name="Exposed soil fraction",
        units="unitless [0,1]",
        roles=(
            StateRole.OBSERVATION_DERIVED,
            StateRole.LATENT_PHYSICAL,
        ),
        bounds=(0.0, 1.0),
        transition_policy=TransitionPolicy.SLOWLY_VARYING,
        assimilation_policy=AssimilationPolicy.PROXY_DERIVED,
        identifiability_class=IdentifiabilityClass.INDIRECTLY_CONSTRAINED,
        authority_ceiling=AuthorityCeiling.PRESCRIPTION_ELIGIBLE,
        notes="BSI-driven; slowly varying environmental state.",
    ),
    StateDescriptor(
        index=8,
        canonical_name="salinity_stress",
        semantic_name="Salinity-induced stress",
        units="unitless [0,1]",
        roles=(StateRole.DIAGNOSTIC_HYPOTHESIS,),
        bounds=(0.0, 1.0),
        transition_policy=TransitionPolicy.EXTERNAL_FORCING,
        assimilation_policy=AssimilationPolicy.HYPOTHESIS_INFERENCE,
        identifiability_class=IdentifiabilityClass.HYPOTHESIS_ONLY,
        authority_ceiling=AuthorityCeiling.MONITORING_ONLY,
        notes="Requires soil EC evidence or local validation; spectral signature alone is insufficient.",
    ),
    StateDescriptor(
        index=9,
        canonical_name="thermal_stress",
        semantic_name="Thermal stress",
        units="unitless [0,1]",
        roles=(StateRole.DIAGNOSTIC_HYPOTHESIS, StateRole.OBSERVATION_CONSTRAINED),
        bounds=(0.0, 1.0),
        transition_policy=TransitionPolicy.EXTERNAL_FORCING,
        assimilation_policy=AssimilationPolicy.HYPOTHESIS_INFERENCE,
        identifiability_class=IdentifiabilityClass.INDIRECTLY_CONSTRAINED,
        authority_ceiling=AuthorityCeiling.DIAGNOSTIC,
        notes="Weather-driven; validated by temperature records.",
    ),
    StateDescriptor(
        index=10,
        canonical_name="biotic_confounder_risk",
        semantic_name="Biotic pressure confounding risk",
        units="unitless [0,1]",
        roles=(StateRole.DIAGNOSTIC_HYPOTHESIS,),
        bounds=(0.0, 1.0),
        transition_policy=TransitionPolicy.EXTERNAL_FORCING,
        assimilation_policy=AssimilationPolicy.HYPOTHESIS_INFERENCE,
        identifiability_class=IdentifiabilityClass.HYPOTHESIS_ONLY,
        authority_ceiling=AuthorityCeiling.MONITORING_ONLY,
        notes="Cannot acquire direct-observation status without external confirmation.",
    ),
    StateDescriptor(
        index=11,
        canonical_name="phenology_progress",
        semantic_name="Phenological stage progress",
        units="unitless [0,1]",
        roles=(StateRole.DYNAMIC_PHYSICAL,),
        bounds=(0.0, 1.0),
        transition_policy=TransitionPolicy.PROCESS_MODEL,
        assimilation_policy=AssimilationPolicy.INDIRECT_CONSTRAINT,
        identifiability_class=IdentifiabilityClass.PARTIALLY_IDENTIFIED,
        authority_ceiling=AuthorityCeiling.DIAGNOSTIC,
        notes="Thermal-time driven; monotonic within season.",
    ),
    StateDescriptor(
        index=12,
        canonical_name="stress_memory",
        semantic_name="EWMA stress accumulator",
        units="unitless [0,1]",
        roles=(StateRole.MEMORY_ACCUMULATOR,),
        bounds=(0.0, 1.0),
        transition_policy=TransitionPolicy.DECAY_ACCUMULATOR,
        assimilation_policy=AssimilationPolicy.NOT_ASSIMILATED,
        identifiability_class=IdentifiabilityClass.NOT_IDENTIFIED,
        authority_ceiling=AuthorityCeiling.VISUALIZATION,
        notes="Computed from heat/water signals; not directly observed.",
    ),
)

assert len(STATE_DESCRIPTORS) == 13, "Must describe all 13 states"

# Cross-check ordering against STATE_ORDER
for _desc in STATE_DESCRIPTORS:
    assert _desc.canonical_name == STATE_ORDER[_desc.index], (
        f"StateDescriptor index {_desc.index} name {_desc.canonical_name!r} "
        f"does not match STATE_ORDER[{_desc.index}] = {STATE_ORDER[_desc.index]!r}"
    )

# ── Lookup helpers ───────────────────────────────────────────────────────────

STATE_DESCRIPTOR_BY_NAME = {d.canonical_name: d for d in STATE_DESCRIPTORS}
STATE_DESCRIPTOR_BY_INDEX = {d.index: d for d in STATE_DESCRIPTORS}


def descriptor_for(name_or_index: str | int) -> StateDescriptor:
    """Look up a state descriptor by canonical name or index."""
    if isinstance(name_or_index, int):
        return STATE_DESCRIPTOR_BY_INDEX[name_or_index]
    return STATE_DESCRIPTOR_BY_NAME[name_or_index]


def get_descriptor(name_or_index: str | int) -> StateDescriptor | None:
    """Safely look up a state descriptor by canonical name or index, returning None if not found."""
    if isinstance(name_or_index, int):
        return STATE_DESCRIPTOR_BY_INDEX.get(name_or_index)
    return STATE_DESCRIPTOR_BY_NAME.get(str(name_or_index))
