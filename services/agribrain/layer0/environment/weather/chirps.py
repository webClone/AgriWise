"""
CHIRPS Rainfall Baseline.

Normalizes pre-fetched CHIRPS 0.05° rainfall data for drought context.
V1.1: stub module — accepts pre-fetched/mocked data only. No live API calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CHIRPSDailyRecord:
    """CHIRPS daily rainfall record."""
    date: str = ""
    precipitation_mm: float = 0.0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    resolution_deg: float = 0.05


@dataclass
class CHIRPSBaseline:
    """CHIRPS rainfall baseline context."""
    rainfall_7d_percentile: Optional[float] = None   # 0-100
    rainfall_30d_percentile: Optional[float] = None
    rainfall_90d_percentile: Optional[float] = None
    season_to_date_percentile: Optional[float] = None
    drought_context_score: float = 0.0  # 0=wet, 1=severe drought
    period_start: str = ""
    period_end: str = ""
    record_count: int = 0


def normalize_chirps_daily(
    raw_data: Dict[str, Any],
) -> List[CHIRPSDailyRecord]:
    """Parse pre-fetched CHIRPS daily rainfall data.

    Expected format:
    {
        "records": [{"date": "2026-01-01", "precipitation": 5.2}, ...],
        "latitude": -1.23,
        "longitude": 36.82
    }
    """
    records_raw = raw_data.get("records", [])
    lat = raw_data.get("latitude")
    lon = raw_data.get("longitude")

    records = []
    for r in records_raw:
        records.append(CHIRPSDailyRecord(
            date=r.get("date", ""),
            precipitation_mm=r.get("precipitation", 0.0),
            latitude=lat,
            longitude=lon,
        ))
    return records


def compute_rainfall_baseline(
    records: List[CHIRPSDailyRecord],
    climatology_percentiles: Optional[Dict[str, float]] = None,
) -> CHIRPSBaseline:
    """Compute rainfall baseline and drought context from CHIRPS records.

    Args:
        records: sorted list of daily CHIRPS records
        climatology_percentiles: optional {period: percentile_threshold}
    """
    if not records:
        return CHIRPSBaseline()

    # Compute cumulative rainfall for different periods
    rain_values = [r.precipitation_mm for r in records]
    n = len(rain_values)

    rain_7d = sum(rain_values[-7:]) if n >= 7 else sum(rain_values)
    rain_30d = sum(rain_values[-30:]) if n >= 30 else sum(rain_values)
    rain_90d = sum(rain_values[-90:]) if n >= 90 else sum(rain_values)

    # Simple percentile estimation (placeholder — real CHIRPS uses historical distribution)
    # In V1.1 this is a stub; real percentile calculation needs climatology
    p7 = _estimate_percentile(rain_7d, expected_mm=35.0)
    p30 = _estimate_percentile(rain_30d, expected_mm=120.0)
    p90 = _estimate_percentile(rain_90d, expected_mm=300.0)

    # Drought context: 0=wet, 1=severe drought
    # Based on 30-day percentile
    drought = max(0.0, min(1.0, 1.0 - (p30 / 100.0)))

    return CHIRPSBaseline(
        rainfall_7d_percentile=round(p7, 1),
        rainfall_30d_percentile=round(p30, 1),
        rainfall_90d_percentile=round(p90, 1),
        drought_context_score=round(drought, 2),
        period_start=records[0].date if records else "",
        period_end=records[-1].date if records else "",
        record_count=n,
    )


def _estimate_percentile(actual_mm: float, expected_mm: float) -> float:
    """Simple percentile estimate. Real implementation uses historical distribution."""
    if expected_mm <= 0:
        return 50.0
    ratio = actual_mm / expected_mm
    return min(100.0, max(0.0, ratio * 50.0))
