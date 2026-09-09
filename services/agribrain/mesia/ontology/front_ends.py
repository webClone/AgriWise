"""MESIA Front-End Classes — R6 §3.1.

Six receiver front-end classes.  Two devices with the same tuning range
are NOT equivalent if one has a different antenna, clock, bandwidth or
decoder.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class FrontEndClass(str, Enum):
    """Receiver front-end class taxonomy — R6 §3.1."""

    F0_METADATA_API = "F0_METADATA_API"
    """Android Telephony, O-RAN, CAMARA, operator portals.
    No RF samples by default; network/device context only."""

    F1_NATIVE_RADIO = "F1_NATIVE_RADIO"
    """Wi-Fi CSI NIC/SoC, LoRa transceiver, GNSS receiver, RFID reader,
    UWB/mmWave module.  Protocol-aware native measurements."""

    F2_WIDEBAND_SDR = "F2_WIDEBAND_SDR"
    """Receive-only or permitted controlled SDR chains.
    IQ over tuning range and instantaneous bandwidth."""

    F3_MICROWAVE_MMWAVE = "F3_MICROWAVE_MMWAVE"
    """6–18 GHz receivers, 24/60/77 GHz radar, >45 GHz WLAN,
    external mixers.  Directional/beam/range evidence."""

    F4_ACTIVE_INSTRUMENT = "F4_ACTIVE_INSTRUMENT"
    """GPR, VNA, channel sounder, private 5G, controlled illuminator.
    Known transmitted waveform/action and richer causal measurement."""

    F5_REFERENCE_SENTINEL = "F5_REFERENCE_SENTINEL"
    """Cable loopback, reference antenna/load/tag/target, noise source,
    truth probes.  Independent instrument and experiment-quality evidence."""


@dataclass(frozen=True)
class FrontEndClassProfile:
    """Metadata for a front-end class."""

    front_end_class: FrontEndClass
    examples: Tuple[str, ...]
    observes: str
    mandatory_controls: str


# ── Per-class profiles ──────────────────────────────────────────────────

FRONT_END_PROFILES = {
    FrontEndClass.F0_METADATA_API: FrontEndClassProfile(
        front_end_class=FrontEndClass.F0_METADATA_API,
        examples=(
            "Android Telephony",
            "O-RAN",
            "CAMARA",
            "Operator portals",
        ),
        observes="No RF samples by default; network/device context only",
        mandatory_controls=(
            "Permissions, availability, semantics, latency, identity "
            "and NetworkEpoch"
        ),
    ),
    FrontEndClass.F1_NATIVE_RADIO: FrontEndClassProfile(
        front_end_class=FrontEndClass.F1_NATIVE_RADIO,
        examples=(
            "Wi-Fi CSI NIC/SoC",
            "LoRa transceiver",
            "GNSS receiver",
            "RFID reader",
            "UWB/mmWave module",
        ),
        observes=(
            "Protocol-aware native measurements, often limited "
            "bandwidth/access"
        ),
        mandatory_controls=(
            "Device/firmware/gain/clock/driver and payload conformance"
        ),
    ),
    FrontEndClass.F2_WIDEBAND_SDR: FrontEndClassProfile(
        front_end_class=FrontEndClass.F2_WIDEBAND_SDR,
        examples=(
            "Receive-only SDR chains",
            "Permitted controlled SDR chains",
        ),
        observes=(
            "IQ over tuning range and instantaneous bandwidth, "
            "not all bands simultaneously"
        ),
        mandatory_controls=(
            "RF calibration, alias/spur rejection, sample loss, "
            "clock, antenna path"
        ),
    ),
    FrontEndClass.F3_MICROWAVE_MMWAVE: FrontEndClassProfile(
        front_end_class=FrontEndClass.F3_MICROWAVE_MMWAVE,
        examples=(
            "6–18 GHz receivers",
            "24/60/77 GHz radar",
            ">45 GHz WLAN",
            "External mixers",
        ),
        observes=(
            "Directional/beam/range evidence with band-specific front ends"
        ),
        mandatory_controls=(
            "Beam/LO calibration, blockage, path loss, thermal drift"
        ),
    ),
    FrontEndClass.F4_ACTIVE_INSTRUMENT: FrontEndClassProfile(
        front_end_class=FrontEndClass.F4_ACTIVE_INSTRUMENT,
        examples=(
            "GPR",
            "VNA",
            "Channel sounder",
            "Private 5G",
            "Controlled illuminator",
        ),
        observes=(
            "Known transmitted waveform/action and richer causal measurement"
        ),
        mandatory_controls=(
            "Policy receipt, exposure/spectrum, calibration, geometry, "
            "action verification"
        ),
    ),
    FrontEndClass.F5_REFERENCE_SENTINEL: FrontEndClassProfile(
        front_end_class=FrontEndClass.F5_REFERENCE_SENTINEL,
        examples=(
            "Cable loopback",
            "Reference antenna/load/tag/target",
            "Noise source",
            "Truth probes",
        ),
        observes="Independent instrument and experiment-quality evidence",
        mandatory_controls=(
            "Traceability, placement, expiry and separation from "
            "target truth"
        ),
    ),
}
