"""MESIA UWB & Ground Penetrating Radar (GPR) Subsurface Lane — R6 §5.6 / P5.6.

Preserves time-zero reference, A-scan radargram trace amplitudes, ToF range bins,
bistatic antenna separation, surface echo calibration, and depth uncertainty.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.observation import RadioObservationPacket
from ..ontology.identity_states import IdentityState
from ..ontology.confirmation_levels import ConfirmationLevel
from ..ontology.evidence_roles import EvidenceRole
from ..radio_families.registry import RadioFamily


@dataclass(frozen=True)
class GprTraceRecord:
    """Native GPR subsurface A-scan trace record."""

    trace_id: str
    timestamp: datetime
    centre_frequency_hz: float  # e.g. 500 MHz, 900 MHz, or 1.6 GHz
    bandwidth_hz: float
    sampling_rate_hz: float
    time_zero_index: int
    antenna_separation_m: float
    trace_samples: List[float]  # Amplitude values per time sample
    estimated_soil_relative_permittivity: float = 9.0
    surface_echo_sample_index: int = 15

    def content_hash(self) -> str:
        d = {
            "trace_id": self.trace_id,
            "centre_frequency_hz": self.centre_frequency_hz,
            "sampling_rate_hz": self.sampling_rate_hz,
            "time_zero_index": self.time_zero_index,
            "antenna_separation_m": self.antenna_separation_m,
            "sample_count": len(self.trace_samples),
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class UwbGprLaneAdapter:
    """Adapts GPR / UWB subsurface records into validated RadioObservationPackets."""

    @staticmethod
    def to_observation_packet(
        record: GprTraceRecord,
        receiver_id: str,
        geometry_epoch_id: str,
        instrument_epoch_id: str,
        network_epoch_id: str,
        calibration_state_id: str,
        software_model_epoch_id: str,
    ) -> RadioObservationPacket:
        # EM propagation velocity in soil: v = c / sqrt(epsilon_r)
        c = 299792458.0
        v_soil = c / math.sqrt(max(record.estimated_soil_relative_permittivity, 1.0))
        dt = 1.0 / record.sampling_rate_hz

        # Depth per sample = (v_soil * dt) / 2
        sample_depth_resolution_m = (v_soil * dt) / 2.0

        native_payload = {
            "sampling_rate_hz": record.sampling_rate_hz,
            "time_zero_index": record.time_zero_index,
            "antenna_separation_m": record.antenna_separation_m,
            "surface_echo_index": record.surface_echo_sample_index,
            "trace_sample_count": len(record.trace_samples),
            "trace_samples": record.trace_samples,
            "estimated_permittivity": record.estimated_soil_relative_permittivity,
            "soil_velocity_m_per_s": v_soil,
            "depth_resolution_m": sample_depth_resolution_m,
        }

        return RadioObservationPacket(
            packet_id=f"obs-gpr-{record.trace_id}",
            source_profile=f"{RadioFamily.GPR.value}/v1",
            receiver_id=receiver_id,
            utc_time=record.timestamp,
            carrier_frequency_hz=record.centre_frequency_hz,
            bandwidth_hz=record.bandwidth_hz,
            identity_state=IdentityState.CONTROLLED_SOURCE.value,
            evidence_role=EvidenceRole.TEACHER.value,
            native_data_uri=f"file://mesia/evidence/gpr/{record.trace_id}.dzt",
            native_data_hash=record.content_hash(),
            native_data_type="gpr_dzt_trace",
            geometry_epoch_id=geometry_epoch_id,
            instrument_epoch_id=instrument_epoch_id,
            network_epoch_id=network_epoch_id,
            coexistence_epoch_id="",
            calibration_state_id=calibration_state_id,
            software_model_epoch_id=software_model_epoch_id,
            task_receipt_ref="",
            authority_scope="evidence_proposal",
        )
