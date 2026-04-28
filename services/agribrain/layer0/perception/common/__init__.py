"""
Shared perception engine foundation.

Exports all common types, contracts, and utilities used by all 4 engines.
"""

from layer0.perception.common.contracts import (
    PerceptionEngineFamily,
    PerceptionEngineInput,
    PerceptionEngineOutput,
    PerceptionVariable,
    PerceptionArtifact,
    QAResult,
)
from layer0.perception.common.base_types import (
    GeometryScope,
    FeasibilityGate,
    ReliabilityBundle,
    SatelliteProvider,
)
from layer0.perception.common.cache import PerceptionCache
from layer0.perception.common.provenance import build_provenance
from layer0.perception.common.packet_adapter import to_observation_packets
