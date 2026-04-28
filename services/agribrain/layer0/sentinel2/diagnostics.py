"""
Sentinel-2 Diagnostics — Explains why scenes were used/downweighted.
"""

from __future__ import annotations

from typing import Any, Dict, List

from layer0.sentinel2.schemas import Sentinel2ScenePackage
from layer0.sentinel2.indices import RasterComputationDiagnostics


def build_diagnostics(
    pkg: Sentinel2ScenePackage,
    index_diagnostics: Dict[str, RasterComputationDiagnostics],
    kalman_obs_created: int = 0,
    kalman_obs_skipped: List[str] = None,
) -> Dict[str, Any]:
    """Build a diagnostics dict for debugging."""
    qa = pkg.qa
    meta = pkg.metadata

    # Determine why used/downweighted
    if not qa.usable:
        why_used = "not_used"
        why_downweighted = qa.reason
    elif qa.quality_class.value == "excellent":
        why_used = "best_valid_recent"
        why_downweighted = "none"
    elif qa.quality_class.value == "good":
        why_used = "good_quality"
        why_downweighted = "; ".join(qa.flags) if qa.flags else "minor_issues"
    else:
        why_used = "degraded_but_usable"
        why_downweighted = "; ".join(qa.flags) if qa.flags else "degraded_quality"

    # Bad indices
    bad_indices = []
    for idx_name, diag in index_diagnostics.items():
        oor = diag.out_of_range_counts.get(idx_name, 0)
        if oor > 0:
            bad_indices.append(f"{idx_name}_{oor}_pixels_out_of_range")
        if diag.valid_input_pixels > 0 and diag.valid_output_pixels == 0:
            bad_indices.append(f"{idx_name}_all_pixels_invalid")

    # Missing bands
    required = {"B02", "B03", "B04", "B05", "B08", "B8A", "B11"}
    provided = set(meta.band_list) if meta.band_list else set()
    missing_bands = sorted(required - provided)

    return {
        "scene_id": meta.scene_id,
        "why_used": why_used,
        "why_downweighted": why_downweighted,
        "missing_bands": missing_bands,
        "bad_indices": bad_indices,
        "qa_flags": qa.flags,
        "zone_failures": [
            zs.zone_id for zs in pkg.zone_summaries
            if zs.valid_fraction < 0.4
        ],
        "kalman_observations_created": kalman_obs_created,
        "kalman_observations_skipped": kalman_obs_skipped or [],
    }
