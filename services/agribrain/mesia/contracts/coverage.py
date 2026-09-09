"""MESIA Coverage Contracts — R6 §3.2–3.3.

Coverage is a tuple, not a frequency range.  The CoverageGraph maps
receiver paths to observable frequency/time/space/polarisation domains
with explicit gaps.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CoverageTuple:
    """Per-receiver-path coverage descriptor — R6 §3.2.

    Records what a specific receiver+antenna path can observe.
    """

    path_id: str
    receiver_id: str

    frequency_range_hz: Optional[Tuple[float, float]] = None
    instantaneous_bandwidth_hz: Optional[float] = None
    scan_dwell_duty_cycle_pct: Optional[float] = None
    sensitivity_dbm: Optional[float] = None
    dynamic_range_db: Optional[float] = None

    antenna_polarisation: str = ""
    antenna_beam_description: str = ""
    spatial_position_wgs84: Optional[Tuple[float, float, float]] = None
    field_of_view_description: str = ""

    clock_trigger_capability: str = ""
    supported_sample_formats: List[str] = field(default_factory=list)
    supported_native_formats: List[str] = field(default_factory=list)

    tx_rx_constraints: str = ""
    """'RX_ONLY', 'TX_RX', 'CONTROLLED_TX'."""

    legal_permissions: str = ""
    health_status: str = "UNKNOWN"
    calibration_state_ref: str = ""

    waveform_operations: List[str] = field(default_factory=list)
    """Protocol operations available on this path."""

    coverage_outcome: str = "OBSERVABLE"
    """CoverageOutcome value for this path."""

    gap_reason: str = ""
    """If not OBSERVABLE, reason for the gap."""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            val = getattr(self, f)
            if isinstance(val, (list, tuple)):
                val = list(val)
            d[f] = val
        return d

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CoverageGraph:
    """Observable frequency/time/space/polarisation map — R6 Appendix A.

    The graph aggregates CoverageTuples and reports gaps.
    """

    graph_id: str
    created_at: Optional[datetime] = None
    coverage_tuples: List[CoverageTuple] = field(default_factory=list)

    # Aggregated gap analysis
    blind_bands: List[Tuple[float, float]] = field(default_factory=list)
    """Frequency ranges (Hz) with no coverage."""

    gap_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "coverage_tuples": [ct.to_dict() for ct in self.coverage_tuples],
            "blind_bands": [list(b) for b in self.blind_bands],
            "gap_summary": self.gap_summary,
        }

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
