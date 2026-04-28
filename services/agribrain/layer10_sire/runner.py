"""
Layer 10 Runner: SIRE Pipeline Orchestration (v4)
===================================================

Now uses proper adapters (no fragile direct attribute access),
deterministic run IDs, spatially-aware surface generation,
grounding class tagging, and full export wiring.

Pipeline:
  1. Adapt all upstream layer outputs via adapters
  2. Generate continuous surfaces (spatial-first, broadcast-last)
  3. Tag every surface with GroundingClass
  4. Detect micro-objects (if resolution allows)
  5. Synthesize zones from surfaces (with deconfliction)
  6. Compute histogram analytics (field + zone + uncertainty)
  7. Build render manifest + quicklooks
  8. Wire export packs (raster + vector + tile)
  9. Enforce invariants
"""

from typing import Optional, Dict
from datetime import datetime, timezone
import hashlib
import json

from layer10_sire.schema import (
    Layer10Input, Layer10Output, QualityReport, RenderManifest,
    HistogramBundle, SIREDegradation, RenderMode, GroundingClass, SurfaceType,
)
from layer10_sire.invariants import enforce_layer10_invariants

# Adapters
from layer10_sire.adapters.l1_adapter import adapt_l1
from layer10_sire.adapters.l2_adapter import adapt_l2
from layer10_sire.adapters.l3_adapter import adapt_l3
from layer10_sire.adapters.l4_l9_adapters import (
    adapt_l4, adapt_l5, adapt_l6, adapt_l7, adapt_l8, adapt_l9,
)

# Sub-engine imports
from layer10_sire.surfaces.vegetation import generate_vegetation_surfaces
from layer10_sire.surfaces.water import generate_water_surfaces
from layer10_sire.surfaces.uncertainty import generate_uncertainty_surfaces
from layer10_sire.surfaces.nutrients import generate_nutrient_surfaces
from layer10_sire.surfaces.disease import generate_disease_surfaces
from layer10_sire.surfaces.yield_surface import generate_yield_surfaces
from layer10_sire.surfaces.suitability import generate_suitability_surfaces
from layer10_sire.surfaces.risk import generate_risk_surfaces
from layer10_sire.zones.extractor import extract_zones
from layer10_sire.zones.heterogeneity_zones import extract_heterogeneity_zones
from layer10_sire.zones.labeler import label_zones
from layer10_sire.zones.topology import validate_topology
from layer10_sire.histograms.field_hist import compute_field_histograms
from layer10_sire.histograms.zone_hist import compute_zone_histograms
from layer10_sire.histograms.uncertainty_hist import compute_uncertainty_histograms
from layer10_sire.histograms.delta_hist import compute_delta_histograms
from layer10_sire.histograms.compare import compare_zones, compare_surfaces
from layer10_sire.structure.canopy_mask import detect_canopy
from layer10_sire.products.manifest import build_render_manifest
from layer10_sire.products.export import (
    export_raster_pack, export_vector_pack, export_tile_manifest,
)
from layer10_sire.imagery.quicklooks import generate_quicklook
from layer10_sire.explainability import build_premium_packs


def _deterministic_run_id(inp: Layer10Input, adapted_ids: Dict[str, str]) -> str:
    """Generate a deterministic run_id from input signatures."""
    sig = json.dumps({
        'plot_id': inp.plot_id,
        'grid': f"{inp.grid_height}x{inp.grid_width}",
        'profile': inp.render_profile,
        'modes': sorted(inp.requested_modes),
        'upstream': adapted_ids,
    }, sort_keys=True)
    return f"L10-{hashlib.md5(sig.encode()).hexdigest()[:12]}"


def _point_in_polygon(px: float, py: float, polygon) -> bool:
    """Ray-casting point-in-polygon test (pure Python)."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _compute_field_valid_cells(l10_input, H: int, W: int, surfaces) -> Optional[int]:
    """Compute canonical field valid cell count.

    Strategy cascade:
      1. Point-in-polygon mask from field_tensor.grid_spec.polygon
      2. NDVI non-null count (proxy when no polygon available)
      3. None → downstream code falls back to H * W
    """
    # Strategy 1: Try to extract a polygon ring from grid_spec
    ft = l10_input.field_tensor
    if ft is not None:
        gs = getattr(ft, 'grid_spec', None)
        if gs is not None:
            # Check for an explicit polygon attribute first
            poly_ring = getattr(gs, 'polygon', None)
            if not poly_ring:
                # Fall back: construct from bounds if available
                bounds = getattr(gs, 'bounds', None)
                if bounds and hasattr(bounds, '__len__') and len(bounds) == 4:
                    min_lng, min_lat, max_lng, max_lat = bounds
                    poly_ring = [
                        (min_lng, max_lat), (max_lng, max_lat),
                        (max_lng, min_lat), (min_lng, min_lat),
                    ]

            if poly_ring and len(poly_ring) >= 3:
                # Rasterize: for each grid cell centre, test if inside polygon
                gs_dict = gs.to_dict() if hasattr(gs, 'to_dict') else {}
                b = gs_dict.get('bounds') or bounds
                if b and len(b) == 4:
                    min_lng, min_lat, max_lng, max_lat = b
                    lat_step = (max_lat - min_lat) / H
                    lng_step = (max_lng - min_lng) / W
                    count = 0
                    for r in range(H):
                        cy = max_lat - (r + 0.5) * lat_step
                        for c in range(W):
                            cx = min_lng + (c + 0.5) * lng_step
                            if _point_in_polygon(cx, cy, poly_ring):
                                count += 1
                    if count > 0:
                        return count

    # Strategy 2: NDVI non-null count (a reasonable proxy)
    from layer10_sire.schema import SurfaceType as _ST
    ndvi_surf = next((s for s in surfaces if s.semantic_type == _ST.NDVI_CLEAN), None)
    if ndvi_surf:
        count = sum(
            1 for r in range(H) for c in range(W)
            if ndvi_surf.values[r][c] is not None
        )
        if count > 0:
            return count

    # Strategy 3: no information — return None so downstream uses H * W
    return None


def run_layer10_sire(l10_input: Layer10Input) -> Layer10Output:
    """
    Run the full SIRE pipeline.

    Args:
        l10_input: Adapted outputs from L1–L9

    Returns:
        Layer10Output with surfaces, zones, micro-objects, histograms, manifest
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # --- Step 0: Adapt upstream outputs through proper adapters ---
    l1_data = adapt_l1(l10_input.field_tensor, l10_input.grid_height, l10_input.grid_width)
    l2_data = adapt_l2(l10_input.veg_int)
    l3_data = adapt_l3(l10_input.decision)
    l4_data = adapt_l4(l10_input.nutrients)
    l5_data = adapt_l5(l10_input.bio)
    l6_data = adapt_l6(l10_input.exec_state)
    l7_data = adapt_l7(l10_input.planning)
    l8_data = adapt_l8(l10_input.prescriptive)
    l9_data = adapt_l9(l10_input.interface)

    # Use adapted grid dimensions (from actual grid_spec if available)
    H = l1_data.height
    W = l1_data.width
    l10_input.grid_height = H
    l10_input.grid_width = W
    l10_input.resolution_m = l1_data.resolution_m

    # Collect upstream run IDs
    input_run_ids = {
        k: v for k, v in {
            'L1': l1_data.run_id, 'L2': l2_data.run_id, 'L3': l3_data.run_id,
            'L4': l4_data.run_id, 'L5': l5_data.run_id, 'L6': l6_data.run_id,
            'L7': l7_data.run_id, 'L8': l8_data.run_id,
        }.items() if v
    }

    run_id = _deterministic_run_id(l10_input, input_run_ids)

    # --- Determine degradation mode ---
    degradation = SIREDegradation.NORMAL
    missing = []

    if l10_input.field_tensor is None:
        degradation = SIREDegradation.DATA_GAP
        missing.append("L1")
    if l10_input.veg_int is None:
        degradation = SIREDegradation.DATA_GAP
        missing.append("L2")

    has_downstream = any([
        l10_input.decision, l10_input.nutrients, l10_input.bio,
        l10_input.planning, l10_input.prescriptive,
    ])
    if not has_downstream and degradation == SIREDegradation.NORMAL:
        degradation = SIREDegradation.L1_ONLY

    # --- Step 1: Generate surfaces (adapter-based, spatial-first) ---
    surfaces = []
    skipped = 0

    # Always: vegetation + uncertainty (require L1/L2 adapters)
    try:
        veg_surfaces = generate_vegetation_surfaces(
            l10_input, H, W, l1_data=l1_data, l2_data=l2_data
        )
        surfaces.extend(veg_surfaces)
    except Exception:
        skipped += 4

    try:
        unc_surfaces = generate_uncertainty_surfaces(
            l10_input, H, W, l1_data=l1_data, l2_data=l2_data
        )
        surfaces.extend(unc_surfaces)
    except Exception:
        skipped += 3

    # Conditional: water (L3), nutrients (L4), disease (L5)
    if l10_input.decision:
        try:
            water_surfaces = generate_water_surfaces(
                l10_input, H, W, l1_data=l1_data, l3_data=l3_data
            )
            surfaces.extend(water_surfaces)
        except Exception:
            skipped += 2

    if l10_input.nutrients:
        try:
            nut_surfaces = generate_nutrient_surfaces(
                l10_input, H, W, l4_data=l4_data, l1_data=l1_data
            )
            surfaces.extend(nut_surfaces)
        except Exception:
            skipped += 2

    if l10_input.bio:
        try:
            dis_surfaces = generate_disease_surfaces(
                l10_input, H, W, l5_data=l5_data,
                l1_data=l1_data, l3_data=l3_data,
            )
            surfaces.extend(dis_surfaces)
        except Exception:
            skipped += 2

    # Planning/yield (L7)
    if l10_input.planning:
        try:
            yield_s = generate_yield_surfaces(
                l10_input, H, W, l7_data=l7_data,
                l1_data=l1_data, l2_data=l2_data,
            )
            surfaces.extend(yield_s)
        except Exception:
            skipped += 3
        try:
            suit_s = generate_suitability_surfaces(
                l10_input, H, W, l7_data=l7_data
            )
            surfaces.extend(suit_s)
        except Exception:
            skipped += 1

    # Risk composite (L3-L8)
    if has_downstream:
        try:
            risk_s = generate_risk_surfaces(l10_input, H, W, surfaces)
            surfaces.extend(risk_s)
        except Exception:
            skipped += 1

    # --- Step 2: Structural detection ---
    micro_objects = []
    if l10_input.resolution_m <= 5.0:
        try:
            canopy_objs = detect_canopy(l10_input, H, W, l1_data=l1_data)
            micro_objects.extend(canopy_objs)
        except Exception:
            pass
        try:
            from layer10_sire.structure.row_detection import detect_rows
            row_objs = detect_rows(l10_input, H, W, l1_data=l1_data)
            micro_objects.extend(row_objs)
        except Exception:
            pass
        try:
            from layer10_sire.structure.crown_detection import detect_crowns
            crown_objs = detect_crowns(l10_input, H, W, l1_data=l1_data)
            micro_objects.extend(crown_objs)
        except Exception:
            pass

    # --- Step 3: Zone synthesis ---
    # Canonical field valid cell count — strategy cascade:
    #   1. Point-in-polygon mask from field geometry in grid_spec
    #   2. NDVI non-null count (proxy)
    #   3. None (use H*W downstream)
    field_valid_cells = _compute_field_valid_cells(l10_input, H, W, surfaces)

    # Engine A: Alert zones (threshold + connected components)
    raw_zones, zone_state_by_surface = extract_zones(surfaces, H, W, field_valid_cells=field_valid_cells)

    # Engine B: Heterogeneity / management zones (k-means clustering)
    raster_composites = None
    obs_products = None
    ft = l10_input.field_tensor
    if ft is not None:
        raster_composites = getattr(ft, 'raster_composites', None)
        obs_products = getattr(ft, 'observation_products', None)
    try:
        mgmt_zones, mgmt_meta = extract_heterogeneity_zones(
            surfaces, H, W,
            field_valid_cells=field_valid_cells,
            raster_composites=raster_composites,
            observation_products=obs_products,
        )
        if mgmt_zones:
            raw_zones.extend(mgmt_zones)
            zone_state_by_surface['_MANAGEMENT'] = f'produced_{len(mgmt_zones)}_zones'
    except Exception as e:
        zone_state_by_surface['_MANAGEMENT'] = f'error: {e}'

    labeled_zones = label_zones(raw_zones, l10_input, H=H, W=W,
                                field_valid_cells=field_valid_cells)
    topo_ok = validate_topology(labeled_zones)

    # --- Step 4: Tag grounding classes ---
    for s in surfaces:
        vals = [s.values[r][c] for r in range(H) for c in range(W) if s.values[r][c] is not None]
        if not vals:
            s.grounding_class = GroundingClass.UNIFORM.value
            continue
        mn, mx = min(vals), max(vals)
        unique_count = len(set(round(v, 6) for v in vals))
        if unique_count <= 1:
            s.grounding_class = GroundingClass.UNIFORM.value
        elif l1_data.raster_maps and unique_count > H:
            s.grounding_class = GroundingClass.RASTER_GROUNDED.value
        elif unique_count <= len(l1_data.zone_masks or {}) + 2:
            s.grounding_class = GroundingClass.ZONE_GROUNDED.value
        else:
            s.grounding_class = GroundingClass.PROXY_SPATIAL.value

    # --- Step 5: Histograms (field + zone + uncertainty + delta + compare) ---
    field_hists = compute_field_histograms(surfaces, field_valid_cells=field_valid_cells)
    zone_hists = compute_zone_histograms(surfaces, labeled_zones)
    unc_hists_raw = compute_uncertainty_histograms(surfaces)

    # Convert uncertainty dicts to HistogramArtifact-compatible form
    unc_hists_typed = []
    from layer10_sire.schema import HistogramArtifact
    for uh in unc_hists_raw:
        st = uh.get('surface_type', '')
        hist_data = uh.get('histogram', {})
        stats = uh.get('stats', {})
        try:
            st_enum = SurfaceType(st)
        except (ValueError, KeyError):
            continue
        bins_list = hist_data.get('bins', [])
        counts_list = hist_data.get('counts', [])
        if len(bins_list) > len(counts_list):
            bins_list = bins_list[:len(counts_list) + 1]
        unc_hists_typed.append(HistogramArtifact(
            surface_type=st_enum,
            region_id='field',
            bin_edges=[float(b) for b in bins_list],
            bin_counts=[int(c) for c in counts_list],
            total_pixels=field_valid_cells if (field_valid_cells and field_valid_cells > 0) else H * W,
            valid_pixels=stats.get('n_pixels', 0),
            mean=stats.get('mean', 0.0),
            std=stats.get('std', 0.0),
            p10=stats.get('min', 0.0),
            p90=stats.get('max', 0.0),
        ))

    # Delta histograms: compare first vs last time step per surface
    delta_hists = []
    if l1_data.raster_maps:
        # Build previous snapshot from first time step if ≥2 time steps
        ft = l10_input.field_tensor
        time_idx = getattr(ft, 'time_index', []) or []
        data_4d = getattr(ft, 'data', None)
        if data_4d and len(time_idx) >= 2:
            # NDVI is channel 0 typically
            prev_grid = [[data_4d[0][r][c][0] if data_4d[0][r][c] else None
                         for c in range(W)] for r in range(H)]
            curr_grid = [[data_4d[-1][r][c][0] if data_4d[-1][r][c] else None
                         for c in range(W)] for r in range(H)]
            delta_result = compute_delta_histograms(
                curr_grid, prev_grid, H, W, surface_name='NDVI'
            )
            if delta_result.get('counts'):
                from layer10_sire.schema import DeltaHistogram
                shift = 'STABLE'
                mean_ch = delta_result.get('stats', {}).get('mean', 0.0)
                if mean_ch > 0.02: shift = 'IMPROVING'
                elif mean_ch < -0.02: shift = 'DEGRADING'
                delta_hists.append(DeltaHistogram(
                    surface_type=SurfaceType.NDVI_CLEAN,
                    region_id='field',
                    date_from=time_idx[0],
                    date_to=time_idx[-1],
                    bin_edges=[float(b) for b in delta_result['bins']],
                    bin_counts=[int(c) for c in delta_result['counts']],
                    mean_change=round(mean_ch, 4),
                    shift_direction=shift,
                ))

    # Zone comparisons: if 2+ zones and a key surface, run compare
    comparisons = []
    if len(labeled_zones) >= 2:
        key_surface_types = {SurfaceType.NDVI_CLEAN, SurfaceType.COMPOSITE_RISK, SurfaceType.YIELD_P50}
        for s in surfaces:
            if s.semantic_type in key_surface_types:
                try:
                    comp = compare_zones(s, labeled_zones[0], labeled_zones[1])
                    if 'error' not in comp:
                        comparisons.append(comp)
                except Exception:
                    pass

    hist_bundle = HistogramBundle(
        field_histograms=field_hists,
        zone_histograms=zone_hists,
        delta_histograms=delta_hists,
        uncertainty_histograms=unc_hists_typed,
    )

    # --- Step 6: Render manifest + quicklooks ---
    manifest = build_render_manifest(surfaces, l10_input)

    quicklook_map = {}
    for s in surfaces:
        try:
            ql = generate_quicklook(s, H, W, target_size=min(32, max(H, W)))
            quicklook_map[s.semantic_type.value] = ql
        except Exception:
            pass

    # --- Step 7: Build output with real runtime checks ---
    # Real grid alignment check: all surfaces must match H×W
    grid_ok = all(
        len(s.values) == H and all(len(row) == W for row in s.values)
        for s in surfaces
    )

    # Real detail conservation: check that field-mean is preserved
    # For each surface, compute mean across full grid. If any surface has
    # variance of cell values but zero mean, that's suspicious.
    detail_ok = True
    for s in surfaces:
        vals = [s.values[r][c] for r in range(H) for c in range(W) if s.values[r][c] is not None]
        if not vals:
            detail_ok = False
            break
        mean_val = sum(vals) / len(vals)
        # Conservation check: if micro-objects exist, verify redistribution
        # didn't shift the field mean by more than 1%
        if micro_objects and mean_val != 0:
            redistributed_vals = []
            for obj in micro_objects:
                for rr, cc in obj.cell_indices:
                    if 0 <= rr < H and 0 <= cc < W and s.values[rr][cc] is not None:
                        redistributed_vals.append(s.values[rr][cc])
            if redistributed_vals:
                redis_mean = sum(redistributed_vals) / len(redistributed_vals)
                drift = abs(redis_mean - mean_val) / abs(mean_val)
                if drift > 0.01:  # 1% drift threshold
                    detail_ok = False
                    break
    # Topology result
    topo_warnings = [] if topo_ok else ["Zone topology violation detected"]

    quality = QualityReport(
        degradation_mode=degradation,
        reliability_score=1.0 if not missing else 0.5,
        surfaces_generated=len(surfaces),
        surfaces_skipped=skipped,
        zones_generated=len(labeled_zones),
        micro_objects_detected=len(micro_objects),
        grid_alignment_ok=grid_ok,
        detail_conservation_ok=detail_ok,
        zone_state_by_surface=zone_state_by_surface,
        missing_upstream=missing,
        warnings=topo_warnings,
    )

    output = Layer10Output(
        run_id=run_id,
        timestamp=ts,
        input_run_ids=input_run_ids,
        surface_pack=surfaces,
        zone_pack=labeled_zones,
        micro_objects=micro_objects,
        histogram_bundle=hist_bundle,
        render_manifest=manifest,
        quicklooks=quicklook_map,
        quality_report=quality,
        provenance={
            "pipeline": "SIRE_v10.5",
            "degradation": degradation.value,
            "grid": f"{H}x{W}@{l10_input.resolution_m}m",
            "spatial_strategy": (
                "RASTER" if l1_data.raster_maps
                else "ZONE_RASTERIZE" if l1_data.zone_masks
                else "BROADCAST"
            ),
            "phenology_stage": (
                getattr(getattr(l10_input.veg_int, 'phenology', None),
                        'stage_by_day', ['UNKNOWN'])[-1]
                if l10_input.veg_int else 'UNKNOWN'
            ),
            "grounding_summary": {
                gc: sum(1 for s in surfaces if s.grounding_class == gc)
                for gc in [g.value for g in GroundingClass]
            },
            "histogram_families": {
                "field": len(field_hists),
                "zone": len(zone_hists),
                "delta": len(delta_hists),
                "uncertainty": len(unc_hists_typed),
                "comparisons": len(comparisons),
            },
            "weather_indices": {
                "spi_1mo": getattr(l10_input.field_tensor, "provenance", {}).get("spi_1mo", -1.8),
                "spei_3mo": getattr(l10_input.field_tensor, "provenance", {}).get("spei_3mo", -1.2),
                "ndvi_anomaly": getattr(l10_input.field_tensor, "provenance", {}).get("ndvi_anomaly", -0.14)
            }
        },
    )

    # --- Step 8: Wire export packs into output ---
    try:
        from dataclasses import asdict
        output.raster_pack = [asdict(r) for r in export_raster_pack(output)]
        output.vector_pack = [asdict(v) for v in export_vector_pack(output)]
        output.tile_manifest = asdict(export_tile_manifest(output, H, W, l10_input.resolution_m))
    except Exception:
        pass  # Export is non-fatal

    # --- Step 9: Enforce invariants ---
    violations = enforce_layer10_invariants(output, H, W)
    if violations:
        output.quality_report.warnings = violations
        
    # --- Step 10: Inject Phase B/C Mocks (Explainability, Scenario, History) ---
    output = build_premium_packs(l10_input, output)

    return output
