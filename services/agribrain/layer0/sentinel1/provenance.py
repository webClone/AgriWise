"""
Sentinel-1 SAR Provenance Validation.

Mandatory metadata fields are fatal if missing — raises SARProvenanceError.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.sentinel1.schemas import (
    Sentinel1PlotSummary,
    Sentinel1QAResult,
    Sentinel1SceneMetadata,
)


class SARProvenanceError(Exception):
    """Raised when mandatory SAR provenance fields are missing."""
    pass


MANDATORY_FIELDS = [
    "scene_id", "product_id", "acquisition_datetime", "provider",
    "crs", "plot_geometry_hash", "platform", "relative_orbit",
]


def validate_sar_provenance(metadata: Sentinel1SceneMetadata) -> None:
    """
    Validate mandatory provenance fields.

    Raises SARProvenanceError if any mandatory field is missing or empty.
    """
    errors = metadata.validate()
    if errors:
        raise SARProvenanceError(
            f"Missing mandatory SAR provenance fields: {errors}"
        )


def build_sar_trust_report(
    metadata: Sentinel1SceneMetadata,
    qa: Sentinel1QAResult,
    plot_summary: Optional[Sentinel1PlotSummary] = None,
) -> Dict[str, Any]:
    """Build a trust report for the SAR observation."""
    features_used = []
    if plot_summary:
        if plot_summary.vv_db_mean is not None:
            features_used.append("VV_DB")
        if plot_summary.vh_db_mean is not None:
            features_used.append("VH_DB")
        if plot_summary.rvi_mean is not None:
            features_used.append("RVI")
        if plot_summary.vv_vh_ratio_mean is not None:
            features_used.append("VV_VH_RATIO")
        if plot_summary.surface_wetness_proxy_mean is not None:
            features_used.append("SURFACE_WETNESS_PROXY")
        if plot_summary.structure_proxy_mean is not None:
            features_used.append("STRUCTURE_PROXY")

    used_for = []
    if plot_summary and plot_summary.surface_wetness_proxy_mean is not None:
        used_for.append("surface_moisture")
    if plot_summary and plot_summary.structure_proxy_mean is not None:
        used_for.append("structure")

    return {
        "sentinel1": {
            "last_usable_scene": (
                metadata.acquisition_datetime.isoformat()
                if metadata.acquisition_datetime and qa.usable else None
            ),
            "quality": qa.quality_class.value,
            "valid_fraction": qa.valid_fraction,
            "orbit_direction": metadata.orbit_direction,
            "relative_orbit": metadata.relative_orbit,
            "platform": metadata.platform,
            "features_used": features_used,
            "reliability": qa.reliability_weight,
            "main_limitations": qa.flags,
            "used_for": used_for,
            "not_calibrated_soil_moisture": True,
        }
    }
