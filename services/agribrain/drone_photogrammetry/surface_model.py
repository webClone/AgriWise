"""
Stage F — Surface Model.

Provides the ground/surface model used during orthorectification.

V1: Flat-ground default + optional external DEM hook.
V2: Dense reconstruction → DSM/DTM/canopy height.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import logging

from .schemas import CameraPose, SurfaceModelType

logger = logging.getLogger(__name__)


@dataclass
class SurfaceModelResult:
    """Surface model for orthorectification."""
    model_type: SurfaceModelType = SurfaceModelType.FLAT_GROUND
    
    # Flat-ground parameters
    ground_elevation_m: float = 0.0   # Mean ground elevation MSL
    
    # DEM parameters (when using external DEM)
    dem_ref: str = ""
    dem_resolution_m: float = 0.0
    dem_coverage: float = 0.0         # Fraction of plot covered by DEM
    
    # Quality
    confidence: float = 1.0
    details: str = ""


class SurfaceModelBuilder:
    """Builds or selects the surface model for orthorectification.
    
    V1 modes:
      - FLAT_GROUND: assumes constant ground elevation derived from
        mean frame altitude. Suitable for flat agricultural fields.
      - EXTERNAL_DEM: accepts a DEM reference URI and propagates
        metadata. The actual DEM lookup is stubbed for V1.
    
    V2: Dense multi-view stereo → DSM/DTM/canopy height.
    """
    
    def build(
        self,
        poses: List[CameraPose],
        dem_ref: Optional[str] = None,
        dem_resolution_m: Optional[float] = None,
    ) -> SurfaceModelResult:
        """Build or select the surface model.
        
        Args:
            poses: Refined camera poses (used for flat-ground estimation).
            dem_ref: Optional URI to an external DEM raster.
            dem_resolution_m: DEM spatial resolution.
            
        Returns:
            SurfaceModelResult describing the surface.
        """
        # --- External DEM mode ---
        if dem_ref:
            return self._build_from_dem(dem_ref, dem_resolution_m)
        
        # --- Flat-ground default ---
        return self._build_flat_ground(poses)
    
    def _build_flat_ground(self, poses: List[CameraPose]) -> SurfaceModelResult:
        """Estimate flat ground elevation from camera positions.
        
        Assumption: all cameras are at roughly the same AGL altitude.
        Ground elevation = 0 (relative coordinate system).
        """
        if not poses:
            return SurfaceModelResult(
                model_type=SurfaceModelType.FLAT_GROUND,
                ground_elevation_m=0.0,
                confidence=0.5,
                details="No poses available; using z=0 flat ground",
            )
        
        # In a relative coordinate system, ground is at z=0
        # Camera altitude is the AGL flight altitude
        mean_alt = sum(p.altitude_m for p in poses) / len(poses)
        alt_spread = max(p.altitude_m for p in poses) - min(p.altitude_m for p in poses)
        
        # Confidence: high if altitude is consistent (flat terrain)
        if alt_spread < 5.0:
            confidence = 0.95  # Very flat
        elif alt_spread < 15.0:
            confidence = 0.75  # Some elevation change
        else:
            confidence = 0.50  # Hilly — flat-ground is questionable
        
        result = SurfaceModelResult(
            model_type=SurfaceModelType.FLAT_GROUND,
            ground_elevation_m=0.0,
            confidence=confidence,
            details=(
                f"Flat ground (z=0). Mean camera AGL={mean_alt:.1f}m, "
                f"altitude spread={alt_spread:.1f}m"
            ),
        )
        
        if confidence < 0.60:
            logger.warning(
                f"[SurfaceModel] Flat-ground confidence low ({confidence:.2f}). "
                f"Altitude spread={alt_spread:.1f}m. Consider using a DEM."
            )
        
        return result
    
    def _build_from_dem(
        self,
        dem_ref: str,
        dem_resolution_m: Optional[float],
    ) -> SurfaceModelResult:
        """Reference an external DEM for orthorectification.
        
        V1: Stores the DEM reference and metadata but does not
        load or query the actual DEM raster. Real DEM lookup is
        a V2 capability.
        """
        result = SurfaceModelResult(
            model_type=SurfaceModelType.EXTERNAL_DEM,
            dem_ref=dem_ref,
            dem_resolution_m=dem_resolution_m or 0.0,
            dem_coverage=1.0,  # Assumed full coverage; V2 verifies
            confidence=0.85,
            details=f"External DEM: {dem_ref} @ {dem_resolution_m}m resolution",
        )
        
        logger.info(
            f"[SurfaceModel] Using external DEM: {dem_ref}, "
            f"resolution={dem_resolution_m}m"
        )
        
        return result
    
    def get_elevation_at(
        self,
        result: SurfaceModelResult,
        latitude: float,
        longitude: float,
    ) -> float:
        """Query surface elevation at a point.
        
        V1: Always returns ground_elevation_m (flat ground) or 0.
        V2: Actual DEM/DSM lookup.
        """
        if result.model_type == SurfaceModelType.FLAT_GROUND:
            return result.ground_elevation_m
        
        # V2: DEM raster lookup
        return result.ground_elevation_m
