"""IR-04/08 bounded integration: exploratory state-cell support on the real graph grid.

No source in this module is accepted as cryptographically admitted. Callers must
supply independently qualified operator footprints; current engine leaves that
sequence empty until a verified upstream binding is implemented. No new map or
1 m certification is granted by this bridge.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from .state_cell_support import (
    EvidenceFootprint, GridSpec, SpatialSupportViolation,
    STATE_NAMES, evaluate_state_cell_support,
)

# Bound the cost of per-state, per-cell metadata before full sparse/tiled support.
MAX_STATEWISE_CELLS = 4096


def build_statewise_engine_support(
    *, raster_maps: Mapping[str, Any], uncertainty_maps: Mapping[str, Any],
    grid_spec: Mapping[str, Any], geometry_sha256: str,
    tenant_id: str, farm_id: str, plot_id: str,
    valid_time: str, knowledge_cutoff: str,
    qualified_footprints: Sequence[EvidenceFootprint] = (),
    max_cells: int = MAX_STATEWISE_CELLS,
) -> dict:
    """State-specific *exploratory* resolution maps; unqualified cells remain null.

    Scientific rasters must already match the unresampled, immutable graph grid.
    This is not a producer of geometric grids, observation operators, or an
    independent proof that the submitted footprint has been admitted.
    """
    width, height = int(grid_spec.get('width', 0) or 0), int(grid_spec.get('height', 0) or 0)
    if width <= 0 or height <= 0 or width * height > max_cells:
        return {'status': 'unavailable', 'reason': 'missing_or_oversize_scientific_grid',
                'authority_status': 'exploratory_only', 'effective_resolution_m_by_state': {}}
    if not all((tenant_id, farm_id, plot_id, geometry_sha256, valid_time, knowledge_cutoff)):
        return {'status': 'unavailable', 'reason': 'unbound_namespace_or_bitemporal_receipt',
                'authority_status': 'exploratory_only', 'effective_resolution_m_by_state': {}}
    transform = grid_spec.get('transform') or ()
    try:
        grid = GridSpec(crs=str(grid_spec.get('crs', '')), transform=tuple(transform),
                        width=width, height=height)
    except (ValueError, TypeError, SpatialSupportViolation) as exc:
        return {'status': 'unavailable', 'reason': 'invalid_authoritative_scientific_grid',
                'authority_status': 'exploratory_only', 'effective_resolution_m_by_state': {}}

    # All state rasters are measured against the graph grid, not the display overlay.
    for source in (raster_maps, uncertainty_maps):
        for state in STATE_NAMES:
            arr = source.get(state)
            if arr is not None and (not isinstance(arr, (list, tuple)) or len(arr) != height
                                    or any(not isinstance(row, (list, tuple)) or len(row) != width for row in arr)):
                return {'status': 'unavailable', 'reason': 'display_resampling_or_grid_shape_mismatch',
                        'authority_status': 'exploratory_only', 'effective_resolution_m_by_state': {}}

    resolutions, classifications, reasons, record_hashes = {}, {}, {}, []
    for state in STATE_NAMES:
        state_values = raster_maps.get(state)
        state_sigmas = uncertainty_maps.get(state)
        resolution_rows, class_rows = [], []
        for row in range(height):
            resolution_row, class_row = [], []
            for col in range(width):
                val = state_values[row][col] if state_values is not None else None
                sigma = state_sigmas[row][col] if state_sigmas is not None else None
                # Nil/non-finite raster values remain unavailable; do not turn nodata into data.
                val = float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(val) else None
                sigma = float(sigma) if isinstance(sigma, (int, float)) and not isinstance(sigma, bool) and math.isfinite(sigma) and sigma >= 0 else None
                record = evaluate_state_cell_support(
                    state=state, row=row, col=col, grid=grid,
                    tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id,
                    geometry_sha256=geometry_sha256,
                    valid_time=valid_time, knowledge_cutoff=knowledge_cutoff,
                    estimated_value=val, sigma=sigma, evidences=qualified_footprints,
                )
                resolution_row.append(record.effective_resolution_m)
                class_row.append(record.spatial_support)
                record_hashes.append(record.digest())
                for reason in record.demotion_reasons:
                    reasons[reason] = reasons.get(reason, 0) + 1
            resolution_rows.append(resolution_row)
            class_rows.append(class_row)
        resolutions[state], classifications[state] = resolution_rows, class_rows
    digest = hashlib.sha256(json.dumps(record_hashes, separators=(',', ':')).encode()).hexdigest()
    return {
        'status': 'exploratory_statewise_metadata',
        'authority_status': 'exploratory_only',
        'certified_1m': False,
        'grid_sha256': grid.digest(),
        'evidence_binding': 'qualified_upstream_footprints_required',
        'effective_resolution_m_by_state': resolutions,
        'spatial_support_class_by_state': classifications,
        'demotion_reason_counts': reasons,
        'support_records_sha256': digest,
    }
