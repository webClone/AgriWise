"""
Request Consolidator — Spatial batching for API call efficiency.

Plots within 5km of each other share the same API call for sources
where the spatial resolution is coarser than that distance
(weather, soil, air quality, fire risk).

This prevents N plots in the same farm from making N identical API calls.

Usage:
    from layer0.data_gateway.request_consolidator import RequestConsolidator

    consolidator = RequestConsolidator()
    batch = consolidator.get_or_create_batch("openweather_current", 33.5, -7.6)
    # batch.key is shared across all plots within 5km
"""

from __future__ import annotations

import time
import math
import logging
import hashlib
import threading
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("agribrain.gateway.consolidator")

# Sources eligible for spatial consolidation (coarse resolution)
CONSOLIDABLE_SOURCES = {
    "openweather_current",     # ~10km grid
    "openweather_forecast",    # ~10km grid
    "open_meteo_archive",      # ~11km grid
    "fire_risk",               # ~375m FIRMS, but risk is regional
    "air_quality",             # ~10km grid
    "solar_radiation",         # ~11km grid
    "elevation",               # ~30m but static (pointless to repeat)
    "sentinel5p_sif",          # ~7km resolution
    "sentinel5p_sif_ts",       # ~7km resolution
    "bulk_historical_weather", # ~11km grid
}

# Spatial snap grid size (degrees, ~5km at equator)
SNAP_DEGREES = 0.045  # ~5km


@dataclass
class ConsolidatedBatch:
    """A shared batch for nearby plots requesting the same source."""
    key: str                     # Composite key for this batch
    source: str
    lat_snap: float             # Snapped latitude
    lng_snap: float             # Snapped longitude
    created_at: float           # timestamp
    plot_ids: List[str] = field(default_factory=list)
    result: Optional[Any] = None
    is_fetched: bool = False
    is_fetching: bool = False
    fetch_error: Optional[str] = None

    def add_plot(self, plot_id: str):
        if plot_id not in self.plot_ids:
            self.plot_ids.append(plot_id)


class RequestConsolidator:
    """Spatial batching engine to reduce duplicate API calls.

    When multiple plots within ~5km request the same source,
    only one API call is made and the result is shared.

    How it works:
    1. Incoming request coordinates are snapped to a ~5km grid
    2. If a batch already exists for that grid cell + source, join it
    3. First joiner triggers the actual fetch
    4. All joiners receive the same result

    Only applies to sources in CONSOLIDABLE_SOURCES (coarse resolution).
    Fine-resolution sources (Sentinel-2, Sentinel-1) are NOT consolidated.
    """

    def __init__(self, ttl_seconds: int = 300):
        """
        Args:
            ttl_seconds: How long a completed batch is kept (default 5 min).
                         After this, a new batch is created for fresh data.
        """
        self._lock = threading.Lock()
        self._batches: Dict[str, ConsolidatedBatch] = {}
        self._ttl = ttl_seconds

    def should_consolidate(self, source: str) -> bool:
        """Check if this source benefits from spatial consolidation."""
        return source in CONSOLIDABLE_SOURCES

    def get_or_create_batch(
        self, source: str, lat: float, lng: float, plot_id: str = "",
        param_hash: str = "", **kwargs,
    ) -> ConsolidatedBatch:
        """Get an existing batch or create a new one.

        If a fresh batch already exists for this grid cell and matching request parameters,
        join it (the result will be shared).
        """
        lat_snap = _snap(lat)
        lng_snap = _snap(lng)
        key_parts = [source, f"{lat_snap:.4f}", f"{lng_snap:.4f}"]
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        if start_date or end_date:
            key_parts.append(f"{start_date or ''}_{end_date or ''}")
        if param_hash:
            key_parts.append(param_hash)
        elif kwargs:
            clean_kwargs = {k: str(v) for k, v in kwargs.items() if k not in ("plot_id",)}
            if clean_kwargs:
                raw = repr(sorted(clean_kwargs.items())).encode("utf-8")
                key_parts.append(hashlib.sha256(raw).hexdigest()[:12])
        key = ":".join(key_parts)

        with self._lock:
            now = time.time()

            # Clean expired batches
            expired = [
                k for k, b in self._batches.items()
                if b.is_fetched and (now - b.created_at) > self._ttl
            ]
            for k in expired:
                del self._batches[k]

            # Check for existing batch
            batch = self._batches.get(key)
            if batch is not None and not batch.fetch_error:
                batch.add_plot(plot_id)
                if len(batch.plot_ids) > 1:
                    logger.debug(
                        "[CONSOLIDATOR] Joined batch %s (now %d plots)",
                        key, len(batch.plot_ids),
                    )
                return batch

            # Create new batch
            batch = ConsolidatedBatch(
                key=key,
                source=source,
                lat_snap=lat_snap,
                lng_snap=lng_snap,
                created_at=now,
            )
            batch.add_plot(plot_id)
            self._batches[key] = batch
            return batch

    def complete_batch(
        self, batch: ConsolidatedBatch, result: Any, error: Optional[str] = None,
    ):
        """Mark a batch as completed with its result."""
        batch.result = result
        batch.is_fetched = True
        batch.is_fetching = False
        batch.fetch_error = error

        if error:
            logger.warning(
                "[CONSOLIDATOR] Batch %s failed: %s", batch.key, error,
            )
        elif len(batch.plot_ids) > 1:
            logger.info(
                "[CONSOLIDATOR] Batch %s served %d plots with 1 API call",
                batch.key, len(batch.plot_ids),
            )

    def get_stats(self) -> Dict:
        """Get consolidation statistics."""
        with self._lock:
            total_batches = len(self._batches)
            active = sum(1 for b in self._batches.values() if not b.is_fetched)
            completed = sum(1 for b in self._batches.values() if b.is_fetched)
            total_plots_served = sum(len(b.plot_ids) for b in self._batches.values())
            api_calls_saved = max(0, total_plots_served - total_batches)

            return {
                "total_batches": total_batches,
                "active": active,
                "completed": completed,
                "total_plots_served": total_plots_served,
                "api_calls_saved": api_calls_saved,
                "savings_pct": round(
                    api_calls_saved / max(1, total_plots_served) * 100, 1
                ),
            }


def _snap(coord: float) -> float:
    """Snap coordinate to the consolidation grid."""
    return round(coord / SNAP_DEGREES) * SNAP_DEGREES
