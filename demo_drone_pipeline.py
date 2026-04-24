"""
End-to-End Drone Pipeline Demo
===============================

Extracts frames from real drone footage → photogrammetry → drone_rgb perception → report.

Pipeline:
  1. Frame Extraction:  Video → N sampled frames (OpenCV)
  2. Photogrammetry:    Frames → OrthomosaicOutput (V3 pipeline)
  3. Drone RGB:         OrthomosaicOutput → structural analysis (rows, trees, weeds)
  4. Report:            Console + saved summary
"""

import cv2
import os
import sys
import math
import time
import datetime
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.agribrain.drone_photogrammetry.engine import PhotogrammetryEngine
from services.agribrain.drone_photogrammetry.schemas import (
    DroneFrameSetInput,
    CameraIntrinsics,
    FrameGPS,
)
from services.agribrain.layer0.perception.drone_rgb.engine import DroneRGBEngine
from services.agribrain.layer0.perception.drone_rgb.schemas import DroneRGBInput
from services.agribrain.drone_mission.schemas import FlightMode, MissionType


# ============================================================================
# Configuration
# ============================================================================

VIDEO_FILES = [
    "Drone_footage_covering_202604241357.mp4",
    "Drone_footage_covering_202604241357 (1).mp4",
]

# Simulated GPS strip for the orchard
# (these are fabricated but plausible coordinates for an orchard in Israel/Mediterranean)
BASE_LAT = 31.8500
BASE_LON = 34.7200
FLIGHT_ALTITUDE_M = 80.0
FRAME_INTERVAL = 6      # Extract every Nth frame
MAX_FRAMES_PER_VIDEO = 15
OUTPUT_DIR = "_demo_output"

# Downscale frames for pipeline (V3 handles real pixels but caps for performance)
FRAME_RESIZE = (120, 90)  # (width, height) — enough for real feature detection


# ============================================================================
# Step 1: Frame Extraction
# ============================================================================

def extract_frames(video_path, video_index):
    """Extract sampled frames from a drone video, returning pixel dicts + GPS."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  ERROR: Cannot open {video_path}")
        return [], []

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"  Source: {w}x{h} @ {fps:.0f}fps, {total} frames ({total/fps:.1f}s)")

    frames_pixels = []
    frames_gps = []
    frame_idx = 0
    extracted = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % FRAME_INTERVAL == 0 and extracted < MAX_FRAMES_PER_VIDEO:
            # Resize for pipeline
            small = cv2.resize(frame, FRAME_RESIZE, interpolation=cv2.INTER_AREA)

            # Split into RGB channels (OpenCV is BGR)
            b, g, r = cv2.split(small)
            pixel_dict = {
                "red": r.tolist(),
                "green": g.tolist(),
                "blue": b.tolist(),
            }
            frames_pixels.append(pixel_dict)

            # Simulate GPS positions along a strip
            # Each frame is offset slightly along the flight direction
            strip_progress = extracted / max(MAX_FRAMES_PER_VIDEO - 1, 1)
            # Video 1: east-west strip, Video 2: offset north
            if video_index == 0:
                lat = BASE_LAT + strip_progress * 0.002
                lon = BASE_LON + strip_progress * 0.001
            else:
                lat = BASE_LAT + 0.001 + strip_progress * 0.002
                lon = BASE_LON + strip_progress * 0.001

            gps = FrameGPS(
                latitude=lat,
                longitude=lon,
                altitude_m=FLIGHT_ALTITUDE_M,
                heading_deg=90.0 if video_index == 0 else 85.0,
                horizontal_accuracy_m=1.5,
            )
            frames_gps.append(gps)
            extracted += 1

            # Save frame for report
            out_path = os.path.join(OUTPUT_DIR, "frames", f"v{video_index+1}_f{extracted:02d}.jpg")
            cv2.imwrite(out_path, small, [cv2.IMWRITE_JPEG_QUALITY, 90])

        frame_idx += 1

    cap.release()
    print(f"  Extracted: {extracted} frames at {FRAME_RESIZE[0]}x{FRAME_RESIZE[1]}")
    return frames_pixels, frames_gps


# ============================================================================
# Step 2: Photogrammetry
# ============================================================================

def run_photogrammetry(all_pixels, all_gps):
    """Run the V3 photogrammetry pipeline on extracted frames."""
    print(f"\n{'='*60}")
    print(f"  STAGE 2: PHOTOGRAMMETRY (V3)")
    print(f"{'='*60}")
    print(f"  Input: {len(all_pixels)} frames")

    # Build camera model (simulated DJI-like parameters)
    camera = CameraIntrinsics(
        focal_length_mm=4.5,
        sensor_width_mm=6.3,
        sensor_height_mm=4.7,
        image_width_px=1280,     # Original video resolution
        image_height_px=720,
        principal_point_x=0.5,
        principal_point_y=0.5,
    )

    # Build frame refs
    frame_refs = [f"drone://video/frame_{i:03d}.jpg" for i in range(len(all_pixels))]

    inp = DroneFrameSetInput(
        mission_id="demo_orchard_2026",
        plot_id="orchard_alpha",
        flight_mode="mapping_mode",
        frame_refs=frame_refs,
        frame_count=len(all_pixels),
        camera=camera,
        frame_gps=all_gps,
        plot_polygon=[
            (BASE_LAT - 0.001, BASE_LON - 0.001),
            (BASE_LAT + 0.004, BASE_LON - 0.001),
            (BASE_LAT + 0.004, BASE_LON + 0.003),
            (BASE_LAT - 0.001, BASE_LON + 0.003),
        ],
        target_gsd_cm=2.0,
        target_overlap_pct=75.0,
        flight_altitude_m=FLIGHT_ALTITUDE_M,
        synthetic_frames=all_pixels,
    )

    engine = PhotogrammetryEngine()
    start = time.time()
    output = engine.process(inp)
    elapsed = time.time() - start

    print(f"\n  --- Photogrammetry Results ---")
    print(f"  Status:       {output.status.value}")
    print(f"  Usable:       {output.usable}")
    print(f"  QA Score:     {output.qa_score:.2f}")
    print(f"  Coverage:     {output.coverage_completeness:.0%}")
    print(f"  GSD:          {output.ground_resolution_cm:.1f} cm/px")
    print(f"  Overlap:      {output.achieved_overlap:.0%}")
    print(f"  Holes:        {output.holes_fraction:.0%}")
    print(f"  Seam Score:   {output.seam_artifact_score:.2f}")
    print(f"  Sigma:        {output.sigma_inflation:.1f}")
    print(f"  Pipeline:     {output.provenance.pipeline_version}")
    print(f"  Alignment:    {output.provenance.alignment_method}")
    print(f"  Reproj Err:   {output.provenance.mean_reprojection_error_px:.2f} px")
    print(f"  Frames Used:  {output.provenance.frames_used_in_mosaic}/{output.provenance.total_frames_ingested}")
    print(f"  Processing:   {elapsed:.1f}s")

    return output


# ============================================================================
# Step 3: Drone RGB Perception
# ============================================================================

def run_drone_rgb(ortho_output):
    """Run drone_rgb perception on the orthomosaic."""
    print(f"\n{'='*60}")
    print(f"  STAGE 3: DRONE RGB PERCEPTION")
    print(f"{'='*60}")

    inp = DroneRGBInput(
        plot_id=ortho_output.plot_id,
        mission_id=ortho_output.mission_id,
        flight_mode=FlightMode.MAPPING_MODE,
        mission_type=MissionType.FULL_PLOT_MAP,
        orthomosaic_output=ortho_output,
    )

    engine = DroneRGBEngine()
    rgb_output, packets = engine.process_full(inp)

    if rgb_output is None:
        print("  ERROR: DroneRGBEngine returned None")
        return None, []

    print(f"\n  --- Drone RGB Results ---")
    print(f"  Valid:           {rgb_output.is_valid}")
    print(f"  QA Score:        {rgb_output.qa_score:.2f}")

    if rgb_output.rejection_reason:
        print(f"  Rejected:        {rgb_output.rejection_reason}")
        return rgb_output, packets

    print(f"  Row Azimuth:     {rgb_output.row_azimuth_deg:.1f}°" if rgb_output.row_azimuth_deg else "  Row Azimuth:     N/A")
    print(f"  Row Spacing:     {rgb_output.row_spacing_cm:.0f} cm" if rgb_output.row_spacing_cm else "  Row Spacing:     N/A")
    print(f"  Row Count:       {rgb_output.row_count}")
    print(f"  Canopy Cover:    {rgb_output.canopy_cover_fraction:.1%}" if rgb_output.canopy_cover_fraction else "  Canopy Cover:    N/A")
    print(f"  Bare Soil:       {rgb_output.bare_soil_fraction:.1%}" if rgb_output.bare_soil_fraction else "  Bare Soil:       N/A")
    print(f"  Weed Pressure:   {rgb_output.weed_pressure_index:.3f}" if rgb_output.weed_pressure_index is not None else "  Weed Pressure:   N/A")
    print(f"  Tree Count:      {rgb_output.tree_count}")
    print(f"  Missing Trees:   {rgb_output.missing_tree_count}")
    print(f"  Canopy CV:       {rgb_output.canopy_uniformity_cv:.3f}")
    print(f"  Spatial Maps:    {len(rgb_output.spatial_maps)}")
    print(f"  Obs Packets:     {len(packets)}")

    if rgb_output.row_breaks:
        print(f"  Row Breaks:      {len(rgb_output.row_breaks)}")

    if rgb_output.orthomosaic_provenance:
        prov = rgb_output.orthomosaic_provenance
        print(f"  Provenance:      pipeline={prov.get('pipeline_version')}, "
              f"alignment={prov.get('alignment_method')}")

    return rgb_output, packets


# ============================================================================
# Step 4: Report Generation
# ============================================================================

def generate_report(ortho_output, rgb_output, packets, all_pixels, elapsed_total):
    """Generate a summary report."""
    print(f"\n{'='*60}")
    print(f"  STAGE 4: REPORT")
    print(f"{'='*60}")

    report = {
        "demo": "AgriWise Drone Pipeline — End-to-End Demo",
        "timestamp": datetime.datetime.now().isoformat(),
        "input": {
            "videos": VIDEO_FILES,
            "total_frames_extracted": len(all_pixels),
            "frame_resolution": f"{FRAME_RESIZE[0]}x{FRAME_RESIZE[1]}",
            "flight_altitude_m": FLIGHT_ALTITUDE_M,
        },
        "photogrammetry": {
            "status": ortho_output.status.value,
            "usable": ortho_output.usable,
            "qa_score": round(ortho_output.qa_score, 3),
            "coverage": round(ortho_output.coverage_completeness, 3),
            "gsd_cm": round(ortho_output.ground_resolution_cm, 2),
            "overlap": round(ortho_output.achieved_overlap, 3),
            "holes": round(ortho_output.holes_fraction, 3),
            "seam_score": round(ortho_output.seam_artifact_score, 3),
            "sigma_inflation": round(ortho_output.sigma_inflation, 2),
            "pipeline_version": ortho_output.provenance.pipeline_version,
            "alignment_method": ortho_output.provenance.alignment_method,
            "reproj_error_px": round(ortho_output.provenance.mean_reprojection_error_px, 3),
            "frames_ingested": ortho_output.provenance.total_frames_ingested,
            "frames_used": ortho_output.provenance.frames_used_in_mosaic,
        },
        "perception": {},
        "total_elapsed_s": round(elapsed_total, 1),
    }

    if rgb_output and rgb_output.is_valid:
        report["perception"] = {
            "qa_score": round(rgb_output.qa_score, 3),
            "row_azimuth_deg": round(rgb_output.row_azimuth_deg, 1) if rgb_output.row_azimuth_deg else None,
            "row_spacing_cm": round(rgb_output.row_spacing_cm, 0) if rgb_output.row_spacing_cm else None,
            "row_count": rgb_output.row_count,
            "canopy_cover": round(rgb_output.canopy_cover_fraction, 3) if rgb_output.canopy_cover_fraction else None,
            "bare_soil": round(rgb_output.bare_soil_fraction, 3) if rgb_output.bare_soil_fraction else None,
            "weed_pressure": round(rgb_output.weed_pressure_index, 4) if rgb_output.weed_pressure_index is not None else None,
            "tree_count": rgb_output.tree_count,
            "missing_trees": rgb_output.missing_tree_count,
            "canopy_uniformity_cv": round(rgb_output.canopy_uniformity_cv, 4),
            "row_breaks": len(rgb_output.row_breaks),
            "spatial_maps": len(rgb_output.spatial_maps),
            "observation_packets": len(packets),
        }

    # Save report
    report_path = os.path.join(OUTPUT_DIR, "demo_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Report saved: {report_path}")

    # Save ortho mosaic pixels as an image if available
    if ortho_output._benchmark_pixels:
        pixels = ortho_output._benchmark_pixels
        green = pixels.get("green", [])
        if green:
            import numpy as np
            h = len(green)
            w = len(green[0]) if green else 0
            red = pixels.get("red", green)
            blue = pixels.get("blue", green)
            img = np.zeros((h, w, 3), dtype=np.uint8)
            for y in range(h):
                for x in range(w):
                    img[y, x, 2] = min(255, max(0, red[y][x]))   # R
                    img[y, x, 1] = min(255, max(0, green[y][x]))  # G
                    img[y, x, 0] = min(255, max(0, blue[y][x]))   # B
            mosaic_path = os.path.join(OUTPUT_DIR, "orthomosaic_preview.jpg")
            # Upscale for visibility
            scale = max(1, 800 // max(w, 1))
            img_up = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)
            cv2.imwrite(mosaic_path, img_up, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"  Mosaic saved:  {mosaic_path} ({w}x{h} → {w*scale}x{h*scale})")

    return report


# ============================================================================
# Main
# ============================================================================

def main():
    print()
    print("=" * 60)
    print("  AGRIWISE — END-TO-END DRONE PIPELINE DEMO")
    print("=" * 60)
    print()

    total_start = time.time()

    # Setup output dir
    os.makedirs(os.path.join(OUTPUT_DIR, "frames"), exist_ok=True)

    # ---- Step 1: Extract frames ----
    print(f"{'='*60}")
    print(f"  STAGE 1: FRAME EXTRACTION")
    print(f"{'='*60}")

    all_pixels = []
    all_gps = []

    for i, vf in enumerate(VIDEO_FILES):
        print(f"\n  Video {i+1}: {vf}")
        if not os.path.exists(vf):
            print(f"  SKIP: File not found")
            continue
        pixels, gps = extract_frames(vf, i)
        all_pixels.extend(pixels)
        all_gps.extend(gps)

    if not all_pixels:
        print("\n  ERROR: No frames extracted. Aborting.")
        return

    print(f"\n  Total frames: {len(all_pixels)}")

    # ---- Step 2: Photogrammetry ----
    ortho_output = run_photogrammetry(all_pixels, all_gps)

    # ---- Step 3: Drone RGB Perception ----
    rgb_output, packets = run_drone_rgb(ortho_output)

    # ---- Step 4: Report ----
    total_elapsed = time.time() - total_start
    report = generate_report(ortho_output, rgb_output, packets, all_pixels, total_elapsed)

    # ---- Summary ----
    print(f"\n{'='*60}")
    print(f"  DEMO COMPLETE")
    print(f"{'='*60}")
    print(f"  Videos processed:      {len(VIDEO_FILES)}")
    print(f"  Frames extracted:      {len(all_pixels)}")
    print(f"  Photogrammetry:        {ortho_output.status.value} (QA={ortho_output.qa_score:.2f})")
    if rgb_output and rgb_output.is_valid:
        print(f"  Perception:            valid (QA={rgb_output.qa_score:.2f})")
        print(f"  Trees detected:        {rgb_output.tree_count}")
        print(f"  Row azimuth:           {rgb_output.row_azimuth_deg:.1f}°" if rgb_output.row_azimuth_deg else "")
        print(f"  Weed pressure:         {rgb_output.weed_pressure_index:.3f}" if rgb_output.weed_pressure_index is not None else "")
    else:
        reason = getattr(rgb_output, 'rejection_reason', 'unknown') if rgb_output else 'no output'
        print(f"  Perception:            rejected ({reason})")
    print(f"  Observation packets:   {len(packets)}")
    print(f"  Total time:            {total_elapsed:.1f}s")
    print(f"  Output:                {OUTPUT_DIR}/")
    print()


if __name__ == "__main__":
    main()
