"""
Shared perception engine foundation.

Exports all common types, contracts, and utilities used by all 4 engines.
"""

from .contracts import (
    PerceptionEngineFamily,
    PerceptionEngineInput,
    PerceptionEngineOutput,
    PerceptionVariable,
    PerceptionArtifact,
    QAResult,
)
from .base_types import (
    GeometryScope,
    FeasibilityGate,
    ReliabilityBundle,
    SatelliteProvider,
)
from .cache import PerceptionCache
from .provenance import build_provenance
from .packet_adapter import to_observation_packets
