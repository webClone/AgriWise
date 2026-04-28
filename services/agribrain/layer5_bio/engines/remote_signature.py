
from typing import Dict, Any, List, Tuple
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
            except:
                pass
    return float(default)

def _sum_last(ts: List[Dict[str, Any]], key: str, n: int) -> float:
    s = 0.0
    c = 0
    for r in ts[-n:]:
        v = r.get(key)
        if v is not None:
            try:
                s += float(v)
                c += 1
            except:
                pass
    return s

def _get_weight(key: str) -> float:
    return EVIDENCE_WEIGHTS.get(key, 1.0)

def build_remote_evidence(
    ts: List[Dict[str, Any]],
    veg_output,
    wdp: Dict[str, Any],
    spread: Dict[str, Any],
    nutrient_output,
    plot_context: Dict[str, Any],
    degradation_mode: DegradationMode
) -> Tuple[Dict[ThreatId, List[EvidenceLogit]], Dict[str, Any]]:

    pattern = spread["pattern"]
    spread_strength = float(spread["strength"])

    # from L2 anomalies
    anomalies = getattr(veg_output, "anomalies", []) or []
    recent_drop = False
    drop_mag = 0.0
    for a in anomalies[-5:]:
        # adapt to your L2 schema fields
        t = getattr(a, "type", None) or (a.get("type") if isinstance(a, dict) else None)
        if t and "DROP" in str(t).upper():
            recent_drop = True
            mag = getattr(a, "magnitude", None)
            if mag is None and isinstance(a, dict): mag = a.get("magnitude", 0.0)
            drop_mag = max(drop_mag, float(mag or 0.0))

    # confounders from L4
    l4_confounders = []
    try:
        ns_map = getattr(nutrient_output, "nutrient_states", {}) or {}
        for _, s in ns_map.items():
            for c in (getattr(s, "confounders", []) or []):
                l4_confounders.append(str(c))
    except Exception:
        pass

    rain14 = _sum_last(ts, "rain", 14)
    # Use ndvi_smoothed from L1
    ndvi_now = _last(ts, "ndvi_smoothed", 0.0)

    feats = {
        "wdp": wdp,
        "spread": {"pattern": pattern.value if hasattr(pattern, "value") else str(pattern),
                   "strength": spread_strength},
        "rain_sum_14d": rain14,
        "ndvi_now": ndvi_now,
        "recent_drop": recent_drop,
        "drop_mag": drop_mag,
        "l4_confounders": l4_confounders,
        "degradation_mode": degradation_mode.value,
    }

    evidence: Dict[ThreatId, List[EvidenceLogit]] = {t: [] for t in ThreatId if t != ThreatId.DATA_GAP}

    # --- Evidence units ---
    wetness = float(wdp.get("leaf_wetness_proxy", 0.0))
    fungal_p = float(wdp.get("fungal_pressure", 0.0))
    bact_p = float(wdp.get("bacterial_pressure", 0.0))
    insect_p = float(wdp.get("insect_pressure", 0.0))

    # Fungal family
    if fungal_p > PRESSURE_THRESHOLD_HIGH:
        w_fung = _get_weight("fungal_pressure_high")
        evidence[ThreatId.FUNGAL_LEAF_SPOT].append(EvidenceLogit(
            driver=Driver.RAIN, condition="fungal_pressure_high", logit_delta=w_fung, weight=1.0,
            source_refs={"fungal_pressure": fungal_p, "wetness": wetness}
        ))
        evidence[ThreatId.FUNGAL_RUST].append(EvidenceLogit(
            driver=Driver.RAIN, condition="fungal_pressure_high", logit_delta=w_fung - 0.3, weight=1.0, # Rust slightly lower risk usually
            source_refs={"fungal_pressure": fungal_p, "wetness": wetness}
        ))

    # Bacterial
    if bact_p > PRESSURE_THRESHOLD_HIGH:
        w_bact = _get_weight("bacterial_pressure_high")
        evidence[ThreatId.BACTERIAL_BLIGHT].append(EvidenceLogit(
            driver=Driver.RAIN, condition="bacterial_pressure_high", logit_delta=w_bact, weight=1.0,
            source_refs={"bacterial_pressure": bact_p}
        ))

    # Insects
    if insect_p > PRESSURE_THRESHOLD_HIGH:
        w_ins = _get_weight("insect_pressure_high")
        evidence[ThreatId.CHEWING_INSECTS].append(EvidenceLogit(
            driver=Driver.TEMP, condition="insect_pressure_high", logit_delta=w_ins, weight=1.0,
            source_refs={"insect_pressure": insect_p}
        ))
        evidence[ThreatId.SUCKING_INSECTS].append(EvidenceLogit(
            driver=Driver.TEMP, condition="insect_pressure_high", logit_delta=w_ins - 0.3, weight=1.0,
            source_refs={"insect_pressure": insect_p}
        ))

    # Remote anomaly supports biotic only if patchy
    if recent_drop and (pattern == SpreadPattern.PATCHY) and drop_mag >= DROP_MAGNITUDE_SIGNIFICANT:
        w_drop = _get_weight("ndvi_drop_patchy")
        for t in [ThreatId.FUNGAL_LEAF_SPOT, ThreatId.FUNGAL_RUST, ThreatId.CHEWING_INSECTS, ThreatId.SUCKING_INSECTS]:
            evidence[t].append(EvidenceLogit(
                driver=Driver.NDVI, condition="ndvi_drop_patchy", logit_delta=w_drop, weight=min(1.0, spread_strength),
                source_refs={"drop_mag": drop_mag, "pattern": "PATCHY", "spread_strength": spread_strength}
            ))

    # Spread itself (biotic prior)
    if pattern == SpreadPattern.PATCHY and spread_strength > SPREAD_STRENGTH_STRONG:
        w_spread = _get_weight("patchy_spread_signature")
        for t in [ThreatId.FUNGAL_LEAF_SPOT, ThreatId.FUNGAL_RUST, ThreatId.BACTERIAL_BLIGHT,
                  ThreatId.CHEWING_INSECTS, ThreatId.SUCKING_INSECTS]:
            evidence[t].append(EvidenceLogit(
                driver=Driver.NDVI_UNC, condition="patchy_spread_signature", logit_delta=w_spread, weight=spread_strength,
                source_refs={"spread_strength": spread_strength}
            ))

    # --- Contra evidence from confounders ---
    uniform_like = (pattern == SpreadPattern.UNIFORM)
    if uniform_like:
        if any("WATER_STRESS" in c for c in l4_confounders):
            w_water = _get_weight("water_stress_uniform")
            for t in evidence.keys():
                evidence[t].append(EvidenceLogit(
                    driver=Driver.RAIN, condition="confounder_water_stress_uniform", logit_delta=w_water, weight=1.0,
                    source_refs={"confounder": "WATER_STRESS", "pattern": "UNIFORM"}
                ))
        if any("N_DEF" in c for c in l4_confounders):
            w_ndef = _get_weight("n_def_uniform")
            for t in evidence.keys():
                evidence[t].append(EvidenceLogit(
                    driver=Driver.NDVI, condition="confounder_n_def_uniform", logit_delta=w_ndef, weight=1.0,
                    source_refs={"confounder": "N_DEFICIENCY", "pattern": "UNIFORM"}
                ))

    return evidence, feats
