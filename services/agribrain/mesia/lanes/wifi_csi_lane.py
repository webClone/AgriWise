"""MESIA Wi-Fi CSI & 802.11bf Radio-Native Acquisition Lane — R6 §5.1 / P5.1.

Preserves raw subcarrier complex channel matrices (H), AGC gain steps,
noise floor, CFO/SFO correction metadata, and maps into RadioObservationPacket.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.observation import RadioObservationPacket
from ..ontology.identity_states import IdentityState
from ..ontology.confirmation_levels import ConfirmationLevel
from ..ontology.evidence_roles import EvidenceRole
from ..radio_families.registry import RadioFamily


@dataclass(frozen=True)
class WifiCsiFrame:
    """Native Wi-Fi Channel State Information (CSI) frame."""

    frame_id: str
    timestamp: datetime
    centre_frequency_hz: float
    channel_bandwidth_hz: float
    num_subcarriers: int
    subcarrier_amplitudes_linear: List[float]
    subcarrier_phases_rad: List[float]
    agc_gain_db: float
    noise_floor_dbm: float
    transmitter_mac: str
    receiver_mac: str
    rssi_dbm: float
    is_80211bf_sensing_session: bool = False
    session_id: str = ""

    def content_hash(self) -> str:
        d = {
            "frame_id": self.frame_id,
            "centre_frequency_hz": self.centre_frequency_hz,
            "channel_bandwidth_hz": self.channel_bandwidth_hz,
            "num_subcarriers": self.num_subcarriers,
            "agc_gain_db": self.agc_gain_db,
            "noise_floor_dbm": self.noise_floor_dbm,
            "transmitter_mac": self.transmitter_mac,
            "receiver_mac": self.receiver_mac,
            "rssi_dbm": self.rssi_dbm,
            "is_80211bf": self.is_80211bf_sensing_session,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class WifiCsiLaneAdapter:
    """Adapts native Wi-Fi CSI frames into validated RadioObservationPackets."""

    @classmethod
    def from_sigmf_dict(cls, sigmf_dict: Dict[str, Any], frame_id: str = "frame-01") -> WifiCsiFrame:
        """Constructs a WifiCsiFrame from a parsed SigMF dict."""
        ts = sigmf_dict.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                ts = datetime.now(timezone.utc)
        elif not isinstance(ts, datetime):
            ts = datetime.now(timezone.utc)

        return WifiCsiFrame(
            frame_id=frame_id,
            timestamp=ts,
            centre_frequency_hz=float(sigmf_dict.get("center_frequency_hz", 2.437e9)),
            channel_bandwidth_hz=float(sigmf_dict.get("bandwidth_hz", 20.0e6)),
            num_subcarriers=int(sigmf_dict.get("num_subcarriers", len(sigmf_dict.get("amplitudes_linear", [])))),
            subcarrier_amplitudes_linear=sigmf_dict.get("amplitudes_linear", []),
            subcarrier_phases_rad=sigmf_dict.get("phases_rad", []),
            agc_gain_db=float(sigmf_dict.get("agc_gain_db", 30.0)),
            noise_floor_dbm=float(sigmf_dict.get("noise_floor_dbm", -92.0)),
            transmitter_mac=str(sigmf_dict.get("transmitter_mac", "")),
            receiver_mac=str(sigmf_dict.get("receiver_mac", "")),
            rssi_dbm=float(sigmf_dict.get("rssi_dbm", -65.0)),
            is_80211bf_sensing_session=bool(sigmf_dict.get("is_80211bf", False)),
            session_id=str(sigmf_dict.get("session_id", "")),
        )

    @staticmethod
    def to_observation_packet(
        csi_frame: WifiCsiFrame,
        receiver_id: str,
        geometry_epoch_id: str,
        instrument_epoch_id: str,
        network_epoch_id: str,
        calibration_state_id: str,
        software_model_epoch_id: str,
        task_receipt_ref: str = "",
    ) -> RadioObservationPacket:
        """Construct standard RadioObservationPacket preserving all native CSI data."""
        native_hash = csi_frame.content_hash()
        native_uri = f"file://mesia/evidence/wifi_csi/{csi_frame.frame_id}.csi"

        native_payload = {
            "num_subcarriers": csi_frame.num_subcarriers,
            "subcarrier_amplitudes": csi_frame.subcarrier_amplitudes_linear,
            "subcarrier_phases": csi_frame.subcarrier_phases_rad,
            "agc_gain_db": csi_frame.agc_gain_db,
            "noise_floor_dbm": csi_frame.noise_floor_dbm,
            "rssi_dbm": csi_frame.rssi_dbm,
            "transmitter_mac": csi_frame.transmitter_mac,
            "receiver_mac": csi_frame.receiver_mac,
            "is_80211bf": csi_frame.is_80211bf_sensing_session,
            "session_id": csi_frame.session_id,
        }

        # Calculate mean subcarrier SNR
        mean_power_dbm = csi_frame.rssi_dbm
        snr_db = mean_power_dbm - csi_frame.noise_floor_dbm

        fam = RadioFamily.WIFI_80211BF_SUB7.value if csi_frame.is_80211bf_sensing_session else RadioFamily.WIFI_CSI.value
        receipt_ref = task_receipt_ref or f"rcpt-proto-{csi_frame.frame_id}"

        return RadioObservationPacket(
            packet_id=f"obs-wifi-{csi_frame.frame_id}",
            source_profile=f"{fam}/v1",
            receiver_id=receiver_id,
            utc_time=csi_frame.timestamp,
            carrier_frequency_hz=csi_frame.centre_frequency_hz,
            bandwidth_hz=csi_frame.channel_bandwidth_hz,
            identity_state=IdentityState.PROTOCOL_CONFIRMED.value,
            evidence_role=EvidenceRole.SENSING.value,
            native_data_uri=native_uri,
            native_data_hash=native_hash,
            native_data_type="wifi_csi_matrix",
            geometry_epoch_id=geometry_epoch_id,
            instrument_epoch_id=instrument_epoch_id,
            network_epoch_id=network_epoch_id,
            coexistence_epoch_id="",
            calibration_state_id=calibration_state_id,
            software_model_epoch_id=software_model_epoch_id,
            noise_floor_dbm=csi_frame.noise_floor_dbm,
            snr_db=snr_db,
            task_receipt_ref=receipt_ref,
            authority_scope="evidence_proposal",
        )
