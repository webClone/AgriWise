"""MESIA Receiver Contracts — R6 §3.1–3.2.

ReceiverCapabilityManifest — Per-receiver hardware truth.
AntennaPathManifest — Antenna/cable/filter/calibration chain.

Coverage is a tuple, not a frequency range (§3.2).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class AntennaPathManifest:
    """Antenna, cable, switch, filter, LNA, polarisation, orientation,
    calibration and phase-centre chain — R6 Appendix A."""

    path_id: str
    antenna_model: str = ""
    cable_type: str = ""
    cable_length_m: Optional[float] = None
    switch_config: str = ""
    filter_config: str = ""
    lna_model: str = ""
    lna_gain_db: Optional[float] = None
    polarisation: str = ""
    orientation_ypr_deg: Optional[Tuple[float, float, float]] = None
    phase_centre_offset_m: Optional[Tuple[float, float, float]] = None
    insertion_loss_db: Optional[float] = None
    calibration_ref: str = ""
    calibration_date: Optional[datetime] = None

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
class ReceiverCapabilityManifest:
    """Per-receiver hardware capability truth — R6 Appendix A.

    Records what a front end can and cannot observe.  Two devices with
    the same tuning range are not equivalent if one has a different
    antenna, clock, bandwidth or decoder (§3.2).
    """

    receiver_id: str
    front_end_class: str = ""
    """FrontEndClass value."""

    hardware_model: str = ""
    firmware_version: str = ""
    driver_version: str = ""

    # Tuning and bandwidth
    tuning_range_hz: Optional[Tuple[float, float]] = None
    """(min_hz, max_hz) frequency tuning range."""

    instantaneous_bandwidth_hz: Optional[float] = None
    sample_rate_hz: Optional[float] = None
    sample_format: str = ""
    """e.g., 'complex_float32', 'int16_iq'."""

    # Gain and sensitivity
    gain_stages: List[str] = field(default_factory=list)
    sensitivity_dbm: Optional[float] = None
    dynamic_range_db: Optional[float] = None

    # Clock
    clock_source: str = ""
    clock_accuracy_ppm: Optional[float] = None

    # Antenna ports
    antenna_port_count: int = 1
    antenna_path_refs: List[str] = field(default_factory=list)

    # Duplex and triggers
    duplex_mode: str = ""
    """'RX_ONLY', 'FDD', 'TDD', 'HALF_DUPLEX'."""

    hardware_trigger_capable: bool = False

    # Health
    health_status: str = "UNKNOWN"
    last_self_test: Optional[datetime] = None

    # Supported waveform/protocol operations
    supported_decoders: List[str] = field(default_factory=list)
    """e.g., ['lte_cell_search', 'wifi_csi', 'lora_decode']."""

    # Scan constraints
    scan_duty_cycle_pct: Optional[float] = None
    max_dwell_time_s: Optional[float] = None

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
