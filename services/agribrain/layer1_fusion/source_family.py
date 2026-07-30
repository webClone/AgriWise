"""
Shared Source Family normalization helper for Layer 1.

Provides consistent translation and mapping of various source family strings
emitted by Layer 0 wrappers or pipelines.
"""

SOURCE_FAMILY_ALIASES = {
    "sensors": "sensor",
    "sensor_iot": "sensor",

    "sentinel_2": "sentinel2",
    "sentinel-2": "sentinel2",
    "s2": "sentinel2",

    "sentinel_1": "sentinel1",
    "sentinel-1": "sentinel1",
    "s1": "sentinel1",

    "weather": "environment",
    "weather_reanalysis": "environment",
    "soilgrids": "environment",
    "fao": "environment",

    "weather_forecast": "weather_forecast",
}

def normalize_source_family(value: str) -> str:
    """Normalize source family string to standard Layer 1 canonical family names."""
    if not value:
        return ""
    val_clean = value.lower().strip()
    return SOURCE_FAMILY_ALIASES.get(val_clean, val_clean)
