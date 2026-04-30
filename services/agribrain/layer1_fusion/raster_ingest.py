"""
Layer 1 Raster Grid Ingestion.

Converts pre-fetched raster composites (pixel arrays from the orchestrator)
into zone-aggregated EvidenceItems for the fusion pipeline.

Layer 1 never fetches rasters directly — the orchestrator provides them
via Layer1InputBundle.raster_composites.

Design:
- Pixels are aggregated to zone-level summaries to avoid O(pixel²) evidence
  explosion. Each zone gets mean, std, valid_count.
- Raster-scoped evidence carries sigma derived from pixel variance.
- SpatialIndex raster_refs are updated with real resolution + content_hash.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .schemas import EvidenceItem, RasterRef


# Variable → canonical name mapping
_VARIABLE_MAP = {
    "NDVI": "ndvi",
    "NDMI": "ndmi",
    "NDRE": "ndre",
    "SAR": "sar_backscatter",
    "SAR_VV": "sar_backscatter",
    "QUALITY": "quality_mask",
}


def ingest_raster_composites(
    composites: Dict[str, Any],
    plot_id: str,
    run_timestamp: datetime,
    zone_masks: Optional[Dict[str, List[List[int]]]] = None,
) -> Tuple[List[EvidenceItem], List[RasterRef]]:
    """Ingest pre-fetched raster composites into evidence items.

    Args:
        composites: Dict mapping variable name → raster dict with:
            - pixel_array: List[List[float]] (H×W)
            - valid_pixel_count: int
            - resolution_m: float (default 10.0)
        plot_id: Plot identifier.
        run_timestamp: Current run timestamp.
        zone_masks: Optional dict of zone_id → H×W binary mask.
            If provided, evidence is generated per zone.
            If not, a single plot-level summary is generated.

    Returns:
        Tuple of (evidence_items, raster_refs).
    """
    evidence: List[EvidenceItem] = []
    raster_refs: List[RasterRef] = []

    for var_key, raster_data in composites.items():
        if not isinstance(raster_data, dict):
            continue

        pixel_array = raster_data.get("pixel_array")
        if not pixel_array or not pixel_array[0]:
            continue

        valid_count = raster_data.get("valid_pixel_count", 0)
        resolution_m = raster_data.get("resolution_m", 10.0)
        canonical_var = _VARIABLE_MAP.get(var_key, var_key.lower())

        # Compute content hash from pixel data
        content_hash = _compute_pixel_hash(pixel_array)

        # Create raster ref
        raster_id = f"raster_{canonical_var}_{content_hash[:8]}"
        raster_refs.append(RasterRef(
            raster_id=raster_id,
            variable=canonical_var,
            resolution_m=resolution_m,
            content_hash=content_hash,
        ))

        if zone_masks:
            # Zone-aggregated evidence
            for zone_id, mask in zone_masks.items():
                stats = _compute_zonal_stats(pixel_array, mask)
                if stats["count"] == 0:
                    continue

                sigma = _compute_raster_sigma(
                    stats["std"], stats["count"], resolution_m,
                )
                evidence.append(EvidenceItem(
                    evidence_id=f"raster_{canonical_var}_{zone_id}_{content_hash[:8]}",
                    plot_id=plot_id,
                    variable=canonical_var,
                    value=stats["mean"],
                    unit="index" if canonical_var in ("ndvi", "ndmi", "ndre") else "dB",
                    source_family="raster_composite",
                    source_id=raster_id,
                    observation_type="measurement",
                    spatial_scope="zone",
                    scope_id=zone_id,
                    observed_at=run_timestamp,
                    confidence=min(0.9, 0.5 + 0.01 * stats["count"]),
                    sigma=sigma,
                    reliability=min(0.95, 0.6 + 0.005 * stats["count"]),
                    freshness_score=1.0,
                    provenance_ref=f"raster_ingest_{raster_id}_zone_{zone_id}",
                ))
        else:
            # Plot-level summary
            stats = _compute_plot_stats(pixel_array)
            if stats["count"] == 0:
                continue

            sigma = _compute_raster_sigma(
                stats["std"], stats["count"], resolution_m,
            )
            evidence.append(EvidenceItem(
                evidence_id=f"raster_{canonical_var}_plot_{content_hash[:8]}",
                plot_id=plot_id,
                variable=canonical_var,
                value=stats["mean"],
                unit="index" if canonical_var in ("ndvi", "ndmi", "ndre") else "dB",
                source_family="raster_composite",
                source_id=raster_id,
                observation_type="measurement",
                spatial_scope="raster",
                scope_id=raster_id,
                observed_at=run_timestamp,
                confidence=min(0.9, 0.5 + 0.01 * stats["count"]),
                sigma=sigma,
                reliability=min(0.95, 0.6 + 0.005 * stats["count"]),
                freshness_score=1.0,
                provenance_ref=f"raster_ingest_{raster_id}",
            ))

    return evidence, raster_refs


def _compute_pixel_hash(pixel_array: List[List[float]]) -> str:
    """Deterministic hash of pixel data."""
    flat = []
    for row in pixel_array:
        for v in row:
            if v is not None and v == v:  # not NaN
                flat.append(f"{v:.6f}")
            else:
                flat.append("NaN")
    raw = ",".join(flat).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _compute_plot_stats(pixel_array: List[List[float]]) -> Dict[str, float]:
    """Compute mean, std, count from 2D pixel array (ignoring NaN/None)."""
    values = []
    for row in pixel_array:
        for v in row:
            if v is not None and v == v:  # not NaN
                values.append(float(v))

    if not values:
        return {"mean": 0.0, "std": 0.0, "count": 0}

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return {
        "mean": round(mean, 6),
        "std": round(math.sqrt(variance), 6),
        "count": len(values),
    }


def _compute_zonal_stats(
    pixel_array: List[List[float]],
    mask: List[List[int]],
) -> Dict[str, float]:
    """Compute stats for pixels within a zone mask."""
    values = []
    H = min(len(pixel_array), len(mask))
    for y in range(H):
        W = min(len(pixel_array[y]), len(mask[y]))
        for x in range(W):
            if mask[y][x] == 1:
                v = pixel_array[y][x]
                if v is not None and v == v:
                    values.append(float(v))

    if not values:
        return {"mean": 0.0, "std": 0.0, "count": 0}

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return {
        "mean": round(mean, 6),
        "std": round(math.sqrt(variance), 6),
        "count": len(values),
    }


def _compute_raster_sigma(std: float, count: int, resolution_m: float) -> float:
    """Compute sigma from pixel statistics.

    Lower sigma (higher precision) when:
    - More valid pixels (sqrt(count) reduction)
    - Lower pixel variance (std)
    - Finer resolution (inverse penalty for coarse grids)
    """
    base_sigma = max(0.01, std)
    pixel_reduction = 1.0 / math.sqrt(max(1, count))
    resolution_penalty = max(1.0, resolution_m / 10.0)  # 10m = baseline
    return round(base_sigma * pixel_reduction * resolution_penalty, 4)
