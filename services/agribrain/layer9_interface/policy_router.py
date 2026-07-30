"""
Layer 9.6: Reliability-Aware Policy Router

Routes LLM phrasing based on L0 audit grade:
  - Grade A/B: CONFIDENT mode — precise, assertive
  - Grade C: HEDGED mode — recommend confirmation, widen ranges
  - Grade D/F: RESTRICTED mode — data issues, scouting only

Enforced BEFORE LLM call, not after.
"""

from typing import Dict, Any, List, Optional

from layer9_interface.schema import (
    Layer9Input, InterfaceOutput, Alert, AlertType, AlertSeverity,
    ZoneCard, Explanation, Disclaimer, Citation, RenderHint,
    BadgeColor, PhrasingMode,
)


class PolicyRouter:
    """
    Determines phrasing mode + generates disclaimers + alerts
    based on upstream audit grade and data quality.
    """
    
    def assess_phrasing_mode(self, audit_grade: str) -> PhrasingMode:
        """Map audit grade to phrasing mode."""
        grade = audit_grade.upper()
        if grade in ("A", "B"):
            return PhrasingMode.CONFIDENT
        if grade == "C":
            return PhrasingMode.HEDGED
        return PhrasingMode.RESTRICTED
    
    def get_badge_color(self, audit_grade: str) -> BadgeColor:
        """Map audit grade to badge color."""
        grade = audit_grade.upper()
        if grade in ("A", "B"):
            return BadgeColor.GREEN
        if grade == "C":
            return BadgeColor.YELLOW
        if grade in ("D", "F"):
            return BadgeColor.RED
        return BadgeColor.GRAY
    
    def generate_disclaimers(self, l9_input: Layer9Input) -> List[Disclaimer]:
        """Generate mandatory disclaimers based on data quality."""
        disclaimers: List[Disclaimer] = []
        grade = l9_input.audit_grade.upper()
        
        if grade in ("D", "F"):
            disclaimers.append(Disclaimer(
                text="Data quality issues detected. Recommendations are preliminary and require field confirmation before any action.",
                reason="low_audit_grade",
                severity=AlertSeverity.CRITICAL,
            ))
        elif grade == "C":
            disclaimers.append(Disclaimer(
                text="Some data gaps or inconsistencies detected. Consider verifying conditions in the field before proceeding.",
                reason="moderate_audit_grade",
                severity=AlertSeverity.WARNING,
            ))
        
        # Conflicts
        if l9_input.conflicts:
            disclaimers.append(Disclaimer(
                text=f"{len(l9_input.conflicts)} data conflict(s) detected between sources. "
                     "Affected recommendations should be treated as tentative.",
                reason="conflict",
                severity=AlertSeverity.WARNING,
            ))
        
        # Low reliability sources
        for source, rel in l9_input.source_reliability.items():
            if rel < 0.5:
                disclaimers.append(Disclaimer(
                    text=f"Source '{source}' has low reliability ({rel:.0%}). "
                         "Data from this source may be unreliable.",
                    reason=f"low_reliability_{source}",
                    severity=AlertSeverity.WARNING,
                ))
        
        # Chemical safety
        has_spray = any(
            a.get("action_type") in ("SPRAY", "spray")
            for a in l9_input.actions
            if isinstance(a, dict) and a.get("is_allowed", True)
        )
        if has_spray:
            disclaimers.append(Disclaimer(
                text="Ensure compliance with local regulations and check product label constraints before any chemical application.",
                reason="chemical_safety",
                severity=AlertSeverity.INFO,
            ))
        
        return disclaimers
    
    def generate_alerts(self, l9_input: Layer9Input) -> List[Alert]:
        """Generate structured alerts from upstream data."""
        alerts: List[Alert] = []
        
        # Data quality alert
        grade = l9_input.audit_grade.upper()
        if grade in ("C", "D", "F"):
            alerts.append(Alert(
                alert_type=AlertType.DATA_QUALITY,
                severity=AlertSeverity.CRITICAL if grade in ("D", "F") else AlertSeverity.WARNING,
                message=f"Data quality grade: {grade}",
                trigger_evidence_id="L0_audit",
                action_required=grade in ("D", "F"),
            ))
        
        # Conflict alerts
        for i, conflict in enumerate(l9_input.conflicts):
            alerts.append(Alert(
                alert_type=AlertType.SYSTEM,
                severity=AlertSeverity.WARNING,
                message=conflict.get("description", f"Conflict #{i+1}"),
                trigger_evidence_id=conflict.get("id", f"conflict_{i}"),
            ))
        
        # Blocked action alerts
        for action in l9_input.actions:
            if isinstance(action, dict) and not action.get("is_allowed", True):
                alerts.append(Alert(
                    alert_type=AlertType.SYSTEM,
                    severity=AlertSeverity.WARNING,
                    message=f"Action '{action.get('action_type', 'unknown')}' blocked: "
                            f"{', '.join(action.get('blocked_reason', ['policy restriction']))}",
                    trigger_evidence_id=action.get("action_id", "unknown"),
                ))
        
        return alerts
    
    def generate_zone_cards(self, l9_input: Layer9Input) -> List[ZoneCard]:
        """Build zone summary cards — enriched with L10 spatial metrics if available."""
        cards: List[ZoneCard] = []
        badge = self.get_badge_color(l9_input.audit_grade)
        
        zone_plan = l9_input.zone_plan
        if isinstance(zone_plan, dict):
            for zone_id, plan in zone_plan.items():
                top_action = None
                key_metrics = {}
                status_text = ""
                
                if isinstance(plan, dict):
                    actions = plan.get("actions", [])
                    top_action = actions[0] if actions else None
                    status_text = plan.get("reason", "")
                    
                    # Enrich with L10 spatial intelligence
                    if plan.get("spatial_severity") is not None:
                        key_metrics["severity"] = round(plan["spatial_severity"], 2)
                        key_metrics["confidence"] = round(plan.get("spatial_confidence", 0.0), 2)
                        key_metrics["area_pct"] = round(plan.get("area_pct", 0.0), 1)
                        key_metrics["zone_type"] = plan.get("zone_type", "")
                        key_metrics["top_drivers"] = plan.get("top_drivers", [])
                        
                        # Surface-level stats (NDVI, etc.)
                        surface_stats = plan.get("surface_stats", {})
                        if surface_stats:
                            key_metrics["surface_stats"] = surface_stats
                        
                        # Linked L8 actions
                        linked = plan.get("linked_actions", [])
                        if linked:
                            key_metrics["linked_actions"] = linked
                        
                        # Use L10 label/description for richer status
                        label = plan.get("label", "")
                        desc = plan.get("description", "")
                        if label and desc:
                            status_text = f"{label}: {desc}"
                        elif label:
                            status_text = label
                        elif desc:
                            status_text = desc
                
                cards.append(ZoneCard(
                    zone_id=zone_id,
                    top_action=top_action,
                    confidence_badge=badge,
                    key_metrics=key_metrics,
                    status_text=status_text,
                ))
        
        return cards
    
    def generate_explanations(self, l9_input: Layer9Input) -> List[Explanation]:
        """Build evidence-backed explanations from diagnoses."""
        explanations: List[Explanation] = []
        
        for diag in l9_input.diagnoses:
            if isinstance(diag, dict) and diag.get("probability", 0) > 0.3:
                prob = diag.get("probability", 0)
                sev = diag.get("severity", 0)
                pid = diag.get("problem_id", "unknown")
                
                explanations.append(Explanation(
                    statement=f"Because {pid.replace('_', ' ').lower()} was detected with "
                              f"{prob:.0%} probability and {sev:.0%} severity",
                    evidence_id=pid,
                    source_layer="L3",
                    confidence=diag.get("confidence", 0.5),
                ))
        
        return explanations
    
    def build_render_hints(self, l9_input: Layer9Input) -> RenderHint:
        """Build UI render directives — uses L10 spatial severity for zone highlighting."""
        badge = self.get_badge_color(l9_input.audit_grade)
        
        # Highlight zones with high spatial severity from L10, or HIGH priority from L8
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
    
    def build_output(self, l9_input: Layer9Input,
                     spatial_explanations: Optional[List[Dict[str, Any]]] = None) -> InterfaceOutput:
        """
        Full Layer 9 output generation.
        
        Deterministic rendering of upstream data — no hallucination possible.
        Spatial explanations from L10 are appended to the explanation list.
        """
        mode = self.assess_phrasing_mode(l9_input.audit_grade)
        
        # Build summary based on phrasing mode
        summary = self._build_summary(l9_input, mode)
        
        # Merge L3 explanations with L10 spatial explanations
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
            citations=self._build_citations(l9_input),
            render_hints=self.build_render_hints(l9_input),
            phrasing_mode=mode,
            follow_up_questions=self._suggest_follow_ups(l9_input, mode),
        )
    
    def _build_summary(self, l9_input: Layer9Input, mode: PhrasingMode) -> str:
        """Build summary text adapted to phrasing mode."""
        n_actions = len([a for a in l9_input.actions
                        if isinstance(a, dict) and a.get("is_allowed", True)])
        n_diagnoses = len([d for d in l9_input.diagnoses
                          if isinstance(d, dict) and d.get("probability", 0) > 0.3])
        
        if mode == PhrasingMode.CONFIDENT:
            return (f"{n_diagnoses} issue(s) detected. "
                    f"{n_actions} action(s) recommended with high confidence.")
        elif mode == PhrasingMode.HEDGED:
            return (f"{n_diagnoses} potential issue(s) detected. "
                    f"{n_actions} action(s) suggested — field confirmation recommended "
                    f"before proceeding.")
        else:  # RESTRICTED
            return (f"Data quality issues limit analysis reliability. "
                    f"{n_diagnoses} possible issue(s) flagged for verification. "
                    f"Recommend field scouting before any intervention.")
    
    def _build_citations(self, l9_input: Layer9Input) -> List[Citation]:
        """Build citations from upstream data."""
        citations: List[Citation] = []
        
        citations.append(Citation(
            source_layer="L0",
            reference_id="audit_grade",
            description=f"Audit grade: {l9_input.audit_grade}",
        ))
        
        for diag in l9_input.diagnoses:
            if isinstance(diag, dict):
                citations.append(Citation(
                    source_layer="L3",
                    reference_id=diag.get("problem_id", "unknown"),
                    value=diag.get("probability"),
                    description=f"Diagnosis: {diag.get('problem_id', '?')} "
                                f"p={diag.get('probability', 0):.2f}",
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
    
    def _suggest_follow_ups(self, l9_input: Layer9Input,
                             mode: PhrasingMode) -> List[str]:
        """Suggest follow-up questions based on context."""
        questions: List[str] = []
        
        if mode in (PhrasingMode.HEDGED, PhrasingMode.RESTRICTED):
            questions.append("Would you like to schedule a field visit to verify conditions?")
        
        if any(isinstance(a, dict) and a.get("action_type") == "IRRIGATE"
               for a in l9_input.actions):
            questions.append("Would you like to see the irrigation schedule in detail?")
        
        if any(isinstance(d, dict) and d.get("probability", 0) > 0.5
               for d in l9_input.diagnoses):
            questions.append("Would you like more detail on the detected issues?")
        
        return questions[:3]  # max 3 follow-ups

    def filter_advice(self, advice: str, action_type: str, confidence: str) -> str:
        """
        Filters advice and appends necessary disclaimers based on action type and data confidence.
        """
        disclaimers = []
        if action_type.lower() == "spray":
            disclaimers.append("SAFETY: Ensure compliance with regulations and check product label constraints.")
        if confidence.lower() == "low":
            disclaimers.append("LOW CONFIDENCE: Verified data missing. We strongly recommend field scouting.")
            
        if disclaimers:
            return f"{advice}\n\n[Disclaimers]\n" + "\n".join(f"- {d}" for d in disclaimers)
        return advice


# Singleton
policy = PolicyRouter()
