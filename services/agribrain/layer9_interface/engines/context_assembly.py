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

        l9_input = Layer9Input(
            audit_grade=audit_grade,
            source_reliability=source_reliability,
            conflicts=conflicts,
            diagnoses=diagnoses,
            actions=actions,
            schedule=schedule,
            zone_plan=zone_plan,
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
