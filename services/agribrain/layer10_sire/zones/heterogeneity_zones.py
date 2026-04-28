"""
Heterogeneity Zone Engine — Management Zones via Constrained Clustering
========================================================================
Complements the alert-zone extractor (threshold + connected components)
with a relative within-field variability engine.

Input: multiple aligned raster surfaces (NDVI, NDMI, SAR VV/VH, etc.)
Output: stable management zones with contiguity + minimum-size constraints.

Methods:
  - Quantile banding with morphological cleanup
  - K-means clustering on multi-band feature vectors
  - Minimum zone size enforcement
  - Contiguity validation
"""
import math
from typing import List, Optional, Dict, Tuple, Any
from layer10_sire.schema import (
    SurfaceArtifact, SurfaceType, ZoneArtifact, ZoneType, ZoneFamily,
)


# ── Configuration ─────────────────────────────────────────────────────────────

MIN_MGMT_ZONE_CELLS = 4        # Minimum cells for a management zone
MAX_MGMT_ZONES = 5              # Maximum zones to produce
DEFAULT_N_BANDS = 3             # Default quantile bands
MIN_VALID_COVERAGE = 0.3        # Need at least 30% valid pixels to attempt zoning


# ── Feature extraction ────────────────────────────────────────────────────────

def _extract_feature_matrix(
    surfaces: List[SurfaceArtifact],
    H: int, W: int,
    raster_composites: Optional[Dict[str, Any]] = None,
    observation_products: Optional[Dict[str, Any]] = None,
) -> Tuple[List[List[Optional[List[float]]]], List[str], int]:
    """Build a multi-band feature matrix [H][W] -> [band_values] from surfaces.
    
    Returns:
        features:    H×W grid, each cell is either None or a list of floats
        band_names:  list of band name strings
        valid_count: number of cells with all bands valid
    """
    # Use raw rasters as primary features (Fix D)
    matched = []
    
    if raster_composites:
        if "NDVI" in raster_composites and "values" in raster_composites["NDVI"]:
            matched.append(("NDVI_RAW", raster_composites["NDVI"]["values"]))
        if "NDMI" in raster_composites and "values" in raster_composites["NDMI"]:
            matched.append(("NDMI_RAW", raster_composites["NDMI"]["values"]))
        if "SAR" in raster_composites:
            sar = raster_composites["SAR"]
            if "vv" in sar:
                matched.append(("SAR_VV", sar["vv"]))
            if "vh" in sar:
                matched.append(("SAR_VH", sar["vh"]))
            elif "values" in sar and "vv" not in sar:
                matched.append(("SAR_BASE", sar["values"]))
                
    # Fix E: Use perception structural layers as a feature constraint
    if observation_products and "spatially_supported" in observation_products:
        # e.g., if we have a row_features map or structural image
        for obs in observation_products["spatially_supported"]:
            if obs.get("observation_type") == "RowFeatureObservation" and obs.get("structural_mask"):
                # Append structural mask as a boolean/float feature
                matched.append(("STRUCTURE_PRIOR", obs["structural_mask"]))
            elif obs.get("observation_type") == "ImageObservation" and obs.get("anomalous_mask"):
                matched.append(("IMAGE_ANOMALY", obs["anomalous_mask"]))
                
    # Fallback to Layer 10 surfaces if no rasters
    if not matched:
        target_types = [
            SurfaceType.NDVI_CLEAN,
            SurfaceType.NDVI_DEVIATION,
            SurfaceType.WATER_STRESS_PROB,
            SurfaceType.NUTRIENT_STRESS_PROB,
        ]
        for st in target_types:
            surf = next((s for s in surfaces if s.semantic_type == st), None)
            if surf:
                matched.append((st.value, surf.values))
    
    if not matched:
        return [[None] * W for _ in range(H)], [], 0
    
    band_names = [name for name, _ in matched]
    features = [[None] * W for _ in range(H)]
    valid_count = 0
    
    for r in range(H):
        for c in range(W):
            vals = []
            all_valid = True
            for _, grid in matched:
                v = grid[r][c] if r < len(grid) and c < len(grid[r]) else None
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    all_valid = False
                    break
                vals.append(float(v) if isinstance(v, (int, float, bool)) else 0.0)
            if all_valid and vals:
                features[r][c] = vals
                valid_count += 1
    
    return features, band_names, valid_count


# ── Normalization ─────────────────────────────────────────────────────────────

def _normalize_features(features, H: int, W: int, n_bands: int):
    """Min-max normalize each band to [0, 1] in-place."""
    band_min = [float('inf')] * n_bands
    band_max = [float('-inf')] * n_bands
    
    for r in range(H):
        for c in range(W):
            if features[r][c] is not None:
                for b in range(n_bands):
                    v = features[r][c][b]
                    band_min[b] = min(band_min[b], v)
                    band_max[b] = max(band_max[b], v)
    
    for r in range(H):
        for c in range(W):
            if features[r][c] is not None:
                for b in range(n_bands):
                    rng = band_max[b] - band_min[b]
                    if rng > 1e-9:
                        features[r][c][b] = (features[r][c][b] - band_min[b]) / rng
                    else:
                        features[r][c][b] = 0.5


# ── K-Means Clustering (Pure Python) ─────────────────────────────────────────

def _euclidean_dist(a: List[float], b: List[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _kmeans_cluster(
    features, H: int, W: int, n_clusters: int, max_iter: int = 20
) -> List[List[int]]:
    """Simple k-means on the feature grid. Returns labels [H][W], -1 = nodata."""
    # Collect valid cells
    valid_cells = []
    for r in range(H):
        for c in range(W):
            if features[r][c] is not None:
                valid_cells.append((r, c, features[r][c]))
    
    if len(valid_cells) < n_clusters:
        return [[-1] * W for _ in range(H)]
    
    n_bands = len(valid_cells[0][2])
    
    # Initialize centroids: evenly spaced from sorted primary band
    valid_cells_sorted = sorted(valid_cells, key=lambda x: x[2][0])
    step = max(1, len(valid_cells_sorted) // n_clusters)
    centroids = [list(valid_cells_sorted[min(i * step, len(valid_cells_sorted) - 1)][2]) for i in range(n_clusters)]
    
    labels = [[-1] * W for _ in range(H)]
    
    for _ in range(max_iter):
        # Assign
        for r, c, fv in valid_cells:
            best_k = 0
            best_d = float('inf')
            for k in range(n_clusters):
                d = _euclidean_dist(fv, centroids[k])
                if d < best_d:
                    best_d = d
                    best_k = k
            labels[r][c] = best_k
        
        # Update centroids
        new_centroids = [[0.0] * n_bands for _ in range(n_clusters)]
        counts = [0] * n_clusters
        for r, c, fv in valid_cells:
            k = labels[r][c]
            counts[k] += 1
            for b in range(n_bands):
                new_centroids[k][b] += fv[b]
        
        converged = True
        for k in range(n_clusters):
            if counts[k] > 0:
                for b in range(n_bands):
                    new_centroids[k][b] /= counts[k]
                if _euclidean_dist(new_centroids[k], centroids[k]) > 1e-4:
                    converged = False
                centroids[k] = new_centroids[k]
        
        if converged:
            break
    
    return labels


# ── Connected Components ──────────────────────────────────────────────────────

def _connected_components(labels, H: int, W: int, target_label: int) -> List[List[Tuple[int, int]]]:
    """Extract connected components for a given label using BFS."""
    visited = [[False] * W for _ in range(H)]
    components = []
    
    for r in range(H):
        for c in range(W):
            if labels[r][c] == target_label and not visited[r][c]:
                # BFS
                queue = [(r, c)]
                visited[r][c] = True
                component = []
                while queue:
                    cr, cc = queue.pop(0)
                    component.append((cr, cc))
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < H and 0 <= nc < W and not visited[nr][nc] and labels[nr][nc] == target_label:
                            visited[nr][nc] = True
                            queue.append((nr, nc))
                if len(component) >= MIN_MGMT_ZONE_CELLS:
                    components.append(component)
    
    return components


# ── Zone Builder ──────────────────────────────────────────────────────────────

def _compute_zone_stats(cells: List[Tuple[int, int]], surfaces: List[SurfaceArtifact]) -> Dict[str, float]:
    """Compute mean value for each surface within a zone's cells."""
    stats = {}
    for surf in surfaces:
        vals = []
        for r, c in cells:
            if r < len(surf.values) and c < len(surf.values[r]):
                v = surf.values[r][c]
                if v is not None and not (isinstance(v, float) and math.isnan(v)):
                    vals.append(v)
        if vals:
            stats[surf.semantic_type.value] = round(sum(vals) / len(vals), 4)
    return stats


def _classify_zone_type(zone_stats: Dict[str, float], cluster_rank: int) -> ZoneType:
    """Assign a semantic zone type based on cluster characteristics."""
    ndvi = zone_stats.get("NDVI_CLEAN", 0.5)
    water = zone_stats.get("WATER_STRESS_PROB", 0.0)
    nutrient = zone_stats.get("NUTRIENT_STRESS_PROB", 0.0)
    
    if ndvi < 0.3 or water > 0.6:
        return ZoneType.WATER_STRESS
    if nutrient > 0.5:
        return ZoneType.NUTRIENT_RISK
    if ndvi > 0.6:
        return ZoneType.HIGH_VIGOR
    return ZoneType.LOW_VIGOR


# ── Main Entry Point ──────────────────────────────────────────────────────────

def extract_heterogeneity_zones(
    surfaces: List[SurfaceArtifact],
    H: int, W: int,
    n_zones: int = DEFAULT_N_BANDS,
    field_valid_cells: Optional[int] = None,
    raster_composites: Optional[Dict[str, Any]] = None,
    observation_products: Optional[Dict[str, Any]] = None,
) -> Tuple[List[ZoneArtifact], Dict[str, Any]]:
    """Extract management zones via constrained clustering.
    
    Parameters
    ----------
    surfaces             : SurfaceArtifacts from the SIRE pipeline
    H, W                 : grid dimensions
    n_zones              : target number of management zones
    field_valid_cells    : canonical valid cell count
    raster_composites    : raw raster grids from Process API
    observation_products : raw user inputs and structure masks
    
    Returns
    -------
    zones              : list of ZoneArtifact (management zones)
    meta               : metadata dict with clustering diagnostics
    """
    zones = []
    meta = {"engine": "heterogeneity_kmeans", "attempted": False, "reason": ""}
    
    # Build feature matrix from surfaces & rasters
    features, band_names, valid_count = _extract_feature_matrix(
        surfaces, H, W, raster_composites, observation_products
    )
    
    total_cells = field_valid_cells or (H * W)
    coverage = valid_count / total_cells if total_cells > 0 else 0
    
    if coverage < MIN_VALID_COVERAGE:
        meta["reason"] = f"insufficient_coverage ({coverage:.1%} < {MIN_VALID_COVERAGE:.0%})"
        return zones, meta
    
    if len(band_names) < 1:
        meta["reason"] = "no_valid_feature_bands"
        return zones, meta
    
    meta["attempted"] = True
    meta["bands"] = band_names
    meta["valid_coverage"] = round(coverage, 3)
    
    # Normalize features
    n_bands = len(band_names)
    _normalize_features(features, H, W, n_bands)
    
    # Determine cluster count — never more than MAX_MGMT_ZONES
    k = min(n_zones, MAX_MGMT_ZONES)
    # Reduce if too few valid cells
    if valid_count < k * MIN_MGMT_ZONE_CELLS:
        k = max(2, valid_count // MIN_MGMT_ZONE_CELLS)
    
    # Cluster
    labels = _kmeans_cluster(features, H, W, k)
    
    # Extract connected components per cluster and build zones
    zone_counter = 0
    for cluster_id in range(k):
        components = _connected_components(labels, H, W, cluster_id)
        
        # Rank components by size (largest first), take only the main body
        components.sort(key=lambda comp: len(comp), reverse=True)
        
        for comp_idx, cells in enumerate(components):
            if zone_counter >= MAX_MGMT_ZONES:
                break
            
            area_pct = len(cells) / total_cells if total_cells > 0 else 0
            zone_stats = _compute_zone_stats(cells, surfaces)
            zone_type = _classify_zone_type(zone_stats, cluster_id)
            
            # Compute bounding box for the zone
            rows = [r for r, c in cells]
            cols = [c for r, c in cells]
            bbox_r = (min(rows), max(rows))
            bbox_c = (min(cols), max(cols))
            
            zone_id = f"MZ_{cluster_id}_{comp_idx}"
            
            zone = ZoneArtifact(
                zone_id=zone_id,
                zone_type=zone_type,
                zone_family=ZoneFamily.AGRONOMIC,
                cell_indices=cells,
                area_pct=round(area_pct, 4),
                area_m2=round(area_pct * total_cells * 100, 1),  # approximate m²
                severity=0.5,  # Management zones are neutral severity
                confidence=round(min(0.95, coverage * 0.9 + 0.1), 3),
                top_drivers=[band_names[0]] if band_names else [],
                label=f"Management Zone {chr(65 + zone_counter)}",
                source_surface_type=SurfaceType.NDVI_CLEAN.value,
                linked_findings=[
                    {"type": "clustering", "detail": f"k-means cluster {cluster_id}"},
                    {"type": "contiguity", "detail": f"component {comp_idx}"},
                ],
                confidence_reasons=[
                    f"based on {len(band_names)} spectral bands",
                    f"coverage {coverage:.0%}",
                ],
                bbox=(bbox_r[0], bbox_c[0], bbox_r[1], bbox_c[1]),
                surface_stats={k: {"mean": v} for k, v in zone_stats.items()},
            )
            zones.append(zone)
            zone_counter += 1
    
    meta["zones_produced"] = len(zones)
    meta["k_used"] = k
    return zones, meta
