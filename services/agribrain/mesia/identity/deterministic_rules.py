"""MESIA Deterministic Channel, Raster, and Numerology Rules — R6 §4.2.

Validates whether an observed emission matches standard protocol channel rasters,
bandwidths, subcarrier spacings, and spectral allocations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.wave import WaveCandidate


@dataclass(frozen=True)
class RuleMatchResult:
    """Outcome of evaluating deterministic protocol rules against a candidate."""
    protocol_name: str
    is_compatible: bool
    channel_name: str = ""
    frequency_error_hz: float = 0.0
    bandwidth_error_hz: float = 0.0
    confidence_contribution: float = 0.0
    rationale: str = ""


class DeterministicProtocolRules:
    """Deterministic channel, raster, and numerology validator for major radio families."""

    @staticmethod
    def match_wifi_24g(candidate: WaveCandidate) -> RuleMatchResult:
        """Evaluate IEEE 802.11 b/g/n in 2.4 GHz ISM (Channels 1-14)."""
        freq = candidate.centre_frequency_hz or 0.0
        bw = candidate.bandwidth_hz or 0.0

        if not (2400e6 <= freq <= 2484e6):
            return RuleMatchResult("IEEE_802.11_2.4G", False, rationale="Frequency out of 2.4 GHz ISM band.")

        # 2.4 GHz channels are spaced by 5 MHz starting at 2412 MHz (Ch 1) to 2472 MHz (Ch 13)
        ch_num = int(round((freq - 2407e6) / 5e6))
        if 1 <= ch_num <= 13:
            nominal_freq = 2407e6 + ch_num * 5e6
            freq_err = abs(freq - nominal_freq)
            bw_err = abs(bw - 20e6)
            is_compat = (freq_err <= 1.0e6) and (15e6 <= bw <= 45e6)
            return RuleMatchResult(
                protocol_name="IEEE_802.11_2.4G",
                is_compatible=is_compat,
                channel_name=f"Ch_{ch_num}",
                frequency_error_hz=freq_err,
                bandwidth_error_hz=bw_err,
                confidence_contribution=0.75 if is_compat else 0.0,
                rationale="Matches 802.11 2.4GHz channel raster." if is_compat else "Bandwidth or offset mismatch.",
            )
        return RuleMatchResult("IEEE_802.11_2.4G", False, rationale="Does not match standard channel raster.")

    @staticmethod
    def match_lora_868(candidate: WaveCandidate) -> RuleMatchResult:
        """Evaluate LoRa in EU/Africa 868 MHz SRD band."""
        freq = candidate.centre_frequency_hz or 0.0
        bw = candidate.bandwidth_hz or 0.0

        if not (863e6 <= freq <= 870e6):
            return RuleMatchResult("LoRa_868", False, rationale="Frequency out of 868 MHz SRD band.")

        # Standard LoRa EU channels: 868.1, 868.3, 868.5 MHz with 125 kHz BW
        standard_channels = [868.1e6, 868.3e6, 868.5e6, 867.1e6, 867.3e6, 867.5e6, 867.7e6, 867.9e6]
        closest_ch = min(standard_channels, key=lambda c: abs(c - freq))
        freq_err = abs(freq - closest_ch)
        bw_err = abs(bw - 125e3)

        is_compat = (freq_err <= 50e3) and (100e3 <= bw <= 500e3)
        return RuleMatchResult(
            protocol_name="LoRa_868",
            is_compatible=is_compat,
            channel_name=f"LoRa_{closest_ch/1e6:.1f}MHz",
            frequency_error_hz=freq_err,
            bandwidth_error_hz=bw_err,
            confidence_contribution=0.80 if is_compat else 0.0,
            rationale="Matches EU868 LoRa channel." if is_compat else "Bandwidth or frequency mismatch.",
        )

    @staticmethod
    def match_ble_24g(candidate: WaveCandidate) -> RuleMatchResult:
        """Evaluate Bluetooth Low Energy (BLE) channels 0-39."""
        freq = candidate.centre_frequency_hz or 0.0
        bw = candidate.bandwidth_hz or 0.0

        if not (2402e6 <= freq <= 2480e6):
            return RuleMatchResult("Bluetooth_LE", False, rationale="Frequency out of BLE band.")

        # BLE channels spaced by 2 MHz: 2402 + k*2 MHz
        ch_idx = int(round((freq - 2402e6) / 2e6))
        if 0 <= ch_idx <= 39:
            nom_freq = 2402e6 + ch_idx * 2e6
            freq_err = abs(freq - nom_freq)
            is_compat = (freq_err <= 500e3) and (0.8e6 <= bw <= 2.5e6)
            return RuleMatchResult(
                protocol_name="Bluetooth_LE",
                is_compatible=is_compat,
                channel_name=f"BLE_Ch_{ch_idx}",
                frequency_error_hz=freq_err,
                bandwidth_error_hz=abs(bw - 1e6),
                confidence_contribution=0.70 if is_compat else 0.0,
                rationale="Matches BLE 2MHz channel raster." if is_compat else "Bandwidth/raster mismatch.",
            )
        return RuleMatchResult("Bluetooth_LE", False, rationale="Out of BLE channel range.")

    @classmethod
    def evaluate_candidate(cls, candidate: WaveCandidate) -> List[RuleMatchResult]:
        """Evaluate a WaveCandidate against all standard deterministic rules."""
        evaluators = [cls.match_wifi_24g, cls.match_lora_868, cls.match_ble_24g]
        results = [ev(candidate) for ev in evaluators]
        return [r for r in results if r.is_compatible]
