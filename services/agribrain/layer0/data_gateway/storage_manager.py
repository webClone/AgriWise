"""
Storage Manager — Plot-aware 3-tier data storage engine.

The central storage engine for the AgriBrain Data Gateway.
Replaces and extends eo/cache.py with:

1. Composite cache keys: {plot_id}:{source}:{lat_snap}:{lng_snap}:{param_hash}
2. Adaptive TTL via AdaptiveTTLEngine (not hardcoded)
3. 3-tier storage: hot (raw) → warm (daily) → cold (seasonal)
4. Automatic observation promotion with ML feature extraction
5. Filesystem fallback when MongoDB unavailable
6. Thread-safe with connection pooling
7. Metrics: hit/miss/latency/error per source per plot

Usage:
    from services.agribrain.layer0.data_gateway.storage_manager import StorageManager

    sm = StorageManager()
    
    # Cache-through: check cache → fetch on miss → store → promote
    result = sm.get_or_fetch("soilgrids", "plot123", 33.5, -7.6,
                              fetch_fn=fetch_soil_properties)
    
    # Freshness report
    report = sm.get_freshness_report("plot123")
"""

from __future__ import annotations

import os
import time
import hashlib
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.agribrain.layer0.data_gateway.ttl_registry import get_source_config, get_base_ttl
from services.agribrain.layer0.data_gateway.adaptive_ttl import AdaptiveTTLEngine
from services.agribrain.layer0.data_gateway.filesystem_fallback import FilesystemFallbackStore
from services.agribrain.layer0.data_gateway.metrics import metrics

logger = logging.getLogger("agribrain.gateway.storage")

# ── MongoDB Connection (lazy singleton with reconnection) ──────────────

_mongo_client = None
_mongo_db = None
_init_attempted = False
_init_lock = threading.Lock()


def _get_db():
    """Lazy-init MongoDB connection. Falls back to None if unavailable."""
    global _mongo_client, _mongo_db, _init_attempted

    if _mongo_db is not None:
        # Quick ping to verify connection is alive
        try:
            _mongo_client.admin.command("ping")
            return _mongo_db
        except Exception:
            logger.warning("[STORAGE] MongoDB connection lost, attempting reconnect...")
            _mongo_client = None
            _mongo_db = None
            _init_attempted = False

    with _init_lock:
        if _mongo_db is not None:
            return _mongo_db

        if _init_attempted:
            return None

        _init_attempted = True

        try:
            from pymongo import MongoClient

            mongo_url = os.getenv("DATABASE_URL", "mongodb://localhost:27017/agriwise")

            db_name = "agriwise"
            try:
                path = mongo_url.split("?")[0].split("/")
                if len(path) >= 4:
                    db_name = path[3] or "agriwise"
            except Exception:
                pass

            _mongo_client = MongoClient(
                mongo_url,
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=3000,
                socketTimeoutMS=5000,
                maxPoolSize=10,
            )

            _mongo_client.admin.command("ping")
            _mongo_db = _mongo_client[db_name]

            # Ensure indexes on eo_cache (hot tier)
            _mongo_db.eo_cache.create_index("expires_at", expireAfterSeconds=0)
            _mongo_db.eo_cache.create_index([("cache_key", 1)], unique=True)
            _mongo_db.eo_cache.create_index([("plot_id", 1), ("source", 1)])

            # Ensure indexes on PlotObservation (warm tier)
            try:
                _mongo_db.PlotObservation.create_index(
                    [("plotId", 1), ("source", 1), ("obsDate", 1), ("obsType", 1)],
                    unique=True,
                )
            except Exception:
                pass  # Index exists with different name — that's fine

            logger.info("[STORAGE] MongoDB connected (%s), 3-tier storage active", db_name)
            return _mongo_db

        except Exception as e:
            logger.warning("[STORAGE] MongoDB unavailable: %s", e)
            _mongo_client = None
            _mongo_db = None
            return None


def _reset_mongo_state():
    """Reset MongoDB connection state to allow reconnection.
    Called when filesystem fallback detects MongoDB might be back."""
    global _init_attempted
    _init_attempted = False


# ── Freshness Entry ────────────────────────────────────────────────────

class FreshnessEntry:
    """TTL status for a single cached source."""

    def __init__(
        self,
        source: str,
        is_cached: bool = False,
        fetched_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        age_seconds: float = 0,
        ttl_remaining_seconds: float = 0,
        ttl_total_seconds: int = 0,
        is_fresh: bool = False,
    ):
        self.source = source
        self.is_cached = is_cached
        self.fetched_at = fetched_at
        self.expires_at = expires_at
        self.age_seconds = age_seconds
        self.ttl_remaining_seconds = ttl_remaining_seconds
        self.ttl_total_seconds = ttl_total_seconds
        self.is_fresh = is_fresh

    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "is_cached": self.is_cached,
            "is_fresh": self.is_fresh,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "age_human": _human_duration(self.age_seconds),
            "ttl_remaining_human": _human_duration(self.ttl_remaining_seconds),
            "freshness_pct": round(
                max(0, self.ttl_remaining_seconds / max(1, self.ttl_total_seconds)) * 100, 1
            ) if self.ttl_total_seconds > 0 else 0,
        }


# ── Storage Manager ────────────────────────────────────────────────────

class StorageManager:
    """Plot-aware 3-tier data storage with adaptive TTL.

    Tier layout:
    - Hot:  MongoDB eo_cache — raw API responses, TTL-managed
    - Warm: MongoDB PlotObservation — daily summaries, 2 years
    - Cold: MongoDB PlotSeasonArchive — weekly medians, permanent

    Fallback: FilesystemFallbackStore when MongoDB is down.
    """

    def __init__(self):
        self._ttl_engine = AdaptiveTTLEngine()
        self._fs_fallback = FilesystemFallbackStore()
        self._promotion_enabled = True

    # ── Core Cache Operations ──────────────────────────────────────

    def get_cached_evidence(
        self,
        source: str,
        plot_id: str,
        lat: float,
        lng: float,
        param_hash: str = "",
    ) -> Optional[Dict]:
        """Peek at last-known evidence without TTL deletion or mutation."""
        db = _get_db()
        if db is not None:
            try:
                key = self._make_key(source, lat, lng, plot_id, param_hash)
                doc = db.eo_cache.find_one({"cache_key": key})
                if doc and doc.get("data") is not None:
                    return doc["data"]
            except Exception as error:
                logger.warning("[STORAGE] MongoDB stale read error for %s: %s", source, error)
        return self._fs_fallback.get_stale(
            source, lat, lng, param_hash, plot_id=plot_id,
        )

    def get_or_fetch(
        self,
        source: str,
        plot_id: str,
        lat: float,
        lng: float,
        fetch_fn: Callable,
        *args,
        force_refresh: bool = False,
        context: Optional[Dict] = None,
        param_hash: str = "",
        candidate_validator: Optional[Callable[[Any], bool]] = None,
        **kwargs,
    ) -> Optional[Dict]:
        """Cache-through: check cache → fetch on miss → store → promote.

        Args:
            source: Source identifier (e.g., "soilgrids")
            plot_id: Plot identifier
            lat, lng: Coordinates
            fetch_fn: Function to call on cache miss
            *args, **kwargs: Passed to fetch_fn
            force_refresh: Skip cache, fetch fresh
            context: TTL context (phenology_stage, anomaly_score, etc.)
            param_hash: Extra key component for variant queries

        Returns:
            Data dict or None on failure.
        """
        # Record access for activity factor
        self._ttl_engine.record_access(plot_id, source)

        if not force_refresh:
            # Check hot tier (MongoDB cache)
            cached = self._cache_get(source, lat, lng, plot_id, param_hash)
            if cached is not None:
                metrics.record_hit(source, plot_id)
                return cached

            # Check filesystem fallback
            fs_cached = self._fs_fallback.get(source, lat, lng, param_hash, plot_id=plot_id)
            if fs_cached is not None:
                metrics.record_hit(source, plot_id)
                return fs_cached

        # Cache miss — fetch from external API
        start_ms = time.time() * 1000
        try:
            result = fetch_fn(lat, lng, *args, **kwargs)
        except Exception as e:
            metrics.record_error(source, plot_id, type(e).__name__, str(e))
            logger.error("[STORAGE] Fetch error %s: %s", source, e)
            return None

        latency_ms = time.time() * 1000 - start_ms
        metrics.record_miss(source, plot_id, latency_ms)

        # Validate a refresh candidate before it can replace last-known-good
        # evidence. A rejected candidate is never written to either cache tier.
        if result is not None and candidate_validator is not None:
            try:
                candidate_valid = bool(candidate_validator(result))
            except Exception as validation_error:
                candidate_valid = False
                logger.warning(
                    "[STORAGE] Candidate validation error %s: %s",
                    source,
                    validation_error,
                )
            if not candidate_valid:
                metrics.record_error(
                    source,
                    plot_id,
                    "CandidateValidationError",
                    "refresh candidate rejected before promotion",
                )
                logger.warning(
                    "[STORAGE] Refresh candidate rejected for %s; last-known-good cache retained",
                    source,
                )
                return None

        # Store result. Filesystem writes use atomic rename and MongoDB uses an
        # atomic replacement keyed by cache_key.
        if result is not None:
            self._cache_put(source, lat, lng, result, plot_id, context, param_hash)

        return result

    # ── Hot Tier: MongoDB eo_cache ─────────────────────────────────

    def _cache_get(
        self, source: str, lat: float, lng: float,
        plot_id: str = "", param_hash: str = "",
    ) -> Optional[Dict]:
        """Check MongoDB hot tier for a fresh entry."""
        db = _get_db()
        if db is None:
            return None

        try:
            key = self._make_key(source, lat, lng, plot_id, param_hash)
            now = datetime.utcnow()

            doc = db.eo_cache.find_one({
                "cache_key": key,
                "expires_at": {"$gt": now},
            })

            if doc and doc.get("data") is not None:
                fetched = doc.get("fetched_at", now)
                age_min = (now - fetched).total_seconds() / 60
                logger.debug("[STORAGE] HOT HIT: %s (%.0fmin old)", source, age_min)
                return doc["data"]

            return None

        except Exception as e:
            logger.warning("[STORAGE] MongoDB read error for %s: %s", source, e)
            return None

    def _cache_put(
        self, source: str, lat: float, lng: float, data: Any,
        plot_id: str = "", context: Optional[Dict] = None,
        param_hash: str = "",
    ) -> bool:
        """Store in hot tier (MongoDB + filesystem fallback)."""
        ttl = self._ttl_engine.compute_ttl(source, plot_id, context)

        # Always write to filesystem (as fallback)
        self._fs_fallback.put(source, lat, lng, data, ttl, plot_id, param_hash)

        db = _get_db()
        if db is None:
            logger.debug("[STORAGE] MongoDB down, stored in filesystem only")
            return True

        try:
            key = self._make_key(source, lat, lng, plot_id, param_hash)
            now = datetime.utcnow()
            expires = now + timedelta(seconds=ttl)

            doc = {
                "cache_key": key,
                "source": source,
                "plot_id": plot_id,
                "lat": round(lat, 4),
                "lng": round(lng, 4),
                "data": data,
                "fetched_at": now,
                "expires_at": expires,
                "ttl_seconds": ttl,
                "param_hash": param_hash,
            }

            db.eo_cache.replace_one({"cache_key": key}, doc, upsert=True)

            ttl_human = f"{ttl // 3600}h" if ttl >= 3600 else f"{ttl // 60}min"
            logger.debug("[STORAGE] HOT STORED: %s (TTL: %s)", source, ttl_human)

            # Promote to warm tier (observation archive)
            if self._promotion_enabled and plot_id and data is not None:
                try:
                    from eo.observation_promoter import promote_to_observation
                    promote_to_observation(db, plot_id, source, lat, lng, data, now)
                except Exception as promo_err:
                    logger.debug("[STORAGE] Promotion skipped: %s", promo_err)

            return True

        except Exception as e:
            logger.warning("[STORAGE] MongoDB write error for %s: %s", source, e)
            return True  # Filesystem fallback succeeded

    # ── Freshness Report ───────────────────────────────────────────

    def get_freshness_report(
        self, plot_id: str, sources: Optional[List[str]] = None,
    ) -> Dict[str, FreshnessEntry]:
        """Per-source TTL status for a plot. No fetching.

        Returns a dict of {source_name: FreshnessEntry} showing
        cache age, TTL remaining, and freshness percentage.
        """
        from services.agribrain.layer0.data_gateway.ttl_registry import get_all_sources

        check_sources = sources or get_all_sources()
        report = {}

        db = _get_db()
        now = datetime.utcnow()

        for source in check_sources:
            entry = FreshnessEntry(source=source)

            if db is not None:
                try:
                    # Find latest cache entry for this plot + source
                    doc = db.eo_cache.find_one(
                        {
                            "source": source,
                            "plot_id": plot_id,
                        },
                        sort=[("fetched_at", -1)],
                    )

                    if doc:
                        entry.is_cached = True
                        entry.fetched_at = doc.get("fetched_at")
                        entry.expires_at = doc.get("expires_at")
                        entry.ttl_total_seconds = doc.get("ttl_seconds", 0)

                        if entry.fetched_at:
                            entry.age_seconds = (now - entry.fetched_at).total_seconds()

                        if entry.expires_at:
                            remaining = (entry.expires_at - now).total_seconds()
                            entry.ttl_remaining_seconds = max(0, remaining)
                            entry.is_fresh = remaining > 0

                except Exception:
                    pass

            report[source] = entry

        return report

    # ── Cache Invalidation ─────────────────────────────────────────

    def invalidate(
        self, plot_id: str, source: Optional[str] = None,
    ) -> int:
        """Force-invalidate cache entries for a plot.

        Used when plot coordinates change or admin requests refresh.
        Returns count of deleted entries.
        """
        deleted = 0

        db = _get_db()
        if db is not None:
            try:
                query = {"plot_id": plot_id}
                if source:
                    query["source"] = source

                result = db.eo_cache.delete_many(query)
                deleted = result.deleted_count
                logger.info(
                    "[STORAGE] Invalidated %d MongoDB entries (plot=%s, source=%s)",
                    deleted, plot_id[:8], source,
                )
            except Exception as e:
                logger.warning("[STORAGE] Invalidation error: %s", e)

        # Also invalidate filesystem
        fs_deleted = self._fs_fallback.invalidate(source=source, plot_id=plot_id)
        deleted += fs_deleted

        return deleted

    # ── MongoDB Reconnection ───────────────────────────────────────

    def attempt_reconnect(self) -> bool:
        """Try to reconnect to MongoDB and sync filesystem cache.

        Called periodically when in fallback mode.
        """
        _reset_mongo_state()
        db = _get_db()

        if db is not None:
            logger.info("[STORAGE] MongoDB reconnected! Syncing filesystem cache...")
            synced = self._fs_fallback.sync_to_mongodb(
                lambda source, lat, lng, data, plot_id: self._cache_put(
                    source, lat, lng, data, plot_id
                )
            )
            logger.info("[STORAGE] Synced %d filesystem entries to MongoDB", synced)
            return True

        return False

    # ── Warm Tier Query ────────────────────────────────────────────

    def query_archive(
        self,
        plot_id: str,
        source: Optional[str] = None,
        obs_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict]:
        """Query the warm tier (PlotObservation) archive.

        Returns observation records matching the filter criteria.
        Used by ML patterns and DNA recalibration.
        """
        db = _get_db()
        if db is None:
            return []

        try:
            query: Dict[str, Any] = {"plotId": plot_id}

            if source:
                query["source"] = source
            if obs_type:
                query["obsType"] = obs_type

            if start_date or end_date:
                date_filter = {}
                if start_date:
                    date_filter["$gte"] = datetime.fromisoformat(start_date)
                if end_date:
                    date_filter["$lte"] = datetime.fromisoformat(end_date)
                query["obsDate"] = date_filter

            cursor = (
                db.PlotObservation
                .find(query)
                .sort("obsDate", -1)
                .limit(limit)
            )

            return list(cursor)

        except Exception as e:
            logger.warning("[STORAGE] Archive query error: %s", e)
            return []

    # ── Diagnostics ────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get storage statistics across all tiers."""
        result = {
            "mongodb": {"status": "disconnected"},
            "filesystem": self._fs_fallback.get_stats(),
            "metrics": metrics.get_global_summary(),
        }

        db = _get_db()
        if db is not None:
            try:
                hot_count = db.eo_cache.count_documents({})
                warm_count = db.PlotObservation.count_documents({})

                # Count by source
                pipeline = [
                    {"$group": {"_id": "$source", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                ]
                hot_by_source = {
                    r["_id"]: r["count"]
                    for r in db.eo_cache.aggregate(pipeline)
                }

                result["mongodb"] = {
                    "status": "connected",
                    "hot_tier": {
                        "collection": "eo_cache",
                        "total_entries": hot_count,
                        "by_source": hot_by_source,
                    },
                    "warm_tier": {
                        "collection": "PlotObservation",
                        "total_entries": warm_count,
                    },
                }
            except Exception as e:
                result["mongodb"] = {"status": "error", "error": str(e)}

        return result

    # ── Properties ─────────────────────────────────────────────────

    @property
    def ttl_engine(self) -> AdaptiveTTLEngine:
        """Access the adaptive TTL engine for configuration."""
        return self._ttl_engine

    @property
    def fs_fallback(self) -> FilesystemFallbackStore:
        """Access the filesystem fallback for diagnostics."""
        return self._fs_fallback

    # ── Internal Helpers ───────────────────────────────────────────

    @staticmethod
    def _make_key(
        source: str, lat: float, lng: float,
        plot_id: str = "", param_hash: str = "",
    ) -> str:
        """Build composite cache key.

        Format: {plot_id}:{source}:{lat:.4f}:{lng:.4f}:{param_hash}
        Snaps coordinates to 4 decimals (~11m grid).
        """
        parts = [
            plot_id or "_",
            source,
            f"{lat:.4f}",
            f"{lng:.4f}",
        ]
        if param_hash:
            parts.append(param_hash)
        return ":".join(parts)


def _human_duration(seconds: float) -> str:
    """Convert seconds to human-readable duration."""
    if seconds <= 0:
        return "0s"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}min"
    if seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h"
    days = seconds / 86400
    return f"{days:.1f}d"
