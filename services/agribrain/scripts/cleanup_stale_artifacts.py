from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict

# Define paths relative to agribrain root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
CACHE_DIR = os.path.join(ARTIFACTS_DIR, "asmae_cache")
OPERATORS_DIR = os.path.join(ARTIFACTS_DIR, "asmae_operators")
RASTERS_DIR = os.path.join(ARTIFACTS_DIR, "asmae_rasters")
SURFACES_CACHE_DIR = os.path.join(ARTIFACTS_DIR, "surfaces_cache")

CLEANUP_DIRS = [CACHE_DIR, OPERATORS_DIR, RASTERS_DIR, SURFACES_CACHE_DIR]
DEFAULT_TTL_DAYS = 14
DEFAULT_MAX_STORAGE_MB = 100.0


def cleanup_stale_artifacts(
    ttl_days: float = DEFAULT_TTL_DAYS,
    max_storage_mb: float = DEFAULT_MAX_STORAGE_MB,
) -> Dict[str, Any]:
    """Prune stale cache files based on TTL and LRU storage budget constraints.

    Returns summary details of files deleted and total freed storage.
    """
    now = time.time()
    ttl_seconds = ttl_days * 24 * 3600
    deleted_files = []
    freed_bytes = 0

    # 0. Cleanup orphans and .tmp files in surfaces cache directory
    if os.path.exists(SURFACES_CACHE_DIR):
        for filename in os.listdir(SURFACES_CACHE_DIR):
            filepath = os.path.join(SURFACES_CACHE_DIR, filename)
            if os.path.isfile(filepath):
                if (
                    filename.endswith(".tmp")
                    or filename.endswith(".tmp.json")
                    or filename.endswith(".tmp.npz")
                    or ".tmp." in filename
                ):
                    try:
                        stat = os.stat(filepath)
                        os.remove(filepath)
                        deleted_files.append(filepath)
                        freed_bytes += stat.st_size
                    except Exception:
                        pass
                elif filename.startswith("surfaces_") and filename.endswith(".npz"):
                    cache_key = filename[len("surfaces_"):-len(".npz")]
                    json_path = os.path.join(SURFACES_CACHE_DIR, f"{cache_key}.json")
                    if not os.path.exists(json_path):
                        try:
                            stat = os.stat(filepath)
                            os.remove(filepath)
                            deleted_files.append(filepath)
                            freed_bytes += stat.st_size
                        except Exception:
                            pass

    # 1. Gather all files in the cleanup directories
    file_records = []
    for directory in CLEANUP_DIRS:
        if not os.path.exists(directory):
            continue
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                try:
                    stat = os.stat(filepath)
                    file_records.append({
                        "path": filepath,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "atime": stat.st_atime,
                    })
                except Exception:
                    pass

    # 2. Prune files exceeding TTL
    files_remaining = []
    for rec in file_records:
        age = now - rec["mtime"]
        if age > ttl_seconds:
            try:
                os.remove(rec["path"])
                deleted_files.append(rec["path"])
                freed_bytes += rec["size"]
            except Exception as e:
                print(f"Failed to delete {rec['path']}: {e}", file=sys.stderr)
        else:
            files_remaining.append(rec)

    # 3. Check storage budget and prune using LRU (ordered by atime/mtime ascending)
    # Sort files so that least recently accessed (lowest atime) are deleted first
    files_remaining.sort(key=lambda x: x["atime"])

    total_size = sum(rec["size"] for rec in files_remaining)
    max_bytes = max_storage_mb * 1024 * 1024

    for rec in files_remaining:
        if total_size <= max_bytes:
            break
        try:
            os.remove(rec["path"])
            deleted_files.append(rec["path"])
            freed_bytes += rec["size"]
            total_size -= rec["size"]
        except Exception as e:
            print(f"Failed to delete {rec['path']}: {e}", file=sys.stderr)

    summary = {
        "files_deleted_count": len(deleted_files),
        "freed_kb": round(freed_bytes / 1024.0, 2),
        "freed_mb": round(freed_bytes / (1024.0 * 1024.0), 2),
        "remaining_mb": round(total_size / (1024.0 * 1024.0), 2),
    }
    print(f"[CLEANUP] Freed {summary['freed_mb']:.2f} MB. Deleted {summary['files_deleted_count']} files.")
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Prune stale pipeline cache artifacts.")
    parser.add_argument("--ttl", type=float, default=DEFAULT_TTL_DAYS, help="Time-to-live in days")
    parser.add_argument("--max-size", type=float, default=DEFAULT_MAX_STORAGE_MB, help="Max storage budget in MB")
    args = parser.parse_args()

    cleanup_stale_artifacts(ttl_days=args.ttl, max_storage_mb=args.max_size)
