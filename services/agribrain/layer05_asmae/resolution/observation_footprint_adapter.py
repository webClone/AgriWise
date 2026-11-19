"""IR-04-R03: Authenticated observation footprint adapter.

Translates admitted Layer 0/1 observation scenes (Sentinel-2, Sentinel-1)
into authentic EvidenceFootprint instances for state×cell spatial support evaluation.
Fails closed on uncalibrated operators, cross-tenant scenes, non-metric CRS, or
invalid geometry hashes.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import base64
import hashlib
import json
import math
import os
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
import rfc8785

from .state_cell_support import EvidenceFootprint, STATE_NAMES, SpatialSupportViolation
from ..chain_integrity import compute_h_matrix_digest
from ..geometry.psf import get_psf_model

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Physical & epistemic sensor specifications
S2_OPTICAL_STATES = (
    "vigor", "lai", "chlorophyll", "canopy_water",
    "structure", "bare_soil_fraction", "phenology_progress",
)
# C-band SAR directly senses surface roughness and near-surface moisture (top ~5cm).
# Root-zone soil moisture is an indirect modeled coupling (EnKF propagation), never a direct observation.
S1_SAR_STATES = (
    "surface_wetness_event", "structure",
)

S2_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s2_msi/spatial_v1").hexdigest()
S2_CALIBRATED_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s2_msi/calibrated_psf_v1").hexdigest()

S1_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s1_cband_sar/spatial_v1").hexdigest()
S1_CALIBRATED_OPERATOR_SHA256 = hashlib.sha256(b"akaloris/operator/s1_cband_sar/calibrated_psf_v1").hexdigest()

# Cryptographic Admission Authority (IR04-665-01, IR04-5CC-P0-01)
DEFAULT_ADMISSION_KEY_ID = "akaloris-l0-s2-production-key-v1"
ADMISSION_GRANT_DOMAIN = "akaloris/layer05/positive-scene-admission/v1"
ALLOWED_ADMISSION_DOMAINS = frozenset((
    ADMISSION_GRANT_DOMAIN,
    "akaloris/layer0/positive-state-observation/v1",
    "akaloris/layer0/positive-scene-admission/v1",
    "akaloris/layer0/positive-state-input/v3",
))

ADMISSION_PURPOSE = "kalman_state_observation"
ADMISSION_SCENE_PURPOSE = "asmae_observation_admission"
ALLOWED_ADMISSION_PURPOSES = frozenset((
    ADMISSION_PURPOSE,
    ADMISSION_SCENE_PURPOSE,
))


@dataclass(frozen=True)
class TrustedAdmissionIssuerKey:
    """Independently provisioned Ed25519 public key and authorized issuer scope."""
    key_id: str
    public_key: ed25519.Ed25519PublicKey
    source: str = "sentinel2"
    purpose: str = "kalman_state_observation"


# Verifier-only: starts strictly EMPTY.
# Never contains hardcoded private keys or HMAC shared secrets (IR04-5CC-P0-01).
_TRUSTED_PUBLIC_KEYS: Dict[str, TrustedAdmissionIssuerKey] = {}


def register_trusted_admission_public_key(
    key_id: str,
    public_key: Any,
    source: str = "sentinel2",
    purpose: str = "kalman_state_observation",
) -> None:
    """Register an independently provisioned Ed25519 public key in the verifier keyring.
    
    Verifier-only: private keys are NEVER registered or stored in the admission verifier.
    """
    if not isinstance(key_id, str) or not key_id.strip():
        raise ValueError("invalid key_id: must be non-empty string")
    clean_key_id = key_id.strip()

    if isinstance(public_key, ed25519.Ed25519PublicKey):
        pub = public_key
    elif isinstance(public_key, bytes):
        if len(public_key) == 32:
            pub = ed25519.Ed25519PublicKey.from_public_bytes(public_key)
        else:
            raise ValueError(f"Ed25519 public key bytes must be exactly 32 bytes, got {len(public_key)}")
    elif isinstance(public_key, str):
        clean_key = public_key.strip()
        if clean_key.startswith("ed25519:"):
            clean_key = clean_key[len("ed25519:"):]
        pub_bytes = bytes.fromhex(clean_key)
        if len(pub_bytes) != 32:
            raise ValueError(f"Ed25519 public key hex must decode to 32 bytes, got {len(pub_bytes)}")
        pub = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
    else:
        raise TypeError(f"unsupported public key type: {type(public_key).__name__}")

    _TRUSTED_PUBLIC_KEYS[clean_key_id] = TrustedAdmissionIssuerKey(
        key_id=clean_key_id,
        public_key=pub,
        source=str(source).lower().strip(),
        purpose=str(purpose).strip(),
    )


def register_trusted_admission_key(
    key_id: str,
    source: str,
    public_key: Any,
    purpose: str = "kalman_state_observation",
) -> None:
    """Alias for register_trusted_admission_public_key."""
    register_trusted_admission_public_key(key_id, public_key, source=source, purpose=purpose)


def clear_trusted_admission_public_keys() -> None:
    """Clear all registered admission public keys (for test hygiene)."""
    _TRUSTED_PUBLIC_KEYS.clear()


def get_trusted_admission_keyring() -> Dict[str, TrustedAdmissionIssuerKey]:
    """Return copy of trusted issuer public keys, merged with deployment env.
    
    Verifier-only: fails closed (returns empty dict) if no public keys are provisioned.
    Never exposes or derives private keys.
    """
    keyring = dict(_TRUSTED_PUBLIC_KEYS)
    raw_env = os.getenv("AKALORIS_LAYER0_ADMISSION_PUBLIC_KEYS", "").strip()
    if raw_env:
        try:
            parsed = json.loads(raw_env)
            if isinstance(parsed, dict):
                for k_id, cfg in parsed.items():
                    if isinstance(cfg, dict):
                        pub_raw = cfg.get("public_key") or cfg.get("public_key_hex") or cfg.get("public_key_b64")
                        if pub_raw:
                            if isinstance(pub_raw, str) and not pub_raw.startswith("ed25519:") and len(pub_raw) not in (64, 72):
                                try:
                                    decoded = base64.b64decode(pub_raw)
                                    if len(decoded) == 32:
                                        pub = ed25519.Ed25519PublicKey.from_public_bytes(decoded)
                                    else:
                                        continue
                                except Exception:
                                    continue
                            else:
                                if isinstance(pub_raw, str) and pub_raw.startswith("ed25519:"):
                                    pub_raw = pub_raw[len("ed25519:"):]
                                pub = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_raw))
                            src = str(cfg.get("source", "sentinel2")).lower().strip()
                            purp = str(cfg.get("purpose", "kalman_state_observation")).strip()
                            keyring[str(k_id)] = TrustedAdmissionIssuerKey(
                                key_id=str(k_id),
                                public_key=pub,
                                source=src,
                                purpose=purp,
                            )
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "key_id" in item:
                        k_id = str(item["key_id"])
                        pub_raw = item.get("public_key") or item.get("public_key_hex")
                        if pub_raw:
                            if isinstance(pub_raw, str) and pub_raw.startswith("ed25519:"):
                                pub_raw = pub_raw[len("ed25519:"):]
                            pub = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_raw))
                            src = str(item.get("source", "sentinel2")).lower().strip()
                            purp = str(item.get("purpose", "kalman_state_observation")).strip()
                            keyring[k_id] = TrustedAdmissionIssuerKey(
                                key_id=k_id,
                                public_key=pub,
                                source=src,
                                purpose=purp,
                            )
        except Exception:
            pass
    return keyring


def _canonical_normalize(value: Any) -> Any:
    """Normalize values for RFC 8785 JSON Canonicalization Scheme (JCS)."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite float in signed grant")
        if value.is_integer():
            return int(value)
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("unsigned or naive timestamp in signed grant")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise TypeError("signed grant dictionary keys must be strings")
        return {str(k): _canonical_normalize(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical_normalize(x) for x in value]
    raise TypeError(f"unsupported canonical type: {type(value).__name__}")


def canonical_grant_bytes(grant_claims: Mapping[str, Any]) -> bytes:
    """Return deterministic canonical RFC 8785 bytes for grant claims (IR04-5CC-P2-04)."""
    normalized = _canonical_normalize(grant_claims)
    return rfc8785.dumps(normalized)


def _canonical_bytes(payload: Any) -> bytes:
    """Backward-compatible alias for canonical_grant_bytes."""
    return canonical_grant_bytes(payload)


def compute_scene_asset_sha256(scene: Any) -> Optional[str]:
    """Compute deterministic SHA-256 over exact physical scene asset bytes/arrays."""
    h = hashlib.sha256()

    # 1. Raw byte payloads
    for attr in ("asset_bytes", "raw_asset_bytes", "source_bytes"):
        val = getattr(scene, attr, None)
        if isinstance(val, (bytes, bytearray)) and len(val) > 0:
            h.update(val)
            return h.hexdigest()

    # 2. Multi-band array payloads
    bands = getattr(scene, "bands", None)
    if isinstance(bands, Mapping) and bands:
        has_arrays = False
        for b_name in sorted(bands.keys()):
            arr = bands[b_name]
            h.update(str(b_name).encode("utf-8"))
            if hasattr(arr, "shape") and hasattr(arr, "dtype") and hasattr(arr, "tobytes"):
                has_arrays = True
                h.update(str(arr.shape).encode("utf-8"))
                h.update(str(arr.dtype).encode("utf-8"))
                h.update(arr.tobytes())
            elif isinstance(arr, (bytes, bytearray)):
                has_arrays = True
                h.update(arr)
            elif hasattr(arr, "tobytes"):
                has_arrays = True
                h.update(arr.tobytes())
            elif isinstance(arr, (int, float, bool, str)):
                h.update(str(arr).encode("utf-8"))
        if has_arrays:
            return h.hexdigest()

    # 3. Single raster array
    for attr in ("raster", "raster_data", "data"):
        arr = getattr(scene, attr, None)
        if arr is not None and hasattr(arr, "shape") and hasattr(arr, "dtype") and hasattr(arr, "tobytes"):
            h.update(str(arr.shape).encode("utf-8"))
            h.update(str(arr.dtype).encode("utf-8"))
            h.update(arr.tobytes())
            return h.hexdigest()

    return None


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
    canonical = canonical_grant_bytes(grant)
    sig_bytes = private_key.sign(canonical)
    sig_str = "ed25519:" + sig_bytes.hex()
    return {"grant": grant, "signature": sig_str, "mac": sig_str}


def verify_scene_admission_receipt(
    receipt: Any,
    *,
    scene: Any,
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    geometry_sha256: str,
    operator_sha256: str,
    calibrated_operator_sha256: Optional[str] = None,
    valid_time: str,
    committed_at: str,
    trusted_keyring: Optional[Mapping[str, TrustedAdmissionIssuerKey]] = None,
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """Verify signed, immutable provider/Layer0 admission receipt against trusted Ed25519 public key.

    Binds:
    - tenant_id, farm_id, plot_id, geometry_sha256
    - exact asset SHA-256 (computed over physical array/payload bytes)
    - operator_sha256 and calibrated_operator_sha256
    - observation_valid_time and committed_at
    - issuer scope: authorized source/sensor and purpose
    - Ed25519 cryptographic signature over canonical RFC 8785 JCS bytes
    """
    if not isinstance(receipt, Mapping):
        return False, "malformed_receipt_structure"
    grant = receipt.get("grant")
    sig_str = receipt.get("signature") or receipt.get("mac")
    if not isinstance(grant, Mapping) or not isinstance(sig_str, str):
        return False, "malformed_grant_or_signature"

    clean_sig = sig_str.strip()
    if clean_sig.startswith("ed25519:"):
        clean_sig = clean_sig[len("ed25519:"):]
    try:
        sig_bytes = bytes.fromhex(clean_sig)
        if len(sig_bytes) != 64:
            return False, "malformed_signature_length"
    except (ValueError, TypeError):
        return False, "invalid_signature_hex"

    keyring = trusted_keyring if trusted_keyring is not None else get_trusted_admission_keyring()
    if not keyring:
        return False, "no_trusted_public_keys_configured"

    key_id = grant.get("key_id")
    if not key_id or key_id not in keyring:
        return False, "untrusted_or_unknown_issuer_key"
    trusted_key = keyring[key_id]

    try:
        canonical_bytes = canonical_grant_bytes(grant)
        trusted_key.public_key.verify(sig_bytes, canonical_bytes)
    except InvalidSignature:
        return False, "forged_admission_signature"
    except Exception as exc:
        return False, f"canonical_verification_error:{exc}"

    domain = grant.get("domain")
    if domain not in ALLOWED_ADMISSION_DOMAINS:
        return False, "unauthorized_admission_domain"

    # IR04-5CC-P1-03: Verify purpose
    grant_purpose = grant.get("purpose")
    if grant_purpose not in ALLOWED_ADMISSION_PURPOSES:
        return False, "wrong_admission_purpose"
    if trusted_key.purpose and trusted_key.purpose not in ("*", "any") and grant_purpose != trusted_key.purpose:
        return False, "wrong_admission_purpose"

    # IR04-5CC-P1-03: Verify source & cross-sensor enforcement
    grant_source = str(grant.get("source") or "").lower().strip()
    scene_sensor = str(getattr(scene, "sensor", "") or "").lower().strip()
    s2_variants = ("s2", "sentinel2", "sentinel-2", "sentinel_2", "s2_msi")
    s1_variants = ("s1", "sentinel1", "sentinel-1", "sentinel_1", "s1_sar")

    grant_norm = "sentinel2" if grant_source in s2_variants else ("sentinel1" if grant_source in s1_variants else grant_source)
    scene_norm = "sentinel2" if scene_sensor in s2_variants else ("sentinel1" if scene_sensor in s1_variants else scene_sensor)

    if grant_norm != scene_norm:
        return False, "cross_sensor_admission_denied"

    if trusted_key.source and trusted_key.source not in ("*", "any"):
        key_source_norm = "sentinel2" if trusted_key.source in s2_variants else ("sentinel1" if trusted_key.source in s1_variants else trusted_key.source)
        if key_source_norm != grant_norm:
            return False, "issuer_source_scope_mismatch"

    # Verify namespace scope
    if grant.get("tenant_id") != str(tenant_id):
        return False, "foreign_tenant_scope"
    if grant.get("farm_id") and grant.get("farm_id") != str(farm_id):
        return False, "foreign_farm_scope"
    if grant.get("plot_id") != str(plot_id):
        return False, "foreign_plot_scope"
    grant_geom = grant.get("geometry_hash") or grant.get("geometry_sha256")
    if grant_geom != str(geometry_sha256):
        return False, "foreign_geometry_digest"

    # Verify exact asset content hash
    computed_asset_sha = compute_scene_asset_sha256(scene)
    if not computed_asset_sha or grant.get("asset_sha256") != computed_asset_sha:
        return False, "swapped_or_unverified_asset_bytes"

    # Verify operator binding
    if grant.get("operator_sha256") != operator_sha256:
        return False, "operator_digest_mismatch"
    if calibrated_operator_sha256 and grant.get("calibrated_operator_sha256"):
        if grant.get("calibrated_operator_sha256") != calibrated_operator_sha256:
            return False, "calibrated_operator_mismatch"

    # Verify timestamps
    if grant.get("observation_valid_time") != valid_time:
        return False, "observation_time_mismatch"
    if grant.get("committed_at") != committed_at:
        return False, "committed_time_mismatch"

    # Expiry
    check_time = now or datetime.now(timezone.utc)
    exp = grant.get("expires_at")
    if exp:
        exp_dt = _ensure_utc_iso(exp)
        if exp_dt and datetime.fromisoformat(exp_dt) <= check_time:
            return False, "expired_admission_receipt"

    return True, "verified_positive_admission_grant"


def verify_bitemporal_replay_receipt(
    receipt: Any,
    *,
    tenant_id: str,
    plot_id: str,
    geometry_hash: str,
    journal_watermark: Optional[str] = None,
) -> Tuple[bool, str, Optional[str]]:
    """Verify journal authority of bitemporal replay receipt at the engine boundary (IR04-5CC-P1-02).

    Returns (is_valid, reason, validated_knowledge_cutoff).

    Verifies:
    1. Structure and schema (contract_version == 'canonical_bitemporal_replay_receipt_v1')
    2. Deterministic replay mode ('bitemporal_deterministic_v1') and status ('replayed')
    3. Namespace and geometry binding: tenant_id, plot_id, geometry_hash must match query
    4. Selected evidence set digest integrity: recomputes SHA-256 over canonical sorted
       selected_evidence_set and compares against evidence_set_digest
    5. Knowledge cutoff K authority:
       - knowledge_cutoff_time must be valid UTC ISO string
       - No event in selected_evidence_set may have committed_at or effective_at strictly
         greater than K (detects forged cutoff or future bitemporal leakage)
       - If journal_watermark is provided, K cannot be in the uncommitted future (K <= watermark)
    """
    if not isinstance(receipt, Mapping):
        return False, "missing_or_non_mapping_receipt", None

    contract_ver = receipt.get("contract_version")
    if contract_ver != "canonical_bitemporal_replay_receipt_v1":
        return False, f"unsupported_contract_version:{contract_ver}", None

    if receipt.get("replay_mode") != "bitemporal_deterministic_v1":
        return False, "unsupported_replay_mode", None

    if receipt.get("status") != "replayed":
        return False, "receipt_not_replayed", None

    if str(receipt.get("tenant_id") or "") != str(tenant_id):
        return False, "foreign_tenant_receipt", None

    if str(receipt.get("plot_id") or "") != str(plot_id):
        return False, "foreign_plot_receipt", None

    rec_geom = str(receipt.get("geometry_hash") or "")
    if rec_geom != str(geometry_hash):
        return False, "foreign_geometry_receipt", None

    query_params = receipt.get("query_parameters")
    if not isinstance(query_params, Mapping):
        return False, "missing_query_parameters", None

    k_str = (
        query_params.get("knowledge_cutoff_time")
        or receipt.get("knowledge_watermark")
        or query_params.get("knowledge_cutoff_K")
    )
    if not k_str or not isinstance(k_str, str):
        return False, "missing_knowledge_cutoff_in_receipt", None

    k_iso = _ensure_utc_iso(k_str)
    if not k_iso:
        return False, "invalid_receipt_knowledge_cutoff_utc", None

    k_dt = datetime.fromisoformat(k_iso.replace("Z", "+00:00"))

    # Check watermark if present
    if journal_watermark:
        wm_iso = _ensure_utc_iso(journal_watermark)
        if wm_iso:
            wm_dt = datetime.fromisoformat(wm_iso.replace("Z", "+00:00"))
            if k_dt > wm_dt:
                return False, "forged_cutoff_exceeds_journal_watermark", None

    # Evidence set digest verification
    ev_digest = receipt.get("evidence_set_digest")
    if not ev_digest or not isinstance(ev_digest, str):
        return False, "missing_evidence_set_digest", None

    ev_set = receipt.get("selected_evidence_set")
    if not isinstance(ev_set, Sequence):
        return False, "missing_or_invalid_evidence_set", None

    try:
        sorted_ev = sorted(
            list(ev_set),
            key=lambda item: (str(item.get("event_type")), str(item.get("event_id"))),
        )
        recomputed_digest = hashlib.sha256(
            json.dumps(sorted_ev, sort_keys=True).encode("utf-8")
        ).hexdigest()
        expected_digest_str = f"sha256:{recomputed_digest}"
        if ev_digest != expected_digest_str and ev_digest != recomputed_digest:
            return False, "forged_evidence_set_digest", None
    except Exception as exc:
        return False, f"evidence_digest_computation_error:{exc}", None

    # Check bitemporal leakage: no event in evidence set may be committed or effective after K
    for ev in ev_set:
        if isinstance(ev, Mapping):
            for t_field in ("committed_at", "journal_committed_at", "effective_at"):
                t_val = ev.get(t_field)
                if t_val:
                    t_iso = _ensure_utc_iso(t_val)
                    if t_iso:
                        t_dt = datetime.fromisoformat(t_iso.replace("Z", "+00:00"))
                        if t_dt > k_dt:
                            return False, f"bitemporal_leakage_event_after_cutoff:{t_field}", None

    return True, "verified_journal_authority", k_iso


def _ensure_utc_iso(dt: Any) -> Optional[str]:
    """Convert datetime or ISO string to standard UTC ISO-8601 string.

    Prohibits naive timestamp timezone inference: any string or datetime
    without an explicit timezone offset ('Z', '+', '-') is rejected.
    """
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            # Explicitly reject naive datetime (no inference)
            return None
        return dt.astimezone(timezone.utc).isoformat()
    if isinstance(dt, str):
        val = dt.strip()
        if not val:
            return None
        # Must have an explicit timezone indicator: 'Z' or '+HH:MM' or '-HH:MM'
        if not (val.endswith("Z") or ("+" in val[10:]) or ("-" in val[10:] and len(val) > 19)):
            return None
        try:
            parsed = datetime.fromisoformat(val.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            return None
    return None


def _extract_bbox(scene: Any) -> Optional[Tuple[float, float, float, float]]:
    """Extract (minx, miny, maxx, maxy) in scene coordinate space."""
    bounds = getattr(scene, "bounds", None)
    if bounds is not None and isinstance(bounds, (list, tuple)) and len(bounds) == 4:
        try:
            minx, miny, maxx, maxy = (float(v) for v in bounds)
            if minx < maxx and miny < maxy and all(math.isfinite(v) for v in (minx, miny, maxx, maxy)):
                return (minx, miny, maxx, maxy)
        except (ValueError, TypeError):
            pass

    transform = getattr(scene, "transform", None)
    width = getattr(scene, "width", None)
    height = getattr(scene, "height", None)
    if transform and width and height and isinstance(transform, (list, tuple)) and len(transform) >= 6:
        try:
            w = int(width)
            h = int(height)
            if w > 0 and h > 0:
                x0, xstep, _, y0, _, ystep = (float(transform[i]) for i in range(6))
                x1 = x0 + xstep * w
                y1 = y0 + ystep * h
                minx, maxx = min(x0, x1), max(x0, x1)
                miny, maxy = min(y0, y1), max(y0, y1)
                if minx < maxx and miny < maxy and all(math.isfinite(v) for v in (minx, miny, maxx, maxy)):
                    return (minx, miny, maxx, maxy)
        except (ValueError, TypeError):
            pass
    return None


def adapt_scene_to_footprint(
    scene: Any,
    *,
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    geometry_sha256: str,
    target_crs: str,
    committed_at: Optional[str] = None,
    operator: Optional[Any] = None,
    require_operator_binding: bool = False,
) -> Optional[EvidenceFootprint]:
    """Translate an admitted scene into an EvidenceFootprint or fail closed (return None).

    Strict admission requirements:
    1. Tenant/farm/plot namespace and geometry digest must match.
    2. Scene must be production-usable or scientifically admitted (not test/diagnostic-only).
    3. Scene CRS must match target projected metric CRS.
    4. Valid non-degenerate bounding box and UTC timestamp required.
    5. When operator is supplied or required, binds to genuine H_t matrix digest and PSF model.
    """
    if not all((tenant_id, farm_id, plot_id, geometry_sha256, target_crs)):
        return None
    if not _SHA256_RE.fullmatch(geometry_sha256):
        return None

    # Check scene admission / reality attributes (HNEW-05, C752-P1-02)
    if getattr(scene, "test_override", False):
        return None
    if getattr(scene, "diagnostic_only", False):
        return None

    is_prod_usable = bool(
        getattr(scene, "production_usable", False)
        or getattr(scene, "scientifically_admitted", False)
    )
    if not is_prod_usable:
        return None

    # Namespace match: mandatory in production/operator-binding mode (C752-P1-02)
    scene_tenant = getattr(scene, "tenant_id", None)
    scene_farm = getattr(scene, "farm_id", None)
    scene_plot = getattr(scene, "plot_id", None)
    scene_geom = getattr(scene, "geometry_sha256", None) or getattr(scene, "geometry_hash", None)

    if require_operator_binding:
        # Mandatory namespace & geometry identity on scene
        if not all((scene_tenant, scene_farm, scene_plot, scene_geom)):
            return None
        if not _SHA256_RE.fullmatch(str(scene_geom)):
            return None

    if scene_tenant and str(scene_tenant) != str(tenant_id):
        return None
    if scene_farm and str(scene_farm) != str(farm_id):
        return None
    if scene_plot and str(scene_plot) != str(plot_id):
        return None
    if scene_geom and str(scene_geom) != str(geometry_sha256):
        return None

    if require_operator_binding:
        # Positive signed admission & verified provider binding required (C752-P1-02, IR04-665-01)
        # Syntactic hashes, metadata flags, or provider product IDs alone are NOT authority.
        if getattr(scene, "forged_asset_hash", False) or getattr(scene, "unverified_asset_hash", False):
            return None

    # CRS match: scene must match the target projected metric grid CRS
    scene_crs = str(getattr(scene, "crs", "") or "").upper()
    if not scene_crs or scene_crs != str(target_crs).upper():
        return None
    if scene_crs in ("EPSG:4326", "OGC:CRS84", "CRS84", "WGS84"):
        return None

    # Bounding box
    bbox = _extract_bbox(scene)
    if bbox is None:
        return None

    # Observation ID
    scene_id = str(getattr(scene, "scene_id", "") or "").strip()
    if not scene_id:
        return None

    # Acquisition time -> valid_time
    acq_time = (
        getattr(scene, "acquisition_time", None)
        or getattr(scene, "timestamp", None)
        or getattr(scene, "date", None)
    )
    valid_time = _ensure_utc_iso(acq_time)
    if not valid_time:
        return None

    # Bitemporal commitment extraction (HNEW-02, C752-P1-01)
    scene_comm = (
        getattr(scene, "committed_at", None)
        or getattr(scene, "journal_committed_at", None)
        or getattr(scene, "journal_entry_time", None)
    )
    if require_operator_binding and not scene_comm:
        # Mandatory genuine journal commitment timestamp in operator binding mode
        return None
    # Caller committed_at is only used in non-operator-binding mode or if matching;
    # in operator binding mode, native journal commitment is strictly preserved.
    # Engine must pass committed_at=None so query K never overwrites scene commitment.
    commit_input = scene_comm if require_operator_binding else (committed_at if committed_at is not None else scene_comm)
    commit_iso = _ensure_utc_iso(commit_input)
    if not commit_iso:
        # Prohibits ungrounded temporal commitment: never fall back to valid_time
        return None

    # Sensor classification
    sensor_raw = str(getattr(scene, "sensor", "") or "").upper()
    if sensor_raw in ("S2", "SENTINEL-2", "SENTINEL_2", "S2_MSI"):
        sensor = "S2"
        supported_states = S2_OPTICAL_STATES
        cloud_frac = float(getattr(scene, "cloud_fraction", 0.0) or 0.0)
        # When per-cell valid_support or operator valid support mask is provided,
        # cell validity is enforced cell-by-cell. Observability for unmasked cells
        # is determined by radiometric QA score (or 0.95), not penalized by whole-scene clouds.
        if (hasattr(scene, "valid_support") and scene.valid_support is not None) or (
            operator is not None and getattr(operator, "valid_support_hash", "")
        ):
            qa = getattr(scene, "qa_score", None)
            observability = float(qa) if qa is not None and 0 <= float(qa) <= 1 else 0.95
        else:
            observability = max(0.0, min(1.0, 1.0 - cloud_frac))
    elif sensor_raw in ("S1", "SENTINEL-1", "SENTINEL_1", "S1_SAR"):
        sensor = "S1"
        supported_states = S1_SAR_STATES
        qa = getattr(scene, "qa_score", None)
        observability = float(qa) if qa is not None and 0 <= float(qa) <= 1 else 0.85
    else:
        # Unknown or uncalibrated sensor: cannot confer calibrated local footprint
        return None

    band = str(getattr(scene, "band", "") or (getattr(operator, "band", "") if operator else "") or "").upper()
    if not band and sensor == "S2":
        bands_dict = getattr(scene, "bands", None)
        if isinstance(bands_dict, dict) and bands_dict:
            b_keys = {str(k).upper() for k in bands_dict.keys()}
            s2_20m = {"B05", "B06", "B07", "B8A", "B11", "B12"}
            s2_60m = {"B01", "B09", "B10"}
            s2_10m = {"B02", "B03", "B04", "B08"}
            if b_keys & s2_20m:
                band = "B05"
            elif b_keys & s2_60m:
                band = "B01"
            elif b_keys & s2_10m:
                band = "B04"
            else:
                band = "B05"
        else:
            tf = getattr(scene, "transform", None)
            if tf and len(tf) >= 6 and max(abs(float(tf[1])), abs(float(tf[5]))) > 12.0:
                band = "B05"
            else:
                band = "B04"

    # PSF & Resolution calibration
    if operator is not None:
        blur_sigma = float(getattr(operator, "blur_sigma_m", 0.0) or 0.0)
        if blur_sigma > 0:
            psf_model = get_psf_model(sensor, band=band, custom_sigma_m=blur_sigma)
        else:
            psf_model = get_psf_model(sensor, band=band)
        psf_fwhm = round(psf_model.fwhm_m, 4)

        src_res = float(getattr(operator, "source_resolution_m", 0.0) or 0.0)
        if src_res > 0:
            if sensor == "S2" and band in ("B05", "B06", "B07", "B8A", "B11", "B12"):
                native_res = max(src_res, 20.0)
            else:
                native_res = src_res
        elif sensor == "S2":
            native_res = 20.0 if band in ("B05", "B06", "B07", "B8A", "B11", "B12") else 10.0
        else:
            native_res = 20.0
    else:
        if require_operator_binding:
            return None
        psf_model = get_psf_model(sensor, band=band)
        psf_fwhm = round(psf_model.fwhm_m, 4)
        if hasattr(scene, "psf_fwhm_m") and scene.psf_fwhm_m is not None:
            psf_fwhm = float(scene.psf_fwhm_m)
        if hasattr(scene, "native_resolution_m") and scene.native_resolution_m is not None:
            native_res = float(scene.native_resolution_m)
        elif sensor == "S2":
            native_res = 20.0 if band in ("B05", "B06", "B07", "B8A", "B11", "B12") else 10.0
        else:
            native_res = 20.0

    valid_cell_indices: Optional[Tuple[int, ...]] = None
    valid_support_hash: Optional[str] = None

    if operator is not None:
        if getattr(operator, "scene_id", "") and str(operator.scene_id) != scene_id:
            return None
        op_target_crs = str(getattr(operator, "target_crs", "") or "").upper()
        if op_target_crs and op_target_crs != str(target_crs).upper():
            return None
        op_source_crs = str(getattr(operator, "source_crs", "") or "").upper()
        if op_source_crs and op_source_crs != scene_crs:
            return None

        h_mat = getattr(operator, "H_matrix", None)
        matrix_digest = compute_h_matrix_digest(h_mat)
        if not matrix_digest or not _SHA256_RE.fullmatch(matrix_digest):
            return None
        op_sha = matrix_digest

        if h_mat is not None and hasattr(h_mat, "indices"):
            valid_cell_indices = tuple(sorted(set(int(idx) for idx in h_mat.indices)))

        op_valid_hash = getattr(operator, "valid_support_hash", "") or ""
        if op_valid_hash:
            valid_support_hash = op_valid_hash
            if hasattr(scene, "valid_support") and scene.valid_support is not None:
                supp_str = str(scene.valid_support).encode()
                actual_supp_hash = hashlib.sha256(supp_str).hexdigest()
                if op_valid_hash != actual_supp_hash:
                    return None

        op_id = getattr(operator, "operator_id", "") or scene_id
        cal_op_sha = hashlib.sha256(
            f"{op_id}:{matrix_digest}:{psf_fwhm:.4f}:{native_res}".encode()
        ).hexdigest()
    else:
        if require_operator_binding:
            return None
        op_sha = getattr(scene, "operator_sha256", None) or (S2_OPERATOR_SHA256 if sensor == "S2" else S1_OPERATOR_SHA256)
        cal_op_sha = getattr(scene, "calibrated_operator_sha256", None) or (S2_CALIBRATED_OPERATOR_SHA256 if sensor == "S2" else S1_CALIBRATED_OPERATOR_SHA256)
        # HNEW-04: Without bound operator, scene-pixel indices must NOT be mapped to target graph cells
        valid_cell_indices = None

    # Deterministic source content hash and signed admission verification (HNEW-01, IR04-665-01)
    computed_asset_sha = compute_scene_asset_sha256(scene)

    if require_operator_binding:
        # IR04-665-01: Positive Signed Source & Asset Admission Validation
        # 1. Physical asset arrays/bytes required
        if not computed_asset_sha or not _SHA256_RE.fullmatch(computed_asset_sha):
            return None

        # 2. Swapped asset hash protection: if scene claims content_hash, it must match exact bytes
        scene_content_hash = (
            getattr(scene, "content_hash", None)
            or getattr(scene, "source_asset_sha256", None)
            or getattr(scene, "sha256", None)
        )
        if scene_content_hash and str(scene_content_hash).lower() != computed_asset_sha.lower():
            return None

        # 3. Signed admission receipt required & verified against trusted key
        binding_proof = getattr(scene, "binding_proof", None)
        admission_receipt = getattr(scene, "admission_receipt", None) or (
            binding_proof.get("admission_receipt") if isinstance(binding_proof, dict) else None
        )
        if not admission_receipt or not isinstance(admission_receipt, dict):
            return None

        valid_receipt, _reason = verify_scene_admission_receipt(
            admission_receipt,
            scene=scene,
            tenant_id=tenant_id,
            farm_id=farm_id,
            plot_id=plot_id,
            geometry_sha256=geometry_sha256,
            operator_sha256=op_sha,
            calibrated_operator_sha256=cal_op_sha,
            valid_time=valid_time,
            committed_at=commit_iso,
        )
        if not valid_receipt:
            return None

        src_hash = computed_asset_sha
    else:
        src_hash = (
            computed_asset_sha
            or getattr(scene, "content_hash", None)
            or getattr(scene, "sha256", None)
            or getattr(scene, "source_asset_sha256", None)
            or getattr(scene, "immutable_source_sha256", None)
            or (getattr(operator, "source_sha256", None) if operator else None)
        )
        if not src_hash or not isinstance(src_hash, str) or not _SHA256_RE.fullmatch(src_hash):
            prov_ref = getattr(scene, "provider_product_id", "") or getattr(scene, "provenance_ref", "") or scene_id
            src_hash = hashlib.sha256(f"{sensor_raw}:{scene_id}:{prov_ref}:{valid_time}".encode()).hexdigest()

    try:
        return EvidenceFootprint(
            observation_id=scene_id,
            source_sha256=src_hash,
            operator_sha256=op_sha,
            tenant_id=tenant_id,
            farm_id=farm_id,
            plot_id=plot_id,
            geometry_sha256=geometry_sha256,
            observation_valid_time=valid_time,
            committed_at=commit_iso,
            supported_states=supported_states,
            bbox=bbox,
            crs=scene_crs,
            native_resolution_m=native_res,
            psf_fwhm_m=psf_fwhm,
            observability=observability,
            calibrated_operator_sha256=cal_op_sha,
            classification="physical",
            nodata=False,
            independent_holdout_sha256=None,
            valid_cell_indices=valid_cell_indices,
            valid_support_hash=valid_support_hash,
        )
    except (SpatialSupportViolation, ValueError, TypeError):
        return None


def adapt_scenes_to_footprints(
    scenes: Sequence[Any],
    *,
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    geometry_sha256: str,
    target_crs: str,
    committed_at: Optional[str] = None,
    operator_bundle: Optional[Any] = None,
    operators: Optional[Sequence[Any]] = None,
    require_operator_binding: bool = False,
) -> Tuple[EvidenceFootprint, ...]:
    """Translate a sequence of scenes into EvidenceFootprint instances.

    Filters out scenes that fail admission, CRS match, or namespace boundaries.
    Binds post-selection operators when provided via operator_bundle or operators.
    """
    ops_list = []
    if operator_bundle is not None:
        ops_list.extend(getattr(operator_bundle, "operators", ()) or ())
    if operators:
        ops_list.extend(operators)
    op_map = {getattr(op, "scene_id", ""): op for op in ops_list if getattr(op, "scene_id", "")}

    footprints: List[EvidenceFootprint] = []
    seen_ids = set()
    for scene in scenes:
        s_id = str(getattr(scene, "scene_id", "") or "").strip()
        matched_op = op_map.get(s_id)
        fp = adapt_scene_to_footprint(
            scene,
            tenant_id=tenant_id,
            farm_id=farm_id,
            plot_id=plot_id,
            geometry_sha256=geometry_sha256,
            target_crs=target_crs,
            committed_at=committed_at,
            operator=matched_op,
            require_operator_binding=require_operator_binding,
        )
        if fp is not None and fp.observation_id not in seen_ids:
            footprints.append(fp)
            seen_ids.add(fp.observation_id)
    return tuple(footprints)
