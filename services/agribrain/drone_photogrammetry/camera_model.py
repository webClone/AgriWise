"""
Stage C — Camera Normalization.

Normalizes camera intrinsics from EXIF, drone profiles, or user input
into a standard pinhole model for downstream reconstruction.

V1: Simple pinhole model with no distortion correction.
V2: Brown-Conrady distortion, rolling-shutter compensation.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
import logging
import math

from .schemas import CameraIntrinsics, FrameMetadata

logger = logging.getLogger(__name__)


@dataclass
class NormalizedCamera:
    """A camera model normalized to a common coordinate system.
    
    All downstream stages (tiepoints, alignment, orthorectify) consume
    this instead of raw EXIF data.
    """
    intrinsics: CameraIntrinsics
    # Precomputed convenience values
    fx_px: float = 0.0    # Focal length in pixels (horizontal)
    fy_px: float = 0.0    # Focal length in pixels (vertical)
    cx_px: float = 0.0    # Principal point X in pixels
    cy_px: float = 0.0    # Principal point Y in pixels
    # V2: undistortion LUT
    has_distortion_model: bool = False


class CameraModelNormalizer:
    """Normalizes camera intrinsics for the reconstruction pipeline.
    
    Responsibilities:
      - Convert EXIF focal length + sensor size → pixel focal length
      - Compute principal point in pixels
      - Flag rolling-shutter cameras
      - Validate sensor geometry
    
    V1 uses pinhole model. V2 adds lens distortion correction.
    """
    
    def normalize(self, intrinsics: CameraIntrinsics) -> NormalizedCamera:
        """Normalize raw camera intrinsics to a standard model.
        
        Args:
            intrinsics: Raw camera parameters from EXIF or drone profile.
            
        Returns:
            NormalizedCamera with precomputed pixel-space values.
        """
        cam = NormalizedCamera(intrinsics=intrinsics)
        
        # --- Focal length in pixels ---
        # fx = focal_length_mm * image_width_px / sensor_width_mm
        if intrinsics.sensor_width_mm > 0 and intrinsics.focal_length_mm > 0:
            cam.fx_px = (
                intrinsics.focal_length_mm * intrinsics.image_width_px
                / intrinsics.sensor_width_mm
            )
        
        if intrinsics.sensor_height_mm > 0 and intrinsics.focal_length_mm > 0:
            cam.fy_px = (
                intrinsics.focal_length_mm * intrinsics.image_height_px
                / intrinsics.sensor_height_mm
            )
        else:
            # Assume square pixels if sensor height not available
            cam.fy_px = cam.fx_px * (
                intrinsics.image_height_px / max(intrinsics.image_width_px, 1)
            )
        
        # --- Principal point in pixels ---
        cam.cx_px = intrinsics.principal_point_x * intrinsics.image_width_px
        cam.cy_px = intrinsics.principal_point_y * intrinsics.image_height_px
        
        # --- Distortion model ---
        if intrinsics.distortion_coeffs:
            cam.has_distortion_model = True
            # V2: precompute undistortion LUT here
        
        logger.debug(
            f"[CameraModel] Normalized: "
            f"fx={cam.fx_px:.1f}px, fy={cam.fy_px:.1f}px, "
            f"cx={cam.cx_px:.1f}, cy={cam.cy_px:.1f}, "
            f"distortion={cam.has_distortion_model}, "
            f"rolling_shutter={intrinsics.rolling_shutter}"
        )
        
        return cam
    
    def normalize_batch(
        self, frames: List[FrameMetadata]
    ) -> List[NormalizedCamera]:
        """Normalize cameras for all frames.
        
        In most drone missions, all frames share the same camera model.
        We still normalize per-frame to support multi-camera rigs later.
        """
        # Optimize: if all frames share the same camera, normalize once
        if frames:
            shared = self.normalize(frames[0].camera)
            # Check if all cameras are identical
            all_same = all(
                f.camera.focal_length_mm == frames[0].camera.focal_length_mm
                and f.camera.sensor_width_mm == frames[0].camera.sensor_width_mm
                and f.camera.image_width_px == frames[0].camera.image_width_px
                for f in frames
            )
            if all_same:
                return [shared] * len(frames)
        
        return [self.normalize(f.camera) for f in frames]
    
    def project_to_ground(
        self,
        cam: NormalizedCamera,
        altitude_m: float,
        pixel_x: float,
        pixel_y: float,
    ) -> Tuple[float, float]:
        """Project a pixel coordinate to ground-plane offset (meters).
        
        Uses pinhole model with flat-ground assumption.
        Returns (east_offset_m, north_offset_m) from camera nadir.
        
        V1: no distortion correction.
        """
        if cam.fx_px <= 0 or cam.fy_px <= 0:
            return (0.0, 0.0)
        
        # Normalized image coordinates
        nx = (pixel_x - cam.cx_px) / cam.fx_px
        ny = (pixel_y - cam.cy_px) / cam.fy_px
        
        # Ground offset at given altitude
        east_m = nx * altitude_m
        north_m = -ny * altitude_m  # Image Y is down, north is up
        
        return (east_m, north_m)
    
    def compute_ground_footprint(
        self,
        cam: NormalizedCamera,
        altitude_m: float,
    ) -> Tuple[float, float]:
        """Compute ground footprint (width_m, height_m) of one frame."""
        return cam.intrinsics.calculate_footprint_m(altitude_m)
    
    def compute_pixel_view_angle(
        self,
        cam: NormalizedCamera,
        pixel_x: float,
        pixel_y: float,
    ) -> float:
        """Compute off-nadir view angle (degrees) for a pixel position.
        
        The nadir point (principal point) has angle 0°. Pixels at the
        edge of the frame have the maximum angle. Used by orthorectify
        to compute off-nadir penalty and uncertainty per tile pixel.
        
        Args:
            cam: Normalized camera model.
            pixel_x: Pixel x coordinate.
            pixel_y: Pixel y coordinate.
            
        Returns:
            Off-nadir angle in degrees (0 = nadir, increases toward edges).
        """
        if cam.fx_px <= 0 or cam.fy_px <= 0:
            return 0.0
        
        # Normalized image coordinates
        nx = (pixel_x - cam.cx_px) / cam.fx_px
        ny = (pixel_y - cam.cy_px) / cam.fy_px
        
        # View angle = atan(sqrt(nx² + ny²))
        r = math.sqrt(nx * nx + ny * ny)
        angle_rad = math.atan(r)
        
        return math.degrees(angle_rad)
    
    def compute_max_view_angle(self, cam: NormalizedCamera) -> float:
        """Compute maximum off-nadir angle (at frame corners)."""
        if cam.fx_px <= 0 or cam.fy_px <= 0:
            return 0.0
        
        # Corner pixel
        corner_x = cam.intrinsics.image_width_px
        corner_y = cam.intrinsics.image_height_px
        return self.compute_pixel_view_angle(cam, corner_x, corner_y)
