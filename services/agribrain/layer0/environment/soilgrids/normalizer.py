"""
SoilGrids Normalizer.

Converts raw SoilGrids API/tile responses into canonical SoilGridsProfile.
Enforces exact unit conversions and labels everything as soil_prior.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.soilgrids.schemas import (
    SOILGRIDS_CORE_PROPERTIES,
    SOILGRIDS_DEPTH_LABELS,
    SOILGRIDS_DEPTH_THICKNESS_MM,
    SOILGRIDS_PROPERTY_ALIASES,
    SOILGRIDS_UNIT_CONVERSIONS,
    SoilGridsDepthLayer,
    SoilGridsProfile,
    SoilGridsPropertyValue,
)


def _resolve_property_id(raw_id: str) -> str:
    """Map aliased property names to canonical IDs."""
    canonical = SOILGRIDS_PROPERTY_ALIASES.get(raw_id, raw_id)
    return canonical


def _convert_value(prop_id: str, raw_value: Optional[float]) -> Optional[float]:
    """Apply the exact unit conversion for a SoilGrids property."""
    if raw_value is None:
        return None
    conv = SOILGRIDS_UNIT_CONVERSIONS.get(prop_id)
    if conv is None:
        return raw_value
    return raw_value / conv["factor"]


def normalize_soilgrids_response(
    raw_data: Dict[str, Any],
    latitude: float,
    longitude: float,
    soilgrids_version: str = "2.0",
    access_method: str = "mocked_fixture",
) -> SoilGridsProfile:
    """
    Convert a raw SoilGrids response dict to a SoilGridsProfile.

    Expected raw_data format:
    {
        "0-5cm": {
            "bdod": {"mean": 1350, "Q0.05": 1200, "Q0.5": 1340, "Q0.95": 1500},
            "clay": {"mean": 250, ...},
            ...
        },
        "5-15cm": { ... },
        ...
    }

    All values are raw (before unit conversion).
    """
    if not _validate_coordinates(latitude, longitude):
        raise ValueError(
            f"Invalid coordinates: lat={latitude}, lon={longitude}. "
            "Must be -90≤lat≤90, -180≤lon≤180."
        )

    depth_layers: Dict[str, SoilGridsDepthLayer] = {}

    for depth_label in SOILGRIDS_DEPTH_LABELS:
        depth_data = raw_data.get(depth_label, {})
        thickness = SOILGRIDS_DEPTH_THICKNESS_MM.get(depth_label, 0)

        properties: Dict[str, SoilGridsPropertyValue] = {}

        for raw_prop_id, prop_data in depth_data.items():
            prop_id = _resolve_property_id(raw_prop_id)

            if prop_id not in SOILGRIDS_CORE_PROPERTIES:
                continue  # Skip unknown or optional properties in V1

            conv = SOILGRIDS_UNIT_CONVERSIONS.get(prop_id, {})
            raw_mean = prop_data.get("mean")

            properties[prop_id] = SoilGridsPropertyValue(
                property_id=prop_id,
                depth_label=depth_label,
                mean=_convert_value(prop_id, raw_mean),
                q005=_convert_value(prop_id, prop_data.get("Q0.05")),
                q050=_convert_value(prop_id, prop_data.get("Q0.5")),
                q095=_convert_value(prop_id, prop_data.get("Q0.95")),
                unit=conv.get("output_unit", ""),
                raw_value=raw_mean,
                conversion_factor=conv.get("factor", 1.0),
                label="soil_prior",
            )

        depth_layers[depth_label] = SoilGridsDepthLayer(
            depth_label=depth_label,
            thickness_mm=thickness,
            properties=properties,
        )

    return SoilGridsProfile(
        latitude=latitude,
        longitude=longitude,
        depth_layers=depth_layers,
        soilgrids_version=soilgrids_version,
        access_method=access_method,
    )


def _validate_coordinates(lat: float, lon: float) -> bool:
    """Check lat/lon are within valid global bounds."""
    return -90 <= lat <= 90 and -180 <= lon <= 180
