"""
Quicklook Generator — Fast preview images from surfaces
========================================================

Generates compact preview tiles from surface data.
"""
from typing import Dict, Any, List, Optional
from services.agribrain.layer10_sire.schema import SurfaceArtifact, SurfaceType


# Palette lookups — surface type to quick color ramp
QUICK_PALETTES = {
    SurfaceType.NDVI_CLEAN: [
        (0.0, (139, 115, 85)),     # Brown
        (0.3, (196, 167, 125)),    # Tan
        (0.5, (144, 181, 96)),     # Light green
        (0.7, (77, 140, 42)),      # Green
        (0.9, (27, 94, 32)),       # Dark green
    ],
    SurfaceType.WATER_STRESS_PROB: [
        (0.0, (21, 101, 192)),     # Blue (no stress)
        (0.3, (79, 195, 247)),     # Light blue
        (0.5, (255, 235, 59)),     # Yellow
        (0.7, (239, 108, 0)),      # Orange
        (1.0, (183, 28, 28)),      # Red
    ],
    SurfaceType.COMPOSITE_RISK: [
        (0.0, (46, 125, 50)),      # Green (low risk)
        (0.3, (255, 235, 59)),     # Yellow
        (0.6, (239, 108, 0)),      # Orange
        (0.8, (211, 47, 47)),      # Red
        (1.0, (136, 14, 79)),      # Deep red
    ],
}

# Default palette for unmatched types
DEFAULT_PALETTE = [
    (0.0, (33, 33, 33)),
    (0.5, (117, 117, 117)),
    (1.0, (238, 238, 238)),
]


def generate_quicklook(
    surface: SurfaceArtifact,
    H: int, W: int,
    target_size: int = 64,
) -> Dict[str, Any]:
    """Generate a compact preview tile for a surface.

    Returns:
      {
        "surface_type": ...,
        "width": ...,
        "height": ...,
        "pixels": [[{"r":, "g":, "b":}...]...]
      }
    """
    palette = QUICK_PALETTES.get(surface.semantic_type, DEFAULT_PALETTE)
    lo, hi = surface.render_range if surface.render_range else (0.0, 1.0)

    # Downsample if needed
    step_r = max(1, H // target_size)
    step_c = max(1, W // target_size)
    out_h = min(H, target_size)
    out_w = min(W, target_size)

    pixels = []
    for ri in range(out_h):
        row = []
        r = ri * step_r
        for ci in range(out_w):
            c = ci * step_c
            v = surface.values[r][c] if r < H and c < W else None
            if v is not None:
                norm = max(0.0, min(1.0, (v - lo) / (hi - lo) if hi != lo else 0.5))
                rgb = _palette_lookup(palette, norm)
            else:
                rgb = (128, 128, 128)  # Gray for NoData
            row.append({"r": rgb[0], "g": rgb[1], "b": rgb[2]})
        pixels.append(row)

    return {
        "surface_type": surface.semantic_type.value,
        "width": out_w,
        "height": out_h,
        "pixels": pixels,
    }


def _palette_lookup(palette, value):
    """Interpolate RGB from palette stops."""
    if value <= palette[0][0]:
        return palette[0][1]
    if value >= palette[-1][0]:
        return palette[-1][1]

    for i in range(len(palette) - 1):
        v0, c0 = palette[i]
        v1, c1 = palette[i + 1]
        if v0 <= value <= v1:
            t = (value - v0) / (v1 - v0) if v1 != v0 else 0.0
            return (
                int(c0[0] + (c1[0] - c0[0]) * t),
                int(c0[1] + (c1[1] - c0[1]) * t),
                int(c0[2] + (c1[2] - c0[2]) * t),
            )

    return palette[-1][1]
