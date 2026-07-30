"""
Layer 5.4: BioThreat Inference Engine — Research-Grade Bayesian Log-Odds

Replaces the v5.0 flat function with a class-based Bayesian engine
matching the L4 NutrientInferenceEngine architecture.

Architecture:
  - Per-threat-class methods with domain-specific evidence weighting
  - Explicit Belief/Trust separation:
      * Probability = sigmoid(sum of logit evidence) — WHAT WE BELIEVE
      * Confidence = 1.0 minus penalty terms — HOW MUCH WE TRUST THE BELIEF
  - L3 confounder integration (water stress, weeds, mechanical damage)
  - Phenology-aware timing criticality
  - Dynamic prior consumption
  - DATA_GAP auto-injection when confidence collapses

Probability = Belief from Evidence (Logits)
Confidence = Trust from Data Quality (Penalties)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from layer5_bio.schema import (
    ThreatId, ThreatClass, BioThreatState, Severity, EvidenceLogit,
    SpreadPattern, Confounder,
)
from layer3_decision.schema import Driver
from layer5_bio.knowledge.threats import THREAT_PRIORS, THREAT_CLASS


# ── Utilities ────────────────────────────────────────────────────────────

def _sigmoid(logit: float) -> float:
    """Numerically stable sigmoid."""
    logit = max(-20.0, min(20.0, logit))
    if logit >= 0:
        z = math.exp(-logit)
        return 1.0 / (1.0 + z)
    z = math.exp(logit)
    return z / (1.0 + z)


def _logit(p: float) -> float:
    """Convert probability to log-odds."""
    p = max(1e-6, min(1.0 - 1e-6, p))
    return math.log(p / (1.0 - p))


def _severity_from_prob(prob: float, timing_criticality: float = 1.0) -> Severity:
    """Map probability × timing criticality to severity enum."""
    score = prob * timing_criticality
    if score > 0.85:
        return Severity.CRITICAL
    if score > 0.65:
        return Severity.HIGH
    if score > 0.45:
        return Severity.MODERATE
    return Severity.LOW


# ── BioThreat Inference Engine ───────────────────────────────────────────

class BioThreatInferenceEngine:
    """Research-grade biotic threat inference with Bayesian log-odds.
    
    Follows L4 NutrientInferenceEngine pattern:
      - infer_states() dispatches to per-threat methods
      - Each method accumulates logit evidence + confidence penalties
      - Evidence trace is fully auditable
    """

    def infer_states(
        self,
        evidence_by_threat: Dict[ThreatId, List[EvidenceLogit]],
        spread: Dict[str, Any],
        priors: Dict[ThreatId, float],
        l3_decision: Any = None,
        wdp: Optional[Dict[str, Any]] = None,
        phenology_stage: str = "",
        missing_drivers: Optional[List[str]] = None,
    ) -> Dict[str, BioThreatState]:
        """Infer threat states for all threat types.
        
        Parameters
        ----------
        evidence_by_threat : per-threat evidence logits from remote_signature
        spread             : spread pattern dict from spread_signature
        priors             : dynamic priors from compute_dynamic_priors()
        l3_decision        : L3 DecisionOutput for confounder extraction
        wdp                : weather pressure dict for LWD metrics
        phenology_stage    : current crop growth stage
        missing_drivers    : list of missing data driver IDs
        """
        pattern = spread.get("pattern", SpreadPattern.UNKNOWN)
        if isinstance(pattern, SpreadPattern):
            spread_pattern = pattern
        else:
            spread_pattern = SpreadPattern.UNKNOWN
        
        missing = missing_drivers or []
        wdp = wdp or {}
        
        states: Dict[str, BioThreatState] = {}

        # ── Fungal Diseases ─────────────────────────────────────────────
        states[ThreatId.FUNGAL_LEAF_SPOT.value] = self._infer_fungal_leaf_spot(
            evidence_by_threat.get(ThreatId.FUNGAL_LEAF_SPOT, []),
            priors, spread_pattern, l3_decision, wdp, phenology_stage, missing,
        )
        states[ThreatId.FUNGAL_RUST.value] = self._infer_fungal_rust(
            evidence_by_threat.get(ThreatId.FUNGAL_RUST, []),
            priors, spread_pattern, l3_decision, wdp, phenology_stage, missing,
        )
        states[ThreatId.DOWNY_MILDEW.value] = self._infer_downy_mildew(
            evidence_by_threat.get(ThreatId.DOWNY_MILDEW, []),
            priors, spread_pattern, l3_decision, wdp, phenology_stage, missing,
        )
        states[ThreatId.POWDERY_MILDEW.value] = self._infer_powdery_mildew(
            evidence_by_threat.get(ThreatId.POWDERY_MILDEW, []),
            priors, spread_pattern, l3_decision, wdp, phenology_stage, missing,
        )

        # ── Bacterial ───────────────────────────────────────────────────
        states[ThreatId.BACTERIAL_BLIGHT.value] = self._infer_bacterial(
            evidence_by_threat.get(ThreatId.BACTERIAL_BLIGHT, []),
            priors, spread_pattern, l3_decision, wdp, phenology_stage, missing,
        )

        # ── Insects ─────────────────────────────────────────────────────
        states[ThreatId.CHEWING_INSECTS.value] = self._infer_chewing_insects(
            evidence_by_threat.get(ThreatId.CHEWING_INSECTS, []),
            priors, spread_pattern, l3_decision, wdp, phenology_stage, missing,
        )
        states[ThreatId.SUCKING_INSECTS.value] = self._infer_sucking_insects(
            evidence_by_threat.get(ThreatId.SUCKING_INSECTS, []),
            priors, spread_pattern, l3_decision, wdp, phenology_stage, missing,
        )
        states[ThreatId.BORERS.value] = self._infer_borers(
            evidence_by_threat.get(ThreatId.BORERS, []),
            priors, spread_pattern, l3_decision, wdp, phenology_stage, missing,
        )

        # ── Weeds ───────────────────────────────────────────────────────
        states[ThreatId.WEED_PRESSURE.value] = self._infer_weed_pressure(
            evidence_by_threat.get(ThreatId.WEED_PRESSURE, []),
            priors, spread_pattern, l3_decision, wdp, phenology_stage, missing,
        )

        # ── DATA_GAP auto-injection ─────────────────────────────────────
        # If overall data quality is too low, inject a system-level DATA_GAP threat
        min_conf = min((s.confidence for s in states.values()), default=1.0)
        if min_conf < 0.45 or "L1_Rain" in missing or "L1_Temp" in missing:
            states[ThreatId.DATA_GAP.value] = BioThreatState(
                threat_id=ThreatId.DATA_GAP,
                threat_class=ThreatClass.SYSTEM,
                probability=0.7,
                confidence=min_conf,
                severity=Severity.MODERATE,
                drivers_used=[],
                evidence_trace=[],
                spread_pattern=spread_pattern,
                confounders=[],
                notes="Low data reliability; verify with field scouting/photos.",
            )

        return states

    # ------------------------------------------------------------------
    # Per-Threat Inference Methods
    # ------------------------------------------------------------------

    def _infer_fungal_leaf_spot(
        self, ev_list, priors, spread_pattern, l3, wdp, stage, missing,
    ) -> BioThreatState:
        """Fungal Leaf Spot — wetness + LWD + temperature band."""
        tid = ThreatId.FUNGAL_LEAF_SPOT
        prior = priors.get(tid, 0.10)
        logit = _logit(prior)
        trace = list(ev_list)  # Copy evidence from remote_signature
        drivers = set()

        # Accumulate evidence logits
        for ev in ev_list:
            logit += ev.weight * ev.logit_delta
            drivers.add(ev.driver)

        # LWD-specific boost: consecutive wet days > 3 → strong fungal signal
        lwd_consec = int(wdp.get("lwd_consecutive_wet_days", 0))
        if lwd_consec >= 3:
            delta = min(1.5, lwd_consec * 0.4)
            logit += delta
            trace.append(EvidenceLogit(
                Driver.RAIN, f"LWD consecutive wet days={lwd_consec}",
                delta, 1.0, {"lwd_consecutive_wet_days": lwd_consec}
            ))
            drivers.add(Driver.RAIN)

        prob = _sigmoid(logit)

        # Confidence (Trust) — separate from probability
        conf, confounders = self._compute_confidence(
            l3, wdp, missing, has_lwd=bool(wdp.get("lwd_available")),
        )

        return BioThreatState(
            threat_id=tid,
            threat_class=ThreatClass.DISEASE,
            probability=round(prob, 4),
            confidence=round(conf, 4),
            severity=_severity_from_prob(prob, self._timing_crit(stage, ThreatClass.DISEASE)),
            drivers_used=sorted(list(drivers), key=str),
            evidence_trace=trace,
            spread_pattern=spread_pattern,
            confounders=confounders,
            notes="Bayesian log-odds: LWD + fungal_pressure + NDVI anomaly",
        )

    def _infer_fungal_rust(self, ev_list, priors, spread_pattern, l3, wdp, stage, missing):
        """Fungal Rust — similar to leaf spot but needs longer LWD + wind dispersal."""
        tid = ThreatId.FUNGAL_RUST
        prior = priors.get(tid, 0.08)
        logit = _logit(prior)
        trace = list(ev_list)
        drivers = set()

        for ev in ev_list:
            logit += ev.weight * ev.logit_delta
            drivers.add(ev.driver)

        prob = _sigmoid(logit)
        conf, confounders = self._compute_confidence(l3, wdp, missing, has_lwd=bool(wdp.get("lwd_available")))

        return BioThreatState(
            threat_id=tid, threat_class=ThreatClass.DISEASE,
            probability=round(prob, 4), confidence=round(conf, 4),
            severity=_severity_from_prob(prob, self._timing_crit(stage, ThreatClass.DISEASE)),
            drivers_used=sorted(list(drivers), key=str),
            evidence_trace=trace, spread_pattern=spread_pattern,
            confounders=confounders,
            notes="Bayesian log-odds: LWD + rust-specific evidence",
        )

    def _infer_downy_mildew(self, ev_list, priors, spread_pattern, l3, wdp, stage, missing):
        """Downy Mildew — oomycete; prolonged wetness + moderate temps + clay."""
        tid = ThreatId.DOWNY_MILDEW
        prior = priors.get(tid, 0.06)
        logit = _logit(prior)
        trace = list(ev_list)
        drivers = set()

        for ev in ev_list:
            logit += ev.weight * ev.logit_delta
            drivers.add(ev.driver)

        prob = _sigmoid(logit)
        conf, confounders = self._compute_confidence(l3, wdp, missing, has_lwd=bool(wdp.get("lwd_available")))
        # Downy mildew is harder to diagnose remotely
        conf *= 0.85

        return BioThreatState(
            threat_id=tid, threat_class=ThreatClass.DISEASE,
            probability=round(prob, 4), confidence=round(max(0.10, conf), 4),
            severity=_severity_from_prob(prob, self._timing_crit(stage, ThreatClass.DISEASE)),
            drivers_used=sorted(list(drivers), key=str),
            evidence_trace=trace, spread_pattern=spread_pattern,
            confounders=confounders,
            notes="Bayesian log-odds: wetness + temp band + soil clay proxy",
        )

    def _infer_powdery_mildew(self, ev_list, priors, spread_pattern, l3, wdp, stage, missing):
        """Powdery Mildew — dry leaves + moderate RH + diurnal oscillation."""
        tid = ThreatId.POWDERY_MILDEW
        prior = priors.get(tid, 0.06)
        logit = _logit(prior)
        trace = list(ev_list)
        drivers = set()

        for ev in ev_list:
            logit += ev.weight * ev.logit_delta
            drivers.add(ev.driver)

        prob = _sigmoid(logit)
        conf, confounders = self._compute_confidence(l3, wdp, missing, has_lwd=bool(wdp.get("lwd_available")))

        return BioThreatState(
            threat_id=tid, threat_class=ThreatClass.DISEASE,
            probability=round(prob, 4), confidence=round(conf, 4),
            severity=_severity_from_prob(prob, self._timing_crit(stage, ThreatClass.DISEASE)),
            drivers_used=sorted(list(drivers), key=str),
            evidence_trace=trace, spread_pattern=spread_pattern,
            confounders=confounders,
            notes="Bayesian log-odds: dry + diurnal oscillation + moderate RH",
        )

    def _infer_bacterial(self, ev_list, priors, spread_pattern, l3, wdp, stage, missing):
        """Bacterial Blight — warm + wet + rain splash."""
        tid = ThreatId.BACTERIAL_BLIGHT
        prior = priors.get(tid, 0.05)
        logit = _logit(prior)
        trace = list(ev_list)
        drivers = set()

        for ev in ev_list:
            logit += ev.weight * ev.logit_delta
            drivers.add(ev.driver)

        prob = _sigmoid(logit)
        conf, confounders = self._compute_confidence(l3, wdp, missing, has_lwd=bool(wdp.get("lwd_available")))

        return BioThreatState(
            threat_id=tid, threat_class=ThreatClass.DISEASE,
            probability=round(prob, 4), confidence=round(conf, 4),
            severity=_severity_from_prob(prob, self._timing_crit(stage, ThreatClass.DISEASE)),
            drivers_used=sorted(list(drivers), key=str),
            evidence_trace=trace, spread_pattern=spread_pattern,
            confounders=confounders,
            notes="Bayesian log-odds: bacterial_pressure + LWD + rain",
        )

    def _infer_chewing_insects(self, ev_list, priors, spread_pattern, l3, wdp, stage, missing):
        """Chewing Insects — degree-days + patchy NDVI drop."""
        tid = ThreatId.CHEWING_INSECTS
        prior = priors.get(tid, 0.09)
        logit = _logit(prior)
        trace = list(ev_list)
        drivers = set()

        for ev in ev_list:
            logit += ev.weight * ev.logit_delta
            drivers.add(ev.driver)

        prob = _sigmoid(logit)
        conf, confounders = self._compute_confidence(
            l3, wdp, missing, has_lwd=False,  # LWD not relevant for insects
        )
        # Insect diagnosis is inherently less precise from remote sensing
        conf *= 0.90

        return BioThreatState(
            threat_id=tid, threat_class=ThreatClass.INSECT,
            probability=round(prob, 4), confidence=round(max(0.10, conf), 4),
            severity=_severity_from_prob(prob, self._timing_crit(stage, ThreatClass.INSECT)),
            drivers_used=sorted(list(drivers), key=str),
            evidence_trace=trace, spread_pattern=spread_pattern,
            confounders=confounders,
            notes="Bayesian log-odds: degree-days + patchy drop + insect pressure",
        )

    def _infer_sucking_insects(self, ev_list, priors, spread_pattern, l3, wdp, stage, missing):
        """Sucking Insects — degree-days + NDVI stall (not drop)."""
        tid = ThreatId.SUCKING_INSECTS
        prior = priors.get(tid, 0.08)
        logit = _logit(prior)
        trace = list(ev_list)
        drivers = set()

        for ev in ev_list:
            logit += ev.weight * ev.logit_delta
            drivers.add(ev.driver)

        prob = _sigmoid(logit)
        conf, confounders = self._compute_confidence(l3, wdp, missing, has_lwd=False)
        conf *= 0.85  # Even harder to diagnose remotely than chewing

        return BioThreatState(
            threat_id=tid, threat_class=ThreatClass.INSECT,
            probability=round(prob, 4), confidence=round(max(0.10, conf), 4),
            severity=_severity_from_prob(prob, self._timing_crit(stage, ThreatClass.INSECT)),
            drivers_used=sorted(list(drivers), key=str),
            evidence_trace=trace, spread_pattern=spread_pattern,
            confounders=confounders,
            notes="Bayesian log-odds: degree-days + insect pressure proxy",
        )

    def _infer_borers(self, ev_list, priors, spread_pattern, l3, wdp, stage, missing):
        """Borers — degree-day accumulation + structural anomaly."""
        tid = ThreatId.BORERS
        prior = priors.get(tid, 0.04)
        logit = _logit(prior)
        trace = list(ev_list)
        drivers = set()

        for ev in ev_list:
            logit += ev.weight * ev.logit_delta
            drivers.add(ev.driver)

        prob = _sigmoid(logit)
        conf, confounders = self._compute_confidence(l3, wdp, missing, has_lwd=False)
        conf *= 0.70  # Very difficult to diagnose from satellite alone

        return BioThreatState(
            threat_id=tid, threat_class=ThreatClass.INSECT,
            probability=round(prob, 4), confidence=round(max(0.10, conf), 4),
            severity=_severity_from_prob(prob, self._timing_crit(stage, ThreatClass.INSECT)),
            drivers_used=sorted(list(drivers), key=str),
            evidence_trace=trace, spread_pattern=spread_pattern,
            confounders=confounders,
            notes="Bayesian log-odds: degree-days + structural proxy",
        )

    def _infer_weed_pressure(self, ev_list, priors, spread_pattern, l3, wdp, stage, missing):
        """Weed Pressure — spatial heterogeneity + growth stall + L3 weed signal."""
        tid = ThreatId.WEED_PRESSURE
        prior = priors.get(tid, 0.07)
        logit = _logit(prior)
        trace = list(ev_list)
        drivers = set()

        for ev in ev_list:
            logit += ev.weight * ev.logit_delta
            drivers.add(ev.driver)

        # L3 weed corroboration: if L3 already detected weeds, amplify
        l3_weed = self._get_l3_prob(l3, "WEED_PRESSURE")
        if l3_weed > 0.3:
            delta = min(1.5, l3_weed * 2.0)
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, f"L3 weed corroboration (p={l3_weed:.2f})",
                delta, 1.0, {"l3_weed_prob": l3_weed}
            ))

        prob = _sigmoid(logit)
        conf, confounders = self._compute_confidence(l3, wdp, missing, has_lwd=False)

        return BioThreatState(
            threat_id=tid, threat_class=ThreatClass.WEED,
            probability=round(prob, 4), confidence=round(conf, 4),
            severity=_severity_from_prob(prob, self._timing_crit(stage, ThreatClass.WEED)),
            drivers_used=sorted(list(drivers), key=str),
            evidence_trace=trace, spread_pattern=spread_pattern,
            confounders=confounders,
            notes="Bayesian log-odds: heterogeneity + growth stall + L3 corroboration",
        )

    # ------------------------------------------------------------------
    # Confidence (Trust) Computation
    # ------------------------------------------------------------------

    def _compute_confidence(
        self,
        l3_decision: Any,
        wdp: Dict[str, Any],
        missing: List[str],
        has_lwd: bool = False,
    ) -> tuple:
        """Compute confidence (trust) from data quality.
        
        Confidence is SEPARATE from probability. It measures how much
        we trust the belief, not what the belief is.
        
        Returns (confidence, confounders_list).
        """
        conf = 1.0
        confounders = []

        # Missing core weather data
        if "L1_Rain" in missing:
            conf -= 0.30
        if "L1_Temp" in missing:
            conf -= 0.25
        if "L1_Soil" in missing:
            conf -= 0.10

        # LWD availability boosts confidence for disease threats
        if has_lwd:
            conf = min(1.0, conf + 0.05)

        # L3 water stress confounder
        l3_water = self._get_l3_prob(l3_decision, "WATER_STRESS")
        if l3_water > 0.4:
            conf -= 0.15
            confounders.append(Confounder.WATER_STRESS)

        # L3 mechanical damage → spectral noise
        l3_mech = self._get_l3_prob(l3_decision, "MECHANICAL_DAMAGE")
        if l3_mech > 0.4:
            conf -= 0.15
            confounders.append(Confounder.OTHER)

        # Salinity confounds spectral interpretation
        l3_salt = self._get_l3_prob(l3_decision, "SALINITY_RISK")
        if l3_salt > 0.3:
            conf -= 0.10
            confounders.append(Confounder.SALINITY_RISK)

        conf = max(0.10, conf)
        return conf, confounders

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_l3_prob(l3_decision: Any, problem_id: str) -> float:
        """Extract probability of an L3 diagnosis by problem_id."""
        if l3_decision and hasattr(l3_decision, "diagnoses"):
            for d in l3_decision.diagnoses:
                if hasattr(d, "problem_id") and d.problem_id == problem_id:
                    return getattr(d, "probability", 0.0)
        return 0.0

    @staticmethod
    def _timing_crit(stage: str, threat_class: ThreatClass) -> float:
        """Phenology-aware timing criticality multiplier.
        
        Amplifies severity during vulnerable growth stages.
        """
        from layer5_bio.knowledge.threats import get_phenology_multiplier
        return get_phenology_multiplier(stage, threat_class)


# ── Backward Compatibility ───────────────────────────────────────────────
# Legacy function signature for callers that haven't migrated yet

def infer_threat_states(
    evidence_by_threat: Dict[ThreatId, List[EvidenceLogit]],
    spread: Dict[str, Any],
    nutrient_output,
    plot_context: Dict[str, Any],
    confidence: float,
) -> Dict[str, BioThreatState]:
    """Legacy wrapper — delegates to BioThreatInferenceEngine.
    
    Preserved for backward compatibility with existing callers.
    New code should use BioThreatInferenceEngine.infer_states() directly.
    """
    engine = BioThreatInferenceEngine()
    return engine.infer_states(
        evidence_by_threat=evidence_by_threat,
        spread=spread,
        priors=THREAT_PRIORS,
    )
