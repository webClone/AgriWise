"""
Crown Detection Engine — Detect individual tree/shrub crowns from NDVI
======================================================================

For orchard/plantation crops: detect circular canopy patches
using local maxima + watershed-like segmentation.
"""
from typing import List, Optional
from layer10_sire.schema import (
    Layer10Input, MicroObjectArtifact, ObjectType,
)
from layer10_sire.adapters.l1_adapter import L1SpatialData


def detect_crowns(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
) -> List[MicroObjectArtifact]:
    """Detect individual tree crowns from NDVI raster."""
    if inp.resolution_m > 3.0:  # Crowns need higher resolution
        return []

    if l1_data is None:
        from layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)

    ndvi = l1_data.raster_maps.get('ndvi')
    if ndvi is None:
        return []

    # Step 1: Find local maxima (crown centers)
    maxima = _find_local_maxima(ndvi, H, W, radius=1)

    # Step 2: Grow crowns from maxima using watershed-like expansion
    objects = []
    assigned = [[False] * W for _ in range(H)]

    for idx, (mr, mc, peak_val) in enumerate(maxima):
        # BFS grow from peak while NDVI stays above drop threshold
        drop_threshold = peak_val * 0.65  # Crown edge at 35% drop from peak
        cells = []
        queue = [(mr, mc)]
        assigned[mr][mc] = True

        while queue:
            cr, cc = queue.pop(0)
            cells.append((cr, cc))
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = cr + dr, cc + dc
                if (0 <= nr < H and 0 <= nc < W
                    and not assigned[nr][nc]
                    and ndvi[nr][nc] is not None
                    and ndvi[nr][nc] > drop_threshold):
                    assigned[nr][nc] = True
                    queue.append((nr, nc))

        if len(cells) < 2:
            continue

        ndvi_vals = [ndvi[r][c] for r, c in cells if ndvi[r][c] is not None]
        mean_ndvi = sum(ndvi_vals) / len(ndvi_vals)

        objects.append(MicroObjectArtifact(
            object_id=f"CROWN-{inp.plot_id}-{idx}",
            object_type=ObjectType.CROWN,
            centroid=(mr, mc),
            cell_indices=cells,
            area_m2=len(cells) * inp.resolution_m * inp.resolution_m,
            score=min(1.0, mean_ndvi / 0.7),
            confidence=0.7 if len(cells) >= 4 else 0.4,
            measurements={
                "peak_ndvi": round(peak_val, 3),
                "mean_ndvi": round(mean_ndvi, 3),
                "crown_pixels": len(cells),
                "estimated_diameter_m": round((len(cells) * inp.resolution_m ** 2 / 3.14159) ** 0.5 * 2, 1),
            },
            derived_from="L1_NDVI_CROWN_WATERSHED",
        ))

    return objects


def _find_local_maxima(ndvi, H, W, radius=1):
    """Find local NDVI maxima — potential crown centers."""
    maxima = []
    threshold = 0.3  # Minimum NDVI for a crown center

    for r in range(radius, H - radius):
        for c in range(radius, W - radius):
            v = ndvi[r][c]
            if v is None or v < threshold:
                continue

            is_max = True
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < H and 0 <= nc < W:
                        nv = ndvi[nr][nc]
                        if nv is not None and nv >= v:
                            is_max = False
                            break
                if not is_max:
                    break

            if is_max:
                maxima.append((r, c, v))

    # Sort by peak value descending
    maxima.sort(key=lambda x: -x[2])
    return maxima
