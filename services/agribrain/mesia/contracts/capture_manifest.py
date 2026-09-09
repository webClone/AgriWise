"""MESIA SigMF Capture Manifest & Radio Profile Contracts — R6 §8.2 / P-04.

Provides atomic, immutable, content-addressed capture manifests that bind
raw radio binary data (.sigmf-data) and metadata (.sigmf-meta) together.
Eliminates synthetic timestamps and unscoped storage paths.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class QuarantinedCaptureException(Exception):
    """Raised when an ingested or stored radio capture lacks valid provenance or metadata.

    Captures with missing metadata, absent timestamps, or hash mismatches must be
    quarantined immediately and fail closed.
    """
    pass


@dataclass(frozen=True)
class RadioProfile:
    """Hardware and RF front-end configuration for an opportunistic radio capture."""

    family: str
    """Radio family: 'WIFI_CSI', 'GNSS_R', 'CELLULAR', 'UHF', etc."""

    frequency_hz: float
    """Centre carrier frequency in Hz."""

    bandwidth_hz: float
    """Channel bandwidth or sample rate in Hz."""

    antenna_array: str = ""
    """Antenna configuration or layout descriptor."""

    rx_gain_db: float = 0.0
    """Receiver RF/AGC gain in dB."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family": self.family,
            "frequency_hz": self.frequency_hz,
            "bandwidth_hz": self.bandwidth_hz,
            "antenna_array": self.antenna_array,
            "rx_gain_db": self.rx_gain_db,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RadioProfile:
        return cls(
            family=str(data.get("family", "UNKNOWN")),
            frequency_hz=float(data.get("frequency_hz", 0.0)),
            bandwidth_hz=float(data.get("bandwidth_hz", 0.0)),
            antenna_array=str(data.get("antenna_array", "")),
            rx_gain_db=float(data.get("rx_gain_db", 0.0)),
        )


@dataclass(frozen=True)
class SigMFCaptureManifest:
    """Immutable, content-addressed manifest binding raw radio binary to SigMF metadata.

    Guarantees:
      1. capture_id is deterministic SHA-256 of data bytes + meta bytes.
      2. capture_timestamp_utc is authentic and immutable; no datetime.now() fallback.
      3. storage_prefix is strictly scoped by tenant_id and plot_id.
    """

    capture_id: str
    """Combined content-addressed hash (SHA-256)."""

    tenant_id: str
    """Tenant owning this capture."""

    plot_id: str
    """Plot / field parcel boundary ID."""

    capture_timestamp_utc: datetime
    """Authentic physical capture timestamp (UTC)."""

    data_sha256: str
    """SHA-256 digest of the .sigmf-data payload."""

    meta_sha256: str
    """SHA-256 digest of the .sigmf-meta payload."""

    radio_profile: RadioProfile
    """Front-end radio configuration."""

    packet_count: int
    """Number of subcarriers or samples in the capture."""

    storage_prefix: str
    """Scoped base path (excluding .sigmf-data / .sigmf-meta extension)."""

    def __post_init__(self) -> None:
        if not self.capture_id or len(self.capture_id) < 16:
            raise ValueError("Invalid capture_id: must be a non-empty hash")
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id must not be empty")
        if not self.plot_id or not self.plot_id.strip():
            raise ValueError("plot_id must not be empty")
        if not isinstance(self.capture_timestamp_utc, datetime):
            raise ValueError("capture_timestamp_utc must be a datetime object")

    @property
    def data_path(self) -> str:
        return f"{self.storage_prefix}.sigmf-data"

    @property
    def meta_path(self) -> str:
        return f"{self.storage_prefix}.sigmf-meta"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "tenant_id": self.tenant_id,
            "plot_id": self.plot_id,
            "capture_timestamp_utc": self.capture_timestamp_utc.isoformat(),
            "data_sha256": self.data_sha256,
            "meta_sha256": self.meta_sha256,
            "radio_profile": self.radio_profile.to_dict(),
            "packet_count": self.packet_count,
            "storage_prefix": self.storage_prefix,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> SigMFCaptureManifest:
        ts_str = d["capture_timestamp_utc"]
        if isinstance(ts_str, str):
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        else:
            ts = ts_str
        return cls(
            capture_id=d["capture_id"],
            tenant_id=d["tenant_id"],
            plot_id=d["plot_id"],
            capture_timestamp_utc=ts,
            data_sha256=d["data_sha256"],
            meta_sha256=d["meta_sha256"],
            radio_profile=RadioProfile.from_dict(d.get("radio_profile", {})),
            packet_count=int(d.get("packet_count", 0)),
            storage_prefix=d["storage_prefix"],
        )

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
