import numpy as np
from typing import List, Any, Dict
from dataclasses import dataclass
from services.agribrain.layer10_sire.schema import SurfaceArtifact, SurfaceType, PaletteId, GroundingClass

@dataclass
class WeightedFeature:
    values: np.ndarray | None
    effective_weight: float
    status: str
    source_kind: str

def box_blur(arr: np.ndarray) -> np.ndarray:
    padded = np.pad(arr, 1, mode='edge')
    sh = np.zeros_like(arr)
    for dr in (0, 1, 2):
        for dc in (0, 1, 2):
            sh += padded[dr:dr+arr.shape[0], dc:dc+arr.shape[1]]
    return sh / 9.0

def highpass(arr: np.ndarray) -> np.ndarray:
    blurred = box_blur(arr)
    hp = arr - blurred
    return np.where(np.isnan(hp), 0.0, hp)

def spatial_gradient(arr: np.ndarray) -> np.ndarray:
    padded = np.pad(arr, 1, mode='edge')
    h, w = arr.shape
    dx = padded[1:h+1, 2:w+2] - padded[1:h+1, 0:w]
    dy = padded[2:h+2, 1:w+1] - padded[0:h, 1:w+1]
    grad = np.sqrt(dx*dx + dy*dy)
    return np.where(np.isnan(grad), 0.0, grad)

def find_grid(H: int, W: int, *sources) -> np.ndarray:
    for src in sources:
        if src is None:
            continue
        grid = None
        if isinstance(src, dict):
            grid = src.get("values") or src.get("pixel_array")
        elif hasattr(src, "values"):
            grid = src.values
            if callable(grid):
                try:
                    grid = grid()
                except Exception:
                    grid = None
        else:
            grid = src
            
        if grid is None:
            continue
            
        try:
            arr = np.asarray(grid, dtype=np.float32)
            if arr.ndim != 2 or arr.shape != (H, W):
                continue
            if np.all(np.isnan(arr)):
                continue
            return arr
        except Exception:
            continue
    return None

def find_grid_any_shape(*sources) -> np.ndarray:
    for src in sources:
        if src is None:
            continue
        grid = None
        if isinstance(src, dict):
            grid = src.get("values") or src.get("pixel_array")
        elif hasattr(src, "values"):
            grid = src.values
            if callable(grid):
                try:
                    grid = grid()
                except Exception:
                    grid = None
        else:
            grid = src
            
        if grid is None:
            continue
            
        try:
            arr = np.asarray(grid, dtype=np.float32)
            if arr.ndim != 2:
                continue
            if np.all(np.isnan(arr)):
                continue
            return arr
        except Exception:
            continue
    return None

def resample_grid(arr: np.ndarray, target_H: int, target_W: int, method: str = 'bilinear') -> np.ndarray:
    if arr.shape == (target_H, target_W):
        return arr
    old_h, old_w = arr.shape
    if method == 'nearest':
        ys = np.clip(np.round((np.arange(target_H) + 0.5) * old_h / target_H - 0.5).astype(int), 0, old_h - 1)
        xs = np.clip(np.round((np.arange(target_W) + 0.5) * old_w / target_W - 0.5).astype(int), 0, old_w - 1)
        return arr[np.ix_(ys, xs)]
    else:
        # Bilinear
        ys = (np.arange(target_H, dtype=float) + 0.5) * old_h / target_H - 0.5
        xs = (np.arange(target_W, dtype=float) + 0.5) * old_w / target_W - 0.5
        y0 = np.clip(np.floor(ys).astype(int), 0, old_h - 1)
        y1 = np.clip(y0 + 1, 0, old_h - 1)
        x0 = np.clip(np.floor(xs).astype(int), 0, old_w - 1)
        x1 = np.clip(x0 + 1, 0, old_w - 1)
        wy = np.clip(ys - y0, 0.0, 1.0)[:, np.newaxis]
        wx = np.clip(xs - x0, 0.0, 1.0)[np.newaxis, :]
        result = (arr[np.ix_(y0, x0)] * (1 - wy) * (1 - wx) +
                  arr[np.ix_(y0, x1)] * (1 - wy) * wx +
                  arr[np.ix_(y1, x0)] * wy * (1 - wx) +
                  arr[np.ix_(y1, x1)] * wy * wx)
        nan_mask = np.isnan(result)
        if np.any(nan_mask):
            ny = np.clip(np.round(ys).astype(int), 0, old_h - 1)
            nx = np.clip(np.round(xs).astype(int), 0, old_w - 1)
            result[nan_mask] = arr[np.ix_(ny, nx)][nan_mask]
        return result

def generate_asmae_composite_surfaces(
    l10_input: Any,
    H: int,
    W: int,
    base_surfaces: List[Any] = None,
    l1_data: Any = None,
    asmae_evidence_state: Dict[str, Any] = None,
) -> List[SurfaceArtifact]:
    """
    Generates composite advisory surfaces from feature bus.

    BC.10.13 P6 changes:
    - bus.available=False → return [] (no fabricated surfaces).
    - Per-feature weight-gated formula: unavailable features contribute 0;
      remaining weights are renormalized so they still sum to 1.
    - support_status reads feature_status[key]["status"] (per-feature dict).
    - Provenance status reads feat dict, not bare string.
    - observed_ratio constant fallback removed; if absent, archive_support
      weight is reduced proportionally.
    - All formula sub-expressions None-guard before numpy ops.
    """
    from services.agribrain.layer10_sire.surfaces.grid_access import (
        extract_surface_grid, resample_to, finite_ratio, nanstd_safe,
        entropy_score, extract_named_grid,
    )
    from services.agribrain.layer10_sire.adapters.asmae_feature_bus import (
        build_asmae_feature_bus, normalize_01, robust_zscore,
        box_blur, box_blur_k, local_variance, spatial_gradient, directional_coherence,
    )

    base_surfaces_dict = {}
    if base_surfaces:
        for s in base_surfaces:
            stype = getattr(s, "semantic_type", None)
            stype_val = getattr(stype, "value", str(stype))
            base_surfaces_dict[stype_val] = s

    # Determine high-res target shape ( satellite-only )
    target_shape = (H, W)
    target_resolution_m = 10.0
    for name in [
        "NDVI_CLEAN",
        "NDVI",
    ]:
        surf = base_surfaces_dict.get(name)
        if surf and surf.values and isinstance(surf.values, list) and len(surf.values) > 0 and isinstance(surf.values[0], list):
            target_shape = (len(surf.values), len(surf.values[0]))
            target_resolution_m = getattr(surf, 'native_resolution_m', 10.0)
            break
    target_H, target_W = target_shape

    bus = build_asmae_feature_bus(
        H=target_H,
        W=target_W,
        base_surfaces=base_surfaces,
        l10_input=l10_input,
        l1_data=l1_data,
        asmae_evidence_state=asmae_evidence_state,
    )

    # ── BC.10.13 P6: hard gate — no spatial signal → no surfaces ─────────────
    if not bus.available:
        return []

    state = bus.state
    authority = bus.authority
    source_reality = bus.source_reality
    real_ev = (state == "full_scene_stack")

    selected_source_name = "none"
    for name in [
        "NDVI_CLEAN",
        "NDVI",
    ]:
        if base_surfaces_dict.get(name) is not None:
            selected_source_name = name
            break

    # If only experimental sources exist, do not emit any composite rasters
    if selected_source_name == "none":
        return []

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _feat_weight(key: str) -> float:
        """Return the downstream weight for a bus feature (0.0 if unavailable)."""
        entry = bus.feature_status.get(key)
        if isinstance(entry, dict):
            return float(entry.get("weight", 0.0))
        return 0.0

    def _feat_status(key: str) -> str:
        """Return status string from per-feature dict."""
        entry = bus.feature_status.get(key)
        if isinstance(entry, dict):
            return entry.get("status", "unavailable")
        if isinstance(entry, str):
            return entry
        return "unavailable"

    def _feat_source_kind(key: str) -> str:
        """Return source kind from per-feature dict."""
        entry = bus.feature_status.get(key)
        if isinstance(entry, dict):
            return entry.get("source_kind", entry.get("source", "unavailable"))
        return "unavailable"

    MIN_CANOPY_WEIGHT = 0.30

    def feature_with_weight(key: str, nominal_weight: float, shape, arr=None) -> WeightedFeature:
        """Returns a structured WeightedFeature.
        If status is 'unavailable' or effective_weight <= 0.0, weight is set to 0.0."""
        if arr is None:
            arr = getattr(bus, key, None)
            if key == "lai" and arr is not None:
                arr = arr / 8.0
        status = _feat_status(key)
        source_kind = _feat_source_kind(key)

        if key == "gapfill":
            status = "real"
            source_kind = "gap_fill_mask"
            feat_w = 1.0
        elif key == "observed_ratio":
            status = "real" if arr is not None else "unavailable"
            source_kind = "observed_ratio"
            feat_w = 1.0 if arr is not None else 0.0
        else:
            feat_w = _feat_weight(key)

        if arr is not None and status != "unavailable" and feat_w != 0.0:
            return WeightedFeature(values=arr, effective_weight=nominal_weight * feat_w, status=status, source_kind=source_kind)
        return WeightedFeature(values=np.zeros(shape, dtype=np.float32), effective_weight=0.0, status="unavailable", source_kind="unavailable")

    zeros = np.zeros((target_H, target_W), dtype=np.float32)

    # ── valid_mask from vigor (which is guaranteed non-None when bus.available) ──
    vigor_arr = bus.vigor  # will not be None when bus.available=True
    valid_mask = ~np.isnan(vigor_arr)

    # ── observed_ratio — only from real data ─────────────────────────────────
    # BC.10.13 P6: no constant fallback. If absent, weight goes to 0.
    observed_ratio_raw = extract_named_grid("OBSERVED_RATIO", base_surfaces, l10_input, l1_data)
    observed_ratio = None
    if observed_ratio_raw is not None:
        observed_ratio = resample_to(
            np.asarray(observed_ratio_raw, dtype=np.float32), (target_H, target_W), method="bilinear"
        )
        observed_ratio = np.where(np.isnan(observed_ratio), 0.0, observed_ratio)

    gapfill_raw = extract_named_grid("GAP_FILL_MASK", base_surfaces, l10_input, l1_data)
    if gapfill_raw is None:
        gapfill_arr = np.where(valid_mask, 0.0, 1.0)
    else:
        gapfill_arr = resample_to(
            np.asarray(gapfill_raw, dtype=np.float32), (target_H, target_W), method="nearest"
        )

    # ── P6: Per-feature weight-gated canopy formula ───────────────────────────
    _pv_spec = [
        ("vigor",          0.26, False),
        ("chlorophyll",    0.16, False),
        ("lai",            0.14, False),
        ("canopy_water",   0.12, False),
        ("root_zone_water",0.10, False),
        ("structure",      0.08, False),
        ("salinity",      -0.08, True),   # penalty term
        ("thermal",       -0.06, True),   # penalty term
    ]

    _pv_weighted_features = {
        key: feature_with_weight(key, nominal_w, (target_H, target_W))
        for key, nominal_w, _ in _pv_spec
    }

    physio_accum = np.zeros((target_H, target_W), dtype=np.float32)
    norm_factor = 0.0
    physio_total_pos_w = 0.0
    physio_total_neg_w = 0.0

    for key, nominal_w, is_penalty in _pv_spec:
        feat = _pv_weighted_features[key]
        if feat.effective_weight != 0.0 and feat.values is not None:
            abs_eff_w = abs(feat.effective_weight)
            norm_factor += abs_eff_w

            if is_penalty:
                # Explicit penalty inversion: contribution = abs_eff_w * (1.0 - values)
                contribution = abs_eff_w * (1.0 - feat.values)
                physio_total_neg_w += abs_eff_w
            else:
                contribution = feat.effective_weight * feat.values
                physio_total_pos_w += feat.effective_weight

            physio_accum += contribution

    # MIN_CANOPY_WEIGHT gate: total active nominal weights * feat weights must be at least 0.30
    if norm_factor < MIN_CANOPY_WEIGHT:
        return []

    physio_vigor = np.clip(physio_accum / norm_factor, 0.0, 1.0)

    # stress_penalty — weight-gated
    _sp_spec = [
        ("bma_disagreement",  0.20, bus.bma_disagreement),
        ("uncertainty",       0.20, bus.uncertainty),
        ("cross_layer_conflict", 0.20, bus.cross_layer_conflict),
        ("bare_soil",         0.15, bus.bare_soil),
        ("biotic_risk",       0.15, bus.biotic_risk),
        ("gapfill",           0.10, gapfill_arr),
    ]
    _sp_weighted_features = {
        key: feature_with_weight(key, nominal_w, (target_H, target_W), arr=arr)
        for key, nominal_w, arr in _sp_spec
    }

    sp_accum = np.zeros((target_H, target_W), dtype=np.float32)
    sp_total_w = 0.0
    for key, _, _ in _sp_spec:
        feat = _sp_weighted_features[key]
        if feat.effective_weight > 0.0 and feat.values is not None:
            sp_accum += feat.effective_weight * feat.values
            sp_total_w += feat.effective_weight
    stress_penalty = np.clip(sp_accum / max(sp_total_w, 0.01), 0.0, 1.0) if sp_total_w > 0.0 else zeros

    # support_gate — weight-gated
    _sg_spec = [
        ("confidence",     0.20, bus.confidence),
        ("retro_score",    0.18, bus.retro_score),
        ("archive_support",0.18, bus.archive_support),
        ("ml_support",     0.16, bus.ml_support),
        ("causal_support", 0.14, bus.causal_support),
        ("observed_ratio", 0.14, observed_ratio),
    ]
    _sg_weighted_features = {
        key: feature_with_weight(key, nominal_w, (target_H, target_W), arr=arr)
        for key, nominal_w, arr in _sg_spec
    }

    sg_accum = np.zeros((target_H, target_W), dtype=np.float32)
    sg_total_w = 0.0
    for key, _, _ in _sg_spec:
        feat = _sg_weighted_features[key]
        if feat.effective_weight > 0.0 and feat.values is not None:
            sg_accum += feat.effective_weight * feat.values
            sg_total_w += feat.effective_weight
    support_gate = np.clip(sg_accum / max(sg_total_w, 0.01), 0.0, 1.0) if sg_total_w > 0.0 else zeros

    # texture_detail — falls back to zeros when vigor lacks spatial variation
    if np.nanstd(vigor_arr) <= 0.01:
        texture_detail = zeros
    else:
        row_coherence = directional_coherence(vigor_arr)
        local_gradient = normalize_01(spatial_gradient(vigor_arr))
        highpass_vigor = highpass(vigor_arr)
        struct_feat = feature_with_weight("structure", 1.0, (target_H, target_W))
        boundary_residual = highpass(struct_feat.values) if struct_feat.effective_weight > 0.0 else zeros
        texture_detail = (
            0.35 * row_coherence
            + 0.25 * local_gradient
            + 0.20 * highpass_vigor
            + 0.20 * boundary_residual
        )
        texture_detail = robust_zscore(texture_detail)
        texture_detail = np.clip(texture_detail, -1.0, 1.0)

    canopy_arr = np.clip(
        physio_vigor
        - 0.30 * stress_penalty
        + 0.18 * support_gate * texture_detail,
        0.0, 1.0,
    )

    # Strictly reject flat canopy advisory surfaces
    if np.nanstd(canopy_arr) <= 0.01:
        return []

    # ── Other ASMAE Advisory Surfaces ────────────────────────────────────────
    vigor_arr = bus.vigor

    # ── Other ASMAE Advisory Surfaces ────────────────────────────────────────
    struct_feat = feature_with_weight("structure", 1.0, (target_H, target_W))
    vigor_feat = feature_with_weight("vigor", 1.0, (target_H, target_W))

    if vigor_feat.effective_weight > 0.0 and vigor_feat.values is not None:
        struct_contrib = struct_feat.values if struct_feat.effective_weight > 0.0 else zeros
        veg_att_arr = np.clip(
            np.abs(vigor_feat.values - 0.5) * (1.0 + 0.1 * struct_contrib), 0.0, 1.0
        )
    else:
        veg_att_arr = zeros

    # water_arr: 0.55 * cw + 0.20 * struct + 0.15 * arch - 0.10 * (1.0 - vigor)
    MIN_WATER_WEIGHT = 0.30
    _wa_spec = [
        ("canopy_water",   0.55, False),
        ("structure",      0.20, False),
        ("archive_support",0.15, False),
        ("vigor",         -0.10, True),
    ]
    wa_accum = np.zeros((target_H, target_W), dtype=np.float32)
    wa_total_w = 0.0
    for key, nominal_w, is_neg in _wa_spec:
        feat = feature_with_weight(key, nominal_w, (target_H, target_W))
        if feat.effective_weight != 0.0 and feat.values is not None:
            abs_w = abs(feat.effective_weight)
            if is_neg:
                contribution = -abs_w * (1.0 - feat.values)
                wa_accum += contribution
            else:
                wa_accum += feat.effective_weight * feat.values
            wa_total_w += abs_w
    has_water_evidence = (
        _feat_status("canopy_water") != "unavailable" or 
        _feat_status("root_zone_water") != "unavailable" or 
        _feat_status("weather_water_balance") != "unavailable" or 
        _feat_status("daily_precip") != "unavailable"
    )
    if wa_total_w < MIN_WATER_WEIGHT or not has_water_evidence:
        water_arr = None
    else:
        water_arr = np.clip(wa_accum / max(wa_total_w, 0.01), 0.0, 1.0) if wa_total_w > 0.0 else zeros

    var_ndvi = local_variance(vigor_arr, k=5)
    texture_uniformity = np.clip(1.0 - robust_zscore(var_ndvi), 0.0, 1.0)

    # nutrient_arr: 0.50 * vigor + 0.20 * chlo + 0.15 * texture_uniformity + 0.15 * cw
    MIN_NUTRIENT_WEIGHT = 0.35
    _nu_spec = [
        ("vigor",        0.50),
        ("chlorophyll",  0.20),
        ("canopy_water", 0.15)
    ]
    nu_accum = np.zeros((target_H, target_W), dtype=np.float32)
    nu_total_w = 0.0
    for key, nominal_w in _nu_spec:
        feat = feature_with_weight(key, nominal_w, (target_H, target_W))
        if feat.effective_weight > 0.0 and feat.values is not None:
            nu_accum += feat.effective_weight * feat.values
            nu_total_w += feat.effective_weight
    # add texture uniformity unconditionally
    nu_accum += 0.15 * texture_uniformity
    nu_total_w += 0.15
    has_nutrient_evidence = (
        _feat_status("chlorophyll") != "unavailable" or 
        _feat_status("red_edge") != "unavailable" or 
        _feat_status("nutrient") != "unavailable"
    )
    if nu_total_w < MIN_NUTRIENT_WEIGHT or not has_nutrient_evidence:
        nutrient_arr = None
    else:
        nutrient_arr = np.clip(nu_accum / max(nu_total_w, 0.01), 0.0, 1.0) if nu_total_w > 0.0 else zeros

    # salinity_arr
    MIN_SALINITY_WEIGHT = 0.35
    cw_feat = feature_with_weight("canopy_water", 1.0, (target_H, target_W))
    low_vigor_persistent = 1.0 - vigor_arr
    edge_accumulation = directional_coherence(vigor_arr)
    sal_accum = np.zeros((target_H, target_W), dtype=np.float32)
    sal_total_w = 0.0
    if cw_feat.effective_weight > 0.0 and cw_feat.values is not None:
        sal_accum += 0.45 * (1.0 - cw_feat.values)
        sal_total_w += 0.45
    if struct_feat.effective_weight > 0.0 and struct_feat.values is not None:
        sal_accum += 0.03 * (1.0 - struct_feat.values)
        sal_total_w += 0.03
    sal_accum += 0.25 * low_vigor_persistent
    sal_total_w += 0.25
    sal_accum += 0.20 * edge_accumulation
    sal_total_w += 0.20
    salinity_entry = bus.feature_status.get("salinity") or {}
    salinity_status = (
        salinity_entry.get("status", "unavailable")
        if isinstance(salinity_entry, dict)
        else str(salinity_entry)
    )
    salinity_source = str(_feat_source_kind("salinity") or "").lower()
    # Generic soil/water/canopy-water evidence does not establish salinity.
    # Accept an explicitly real salinity feature or a source that names a
    # salinity-specific measurement/feature family.
    has_salinity_evidence = salinity_status in {
        "real", "observed", "validated", "provider_observation"
    } and (
        salinity_status == "real"
        or any(
            marker in salinity_source
            for marker in (
                "swir", "salinity", "saline", "salt_index", "soil_ec",
                "electrical_conductivity", "irrigation_water_ec", "water_ec",
            )
        )
    )
    if sal_total_w < MIN_SALINITY_WEIGHT or not has_salinity_evidence:
        salinity_arr = None
    else:
        salinity_arr = np.clip(sal_accum / max(sal_total_w, 0.01), 0.0, 1.0)

    # risk_arr
    MIN_RISK_WEIGHT = 0.35
    anomaly_score = np.clip(np.abs(robust_zscore(vigor_arr - box_blur_k(vigor_arr, 9))), 0.0, 1.0)
    unc_feat = feature_with_weight("uncertainty", 0.20, (target_H, target_W), arr=bus.uncertainty)
    bma_feat = feature_with_weight("bma_disagreement", 0.20, (target_H, target_W), arr=bus.bma_disagreement)
    risk_accum = np.zeros((target_H, target_W), dtype=np.float32)
    risk_total_w = 0.0
    risk_accum += 0.35 * (1.0 - canopy_arr)
    risk_total_w += 0.35
    risk_accum += 0.15 * gapfill_arr
    risk_total_w += 0.15
    risk_accum += 0.10 * anomaly_score
    risk_total_w += 0.10
    if unc_feat.effective_weight > 0.0 and unc_feat.values is not None:
        risk_accum += unc_feat.effective_weight * unc_feat.values
        risk_total_w += unc_feat.effective_weight
    if bma_feat.effective_weight > 0.0 and bma_feat.values is not None:
        risk_accum += bma_feat.effective_weight * bma_feat.values
        risk_total_w += bma_feat.effective_weight
    has_risk_evidence = (
        _feat_status("uncertainty") != "unavailable" and (
            _feat_status("bma_disagreement") != "unavailable" or 
            _feat_status("retro_score") != "unavailable" or 
            _feat_status("anomaly") != "unavailable"
        )
    )
    if risk_total_w < MIN_RISK_WEIGHT or not has_risk_evidence:
        risk_arr = None
    else:
        risk_arr = np.clip(risk_accum / max(risk_total_w, 0.01), 0.0, 1.0)

    texture_signal = texture_detail

    def restore_nodata(arr):
        if arr is None:
            return None
        invalid = ~valid_mask | ~np.isfinite(arr)
        arr_clean = np.where(invalid, np.nan, arr)
        obj_arr = arr_clean.astype(object)
        obj_arr[np.isnan(arr_clean)] = None
        return obj_arr.tolist()

    surface_data = [
        (SurfaceType.COMPOSITE_ADVISORY_CANOPY,    restore_nodata(canopy_arr),    PaletteId.VIGOR_GREEN,     (0.0, 1.0)),
        (SurfaceType.COMPOSITE_VEG_ATTENTION,      restore_nodata(veg_att_arr),   PaletteId.VIGOR_GREEN,     (0.0, 1.0)),
        (SurfaceType.COMPOSITE_WATER_SUPPORT,      restore_nodata(water_arr),     PaletteId.YIELD_BLUE,      (-1.0, 1.0)),
        (SurfaceType.COMPOSITE_NUTRIENT_SUPPORT,   restore_nodata(nutrient_arr),  PaletteId.VIGOR_GREEN,     (0.0, 1.0)),
        (SurfaceType.COMPOSITE_SALINITY_STRESS,    restore_nodata(salinity_arr),  PaletteId.SALINITY_TEAL,   (0.0, 1.0)),
        (SurfaceType.COMPOSITE_RISK_DIAGNOSTIC,    restore_nodata(risk_arr),      PaletteId.RISK_HEAT,       (0.0, 1.0)),
        (SurfaceType.COMPOSITE_CONFIDENCE,         restore_nodata(bus.confidence),        PaletteId.UNCERTAINTY_GRAY,(0.0, 1.0)),
        (SurfaceType.COMPOSITE_EFFECTIVE_RESOLUTION, restore_nodata(bus.effective_resolution),   PaletteId.RAW_GRAYSCALE,   (0.03, 10.0)),
        (SurfaceType.COMPOSITE_UNCERTAINTY,        restore_nodata(bus.uncertainty),         PaletteId.UNCERTAINTY_GRAY,(0.0, 1.0)),
        (SurfaceType.COMPOSITE_BMA_DISAGREEMENT,  restore_nodata(bus.bma_disagreement),         PaletteId.UNCERTAINTY_GRAY,(0.0, 1.0)),
        (SurfaceType.COMPOSITE_ARCHIVE_SUPPORT,   restore_nodata(bus.archive_support),         PaletteId.UNCERTAINTY_GRAY,(0.0, 1.0)),
        (SurfaceType.COMPOSITE_RETRO_SCORE,       restore_nodata(bus.retro_score),         PaletteId.UNCERTAINTY_GRAY,(0.0, 1.0)),
        (SurfaceType.COMPOSITE_ML_SUPPORT,        restore_nodata(bus.ml_support),          PaletteId.UNCERTAINTY_GRAY,(0.0, 1.0)),
        (SurfaceType.COMPOSITE_TEXTURE_DETAIL,    restore_nodata(texture_signal),PaletteId.RAW_GRAYSCALE,   (-1.0, 1.0)),
    ]

    plot_id = getattr(l10_input, "plot_id", "unknown")
    surfaces = []

    for stype, values, palette, r_range in surface_data:
        # Skip if values is None or all-None
        is_all_none = True
        if values is not None:
            for row in values:
                if any(x is not None for x in row):
                    is_all_none = False
                    break
        if is_all_none:
            continue

        # BC.10.13 P6: support_status reads per-feature dict "status" field.
        # Legacy string-matching against the dict object was always wrong.
        def _lstat(key):
            return _feat_status(key)

        support_status = {
            # Legacy keys — always strings for backward compatibility.
            # These are NOT overwritten by the feature_status spread below.
            "archive":         _lstat("archive_support"),
            "retrovalidation": _lstat("retro_score"),
            "ml":              _lstat("ml_support"),
            "bma":             _lstat("bma_disagreement"),
            "uncertainty":     _lstat("uncertainty"),
            # Full per-feature details nested under its own key to avoid
            # collision with the legacy string keys above.
            "feature_details": dict(bus.feature_status),
        }

        provenance = {
            "source_reality":               source_reality,
            "real_asmae_evidence":          real_ev,
            "asmae_advisory_evidence":      True,
            "current_1m_approval_allowed":  False,
            "authority":                    authority,
            "state_update_allowed":         False,
            "prescription_driver_allowed":  False,
            "creator":                      "L10_ASMAE_COMPOSITE",
            # BC.10.13 P6: status fields read from per-feature dict, not bare string compare
            "bma_status":            "active" if _lstat("bma_disagreement") == "real" else "proxy",
            "archive_status":        "active" if _lstat("archive_support") == "real" else "unavailable",
            "ml_status":             "active" if _lstat("ml_support") == "real" else "unavailable",
            "retrovalidation_status":"active" if _lstat("retro_score") == "real" else "unavailable",
            "enkf_status":           "proxy",
            "support_status":        support_status,
            "source_signal_used":    selected_source_name,
            "highres_source_used": selected_source_name in {
                "EXPERIMENTAL_VISUAL_CANOPY_HIGHRES",
                "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL",
                "EXPERIMENTAL_VISUAL_CANOPY",
            },
            "input_signal_shape":  list(target_shape),
            "target_shape":        [target_H, target_W],
            "used_asmae_features": {
                k: bus.feature_status.get(k) for k in [
                    "vigor", "lai", "chlorophyll", "canopy_water", "root_zone_water",
                    "structure", "salinity", "confidence", "uncertainty",
                    "bma_disagreement", "retro_score", "archive_support",
                    "ml_support", "effective_resolution",
                ]
            },
        }

        surface = SurfaceArtifact(
            surface_id=f"{stype.value}_{plot_id}",
            semantic_type=stype,
            grid_ref=f"{target_H}x{target_W}",
            values=values,
            units="index" if stype != SurfaceType.COMPOSITE_EFFECTIVE_RESOLUTION else "meters",
            native_resolution_m=target_resolution_m,
            render_range=r_range,
            palette_id=palette,
            source_layers=["NDVI_CLEAN", "NDMI", "SAR", "QUALITY"],
            provenance=provenance,
            grounding_class=GroundingClass.MODEL_ASSISTED_RASTER.value,
            grid_spec={"height": target_H, "width": target_W, "res": target_resolution_m},
        )
        surfaces.append(surface)

    return surfaces
