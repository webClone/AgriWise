"""
Geo Context Engine V1.

Provides topography (DEM), land cover (ESA WorldCover + Dynamic World),
and optional WaPOR water-productivity context for field plots.

Produces: static context, QA flags, sensor placement guidance,
satellite trust modifiers, plot validity checks, diagnostic packets.

Does NOT produce Kalman observations.
"""

__version__ = "1.0.0"
