"""Crop Identity - ASMAE Historical Fusion reusing Layer 2 CropIdentification & CropPosterior (V2).

Computes chronological bitemporal seasonal crop posteriors P(C_t | O_{<=t}, K),
tracks versioned product availability per physical acquisition (WM1-P1-03),
preserves exact crop declaration vs confirmation authority (WM1-P1-02),
applies bounded post-ASMAE refinement, and reports standard multiclass calibration
& unknown-class metrics across verified crop & true non-crop/unknown sets (WM1-P2-09).
"""

from __future__ import annotations

import json
import math
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from services.agribrain.crop_database import get_crop_with_provenance
except ImportError:
    from crop_database import get_crop_with_provenance
from services.agribrain.layer2_veg_int.crop_observations import (
    build_canonical_crop_observations,
    build_crop_evidence_ledger,
)
from services.agribrain.layer2_veg_int.crop_posterior import (
    condition_crop_context,
    infer_crop_posterior,
    refine_crop_posterior,
)
from services.agribrain.scientific_contracts.crop_cycle_segmentation import (
    build_crop_cycle_segmentation_receipt,
)

from .domain_chronology import DomainChronology, _parse_iso_utc
from .world_model_contracts import CONFIRMED_CROP_AUTHORITIES


_BROAD_GROUPS: Tuple[str, ...] = (
    "orchard",
    "cereal",
    "vegetable",
    "legume",
    "forage",
    "other",
    "unknown",
)


def _obs_time_utc(obs: Mapping[str, Any]) -> Optional[datetime]:
    return (
        _parse_iso_utc(obs.get("sensing_timestamp"))
        or _parse_iso_utc(obs.get("sensing_time"))
        or _parse_iso_utc(obs.get("timestamp"))
        or _parse_iso_utc(obs.get("acquisition_datetime"))
        or _parse_iso_utc(obs.get("date"))
    )


def _extract_version_entries(obs: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Return normalized documented product versions with explicit availability timestamps (WM1-P1-03)."""
    acq_ts = _obs_time_utc(obs)
    entries: List[Dict[str, Any]] = []

    raw_history = obs.get("version_history") or obs.get("product_versions") or []
    if isinstance(raw_history, list):
        for item in raw_history:
            if not isinstance(item, Mapping):
                continue
            avail = (
                _parse_iso_utc(item.get("version_available_at"))
                or _parse_iso_utc(item.get("available_at"))
                or _parse_iso_utc(item.get("knowledge_time"))
                or _parse_iso_utc(item.get("processing_timestamp"))
            )
            if avail is not None:
                entries.append({
                    **dict(item),
                    "_available_at": avail,
                    "_sensing_ts": _parse_iso_utc(item.get("sensing_timestamp") or item.get("sensing_time")) or acq_ts,
                    "processing_baseline": str(item.get("processing_baseline") or item.get("baseline") or "unknown"),
                })

    for lin in obs.get("processing_lineage") or []:
        if not isinstance(lin, Mapping):
            continue
        avail = (
            _parse_iso_utc(lin.get("version_available_at"))
            or _parse_iso_utc(lin.get("available_at"))
            or _parse_iso_utc(lin.get("knowledge_time"))
            or _parse_iso_utc(obs.get("available_at"))
            or _parse_iso_utc(obs.get("knowledge_time"))
            or _parse_iso_utc(lin.get("processing_timestamp"))
        )
        if avail is not None:
            entries.append({
                "provider_product_id": lin.get("provider_product_id"),
                "processing_baseline": str(lin.get("processing_baseline") or "unknown"),
                "processing_timestamp": lin.get("processing_timestamp"),
                "available_at": avail.isoformat(),
                "_available_at": avail,
                "_sensing_ts": acq_ts,
                "content_hash": lin.get("content_hash"),
            })

    if not entries:
        top_avail = (
            _parse_iso_utc(obs.get("version_available_at"))
            or _parse_iso_utc(obs.get("available_at"))
            or _parse_iso_utc(obs.get("knowledge_time"))
            or _parse_iso_utc(obs.get("processing_timestamp"))
            or acq_ts
        )
        if top_avail is not None:
            entries.append({
                "processing_baseline": str(obs.get("processing_baseline") or "undocumented"),
                "available_at": top_avail.isoformat(),
                "_available_at": top_avail,
                "_sensing_ts": acq_ts,
            })

    entries.sort(key=lambda e: (e["_available_at"], str(e.get("processing_baseline") or "")))
    return entries


def _select_eligible_product_version_as_of(
    obs: Mapping[str, Any],
    *,
    valid_time_T: Optional[datetime],
    knowledge_cutoff_K: Optional[datetime],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Select the newest documented product version eligible by (T, K); NEVER backdate reprocessing (WM1-P1-03)."""
    acq_ts = _obs_time_utc(obs)
    if valid_time_T is not None and acq_ts is not None and acq_ts > valid_time_T:
        return False, None, "future_physical_acquisition"

    versions = _extract_version_entries(obs)
    if not versions:
        return False, None, "missing_version_availability_metadata"

    if knowledge_cutoff_K is None:
        return True, versions[-1], "unbounded_k_latest_version"

    eligible = [
        v for v in versions
        if v["_available_at"] <= knowledge_cutoff_K
        and (v["_sensing_ts"] is None or valid_time_T is None or v["_sensing_ts"] <= valid_time_T)
    ]
    if not eligible:
        return False, None, "reprocessed_or_late_version_unavailable_at_k"
    return True, eligible[-1], "version_eligible_as_of_k"


def _obs_knowledge_utc(obs: Mapping[str, Any]) -> Optional[datetime]:
    """Return earliest documented product availability timestamp (no heuristic backdating)."""
    versions = _extract_version_entries(obs)
    if versions:
        return versions[0]["_available_at"]
    return _obs_time_utc(obs)


def _materialize_obs_for_version(obs: Mapping[str, Any], ver: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Bind observation metrics to the specific documented product version eligible at K."""
    out = dict(obs)
    if isinstance(ver, Mapping) and ver:
        if ver.get("index_statistics") and isinstance(ver["index_statistics"], Mapping):
            out["index_statistics"] = dict(ver["index_statistics"])
        if ver.get("band_statistics") and isinstance(ver["band_statistics"], Mapping):
            out["band_statistics"] = dict(ver["band_statistics"])
        if ver.get("spectral_summary") and isinstance(ver["spectral_summary"], Mapping):
            out["spectral_summary"] = dict(ver["spectral_summary"])
        out["selected_product_version"] = {
            "processing_baseline": ver.get("processing_baseline"),
            "processing_timestamp": ver.get("processing_timestamp"),
            "available_at": ver.get("available_at") or (
                ver["_available_at"].isoformat() if isinstance(ver.get("_available_at"), datetime) else None
            ),
            "provider_product_id": ver.get("provider_product_id"),
        }
    return out


def _entropy(dist: Mapping[str, Any]) -> float:
    h = 0.0
    for val in dist.values():
        p = float(val or 0.0)
        if p > 1e-12:
            h -= p * math.log(p)
    return round(h, 6)


def _broad_crop_group(code_or_arch: str) -> str:
    low = str(code_or_arch or "unknown").strip().lower()
    if low in {
        "citrus", "clementine", "orange", "olive", "date_palm", "almond",
        "orchard", "perennial", "tropical_tree", "evergreen_orchard",
        "deciduous_orchard", "tropical_palm",
    }:
        return "orchard"
    if low in {
        "wheat", "durum_wheat", "barley", "oat", "corn", "maize", "rice",
        "cereal", "winter_cereal", "summer_cereal", "pseudo_cereal",
    }:
        return "cereal"
    if low in {
        "tomato", "potato", "pepper", "vegetable", "solanaceae_veg",
        "cucurbit_veg", "allium_veg", "root_tuber", "horticulture", "leafy_veg",
    }:
        return "vegetable"
    if low in {
        "chickpea", "lentil", "fava_bean", "soybean", "legume",
        "cool_legume", "warm_legume",
    }:
        return "legume"
    if low in {"alfalfa", "forage"}:
        return "forage"
    if low in {"unknown", "non_crop", "bare_soil", "fallow", "mixed_unknown"}:
        return "unknown"
    return "other"


def adapt_scenes_to_source_packages(
    scenes: Sequence[Mapping[str, Any]],
    *,
    plot_id: str,
    tenant_id: str,
    farm_id: Optional[str],
    plot_geometry: Optional[Mapping[str, Any]],
    geometry_hash: str,
    scene_cache_dir: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Adapt historical archive SafeScene entries into Layer 2 physical source packages."""
    s2_pkgs: List[Dict[str, Any]] = []
    s1_pkgs: List[Dict[str, Any]] = []

    safe_lookup: Dict[str, Path] = {}
    if scene_cache_dir and os.path.isdir(scene_cache_dir):
        for entry in Path(scene_cache_dir).iterdir():
            if entry.is_dir() and (entry / "metadata.json").exists():
                safe_lookup[entry.name] = entry

    for scene in scenes or []:
        rt = scene.get("runtime") if isinstance(scene, Mapping) else getattr(scene, "runtime", None)
        if rt is None and isinstance(scene, Mapping) and scene.get("acquisition_time"):
            src_raw = str(scene.get("source") or scene.get("sensor") or "sentinel2").lower()
            is_s1 = "s1" in src_raw or "sentinel1" in src_raw
            sensor = "S1" if is_s1 else "S2"
            scene_id = str(scene.get("scene_id") or scene.get("provider_product_id") or "")
            provider_id = str(scene.get("provider_product_id") or scene.get("catalog_item_id") or scene_id)
            avail_ts = (
                scene.get("version_available_at")
                or scene.get("product_available_at")
                or scene.get("available_at")
                or scene.get("processing_timestamp")
                or scene.get("generation_time")
            )
            metrics = dict(scene.get("metrics") or {})
            pkt = {
                "timestamp": str(scene["acquisition_time"]),
                "source_reality": str(scene.get("source_reality") or "real_raster"),
                "real_provider_product": bool(scene.get("real_provider_product", True)),
                "production_usable": bool(scene.get("production_usable", True)),
                "diagnostic_only": bool(scene.get("diagnostic_only", False)),
                "quality_admitted": bool(scene.get("quality_score", 1.0) >= 0.4),
                "usable": True,
                "valid_fraction": float(scene.get("valid_pixel_fraction", 0.95) or 0.95),
                "cloud_fraction": float(scene.get("cloud_score", 0.05) or 0.05),
                "ndvi_mean": metrics.get("ndvi_mean"),
                "evi_mean": metrics.get("evi_mean"),
                "ndmi_mean": metrics.get("ndmi_mean"),
                "ndre_mean": metrics.get("ndre_mean"),
                "vv_db_mean": metrics.get("vv_mean_db"),
                "vh_db_mean": metrics.get("vh_mean_db"),
            }
            pkg = {
                "source_family": "sentinel1" if is_s1 else "sentinel2",
                "metadata": {
                    "source_family": "sentinel1" if is_s1 else "sentinel2",
                    "provider_product_id": provider_id,
                    "scene_id": scene_id,
                    "plot_geometry_hash": geometry_hash,
                    "source_reality": str(scene.get("source_reality") or "real_raster"),
                    "production_usable": bool(scene.get("production_usable", True)),
                    "real_provider_product": bool(scene.get("real_provider_product", True)),
                    "diagnostic_only": bool(scene.get("diagnostic_only", False)),
                    "processing_baseline": scene.get("processing_baseline"),
                    "processing_timestamp": avail_ts,
                    "generation_time": avail_ts,
                    "available_at": avail_ts,
                    "plot_id": plot_id,
                    "tenant_id": tenant_id,
                    "farm_id": farm_id or "default_farm",
                },
                "processing_baseline": scene.get("processing_baseline"),
                "processing_timestamp": avail_ts,
                "generation_time": avail_ts,
                "version_history": list(scene.get("version_history") or []),
                "packets": [pkt],
            }
            if sensor == "S2":
                s2_pkgs.append(pkg)
            else:
                s1_pkgs.append(pkg)
            continue
        if rt is None:
            continue
        sensor = str(getattr(rt, "sensor", "") or "").upper()
        acq_dt = getattr(rt, "acquisition_time", None)
        scene_id = str(getattr(rt, "scene_id", "") or "")
        provider_id = str(getattr(rt, "provider_product_id", None) or getattr(rt, "catalog_item_id", None) or scene_id)

        safe_dir = safe_lookup.get(provider_id) or safe_lookup.get(scene_id)
        if safe_dir is not None:
            try:
                meta = json.loads((safe_dir / "metadata.json").read_text(encoding="utf-8"))
                refs = {f.stem.upper(): str(f) for f in safe_dir.glob("*.npz")}
                pkg = {
                    "metadata": {
                        **meta,
                        "plot_id": plot_id,
                        "tenant_id": tenant_id,
                        "farm_id": farm_id or "default_farm",
                        "plot_geometry_hash": geometry_hash,
                    },
                    **meta,
                    "local_cache_refs": refs,
                    "plot_geometry": plot_geometry,
                    "plot_geometry_crs": "EPSG:4326",
                    "plot_id": plot_id,
                    "tenant_id": tenant_id,
                    "farm_id": farm_id or "default_farm",
                }
                if sensor == "S2":
                    s2_pkgs.append(pkg)
                elif sensor == "S1":
                    s1_pkgs.append(pkg)
                continue
            except Exception:
                pass

        bands = dict(getattr(rt, "bands", {}) or {})

        def _band_mean(k: str) -> Optional[float]:
            v = bands.get(k)
            if v is None:
                return None
            try:
                import numpy as np
                arr = np.asarray(v, dtype=float)
                arr = arr[np.isfinite(arr)]
                return float(np.mean(arr)) if arr.size else None
            except Exception:
                return float(v) if isinstance(v, (int, float)) else None

        pkt = {
            "timestamp": acq_dt.isoformat() if isinstance(acq_dt, datetime) else str(acq_dt or ""),
            "source_reality": str(getattr(rt, "source_reality", "unknown")),
            "real_provider_product": bool(getattr(rt, "real_provider_product", False)),
            "production_usable": bool(getattr(rt, "production_usable", False)),
            "diagnostic_only": bool(getattr(rt, "diagnostic_only", True)),
            "quality_admitted": bool(getattr(rt, "real_provider_product", False)),
            "usable": bool(getattr(rt, "real_provider_product", False)),
            "ndvi_mean": _band_mean("ndvi"),
            "evi_mean": _band_mean("evi"),
            "ndmi_mean": _band_mean("ndmi"),
            "ndwi_mean": _band_mean("ndwi"),
            "vv_db_mean": _band_mean("vv"),
            "vh_db_mean": _band_mean("vh"),
        }
        pkg = {
            "source_family": "sentinel2" if sensor == "S2" else "sentinel1",
            "metadata": {
                "source_family": "sentinel2" if sensor == "S2" else "sentinel1",
                "provider_product_id": provider_id,
                "scene_id": scene_id,
                "plot_geometry_hash": geometry_hash,
                "source_reality": str(getattr(rt, "source_reality", "unknown")),
                "production_usable": bool(getattr(rt, "production_usable", False)),
                "real_provider_product": bool(getattr(rt, "real_provider_product", False)),
                "diagnostic_only": bool(getattr(rt, "diagnostic_only", True)),
                "plot_id": plot_id,
                "tenant_id": tenant_id,
                "farm_id": farm_id or "default_farm",
            },
            "packets": [pkt],
        }
        if sensor == "S2":
            s2_pkgs.append(pkg)
        elif sensor == "S1":
            s1_pkgs.append(pkg)

    if not scenes and scene_cache_dir and os.path.isdir(scene_cache_dir):
        for safe_dir in sorted(Path(scene_cache_dir).iterdir()):
            meta_p = safe_dir / "metadata.json"
            if not safe_dir.is_dir() or not meta_p.is_file():
                continue
            try:
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
                refs = {f.stem.upper(): str(f) for f in safe_dir.glob("*.npz")}
                pkg = {
                    "metadata": {
                        **meta,
                        "plot_id": plot_id,
                        "tenant_id": tenant_id,
                        "farm_id": farm_id or "default_farm",
                        "plot_geometry_hash": geometry_hash,
                    },
                    **meta,
                    "local_cache_refs": refs,
                    "plot_geometry": plot_geometry,
                    "plot_geometry_crs": "EPSG:4326",
                    "plot_id": plot_id,
                    "tenant_id": tenant_id,
                    "farm_id": farm_id or "default_farm",
                }
                sid = str(meta.get("provider_product_id") or meta.get("scene_id") or safe_dir.name).upper()
                if sid.startswith("S2") or "B04" in refs:
                    s2_pkgs.append(pkg)
                elif sid.startswith("S1") or "VV" in refs:
                    s1_pkgs.append(pkg)
            except Exception:
                continue

    return {"sentinel2": s2_pkgs, "sentinel1": s1_pkgs}


def build_historical_crop_observations(
    scenes: Sequence[Mapping[str, Any]],
    *,
    plot_id: str,
    tenant_id: str,
    farm_id: Optional[str],
    plot_geometry: Optional[Mapping[str, Any]],
    geometry_hash: str,
    scene_cache_dir: Optional[str] = None,
    weather_records: Iterable[Any] = (),
) -> List[Dict[str, Any]]:
    """Ingest archive S1/S2 scenes into deduplicated CanonicalCropObservationV2 records."""
    source_packages = adapt_scenes_to_source_packages(
        scenes,
        plot_id=plot_id,
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_geometry=plot_geometry,
        geometry_hash=geometry_hash,
        scene_cache_dir=scene_cache_dir,
    )
    namespace = {
        "tenant_id": tenant_id,
        "farm_id": farm_id or "default_farm",
        "plot_id": plot_id,
    }
    canonical = build_canonical_crop_observations(
        source_packages,
        plot_geometry=plot_geometry,
        geometry_hash=geometry_hash,
        plot_geometry_crs="EPSG:4326",
        plot_namespace=namespace,
        weather_records=weather_records,
    )
    scene_by_key: Dict[str, Mapping[str, Any]] = {}
    for sc in scenes or []:
        if isinstance(sc, Mapping):
            for k in (sc.get("provider_product_id"), sc.get("scene_id"), str(sc.get("acquisition_time") or "")[:19]):
                if k:
                    scene_by_key[str(k)] = sc
    for obs in canonical:
        obs_acq = str(obs.get("sensing_timestamp") or obs.get("timestamp") or obs.get("acquisition_datetime") or "")[:19]
        lin_pid = next(
            (str(l.get("provider_product_id") or "") for l in (obs.get("processing_lineage") or []) if isinstance(l, Mapping) and l.get("provider_product_id")),
            None,
        )
        matched = (
            scene_by_key.get(str(lin_pid or ""))
            or scene_by_key.get(str(obs.get("physical_acquisition_key") or ""))
            or scene_by_key.get(obs_acq)
        )
        if isinstance(matched, Mapping):
            if matched.get("version_history"):
                obs["version_history"] = list(matched["version_history"])
            for av_key in ("version_available_at", "product_available_at", "available_at", "processing_timestamp", "processing_baseline"):
                if matched.get(av_key) and not obs.get(av_key):
                    obs[av_key] = matched[av_key]
    return canonical


def _season_windows_from_observations(
    canonical_obs: Sequence[Dict[str, Any]],
    plot_namespace: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Partition multi-year archive using CropCycleSegmentationReceiptV1 plus annual hydrologic windows."""
    admitted = [o for o in canonical_obs if o.get("quality_admitted") is True and _obs_time_utc(o) is not None]
    admitted.sort(key=lambda o: _obs_time_utc(o))
    if not admitted:
        return [], None

    seg_receipt_dict: Optional[Dict[str, Any]] = None
    optical_breaks: List[Tuple[datetime, str]] = []
    if len(admitted) >= 4:
        try:
            full_ledger = build_crop_evidence_ledger(admitted, plot_namespace=plot_namespace)
            seg_receipt = build_crop_cycle_segmentation_receipt(full_ledger)
            seg_receipt_dict = seg_receipt.to_dict()
            for idx, seg in enumerate(seg_receipt.segments):
                if idx == 0:
                    continue
                st = _parse_iso_utc(seg.start_time)
                if st is not None:
                    optical_breaks.append((st, str(seg.boundary_reason or "optical_segmentation_boundary")))
        except Exception:
            seg_receipt_dict = None

    first_dt = _obs_time_utc(admitted[0])
    last_dt = _obs_time_utc(admitted[-1])
    assert first_dt is not None and last_dt is not None

    breakpoints: List[Tuple[datetime, str]] = [(first_dt, "archive_start")]
    breakpoints.extend(optical_breaks)

    sorted_bps = sorted(breakpoints, key=lambda x: x[0])
    expanded_bps: List[Tuple[datetime, str]] = list(sorted_bps)
    for i, (bp_dt, _) in enumerate(sorted_bps):
        next_bp = sorted_bps[i + 1][0] if i + 1 < len(sorted_bps) else (last_dt + timedelta(days=1))
        if (next_bp - bp_dt).days > 400:
            yr = bp_dt.year
            while yr <= next_bp.year:
                hydro_dt = datetime(yr, 9, 1, 0, 0, tzinfo=timezone.utc)
                if bp_dt + timedelta(days=45) < hydro_dt < next_bp - timedelta(days=45):
                    expanded_bps.append((hydro_dt, "hydrologic_crop_year_boundary"))
                yr += 1
    expanded_bps.sort(key=lambda x: x[0])

    merged_bps: List[Tuple[datetime, str]] = []
    for dt, reason in expanded_bps:
        if not merged_bps or (dt - merged_bps[-1][0]).days >= 35:
            merged_bps.append((dt, reason))
        elif "optical" in reason or "harvest" in reason:
            merged_bps[-1] = (merged_bps[-1][0], reason)

    windows: List[Dict[str, Any]] = []
    for idx, (start_dt, reason) in enumerate(merged_bps):
        end_dt = merged_bps[idx + 1][0] - timedelta(seconds=1) if idx + 1 < len(merged_bps) else last_dt
        win_obs = [
            o for o in admitted
            if (_obs_time_utc(o) is not None and start_dt <= _obs_time_utc(o) <= end_dt)
        ]
        if not win_obs:
            continue
        actual_start = _obs_time_utc(win_obs[0])
        actual_end = _obs_time_utc(win_obs[-1])
        windows.append({
            "season_id": f"season_{idx + 1:02d}_{actual_start.strftime('%Y%m')}",
            "start_dt": actual_start,
            "end_dt": actual_end,
            "boundary_reason": reason,
            "observations": win_obs,
        })
    return windows, seg_receipt_dict


def _safe_crop_context_mixture(
    *,
    declared_crop_code: Optional[str],
    declared_verified: bool,
    crop_authority: str,
    physical_regime: str,
    posterior_dict: Mapping[str, Any],
    base_soil_context: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Condition ASMAE crop parameters without ever leaking unverified legacy defaults."""
    is_confirmed_authority = crop_authority in CONFIRMED_CROP_AUTHORITIES and bool(declared_verified)

    if physical_regime == "PRE_PLANTING_FALLOW_OR_PREP":
        return {
            "crop": "fallow",
            "crop_type": "fallow",
            "crop_authority": crop_authority,
            "crop_identity_verified": False,
            "crop_coefficient": 0.30,
            "t_base": 6.0,
            "t_opt": 24.0,
            "t_max": 38.0,
            "max_root_depth_cm": 35.0,
            "physical_regime": physical_regime,
            "posterior_source": "confirmed_pre_planting_fallow_regime",
            "crop_group_posterior": dict(posterior_dict.get("crop_group_posterior") or {"unknown": 1.0}),
            "unknown_probability": float(posterior_dict.get("unknown_probability", 1.0) or 1.0),
            "crop_lineage_id": posterior_dict.get("lineage_id"),
        }

    # WM1-P2-11: Unknown pre-cycle land cover preserves EO mixture with explicit neutral uncertainty
    if physical_regime == "PRE_KNOWN_CYCLE_UNKNOWN":
        base_ctx = {
            "crop": "unknown",
            "crop_type": "unknown",
            "soil_type": (base_soil_context or {}).get("soil_type", "loam"),
            "max_root_depth_cm": 70.0,
        }
        conditioned = condition_crop_context(base_ctx, posterior_dict)
        conditioned["crop_authority"] = "UNKNOWN"
        conditioned["crop_identity_verified"] = False
        conditioned["physical_regime"] = physical_regime
        conditioned["posterior_source"] = "pre_known_cycle_unknown_eo_mixture"
        return conditioned

    if is_confirmed_authority and declared_crop_code:
        spec, canon, used_default = get_crop_with_provenance(declared_crop_code)
        base_ctx = {
            "crop": canon if not used_default else declared_crop_code,
            "crop_type": canon if not used_default else declared_crop_code,
            "kc_init": getattr(spec, "kc_init", None),
            "kc_mid": getattr(spec, "kc_mid", None),
            "kc_end": getattr(spec, "kc_end", None),
            "crop_coefficient": getattr(spec, "kc_mid", 0.75) or 0.75,
            "t_base": getattr(spec, "t_base", 8.0) or 8.0,
            "t_opt": getattr(spec, "t_opt", 25.0) or 25.0,
            "t_max": getattr(spec, "t_max", 38.0) or 38.0,
            "max_root_depth_cm": getattr(spec, "root_depth_max_cm", 110.0) or 110.0,
            "soil_type": (base_soil_context or {}).get("soil_type", "loam"),
        }
    elif declared_crop_code and crop_authority == "REGISTRY_DECLARED":
        spec, canon, used_default = get_crop_with_provenance(declared_crop_code)
        base_ctx = {
            "crop": "unknown",
            "crop_type": "unknown",
            "declared_registry_candidate": canon if not used_default else declared_crop_code,
            "soil_type": (base_soil_context or {}).get("soil_type", "loam"),
            "max_root_depth_cm": 75.0,
        }
    else:
        base_ctx = {
            "crop": "unknown",
            "crop_type": "unknown",
            "soil_type": (base_soil_context or {}).get("soil_type", "loam"),
            "max_root_depth_cm": 75.0,
        }

    conditioned = condition_crop_context(base_ctx, posterior_dict)
    if physical_regime == "EARLY_ESTABLISHMENT":
        conditioned["crop_coefficient"] = min(float(conditioned.get("crop_coefficient", 0.55) or 0.55), 0.58)
        conditioned["max_root_depth_cm"] = min(float(conditioned.get("max_root_depth_cm", 45.0) or 45.0), 45.0)
        conditioned["early_establishment_damping"] = True
    elif physical_regime == "POST_HARVEST_RESIDUE_OR_FALLOW":
        conditioned["crop_coefficient"] = 0.30
        conditioned["post_harvest_fallow"] = True

    conditioned["crop_identity_verified"] = bool(is_confirmed_authority)
    conditioned["crop_authority"] = crop_authority
    conditioned["physical_regime"] = physical_regime
    conditioned["posterior_source"] = (
        "confirmed_crop_cycle_with_layer2_conditioning"
        if is_confirmed_authority
        else (
            "registry_declared_cycle_with_layer2_mixture"
            if crop_authority == "REGISTRY_DECLARED"
            else "layer2_eo_crop_posterior_mixture_unverified"
        )
    )
    return conditioned


def reconstruct_chronological_crop_posteriors(
    *,
    plot_id: str,
    tenant_id: str,
    farm_id: Optional[str],
    scenes: Sequence[Mapping[str, Any]],
    domain_chronology: DomainChronology,
    plot_geometry: Optional[Mapping[str, Any]] = None,
    geometry_hash: str = "",
    scene_cache_dir: Optional[str] = None,
    operational_context: Optional[Mapping[str, Any]] = None,
    soil_context: Optional[Mapping[str, Any]] = None,
    knowledge_cutoff_K: Optional[datetime] = None,
    canonical_observations_override: Optional[Sequence[Dict[str, Any]]] = None,
    run_id: str = "historical_crop_fusion_v2",
) -> Dict[str, Any]:
    """Build versioned CropEvidenceLedgerV2 and compute causal seasonal P(C_t | O_{<=t}, K) series."""
    plot_namespace = {
        "tenant_id": tenant_id,
        "farm_id": farm_id or "default_farm",
        "plot_id": plot_id,
    }
    op_ctx = dict(operational_context or {})
    k_limit = _parse_iso_utc(knowledge_cutoff_K)

    if canonical_observations_override is not None:
        canonical_obs = [dict(o) for o in canonical_observations_override]
    else:
        canonical_obs = build_historical_crop_observations(
            scenes,
            plot_id=plot_id,
            tenant_id=tenant_id,
            farm_id=farm_id,
            plot_geometry=plot_geometry,
            geometry_hash=geometry_hash,
            scene_cache_dir=scene_cache_dir,
        )

    withheld_reprocessed_total = 0
    filtered_obs_for_windows: List[Dict[str, Any]] = []
    for o in canonical_obs:
        eligible, selected_ver, reason = _select_eligible_product_version_as_of(
            o, valid_time_T=k_limit, knowledge_cutoff_K=k_limit
        )
        if not eligible:
            if reason == "reprocessed_or_late_version_unavailable_at_k":
                withheld_reprocessed_total += 1
            continue
        filtered_obs_for_windows.append(_materialize_obs_for_version(o, selected_ver))

    windows, full_seg_receipt = _season_windows_from_observations(filtered_obs_for_windows, plot_namespace)
    timeline: List[Dict[str, Any]] = []
    previous_posterior: Optional[Dict[str, Any]] = None

    for idx, win in enumerate(windows):
        t_season_end = win["end_dt"]
        eff_k = k_limit if k_limit is not None else t_season_end
        domain_at_tk = domain_chronology.as_of(t_season_end, knowledge_cutoff_K=eff_k)

        win_obs: List[Dict[str, Any]] = []
        win_withheld_reprocessed = 0
        for o in win["observations"]:
            eligible, selected_ver, reason = _select_eligible_product_version_as_of(
                o, valid_time_T=t_season_end, knowledge_cutoff_K=eff_k
            )
            if not eligible:
                if reason == "reprocessed_or_late_version_unavailable_at_k":
                    win_withheld_reprocessed += 1
                continue
            win_obs.append(_materialize_obs_for_version(o, selected_ver))

        v2_obs = [
            o for o in win_obs
            if o.get("contract_version") in {"canonical_crop_observation_v2", "crop_observation_v2"}
        ]
        ledger_dict: Optional[Dict[str, Any]] = None
        if v2_obs:
            try:
                ledger = build_crop_evidence_ledger(v2_obs, plot_namespace=plot_namespace)
                ledger_dict = ledger.to_dict()
            except Exception:
                ledger_dict = None

        declared_verified = bool(domain_at_tk.get("crop_verified_as_of_k"))
        crop_authority_tk = str(domain_at_tk.get("crop_authority") or "UNKNOWN").upper()
        declared_crop_tk = domain_at_tk.get("verified_crop_code") or domain_at_tk.get("declared_crop_code")
        active_cycle = domain_at_tk.get("active_crop_cycle")
        physical_regime = str(domain_at_tk.get("physical_regime") or "UNVERIFIED_CROP_REGIME")

        # WM1-P1-02: NEVER elevate REGISTRY_DECLARED to FARMER_CONFIRMED
        crop_cfg: Dict[str, Any] = {}
        if declared_crop_tk and crop_authority_tk != "UNKNOWN":
            crop_cfg = {
                "crop": declared_crop_tk,
                "crop_type": declared_crop_tk,
                "authority": crop_authority_tk,
                "crop_authority": crop_authority_tk,
                "declared_crop_authority": crop_authority_tk,
                "declared_crop_at": domain_at_tk.get("crop_declared_at"),
                "declared_crop_source": domain_at_tk.get("crop_declared_source"),
                "crop_cycle_id": (active_cycle or {}).get("record_id"),
                "crop_cycle": active_cycle,
            }

        use_prev = (
            previous_posterior
            if (previous_posterior is not None and "harvest" not in str(win["boundary_reason"]).lower())
            else None
        )
        step_op = {
            **op_ctx,
            "tenant_id": tenant_id,
            "farm_id": farm_id or "default_farm",
        }
        if ledger_dict is not None:
            step_op["crop_evidence_ledger"] = ledger_dict
            step_op["crop_evidence_ledger_hash"] = ledger_dict.get("ledger_hash")

        posterior = infer_crop_posterior(
            plot_id=plot_id,
            run_id=f"{run_id}_{win['season_id']}",
            plot_timeseries=[],
            crop_config=crop_cfg,
            operational_context=step_op,
            archive_context={"previous_crop_posterior": use_prev} if use_prev else {},
        )
        conditioned_ctx = _safe_crop_context_mixture(
            declared_crop_code=declared_crop_tk,
            declared_verified=declared_verified,
            crop_authority=crop_authority_tk,
            physical_regime=physical_regime,
            posterior_dict=posterior,
            base_soil_context=soil_context,
        )
        group_post = dict(posterior.get("crop_group_posterior") or {})
        selected_versions = [
            o.get("selected_product_version") for o in win_obs if isinstance(o.get("selected_product_version"), Mapping)
        ]
        max_avail_at = max(
            (_parse_iso_utc(v.get("available_at")) for v in selected_versions if _parse_iso_utc(v.get("available_at"))),
            default=None,
        )
        timeline.append({
            "season_id": win["season_id"],
            "season_index": idx + 1,
            "start_time": win["start_dt"].isoformat(),
            "end_time": t_season_end.isoformat(),
            "evidence_end_time": t_season_end.isoformat(),
            "valid_as_of_T": t_season_end.isoformat(),
            "knowledge_cutoff_K": eff_k.isoformat(),
            "max_product_available_at": max_avail_at.isoformat() if max_avail_at else None,
            "withheld_reprocessed_after_k_count": win_withheld_reprocessed,
            "boundary_reason": win["boundary_reason"],
            "observation_count": len(win_obs),
            "admitted_v2_count": len(v2_obs),
            "crop_identity_verified_as_of_tk": declared_verified,
            "verified_crop_code_as_of_tk": domain_at_tk.get("verified_crop_code"),
            "declared_crop_code_as_of_tk": declared_crop_tk,
            "crop_declaration_authority": crop_authority_tk,
            "physical_regime": physical_regime,
            "fallow_support_source": domain_at_tk.get("fallow_support_source"),
            "withheld_future_crop_cycles_count": domain_at_tk.get("withheld_future_crop_cycles_count", 0),
            "authority": posterior.get("authority"),
            "top_group": posterior.get("top_group"),
            "top_group_probability": posterior.get("top_group_probability"),
            "unknown_probability": posterior.get("unknown_probability"),
            "posterior_entropy": _entropy(group_post),
            "crop_group_posterior": group_post,
            "species_ranking_top5": list(posterior.get("species_ranking") or [])[:5],
            "calibration_status": posterior.get("calibration_status"),
            "ml_production_eligible": bool(posterior.get("ml_production_eligible", False)),
            "ml_handoff_status": dict(posterior.get("ml_handoff_status") or {}),
            "species_probability_published": False,
            "crop_evidence_ledger_hash": posterior.get("crop_evidence_ledger_hash"),
            "crop_evidence_ledger_status": posterior.get("crop_evidence_ledger_status"),
            "crop_posterior_hash": posterior.get("content_hash"),
            "crop_lineage_id": posterior.get("lineage_id"),
            "asmae_mixture_conditioning": posterior.get("asmae_mixture_conditioning"),
            "conditioned_crop_context": conditioned_ctx,
            "raw_posterior": posterior,
        })
        previous_posterior = posterior

    compact_canon_obs = [
        {
            k: v
            for k, v in o.items()
            if k not in {"local_cache_refs", "raw_bands"}
        }
        for o in canonical_obs
    ]
    latest_entry = timeline[-1] if timeline else None
    return {
        "contract_version": "asmae_historical_crop_fusion_v2",
        "plot_id": plot_id,
        "tenant_id": tenant_id,
        "canonical_observation_count": len(canonical_obs),
        "eligible_at_k_observation_count": len(filtered_obs_for_windows),
        "withheld_reprocessed_after_k_count": withheld_reprocessed_total,
        "admitted_physical_count": sum(1 for o in filtered_obs_for_windows if o.get("quality_admitted") is True),
        "seasons_count": len(timeline),
        "full_segmentation_receipt": full_seg_receipt,
        "seasonal_timeline": timeline,
        "canonical_observations": compact_canon_obs,
        "latest_crop_posterior": latest_entry,
        "ml_production_eligible": False,
        "inference_mode": "versioned_lineage_group_mixture_with_bitemporal_crop_authority",
    }


def crop_context_as_of(
    crop_fusion_result: Optional[Mapping[str, Any]],
    *,
    valid_time_T: datetime,
    knowledge_cutoff_K: Optional[datetime] = None,
    domain_chronology: Optional[DomainChronology] = None,
    base_soil_context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Select causal conditioned crop context P(C_t | O_{<=t}, K) strictly without post-T evidence leakage."""
    t_dt = _parse_iso_utc(valid_time_T) or datetime.now(timezone.utc)
    k_dt = _parse_iso_utc(knowledge_cutoff_K) or t_dt
    timeline = list((crop_fusion_result or {}).get("seasonal_timeline") or [])

    if domain_chronology is not None:
        dom_tk = domain_chronology.as_of(t_dt, knowledge_cutoff_K=k_dt)
        verified_as_of_k = bool(dom_tk.get("crop_verified_as_of_k"))
        crop_authority = str(dom_tk.get("crop_authority") or "UNKNOWN").upper()
        declared_code = dom_tk.get("verified_crop_code") or dom_tk.get("declared_crop_code")
        physical_regime = str(dom_tk.get("physical_regime") or "UNVERIFIED_CROP_REGIME")
        declared_at = dom_tk.get("crop_declared_at")
        declared_src = dom_tk.get("crop_declared_source")
        active_cycle = dom_tk.get("active_crop_cycle")
    else:
        verified_as_of_k = False
        crop_authority = "UNKNOWN"
        declared_code = None
        physical_regime = "UNVERIFIED_CROP_REGIME"
        declared_at = None
        declared_src = None
        active_cycle = None

    # Only completed seasons whose evidence ENDED by valid_time_T and known by K can be reused directly!
    completed_before_t: Optional[Mapping[str, Any]] = None
    covering_completed: Optional[Mapping[str, Any]] = None
    in_progress_season_start: Optional[datetime] = None
    for item in timeline:
        s_start = _parse_iso_utc(item.get("start_time"))
        s_end = _parse_iso_utc(item.get("evidence_end_time") or item.get("end_time"))
        max_avail = _parse_iso_utc(item.get("max_product_available_at"))
        s_k = _parse_iso_utc(item.get("knowledge_cutoff_K"))
        if max_avail is not None and max_avail > k_dt:
            continue
        elif max_avail is None and s_k is not None and s_k > k_dt:
            continue
        if s_start is not None and s_start <= t_dt:
            if s_end is not None and s_end > t_dt:
                # Season spans past t_dt -> NEVER use its end-of-season posterior before s_end!
                in_progress_season_start = s_start
                break
            completed_before_t = item
            if s_end is None or t_dt <= s_end + timedelta(days=30):
                covering_completed = item

    posterior: Dict[str, Any] = {}
    selected: Optional[Mapping[str, Any]] = covering_completed
    raw_canon = (crop_fusion_result or {}).get("canonical_observations")
    if selected is None and isinstance(raw_canon, list) and raw_canon:
        season_win_start = in_progress_season_start or (
            _parse_iso_utc((completed_before_t or {}).get("end_time")) or datetime.min.replace(tzinfo=timezone.utc)
        )
        prefix_obs: List[Dict[str, Any]] = []
        obs_sig_parts: List[str] = []
        for o in raw_canon:
            obs_t = _obs_time_utc(o)
            if obs_t is None or obs_t > t_dt:
                continue
            if obs_t < season_win_start:
                continue
            elig, sel_ver, _ = _select_eligible_product_version_as_of(
                o, valid_time_T=t_dt, knowledge_cutoff_K=k_dt
            )
            if elig:
                mat = _materialize_obs_for_version(o, sel_ver)
                prefix_obs.append(mat)
                obs_sig_parts.append(f"{o.get('observation_id') or obs_t.isoformat()}:{(sel_ver or {}).get('processing_baseline')}")

        if prefix_obs:
            # Memoize pure causal prefix posterior on the crop_fusion_result dict when mutable
            cache_map = (
                crop_fusion_result.setdefault("_causal_prefix_cache", {})
                if isinstance(crop_fusion_result, dict)
                else {}
            )
            cache_key = (
                tuple(obs_sig_parts),
                declared_code,
                verified_as_of_k,
                crop_authority,
                physical_regime,
            )
            cached_post = cache_map.get(cache_key) if isinstance(cache_map, dict) else None
            if isinstance(cached_post, dict):
                posterior = dict(cached_post)
            else:
                plot_id = str((crop_fusion_result or {}).get("plot_id") or "plot")
                tenant_id = str((crop_fusion_result or {}).get("tenant_id") or "default_tenant")
                plot_ns = {"tenant_id": tenant_id, "farm_id": "default_farm", "plot_id": plot_id}
                v2_obs = [
                    o for o in prefix_obs
                    if o.get("contract_version") in {"canonical_crop_observation_v2", "crop_observation_v2"}
                ]
                step_op: Dict[str, Any] = {
                    "tenant_id": tenant_id,
                    "farm_id": "default_farm",
                    "soil_type": (base_soil_context or {}).get("soil_type", "loam"),
                }
                if v2_obs:
                    try:
                        led = build_crop_evidence_ledger(v2_obs, plot_namespace=plot_ns)
                        ld = led.to_dict()
                        step_op["crop_evidence_ledger"] = ld
                        step_op["crop_evidence_ledger_hash"] = ld.get("ledger_hash")
                    except Exception:
                        pass
                crop_cfg: Dict[str, Any] = {}
                if declared_code and crop_authority != "UNKNOWN":
                    crop_cfg = {
                        "crop": declared_code,
                        "crop_type": declared_code,
                        "authority": crop_authority,
                        "crop_authority": crop_authority,
                        "declared_crop_authority": crop_authority,
                        "declared_crop_at": declared_at,
                        "declared_crop_source": declared_src,
                        "crop_cycle_id": (active_cycle or {}).get("record_id"),
                        "crop_cycle": active_cycle,
                    }
                prev_comp_post = dict((completed_before_t or {}).get("raw_posterior") or {}) or None
                posterior = infer_crop_posterior(
                    plot_id=plot_id,
                    run_id=f"prefix_{t_dt.strftime('%Y%m%d')}",
                    plot_timeseries=[],
                    crop_config=crop_cfg,
                    operational_context=step_op,
                    archive_context={"previous_crop_posterior": prev_comp_post} if prev_comp_post else {},
                )
                if isinstance(cache_map, dict):
                    if len(cache_map) > 256:
                        cache_map.clear()
                    cache_map[cache_key] = posterior

    if not posterior and selected is not None:
        posterior = dict(selected.get("raw_posterior") or {})
        if not posterior:
            posterior = {
                "authority": selected.get("authority", "MODEL_GROUP_POSTERIOR"),
                "crop_group_posterior": selected.get("crop_group_posterior", {"unknown": 1.0}),
                "unknown_probability": selected.get("unknown_probability", 1.0),
                "asmae_mixture_conditioning": selected.get("asmae_mixture_conditioning", {}),
                "content_hash": selected.get("crop_posterior_hash"),
                "lineage_id": selected.get("crop_lineage_id"),
            }

    return _safe_crop_context_mixture(
        declared_crop_code=declared_code,
        declared_verified=verified_as_of_k,
        crop_authority=crop_authority,
        physical_regime=physical_regime,
        posterior_dict=posterior or {"authority": "UNKNOWN", "crop_group_posterior": {"unknown": 1.0}, "unknown_probability": 1.0},
        base_soil_context=base_soil_context,
    )


def apply_post_asmae_crop_refinement(
    crop_fusion_result: Dict[str, Any],
    trajectory: Sequence[Mapping[str, Any]],
    *,
    run_id: str = "hist_post_asmae_v2",
) -> Dict[str, Any]:
    """Apply Layer 2 refine_crop_posterior() per season using causally aligned ASMAE trajectory means."""
    timeline = crop_fusion_result.get("seasonal_timeline") or []
    if not timeline or not trajectory:
        return crop_fusion_result

    refined_count = 0
    for item in timeline:
        pre_post = item.get("raw_posterior")
        if not isinstance(pre_post, dict):
            continue
        s_start = _parse_iso_utc(item.get("start_time"))
        s_end = _parse_iso_utc(item.get("end_time"))
        if s_start is None or s_end is None:
            continue
        win_steps = [
            st for st in trajectory
            if (_parse_iso_utc(st.get("acquisition_time")) or datetime.min.replace(tzinfo=timezone.utc)) >= s_start
            and (_parse_iso_utc(st.get("acquisition_time")) or datetime.max.replace(tzinfo=timezone.utc)) <= s_end
        ]
        if not win_steps:
            item["refinement_status"] = "skipped_no_asmae_steps_in_window"
            continue
        last_means = dict(win_steps[-1].get("posterior_state_means") or {})
        plot_state = {
            "posterior": {
                "structure": {"mean": last_means.get("structure")},
                "phenology_progress": {"mean": last_means.get("phenology_progress")},
                "vigor": {"mean": last_means.get("vigor")},
            }
        }
        refined = refine_crop_posterior(
            pre_post,
            plot_state,
            parent_run_id=f"{run_id}_{item['season_id']}",
            material_change_threshold=0.10,
        )
        item["post_asmae_crop_group_posterior"] = dict(refined.get("crop_group_posterior") or {})
        item["post_asmae_top_group"] = refined.get("top_group")
        item["post_asmae_l1_shift"] = refined.get("prior_to_posterior_l1_shift", refined.get("total_variation_distance"))
        item["refinement_status"] = str(refined.get("refinement_status", "completed"))
        refined_count += 1

    crop_fusion_result["post_asmae_refined_seasons"] = refined_count
    return crop_fusion_result


def _canonical_broad_group_probs(raw_dist: Mapping[str, Any]) -> Dict[str, float]:
    probs = {g: 0.0 for g in _BROAD_GROUPS}
    for k, v in (raw_dist or {}).items():
        if isinstance(v, bool) or v is None:
            continue
        try:
            f = max(0.0, float(v))
        except (TypeError, ValueError):
            continue
        g = _broad_crop_group(str(k))
        probs[g] = probs.get(g, 0.0) + f
    tot = sum(probs.values())
    if tot <= 0.0:
        probs["unknown"] = 1.0
        return probs
    return {k: val / tot for k, val in probs.items()}


def _bootstrap_ci(values: Sequence[float], seed: int = 20261127, n_boot: int = 250) -> Optional[List[float]]:
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    lo = means[max(0, int(0.025 * (n_boot - 1)))]
    hi = means[min(n_boot - 1, int(0.975 * (n_boot - 1)))]
    return [round(lo, 4), round(hi, 4)]


def evaluate_crop_detection_benchmark(
    cohort_items: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Evaluate Layer 2 crop inference with full multiclass Brier, log loss, ECE, coverage & unknown-set recall."""
    evaluated_seasons: List[Dict[str, Any]] = []
    unknown_non_crop_records: List[Dict[str, Any]] = []
    multiclass_brier_scores: List[float] = []
    log_loss_scores: List[float] = []
    ece_points: List[Tuple[float, float]] = []
    group_hits = 0
    accepted_hits = 0
    accepted_count = 0
    species_top1_hits = 0
    species_top5_hits = 0
    known_crop_abstained = 0
    synthetic_excluded_count = 0

    for item in cohort_items:
        plot_id = str(item.get("plot_id") or "")
        dom = item.get("domain_identity") or {}
        if dom.get("synthetic_label_rejected"):
            synthetic_excluded_count += 1
        chron = item.get("domain_chronology")
        fusion = item.get("crop_fusion") or {}
        if not isinstance(chron, DomainChronology):
            continue

        for season in fusion.get("seasonal_timeline") or []:
            s_end = _parse_iso_utc(season.get("end_time"))
            if s_end is None:
                continue

            matching_cycle = None
            for rec in chron.crop_intervals:
                if rec.synthetic_rejected or not rec.registry_recognized:
                    continue
                vf = _parse_iso_utc(rec.valid_from)
                vt = _parse_iso_utc(rec.valid_to)
                if vf is not None and s_end < vf:
                    continue
                if vt is not None and rec.architecture_class not in {"perennial", "tropical_tree"} and s_end > vt + timedelta(days=30):
                    continue
                matching_cycle = rec
                break

            raw_post = season.get("raw_posterior") or {}
            eo_group_dist = dict(raw_post.get("model_context_group_posterior") or season.get("crop_group_posterior") or {})
            canon_probs = _canonical_broad_group_probs(eo_group_dist)
            eo_non_unk = {k: v for k, v in canon_probs.items() if k != "unknown" and v > 0.0}
            pred_top_group = max(eo_non_unk.items(), key=lambda kv: kv[1])[0] if eo_non_unk else "unknown"
            unk_prob = float(canon_probs.get("unknown", 1.0))
            is_deferred = pred_top_group == "unknown" or unk_prob >= 0.55

            if matching_cycle is None:
                # Separate true non-crop / fallow-verified evaluation vs unverified unknown periods
                dom_tk = chron.as_of(s_end, knowledge_cutoff_K=s_end)
                if dom_tk.get("physical_regime") in {"PRE_PLANTING_FALLOW_OR_PREP", "POST_HARVEST_RESIDUE_OR_FALLOW"}:
                    unknown_non_crop_records.append({
                        "plot_id": plot_id,
                        "season_id": season.get("season_id"),
                        "regime": dom_tk.get("physical_regime"),
                        "deferred_or_unknown": is_deferred,
                        "unknown_probability": round(unk_prob, 4),
                    })
                continue

            true_code = matching_cycle.crop_code
            true_group = _broad_crop_group(true_code)
            label_authority = matching_cycle.authority

            if is_deferred:
                known_crop_abstained += 1
            else:
                accepted_count += 1
            hit_group = (not is_deferred) and (pred_top_group == true_group)
            if hit_group:
                group_hits += 1
                accepted_hits += 1

            species_list = [str(s.get("code") or "") for s in (season.get("species_ranking_top5") or [])]
            top1_sp = species_list[0] if species_list else None
            hit_sp1 = top1_sp == true_code
            hit_sp5 = true_code in species_list[:5]
            if hit_sp1:
                species_top1_hits += 1
            if hit_sp5:
                species_top5_hits += 1

            # Proper multiclass Brier over full broad-group simplex + Log Loss + ECE
            mc_brier = sum((canon_probs[g] - (1.0 if g == true_group else 0.0)) ** 2 for g in _BROAD_GROUPS)
            nll = -math.log(max(1e-6, canon_probs.get(true_group, 0.0)))
            max_conf_group = max(canon_probs.items(), key=lambda kv: kv[1])[0]
            max_conf_val = float(canon_probs[max_conf_group])
            multiclass_brier_scores.append(mc_brier)
            log_loss_scores.append(nll)
            ece_points.append((max_conf_val, 1.0 if max_conf_group == true_group else 0.0))

            evaluated_seasons.append({
                "plot_id": plot_id,
                "season_id": season.get("season_id"),
                "true_crop_code": true_code,
                "true_crop_group": true_group,
                "label_authority": label_authority,
                "label_confirmed": bool(matching_cycle.confirmed),
                "eo_predicted_group": pred_top_group,
                "eo_unknown_probability": round(unk_prob, 4),
                "deferred_unknown": is_deferred,
                "group_correct": hit_group,
                "species_top1": top1_sp,
                "species_top1_correct": hit_sp1,
                "species_top5_correct": hit_sp5,
                "multiclass_brier": round(mc_brier, 4),
                "multiclass_log_loss": round(nll, 4),
            })

    n = len(evaluated_seasons)
    # 5-bin Expected Calibration Error
    ece = None
    if ece_points:
        bins = [(i / 5.0, (i + 1) / 5.0) for i in range(5)]
        ece_acc = 0.0
        for lo, hi in bins:
            pts = [pt for pt in ece_points if (lo <= pt[0] < hi) or (hi == 1.0 and pt[0] == 1.0)]
            if pts:
                avg_conf = sum(p[0] for p in pts) / len(pts)
                avg_acc = sum(p[1] for p in pts) / len(pts)
                ece_acc += (len(pts) / len(ece_points)) * abs(avg_conf - avg_acc)
        ece = round(ece_acc, 4)

    n_unk = len(unknown_non_crop_records)
    unk_recall = (
        round(sum(1 for u in unknown_non_crop_records if u["deferred_or_unknown"]) / n_unk, 4)
        if n_unk > 0
        else None
    )

    confirmed_only_count = sum(1 for r in evaluated_seasons if r["label_confirmed"])
    acc_values = [1.0 if r["group_correct"] else 0.0 for r in evaluated_seasons]

    acc_among_accepted = round(accepted_hits / accepted_count, 4) if accepted_count else None
    return {
        "evaluated_verified_seasons": n,
        "confirmed_label_seasons_count": confirmed_only_count,
        "registry_declaration_seasons_count": n - confirmed_only_count,
        "synthetic_labels_excluded_count": synthetic_excluded_count,
        "crop_group_accuracy_overall": round(group_hits / n, 4) if n else None,
        "crop_group_accuracy": round(group_hits / n, 4) if n else None,
        "crop_group_accuracy_among_accepted": acc_among_accepted,
        "conditional_accuracy_when_accepted": acc_among_accepted,
        "accepted_coverage": round(accepted_count / n, 4) if n else None,
        "known_crop_abstention_rate": round(known_crop_abstained / n, 4) if n else None,
        "species_top1_ranking_accuracy": round(species_top1_hits / n, 4) if n else None,
        "species_top5_ranking_accuracy": round(species_top5_hits / n, 4) if n else None,
        "multiclass_brier_score": round(sum(multiclass_brier_scores) / n, 4) if n else None,
        "multiclass_log_loss": round(sum(log_loss_scores) / n, 4) if n else None,
        "group_ece": ece,
        "expected_calibration_error_5bin": ece,
        "unknown_non_crop_eval_count": n_unk,
        "unknown_class_recall": unk_recall,
        "true_non_crop_unknown_recall": unk_recall,
        "unknown_set_note": (
            "Evaluated against independent fallow/post-harvest intervals."
            if n_unk > 0
            else "no_independently_confirmed_non_crop_set"
        ),
        "confidence_intervals_95pct": {
            "crop_group_accuracy_overall_ci": _bootstrap_ci(acc_values),
            "multiclass_brier_score_ci": _bootstrap_ci(multiclass_brier_scores),
        },
        "calibration_status": "uncalibrated_reference_science_ranking_only",
        "ml_production_eligible": False,
        "season_records": evaluated_seasons[:20],
    }


__all__ = [
    "_broad_crop_group",
    "adapt_scenes_to_source_packages",
    "apply_post_asmae_crop_refinement",
    "build_historical_crop_observations",
    "crop_context_as_of",
    "evaluate_crop_detection_benchmark",
    "reconstruct_chronological_crop_posteriors",
]
