"""
Baseline Model — hour-bucketed in-memory ring buffer with histogram descriptors.

Each camera stores stats + histogram per hour-of-day (0-23). When a new frame
arrives, scene_stability compares it against the same-hour baseline using both
scalar stats AND histogram correlation.

This prevents false alarms from normal diurnal lighting variation while
detecting real structural changes via feature comparison.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import deque

try:
    import numpy as np
    import cv2
    HAS_CV2 = True
except ImportError:
    np = None  # type: ignore
    cv2 = None  # type: ignore
    HAS_CV2 = False


@dataclass
class BaselineEntry:
    """Snapshot of key stats + feature descriptors at a specific time."""
    # Scalar stats
    green_ratio: float = 0.33
    brightness_mean: float = 128.0
    saturation_mean: float = 100.0
    green_coverage_fraction: float = 0.3
    edge_density: float = 0.05
    crop_fraction: float = 0.3

    # Feature descriptors (only populated with cv2)
    hsv_histogram: Optional[Any] = None   # normalized HSV histogram
    gray_thumbnail: Optional[Any] = None  # 64x64 uint8 for SSIM

    # Metadata
    captured_at: Optional[datetime] = None
    frame_ref: str = ""


class BaselineModel:
    """
    Hour-bucketed baseline storage for fixed cameras.

    Structure: {camera_id: {hour_bucket: deque[BaselineEntry]}}
    Each hour bucket keeps the last MAX_ENTRIES entries (ring buffer).
    """

    MAX_ENTRIES = 7  # 7 days of same-hour baselines

    def __init__(self):
        # {camera_id: {hour(0-23): deque[BaselineEntry]}}
        self._baselines: Dict[str, Dict[int, deque]] = {}
        # Slow-moving seasonal average per camera
        self._seasonal: Dict[str, BaselineEntry] = {}

    def get_time_of_day_baseline(
        self, camera_id: str, target_time: Optional[datetime]
    ) -> Optional[BaselineEntry]:
        """
        Retrieve the most recent baseline entry for this camera
        at the same hour-of-day. Returns None if no baseline exists.
        """
        if camera_id not in self._baselines:
            return None

        hour = target_time.hour if target_time else 12
        buckets = self._baselines[camera_id]

        if hour in buckets and len(buckets[hour]) > 0:
            return buckets[hour][-1]

        # Try adjacent hours (+/-1, +/-2) as fallback
        for offset in [1, -1, 2, -2]:
            adj = (hour + offset) % 24
            if adj in buckets and len(buckets[adj]) > 0:
                return buckets[adj][-1]

        return None

    def update_baseline(
        self,
        camera_id: str,
        current_time: Optional[datetime],
        green_ratio: float,
        brightness_mean: float,
        saturation_mean: float,
        green_coverage_fraction: float = 0.0,
        edge_density: float = 0.0,
        hsv_histogram: Optional[Any] = None,
        gray_thumbnail: Optional[Any] = None,
        frame_ref: str = "",
    ) -> None:
        """Store a new baseline entry in the appropriate hour bucket."""
        if camera_id not in self._baselines:
            self._baselines[camera_id] = {}

        hour = current_time.hour if current_time else 12
        if hour not in self._baselines[camera_id]:
            self._baselines[camera_id][hour] = deque(maxlen=self.MAX_ENTRIES)

        entry = BaselineEntry(
            green_ratio=green_ratio,
            brightness_mean=brightness_mean,
            saturation_mean=saturation_mean,
            green_coverage_fraction=green_coverage_fraction,
            edge_density=edge_density,
            crop_fraction=green_coverage_fraction,
            hsv_histogram=hsv_histogram,
            gray_thumbnail=gray_thumbnail,
            captured_at=current_time,
            frame_ref=frame_ref,
        )
        self._baselines[camera_id][hour].append(entry)

    def compare_histogram(
        self, current_hist: Any, baseline_hist: Any
    ) -> float:
        """
        Compare two HSV histograms using correlation.
        Returns 0.0 (no match) to 1.0 (identical).
        Returns 0.5 if either histogram is None.
        """
        if current_hist is None or baseline_hist is None:
            return 0.5
        if not HAS_CV2:
            return 0.5
        try:
            score = cv2.compareHist(
                current_hist.astype(np.float32),
                baseline_hist.astype(np.float32),
                cv2.HISTCMP_CORREL
            )
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.5

    def update_seasonal_baseline(
        self, camera_id: str, green_ratio: float,
        brightness_mean: float, saturation_mean: float,
    ) -> None:
        """Exponential moving average for slow seasonal drift."""
        alpha = 0.05
        if camera_id not in self._seasonal:
            self._seasonal[camera_id] = BaselineEntry(
                green_ratio=green_ratio,
                brightness_mean=brightness_mean,
                saturation_mean=saturation_mean,
            )
        else:
            s = self._seasonal[camera_id]
            s.green_ratio = alpha * green_ratio + (1 - alpha) * s.green_ratio
            s.brightness_mean = alpha * brightness_mean + (1 - alpha) * s.brightness_mean
            s.saturation_mean = alpha * saturation_mean + (1 - alpha) * s.saturation_mean

    def get_seasonal_baseline(self, camera_id: str) -> Optional[BaselineEntry]:
        return self._seasonal.get(camera_id)

    def reset_baseline_for_event(self, camera_id: str, event_type: str) -> None:
        """
        Hard reset all baselines for a camera when a major event occurs.
        Events: 'harvest', 'pruning', 'mowing', 'replanting'
        """
        if camera_id in self._baselines:
            self._baselines[camera_id] = {}
        if camera_id in self._seasonal:
            del self._seasonal[camera_id]

    def has_baseline(self, camera_id: str) -> bool:
        if camera_id not in self._baselines:
            return False
        return any(len(q) > 0 for q in self._baselines[camera_id].values())
