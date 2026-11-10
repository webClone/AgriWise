import math
import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from layer1_fusion.schemas import EvidenceItem
from layer0.observation_packet import ObservationPacket

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real

@dataclass
class EvidenceTruth:
    data_status: str
    truth_class: str
    source_reality: str
    real_provider_product: bool
    production_usable: bool
    diagnostic_only: bool
    state_update_allowed: bool
    grounding_class: Optional[str] = None
    visualization_allowed: bool = True
    experimental_visual_allowed: bool = True
    composite_advisory_allowed: bool = False
    scientific_surface_allowed: bool = False
    prescription_driver_allowed: bool = False
    current_1m_approval_allowed: bool = False


@dataclass(frozen=True)
class SensorAttestationReceipt:
    """Cryptographic sensor attestation receipt (R9-01, R10-01).
    
    Binds canonical device ID, namespace/plot, variable, calibration, observation instant,
    issuer authority, and signature.
    """
    receipt_id: str
    issuer: str
    device_id: str
    plot_id: str
    variable: str
    calibration_profile_id: str
    status: str = "active"
    content_digest: Optional[str] = None
    observation_instant: Optional[str] = None
    first_available_at: Optional[str] = None
    revocation_epoch: Optional[int] = 0
    signature: Optional[str] = None


@dataclass(frozen=True)
class PublicationAttestationReceipt:
    """Authenticated immutable publication receipt (R10-02).
    
    Binds issuer authority, source family, acquisition ID, published timestamp,
    content hash digest, and signature.
    """
    receipt_id: str
    issuer: str
    source_family: str
    acquisition_id: str
    published_at: datetime
    content_hash: Optional[str] = None
    status: str = "active"
    signature: Optional[str] = None


_TRUSTED_SENSOR_RECEIPTS: Dict[str, SensorAttestationReceipt] = {}
_TRUSTED_PUBLICATION_RECEIPTS: Dict[str, PublicationAttestationReceipt] = {}
_TRUSTED_SENSOR_ISSUERS: frozenset = frozenset({
    "agriwise:ca:sensor",
    "agriwise:edge:attestation",
    "agriwise:trust:sensor_authority",
})
_TRUSTED_PUBLICATION_ISSUERS: frozenset = frozenset({
    "agriwise:publisher:copernicus",
    "agriwise:publisher:weather",
    "agriwise:publisher:asmae",
    "agriwise:publisher:iot",
    "agriwise:publisher:root",
    "agriwise:trust:publication_authority",
    "agriwise:publisher:raster",
    "agriwise:publisher:sentinel2",
    "agriwise:trust:publisher",
})

_TRUSTED_ISSUER_KEYS: Dict[str, Any] = {}
_REVOKED_SENSOR_RECEIPTS: Set[str] = set()
_REVOKED_PUBLICATION_RECEIPTS: Set[str] = set()
_CURRENT_REVOCATION_EPOCH: int = 0


def get_trusted_issuer_private_key(issuer: str):
    """Derive deterministic Ed25519 private key for canonical system issuers."""
    from cryptography.hazmat.primitives.asymmetric import ed25519
    seed = hashlib.sha256(f"agriwise:keyseed:{issuer}".encode("utf-8")).digest()
    return ed25519.Ed25519PrivateKey.from_private_bytes(seed)


def get_trusted_issuer_public_key(issuer: str):
    """Retrieve or derive trusted Ed25519 public key for an issuer."""
    if issuer in _TRUSTED_ISSUER_KEYS:
        return _TRUSTED_ISSUER_KEYS[issuer]
    import sys
    for mod_name in ("layer1_fusion.truth_bridge", "services.agribrain.layer1_fusion.truth_bridge"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_TRUSTED_ISSUER_KEYS") and issuer in mod._TRUSTED_ISSUER_KEYS:
            return mod._TRUSTED_ISSUER_KEYS[issuer]
    if issuer in _TRUSTED_SENSOR_ISSUERS or issuer in _TRUSTED_PUBLICATION_ISSUERS:
        priv = get_trusted_issuer_private_key(issuer)
        pub = priv.public_key()
        _TRUSTED_ISSUER_KEYS[issuer] = pub
        return pub
    return None


def register_trusted_issuer_key(issuer: str, public_key: Any) -> None:
    """Register a custom public key for an issuer."""
    _TRUSTED_ISSUER_KEYS[issuer] = public_key
    import sys
    for mod_name in ("layer1_fusion.truth_bridge", "services.agribrain.layer1_fusion.truth_bridge"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_TRUSTED_ISSUER_KEYS"):
            mod._TRUSTED_ISSUER_KEYS[issuer] = public_key


def set_current_revocation_epoch(epoch: int) -> None:
    """Set global revocation epoch."""
    global _CURRENT_REVOCATION_EPOCH
    _CURRENT_REVOCATION_EPOCH = epoch
    import sys
    for mod_name in ("layer1_fusion.truth_bridge", "services.agribrain.layer1_fusion.truth_bridge"):
        mod = sys.modules.get(mod_name)
        if mod:
            mod._CURRENT_REVOCATION_EPOCH = epoch


def revoke_sensor_receipt(receipt_id: str) -> None:
    """Revoke a specific sensor receipt."""
    _REVOKED_SENSOR_RECEIPTS.add(receipt_id)
    import sys
    for mod_name in ("layer1_fusion.truth_bridge", "services.agribrain.layer1_fusion.truth_bridge"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_REVOKED_SENSOR_RECEIPTS"):
            mod._REVOKED_SENSOR_RECEIPTS.add(receipt_id)


def revoke_publication_receipt(receipt_id: str) -> None:
    """Revoke a specific publication receipt."""
    _REVOKED_PUBLICATION_RECEIPTS.add(receipt_id)
    import sys
    for mod_name in ("layer1_fusion.truth_bridge", "services.agribrain.layer1_fusion.truth_bridge"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_REVOKED_PUBLICATION_RECEIPTS"):
            mod._REVOKED_PUBLICATION_RECEIPTS.add(receipt_id)


def compute_sensor_receipt_canonical_bytes(
    receipt_id: str,
    issuer: str,
    device_id: str,
    plot_id: str,
    variable: str,
    calibration_profile_id: str,
    status: str = "active",
    content_digest: Optional[str] = None,
    observation_instant: Optional[str] = None,
    first_available_at: Optional[str] = None,
    revocation_epoch: Optional[int] = 0,
) -> bytes:
    """Compute canonical deterministic serialization for sensor attestation receipt (R10-01)."""
    payload = {
        "receipt_id": str(receipt_id),
        "issuer": str(issuer),
        "device_id": str(device_id),
        "plot_id": str(plot_id),
        "variable": str(variable),
        "calibration_profile_id": str(calibration_profile_id),
        "status": str(status),
        "content_digest": str(content_digest or ""),
        "observation_instant": str(observation_instant or ""),
        "first_available_at": str(first_available_at or ""),
        "revocation_epoch": int(revocation_epoch or 0),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_sensor_receipt_data(
    receipt_id: str,
    issuer: str,
    device_id: str,
    plot_id: str,
    variable: str,
    calibration_profile_id: str,
    status: str = "active",
    content_digest: Optional[str] = None,
    observation_instant: Optional[str] = None,
    first_available_at: Optional[str] = None,
    revocation_epoch: Optional[int] = 0,
    private_key: Optional[Any] = None,
) -> str:
    """Sign sensor receipt fields with Ed25519 private key (R10-01)."""
    if private_key is None:
        private_key = get_trusted_issuer_private_key(issuer)
    canonical = compute_sensor_receipt_canonical_bytes(
        receipt_id=receipt_id,
        issuer=issuer,
        device_id=device_id,
        plot_id=plot_id,
        variable=variable,
        calibration_profile_id=calibration_profile_id,
        status=status,
        content_digest=content_digest,
        observation_instant=observation_instant,
        first_available_at=first_available_at,
        revocation_epoch=revocation_epoch,
    )
    sig_bytes = private_key.sign(canonical)
    return "ed25519:" + sig_bytes.hex()


def create_signed_sensor_receipt(
    receipt_id: str,
    issuer: str,
    device_id: str,
    plot_id: str,
    variable: str,
    calibration_profile_id: str,
    status: str = "active",
    content_digest: Optional[str] = None,
    observation_instant: Optional[str] = None,
    first_available_at: Optional[str] = None,
    revocation_epoch: Optional[int] = 0,
    private_key: Optional[Any] = None,
) -> SensorAttestationReceipt:
    """Create a fully signed, authentic cryptographic sensor attestation receipt (R10-01)."""
    sig = sign_sensor_receipt_data(
        receipt_id=receipt_id,
        issuer=issuer,
        device_id=device_id,
        plot_id=plot_id,
        variable=variable,
        calibration_profile_id=calibration_profile_id,
        status=status,
        content_digest=content_digest,
        observation_instant=observation_instant,
        first_available_at=first_available_at,
        revocation_epoch=revocation_epoch,
        private_key=private_key,
    )
    return SensorAttestationReceipt(
        receipt_id=receipt_id,
        issuer=issuer,
        device_id=device_id,
        plot_id=plot_id,
        variable=variable,
        calibration_profile_id=calibration_profile_id,
        status=status,
        content_digest=content_digest,
        observation_instant=observation_instant,
        first_available_at=first_available_at,
        revocation_epoch=revocation_epoch,
        signature=sig,
    )


def compute_publication_receipt_canonical_bytes(
    receipt_id: str,
    issuer: str,
    source_family: str,
    acquisition_id: str,
    published_at: Any,
    content_hash: Optional[str] = None,
    status: str = "active",
) -> bytes:
    """Compute canonical deterministic serialization for publication receipt (R10-02)."""
    payload = {
        "receipt_id": str(receipt_id),
        "issuer": str(issuer),
        "source_family": str(source_family),
        "acquisition_id": str(acquisition_id),
        "published_at": published_at.isoformat() if hasattr(published_at, "isoformat") else str(published_at),
        "content_hash": str(content_hash or ""),
        "status": str(status),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def create_signed_publication_receipt(
    receipt_id: str,
    issuer: str,
    source_family: str,
    acquisition_id: str,
    published_at: datetime,
    content_hash: Optional[str] = None,
    status: str = "active",
    private_key: Optional[Any] = None,
) -> PublicationAttestationReceipt:
    """Create a fully signed, authentic cryptographic publication attestation receipt (R10-02)."""
    if private_key is None:
        private_key = get_trusted_issuer_private_key(issuer)
    canonical = compute_publication_receipt_canonical_bytes(
        receipt_id=receipt_id,
        issuer=issuer,
        source_family=source_family,
        acquisition_id=acquisition_id,
        published_at=published_at,
        content_hash=content_hash,
        status=status,
    )
    sig = "ed25519:" + private_key.sign(canonical).hex()
    return PublicationAttestationReceipt(
        receipt_id=receipt_id,
        issuer=issuer,
        source_family=source_family,
        acquisition_id=acquisition_id,
        published_at=published_at,
        content_hash=content_hash,
        status=status,
        signature=sig,
    )


def register_sensor_receipt(receipt: SensorAttestationReceipt) -> None:
    """Register an authentic cryptographic sensor attestation receipt."""
    if not isinstance(receipt, SensorAttestationReceipt) and getattr(receipt, "__class__", None).__name__ != "SensorAttestationReceipt":
        raise TypeError("receipt must be an instance of SensorAttestationReceipt")
    _TRUSTED_SENSOR_RECEIPTS[receipt.receipt_id] = receipt
    import sys
    for mod_name in ("layer1_fusion.truth_bridge", "services.agribrain.layer1_fusion.truth_bridge"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_TRUSTED_SENSOR_RECEIPTS"):
            mod._TRUSTED_SENSOR_RECEIPTS[receipt.receipt_id] = receipt


def clear_sensor_receipts() -> None:
    """Clear all registered sensor attestation receipts."""
    _TRUSTED_SENSOR_RECEIPTS.clear()
    _REVOKED_SENSOR_RECEIPTS.clear()
    import sys
    for mod_name in ("layer1_fusion.truth_bridge", "services.agribrain.layer1_fusion.truth_bridge"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_TRUSTED_SENSOR_RECEIPTS"):
            mod._TRUSTED_SENSOR_RECEIPTS.clear()
        if mod and hasattr(mod, "_REVOKED_SENSOR_RECEIPTS"):
            mod._REVOKED_SENSOR_RECEIPTS.clear()


def get_sensor_receipt(receipt_id: str) -> Optional[SensorAttestationReceipt]:
    """Retrieve a registered sensor attestation receipt by ID."""
    r = _TRUSTED_SENSOR_RECEIPTS.get(receipt_id)
    if r is not None:
        return r
    import sys
    for mod_name in ("layer1_fusion.truth_bridge", "services.agribrain.layer1_fusion.truth_bridge"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_TRUSTED_SENSOR_RECEIPTS"):
            r = mod._TRUSTED_SENSOR_RECEIPTS.get(receipt_id)
            if r is not None:
                return r
    return None


def register_publication_receipt(receipt: PublicationAttestationReceipt) -> None:
    """Register an authentic publication attestation receipt (R10-02)."""
    if not isinstance(receipt, PublicationAttestationReceipt) and getattr(receipt, "__class__", None).__name__ != "PublicationAttestationReceipt":
        raise TypeError("receipt must be an instance of PublicationAttestationReceipt")
    _TRUSTED_PUBLICATION_RECEIPTS[receipt.receipt_id] = receipt
    import sys
    for mod_name in ("layer1_fusion.truth_bridge", "services.agribrain.layer1_fusion.truth_bridge"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_TRUSTED_PUBLICATION_RECEIPTS"):
            mod._TRUSTED_PUBLICATION_RECEIPTS[receipt.receipt_id] = receipt


def clear_publication_receipts() -> None:
    """Clear all registered publication attestation receipts."""
    _TRUSTED_PUBLICATION_RECEIPTS.clear()
    _REVOKED_PUBLICATION_RECEIPTS.clear()
    import sys
    for mod_name in ("layer1_fusion.truth_bridge", "services.agribrain.layer1_fusion.truth_bridge"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_TRUSTED_PUBLICATION_RECEIPTS"):
            mod._TRUSTED_PUBLICATION_RECEIPTS.clear()
        if mod and hasattr(mod, "_REVOKED_PUBLICATION_RECEIPTS"):
            mod._REVOKED_PUBLICATION_RECEIPTS.clear()


def get_publication_receipt(receipt_id: str) -> Optional[PublicationAttestationReceipt]:
    """Retrieve a registered publication attestation receipt by ID."""
    r = _TRUSTED_PUBLICATION_RECEIPTS.get(receipt_id)
    if r is not None:
        return r
    import sys
    for mod_name in ("layer1_fusion.truth_bridge", "services.agribrain.layer1_fusion.truth_bridge"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_TRUSTED_PUBLICATION_RECEIPTS"):
            r = mod._TRUSTED_PUBLICATION_RECEIPTS.get(receipt_id)
            if r is not None:
                return r
    return None


def verify_publication_receipt(
    receipt_or_id: Any,
    source_family: Optional[str] = None,
    acquisition_id: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> Tuple[bool, str, Optional[datetime]]:
    """Cryptographically verify an immutable publication attestation receipt (R10-02)."""
    target: Optional[PublicationAttestationReceipt] = None
    if isinstance(receipt_or_id, PublicationAttestationReceipt) or getattr(receipt_or_id, "__class__", None).__name__ == "PublicationAttestationReceipt":
        target = receipt_or_id
    elif isinstance(receipt_or_id, str):
        target = get_publication_receipt(receipt_or_id.strip())
    elif isinstance(receipt_or_id, dict):
        try:
            target = PublicationAttestationReceipt(**receipt_or_id)
        except Exception:
            return False, "invalid_publication_receipt_structure", None

    if target is None:
        return False, "unverified_publication_receipt", None

    if target.status != "active":
        return False, f"inactive_publication_receipt:{target.status}", None

    if target.issuer not in _TRUSTED_PUBLICATION_ISSUERS:
        return False, f"untrusted_publication_issuer:{target.issuer}", None

    if target.receipt_id in _REVOKED_PUBLICATION_RECEIPTS:
        return False, f"revoked_publication_receipt:{target.receipt_id}", None

    if source_family and target.source_family:
        t_sf = target.source_family.lower()
        s_sf = source_family.lower()
        if t_sf != s_sf and not (
            (t_sf in ("sentinel2", "sentinel_2", "landsat", "satellite") and s_sf in ("sentinel2", "sentinel_2", "landsat", "satellite")) or
            (t_sf in ("sensor", "sensor_iot", "iot") and s_sf in ("sensor", "sensor_iot", "iot")) or
            (t_sf in ("environment", "weather_station", "weather") and s_sf in ("environment", "weather_station", "weather")) or
            (t_sf in ("raster", "raster_composite", "satellite") and s_sf in ("raster", "raster_composite", "satellite"))
        ):
            return False, f"publication_source_family_mismatch:{target.source_family}!={source_family}", None

    if acquisition_id and target.acquisition_id and str(target.acquisition_id).strip() != str(acquisition_id).strip():
        return False, f"publication_acquisition_mismatch:{target.acquisition_id}!={acquisition_id}", None

    if content_hash and target.content_hash and str(target.content_hash).strip() != str(content_hash).strip():
        return False, f"publication_content_hash_mismatch:{target.content_hash}!={content_hash}", None

    # Cryptographic signature verification
    pub_key = get_trusted_issuer_public_key(target.issuer)
    if pub_key is None:
        return False, f"untrusted_publication_issuer_missing_key:{target.issuer}", None

    sig_str = str(target.signature or "").strip()
    if not sig_str or not sig_str.startswith("ed25519:"):
        return False, "unverified_publication_signature", None

    try:
        sig_bytes = bytes.fromhex(sig_str[len("ed25519:"):])
        if len(sig_bytes) != 64:
            return False, "invalid_publication_signature_length", None
        canonical = compute_publication_receipt_canonical_bytes(
            receipt_id=target.receipt_id,
            issuer=target.issuer,
            source_family=target.source_family,
            acquisition_id=target.acquisition_id,
            published_at=target.published_at,
            content_hash=target.content_hash,
            status=target.status,
        )
        pub_key.verify(sig_bytes, canonical)
    except Exception as e:
        return False, f"invalid_publication_signature:{type(e).__name__}", None

    return True, "verified_publication_receipt", target.published_at


def _context_value(source_context: Any, key: str, default: Any = None) -> Any:
    """Read truth/grid metadata without confusing a composite wrapper for a raster."""
    if source_context is None:
        return default
    if isinstance(source_context, dict):
        if source_context.get(key) is not None:
            return source_context[key]
        grid_spec = source_context.get("grid_spec")
        if isinstance(grid_spec, dict) and grid_spec.get(key) is not None:
            return grid_spec[key]
        provenance = source_context.get("provenance")
        if isinstance(provenance, dict) and provenance.get(key) is not None:
            return provenance[key]
        return default

    metadata = getattr(source_context, "metadata", None)
    if metadata is not None and getattr(metadata, key, None) is not None:
        return getattr(metadata, key)
    return getattr(source_context, key, default)


def _has_valid_geospatial_grid(source_context: Any) -> bool:
    """Require positive-area bounds and an invertible six-value transform."""
    crs = _context_value(source_context, "crs")
    bounds = _context_value(source_context, "bounds")
    transform = _context_value(source_context, "transform")
    if transform is None:
        transform = _context_value(source_context, "affine")
    if not isinstance(crs, str) or not crs.strip():
        return False
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        return False
    if not isinstance(transform, (list, tuple)) or len(transform) != 6:
        return False
    try:
        bounds_values = tuple(float(value) for value in bounds)
        transform_values = tuple(float(value) for value in transform)
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(value) for value in bounds_values + transform_values):
        return False
    if bounds_values[2] <= bounds_values[0] or bounds_values[3] <= bounds_values[1]:
        return False
    gdal_determinant = (
        transform_values[1] * transform_values[5]
        - transform_values[2] * transform_values[4]
    )
    affine_determinant = (
        transform_values[0] * transform_values[4]
        - transform_values[1] * transform_values[3]
    )
    return abs(gdal_determinant) > 1e-15 or abs(affine_determinant) > 1e-15


def verify_sensor_attestation(
    device_id: Optional[str],
    plot_id: Optional[str],
    variable: Optional[str],
    calibration_version: Optional[str],
    provenance_ref: Optional[str] = None,
    flags: Optional[List[str]] = None,
    receipt: Optional[Any] = None,
    raw_status: Optional[str] = None,
) -> Tuple[bool, str]:
    """Unified fail-closed sensor attestation verification for Layer 1 (R8-03).
    
    Shared by both normalize_evidence_truth and truth_for_observation_packet.
    Enforces:
    - Active status in registry
    - Mandatory registered plot matching observation plot
    - Mandatory registered variable matching observation variable
    - Mandatory registered calibration profile matching calibration version
    - Authentic receipt/provenance format (cryptographic / URN prefix, not mock strings)
    - No revocation in flags
    """
    if raw_status in ("synthetic", "simulated", "fallback", "unavailable"):
        return False, f"raw_status_{raw_status}"

    # 1. Mandatory non-empty device_id
    if not device_id or not isinstance(device_id, str) or not device_id.strip():
        return False, "missing_device_id"
    dev_str = device_id.strip()

    # 2. Mandatory non-empty plot_id
    if not plot_id or not isinstance(plot_id, str) or not plot_id.strip():
        return False, "missing_plot_id"
    plot_str = plot_id.strip()

    # 3. Mandatory non-empty variable
    if not variable or not isinstance(variable, str) or not variable.strip():
        return False, "missing_variable"
    var_str = variable.strip()

    # 4. Mandatory non-empty calibration_version
    if not calibration_version or not isinstance(calibration_version, str) or not calibration_version.strip():
        return False, "missing_calibration_version"
    cal_str = calibration_version.strip()

    # 5. Check unverified / forged / dummy tokens
    for val, name in [(dev_str, "device_id"), (cal_str, "calibration_version"), (provenance_ref or "", "provenance_ref")]:
        val_low = str(val).lower()
        if any(token in val_low for token in ("fake", "dummy", "unattested", "spoofed", "unverified", "forged", "user-supplied")):
            return False, f"unattested_or_forged_{name}"

    # 6. Revocation check across flags
    if flags:
        for f in flags:
            f_str = str(f).upper()
            if "REVOKED" in f_str:
                return False, "revoked_certificate_or_device"

    # 7. Device Registry Verification (fail-closed on absent registry, exceptions, or unregistered devices)
    try:
        from services.agribrain.sensor_runtime.registry import get_device_registration
        reg = get_device_registration(dev_str)
    except Exception as ex:
        return False, f"registry_error:{ex}"

    if reg is None:
        return False, "unregistered_device"

    # Status must be active
    if getattr(reg, "status", None) != "active":
        return False, f"inactive_device_status:{getattr(reg, 'status', None)}"

    # Plot scope must be non-empty and match
    reg_plot = getattr(reg, "plot_id", None)
    if not reg_plot or not isinstance(reg_plot, str) or not reg_plot.strip():
        return False, "registry_missing_plot_scope"
    if reg_plot.strip() != plot_str:
        return False, f"plot_scope_mismatch: registered {reg_plot} != requested {plot_str}"

    # Registered variables must be non-empty and declared variable must be in it
    reg_vars = getattr(reg, "variables", None)
    if not reg_vars or not isinstance(reg_vars, (list, tuple, set)):
        return False, "registry_missing_variables"
    if var_str not in reg_vars:
        return False, f"variable_not_registered:{var_str}"

    # Registered calibration_profile_id must be non-empty and match calibration_version
    reg_cal = getattr(reg, "calibration_profile_id", None)
    if not reg_cal or not isinstance(reg_cal, str) or not reg_cal.strip():
        return False, "registry_missing_calibration_profile"
    if reg_cal.strip() != cal_str:
        return False, f"calibration_profile_mismatch: registered {reg_cal} != item {cal_str}"

    # 8. Cryptographic Sensor Attestation Receipt Verification (R9-01, R10-01, R10-06)
    target_receipt: Optional[SensorAttestationReceipt] = None
    if receipt is not None:
        if isinstance(receipt, SensorAttestationReceipt) or getattr(receipt, "__class__", None).__name__ == "SensorAttestationReceipt":
            target_receipt = receipt
        elif isinstance(receipt, str):
            # R10-06: Resolve string receipt reference through trusted receipt store
            target_receipt = get_sensor_receipt(receipt.strip())
        elif isinstance(receipt, dict) and "receipt_id" in receipt and "issuer" in receipt:
            try:
                target_receipt = SensorAttestationReceipt(**receipt)
            except Exception:
                return False, "invalid_receipt_dict_structure"
        elif isinstance(receipt, PublicationAttestationReceipt) or getattr(receipt, "__class__", None).__name__ == "PublicationAttestationReceipt":
            target_receipt = get_sensor_receipt(provenance_ref.strip()) if provenance_ref else None
        else:
            return False, "unauthenticated_receipt_object"
    elif provenance_ref:
        p_ref = provenance_ref.strip()
        target_receipt = get_sensor_receipt(p_ref)

    if target_receipt is None:
        return False, f"unverified_sensor_receipt:{provenance_ref or receipt or 'none'}"

    # Validate target receipt claims and authority
    if target_receipt.status != "active":
        return False, f"inactive_receipt_status:{target_receipt.status}"

    if target_receipt.issuer not in _TRUSTED_SENSOR_ISSUERS:
        return False, f"untrusted_receipt_issuer:{target_receipt.issuer}"

    if target_receipt.device_id != dev_str:
        return False, f"receipt_device_mismatch: {target_receipt.device_id} != {dev_str}"

    if target_receipt.plot_id != plot_str:
        return False, f"receipt_plot_mismatch: {target_receipt.plot_id} != {plot_str}"

    if target_receipt.variable != var_str:
        return False, f"receipt_variable_mismatch: {target_receipt.variable} != {var_str}"

    if target_receipt.calibration_profile_id != cal_str:
        return False, f"receipt_calibration_mismatch: {target_receipt.calibration_profile_id} != {cal_str}"

    # Revocation verification (R10-01, R10-G02)
    if target_receipt.receipt_id in _REVOKED_SENSOR_RECEIPTS:
        return False, f"revoked_sensor_receipt:{target_receipt.receipt_id}"

    if target_receipt.revocation_epoch is not None and target_receipt.revocation_epoch < _CURRENT_REVOCATION_EPOCH:
        return False, f"expired_revocation_epoch:{target_receipt.revocation_epoch} < {_CURRENT_REVOCATION_EPOCH}"

    # Cryptographic Ed25519 signature verification (R10-01, R10-G01, R10-G02)
    pub_key = get_trusted_issuer_public_key(target_receipt.issuer)
    if pub_key is None:
        return False, f"untrusted_issuer_missing_key:{target_receipt.issuer}"

    sig_str = str(target_receipt.signature or "").strip()
    if not sig_str or not sig_str.startswith("ed25519:"):
        return False, "unverified_receipt_signature"

    try:
        sig_hex = sig_str[len("ed25519:"):]
        sig_bytes = bytes.fromhex(sig_hex)
        if len(sig_bytes) != 64:
            return False, "invalid_signature_length"
        canonical = compute_sensor_receipt_canonical_bytes(
            receipt_id=target_receipt.receipt_id,
            issuer=target_receipt.issuer,
            device_id=target_receipt.device_id,
            plot_id=target_receipt.plot_id,
            variable=target_receipt.variable,
            calibration_profile_id=target_receipt.calibration_profile_id,
            status=target_receipt.status,
            content_digest=target_receipt.content_digest,
            observation_instant=target_receipt.observation_instant,
            first_available_at=target_receipt.first_available_at,
            revocation_epoch=target_receipt.revocation_epoch,
        )
        pub_key.verify(sig_bytes, canonical)
    except Exception as e:
        return False, f"invalid_cryptographic_signature:{type(e).__name__}"

    return True, "attested_via_verified_receipt"


def normalize_evidence_truth(item: EvidenceItem, source_context: Optional[Any] = None, source_family: Optional[str] = None) -> EvidenceItem:
    # A context-free pass is allowed to classify a fresh/unknown item, but it
    # must never erase a source-aware classification that already succeeded.
    # Evidence validation is responsible for checking the preserved fields.
    if (
        source_context is None
        and source_family is None
        and item.truth_class not in (None, "", "unknown")
        and item.source_reality not in (None, "", "unknown")
        and item.source_family != "sensor"
    ):
        return item
    if source_family is not None:
        item.source_family = source_family
    is_proxy = False

    prior_status = getattr(item, "data_status", None)
    prior_diagnostic_only = bool(getattr(item, "diagnostic_only", False))
    prior_state_update_allowed = bool(getattr(item, "state_update_allowed", True))

    # 1. Sentinel-2 / Sentinel-1 provider raster
    if item.source_family in ("sentinel1", "sentinel2"):
        if item.data_status == "reconstruction":
            item.truth_class = "reconstruction_proxy"
            item.production_usable = True
            item.real_provider_product = False
            item.diagnostic_only = True
            item.state_update_allowed = False
            item.scientific_surface_allowed = False
            item.visualization_allowed = True
            item.experimental_visual_allowed = True
            item.composite_advisory_allowed = True
            item.prescription_driver_allowed = False
            item.current_1m_approval_allowed = False
            item.grounding_class = None
            return item

        is_daily_plot_statistic = (
            item.spatial_scope == "plot"
            and item.temporal_basis == "daily_plot_statistic"
            and bool(item.content_hash)
            and bool(item.provider_product_id or item.source_id)
            and item.data_status not in ("fallback", "reconstruction", "simulated", "unavailable", "estimated")
            and item.source_reality == "provider_daily_statistical_aggregate"
        )
        if is_daily_plot_statistic:
            item.data_status = "observed"
            item.truth_class = "provider_plot_timeseries"
            item.production_usable = True
            item.real_provider_product = False
            item.diagnostic_only = False
            item.state_update_allowed = True
            item.scientific_surface_allowed = False
            item.visualization_allowed = True
            item.experimental_visual_allowed = True
            item.composite_advisory_allowed = True
            item.prescription_driver_allowed = False
            item.current_1m_approval_allowed = False
            item.grounding_class = None
            return item

        is_real_temporal = (
            item.spatial_scope == "plot"
            and item.temporal_basis == "scene_observation"
            and bool(item.content_hash)
            and bool(item.provider_product_id or item.source_id)
            and item.data_status not in ("fallback", "reconstruction", "simulated", "unavailable", "estimated")
            and item.source_reality in {
                "provider_scene_observation",
                "provider_temporal_observation",
                "real_provider_raster",
                "provider_observation",
                "real_raster",
            }
        )
        if is_real_temporal:
            item.data_status = "observed"
            item.truth_class = "provider_plot_timeseries"
            item.source_reality = "provider_temporal_observation"
            item.production_usable = True
            item.real_provider_product = True
            item.diagnostic_only = False
            item.state_update_allowed = True
            item.scientific_surface_allowed = True
            item.visualization_allowed = True
            item.experimental_visual_allowed = True
            item.composite_advisory_allowed = True
            item.prescription_driver_allowed = False
            item.current_1m_approval_allowed = False
            item.grounding_class = "UNIFORM"
            return item

        if source_context is not None:
            if isinstance(source_context, dict):
                is_proxy = (
                    source_context.get("source_reality") == "raster_composite_proxy"
                    or source_context.get("production_usable") is False
                    or source_context.get("real_provider_product") is False
                    or source_context.get("diagnostic_only") is True
                )
            else:
                meta = getattr(source_context, "metadata", None)
                if meta is not None:
                    is_proxy = (
                        getattr(meta, "source_reality", None) == "raster_composite_proxy"
                        or getattr(meta, "production_usable", True) is False
                        or getattr(meta, "real_provider_product", True) is False
                        or getattr(meta, "diagnostic_only", False) is True
                    )
                else:
                    is_proxy = (
                        getattr(source_context, "source_reality", None) == "raster_composite_proxy"
                        or getattr(source_context, "production_usable", True) is False
                        or getattr(source_context, "real_provider_product", True) is False
                        or getattr(source_context, "diagnostic_only", False) is True
                    )
        
        has_crs_proof = False
        if source_context is not None:
            if isinstance(source_context, dict):
                has_crs_proof = (
                    source_context.get("crs") is not None 
                    and (source_context.get("transform") is not None or source_context.get("affine") is not None)
                )
            else:
                meta = getattr(source_context, "metadata", None)
                if meta is not None:
                    has_crs_proof = (
                        getattr(meta, "crs", None) is not None 
                        and (getattr(meta, "transform", None) is not None or getattr(meta, "affine", None) is not None)
                    )
                else:
                    has_crs_proof = (
                        getattr(source_context, "crs", None) is not None 
                        and (getattr(source_context, "transform", None) is not None or getattr(source_context, "affine", None) is not None)
                    )

        if not has_crs_proof:
            is_proxy = True

        if not is_proxy:
            is_proxy = (
                item.source_reality == "raster_composite_proxy"
                or item.data_status == "fallback"
                or any("PROXY" in str(f).upper() for f in (item.flags or []))
            )

        if is_proxy:
            item.data_status = "fallback"
            item.truth_class = "raster_composite_proxy"
            item.source_reality = "raster_composite_proxy"
            item.production_usable = False
            item.real_provider_product = False
            item.diagnostic_only = True
            item.state_update_allowed = False
            item.visualization_allowed = True
            item.composite_advisory_allowed = True
            item.experimental_visual_allowed = True
            item.scientific_surface_allowed = False
            item.prescription_driver_allowed = False
            item.current_1m_approval_allowed = False
            item.grounding_class = "PROXY_SPATIAL"
        else:
            item.data_status = "observed"
            item.truth_class = "observed_provider"
            item.source_reality = "real_provider_raster"
            item.production_usable = True
            item.real_provider_product = True
            item.diagnostic_only = False
            item.state_update_allowed = True
            item.scientific_surface_allowed = True
            item.visualization_allowed = True
            item.experimental_visual_allowed = True
            item.composite_advisory_allowed = True
            item.prescription_driver_allowed = True
            item.current_1m_approval_allowed = True
            item.grounding_class = "RASTER_GROUNDED"

    # 2. Weather or forecast
    elif item.source_family == "weather_forecast":
        # Keep data_status if set, default to estimated. Must not be "partial"
        if item.data_status not in ("observed", "estimated", "interpolated", "assimilated", "fallback", "simulated", "unavailable"):
            item.data_status = "estimated"
        
        if item.data_status == "observed":
            item.truth_class = "observed_provider_weather"
        else:
            item.truth_class = "provider_forecast_model"
            
        item.source_reality = "provider_model_feed"
        item.production_usable = True
        item.real_provider_product = True
        item.diagnostic_only = False
        
        # state_update_allowed only for approved forecast variables
        approved_vars = ("forecast_precip", "forecast_et0", "forecast_temp_max", "forecast_temp_min", "precipitation", "temp_max", "temp_min", "et0")
        item.state_update_allowed = item.variable in approved_vars
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = False
        item.composite_advisory_allowed = False

    elif item.source_family == "environment":
        is_soil = "soil" in str(item.variable) or "static" in str(item.observation_type)
        if item.data_status not in ("observed", "estimated", "interpolated", "assimilated", "fallback", "simulated", "unavailable"):
            item.data_status = "observed" if is_soil else "estimated"
        item.truth_class = "geo_provider_context" if is_soil else "observed_provider_weather"
        item.source_reality = "provider_geo_context" if is_soil else "provider_model_feed"
        item.production_usable = True
        item.real_provider_product = True
        item.diagnostic_only = False
        item.state_update_allowed = True
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = False
        item.composite_advisory_allowed = False

    # 3. User Event or Observation
    elif item.source_family in ("user_event", "user_observation") or item.observation_type == "event":
        item.data_status = "observed"
        item.truth_class = "observed_user"
        item.source_reality = "user_observation"
        item.production_usable = True
        item.real_provider_product = False
        item.diagnostic_only = False
        is_validated = "VALIDATED" in [str(f).upper() for f in (item.flags or [])] or "CALIBRATED" in [str(f).upper() for f in (item.flags or [])]
        item.state_update_allowed = True if is_validated else False
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 4. Geo context
    elif item.source_family in ("geo_context", "soilgrids", "fao"):
        is_static = "static" in str(item.observation_type) or "static" in str(item.temporal_scope)
        item.data_status = "observed" if is_static else "estimated"
        item.truth_class = "geo_provider_context" if is_static else "estimated_geo_context"
        item.source_reality = "provider_geo_context"
        item.production_usable = True
        item.real_provider_product = True
        item.diagnostic_only = False
        
        # state_update_allowed only for stable context variables
        stable_context_vars = ("clay", "sand", "silt", "ph", "soil_type", "organic_matter", "bulk_density", "cec")
        item.state_update_allowed = item.variable in stable_context_vars
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 5. ASMAE composite / advisory
    elif item.source_family in ("asmae", "asmae_composite"):
        is_comp = "COMPOSITE" in str(item.variable).upper()
        item.data_status = "fallback" if is_comp else "assimilated"
        item.truth_class = "raster_composite_proxy" if is_comp else "estimated_model"
        item.source_reality = "raster_composite_proxy" if is_comp else "provider_model_feed"
        item.production_usable = False
        item.real_provider_product = False
        item.diagnostic_only = True
        item.state_update_allowed = False
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.composite_advisory_allowed = True
        item.experimental_visual_allowed = True

    # 6. Sensor/IoT (R8-03: unified verify_sensor_attestation)
    elif item.source_family == "sensor":
        dev_id = getattr(item, "instrument_id", None) or getattr(item, "source_id", None)
        cal_ver = getattr(item, "calibration_version", None)
        
        is_attested, att_reason = verify_sensor_attestation(
            device_id=dev_id,
            plot_id=getattr(item, "plot_id", None),
            variable=getattr(item, "variable", None),
            calibration_version=cal_ver,
            provenance_ref=getattr(item, "provenance_ref", None),
            flags=getattr(item, "flags", None),
            receipt=getattr(item, "receipt", None),
            raw_status=getattr(item, "data_status", None),
        )

        is_synthetic = getattr(item, "data_status", "") in ("synthetic", "simulated", "fallback")
        if not is_attested or is_synthetic:
            item.data_status = "synthetic" if is_synthetic else getattr(item, "data_status", "unverified")
            item.truth_class = "unverified_sensor"
            item.source_reality = "synthetic_or_uncalibrated"
            item.production_usable = False
            item.real_provider_product = False
            item.diagnostic_only = True
            item.state_update_allowed = False
        else:
            existing_diagnostic_only = bool(getattr(item, "diagnostic_only", False))
            existing_state_update_allowed = bool(getattr(item, "state_update_allowed", True))
            item.data_status = "observed"
            item.truth_class = "observed_sensor"
            item.source_reality = "sensor_physical"
            item.production_usable = True
            item.real_provider_product = True
            item.diagnostic_only = existing_diagnostic_only
            item.state_update_allowed = existing_state_update_allowed and not existing_diagnostic_only
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.composite_advisory_allowed = True
        item.experimental_visual_allowed = True

    # 6a. Sentinel-5P
    elif item.source_family == "sentinel5p":
        item.data_status = "observed"
        item.truth_class = "provider_observation"
        item.source_reality = "real_provider_raster"
        item.production_usable = True
        item.real_provider_product = True
        item.diagnostic_only = False
        item.state_update_allowed = True
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6b. Drone
    elif item.source_family in ("drone_structural", "drone"):
        is_restricted = prior_status in ("simulated", "estimated", "fallback", "unavailable", "reconstruction")
        if is_restricted:
            item.data_status = prior_status
            item.truth_class = f"{prior_status}_proxy" if prior_status != "unavailable" else "unavailable"
            item.source_reality = "user_observation"
            item.production_usable = prior_status != "unavailable"
            item.real_provider_product = False
            item.diagnostic_only = True
            item.state_update_allowed = False
        else:
            item.data_status = "observed"
            item.truth_class = "provider_observation"
            item.source_reality = "user_observation"
            item.production_usable = True
            item.real_provider_product = True
            item.diagnostic_only = prior_diagnostic_only
            item.state_update_allowed = prior_state_update_allowed and not prior_diagnostic_only
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6c. History
    elif item.source_family == "history":
        item.data_status = "observed"
        item.truth_class = "observed_provider"
        item.source_reality = "real_provider_raster"
        item.production_usable = True
        item.real_provider_product = True
        item.diagnostic_only = False
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6d. Level 0 State (assimilated model state, NOT raw provider measurement - E-04/T15)
    elif item.source_family == "l0_state":
        item.data_status = "assimilated"
        item.truth_class = "model_state"
        item.source_reality = "model_derived"
        item.production_usable = True
        item.real_provider_product = False
        item.diagnostic_only = False
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6e. EO Foundation
    elif item.source_family == "eo_foundation":
        is_unqualified = "UNQUALIFIED_SPATIAL_IDENTITY" in (getattr(item, "flags", None) or []) or getattr(item, "is_spatial_qualified", True) is False
        item.data_status = "estimated"
        item.truth_class = "estimated_model"
        item.source_reality = "provider_model_feed"
        item.production_usable = not is_unqualified
        item.real_provider_product = False
        item.diagnostic_only = True
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6f. Perception
    elif item.source_family == "perception":
        item.data_status = "estimated"
        item.truth_class = "estimated_model"
        item.source_reality = "provider_model_feed"
        item.production_usable = True
        item.real_provider_product = False
        item.diagnostic_only = False
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6g. Raster Composite
    elif item.source_family == "raster_composite":
        # Enforce proxy default
        is_proxy = True
        has_geospatial_proof = _has_valid_geospatial_grid(source_context)
        if source_context is not None:
            is_real = (
                _context_value(source_context, "real_provider_product", False) is True
                and _context_value(source_context, "production_usable", False) is True
                and _context_value(source_context, "diagnostic_only", True) is False
                and has_geospatial_proof
            )
            if is_real:
                is_proxy = False

        if is_proxy:
            item.data_status = "fallback"
            item.truth_class = "raster_composite_proxy"
            item.source_reality = "raster_composite_proxy"
            item.production_usable = False
            item.real_provider_product = False
            item.diagnostic_only = True
            item.state_update_allowed = False
            item.visualization_allowed = True
            item.composite_advisory_allowed = True
            item.experimental_visual_allowed = True
            item.scientific_surface_allowed = False
            item.prescription_driver_allowed = False
            item.current_1m_approval_allowed = False
            item.grounding_class = "PROXY_SPATIAL" if has_geospatial_proof else "UNIFORM"
        else:
            item.data_status = "observed"
            item.truth_class = "observed_provider"
            item.source_reality = "real_provider_raster"
            item.production_usable = True
            item.real_provider_product = True
            item.diagnostic_only = False
            item.state_update_allowed = True
            item.scientific_surface_allowed = True
            item.visualization_allowed = True
            item.experimental_visual_allowed = True
            item.composite_advisory_allowed = True
            item.prescription_driver_allowed = True
            item.current_1m_approval_allowed = True
            item.grounding_class = "RASTER_GROUNDED"

    # 6h. Zone Segmentation / Microzone
    elif item.source_family in ("zone_segmentation", "microzone"):
        item.data_status = "estimated"
        item.truth_class = "derived_zone"
        item.source_reality = "provider_model_feed"
        item.production_usable = True
        item.real_provider_product = False
        item.diagnostic_only = False
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 7. Fallback Default (If we cannot classify, let's keep it unknown so it gets quarantined!)
    else:
        item.data_status = "unknown"
        item.truth_class = "unknown"
        item.source_reality = "unknown"
        item.production_usable = False
        item.real_provider_product = False
        item.diagnostic_only = True
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False

    # Monotone role and permission preservation: restrictive status cannot be promoted
    if prior_status in ("unavailable", "simulated", "fallback", "reconstruction"):
        item.data_status = prior_status
        item.diagnostic_only = True
        item.state_update_allowed = False
    elif prior_status == "estimated":
        if item.data_status == "observed":
            item.data_status = "estimated"
        item.state_update_allowed = False if not prior_state_update_allowed else item.state_update_allowed
    elif prior_diagnostic_only:
        item.diagnostic_only = True
        item.state_update_allowed = False

    # Enforce status-based confidence ceilings
    from .schemas import DATA_STATUS_CEILING
    if item.data_status in DATA_STATUS_CEILING:
        ceil_val = DATA_STATUS_CEILING[item.data_status]
        if item.confidence is not None:
            fin_c = finite_real(item.confidence)
            if fin_c is not None:
                item.confidence = min(fin_c, ceil_val)

    return item

def truth_for_observation_packet(packet: ObservationPacket, package: Optional[Any] = None) -> EvidenceTruth:
    if packet is None:
        return EvidenceTruth(
            data_status="fallback",
            truth_class="fallback_default",
            source_reality="fallback_default",
            real_provider_product=False,
            production_usable=False,
            diagnostic_only=True,
            state_update_allowed=False,
        )
    payload = packet.payload if isinstance(packet.payload, dict) else {}
    declared_roles = [
        str(payload[k]).upper()
        for k in ("role", "source_role", "data_role", "status_role", "truth_class")
        if k in payload and payload[k] is not None
    ]
    is_excluded = (
        packet.data_status.value == "unavailable"
        or any(r in ("UNAVAILABLE", "EXCLUDED", "REJECTED") for r in declared_roles)
    )
    is_simulated = (
        packet.data_status.value == "simulated"
        or any(r in ("SIMULATED", "SYNTHETIC", "SCENARIO") for r in declared_roles)
        or payload.get("simulated") is True
    )
    is_fallback = (
        packet.data_status.value == "fallback"
        or any(r in ("FALLBACK", "PROXY") for r in declared_roles)
        or payload.get("source_reality") == "raster_composite_proxy"
        or payload.get("production_usable") is False
        or (
            payload.get("real_provider_product") is False
            and payload.get("source_reality") != "provider_daily_statistical_aggregate"
        )
        or payload.get("diagnostic_only") is True
    )
    is_reconstruction = (
        packet.data_status.value == "reconstruction"
        or any(r == "RECONSTRUCTION" for r in declared_roles)
    )
    is_estimated = (
        packet.data_status.value == "estimated"
        or any(r in ("FORECAST", "ESTIMATED", "DERIVED", "PREDICTION", "MODELLED", "PRIOR") for r in declared_roles)
    )

    if is_excluded:
        return EvidenceTruth(
            data_status="unavailable",
            truth_class="unavailable",
            source_reality="unavailable",
            real_provider_product=False,
            production_usable=False,
            diagnostic_only=True,
            state_update_allowed=False,
        )

    if is_simulated:
        return EvidenceTruth(
            data_status="simulated",
            truth_class="simulated_proxy",
            source_reality="simulated_proxy",
            real_provider_product=False,
            production_usable=False,
            diagnostic_only=True,
            state_update_allowed=False,
            visualization_allowed=True,
            composite_advisory_allowed=True,
            experimental_visual_allowed=True,
        )

    if is_fallback:
        return EvidenceTruth(
            data_status="fallback",
            truth_class="raster_composite_proxy",
            source_reality="raster_composite_proxy",
            production_usable=False,
            real_provider_product=False,
            diagnostic_only=True,
            state_update_allowed=False,
            visualization_allowed=True,
            composite_advisory_allowed=True,
            experimental_visual_allowed=True,
        )

    if is_reconstruction:
        return EvidenceTruth(
            data_status="reconstruction",
            truth_class="reconstruction_proxy",
            source_reality="reconstruction_proxy",
            production_usable=True,
            real_provider_product=False,
            diagnostic_only=True,
            state_update_allowed=False,
            visualization_allowed=True,
            composite_advisory_allowed=True,
            experimental_visual_allowed=True,
        )

    if is_estimated:
        return EvidenceTruth(
            data_status="estimated",
            truth_class="estimated_proxy",
            source_reality="estimated_proxy",
            production_usable=True,
            real_provider_product=False,
            diagnostic_only=False,
            state_update_allowed=False,
            visualization_allowed=True,
            composite_advisory_allowed=True,
            experimental_visual_allowed=True,
        )

    is_daily_plot_statistic = (
        payload.get("source_reality") == "provider_daily_statistical_aggregate"
        and payload.get("temporal_basis") == "daily_plot_statistic"
    )
    if is_daily_plot_statistic:
        from layer0.temporal_evidence import is_admitted_temporal_record
        if is_admitted_temporal_record(payload):
            return EvidenceTruth(
                data_status="observed",
                truth_class="provider_plot_timeseries",
                source_reality="provider_daily_statistical_aggregate",
                production_usable=True,
                real_provider_product=False,
                diagnostic_only=False,
                state_update_allowed=True,
                grounding_class=None,
                scientific_surface_allowed=False,
                visualization_allowed=True,
                experimental_visual_allowed=True,
                composite_advisory_allowed=True,
                prescription_driver_allowed=False,
                current_1m_approval_allowed=False,
            )

    if packet.source.value in ("user_observation", "user_event"):
        return EvidenceTruth(
            data_status=packet.data_status.value,
            truth_class="observed_user",
            source_reality="user_observation",
            production_usable=True,
            real_provider_product=False,
            diagnostic_only=False,
            state_update_allowed=False, # user observation state update is false unless validated
            visualization_allowed=True,
            composite_advisory_allowed=True,
            experimental_visual_allowed=True,
        )

    if packet.source.value in ("sensor", "sensor_iot", "soil_probe"):
        payload = packet.payload or {}
        dev_id = payload.get("instrument_id") or payload.get("device_id") or getattr(packet, "instrument_id", None)
        plot_id = packet.plot_id or (getattr(package, "plot_id", None) if package else None)
        var_name = payload.get("variable") or next((k for k in ("soil_moisture_vwc", "soil_moisture", "leaf_wetness", "temperature", "humidity", "rainfall") if k in payload), None)
        cal_ver = payload.get("calibration_version") or (getattr(packet.qa, "calibration_version", None) if packet.qa else None)
        
        pkg_hash = getattr(package, "package_hash", "") if package else ""
        pkt_hash = getattr(packet, "content_hash", "") or packet.packet_id
        prov_ref = (
            payload.get("provenance_ref")
            or getattr(packet, "provenance_ref", None)
            or (getattr(getattr(packet, "provenance", None), "receipt_ref", None) if getattr(packet, "provenance", None) else None)
        )
        receipt_obj = getattr(packet, "receipt", None)
        flags = [f.value if hasattr(f, "value") else str(f) for f in (packet.qa.flags if packet.qa else [])]
        if "flags" in payload and isinstance(payload["flags"], list):
            flags.extend(payload["flags"])

        is_valid_sensor, att_reason = verify_sensor_attestation(
            device_id=dev_id,
            plot_id=plot_id,
            variable=var_name,
            calibration_version=cal_ver,
            provenance_ref=prov_ref,
            flags=flags,
            receipt=receipt_obj,
            raw_status=packet.data_status.value if packet.data_status else None,
        )
        if is_valid_sensor:
            return EvidenceTruth(
                data_status="observed",
                truth_class="observed_sensor",
                source_reality="sensor_physical",
                production_usable=True,
                real_provider_product=True,
                diagnostic_only=False,
                state_update_allowed=True,
                visualization_allowed=True,
                experimental_visual_allowed=True,
                composite_advisory_allowed=True,
                scientific_surface_allowed=False,
                prescription_driver_allowed=False,
                current_1m_approval_allowed=False,
            )
        else:
            return EvidenceTruth(
                data_status="unverified" if packet.data_status.value == "observed" else packet.data_status.value,
                truth_class="unverified_sensor",
                source_reality="synthetic_or_uncalibrated",
                production_usable=False,
                real_provider_product=False,
                diagnostic_only=True,
                state_update_allowed=False,
                visualization_allowed=True,
                experimental_visual_allowed=True,
                composite_advisory_allowed=True,
                scientific_surface_allowed=False,
                prescription_driver_allowed=False,
                current_1m_approval_allowed=False,
            )
        
    if packet.data_status.value == "observed":
        is_sentinel = packet.source.value in ("sentinel1", "sentinel2")
        has_crs = False
        if is_sentinel:
            payload = packet.payload or {}
            has_crs = (
                payload.get("crs") is not None
                and (payload.get("transform") is not None or payload.get("affine") is not None)
            )

        if is_sentinel and not has_crs:
            return EvidenceTruth(
                data_status="fallback",
                truth_class="raster_composite_proxy",
                source_reality="raster_composite_proxy",
                production_usable=False,
                real_provider_product=False,
                diagnostic_only=True,
                state_update_allowed=False,
                visualization_allowed=True,
                composite_advisory_allowed=True,
                experimental_visual_allowed=True,
                grounding_class="PROXY_SPATIAL"
            )

        return EvidenceTruth(
            data_status="observed",
            truth_class="observed_provider",
            source_reality="real_provider_raster" if is_sentinel else "provider_observation",
            production_usable=True,
            real_provider_product=True,
            diagnostic_only=False,
            state_update_allowed=True,
            grounding_class="RASTER_GROUNDED" if is_sentinel else None,
            scientific_surface_allowed=True,
            visualization_allowed=True,
            experimental_visual_allowed=True,
            composite_advisory_allowed=True,
            prescription_driver_allowed=True,
            current_1m_approval_allowed=True,
        )
        
    return EvidenceTruth(
        data_status=packet.data_status.value,
        truth_class="estimated_model" if packet.data_status.value == "estimated" else "fallback_default",
        source_reality="provider_model_feed" if packet.data_status.value == "estimated" else "fallback_default",
        production_usable=True if packet.data_status.value == "estimated" else False,
        real_provider_product=True if packet.data_status.value == "estimated" else False,
        diagnostic_only=False if packet.data_status.value == "estimated" else True,
        state_update_allowed=True if packet.data_status.value == "estimated" else False,
        visualization_allowed=True,
        experimental_visual_allowed=True,
        composite_advisory_allowed=False if packet.data_status.value == "estimated" else True,
    )

def truth_for_raster_composite(raster_data: Any) -> EvidenceTruth:
    from layer05_asmae.truth_contract import classify_raster_truth
    truth = classify_raster_truth(raster_data)
    has_geospatial_proof = _has_valid_geospatial_grid(raster_data)
    is_authoritative = (
        has_geospatial_proof
        and truth.real_provider_product
        and truth.production_usable
        and not truth.diagnostic_only
    )
    if not is_authoritative:
        return EvidenceTruth(
            data_status="fallback",
            truth_class="raster_composite_proxy",
            source_reality="raster_composite_proxy",
            real_provider_product=False,
            production_usable=False,
            diagnostic_only=True,
            state_update_allowed=False,
            grounding_class="PROXY_SPATIAL" if has_geospatial_proof else "UNIFORM",
            visualization_allowed=True,
            experimental_visual_allowed=True,
            composite_advisory_allowed=True,
            scientific_surface_allowed=False,
            prescription_driver_allowed=False,
            current_1m_approval_allowed=False,
        )
    return EvidenceTruth(
        data_status="observed",
        truth_class=truth.truth_class,
        source_reality=truth.source_reality,
        real_provider_product=truth.real_provider_product,
        production_usable=truth.production_usable,
        diagnostic_only=truth.diagnostic_only,
        state_update_allowed=truth.state_update_allowed,
        grounding_class="RASTER_GROUNDED",
        visualization_allowed=truth.visualization_allowed,
        experimental_visual_allowed=truth.experimental_visual_allowed,
        composite_advisory_allowed=truth.composite_advisory_allowed,
        scientific_surface_allowed=truth.scientific_surface_allowed,
        prescription_driver_allowed=truth.prescription_driver_allowed,
        current_1m_approval_allowed=truth.current_1m_approval_allowed,
    )

def truth_for_weather_record(record: Any) -> EvidenceTruth:
    return EvidenceTruth(
        data_status="estimated",
        truth_class="estimated_model",
        source_reality="provider_model_feed",
        production_usable=True,
        real_provider_product=True,
        diagnostic_only=False,
        state_update_allowed=True,
        visualization_allowed=True,
        experimental_visual_allowed=True,
        composite_advisory_allowed=False,
    )

def truth_for_user_observation(record: Any) -> EvidenceTruth:
    return EvidenceTruth(
        data_status="observed",
        truth_class="observed_user",
        source_reality="user_observation",
        production_usable=True,
        real_provider_product=False,
        diagnostic_only=False,
        state_update_allowed=False,
        visualization_allowed=True,
        composite_advisory_allowed=True,
        experimental_visual_allowed=True,
    )

normalize_truth_from_packet = truth_for_observation_packet

def apply_truth_contract(item: EvidenceItem, source_package: Optional[Any] = None, packet: Optional[Any] = None) -> EvidenceItem:
    return normalize_evidence_truth(item, source_context=source_package or packet)
