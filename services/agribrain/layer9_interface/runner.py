"""
Layer 9 Interface Runner
========================

Pipeline entry point that wraps PolicyRouter into a standard runner.

Usage:
    from services.agribrain.layer9_interface.runner import run_layer9
    output = run_layer9(orch_inputs, l8_output, l3_output, l6_output, l10_output)
"""
from typing import Any, Optional, Dict, List
from dataclasses import asdict
from services.agribrain.layer9_interface.schema import Layer9Input, InterfaceOutput
from services.agribrain.layer9_interface.policy_router import PolicyRouter


def run_layer9(
    orch_inputs: Any,
    l8_output: Optional[Any] = None,
    l3_output: Optional[Any] = None,
    l6_output: Optional[Any] = None,
    l10_output: Optional[Any] = None,
    l1_conflicts: Optional[List[Dict[str, Any]]] = None,
) -> InterfaceOutput:
    """
    Run Layer 9 interface rendering.

    Assembles Layer9Input from L3/L6/L8/L10 outputs, then calls PolicyRouter.

    Args:
        orch_inputs: OrchestratorInput (for plot_id, config)
        l8_output: Layer8Output (actions, schedule, zone_plan)
        l3_output: DecisionOutput (diagnoses)
        l6_output: Layer6Output (execution state)
        l10_output: Layer10Output (spatial zones, surfaces, explainability)
        l1_conflicts: Cross-source conflicts from L1 provenance (passed directly
                      from orchestrator because L8Output does not expose conflicts)

    Returns:
        InterfaceOutput with zone_cards, alerts, explanations, etc.
    """
    # --- Extract audit grade + conflicts ---
    # Conflicts come directly from orchestrator (L1 provenance extraction).
    # This is the definitive path — no fallback needed.
    audit_grade = "C"  # Default fallback
    source_reliability = {}
    conflicts = l1_conflicts if isinstance(l1_conflicts, list) else []

    if l8_output:
        quality = getattr(l8_output, 'quality', None)
        if quality:
            audit_grade = getattr(quality, 'audit_grade', 'C')
            source_reliability = getattr(quality, 'upstream_confidence', {})

    # --- Extract diagnoses ---
    diagnoses = []
    if l3_output:
        raw_diags = getattr(l3_output, 'diagnoses', [])
        for d in raw_diags:
            diagnoses.append({
                "problem_id": getattr(d, 'problem_id', 'UNKNOWN'),
                "probability": getattr(d, 'probability', 0.0),
                "severity": getattr(d, 'severity', 0.0),
                "confidence": getattr(d, 'confidence', 0.0),
                "affected_area_pct": getattr(d, 'affected_area_pct', 0.0),
            })

    # --- Extract actions/schedule/zone_plan ---
    actions = []
    schedule = []
    zone_plan = {}

    if l8_output:
        for a in getattr(l8_output, 'actions', []):
            actions.append({
                "action_id": getattr(a, 'action_id', ''),
                "action_type": getattr(getattr(a, 'action_type', None), 'value', 'UNKNOWN'),
                "priority_score": getattr(a, 'priority_score', 0.0),
                "is_allowed": getattr(a, 'is_allowed', True),
                "confidence": getattr(getattr(a, 'confidence', None), 'value', 'MODERATE'),
            })
        # ScheduledAction: actual fields are scheduled_date, status, blocking_constraints
        for s in getattr(l8_output, 'schedule', []):
            action_type = getattr(s, 'action_type', None)
            status = getattr(s, 'status', None)
            schedule.append({
                "action_id": getattr(s, 'action_id', ''),
                "action_type": action_type.value if hasattr(action_type, 'value') else str(action_type or ''),
                "scheduled_date": getattr(s, 'scheduled_date', None),
                "status": status.value if hasattr(status, 'value') else str(status or ''),
                "blocking_constraints": getattr(s, 'blocking_constraints', []),
                "priority_score": getattr(s, 'priority_score', 0.0),
                "weather_ok": getattr(s, 'weather_ok', True),
                "phenology_ok": getattr(s, 'phenology_ok', True),
            })
        # ZoneActionPlan: serialize dataclasses into dicts for safe enrichment
        zone_plan = _serialize_zone_plan(getattr(l8_output, 'zone_plan', {}))

    # --- Enrich zone_plan with L10 spatial intelligence ---
    spatial_zones = []
    spatial_explanations = []
    if l10_output:
        spatial_zones, spatial_explanations = _extract_l10_spatial(l10_output)
        zone_plan = _enrich_zone_plan_with_l10(zone_plan, spatial_zones)

    # --- Assemble Layer9Input ---
    l9_input = Layer9Input(
        audit_grade=audit_grade,
        source_reliability=source_reliability,
        conflicts=conflicts,
        diagnoses=diagnoses,
        actions=actions,
        schedule=schedule,
        zone_plan=zone_plan,
    )

    # --- Run PolicyRouter ---
    router = PolicyRouter()
    output = router.build_output(l9_input, spatial_explanations=spatial_explanations)

    return output


# ============================================================================
# L10 Spatial Translation Helpers
# ============================================================================

def _extract_l10_spatial(l10_output) -> tuple:
    """
    Translate L10's zone_pack and explainability_pack into L9-consumable dicts.
    
    Returns:
        (spatial_zones, spatial_explanations)
        spatial_zones: list of dicts with zone metrics for enriching zone_plan
        spatial_explanations: list of dicts for spatial evidence-backed explanations
    """
    spatial_zones: List[Dict[str, Any]] = []
    spatial_explanations: List[Dict[str, Any]] = []
    
    # --- Zone Pack ---
    for zone in getattr(l10_output, 'zone_pack', []):
        zone_id = getattr(zone, 'zone_id', '')
        zone_type = getattr(zone, 'zone_type', None)
        zone_type_str = zone_type.value if hasattr(zone_type, 'value') else str(zone_type or '')
        
        spatial_zones.append({
            "zone_id": zone_id,
            "zone_type": zone_type_str,
            "severity": getattr(zone, 'severity', 0.0),
            "confidence": getattr(zone, 'confidence', 0.0),
            "area_pct": getattr(zone, 'area_pct', 0.0),
            "top_drivers": getattr(zone, 'top_drivers', []),
            "surface_stats": getattr(zone, 'surface_stats', {}),
            "linked_actions": getattr(zone, 'linked_actions', []),
            "label": getattr(zone, 'label', ''),
            "description": getattr(zone, 'description', ''),
            "source_surface_type": getattr(zone, 'source_surface_type', ''),
        })
    
    # --- Explainability Pack ---
    for surface_key, pack in getattr(l10_output, 'explainability_pack', {}).items():
        summary = getattr(pack, 'summary', '')
        if summary:
            spatial_explanations.append({
                "statement": summary,
                "evidence_id": f"L10_{surface_key}",
                "source_layer": "L10",
                "confidence": getattr(getattr(pack, 'confidence', None), 'score', 0.7),
            })
        # Add top drivers as individual explanations
        for driver in getattr(pack, 'top_drivers', [])[:2]:
            name = getattr(driver, 'name', '')
            value = getattr(driver, 'value', 0.0)
            role = getattr(driver, 'role', '')
            if name:
                spatial_explanations.append({
                    "statement": f"Spatial driver: {name} ({role}, contribution={value:.2f})",
                    "evidence_id": f"L10_{surface_key}_{name}",
                    "source_layer": "L10",
                    "confidence": 0.7,
                })
    
    return spatial_zones, spatial_explanations


def _enrich_zone_plan_with_l10(
    zone_plan: Dict[str, Any],
    spatial_zones: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Merge L10 spatial zone intelligence into L8's zone_plan.
    
    For each L10 zone, either enrich an existing zone_plan entry
    or create a new one with spatial metrics.
    """
    enriched = dict(zone_plan) if zone_plan else {}
    
    for sz in spatial_zones:
        zid = sz["zone_id"]
        existing = enriched.get(zid, {})
        if not isinstance(existing, dict):
            existing = {}
        
        # Inject spatial metrics without overwriting L8 prescriptive data
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


def _serialize_zone_plan(zone_plan) -> Dict[str, Any]:
    """
    Convert ZoneActionPlan dataclasses into plain dicts.
    
    Layer8Output.zone_plan is Dict[str, ZoneActionPlan] — dataclass objects.
    L10 enrichment and PolicyRouter both need dicts, so we serialize here
    to preserve L8 prescriptive fields (actions, priority, reason, etc.).
    """
    if not zone_plan or not isinstance(zone_plan, dict):
        return {}
    result = {}
    for zone_id, plan in zone_plan.items():
        if isinstance(plan, dict):
            result[zone_id] = plan
        elif hasattr(plan, '__dataclass_fields__'):
            # Proper dataclass → dict conversion
            try:
                result[zone_id] = asdict(plan)
            except Exception:
                # Fallback: manual extraction
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

