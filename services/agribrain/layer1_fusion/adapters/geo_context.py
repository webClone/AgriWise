"""
Geo context source adapter.

Extracts DEM, landcover, WaPOR, trust modifiers, plot validity,
and sensor placement guidance.

Rules:
- DEM/elevation/slope are static site priors
- Landcover is static prior — NEVER crop health diagnosis
- WaPOR is coarse proxy — NEVER plot truth
- Trust modifiers feed confidence model, not diagnosis
"""

from __future__ import annotations

from typing import Any, List

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle, SourceEnvelope


class GeoContextAdapter:
    source_family = "geo_context"

    def can_read(self, package: Any) -> bool:
        return package is not None and hasattr(package, "plot_id")

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id
        pkg_id = f"geo_{plot_id}"

        # --- DEM context (static) ---
        dem = getattr(package, "dem_context", None)
        if dem is not None:
            dem_dict = dem if isinstance(dem, dict) else {}
            for attr, var, unit in [
                ("elevation_mean", "elevation", "cm"),
                ("slope_mean", "slope", "deg"),
                ("aspect_mean", "aspect", "deg"),
            ]:
                val = dem_dict.get(attr) if isinstance(dem_dict, dict) else getattr(dem, attr, None)
                if val is not None:
                    items.append(EvidenceItem(
                        evidence_id=f"geo_dem_{var}",
                        plot_id=plot_id,
                        variable=var,
                        value=val,
                        unit=unit,
                        source_family="geo_context",
                        source_id="dem",
                        observation_type="static_prior",
                        spatial_scope="plot",
                        confidence=0.85,
                        reliability=0.90,
                        freshness_score=1.0,
                        provenance_ref=f"geo_dem_{plot_id}",
                    ))

        # --- Landcover (static prior, NOT crop diagnosis) ---
        lc = getattr(package, "landcover_context", None)
        if lc is not None:
            lc_dict = lc if isinstance(lc, dict) else {}
            for attr, var in [
                ("cropland_fraction", "landcover_cropland_fraction"),
                ("forest_fraction", "landcover_forest_fraction"),
                ("water_fraction", "landcover_water_fraction"),
                ("builtup_fraction", "landcover_builtup_fraction"),
            ]:
                val = lc_dict.get(attr) if isinstance(lc_dict, dict) else getattr(lc, attr, None)
                if val is not None:
                    items.append(EvidenceItem(
                        evidence_id=f"geo_lc_{var}",
                        plot_id=plot_id,
                        variable=var,
                        value=val,
                        unit="fraction",
                        source_family="geo_context",
                        source_id="landcover",
                        observation_type="static_prior",
                        spatial_scope="plot",
                        confidence=0.70,
                        reliability=0.75,
                        freshness_score=1.0,
                        provenance_ref=f"geo_lc_{plot_id}",
                        diagnostic_only=True,
                        state_update_allowed=False,
                    ))

        # --- Plot validity ---
        pv = getattr(package, "plot_validity", None)
        if pv is not None:
            items.append(EvidenceItem(
                evidence_id=f"geo_validity_{plot_id}",
                plot_id=plot_id,
                variable="plot_cropland_confidence",
                value=getattr(pv, "cropland_confidence", 0.0),
                unit="score",
                source_family="geo_context",
                source_id="plot_validity",
                observation_type="derived_feature",
                spatial_scope="plot",
                confidence=0.70,
                reliability=0.70,
                freshness_score=1.0,
                provenance_ref=f"geo_validity_{plot_id}",
            ))

        # --- Trust modifiers (feed confidence model) ---
        tm = getattr(package, "satellite_trust_modifiers", None)
        if tm is not None:
            for attr, var in [
                ("sentinel2_boundary_risk", "s2_boundary_risk"),
                ("sentinel1_terrain_risk", "s1_terrain_risk"),
            ]:
                val = getattr(tm, attr, None)
                if val is not None:
                    items.append(EvidenceItem(
                        evidence_id=f"geo_trust_{var}",
                        plot_id=plot_id,
                        variable=var,
                        value=val,
                        unit="score",
                        source_family="geo_context",
                        source_id="trust_modifiers",
                        observation_type="derived_feature",
                        spatial_scope="edge" if "boundary" in var else "plot",
                        confidence=0.80,
                        reliability=0.80,
                        freshness_score=1.0,
                        provenance_ref=f"geo_trust_{plot_id}",
                        diagnostic_only=True,
                        state_update_allowed=False,
                    ))

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="geo_context_missing", source_family="geo_context",
                source_name="Geo Context", package_id="", package_version="",
                source_status="missing",
            )
        return SourceEnvelope(
            source_id=f"geo_{getattr(package, 'plot_id', '')}",
            source_family="geo_context",
            source_name="Geo Context V1",
            package_id=f"geo_{getattr(package, 'plot_id', '')}",
            package_version="geo_v1",
            spatial_scope="plot",
            temporal_scope="static",
            trust_score=0.75,
            source_status="ok",
        )
