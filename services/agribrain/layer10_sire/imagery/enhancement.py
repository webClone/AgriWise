"""
Image Enhancement Pipeline — CLAHE, saturation, tone mapping
=============================================================

Purely algorithmic enhancement for rendering surfaces as images.
Works on surface value grids (not RGB images).
"""
from typing import List, Optional, Dict, Any
from layer10_sire.schema import SurfaceArtifact


def enhance_surface(
    surface: SurfaceArtifact,
    H: int, W: int,
    contrast: float = 1.0,
    saturation: float = 1.0,
    brightness: float = 1.0,
    gamma: float = 1.0,
    clahe_clip: float = 0.0,
) -> List[List[float]]:
    """
    Apply enhancement to surface values for rendering.

    Returns normalized [0, 1] enhanced grid ready for colormapping.
    """
    # Step 1: Extract and normalize values to [0, 1]
    vals = []
    for r in range(min(H, len(surface.values))):
        for c in range(min(W, len(surface.values[r]))):
            v = surface.values[r][c]
            if v is not None:
                vals.append(v)

    if not vals:
        return [[0.5] * W for _ in range(H)]

    lo, hi = surface.render_range if surface.render_range else (min(vals), max(vals))
    span = hi - lo if hi != lo else 1.0

    norm = [[0.5] * W for _ in range(H)]
    for r in range(min(H, len(surface.values))):
        for c in range(min(W, len(surface.values[r]))):
            v = surface.values[r][c]
            if v is not None:
                norm[r][c] = max(0.0, min(1.0, (v - lo) / span))
            else:
                norm[r][c] = 0.5

    # Step 2: CLAHE-like local contrast enhancement
    if clahe_clip > 0:
        norm = _apply_clahe(norm, H, W, clahe_clip)

    # Step 3: Gamma correction
    if gamma != 1.0:
        for r in range(H):
            for c in range(W):
                norm[r][c] = norm[r][c] ** (1.0 / gamma)

    # Step 4: Contrast adjustment (stretch around 0.5)
    if contrast != 1.0:
        for r in range(H):
            for c in range(W):
                norm[r][c] = max(0.0, min(1.0, 0.5 + (norm[r][c] - 0.5) * contrast))

    # Step 5: Brightness adjustment
    if brightness != 1.0:
        for r in range(H):
            for c in range(W):
                norm[r][c] = max(0.0, min(1.0, norm[r][c] * brightness))

    return norm


def _apply_clahe(grid, H, W, clip_limit, tile_size=4):
    """Contrast-Limited Adaptive Histogram Equalization (simplified)."""
    result = [row[:] for row in grid]

    for tile_r in range(0, H, tile_size):
        for tile_c in range(0, W, tile_size):
            # Collect tile values
            tile_vals = []
            for r in range(tile_r, min(tile_r + tile_size, H)):
                for c in range(tile_c, min(tile_c + tile_size, W)):
                    tile_vals.append(grid[r][c])

            if not tile_vals:
                continue

            # Build local histogram
            bins = 16
            hist = [0] * bins
            for v in tile_vals:
                idx = min(int(v * bins), bins - 1)
                hist[idx] += 1

            # Clip histogram
            total = len(tile_vals)
            clip_threshold = max(1, int(total / bins * clip_limit))
            excess = 0
            for i in range(bins):
                if hist[i] > clip_threshold:
                    excess += hist[i] - clip_threshold
                    hist[i] = clip_threshold

            # Redistribute excess
            per_bin = excess // bins
            for i in range(bins):
                hist[i] += per_bin

            # Build CDF
            cdf = [0.0] * bins
            cdf[0] = hist[0]
            for i in range(1, bins):
                cdf[i] = cdf[i - 1] + hist[i]
            cdf_min = cdf[0]
            cdf_max = cdf[-1]

            # Apply equalization
            for r in range(tile_r, min(tile_r + tile_size, H)):
                for c in range(tile_c, min(tile_c + tile_size, W)):
                    v = grid[r][c]
                    idx = min(int(v * bins), bins - 1)
                    if cdf_max > cdf_min:
                        result[r][c] = (cdf[idx] - cdf_min) / (cdf_max - cdf_min)
                    else:
                        result[r][c] = v

    return result


def generate_false_color(
    band_r: List[List[Optional[float]]],
    band_g: List[List[Optional[float]]],
    band_b: List[List[Optional[float]]],
    H: int, W: int,
) -> List[List[Dict[str, int]]]:
    """
    Generate false-color composite from 3 bands.

    Typical agronomic combos:
      - NIR, Red, Green → CIR (Color Infrared)
      - NDVI, NDWI, NDMI → Moisture-Vegetation
    """
    image = [[{"r": 0, "g": 0, "b": 0}] * W for _ in range(H)]

    # Find ranges for each band
    def _range(band):
        vals = [band[r][c] for r in range(H) for c in range(W) if band[r][c] is not None]
        if not vals:
            return 0.0, 1.0
        return min(vals), max(vals)

    r_lo, r_hi = _range(band_r)
    g_lo, g_hi = _range(band_g)
    b_lo, b_hi = _range(band_b)

    for r in range(H):
        for c in range(W):
            vr = band_r[r][c] if band_r[r][c] is not None else 0.0
            vg = band_g[r][c] if band_g[r][c] is not None else 0.0
            vb = band_b[r][c] if band_b[r][c] is not None else 0.0

            # Normalize to [0, 255]
            rv = int(max(0, min(255, (vr - r_lo) / max(0.001, r_hi - r_lo) * 255)))
            gv = int(max(0, min(255, (vg - g_lo) / max(0.001, g_hi - g_lo) * 255)))
            bv = int(max(0, min(255, (vb - b_lo) / max(0.001, b_hi - b_lo) * 255)))

            image[r][c] = {"r": rv, "g": gv, "b": bv}

    return image
