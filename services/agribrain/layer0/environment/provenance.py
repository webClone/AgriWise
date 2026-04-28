"""
Environmental Provenance.

Mandatory provenance for environmental context.
Missing coordinates → fatal EnvironmentalProvenanceError.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class EnvironmentalProvenanceError(Exception):
    """Fatal error when required provenance is missing."""
    pass


REQUIRED_PROVENANCE_FIELDS = [
    "latitude", "longitude",
]


def build_provenance(
    latitude: float,
    longitude: float,
    coordinate_crs: str = "EPSG:4326",
    soilgrids_version: str = "",
    soilgrids_access_method: str = "mocked_fixture",
    fao_dataset_name: str = "HWSD",
    fao_dataset_version: str = "v2.0",
    fao_resolution_m: float = 1000.0,
    weather_providers: Optional[List[str]] = None,
    weather_model_or_product: str = "",
    weather_run_time: Optional[str] = None,
    timezone: str = "UTC",
    retrieval_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Build provenance dict for environmental context.

    Raises EnvironmentalProvenanceError if coordinates are missing/invalid.
    """
    if latitude is None or longitude is None:
        raise EnvironmentalProvenanceError(
            "Coordinates are mandatory for environmental provenance. "
            f"Got latitude={latitude}, longitude={longitude}"
        )

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise EnvironmentalProvenanceError(
            f"Invalid coordinates: lat={latitude}, lon={longitude}"
        )

    return {
        "latitude": latitude,
        "longitude": longitude,
        "coordinate_crs": coordinate_crs,
        "soilgrids_version": soilgrids_version,
        "soilgrids_access_method": soilgrids_access_method,
        "fao_dataset_name": fao_dataset_name,
        "fao_dataset_version": fao_dataset_version,
        "fao_resolution_m": fao_resolution_m,
        "weather_providers": weather_providers or [],
        "weather_model_or_product": weather_model_or_product,
        "weather_run_time": weather_run_time,
        "timezone": timezone,
        "retrieval_timestamp": retrieval_timestamp,
    }
