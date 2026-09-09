"""MESIA SigMF (Signal Metadata Format) Adapter — R6 §8.2.

Implements SigMF-compliant metadata generation for generic IQ recordings
as specified in the blueprint's native storage requirements.

Reference: https://sigmf.org — SigMF specification v1.0.0.

Storage approach from §8.2:
    'SigMF recording plus immutable object/chunk storage'
    Mandatory context: sample type/rate, centre frequency, capture
    segments, annotations, clock/calibration extension.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


SIGMF_VERSION = "1.0.0"
MESIA_SIGMF_EXTENSION = "mesia-calibration"
MESIA_SIGMF_EXTENSION_VERSION = "0.1.0"


@dataclass(frozen=True)
class SigMFCapture:
    """SigMF capture segment — maps to a contiguous IQ recording block."""

    sample_start: int
    """Zero-based sample index where this capture begins."""

    frequency_hz: float
    """Centre frequency in Hz."""

    datetime_utc: Optional[str] = None
    """ISO 8601 UTC timestamp of the first sample."""

    global_index: int = 0

    # MESIA calibration extension fields
    clock_source: str = ""
    """e.g. 'GPSDO', 'TCXO', 'internal'."""

    clock_uncertainty_ppb: Optional[float] = None
    gain_db: Optional[float] = None
    temperature_celsius: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "core:sample_start": self.sample_start,
            "core:frequency": self.frequency_hz,
        }
        if self.datetime_utc:
            d["core:datetime"] = self.datetime_utc
        if self.global_index:
            d["core:global_index"] = self.global_index
        if self.clock_source:
            d[f"{MESIA_SIGMF_EXTENSION}:clock_source"] = self.clock_source
        if self.clock_uncertainty_ppb is not None:
            d[f"{MESIA_SIGMF_EXTENSION}:clock_uncertainty_ppb"] = self.clock_uncertainty_ppb
        if self.gain_db is not None:
            d[f"{MESIA_SIGMF_EXTENSION}:gain_db"] = self.gain_db
        if self.temperature_celsius is not None:
            d[f"{MESIA_SIGMF_EXTENSION}:temperature_celsius"] = self.temperature_celsius
        return d


@dataclass(frozen=True)
class SigMFAnnotation:
    """SigMF annotation — marks a region of interest within the recording."""

    sample_start: int
    sample_count: int
    frequency_lower_hz: Optional[float] = None
    frequency_upper_hz: Optional[float] = None
    label: str = ""
    comment: str = ""

    # MESIA extension
    identity_state: str = ""
    detector_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "core:sample_start": self.sample_start,
            "core:sample_count": self.sample_count,
        }
        if self.frequency_lower_hz is not None:
            d["core:freq_lower_edge"] = self.frequency_lower_hz
        if self.frequency_upper_hz is not None:
            d["core:freq_upper_edge"] = self.frequency_upper_hz
        if self.label:
            d["core:label"] = self.label
        if self.comment:
            d["core:comment"] = self.comment
        if self.identity_state:
            d[f"{MESIA_SIGMF_EXTENSION}:identity_state"] = self.identity_state
        if self.detector_type:
            d[f"{MESIA_SIGMF_EXTENSION}:detector_type"] = self.detector_type
        return d


@dataclass(frozen=True)
class SigMFMetadata:
    """Complete SigMF metadata object for a single recording."""

    # Global fields
    datatype: str = "cf32_le"
    """SigMF data type: cf32_le (complex float32 little-endian) default."""

    sample_rate_hz: float = 0.0
    version: str = SIGMF_VERSION
    sha256: str = ""
    """SHA-256 hash of the companion .sigmf-data file."""

    description: str = ""
    author: str = "MESIA Observatory"
    recorder: str = ""
    hw: str = ""
    """Hardware description."""

    # MESIA extension
    receiver_id: str = ""
    instrument_epoch_id: str = ""
    geometry_epoch_id: str = ""
    calibration_state_id: str = ""

    captures: List[SigMFCapture] = field(default_factory=list)
    annotations: List[SigMFAnnotation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        global_block: Dict[str, Any] = {
            "core:datatype": self.datatype,
            "core:sample_rate": self.sample_rate_hz,
            "core:version": self.version,
            "core:description": self.description,
            "core:author": self.author,
        }
        if self.sha256:
            global_block["core:sha256"] = self.sha256
        if self.recorder:
            global_block["core:recorder"] = self.recorder
        if self.hw:
            global_block["core:hw"] = self.hw

        # MESIA extension fields
        global_block[f"{MESIA_SIGMF_EXTENSION}:version"] = MESIA_SIGMF_EXTENSION_VERSION
        if self.receiver_id:
            global_block[f"{MESIA_SIGMF_EXTENSION}:receiver_id"] = self.receiver_id
        if self.instrument_epoch_id:
            global_block[f"{MESIA_SIGMF_EXTENSION}:instrument_epoch_id"] = self.instrument_epoch_id
        if self.geometry_epoch_id:
            global_block[f"{MESIA_SIGMF_EXTENSION}:geometry_epoch_id"] = self.geometry_epoch_id
        if self.calibration_state_id:
            global_block[f"{MESIA_SIGMF_EXTENSION}:calibration_state_id"] = self.calibration_state_id

        return {
            "global": global_block,
            "captures": [c.to_dict() for c in self.captures],
            "annotations": [a.to_dict() for a in self.annotations],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to SigMF JSON (.sigmf-meta)."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def content_hash(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


class SigMFAdapter:
    """Adapter for creating and validating SigMF metadata objects.

    Usage:
        meta = SigMFAdapter.create_metadata(
            datatype="cf32_le",
            sample_rate_hz=20e6,
            captures=[SigMFCapture(sample_start=0, frequency_hz=2.44e9)],
        )
        json_str = meta.to_json()
    """

    @staticmethod
    def create_metadata(
        datatype: str = "cf32_le",
        sample_rate_hz: float = 0.0,
        description: str = "",
        hw: str = "",
        receiver_id: str = "",
        instrument_epoch_id: str = "",
        geometry_epoch_id: str = "",
        calibration_state_id: str = "",
        data_sha256: str = "",
        captures: Optional[List[SigMFCapture]] = None,
        annotations: Optional[List[SigMFAnnotation]] = None,
    ) -> SigMFMetadata:
        """Create a SigMF metadata object with MESIA calibration extension."""
        return SigMFMetadata(
            datatype=datatype,
            sample_rate_hz=sample_rate_hz,
            sha256=data_sha256,
            description=description,
            hw=hw,
            receiver_id=receiver_id,
            instrument_epoch_id=instrument_epoch_id,
            geometry_epoch_id=geometry_epoch_id,
            calibration_state_id=calibration_state_id,
            captures=captures or [],
            annotations=annotations or [],
        )

    @staticmethod
    def validate_metadata(meta: SigMFMetadata) -> List[str]:
        """Validate SigMF metadata completeness per R6 §8.2 requirements.

        Returns a list of validation errors (empty if valid).
        """
        errors: List[str] = []
        if not meta.datatype:
            errors.append("Missing core:datatype")
        if meta.sample_rate_hz <= 0:
            errors.append("sample_rate_hz must be positive")
        if not meta.captures:
            errors.append("At least one capture segment is required")
        for i, cap in enumerate(meta.captures):
            if cap.frequency_hz <= 0:
                errors.append(f"Capture[{i}]: frequency_hz must be positive")
        return errors
