"""
NASA POWER Agroclimate Fallback.

Normalizes pre-fetched NASA POWER daily data for radiation/temperature fallback.
V1.1: stub module — accepts pre-fetched/mocked data only. No live API calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class NASAPowerDailyRecord:
    """NASA POWER daily record."""
    date: str = ""
    provider: str = "nasa_power"

    # Radiation (MJ/m²/day)
    allsky_sfc_sw_dwn: Optional[float] = None  # All-sky surface shortwave downward
    clrsky_sfc_sw_dwn: Optional[float] = None  # Clear-sky surface shortwave

    # Temperature (°C)
    t2m_max: Optional[float] = None
    t2m_min: Optional[float] = None
    t2m_mean: Optional[float] = None

    # Humidity
    rh2m: Optional[float] = None  # %

    # Wind (m/s)
    ws2m: Optional[float] = None  # Wind speed at 2m

    # ET₀ (mm/day) — if available
    et0_mm: Optional[float] = None

    # Precipitation (mm)
    prectotcorr: Optional[float] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None


def normalize_nasa_power_daily(
    raw_data: Dict[str, Any],
) -> List[NASAPowerDailyRecord]:
    """Parse pre-fetched NASA POWER daily JSON.

    Expected format:
    {
        "properties": {
            "parameter": {
                "ALLSKY_SFC_SW_DWN": {"20260420": 18.5, ...},
                "T2M_MAX": {"20260420": 25.3, ...},
                ...
            }
        },
        "geometry": {"coordinates": [lon, lat]}
    }
    """
    params = raw_data.get("properties", {}).get("parameter", {})
    coords = raw_data.get("geometry", {}).get("coordinates", [None, None])
    lon, lat = coords[0], coords[1] if len(coords) >= 2 else (None, None)

    # Get all dates from any parameter
    all_dates = set()
    for param_values in params.values():
        if isinstance(param_values, dict):
            all_dates.update(param_values.keys())

    records = []
    for date_key in sorted(all_dates):
        # Format date from YYYYMMDD to YYYY-MM-DD
        if len(date_key) == 8:
            date = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}"
        else:
            date = date_key

        rec = NASAPowerDailyRecord(
            date=date,
            latitude=lat,
            longitude=lon,
            allsky_sfc_sw_dwn=_get_param(params, "ALLSKY_SFC_SW_DWN", date_key),
            clrsky_sfc_sw_dwn=_get_param(params, "CLRSKY_SFC_SW_DWN", date_key),
            t2m_max=_get_param(params, "T2M_MAX", date_key),
            t2m_min=_get_param(params, "T2M_MIN", date_key),
            t2m_mean=_get_param(params, "T2M", date_key),
            rh2m=_get_param(params, "RH2M", date_key),
            ws2m=_get_param(params, "WS2M", date_key),
            prectotcorr=_get_param(params, "PRECTOTCORR", date_key),
        )
        records.append(rec)

    return records


def _get_param(params: Dict, name: str, date_key: str) -> Optional[float]:
    """Safely get parameter value. NASA POWER uses -999 for missing."""
    param = params.get(name, {})
    if isinstance(param, dict):
        val = param.get(date_key)
        if val is not None and val != -999 and val != -999.0:
            return val
    return None
