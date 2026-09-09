"""MESIA RF Bench Calibration & Metrology Models — R6 §1.1 & §14.

Implements S-parameter analysis, VSWR, return loss, cascaded noise figure (Friis formula),
1dB gain compression, linearity/IP3, and VNA calibration standard verification.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SParameterMeasurement:
    """S-parameter vector at a specific frequency."""

    frequency_hz: float
    s11_mag_db: float
    s11_phase_deg: float
    s21_mag_db: float
    s21_phase_deg: float
    s12_mag_db: Optional[float] = None
    s22_mag_db: Optional[float] = None

    @property
    def vswr(self) -> float:
        """Voltage Standing Wave Ratio calculated from S11."""
        # Gamma = 10^(s11_mag_db / 20)
        gamma = 10.0 ** (self.s11_mag_db / 20.0)
        if gamma >= 1.0:
            return float("inf")
        return (1.0 + gamma) / max(1.0 - gamma, 1e-6)

    @property
    def return_loss_db(self) -> float:
        """Return loss (positive quantity: RL = -S11_db)."""
        return -self.s11_mag_db

    @property
    def insertion_loss_db(self) -> float:
        """Insertion loss (positive quantity: IL = -S21_db)."""
        return -self.s21_mag_db

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frequency_hz": self.frequency_hz,
            "s11_mag_db": self.s11_mag_db,
            "s11_phase_deg": self.s11_phase_deg,
            "s21_mag_db": self.s21_mag_db,
            "s21_phase_deg": self.s21_phase_deg,
            "vswr": self.vswr,
            "return_loss_db": self.return_loss_db,
            "insertion_loss_db": self.insertion_loss_db,
        }


def calculate_cascaded_noise_figure(stages: List[Tuple[float, float]]) -> float:
    """Calculate cascaded noise figure using Friis' formula.

    Args:
        stages: List of (gain_db, noise_figure_db) for each stage in the RF chain.

    Returns:
        Total cascaded Noise Figure in dB.

    Formula:
        F_total = F1 + (F2 - 1)/G1 + (F3 - 1)/(G1*G2) + ...
    """
    if not stages:
        return 0.0

    # Convert dB to linear ratios
    linear_stages = []
    for g_db, nf_db in stages:
        g_lin = 10.0 ** (g_db / 10.0)
        f_lin = 10.0 ** (nf_db / 10.0)
        linear_stages.append((g_lin, f_lin))

    f_total_lin = linear_stages[0][1]
    cum_gain = linear_stages[0][0]

    for g_lin, f_lin in linear_stages[1:]:
        f_total_lin += (f_lin - 1.0) / max(cum_gain, 1e-9)
        cum_gain *= g_lin

    return 10.0 * math.log10(max(f_total_lin, 1.0))


def calculate_p1db_and_iip3(
    pin_pout_curve: List[Tuple[float, float]],
    small_signal_gain_db: float,
) -> Tuple[Optional[float], Optional[float]]:
    """Determine 1dB compression point (Pin_1dB) and estimated IIP3 from Pin-Pout sweep.

    Args:
        pin_pout_curve: List of (Pin_dBm, Pout_dBm) points.
        small_signal_gain_db: Linear small-signal gain in dB.

    Returns:
        (pin_1db_dbm, iip3_dbm)
    """
    pin_1db = None
    for pin, pout in sorted(pin_pout_curve, key=lambda x: x[0]):
        expected_pout = pin + small_signal_gain_db
        compression = expected_pout - pout
        if compression >= 1.0:
            pin_1db = pin
            break

    iip3 = None
    if pin_1db is not None:
        # Rule of thumb for standard amplifiers / mixers: IIP3 ~= Pin_1dB + 9.6 to 10.6 dB
        iip3 = pin_1db + 10.0

    return pin_1db, iip3


@dataclass(frozen=True)
class RFBenchTestReport:
    """Complete RF bench calibration validation report for a receiver/LNA chain."""

    report_id: str
    device_id: str
    tested_at: Optional[datetime] = None
    frequency_sweep: List[SParameterMeasurement] = field(default_factory=list)
    cascaded_noise_figure_db: Optional[float] = None
    p1db_input_dbm: Optional[float] = None
    iip3_dbm: Optional[float] = None
    dynamic_range_db: Optional[float] = None
    spur_free_dynamic_range_db: Optional[float] = None
    is_compliant: bool = True
    non_compliance_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            val = getattr(self, f)
            if isinstance(val, datetime):
                val = val.isoformat()
            elif isinstance(val, list):
                val = [x.to_dict() if hasattr(x, "to_dict") else x for x in val]
            d[f] = val
        return d

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
