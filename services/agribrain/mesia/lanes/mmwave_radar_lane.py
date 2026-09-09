"""MESIA mmWave Radar & FR2 Sensing Acquisition Lane — R6 §5.7 / P5.7.

Preserves range-Doppler-angle cubes, chirp FMCW numerology, point clouds,
and canopy wind-motion micro-Doppler signatures.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.observation import RadioObservationPacket
from ..ontology.identity_states import IdentityState
from ..ontology.confirmation_levels import ConfirmationLevel
from ..ontology.evidence_roles import EvidenceRole
from ..radio_families.registry import RadioFamily


@dataclass(frozen=True)
class MmWaveRadarFrame:
    """Native FMCW mmWave radar frame record."""

    frame_id: str
    timestamp: datetime
    start_frequency_hz: float  # e.g. 60e9 or 77e9
    sweep_bandwidth_hz: float  # e.g. 4e9
    num_chirps_per_frame: int
    num_adc_samples_per_chirp: int
    detected_targets: List[Dict[str, float]]  # List of {range_m, velocity_m_s, azimuth_deg, snr_db}
    is_rain_cluttered: bool = False
    is_radome_blocked: bool = False
    canopy_micro_doppler_spread_hz: float = 0.0

    def content_hash(self) -> str:
        d = {
            "frame_id": self.frame_id,
            "start_freq": self.start_frequency_hz,
            "sweep_bw": self.sweep_bandwidth_hz,
            "target_count": len(self.detected_targets),
            "micro_doppler": self.canopy_micro_doppler_spread_hz,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class MmWaveRadarLaneAdapter:
    """Adapts native mmWave radar frames into validated RadioObservationPackets."""

    @staticmethod
    def to_observation_packet(
        record: MmWaveRadarFrame,
        receiver_id: str,
        geometry_epoch_id: str,
        instrument_epoch_id: str,
        network_epoch_id: str,
        calibration_state_id: str,
        software_model_epoch_id: str,
    ) -> RadioObservationPacket:
        # Range resolution = c / (2 * B)
        c = 299792458.0
        range_res_m = c / (2.0 * record.sweep_bandwidth_hz)

        native_payload = {
            "start_frequency_hz": record.start_frequency_hz,
            "sweep_bandwidth_hz": record.sweep_bandwidth_hz,
            "chirps_per_frame": record.num_chirps_per_frame,
            "adc_samples_per_chirp": record.num_adc_samples_per_chirp,
            "range_resolution_m": range_res_m,
            "targets": record.detected_targets,
            "is_rain_cluttered": record.is_rain_cluttered,
            "is_radome_blocked": record.is_radome_blocked,
            "micro_doppler_spread_hz": record.canopy_micro_doppler_spread_hz,
        }

        mean_target_snr = (
            sum(t.get("snr_db", 0.0) for t in record.detected_targets) / len(record.detected_targets)
            if record.detected_targets else 0.0
        )

        return RadioObservationPacket(
            packet_id=f"obs-radar-{record.frame_id}",
            source_profile=f"{RadioFamily.MMWAVE_RADAR.value}/v1",
            receiver_id=receiver_id,
            utc_time=record.timestamp,
            carrier_frequency_hz=record.start_frequency_hz + record.sweep_bandwidth_hz / 2.0,
            bandwidth_hz=record.sweep_bandwidth_hz,
            identity_state=IdentityState.CONTROLLED_SOURCE.value,
            evidence_role=EvidenceRole.SENSING.value,
            native_data_uri=f"file://mesia/evidence/radar/{record.frame_id}.bin",
            native_data_hash=record.content_hash(),
            native_data_type="mmwave_radar_cube",
            geometry_epoch_id=geometry_epoch_id,
            instrument_epoch_id=instrument_epoch_id,
            network_epoch_id=network_epoch_id,
            coexistence_epoch_id="",
            calibration_state_id=calibration_state_id,
            software_model_epoch_id=software_model_epoch_id,
            snr_db=mean_target_snr,
            task_receipt_ref="",
            authority_scope="evidence_proposal",
        )
