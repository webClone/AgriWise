"""
Environment source adapter.

Extracts SoilGrids profile, FAO context, weather consensus,
process forcing, soil AWC, and modelled soil moisture (weak evidence).

Rules:
- SoilGrids/FAO are static priors
- Weather is forcing, not crop diagnosis
- Modelled soil moisture is weak evidence (capped at 0.35)
"""

from __future__ import annotations

from typing import Any, List

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle, SourceEnvelope


class EnvironmentAdapter:
    source_family = "environment"

    def can_read(self, package: Any) -> bool:
        return package is not None and hasattr(package, "plot_id")

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id
        pkg_id = f"env_{plot_id}"

        # --- SoilGrids static priors ---
        soil = getattr(package, "soilgrids_profile", None)
        if soil is not None:
            soil_dict = soil if isinstance(soil, dict) else (
                {k: getattr(soil, k, None) for k in ["clay", "sand", "silt", "ph", "soc", "cec", "nitrogen"]}
                if soil else {}
            )
            for var, val in (soil_dict.items() if isinstance(soil_dict, dict) else []):
                if val is not None:
                    items.append(EvidenceItem(
                        evidence_id=f"env_soilgrids_{var}",
                        plot_id=plot_id,
                        variable=f"soil_{var}",
                        value=val,
                        unit=None,
                        source_family="environment",
                        source_id="soilgrids",
                        observation_type="static_prior",
                        spatial_scope="plot",
                        confidence=0.65,
                        reliability=0.75,
                        freshness_score=1.0,  # static → no decay
                        provenance_ref=f"soilgrids_{plot_id}",
                    ))

        # --- Process parameters (AWC) ---
        pp = getattr(package, "process_parameters", None)
        if pp is not None:
            for attr, var in [
                ("field_capacity_vol_pct", "soil_field_capacity"),
                ("wilting_point_vol_pct", "soil_wilting_point"),
                ("whc_mm_per_m", "soil_whc"),
            ]:
                val = getattr(pp, attr, None)
                if val is not None:
                    items.append(EvidenceItem(
                        evidence_id=f"env_pp_{var}",
                        plot_id=plot_id,
                        variable=var,
                        value=val,
                        unit="mm" if "mm" in var else "percent",
                        source_family="environment",
                        source_id=getattr(pp, "soil_source", "soilgrids"),
                        observation_type="static_prior",
                        spatial_scope="plot",
                        confidence=0.60,
                        reliability=0.70,
                        freshness_score=1.0,
                        provenance_ref=f"env_pp_{plot_id}",
                    ))

        # --- Weather consensus ---
        for wc in getattr(package, "weather_consensus", []):
            date = getattr(wc, "date", None) or (wc.get("date") if isinstance(wc, dict) else None)
            wc_dict = wc if isinstance(wc, dict) else {
                k: getattr(wc, k, None) for k in
                ["precipitation_mm", "temp_mean", "temp_min", "temp_max", "et0_mm", "vpd_kpa"]
            }
            for var, val in wc_dict.items():
                if val is not None and var != "date":
                    items.append(EvidenceItem(
                        evidence_id=f"env_wx_{date}_{var}",
                        plot_id=plot_id,
                        variable=f"weather_{var}",
                        value=val,
                        unit="mm" if "mm" in var or "precip" in var else "degC" if "temp" in var else None,
                        source_family="environment",
                        source_id="weather_consensus",
                        observation_type="model_estimate",
                        spatial_scope="plot",
                        confidence=0.70,
                        reliability=0.65,
                        freshness_score=0.0,
                        provenance_ref=f"env_wx_{plot_id}_{date}",
                    ))

        # --- Weak Kalman observations (modelled soil moisture) ---
        for wko in getattr(package, "weak_kalman_observations", []):
            items.append(EvidenceItem(
                evidence_id=f"env_weak_{getattr(wko, 'obs_type', 'sm')}",
                plot_id=plot_id,
                variable=getattr(wko, "state_maps_to", "modelled_sm"),
                value=getattr(wko, "value", 0.0),
                unit="fraction",
                source_family="environment",
                source_id=getattr(wko, "source", "open_meteo"),
                observation_type="model_estimate",
                spatial_scope="plot",
                confidence=min(0.35, getattr(wko, "reliability", 0.30)),  # capped weak
                sigma=getattr(wko, "sigma", 0.15),
                reliability=getattr(wko, "reliability", 0.30),
                freshness_score=0.0,
                provenance_ref=f"env_weak_sm_{plot_id}",
                flags=["WEAK_EVIDENCE", "MODEL_NOT_OBSERVATION"],
            ))

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="environment_missing", source_family="environment",
                source_name="Environmental Context", package_id="", package_version="",
                source_status="missing",
            )
        qa = getattr(package, "qa", None)
        qc = getattr(qa, "quality_class", None) if qa else None
        status = "ok" if qc and qc.value == "good" else "degraded"
        return SourceEnvelope(
            source_id=f"env_{getattr(package, 'plot_id', '')}",
            source_family="environment",
            source_name="Environmental Context V1",
            package_id=f"env_{getattr(package, 'plot_id', '')}",
            package_version="env_v1",
            spatial_scope="plot",
            temporal_scope="daily",
            trust_score=0.65,
            source_status=status,
        )
