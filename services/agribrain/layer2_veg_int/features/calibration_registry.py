"""Server-side trusted calibration artifact store for Layer 2 crop inference (WM1-P2-12).

A raw dictionary supplied in ``operational_context['crop_calibration_receipt']`` with
``calibration_verified=True`` cannot self-authorize calibrated species publication.
Calibration validity requires matching a non-revoked, cryptographically signed entry
registered in a trusted calibration store alongside schema & policy binding.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_PARTITION_POLICY = "external_farm_cycle_year_region_disjoint_required"


def _calibration_signing_secret() -> str:
    env_sec = os.getenv("AGRIBRAIN_CALIBRATION_TRUST_SECRET", "").strip()
    if env_sec:
        return env_sec
    return "agribrain-dev-calibration-trust-root-v2"


@dataclass(frozen=True)
class TrustedCalibrationArtifactRecord:
    calibration_artifact_hash: str
    feature_schema_hash: str
    class_hierarchy_version: str
    calibration_partition_policy: str
    ece: float
    heldout_validation_complete: bool
    calibration_verified: bool
    region_domain_compatibility: Tuple[str, ...] = ()
    issuer: str = "agribrain_calibration_authority_v2"
    revoked: bool = False
    revocation_reason: Optional[str] = None
    signature_hmac: str = ""

    def canonical_payload(self) -> Dict[str, Any]:
        return {
            "calibration_artifact_hash": self.calibration_artifact_hash,
            "feature_schema_hash": self.feature_schema_hash,
            "class_hierarchy_version": self.class_hierarchy_version,
            "calibration_partition_policy": self.calibration_partition_policy,
            "ece": round(float(self.ece), 6),
            "heldout_validation_complete": bool(self.heldout_validation_complete),
            "calibration_verified": bool(self.calibration_verified),
            "region_domain_compatibility": list(sorted(self.region_domain_compatibility)),
            "issuer": self.issuer,
        }

    def expected_signature(self, secret: Optional[str] = None) -> str:
        raw = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        key = (secret if secret is not None else _calibration_signing_secret()).encode("utf-8")
        return hmac.new(key, raw, hashlib.sha256).hexdigest()

    def signature_valid(self, secret: Optional[str] = None) -> bool:
        if not self.signature_hmac:
            return False
        return hmac.compare_digest(self.signature_hmac.lower(), self.expected_signature(secret))


class TrustedCalibrationArtifactStore:
    """In-process server-side allowlist and revocation store for calibration artifacts."""

    def __init__(self, *, signing_secret: Optional[str] = None) -> None:
        self._secret = signing_secret
        self._records: Dict[str, TrustedCalibrationArtifactRecord] = {}
        self._revoked_hashes: Dict[str, str] = {}

    def issue_and_register(
        self,
        *,
        calibration_artifact_hash: str,
        feature_schema_hash: str,
        class_hierarchy_version: str = "crop-taxonomy-v2",
        calibration_partition_policy: str = REQUIRED_PARTITION_POLICY,
        ece: float = 0.04,
        heldout_validation_complete: bool = True,
        calibration_verified: bool = True,
        region_domain_compatibility: Tuple[str, ...] = ("compatible",),
        issuer: str = "agribrain_calibration_authority_v2",
    ) -> TrustedCalibrationArtifactRecord:
        art_hash = str(calibration_artifact_hash or "").strip().lower()
        sch_hash = str(feature_schema_hash or "").strip().lower()
        if not _SHA256_RE.fullmatch(art_hash):
            raise ValueError("calibration_artifact_hash must be a lowercase 64-hex SHA-256")
        if not _SHA256_RE.fullmatch(sch_hash):
            raise ValueError("feature_schema_hash must be a lowercase 64-hex SHA-256")
        draft = TrustedCalibrationArtifactRecord(
            calibration_artifact_hash=art_hash,
            feature_schema_hash=sch_hash,
            class_hierarchy_version=str(class_hierarchy_version or "crop-taxonomy-v2"),
            calibration_partition_policy=str(calibration_partition_policy or ""),
            ece=float(ece),
            heldout_validation_complete=bool(heldout_validation_complete),
            calibration_verified=bool(calibration_verified),
            region_domain_compatibility=tuple(sorted(str(x) for x in region_domain_compatibility if str(x).strip())),
            issuer=str(issuer or "agribrain_calibration_authority_v2"),
            revoked=False,
        )
        signed = TrustedCalibrationArtifactRecord(
            **{**draft.__dict__, "signature_hmac": draft.expected_signature(self._secret)}
        )
        self._records[art_hash] = signed
        self._revoked_hashes.pop(art_hash, None)
        return signed

    def revoke(self, calibration_artifact_hash: str, reason: str = "revoked_by_authority") -> None:
        art_hash = str(calibration_artifact_hash or "").strip().lower()
        if art_hash:
            self._revoked_hashes[art_hash] = str(reason or "revoked_by_authority")
            rec = self._records.get(art_hash)
            if rec is not None:
                self._records[art_hash] = TrustedCalibrationArtifactRecord(
                    **{**rec.__dict__, "revoked": True, "revocation_reason": self._revoked_hashes[art_hash]}
                )

    def verify_receipt(
        self,
        calibration_receipt: Optional[Mapping[str, Any]],
        *,
        expected_feature_schema_hash: Optional[str] = None,
    ) -> Tuple[str, Optional[str], str]:
        """Verify receipt strictly against registered, non-revoked, cryptographically signed store entry."""
        if not isinstance(calibration_receipt, Mapping):
            return "unavailable", None, "calibration_receipt_missing"

        art_hash = str(calibration_receipt.get("calibration_artifact_hash") or "").strip().lower()
        if not _SHA256_RE.fullmatch(art_hash):
            return "unavailable", None, "invalid_or_missing_calibration_artifact_hash"

        if art_hash in self._revoked_hashes:
            return "unavailable", art_hash, f"calibration_artifact_revoked:{self._revoked_hashes[art_hash]}"

        trusted = self._records.get(art_hash)
        if trusted is None:
            return "unavailable", art_hash, "unregistered_calibration_artifact"
        if trusted.revoked:
            return "unavailable", art_hash, f"calibration_artifact_revoked:{trusted.revocation_reason or 'revoked'}"
        if not trusted.signature_valid(self._secret):
            return "unavailable", art_hash, "trusted_store_signature_mismatch"

        supplied_sig = str(
            calibration_receipt.get("signature_hmac") or calibration_receipt.get("authority_signature") or ""
        ).strip().lower()
        if not supplied_sig or not hmac.compare_digest(supplied_sig, trusted.signature_hmac.lower()):
            return "unavailable", art_hash, "calibration_receipt_signature_unverified"

        if expected_feature_schema_hash and trusted.feature_schema_hash != str(expected_feature_schema_hash).strip().lower():
            return "unavailable", art_hash, "calibration_schema_hash_mismatch"

        supplied_schema = str(calibration_receipt.get("feature_schema_hash") or "").strip().lower()
        if supplied_schema and supplied_schema != trusted.feature_schema_hash:
            return "unavailable", art_hash, "calibration_receipt_schema_mismatch"

        if (
            trusted.calibration_partition_policy != REQUIRED_PARTITION_POLICY
            or not trusted.calibration_verified
            or not trusted.heldout_validation_complete
            or not isinstance(trusted.ece, (int, float))
            or float(trusted.ece) > 0.12
        ):
            return "unavailable", art_hash, "calibration_policy_or_ece_gate_failed"

        return "valid", art_hash, "verified_trusted_calibration_artifact"


_DEFAULT_TRUSTED_CALIBRATION_STORE = TrustedCalibrationArtifactStore()


def get_default_trusted_calibration_store() -> TrustedCalibrationArtifactStore:
    return _DEFAULT_TRUSTED_CALIBRATION_STORE


__all__ = [
    "REQUIRED_PARTITION_POLICY",
    "TrustedCalibrationArtifactRecord",
    "TrustedCalibrationArtifactStore",
    "get_default_trusted_calibration_store",
]
