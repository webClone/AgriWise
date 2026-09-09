"""MESIA Coexistence, Action & Transport Acquisition Lane — R6 §5.8 / P5.8.

Captures BLE, Zigbee, Thread, Matter, and machinery emissions as coexistence or
intervention ledger events; captures NTN / satellite cellular as transport context.
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
class CoexistenceEventRecord:
    """Native event record for coexistence interference or machinery actuation."""

    event_id: str
    timestamp: datetime
    protocol_type: str  # "BLUETOOTH_LE", "ZIGBEE_802_15_4", "MATTER_THREAD", "IRRIGATION_PUMP_VFD"
    carrier_frequency_hz: float
    bandwidth_hz: float
    observed_rssi_dbm: float
    duration_seconds: float
    is_intervention_event: bool = False
    intervention_command: str = ""

    def content_hash(self) -> str:
        d = {
            "event_id": self.event_id,
            "protocol_type": self.protocol_type,
            "carrier_frequency_hz": self.carrier_frequency_hz,
            "rssi_dbm": self.observed_rssi_dbm,
            "is_intervention": self.is_intervention_event,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CoexistenceTransportLaneAdapter:
    """Adapts coexistence and intervention events into validated RadioObservationPackets."""

    @staticmethod
    def to_observation_packet(
        record: CoexistenceEventRecord,
        receiver_id: str,
        geometry_epoch_id: str,
        instrument_epoch_id: str,
        network_epoch_id: str,
        calibration_state_id: str,
        software_model_epoch_id: str,
    ) -> RadioObservationPacket:
        evidence_role = EvidenceRole.EVENT_LEDGER.value

        native_payload = {
            "protocol_type": record.protocol_type,
            "observed_rssi_dbm": record.observed_rssi_dbm,
            "duration_s": record.duration_seconds,
            "is_intervention": record.is_intervention_event,
            "intervention_command": record.intervention_command,
        }

        return RadioObservationPacket(
            packet_id=f"obs-coex-{record.event_id}",
            source_profile=f"{RadioFamily.BLE_ZIGBEE_THREAD.value}/v1",
            receiver_id=receiver_id,
            utc_time=record.timestamp,
            carrier_frequency_hz=record.carrier_frequency_hz,
            bandwidth_hz=record.bandwidth_hz,
            identity_state=IdentityState.PROTOCOL_CONFIRMED.value,
            evidence_role=evidence_role,
            native_data_uri=f"file://mesia/evidence/coexistence/{record.event_id}.json",
            native_data_hash=record.content_hash(),
            native_data_type="coexistence_event_json",
            geometry_epoch_id=geometry_epoch_id,
            instrument_epoch_id=instrument_epoch_id,
            network_epoch_id=network_epoch_id,
            coexistence_epoch_id="coex-event-ledger",
            calibration_state_id=calibration_state_id,
            software_model_epoch_id=software_model_epoch_id,
            executed_action=record.intervention_command,
            task_receipt_ref="",
            authority_scope="evidence_proposal",
        )
