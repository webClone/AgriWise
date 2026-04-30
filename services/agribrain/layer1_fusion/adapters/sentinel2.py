"""
Sentinel-2 source adapter.

Extracts NDVI, NDMI, NDRE, LAI proxy, chlorophyll proxy, canopy cover,
cloud/shadow QA, zone summaries, scene provenance, and raster stack refs.

Rules:
- Cloudy or shadowed zones → lower confidence
- Byte-scaled RGB → never used as scientific index
- Zone QA remains zone-specific
- No temporal feature invented unless package provides it
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, List

from layer1_fusion.schemas import (
    EvidenceItem,
    Layer1InputBundle,
    SourceEnvelope,
)


class Sentinel2Adapter:
    source_family = "sentinel2"

    def can_read(self, package: Any) -> bool:
        return package is not None and hasattr(package, "plot_id")

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id
        acq_dt = getattr(getattr(package, "metadata", None), "acquisition_datetime", None)
        scene_id = getattr(getattr(package, "metadata", None), "scene_id", "") or ""
        qa = getattr(package, "qa", None)
        usable = getattr(qa, "usable", True) if qa else True
        reliability = getattr(qa, "reliability_weight", 0.8) if qa else 0.8
        cloud_frac = getattr(qa, "cloud_fraction", 0.0) if qa else 0.0

        # Confidence penalty for cloud/shadow
        base_confidence = max(0.0, min(0.85, reliability * (1.0 - cloud_frac)))

        # Uncertainty (sigma): higher cloud + lower reliability → higher sigma
        base_sigma = round((1.0 - reliability) * (1.0 + cloud_frac), 4)

        ps = getattr(package, "plot_summary", None)
        if ps is None:
            return items

        # Extract plot-level indices
        _index_fields = [
            ("ndvi_mean", "ndvi", "index"),
            ("ndmi_mean", "ndmi", "index"),
            ("ndre_mean", "ndre", "index"),
            ("evi_mean", "evi", "index"),
            ("bsi_mean", "bsi", "index"),
        ]
        for attr, var, unit in _index_fields:
            val = getattr(ps, attr, None)
            if val is not None:
                items.append(EvidenceItem(
                    evidence_id=f"s2_{scene_id}_{var}",
                    plot_id=plot_id,
                    variable=var,
                    value=val,
                    unit=unit,
                    source_family="sentinel2",
                    source_id=scene_id,
                    observation_type="measurement",
                    spatial_scope="plot",
                    observed_at=acq_dt,
                    confidence=base_confidence,
                    sigma=base_sigma,
                    reliability=reliability,
                    freshness_score=0.0,  # set by freshness engine
                    provenance_ref=f"s2_scene_{scene_id}",
                    flags=["CLOUDY"] if cloud_frac > 0.3 else [],
                ))

        # Extract vegetation fractions
        for attr, var in [
            ("vegetation_fraction_scl", "vegetation_fraction"),
            ("bare_soil_fraction_scl", "bare_soil_fraction"),
        ]:
            val = getattr(ps, attr, None)
            if val is not None:
                items.append(EvidenceItem(
                    evidence_id=f"s2_{scene_id}_{var}",
                    plot_id=plot_id,
                    variable=var,
                    value=val,
                    unit="fraction",
                    source_family="sentinel2",
                    source_id=scene_id,
                    observation_type="derived_feature",
                    spatial_scope="plot",
                    observed_at=acq_dt,
                    confidence=base_confidence,
                    reliability=reliability,
                    freshness_score=0.0,
                    provenance_ref=f"s2_scene_{scene_id}",
                ))

        # Extract zone summaries (preserve zone scope)
        for zs in getattr(package, "zone_summaries", []):
            zone_id = getattr(zs, "zone_id", "")
            z_reliability = getattr(zs, "reliability", reliability)
            z_cloud = getattr(zs, "cloud_fraction", cloud_frac)
            z_conf = max(0.0, min(0.85, z_reliability * (1.0 - z_cloud)))
            z_sigma = round((1.0 - z_reliability) * (1.0 + z_cloud), 4)

            for attr, var in [("ndvi_mean", "ndvi"), ("ndmi_mean", "ndmi"), ("ndre_mean", "ndre")]:
                val = getattr(zs, attr, None)
                if val is not None:
                    items.append(EvidenceItem(
                        evidence_id=f"s2_{scene_id}_{zone_id}_{var}",
                        plot_id=plot_id,
                        variable=var,
                        value=val,
                        unit="index",
                        source_family="sentinel2",
                        source_id=scene_id,
                        observation_type="measurement",
                        spatial_scope="zone",
                        scope_id=zone_id,
                        observed_at=acq_dt,
                        confidence=z_conf,
                        sigma=z_sigma,
                        reliability=z_reliability,
                        freshness_score=0.0,
                        provenance_ref=f"s2_scene_{scene_id}_zone_{zone_id}",
                    ))

        # Raster refs (preserve raster scope)
        for idx_name, raster in getattr(package, "indices", {}).items():
            content_hash = getattr(raster, "content_hash", None) or ""
            items.append(EvidenceItem(
                evidence_id=f"s2_{scene_id}_raster_{idx_name}",
                plot_id=plot_id,
                variable=f"{idx_name}_raster",
                value=content_hash,
                unit=None,
                source_family="sentinel2",
                source_id=scene_id,
                observation_type="measurement",
                spatial_scope="raster",
                observed_at=acq_dt,
                confidence=base_confidence,
                reliability=reliability,
                freshness_score=0.0,
                provenance_ref=f"s2_scene_{scene_id}_raster_{idx_name}",
                flags=["RASTER_REF"],
            ))

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="sentinel2_missing",
                source_family="sentinel2",
                source_name="Sentinel-2 L2A",
                package_id="",
                package_version="",
                source_status="missing",
            )

        meta = getattr(package, "metadata", None)
        qa = getattr(package, "qa", None)

        return SourceEnvelope(
            source_id=getattr(meta, "scene_id", "") if meta else "",
            source_family="sentinel2",
            source_name="Sentinel-2 L2A",
            package_id=getattr(meta, "scene_id", "") if meta else "",
            package_version=getattr(meta, "qa_version", "s2qa_v1") if meta else "",
            input_hash=getattr(meta, "grid_alignment_hash", None) if meta else None,
            produced_at=None,
            observed_start=getattr(meta, "acquisition_datetime", None) if meta else None,
            observed_end=getattr(meta, "acquisition_datetime", None) if meta else None,
            spatial_scope="plot",
            temporal_scope="instant",
            trust_score=getattr(qa, "reliability_weight", 0.8) if qa else 0.0,
            source_status="ok" if (qa and getattr(qa, "usable", False)) else "degraded",
        )
