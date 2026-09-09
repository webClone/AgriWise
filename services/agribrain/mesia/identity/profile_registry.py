"""MESIA Signal Identity Profile Registry & Governance — R6 §4.8 & §6.1.

Maintains versioned, governed SignalIdentityProfile records establishing
evidence requirements, frequency bounds, supported front-ends, and rollback rules.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..ontology.confirmation_levels import ConfirmationLevel
from ..ontology.front_ends import FrontEndClass


@dataclass(frozen=True)
class SignalIdentityProfile:
    """Versioned governance profile defining how a specific protocol is identified."""

    profile_id: str
    protocol_name: str
    version: str = "1.0.0"

    min_required_confirmation_level: int = 4
    """Default 4 (PROTOCOL_DECODE) or 5 (TRUSTED_NATIVE_CONTROL)."""

    supported_front_end_classes: List[str] = field(default_factory=list)
    frequency_bounds_hz: Tuple[float, float] = (0.0, 100e9)
    known_confounders: List[str] = field(default_factory=list)
    test_corpus_ref: str = ""
    is_active: bool = True
    rollback_profile_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "protocol_name": self.protocol_name,
            "version": self.version,
            "min_required_confirmation_level": self.min_required_confirmation_level,
            "supported_front_end_classes": list(self.supported_front_end_classes),
            "frequency_bounds_hz": list(self.frequency_bounds_hz),
            "known_confounders": list(self.known_confounders),
            "test_corpus_ref": self.test_corpus_ref,
            "is_active": self.is_active,
            "rollback_profile_id": self.rollback_profile_id,
        }

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SignalIdentityProfileRegistry:
    """Catalogue of governed SignalIdentityProfiles."""

    def __init__(self) -> None:
        self._profiles: Dict[str, SignalIdentityProfile] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Initialize standard R6 profiles."""
        wifi_profile = SignalIdentityProfile(
            profile_id="sip-wifi-ofdm-v1",
            protocol_name="IEEE_802.11_OFDM",
            version="1.0.0",
            min_required_confirmation_level=4,
            supported_front_end_classes=[FrontEndClass.F1_NATIVE_RADIO.value, FrontEndClass.F2_WIDEBAND_SDR.value],
            frequency_bounds_hz=(2400e6, 6000e6),
            known_confounders=["Bluetooth_LE_advertisements", "Microwave_ovens", "Zigbee_transmissions"],
            test_corpus_ref="corpus-wifi-ofdm-2026",
        )
        lora_profile = SignalIdentityProfile(
            profile_id="sip-lora-css-v1",
            protocol_name="LoRa_CSS",
            version="1.0.0",
            min_required_confirmation_level=4,
            supported_front_end_classes=[FrontEndClass.F1_NATIVE_RADIO.value, FrontEndClass.F2_WIDEBAND_SDR.value],
            frequency_bounds_hz=(433e6, 928e6),
            known_confounders=["FSK_transmitters", "Car_keyfobs", "Industrial_ISM_telemetry"],
            test_corpus_ref="corpus-lora-css-2026",
        )
        self.register_profile(wifi_profile)
        self.register_profile(lora_profile)

    def register_profile(self, profile: SignalIdentityProfile) -> None:
        self._profiles[profile.profile_id] = profile

    def get_profile(self, profile_id: str) -> Optional[SignalIdentityProfile]:
        return self._profiles.get(profile_id)

    def list_active_profiles(self) -> List[SignalIdentityProfile]:
        return [p for p in self._profiles.values() if p.is_active]
