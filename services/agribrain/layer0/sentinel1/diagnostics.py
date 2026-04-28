"""
Sentinel-1 SAR Diagnostics.

Explains why a SAR scene was used/downweighted, reports SAR-specific issues.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.sentinel1.features import SARFeatureDiagnostics
from layer0.sentinel1.schemas import (
    SARQualityClass,
    Sentinel1QAResult,
    Sentinel1SceneMetadata,
    Sentinel1ZoneSummary,
)


def build_sar_diagnostics(
    metadata: Sentinel1SceneMetadata,
    qa: Sentinel1QAResult,
    feature_diagnostics: Optional[Dict[str, SARFeatureDiagnostics]] = None,
    zone_summaries: Optional[List[Sentinel1ZoneSummary]] = None,
    kalman_count: int = 0,
    kalman_skipped: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build comprehensive diagnostic report for a SAR scene."""

    # Why used/not used
    if not qa.usable:
        why_used = "not_used"
    elif qa.quality_class == SARQualityClass.EXCELLENT:
        why_used = "cloud_independent_excellent_scene"
    elif qa.quality_class == SARQualityClass.GOOD:
        why_used = "cloud_independent_valid_scene"
    else:
        why_used = "cloud_independent_degraded_scene"

    # Why downweighted
    why_downweighted = list(qa.flags)

    # Missing bands
    missing_bands = []

    # Bad features from diagnostics
    bad_features = []
    if feature_diagnostics:
        for name, diag in feature_diagnostics.items():
            if diag.out_of_hard_range > 0:
                bad_features.append(
                    f"{name}_{diag.out_of_hard_range}_pixels_out_of_hard_range"
                )
            if diag.out_of_soft_range > 0:
                bad_features.append(
                    f"{name}_{diag.out_of_soft_range}_pixels_out_of_soft_range"
                )
            for flag in diag.flags:
                bad_features.append(f"{name}_{flag}")

    # Zone failures
    zone_failures = []
    if zone_summaries:
        for zs in zone_summaries:
            if zs.valid_fraction < 0.45:
                zone_failures.append(f"{zs.zone_id}_valid_fraction_low")
            if zs.border_noise_fraction > 0.30:
                zone_failures.append(f"{zs.zone_id}_border_noise_high")
            if zs.low_signal_fraction > 0.50:
                zone_failures.append(f"{zs.zone_id}_low_signal_dominated")

    return {
        "scene_id": metadata.scene_id,
        "product_id": metadata.product_id,
        "orbit_direction": metadata.orbit_direction,
        "relative_orbit": metadata.relative_orbit,
        "platform": metadata.platform,
        "quality_class": qa.quality_class.value,
        "why_used": why_used,
        "why_downweighted": why_downweighted,
        "missing_bands": missing_bands,
        "bad_features": bad_features,
        "qa_flags": qa.flags,
        "zone_failures": zone_failures,
        "kalman_observations_created": kalman_count,
        "kalman_observations_skipped": kalman_skipped or [
            "flood_score_not_direct_state",
            "roughness_proxy_context_dependent",
            "emergence_signal_deferred",
        ],
    }
