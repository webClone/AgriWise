"""Portable, content-addressed identities for externally referenced rasters."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


ARTIFACT_REFERENCE_IDENTITY_VERSION = "asmae_artifact_reference_identity_v1"
REFERENCE_COLLECTION_KEYS = frozenset({
    "band_refs", "mask_refs", "local_cache_refs",
})
_DIGEST_KEYS = (
    "file_sha256", "sha256", "content_sha256", "artifact_sha256",
)
_PATH_KEYS = ("path", "local_path", "file_path", "ref")


class ArtifactIdentityError(ValueError):
    """Raised when referenced scientific bytes cannot be identified exactly."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def referenced_path(value: Any) -> Optional[Path]:
    if isinstance(value, Path):
        return value.expanduser()
    if isinstance(value, str):
        return Path(value).expanduser()
    if isinstance(value, Mapping):
        for key in _PATH_KEYS:
            raw = value.get(key)
            if isinstance(raw, (str, Path)) and str(raw):
                return Path(raw).expanduser()
    return None


def _declared_digest(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    for key in _DIGEST_KEYS:
        digest = str(value.get(key) or "").lower()
        if len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest):
            return digest
    return ""


def artifact_reference_identity(value: Any, role: str) -> Dict[str, Any]:
    """Return an identity that never includes a host-local filesystem path."""
    path = referenced_path(value)
    declared = _declared_digest(value)
    if path is not None and path.is_file():
        digest = _sha256_file(path)
        if declared and declared != digest:
            raise ArtifactIdentityError(
                f"declared digest does not match referenced artifact bytes: {role}"
            )
        size = path.stat().st_size
    elif declared:
        digest = declared
        raw_size = value.get("size") if isinstance(value, Mapping) else None
        try:
            size = int(raw_size) if raw_size is not None else None
        except (TypeError, ValueError):
            size = None
    else:
        raise ArtifactIdentityError(
            f"referenced scientific artifact is unreadable and has no exact digest: {role}"
        )

    identity: Dict[str, Any] = {
        "version": ARTIFACT_REFERENCE_IDENTITY_VERSION,
        "logical_artifact_id": f"{role}:{digest[:24]}",
        "role": str(role),
        "file_sha256": digest,
        "portable_uri": f"sha256:{digest}",
        "size": size,
    }
    if isinstance(value, Mapping):
        for key in ("shape", "dtype", "width", "height", "count"):
            if value.get(key) is not None:
                identity[key] = value.get(key)
    return identity


def canonicalize_artifact_references(value: Any, key_hint: str = "") -> Any:
    """Replace operational raster paths with exact portable identities."""
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        if key_hint in REFERENCE_COLLECTION_KEYS:
            for role, item in sorted(value.items(), key=lambda pair: str(pair[0])):
                result[str(role)] = artifact_reference_identity(
                    item, f"{key_hint}:{role}"
                )
            return result
        for key, item in value.items():
            name = str(key)
            result[name] = canonicalize_artifact_references(item, name)
        return result
    if isinstance(value, list):
        if key_hint in REFERENCE_COLLECTION_KEYS:
            return [
                artifact_reference_identity(item, f"{key_hint}:{index}")
                for index, item in enumerate(value)
            ]
        return [canonicalize_artifact_references(item, key_hint) for item in value]
    if isinstance(value, tuple):
        return tuple(canonicalize_artifact_references(item, key_hint) for item in value)
    if key_hint in REFERENCE_COLLECTION_KEYS:
        return artifact_reference_identity(value, key_hint)
    return value
