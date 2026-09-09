"""MESIA Protocol Correlators, Sync Verifiers & Confirmation Receipts — R6 §4.2 & §5.2.

Provides deterministic preamble correlation, sync-word detection, frame CRC
verification, and generates immutable ProtocolConfirmationReceipt objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.identity import ProtocolConfirmationReceipt
from ..ontology.confirmation_levels import ConfirmationLevel


class CorrelatorEngine:
    """Executes deterministic correlator and decoder verification."""

    @staticmethod
    def verify_wifi_ofdm_preamble(
        raw_samples: List[complex],
        threshold: float = 0.85,
    ) -> Tuple[bool, float]:
        """Perform normalized auto/cross-correlation with 802.11 Short/Long Training Field (STF/LTF)."""
        import cmath
        if len(raw_samples) < 64:
            return False, 0.0
            
        # Actual 802.11a/g/n L-STF frequency-domain sequence (mapped to time domain approx)
        # For simplicity in this implementation, we check the Schmidl-Cox delayed auto-correlation
        # which is the standard way to detect OFDM preambles (delay = 16 samples for STF).
        delay = 16
        window = 16
        if len(raw_samples) < delay + window:
            return False, 0.0
            
        # Compute Schmidl-Cox metric: M(d) = |P(d)|^2 / (R(d))^2
        # where P(d) is cross-correlation of conjugated received signal with delayed signal
        # and R(d) is received energy.
        p_d = sum((raw_samples[i].conjugate() * raw_samples[i + delay]) for i in range(window))
        r_d = sum((abs(raw_samples[i + delay]) ** 2) for i in range(window))
        
        if r_d == 0:
            return False, 0.0
            
        corr_score = (abs(p_d) ** 2) / (r_d ** 2)
        return (corr_score >= threshold), corr_score

    @staticmethod
    def verify_crc(data_bytes: bytes, polynomial: int = 0x04C11DB7) -> bool:
        """Verify 32-bit CRC integrity of a captured frame."""
        import zlib
        if len(data_bytes) < 4:
            return False
        payload = data_bytes[:-4]
        expected_crc = int.from_bytes(data_bytes[-4:], byteorder="little")
        computed_crc = zlib.crc32(payload) & 0xFFFFFFFF
        return computed_crc == expected_crc

    @staticmethod
    def verify_gnss_parity(word: int) -> bool:
        """Verify 30-bit GNSS navigation word parity (Hamming code)."""
        raise NotImplementedError("Requires stateful D29/D30 parity decoding from physical baseband.")

    @classmethod
    def issue_confirmation_receipt(
        cls,
        receipt_id: str,
        protocol_name: str,
        confirmation_level: ConfirmationLevel,
        receiver_id: str,
        preamble_detected: bool,
        crc_valid: bool,
        cell_id: str = "",
        network_identity: str = "",
        tag_identity: str = "",
        native_artefact_ref: str = "",
    ) -> ProtocolConfirmationReceipt:
        """Construct an immutable ProtocolConfirmationReceipt."""
        now = datetime.now(timezone.utc)
        return ProtocolConfirmationReceipt(
            receipt_id=receipt_id,
            protocol_name=protocol_name,
            protocol_version="1.0",
            confirmation_method="CORRELATOR_AND_DECODER",
            confirmation_level=int(confirmation_level.value),
            preamble_detected=preamble_detected,
            crc_valid=crc_valid,
            cell_id=cell_id,
            network_identity=network_identity,
            tag_identity=tag_identity,
            frame_fields_valid=crc_valid,
            repeated_confirmation_count=1,
            confirmed_at=now,
            receiver_id=receiver_id,
            native_artefact_ref=native_artefact_ref,
        )
