"""
Engine 1: Intervention Synthesis — Cross-Layer Intelligence Fusion

Consumes L1-L5 upstream intelligence and produces a ranked portfolio of
intervention candidates with full evidence trace for farmer explainability.

Science:
  - Harvests L3 diagnoses, L4 nutrient prescriptions, L5 bio-threat plans
  - Detects cross-layer conflicts (e.g. irrigate vs. fungal risk)
  - Scores: utility = (impact × urgency × confidence) / (1 + normalized_cost)
  - Applies dominance pruning: if A subsumes B, drop B

References:
  - FAO IPM Decision Framework
  - Multi-criteria decision analysis (MCDA) for farm interventions
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from layer6_exec.schema import (
    InterventionCandidate, InterventionDomain, ConflictRecord,
    ConflictType, ConflictResolutionStrategy, UpstreamDigest,
)
from layer6_exec.knowledge.intervention_catalog import (
    INTERVENTION_TEMPLATES, COST_OF_INACTION, CONFLICT_RULES,
    get_timing_urgency,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _window(days: int = 5) -> Dict[str, str]:
    s = datetime.now(timezone.utc).date()
    e = s + timedelta(days=days)
    return {"start": s.isoformat(), "end": e.isoformat()}


def _inv_id(domain: str, source: str, target: str) -> str:
    raw = f"{domain}|{source}|{target}|{_iso_now()}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:10]
    return f"INV-{h}"


# ============================================================================
# Upstream Digest Builder
# ============================================================================

def build_upstream_digest(
    tensor: Any, veg_int: Any, decision_l3: Any,
    nutrient_l4: Any, bio_l5: Any,
) -> UpstreamDigest:
    """Extract maximum intelligence from each layer for explainability."""
    d = UpstreamDigest()
    confidences = []

    # ── L1: Environmental ────────────────────────────────────────────────
    if tensor:
        ts = getattr(tensor, "plot_timeseries", []) or []
        recent = ts[-7:] if len(ts) >= 7 else ts
        if recent:
            rain_vals = [float(r.get("rain", 0) or r.get("precipitation", 0) or 0)
                         for r in recent if isinstance(r, dict)]
            d.rain_7d_mm = sum(rain_vals)
            tmeans = [float(r.get("tmean", 20)) for r in recent
                      if isinstance(r, dict) and r.get("tmean") is not None]
            d.tmean_7d_c = sum(tmeans) / max(len(tmeans), 1)
            d.heat_days = sum(1 for r in recent if isinstance(r, dict)
                              and (r.get("temp_max") or 0) > 35)
            d.frost_risk = any(isinstance(r, dict) and (r.get("temp_min") or 99) < 2
                               for r in recent)
            # Soil moisture
            sm = (getattr(tensor, "static", {}) or {}).get("soil_moisture")
            if isinstance(sm, dict):
                vals = [v for v in sm.values() if isinstance(v, (int, float))]
                avg = sum(vals) / max(len(vals), 1) if vals else 0.3
                if avg < 0.15:
                    d.soil_moisture_status = "DRY"
                elif avg > 0.40:
                    d.soil_moisture_status = "SATURATED"
                elif avg > 0.30:
                    d.soil_moisture_status = "WET"

    # ── L2: Vegetation ───────────────────────────────────────────────────
    if veg_int:
        # VegIntOutput has: curve (ModeledCurveOutput), phenology, anomalies, stability
        # NOT: indices.timeseries (that attribute doesn't exist)
        curve = getattr(veg_int, "curve", None)
        if curve:
            ndvi_fit = getattr(curve, "ndvi_fit", []) or []
            ndvi_fit_d1 = getattr(curve, "ndvi_fit_d1", []) or []
            if ndvi_fit:
                d.ndvi_current = float(ndvi_fit[-1])

                # Compute trend from last 5 values of the fitted curve
                if len(ndvi_fit) >= 5:
                    recent_5 = ndvi_fit[-5:]
                    slope = (recent_5[-1] - recent_5[0]) / max(len(recent_5) - 1, 1)
                    d.growth_velocity = slope
                    if slope > 0.005:
                        d.ndvi_trend = "RISING"
                    elif slope < -0.01:
                        d.ndvi_trend = "CRASH"
                    elif slope < -0.003:
                        d.ndvi_trend = "DECLINING"

            # Growth velocity from derivative (more precise than slope)
            if ndvi_fit_d1:
                d.growth_velocity = float(ndvi_fit_d1[-1])

            # Canopy cover proxy from NDVI
            if d.ndvi_current > 0:
                d.canopy_cover_pct = min(100.0, d.ndvi_current * 120.0)

        phenology = getattr(veg_int, "phenology", None)
        if phenology:
            sbd = getattr(phenology, "stage_by_day", []) or []
            if sbd:
                last_stage = sbd[-1]
                if hasattr(last_stage, "value"):
                    d.phenology_stage = last_stage.value
                elif isinstance(last_stage, str):
                    d.phenology_stage = last_stage.upper()
        confidences.append(0.7)

    # ── L3: Decision Diagnoses ───────────────────────────────────────────
    if decision_l3:
        diags = getattr(decision_l3, "diagnoses", []) or []
        for diag in diags[:3]:
            entry = {
                "problem_id": getattr(diag, "problem_id", "UNKNOWN"),
                "probability": getattr(diag, "probability", 0.0),
                "severity": getattr(diag, "severity", 0.0),
                "confidence": getattr(diag, "confidence", 0.0),
            }
            d.active_diagnoses.append(entry)
            confidences.append(entry["confidence"])

    # ── L4: Nutrient State ───────────────────────────────────────────────
    if nutrient_l4:
        ns = getattr(nutrient_l4, "nutrient_states", {}) or {}
        for key, state in ns.items():
            k = key.value if hasattr(key, "value") else str(key)
            prob = getattr(state, "probability_deficient", 0.0)
            if prob > 0.3:
                d.nutrient_deficiencies.append({
                    "nutrient": k,
                    "probability_deficient": prob,
                    "severity": getattr(state, "severity", "LOW"),
                    "confidence": getattr(state, "confidence", 0.5),
                })
                confidences.append(getattr(state, "confidence", 0.5))
        swb = getattr(nutrient_l4, "water_balance", None)
        if swb:
            deficit = getattr(swb, "deficit_mm", 0.0)
            if deficit > 20:
                d.water_balance_status = "DEFICIT"
            elif deficit < -10:
                d.water_balance_status = "SURPLUS"

    # ── L5: BioThreat State ──────────────────────────────────────────────
    if bio_l5:
        ts_map = getattr(bio_l5, "threat_states", {}) or {}
        for key, state in ts_map.items():
            k = key.value if hasattr(key, "value") else str(key)
            prob = getattr(state, "probability", 0.0)
            if prob > 0.2:
                tc = getattr(state, "threat_class", None)
                tc_val = tc.value if hasattr(tc, "value") else str(tc) if tc else ""
                d.active_threats.append({
                    "threat_id": k,
                    "probability": prob,
                    "confidence": getattr(state, "confidence", 0.5),
                    "severity": getattr(getattr(state, "severity", "LOW"), "value",
                                        getattr(state, "severity", "LOW")),
                    "threat_class": tc_val,
                })
                confidences.append(getattr(state, "confidence", 0.5))
                if "FUNGAL" in k.upper():
                    d.fungal_pressure = max(d.fungal_pressure, prob)
                elif "INSECT" in k.upper() or "BORER" in k.upper():
                    d.insect_pressure = max(d.insect_pressure, prob)
        lwd = getattr(bio_l5, "leaf_wetness_hours", None)
        if lwd is not None:
            d.leaf_wetness_hours = float(lwd)

    d.min_upstream_confidence = min(confidences) if confidences else 0.5
    return d


# ============================================================================
# Intervention Harvesting
# ============================================================================

def _harvest_l3_interventions(
    digest: UpstreamDigest, stage: str,
) -> List[InterventionCandidate]:
    """Convert L3 diagnoses into intervention candidates."""
    candidates = []
    stage_urgency = get_timing_urgency(stage)

    for diag in digest.active_diagnoses:
        pid = diag["problem_id"]
        prob = diag.get("probability", 0.0)
        sev = diag.get("severity", 0.0)
        conf = diag.get("confidence", 0.5)
        if prob < 0.4:
            continue

        # Map problem to template
        template_key = None
        if "WATER_STRESS" in pid.upper():
            template_key = "IRR_DEFICIT_CORRECTION"
        elif "WATERLOGGING" in pid.upper():
            template_key = "MON_FIELD_SCOUT"  # Can't fix waterlogging, scout instead
        elif "LODGING" in pid.upper():
            template_key = "MON_FIELD_SCOUT"
        elif "HEAT" in pid.upper():
            template_key = "IRR_STRESS_PREVENTION"

        if not template_key or template_key not in INTERVENTION_TEMPLATES:
            template_key = "MON_FIELD_SCOUT"

        tmpl = INTERVENTION_TEMPLATES[template_key]
        cost = tmpl["cost_per_ha_eur"]
        impact = tmpl["expected_impact"] * float(sev if isinstance(sev, (int, float)) else 0.5)
        urgency = min(1.0, stage_urgency * prob)
        utility = (impact * urgency * conf) / (1.0 + cost / 100.0)

        coi = COST_OF_INACTION.get(pid.upper(), {})
        coi_eur = coi.get("eur_per_ha", 0.0) * prob

        candidates.append(InterventionCandidate(
            intervention_id=_inv_id(tmpl["domain"].value, "L3", pid),
            domain=tmpl["domain"],
            action_type="INTERVENE" if "IRR_" in template_key else "MONITOR",
            title=tmpl["title"],
            instructions=tmpl["instructions"],
            utility_score=round(utility, 4),
            expected_impact=round(impact, 3),
            urgency=round(urgency, 3),
            confidence=round(conf, 3),
            estimated_cost_eur=cost,
            estimated_roi=round(coi_eur / max(cost, 1.0), 2),
            cost_of_inaction_eur=round(coi_eur, 2),
            timing_window=_window(tmpl["timing_urgency_days"]),
            source_layer="L3",
            linked_diagnosis_ids=[pid],
            evidence_summary=f"L3 diagnosis: {pid} (p={prob:.0%}, severity={sev})",
            resource_requirements=[{
                "resource_type": tmpl["resource_type"].value,
                "quantity": tmpl["resource_qty_per_ha"],
                "unit": tmpl["resource_unit"],
            }],
        ))
    return candidates


def _harvest_l4_interventions(
    digest: UpstreamDigest, stage: str,
) -> List[InterventionCandidate]:
    """Convert L4 nutrient deficiencies into intervention candidates."""
    candidates = []
    stage_urgency = get_timing_urgency(stage)

    for nd in digest.nutrient_deficiencies:
        nutrient = nd["nutrient"]
        prob = nd.get("probability_deficient", 0.0)
        conf = nd.get("confidence", 0.5)
        if prob < 0.4:
            continue

        template_key = "NUT_N_TOPDRESS" if nutrient.upper() == "N" else "NUT_PK_CORRECTION"
        if template_key not in INTERVENTION_TEMPLATES:
            continue
        tmpl = INTERVENTION_TEMPLATES[template_key]
        cost = tmpl["cost_per_ha_eur"]
        impact = tmpl["expected_impact"] * prob
        urgency = min(1.0, stage_urgency * prob)
        utility = (impact * urgency * conf) / (1.0 + cost / 100.0)

        coi_key = f"{nutrient.upper()}_DEFICIENCY" if len(nutrient) <= 2 else nutrient.upper()
        coi = COST_OF_INACTION.get(coi_key, COST_OF_INACTION.get(f"{nutrient.upper()}_DEFICIENCY", {}))
        coi_eur = coi.get("eur_per_ha", 0.0) * prob

        candidates.append(InterventionCandidate(
            intervention_id=_inv_id("NUTRIENT", "L4", nutrient),
            domain=InterventionDomain.NUTRIENT,
            action_type="INTERVENE",
            title=tmpl["title"],
            instructions=tmpl["instructions"],
            utility_score=round(utility, 4),
            expected_impact=round(impact, 3),
            urgency=round(urgency, 3),
            confidence=round(conf, 3),
            estimated_cost_eur=cost,
            estimated_roi=round(coi_eur / max(cost, 1.0), 2),
            cost_of_inaction_eur=round(coi_eur, 2),
            timing_window=_window(tmpl["timing_urgency_days"]),
            source_layer="L4",
            evidence_summary=f"L4 nutrient deficiency: {nutrient} (p={prob:.0%})",
            resource_requirements=[{
                "resource_type": tmpl["resource_type"].value,
                "quantity": tmpl["resource_qty_per_ha"],
                "unit": tmpl["resource_unit"],
            }],
        ))
    return candidates


def _harvest_l5_interventions(
    digest: UpstreamDigest, stage: str,
) -> List[InterventionCandidate]:
    """Convert L5 bio-threats into intervention candidates."""
    candidates = []
    stage_urgency = get_timing_urgency(stage)

    for threat in digest.active_threats:
        tid = threat["threat_id"]
        prob = threat.get("probability", 0.0)
        conf = threat.get("confidence", 0.5)
        tc = threat.get("threat_class", "").upper()
        if prob < 0.4:
            continue

        # Always add scout first
        scout_tmpl = INTERVENTION_TEMPLATES["MON_FIELD_SCOUT"]
        scout_id = _inv_id("MONITORING", "L5", f"SCOUT_{tid}")
        candidates.append(InterventionCandidate(
            intervention_id=scout_id,
            domain=InterventionDomain.MONITORING,
            action_type="VERIFY",
            title=f"Scout for {tid}",
            instructions=scout_tmpl["instructions"],
            utility_score=round(0.3 * conf, 4),
            expected_impact=0.2, urgency=round(min(1.0, stage_urgency * 0.8), 3),
            confidence=round(conf, 3),
            estimated_cost_eur=scout_tmpl["cost_per_ha_eur"],
            timing_window=_window(3),
            source_layer="L5", linked_threat_ids=[tid],
            evidence_summary=f"L5 threat: {tid} (p={prob:.0%}). Scout to confirm.",
        ))

        # If high confidence + probability → treatment candidate
        if prob >= 0.55 and conf >= 0.6:
            if "FUNGAL" in tid.upper() or "MILDEW" in tid.upper() or "RUST" in tid.upper():
                tkey = "PHYTO_FUNGICIDE_CLASS"
            elif "INSECT" in tid.upper() or "BORER" in tid.upper():
                tkey = "PHYTO_INSECTICIDE_CLASS"
            elif "WEED" in tid.upper():
                tkey = "PHYTO_HERBICIDE_CLASS"
            else:
                tkey = "MON_FIELD_SCOUT"

            if tkey in INTERVENTION_TEMPLATES:
                tmpl = INTERVENTION_TEMPLATES[tkey]
                cost = tmpl["cost_per_ha_eur"]
                impact = tmpl["expected_impact"] * prob
                urgency = min(1.0, stage_urgency * prob)
                utility = (impact * urgency * conf) / (1.0 + cost / 100.0)
                coi = COST_OF_INACTION.get(tid.upper(), {})
                coi_eur = coi.get("eur_per_ha", 0.0) * prob

                treat_id = _inv_id(tmpl["domain"].value, "L5", tid)
                candidates.append(InterventionCandidate(
                    intervention_id=treat_id,
                    domain=tmpl["domain"],
                    action_type="INTERVENE",
                    title=tmpl["title"],
                    instructions=tmpl["instructions"],
                    utility_score=round(utility, 4),
                    expected_impact=round(impact, 3),
                    urgency=round(urgency, 3),
                    confidence=round(conf, 3),
                    estimated_cost_eur=cost,
                    estimated_roi=round(coi_eur / max(cost, 1.0), 2),
                    cost_of_inaction_eur=round(coi_eur, 2),
                    timing_window=_window(tmpl["timing_urgency_days"]),
                    source_layer="L5", linked_threat_ids=[tid],
                    evidence_summary=f"L5 high-confidence threat: {tid} (p={prob:.0%}, c={conf:.0%})",
                    depends_on=[scout_id],
                    resource_requirements=[{
                        "resource_type": tmpl["resource_type"].value,
                        "quantity": tmpl["resource_qty_per_ha"],
                        "unit": tmpl["resource_unit"],
                    }],
                ))
    return candidates


# ============================================================================
# Conflict Detection
# ============================================================================

def detect_conflicts(
    candidates: List[InterventionCandidate],
    digest: UpstreamDigest,
) -> List[ConflictRecord]:
    """Detect cross-layer recommendation conflicts using knowledge rules."""
    conflicts = []

    # Check irrigation vs fungal
    irr_cands = [c for c in candidates if c.domain == InterventionDomain.IRRIGATION]
    fungal_threats = [t for t in digest.active_threats if "FUNGAL" in t.get("threat_id", "").upper()
                      or "MILDEW" in t.get("threat_id", "").upper()]

    if irr_cands and fungal_threats:
        top_fungal = max(fungal_threats, key=lambda t: t.get("probability", 0))
        if top_fungal.get("probability", 0) >= 0.5:
            conflicts.append(ConflictRecord(
                conflict_id=f"CONF-IRR-FUNG-{_iso_now()[:10]}",
                conflict_type=ConflictType.IRRIGATION_VS_FUNGAL,
                description=(
                    f"L3 recommends irrigation but L5 detects high fungal risk "
                    f"({top_fungal['threat_id']}, p={top_fungal['probability']:.0%}). "
                    f"Overhead irrigation may worsen leaf wetness conditions."
                ),
                source_a={"layer": "L3", "action": "IRRIGATE",
                           "confidence": irr_cands[0].confidence},
                source_b={"layer": "L5", "threat": top_fungal["threat_id"],
                           "confidence": top_fungal.get("confidence", 0.5)},
                resolution=ConflictResolutionStrategy.PRIORITIZE_SAFETY,
                resolution_rationale="High fungal risk: prefer drip irrigation or delay.",
                winning_source="L5",
            ))

    # Check N application vs lodging
    n_cands = [c for c in candidates if c.domain == InterventionDomain.NUTRIENT
               and "nitrogen" in c.title.lower()]
    lodging_diags = [d for d in digest.active_diagnoses if "LODGING" in d.get("problem_id", "").upper()]
    if n_cands and lodging_diags:
        top_lodging = max(lodging_diags, key=lambda d: d.get("probability", 0))
        if top_lodging.get("probability", 0) >= 0.4:
            conflicts.append(ConflictRecord(
                conflict_id=f"CONF-N-LODGE-{_iso_now()[:10]}",
                conflict_type=ConflictType.NITROGEN_VS_LODGING,
                description=(
                    f"L4 recommends nitrogen but L3 flags lodging risk "
                    f"(p={top_lodging['probability']:.0%}). Extra N may worsen lodging."
                ),
                source_a={"layer": "L4", "action": "APPLY_N",
                           "confidence": n_cands[0].confidence},
                source_b={"layer": "L3", "diagnosis": "LODGING_RISK",
                           "confidence": top_lodging.get("confidence", 0.5)},
                resolution=ConflictResolutionStrategy.COMPROMISE,
                resolution_rationale="Reduce N rate by 25% and consider growth regulator.",
                winning_source="BOTH",
            ))

    return conflicts


def apply_conflict_resolutions(
    candidates: List[InterventionCandidate],
    conflicts: List[ConflictRecord],
) -> List[InterventionCandidate]:
    """Apply conflict resolutions by adjusting intervention scores."""
    for conflict in conflicts:
        if conflict.resolution == ConflictResolutionStrategy.PRIORITIZE_SAFETY:
            # Penalize the unsafe recommendation
            if conflict.conflict_type == ConflictType.IRRIGATION_VS_FUNGAL:
                for c in candidates:
                    if c.domain == InterventionDomain.IRRIGATION:
                        c.utility_score *= 0.3
                        c.blocked_reasons.append(f"Penalized: {conflict.description}")
        elif conflict.resolution == ConflictResolutionStrategy.COMPROMISE:
            if conflict.conflict_type == ConflictType.NITROGEN_VS_LODGING:
                for c in candidates:
                    if c.domain == InterventionDomain.NUTRIENT and "nitrogen" in c.title.lower():
                        c.utility_score *= 0.7
                        c.instructions += " [REDUCED RATE: -25% due to lodging risk]"
    return candidates


# ============================================================================
# Dominance Pruning + Ranking
# ============================================================================

def _prune_and_rank(candidates: List[InterventionCandidate]) -> List[InterventionCandidate]:
    """Remove dominated candidates and rank by utility."""
    if not candidates:
        return []

    # Group by (domain, target)
    groups: Dict[str, List[InterventionCandidate]] = {}
    for c in candidates:
        key = f"{c.domain.value}|{'|'.join(sorted(c.linked_diagnosis_ids + c.linked_threat_ids))}"
        groups.setdefault(key, []).append(c)

    pruned = []
    for group in groups.values():
        # Keep the highest-utility candidate per group, plus all VERIFY types
        verifies = [c for c in group if c.action_type == "VERIFY"]
        intervenes = sorted([c for c in group if c.action_type != "VERIFY"],
                            key=lambda x: x.utility_score, reverse=True)
        pruned.extend(verifies)
        if intervenes:
            pruned.append(intervenes[0])

    return sorted(pruned, key=lambda x: x.utility_score, reverse=True)


# ============================================================================
# Main Entry Point
# ============================================================================

def synthesize_interventions(
    digest: UpstreamDigest,
) -> Tuple[List[InterventionCandidate], List[ConflictRecord]]:
    """Main synthesis pipeline: harvest → conflict detect → resolve → prune → rank."""
    stage = digest.phenology_stage

    # 1. Harvest from all layers
    l3_cands = _harvest_l3_interventions(digest, stage)
    l4_cands = _harvest_l4_interventions(digest, stage)
    l5_cands = _harvest_l5_interventions(digest, stage)
    all_cands = l3_cands + l4_cands + l5_cands

    # 2. Always add a baseline scout if no interventions generated
    if not all_cands:
        tmpl = INTERVENTION_TEMPLATES["MON_FIELD_SCOUT"]
        all_cands.append(InterventionCandidate(
            intervention_id=_inv_id("MONITORING", "L6", "BASELINE"),
            domain=InterventionDomain.MONITORING,
            action_type="MONITOR",
            title="Routine Field Scouting",
            instructions=tmpl["instructions"],
            utility_score=0.1, expected_impact=0.1,
            urgency=0.3, confidence=0.9,
            estimated_cost_eur=tmpl["cost_per_ha_eur"],
            timing_window=_window(7),
            source_layer="L6",
            evidence_summary="No urgent issues detected. Routine monitoring recommended.",
        ))

    # 3. Detect conflicts
    conflicts = detect_conflicts(all_cands, digest)

    # 4. Apply resolutions
    all_cands = apply_conflict_resolutions(all_cands, conflicts)

    # 5. Prune and rank
    portfolio = _prune_and_rank(all_cands)

    return portfolio, conflicts
