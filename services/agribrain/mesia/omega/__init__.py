"""MESIA Omega Scientific Automation & Institutional Reference Network Package."""

from .hierarchical_aggregation import (
    AggregationScale,
    AggregatedEvidenceSummary,
    HierarchicalAggregator,
)
from .surprise_detector import (
    ScientificSurpriseHypothesis,
    OmegaSurpriseDetector,
)
from .experiment_proposer import (
    ProposedScientificExperiment,
    OmegaExperimentProposer,
)

__all__ = [
    "AggregationScale",
    "AggregatedEvidenceSummary",
    "HierarchicalAggregator",
    "ScientificSurpriseHypothesis",
    "OmegaSurpriseDetector",
    "ProposedScientificExperiment",
    "OmegaExperimentProposer",
]
