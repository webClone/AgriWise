"""
Layer 1 Freshness Scoring.

Source-specific freshness scoring based on observation age.

Rules:
- Sensor < 6h = high, < 24h = good, < 7d = fair
- S2 < 5d = good, < 12d = fair
- S1 < 6d = good
- SoilGrids = no decay (static)
- Forecast day 0 = high, day 5 = low
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from .schemas import EvidenceItem


# Source-specific freshness decay curves (max_age_hours → freshness_score)
_FRESHNESS_CURVES = {
    "sensor": [
        (6, 0.95), (24, 0.80), (72, 0.60), (168, 0.30), (720, 0.10),
    ],
    "sentinel2": [
        (120, 0.85), (240, 0.65), (480, 0.40), (720, 0.20),
    ],
    "sentinel1": [
        (144, 0.80), (288, 0.60), (576, 0.35),
    ],
    "environment": [
        (24, 0.80), (72, 0.60), (168, 0.40), (720, 0.20),
    ],
    "weather_forecast": [
        (24, 0.80), (48, 0.65), (72, 0.50), (96, 0.35), (120, 0.25), (144, 0.20), (168, 0.15),
    ],
    "geo_context": [],  # static — no decay
    "perception": [
        (24, 0.70), (72, 0.50), (168, 0.25),
    ],
    "user_event": [
        (24, 0.90), (72, 0.75), (168, 0.50),
    ],
    "history": [
        (0, 0.30),  # always stale
    ],
}


def compute_freshness(
    item: EvidenceItem, run_timestamp: datetime
) -> float:
    """Compute freshness score for a single evidence item."""
    # Static priors never decay
    if item.observation_type == "static_prior":
        return 1.0

    # Historical carry-forward is always low
    if "HISTORICAL" in item.flags or "STALE" in item.flags:
        return 0.10

    # If no observed_at, use moderate default
    if item.observed_at is None:
        return 0.50

    age_hours = (run_timestamp - item.observed_at).total_seconds() / 3600.0
    if age_hours < 0:
        age_hours = 0

    curve = _FRESHNESS_CURVES.get(item.source_family, [])

    # Static sources (empty curve)
    if not curve:
        return 1.0

    # Walk the curve
    prev_score = 1.0
    for max_age, score in curve:
        if age_hours <= max_age:
            return score
        prev_score = score

    # Beyond last threshold
    return max(0.05, prev_score * 0.5)


def compute_freshness_batch(
    items: List[EvidenceItem], run_timestamp: datetime
) -> List[EvidenceItem]:
    """Compute freshness for all items and update their freshness_score."""
    for item in items:
        item.freshness_score = compute_freshness(item, run_timestamp)
    return items
