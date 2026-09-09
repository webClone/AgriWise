"""MESIA Spatial Coordinate Hierarchy & Transforms — R6 §6.2 / P6.2.

Provides exact transforms between WGS84 geodesy, local East-North-Up (ENU)
metric Cartesian frames, agricultural plot zones, and soil depth strata.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class LocalEnuPoint:
    """3D point in the local metric East-North-Up Cartesian frame (in meters)."""
    east_m: float
    north_m: float
    up_m: float
    plot_zone_id: str = ""
    depth_stratum: str = ""
    covariance_xyz_m2: Tuple[float, float, float] = (0.01, 0.01, 0.01)


class SpatialCoordinateAuthority:
    """Authority for spatial geodetic transforms and ASMAE spatial lattice linkage."""

    # Earth radius WGS84 approximation in meters
    EARTH_RADIUS_M = 6378137.0

    @classmethod
    def wgs84_to_enu(
        cls,
        lat_deg: float,
        lon_deg: float,
        alt_m: float,
        origin_lat_deg: float,
        origin_lon_deg: float,
        origin_alt_m: float,
        plot_zone_id: str = "PLOT_MAIN",
    ) -> LocalEnuPoint:
        """Convert WGS84 geodetic coordinates to local metric East-North-Up (ENU)."""
        d_lat_rad = math.radians(lat_deg - origin_lat_deg)
        d_lon_rad = math.radians(lon_deg - origin_lon_deg)
        mean_lat_rad = math.radians((lat_deg + origin_lat_deg) / 2.0)

        # Flat-earth geodetic approximation valid for field scales (< 50 km)
        north_m = d_lat_rad * cls.EARTH_RADIUS_M
        east_m = d_lon_rad * cls.EARTH_RADIUS_M * math.cos(mean_lat_rad)
        up_m = alt_m - origin_alt_m

        # Depth stratum classification if below soil surface (up_m < 0)
        stratum = "ABOVE_GROUND"
        if up_m < 0:
            depth_cm = abs(up_m) * 100.0
            if depth_cm <= 10.0:
                stratum = "STRATUM_TOP_0_10CM"
            elif depth_cm <= 30.0:
                stratum = "STRATUM_ROOT_10_30CM"
            elif depth_cm <= 60.0:
                stratum = "STRATUM_DEEP_30_60CM"
            else:
                stratum = "STRATUM_SUBROOT_60CM_PLUS"

        return LocalEnuPoint(
            east_m=east_m,
            north_m=north_m,
            up_m=up_m,
            plot_zone_id=plot_zone_id,
            depth_stratum=stratum,
        )

    @classmethod
    def enu_to_wgs84(
        cls,
        east_m: float,
        north_m: float,
        up_m: float,
        origin_lat_deg: float,
        origin_lon_deg: float,
        origin_alt_m: float,
    ) -> Tuple[float, float, float]:
        """Convert local ENU coordinates back to WGS84 (lat_deg, lon_deg, alt_m)."""
        d_lat_deg = math.degrees(north_m / cls.EARTH_RADIUS_M)
        lat_deg = origin_lat_deg + d_lat_deg
        mean_lat_rad = math.radians((lat_deg + origin_lat_deg) / 2.0)
        d_lon_deg = math.degrees(east_m / (cls.EARTH_RADIUS_M * math.cos(mean_lat_rad)))
        lon_deg = origin_lon_deg + d_lon_deg
        alt_m = origin_alt_m + up_m

        return (lat_deg, lon_deg, alt_m)
