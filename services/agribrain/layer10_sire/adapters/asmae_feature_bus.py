# -*- coding: utf-8 -*-
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from services.agribrain.layer10_sire.surfaces.grid_access import extract_named_grid, resample_to, extract_surface_grid

@dataclass
class ASMAEFeatureBus:
    state: str
    authority: str
    source_reality: str

    # BC.10.13 P4: available=False means no spatially meaningful base signal was found.
    # Downstream code must not emit surfaces when available=False.
    available: bool
    unavailable_reason: str

    vigor: Optional[np.ndarray]
    lai: Optional[np.ndarray]
    chlorophyll: Optional[np.ndarray]
    canopy_water: Optional[np.ndarray]
    root_zone_water: Optional[np.ndarray]
    structure: Optional[np.ndarray]
    bare_soil: Optional[np.ndarray]
    salinity: Optional[np.ndarray]
    thermal: Optional[np.ndarray]
    biotic_risk: Optional[np.ndarray]

    confidence: Optional[np.ndarray]
    uncertainty: Optional[np.ndarray]
    bma_disagreement: Optional[np.ndarray]
    cross_layer_conflict: Optional[np.ndarray]
    retro_score: Optional[np.ndarray]
    archive_support: Optional[np.ndarray]
    ml_support: Optional[np.ndarray]
    causal_support: Optional[np.ndarray]

    proxy_reconstruction_stability: Optional[np.ndarray]
    proxy_texture_stability: Optional[np.ndarray]
    proxy_observation_support: Optional[np.ndarray]
    proxy_stack_disagreement: Optional[np.ndarray]
    proxy_causal_support: Optional[np.ndarray]

    effective_resolution: Optional[np.ndarray]
    one_meter_mask: Optional[np.ndarray]
    model_assisted_2_5m_mask: Optional[np.ndarray]
    generalized_5m_mask: Optional[np.ndarray]

    # feature_status: per-feature dict {status, source, confidence, weight}
    feature_status: dict
    feature_weights: dict
    feature_manifest: dict = field(default_factory=dict)

def normalize_01(arr: np.ndarray) -> np.ndarray:
    if arr is None or arr.size == 0:
        return np.zeros_like(arr)
    mn = np.nanmin(arr)
    mx = np.nanmax(arr)
    diff = mx - mn
    if diff < 1e-6:
        return np.zeros_like(arr)
    scale = 1.0 if diff > 0.01 else diff / 0.01
    return ((arr - mn) / diff) * scale

def robust_zscore(arr: np.ndarray) -> np.ndarray:
    if arr is None or arr.size == 0:
        return np.zeros_like(arr)
    med = np.median(arr)
    mad = np.median(np.abs(arr - med))
    denom = mad if mad > 0.01 else 0.01
    return (arr - med) / denom

def box_blur(arr: np.ndarray) -> np.ndarray:
    padded = np.pad(arr, 1, mode='edge')
    sh = np.zeros_like(arr)
    for dr in (0, 1, 2):
        for dc in (0, 1, 2):
            sh += padded[dr:dr+arr.shape[0], dc:dc+arr.shape[1]]
    return sh / 9.0

def box_blur_k(arr: np.ndarray, k: int = 5) -> np.ndarray:
    pad_w = k // 2
    padded = np.pad(arr, pad_w, mode='edge')
    sh = np.zeros_like(arr)
    for dr in range(k):
        for dc in range(k):
            sh += padded[dr:dr+arr.shape[0], dc:dc+arr.shape[1]]
    return sh / float(k * k)

def local_variance(arr: np.ndarray, k: int = 5) -> np.ndarray:
    mean = box_blur_k(arr, k)
    mean2 = box_blur_k(arr * arr, k)
    return np.maximum(mean2 - mean * mean, 0.0)

def spatial_gradient(arr: np.ndarray) -> np.ndarray:
    padded = np.pad(arr, 1, mode='edge')
    h, w = arr.shape
    dx = padded[1:h+1, 2:w+2] - padded[1:h+1, 0:w]
    dy = padded[2:h+2, 1:w+1] - padded[0:h, 1:w+1]
    grad = np.sqrt(dx*dx + dy*dy)
    return np.where(np.isnan(grad), 0.0, grad)

def directional_coherence(arr: np.ndarray) -> np.ndarray:
    gx, gy = np.gradient(arr)
    return np.clip(np.abs(gx) / (np.abs(gx) + np.abs(gy) + 1e-6), 0.0, 1.0)

def is_blocked_as_asmae_input(name: str) -> bool:
    """BC.10.17: ASMAE may only consume provider evidence, Layer 1 normalized
    evidence, or Layer 05 feature packs. Everything else is blocked.
    
    CRITICAL: This blocklist applies ONLY to candidate raster surface names
    entering the ASMAE feature bus from Layer10/base_surfaces/raster maps.
    It must NOT block trusted Layer 05 asmae_feature_pack fields that already
    passed ASMAE proof export."""
    n = str(name).upper()
    return (
        n in _BLOCKED_EXACT or
        n.startswith("EXPERIMENTAL_VISUAL_") or
        n.endswith("_EXPERIMENTAL_FINE_DETAIL") or
        n.startswith("COMPOSITE_") or
        n.startswith("FALLBACK_") or
        n.startswith("NDVI_CLEAN_EXPERIMENTAL")
    )

_BLOCKED_EXACT = {
    "EXPERIMENTAL_VISUAL_CANOPY_HIGHRES",
    "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL",
    "EXPERIMENTAL_VISUAL_CANOPY",
}

def build_asmae_feature_bus(
    H: int,
    W: int,
    base_surfaces: List[Any],
    l10_input: Any,
    l1_data: Any,
    asmae_evidence_state: Optional[Dict[str, Any]] = None,
) -> ASMAEFeatureBus:
    """
    Constructs the ASMAEFeatureBus by extracting genuine ASMAE features from layers,
    and falls back to scientifically sound proxy algorithms.
    """
    # 1. Resolve State, Authority, Reality
    real_ev = getattr(l1_data, "real_asmae_evidence", False) if l1_data else False
    if real_ev:
        state = "full_scene_stack"
        authority = "asmae_state_authority"
        source_reality = "real_raster"
    else:
        state = "composite_assimilated_asmae"
        authority = "experimental_asmae_advisory"
        source_reality = "raster_composite_proxy"

    if asmae_evidence_state:
        state = asmae_evidence_state.get("state", state)
        authority = asmae_evidence_state.get("authority", authority)
        source_reality = asmae_evidence_state.get("source_reality", source_reality)

    feature_status = {}
    feature_manifest = {}

    # ── BC.10.13 P4: Proxy assimilation — RasterEvidence gating ──────────────
    # NDVI is the primary spatial base signal. All composite features derive from it.
    # If no spatially meaningful NDVI exists, we cannot fabricate features.
    from services.agribrain.layer10_sire.surfaces.raster_evidence_accessor import assess_raster_evidence

    base_surfaces_dict = {}
    if base_surfaces:
        for s in base_surfaces:
            stype = getattr(s, "semantic_type", None)
            stype_val = getattr(stype, "value", str(stype))
            base_surfaces_dict[stype_val] = s

    # Priority-ordered NDVI search — every candidate is assessed for spatial meaningfulness.
    ndvi_evidence = None
    selected_source_name = "none"

    # 1. Base surfaces (highest quality)
    for name in ["NDVI_CLEAN", "NDVI"]:
        if is_blocked_as_asmae_input(name):
            continue
        surf = base_surfaces_dict.get(name)
        if surf:
            arr = extract_surface_grid(surf)
            if arr is not None:
                arr_np = np.asarray(arr, dtype=np.float32)
                if arr_np.ndim == 2:
                    ev = assess_raster_evidence(arr_np, name, "raster_composite_proxy")
                    if ev.is_spatially_meaningful:
                        ndvi_evidence = ev
                        selected_source_name = name
                        break

    # 2. raster_composites from l10_input
    if ndvi_evidence is None and l10_input:
        rc = getattr(l10_input, "raster_composites", {}) or {}
        for name in ["NDVI_CLEAN", "NDVI"]:
            if is_blocked_as_asmae_input(name):
                continue
            val_grid = rc.get(name)
            if val_grid is None:
                continue
            arr_np = extract_surface_grid(val_grid)
            if arr_np is not None:
                ev = assess_raster_evidence(arr_np, f"l10_composite_{name}",
                                            "raster_composite_proxy")
                if ev.is_spatially_meaningful:
                    ndvi_evidence = ev
                    selected_source_name = f"l10_composite_{name}"
                    break

    # 3. Layer 1 raster maps
    if ndvi_evidence is None and l1_data:
        rm = getattr(l1_data, "raster_maps", {}) or {}
        for name in ["NDVI_CLEAN", "NDVI", "ndvi_clean", "ndvi"]:
            if is_blocked_as_asmae_input(name):
                continue
            if name in rm:
                arr = extract_surface_grid(rm[name])
                if arr is not None:
                    arr_np = np.asarray(arr, dtype=np.float32)
                    if arr_np.ndim == 2:
                        ev = assess_raster_evidence(arr_np, f"l1_raster_{name}",
                                                    "raster_composite_proxy")
                        if ev.is_spatially_meaningful:
                            ndvi_evidence = ev
                            selected_source_name = f"l1_raster_{name}"
                            break

    # HARD GATE: no meaningful NDVI found → feature bus unavailable.
    if ndvi_evidence is None:
        _unavail_status = {"status": "unavailable", "source": None, "confidence": 0.0, "weight": 0.0}
        return ASMAEFeatureBus(
            state="unavailable",
            authority="none",
            source_reality="unavailable",
            available=False,
            unavailable_reason="no_spatially_meaningful_ndvi",
            vigor=None, lai=None, chlorophyll=None, canopy_water=None,
            root_zone_water=None, structure=None, bare_soil=None,
            salinity=None, thermal=None, biotic_risk=None,
            confidence=None, uncertainty=None, bma_disagreement=None,
            cross_layer_conflict=None, retro_score=None, archive_support=None,
            ml_support=None, causal_support=None,
            proxy_reconstruction_stability=None, proxy_texture_stability=None,
            proxy_observation_support=None, proxy_stack_disagreement=None,
            proxy_causal_support=None,
            effective_resolution=None, one_meter_mask=None,
            model_assisted_2_5m_mask=None, generalized_5m_mask=None,
            feature_status={k: _unavail_status for k in [
                "vigor", "lai", "chlorophyll", "canopy_water", "root_zone_water",
                "structure", "bare_soil", "salinity", "thermal", "biotic_risk",
                "confidence", "uncertainty", "bma_disagreement", "cross_layer_conflict",
                "retro_score", "archive_support", "ml_support", "causal_support",
            ]},
            feature_weights={},
            feature_manifest={},
        )

    # We have a valid NDVI — proceed with proxy assimilation.
    ndvi_arr = resample_to(ndvi_evidence.array, (H, W), method="bilinear")
    ndvi_arr_filled = np.where(np.isnan(ndvi_arr), 0.0, ndvi_arr)

    # ── NDMI / SAR / Quality — assessed via RasterEvidence ───────────────────
    # Only used if they pass the spatial meaningfulness gate. No constant fallbacks.
    ndmi_raw = extract_named_grid("NDMI", base_surfaces, l10_input, l1_data)
    ndmi_arr_filled: Optional[np.ndarray] = None
    if ndmi_raw is not None:
        ndmi_np = np.asarray(ndmi_raw, dtype=np.float32)
        if ndmi_np.ndim == 2:
            ev_ndmi = assess_raster_evidence(ndmi_np, "NDMI", "raster_composite_proxy")
            if ev_ndmi.is_spatially_meaningful:
                ndmi_arr_filled = resample_to(ndmi_np, (H, W), method="bilinear")
                ndmi_arr_filled = np.where(np.isnan(ndmi_arr_filled), 0.0, ndmi_arr_filled)

    sar_raw = extract_named_grid("SAR", base_surfaces, l10_input, l1_data)
    if sar_raw is None:
        sar_raw = extract_named_grid("VV", base_surfaces, l10_input, l1_data)
    sar_arr_filled: Optional[np.ndarray] = None
    if sar_raw is not None:
        sar_np = np.asarray(sar_raw, dtype=np.float32)
        if sar_np.ndim == 2:
            ev_sar = assess_raster_evidence(sar_np, "SAR", "raster_composite_proxy")
            if ev_sar.is_spatially_meaningful:
                sar_arr_filled = resample_to(sar_np, (H, W), method="bilinear")
                # Convert dB to linear fraction if needed
                if np.any(sar_arr_filled < 0.0):
                    sar_arr_filled = np.clip((sar_arr_filled + 25.0) / 25.0, 0.0, 1.0)
                sar_arr_filled = np.where(np.isnan(sar_arr_filled), 0.0, sar_arr_filled)

    quality_raw = extract_named_grid("QUALITY", base_surfaces, l10_input, l1_data)
    if quality_raw is None:
        quality_raw = extract_named_grid("DATA_RELIABILITY", base_surfaces, l10_input, l1_data)
    quality_arr_filled: Optional[np.ndarray] = None
    if quality_raw is not None:
        qual_np = np.asarray(quality_raw, dtype=np.float32)
        if qual_np.ndim == 2:
            ev_qual = assess_raster_evidence(qual_np, "QUALITY", "raster_composite_proxy")
            if ev_qual.is_spatially_meaningful:
                quality_arr_filled = resample_to(qual_np, (H, W), method="bilinear")
                quality_arr_filled = np.where(np.isnan(quality_arr_filled), 0.5, quality_arr_filled)

    # ── Feature Pack from Layer 05 ─────────────────────────────────────────────
    fpack = getattr(l1_data, "asmae_feature_pack", None) if l1_data else None
    if fpack is None and l10_input:
        ft = getattr(l10_input, "field_tensor", None)
        cp = getattr(ft, "_context_package", None) if ft else None
        ao = getattr(cp, "asmae_output", None) if cp else None
        if ao:
            candidate_pack = getattr(ao, "asmae_feature_pack", None)
            if isinstance(candidate_pack, dict):
                fpack = candidate_pack

    from services.agribrain.scientific_contracts.state_schema_ref import canonical_state_key

    FPACK_KEYS = {
        "vigor": "vigor",
        "lai": "lai",
        "chlorophyll": "chlorophyll",
        "canopy_water": "canopy_water",
        "root_zone_water": "root_zone_water",
        "structure": "structure",
        "bare_soil": canonical_state_key("bare_soil"),
        "salinity": canonical_state_key("salinity"),
        "thermal": canonical_state_key("thermal"),
        "biotic_risk": canonical_state_key("biotic_risk"),
        "confidence": "confidence",
        "uncertainty": "uncertainty",
        "bma_disagreement": "bma_disagreement",
        "cross_layer_conflict": "cross_layer_conflict",
        "retro_score": "retrovalidation_score",
        "archive_support": "archive_support",
        "ml_support": "ml_support",
        "causal_support": "causal_support",
        "effective_resolution": "effective_resolution",
        "one_meter_mask": "one_meter_mask",
        "model_assisted_2_5m_mask": "model_assisted_2_5m_mask",
        "generalized_5m_mask": "generalized_5m_mask",
    }

    NORM_ENVELOPES = {
        "vigor": (0.0, 1.0),
        "lai": (0.0, 8.0),
        "chlorophyll": (0.0, 80.0),
        "canopy_water": (0.0, 1.0),
        "root_zone_water": (0.0, 1.0),
        "structure": (0.0, 1.0),
        "bare_soil": (0.0, 1.0),
        "salinity": (0.0, 1.0),
        "thermal": (0.0, 1.0),
        "biotic_risk": (0.0, 1.0),
        "stress_memory": (0.0, 1.0),
    }

    def lookup_feature(bus_key: str, fallback_func):
        """
        BC.10.13 P4 — Priority resolution for each feature:
          1. Layer 05 feature pack (real or proxy_derived with per-feature status)
          2. Layer 1 ASMAE raster maps
          3. Proxy derivation from validated base composites (NDVI/NDMI/SAR)

        fallback_func() must return (array_or_None, status_str, source_str).
        None is acceptable and means "unavailable".
        """
        fpack_key = FPACK_KEYS.get(bus_key, bus_key)
        explicit_status = None

        # Priority 1 & 2: Layer 05 feature pack
        if fpack:
            fstatus_entry = fpack.get("feature_status", {}).get(fpack_key)
            # P3 feature_status is now a per-feature dict
            if isinstance(fstatus_entry, dict):
                fs = fstatus_entry.get("status", "unavailable")
            else:
                fs = fstatus_entry  # legacy string
            explicit_status = fs
            if fs in ("real", "proxy_derived"):
                for category in ("state", "diagnostics", "resolution"):
                    grid = fpack.get(category, {}).get(fpack_key)
                    if grid is not None:
                        arr = np.asarray(grid, dtype=np.float32)
                        if bus_key in NORM_ENVELOPES:
                            min_val, max_val = NORM_ENVELOPES[bus_key]
                            if max_val - min_val > 1e-6:
                                arr = np.clip((arr - min_val) / (max_val - min_val), 0.0, 1.0)
                        if arr.shape != (H, W):
                            arr = resample_to(arr, (H, W), method="bilinear")

                        if isinstance(fstatus_entry, dict):
                            feature_status[bus_key] = fstatus_entry
                        else:
                            feature_status[bus_key] = {
                                "status": fs,
                                "source": f"layer05_asmae_{category}",
                                "weight": 0.90 if fs == "real" else 0.70,
                                "confidence": 0.90 if fs == "real" else 0.70,
                            }
                        feature_manifest[bus_key] = feature_status[bus_key]
                        return arr

            # An explicit Layer 05 upper-bound is authoritative. In particular,
            # a prior-only state or an unexecuted archive/ML/BMA stage must not
            # fall through and be relabelled as a real Layer 1 raster or proxy.
            if fs in ("prior_constrained", "unavailable", "unsupported"):
                if isinstance(fstatus_entry, dict):
                    st = dict(fstatus_entry)
                else:
                    st = {
                        "status": fs,
                        "source": None,
                        "confidence": 0.0,
                        "weight": 0.0,
                    }
                st.update(
                    weight=0.0,
                    usable_for_advisory=False,
                    authority_upper_bound=fs,
                )
                feature_status[bus_key] = st
                feature_manifest[bus_key] = st
                return None

        # Priority 3: Layer 1 ASMAE raster maps
        l1_key = f"asmae_{bus_key}"
        if l1_data:
            raster_maps = getattr(l1_data, "raster_maps", {}) or {}
            for name in [l1_key.upper(), l1_key.lower(), bus_key.upper(), bus_key.lower()]:
                if name in raster_maps:
                    arr = np.asarray(raster_maps[name], dtype=np.float32)
                    if bus_key in NORM_ENVELOPES:
                        min_val, max_val = NORM_ENVELOPES[bus_key]
                        if max_val - min_val > 1e-6:
                            arr = np.clip((arr - min_val) / (max_val - min_val), 0.0, 1.0)
                    if arr.shape != (H, W):
                        arr = resample_to(arr, (H, W), method="bilinear")
                    st = {"status": "real", "source": "layer1_asmae_raster",
                          "weight": 0.85, "confidence": 0.85,
                          "authority_upper_bound": explicit_status or "legacy_unbounded"}
                    feature_status[bus_key] = st
                    feature_manifest[bus_key] = st
                    return arr

        # Priority 4: fallback derivation from validated composites
        arr, status, source = fallback_func()
        if arr is None:
            st = {"status": "unavailable", "source": None, "confidence": 0.0, "weight": 0.0}
        elif "proxy" in str(status):
            st = {"status": "proxy_derived", "source": source,
                  "weight": 0.50, "confidence": 0.50}
        else:
            st = {"status": status, "source": source, "confidence": 0.0, "weight": 0.0}
        feature_status[bus_key] = st
        feature_manifest[bus_key] = st
        return arr

    # ── Feature derivations using validated composites only ───────────────────
    # Fallback lambdas return None when the required input composite is unavailable.
    # No constant arrays are fabricated.
    vigor = lookup_feature("vigor", lambda: (
        (ndvi_arr_filled, "proxy_from_ndvi", "satellite_ndvi") if ndvi_arr_filled is not None else (None, "unavailable", "none")
    ))
    lai = lookup_feature("lai", lambda: (
        (np.clip(3.5 * vigor, 0.0, 8.0), "proxy_from_vigor", "derived_lai")
        if vigor is not None else (None, "unavailable", "none")
    ))
    chlorophyll = lookup_feature("chlorophyll", lambda: (
        (np.clip(1.2 * vigor - 0.1, 0.0, 1.0), "proxy_from_ndvi_reip", "derived_chlorophyll")
        if vigor is not None else (None, "unavailable", "none")
    ))
    canopy_water = lookup_feature("canopy_water", lambda: (
        (ndmi_arr_filled, "proxy_from_ndmi", "satellite_ndmi")
        if ndmi_arr_filled is not None else (None, "unavailable", "none")
    ))
    root_zone_water = lookup_feature("root_zone_water", lambda: (
        (np.clip(0.6 * ndmi_arr_filled + 0.4 * sar_arr_filled, 0.0, 1.0), "proxy_from_ndmi_sar", "derived_rz_water")
        if (ndmi_arr_filled is not None and sar_arr_filled is not None)
        else (np.clip(0.6 * ndmi_arr_filled, 0.0, 1.0) if ndmi_arr_filled is not None else (None, "unavailable", "none"))
    ))
    structure = lookup_feature("structure", lambda: (
        (sar_arr_filled, "proxy_from_sar", "satellite_sar")
        if sar_arr_filled is not None else (None, "unavailable", "none")
    ))
    bare_soil = lookup_feature("bare_soil", lambda: (
        (np.clip(1.0 - vigor, 0.0, 1.0), "proxy_from_vigor", "derived_bare_soil")
        if vigor is not None else (None, "unavailable", "none")
    ))
    salinity = lookup_feature("salinity", lambda: (
        (np.clip(0.5*(1.0-ndmi_arr_filled)+0.5*(1.0-vigor), 0.0, 1.0), "proxy_from_ndmi_vigor", "derived_salinity")
        if (ndmi_arr_filled is not None and vigor is not None) else (None, "unavailable", "none")
    ))
    thermal = lookup_feature("thermal", lambda: (
        (np.clip(1.0 - vigor, 0.0, 1.0), "proxy_from_vigor", "derived_thermal")
        if vigor is not None else (None, "unavailable", "none")
    ))
    biotic_risk = lookup_feature("biotic_risk", lambda: (
        (np.clip(0.3*(1.0-vigor)+0.7*local_variance(vigor), 0.0, 1.0), "proxy_from_vigor_variance", "derived_biotic_risk")
        if vigor is not None else (None, "unavailable", "none")
    ))

    # ── Support diagnostics ───────────────────────────────────────────────────
    # Derived only from validated composite arrays (not constant fallbacks).
    _stk_avail = [a for a in [vigor, ndmi_arr_filled, sar_arr_filled] if a is not None]
    bma_disagreement = lookup_feature("bma_disagreement", lambda: (
        (np.clip(normalize_01(np.std(np.stack(_stk_avail, axis=0), axis=0)), 0.0, 1.0),
         "proxy_from_stack_std", "derived_bma_disagreement")
        if len(_stk_avail) >= 2 else (None, "unavailable", "none")
    ))
    cross_layer_conflict = lookup_feature("cross_layer_conflict", lambda: (
        (np.clip(0.4*(1.0-quality_arr_filled)+0.6*local_variance(vigor), 0.0, 1.0),
         "proxy_from_quality_variance", "derived_cross_layer_conflict")
        if (quality_arr_filled is not None and vigor is not None) else (None, "unavailable", "none")
    ))
    _obs_ratio = extract_named_grid("OBSERVED_RATIO", base_surfaces, l10_input, l1_data)
    _gap_mask = extract_named_grid("GAP_FILL_MASK", base_surfaces, l10_input, l1_data)

    # Proxy supports computation
    if quality_arr_filled is not None:
        obs_ratio_resampled = resample_to(np.asarray(_obs_ratio, np.float32), (H, W), "bilinear") if _obs_ratio is not None else quality_arr_filled
        gap_mask_resampled = resample_to(np.asarray(_gap_mask, np.float32), (H, W), "nearest") if _gap_mask is not None else np.zeros((H, W), dtype=np.float32)
        proxy_observation_support = np.clip(
            0.55 * quality_arr_filled
            + 0.25 * obs_ratio_resampled
            + 0.20 * (1.0 - gap_mask_resampled),
            0.0, 1.0
        )
    else:
        proxy_observation_support = None

    proxy_reconstruction_stability = np.clip(1.0 - normalize_01(np.abs(vigor - box_blur(vigor))), 0.0, 1.0) if vigor is not None else None

    if sar_arr_filled is not None and vigor is not None:
        proxy_texture_stability = np.clip(
            0.5 * np.clip(1.0 - spatial_gradient(sar_arr_filled), 0.0, 1.0)
            + 0.5 * np.clip(1.0 - spatial_gradient(vigor), 0.0, 1.0),
            0.0, 1.0
        )
    elif vigor is not None:
        proxy_texture_stability = np.clip(1.0 - spatial_gradient(vigor), 0.0, 1.0)
    else:
        proxy_texture_stability = None

    _stk_avail = [a for a in [vigor, ndmi_arr_filled, sar_arr_filled] if a is not None]
    proxy_stack_disagreement = np.clip(normalize_01(np.std(np.stack(_stk_avail, axis=0), axis=0)), 0.0, 1.0) if len(_stk_avail) >= 2 else None

    if quality_arr_filled is not None or proxy_texture_stability is not None:
        q_part = quality_arr_filled if quality_arr_filled is not None else np.zeros((H, W))
        t_part = proxy_texture_stability if proxy_texture_stability is not None else np.zeros((H, W))
        proxy_causal_support = np.clip(0.7 * q_part + 0.3 * t_part, 0.0, 1.0)
    else:
        proxy_causal_support = None

    # Real lookup_feature resolution (with fallback to None/unavailable)
    archive_support = lookup_feature("archive_support", lambda: (None, "unavailable", "none"))
    retro_score = lookup_feature("retro_score", lambda: (None, "unavailable", "none"))
    ml_support = lookup_feature("ml_support", lambda: (None, "unavailable", "none"))
    causal_support = lookup_feature("causal_support", lambda: (None, "unavailable", "none"))

    # Confidence depends on available supports; floor 0.05 when proxy-only.
    def _build_confidence():
        eff_arch = archive_support if archive_support is not None else proxy_observation_support
        eff_retro = retro_score if retro_score is not None else proxy_reconstruction_stability
        eff_ml = ml_support if ml_support is not None else proxy_texture_stability
        eff_bma = bma_disagreement if bma_disagreement is not None else proxy_stack_disagreement

        parts = [
            (0.25, quality_arr_filled),
            (0.20, eff_arch),
            (0.20, eff_retro),
            (0.15, eff_ml),
            (0.10, (1.0 - eff_bma) if eff_bma is not None else None),
            (0.10, (1.0 - cross_layer_conflict) if cross_layer_conflict is not None else None)
        ]
        total_w, accum = 0.0, None
        for w, arr in parts:
            if arr is not None:
                if accum is None:
                    accum = np.zeros((H, W), dtype=np.float32)
                accum += w * arr
                total_w += w
        if total_w == 0 or accum is None:
            return None, "unavailable", "none"
        return np.clip(0.05 + 0.95 * (accum / total_w), 0.0, 1.0), "proxy_from_supports", "derived_confidence"

    confidence = lookup_feature("confidence", _build_confidence)
    uncertainty = lookup_feature("uncertainty", lambda: (
        (1.0 - confidence, "proxy_from_confidence", "derived_uncertainty")
        if confidence is not None else (None, "unavailable", "none")
    ))
    effective_resolution = lookup_feature("effective_resolution", lambda: (
        (np.where(confidence > 0.75, 5.0, np.where(confidence > 0.55, 7.5, 10.0)),
         "proxy_from_confidence", "derived_effective_resolution")
        if confidence is not None else (None, "unavailable", "none")
    ))

    one_meter_mask = lookup_feature("one_meter_mask", lambda: (
        (np.where(confidence > 0.8, 1.0, 0.0), "proxy_from_confidence", "derived_one_meter_mask")
        if confidence is not None else (None, "unavailable", "none")
    ))
    model_assisted_2_5m_mask = lookup_feature("model_assisted_2_5m_mask", lambda: (
        (np.where(confidence > 0.6, 1.0, 0.0), "proxy_from_confidence", "derived_model_assisted_2_5m_mask")
        if confidence is not None else (None, "unavailable", "none")
    ))
    generalized_5m_mask = lookup_feature("generalized_5m_mask", lambda: (
        (np.where(confidence > 0.4, 1.0, 0.0), "proxy_from_confidence", "derived_generalized_5m_mask")
        if confidence is not None else (None, "unavailable", "none")
    ))

    feature_weights = {
        "physio_vigor": {
            "vigor": 0.26, "chlorophyll": 0.16, "lai": 0.14, "canopy_water": 0.12,
            "root_zone_water": 0.10, "structure": 0.08, "salinity": -0.08, "thermal": -0.06
        },
        "stress_penalty": {
            "bma_disagreement": 0.20, "uncertainty": 0.20, "cross_layer_conflict": 0.20,
            "bare_soil": 0.15, "biotic_risk": 0.15, "gapfill": 0.10
        },
        "support_gate": {
            "confidence": 0.20, "retro_score": 0.18, "archive_support": 0.18,
            "ml_support": 0.16, "causal_support": 0.14, "observed_ratio": 0.14
        },
        "texture_detail": {
            "row_coherence": 0.35, "local_gradient": 0.25, "highpass_vigor": 0.20,
            "boundary_residual": 0.20
        }
    }

    # Ensure proxy fields are registered in feature_status for completeness
    for pk, pv in [
        ("proxy_reconstruction_stability", proxy_reconstruction_stability),
        ("proxy_texture_stability", proxy_texture_stability),
        ("proxy_observation_support", proxy_observation_support),
        ("proxy_stack_disagreement", proxy_stack_disagreement),
        ("proxy_causal_support", proxy_causal_support)
    ]:
        if pv is not None:
            feature_status[pk] = {"status": "proxy_derived", "source": "texture_analysis", "weight": 0.50, "confidence": 0.50}
        else:
            feature_status[pk] = {"status": "unavailable", "source": None, "weight": 0.0, "confidence": 0.0}

    return ASMAEFeatureBus(
        state=state,
        authority=authority,
        source_reality=source_reality,
        available=True,
        unavailable_reason="",
        vigor=vigor,
        lai=lai,
        chlorophyll=chlorophyll,
        canopy_water=canopy_water,
        root_zone_water=root_zone_water,
        structure=structure,
        bare_soil=bare_soil,
        salinity=salinity,
        thermal=thermal,
        biotic_risk=biotic_risk,
        confidence=confidence,
        uncertainty=uncertainty,
        bma_disagreement=bma_disagreement,
        cross_layer_conflict=cross_layer_conflict,
        retro_score=retro_score,
        archive_support=archive_support,
        ml_support=ml_support,
        causal_support=causal_support,
        proxy_reconstruction_stability=proxy_reconstruction_stability,
        proxy_texture_stability=proxy_texture_stability,
        proxy_observation_support=proxy_observation_support,
        proxy_stack_disagreement=proxy_stack_disagreement,
        proxy_causal_support=proxy_causal_support,
        effective_resolution=effective_resolution,
        one_meter_mask=one_meter_mask,
        model_assisted_2_5m_mask=model_assisted_2_5m_mask,
        generalized_5m_mask=generalized_5m_mask,
        feature_status=feature_status,
        feature_weights=feature_weights,
        feature_manifest=feature_manifest,
    )
