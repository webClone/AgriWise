"""MESIA Universal Lane Conformance & Data Contract Validator — R6 §5.9 / P5.9.

Validates that every RadioObservationPacket satisfies Principle P-04
(native evidence preserved without loss), complete epoch references, and valid hashes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.observation import RadioObservationPacket
from ..constitution.principles import validate_observation_packet, ConstitutionalViolation


@dataclass(frozen=True)
class ConformanceValidationReport:
    """Report detailing the conformance of a RadioObservationPacket to MESIA standards."""

    observation_id: str
    is_conformant: bool
    radio_family: str
    has_native_data: bool
    has_valid_hash: bool
    all_epochs_present: bool
    violations: List[str]


class LaneConformanceValidator:
    """Universal validator for MESIA acquisition lane packets."""

    @staticmethod
    def validate_packet(packet: RadioObservationPacket) -> ConformanceValidationReport:
        """Run strict validation against data contract rules."""
        violations: List[str] = []

        # 1. Constitutional invariant check
        try:
            validate_observation_packet(packet)
        except ConstitutionalViolation as e:
            violations.append(str(e))

        # 2. Native data completeness check (P-04)
        has_uri = bool(packet.native_data_uri and len(packet.native_data_uri) > 0)
        has_hash = bool(
            packet.native_data_hash
            and len(packet.native_data_hash) == 64
            and all(c in "0123456789abcdefABCDEF" for c in packet.native_data_hash)
        )
        if not has_uri or not has_hash:
            violations.append("Native data URI or 64-character SHA-256 hash is missing or invalid.")
        else:
            # If filesystem artifact exists, verify actual capture integrity
            from services.agribrain.mesia.ingestion.sigmf_ingest import verify_capture_integrity
            from pathlib import Path
            clean_path = packet.native_data_uri.replace("file://", "")
            p = Path(clean_path)
            if p.exists() or (p.parent / f"{p.name}.sigmf-data").exists() or p.with_suffix(".sigmf-data").exists():
                try:
                    if not verify_capture_integrity(p):
                        violations.append("Native SigMF capture manifest or data integrity verification failed.")
                except Exception as exc:
                    violations.append(f"Capture integrity check error: {exc}")

        # 3. Epoch completeness check
        epochs_present = bool(
            packet.geometry_epoch_id
            and packet.instrument_epoch_id
            and packet.network_epoch_id
            and packet.calibration_state_id
            and packet.software_model_epoch_id
        )
        if not epochs_present:
            violations.append("One or more required epoch IDs are empty.")

        is_conformant = len(violations) == 0

        return ConformanceValidationReport(
            observation_id=packet.packet_id,
            is_conformant=is_conformant,
            radio_family=packet.source_profile,
            has_native_data=has_uri,
            has_valid_hash=has_hash,
            all_epochs_present=epochs_present,
            violations=violations,
        )
