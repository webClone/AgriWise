"""Pre-allocation feasibility planning for ASMAE spatial resolutions."""

from __future__ import annotations

import os
from typing import Any, Dict

from ..assimilation.filter import select_ensemble_size
from ..config import N_STATES
from ..geometry.spatial_reference import target_grid_from_reference


DEFAULT_MEMORY_LIMIT_MB = 768.0


def memory_limit_bytes(inp: Any = None) -> int:
    configured = None
    if inp is not None:
        configured = getattr(inp, "resource_memory_limit_mb", None)
    raw = configured if configured is not None else os.environ.get("ASMAE_MEMORY_LIMIT_MB")
    try:
        limit_mb = float(raw) if raw is not None else DEFAULT_MEMORY_LIMIT_MB
    except (TypeError, ValueError):
        limit_mb = DEFAULT_MEMORY_LIMIT_MB
    return int(max(64.0, limit_mb) * 1024 * 1024)


def plan_resolution(scene: Any, resolution_m: int, mode: str, inp: Any = None) -> Dict[str, Any]:
    grid = target_grid_from_reference(scene, resolution_m)
    zones = grid.n_rows * grid.n_cols
    ensemble_size = select_ensemble_size(mode, zones)
    scalar_count = zones * N_STATES * ensemble_size
    packed_ensemble_bytes = scalar_count * 8
    # Forecast + analysis arrays, statistics, graph, H_t bookkeeping, and
    # Python/runtime overhead.  This is deliberately conservative.
    estimated_peak_bytes = int(
        packed_ensemble_bytes * 3.0
        + zones * N_STATES * 16
        + zones * 8 * 64
    )
    limit = memory_limit_bytes(inp)
    return {
        "resolution_m": int(resolution_m),
        "n_microzones": int(zones),
        "ensemble_size": int(ensemble_size),
        "ensemble_state_scalars": int(scalar_count),
        "packed_float64_bytes": int(packed_ensemble_bytes),
        "estimated_peak_bytes": int(estimated_peak_bytes),
        "memory_limit_bytes": int(limit),
        "feasible": bool(estimated_peak_bytes <= limit),
        "planner_version": "asmae_resource_planner_v1",
    }
