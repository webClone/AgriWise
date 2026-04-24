"""
Spatial Intelligence Schema — Canonical Type System
====================================================
Research-grade spatial types for management zone analysis.
This module defines the contract for all spatial operations in AgriBrain.

All types are frozen dataclasses for determinism and immutability.
Pure Python only — no numpy dependency.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class GridCrs(Enum):
    """Coordinate Reference System for the analysis grid."""
    WGS84 = "EPSG:4326"
    WEB_MERCATOR = "EPSG:3857"
    UTM = "UTM_AUTO"


class FeatureId(Enum):
    """Identifiers for raster feature layers used in zonal analysis."""
    NDVI = "NDVI"
    NDWI = "NDWI"
    VV = "SAR_VV"
    VH = "SAR_VH"
    DEM = "DEM"
    SLOPE = "SLOPE"
    TWI = "TWI"                 # Topographic Wetness Index
    SOIL_CLAY = "SOIL_CLAY"
    SOIL_SAND = "SOIL_SAND"
    SOIL_SILT = "SOIL_SILT"
    SOIL_OC = "SOIL_OC"        # Soil Organic Carbon
    SOIL_PH = "SOIL_PH"
    PRECIPITATION = "PRECIPITATION"
    NDVI_UNC = "NDVI_UNC"      # NDVI uncertainty


class ZoneMethod(Enum):
    """Segmentation method used to partition the field."""
    KMEANS = "KMEANS"
    GMM = "GMM"
    QUANTILE = "QUANTILE"
    SLIC = "SLIC_SUPERPIXELS"
    RULED = "RULED_THRESHOLD"
    HYBRID = "HYBRID"


class ZoneLabel(Enum):
    """Semantic labels for management zones."""
    HIGH_VIGOR = "HIGH_VIGOR"
    MED_VIGOR = "MED_VIGOR"
    LOW_VIGOR = "LOW_VIGOR"
    WET_ZONE = "WET_ZONE"
    DRY_ZONE = "DRY_ZONE"
    COMPACTED = "COMPACTED"
    SLOPE_RISK = "SLOPE_RISK"
    URBAN_EDGE = "URBAN_EDGE"
    HOMOGENEOUS = "HOMOGENEOUS"
    UNKNOWN = "UNKNOWN"


# ============================================================================
# SPATIAL GRID
# ============================================================================

@dataclass(frozen=True)
class SpatialGridSpec:
    """
    Defines the canonical analysis grid for a plot polygon.
    All raster layers are resampled to this grid before analysis.
    """
    crs: str                                    # e.g. "EPSG:4326"
    cell_size_m: float                          # e.g. 10.0, 20.0
    width: int                                  # grid columns
    height: int                                 # grid rows
    origin_lat: float                           # top-left latitude
    origin_lng: float                           # top-left longitude
    bbox: Tuple[float, float, float, float]     # (min_lng, min_lat, max_lng, max_lat)
    mask_ratio: float                           # fraction of cells inside polygon (0..1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "crs": self.crs,
            "cell_size_m": self.cell_size_m,
            "width": self.width,
            "height": self.height,
            "origin_lat": self.origin_lat,
            "origin_lng": self.origin_lng,
            "bbox": list(self.bbox),
            "mask_ratio": self.mask_ratio,
        }


# ============================================================================
# FEATURE LAYERS
# ============================================================================

@dataclass(frozen=True)
class FeatureLayer:
    """
    A single raster feature layer aligned to the SpatialGridSpec.
    Values is a 2D list [H][W]; valid_mask is a 2D bool list [H][W].
    """
    feature: FeatureId
    values: List[List[float]]                   # [H][W]
    valid_mask: List[List[bool]]                # [H][W] — True if pixel is valid
    resolution_m: float                         # native resolution of this source
    source: str = ""                            # e.g. "Sentinel-2", "SoilGrids"
    timestamp: Optional[str] = None             # ISO date if temporal
    uncertainty_sigma: Optional[List[List[float]]] = None  # [H][W] per-pixel sigma
    quality_flags: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature.value,
            "resolution_m": self.resolution_m,
            "source": self.source,
            "timestamp": self.timestamp,
            "has_uncertainty": self.uncertainty_sigma is not None,
            "quality_flags": list(self.quality_flags),
        }


# ============================================================================
# ZONE MAP & ZONE STATS
# ============================================================================

@dataclass(frozen=True)
class ZoneMap:
    """
    The spatial segmentation result — assigns every grid cell to a zone.
    zone_id_grid[y][x] = integer zone_id (0..n_zones-1), or -1 if outside polygon.
    """
    zone_id_grid: List[List[int]]               # [H][W]
    n_zones: int
    method: ZoneMethod
    features_used: Tuple[FeatureId, ...]
    params: Dict[str, Any]                       # e.g. {"k": 3, "seed": 42}
    stability_score: float                       # 0..1, how stable is segmentation
    boundary_complexity: float                   # perimeter/area proxy

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_zones": self.n_zones,
            "method": self.method.value,
            "features_used": [f.value for f in self.features_used],
            "params": self.params,
            "stability_score": round(self.stability_score, 3),
            "boundary_complexity": round(self.boundary_complexity, 3),
        }


@dataclass(frozen=True)
class ZoneStats:
    """
    Aggregated statistics for a single management zone.
    This is the primary input to downstream engines (L2–L7).
    """
    zone_id: int
    zone_label: ZoneLabel
    spatial_label: str                           # "north-west", "south-east", etc.
    area_m2: float
    area_pct: float                              # % of total plot
    centroid_lat: float
    centroid_lng: float

    # Per-feature aggregated statistics
    feature_means: Dict[str, float]              # FeatureId.value -> mean
    feature_p10: Dict[str, float]                # FeatureId.value -> 10th percentile
    feature_p90: Dict[str, float]                # FeatureId.value -> 90th percentile
    feature_std: Dict[str, float]                # FeatureId.value -> std dev

    # Data quality per feature
    valid_fraction: Dict[str, float]             # FeatureId.value -> 0..1
    uncertainty_mean: Dict[str, float]           # FeatureId.value -> mean sigma
    uncertainty_p90: Dict[str, float]            # FeatureId.value -> 90th pctl sigma

    # Derived
    notes: Tuple[str, ...] = ()                  # e.g. "Near urban edge", "Lowest NDVI"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_label": self.zone_label.value,
            "spatial_label": self.spatial_label,
            "area_pct": round(self.area_pct, 1),
            "centroid": [round(self.centroid_lat, 6), round(self.centroid_lng, 6)],
            "feature_means": {k: round(v, 4) for k, v in self.feature_means.items()},
            "feature_p10": {k: round(v, 4) for k, v in self.feature_p10.items()},
            "feature_p90": {k: round(v, 4) for k, v in self.feature_p90.items()},
            "valid_fraction": {k: round(v, 3) for k, v in self.valid_fraction.items()},
            "uncertainty_mean": {k: round(v, 4) for k, v in self.uncertainty_mean.items()},
            "notes": list(self.notes),
        }


# ============================================================================
# SPATIAL TENSOR (top-level container)
# ============================================================================

@dataclass
class SpatialTensor:
    """
    The unified spatial intelligence artifact for a plot.
    Contains the analysis grid, all feature layers, zone segmentation, and zone stats.
    This is the input to zone-aware L2–L7 engines.
    """
    plot_id: str
    grid: SpatialGridSpec
    layers: Dict[str, FeatureLayer]              # FeatureId.value -> FeatureLayer
    zone_map: Optional[ZoneMap] = None
    zone_stats: Optional[List[ZoneStats]] = None

    # Provenance
    run_id: str = ""
    code_version: str = "spatial_v1.0"
    polygon_hash: str = ""                       # hash of input polygon for cache key

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plot_id": self.plot_id,
            "run_id": self.run_id,
            "code_version": self.code_version,
            "grid": self.grid.to_dict(),
            "layers": {k: v.to_dict() for k, v in self.layers.items()},
            "zone_map": self.zone_map.to_dict() if self.zone_map else None,
            "zone_stats": [z.to_dict() for z in self.zone_stats] if self.zone_stats else [],
            "n_zones": self.zone_map.n_zones if self.zone_map else 0,
        }

    @property
    def has_zones(self) -> bool:
        return self.zone_map is not None and self.zone_map.n_zones > 1

    @property
    def weakest_zone(self) -> Optional['ZoneStats']:
        """Returns the zone with lowest NDVI mean (proxy for weakest)."""
        if not self.zone_stats:
            return None
        candidates = [z for z in self.zone_stats if FeatureId.NDVI.value in z.feature_means]
        if not candidates:
            return self.zone_stats[-1] if self.zone_stats else None
        return min(candidates, key=lambda z: z.feature_means.get(FeatureId.NDVI.value, 0))

    @property
    def strongest_zone(self) -> Optional['ZoneStats']:
        """Returns the zone with highest NDVI mean (proxy for strongest)."""
        if not self.zone_stats:
            return None
        candidates = [z for z in self.zone_stats if FeatureId.NDVI.value in z.feature_means]
        if not candidates:
            return self.zone_stats[0] if self.zone_stats else None
        return max(candidates, key=lambda z: z.feature_means.get(FeatureId.NDVI.value, 0))
