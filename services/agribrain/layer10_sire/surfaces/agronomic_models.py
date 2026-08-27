"""
Biophysical & Agronomic Model Surface Engine (v2)
=================================================

Implements 5 new biophysical surfaces:
  1. SOIL_CARBON: Organic carbon stocks (t C/ha) incorporating RothC outcomes.
  2. N_LEACHING_RISK: Nitrate leaching driven by sand fraction, precipitation, and soil moisture.
  3. N_VOLATILIZATION_RISK: Ammonia volatilization driven by soil pH, temp, wind, and urea rate.
  4. SOIL_COMPACTION: Mechanical compaction driven by clay, moisture, and machinery activity.
  5. THERMAL_STRESS: Crop temperature stress modulated by VPD and optimal crop temperature bounds.
"""
import math
from typing import List, Dict, Optional, Tuple, Any
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId, GroundingClass,
)
from services.agribrain.crop_database import resolve_crop_code, get_crop
from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1, L1SpatialData
from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_combined


def _get_crop_code(inp: Layer10Input) -> str:
    """Safely resolve crop code from inputs."""
    if hasattr(inp, 'crop') and inp.crop:
        return resolve_crop_code(inp.crop)
    if inp.planning:
        from services.agribrain.layer10_sire.adapters.l4_l9_adapters import adapt_l7
        l7_data = adapt_l7(inp.planning)
        if l7_data.crop:
            return resolve_crop_code(l7_data.crop)
    return ""


def _get_weather_metrics(
    inp: Layer10Input, l1_data: Optional[L1SpatialData] = None,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Safely extract current/forecast weather metrics."""
    temp_c = wind_m_s = rh = precip_mm = None

    def numeric(value):
        return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else None

    fc = inp.forecast_context
    if fc:
        tmaxs = getattr(fc, "temperature_max_forecast", []) or []
        tmins = getattr(fc, "temperature_min_forecast", []) or []
        winds = getattr(fc, "wind_speed_forecast", []) or []
        hums = getattr(fc, "humidity_forecast", []) or []
        precips = getattr(fc, "precipitation_forecast", []) or []

        tmax = numeric(tmaxs[0]) if tmaxs else None
        tmin = numeric(tmins[0]) if tmins else None
        if tmax is not None and tmin is not None:
            temp_c = (tmax + tmin) / 2.0
        elif tmax is not None:
            temp_c = tmax
        if winds:
            wind_m_s = numeric(winds[0])
        if hums:
            rh = numeric(hums[0])
        if precips:
            precip_mm = numeric(precips[0])
    # Fill each missing forecast metric from the canonical L1 forcing history.
    # ForecastContext is normally present even when all of its arrays are
    # empty, so an ``else`` here used to disconnect valid L1 weather.
    if any(value is None for value in (temp_c, wind_m_s, rh, precip_mm)):
        if l1_data is None:
            l1_data = adapt_l1(inp.field_tensor)
        wh = getattr(l1_data, "weather_history", []) or []
        if wh:
            last = wh[-1]
            if isinstance(last, dict):
                t_mean = last.get("temperature")
                if t_mean is None:
                    t_mean = last.get("temp_mean", last.get("tmean"))
                if t_mean is None:
                    t_max = numeric(last.get("temp_max"))
                    t_min = numeric(last.get("temp_min"))
                    t_mean = (t_max + t_min) / 2.0 if t_max is not None and t_min is not None else None
                if temp_c is None:
                    temp_c = numeric(t_mean)
                if wind_m_s is None:
                    wind_m_s = numeric(last.get("wind_speed", last.get("wind_speed_m_s")))
                if rh is None:
                    rh = numeric(last.get("humidity", last.get("rh")))
                if precip_mm is None:
                    precip_mm = numeric(last.get("precipitation", last.get("precipitation_mm", last.get("rain"))))

    return temp_c, wind_m_s, rh, precip_mm


def generate_agronomic_models(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
) -> List[SurfaceArtifact]:
    """Generate the 5 biophysical model surfaces."""
    surfaces = []
    crop_code = _get_crop_code(inp)
    if not crop_code:
        raise ValueError("agronomic_models_unavailable:missing_crop_identity")
    crop_spec = get_crop(crop_code)

    if l1_data is None:
        l1_data = adapt_l1(inp.field_tensor, H, W)
    ndvi_r = get_ndvi_raster(l1_data, H, W)

    # Load static properties from L1 field tensor
    static_props = {}
    if inp.field_tensor and hasattr(inp.field_tensor, "static"):
        static_props = getattr(inp.field_tensor, "static", {}) or {}
    
    # Weather metrics
    temp_c, wind_m_s, rh, precip_mm = _get_weather_metrics(inp, l1_data=l1_data)
    required = {
        "soil_org_carbon": static_props.get("soil_org_carbon"),
        "soil_clay": static_props.get("soil_clay"),
        "soil_sand": static_props.get("soil_sand"),
        "soil_ph": static_props.get("soil_ph"),
        "nitrogen_application_kg_ha": static_props.get("nitrogen_application_kg_ha"),
        "temperature": temp_c, "wind": wind_m_s, "humidity": rh, "precipitation": precip_mm,
    }
    missing = [key for key, value in required.items() if not isinstance(value, (int, float)) or not math.isfinite(float(value))]
    sm_raster = l1_data.raster_maps.get("soil_moisture")
    if not sm_raster:
        missing.append("soil_moisture_raster")
    if missing:
        raise ValueError("agronomic_models_unavailable:missing_evidence:" + ",".join(sorted(set(missing))))

    # --- 1. SOIL_CARBON ---
    # Baseline SOC stock (t C/ha) derived from soil_org_carbon % (default 1.8%)
    soc_pct = float(static_props["soil_org_carbon"])
    # Standard conversion: SOC% * BD (1.3) * Depth (30cm) = SOC% * 39.0 t C/ha
    soc_base = soc_pct * 39.0

    # Retrieve L6 RK4 RothC net carbon change (t CO2eq) and convert to t C
    l6_net_c_change = 0.0
    if inp.exec_state:
        from services.agribrain.layer10_sire.adapters.l4_l9_adapters import adapt_l6
        l6_data = adapt_l6(inp.exec_state)
        # Check output_projections or net_carbon_balance_t_co2eq directly
        l6_net_co2eq = getattr(inp.exec_state, "net_carbon_balance_t_co2eq", 0.0) or 0.0
        if not l6_net_co2eq and l6_data.outcome_projections:
            l6_net_co2eq = l6_data.outcome_projections.get("net_carbon_balance_t_co2eq", 0.0)
        # Convert t CO2eq back to t C (ratio 12/44)
        l6_net_c_change = l6_net_co2eq * (12.0 / 44.0)

    # Clay content modifier (clay protects SOC from decomposition)
    clay_pct = float(static_props["soil_clay"])
    clay_modifier = clay_pct / 100.0 * 0.1

    # Generate Soil Carbon Stock Surface (t C/ha) modulated by NDVI
    carbon_mean = soc_base + l6_net_c_change
    carbon_grid = modulate_combined(
        carbon_mean, ndvi_r, H, W,
        ndvi_weight=1.0, invert=False,
        clamp_min=10.0, clamp_max=200.0
    )
    # Apply clay modifier locally
    for r in range(H):
        for c in range(W):
            if carbon_grid[r][c] is not None:
                carbon_grid[r][c] = round(carbon_grid[r][c] * (1.0 + clay_modifier), 3)

    surfaces.append(SurfaceArtifact(
        surface_id=f"SOIL_CARBON_{inp.plot_id}",
        semantic_type=SurfaceType.SOIL_CARBON,
        grid_ref=f"{H}x{W}",
        values=carbon_grid,
        units="t C/ha",
        native_resolution_m=inp.resolution_m,
        render_range=(10.0, 150.0),
        palette_id=PaletteId.CARBON_BROWN,
        source_layers=["L1", "L6"],
        grounding_class=GroundingClass.PROXY_SPATIAL.value,
        provenance={
            "soc_pct": soc_pct,
            "clay_pct": clay_pct,
            "l6_net_c_change_t": round(l6_net_c_change, 4),
            "model": "RothC-26.3 RK4",
        }
    ))

    # --- 2. N_LEACHING_RISK ---
    # Leaching risk increases with sand content, precipitation, and soil moisture
    sand_pct = float(static_props["soil_sand"])
    # Extract soil moisture from L1 (fall back to 0.45)
    sm_raster = l1_data.raster_maps["soil_moisture"]
    sm_values = [v for row in sm_raster for v in row if isinstance(v, (int, float)) and math.isfinite(float(v))]
    if not sm_values:
        raise ValueError("agronomic_models_unavailable:missing_evidence:soil_moisture_values")
    sm_mean = sum(sm_values) / len(sm_values)

    # Nitrogen applied: from prescriptive (L8) or nutrients (L4)
    n_applied = float(static_props["nitrogen_application_kg_ha"])
    if inp.prescriptive:
        from services.agribrain.layer10_sire.adapters.l4_l9_adapters import adapt_l8
        l8_data = adapt_l8(inp.prescriptive)
        for action in l8_data.actions:
            act_type = str(action.get("action_type", "")).lower()
            if "fertil" in act_type or "nutri" in act_type:
                n_applied = 150.0  # active application
    
    # Leaching fraction: sand content * wetness factor * precip factor
    rain_factor = min(1.5, precip_mm / 10.0)
    leaching_risk_base = (sand_pct / 100.0) * sm_mean * (1.0 + rain_factor) * (n_applied / 200.0)
    leaching_risk_base = min(1.0, max(0.0, leaching_risk_base))

    # Spatially modulate: sandy pockets and low-elevation/wet pockets (proxied by NDVI) have higher risk
    leaching_grid = modulate_combined(
        leaching_risk_base, ndvi_r, H, W,
        ndvi_weight=0.5, invert=False,
        clamp_min=0.0, clamp_max=1.0
    )

    surfaces.append(SurfaceArtifact(
        surface_id=f"N_LEACHING_RISK_{inp.plot_id}",
        semantic_type=SurfaceType.N_LEACHING_RISK,
        grid_ref=f"{H}x{W}",
        values=leaching_grid,
        units="index",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.STRESS_RED,
        source_layers=["L1", "L4", "L8"],
        grounding_class=GroundingClass.PROXY_SPATIAL.value,
        provenance={
            "sand_pct": sand_pct,
            "precip_mm": precip_mm,
            "n_applied_kg_ha": n_applied,
        }
    ))

    # --- 3. N_VOLATILIZATION_RISK ---
    # Volatilization increases with soil pH, temperature, wind, and surface-applied nitrogen (urea)
    soil_ph = float(static_props["soil_ph"])
    # Sigmoidal pH factor: volatilization accelerates above pH 7.0
    ph_factor = 1.0 / (1.0 + math.exp(-(soil_ph - 7.0) * 1.5))
    temp_factor = max(0.1, min(1.5, temp_c / 25.0))
    wind_factor = max(0.5, min(2.0, wind_m_s / 3.0))

    volatilization_risk_base = ph_factor * temp_factor * wind_factor
    volatilization_risk_base = min(1.0, max(0.0, volatilization_risk_base))

    # Spatially modulate by NDVI: areas with lower canopy cover (lower NDVI) have more bare soil exposure, increasing wind sweep/volatilization
    volatilization_grid = modulate_combined(
        volatilization_risk_base, ndvi_r, H, W,
        ndvi_weight=1.0, invert=True,
        clamp_min=0.0, clamp_max=1.0
    )

    surfaces.append(SurfaceArtifact(
        surface_id=f"N_VOLATILIZATION_RISK_{inp.plot_id}",
        semantic_type=SurfaceType.N_VOLATILIZATION_RISK,
        grid_ref=f"{H}x{W}",
        values=volatilization_grid,
        units="index",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.RISK_HEAT,
        source_layers=["L1", "L4"],
        grounding_class=GroundingClass.PROXY_SPATIAL.value,
        provenance={
            "soil_ph": soil_ph,
            "temp_c": temp_c,
            "wind_m_s": wind_m_s,
        }
    ))

    # --- 4. SOIL_COMPACTION ---
    # Compaction risk increases with clay content, soil moisture, and machinery traffic
    clay_pct = float(static_props["soil_clay"])
    # Check if machinery is active from L6 execution state
    machinery_active = False
    if inp.exec_state:
        from services.agribrain.layer10_sire.adapters.l4_l9_adapters import adapt_l6
        l6_data = adapt_l6(inp.exec_state)
        for intervention in l6_data.interventions:
            intv_id = str(intervention.get("intervention_id", "")).lower()
            if "tillage" in intv_id or "harvest" in intv_id:
                machinery_active = True
                break
    
    machinery_mult = 1.6 if machinery_active else 1.0
    compaction_base = (clay_pct / 100.0) * sm_mean * machinery_mult
    compaction_base = min(1.0, max(0.0, compaction_base))

    # Spatially modulate by NDVI: higher NDVI often indicates denser biomass where heavy traffic has been avoided,
    # or lower NDVI could align with compacted zone track lines. We modulate with a negative correlation.
    compaction_grid = modulate_combined(
        compaction_base, ndvi_r, H, W,
        ndvi_weight=0.7, invert=True,
        clamp_min=0.0, clamp_max=1.0
    )

    surfaces.append(SurfaceArtifact(
        surface_id=f"SOIL_COMPACTION_{inp.plot_id}",
        semantic_type=SurfaceType.SOIL_COMPACTION,
        grid_ref=f"{H}x{W}",
        values=compaction_grid,
        units="index",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.COMPACTION_PURPLE,
        source_layers=["L1", "L6"],
        grounding_class=GroundingClass.PROXY_SPATIAL.value,
        provenance={
            "clay_pct": clay_pct,
            "machinery_active": machinery_active,
            "soil_moisture_mean": round(sm_mean, 3),
        }
    ))

    # --- 5. THERMAL_STRESS ---
    # Crop thermal stress based on Tetens VPD and air temp relative to Crop bounds
    opt_min = float(crop_spec.optimal_temp_min)
    opt_max = float(crop_spec.optimal_temp_max)

    # Tetens equation for VPD
    e_s = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    e_a = e_s * (rh / 100.0)
    vpd_kpa = max(0.0, e_s - e_a)

    # Calculate stress indicators
    vpd_stress = min(1.0, max(0.0, (vpd_kpa - 1.5) / 2.5)) if vpd_kpa > 1.5 else 0.0
    
    temp_stress = 0.0
    if temp_c > opt_max:
        temp_stress = min(1.0, (temp_c - opt_max) / 10.0)
    elif temp_c < opt_min:
        temp_stress = min(1.0, (opt_min - temp_c) / 10.0)

    thermal_stress_base = max(vpd_stress, temp_stress)
    
    # Spatially modulate by NDVI: areas with higher canopy transpiration/cooling (higher NDVI) have lower stress
    thermal_grid = modulate_combined(
        thermal_stress_base, ndvi_r, H, W,
        ndvi_weight=1.0, invert=True,
        clamp_min=0.0, clamp_max=1.0
    )

    surfaces.append(SurfaceArtifact(
        surface_id=f"THERMAL_STRESS_{inp.plot_id}",
        semantic_type=SurfaceType.THERMAL_STRESS,
        grid_ref=f"{H}x{W}",
        values=thermal_grid,
        units="probability",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.THERMAL_ORANGE,
        source_layers=["L1", "L2"],
        grounding_class=GroundingClass.PROXY_SPATIAL.value,
        provenance={
            "crop_code": crop_code,
            "optimal_range": f"{opt_min}-{opt_max}°C",
            "vpd_kpa": round(vpd_kpa, 2),
            "temp_c": temp_c,
            "humidity_rh": rh,
        }
    ))

    return surfaces
