"""MESIA Radio Family Catalogue and Registry — R6 §6.1.

Maps each radio family to its front-end class, confirmation route, native evidence
format, scientific role, principal controls, and primary execution lane.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..ontology.evidence_roles import EvidenceRole
from ..ontology.front_ends import FrontEndClass


class RadioFamily(str, Enum):
    """The 20 radio family implementation lanes from R6 §6.1."""

    WIFI_CSI = "WIFI_CSI"
    WIFI_80211BF_SUB7 = "WIFI_80211BF_SUB7"
    WIFI_80211BF_MMWAVE = "WIFI_80211BF_MMWAVE"
    LTE_PUBLIC_SDR = "LTE_PUBLIC_SDR"
    NR_PUBLIC_UE = "NR_PUBLIC_UE"
    NR_PASSIVE_SDR = "NR_PASSIVE_SDR"
    PRIVATE_5G = "PRIVATE_5G"
    ORAN_OPERATOR = "ORAN_OPERATOR"
    LORA_CONTROLLED = "LORA_CONTROLLED"
    WIFI_HALOW = "WIFI_HALOW"
    GNSS_REFLECTOMETRY = "GNSS_REFLECTOMETRY"
    GNSS_BURIED_DIFF = "GNSS_BURIED_DIFF"
    GNSS_RTK_GEOMETRY = "GNSS_RTK_GEOMETRY"
    RFID_BACKSCATTER = "RFID_BACKSCATTER"
    AMBIENT_IOT = "AMBIENT_IOT"
    UWB_IMPULSE_FMCW = "UWB_IMPULSE_FMCW"
    GPR = "GPR"
    MMWAVE_RADAR = "MMWAVE_RADAR"
    BLE_ZIGBEE_THREAD = "BLE_ZIGBEE_THREAD"
    NBIOT_NTN = "NBIOT_NTN"


@dataclass(frozen=True)
class RadioFamilyProfile:
    """Metadata profile for a single radio lane — R6 §6.1."""

    family: RadioFamily
    display_name: str
    front_end_class: FrontEndClass
    default_evidence_role: EvidenceRole
    confirmation_route: str
    native_evidence_payload: str
    scientific_role_description: str
    principal_controls: str
    execution_lane_ref: str
    maturity_status: str = "UNIMPLEMENTED_RESEARCH"


RADIO_FAMILY_REGISTRY: Dict[RadioFamily, RadioFamilyProfile] = {
    RadioFamily.WIFI_CSI: RadioFamilyProfile(
        family=RadioFamily.WIFI_CSI,
        display_name="Wi-Fi CSI 2.4/5/6 GHz",
        front_end_class=FrontEndClass.F1_NATIVE_RADIO,
        default_evidence_role=EvidenceRole.SENSING,
        confirmation_route="Spectral occupancy → OFDM/preamble/frame evidence → controlled device/session",
        native_evidence_payload="Complex subcarrier channel, RSSI/noise/AGC/gain, channel, packet health",
        scientific_role_description="Controlled research anchor for dielectric/canopy/motion response",
        principal_controls="CFO/SFO, packet timing, AGC, phase jumps, multipath, people/machines, antenna motion",
        execution_lane_ref="P5.1; P8 E0–E4",
    ),
    RadioFamily.WIFI_80211BF_SUB7: RadioFamilyProfile(
        family=RadioFamily.WIFI_80211BF_SUB7,
        display_name="IEEE 802.11bf sub-7 GHz",
        front_end_class=FrontEndClass.F1_NATIVE_RADIO,
        default_evidence_role=EvidenceRole.SENSING,
        confirmation_route="802.11 identification + negotiated sensing-session receipt",
        native_evidence_payload="Session, feedback, PHY/MAC, geometry and calibration products",
        scientific_role_description="Preferred future WLAN procedure lane",
        principal_controls="Availability, privacy, vendor API, legacy traffic; standard does not validate agriculture",
        execution_lane_ref="P5.1; standards watch",
    ),
    RadioFamily.WIFI_80211BF_MMWAVE: RadioFamilyProfile(
        family=RadioFamily.WIFI_80211BF_MMWAVE,
        display_name="802.11bf >45 GHz / mmWave WLAN",
        front_end_class=FrontEndClass.F3_MICROWAVE_MMWAVE,
        default_evidence_role=EvidenceRole.SENSING,
        confirmation_route="Directional waveform/beam/session confirmation",
        native_evidence_payload="Delay/angle/Doppler/beam products",
        scientific_role_description="Surface/canopy/structure; not default root-zone sensing",
        principal_controls="Blockage, rain/canopy, beam change, path loss",
        execution_lane_ref="P5.7; P8 E1–E4",
    ),
    RadioFamily.LTE_PUBLIC_SDR: RadioFamilyProfile(
        family=RadioFamily.LTE_PUBLIC_SDR,
        display_name="LTE public downlink + SDR",
        front_end_class=FrontEndClass.F2_WIDEBAND_SDR,
        default_evidence_role=EvidenceRole.CONTEXT,
        confirmation_route="Cell search/PSS/SSS/CRS or equivalent direct evidence",
        native_evidence_payload="IQ, cell ID, timing, reference-channel response, network epoch",
        scientific_role_description="Passive cellular-band research profile",
        principal_controls="Oscillator/sync, base-station changes, interference, geometry, high-moisture saturation",
        execution_lane_ref="P11.3",
    ),
    RadioFamily.NR_PUBLIC_UE: RadioFamilyProfile(
        family=RadioFamily.NR_PUBLIC_UE,
        display_name="NR public UE / Android Telephony",
        front_end_class=FrontEndClass.F0_METADATA_API,
        default_evidence_role=EvidenceRole.CONTEXT,
        confirmation_route="OS/modem/API reports with availability and permission state",
        native_evidence_payload="SS/CSI RSRP/RSRQ/SINR, CQI/TA/channel/status when available",
        scientific_role_description="Network context, anomaly and nuisance attribution initially",
        principal_controls="Quantisation, RRC, handover, beam/scheduler/power, OEM/modem/permission",
        execution_lane_ref="P11.2",
    ),
    RadioFamily.NR_PASSIVE_SDR: RadioFamilyProfile(
        family=RadioFamily.NR_PASSIVE_SDR,
        display_name="NR passive SDR",
        front_end_class=FrontEndClass.F2_WIDEBAND_SDR,
        default_evidence_role=EvidenceRole.CONTEXT,
        confirmation_route="NR cell/numerology/beam evidence from correlators/decoders",
        native_evidence_payload="IQ, SSB/beam timing, frequency/TDD observations, calibration",
        scientific_role_description="Conditional FR1/FR2 research lane",
        principal_controls="Beam sweep, scheduler/TDD, sync, data volume, legal/ethical constraints",
        execution_lane_ref="P11.4",
    ),
    RadioFamily.PRIVATE_5G: RadioFamilyProfile(
        family=RadioFamily.PRIVATE_5G,
        display_name="Private 5G / OAI / srsRAN",
        front_end_class=FrontEndClass.F4_ACTIVE_INSTRUMENT,
        default_evidence_role=EvidenceRole.SENSING,
        confirmation_route="Known configuration + decoded control/reference + task receipt",
        native_evidence_payload="SRS/CSI-RS/PRS/DMRS, beam/power/TDD/scheduler/IQ as exposed",
        scientific_role_description="Causal bridge to operator cellular sensing",
        principal_controls="Spectrum permission, calibration, stack/vendor complexity",
        execution_lane_ref="P11.5",
    ),
    RadioFamily.ORAN_OPERATOR: RadioFamilyProfile(
        family=RadioFamily.ORAN_OPERATOR,
        display_name="O-RAN operator tier",
        front_end_class=FrontEndClass.F0_METADATA_API,
        default_evidence_role=EvidenceRole.CONTEXT,
        confirmation_route="OperatorEvidenceBundle signed against network epoch",
        native_evidence_payload="KPM, cell/beam/power/scheduler/configuration; no generic raw-CSI assumption",
        scientific_role_description="Network attribution and coordinated probes",
        principal_controls="Partner access, vendor split, policy, privacy/security, revocation",
        execution_lane_ref="P11.6–P11.8",
    ),
    RadioFamily.LORA_CONTROLLED: RadioFamilyProfile(
        family=RadioFamily.LORA_CONTROLLED,
        display_name="LoRa controlled",
        front_end_class=FrontEndClass.F1_NATIVE_RADIO,
        default_evidence_role=EvidenceRole.SENSING,
        confirmation_route="CSS chirp/preamble/decode/CRC or known node receipt",
        native_evidence_payload="RSSI/SNR, SF/BW/channel, threshold, chirp/relative phase where supported",
        scientific_role_description="Low-power distributed behaviour probe",
        principal_controls="Narrow bandwidth, multipath, buried detuning, duty cycle, soil-specific calibration",
        execution_lane_ref="P5.3; P8",
    ),
    RadioFamily.WIFI_HALOW: RadioFamilyProfile(
        family=RadioFamily.WIFI_HALOW,
        display_name="Wi-Fi HaLow 802.11ah",
        front_end_class=FrontEndClass.F1_NATIVE_RADIO,
        default_evidence_role=EvidenceRole.TRANSPORT,
        confirmation_route="802.11ah waveform/frame confirmation",
        native_evidence_payload="RSSI/frame/possible CSI-like products as hardware allows",
        scientific_role_description="Backhaul first; sensing candidate only after E0/E1 evidence",
        principal_controls="Regional channels, sparse tooling, unvalidated soil sensing",
        execution_lane_ref="P5.1; research watch",
    ),
    RadioFamily.GNSS_REFLECTOMETRY: RadioFamilyProfile(
        family=RadioFamily.GNSS_REFLECTOMETRY,
        display_name="GNSS reflectometry",
        front_end_class=FrontEndClass.F1_NATIVE_RADIO,
        default_evidence_role=EvidenceRole.SENSING,
        confirmation_route="Constellation/signal correlation and satellite geometry",
        native_evidence_payload="SNR, carrier/code multipath, delay/Doppler, geometry, ephemeris",
        scientific_role_description="Passive near-surface temporal/footprint reference",
        principal_controls="Vegetation, roughness, antenna, satellite geometry, snow/multipath",
        execution_lane_ref="P5.4; P8",
    ),
    RadioFamily.GNSS_BURIED_DIFF: RadioFamilyProfile(
        family=RadioFamily.GNSS_BURIED_DIFF,
        display_name="GNSS buried differential",
        front_end_class=FrontEndClass.F1_NATIVE_RADIO,
        default_evidence_role=EvidenceRole.SENSING,
        confirmation_route="Known GNSS signal plus controlled path identity",
        native_evidence_payload="Differential amplitude/phase/correlation and clock state",
        scientific_role_description="Local subsurface research/reference",
        principal_controls="Clock, switch imbalance, deployment depth, soil variability",
        execution_lane_ref="P5.4; P8",
    ),
    RadioFamily.GNSS_RTK_GEOMETRY: RadioFamilyProfile(
        family=RadioFamily.GNSS_RTK_GEOMETRY,
        display_name="GNSS/RTK geometry authority",
        front_end_class=FrontEndClass.F1_NATIVE_RADIO,
        default_evidence_role=EvidenceRole.GEOMETRY_AUTHORITY,
        confirmation_route="Solution status and correction provenance",
        native_evidence_payload="Pose, covariance, time, trajectory",
        scientific_role_description="Geometry/timing authority only",
        principal_controls="Canopy, multipath, corrections outage",
        execution_lane_ref="P6",
    ),
    RadioFamily.RFID_BACKSCATTER: RadioFamilyProfile(
        family=RadioFamily.RFID_BACKSCATTER,
        display_name="RFID/chipless/backscatter",
        front_end_class=FrontEndClass.F1_NATIVE_RADIO,
        default_evidence_role=EvidenceRole.SENTINEL,
        confirmation_route="Reader inventory/CRC/tag identity or calibrated resonance evidence",
        native_evidence_payload="Resonance, amplitude, threshold, phase/ToF, trajectory/orientation",
        scientific_role_description="Sparse local sentinel/teacher capability",
        principal_controls="Reader motion, orientation, detuning, ageing, burial, soil-specific calibration",
        execution_lane_ref="P5.5; P8",
    ),
    RadioFamily.AMBIENT_IOT: RadioFamilyProfile(
        family=RadioFamily.AMBIENT_IOT,
        display_name="Ambient IoT / 802.11bp",
        front_end_class=FrontEndClass.F1_NATIVE_RADIO,
        default_evidence_role=EvidenceRole.SENTINEL,
        confirmation_route="Native device/session evidence when ecosystem exists",
        native_evidence_payload="Energy/link/identity/status and sensing payload if explicitly provided",
        scientific_role_description="Strategic sentinel route; not assumed environmental CSI",
        principal_controls="Immature devices, energy budget, coexistence, lifecycle",
        execution_lane_ref="P5.5; standards watch",
    ),
    RadioFamily.UWB_IMPULSE_FMCW: RadioFamilyProfile(
        family=RadioFamily.UWB_IMPULSE_FMCW,
        display_name="UWB impulse/FMCW",
        front_end_class=FrontEndClass.F4_ACTIVE_INSTRUMENT,
        default_evidence_role=EvidenceRole.TEACHER,
        confirmation_route="Known pulse/FMCW configuration and range calibration",
        native_evidence_payload="ToF, impulse/range profile, reflection, dispersion, tag delay",
        scientific_role_description="High-resolution controlled benchmark/local sensing",
        principal_controls="Wet/clayey/saline attenuation, clutter, surface echo, depth ambiguity",
        execution_lane_ref="P5.6; P8",
    ),
    RadioFamily.GPR: RadioFamilyProfile(
        family=RadioFamily.GPR,
        display_name="Ground Penetrating Radar (GPR)",
        front_end_class=FrontEndClass.F4_ACTIVE_INSTRUMENT,
        default_evidence_role=EvidenceRole.TEACHER,
        confirmation_route="Instrument waveform/survey receipt",
        native_evidence_payload="Traces, time-zero, amplitude/travel time, common/multi-offset geometry",
        scientific_role_description="Teacher and time-lapse depth profile",
        principal_controls="Conductivity/clay/salt attenuation, inversion ambiguity, heavy field logistics",
        execution_lane_ref="P5.6; P8",
    ),
    RadioFamily.MMWAVE_RADAR: RadioFamilyProfile(
        family=RadioFamily.MMWAVE_RADAR,
        display_name="mmWave radar 24/60/77 GHz",
        front_end_class=FrontEndClass.F3_MICROWAVE_MMWAVE,
        default_evidence_role=EvidenceRole.NEGATIVE_CONTROL,
        confirmation_route="Known radar waveform/beam configuration",
        native_evidence_payload="Range-Doppler-angle, radar cube, polarisation/beam",
        scientific_role_description="Canopy water/structure, surface, motion; negative control for deep claims",
        principal_controls="Rain/foliage, blockage, calibration, limited deep penetration",
        execution_lane_ref="P5.7; P8",
    ),
    RadioFamily.BLE_ZIGBEE_THREAD: RadioFamilyProfile(
        family=RadioFamily.BLE_ZIGBEE_THREAD,
        display_name="BLE / Zigbee / Thread / Matter",
        front_end_class=FrontEndClass.F1_NATIVE_RADIO,
        default_evidence_role=EvidenceRole.EVENT_LEDGER,
        confirmation_route="Protocol decode/known device command receipt",
        native_evidence_payload="Coexistence, topology, valve/pump command/status",
        scientific_role_description="Event ledger, nuisance and intervention truth",
        principal_controls="Mesh changes, batteries, firmware, 2.4 GHz coexistence",
        execution_lane_ref="P5.8",
    ),
    RadioFamily.NBIOT_NTN: RadioFamilyProfile(
        family=RadioFamily.NBIOT_NTN,
        display_name="NB-IoT NTN / Satellite IoT",
        front_end_class=FrontEndClass.F0_METADATA_API,
        default_evidence_role=EvidenceRole.TRANSPORT,
        confirmation_route="Network/session receipt",
        native_evidence_payload="Availability, pass, latency, loss, buffering and coarse context",
        scientific_role_description="Backhaul only",
        principal_controls="Delay, intermittent visibility, buffering artefacts",
        execution_lane_ref="P11.1",
    ),
}


def get_radio_family_profile(family: RadioFamily) -> RadioFamilyProfile:
    """Retrieve the immutable metadata profile for a radio family."""
    if family not in RADIO_FAMILY_REGISTRY:
        raise KeyError(f"Unknown radio family: {family}")
    return RADIO_FAMILY_REGISTRY[family]


def list_supported_families() -> List[RadioFamily]:
    """List all supported radio families."""
    return list(RADIO_FAMILY_REGISTRY.keys())
