"""MESIA RFID, Chipless Resonance & Ambient IoT Lane — R6 §5.5 / P5.5.

Preserves reader illumination receipts, tag IDs, backscatter power/phase,
resonance frequency dips (chipless sensors), and active-interrogation policies.
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
class RfidObservationRecord:
    """Native RFID / Backscatter sensor record."""

    record_id: str
    timestamp: datetime
    carrier_frequency_hz: float
    reader_tx_power_dbm: float
    tag_epc: str
    backscatter_rssi_dbm: float
    backscatter_phase_rad: float
    resonance_frequency_dip_hz: Optional[float]
    round_trip_time_ns: float
    is_chipless_resonant_tag: bool = False

    def content_hash(self) -> str:
        d = {
            "record_id": self.record_id,
            "carrier_frequency_hz": self.carrier_frequency_hz,
            "reader_tx_power_dbm": self.reader_tx_power_dbm,
            "tag_epc": self.tag_epc,
            "backscatter_rssi_dbm": self.backscatter_rssi_dbm,
            "backscatter_phase_rad": self.backscatter_phase_rad,
            "resonance_dip": self.resonance_frequency_dip_hz,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RfidLaneAdapter:
    """Adapts native RFID measurements into validated RadioObservationPackets."""

    @staticmethod
    def to_observation_packet(
        record: RfidObservationRecord,
        receiver_id: str,
        geometry_epoch_id: str,
        instrument_epoch_id: str,
        network_epoch_id: str,
        calibration_state_id: str,
        software_model_epoch_id: str,
        task_receipt_ref: str = "",
    ) -> RadioObservationPacket:
        family = RadioFamily.AMBIENT_IOT.value if record.is_chipless_resonant_tag else RadioFamily.RFID_BACKSCATTER.value

        native_payload = {
            "reader_tx_power_dbm": record.reader_tx_power_dbm,
            "tag_epc": record.tag_epc,
            "backscatter_rssi_dbm": record.backscatter_rssi_dbm,
            "backscatter_phase_rad": record.backscatter_phase_rad,
            "resonance_dip_hz": record.resonance_frequency_dip_hz,
            "rtt_ns": record.round_trip_time_ns,
            "is_chipless": record.is_chipless_resonant_tag,
        }

        # Path loss from reader TX to backscatter RX
        two_way_loss_db = record.reader_tx_power_dbm - record.backscatter_rssi_dbm
        receipt_ref = task_receipt_ref or f"rcpt-proto-{record.record_id}"

        return RadioObservationPacket(
            packet_id=f"obs-rfid-{record.record_id}",
            source_profile=f"{family}/v1",
            receiver_id=receiver_id,
            utc_time=record.timestamp,
            carrier_frequency_hz=record.carrier_frequency_hz,
            bandwidth_hz=500e3,
            identity_state=IdentityState.PROTOCOL_CONFIRMED.value,
            evidence_role=EvidenceRole.SENSING.value,
            native_data_uri=f"file://mesia/evidence/rfid/{record.record_id}.json",
            native_data_hash=record.content_hash(),
            native_data_type="rfid_backscatter_json",
            geometry_epoch_id=geometry_epoch_id,
            instrument_epoch_id=instrument_epoch_id,
            network_epoch_id=network_epoch_id,
            coexistence_epoch_id="",
            calibration_state_id=calibration_state_id,
            software_model_epoch_id=software_model_epoch_id,
            snr_db=record.backscatter_rssi_dbm + 100.0,
            task_receipt_ref=receipt_ref,
            authority_scope="evidence_proposal",
        )
