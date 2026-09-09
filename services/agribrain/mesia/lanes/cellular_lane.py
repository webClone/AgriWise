"""MESIA Cellular LTE & 5G NR Receive-Only Acquisition Lane — R6 §5.2 / P5.2.

Preserves cell identification, RSRP/RSRQ, Timing Advance, CRS/SSB beam indices,
subcarrier spacing, and maps into RadioObservationPacket.
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
class CellularObservationRecord:
    """Native cellular survey record (LTE CRS or 5G NR SSB beam survey)."""

    record_id: str
    timestamp: datetime
    rat_type: str  # "LTE" or "5G_NR"
    carrier_frequency_hz: float
    channel_bandwidth_hz: float
    cell_id: int
    plmn: str
    tracking_area_code: int
    rsrp_dbm: float
    rsrq_db: float
    sinr_db: float
    timing_advance_chips: Optional[int]
    beam_index: Optional[int]
    subcarrier_spacing_khz: float = 15.0

    def content_hash(self) -> str:
        d = {
            "record_id": self.record_id,
            "rat_type": self.rat_type,
            "carrier_frequency_hz": self.carrier_frequency_hz,
            "cell_id": self.cell_id,
            "plmn": self.plmn,
            "rsrp_dbm": self.rsrp_dbm,
            "sinr_db": self.sinr_db,
            "timing_advance": self.timing_advance_chips,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CellularLaneAdapter:
    """Adapts native Cellular measurements into validated RadioObservationPackets."""

    @staticmethod
    def to_observation_packet(
        record: CellularObservationRecord,
        receiver_id: str,
        geometry_epoch_id: str,
        instrument_epoch_id: str,
        network_epoch_id: str,
        calibration_state_id: str,
        software_model_epoch_id: str,
        task_receipt_ref: str = "",
    ) -> RadioObservationPacket:
        family = RadioFamily.NR_PASSIVE_SDR.value if record.rat_type == "5G_NR" else RadioFamily.LTE_PUBLIC_SDR.value

        native_payload = {
            "rat_type": record.rat_type,
            "cell_id": record.cell_id,
            "plmn": record.plmn,
            "tac": record.tracking_area_code,
            "rsrp_dbm": record.rsrp_dbm,
            "rsrq_db": record.rsrq_db,
            "sinr_db": record.sinr_db,
            "timing_advance_chips": record.timing_advance_chips,
            "beam_index": record.beam_index,
            "scs_khz": record.subcarrier_spacing_khz,
        }

        receipt_ref = task_receipt_ref or f"rcpt-proto-{record.record_id}"

        return RadioObservationPacket(
            packet_id=f"obs-cell-{record.record_id}",
            source_profile=f"{family}/v1",
            receiver_id=receiver_id,
            utc_time=record.timestamp,
            carrier_frequency_hz=record.carrier_frequency_hz,
            bandwidth_hz=record.channel_bandwidth_hz,
            identity_state=IdentityState.PROTOCOL_CONFIRMED.value,
            evidence_role=EvidenceRole.SENSING.value,
            native_data_uri=f"file://mesia/evidence/cellular/{record.record_id}.json",
            native_data_hash=record.content_hash(),
            native_data_type="cellular_survey_json",
            geometry_epoch_id=geometry_epoch_id,
            instrument_epoch_id=instrument_epoch_id,
            network_epoch_id=network_epoch_id,
            coexistence_epoch_id="",
            calibration_state_id=calibration_state_id,
            software_model_epoch_id=software_model_epoch_id,
            snr_db=record.sinr_db,
            cell_id=str(record.cell_id),
            task_receipt_ref=receipt_ref,
            authority_scope="evidence_proposal",
        )
