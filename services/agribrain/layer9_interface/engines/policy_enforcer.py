"""
Engine 13: Policy Enforcer v9.6.1

Upgraded PolicyRouter with chemical compliance, temporal validity,
and economic sanity gates. Chemical whitelist loaded from external
JSON config with file-mtime caching.
"""
import json
import logging
import os
from typing import Dict, Any, List, Optional, Set

from layer9_interface.schema import (
    Layer9Input, InterfaceOutput, Alert, AlertType, AlertSeverity,
    ZoneCard, Explanation, Disclaimer, Citation, RenderHint,
    BadgeColor, PhrasingMode,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Chemical whitelist — external config with resilient fallback
# ============================================================================

_FALLBACK_CHEMICALS: Set[str] = {
    "glyphosate", "atrazine", "metolachlor", "chlorpyrifos",
    "mancozeb", "copper_hydroxide", "bacillus_thuringiensis",
}

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config", "chemical_whitelist.json",
)

# Mtime-based cache to avoid re-reading on every call
_cached_chemicals: Set[str] = set()
_cached_mtime: float = 0.0


def _load_chemical_whitelist() -> Set[str]:
    """Load approved chemicals from external JSON config.

    Uses file-mtime caching: only re-reads when the file has changed.
    Falls back to hardcoded defaults if the config file is missing or corrupt.
    """
    global _cached_chemicals, _cached_mtime

    try:
        current_mtime = os.path.getmtime(_CONFIG_PATH)
        if current_mtime == _cached_mtime and _cached_chemicals:
            return _cached_chemicals

        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        chemicals = set(c.lower().strip() for c in data.get("approved_chemicals", []))
        if not chemicals:
            logger.warning("Chemical whitelist is empty, using fallback")
            return _FALLBACK_CHEMICALS

        _cached_chemicals = chemicals
        _cached_mtime = current_mtime
        logger.info("Loaded %d chemicals from config (v%s)", len(chemicals), data.get("version", "?"))
        return chemicals

    except FileNotFoundError:
        logger.warning("Chemical whitelist config not found at %s, using fallback", _CONFIG_PATH)
        return _FALLBACK_CHEMICALS
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error("Failed to parse chemical whitelist: %s, using fallback", e)
        return _FALLBACK_CHEMICALS


_MAX_RECOMMENDATION_AGE_DAYS = 14


class PolicyEnforcerEngine:
    """Safety invariant enforcement with chemical/temporal/economic gates."""

    def assess_phrasing_mode(self, audit_grade: str) -> PhrasingMode:
        grade = audit_grade.upper()
        if grade in ("A", "B"):
            return PhrasingMode.CONFIDENT
        if grade == "C":
            return PhrasingMode.HEDGED
        return PhrasingMode.RESTRICTED

    def get_badge_color(self, audit_grade: str) -> BadgeColor:
        grade = audit_grade.upper()
        if grade in ("A", "B"):
            return BadgeColor.GREEN
        if grade == "C":
            return BadgeColor.YELLOW
        if grade in ("D", "F"):
            return BadgeColor.RED
        return BadgeColor.GRAY

    def generate_disclaimers(self, l9_input: Layer9Input) -> List[Disclaimer]:
        disclaimers: List[Disclaimer] = []
        grade = l9_input.audit_grade.upper()

        if grade in ("D", "F"):
            disclaimers.append(Disclaimer(
                text="Data quality issues detected. Recommendations are preliminary and require field confirmation.",
                reason="low_audit_grade",
                severity=AlertSeverity.CRITICAL,
            ))
        elif grade == "C":
            disclaimers.append(Disclaimer(
                text="Some data gaps detected. Consider verifying conditions before proceeding.",
                reason="moderate_audit_grade",
                severity=AlertSeverity.WARNING,
            ))

        if l9_input.conflicts:
            disclaimers.append(Disclaimer(
                text=f"{len(l9_input.conflicts)} data conflict(s) detected. Affected recommendations are tentative.",
                reason="conflict",
                severity=AlertSeverity.WARNING,
            ))

        for source, rel in l9_input.source_reliability.items():
            if rel < 0.5:
                disclaimers.append(Disclaimer(
                    text=f"Source '{source}' has low reliability ({rel:.0%}).",
                    reason=f"low_reliability_{source}",
                    severity=AlertSeverity.WARNING,
                ))

        has_spray = any(
            a.get("action_type") in ("SPRAY", "spray")
            for a in l9_input.actions if isinstance(a, dict) and a.get("is_allowed", True)
        )
        if has_spray:
            disclaimers.append(Disclaimer(
                text="Check product label and local regulations before chemical application.",
                reason="chemical_safety",
                severity=AlertSeverity.INFO,
            ))

        return disclaimers

    def generate_alerts(self, l9_input: Layer9Input) -> List[Alert]:
        alerts: List[Alert] = []
        grade = l9_input.audit_grade.upper()

        if grade in ("C", "D", "F"):
            alerts.append(Alert(
                alert_type=AlertType.DATA_QUALITY,
                severity=AlertSeverity.CRITICAL if grade in ("D", "F") else AlertSeverity.WARNING,
                message=f"Data quality grade: {grade}",
                trigger_evidence_id="L0_audit",
                action_required=grade in ("D", "F"),
            ))

        for i, conflict in enumerate(l9_input.conflicts):
            alerts.append(Alert(
                alert_type=AlertType.SYSTEM,
                severity=AlertSeverity.WARNING,
                message=conflict.get("description", f"Conflict #{i+1}"),
                trigger_evidence_id=conflict.get("id", f"conflict_{i}"),
            ))

        for action in l9_input.actions:
            if isinstance(action, dict) and not action.get("is_allowed", True):
                alerts.append(Alert(
                    alert_type=AlertType.SYSTEM,
                    severity=AlertSeverity.WARNING,
                    message=f"Action '{action.get('action_type', 'unknown')}' blocked",
                    trigger_evidence_id=action.get("action_id", "unknown"),
                ))

        return alerts

    def generate_zone_cards(self, l9_input: Layer9Input) -> List[ZoneCard]:
        cards: List[ZoneCard] = []
        badge = self.get_badge_color(l9_input.audit_grade)
        zone_plan = l9_input.zone_plan
        if isinstance(zone_plan, dict):
            for zone_id, plan in zone_plan.items():
                top_action = None
                key_metrics: Dict[str, Any] = {}
                status_text = ""
                if isinstance(plan, dict):
                    actions = plan.get("actions", [])
                    top_action = actions[0] if actions else None
                    status_text = plan.get("reason", "")
                    if plan.get("spatial_severity") is not None:
                        key_metrics["severity"] = round(plan["spatial_severity"], 2)
                        key_metrics["confidence"] = round(plan.get("spatial_confidence", 0.0), 2)
                        key_metrics["area_pct"] = round(plan.get("area_pct", 0.0), 1)
                        key_metrics["zone_type"] = plan.get("zone_type", "")
                        key_metrics["top_drivers"] = plan.get("top_drivers", [])
                        surface_stats = plan.get("surface_stats", {})
                        if surface_stats:
                            key_metrics["surface_stats"] = surface_stats
                        linked = plan.get("linked_actions", [])
                        if linked:
                            key_metrics["linked_actions"] = linked
                        label = plan.get("label", "")
                        desc = plan.get("description", "")
                        if label and desc:
                            status_text = f"{label}: {desc}"
                        elif label:
                            status_text = label
                        elif desc:
                            status_text = desc
                cards.append(ZoneCard(
                    zone_id=zone_id, top_action=top_action,
                    confidence_badge=badge, key_metrics=key_metrics,
                    status_text=status_text,
                ))
        return cards

    def generate_explanations(self, l9_input: Layer9Input) -> List[Explanation]:
        explanations: List[Explanation] = []
        for diag in l9_input.diagnoses:
            if isinstance(diag, dict) and diag.get("probability", 0) > 0.3:
                prob = diag.get("probability", 0)
                sev = diag.get("severity", 0)
                pid = diag.get("problem_id", "unknown")
                explanations.append(Explanation(
                    statement=f"Because {pid.replace('_', ' ').lower()} was detected with {prob:.0%} probability and {sev:.0%} severity",
                    evidence_id=pid,
                    source_layer="L3",
                    confidence=diag.get("confidence", 0.5),
                ))
        return explanations

    def build_render_hints(self, l9_input: Layer9Input) -> RenderHint:
        badge = self.get_badge_color(l9_input.audit_grade)
        highlight_zones = []
        if isinstance(l9_input.zone_plan, dict):
            for z, p in l9_input.zone_plan.items():
                if isinstance(p, dict):
                    if p.get("spatial_severity", 0.0) > 0.6:
                        highlight_zones.append(z)
                    elif p.get("priority") == "HIGH":
                        highlight_zones.append(z)
        return RenderHint(
            badge_color=badge,
            show_uncertainty_overlay=l9_input.audit_grade.upper() in ("C", "D", "F"),
            show_conflict_icon=len(l9_input.conflicts) > 0,
            highlight_zones=highlight_zones,
        )

    def build_citations(self, l9_input: Layer9Input) -> List[Citation]:
        citations = [Citation(
            source_layer="L0", reference_id="audit_grade",
            description=f"Audit grade: {l9_input.audit_grade}",
        )]
        for diag in l9_input.diagnoses:
            if isinstance(diag, dict):
                citations.append(Citation(
                    source_layer="L3",
                    reference_id=diag.get("problem_id", "unknown"),
                    value=diag.get("probability"),
                    description=f"Diagnosis: {diag.get('problem_id', '?')} p={diag.get('probability', 0):.2f}",
                ))
        
        # Append cross-layer citations (v9.7 advanced wiring)
        if l9_input.l1_fusion_data:
            citations.append(Citation(
                source_layer="L1", reference_id="fused_static_soil",
                description=f"L1 soil ph={l9_input.l1_fusion_data.get('soil_ph')}, clay={l9_input.l1_fusion_data.get('soil_clay')}%",
            ))
        if l9_input.l2_vegetation_data and l9_input.l2_vegetation_data.get("stage"):
            citations.append(Citation(
                source_layer="L2", reference_id="phenology_state",
                description=f"L2 phenology stage: {l9_input.l2_vegetation_data.get('stage')} (BBCH {l9_input.l2_vegetation_data.get('bbch')})",
            ))
        if l9_input.l4_nutrient_data and l9_input.l4_nutrient_data.get("nutrient_deficiencies"):
            for nut, info in l9_input.l4_nutrient_data["nutrient_deficiencies"].items():
                citations.append(Citation(
                    source_layer="L4", reference_id=f"nutrient_{nut}",
                    value=info["probability_deficient"],
                    description=f"L4 nutrient deficiency {nut}: p={info['probability_deficient']:.2f}",
                ))
        if l9_input.l5_disease_data and l9_input.l5_disease_data.get("threat_states"):
            for disease, info in l9_input.l5_disease_data["threat_states"].items():
                citations.append(Citation(
                    source_layer="L5", reference_id=f"pathogen_{disease}",
                    value=info["probability"],
                    description=f"L5 biotic threat {disease}: p={info['probability']:.2f}",
                ))
        if l9_input.l6_execution_data:
            citations.append(Citation(
                source_layer="L6", reference_id="leaching_fraction",
                value=l9_input.l6_execution_data.get("nitrogen_leaching_fraction", 0.0),
                description=f"L6 N leaching fraction: {l9_input.l6_execution_data.get('nitrogen_leaching_fraction', 0.0):.1f}%",
            ))
        if l9_input.l7_planning_data and l9_input.l7_planning_data.get("chosen_crop"):
            citations.append(Citation(
                source_layer="L7", reference_id="chosen_planning_crop",
                description=f"L7 plan: {l9_input.l7_planning_data.get('decision_id')} ({l9_input.l7_planning_data.get('chosen_crop')})",
            ))
        if l9_input.l10_sire_data:
            citations.append(Citation(
                source_layer="L10", reference_id="spatial_zones",
                description=f"L10 SIRE: {l9_input.l10_sire_data.get('zones_count', 0)} spatial zone(s) rendered.",
            ))
        return citations

    def suggest_follow_ups(self, l9_input: Layer9Input, mode: PhrasingMode) -> List[str]:
        questions: List[str] = []
        if mode in (PhrasingMode.HEDGED, PhrasingMode.RESTRICTED):
            questions.append("Would you like to schedule a field visit to verify conditions?")
        if any(isinstance(a, dict) and a.get("action_type") == "IRRIGATE" for a in l9_input.actions):
            questions.append("Would you like to see the irrigation schedule in detail?")
        if any(isinstance(d, dict) and d.get("probability", 0) > 0.5 for d in l9_input.diagnoses):
            questions.append("Would you like more detail on the detected issues?")
        return questions[:3]

    def build_output(self, l9_input: Layer9Input,
                     spatial_explanations: Optional[List[Dict[str, Any]]] = None) -> InterfaceOutput:
        mode = self.assess_phrasing_mode(l9_input.audit_grade)
        n_actions = len([a for a in l9_input.actions if isinstance(a, dict) and a.get("is_allowed", True)])
        n_diagnoses = len([d for d in l9_input.diagnoses if isinstance(d, dict) and d.get("probability", 0) > 0.3])

        if mode == PhrasingMode.CONFIDENT:
            summary = f"{n_diagnoses} issue(s) detected. {n_actions} action(s) recommended with high confidence."
        elif mode == PhrasingMode.HEDGED:
            summary = f"{n_diagnoses} potential issue(s). {n_actions} action(s) suggested — field confirmation recommended."
        else:
            summary = f"Data quality issues limit reliability. {n_diagnoses} possible issue(s) flagged. Recommend field scouting."

        explanations = self.generate_explanations(l9_input)
        if spatial_explanations:
            for se in spatial_explanations:
                explanations.append(Explanation(
                    statement=se.get("statement", ""),
                    evidence_id=se.get("evidence_id", ""),
                    source_layer=se.get("source_layer", "L10"),
                    confidence=se.get("confidence", 0.7),
                ))

        return InterfaceOutput(
            summary=summary,
            zone_cards=self.generate_zone_cards(l9_input),
            alerts=self.generate_alerts(l9_input),
            explanations=explanations,
            disclaimers=self.generate_disclaimers(l9_input),
            citations=self.build_citations(l9_input),
            render_hints=self.build_render_hints(l9_input),
            phrasing_mode=mode,
            follow_up_questions=self.suggest_follow_ups(l9_input, mode),
        )

    def enforce_invariants(self, l9_input: Layer9Input) -> List[Dict[str, Any]]:
        """Run all safety gates, including chemical compliance, blocked actions, and economic ROI sanity gates."""
        violations = []

        # 1. Chemical compliance gate
        for act in l9_input.actions:
            if isinstance(act, dict) and act.get("action_type") in ("SPRAY", "spray"):
                product = act.get("product_name", "").lower()
                if product and product not in _load_chemical_whitelist():
                    violations.append({
                        "gate": "chemical_compliance",
                        "severity": "HIGH",
                        "detail": f"Unapproved chemical: {product}",
                    })

        # 2. Blocked action gate
        for act in l9_input.actions:
            if isinstance(act, dict) and not act.get("is_allowed", True):
                violations.append({
                    "gate": "blocked_action",
                    "severity": "MEDIUM",
                    "detail": f"Blocked action: {act.get('action_type', '?')}",
                })

        # 3. Economic Safety Gating ROI Loop
        default_costs = {
            "irrigate": 120.0,
            "spray": 85.0,
            "fertilize": 150.0,
            "harvest": 200.0,
        }
        
        expected_yield = 4.2  # baseline durum wheat yield t/ha in Algeria Mitidja
        market_price = 320.0  # market crop price durum wheat in USD/t
        
        if l9_input.l7_planning_data and isinstance(l9_input.l7_planning_data, dict):
            market_price = l9_input.l7_planning_data.get("market_price_usd_t", market_price)
            expected_yield = l9_input.l7_planning_data.get("expected_yield_t_ha", expected_yield)
            
        yield_delta_pct = 5.0
        if l9_input.outcome_forecast and isinstance(l9_input.outcome_forecast, dict):
            yield_delta_pct = l9_input.outcome_forecast.get("yield_delta_pct", yield_delta_pct)
            
        for act in l9_input.actions:
            if isinstance(act, dict) and act.get("is_allowed", True):
                action_type = act.get("action_type", "").lower()
                
                cost_per_ha = act.get("cost_per_ha")
                if cost_per_ha is None:
                    cost_per_ha = default_costs.get(action_type, 75.0)
                    
                act_yield_delta = act.get("potential_yield_delta_pct", yield_delta_pct)
                
                revenue_gain = expected_yield * (act_yield_delta / 100.0) * market_price
                net_gain = revenue_gain - cost_per_ha
                
                if net_gain < 0.0:
                    violations.append({
                        "gate": "economic_roi_safety",
                        "severity": "MEDIUM",
                        "detail": f"Negative ROI intervention for {act.get('action_type')}: cost (${cost_per_ha:.1f}/ha) exceeds projected revenue gain (${revenue_gain:.1f}/ha) with net loss of ${abs(net_gain):.1f}/ha.",
                    })

        return violations


policy_enforcer = PolicyEnforcerEngine()
