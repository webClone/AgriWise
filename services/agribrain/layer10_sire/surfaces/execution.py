"""
Execution Surface Engine — L6/L8 Intervention Intelligence Surfaces
=====================================================================

Generates spatial surfaces from L6 (Strategic Execution) and L8 (Prescriptive)
to represent intervention readiness, priority, timing, and conflict resolution.

Surfaces produced:
  - EXECUTION_READINESS: Per-zone readiness score from L6 feasibility grades
  - INTERVENTION_PRIORITY: Per-zone action priority from L8 × L6 utility
  - INTERVENTION_TIMING: Optimal timing overlay from L8 schedule
  - CONFLICT_RESOLUTION: Cross-layer conflict heatmap from L6 conflict log
"""
from typing import List, Optional, Dict
from layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from layer10_sire.adapters.l1_adapter import L1SpatialData
from layer10_sire.adapters.l4_l9_adapters import L6ExecData, L8ActionData


# Feasibility grade to numeric score
FEASIBILITY_SCORES = {
    'A': 0.95, 'B': 0.80, 'C': 0.60, 'D': 0.40, 'F': 0.15,
    'HIGH': 0.9, 'MEDIUM': 0.6, 'LOW': 0.3,
    'UNKNOWN': 0.5,
}


def generate_execution_surfaces(
    inp: Layer10Input, H: int, W: int,
    l6_data: Optional[L6ExecData] = None,
    l8_data: Optional[L8ActionData] = None,
    l1_data: Optional[L1SpatialData] = None,
) -> List[SurfaceArtifact]:
    """Generate L6/L8 execution intelligence surfaces."""
    surfaces = []

    if l6_data is None:
        from layer10_sire.adapters.l4_l9_adapters import adapt_l6
        l6_data = adapt_l6(inp.exec_state)
    if l8_data is None:
        from layer10_sire.adapters.l4_l9_adapters import adapt_l8
        l8_data = adapt_l8(inp.prescriptive)
    if l1_data is None:
        from layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)

    # --- 1. EXECUTION_READINESS ---
    readiness = _compute_readiness(l6_data, l1_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"EXEC_READY_{inp.plot_id}",
        semantic_type=SurfaceType.EXECUTION_READINESS,
        grid_ref=f"{H}x{W}",
        values=readiness,
        units="score",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L6"],
        provenance={
            "n_interventions": len(l6_data.interventions),
            "execution_confidence": l6_data.execution_confidence,
        },
    ))

    # --- 2. INTERVENTION_PRIORITY ---
    priority = _compute_priority(l6_data, l8_data, l1_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"INTV_PRIORITY_{inp.plot_id}",
        semantic_type=SurfaceType.INTERVENTION_PRIORITY,
        grid_ref=f"{H}x{W}",
        values=priority,
        units="score",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.RISK_HEAT,
        source_layers=["L6", "L8"],
    ))

    # --- 3. INTERVENTION_TIMING ---
    timing = _compute_timing(l8_data, l1_data, H, W)
    surfaces.append(SurfaceArtifact(
        surface_id=f"INTV_TIMING_{inp.plot_id}",
        semantic_type=SurfaceType.INTERVENTION_TIMING,
        grid_ref=f"{H}x{W}",
        values=timing,
        units="urgency",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.STRESS_RED,
        source_layers=["L8"],
    ))

    # --- 4. CONFLICT_RESOLUTION ---
    if l6_data.conflict_log:
        conflict = _compute_conflict(l6_data, l1_data, H, W)
        surfaces.append(SurfaceArtifact(
            surface_id=f"CONFLICT_RES_{inp.plot_id}",
            semantic_type=SurfaceType.CONFLICT_RESOLUTION,
            grid_ref=f"{H}x{W}",
            values=conflict,
            units="score",
            native_resolution_m=inp.resolution_m,
            render_range=(0.0, 1.0),
            palette_id=PaletteId.DISEASE_ORANGE,
            source_layers=["L6"],
            provenance={"n_conflicts": len(l6_data.conflict_log)},
        ))

    return surfaces


# ============================================================================
# INTERNAL COMPUTATION FUNCTIONS
# ============================================================================

def _compute_readiness(
    l6: L6ExecData, l1: L1SpatialData, H: int, W: int
) -> List[List[Optional[float]]]:
    """Compute execution readiness score per zone, rasterized to grid.

    Readiness = f(feasibility_grade, execution_confidence, blocked_status).
    """
    # Build zone-level readiness from interventions
    zone_readiness: Dict[str, float] = {}
    for intv in l6.interventions:
        fg = intv.get('feasibility_grade', 'UNKNOWN')
        fg_str = fg.value if hasattr(fg, 'value') else str(fg)
        score = FEASIBILITY_SCORES.get(fg_str, 0.5)
        utility = intv.get('utility_score', 0.5)
        readiness_val = score * 0.6 + utility * 0.4

        # Apply to target zones
        for z_id in intv.get('zone_targets', []):
            z_str = str(z_id)
            if z_str not in zone_readiness:
                zone_readiness[z_str] = readiness_val
            else:
                zone_readiness[z_str] = max(zone_readiness[z_str], readiness_val)

    # Blocked zones get zero readiness
    for z_id in l6.blocked_zones:
        zone_readiness[str(z_id)] = 0.0

    # Global confidence modifier
    conf_mod = l6.execution_confidence

    # Rasterize to grid using zone masks
    base_readiness = round(conf_mod * 0.5, 4)  # Default for unzoned areas
    grid = [[base_readiness] * W for _ in range(H)]

    if l1.zone_masks and zone_readiness:
        for z_id, cells in l1.zone_masks.items():
            z_score = zone_readiness.get(z_id, base_readiness)
            final_score = round(z_score * conf_mod, 4)
            for r, c in cells:
                if r < H and c < W:
                    grid[r][c] = final_score
    elif zone_readiness:
        avg_r = sum(zone_readiness.values()) / len(zone_readiness)
        from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_by_ndvi
        ndvi_r = get_ndvi_raster(l1, H, W)
        grid = modulate_by_ndvi(avg_r * conf_mod, ndvi_r, H, W, invert=False, clamp_min=0.0, clamp_max=1.0)
    else:
        from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_combined
        ndvi_r = get_ndvi_raster(l1, H, W)
        grid = modulate_combined(base_readiness, ndvi_r, H, W, invert=False, clamp_min=0.0, clamp_max=1.0)

    return grid


def _compute_priority(
    l6: L6ExecData, l8: L8ActionData, l1: L1SpatialData, H: int, W: int
) -> List[List[Optional[float]]]:
    """Compute intervention priority heatmap combining L6 utility × L8 priority."""
    zone_priority: Dict[str, float] = {}

    # L8 action priorities per zone
    for act in l8.actions:
        priority = act.get('priority_score', 0.0)
        for z_id in act.get('zone_targets', []):
            z_str = str(z_id)
            if z_str not in zone_priority:
                zone_priority[z_str] = priority
            else:
                zone_priority[z_str] = max(zone_priority[z_str], priority)

    # L8 zone plan priorities
    for zp in l8.zone_plan:
        z_str = str(zp.get('zone_id', ''))
        p = zp.get('allocation_fraction', 0.0)
        if z_str not in zone_priority:
            zone_priority[z_str] = p
        else:
            zone_priority[z_str] = max(zone_priority[z_str], p)

    # Cross-reference with L6 utility
    for intv in l6.interventions:
        utility = intv.get('utility_score', 0.5)
        for z_id in intv.get('zone_targets', []):
            z_str = str(z_id)
            if z_str in zone_priority:
                zone_priority[z_str] = round(
                    zone_priority[z_str] * 0.6 + utility * 0.4, 4
                )

    # Rasterize
    base = 0.3
    grid = [[base] * W for _ in range(H)]
    if l1.zone_masks and zone_priority:
        for z_id, cells in l1.zone_masks.items():
            z_score = zone_priority.get(z_id, base)
            for r, c in cells:
                if r < H and c < W:
                    grid[r][c] = round(z_score, 4)
    elif zone_priority:
        avg_p = sum(zone_priority.values()) / len(zone_priority)
        from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_by_ndvi
        ndvi_r = get_ndvi_raster(l1, H, W)
        grid = modulate_by_ndvi(avg_p, ndvi_r, H, W, invert=True, clamp_min=0.0, clamp_max=1.0)
    else:
        from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_combined
        ndvi_r = get_ndvi_raster(l1, H, W)
        grid = modulate_combined(base, ndvi_r, H, W, invert=True, clamp_min=0.0, clamp_max=1.0)

    # Post-check: if rasterization produced a uniform grid, modulate spatially
    flat = set(round(grid[r][c], 6) for r in range(H) for c in range(W))
    if len(flat) <= 1:
        from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_combined
        ndvi_r = get_ndvi_raster(l1, H, W)
        base_val = flat.pop() if flat else base
        grid = modulate_combined(base_val, ndvi_r, H, W, invert=True, clamp_min=0.0, clamp_max=1.0)

    return grid


def _compute_timing(
    l8: L8ActionData, l1: L1SpatialData, H: int, W: int
) -> List[List[Optional[float]]]:
    """Compute intervention timing urgency.

    Timing-critical actions get higher scores, zones with imminent interventions
    get amplified urgency.
    """
    zone_urgency: Dict[str, float] = {}

    for act in l8.actions:
        action_id = act.get('action_id', '')
        is_critical = action_id in l8.timing_critical_actions
        priority = act.get('priority_score', 0.0)
        urgency = priority * (1.5 if is_critical else 1.0)
        urgency = min(1.0, urgency)

        for z_id in act.get('zone_targets', []):
            z_str = str(z_id)
            if z_str not in zone_urgency:
                zone_urgency[z_str] = urgency
            else:
                zone_urgency[z_str] = max(zone_urgency[z_str], urgency)

    # Rasterize
    base = 0.1
    grid = [[base] * W for _ in range(H)]
    if l1.zone_masks and zone_urgency:
        for z_id, cells in l1.zone_masks.items():
            z_score = zone_urgency.get(z_id, base)
            for r, c in cells:
                if r < H and c < W:
                    grid[r][c] = round(z_score, 4)
    else:
        from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_combined
        ndvi_r = get_ndvi_raster(l1, H, W)
        grid = modulate_combined(base, ndvi_r, H, W, invert=True, clamp_min=0.0, clamp_max=1.0)

    # Post-check: if rasterization produced a uniform grid, modulate spatially
    flat = set(round(grid[r][c], 6) for r in range(H) for c in range(W))
    if len(flat) <= 1:
        from layer10_sire.surfaces.spatial_modulation import get_ndvi_raster, modulate_combined
        ndvi_r = get_ndvi_raster(l1, H, W)
        base_val = flat.pop() if flat else base
        grid = modulate_combined(base_val, ndvi_r, H, W, invert=True, clamp_min=0.0, clamp_max=1.0)

    return grid


def _compute_conflict(
    l6: L6ExecData, l1: L1SpatialData, H: int, W: int
) -> List[List[Optional[float]]]:
    """Compute conflict density heatmap from L6 conflict log.

    Higher = more unresolved conflicts in that zone.
    """
    zone_conflict: Dict[str, float] = {}

    for conflict in l6.conflict_log:
        resolution = conflict.get('resolution', 'UNRESOLVED')
        severity = 0.8 if resolution == 'UNRESOLVED' else 0.3
        for z_id in conflict.get('affected_zones', []):
            z_str = str(z_id)
            if z_str not in zone_conflict:
                zone_conflict[z_str] = severity
            else:
                zone_conflict[z_str] = min(1.0, zone_conflict[z_str] + severity * 0.5)

    # Rasterize
    grid = [[0.0] * W for _ in range(H)]
    if l1.zone_masks and zone_conflict:
        for z_id, cells in l1.zone_masks.items():
            z_score = zone_conflict.get(z_id, 0.0)
            for r, c in cells:
                if r < H and c < W:
                    grid[r][c] = round(z_score, 4)

    return grid
