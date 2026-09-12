"""
Water Surface Engine (v3) — Multi-Source Spatial Water Stress
==============================================================

Generates the WATER_STRESS_PROB surface using REAL moisture indicators
rather than inverted NDVI proxy.

Data source priority for spatial distribution:
  1. NDMI raster (Normalized Difference Moisture Index) — direct canopy water
  2. SAR VV backscatter — soil surface moisture proxy
  3. IoT soil moisture sensors (if available via L1)
  4. Soil Water Balance Ks coefficient (from L4, zone-level)
  5. NDVI spatial modulation (LAST RESORT fallback only)

The L3 diagnostic probability anchors the field-level mean;
spatial sources distribute that probability across pixels.
"""
import logging
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId, GroundingClass,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.layer10_sire.adapters.l3_adapter import L3DiagnosticData
from services.agribrain.scientific_contracts.crop_phenology import (
    consume_canonical_phenology_output,
)

logger = logging.getLogger(__name__)


def _first_not_none(*values: Any) -> Any:
    """Return the first value that is not None, avoiding falsey drops for 0.0 or 0."""
    for v in values:
        if v is not None:
            return v
    return None


@dataclass(frozen=True)
class VPDStressResult:
    grid: Optional[List[List[float]]]
    vpd_kpa: Optional[float]
    computed_stress_probability: float
    phenology_stage: str
    stage_sensitivity: float
    crop_applicability: str
    humidity_value: Optional[float]
    humidity_source: str
    temp_max_value: Optional[float]
    temp_max_source: str
    temp_min_value: Optional[float]
    temp_min_source: str
    physiological_claim_allowed: bool


def _compute_water_stress_prob(
    inp: Layer10Input,
    l1: L1SpatialData,
    l3: L3DiagnosticData,
    H: int,
    W: int,
) -> Tuple[Optional[List[List[float]]], str, str, Dict[str, Any]]:
    """Compute WATER_STRESS_PROB surface and provenance metadata."""
    grid, grounding, src = _compute_spatial_water_stress(inp, l1, l3, H, W)
    basis = "composite_moisture" if "L1" in src else "l3_diagnostic_anchor"
    prov = {
        "grounding_class": grounding,
        "source_layers": src,
        "method": "MULTI_SOURCE_SPATIAL_WATER_STRESS",
    }
    return grid, grounding, basis, prov


def _compute_drainage_deficit(
    l1: L1SpatialData,
    H: int,
    W: int,
    root_zone_depth_m: float = 0.40,
    field_capacity_vwc: float = 0.35,
    l3: Optional[L3DiagnosticData] = None,
) -> Optional[Tuple[List[List[float]], str, GroundingClass, Dict[str, Any]]]:
    """Compute drainage deficit / waterlogging anoxia risk.

    Returns:
        (grid, units, grounding_class, provenance) or None if no moisture source available.
        - Physical mm: computed from volumetric water content (VWC) above field capacity across root depth.
        - Proxy index: computed from spectral NDMI; labeled as proxy_index (NOT mm).
    """
    c_water = getattr(l3, "canonical_water_state", None) if l3 else None
    if c_water is not None:
        if hasattr(c_water, "soil_water") and hasattr(c_water.soil_water, "theta_fc"):
            field_capacity_vwc = float(c_water.soil_water.theta_fc)

    sm_raster, _ = _get_raster(l1, ["soil_moisture", "root_zone_water", "surface_water"], H, W)
    if sm_raster is not None:
        grid = []
        for r in range(H):
            row = []
            for c in range(W):
                v = sm_raster[r][c] if r < len(sm_raster) and c < len(sm_raster[r]) else None
                if v is not None and v > field_capacity_vwc:
                    # Physical water depth in mm: excess_vwc * root_zone_depth_m * 1000 mm/m
                    excess_mm = min(50.0, max(0.0, (v - field_capacity_vwc) * root_zone_depth_m * 1000.0))
                else:
                    excess_mm = 0.0
                row.append(round(excess_mm, 2))
            grid.append(row)
        prov = {
            "source_type": "volumetric_water_content",
            "root_zone_depth_m": root_zone_depth_m,
            "field_capacity_vwc": field_capacity_vwc,
            "calibrated_physical_units": True,
            "formula": "max(0, (VWC - FC) * Zr * 1000)",
        }
        if c_water is not None:
            prov["canonical_water_authority"] = "L3_WATER_INTELLIGENCE"
            prov["canonical_deep_drainage_mm"] = float(getattr(getattr(c_water, "fluxes", None), "actual", None).deep_drainage_mm) if hasattr(getattr(c_water, "fluxes", None), "actual") else 0.0
        return grid, "mm", GroundingClass.RASTER_GROUNDED, prov

    ndmi_raster, _ = _get_raster(l1, ["ndmi", "water_index"], H, W)
    if ndmi_raster is not None:
        grid = []
        for r in range(H):
            row = []
            for c in range(W):
                v = ndmi_raster[r][c] if r < len(ndmi_raster) and c < len(ndmi_raster[r]) else None
                if v is not None and v > 0.2:
                    # NDMI is a dimensionless optical proxy [0..1], NOT physical millimetres
                    proxy_val = min(1.0, max(0.0, (v - 0.2) / 0.8))
                else:
                    proxy_val = 0.0
                row.append(round(proxy_val, 3))
            grid.append(row)
        prov = {
            "source_type": "spectral_ndmi",
            "calibrated_physical_units": False,
            "note": "dimensionless_canopy_water_proxy_not_physical_mm",
            "formula": "normalized_ndmi_above_threshold",
        }
        return grid, "proxy_index", GroundingClass.PROXY_SPATIAL, prov

    return None


def legacy_generate_water_surfaces_adapter(*args: Any, **kwargs: Any) -> List[SurfaceArtifact]:
    """Legacy positional adapter for generate_water_surfaces.

    Supports legacy positional signatures such as:
      generate_water_surfaces(inp, l1_data, l3_data, H, W)
    Deprecated: Call generate_water_surfaces(inp, H, W, l1_data=..., l3_data=...) directly.
    """
    import warnings
    warnings.warn(
        "Positional legacy signature for generate_water_surfaces is deprecated. "
        "Use generate_water_surfaces(inp, H, W, l1_data=..., l3_data=...).",
        DeprecationWarning,
        stacklevel=2,
    )
    inp = args[0]
    H_arg = args[1] if len(args) > 1 else kwargs.get("H", 10)
    W_arg = args[2] if len(args) > 2 else kwargs.get("W", 10)
    l1_arg = args[3] if len(args) > 3 else kwargs.get("l1_data")
    l3_arg = args[4] if len(args) > 4 else kwargs.get("l3_data")

    if isinstance(H_arg, L1SpatialData):
        actual_l1 = H_arg
        actual_l3 = W_arg if isinstance(W_arg, L3DiagnosticData) else None
        actual_H = int(l1_arg) if isinstance(l1_arg, (int, float)) else int(kwargs.get("H", 10))
        actual_W = int(l3_arg) if isinstance(l3_arg, (int, float)) else int(kwargs.get("W", 10))
    else:
        actual_H = int(H_arg)
        actual_W = int(W_arg)
        actual_l1 = l1_arg
        actual_l3 = l3_arg

    return _generate_water_surfaces_impl(
        inp=inp,
        H=actual_H,
        W=actual_W,
        l1_data=actual_l1,
        l3_data=actual_l3,
    )


def generate_water_surfaces(
    inp: Layer10Input,
    H: Any,
    W: Any,
    l1_data: Optional[L1SpatialData] = None,
    l3_data: Optional[L3DiagnosticData] = None,
    **kwargs: Any,
) -> List[SurfaceArtifact]:
    """Primary typed water surface generation contract.

    Args:
        inp: Layer10Input configuration and tensor metadata.
        H: Target grid height in pixels.
        W: Target grid width in pixels.
        l1_data: Optional pre-adapted L1 spatial data.
        l3_data: Optional pre-adapted L3 diagnostic data.
    """
    if isinstance(H, L1SpatialData):
        # Delegate legacy positional reinterpretation to dedicated adapter
        return legacy_generate_water_surfaces_adapter(inp, H, W, l1_data, l3_data, **kwargs)

    return _generate_water_surfaces_impl(
        inp=inp,
        H=int(H),
        W=int(W),
        l1_data=l1_data,
        l3_data=l3_data,
    )


def _generate_water_surfaces_impl(
    inp: Layer10Input,
    H: int,
    W: int,
    l1_data: Optional[L1SpatialData] = None,
    l3_data: Optional[L3DiagnosticData] = None,
) -> List[SurfaceArtifact]:
    surfaces: List[SurfaceArtifact] = []
    actual_H = H
    actual_W = W
    actual_l1 = l1_data
    actual_l3 = l3_data

    if actual_l1 is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        actual_l1 = adapt_l1(inp.field_tensor, actual_H, actual_W)
    if actual_l3 is None:
        from services.agribrain.layer10_sire.adapters.l3_adapter import adapt_l3
        actual_l3 = adapt_l3(inp.decision)

    # --- 1. WATER_STRESS_PROB — Primary Water Stress Map ---
    prob_grid, grounding_class, basis, prov = _compute_water_stress_prob(
        inp, actual_l1, actual_l3, actual_H, actual_W
    )
    if prob_grid is not None:
        surfaces.append(SurfaceArtifact(
            surface_id=f"WATER_STRESS_PROB_{inp.plot_id}",
            semantic_type=SurfaceType.WATER_STRESS_PROB,
            grid_ref=f"{actual_H}x{actual_W}",
            values=prob_grid,
            units="probability",
            native_resolution_m=inp.resolution_m,
            render_range=(0.0, 1.0),
            palette_id=PaletteId.STRESS_WATER,
            source_layers=["L1", "L3", "L4"],
            grounding_class=grounding_class,
            provenance=prov,
        ))

    # --- 2. DRAINAGE_DEFICIT_MM or WATERLOGGING_PROXY_INDEX — Waterlogging / Anoxia Risk ---
    drainage_result = _compute_drainage_deficit(actual_l1, actual_H, actual_W, l3=actual_l3)
    if drainage_result is not None:
        drainage_grid, units, drainage_grounding, d_prov = drainage_result
        if units == "mm":
            sem_type = SurfaceType.DRAINAGE_DEFICIT_MM
            surf_id = f"DRAINAGE_DEFICIT_MM_{inp.plot_id}"
            render_max = 50.0
        else:
            sem_type = SurfaceType.WATERLOGGING_PROXY_INDEX
            surf_id = f"WATERLOGGING_PROXY_INDEX_{inp.plot_id}"
            render_max = 1.0
            d_prov = dict(d_prov)
            d_prov["prescription_driver_allowed"] = False
            d_prov["is_physical_measurement"] = False

        surfaces.append(SurfaceArtifact(
            surface_id=surf_id,
            semantic_type=sem_type,
            grid_ref=f"{actual_H}x{actual_W}",
            values=drainage_grid,
            units=units,
            native_resolution_m=inp.resolution_m,
            render_range=(0.0, render_max),
            palette_id=PaletteId.STRESS_RED,
            source_layers=["L1"],
            grounding_class=drainage_grounding,
            provenance=d_prov,
        ))

    # --- 3. VPD_STRESS — Vapor Pressure Deficit stomatal stress ---
    vpd_res = _compute_vpd_stress(actual_l1, inp, actual_H, actual_W)
    if vpd_res.grid is not None:
        surfaces.append(SurfaceArtifact(
            surface_id=f"VPD_STRESS_{inp.plot_id}",
            semantic_type=SurfaceType.VPD_STRESS,
            grid_ref=f"{actual_H}x{actual_W}",
            values=vpd_res.grid,
            units="probability",
            native_resolution_m=inp.resolution_m,
            render_range=(0.0, 1.0),
            palette_id=PaletteId.RISK_HEAT,
            source_layers=["L1"],
            grounding_class=GroundingClass.PROXY_SPATIAL.value,
            provenance={
                "vpd_kpa": round(vpd_res.vpd_kpa, 2) if vpd_res.vpd_kpa is not None else None,
                "computed_stress_probability": round(vpd_res.computed_stress_probability, 4),
                "phenology_stage": vpd_res.phenology_stage,
                "stage_sensitivity": vpd_res.stage_sensitivity,
                "crop_applicability": vpd_res.crop_applicability,
                "humidity_source": vpd_res.humidity_source,
                "humidity_value": vpd_res.humidity_value,
                "temp_max_source": vpd_res.temp_max_source,
                "temp_max_value": vpd_res.temp_max_value,
                "temp_min_source": vpd_res.temp_min_source,
                "temp_min_value": vpd_res.temp_min_value,
                "physiological_claim_allowed": vpd_res.physiological_claim_allowed,
                "method": "TETENS_EQUATION",
                "reference": "Allen et al. 1998, FAO-56 Eq. 11-12",
            },
        ))

    return surfaces

# ============================================================================
# RASTER EXTRACTION HELPERS
# ============================================================================

def _get_raster(l1: L1SpatialData, keys: list, H: int, W: int):
    """Try multiple key names to find a raster in L1, return (raster, key) or (None, None)."""
    for key in keys:
        r = l1.raster_maps.get(key)
        if r and _has_valid_pixels(r, H, W):
            return r, key
    return None, None


def _has_valid_pixels(raster, H: int, W: int, min_fraction: float = 0.1) -> bool:
    """Check if a raster has enough valid (non-None) pixels."""
    total = 0
    valid = 0
    for r in range(min(H, len(raster))):
        for c in range(min(W, len(raster[r]))):
            total += 1
            if raster[r][c] is not None:
                valid += 1
    return total > 0 and (valid / total) >= min_fraction


def _raster_stats(raster, H: int, W: int) -> Tuple[float, float, float]:
    """Compute mean, min, max of a raster (ignoring None)."""
    vals = []
    for r in range(min(H, len(raster))):
        for c in range(min(W, len(raster[r]))):
            v = raster[r][c]
            if v is not None:
                vals.append(v)
    if not vals:
        return 0.5, 0.0, 1.0
    return sum(vals) / len(vals), min(vals), max(vals)


# ============================================================================
# CORE: MULTI-SOURCE SPATIAL WATER STRESS
# ============================================================================

def _compute_spatial_water_stress(
    inp: Layer10Input,
    l1: L1SpatialData,
    l3: L3DiagnosticData,
    H: int, W: int
) -> Tuple[list, str, list]:
    """
    Compute the WATER_STRESS_PROB surface using real moisture rasters.

    Returns: (grid, grounding_class, source_layers)
    """
    # --- Step 1: Extract L3 diagnostic probability (field-level anchor) ---
    base_prob, affected_pct, hotspot_zones = _extract_l3_water_diagnosis(l3)
    print(f"[WATER] L3 anchor: base_prob={base_prob:.4f}, affected_pct={affected_pct:.2f}, hotspots={len(hotspot_zones)}", file=sys.stderr)

    # --- Step 2: Try hotspot zones first (best spatial precision) ---
    if hotspot_zones and l1.zone_masks:
        grid = _strategy_hotspot_zones(base_prob, hotspot_zones, l1, H, W)
        if grid:
            print("[WATER] Strategy A: Hotspot zones (zone-grounded)", file=sys.stderr)
            return grid, GroundingClass.ZONE_GROUNDED.value, ["L1", "L3"]

    # --- Step 3: Build composite moisture raster from real indicators ---
    moisture_grid, sources_used = _build_composite_moisture(l1, inp, H, W)

    if moisture_grid:
        # Anchor composite to L3 diagnostic probability
        grid = _anchor_to_diagnosis(moisture_grid, base_prob, affected_pct, H, W)
        grounding = GroundingClass.RASTER_GROUNDED.value
        src = ["L1", "L3"] + sources_used
        print(f"[WATER] Strategy B: Composite moisture ({', '.join(sources_used)})", file=sys.stderr)
        # Log composite output stats
        comp_vals = [v for row in grid for v in row if v is not None]
        if comp_vals:
            print(f"[WATER] Composite grid: mean={sum(comp_vals)/len(comp_vals):.4f}, min={min(comp_vals):.4f}, max={max(comp_vals):.4f}, unique={len(set(round(v,4) for v in comp_vals))}", file=sys.stderr)
        return grid, grounding, src

    # --- Step 4: Deficit-aware fallback (no real moisture rasters) ---
    # CRITICAL: Do NOT use inverted NDVI as a water stress proxy.
    # NDVI is a LAGGING indicator: a crop can have NDVI=0.72 (green) while
    # soil moisture deficit is -65mm (severe). By the time NDVI drops,
    # yield damage is already done.
    #
    # Instead: use the L3 diagnostic probability directly as the stress level,
    # and use NDVI only for SPATIAL DISTRIBUTION (where within the field
    # is likely drier), not for overriding the absolute stress level.
    print("[WATER] Strategy C: L3-anchored spatial distribution (no real moisture rasters)", file=sys.stderr)
    print(f"[WATER] L1 raster_maps keys: {list(l1.raster_maps.keys())}", file=sys.stderr)

    # Also check for deficit_mm in L3 to cross-validate the diagnosis
    deficit_mm = _extract_l3_deficit_mm(l3)
    if deficit_mm is not None:
        # ── ET₀-based crop water requirement (FAO-56) ──
        # Instead of a fixed 80mm ceiling, compute stress relative to actual
        # crop water demand: ETc = Kc × ET₀
        #
        # A 40mm deficit at Kc=1.2 with ET₀=6mm/day (≈50mm/week demand)
        # is far more critical than the same deficit at ET₀=2mm/day.
        et0_daily = _extract_et0(l1)
        kc = _get_stage_kc(inp)
        
        if et0_daily is not None and et0_daily > 0:
            # Crop water demand over ~10 days (typical deficit accumulation window)
            etc_10d = et0_daily * kc * 10.0  # mm over 10 days
            # Stress ratio: deficit / demand. Clamp at 0.95.
            # If demand is 60mm and deficit is 40mm → stress = 0.67
            # If demand is 20mm and deficit is 40mm → stress = 0.95 (severe)
            deficit_prob = min(0.95, abs(deficit_mm) / max(etc_10d, 5.0))
            print(f"[WATER] ET₀-based: ET₀={et0_daily:.1f}mm/d, Kc={kc:.2f}, ETc_10d={etc_10d:.1f}mm, deficit={deficit_mm:.1f}mm → prob={deficit_prob:.3f}", file=sys.stderr)
        else:
            # Fallback: conservative linear scaling (original)
            deficit_prob = min(0.95, abs(deficit_mm) / 80.0)
            print(f"[WATER] Linear fallback (no ET₀): deficit={deficit_mm:.1f}mm → prob={deficit_prob:.3f}", file=sys.stderr)
        
        # Use the higher of diagnostic or deficit-derived probability
        if deficit_prob > base_prob:
            print(f"[WATER] Deficit override: prob={deficit_prob:.3f} (was {base_prob:.3f})", file=sys.stderr)
            base_prob = max(base_prob, deficit_prob)

    # Use NDVI only for spatial distribution (low NDVI areas are drier),
    # but keep the absolute level anchored to the L3 diagnosis
    from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, ndvi_stats
    ndvi_r = get_ndvi_raster(l1, H, W)
    mean, mn, mx, valid_count = ndvi_stats(ndvi_r, H, W)
    rng = mx - mn

    grid = [[round(base_prob, 4)] * W for _ in range(H)]

    if valid_count > 0 and rng > 0.01:
        # Distribute spatially: low NDVI gets slightly more stress, high NDVI slightly less
        # But cap the modulation at ±20% of base_prob — NDVI is only a spatial proxy here
        for r in range(H):
            for c in range(W):
                v = ndvi_r[r][c] if r < len(ndvi_r) and c < len(ndvi_r[r]) else None
                if v is not None:
                    norm = (v - mean) / rng  # [-1, +1]
                    # Invert: low NDVI → higher stress
                    modulated = base_prob * (1.0 - norm * 0.20)
                    grid[r][c] = round(max(0.0, min(1.0, modulated)), 4)

    # Log output stats
    vals = [v for row in grid for v in row if v is not None]
    if vals:
        print(f"[WATER] Output grid: mean={sum(vals)/len(vals):.4f}, min={min(vals):.4f}, max={max(vals):.4f}, unique={len(set(round(v,4) for v in vals))}", file=sys.stderr)
    return grid, GroundingClass.PROXY_SPATIAL.value, ["L1", "L3"]


def _extract_l3_water_diagnosis(l3: L3DiagnosticData):
    """Extract water stress probability from L3 diagnoses."""
    stress_dx = None
    for dx in l3.diagnoses:
        pid = dx.get('problem_id', '') if isinstance(dx, dict) else getattr(dx, 'problem_id', '')
        pid_upper = pid.upper()
        if "WATER_STRESS" in pid_upper or "DROUGHT" in pid_upper:
            prob = dx.get('probability', 0.0) if isinstance(dx, dict) else getattr(dx, 'probability', 0.0)
            if stress_dx is None:
                stress_dx = dx
            else:
                prev_prob = stress_dx.get('probability', 0.0) if isinstance(stress_dx, dict) else getattr(stress_dx, 'probability', 0.0)
                if prob > prev_prob:
                    stress_dx = dx

    if stress_dx is None:
        return 0.15, 1.0, []  # Low baseline, no diagnosis

    if isinstance(stress_dx, dict):
        base_prob = stress_dx.get('probability', 0.0)
        affected_pct = stress_dx.get('affected_area_pct', 100.0) / 100.0
        hotspot_zones = stress_dx.get('hotspot_zone_ids', [])
    else:
        base_prob = getattr(stress_dx, 'probability', 0.0)
        affected_pct = getattr(stress_dx, 'affected_area_pct', 100.0) / 100.0
        hotspot_zones = getattr(stress_dx, 'hotspot_zone_ids', [])

    return base_prob, affected_pct, hotspot_zones


def _extract_l3_deficit_mm(l3: L3DiagnosticData) -> float:
    """Extract water deficit in mm from L3 diagnoses or recommendations.

    The L3 water balance engine typically provides deficit_mm in the
    diagnosis metadata or the recommendation context. This is the
    physically-derived soil water balance, which is far more reliable
    than NDVI as an early-warning indicator.
    """
    for dx in l3.diagnoses:
        pid = dx.get('problem_id', '') if isinstance(dx, dict) else getattr(dx, 'problem_id', '')
        if 'WATER' in pid.upper() or 'DROUGHT' in pid.upper():
            # Check direct field
            deficit = dx.get('deficit_mm') if isinstance(dx, dict) else getattr(dx, 'deficit_mm', None)
            if deficit is not None:
                return float(deficit)
            # Check severity as a proxy (severity 0-1 maps to ~0-100mm deficit)
            severity = dx.get('severity', 0) if isinstance(dx, dict) else getattr(dx, 'severity', 0)
            prob = dx.get('probability', 0) if isinstance(dx, dict) else getattr(dx, 'probability', 0)
            if severity > 0.3 and prob > 0.3:
                # Approximate deficit from severity × typical crop water requirement
                return severity * 80.0  # Conservative: max ~80mm

    # Check recommendations for deficit_mm context
    for rec in l3.recommendations:
        meta = rec.get('metadata', {}) if isinstance(rec, dict) else {}
        deficit = meta.get('deficit_mm')
        if deficit is not None:
            return float(deficit)

    return None


def _extract_et0(l1) -> Optional[float]:
    """Extract reference evapotranspiration (ET₀) from L1 weather data.

    Sources (priority order):
      1. L1 last_values['et0'] — today's computed ET₀ from Open-Meteo
      2. L1 weather_history[-1]['et0'] — most recent day
      3. L1 last_values['evapotranspiration'] — alternate key
    Returns mm/day or None if not available.
    """
    # Direct key
    et0 = l1.last_values.get('et0')
    if et0 is not None and float(et0) > 0:
        return float(et0)

    # Alternate key
    et0 = l1.last_values.get('evapotranspiration')
    if et0 is not None and float(et0) > 0:
        return float(et0)

    # From weather history
    if l1.weather_history:
        last_day = l1.weather_history[-1]
        et0 = last_day.get('et0') or last_day.get('et0_fao_evapotranspiration')
        if et0 is not None and float(et0) > 0:
            return float(et0)

    return None


# FAO-56 crop coefficient lookup by phenology stage
# Source: Allen et al. (1998) FAO Irrigation & Drainage Paper 56
# These are mid-range Kc values for field crops (wheat, corn, sorghum)
_KC_BY_STAGE = {
    "BARE_SOIL":    0.30,   # Kc_ini — minimal crop cover
    "EMERGENCE":    0.40,   # Early Kc_ini
    "VEGETATIVE":   0.85,   # Kc_mid transitioning
    "REPRODUCTIVE": 1.15,   # Kc_mid — peak water demand
    "SENESCENCE":   0.70,   # Kc_end — declining demand
    "HARVESTED":    0.30,   # Post-harvest residue
    "UNKNOWN":      0.80,   # Conservative mid-season estimate
}


def _get_stage_kc(inp) -> float:
    """Get crop coefficient (Kc) from phenology stage (FAO-56).

    The Kc modulates ET₀ to get actual crop water demand (ETc = Kc × ET₀).
    Higher Kc during reproductive stage means the crop is more vulnerable
    to the same raw deficit — this is agronomically critical.
    """
    stage = consume_canonical_phenology_output(inp.veg_int)["resolved_crop_stage"]

    return _KC_BY_STAGE.get(stage, _KC_BY_STAGE["UNKNOWN"])


def _strategy_hotspot_zones(base_prob, hotspot_zones, l1, H, W):
    """Strategy A: Zone-grounded stress from L3 hotspot zones.

    Falls through (returns None) when hotspot zones cover >= 90% of the field,
    since field-wide coverage means there's no spatial contrast between zones.
    Strategy B/C will handle those cases with better spatial differentiation.
    """
    hotspot_cells = set()
    for z_id in hotspot_zones:
        for r, c in l1.zone_masks.get(z_id, []):
            if r < H and c < W:
                hotspot_cells.add((r, c))

    if not hotspot_cells:
        return None

    # If hotspots cover >= 90% of the grid, the stress is field-wide.
    # Fall through to Strategy B/C for better spatial differentiation.
    total_pixels = H * W
    coverage = len(hotspot_cells) / total_pixels if total_pixels > 0 else 0
    if coverage >= 0.9:
        print(f"[WATER] Strategy A skipped: hotspot coverage {coverage:.0%} (field-wide), deferring to B/C", file=sys.stderr)
        return None

    # Build zone grid with NDVI intra-zone modulation for spatial texture
    from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, ndvi_stats
    ndvi_r = get_ndvi_raster(l1, H, W)
    stats = ndvi_stats(ndvi_r, H, W)
    ndvi_mean = stats[0]
    ndvi_rng = stats[2] - stats[1]
    has_ndvi = stats[3] > 0 and ndvi_rng > 0.01

    grid = [[0.0] * W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            if (r, c) in hotspot_cells:
                val = base_prob
                # Add NDVI-based intra-zone modulation (±15%)
                if has_ndvi:
                    ndvi_v = ndvi_r[r][c] if r < len(ndvi_r) and c < len(ndvi_r[r]) else None
                    if ndvi_v is not None:
                        norm = (ndvi_v - ndvi_mean) / ndvi_rng
                        val = base_prob * (1.0 - norm * 0.15)  # Lower NDVI → higher stress
                # No NDVI available: keep uniform zone value (honest)
                # Previously injected ±8% deterministic noise — fabricated spatial texture
                grid[r][c] = round(max(0.0, min(1.0, val)), 4)
            else:
                grid[r][c] = round(base_prob * 0.2, 4)
    return grid


# ============================================================================
# COMPOSITE MOISTURE BUILDER
# ============================================================================

def _build_composite_moisture(
    l1: L1SpatialData, inp: Layer10Input, H: int, W: int
) -> Tuple[Optional[list], list]:
    """
    Build a composite moisture index from all available real moisture rasters.

    Each source is normalized to [0, 1] where 1 = maximum stress.
    Sources are weighted and averaged.

    Returns: (composite_grid or None, list of source names used)
    """
    layers = []  # List of (weight, normalized_grid, source_name)

    # --- Source 1: NDMI (Normalized Difference Moisture Index) ---
    # NDMI directly measures canopy water content: high NDMI = wet, low = dry
    ndmi_raster, ndmi_key = _get_raster(l1, ['ndmi', 'NDMI', 'ndmi_interpolated', 'ndmi_mean'], H, W)
    if ndmi_raster:
        norm = _normalize_raster_to_stress(ndmi_raster, H, W, invert=True)
        layers.append((3.0, norm, "NDMI"))
        logger.info(f"[WATER] NDMI raster found ({ndmi_key}), weight=3.0")

    # --- Source 2: SAR VV backscatter (soil surface moisture proxy) ---
    # Lower VV backscatter in bare/sparse canopy = drier soil
    # Higher VV = wetter soil (in general, for bare/low vegetation)
    sar_raster, sar_key = _get_raster(l1, ['vv', 'VV', 'sar_vv'], H, W)
    if sar_raster:
        # SAR: higher backscatter = wetter soil = LESS stress → invert
        norm = _normalize_raster_to_stress(sar_raster, H, W, invert=True)
        layers.append((2.0, norm, "SAR-VV"))
        logger.info(f"[WATER] SAR VV raster found ({sar_key}), weight=2.0")

    # --- Source 3: IoT soil moisture (ground truth) ---
    # Check for IoT moisture readings that may have been injected into raster_maps
    iot_raster, iot_key = _get_raster(l1, ['soil_moisture', 'moisture', 'moisture_pct'], H, W)
    if iot_raster:
        # Higher moisture = less stress → invert
        norm = _normalize_raster_to_stress(iot_raster, H, W, invert=True)
        layers.append((4.0, norm, "IoT-Moisture"))  # Highest weight: ground truth
        logger.info(f"[WATER] IoT moisture raster found ({iot_key}), weight=4.0")

    # --- Source 4: L4 Soil Water Balance (zone-level Ks) ---
    # Check if we have SWB water_stress_index from L4 via nutrients layer
    swb_grid = _extract_swb_stress(inp, l1, H, W)
    if swb_grid:
        layers.append((2.5, swb_grid, "SWB-Ks"))
        logger.info("[WATER] SWB water_stress_index found, weight=2.5")

    if not layers:
        return None, []

    # --- Weighted composite ---
    composite = [[0.0] * W for _ in range(H)]
    total_weight = sum(w for w, _, _ in layers)

    for r in range(H):
        for c in range(W):
            weighted_sum = 0.0
            pixel_weight = 0.0
            for weight, grid, _ in layers:
                v = grid[r][c]
                if v is not None:
                    weighted_sum += v * weight
                    pixel_weight += weight

            if pixel_weight > 0:
                composite[r][c] = round(weighted_sum / pixel_weight, 4)
            else:
                composite[r][c] = None

    sources_used = [name for _, _, name in layers]
    return composite, sources_used


def _normalize_raster_to_stress(
    raster, H: int, W: int, invert: bool = False
) -> list:
    """
    Normalize a raster to a stress deviation scale centered on 0.5.

    v2: Uses z-score deviation from field mean instead of min-max stretch.
    Min-max forced every field's driest pixel to 1.0 and wettest to 0.0,
    making ALL fields look equally spatially stressed regardless of actual
    moisture conditions. This made the anchor compression problem worse.

    Now: deviation from field mean → scaled to [0, 1] with 0.5 = field average.
    A pixel 1σ drier than the mean → ~0.7 (moderate stress above average).
    A pixel 1σ wetter → ~0.3 (below-average stress).

    If invert=True, higher raw values → LOWER stress (e.g., NDMI, moisture).
    When the raster has no spatial range (uniform), returns 0.5 (indeterminate).
    """
    vals = []
    for r in range(min(H, len(raster))):
        for c in range(min(W, len(raster[r]))):
            v = raster[r][c]
            if v is not None:
                vals.append(v)

    grid = [[None] * W for _ in range(H)]
    if not vals:
        return grid

    mean = sum(vals) / len(vals)
    # Compute standard deviation
    variance = sum((v - mean) ** 2 for v in vals) / len(vals) if len(vals) > 1 else 0.0
    std = variance ** 0.5

    if std < 1e-6:
        # Uniform raster: return 0.5 (neutral/indeterminate stress) for all valid pixels
        for r in range(min(H, len(raster))):
            for c in range(min(W, len(raster[r]))):
                if raster[r][c] is not None:
                    grid[r][c] = 0.5
        return grid

    for r in range(min(H, len(raster))):
        for c in range(min(W, len(raster[r]))):
            v = raster[r][c]
            if v is not None:
                # Z-score: how many σ from the mean
                z = (v - mean) / std
                # Clip to ±2.5σ to prevent outlier domination
                z = max(-2.5, min(2.5, z))
                # Map z-score to [0, 1] centered at 0.5
                # z=-2.5 → 0.0, z=0 → 0.5, z=+2.5 → 1.0
                normalized = 0.5 + z * 0.2  # 0.2 = spread factor per σ
                if invert:
                    normalized = 1.0 - normalized
                grid[r][c] = round(max(0.0, min(1.0, normalized)), 4)
    return grid


def _anchor_to_diagnosis(
    composite_grid: list, base_prob: float, affected_pct: float, H: int, W: int
) -> list:
    """
    Rescale the composite moisture grid so its mean matches the L3 diagnostic
    probability, preserving the spatial variation from real sensors.

    v3: Multiplicative scaling with z-score normalized input.

    The composite grid arrives from _normalize_raster_to_stress which now uses
    z-score normalization (centered at 0.5, spread ±0.2 per σ). This means:
      - comp_mean ≈ 0.5 always
      - No outlier-dominated extremes (clipped at ±2.5σ)
      - Typical pixel range: [0.1, 0.9]

    Multiplicative scaling (target/comp_mean) then proportionally maps:
      - base_prob=0.15: scale=0.3x → range [0.03, 0.27], mean=0.15
      - base_prob=0.50: scale=1.0x → range [0.10, 0.90], mean=0.50
      - base_prob=0.78: scale=1.56x → range [0.16, 1.0], mean=0.78

    This was previously broken with min-max normalization because min-max
    produced full [0, 1] ranges with comp_mean=0.5, and the 0.3x scale
    created values at exactly 0.0 (artificial "zero stress" pixels).
    Z-score normalization avoids this by keeping the tails above ~0.1.
    """
    # Compute current composite mean
    vals = []
    for r in range(H):
        for c in range(W):
            v = composite_grid[r][c]
            if v is not None:
                vals.append(v)

    if not vals:
        return composite_grid

    comp_mean = sum(vals) / len(vals)
    target_mean = base_prob * affected_pct

    # Multiplicative scale factor
    if comp_mean > 1e-6:
        scale = target_mean / comp_mean
    else:
        scale = 1.0

    grid = [[None] * W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            v = composite_grid[r][c]
            if v is not None:
                scaled = v * scale
                grid[r][c] = round(max(0.0, min(1.0, scaled)), 4)

    return grid


def _extract_swb_stress(inp: Layer10Input, l1: L1SpatialData, H: int, W: int):
    """
    Extract Soil Water Balance stress index from L4 nutrients output.
    Returns a zone-rasterized grid if available, else None.
    """
    nutrients = inp.nutrients
    if nutrients is None:
        return None

    # Try to get SWB output from nutrients
    swb = getattr(nutrients, 'soil_water_balance', None)
    if swb is None:
        return None

    wsi = getattr(swb, 'water_stress_index', None)
    if wsi is None or wsi <= 0:
        return None

    # SWB is field-level. Distribute using zone structure if available.
    if l1.zone_masks:
        grid = [[None] * W for _ in range(H)]
        filled = False
        for z_id, cells in l1.zone_masks.items():
            for r, c in cells:
                if r < H and c < W:
                    grid[r][c] = round(float(wsi), 4)
                    filled = True
        if filled:
            return grid

    # Broadcast as uniform if no zone masks
    return [[round(float(wsi), 4)] * W for _ in range(H)]


# ============================================================================
# DROUGHT ACCUMULATION (unchanged)
# ============================================================================

def _compute_spatial_drought(l1: L1SpatialData, H: int, W: int):
    """Compute trailing dry days — spatial if precipitation raster exists."""
    precip_ts = l1.last_values.get('precipitation')
    dry_days = 0

    # Try zone-level precipitation
    if 'precipitation' in l1.zone_timeseries:
        zone_droughts = {}
        for z_id, ts in l1.zone_timeseries['precipitation'].items():
            dd = 0
            for p in reversed(ts):
                if p > 2.0:
                    break
                dd += 1
            zone_droughts[z_id] = float(dd)

        if zone_droughts and l1.zone_masks:
            grid = [[0.0] * W for _ in range(H)]
            for z_id, cells in l1.zone_masks.items():
                dd = zone_droughts.get(z_id, 0.0)
                for r, c in cells:
                    if r < H and c < W:
                        grid[r][c] = dd
            return grid

    # Fallback: spatially modulated using NDVI (low NDVI = more drought exposure)
    from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_by_ndvi
    ndvi_r = get_ndvi_raster(l1, H, W)
    return modulate_by_ndvi(max(float(dry_days), 3.0), ndvi_r, H, W, invert=True, clamp_min=0.0, clamp_max=30.0)


# ============================================================================
# VPD HEAT STRESS (Tetens equation — FAO-56)
# ============================================================================

# Phenology-aware VPD sensitivity multiplier
# During REPRODUCTIVE, stomatal closure causes pollen desiccation and
# irreversible yield loss. The same VPD at SENESCENCE is benign.
_VPD_STAGE_SENSITIVITY = {
    "BARE_SOIL":    0.3,   # Soil evaporation, no crop canopy
    "EMERGENCE":    0.6,   # Young seedlings tolerant
    "VEGETATIVE":   1.0,   # Normal sensitivity
    "REPRODUCTIVE": 1.4,   # Critical: pollen viability at risk
    "SENESCENCE":   0.5,   # Crop hardening, stomata less responsive
    "HARVESTED":    0.0,   # No crop
    "UNKNOWN":      0.8,   # Conservative
}


def _tetens_es(temp_c: float) -> float:
    """Saturation vapor pressure (kPa) using Tetens equation (FAO-56 Eq. 11).

    es = 0.6108 × exp(17.27 × T / (T + 237.3))
    """
    if temp_c is None:
        return 0.0
    return 0.6108 * (2.71828 ** (17.27 * temp_c / (temp_c + 237.3)))


def _compute_vpd_stress(l1, inp, H: int, W: int) -> VPDStressResult:
    """Compute VPD-based stomatal stress surface.

    Returns VPDStressResult containing grid, vpd_kpa, and full provenance receipt.
    """
    last_vals = l1.last_values if l1 else {}
    last_hist = l1.weather_history[-1] if (l1 and l1.weather_history) else {}

    temp_max_raw = _first_not_none(
        last_vals.get('temperature_max'), last_vals.get('temp_max'),
        last_hist.get('temperature_max'), last_hist.get('temp_max'), last_hist.get('temperature_2m_max')
    )
    temp_min_raw = _first_not_none(
        last_vals.get('temperature_min'), last_vals.get('temp_min'),
        last_hist.get('temperature_min'), last_hist.get('temp_min'), last_hist.get('temperature_2m_min')
    )
    humidity_raw = _first_not_none(
        last_vals.get('humidity'), last_vals.get('relative_humidity'),
        last_hist.get('humidity'), last_hist.get('relative_humidity'), last_hist.get('relative_humidity_2m')
    )

    if temp_max_raw is None:
        return VPDStressResult(
            grid=None,
            vpd_kpa=None,
            computed_stress_probability=0.0,
            phenology_stage="UNKNOWN",
            stage_sensitivity=0.8,
            crop_applicability="unknown_stage",
            humidity_value=None,
            humidity_source="unknown",
            temp_max_value=None,
            temp_max_source="unknown",
            temp_min_value=None,
            temp_min_source="unknown",
            physiological_claim_allowed=False,
        )

    temp_max = float(temp_max_raw)
    temp_max_source = "provider_current" if (last_vals.get('temperature_max') is not None or last_vals.get('temp_max') is not None) else "provider_archive"

    if temp_min_raw is not None:
        temp_min = float(temp_min_raw)
        temp_min_source = "provider_current" if (last_vals.get('temperature_min') is not None or last_vals.get('temp_min') is not None) else "provider_archive"
    else:
        temp_min = temp_max - 10.0
        temp_min_source = "imputed_delta"

    if humidity_raw is not None:
        humidity = float(humidity_raw)
        humidity_source = "provider_current" if (last_vals.get('humidity') is not None or last_vals.get('relative_humidity') is not None) else "provider_archive"
    else:
        humidity = 50.0
        humidity_source = "imputed_default"

    # Tetens equation
    es_max = _tetens_es(temp_max)
    es_min = _tetens_es(temp_min)
    es_mean = (es_max + es_min) / 2.0

    # Actual vapor pressure from humidity and Tmin
    ea = es_min * (humidity / 100.0)

    # VPD in kPa
    vpd = max(0.0, es_mean - ea)

    # Get phenology stage sensitivity
    stage = consume_canonical_phenology_output(
        inp.veg_int if inp else None
    )["resolved_crop_stage"]

    sensitivity = _VPD_STAGE_SENSITIVITY.get(stage, 0.8)

    # Map VPD to stress probability with stage sensitivity
    if vpd < 0.8:
        base_stress = 0.0
    elif vpd < 2.0:
        base_stress = (vpd - 0.8) / 1.2 * 0.3
    elif vpd < 3.5:
        base_stress = 0.3 + (vpd - 2.0) / 1.5 * 0.4
    else:
        base_stress = min(1.0, 0.7 + (vpd - 3.5) / 2.0 * 0.3)

    # Apply phenology sensitivity
    stress = min(1.0, base_stress * sensitivity)

    crop_applicability = "applicable"
    if stage == "BARE_SOIL":
        crop_applicability = "bare_soil"
    elif stage in ("UNKNOWN", "HARVESTED"):
        crop_applicability = "unknown_stage"

    physiological_claim_allowed = (
        humidity_source != "imputed_default"
        and temp_min_source != "imputed_delta"
        and crop_applicability == "applicable"
    )

    if stress < 0.01:
        return VPDStressResult(
            grid=None,
            vpd_kpa=vpd,
            computed_stress_probability=stress,
            phenology_stage=stage,
            stage_sensitivity=sensitivity,
            crop_applicability=crop_applicability,
            humidity_value=humidity,
            humidity_source=humidity_source,
            temp_max_value=temp_max,
            temp_max_source=temp_max_source,
            temp_min_value=temp_min,
            temp_min_source=temp_min_source,
            physiological_claim_allowed=physiological_claim_allowed,
        )

    # Spatial modulation: NDVI inversely correlates with VPD impact
    from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, ndvi_stats
    ndvi_r = get_ndvi_raster(l1, H, W)
    mean, mn, mx, valid = ndvi_stats(ndvi_r, H, W)
    rng = mx - mn

    grid = [[round(stress, 4)] * W for _ in range(H)]

    if valid > 0 and rng > 0.01:
        for r in range(H):
            for c in range(W):
                v = ndvi_r[r][c] if r < len(ndvi_r) and c < len(ndvi_r[r]) else None
                if v is not None:
                    norm = (v - mean) / rng
                    modulated = stress * (1.0 + norm * 0.25)
                    grid[r][c] = round(max(0.0, min(1.0, modulated)), 4)

    print(f"[WATER] VPD: {vpd:.2f} kPa, stage={stage}, sensitivity={sensitivity:.1f}, stress={stress:.3f}", file=sys.stderr)
    return VPDStressResult(
        grid=grid,
        vpd_kpa=vpd,
        computed_stress_probability=stress,
        phenology_stage=stage,
        stage_sensitivity=sensitivity,
        crop_applicability=crop_applicability,
        humidity_value=humidity,
        humidity_source=humidity_source,
        temp_max_value=temp_max,
        temp_max_source=temp_max_source,
        temp_min_value=temp_min,
        temp_min_source=temp_min_source,
        physiological_claim_allowed=physiological_claim_allowed,
    )
