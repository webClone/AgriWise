"""MESIA Epoch Types — R6 §7.3.

Six typed epochs that make every reconfiguration scientifically visible.
Each epoch is immutable, content-hashable, and chainable to its
predecessor.

  GeometryEpoch     — Position/orientation/mount/cable/antenna change.
  InstrumentEpoch   — Device/firmware/driver/OS/gain/clock/power change.
  NetworkEpoch      — Operator/cell/band/channel/beam/scheduler/RRC change.
  CoexistenceEpoch  — Interference/neighbours/machinery/people/motion.
  CalibrationState  — Reference validity, uncertainty, drift, expiry.
  SoftwareModelEpoch — Detector/decoder/profile/feature/model version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _content_hash(d: Dict[str, Any]) -> str:
    """Deterministic SHA-256 of a JSON-serializable dict."""
    raw = json.dumps(d, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Base ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _EpochBase:
    """Common fields for all epoch types."""

    epoch_id: str
    """Unique identifier (UUID recommended)."""

    triggered_at: datetime
    """UTC timestamp of the triggering change."""

    trigger_reason: str
    """Human-readable reason for the epoch transition."""

    previous_epoch_id: Optional[str] = None
    """Chain link to the preceding epoch (None for the first)."""

    def _base_dict(self) -> Dict[str, Any]:
        return {
            "epoch_id": self.epoch_id,
            "triggered_at": self.triggered_at.isoformat(),
            "trigger_reason": self.trigger_reason,
            "previous_epoch_id": self.previous_epoch_id,
        }


# ── GeometryEpoch ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class GeometryEpoch(_EpochBase):
    """R6 §7.3 — Triggered by position/orientation/mount/cable/antenna
    or trajectory change.

    Scientific consequence: Recompute sensitivity kernels; invalidate
    site calibration where material.
    """

    position_wgs84: Optional[Tuple[float, float, float]] = None
    """(lat, lon, alt_m) — WGS84 position of the device."""

    position_local_enu: Optional[Tuple[float, float, float]] = None
    """(e, n, u) in metres relative to the field origin."""

    orientation_ypr_deg: Optional[Tuple[float, float, float]] = None
    """(yaw, pitch, roll) in degrees."""

    antenna_path_ref: Optional[str] = None
    """Reference to the AntennaPathManifest."""

    mount_description: str = ""
    """Mount type, cable routing, height/depth."""

    covariance_m: Optional[Tuple[float, float, float]] = None
    """(σ_x, σ_y, σ_z) position standard deviations in metres."""

    position_covariance: Optional[Tuple[float, float, float, float, float, float]] = None
    """Upper-triangular 3x3 covariance matrix (σ_xx, σ_xy, σ_xz, σ_yy, σ_yz, σ_zz) in m²."""

    orientation_covariance_deg2: Optional[Tuple[float, float, float]] = None
    """(σ_yaw², σ_pitch², σ_roll²) orientation variance in deg²."""

    antenna_model: str = ""
    """Antenna model identifier (e.g. UBLOX_ANN_MB, MIKROTIK_DIPOLE_2GHZ)."""

    phase_center_offset_mm: Optional[Tuple[float, float, float]] = None
    """(Δx, Δy, Δz) electrical Phase Center Offset in mm relative to ARP."""

    phase_center_variation_ref: Optional[str] = None
    """Reference to ANTEX or calibrated Phase Center Variation (PCV) model."""

    mount_model: str = ""
    """Rigid fixture or mast mount model identifier."""

    wiring_route_hash: Optional[str] = None
    """SHA-256 hash of the physical cable run topology."""

    survey_method: str = "MANUAL"
    """RTK_FIXED, RTK_FLOAT, DGPS, TOTAL_STATION, MANUAL (Monograph §143)."""

    survey_time_utc: Optional[datetime] = None
    """UTC timestamp when the physical survey was conducted."""

    geometry_version: str = "1.0.0"
    """Schema version for the geometry configuration."""

    geometry_hash: Optional[str] = None
    """Immutable integrity hash of the anchor geometry definition."""

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d.update({
            "epoch_type": "GeometryEpoch",
            "position_wgs84": self.position_wgs84,
            "position_local_enu": self.position_local_enu,
            "orientation_ypr_deg": self.orientation_ypr_deg,
            "antenna_path_ref": self.antenna_path_ref,
            "mount_description": self.mount_description,
            "covariance_m": self.covariance_m,
            "position_covariance": self.position_covariance,
            "orientation_covariance_deg2": self.orientation_covariance_deg2,
            "antenna_model": self.antenna_model,
            "phase_center_offset_mm": self.phase_center_offset_mm,
            "phase_center_variation_ref": self.phase_center_variation_ref,
            "mount_model": self.mount_model,
            "wiring_route_hash": self.wiring_route_hash,
            "survey_method": self.survey_method,
            "survey_time_utc": self.survey_time_utc.isoformat() if self.survey_time_utc else None,
            "geometry_version": self.geometry_version,
            "geometry_hash": self.geometry_hash,
        })
        return d

    def content_hash(self) -> str:
        return _content_hash(self.to_dict())


# ── InstrumentEpoch ────────────────────────────────────────────────────

@dataclass(frozen=True)
class InstrumentEpoch(_EpochBase):
    """R6 §7.3 — Triggered by device/firmware/driver/OS/modem/gain/clock/
    power or repair change.

    Scientific consequence: Revalidate native capture and behaviour
    transfer.
    """

    device_id: str = ""
    hardware_model: str = ""
    firmware_version: str = ""
    driver_version: str = ""
    os_version: str = ""
    modem_version: str = ""
    gain_chain_description: str = ""
    clock_source: str = ""
    power_state: str = ""
    temperature_c: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d.update({
            "epoch_type": "InstrumentEpoch",
            "device_id": self.device_id,
            "hardware_model": self.hardware_model,
            "firmware_version": self.firmware_version,
            "driver_version": self.driver_version,
            "os_version": self.os_version,
            "modem_version": self.modem_version,
            "gain_chain_description": self.gain_chain_description,
            "clock_source": self.clock_source,
            "power_state": self.power_state,
            "temperature_c": self.temperature_c,
        })
        return d

    def content_hash(self) -> str:
        return _content_hash(self.to_dict())


# ── NetworkEpoch ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class NetworkEpoch(_EpochBase):
    """R6 §7.3 — Triggered by operator/cell/band/channel/beam/scheduler/
    RRC/RAN/QoS change.

    Scientific consequence: Prevent network change being called
    environmental.
    """

    operator: str = ""
    cell_id: str = ""
    band: str = ""
    channel: str = ""
    bandwidth_mhz: Optional[float] = None
    beam_id: str = ""
    scheduler_config: str = ""
    rrc_state: str = ""
    tdd_config: str = ""
    qos_config: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d.update({
            "epoch_type": "NetworkEpoch",
            "operator": self.operator,
            "cell_id": self.cell_id,
            "band": self.band,
            "channel": self.channel,
            "bandwidth_mhz": self.bandwidth_mhz,
            "beam_id": self.beam_id,
            "scheduler_config": self.scheduler_config,
            "rrc_state": self.rrc_state,
            "tdd_config": self.tdd_config,
            "qos_config": self.qos_config,
        })
        return d

    def content_hash(self) -> str:
        return _content_hash(self.to_dict())


# ── CoexistenceEpoch ───────────────────────────────────────────────────

@dataclass(frozen=True)
class CoexistenceEpoch(_EpochBase):
    """R6 §7.3 — Triggered by interference, neighbours, machinery,
    people, motion or weather regime change.

    Scientific consequence: Re-evaluate nuisance attribution and
    detection baseline.
    """

    description: str = ""
    neighbouring_networks: List[str] = field(default_factory=list)
    interference_sources: List[str] = field(default_factory=list)
    machinery_present: bool = False
    people_present: bool = False
    weather_regime: str = ""
    motion_detected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d.update({
            "epoch_type": "CoexistenceEpoch",
            "description": self.description,
            "neighbouring_networks": list(self.neighbouring_networks),
            "interference_sources": list(self.interference_sources),
            "machinery_present": self.machinery_present,
            "people_present": self.people_present,
            "weather_regime": self.weather_regime,
            "motion_detected": self.motion_detected,
        })
        return d

    def content_hash(self) -> str:
        return _content_hash(self.to_dict())


# ── CalibrationState ───────────────────────────────────────────────────

@dataclass(frozen=True)
class CalibrationState(_EpochBase):
    """R6 §7.3 — Tracks reference validity, uncertainty, drift, expiry
    or failure.

    Scientific consequence: Demote/revoke dependent evidence and
    reprocess if justified.
    """

    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    uncertainty_db: Optional[float] = None
    reference_artefact_ref: str = ""
    drift_sentinel_ref: str = ""
    status: str = "VALID"  # VALID | DRIFTING | EXPIRED | FAILED
    demotion_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d.update({
            "epoch_type": "CalibrationState",
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "uncertainty_db": self.uncertainty_db,
            "reference_artefact_ref": self.reference_artefact_ref,
            "drift_sentinel_ref": self.drift_sentinel_ref,
            "status": self.status,
            "demotion_reason": self.demotion_reason,
        })
        return d

    def content_hash(self) -> str:
        return _content_hash(self.to_dict())

    @property
    def is_valid(self) -> bool:
        return self.status == "VALID"


# ── SoftwareModelEpoch ─────────────────────────────────────────────────

@dataclass(frozen=True)
class SoftwareModelEpoch(_EpochBase):
    """R6 §7.3 — Triggered by detector, decoder, profile, feature, model
    or ASMAE operator version change.

    Scientific consequence: Preserve exact replay and compare promotion
    evidence.
    """

    component: str = ""
    version: str = ""
    model_hash: str = ""
    training_data_ref: str = ""
    split_manifest_ref: str = ""
    previous_version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d.update({
            "epoch_type": "SoftwareModelEpoch",
            "component": self.component,
            "version": self.version,
            "model_hash": self.model_hash,
            "training_data_ref": self.training_data_ref,
            "split_manifest_ref": self.split_manifest_ref,
            "previous_version": self.previous_version,
        })
        return d

    def content_hash(self) -> str:
        return _content_hash(self.to_dict())
