"""MESIA SigMF Capture Ingestion Pipeline — R6 §8.2 / P-04 / Finding #17, #21.

Architected around atomic, content-addressed capture manifests that bind
binary payload and metadata together under strict tenant/plot scoped paths.
Never substitutes default or synthetic timestamps.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from ..contracts.capture_manifest import (
    QuarantinedCaptureException,
    RadioProfile,
    SigMFCaptureManifest,
)

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
DEFAULT_STORAGE_ROOT = WORKSPACE_ROOT / "services" / "agribrain" / "mesia" / "data" / "captures"


def _sanitize_id(identifier: str, field_name: str) -> str:
    clean = str(identifier).strip()
    if not clean:
        raise ValueError(f"{field_name} must not be empty")
    if ".." in clean or "/" in clean or "\\" in clean:
        raise ValueError(f"{field_name} contains forbidden path traversal characters: {identifier!r}")
    return clean


def parse_capture_timestamp(dt_val: Any) -> datetime:
    """Parse capture timestamp into a timezone-aware UTC datetime.

    Fails closed: never returns datetime.now() fallback.
    """
    if not dt_val:
        raise QuarantinedCaptureException("Missing capture timestamp: temporal provenance cannot be established")

    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val.astimezone(timezone.utc)

    if isinstance(dt_val, str):
        clean_str = dt_val.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(clean_str)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (ValueError, TypeError) as e:
            raise QuarantinedCaptureException(f"Unparseable capture timestamp {dt_val!r}: {e}") from e

    raise QuarantinedCaptureException(f"Invalid timestamp type {type(dt_val).__name__} for radio capture")


def ingest_sigmf_capture(
    tenant_id: str,
    plot_id: str,
    raw_data_bytes: bytes,
    metadata_dict: Dict[str, Any],
    storage_root: Optional[Path] = None,
) -> SigMFCaptureManifest:
    """Ingest a SigMF CSI/IQ recording with atomic binding and strict tenant scoping.

    Args:
        tenant_id: Tenant identifier (e.g. 'tenant_algeria_01').
        plot_id: Plot identifier (e.g. 'plot_wifi_01').
        raw_data_bytes: Raw binary bytes of the .sigmf-data stream.
        metadata_dict: Full SigMF metadata dictionary.
        storage_root: Optional root directory for captures.

    Returns:
        SigMFCaptureManifest binding data and metadata under identical capture_id.

    Raises:
        QuarantinedCaptureException: If metadata lacks valid timestamp, hardware info,
            or binary payload is empty.
        ValueError: If tenant_id or plot_id contains path traversal elements.
    """
    tenant_clean = _sanitize_id(tenant_id, "tenant_id")
    plot_clean = _sanitize_id(plot_id, "plot_id")

    if not raw_data_bytes:
        raise QuarantinedCaptureException("Binary payload (.sigmf-data) is empty")

    if not isinstance(metadata_dict, dict) or not metadata_dict:
        raise QuarantinedCaptureException("Metadata dictionary (.sigmf-meta) is missing or empty")

    # 1. Validate mandatory SigMF captures block and acquisition timestamp
    captures = metadata_dict.get("captures")
    if not isinstance(captures, list) or not captures:
        raise QuarantinedCaptureException("SigMF metadata lacks mandatory 'captures' array")

    first_capture = captures[0]
    if not isinstance(first_capture, dict):
        raise QuarantinedCaptureException("SigMF first capture segment is invalid")

    raw_dt = first_capture.get("core:datetime")
    capture_timestamp = parse_capture_timestamp(raw_dt)

    # 2. Extract radio profile
    glob = metadata_dict.get("global", {})
    frequency_hz = float(first_capture.get("core:frequency", 0.0))
    sample_rate_hz = float(glob.get("core:sample_rate", 0.0))
    hw_driver = str(glob.get("core:hw", "UNKNOWN"))

    annot = (metadata_dict.get("annotations") or [{}])[0]
    rx_gain = float(annot.get("mesia:agc_gain_db", 0.0))
    num_samples = int(annot.get("core:sample_count", len(raw_data_bytes) // 8))

    radio_profile = RadioProfile(
        family="WIFI_CSI" if "wifi" in hw_driver.lower() or "csi" in hw_driver.lower() else "RADIO_SENSING",
        frequency_hz=frequency_hz,
        bandwidth_hz=sample_rate_hz,
        antenna_array=hw_driver,
        rx_gain_db=rx_gain,
    )

    # 3. Compute digests
    data_sha256 = hashlib.sha256(raw_data_bytes).hexdigest()

    # Update metadata with actual payload hash
    metadata_dict.setdefault("global", {})["core:sha256"] = data_sha256
    meta_json_bytes = json.dumps(metadata_dict, indent=2, sort_keys=True).encode("utf-8")
    meta_sha256 = hashlib.sha256(meta_json_bytes).hexdigest()

    # Combined content-addressed capture identifier
    combined_hasher = hashlib.sha256()
    combined_hasher.update(raw_data_bytes)
    combined_hasher.update(meta_json_bytes)
    capture_id = combined_hasher.hexdigest()

    # 4. Scoped atomic write
    root = Path(storage_root or DEFAULT_STORAGE_ROOT)
    dest_dir = root / tenant_clean / plot_clean
    dest_dir.mkdir(parents=True, exist_ok=True)

    prefix = dest_dir / capture_id
    data_file = dest_dir / f"{capture_id}.sigmf-data"
    meta_file = dest_dir / f"{capture_id}.sigmf-meta"

    # Write data file atomically
    tmp_data = dest_dir / f".tmp_{capture_id}.sigmf-data"
    tmp_meta = dest_dir / f".tmp_{capture_id}.sigmf-meta"

    try:
        tmp_data.write_bytes(raw_data_bytes)
        tmp_meta.write_bytes(meta_json_bytes)
        # Atomic rename on POSIX / replacement on Windows
        os.replace(tmp_data, data_file)
        os.replace(tmp_meta, meta_file)
    except Exception as e:
        if tmp_data.exists():
            tmp_data.unlink()
        if tmp_meta.exists():
            tmp_meta.unlink()
        raise OSError(f"Failed to atomically persist SigMF capture: {e}") from e

    manifest = SigMFCaptureManifest(
        capture_id=capture_id,
        tenant_id=tenant_clean,
        plot_id=plot_clean,
        capture_timestamp_utc=capture_timestamp,
        data_sha256=data_sha256,
        meta_sha256=meta_sha256,
        radio_profile=radio_profile,
        packet_count=num_samples,
        storage_prefix=str(prefix),
    )

    # Persist manifest alongside recording
    manifest_file = dest_dir / f"{capture_id}.manifest.json"
    manifest_file.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")

    return manifest


def verify_capture_integrity(
    storage_prefix_or_manifest: Union[str, Path, SigMFCaptureManifest],
    expected_namespace: Optional[Any] = None,
    storage_root: Optional[Union[str, Path]] = None,
) -> bool:
    """Verify that .sigmf-data, .sigmf-meta, and .manifest.json exist, are non-symlink,
    and mutually bind data, metadata, manifest, namespace, and content-addressed capture_id.
    """
    try:
        expected_tenant: Optional[str] = None
        expected_plot: Optional[str] = None
        if expected_namespace is not None:
            if hasattr(expected_namespace, "tenant_id") and hasattr(expected_namespace, "plot_id"):
                expected_tenant = _sanitize_id(str(expected_namespace.tenant_id), "tenant_id")
                expected_plot = _sanitize_id(str(expected_namespace.plot_id), "plot_id")
            elif isinstance(expected_namespace, dict):
                expected_tenant = _sanitize_id(str(expected_namespace.get("tenant_id") or ""), "tenant_id")
                expected_plot = _sanitize_id(str(expected_namespace.get("plot_id") or ""), "plot_id")
            elif isinstance(expected_namespace, str) and ":" in expected_namespace:
                parts = expected_namespace.split(":")
                if len(parts) >= 3 and parts[0] and parts[2]:
                    expected_tenant = _sanitize_id(parts[0], "tenant_id")
                    expected_plot = _sanitize_id(parts[2], "plot_id")

        if isinstance(storage_prefix_or_manifest, SigMFCaptureManifest):
            prefix = Path(storage_prefix_or_manifest.storage_prefix)
            expected_data_sha = storage_prefix_or_manifest.data_sha256.lower()
            expected_meta_sha = storage_prefix_or_manifest.meta_sha256.lower()
            expected_capture_id = storage_prefix_or_manifest.capture_id.lower()
            manifest_tenant = _sanitize_id(storage_prefix_or_manifest.tenant_id, "tenant_id")
            manifest_plot = _sanitize_id(storage_prefix_or_manifest.plot_id, "plot_id")
            if expected_tenant and manifest_tenant != expected_tenant:
                return False
            if expected_plot and manifest_plot != expected_plot:
                return False
            expected_tenant = manifest_tenant
            expected_plot = manifest_plot
        else:
            p_str = str(storage_prefix_or_manifest).strip()
            if p_str.startswith("file://"):
                from urllib.parse import urlsplit
                from urllib.request import url2pathname
                parsed = urlsplit(p_str)
                p_str = url2pathname(parsed.path)
            if p_str.endswith(".sigmf-data"):
                prefix = Path(p_str[:-11])
            elif p_str.endswith(".sigmf-meta"):
                prefix = Path(p_str[:-11])
            elif p_str.endswith(".manifest.json"):
                prefix = Path(p_str[:-14])
            else:
                prefix = Path(p_str)
            expected_data_sha = None
            expected_meta_sha = None
            expected_capture_id = None

        dest_dir = prefix.parent
        capture_stem = prefix.name

        data_file = dest_dir / f"{capture_stem}.sigmf-data"
        meta_file = dest_dir / f"{capture_stem}.sigmf-meta"
        manifest_file = dest_dir / f"{capture_stem}.manifest.json"

        # 1. Existence and regular file checks
        if not data_file.is_file() or not meta_file.is_file() or not manifest_file.is_file():
            return False

        # 2. Strict symlink rejection
        if data_file.is_symlink() or meta_file.is_symlink() or manifest_file.is_symlink():
            return False

        # 3. Read and hash data payload
        raw_data_bytes = data_file.read_bytes()
        if not raw_data_bytes:
            return False
        actual_data_sha = hashlib.sha256(raw_data_bytes).hexdigest().lower()
        if expected_data_sha and actual_data_sha != expected_data_sha:
            return False

        # 4. Read and hash meta payload
        meta_json_bytes = meta_file.read_bytes()
        if not meta_json_bytes:
            return False
        actual_meta_sha = hashlib.sha256(meta_json_bytes).hexdigest().lower()
        if expected_meta_sha and actual_meta_sha != expected_meta_sha:
            return False

        # 5. Compute combined capture_id
        combined_hasher = hashlib.sha256()
        combined_hasher.update(raw_data_bytes)
        combined_hasher.update(meta_json_bytes)
        computed_capture_id = combined_hasher.hexdigest().lower()

        # Stem must match computed capture ID
        if capture_stem.lower() != computed_capture_id:
            return False
        if expected_capture_id and expected_capture_id != computed_capture_id:
            return False

        # 6. Parse and validate metadata dictionary
        try:
            metadata_dict = json.loads(meta_json_bytes.decode("utf-8"))
            if not isinstance(metadata_dict, dict):
                return False
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return False

        embedded_data_sha = str(metadata_dict.get("global", {}).get("core:sha256", "")).lower()
        if not embedded_data_sha or embedded_data_sha != actual_data_sha:
            return False

        captures = metadata_dict.get("captures")
        if not isinstance(captures, list) or not captures or not isinstance(captures[0], dict):
            return False
        if not captures[0].get("core:datetime"):
            return False

        # 7. Parse and validate manifest dictionary
        try:
            manifest_dict = json.loads(manifest_file.read_text(encoding="utf-8"))
            if not isinstance(manifest_dict, dict):
                return False
        except (OSError, json.JSONDecodeError):
            return False

        if str(manifest_dict.get("capture_id", "")).lower() != computed_capture_id:
            return False
        if str(manifest_dict.get("data_sha256", "")).lower() != actual_data_sha:
            return False
        if str(manifest_dict.get("meta_sha256", "")).lower() != actual_meta_sha:
            return False

        for req_field in ("tenant_id", "plot_id", "capture_timestamp_utc", "radio_profile", "packet_count", "storage_prefix"):
            if req_field not in manifest_dict or manifest_dict[req_field] is None:
                return False

        manifest_tenant = _sanitize_id(str(manifest_dict.get("tenant_id", "")), "tenant_id")
        manifest_plot = _sanitize_id(str(manifest_dict.get("plot_id", "")), "plot_id")

        if expected_tenant and manifest_tenant != expected_tenant:
            return False
        if expected_plot and manifest_plot != expected_plot:
            return False

        # 8. Verify directory namespace hierarchy matches manifest
        resolved_dest = dest_dir.resolve(strict=True)
        if len(resolved_dest.parts) < 2 or resolved_dest.parts[-2] != manifest_tenant or resolved_dest.parts[-1] != manifest_plot:
            return False

        # 9. Verify strictly within storage root if provided
        if storage_root is not None:
            resolved_root = Path(storage_root).resolve(strict=True)
            try:
                resolved_dest.relative_to(resolved_root)
            except ValueError:
                return False

        return True
    except Exception:
        return False
