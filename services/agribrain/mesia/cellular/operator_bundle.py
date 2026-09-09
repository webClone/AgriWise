"""MESIA Operator Evidence Bundle Specification — R6 §13.6 / P11.6.

Defines the structured data package provided by mobile network operators or O-RAN
systems with time alignment, privacy anonymization, and explicit revocation handling.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OperatorEvidenceBundle:
    """Operator evidence package for agricultural radio intelligence."""

    bundle_id: str
    operator_name: str
    cell_id: int
    tracking_area_code: int
    plmn_id: str  # e.g., "603-01" (Mobilis), "603-02" (Djezzy), "603-03" (Ooredoo)
    recorded_at: datetime
    prb_utilization_pct: float
    mean_tx_power_dbm: float
    active_beam_index: int
    scheduler_mode: str  # PROPORTIONAL_FAIR | ROUND_ROBIN | MAXIMUM_THROUGHPUT
    anonymized_ue_count: int
    is_consent_valid: bool
    revocation_hook_ref: str

    def content_hash(self) -> str:
        d = {
            "bundle_id": self.bundle_id,
            "operator_name": self.operator_name,
            "cell_id": self.cell_id,
            "tracking_area_code": self.tracking_area_code,
            "plmn_id": self.plmn_id,
            "recorded_at": self.recorded_at.isoformat(),
            "prb_utilization_pct": self.prb_utilization_pct,
            "mean_tx_power_dbm": self.mean_tx_power_dbm,
            "active_beam_index": self.active_beam_index,
            "scheduler_mode": self.scheduler_mode,
            "anonymized_ue_count": self.anonymized_ue_count,
            "is_consent_valid": self.is_consent_valid,
            "revocation_hook_ref": self.revocation_hook_ref,
        }
        raw = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def verify_consent_signature(
        cls, 
        operator_public_key: str, 
        bundle_id: str, 
        hook_ref: str
    ) -> bool:
        """
        Verifies that the provided revocation_hook_ref contains a valid cryptographic
        signature linking the bundle_id to the operator's public key.
        This ensures ASMAE data ingest is legally consented and can be revoked.
        """
        import hmac
        # Using HMAC-SHA256 as a stand-in for RSA/ECDSA verification in this context.
        # The hook_ref should match HMAC(operator_public_key, bundle_id).
        expected = hmac.new(
            operator_public_key.encode('utf-8'), 
            bundle_id.encode('utf-8'), 
            hashlib.sha256
        ).hexdigest()
        
        # A real system would use ECDSA/RSA verify:
        # ecdsa.verify(public_key, signature=hook_ref, data=bundle_id)
        
        # For our test compatibility and math-enforcement, we check if they match.
        import hmac
        return hmac.compare_digest(expected, hook_ref)
