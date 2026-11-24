"""Canonical frontend-ready plot snapshots produced after ASMAE completion."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import logging
import math
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from services.agribrain.common.plot_namespace import PlotNamespace, _coerce_namespace
from services.agribrain.common.surface_hashing import compute_surface_inventory_hash
from services.agribrain.layer10_sire.surface_contract import (
    SURFACES_SCHEMA_VERSION,
    VALID_PUBLICATION_STATUSES,
    classify_surface_publication,
    validate_declared_publication_status,
)

PLOT_SNAPSHOT_CONTRACT_VERSION = "canonical_plot_snapshot_v1"
logger = logging.getLogger(__name__)
PLOT_SNAPSHOT_RECEIPT_CONTRACT_VERSION = "canonical_plot_snapshot_publication_receipt_v1"
PLOT_PUBLICATION_CONTRACT_VERSION = "canonical_plot_frontend_publication_v1"
_HEX64_REGEX = re.compile(r"^[0-9a-f]{64}$")
PLOT_SNAPSHOT_ROOT = (
    Path(__file__).resolve().parents[1] / "artifacts" / "plot_snapshots"
)

VALID_PUBLICATION_AUTHORITIES = frozenset({
    "CERTIFIED_NUMERICAL",
    "DIAGNOSTIC_ONLY",
    "CONTAINED_PROPOSAL",
})


def resolve_publication_authority(
    *,
    publication_authority: Optional[str] = None,
    frontend_payload: Optional[Dict[str, Any]] = None,
    scientific_result: Optional[Dict[str, Any]] = None,
    snapshot_kind: str = "asmae",
) -> str:
    """Classify versioned scientific publication authority.

    - CERTIFIED_NUMERICAL: Full state posterior with verified covariance/uncertainty vectors.
    - DIAGNOSTIC_ONLY: Bounded diagnostic observations without numerical state certification.
    - CONTAINED_PROPOSAL: Contained experimental proposal for simulation/what-if evaluation.
    """
    fe = frontend_payload or {}
    sci = scientific_result or {}

    has_numerical_evidence = bool(
        sci.get("asmae_numerical_digest")
        or (sci.get("state_means") and sci.get("state_covariances"))
        or (fe.get("asmae_posterior_numerical_record") and (fe.get("asmae_proof") or {}).get("numerical_vector_hash"))
        or sci.get("claims_numerical_authority") is True
        or fe.get("claims_numerical_authority") is True
    )

    explicit_auth: Optional[str] = None
    if publication_authority and str(publication_authority).strip().upper() in VALID_PUBLICATION_AUTHORITIES:
        explicit_auth = str(publication_authority).strip().upper()
    elif fe.get("publication_authority") and str(fe.get("publication_authority")).strip().upper() in VALID_PUBLICATION_AUTHORITIES:
        explicit_auth = str(fe.get("publication_authority")).strip().upper()
    elif sci.get("publication_authority") and str(sci.get("publication_authority")).strip().upper() in VALID_PUBLICATION_AUTHORITIES:
        explicit_auth = str(sci.get("publication_authority")).strip().upper()

    if explicit_auth:
        if explicit_auth in ("DIAGNOSTIC_ONLY", "CONTAINED_PROPOSAL"):
            if sci.get("claims_numerical_authority") is True or fe.get("claims_numerical_authority") is True:
                raise ValueError(
                    f"Publication authority '{explicit_auth}' contradicts explicit claims_numerical_authority=True in evidence"
                )
            if sci.get("asmae_numerical_digest") or (sci.get("state_means") and sci.get("state_covariances")):
                raise ValueError(
                    f"Publication authority '{explicit_auth}' contradicts certified numerical posterior in scientific_result"
                )
            if fe.get("asmae_posterior_numerical_record") or (fe.get("asmae_proof") or {}).get("numerical_vector_hash"):
                raise ValueError(
                    f"Publication authority '{explicit_auth}' contradicts numerical posterior record in frontend_payload"
                )
        return explicit_auth

    # Explicit disclaimers
    if fe.get("claims_numerical_authority") is False or sci.get("claims_numerical_authority") is False:
        if sci.get("asmae_numerical_digest") or (sci.get("state_means") and sci.get("state_covariances")) or fe.get("asmae_posterior_numerical_record"):
            raise ValueError("Contradictory evidence: claims_numerical_authority=False but numerical posterior is present")
        if fe.get("contained_proposal") is True or sci.get("contained_proposal") is True:
            return "CONTAINED_PROPOSAL"
        return "DIAGNOSTIC_ONLY"

    # Explicit claims or numerical records
    if has_numerical_evidence:
        return "CERTIFIED_NUMERICAL"

    return "DIAGNOSTIC_ONLY"

_ASMAE_RUNTIME_FIELDS = frozenset({
    "snapshot_ref",
    "snapshot_status",
    "snapshot_age_days",
    "snapshot_published_at",
    "worldline_event_id",
    "worldline_publish_error",
    "snapshot_publish_error",
    "archive_refresh",
    "archive_refresh_error",
})

# These identities are frozen by the authenticated orchestrator before the
# external worker starts.  Older immutable science nodes do not contain the
# worldline event IDs because those IDs are publication-authority bindings,
# not outputs of the numerical ASMAE kernel.  They must survive the exact-node
# reload used by canonical publication, while any disagreement with a newer
# science node remains a hard integrity failure.
_ASMAE_FROZEN_LINEAGE_FIELDS = (
    "crop_posterior_lineage",
    "crop_worldline_event_id",
    "phenology_worldline_event_id",
    "crop_evidence_ledger_hash",
    "crop_influence_manifest_hash",
)

_CANONICAL_SNAPSHOT_CACHE: Dict[Tuple[str, int, int, int, int, int, int, int, int, str, str], Dict[str, Any]] = {}
_SNAPSHOT_CACHE_LOCK = threading.Lock()


def clear_canonical_snapshot_cache() -> None:
    """Clear memory snapshot cache across all namespaces."""
    with _SNAPSHOT_CACHE_LOCK:
        _CANONICAL_SNAPSHOT_CACHE.clear()


def validate_complete_numerical_record(num_rec: Any) -> Tuple[bool, Optional[str]]:
    """Validate completeness and physical sanity of an ASMAE posterior numerical record.

    Invariant:
        keys(states) == keys(sigmas), |states| > 0
        Every mean must be finite (not bool, int/float, math.isfinite)
        Every sigma must be finite and non-negative (not bool, int/float, math.isfinite, >= 0.0)
    """
    if not isinstance(num_rec, dict):
        return False, "numerical record must be a dict"
    states = num_rec.get("states")
    sigmas = num_rec.get("sigmas")
    if not isinstance(states, dict) or not states:
        return False, "states dictionary is missing, not a dict, or empty"
    if not isinstance(sigmas, dict) or not sigmas:
        return False, "sigmas dictionary is missing, not a dict, or empty"
    if set(states) != set(sigmas):
        return False, f"mismatched states and sigmas keys: {set(states) ^ set(sigmas)}"
    for key, mean in states.items():
        if not isinstance(key, str) or not key.strip():
            return False, f"invalid state key {key!r}"
        sigma = sigmas[key]
        for val_name, val in (("mean", mean), ("sigma", sigma)):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                return False, f"{val_name} for {key} is not numeric ({type(val).__name__})"
            if not math.isfinite(float(val)):
                return False, f"{val_name} for {key} is not finite ({val})"
        if float(sigma) < 0.0:
            return False, f"sigma for {key} is negative ({sigma})"
    return True, None


def validate_certified_numerical_publication(
    num_rec: Any,
    frontend_payload: Dict[str, Any],
    scientific_result: Dict[str, Any],
    node: Optional[Dict[str, Any]] = None,
) -> str:
    """Validate completeness, physical sanity, and exact cryptographic digest agreement.

    Enforces identical author-time and reader-time verification under CERTIFIED_NUMERICAL:
    1. Complete uncertainty validation passes (keys match, finite, non-negative).
    2. The vector numerical hash is recomputed directly from states and sigmas.
    3. num_rec['numerical_vector_hash'] matches recomputed hash.
    4. Mandatory asmae_proof['numerical_vector_hash'] matches recomputed hash.
    5. Mandatory scientific_evidence_lineage['asmae_posterior_vector_hash'] matches recomputed hash.
    6. scientific_result['asmae_numerical_digest'] (if present) matches recomputed hash.
    7. scientific_result.get("asmae", {}).get("asmae_numerical_digest") (if present) matches recomputed hash.
    8. node numerical digest (if present) matches recomputed hash.

    Returns the recomputed actual_num_hash on success; raises ValueError otherwise.
    """
    if num_rec is None:
        raise ValueError("CERTIFIED_NUMERICAL publication requires complete uncertainty: missing numerical posterior record")

    is_num_valid, num_err = validate_complete_numerical_record(num_rec)
    if not is_num_valid:
        raise ValueError(f"CERTIFIED_NUMERICAL publication requires complete uncertainty: {num_err}")

    try:
        try:
            from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash
        except ImportError:
            from layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash
        states = num_rec.get("states", {})
        sigmas = num_rec.get("sigmas", {})
        actual_num_hash = compute_asmae_vector_numerical_hash(states, sigmas)
    except Exception as exc:
        raise ValueError(f"Failed to compute ASMAE vector numerical hash: {exc}") from exc

    claimed_num_hash = num_rec.get("numerical_vector_hash")
    if not claimed_num_hash or claimed_num_hash != actual_num_hash:
        raise ValueError(
            f"ASMAE numerical posterior hash mismatch: recomputed {actual_num_hash} != claimed record {claimed_num_hash}"
        )

    proof = frontend_payload.get("asmae_proof")
    if not isinstance(proof, dict) or not proof.get("numerical_vector_hash"):
        raise ValueError(
            "CERTIFIED_NUMERICAL publication requires mandatory frontend_payload['asmae_proof']['numerical_vector_hash']"
        )
    claimed_proof_hash = proof.get("numerical_vector_hash")
    if claimed_proof_hash != actual_num_hash:
        raise ValueError(
            f"ASMAE proof numerical vector hash mismatch: recomputed {actual_num_hash} != claimed asmae_proof {claimed_proof_hash}"
        )

    lineage = frontend_payload.get("scientific_evidence_lineage")
    if not isinstance(lineage, dict) or not lineage.get("asmae_posterior_vector_hash"):
        raise ValueError(
            "CERTIFIED_NUMERICAL publication requires mandatory frontend_payload['scientific_evidence_lineage']['asmae_posterior_vector_hash']"
        )
    claimed_lineage_hash = lineage.get("asmae_posterior_vector_hash")
    if claimed_lineage_hash != actual_num_hash:
        raise ValueError(
            f"ASMAE lineage numerical vector hash mismatch: recomputed {actual_num_hash} != claimed lineage {claimed_lineage_hash}"
        )

    sci_digest = scientific_result.get("asmae_numerical_digest")
    if sci_digest and sci_digest != actual_num_hash:
        raise ValueError(
            f"ASMAE scientific result numerical digest mismatch: recomputed {actual_num_hash} != claimed digest {sci_digest}"
        )

    sci_asmae_digest = (scientific_result.get("asmae") or {}).get("asmae_numerical_digest")
    if sci_asmae_digest and sci_asmae_digest != actual_num_hash:
        raise ValueError(
            f"ASMAE scientific result nested numerical digest mismatch: recomputed {actual_num_hash} != claimed digest {sci_asmae_digest}"
        )

    if node:
        node_num_hash = (
            (node.get("scientific_result") or {}).get("asmae_numerical_digest")
            or ((node.get("frontend_payload") or {}).get("asmae_posterior_numerical_record") or {}).get("numerical_vector_hash")
            or (node.get("asmae") or {}).get("asmae_numerical_digest")
        )
        if node_num_hash and node_num_hash != actual_num_hash:
            raise ValueError(
                f"ASMAE node numerical digest mismatch: recomputed {actual_num_hash} != claimed node {node_num_hash}"
            )

    return actual_num_hash


def _plot_key(namespace: PlotNamespace) -> str:
    return hashlib.sha256(namespace.stable_key().encode("utf-8")).hexdigest()[:32]


def _plot_dir(namespace: PlotNamespace) -> Path:
    return PLOT_SNAPSHOT_ROOT / _plot_key(namespace)


def _head_path(namespace: PlotNamespace) -> Path:
    return _plot_dir(namespace) / "head.json"


def _read(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    ).encode("utf-8")


def _atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        path.name
        + f".{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with temporary.open("xb") as handle:
            handle.write(_json_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        last_error: Optional[OSError] = None
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                return
            except OSError as exc:
                last_error = exc
                if attempt == 5:
                    break
                time.sleep(0.02 * (2 ** attempt))
        assert last_error is not None
        raise last_error
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


_PLOT_MUTEXES: Dict[str, threading.Lock] = {}
_PLOT_MUTEXES_LOCK = threading.Lock()


def _get_process_plot_mutex(plot_dir_str: str) -> threading.Lock:
    with _PLOT_MUTEXES_LOCK:
        if plot_dir_str not in _PLOT_MUTEXES:
            _PLOT_MUTEXES[plot_dir_str] = threading.Lock()
        return _PLOT_MUTEXES[plot_dir_str]


@contextlib.contextmanager
def _plot_publication_lock(plot_dir: Path, timeout: float = 10.0):
    """Interprocess and thread-safe advisory lock for plot head supersession."""
    plot_dir.mkdir(parents=True, exist_ok=True)
    lock_path = plot_dir / ".head.lock"
    process_mutex = _get_process_plot_mutex(str(plot_dir.resolve()))
    acquired_thread = process_mutex.acquire(timeout=timeout)
    if not acquired_thread:
        raise TimeoutError(f"Timed out after {timeout}s waiting for intra-process thread lock on {plot_dir}")
    fd = -1
    locked_os = False
    try:
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked_os = True
                break
            except (OSError, IOError, PermissionError):
                time.sleep(0.005)
        if not locked_os:
            raise TimeoutError(f"Timed out after {timeout}s waiting for publication OS lock at {lock_path}")
        yield
    finally:
        if locked_os and fd >= 0:
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        process_mutex.release()


LEGACY_HISTORICAL_BENCHMARK_ALLOWLIST = frozenset({
    "L10-SNAP-MITIDJA-202609081200",
    "L10-SNAP-P1B-202609081200",
    "L10-SNAP-P1B-202608151200",
    "L10-SNAP-P1B-202608181200",
    "L10-SNAP-P1B-202608261200",
    "L10-SNAP-P1B-202608311200",
    "ASMAE-SNAPSHOT-17767bfef27763500e30ccc3fefce1d8",
    "ASMAE-SNAPSHOT-4e39ea92eba2db3c85f9972a169f613f",
    "ASMAE-SNAPSHOT-a21c3ebc72353277a18a25771d059b1a",
    "ASMAE-SNAPSHOT-3c77594de7de8f1de2e3a72f72219fd2",
})


def validate_publication_commit_ledger(
    directory: Path,
) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
    """Validate completeness, cryptographic continuity, and integrity of commits.jsonl.

    Enforces:
    1. If commits.jsonl does not exist, returns (True, [], None).
    2. Every line must be a valid JSON object (malformed/truncated lines FAIL CLOSED).
    3. commit_seq must be strictly monotonic starting at 1 (1, 2, 3, ...).
    4. commit_hash must match recomputed sha256 of canonical fields.
    5. parent_commit_hash must link to preceding commit_hash (genesis parent is '0'*64).
    6. snapshot_id must be unique across the ledger (no duplicate commits).
    7. node_hash, frontend_publication_hash, publication_receipt_hash must be non-empty 64-char hex strings.

    Returns:
        (is_valid, records, error_message)
    """
    commits_file = directory / "commits.jsonl"
    head_file = directory / "head.json"
    head = _read(head_file) if head_file.exists() else {}
    has_post_ledger_head = bool(
        head.get("commit_seq") is not None
        or head.get("commit_hash")
    )

    if not commits_file.exists():
        if has_post_ledger_head:
            return False, [], "Missing commit ledger: head contains committed ledger markers (explicit authorized recovery required)"
        return True, [], None

    try:
        content = commits_file.read_text(encoding="utf-8")
    except OSError as exc:
        return False, [], f"Unreadable commits.jsonl: {exc}"

    if not content.strip():
        if has_post_ledger_head:
            return False, [], "Empty commit ledger: head contains committed ledger markers (explicit authorized recovery required)"
        return True, [], None

    lines = content.splitlines()
    records: List[Dict[str, Any]] = []
    seen_entries = set()
    seen_commit_hashes = set()
    seen_receipt_hashes = set()

    for line_idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            if line_idx == len(lines):
                continue
            return False, [], f"Malformed commit ledger: empty line at line {line_idx}"
        try:
            rec = json.loads(line)
        except Exception as exc:
            return False, [], f"Malformed commit ledger JSON at line {line_idx}: {exc}"

        if not isinstance(rec, dict):
            return False, [], f"Malformed commit ledger record at line {line_idx}: not a dict"

        seq = rec.get("commit_seq")
        expected_seq = len(records) + 1
        if seq != expected_seq:
            return False, [], f"Ledger sequence discontinuity at line {line_idx}: expected {expected_seq}, got {seq}"

        sid = rec.get("snapshot_id")
        if not sid or not isinstance(sid, str):
            return False, [], f"Missing or invalid snapshot_id at line {line_idx}"

        rcpt_hash = rec.get("publication_receipt_hash")
        commit_entry_key = (sid, rcpt_hash)
        if commit_entry_key in seen_entries:
            return False, [], f"Duplicate commit entry for snapshot '{sid}' in commit ledger at line {line_idx}"
        seen_entries.add(commit_entry_key)

        if rcpt_hash in seen_receipt_hashes:
            return False, [], f"Duplicate publication_receipt_hash in commit ledger at line {line_idx}"
        seen_receipt_hashes.add(rcpt_hash)

        parent_hash = rec.get("parent_commit_hash")
        expected_parent = records[-1]["commit_hash"] if records else ("0" * 64)
        if parent_hash != expected_parent:
            return False, [], f"Parent commit hash mismatch at line {line_idx}: expected {expected_parent}, got {parent_hash}"
        if not bool(_HEX64_REGEX.fullmatch(str(parent_hash or ""))):
            return False, [], f"Invalid parent_commit_hash at line {line_idx}: expected 64-char lowercase sha256 hex"

        for hkey in ("node_hash", "frontend_publication_hash", "publication_receipt_hash"):
            hval = rec.get(hkey)
            if not hval or not isinstance(hval, str) or not bool(_HEX64_REGEX.fullmatch(hval)):
                return False, [], f"Invalid {hkey} at line {line_idx}: expected 64-char lowercase sha256 hex"

        hashable_rec = {k: v for k, v in rec.items() if k != "commit_hash"}
        computed_hash = hashlib.sha256(_json_bytes(hashable_rec)).hexdigest()
        claimed_hash = rec.get("commit_hash")
        if not claimed_hash or not bool(_HEX64_REGEX.fullmatch(str(claimed_hash))):
            return False, [], f"Invalid commit_hash at line {line_idx}: expected 64-char lowercase sha256 hex"
        if claimed_hash != computed_hash:
            return False, [], f"Commit hash mismatch at line {line_idx}: computed {computed_hash}, claimed {claimed_hash}"

        if claimed_hash in seen_commit_hashes:
            return False, [], f"Duplicate commit_hash in commit ledger at line {line_idx}"
        seen_commit_hashes.add(claimed_hash)

        records.append(rec)

    return True, records, None


def reconcile_publication_ledger_and_head(
    directory: Path,
    ns: PlotNamespace,
) -> Optional[Dict[str, Any]]:
    """Deterministically reconcile ledger commit tip with head.json under crash recovery.

    If a writer crashed after appending & fsyncing commits.jsonl but before updating head.json,
    this function reconciles head.json to the validated ledger tip if all staged artifacts are
    cryptographically intact and scientifically admissible.
    """
    head_file = _head_path(ns)
    is_valid, records, _ = validate_publication_commit_ledger(directory)
    if not is_valid or not records:
        return _read(head_file) if head_file.exists() else None

    tip = records[-1]
    current_head = _read(head_file) if head_file.exists() else {}

    if (
        current_head.get("snapshot_id") == tip["snapshot_id"]
        and current_head.get("commit_hash") == tip["commit_hash"]
        and current_head.get("commit_seq") == tip["commit_seq"]
    ):
        return current_head

    # Interrupted head replacement detected: ledger tip is ahead of head.json
    tip_sid = tip["snapshot_id"]
    node_path = directory / "nodes" / f"{tip_sid}.json"
    if not node_path.exists():
        return current_head if current_head else None

    node = _read(node_path)
    hashable_node = {
        k: v for k, v in node.items()
        if not k.endswith("_ref") and k not in (
            "node_hash", "snapshot_age_seconds", "snapshot_ref",
            "publication_receipt_ref", "publication_receipt_hash",
            "publication_job_id", "frontend_publication_hash",
            "surface_inventory_hash", "validation", "historical"
        )
    }
    computed_node_hash = hashlib.sha256(_json_bytes(hashable_node)).hexdigest()
    if computed_node_hash != tip["node_hash"]:
        return current_head if current_head else None

    job_id_raw = tip.get("publication_job_id") or node.get("job_id") or node.get("publication_job_id") or ""
    safe_job_id = hashlib.sha256(str(job_id_raw).encode("utf-8")).hexdigest()[:32]
    pub_path = directory / "publications" / f"{safe_job_id}.json"
    rcpt_path = directory / "receipts" / f"{safe_job_id}.json"
    if not pub_path.exists() or not rcpt_path.exists():
        return current_head if current_head else None

    pub = _read(pub_path)
    rcpt = _read(rcpt_path)

    # Recompute cryptographic publication hash from content (R2)
    hashable_pub = {
        k: v for k, v in pub.items()
        if not k.endswith("_ref") and k != "publication_hash"
    }
    computed_pub_hash = hashlib.sha256(_json_bytes(hashable_pub)).hexdigest()
    if (
        pub.get("publication_hash") != computed_pub_hash
        or computed_pub_hash != tip["frontend_publication_hash"]
    ):
        return current_head if current_head else None

    # Recompute cryptographic receipt hash from content (R2)
    hashable_rcpt = {
        k: v for k, v in rcpt.items()
        if not k.endswith("_ref") and k != "receipt_hash"
    }
    computed_rcpt_hash = hashlib.sha256(_json_bytes(hashable_rcpt)).hexdigest()
    if (
        rcpt.get("receipt_hash") != computed_rcpt_hash
        or computed_rcpt_hash != tip["publication_receipt_hash"]
    ):
        return current_head if current_head else None

    # Cross-artifact binding verification (R2)
    if pub.get("snapshot_id") != tip_sid or rcpt.get("snapshot_id") != tip_sid:
        return current_head if current_head else None
    if pub.get("node_hash") != tip["node_hash"] or rcpt.get("node_hash") != tip["node_hash"]:
        return current_head if current_head else None
    if rcpt.get("frontend_publication_hash") != tip["frontend_publication_hash"]:
        return current_head if current_head else None

    pub_frontend = pub.get("frontend_payload") or {}
    published_schema_version = str(
        pub_frontend.get("surface_schema_version")
        or pub_frontend.get("schema_version")
        or pub_frontend.get("version")
        or (pub_frontend.get("provenance") or {}).get("surface_schema_version")
        or ""
    )

    reconciled_head = {
        "contract_version": PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": node.get("snapshot_kind") or "layer10_terminal",
        "publication_authority": node.get("publication_authority") or pub.get("publication_authority") or "DIAGNOSTIC_ONLY",
        "tenant_id": ns.tenant_id,
        "farm_id": ns.farm_id,
        "plot_id": ns.plot_id,
        "geometry_hash": node.get("geometry_hash") or "",
        "snapshot_id": tip_sid,
        "node_ref": str(node_path),
        "node_hash": tip["node_hash"],
        "publication_job_id": str(job_id_raw),
        "publication_manifest_hash": node.get("manifest_hash") or pub.get("manifest_hash") or "",
        "crop_posterior_lineage": node.get("crop_posterior_lineage"),
        "crop_worldline_event_id": node.get("crop_worldline_event_id"),
        "phenology_worldline_event_id": node.get("phenology_worldline_event_id"),
        "publication_receipt_ref": str(rcpt_path),
        "publication_receipt_hash": tip["publication_receipt_hash"],
        "frontend_publication_ref": str(pub_path),
        "frontend_publication_hash": tip["frontend_publication_hash"],
        "surface_inventory_hash": pub_frontend.get("surface_inventory_hash"),
        "published_at": pub.get("published_at") or node.get("published_at") or tip["committed_at"],
        "evidence_cutoff_at": pub.get("evidence_cutoff_at") or node.get("evidence_cutoff_at"),
        "observation_window": pub.get("observation_window") or node.get("observation_window"),
        "crop_cycle_id": node.get("crop_cycle_id"),
        "updated_at": tip["committed_at"],
        "commit_seq": tip["commit_seq"],
        "commit_hash": tip["commit_hash"],
    }

    # Verify scientific admission contract before advancing head.json (R2)
    payload_surfaces = pub_frontend.get("surfaces") or pub_frontend.get("surface_pack") or []
    try:
        computed_inv_hash = (
            compute_surface_inventory_hash(payload_surfaces)
            if isinstance(payload_surfaces, list) and payload_surfaces
            else None
        )
    except (TypeError, ValueError):
        computed_inv_hash = None

    derived_publication_status, _ = classify_surface_publication(pub_frontend)
    declared_status_valid, _, _ = validate_declared_publication_status(pub_frontend)

    # Numerical authority check
    num_rec = (
        (node.get("scientific_result") or {}).get("asmae_posterior_numerical_record")
        or (node.get("asmae") or {}).get("asmae_posterior_numerical_record")
        or pub_frontend.get("asmae_posterior_numerical_record")
    )
    numerical_valid = True
    if reconciled_head["publication_authority"] == "CERTIFIED_NUMERICAL":
        try:
            validate_certified_numerical_publication(
                num_rec, pub_frontend, node.get("scientific_result") or node.get("asmae") or {}, node=node
            )
        except (ValueError, TypeError):
            numerical_valid = False

    candidate_validation = {
        "nodeValid": True,
        "publicationValid": True,
        "receiptValid": True,
        "inventoryValid": bool(
            not payload_surfaces
            or (
                reconciled_head.get("surface_inventory_hash")
                and computed_inv_hash
                and reconciled_head.get("surface_inventory_hash") == computed_inv_hash
            )
        ),
        "temporalBindingValid": True,
        "numericalBindingValid": numerical_valid,
        "nodeAgreementValid": True,
        "authorityAgreementValid": True,
        "replayReceiptValid": True,
        "bindingValid": True,
        "lineageValid": bool(
            node.get("snapshot_kind") != "asmae"
            or (
                node.get("crop_posterior_lineage")
                and node.get("crop_worldline_event_id")
                and node.get("phenology_worldline_event_id")
                and pub.get("crop_posterior_lineage") == node.get("crop_posterior_lineage")
                and rcpt.get("crop_posterior_lineage") == node.get("crop_posterior_lineage")
            )
        ),
        "schemaValid": published_schema_version == SURFACES_SCHEMA_VERSION,
        "contractValid": derived_publication_status in VALID_PUBLICATION_STATUSES and numerical_valid,
        "publicationStatusValid": declared_status_valid,
    }

    reconstructed_candidate = {
        **reconciled_head,
        "scientific_result": node.get("scientific_result") or node.get("asmae") or {},
        "frontend_payload": pub_frontend,
        "publication_receipt": rcpt,
        "validation": candidate_validation,
    }
    admission_report = evaluate_snapshot_admission(reconstructed_candidate, namespace=ns)
    if not admission_report.get("is_valid", False):
        # Ledger tip fails scientific admission; do NOT promote to head.json (R2)
        return current_head if current_head else None

    # All checks passed: atomically update head.json to validated tip
    _atomic(head_file, reconciled_head)
    with _SNAPSHOT_CACHE_LOCK:
        keys_to_evict = [k for k in _CANONICAL_SNAPSHOT_CACHE if k[0] == ns.stable_key()]
        for k in keys_to_evict:
            _CANONICAL_SNAPSHOT_CACHE.pop(k, None)
    return reconciled_head
    with _SNAPSHOT_CACHE_LOCK:
        keys_to_evict = [k for k in _CANONICAL_SNAPSHOT_CACHE if k[0] == ns.stable_key()]
        for k in keys_to_evict:
            _CANONICAL_SNAPSHOT_CACHE.pop(k, None)
    return reconciled_head


def _immutable_asmae_payload(
    result: Dict[str, Any],
    *,
    plot_id: str,
    geometry_hash: str,
    snapshot_id: str,
) -> Dict[str, Any]:
    """Bind canonical publication to the immutable ASMAE science node.

    Runner-side worldline/archive fields are attached after the science node
    is written. They are operational receipts, not part of the immutable
    scientific payload. Loading the exact node makes first publication and a
    reintegration retry byte-equivalent instead of order-dependent.
    """
    immutable = copy.deepcopy(result)
    snapshot_ref = str(result.get("snapshot_ref") or "").strip()
    if snapshot_ref:
        from .snapshot_store import SnapshotIntegrityError, load_snapshot_exact

        try:
            exact = load_snapshot_exact(
                plot_id=plot_id,
                geometry_hash=geometry_hash,
                snapshot_ref=snapshot_ref,
                snapshot_id=snapshot_id,
            )
        except SnapshotIntegrityError as exc:
            raise ValueError(
                "canonical publication has no valid immutable ASMAE source"
            ) from exc
        if exact is None:
            raise ValueError(
                "canonical publication immutable ASMAE source is unavailable"
            )
        immutable = exact
        for key in _ASMAE_FROZEN_LINEAGE_FIELDS:
            frozen_value = result.get(key)
            exact_value = immutable.get(key)
            if (
                frozen_value not in (None, "")
                and exact_value not in (None, "")
                and exact_value != frozen_value
            ):
                raise ValueError(
                    f"canonical publication immutable {key} mismatch"
                )
            if exact_value in (None, "") and frozen_value not in (None, ""):
                immutable[key] = copy.deepcopy(frozen_value)
    for key in _ASMAE_RUNTIME_FIELDS:
        immutable.pop(key, None)
    return immutable


def publish_canonical_plot_snapshot(
    *,
    namespace: Optional[Union[PlotNamespace, str]] = None,
    tenant_id: str = "",
    farm_id: str = "",
    plot_id: str = "",
    geometry_hash: str,
    snapshot_id: str,
    asmae_result: Dict[str, Any],
    frontend_payload: Dict[str, Any],
    job_id: str,
    manifest_hash: str,
    execution_identity: Optional[Dict[str, Any]] = None,
    snapshot_kind: str = "asmae",
    allow_overwrite: bool = False,
    publication_authority: Optional[str] = None,
) -> Dict[str, Any]:
    """Write one immutable node, then atomically supersede the plot head."""
    ns = _coerce_namespace(namespace or plot_id, tenant_id=tenant_id, farm_id=farm_id)

    normalized_kind = str(snapshot_kind or "").strip().lower()
    if normalized_kind == "asmae":
        if not str(snapshot_id).startswith("ASMAE-SNAPSHOT-"):
            raise ValueError("canonical ASMAE snapshot_id is invalid")
        if asmae_result.get("snapshot_id") != snapshot_id:
            raise ValueError("ASMAE result snapshot identity mismatch")
    elif normalized_kind == "layer10_terminal":
        if not str(snapshot_id).startswith("L10-"):
            raise ValueError("canonical Layer 10 snapshot_id is invalid")
        if asmae_result.get("snapshot_id") != snapshot_id:
            raise ValueError("Layer 10 result snapshot identity mismatch")
    else:
        raise ValueError("canonical snapshot kind is invalid")
    if frontend_payload.get("intelligence_snapshot_id") != snapshot_id:
        raise ValueError("downstream snapshot identity mismatch")

    scientific_result = (
        _immutable_asmae_payload(
            asmae_result,
            plot_id=ns.plot_id,
            geometry_hash=str(geometry_hash or ""),
            snapshot_id=snapshot_id,
        )
        if normalized_kind == "asmae"
        else copy.deepcopy(asmae_result)
    )

    pub_auth = resolve_publication_authority(
        publication_authority=publication_authority,
        frontend_payload=frontend_payload,
        scientific_result=scientific_result,
        snapshot_kind=normalized_kind,
    )

    directory = _plot_dir(ns)
    node_dir = directory / "nodes"
    node_dir.mkdir(parents=True, exist_ok=True)

    node_path = node_dir / f"{snapshot_id}.json"
    logical_node_ref = str(node_path)
    prior_head = _read(_head_path(ns))

    # The frontend payload is part of both immutable artifacts.  Finalize a
    # private copy before either hash is computed and never mutate it again.
    immutable_frontend_payload = copy.deepcopy(frontend_payload)
    if pub_auth == "DIAGNOSTIC_ONLY":
        immutable_frontend_payload["claims_numerical_authority"] = False
        scientific_result["claims_numerical_authority"] = False
    elif pub_auth == "CERTIFIED_NUMERICAL":
        num_rec = (
            immutable_frontend_payload.get("asmae_posterior_numerical_record")
            or scientific_result.get("asmae_posterior_numerical_record")
        )
        actual_num_hash = validate_certified_numerical_publication(
            num_rec,
            immutable_frontend_payload,
            scientific_result,
        )
        immutable_frontend_payload["claims_numerical_authority"] = True
        scientific_result["claims_numerical_authority"] = True
        if not scientific_result.get("asmae_numerical_digest"):
            scientific_result["asmae_numerical_digest"] = actual_num_hash
        if isinstance(scientific_result.get("asmae"), dict) and not scientific_result["asmae"].get("asmae_numerical_digest"):
            scientific_result["asmae"]["asmae_numerical_digest"] = actual_num_hash
    elif pub_auth == "CONTAINED_PROPOSAL":
        immutable_frontend_payload["claims_numerical_authority"] = False
        scientific_result["claims_numerical_authority"] = False
    immutable_frontend_payload["publication_authority"] = pub_auth
    if normalized_kind == "asmae":
        from services.agribrain.layer05_asmae.reintegration import _mark_completed_publication
        _mark_completed_publication(immutable_frontend_payload, str(job_id))
        evidence_lineage = immutable_frontend_payload.get(
            "scientific_evidence_lineage"
        )
        evidence_lineage = (
            evidence_lineage if isinstance(evidence_lineage, dict) else {}
        )
        for key in (
            "crop_posterior_lineage",
            "crop_worldline_event_id",
            "phenology_worldline_event_id",
        ):
            expected = str(scientific_result.get(key) or "").strip()
            if not expected or str(evidence_lineage.get(key) or "") != expected:
                raise ValueError(
                    f"canonical ASMAE publication {key} mismatch"
                )

    surfaces = immutable_frontend_payload.get("surface_pack") or immutable_frontend_payload.get("surfaces") or []
    if (
        normalized_kind == "asmae"
        and scientific_result.get("visual_allowed") is True
        and bool(scientific_result.get("raster_maps"))
        and not surfaces
    ):
        raise ValueError(
            "canonical ASMAE publication has raster evidence but no surfaces"
        )
    if isinstance(surfaces, list):
        inv_hash = compute_surface_inventory_hash(surfaces)
        immutable_frontend_payload["surface_inventory_hash"] = inv_hash

    publication_timestamp = datetime.now(timezone.utc).isoformat()
    existing_node_for_retry = _read(node_path) if node_path.exists() else None
    if existing_node_for_retry and existing_node_for_retry.get("published_at"):
        published_at_str = str(existing_node_for_retry.get("published_at"))
        publication_timestamp = str(existing_node_for_retry.get("recorded_at") or publication_timestamp)
    else:
        published_at_str = (
            immutable_frontend_payload.get("published_at")
            or immutable_frontend_payload.get("publishedAt")
            or publication_timestamp
        )
    evidence_cutoff_str = (
        scientific_result.get("evidence_cutoff_at")
        or scientific_result.get("evidence_cutoff")
        or scientific_result.get("spatial_evidence_cutoff")
        or scientific_result.get("as_of")
        or (scientific_result.get("plot_state_artifact") or {}).get("spatial_evidence_cutoff")
        or (scientific_result.get("plot_state_artifact") or {}).get("as_of")
        or (scientific_result.get("asmae") or {}).get("spatial_evidence_cutoff")
        or (scientific_result.get("asmae") or {}).get("as_of")
        or ((scientific_result.get("asmae") or {}).get("plot_state_artifact") or {}).get("spatial_evidence_cutoff")
        or ((scientific_result.get("asmae") or {}).get("plot_state_artifact") or {}).get("as_of")
        or immutable_frontend_payload.get("evidence_cutoff_at")
        or immutable_frontend_payload.get("evidenceCutoffAt")
    )
    if hasattr(evidence_cutoff_str, "isoformat"):
        evidence_cutoff_str = evidence_cutoff_str.isoformat()
    evidence_cutoff_str = str(evidence_cutoff_str or "").strip()

    obs_win = (
        immutable_frontend_payload.get("observation_window")
        or immutable_frontend_payload.get("observationWindow")
        or scientific_result.get("observation_window")
    )
    if not obs_win:
        src_win = (
            immutable_frontend_payload.get("source_window")
            or scientific_result.get("source_window")
        )
        if isinstance(src_win, (list, tuple)) and len(src_win) >= 2 and src_win[0] and src_win[1]:
            obs_win = {"start": str(src_win[0]), "end": str(src_win[1])}
        elif isinstance(scientific_result.get("date_range"), dict):
            dr = scientific_result["date_range"]
            if dr.get("start") and dr.get("end"):
                obs_win = {"start": str(dr["start"]), "end": str(dr["end"])}

    # Scientific Provenance Guarantee:
    # A missing scientific evidence cutoff must NEVER be silently replaced
    # with publication time or inferred from observation window bounds.
    # If no validated manifest or processing boundary exists, it remains None/null (unknown).
    if not evidence_cutoff_str:
        evidence_cutoff_str = None

    if not obs_win:
        obs_win = None

    crop_cycle_id = (
        immutable_frontend_payload.get("crop_cycle_id")
        or immutable_frontend_payload.get("cropCycleId")
        or scientific_result.get("crop_cycle_id")
        or (scientific_result.get("operational_context") or {}).get("crop_cycle_id")
        or (scientific_result.get("crop_config") or {}).get("crop_cycle_id")
        or (execution_identity or {}).get("crop_cycle_id")
    )
    if crop_cycle_id:
        crop_cycle_id = str(crop_cycle_id).strip() or None
    else:
        crop_cycle_id = None

    immutable_frontend_payload["published_at"] = published_at_str
    immutable_frontend_payload["evidence_cutoff_at"] = evidence_cutoff_str
    immutable_frontend_payload["observation_window"] = obs_win
    if crop_cycle_id:
        immutable_frontend_payload["crop_cycle_id"] = crop_cycle_id

    envelope: Dict[str, Any] = {
        "contract_version": PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": normalized_kind,
        "publication_authority": pub_auth,
        "snapshot_id": snapshot_id,
        "tenant_id": ns.tenant_id,
        "farm_id": ns.farm_id,
        "plot_id": ns.plot_id,
        "geometry_hash": str(geometry_hash or ""),
        "recorded_at": publication_timestamp,
        "published_at": published_at_str,
        "evidence_cutoff_at": evidence_cutoff_str,
        "observation_window": obs_win,
        "crop_cycle_id": crop_cycle_id,
        "supersedes_snapshot_id": prior_head.get("snapshot_id"),
        "job_id": str(job_id),
        "manifest_hash": str(manifest_hash),
        "crop_posterior_lineage": scientific_result.get("crop_posterior_lineage"),
        "crop_worldline_event_id": scientific_result.get(
            "crop_worldline_event_id"
        ),
        "phenology_worldline_event_id": scientific_result.get(
            "phenology_worldline_event_id"
        ),
        "crop_evidence_ledger_hash": scientific_result.get(
            "crop_evidence_ledger_hash"
        ),
        "crop_influence_manifest_hash": scientific_result.get(
            "crop_influence_manifest_hash"
        ),
        "frontend_payload": immutable_frontend_payload,
    }
    if normalized_kind == "asmae":
        envelope["asmae_content_hash"] = scientific_result.get("content_hash")
        envelope["asmae"] = scientific_result
    else:
        envelope["scientific_content_hash"] = scientific_result.get("content_hash")
        envelope["scientific_result"] = scientific_result

    replay_receipt = (
        scientific_result.get("bitemporal_replay_receipt")
        or (execution_identity or {}).get("bitemporal_replay_receipt")
    )
    if replay_receipt:
        envelope["bitemporal_replay_receipt"] = replay_receipt
        envelope["evidence_set_digest"] = replay_receipt.get("evidence_set_digest")

    hashable_envelope = {k: v for k, v in envelope.items() if not k.endswith("_ref")}
    envelope["node_hash"] = hashlib.sha256(_json_bytes(hashable_envelope)).hexdigest()

    comparable_keys = (
        (
            "contract_version", "snapshot_kind", "snapshot_id",
            "publication_authority",
            "tenant_id", "farm_id", "plot_id", "geometry_hash",
            "asmae_content_hash", "crop_posterior_lineage",
            "crop_worldline_event_id", "phenology_worldline_event_id",
            "crop_evidence_ledger_hash", "crop_influence_manifest_hash",
        )
        if normalized_kind == "asmae"
        else (
            "contract_version", "snapshot_kind", "snapshot_id",
            "publication_authority",
            "tenant_id", "farm_id", "plot_id", "geometry_hash",
            "scientific_content_hash", "crop_posterior_lineage",
            "crop_worldline_event_id", "phenology_worldline_event_id",
            "crop_evidence_ledger_hash", "crop_influence_manifest_hash",
        )
    )

    if node_path.exists():
        existing = _read(node_path)
        if not existing or not existing.get("node_hash"):
            for _ in range(50):
                time.sleep(0.002)
                existing = _read(node_path)
                if existing and existing.get("node_hash"):
                    break
        if not existing or not existing.get("node_hash"):
            with open(node_path, "wb") as handle:
                handle.write(_json_bytes(envelope))
                handle.flush()
                os.fsync(handle.fileno())
            existing = envelope
        existing_num_hash = (
            (existing.get("scientific_result") or {}).get("asmae_numerical_digest")
            or ((existing.get("frontend_payload") or {}).get("asmae_posterior_numerical_record") or {}).get("numerical_vector_hash")
            or (existing.get("asmae") or {}).get("asmae_numerical_digest")
        )
        incoming_num_hash = (
            (envelope.get("scientific_result") or {}).get("asmae_numerical_digest")
            or ((envelope.get("frontend_payload") or {}).get("asmae_posterior_numerical_record") or {}).get("numerical_vector_hash")
            or (envelope.get("asmae") or {}).get("asmae_numerical_digest")
            or ((immutable_frontend_payload.get("asmae_posterior_numerical_record") or {})).get("numerical_vector_hash")
        )
        if existing_num_hash and incoming_num_hash and existing_num_hash != incoming_num_hash:
            raise ValueError(
                f"immutable plot snapshot collision: numerical record mismatch (existing={existing_num_hash}, incoming={incoming_num_hash})"
            )
        if existing_num_hash and not incoming_num_hash:
            raise ValueError("immutable plot snapshot collision: numerical record presence mismatch")
        if not existing_num_hash and incoming_num_hash:
            raise ValueError("immutable plot snapshot collision: numerical record presence mismatch")

        if any(
            (
                (existing.get(key) or "asmae") != envelope.get(key)
                if key == "snapshot_kind" and normalized_kind == "asmae"
                else existing.get(key) != envelope.get(key)
            )
            for key in comparable_keys
        ):
            raise ValueError("immutable plot snapshot collision")
        existing_sci = existing.get("asmae") or existing.get("scientific_result")
        incoming_sci = envelope.get("asmae") or envelope.get("scientific_result")
        if existing_sci and incoming_sci and existing_sci != incoming_sci:
            raise ValueError("immutable plot snapshot collision: scientific result mismatch")
        existing_hashable = {
            key: value for key, value in existing.items() if key != "node_hash"
        }
        if existing.get("node_hash") != hashlib.sha256(
            _json_bytes(existing_hashable)
        ).hexdigest():
            raise ValueError("existing immutable plot snapshot hash is invalid")
        envelope = existing
    else:
        try:
            descriptor = os.open(str(node_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(_json_bytes(envelope))
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            # Wait for winning publisher to finish flushing node file
            existing = {}
            for _ in range(200):
                existing = _read(node_path)
                if existing and existing.get("node_hash"):
                    break
                time.sleep(0.002)

            existing_num_hash = (
                (existing.get("scientific_result") or {}).get("asmae_numerical_digest")
                or ((existing.get("frontend_payload") or {}).get("asmae_posterior_numerical_record") or {}).get("numerical_vector_hash")
                or (existing.get("asmae") or {}).get("asmae_numerical_digest")
            )
            incoming_num_hash = (
                (envelope.get("scientific_result") or {}).get("asmae_numerical_digest")
                or ((envelope.get("frontend_payload") or {}).get("asmae_posterior_numerical_record") or {}).get("numerical_vector_hash")
                or (envelope.get("asmae") or {}).get("asmae_numerical_digest")
                or ((immutable_frontend_payload.get("asmae_posterior_numerical_record") or {})).get("numerical_vector_hash")
            )
            if existing_num_hash and incoming_num_hash and existing_num_hash != incoming_num_hash:
                raise ValueError(
                    f"immutable plot snapshot collision: numerical record mismatch (existing={existing_num_hash}, incoming={incoming_num_hash})"
                )
            if existing_num_hash and not incoming_num_hash:
                raise ValueError("immutable plot snapshot collision: numerical record presence mismatch")
            if not existing_num_hash and incoming_num_hash:
                raise ValueError("immutable plot snapshot collision: numerical record presence mismatch")

            if any(
                (
                    (existing.get(key) or "asmae") != envelope.get(key)
                    if key == "snapshot_kind" and normalized_kind == "asmae"
                    else existing.get(key) != envelope.get(key)
                )
                for key in comparable_keys
            ):
                raise ValueError("immutable plot snapshot collision")

            existing_sci = existing.get("asmae") or existing.get("scientific_result")
            incoming_sci = envelope.get("asmae") or envelope.get("scientific_result")
            if existing_sci and incoming_sci and existing_sci != incoming_sci:
                raise ValueError("immutable plot snapshot collision: scientific result mismatch")

            if existing.get("node_hash") != envelope.get("node_hash"):
                raise ValueError("immutable plot snapshot collision: node content hash mismatch")

            envelope = existing

    publication_dir = directory / "publications"
    publication_dir.mkdir(parents=True, exist_ok=True)
    safe_job_id = hashlib.sha256(str(job_id).encode("utf-8")).hexdigest()[:32]
    publication_path = publication_dir / f"{safe_job_id}.json"
    logical_publication_ref = str(publication_path)

    publication = {
        "contract_version": PLOT_PUBLICATION_CONTRACT_VERSION,
        "snapshot_kind": normalized_kind,
        "publication_authority": pub_auth,
        "tenant_id": ns.tenant_id,
        "farm_id": ns.farm_id,
        "plot_id": ns.plot_id,
        "geometry_hash": str(geometry_hash or ""),
        "snapshot_id": snapshot_id,
        "job_id": str(job_id),
        "manifest_hash": str(manifest_hash),
        "crop_posterior_lineage": envelope.get("crop_posterior_lineage"),
        "crop_worldline_event_id": envelope.get("crop_worldline_event_id"),
        "phenology_worldline_event_id": envelope.get(
            "phenology_worldline_event_id"
        ),
        "node_ref": logical_node_ref,
        "node_hash": envelope.get("node_hash"),
        "frontend_payload": immutable_frontend_payload,
        "published_at": published_at_str,
        "evidence_cutoff_at": evidence_cutoff_str,
        "observation_window": obs_win,
        "crop_cycle_id": crop_cycle_id,
        "recorded_at": publication_timestamp,
    }
    if envelope.get("bitemporal_replay_receipt"):
        publication["bitemporal_replay_receipt"] = envelope["bitemporal_replay_receipt"]
        publication["evidence_set_digest"] = envelope.get("evidence_set_digest")

    hashable_pub = {k: v for k, v in publication.items() if not k.endswith("_ref")}
    publication["publication_hash"] = hashlib.sha256(_json_bytes(hashable_pub)).hexdigest()

    if publication_path.exists():
        existing_publication = _read(publication_path)
        if not existing_publication:
            with open(publication_path, "wb") as handle:
                handle.write(_json_bytes(publication))
                handle.flush()
                os.fsync(handle.fileno())
            existing_publication = publication
        if (
            existing_publication.get("job_id") != str(job_id)
            or existing_publication.get("manifest_hash") != str(manifest_hash)
            or existing_publication.get("snapshot_id") != snapshot_id
            or existing_publication.get("node_hash") != envelope.get("node_hash")
            or existing_publication.get("frontend_payload") != publication.get("frontend_payload")
        ):
            raise ValueError("immutable plot frontend publication collision")
        existing_hashable = {
            key: value for key, value in existing_publication.items()
            if not key.endswith("_ref") and key != "publication_hash"
        }
        if existing_publication.get("publication_hash") != hashlib.sha256(
            _json_bytes(existing_hashable)
        ).hexdigest():
            raise ValueError("existing frontend publication hash is invalid")
        publication = existing_publication
    else:
        try:
            publication_descriptor = os.open(str(publication_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(publication_descriptor, "wb") as handle:
                handle.write(_json_bytes(publication))
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            existing_publication = _read(publication_path)
            if existing_publication.get("publication_hash") != publication.get("publication_hash"):
                raise ValueError("immutable plot frontend publication collision")
            publication = existing_publication

    # Receipt construction is deliberately last: node -> publication ->
    # receipt.  This avoids the former mutation cycle where receipt fields
    # changed the already-hashed frontend payload.
    receipt_dir = directory / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{safe_job_id}.json"
    logical_receipt_ref = str(receipt_path)
    identity = dict(execution_identity or {})
    receipt = {
        "contract_version": PLOT_SNAPSHOT_RECEIPT_CONTRACT_VERSION,
        "snapshot_kind": normalized_kind,
        "publication_authority": pub_auth,
        "tenant_id": ns.tenant_id,
        "farm_id": ns.farm_id,
        "plot_id": ns.plot_id,
        "geometry_hash": str(geometry_hash or ""),
        "snapshot_id": snapshot_id,
        "node_ref": logical_node_ref,
        "node_hash": envelope.get("node_hash"),
        "source_node_job_id": envelope.get("job_id"),
        "source_node_manifest_hash": envelope.get("manifest_hash"),
        "job_id": str(job_id),
        "manifest_hash": str(manifest_hash),
        "crop_posterior_lineage": envelope.get("crop_posterior_lineage"),
        "crop_worldline_event_id": envelope.get("crop_worldline_event_id"),
        "phenology_worldline_event_id": envelope.get(
            "phenology_worldline_event_id"
        ),
        "worker_contract_version": identity.get("worker_contract_version"),
        "capability_contract_version": identity.get("capability_contract_version"),
        "capability_plan_hash": identity.get("capability_plan_hash"),
        "frontend_publication_ref": logical_publication_ref,
        "frontend_publication_hash": publication.get("publication_hash"),
        "equivalence_reason": "scientific_content_hash_equivalent",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    if envelope.get("bitemporal_replay_receipt"):
        receipt["bitemporal_replay_receipt"] = envelope["bitemporal_replay_receipt"]
        receipt["evidence_set_digest"] = envelope.get("evidence_set_digest")

    hashable_receipt = {
        key: value for key, value in receipt.items() if not key.endswith("_ref")
    }
    receipt["receipt_hash"] = hashlib.sha256(
        _json_bytes(hashable_receipt)
    ).hexdigest()

    if receipt_path.exists():
        existing_receipt = _read(receipt_path)
        if not existing_receipt:
            with open(receipt_path, "wb") as handle:
                handle.write(_json_bytes(receipt))
                handle.flush()
                os.fsync(handle.fileno())
            existing_receipt = receipt
        comparable = {k: receipt.get(k) for k in receipt if k not in {"recorded_at", "receipt_hash"}}
        existing_comparable = {k: existing_receipt.get(k) for k in receipt if k not in {"recorded_at", "receipt_hash"}}
        if comparable != existing_comparable:
            raise ValueError("immutable plot snapshot publication receipt collision")
        receipt = existing_receipt
    else:
        try:
            receipt_descriptor = os.open(str(receipt_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(receipt_descriptor, "wb") as handle:
                handle.write(_json_bytes(receipt))
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            existing_receipt = _read(receipt_path)
            comparable = {k: receipt.get(k) for k in receipt if k not in {"recorded_at", "receipt_hash"}}
            existing_comparable = {k: existing_receipt.get(k) for k in receipt if k not in {"recorded_at", "receipt_hash"}}
            if comparable != existing_comparable:
                raise ValueError("immutable plot snapshot publication receipt collision")
            receipt = existing_receipt

    head = {
        "contract_version": PLOT_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_kind": normalized_kind,
        "publication_authority": pub_auth,
        "tenant_id": ns.tenant_id,
        "farm_id": ns.farm_id,
        "plot_id": ns.plot_id,
        "geometry_hash": str(geometry_hash or ""),
        "snapshot_id": snapshot_id,
        "node_ref": logical_node_ref,
        "node_hash": envelope.get("node_hash"),
        "publication_job_id": str(job_id),
        "publication_manifest_hash": str(manifest_hash),
        "crop_posterior_lineage": envelope.get("crop_posterior_lineage"),
        "crop_worldline_event_id": envelope.get("crop_worldline_event_id"),
        "phenology_worldline_event_id": envelope.get(
            "phenology_worldline_event_id"
        ),
        "publication_receipt_ref": logical_receipt_ref,
        "publication_receipt_hash": receipt.get("receipt_hash"),
        "frontend_publication_ref": logical_publication_ref,
        "frontend_publication_hash": publication.get("publication_hash"),
        "surface_inventory_hash": publication.get("frontend_payload", {}).get("surface_inventory_hash"),
        "published_at": published_at_str,
        "evidence_cutoff_at": evidence_cutoff_str,
        "observation_window": obs_win,
        "crop_cycle_id": crop_cycle_id,
        "updated_at": publication_timestamp,
    }
    if envelope.get("bitemporal_replay_receipt"):
        head["bitemporal_replay_receipt"] = envelope["bitemporal_replay_receipt"]
        head["evidence_set_digest"] = envelope.get("evidence_set_digest")

    with _plot_publication_lock(directory):
        reconcile_publication_ledger_and_head(directory, ns)
        current_head_check = _read(_head_path(ns))

        # Idempotent re-publication guard: if snapshot is already the committed head with identical hashes, no-op
        if current_head_check.get("snapshot_id") == snapshot_id:
            if (
                current_head_check.get("node_hash") == envelope.get("node_hash")
                and current_head_check.get("frontend_publication_hash") == publication.get("publication_hash")
                and current_head_check.get("publication_receipt_hash") == receipt.get("receipt_hash")
            ):
                return current_head_check

        if not allow_overwrite:
            if current_head_check.get("snapshot_id") != snapshot_id:
                if prior_head and current_head_check:
                    if current_head_check.get("snapshot_id") != prior_head.get("snapshot_id"):
                        raise ValueError("concurrent publication collision: head was superseded by another process")
                elif not prior_head and current_head_check:
                    raise ValueError("concurrent publication collision: head was initialized by another process")

        # ── Publication Commit Ledger (Append-only hash-bound commit index) ──
        commits_file = directory / "commits.jsonl"
        is_ledger_valid, existing_commits, ledger_err = validate_publication_commit_ledger(directory)
        if not is_ledger_valid:
            raise ValueError(f"Cannot publish snapshot: commit ledger is corrupted: {ledger_err}")

        # Post-ledger store missing ledger guard (R1):
        has_post_ledger_head = bool(
            current_head_check.get("commit_seq") is not None
            or current_head_check.get("commit_hash")
        )
        if has_post_ledger_head and (not commits_file.exists() or commits_file.stat().st_size == 0):
            raise ValueError(
                "Cannot publish snapshot: existing store has committed ledger markers but commits.jsonl is missing or empty; "
                "explicit authorized recovery required"
            )

        # Unreconciled tip quarantine guard (R2):
        if existing_commits and current_head_check:
            tip = existing_commits[-1]
            if (
                current_head_check.get("commit_seq") is not None
                and current_head_check.get("commit_hash") != tip["commit_hash"]
            ):
                raise ValueError(
                    f"Cannot publish snapshot: commit ledger tip '{tip.get('snapshot_id')}' could not be reconciled with head "
                    "(quarantined/repair state required)"
                )

        if not commits_file.exists() and current_head_check and current_head_check.get("snapshot_id"):
            # Bootstrap legacy committed head as genesis commit ONLY if genuinely pre-ledger (no commit markers)
            if not has_post_ledger_head:
                leg_id = current_head_check.get("snapshot_id")
                leg_node_hash = current_head_check.get("node_hash")
                leg_pub_hash = current_head_check.get("frontend_publication_hash")
                leg_rcpt_hash = current_head_check.get("publication_receipt_hash")
                if leg_node_hash and leg_pub_hash and leg_rcpt_hash:
                    leg_rec = {
                        "commit_seq": 1,
                        "snapshot_id": leg_id,
                        "node_hash": leg_node_hash,
                        "frontend_publication_hash": leg_pub_hash,
                        "publication_receipt_hash": leg_rcpt_hash,
                        "publication_job_id": str(current_head_check.get("publication_job_id") or ""),
                        "committed_at": str(current_head_check.get("published_at") or publication_timestamp),
                        "parent_commit_hash": "0" * 64,
                    }
                    leg_rec["commit_hash"] = hashlib.sha256(_json_bytes({k: v for k, v in leg_rec.items() if k != "commit_hash"})).hexdigest()
                    existing_commits.append(leg_rec)

        commit_seq = len(existing_commits) + 1
        parent_commit_hash = existing_commits[-1]["commit_hash"] if existing_commits else ("0" * 64)
        commit_record = {
            "commit_seq": commit_seq,
            "snapshot_id": snapshot_id,
            "node_hash": envelope.get("node_hash"),
            "frontend_publication_hash": publication.get("publication_hash"),
            "publication_receipt_hash": receipt.get("receipt_hash"),
            "publication_job_id": str(job_id),
            "committed_at": publication_timestamp,
            "parent_commit_hash": parent_commit_hash,
        }
        commit_hash = hashlib.sha256(_json_bytes({k: v for k, v in commit_record.items() if k != "commit_hash"})).hexdigest()
        commit_record["commit_hash"] = commit_hash

        # Append commit record to commits.jsonl atomically
        needs_initial_bootstrap = (not commits_file.exists() or commits_file.stat().st_size == 0) and bool(existing_commits[:-1] if commit_seq == 1 else existing_commits)
        with open(commits_file, "a", encoding="utf-8") as f:
            if needs_initial_bootstrap:
                for c in existing_commits[:-1] if commit_seq == 1 else existing_commits:
                    f.write(json.dumps(c, separators=(",", ":")) + "\n")
            f.write(json.dumps(commit_record, separators=(",", ":")) + "\n")
            f.flush()
            os.fsync(f.fileno())

        head["commit_seq"] = commit_seq
        head["commit_hash"] = commit_hash
        _atomic(_head_path(ns), head)
        with _SNAPSHOT_CACHE_LOCK:
            keys_to_evict = [k for k in _CANONICAL_SNAPSHOT_CACHE if k[0] == ns.stable_key()]
            for k in keys_to_evict:
                _CANONICAL_SNAPSHOT_CACHE.pop(k, None)
    return head


def evaluate_snapshot_admission(
    snapshot: Optional[Dict[str, Any]],
    namespace: Optional[PlotNamespace] = None,
) -> Dict[str, Any]:
    """Authoritative shared admission predicate for scientific snapshot authority.

    Evaluates both cryptographic integrity keys and lifecycle contract keys.
    Shared identically by API admission and Layer 10 fallback decision gates.
    """
    if not snapshot or not isinstance(snapshot, dict):
        return {
            "is_valid": False,
            "status": "missing",
            "reason": "missing_snapshot",
            "invalid_integrity_flags": ["snapshotMissing"],
            "invalid_contract_flags": [],
            "quarantined": True,
            "refresh_required": True,
            "publication_authority": None,
        }

    validation = snapshot.get("validation") or {}
    integrity_keys = [
        "nodeValid",
        "publicationValid",
        "receiptValid",
        "inventoryValid",
        "bindingValid",
        "lineageValid",
        "temporalBindingValid",
    ]
    if snapshot.get("bitemporal_replay_receipt"):
        integrity_keys.append("replayReceiptValid")
    contract_keys = (
        "schemaValid",
        "contractValid",
        "publicationStatusValid",
    )

    invalid_integrity = [k for k in integrity_keys if validation.get(k) is not True]

    fe_payload = snapshot.get("frontend_payload") or {}
    pub_auth = (
        snapshot.get("publication_authority")
        or (snapshot.get("contract_validation") or {}).get("publication_authority")
        or fe_payload.get("publication_authority")
        or resolve_publication_authority(
            frontend_payload=fe_payload,
            scientific_result=snapshot.get("asmae") or snapshot.get("scientific_result"),
            snapshot_kind=snapshot.get("snapshot_kind", "asmae"),
        )
    )

    if validation.get("authorityAgreementValid") is False:
        if "authorityAgreementValid" not in invalid_integrity:
            invalid_integrity.append("authorityAgreementValid")

    if pub_auth == "CERTIFIED_NUMERICAL":
        if validation.get("numericalBindingValid") is not True:
            invalid_integrity.append("numericalBindingValid")
        if validation.get("nodeAgreementValid") is not True:
            invalid_integrity.append("nodeAgreementValid")
        num_rec = (
            fe_payload.get("asmae_posterior_numerical_record")
            or (snapshot.get("scientific_result") or {}).get("asmae_posterior_numerical_record")
            or (snapshot.get("asmae") or {}).get("asmae_posterior_numerical_record")
        )
        if num_rec is not None:
            is_num_valid, _ = validate_complete_numerical_record(num_rec)
            if not is_num_valid:
                if "numericalBindingValid" not in invalid_integrity:
                    invalid_integrity.append("numericalBindingValid")
    elif pub_auth in ("DIAGNOSTIC_ONLY", "CONTAINED_PROPOSAL"):
        if validation.get("numericalBindingValid") is False:
            invalid_integrity.append("numericalBindingValid")
        if validation.get("nodeAgreementValid") is False:
            invalid_integrity.append("nodeAgreementValid")
        sci_res = snapshot.get("asmae") or snapshot.get("scientific_result") or {}
        if (
            sci_res.get("asmae_numerical_digest")
            or (sci_res.get("state_means") and sci_res.get("state_covariances"))
            or fe_payload.get("asmae_posterior_numerical_record")
            or (fe_payload.get("asmae_proof") or {}).get("numerical_vector_hash")
            or fe_payload.get("claims_numerical_authority") is True
            or sci_res.get("claims_numerical_authority") is True
        ):
            if "authorityAgreementValid" not in invalid_integrity:
                invalid_integrity.append("authorityAgreementValid")

    if invalid_integrity:
        return {
            "is_valid": False,
            "status": "quarantined",
            "reason": "canonical_head_integrity_invalid",
            "invalid_integrity_flags": invalid_integrity,
            "invalid_contract_flags": [],
            "quarantined": True,
            "refresh_required": True,
            "publication_authority": pub_auth,
        }

    invalid_contract = [k for k in contract_keys if validation.get(k) is not True]
    if invalid_contract:
        return {
            "is_valid": False,
            "status": "stale",
            "reason": "canonical_head_schema_stale",
            "invalid_integrity_flags": [],
            "invalid_contract_flags": invalid_contract,
            "quarantined": False,
            "refresh_required": True,
            "publication_authority": pub_auth,
        }

    return {
        "is_valid": True,
        "status": "admitted",
        "reason": None,
        "invalid_integrity_flags": [],
        "invalid_contract_flags": [],
        "quarantined": False,
        "refresh_required": False,
        "publication_authority": pub_auth,
    }


def publish_canonical_layer10_snapshot(
    *,
    namespace: PlotNamespace,
    geometry_hash: str,
    frontend_payload: Dict[str, Any],
    request_run_id: str,
    crop_cycle_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Publish a validated terminal L10 result when no ASMAE head exists yet.

    A degraded provider-backed result is still a legitimate scientific
    publication.  Keeping it outside the canonical head made the browser wait
    forever even though L10 had completed successfully.  This bridge preserves
    the same immutable node/publication/receipt/head ordering used by ASMAE
    without falsely marking unavailable ASMAE evidence as completed.
    """
    ns = _coerce_namespace(namespace)
    payload = copy.deepcopy(frontend_payload)
    snapshot_id = str(payload.get("intelligence_snapshot_id") or "")
    if snapshot_id.startswith("ASMAE-SNAPSHOT-"):
        existing = load_latest_plot_snapshot(ns, geometry_hash or None, force_verify=True)
        incoming_cycle = crop_cycle_id or payload.get("crop_cycle_id") or payload.get("cropCycleId")
        if (
            existing
            and existing.get("snapshot_id") == snapshot_id
            and (existing.get("crop_cycle_id") or None) == (incoming_cycle or None)
        ):
            return {
                "snapshot_id": snapshot_id,
                "node_hash": existing.get("node_hash"),
                "frontend_publication_hash": existing.get("frontend_publication_hash"),
                "publication_receipt_hash": existing.get("publication_receipt_hash"),
                "surface_inventory_hash": existing.get("surface_inventory_hash"),
            }
        raise ValueError("ASMAE frontend payload has no matching canonical head")
    if not snapshot_id.startswith("L10-"):
        raise ValueError("terminal Layer 10 payload has no canonical snapshot identity")

    requested_crop_cycle_id = (
        crop_cycle_id
        or payload.get("crop_cycle_id")
        or payload.get("cropCycleId")
        or (payload.get("phenology_context") or {}).get("crop_cycle_id")
        or (payload.get("crop_cycle_context") or {}).get("crop_cycle_id")
    )
    requested_crop_cycle_id = str(requested_crop_cycle_id).strip() or None if requested_crop_cycle_id else None

    existing_head = _read(_head_path(ns))
    old_asmae_head = (
        existing_head.get("snapshot_kind") == "asmae"
        or str(existing_head.get("snapshot_id", "")).startswith("ASMAE-SNAPSHOT-")
    )
    if old_asmae_head:
        same_geometry = existing_head.get("geometry_hash") == str(geometry_hash or "")
        same_cycle = (existing_head.get("crop_cycle_id") or None) == requested_crop_cycle_id
        if same_geometry and same_cycle:
            # Prefer a verified ASMAE head only for the very same scientific scope.
            # Uses force_verify=True to inspect actual disk bytes, bypassing in-memory advisory cache.
            verified_head = load_latest_plot_snapshot(ns, geometry_hash or None, force_verify=True)
            admission = evaluate_snapshot_admission(verified_head, ns)
            if admission["is_valid"] and verified_head and verified_head.get("snapshot_id") == existing_head.get("snapshot_id"):
                return {
                    "snapshot_id": existing_head.get("snapshot_id"),
                    "node_hash": existing_head.get("node_hash"),
                    "frontend_publication_hash": existing_head.get("frontend_publication_hash"),
                    "publication_receipt_hash": existing_head.get("publication_receipt_hash"),
                    "surface_inventory_hash": existing_head.get("surface_inventory_hash"),
                }
            else:
                logger.warning(
                    "[SNAPSHOT_STORE] Existing ASMAE head %s failed canonical validation/numerical binding (quarantined). Allowing terminal Layer 10 fallback publication to proceed.",
                    existing_head.get("snapshot_id"),
                )
        if existing_head.get("crop_cycle_id") and not requested_crop_cycle_id:
            verified_head = load_latest_plot_snapshot(ns, geometry_hash or None)
            validation = (verified_head.get("validation") or {}) if isinstance(verified_head, dict) else {}
            if validation.get("numericalBindingValid") is True and validation.get("nodeValid") is True:
                raise ValueError("Cannot replace ASMAE head without a declared crop-cycle scope")
            requested_crop_cycle_id = existing_head.get("crop_cycle_id")
        # Old-scope ASMAE nodes remain immutable in history; the new context
        # may publish its own terminal head without inheriting old authority.

    surfaces = payload.get("surfaces") or payload.get("surface_pack") or []
    if not isinstance(surfaces, list):
        raise ValueError("terminal Layer 10 surface inventory is invalid")
    seen_sids = set()
    deduped_surfs = []
    for s in surfaces:
        sid = str(s.get("surface_id") or "").strip() if isinstance(s, dict) else str(getattr(s, "surface_id", "") or "").strip()
        if sid and sid not in seen_sids:
            deduped_surfs.append(s)
            seen_sids.add(sid)
    surfaces = deduped_surfs
    payload["surfaces"] = surfaces
    inventory_hash = compute_surface_inventory_hash(surfaces)
    payload["surface_inventory_hash"] = inventory_hash

    # ASMAE numerical posterior verification in production publisher (R12-06)
    num_rec = payload.get("asmae_posterior_numerical_record")
    if num_rec is not None:
        if not isinstance(num_rec, dict) or "states" not in num_rec:
            raise ValueError("terminal Layer 10 asmae_posterior_numerical_record is malformed")
        try:
            from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash
        except ImportError:
            from layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash
        states = num_rec.get("states", {})
        sigmas = num_rec.get("sigmas", {})
        try:
            actual_num_hash = compute_asmae_vector_numerical_hash(states, sigmas)
        except Exception as e:
            raise ValueError(f"Failed to compute ASMAE vector numerical hash: {e}") from e

        claimed_num_hash = num_rec.get("numerical_vector_hash")
        claimed_proof_hash = (payload.get("asmae_proof") or {}).get("numerical_vector_hash")
        claimed_lineage_hash = (payload.get("scientific_evidence_lineage") or {}).get("asmae_posterior_vector_hash")

        if not claimed_num_hash or claimed_num_hash != actual_num_hash:
            raise ValueError(
                f"ASMAE numerical posterior hash mismatch: recomputed {actual_num_hash} != claimed record {claimed_num_hash}"
            )
        if not claimed_proof_hash or claimed_proof_hash != actual_num_hash:
            raise ValueError(
                f"ASMAE proof numerical vector hash mismatch: recomputed {actual_num_hash} != claimed asmae_proof {claimed_proof_hash}"
            )
        if not claimed_lineage_hash or claimed_lineage_hash != actual_num_hash:
            raise ValueError(
                f"ASMAE lineage numerical vector hash mismatch: recomputed {actual_num_hash} != claimed lineage {claimed_lineage_hash}"
            )

    resolved_crop_cycle_id = requested_crop_cycle_id
    if resolved_crop_cycle_id:
        resolved_crop_cycle_id = str(resolved_crop_cycle_id).strip() or None
        payload["crop_cycle_id"] = resolved_crop_cycle_id
        payload["cropCycleId"] = resolved_crop_cycle_id

    scientific_identity = {
        "snapshot_id": snapshot_id,
        "plot_id": ns.plot_id,
        "crop_cycle_id": resolved_crop_cycle_id,
        "publication_id": str(payload.get("publication_id") or ""),
        "publication_status": str(payload.get("publication_status") or ""),
        "surface_inventory_hash": inventory_hash,
        "surface_schema_version": str(payload.get("surface_schema_version") or ""),
        "render_authorization_version": str(payload.get("render_authorization_version") or ""),
        "resolved_crop_stage": str(payload.get("resolved_crop_stage") or "UNKNOWN"),
        "phenology_context": copy.deepcopy(payload.get("phenology_context") or {}),
        "source_policy": str(payload.get("source_policy") or "canonical"),
        "crop_posterior_lineage": (
            (payload.get("scientific_evidence_lineage") or {}).get("crop_posterior_lineage")
            if isinstance(payload.get("scientific_evidence_lineage"), dict) and (payload.get("scientific_evidence_lineage") or {}).get("crop_posterior_lineage")
            else (
                (payload.get("asmae_feature_pack") or {}).get("crop_posterior_lineage")
                if isinstance(payload.get("asmae_feature_pack"), dict) and (payload.get("asmae_feature_pack") or {}).get("crop_posterior_lineage")
                else payload.get("crop_posterior_lineage")
            )
        ),
        "crop_worldline_event_id": (
            (payload.get("scientific_evidence_lineage") or {}).get("crop_worldline_event_id")
            if isinstance(payload.get("scientific_evidence_lineage"), dict) and (payload.get("scientific_evidence_lineage") or {}).get("crop_worldline_event_id")
            else payload.get("crop_worldline_event_id")
        ),
        "phenology_worldline_event_id": (
            (payload.get("scientific_evidence_lineage") or {}).get("phenology_worldline_event_id")
            if isinstance(payload.get("scientific_evidence_lineage"), dict) and (payload.get("scientific_evidence_lineage") or {}).get("phenology_worldline_event_id")
            else payload.get("phenology_worldline_event_id")
        ),
        "crop_evidence_ledger_hash": (
            (payload.get("scientific_evidence_lineage") or {}).get("crop_evidence_ledger_hash")
            if isinstance(payload.get("scientific_evidence_lineage"), dict) and (payload.get("scientific_evidence_lineage") or {}).get("crop_evidence_ledger_hash")
            else (
                (payload.get("asmae_feature_pack") or {}).get("crop_evidence_ledger_hash")
                if isinstance(payload.get("asmae_feature_pack"), dict) and (payload.get("asmae_feature_pack") or {}).get("crop_evidence_ledger_hash")
                else payload.get("crop_evidence_ledger_hash")
            )
        ),
        "crop_influence_manifest_hash": (
            (payload.get("scientific_evidence_lineage") or {}).get("crop_influence_manifest_hash")
            if isinstance(payload.get("scientific_evidence_lineage"), dict) and (payload.get("scientific_evidence_lineage") or {}).get("crop_influence_manifest_hash")
            else (
                (payload.get("asmae_feature_pack") or {}).get("crop_influence_manifest_hash")
                if isinstance(payload.get("asmae_feature_pack"), dict) and (payload.get("asmae_feature_pack") or {}).get("crop_influence_manifest_hash")
                else payload.get("crop_influence_manifest_hash")
            )
        ),
        "asmae_numerical_digest": (
            num_rec.get("numerical_vector_hash")
            if isinstance(num_rec, dict) and num_rec.get("numerical_vector_hash")
            else None
        ),
    }
    scientific_identity["content_hash"] = hashlib.sha256(
        _json_bytes(scientific_identity)
    ).hexdigest()
    manifest_identity = {
        "namespace": {
            "tenant_id": ns.tenant_id,
            "farm_id": ns.farm_id,
            "plot_id": ns.plot_id,
        },
        "geometry_hash": str(geometry_hash or ""),
        "request_run_id": str(request_run_id),
        "scientific_content_hash": scientific_identity["content_hash"],
    }
    manifest_hash = hashlib.sha256(_json_bytes(manifest_identity)).hexdigest()
    return publish_canonical_plot_snapshot(
        namespace=ns,
        geometry_hash=str(geometry_hash or ""),
        snapshot_id=snapshot_id,
        asmae_result=scientific_identity,
        frontend_payload=payload,
        job_id=str(request_run_id),
        manifest_hash=manifest_hash,
        execution_identity={
            "worker_contract_version": "synchronous_layer10_terminal_publication_v1",
            "capability_contract_version": str(
                payload.get("render_authorization_version") or ""
            ),
            "crop_cycle_id": resolved_crop_cycle_id,
        },
        snapshot_kind="layer10_terminal",
    )


def load_latest_plot_snapshot(
    namespace: Union[PlotNamespace, str],
    geometry_hash: Optional[str] = None,
    tenant_id: str = "",
    farm_id: str = "",
    force_verify: bool = False,
) -> Optional[Dict[str, Any]]:
    """Load latest canonical plot snapshot.

    Threat Model & Cache Guarantees:
      1. Operational reads (force_verify=False):
         Employs an in-memory advisory cache keyed on filesystem metadata:
         head, node, publication, receipt timestamps AND file sizes.
         Designed for high-throughput dashboard reads under a cooperative filesystem.
      2. Scientific authority reads (force_verify=True):
         Completely bypasses the advisory in-memory cache and recomputes all
         cryptographic SHA-256 hashes (node, publication, receipt, inventory,
         numerical vector digest, temporal binding) directly from raw disk bytes.
         Guarantees tamper detection even if an attacker alters file contents
         while restoring original nanosecond timestamps and padding file sizes.
    """
    ns = _coerce_namespace(namespace, tenant_id=tenant_id, farm_id=farm_id)
    directory = _plot_dir(ns)
    head_file = _head_path(ns)
    if not head_file.exists():
        return None

    head = _read(head_file)
    if head.get("contract_version") != PLOT_SNAPSHOT_CONTRACT_VERSION:
        return None
    if geometry_hash and head.get("geometry_hash") != geometry_hash:
        return None

    has_post_ledger_head = bool(
        head.get("commit_seq") is not None
        or head.get("commit_hash")
    )
    commits_file = directory / "commits.jsonl"

    if has_post_ledger_head:
        if not commits_file.exists() or commits_file.stat().st_size == 0:
            # Post-ledger store missing ledger strictly fails closed (R1)
            return None
        is_ledger_valid, records, _ = validate_publication_commit_ledger(directory)
        if not is_ledger_valid or not records:
            return None
        with _plot_publication_lock(directory):
            reconcile_publication_ledger_and_head(directory, ns)
        head = _read(head_file)
        tip = records[-1]
        if (
            head.get("commit_hash") != tip["commit_hash"]
            or head.get("commit_seq") != tip["commit_seq"]
            or head.get("snapshot_id") != tip["snapshot_id"]
        ):
            return None
    elif commits_file.exists():
        is_ledger_valid, records, _ = validate_publication_commit_ledger(directory)
        if not is_ledger_valid:
            return None
        with _plot_publication_lock(directory):
            reconcile_publication_ledger_and_head(directory, ns)
        head = _read(head_file)

    if force_verify and commits_file.exists():
        is_ledger_valid, records, _ = validate_publication_commit_ledger(directory)
        if not is_ledger_valid or not records:
            return None
        tip = records[-1]
        if (
            head.get("commit_hash") != tip["commit_hash"]
            or head.get("commit_seq") != tip["commit_seq"]
            or head.get("snapshot_id") != tip["snapshot_id"]
        ):
            return None

    snapshot_id = head.get("snapshot_id")
    if not snapshot_id:
        return None

    directory = _plot_dir(ns)
    safe_job_id = hashlib.sha256(str(head.get("publication_job_id", "")).encode("utf-8")).hexdigest()[:32]
    node_path = directory / "nodes" / f"{snapshot_id}.json"
    pub_path = directory / "publications" / f"{safe_job_id}.json"
    receipt_path = directory / "receipts" / f"{safe_job_id}.json"

    try:
        head_stat = head_file.stat()
        head_mtime = head_stat.st_mtime_ns
        head_size = head_stat.st_size
    except OSError:
        head_mtime = 0
        head_size = 0
    try:
        node_stat = node_path.stat()
        node_mtime = node_stat.st_mtime_ns
        node_size = node_stat.st_size
    except OSError:
        node_mtime = 0
        node_size = 0
    try:
        pub_stat = pub_path.stat()
        pub_mtime = pub_stat.st_mtime_ns
        pub_size = pub_stat.st_size
    except OSError:
        pub_mtime = 0
        pub_size = 0
    try:
        receipt_stat = receipt_path.stat()
        receipt_mtime = receipt_stat.st_mtime_ns
        receipt_size = receipt_stat.st_size
    except OSError:
        receipt_mtime = 0
        receipt_size = 0
    try:
        commits_stat = commits_file.stat()
        commits_mtime = commits_stat.st_mtime_ns
        commits_size = commits_stat.st_size
    except OSError:
        commits_mtime = 0
        commits_size = 0

    cache_key = (
        ns.stable_key(),
        head_mtime,
        head_size,
        commits_mtime,
        commits_size,
        node_mtime,
        node_size,
        pub_mtime,
        pub_size,
        receipt_mtime,
        receipt_size,
        str(snapshot_id),
        str(head.get("frontend_publication_hash") or ""),
    )
    if not force_verify:
        with _SNAPSHOT_CACHE_LOCK:
            cached = _CANONICAL_SNAPSHOT_CACHE.get(cache_key)
            if cached is not None:
                return copy.deepcopy(cached)

    if not node_path.exists():
        return None

    node = _read(node_path)
    if (
        node.get("contract_version") != PLOT_SNAPSHOT_CONTRACT_VERSION
        or node.get("plot_id") != ns.plot_id
        or node.get("tenant_id") != ns.tenant_id
        or node.get("farm_id") != ns.farm_id
        or node.get("snapshot_id") != snapshot_id
    ):
        return None

    try:
        recorded = datetime.fromisoformat(
            str(node.get("recorded_at", "")).replace("Z", "+00:00")
        )
        node["snapshot_age_seconds"] = max(
            0.0,
            (datetime.now(timezone.utc) - recorded.astimezone(timezone.utc)).total_seconds(),
        )
    except (ValueError, TypeError):
        node["snapshot_age_seconds"] = None

    publication = _read(pub_path)
    receipt = _read(receipt_path)

    node["snapshot_ref"] = f"nodes/{snapshot_id}.json"
    node["publication_receipt_ref"] = head.get("publication_receipt_ref")
    node["publication_receipt_hash"] = head.get("publication_receipt_hash")
    node["publication_job_id"] = head.get("publication_job_id")
    node["frontend_publication_hash"] = head.get("frontend_publication_hash")
    node["surface_inventory_hash"] = head.get("surface_inventory_hash")

    publication_frontend = publication.get("frontend_payload") or {}
    payload_surfaces = publication_frontend.get("surfaces") or publication_frontend.get("surface_pack") or []

    # SHA-256 cryptographic recomputation validation
    hashable_node = {k: v for k, v in node.items() if not k.endswith("_ref") and k not in ("node_hash", "snapshot_age_seconds", "snapshot_ref", "publication_receipt_ref", "publication_receipt_hash", "publication_job_id", "frontend_publication_hash", "surface_inventory_hash", "validation")}
    computed_node_hash = hashlib.sha256(_json_bytes(hashable_node)).hexdigest()

    computed_pub_hash = None
    if publication:
        hashable_pub = {k: v for k, v in publication.items() if not k.endswith("_ref") and k != "publication_hash"}
        computed_pub_hash = hashlib.sha256(_json_bytes(hashable_pub)).hexdigest()

    computed_receipt_hash = None
    if receipt:
        hashable_receipt = {
            k: v for k, v in receipt.items()
            if not k.endswith("_ref") and k != "receipt_hash"
        }
        computed_receipt_hash = hashlib.sha256(_json_bytes(hashable_receipt)).hexdigest()

    try:
        computed_inv_hash = (
            compute_surface_inventory_hash(payload_surfaces)
            if isinstance(payload_surfaces, list)
            else None
        )
    except (TypeError, ValueError):
        # Immutable legacy/malformed publications remain readable for audit,
        # but can never validate as the canonical browser authority.
        computed_inv_hash = None

    derived_publication_status, contract_reason = classify_surface_publication(
        publication_frontend
    )
    declared_status_valid, _, declared_status_reason = (
        validate_declared_publication_status(publication_frontend)
    )
    published_schema_version = str(
        publication_frontend.get("surface_schema_version")
        or publication_frontend.get("schema_version")
        or publication_frontend.get("version")
        or (publication_frontend.get("provenance") or {}).get(
            "surface_schema_version"
        )
        or ""
    )

    # Authoritative temporal fields derived strictly from hash-verified publication or node
    authoritative_published_at = (
        publication.get("published_at")
        or node.get("published_at")
        or node.get("recorded_at")
    )
    authoritative_evidence_cutoff = (
        publication.get("evidence_cutoff_at")
        or node.get("evidence_cutoff_at")
    )
    authoritative_observation_window = (
        publication.get("observation_window")
        or node.get("observation_window")
    )

    # Cryptographic temporal binding validation:
    # Mutating any head temporal field (published_at, evidence_cutoff_at, observation_window)
    # to contradict the hash-verified publication causes validation failure.
    temporal_binding_valid = bool(
        head.get("published_at") == authoritative_published_at
        and head.get("evidence_cutoff_at") == authoritative_evidence_cutoff
        and head.get("observation_window") == authoritative_observation_window
    )

    # Cryptographic ASMAE numerical binding validation (R12-06 production reader)
    num_rec = publication_frontend.get("asmae_posterior_numerical_record")
    numerical_binding_valid: Optional[bool] = None

    # Check cross-artifact agreement between immutable node and published frontend
    node_num_hash = (
        (node.get("scientific_result") or {}).get("asmae_numerical_digest")
        or ((node.get("frontend_payload") or {}).get("asmae_posterior_numerical_record") or {}).get("numerical_vector_hash")
        or (node.get("asmae") or {}).get("asmae_numerical_digest")
    )
    fe_pub_auth = (
        publication.get("publication_authority")
        or node.get("publication_authority")
        or publication_frontend.get("publication_authority")
    )
    authority_agreement_valid = True
    if fe_pub_auth in ("DIAGNOSTIC_ONLY", "CONTAINED_PROPOSAL"):
        claims_numerical_authority = False
        if node_num_hash or num_rec or (node.get("asmae") or {}).get("state_means"):
            authority_agreement_valid = False
            node_agreement_valid = False
            numerical_binding_valid = False
    elif fe_pub_auth == "CERTIFIED_NUMERICAL":
        claims_numerical_authority = True
    else:
        claims_numerical_authority = bool(
            publication_frontend.get("claims_numerical_authority") is True
            or publication_frontend.get("numerical_authority_claimed") is True
            or (publication_frontend.get("asmae_proof") or {}).get("numerical_vector_hash")
            or (publication_frontend.get("scientific_evidence_lineage") or {}).get("asmae_posterior_vector_hash")
            or node_num_hash
            or (node.get("snapshot_kind") == "asmae" and (node.get("asmae") or {}).get("state_means"))
        )

    node_agreement_valid = True
    if claims_numerical_authority or fe_pub_auth == "CERTIFIED_NUMERICAL":
        try:
            sci_res = node.get("scientific_result") or node.get("asmae") or {}
            validate_certified_numerical_publication(
                num_rec=num_rec,
                frontend_payload=publication_frontend,
                scientific_result=sci_res,
                node=node,
            )
            numerical_binding_valid = True
        except ValueError:
            numerical_binding_valid = False
            node_agreement_valid = False
    elif num_rec is not None:
        try:
            sci_res = node.get("scientific_result") or node.get("asmae") or {}
            validate_certified_numerical_publication(
                num_rec=num_rec,
                frontend_payload=publication_frontend,
                scientific_result=sci_res,
                node=node,
            )
            numerical_binding_valid = True
        except ValueError:
            numerical_binding_valid = False
            node_agreement_valid = False

    replay_receipt_valid = True
    if node.get("bitemporal_replay_receipt"):
        n_rr = node.get("bitemporal_replay_receipt") or {}
        p_rr = publication.get("bitemporal_replay_receipt") or {}
        r_rr = receipt.get("bitemporal_replay_receipt") or {}
        h_rr = head.get("bitemporal_replay_receipt") or {}
        expected_digest = node.get("evidence_set_digest")
        if not expected_digest or n_rr.get("evidence_set_digest") != expected_digest:
            replay_receipt_valid = False
        if p_rr and p_rr.get("evidence_set_digest") != expected_digest:
            replay_receipt_valid = False
        if r_rr and r_rr.get("evidence_set_digest") != expected_digest:
            replay_receipt_valid = False
        if h_rr and h_rr.get("evidence_set_digest") != expected_digest:
            replay_receipt_valid = False

    validation_flags = {
        "nodeValid": bool(node.get("node_hash") and node.get("node_hash") == head.get("node_hash") and node.get("node_hash") == computed_node_hash),
        "publicationValid": bool(publication.get("publication_hash") and publication.get("publication_hash") == head.get("frontend_publication_hash") and publication.get("publication_hash") == computed_pub_hash),
        "receiptValid": bool(receipt.get("receipt_hash") and receipt.get("receipt_hash") == head.get("publication_receipt_hash") and receipt.get("receipt_hash") == computed_receipt_hash),
        "inventoryValid": bool(head.get("surface_inventory_hash") and computed_inv_hash and head.get("surface_inventory_hash") == computed_inv_hash),
        "temporalBindingValid": temporal_binding_valid,
        "numericalBindingValid": numerical_binding_valid,
        "nodeAgreementValid": bool(node_agreement_valid),
        "authorityAgreementValid": bool(authority_agreement_valid),
        "replayReceiptValid": replay_receipt_valid,
        "bindingValid": bool(
            head.get("snapshot_id") == snapshot_id
            and head.get("plot_id") == ns.plot_id
            and head.get("tenant_id") == ns.tenant_id
            and head.get("farm_id") == ns.farm_id
            and publication.get("snapshot_id") == snapshot_id
            and publication.get("node_hash") == node.get("node_hash")
            and receipt.get("snapshot_id") == snapshot_id
            and receipt.get("node_hash") == node.get("node_hash")
            and receipt.get("frontend_publication_hash")
            == publication.get("publication_hash")
            and temporal_binding_valid
            and (numerical_binding_valid is not False)
            and node_agreement_valid
            and replay_receipt_valid
            and (node.get("node_hash") == computed_node_hash)
        ),
        "lineageValid": bool(
            node.get("snapshot_kind") != "asmae"
            or (
                node.get("crop_posterior_lineage")
                and node.get("crop_worldline_event_id")
                and node.get("phenology_worldline_event_id")
                and publication.get("crop_posterior_lineage")
                == node.get("crop_posterior_lineage")
                and publication.get("crop_worldline_event_id")
                == node.get("crop_worldline_event_id")
                and publication.get("phenology_worldline_event_id")
                == node.get("phenology_worldline_event_id")
                and receipt.get("crop_posterior_lineage")
                == node.get("crop_posterior_lineage")
                and receipt.get("crop_worldline_event_id")
                == node.get("crop_worldline_event_id")
                and receipt.get("phenology_worldline_event_id")
                == node.get("phenology_worldline_event_id")
            )
        ),
        # Integrity-valid does not mean scientifically current. These contract
        # flags are deliberately separate so callers can refresh a stale head
        # without misreporting it as cryptographic corruption.
        "schemaValid": published_schema_version == SURFACES_SCHEMA_VERSION,
        "contractValid": derived_publication_status in VALID_PUBLICATION_STATUSES and (numerical_binding_valid is not False) and node_agreement_valid,
        "publicationStatusValid": declared_status_valid,
    }
    effective_publication_status = (
        derived_publication_status
        if (numerical_binding_valid is not False and node_agreement_valid)
        else "INVALID_NUMERICAL_BINDING"
    )
    if not node_agreement_valid:
        effective_contract_reason = (
            "Publication numerical record contradicts stored immutable node"
            if (node_num_hash and num_rec is not None)
            else "Numerical authority claimed but asmae_posterior_numerical_record is missing"
        )
    elif numerical_binding_valid is False:
        effective_contract_reason = "ASMAE numerical vector hash contradicts stored states/sigmas"
    else:
        effective_contract_reason = contract_reason

    node["publication_authority"] = fe_pub_auth or ("CERTIFIED_NUMERICAL" if claims_numerical_authority else "DIAGNOSTIC_ONLY")
    node["validation"] = validation_flags
    node["contract_validation"] = {
        "current_surface_schema_version": SURFACES_SCHEMA_VERSION,
        "published_surface_schema_version": published_schema_version,
        "derived_publication_status": effective_publication_status,
        "contract_reason": effective_contract_reason,
        "declared_status_reason": declared_status_reason,
        "numerical_binding_valid": numerical_binding_valid,
        "numerical_authority_verified": bool(numerical_binding_valid is True and node_agreement_valid and authority_agreement_valid),
        "authority_agreement_valid": bool(authority_agreement_valid),
        "publication_authority": node["publication_authority"],
    }
    if numerical_binding_valid is False or not node_agreement_valid:
        node["scientific_authority_certified"] = False
        node["scientific_publication_authorized"] = False
    node["refresh_required"] = bool(
        all(
            validation_flags[key]
            for key in (
                "nodeValid",
                "publicationValid",
                "receiptValid",
                "inventoryValid",
                "temporalBindingValid",
                "bindingValid",
                "lineageValid",
            )
        )
        and not all(
            validation_flags[key]
            for key in (
                "schemaValid",
                "contractValid",
                "publicationStatusValid",
            )
        )
    )
    published_at_val = authoritative_published_at
    evidence_cutoff_val = authoritative_evidence_cutoff
    obs_win_val = authoritative_observation_window
    authoritative_crop_cycle = (
        publication.get("crop_cycle_id")
        or node.get("crop_cycle_id")
        or (publication_frontend.get("crop_cycle_id") if publication_frontend else None)
    )

    node["published_at"] = published_at_val
    node["evidence_cutoff_at"] = evidence_cutoff_val
    node["observation_window"] = obs_win_val
    if authoritative_crop_cycle:
        node["crop_cycle_id"] = authoritative_crop_cycle
        if publication_frontend:
            publication_frontend["crop_cycle_id"] = authoritative_crop_cycle

    if head.get("commit_seq") is not None:
        node["commit_seq"] = head.get("commit_seq")
    if head.get("commit_hash") is not None:
        node["commit_hash"] = head.get("commit_hash")

    # Return the job-bound frontend publication only after the immutable node
    # hash has been recomputed.  It is a separate hashed artifact, not a
    # mutation of the node.
    if publication_frontend:
        publication_frontend["published_at"] = published_at_val
        publication_frontend["evidence_cutoff_at"] = evidence_cutoff_val
        publication_frontend["observation_window"] = obs_win_val
        node["frontend_payload"] = publication_frontend

    with _SNAPSHOT_CACHE_LOCK:
        if len(_CANONICAL_SNAPSHOT_CACHE) > 20:
            _CANONICAL_SNAPSHOT_CACHE.clear()
        _CANONICAL_SNAPSHOT_CACHE[cache_key] = copy.deepcopy(node)

    return copy.deepcopy(node)


def load_plot_snapshot_by_id(
    snapshot_id: str,
    namespace: Optional[PlotNamespace] = None,
    tenant_id: str = "",
    farm_id: str = "",
    plot_id: str = "",
) -> Optional[Dict[str, Any]]:
    if not snapshot_id:
        return None

    if namespace is not None and namespace.is_valid():
        ns = namespace
    elif tenant_id and farm_id and plot_id:
        ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    else:
        return None

    node_path = _plot_dir(ns) / "nodes" / f"{snapshot_id}.json"
    if not node_path.exists():
        return None

    node = _read(node_path)
    if (
        node.get("snapshot_id") == snapshot_id
        and node.get("tenant_id") == ns.tenant_id
        and node.get("farm_id") == ns.farm_id
        and node.get("plot_id") == ns.plot_id
    ):
        if node.get("bitemporal_replay_receipt"):
            rr = node.get("bitemporal_replay_receipt") or {}
            if node.get("evidence_set_digest") != rr.get("evidence_set_digest"):
                return None
        return node

    return None


def load_and_validate_plot_snapshot_by_id(
    snapshot_id: str,
    namespace: Optional[PlotNamespace] = None,
    tenant_id: str = "",
    farm_id: str = "",
    plot_id: str = "",
) -> Optional[Dict[str, Any]]:
    """Load and independently validate any snapshot (head or historical benchmark).

    Recomputes cryptographic hashes across node, publication, and receipt,
    verifying surface inventory, temporal consistency, and lifecycle contracts.
    """
    if not snapshot_id:
        return None

    if namespace is not None and namespace.is_valid():
        ns = namespace
    elif tenant_id and farm_id and plot_id:
        ns = PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)
    else:
        return None

    directory = _plot_dir(ns)
    head_file = _head_path(ns)
    head_check = _read(head_file) if head_file.exists() else {}
    has_post_ledger_head = bool(
        head_check.get("commit_seq") is not None
        or head_check.get("commit_hash")
    )
    commits_file = directory / "commits.jsonl"

    if has_post_ledger_head:
        if not commits_file.exists() or commits_file.stat().st_size == 0:
            return None
        is_ledger_valid, records, _ = validate_publication_commit_ledger(directory)
        if not is_ledger_valid or not records:
            return None
        with _plot_publication_lock(directory):
            reconcile_publication_ledger_and_head(directory, ns)
    elif commits_file.exists():
        is_ledger_valid, records, _ = validate_publication_commit_ledger(directory)
        if not is_ledger_valid:
            return None
        with _plot_publication_lock(directory):
            reconcile_publication_ledger_and_head(directory, ns)

    # Check if this matches the current canonical plot head first
    latest = load_latest_plot_snapshot(ns, force_verify=True)
    if latest and str(latest.get("snapshot_id") or "") == snapshot_id:
        return copy.deepcopy(latest)
    node_path = directory / "nodes" / f"{snapshot_id}.json"
    if not node_path.exists():
        return None

    node = _read(node_path)
    if (
        node.get("contract_version") != PLOT_SNAPSHOT_CONTRACT_VERSION
        or node.get("plot_id") != ns.plot_id
        or node.get("tenant_id") != ns.tenant_id
        or node.get("farm_id") != ns.farm_id
        or node.get("snapshot_id") != snapshot_id
    ):
        return None

    # Verify node cryptographic hash
    hashable_node = {
        k: v for k, v in node.items()
        if not k.endswith("_ref") and k not in (
            "node_hash", "snapshot_age_seconds", "snapshot_ref",
            "publication_receipt_ref", "publication_receipt_hash",
            "publication_job_id", "frontend_publication_hash",
            "surface_inventory_hash", "validation", "historical"
        )
    }
    computed_node_hash = hashlib.sha256(_json_bytes(hashable_node)).hexdigest()
    if not node.get("node_hash") or node.get("node_hash") != computed_node_hash:
        return None

    job_id = node.get("job_id") or node.get("publication_job_id")
    if not job_id:
        return None

    safe_job_id = hashlib.sha256(str(job_id).encode("utf-8")).hexdigest()[:32]
    pub_path = directory / "publications" / f"{safe_job_id}.json"
    receipt_path = directory / "receipts" / f"{safe_job_id}.json"
    if not pub_path.exists() or not receipt_path.exists():
        return None

    publication = _read(pub_path)
    receipt = _read(receipt_path)

    # Recompute cryptographic publication and receipt hashes
    hashable_pub = {
        k: v for k, v in publication.items()
        if not k.endswith("_ref") and k != "publication_hash"
    }
    computed_pub_hash = hashlib.sha256(_json_bytes(hashable_pub)).hexdigest()
    if not publication.get("publication_hash") or publication.get("publication_hash") != computed_pub_hash:
        return None

    hashable_receipt = {
        k: v for k, v in receipt.items()
        if not k.endswith("_ref") and k != "receipt_hash"
    }
    computed_receipt_hash = hashlib.sha256(_json_bytes(hashable_receipt)).hexdigest()
    if not receipt.get("receipt_hash") or receipt.get("receipt_hash") != computed_receipt_hash:
        return None

    # Cross-artifact binding
    if publication.get("snapshot_id") != snapshot_id or receipt.get("snapshot_id") != snapshot_id:
        return None
    if publication.get("node_hash") != node.get("node_hash") or receipt.get("node_hash") != node.get("node_hash"):
        return None
    if receipt.get("frontend_publication_hash") != publication.get("publication_hash"):
        return None

    # Verify publication commit identity:
    # A candidate is eligible for historical/exact retrieval if and only if it
    # won a genuine publication commit recorded in the append-only commit index.
    # Losing candidates from concurrent publication races remain uncommitted and unavailable.
    commits_file = directory / "commits.jsonl"
    commit_record = None
    if commits_file.exists():
        # 1. Full cryptographic validation of the ledger chain
        is_ledger_valid, records, ledger_err = validate_publication_commit_ledger(directory)
        if not is_ledger_valid:
            # Corrupted, malformed, or tampered ledger strictly fails closed
            return None

        # 2. Deterministic reconciliation under lock if crash left ledger ahead of head
        with _plot_publication_lock(directory):
            reconcile_publication_ledger_and_head(directory, ns)

        matching_commits = [r for r in records if r.get("snapshot_id") == snapshot_id]
        commit_record = next(
            (r for r in matching_commits if r.get("publication_receipt_hash") == receipt.get("receipt_hash")),
            matching_commits[-1] if matching_commits else None,
        )
        if commit_record:
            if (
                commit_record.get("node_hash") != node.get("node_hash")
                or commit_record.get("frontend_publication_hash") != publication.get("publication_hash")
                or commit_record.get("publication_receipt_hash") != receipt.get("receipt_hash")
            ):
                return None
        else:
            # Candidate is NOT in the committed ledger.
            # It is admitted ONLY if:
            # 1. It is present in LEGACY_HISTORICAL_BENCHMARK_ALLOWLIST; OR
            # 2. It is an authentic pre-index legacy snapshot:
            #    - Recorded/published strictly prior to the earliest ledger commit; AND
            #    - Reachable by walking strictly BACKWARD along supersedes_snapshot_id from the earliest committed node.
            legacy_admitted = False
            if snapshot_id in LEGACY_HISTORICAL_BENCHMARK_ALLOWLIST:
                legacy_admitted = True
            else:
                first_committed_at_str = records[0].get("committed_at") if records else None
                cand_prior_to_ledger = False
                if first_committed_at_str:
                    try:
                        first_committed_at = datetime.fromisoformat(str(first_committed_at_str).replace("Z", "+00:00")).astimezone(timezone.utc)
                        cand_time_str = node.get("recorded_at") or node.get("published_at")
                        if cand_time_str:
                            cand_time = datetime.fromisoformat(str(cand_time_str).replace("Z", "+00:00")).astimezone(timezone.utc)
                            if cand_time < first_committed_at:
                                cand_prior_to_ledger = True
                    except Exception:
                        cand_prior_to_ledger = False

                if cand_prior_to_ledger:
                    earliest_node_id = records[0].get("snapshot_id")
                    anc_id = earliest_node_id
                    visited = set()
                    while anc_id and anc_id not in visited:
                        visited.add(anc_id)
                        anc_node_path = directory / "nodes" / f"{anc_id}.json"
                        if not anc_node_path.exists():
                            break
                        anc_data = _read(anc_node_path)
                        parent_id = anc_data.get("supersedes_snapshot_id")
                        if parent_id == snapshot_id:
                            legacy_admitted = True
                            break
                        anc_id = parent_id

            if not legacy_admitted:
                return None
    else:
        # commits.jsonl DOES NOT EXIST (Legacy plot prior to ledger introduction)
        head_file = _head_path(ns)
        if not head_file.exists():
            return None
        current_head = _read(head_file)
        if current_head.get("commit_seq") is not None or current_head.get("commit_hash"):
            # Post-ledger store missing ledger strictly fails closed (R1)
            return None
        legacy_verified = False
        if current_head.get("snapshot_id") == snapshot_id:
            legacy_verified = True
        elif snapshot_id in LEGACY_HISTORICAL_BENCHMARK_ALLOWLIST:
            legacy_verified = True
        else:
            # Walk strictly BACKWARD from legacy head.json
            head_node_path = directory / "nodes" / f"{current_head.get('snapshot_id')}.json"
            if head_node_path.exists():
                anc_id = _read(head_node_path).get("supersedes_snapshot_id")
                visited = set()
                while anc_id and anc_id not in visited:
                    visited.add(anc_id)
                    if anc_id == snapshot_id:
                        legacy_verified = True
                        break
                    anc_path = directory / "nodes" / f"{anc_id}.json"
                    if not anc_path.exists():
                        break
                    anc_id = _read(anc_path).get("supersedes_snapshot_id")

        if not legacy_verified:
            return None

    publication_frontend = publication.get("frontend_payload") or {}
    payload_surfaces = publication_frontend.get("surfaces") or publication_frontend.get("surface_pack") or []
    try:
        computed_inv_hash = (
            compute_surface_inventory_hash(payload_surfaces)
            if isinstance(payload_surfaces, list)
            else None
        )
    except (TypeError, ValueError):
        computed_inv_hash = None

    expected_inv_hash = (
        publication_frontend.get("surface_inventory_hash")
        or receipt.get("surface_inventory_hash")
        or node.get("surface_inventory_hash")
    )
    inventory_valid = bool(
        computed_inv_hash and (
            not expected_inv_hash or computed_inv_hash == expected_inv_hash
        )
    )

    # Temporal fields
    authoritative_published_at = (
        publication.get("published_at")
        or node.get("published_at")
        or node.get("recorded_at")
    )
    authoritative_evidence_cutoff = (
        publication.get("evidence_cutoff_at")
        or node.get("evidence_cutoff_at")
    )
    authoritative_observation_window = (
        publication.get("observation_window")
        or node.get("observation_window")
    )
    temporal_binding_valid = bool(
        (node.get("published_at") or authoritative_published_at) == authoritative_published_at
        and (node.get("evidence_cutoff_at") or authoritative_evidence_cutoff) == authoritative_evidence_cutoff
        and (node.get("observation_window") or authoritative_observation_window) == authoritative_observation_window
    )

    # Bitemporal replay receipt verification
    replay_receipt_valid = True
    if node.get("bitemporal_replay_receipt"):
        n_rr = node.get("bitemporal_replay_receipt") or {}
        p_rr = publication.get("bitemporal_replay_receipt") or {}
        r_rr = receipt.get("bitemporal_replay_receipt") or {}
        expected_digest = node.get("evidence_set_digest")
        if not expected_digest or n_rr.get("evidence_set_digest") != expected_digest:
            replay_receipt_valid = False
        if p_rr and p_rr.get("evidence_set_digest") != expected_digest:
            replay_receipt_valid = False
        if r_rr and r_rr.get("evidence_set_digest") != expected_digest:
            replay_receipt_valid = False

    # Numerical binding verification
    num_rec = publication_frontend.get("asmae_posterior_numerical_record")
    node_num_hash = (
        (node.get("scientific_result") or {}).get("asmae_numerical_digest")
        or ((node.get("frontend_payload") or {}).get("asmae_posterior_numerical_record") or {}).get("numerical_vector_hash")
        or (node.get("asmae") or {}).get("asmae_numerical_digest")
    )
    fe_pub_auth = (
        publication.get("publication_authority")
        or node.get("publication_authority")
        or publication_frontend.get("publication_authority")
    )
    authority_agreement_valid = True
    if fe_pub_auth in ("DIAGNOSTIC_ONLY", "CONTAINED_PROPOSAL"):
        claims_numerical_authority = False
        if node_num_hash or num_rec or (node.get("asmae") or {}).get("state_means"):
            authority_agreement_valid = False
            node_agreement_valid = False
            numerical_binding_valid = False
    elif fe_pub_auth == "CERTIFIED_NUMERICAL":
        claims_numerical_authority = True
    else:
        claims_numerical_authority = bool(
            publication_frontend.get("claims_numerical_authority") is True
            or publication_frontend.get("numerical_authority_claimed") is True
            or (publication_frontend.get("asmae_proof") or {}).get("numerical_vector_hash")
            or (publication_frontend.get("scientific_evidence_lineage") or {}).get("asmae_posterior_vector_hash")
            or node_num_hash
            or (node.get("snapshot_kind") == "asmae" and (node.get("asmae") or {}).get("state_means"))
        )
    numerical_binding_valid: Optional[bool] = None
    node_agreement_valid = True
    if claims_numerical_authority or fe_pub_auth == "CERTIFIED_NUMERICAL":
        try:
            sci_res = node.get("scientific_result") or node.get("asmae") or {}
            validate_certified_numerical_publication(
                num_rec=num_rec,
                frontend_payload=publication_frontend,
                scientific_result=sci_res,
                node=node,
            )
            numerical_binding_valid = True
        except ValueError:
            numerical_binding_valid = False
            node_agreement_valid = False
    elif num_rec is not None:
        try:
            sci_res = node.get("scientific_result") or node.get("asmae") or {}
            validate_certified_numerical_publication(
                num_rec=num_rec,
                frontend_payload=publication_frontend,
                scientific_result=sci_res,
                node=node,
            )
            numerical_binding_valid = True
        except ValueError:
            numerical_binding_valid = False
            node_agreement_valid = False

    derived_publication_status, contract_reason = classify_surface_publication(publication_frontend)
    declared_status_valid, _, declared_status_reason = validate_declared_publication_status(publication_frontend)
    published_schema_version = str(
        publication_frontend.get("surface_schema_version")
        or publication_frontend.get("schema_version")
        or publication_frontend.get("version")
        or (publication_frontend.get("provenance") or {}).get("surface_schema_version")
        or ""
    )

    validation_flags = {
        "nodeValid": True,
        "publicationValid": True,
        "receiptValid": True,
        "inventoryValid": inventory_valid,
        "temporalBindingValid": temporal_binding_valid,
        "numericalBindingValid": numerical_binding_valid,
        "nodeAgreementValid": bool(node_agreement_valid),
        "authorityAgreementValid": bool(authority_agreement_valid),
        "replayReceiptValid": replay_receipt_valid,
        "bindingValid": bool(
            publication.get("snapshot_id") == snapshot_id
            and publication.get("node_hash") == node.get("node_hash")
            and receipt.get("snapshot_id") == snapshot_id
            and receipt.get("node_hash") == node.get("node_hash")
            and receipt.get("frontend_publication_hash") == publication.get("publication_hash")
            and temporal_binding_valid
            and (numerical_binding_valid is not False)
            and node_agreement_valid
            and replay_receipt_valid
        ),
        "lineageValid": bool(
            node.get("snapshot_kind") != "asmae"
            or (
                node.get("crop_posterior_lineage")
                and node.get("crop_worldline_event_id")
                and node.get("phenology_worldline_event_id")
                and publication.get("crop_posterior_lineage") == node.get("crop_posterior_lineage")
                and receipt.get("crop_posterior_lineage") == node.get("crop_posterior_lineage")
                and publication.get("crop_worldline_event_id") == node.get("crop_worldline_event_id")
                and receipt.get("crop_worldline_event_id") == node.get("crop_worldline_event_id")
                and publication.get("phenology_worldline_event_id") == node.get("phenology_worldline_event_id")
                and receipt.get("phenology_worldline_event_id") == node.get("phenology_worldline_event_id")
            )
        ),
        "schemaValid": bool(published_schema_version == SURFACES_SCHEMA_VERSION),
        "contractValid": bool(derived_publication_status in VALID_PUBLICATION_STATUSES),
        "publicationStatusValid": bool(declared_status_valid),
    }

    try:
        recorded = datetime.fromisoformat(
            str(node.get("recorded_at", "")).replace("Z", "+00:00")
        )
        node["snapshot_age_seconds"] = max(
            0.0,
            (datetime.now(timezone.utc) - recorded.astimezone(timezone.utc)).total_seconds(),
        )
    except (ValueError, TypeError):
        node["snapshot_age_seconds"] = None

    node["snapshot_ref"] = f"nodes/{snapshot_id}.json"
    node["publication_receipt_ref"] = f"receipts/{safe_job_id}.json"
    node["publication_receipt_hash"] = receipt.get("receipt_hash")
    node["publication_job_id"] = job_id
    node["frontend_publication_hash"] = publication.get("publication_hash")
    node["surface_inventory_hash"] = computed_inv_hash or expected_inv_hash
    node["frontend_payload"] = copy.deepcopy(publication_frontend)
    node["published_at"] = authoritative_published_at
    node["evidence_cutoff_at"] = authoritative_evidence_cutoff
    node["observation_window"] = authoritative_observation_window
    node["validation"] = validation_flags
    node["publication_authority"] = fe_pub_auth or ("CERTIFIED_NUMERICAL" if claims_numerical_authority else "DIAGNOSTIC_ONLY")
    node["contract_validation"] = {
        "schema_valid": validation_flags["schemaValid"],
        "contract_valid": validation_flags["contractValid"],
        "publication_status_valid": validation_flags["publicationStatusValid"],
        "published_schema_version": published_schema_version,
        "derived_publication_status": derived_publication_status,
        "numerical_authority_verified": bool(numerical_binding_valid is True and node_agreement_valid and authority_agreement_valid),
        "authority_agreement_valid": bool(authority_agreement_valid),
        "temporal_binding_verified": bool(temporal_binding_valid),
        "publication_authority": node["publication_authority"],
    }
    if commit_record:
        node["commit_seq"] = commit_record.get("commit_seq")
        node["commit_hash"] = commit_record.get("commit_hash")
    node["historical"] = True
    return node
