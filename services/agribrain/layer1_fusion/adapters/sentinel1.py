"""
Sentinel-1 SAR source adapter.

Extracts VV, VH, VV/VH ratio, RVI, surface wetness proxy, flood score,
roughness proxy, incidence QA, speckle QA, orbit metadata, and zone summaries.

Rules:
- Flood/roughness/emergence remain event/diagnostic context
- Missing incidence → lower confidence
- SAR moisture proxy is weak unless confirmed by sensors/rain/weather
"""

from __future__ import annotations

from typing import Any, List

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle, SourceEnvelope


class Sentinel1Adapter:
    source_family = "sentinel1"

    def can_read(self, package: Any) -> bool:
        return package is not None and hasattr(package, "plot_id")

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id
        meta = getattr(package, "metadata", None)
        scene_id = getattr(meta, "scene_id", "") if meta else ""
        acq_dt = getattr(meta, "acquisition_datetime", None) if meta else None
        qa = getattr(package, "qa", None)
        reliability = getattr(qa, "reliability_weight", 0.7) if qa else 0.7
        speckle = getattr(qa, "speckle_score", 1.0) if qa else 1.0
        base_conf = max(0.0, min(0.65, reliability * speckle))

        ps = getattr(package, "plot_summary", None)
        if ps is None:
            return items

        # Plot-level SAR features
        _sar_fields = [
            ("vv_db_mean", "vv_db", "db"),
            ("vh_db_mean", "vh_db", "db"),
            ("vv_vh_ratio_mean", "vv_vh_ratio", "ratio"),
            ("rvi_mean", "rvi", "index"),
            ("surface_wetness_proxy_mean", "sar_wetness_proxy", "score"),
        ]
        for attr, var, unit in _sar_fields:
            val = getattr(ps, attr, None)
            if val is not None:
                obs_type = "measurement"
                diag_only = False
                if var == "sar_wetness_proxy":
                    obs_type = "derived_feature"
                items.append(EvidenceItem(
                    evidence_id=f"s1_{scene_id}_{var}",
                    plot_id=plot_id,
                    variable=var,
                    value=val,
                    unit=unit,
                    source_family="sentinel1",
                    source_id=scene_id,
                    observation_type=obs_type,
                    spatial_scope="plot",
                    observed_at=acq_dt,
                    confidence=base_conf,
                    reliability=reliability,
                    freshness_score=0.0,
                    provenance_ref=f"s1_scene_{scene_id}",
                    diagnostic_only=diag_only,
                ))

        # Flood and roughness are diagnostic only
        for attr, var in [("flood_score", "sar_flood_score"), ("roughness_proxy", "sar_roughness_proxy")]:
            val = getattr(ps, attr, None)
            if val is not None:
                items.append(EvidenceItem(
                    evidence_id=f"s1_{scene_id}_{var}",
                    plot_id=plot_id,
                    variable=var,
                    value=val,
                    unit="score",
                    source_family="sentinel1",
                    source_id=scene_id,
                    observation_type="diagnostic",
                    spatial_scope="plot",
                    observed_at=acq_dt,
                    confidence=base_conf * 0.8,
                    reliability=reliability,
                    freshness_score=0.0,
                    provenance_ref=f"s1_scene_{scene_id}",
                    diagnostic_only=True,
                    state_update_allowed=False,
                ))

        # Zone summaries
        for zs in getattr(package, "zone_summaries", []):
            zone_id = getattr(zs, "zone_id", "")
            z_rel = getattr(zs, "reliability", reliability)
            z_conf = max(0.0, min(0.65, z_rel))

            for attr, var, unit in [
                ("vv_db_mean", "vv_db", "db"),
                ("vh_db_mean", "vh_db", "db"),
                ("surface_wetness_proxy_mean", "sar_wetness_proxy", "score"),
            ]:
                val = getattr(zs, attr, None)
                if val is not None:
                    items.append(EvidenceItem(
                        evidence_id=f"s1_{scene_id}_{zone_id}_{var}",
                        plot_id=plot_id,
                        variable=var,
                        value=val,
                        unit=unit,
                        source_family="sentinel1",
                        source_id=scene_id,
                        observation_type="measurement" if var != "sar_wetness_proxy" else "derived_feature",
                        spatial_scope="zone",
                        scope_id=zone_id,
                        observed_at=acq_dt,
                        confidence=z_conf,
                        reliability=z_rel,
                        freshness_score=0.0,
                        provenance_ref=f"s1_scene_{scene_id}_zone_{zone_id}",
                    ))

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="sentinel1_missing", source_family="sentinel1",
                source_name="Sentinel-1 GRD", package_id="", package_version="",
                source_status="missing",
            )
        meta = getattr(package, "metadata", None)
        qa = getattr(package, "qa", None)
        return SourceEnvelope(
            source_id=getattr(meta, "scene_id", "") if meta else "",
            source_family="sentinel1",
            source_name="Sentinel-1 GRD",
            package_id=getattr(meta, "scene_id", "") if meta else "",
            package_version=getattr(meta, "sar_version", "s1sar_v1") if meta else "",
            observed_start=getattr(meta, "acquisition_datetime", None) if meta else None,
            observed_end=getattr(meta, "acquisition_datetime", None) if meta else None,
            spatial_scope="plot",
            temporal_scope="instant",
            trust_score=getattr(qa, "reliability_weight", 0.7) if qa else 0.0,
            source_status="ok" if (qa and getattr(qa, "usable", False)) else "degraded",
        )
