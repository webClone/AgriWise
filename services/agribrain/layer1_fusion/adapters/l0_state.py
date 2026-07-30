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
        """Read if package is a non-empty dict or has daily_state attribute."""
        if package is None:
            return False
        if isinstance(package, dict):
            return len(package) > 0
        return hasattr(package, "daily_state") or hasattr(package, "zone_summaries")

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id
        run_ts = context.run_timestamp
        run_id = context.run_id

        # Normalize access using duck typing
        daily_state_dict = {}
        state_uncertainty_dict = {}
        validation_conflicts = []
        source_reliability = {}
        zone_reliability = {}
        edge_contamination = []
        zone_summaries = []

        if isinstance(package, dict):
            daily_state_dict = package.get("state_vectors", {})
            state_uncertainty_dict = package.get("state_uncertainties", {}) or package.get("state_uncertainty", {})
            validation_conflicts = package.get("validation_conflicts", [])
            source_reliability = package.get("source_reliability", {})
            zone_reliability = package.get("zone_reliability", {})
            edge_contamination = package.get("edge_contamination", [])
            zone_summaries = package.get("zone_summaries", [])
        else:
            # It's a Layer0StatePackage object!
            daily_state_dict = getattr(package, "daily_state", {}) or {}
            state_uncertainty_dict = getattr(package, "state_uncertainty", {}) or {}
            validation_conflicts = getattr(package, "validation_conflicts", []) or []
            
            health_rep = getattr(package, "health_report", {}) or {}
            if isinstance(health_rep, dict):
                source_reliability = health_rep.get("source_reliability", {}) or {}
            else:
                source_reliability = getattr(health_rep, "source_reliability", {}) or {}

            # Construct synthesized zone summaries from daily_state
            for zone_id, states in daily_state_dict.items():
                if not states:
                    continue
                # Get the last state vector (for current/latest run day)
                last_state = states[-1]
                if not isinstance(last_state, dict) and hasattr(last_state, "to_dict"):
                    last_state = last_state.to_dict()
                elif not isinstance(last_state, dict):
                    last_state = {}

                # Build the zone summary dict
                zs = {
                    "zone_id": zone_id,
                    "label": zone_id.upper(),
                    "area_fraction": 1.0 if zone_id == "plot" else 0.0,
                }
                
                # Propagate any variables present in the state vector
                if "lai_proxy" in last_state:
                    zs["lai_mean"] = last_state["lai_proxy"]
                if "sm_0_10" in last_state:
                    zs["sm_mean"] = last_state["sm_0_10"]
                if "ndvi" in last_state:
                    zs["ndvi_mean"] = last_state["ndvi"]
                
                zone_summaries.append(zs)

        idx = 0

        # Helper to extract latest uncertainty for a zone
        def _get_latest_uncertainty(zone_id: str) -> dict:
            unc_list = state_uncertainty_dict
            if isinstance(state_uncertainty_dict, dict) and zone_id in state_uncertainty_dict:
                unc_list = state_uncertainty_dict[zone_id]
            
            if isinstance(unc_list, list) and unc_list:
                last_u = unc_list[-1]
                if not isinstance(last_u, dict) and hasattr(last_u, "uncertainty_dict"):
                    return last_u.uncertainty_dict()
                elif isinstance(last_u, dict):
                    return last_u
            elif isinstance(unc_list, dict):
                return unc_list
            return {}

        def _add(variable: str, value: Any, unit: str,
                 spatial_scope: str = "plot",
                 scope_id: str = None,
                 confidence: float = 0.70,
                 reliability: float = 0.75,
                 sigma: Optional[float] = None,
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
                sigma=sigma,
                freshness_score=1.0,  # L0 state is always current-day
                provenance_ref=f"l0_state_{run_id}_{plot_id}",
                diagnostic_only=diagnostic_only,
                state_update_allowed=not diagnostic_only,
                flags=flags or [],
                data_status="assimilated",
            ))
            idx += 1

        # ---- Zone summaries ----
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
            zone_unc = _get_latest_uncertainty(zone_id)
            for key in ("ndvi_mean", "ndmi_mean", "sm_mean", "lai_mean"):
                val = zs.get(key)
                if val is not None:
                    var_name = key.replace("_mean", "")
                    
                    # Map to the correct key in the uncertainty dictionary
                    unc_key = var_name
                    if var_name == "sm":
                        unc_key = "sm_0_10"
                    elif var_name == "lai":
                        unc_key = "lai_proxy"

                    sigma_val = zone_unc.get(unc_key) or zone_unc.get(var_name) or zone_unc.get(key)
                    if sigma_val is not None:
                        sigma_val = float(sigma_val)

                    _add(
                        variable=f"l0_{var_name}",
                        value=float(val),
                        unit="index" if "ndvi" in key or "ndmi" in key else "fraction",
                        spatial_scope="zone",
                        scope_id=zone_id,
                        confidence=0.70,
                        sigma=sigma_val,
                    )

        # ---- Plot-level state vectors ----
        plot_state = {}
        if isinstance(package, dict):
            plot_state = package.get("state_vectors", {})
        else:
            # Object shape: extract last "plot" daily state vector dict
            plot_states = daily_state_dict.get("plot", [])
            if plot_states:
                last_s = plot_states[-1]
                if not isinstance(last_s, dict) and hasattr(last_s, "to_dict"):
                    plot_state = last_s.to_dict()
                elif isinstance(last_s, dict):
                    plot_state = last_s

        plot_unc = _get_latest_uncertainty("plot")

        if plot_state:
            KNOWN_STATE_VARS = {
                "lai_proxy": ("fraction", 0.75),
                "biomass_proxy": ("fraction", 0.70),
                "sm_0_10": ("fraction", 0.75),
                "sm_10_40": ("fraction", 0.70),
                "phenology_gdd": ("degC", 0.65),
                "phenology_stage": ("class", 0.65),
                "canopy_cover": ("fraction", 0.70),
            }
            for var, val in plot_state.items():
                if val is None or var == "day":
                    continue
                unit, conf = KNOWN_STATE_VARS.get(var, ("score", 0.60))
                
                # Fetch plot sigma for this variable
                sigma_val = plot_unc.get(var)
                if sigma_val is not None:
                    sigma_val = float(sigma_val)

                _add(
                    variable=f"l0_{var}",
                    value=float(val) if isinstance(val, (int, float)) else val,
                    unit=unit,
                    confidence=conf,
                    sigma=sigma_val,
                )

        # Legacy dict format top-level state fallback
        if isinstance(package, dict):
            for top_var in ("biomass_proxy", "lai_proxy", "sm_0_10",
                            "phenology_gdd", "phenology_stage"):
                val = package.get(top_var)
                if val is not None and not plot_state.get(top_var):
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
        if source_reliability:
            for src, weight in source_reliability.items():
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
        if isinstance(package, dict):
            zone_rel = package.get("zone_reliability", {})
        else:
            zone_rel = getattr(package, "zone_reliability", {}) or {}
            
        if zone_rel:
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
        if isinstance(package, dict):
            edge_data = package.get("edge_contamination", [])
        else:
            edge_data = getattr(package, "edge_contamination", []) or []
            
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
        import datetime
        
        if package is None:
            return SourceEnvelope(
                source_id="l0_state_missing",
                source_family="l0_state",
                source_name="Layer 0 State Vector",
                package_id="",
                package_version="",
                source_status="missing",
            )

        if not isinstance(package, dict) and getattr(package, "contract_version", "") == "layer0-state-package-v1":
            # Canonical state package object metadata preservation
            run_id = getattr(package, "run_id", "l0_state")
            output_hash = getattr(package, "output_hash", "")
            prov = getattr(package, "provenance", {})
            diag = getattr(package, "health_report", {})
            
            richness = len(getattr(package, "daily_state", {}))
            status = "ok" if richness > 0 else "degraded"

            return SourceEnvelope(
                source_id=f"l0_state_{run_id[:8]}" if run_id else "l0_state",
                source_family="l0_state",
                source_name="Layer 0 State Vector",
                package_id=run_id,
                package_version="layer0-state-package-v1",
                input_hash=output_hash,
                produced_at=datetime.datetime.now(datetime.timezone.utc),
                trust_score=0.85 if status == "ok" else 0.50,
                spatial_scope="plot",
                temporal_scope="daily",
                source_status=status,
                provenance=prov,
                diagnostics=diag,
            )

        # Legacy dict fallback
        has_zones = bool(package.get("zone_summaries", []))
        has_state = bool(package.get("state_vectors", {}))
        has_reliability = bool(package.get("source_reliability", {}))
        has_edges = bool(package.get("edge_contamination", []))

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
