"""
Layer 2 → Layer 3 Output Adapter.

Builds a clean Layer3InputContext from Layer2Output.
Layer 3 (Decision Engine) should not need raw L1 data.

This adapter surfaces the interpreted intelligence L3 needs to build
DecisionFeatures without reaching back to L1:
  - Stress summary (type → severity)
  - Per-zone stress profiles
  - Vegetation intelligence (NDVI vigor, uniformity, greenness trend)
  - Phenology stage + GDD-adjusted vigor
  - Operational signals (SAR availability, observation counts, water signals)
  - Data quality gates (health, ceiling, usability)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from layer1_fusion.schemas import DataHealthScore

from layer2_intelligence.schemas import Layer2Output, StressEvidence


@dataclass
class Layer3InputContext:
    """What Layer 3 receives from Layer 2.

    Clean, actionable summary — no raw features, only interpreted intelligence.
    """
    plot_id: str = ""
    layer1_run_id: str = ""
    layer2_run_id: str = ""

    # Stress summary: stress_type → max_severity
    stress_summary: Dict[str, float] = field(default_factory=dict)

    # Stress detail: stress_type → {severity, confidence, uncertainty, drivers}
    stress_detail: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Per-zone stress map: zone_id → {dominant_type, severity, confidence, stress_count}
    zone_status: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Vegetation status: feature_name → {value, unit, confidence}
    vegetation_status: Dict[str, Any] = field(default_factory=dict)

    # Phenology
    phenology_stage: str = "unknown"
    gdd_adjusted_vigor: Optional[float] = None
    gdd_accumulated: float = 0.0

    # Operational signals (so L3 feature builder can assess data coverage)
    operational_signals: Dict[str, Any] = field(default_factory=dict)
    # Keys: sar_available, optical_available, rain_available, temp_available,
    #        sar_obs_count, optical_obs_count, water_deficit_severity, etc.

    # Quality gates
    data_health: DataHealthScore = field(default_factory=DataHealthScore)
    confidence_ceiling: float = 0.0
    usable_for_layer3: bool = False

    provenance_ref: str = ""
    flags: List[str] = field(default_factory=list)


def build_layer3_context(pkg: Layer2Output) -> Layer3InputContext:
    """Build the Layer 3 input payload from a Layer 2 output."""

    # Stress summary: max severity per type
    stress_summary: Dict[str, float] = {}
    stress_detail: Dict[str, Dict[str, Any]] = {}

    for s in pkg.stress_context:
        current_max = stress_summary.get(s.stress_type, 0.0)
        if s.severity >= current_max:
            stress_summary[s.stress_type] = s.severity
            stress_detail[s.stress_type] = {
                "severity": s.severity,
                "confidence": s.confidence,
                "uncertainty": s.uncertainty,
                "primary_driver": s.primary_driver,
                "evidence_count": len(s.contributing_evidence_ids),
                "explanation_basis": s.explanation_basis,
                "spatial_scope": s.spatial_scope,
                "diagnostic_only": s.diagnostic_only,
            }

    # Zone status
    zone_status: Dict[str, Dict[str, Any]] = {}
    for zone_id, zsm in pkg.zone_stress_map.items():
        zone_status[zone_id] = {
            "dominant_stress_type": zsm.dominant_stress_type,
            "severity": zsm.max_severity,
            "confidence": zsm.avg_confidence,
            "stress_count": zsm.stress_count,
        }

    # Vegetation status (plot-level features)
    veg_status: Dict[str, Any] = {}
    for vf in pkg.vegetation_intelligence:
        if vf.spatial_scope == "plot":
            veg_status[vf.name] = {
                "value": vf.value,
                "unit": vf.unit,
                "confidence": vf.confidence,
            }

    # Phenology
    stage = "unknown"
    vigor = None
    gdd_acc = 0.0
    for pf in pkg.phenology_adjusted_indices:
        if pf.name == "gdd_adjusted_vigor":
            vigor = pf.value
            stage = pf.crop_stage
            gdd_acc = pf.gdd_accumulated
            break

    # Operational signals — derived from L2's inherited L1 context
    operational = _extract_operational_signals(pkg)

    # Usability
    usable = (
        pkg.diagnostics.status != "unusable"
        and pkg.data_health.overall >= 0.2
    )

    return Layer3InputContext(
        plot_id=pkg.plot_id,
        layer1_run_id=pkg.layer1_run_id,
        layer2_run_id=pkg.run_id,
        stress_summary=stress_summary,
        stress_detail=stress_detail,
        zone_status=zone_status,
        vegetation_status=veg_status,
        phenology_stage=stage,
        gdd_adjusted_vigor=vigor,
        gdd_accumulated=gdd_acc,
        operational_signals=operational,
        data_health=pkg.data_health,
        confidence_ceiling=pkg.data_health.confidence_ceiling,
        usable_for_layer3=usable,
        provenance_ref=pkg.run_id,
        flags=pkg.diagnostics.input_degradation_flags,
    )


def _extract_operational_signals(pkg: Layer2Output) -> Dict[str, Any]:
    """Extract operational coverage signals from L2 output.

    These allow L3's feature builder to determine which drivers are
    available/missing without reaching back to L1.
    """
    signals: Dict[str, Any] = {}

    # Determine driver availability from stress evidence + vegetation features
    stress_types = {s.stress_type for s in pkg.stress_context}
    stress_drivers = set()
    for s in pkg.stress_context:
        if s.primary_driver:
            stress_drivers.add(s.primary_driver)

    # Water availability: if we have WATER stress evidence or water-related
    # vegetation features, water signals were available
    has_water_evidence = "WATER" in stress_types or any(
        "water" in d or "ndmi" in d or "precip" in d
        for d in stress_drivers
    )

    # Vegetation availability: always true if we have vegetation features
    has_veg = len(pkg.vegetation_intelligence) > 0

    # Check for SAR signals in vegetation features or stress evidence
    has_sar = any(
        "sar" in d or "vv" in d or "vh" in d
        for d in stress_drivers
    )

    # Check for thermal signals
    has_thermal = "THERMAL" in stress_types

    # Count observation proxies from vegetation features
    optical_proxy = sum(
        1 for vf in pkg.vegetation_intelligence
        if vf.spatial_scope == "plot" and "ndvi" in vf.name.lower()
    )

    # Water deficit severity (from stress summary)
    water_severity = 0.0
    for s in pkg.stress_context:
        if s.stress_type == "WATER" and s.spatial_scope == "plot":
            water_severity = max(water_severity, s.severity)

    # Temperature stress days proxy
    thermal_severity = 0.0
    for s in pkg.stress_context:
        if s.stress_type == "THERMAL" and s.spatial_scope == "plot":
            thermal_severity = max(thermal_severity, s.severity)

    # Anomaly detection from vegetation intelligence
    has_anomaly = False
    anomaly_severity = 0.0
    anomaly_type = "NONE"
    for vf in pkg.vegetation_intelligence:
        if "anomaly" in vf.name.lower() or "deviation" in vf.name.lower():
            has_anomaly = True
            anomaly_severity = abs(vf.value)
            if vf.value < 0:
                anomaly_type = "DROP"
            elif vf.value > 0:
                anomaly_type = "SURGE"

    # Growth velocity from phenology
    growth_velocity = 0.0
    for pf in pkg.phenology_adjusted_indices:
        if pf.name == "deviation_from_expected":
            growth_velocity = pf.value

    # Inherited gap analysis
    gap_types = set()
    for gap in pkg.gaps_inherited:
        gap_types.add(gap.gap_type)

    rain_available = "NO_RAIN_GAUGE" not in gap_types
    temp_available = True  # Assume available unless explicitly missing
    sar_available = has_sar or "NO_RECENT_SENTINEL1" not in gap_types

    signals["sar_available"] = sar_available
    signals["optical_available"] = has_veg
    signals["rain_available"] = rain_available
    signals["temp_available"] = temp_available
    signals["optical_obs_count"] = max(optical_proxy, 1 if has_veg else 0)
    signals["sar_obs_count"] = 1 if has_sar else 0
    signals["water_deficit_severity"] = water_severity
    signals["thermal_severity"] = thermal_severity
    signals["has_anomaly"] = has_anomaly
    signals["anomaly_severity"] = anomaly_severity
    signals["anomaly_type"] = anomaly_type
    signals["growth_velocity"] = growth_velocity
    signals["has_water_evidence"] = has_water_evidence
    signals["conflict_count"] = len(pkg.conflicts_inherited)
    signals["gap_types"] = sorted(gap_types)

    # --- Drone Structural Intelligence ---
    # These originate from drone RGB analysis (L0 → L1 → L2) and surface
    # structural field metrics for L3 decision-making.
    _extract_drone_structural_signals(pkg, signals)

    # --- Energy Balance signals (from L0 thermal → L1 environment → L2) ---
    # These originate from satellite thermal sensors (Landsat 8/9, ECOSTRESS)
    # ingested at Layer 0, flowing through L1 environment evidence into L2.
    _extract_energy_balance_signals(pkg, signals)

    return signals


def _extract_drone_structural_signals(
    pkg: Layer2Output, signals: Dict[str, Any]
) -> None:
    """Extract drone structural intelligence for L3 decision-making.

    Data path: L0 (DroneRGBEngine)
             → L1 (drone structural adapter → vegetation/operational evidence)
             → L2 (stress attribution: BIOTIC/weed, MECHANICAL/row damage)
             → L3 (this adapter → operational_signals)

    Signals surfaced:
      - has_drone_structural: bool
      - canopy_cover_fraction: float (0-1)
      - bare_soil_fraction: float (0-1)
      - weed_pressure_severity: float (from BIOTIC stress with weed driver)
      - row_continuity_mean: float (0-1, from vegetation features)
      - mechanical_damage_detected: bool (from MECHANICAL stress)
      - mechanical_damage_severity: float
      - missing_tree_count: int (orchard mode)
    """
    has_drone = False

    # Scan vegetation intelligence for drone-originated features
    for vf in pkg.vegetation_intelligence:
        name_lower = vf.name.lower()

        if "canopy_cover_fraction" in name_lower:
            signals["canopy_cover_fraction"] = vf.value
            has_drone = True

        if "bare_soil_fraction" in name_lower:
            signals["bare_soil_fraction"] = vf.value
            has_drone = True

        if "weed_pressure" in name_lower:
            signals["weed_pressure_index"] = vf.value
            has_drone = True

        if "canopy_uniformity_cv" in name_lower:
            signals["canopy_uniformity_cv"] = vf.value
            has_drone = True

        if "missing_tree" in name_lower:
            signals["missing_tree_count"] = int(vf.value)
            has_drone = True

        if "tree_count" in name_lower and "missing" not in name_lower:
            signals["tree_count"] = int(vf.value)
            has_drone = True

    # Extract weed pressure severity from BIOTIC stress with weed driver
    weed_severity = 0.0
    for s in pkg.stress_context:
        if s.stress_type == "BIOTIC" and s.primary_driver == "weed_pressure_detected":
            weed_severity = max(weed_severity, s.severity)
            has_drone = True
    signals["weed_pressure_severity"] = weed_severity

    # Extract mechanical damage from MECHANICAL stress
    mechanical_detected = False
    mechanical_severity = 0.0
    for s in pkg.stress_context:
        if s.stress_type == "MECHANICAL":
            mechanical_detected = True
            mechanical_severity = max(mechanical_severity, s.severity)
            has_drone = True
    signals["mechanical_damage_detected"] = mechanical_detected
    signals["mechanical_damage_severity"] = mechanical_severity

    signals["has_drone_structural"] = has_drone


def _extract_energy_balance_signals(
    pkg: Layer2Output, signals: Dict[str, Any]
) -> None:
    """Extract LST, ET0, VPD, and related signals for energy balance.

    Data path: L0 (Landsat/ECOSTRESS thermal adapter)
             → L1 (environment evidence: lst_canopy, et0, vpd, t_air)
             → L2 (vegetation/water features)
             → L3 (this adapter → operational_signals)
    """
    # Scan vegetation intelligence for energy balance features
    for vf in pkg.vegetation_intelligence:
        name_lower = vf.name.lower()

        if "lst" in name_lower or "land_surface_temp" in name_lower:
            signals["lst_canopy_c"] = vf.value

        if "et0" in name_lower or "reference_et" in name_lower:
            signals["et0_mm"] = vf.value

        if "vpd" in name_lower:
            signals["vpd_kpa"] = vf.value

        if name_lower == "ndvi_mean":
            signals["ndvi_mean"] = vf.value

        if "wind" in name_lower:
            signals["wind_speed_ms"] = vf.value
            
        if "t_air" in name_lower or "air_temp" in name_lower:
            signals["t_air_c"] = vf.value

    # Scan water features for temperature signals
    for wf in getattr(pkg, "water_features", []):
        name_lower = getattr(wf, "name", "").lower()

        if "t_air" in name_lower or "air_temp" in name_lower:
            signals["t_air_c"] = wf.value

        if "et0" in name_lower and "et0_mm" not in signals:
            signals["et0_mm"] = wf.value

    # If t_air not found in water features, check stress evidence drivers
    if "t_air_c" not in signals:
        for s in pkg.stress_context:
            if s.stress_type == "THERMAL" and s.primary_driver:
                driver_lower = s.primary_driver.lower()
                if "temp" in driver_lower:
                    # Extract air temp from explanation basis if available
                    for basis in s.explanation_basis:
                        if "temp" in basis.lower() and "°c" in basis.lower():
                            # Try to parse: "Air temp 38°C" → 38.0
                            import re
                            match = re.search(r'(\d+\.?\d*)\s*[°]', basis)
                            if match:
                                signals["t_air_c"] = float(match.group(1))
                                break

