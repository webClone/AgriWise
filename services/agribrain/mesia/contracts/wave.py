"""MESIA Wave Discovery Contracts — R6 §4.

WaveCandidate — Calibrated detected event with no protocol name.
WaveSurveyPlan — Sweep/dwell/trigger priorities and constraints.

Principle P-02: Discovery records an observable wave event; protocol
identity is a later, evidence-gated result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class WaveCandidate:
    """Calibrated detected event — R6 Appendix A.

    No protocol name.  No agronomic meaning.  Just a calibrated
    time-frequency/pulse/chirp/occupancy event with native artefact
    references.
    """

    candidate_id: str

    # Time-frequency bounds
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    centre_frequency_hz: Optional[float] = None
    bandwidth_hz: Optional[float] = None

    # Morphology
    morphology: str = ""
    """'NARROWBAND_CW', 'OFDM', 'CSS_CHIRP', 'FHSS', 'DSSS',
    'UWB_IMPULSE', 'FMCW', 'BACKSCATTER', 'UNKNOWN'."""

    duty_cycle_pct: Optional[float] = None
    periodicity_s: Optional[float] = None
    slope_hz_per_s: Optional[float] = None

    # Detection metadata
    detection_method: str = ""
    """'ENERGY_CFAR', 'KURTOSIS', 'CYCLOSTATIONARY', 'AUTOCORRELATION',
    'MATCHED_FILTER', 'PULSE', 'CHIRP', 'HOPPING', 'MULTICARRIER'."""

    snr_db: Optional[float] = None
    confidence: Optional[float] = None
    masks: List[str] = field(default_factory=list)
    uncertainty_description: str = ""

    # Native artefact
    native_artefact_uri: str = ""
    native_artefact_hash: str = ""

    # Receiver context
    receiver_id: str = ""
    antenna_path_ref: str = ""
    calibration_state_ref: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            val = getattr(self, f)
            if isinstance(val, datetime):
                val = val.isoformat()
            elif isinstance(val, (list, tuple)):
                val = list(val)
            d[f] = val
        return d

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WaveSurveyPlan:
    """Sweep/dwell/trigger priorities and constraints — R6 Appendix A."""

    plan_id: str
    objective: str = ""
    """'SURVEY', 'KNOWN_SOURCE_MONITOR', 'INTERFERENCE_WATCH',
    'EVENT_TRIGGER', 'CONTROLLED_EXPERIMENT'."""

    # Sweep configuration
    coarse_sweep_bands: List[Tuple[float, float]] = field(default_factory=list)
    """(start_hz, stop_hz) for coarse sweeps."""

    focused_dwell_frequencies: List[float] = field(default_factory=list)
    native_device_listeners: List[str] = field(default_factory=list)
    trigger_conditions: List[str] = field(default_factory=list)

    # Resource constraints
    scan_cadence_s: Optional[float] = None
    storage_budget_mb: Optional[float] = None
    max_duration_s: Optional[float] = None
    priority: int = 0

    # Policy
    jurisdiction_ref: str = ""
    spectrum_policy_ref: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            val = getattr(self, f)
            if isinstance(val, (list, tuple)):
                val = [list(x) if isinstance(x, tuple) else x for x in val]
            d[f] = val
        return d

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
