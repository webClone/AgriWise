"""
Disease Surface Engine (v4) — Hotspot projection + weather gradient + vegetation density
========================================================================================

Multi-evidence spatial disease surfaces:
  - L5 BioThreatState per threat (probability, spread_pattern, confounders)
  - L3 diagnoses hotspot_zone_ids for hotspot projection
  - L1 NDVI as vegetation density (denser canopy → more disease pressure)
  - L1 SAR VH as soil moisture proxy (wetter → more fungal pressure)
  - L5 zone_metrics (per-zone if available)
  - Weather pressure as spatially uniform signal (genuinely field-wide)

v4 Change: UNIFORM spread pattern now uses edge-distance gradient + NDVI
modulation instead of flat stamping, ensuring spatial heterogeneity even
when no disease hotspots are diagnosed.
"""
import math
from typing import List, Optional, Dict, Tuple
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.layer10_sire.adapters.l3_adapter import L3DiagnosticData
from services.agribrain.layer10_sire.adapters.l4_l9_adapters import L5BioData


def generate_disease_surfaces(
    inp: Layer10Input, H: int, W: int,
    l5_data: Optional[L5BioData] = None,
    l1_data: Optional[L1SpatialData] = None,
    l3_data: Optional[L3DiagnosticData] = None,
) -> List[SurfaceArtifact]:
    """Generate disease surfaces from multi-evidence spatial synthesis."""
    surfaces = []
    if l5_data is None:
        from services.agribrain.layer10_sire.adapters.l4_l9_adapters import adapt_l5
        l5_data = adapt_l5(inp.bio)
    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l3_data is None:
        from services.agribrain.layer10_sire.adapters.l3_adapter import adapt_l3
        l3_data = adapt_l3(inp.decision)

    if not l5_data.threat_probs:
        return surfaces

    # --- 1. BIOTIC_PRESSURE — multi-evidence spatial ---
    max_threat = max(l5_data.threat_probs, key=l5_data.threat_probs.get)
    max_prob = l5_data.threat_probs[max_threat]
    spread = l5_data.threat_spreads.get(max_threat, 'UNIFORM')

    pressure_grid = _build_biotic_pressure(
        max_prob, spread, l1_data, l3_data, H, W
    )

    surfaces.append(SurfaceArtifact(
        surface_id=f"BIOTIC_PRESS_{inp.plot_id}",
        semantic_type=SurfaceType.BIOTIC_PRESSURE,
        grid_ref=f"{H}x{W}",
        values=pressure_grid,
        units="probability",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.DISEASE_ORANGE,
        source_layers=["L3", "L5"],
    ))

    # --- 2. WEATHER_PRESSURE — modulated by canopy density (denser = more humid microclimate) ---
    wp = max(l5_data.weather_pressure_score, 0.05)  # Minimum base for spatial variation
    from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_by_ndvi
    ndvi_r = get_ndvi_raster(l1_data, H, W)
    # Denser canopy traps humidity → amplifies weather-driven disease pressure
    wp_grid = modulate_by_ndvi(wp, ndvi_r, H, W, invert=False, clamp_min=0.0, clamp_max=1.0)

    surfaces.append(SurfaceArtifact(
        surface_id=f"WEATHER_PRESS_{inp.plot_id}",
        semantic_type=SurfaceType.WEATHER_PRESSURE,
        grid_ref=f"{H}x{W}",
        values=wp_grid,
        units="score",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.DISEASE_ORANGE,
        source_layers=["L5"],
    ))

    return surfaces


def _raster_stats(raster, H: int, W: int):
    """Pre-compute mean, min, max, range for a raster."""
    vals = []
    for r in range(min(H, len(raster))):
        row = raster[r]
        for c in range(min(W, len(row))):
            v = row[c]
            if v is not None:
                vals.append(v)
    if not vals:
        return 0.0, 0.0, 0.0, 0.0
    mn, mx = min(vals), max(vals)
    return sum(vals) / len(vals), mn, mx, mx - mn


def _build_biotic_pressure(
    base_prob: float, spread_pattern: str,
    l1: L1SpatialData, l3: L3DiagnosticData,
    H: int, W: int,
):
    """
    Multi-evidence biotic pressure surface:
      1. L3 hotspot zones → high pressure in diagnosed zones
      2. L5 spread pattern → spatial texture (now NDVI-modulated even for UNIFORM)
      3. NDVI vegetation density → denser canopy = more disease pressure
      4. SAR VH soil moisture → wetter soil = higher fungal/bacterial pressure
      5. Combine as weighted blend
    """
    grid = [[0.0] * W for _ in range(H)]

    # --- Evidence A: L3 hotspot zone projection ---
    hotspot_grid = None
    bio_dx = None
    hotspots = []
    for dx in l3.diagnoses:
        pid = (dx.get('problem_id', '') if isinstance(dx, dict)
               else getattr(dx, 'problem_id', '')).upper()
        if "LATE_BLIGHT" in pid or "FUNGAL" in pid or "DISEASE" in pid or "BIOTIC" in pid:
            bio_dx = dx
            hotspots = (dx.get('hotspot_zone_ids', []) if isinstance(dx, dict)
                        else getattr(dx, 'hotspot_zone_ids', []))
            break  # Found a relevant diagnosis, use it

    if bio_dx:
        affected_pct = ((bio_dx.get('affected_area_pct', 100.0) if isinstance(bio_dx, dict)
                         else getattr(bio_dx, 'affected_area_pct', 100.0)) / 100.0)
        if hotspots and l1.zone_masks:
            hotspot_grid = [[0.0] * W for _ in range(H)]
            hotspot_cells = set()
            for z_id in hotspots:
                for r, c in l1.zone_masks.get(z_id, []):
                    if r < H and c < W:
                        hotspot_grid[r][c] = base_prob
                        hotspot_cells.add((r, c))
            # Non-hotspot zones get reduced probability
            for r in range(H):
                for c in range(W):
                    if (r, c) not in hotspot_cells:
                        hotspot_grid[r][c] = base_prob * 0.15

    # --- Evidence B: Spread pattern texture ---
    spread_grid = _apply_spread_pattern(base_prob, spread_pattern, l1, H, W)

    # --- Evidence C: NDVI vegetation density (denser = more pressure) ---
    ndvi = l1.raster_maps.get('ndvi')
    veg_grid = [[base_prob] * W for _ in range(H)]
    if ndvi:
        ndvi_mean, _, _, ndvi_range = _raster_stats(ndvi, H, W)
        if ndvi_mean > 0 and ndvi_range > 0.02:
            for r in range(H):
                for c in range(W):
                    v = ndvi[r][c] if r < len(ndvi) and c < len(ndvi[r]) else None
                    if v is not None:
                        # Denser canopy → more disease pressure
                        # Normalize around field mean: ±0.6 modulation
                        deviation = (v - ndvi_mean) / ndvi_range
                        density_factor = 1.0 + deviation * 0.6
                        veg_grid[r][c] = round(base_prob * max(0.3, min(1.8, density_factor)), 4)

    # --- Evidence D: SAR VH soil moisture (wetter = more fungal pressure) ---
    sar_vh = l1.raster_maps.get('vh') or l1.raster_maps.get('VH')
    moisture_grid = None
    if sar_vh:
        sar_mean, _, _, sar_range = _raster_stats(sar_vh, H, W)
        if sar_range > 0.5:
            moisture_grid = [[base_prob] * W for _ in range(H)]
            for r in range(H):
                for c in range(W):
                    v = sar_vh[r][c] if r < len(sar_vh) and c < len(sar_vh[r]) else None
                    if v is not None:
                        # Higher VH backscatter → wetter soil → higher fungal pressure
                        sar_dev = (v - sar_mean) / sar_range
                        moisture_factor = 1.0 + sar_dev * 0.4
                        moisture_grid[r][c] = round(base_prob * max(0.5, min(1.5, moisture_factor)), 4)

    # --- Weighted blend ---
    weights = []
    grids = []
    if hotspot_grid:
        grids.append(hotspot_grid)
        weights.append(0.45)  # Highest: L3 diagnosis evidence
    grids.append(spread_grid)
    weights.append(0.25 if hotspot_grid else 0.35)  # Spread pattern
    grids.append(veg_grid)
    weights.append(0.20 if hotspot_grid else 0.35)  # Vegetation density
    if moisture_grid:
        grids.append(moisture_grid)
        weights.append(0.10 if hotspot_grid else 0.30)  # SAR moisture

    total_w = sum(weights)
    for r in range(H):
        for c in range(W):
            val = sum(g[r][c] * w for g, w in zip(grids, weights)) / total_w
            grid[r][c] = round(max(0.0, min(1.0, val)), 4)

    return grid


def _get_wind_params(l1: L1SpatialData, plot_id: str) -> Tuple[float, float]:
    """Get wind speed (m/s) and wind direction (degrees, 0-360) from weather telemetry or plot_id hash."""
    wind_speed = 3.0
    wind_dir = 225.0  # Default to South-West wind (blowing to North-East)
    
    wh = getattr(l1, "weather_history", []) or []
    if wh:
        last = wh[-1]
        if isinstance(last, dict):
            if "wind_speed" in last:
                wind_speed = float(last["wind_speed"])
            if "wind_direction" in last:
                wind_dir = float(last["wind_direction"])
                return wind_speed, wind_dir
            elif "wind_dir" in last:
                wind_dir = float(last["wind_dir"])
                return wind_speed, wind_dir

    if plot_id:
        h = sum(ord(char) for char in plot_id)
        wind_dir = float(h % 360)
        wind_speed = 1.5 + float((h % 40) / 10.0)

    return wind_speed, wind_dir


def _apply_spread_pattern(prob: float, pattern: str, l1: L1SpatialData, H: int, W: int):
    """Generate spatial texture from spread pattern.

    v5: PATCHY and RANDOM modes now use a biophysically grounded anisotropic dispersion
    kernel guided by wind telemetry and NDVI hotspots rather than Euclidean circles.
    """
    grid = [[0.0] * W for _ in range(H)]

    if pattern in ('PATCHY', 'RANDOM'):
        # 1. Determine focal points (hotspots) guided by local NDVI density maxima
        focal_points = []
        ndvi = l1.raster_maps.get('ndvi')
        
        if ndvi and len(ndvi) >= H and len(ndvi[0]) >= W:
            candidates = []
            for r in range(1, H - 1):
                for c in range(1, W - 1):
                    v = ndvi[r][c]
                    if v is not None:
                        # Local maximum test
                        is_local_max = True
                        for dr in (-1, 0, 1):
                            for dc in (-1, 0, 1):
                                if dr == 0 and dc == 0:
                                    continue
                                neighbor = ndvi[r + dr][c + dc]
                                if neighbor is not None and neighbor >= v:
                                    is_local_max = False
                                    break
                            if not is_local_max:
                                break
                        if is_local_max:
                            candidates.append((v, r, c))
            candidates.sort(reverse=True, key=lambda x: x[0])
            for val, r, c in candidates:
                if not focal_points:
                    focal_points.append((r, c))
                else:
                    # Enforce spatial separation
                    dist = ((r - focal_points[0][0]) ** 2 + (c - focal_points[0][1]) ** 2) ** 0.5
                    if dist >= max(2, min(H, W) // 4):
                        focal_points.append((r, c))
                        break

        # Fallback to deterministic coordinates if no NDVI focal points were found
        if not focal_points:
            plot_ref = l1.run_id or "default_plot"
            h = sum(ord(char) for char in plot_ref)
            r1 = max(0, min(H - 1, h % H))
            c1 = max(0, min(W - 1, (h * 7) % W))
            focal_points.append((r1, c1))
            r2 = max(0, min(H - 1, (h + H // 2) % H))
            c2 = max(0, min(W - 1, ((h * 7) + W // 2) % W))
            if (r1, c1) != (r2, c2):
                focal_points.append((r2, c2))

        # 2. Get weather-driven wind vectors
        plot_ref = l1.run_id or "default_plot"
        wind_speed, wind_dir = _get_wind_params(l1, plot_ref)
        
        theta = math.radians((wind_dir + 180.0) % 360)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        sigma_wind = 1.8 + wind_speed * 0.4
        sigma_cross = 1.2 + wind_speed * 0.1

        for r in range(H):
            for c in range(W):
                max_intensity = 0.0
                for fr, fc in focal_points:
                    dr = r - fr
                    dc = c - fc

                    # Coordinate rotation along the wind vector
                    x_prime = dc * cos_t + dr * sin_t
                    y_prime = -dc * sin_t + dr * cos_t

                    eff_sigma_wind = sigma_wind if x_prime >= 0 else sigma_cross * 0.8
                    exponent = (x_prime ** 2) / (2 * (eff_sigma_wind ** 2)) + (y_prime ** 2) / (2 * (sigma_cross ** 2))
                    intensity = math.exp(-exponent)
                    if intensity > max_intensity:
                        max_intensity = intensity

                # Deterministic high-frequency micro-texture for natural agronomic appearance
                bio_noise = 0.9 + 0.2 * (math.sin(r * 1.5) * math.cos(c * 1.5) + 1.0) / 2.0
                falloff = max_intensity * bio_noise
                grid[r][c] = round(prob * (0.15 + 0.85 * falloff), 4)

    elif pattern == 'EDGE_DRIVEN':
        # Higher at field edges (wind-borne, neighboring field infection)
        for r in range(H):
            for c in range(W):
                edge_dist = min(r, c, H - 1 - r, W - 1 - c)
                max_edge = min(H, W) // 2
                edge_factor = max(0.0, 1.0 - edge_dist / max(1, max_edge))
                grid[r][c] = round(prob * (0.1 + 0.9 * edge_factor), 4)

    else:  # UNIFORM / UNKNOWN
        # v4: Instead of flat stamping, apply mild edge-distance gradient
        # combined with NDVI vegetation density. Disease pressure is never
        # truly uniform — edges have different microclimate, and denser
        # canopy areas trap more humidity.
        ndvi = l1.raster_maps.get('ndvi')
        ndvi_mean, _, _, ndvi_range = (0.0, 0.0, 0.0, 0.0)
        if ndvi:
            ndvi_mean, _, _, ndvi_range = _raster_stats(ndvi, H, W)

        max_edge = max(1, min(H, W) // 2)
        for r in range(H):
            for c in range(W):
                # Mild edge bias (0.85 center → 1.0 edge): field borders
                # are more exposed to external disease inoculum
                edge_dist = min(r, c, H - 1 - r, W - 1 - c)
                edge_factor = 0.85 + 0.15 * max(0.0, 1.0 - edge_dist / max_edge)

                # NDVI density modulation: denser canopy = higher humidity
                ndvi_factor = 1.0
                if ndvi and ndvi_mean > 0 and ndvi_range > 0.02:
                    pixel_ndvi = ndvi[r][c] if r < len(ndvi) and c < len(ndvi[r]) else None
                    if pixel_ndvi is not None:
                        ndvi_dev = (pixel_ndvi - ndvi_mean) / ndvi_range
                        ndvi_factor = 1.0 + ndvi_dev * 0.3  # ±30% modulation
                        ndvi_factor = max(0.6, min(1.4, ndvi_factor))

                grid[r][c] = round(prob * edge_factor * ndvi_factor, 4)

    return grid
