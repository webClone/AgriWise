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

import math
from typing import Any, Dict, List, Optional

from .schemas import (
    DataHealthScore,
    EvidenceConflict,
    StressEvidence,
    StressEvidenceFactory,
    STRESS_TYPES,
)
from layer2_contracts.state_contracts import (
    UncertaintyBudget,
    StressHypothesisState,
    CANONICAL_HYPOTHESES,
)
from layer2_uncertainty.retrieval_models import (
    NDMIWaterStressModel,
    TemperatureThermalStressModel,
    SalinityECModel,
    UncertaintyPropagator,
)
from layer1_fusion.outputs.asmae_feature_view import (
    get_asmae_state_feature,
    is_asmae_state_usable,
    evaluate_asmae_state_usability,
    ASMAEFeature,
)


def _get_usable_asmae_feature(ctx: Any, var: str) -> Optional[ASMAEFeature]:
    if ctx is None:
        return None
    feat = get_asmae_state_feature(ctx, var)
    if feat is not None and is_asmae_state_usable(feat):
        return feat
    return None


def _asmae_evidence_id(feat: ASMAEFeature) -> tuple[Optional[str], Optional[str], bool]:
    """Resolve ASMAE feature evidence ID.
    
    Returns (evidence_id, derived_id, is_diagnostic_only).
    
    Rules:
    - If artifact_instance_hash is present: returns (f"asmae_artifact:{feat.artifact_instance_hash}", None, False)
    - If content_hash is present: returns (f"asmae_content:{feat.content_hash}", None, False)
    - If neither: returns (None, f"asmae_derived:{feat.variable}", True)
    """
    if getattr(feat, "artifact_instance_hash", None):
        return f"asmae_artifact:{feat.artifact_instance_hash}", None, False
    if getattr(feat, "content_hash", None):
        return f"asmae_content:{feat.content_hash}", None, False
    return None, f"asmae_derived:{feat.variable}", True


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
    context: Optional[Any] = None,
) -> List[StressEvidence]:
    """Run multi-factor stress attribution.

    Returns a list of StressEvidence items with attribution chains.
    """
    stress_items: List[StressEvidence] = []

    # Extract feature values safely
    # V91.2: veg_fit_* keys are enricher-produced fallbacks; L1 canonical keys take priority
    ndmi = _fv(water_features, "ndmi_mean", "ndmi", "veg_fit_ndmi")
    soil_moisture = _fv(water_features, "soil_moisture_vwc", "soil_moisture")
    ndvi = _fv(vegetation_features, "ndvi_mean", "ndvi", "veg_fit_ndvi")
    evi = _fv(vegetation_features, "evi_mean", "evi")
    veg_fraction = _fv(vegetation_features, "vegetation_fraction_scl", "veg_fit_fvc")
    precip = _fv(water_features, "precipitation_mm", "precip_recent", "rain_mm", "rain")
    if precip is None:
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
        context=context,
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
        context=context,
    )
    if nutrient_stress:
        stress_items.append(nutrient_stress)

    # -- Thermal stress --
    thermal_stress = _assess_thermal_stress(
        temp_max, vpd, ndvi,
        conf_ceiling, base_uncertainty, conflict_penalty,
        environment_features, vegetation_features,
        plot_id, run_id, spatial_scope, scope_id,
        context=context,
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
        context=context,
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

    # -- Salinity stress (v3.2 — MENA-critical, Allbed & Kumar 2013) --
    salinity_stress = _assess_salinity_stress(
        ndmi=ndmi, evi=evi, ndvi=ndvi,
        soil_ec=_fv(soil_site_features, "soil_ec_ds_m", "electrical_conductivity"),
        precip=precip,
        conf_ceiling=conf_ceiling, base_unc=base_uncertainty,
        conflict_penalty=conflict_penalty,
        water_features=water_features, vegetation_features=vegetation_features,
        soil_site_features=soil_site_features,
        plot_id=plot_id, run_id=run_id,
        spatial_scope=spatial_scope, scope_id=scope_id,
        has_water_stress=(water_stress is not None),
        context=context,
    )
    if salinity_stress:
        stress_items.append(salinity_stress)

    # -- EO Foundation Model anomaly corroboration --
    if anomaly_score is not None:
        _apply_eo_anomaly_corroboration(
            anomaly_score, stress_items, vegetation_features,
            conf_ceiling, base_uncertainty, conflict_penalty,
            plot_id, run_id, spatial_scope, scope_id,
        )

    # -- v3.2: Compound Stress Interaction Model (Mittler 2006) --
    _apply_compound_stress_synergy(stress_items)

    # -- v3.2: Grouped Tempered Naive Bayes Stress Confidence Fusion --
    posteriors = _bayesian_stress_confidence(
        stress_items,
        ndmi=ndmi, soil_moisture=soil_moisture, ndvi=ndvi, evi=evi,
        temp_max=temp_max, vpd=vpd, precip=precip, sif=sif,
        conf_ceiling=conf_ceiling,
    )

    # -- Operational UNRESOLVED hypothesis: continuous competing diagnostic state --
    if posteriors:
        p_unresolved = posteriors.get("UNRESOLVED", 0.0)
        has_decline = (ndvi is not None and ndvi < 0.45) or (veg_fraction is not None and veg_fraction < 0.40) or (_fv(vegetation_features, "veg_growth_anomaly") is not None)

        # Case A: No specific stress triggers, absorb unexplained decline
        if not stress_items and has_decline and p_unresolved >= 0.15:
            unresolved_sev = round(min(1.0, 0.45 - (ndvi or 0.45) * 0.5 + 0.2), 3)
            stress_items.append(StressEvidenceFactory.create(
                stress_id=f"unresolved_{plot_id}_{scope_id or 'plot'}",
                stress_type="UNRESOLVED",
                severity=unresolved_sev,
                confidence=round(min(conf_ceiling, p_unresolved), 3),
                uncertainty=round(base_uncertainty + conflict_penalty + 0.12, 4),
                magnitude_uncertainty=round(base_uncertainty + 0.08, 4),
                spatial_scope=spatial_scope,
                scope_id=scope_id,
                primary_driver="unexplained_vegetation_decline",
                explanation_basis=[
                    f"Vegetation decline observed (NDVI={ndvi}) without dominant abiotic or biotic driver; "
                    f"Bayesian posterior P(UNRESOLVED|E)={p_unresolved:.3f}"
                ],
                data_health_at_attribution=0.0,
                diagnostic_only=True,
                hypothesis_posterior=round(p_unresolved, 3),
                posterior_status="COMPUTED",
                stress_magnitude=unresolved_sev,
                raw_biological_impact=unresolved_sev,
                normalized_impact=unresolved_sev,
                flags=["UNRESOLVED_RESIDUAL_DECLINE"],
            ))
        # Case B: Stresses exist but high residual uncertainty / competing UNRESOLVED hypothesis
        elif stress_items and p_unresolved >= 0.30 and any(s.confidence < 0.55 or conflict_penalty > 0.05 for s in stress_items):
            for s in stress_items:
                if "HIGH_EPISTEMIC_RESIDUAL" not in s.flags:
                    s.flags.append("HIGH_EPISTEMIC_RESIDUAL")
                s.explanation_basis.append(
                    f"Competing background hypothesis: P(UNRESOLVED|E)={p_unresolved:.3f} indicates substantial unmodeled residual"
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
    """Collect source_evidence_ids from feature dicts.

    V91.2: Only collects non-empty source_evidence_ids. Enricher features
    (veg_fit_*) have source_evidence_ids=[] by design, so they contribute
    nothing here — their provenance is in lineage_source_evidence_ids.
    """
    ids = []
    for k in keys:
        entry = features.get(k)
        if isinstance(entry, dict):
            for eid in entry.get("source_evidence_ids", []):
                if eid and eid not in ids:
                    ids.append(eid)
    return ids


def _collect_derived_artifact_ids(features: Dict[str, Any], *keys: str) -> List[str]:
    """Collect derived_artifact_ids from feature dicts.

    V91.2: Enricher features carry derived_artifact_ids=["veg_curve_fit"].
    These are model artifact references, never real evidence.
    """
    ids = []
    for k in keys:
        entry = features.get(k)
        if isinstance(entry, dict):
            for aid in entry.get("derived_artifact_ids", []):
                if aid and aid not in ids:
                    ids.append(aid)
    return ids


def _collect_lineage_source_ids(features: Dict[str, Any], *keys: str) -> List[str]:
    """Collect lineage_source_evidence_ids from feature dicts.

    V91.2: Real observations the curves/features were fitted from.
    """
    ids = []
    for k in keys:
        entry = features.get(k)
        if isinstance(entry, dict):
            for lid in entry.get("lineage_source_evidence_ids", []):
                if lid and lid not in ids:
                    ids.append(lid)
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
    context=None,
) -> Optional[StressEvidence]:
    """Low NDMI + low soil moisture + corroborating weather = water stress."""
    is_anomaly_only = False
    veg_water_anomaly = _fv(water_features, "veg_water_anomaly")
    if ndmi is None and soil_moisture is None and veg_water_anomaly is None:
        return None

    vpd_diagnostic = _is_diagnostic(water_features, "vpd")

    # Check for independent water evidence (excluding the anomaly itself).
    # Diagnostic-only VPD and transient surface wetness are not independent
    # evidence of root-zone water deficit.
    has_independent = (
        (ndmi is not None) or
        (soil_moisture is not None) or
        (vpd is not None and vpd > 2.0 and not vpd_diagnostic)
    )

    severity = 0.0
    evidence_chain = []
    evidence_ids = _collect_evidence_ids(water_features, "ndmi_mean", "ndmi", "soil_moisture_vwc", "soil_moisture")
    derived_ids = _collect_derived_artifact_ids(water_features, "veg_fit_ndmi", "veg_fit_cwsi", "veg_fit_et_deficit")
    lineage_ids = _collect_lineage_source_ids(water_features, "veg_fit_ndmi", "veg_fit_cwsi", "veg_fit_et_deficit", "ndmi_mean", "ndmi")

    # ASMAE Water state corroboration
    asmae_canopy = _get_usable_asmae_feature(context, "ASMAE_CANOPY_WATER")
    if asmae_canopy is not None:
        if asmae_canopy.value < 0.2:
            severity += 0.2 + max(0.0, (0.2 - asmae_canopy.value) * 1.5)
            evidence_chain.append(
                f"ASMAE canopy water={asmae_canopy.value:.2f} indicates plant water deficit"
            )
            eid, did, force_diag = _asmae_evidence_id(asmae_canopy)
            if eid:
                if eid not in evidence_ids:
                    evidence_ids.append(eid)
            if did:
                if did not in derived_ids:
                    derived_ids.append(did)
            if force_diag:
                is_anomaly_only = True
            has_independent = True

    asmae_root = _get_usable_asmae_feature(context, "ASMAE_ROOT_ZONE_WATER")
    if asmae_root is not None:
        if asmae_root.value < 0.2:
            severity += 0.2 + max(0.0, (0.2 - asmae_root.value) * 1.5)
            evidence_chain.append(
                f"ASMAE root zone water={asmae_root.value:.2f} indicates root-zone water deficit"
            )
            eid, did, force_diag = _asmae_evidence_id(asmae_root)
            if eid:
                if eid not in evidence_ids:
                    evidence_ids.append(eid)
            if did:
                if did not in derived_ids:
                    derived_ids.append(did)
            if force_diag:
                is_anomaly_only = True
            has_independent = True

    # ASMAE Surface wetness event check (never reduces water stress alone)
    asmae_wetness = _get_usable_asmae_feature(context, "ASMAE_SURFACE_WETNESS_EVENT")
    if asmae_wetness is not None:
        evidence_chain.append(
            f"ASMAE surface wetness event={asmae_wetness.value:.2f} detected (short-lived event)"
        )
        eid, did, force_diag = _asmae_evidence_id(asmae_wetness)
        if eid:
            if eid not in evidence_ids:
                evidence_ids.append(eid)
        if did:
            if did not in derived_ids:
                derived_ids.append(did)
        if force_diag:
            is_anomaly_only = True
        # Preserve surface wetness as context only.  It can coexist with a dry
        # root zone and therefore cannot corroborate a deficit independently.

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

    # Contextual: low precipitation (contextual evidence, not direct physiological water stress)
    if precip is not None and precip < 5.0:
        evidence_chain.append(
            f"Precipitation context: recent rainfall={precip:.1f}mm indicates dry meteorological conditions"
        )

    # Corroborating: high VPD
    if vpd is not None and vpd > 2.0:
        severity += 0.1
        evidence_chain.append(
            f"VPD={vpd:.1f}kPa indicates high evaporative demand"
        )

    # Apply anomaly corroboration rule
    if veg_water_anomaly is not None:
        if has_independent:
            severity += veg_water_anomaly * 0.15
            evidence_chain.append(
                f"Vegetation water anomaly={veg_water_anomaly:.2f} corroborates water stress"
            )
        else:
            is_anomaly_only = True
            severity = min(0.35, veg_water_anomaly)
            evidence_chain.append(
                f"Vegetation water anomaly={veg_water_anomaly:.2f} observed without independent corroboration (diagnostic-only)"
            )
        for eid in _collect_derived_artifact_ids(water_features, "veg_water_anomaly"):
            if eid not in derived_ids:
                derived_ids.append(eid)
        for lid in _collect_lineage_source_ids(water_features, "veg_water_anomaly"):
            if lid not in lineage_ids:
                lineage_ids.append(lid)

    # Threshold checks
    min_threshold = 0.15 if is_anomaly_only else 0.2
    if severity < min_threshold:
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
    if is_anomaly_only:
        confidence = min(confidence, 0.35)
    uncertainty = round(base_unc + conflict_penalty, 4)
    is_diag = (
        _is_diagnostic(water_features, "ndmi_mean")
        or _is_diagnostic(water_features, "ndmi")
        or _is_diagnostic(water_features, "veg_fit_ndmi")
        or (vpd is not None and vpd > 2.0 and vpd_diagnostic)
        or is_anomaly_only
    )

    return StressEvidenceFactory.create(
        stress_id=f"water_{plot_id}_{scope_id or 'plot'}",
        stress_type="WATER",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        magnitude_uncertainty=round(math.sqrt(base_unc**2 + conflict_penalty**2 + (0.04 if is_anomaly_only else 0.02)**2), 4),
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="low_ndmi_low_soil_moisture" if soil_moisture is not None else "low_ndmi",
        contributing_evidence_ids=evidence_ids,
        derived_artifact_ids=derived_ids,
        lineage_source_evidence_ids=lineage_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
        diagnostic_only=is_diag,
        stress_magnitude=round(severity, 3),
    )


def _assess_nutrient_stress(
    ndvi, evi, ndmi, soil_moisture,
    conf_ceiling, base_unc, conflict_penalty,
    veg_features, water_features,
    plot_id, run_id, spatial_scope, scope_id,
    has_water_stress: bool,
    canopy_uniformity_cv=None,
    context=None,
) -> Optional[StressEvidence]:
    """Declining NDVI without water deficit suggests nutrient limitation.

    LOGIC-1 FIX: When water stress co-occurs, nutrient stress is no longer
    completely suppressed. Instead, confidence is reduced and a flag is added.
    This allows compound WATER+NUTRIENT stress (Mittler 2006, synergy 1.15×)
    to be detected.
    """
    veg_nutrient_anomaly = _fv(veg_features, "veg_nutrient_anomaly")
    if ndvi is None and veg_nutrient_anomaly is None:
        return None

    # Only trigger if NDVI is low but water is adequate
    if ndvi is not None and ndvi > 0.45:
        return None

    has_biotic_confounder = False
    asmae_biotic = _get_usable_asmae_feature(context, "ASMAE_BIOTIC_CONFOUNDER_RISK")
    if asmae_biotic is not None and asmae_biotic.value > 0.4:
        has_biotic_confounder = True

    # LOGIC-1 FIX: when water stress exists, don't suppress entirely —
    # reduce confidence instead (compound stress is common)
    water_confounds = False
    if has_water_stress:
        water_confounds = True
        water_ok = (ndmi is not None and ndmi > 0.3) or (
            soil_moisture is not None and soil_moisture > 0.25
        )
        has_independent_nutrient_signal = (
            canopy_uniformity_cv is not None and canopy_uniformity_cv > 0.3
        )
        if not water_ok and not has_independent_nutrient_signal:
            return None
    else:
        water_ok = (ndmi is not None and ndmi > 0.3) or (
            soil_moisture is not None and soil_moisture > 0.25
        )
        if not water_ok:
            return None

    # ASMAE Chlorophyll check
    chlorophyll_confounded = False
    asmae_chloro = _get_usable_asmae_feature(context, "ASMAE_CHLOROPHYLL")
    if asmae_chloro is not None and (has_water_stress or has_biotic_confounder):
        chlorophyll_confounded = True

    # Check for positive nutrient indicators (chlorophyll deficit, chlorosis, patchy growth, or anomaly)
    has_nutrient_indicator = (
        (asmae_chloro is not None) or
        (veg_nutrient_anomaly is not None) or
        (canopy_uniformity_cv is not None and canopy_uniformity_cv > 0.3) or
        (evi is not None and evi < 0.22)
    )
    if not has_nutrient_indicator:
        return None

    has_independent = (
        (asmae_chloro is not None and not chlorophyll_confounded) or
        (evi is not None and evi < 0.22) or
        (canopy_uniformity_cv is not None and canopy_uniformity_cv > 0.3)
    )

    is_anomaly_only = False
    severity = max(0.0, 0.5 - ndvi) * 2.0 if ndvi is not None else 0.0
    evidence_chain = []
    if ndvi is not None:
        evidence_chain.append(f"NDVI={ndvi:.2f} indicates reduced vegetation vigor")
    
    if not water_confounds:
        evidence_chain.append(
            "Water indicators adequate — deficit not attributed to water stress"
        )
    else:
        evidence_chain.append(
            "Water stress co-occurs — nutrient signal flagged with reduced "
            "confidence (compound stress possible, Mittler 2006)"
        )
    evidence_ids = _collect_evidence_ids(veg_features, "ndvi_mean", "ndvi", "evi_mean", "evi")
    evidence_ids.extend(_collect_evidence_ids(water_features, "ndmi_mean", "ndmi"))
    nutrient_derived_ids = _collect_derived_artifact_ids(veg_features, "veg_fit_ndvi", "veg_fit_lai")
    nutrient_derived_ids.extend(_collect_derived_artifact_ids(water_features, "veg_fit_ndmi"))
    lineage_ids = _collect_lineage_source_ids(veg_features, "veg_fit_ndvi", "veg_fit_lai", "ndvi_mean", "ndvi", "evi_mean", "evi")
    lineage_ids.extend(_collect_lineage_source_ids(water_features, "veg_fit_ndmi", "ndmi_mean", "ndmi"))

    if asmae_chloro is not None:
        if asmae_chloro.value < 0.45:
            severity += 0.2 + max(0.0, (0.45 - asmae_chloro.value) * 1.5)
            evidence_chain.append(
                f"ASMAE chlorophyll={asmae_chloro.value:.2f} indicates low leaf nitrogen"
            )
            eid, did, force_diag = _asmae_evidence_id(asmae_chloro)
            if eid:
                if eid not in evidence_ids:
                    evidence_ids.append(eid)
            if did:
                if did not in nutrient_derived_ids:
                    nutrient_derived_ids.append(did)
            if force_diag:
                chlorophyll_confounded = True
            has_independent = True
            
            if has_water_stress or has_biotic_confounder:
                chlorophyll_confounded = True
                evidence_chain.append(
                    "Nutrient signal from ASMAE Chlorophyll is confounded by water/biotic stress (reduced confidence)"
                )

    if evi is not None and evi < 0.3:
        severity += 0.1
        evidence_chain.append(f"EVI={evi:.2f} corroborates low canopy chlorophyll")

    # Drone structural: high canopy uniformity CV suggests patchy nutrient depletion
    if canopy_uniformity_cv is not None and canopy_uniformity_cv > 0.3:
        severity += 0.08
        evidence_chain.append(
            f"Drone canopy_uniformity_cv={canopy_uniformity_cv:.2f} indicates patchy growth consistent with nutrient variability"
        )

    # Apply anomaly corroboration
    if veg_nutrient_anomaly is not None:
        if has_independent:
            severity += veg_nutrient_anomaly * 0.15
            evidence_chain.append(
                f"Vegetation nutrient anomaly={veg_nutrient_anomaly:.2f} corroborates nutrient stress"
            )
        else:
            is_anomaly_only = True
            severity = min(0.35, veg_nutrient_anomaly)
            evidence_chain.append(
                f"Vegetation nutrient anomaly={veg_nutrient_anomaly:.2f} observed without independent corroboration (diagnostic-only)"
            )
        for eid in _collect_derived_artifact_ids(veg_features, "veg_nutrient_anomaly"):
            if eid not in nutrient_derived_ids:
                nutrient_derived_ids.append(eid)
        for lid in _collect_lineage_source_ids(veg_features, "veg_nutrient_anomaly"):
            if lid not in lineage_ids:
                lineage_ids.append(lid)

    severity = min(1.0, severity)
    confidence = min(conf_ceiling, 0.3 + 0.1 * len(evidence_chain))
    if is_anomaly_only:
        confidence = min(confidence, 0.35)
    # LOGIC-1 FIX: reduce confidence when water stress or chlorophyll confounder exists
    if water_confounds or chlorophyll_confounded:
        confidence *= 0.5
    uncertainty = round(base_unc + conflict_penalty + 0.05, 4)

    flags = []
    if water_confounds:
        flags.append("WATER_CONFOUNDED")
    if chlorophyll_confounded:
        flags.append("CHLOROPHYLL_CONFOUNDED")
    if is_anomaly_only:
        flags.append("ANOMALY_ONLY_NUTRIENT")

    min_threshold = 0.15
    if severity < min_threshold:
        return None

    return StressEvidenceFactory.create(
        stress_id=f"nutrient_{plot_id}_{scope_id or 'plot'}",
        stress_type="NUTRIENT",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        magnitude_uncertainty=round(math.sqrt(base_unc**2 + conflict_penalty**2 + (0.05 if is_anomaly_only else 0.03)**2), 4),
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="low_ndvi_adequate_water",
        contributing_evidence_ids=evidence_ids,
        derived_artifact_ids=nutrient_derived_ids,
        lineage_source_evidence_ids=lineage_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
        diagnostic_only=water_confounds or chlorophyll_confounded or is_anomaly_only,
        flags=flags,
        stress_magnitude=round(severity, 3),
    )


def _assess_thermal_stress(
    temp_max, vpd, ndvi,
    conf_ceiling, base_unc, conflict_penalty,
    env_features, veg_features,
    plot_id, run_id, spatial_scope, scope_id,
    context=None,
) -> Optional[StressEvidence]:
    """High temperature + VPD exceeding crop tolerance."""
    veg_thermal_anomaly = _fv(env_features, "veg_thermal_anomaly")
    if temp_max is None and veg_thermal_anomaly is None:
        # Check if ASMAE thermal stress is available even if temp_max is missing
        asmae_thermal = _get_usable_asmae_feature(context, "ASMAE_THERMAL_STRESS")
        if asmae_thermal is None:
            return None

    # Check for independent thermal support
    has_independent = (
        (temp_max is not None and temp_max > 35.0) or
        (vpd is not None and vpd > 3.0)
    )

    is_anomaly_only = False

    # Initialize ASMAE thermal
    asmae_thermal = _get_usable_asmae_feature(context, "ASMAE_THERMAL_STRESS")
    if asmae_thermal is not None and asmae_thermal.value > 0.3:
        has_independent = True

    severity = min(1.0, (temp_max - 35.0) / 10.0 * 0.5) if (temp_max is not None and temp_max > 35.0) else 0.0
    evidence_chain = []
    if temp_max is not None and temp_max > 35.0:
        evidence_chain.append(
            f"Temperature max={temp_max:.1f}°C exceeds thermal comfort threshold"
        )
    evidence_ids = _collect_evidence_ids(env_features, "temp_max", "temperature_max")
    thermal_derived_ids = _collect_derived_artifact_ids(env_features, "veg_thermal_anomaly")
    lineage_ids = _collect_lineage_source_ids(env_features, "veg_thermal_anomaly", "temp_max", "temperature_max")

    if asmae_thermal is not None:
        if asmae_thermal.value > 0.3:
            severity += 0.2 + max(0.0, (asmae_thermal.value - 0.3) * 1.5)
            evidence_chain.append(
                f"ASMAE thermal stress={asmae_thermal.value:.2f} indicates elevated canopy temperature"
            )
            eid, did, force_diag = _asmae_evidence_id(asmae_thermal)
            if eid:
                if eid not in evidence_ids:
                    evidence_ids.append(eid)
            if did:
                if did not in thermal_derived_ids:
                    thermal_derived_ids.append(did)
            if force_diag:
                is_anomaly_only = True

    # Apply anomaly corroboration (without resetting prior ASMAE authority demotion)
    if veg_thermal_anomaly is not None:
        if has_independent:
            severity += veg_thermal_anomaly * 0.15
            evidence_chain.append(
                f"Vegetation thermal anomaly={veg_thermal_anomaly:.2f} corroborates thermal stress"
            )
        else:
            is_anomaly_only = True
            severity = min(0.35, veg_thermal_anomaly)
            evidence_chain.append(
                f"Vegetation thermal anomaly={veg_thermal_anomaly:.2f} observed without independent corroboration (diagnostic-only)"
            )
        for eid in _collect_derived_artifact_ids(env_features, "veg_thermal_anomaly"):
            if eid not in thermal_derived_ids:
                thermal_derived_ids.append(eid)
        for lid in _collect_lineage_source_ids(env_features, "veg_thermal_anomaly"):
            if lid not in lineage_ids:
                lineage_ids.append(lid)

    if severity <= 0.0:
        return None

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
    if is_anomaly_only:
        confidence = min(confidence, 0.35)
    uncertainty = round(base_unc + conflict_penalty, 4)

    return StressEvidenceFactory.create(
        stress_id=f"thermal_{plot_id}_{scope_id or 'plot'}",
        stress_type="THERMAL",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        magnitude_uncertainty=round(math.sqrt(base_unc**2 + conflict_penalty**2 + (0.04 if is_anomaly_only else 0.02)**2), 4),
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="high_temperature_vpd",
        contributing_evidence_ids=evidence_ids,
        derived_artifact_ids=thermal_derived_ids,
        lineage_source_evidence_ids=lineage_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
        diagnostic_only=is_anomaly_only,
        stress_magnitude=round(severity, 3),
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
    context=None,
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

    # ASMAE Biotic risk checks
    asmae_biotic = _get_usable_asmae_feature(context, "ASMAE_BIOTIC_CONFOUNDER_RISK")

    # Positive biotic evidence check: weed competition or ASMAE pathogen pattern
    if not weed_triggered and (asmae_biotic is None or asmae_biotic.value <= 0.3):
        # Absence of abiotic stress does NOT imply biotic stress -> UNRESOLVED/None
        return None

    # ASMAE alone!
    if not weed_triggered and asmae_biotic is not None and asmae_biotic.value > 0.3:
        if asmae_biotic.value > 0.7:
            driver = "biotic_pattern_suspicion"
        elif asmae_biotic.value >= 0.5:
            driver = "biotic_scout_priority"
        else:
            driver = "biotic_confounder_possible"

        severity = round(asmae_biotic.value, 3)
        confidence = round(asmae_biotic.confidence, 3)
        uncertainty = round(base_unc + conflict_penalty + 0.1, 4)
        evidence_chain = [
            f"ASMAE biotic risk={asmae_biotic.value:.2f} (cautious interpretation: {driver})"
        ]
        flags = ["BIOTIC_CONFOUNDER_POSSIBLE", "BIOTIC_SCOUT_PRIORITY", "BIOTIC_PATTERN_SUSPICION"]
        biotic_derived_ids = _collect_derived_artifact_ids(veg_features, "veg_fit_ndvi", "veg_fit_fvc")
        lineage_ids = _collect_lineage_source_ids(veg_features, "veg_fit_ndvi", "veg_fit_fvc", "ndvi_mean", "ndvi", "veg_fraction")

        eid, did, force_diag = _asmae_evidence_id(asmae_biotic)
        ev_ids = []
        if eid:
            ev_ids.append(eid)
        if did:
            if did not in biotic_derived_ids:
                biotic_derived_ids.append(did)

        return StressEvidenceFactory.create(
            stress_id=f"biotic_{plot_id}_{scope_id or 'plot'}",
            stress_type="BIOTIC",
            severity=severity,
            confidence=confidence,
            uncertainty=uncertainty,
            magnitude_uncertainty=round(math.sqrt(base_unc**2 + conflict_penalty**2 + 0.06**2), 4),
            spatial_scope=spatial_scope,
            scope_id=scope_id,
            primary_driver=driver,
            contributing_evidence_ids=ev_ids,
            derived_artifact_ids=biotic_derived_ids,
            lineage_source_evidence_ids=lineage_ids,
            explanation_basis=evidence_chain,
            data_health_at_attribution=0.0,
            diagnostic_only=True,
            flags=flags,
            stress_magnitude=round(severity, 3),
        )

    # Weed-triggered positive evidence
    force_biotic_diag = False
    severity = weed_severity
    evidence_chain = list(weed_evidence)
    evidence_ids = list(weed_ids)
    biotic_derived_ids = _collect_derived_artifact_ids(veg_features, "veg_fit_ndvi", "veg_fit_fvc")
    lineage_ids = _collect_lineage_source_ids(veg_features, "veg_fit_ndvi", "veg_fit_fvc", "ndvi_mean", "ndvi", "veg_fraction")

    if ndvi is not None and ndvi < 0.4:
        severity += max(0.0, (0.4 - ndvi) * 0.5)
        evidence_chain.append(f"NDVI={ndvi:.2f} consistent with weed-induced canopy competition")

    if evi is not None and evi < 0.25:
        severity += 0.05
        evidence_chain.append(f"EVI={evi:.2f} corroborates canopy competition")

    # Add ASMAE biotic risk as supporting evidence if present
    if asmae_biotic is not None:
        severity += asmae_biotic.value * 0.15
        evidence_chain.append(
            f"ASMAE biotic risk={asmae_biotic.value:.2f} corroborates weed/biotic observations"
        )
        eid, did, force_diag = _asmae_evidence_id(asmae_biotic)
        if eid:
            if eid not in evidence_ids:
                evidence_ids.append(eid)
        if did:
            if did not in biotic_derived_ids:
                biotic_derived_ids.append(did)
        if force_diag:
            force_biotic_diag = True

    severity = min(1.0, severity)
    confidence = min(conf_ceiling, 0.45 + 0.08 * len(evidence_chain))
    uncertainty = round(base_unc + conflict_penalty + 0.1, 4)

    if severity < 0.1:
        return None

    return StressEvidenceFactory.create(
        stress_id=f"biotic_{plot_id}_{scope_id or 'plot'}",
        stress_type="BIOTIC",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        magnitude_uncertainty=round(math.sqrt(base_unc**2 + conflict_penalty**2 + 0.05**2), 4),
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="weed_pressure_detected",
        contributing_evidence_ids=evidence_ids,
        derived_artifact_ids=biotic_derived_ids,
        lineage_source_evidence_ids=lineage_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
        diagnostic_only=force_biotic_diag,
        stress_magnitude=round(severity, 3),
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
    derived_ids = _collect_derived_artifact_ids(veg_features, "veg_fit_ndvi", "veg_fit_sif", "veg_fit_pri")
    lineage_ids = _collect_lineage_source_ids(veg_features, "veg_fit_ndvi", "veg_fit_sif", "veg_fit_pri", "sif", "sif_mean", "ndvi_mean", "ndvi", "pri", "pri_mean")

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

    return StressEvidenceFactory.create(
        stress_id=f"photosynthetic_shutdown_{plot_id}_{scope_id or 'plot'}",
        stress_type="PHOTOSYNTHETIC_SHUTDOWN",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        magnitude_uncertainty=round(math.sqrt(base_unc**2 + conflict_penalty**2 + 0.04**2), 4),
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="sif_drop_ndvi_stable",
        contributing_evidence_ids=evidence_ids,
        derived_artifact_ids=derived_ids,
        lineage_source_evidence_ids=lineage_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
        stress_magnitude=round(severity, 3),
        biological_impact=round(severity, 3),
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
    derived_ids = _collect_derived_artifact_ids(
        operational_features, "row_continuity_mean", "row_break_count"
    )
    derived_ids.extend(_collect_derived_artifact_ids(vegetation_features, "canopy_cover_fraction", "veg_fit_ndvi"))
    lineage_ids = _collect_lineage_source_ids(
        operational_features, "row_continuity_mean", "row_break_count"
    )
    lineage_ids.extend(_collect_lineage_source_ids(vegetation_features, "canopy_cover_fraction", "veg_fit_ndvi", "ndvi_mean", "ndvi"))

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

    return StressEvidenceFactory.create(
        stress_id=f"mechanical_{plot_id}_{scope_id or 'plot'}",
        stress_type="MECHANICAL",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        magnitude_uncertainty=round(math.sqrt(base_unc**2 + conflict_penalty**2 + 0.04**2), 4),
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="row_structural_damage",
        contributing_evidence_ids=evidence_ids,
        derived_artifact_ids=derived_ids,
        lineage_source_evidence_ids=lineage_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
        flags=["DRONE_STRUCTURAL"],
        stress_magnitude=round(severity, 3),
        biological_impact=round(severity, 3),
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
    # CONTRACT-3 FIX: Only boost the HIGHEST-severity stress item, not all items.
    # An EO anomaly most likely corresponds to the dominant stress — boosting
    # contradictory stresses (e.g., both water stress AND waterlogging) is wrong.
    if stress_items and anomaly_score > 0.6:
        boost = min(0.15, (anomaly_score - 0.6) * 0.375)  # 0.6→0, 0.8→0.075, 1.0→0.15
        # Find the highest-severity stress to corroborate
        top_item = max(stress_items, key=lambda s: s.severity)
        top_item.severity = min(1.0, round(top_item.severity + boost, 3))
        top_item.confidence = min(conf_ceiling, round(top_item.confidence + boost * 0.5, 3))
        top_item.explanation_basis.append(
            f"EO Foundation Model anomaly_score={anomaly_score:.2f} corroborates {top_item.stress_type}"
        )
        top_item.contributing_evidence_ids.extend(evidence_ids)
        for eid in _collect_derived_artifact_ids(vegetation_features, "anomaly_score"):
            if eid not in top_item.derived_artifact_ids:
                top_item.derived_artifact_ids.append(eid)
        for lid in _collect_lineage_source_ids(vegetation_features, "anomaly_score"):
            if lid not in top_item.lineage_source_evidence_ids:
                top_item.lineage_source_evidence_ids.append(lid)
        return

    # Mode 2: Novel anomaly — the model sees something indices miss
    if not stress_items and anomaly_score > 0.8:
        severity = min(1.0, (anomaly_score - 0.8) * 2.5 + 0.3)  # 0.8→0.3, 1.0→0.8
        confidence = min(conf_ceiling, min(0.60, anomaly_score * 0.5))
        uncertainty = round(base_unc + conflict_penalty + 0.10, 4)
        derived_ids = _collect_derived_artifact_ids(vegetation_features, "anomaly_score")
        lineage_ids = _collect_lineage_source_ids(vegetation_features, "anomaly_score")

        stress_items.append(StressEvidenceFactory.create(
            stress_id=f"unknown_{plot_id}_{scope_id or 'plot'}",
            stress_type="UNKNOWN",
            severity=round(severity, 3),
            confidence=round(confidence, 3),
            uncertainty=uncertainty,
            magnitude_uncertainty=round(base_unc + 0.08, 4),
            spatial_scope=spatial_scope,
            scope_id=scope_id,
            primary_driver="eo_foundation_anomaly",
            contributing_evidence_ids=evidence_ids,
            derived_artifact_ids=derived_ids,
            lineage_source_evidence_ids=lineage_ids,
            explanation_basis=[
                f"EO Foundation Model anomaly_score={anomaly_score:.2f} indicates "
                "unattributed spectral anomaly"
            ],
            data_health_at_attribution=0.0,
            flags=["EO_ANOMALY", "REQUIRES_INVESTIGATION"],
            stress_magnitude=round(severity, 3),
            biological_impact=round(severity, 3),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# v3.2: Salinity Stress Attribution (Allbed & Kumar 2013)
# ═══════════════════════════════════════════════════════════════════════════════

def _assess_salinity_stress(
    ndmi: Optional[float],
    evi: Optional[float],
    ndvi: Optional[float],
    soil_ec: Optional[float],
    precip: Optional[float],
    conf_ceiling: float,
    base_unc: float,
    conflict_penalty: float,
    water_features: Dict[str, Any],
    vegetation_features: Dict[str, Any],
    soil_site_features: Dict[str, Any],
    plot_id: str,
    run_id: str,
    spatial_scope: str,
    scope_id: Optional[str],
    has_water_stress: bool,
    context=None,
) -> Optional[StressEvidence]:
    """Detect salinity stress from spectral + soil indicators.

    Salinity manifests as:
      1. Low NDMI (< 0.15) — salt crusting reduces surface moisture signature
      2. Depressed EVI/NDVI ratio (< 0.65) — chlorosis from Na⁺/Cl⁻ toxicity
      3. High soil EC (> 4 dS/m moderately saline, > 8 dS/m severely saline)
         — FAO classification (Richards 1954)
      4. Low precipitation context — salinity accumulates in arid conditions

    Exclusion: If water stress is already attributed AND no soil EC data exists,
    we cannot distinguish drought from salinity spectrally — flag as diagnostic.

    Reference: Allbed & Kumar (2013) "Soil salinity mapping and monitoring
    in arid and semi-arid regions using remote sensing technology"
    """
    evidence = []
    severity_sum = 0.0
    weight_sum = 0.0

    # Indicator 1: Soil EC (most reliable, direct measurement)
    ec_severity = 0.0
    if soil_ec is not None and soil_ec > 2.0:
        # FAO salinity classes: 0-2 non-saline, 2-4 slightly, 4-8 moderate, 8-16 strong, >16 extreme
        if soil_ec > 16.0:
            ec_severity = 1.0
            evidence.append(f"Soil EC={soil_ec:.1f} dS/m — extreme salinity (FAO class)")
        elif soil_ec > 8.0:
            ec_severity = 0.8
            evidence.append(f"Soil EC={soil_ec:.1f} dS/m — strongly saline (FAO class)")
        elif soil_ec > 4.0:
            ec_severity = 0.55
            evidence.append(f"Soil EC={soil_ec:.1f} dS/m — moderately saline (FAO class)")
        else:
            ec_severity = 0.25
            evidence.append(f"Soil EC={soil_ec:.1f} dS/m — slightly saline (FAO class)")
        severity_sum += ec_severity * 0.45  # Highest weight for direct measurement
        weight_sum += 0.45

    # Indicator 2: NDMI depression (salt crusting effect)
    ndmi_severity = 0.0
    if ndmi is not None and ndmi < 0.15:
        ndmi_severity = min(1.0, (0.15 - ndmi) / 0.15)
        evidence.append(f"NDMI={ndmi:.3f} < 0.15 — reduced surface moisture, possible salt crust")
        severity_sum += ndmi_severity * 0.20
        weight_sum += 0.20

    # Indicator 3: EVI/NDVI ratio depression (chlorophyll degradation)
    evi_ratio_severity = 0.0
    if evi is not None and ndvi is not None and ndvi > 0.15:
        evi_ndvi_ratio = evi / ndvi
        if evi_ndvi_ratio < 0.65:
            evi_ratio_severity = min(1.0, (0.65 - evi_ndvi_ratio) / 0.30)
            evidence.append(
                f"EVI/NDVI ratio={evi_ndvi_ratio:.2f} < 0.65 — "
                "chlorophyll degradation consistent with ion toxicity"
            )
            severity_sum += evi_ratio_severity * 0.20
            weight_sum += 0.20

    # Indicator 4: Aridity context (salt accumulation requires low leaching)
    aridity_factor = 0.0
    if precip is not None and precip < 2.0:
        aridity_factor = min(1.0, (2.0 - precip) / 2.0)
        evidence.append(f"Low precipitation={precip:.1f}mm — reduced salt leaching")
        severity_sum += aridity_factor * 0.15
        weight_sum += 0.15

    force_salinity_diag = False
    # ASMAE Salinity corroboration
    asmae_salinity = _get_usable_asmae_feature(context, "ASMAE_SALINITY_STRESS")
    if asmae_salinity is not None:
        if asmae_salinity.value > 0.3:
            severity_sum += asmae_salinity.value * 0.3
            weight_sum += 0.3
            evidence.append(
                f"ASMAE salinity stress={asmae_salinity.value:.2f} indicates elevated soil salinity pressure"
            )

    # Need at least 2 indicators to attribute salinity
    indicator_count = sum([
        ec_severity > 0, ndmi_severity > 0,
        evi_ratio_severity > 0, aridity_factor > 0,
        (asmae_salinity is not None and asmae_salinity.value > 0.3),
    ])
    if indicator_count < 2:
        return None

    severity = severity_sum / max(weight_sum, 0.01)
    if severity < 0.15:
        return None

    # Confidence: highest when we have soil EC data
    confidence = min(conf_ceiling, 0.35 + 0.15 * indicator_count)
    if soil_ec is not None:
        confidence = min(conf_ceiling, confidence + 0.15)

    uncertainty = round(base_unc + conflict_penalty + (0.05 if soil_ec is None else 0.0), 4)

    # Diagnostic-only if we can't distinguish from drought
    diagnostic_only = has_water_stress and soil_ec is None

    if diagnostic_only:
        evidence.append(
            "Spectral indicators overlap with water stress — salinity flagged as "
            "diagnostic only without soil EC confirmation"
        )

    evidence_ids = _collect_evidence_ids(soil_site_features, "soil_ec_ds_m", "electrical_conductivity")
    evidence_ids.extend(_collect_evidence_ids(water_features, "ndmi_mean", "ndmi"))
    evidence_ids.extend(_collect_evidence_ids(vegetation_features, "ndvi_mean", "ndvi", "evi_mean", "evi"))
    
    derived_ids = _collect_derived_artifact_ids(soil_site_features, "soil_ec_ds_m")
    derived_ids.extend(_collect_derived_artifact_ids(water_features, "veg_fit_ndmi"))
    derived_ids.extend(_collect_derived_artifact_ids(vegetation_features, "veg_fit_ndvi", "veg_fit_evi"))

    if asmae_salinity is not None and asmae_salinity.value > 0.3:
        eid, did, force_diag = _asmae_evidence_id(asmae_salinity)
        if eid:
            if eid not in evidence_ids:
                evidence_ids.append(eid)
        if did:
            if did not in derived_ids:
                derived_ids.append(did)
        if force_diag:
            force_salinity_diag = True

    lineage_ids = _collect_lineage_source_ids(soil_site_features, "soil_ec_ds_m")
    lineage_ids.extend(_collect_lineage_source_ids(water_features, "veg_fit_ndmi", "ndmi_mean", "ndmi"))
    lineage_ids.extend(_collect_lineage_source_ids(vegetation_features, "veg_fit_ndvi", "veg_fit_evi", "ndvi_mean", "ndvi", "evi_mean", "evi"))

    return StressEvidenceFactory.create(
        stress_id=f"salinity_{plot_id}_{scope_id or 'plot'}",
        stress_type="SALINITY",
        severity=round(severity, 3),
        confidence=round(confidence, 3),
        uncertainty=uncertainty,
        magnitude_uncertainty=round(math.sqrt(base_unc**2 + conflict_penalty**2 + (0.06 if diagnostic_only else 0.03)**2), 4),
        spatial_scope=spatial_scope,
        scope_id=scope_id,
        primary_driver="soil_ec_elevated" if soil_ec is not None else "spectral_salinity_signature",
        contributing_evidence_ids=evidence_ids,
        derived_artifact_ids=derived_ids,
        lineage_source_evidence_ids=lineage_ids,
        explanation_basis=evidence,
        data_health_at_attribution=0.0,
        diagnostic_only=diagnostic_only or force_salinity_diag,
        flags=["SALINITY_MENA"] if not (diagnostic_only or force_salinity_diag) else ["SALINITY_MENA", "DIAGNOSTIC_ONLY"],
        stress_magnitude=round(severity, 3),
        biological_impact=round(severity, 3),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# v3.2: Compound Stress Interaction Model (Mittler 2006)
# ═══════════════════════════════════════════════════════════════════════════════

# Synergy matrix: (type_a, type_b) → multiplier
# Based on Mittler (2006) "Abiotic stress, the field environment and
# stress combination", Trends in Plant Science 11(1): 15-19
_COMPOUND_SYNERGY_MATRIX: Dict[tuple, float] = {
    ("WATER", "THERMAL"):    1.25,  # Stomatal closure + heat → catastrophic
    ("THERMAL", "WATER"):    1.25,
    ("WATER", "NUTRIENT"):   1.15,  # Nutrient uptake collapses under drought
    ("NUTRIENT", "WATER"):   1.15,
    ("THERMAL", "BIOTIC"):   1.10,  # Heat weakens plant defenses
    ("BIOTIC", "THERMAL"):   1.10,
    ("WATER", "SALINITY"):   1.30,  # Salt + drought → osmotic crisis
    ("SALINITY", "WATER"):   1.30,
    ("THERMAL", "SALINITY"): 1.15,  # Heat + salt → ion toxicity amplified
    ("SALINITY", "THERMAL"): 1.15,
}


def _apply_compound_stress_synergy(
    stress_items: List[StressEvidence],
) -> None:
    """Apply supra-additive synergy when multiple stresses co-occur.

    Physiological Principle:
      - S_k (physical stress magnitude) is UNMUTATED.
      - Synergy factor β_ij amplifies biological impact I_k.

    Modification is in-place on the stress_items list.
    """
    if len(stress_items) < 2:
        return

    # Build type → item index map
    type_items: Dict[str, List[int]] = {}
    for idx, s in enumerate(stress_items):
        type_items.setdefault(s.stress_type, []).append(idx)

    applied_pairs: set = set()

    for idx_a, item_a in enumerate(stress_items):
        for idx_b, item_b in enumerate(stress_items):
            if idx_a >= idx_b:
                continue
            pair_key = tuple(sorted((item_a.stress_type, item_b.stress_type)))
            if pair_key in applied_pairs:
                continue

            synergy = _COMPOUND_SYNERGY_MATRIX.get(
                (item_a.stress_type, item_b.stress_type), 1.0
            )
            if synergy <= 1.0:
                continue

            applied_pairs.add(pair_key)

            # Apply synergy to the WEAKER stress (the one most amplified)
            if item_a.severity <= item_b.severity:
                target, partner = item_a, item_b
            else:
                target, partner = item_b, item_a

            old_severity = target.severity
            target.compound_synergy_factor = synergy
            target.compound_partner = partner.stress_type
            # Scale biological impact without modifying physical stress_magnitude
            target.biological_impact = min(1.0, round(target.stress_magnitude * synergy, 3))
            target.severity = target.biological_impact  # Backwards compatibility
            target.explanation_basis.append(
                f"Compound stress synergy: {target.stress_type}+{partner.stress_type} "
                f"→ biological impact ×{synergy} (Mittler 2006), "
                f"{old_severity:.3f}→{target.severity:.3f}"
            )
            target.flags.append("COMPOUND_STRESS")


# ═══════════════════════════════════════════════════════════════════════════════
# v3.2: Grouped Tempered Naive Bayes Stress Confidence Fusion
# ═══════════════════════════════════════════════════════════════════════════════

# Per-stress-type Gaussian likelihood parameters: (mean, sigma) for each feature
# Features: [ndmi, soil_moisture, ndvi, evi, temp_max, vpd, precip, sif]
# Derived from FAO-56, Hsiao (2009), and field observation distributions.
_BAYES_LIKELIHOODS: Dict[str, Dict[str, tuple]] = {
    "WATER": {
        "ndmi":  (0.08, 0.08),  "soil_moisture": (0.12, 0.08),
        "ndvi":  (0.30, 0.15),  "evi":           (0.20, 0.12),
        "temp_max": (32.0, 8.0), "vpd":          (3.0, 1.5),
        "precip": (0.5, 1.0),   "sif":           (0.3, 0.2),
    },
    "NUTRIENT": {
        "ndmi":  (0.20, 0.10),  "soil_moisture": (0.25, 0.10),
        "ndvi":  (0.35, 0.12),  "evi":           (0.18, 0.10),
        "temp_max": (28.0, 6.0), "vpd":          (1.5, 1.0),
        "precip": (3.0, 3.0),   "sif":           (0.25, 0.15),
    },
    "THERMAL": {
        "ndmi":  (0.15, 0.12),  "soil_moisture": (0.20, 0.12),
        "ndvi":  (0.40, 0.15),  "evi":           (0.30, 0.15),
        "temp_max": (40.0, 5.0), "vpd":          (4.0, 1.5),
        "precip": (1.0, 2.0),   "sif":           (0.2, 0.15),
    },
    "SALINITY": {
        "ndmi":  (0.08, 0.06),  "soil_moisture": (0.15, 0.10),
        "ndvi":  (0.30, 0.12),  "evi":           (0.15, 0.10),
        "temp_max": (35.0, 7.0), "vpd":          (2.5, 1.5),
        "precip": (0.2, 0.5),   "sif":           (0.2, 0.15),
    },
    "BIOTIC": {
        "ndmi":  (0.20, 0.12),  "soil_moisture": (0.25, 0.12),
        "ndvi":  (0.35, 0.15),  "evi":           (0.25, 0.12),
        "temp_max": (28.0, 6.0), "vpd":          (2.0, 1.0),
        "precip": (5.0, 5.0),   "sif":           (0.2, 0.2),
    },
    # Operational UNRESOLVED hypothesis: ambient background / uncharacterized baseline
    "UNRESOLVED": {
        "ndmi":  (0.30, 0.15),  "soil_moisture": (0.25, 0.15),
        "ndvi":  (0.45, 0.15),  "evi":           (0.30, 0.15),
        "temp_max": (26.0, 7.0), "vpd":          (1.8, 1.2),
        "precip": (5.0, 5.0),   "sif":           (0.3, 0.20),
    },
}

# Regional priors — MENA arid zone weighting with operational UNRESOLVED hypothesis
_BAYES_PRIORS: Dict[str, float] = {
    "WATER": 0.28,
    "THERMAL": 0.20,
    "SALINITY": 0.15,
    "NUTRIENT": 0.15,
    "BIOTIC": 0.10,
    "UNRESOLVED": 0.12,
}


def _gaussian_log_likelihood(x: float, mean: float, sigma: float) -> float:
    """Log of Gaussian PDF at x."""
    import math
    if sigma < 1e-6:
        sigma = 1e-6
    return -0.5 * ((x - mean) / sigma) ** 2 - math.log(sigma)


def _bayesian_stress_confidence(
    stress_items: List[StressEvidence],
    ndmi: Optional[float],
    soil_moisture: Optional[float],
    ndvi: Optional[float],
    evi: Optional[float],
    temp_max: Optional[float],
    vpd: Optional[float],
    precip: Optional[float],
    sif: Optional[float],
    conf_ceiling: float,
) -> Dict[str, float]:
    """Adjust stress confidence using bidirectional Bayesian posterior probabilities.

    Groups observations into sensor/physical evidence families to prevent
    spurious probability inflation from collinear optical/weather features.

    Evidence Families:
      - Optical / Canopy: [ndmi, ndvi, evi] (shared variance factor)
      - Water State: [soil_moisture, sif]
      - Atmospheric / Weather: [temp_max, vpd, precip]

    Algorithm:
        P(type | features) ∝ P(type) × Π_family P(E_family | type)
        confidence_new = blend(rule_confidence, bayes_posterior)

    Returns:
        Full posterior distribution dictionary {hypothesis: P(H_k | E)}.
    """
    import math

    # Group observed features by evidence family to mitigate conditional dependence
    families: Dict[str, Dict[str, float]] = {
        "optical": {},
        "water_state": {},
        "weather": {},
    }
    if ndmi is not None:
        families["optical"]["ndmi"] = ndmi
    if ndvi is not None:
        families["optical"]["ndvi"] = ndvi
    if evi is not None:
        families["optical"]["evi"] = evi

    if soil_moisture is not None:
        families["water_state"]["soil_moisture"] = soil_moisture
    if sif is not None:
        families["water_state"]["sif"] = sif

    if temp_max is not None:
        families["weather"]["temp_max"] = temp_max
    if vpd is not None:
        families["weather"]["vpd"] = vpd
    if precip is not None:
        families["weather"]["precip"] = precip

    total_obs = sum(len(f) for f in families.values())
    if total_obs < 2:
        # Default uninformative simplex when observations are sparse
        default_simplex = {
            "WATER": 0.15,
            "THERMAL": 0.15,
            "NUTRIENT": 0.15,
            "SALINITY": 0.10,
            "BIOTIC": 0.15,
            "UNRESOLVED": 0.30,
        }
        for item in stress_items:
            item.hypothesis_posterior = default_simplex.get(item.stress_type, 0.15)
            item.posterior_status = "COMPUTED"
        return default_simplex

    # Compute log-posteriors for each stress type (including UNRESOLVED)
    log_posteriors: Dict[str, float] = {}
    for stress_type, likelihoods in _BAYES_LIKELIHOODS.items():
        prior = _BAYES_PRIORS.get(stress_type, 0.1)
        log_post = math.log(max(prior, 1e-10))

        # Sum family log-likelihoods with conditional-dependence tempering
        for fam_name, fam_feats in families.items():
            if not fam_feats:
                continue
            fam_ll = 0.0
            n_in_fam = len(fam_feats)
            for feat_name, feat_val in fam_feats.items():
                if feat_name in likelihoods:
                    mean, sigma = likelihoods[feat_name]
                    fam_ll += _gaussian_log_likelihood(feat_val, mean, sigma)
            # Effective sample size scaling for collinear family members (tempered naive Bayes)
            effective_weight = 1.0 / math.sqrt(n_in_fam)
            log_post += fam_ll * effective_weight

        log_posteriors[stress_type] = log_post

    # Normalize to probabilities via log-sum-exp to guarantee strict simplex
    max_lp = max(log_posteriors.values())
    exp_sum = sum(math.exp(lp - max_lp) for lp in log_posteriors.values())
    posteriors: Dict[str, float] = {}
    for stype in CANONICAL_HYPOTHESES:
        lp = log_posteriors.get(stype, -10.0)
        posteriors[stype] = round(math.exp(lp - max_lp) / exp_sum, 4)

    # Re-normalize to exact sum 1.0
    tot = sum(posteriors.values())
    if tot > 0:
        posteriors = {k: round(v / tot, 4) for k, v in posteriors.items()}

    # Apply bidirectional update to existing stress items
    for item in stress_items:
        bayes_conf = posteriors.get(item.stress_type)
        if bayes_conf is not None:
            old_conf = item.confidence
            # Record diagnostic hypothesis posterior P(H_k | E)
            item.hypothesis_posterior = round(bayes_conf, 3)
            item.posterior_status = "COMPUTED"
            # Blend: 70% Bayes posterior + 30% rule confidence
            blended = bayes_conf * 0.7 + old_conf * 0.3
            item.confidence = min(conf_ceiling, max(0.05, round(blended, 3)))
            if bayes_conf > old_conf:
                item.explanation_basis.append(
                    f"Bayesian posterior P({item.stress_type}|features)="
                    f"{bayes_conf:.3f} > rule_confidence={old_conf:.3f} — "
                    f"blended to {item.confidence:.3f}"
                )
                item.flags.append("BAYES_BOOSTED")
            elif bayes_conf < old_conf - 0.1:
                item.explanation_basis.append(
                    f"Bayesian posterior P({item.stress_type}|features)="
                    f"{bayes_conf:.3f} < rule_confidence={old_conf:.3f} — "
                    f"moderated to {item.confidence:.3f}"
                )
                item.flags.append("BAYES_MODERATED")

    return posteriors

