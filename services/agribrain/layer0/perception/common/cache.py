"""
Shared perception cache.

Content-hash keyed cache to prevent redundant inference.
Key: (engine_family, plot_id, image_content_hash, model_version)
NOT keyed by width/height/timestamp — those cause collision problems.

In production, this would be backed by Redis or a persistent store.
Currently in-memory with TTL-based expiry.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import hashlib


@dataclass
class CacheEntry:
    """A single cache entry with TTL."""
    data: Any
    plot_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = 3600  # 1 hour default

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        created = self.created_at if self.created_at.tzinfo else self.created_at.replace(tzinfo=timezone.utc)
        return (now - created).total_seconds() > self.ttl_seconds


class PerceptionCache:
    """
    In-memory perception result cache.
    
    Keyed by (engine_family, plot_id, image_content_hash, model_version)
    to prevent redundant inference on the same image.
    
    Usage:
        cache = PerceptionCache()
        key = cache.make_key("satellite_rgb", "plot_123", "abc123hash", "v1")
        
        cached = cache.get(key)
        if cached is not None:
            return cached
        
        result = run_inference(...)
        cache.set(key, result)
    """

    _key_to_plot: Dict[str, str] = {}

    def __init__(self, default_ttl_seconds: int = 3600):
        self._store: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl_seconds

    @classmethod
    def make_key(
        cls,
        engine_family: str,
        plot_id: str,
        image_content_hash: str,
        model_version: str = "v1",
    ) -> str:
        """
        Build a deterministic cache key from content-based identifiers.
        
        Uses image_content_hash (NOT width/height/timestamp) to avoid
        collision problems seen in the legacy path.
        """
        raw = f"{engine_family}:{plot_id}:{image_content_hash}:{model_version}"
        key = hashlib.sha256(raw.encode()).hexdigest()[:24]
        cls._key_to_plot[key] = plot_id
        return key

    @staticmethod
    def compute_content_hash(image_data: bytes) -> str:
        """
        Compute a content hash from raw image bytes.
        This is the canonical way to get the image_content_hash.
        """
        return hashlib.sha256(image_data).hexdigest()[:16]

    def get(self, key: str) -> Optional[Any]:
        """Retrieve cached result, or None if missing/expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            self.invalidate(key)
            return None
        return entry.data

    def set(
        self,
        key: str,
        data: Any,
        ttl_seconds: Optional[int] = None,
        plot_id: Optional[str] = None,
    ) -> None:
        """Store a result in the cache."""
        resolved_plot = plot_id or self._key_to_plot.get(key)
        self._store[key] = CacheEntry(
            data=data,
            plot_id=resolved_plot,
            ttl_seconds=ttl_seconds or self._default_ttl,
        )

    def invalidate(self, key: str) -> bool:
        """Remove a specific entry. Returns True if it existed."""
        if key in self._store:
            del self._store[key]
            self._key_to_plot.pop(key, None)
            return True
        return False

    def invalidate_plot(self, plot_id: str) -> int:
        """Remove all entries for a specific plot. Returns count removed."""
        to_remove = [
            k for k, v in self._store.items()
            if v.plot_id == plot_id or self._key_to_plot.get(k) == plot_id or plot_id in k
        ]
        for k in to_remove:
            self.invalidate(k)
        return len(to_remove)

    def clear(self) -> None:
        """Clear the entire cache."""
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
