"""Verifier-only cryptographic admission trust boundary for ASMAE IR-04.

Production ASMAE has no signing function, private signing key, or default trust
root. Layer 0's independently authorized issuer signs the grant externally.
This module accepts only explicitly configured Ed25519 PUBLIC verification keys.

Canonicalization uses a named, narrowly scoped sorted-JSON UTF-8 v1 profile.
It does not claim RFC 8785 interoperability; only string-valued fixed fields
are allowed. A future RFC 8785 upgrade must use a new version and domain.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
from typing import Any, Dict, Mapping, Optional, Tuple

ADMISSION_DOMAIN = "akaloris/layer05/positive-scene-admission/v1"
ADMISSION_PURPOSE = "kalman_state_observation"
CANONICALIZATION_VERSION = "akaloris/sorted-json-utf8-strings/v1"
ADMISSION_ALGORITHM = "Ed25519"
TRUST_ENV = "AKALORIS_LAYER0_ADMISSION_VERIFIERS_JSON"
_HASH = re.compile(r"^[0-9a-f]{64}$")
_GRANT_KEYS = frozenset({
    "algorithm", "canonicalization", "domain", "purpose", "key_id",
    "source", "tenant_id", "farm_id", "plot_id", "geometry_hash",
    "asset_sha256", "operator_sha256", "calibrated_operator_sha256",
    "observation_valid_time", "committed_at", "issued_at", "expires_at",
})


def _source(value: Any) -> Optional[str]:
    name = str(value or "").upper().replace("_", "-")
    if name in {"S2", "SENTINEL-2", "S2-MSI", "SENTINEL2"}:
        return "S2"
    if name in {"S1", "SENTINEL-1", "S1-SAR", "SENTINEL1"}:
        return "S1"
    return None


def _utc(value: Any) -> Optional[datetime]:
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def canonical_grant_bytes(grant: Mapping[str, str]) -> bytes:
    """Versioned exact JSON profile, NOT RFC 8785.

    Grants have a fixed collection of string fields so number formatting,
    Python object coercion, and serializer discrepancies are excluded.
    """
    if not isinstance(grant, Mapping) or set(grant) != _GRANT_KEYS:
        raise ValueError("invalid_admission_grant_schema")
    if any(not isinstance(v, str) or not v for v in grant.values()):
        raise ValueError("admission_grant_fields_must_be_nonempty_strings")
    if grant["canonicalization"] != CANONICALIZATION_VERSION:
        raise ValueError("unsupported_admission_canonicalization")
    return json.dumps(
        dict(grant), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def get_trusted_admission_keyring() -> Dict[str, Dict[str, Any]]:
    """Load explicit PUBLIC verifier keys; no embedded or fallback secrets.

    Env example:
      {"issuer-id":{"public_key_b64":"<base64-32-byte-public-key>",
                    "source":"S2","purpose":"kalman_state_observation",
                    "domain":"akaloris/layer05/positive-scene-admission/v1"}}

    Any malformed entry invalidates the entire configuration (fail closed).
    The old AKALORIS_LAYER0_ISSUER_KEYS symmetric-secret variable is ignored.
    """
    raw = os.environ.get(TRUST_ENV, "").strip()
    if not raw:
        return {}
    try:
        config = json.loads(raw)
        if not isinstance(config, dict) or not config:
            return {}
        result: Dict[str, Dict[str, Any]] = {}
        for kid, item in config.items():
            if not isinstance(kid, str) or not kid or not isinstance(item, dict):
                return {}
            if set(item) != {"public_key_b64", "source", "purpose", "domain"}:
                return {}
            source = _source(item["source"])
            if (source is None or item["purpose"] != ADMISSION_PURPOSE
                    or item["domain"] != ADMISSION_DOMAIN):
                return {}
            public_key = base64.b64decode(item["public_key_b64"], validate=True)
            if len(public_key) != 32:
                return {}
            result[kid] = {
                "source": source, "purpose": item["purpose"],
                "domain": item["domain"], "public_key": public_key,
            }
        return result
    except (ValueError, TypeError, KeyError, binascii.Error):
        return {}


def verify_admission_grant(
    receipt: Any,
    *,
    scene_source: Any,
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    geometry_sha256: str,
    asset_sha256: Optional[str],
    operator_sha256: str,
    calibrated_operator_sha256: str,
    valid_time: str,
    committed_at: str,
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """Verify a detached Ed25519 grant scoped to source, purpose, data, clocks.

    A caller-provided trusted keyring is intentionally NOT accepted. Verification
    trust is controlled by deployment configuration, not supplied observations.
    """
    if not isinstance(receipt, dict) or set(receipt) != {"grant", "signature"}:
        return False, "invalid_admission_envelope_or_legacy_mac"
    grant, encoded_signature = receipt["grant"], receipt["signature"]
    try:
        data = canonical_grant_bytes(grant)
    except (ValueError, TypeError):
        return False, "invalid_or_unsupported_admission_grant"

    if grant["algorithm"] != ADMISSION_ALGORITHM:
        return False, "unsupported_admission_algorithm"
    if grant["domain"] != ADMISSION_DOMAIN or grant["purpose"] != ADMISSION_PURPOSE:
        return False, "wrong_admission_domain_or_purpose"

    scene_sensor = _source(scene_source)
    if not scene_sensor or grant["source"] != scene_sensor:
        return False, "wrong_sensor_source"

    keyring = get_trusted_admission_keyring()
    key_id = grant["key_id"]
    policy = keyring.get(key_id)
    if not policy:
        return False, "untrusted_or_unconfigured_issuer"
    if (policy["source"] != scene_sensor or policy["purpose"] != grant["purpose"]
            or policy["domain"] != grant["domain"]):
        return False, "issuer_sensor_or_purpose_scope_mismatch"

    try:
        if not isinstance(encoded_signature, str):
            return False, "invalid_admission_signature"
        signature = base64.b64decode(encoded_signature, validate=True)
        if len(signature) != 64:
            return False, "invalid_admission_signature"
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        Ed25519PublicKey.from_public_bytes(policy["public_key"]).verify(signature, data)
    except (ValueError, TypeError, binascii.Error, ImportError, InvalidSignature):
        return False, "invalid_admission_signature"

    expected = {
        "tenant_id": tenant_id, "farm_id": farm_id, "plot_id": plot_id,
        "geometry_hash": geometry_sha256, "asset_sha256": asset_sha256,
        "operator_sha256": operator_sha256,
        "calibrated_operator_sha256": calibrated_operator_sha256,
    }
    if any(not isinstance(value, str) or not value for value in expected.values()):
        return False, "missing_authoritative_binding"
    if not all(_HASH.fullmatch(expected[k]) for k in (
        "geometry_hash", "asset_sha256", "operator_sha256",
        "calibrated_operator_sha256",
    )):
        return False, "invalid_authoritative_digest"
    if any(grant[key] != value for key, value in expected.items()):
        return False, "grant_namespace_asset_or_operator_mismatch"

    t, k = _utc(valid_time), _utc(committed_at)
    gt, gk = _utc(grant["observation_valid_time"]), _utc(grant["committed_at"])
    if not all((t, k, gt, gk)) or gt != t or gk != k:
        return False, "grant_bitemporal_mismatch"
    if k < t:
        return False, "knowledge_commitment_precedes_observation"

    issued, expires = _utc(grant["issued_at"]), _utc(grant["expires_at"])
    check_at = _utc(now or datetime.now(timezone.utc))
    if not all((issued, expires, check_at)):
        return False, "missing_or_invalid_admission_expiration"
    if issued < k or issued > check_at or expires <= check_at or expires <= issued:
        return False, "inadmissible_admission_lifetime"
    if expires - issued > timedelta(days=366):
        return False, "admission_grant_ttl_exceeds_policy"

    return True, "verified_external_issuer_admission"
