"""MESIA Spectrum Jurisdiction & Regulatory Policy Engine — R6 §2.5 & §19.3.

Binds allowed receive/transmit bands, EIRP limits, maximum duty cycles,
licence profiles, and active-probe safety permissions by jurisdiction.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class JurisdictionRegion(str, Enum):
    """Supported spectrum regulatory jurisdictions."""
    ALGERIA_ARPT_ANF = "ALGERIA_ARPT_ANF"
    EU_RED_ETSI = "EU_RED_ETSI"
    US_FCC = "US_FCC"
    GLOBAL_ITU_REGION_1 = "GLOBAL_ITU_REGION_1"


@dataclass(frozen=True)
class FrequencyBandPolicy:
    """Regulatory rule for a specific frequency band."""

    band_name: str
    freq_start_hz: float
    freq_end_hz: float
    is_unlicensed_ism: bool
    max_eirp_dbm: float
    max_duty_cycle_pct: float
    requires_licence: bool
    allow_active_probing: bool


@dataclass(frozen=True)
class JurisdictionProfile:
    """Complete regulatory profile for a geographic jurisdiction."""

    jurisdiction: JurisdictionRegion
    profile_version: str = "2026.1"
    band_policies: List[FrequencyBandPolicy] = field(default_factory=list)

    def find_policy_for_frequency(self, freq_hz: float) -> Optional[FrequencyBandPolicy]:
        """Find matching regulatory band policy for a given carrier frequency."""
        for p in self.band_policies:
            if p.freq_start_hz <= freq_hz <= p.freq_end_hz:
                return p
        return None

    def validate_transmission(
        self,
        freq_hz: float,
        tx_power_dbm: float,
        duty_cycle_pct: float,
        licence_ref: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Validate whether an active transmission is permitted under this jurisdiction's rules."""
        policy = self.find_policy_for_frequency(freq_hz)
        if not policy:
            return False, f"Frequency {freq_hz/1e6:.3f} MHz is not authorized in jurisdiction {self.jurisdiction.value}."

        if not policy.allow_active_probing:
            return False, f"Active probing is prohibited in band {policy.band_name}."

        if tx_power_dbm > policy.max_eirp_dbm:
            return False, f"TX power {tx_power_dbm} dBm exceeds maximum EIRP limit {policy.max_eirp_dbm} dBm in {policy.band_name}."

        if duty_cycle_pct > policy.max_duty_cycle_pct:
            return False, f"Duty cycle {duty_cycle_pct}% exceeds maximum permitted {policy.max_duty_cycle_pct}% in {policy.band_name}."

        if policy.requires_licence and (not licence_ref or not licence_ref.strip()):
            return False, f"Band {policy.band_name} requires an explicit regulatory licence reference."

        return True, "Authorized"


def get_default_algeria_profile() -> JurisdictionProfile:
    """Pre-configured regulatory profile for Algeria (ARPT/ANF)."""
    return JurisdictionProfile(
        jurisdiction=JurisdictionRegion.ALGERIA_ARPT_ANF,
        band_policies=[
            # 433 MHz ISM
            FrequencyBandPolicy(
                band_name="ISM_433",
                freq_start_hz=433.05e6,
                freq_end_hz=434.79e6,
                is_unlicensed_ism=True,
                max_eirp_dbm=10.0,
                max_duty_cycle_pct=10.0,
                requires_licence=False,
                allow_active_probing=True,
            ),
            # 868 MHz SRD / LoRa
            FrequencyBandPolicy(
                band_name="SRD_868",
                freq_start_hz=868.0e6,
                freq_end_hz=870.0e6,
                is_unlicensed_ism=True,
                max_eirp_dbm=14.0,
                max_duty_cycle_pct=1.0,
                requires_licence=False,
                allow_active_probing=True,
            ),
            # 2.4 GHz ISM / Wi-Fi
            FrequencyBandPolicy(
                band_name="ISM_2400",
                freq_start_hz=2400.0e6,
                freq_end_hz=2483.5e6,
                is_unlicensed_ism=True,
                max_eirp_dbm=20.0,
                max_duty_cycle_pct=100.0,
                requires_licence=False,
                allow_active_probing=True,
            ),
            # 5 GHz WLAN (5150-5350, 5470-5725 MHz)
            FrequencyBandPolicy(
                band_name="WLAN_5GHZ",
                freq_start_hz=5150.0e6,
                freq_end_hz=5725.0e6,
                is_unlicensed_ism=True,
                max_eirp_dbm=23.0,
                max_duty_cycle_pct=100.0,
                requires_licence=False,
                allow_active_probing=True,
            ),
            # 3.5 GHz Licensed 5G FR1 (n78)
            FrequencyBandPolicy(
                band_name="CELLULAR_3500_N78",
                freq_start_hz=3400.0e6,
                freq_end_hz=3800.0e6,
                is_unlicensed_ism=False,
                max_eirp_dbm=30.0,
                max_duty_cycle_pct=100.0,
                requires_licence=True,
                allow_active_probing=True,
            ),
        ],
    )
