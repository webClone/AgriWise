"""MESIA Receiver Self-Test & Diagnostic Diagnostics — R6 §2.7.

Runs pre-flight and scheduled receiver health checks: reference-tone injection,
noise diode/load checks, loopback continuity, and storage throughput checks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DiagnosticSelfTestReport:
    """Outcome of a receiver hardware self-test."""

    test_id: str
    receiver_id: str
    executed_at: datetime

    # Sub-test outcomes (Pass/Fail)
    reference_tone_check_passed: bool
    noise_floor_check_passed: bool
    loopback_continuity_passed: bool
    clock_lock_passed: bool
    storage_throughput_passed: bool

    measured_noise_floor_dbm: float
    measured_clock_offset_ppm: float
    storage_write_speed_mb_s: float

    overall_health: str = "HEALTHY"
    """'HEALTHY', 'DEGRADED', 'SATURATED', 'OFFLINE', 'FAULT'."""

    diagnostic_notes: List[str] = field(default_factory=list)

    @property
    def all_checks_passed(self) -> bool:
        return (
            self.reference_tone_check_passed
            and self.noise_floor_check_passed
            and self.loopback_continuity_passed
            and self.clock_lock_passed
            and self.storage_throughput_passed
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "receiver_id": self.receiver_id,
            "executed_at": self.executed_at.isoformat(),
            "reference_tone_check_passed": self.reference_tone_check_passed,
            "noise_floor_check_passed": self.noise_floor_check_passed,
            "loopback_continuity_passed": self.loopback_continuity_passed,
            "clock_lock_passed": self.clock_lock_passed,
            "storage_throughput_passed": self.storage_throughput_passed,
            "measured_noise_floor_dbm": self.measured_noise_floor_dbm,
            "measured_clock_offset_ppm": self.measured_clock_offset_ppm,
            "storage_write_speed_mb_s": self.storage_write_speed_mb_s,
            "overall_health": self.overall_health,
            "diagnostic_notes": list(self.diagnostic_notes),
        }

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SelfTestRunner:
    """Executes automated diagnostic self-tests on receiver hardware."""

    @staticmethod
    def evaluate_test(
        test_id: str,
        receiver_id: str,
        measured_tone_level_dbm: float,
        expected_tone_level_dbm: float,
        measured_noise_floor_dbm: float,
        expected_noise_floor_dbm: float,
        loopback_loss_db: float,
        max_loopback_loss_db: float,
        clock_offset_ppm: float,
        max_clock_offset_ppm: float,
        storage_write_speed_mb_s: float,
        min_storage_speed_mb_s: float = 100.0,
    ) -> DiagnosticSelfTestReport:
        """Evaluate measured physical self-test parameters against tolerances."""
        notes = []

        # 1. Reference tone
        tone_err = abs(measured_tone_level_dbm - expected_tone_level_dbm)
        tone_passed = tone_err <= 1.0
        if not tone_passed:
            notes.append(f"Tone level error {tone_err:.2f} dB exceeds 1.0 dB threshold.")

        # 2. Noise floor (check for saturation > -40 dBm or dead receiver < -140 dBm)
        noise_passed = expected_noise_floor_dbm - 10.0 <= measured_noise_floor_dbm <= expected_noise_floor_dbm + 10.0
        if not noise_passed:
            notes.append(f"Noise floor {measured_noise_floor_dbm:.1f} dBm out of expected range.")

        # 3. Loopback
        loopback_passed = loopback_loss_db <= max_loopback_loss_db
        if not loopback_passed:
            notes.append(f"Loopback loss {loopback_loss_db:.2f} dB exceeds max {max_loopback_loss_db:.2f} dB.")

        # 4. Clock
        clock_passed = abs(clock_offset_ppm) <= max_clock_offset_ppm
        if not clock_passed:
            notes.append(f"Clock offset {clock_offset_ppm:.2f} ppm exceeds {max_clock_offset_ppm:.2f} ppm.")

        # 5. Storage
        storage_passed = storage_write_speed_mb_s >= min_storage_speed_mb_s
        if not storage_passed:
            notes.append(f"Storage speed {storage_write_speed_mb_s:.1f} MB/s below minimum {min_storage_speed_mb_s} MB/s.")

        # Health state determination
        if all([tone_passed, noise_passed, loopback_passed, clock_passed, storage_passed]):
            overall_health = "HEALTHY"
        elif measured_noise_floor_dbm > -40.0:
            overall_health = "SATURATED"
        elif not loopback_passed or not tone_passed:
            overall_health = "FAULT"
        else:
            overall_health = "DEGRADED"

        now = datetime.now(timezone.utc)
        return DiagnosticSelfTestReport(
            test_id=test_id,
            receiver_id=receiver_id,
            executed_at=now,
            reference_tone_check_passed=tone_passed,
            noise_floor_check_passed=noise_passed,
            loopback_continuity_passed=loopback_passed,
            clock_lock_passed=clock_passed,
            storage_throughput_passed=storage_passed,
            measured_noise_floor_dbm=measured_noise_floor_dbm,
            measured_clock_offset_ppm=clock_offset_ppm,
            storage_write_speed_mb_s=storage_write_speed_mb_s,
            overall_health=overall_health,
            diagnostic_notes=notes,
        )
