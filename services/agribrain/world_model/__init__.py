"""Transition foundations for a future AgriBrain Agricultural World Model.

This package owns the canonical plot worldline, belief snapshot archive,
forecast archive, event identity, bitemporal historical extractor, and
mathematical agronomical state contracts.
"""

from .canonical_worldline import (
    CanonicalWorldlineService,
    WorldlineEventProposal,
    CorruptedWorldlineError,
    SecurityViolation,
)
from .event_identity import (
    compute_payload_hash,
    compute_v2_identity,
    EventIdentityInput,
    EventIdentityRecord,
    ParentRef,
    ExternalParentRef,
)
from .belief_snapshot import (
    BeliefStateSnapshot,
    BELIEF_SNAPSHOT_SCHEMA_VERSION,
)
from .forecast_archive import (
    ForecastArtifact,
    ForecastEvaluation,
    ForecastRecord,
    ForecastEvaluationRecord,
    ImmutableForecastArchive,
    compute_forecast_id,
    compute_crps_quantiles,
    compute_crps_gaussian,
    compute_interval_coverage,
    DomainStatus,
    EvaluationSpace,
)
from .historical_extractor import (
    BitemporalWorldlineExtractor,
    TrainingTrajectoryWindow,
)
from .contracts import (
    AgronomicalStateVector,
    EnvironmentalDisturbance,
    ActionVector,
    verify_water_balance_conservation,
    SOIL_STRATA_DEPTHS_CM,
)

__all__ = [
    "CanonicalWorldlineService",
    "WorldlineEventProposal",
    "CorruptedWorldlineError",
    "SecurityViolation",
    "compute_payload_hash",
    "compute_v2_identity",
    "EventIdentityInput",
    "EventIdentityRecord",
    "ParentRef",
    "ExternalParentRef",
    "BeliefStateSnapshot",
    "BELIEF_SNAPSHOT_SCHEMA_VERSION",
    "ForecastArtifact",
    "ForecastEvaluation",
    "ForecastRecord",
    "ForecastEvaluationRecord",
    "ImmutableForecastArchive",
    "compute_forecast_id",
    "compute_crps_quantiles",
    "compute_crps_gaussian",
    "compute_interval_coverage",
    "DomainStatus",
    "EvaluationSpace",
    "BitemporalWorldlineExtractor",
    "TrainingTrajectoryWindow",
    "AgronomicalStateVector",
    "EnvironmentalDisturbance",
    "ActionVector",
    "verify_water_balance_conservation",
    "SOIL_STRATA_DEPTHS_CM",
]
