"""
Stand Density Engine — Compute canopy density heatmap
=====================================================

Produces a per-pixel stand density surface:
  - High density = many canopy pixels in neighborhood
  - Low density = gaps or bare soil
  - Useful for plantation/orchard health assessment
"""
from typing import List, Optional
from layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from layer10_sire.adapters.l1_adapter import L1SpatialData

CANOPY_THRESHOLD = 0.20  # Lowered from 0.35 to avoid misclassifying patchy early emergence as bare soil


def compute_stand_density(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
    kernel_radius: int = 2,
) -> Optional[SurfaceArtifact]:
    """Compute stand density heatmap from NDVI canopy fraction."""
    if inp.resolution_m > 10.0:
        return None

    if l1_data is None:
        from layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)

    ndvi = l1_data.raster_maps.get('ndvi')
    if ndvi is None:
        return None

    # Binary canopy mask
    canopy = [[False] * W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            v = ndvi[r][c]
            if v is not None and v > CANOPY_THRESHOLD:
                canopy[r][c] = True

    # Compute local canopy fraction in kernel_radius neighborhood
    density = [[0.0] * W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            count = 0
            total = 0
            for dr in range(-kernel_radius, kernel_radius + 1):
                for dc in range(-kernel_radius, kernel_radius + 1):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < H and 0 <= nc < W:
                        total += 1
                        if canopy[nr][nc]:
                            count += 1
            density[r][c] = round(count / total if total > 0 else 0.0, 3)

    return SurfaceArtifact(
        surface_id=f"STAND_DENSITY_{inp.plot_id}",
        semantic_type=SurfaceType.STABILITY_CLASS,  # Reuse semantic type
        grid_ref=f"{H}x{W}",
        values=density,
        units="fraction",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L1"],
    )
