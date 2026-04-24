"""
Photogrammetry Benchmark — Test Cases.

Seven benchmark slices covering the operational envelope:
  1. Clean mapping — high overlap, good light, rectangular field
  2. Irregular polygon — clipped edges, boundary overhang
  3. Row-sensitive field — row continuity preservation
  4. Partial strip — battery died, missing last passes
  5. Heavy blur — motion smear, reject or degrade
  6. Shadowed mission — alternating illumination
  7. Orchard mission — repeated canopy blobs

Each case generates synthetic frame sets with GPS, camera intrinsics,
and pixel data to exercise the full pipeline.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import random
import math

from ..schemas import (
    DroneFrameSetInput,
    CameraIntrinsics,
    FrameGPS,
    GroundControlPoint,
)


@dataclass
class BenchmarkCase:
    """A single benchmark scenario."""
    case_id: str
    description: str
    slice_name: str
    
    # Input parameters
    num_frames: int = 20
    flight_altitude_m: float = 50.0
    target_overlap_pct: float = 75.0
    target_gsd_cm: float = 2.0
    
    # Plot polygon (lat, lon vertices)
    plot_polygon: List[Tuple[float, float]] = field(default_factory=list)
    
    # Frame generation parameters
    strip_count: int = 4
    frames_per_strip: int = 5
    strip_spacing_m: float = 30.0     # Cross-track spacing
    frame_spacing_m: float = 20.0     # Along-track spacing
    
    # Quality modifiers
    blur_probability: float = 0.0     # Fraction of frames with blur
    shadow_probability: float = 0.0   # Fraction of frames with shadows
    missing_gps_probability: float = 0.0
    
    # Special conditions
    partial_strip: bool = False       # Simulate battery die / incomplete strip
    missing_strip_index: int = -1     # Which strip to drop
    
    # Expected outcomes
    expect_usable: bool = True
    expect_status: str = "usable"
    min_coverage: float = 0.80
    max_holes: float = 0.15
    max_seam_score: float = 0.30
    max_blur: float = 0.35

    # Ground control points
    gcps: List[GroundControlPoint] = field(default_factory=list)
    
    # DEM
    dem_ref: Optional[str] = None


# Default camera (DJI Mavic-like)
DEFAULT_CAMERA = CameraIntrinsics(
    focal_length_mm=4.5,
    sensor_width_mm=6.3,
    sensor_height_mm=4.7,
    image_width_px=4000,
    image_height_px=3000,
    principal_point_x=0.5,
    principal_point_y=0.5,
)

# Default rectangular field polygon (~100x80m)
DEFAULT_POLYGON = [
    (36.0000, 10.0000),
    (36.0000, 10.0012),
    (36.0007, 10.0012),
    (36.0007, 10.0000),
]


def _make_polygon(lat0, lon0, width_m, height_m):
    """Create a rectangular polygon from a corner + dimensions."""
    dlat = height_m / 111000
    dlon = width_m / (111000 * math.cos(math.radians(lat0)))
    return [
        (lat0, lon0),
        (lat0, lon0 + dlon),
        (lat0 + dlat, lon0 + dlon),
        (lat0 + dlat, lon0),
    ]


def _make_irregular_polygon(lat0, lon0):
    """Create an irregular polygon (L-shape)."""
    dlat = 80 / 111000
    dlon = 100 / (111000 * math.cos(math.radians(lat0)))
    return [
        (lat0, lon0),
        (lat0, lon0 + dlon),
        (lat0 + dlat * 0.6, lon0 + dlon),
        (lat0 + dlat * 0.6, lon0 + dlon * 0.5),
        (lat0 + dlat, lon0 + dlon * 0.5),
        (lat0 + dlat, lon0),
    ]


# ============================================================================
# Benchmark Cases
# ============================================================================

BENCHMARK_CASES: List[BenchmarkCase] = [
    # --- Slice 1: Clean Mapping ---
    BenchmarkCase(
        case_id="clean_mapping",
        description="Ideal conditions: rectangular field, high overlap, good light",
        slice_name="clean_mapping",
        num_frames=20,
        flight_altitude_m=50.0,
        target_overlap_pct=75.0,
        plot_polygon=DEFAULT_POLYGON,
        strip_count=4,
        frames_per_strip=5,
        strip_spacing_m=30.0,
        frame_spacing_m=20.0,
        expect_usable=True,
        expect_status="usable",
        min_coverage=0.85,
        max_holes=0.10,
    ),
    
    # --- Slice 2: Irregular Polygon ---
    BenchmarkCase(
        case_id="irregular_polygon",
        description="L-shaped field with clipped edges and boundary overhang",
        slice_name="irregular_polygon",
        num_frames=25,
        flight_altitude_m=50.0,
        plot_polygon=_make_irregular_polygon(36.0, 10.0),
        strip_count=5,
        frames_per_strip=5,
        strip_spacing_m=25.0,
        frame_spacing_m=18.0,
        expect_usable=True,
        expect_status="usable",
        min_coverage=0.70,
        max_holes=0.20,
    ),
    
    # --- Slice 3: Row-Sensitive Field ---
    BenchmarkCase(
        case_id="row_sensitive",
        description="Tight row spacing — seam optimization matters for row continuity",
        slice_name="row_sensitive",
        num_frames=24,
        flight_altitude_m=40.0,
        target_overlap_pct=80.0,
        plot_polygon=_make_polygon(36.0, 10.0, 120, 80),
        strip_count=4,
        frames_per_strip=6,
        strip_spacing_m=20.0,
        frame_spacing_m=15.0,
        expect_usable=True,
        expect_status="usable",
        min_coverage=0.85,
        max_seam_score=0.20,
    ),
    
    # --- Slice 4: Partial Strip ---
    BenchmarkCase(
        case_id="partial_strip",
        description="Battery died — last strip incomplete (only 2 of 5 frames)",
        slice_name="partial_strip",
        num_frames=17,
        flight_altitude_m=50.0,
        plot_polygon=DEFAULT_POLYGON,
        strip_count=4,
        frames_per_strip=5,
        partial_strip=True,
        missing_strip_index=3,
        expect_usable=True,
        expect_status="degraded",
        min_coverage=0.60,
        max_holes=0.30,
    ),
    
    # --- Slice 5: Heavy Blur ---
    BenchmarkCase(
        case_id="heavy_blur",
        description="Windy conditions — 60% of frames have motion blur",
        slice_name="heavy_blur",
        num_frames=20,
        flight_altitude_m=50.0,
        plot_polygon=DEFAULT_POLYGON,
        strip_count=4,
        frames_per_strip=5,
        blur_probability=0.60,
        expect_usable=True,  # Should still produce a result, but degraded
        expect_status="degraded",
        max_blur=0.50,
    ),
    
    # --- Slice 6: Shadowed Mission ---
    BenchmarkCase(
        case_id="shadowed_mission",
        description="Late afternoon — alternating illumination across strips",
        slice_name="shadowed_mission",
        num_frames=20,
        flight_altitude_m=50.0,
        plot_polygon=DEFAULT_POLYGON,
        strip_count=4,
        frames_per_strip=5,
        shadow_probability=0.40,
        expect_usable=True,
        expect_status="usable",
        min_coverage=0.80,
    ),
    
    # --- Slice 7: Orchard Mission ---
    BenchmarkCase(
        case_id="orchard_mission",
        description="Orchard with repeated canopy blobs — tests tree continuity",
        slice_name="orchard_mission",
        num_frames=16,
        flight_altitude_m=60.0,
        target_overlap_pct=80.0,
        plot_polygon=_make_polygon(36.0, 10.0, 100, 100),
        strip_count=4,
        frames_per_strip=4,
        strip_spacing_m=25.0,
        frame_spacing_m=25.0,
        expect_usable=True,
        expect_status="usable",
        min_coverage=0.80,
    ),
]


def generate_synthetic_frame_set(case: BenchmarkCase) -> DroneFrameSetInput:
    """Generate a synthetic DroneFrameSetInput for a benchmark case.
    
    Produces GPS positions in a grid pattern simulating a boustrophedon
    flight, plus synthetic pixel arrays for each frame.
    """
    rng = random.Random(hash(case.case_id))
    
    # Compute plot center
    if case.plot_polygon:
        center_lat = sum(p[0] for p in case.plot_polygon) / len(case.plot_polygon)
        center_lon = sum(p[1] for p in case.plot_polygon) / len(case.plot_polygon)
    else:
        center_lat, center_lon = 36.0, 10.0
    
    cos_lat = math.cos(math.radians(center_lat))
    
    # Generate frame positions in boustrophedon pattern
    frame_gps = []
    synthetic_frames = []
    
    total_strips = case.strip_count
    
    for strip_idx in range(total_strips):
        # Cross-track offset
        cross_offset_m = (strip_idx - total_strips / 2 + 0.5) * case.strip_spacing_m
        cross_dlat = 0.0
        cross_dlon = cross_offset_m / (111000 * cos_lat)
        
        frames_in_strip = case.frames_per_strip
        
        # Partial strip: reduce last strip
        if case.partial_strip and strip_idx == case.missing_strip_index:
            frames_in_strip = max(2, frames_in_strip // 3)
        
        for frame_idx in range(frames_in_strip):
            # Along-track offset (reverse every other strip for boustrophedon)
            along_offset_m = (
                frame_idx - frames_in_strip / 2 + 0.5
            ) * case.frame_spacing_m
            if strip_idx % 2 == 1:
                along_offset_m = -along_offset_m
            
            along_dlat = along_offset_m / 111000
            
            # GPS position
            gps = FrameGPS(
                latitude=center_lat + along_dlat + cross_dlat,
                longitude=center_lon + cross_dlon,
                altitude_m=case.flight_altitude_m + rng.gauss(0, 0.5),
                heading_deg=0.0 if strip_idx % 2 == 0 else 180.0,
                horizontal_accuracy_m=2.0,
            )
            
            # Check for missing GPS
            if rng.random() < case.missing_gps_probability:
                gps = FrameGPS()  # Default/zero GPS
            
            frame_gps.append(gps)
            
            # Generate synthetic pixels (simple vegetation pattern)
            pixels = _generate_frame_pixels(case, rng, strip_idx, frame_idx)
            
            # Apply blur
            if rng.random() < case.blur_probability:
                pixels = _apply_blur(pixels, rng)
            
            # Apply shadows
            if rng.random() < case.shadow_probability:
                pixels = _apply_shadow(pixels, rng)
            
            synthetic_frames.append(pixels)
    
    return DroneFrameSetInput(
        mission_id=f"bench_{case.case_id}",
        plot_id=f"plot_{case.case_id}",
        flight_mode="mapping_mode",
        camera=DEFAULT_CAMERA,
        frame_gps=frame_gps,
        frame_count=len(frame_gps),
        synthetic_frames=synthetic_frames,
        plot_polygon=case.plot_polygon,
        target_gsd_cm=case.target_gsd_cm,
        target_overlap_pct=case.target_overlap_pct,
        flight_altitude_m=case.flight_altitude_m,
        gcps=case.gcps,
        dem_ref=case.dem_ref,
    )


def _generate_frame_pixels(
    case: BenchmarkCase, rng: random.Random,
    strip_idx: int, frame_idx: int,
) -> Dict[str, List[List[int]]]:
    """Generate synthetic pixel arrays for a single frame.
    
    Creates a simple vegetation pattern: green crops with soil rows.
    """
    h, w = 30, 40  # Small for benchmark speed
    
    red = [[0] * w for _ in range(h)]
    green = [[0] * w for _ in range(h)]
    blue = [[0] * w for _ in range(h)]
    
    for y in range(h):
        for x in range(w):
            # Alternating crop/soil rows
            is_crop = (y + strip_idx * 3) % 6 < 4
            
            if is_crop:
                r = 40 + rng.randint(-10, 10)
                g = 120 + rng.randint(-15, 15)
                b = 35 + rng.randint(-10, 10)
            else:
                r = 130 + rng.randint(-10, 10)
                g = 100 + rng.randint(-10, 10)
                b = 70 + rng.randint(-10, 10)
            
            red[y][x] = max(0, min(255, r))
            green[y][x] = max(0, min(255, g))
            blue[y][x] = max(0, min(255, b))
    
    return {"red": red, "green": green, "blue": blue}


def _apply_blur(
    pixels: Dict[str, List[List[int]]], rng: random.Random,
) -> Dict[str, List[List[int]]]:
    """Simulate blur by reducing pixel variance."""
    for channel in ["red", "green", "blue"]:
        data = pixels[channel]
        h, w = len(data), len(data[0])
        # Simple box blur
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                avg = (
                    data[y-1][x] + data[y+1][x] +
                    data[y][x-1] + data[y][x+1] + data[y][x]
                ) // 5
                data[y][x] = avg
    return pixels


def _apply_shadow(
    pixels: Dict[str, List[List[int]]], rng: random.Random,
) -> Dict[str, List[List[int]]]:
    """Simulate shadow by darkening half the frame."""
    for channel in ["red", "green", "blue"]:
        data = pixels[channel]
        h, w = len(data), len(data[0])
        shadow_start = rng.randint(0, h // 2)
        for y in range(shadow_start, h):
            for x in range(w):
                data[y][x] = max(0, data[y][x] - 40)
    return pixels
