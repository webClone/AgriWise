"""
Bootstrap Engine — Pre-fetches ALL data when a new plot is created.

When a farmer creates a new plot, this engine:
1. Fetches all 24+ sources in parallel via the broker
2. Seeds the cache (hot tier) so first dashboard load is instant
3. Runs initial DNA sequencing (bulk historical fetch)
4. Seeds the observation archive (warm tier)
5. Initializes ML pattern baselines

This replaces the old pattern where the first dashboard visit
triggered 20+ parallel API calls with no cache.

Usage:
    from layer0.data_gateway.bootstrap_engine import BootstrapEngine

    engine = BootstrapEngine(broker)
    result = await engine.bootstrap_plot("plot123", 33.5, -7.6, {
        "crop_type": "wheat",
        "planting_date": "2026-01-15",
    })
"""

from __future__ import annotations

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agribrain.gateway.bootstrap")

# Sources to fetch during bootstrap, ordered by priority
BOOTSTRAP_SOURCES_CORE = [
    # Critical — needed for first dashboard render
    "openweather_current",
    "openweather_forecast",
    "sentinel2_indices",
    "sentinel1_sar",
    "soilgrids",
    "elevation",
    "water_balance",
]

BOOTSTRAP_SOURCES_EXTENDED = [
    # Important — needed for intelligence features
    "sentinel2_ndvi_ts",
    "sentinel1_sar_ts",
    "open_meteo_archive",
    "fire_risk",
    "air_quality",
    "solar_radiation",
    "land_cover",
    "soil_moisture_layers",
    "biomass_estimate",
    "sentinel5p_sif",
]

BOOTSTRAP_SOURCES_BULK = [
    # Heavy — for DNA sequencing (deferred to second pass)
    "bulk_historical_weather",
    "bulk_historical_ndvi",
]


class BootstrapResult:
    """Result of a plot bootstrap operation."""

    def __init__(self):
        self.plot_id: str = ""
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.sources_fetched: List[str] = []
        self.sources_failed: List[str] = []
        self.sources_skipped: List[str] = []
        self.duration_seconds: float = 0.0
        self.errors: Dict[str, str] = {}

    @property
    def success_rate(self) -> float:
        total = len(self.sources_fetched) + len(self.sources_failed)
        return len(self.sources_fetched) / max(1, total)

    def to_dict(self) -> Dict:
        return {
            "plot_id": self.plot_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": round(self.duration_seconds, 1),
            "sources_fetched": len(self.sources_fetched),
            "sources_failed": len(self.sources_failed),
            "sources_skipped": len(self.sources_skipped),
            "success_rate": round(self.success_rate, 3),
            "errors": self.errors,
        }


class BootstrapEngine:
    """Pre-fetches all data when a new plot is created.

    Two-pass approach:
    1. Core pass (parallel): fetches essential data for first dashboard render
    2. Extended pass (parallel): fetches intelligence features
    3. Bulk pass (sequential): fetches historical archives for DNA sequencing

    All fetches go through the DataRequestBroker, so:
    - Spatial consolidation applies (nearby plots share calls)
    - Results are cached in hot tier + promoted to warm tier
    - Metrics are tracked
    """

    def __init__(self, broker=None):
        self._broker = broker
        self._active_bootstraps: Dict[str, BootstrapResult] = {}

    def _get_broker(self):
        """Lazy-load broker."""
        if self._broker is None:
            from layer0.data_gateway.request_broker import DataRequestBroker
            self._broker = DataRequestBroker()
        return self._broker

    def bootstrap_plot(
        self,
        plot_id: str,
        lat: float,
        lng: float,
        plot_info: Optional[Dict] = None,
        skip_bulk: bool = False,
        max_workers: int = 8,
    ) -> BootstrapResult:
        """Bootstrap a new plot with all data sources.

        Args:
            plot_id: Plot identifier
            lat, lng: Plot center coordinates
            plot_info: Optional plot metadata (crop_type, planting_date, etc.)
            skip_bulk: Skip heavy historical fetches (defer to background)
            max_workers: Parallel fetch threads

        Returns:
            BootstrapResult with success/failure details
        """
        result = BootstrapResult()
        result.plot_id = plot_id
        result.started_at = datetime.now(timezone.utc)
        self._active_bootstraps[plot_id] = result

        info = plot_info or {}
        broker = self._get_broker()

        # Build context from plot info
        context = {
            "phenology_stage": "germination",  # New plot starts at germination
            "crop_type": info.get("crop_type", "unknown"),
        }

        # Build extra args for sources that need them
        days_past = 60
        days_future = 14
        now = datetime.now(timezone.utc)
        past_start = (now - timedelta(days=days_past)).strftime("%Y-%m-%d")
        now_str = now.strftime("%Y-%m-%d")

        extra_args = {
            "sentinel2_ndvi_ts": {"days": 180},
            "sentinel1_sar_ts": {"days": days_past},
            "open_meteo_archive": {"start_date": past_start, "end_date": now_str},
            "water_balance": {"days_past": days_past, "days_future": days_future},
        }

        logger.info(
            "[BOOTSTRAP] Starting plot %s at (%.4f, %.4f) crop=%s",
            plot_id[:8], lat, lng, info.get("crop_type", "unknown"),
        )

        # ── Pass 1: Core sources (parallel) ────────────────────────
        core_results = broker.get_bulk(
            BOOTSTRAP_SOURCES_CORE, plot_id, lat, lng,
            context=context, extra_args=extra_args,
        )
        for src, data in core_results.items():
            if data is not None:
                result.sources_fetched.append(src)
            else:
                result.sources_failed.append(src)
                result.errors[src] = "fetch returned None"

        logger.info(
            "[BOOTSTRAP] Core pass: %d/%d succeeded",
            len(result.sources_fetched), len(BOOTSTRAP_SOURCES_CORE),
        )

        # ── Pass 2: Extended sources (parallel) ────────────────────
        ext_results = broker.get_bulk(
            BOOTSTRAP_SOURCES_EXTENDED, plot_id, lat, lng,
            context=context, extra_args=extra_args,
        )
        for src, data in ext_results.items():
            if data is not None:
                result.sources_fetched.append(src)
            else:
                result.sources_failed.append(src)
                result.errors[src] = "fetch returned None"

        logger.info(
            "[BOOTSTRAP] Extended pass: %d/%d succeeded",
            sum(1 for s in BOOTSTRAP_SOURCES_EXTENDED if s in result.sources_fetched),
            len(BOOTSTRAP_SOURCES_EXTENDED),
        )

        # ── Pass 3: Bulk historical (optional, sequential) ────────
        if not skip_bulk:
            for src in BOOTSTRAP_SOURCES_BULK:
                try:
                    data = broker.get(src, plot_id, lat, lng, context=context)
                    if data is not None:
                        result.sources_fetched.append(src)
                    else:
                        result.sources_skipped.append(src)
                except Exception as e:
                    result.sources_skipped.append(src)
                    result.errors[src] = str(e)
                    logger.warning("[BOOTSTRAP] Bulk source %s skipped: %s", src, e)
        else:
            result.sources_skipped.extend(BOOTSTRAP_SOURCES_BULK)
            logger.info("[BOOTSTRAP] Bulk historical deferred to background")

        # ── Finalize ───────────────────────────────────────────────
        result.completed_at = datetime.now(timezone.utc)
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

        # Clean up active bootstrap
        self._active_bootstraps.pop(plot_id, None)

        logger.info(
            "[BOOTSTRAP] Plot %s complete in %.1fs: %d fetched, %d failed, %d skipped",
            plot_id[:8], result.duration_seconds,
            len(result.sources_fetched), len(result.sources_failed),
            len(result.sources_skipped),
        )

        return result

    def get_active_bootstraps(self) -> Dict[str, Dict]:
        """Get status of currently running bootstraps."""
        return {
            pid: r.to_dict()
            for pid, r in self._active_bootstraps.items()
        }

    def is_bootstrapping(self, plot_id: str) -> bool:
        """Check if a plot is currently being bootstrapped."""
        return plot_id in self._active_bootstraps
