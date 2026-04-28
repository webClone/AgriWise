"""
Test fixtures for Geo Context Engine V1.

Provides complete DEM rasters, WorldCover rasters, Dynamic World
probability bands, and WaPOR data for testing.
"""

import numpy as np

# ---------------------------------------------------------------------------
# DEM fixtures — simulated hillslope (8x8 at 30m)
# ---------------------------------------------------------------------------

def make_dem_hillslope(rows: int = 8, cols: int = 8, res: float = 30.0):
    """An 8x8 DEM with a gentle N-S slope. Elevation increases southward."""
    elev = np.zeros((rows, cols), dtype=np.float64)
    for r in range(rows):
        elev[r, :] = 100.0 + r * 2.0  # 2m per pixel
    return {
        "elevation_m": elev,
        "valid_mask": np.ones((rows, cols), dtype=bool),
        "resolution_m": res,
        "crs": "EPSG:4326",
        "alpha_mask": np.ones((rows, cols), dtype=np.float64),
        "raster_ref": "test_hillslope",
    }


def make_dem_flat(rows: int = 8, cols: int = 8, res: float = 30.0):
    """A perfectly flat DEM."""
    return {
        "elevation_m": np.full((rows, cols), 100.0),
        "valid_mask": np.ones((rows, cols), dtype=bool),
        "resolution_m": res,
        "crs": "EPSG:4326",
        "alpha_mask": np.ones((rows, cols), dtype=np.float64),
    }


def make_dem_with_lowspot(rows: int = 8, cols: int = 8, res: float = 30.0):
    """DEM with a low spot at center."""
    elev = np.full((rows, cols), 100.0)
    elev[3:5, 3:5] = 95.0  # 5m depression at center
    return {
        "elevation_m": elev,
        "valid_mask": np.ones((rows, cols), dtype=bool),
        "resolution_m": res,
        "crs": "EPSG:4326",
        "alpha_mask": np.ones((rows, cols), dtype=np.float64),
    }


def make_dem_steep(rows: int = 8, cols: int = 8, res: float = 30.0):
    """A steep DEM (~45° slope)."""
    elev = np.zeros((rows, cols), dtype=np.float64)
    for r in range(rows):
        elev[r, :] = 100.0 + r * 30.0  # 30m per 30m pixel = 45°
    return {
        "elevation_m": elev,
        "valid_mask": np.ones((rows, cols), dtype=bool),
        "resolution_m": res,
    }


def make_dem_tiny(rows: int = 3, cols: int = 3, res: float = 90.0):
    """A very small DEM (3x3 = 9 pixels) for coarse-plot testing."""
    return {
        "elevation_m": np.array([[100, 101, 102], [99, 100, 101], [98, 99, 100]], dtype=np.float64),
        "valid_mask": np.ones((rows, cols), dtype=bool),
        "resolution_m": res,
    }


# ---------------------------------------------------------------------------
# WorldCover fixtures (ESA classes: 40=cropland, 10=tree, 50=built, 80=water)
# ---------------------------------------------------------------------------

def make_worldcover_pure_cropland(rows: int = 10, cols: int = 10, res: float = 10.0):
    """A 10x10 raster that is 100% cropland (class 40)."""
    return {
        "class_map": np.full((rows, cols), 40),
        "valid_mask": np.ones((rows, cols), dtype=bool),
        "resolution_m": res,
        "alpha_mask": np.ones((rows, cols), dtype=np.float64),
    }


def make_worldcover_tree_edge(rows: int = 10, cols: int = 10, res: float = 10.0):
    """Cropland interior with tree cover at edges."""
    data = np.full((rows, cols), 40)  # cropland
    data[0, :] = 10   # top edge = trees
    data[-1, :] = 10  # bottom edge = trees
    data[:, 0] = 10   # left edge = trees
    data[:, -1] = 10  # right edge = trees
    return {
        "class_map": data,
        "valid_mask": np.ones((rows, cols), dtype=bool),
        "resolution_m": res,
        "alpha_mask": np.ones((rows, cols), dtype=np.float64),
    }


def make_worldcover_water_contamination(rows: int = 10, cols: int = 10, res: float = 10.0):
    """Cropland with water pixels inside."""
    data = np.full((rows, cols), 40)
    data[4:6, 4:6] = 80  # water in middle
    return {
        "class_map": data,
        "valid_mask": np.ones((rows, cols), dtype=bool),
        "resolution_m": res,
        "alpha_mask": np.ones((rows, cols), dtype=np.float64),
    }


def make_worldcover_with_unknown(rows: int = 10, cols: int = 10, res: float = 10.0):
    """Cropland with some unknown class IDs (e.g. 255)."""
    data = np.full((rows, cols), 40)
    data[0:2, 0:2] = 255  # unknown class
    return {
        "class_map": data,
        "valid_mask": np.ones((rows, cols), dtype=bool),
        "resolution_m": res,
        "alpha_mask": np.ones((rows, cols), dtype=np.float64),
    }


def make_neighbor_buffer_trees(rows: int = 10, cols: int = 10, res: float = 10.0):
    """Neighbor buffer dominated by trees."""
    return {
        "class_map": np.full((rows, cols), 10),
        "valid_mask": np.ones((rows, cols), dtype=bool),
        "resolution_m": res,
    }


# ---------------------------------------------------------------------------
# Dynamic World fixtures
# ---------------------------------------------------------------------------

def make_dynamic_world_mostly_crop(rows: int = 10, cols: int = 10, res: float = 10.0):
    """Dynamic World probability bands — dominant crop."""
    base = {"valid_mask": np.ones((rows, cols), dtype=bool), "resolution_m": res}
    return {
        "bands": {
            "crops": {"data": np.full((rows, cols), 0.7), **base},
            "trees": {"data": np.full((rows, cols), 0.1), **base},
            "grass": {"data": np.full((rows, cols), 0.05), **base},
            "water": {"data": np.full((rows, cols), 0.02), **base},
            "built": {"data": np.full((rows, cols), 0.03), **base},
            "bare": {"data": np.full((rows, cols), 0.05), **base},
            "shrub_scrub": {"data": np.full((rows, cols), 0.02), **base},
            "flooded_vegetation": {"data": np.full((rows, cols), 0.02), **base},
            "snow_ice": {"data": np.full((rows, cols), 0.01), **base},
        },
        "acquisition_date": "2026-04-20",
    }


def make_dynamic_world_high_entropy(rows: int = 10, cols: int = 10, res: float = 10.0):
    """Dynamic World with near-uniform probabilities (high entropy)."""
    base = {"valid_mask": np.ones((rows, cols), dtype=bool), "resolution_m": res}
    p = 1.0 / 9.0  # uniform
    return {
        "bands": {
            cls: {"data": np.full((rows, cols), p), **base}
            for cls in ["crops", "trees", "grass", "water", "built", "bare",
                        "shrub_scrub", "flooded_vegetation", "snow_ice"]
        },
    }


def make_dynamic_world_disagrees(rows: int = 10, cols: int = 10, res: float = 10.0):
    """Dynamic World where trees dominate (disagrees with cropland WorldCover)."""
    base = {"valid_mask": np.ones((rows, cols), dtype=bool), "resolution_m": res}
    return {
        "bands": {
            "crops": {"data": np.full((rows, cols), 0.1), **base},
            "trees": {"data": np.full((rows, cols), 0.7), **base},
            "grass": {"data": np.full((rows, cols), 0.05), **base},
            "water": {"data": np.full((rows, cols), 0.02), **base},
            "built": {"data": np.full((rows, cols), 0.03), **base},
            "bare": {"data": np.full((rows, cols), 0.05), **base},
            "shrub_scrub": {"data": np.full((rows, cols), 0.02), **base},
            "flooded_vegetation": {"data": np.full((rows, cols), 0.02), **base},
            "snow_ice": {"data": np.full((rows, cols), 0.01), **base},
        },
    }


# ---------------------------------------------------------------------------
# WaPOR fixtures
# ---------------------------------------------------------------------------

def make_wapor_africa_level2():
    """WaPOR Level 2 data for African plot."""
    return {
        "available": True,
        "level": 2,
        "resolution_m": 100.0,
        "actual_et": 4.5,
        "reference_et": 5.0,
        "biomass": 0.3,
        "water_productivity": 1.2,
        "land_productivity": 0.8,
    }


def make_wapor_unavailable():
    """WaPOR unavailable for region."""
    return {
        "available": False,
        "reason": "WAPOR_OUT_OF_COVERAGE",
    }


def make_wapor_level1_coarse():
    """WaPOR Level 1 (250m), regional context only."""
    return {
        "available": True,
        "level": 1,
        "resolution_m": 250.0,
        "actual_et": 3.5,
        "reference_et": 5.0,
    }
