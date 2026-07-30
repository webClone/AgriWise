"""
TTL Registry — Source-aware TTL configuration for 24+ data sources.

Each source type has:
  - default: base TTL in seconds
  - min: absolute minimum (prevents API abuse)
  - max: absolute maximum (prevents stale data)
  - volatility: how fast the data changes (static|low|medium|high)
  - revisit_days: satellite revisit cycle (for satellite sources)

The AdaptiveTTLEngine reads from this registry and adjusts TTLs
dynamically based on context signals (volatility, activity, season, anomaly).

Usage:
    from layer0.data_gateway.ttl_registry import TTL_REGISTRY, get_base_ttl
    
    ttl = get_base_ttl("soilgrids")  # → 2592000 (30 days)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class SourceTTLConfig:
    """TTL configuration for a single data source."""
    default: int           # Default TTL in seconds
    min: int               # Minimum TTL (floor, prevents API abuse)
    max: int               # Maximum TTL (ceiling, prevents staleness)
    volatility: str        # "static" | "low" | "medium" | "high"
    revisit_days: Optional[float] = None  # Satellite revisit (days), None for non-satellite
    description: str = ""


# ── 24+ Source TTL Definitions ──────────────────────────────────────────

TTL_REGISTRY: Dict[str, SourceTTLConfig] = {

    # ── Sentinel-2 (Optical / Vegetation Indices) ──────────────────
    "sentinel2_indices": SourceTTLConfig(
        default=4 * 3600,        # 4 hours
        min=1800,                # 30 min
        max=24 * 3600,           # 24 hours
        volatility="low",
        revisit_days=5.0,
        description="Sentinel-2 L2A vegetation indices (NDVI, EVI, NDWI, NDMI)",
    ),
    "sentinel2_ndvi_ts": SourceTTLConfig(
        default=6 * 3600,        # 6 hours
        min=3600,                # 1 hour
        max=48 * 3600,           # 48 hours
        volatility="low",
        revisit_days=5.0,
        description="Sentinel-2 NDVI timeseries (180-day history)",
    ),

    # ── Sentinel-1 (SAR / Soil Moisture) ───────────────────────────
    "sentinel1_sar": SourceTTLConfig(
        default=4 * 3600,        # 4 hours
        min=1800,                # 30 min
        max=24 * 3600,           # 24 hours
        volatility="low",
        revisit_days=6.0,
        description="Sentinel-1 SAR backscatter (VV, VH, soil moisture proxy)",
    ),
    "sentinel1_sar_ts": SourceTTLConfig(
        default=6 * 3600,        # 6 hours
        min=3600,                # 1 hour
        max=48 * 3600,           # 48 hours
        volatility="low",
        revisit_days=6.0,
        description="Sentinel-1 SAR timeseries",
    ),

    # ── Sentinel-5P (TROPOMI SIF/PRI) ─────────────────────────────
    "sentinel5p_sif": SourceTTLConfig(
        default=6 * 3600,        # 6 hours
        min=3600,                # 1 hour
        max=24 * 3600,           # 24 hours
        volatility="low",
        revisit_days=1.0,        # Daily revisit (but ~7km resolution)
        description="Sentinel-5P TROPOMI Solar-Induced Fluorescence (SIF)",
    ),
    "sentinel5p_sif_ts": SourceTTLConfig(
        default=12 * 3600,       # 12 hours
        min=6 * 3600,            # 6 hours
        max=48 * 3600,           # 48 hours
        volatility="low",
        revisit_days=1.0,
        description="Sentinel-5P SIF timeseries (historical)",
    ),

    # ── Raster Composites (Spatial Tiles) ──────────────────────────
    "raster_composite_ndvi": SourceTTLConfig(
        default=6 * 3600,        # 6 hours
        min=3600,
        max=24 * 3600,
        volatility="low",
        revisit_days=5.0,
        description="NDVI raster composite for spatial visualization",
    ),
    "raster_composite_ndmi": SourceTTLConfig(
        default=6 * 3600,
        min=3600,
        max=24 * 3600,
        volatility="low",
        revisit_days=5.0,
        description="NDMI raster composite for water stress mapping",
    ),
    "raster_composite_sar": SourceTTLConfig(
        default=6 * 3600,
        min=3600,
        max=24 * 3600,
        volatility="low",
        revisit_days=6.0,
        description="SAR raster composite for soil moisture mapping",
    ),
    "raster_quality_mask": SourceTTLConfig(
        default=6 * 3600,
        min=3600,
        max=24 * 3600,
        volatility="low",
        description="Scene Classification Layer quality mask",
    ),

    # ── Weather (Fast-Moving) ──────────────────────────────────────
    "openweather_current": SourceTTLConfig(
        default=600,             # 10 minutes
        min=300,                 # 5 min
        max=3600,                # 1 hour
        volatility="high",
        description="OpenWeatherMap current conditions",
    ),
    "openweather_forecast": SourceTTLConfig(
        default=1800,            # 30 minutes
        min=900,                 # 15 min
        max=7200,                # 2 hours
        volatility="high",
        description="OpenWeatherMap 5-day forecast",
    ),
    "open_meteo_archive": SourceTTLConfig(
        default=4 * 3600,        # 4 hours
        min=3600,                # 1 hour
        max=24 * 3600,           # 24 hours
        volatility="medium",
        description="Open-Meteo historical weather archive",
    ),
    "water_balance": SourceTTLConfig(
        default=4 * 3600,        # 4 hours
        min=1800,                # 30 min
        max=12 * 3600,           # 12 hours
        volatility="medium",
        description="Calculated water balance (ET0, precipitation, deficit)",
    ),

    # ── Static / Semi-Static ───────────────────────────────────────
    "soilgrids": SourceTTLConfig(
        default=30 * 86400,      # 30 days
        min=7 * 86400,           # 7 days
        max=90 * 86400,          # 90 days
        volatility="static",
        description="ISRIC SoilGrids soil properties (pH, OC, N, clay, sand)",
    ),
    "elevation": SourceTTLConfig(
        default=365 * 86400,     # 1 year
        min=30 * 86400,          # 30 days
        max=365 * 86400,         # 1 year
        volatility="static",
        description="Open-Elevation terrain height",
    ),
    "land_cover": SourceTTLConfig(
        default=90 * 86400,      # 90 days
        min=30 * 86400,
        max=365 * 86400,
        volatility="static",
        description="ESA/Sentinel-2 Scene Classification Layer land cover",
    ),

    # ── Alerts (Fast Refresh) ──────────────────────────────────────
    "fire_risk": SourceTTLConfig(
        default=3600,            # 1 hour
        min=600,                 # 10 min
        max=6 * 3600,            # 6 hours
        volatility="high",
        description="NASA FIRMS fire/hotspot risk",
    ),
    "air_quality": SourceTTLConfig(
        default=1800,            # 30 minutes
        min=600,                 # 10 min
        max=3600,                # 1 hour
        volatility="high",
        description="Air quality index (PM2.5, PM10, O3)",
    ),
    "solar_radiation": SourceTTLConfig(
        default=6 * 3600,        # 6 hours
        min=3600,
        max=24 * 3600,
        volatility="medium",
        description="Solar radiation / PAR measurements",
    ),

    # ── Bulk Historical (for DNA Sequencing) ───────────────────────
    "bulk_historical_weather": SourceTTLConfig(
        default=24 * 3600,       # 24 hours
        min=12 * 3600,           # 12 hours
        max=7 * 86400,           # 7 days
        volatility="low",
        description="1800-day historical weather archive for DNA inversion",
    ),
    "bulk_historical_ndvi": SourceTTLConfig(
        default=24 * 3600,       # 24 hours
        min=12 * 3600,
        max=7 * 86400,
        volatility="low",
        description="1800-day historical NDVI archive for DNA inversion",
    ),

    # ── Derived / Computed ─────────────────────────────────────────
    "soil_moisture_layers": SourceTTLConfig(
        default=4 * 3600,        # 4 hours
        min=1800,
        max=12 * 3600,
        volatility="medium",
        description="Multi-layer soil moisture profile (SAR + model fusion)",
    ),
    "biomass_estimate": SourceTTLConfig(
        default=6 * 3600,        # 6 hours
        min=3600,
        max=24 * 3600,
        volatility="low",
        description="Biomass estimation from SAR + optical fusion",
    ),
    "sentinel2_rgb_tile": SourceTTLConfig(
        default=7 * 86400,       # 7 days
        min=24 * 3600,           # 1 day
        max=14 * 86400,          # 14 days
        volatility="low",
        description="Sentinel-2 RGB True Color tile (PNG base64)",
    ),
}

# Default for unknown sources
DEFAULT_TTL = SourceTTLConfig(
    default=2 * 3600,  # 2 hours
    min=600,
    max=24 * 3600,
    volatility="medium",
    description="Default fallback for unregistered sources",
)


def get_source_config(source: str) -> SourceTTLConfig:
    """Get TTL config for a source. Falls back to DEFAULT_TTL for unknown sources."""
    return TTL_REGISTRY.get(source, DEFAULT_TTL)


def get_base_ttl(source: str) -> int:
    """Get base TTL in seconds for a source."""
    return get_source_config(source).default


def get_all_sources() -> list:
    """Return list of all registered source names."""
    return sorted(TTL_REGISTRY.keys())


def get_sources_by_volatility(volatility: str) -> list:
    """Return source names matching a volatility class."""
    return [s for s, cfg in TTL_REGISTRY.items() if cfg.volatility == volatility]


def get_satellite_sources() -> list:
    """Return source names that have satellite revisit cycles."""
    return [s for s, cfg in TTL_REGISTRY.items() if cfg.revisit_days is not None]
