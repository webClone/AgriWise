"""
Resolution Coverage Surface Generator (V61C)
=============================================

Builds the RESOLUTION_COVERAGE surface as stable categorical codes. Physical
support values are used only inside the selector and are translated through
an explicit class legend before serialization.

Resolution hierarchy (V61C six-tier ladder):
  1. If best_val_res_map is available (from MicroZone adapter / L1 data):
     render it directly -> spatial_precision = "pixel_resolved"
  2. Else, run ResolutionLadderSelector to evaluate satellite-derived gates
     per pixel -> spatial_precision = "ladder_evaluated"
  3. Else if ground_truth_summary exists (but no L1 rasters):
     build an area-proportional categorical placeholder
     -> spatial_precision = "area_proportional_placeholder"
  4. Else:
     fill all pixels with 10.0 (native fallback)
     -> spatial_precision = "uniform_fallback"

The surface is CATEGORICAL, not continuous. Values are discrete resolution
classes, not probabilities.

V61C change: absence of 3cm ground truth no longer forces 10m.
The ladder evaluates 1m -> 2m -> 3m -> 5m -> 10m independently.
"""

from typing import List, Optional, Dict, Any

import numpy as np

from services.agribrain.layer10_sire.schema import (
    SurfaceArtifact, SurfaceType, GroundingClass, PaletteId,
)
from services.agribrain.layer10_sire.surfaces.resolution_ladder import (
    select_resolution_per_pixel,
    ResolutionLadderConfig,
    _compute_percentages,
    PERCENTAGE_FIELDS,
)


RESOLUTION_CLASS_CODES = {
    0.03: 0,  # EXTERNAL_GROUND_TRUTH_3CM
    1.0: 1,   # ADVISORY_FINE_DETAIL
    2.0: 2,   # MODEL_ASSISTED_2M
    3.0: 3,   # MODEL_ASSISTED_3M
    5.0: 4,   # MODEL_ASSISTED_5M
    10.0: 5,  # NATIVE_10M
}
RESOLUTION_CLASS_LEGEND = {
    "0": {"class": "EXTERNAL_GROUND_TRUTH_3CM", "evidence_resolution_m": 0.03},
    "1": {"class": "ADVISORY_FINE_DETAIL", "display_target_m": 1.0, "source_evidence_resolution_m": 10.0},
    "2": {"class": "MODEL_ASSISTED_2M", "computational_grid_m": 2.0, "source_evidence_resolution_m": 10.0},
    "3": {"class": "MODEL_ASSISTED_3M", "computational_grid_m": 3.0, "source_evidence_resolution_m": 10.0},
    "4": {"class": "MODEL_ASSISTED_5M", "computational_grid_m": 5.0, "source_evidence_resolution_m": 10.0},
    "5": {"class": "NATIVE_10M", "source_evidence_resolution_m": 10.0},
}

CANDIDATE_MASK_CONTRACT_VERSION = "asmae_candidate_mask_v1"


def _value_from_object(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _semantic_type_value(surface: Any) -> str:
    value = _value_from_object(surface, "semantic_type", "")
    return str(getattr(value, "value", value))


def _current_asmae_identity(asmae_output: Any) -> Dict[str, Any]:
    """Read the immutable identity of the ASMAE output in this L10 context."""
    content_hash = _value_from_object(asmae_output, "content_hash")
    if callable(content_hash):
        content_hash = content_hash()
    return {
        "content_hash": content_hash,
        "schema_version": _value_from_object(asmae_output, "schema_version"),
        "plot_id": _value_from_object(asmae_output, "plot_id"),
    }


def _validate_asmae_candidate_mask(
    surface: Any,
    *,
    expected_shape: tuple[int, int],
    expected_plot_id: str,
    current_identity: Dict[str, Any],
) -> tuple[bool, List[str], Optional[np.ndarray], Dict[str, Any]]:
    """Fail-closed validation for the ASMAE-to-L10 candidate-mask bridge."""
    reasons: List[str] = []
    proof = dict(_value_from_object(surface, "provenance", {}) or {}).get("candidate_mask_proof")
    proof = dict(proof or {})

    if _semantic_type_value(surface) != "ASMAE_1M_ADVISORY_MASK":
        reasons.append("wrong_semantic_type")
    if proof.get("contract_version") != CANDIDATE_MASK_CONTRACT_VERSION:
        reasons.append("incompatible_contract_version")
    if str(proof.get("plot_id") or "") != str(expected_plot_id or ""):
        reasons.append("plot_id_mismatch")

    current_hash = current_identity.get("content_hash")
    proof_hash = proof.get("source_output_content_hash")
    if not current_hash:
        reasons.append("current_output_content_hash_missing")
    elif not proof_hash or proof_hash != current_hash:
        reasons.append("source_output_content_hash_mismatch")

    current_schema = current_identity.get("schema_version")
    proof_schema = proof.get("source_schema_version")
    if not current_schema or not proof_schema:
        reasons.append("source_schema_version_missing")
    elif proof_schema != current_schema:
        reasons.append("source_schema_version_mismatch")

    identity_plot = current_identity.get("plot_id")
    if identity_plot and str(identity_plot) != str(expected_plot_id or ""):
        reasons.append("current_output_plot_id_mismatch")
    if proof.get("grid_shape") != [int(expected_shape[0]), int(expected_shape[1])]:
        reasons.append("proof_grid_shape_mismatch")
    if not proof.get("generated_from_current_raster", False):
        reasons.append("not_generated_from_current_raster")
    if not proof.get("real_asmae_evidence", False):
        reasons.append("real_asmae_evidence_required")
    if not proof.get("non_proxy", False):
        reasons.append("proxy_candidate_mask_rejected")
    if not proof.get("current_1m_authority_allowed", False):
        reasons.append("current_1m_authority_required")
    if not proof.get("output_allowed", False):
        reasons.append("candidate_mask_output_not_allowed")
    source_reality = str(proof.get("source_reality") or "").lower()
    if not source_reality or "proxy" in source_reality or source_reality in {"synthetic", "unknown", "missing"}:
        reasons.append("non_real_source_reality")

    raw_values = _value_from_object(surface, "values")
    try:
        raw_mask = np.asarray(raw_values, dtype=float)
    except (TypeError, ValueError):
        raw_mask = None
        reasons.append("mask_values_invalid")
    if raw_mask is not None:
        if raw_mask.ndim != 2 or raw_mask.shape != expected_shape:
            reasons.append("mask_grid_shape_mismatch")
        elif not np.all(np.isfinite(raw_mask)):
            reasons.append("mask_contains_non_finite_values")
        elif not np.all((raw_mask == 0.0) | (raw_mask == 1.0)):
            reasons.append("mask_not_binary")

    accepted_mask = raw_mask.astype(bool) if raw_mask is not None and not reasons else None
    consumed_proof = {
        "contract_version": proof.get("contract_version"),
        "source_output_content_hash": proof_hash,
        "source_schema_version": proof_schema,
        "plot_id": proof.get("plot_id"),
        "grid_shape": proof.get("grid_shape"),
        "authority": proof.get("authority"),
        "source_reality": proof.get("source_reality"),
        "accepted": not reasons,
        "rejection_reasons": reasons,
    }
    return not reasons, reasons, accepted_mask, consumed_proof


def _encode_resolution_classes(values: List[List[float]]) -> List[List[float]]:
    return [
        [
            float(RESOLUTION_CLASS_CODES.get(round(float(value), 4), 5))
            if value is not None and np.isfinite(value)
            else None
            for value in row
        ]
        for row in values
    ]


def robust_zscore(arr: np.ndarray) -> np.ndarray:
    med = np.median(arr)
    mad = np.median(np.abs(arr - med))
    if mad < 1e-5:
        mad = 1.0
    return (arr - med) / mad

def fill_nans_local(arr: np.ndarray) -> np.ndarray:
    if not np.any(np.isnan(arr)):
        return arr.copy()
    filled = arr.copy()
    h, w = arr.shape
    padded = np.pad(arr, 1, mode='edge')
    for r in range(h):
        for c in range(w):
            if np.isnan(filled[r, c]):
                block = padded[r:r+3, c:c+3]
                valid = block[~np.isnan(block)]
                if valid.size > 0:
                    filled[r, c] = np.mean(valid)
    return filled

def box_blur_k(arr: np.ndarray, k: int = 5) -> np.ndarray:
    pad_w = k // 2
    padded = np.pad(arr, pad_w, mode='edge')
    sh = np.zeros_like(arr)
    for dr in range(k):
        for dc in range(k):
            sh += padded[dr:dr+arr.shape[0], dc:dc+arr.shape[1]]
    return sh / float(k * k)

def spatial_gradient(arr: np.ndarray) -> np.ndarray:
    padded = np.pad(arr, 1, mode='edge')
    h, w = arr.shape
    dx = padded[1:h+1, 2:w+2] - padded[1:h+1, 0:w]
    dy = padded[2:h+2, 1:w+1] - padded[0:h, 1:w+1]
    return np.sqrt(dx*dx + dy*dy)

def directional_texture_coherence(arr: np.ndarray) -> np.ndarray:
    padded = np.pad(arr, 1, mode='edge')
    h, w = arr.shape
    dx = padded[1:h+1, 2:w+2] - padded[1:h+1, 0:w]
    dy = padded[2:h+2, 1:w+1] - padded[0:h, 1:w+1]
    denom = np.abs(dx) + np.abs(dy) + 1e-6
    return np.clip(np.abs(dx) / denom, 0.0, 1.0)

def boundary_aware_edge_signal(arr: np.ndarray) -> np.ndarray:
    padded = np.pad(arr, 1, mode='edge')
    h, w = arr.shape
    lap = 4.0 * arr - (padded[0:h, 1:w+1] + padded[2:h+2, 1:w+1] + padded[1:h+1, 0:w] + padded[1:h+1, 2:w+2])
    return np.abs(lap)


def _local_conservation_supports(mask: np.ndarray, tile_size: int = 5) -> List[np.ndarray]:
    """Partition candidate cells into deterministic local conservation units."""
    supports: List[np.ndarray] = []
    height, width = mask.shape
    for row_start in range(0, height, tile_size):
        for col_start in range(0, width, tile_size):
            support = np.zeros_like(mask, dtype=bool)
            support[
                row_start:min(row_start + tile_size, height),
                col_start:min(col_start + tile_size, width),
            ] = mask[
                row_start:min(row_start + tile_size, height),
                col_start:min(col_start + tile_size, width),
            ]
            if np.any(support):
                supports.append(support)
    return supports


def _restore_local_source_sums(
    experimental: np.ndarray,
    source: np.ndarray,
    supports: List[np.ndarray],
) -> None:
    """Restore each local source sum after clipping without crossing tile boundaries."""
    for support in supports:
        target_sum = float(np.sum(source[support], dtype=np.float64))
        for _ in range(16):
            current_sum = float(np.sum(experimental[support], dtype=np.float64))
            residual = target_sum - current_sum
            if abs(residual) <= 1e-9:
                break
            if residual > 0.0:
                adjustable = support & (experimental < 1.0 - 1e-7)
            else:
                adjustable = support & (experimental > 1e-7)
            adjustable_count = int(np.sum(adjustable))
            if adjustable_count == 0:
                break
            experimental[adjustable] = np.clip(
                experimental[adjustable] + residual / adjustable_count,
                0.0,
                1.0,
            )

def generate_resolution_surfaces(
    l10_input: Any,
    H: int,
    W: int,
    l1_data: Any = None,
    ground_truth_context: Optional[Dict[str, Any]] = None,
    current_asmae_surfaces: Optional[List[SurfaceArtifact]] = None,
) -> List[SurfaceArtifact]:
    """
    Generate the RESOLUTION_COVERAGE surface.

    Args:
        l10_input: Layer10Input (used for ground_truth_context fallback)
        H, W: grid dimensions
        l1_data: Adapted L1 data (may contain best_val_res_map from MicroZone)
        ground_truth_context: Ground truth registry decision (resolution percentages)

    Returns:
        List containing the RESOLUTION_COVERAGE SurfaceArtifact
    """
    # Resolve ground truth context
    gt_ctx = ground_truth_context or getattr(l10_input, 'ground_truth_context', {}) or {}

    # Strategy 1: Prefer pixel-resolved best_val_res_map from L1 data
    best_map = None
    if l1_data is not None:
        raster_maps = getattr(l1_data, 'raster_maps', {}) or {}
        for key in ['microzone_best_validated_resolution_m', 'best_val_res_map']:
            if key in raster_maps:
                candidate = raster_maps[key]
                if hasattr(candidate, 'shape') or isinstance(candidate, list):
                    best_map = candidate
                    break

    if best_map is not None:
        # Pixel-resolved: use the real best_val_res_map from MicroZone
        values = _build_from_best_val_res_map(best_map, H, W)
        spatial_precision = "pixel_resolved"
        uses_best_val_res_map = True
        grounding = GroundingClass.RASTER_GROUNDED.value
        # Compute percentages from the actual raster
        arr = np.asarray(values, dtype=float)
        resolution_percentages = _compute_percentages(arr, H * W)
        ladder_metadata = {
            "ladder_inputs": {
                "has_best_val_res_map": True,
                "has_uncertainty": False,
                "has_observation_count": False,
                "has_zone_policy": False,
                "has_retrovalidation_score": False,
                "ndvi_observed_ratio": 1.0,
                "ndmi_observed_ratio": 1.0
            },
            "selection_policy": "best_validated_resolution_map",
            "anti_uniform_3m_demoted": False
        }

    elif l1_data is not None and getattr(l1_data, 'raster_maps', {}):
        # Strategy 2 (V61C NEW): Run the resolution ladder selector
        import sys
        raster_keys = list((getattr(l1_data, 'raster_maps', {}) or {}).keys())
        print(f"[V61C] Strategy 2: ladder_evaluated. L1 raster_maps keys={raster_keys}, H={H}, W={W}", file=sys.stderr)

        # Build ground truth mask from context
        gt_mask = _build_ground_truth_mask(gt_ctx, H, W)
        block_mask = _build_one_meter_block_mask(gt_ctx, H, W)

        # Check if conditional 1m certification is active
        conditional_1m = False
        if gt_ctx:
            cert = gt_ctx.get("certification_decision", {}) or {}
            if cert.get("allow_conditional_1m_certified_export") or cert.get("one_meter_advisory_certified"):
                conditional_1m = True

        # Check if strict microzone maps are present
        strict_maps = False
        if l1_data is not None:
            raster_maps = getattr(l1_data, 'raster_maps', {}) or {}
            if any(k in raster_maps for k in ['ndvi_uncertainty', 'uncertainty', 'microzone_uncertainty']):
                strict_maps = True

        ladder_res = select_resolution_per_pixel(
            l1_data, H, W,
            ground_truth_mask=gt_mask,
            one_meter_block_mask=block_mask,
            config=ResolutionLadderConfig(),
            uses_best_val_res_map=False,
            conditional_1m_certification=conditional_1m,
            strict_microzone_maps=strict_maps,
        )
        ladder_map, resolution_percentages = ladder_res
        values = ladder_map.tolist()
        ladder_metadata = ladder_res.metadata
        spatial_precision = "ladder_evaluated"
        uses_best_val_res_map = False
        grounding = GroundingClass.RASTER_GROUNDED.value

        unique_vals = sorted(set(v for row in values for v in row))
        print(f"[V61C] Ladder result: unique_values={unique_vals}, pcts={resolution_percentages}", file=sys.stderr)

    elif gt_ctx:
        # Strategy 3: Area-proportional placeholder from ground truth summary
        values = _build_area_proportional_placeholder(gt_ctx, H, W)
        spatial_precision = "area_proportional_placeholder"
        uses_best_val_res_map = False
        grounding = GroundingClass.ZONE_GROUNDED.value
        arr = np.asarray(values, dtype=float)
        resolution_percentages = _compute_percentages(arr, H * W)
        ladder_metadata = {
            "ladder_inputs": {
                "has_best_val_res_map": False,
                "has_uncertainty": False,
                "has_observation_count": False,
                "has_zone_policy": False,
                "has_retrovalidation_score": False,
                "ndvi_observed_ratio": 0.0,
                "ndmi_observed_ratio": 0.0
            },
            "selection_policy": "area_proportional_placeholder",
            "anti_uniform_3m_demoted": False
        }

    else:
        # Strategy 4: Uniform fallback — all native 10m
        values = [[10.0] * W for _ in range(H)]
        spatial_precision = "uniform_fallback"
        uses_best_val_res_map = False
        grounding = GroundingClass.UNIFORM.value
        resolution_percentages = {
            "three_cm_external_ground_truth_pct": 0.0,
            "one_meter_advisory_pct": 0.0,
            "two_meter_production_pct": 0.0,
            "three_meter_production_pct": 0.0,
            "five_meter_production_pct": 0.0,
            "ten_meter_fallback_pct": 100.0,
        }
        ladder_metadata = {
            "ladder_inputs": {
                "has_best_val_res_map": False,
                "has_uncertainty": False,
                "has_observation_count": False,
                "has_zone_policy": False,
                "has_retrovalidation_score": False,
                "ndvi_observed_ratio": 0.0,
                "ndmi_observed_ratio": 0.0
            },
            "selection_policy": "uniform_fallback",
            "anti_uniform_3m_demoted": False
        }

    # Any sub-10 m satellite-derived class is model-assisted. Preserve legacy
    # production fields as explicit zeroes and expose separate honest fields.
    resolution_percentages["two_meter_model_assisted_pct"] = resolution_percentages.get(
        "two_meter_model_assisted_pct",
        resolution_percentages.get("two_meter_production_pct", 0.0),
    )
    resolution_percentages["three_meter_model_assisted_pct"] = resolution_percentages.get(
        "three_meter_model_assisted_pct",
        resolution_percentages.get("three_meter_production_pct", 0.0),
    )
    resolution_percentages["five_meter_model_assisted_pct"] = resolution_percentages.get(
        "five_meter_model_assisted_pct",
        resolution_percentages.get("five_meter_production_pct", 0.0),
    )
    resolution_percentages["two_meter_production_pct"] = 0.0
    resolution_percentages["three_meter_production_pct"] = 0.0
    resolution_percentages["five_meter_production_pct"] = 0.0

    # Preserve physical support classes in provenance, then serialize stable
    # category codes so downstream consumers cannot reinterpret a bare meter
    # value as native observation resolution.
    support_values = values
    unique_support_values = sorted({
        round(float(v), 4)
        for row in support_values
        for v in row
        if v is not None and np.isfinite(v)
    })
    values = _encode_resolution_classes(support_values)

    # Collect unique categorical codes present.
    unique_values = set()
    for row in values:
        for v in row:
            if v is not None:
                unique_values.add(round(v, 4))

    provenance = {
        "surface_semantics": "categorical_resolution_class",
        "spatial_precision": spatial_precision,
        "true_drone_footprint_rendering": False,
        "actual_drone_tile_delivery_deferred_to": "V62",
        "uses_best_val_res_map": uses_best_val_res_map,
        "unique_resolution_class_codes": sorted(unique_values),
        "unique_support_values_m": unique_support_values,
        "resolution_class_legend": RESOLUTION_CLASS_LEGEND,
        "values_are_categorical_codes": True,
        "resolution_percentages": resolution_percentages,
        "generator": "V61C_resolution_ladder_surface",
        "six_tier_ladder": True,
        "truthful_resolution_note": "5 m is a model-assisted representation of 10 m-class source evidence",
        "source_evidence_resolution_m": 10.0,
    }
    provenance.update(ladder_metadata)

    surface = SurfaceArtifact(
        surface_id=f"RESOLUTION_COVERAGE_{getattr(l10_input, 'plot_id', 'unknown')}",
        semantic_type=SurfaceType.RESOLUTION_COVERAGE,
        grid_ref=f"{H}x{W}",
        values=values,
        units="category_code",
        native_resolution_m=10.0,
        render_range=(0.0, 5.0),
        palette_id="resolution_categorical",
        source_layers=["ground_truth_registry", "microzone_adapter", "resolution_ladder_selector"],
        provenance=provenance,
        grounding_class=grounding,
    )

    # --- Step 1a-V65D: Experimental fine-detail candidate surface ---
    observed_mask = None
    if l1_data is not None:
        observed_masks = getattr(l1_data, 'observed_masks', {}) or {}
        ndvi_key = next((k for k in ['ndvi', 'NDVI'] if k in observed_masks), None)
        if ndvi_key:
            observed_mask = np.asarray(observed_masks[ndvi_key], dtype=bool)
        else:
            other_key = next(iter(observed_masks.keys()), None)
            if other_key:
                observed_mask = np.asarray(observed_masks[other_key], dtype=bool)

    if observed_mask is not None:
        if observed_mask.shape != (H, W):
            row_idx = np.linspace(0, observed_mask.shape[0] - 1, H).astype(int)
            col_idx = np.linspace(0, observed_mask.shape[1] - 1, W).astype(int)
            observed_mask = observed_mask[np.ix_(row_idx, col_idx)]
        
        permissive_observed_mask = observed_mask.copy()
        
        # Binary erosion of the observed mask by 1-2 cells (2 iterations of 3x3 structuring element)
        def _binary_erosion_3x3(arr):
            eroded = np.zeros_like(arr)
            eroded[1:-1, 1:-1] = (
                arr[1:-1, 1:-1] &
                arr[:-2, 1:-1] &
                arr[2:, 1:-1] &
                arr[1:-1, :-2] &
                arr[1:-1, 2:] &
                arr[:-2, :-2] &
                arr[:-2, 2:] &
                arr[2:, :-2] &
                arr[2:, 2:]
            )
            return eroded
        
        eroded_mask = observed_mask.copy()
        for _ in range(2):
            eroded_mask = _binary_erosion_3x3(eroded_mask)
        # Suppress any cells on the absolute outer edge boundary of the H x W grid
        eroded_mask[0, :] = False
        eroded_mask[-1, :] = False
        eroded_mask[:, 0] = False
        eroded_mask[:, -1] = False
        observed_mask = eroded_mask
    else:
        observed_mask = np.zeros((H, W), dtype=bool)
        from services.agribrain.layer10_sire.surfaces.resolution_ladder import _extract_raster
        raster_maps = getattr(l1_data, 'raster_maps', {}) or {} if l1_data is not None else {}
        ndvi_basis = _extract_raster(raster_maps, ["ndvi", "NDVI", "NDVI_CLEAN", "canopy", "vegetation"], H, W)
        if ndvi_basis is not None:
            permissive_observed_mask = np.isfinite(ndvi_basis)
        else:
            permissive_observed_mask = np.zeros((H, W), dtype=bool)

    from services.agribrain.layer10_sire.surfaces.resolution_ladder import _extract_raster
    raster_maps = getattr(l1_data, 'raster_maps', {}) or {} if l1_data is not None else {}
    uncertainty = _extract_raster(raster_maps, ['ndvi_uncertainty', 'uncertainty', 'microzone_uncertainty'], H, W)
    zone_policy = _extract_raster(raster_maps, ['microzone_zone_policy', 'zone_policy_map'], H, W)
    gapfill = _extract_raster(raster_maps, ['gapfill', 'gap_fill', 'gap_fill_mask'], H, W)

    quality_evidence_present = zone_policy is not None or uncertainty is not None
    has_observed_pixels = observed_mask is not None and np.any(observed_mask)

    status_info = None

    # Check if the current L10 run explicitly generated an ASMAE 1m mask.
    # The surface list is handed off directly by the caller; the context output
    # is used only to verify its immutable snapshot identity.
    ctx_pkg = getattr(l10_input.field_tensor, "_context_package", None) if getattr(l10_input, "field_tensor", None) else None
    asmae_output_ref = getattr(ctx_pkg, "asmae_output", None) if ctx_pkg else None
    asmae_1m_mask_surf = next(
        (s for s in (current_asmae_surfaces or []) if _semantic_type_value(s) == "ASMAE_1M_ADVISORY_MASK"),
        None,
    )
    candidate_mask_proof = None
    mask_accepted = False
    if asmae_1m_mask_surf is not None:
        mask_accepted, mask_reasons, accepted_mask, candidate_mask_proof = _validate_asmae_candidate_mask(
            asmae_1m_mask_surf,
            expected_shape=(H, W),
            expected_plot_id=str(getattr(l10_input, "plot_id", "") or ""),
            current_identity=_current_asmae_identity(asmae_output_ref),
        )
        if not mask_accepted:
            status_info = "asmae_candidate_mask_rejected:" + ",".join(mask_reasons)

    if mask_accepted and accepted_mask is not None:
        candidate_mask = accepted_mask.copy()
        candidate_source = "asmae_1m_advisory_mask"
        certification_status = "experimental_learning" if np.any(candidate_mask) else "no_experimental_candidates"
        status_info = "bridged_from_current_asmae"
        quality_evidence_present = True

    elif not has_observed_pixels:
        candidate_mask = np.zeros((H, W), dtype=bool)
        candidate_source = "none"
        certification_status = "no_experimental_candidates"
        status_info = "no_observed_pixels"
    elif quality_evidence_present:
        zone_policy_part = (zone_policy >= 0.5) if zone_policy is not None else np.zeros((H, W), dtype=bool)
        uncertainty_part = (uncertainty < 0.20) if uncertainty is not None else np.zeros((H, W), dtype=bool)
        candidate_mask = observed_mask & (zone_policy_part | uncertainty_part)
        
        if np.any(candidate_mask):
            candidate_source = "quality_gated_candidate"
            certification_status = "experimental_learning"
        else:
            candidate_source = "none"
            certification_status = "no_experimental_candidates"
    else:
        # Fallback logic: No uncertainty and no zone policy, use texture learning on actual observed base map
        ndvi = _extract_raster(raster_maps, ['ndvi', 'NDVI'], H, W)
        if ndvi is not None:
            mean_val = np.nanmean(ndvi) if not np.isnan(np.nanmean(ndvi)) else 0.0
            ndvi_clean = np.nan_to_num(ndvi, nan=mean_val)
            dy, dx = np.gradient(ndvi_clean)
            gradient = np.sqrt(dx**2 + dy**2)
            
            grad_threshold = max(0.01, float(np.nanpercentile(gradient[observed_mask], 75)))
            candidate_mask = observed_mask & (gradient >= grad_threshold)
            
            # low-confidence fallback candidate coverage <= 35% cap
            total_cells = H * W
            max_candidate_cells = int(total_cells * 0.35)
            if np.sum(candidate_mask) > max_candidate_cells:
                candidate_vals = gradient[candidate_mask]
                cutoff_val = float(np.percentile(candidate_vals, 100.0 - (100.0 * max_candidate_cells / len(candidate_vals))))
                candidate_mask = candidate_mask & (gradient >= cutoff_val)
            
            if np.any(candidate_mask):
                candidate_source = "texture_learning_candidate"
                certification_status = "experimental_learning_unvalidated"
            else:
                candidate_source = "none"
                certification_status = "no_experimental_candidates"
        else:
            candidate_mask = np.zeros((H, W), dtype=bool)
            candidate_source = "none"
            certification_status = "no_experimental_candidates"

    # Suppress small components (size < 4 cells) from candidate mask using manual BFS
    def _suppress_small_components(mask, min_size=4):
        h_dim, w_dim = mask.shape
        visited = np.zeros_like(mask, dtype=bool)
        res_mask = mask.copy()
        for r in range(h_dim):
            for c in range(w_dim):
                if res_mask[r, c] and not visited[r, c]:
                    comp = []
                    queue = [(r, c)]
                    visited[r, c] = True
                    head = 0
                    while head < len(queue):
                        curr_r, curr_c = queue[head]
                        comp.append((curr_r, curr_c))
                        head += 1
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nr, nc = curr_r + dr, curr_c + dc
                            if 0 <= nr < h_dim and 0 <= nc < w_dim:
                                if res_mask[nr, nc] and not visited[nr, nc]:
                                    visited[nr, nc] = True
                                    queue.append((nr, nc))
                    if len(comp) < min_size:
                        for cr, cc in comp:
                            res_mask[cr, cc] = False
        return res_mask

    candidate_mask = _suppress_small_components(candidate_mask, min_size=4)
    candidate_mask &= permissive_observed_mask
    if gapfill is not None:
        candidate_mask &= np.asarray(gapfill) < 0.75
    valid_field_cells = int(np.sum(permissive_observed_mask))
    candidate_pct = (
        100.0 * float(np.sum(candidate_mask)) / float(valid_field_cells)
        if valid_field_cells > 0 else 0.0
    )

    if uncertainty is not None and np.any(candidate_mask):
        candidate_unc = uncertainty[candidate_mask]
        mean_unc = float(np.mean(candidate_unc))
        fine_detail_uncertainty = round(mean_unc, 2)
        fine_detail_confidence = round(1.0 - mean_unc, 2)
    else:
        fine_detail_confidence = None
        fine_detail_uncertainty = None

    # Binary candidate membership. These values are category codes, never metres.
    exp_values = np.where(candidate_mask, 1.0, 0.0).tolist()

    source_evidence_resolution_m = float(getattr(surface, "native_resolution_m", None) or 10.0)
    exp_provenance = {
        "surface_semantics": "experimental_fine_detail_candidate",
        "type": "EXPERIMENTAL_FINE_DETAIL_CANDIDATE",
        "canonical_type": "EXPERIMENTAL_FINE_DETAIL_CANDIDATE",
        "source_reality": "model_assisted_visual_detail",
        "source_evidence_resolution_m": source_evidence_resolution_m,
        "computational_grid_resolution_m": source_evidence_resolution_m,
        "display_grid_resolution_m": source_evidence_resolution_m,
        "resolution_role": "experimental_advisory_visual_layer",
        "production_selectable": False,
        "state_update_allowed": False,
        "diagnostic_only": True,
        "requires_user_warning": True,
        "fine_detail_confidence": fine_detail_confidence,
        "fine_detail_uncertainty": fine_detail_uncertainty,
        "fine_detail_reason": "deconvolution candidate, not certified" if quality_evidence_present else "low-confidence texture learning candidate, unvalidated",
        "generator": "V65F_experimental_fine_detail_candidate",
        "candidate_coverage_pct": candidate_pct,
        "quality_evidence_present": quality_evidence_present,
        "has_uncertainty": uncertainty is not None,
        "has_zone_policy": zone_policy is not None,
        "learning_enabled": True,
        "feedback_allowed": True,
        "validation_sources": [
            "farmer_input",
            "farmer_photo",
            "ip_camera",
            "iot_sensor",
            "drone_orthomosaic"
        ],
        "certification_status": certification_status,
        "candidate_source": candidate_source
    }
    if status_info:
        exp_provenance["status"] = status_info
    if candidate_mask_proof is not None:
        exp_provenance["candidate_mask_proof"] = candidate_mask_proof

    source_layers = ["observed_mask"]
    if zone_policy is not None:
        source_layers.append("zone_policy")
    if uncertainty is not None:
        source_layers.append("uncertainty_map")

    exp_surface = SurfaceArtifact(
        surface_id=f"EXPERIMENTAL_FINE_DETAIL_CANDIDATE_{getattr(l10_input, 'plot_id', 'unknown')}",
        semantic_type=SurfaceType.EXPERIMENTAL_FINE_DETAIL_CANDIDATE,
        grid_ref=f"{H}x{W}",
        values=exp_values,
        units="category_code",
        native_resolution_m=source_evidence_resolution_m,
        render_range=(0.0, 1.0),
        palette_id="experimental_fine_detail",
        source_layers=source_layers,
        provenance=exp_provenance,
        grounding_class=GroundingClass.MODEL_ASSISTED_RASTER.value,
    )

    # Generate 5 new experimental surfaces using real texture features
    if observed_mask is None:
        return [surface]

    ndvi_grid = None
    if l1_data is not None:
        r_maps = getattr(l1_data, 'raster_maps', {}) or {}
        ndvi_grid = r_maps.get("NDVI") or r_maps.get("NDVI_CLEAN") or r_maps.get("ndvi") or r_maps.get("ndvi_clean")
    if ndvi_grid is None:
        return [surface]

    ndvi_arr = np.asarray(ndvi_grid, dtype=np.float32)
    ndvi_filled = fill_nans_local(ndvi_arr)

    # Compute a visual texture signal. Every normalization statistic is limited
    # to valid candidate cells; rectangular fill pixels never influence it.
    local_mean = box_blur_k(ndvi_filled, k=5)
    hp = ndvi_filled - local_mean
    grad = spatial_gradient(ndvi_filled)
    row_coh = directional_texture_coherence(ndvi_filled)
    edge_sig = boundary_aware_edge_signal(ndvi_filled)

    def _masked_robust_score(values: np.ndarray, support: np.ndarray) -> np.ndarray:
        result = np.zeros_like(values, dtype=np.float32)
        finite_support = support & np.isfinite(values)
        samples = values[finite_support]
        if samples.size < 4:
            return result
        median = float(np.median(samples))
        mad = float(np.median(np.abs(samples - median)))
        scale = max(1.4826 * mad, float(np.std(samples)), 1e-6)
        result[finite_support] = np.clip((values[finite_support] - median) / scale, -3.0, 3.0)
        return result

    combined_texture = (
        0.35 * _masked_robust_score(hp, candidate_mask)
      + 0.25 * _masked_robust_score(grad, candidate_mask)
      + 0.20 * _masked_robust_score(row_coh, candidate_mask)
      + 0.20 * _masked_robust_score(edge_sig, candidate_mask)
    )
    if np.any(candidate_mask):
        support_values = combined_texture[candidate_mask]
        combined_texture[candidate_mask] -= float(np.mean(support_values))
        peak = float(np.max(np.abs(combined_texture[candidate_mask])))
        if peak > 1e-6:
            combined_texture[candidate_mask] /= peak
    combined_texture[~candidate_mask] = 0.0

    valid_source = permissive_observed_mask & np.isfinite(ndvi_arr)
    source_samples = ndvi_arr[valid_source]
    source_iqr = (
        float(np.percentile(source_samples, 75) - np.percentile(source_samples, 25))
        if source_samples.size else 0.0
    )
    # Unvalidated texture may move a candidate by at most 15% of the field IQR,
    # never more than 0.03 NDVI. This is a visual ceiling, not evidence precision.
    amplitude_ceiling = min(0.03, max(0.0, 0.15 * source_iqr))
    amplitude_map = np.full((H, W), amplitude_ceiling, dtype=np.float32)
    if uncertainty is not None:
        finite_uncertainty = np.where(np.isfinite(uncertainty), np.maximum(uncertainty, 0.0), 0.0)
        amplitude_map = np.minimum(amplitude_map, finite_uncertainty)
    texture_delta = combined_texture * amplitude_map * candidate_mask
    conservation_support = candidate_mask & valid_source
    local_conservation_supports = _local_conservation_supports(
        conservation_support,
        tile_size=5,
    )
    for local_support in local_conservation_supports:
        texture_delta[local_support] -= float(np.mean(texture_delta[local_support]))

    exp_highres_arr = np.clip(ndvi_filled + texture_delta, 0.0, 1.0)
    # Clipping can reintroduce a signed field bias after the pre-clip delta was
    # centred. Restore the candidate-cell source mean using only non-saturated
    # candidate values. This preserves the coarse signal without changing any
    # non-candidate cell or claiming additional evidence resolution.
    _restore_local_source_sums(
        exp_highres_arr,
        ndvi_arr,
        local_conservation_supports,
    )
    exp_highres_arr[~valid_source] = np.nan
    source_to_experimental_delta = exp_highres_arr - ndvi_arr
    signed_error = float(np.nanmean(source_to_experimental_delta[valid_source])) if np.any(valid_source) else 0.0
    absolute_error = float(np.nanmean(np.abs(source_to_experimental_delta[valid_source]))) if np.any(valid_source) else 0.0
    max_absolute_error = float(np.nanmax(np.abs(source_to_experimental_delta[valid_source]))) if np.any(valid_source) else 0.0
    candidate_signed_error = (
        float(np.nanmean(source_to_experimental_delta[conservation_support]))
        if np.any(conservation_support) else 0.0
    )
    local_signal_mean_errors = [
        float(np.nanmean(source_to_experimental_delta[support]))
        for support in local_conservation_supports
    ]
    local_signal_max_mean_error = max(
        (abs(value) for value in local_signal_mean_errors),
        default=0.0,
    )
    visual_canopy_values = exp_highres_arr.tolist()

    strict_mask_values = [[1.0 if candidate_mask[r, c] else 0.0 for c in range(W)] for r in range(H)]
    observed_grid = observed_mask if observed_mask is not None else np.ones((H, W), dtype=bool)
    gapfill_mask_values = [[0.0 if observed_grid[r, c] else 1.0 for c in range(W)] for r in range(H)]

    # Provenance dict for the 5 experimental surfaces
    exp_details_prov = {
        "resolution_role": "experimental_visual_detail",
        "source_reality": "model_assisted_visual_detail",
        "source_evidence_resolution_m": source_evidence_resolution_m,
        "computational_grid_resolution_m": source_evidence_resolution_m,
        "display_grid_resolution_m": source_evidence_resolution_m,
        "state_update_allowed": False,
        "production_selectable": False,
        "diagnostic_only": True,
        "requires_user_warning": True,
        "candidate_source": candidate_source,
        "candidate_coverage_pct": candidate_pct,
        "validated_fine_detail_pct": 0.0,
        "confidence_status": "unavailable_unvalidated",
        "amplitude_ceiling": round(amplitude_ceiling, 6),
        "source_to_experimental_mean_error": round(signed_error, 8),
        "candidate_signal_mean_error": round(candidate_signed_error, 8),
        "signal_conservation_passed": abs(candidate_signed_error) <= 1e-6,
        "signal_conservation_support_cells": int(np.sum(conservation_support)),
        "local_signal_conservation_unit": "5x5_source_grid_tile",
        "local_signal_conservation_unit_count": len(local_conservation_supports),
        "local_signal_max_mean_error": round(local_signal_max_mean_error, 8),
        "local_signal_conservation_passed": local_signal_max_mean_error <= 1e-6,
        "source_to_experimental_absolute_error": round(absolute_error, 8),
        "source_to_experimental_max_absolute_error": round(max_absolute_error, 8),
    }

    vis_canopy_surf = SurfaceArtifact(
        surface_id=f"EXPERIMENTAL_VISUAL_CANOPY_{getattr(l10_input, 'plot_id', 'unknown')}",
        semantic_type=SurfaceType.EXPERIMENTAL_VISUAL_CANOPY,
        grid_ref=f"{H}x{W}",
        values=visual_canopy_values,
        units="fraction",
        native_resolution_m=source_evidence_resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=source_layers,
        provenance=exp_details_prov,
        grounding_class=GroundingClass.MODEL_ASSISTED_RASTER.value,
    )

    strict_mask_surf = SurfaceArtifact(
        surface_id=f"EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK_{getattr(l10_input, 'plot_id', 'unknown')}",
        semantic_type=SurfaceType.EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK,
        grid_ref=f"{H}x{W}",
        values=strict_mask_values,
        units="fraction",
        native_resolution_m=source_evidence_resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.RAW_GRAYSCALE,
        source_layers=source_layers,
        provenance=exp_details_prov,
        grounding_class=GroundingClass.MODEL_ASSISTED_RASTER.value,
    )

    gapfill_mask_surf = SurfaceArtifact(
        surface_id=f"EXPERIMENTAL_GAPFILL_MASK_{getattr(l10_input, 'plot_id', 'unknown')}",
        semantic_type=SurfaceType.EXPERIMENTAL_GAPFILL_MASK,
        grid_ref=f"{H}x{W}",
        values=gapfill_mask_values,
        units="fraction",
        native_resolution_m=source_evidence_resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.RAW_GRAYSCALE,
        source_layers=source_layers,
        provenance=exp_details_prov,
        grounding_class=GroundingClass.MODEL_ASSISTED_RASTER.value,
    )

    texture_support_values = strict_mask_values
    
    experimental_1m_detail_mask_surf = SurfaceArtifact(
        surface_id=f"EXPERIMENTAL_TEXTURE_SUPPORT_MASK_{getattr(l10_input, 'plot_id', 'unknown')}",
        semantic_type=SurfaceType.EXPERIMENTAL_TEXTURE_SUPPORT_MASK,
        grid_ref=f"{H}x{W}",
        values=texture_support_values,
        units="fraction",
        native_resolution_m=source_evidence_resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.RAW_GRAYSCALE,
        source_layers=source_layers,
        provenance=exp_details_prov,
        grounding_class=GroundingClass.MODEL_ASSISTED_RASTER.value,
    )

    return [surface, exp_surface, vis_canopy_surf, strict_mask_surf, gapfill_mask_surf, experimental_1m_detail_mask_surf]



def _build_from_best_val_res_map(best_map: Any, H: int, W: int) -> list:
    """
    Build surface values from a pixel-resolved best_val_res_map array.
    Handles shape mismatches by nearest-neighbor resampling.
    """
    arr = np.asarray(best_map, dtype=float)

    # Handle 1D flat arrays
    if arr.ndim == 1:
        total = arr.shape[0]
        side = int(total ** 0.5)
        if side * side == total:
            arr = arr.reshape(side, side)
        else:
            arr = arr[:H * W].reshape(H, W) if total >= H * W else np.full((H, W), 10.0)

    # Handle shape mismatch with nearest-neighbor resize
    if arr.shape[0] != H or arr.shape[1] != W:
        row_idx = np.linspace(0, arr.shape[0] - 1, H).astype(int)
        col_idx = np.linspace(0, arr.shape[1] - 1, W).astype(int)
        arr = arr[np.ix_(row_idx, col_idx)]

    return arr.tolist()


def _build_ground_truth_mask(
    gt_ctx: Dict[str, Any], H: int, W: int
) -> Optional[np.ndarray]:
    """
    Build a boolean mask for 3cm ground truth coverage.
    
    Uses the ground_truth_summary percentages to create an area-proportional
    mask. Returns None if no 3cm coverage exists.
    """
    res_pcts = gt_ctx.get("resolution_percentages", {})
    if not res_pcts:
        gts = gt_ctx.get("ground_truth_summary", {})
        res_pcts = gts.get("resolution_percentages", gts)
    
    three_cm_pct = res_pcts.get("three_cm_pct",
                   res_pcts.get("three_cm_external_ground_truth_pct", 0.0))
    
    if three_cm_pct <= 0.0:
        return None
    
    total_pixels = H * W
    three_cm_pixels = int(round(total_pixels * three_cm_pct / 100.0))
    if three_cm_pixels <= 0:
        return None
    
    mask = np.zeros((H, W), dtype=bool)
    flat = mask.ravel()
    flat[:min(three_cm_pixels, total_pixels)] = True
    return mask


def _build_one_meter_block_mask(
    gt_ctx: Dict[str, Any], H: int, W: int
) -> Optional[np.ndarray]:
    """
    Build a boolean mask blocking 1m where ground-truth conflicts exist.
    
    Returns a uniform block mask if the certification decision blocks 1m.
    Returns None if 1m is not blocked.
    """
    cert = gt_ctx.get("certification_decision", {})
    if not cert:
        gts = gt_ctx.get("ground_truth_summary", {})
        cert = gts.get("certification_decision", {})

    # Check if 1m is blocked by ground truth conflicts
    one_m_certified = cert.get("one_meter_advisory_certified", True)
    
    if one_m_certified:
        return None  # Not blocked
    
    # 1m is blocked everywhere
    return np.zeros((H, W), dtype=bool)


def _build_area_proportional_placeholder(
    gt_ctx: Dict[str, Any], H: int, W: int
) -> list:
    """
    Build an area-proportional placeholder surface from ground_truth_summary.

    V61C: supports full six-tier ladder (0.03, 1.0, 2.0, 3.0, 5.0, 10.0).
    Fills cells top-to-bottom with resolution classes proportional to their
    certified coverage percentage.

    NOTE: This is NOT a true geospatial drone footprint. It is a visual
    placeholder showing area proportions.
    """
    total_cells = H * W

    # Extract percentages from ground truth summary
    res_pcts = gt_ctx.get("resolution_percentages", {})
    if not res_pcts:
        gts = gt_ctx.get("ground_truth_summary", {})
        res_pcts = gts.get("resolution_percentages", gts)

    three_cm_pct = res_pcts.get("three_cm_pct",
                   res_pcts.get("three_cm_external_ground_truth_pct", 0.0))
    one_m_pct = res_pcts.get("one_meter_pct",
                res_pcts.get("one_meter_advisory_pct", 0.0))
    two_m_pct = res_pcts.get("two_meter_production_pct", 0.0)
    three_m_pct = res_pcts.get("three_meter_production_pct", 0.0)
    five_m_pct = res_pcts.get(
        "five_meter_model_assisted_pct",
        res_pcts.get("five_meter_production_pct", 0.0),
    )
    # ten_m_pct is the implicit remainder

    # Compute cell counts
    three_cm_cells = int(round(total_cells * three_cm_pct / 100.0))
    one_m_cells = int(round(total_cells * one_m_pct / 100.0))
    two_m_cells = int(round(total_cells * two_m_pct / 100.0))
    three_m_cells = int(round(total_cells * three_m_pct / 100.0))
    five_m_cells = int(round(total_cells * five_m_pct / 100.0))
    ten_m_cells = total_cells - three_cm_cells - one_m_cells - two_m_cells - three_m_cells - five_m_cells

    # Clamp to prevent negative
    if ten_m_cells < 0:
        five_m_cells = max(0, five_m_cells + ten_m_cells)
        ten_m_cells = total_cells - three_cm_cells - one_m_cells - two_m_cells - three_m_cells - five_m_cells
    if ten_m_cells < 0:
        ten_m_cells = 0

    # Build flat array in priority order
    flat = (
        [0.03] * three_cm_cells +
        [1.0] * one_m_cells +
        [2.0] * two_m_cells +
        [3.0] * three_m_cells +
        [5.0] * five_m_cells +
        [10.0] * ten_m_cells
    )

    # Reshape to H x W
    values = []
    idx = 0
    for r in range(H):
        row = []
        for c in range(W):
            if idx < len(flat):
                row.append(flat[idx])
            else:
                row.append(10.0)
            idx += 1
        values.append(row)

    return values
