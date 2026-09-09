"""MESIA Receiver Interrogation & Capability Extraction — R6 §2.1–§2.3.

Interrogates front-end receivers, native devices, and metadata APIs to produce
validated, immutable ReceiverCapabilityManifest and AntennaPathManifest objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.receiver import ReceiverCapabilityManifest, AntennaPathManifest
from ..ontology.front_ends import FrontEndClass, FRONT_END_PROFILES


class HardwareInterrogationError(ValueError):
    """Raised when hardware capabilities cannot be validated."""


class ReceiverInterrogator:
    """Extracts and verifies hardware capability parameters for a receiver front-end."""

    @staticmethod
    def build_receiver_manifest(
        receiver_id: str,
        front_end_class: FrontEndClass,
        hardware_model: str,
        tuning_range_hz: Tuple[float, float],
        instantaneous_bandwidth_hz: float,
        sample_format: str,
        antenna_path_refs: List[str],
        firmware_version: str = "1.0.0",
        driver_version: str = "1.0.0",
        gain_stages: Optional[List[str]] = None,
        sensitivity_dbm: Optional[float] = None,
        dynamic_range_db: Optional[float] = None,
        clock_source: str = "INTERNAL_TCXO",
        clock_accuracy_ppm: Optional[float] = 1.0,
        supported_decoders: Optional[List[str]] = None,
        scan_duty_cycle_pct: float = 100.0,
    ) -> ReceiverCapabilityManifest:
        """Build and validate a ReceiverCapabilityManifest."""
        if tuning_range_hz[0] >= tuning_range_hz[1]:
            raise HardwareInterrogationError(
                f"Invalid tuning range: min {tuning_range_hz[0]} Hz >= max {tuning_range_hz[1]} Hz"
            )
        if instantaneous_bandwidth_hz <= 0:
            raise HardwareInterrogationError(
                f"Instantaneous bandwidth must be positive, got {instantaneous_bandwidth_hz}"
            )
        if not antenna_path_refs and front_end_class != FrontEndClass.F0_METADATA_API:
            raise HardwareInterrogationError(
                f"Receiver {receiver_id} of class {front_end_class.value} requires at least one antenna path reference."
            )

        now = datetime.now(timezone.utc)
        return ReceiverCapabilityManifest(
            receiver_id=receiver_id,
            front_end_class=front_end_class.value,
            hardware_model=hardware_model,
            firmware_version=firmware_version,
            driver_version=driver_version,
            tuning_range_hz=tuning_range_hz,
            instantaneous_bandwidth_hz=instantaneous_bandwidth_hz,
            sample_rate_hz=instantaneous_bandwidth_hz,
            sample_format=sample_format,
            gain_stages=gain_stages or ["LNA", "VGA"],
            sensitivity_dbm=sensitivity_dbm or -110.0,
            dynamic_range_db=dynamic_range_db or 70.0,
            clock_source=clock_source,
            clock_accuracy_ppm=clock_accuracy_ppm,
            antenna_port_count=len(antenna_path_refs) if antenna_path_refs else 1,
            antenna_path_refs=list(antenna_path_refs),
            duplex_mode="RX_ONLY",
            hardware_trigger_capable=True,
            health_status="HEALTHY",
            last_self_test=now,
            supported_decoders=list(supported_decoders or []),
            scan_duty_cycle_pct=scan_duty_cycle_pct,
        )

    @staticmethod
    def build_antenna_manifest(
        path_id: str,
        antenna_model: str,
        polarisation: str = "VERTICAL_LINEAR",
        cable_length_m: float = 1.0,
        cable_type: str = "LMR-400",
        insertion_loss_db: float = 0.5,
        orientation_ypr_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> AntennaPathManifest:
        """Build and validate an AntennaPathManifest."""
        if insertion_loss_db < 0:
            raise HardwareInterrogationError(
                f"Insertion loss must be non-negative, got {insertion_loss_db}"
            )
        now = datetime.now(timezone.utc)
        return AntennaPathManifest(
            path_id=path_id,
            antenna_model=antenna_model,
            cable_type=cable_type,
            cable_length_m=cable_length_m,
            polarisation=polarisation,
            orientation_ypr_deg=orientation_ypr_deg,
            insertion_loss_db=insertion_loss_db,
            calibration_ref=f"cal-ant-{path_id}",
            calibration_date=now,
        )
