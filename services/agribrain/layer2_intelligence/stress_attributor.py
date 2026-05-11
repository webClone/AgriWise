"""
Layer 2 Intelligence — Stress Attributor.

Multi-factor stress attribution engine. Replaces legacy stress_detector.py.
Produces evidence-based StressEvidence items — never prescriptions.

Attribution rules:
  WATER:    low NDMI + low soil_moisture + corroborating VPD/precip
  NUTRIENT: declining NDVI but adequate NDMI (no water deficit)
  THERMAL:  high temp_max + high VPD exceeding crop tolerance
  BIOTIC:   patchy NDVI decline not explained by abiotic factors
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .schemas import (
    DataHealthScore,
    EvidenceConflict,
    StressEvidence,
    STRESS_TYPES,
)


def attribute_stress(
    water_features: Dict[str, Any],
    vegetation_features: Dict[str, Any],
    environment_features: Dict[str, Any],
    operational_features: Dict[str, Any],
    soil_site_features: Dict[str, Any],
    conflicts: List[EvidenceConflict],
    data_health: DataHealthScore,
    plot_id: str = "",
    run_id: str = "",
    spatial_scope: str = "plot",
    scope_id: Optional[str] = None,
) -> List[StressEvidence]:
    """Run multi-factor stress attribution.

    Returns a list of StressEvidence items with attribution chains.
    """
    stress_items: List[StressEvidence] = []

    # Extract feature values safely
    ndmi = _fv(water_features, "ndmi_mean", "ndmi")
    soil_moisture = _fv(water_features, "soil_moisture_vwc", "soil_moisture")
    ndvi = _fv(vegetation_features, "ndvi_mean", "ndvi")
    evi = _fv(vegetation_features, "evi_mean", "evi")
    veg_fraction = _fv(vegetation_features, "vegetation_fraction_scl")
    precip = _fv(operational_features, "precipitation_mm", "precip_recent")
    temp_max = _fv(environment_features, "temp_max", "temperature_max")
    vpd = _fv(environment_features, "vpd", "vapor_pressure_deficit")
    et0 = _fv(environment_features, "et0_mm", "et0")
    sif = _fv(vegetation_features, "sif", "sif_mean")
    pri = _fv(vegetation_features, "pri", "pri_mean")
    anomaly_score = _fv(vegetation_features, "anomaly_score")

    # Confidence ceiling from data health
    conf_ceiling = min(1.0, data_health.confidence_ceiling or 1.0)
    base_uncertainty = max(0.05, 1.0 - data_health.overall) * 0.5

    # Conflict penalty: increase uncertainty when sources disagree
    conflict_penalty = 0.0
    for c in conflicts:
        if c.severity == "major":
            conflict_penalty += 0.15
        elif c.severity == "moderate":
            conflict_penalty += 0.08

    # -- Water stress --
    water_stress = _assess_water_stress(
        ndmi, soil_moisture, precip, vpd, et0,
        conf_ceiling, base_uncertainty, conflict_penalty,
        water_features, plot_id, run_id, spatial_scope, scope_id,
        canopy_cover=_fv(vegetation_features, "canopy_cover_fraction"),
        bare_soil=_fv(vegetation_features, "bare_soil_fraction"),
    )
    if water_stress:
        stress_items.append(water_stress)

    # -- Nutrient stress --
    nutrient_stress = _assess_nutrient_stress(
        ndvi, evi, ndmi, soil_moisture,
        conf_ceiling, base_uncertainty, conflict_penalty,
        vegetation_features, water_features,
        plot_id, run_id, spatial_scope, scope_id,
        has_water_stress=(water_stress is not None),
        canopy_uniformity_cv=_fv(vegetation_features, "canopy_uniformity_cv"),
    )
    if nutrient_stress:
        stress_items.append(nutrient_stress)

    # -- Thermal stress --
    thermal_stress = _assess_thermal_stress(
        temp_max, vpd, ndvi,
        conf_ceiling, base_uncertainty, conflict_penalty,
        environment_features, vegetation_features,
        plot_id, run_id, spatial_scope, scope_id,
    )
    if thermal_stress:
        stress_items.append(thermal_stress)

    # -- Photosynthetic shutdown (SIF/PRI early warning) --
    photo_shutdown = _assess_photosynthetic_shutdown(
        sif, pri, ndvi, evi, temp_max, vpd,
        conf_ceiling, base_uncertainty, conflict_penalty,
        vegetation_features, environment_features,
        plot_id, run_id, spatial_scope, scope_id,
        has_water_stress=(water_stress is not None),
        has_thermal_stress=(thermal_stress is not None),
    )
    if photo_shutdown:
        stress_items.append(photo_shutdown)

    # -- Biotic stress (inferred when vegetation drops without abiotic cause) --
    biotic_stress = _assess_biotic_stress(
        ndvi, evi, veg_fraction,
        conf_ceiling, base_uncertainty, conflict_penalty,
        vegetation_features,
        plot_id, run_id, spatial_scope, scope_id,
        has_water_stress=(water_stress is not None),
        has_thermal_stress=(thermal_stress is not None),
        weed_pressure=_fv(vegetation_features, "weed_pressure_index"),
        in_row_weed=_fv(vegetation_features, "in_row_weed_fraction"),
        inter_row_weed=_fv(vegetation_features, "inter_row_weed_fraction"),
    )
    if biotic_stress:
        stress_items.append(biotic_stress)

    # -- Mechanical stress (drone structural damage detection) --
    mechanical_stress = _assess_mechanical_stress(
        row_continuity=_fv(operational_features, "row_continuity_mean"),
        row_break_count=_fv(operational_features, "row_break_count"),
        canopy_cover=_fv(vegetation_features, "canopy_cover_fraction"),
        ndvi=ndvi,
        conf_ceiling=conf_ceiling,
        base_unc=base_uncertainty,
        conflict_penalty=conflict_penalty,
        operational_features=operational_features,
        vegetation_features=vegetation_features,
        plot_id=plot_id,
        run_id=run_id,
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        has_water_stress=(water_stress is not None),
        has_thermal_stress=(thermal_stress is not None),
    )
    if mechanical_stress:
        stress_items.append(mechanical_stress)

    # -- EO Foundation Model anomaly corroboration --
    if anomaly_score is not None:
        _apply_eo_anomaly_corroboration(
            anomaly_score, stress_items, vegetation_features,
            conf_ceiling, base_uncertainty, conflict_penalty,
            plot_id, run_id, spatial_scope, scope_id,
        )

    return stress_items


# ── Private helpers ──────────────────────────────────────────────────────────

def _fv(features: Dict[str, Any], *keys: str) -> Optional[float]:
    """Extract feature value by trying multiple key names, filtering NaNs."""
    import math
    for k in keys:
        entry = features.get(k)
        if entry is not None:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val is not None and not (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                return val
    return None


def _collect_evidence_ids(features: Dict[str, Any], *keys: str) -> List[str]:
    """Collect source_evidence_ids from feature dicts."""
    ids = []
    for k in keys:
        entry = features.get(k)
        if isinstance(entry, dict):
            for eid in entry.get("source_weights", {}).keys():
                if eid not in ids:
                    ids.append(eid)
    return ids


def _is_diagnostic(features: Dict[str, Any], key: str) -> bool:
    """Check if a feature is diagnostic-only."""
    entry = features.get(key)
    if isinstance(entry, dict):
        return entry.get("diagnostic_only", False)
    return False


def _assess_water_stress(
    ndmi, soil_moisture, precip, vpd, et0,
    conf_ceiling, base_unc, conflict_penalty,
    water_features, plot_id, run_id, spatial_scope, scope_id,
    canopy_cover=None, bare_soil=None,
) -> Optional[StressEvidence]:
    """Low NDMI + low soil moisture + corroborating weather = water stress."""
    if ndmi is None and soil_moisture is None:
        return None

    severity = 0.0
    evidence_chain = []
    evidence_ids = _collect_evidence_ids(water_features, "ndmi_mean", "ndmi", "soil_moisture_vwc", "soil_moisture")

    # NDMI check
    if ndmi is not None and ndmi < 0.2:
        severity += 0.3 + max(0.0, (0.2 - ndmi) * 2.0)
        evidence_chain.append(
            f"NDMI={ndmi:.2f} indicates reduced plant water content"
        )

    # Soil moisture check
    if soil_moisture is not None and soil_moisture < 0.2:
        severity += 0.2 + max(0.0, (0.2 - soil_moisture) * 1.5)
        evidence_chain.append(
            f"Soil moisture={soil_moisture:.2f} consistent with water deficit"
        )

    # Corroborating: low precipitation
    if precip is not None and precip < 5.0:
        severity += 0.1
        evidence_chain.append(
            f"Recent precipitation={precip:.1f}mm corroborates dry conditions"
        )

    # Corroborating: high VPD
    if vpd is not None and vpd > 2.0:
        severity += 0.1
        evidence_chain.append(
            f"VPD={vpd:.1f}kPa indicates high evaporative demand"
        )

    if severity < 0.2:
        return None

    # Drone structural corroboration: low canopy cover strengthens water signal
    if canopy_cover is not None and canopy_cover < 0.4:
        severity += 0.08
        evidence_chain.append(
            f"Drone canopy_cover={canopy_cover:.2f} corroborates reduced vegetation cover"
        )

    # Drone structural corroboration: high bare soil fraction
    if bare_soil is not None and bare_soil > 0.5:
        severity += 0.06
        evidence_chain.append(
            f"Drone bare_soil={bare_soil:.2f} indicates exposed soil consistent with water deficit"
        )

    severity = min(1.0, severity)
    confidence = min(conf_ceiling, 0.4 + 0.1 * len(evidence_chain))
    uncertainty = round(base_unc + conflict_penalty, 4)
    is_diag = _is_diagnostic(water_features, "ndmi_mean") or _is_diagnostic(water_features, "ndmi")

    return StressEvidence(
        stress_id=f"water_{plot_id}_{scope_id or 'plot'}",
        stress_type="WATER",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="low_ndmi_low_soil_moisture" if soil_moisture is not None else "low_ndmi",
        contributing_evidence_ids=evidence_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
        diagnostic_only=is_diag,
    )


def _assess_nutrient_stress(
    ndvi, evi, ndmi, soil_moisture,
    conf_ceiling, base_unc, conflict_penalty,
    veg_features, water_features,
    plot_id, run_id, spatial_scope, scope_id,
    has_water_stress: bool,
    canopy_uniformity_cv=None,
) -> Optional[StressEvidence]:
    """Declining NDVI without water deficit suggests nutrient limitation."""
    if ndvi is None or has_water_stress:
        return None

    # Only trigger if NDVI is low but water is adequate
    if ndvi > 0.45:
        return None

    water_ok = (ndmi is not None and ndmi > 0.3) or (soil_moisture is not None and soil_moisture > 0.25)
    if not water_ok:
        return None

    severity = max(0.0, 0.5 - ndvi) * 2.0
    evidence_chain = [
        f"NDVI={ndvi:.2f} indicates reduced vegetation vigor",
        "Water indicators adequate — deficit not attributed to water stress",
    ]
    evidence_ids = _collect_evidence_ids(veg_features, "ndvi_mean", "ndvi", "evi_mean", "evi")
    evidence_ids.extend(_collect_evidence_ids(water_features, "ndmi_mean", "ndmi"))

    if evi is not None and evi < 0.3:
        severity += 0.1
        evidence_chain.append(f"EVI={evi:.2f} corroborates low canopy chlorophyll")

    # Drone structural: high canopy uniformity CV suggests patchy nutrient depletion
    if canopy_uniformity_cv is not None and canopy_uniformity_cv > 0.3:
        severity += 0.08
        evidence_chain.append(
            f"Drone canopy_uniformity_cv={canopy_uniformity_cv:.2f} indicates patchy growth consistent with nutrient variability"
        )

    severity = min(1.0, severity)
    confidence = min(conf_ceiling, 0.3 + 0.1 * len(evidence_chain))
    uncertainty = round(base_unc + conflict_penalty + 0.05, 4)

    if severity < 0.15:
        return None

    return StressEvidence(
        stress_id=f"nutrient_{plot_id}_{scope_id or 'plot'}",
        stress_type="NUTRIENT",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="low_ndvi_adequate_water",
        contributing_evidence_ids=evidence_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
    )


def _assess_thermal_stress(
    temp_max, vpd, ndvi,
    conf_ceiling, base_unc, conflict_penalty,
    env_features, veg_features,
    plot_id, run_id, spatial_scope, scope_id,
) -> Optional[StressEvidence]:
    """High temperature + VPD exceeding crop tolerance."""
    if temp_max is None:
        return None
    if temp_max <= 35.0:
        return None

    severity = min(1.0, (temp_max - 35.0) / 10.0 * 0.5)
    evidence_chain = [
        f"Temperature max={temp_max:.1f}°C exceeds thermal comfort threshold"
    ]
    evidence_ids = _collect_evidence_ids(env_features, "temp_max", "temperature_max")

    if vpd is not None and vpd > 3.0:
        severity += 0.2
        evidence_chain.append(
            f"VPD={vpd:.1f}kPa indicates extreme evaporative demand"
        )

    if ndvi is not None and ndvi < 0.4:
        severity += 0.1
        evidence_chain.append(
            f"NDVI={ndvi:.2f} consistent with thermal-induced vigor reduction"
        )

    severity = min(1.0, severity)
    confidence = min(conf_ceiling, 0.4 + 0.1 * len(evidence_chain))
    uncertainty = round(base_unc + conflict_penalty, 4)

    return StressEvidence(
        stress_id=f"thermal_{plot_id}_{scope_id or 'plot'}",
        stress_type="THERMAL",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="high_temperature_vpd",
        contributing_evidence_ids=evidence_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
    )


def _assess_biotic_stress(
    ndvi, evi, veg_fraction,
    conf_ceiling, base_unc, conflict_penalty,
    veg_features,
    plot_id, run_id, spatial_scope, scope_id,
    has_water_stress: bool,
    has_thermal_stress: bool,
    weed_pressure=None,
    in_row_weed=None,
    inter_row_weed=None,
) -> Optional[StressEvidence]:
    """Vegetation decline not explained by abiotic factors.

    Enhanced with drone weed detection: high weed pressure is a direct
    biotic indicator that can trigger this stress even when abiotic
    stresses are present.
    """
    # Drone weed pressure overrides exclusion logic — weed competition
    # is biotic regardless of other stresses
    weed_triggered = False
    weed_severity = 0.0
    weed_evidence: List[str] = []
    weed_ids: List[str] = []

    if weed_pressure is not None and weed_pressure > 0.15:
        weed_triggered = True
        weed_severity = min(0.6, weed_pressure * 0.8)
        weed_evidence.append(
            f"Drone weed_pressure_index={weed_pressure:.2f} indicates biotic competition"
        )
        weed_ids = _collect_evidence_ids(veg_features, "weed_pressure_index")

        if in_row_weed is not None and in_row_weed > 0.1:
            weed_severity += 0.08
            weed_evidence.append(
                f"In-row weed ratio={in_row_weed:.2f} — competition at plant base"
            )
        if inter_row_weed is not None and inter_row_weed > 0.15:
            weed_severity += 0.06
            weed_evidence.append(
                f"Inter-row weed ratio={inter_row_weed:.2f} — competition between rows"
            )

    if ndvi is None and not weed_triggered:
        return None
    if not weed_triggered:
        if ndvi is not None and ndvi > 0.4:
            return None
        if has_water_stress or has_thermal_stress:
            return None

    severity = max(0.0, 0.4 - ndvi) * 2.0 if ndvi is not None else 0.0
    evidence_chain = []
    if ndvi is not None:
        evidence_chain.append(f"NDVI={ndvi:.2f} indicates vegetation decline")
    if not weed_triggered:
        evidence_chain.append("No water or thermal stress detected — biotic cause possible")
    evidence_ids = _collect_evidence_ids(veg_features, "ndvi_mean", "ndvi")

    # Merge weed-triggered evidence
    if weed_triggered:
        severity += weed_severity
        evidence_chain.extend(weed_evidence)
        evidence_ids.extend(weed_ids)

    if evi is not None and evi < 0.25:
        severity += 0.1
        evidence_chain.append(f"EVI={evi:.2f} corroborates canopy degradation")

    severity = min(1.0, severity)
    # Weed-triggered biotic stress has higher confidence (direct observation)
    if weed_triggered:
        confidence = min(conf_ceiling, 0.45 + 0.08 * len(evidence_chain))
    else:
        confidence = min(conf_ceiling, 0.25)  # lower confidence — exclusion-based
    uncertainty = round(base_unc + conflict_penalty + 0.1, 4)

    if severity < 0.1:
        return None

    return StressEvidence(
        stress_id=f"biotic_{plot_id}_{scope_id or 'plot'}",
        stress_type="BIOTIC",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="weed_pressure_detected" if weed_triggered else "unexplained_vegetation_decline",
        contributing_evidence_ids=evidence_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
    )


def _assess_photosynthetic_shutdown(
    sif, pri, ndvi, evi, temp_max, vpd,
    conf_ceiling, base_unc, conflict_penalty,
    veg_features, env_features,
    plot_id, run_id, spatial_scope, scope_id,
    has_water_stress: bool,
    has_thermal_stress: bool,
) -> Optional[StressEvidence]:
    """SIF drop with stable NDVI indicates acute stomatal closure.

    This is the key early-warning signal: photosynthesis shuts down
    days/weeks before visible canopy changes (NDVI drop, wilting).

    Trigger: SIF < 0.3 AND NDVI > 0.55 (green canopy, dead photosynthesis).
    Corroboration: PRI drop, high VPD, high temperature.
    """
    # Requires SIF data to make this diagnosis
    if sif is None:
        return None

    # Core signal: low SIF with healthy-looking canopy
    if sif >= 0.3:
        return None  # SIF is still active — no shutdown
    if ndvi is not None and ndvi < 0.55:
        return None  # NDVI already low — this is a structural problem, not SIF-specific

    severity = 0.0
    evidence_chain = []
    evidence_ids = _collect_evidence_ids(veg_features, "sif", "sif_mean")

    # Primary signal: SIF drop
    severity += 0.3 + max(0.0, (0.3 - sif) * 2.0)
    evidence_chain.append(
        f"SIF={sif:.2f} indicates photosynthetic shutdown"
    )

    # NDVI still healthy — the key divergence
    if ndvi is not None and ndvi > 0.6:
        severity += 0.15
        evidence_chain.append(
            f"NDVI={ndvi:.2f} shows canopy structure intact — "
            f"acute stomatal closure rather than structural decline"
        )
        evidence_ids.extend(_collect_evidence_ids(veg_features, "ndvi_mean", "ndvi"))

    # Corroboration: PRI drop
    if pri is not None and pri < -0.01:
        severity += 0.1
        evidence_chain.append(
            f"PRI={pri:.3f} corroborates reduced light-use efficiency"
        )
        evidence_ids.extend(_collect_evidence_ids(veg_features, "pri", "pri_mean"))

    # Corroboration: high VPD (stomatal closure driver)
    if vpd is not None and vpd > 2.5:
        severity += 0.1
        evidence_chain.append(
            f"VPD={vpd:.1f}kPa indicates high atmospheric demand — stomatal closure likely"
        )
        evidence_ids.extend(_collect_evidence_ids(env_features, "vpd"))

    # Corroboration: high temperature
    if temp_max is not None and temp_max > 33.0:
        severity += 0.05
        evidence_chain.append(
            f"Temperature={temp_max:.1f}°C consistent with heat-induced stomatal regulation"
        )

    # Context: if water or thermal stress already flagged, this is a refinement
    if has_water_stress or has_thermal_stress:
        evidence_chain.append(
            "SIF confirms active photosynthetic impairment corroborating detected stress"
        )

    if severity < 0.2:
        return None

    severity = min(1.0, severity)
    # Confidence: moderate — SIF is physically powerful but spatially coarse
    confidence = min(conf_ceiling, 0.45 + 0.08 * len(evidence_chain))
    # Cap due to coarse SIF resolution
    confidence = min(confidence, 0.70)
    uncertainty = round(base_unc + conflict_penalty + 0.03, 4)

    return StressEvidence(
        stress_id=f"photosynthetic_shutdown_{plot_id}_{scope_id or 'plot'}",
        stress_type="PHOTOSYNTHETIC_SHUTDOWN",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="sif_drop_ndvi_stable",
        contributing_evidence_ids=evidence_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
    )


# -- Mechanical Stress (Drone structural damage detection) --

def _assess_mechanical_stress(
    row_continuity, row_break_count, canopy_cover, ndvi,
    conf_ceiling, base_unc, conflict_penalty,
    operational_features, vegetation_features,
    plot_id, run_id, spatial_scope, scope_id,
    has_water_stress: bool,
    has_thermal_stress: bool,
) -> Optional[StressEvidence]:
    """Structural damage detected by drone row geometry analysis.

    Trigger conditions:
      - row_continuity_mean < 0.65 (broken/incomplete rows)
      - AND/OR row_break_count >= 3 (multiple visible breaks)
    Exclusion:
      - Not triggered if water or thermal stress fully explains canopy drop
        (unless breaks are severe: row_break_count >= 5)
    Attribution:
      - Mechanical damage (equipment, animal, hail) or structural planting failure
    """
    if row_continuity is None and row_break_count is None:
        return None

    # Only fire if row continuity is degraded or many breaks detected
    has_low_continuity = row_continuity is not None and row_continuity < 0.65
    has_many_breaks = row_break_count is not None and row_break_count >= 3

    if not has_low_continuity and not has_many_breaks:
        return None

    # Exclusion: if abiotic stress explains the damage, skip unless severe
    severe_breaks = row_break_count is not None and row_break_count >= 5
    if (has_water_stress or has_thermal_stress) and not severe_breaks:
        return None

    severity = 0.0
    evidence_chain = []
    evidence_ids = _collect_evidence_ids(
        operational_features, "row_continuity_mean", "row_break_count",
    )

    if has_low_continuity:
        severity += 0.25 + max(0.0, (0.65 - row_continuity) * 1.5)
        evidence_chain.append(
            f"Drone row_continuity={row_continuity:.2f} indicates structural disruption in crop rows"
        )

    if has_many_breaks:
        severity += min(0.3, row_break_count * 0.05)
        evidence_chain.append(
            f"Drone row_break_count={row_break_count} detected — multiple structural discontinuities"
        )

    # Corroboration: low canopy cover confirms visible damage
    if canopy_cover is not None and canopy_cover < 0.5:
        severity += 0.08
        evidence_chain.append(
            f"Drone canopy_cover={canopy_cover:.2f} corroborates reduced structural integrity"
        )
        evidence_ids.extend(
            _collect_evidence_ids(vegetation_features, "canopy_cover_fraction")
        )

    # Corroboration: low NDVI confirms the visible damage is biologically significant
    if ndvi is not None and ndvi < 0.4:
        severity += 0.06
        evidence_chain.append(
            f"NDVI={ndvi:.2f} consistent with mechanically-induced vegetation loss"
        )

    if severity < 0.15:
        return None

    severity = min(1.0, severity)
    # Moderate confidence — drone structural is high fidelity but diagnostic
    confidence = min(conf_ceiling, 0.40 + 0.08 * len(evidence_chain))
    uncertainty = round(base_unc + conflict_penalty + 0.05, 4)

    return StressEvidence(
        stress_id=f"mechanical_{plot_id}_{scope_id or 'plot'}",
        stress_type="MECHANICAL",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="row_structural_damage",
        contributing_evidence_ids=evidence_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
        flags=["DRONE_STRUCTURAL"],
    )


# -- EO Foundation Model Anomaly Corroboration --

def _apply_eo_anomaly_corroboration(
    anomaly_score: float,
    stress_items: List[StressEvidence],
    vegetation_features: Dict[str, Any],
    conf_ceiling: float,
    base_unc: float,
    conflict_penalty: float,
    plot_id: str,
    run_id: str,
    spatial_scope: str,
    scope_id: Optional[str],
) -> None:
    """Apply EO Foundation Model anomaly corroboration.

    Two modes:
      1. Corroborate: When anomaly_score > 0.6 AND existing stress is detected,
         boost severity and confidence of existing stress items.
      2. Novel anomaly: When anomaly_score > 0.8 AND no existing stress is found,
         create an UNKNOWN stress item (the model sees something indices miss).

    This is purely additive — never overrides hand-crafted attribution.
    """
    if anomaly_score < 0.4:
        return  # Score too low to be meaningful

    evidence_ids = _collect_evidence_ids(vegetation_features, "anomaly_score")

    # Mode 1: Corroborate existing stress
    if stress_items and anomaly_score > 0.6:
        boost = min(0.15, (anomaly_score - 0.6) * 0.375)  # 0.6→0, 0.8→0.075, 1.0→0.15
        for item in stress_items:
            item.severity = min(1.0, round(item.severity + boost, 3))
            item.confidence = min(conf_ceiling, round(item.confidence + boost * 0.5, 3))
            item.explanation_basis.append(
                f"EO Foundation Model anomaly_score={anomaly_score:.2f} corroborates {item.stress_type}"
            )
            item.contributing_evidence_ids.extend(evidence_ids)
        return

    # Mode 2: Novel anomaly — the model sees something indices miss
    if not stress_items and anomaly_score > 0.8:
        severity = min(1.0, (anomaly_score - 0.8) * 2.5 + 0.3)  # 0.8→0.3, 1.0→0.8
        confidence = min(conf_ceiling, min(0.60, anomaly_score * 0.5))
        uncertainty = round(base_unc + conflict_penalty + 0.10, 4)

        stress_items.append(StressEvidence(
            stress_id=f"eo_anomaly_{plot_id}_{scope_id or 'plot'}",
            stress_type="UNKNOWN",
            severity=round(severity, 3),
            confidence=round(confidence, 3),
            uncertainty=uncertainty,
            spatial_scope=spatial_scope,
            scope_id=scope_id,
            primary_driver="eo_anomaly_detected",
            contributing_evidence_ids=evidence_ids,
            explanation_basis=[
                f"EO Foundation Model anomaly_score={anomaly_score:.2f} indicates"
                " spectral deviation not captured by standard indices",
                "Anomaly detected in learned embedding space — further investigation"
                " recommended (crop stress, soil change, or management event)",
            ],
            data_health_at_attribution=0.0,
            flags=["EO_ANOMALY", "REQUIRES_INVESTIGATION"],
        ))
