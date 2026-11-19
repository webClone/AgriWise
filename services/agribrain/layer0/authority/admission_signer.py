"""Layer 0 Cryptographic Admission Signer Authority.

Segregated outside the ASMAE Layer 05 runtime.
Provides authoritative signing of observation admission grants using
authorized Ed25519 private keys.

ASMAE runtime is strictly verifier-only and must NEVER hold private keys.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
from typing import Any, Dict, Mapping, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
import rfc8785

from services.agribrain.layer05_asmae.resolution.observation_footprint_adapter import (
    DEFAULT_ADMISSION_KEY_ID,
    ADMISSION_GRANT_DOMAIN,
    ADMISSION_PURPOSE,
    canonical_grant_bytes,
    compute_scene_asset_sha256,
    _ensure_utc_iso,
)


def create_scene_admission_receipt(
    scene: Any,
    *,
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    geometry_sha256: str,
    operator_sha256: str,
    calibrated_operator_sha256: Optional[str] = None,
    key_id: str = DEFAULT_ADMISSION_KEY_ID,
    private_key: Optional[ed25519.Ed25519PrivateKey] = None,
    domain: str = ADMISSION_GRANT_DOMAIN,
    purpose: str = ADMISSION_PURPOSE,
    source: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Create a signed cryptographic admission receipt for a scene using Ed25519 over RFC 8785 JCS.
    
    Resides in Layer 0 Authority (strictly outside the ASMAE Layer 05 runtime).
    Requires an explicit authorized issuer private key capability (Ed25519PrivateKey).
    Private signing keys are NEVER bundled or defaulted into ASMAE source or worker processes.
    """
    if private_key is None:
        raise PermissionError(
            "Authorized issuer capability required: private_key must be explicitly provided; "
            "production verifier and worker code cannot self-provision or embed private keys."
        )
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise TypeError("private_key must be an ed25519.Ed25519PrivateKey instance")

    asset_sha = compute_scene_asset_sha256(scene)
    if not asset_sha:
        raise ValueError("Cannot create admission receipt: scene has no exact asset data")

    valid_time = _ensure_utc_iso(
        getattr(scene, "acquisition_time", None)
        or getattr(scene, "timestamp", None)
        or getattr(scene, "date", None)
    )
    commit_time = _ensure_utc_iso(
        getattr(scene, "committed_at", None)
        or getattr(scene, "journal_committed_at", None)
        or getattr(scene, "journal_entry_time", None)
    )
    if not valid_time or not commit_time:
        raise ValueError("Cannot create admission receipt: valid_time or committed_at missing")

    sensor_str = str(source or getattr(scene, "sensor", "sentinel2")).lower()
    run_now = now or datetime.now(timezone.utc)
    grant = {
        "domain": str(domain),
        "version": "v1",
        "canonical_format": "rfc8785_jcs_v1",
        "algorithm": "Ed25519",
        "key_id": str(key_id),
        "purpose": str(purpose),
        "source": sensor_str,
        "tenant_id": str(tenant_id),
        "farm_id": str(farm_id),
        "plot_id": str(plot_id),
        "geometry_hash": str(geometry_sha256),
        "asset_sha256": str(asset_sha),
        "operator_sha256": str(operator_sha256),
        "calibrated_operator_sha256": str(calibrated_operator_sha256 or operator_sha256),
        "observation_valid_time": valid_time,
        "committed_at": commit_time,
        "issued_at": run_now.isoformat(),
        "expires_at": (run_now + timedelta(days=365)).isoformat(),
    }
    canonical_bytes = canonical_grant_bytes(grant)
    grant_digest = hashlib.sha256(canonical_bytes).hexdigest()
    sig_raw = private_key.sign(canonical_bytes)
    sig_str = f"ed25519:{sig_raw.hex()}"

    return {
        "contract_version": "canonical_positive_admission_grant_v1",
        "key_id": str(key_id),
        "signature": sig_str,
        "grant_digest": f"sha256:{grant_digest}",
        "grant": grant,
    }
