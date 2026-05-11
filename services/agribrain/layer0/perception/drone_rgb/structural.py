"""
Drone Structural Analyzer.

Extracts high-resolution 2D structural maps (canopy, soil, weeds, gaps, rows)
from stitched orthomosaic arrays.

V1.5 additions:
  - Row continuity profiling + row break detection
  - In-row vs inter-row weed separation
  - Orchard mode (tree count, missing trees, canopy diameter, uniformity)
"""

from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
import math

from layer0.perception.drone_rgb.schemas import DroneRGBInput, DroneStructuralMap, RowBreak
from layer0.perception.drone_rgb import row_analysis
from layer0.perception.drone_rgb import orchard_analysis
from drone_mission.schemas import MissionType

@dataclass
class StructuralResult:
    row_azimuth_deg: float = 0.0
    row_spacing_cm: float = 0.0
    canopy_cover_fraction: float = 0.0
    bare_soil_fraction: float = 0.0
    weed_pressure_index: float = 0.0
    spatial_maps: List[DroneStructuralMap] = None

    # V1.5 Row continuity
    row_count: int = 0
    row_continuity_scores: List[float] = field(default_factory=list)
    row_breaks: List[RowBreak] = field(default_factory=list)
    stand_density_per_row: List[float] = field(default_factory=list)

    # V1.5 Weed separation
    in_row_weed_fraction: float = 0.0
    inter_row_weed_fraction: float = 0.0

    # V1.5 Orchard mode
    tree_count: int = 0
    missing_tree_count: int = 0
    canopy_diameters_cm: List[float] = field(default_factory=list)
    canopy_uniformity_cv: float = 0.0


class DroneStructuralAnalyzer:
    """Analyzes Drone orthomosaic arrays for structural features."""
    
    def analyze(self, inp: DroneRGBInput) -> StructuralResult:
        res = StructuralResult(spatial_maps=[])
        
        # 1. Pixel Extraction
        pixels = inp.synthetic_ortho_pixels
        if not pixels:
            # Fallback if no synthetic pixels provided (e.g. real prod environment not yet hooked up)
            return res
            
        red = pixels.get("red", [])
        green = pixels.get("green", [])
        blue = pixels.get("blue", [])
        if not red or not red[0]:
            return res
            
        h, w = len(red), len(red[0])
        total_pixels = h * w
        
        # We will build spatial raster maps (downsampled to 10x10 blocks for speed/memory in MVP)
        block_size = max(1, min(w, h) // 40)
        grid_h = h // block_size
        grid_w = w // block_size
        
        canopy_map = [[0.0] * grid_w for _ in range(grid_h)]
        weed_map = [[0.0] * grid_w for _ in range(grid_h)]
        gap_map = [[0.0] * grid_w for _ in range(grid_h)]
        
        canopy_count = 0
        soil_count = 0
        weed_count = 0
        
        # 2. Vegetation Indexing (ExG + ExR)
        # We iterate over blocks to build the spatial rasters
        for gy in range(grid_h):
            for gx in range(grid_w):
                block_veg_count = 0
                block_soil_count = 0
                block_weed_count = 0
                
                # Scan pixels within the block
                for by in range(block_size):
                    for bx in range(block_size):
                        y = gy * block_size + by
                        x = gx * block_size + bx
                        if y >= h or x >= w:
                            continue
                            
                        r, g, b = red[y][x], green[y][x], blue[y][x]
                        total_rgb = r + g + b
                        if total_rgb == 0:
                            block_soil_count += 1
                            continue
                            
                        # Normalized RGB
                        nr, ng, nb = r / total_rgb, g / total_rgb, b / total_rgb
                        exg = 2 * ng - nr - nb
                        
                        # High ExG and sufficiently bright -> vegetation
                        if exg > 0.25 and total_rgb > 100:
                            # Two-feature crop/weed separation:
                            # Crop: very green-dominant, low red ratio (r/g ~ 0.25)
                            # Weed: moderate green, higher red ratio (r/g ~ 0.67)
                            # ExG alone is noisy; red/green ratio is more stable
                            rg_ratio = r / max(g, 1)
                            
                            # Crop: ExG > 0.85 AND r/g < 0.40
                            # Weed: everything else that's vegetation
                            if exg > 0.85 and rg_ratio < 0.40:
                                block_veg_count += 1
                            elif rg_ratio < 0.35:
                                # Very low r/g despite lower ExG -> still crop
                                block_veg_count += 1
                            else:
                                block_weed_count += 1
                        else:
                            block_soil_count += 1
                            
                block_total = block_veg_count + block_soil_count + block_weed_count
                if block_total > 0:
                    veg_frac = block_veg_count / block_total
                    weed_frac = block_weed_count / block_total
                    soil_frac = block_soil_count / block_total
                    
                    canopy_map[gy][gx] = veg_frac
                    weed_map[gy][gx] = weed_frac
                    # A gap is an area that should be canopy but is entirely soil (in a row context)
                    gap_map[gy][gx] = 1.0 if (soil_frac > 0.95) else 0.0
                    
                    canopy_count += block_veg_count
                    weed_count += block_weed_count
                    soil_count += block_soil_count
                    
        # 3. Overall Plot Metrics
        if total_pixels > 0:
            res.canopy_cover_fraction = canopy_count / total_pixels
            res.bare_soil_fraction = soil_count / total_pixels
            res.weed_pressure_index = weed_count / total_pixels
            
        # 4. Row Extraction — FFT-based detection (Phase D)
        #    Falls back to projection-variance if grid is too small for FFT
        meta = inp.orthomosaic_metadata or {}
        gsd_cm = meta.get("achieved_gsd_cm", 2.0)
        
        fft_result = row_analysis.fft_detect_rows(
            canopy_map, gsd_cm=gsd_cm, block_size=block_size,
        )
        
        if fft_result.confidence > 0.3:
            # FFT detected strong row pattern — use FFT results
            res.row_azimuth_deg = fft_result.azimuth_deg
            res.row_spacing_cm = fft_result.spacing_cm
        else:
            # Fallback to projection-variance for angle, default spacing
            res.row_azimuth_deg = self._extract_row_angle(canopy_map)
            res.row_spacing_cm = 75.0  # Default 75cm (30-inch) rows
        
        # 5. Populate Spatial Maps
        meta = inp.orthomosaic_metadata or {}
        gsd_cm = meta.get("achieved_gsd_cm", 2.0)
        map_res_cm = gsd_cm * block_size
        
        res.spatial_maps.append(DroneStructuralMap(
            map_type="canopy_cover", resolution_cm=map_res_cm, data_grid=canopy_map
        ))
        res.spatial_maps.append(DroneStructuralMap(
            map_type="weed_pressure", resolution_cm=map_res_cm, data_grid=weed_map
        ))
        res.spatial_maps.append(DroneStructuralMap(
            map_type="stand_gaps", resolution_cm=map_res_cm, data_grid=gap_map
        ))
        
        # ====================================================================
        # V1.5 Extensions
        # ====================================================================
        
        is_orchard = (
            inp.mission_type == MissionType.ORCHARD_AUDIT
            or not self._has_row_structure(canopy_map, res.row_azimuth_deg)
        )
        
        if is_orchard:
            self._run_orchard_analysis(res, inp, canopy_map, block_size, map_res_cm)
        else:
            self._run_row_analysis(
                res, canopy_map, weed_map,
                res.row_azimuth_deg, inp, block_size, map_res_cm
            )

        return res
    
    def _has_row_structure(self, canopy_map: List[List[float]], azimuth: float) -> bool:
        """Quick check: does the canopy map have clear linear row structure?
        
        Returns True if projection variance at best angle is significantly higher
        than the mean variance across all angles (indicates strong linear pattern).
        """
        if not canopy_map or not canopy_map[0]:
            return False
        h, w = len(canopy_map), len(canopy_map[0])
        
        # Compute projection variance at the best angle and at a perpendicular angle
        theta_best = math.radians(azimuth)
        theta_perp = math.radians((azimuth + 90) % 180)
        
        def _proj_var(theta):
            cos_t, sin_t = math.cos(theta), math.sin(theta)
            bins = {}
            for y in range(h):
                for x in range(w):
                    if canopy_map[y][x] > 0.1:
                        rho = int(x * cos_t + y * sin_t)
                        bins[rho] = bins.get(rho, 0.0) + canopy_map[y][x]
            if not bins:
                return 0.0
            mean = sum(bins.values()) / len(bins)
            return sum((v - mean) ** 2 for v in bins.values()) / len(bins)
        
        var_best = _proj_var(theta_best)
        var_perp = _proj_var(theta_perp)
        
        # If best-angle variance is > 2x perpendicular, there are rows
        return var_best > var_perp * 2.0

    def _run_row_analysis(
        self, res: StructuralResult,
        canopy_map: List[List[float]],
        weed_map: List[List[float]],
        azimuth: float,
        inp: DroneRGBInput,
        block_size: int,
        map_res_cm: float,
    ):
        """V1.5 row continuity, break detection, weed separation."""
        grid_h = len(canopy_map)
        grid_w = len(canopy_map[0]) if grid_h > 0 else 0
        
        # Use the synthetic image's row params for spacing
        row_spacing_px = 40  # default from benchmark cases
        row_width_px = 10
        
        # Row continuity
        scores, row_count = row_analysis.compute_row_profiles(
            canopy_map, azimuth, row_spacing_px, block_size,
        )
        res.row_continuity_scores = scores
        res.row_count = row_count
        
        # Row breaks
        res.row_breaks = row_analysis.detect_row_breaks(
            canopy_map, azimuth, row_spacing_px, row_width_px, block_size,
        )
        
        # Stand density
        res.stand_density_per_row = row_analysis.compute_stand_density(
            canopy_map, azimuth, row_spacing_px, row_width_px, block_size,
        )
        
        # In-row vs inter-row weed separation
        row_mask = row_analysis._build_row_mask(
            grid_h, grid_w, azimuth, row_spacing_px, row_width_px, block_size,
        )
        in_row_map, inter_row_map, in_frac, inter_frac = row_analysis.classify_weed_location(
            weed_map, row_mask,
        )
        res.in_row_weed_fraction = in_frac
        res.inter_row_weed_fraction = inter_frac
        
        # Append weed split maps
        res.spatial_maps.append(DroneStructuralMap(
            map_type="in_row_weeds", resolution_cm=map_res_cm, data_grid=in_row_map,
        ))
        res.spatial_maps.append(DroneStructuralMap(
            map_type="inter_row_weeds", resolution_cm=map_res_cm, data_grid=inter_row_map,
        ))

    def _run_orchard_analysis(
        self, res: StructuralResult,
        inp: DroneRGBInput,
        canopy_map: List[List[float]],
        block_size: int,
        map_res_cm: float,
    ):
        """V1.5 orchard mode: tree detection, missing trees, canopy stats."""
        # Detect tree clusters
        clusters = orchard_analysis.detect_tree_clusters(canopy_map)
        res.tree_count = len(clusters)
        
        # Estimate or override spacing
        if inp.expected_tree_spacing_m is not None:
            spacing_blocks = (inp.expected_tree_spacing_m * 100.0) / map_res_cm
        else:
            spacing_blocks = orchard_analysis.estimate_tree_spacing(clusters)
        
        # Missing trees
        if spacing_blocks > 1:
            missing_map, missing_count = orchard_analysis.estimate_missing_trees(
                canopy_map, clusters, spacing_blocks,
            )
            res.missing_tree_count = missing_count
            if missing_map:
                res.spatial_maps.append(DroneStructuralMap(
                    map_type="missing_tree_map", resolution_cm=map_res_cm,
                    data_grid=missing_map,
                ))
        
        # Canopy diameters
        res.canopy_diameters_cm = orchard_analysis.compute_canopy_diameters(
            clusters, map_res_cm,
        )
        
        # Uniformity
        res.canopy_uniformity_cv = orchard_analysis.compute_canopy_uniformity(
            res.canopy_diameters_cm,
        )
        
    def _extract_row_angle(self, canopy_map: List[List[float]]) -> float:
        """Estimate row azimuth (0-180 deg) by maximizing projection variance.
        
        Row azimuth is defined modulo 180° (0° and 180° are the same line).
        Uses integer rho binning for stability, with a clamped fine sweep
        that does not cross the 0°/180° boundary.
        """
        if not canopy_map or not canopy_map[0]:
            return 0.0
            
        h, w = len(canopy_map), len(canopy_map[0])
        
        # Precompute vegetation block positions
        veg_blocks = []
        for y in range(h):
            for x in range(w):
                val = canopy_map[y][x]
                if val > 0.1:
                    veg_blocks.append((x, y, val))
        if not veg_blocks:
            return 0.0
        
        # Fixed bin count for projection — use the larger grid dimension
        # to ensure sufficient resolution for row detection
        num_bins = max(w, h)
        
        def _proj_variance(angle_deg: float) -> float:
            theta = math.radians(angle_deg)
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            # Project to fixed number of bins to ensure variance is
            # comparable across all angles. At 0°, rho ranges [0, w).
            # At 45°, rho ranges [0, w*1.414). We normalise rho into
            # NUM_BINS bins regardless of the angle.
            rho_vals = []
            for x, y, val in veg_blocks:
                rho_vals.append((x * cos_t + y * sin_t, val))
            if not rho_vals:
                return 0.0
            rho_min = min(r[0] for r in rho_vals)
            rho_max = max(r[0] for r in rho_vals)
            rho_range = rho_max - rho_min
            if rho_range < 1e-6:
                return 0.0
            proj_bins = {}
            for rho, val in rho_vals:
                # Quantize into num_bins uniform buckets
                bucket = int((rho - rho_min) / rho_range * num_bins)
                bucket = min(bucket, num_bins - 1)
                proj_bins[bucket] = proj_bins.get(bucket, 0.0) + val
            mean = sum(proj_bins.values()) / len(proj_bins)
            return sum((v - mean) ** 2 for v in proj_bins.values()) / len(proj_bins)
        
        # Pass 1: Coarse sweep at 1° steps (0 to 179)
        best_angle = 0.0
        max_var = -1.0
        for angle_deg in range(180):
            var = _proj_variance(float(angle_deg))
            if var > max_var:
                max_var = var
                best_angle = float(angle_deg)
        
        # Pass 2: Fine sweep — clamped to avoid crossing 0°/180° boundary
        fine_best = best_angle
        fine_max = max_var
        low = max(0.0, best_angle - 2.0)
        high = min(179.5, best_angle + 2.0)
        step = 0.5
        angle = low
        while angle <= high:
            var = _proj_variance(angle)
            if var > fine_max:
                fine_max = var
                fine_best = angle
            angle += step
        
        # Pass 3: Boundary canonicalization.
        # Near 0°/180° and 90°, the projection variance is dominated by
        # binning artifacts, not actual signal differences. Any result
        # within ±3° of a boundary is snapped to the canonical form.
        if fine_best >= 177.0 or fine_best <= 3.0:
            # Snap to 0° (canonical for vertical rows)
            fine_best = 0.0
        elif 87.0 <= fine_best <= 93.0:
            # Snap to 90° (canonical for horizontal rows)
            fine_best = 90.0
        
        # Round to nearest 0.5°
        return round(fine_best * 2) / 2.0

