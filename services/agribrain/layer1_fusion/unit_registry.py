"""
Layer 1 Unit Registry.

Canonical unit definitions and verification.
Verify-only mode: reject non-canonical units, do not silently convert.

All internal unit names are ASCII-safe.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple


# Canonical internal → display mapping
UNIT_DISPLAY_MAP: Dict[str, str] = {
    "degC": "°C",
    "fraction": "—",
    "percent": "%",
    "mm": "mm",
    "mm_day": "mm/day",
    "mm_h": "mm/h",
    "m_s": "m/s",
    "kPa": "kPa",
    "dS_m": "dS/m",
    "pH": "pH",
    "kg_ha": "kg/ha",
    "W_m2": "W/m²",
    "umol_m2_s": "µmol/m²/s",
    "dBm": "dBm",
    "dB": "dB",
    "m2": "m²",
    "cm": "cm",
    "L": "L",
    "L_min": "L/min",
    "deg": "°",
    "min": "min",
    "bar": "bar",
    "V": "V",
    "ratio": "ratio",
    "score": "score",
    "index": "index",
    "count": "count",
    "bool": "bool",
    "class": "class",
    "linear_power": "linear power",
    "db": "dB (raster)",
}

# All canonical unit keys
CANONICAL_UNIT_KEYS = frozenset(UNIT_DISPLAY_MAP.keys())


def is_canonical_unit(unit: Optional[str]) -> bool:
    """Check if a unit is in the canonical registry."""
    if unit is None:
        return True  # None is valid (unitless evidence)
    return unit in CANONICAL_UNIT_KEYS


def display_unit(unit: Optional[str]) -> str:
    """Return human-readable display string for a canonical unit."""
    if unit is None:
        return "—"
    return UNIT_DISPLAY_MAP.get(unit, unit)


def verify_unit(unit: Optional[str]) -> Tuple[bool, str]:
    """Verify-only: check if unit is canonical.

    Returns (is_valid, message).
    Does NOT silently convert. If the unit is wrong, the evidence
    must be quarantined.
    """
    if unit is None:
        return True, "unitless (ok)"
    if unit in CANONICAL_UNIT_KEYS:
        return True, f"canonical unit: {unit}"
    return False, f"NON_CANONICAL_UNIT: '{unit}' — quarantine evidence"
