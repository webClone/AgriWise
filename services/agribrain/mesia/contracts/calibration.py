"""MESIA Calibration Contracts — R6 §4, §7.3, Appendix A.

SpectrumCalibrationEpoch — Noise, gain, spur/image, amplitude/frequency/time
calibration and validity window.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SpectrumCalibrationEpoch:
    """Spectrum calibration window and validity metadata — R6 Appendix A.

    Tracks noise floor, receiver spurs, image responses, amplitude and
    frequency calibration for a specific receiver/antenna path over time.
    """

    calibration_id: str
    receiver_id: str
    antenna_path_ref: str = ""

    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

    # Noise & Dynamic Range
    noise_figure_db: Optional[float] = None
    noise_floor_dbm_per_hz: Optional[float] = None
    dynamic_range_db: Optional[float] = None

    # Linearity & Gain
    gain_correction_curve_ref: str = ""
    p1db_compression_point_dbm: Optional[float] = None

    # Spurs, Images & Harmonics
    known_spurs_hz: List[float] = field(default_factory=list)
    image_rejection_db: Optional[float] = None
    harmonic_suppression_db: Optional[float] = None

    # Frequency & Time
    frequency_offset_ppm: Optional[float] = None
    phase_noise_dbc_per_hz: Optional[float] = None
    time_uncertainty_ns: Optional[float] = None

    # Metrology Traceability
    calibration_method: str = ""
    """e.g., 'LAB_CALIBRATION', 'LOOPBACK', 'REFERENCE_SOURCE', 'SENTINEL'."""

    calibrated_by: str = ""
    standards_traceability_ref: str = ""
    is_valid: bool = True
    invalidation_reason: str = ""

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
