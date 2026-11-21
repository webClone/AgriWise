"""
Layer 8.1: Reliability-Aware Action Ranking Engine v8.1.0

Ranks interventions using multi-objective scoring with evidence trace.
Reads L0 audit grade and upstream confidence to adjust behavior:
  - Grade A/B: normal ranking
  - Grade C: hedge toward SCOUT/MONITOR, set requires_confirmation=True
  - Grade D/F: restrict to SCOUT/WAIT/MONITOR, avoid irreversible actions
"""

import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

from layer8_prescriptive.schema import (
    ActionCard, ActionType, PriorityBreakdown, RateRange, TimeWindow,
    PrescriptiveEvidence, ConfidenceLevel, PrescriptiveDegradation,
    Layer8Input,
)


# ============================================================================
# Constants
# ============================================================================

# Weights for multi-objective scoring (configurable)
DEFAULT_WEIGHTS = {
    "impact": 0.30,
    "urgency": 0.25,
    "risk": 0.20,
    "cost": 0.10,
    "confidence": 0.15,
}

# Max safe rates per action type (kg/ha or mm)
MAX_SAFE_RATES = {
    ActionType.IRRIGATE: {"max": 80, "unit": "mm"},
    ActionType.FERTILIZE: {"max": 250, "unit": "kg_N/ha"},
    ActionType.SPRAY: {"max": 5, "unit": "L/ha"},
}

# Action types that are irreversible (should not be used under low trust)
IRREVERSIBLE_ACTIONS = {ActionType.SPRAY, ActionType.FERTILIZE, ActionType.REPLANT}

# Safe fallback actions for low-trust scenarios
SAFE_ACTIONS = {ActionType.SCOUT, ActionType.WAIT, ActionType.MONITOR}


# ============================================================================
# Core Engine
# ============================================================================

class ActionRankingEngine:
    """
    Produces ranked ActionCards from upstream diagnoses + constraints.
    
    Behavior adapts to L0 audit grade:
      - A/B: full ranking, all actions eligible
      - C: prefer SCOUT/MONITOR, mark irreversible as requires_confirmation
      - D/F: only SAFE_ACTIONS, no irreversible actions
    """
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS
    
    def rank_actions(self, l8_input: Layer8Input) -> List[ActionCard]:
        """
        Generate and rank action cards from upstream layer outputs.
        
        Returns:
            Sorted list of ActionCards (highest priority first)
        """
        degradation = self._assess_degradation(l8_input)
        confidence_level = self._assess_confidence(l8_input)
        
        # Generate candidate actions from upstream diagnoses
        candidates = self._generate_candidates(l8_input, degradation, confidence_level)
        
        # Score and rank
        for card in candidates:
            card.priority_score = self._compute_score(card.priority_breakdown)
        
        # Sort descending
        candidates.sort(key=lambda c: c.priority_score, reverse=True)
        
        # Apply reliability-aware adjustments
        candidates = self._apply_trust_adjustments(candidates, degradation, confidence_level, l8_input)
        
        logger.debug("Ranked %d candidates (degradation=%s, confidence=%s)",
                     len(candidates), degradation.value, confidence_level.value)
        return candidates
    
    def _assess_degradation(self, l8_input: Layer8Input) -> PrescriptiveDegradation:
        """Map audit grade + conflicts to degradation mode."""
        grade = l8_input.audit_grade.upper()
        
        if l8_input.conflicts:
            return PrescriptiveDegradation.CONFLICT_FLAG
        if grade in ("D", "F"):
            return PrescriptiveDegradation.VERY_LOW_TRUST
        if grade == "C":
            return PrescriptiveDegradation.LOW_TRUST
        return PrescriptiveDegradation.NORMAL
    
    def _assess_confidence(self, l8_input: Layer8Input) -> ConfidenceLevel:
        """Map audit grade to confidence level."""
        grade = l8_input.audit_grade.upper()
        if grade in ("A", "B"):
            return ConfidenceLevel.HIGH
        if grade == "C":
            return ConfidenceLevel.MODERATE
        return ConfidenceLevel.LOW
    
    def _generate_candidates(self, l8_input: Layer8Input,
                              degradation: PrescriptiveDegradation,
                              confidence: ConfidenceLevel) -> List[ActionCard]:
        """
        Generate ActionCards from upstream diagnoses.
        
        Maps:
          - WATER_STRESS → IRRIGATE
          - N_DEFICIENCY, P_DEFICIENCY, K_DEFICIENCY → FERTILIZE
          - FUNGAL_*, BACTERIAL_*, INSECT → SPRAY (or SCOUT first)
          - WEED_PRESSURE → SPRAY or SCOUT
          - Any unclear → SCOUT / MONITOR
        """
        cards: List[ActionCard] = []
        zones = l8_input.zone_ids if l8_input.zone_ids else ["plot"]
        
        # --- From L3 diagnoses ---
        for diag in l8_input.diagnoses:
            if isinstance(diag, dict):
                problem_id = diag.get("problem_id", "UNKNOWN")
                probability = diag.get("probability", 0.0)
                severity = diag.get("severity", 0.0)
                diag_confidence = diag.get("confidence", 0.5)
            else:
                problem_id = getattr(diag, "problem_id", "UNKNOWN")
                probability = getattr(diag, "probability", 0.0)
                severity = getattr(diag, "severity", 0.0)
                diag_confidence = getattr(diag, "confidence", 0.5)

            
            if probability < 0.2:
                continue  # skip low-probability diagnoses
            
            evidence = [PrescriptiveEvidence(
                source_layer="L3",
                evidence_type="diagnosis",
                reference_id=problem_id,
                contribution=probability * severity,
                description=f"{problem_id}: p={probability:.2f}, sev={severity:.2f}"
            )]
            
            action_type, rate = self._map_diagnosis_to_action(problem_id, severity)
            
            # Under low trust, force to SCOUT for irreversible actions
            if degradation in (PrescriptiveDegradation.LOW_TRUST,
                               PrescriptiveDegradation.VERY_LOW_TRUST,
                               PrescriptiveDegradation.CONFLICT_FLAG):
                if action_type in IRREVERSIBLE_ACTIONS:
                    if degradation == PrescriptiveDegradation.VERY_LOW_TRUST:
                        action_type = ActionType.SCOUT
                        rate = None
            
            breakdown = PriorityBreakdown(
                impact_score=min(1.0, probability * severity * 2),
                urgency_score=min(1.0, severity),
                risk_score=min(1.0, probability * 0.8),
                cost_score=0.7 if action_type in SAFE_ACTIONS else 0.4,
                confidence_score=min(1.0, diag_confidence),
            )
            
            card = ActionCard(
                action_id=self._make_id(problem_id, action_type),
                action_type=action_type,
                priority_score=0.0,  # computed later
                priority_breakdown=breakdown,
                zone_targets=zones,
                zone_allocation={z: 1.0 / len(zones) for z in zones},
                rate=rate,
                time_window=TimeWindow(
                    earliest=datetime.now().strftime("%Y-%m-%d"),
                    latest="",  # filled by scheduler
                ),
                evidence=evidence,
                confidence=confidence,
                explain=f"{action_type.value} recommended due to {problem_id} (p={probability:.0%})",
            )
            cards.append(card)
        
        # --- From L4 nutrient states ---
        for nutrient, state in l8_input.nutrient_states.items():
            prob_def = state.get("probability_deficient", 0.0) if isinstance(state, dict) else 0.0
            if prob_def > 0.3:
                evidence = [PrescriptiveEvidence(
                    source_layer="L4",
                    evidence_type="nutrient_state",
                    reference_id=f"{nutrient}_DEFICIENCY",
                    contribution=prob_def,
                    description=f"{nutrient} deficiency prob={prob_def:.2f}"
                )]
                
                action_type = ActionType.FERTILIZE
                if degradation == PrescriptiveDegradation.VERY_LOW_TRUST:
                    action_type = ActionType.SCOUT
                
                rate_val = min(prob_def * 150, MAX_SAFE_RATES[ActionType.FERTILIZE]["max"])

                # CEB03: Check upstream restrictions and conservation blockers
                is_card_allowed = state.get("is_allowed", True) if isinstance(state, dict) else True
                card_blocked_reasons = list(state.get("blocked_reasons", [])) if isinstance(state, dict) else []
                if isinstance(state, dict) and not state.get("mass_conserved", True):
                    is_card_allowed = False
                    if "nonconserved_water_transition" not in card_blocked_reasons:
                        card_blocked_reasons.append("nonconserved_water_transition")

                card_confidence = confidence
                conf_score = state.get("confidence", 0.5) if isinstance(state, dict) else 0.5
                if not is_card_allowed or conf_score < 0.3:
                    card_confidence = ConfidenceLevel.LOW
                elif conf_score < 0.6 and card_confidence == ConfidenceLevel.HIGH:
                    card_confidence = ConfidenceLevel.MODERATE

                cards.append(ActionCard(
                    action_id=self._make_id(f"{nutrient}_DEF", action_type),
                    action_type=action_type,
                    priority_score=0.0,
                    priority_breakdown=PriorityBreakdown(
                        impact_score=min(1.0, prob_def),
                        urgency_score=0.5,
                        risk_score=prob_def * 0.6,
                        cost_score=0.3,
                        confidence_score=conf_score,
                    ),
                    zone_targets=zones,
                    zone_allocation={z: 1.0 / len(zones) for z in zones},
                    rate=RateRange(
                        recommended=round(rate_val, 1),
                        min_safe=0,
                        max_safe=MAX_SAFE_RATES[ActionType.FERTILIZE]["max"],
                        unit="kg_N/ha",
                    ) if action_type == ActionType.FERTILIZE else None,
                    evidence=evidence,
                    is_allowed=is_card_allowed,
                    blocked_reason=card_blocked_reasons,
                    confidence=card_confidence,
                    explain=f"{'Fertilize' if action_type == ActionType.FERTILIZE else 'Scout'} for {nutrient} deficiency (p={prob_def:.0%})",
                ))
        
        # --- From L5 bio threats ---
        for threat_id, state in l8_input.bio_threats.items():
            prob = state.get("probability", 0.0) if isinstance(state, dict) else 0.0
            if prob > 0.25:
                evidence = [PrescriptiveEvidence(
                    source_layer="L5",
                    evidence_type="threat",
                    reference_id=threat_id,
                    contribution=prob,
                    description=f"Bio threat {threat_id} prob={prob:.2f}"
                )]
                
                action_type = ActionType.SPRAY if prob > 0.6 else ActionType.SCOUT
                if degradation != PrescriptiveDegradation.NORMAL:
                    action_type = ActionType.SCOUT
                
                cards.append(ActionCard(
                    action_id=self._make_id(threat_id, action_type),
                    action_type=action_type,
                    priority_score=0.0,
                    priority_breakdown=PriorityBreakdown(
                        impact_score=min(1.0, prob),
                        urgency_score=min(1.0, prob * 1.2),
                        risk_score=prob * 0.7,
                        cost_score=0.6 if action_type == ActionType.SCOUT else 0.2,
                        confidence_score=state.get("confidence", 0.5) if isinstance(state, dict) else 0.5,
                    ),
                    zone_targets=zones,
                    zone_allocation={z: 1.0 / len(zones) for z in zones},
                    evidence=evidence,
                    confidence=confidence,
                    explain=f"{'Scout for' if action_type == ActionType.SCOUT else 'Treat'} {threat_id} (p={prob:.0%})",
                ))
        
        # Always add MONITOR as a baseline action
        cards.append(ActionCard(
            action_id=self._make_id("BASELINE", ActionType.MONITOR),
            action_type=ActionType.MONITOR,
            priority_score=0.0,
            priority_breakdown=PriorityBreakdown(
                impact_score=0.1, urgency_score=0.1, risk_score=0.1,
                cost_score=0.95, confidence_score=1.0,
            ),
            zone_targets=zones,
            zone_allocation={z: 1.0 / len(zones) for z in zones},
            evidence=[],
            heuristic=True,
            confidence=ConfidenceLevel.HIGH,
            explain="Continue monitoring — baseline action",
        ))
        
        return cards
    
    def _map_diagnosis_to_action(self, problem_id: str,
                                  severity: float) -> tuple:
        """Map a diagnosis problem_id to an ActionType + optional RateRange."""
        pid = problem_id.upper()
        
        if "WATER_STRESS" in pid:
            rate = RateRange(
                recommended=round(min(severity * 40, 80), 1),
                min_safe=0, max_safe=80, unit="mm"
            )
            return ActionType.IRRIGATE, rate
        
        if any(n in pid for n in ("N_DEF", "P_DEF", "K_DEF", "NUTRIENT", "SALINITY")):
            rate = RateRange(
                recommended=round(min(severity * 100, 250), 1),
                min_safe=0, max_safe=250, unit="kg_N/ha"
            )
            return ActionType.FERTILIZE, rate
        
        if any(t in pid for t in ("FUNGAL", "RUST", "MILDEW", "BACTERIAL", "BLIGHT")):
            return ActionType.SPRAY if severity > 0.5 else ActionType.SCOUT, None
        
        if any(t in pid for t in ("INSECT", "BORER", "CHEWING", "SUCKING")):
            return ActionType.SPRAY if severity > 0.5 else ActionType.SCOUT, None
        
        if "WEED" in pid:
            return ActionType.SPRAY if severity > 0.6 else ActionType.SCOUT, None
        
        return ActionType.SCOUT, None
    
    def _compute_score(self, bd: PriorityBreakdown) -> float:
        """Weighted sum of priority breakdown components."""
        w = self.weights
        score = (
            bd.impact_score * w["impact"] +
            bd.urgency_score * w["urgency"] +
            bd.risk_score * w["risk"] +
            bd.cost_score * w["cost"] +
            bd.confidence_score * w["confidence"]
        )
        return round(score, 4)
    
    def _apply_trust_adjustments(self, cards: List[ActionCard],
                                  degradation: PrescriptiveDegradation,
                                  confidence: ConfidenceLevel,
                                  l8_input: Layer8Input) -> List[ActionCard]:
        """Post-ranking adjustments based on trust level."""
        # Check conflicts for high-conflict status
        has_high_conflict = False
        for c in l8_input.conflicts:
            if c.get("severity") == "major" or "conflict" in str(c.get("type", "")).lower():
                has_high_conflict = True

        for card in cards:
            # 1. Populating driver provenance across all 13 canonical states.
            from services.agribrain.scientific_contracts.state_schema_ref import STATE_ORDER
            import re
            participating_vars = []
            evidence_texts = [
                str(getattr(ev, "reference_id", "") or "") + " " + str(getattr(ev, "description", "") or "")
                for ev in card.evidence
            ]
            evidence_texts.append(str(card.explain or ""))
            for state in STATE_ORDER:
                key = f"ASMAE_{state.upper()}"
                expr = r"(?<![a-z0-9_])asmae_(?:" + re.escape(state.lower()) + r")(?![a-z0-9_])"
                artifact = r"(?<![a-z0-9_])asmae_artifact:" + re.escape(state.lower()) + r"(?![a-z0-9_])"
                if any(re.search(expr, text.lower()) or re.search(artifact, text.lower()) for text in evidence_texts):
                    participating_vars.append(key)
            if participating_vars:
                card.primary_driver = participating_vars[0]
                card.driver_source_family = "asmae"
                feat = l8_input.asmae_features.get(card.primary_driver)
                if feat is not None:
                    def _read_fld(f, key, default=None):
                        return f.get(key, default) if isinstance(f, dict) else getattr(f, key, default)
                    def _finite_fld(f, key):
                        import math
                        v = _read_fld(f, key)
                        try:
                            return float(v) if v is not None and math.isfinite(float(v)) else None
                        except (TypeError, ValueError, OverflowError):
                            return None
                    card.driver_confidence = _finite_fld(feat, "confidence")
                    card.driver_uncertainty = _finite_fld(feat, "uncertainty")
                    card.driver_channel = _read_fld(feat, "asmae_channel") or _read_fld(feat, "channel") or "diagnostic"
                else:
                    card.driver_confidence = None
                    card.driver_uncertainty = None
                    card.driver_channel = "diagnostic"
                card.corroborating_sources = [
                    str(getattr(ev, "reference_id", "")) for ev in card.evidence
                    if str(getattr(ev, "reference_id", "") or "")
                    and "asmae" not in str(getattr(ev, "reference_id", "")).lower()
                ]

            # 2. Irreversible ASMAE-driven action safety gates
            if card.action_type in IRREVERSIBLE_ACTIONS and card.driver_source_family == "asmae":
                conf_val = card.driver_confidence
                unc_val = card.driver_uncertainty
                channel = card.driver_channel
                
                # Missing physical uncertainty, disagreement or local resolution
                # is NOT equivalent to 0 sigma, zero BMA disagreement or 10 m.
                bma_disagreement = None
                res_m = None
                diag_only = True
                state_allowed = False
                participating_vars = locals().get("participating_vars", [])
                participating_authorized = bool(participating_vars)
                for var in participating_vars:
                    candidate = l8_input.asmae_features.get(var)
                    if candidate is None:
                        participating_authorized = False
                        continue
                    def _attr(k, default=None):
                        return candidate.get(k, default) if isinstance(candidate, dict) else getattr(candidate, k, default)
                    import math
                    try:
                        bma = float(_attr("bma_disagreement"))
                        res = float(_attr("resolution_m"))
                        sig = float(_attr("uncertainty"))
                        conf = float(_attr("confidence"))
                        valid_numbers = all(math.isfinite(q) for q in (bma, res, sig, conf))
                    except (ValueError, TypeError, OverflowError):
                        valid_numbers = False
                    if not valid_numbers or bma > 0.3 or res <= 1.0 or sig > 0.5 or conf < 0.45:
                        participating_authorized = False
                    if _attr("diagnostic_only", True) is not False or _attr("state_update_allowed") is not True:
                        participating_authorized = False
                    if (_attr("asmae_channel") or _attr("channel")) in ("diagnostic", "visual", None):
                        participating_authorized = False
                    if var == card.primary_driver and valid_numbers:
                        bma_disagreement, res_m = bma, res
                        diag_only = _attr("diagnostic_only", True)
                        state_allowed = _attr("state_update_allowed") is True

                # W2-B contains no independently signed server-side action
                # certificate verifier. Even a self-consistent high-confidence
                # ASMAE feature cannot authorize irreversible prescriptions.
                # Keep this false until a separate verified action gate is built.
                signed_action_authority_verified = False
                is_blocked = (
                    not signed_action_authority_verified
                    or not participating_authorized
                    or conf_val is None or unc_val is None
                    or bma_disagreement is None or res_m is None
                    or diag_only or not state_allowed
                    or channel in ("diagnostic", "visual", None)
                    or has_high_conflict
                )

                if is_blocked:
                    card.is_allowed = False
                    card.blocked_reason.append("blocked_by_asmae_safety_gate")
                    card.explain += " [BLOCKED: ASMAE trust/safety gate failed]"
                else:
                    # REQUIRE CONFIRMATION Check
                    is_req_conf = (
                        (0.45 <= conf_val <= 0.65)
                        or (0.35 <= unc_val <= 0.50)
                        or (0.20 <= bma_disagreement <= 0.30)
                    )
                    if is_req_conf:
                        card.requires_confirmation = True
                        card.explain += " [requires field confirmation]"
                    else:
                        # CORROBORATION REQUIRED Check
                        is_corrob_req = (0.65 < conf_val <= 0.80)
                        if is_corrob_req:
                            if not card.corroborating_sources:
                                card.requires_confirmation = True
                                card.explain += " [requires non-ASMAE corroboration]"
            
            # 3. Standard degradation adjustments (fallbacks)
            if card.is_allowed:
                if degradation in (PrescriptiveDegradation.LOW_TRUST,
                                   PrescriptiveDegradation.CONFLICT_FLAG):
                    if card.action_type in IRREVERSIBLE_ACTIONS:
                        card.requires_confirmation = True
                        card.explain += " [requires field confirmation]"
                
                if degradation == PrescriptiveDegradation.VERY_LOW_TRUST:
                    if card.action_type in IRREVERSIBLE_ACTIONS:
                        card.is_allowed = False
                        card.blocked_reason.append("audit_grade_too_low")
                        card.explain += " [BLOCKED: insufficient data quality]"
            
            # Widen rate ranges under uncertainty
            if confidence != ConfidenceLevel.HIGH and card.rate:
                spread = 0.3 if confidence == ConfidenceLevel.MODERATE else 0.5
                card.rate = RateRange(
                    recommended=card.rate.recommended,
                    min_safe=max(0, card.rate.recommended * (1 - spread)),
                    max_safe=min(card.rate.max_safe, card.rate.recommended * (1 + spread)),
                    unit=card.rate.unit,
                )
        
        return cards
    
    def _make_id(self, ref: str, action_type: ActionType) -> str:
        """Generate deterministic action ID."""
        raw = f"{ref}_{action_type.value}"
        return f"ACT-{hashlib.md5(raw.encode()).hexdigest()[:8]}"


# Singleton
action_ranker = ActionRankingEngine()
