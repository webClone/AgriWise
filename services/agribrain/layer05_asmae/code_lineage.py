"""Immutable code/build receipts for externally executed ASMAE science."""

from __future__ import annotations

import hashlib
import platform
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOTS = (
    REPO_ROOT / "services" / "agribrain",
)
EXCLUDED_SOURCE_PARTS = {"artifacts", "tests", "__pycache__"}
CODE_LINEAGE_CONTRACT_VERSION = "asmae_code_lineage_v2_full_backend_closure"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scientific_source_files() -> Iterable[Path]:
    files = set()
    for root in SOURCE_ROOTS:
        if root.is_dir():
            files.update(
                path for path in root.rglob("*.py")
                if not EXCLUDED_SOURCE_PARTS.intersection(
                    path.relative_to(root).parts
                )
            )
    return sorted(files, key=lambda path: path.relative_to(REPO_ROOT).as_posix())


@lru_cache(maxsize=1)
def scientific_source_digest() -> str:
    """Hash source paths and exact bytes; independent of Git availability."""
    digest = hashlib.sha256()
    for path in _scientific_source_files():
        relative = path.relative_to(REPO_ROOT).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def operational_build_receipt(
    *,
    source_bundle_digest: str,
    config_hash: str,
    manifest_hash: str,
    phase: str,
    launch_generation: int,
    input_snapshot_id: str = "",
) -> Dict[str, Any]:
    executable = Path(sys.executable).resolve()
    return {
        "receipt_contract_version": CODE_LINEAGE_CONTRACT_VERSION,
        "operational_attempt_id": (
            f"ASMAE-ATTEMPT-{source_bundle_digest[:12]}-{launch_generation}"
        ),
        "source_bundle_digest": source_bundle_digest,
        "worker_executable": str(executable),
        "worker_executable_sha256": sha256_file(executable),
        "python_version": platform.python_version(),
        "config_hash": str(config_hash or ""),
        "manifest_hash": str(manifest_hash or ""),
        "phase": str(phase),
        "launch_generation": int(launch_generation),
        "input_snapshot_id": str(input_snapshot_id or ""),
        "reserved_at": datetime.now(timezone.utc).isoformat(),
    }
