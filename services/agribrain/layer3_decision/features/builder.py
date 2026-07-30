"""
Layer 3 Decision Feature Builder.

Pure function: Layer3InputContext → DecisionFeatures.

Reads ONLY from the L2→L3 adapter output. Does NOT reach back to L1.
All raw signal derivation (rain sums, SAR trends, thermal days) comes
from L2's interpreted stress evidence and operational signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from layer3_decision.schema import PlotContext, Driver
from layer3_decision.features.evapotranspiration import (
    compute_water_budget,
    get_kc_for_stage,
)


@dataclass
class DecisionFeatures:
    """Frozen snapshot of features for Decision Audit.

    All fields are derived from Layer3InputContext,
    NOT from raw FieldTensor or VegIntOutput.
    """
    # Water Context (from L2 stress interpretation)
    rain_sum_7d: float = 0.0
    rain_sum_14d: float = 0.0
    days_since_rain: int = 0
    soil_moisture_proxy: float = 0.5

    # Crop State (from L2 phenology)
    current_stage: str = "UNKNOWN"
    days_in_stage: int = 0
    stage_confidence: float = 0.5
    growth_adequacy: float = 1.0
    growth_velocity_7d: float = 0.0

    # Anomalies (from L2 vegetation intelligence)
    has_anomaly: bool = False
    anomaly_severity: float = 0.0
    anomaly_type: str = "NONE"
    # CONTRACT-2: Reserved for future wiring from L2 persistence tracking.
    # Currently unused in inference.py. Will be populated when L2 emits
    # anomaly duration in vegetation_intelligence items.
    anomaly_duration: int = 0

    # Structure (from L2 operational signals)
    sar_vv_trend_7d: float = 0.0
    sar_roughness_change: float = 0.0

    # Stability (from L2 zone intelligence)
    spatial_stability: str = "UNKNOWN"
    spatial_confidence: float = 0.0

    # Data Quality / Availability (from L2 operational signals)
    sar_available: bool = False
    low_sar_cadence: bool = False
    rain_available: bool = False
    temp_available: bool = False
    optical_available: bool = False
    missing_inputs: List[Driver] = field(default_factory=list)
    sar_obs_count: int = 0
    optical_obs_count: int = 0

    # Thermal & Saturation (from L2 stress evidence)
    heat_stress_days: int = 0
    cold_stress_days: int = 0
    saturation_days: int = 0

    # Energy Balance Context (from L3 evapotranspiration engine)
    lst_canopy_c: Optional[float] = None      # Land Surface Temp (°C)
    t_air_c: Optional[float] = None           # Ambient air temp (°C)
    canopy_air_delta_c: float = 0.0           # T_canopy - T_air (°C). Positive = overheating
    esi: float = 0.0                          # Evaporative Stress Index [0=healthy, 1=shutdown]
    cwsi: float = 0.0                         # Crop Water Stress Index [0=well-watered, 1=stressed]
    et_potential_mm: float = 0.0              # FAO-56 ET₀ × Kc
    et_actual_mm: float = 0.0                 # Energy-balance actual ET
    et_deficit_mm: float = 0.0                # Potential - Actual (water gap)
    transpiration_efficiency: float = 1.0     # Fraction of potential transpiration [0-1]
    lst_available: bool = False               # Whether satellite LST data exists
    energy_balance_method: str = "none"       # "fao56_only" | "energy_balance_fused"

    # Drone Structural Intelligence (from L0 RGB → L1 → L2 → L3 adapter)
    has_drone_structural: bool = False        # Whether drone structural data exists
    canopy_cover_ratio: float = 0.0           # Canopy cover [0-1] from drone RGB
    bare_soil_ratio: float = 0.0              # Bare soil [0-1] from drone RGB
    weed_pressure_index: float = 0.0          # Weed pressure severity [0-1]
    weed_pressure_severity: float = 0.0       # L2-attributed biotic weed severity [0-1]
    canopy_uniformity_cv: float = 0.0         # Coefficient of variation of canopy cover
    mechanical_damage_detected: bool = False  # Mechanical/structural damage from L2
    mechanical_damage_severity: float = 0.0   # Severity of mechanical damage [0-1]
    missing_tree_count: int = 0               # Orchard: count of missing trees
    tree_count: int = 0                       # Orchard: total tree count

    # Forecast Intelligence (from 7-day weather forecast)
    forecast_available: bool = False          # Whether forecast data exists
    forecast_rain_3d: float = 0.0             # Forecast rain next 3 days (mm)
    forecast_rain_7d: float = 0.0             # Forecast rain next 7 days (mm)
    forecast_cold_days: int = 0               # Days with temp_min < 2°C in next 7 days
    # LOGIC-3: Default 15.0°C is deliberately warm so that when forecast data
    # is unavailable (forecast_available=False), the frost diagnosis returns
    # None at its guard check. The value is never consumed in that path
    # but prevents accidental frost false-positives if the guard is bypassed.
    forecast_min_temp: float = 15.0           # Lowest temp_min in next 7 days (°C)
    forecast_heat_days: int = 0               # Days with temp_max > 38°C in next 7 days
    forecast_max_temp: float = 30.0           # Highest temp_max in next 7 days (°C)

    # Atmospheric drivers (SCI-1, SCI-6)
    vpd_kpa: float = 0.0                      # Vapor Pressure Deficit (kPa). >3 = extreme demand.
    wind_speed_ms: float = 0.0                # Wind speed (m/s). >10 = lodging risk.
    wind_available: bool = False              # Whether wind data exists


def build_decision_features(
    l3_context: Any,
    context: PlotContext,
    weather_forecast: Optional[List[Dict]] = None,
) -> DecisionFeatures:
    """Pure function: Layer3InputContext → DecisionFeatures.

    Strictly reads from L2→L3 adapter output.
    All signals are L2-interpreted, not raw L1 data.
    """
    if l3_context is None:
        return _empty_features()

    # --- 1. Operational signal extraction ---
    ops = getattr(l3_context, "operational_signals", {}) or {}

    sar_available = ops.get("sar_available", False)
    optical_available = ops.get("optical_available", False)
    rain_available = ops.get("rain_available", False)
    temp_available = ops.get("temp_available", True)
    sar_obs_count = ops.get("sar_obs_count", 0)
    optical_obs_count = ops.get("optical_obs_count", 0)

    # --- 2. Missing driver analysis ---
    missing: List[Driver] = []
    if not rain_available:
        missing.append(Driver.RAIN)
    if not temp_available:
        missing.append(Driver.TEMP)
    if not sar_available:
        missing.append(Driver.SAR_VV)
    if not optical_available:
        missing.append(Driver.NDVI)

    # --- 3. Water context from L2 stress interpretation ---
    # v2: Use REAL precipitation data when available from L1 timeseries.
    # Falls back to severity-based proxy ONLY when real data is missing.
    water_severity = ops.get("water_deficit_severity", 0.0)
    stress_summary = getattr(l3_context, "stress_summary", {}) or {}

    # Priority 1: Real precipitation from L1 timeseries
    if ops.get("real_rain_available"):
        rain_sum_7d = ops.get("real_rain_sum_7d", 0.0)
        rain_sum_14d = ops.get("real_rain_sum_14d", 0.0)
        days_since_rain = ops.get("real_days_since_rain", 0)
    else:
        # Fallback: proxy from water deficit severity (legacy path)
        # NOTE: This creates a circular evidence loop when water_deficit_severity
        # was itself derived from proxy data. Prefer real rain data always.
        if water_severity > 0.5:
            rain_sum_7d = 2.0
            rain_sum_14d = 3.0
            days_since_rain = 14
        elif water_severity > 0.2:
            rain_sum_7d = 10.0
            rain_sum_14d = 15.0
            days_since_rain = 7
        else:
            rain_sum_7d = 25.0
            rain_sum_14d = 40.0
            days_since_rain = 2

    # Soil moisture proxy from water stress
    soil_moisture_proxy = max(0.0, min(1.0, 1.0 - water_severity))

    # --- 4. Thermal context from L2 stress evidence ---
    thermal_severity = ops.get("thermal_severity", 0.0)
    stress_detail = getattr(l3_context, "stress_detail", {}) or {}

    # Derive thermal day proxies from severity
    heat_stress_days = 0
    cold_stress_days = 0
    if thermal_severity > 0.3:
        # Check if it's heat or cold from the stress detail
        thermal_detail = stress_detail.get("THERMAL", {})
        driver = thermal_detail.get("primary_driver", "")
        if "cold" in driver.lower() or "frost" in driver.lower():
            cold_stress_days = max(1, int(thermal_severity * 7))
        else:
            heat_stress_days = max(1, int(thermal_severity * 7))

    # Saturation from water evidence
    saturation_days = 0
    if stress_summary.get("WATER", 0.0) > 0.3:
        # Check if the water issue is excess (waterlogging) vs deficit
        water_detail = stress_detail.get("WATER", {})
        driver = water_detail.get("primary_driver", "")
        if "excess" in driver.lower() or "saturated" in driver.lower():
            saturation_days = max(1, int(water_severity * 5))

    # --- 5. Crop state from L2 phenology ---
    phenology_stage = getattr(l3_context, "phenology_stage", "unknown") or "unknown"

    # Map L2 stages to L3 canonical stages
    # BUG-9 FIX: Added emergence, harvested, grain_filling as separate keys
    stage_map = {
        "emergence": "EMERGENCE",
        "vegetative": "VEGETATIVE",
        "tillering": "VEGETATIVE",
        "flowering": "REPRODUCTIVE",
        "reproductive": "REPRODUCTIVE",
        "grain_filling": "MATURITY",
        "maturity": "MATURITY",
        "senescence": "SENESCENCE",
        "harvested": "SENESCENCE",
        "bare_soil": "BARE_SOIL",
        "unknown": "UNKNOWN",
    }
    current_stage = stage_map.get(phenology_stage.lower(), "UNKNOWN")

    gdd_vigor = getattr(l3_context, "gdd_adjusted_vigor", None)
    stage_confidence = 0.5
    veg_status = getattr(l3_context, "vegetation_status", {}) or {}

    # Extract confidence from vegetation features
    for vf_name, vf_data in veg_status.items():
        if isinstance(vf_data, dict) and "confidence" in vf_data:
            stage_confidence = max(stage_confidence, vf_data["confidence"])

    # Growth adequacy from vigor
    growth_adequacy = gdd_vigor if gdd_vigor is not None else 1.0

    # Growth velocity from operational signals
    growth_velocity = ops.get("growth_velocity", 0.0)

    # --- 6. Anomalies from L2 operational signals ---
    has_anomaly = ops.get("has_anomaly", False)
    anomaly_severity = ops.get("anomaly_severity", 0.0)
    anomaly_type = ops.get("anomaly_type", "NONE")

    # --- 7. SAR structure signals ---
    # SAR trends are embedded in stress evidence
    sar_vv_trend = 0.0
    sar_roughness = 0.0
    # If we have SAR data and biotic/mechanical stress, it implies SAR signals
    if sar_available and "MECHANICAL" in stress_summary:
        sar_vv_trend = stress_summary.get("MECHANICAL", 0.0) * 2.0
        sar_roughness = stress_summary.get("MECHANICAL", 0.0) * 1.5

    # --- 8. Spatial stability from zone intelligence ---
    zone_status = getattr(l3_context, "zone_status", {}) or {}
    spatial_stability = "STABLE"
    spatial_confidence = 0.5
    if len(zone_status) > 1:
        severities = [z.get("severity", 0.0) for z in zone_status.values()]
        if max(severities) - min(severities) > 0.3:
            spatial_stability = "HETEROGENEOUS"
        spatial_confidence = min(
            z.get("confidence", 0.5) for z in zone_status.values()
        )

    # --- 9. Data health integration ---
    data_health = getattr(l3_context, "data_health", None)
    if data_health:
        conf_ceiling = data_health.confidence_ceiling
        stage_confidence = min(stage_confidence, conf_ceiling)

    low_sar_cadence = sar_available and sar_obs_count <= 5

    features = DecisionFeatures(
        rain_sum_7d=rain_sum_7d,
        rain_sum_14d=rain_sum_14d,
        days_since_rain=days_since_rain,
        soil_moisture_proxy=soil_moisture_proxy,

        current_stage=current_stage,
        days_in_stage=0,  # Not available from L2 summary
        stage_confidence=stage_confidence,
        growth_adequacy=growth_adequacy,
        growth_velocity_7d=growth_velocity,

        has_anomaly=has_anomaly,
        anomaly_severity=anomaly_severity,
        anomaly_type=anomaly_type,
        anomaly_duration=0,

        sar_vv_trend_7d=sar_vv_trend,
        sar_roughness_change=sar_roughness,

        spatial_stability=spatial_stability,
        spatial_confidence=spatial_confidence,

        sar_available=sar_available,
        low_sar_cadence=low_sar_cadence,
        rain_available=rain_available,
        temp_available=temp_available,
        optical_available=optical_available,
        missing_inputs=list(set(missing)),
        sar_obs_count=sar_obs_count,
        optical_obs_count=optical_obs_count,

        heat_stress_days=heat_stress_days,
        cold_stress_days=cold_stress_days,
        saturation_days=saturation_days,
    )

    # --- 10. Energy Balance (Surface Energy Balance fusion) ---
    features = _apply_energy_balance(features, ops, context)

    # --- 11. Drone Structural Intelligence ---
    features = _apply_drone_structural(features, ops)

    # --- 12. Forecast Intelligence ---
    features = _apply_forecast_features(features, weather_forecast or [])

    # --- 13. Atmospheric drivers (SCI-1: VPD, SCI-6: Wind) ---
    features = _apply_atmospheric_drivers(features, ops, l3_context)

    return features


def _empty_features() -> DecisionFeatures:
    """Return empty features for null/missing context."""
    return DecisionFeatures(
        missing_inputs=[Driver.RAIN, Driver.TEMP, Driver.SAR_VV, Driver.NDVI],
    )


def _apply_energy_balance(
    features: DecisionFeatures,
    ops: Dict[str, Any],
    context: PlotContext,
) -> DecisionFeatures:
    """Compute energy balance from L0→L1→L2 signals.

    LST and ET0 arrive through the L0 thermal adapter,
    flow through L1 environment evidence, get interpreted by L2,
    and surface here via operational_signals.
    """
    from layer3_decision.knowledge.crops import get_crop_profile

    # Extract energy balance inputs from operational signals
    lst_canopy_c = ops.get("lst_canopy_c")
    t_air_c = ops.get("t_air_c")
    vpd_kpa = ops.get("vpd_kpa")
    et0_mm = ops.get("et0_mm")
    ndvi = ops.get("ndvi_mean")
    wind_speed = ops.get("wind_speed_ms")

    # Determine Kc from crop profile + phenological stage
    crop_profile = get_crop_profile(context.crop_type)
    kc = get_kc_for_stage(
        crop_type=context.crop_type,
        stage=features.current_stage,
        kc_init=crop_profile.kc_init,
        kc_mid=crop_profile.kc_mid,
        kc_end=crop_profile.kc_end,
    )

    # Compute water budget
    wb = compute_water_budget(
        et0_mm=et0_mm,
        kc=kc,
        lst_canopy_c=lst_canopy_c,
        t_air_c=t_air_c,
        vpd_kpa=vpd_kpa,
        ndvi=ndvi,
        wind_speed_ms=wind_speed,
    )

    # Populate features
    features.lst_canopy_c = lst_canopy_c
    features.t_air_c = t_air_c
    features.canopy_air_delta_c = wb.canopy_air_delta_c
    features.esi = wb.esi
    features.cwsi = wb.cwsi
    features.et_potential_mm = wb.et_potential_mm
    features.et_actual_mm = wb.et_actual_mm
    features.et_deficit_mm = wb.deficit_mm
    features.transpiration_efficiency = wb.transpiration_efficiency
    features.lst_available = lst_canopy_c is not None and t_air_c is not None
    features.energy_balance_method = wb.method

    # Update missing drivers if no LST/ET0
    if lst_canopy_c is None:
        if Driver.LST not in features.missing_inputs:
            features.missing_inputs.append(Driver.LST)
    if et0_mm is None:
        if Driver.ET0 not in features.missing_inputs:
            features.missing_inputs.append(Driver.ET0)

    return features


def _apply_drone_structural(
    features: DecisionFeatures,
    ops: Dict[str, Any],
) -> DecisionFeatures:
    """Populate drone structural fields from L2→L3 adapter operational_signals.

    Data path: L0 (DroneRGBEngine)
             → L1 (drone structural adapter → vegetation/operational evidence)
             → L2 (stress attribution: BIOTIC/weed, MECHANICAL/row damage)
             → L3 adapter (operational_signals keys)
             → here
    """
    has_drone = ops.get("has_drone_structural", False)
    features.has_drone_structural = has_drone

    if not has_drone:
        return features

    features.canopy_cover_ratio = ops.get("canopy_cover_fraction", 0.0)
    features.bare_soil_ratio = ops.get("bare_soil_fraction", 0.0)
    features.weed_pressure_index = ops.get("weed_pressure_index", 0.0)
    features.weed_pressure_severity = ops.get("weed_pressure_severity", 0.0)
    features.canopy_uniformity_cv = ops.get("canopy_uniformity_cv", 0.0)
    features.mechanical_damage_detected = ops.get("mechanical_damage_detected", False)
    features.mechanical_damage_severity = ops.get("mechanical_damage_severity", 0.0)
    features.missing_tree_count = ops.get("missing_tree_count", 0)
    features.tree_count = ops.get("tree_count", 0)

    return features


def _apply_forecast_features(
    features: DecisionFeatures,
    forecast: List[Dict],
) -> DecisionFeatures:
    """Extract forecast-derived features from 7-day weather forecast.

    Feeds the frost risk diagnosis (ENH-4), rain-suppression in policy,
    and heat wave early warning.
    """
    if not forecast:
        return features

    features.forecast_available = True
    rain_3d = 0.0
    rain_7d = 0.0
    cold_days = 0
    heat_days = 0
    min_temp = 50.0   # start high
    max_temp = -50.0  # start low

    for i, day in enumerate(forecast[:7]):
        if not isinstance(day, dict):
            continue

        rain = float(day.get("rain", 0.0) or 0.0)
        t_min = float(day.get("temp_min", 15.0) or 15.0)
        t_max = float(day.get("temp_max", 30.0) or 30.0)

        rain_7d += rain
        if i < 3:
            rain_3d += rain

        if t_min < 2.0:
            cold_days += 1
        if t_max > 38.0:
            heat_days += 1

        min_temp = min(min_temp, t_min)
        max_temp = max(max_temp, t_max)

    features.forecast_rain_3d = round(rain_3d, 1)
    features.forecast_rain_7d = round(rain_7d, 1)
    features.forecast_cold_days = cold_days
    features.forecast_min_temp = round(min_temp, 1) if min_temp < 50.0 else 15.0
    features.forecast_heat_days = heat_days
    features.forecast_max_temp = round(max_temp, 1) if max_temp > -50.0 else 30.0

    return features


def _apply_atmospheric_drivers(
    features: DecisionFeatures,
    ops: Dict[str, Any],
    l3_context: Any,
) -> DecisionFeatures:
    """SCI-1: VPD computation. SCI-6: Wind speed extraction.

    VPD (Vapor Pressure Deficit) is the primary atmospheric driver of
    transpiration demand. High VPD (>3.0 kPa) causes rapid soil drying
    and stomatal closure even without rain deficit.

    Formula (Tetens, 1930):
      e_sat = 0.6108 * exp(17.27 * T / (T + 237.3))  [kPa]
      VPD = e_sat * (1 - RH/100)

    Wind speed drives lodging risk and evapotranspiration rate.
    """
    # --- VPD from L1 weather ---
    # Try to get temp_max and humidity from operational signals or L1 timeseries
    t_max = ops.get("temp_max_recent", None)
    t_min = ops.get("temp_min_recent", None)
    rh = ops.get("relative_humidity", None)

    # Fallback: estimate from L1 timeseries if available
    if t_max is None:
        # Try to read from the last timeseries entry via vegetation_status
        veg = getattr(l3_context, "vegetation_status", {}) or {}
        t_info = veg.get("temperature", {})
        if isinstance(t_info, dict):
            t_max = t_info.get("value")

    if t_max is not None and isinstance(t_max, (int, float)):
        import math as _math
        t_max_f = float(t_max)
        # NUM-2 FIX: FAO-56 Eq. 12 — use mean of e_sat(Tmax) and e_sat(Tmin)
        # instead of e_sat(Tmax) alone, which overestimates VPD by 15-30%.
        e_sat_max = 0.6108 * _math.exp(17.27 * t_max_f / (t_max_f + 237.3))
        if t_min is not None and isinstance(t_min, (int, float)):
            t_min_f = float(t_min)
            e_sat_min = 0.6108 * _math.exp(17.27 * t_min_f / (t_min_f + 237.3))
            e_sat = (e_sat_max + e_sat_min) / 2.0  # FAO-56 Eq. 11
        else:
            # Fallback: t_max only (less accurate, overestimates)
            e_sat = e_sat_max
        if rh is not None and isinstance(rh, (int, float)):
            vpd = e_sat * (1.0 - float(rh) / 100.0)
        else:
            # No RH data: estimate VPD from temp alone
            # Arid regions (MENA default): RH ~ 30-40%
            vpd = e_sat * 0.65  # ~35% RH assumption
        features.vpd_kpa = round(max(0.0, vpd), 2)

    # --- Wind Speed ---
    wind = ops.get("wind_speed_ms", None)
    if wind is None:
        wind = ops.get("wind_speed", None)
    if wind is not None and isinstance(wind, (int, float)):
        features.wind_speed_ms = round(float(wind), 1)
        features.wind_available = True

    return features
