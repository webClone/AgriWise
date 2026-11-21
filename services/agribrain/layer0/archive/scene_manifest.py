"""
Historical scene manifest and serialization logic.
"""
from __future__ import annotations

import os
import json
import time
import hashlib
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple

from .archive_policy import (
    ARCHIVE_POLICY_VERSION,
    QUALITY_POLICY_VERSION,
    HARMONIZATION_POLICY_VERSION,
    OPERATOR_POLICY_VERSION,
    RETROVALIDATION_POLICY_VERSION
)

@dataclass(frozen=True)
class HistoricalSceneRecord:
    scene_id: str
    plot_id: str
    geometry_hash: str

    source: str                  # sentinel2, sentinel1
    mission: str                 # S2A, S2B, S1A, S1B
    product_level: str           # L1C, L2A, GRD, RTC, etc.
    collection: Optional[str]

    acquisition_time: str
    orbit_number: Optional[str]
    relative_orbit: Optional[str]
    tile_id: Optional[str]

    native_resolution_m: float
    crs: str
    transform_hash: str
    footprint_hash: str

    cloud_score: Optional[float]
    valid_pixel_fraction: float
    quality_status: str          # candidate, accepted, rejected
    source_content_hash: str
    rejection_reasons: List[str] = field(default_factory=list)

    bands_available: List[str] = field(default_factory=list)
    masks_available: List[str] = field(default_factory=list)

    remote_asset_refs: Dict[str, Any] = field(default_factory=dict)
    local_cache_refs: Dict[str, Any] = field(default_factory=dict)

    manifest_record_hash: str = ""

    # Policy versions to prevent stale cache reuse
    archive_policy_version: str = ARCHIVE_POLICY_VERSION
    quality_policy_version: str = QUALITY_POLICY_VERSION
    harmonization_policy_version: str = HARMONIZATION_POLICY_VERSION
    operator_policy_version: str = OPERATOR_POLICY_VERSION
    retrovalidation_policy_version: str = RETROVALIDATION_POLICY_VERSION

    def calculate_manifest_hash(self) -> str:
        """Calculate a hash of the content fields."""
        hasher = hashlib.sha256()
        hasher.update(str(self.scene_id).encode("utf-8"))
        hasher.update(str(self.plot_id).encode("utf-8"))
        hasher.update(str(self.geometry_hash).encode("utf-8"))
        hasher.update(str(self.acquisition_time).encode("utf-8"))
        hasher.update(str(self.cloud_score).encode("utf-8"))
        hasher.update(str(self.valid_pixel_fraction).encode("utf-8"))
        hasher.update(str(self.source_content_hash).encode("utf-8"))
        hasher.update(str(self.archive_policy_version).encode("utf-8"))
        return hasher.hexdigest()

def validate_scene_for_asmae(record: HistoricalSceneRecord) -> bool:
    """Enforces manifest entry rules before the scene can enter ASMAE."""
    if not record.plot_id:
        return False
    if not record.geometry_hash:
        return False
    if not record.source_content_hash:
        return False
    if not record.acquisition_time:
        return False
    if record.native_resolution_m <= 0:
        return False
    if record.valid_pixel_fraction < 0.0 or record.valid_pixel_fraction > 1.0:
        return False
    if record.quality_status != "accepted":
        return False
    if not record.source:
        return False
    if not record.product_level:
        return False
    if not record.crs or not record.transform_hash:
        return False
    return True

@contextmanager
def manifest_lock(manifest_dir: str, timeout: float = 30.0):
    """Advisory file lock for concurrent manifest mutations."""
    lock_path = os.path.join(manifest_dir, ".manifest.lock")
    start = time.time()
    fd = None
    while time.time() - start < timeout:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock_path) > 180.0:
                    try:
                        os.unlink(lock_path)
                    except OSError:
                        pass
                    continue
            except OSError:
                pass
            time.sleep(0.02)
    if fd is None:
        raise TimeoutError(f"Manifest lock timed out on {lock_path}")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass

def load_scene_manifest(
    plot_id: str,
    geometry_hash: str,
    artifacts_dir: Optional[str] = None
) -> List[HistoricalSceneRecord]:
    """Load existing historical scene records from scene_manifest.jsonl."""
    if not artifacts_dir:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        artifacts_dir = os.path.join(base, "artifacts", "archive_manifest")
        
    manifest_dir = os.path.join(artifacts_dir, str(plot_id), str(geometry_hash))
    manifest_path = os.path.join(manifest_dir, "scene_manifest.jsonl")
    if not os.path.exists(manifest_path):
        return []

    records: List[HistoricalSceneRecord] = []
    allowed = set(HistoricalSceneRecord.__dataclass_fields__)
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    raw = json.loads(line_str)
                    if isinstance(raw, dict):
                        filtered = {k: v for k, v in raw.items() if k in allowed}
                        records.append(HistoricalSceneRecord(**filtered))
                except Exception:
                    continue
    except OSError:
        return []
    return records

def save_scene_manifest(
    plot_id: str,
    geometry_hash: str,
    records: List[HistoricalSceneRecord],
    artifacts_dir: Optional[str] = None
) -> List[HistoricalSceneRecord]:
    """
    Persist historical scene records into cumulative scene_manifest.jsonl and index.
    
    Reconciles newly ingested records with previously persisted records,
    deduplicating by (scene_id, source_content_hash), ensuring that queries across
    separate historical windows accumulate rather than replace historical evidence.
    Mutations are protected by a file lock and written atomically via temporary files and fsync.
    """
    if not artifacts_dir:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        artifacts_dir = os.path.join(base, "artifacts", "archive_manifest")
        
    manifest_dir = os.path.join(artifacts_dir, str(plot_id), str(geometry_hash))
    os.makedirs(manifest_dir, exist_ok=True)
    
    with manifest_lock(manifest_dir):
        # 1. Load existing records
        existing_records = load_scene_manifest(plot_id, geometry_hash, artifacts_dir)

        # 2. Merge and deduplicate by (scene_id, source_content_hash)
        merged_map: Dict[Tuple[str, str], HistoricalSceneRecord] = {}
        for rec in existing_records:
            key = (rec.scene_id, rec.source_content_hash)
            merged_map[key] = rec

        for rec in records:
            key = (rec.scene_id, rec.source_content_hash)
            merged_map[key] = rec

        merged_records = sorted(
            merged_map.values(),
            key=lambda r: (str(r.acquisition_time or ""), str(r.scene_id or ""))
        )

        # 3. Save jsonl atomically
        manifest_path = os.path.join(manifest_dir, "scene_manifest.jsonl")
        fd, temp_path = tempfile_write_helper(manifest_path)
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                for rec in merged_records:
                    h = rec.calculate_manifest_hash()
                    d = asdict(rec)
                    d["manifest_record_hash"] = h
                    f.write(json.dumps(d) + "\n")
                f.flush()
                os.fsync(f.fileno())

            for attempt in range(10):
                try:
                    os.replace(temp_path, manifest_path)
                    break
                except PermissionError as pe:
                    if attempt == 9:
                        raise pe
                    time.sleep(0.05)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

        # 4. Save index atomically
        index_path = os.path.join(manifest_dir, "scene_manifest_index.json")
        fd_idx, temp_idx_path = tempfile_write_helper(index_path)
        try:
            index_data = {
                "plot_id": plot_id,
                "geometry_hash": geometry_hash,
                "scene_count": len(merged_records),
                "archive_policy_version": ARCHIVE_POLICY_VERSION,
                "quality_policy_version": QUALITY_POLICY_VERSION,
                "scenes": [rec.scene_id for rec in merged_records]
            }
            with open(temp_idx_path, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            for attempt in range(10):
                try:
                    os.replace(temp_idx_path, index_path)
                    break
                except PermissionError as pe:
                    if attempt == 9:
                        raise pe
                    time.sleep(0.05)
        except Exception:
            if os.path.exists(temp_idx_path):
                try:
                    os.remove(temp_idx_path)
                except OSError:
                    pass
            raise

        return merged_records

def tempfile_write_helper(target_path: str):
    dir_name = os.path.dirname(target_path)
    fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    os.close(fd)
    return fd, temp_path
