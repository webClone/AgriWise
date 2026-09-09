"""MESIA Cadastral Spatial Isolation & Observation Gating Package."""

from .attribution import MultiHypothesisAttributionEngine
from .classifier import SpatialGatingClassifier
from .footprints import (
    BroadcastUhfFootprint,
    CellularForwardScatterFootprint,
    GnssReflectometryFootprint,
    SarRadarFootprint,
    WifiMultipathFootprint,
)
from .geometry import (
    compute_dynamic_buffer_width,
    erode_polygon_inward,
    geodetic_to_local_enu,
    local_enu_to_geodetic,
    point_in_polygon,
    polygon_area,
)
from .integrator import SpatialSensitivityIntegrator
from .models import (
    ContainmentInterval,
    ExternalAttributionVector,
    PlotSpatialIsolationSummary,
    SpatialAuditRecord,
    SpatialClassificationTier,
    StateSpecificSensitivity,
)
from .pipeline import SpatialIsolationPipeline

__all__ = [
    "SpatialClassificationTier",
    "ContainmentInterval",
    "StateSpecificSensitivity",
    "ExternalAttributionVector",
    "SpatialAuditRecord",
    "PlotSpatialIsolationSummary",
    "geodetic_to_local_enu",
    "local_enu_to_geodetic",
    "polygon_area",
    "point_in_polygon",
    "erode_polygon_inward",
    "compute_dynamic_buffer_width",
    "GnssReflectometryFootprint",
    "CellularForwardScatterFootprint",
    "WifiMultipathFootprint",
    "BroadcastUhfFootprint",
    "SarRadarFootprint",
    "SpatialSensitivityIntegrator",
    "SpatialGatingClassifier",
    "MultiHypothesisAttributionEngine",
    "SpatialIsolationPipeline",
]
