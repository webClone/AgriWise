"""
Sentinel-2 Provenance — Trust report generation.

Every Sentinel2ScenePackage must have complete provenance.
This module validates and generates trust report entries.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.sentinel2.schemas import Sentinel2ScenePackage


def validate_provenance(pkg: Sentinel2ScenePackage) -> List[str]:
    """
    Validate that all mandatory provenance fields are present.
    Returns list of error messages (empty = valid).
    """
    return pkg.metadata.validate()


def generate_trust_report(pkg: Sentinel2ScenePackage) -> Dict[str, Any]:
    """Generate a trust report entry for Sentinel-2."""
    meta = pkg.metadata
    qa = pkg.qa
    summary = pkg.plot_summary

    indices_used = []
    for idx in ["NDVI", "EVI", "NDMI", "NDRE", "BSI"]:
        attr = f"{idx.lower()}_mean"
        if getattr(summary, attr, None) is not None:
            indices_used.append(idx)

    # Determine limitations
    limitations = []
    if not qa.usable:
        limitations.append(f"Scene unusable: {qa.reason}")
    if qa.cloud_fraction > 0.15:
        limitations.append(f"Cloud fraction {qa.cloud_fraction:.0%}")
    if qa.shadow_fraction > 0.10:
        limitations.append(f"Shadow fraction {qa.shadow_fraction:.0%}")
    if summary.boundary_contamination_score > 0.1:
        limitations.append(f"Boundary contamination {summary.boundary_contamination_score:.2f}")
    if "STALE" in qa.flags:
        limitations.append("Scene is stale (>45 days)")
    if "CLOUD_QA_MISSING" in qa.flags:
        limitations.append("Cloud QA data missing")

    degraded_zones = [
        zs.zone_id for zs in pkg.zone_summaries
        if zs.valid_fraction < 0.5
    ]

    return {
        "sentinel2": {
            "scene_id": meta.scene_id,
            "acquisition_datetime": (
                meta.acquisition_datetime.isoformat()
                if meta.acquisition_datetime else None
            ),
            "provider": meta.provider,
            "quality_class": qa.quality_class.value,
            "valid_fraction": qa.valid_fraction,
            "cloud_fraction": qa.cloud_fraction,
            "shadow_fraction": qa.shadow_fraction,
            "indices_used": indices_used,
            "zones_degraded": degraded_zones,
            "reliability": qa.reliability_weight,
            "sigma_multiplier": qa.sigma_multiplier,
            "main_limitations": limitations or ["none"],
            "flags": qa.flags,
        }
    }
