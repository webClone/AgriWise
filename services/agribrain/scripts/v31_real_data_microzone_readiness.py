from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

# Load workspace environment variables from .env
load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=True)

REPORT = {
    "version": "V31-real-data-readiness",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "constraints": {
        "latent_grid_target_m": 1,
        "external_validation": "none: no drones, cameras, or sensors",
        "satellite_shifting_core": True,
        "real_data_goal": "Sentinel-2 + Sentinel-1 via existing AgriWise acquisition path",
    },
}

# A small real irrigated-agriculture style polygon in El Oued / Oued Souf, Algeria.
# Replace with a real user plot polygon when available.
POLYGON = [[
    [6.86000, 33.34800],
    [6.86300, 33.34800],
    [6.86300, 33.35100],
    [6.86000, 33.35100],
    [6.86000, 33.34800],
]]
LAT = 33.3495
LNG = 6.8615
PLOT_ID = "v31_real_polygon_el_oued"


def _safe_err(e: Exception) -> dict:
    return {"type": type(e).__name__, "message": str(e)[:500]}


def check_auth_and_network():
    out = {
        "has_client_id": bool(os.getenv("SENTINEL_HUB_CLIENT_ID")),
        "has_client_secret": bool(os.getenv("SENTINEL_HUB_CLIENT_SECRET")),
        "auth_ok": False,
    }
    try:
        from eo.auth import get_access_token
        tok = get_access_token()
        out["auth_ok"] = bool(tok)
        out["token_length"] = len(tok) if tok else 0
    except Exception as e:
        out["auth_error"] = _safe_err(e)
    return out


def try_real_acquisition():
    out = {"attempted": True, "polygon": {"lat": LAT, "lng": LNG, "ring_points": len(POLYGON[0])}}
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=1800)
    start_s, end_s = str(start), str(end)
    out["window"] = {"start": start_s, "end": end_s, "days": 1800}

    try:
        from eo.sentinel import fetch_ndvi_timeseries, fetch_sar_timeseries
        ndvi = fetch_ndvi_timeseries(LAT, LNG, days=1800, polygon_coords=POLYGON)
        out["s2_timeseries_ok"] = isinstance(ndvi, dict)
        out["s2_observations"] = len(ndvi.get("data", [])) if isinstance(ndvi, dict) else 0
    except Exception as e:
        out["s2_timeseries_error"] = _safe_err(e)

    try:
        from eo.sentinel import fetch_sar_timeseries
        sar = fetch_sar_timeseries(LAT, LNG, days=1800, polygon_coords=POLYGON)
        out["s1_timeseries_ok"] = isinstance(sar, dict)
        out["s1_observations"] = len(sar.get("timeseries", sar.get("data", []))) if isinstance(sar, dict) else 0
    except Exception as e:
        out["s1_timeseries_error"] = _safe_err(e)

    # Raster composite attempt. This is what V31/ASMAE would need for real shifted-scene work,
    # though the current functions fetch composites on a fixed output grid rather than native per-scene footprints.
    try:
        from eo.sentinel import fetch_ndvi_raster_composite, fetch_ndmi_raster_composite, fetch_sar_raster_composite
        comps = {}
        for name, fn in [
            ("NDVI", fetch_ndvi_raster_composite),
            ("NDMI", fetch_ndmi_raster_composite),
            ("SAR_VV", fetch_sar_raster_composite),
        ]:
            try:
                r = fn(LAT, LNG, start_s, end_s, polygon_coords=POLYGON, target_resolution_m=10)
                comps[name] = r
            except Exception as e:
                comps[name] = {"error": _safe_err(e)}
        out["raster_composites"] = {
            k: {
                "ok": isinstance(v, dict) and ("values" in v or "pixel_array" in v),
                "height": len(v.get("values", v.get("pixel_array", []))) if isinstance(v, dict) else 0,
                "width": len(v.get("values", v.get("pixel_array", [[]]))[0]) if isinstance(v, dict) and (v.get("values") or v.get("pixel_array")) else 0,
                "resolution_m": v.get("resolution_m", 10.0) if isinstance(v, dict) else None,
                "error": v.get("error") if isinstance(v, dict) else None,
            }
            for k, v in comps.items()
        }
    except Exception as e:
        out["raster_composite_stage_error"] = _safe_err(e)
    return out


def layer1_raster_ingestion_smoke():
    out = {"attempted": True}
    try:
        from layer1_fusion.engine import Layer1FusionEngine
        from layer1_fusion.schemas import Layer1InputBundle
        now = datetime.now(timezone.utc)
        pix = [[0.42 + 0.01 * r + 0.004 * c for c in range(10)] for r in range(10)]
        bundle = Layer1InputBundle(
            plot_id=PLOT_ID,
            run_id="v31_l1_raster_smoke",
            run_timestamp=now,
            window_start=now - timedelta(days=30),
            window_end=now,
            plot_geometry={"type": "Polygon", "coordinates": POLYGON},
            raster_composites={
                "NDVI": {"pixel_array": pix, "valid_pixel_count": 100, "resolution_m": 10.0}
            },
        )
        pkg = Layer1FusionEngine().fuse(bundle)
        out.update({
            "ok": True,
            "evidence_count": len(pkg.evidence_items),
            "raster_refs": [(r.variable, r.resolution_m) for r in pkg.spatial_index.raster_refs],
            "usable_for_layer2": pkg.state_summary.usable_for_layer2,
            "data_health": pkg.diagnostics.data_health.overall,
            "status": pkg.diagnostics.status,
        })
    except Exception as e:
        out["ok"] = False
        out["error"] = _safe_err(e)
        out["traceback"] = traceback.format_exc()[-2000:]
    return out


def inspect_microzone_insertion_points():
    return {
        "recommended_module": "services/agribrain/layer0/microzone",
        "layer1_handoff": "Layer1InputBundle.raster_composites",
        "existing_reusable_engines": [
            "layer0.kalman_engine.DailyAssimilationEngine",
            "layer0.state_vector.StateVector / ProcessModel",
            "layer0.observation_model.ObservationModel",
            "layer0.sentinel2.engine / kalman_adapter",
            "layer0.sentinel1.engine / kalman_adapter",
            "layer2_veg_int.growth_engine.GrowthCurveEngine",
            "layer2_veg_int.phenology_engine.PhenologyEngine",
            "layer3_water.evapotranspiration.ETEngine",
            "layer4_nutrients.soil_water_balance.SoilWaterBalanceEngine",
            "layer4_nutrients.proxies.NutrientObservationProxyEngine",
            "layer1_fusion.raster_ingest.ingest_raster_composites",
        ],
        "missing_for_true_v31": [
            "native per-scene Sentinel-2 band rasters instead of fixed-grid composites",
            "scene-specific geotransform / residual co-registration estimation",
            "Sentinel-1 per-scene VV/VH rasters with incidence angle metadata",
            "local future-scene residual maps for export gating",
        ],
    }


if __name__ == "__main__":
    REPORT["auth_network"] = check_auth_and_network()
    if REPORT["auth_network"].get("auth_ok"):
        REPORT["real_acquisition"] = try_real_acquisition()
    else:
        REPORT["real_acquisition"] = {"attempted": False, "reason": "auth/network unavailable"}
    REPORT["layer1_raster_ingestion_smoke"] = layer1_raster_ingestion_smoke()
    REPORT["microzone_insertion_points"] = inspect_microzone_insertion_points()

    out_path = Path("artifacts/v31_real_data_microzone_readiness_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(REPORT, indent=2, default=str), encoding="utf-8")
    print(json.dumps(REPORT, indent=2, default=str))
    print(f"\nSaved: {out_path}")
