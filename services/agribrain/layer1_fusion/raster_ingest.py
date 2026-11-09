"""
Layer 1 Raster Grid Ingestion.

Converts pre-fetched raster composites (pixel arrays from the orchestrator)
into zone-aggregated EvidenceItems for the fusion pipeline.

Layer 1 never fetches rasters directly — the orchestrator provides them
via Layer1InputBundle.raster_composites.

Design:
- Pixels are aggregated to zone-level summaries to avoid O(pixel²) evidence
  explosion. Each zone gets mean, std, valid_count.
- Raster-scoped evidence carries sigma derived from pixel variance.
- SpatialIndex raster_refs are updated with real resolution + content_hash.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .schemas import (
    EvidenceItem,
    RasterRef,
    normalize_geographic_grid_contract,
    raster_grid_matches_dimensions,
)
from .truth_bridge import normalize_evidence_truth, truth_for_raster_composite


# Variable → canonical name mapping
_VARIABLE_MAP = {
    "NDVI": "ndvi",
    "NDMI": "ndmi",
    "NDRE": "ndre",
    "SAR": "sar_backscatter",
    "SAR_VV": "sar_backscatter",
    "QUALITY": "quality_mask",
}


def validate_raster_grid_spec(
    raster_data: Dict[str, Any],
    array_height: int,
    array_width: int,
    resolution_m: float,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Return a normalized, non-zero raster grid or a rejection reason.

    RasterRef is a spatial authority object.  Array dimensions alone are not
    enough to create one: CRS, positive-area bounds, and an invertible affine
    transform must all be present.  Top-level fields are accepted for legacy
    producers, but the canonical output is ``grid_spec``.
    """
    raw_grid = raster_data.get("grid_spec")
    grid = dict(raw_grid) if isinstance(raw_grid, dict) else {}

    for key in ("crs", "bounds", "transform", "affine", "width", "height", "resolution_m"):
        if grid.get(key) is None and raster_data.get(key) is not None:
            grid[key] = raster_data[key]
    if grid.get("bounds") is None and raster_data.get("request_bbox") is not None:
        grid["bounds"] = raster_data["request_bbox"]
    if grid.get("transform") is None and grid.get("affine") is not None:
        grid["transform"] = grid["affine"]

    normalized_contract, reason = normalize_geographic_grid_contract(
        crs=grid.get("crs"),
        bounds=grid.get("bounds"),
        transform=grid.get("transform"),
        width=grid.get("width", array_width),
        height=grid.get("height", array_height),
        resolution_m=grid.get("resolution_m", resolution_m),
        expected_width=array_width,
        expected_height=array_height,
    )
    if normalized_contract is None:
        return None, reason

    normalized = {
        **grid,
        **normalized_contract,
        "affine": normalized_contract["transform"],
    }
    return normalized, "ok"


def ingest_raster_composites(
    composites: Dict[str, Any],
    plot_id: str,
    run_timestamp: datetime,
    zone_masks: Optional[Dict[str, List[List[int]]]] = None,
) -> Tuple[List[EvidenceItem], List[RasterRef]]:
    """Ingest pre-fetched raster composites into evidence items.

    Args:
        composites: Dict mapping variable name → raster dict with:
            - pixel_array: List[List[float]] (H×W)
            - valid_pixel_count: int
            - resolution_m: float (default 10.0)
        plot_id: Plot identifier.
        run_timestamp: Current run timestamp.
        zone_masks: Optional dict of zone_id → H×W binary mask.
            If provided, evidence is generated per zone.
            If not, a single plot-level summary is generated.

    Returns:
        Tuple of (evidence_items, raster_refs).
    """
    evidence: List[EvidenceItem] = []
    raster_refs: List[RasterRef] = []

    for var_key, raster_data in composites.items():
        if not isinstance(raster_data, dict):
            continue

        pixel_array = raster_data.get("pixel_array")
        if pixel_array is None:
            pixel_array = raster_data.get("values")
        if pixel_array is None:
            continue
        try:
            H = len(pixel_array)
            W = len(pixel_array[0]) if H else 0
        except (TypeError, IndexError):
            continue
        if H <= 0 or W <= 0:
            continue

        # Recompute actual valid non-null, finite pixel count (T33 / PR28-12)
        actual_valid = 0
        if isinstance(pixel_array, list) and all(isinstance(row, list) and len(row) == W for row in pixel_array):
            for row in pixel_array:
                for v in row:
                    if v is not None and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
                        actual_valid += 1
        valid_count = max(0, min(H * W, actual_valid))
        resolution_m = raster_data.get("resolution_m", 10.0)
        canonical_var = _VARIABLE_MAP.get(var_key, var_key.lower())

        total_cells = H * W
        observed_ratio = float(valid_count / total_cells) if total_cells > 0 else 0.0
        if raster_grid_matches_dimensions(pixel_array, H, W):
            grid_spec, grid_status = validate_raster_grid_spec(
                raster_data, H, W, resolution_m,
            )
        else:
            grid_spec, grid_status = None, "grid_array_shape_mismatch"

        # Compute content hash from pixel data and grid spec
        content_hash = _compute_pixel_hash(pixel_array, grid_spec=grid_spec, native_resolution_m=resolution_m)

        raster_id = f"raster_{canonical_var}_{content_hash[:8]}"

        # V92.4-BC.10.5 Truth Governance
        from layer05_asmae.truth_contract import truth_to_evidence_fields
        truth = truth_for_raster_composite(raster_data)
        ev_fields = truth_to_evidence_fields(truth)
        has_provider_authority = (
            grid_spec is not None
            and truth.real_provider_product
            and truth.production_usable
            and not truth.diagnostic_only
        )
        grounding_class = truth.grounding_class or (
            "RASTER_GROUNDED" if has_provider_authority else "UNIFORM"
        )

        # Never create a RasterRef from an absent/zero geographic contract.
        # The plot-level numeric summary remains available as diagnostic
        # evidence, but no downstream layer can mistake it for a map.
        if grid_spec is not None:
            raster_refs.append(RasterRef(
                raster_id=raster_id,
                variable=canonical_var,
                resolution_m=grid_spec["resolution_m"],
                content_hash=content_hash,
                width=W,
                height=H,
                crs=grid_spec["crs"],
                bounds=tuple(grid_spec["bounds"]),
                transform=tuple(grid_spec["transform"]),
                grid=pixel_array,
                valid_pixel_count=valid_count,
                observed_ratio=observed_ratio,
                truth_class=truth.truth_class,
                source_reality=truth.source_reality,
                real_provider_product=truth.real_provider_product,
                production_usable=truth.production_usable and has_provider_authority,
                grounding_class=grounding_class,
                visualization_allowed=truth.visualization_allowed,
                experimental_visual_allowed=truth.experimental_visual_allowed,
                composite_advisory_allowed=truth.composite_advisory_allowed,
                scientific_surface_allowed=(
                    truth.scientific_surface_allowed and has_provider_authority
                ),
                current_1m_approval_allowed=(
                    truth.current_1m_approval_allowed and has_provider_authority
                ),
                state_update_allowed=truth.state_update_allowed and has_provider_authority,
                observed_spatial_surface=has_provider_authority,
                diagnostic_only=truth.diagnostic_only or not has_provider_authority,
                source_basis=truth.source_reality,
                prescription_driver_allowed=(
                    truth.prescription_driver_allowed and has_provider_authority
                ),
                authority_block_reason=(
                    None if has_provider_authority else "raster_truth_not_authoritative"
                ),
            ))

        evidence_flags = [] if grid_spec is not None else [
            f"INVALID_GEOSPATIAL_GRID:{grid_status}"
        ]
        effective_zone_masks = zone_masks if grid_spec is not None else None

        if effective_zone_masks:
            # Zone-aggregated evidence
            for zone_id, mask in effective_zone_masks.items():
                stats = _compute_zonal_stats(pixel_array, mask)
                if stats["count"] == 0:
                    continue

                sigma = _compute_raster_sigma(
                    stats["std"], stats["count"], resolution_m,
                )
                confidence_val = min(0.9, 0.5 + 0.01 * stats["count"])
                if not has_provider_authority:
                    confidence_val = min(confidence_val, 0.20)

                item = EvidenceItem(
                    evidence_id=f"raster_{canonical_var}_{zone_id}_{content_hash[:8]}",
                    plot_id=plot_id,
                    variable=canonical_var,
                    value=stats["mean"],
                    unit="index" if canonical_var in ("ndvi", "ndmi", "ndre") else "dB",
                    source_family="raster_composite",
                    source_id=raster_id,
                    observation_type="measurement",
                    spatial_scope="zone",
                    scope_id=zone_id,
                    observed_at=run_timestamp,
                    confidence=confidence_val,
                    sigma=sigma,
                    reliability=min(0.95, 0.6 + 0.005 * stats["count"]),
                    freshness_score=1.0,
                    provenance_ref=f"raster_ingest_{raster_id}_zone_{zone_id}",
                    flags=list(evidence_flags),
                    grounding_class=grounding_class,
                    **ev_fields
                )
                evidence.append(normalize_evidence_truth(item, source_context=raster_data))
        else:
            # Plot-level summary
            stats = _compute_plot_stats(pixel_array)
            if stats["count"] == 0:
                continue

            sigma = _compute_raster_sigma(
                stats["std"], stats["count"], resolution_m,
            )
            confidence_val = min(0.9, 0.5 + 0.01 * stats["count"])
            if not has_provider_authority:
                confidence_val = min(confidence_val, 0.20)

            item = EvidenceItem(
                evidence_id=f"raster_{canonical_var}_plot_{content_hash[:8]}",
                plot_id=plot_id,
                variable=canonical_var,
                value=stats["mean"],
                unit="index" if canonical_var in ("ndvi", "ndmi", "ndre") else "dB",
                source_family="raster_composite",
                source_id=raster_id,
                observation_type="measurement",
                spatial_scope="raster" if grid_spec is not None else "plot",
                scope_id=raster_id if grid_spec is not None else plot_id,
                observed_at=run_timestamp,
                confidence=confidence_val,
                sigma=sigma,
                reliability=min(0.95, 0.6 + 0.005 * stats["count"]),
                freshness_score=1.0,
                provenance_ref=f"raster_ingest_{raster_id}",
                flags=list(evidence_flags),
                grounding_class=grounding_class,
                **ev_fields
            )
            evidence.append(normalize_evidence_truth(item, source_context=raster_data))

    return evidence, raster_refs


def _compute_pixel_hash(
    pixel_array: List[List[float]],
    grid_spec: Optional[Dict[str, Any]] = None,
    native_resolution_m: Optional[float] = None,
) -> str:
    """Deterministic hash of pixel data and grid geometry."""
    h = len(pixel_array) if pixel_array else 0
    w = len(pixel_array[0]) if (pixel_array and isinstance(pixel_array[0], list)) else 0
    flat = [f"shape={h}x{w}"]
    if native_resolution_m is not None:
        flat.append(f"res={native_resolution_m}")
    if grid_spec is not None:
        flat.append(f"crs={grid_spec.get('crs')}")
        flat.append(f"transform={grid_spec.get('transform') or grid_spec.get('affine')}")
        flat.append(f"bounds={grid_spec.get('bounds')}")
    for row in pixel_array:
        if isinstance(row, list):
            for v in row:
                if v is not None and v == v:  # not NaN
                    flat.append(f"{v:.6f}")
                else:
                    flat.append("NaN")
        else:
            flat.append(f"{row:.6f}" if (row is not None and row == row) else "NaN")
    raw = ",".join(flat).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _compute_plot_stats(pixel_array: List[List[float]]) -> Dict[str, float]:
    """Compute mean, std, count from 2D pixel array (ignoring NaN/None)."""
    values = []
    for row in pixel_array:
        for v in row:
            if v is not None and v == v:  # not NaN
                values.append(float(v))

    if not values:
        return {"mean": 0.0, "std": 0.0, "count": 0}

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return {
        "mean": round(mean, 6),
        "std": round(math.sqrt(variance), 6),
        "count": len(values),
    }


def _compute_zonal_stats(
    pixel_array: List[List[float]],
    mask: List[List[int]],
) -> Dict[str, float]:
    """Compute stats for pixels within a zone mask."""
    values = []
    H = min(len(pixel_array), len(mask))
    for y in range(H):
        W = min(len(pixel_array[y]), len(mask[y]))
        for x in range(W):
            if mask[y][x] == 1:
                v = pixel_array[y][x]
                if v is not None and v == v:
                    values.append(float(v))

    if not values:
        return {"mean": 0.0, "std": 0.0, "count": 0}

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return {
        "mean": round(mean, 6),
        "std": round(math.sqrt(variance), 6),
        "count": len(values),
    }


def _compute_raster_sigma(std: float, count: int, resolution_m: float) -> float:
    """Compute sigma from pixel statistics.

    Lower sigma (higher precision) when:
    - More valid pixels (sqrt(count) reduction)
    - Lower pixel variance (std)
    - Finer resolution (inverse penalty for coarse grids)
    """
    base_sigma = max(0.01, std)
    pixel_reduction = 1.0 / math.sqrt(max(1, count))
    resolution_penalty = max(1.0, resolution_m / 10.0)  # 10m = baseline
    return round(base_sigma * pixel_reduction * resolution_penalty, 4)


def check_asmae_authority(output: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    prov = output.get("provenance") or {}
    diag = output.get("diagnostics") or {}

    # 1. grid_spec valid
    grid_spec = output.get("grid_spec")
    if not isinstance(grid_spec, dict):
        return False, "missing_grid_spec"
    res_decision = output.get("resolution_decision") or {}
    normalized_grid, grid_reason = normalize_geographic_grid_contract(
        crs=grid_spec.get("crs"),
        bounds=grid_spec.get("bounds"),
        transform=grid_spec.get("transform", grid_spec.get("affine")),
        width=grid_spec.get("width"),
        height=grid_spec.get("height"),
        resolution_m=grid_spec.get(
            "resolution_m",
            grid_spec.get(
                "resolution",
                res_decision.get("selected_effective_resolution_m"),
            ),
        ),
    )
    if normalized_grid is None:
        return False, f"invalid_grid_spec:{grid_reason}"

    # 2. operator locked
    if prov.get("operator_locked") is not True and diag.get("operator_locked") is not True:
        return False, "operator_not_locked"
        
    # 3. graph locked
    if prov.get("graph_locked") is not True and diag.get("graph_locked") is not True:
        return False, "graph_not_locked"
        
    # 4. radiometric checked
    rad_mode = prov.get("radiometric_mode") or diag.get("radiometric_mode")
    if rad_mode != "ht_per_pixel":
        return False, "radiometric_not_ht_per_pixel"
    if prov.get("full_radiometric_credit_allowed") is not True and diag.get("full_radiometric_credit_allowed") is not True:
        return False, "radiometric_credit_not_allowed"
        
    # 5. EnKF full credit
    e_mode = prov.get("enkf_mode") or diag.get("enkf_mode")
    if e_mode != "ht_per_pixel":
        return False, "enkf_not_ht_per_pixel"
    if prov.get("full_enkf_credit_allowed") is not True and diag.get("full_enkf_credit_allowed") is not True:
        return False, "enkf_credit_not_allowed"
        
    if prov.get("has_enkf_proxy_fallback") is True or diag.get("has_enkf_proxy_fallback") is True:
        return False, "enkf_proxy_fallback"
        
    # 6. retrovalidation passed (exists and valid)
    retro_score = prov.get("retrovalidation_score")
    if retro_score is None:
        retro_score = diag.get("retro_mean_score")
    if retro_score is None:
        return False, "retrovalidation_missing"
    if float(retro_score) < 0.7:
        return False, "retrovalidation_score_too_low"
        
    # 7. BMA confidence acceptable (disagreement <= 0.3)
    bma_dis = prov.get("bma_disagreement")
    if bma_dis is None:
        bma_dis = diag.get("bma_mean_disagreement")
    if bma_dis is not None and float(bma_dis) > 0.3:
        return False, "bma_disagreement_too_high"
        
    return True, None


def ingest_asmae_raster_refs(output: Dict[str, Any], plot_id: str) -> List[RasterRef]:
    """Ingest ASMAE raster maps (states, uncertainties, confidences, retrovalidation, BMA)
    into RasterRefs with appropriate channels and flags.
    """
    if not isinstance(output, dict) or output.get("status") not in ("success", "partial"):
        return []

    from .adapters.asmae_adapter import asmae_state_evidence_allowed

    res_decision = output.get("resolution_decision") or {}
    grid_spec = output.get("grid_spec")
    if not isinstance(grid_spec, dict):
        return []
    selected_resolution = res_decision.get(
        "selected_effective_resolution_m",
        grid_spec.get("resolution_m", grid_spec.get("resolution")),
    )
    normalized_grid, _ = normalize_geographic_grid_contract(
        crs=grid_spec.get("crs"),
        bounds=grid_spec.get("bounds"),
        transform=grid_spec.get("transform", grid_spec.get("affine")),
        width=grid_spec.get("width"),
        height=grid_spec.get("height"),
        resolution_m=grid_spec.get(
            "resolution_m", grid_spec.get("resolution", selected_resolution)
        ),
    )
    if normalized_grid is None:
        # ASMAE metadata remains available to the plot-level diagnostic path,
        # but no RasterRef is admitted without a complete geographic contract.
        return []
    try:
        res_m = float(selected_resolution)
    except (TypeError, ValueError):
        return []
    if not math.isfinite(res_m) or res_m <= 0:
        return []

    state_allowed = asmae_state_evidence_allowed(output)
    crs = normalized_grid["crs"]
    bounds = normalized_grid["bounds"]
    transform = normalized_grid["transform"]
    grid_width = normalized_grid["width"]
    grid_height = normalized_grid["height"]

    # Authority and block reasons
    auth_ok, block_reason = check_asmae_authority(output)
    state_allowed = state_allowed and auth_ok
    prescription_allowed = auth_ok

    # Determine channel for state variables if state update is blocked
    if state_allowed:
        state_channel = "state_evidence"
    else:
        state_channel = "visual" if res_m <= 1 else "diagnostic"

    raster_refs: List[RasterRef] = []

    def build_ref(var_name: str, pixel_array: List[List[float]], channel: str, is_state: bool) -> Optional[RasterRef]:
        if not raster_grid_matches_dimensions(pixel_array, grid_height, grid_width):
            return None
        H = grid_height
        W = grid_width
        
        # Compute valid pixel count and observed ratio
        valid_count = sum(1 for r in pixel_array for v in r if v is not None and v == v)
        total_cells = H * W
        observed_ratio = float(valid_count / total_cells) if total_cells > 0 else 0.0
        
        # Compute content hash
        content_hash = _compute_pixel_hash(pixel_array, grid_spec=normalized_grid, native_resolution_m=res_m)
        
        # Determine trust parameters
        ref_state_allowed = state_allowed if is_state else False
        ref_diagnostic_only = not ref_state_allowed
        ref_prescription_allowed = prescription_allowed if is_state else False
        
        # Pull trust score and diagnostics
        diag = output.get("diagnostics", {}) or {}
        prov = output.get("provenance") or {}

        def finite_support_mean(group_name: str, preferred_key: str):
            group = output.get(group_name) or {}
            grid = group.get(preferred_key)
            if not isinstance(grid, list):
                return None
            values = []
            for row in grid:
                if not isinstance(row, list):
                    continue
                for value in row:
                    try:
                        number = float(value)
                    except (TypeError, ValueError):
                        continue
                    if math.isfinite(number):
                        values.append(number)
            return sum(values) / len(values) if values else None

        post_conc_mean = finite_support_mean("confidence_maps", "ASMAE_POSTERIOR_CONCENTRATION")
        if post_conc_mean is None:
            post_conc_mean = finite_support_mean("confidence_maps", "ASMAE_CONFIDENCE")
        uncertainty_mean = finite_support_mean("uncertainty_maps", "ASMAE_UNCERTAINTY")
        post_conc_val = float(post_conc_mean) if post_conc_mean is not None else 0.0
        unc_val = float(uncertainty_mean) if uncertainty_mean is not None else 1.0

        archive_used = prov.get("sentinel_archive_used") or diag.get("sentinel_archive_used") or False
        archive_count = prov.get("archive_scene_count") or diag.get("archive_scene_count") or 0
        archive_date_range = prov.get("archive_date_range") or diag.get("archive_date_range")
        scene_stack_mode = prov.get("scene_stack_mode") or diag.get("scene_stack_mode")

        # Sanitize raster ID prefix
        ref_id_prefix = var_name if var_name.lower().startswith("asmae_") else f"asmae_{var_name}"

        # Build RasterRef
        return RasterRef(
            raster_id=f"{ref_id_prefix}_{content_hash[:8]}",
            variable=var_name,
            resolution_m=res_m,
            content_hash=content_hash,
            width=W,
            height=H,
            crs=crs,
            bounds=bounds,
            transform=transform,
            grid=pixel_array,
            artifact_ref=None,
            valid_pixel_count=valid_count,
            observed_ratio=observed_ratio,
            production_usable=auth_ok and is_state,
            visualization_allowed=True,
            experimental_visual_allowed=True,
            scientific_surface_allowed=ref_state_allowed,
            state_update_allowed=ref_state_allowed,
            observed_spatial_surface=False,
            diagnostic_only=ref_diagnostic_only,
            asmae_channel=channel,
            source_basis="asmae",
            confidence=None,
            uncertainty=unc_val,
            archive_scene_count=archive_count,
            archive_date_range=archive_date_range,
            scene_stack_mode=scene_stack_mode,
        )

    # Ingest state maps
    for var, grid in output.get("raster_maps", {}).items():
        var_name = var if var.lower().startswith("asmae_") else f"asmae_{var}"
        ref = build_ref(var_name, grid, state_channel, is_state=True)
        if ref:
            raster_refs.append(ref)

    # Ingest uncertainty maps
    for var, grid in output.get("uncertainty_maps", {}).items():
        if var == "ASMAE_UNCERTAINTY":
            var_name = "asmae_uncertainty"
        else:
            var_name = var if var.lower().startswith("asmae_") else f"asmae_{var}_uncertainty"
        ref = build_ref(var_name, grid, "diagnostic", is_state=False)
        if ref:
            raster_refs.append(ref)

    # Ingest confidence maps (deduplicated to single canonical asmae_posterior_concentration raster)
    ingested_confidence_vars = set()
    for var, grid in output.get("confidence_maps", {}).items():
        if var in ("ASMAE_CONFIDENCE", "CONFIDENCE_ASMAE", "ASMAE_POSTERIOR_CONCENTRATION"):
            canonical_key = "asmae_posterior_concentration"
            if canonical_key in ingested_confidence_vars:
                continue
            ingested_confidence_vars.add(canonical_key)
            var_name = canonical_key
            ref = build_ref(var_name, grid, "diagnostic", is_state=False)
            if ref and isinstance(ref, dict):
                ref.setdefault("metadata", {})["legacy_aliases"] = ["ASMAE_CONFIDENCE", "CONFIDENCE_ASMAE"]
                ref["metadata"]["canonical_name"] = "ASMAE_POSTERIOR_CONCENTRATION"
                raster_refs.append(ref)
        else:
            var_name = var if var.lower().startswith("asmae_") else f"asmae_{var}_confidence"
            ref = build_ref(var_name, grid, "diagnostic", is_state=False)
            if ref:
                raster_refs.append(ref)


    # Ingest retrovalidation maps
    for var, grid in output.get("retrovalidation_maps", {}).items():
        if var == "ASMAE_RETROVALIDATION_SCORE":
            var_name = "asmae_retrovalidation_score"
        else:
            var_name = var if var.lower().startswith("asmae_") else f"asmae_{var}_retrovalidation"
        ref = build_ref(var_name, grid, "diagnostic", is_state=False)
        if ref:
            raster_refs.append(ref)

    # Ingest BMA maps
    for var, grid in output.get("bma_maps", {}).items():
        if var == "ASMAE_BMA_DISAGREEMENT":
            var_name = "asmae_bma_disagreement"
        else:
            var_name = var if var.lower().startswith("asmae_") else f"asmae_{var}_bma"
        ref = build_ref(var_name, grid, "diagnostic", is_state=False)
        if ref:
            raster_refs.append(ref)

    return raster_refs
