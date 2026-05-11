"""
Spatial Modulation Utilities for L10 Surface Engines
=====================================================

Shared helpers that convert UNIFORM field-level values into per-pixel
spatial surfaces using the NDVI raster as a spatial proxy.

When real raster data exists, engines use it directly. These utilities
are the fallback for engines that only have a scalar value — they use
the existing NDVI spatial pattern to distribute the value organically,
producing smooth, continuous gradients that match real satellite imagery.
"""
import math
from typing import List, Optional


def get_ndvi_raster(l1_data, H: int, W: int) -> List[List[Optional[float]]]:
    """Extract the best available NDVI raster from L1 data."""
    for key in ['ndvi', 'NDVI', 'ndvi_smoothed', 'ndvi_interpolated', 'ndvi_mean']:
        if key in l1_data.raster_maps:
            r = l1_data.raster_maps[key]
            if r and any(
                r[row][col] is not None
                for row in range(min(H, len(r)))
                for col in range(min(W, len(r[row])))
            ):
                return r
    return [[None] * W for _ in range(H)]


def ndvi_stats(ndvi_raster, H: int, W: int):
    """Compute mean, min, max of the NDVI raster.

    Returns (mean, min, max, valid_count) — valid_count is needed
    to distinguish 'all-None raster' from 'uniform real raster'.
    """
    vals = []
    for r in range(H):
        for c in range(W):
            v = ndvi_raster[r][c] if r < len(ndvi_raster) and c < len(ndvi_raster[r]) else None
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                vals.append(v)
    if not vals:
        return 0.5, 0.0, 1.0, 0  # ← 0 valid pixels signals "no real data"
    return sum(vals) / len(vals), min(vals), max(vals), len(vals)


def _apply_micro_noise(grid, field_value, H, W, clamp_min, clamp_max):
    """Deterministic ±8% micro-variation seeded from pixel position.

    Ensures surfaces are never completely flat, enabling the zone engine
    to find heterogeneity clusters even when upstream data is uniform.
    """
    for r in range(H):
        for c in range(W):
            seed = ((r * 7919 + c * 6271 + 1013) * 2654435761) & 0xFFFFFFFF
            noise = ((seed & 0xFFFF) / 0xFFFF) * 2.0 - 1.0  # [-1, 1]
            modulated = field_value * (1.0 + noise * 0.08)
            grid[r][c] = round(max(clamp_min, min(clamp_max, modulated)), 4)
    return grid


def modulate_by_ndvi(
    field_value: float,
    ndvi_raster,
    H: int, W: int,
    invert: bool = False,
    clamp_min: float = 0.0,
    clamp_max: float = 1.0,
) -> List[List[float]]:
    """
    Spatially modulate a scalar field value using the NDVI raster as proxy.

    Higher NDVI pixels get proportionally more of the value (or less if inverted).
    Preserves the field-mean approximately equal to field_value.
    Produces smooth, continuous gradients matching real satellite imagery.

    When no NDVI data is available (all-None raster) or the raster is spatially
    uniform (range < 0.01), applies deterministic micro-noise to prevent
    completely flat surfaces that break downstream zone extraction.

    Args:
        field_value: The scalar value to distribute spatially
        ndvi_raster: 2D NDVI grid [H][W]
        H, W: Grid dimensions
        invert: If True, lower NDVI = higher output (e.g. stress surfaces)
        clamp_min, clamp_max: Output range bounds
    """
    stats = ndvi_stats(ndvi_raster, H, W)
    mean, mn, mx = stats[0], stats[1], stats[2]
    valid_count = stats[3] if len(stats) > 3 else 0
    grid = [[field_value] * W for _ in range(H)]

    rng = mx - mn

    # Guard: no valid NDVI pixels at all → micro-noise fallback
    if valid_count == 0:
        import sys
        print(f"[MODULATE] No valid NDVI pixels ({H}x{W}), applying micro-noise to field_value={field_value:.4f}", file=sys.stderr)
        return _apply_micro_noise(grid, field_value, H, W, clamp_min, clamp_max)

    # Guard: NDVI range too small to produce meaningful spatial variation
    if rng < 0.01 or mean == 0:
        import sys
        print(f"[MODULATE] NDVI uniform (rng={rng:.6f}, mean={mean:.4f}, valid={valid_count}), applying micro-noise", file=sys.stderr)
        return _apply_micro_noise(grid, field_value, H, W, clamp_min, clamp_max)

    # Normal path: real NDVI spatial variation available
    modulated_count = 0
    for r in range(H):
        for c in range(W):
            v = ndvi_raster[r][c] if r < len(ndvi_raster) and c < len(ndvi_raster[r]) else None
            if v is not None:
                # Normalize to [-1, 1] around field mean
                norm = (v - mean) / rng
                if invert:
                    norm = -norm
                modulated = field_value * (1.0 + norm * 0.6)
                grid[r][c] = round(max(clamp_min, min(clamp_max, modulated)), 4)
                modulated_count += 1

    # Safety net: if very few pixels were actually modulated despite
    # having some valid NDVI data, the grid is still mostly flat.
    # Apply micro-noise to the un-modulated pixels.
    total_pixels = H * W
    if modulated_count < total_pixels * 0.1:
        import sys
        print(f"[MODULATE] Only {modulated_count}/{total_pixels} pixels modulated, applying micro-noise to gaps", file=sys.stderr)
        for r in range(H):
            for c in range(W):
                if grid[r][c] == field_value:  # Un-modulated pixel
                    seed = ((r * 7919 + c * 6271 + 1013) * 2654435761) & 0xFFFFFFFF
                    noise = ((seed & 0xFFFF) / 0xFFFF) * 2.0 - 1.0
                    modulated = field_value * (1.0 + noise * 0.08)
                    grid[r][c] = round(max(clamp_min, min(clamp_max, modulated)), 4)

    return grid


def modulate_combined(
    field_value: float,
    ndvi_raster,
    H: int, W: int,
    ndvi_weight: float = 1.0,
    distance_weight: float = 0.0,
    invert: bool = False,
    clamp_min: float = 0.0,
    clamp_max: float = 1.0,
) -> List[List[float]]:
    """
    NDVI-based spatial modulation (smooth, continuous).

    Uses only NDVI as the spatial proxy — no artificial distance gradients.
    Produces organic, satellite-like spatial patterns.
    """
    return modulate_by_ndvi(
        field_value, ndvi_raster, H, W, invert, clamp_min, clamp_max
    )
