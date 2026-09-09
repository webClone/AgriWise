from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class SourceConfirmationReceipt:
    """Canonical base receipt for all physical, remote, and computational sources."""

    receipt_id: str
    source_type: str
    timestamp_utc: datetime
    content_hash: str
    issuer_identity: str = "MESIA_CORE"
    hardware_id: Optional[str] = None
    signature: Optional[str] = None
    calibration_ref: Optional[str] = None
    quarantine_status: Optional[str] = None

    def __post_init__(self) -> None:
        if self.timestamp_utc.tzinfo is None:
            raise ValueError("timestamp_utc must be a timezone-aware UTC datetime.")
        if not self.content_hash or len(self.content_hash.strip()) < 32:
            raise ValueError("content_hash must be a valid cryptographic hash.")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp_utc"] = self.timestamp_utc.isoformat()
        return d


@dataclass(frozen=True)
class ProtocolConfirmationReceipt(SourceConfirmationReceipt):
    """Unified direct protocol frame decode receipt (Wi-Fi, LTE, LoRa, RFID)."""

    protocol_name: str = ""
    protocol_version: str = ""
    confirmation_method: str = "DECODER"  # CORRELATOR, DECODER, CRC, REFERENCE_SIGNAL, NATIVE_DEVICE, CONTROLLED_SOURCE
    confirmation_level: int = 4            # 4=PROTOCOL_DECODE, 5=TRUSTED_NATIVE
    frame_type: str = ""
    station_or_cell_id: str = ""
    cell_id: str = ""
    network_identity: str = ""
    tag_identity: str = ""
    crc_passed: bool = True
    crc_valid: bool = True
    preamble_detected: bool = True
    frame_fields_valid: bool = True
    repeated_confirmation_count: int = 1
    channel_freq_hz: float = 0.0
    snr_db: float = 0.0
    device_attestation_ref: str = ""
    signed_configuration_ref: str = ""
    task_schedule_ref: str = ""
    native_artefact_ref: str = ""
    hardware_version: str = ""
    profile_version: str = ""


@dataclass(frozen=True)
class SatelliteObservationReceipt(SourceConfirmationReceipt):
    """Direct GNSS satellite observation cycle receipt."""

    constellation: str = ""  # GPS, GALILEO, BEIDOU, GLONASS
    prn: int = 0
    signal_id: str = ""      # L1C/A, E1B, B1I, etc.
    carrier_freq_hz: float = 0.0
    elevation_deg: float = 0.0
    azimuth_deg: float = 0.0
    cycle_valid: bool = True
    direct_snr_db_hz: Optional[float] = None
    rtk_fix_status: str = "STANDALONE"


@dataclass(frozen=True)
class RemoteProductReceipt(SourceConfirmationReceipt):
    """Authenticated satellite/airborne remote sensing product receipt."""

    mission: str = ""        # SENTINEL-1, NASA-CYGNSS, COPERNICUS
    product_level: str = ""  # L1-GRD, L3-SOIL-MOISTURE
    granule_id: str = ""
    product_uri: str = ""
    provider_checksum: str = ""
    spatial_footprint_wkt: str = ""
    spatial_coverage_pct: float = 100.0
    temporal_delta_seconds: float = 0.0
    product_quality_flags: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RadarFrameReceipt(SourceConfirmationReceipt):
    """Radar chirp/frame instrument configuration receipt (mmWave, UWB, GPR)."""

    radar_band: str = ""
    chirp_slope_mhz_us: float = 0.0
    samples_per_chirp: int = 0
    pulse_repetition_freq_hz: float = 0.0


@dataclass(frozen=True)
class RegistryQueryReceipt(SourceConfirmationReceipt):
    """Geodetic infrastructure database query receipt (OpenStreetMap)."""

    registry_name: str = ""
    query_coordinates: str = ""
    nodes_returned_count: int = 0


@dataclass(frozen=True)
class ModelContextReceipt(SourceConfirmationReceipt):
    """Numerical weather prediction / atmospheric model context receipt."""

    model_name: str = ""
    model_version: str = ""
    model_run_id: str = ""
    request_hash: str = ""
    response_hash: str = ""
    model_provider: str = "OPEN_METEO_ECMWF"
    model_run_utc: Optional[datetime] = None
    interpolation_method: str = "BILINEAR"
    variables_ingested: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp_utc"] = self.timestamp_utc.isoformat()
        if self.model_run_utc:
            d["model_run_utc"] = self.model_run_utc.isoformat()
        return d

