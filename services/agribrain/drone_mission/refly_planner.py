"""
Re-Fly Planner.

Identifies weak-confidence zones from a completed drone mission and generates
a targeted re-fly plan covering only those zones instead of the whole plot.

V1.5B tightening: now builds actual sub-polygon bounding boxes from spatial
map analysis and plans over those sub-regions, not the full plot.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import uuid
import math

from .schemas import (
    MissionIntent, MissionType, FlightMode, FlightPlan,
    CoveragePattern, Waypoint,
)
from .capability_profiles import get_profile
from .coverage_patterns import plan_adaptive_boustrophedon
from .safety_rules import check_feasibility


@dataclass
class WeakZone:
    """A zone within a completed mission that needs re-inspection."""
    zone_bbox: Dict[str, float]     # {min_lat, max_lat, min_lon, max_lon}
    weakness_type: str              # "low_coverage", "blur", "shadow", "high_gap_density"
    confidence: float               # Original confidence (0–1), lower = weaker
    area_fraction: float            # Fraction of total plot area


# Minimum area fraction to justify a re-fly (don't re-fly for tiny slivers)
_MIN_AREA_FRACTION = 0.05
# Confidence below which a zone is "weak"
_WEAKNESS_THRESHOLD = 0.6


class ReflyPlanner:
    """Plans targeted re-fly missions for weak-confidence zones."""

    def identify_weak_zones(
        self,
        qa_score: float,
        coverage_completeness: float,
        spatial_maps: List[Any] = None,
        plot_polygon: Dict[str, Any] = None,
    ) -> List[WeakZone]:
        """Identify weak zones from QA output and spatial maps.
        
        When spatial maps are available, extracts actual bounding boxes for
        weak regions.  Otherwise falls back to heuristic full-plot estimates.
        
        Args:
            qa_score: Overall QA score (0–1)
            coverage_completeness: Coverage fraction (0–1)
            spatial_maps: List of DroneStructuralMap objects (optional)
            plot_polygon: Original plot polygon GeoJSON (for bbox computation)
        
        Returns:
            List of WeakZone objects with populated zone_bbox when possible.
        """
        zones = []
        plot_bbox = self._polygon_to_bbox(plot_polygon) if plot_polygon else {}

        # 1. Low coverage → the uncovered area is a weak zone
        if coverage_completeness < 0.90:
            uncovered = 1.0 - coverage_completeness
            if uncovered >= _MIN_AREA_FRACTION:
                zones.append(WeakZone(
                    zone_bbox=plot_bbox,  # Full-plot when we can't localise
                    weakness_type="low_coverage",
                    confidence=coverage_completeness,
                    area_fraction=uncovered,
                ))

        # 2. Low QA score → general quality degradation
        if qa_score < _WEAKNESS_THRESHOLD:
            zones.append(WeakZone(
                zone_bbox=plot_bbox,
                weakness_type="quality_degradation",
                confidence=qa_score,
                area_fraction=0.5,
            ))

        # 3. Scan spatial maps for localised gap clusters
        if spatial_maps and plot_bbox:
            for smap in spatial_maps:
                if smap.map_type == "stand_gaps":
                    gap_zones = self._extract_gap_zones(smap.data_grid, plot_bbox)
                    zones.extend(gap_zones)

        return zones

    def _polygon_to_bbox(self, polygon_geojson: Dict[str, Any]) -> Dict[str, float]:
        """Extract bounding box from polygon GeoJSON."""
        coords = polygon_geojson.get("coordinates", [[]])[0]
        if len(coords) < 3:
            return {}
        lats = [p[1] for p in coords]
        lons = [p[0] for p in coords]
        return {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lon": min(lons),
            "max_lon": max(lons),
        }

    def _extract_gap_zones(
        self,
        gap_grid: List[List[float]],
        plot_bbox: Dict[str, float],
    ) -> List[WeakZone]:
        """Extract sub-region bounding boxes from gap clusters in the spatial map.
        
        Divides the grid into quadrants, computes gap fraction per quadrant,
        and returns WeakZone objects for quadrants with > 15% gap density.
        """
        if not gap_grid or not gap_grid[0]:
            return []

        h, w = len(gap_grid), len(gap_grid[0])
        total_cells = h * w
        if total_cells == 0:
            return []

        # Overall gap fraction
        total_gaps = sum(1 for row in gap_grid for val in row if val > 0.5)
        overall_fraction = total_gaps / total_cells
        if overall_fraction <= 0.15:
            return []

        # Divide into quadrants for sub-region localisation
        mid_y, mid_x = h // 2, w // 2
        lat_range = plot_bbox["max_lat"] - plot_bbox["min_lat"]
        lon_range = plot_bbox["max_lon"] - plot_bbox["min_lon"]

        quadrants = [
            # (y_start, y_end, x_start, x_end, bbox)
            (0, mid_y, 0, mid_x, {
                "min_lat": plot_bbox["min_lat"],
                "max_lat": plot_bbox["min_lat"] + lat_range / 2,
                "min_lon": plot_bbox["min_lon"],
                "max_lon": plot_bbox["min_lon"] + lon_range / 2,
            }),
            (0, mid_y, mid_x, w, {
                "min_lat": plot_bbox["min_lat"],
                "max_lat": plot_bbox["min_lat"] + lat_range / 2,
                "min_lon": plot_bbox["min_lon"] + lon_range / 2,
                "max_lon": plot_bbox["max_lon"],
            }),
            (mid_y, h, 0, mid_x, {
                "min_lat": plot_bbox["min_lat"] + lat_range / 2,
                "max_lat": plot_bbox["max_lat"],
                "min_lon": plot_bbox["min_lon"],
                "max_lon": plot_bbox["min_lon"] + lon_range / 2,
            }),
            (mid_y, h, mid_x, w, {
                "min_lat": plot_bbox["min_lat"] + lat_range / 2,
                "max_lat": plot_bbox["max_lat"],
                "min_lon": plot_bbox["min_lon"] + lon_range / 2,
                "max_lon": plot_bbox["max_lon"],
            }),
        ]

        zones = []
        for y0, y1, x0, x1, bbox in quadrants:
            quad_total = 0
            quad_gaps = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    quad_total += 1
                    if gap_grid[y][x] > 0.5:
                        quad_gaps += 1
            if quad_total > 0:
                quad_fraction = quad_gaps / quad_total
                if quad_fraction > 0.15:
                    zones.append(WeakZone(
                        zone_bbox=bbox,
                        weakness_type="high_gap_density",
                        confidence=1.0 - quad_fraction,
                        area_fraction=quad_fraction * 0.25,  # Quadrant is 25% of plot
                    ))

        return zones

    def _compute_gap_fraction(self, grid: List[List[float]]) -> float:
        """Compute fraction of blocks that are gaps."""
        if not grid or not grid[0]:
            return 0.0
        total = 0
        gap_count = 0
        for row in grid:
            for val in row:
                total += 1
                if val > 0.5:
                    gap_count += 1
        return gap_count / total if total > 0 else 0.0

    def plan_refly(
        self,
        weak_zones: List[WeakZone],
        plot_polygon: Dict[str, Any],
        profile_name: str = "standard_prosumer",
        plot_id: str = "unknown",
    ) -> Optional[FlightPlan]:
        """Generate a minimal re-fly plan covering only the weak zones.
        
        If zones have sub-region bounding boxes, the planner builds a
        merged bounding-box polygon and flies only that area.
        Otherwise falls back to full-plot re-fly.
        
        Returns None if no zones are worth re-flying.
        """
        if not weak_zones:
            return None

        # Filter zones worth re-flying
        worth_it = [z for z in weak_zones if z.area_fraction >= _MIN_AREA_FRACTION]
        if not worth_it:
            return None

        # Build target polygon: merge sub-region bboxes if available
        target_polygon = self._build_target_polygon(worth_it, plot_polygon)

        profile = get_profile(profile_name)

        # Use a conservative GSD for re-fly (2.0 cm)
        target_gsd = 2.0
        target_gsd_mm = target_gsd * 10.0
        alt_m = (target_gsd_mm * profile.focal_length_mm * profile.image_width_px) / (
            1000.0 * profile.sensor_width_mm
        )

        footprint_w, footprint_h = profile.calculate_footprint(alt_m)
        spacing_m = footprint_h * 0.25  # 75% overlap for re-fly (tighter)

        waypoints = plan_adaptive_boustrophedon(target_polygon, alt_m, spacing_m)

        if len(waypoints) < 2:
            return None

        # Estimate flight time
        dist_m = 0.0
        for i in range(len(waypoints) - 1):
            dx = (waypoints[i + 1].lon - waypoints[i].lon) * 85000.0
            dy = (waypoints[i + 1].lat - waypoints[i].lat) * 111000.0
            dist_m += (dx ** 2 + dy ** 2) ** 0.5

        est_time_min = (dist_m / profile.max_speed_m_s) / 60.0
        est_images = max(1, int((dist_m / profile.max_speed_m_s) / 2.0))

        plan = FlightPlan(
            plan_id=f"refly_{uuid.uuid4().hex[:8]}",
            intent_id=f"refly_{plot_id}",
            drone_profile=profile.name,
            pattern=CoveragePattern.BOUSTROPHEDON,
            waypoints=waypoints,
            estimated_flight_time_min=est_time_min,
            estimated_image_count=est_images,
            achieved_gsd_cm=target_gsd,
            flight_altitude_m=alt_m,
        )

        # Feasibility check
        intent = MissionIntent(
            intent_id=plan.intent_id,
            plot_id=plot_id,
            mission_type=MissionType.REFLY_WEAK_ZONES,
            flight_mode=FlightMode.MAPPING_MODE,
            polygon_geojson=target_polygon,
            target_gsd_cm=target_gsd,
        )
        is_feasible, reason = check_feasibility(intent, plan, profile)
        plan.is_feasible = is_feasible
        plan.infeasibility_reason = reason if not is_feasible else None

        return plan

    def _build_target_polygon(
        self,
        zones: List[WeakZone],
        full_polygon: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a target polygon from zone bounding boxes.
        
        Merges all zone bboxes into a single enclosing bbox, then
        creates a rectangular polygon from it.
        If no zones have bboxes, returns the full plot polygon.
        """
        bboxes = [z.zone_bbox for z in zones if z.zone_bbox]
        if not bboxes:
            return full_polygon

        # Merge: take the union bounding box of all zones
        min_lat = min(b.get("min_lat", 999) for b in bboxes)
        max_lat = max(b.get("max_lat", -999) for b in bboxes)
        min_lon = min(b.get("min_lon", 999) for b in bboxes)
        max_lon = max(b.get("max_lon", -999) for b in bboxes)

        # Sanity check: if merged bbox covers > 80% of full polygon, just use full
        full_coords = full_polygon.get("coordinates", [[]])[0]
        if len(full_coords) >= 3:
            full_lats = [p[1] for p in full_coords]
            full_lons = [p[0] for p in full_coords]
            full_lat_range = max(full_lats) - min(full_lats)
            full_lon_range = max(full_lons) - min(full_lons)

            if full_lat_range > 0 and full_lon_range > 0:
                sub_area = (max_lat - min_lat) * (max_lon - min_lon)
                full_area = full_lat_range * full_lon_range
                if full_area > 0 and sub_area / full_area > 0.80:
                    return full_polygon

        # Build rectangular polygon from merged bbox
        return {
            "type": "Polygon",
            "coordinates": [[
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]]
        }
