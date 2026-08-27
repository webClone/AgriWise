"""
Engine 1: Context Assembly Engine v9.6.0

Centralizes all upstream data marshalling — replaces inline extraction
logic from the old runner.py.  Produces a clean Layer9Input from raw
layer outputs.
"""
import hashlib, json, logging
from typing import Any, Optional, Dict, List
from dataclasses import asdict

from layer9_interface.schema import Layer9Input
from services.agribrain.scientific_contracts.crop_phenology import (
    consume_canonical_phenology_output,
)

logger = logging.getLogger(__name__)


class ContextAssemblyEngine:
    """Merges L3/L6/L8/L10 outputs into a single Layer9Input."""

    def assemble(
        self,
        orch_inputs: Any,
        l8_output: Optional[Any] = None,
        l3_output: Optional[Any] = None,
        l6_output: Optional[Any] = None,
        l10_output: Optional[Any] = None,
        l1_conflicts: Optional[List[Dict[str, Any]]] = None,
        l1_output: Optional[Any] = None,
        l2_output: Optional[Any] = None,
        l4_output: Optional[Any] = None,
        l5_output: Optional[Any] = None,
        l7_output: Optional[Any] = None,
    ) -> tuple:
        """
        Returns:
            (Layer9Input, spatial_explanations)
        """
        audit_grade, source_reliability = self._extract_quality(l8_output)
        conflicts = l1_conflicts if isinstance(l1_conflicts, list) else []
        diagnoses = self._extract_diagnoses(l3_output)
        actions, schedule, zone_plan = self._extract_prescriptive(l8_output)
        spatial_zones, spatial_explanations = self._extract_l10_spatial(l10_output)
        zone_plan = self._enrich_zone_plan(zone_plan, spatial_zones)

        # Extract new layer data (v9.7 advanced wiring)
        l1_data = {}
        if l1_output:
            forecast_7d = getattr(l1_output, "forecast_7d", []) or []
            plot_ts = getattr(l1_output, "plot_timeseries", []) or []
            l1_data["forecast_days"] = len(forecast_7d)
            l1_data["plot_timeseries_days"] = len(plot_ts)
            l1_static = getattr(l1_output, "static", {}) or {}
            l1_data["soil_ph"] = l1_static.get("soil_ph", 6.5)
            l1_data["soil_clay"] = l1_static.get("soil_clay", 22.0)
            l1_data["soil_org_carbon"] = l1_static.get("soil_org_carbon", 1.8)
            
            # Enrich with evidence items for V89 report engine
            ev_items = getattr(l1_output, "evidence_items", []) or []
            l1_data["evidence_items"] = [
                {
                    "evidence_id": getattr(e, "evidence_id", ""),
                    "variable": getattr(e, "variable", ""),
                    "value": getattr(e, "value", None),
                    "confidence": getattr(e, "confidence", 0.5),
                    "source_family": getattr(e, "source_family", "unknown"),
                    "observed_at": getattr(e, "observed_at", None).isoformat() if getattr(e, "observed_at", None) else None,
                    "data_status": getattr(e, "data_status", "observed"),
                    "observation_type": getattr(e, "observation_type", "measurement"),
                } for e in ev_items
            ]

        l2_data = {}
        if l2_output:
            phenology = consume_canonical_phenology_output(l2_output)
            l2_data.update({
                "stage": phenology["resolved_crop_stage"],
                "phenology_authority": phenology["phenology_authority"],
                "phenology_posterior_hash": phenology["phenology_posterior_hash"],
                "phenology_receipt_valid": phenology["phenology_receipt_valid"],
                "phenology_confidence": phenology["phenology_confidence"],
                "phenology_evidence_needed_reason": phenology[
                    "phenology_evidence_needed_reason"
                ],
            })
            temporal = getattr(l2_output, "veg_temporal", l2_output)
            anomalies = getattr(temporal, "anomalies", []) or []
            l2_data["anomalies_count"] = len(anomalies)
            l2_data["anomalies_severity"] = [getattr(a, "severity", 0.0) for a in anomalies]

        l4_data = {}
        if l4_output:
            l4_states = getattr(l4_output, "nutrient_states", {}) or {}
            l4_data["nutrient_deficiencies"] = {
                k.value if hasattr(k, "value") else str(k): {
                    "probability_deficient": getattr(state, "probability_deficient", 0.0),
                    "confidence": getattr(state, "confidence", 0.5),
                    "severity": getattr(state, "severity", "LOW")
                } for k, state in l4_states.items()
            }
            l4_soil = getattr(l4_output, "soil_props", {}) or {}
            l4_data["soil_ph"] = l4_soil.get("ph")
            l4_data["clay_pct"] = l4_soil.get("clay_pct")

        l5_data = {}
        if l5_output:
            l5_states = getattr(l5_output, "threat_states", {}) or {}
            l5_data["threat_states"] = {
                k.value if hasattr(k, "value") else str(k): {
                    "probability": getattr(state, "probability", 0.0),
                    "confidence": getattr(state, "confidence", 0.5),
                    "severity": getattr(state, "severity", "LOW")
                } for k, state in l5_states.items()
            }

        l6_data = {}
        if l6_output:
            l6_data["feasibility_grade"] = getattr(getattr(l6_output, "quality_metrics", None), "intervention_feasibility_score", 0.8)
            l6_data["conflict_count"] = len(getattr(l6_output, "conflict_log", []) or [])
            l6_data["nitrogen_leaching_fraction"] = getattr(l6_output, "nitrogen_leaching_fraction", 0.0)
            l6_data["runoff_risk_index"] = getattr(l6_output, "runoff_risk_index", 0.0)
            l6_data["vapor_pressure_deficit_kpa"] = getattr(l6_output, "vapor_pressure_deficit_kpa", 0.0)
            l6_data["net_carbon_balance_t_co2eq"] = getattr(l6_output, "net_carbon_balance_t_co2eq", 0.0)

        l7_data = {}
        if l7_output:
            options = getattr(l7_output, "options", []) or []
            l7_data["options"] = [
                {
                    "crop": getattr(o, "crop", ""),
                    "overall_rank_score": getattr(o, "overall_rank_score", 0.0),
                    "suitability_percentage": getattr(o, "suitability_percentage", 0.0),
                    "expected_profit": getattr(getattr(o, "econ", None), "expected_profit", 0.0) if getattr(o, "econ", None) else 0.0
                } for o in options
            ]
            chosen = getattr(l7_output, "chosen_plan", None)
            if chosen:
                l7_data["chosen_crop"] = getattr(chosen, "crop", "")
                l7_data["decision_id"] = getattr(getattr(chosen, "decision_id", None), "value", "UNKNOWN")

        l10_data = {}
        if l10_output:
            l10_data["zones_count"] = len(getattr(l10_output, "zone_pack", []) or [])
            l10_data["explainability_surfaces"] = list(getattr(l10_output, "explainability_pack", {}).keys() or [])
            
            # Enrich with surfaces details for V89 report engine
            surfs = getattr(l10_output, "surface_pack", []) or []
            l10_data["surfaces"] = [
                {
                    "surface_id": getattr(s, "surface_id", ""),
                    "semantic_type": getattr(getattr(s, "semantic_type", None), "value", str(getattr(s, "semantic_type", ""))),
                    "native_resolution_m": getattr(s, "native_resolution_m", 10.0),
                    "provenance": getattr(s, "provenance", {}),
                } for s in surfs
            ]

        # Auto-generate cross-layer Explanations
        cross_explanations = []
        if l1_data:
            cross_explanations.append({
                "statement": f"Weather forecast data loaded successfully: {l1_data['forecast_days']} days processed from reanalysis models.",
                "evidence_id": "L1_weather_forecast",
                "source_layer": "L1",
                "confidence": 0.95
            })
        if l2_data.get("phenology_receipt_valid") and l2_data.get("stage") != "UNKNOWN":
            cross_explanations.append({
                "statement": f"Layer-2 canonical phenology: {l2_data['stage']} ({l2_data['phenology_authority']} authority; receipt {l2_data['phenology_posterior_hash'][:12]}).",
                "evidence_id": l2_data["phenology_posterior_hash"],
                "source_layer": "L2",
                "confidence": l2_data["phenology_confidence"],
            })
        elif l2_data:
            cross_explanations.append({
                "statement": f"Growth stage is UNKNOWN: {l2_data.get('phenology_evidence_needed_reason', 'canonical Layer-2 phenology evidence required')}.",
                "evidence_id": "L2_phenology_unavailable",
                "source_layer": "L2",
                "confidence": 0.0,
            })
        if l2_data.get("anomalies_count", 0) > 0:
            max_sev = max(l2_data["anomalies_severity"])
            cross_explanations.append({
                "statement": f"Vegetation anomalies flagged: {l2_data['anomalies_count']} stress events detected, maximum severity={max_sev:.2f}.",
                "evidence_id": "L2_anomalies",
                "source_layer": "L2",
                "confidence": 0.85
            })
        if l4_data.get("nutrient_deficiencies"):
            for nut, info in l4_data["nutrient_deficiencies"].items():
                if info["probability_deficient"] > 0.4:
                    cross_explanations.append({
                        "statement": f"Nutrient {nut} deficiency risk identified: p(deficient)={info['probability_deficient']:.2f} ({info['severity']} severity).",
                        "evidence_id": f"L4_{nut}_deficiency",
                        "source_layer": "L4",
                        "confidence": info["confidence"]
                    })
        if l5_data.get("threat_states"):
            for disease, info in l5_data["threat_states"].items():
                if info["probability"] > 0.4:
                    cross_explanations.append({
                        "statement": f"Pathogen/Pest risk detected: {disease} outbreak likelihood={info['probability']:.2f} ({info['severity']} severity).",
                        "evidence_id": f"L5_{disease}_outbreak",
                        "source_layer": "L5",
                        "confidence": info["confidence"]
                    })
        if l6_data:
            if l6_data.get("nitrogen_leaching_fraction", 0.0) > 0.15:
                cross_explanations.append({
                    "statement": f"High nitrogen leaching risk calculated: leaching fraction={l6_data['nitrogen_leaching_fraction']:.1f}% under forecast rainfall.",
                    "evidence_id": "L6_n_leaching",
                    "source_layer": "L6",
                    "confidence": 0.80
                })
            if l6_data.get("runoff_risk_index", 0.0) > 0.5:
                cross_explanations.append({
                    "statement": f"Runoff and soil erosion warning: risk index={l6_data['runoff_risk_index']:.2f}.",
                    "evidence_id": "L6_runoff_risk",
                    "source_layer": "L6",
                    "confidence": 0.85
                })
        if l7_data.get("chosen_crop"):
            cross_explanations.append({
                "statement": f"Pre-season planning recommendation: {l7_data['decision_id']} for crop '{l7_data['chosen_crop']}'.",
                "evidence_id": "L7_suitability",
                "source_layer": "L7",
                "confidence": 0.90
            })
            for opt in l7_data.get("options", [])[:2]:
                cross_explanations.append({
                    "statement": f"Crop option evaluation: {opt['crop']} suitability={opt['suitability_percentage']:.1f}%, expected profit={opt['expected_profit']:.1f} EUR/ha.",
                    "evidence_id": f"L7_option_{opt['crop']}",
                    "source_layer": "L7",
                    "confidence": 0.85
                })

        # Merge new explanations with spatial ones
        spatial_explanations.extend(cross_explanations)

        # Extract plot_id for plot-specific persistent memory tracking
        plot_id = "UNKNOWN"
        if hasattr(orch_inputs, "plot_id"):
            plot_id = getattr(orch_inputs, "plot_id") or "UNKNOWN"
        elif isinstance(orch_inputs, dict):
            plot_id = orch_inputs.get("plot_id", "UNKNOWN")

        # Extract user_query and image_data_b64 for downstream Q&A and routing
        user_query = None
        image_data_b64 = None
        if hasattr(orch_inputs, "user_query"):
            user_query = getattr(orch_inputs, "user_query")
        elif isinstance(orch_inputs, dict):
            user_query = orch_inputs.get("user_query")

        if hasattr(orch_inputs, "image_data_b64"):
            image_data_b64 = getattr(orch_inputs, "image_data_b64")
        elif isinstance(orch_inputs, dict):
            image_data_b64 = orch_inputs.get("image_data_b64")

        # 1. Extract Plot DNA Decadal Inversion traits from cache
        plot_dna = {}
        if plot_id and plot_id != "UNKNOWN":
            try:
                from layer0.calibration.dna_cache import load_dna_cache, dna_to_crop_params
                dna = load_dna_cache(plot_id)
                if dna:
                    plot_dna = {
                        "traits": dna.get("traits", {}),
                        "crop_params": dna_to_crop_params(dna),
                        "data_quality": dna.get("data_quality", {})
                    }
            except Exception:
                pass

        # 2. Extract Biophysical History (NDVI and weather timeseries logs)
        biophysical_history = {}
        if l1_output:
            plot_ts = getattr(l1_output, "plot_timeseries", []) or []
            if plot_ts:
                biophysical_history["weather_history_days"] = len(plot_ts)
                biophysical_history["last_14d_weather"] = plot_ts[-14:]
        if l2_output:
            curve = getattr(l2_output, "curve", None)
            if curve:
                ndvi_fit = getattr(curve, "ndvi_fit", []) or []
                if ndvi_fit:
                    biophysical_history["ndvi_history_days"] = len(ndvi_fit)
                    biophysical_history["last_10_ndvi"] = ndvi_fit[-10:]

        # 3. Extract User Events & Operational Schedules
        user_events = {}
        op_ctx = {}
        if hasattr(orch_inputs, "operational_context"):
            op_ctx = getattr(orch_inputs, "operational_context") or {}
        elif isinstance(orch_inputs, dict):
            op_ctx = orch_inputs.get("operational_context") or {}

        if isinstance(op_ctx, dict):
            user_events["drone_mission"] = op_ctx.get("drone_mission") or op_ctx.get("drone")
            user_events["irrigation_runtime"] = op_ctx.get("irrigation_runtime") or op_ctx.get("irrigation")
            user_events["camera_freshness"] = op_ctx.get("camera_freshness") or op_ctx.get("camera")

        l9_input = Layer9Input(
            audit_grade=audit_grade,
            source_reliability=source_reliability,
            conflicts=conflicts,
            diagnoses=diagnoses,
            actions=actions,
            schedule=schedule,
            zone_plan=zone_plan,
            l1_fusion_data=l1_data,
            l2_vegetation_data=l2_data,
            l4_nutrient_data=l4_data,
            l5_disease_data=l5_data,
            l6_execution_data=l6_data,
            l7_planning_data=l7_data,
            l10_sire_data=l10_data,
            plot_id=plot_id,
            user_query=user_query,
            image_data_b64=image_data_b64,
            plot_dna=plot_dna,
            biophysical_history=biophysical_history,
            user_events=user_events,
        )
        return l9_input, spatial_explanations

    def compute_field_hash(self, l9_input: Layer9Input) -> str:
        """Deterministic hash for cache-invalidation."""
        raw = json.dumps({
            "grade": l9_input.audit_grade,
            "n_diag": len(l9_input.diagnoses),
            "n_act": len(l9_input.actions),
            "zones": sorted(l9_input.zone_plan.keys()) if l9_input.zone_plan else [],
        }, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    # ------------------------------------------------------------------
    # Private helpers (migrated from old runner.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_quality(l8_output) -> tuple:
        audit_grade = "C"
        source_reliability: Dict[str, float] = {}
        if l8_output:
            quality = getattr(l8_output, "quality", None)
            if quality:
                audit_grade = getattr(quality, "audit_grade", "C")
                source_reliability = getattr(quality, "upstream_confidence", {})
        return audit_grade, source_reliability

    @staticmethod
    def _extract_diagnoses(l3_output) -> List[Dict[str, Any]]:
        diagnoses: List[Dict[str, Any]] = []
        if l3_output:
            for d in getattr(l3_output, "diagnoses", []):
                diagnoses.append({
                    "problem_id": getattr(d, "problem_id", "UNKNOWN"),
                    "probability": getattr(d, "probability", 0.0),
                    "severity": getattr(d, "severity", 0.0),
                    "confidence": getattr(d, "confidence", 0.0),
                    "affected_area_pct": getattr(d, "affected_area_pct", 0.0),
                })
        return diagnoses

    @staticmethod
    def _extract_prescriptive(l8_output) -> tuple:
        actions: List[Dict[str, Any]] = []
        schedule: List[Dict[str, Any]] = []
        zone_plan: Dict[str, Any] = {}
        if not l8_output:
            return actions, schedule, zone_plan

        for a in getattr(l8_output, "actions", []):
            actions.append({
                "action_id": getattr(a, "action_id", ""),
                "action_type": getattr(
                    getattr(a, "action_type", None), "value", "UNKNOWN"
                ),
                "priority_score": getattr(a, "priority_score", 0.0),
                "is_allowed": getattr(a, "is_allowed", True),
                "confidence": getattr(
                    getattr(a, "confidence", None), "value", "MODERATE"
                ),
            })

        for s in getattr(l8_output, "schedule", []):
            action_type = getattr(s, "action_type", None)
            status = getattr(s, "status", None)
            schedule.append({
                "action_id": getattr(s, "action_id", ""),
                "action_type": (
                    action_type.value
                    if hasattr(action_type, "value")
                    else str(action_type or "")
                ),
                "scheduled_date": getattr(s, "scheduled_date", None),
                "status": (
                    status.value
                    if hasattr(status, "value")
                    else str(status or "")
                ),
                "blocking_constraints": getattr(s, "blocking_constraints", []),
                "priority_score": getattr(s, "priority_score", 0.0),
                "weather_ok": getattr(s, "weather_ok", True),
                "phenology_ok": getattr(s, "phenology_ok", True),
            })

        raw_plan = getattr(l8_output, "zone_plan", {})
        zone_plan = ContextAssemblyEngine._serialize_zone_plan(raw_plan)
        return actions, schedule, zone_plan

    @staticmethod
    def _serialize_zone_plan(zone_plan) -> Dict[str, Any]:
        if not zone_plan or not isinstance(zone_plan, dict):
            return {}
        result: Dict[str, Any] = {}
        for zone_id, plan in zone_plan.items():
            if isinstance(plan, dict):
                result[zone_id] = plan
            elif hasattr(plan, "__dataclass_fields__"):
                try:
                    result[zone_id] = asdict(plan)
                except Exception:
                    result[zone_id] = {
                        "zone_id": getattr(plan, "zone_id", zone_id),
                        "actions": getattr(plan, "actions", []),
                        "allocation_fraction": getattr(plan, "allocation_fraction", 0.0),
                        "priority": getattr(plan, "priority", "MEDIUM"),
                        "reason": getattr(plan, "reason", ""),
                    }
            else:
                result[zone_id] = {"zone_id": zone_id}
        return result

    @staticmethod
    def _extract_l10_spatial(l10_output) -> tuple:
        spatial_zones: List[Dict[str, Any]] = []
        spatial_explanations: List[Dict[str, Any]] = []
        if not l10_output:
            return spatial_zones, spatial_explanations

        for zone in getattr(l10_output, "zone_pack", []):
            zone_type = getattr(zone, "zone_type", None)
            spatial_zones.append({
                "zone_id": getattr(zone, "zone_id", ""),
                "zone_type": zone_type.value if hasattr(zone_type, "value") else str(zone_type or ""),
                "severity": getattr(zone, "severity", 0.0),
                "confidence": getattr(zone, "confidence", 0.0),
                "area_pct": getattr(zone, "area_pct", 0.0),
                "top_drivers": getattr(zone, "top_drivers", []),
                "surface_stats": getattr(zone, "surface_stats", {}),
                "linked_actions": getattr(zone, "linked_actions", []),
                "label": getattr(zone, "label", ""),
                "description": getattr(zone, "description", ""),
                "source_surface_type": getattr(zone, "source_surface_type", ""),
            })

        for surface_key, pack in getattr(l10_output, "explainability_pack", {}).items():
            summary = getattr(pack, "summary", "")
            if summary:
                spatial_explanations.append({
                    "statement": summary,
                    "evidence_id": f"L10_{surface_key}",
                    "source_layer": "L10",
                    "confidence": getattr(getattr(pack, "confidence", None), "score", 0.7),
                })
            for driver in getattr(pack, "top_drivers", [])[:2]:
                name = getattr(driver, "name", "")
                value = getattr(driver, "value", 0.0)
                role = getattr(driver, "role", "")
                if name:
                    spatial_explanations.append({
                        "statement": f"Spatial driver: {name} ({role}, contribution={value:.2f})",
                        "evidence_id": f"L10_{surface_key}_{name}",
                        "source_layer": "L10",
                        "confidence": 0.7,
                    })
        return spatial_zones, spatial_explanations

    @staticmethod
    def _enrich_zone_plan(zone_plan, spatial_zones):
        enriched = dict(zone_plan) if zone_plan else {}
        for sz in spatial_zones:
            zid = sz["zone_id"]
            existing = enriched.get(zid, {})
            if not isinstance(existing, dict):
                existing = {}
            existing["spatial_severity"] = sz["severity"]
            existing["spatial_confidence"] = sz["confidence"]
            existing["area_pct"] = sz["area_pct"]
            existing["zone_type"] = sz["zone_type"]
            existing["top_drivers"] = sz["top_drivers"]
            existing["surface_stats"] = sz["surface_stats"]
            existing["linked_actions"] = sz.get("linked_actions", [])
            existing["label"] = sz.get("label", "")
            existing["description"] = sz.get("description", "")
            existing["source_surface_type"] = sz.get("source_surface_type", "")
            enriched[zid] = existing
        return enriched


context_assembly = ContextAssemblyEngine()
