"""MESIA Five-Tier Cellular Framework — R6 §13 / P11.

Separates transport, Android telemetry, passive SDR, private RAN, and operator O-RAN
into 5 distinct evidence tiers to prevent conflation of public metadata with physical CSI.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class CellularTier(str, Enum):
    P0_TRANSPORT = "P0_TRANSPORT"          # Backhaul / connectivity only
    P1_ANDROID = "P1_ANDROID"              # Android telephony API metrics (SS/CSI RSRP/RSRQ/SINR)
    P2_PASSIVE_SDR = "P2_PASSIVE_SDR"      # Receive-only SDR (CRS/SSB IQ traces)
    P3_PRIVATE_RAN = "P3_PRIVATE_RAN"      # Controlled private cell actions (SRS/CSI-RS)
    P4_OPERATOR_ORAN = "P4_OPERATOR_ORAN"  # Operator partner evidence / O-RAN E2 KPM


@dataclass(frozen=True)
class TierValidationRecord:
    """Validation report verifying that a cellular evidence bundle satisfies tier boundaries."""

    tier: CellularTier
    is_csi_claimed: bool
    is_valid: bool
    reason: str


class CellularTierValidator:
    """Enforces tier boundaries (e.g. public Android phones never claim raw CSI)."""

    @staticmethod
    def validate_tier_conformance(
        tier: CellularTier,
        claims_raw_csi: bool,
    ) -> TierValidationRecord:
        """Verify that tier does not exceed scientific authority."""
        if tier in {CellularTier.P0_TRANSPORT, CellularTier.P1_ANDROID} and claims_raw_csi:
            return TierValidationRecord(
                tier=tier,
                is_csi_claimed=claims_raw_csi,
                is_valid=False,
                reason=f"Violation: Cellular tier {tier.value} cannot claim physical channel CSI.",
            )

        return TierValidationRecord(
            tier=tier,
            is_csi_claimed=claims_raw_csi,
            is_valid=True,
            reason="Tier boundaries respected.",
        )
