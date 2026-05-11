"""
Layer 0 State source adapter.

Extracts Kalman state vectors, zone reliability weights, and
ValidationGraph outputs from the layer0_state_package into the
Layer 1 evidence ledger.

The layer0_state_package is a dict assembled by the orchestrator,
containing:
  - zone_summaries: [{zone_id, label, area_fraction, ...}]
  - source_reliability: {source: weight}  (from ValidationGraph)
  - zone_reliability: {zone_id: {source: weight}}
  - state_vectors: {variable: value}  (Kalman-filtered daily state)
  - edge_contamination: [{edge_id, contamination_score}]
  - biomass_proxy: float
  - lai_proxy: float
  - sm_0_10: float (soil moisture 0-10cm)
  - phenology_gdd: float
  - phenology_stage: float

Rules:
- All L0 state data is observation_type="state_estimate"
- Zone summaries are spatial_scope="zone" with scope_id
- State vectors are spatial_scope="plot"
- Source reliability weights are diagnostic_only (inform fusion confidence,
  but do not create new state)
- Edge contamination data is spatial_scope="edge"
"""

from __future__ import annotations

from typing import Any, Dict, List

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle, SourceEnvelope


class Layer0StateAdapter:
    source_family = "l0_state"

    def can_read(self, package: Any) -> bool:
        """Read if package is a non-empty dict."""
        if package is None:
            return False
        if isinstance(package, dict):
            return len(package) > 0
        # Also accept objects with at least a zone_summaries attribute
        return hasattr(package, "zone_summaries")

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id
        run_ts = context.run_timestamp
        run_id = context.run_id

        # Normalize access
        def _get(key: str, default=None):
            if isinstance(package, dict):
                return package.get(key, default)
            return getattr(package, key, default)

        idx = 0

        def _add(variable: str, value: Any, unit: str,
                 spatial_scope: str = "plot",
                 scope_id: str = None,
                 confidence: float = 0.70,
                 reliability: float = 0.75,
                 diagnostic_only: bool = False,
                 flags: list = None):
            nonlocal idx
            items.append(EvidenceItem(
                evidence_id=f"l0_state_{run_id}_{variable}_{idx}",
                plot_id=plot_id,
                variable=variable,
                value=value,
                unit=unit,
                source_family="l0_state",
                source_id=f"l0_state_{run_id}",
                observation_type="state_estimate",
                spatial_scope=spatial_scope,
                scope_id=scope_id,
                observed_at=run_ts,
                confidence=confidence,
                reliability=reliability,
                freshness_score=1.0,  # L0 state is always current-day
                provenance_ref=f"l0_state_{run_id}_{plot_id}",
                diagnostic_only=diagnostic_only,
                state_update_allowed=not diagnostic_only,
                flags=flags or [],
            ))
            idx += 1

        # ---- Zone summaries ----
        zone_summaries = _get("zone_summaries", [])
        for zs in zone_summaries:
            if not isinstance(zs, dict):
                continue
            zone_id = zs.get("zone_id", "")
            if not zone_id:
                continue

            label = zs.get("label", "")
            area_frac = zs.get("area_fraction", 0.0)

            _add(
                variable="zone_label",
                value=label,
                unit="class",
                spatial_scope="zone",
                scope_id=zone_id,
                confidence=0.75,
            )
            _add(
                variable="zone_area_fraction",
                value=float(area_frac),
                unit="fraction",
                spatial_scope="zone",
                scope_id=zone_id,
                confidence=0.80,
            )

            # Propagate any zone-level state variables
            for key in ("ndvi_mean", "ndmi_mean", "sm_mean", "lai_mean"):
                val = zs.get(key)
                if val is not None:
                    var_name = key.replace("_mean", "")
                    _add(
                        variable=f"l0_{var_name}",
                        value=float(val),
                        unit="index" if "ndvi" in key or "ndmi" in key else "fraction",
                        spatial_scope="zone",
                        scope_id=zone_id,
                        confidence=0.70,
                    )

        # ---- Plot-level state vectors ----
        state_vectors = _get("state_vectors", {})
        if isinstance(state_vectors, dict):
            KNOWN_STATE_VARS = {
                "lai_proxy": ("fraction", 0.75),
                "biomass_proxy": ("fraction", 0.70),
                "sm_0_10": ("fraction", 0.75),
                "sm_10_30": ("fraction", 0.70),
                "phenology_gdd": ("degC", 0.65),
                "phenology_stage": ("class", 0.65),
                "canopy_cover": ("fraction", 0.70),
            }
            for var, val in state_vectors.items():
                if val is None:
                    continue
                unit, conf = KNOWN_STATE_VARS.get(var, ("score", 0.60))
                _add(
                    variable=f"l0_{var}",
                    value=float(val) if isinstance(val, (int, float)) else val,
                    unit=unit,
                    confidence=conf,
                )

        # Also check for top-level state vars (legacy format)
        for top_var in ("biomass_proxy", "lai_proxy", "sm_0_10",
                        "phenology_gdd", "phenology_stage"):
            val = _get(top_var)
            if val is not None and not state_vectors.get(top_var):
                unit_map = {
                    "biomass_proxy": "fraction",
                    "lai_proxy": "fraction",
                    "sm_0_10": "fraction",
                    "phenology_gdd": "degC",
                    "phenology_stage": "class",
                }
                _add(
                    variable=f"l0_{top_var}",
                    value=float(val) if isinstance(val, (int, float)) else val,
                    unit=unit_map.get(top_var, "score"),
                    confidence=0.70,
                )

        # ---- Source reliability weights (diagnostic) ----
        source_rel = _get("source_reliability", {})
        if isinstance(source_rel, dict) and source_rel:
            for src, weight in source_rel.items():
                _add(
                    variable=f"l0_reliability_{src}",
                    value=float(weight),
                    unit="score",
                    confidence=0.90,
                    reliability=0.90,
                    diagnostic_only=True,
                    flags=["L0_VALIDATION_GRAPH"],
                )

        # ---- Zone-level reliability (diagnostic) ----
        zone_rel = _get("zone_reliability", {})
        if isinstance(zone_rel, dict):
            for zone_id, src_weights in zone_rel.items():
                if not isinstance(src_weights, dict):
                    continue
                for src, weight in src_weights.items():
                    _add(
                        variable=f"l0_zone_reliability_{src}",
                        value=float(weight),
                        unit="score",
                        spatial_scope="zone",
                        scope_id=zone_id,
                        confidence=0.90,
                        reliability=0.90,
                        diagnostic_only=True,
                        flags=["L0_VALIDATION_GRAPH", "ZONE_SPECIFIC"],
                    )

        # ---- Edge contamination ----
        edge_data = _get("edge_contamination", [])
        for edge in edge_data:
            if not isinstance(edge, dict):
                continue
            edge_id = edge.get("edge_id", "")
            cont_score = edge.get("contamination_score", 0.0)
            if edge_id:
                _add(
                    variable="edge_contamination_score",
                    value=float(cont_score),
                    unit="score",
                    spatial_scope="edge",
                    scope_id=edge_id,
                    confidence=0.80,
                )

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="l0_state_missing",
                source_family="l0_state",
                source_name="Layer 0 State Vector",
                package_id="",
                package_version="",
                source_status="missing",
            )

        # Check data richness to determine health
        def _get(key, default=None):
            if isinstance(package, dict):
                return package.get(key, default)
            return getattr(package, key, default)

        has_zones = bool(_get("zone_summaries", []))
        has_state = bool(_get("state_vectors", {}))
        has_reliability = bool(_get("source_reliability", {}))
        has_edges = bool(_get("edge_contamination", []))

        richness = sum([has_zones, has_state, has_reliability, has_edges])
        trust = min(0.85, 0.50 + richness * 0.10)

        return SourceEnvelope(
            source_id="l0_state",
            source_family="l0_state",
            source_name="Layer 0 State Vector",
            package_id="l0_state",
            package_version="l0_state_v1",
            trust_score=trust,
            spatial_scope="plot",
            temporal_scope="daily",
            source_status="ok" if richness >= 1 else "degraded",
        )
