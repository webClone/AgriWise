"""L0-B2B06: State Grant Separation Gate & Unified Admission Verifier.

Invariants:
1. An incoming observation packet or client request NEVER self-asserts
   `eligible_for_state_grant=True`. Any unverified packet claiming state grant
   eligibility is immediately rejected with SpatialTenantDenied.
2. Only positive verification by V3KmsGrantVerifier (or legacy PositiveObservationAdmissionVerifier)
   can mint an authorized V3StateGrantToken and set `eligible_for_state_grant=True`.
3. Spatial support must be FULL_CONTAINED; fractional boundary overlap cannot receive
   a full state grant.
4. UnifiedAdmissionVerifier transparently routes receipts to either V3KmsGrantVerifier
   or legacy v1/v2 HMAC verifier, while enforcing mandatory v3 when configured.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from services.agribrain.layer0.observation_packet import ObservationPacket
from services.agribrain.layer0.spatial_tenant_contract import (
    VerifiedPlotScope,
    FractionalPixelSupport,
    SpatialTenantDenied,
)
from services.agribrain.layer0.v3_kms_signed_issuer import (
    V3KmsGrantVerifier,
    V3SignedReceipt,
    V3StateGrantToken,
    GRANT_PURPOSE,
    WEATHER_GRANT_PURPOSE,
)
from services.agribrain.layer0.positive_observation_admission import (
    PositiveObservationAdmissionVerifier,
)
from services.agribrain.layer0.production_admission import Layer0AdmissionRequiredError


def v3_kms_required() -> bool:
    """Check whether v3 KMS asymmetric issuance is mandatory."""
    return os.getenv("AKALORIS_LAYER0_REQUIRE_V3_KMS", "").strip().lower() in ("true", "1", "yes")


class StateGrantSeparationViolation(SpatialTenantDenied):
    """Raised when an unverified packet attempts unauthorized state grant self-promotion."""


def certify_state_grant_eligibility(
    packet: ObservationPacket,
    receipt: Any,
    scope: VerifiedPlotScope,
    support: FractionalPixelSupport,
    verifier: V3KmsGrantVerifier,
    *,
    now: datetime | None = None,
    purpose: str = GRANT_PURPOSE,
    variables: Sequence[str] | None = None,
) -> tuple[bool, str, Optional[V3StateGrantToken]]:
    """Strict state grant admission gate.
    
    Rejects self-promotion, verifies spatial support is FULL_CONTAINED,
    validates the v3 receipt through the KMS verifier, and mints a V3StateGrantToken.
    """
    # 1. Anti-self-promotion check on the raw packet
    raw_prov = getattr(packet, "spatial_provenance", None)
    if isinstance(raw_prov, dict):
        if raw_prov.get("eligible_for_state_grant") is True or raw_prov.get("source_qualified") is True:
            raise StateGrantSeparationViolation("unauthorized_state_grant_self_promotion")

    # 2. Scope and support checks
    if not isinstance(scope, VerifiedPlotScope) or not isinstance(support, FractionalPixelSupport):
        return False, "invalid_scope_or_support_type", None
    if scope.scope_hash != support.scope_hash:
        return False, "scope_support_hash_mismatch", None
    if support.classification != "FULL_CONTAINED" or not support.geometry_support_verified:
        return False, "fractional_or_partial_spatial_support_not_eligible", None

    current_time = now or datetime.now(timezone.utc)

    # 3. Cryptographic KMS verification
    valid, reason, token = verifier.verify_grant(
        receipt,
        packet,
        plot_id=scope.plot_id,
        geometry_hash=scope.geometry_hash,
        geometry_version=scope.geometry_version,
        run_timestamp=current_time,
        purpose=purpose,
        variables=variables,
        tenant_id=scope.tenant_id,
    )

    if not valid or token is None:
        return False, reason, None

    # 4. Attach verified state grant token to the packet in-memory
    setattr(packet, "_v3_state_grant_token", token)
    setattr(packet, "_state_grant_authorized", True)

    return True, "state_grant_eligibility_certified", token


class UnifiedAdmissionVerifier:
    """Unified admission verifier supporting both v3 KMS and legacy v1/v2 HMAC.
    
    When AKALORIS_LAYER0_REQUIRE_V3_KMS=true, legacy receipts are rejected.
    """

    def __init__(
        self,
        v3_verifier: Optional[V3KmsGrantVerifier] = None,
        legacy_verifier: Optional[PositiveObservationAdmissionVerifier] = None,
        *,
        enforce_v3_only: bool = False,
    ) -> None:
        self._v3 = v3_verifier
        self._legacy = legacy_verifier
        self._enforce_v3_only = enforce_v3_only or v3_kms_required()

    @property
    def enforces_v3_only(self) -> bool:
        """Live server policy can become mandatory after verifier creation."""
        return self._enforce_v3_only or v3_kms_required()

    @property
    def v3_verifier(self) -> Optional[V3KmsGrantVerifier]:
        return self._v3

    @property
    def legacy_verifier(self) -> Optional[PositiveObservationAdmissionVerifier]:
        return self._legacy

    @property
    def revocation_enforced(self) -> bool:
        if self._v3 is not None and self._v3.revocation_enforced:
            return True
        if self._legacy is not None and self._legacy.revocation_enforced:
            return True
        return False

    @property
    def zone_authority_configured(self) -> bool:
        if self._v3 is not None and self._v3.zone_authority_configured:
            return True
        if self._legacy is not None and getattr(self._legacy, "zone_authority_configured", False):
            return True
        return False

    @property
    def revocation_snapshot_digest(self) -> str | None:
        if self._v3 is not None and self._v3.revocation_snapshot_digest is not None:
            return self._v3.revocation_snapshot_digest
        if self._legacy is not None:
            return getattr(self._legacy, "revocation_snapshot_digest", None)
        return None

    def verify(
        self,
        receipt: Any,
        packet: Any,
        *,
        plot_id: str,
        geometry_hash: str,
        geometry_version: int | None,
        run_timestamp: datetime,
        purpose: str = GRANT_PURPOSE,
        variables: Sequence[str] | None = None,
        tenant_id: str | None = None,
    ) -> tuple[bool, str]:
        """Dispatch receipt to v3 KMS verifier or legacy HMAC verifier."""
        if not isinstance(receipt, (Mapping, V3SignedReceipt)):
            return False, "missing_or_malformed_grant"

        # Detect v3 receipt
        is_v3 = False
        if isinstance(receipt, V3SignedReceipt):
            is_v3 = True
        elif "signature" in receipt and "grant" in receipt:
            grant = receipt.get("grant", {})
            if isinstance(grant, Mapping) and (
                grant.get("version") == "v3"
                or grant.get("domain", "").startswith("akaloris/layer0/positive-")
                and grant.get("domain", "").endswith("/v3")
            ):
                is_v3 = True

        if is_v3:
            if self._v3 is None:
                return False, "v3_kms_verifier_not_configured"
            valid, reason = self._v3.verify(
                receipt,
                packet,
                plot_id=plot_id,
                geometry_hash=geometry_hash,
                geometry_version=geometry_version,
                run_timestamp=run_timestamp,
                purpose=purpose,
                variables=variables,
                tenant_id=tenant_id,
            )
            return valid, reason

        # Legacy v1/v2 HMAC receipt
        if self.enforces_v3_only:
            return False, "legacy_v1_v2_grant_prohibited_under_v3_kms_policy"

        if self._legacy is None:
            return False, "legacy_admission_verifier_not_configured"

        return self._legacy.verify(
            receipt,
            packet,
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            geometry_version=geometry_version,
            run_timestamp=run_timestamp,
            purpose=purpose,
        )
