"""
Canopy Mask Engine (v2) — Connected canopy patches, not single blob
"""
from typing import List, Optional
from services.agribrain.layer10_sire.schema import (
    Layer10Input, MicroObjectArtifact, ObjectType,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData


CANOPY_THRESHOLD = 0.4


def detect_canopy(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
) -> List[MicroObjectArtifact]:
    """
    Detect canopy patches as connected components from NDVI raster.
    Returns individual canopy patches, not one blob.
    """
    objects = []

    if inp.resolution_m > 5.0:
        return objects

    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)

    ndvi = l1_data.raster_maps.get('ndvi')
    if ndvi is None:
        return objects

    # Binary mask: NDVI > threshold = canopy
    mask = [[False]*W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            v = ndvi[r][c]
            if v is not None and v > CANOPY_THRESHOLD:
                mask[r][c] = True

    # Connected components (4-connectivity BFS)
    visited = [[False]*W for _ in range(H)]
    patch_idx = 0

    for r in range(H):
        for c in range(W):
            if mask[r][c] and not visited[r][c]:
                cells = []
                queue = [(r, c)]
                visited[r][c] = True

                while queue:
                    cr, cc = queue.pop(0)
                    cells.append((cr, cc))
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < H and 0 <= nc < W and mask[nr][nc] and not visited[nr][nc]:
                            visited[nr][nc] = True
                            queue.append((nr, nc))

                if len(cells) < 1:
                    continue

                # Compute patch metrics
                ndvi_vals = [ndvi[cr][cc] for cr, cc in cells if ndvi[cr][cc] is not None]
                mean_ndvi = sum(ndvi_vals) / len(ndvi_vals) if ndvi_vals else 0.0
                centroid_r = sum(cr for cr, cc in cells) / len(cells)
                centroid_c = sum(cc for cr, cc in cells) / len(cells)

                objects.append(MicroObjectArtifact(
                    object_id=f"CANOPY-{inp.plot_id}-{patch_idx}",
                    object_type=ObjectType.CANOPY_PATCH,
                    centroid=(centroid_r, centroid_c),
                    cell_indices=cells,
                    area_m2=len(cells) * inp.resolution_m * inp.resolution_m,
                    score=min(1.0, mean_ndvi / 0.8),
                    confidence=0.7 if len(cells) >= 3 else 0.4,
                    measurements={
                        "ndvi_mean": round(mean_ndvi, 3),
                        "pixel_count": len(cells),
                    },
                    derived_from="L1_NDVI_RASTER",
                ))
                patch_idx += 1

    # Also detect gaps (non-canopy patches within canopy)
    gap_idx = 0
    gap_visited = [[False]*W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            if not mask[r][c] and not gap_visited[r][c]:
                cells = []
                queue = [(r, c)]
                gap_visited[r][c] = True
                while queue:
                    cr, cc = queue.pop(0)
                    cells.append((cr, cc))
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < H and 0 <= nc < W and not mask[nr][nc] and not gap_visited[nr][nc]:
                            gap_visited[nr][nc] = True
                            queue.append((nr, nc))

                # Only interior gaps (surrounded by canopy, not field edge)
                is_edge = any(
                    cr == 0 or cr == H-1 or cc == 0 or cc == W-1
                    for cr, cc in cells
                )
                if not is_edge and len(cells) >= 2:
                    centroid_r = sum(cr for cr, cc in cells) / len(cells)
                    centroid_c = sum(cc for cr, cc in cells) / len(cells)
                    objects.append(MicroObjectArtifact(
                        object_id=f"GAP-{inp.plot_id}-{gap_idx}",
                        object_type=ObjectType.GAP_CLUSTER,
                        centroid=(centroid_r, centroid_c),
                        cell_indices=cells,
                        area_m2=len(cells) * inp.resolution_m * inp.resolution_m,
                        score=0.8,
                        confidence=0.6,
                        measurements={"pixel_count": len(cells)},
                        derived_from="L1_NDVI_RASTER_INVERSE",
                    ))
                    gap_idx += 1

    return objects
