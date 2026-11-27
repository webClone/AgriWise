"""Server-side trusted calibration artifact store for Layer 2 crop inference (WM1-P2-12 & V2.1-P2).

A raw dictionary supplied in ``operational_context['crop_calibration_receipt']`` with
``calibration_verified=True`` cannot self-authorize calibrated species publication.
Calibration validity requires matching a non-revoked, cryptographically signed entry
registered in a trusted calibration store alongside schema, policy & evaluation binding.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple, Union


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_PARTITION_POLICY = "external_farm_cycle_year_region_disjoint_required"
_DEV_FALLBACK_CALIBRATION_SECRET = "agribrain-dev-calibration-trust-root-v2"


def _runtime_env_name() -> str:
    return (
        os.getenv("NODE_ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("ENV")
        or os.getenv("APP_ENV")
        or "development"
    ).strip().lower()


def _is_non_dev_runtime() -> bool:
    return _runtime_env_name() in {"production", "prod", "staging"}


def _resolve_signing_secret(
    explicit_secret: Optional[str] = None,
    *,
    require_production_trust: bool = False,
) -> Tuple[Optional[str], str]:
    """Resolve signing key with fail-closed behavior outside isolated local development."""
    if explicit_secret is not None and str(explicit_secret).strip():
        return str(explicit_secret).strip(), "explicit_caller_secret"

    env_sec = os.getenv("AGRIBRAIN_CALIBRATION_TRUST_SECRET", "").strip()
    if env_sec:
        return env_sec, "provisioned_env_secret"

    allow_dev = os.getenv("AGRIBRAIN_ALLOW_DEV_CALIBRATION_SECRET", "true").strip().lower() == "true"
    if require_production_trust or _is_non_dev_runtime() or not allow_dev:
        return None, "missing_provisioned_calibration_trust_secret"

    return _DEV_FALLBACK_CALIBRATION_SECRET, "isolated_dev_ephemeral_secret"


@dataclass(frozen=True)
class CalibrationEvaluationRecord:
    """Immutable independent calibration evaluation binding for a calibration artifact."""

    evaluation_digest: str
    evaluator_version: str
    dataset_scope: str
    evaluated_season_count: int
    confirmed_label_seasons_count: int
    ece: float
    multiclass_brier_score: float
    multiclass_log_loss: float
    partition_policy: str = REQUIRED_PARTITION_POLICY
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
    calibration_evaluation_digest: Optional[str] = None
    evaluation_record: Optional[Dict[str, Any]] = None
    trust_mode: str = "isolated_dev_ephemeral_secret"
    issued_at: str = ""
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
            "calibration_evaluation_digest": self.calibration_evaluation_digest,
        }

    def expected_signature(self, secret: Optional[str] = None) -> Optional[str]:
        if secret is None:
            resolved, _ = _resolve_signing_secret(None)
        else:
            resolved = secret
        if not resolved:
            return None
        raw = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hmac.new(resolved.encode("utf-8"), raw, hashlib.sha256).hexdigest()

    def signature_valid(self, secret: Optional[str] = None) -> bool:
        expected = self.expected_signature(secret)
        if not self.signature_hmac or not expected:
            return False
        return hmac.compare_digest(self.signature_hmac.lower(), expected)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "region_domain_compatibility": list(self.region_domain_compatibility),
        }


class TrustedCalibrationArtifactStore:
    """Server-side allowlist and revocation store with optional durable JSON persistence."""

    def __init__(
        self,
        *,
        signing_secret: Optional[str] = None,
        registry_path: Optional[Union[str, Path]] = None,
        require_production_trust: Optional[bool] = None,
    ) -> None:
        self._explicit_secret = signing_secret
        env_reg = os.getenv("AGRIBRAIN_CALIBRATION_REGISTRY_PATH", "").strip()
        resolved_path = registry_path if registry_path is not None else (Path(env_reg) if env_reg else None)
        self._registry_path: Optional[Path] = Path(resolved_path) if resolved_path is not None else None
        self._require_prod = (
            bool(require_production_trust)
            if require_production_trust is not None
            else (_is_non_dev_runtime() or os.getenv("AGRIBRAIN_REQUIRE_PRODUCTION_CALIBRATION_TRUST", "").lower() == "true")
        )
        self._records: Dict[str, TrustedCalibrationArtifactRecord] = {}
        self._revoked_hashes: Dict[str, str] = {}
        self._load_persisted_state()

    def _active_secret_and_mode(self, *, require_prod_override: Optional[bool] = None) -> Tuple[Optional[str], str]:
        req_prod = self._require_prod if require_prod_override is None else bool(require_prod_override)
        return _resolve_signing_secret(self._explicit_secret, require_production_trust=req_prod)

    def _load_persisted_state(self) -> None:
        if self._registry_path is None or not self._registry_path.is_file():
            return
        try:
            data = json.loads(self._registry_path.read_text(encoding="utf-8"))
        except Exception:
            return
        for k, reason in (data.get("revoked_hashes") or {}).items():
            self._revoked_hashes[str(k).lower()] = str(reason)
        for art_hash, raw in (data.get("records") or {}).items():
            if not isinstance(raw, Mapping):
                continue
            try:
                rec = TrustedCalibrationArtifactRecord(
                    calibration_artifact_hash=str(raw["calibration_artifact_hash"]).lower(),
                    feature_schema_hash=str(raw["feature_schema_hash"]).lower(),
                    class_hierarchy_version=str(raw.get("class_hierarchy_version") or "crop-taxonomy-v2"),
                    calibration_partition_policy=str(raw.get("calibration_partition_policy") or ""),
                    ece=float(raw["ece"]),
                    heldout_validation_complete=bool(raw.get("heldout_validation_complete")),
                    calibration_verified=bool(raw.get("calibration_verified")),
                    region_domain_compatibility=tuple(str(x) for x in (raw.get("region_domain_compatibility") or ())),
                    issuer=str(raw.get("issuer") or "agribrain_calibration_authority_v2"),
                    calibration_evaluation_digest=raw.get("calibration_evaluation_digest"),
                    evaluation_record=dict(raw["evaluation_record"]) if isinstance(raw.get("evaluation_record"), Mapping) else None,
                    trust_mode=str(raw.get("trust_mode") or "isolated_dev_ephemeral_secret"),
                    issued_at=str(raw.get("issued_at") or ""),
                    revoked=bool(raw.get("revoked", False)) or (str(art_hash).lower() in self._revoked_hashes),
                    revocation_reason=raw.get("revocation_reason") or self._revoked_hashes.get(str(art_hash).lower()),
                    signature_hmac=str(raw.get("signature_hmac") or ""),
                )
                self._records[rec.calibration_artifact_hash] = rec
            except Exception:
                continue

    def _persist_state(self) -> None:
        if self._registry_path is None:
            return
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "trusted_calibration_registry_v2",
            "records": {k: v.to_dict() for k, v in sorted(self._records.items())},
            "revoked_hashes": dict(sorted(self._revoked_hashes.items())),
        }
        tmp = self._registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
        tmp.replace(self._registry_path)

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
        calibration_evaluation_digest: Optional[str] = None,
        evaluation_record: Optional[Union[CalibrationEvaluationRecord, Mapping[str, Any]]] = None,
    ) -> TrustedCalibrationArtifactRecord:
        secret, trust_mode = self._active_secret_and_mode()
        if not secret:
            raise RuntimeError(
                "Cannot issue calibration artifact without provisioned AGRIBRAIN_CALIBRATION_TRUST_SECRET in non-dev runtime"
            )
        art_hash = str(calibration_artifact_hash or "").strip().lower()
        sch_hash = str(feature_schema_hash or "").strip().lower()
        if not _SHA256_RE.fullmatch(art_hash):
            raise ValueError("calibration_artifact_hash must be a lowercase 64-hex SHA-256")
        if not _SHA256_RE.fullmatch(sch_hash):
            raise ValueError("feature_schema_hash must be a lowercase 64-hex SHA-256")

        eval_dict: Optional[Dict[str, Any]] = None
        eval_digest = str(calibration_evaluation_digest or "").strip().lower() or None
        if evaluation_record is not None:
            eval_dict = (
                evaluation_record.to_dict()
                if hasattr(evaluation_record, "to_dict")
                else dict(evaluation_record)
            )
            if eval_digest is None:
                eval_digest = str(eval_dict.get("evaluation_digest") or "").strip().lower() or None
        if eval_digest is not None and not _SHA256_RE.fullmatch(eval_digest):
            raise ValueError("calibration_evaluation_digest must be a lowercase 64-hex SHA-256")

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
            calibration_evaluation_digest=eval_digest,
            evaluation_record=eval_dict,
            trust_mode=trust_mode,
            issued_at=datetime.now(timezone.utc).isoformat(),
            revoked=False,
        )
        sig = draft.expected_signature(secret)
        if not sig:
            raise RuntimeError("Failed to sign calibration artifact")
        signed = TrustedCalibrationArtifactRecord(**{**draft.__dict__, "signature_hmac": sig})
        self._records[art_hash] = signed
        self._revoked_hashes.pop(art_hash, None)
        self._persist_state()
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
            self._persist_state()

    def verify_receipt(
        self,
        calibration_receipt: Optional[Mapping[str, Any]],
        *,
        expected_feature_schema_hash: Optional[str] = None,
        require_production_trust: Optional[bool] = None,
    ) -> Tuple[str, Optional[str], str]:
        """Verify receipt strictly against registered, non-revoked, cryptographically signed store entry."""
        if not isinstance(calibration_receipt, Mapping):
            return "unavailable", None, "calibration_receipt_missing"

        self._load_persisted_state()

        art_hash = str(calibration_receipt.get("calibration_artifact_hash") or "").strip().lower()
        if not _SHA256_RE.fullmatch(art_hash):
            return "unavailable", None, "invalid_or_missing_calibration_artifact_hash"

        req_prod = self._require_prod if require_production_trust is None else bool(require_production_trust)
        secret, trust_mode = self._active_secret_and_mode(require_prod_override=req_prod)

        if art_hash in self._revoked_hashes:
            return "unavailable", art_hash, f"calibration_artifact_revoked:{self._revoked_hashes[art_hash]}"

        trusted = self._records.get(art_hash)
        if req_prod and trusted is not None and trusted.trust_mode == "isolated_dev_ephemeral_secret":
            return "unavailable", art_hash, "dev_ephemeral_calibration_secret_forbidden_in_production"
        if not secret:
            return "unavailable", art_hash, "production_calibration_trust_secret_missing"
        if trusted is None:
            return "unavailable", art_hash, "unregistered_calibration_artifact"
        if trusted.revoked:
            return "unavailable", art_hash, f"calibration_artifact_revoked:{trusted.revocation_reason or 'revoked'}"
        if not trusted.signature_valid(secret):
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

        if req_prod:
            if trust_mode == "isolated_dev_ephemeral_secret" or trusted.trust_mode == "isolated_dev_ephemeral_secret":
                return "unavailable", art_hash, "dev_ephemeral_calibration_secret_forbidden_in_production"
            if self._registry_path is None:
                return "unavailable", art_hash, "durable_calibration_registry_required_for_production"
            if not trusted.calibration_evaluation_digest or not _SHA256_RE.fullmatch(trusted.calibration_evaluation_digest):
                return "unavailable", art_hash, "immutable_calibration_evaluation_record_required"

        return "valid", art_hash, "verified_trusted_calibration_artifact"

    def status_summary(self) -> Dict[str, Any]:
        secret, trust_mode = self._active_secret_and_mode()
        return {
            "runtime_env": _runtime_env_name(),
            "trust_mode": trust_mode,
            "has_provisioned_secret": bool(secret and trust_mode != "isolated_dev_ephemeral_secret"),
            "durable_registry_configured": self._registry_path is not None,
            "durable_registry_path": str(self._registry_path) if self._registry_path else None,
            "registered_artifact_count": len(self._records),
            "revoked_artifact_count": len(self._revoked_hashes),
            "production_trust_ready": bool(
                secret
                and trust_mode != "isolated_dev_ephemeral_secret"
                and self._registry_path is not None
            ),
        }


_DEFAULT_TRUSTED_CALIBRATION_STORE = TrustedCalibrationArtifactStore()


def get_default_trusted_calibration_store() -> TrustedCalibrationArtifactStore:
    return _DEFAULT_TRUSTED_CALIBRATION_STORE


__all__ = [
    "CalibrationEvaluationRecord",
    "REQUIRED_PARTITION_POLICY",
    "TrustedCalibrationArtifactRecord",
    "TrustedCalibrationArtifactStore",
    "get_default_trusted_calibration_store",
]
