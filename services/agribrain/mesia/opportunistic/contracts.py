"""MESIA Opportunistic & Ambient Sensing Contracts — R6 §6.5 / P6.5.

Typed contracts for signals of opportunity (SoOP), passive bistatic sensing,
and pure remote spaceborne reflectometry.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SensingModality(str, Enum):
    """Operational deployment modality."""

    PURE_REMOTE_ORBITAL = "PURE_REMOTE_ORBITAL"
    """Zero in-situ hardware. Uses orbital reflectometry (CYGNSS/Spire), SAR, and CML."""

    PERIMETER_PASSIVE_SENTINEL = "PERIMETER_PASSIVE_SENTINEL"
    """1–2 passive listening receivers placed on boundary fence or existing structures."""

    DEDICATED_IN_SITU = "DEDICATED_IN_SITU"
    """Dedicated active/passive mesh deployed across the field."""


class AmbientRadioFamily(str, Enum):
    """Signals of opportunity (SoOP) radio families."""

    GNSS_REFLECTOMETRY = "GNSS_REFLECTOMETRY"
    """Overhead GPS/Galileo/GLONASS/BeiDou L-band (1.1–1.6 GHz)."""

    PUBLIC_CELLULAR_DOWNLINK = "PUBLIC_CELLULAR_DOWNLINK"
    """4G LTE (CRS) and 5G NR (SSB/CSI-RS) base station downlinks (700 MHz–3.5 GHz)."""

    TERRESTRIAL_BROADCAST_UHF = "TERRESTRIAL_BROADCAST_UHF"
    """DVB-T2 / ISDB-T television (470–790 MHz) and FM radio (88–108 MHz)."""

    LEO_SATELLITE_DOWNLINK = "LEO_SATELLITE_DOWNLINK"
    """Starlink / OneWeb / Kuiper Ku/Ka-band downlinks (10.7–12.7 GHz)."""

    AMBIENT_WIFI_LORA = "AMBIENT_WIFI_LORA"
    """Uncoordinated ambient Wi-Fi beacons (2.4/5.8 GHz) and LoRa telemetries."""

    SPACEBORNE_GNSSR = "SPACEBORNE_GNSSR"
    """NASA CYGNSS / Spire / ESA HydroGNSS spaceborne bistatic reflectometry."""

    COMMERCIAL_MICROWAVE_LINK = "COMMERCIAL_MICROWAVE_LINK"
    """Telecom tower backhaul microwave attenuation (7–38 GHz)."""


@dataclass(frozen=True)
class AmbientOpportunityDescriptor:
    """Catalog entry for an available ambient emitter of opportunity."""

    source_id: str
    family: AmbientRadioFamily
    center_frequency_hz: float
    bandwidth_hz: float
    polarization: str  # "RHCP", "VERTICAL", "HORIZONTAL", "DUAL"
    transmitter_location_wgs84: Optional[Tuple[float, float, float]] = None  # (lat, lon, alt)
    transmitter_eirp_dbm: Optional[float] = None
    pilot_type: str = "UNKNOWN"  # e.g., "GPS_L1CA", "LTE_CRS", "DVB_PILOT", "BEACON"
    is_continuous: bool = True
    elevation_range_deg: Tuple[float, float] = (5.0, 90.0)

    def content_hash(self) -> str:
        d = {
            "source_id": self.source_id,
            "family": self.family.value,
            "center_freq": self.center_frequency_hz,
            "bandwidth": self.bandwidth_hz,
            "tx_loc": self.transmitter_location_wgs84,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GnssInterferometryObservation:
    """Observation derived from GNSS-Reflectometry SNR oscillations."""

    observation_id: str
    timestamp: datetime
    prn: int
    constellation: str  # "GPS", "GALILEO", "BEIDOU", "GLONASS"
    carrier_freq_hz: float
    elevation_start_deg: float
    elevation_end_deg: float
    azimuth_mean_deg: float
    effective_reflector_height_m: float
    dielectric_phase_shift_rad: float
    estimated_vwc: float  # Inferred Volumetric Water Content (0.0 to 1.0)
    observation_variance: float
    snr_detrended_peaks: List[float] = field(default_factory=list)
    raw_nmea_hash: str = ""

    def content_hash(self) -> str:
        d = {
            "id": self.observation_id,
            "prn": self.prn,
            "constellation": self.constellation,
            "vwc": round(self.estimated_vwc, 4),
            "var": round(self.observation_variance, 6),
            "raw_hash": self.raw_nmea_hash,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BistaticForwardScatterObservation:
    """Forward-scatter radar observation through crop canopy from cell/TV towers."""

    observation_id: str
    timestamp: datetime
    source_tower_id: str
    receiver_node_id: str
    carrier_freq_hz: float
    path_length_m: float
    measured_path_loss_db: float
    free_space_loss_db: float
    excess_canopy_loss_db: float  # Attenuation attributable to canopy biomass & water
    estimated_canopy_water_index: float  # [0.0, 1.0]
    observation_variance: float
    native_iq_hash: str = ""

    def content_hash(self) -> str:
        d = {
            "id": self.observation_id,
            "source_tower": self.source_tower_id,
            "excess_loss_db": round(self.excess_canopy_loss_db, 3),
            "canopy_water": round(self.estimated_canopy_water_index, 4),
            "raw_hash": self.native_iq_hash,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PureRemoteObservation:
    """Observation ingested purely from spaceborne or external telecom data."""

    observation_id: str
    mission: str  # "CYGNSS", "SPIRE_GNSSR", "SENTINEL1_INSAR", "CML_TELECOM"
    timestamp: datetime
    specular_point_wgs84: Tuple[float, float]  # (lat, lon)
    reflectivity_db: float
    estimated_root_zone_vwc: float
    confidence: float
    coverage_fraction: float
    external_granule_id: str = ""

    def content_hash(self) -> str:
        d = {
            "id": self.observation_id,
            "mission": self.mission,
            "specular": self.specular_point_wgs84,
            "vwc": round(self.estimated_root_zone_vwc, 4),
            "granule": self.external_granule_id,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
