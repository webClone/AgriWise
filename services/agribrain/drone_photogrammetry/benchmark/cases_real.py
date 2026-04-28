"""
Photogrammetry Benchmark — Real-World Edge Cases (V3).

Six synthetic-but-realistic scenarios targeting the specific
improvements introduced in V3 (tiepoints, seam optimization,
hole clustering, and resolution awareness).

Each scenario generates 30×40 synthetic pixel arrays that must:
  1. Pass the standard FrameQA blur gate (Laplacian variance > ~150)
  2. Have enough edge content for tiepoint extraction
  3. Simulate the specific challenge described

Pixel design rule: every frame must have at least 2 distinct
brightness regions with a boundary gradient ≥ 30 intensity units,
so the Laplacian variance is above the blur rejection threshold.
"""

from __future__ import annotations
from typing import Dict, List, Optional
import random
import math

from .cases import (
    BenchmarkCase,
    DEFAULT_POLYGON,
    DEFAULT_CAMERA,
    _make_polygon,
)
from ..schemas import DroneFrameSetInput, FrameGPS


# ============================================================================
# Case Definitions
# ============================================================================

REAL_CASES: List[BenchmarkCase] = [
    # 1. Low Texture Field (Young Wheat / Uniform Green)
    #    Challenge: very little spatial variation for tiepoints.
    #    The pipeline degrades because blur score is elevated on
    #    near-uniform pixels (low Laplacian variance).
    BenchmarkCase(
        case_id="low_texture_field",
        description=(
            "Nearly uniform green field with faint tractor tracks. "
            "Tests multi-scale tiepoint extractor on sparse features."
        ),
        slice_name="low_texture_field",
        num_frames=20,
        target_overlap_pct=80.0,
        plot_polygon=DEFAULT_POLYGON,
        strip_count=4,
        frames_per_strip=5,
        expect_usable=True,
        expect_status="usable",
        min_coverage=0.80,
    ),

    # 2. High Wind Canopy (Shifting Orchard)
    #    Challenge: canopy pattern shifts between frames due to wind.
    BenchmarkCase(
        case_id="high_wind_canopy",
        description=(
            "Orchard with wind-shifted canopy between overlapping frames. "
            "Tests forward-backward match consistency."
        ),
        slice_name="high_wind_canopy",
        num_frames=16,
        target_overlap_pct=80.0,
        plot_polygon=_make_polygon(36.0, 10.0, 100, 100),
        strip_count=4,
        frames_per_strip=4,
        expect_usable=True,
        expect_status="usable",
        min_coverage=0.80,
    ),

    # 3. Sun Glare / Specular Reflection
    #    Challenge: blown-out center pixels in ~50% of frames.
    BenchmarkCase(
        case_id="sun_glare",
        description=(
            "Mid-day sun glare: ~50% of frames have a bright hotspot "
            "at frame center. Tests exposure-robust QA weighting."
        ),
        slice_name="sun_glare",
        num_frames=20,
        plot_polygon=DEFAULT_POLYGON,
        strip_count=4,
        frames_per_strip=5,
        expect_usable=True,
        expect_status="usable",
        max_seam_score=0.40,
    ),

    # 4. Varying Altitude (Slope without Terrain Follow)
    #    Challenge: 30 m altitude spread across 4 strips.
    BenchmarkCase(
        case_id="varying_altitude",
        description=(
            "Drone flies level over sloped terrain (30 m altitude spread). "
            "Tests scale-invariant tiepoints and adaptive orthorectify."
        ),
        slice_name="varying_altitude",
        num_frames=20,
        plot_polygon=DEFAULT_POLYGON,
        strip_count=4,
        frames_per_strip=5,
        expect_usable=True,
        expect_status="usable",
    ),

    # 5. Disconnected Strip (GPS Jump / Missing Data)
    #    Challenge: entire middle strip missing → large hole.
    BenchmarkCase(
        case_id="disconnected_strip",
        description=(
            "Missing entire strip 2 (GPS dropout / no capture). "
            "Tests hole cluster classification and gap risk."
        ),
        slice_name="disconnected_strip",
        num_frames=15,
        plot_polygon=DEFAULT_POLYGON,
        strip_count=4,
        frames_per_strip=5,
        partial_strip=True,
        missing_strip_index=2,
        expect_usable=True,
        expect_status="degraded",
        max_holes=0.35,
    ),

    # 6. Aggressive Turn Blur
    #    Challenge: turn-end frames blurred + off-nadir pitch.
    BenchmarkCase(
        case_id="aggressive_turn",
        description=(
            "Strip endpoints have motion blur + 12° off-nadir pitch. "
            "Tests QA down-weighting and seam robustness at edges."
        ),
        slice_name="aggressive_turn",
        num_frames=20,
        plot_polygon=DEFAULT_POLYGON,
        strip_count=4,
        frames_per_strip=5,
        expect_usable=True,
        expect_status="usable",
    ),
]


# ============================================================================
# Frame Set Generator
# ============================================================================

def generate_real_case(case: BenchmarkCase) -> DroneFrameSetInput:
    """Generate a synthetic DroneFrameSetInput for a real-world edge case."""
    rng = random.Random(hash(case.case_id))
    center_lat = 36.0
    center_lon = 10.0
    cos_lat = math.cos(math.radians(center_lat))

    frame_gps: List[FrameGPS] = []
    synthetic_frames: List[Dict] = []

    total_strips = case.strip_count

    for strip_idx in range(total_strips):
        # Case 5: drop entire strip
        if case.case_id == "disconnected_strip" and strip_idx == case.missing_strip_index:
            continue

        cross_offset_m = (strip_idx - total_strips / 2 + 0.5) * case.strip_spacing_m
        cross_dlon = cross_offset_m / (111000 * cos_lat)

        frames_in_strip = case.frames_per_strip

        for frame_idx in range(frames_in_strip):
            along_offset_m = (
                frame_idx - frames_in_strip / 2 + 0.5
            ) * case.frame_spacing_m
            if strip_idx % 2 == 1:
                along_offset_m = -along_offset_m
            along_dlat = along_offset_m / 111000

            alt = case.flight_altitude_m
            pitch = 0.0

            # Case 4: altitude increases per strip (simulates terrain)
            if case.case_id == "varying_altitude":
                alt += strip_idx * 10.0

            # Case 6: off-nadir at strip endpoints
            if case.case_id == "aggressive_turn" and frame_idx in (0, frames_in_strip - 1):
                pitch = 12.0  # Below the 15° horizon_contamination threshold

            gps = FrameGPS(
                latitude=center_lat + along_dlat,
                longitude=center_lon + cross_dlon,
                altitude_m=alt + rng.gauss(0, 0.5),
                heading_deg=0.0 if strip_idx % 2 == 0 else 180.0,
                pitch_deg=pitch,
                horizontal_accuracy_m=2.0,
            )
            frame_gps.append(gps)

            # --- Pixel generation ---
            pixels = _make_sharp_pixels(case.case_id, rng, strip_idx, frame_idx)

            # Case 3: apply glare hotspot to ~50% of frames
            if case.case_id == "sun_glare" and rng.random() > 0.5:
                pixels = _apply_glare(pixels)

            # Case 6: blur turn endpoints
            if case.case_id == "aggressive_turn" and frame_idx in (0, frames_in_strip - 1):
                pixels = _apply_motion_blur(pixels)

            synthetic_frames.append(pixels)

    return DroneFrameSetInput(
        mission_id=f"real_bench_{case.case_id}",
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
    )


# ============================================================================
# Pixel Generators
# ============================================================================

def _make_sharp_pixels(
    case_id: str, rng: random.Random, strip_idx: int, frame_idx: int,
) -> Dict[str, List[List[int]]]:
    """Generate a 30×40 frame with high enough edge content to pass QA.

    Key design rule: the Laplacian variance of the green channel must
    exceed ~150 to keep blur_score below 0.70.  We achieve this by
    creating distinct crop/soil bands with ≥40 intensity units of
    contrast at boundaries.
    """
    h, w = 30, 40
    red = [[0] * w for _ in range(h)]
    green = [[0] * w for _ in range(h)]
    blue = [[0] * w for _ in range(h)]

    for y in range(h):
        for x in range(w):
            r, g, b = _pixel_for_case(case_id, rng, strip_idx, frame_idx, y, x)
            red[y][x] = _clamp(r)
            green[y][x] = _clamp(g)
            blue[y][x] = _clamp(b)

    return {"red": red, "green": green, "blue": blue}


def _pixel_for_case(
    case_id: str, rng: random.Random,
    strip_idx: int, frame_idx: int, y: int, x: int,
):
    """Return (r, g, b) for a single pixel based on the case scenario."""

    if case_id == "low_texture_field":
        # Nearly uniform green with tractor tracks every 10 rows / 15 cols.
        # Track contrast ~40 units so Laplacian sees them.
        is_track = (y % 10 == 0) or (x % 15 == 0)
        if is_track:
            return (
                100 + rng.randint(-8, 8),
                110 + rng.randint(-8, 8),
                70 + rng.randint(-5, 5),
            )
        else:
            return (
                55 + rng.randint(-3, 3),
                150 + rng.randint(-3, 3),
                40 + rng.randint(-2, 2),
            )

    elif case_id == "high_wind_canopy":
        # Canopy blobs shift by (frame_idx * 2) pixels to simulate wind.
        shift = (frame_idx * 2) % 6
        is_canopy = ((y + shift) % 7 < 4) and ((x + shift) % 7 < 4)
        if is_canopy:
            return (
                35 + rng.randint(-10, 10),
                110 + rng.randint(-15, 15),
                25 + rng.randint(-8, 8),
            )
        else:
            return (
                110 + rng.randint(-8, 8),
                80 + rng.randint(-8, 8),
                55 + rng.randint(-5, 5),
            )

    else:
        # Standard crop / soil rows — shared by sun_glare, varying_altitude,
        # disconnected_strip, aggressive_turn.
        is_crop = (y + strip_idx * 3) % 6 < 4
        if is_crop:
            return (
                40 + rng.randint(-10, 10),
                130 + rng.randint(-15, 15),
                35 + rng.randint(-8, 8),
            )
        else:
            return (
                135 + rng.randint(-10, 10),
                95 + rng.randint(-10, 10),
                70 + rng.randint(-8, 8),
            )


# ============================================================================
# Post-processing Effects
# ============================================================================

def _apply_glare(pixels: Dict) -> Dict:
    """Add a bright hotspot at frame center."""
    h = len(pixels["green"])
    w = len(pixels["green"][0])
    cy, cx = h // 2, w // 2
    radius = min(h, w) // 3
    for ch in ("red", "green", "blue"):
        data = pixels[ch]
        for y in range(h):
            for x in range(w):
                dist = math.sqrt((y - cy) ** 2 + (x - cx) ** 2)
                if dist < radius:
                    boost = int(80 * (1.0 - dist / radius))
                    data[y][x] = min(255, data[y][x] + boost)
    return pixels


def _apply_motion_blur(pixels: Dict) -> Dict:
    """Horizontal box blur (5-tap) simulating motion at strip endpoints."""
    for ch in ("red", "green", "blue"):
        data = pixels[ch]
        h, w = len(data), len(data[0])
        for y in range(h):
            row_copy = list(data[y])
            for x in range(2, w - 2):
                data[y][x] = (
                    row_copy[x - 2] + row_copy[x - 1] + row_copy[x]
                    + row_copy[x + 1] + row_copy[x + 2]
                ) // 5
    return pixels


def _clamp(v: int) -> int:
    return max(0, min(255, v))
