"""
Layer 5 Remote Signature Engine — Evidence Generation for All 9 Threat Types

Consumes:
  - Plot timeseries (L1)
  - Vegetation intelligence (L2)
  - Weather pressure with LWD (WDP engine)
  - Spread signature (SSS engine)
  - Nutrient intelligence (L4)
  - L3 diagnoses (for confounder gating)

Produces:
  Dict[ThreatId, List[EvidenceLogit]] — per-threat evidence traces
"""

from typing import Dict, Any, List, Tuple, Optional
from layer5_bio.schema import EvidenceLogit, ThreatId, SpreadPattern, Confounder
from layer3_decision.schema import Driver, DegradationMode
from layer5_bio.knowledge.evidence_weights import EVIDENCE_WEIGHTS
from layer5_bio.knowledge.thresholds import (
    PRESSURE_THRESHOLD_HIGH, SPREAD_STRENGTH_STRONG, DROP_MAGNITUDE_SIGNIFICANT
)


def _last(ts: List[Dict[str, Any]], key: str, default=0.0) -> float:
    for r in reversed(ts):
        v = r.get(key)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    return float(default)


def _sum_last(ts: List[Dict[str, Any]], key: str, n: int) -> float:
    s = 0.0
    for r in ts[-n:]:
        v = r.get(key)
        if v is not None:
            try:
                s += float(v)
            except Exception:
                pass
    return s


def _get_weight(key: str) -> float:
    return EVIDENCE_WEIGHTS.get(key, 1.0)


def _get_l3_diagnosis_prob(l3_decision: Any, problem_id: str) -> float:
    """Extract probability of an L3 diagnosis by problem_id.
    
    Mirrors L4's confounder extraction pattern for consistency.
    """
    if l3_decision and hasattr(l3_decision, "diagnoses"):
        for d in l3_decision.diagnoses:
            if hasattr(d, "problem_id") and d.problem_id == problem_id:
                return getattr(d, "probability", 0.0)
    return 0.0


def build_remote_evidence(
    ts: List[Dict[str, Any]],
    veg_output,
    wdp: Dict[str, Any],
    spread: Dict[str, Any],
    nutrient_output,
    plot_context: Dict[str, Any],
    degradation_mode: DegradationMode,
    l3_decision: Any = None,
) -> Tuple[Dict[ThreatId, List[EvidenceLogit]], Dict[str, Any]]:
    """Build per-threat evidence from all available data sources.
    
    Returns:
        evidence_by_threat: Dict[ThreatId, List[EvidenceLogit]]
        features_snapshot: Dict[str, Any] for audit trail
    """
    pattern = spread["pattern"]
    spread_strength = float(spread["strength"])

    # ── Extract L2 anomalies ────────────────────────────────────────────
    anomalies = getattr(veg_output, "anomalies", []) or []
    recent_drop = False
    drop_mag = 0.0
    for a in anomalies[-5:]:
        t = getattr(a, "type", None) or (a.get("type") if isinstance(a, dict) else None)
        if t and "DROP" in str(t).upper():
            recent_drop = True
            mag = getattr(a, "magnitude", None)
            if mag is None and isinstance(a, dict):
                mag = a.get("magnitude", 0.0)
            drop_mag = max(drop_mag, float(mag or 0.0))

    # ── Extract L4 confounders ──────────────────────────────────────────
    l4_confounders = []
    try:
        ns_map = getattr(nutrient_output, "nutrient_states", {}) or {}
        for _, s in ns_map.items():
            for c in (getattr(s, "confounders", []) or []):
                l4_confounders.append(str(c))
    except Exception:
        pass

    # ── Extract L3 confounders ──────────────────────────────────────────
    l3_water_prob = _get_l3_diagnosis_prob(l3_decision, "WATER_STRESS") if l3_decision else 0.0
    l3_weed_prob = _get_l3_diagnosis_prob(l3_decision, "WEED_PRESSURE") if l3_decision else 0.0
    l3_mech_prob = _get_l3_diagnosis_prob(l3_decision, "MECHANICAL_DAMAGE") if l3_decision else 0.0

    rain14 = _sum_last(ts, "rain", 14)
    ndvi_now = _last(ts, "ndvi_smoothed", 0.0)

    feats = {
        "wdp": wdp,
        "spread": {
            "pattern": pattern.value if hasattr(pattern, "value") else str(pattern),
            "strength": spread_strength,
        },
        "rain_sum_14d": rain14,
        "ndvi_now": ndvi_now,
        "recent_drop": recent_drop,
        "drop_mag": drop_mag,
        "l4_confounders": l4_confounders,
        "l3_water_prob": l3_water_prob,
        "l3_weed_prob": l3_weed_prob,
        "l3_mech_prob": l3_mech_prob,
        "degradation_mode": degradation_mode.value,
    }

    # Initialize evidence for ALL non-SYSTEM threats
    evidence: Dict[ThreatId, List[EvidenceLogit]] = {
        t: [] for t in ThreatId if t != ThreatId.DATA_GAP
    }

    # ── Weather-derived evidence ────────────────────────────────────────
    wetness = float(wdp.get("leaf_wetness_lwd", wdp.get("leaf_wetness_proxy", 0.0)))
    fungal_p = float(wdp.get("fungal_pressure", 0.0))
    bact_p = float(wdp.get("bacterial_pressure", 0.0))
    insect_p = float(wdp.get("insect_pressure", 0.0))
    pm_p = float(wdp.get("powdery_mildew_pressure", 0.0))
    
    # LWD-specific evidence (New Science)
    lwd_mean = float(wdp.get("lwd_mean_hours", 0.0))
    lwd_consec = int(wdp.get("lwd_consecutive_wet_days", 0))
    lwd_available = bool(wdp.get("lwd_available", False))

    # ── FUNGAL LEAF SPOT ────────────────────────────────────────────────
    if fungal_p > PRESSURE_THRESHOLD_HIGH:
        w = _get_weight("fungal_pressure_high")
        evidence[ThreatId.FUNGAL_LEAF_SPOT].append(EvidenceLogit(
            driver=Driver.RAIN, condition="fungal_pressure_high",
            logit_delta=w, weight=1.0,
            source_refs={"fungal_pressure": fungal_p, "wetness": wetness}
        ))
    
    # LWD evidence for fungal leaf spot
    if lwd_available and lwd_mean > 8.0:
        w = _get_weight("lwd_extended")
        evidence[ThreatId.FUNGAL_LEAF_SPOT].append(EvidenceLogit(
            driver=Driver.RAIN, condition="lwd_extended",
            logit_delta=w, weight=1.0,
            source_refs={"lwd_mean_hours": lwd_mean, "lwd_consecutive_days": lwd_consec}
        ))
    elif lwd_available and lwd_mean > 4.0:
        w = _get_weight("lwd_moderate")
        evidence[ThreatId.FUNGAL_LEAF_SPOT].append(EvidenceLogit(
            driver=Driver.RAIN, condition="lwd_moderate",
            logit_delta=w, weight=1.0,
            source_refs={"lwd_mean_hours": lwd_mean}
        ))

    # ── FUNGAL RUST ─────────────────────────────────────────────────────
    if fungal_p > PRESSURE_THRESHOLD_HIGH:
        w = _get_weight("fungal_pressure_high") - 0.3
        evidence[ThreatId.FUNGAL_RUST].append(EvidenceLogit(
            driver=Driver.RAIN, condition="fungal_pressure_high",
            logit_delta=w, weight=1.0,
            source_refs={"fungal_pressure": fungal_p, "wetness": wetness}
        ))
    
    # LWD for rust (longer duration needed than leaf spot)
    if lwd_available and lwd_mean > 6.0 and lwd_consec >= 2:
        w = _get_weight("lwd_extended") * 0.9
        evidence[ThreatId.FUNGAL_RUST].append(EvidenceLogit(
            driver=Driver.RAIN, condition="lwd_extended_rust",
            logit_delta=w, weight=1.0,
            source_refs={"lwd_mean_hours": lwd_mean, "consecutive_wet_days": lwd_consec}
        ))

    # ── DOWNY MILDEW ───────────────────────────────────────────────────
    # Science: Oomycete; needs prolonged wetness + moderate temps (15-22°C)
    tmean = float(wdp.get("tmean_7d", 20.0))
    if wetness > 0.5 and 14.0 < tmean < 24.0:
        w = _get_weight("downy_mildew_wetness")
        evidence[ThreatId.DOWNY_MILDEW].append(EvidenceLogit(
            driver=Driver.RAIN, condition="downy_mildew_wetness",
            logit_delta=w, weight=1.0,
            source_refs={"wetness": wetness, "tmean": tmean}
        ))
    
    # LWD: downy mildew needs extended leaf wetness
    if lwd_available and lwd_mean > 6.0:
        w = _get_weight("lwd_extended") * 0.85
        evidence[ThreatId.DOWNY_MILDEW].append(EvidenceLogit(
            driver=Driver.RAIN, condition="lwd_downy_extended",
            logit_delta=w, weight=1.0,
            source_refs={"lwd_mean_hours": lwd_mean}
        ))

    # ── POWDERY MILDEW ──────────────────────────────────────────────────
    # Science: Prefers dry leaf surfaces + moderate humidity + temp oscillation
    if pm_p > 0.4:
        w = _get_weight("powdery_mildew_dry_oscillation")
        evidence[ThreatId.POWDERY_MILDEW].append(EvidenceLogit(
            driver=Driver.TEMP, condition="powdery_mildew_dry_oscillation",
            logit_delta=w, weight=1.0,
            source_refs={"powdery_mildew_pressure": pm_p}
        ))
    
    # Moderate humidity without rain
    rain_sum_7d = float(wdp.get("rain_sum_7d", 0.0))
    if rain_sum_7d < 5.0 and wetness < 0.3:
        w = _get_weight("powdery_mildew_humidity_moderate")
        evidence[ThreatId.POWDERY_MILDEW].append(EvidenceLogit(
            driver=Driver.RAIN, condition="dry_conditions_pm_favorable",
            logit_delta=w, weight=1.0,
            source_refs={"rain_sum_7d": rain_sum_7d, "wetness": wetness}
        ))

    # ── BACTERIAL BLIGHT ────────────────────────────────────────────────
    if bact_p > PRESSURE_THRESHOLD_HIGH:
        w = _get_weight("bacterial_pressure_high")
        evidence[ThreatId.BACTERIAL_BLIGHT].append(EvidenceLogit(
            driver=Driver.RAIN, condition="bacterial_pressure_high",
            logit_delta=w, weight=1.0,
            source_refs={"bacterial_pressure": bact_p}
        ))
    
    # LWD for bacteria (rain splash + prolonged wetness)
    if lwd_available and lwd_mean > 6.0 and rain_sum_7d > 15.0:
        w = _get_weight("lwd_moderate") * 0.9
        evidence[ThreatId.BACTERIAL_BLIGHT].append(EvidenceLogit(
            driver=Driver.RAIN, condition="lwd_bacterial_wet",
            logit_delta=w, weight=1.0,
            source_refs={"lwd_mean_hours": lwd_mean, "rain_sum_7d": rain_sum_7d}
        ))

    # ── CHEWING INSECTS ─────────────────────────────────────────────────
    if insect_p > PRESSURE_THRESHOLD_HIGH:
        w = _get_weight("insect_pressure_high")
        evidence[ThreatId.CHEWING_INSECTS].append(EvidenceLogit(
            driver=Driver.TEMP, condition="insect_pressure_high",
            logit_delta=w, weight=1.0,
            source_refs={"insect_pressure": insect_p}
        ))

    # ── SUCKING INSECTS ─────────────────────────────────────────────────
    if insect_p > PRESSURE_THRESHOLD_HIGH:
        w = _get_weight("insect_pressure_high") - 0.3
        evidence[ThreatId.SUCKING_INSECTS].append(EvidenceLogit(
            driver=Driver.TEMP, condition="insect_pressure_high",
            logit_delta=w, weight=1.0,
            source_refs={"insect_pressure": insect_p}
        ))

    # ── BORERS ──────────────────────────────────────────────────────────
    # Science: Borers driven by cumulative degree-days above base temp
    dd_proxy = float(wdp.get("insect_degree_proxy", 0.0))
    if dd_proxy > 0.5:
        w = _get_weight("borer_degree_day")
        evidence[ThreatId.BORERS].append(EvidenceLogit(
            driver=Driver.TEMP, condition="borer_degree_day_accumulation",
            logit_delta=w, weight=1.0,
            source_refs={"degree_day_proxy": dd_proxy}
        ))

    # ── WEED PRESSURE ───────────────────────────────────────────────────
    # Science: Weeds indicated by spatial heterogeneity + growth stall
    if pattern == SpreadPattern.PATCHY and spread_strength > 0.6:
        w = _get_weight("weed_heterogeneity")
        evidence[ThreatId.WEED_PRESSURE].append(EvidenceLogit(
            driver=Driver.NDVI, condition="weed_spatial_heterogeneity",
            logit_delta=w, weight=1.0,
            source_refs={"pattern": "PATCHY", "spread_strength": spread_strength}
        ))
    
    # Growth stall without clear abiotic cause
    growth_vel = _last(ts, "growth_velocity_7d", 0.01)
    if growth_vel < 0.005 and l3_water_prob < 0.3:
        w = _get_weight("weed_growth_stall")
        evidence[ThreatId.WEED_PRESSURE].append(EvidenceLogit(
            driver=Driver.NDVI, condition="weed_growth_stall",
            logit_delta=w, weight=1.0,
            source_refs={"growth_velocity": growth_vel, "l3_water_prob": l3_water_prob}
        ))

    # ── NDVI Drop + Patchy Pattern (multi-threat) ──────────────────────
    if recent_drop and pattern == SpreadPattern.PATCHY and drop_mag >= DROP_MAGNITUDE_SIGNIFICANT:
        w_drop = _get_weight("ndvi_drop_patchy")
        for t in [ThreatId.FUNGAL_LEAF_SPOT, ThreatId.FUNGAL_RUST,
                  ThreatId.CHEWING_INSECTS, ThreatId.SUCKING_INSECTS]:
            evidence[t].append(EvidenceLogit(
                driver=Driver.NDVI, condition="ndvi_drop_patchy",
                logit_delta=w_drop, weight=min(1.0, spread_strength),
                source_refs={"drop_mag": drop_mag, "pattern": "PATCHY"}
            ))

    # ── Spread Signature (biotic prior) ────────────────────────────────
    if pattern == SpreadPattern.PATCHY and spread_strength > SPREAD_STRENGTH_STRONG:
        w_spread = _get_weight("patchy_spread_signature")
        for t in [ThreatId.FUNGAL_LEAF_SPOT, ThreatId.FUNGAL_RUST,
                  ThreatId.BACTERIAL_BLIGHT, ThreatId.CHEWING_INSECTS,
                  ThreatId.SUCKING_INSECTS]:
            evidence[t].append(EvidenceLogit(
                driver=Driver.NDVI_UNC, condition="patchy_spread_signature",
                logit_delta=w_spread, weight=spread_strength,
                source_refs={"spread_strength": spread_strength}
            ))

    # ── L3 Structural Confounder Contra-Evidence ───────────────────────
    # Science: If L3 already explains the NDVI signal (water stress, weeds,
    # mechanical damage), then biotic threats are LESS likely.

    if l3_water_prob > 0.4:
        w = _get_weight("l3_water_stress_confounder")
        for t in evidence.keys():
            evidence[t].append(EvidenceLogit(
                driver=Driver.RAIN, condition="l3_water_stress_confounder",
                logit_delta=w, weight=1.0,
                source_refs={"l3_water_prob": l3_water_prob}
            ))

    if l3_mech_prob > 0.4:
        w = _get_weight("l3_mechanical_damage_confounder")
        for t in [ThreatId.FUNGAL_LEAF_SPOT, ThreatId.FUNGAL_RUST,
                  ThreatId.CHEWING_INSECTS, ThreatId.SUCKING_INSECTS]:
            evidence[t].append(EvidenceLogit(
                driver=Driver.NDVI, condition="l3_mechanical_damage_confounder",
                logit_delta=w, weight=1.0,
                source_refs={"l3_mech_prob": l3_mech_prob}
            ))

    # L3 weed already diagnosed → suppress L5 WEED_PRESSURE duplicate
    # (but keep it as corroborating evidence rather than pure suppression)
    if l3_weed_prob > 0.5:
        w = _get_weight("l3_weed_competition_confounder")
        # Reduce OTHER threats' probability (weed explains spectral signal)
        for t in [ThreatId.FUNGAL_LEAF_SPOT, ThreatId.CHEWING_INSECTS]:
            evidence[t].append(EvidenceLogit(
                driver=Driver.NDVI, condition="l3_weed_competition_confounder",
                logit_delta=w, weight=1.0,
                source_refs={"l3_weed_prob": l3_weed_prob}
            ))

    # ── Legacy L4 confounder contra-evidence ───────────────────────────
    uniform_like = (pattern == SpreadPattern.UNIFORM)
    if uniform_like:
        if any("WATER_STRESS" in c for c in l4_confounders):
            w = _get_weight("water_stress_uniform")
            for t in evidence.keys():
                evidence[t].append(EvidenceLogit(
                    driver=Driver.RAIN, condition="confounder_water_stress_uniform",
                    logit_delta=w, weight=1.0,
                    source_refs={"confounder": "WATER_STRESS", "pattern": "UNIFORM"}
                ))
        if any("N_DEF" in c for c in l4_confounders):
            w = _get_weight("n_def_uniform")
            for t in evidence.keys():
                evidence[t].append(EvidenceLogit(
                    driver=Driver.NDVI, condition="confounder_n_def_uniform",
                    logit_delta=w, weight=1.0,
                    source_refs={"confounder": "N_DEFICIENCY", "pattern": "UNIFORM"}
                ))

    return evidence, feats
