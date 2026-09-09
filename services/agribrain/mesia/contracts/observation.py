"""MESIA RadioObservationPacket — R6 Appendix E.

The core exchange format for a single radio observation.  Carries all
nine field groups: Identity, Time, Space, Waveform, Native data, Action,
Epochs, Quality, and Evidence.

Design rules:
  - Frozen dataclass for immutability.
  - Deterministic content_hash() for reproducibility.
  - No numpy in the persisted form; native artefacts are external refs.
  - Epoch refs are mandatory (principle P-06).
  - Native data URI/hash is mandatory (principle P-04).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class RadioObservationPacket:
    """Core observation exchange format — R6 Appendix E.

    One packet per source-specific, time-specific radio observation.
    """

    # ── Identity ────────────────────────────────────────────────────
    packet_id: str
    """Unique packet UUID."""

    source_profile: str
    """RadioFamily + profile version (e.g., 'WIFI_CSI/v2')."""

    receiver_id: str
    """Receiver device identifier."""

    transmitter_id: str = ""
    """Transmitter/illuminator/tag/modem/satellite where applicable."""

    firmware_version: str = ""
    operator: str = ""
    cell_id: str = ""
    satellite_id: str = ""

    # ── Time ────────────────────────────────────────────────────────
    utc_time: Optional[datetime] = None
    """UTC acquisition time with source of time."""

    device_time: Optional[datetime] = None
    """Device-local time."""

    time_source: str = ""
    """Source of time: 'GPSDO', 'NTP', 'PTP', 'device_clock', etc."""

    time_uncertainty_s: Optional[float] = None
    """Time uncertainty in seconds."""

    acquisition_interval_s: Optional[float] = None
    """Duration of the acquisition window."""

    sequence_gap: bool = False
    """Whether a gap in the sequence was detected."""

    trigger_latency_s: Optional[float] = None
    """Latency from trigger to first sample."""

    # ── Space ───────────────────────────────────────────────────────
    tx_position_wgs84: Optional[Tuple[float, float, float]] = None
    """Transmitter (lat, lon, alt_m)."""

    rx_position_wgs84: Optional[Tuple[float, float, float]] = None
    """Receiver (lat, lon, alt_m)."""

    tag_position_wgs84: Optional[Tuple[float, float, float]] = None
    """Tag/target (lat, lon, alt_m) if applicable."""

    position_covariance_m: Optional[Tuple[float, float, float]] = None
    """Position uncertainty (σ_x, σ_y, σ_z)."""

    orientation_ypr_deg: Optional[Tuple[float, float, float]] = None
    """(yaw, pitch, roll) in degrees."""

    polarisation: str = ""
    plot_zone_ref: str = ""
    depth_m: Optional[float] = None

    # ── Waveform ────────────────────────────────────────────────────
    identity_state: str = ""
    """Current IdentityState value."""

    rat_candidate: str = ""
    """RAT candidate or confirmed protocol name."""

    carrier_frequency_hz: Optional[float] = None
    channel: str = ""
    arfcn: str = ""
    bandwidth_hz: Optional[float] = None
    numerology: str = ""
    reference_signal: str = ""
    tx_power_dbm: Optional[float] = None
    beam_id: str = ""
    schedule_ref: str = ""

    # ── Native Data ─────────────────────────────────────────────────
    native_data_uri: str = ""
    """URI to the immutable native artefact (IQ, CSI, radar cube, etc.)."""

    native_data_hash: str = ""
    """Content hash of the native artefact (SHA-256)."""

    native_data_type: str = ""
    """Type/shape descriptor: 'sigMF_iq', 'csi_matrix', 'radar_cube', etc."""

    native_data_compression: str = ""
    masks: List[str] = field(default_factory=list)
    """Applied masks (e.g., 'agc_saturation', 'sample_loss')."""

    raw_corrected_lineage: str = ""
    sample_loss_reason: str = ""
    unavailable_fields: List[str] = field(default_factory=list)

    # ── Action ──────────────────────────────────────────────────────
    action_type: str = "PASSIVE"
    """PASSIVE or ACTIVE."""

    requested_action: str = ""
    executed_action: str = ""
    task_receipt_ref: str = ""
    policy_receipt_ref: str = ""

    # ── Epochs ──────────────────────────────────────────────────────
    geometry_epoch_id: str = ""
    instrument_epoch_id: str = ""
    network_epoch_id: str = ""
    coexistence_epoch_id: str = ""
    calibration_state_id: str = ""
    software_model_epoch_id: str = ""
    coverage_epoch_ref: str = ""
    jurisdiction_ref: str = ""

    # ── Quality ─────────────────────────────────────────────────────
    noise_floor_dbm: Optional[float] = None
    snr_db: Optional[float] = None
    saturated: bool = False
    timing_quality: str = ""
    gain_state: str = ""
    packet_quality: str = ""
    correlation_quality: str = ""
    range_quality: str = ""
    calibration_result: str = ""
    uncertainty_model_ref: str = ""

    # ── Evidence ────────────────────────────────────────────────────
    evidence_role: str = ""
    """EvidenceRole value."""

    authority_scope: str = "evidence_proposal"
    """Always 'evidence_proposal' per principle P-08."""

    allowed_use: str = ""
    dependency_refs: List[str] = field(default_factory=list)
    retention_policy: str = ""
    consent_ref: str = ""
    qualification_ref: str = ""
    expiry: Optional[datetime] = None
    revocation_ref: str = ""

    # ── Serialization ───────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
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
        """Deterministic SHA-256 content hash."""
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
