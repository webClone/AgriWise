"""
Sentinel-2 Optical Observation Engine — Layer 0

Converts raw Sentinel-2 L2A scene data into structured, QA-gated,
uncertainty-aware observations for the Layer 0 assimilation engine.

V1 scope: NDVI, EVI, NDMI, NDRE, BSI + SCL QA + plot/zone summaries
         + ObservationPackets + KalmanObservations + provenance.
"""

from layer0.sentinel2.schemas import (
    Raster2D,
    SceneQualityClass,
    Sentinel2QAResult,
    Sentinel2PlotSummary,
    Sentinel2ZoneSummary,
    Sentinel2SceneMetadata,
    Sentinel2ScenePackage,
)

__all__ = [
    "Raster2D",
    "SceneQualityClass",
    "Sentinel2QAResult",
    "Sentinel2PlotSummary",
    "Sentinel2ZoneSummary",
    "Sentinel2SceneMetadata",
    "Sentinel2ScenePackage",
]
