"""MESIA LoRa & Sub-GHz Radio-Native Acquisition Lane — R6 §5.3 / P5.3.

Preserves spreading factors (SF7-12), bandwidth, coding rate, RSSI, SNR,
duty-cycle receipts, and buried-soil attenuation links.
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
class LoRaObservationRecord:
    """Native LoRa frame reception record."""

    record_id: str
    timestamp: datetime
    carrier_frequency_hz: float
    bandwidth_hz: float
    spreading_factor: int  # 7 to 12
    coding_rate: str       # "4/5", "4/7", etc.
    rssi_dbm: float
    snr_db: float
    packet_crc_valid: bool
    dev_addr: str
    gateway_id: str
    is_buried_node: bool = False
    burial_depth_cm: Optional[float] = None
    duty_cycle_used_pct: float = 0.1

    def content_hash(self) -> str:
        d = {
            "record_id": self.record_id,
            "carrier_frequency_hz": self.carrier_frequency_hz,
            "bandwidth_hz": self.bandwidth_hz,
            "spreading_factor": self.spreading_factor,
            "rssi_dbm": self.rssi_dbm,
            "snr_db": self.snr_db,
            "dev_addr": self.dev_addr,
            "crc_valid": self.packet_crc_valid,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LoRaSubGhzLaneAdapter:
    """Adapts native LoRa measurements into validated RadioObservationPackets."""

    @staticmethod
    def to_observation_packet(
        record: LoRaObservationRecord,
        receiver_id: str,
        geometry_epoch_id: str,
        instrument_epoch_id: str,
        network_epoch_id: str,
        calibration_state_id: str,
        software_model_epoch_id: str,
        task_receipt_ref: str = "",
    ) -> RadioObservationPacket:
        native_payload = {
            "spreading_factor": record.spreading_factor,
            "coding_rate": record.coding_rate,
            "rssi_dbm": record.rssi_dbm,
            "snr_db": record.snr_db,
            "crc_valid": record.packet_crc_valid,
            "dev_addr": record.dev_addr,
            "gateway_id": record.gateway_id,
            "is_buried_node": record.is_buried_node,
            "burial_depth_cm": record.burial_depth_cm,
            "duty_cycle_used_pct": record.duty_cycle_used_pct,
        }

        state = IdentityState.PROTOCOL_CONFIRMED.value if record.packet_crc_valid else IdentityState.RAT_CANDIDATE.value
        receipt_ref = task_receipt_ref or (f"rcpt-proto-{record.record_id}" if state == IdentityState.PROTOCOL_CONFIRMED.value else "")

        return RadioObservationPacket(
            packet_id=f"obs-lora-{record.record_id}",
            source_profile=f"{RadioFamily.LORA_CONTROLLED.value}/v1",
            receiver_id=receiver_id,
            utc_time=record.timestamp,
            carrier_frequency_hz=record.carrier_frequency_hz,
            bandwidth_hz=record.bandwidth_hz,
            identity_state=state,
            evidence_role=EvidenceRole.SENSING.value,
            native_data_uri=f"file://mesia/evidence/lora/{record.record_id}.json",
            native_data_hash=record.content_hash(),
            native_data_type="lora_frame_json",
            geometry_epoch_id=geometry_epoch_id,
            instrument_epoch_id=instrument_epoch_id,
            network_epoch_id=network_epoch_id,
            coexistence_epoch_id="",
            calibration_state_id=calibration_state_id,
            software_model_epoch_id=software_model_epoch_id,
            snr_db=record.snr_db,
            depth_m=(record.burial_depth_cm / 100.0) if record.burial_depth_cm else None,
            task_receipt_ref=receipt_ref,
            authority_scope="evidence_proposal",
        )
