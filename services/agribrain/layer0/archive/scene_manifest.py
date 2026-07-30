"""
Historical scene manifest and serialization logic.
"""
import os
import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

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

def save_scene_manifest(
    plot_id: str,
    geometry_hash: str,
    records: List[HistoricalSceneRecord],
    artifacts_dir: Optional[str] = None
) -> None:
    if not artifacts_dir:
        # relative to current file workspace
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        artifacts_dir = os.path.join(base, "artifacts", "archive_manifest")
        
    manifest_dir = os.path.join(artifacts_dir, plot_id, geometry_hash)
    os.makedirs(manifest_dir, exist_ok=True)
    
    # Save jsonl
    manifest_path = os.path.join(manifest_dir, "scene_manifest.jsonl")
    fd, temp_path = tempfile_write_helper(manifest_path)
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            for rec in records:
                h = rec.calculate_manifest_hash()
                # construct copy with updated hash
                d = asdict(rec)
                d["manifest_record_hash"] = h
                f.write(json.dumps(d) + "\n")
        import time
        for attempt in range(10):
            try:
                os.replace(temp_path, manifest_path)
                break
            except PermissionError as pe:
                if attempt == 9:
                    raise pe
                time.sleep(0.05)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

    # Save index
    index_path = os.path.join(manifest_dir, "scene_manifest_index.json")
    fd_idx, temp_idx_path = tempfile_write_helper(index_path)
    try:
        index_data = {
            "plot_id": plot_id,
            "geometry_hash": geometry_hash,
            "scene_count": len(records),
            "archive_policy_version": ARCHIVE_POLICY_VERSION,
            "quality_policy_version": QUALITY_POLICY_VERSION,
            "scenes": [rec.scene_id for rec in records]
        }
        with open(temp_idx_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2)
        import time
        for attempt in range(10):
            try:
                os.replace(temp_idx_path, index_path)
                break
            except PermissionError as pe:
                if attempt == 9:
                    raise pe
                time.sleep(0.05)
    except Exception as e:
        if os.path.exists(temp_idx_path):
            os.remove(temp_idx_path)
        raise e

def tempfile_write_helper(target_path: str):
    import tempfile
    dir_name = os.path.dirname(target_path)
    fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    os.close(fd)
    return fd, temp_path
