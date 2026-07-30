"""
Shared perception engine foundation.

Exports all common types, contracts, and utilities used by all 4 engines.
"""

from services.agribrain.layer0.perception.common.contracts import (
    PerceptionEngineFamily,
    PerceptionEngineInput,
    PerceptionEngineOutput,
    PerceptionVariable,
    PerceptionArtifact,
    QAResult,
)
from services.agribrain.layer0.perception.common.base_types import (
    GeometryScope,
    FeasibilityGate,
    ReliabilityBundle,
    SatelliteProvider,
)
from services.agribrain.layer0.perception.common.cache import PerceptionCache
from services.agribrain.layer0.perception.common.provenance import build_provenance
from services.agribrain.layer0.perception.common.packet_adapter import to_observation_packets
