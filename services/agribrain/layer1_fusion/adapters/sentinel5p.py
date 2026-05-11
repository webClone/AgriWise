"""
Sentinel-5P (TROPOMI) source adapter — Solar-Induced Fluorescence (SIF).

Extracts regional SIF measurements from Sentinel-5P packages.
SIF directly measures photosynthetic activity — it drops to zero
days/weeks before NDVI when plants experience acute stress.

Resolution: ~7km — plot-level spatial scope with confidence ceiling 0.70.
Daily cadence (vs S2's 5-day), making it a powerful temporal indicator.

Rules:
- SIF is ALWAYS plot-scope (7km pixel covers entire field)
- Confidence ceiling 0.70 (coarse spatial resolution)
- No zone-level SIF (would be spatially dishonest)
- Clear radiance quality filter (cloud-free observations only)
"""

from __future__ import annotations

from typing import Any, List

from layer1_fusion.schemas import (
    EvidenceItem,
    Layer1InputBundle,
    SourceEnvelope,
)


class Sentinel5PAdapter:
    source_family = "sentinel5p"

    def can_read(self, package: Any) -> bool:
        if package is None:
            return False
        # Requires at minimum a SIF value
        return hasattr(package, "sif_mean") or (
            isinstance(package, dict) and "sif_mean" in package
        )

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id

        # Extract from object or dict
        if isinstance(package, dict):
            sif_mean = package.get("sif_mean")
            acq_dt = package.get("acquisition_datetime")
            scene_id = package.get("scene_id", "")
            cloud_frac = package.get("cloud_fraction", 0.0)
            reliability = package.get("reliability_weight", 0.6)
            pri_mean = package.get("pri_mean")
        else:
            sif_mean = getattr(package, "sif_mean", None)
            acq_dt = getattr(package, "acquisition_datetime", None)
            scene_id = getattr(package, "scene_id", "") or ""
            qa = getattr(package, "qa", None)
            cloud_frac = getattr(qa, "cloud_fraction", 0.0) if qa else 0.0
            reliability = getattr(qa, "reliability_weight", 0.6) if qa else 0.6
            pri_mean = getattr(package, "pri_mean", None)

        # Confidence ceiling for 7km resolution — spatially imprecise
        base_confidence = min(0.70, max(0.0, reliability * (1.0 - cloud_frac)))
        base_sigma = round(0.15 + (1.0 - reliability) * 0.1, 4)

        # SIF evidence
        if sif_mean is not None:
            items.append(EvidenceItem(
                evidence_id=f"s5p_{scene_id}_sif",
                plot_id=plot_id,
                variable="sif",
                value=sif_mean,
                unit="index",  # Normalized SIF (0–2 mW/m²/sr/nm range)
                source_family="sentinel5p",
                source_id=scene_id,
                observation_type="measurement",
                spatial_scope="plot",  # Always plot — 7km pixel
                observed_at=acq_dt,
                confidence=base_confidence,
                sigma=base_sigma,
                reliability=reliability,
                freshness_score=0.0,  # Set by freshness engine
                provenance_ref=f"s5p_tropomi_{scene_id}",
                flags=["COARSE_RESOLUTION"] if cloud_frac < 0.1 else ["COARSE_RESOLUTION", "CLOUDY"],
            ))

        # PRI evidence (if provided — e.g., pseudo-PRI computed from S2)
        if pri_mean is not None:
            pri_confidence = min(0.65, base_confidence)
            items.append(EvidenceItem(
                evidence_id=f"s5p_{scene_id}_pri",
                plot_id=plot_id,
                variable="pri",
                value=pri_mean,
                unit="index",
                source_family="sentinel5p",
                source_id=scene_id,
                observation_type="derived_feature",
                spatial_scope="plot",
                observed_at=acq_dt,
                confidence=pri_confidence,
                sigma=round(base_sigma * 0.8, 4),  # PRI slightly less uncertain
                reliability=reliability,
                freshness_score=0.0,
                provenance_ref=f"s5p_tropomi_{scene_id}_pri",
                flags=["PSEUDO_PRI"],
            ))

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="sentinel5p_missing",
                source_family="sentinel5p",
                source_name="Sentinel-5P TROPOMI (SIF)",
                package_id="",
                package_version="",
                source_status="missing",
            )

        if isinstance(package, dict):
            scene_id = package.get("scene_id", "")
            acq_dt = package.get("acquisition_datetime")
            reliability = package.get("reliability_weight", 0.6)
        else:
            scene_id = getattr(package, "scene_id", "") or ""
            acq_dt = getattr(package, "acquisition_datetime", None)
            qa = getattr(package, "qa", None)
            reliability = getattr(qa, "reliability_weight", 0.6) if qa else 0.6

        return SourceEnvelope(
            source_id=scene_id,
            source_family="sentinel5p",
            source_name="Sentinel-5P TROPOMI (SIF)",
            package_id=scene_id,
            package_version="s5p_sif_v1",
            observed_start=acq_dt,
            observed_end=acq_dt,
            spatial_scope="plot",
            temporal_scope="daily",
            trust_score=reliability,
            source_status="ok" if reliability > 0.3 else "degraded",
        )
