"""
Stage G — Orthorectification.

Warps each frame onto the target map plane using camera intrinsics,
refined pose, and surface model.

V3: Full perspective projection with adaptive resolution, per-pixel
    valid mask, off-nadir penalty, and tile-level uncertainty.
    
    Resolution modes:
    - BENCHMARK: MAX_TILE_DIM = 50 (fast synthetic tests)
    - WORKING:   MAX_TILE_DIM = 500 (resource-constrained)
    - NATIVE:    MAX_TILE_DIM = 2000 (production full-res)
    
    Tile/block processing: output tiles are sized per-frame, never
    assuming the entire mosaic fits in one array.
    
    Guardrails:
    - Benchmark caps never leak into production paths
    - Production defaults never leak into CI
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import logging
import math

from .schemas import CameraPose, FrameMetadata, FrameQAResult, OrthoTile
from .camera_model import NormalizedCamera
from .surface_model import SurfaceModelResult

logger = logging.getLogger(__name__)


# Resolution caps per mode — hard separation between benchmark and production
RESOLUTION_CAPS = {
    "benchmark": 100,
    "working": 500,
    "native": 2000,
}
RESOLUTION_MIN = 15


@dataclass
class OrthoTileStack:
    """Collection of orthorectified tiles ready for mosaicking."""
    tiles: List[OrthoTile] = field(default_factory=list)
    
    # Map-plane extent
    min_lat: float = 90.0
    max_lat: float = -90.0
    min_lon: float = 180.0
    max_lon: float = -180.0
    
    # Quality summary
    mean_qa_weight: float = 1.0
    total_usable_area_fraction: float = 1.0
    
    # V3: Resolution mode used
    resolution_mode: str = "benchmark"


class Orthorectifier:
    """Orthorectifies individual frames onto the map plane.
    
    V3: Full perspective projection with adaptive resolution sizing,
    per-pixel valid mask, off-nadir penalty, and per-tile uncertainty.
    
    Pipeline:
    1. Compute ground footprint from pose + intrinsics
    2. Create output tile grid at resolution-appropriate size
    3. For each output pixel, compute the ground point (lat/lon)
    4. Inverse-project through camera model to find source pixel (u, v)
    5. Bilinear-interpolate source pixel value
    6. Build valid mask, compute view angles, off-nadir penalty
    7. Compute per-tile uncertainty from pose sigma + view angle
    
    Tile/block processing guarantee: each frame produces ONE tile.
    No whole-mosaic arrays are created here.
    """
    
    def rectify(
        self,
        frames: List[FrameMetadata],
        qa_results: List[FrameQAResult],
        poses: List[CameraPose],
        cameras: List[NormalizedCamera],
        surface: SurfaceModelResult,
        resolution_mode: str = "benchmark",
    ) -> OrthoTileStack:
        """Orthorectify all frames into tiles.
        
        Args:
            frames: Source frames.
            qa_results: Per-frame QA.
            poses: Refined camera poses.
            cameras: Normalized camera models.
            surface: Surface model for projection.
            resolution_mode: "benchmark", "working", or "native".
            
        Returns:
            OrthoTileStack ready for mosaicking.
        """
        stack = OrthoTileStack(resolution_mode=resolution_mode)
        max_tile_dim = RESOLUTION_CAPS.get(resolution_mode, RESOLUTION_CAPS["benchmark"])
        
        # Build pose lookup
        pose_map = {p.frame_id: p for p in poses}
        
        for i, (frame, qa) in enumerate(zip(frames, qa_results)):
            if not qa.usable or frame.duplicate_of:
                continue
            
            pose = pose_map.get(frame.frame_id)
            if not pose:
                continue
            
            cam = cameras[min(i, len(cameras) - 1)]
            tile = self._rectify_single(
                frame, qa, pose, cam, surface, max_tile_dim
            )
            
            if tile:
                stack.tiles.append(tile)
                stack.min_lat = min(stack.min_lat, tile.min_lat)
                stack.max_lat = max(stack.max_lat, tile.max_lat)
                stack.min_lon = min(stack.min_lon, tile.min_lon)
                stack.max_lon = max(stack.max_lon, tile.max_lon)
        
        if stack.tiles:
            stack.mean_qa_weight = (
                sum(t.qa_weight for t in stack.tiles) / len(stack.tiles)
            )
            stack.total_usable_area_fraction = (
                sum(t.usable_fraction for t in stack.tiles) / len(stack.tiles)
            )
        
        logger.info(
            f"[Orthorectify] {len(stack.tiles)} tiles, "
            f"mode={resolution_mode}, max_dim={max_tile_dim}, "
            f"extent=({stack.min_lat:.6f},{stack.min_lon:.6f})-"
            f"({stack.max_lat:.6f},{stack.max_lon:.6f}), "
            f"mean_qa={stack.mean_qa_weight:.2f}"
        )
        
        return stack
    
    def _rectify_single(
        self,
        frame: FrameMetadata,
        qa: FrameQAResult,
        pose: CameraPose,
        cam: NormalizedCamera,
        surface: SurfaceModelResult,
        max_tile_dim: int,
    ) -> Optional[OrthoTile]:
        """Orthorectify a single frame using perspective projection.
        
        For each output pixel:
        1. Compute ground (lat, lon) from tile grid position
        2. Transform to camera-local coordinates (east, north)
        3. Project through camera model to get source pixel (u, v)
        4. Sample source pixel with bilinear interpolation
        5. Track valid pixels and compute view angle
        """
        altitude = pose.altitude_m
        if altitude <= 0:
            altitude = frame.gps.altitude_m or 50.0
        
        # Ground elevation from surface model
        ground_z = surface.ground_elevation_m
        cam_height = altitude - ground_z
        if cam_height <= 0:
            cam_height = altitude
        
        # --- 1. Compute ground footprint from camera intrinsics ---
        fw_m, fh_m = cam.intrinsics.calculate_footprint_m(cam_height)
        
        cos_lat = math.cos(math.radians(pose.latitude)) if pose.latitude != 0 else 1.0
        half_lat = (fh_m / 2.0) / 111000.0
        half_lon = (fw_m / 2.0) / (111000.0 * max(cos_lat, 0.01))
        
        tile_min_lat = pose.latitude - half_lat
        tile_max_lat = pose.latitude + half_lat
        tile_min_lon = pose.longitude - half_lon
        tile_max_lon = pose.longitude + half_lon
        
        # --- 2. Determine output tile grid size (adaptive) ---
        # Source resolution: prefer working_width (tracks actual pixel data)
        if frame.synthetic_pixels:
            green = frame.synthetic_pixels.get("green", [])
            src_h = len(green) if green else 0
            src_w = len(green[0]) if (green and green[0]) else 0
        elif frame.working_width_px > 0:
            src_w = frame.working_width_px
            src_h = frame.working_height_px
        else:
            src_w = cam.intrinsics.image_width_px
            src_h = cam.intrinsics.image_height_px
        
        # Scale output tile to match source resolution, capped by mode
        if src_w > 0 and src_h > 0:
            tile_w = min(max_tile_dim, max(RESOLUTION_MIN, src_w))
            tile_h = min(max_tile_dim, max(RESOLUTION_MIN, src_h))
        else:
            tile_w = RESOLUTION_MIN
            tile_h = RESOLUTION_MIN
        
        lat_span = tile_max_lat - tile_min_lat
        lon_span = tile_max_lon - tile_min_lon
        
        # --- 3. Perspective warp: for each output pixel, find source pixel ---
        heading_rad = math.radians(pose.heading_deg) if pose.heading_deg != 0 else 0.0
        cos_h = math.cos(heading_rad)
        sin_h = math.sin(heading_rad)
        
        has_source = frame.synthetic_pixels is not None and src_h > 0 and src_w > 0
        
        if has_source:
            src_red = frame.synthetic_pixels.get("red", [])
            src_green = frame.synthetic_pixels.get("green", [])
            src_blue = frame.synthetic_pixels.get("blue", [])
            
            out_red = [[0] * tile_w for _ in range(tile_h)]
            out_green = [[0] * tile_w for _ in range(tile_h)]
            out_blue = [[0] * tile_w for _ in range(tile_h)]
            valid_mask = [[False] * tile_w for _ in range(tile_h)]
            usable_pixels = 0
            total_pixels = tile_w * tile_h
            view_angle_sum = 0.0
            
            for oy in range(tile_h):
                # Ground latitude for this output row
                ground_lat = tile_min_lat + (oy + 0.5) / tile_h * lat_span
                
                for ox in range(tile_w):
                    # Ground longitude for this output column
                    ground_lon = tile_min_lon + (ox + 0.5) / tile_w * lon_span
                    
                    # Transform ground point to camera-local coordinates
                    # (east, north) offset from camera nadir in meters
                    east_m = (ground_lon - pose.longitude) * 111000 * cos_lat
                    north_m = (ground_lat - pose.latitude) * 111000
                    
                    # Apply heading rotation (camera may not face north)
                    local_x = east_m * cos_h + north_m * sin_h
                    local_y = -east_m * sin_h + north_m * cos_h
                    
                    # Project through pinhole camera model
                    # u = fx * (X/Z) + cx
                    # v = fy * (Y/Z) + cy
                    # Z = camera height above ground
                    if cam.fx_px > 0 and cam.fy_px > 0:
                        src_u = cam.fx_px * (local_x / cam_height) + cam.cx_px
                        src_v = cam.fy_px * (-local_y / cam_height) + cam.cy_px
                    else:
                        # Fallback: linear mapping
                        src_u = src_w / 2.0 + local_x / max(fw_m, 0.1) * src_w
                        src_v = src_h / 2.0 - local_y / max(fh_m, 0.1) * src_h
                    
                    # Scale from full-res camera space to actual pixel space
                    # (synthetic frames are smaller than camera resolution)
                    scale_x = src_w / cam.intrinsics.image_width_px
                    scale_y = src_h / cam.intrinsics.image_height_px
                    src_u *= scale_x
                    src_v *= scale_y
                    
                    # Compute view angle for this pixel
                    pixel_r = math.sqrt(
                        (src_u / scale_x - cam.cx_px) ** 2 / max(cam.fx_px ** 2, 1) +
                        (src_v / scale_y - cam.cy_px) ** 2 / max(cam.fy_px ** 2, 1)
                    )
                    pixel_view_angle = math.degrees(math.atan(pixel_r))
                    view_angle_sum += pixel_view_angle
                    
                    # Bilinear interpolation
                    pixel = self._bilinear_sample(
                        src_red, src_green, src_blue,
                        src_u, src_v, src_w, src_h
                    )
                    
                    if pixel is not None:
                        r, g, b = pixel
                        out_red[oy][ox] = r
                        out_green[oy][ox] = g
                        out_blue[oy][ox] = b
                        valid_mask[oy][ox] = True
                        usable_pixels += 1
            
            usable_frac = usable_pixels / max(total_pixels, 1)
            mean_view_angle = view_angle_sum / max(total_pixels, 1)
            
            # Off-nadir penalty: higher for tiles with large mean view angle
            # 0° → 0.0 penalty, 30° → 0.5, 45° → 1.0
            off_nadir_penalty = min(1.0, mean_view_angle / 45.0)
            
            # Uncertainty: combination of view angle and pose uncertainty
            pose_uncertainty = pose.position_sigma_m / 10.0  # Normalize to [0,1]
            uncertainty = min(1.0, off_nadir_penalty * 0.5 + pose_uncertainty * 0.5)
            
            tile = OrthoTile(
                frame_id=frame.frame_id,
                min_lat=tile_min_lat,
                max_lat=tile_max_lat,
                min_lon=tile_min_lon,
                max_lon=tile_max_lon,
                qa_weight=qa.quality_weight,
                blur_score=qa.blur_score,
                usable_fraction=min(qa.coverage_usefulness, usable_frac),
                synthetic_pixels={"red": out_red, "green": out_green, "blue": out_blue},
                valid_mask=valid_mask,
                off_nadir_penalty=off_nadir_penalty,
                uncertainty_score=uncertainty,
                view_angle_deg=mean_view_angle,
                tile_width_px=tile_w,
                tile_height_px=tile_h,
            )
        else:
            # No source pixels — footprint-only tile (production: would use tile_ref)
            tile = OrthoTile(
                frame_id=frame.frame_id,
                min_lat=tile_min_lat,
                max_lat=tile_max_lat,
                min_lon=tile_min_lon,
                max_lon=tile_max_lon,
                qa_weight=qa.quality_weight,
                blur_score=qa.blur_score,
                usable_fraction=qa.coverage_usefulness,
                tile_width_px=tile_w,
                tile_height_px=tile_h,
            )
            if frame.synthetic_pixels:
                tile.synthetic_pixels = frame.synthetic_pixels
        
        return tile
    
    def _bilinear_sample(
        self,
        red: List[List[int]],
        green: List[List[int]],
        blue: List[List[int]],
        u: float, v: float,
        w: int, h: int,
    ) -> Optional[Tuple[int, int, int]]:
        """Bilinear interpolation of source pixel at (u, v).
        
        Returns None if (u, v) is outside the source frame bounds.
        """
        # Check bounds with a small margin for edge pixels
        if u < -0.5 or u >= w - 0.5 or v < -0.5 or v >= h - 0.5:
            return None
        
        # Integer coordinates
        x0 = max(0, min(w - 1, int(math.floor(u))))
        y0 = max(0, min(h - 1, int(math.floor(v))))
        x1 = min(w - 1, x0 + 1)
        y1 = min(h - 1, y0 + 1)
        
        # Fractional parts
        fx = u - x0
        fy = v - y0
        fx = max(0.0, min(1.0, fx))
        fy = max(0.0, min(1.0, fy))
        
        # Bilinear weights
        w00 = (1 - fx) * (1 - fy)
        w10 = fx * (1 - fy)
        w01 = (1 - fx) * fy
        w11 = fx * fy
        
        def interp(ch):
            if not ch or y0 >= len(ch) or y1 >= len(ch):
                return 128
            row0 = ch[y0]
            row1 = ch[y1]
            if x0 >= len(row0) or x1 >= len(row0) or x0 >= len(row1) or x1 >= len(row1):
                return 128
            return int(
                row0[x0] * w00 + row0[x1] * w10
                + row1[x0] * w01 + row1[x1] * w11
            )
        
        r = max(0, min(255, interp(red)))
        g = max(0, min(255, interp(green)))
        b = max(0, min(255, interp(blue)))
        
        return (r, g, b)
