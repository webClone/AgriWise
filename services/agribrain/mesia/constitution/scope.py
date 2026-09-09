"""MESIA Scope, Target State, and Excluded Claims — R6 §1.1 & §1.3."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, List, Tuple


class SupportedFamily(str, Enum):
    """Supported radio families across front ends — R6 §6.1."""

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
    WILDFIRE_VANGUARD_THERMAL = "WILDFIRE_VANGUARD_THERMAL"


class ExcludedClaim(str, Enum):
    """Explicitly excluded claims — R6 §1.3."""

    NO_CODE_DELIVERABLE = "NO_CODE_DELIVERABLE"
    """MESIA R6 plan does not supply operational agronomic capability code."""

    NO_UNIVERSAL_SENSOR_PROMISE = "NO_UNIVERSAL_SENSOR_PROMISE"
    """Not every radio will become a useful soil or crop sensor; some remain transport/context."""

    NO_ANDROID_RAW_CSI = "NO_ANDROID_RAW_CSI"
    """Android does not expose raw NR CSI; TelephonyDisplayInfo is display-oriented context."""

    NO_80211BF_AGRONOMIC_VALIDATION = "NO_80211BF_AGRONOMIC_VALIDATION"
    """802.11bf standards alignment does not validate agricultural inference."""

    NO_DEEP_SOIL_MMWAVE = "NO_DEEP_SOIL_MMWAVE"
    """No deep-soil claim from mmWave without coupled resonant tag architecture."""

    NO_UNQUALIFIED_IRRIGATION_ACTION = "NO_UNQUALIFIED_IRRIGATION_ACTION"
    """No operational irrigation recommendation based solely on MESIA until qualification passes."""


EXCLUDED_CLAIMS: FrozenSet[str] = frozenset({
    claim.value for claim in ExcludedClaim
})


@dataclass(frozen=True)
class TargetState:
    """Full target state specification — R6 §1.1."""

    supported_families: Tuple[str, ...] = tuple(f.value for f in SupportedFamily)
    excluded_claims: FrozenSet[str] = EXCLUDED_CLAIMS
    governed_boundary: str = "MESIA proposes likelihoods; ASMAE owns posterior."
    planning_horizon_months: int = 72
    scientific_gates_required: int = 8
    target_operating_model_version: str = "R6_TOM_v1"
