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

    # ── Water stress ─────────────────────────────────────────────────
    water_stress = _assess_water_stress(
        ndmi, soil_moisture, precip, vpd, et0,
        conf_ceiling, base_uncertainty, conflict_penalty,
        water_features, plot_id, run_id, spatial_scope, scope_id,
    )
    if water_stress:
        stress_items.append(water_stress)

    # ── Nutrient stress ──────────────────────────────────────────────
    nutrient_stress = _assess_nutrient_stress(
        ndvi, evi, ndmi, soil_moisture,
        conf_ceiling, base_uncertainty, conflict_penalty,
        vegetation_features, water_features,
        plot_id, run_id, spatial_scope, scope_id,
        has_water_stress=(water_stress is not None),
    )
    if nutrient_stress:
        stress_items.append(nutrient_stress)

    # ── Thermal stress ───────────────────────────────────────────────
    thermal_stress = _assess_thermal_stress(
        temp_max, vpd, ndvi,
        conf_ceiling, base_uncertainty, conflict_penalty,
        environment_features, vegetation_features,
        plot_id, run_id, spatial_scope, scope_id,
    )
    if thermal_stress:
        stress_items.append(thermal_stress)

    # ── Biotic stress (inferred when vegetation drops without abiotic cause) ─
    biotic_stress = _assess_biotic_stress(
        ndvi, evi, veg_fraction,
        conf_ceiling, base_uncertainty, conflict_penalty,
        vegetation_features,
        plot_id, run_id, spatial_scope, scope_id,
        has_water_stress=(water_stress is not None),
        has_thermal_stress=(thermal_stress is not None),
    )
    if biotic_stress:
        stress_items.append(biotic_stress)

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
) -> Optional[StressEvidence]:
    """Vegetation decline not explained by abiotic factors."""
    if ndvi is None:
        return None
    if ndvi > 0.4:
        return None
    if has_water_stress or has_thermal_stress:
        return None

    severity = max(0.0, 0.4 - ndvi) * 2.0
    evidence_chain = [
        f"NDVI={ndvi:.2f} indicates vegetation decline",
        "No water or thermal stress detected — biotic cause possible",
    ]
    evidence_ids = _collect_evidence_ids(veg_features, "ndvi_mean", "ndvi")

    if evi is not None and evi < 0.25:
        severity += 0.1
        evidence_chain.append(f"EVI={evi:.2f} corroborates canopy degradation")

    severity = min(1.0, severity)
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
        primary_driver="unexplained_vegetation_decline",
        contributing_evidence_ids=evidence_ids,
        explanation_basis=evidence_chain,
        data_health_at_attribution=0.0,
    )
