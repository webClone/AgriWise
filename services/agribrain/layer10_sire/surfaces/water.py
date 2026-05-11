"""
Water Surface Engine (v3) — Multi-Source Spatial Water Stress
==============================================================

Generates the WATER_STRESS_PROB surface using REAL moisture indicators
rather than inverted NDVI proxy.

Data source priority for spatial distribution:
  1. NDMI raster (Normalized Difference Moisture Index) — direct canopy water
  2. SAR VV backscatter — soil surface moisture proxy
  3. IoT soil moisture sensors (if available via L1)
  4. Soil Water Balance Ks coefficient (from L4, zone-level)
  5. NDVI spatial modulation (LAST RESORT fallback only)

The L3 diagnostic probability anchors the field-level mean;
spatial sources distribute that probability across pixels.
"""
import logging
import sys
from typing import List, Optional, Tuple
from layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId, GroundingClass,
)
from layer10_sire.adapters.l1_adapter import L1SpatialData
from layer10_sire.adapters.l3_adapter import L3DiagnosticData

logger = logging.getLogger(__name__)


def generate_water_surfaces(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
    l3_data: Optional[L3DiagnosticData] = None,
) -> List[SurfaceArtifact]:
    """Generate water surfaces from L1/L3 adapter data (multi-source spatial)."""
    surfaces = []
    if l1_data is None:
        from layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l3_data is None:
        from layer10_sire.adapters.l3_adapter import adapt_l3
        l3_data = adapt_l3(inp.decision)

    # --- 1. WATER_STRESS_PROB — multi-source spatial ---
    stress_grid, grounding, source_layers = _compute_spatial_water_stress(
        inp, l1_data, l3_data, H, W
    )
    surfaces.append(SurfaceArtifact(
        surface_id=f"WATER_STRESS_{inp.plot_id}",
        semantic_type=SurfaceType.WATER_STRESS_PROB,
        grid_ref=f"{H}x{W}",
        values=stress_grid,
        units="probability",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.STRESS_RED,
        source_layers=source_layers,
        grounding_class=grounding,
    ))

    # --- 2. DROUGHT_ACCUMULATION — from L1 precipitation ---
    drought_grid = _compute_spatial_drought(l1_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"DROUGHT_{inp.plot_id}",
        semantic_type=SurfaceType.DROUGHT_ACCUMULATION,
        grid_ref=f"{H}x{W}",
        values=drought_grid,
        units="days",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 30.0),
        palette_id=PaletteId.STRESS_RED,
        source_layers=["L1"],
    ))

    return surfaces


# ============================================================================
# RASTER EXTRACTION HELPERS
# ============================================================================

def _get_raster(l1: L1SpatialData, keys: list, H: int, W: int):
    """Try multiple key names to find a raster in L1, return (raster, key) or (None, None)."""
    for key in keys:
        r = l1.raster_maps.get(key)
        if r and _has_valid_pixels(r, H, W):
            return r, key
    return None, None


def _has_valid_pixels(raster, H: int, W: int, min_fraction: float = 0.1) -> bool:
    """Check if a raster has enough valid (non-None) pixels."""
    total = 0
    valid = 0
    for r in range(min(H, len(raster))):
        for c in range(min(W, len(raster[r]))):
            total += 1
            if raster[r][c] is not None:
                valid += 1
    return total > 0 and (valid / total) >= min_fraction


def _raster_stats(raster, H: int, W: int) -> Tuple[float, float, float]:
    """Compute mean, min, max of a raster (ignoring None)."""
    vals = []
    for r in range(min(H, len(raster))):
        for c in range(min(W, len(raster[r]))):
            v = raster[r][c]
            if v is not None:
                vals.append(v)
    if not vals:
        return 0.5, 0.0, 1.0
    return sum(vals) / len(vals), min(vals), max(vals)


# ============================================================================
# CORE: MULTI-SOURCE SPATIAL WATER STRESS
# ============================================================================

def _compute_spatial_water_stress(
    inp: Layer10Input,
    l1: L1SpatialData,
    l3: L3DiagnosticData,
    H: int, W: int
) -> Tuple[list, str, list]:
    """
    Compute the WATER_STRESS_PROB surface using real moisture rasters.

    Returns: (grid, grounding_class, source_layers)
    """
    # --- Step 1: Extract L3 diagnostic probability (field-level anchor) ---
    base_prob, affected_pct, hotspot_zones = _extract_l3_water_diagnosis(l3)
    print(f"[WATER] L3 anchor: base_prob={base_prob:.4f}, affected_pct={affected_pct:.2f}, hotspots={len(hotspot_zones)}", file=sys.stderr)

    # --- Step 2: Try hotspot zones first (best spatial precision) ---
    if hotspot_zones and l1.zone_masks:
        grid = _strategy_hotspot_zones(base_prob, hotspot_zones, l1, H, W)
        if grid:
            print("[WATER] Strategy A: Hotspot zones (zone-grounded)", file=sys.stderr)
            return grid, GroundingClass.ZONE_GROUNDED.value, ["L1", "L3"]

    # --- Step 3: Build composite moisture raster from real indicators ---
    moisture_grid, sources_used = _build_composite_moisture(l1, inp, H, W)

    if moisture_grid:
        # Anchor composite to L3 diagnostic probability
        grid = _anchor_to_diagnosis(moisture_grid, base_prob, affected_pct, H, W)
        grounding = GroundingClass.RASTER_GROUNDED.value
        src = ["L1", "L3"] + sources_used
        print(f"[WATER] Strategy B: Composite moisture ({', '.join(sources_used)})", file=sys.stderr)
        # Log composite output stats
        comp_vals = [v for row in grid for v in row if v is not None]
        if comp_vals:
            print(f"[WATER] Composite grid: mean={sum(comp_vals)/len(comp_vals):.4f}, min={min(comp_vals):.4f}, max={max(comp_vals):.4f}, unique={len(set(round(v,4) for v in comp_vals))}", file=sys.stderr)
        return grid, grounding, src

    # --- Step 4: NDVI fallback (last resort) ---
    print("[WATER] Strategy C: NDVI proxy fallback (no real moisture data)", file=sys.stderr)
    print(f"[WATER] L1 raster_maps keys: {list(l1.raster_maps.keys())}", file=sys.stderr)
    from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_by_ndvi, ndvi_stats
    ndvi_r = get_ndvi_raster(l1, H, W)
    mean, mn, mx, valid_count = ndvi_stats(ndvi_r, H, W)
    print(f"[WATER] NDVI stats: mean={mean:.4f}, min={mn:.4f}, max={mx:.4f}, range={mx-mn:.4f}, valid_pixels={valid_count}", file=sys.stderr)
    grid = modulate_by_ndvi(
        base_prob if base_prob > 0 else 0.15,
        ndvi_r, H, W, invert=True, clamp_min=0.0, clamp_max=0.8
    )
    # Log output stats
    vals = [v for row in grid for v in row if v is not None]
    if vals:
        print(f"[WATER] Output grid: mean={sum(vals)/len(vals):.4f}, min={min(vals):.4f}, max={max(vals):.4f}, unique={len(set(round(v,4) for v in vals))}", file=sys.stderr)
    return grid, GroundingClass.PROXY_SPATIAL.value, ["L1", "L3"]


def _extract_l3_water_diagnosis(l3: L3DiagnosticData):
    """Extract water stress probability from L3 diagnoses."""
    stress_dx = None
    for dx in l3.diagnoses:
        pid = dx.get('problem_id', '') if isinstance(dx, dict) else getattr(dx, 'problem_id', '')
        pid_upper = pid.upper()
        if "WATER_STRESS" in pid_upper or "DROUGHT" in pid_upper:
            prob = dx.get('probability', 0.0) if isinstance(dx, dict) else getattr(dx, 'probability', 0.0)
            if stress_dx is None:
                stress_dx = dx
            else:
                prev_prob = stress_dx.get('probability', 0.0) if isinstance(stress_dx, dict) else getattr(stress_dx, 'probability', 0.0)
                if prob > prev_prob:
                    stress_dx = dx

    if stress_dx is None:
        return 0.15, 1.0, []  # Low baseline, no diagnosis

    if isinstance(stress_dx, dict):
        base_prob = stress_dx.get('probability', 0.0)
        affected_pct = stress_dx.get('affected_area_pct', 100.0) / 100.0
        hotspot_zones = stress_dx.get('hotspot_zone_ids', [])
    else:
        base_prob = getattr(stress_dx, 'probability', 0.0)
        affected_pct = getattr(stress_dx, 'affected_area_pct', 100.0) / 100.0
        hotspot_zones = getattr(stress_dx, 'hotspot_zone_ids', [])

    return base_prob, affected_pct, hotspot_zones


def _strategy_hotspot_zones(base_prob, hotspot_zones, l1, H, W):
    """Strategy A: Zone-grounded stress from L3 hotspot zones.

    Falls through (returns None) when hotspot zones cover >= 90% of the field,
    since field-wide coverage means there's no spatial contrast between zones.
    Strategy B/C will handle those cases with better spatial differentiation.
    """
    hotspot_cells = set()
    for z_id in hotspot_zones:
        for r, c in l1.zone_masks.get(z_id, []):
            if r < H and c < W:
                hotspot_cells.add((r, c))

    if not hotspot_cells:
        return None

    # If hotspots cover >= 90% of the grid, the stress is field-wide.
    # Fall through to Strategy B/C for better spatial differentiation.
    total_pixels = H * W
    coverage = len(hotspot_cells) / total_pixels if total_pixels > 0 else 0
    if coverage >= 0.9:
        print(f"[WATER] Strategy A skipped: hotspot coverage {coverage:.0%} (field-wide), deferring to B/C", file=sys.stderr)
        return None

    # Build zone grid with NDVI intra-zone modulation for spatial texture
    from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, ndvi_stats
    ndvi_r = get_ndvi_raster(l1, H, W)
    stats = ndvi_stats(ndvi_r, H, W)
    ndvi_mean = stats[0]
    ndvi_rng = stats[2] - stats[1]
    has_ndvi = stats[3] > 0 and ndvi_rng > 0.01

    grid = [[0.0] * W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            if (r, c) in hotspot_cells:
                val = base_prob
                # Add NDVI-based intra-zone modulation (±15%)
                if has_ndvi:
                    ndvi_v = ndvi_r[r][c] if r < len(ndvi_r) and c < len(ndvi_r[r]) else None
                    if ndvi_v is not None:
                        norm = (ndvi_v - ndvi_mean) / ndvi_rng
                        val = base_prob * (1.0 - norm * 0.15)  # Lower NDVI → higher stress
                else:
                    # No NDVI: deterministic micro-noise
                    seed = ((r * 7919 + c * 6271 + 1013) * 2654435761) & 0xFFFFFFFF
                    noise = ((seed & 0xFFFF) / 0xFFFF) * 2.0 - 1.0
                    val = base_prob * (1.0 + noise * 0.08)
                grid[r][c] = round(max(0.0, min(1.0, val)), 4)
            else:
                grid[r][c] = round(base_prob * 0.2, 4)
    return grid


# ============================================================================
# COMPOSITE MOISTURE BUILDER
# ============================================================================

def _build_composite_moisture(
    l1: L1SpatialData, inp: Layer10Input, H: int, W: int
) -> Tuple[Optional[list], list]:
    """
    Build a composite moisture index from all available real moisture rasters.

    Each source is normalized to [0, 1] where 1 = maximum stress.
    Sources are weighted and averaged.

    Returns: (composite_grid or None, list of source names used)
    """
    layers = []  # List of (weight, normalized_grid, source_name)

    # --- Source 1: NDMI (Normalized Difference Moisture Index) ---
    # NDMI directly measures canopy water content: high NDMI = wet, low = dry
    ndmi_raster, ndmi_key = _get_raster(l1, ['ndmi', 'NDMI', 'ndmi_interpolated', 'ndmi_mean'], H, W)
    if ndmi_raster:
        norm = _normalize_raster_to_stress(ndmi_raster, H, W, invert=True)
        layers.append((3.0, norm, "NDMI"))
        logger.info(f"[WATER] NDMI raster found ({ndmi_key}), weight=3.0")

    # --- Source 2: SAR VV backscatter (soil surface moisture proxy) ---
    # Lower VV backscatter in bare/sparse canopy = drier soil
    # Higher VV = wetter soil (in general, for bare/low vegetation)
    sar_raster, sar_key = _get_raster(l1, ['vv', 'VV', 'sar_vv'], H, W)
    if sar_raster:
        # SAR: higher backscatter = wetter soil = LESS stress → invert
        norm = _normalize_raster_to_stress(sar_raster, H, W, invert=True)
        layers.append((2.0, norm, "SAR-VV"))
        logger.info(f"[WATER] SAR VV raster found ({sar_key}), weight=2.0")

    # --- Source 3: IoT soil moisture (ground truth) ---
    # Check for IoT moisture readings that may have been injected into raster_maps
    iot_raster, iot_key = _get_raster(l1, ['soil_moisture', 'moisture', 'moisture_pct'], H, W)
    if iot_raster:
        # Higher moisture = less stress → invert
        norm = _normalize_raster_to_stress(iot_raster, H, W, invert=True)
        layers.append((4.0, norm, "IoT-Moisture"))  # Highest weight: ground truth
        logger.info(f"[WATER] IoT moisture raster found ({iot_key}), weight=4.0")

    # --- Source 4: L4 Soil Water Balance (zone-level Ks) ---
    # Check if we have SWB water_stress_index from L4 via nutrients layer
    swb_grid = _extract_swb_stress(inp, l1, H, W)
    if swb_grid:
        layers.append((2.5, swb_grid, "SWB-Ks"))
        logger.info("[WATER] SWB water_stress_index found, weight=2.5")

    if not layers:
        return None, []

    # --- Weighted composite ---
    composite = [[0.0] * W for _ in range(H)]
    total_weight = sum(w for w, _, _ in layers)

    for r in range(H):
        for c in range(W):
            weighted_sum = 0.0
            pixel_weight = 0.0
            for weight, grid, _ in layers:
                v = grid[r][c]
                if v is not None:
                    weighted_sum += v * weight
                    pixel_weight += weight

            if pixel_weight > 0:
                composite[r][c] = round(weighted_sum / pixel_weight, 4)
            else:
                composite[r][c] = None

    sources_used = [name for _, _, name in layers]
    return composite, sources_used


def _normalize_raster_to_stress(
    raster, H: int, W: int, invert: bool = False
) -> list:
    """
    Normalize a raster to [0, 1] stress scale using min-max stretch.

    If invert=True, higher raw values → LOWER stress (e.g., NDMI, moisture).
    When the raster has no spatial range (uniform), returns 0.5 (indeterminate stress).
    """
    mean, mn, mx = _raster_stats(raster, H, W)
    rng = mx - mn

    grid = [[None] * W for _ in range(H)]
    if rng < 1e-6:
        # Uniform raster: return 0.5 (neutral/indeterminate stress) for all valid pixels
        for r in range(min(H, len(raster))):
            for c in range(min(W, len(raster[r]))):
                if raster[r][c] is not None:
                    grid[r][c] = 0.5
        return grid

    for r in range(min(H, len(raster))):
        for c in range(min(W, len(raster[r]))):
            v = raster[r][c]
            if v is not None:
                normalized = max(0.0, min(1.0, (v - mn) / rng))
                if invert:
                    normalized = 1.0 - normalized
                grid[r][c] = round(normalized, 4)
    return grid


def _anchor_to_diagnosis(
    composite_grid: list, base_prob: float, affected_pct: float, H: int, W: int
) -> list:
    """
    Rescale the composite moisture grid so its mean matches the L3 diagnostic
    probability, preserving the spatial variation from real sensors.

    This ensures the map values are physically meaningful probabilities
    while the spatial pattern comes from real moisture measurements.
    """
    # Compute current composite mean
    vals = []
    for r in range(H):
        for c in range(W):
            v = composite_grid[r][c]
            if v is not None:
                vals.append(v)

    if not vals:
        return composite_grid

    comp_mean = sum(vals) / len(vals)
    target_mean = base_prob * affected_pct

    # Scale factor to shift composite mean to match L3 probability
    if comp_mean > 1e-6:
        scale = target_mean / comp_mean
    else:
        scale = 1.0

    grid = [[None] * W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            v = composite_grid[r][c]
            if v is not None:
                scaled = v * scale
                grid[r][c] = round(max(0.0, min(1.0, scaled)), 4)

    return grid


def _extract_swb_stress(inp: Layer10Input, l1: L1SpatialData, H: int, W: int):
    """
    Extract Soil Water Balance stress index from L4 nutrients output.
    Returns a zone-rasterized grid if available, else None.
    """
    nutrients = inp.nutrients
    if nutrients is None:
        return None

    # Try to get SWB output from nutrients
    swb = getattr(nutrients, 'soil_water_balance', None)
    if swb is None:
        return None

    wsi = getattr(swb, 'water_stress_index', None)
    if wsi is None or wsi <= 0:
        return None

    # SWB is field-level. Distribute using zone structure if available.
    if l1.zone_masks:
        grid = [[None] * W for _ in range(H)]
        filled = False
        for z_id, cells in l1.zone_masks.items():
            for r, c in cells:
                if r < H and c < W:
                    grid[r][c] = round(float(wsi), 4)
                    filled = True
        if filled:
            return grid

    # Broadcast as uniform if no zone masks
    return [[round(float(wsi), 4)] * W for _ in range(H)]


# ============================================================================
# DROUGHT ACCUMULATION (unchanged)
# ============================================================================

def _compute_spatial_drought(l1: L1SpatialData, H: int, W: int):
    """Compute trailing dry days — spatial if precipitation raster exists."""
    precip_ts = l1.last_values.get('precipitation')
    dry_days = 0

    # Try zone-level precipitation
    if 'precipitation' in l1.zone_timeseries:
        zone_droughts = {}
        for z_id, ts in l1.zone_timeseries['precipitation'].items():
            dd = 0
            for p in reversed(ts):
                if p > 2.0:
                    break
                dd += 1
            zone_droughts[z_id] = float(dd)

        if zone_droughts and l1.zone_masks:
            grid = [[0.0] * W for _ in range(H)]
            for z_id, cells in l1.zone_masks.items():
                dd = zone_droughts.get(z_id, 0.0)
                for r, c in cells:
                    if r < H and c < W:
                        grid[r][c] = dd
            return grid

    # Fallback: spatially modulated using NDVI (low NDVI = more drought exposure)
    from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_by_ndvi
    ndvi_r = get_ndvi_raster(l1, H, W)
    return modulate_by_ndvi(max(float(dry_days), 3.0), ndvi_r, H, W, invert=True, clamp_min=0.0, clamp_max=30.0)
