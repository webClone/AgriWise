"""MESIA Continuous Capability Governance & Revocation Authority — R6 §12 / P10 / D03.

Manages 8-gate qualification dossiers (CapabilityAuthorityRecord), periodic
auditing, cryptographic Ed25519 signature governance, and automatic fail-closed
revocation (RevocationEvent) enforcing Principles P-09, P-10, and D03.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from ..contracts.authority import CapabilityAuthorityRecord, RevocationEvent

DEFAULT_CAPABILITY_ISSUER: str = "agriwise:trust:mesia_science_gate"

_TRUSTED_CAPABILITY_ISSUERS: Dict[str, ed25519.Ed25519PublicKey] = {}
_TEST_CAPABILITY_PRIVATE_KEYS: Dict[str, ed25519.Ed25519PrivateKey] = {}
_REVOKED_CAPABILITIES: Dict[str, RevocationEvent] = {}

_FORBIDDEN_USE_SUBSTRINGS = (
    "AUTONOMOUS_ACTUATION",
    "AUTHORITATIVE_STATE_MUTATION",
    "AUTONOMOUS_IRRIGATION",
    "AUTONOMOUS_PESTICIDE",
    "DIRECT_STATE_MUTATION",
)

_DEFAULT_PROHIBITED_USES = [
    "AUTONOMOUS_ACTUATION",
    "AUTHORITATIVE_STATE_MUTATION",
    "Autonomous pesticide prescription",
    "Deep aquifer water rights enforcement",
    "Direct agricultural state mutation",
]


def _coerce_datetime(dt_val: Any) -> Optional[datetime]:
    """Coerce string or datetime value to UTC-aware datetime instance."""
    if dt_val is None:
        return None
    if isinstance(dt_val, datetime):
        return dt_val if dt_val.tzinfo else dt_val.replace(tzinfo=timezone.utc)
    if isinstance(dt_val, str):
        clean = dt_val.strip()
        if not clean:
            return None
        try:
            parsed = datetime.fromisoformat(clean)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def register_trusted_capability_issuer(issuer: str, public_key: Any) -> None:
    """Register an independently provisioned Ed25519 public key for a capability issuer (D03)."""
    if isinstance(public_key, ed25519.Ed25519PublicKey):
        pub = public_key
    elif isinstance(public_key, bytes) and len(public_key) == 32:
        pub = ed25519.Ed25519PublicKey.from_public_bytes(public_key)
    elif isinstance(public_key, str):
        clean = public_key.strip()
        if clean.startswith("ed25519:"):
            clean = clean[len("ed25519:"):]
        pub = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(clean))
    else:
        raise TypeError(f"Unsupported public key type: {type(public_key)}")
    _TRUSTED_CAPABILITY_ISSUERS[issuer] = pub


def get_trusted_capability_issuer_public_key(issuer: str) -> Optional[ed25519.Ed25519PublicKey]:
    """Retrieve provisioned Ed25519 public key for an issuer (D03)."""
    return _TRUSTED_CAPABILITY_ISSUERS.get(issuer)


def provision_test_capability_issuer_keypair(
    issuer: str = DEFAULT_CAPABILITY_ISSUER,
) -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    """Provision a fresh Ed25519 keypair for test or default runtime governance (D03)."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    _TEST_CAPABILITY_PRIVATE_KEYS[issuer] = priv
    _TRUSTED_CAPABILITY_ISSUERS[issuer] = pub
    return priv, pub


def get_test_capability_private_key(
    issuer: str = DEFAULT_CAPABILITY_ISSUER,
) -> Optional[ed25519.Ed25519PrivateKey]:
    """Retrieve test private key for an issuer if provisioned (D03)."""
    return _TEST_CAPABILITY_PRIVATE_KEYS.get(issuer)


def is_capability_revoked(capability_id: str) -> Tuple[bool, Optional[RevocationEvent]]:
    """Check whether a capability has been revoked in the monotonic registry (P-10, D03)."""
    clean_id = str(capability_id).strip()
    if clean_id in _REVOKED_CAPABILITIES:
        return True, _REVOKED_CAPABILITIES[clean_id]
    return False, None


def revoke_capability_authority(
    record_or_id: Union[CapabilityAuthorityRecord, str],
    trigger_reason: str,
    new_state: str = "REVOKED",
) -> RevocationEvent:
    """Demote or withdraw capability authority and record monotonic event (P-10, D03)."""
    now = datetime.now(timezone.utc)
    if isinstance(record_or_id, CapabilityAuthorityRecord):
        cap_id = record_or_id.capability_id
        prev_state = record_or_id.state
        affected_uses = list(record_or_id.allowed_uses)
    else:
        cap_id = str(record_or_id).strip()
        prev_state = "QUALIFIED"
        affected_uses = []

    rev_event = RevocationEvent(
        event_id=f"rev-ev-{cap_id}-{int(now.timestamp())}",
        capability_authority_ref=cap_id,
        revoked_at=now,
        trigger_reason=trigger_reason,
        previous_state=prev_state,
        new_state=new_state,
        affected_uses=affected_uses,
        affected_deployments=["ALL_CLUSTERS"],
        remediation_required="Re-calibration and multi-radio closure verification required.",
        recommissioning_checklist_ref="CHK_RECOMMISSION_R6",
        notified_stakeholders=["ScienceGateBoard", "FieldOperations", "ASMAE_Engine"],
    )
    _REVOKED_CAPABILITIES[cap_id] = rev_event
    return rev_event


def clear_capability_revocations_for_tests() -> None:
    """Clear in-memory revocation store for test suite isolation."""
    _REVOKED_CAPABILITIES.clear()


def sign_capability_record(
    record: CapabilityAuthorityRecord,
    private_key: ed25519.Ed25519PrivateKey,
    *,
    issuer_id: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    qualification_receipt_hash: Optional[str] = None,
) -> CapabilityAuthorityRecord:
    """Sign canonical capability record bytes with an Ed25519 private key (D03)."""
    eff_issuer = str(issuer_id or record.issuer_id or DEFAULT_CAPABILITY_ISSUER).strip()
    now = datetime.now(timezone.utc)
    eff_expires = expires_at or record.expires_at or (now + timedelta(days=record.renewal_cadence_days))
    rec_hash = qualification_receipt_hash or record.qualification_receipt_hash
    if not rec_hash or len(rec_hash) != 64:
        rec_hash = hashlib.sha256(f"{record.capability_id}:{record.target_variable}:{now.isoformat()}".encode("utf-8")).hexdigest()

    pub_bytes = private_key.public_key().public_bytes_raw()
    pub_hex = "ed25519:" + pub_bytes.hex()

    unsigned_record = replace(
        record,
        issuer_id=eff_issuer,
        issuer_public_key=pub_hex,
        expires_at=eff_expires,
        qualification_receipt_hash=rec_hash,
        signature=None,
        validation_signature=None,
    )
    canonical = unsigned_record.compute_canonical_bytes()
    sig_bytes = private_key.sign(canonical)
    sig_str = "ed25519:" + sig_bytes.hex()

    return replace(unsigned_record, signature=sig_str, validation_signature=sig_str)


def verify_capability_authority(
    record: Any,
    *,
    current_time: Optional[datetime] = None,
    trusted_issuers: Optional[Mapping[str, Any]] = None,
) -> Tuple[bool, str]:
    """Cryptographically and administratively verify scientific capability authority (D03).

    Checks:
    1. Valid CapabilityAuthorityRecord dataclass instance.
    2. Monotonic revocation registry check (Principle P-10).
    3. State == 'QUALIFIED'.
    4. All 8 qualification gates == True (R6 §12).
    5. Explicit named target variable (Principle P-09: no global/wildcard certifications).
    6. Non-expired and not post-dated (issued_at <= now < expires_at).
    7. 64-character SHA256 qualification_receipt_hash present.
    8. Prohibited uses specified; allowed_uses strictly devoid of autonomous actuation or state mutation.
    9. Cryptographic Ed25519 signature valid against provisioned issuer public key.
    """
    if not isinstance(record, CapabilityAuthorityRecord):
        return False, "Not a CapabilityAuthorityRecord instance"

    # 1. Monotonic revocation check (P-10)
    is_rev, rev_ev = is_capability_revoked(record.capability_id)
    if is_rev or record.state == "REVOKED":
        reason = rev_ev.trigger_reason if rev_ev else "Capability state is REVOKED"
        return False, f"Capability {record.capability_id} is revoked: {reason}"

    # 2. Qualification state
    if record.state != "QUALIFIED":
        return False, f"Capability state is {record.state}, expected QUALIFIED"

    # 3. 8 Qualification Gates (R6 §12)
    if not record.all_gates_passed:
        return False, "Not all 8 qualification gates passed"

    # 4. Explicit named biological target variable (Principle P-09: no global certification)
    target_var = str(record.target_variable or "").strip()
    if not target_var or target_var.upper() in (
        "*", "ALL", "GLOBAL", "UNSPECIFIED", "ANY", "UNSPECIFIED_PENDING_CALIBRATED_OPERATOR"
    ):
        return False, f"Target variable {target_var!r} is invalid; explicit target variable required (Principle P-09)"

    # 5. Temporal validity & expiration
    now = current_time or datetime.now(timezone.utc)
    issued = _coerce_datetime(record.issued_at)
    expires = _coerce_datetime(record.expires_at)
    if issued is None:
        return False, "Missing or invalid issued_at timestamp"
    if expires is None:
        return False, "Missing or invalid expires_at timestamp"

    if issued > now + timedelta(seconds=60):
        return False, f"Capability issued_at {issued} is in the future"
    if now >= expires:
        return False, f"Capability expired at {expires}"

    # 6. Qualification receipt hash (64-char SHA256)
    receipt_hash = str(record.qualification_receipt_hash or "").strip()
    if len(receipt_hash) != 64 or any(c not in "0123456789abcdefABCDEF" for c in receipt_hash):
        return False, "Missing or invalid 64-character qualification_receipt_hash"

    # 7. Prohibited & allowed uses governance
    if not record.prohibited_uses:
        return False, "prohibited_uses list must not be empty"

    prohibited_combined = " ".join([str(p).upper() for p in record.prohibited_uses])
    if not any(sub in prohibited_combined for sub in _FORBIDDEN_USE_SUBSTRINGS):
        return False, "prohibited_uses must explicitly forbid autonomous actuation and state mutation"

    for use in record.allowed_uses:
        use_u = str(use).upper()
        if any(bad in use_u for bad in _FORBIDDEN_USE_SUBSTRINGS):
            return False, f"Forbidden use {use!r} found in allowed_uses"

    # 8. Cryptographic Ed25519 signature verification
    sig_str = str(record.signature or "").strip()
    if not sig_str or not sig_str.startswith("ed25519:"):
        return False, "Missing or invalid Ed25519 signature prefix"

    issuer = str(record.issuer_id or DEFAULT_CAPABILITY_ISSUER).strip()
    pub_key = None
    if trusted_issuers and issuer in trusted_issuers:
        cand = trusted_issuers[issuer]
        if isinstance(cand, ed25519.Ed25519PublicKey):
            pub_key = cand
        elif isinstance(cand, (bytes, str)):
            clean = cand.strip() if isinstance(cand, str) else cand
            if isinstance(clean, str) and clean.startswith("ed25519:"):
                clean = clean[len("ed25519:"):]
            raw = bytes.fromhex(clean) if isinstance(clean, str) else clean
            pub_key = ed25519.Ed25519PublicKey.from_public_bytes(raw)
    else:
        pub_key = get_trusted_capability_issuer_public_key(issuer)

    if pub_key is None:
        return False, f"Untrusted or unprovisioned capability issuer: {issuer}"

    sig_hex = sig_str[len("ed25519:"):]
    try:
        sig_bytes = bytes.fromhex(sig_hex)
    except ValueError:
        return False, "Invalid signature hex encoding"

    try:
        unsigned_record = replace(record, signature=None, validation_signature=None)
        canonical = unsigned_record.compute_canonical_bytes()
        pub_key.verify(sig_bytes, canonical)
    except InvalidSignature:
        return False, "Cryptographic Ed25519 signature verification failed"
    except Exception as ex:
        return False, f"Signature verification error: {ex}"

    return True, "Capability authority verified"


# Initialize default trusted issuer keypair
provision_test_capability_issuer_keypair(DEFAULT_CAPABILITY_ISSUER)


class CapabilityGovernanceAuthority:
    """Manages capability qualification dossiers, periodic reviews, and revocations."""

    @staticmethod
    def issue_qualification_record(
        capability_id: str,
        capability_name: str,
        target_variable: str,
        supported_radios: List[str],
        supported_soils: List[str],
        supported_crops: List[str],
        gate_repeatability_passed: bool = False,
        gate_sensitivity_passed: bool = False,
        gate_specificity_passed: bool = False,
        gate_observability_passed: bool = False,
        gate_transfer_passed: bool = False,
        gate_closure_passed: bool = False,
        gate_incremental_value_passed: bool = False,
        gate_governance_passed: bool = False,
        validation_signature: Optional[str] = None,
        *,
        issuer_id: str = DEFAULT_CAPABILITY_ISSUER,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        expires_at: Optional[datetime] = None,
        renewal_cadence_days: int = 90,
        qualification_receipt_hash: Optional[str] = None,
        prohibited_uses: Optional[List[str]] = None,
        allowed_uses: Optional[List[str]] = None,
    ) -> CapabilityAuthorityRecord:
        """Issue qualification dossier with explicit gate results and cryptographic authority (D03)."""
        now = datetime.now(timezone.utc)

        all_passed = all([
            gate_repeatability_passed,
            gate_sensitivity_passed,
            gate_specificity_passed,
            gate_observability_passed,
            gate_transfer_passed,
            gate_closure_passed,
            gate_incremental_value_passed,
            gate_governance_passed,
        ])

        # Require genuine, non-empty validation signature (minimum 16 chars)
        has_valid_sig = bool(validation_signature and len(str(validation_signature).strip()) >= 16)

        clean_target = str(target_variable or "").strip()
        has_valid_target = bool(
            clean_target and clean_target.upper() not in (
                "*", "ALL", "GLOBAL", "UNSPECIFIED", "ANY", "UNSPECIFIED_PENDING_CALIBRATED_OPERATOR"
            )
        )

        effective_prohibited = list(prohibited_uses) if prohibited_uses is not None else list(_DEFAULT_PROHIBITED_USES)
        effective_allowed = (
            list(allowed_uses) if allowed_uses is not None
            else (["RESEARCH_ONLY"] if not all_passed else ["RESEARCH_ONLY", "CONTEXT", "DIAGNOSTIC_SUPPORT", "STATE_PROPOSAL"])
        )

        has_forbidden_use = any(
            any(bad in str(u).upper() for bad in _FORBIDDEN_USE_SUBSTRINGS)
            for u in effective_allowed
        )

        effective_expires = expires_at or (now + timedelta(days=renewal_cadence_days))
        effective_receipt_hash = qualification_receipt_hash or hashlib.sha256(
            f"{capability_id}:{clean_target}:{now.isoformat()}".encode("utf-8")
        ).hexdigest()

        is_qualified = all_passed and has_valid_sig and has_valid_target and not has_forbidden_use

        # Determine signing key
        key_to_use = signing_key or get_test_capability_private_key(issuer_id)
        pub_hex = None

        if is_qualified and key_to_use is not None:
            pub_hex = "ed25519:" + key_to_use.public_key().public_bytes_raw().hex()

        raw_record = CapabilityAuthorityRecord(
            capability_id=capability_id,
            capability_name=capability_name,
            version="1.0.0",
            target_variable=target_variable,
            gate_repeatability_passed=gate_repeatability_passed,
            gate_sensitivity_passed=gate_sensitivity_passed,
            gate_specificity_passed=gate_specificity_passed,
            gate_observability_passed=gate_observability_passed,
            gate_transfer_passed=gate_transfer_passed,
            gate_closure_passed=gate_closure_passed,
            gate_incremental_value_passed=gate_incremental_value_passed,
            gate_governance_passed=gate_governance_passed,
            supported_radio_families=supported_radios,
            supported_soil_textures=supported_soils,
            supported_crop_types=supported_crops,
            supported_moisture_range=[],
            geographic_domain="",
            climate_zones=[],
            allowed_uses=effective_allowed,
            prohibited_uses=effective_prohibited,
            state="QUALIFIED" if is_qualified else "UNQUALIFIED_PENDING_EVIDENCE",
            issued_at=now,
            expires_at=effective_expires,
            renewal_cadence_days=renewal_cadence_days,
            review_board="",
            approved_by=[],
            preregistration_ref="",
            closure_certificate_ref=f"close-cert-{capability_id}",
            observability_certificate_ref=f"obs-cert-{capability_id}",
            fallback_capability_ref="weather_crop_water_balance_fallback",
            issuer_id=issuer_id,
            issuer_public_key=pub_hex,
            signature=None,
            validation_signature=validation_signature,
            qualification_receipt_hash=effective_receipt_hash,
        )

        if is_qualified and key_to_use is not None:
            canonical = raw_record.compute_canonical_bytes()
            sig_bytes = key_to_use.sign(canonical)
            sig_str = "ed25519:" + sig_bytes.hex()
            return replace(raw_record, signature=sig_str, validation_signature=sig_str)

        return raw_record

    @staticmethod
    def revoke_authority_on_drift(
        record: CapabilityAuthorityRecord,
        trigger_reason: str,
        new_state: str = "REVOKED",
    ) -> RevocationEvent:
        """Principle P-10: Revoke or demote capability when drift or violation occurs."""
        return revoke_capability_authority(record, trigger_reason, new_state=new_state)
