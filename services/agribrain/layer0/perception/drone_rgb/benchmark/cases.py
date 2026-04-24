"""
Drone Benchmark Cases.

Synthetic test cases evaluating both structural perception (Track B)
and mission execution quality.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import math
import hashlib
import random

from services.agribrain.drone_mission.schemas import MissionType, FlightMode

@dataclass
class DroneBenchmarkCase:
    case_id: str
    description: str
    
    # Mission Config
    mission_type: MissionType
    flight_mode: FlightMode
    polygon_geojson: Dict[str, Any]
    target_gsd_cm: float = 2.0
    
    # Ground Truth: Execution Quality
    gt_coverage_completeness: float = 1.0
    gt_outside_polygon_waste: float = 0.0
    gt_achieved_overlap: float = 75.0
    
    # Ground Truth: Perception Quality (Track B)
    gt_row_azimuth_deg: Optional[float] = None
    gt_row_spacing_cm: Optional[float] = None
    gt_canopy_cover: Optional[float] = None
    gt_weed_pressure: Optional[float] = None
    gt_gap_fraction: Optional[float] = None
    gt_false_positive_rows: bool = False
    
    # V1.5 Ground Truth
    gt_row_break_count: Optional[int] = None
    gt_in_row_weed_fraction: Optional[float] = None
    gt_inter_row_weed_fraction: Optional[float] = None
    gt_tree_count: Optional[int] = None
    gt_missing_tree_count: Optional[int] = None
    gt_canopy_uniformity_cv: Optional[float] = None
    is_orchard: bool = False
    
    # Image Simulation Params
    image_width: int = 100
    image_height: int = 100
    row_angle_deg: float = 0.0
    row_width_px: int = 10
    row_spacing_px: int = 40
    weed_density: float = 0.0
    gap_density: float = 0.0
    contiguous_gaps: bool = False  # If True, gaps are contiguous block-level segments
    gap_segment_length_px: int = 20  # Length of each contiguous gap segment in pixels

def _generate_synthetic_ortho(case: DroneBenchmarkCase) -> Dict[str, List[List[int]]]:
    """Generate a 2D synthetic orthomosaic with rows, weeds, gaps, or disease."""
    w, h = case.image_width, case.image_height
    seed = int(hashlib.md5(case.case_id.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    
    red = [[0] * w for _ in range(h)]
    green = [[0] * w for _ in range(h)]
    blue = [[0] * w for _ in range(h)]
    
    # If this is the command mode, generate disease pixels
    if case.flight_mode == FlightMode.COMMAND_REVISIT_MODE:
        for y in range(h):
            for x in range(w):
                # Base color: R=240, G=200, B=100 (Golden wheat / severe chlorosis)
                # This explicitly passes the FIELD fallback due to brown_ratio > 0.20
                # and green_ratio = 0.37 (which is > 0.36).
                r, g, b = 240, 200, 100 
                    
                # Add noise uniformly in [-25, 25] to get bstd ~ 14.
                # This avoids Rule 0 (bstd < 3) and Rule 1c (bstd < 12),
                # and avoids symptom uniformity penalty (bstd < 10).
                noise = rng.randint(-25, 25)
                red[y][x] = min(255, max(0, r + noise))
                green[y][x] = min(255, max(0, g + noise))
                blue[y][x] = min(255, max(0, b + noise))
        return {"red": red, "green": green, "blue": blue}

    # --- QA Stress Cases ---
    
    if case.case_id == "qa_partial_strip":
        # 40% of the mosaic is black (simulates battery-died mid-flight).
        # First 60% has normal rows, last 40% is all zeros.
        cutoff_y = int(h * 0.6)
        theta = math.radians(case.row_angle_deg)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        for y in range(cutoff_y):
            for x in range(w):
                rho = x * cos_t + y * sin_t
                dist_to_row = rho % case.row_spacing_px
                if dist_to_row > case.row_spacing_px / 2:
                    dist_to_row = case.row_spacing_px - dist_to_row
                if dist_to_row < (case.row_width_px / 2):
                    r, g, b = 40, 160, 40
                else:
                    r, g, b = 130, 100, 70
                noise = rng.randint(-10, 10)
                red[y][x] = min(255, max(0, r + noise))
                green[y][x] = min(255, max(0, g + noise))
                blue[y][x] = min(255, max(0, b + noise))
        # y >= cutoff_y stays all zeros (black strip)
        return {"red": red, "green": green, "blue": blue}
    
    if case.case_id == "qa_blur_heavy":
        # Uniform green with near-zero variance — simulates severe motion blur.
        # All pixels are exactly the same value (Laplacian variance → 0).
        for y in range(h):
            for x in range(w):
                red[y][x] = 60
                green[y][x] = 130
                blue[y][x] = 50
        return {"red": red, "green": green, "blue": blue}
    
    if case.case_id == "qa_shadow_rows":
        # Alternating very bright and very dark horizontal bands (shadow).
        # Normal rows underneath, but with dramatic brightness modulation.
        theta = math.radians(case.row_angle_deg)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        for y in range(h):
            # Shadow multiplier: alternates between 0.3 and 1.0 every 10 rows
            shadow = 0.3 if (y // 10) % 2 == 0 else 1.0
            for x in range(w):
                rho = x * cos_t + y * sin_t
                dist_to_row = rho % case.row_spacing_px
                if dist_to_row > case.row_spacing_px / 2:
                    dist_to_row = case.row_spacing_px - dist_to_row
                if dist_to_row < (case.row_width_px / 2):
                    r, g, b = 40, 160, 40
                else:
                    r, g, b = 130, 100, 70
                r = int(r * shadow)
                g = int(g * shadow)
                b = int(b * shadow)
                noise = rng.randint(-5, 5)
                red[y][x] = min(255, max(0, r + noise))
                green[y][x] = min(255, max(0, g + noise))
                blue[y][x] = min(255, max(0, b + noise))
        return {"red": red, "green": green, "blue": blue}
    
    # --- Orchard Mode Cases ---
    if case.is_orchard:
        # Generate circular tree canopies on a regular grid
        tree_spacing_px = 25  # Space between tree centres
        tree_radius_px = 8    # Base canopy radius
        
        # Build tree grid
        trees = []
        ty = tree_spacing_px // 2
        while ty < h:
            tx = tree_spacing_px // 2
            while tx < w:
                trees.append((ty, tx))
                tx += tree_spacing_px
            ty += tree_spacing_px
        
        # Remove trees for "missing" cases
        if case.case_id == "orchard_missing_5pct" and len(trees) > 1:
            # Remove the 4th tree (deterministic)
            trees.pop(3)
        
        for y in range(h):
            for x in range(w):
                is_tree = False
                for ty, tx in trees:
                    dist = math.sqrt((y - ty) ** 2 + (x - tx) ** 2)
                    radius = tree_radius_px
                    # Variable canopy for uniformity test
                    if case.case_id == "orchard_variable_canopy":
                        # Vary radius based on tree index
                        idx = trees.index((ty, tx))
                        radius = tree_radius_px + (idx % 5) * 2 - 4  # Range: 4 to 12
                        radius = max(3, radius)
                    if dist < radius:
                        is_tree = True
                        break
                
                if is_tree:
                    r, g, b = 30, 140, 30  # Dark tree canopy green
                else:
                    r, g, b = 130, 100, 70  # Soil/ground
                
                noise = rng.randint(-10, 10)
                red[y][x] = min(255, max(0, r + noise))
                green[y][x] = min(255, max(0, g + noise))
                blue[y][x] = min(255, max(0, b + noise))
        
        return {"red": red, "green": green, "blue": blue}
        
    theta = math.radians(case.row_angle_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    
    # Precompute contiguous gap regions if requested
    gap_regions = set()  # Set of (y, x) pixels that are in a gap
    if case.contiguous_gaps and case.gap_density > 0:
        # Place contiguous gap segments along rows
        seg_len = case.gap_segment_length_px
        # Number of segments to place (approximate gap_density coverage)
        total_row_pixels = 0
        row_positions = {}  # row_idx -> list of (y, x) crop positions
        for y in range(h):
            for x in range(w):
                rho = x * cos_t + y * sin_t
                dist_to_row = rho % case.row_spacing_px
                if dist_to_row > case.row_spacing_px / 2:
                    dist_to_row = case.row_spacing_px - dist_to_row
                if dist_to_row < (case.row_width_px / 2):
                    # Position along row
                    along = -x * sin_t + y * cos_t
                    row_idx = round(rho / case.row_spacing_px)
                    if row_idx not in row_positions:
                        row_positions[row_idx] = []
                    row_positions[row_idx].append((along, y, x))
                    total_row_pixels += 1
        
        # Sort each row by along-position
        for row_idx in row_positions:
            row_positions[row_idx].sort(key=lambda p: p[0])
        
        # Place gap segments to achieve ~gap_density coverage
        target_gap_pixels = int(total_row_pixels * case.gap_density)
        placed = 0
        for row_idx in sorted(row_positions.keys()):
            positions = row_positions[row_idx]
            if len(positions) < seg_len:
                continue
            # Place one gap segment per row (at a random start)
            start = rng.randint(0, max(0, len(positions) - seg_len))
            for i in range(start, min(start + seg_len, len(positions))):
                _, gy, gx = positions[i]
                gap_regions.add((gy, gx))
                placed += 1
            if placed >= target_gap_pixels:
                break
    
    for y in range(h):
        for x in range(w):
            # Distance to nearest row
            rho = x * cos_t + y * sin_t
            dist_to_row = rho % case.row_spacing_px
            if dist_to_row > case.row_spacing_px / 2:
                dist_to_row = case.row_spacing_px - dist_to_row
                
            is_crop = dist_to_row < (case.row_width_px / 2)
            
            # Simulate gaps
            if is_crop and case.gap_density > 0:
                if case.contiguous_gaps:
                    if (y, x) in gap_regions:
                        is_crop = False
                else:
                    if rng.random() < case.gap_density:
                        is_crop = False
                
            # Simulate weeds
            is_weed = (not is_crop) and (rng.random() < case.weed_density)
            
            if is_crop:
                r, g, b = 40, 160, 40 # Crop green (ExG ~ 1.0)
            elif is_weed:
                r, g, b = 100, 150, 30 # Weed green (ExG ~ 0.6)
            else:
                r, g, b = 130, 100, 70 # Soil brown
                
            # Add noise
            r = min(255, max(0, r + rng.randint(-15, 15)))
            g = min(255, max(0, g + rng.randint(-15, 15)))
            b = min(255, max(0, b + rng.randint(-15, 15)))
            
            red[y][x] = r
            green[y][x] = g
            blue[y][x] = b
            
    return {"red": red, "green": green, "blue": blue}

# Standard rectangular plot (~170m x 167m, ~2.8 hectares — realistic field-scale).
# Large enough relative to the camera footprint (~80m x 60m) to produce meaningful
# waste metrics, while small enough to fit within prosumer drone battery limits.
STANDARD_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [0.0, 0.0], [0.002, 0.0], [0.002, 0.0015], [0.0, 0.0015], [0.0, 0.0]
    ]]
}

BENCHMARK_CASES = [
    # 1. Clean Row Audit
    DroneBenchmarkCase(
        case_id="row_audit_clean_0deg",
        description="Clean rows aligned North-South (0 deg)",
        mission_type=MissionType.ROW_AUDIT,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_row_azimuth_deg=0.0,
        gt_canopy_cover=0.25,
        gt_weed_pressure=0.0,
        row_angle_deg=0.0,
        weed_density=0.0
    ),
    DroneBenchmarkCase(
        case_id="row_audit_clean_45deg",
        description="Clean rows angled at 45 deg",
        mission_type=MissionType.ROW_AUDIT,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_row_azimuth_deg=45.0,
        gt_canopy_cover=0.25,
        gt_weed_pressure=0.0,
        row_angle_deg=45.0,
        weed_density=0.0
    ),
    
    # 2. Weedy Field
    DroneBenchmarkCase(
        case_id="weed_map_high_pressure",
        description="Rows with heavy inter-row weed pressure",
        mission_type=MissionType.WEED_MAP,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_row_azimuth_deg=90.0,
        gt_weed_pressure=0.30, # 30% of field is weed
        row_angle_deg=90.0,
        weed_density=0.40 # density applied to non-crop area
    ),
    
    # 3. Gap Detection
    DroneBenchmarkCase(
        case_id="stand_gaps_10pct",
        description="10% stand loss (emergence failure gaps)",
        mission_type=MissionType.ROW_AUDIT,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_row_azimuth_deg=15.0,
        gt_gap_fraction=0.10,
        row_angle_deg=15.0,
        gap_density=0.10
    ),
    
    # 4. Command Mode Revisit (Feasibility & Routing)
    DroneBenchmarkCase(
        case_id="command_leaf_revisit",
        description="Low altitude orbit around a concern zone",
        mission_type=MissionType.CONCERN_ZONE_COMMAND,
        flight_mode=FlightMode.COMMAND_REVISIT_MODE,
        polygon_geojson=STANDARD_POLYGON, # Small target zone
        target_gsd_cm=0.5,
        gt_row_azimuth_deg=None # Not extracted in command mode
    ),
    
    # ============================================================
    # QA Robustness Cases
    # ============================================================
    
    # 5. Partial Strip — 40% of mosaic is black (battery died mid-flight)
    DroneBenchmarkCase(
        case_id="qa_partial_strip",
        description="QA: 40% coverage hole (partial strip)",
        mission_type=MissionType.FULL_PLOT_MAP,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_row_azimuth_deg=0.0,
        gt_weed_pressure=0.0,
        row_angle_deg=0.0,
        weed_density=0.0,
    ),
    
    # 6. Heavy Blur — uniform green (severe motion blur destroys all texture)
    DroneBenchmarkCase(
        case_id="qa_blur_heavy",
        description="QA: Severe motion blur (uniform green)",
        mission_type=MissionType.FULL_PLOT_MAP,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_row_azimuth_deg=None, # Not extractable from blur
        gt_weed_pressure=None,
    ),
    
    # 7. Shadow Rows — alternating very bright and very dark bands
    DroneBenchmarkCase(
        case_id="qa_shadow_rows",
        description="QA: Heavy shadow bands across rows",
        mission_type=MissionType.FULL_PLOT_MAP,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_row_azimuth_deg=0.0,
        gt_weed_pressure=0.0,
        row_angle_deg=0.0,
        weed_density=0.0,
    ),
    
    # ============================================================
    # V1.5 — Row Continuity & Break Detection
    # ============================================================
    
    DroneBenchmarkCase(
        case_id="row_breaks_15pct",
        description="15% stand loss with distinct contiguous row breaks",
        mission_type=MissionType.ROW_AUDIT,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_row_azimuth_deg=0.0,
        gt_gap_fraction=0.15,
        gt_row_break_count=3,  # ~3 contiguous gap segments (one per row)
        row_angle_deg=0.0,
        gap_density=0.15,
        contiguous_gaps=True,
        gap_segment_length_px=20,
    ),
    DroneBenchmarkCase(
        case_id="row_breaks_scattered",
        description="10% scattered gaps (not contiguous — fewer breaks)",
        mission_type=MissionType.ROW_AUDIT,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_row_azimuth_deg=30.0,
        gt_gap_fraction=0.10,
        gt_row_break_count=0,  # Scattered gaps don't form contiguous breaks
        row_angle_deg=30.0,
        gap_density=0.10,
    ),
    
    # ============================================================
    # V1.5 — In-Row vs Inter-Row Weed Separation
    # ============================================================
    
    DroneBenchmarkCase(
        case_id="in_row_vs_inter_weed",
        description="In-row weed at ~10%, inter-row weed at ~30%",
        mission_type=MissionType.WEED_MAP,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_row_azimuth_deg=0.0,
        gt_weed_pressure=0.30,
        row_angle_deg=0.0,
        weed_density=0.40,  # Applied uniformly; row mask separates in/inter
    ),
    
    # ============================================================
    # V1.5 — Orchard Mode
    # ============================================================
    
    DroneBenchmarkCase(
        case_id="orchard_regular_grid",
        description="Regular olive tree grid (25px spacing, 16 trees)",
        mission_type=MissionType.ORCHARD_AUDIT,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_tree_count=16,
        gt_missing_tree_count=0,
        is_orchard=True,
    ),
    DroneBenchmarkCase(
        case_id="orchard_missing_5pct",
        description="Orchard with 1 missing tree out of 16",
        mission_type=MissionType.ORCHARD_AUDIT,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_tree_count=15,
        gt_missing_tree_count=1,
        is_orchard=True,
    ),
    DroneBenchmarkCase(
        case_id="orchard_variable_canopy",
        description="Orchard with variable canopy sizes (CV > 0.2)",
        mission_type=MissionType.ORCHARD_AUDIT,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson=STANDARD_POLYGON,
        gt_tree_count=16,
        gt_canopy_uniformity_cv=0.37,
        is_orchard=True,
    ),
    
    # ============================================================
    # V1.5 — Irregular Polygon Planner Stress
    # ============================================================
    
    DroneBenchmarkCase(
        case_id="irregular_polygon_L",
        description="L-shaped polygon to test turn optimization",
        mission_type=MissionType.FULL_PLOT_MAP,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson={
            "type": "Polygon",
            "coordinates": [[
                [0.0, 0.0], [0.002, 0.0], [0.002, 0.0008],
                [0.001, 0.0008], [0.001, 0.0015], [0.0, 0.0015], [0.0, 0.0]
            ]]
        },
        gt_row_azimuth_deg=0.0,
        row_angle_deg=0.0,
    ),
    DroneBenchmarkCase(
        case_id="irregular_polygon_triangle",
        description="Triangular field (high edge waste expected)",
        mission_type=MissionType.FULL_PLOT_MAP,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson={
            "type": "Polygon",
            "coordinates": [[
                [0.0, 0.0], [0.002, 0.0], [0.001, 0.0015], [0.0, 0.0]
            ]]
        },
        gt_row_azimuth_deg=0.0,
        row_angle_deg=0.0,
    ),
    DroneBenchmarkCase(
        case_id="adaptive_overlap_narrow",
        description="Very narrow polygon strip to test pass filtering",
        mission_type=MissionType.FULL_PLOT_MAP,
        flight_mode=FlightMode.MAPPING_MODE,
        polygon_geojson={
            "type": "Polygon",
            "coordinates": [[
                [0.0, 0.0], [0.0003, 0.0], [0.0003, 0.0015], [0.0, 0.0015], [0.0, 0.0]
            ]]
        },
        gt_row_azimuth_deg=0.0,
        row_angle_deg=0.0,
    ),
]
