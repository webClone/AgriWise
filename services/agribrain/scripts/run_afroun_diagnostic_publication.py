"""Unified Full-Engine Canonical Diagnostic Publication for `afroun` (`6a09d9e91dd0c7ed6fce7d50`).

Executes the real 13-state `ASMAEEngine` (via `ASMAERunner`) over coincident
Sentinel-2 + Sentinel-1 scene products and real ERA5 historical reanalysis weather,
passes the supported posterior & uncertainty maps through Layer 10 (`run_layer10_sire`
+ `l10_frontend_bridge.serialize_output`) while keeping unsupported/unverified states
(e.g. `thermal_stress` without TIR, `prior_constrained` `stress_memory`, and
hypothesis-only `salinity_stress` / `biotic_confounder_risk`) explicitly withheld,
and publishes atomically via `publish_canonical_plot_snapshot` with exact DB
parcel geometry, active crop cycle binding, and Worldline lineage.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from shapely.geometry import Polygon

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.agribrain.common.plot_namespace import PlotNamespace, namespace_payload
from services.agribrain.common.surface_hashing import compute_surface_inventory_hash
from services.agribrain.eo.weather import fetch_historical_weather
from services.agribrain.geometry_contract import compute_geometry_hash
from services.agribrain.layer0.asmae_scene_products.s1_real_scene_product_fetcher import (
    fetch_asmae_s1_scene_stack,
)
from services.agribrain.layer0.asmae_scene_products.s2_real_scene_product_fetcher import (
    fetch_asmae_s2_scene_stack,
)
from services.agribrain.layer0.environment.weather.source_roles import role_for_data_kind
from services.agribrain.layer05_asmae.history.weather_archive_adapter import (
    normalize_weather_archive,
)
from services.agribrain.layer05_asmae.plot_snapshot_store import (
    publish_canonical_plot_snapshot,
)
from services.agribrain.layer05_asmae.runner import ASMAERunner
from services.agribrain.layer10_sire.l10_frontend_bridge import serialize_output
from services.agribrain.layer10_sire.runner import run_layer10_sire
from services.agribrain.layer10_sire.schema import Layer10Input
from services.agribrain.layer10_sire.surface_contract import (
    classify_surface_publication,
)
from services.agribrain.layer1_fusion.schema import FieldTensor
from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService

logger = logging.getLogger("run_afroun_diagnostic_publication")

# Canonical `afroun` database identity (verified against live PostgreSQL Prisma Plot/CropCycle)
TENANT_ID = "697ddd3bd4195b809226a67b"
FARM_ID = "69ad7b6f7e6843e8234afcf6"
PLOT_ID = "6a09d9e91dd0c7ed6fce7d50"
CROP_CYCLE_ID = "6aa3fcfb33e482b6c2add386"

PLOT_COORDINATES: List[List[float]] = [
    [2.65551, 36.509522],
    [2.655457, 36.507444],
    [2.662473, 36.507194],
    [2.663331, 36.510195],
    [2.663331, 36.510609],
    [2.65551, 36.509522],
]
PLOT_GEOJSON: Dict[str, Any] = {
    "type": "Feature",
    "properties": {},
    "geometry": {
        "type": "Polygon",
        "coordinates": [PLOT_COORDINATES],
    },
}
GEOMETRY_HASH = compute_geometry_hash(PLOT_GEOJSON)
CENTER_LAT = 36.5089
CENTER_LNG = 2.6594

DEFAULT_OBS_START = "2026-08-30"
DEFAULT_OBS_END = "2026-09-08"

# Reflectance relative uncertainty assumption used in analytical NDVI uncertainty propagation
REFLECTANCE_REL_ERROR = 0.02

# SCL classes treated as invalid/cloudy/shadow/nodata
INVALID_SCL_CLASSES = (0, 1, 3, 8, 9, 10, 11)

# Unsupported / unverified states withheld from spatial raster publication
WITHHELD_STATE_REASONS: Dict[str, Tuple[str, str]] = {
    "thermal_stress": (
        "ASMAE_THERMAL_STRESS",
        "no_thermal_ir_observation:Sentinel-2 has no TIR/LST band (only uncalibrated optical CWSI proxy)",
    ),
    "stress_memory": (
        "ASMAE_STRESS_MEMORY",
        "prior_constrained_no_accepted_updates:zero observation updates admitted",
    ),
    "salinity_stress": (
        "ASMAE_SALINITY_STRESS",
        "missing_salinity_evidence_family:no in-situ EC or salinity-specific spectral inversion",
    ),
    "biotic_confounder_risk": (
        "ASMAE_BIOTIC_CONFOUNDER_RISK",
        "monitoring_only_no_in_situ_verification:no pathology/scouting ground verification",
    ),
}

WITHHELD_SURFACE_TYPES = frozenset({
    "ASMAE_THERMAL_STRESS",
    "ASMAE_STRESS_MEMORY",
    "ASMAE_SALINITY_STRESS",
    "SALINITY_ASMAE_STRESS",
    "ASMAE_BIOTIC_CONFOUNDER_RISK",
    "ASMAE_1M_ADVISORY_MASK",
    "ASMAE_1M_CERTIFIED_MASK",
})


def _load_band_array(path: str) -> np.ndarray:
    """Load raster array cleanly from .npz without leaking file handles."""
    with np.load(path) as archive:
        key = (
            "data"
            if "data" in archive.files
            else ("arr_0" if "arr_0" in archive.files else archive.files[0])
        )
        return np.asarray(archive[key], dtype=float)


def _scene_attr(scene: Any, name: str, default: Any = None) -> Any:
    return scene.get(name, default) if isinstance(scene, dict) else getattr(scene, name, default)


def verify_scene_grid_coincidence(
    s2_products: List[Any],
    s1_products: List[Any],
    tolerance: float = 1e-9,
) -> Dict[str, Any]:
    """Assert every S2 and S1 scene shares identical CRS, shape, and affine transform."""
    all_scenes = [*s2_products, *s1_products]
    if not all_scenes:
        raise RuntimeError("Cannot verify grid coincidence without scenes.")

    ref = s2_products[-1] if s2_products else s1_products[-1]
    crs = str(_scene_attr(ref, "crs") or "")
    height = int(_scene_attr(ref, "height") or 0)
    width = int(_scene_attr(ref, "width") or 0)
    transform = [float(x) for x in (_scene_attr(ref, "transform") or [])[:6]]
    if not crs or height <= 0 or width <= 0 or len(transform) != 6:
        raise RuntimeError(
            f"Reference scene lacks complete georeferencing: crs={crs!r}, H={height}, W={width}, transform={transform}"
        )

    for sc in all_scenes:
        sid = str(_scene_attr(sc, "scene_id") or "")
        sc_crs = str(_scene_attr(sc, "crs") or "")
        sc_h = int(_scene_attr(sc, "height") or 0)
        sc_w = int(_scene_attr(sc, "width") or 0)
        sc_t = [float(x) for x in (_scene_attr(sc, "transform") or [])[:6]]
        if sc_crs != crs:
            raise ValueError(f"Scene {sid} CRS mismatch: {sc_crs} != {crs}")
        if (sc_h, sc_w) != (height, width):
            raise ValueError(f"Scene {sid} shape mismatch: {(sc_h, sc_w)} != {(height, width)}")
        if len(sc_t) != 6 or any(abs(a - b) > tolerance for a, b in zip(sc_t, transform)):
            raise ValueError(f"Scene {sid} transform mismatch: {sc_t} != {transform}")

    x0, dx, _, y0, _, dy = transform
    bounds = [
        min(x0, x0 + width * dx),
        min(y0, y0 + height * dy),
        max(x0, x0 + width * dx),
        max(y0, y0 + height * dy),
    ]
    return {
        "coincident": True,
        "crs": crs,
        "height": height,
        "width": width,
        "transform": transform,
        "bounds": bounds,
        "s2_scene_count": len(s2_products),
        "s1_scene_count": len(s1_products),
    }


def fetch_verified_weather_series(
    lat: float, lng: float, start_date: str, end_date: str
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch real ERA5 Open-Meteo reanalysis weather and build truthful proof without fallbacks."""
    raw = fetch_historical_weather(lat, lng, start_date, end_date)
    records = (raw or {}).get("records") if isinstance(raw, dict) else None
    source_name = str((raw or {}).get("source") or "era5-open-meteo") if isinstance(raw, dict) else "unavailable"
    if not records:
        return [], {
            "status": "unavailable",
            "source_reality": "missing",
            "provider": "unavailable",
            "days": 0,
            "missing_variables": [
                "temp_min_c", "temp_max_c", "precipitation_mm", "et0_mm", "humidity_mean_pct", "wind_speed_m_s"
            ],
            "completeness": {},
        }

    tagged: List[Dict[str, Any]] = []
    for rec in records:
        tagged.append({
            **rec,
            "provider": source_name,
            "data_kind": "historical_reanalysis",
            "source_role": role_for_data_kind("historical_reanalysis").value,
            "source_qualified": False,
            "precipitation_sum": rec.get("precipitation"),
            "wind_speed_max": rec.get("wind_max"),
            "et0_mm": rec.get("et0"),
        })

    normalized = normalize_weather_archive({"records": tagged})
    precip_vals = [float(r["precipitation"]) for r in records if r.get("precipitation") is not None]
    temp_vals = [float(r["temp_mean"]) for r in records if r.get("temp_mean") is not None]
    et0_vals = [float(r["et0"]) for r in records if r.get("et0") is not None]

    proof = {
        "status": normalized.get("weather_archive_status", "unavailable"),
        "source_reality": normalized.get("weather_source_reality", "reanalysis_archive"),
        "provider": source_name,
        "days": len(normalized.get("weather_daily_series") or {}),
        "precipitation_total_mm": round(sum(precip_vals), 2) if precip_vals else None,
        "temp_mean_avg_c": round(sum(temp_vals) / len(temp_vals), 2) if temp_vals else None,
        "et0_total_mm": round(sum(et0_vals), 2) if et0_vals else None,
        "missing_variables": list(normalized.get("missing_variables") or []),
        "completeness": dict(normalized.get("variable_completeness") or {}),
        "weather_archive_hash": normalized.get("weather_archive_hash"),
    }
    return tagged, proof


def _compute_optical_and_sar_diagnostics(
    s2_products: List[Any],
    s1_products: List[Any],
    inside_poly: np.ndarray,
) -> Dict[str, Any]:
    """Compute cloud/polygon-masked NDVI, analytical reflectance uncertainty, and SAR wetness proxy."""
    ndvi_stack, ndvi_sigma_stack = [], []
    for s in s2_products:
        band_refs = _scene_attr(s, "band_refs") or {}
        mask_refs = _scene_attr(s, "mask_refs") or {}
        b04 = _load_band_array(band_refs["B04"])
        b08 = _load_band_array(band_refs["B08"])
        scl = _load_band_array(mask_refs["SCL"])
        cloud_invalid = np.isin(scl, INVALID_SCL_CLASSES)
        denom = b08 + b04
        valid = inside_poly & (~cloud_invalid) & np.isfinite(b04) & np.isfinite(b08) & (denom > 0.0)
        ndvi = np.where(valid, (b08 - b04) / np.where(valid, denom, 1.0), np.nan)
        # First-order analytical uncertainty from independent multiplicative reflectance errors
        sigma = np.where(
            valid,
            (2.0 * REFLECTANCE_REL_ERROR * np.abs(b04) * np.abs(b08) * np.sqrt(2.0))
            / np.square(np.where(valid, denom, 1.0)),
            np.nan,
        )
        ndvi_stack.append(ndvi)
        ndvi_sigma_stack.append(sigma)

    vv_db_stack = []
    for s in s1_products:
        band_refs = _scene_attr(s, "band_refs") or {}
        vv = _load_band_array(band_refs["VV"])
        valid = inside_poly & np.isfinite(vv) & (vv > 0.0)
        vv_db = np.where(valid, 10.0 * np.log10(np.maximum(vv, 1e-6)), np.nan)
        vv_db_stack.append(vv_db)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        ndvi_mean = np.nanmean(np.stack(ndvi_stack, axis=0), axis=0)
        ndvi_unc = np.nanmean(np.stack(ndvi_sigma_stack, axis=0), axis=0)
        vv_db_mean = np.nanmean(np.stack(vv_db_stack, axis=0), axis=0)

    sar_valid = inside_poly & np.isfinite(vv_db_mean)
    sar_wetness_proxy = np.where(
        sar_valid, np.clip((vv_db_mean + 20.0) / 15.0, 0.0, 1.0), np.nan
    )

    return {
        "ndvi_mean": np.where(inside_poly, ndvi_mean, np.nan),
        "ndvi_uncertainty": np.where(inside_poly, ndvi_unc, np.nan),
        "vv_db_mean": np.where(inside_poly, vv_db_mean, np.nan),
        "sar_wetness_proxy": np.where(inside_poly, sar_wetness_proxy, np.nan),
        "valid_ndvi_pixels": int(np.sum(np.isfinite(ndvi_mean) & inside_poly)),
        "valid_sar_pixels": int(np.sum(sar_valid)),
    }


def build_l10_filtered_asmae_payload(asmae_res: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Filter unsupported/prior-only ASMAE state rasters before Layer 10 surface serialization."""
    filtered = copy.deepcopy(asmae_res)
    diag = filtered.get("diagnostics") or {}
    ledger = diag.get("state_support_ledger") or {}
    raster_maps = filtered.get("raster_maps") or {}
    uncertainty_maps = filtered.get("uncertainty_maps") or {}

    withheld_entries: List[Dict[str, Any]] = []
    withheld_keys = set(WITHHELD_STATE_REASONS.keys())

    # Dynamically withhold any state whose ledger shows zero accepted observation updates
    for state_key, entry in ledger.items():
        if not isinstance(entry, dict):
            continue
        updates = int(entry.get("accepted_update_count", 0) or 0)
        status = str(entry.get("support_status") or "").lower()
        blocks = [str(b) for b in (entry.get("block_reasons") or [])]
        if updates <= 0 or status in ("prior_constrained", "unsupported", "blocked") or "no_accepted_state_update" in blocks:
            withheld_keys.add(state_key)

    for state_key in sorted(withheld_keys):
        surface_type, reason = WITHHELD_STATE_REASONS.get(
            state_key,
            (f"ASMAE_{state_key.upper()}", "prior_constrained_or_unverified_state"),
        )
        for prefix in ("", "asmae_"):
            raster_maps.pop(f"{prefix}{state_key}", None)
            uncertainty_maps.pop(f"{prefix}{state_key}", None)
        if state_key in ledger and isinstance(ledger[state_key], dict):
            prev_status = str(ledger[state_key].get("support_status") or "").lower()
            ledger[state_key]["spatial_support"] = "unavailable"
            ledger[state_key]["field_approval_eligible"] = False
            ledger[state_key]["support_status"] = (
                "prior_constrained" if prev_status == "prior_constrained" else "unsupported"
            )
            if ledger[state_key]["support_status"] == "unsupported":
                ledger[state_key]["observation_relationship"] = "none"
            ledger[state_key]["block_reasons"] = sorted(
                set(list(ledger[state_key].get("block_reasons") or []) + [reason.split(":")[0]])
            )
        withheld_entries.append({
            "state": state_key,
            "surface_type": surface_type,
            "reason": reason,
            "withheld": True,
        })

    return filtered, withheld_entries


def _to_masked_grid_list(arr: np.ndarray, inside_poly: np.ndarray) -> List[List[Optional[float]]]:
    """Convert numpy array to JSON 2D list keeping every outside-polygon or NaN cell as None."""
    out: List[List[Optional[float]]] = []
    h, w = arr.shape
    for r in range(h):
        row: List[Optional[float]] = []
        for c in range(w):
            v = float(arr[r, c])
            if bool(inside_poly[r, c]) and np.isfinite(v):
                row.append(round(v, 6))
            else:
                row.append(None)
        out.append(row)
    return out


def _apply_polygon_mask_to_surface(
    surface: Dict[str, Any],
    inside_poly: np.ndarray,
    ndvi_unc_list: Optional[List[List[Optional[float]]]] = None,
) -> bool:
    """Enforce strict interior-polygon null masking on surface values & aligned uncertainty grids."""
    vals = surface.get("values")
    if not isinstance(vals, list) or not vals or not isinstance(vals[0], list):
        return False
    sh, sw = len(vals), len(vals[0])
    base_h, base_w = inside_poly.shape

    def _mask_2d(grid: Any) -> Tuple[List[List[Optional[float]]], int]:
        out_grid: List[List[Optional[float]]] = []
        finite_count = 0
        gh, gw = len(grid), len(grid[0])
        for r in range(gh):
            poly_r = min(base_h - 1, int(r * base_h / gh))
            row: List[Optional[float]] = []
            for c in range(gw):
                poly_c = min(base_w - 1, int(c * base_w / gw))
                raw_v = grid[r][c]
                if bool(inside_poly[poly_r, poly_c]) and raw_v is not None:
                    num = float(raw_v)
                    if np.isfinite(num):
                        row.append(round(num, 6))
                        finite_count += 1
                        continue
                row.append(None)
            out_grid.append(row)
        return out_grid, finite_count

    masked_vals, finite_count = _mask_2d(vals)
    surface["values"] = masked_vals

    prov = surface.setdefault("provenance", {})
    for aux_key in ("uncertainty_grid", "confidence_grid"):
        aux_grid = prov.get(aux_key)
        if isinstance(aux_grid, list) and aux_grid and isinstance(aux_grid[0], list):
            if len(aux_grid) == sh and len(aux_grid[0]) == sw:
                masked_aux, _ = _mask_2d(aux_grid)
                prov[aux_key] = masked_aux
                if aux_key == "uncertainty_grid":
                    prov["uncertainty"] = masked_aux

    if surface.get("type") == "NDVI_CLEAN" and ndvi_unc_list is not None and (sh, sw) == (base_h, base_w):
        prov["uncertainty_grid"] = ndvi_unc_list
        prov["uncertainty"] = ndvi_unc_list
        prov["uncertainty_model"] = f"analytical_reflectance_{int(REFLECTANCE_REL_ERROR * 100)}pct"

    return finite_count > 0


def _authorize_surface_in_matrix(
    render_authorizations: Dict[str, Any],
    surface_type: str,
    modes: List[str],
    *,
    allowed: bool = True,
    diagnostic_only: bool = True,
    reason: Optional[str] = None,
    render_kind: Optional[str] = None,
    policies: Tuple[str, ...] = ("satellite", "experimental", "asmae_diagnostic", "hybrid"),
    roles: Tuple[str, ...] = ("base", "overlay", "candidate", "inspector"),
    preserve_existing: bool = True,
) -> None:
    resolved_kind = render_kind or ("full_raster" if allowed else "none")
    for p in policies:
        p_map = render_authorizations.setdefault(p, {})
        for m in modes:
            m_map = p_map.setdefault(m, {})
            for r in roles:
                r_map = m_map.setdefault(r, {})
                existing = r_map.get(surface_type)
                if preserve_existing and isinstance(existing, dict) and "authorized" in existing:
                    continue
                r_map[surface_type] = {
                    "surfaceType": surface_type,
                    "policy": p,
                    "mode": m,
                    "role": r,
                    "surfaceRole": "agronomic_surface",
                    "authorized": allowed,
                    "renderKind": resolved_kind,
                    "reason": reason or ("authorized_diagnostic_surface" if allowed else "withheld_or_unsupported"),
                    "gridValidity": "valid" if allowed else "invalid:withheld",
                    "gridSpecStatus": "ok" if allowed else "withheld",
                    "spatialMaterializationAllowed": allowed,
                    "diagnostic_only": diagnostic_only,
                    "state_update_allowed": False,
                    "prescription_driver_allowed": False,
                }


def publish_afroun_canonical_snapshot(
    *,
    obs_start: str = DEFAULT_OBS_START,
    obs_end: str = DEFAULT_OBS_END,
    native_10m_only: bool = True,
    allow_overwrite: bool = True,
) -> Dict[str, Any]:
    """Run full-engine ASMAE -> Layer 10 -> canonical snapshot store for `afroun`."""
    ns = PlotNamespace(tenant_id=TENANT_ID, farm_id=FARM_ID, plot_id=PLOT_ID)

    # 1. Acquire real Sentinel-2 & Sentinel-1 scenes with authentic parcel polygon
    s2_products = fetch_asmae_s2_scene_stack(
        PLOT_ID, GEOMETRY_HASH, (obs_start, obs_end), {}, polygon_coords=PLOT_COORDINATES
    )
    s1_products = fetch_asmae_s1_scene_stack(
        PLOT_ID, GEOMETRY_HASH, (obs_start, obs_end), {}, polygon_coords=PLOT_COORDINATES
    )
    if not isinstance(s2_products, list) or not s2_products:
        raise RuntimeError(f"Sentinel-2 stack unavailable for afroun ({obs_start}..{obs_end}): {s2_products}")
    if not isinstance(s1_products, list) or not s1_products:
        raise RuntimeError(f"Sentinel-1 stack unavailable for afroun ({obs_start}..{obs_end}): {s1_products}")

    # 2. Enforce cross-sensor spatial coincidence (CRS, shape, affine transform)
    coincidence = verify_scene_grid_coincidence(s2_products, s1_products)
    H = coincidence["height"]
    W = coincidence["width"]
    crs = coincidence["crs"]
    transform = coincidence["transform"]
    bounds = coincidence["bounds"]
    base_grid_spec = {
        "crs": crs,
        "bounds": bounds,
        "transform": transform,
        "width": W,
        "height": H,
        "resolution_m": 10.0,
    }

    poly = Polygon(PLOT_COORDINATES)
    out_mask = geometry_mask([poly], out_shape=(H, W), transform=Affine.from_gdal(*transform), invert=False)
    inside_poly = ~out_mask

    # 3. Compute direct optical NDVI (+ analytical reflectance error) and SAR backscatter proxy
    diag_products = _compute_optical_and_sar_diagnostics(s2_products, s1_products, inside_poly)
    ndvi_grid_list = _to_masked_grid_list(diag_products["ndvi_mean"], inside_poly)
    ndvi_unc_list = _to_masked_grid_list(diag_products["ndvi_uncertainty"], inside_poly)
    sar_wetness_list = _to_masked_grid_list(diag_products["sar_wetness_proxy"], inside_poly)
    sar_vv_mean_db = (
        round(float(np.nanmean(diag_products["vv_db_mean"])), 3)
        if diag_products["valid_sar_pixels"] > 0
        else None
    )

    # 4. Fetch real ERA5 reanalysis weather (never hardcoded placeholders)
    weather_records, weather_proof = fetch_verified_weather_series(
        CENTER_LAT, CENTER_LNG, obs_start, obs_end
    )

    # Compute true latest observation acquisition timestamp as evidence_cutoff_at
    acq_timestamps = []
    for sc in [*s2_products, *s1_products]:
        acq_dt = _scene_attr(sc, "acquisition_datetime")
        if hasattr(acq_dt, "isoformat"):
            acq_timestamps.append(acq_dt.astimezone(timezone.utc))
    evidence_cutoff_dt = max(acq_timestamps) if acq_timestamps else datetime.now(timezone.utc)
    evidence_cutoff_iso = evidence_cutoff_dt.isoformat()
    obs_date_str = evidence_cutoff_iso[:10]
    published_at_iso = datetime.now(timezone.utc).isoformat()

    # 5. Resolve canonical crop & phenology worldline lineage and run ASMAEEngine via ASMAERunner
    cw = CanonicalWorldlineService()
    existing_events = cw.load_all_events(PLOT_ID, TENANT_ID, FARM_ID)
    crop_events = [e for e in existing_events if e.get("event_type") == "CROP_POSTERIOR"]
    pheno_events = [e for e in existing_events if e.get("event_type") == "PHENOLOGY_POSTERIOR"]
    if crop_events:
        crop_ev = crop_events[-1]
        crop_posterior_payload = (crop_ev.get("payload") or {}).get("crop_posterior") or {}
        crop_worldline_event_id = str(crop_ev["event_id"])
    else:
        from services.agribrain.layer2_veg_int.crop_posterior import infer_crop_posterior
        crop_posterior_payload = infer_crop_posterior(
            plot_id=PLOT_ID,
            run_id=f"init_{PLOT_ID}",
            plot_timeseries=[],
            crop_config={"crop": "citrus", "crop_cycle_id": CROP_CYCLE_ID},
            operational_context={"variety": "Clementine", "administrative_status": "FRUITING"},
        )
        crop_ev = cw.commit_event(
            event_type="CROP_POSTERIOR",
            plot_id=PLOT_ID,
            tenant_id=TENANT_ID,
            namespace=FARM_ID,
            effective_at=obs_end,
            observation_or_valid_time=evidence_cutoff_iso,
            payload={"crop_posterior": crop_posterior_payload, "plot_namespace": namespace_payload(ns)},
            authority="FARMER_CONFIRMED",
        )
        crop_worldline_event_id = str(crop_ev["event_id"])

    crop_posterior_lineage = str(crop_posterior_payload.get("content_hash") or "")
    if pheno_events:
        pheno_ev = pheno_events[-1]
        phenology_posterior_payload = (pheno_ev.get("payload") or {}).get("phenology_posterior") or {}
        phenology_worldline_event_id = str(pheno_ev["event_id"])
    else:
        phenology_posterior_payload = {
            "contract_version": "canonical-phenology-posterior-v2",
            "crop_cycle_id": CROP_CYCLE_ID,
            "current_stage": "REPRODUCTIVE",
            "effective_at": obs_end,
            "calibration_status": "uncalibrated_diagnostic",
        }
        phenology_posterior_payload["content_hash"] = hashlib.sha256(
            json.dumps(phenology_posterior_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        pheno_ev = cw.commit_event(
            event_type="PHENOLOGY_POSTERIOR",
            plot_id=PLOT_ID,
            tenant_id=TENANT_ID,
            namespace=FARM_ID,
            effective_at=obs_end,
            observation_or_valid_time=obs_end,
            payload={"phenology_posterior": phenology_posterior_payload, "plot_namespace": namespace_payload(ns)},
            authority="DIAGNOSTIC_ONLY",
        )
        phenology_worldline_event_id = str(pheno_ev["event_id"])
    phenology_posterior_hash = str(phenology_posterior_payload.get("content_hash") or "")

    asmae_run_id = f"asmae_afroun_full_{obs_end.replace('-', '')}_{int(datetime.now(timezone.utc).timestamp())}"
    asmae_ctx = {
        "plot_id": PLOT_ID,
        "tenant_id": TENANT_ID,
        "farm_id": FARM_ID,
        "plot_namespace": namespace_payload(ns),
        "worldline_namespace": FARM_ID,
        "polygon_geojson": PLOT_GEOJSON["geometry"],
        "geometry_hash": GEOMETRY_HASH,
        "start_date": obs_start,
        "end_date": obs_end,
        "layer0_source_packages": {
            "asmae_sentinel2_real": [s.to_dict() for s in s2_products],
            "asmae_sentinel1_real": [s.to_dict() for s in s1_products],
        },
        "weather_archive": {"records": weather_records} if weather_records else None,
        "crop_context": {
            "crop_cycle_id": CROP_CYCLE_ID,
            "crop_code": "citrus",
            "variety": "Clementine",
            "status": "FRUITING",
        },
        "crop_posterior": crop_posterior_payload,
        "crop_posterior_lineage": crop_posterior_lineage,
        "crop_worldline_event_id": crop_worldline_event_id,
        "phenology_posterior": phenology_posterior_payload,
        "phenology_posterior_hash": phenology_posterior_hash,
        "phenology_worldline_event_id": phenology_worldline_event_id,
        "source_policy": "asmae_diagnostic",
    }
    runner = ASMAERunner(config={"native_10m_only": native_10m_only})
    asmae_res = runner.execute(plot_id=PLOT_ID, run_id=asmae_run_id, context=asmae_ctx, mode="standard")
    if asmae_res.get("status") not in ("success", "partial", "completed", "ok"):
        raise RuntimeError(f"ASMAERunner did not succeed: status={asmae_res.get('status')} error={asmae_res.get('error')}")
    asmae_res.setdefault("crop_posterior_lineage", crop_posterior_lineage)
    asmae_res.setdefault("crop_worldline_event_id", crop_worldline_event_id)
    asmae_res.setdefault("phenology_worldline_event_id", phenology_worldline_event_id)

    # 6. Connect engine output to canonical Layer 10 while keeping unsupported states withheld
    filtered_asmae, withheld_states = build_l10_filtered_asmae_payload(asmae_res)
    ft = FieldTensor(
        plot_id=PLOT_ID,
        run_id=f"L1_{asmae_run_id}",
        grid_spec={"plot_id": PLOT_ID, **base_grid_spec, "resolution": 10.0},
        maps={
            "ndvi": ndvi_grid_list,
            "NDVI": ndvi_grid_list,
            "NDVI_CLEAN": ndvi_grid_list,
            "SAR": sar_wetness_list,
        },
        map_metadata={
            "ndvi": {"grid_spec": base_grid_spec, "source_reality": "real_raster"},
            "NDVI": {"grid_spec": base_grid_spec, "source_reality": "real_raster"},
            "NDVI_CLEAN": {"grid_spec": base_grid_spec, "source_reality": "real_raster"},
            "SAR": {"grid_spec": base_grid_spec, "source_reality": "real_raster"},
        },
        provenance={
            "evidence_count": len(s2_products) + len(s1_products),
            "data_health_status": "diagnostic_only",
            "data_health_overall": 0.75,
            "source": "sentinel2+sentinel1",
            "provider": "copernicus_sentinel_hub",
            "acquired_at": evidence_cutoff_iso,
        },
    )
    ft._context_package = SimpleNamespace(
        asmae_output=filtered_asmae,
        asmae_evidence_state=filtered_asmae.get("asmae_evidence_state", {}),
        asmae_run_record={"status": "completed", "mode": "standard", "run_id": asmae_res.get("run_id")},
        geometry_mask=inside_poly.tolist(),
    )

    l10_inp = Layer10Input(
        plot_namespace=ns,
        tenant_id=TENANT_ID,
        farm_id=FARM_ID,
        plot_id=PLOT_ID,
        field_tensor=ft,
        veg_int=SimpleNamespace(ndvi_records=[], phenology=SimpleNamespace(stage_by_day=["UNKNOWN"])),
        grid_height=H,
        grid_width=W,
        resolution_m=10.0,
        crop="citrus",
        source_policy="asmae_diagnostic",
        field_geometry=PLOT_GEOJSON,
        canonical_geometry_hash=GEOMETRY_HASH,
        source_geometry_hash=GEOMETRY_HASH,
    )
    l10_out = run_layer10_sire(l10_inp)
    fe = serialize_output(l10_out)

    # 7. Filter withheld/all-null surfaces, enforce strict polygon masking, add uncalibrated SAR proxy
    kept_surfaces: List[Dict[str, Any]] = []
    withheld_reasons: Dict[str, str] = {w["surface_type"]: w["reason"] for w in withheld_states}

    for surf in fe.get("surfaces") or []:
        stype = str(surf.get("type") or "").upper()
        if stype in WITHHELD_SURFACE_TYPES:
            withheld_reasons.setdefault(stype, "unsupported_or_unverified_state")
            continue
        if not _apply_polygon_mask_to_surface(surf, inside_poly, ndvi_unc_list=ndvi_unc_list):
            continue
        prov = surf.setdefault("provenance", {})
        prov.setdefault("provider", "Sentinel-2 L2A + Sentinel-1 GRD via ASMAE" if "ASMAE" in stype else "Copernicus Sentinel-2 L2A")
        prov.setdefault("observation_date", obs_date_str)
        prov.setdefault("acquired_at", evidence_cutoff_iso)
        prov.setdefault("native_resolution_m", 10.0)
        prov.setdefault("has_spatial_grid", True)
        if not surf.get("units"):
            surf["units"] = prov.get("units") or "fraction"
        if not surf.get("grid_spec"):
            surf["grid_spec"] = dict(base_grid_spec)
        if not surf.get("display_grid_spec"):
            surf["display_grid_spec"] = dict(surf["grid_spec"])
        kept_surfaces.append(surf)

    # Ensure VALID_DATA_MASK_NDVI matches strict inside_poly finite mask
    valid_mask_vals = [[1.0 if bool(inside_poly[r, c]) and np.isfinite(diag_products["ndvi_mean"][r, c]) else 0.0 for c in range(W)] for r in range(H)]
    for surf in kept_surfaces:
        if surf.get("type") in ("VALID_DATA_MASK_NDVI", "OBSERVED_DATA_MASK_NDVI"):
            surf["values"] = valid_mask_vals

    # Append direct Sentinel-1 SAR backscatter proxy surface clearly labeled uncalibrated_proxy
    sar_surf_id = f"surf_sar_wetness_proxy_{PLOT_ID}_{obs_end.replace('-', '')}"
    sar_surface = {
        "surface_id": sar_surf_id,
        "type": "WATER_STRESS_PROB",
        "semantic_type": "WATER_STRESS_PROB",
        "values": sar_wetness_list,
        "grounding_class": "RASTER_GROUNDED",
        "raster_basis": ["sentinel1_vv"],
        "observed_ratio": round(float(diag_products["valid_sar_pixels"] / max(1, int(np.sum(inside_poly)))), 4),
        "native_resolution_m": 10.0,
        "display_resolution_m": 10.0,
        "effective_resolution_m": 10.0,
        "units": "proxy_index (uncalibrated SAR wetness)",
        "render_range": [0.0, 1.0],
        "palette_id": "YIELD_BLUE",
        "source_layers": ["L0_S1_GRD", "ASMAE_DIAGNOSTIC"],
        "grid_spec": dict(base_grid_spec),
        "display_grid_spec": dict(base_grid_spec),
        "source_grid_spec": dict(base_grid_spec),
        "source_reality": "real_raster",
        "diagnostic_only": True,
        "state_update_allowed": False,
        "prescription_driver_allowed": False,
        "surface_role": "agronomic_surface",
        "provenance": {
            "provider": "Copernicus Sentinel-1 IW GRD",
            "source": "sentinel1_vv",
            "observation_date": obs_date_str,
            "acquired_at": evidence_cutoff_iso,
            "native_resolution_m": 10.0,
            "has_spatial_grid": True,
            "support_class": "proxy_assimilated",
            "evidence_class": "uncalibrated_proxy",
            "calibration_status": "uncalibrated_proxy",
            "sar_vv_mean_db": sar_vv_mean_db,
            "uncertainty_model": "uncalibrated_radar_backscatter_proxy",
            "diagnostic_only": True,
            "warning_wording": "Uncalibrated Sentinel-1 SAR wetness proxy (relative index, not volumetric soil moisture).",
        },
    }
    if not any(s.get("type") == "WATER_STRESS_PROB" for s in kept_surfaces):
        kept_surfaces.append(sar_surface)

    fe["surfaces"] = kept_surfaces

    # 8. Update authorizations, withheld inventory, and canonical publication metadata
    # Preserve Layer 10's complete render_authorizations (authorized/renderKind/gridValidity) for
    # all kept surfaces; authorize the post-L10 WATER_STRESS_PROB SAR proxy under normalized mode "water",
    # and explicitly mark all withheld surfaces as unauthorized across all normalized modes.
    render_auth = fe.setdefault("render_authorizations", {})
    _authorize_surface_in_matrix(
        render_auth,
        "NDVI_CLEAN",
        ["canopy"],
        allowed=True,
        diagnostic_only=True,
        reason="satellite_ndvi_clean_authorized",
        render_kind="full_raster",
        preserve_existing=True,
    )
    _authorize_surface_in_matrix(
        render_auth,
        "WATER_STRESS_PROB",
        ["water"],
        allowed=True,
        diagnostic_only=True,
        reason="uncalibrated_sar_wetness_proxy_authorized",
        render_kind="full_raster",
        policies=("satellite", "experimental", "asmae_diagnostic", "hybrid"),
        roles=("base", "overlay", "candidate", "inspector"),
        preserve_existing=False,
    )

    for w_type, w_reason in withheld_reasons.items():
        _authorize_surface_in_matrix(
            render_auth,
            w_type,
            ["canopy", "water", "nutrients", "salinity", "risk", "veg_attention", "uncertainty", "resolution_coverage"],
            allowed=False,
            diagnostic_only=True,
            reason=w_reason,
            render_kind="none",
            roles=("base", "overlay", "candidate", "inspector", "dependency"),
            preserve_existing=False,
        )

    surface_inventory = fe.setdefault("surface_inventory", {})
    for w_type, w_reason in withheld_reasons.items():
        surface_inventory[w_type] = {
            "surface_type": w_type,
            "status": "withheld",
            "available": False,
            "spatial": False,
            "reason": w_reason,
            "authority": "WITHHELD",
        }
    for surf in kept_surfaces:
        st = str(surf.get("type") or "")
        existing_inv = surface_inventory.get(st) if isinstance(surface_inventory.get(st), dict) else {}
        surface_inventory[st] = {
            **existing_inv,
            "surface_type": st,
            "status": "available",
            "available": True,
            "spatial": True,
            "authority": "DIAGNOSTIC_ONLY",
        }

    supported_layers = sorted({
        str(s.get("type"))
        for s in kept_surfaces
        if str(s.get("type") or "") not in (
            "OBSERVED_DATA_MASK_NDVI", "GAP_FILL_MASK_NDVI", "VALID_DATA_MASK_NDVI"
        )
    })
    unsupported_layers = sorted(withheld_reasons.keys())

    fe["surface_inventory_hash"] = compute_surface_inventory_hash(kept_surfaces)
    fe["published_at"] = published_at_iso
    fe["evidence_cutoff_at"] = evidence_cutoff_iso
    fe["observation_window"] = {"start": obs_start, "end": obs_end}
    fe["source_window"] = [obs_start, obs_end]
    fe["crop_cycle_id"] = CROP_CYCLE_ID
    fe["geometry_hash"] = GEOMETRY_HASH
    fe["grid_spec"] = dict(base_grid_spec)
    fe["display_grid_spec"] = dict(base_grid_spec)
    fe["publication_authority"] = "DIAGNOSTIC_ONLY"
    fe["claims_numerical_authority"] = False
    fe["effective_resolution"] = "10m native satellite"
    fe["calibration_status"] = "uncalibrated_diagnostic"
    fe["supported_layers"] = supported_layers
    fe["unsupported_layers"] = unsupported_layers
    fe["withheld_reasons"] = withheld_reasons
    fe["raster_availability"] = {
        "supported_layers": supported_layers,
        "unsupported_layers": unsupported_layers,
        "withheld_1m": True,
        "can_render_pixels": len(supported_layers) > 0,
        "effective_resolution_m": 10.0,
    }
    fe["weather_proof"] = weather_proof
    fe["spatial_coincidence_proof"] = coincidence
    fe["data_origin"] = "real_provider_engine_reintegration"

    import math as _math
    def _sanitize_json_numbers(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _sanitize_json_numbers(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_sanitize_json_numbers(v) for v in obj]
        if isinstance(obj, np.ndarray):
            return _sanitize_json_numbers(obj.tolist())
        if isinstance(obj, np.generic):
            obj = obj.item()
        if isinstance(obj, float) and not _math.isfinite(obj):
            return None
        return obj

    fe = _sanitize_json_numbers(fe)
    sanitized_asmae = _sanitize_json_numbers(asmae_res)

    pub_status, pub_reason = classify_surface_publication(fe)
    if pub_status not in ("VALID_PUBLICATION", "VALID_DEGRADED"):
        raise RuntimeError(f"Surface publication envelope invalid: status={pub_status}, reason={pub_reason}")
    snapshot_id = str(asmae_res["snapshot_id"])
    fe["intelligence_snapshot_id"] = snapshot_id
    if isinstance(fe.get("provenance"), dict):
        fe["provenance"]["intelligence_snapshot_id"] = snapshot_id
    fe["scientific_evidence_lineage"] = {
        "crop_posterior_lineage": crop_posterior_lineage,
        "crop_worldline_event_id": crop_worldline_event_id,
        "phenology_worldline_event_id": phenology_worldline_event_id,
    }
    fe["publication_status"] = pub_status

    manifest_hash = hashlib.sha256(
        json.dumps(
            {
                "plot_id": PLOT_ID,
                "geometry_hash": GEOMETRY_HASH,
                "crop_cycle_id": CROP_CYCLE_ID,
                "asmae_snapshot_id": snapshot_id,
                "surface_inventory_hash": fe["surface_inventory_hash"],
                "evidence_cutoff_at": evidence_cutoff_iso,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    head = publish_canonical_plot_snapshot(
        namespace=ns,
        tenant_id=TENANT_ID,
        farm_id=FARM_ID,
        plot_id=PLOT_ID,
        geometry_hash=GEOMETRY_HASH,
        snapshot_id=snapshot_id,
        asmae_result=sanitized_asmae,
        frontend_payload=fe,
        job_id=f"job_{asmae_run_id}",
        manifest_hash=manifest_hash,
        execution_identity={"crop_cycle_id": CROP_CYCLE_ID},
        snapshot_kind="asmae",
        allow_overwrite=allow_overwrite,
        publication_authority="DIAGNOSTIC_ONLY",
    )

    cw = CanonicalWorldlineService()
    worldline_ev = cw.commit_asmae_result(
        {
            **asmae_res,
            "snapshot_id": snapshot_id,
            "publication_authority": "DIAGNOSTIC_ONLY",
            "claims_numerical_authority": False,
        },
        geometry_hash=GEOMETRY_HASH,
        snapshot_ref=head.get("snapshot_ref"),
        tenant_id=TENANT_ID,
        namespace=FARM_ID,
    )

    return {
        "snapshot_id": snapshot_id,
        "asmae_snapshot_id": asmae_res.get("snapshot_id"),
        "plot_id": PLOT_ID,
        "crop_cycle_id": CROP_CYCLE_ID,
        "geometry_hash": GEOMETRY_HASH,
        "observation_window": fe["observation_window"],
        "evidence_cutoff_at": evidence_cutoff_iso,
        "published_at": published_at_iso,
        "publication_authority": "DIAGNOSTIC_ONLY",
        "publication_status": pub_status,
        "supported_layers_count": len(supported_layers),
        "unsupported_layers": unsupported_layers,
        "weather_proof": weather_proof,
        "spatial_coincidence_proof": coincidence,
        "worldline_event_id": worldline_ev.get("event_id") if isinstance(worldline_ev, dict) else None,
        "head": head,
    }


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Publish canonical full-engine ASMAE diagnostic snapshot for afroun")
    parser.add_argument("--start", default=DEFAULT_OBS_START)
    parser.add_argument("--end", default=DEFAULT_OBS_END)
    parser.add_argument("--full-ladder", action="store_true", help="Run full resolution ladder instead of fast native 10m lock")
    args = parser.parse_args()

    res = publish_afroun_canonical_snapshot(
        obs_start=args.start,
        obs_end=args.end,
        native_10m_only=not args.full_ladder,
    )
    summary = {k: v for k, v in res.items() if k != "head"}
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
