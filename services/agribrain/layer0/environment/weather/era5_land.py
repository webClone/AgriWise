"""
ERA5-Land Climate Baseline.

Normalizes pre-fetched ERA5-Land reanalysis data for climate baseline context.
V1.1: stub module — accepts pre-fetched/mocked data only. No live API calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ERA5LandDailyRecord:
    """ERA5-Land daily reanalysis record."""
    date: str = ""
    provider: str = "era5_land"

    # Temperature (°C)
    t2m_max: Optional[float] = None
    t2m_min: Optional[float] = None
    t2m_mean: Optional[float] = None

    # Soil moisture (m³/m³)
    swvl1: Optional[float] = None  # 0-7cm
    swvl2: Optional[float] = None  # 7-28cm
    swvl3: Optional[float] = None  # 28-100cm
    swvl4: Optional[float] = None  # 100-289cm

    # ET (mm/day)
    total_evaporation_mm: Optional[float] = None

    # Precipitation (mm)
    total_precipitation_mm: Optional[float] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass
class ClimateBaseline:
    """ERA5-Land climate baseline context."""
    temperature_anomaly_c: Optional[float] = None  # vs 30-year mean
    soil_moisture_anomaly_pct: Optional[float] = None
    et_anomaly_pct: Optional[float] = None
    drydown_context: Optional[str] = None  # "normal" | "drying" | "wetting"
    period_start: str = ""
    period_end: str = ""
    record_count: int = 0


def normalize_era5land_daily(
    raw_data: Dict[str, Any],
) -> List[ERA5LandDailyRecord]:
    """Parse pre-fetched ERA5-Land daily data.

    Expected format:
    {
        "records": [
            {"date": "2026-01-01", "t2m_max": 25.3, "swvl1": 0.28, ...},
            ...
        ],
        "latitude": -1.23,
        "longitude": 36.82
    }
    """
    records_raw = raw_data.get("records", [])
    lat = raw_data.get("latitude")
    lon = raw_data.get("longitude")

    records = []
    for r in records_raw:
        records.append(ERA5LandDailyRecord(
            date=r.get("date", ""),
            latitude=lat,
            longitude=lon,
            t2m_max=r.get("t2m_max"),
            t2m_min=r.get("t2m_min"),
            t2m_mean=r.get("t2m_mean"),
            swvl1=r.get("swvl1"),
            swvl2=r.get("swvl2"),
            swvl3=r.get("swvl3"),
            swvl4=r.get("swvl4"),
            total_evaporation_mm=r.get("total_evaporation_mm"),
            total_precipitation_mm=r.get("total_precipitation_mm"),
        ))
    return records


def compute_climate_baseline(
    records: List[ERA5LandDailyRecord],
    climatology_means: Optional[Dict[str, float]] = None,
) -> ClimateBaseline:
    """Compute climate baseline from ERA5-Land records.

    In V1.1 this is a simplified stub. Real implementation needs 30-year normals.
    """
    if not records:
        return ClimateBaseline()

    temps = [r.t2m_mean for r in records if r.t2m_mean is not None]
    sm_values = [r.swvl1 for r in records if r.swvl1 is not None]

    # Simple anomaly (placeholder — real needs climatology normals)
    temp_mean = sum(temps) / len(temps) if temps else None
    sm_mean = sum(sm_values) / len(sm_values) if sm_values else None

    temp_anomaly = None
    if temp_mean is not None and climatology_means and "temperature" in climatology_means:
        temp_anomaly = round(temp_mean - climatology_means["temperature"], 2)

    # Drydown context from soil moisture trend
    drydown = "normal"
    if len(sm_values) >= 3:
        if sm_values[-1] < sm_values[0] * 0.9:
            drydown = "drying"
        elif sm_values[-1] > sm_values[0] * 1.1:
            drydown = "wetting"

    return ClimateBaseline(
        temperature_anomaly_c=temp_anomaly,
        drydown_context=drydown,
        period_start=records[0].date if records else "",
        period_end=records[-1].date if records else "",
        record_count=len(records),
    )
