"""Crop Identity - ASMAE Historical Fusion reusing Layer 2 CropIdentification & CropPosterior.

Computes chronological bitemporal seasonal crop posteriors P(C_t | O_{<=t}, K),
conditions ASMAE & L2-8 crop parameter mixtures causally without future CropCycle leakage,
applies bounded post-ASMAE refinement, and benchmarks crop detection on verified non-synthetic labels.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from services.agribrain.crop_database import get_crop_with_provenance, resolve_crop_code
except ImportError:
    from crop_database import get_crop_with_provenance, resolve_crop_code
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


def _obs_time_utc(obs: Mapping[str, Any]) -> Optional[datetime]:
    return (
        _parse_iso_utc(obs.get("sensing_timestamp"))
        or _parse_iso_utc(obs.get("timestamp"))
        or _parse_iso_utc(obs.get("acquisition_datetime"))
        or _parse_iso_utc(obs.get("date"))
    )


def _obs_knowledge_utc(obs: Mapping[str, Any]) -> Optional[datetime]:
    explicit = _parse_iso_utc(obs.get("knowledge_time")) or _parse_iso_utc(obs.get("available_at"))
    if explicit is not None:
        return explicit
    lineage = obs.get("processing_lineage") or []
    proc_ts = None
    if isinstance(lineage, list) and lineage and isinstance(lineage[0], Mapping):
        proc_ts = _parse_iso_utc(lineage[0].get("processing_timestamp"))
    acq_ts = _obs_time_utc(obs)
    if acq_ts is not None and proc_ts is not None:
        # Operational dissemination lag is within days; multi-year Collection-2 catalog reprocessing
        # (e.g., S2 N0500 reprocessed in 2023-2024 for 2015-2022 acquisitions) must not withhold historical scenes.
        if (proc_ts - acq_ts) <= timedelta(days=30):
            return max(acq_ts, proc_ts)
        return acq_ts
    return proc_ts or acq_ts


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
        "cucurbit_veg", "allium_veg", "root_tuber", "horticulture",
    }:
        return "vegetable"
    if low in {
        "chickpea", "lentil", "fava_bean", "soybean", "legume",
        "cool_legume", "warm_legume",
    }:
        return "legume"
    if low in {"alfalfa", "forage"}:
        return "forage"
    return low or "unknown"


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

        # Fallback: preserve existing scalar/packet metadata cleanly without fabricating physical binding
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
    return build_canonical_crop_observations(
        source_packages,
        plot_geometry=plot_geometry,
        geometry_hash=geometry_hash,
        plot_geometry_crs="EPSG:4326",
        plot_namespace=namespace,
        weather_records=weather_records,
    )


def _season_windows_from_observations(
    canonical_obs: Sequence[Dict[str, Any]],
    plot_namespace: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Partition multi-year archive using CropCycleSegmentationReceiptV1 plus annual windowing for perennials."""
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

    # Combine detected optical/gap breakpoints with annual agricultural years (Oct 1 hydrologic boundaries)
    # whenever a single segment spans > 400 days so multi-year perennial archives still track seasonal P(C_t)
    breakpoints: List[Tuple[datetime, str]] = [(first_dt, "archive_start")]
    breakpoints.extend(optical_breaks)

    # Check long unbroken spans (> 400 days)
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

    # Deduplicate breakpoints within 35 days
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
    physical_regime: str,
    posterior_dict: Mapping[str, Any],
    base_soil_context: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Condition downstream crop parameters from verified CropCycle or uncertainty-aware EO posterior."""
    base_ctx: Dict[str, Any] = {
        "soil_type": (base_soil_context or {}).get("soil_type", "loam"),
        "crop_identity_verified": bool(declared_verified),
        "physical_regime": physical_regime,
    }
    if declared_verified and declared_crop_code and declared_crop_code != "unknown":
        base_ctx["crop"] = declared_crop_code
        base_ctx["crop_type"] = declared_crop_code
        base_ctx["authority"] = "FARMER_CONFIRMED"
        base_ctx["crop_authority"] = "FARMER_CONFIRMED"
        try:
            spec, canon, used_default = get_crop_with_provenance(declared_crop_code)
            if not used_default:
                base_ctx["crop_spec_code"] = canon
                base_ctx["crop_architecture"] = spec.architecture
                base_ctx["crop_coefficient"] = float(spec.kc_mid)
                base_ctx["t_base"] = float(spec.gdd_base_temp)
                base_ctx["t_opt"] = float(0.5 * (spec.optimal_temp_min + spec.optimal_temp_max))
                base_ctx["max_root_depth_cm"] = float(spec.max_root_depth_cm)
                base_ctx["water_stress_sensitivity"] = dict(spec.water_stress_sensitivity)
                base_ctx["harvest_index"] = float(spec.harvest_index)
        except Exception:
            pass
    elif physical_regime == "PRE_PLANTING_FALLOW_OR_PREP":
        base_ctx["crop"] = "fallow"
        base_ctx["crop_type"] = "fallow"
        base_ctx["crop_coefficient"] = 0.25
        base_ctx["t_base"] = 5.0
        base_ctx["t_opt"] = 24.0
        base_ctx["authority"] = "UNKNOWN"
    else:
        # Never inject a silent fallback species name when CropCycle is missing/unverified as of (T, K)
        base_ctx["crop"] = "unknown"
        base_ctx["crop_type"] = "unknown"
        base_ctx["authority"] = str(posterior_dict.get("authority") or "MODEL_GROUP_POSTERIOR")

    conditioned = condition_crop_context(base_ctx, posterior_dict)
    if physical_regime == "EARLY_ESTABLISHMENT":
        # Young newly planted seedlings/saplings have shallow effective canopy/root uptake
        conditioned["crop_coefficient"] = min(float(conditioned.get("crop_coefficient", 0.55) or 0.55), 0.58)
        conditioned["max_root_depth_cm"] = min(float(conditioned.get("max_root_depth_cm", 45.0) or 45.0), 45.0)
        conditioned["early_establishment_damping"] = True
    elif physical_regime == "POST_HARVEST_RESIDUE_OR_FALLOW":
        conditioned["crop_coefficient"] = 0.30
        conditioned["post_harvest_fallow"] = True

    conditioned["crop_identity_verified"] = bool(declared_verified)
    conditioned["physical_regime"] = physical_regime
    conditioned["posterior_source"] = (
        "verified_crop_cycle_with_layer2_conditioning"
        if declared_verified
        else "layer2_eo_crop_posterior_mixture_unverified"
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
    run_id: str = "historical_crop_fusion_v1",
) -> Dict[str, Any]:
    """Build verified CropEvidenceLedgerV2 and compute causal seasonal P(C_t | O_{<=t}, K) series."""
    plot_namespace = {
        "tenant_id": tenant_id,
        "farm_id": farm_id or "default_farm",
        "plot_id": plot_id,
    }
    op_ctx = dict(operational_context or {})
    k_limit = _parse_iso_utc(knowledge_cutoff_K)

    canonical_obs = build_historical_crop_observations(
        scenes,
        plot_id=plot_id,
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_geometry=plot_geometry,
        geometry_hash=geometry_hash,
        scene_cache_dir=scene_cache_dir,
    )
    if k_limit is not None:
        canonical_obs = [
            o for o in canonical_obs
            if (_obs_time_utc(o) is None or _obs_time_utc(o) <= k_limit)
            and (_obs_knowledge_utc(o) is None or _obs_knowledge_utc(o) <= k_limit)
        ]

    windows, full_seg_receipt = _season_windows_from_observations(canonical_obs, plot_namespace)
    timeline: List[Dict[str, Any]] = []
    previous_posterior: Optional[Dict[str, Any]] = None

    for idx, win in enumerate(windows):
        t_season_end = win["end_dt"]
        eff_k = min(t_season_end, k_limit) if k_limit is not None else t_season_end
        domain_at_tk = domain_chronology.as_of(t_season_end, knowledge_cutoff_K=eff_k)
        win_obs = [
            o for o in win["observations"]
            if (_obs_time_utc(o) or t_season_end) <= t_season_end
            and (_obs_knowledge_utc(o) or t_season_end) <= eff_k
        ]
        # Only feed CanonicalCropObservationV2 records into strict Layer 2 CropEvidenceLedgerV2
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
        verified_crop = domain_at_tk.get("verified_crop_code")
        active_cycle = domain_at_tk.get("active_crop_cycle")
        physical_regime = str(domain_at_tk.get("physical_regime") or "UNVERIFIED_CROP_REGIME")

        crop_cfg: Dict[str, Any] = {}
        if declared_verified and verified_crop:
            crop_cfg = {
                "crop": verified_crop,
                "crop_type": verified_crop,
                "authority": "FARMER_CONFIRMED",
                "crop_authority": "FARMER_CONFIRMED",
                "crop_cycle_id": (active_cycle or {}).get("record_id"),
                "crop_cycle": active_cycle,
            }

        # Reset temporal prior across detected optical harvest breaks to prevent stale rotation persistence
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
            declared_crop_code=verified_crop,
            declared_verified=declared_verified,
            physical_regime=physical_regime,
            posterior_dict=posterior,
            base_soil_context=soil_context,
        )
        group_post = dict(posterior.get("crop_group_posterior") or {})
        timeline.append({
            "season_id": win["season_id"],
            "season_index": idx + 1,
            "start_time": win["start_dt"].isoformat(),
            "end_time": t_season_end.isoformat(),
            "valid_as_of_T": t_season_end.isoformat(),
            "knowledge_cutoff_K": eff_k.isoformat(),
            "boundary_reason": win["boundary_reason"],
            "observation_count": len(win_obs),
            "admitted_v2_count": len(v2_obs),
            "crop_identity_verified_as_of_tk": declared_verified,
            "verified_crop_code_as_of_tk": verified_crop,
            "physical_regime": physical_regime,
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

    latest_entry = timeline[-1] if timeline else None
    return {
        "contract_version": "asmae_historical_crop_fusion_v1",
        "plot_id": plot_id,
        "tenant_id": tenant_id,
        "canonical_observation_count": len(canonical_obs),
        "admitted_physical_count": sum(1 for o in canonical_obs if o.get("quality_admitted") is True),
        "seasons_count": len(timeline),
        "full_segmentation_receipt": full_seg_receipt,
        "seasonal_timeline": timeline,
        "latest_crop_posterior": latest_entry,
        "ml_production_eligible": False,
        "inference_mode": "reference_science_group_mixture_with_bitemporal_crop_cycles",
    }


def crop_context_as_of(
    crop_fusion_result: Optional[Mapping[str, Any]],
    *,
    valid_time_T: datetime,
    knowledge_cutoff_K: Optional[datetime] = None,
    domain_chronology: Optional[DomainChronology] = None,
    base_soil_context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Select causal conditioned crop context P(C_t | O_{<=t}, K) valid at T and known at K."""
    t_dt = _parse_iso_utc(valid_time_T) or datetime.now(timezone.utc)
    k_dt = _parse_iso_utc(knowledge_cutoff_K) or t_dt
    timeline = list((crop_fusion_result or {}).get("seasonal_timeline") or [])

    selected: Optional[Mapping[str, Any]] = None
    for item in timeline:
        s_start = _parse_iso_utc(item.get("start_time"))
        s_end = _parse_iso_utc(item.get("end_time"))
        s_k = _parse_iso_utc(item.get("knowledge_cutoff_K"))
        if s_k is not None and s_k > k_dt:
            continue
        if s_start is not None and s_start <= t_dt and (s_end is None or t_dt <= s_end + timedelta(days=45)):
            selected = item

    if domain_chronology is not None:
        dom_tk = domain_chronology.as_of(t_dt, knowledge_cutoff_K=k_dt)
        verified_as_of_k = bool(dom_tk.get("crop_verified_as_of_k"))
        verified_code = dom_tk.get("verified_crop_code")
        physical_regime = str(dom_tk.get("physical_regime") or "UNVERIFIED_CROP_REGIME")
    else:
        verified_as_of_k = False
        verified_code = None
        physical_regime = "UNVERIFIED_CROP_REGIME"

    posterior = dict((selected or {}).get("raw_posterior") or {})
    if not posterior and selected is not None:
        posterior = {
            "authority": selected.get("authority", "MODEL_GROUP_POSTERIOR"),
            "crop_group_posterior": selected.get("crop_group_posterior", {"unknown": 1.0}),
            "unknown_probability": selected.get("unknown_probability", 1.0),
            "asmae_mixture_conditioning": selected.get("asmae_mixture_conditioning", {}),
            "content_hash": selected.get("crop_posterior_hash"),
            "lineage_id": selected.get("crop_lineage_id"),
        }
    return _safe_crop_context_mixture(
        declared_crop_code=verified_code,
        declared_verified=verified_as_of_k,
        physical_regime=physical_regime,
        posterior_dict=posterior or {"authority": "UNKNOWN", "crop_group_posterior": {"unknown": 1.0}, "unknown_probability": 1.0},
        base_soil_context=base_soil_context,
    )


def apply_post_asmae_crop_refinement(
    crop_fusion_result: Dict[str, Any],
    trajectory: Sequence[Mapping[str, Any]],
    *,
    run_id: str = "historical_asmae_refinement",
) -> Dict[str, Any]:
    """Run Layer 2's bounded post-ASMAE crop posterior refinement on each season with matching trajectory."""
    timeline = list(crop_fusion_result.get("seasonal_timeline") or [])
    if not timeline or not trajectory:
        return crop_fusion_result

    refined_count = 0
    for item in timeline:
        s_start = _parse_iso_utc(item.get("start_time"))
        s_end = _parse_iso_utc(item.get("end_time"))
        pre_post = item.get("raw_posterior")
        if not isinstance(pre_post, Mapping) or s_start is None or s_end is None:
            item["refinement_status"] = "skipped_missing_posterior"
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


def evaluate_crop_detection_benchmark(
    cohort_items: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Evaluate Layer 2 crop inference against real verified non-synthetic CropCycle labels."""
    evaluated_seasons: List[Dict[str, Any]] = []
    brier_scores: List[float] = []
    group_hits = 0
    species_top1_hits = 0
    species_top5_hits = 0
    unknown_deferred = 0
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
            # Evaluate EO-only signal against true confirmed CropCycle covering that window
            matching_cycle = None
            for rec in chron.crop_intervals:
                if not rec.verified:
                    continue
                vf = _parse_iso_utc(rec.valid_from)
                vt = _parse_iso_utc(rec.valid_to)
                if vf is not None and s_end < vf:
                    continue
                if vt is not None and rec.architecture_class not in {"perennial", "tropical_tree"} and s_end > vt + timedelta(days=30):
                    continue
                matching_cycle = rec
                break
            if matching_cycle is None:
                continue

            true_code = matching_cycle.crop_code
            true_group = _broad_crop_group(true_code)
            raw_post = season.get("raw_posterior") or {}
            # Prefer declaration-free model_context_group_posterior to avoid testing circular declaration pass-through!
            eo_group_dist = dict(raw_post.get("model_context_group_posterior") or season.get("crop_group_posterior") or {})
            eo_non_unk = {k: float(v) for k, v in eo_group_dist.items() if k != "unknown"}
            pred_top_group = max(eo_non_unk.items(), key=lambda kv: kv[1])[0] if eo_non_unk else "unknown"
            pred_group_broad = _broad_crop_group(pred_top_group)
            unk_prob = float(eo_group_dist.get("unknown", 1.0) or 0.0)
            is_deferred = pred_top_group == "unknown" or unk_prob >= 0.55
            if is_deferred:
                unknown_deferred += 1
            hit_group = (not is_deferred) and (pred_group_broad == true_group)
            if hit_group:
                group_hits += 1

            species_list = [str(s.get("code") or "") for s in (season.get("species_ranking_top5") or [])]
            top1_sp = species_list[0] if species_list else None
            hit_sp1 = top1_sp == true_code
            hit_sp5 = true_code in species_list[:5]
            if hit_sp1:
                species_top1_hits += 1
            if hit_sp5:
                species_top5_hits += 1

            p_true_group = float(sum(float(v) for k, v in eo_non_unk.items() if _broad_crop_group(k) == true_group))
            brier = (p_true_group - 1.0) ** 2
            brier_scores.append(brier)
            evaluated_seasons.append({
                "plot_id": plot_id,
                "season_id": season.get("season_id"),
                "true_crop_code": true_code,
                "true_crop_group": true_group,
                "eo_predicted_group": pred_top_group,
                "eo_unknown_probability": round(unk_prob, 4),
                "deferred_unknown": is_deferred,
                "group_correct": hit_group,
                "species_top1": top1_sp,
                "species_top1_correct": hit_sp1,
                "species_top5_correct": hit_sp5,
                "group_brier": round(brier, 4),
            })

    n = len(evaluated_seasons)
    return {
        "evaluated_verified_seasons": n,
        "synthetic_labels_excluded_count": synthetic_excluded_count,
        "crop_group_accuracy": round(group_hits / n, 4) if n else None,
        "species_top1_ranking_accuracy": round(species_top1_hits / n, 4) if n else None,
        "species_top5_ranking_accuracy": round(species_top5_hits / n, 4) if n else None,
        "unknown_class_deferral_rate": round(unknown_deferred / n, 4) if n else None,
        "group_brier_score": round(sum(brier_scores) / n, 4) if n else None,
        "calibration_status": "uncalibrated_reference_science_ranking_only",
        "ml_production_eligible": False,
        "season_records": evaluated_seasons[:20],
    }


__all__ = [
    "adapt_scenes_to_source_packages",
    "apply_post_asmae_crop_refinement",
    "build_historical_crop_observations",
    "crop_context_as_of",
    "evaluate_crop_detection_benchmark",
    "reconstruct_chronological_crop_posteriors",
]
