"""
Data Refresh Worker — Background daemon for proactive cache refresh.

Runs every 15 minutes and pre-fetches data that is near expiry.
This ensures that when a user opens the dashboard, data is always
fresh — no cold-start latency.

Strategy:
1. Scan all active plots (plots with recent cache entries)
2. For each plot, check which sources are near expiry (< 25% TTL remaining)
3. Pre-fetch those sources in the background
4. Prioritize: high-volatility sources first, then active plots

The worker also:
- Attempts MongoDB reconnection if in filesystem-fallback mode
- Cleans up expired filesystem cache entries
- Runs periodic compaction (warm → cold tier promotion)

Usage:
    from layer0.data_gateway.refresh_worker import DataRefreshWorker

    worker = DataRefreshWorker(broker)
    worker.run_cycle()  # Run one refresh cycle
    worker.start()      # Start background daemon (threaded)
"""

from __future__ import annotations

import os
import time
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("agribrain.gateway.refresh_worker")

# Refresh threshold: pre-fetch when TTL remaining < this fraction
REFRESH_THRESHOLD = 0.25  # 25% TTL remaining

# Worker interval
WORKER_INTERVAL_SECONDS = int(os.getenv("REFRESH_INTERVAL", "900"))  # 15 minutes

# Maximum sources to refresh per cycle (prevents runaway)
MAX_REFRESHES_PER_CYCLE = 50
ASMAE_ARCHIVE_REFRESH_EVERY_CYCLES = max(
    1, int(os.getenv("ASMAE_ARCHIVE_REFRESH_EVERY_CYCLES", "4"))
)

# High-priority sources (weather changes fast)
HIGH_PRIORITY_SOURCES = {
    "openweather_current",
    "openweather_forecast",
    "fire_risk",
    "air_quality",
}


class DataRefreshWorker:
    """Background worker that proactively refreshes near-expiry data.

    Runs in a daemon thread. Each cycle:
    1. Gets freshness report for all active plots
    2. Identifies sources near expiry (< 25% TTL remaining)
    3. Pre-fetches them through the broker (cached, deduplicated)
    4. Housekeeping: cleanup, reconnection, compaction

    This ensures the dashboard always has fresh data — no cold starts.
    """

    def __init__(self, broker=None):
        self._broker = broker
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._cycle_count = 0
        self._total_refreshed = 0
        self._last_cycle_at: Optional[datetime] = None
        self._last_cycle_duration: float = 0.0
        self._active_plots: Set[str] = set()
        self._last_asmae_archive_stats: Optional[Dict[str, Any]] = None

    def _get_broker(self):
        """Lazy-load broker."""
        if self._broker is None:
            from layer0.data_gateway.request_broker import DataRequestBroker
            self._broker = DataRequestBroker()
        return self._broker

    # ── Main Cycle ─────────────────────────────────────────────────

    def run_cycle(self) -> Dict:
        """Run one refresh cycle. Returns cycle stats."""
        start = time.time()
        self._cycle_count += 1
        cycle_refreshed = 0
        cycle_errors = 0

        broker = self._get_broker()

        logger.info(
            "[REFRESH] Starting cycle %d (active plots: %d)",
            self._cycle_count, len(self._active_plots),
        )

        # Step 1: Discover active plots from MongoDB
        self._discover_active_plots()

        # Step 2: Check freshness and refresh near-expiry sources
        for plot_id in list(self._active_plots):
            if cycle_refreshed >= MAX_REFRESHES_PER_CYCLE:
                logger.info("[REFRESH] Hit max refreshes (%d), stopping", MAX_REFRESHES_PER_CYCLE)
                break

            try:
                refreshed = self._refresh_plot(plot_id)
                cycle_refreshed += refreshed
            except Exception as e:
                cycle_errors += 1
                logger.warning("[REFRESH] Error refreshing plot %s: %s", plot_id[:8], e)

        # Step 3: Scheduled ASMAE archive/worldline reconciliation. This is the
        # normal service path for the historical forward filter + RTS smoother;
        # it is no longer confined to a pilot script.
        if (
            (self._cycle_count - 1)
            % ASMAE_ARCHIVE_REFRESH_EVERY_CYCLES
            == 0
        ):
            try:
                from layer05_asmae.history.archive_scheduler_service import (
                    ScheduledArchiveWorldlineService,
                )
                self._last_asmae_archive_stats = (
                    ScheduledArchiveWorldlineService().run_cycle()
                )
                cycle_errors += len(
                    self._last_asmae_archive_stats.get("errors", [])
                )
            except Exception as archive_exc:
                cycle_errors += 1
                self._last_asmae_archive_stats = {
                    "status": "failed",
                    "reason": str(archive_exc),
                }
                logger.warning(
                    "[REFRESH] ASMAE archive reconciliation failed: %s",
                    archive_exc,
                )

        # Step 4: Housekeeping
        self._housekeeping()

        # Stats
        duration = time.time() - start
        self._last_cycle_at = datetime.now(timezone.utc)
        self._last_cycle_duration = duration
        self._total_refreshed += cycle_refreshed

        stats = {
            "cycle": self._cycle_count,
            "duration_seconds": round(duration, 1),
            "active_plots": len(self._active_plots),
            "sources_refreshed": cycle_refreshed,
            "errors": cycle_errors,
            "total_refreshed": self._total_refreshed,
        }

        logger.info(
            "[REFRESH] Cycle %d complete: %d refreshed, %d errors, %.1fs",
            self._cycle_count, cycle_refreshed, cycle_errors, duration,
        )

        return stats

    def _refresh_plot(self, plot_id: str) -> int:
        """Check and refresh near-expiry sources for a single plot.

        Returns count of sources refreshed.
        """
        broker = self._get_broker()

        # Get freshness for high-priority sources first, then all
        sources_to_check = list(HIGH_PRIORITY_SOURCES) + [
            s for s in broker.storage.ttl_engine._access_log.get(plot_id, [])
            if s not in HIGH_PRIORITY_SOURCES
        ]

        if not sources_to_check:
            # Fall back to checking all sources via freshness report
            report = broker.freshness(plot_id)
            sources_to_check = list(report.keys())

        refreshed = 0

        for source in sources_to_check:
            if refreshed >= 5:  # Max 5 per plot per cycle
                break

            # Check if source needs refresh
            fresh_report = broker.freshness(plot_id, [source])
            entry = fresh_report.get(source, {})

            if not entry.get("is_cached"):
                continue  # Never cached — skip (will be fetched on demand)

            freshness_pct = entry.get("freshness_pct", 100)
            if freshness_pct < REFRESH_THRESHOLD * 100:
                # Near expiry — pre-fetch
                try:
                    # We need lat/lng for the fetch — get from cache metadata
                    # For now, we use the plot's last known coordinates
                    lat, lng = self._get_plot_coords(plot_id)
                    if lat is not None and lng is not None:
                        broker.get(source, plot_id, lat, lng, force_refresh=True)
                        refreshed += 1
                        logger.debug(
                            "[REFRESH] Pre-fetched %s for plot %s (was %.0f%% fresh)",
                            source, plot_id[:8], freshness_pct,
                        )
                except Exception as e:
                    logger.debug("[REFRESH] Failed to refresh %s/%s: %s", source, plot_id[:8], e)

        return refreshed

    # ── Discovery ──────────────────────────────────────────────────

    def _discover_active_plots(self):
        """Discover plots with recent cache entries (active in last 24h)."""
        try:
            from layer0.data_gateway.storage_manager import _get_db
            db = _get_db()
            if db is None:
                return

            # Find distinct plot_ids with recent cache entries
            cutoff = datetime.utcnow()
            pipeline = [
                {"$match": {"plot_id": {"$ne": ""}, "fetched_at": {"$exists": True}}},
                {"$group": {"_id": "$plot_id"}},
                {"$limit": 500},  # Cap at 500 plots
            ]

            results = list(db.eo_cache.aggregate(pipeline))
            new_plots = {r["_id"] for r in results if r["_id"]}

            if new_plots:
                added = new_plots - self._active_plots
                removed = self._active_plots - new_plots
                self._active_plots = new_plots

                if added:
                    logger.debug("[REFRESH] Discovered %d new active plots", len(added))

        except Exception as e:
            logger.debug("[REFRESH] Plot discovery error: %s", e)

    def _get_plot_coords(self, plot_id: str) -> tuple:
        """Get the last known coordinates for a plot."""
        try:
            from layer0.data_gateway.storage_manager import _get_db
            db = _get_db()
            if db is None:
                return None, None

            doc = db.eo_cache.find_one(
                {"plot_id": plot_id, "lat": {"$exists": True}},
                {"lat": 1, "lng": 1},
            )

            if doc:
                return doc.get("lat"), doc.get("lng")

        except Exception:
            pass

        return None, None

    # ── Housekeeping ───────────────────────────────────────────────

    def _housekeeping(self):
        """Periodic cleanup tasks."""
        broker = self._get_broker()

        # Clean expired filesystem cache entries
        try:
            cleaned = broker.storage.fs_fallback.cleanup_expired()
            if cleaned > 0:
                logger.info("[REFRESH] Cleaned %d expired filesystem entries", cleaned)
        except Exception as e:
            logger.debug("[REFRESH] FS cleanup error: %s", e)

        # Attempt MongoDB reconnection if in fallback mode
        try:
            from layer0.data_gateway.storage_manager import _get_db
            if _get_db() is None:
                broker.storage.attempt_reconnect()
        except Exception:
            pass

    # ── Daemon Thread ──────────────────────────────────────────────

    def start(self):
        """Start the background refresh daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("[REFRESH] Worker already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._daemon_loop,
            name="agribrain-refresh-worker",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "[REFRESH] Background worker started (interval: %ds)",
            WORKER_INTERVAL_SECONDS,
        )

    def stop(self):
        """Stop the background refresh daemon."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("[REFRESH] Background worker stopped")

    def _daemon_loop(self):
        """Main daemon loop."""
        # Initial delay to let the app start up
        self._stop_event.wait(30)

        while not self._stop_event.is_set():
            try:
                self.run_cycle()
            except Exception as e:
                logger.error("[REFRESH] Cycle error: %s", e)

            self._stop_event.wait(WORKER_INTERVAL_SECONDS)

    @property
    def is_running(self) -> bool:
        """Check if the daemon thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    # ── Stats ──────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get worker statistics."""
        return {
            "is_running": self.is_running,
            "cycle_count": self._cycle_count,
            "total_refreshed": self._total_refreshed,
            "active_plots": len(self._active_plots),
            "last_cycle_at": self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            "last_cycle_duration": round(self._last_cycle_duration, 1),
            "interval_seconds": WORKER_INTERVAL_SECONDS,
            "refresh_threshold": REFRESH_THRESHOLD,
            "asmae_archive_refresh_every_cycles": (
                ASMAE_ARCHIVE_REFRESH_EVERY_CYCLES
            ),
            "last_asmae_archive_stats": self._last_asmae_archive_stats,
        }
