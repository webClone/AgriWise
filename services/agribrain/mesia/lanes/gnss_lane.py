"""MESIA GNSS Positioning & GNSS-Reflectometry (GNSS-R) Lane — R6 §5.4 / P5.4.

Preserves direct/reflected SNR series, multipath carrier phase metrics,
satellite elevation/azimuth geometry, and RTK precision states.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.observation import RadioObservationPacket
from ..ontology.identity_states import IdentityState
from ..ontology.confirmation_levels import ConfirmationLevel
from ..ontology.evidence_roles import EvidenceRole
from ..radio_families.registry import RadioFamily


@dataclass(frozen=True)
class GnssReflectometryRecord:
    """Native GNSS-R reflectometry observation for soil moisture / canopy sensing."""

    record_id: str
    timestamp: datetime
    satellite_prn: int
    constellation: str  # "GPS", "GALILEO", "GLONASS", "BEIDOU"
    carrier_frequency_hz: float  # e.g. 1575.42e6 (L1) or 1227.60e6 (L2)
    elevation_deg: float
    azimuth_deg: float
    direct_snr_db_hz: Optional[float] = None
    reflected_snr_db_hz: Optional[float] = None
    multipath_carrier_metric: Optional[float] = None
    antenna_height_m: float = 1.85
    rtk_fix_status: str = "STANDALONE"  # "FIXED", "FLOAT", "STANDALONE"
    raw_bytes: Optional[bytes] = None

    def content_hash(self) -> str:
        if self.raw_bytes:
            return hashlib.sha256(self.raw_bytes).hexdigest()
        d = {
            "record_id": self.record_id,
            "prn": self.satellite_prn,
            "constellation": self.constellation,
            "carrier_frequency_hz": self.carrier_frequency_hz,
            "elevation_deg": self.elevation_deg,
            "azimuth_deg": self.azimuth_deg,
            "direct_snr": self.direct_snr_db_hz,
            "reflected_snr": self.reflected_snr_db_hz,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class GnssLaneAdapter:
    """Adapts GNSS-R records into validated RadioObservationPackets."""

    @staticmethod
    def to_observation_packet(
        record: GnssReflectometryRecord,
        receiver_id: str,
        geometry_epoch_id: str,
        instrument_epoch_id: str,
        network_epoch_id: str,
        calibration_state_id: str,
        software_model_epoch_id: str,
        task_receipt_ref: str = "",
    ) -> RadioObservationPacket:
        native_payload = {
            "prn": record.satellite_prn,
            "constellation": record.constellation,
            "elevation_deg": record.elevation_deg,
            "azimuth_deg": record.azimuth_deg,
            "direct_snr_db_hz": record.direct_snr_db_hz,
            "reflected_snr_db_hz": record.reflected_snr_db_hz,
            "multipath_metric": record.multipath_carrier_metric,
            "antenna_height_m": record.antenna_height_m,
            "rtk_status": record.rtk_fix_status,
        }

        # In dual-antenna reflectometry, direct minus reflected SNR indicates reflection coefficient.
        # In single-antenna GNSS-IR, snr_db is the direct composite SNR.
        if record.direct_snr_db_hz is not None and record.reflected_snr_db_hz is not None:
            snr_metric: Optional[float] = record.direct_snr_db_hz - record.reflected_snr_db_hz
        else:
            snr_metric = record.direct_snr_db_hz

        receipt_ref = task_receipt_ref or f"rcpt-proto-{record.record_id}"

        return RadioObservationPacket(
            packet_id=f"obs-gnss-{record.record_id}",
            source_profile=f"{RadioFamily.GNSS_REFLECTOMETRY.value}/v1",
            receiver_id=receiver_id,
            utc_time=record.timestamp,
            carrier_frequency_hz=record.carrier_frequency_hz,
            bandwidth_hz=2.046e6,
            identity_state=IdentityState.PROTOCOL_CONFIRMED.value,
            evidence_role=EvidenceRole.SENSING.value,
            native_data_uri=f"file://mesia/evidence/gnss/{record.record_id}.json",
            native_data_hash=record.content_hash(),
            native_data_type="gnss_reflectometry_json",
            geometry_epoch_id=geometry_epoch_id,
            instrument_epoch_id=instrument_epoch_id,
            network_epoch_id=network_epoch_id,
            coexistence_epoch_id="",
            calibration_state_id=calibration_state_id,
            software_model_epoch_id=software_model_epoch_id,
            snr_db=snr_metric,
            satellite_id=f"{record.constellation}_{record.satellite_prn}",
            task_receipt_ref=receipt_ref,
            authority_scope="evidence_proposal",
        )
