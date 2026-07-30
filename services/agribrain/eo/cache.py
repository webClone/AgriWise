"""
EO Cache Layer — DEPRECATED SHIM.

All functions are redirected to the new StorageManager in the Layer 0 Ingestion Cortex
(layer0.data_gateway.storage_manager).
This shim exists for backwards compatibility during migration.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any, Callable, Dict, Optional

from layer0.data_gateway.storage_manager import StorageManager

logger = logging.getLogger("agribrain.eo.cache")

# Emit a deprecation warning at import time
warnings.warn(
    "eo.cache is deprecated and scheduled for removal. Use layer0.data_gateway instead.",
    DeprecationWarning,
    stacklevel=2
)

_storage_manager = StorageManager()


def cache_get(source: str, lat: float, lng: float) -> Optional[Dict]:
    """[DEPRECATED] Redirects to StorageManager._cache_get."""
    logger.debug("[DEPRECATED] cache_get called, redirecting to StorageManager")
    return _storage_manager._cache_get(source, lat, lng)


def cache_put(source: str, lat: float, lng: float, data: Any, plot_id: Optional[str] = None) -> bool:
    """[DEPRECATED] Redirects to StorageManager._cache_put."""
    logger.debug("[DEPRECATED] cache_put called, redirecting to StorageManager")
    # For coordinate-only backwards compatibility, we store with plot_id=""
    _storage_manager._cache_put(source, lat, lng, data, "")
    # If a plot_id is passed, we also store it with the plot_id to trigger observation promotion
    if plot_id:
        return _storage_manager._cache_put(source, lat, lng, data, plot_id)
    return True


def cached_fetch(source: str, fetch_fn: Callable, *args, **kwargs) -> Any:
    """[DEPRECATED] Redirects to StorageManager.get_or_fetch."""
    logger.debug("[DEPRECATED] cached_fetch called, redirecting to StorageManager")
    if len(args) < 2:
        return fetch_fn(*args, **kwargs)
    
    lat, lng = float(args[0]), float(args[1])
    return _storage_manager.get_or_fetch(
        source=source,
        plot_id="",
        lat=lat,
        lng=lng,
        fetch_fn=fetch_fn,
        *args,
        **kwargs
    )


def cached_fetch_fn(source: str, fetch_fn: Callable) -> Callable:
    """[DEPRECATED] Redirects to a wrapper around cached_fetch."""
    def wrapper(*args, **kwargs):
        return cached_fetch(source, fetch_fn, *args, **kwargs)
    
    wrapper.__name__ = f"cached_{fetch_fn.__name__}"
    return wrapper


def cache_stats() -> Dict[str, Any]:
    """[DEPRECATED] Redirects to StorageManager.get_stats."""
    logger.debug("[DEPRECATED] cache_stats called, redirecting to StorageManager")
    stats = _storage_manager.get_stats()
    mongodb_stats = stats.get("mongodb", {})
    if mongodb_stats.get("status") == "connected":
        hot_tier = mongodb_stats.get("hot_tier", {})
        return {
            "status": "active",
            "total_entries": hot_tier.get("total_entries", 0),
            "fresh_entries": hot_tier.get("total_entries", 0),
            "expired_entries": 0,
            "by_source": hot_tier.get("by_source", {}),
        }
    return {"status": "disabled", "reason": "MongoDB unavailable"}


def cache_invalidate(source: Optional[str] = None, lat: Optional[float] = None,
                     lng: Optional[float] = None) -> int:
    """[DEPRECATED] Redirects to StorageManager.invalidate."""
    logger.debug("[DEPRECATED] cache_invalidate called, redirecting to StorageManager")
    return _storage_manager.invalidate(plot_id="", source=source)
