"""
Filesystem Fallback Store — JSON file cache when MongoDB is unavailable.

Provides identical cache semantics to the main StorageManager but uses
the local filesystem. This ensures AgriBrain keeps working even when
MongoDB goes down.

Directory layout:
    data/cache/{source}/{lat_snap}_{lng_snap}/{param_hash}.json

Each cached file contains:
    {
        "source": "soilgrids",
        "plot_id": "abc123",
        "lat": 33.5000,
        "lng": -7.6000,
        "data": { ... },
        "fetched_at": "2026-05-25T12:00:00Z",
        "expires_at": "2026-06-24T12:00:00Z",
        "ttl_seconds": 2592000,
        "param_hash": "a1b2c3d4"
    }

TTL is checked via expires_at timestamp (not file mtime).

When MongoDB reconnects, pending filesystem entries are synced back
to the MongoDB cache via sync_to_mongodb().
"""

from __future__ import annotations

import json
import os
import hashlib
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("agribrain.gateway.fs_fallback")

# Root directory for filesystem cache
CACHE_ROOT = Path(__file__).parent.parent.parent / "data" / "cache"


class FilesystemFallbackStore:
    """JSON file cache with TTL semantics matching StorageManager.

    Used when MongoDB is unavailable. Provides:
    - Same composite key logic
    - Same TTL expiration checks
    - Automatic sync to MongoDB when connection restored
    - Thread-safe file operations via atomic write pattern

    Limitations vs MongoDB:
    - No aggregation queries (compaction deferred)
    - No observation promotion (queued for later)
    - No ML pattern updates (patterns freeze)
    """

    def __init__(self, cache_root: Optional[Path] = None):
        self._root = cache_root or CACHE_ROOT
        self._root.mkdir(parents=True, exist_ok=True)
        self._pending_sync: List[Path] = []
        logger.info("Filesystem fallback initialized: %s", self._root)

    # ── Cache Operations ───────────────────────────────────────────

    def get(
        self, source: str, lat: float, lng: float,
        param_hash: str = "",
        plot_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """Check filesystem cache. Returns data dict or None if expired/missing."""
        pid = plot_id or "default"
        path = self._cache_path(pid, source, lat, lng, param_hash)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)

            # Check TTL
            expires_str = doc.get("expires_at", "")
            if expires_str:
                expires = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > expires:
                    # Expired — delete and return None
                    self._safe_delete(path)
                    return None

            data = doc.get("data")
            if data is not None:
                fetched_str = doc.get("fetched_at", "")
                age_min = 0
                if fetched_str:
                    try:
                        fetched = datetime.fromisoformat(fetched_str.replace("Z", "+00:00"))
                        age_min = (datetime.now(timezone.utc) - fetched).total_seconds() / 60
                    except Exception:
                        pass
                logger.debug(
                    "[FS_CACHE] HIT: %s (%.0fmin old)", source, age_min
                )
                return data

            return None

        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("[FS_CACHE] Read error %s: %s", path.name, e)
            self._safe_delete(path)
            return None

    def get_stale(
        self, source: str, lat: float, lng: float,
        param_hash: str = "",
        plot_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """Return the last stored payload without enforcing TTL.

        This read is intentionally non-destructive. It is used only as the
        rollback source while a provider refresh is fetched and validated.
        """
        pid = plot_id or "default"
        path = self._cache_path(pid, source, lat, lng, param_hash)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            return doc.get("data")
        except (json.JSONDecodeError, OSError, KeyError) as error:
            logger.warning("[FS_CACHE] Non-destructive stale read error %s: %s", path.name, error)
            return None

    def put(
        self, source: str, lat: float, lng: float, data: Any,
        ttl_seconds: int,
        plot_id: Optional[str] = None,
        param_hash: str = "",
    ) -> bool:
        """Store a cache entry on the filesystem."""
        pid = plot_id or "default"
        path = self._cache_path(pid, source, lat, lng, param_hash)

        try:
            now = datetime.now(timezone.utc)
            expires = now + timedelta(seconds=ttl_seconds)

            doc = {
                "source": source,
                "lat": round(lat, 4),
                "lng": round(lng, 4),
                "data": data,
                "fetched_at": now.isoformat(),
                "expires_at": expires.isoformat(),
                "ttl_seconds": ttl_seconds,
                "param_hash": param_hash,
            }
            if plot_id:
                doc["plot_id"] = plot_id

            # Atomic write: write to unique .tmp then rename
            import uuid
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.parent / f"{path.name}.{uuid.uuid4().hex[:8]}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, default=str, indent=None)

            # Atomic rename (on same filesystem)
            tmp_path.replace(path)

            ttl_human = f"{ttl_seconds // 3600}h" if ttl_seconds >= 3600 else f"{ttl_seconds // 60}min"
            logger.debug("[FS_CACHE] STORED: %s (TTL: %s)", source, ttl_human)

            # Track for later MongoDB sync
            self._pending_sync.append(path)

            return True

        except OSError as e:
            logger.error("[FS_CACHE] Write error %s: %s", source, e)
            if 'tmp_path' in locals() and tmp_path.exists():
                self._safe_delete(tmp_path)
            return False

    def invalidate(
        self, source: Optional[str] = None,
        lat: Optional[float] = None, lng: Optional[float] = None,
        plot_id: Optional[str] = None,
    ) -> int:
        """Delete cache entries. Returns count deleted."""
        deleted = 0

        if plot_id and source and lat is not None and lng is not None:
            coord_dir = self._coord_dir(plot_id, source, lat, lng)
            if coord_dir.exists():
                for path in coord_dir.glob("*.json"):
                    self._safe_delete(path)
                    deleted += 1
        elif not plot_id and source and lat is not None and lng is not None:
            # glob across all plots
            lat_snap = f"{lat:.4f}".replace("-", "n")
            lng_snap = f"{lng:.4f}".replace("-", "n")
            for path in self._root.glob(f"*/{source}/{lat_snap}_{lng_snap}/*.json"):
                self._safe_delete(path)
                deleted += 1
        elif plot_id and source:
            source_dir = self._root / plot_id / source
            if source_dir.exists():
                for path in source_dir.rglob("*.json"):
                    self._safe_delete(path)
                    deleted += 1
        elif plot_id:
            plot_dir = self._root / plot_id
            if plot_dir.exists():
                for path in plot_dir.rglob("*.json"):
                    self._safe_delete(path)
                    deleted += 1
        elif source:
            for path in self._root.glob(f"*/{source}/**/*.json"):
                self._safe_delete(path)
                deleted += 1
        else:
            for path in self._root.rglob("*.json"):
                self._safe_delete(path)
                deleted += 1

        if deleted > 0:
            logger.info("[FS_CACHE] Invalidated %d entries (plot=%s, source=%s)", deleted, plot_id, source)

        return deleted

    # ── Sync to MongoDB ────────────────────────────────────────────

    def sync_to_mongodb(self, cache_put_fn: Callable) -> int:
        """Sync pending filesystem entries back to MongoDB.

        Called when MongoDB reconnects. Reads each pending file
        and calls cache_put_fn(source, lat, lng, data, plot_id)
        to re-populate the MongoDB cache.

        Returns count of synced entries.
        """
        synced = 0
        remaining = []

        for path in self._pending_sync:
            if not path.exists():
                continue

            try:
                with open(path, "r", encoding="utf-8") as f:
                    doc = json.load(f)

                # Check if still valid
                expires_str = doc.get("expires_at", "")
                if expires_str:
                    expires = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > expires:
                        self._safe_delete(path)
                        continue

                success = cache_put_fn(
                    source=doc["source"],
                    lat=doc["lat"],
                    lng=doc["lng"],
                    data=doc.get("data"),
                    plot_id=doc.get("plot_id"),
                )

                if success:
                    synced += 1
                else:
                    remaining.append(path)

            except Exception as e:
                logger.warning("[FS_CACHE] Sync error %s: %s", path.name, e)
                remaining.append(path)

        self._pending_sync = remaining

        if synced > 0:
            logger.info(
                "[FS_CACHE] Synced %d entries to MongoDB (%d remaining)",
                synced, len(remaining),
            )

        return synced

    def get_pending_sync_count(self) -> int:
        """Return count of entries pending MongoDB sync."""
        return len(self._pending_sync)

    # ── Stats ──────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get filesystem cache statistics."""
        total_files = 0
        total_bytes = 0
        by_source: Dict[str, int] = {}

        try:
            for path in self._root.rglob("*.json"):
                total_files += 1
                total_bytes += path.stat().st_size
                # Extract source from path: data/cache/{plot_id}/{source}/...
                parts = path.relative_to(self._root).parts
                if len(parts) >= 2:
                    source = parts[1]
                    by_source[source] = by_source.get(source, 0) + 1
        except OSError:
            pass

        return {
            "status": "active",
            "root": str(self._root),
            "total_files": total_files,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "by_source": by_source,
            "pending_sync": len(self._pending_sync),
        }

    # ── Cleanup ────────────────────────────────────────────────────

    def cleanup_expired(self) -> int:
        """Delete all expired cache files. Returns count deleted."""
        deleted = 0
        now = datetime.now(timezone.utc)

        try:
            for path in self._root.rglob("*.json"):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        doc = json.load(f)
                    expires_str = doc.get("expires_at", "")
                    if expires_str:
                        expires = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                        if now > expires:
                            self._safe_delete(path)
                            deleted += 1
                except Exception:
                    pass
        except OSError:
            pass

        if deleted > 0:
            logger.info("[FS_CACHE] Cleaned up %d expired entries", deleted)

        return deleted

    # ── Internal Helpers ───────────────────────────────────────────

    def _cache_path(
        self, plot_id: str, source: str, lat: float, lng: float, param_hash: str = "",
    ) -> Path:
        """Build filesystem path for a cache entry."""
        coord_dir = self._coord_dir(plot_id, source, lat, lng)
        filename = f"{param_hash or 'default'}.json"
        return coord_dir / filename

    def _coord_dir(self, plot_id: str, source: str, lat: float, lng: float) -> Path:
        """Build coordinate directory: data/cache/{plot_id}/{source}/{lat}_{lng}/"""
        pid = plot_id or "default"
        lat_snap = f"{lat:.4f}".replace("-", "n")
        lng_snap = f"{lng:.4f}".replace("-", "n")
        return self._root / pid / source / f"{lat_snap}_{lng_snap}"

    def _safe_delete(self, path: Path):
        """Delete a file, ignoring errors."""
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
