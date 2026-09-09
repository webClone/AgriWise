"""MESIA Behaviour Contracts — R6 §9.

RadioBehaviourContract — Source-specific measurement primitive definition.
BehaviourLikelihood — Calibrated likelihood output for ASMAE.

Behaviour is source-specific (§9.1): Wi-Fi CSI, LoRa thresholds, GNSS
reflectometry, RFID resonance, UWB/GPR range profiles, mmWave beams
and public telephony metrics do NOT share the same measurement primitive.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RadioBehaviourContract:
    """Source-specific measurement primitive — R6 Appendix A.

    Each contract states the observable, actions, calibration, nuisance
    variables, valid domain, uncertainty and allowed output.
    """

    contract_id: str
    radio_family: str
    """RadioFamily value."""

    profile_version: str = ""

    # What this source measures
    physical_primitive: str = ""
    """e.g., 'complex_subcarrier_channel', 'chirp_rssi_threshold',
    'gnss_snr_multipath', 'rfid_resonance_response',
    'range_profile', 'aggregated_rsrp'."""

    # Controlled actions available
    controlled_actions: List[str] = field(default_factory=list)
    """e.g., ['power_sweep', 'channel_sweep', 'antenna_rotation']."""

    # Features this source can produce
    stable_features: List[str] = field(default_factory=list)
    """e.g., ['amplitude_response', 'relative_phase', 'delay_spread']."""

    # Invalid/forbidden states
    invalid_states: List[str] = field(default_factory=list)
    """Conditions under which this source cannot produce valid evidence."""

    # Nuisance variables
    nuisance_variables: List[str] = field(default_factory=list)
    """e.g., ['agc_jumps', 'multipath', 'people_motion', 'rain']."""

    # Valid domain
    valid_domain: Dict[str, Any] = field(default_factory=dict)
    """e.g., {'soil_types': [...], 'moisture_range': [0.05, 0.45]}."""

    # Calibration requirements
    calibration_requirements: List[str] = field(default_factory=list)

    # Uncertainty model
    uncertainty_model: str = ""
    """Reference to uncertainty model specification."""

    # Allowed outputs
    allowed_outputs: List[str] = field(default_factory=list)
    """What this contract permits as downstream output."""

    # Prohibited inferences
    prohibited_inferences: List[str] = field(default_factory=list)
    """Explicitly forbidden downstream interpretations."""

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
class BehaviourLikelihood:
    """Calibrated likelihood/innovation for ASMAE — R6 Appendix A.

    This is what MESIA proposes to ASMAE.  ASMAE decides whether to
    incorporate it (principle P-08).
    """

    likelihood_id: str
    radio_family: str
    contract_ref: str
    """Reference to the RadioBehaviourContract."""

    # The likelihood itself
    target_variable: str = ""
    """What physical quantity this likelihood addresses.
    e.g., 'root_zone_water', 'canopy_water', 'salinity'."""

    likelihood_value: Optional[float] = None
    innovation: Optional[float] = None
    """Observation minus prior prediction."""

    support: Optional[float] = None
    """Spatial/temporal support of this observation."""

    covariance: Optional[float] = None
    """Observation error covariance."""

    # Authority and alternatives
    authority_scope: str = "evidence_proposal"
    """Always 'evidence_proposal' — ASMAE owns the posterior."""

    alternative_causes: List[Dict[str, Any]] = field(default_factory=list)
    """Nuisance/non-agricultural alternative explanations with
    probabilities."""

    # Epoch and calibration context
    epoch_refs: Dict[str, str] = field(default_factory=dict)
    """All active epoch IDs at the time of this likelihood."""

    observability_ref: str = ""
    closure_ref: str = ""
    qualification_ref: str = ""

    # Metadata
    created_at: Optional[datetime] = None
    native_observation_ref: str = ""
    """Reference to the RadioObservationPacket."""

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
