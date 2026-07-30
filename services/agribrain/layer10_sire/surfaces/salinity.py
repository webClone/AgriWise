"""
Salinity Surface Engine — Multi-Source Spatial Soil Salinity Stress
====================================================================

Generates the SALINITY_STRESS surface using available salinity indicators
rather than fabricated assumptions.

Data source priority cascade:
  1. L3 Salinity Diagnosis (probability from Decision Engine)
  2. L1 Soil EC (Electrical Conductivity) raster — direct salinity measure
  3. L1 Soil pH raster — alkalinity proxy (pH > 8.5 → sodic soils)
  4. L0 FAO Soil Category — static regional classification
  5. NDVI spatial modulation of L3 diagnostic (last resort)

The L3 diagnostic probability anchors the field-level mean;
spatial sources distribute that probability across pixels.

Salinity stress mapping (EC-based, FAO-56 reference):
  EC < 2 dS/m  : No stress (most crops tolerant)
  EC 2-4 dS/m  : Mild stress (yield reduction begins for sensitive crops)
  EC 4-8 dS/m  : Moderate stress (significant yield loss)
  EC > 8 dS/m  : Severe stress (only tolerant crops survive)
"""
import logging
import sys
from typing import List, Optional, Tuple
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId, GroundingClass,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.layer10_sire.adapters.l3_adapter import L3DiagnosticData

logger = logging.getLogger(__name__)


def generate_salinity_surfaces(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
    l3_data: Optional[L3DiagnosticData] = None,
) -> List[SurfaceArtifact]:
    """Generate salinity stress surface from L1/L3 adapter data (multi-source spatial)."""
    surfaces = []
    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)
    if l3_data is None:
        from services.agribrain.layer10_sire.adapters.l3_adapter import adapt_l3
        l3_data = adapt_l3(inp.decision)

    if not _has_salinity_specific_evidence(inp, l1_data, l3_data, H, W):
        logger.warning("SALINITY_STRESS unavailable: no salinity-specific evidence")
        return []

    # --- 1. SALINITY_STRESS — multi-source spatial ---
    stress_grid, grounding, source_layers, provenance = _compute_spatial_salinity(
        inp, l1_data, l3_data, H, W
    )
    surfaces.append(SurfaceArtifact(
        surface_id=f"SALINITY_{inp.plot_id}",
        semantic_type=SurfaceType.SALINITY_STRESS,
        grid_ref=f"{H}x{W}",
        values=stress_grid,
        units="probability",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.SALINITY_TEAL,
        source_layers=source_layers,
        grounding_class=grounding,
        provenance=provenance,
    ))

    return surfaces


def _has_salinity_specific_evidence(inp, l1, l3, H, W) -> bool:
    direct, _ = _get_raster(l1, ["ec", "EC", "soil_ec", "electrical_conductivity", "ec_dsm"], H, W)
    if direct is not None:
        return True
    if _extract_fao_salinity(inp) is not None:
        return True
    for diagnosis in l3.diagnoses:
        pid = str(diagnosis.get("problem_id", "")).upper()
        drivers = " ".join(str(v) for v in diagnosis.get("drivers_used", [])).upper()
        if any(key in pid for key in ("SALINITY", "SALINE", "SODIC", "EC_HIGH")) and any(
            key in drivers for key in ("SALINITY", "SWIR", "ELECTRICAL_CONDUCTIVITY", "SOIL_EC", "WATER_QUALITY")
        ):
            return True
    return False


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


# ============================================================================
# CORE: MULTI-SOURCE SPATIAL SALINITY STRESS
# ============================================================================

def _compute_spatial_salinity(
    inp: Layer10Input,
    l1: L1SpatialData,
    l3: L3DiagnosticData,
    H: int, W: int
) -> Tuple[list, str, list, dict]:
    """
    Compute the SALINITY_STRESS surface using available salinity indicators.

    Priority cascade:
      1. L3 Salinity Diagnosis → probability anchor
      2. L1 EC raster → direct spatial salinity
      3. L1 pH raster → alkalinity/sodicity proxy
      4. FAO soil category → static classification
      5. NDVI-modulated L3 probability → spatial fallback

    Returns: (grid, grounding_class, source_layers, provenance)
    """
    # --- Step 1: Extract L3 salinity diagnosis (field-level anchor) ---
    base_prob, affected_pct = _extract_l3_salinity_diagnosis(l3)
    print(f"[SALINITY] L3 anchor: base_prob={base_prob:.4f}, affected_pct={affected_pct:.2f}", file=sys.stderr)

    provenance = {
        "method": "MULTI_SOURCE_CASCADE",
        "l3_base_prob": round(base_prob, 4),
        "l3_affected_pct": round(affected_pct, 2),
    }

    # --- Step 2: Try EC raster (best direct indicator) ---
    ec_raster, ec_key = _get_raster(
        l1, ['ec', 'EC', 'soil_ec', 'electrical_conductivity', 'ec_dsm'], H, W
    )
    if ec_raster:
        grid = _ec_to_stress_grid(ec_raster, base_prob, H, W)
        print(f"[SALINITY] Strategy A: EC raster ({ec_key})", file=sys.stderr)
        provenance["strategy"] = "EC_RASTER"
        provenance["ec_key"] = ec_key
        _log_grid_stats("[SALINITY]", grid, H, W)
        return grid, GroundingClass.RASTER_GROUNDED.value, ["L1", "L3"], provenance

    # --- Step 3: Try pH raster (sodicity proxy) ---
    ph_raster, ph_key = _get_raster(
        l1, ['ph', 'pH', 'soil_ph', 'ph_water'], H, W
    )
    if ph_raster:
        grid = _ph_to_stress_grid(ph_raster, base_prob, H, W)
        print(f"[SALINITY] Strategy B: pH raster ({ph_key})", file=sys.stderr)
        provenance["strategy"] = "PH_RASTER"
        provenance["ph_key"] = ph_key
        _log_grid_stats("[SALINITY]", grid, H, W)
        return grid, GroundingClass.RASTER_GROUNDED.value, ["L1", "L3"], provenance

    # --- Step 4: Try FAO soil salinity category from static metadata ---
    fao_stress = _extract_fao_salinity(inp)
    if fao_stress is not None:
        # Use FAO as uniform anchor, override L3 if more severe
        effective_prob = max(base_prob, fao_stress)
        from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_by_ndvi
        ndvi_r = get_ndvi_raster(l1, H, W)
        grid = modulate_by_ndvi(effective_prob, ndvi_r, H, W, invert=True, clamp_min=0.0, clamp_max=1.0)
        print(f"[SALINITY] Strategy C: FAO category (fao_stress={fao_stress:.3f}, effective={effective_prob:.3f})", file=sys.stderr)
        provenance["strategy"] = "FAO_CATEGORY"
        provenance["fao_stress"] = round(fao_stress, 3)
        _log_grid_stats("[SALINITY]", grid, H, W)
        return grid, GroundingClass.PROXY_SPATIAL.value, ["L1", "L3", "FAO"], provenance

    # --- Step 5: NDVI-modulated L3 diagnostic fallback ---
    # Use NDVI only for spatial distribution (low NDVI areas are more affected),
    # keeping absolute level anchored to L3 diagnosis probability.
    print("[SALINITY] Strategy D: L3-anchored NDVI modulation (no EC/pH/FAO data)", file=sys.stderr)
    provenance["strategy"] = "L3_NDVI_FALLBACK"

    from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, ndvi_stats
    ndvi_r = get_ndvi_raster(l1, H, W)
    mean, mn, mx, valid_count = ndvi_stats(ndvi_r, H, W)
    rng = mx - mn

    grid = [[round(base_prob, 4)] * W for _ in range(H)]

    if valid_count > 0 and rng > 0.01:
        # Distribute spatially: low NDVI gets slightly more salinity stress
        # Cap modulation at ±20% of base_prob — NDVI is only a spatial proxy
        for r in range(H):
            for c in range(W):
                v = ndvi_r[r][c] if r < len(ndvi_r) and c < len(ndvi_r[r]) else None
                if v is not None:
                    norm = (v - mean) / rng  # [-1, +1]
                    # Invert: low NDVI → higher salinity stress
                    modulated = base_prob * (1.0 - norm * 0.20)
                    grid[r][c] = round(max(0.0, min(1.0, modulated)), 4)

    _log_grid_stats("[SALINITY]", grid, H, W)
    return grid, GroundingClass.PROXY_SPATIAL.value, ["L1", "L3"], provenance


# ============================================================================
# DIAGNOSIS EXTRACTION
# ============================================================================

def _extract_l3_salinity_diagnosis(l3: L3DiagnosticData) -> Tuple[float, float]:
    """Extract salinity stress probability from L3 diagnoses.

    Looks for problem_ids containing 'SALINITY', 'SALT', 'SODIC', 'SALINE'.
    Returns (probability, affected_area_fraction).
    """
    best_prob = 0.0
    best_affected = 1.0

    for dx in l3.diagnoses:
        pid = dx.get('problem_id', '') if isinstance(dx, dict) else getattr(dx, 'problem_id', '')
        pid_upper = pid.upper()

        if any(kw in pid_upper for kw in ('SALINITY', 'SALT', 'SODIC', 'SALINE', 'EC_HIGH')):
            prob = dx.get('probability', 0.0) if isinstance(dx, dict) else getattr(dx, 'probability', 0.0)
            if prob > best_prob:
                best_prob = prob
                best_affected = (
                    (dx.get('affected_area_pct', 100.0) if isinstance(dx, dict)
                     else getattr(dx, 'affected_area_pct', 100.0)) / 100.0
                )

    return best_prob, best_affected


# ============================================================================
# EC → STRESS MAPPING (FAO-56 compliant)
# ============================================================================

def _ec_to_stress_grid(
    ec_raster, base_prob: float, H: int, W: int
) -> list:
    """Convert EC raster (dS/m) to salinity stress probability [0, 1].

    Mapping (FAO Irrigation & Drainage Paper 29, Ayers & Westcot 1985):
      EC < 2.0 dS/m  → stress = 0.0  (no restriction)
      EC 2.0–4.0     → stress = 0.0–0.30  (slight to moderate)
      EC 4.0–8.0     → stress = 0.30–0.70  (moderate to severe)
      EC > 8.0       → stress = 0.70–1.0  (severe)

    The L3 diagnostic probability acts as a floor: if L3 says salinity
    is 0.60 probable but EC readings are low, the higher signal wins
    per pixel.
    """
    grid = [[None] * W for _ in range(H)]

    for r in range(min(H, len(ec_raster))):
        for c in range(min(W, len(ec_raster[r]))):
            ec_val = ec_raster[r][c]
            if ec_val is None:
                grid[r][c] = round(base_prob, 4)
                continue

            ec_val = float(ec_val)
            if ec_val < 2.0:
                stress = 0.0
            elif ec_val < 4.0:
                stress = (ec_val - 2.0) / 2.0 * 0.30  # 0.0 → 0.30
            elif ec_val < 8.0:
                stress = 0.30 + (ec_val - 4.0) / 4.0 * 0.40  # 0.30 → 0.70
            else:
                stress = min(1.0, 0.70 + (ec_val - 8.0) / 8.0 * 0.30)  # 0.70 → 1.0

            # Use the higher of EC-derived or L3 diagnostic
            grid[r][c] = round(max(stress, base_prob * 0.5), 4)

    return grid


# ============================================================================
# pH → STRESS MAPPING (Sodicity proxy)
# ============================================================================

def _ph_to_stress_grid(
    ph_raster, base_prob: float, H: int, W: int
) -> list:
    """Convert pH raster to salinity/sodicity stress probability [0, 1].

    Mapping:
      pH < 7.5       → stress = 0.0  (normal/acidic — not saline)
      pH 7.5–8.5     → stress = 0.0–0.30  (mildly alkaline)
      pH 8.5–9.5     → stress = 0.30–0.70  (sodic conditions likely)
      pH > 9.5       → stress = 0.70–1.0  (strongly sodic)

    pH is an indirect indicator: high pH correlates with sodium accumulation
    (sodicity) which co-occurs with salinity in many arid/semi-arid soils.
    """
    grid = [[None] * W for _ in range(H)]

    for r in range(min(H, len(ph_raster))):
        for c in range(min(W, len(ph_raster[r]))):
            ph_val = ph_raster[r][c]
            if ph_val is None:
                grid[r][c] = round(base_prob, 4)
                continue

            ph_val = float(ph_val)
            if ph_val < 7.5:
                stress = 0.0
            elif ph_val < 8.5:
                stress = (ph_val - 7.5) / 1.0 * 0.30  # 0.0 → 0.30
            elif ph_val < 9.5:
                stress = 0.30 + (ph_val - 8.5) / 1.0 * 0.40  # 0.30 → 0.70
            else:
                stress = min(1.0, 0.70 + (ph_val - 9.5) / 1.0 * 0.30)  # 0.70 → 1.0

            grid[r][c] = round(max(stress, base_prob * 0.5), 4)

    return grid


# ============================================================================
# FAO SOIL CLASSIFICATION EXTRACTION
# ============================================================================

def _extract_fao_salinity(inp: Layer10Input) -> Optional[float]:
    """Extract salinity stress from FAO soil classification in field metadata.

    Checks field_tensor.static for soil class / FAO category indicators.
    FAO categories mapped to stress probability:
      'non_saline'      → 0.05
      'slightly_saline'  → 0.25
      'moderately_saline' → 0.50
      'highly_saline'    → 0.75
      'very_highly_saline' → 0.90

    Returns stress probability or None if no FAO data available.
    """
    FAO_MAP = {
        'non_saline': 0.05,
        'slightly_saline': 0.25,
        'moderately_saline': 0.50,
        'highly_saline': 0.75,
        'very_highly_saline': 0.90,
        'saline': 0.50,
        'sodic': 0.60,
        'saline_sodic': 0.70,
    }

    ft = inp.field_tensor
    if ft is None:
        return None

    static = getattr(ft, 'static', {}) or {}

    # Check various possible metadata keys
    for key in ('soil_salinity_class', 'fao_soil_class', 'salinity_category',
                'soil_class', 'salinity_level'):
        val = static.get(key)
        if val and isinstance(val, str):
            normalized = val.lower().strip().replace(' ', '_').replace('-', '_')
            stress = FAO_MAP.get(normalized)
            if stress is not None:
                print(f"[SALINITY] FAO category found: {key}={val} → stress={stress}", file=sys.stderr)
                return stress

    return None


# ============================================================================
# LOGGING HELPER
# ============================================================================

def _log_grid_stats(prefix: str, grid: list, H: int, W: int):
    """Log grid statistics for debugging."""
    vals = [v for row in grid for v in row if v is not None]
    if vals:
        print(
            f"{prefix} Output grid: mean={sum(vals)/len(vals):.4f}, "
            f"min={min(vals):.4f}, max={max(vals):.4f}, "
            f"unique={len(set(round(v, 4) for v in vals))}",
            file=sys.stderr,
        )
