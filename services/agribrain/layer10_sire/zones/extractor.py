"""
Zone Extractor — Convert surfaces to spatial zones via threshold + connected components
"""
import math
from typing import List, Optional, Tuple, Dict
from layer10_sire.schema import (
    SurfaceArtifact, SurfaceType, ZoneArtifact, ZoneType, ZoneFamily,
)

# Threshold configs: which surfaces generate which zones
ZONE_CONFIGS = {
    SurfaceType.NDVI_DEVIATION: {
        "threshold": None,     # Adaptive — computed per field from variance
        "threshold_adaptive": True,
        "compare": "lt",
        "zone_type": ZoneType.LOW_VIGOR,
        "family": ZoneFamily.AGRONOMIC,
    },
    SurfaceType.BASELINE_ANOMALY: {
        "threshold": -0.05,     # Static threshold for being behind expectation
        "threshold_adaptive": False,
        "compare": "lt",
        "zone_type": ZoneType.LOW_VIGOR,
        "family": ZoneFamily.AGRONOMIC,
    },
    SurfaceType.WATER_STRESS_PROB: {
        "threshold": 0.5,
        "compare": "gt",
        "zone_type": ZoneType.WATER_STRESS,
        "family": ZoneFamily.AGRONOMIC,
    },
    SurfaceType.NUTRIENT_STRESS_PROB: {
        "threshold": 0.5,
        "compare": "gt",
        "zone_type": ZoneType.NUTRIENT_RISK,
        "family": ZoneFamily.AGRONOMIC,
    },
    SurfaceType.BIOTIC_PRESSURE: {
        "threshold": 0.5,
        "compare": "gt",
        "zone_type": ZoneType.DISEASE_RISK,
        "family": ZoneFamily.AGRONOMIC,
    },
    SurfaceType.UNCERTAINTY_SIGMA: {
        "threshold": 0.2,
        "compare": "gt",
        "zone_type": ZoneType.LOW_CONFIDENCE,
        "family": ZoneFamily.TRUST,
    },
}


def _compute_adaptive_threshold(surface: 'SurfaceArtifact', H: int, W: int) -> float:
    """Compute an adaptive vegetation anomaly threshold from field deviation statistics.

    Strategy: use mean - 1.2*std as the threshold, floored at -0.08.
    This means uniform orchards (tight std) get a lower bar, while
    high-variance fields still need meaningful negative deviation.
    """
    vals = []
    for r in range(H):
        for c in range(W):
            v = surface.values[r][c]
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                vals.append(v)
    if len(vals) < 4:
        return -0.08  # Minimum floor
    mean_v = sum(vals) / len(vals)
    std_v = math.sqrt(sum((x - mean_v) ** 2 for x in vals) / len(vals))
    # For mean-centered deviation: mean ~0, so threshold = -1.2*std, floor -0.08
    adaptive = -(1.2 * std_v)
    return max(adaptive, -0.08)  # Never easier than -0.08

MIN_ZONE_CELLS = 2  # Minimum cells to form a zone


# ── Confidence scoring (WS9) ──────────────────────────────────────────────────

def _count_edge_cells(cells: List, surface: SurfaceArtifact) -> int:
    """Count cells that have at least one None neighbor (boundary/edge cells)."""
    H = len(surface.values)
    W = len(surface.values[0]) if H > 0 else 0
    cell_set = set((r, c) for r, c in cells)
    edge_count = 0
    for r, c in cells:
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            # Neighbour is outside grid OR a null cell → this is an edge cell
            if not (0 <= nr < H and 0 <= nc < W):
                edge_count += 1
                break
            v = surface.values[nr][nc]
            if v is None or (isinstance(v, float) and math.isnan(v)):
                edge_count += 1
                break
    return edge_count


def _compute_zone_confidence(
    cells: List,
    surface: SurfaceArtifact,
    sigma_surface: Optional[SurfaceArtifact] = None,
    denom: Optional[int] = None,
) -> tuple[float, List[str]]:
    """
    Compute a multi-factor zone confidence score and return reasons.

    Factors (all in [0,1]):
      base    = mean of surface.confidence channel over cells (default 0.7)
      size    = min(1.0, n_cells / 20)                — small zones penalised
      sigma   = 1.0 - mean_sigma_at_cells (clamped)  — high uncertainty penalised
      edge    = 1.0 - edge_fraction * 0.4             — edge-heavy zones penalised

    confidence = base * size * sigma - edge_penalty (floor 0.1)
    """
    reasons: List[str] = []
    n = len(cells)

    # Base: mean of confidence channel
    base = 0.7
    if surface.confidence:
        conf_vals = [
            surface.confidence[r][c]
            for r, c in cells
            if r < len(surface.confidence)
            and c < len(surface.confidence[r])
            and surface.confidence[r][c] is not None
        ]
        if conf_vals:
            base = sum(conf_vals) / len(conf_vals)

    # Size factor: scaled dynamically by plot size
    if denom and denom > 0:
        # A zone needs to cover at least ~2% of the field, but at least 4 cells, to avoid penalty
        expected_cells = max(4, int(denom * 0.02))
        size_factor = min(1.0, n / expected_cells)
    else:
        # Softer absolute fallback
        size_factor = min(1.0, n / 10.0)

    if size_factor < 0.7:
        reasons.append("reduced by small zone size relative to field")

    # Sigma factor
    sigma_factor = 1.0
    if sigma_surface is not None:
        sigma_vals = [
            sigma_surface.values[r][c]
            for r, c in cells
            if r < len(sigma_surface.values)
            and c < len(sigma_surface.values[r])
            and sigma_surface.values[r][c] is not None
        ]
        if sigma_vals:
            mean_sigma = sum(sigma_vals) / len(sigma_vals)
            sigma_factor = max(0.3, 1.0 - min(0.7, mean_sigma))
            if mean_sigma > 0.3:
                reasons.append("reduced by high local uncertainty")

    # Edge penalty
    edge_count = _count_edge_cells(cells, surface)
    edge_frac = edge_count / max(1, n)
    edge_penalty = edge_frac * 0.4
    if edge_frac > 0.5:
        reasons.append("reduced by edge adjacency")

    # Multi-cell agreement boost
    if n >= 20 and size_factor >= 0.8:
        reasons.append("boosted by multi-cell agreement")

    score = base * size_factor * sigma_factor - edge_penalty
    score = round(max(0.1, min(1.0, score)), 3)
    return score, reasons


# ── Main extractor ────────────────────────────────────────────────────────────

def extract_zones(
    surfaces: List[SurfaceArtifact],
    H: int,
    W: int,
    field_valid_cells: Optional[int] = None,
) -> Tuple[List[ZoneArtifact], Dict[str, str]]:
    """Extract zones from surfaces using thresholding + connected components.

    Parameters
    ----------
    surfaces          : list of SurfaceArtifact produced by the pipeline
    H, W              : raster grid dimensions
    field_valid_cells : count of non-null cells inside the actual field polygon.
                       If provided, used as area denominator instead of H*W so
                       that area_pct reflects the true field footprint, not bbox.
    """
    zones = []
    zone_state_by_surface: Dict[str, str] = {}

    # Find sigma surface once for confidence scoring
    sigma_surface: Optional[SurfaceArtifact] = next(
        (s for s in surfaces if s.semantic_type == SurfaceType.UNCERTAINTY_SIGMA), None
    )

    # True denominator — field-masked if available (WS2)
    denom = field_valid_cells if (field_valid_cells is not None and field_valid_cells > 0) else (H * W)

    for surface in surfaces:
        config = ZONE_CONFIGS.get(surface.semantic_type)
        if config is None:
            continue

        # Resolve threshold — adaptive for NDVI_DEVIATION, static otherwise
        threshold = config["threshold"]
        if config.get("threshold_adaptive"):
            threshold = _compute_adaptive_threshold(surface, H, W)

        # Threshold → binary mask
        mask = [[False]*W for _ in range(H)]
        valid_cells_count = 0
        for r in range(H):
            for c in range(W):
                v = surface.values[r][c]
                if v is None:
                    continue
                valid_cells_count += 1
                if config["compare"] == "gt" and v > threshold:
                    mask[r][c] = True
                elif config["compare"] == "lt" and v < threshold:
                    mask[r][c] = True

        # Connected components (4-connectivity BFS)
        visited = [[False]*W for _ in range(H)]
        components = []
        total_cells_above_threshold = 0

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
                    if len(cells) >= MIN_ZONE_CELLS:
                        components.append(cells)
                    total_cells_above_threshold += len(cells)

        surface_zones = []
        for i, cells in enumerate(components):
            rows = [c[0] for c in cells]
            cols = [c[1] for c in cells]
            bbox = (min(rows), min(cols), max(rows), max(cols))

            valid_vals = [
                surface.values[r][c] for r, c in cells
                if surface.values[r][c] is not None
            ]
            mean_val = sum(valid_vals) / len(valid_vals) if valid_vals else 0.0

            # WS9: real confidence with reasons
            conf, conf_reasons = _compute_zone_confidence(cells, surface, sigma_surface, denom)

            if conf < 0.45:
                # Weak evidence is suppressed - don't draw faked shapes
                continue

            # WS2: area fraction uses true field denominator
            area_fraction = round(len(cells) / denom, 4)

            # Compute richer zonal stats (WS6 enrichment)
            sorted_vv = sorted(valid_vals)
            nv = len(sorted_vv)
            std_val = math.sqrt(sum((v - mean_val) ** 2 for v in valid_vals) / nv) if nv > 0 else 0.0
            p10_val = sorted_vv[max(0, int(nv * 0.10))] if nv > 0 else mean_val
            p90_val = sorted_vv[min(nv - 1, int(nv * 0.90))] if nv > 0 else mean_val

            zone = ZoneArtifact(
                zone_id=f"Z-{config['zone_type'].value}-{i}",
                zone_type=config["zone_type"],
                zone_family=config["family"],
                bbox=bbox,
                cell_indices=cells,
                area_m2=len(cells) * 100.0,   # 10m × 10m per cell
                area_pct=area_fraction,        # 0–1 fraction of true field area
                severity=round(abs(mean_val), 3),
                confidence=conf,
                confidence_reasons=conf_reasons,
                top_drivers=[surface.semantic_type.value],
                source_surface_type=surface.semantic_type.value,
                description=f"{config['zone_type'].value}: {len(cells)} cells ({area_fraction*100:.1f}% of field)",
                surface_stats={
                    surface.semantic_type.value: {
                        "mean": round(mean_val, 4),
                        "std": round(std_val, 4),
                        "p10": round(p10_val, 4),
                        "p90": round(p90_val, 4),
                        "cells": len(cells),
                    }
                },
            )
            surface_zones.append(zone)

        # ── Pre-deconfliction state bookkeeping ──
        # Track which surfaces had signal and their fraction for post-deconfliction recomputation
        fraction_above = total_cells_above_threshold / denom if denom > 0 else 0
        zone_state_by_surface[surface.semantic_type.value] = {
            "fraction_above": fraction_above,
            "pre_zone_count": len(surface_zones),
            "total_cells_above": total_cells_above_threshold,
            "valid_cells_count": valid_cells_count,
        }
        zones.extend(surface_zones)

    # Deconflict overlaps within each family
    zones = _deconflict_family_overlaps(zones, denom)

    # ── Recompute zone_state_by_surface AFTER deconfliction ──
    final_state: Dict[str, str] = {}
    for surface_key, pre_info in zone_state_by_surface.items():
        fraction_above = pre_info["fraction_above"]
        total_cells_above = pre_info["total_cells_above"]
        valid_cells_count = pre_info.get("valid_cells_count", 0)
        # Count surviving zones for this surface
        surviving = [z for z in zones if z.source_surface_type == surface_key]

        if valid_cells_count == 0:
            state = "no_data"
        elif total_cells_above == 0:
            state = "none"
        elif fraction_above > 0.6:
            state = "field_wide"
            # Fix 3: Keep the field-wide artifact instead of stripping it to empty.
            # No longer dropping: zones = [z for z in zones if not (... > 0.6)]
        elif len(surviving) > 0:
            state = "localized"
        else:
            state = "low_confidence"

        final_state[surface_key] = state

    return zones, final_state


def _deconflict_family_overlaps(
    zones: List[ZoneArtifact],
    field_total_cells: int = 1,
) -> List[ZoneArtifact]:
    """Remove overlapping cells within each zone family.

    Higher-severity zones win ties. Zones with no remaining
    cells after deconfliction are dropped entirely.
    Area fraction and description are refreshed after deconfliction.
    """
    families: dict = {}
    for z in zones:
        families.setdefault(z.zone_family.value, []).append(z)

    result = []
    for _fam, fam_zones in families.items():
        fam_zones.sort(key=lambda z: z.severity, reverse=True)

        claimed: set = set()
        for z in fam_zones:
            new_cells = [(r, c) for r, c in z.cell_indices if (r, c) not in claimed]
            if len(new_cells) < MIN_ZONE_CELLS:
                continue

            for cell in new_cells:
                claimed.add(cell)

            rows = [c[0] for c in new_cells]
            cols = [c[1] for c in new_cells]

            z.cell_indices = new_cells
            z.bbox = (min(rows), min(cols), max(rows), max(cols))
            # WS2: recompute area with same true-field denominator
            z.area_pct = round(len(new_cells) / max(1, field_total_cells), 4)
            z.area_m2 = len(new_cells) * 100.0
            # WS5: refresh description so cell count is post-deconfliction truth
            z.description = (
                f"{z.zone_type.value}: {len(new_cells)} cells "
                f"({z.area_pct * 100:.1f}% of field)"
            )
            result.append(z)

    return result
