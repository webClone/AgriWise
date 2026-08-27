"""
Historical Diagnostic Overlays.
Enforces that state_update_allowed = False and generates historical diagnostic surfaces.
Uses real historical metrics from ArchiveMetricsStore.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import numpy as np
from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData

def generate_historical_surfaces(
    inp: Layer10Input, H: int, W: int,
    l1_data: Optional[L1SpatialData] = None,
) -> List[SurfaceArtifact]:
    """
    Generates historical diagnostic surfaces (baselines, anomalies, retrovalidation scores, BMA disagreements).
    Enforces strict diagnostic-only status with state_update_allowed = False.
    """
    from rollout.rollout_policy import should_render_l10_asmae
    if not should_render_l10_asmae(inp.plot_id):
        return []

    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        try:
            l1_data = adapt_l1(inp.field_tensor, H, W)
        except Exception:
            return []
        
    has_asmae_input = any(
        str(k).lower().startswith("asmae_")
        for k in (
            list(l1_data.raster_maps.keys())
            + list(l1_data.raster_metadata.keys())
            + list(l1_data.last_values.keys())
        )
    )
    if not has_asmae_input:
        return []

    # 1. Fetch metrics from the metrics store
    from services.agribrain.layer05_asmae.history.archive_metrics_store import (
        ArchiveMetricsStore,
    )
    store = ArchiveMetricsStore()
    
    status = "success"
    warning_code = None
    metrics_info = None
    confidence_val = 1.0
    uncertainty_val = 0.0

    try:
        metrics_info = store.get_latest_metrics_info(inp.plot_id)
        if not metrics_info:
            status = "missing"
            warning_code = "historical_metrics_missing"
            confidence_val = 0.0
            uncertainty_val = 1.0
    except ValueError:
        # Malformed metrics
        status = "malformed"
        warning_code = "historical_metrics_malformed"
        confidence_val = 0.0
        uncertainty_val = 1.0
    except Exception:
        status = "missing"
        warning_code = "historical_metrics_missing"
        confidence_val = 0.0
        uncertainty_val = 1.0

    # An absent or malformed archive is a data-availability state, not an
    # ASMAE raster product. Emitting all-null ASMAE_* grids here misrepresents
    # an execution that never produced historical evidence and poisons the
    # Layer 10 detail/invariant contract.
    if status != "success" or not metrics_info:
        return []

    # 2. Get baseline values or defaults
    retro_val = None
    bma_val = None
    baseline_mean = 0.5
    
    if status == "success" and metrics_info:
        data = metrics_info["data"]
        hist_data = data.get("historical_metrics", {})
        retro_data = data.get("retrovalidation_metrics", {})
        bma_data = data.get("archive_bma_metrics", {})
        base_data = data.get("baseline_metrics", {})

        # Read directly from metrics fields - never use static defaults if they exist
        # retrovalidation_metrics could have rmse
        retro_val = retro_data.get("rmse") or retro_data.get("retrovalidation_score")
        if retro_val is not None:
            retro_val = float(retro_val)
        else:
            retro_val = hist_data.get("retrovalidation_score")
            
        bma_val = bma_data.get("bma_disagreement")
        if bma_val is not None:
            bma_val = float(bma_val)
        else:
            # fallback to average difference or variance of weights
            weights = bma_data.get("weights", {})
            if weights:
                bma_val = float(np.var(list(weights.values())))
            else:
                bma_val = hist_data.get("bma_disagreement")

        # Parse current date to get DOY
        doy = 1
        if inp.field_tensor and hasattr(inp.field_tensor, "time_index") and inp.field_tensor.time_index:
            try:
                last_date_str = inp.field_tensor.time_index[-1]
                dt = datetime.strptime(last_date_str, "%Y-%m-%d")
                doy = dt.timetuple().tm_yday
            except Exception:
                pass
        
        # Look up DOY mean
        baseline_doy_mean = base_data.get("baseline_doy_mean", {}) or hist_data.get("baseline_doy_mean", {})
        doy_str = str(doy)
        if doy_str in baseline_doy_mean:
            baseline_mean = float(baseline_doy_mean[doy_str])
        elif doy in baseline_doy_mean:
            baseline_mean = float(baseline_doy_mean[doy])

    # Construct grids
    anomaly_grid = [[None] * W for _ in range(H)]
    retro_grid = [[None] * W for _ in range(H)]
    bma_grid = [[None] * W for _ in range(H)]
    confidence_grid = [[confidence_val] * W for _ in range(H)]

    if status == "success" and metrics_info:
        # Modulate anomaly_grid with ndvi if available
        from services.agribrain.layer10_sire.surfaces.spatial_modulation import get_ndvi_raster
        ndvi_r = None
        try:
            ndvi_r = get_ndvi_raster(l1_data, H, W)
        except Exception:
            pass
            
        if ndvi_r:
            for r in range(H):
                for c in range(W):
                    val = ndvi_r[r][c]
                    if val is not None:
                        anomaly_grid[r][c] = round(val - baseline_mean, 4)
                    else:
                        anomaly_grid[r][c] = None
        else:
            for r in range(H):
                for c in range(W):
                    anomaly_grid[r][c] = 0.0

        for r in range(H):
            for c in range(W):
                retro_grid[r][c] = retro_val
                bma_grid[r][c] = bma_val

    # Setup provenance
    provenance = {
        "diagnostic_only": True,
        "state_update_allowed": False,
        "provenance": "historical_sentinel_archive"
    }
    if warning_code:
        provenance["warning_code"] = warning_code
    if uncertainty_val is not None:
        provenance["uncertainty"] = uncertainty_val

    if metrics_info:
        provenance["archive_metrics_hash"] = metrics_info["archive_metrics_hash"]
        provenance["archive_run_id"] = metrics_info["archive_run_id"]
        provenance["archive_policy_version"] = metrics_info["archive_policy_version"]
        provenance["retrovalidation_policy_version"] = metrics_info["retrovalidation_policy_version"]
        provenance["archive_bma_policy_version"] = metrics_info["archive_bma_policy_version"]
        provenance["baseline_policy_version"] = metrics_info["baseline_policy_version"]

    surfaces = []
    
    # 1. BASELINE_ANOMALY
    surfaces.append(SurfaceArtifact(
        surface_id=f"BASELINE_ANOMALY_{inp.plot_id}",
        semantic_type=SurfaceType.BASELINE_ANOMALY,
        grid_ref=f"{H}x{W}",
        values=anomaly_grid,
        units="deviation",
        native_resolution_m=inp.resolution_m,
        render_range=(-0.5, 0.5),
        palette_id=PaletteId.STRESS_RED,
        source_layers=["L10_HISTORICAL"],
        confidence=confidence_grid,
        provenance=provenance
    ))

    # 2. ASMAE_RETROVALIDATION_SCORE
    surfaces.append(SurfaceArtifact(
        surface_id=f"ASMAE_RETROVALIDATION_{inp.plot_id}",
        semantic_type=SurfaceType.ASMAE_RETROVALIDATION_SCORE,
        grid_ref=f"{H}x{W}",
        values=retro_grid,
        units="accuracy",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.VIGOR_GREEN,
        source_layers=["L10_HISTORICAL"],
        confidence=confidence_grid,
        provenance=provenance
    ))

    # 3. ASMAE_BMA_DISAGREEMENT
    surfaces.append(SurfaceArtifact(
        surface_id=f"ASMAE_BMA_DISAGREEMENT_{inp.plot_id}",
        semantic_type=SurfaceType.ASMAE_BMA_DISAGREEMENT,
        grid_ref=f"{H}x{W}",
        values=bma_grid,
        units="disagreement",
        native_resolution_m=inp.resolution_m,
        render_range=(0.0, 1.0),
        palette_id=PaletteId.STRESS_RED,
        source_layers=["L10_HISTORICAL"],
        confidence=confidence_grid,
        provenance=provenance
    ))

    return surfaces
