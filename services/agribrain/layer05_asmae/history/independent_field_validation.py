"""Independent Physical & Field Evidence Validation for ASMAE Historical Intelligence.

Evaluates withheld physical domain evidence (SoilAnalysis lab records, IoT Soil
Moisture/EC/Temp SensorReadings, MESIA multi-strata radio bridges, CropObservation
scouting notes, and CropTask management records) against ASMAE's independent
satellite + ERA5 state reconstructions WITHOUT feeding validation targets back
into the assimilation filter or tuning model parameters on evaluation plots.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from services.agribrain.layer05_asmae.history.historical_retrovalidation import _parse_dt
from services.agribrain.mesia.assimilation.spatial_lattice import LatticeStrata
from services.agribrain.mesia.contracts.behaviour import BehaviourLikelihood
from services.agribrain.mesia.integration_layer3 import MesiaLayer3WaterBridge

# Standard USDA soil texture hydrology priors (van Genuchten / FAO-56 class means)
_TEXTURE_HYDROLOGY: Dict[str, Dict[str, float]] = {
    "SAND": {
        "field_capacity": 0.16,
        "wilting_point": 0.06,
        "saturation": 0.43,
        "drainage_fraction": 0.72,
        "runoff_fraction": 0.05,
        "rooting_depth_m": 0.50,
    },
    "SANDY": {
        "field_capacity": 0.21,
        "wilting_point": 0.08,
        "saturation": 0.44,
        "drainage_fraction": 0.65,
        "runoff_fraction": 0.08,
        "rooting_depth_m": 0.55,
    },
    "SANDY_LOAM": {
        "field_capacity": 0.23,
        "wilting_point": 0.10,
        "saturation": 0.45,
        "drainage_fraction": 0.60,
        "runoff_fraction": 0.10,
        "rooting_depth_m": 0.60,
    },
    "LOAM": {
        "field_capacity": 0.29,
        "wilting_point": 0.13,
        "saturation": 0.47,
        "drainage_fraction": 0.48,
        "runoff_fraction": 0.12,
        "rooting_depth_m": 0.70,
    },
    "CLAY_LOAM": {
        "field_capacity": 0.36,
        "wilting_point": 0.19,
        "saturation": 0.49,
        "drainage_fraction": 0.35,
        "runoff_fraction": 0.18,
        "rooting_depth_m": 0.65,
    },
    "CLAY": {
        "field_capacity": 0.40,
        "wilting_point": 0.23,
        "saturation": 0.50,
        "drainage_fraction": 0.25,
        "runoff_fraction": 0.22,
        "rooting_depth_m": 0.60,
    },
}

_CROP_PHYSICS_DEFAULTS: Dict[str, Dict[str, float]] = {
    "citrus": {"crop_coefficient": 0.75, "t_opt": 25.0, "t_max": 39.0, "t_base": 12.0, "rooting_depth_m": 0.85},
    "orange": {"crop_coefficient": 0.75, "t_opt": 25.0, "t_max": 39.0, "t_base": 12.0, "rooting_depth_m": 0.85},
    "tomato": {"crop_coefficient": 1.05, "t_opt": 24.0, "t_max": 37.0, "t_base": 10.0, "rooting_depth_m": 0.55},
    "wheat": {"crop_coefficient": 0.95, "t_opt": 20.0, "t_max": 34.0, "t_base": 4.0, "rooting_depth_m": 0.80},
    "potato": {"crop_coefficient": 1.00, "t_opt": 20.0, "t_max": 33.0, "t_base": 7.0, "rooting_depth_m": 0.45},
    "olive": {"crop_coefficient": 0.60, "t_opt": 26.0, "t_max": 42.0, "t_base": 10.0, "rooting_depth_m": 1.00},
    "date_palm": {"crop_coefficient": 0.90, "t_opt": 30.0, "t_max": 46.0, "t_base": 14.0, "rooting_depth_m": 1.20},
}


def build_soil_and_crop_context_from_domain(
    *,
    plot_doc: Optional[Dict[str, Any]] = None,
    soil_analysis: Optional[Dict[str, Any]] = None,
    crop_cycle: Optional[Dict[str, Any]] = None,
    fallback_crop: str = "citrus",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Translate Plot, SoilAnalysis, and CropCycle domain metadata into physical ASMAE priors."""
    p = plot_doc or {}
    sa = soil_analysis or {}
    cc = crop_cycle or {}

    raw_tex = str(sa.get("texture") or p.get("soilType") or "LOAM").strip().upper().replace(" ", "_")
    hyd = dict(_TEXTURE_HYDROLOGY.get(raw_tex, _TEXTURE_HYDROLOGY["LOAM"]))
    soil_ctx: Dict[str, Any] = {
        "texture": raw_tex,
        **hyd,
    }
    if sa.get("ec") is not None and math.isfinite(float(sa["ec"])):
        soil_ctx["electrical_conductivity"] = float(sa["ec"])
    if sa.get("ph") is not None and math.isfinite(float(sa["ph"])):
        soil_ctx["ph"] = float(sa["ph"])
    if sa.get("organicMatter") is not None and math.isfinite(float(sa["organicMatter"])):
        om = float(sa["organicMatter"])
        soil_ctx["organic_matter_pct"] = om
        # Slight organic-matter water retention refinement (Saxton & Rawls sign direction)
        soil_ctx["field_capacity"] = round(min(0.48, soil_ctx["field_capacity"] + 0.008 * max(0.0, om - 1.5)), 4)

    raw_crop = str(cc.get("cropCode") or cc.get("cropType") or p.get("cropType") or fallback_crop).strip().lower()
    crop_key = raw_crop if raw_crop in _CROP_PHYSICS_DEFAULTS else fallback_crop
    crop_params = dict(_CROP_PHYSICS_DEFAULTS.get(crop_key, _CROP_PHYSICS_DEFAULTS["citrus"]))
    if crop_params.get("rooting_depth_m"):
        soil_ctx["rooting_depth_m"] = float(crop_params["rooting_depth_m"])
    crop_ctx: Dict[str, Any] = {
        "crop_type": crop_key,
        "variety": cc.get("variety"),
        "stage": cc.get("stage") or cc.get("status"),
        "crop_coefficient": crop_params["crop_coefficient"],
        "optimal_temperature": crop_params["t_opt"],
        "maximum_temperature": crop_params["t_max"],
        "base_temperature": crop_params["t_base"],
    }
    return soil_ctx, crop_ctx


def normalize_soil_moisture_vwc(raw_val: Any) -> Optional[float]:
    """Normalize IoT volumetric moisture reading (% or m3/m3) into [0.0, 0.70] m3/m3."""
    if raw_val is None or isinstance(raw_val, bool):
        return None
    try:
        v = float(raw_val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v < 0.0:
        return None
    if v > 1.5:
        v = v / 100.0
    if v > 0.75:
        return None
    return round(v, 5)


def evaluate_independent_field_evidence(
    *,
    plot_id: str,
    trajectory: Sequence[Dict[str, Any]],
    sensor_readings: Optional[Sequence[Dict[str, Any]]] = None,
    soil_analyses: Optional[Sequence[Dict[str, Any]]] = None,
    crop_observations: Optional[Sequence[Dict[str, Any]]] = None,
    crop_tasks: Optional[Sequence[Dict[str, Any]]] = None,
    mesia_packets: Optional[Sequence[Dict[str, Any]]] = None,
    exclude_mock_vendors: bool = True,
) -> Dict[str, Any]:
    """Cross-check withheld physical evidence against ASMAE's S1/S2/ERA5 posterior trajectory."""
    parsed_steps: List[Tuple[datetime, Dict[str, Any]]] = []
    for st in trajectory:
        if st.get("acquisition_time") and isinstance(st.get("posterior_state_means"), dict):
            parsed_steps.append((_parse_dt(st["acquisition_time"]), st))
    parsed_steps.sort(key=lambda item: item[0])

    def _nearest_asmae_state(ts: datetime, max_gap_days: float = 14.0) -> Optional[Tuple[float, Dict[str, Any]]]:
        best: Optional[Tuple[float, Dict[str, Any]]] = None
        for dt_s, st in parsed_steps:
            gap_d = abs((ts - dt_s).total_seconds()) / 86400.0
            if gap_d <= max_gap_days and (best is None or gap_d < best[0]):
                best = (gap_d, st)
        return best

    # 1. In-situ SensorReading validation (Soil Moisture VWC vs ASMAE root_zone_water)
    vwc_comparisons: List[Dict[str, Any]] = []
    skipped_mock_count = 0
    for rec in sensor_readings or []:
        vendor = str(rec.get("vendor") or "")
        if exclude_mock_vendors and any(tok in vendor.lower() for tok in ("mock", "simulator", "synthetic")):
            skipped_mock_count += 1
            continue
        vwc = normalize_soil_moisture_vwc(rec.get("soilMoisture"))
        raw_ts = rec.get("timestamp")
        if vwc is None or not raw_ts:
            continue
        ts_dt = _parse_dt(raw_ts)
        matched = _nearest_asmae_state(ts_dt, max_gap_days=21.0)
        if matched is None:
            continue
        gap_d, st = matched
        rzw_mu = float((st.get("posterior_state_means") or {}).get("root_zone_water", 0.0))
        rzw_sig = max(0.01, float((st.get("posterior_state_stds") or {}).get("root_zone_water", 0.05)))
        err = rzw_mu - vwc
        z_val = abs(err) / rzw_sig
        vwc_comparisons.append({
            "timestamp": ts_dt.isoformat(),
            "device_id": str(rec.get("deviceId") or rec.get("sensorId") or ""),
            "vendor": vendor or "unspecified",
            "observed_vwc": vwc,
            "asmae_rzw_mean": round(rzw_mu, 5),
            "asmae_rzw_sigma": round(rzw_sig, 5),
            "error": round(err, 5),
            "abs_z": round(z_val, 3),
            "within_2sigma": bool(z_val <= 2.0),
            "scene_gap_days": round(gap_d, 2),
        })

    # Aggregate VWC metrics deduplicated by daily/device or across all readings
    if vwc_comparisons:
        errs = np.asarray([c["error"] for c in vwc_comparisons], dtype=float)
        vwc_summary = {
            "n_readings": len(vwc_comparisons),
            "rmse_vwc": round(float(np.sqrt(np.mean(errs ** 2))), 5),
            "mae_vwc": round(float(np.mean(np.abs(errs))), 5),
            "bias_vwc": round(float(np.mean(errs)), 5),
            "coverage_2sigma": round(float(np.mean([1.0 if c["within_2sigma"] else 0.0 for c in vwc_comparisons])), 4),
            "skipped_mock_or_simulator": skipped_mock_count,
            "sample_records": vwc_comparisons[:5],
        }
    else:
        vwc_summary = {
            "n_readings": 0,
            "skipped_mock_or_simulator": skipped_mock_count,
            "note": "No overlapping real soil moisture sensor timestamps within ±21 days of assimilated satellite scenes.",
        }

    # 2. MESIA multi-strata hydrological comparison via MesiaLayer3WaterBridge
    mesia_results: List[Dict[str, Any]] = []
    for m_pkt in mesia_packets or []:
        raw_ts = m_pkt.get("timestamp")
        if not raw_ts:
            continue
        ts_dt = _parse_dt(raw_ts)
        matched = _nearest_asmae_state(ts_dt, max_gap_days=21.0)
        if matched is None:
            continue
        _, st = matched
        rzw_mu = float((st.get("posterior_state_means") or {}).get("root_zone_water", 0.25))
        stratum = LatticeStrata.ROOT_ZONE_5_30CM
        lik = BehaviourLikelihood(
            likelihood_id=str(m_pkt.get("likelihood_id") or f"mesia_{plot_id}_{ts_dt.date().isoformat()}"),
            radio_family=str(m_pkt.get("radio_family") or "LORA_RANGING"),
            contract_ref=str(m_pkt.get("contract_ref") or "contract_soil_moisture_v1"),
            target_variable="root_zone_water",
            likelihood_value=float(m_pkt.get("likelihood_value", 0.25)),
        )
        cmp_res = MesiaLayer3WaterBridge.compare_with_hydrological_model(
            plot_id=plot_id,
            stratum=stratum,
            mesia_likelihood=lik,
            layer3_model_vwc=rzw_mu,
            tolerance_vwc=0.06,
            calibrated_vwc=m_pkt.get("calibrated_vwc"),
        )
        mesia_results.append({
            "timestamp": ts_dt.isoformat(),
            "comparison_mode": cmp_res.comparison_mode,
            "is_calibrated_physical_observation": cmp_res.is_calibrated_physical_observation,
            "is_likelihood_consistency_proxy": cmp_res.is_likelihood_consistency_proxy,
            "mesia_vwc_or_proxy": round(float(cmp_res.mesia_observed_vwc), 5),
            "asmae_model_vwc": round(float(cmp_res.model_predicted_vwc), 5),
            "residual_error_vwc": round(float(cmp_res.residual_error_vwc), 5),
            "is_hydrologically_consistent": bool(cmp_res.is_hydrologically_consistent),
        })

    # 3. Scouting (CropObservation) honesty audit vs ASMAE satellite attribution
    scouting_audits: List[Dict[str, Any]] = []
    for obs in crop_observations or []:
        raw_ts = obs.get("createdAt") or obs.get("timestamp")
        if not raw_ts:
            continue
        ts_dt = _parse_dt(raw_ts)
        matched = _nearest_asmae_state(ts_dt, max_gap_days=21.0)
        if matched is None:
            continue
        gap_d, st = matched
        means = st.get("posterior_state_means") or {}
        cl_ref = st.get("cross_layer_refined") or {}
        l5 = (cl_ref.get("layers_refined") or {}).get("layer5_biotic") or {}
        scouting_audits.append({
            "timestamp": ts_dt.isoformat(),
            "obs_type": str(obs.get("type") or ""),
            "title": str(obs.get("title") or ""),
            "scene_gap_days": round(gap_d, 2),
            "asmae_vigor": round(float(means.get("vigor", 0.0)), 4),
            "asmae_stress_memory": round(float(means.get("stress_memory", 0.0)), 4),
            "l5_biotic_threat": l5.get("top_threat_hypothesis"),
            "diagnostic_note": "Satellite optical/SAR cannot independently isolate pest/compaction etiology without field scouting.",
        })

    # 4. CropTask verification: strictly segregate unconfirmed planned tasks vs completed/applied management
    applied_tasks = []
    planned_unconfirmed_tasks = []
    for tk in crop_tasks or []:
        is_completed = bool(tk.get("completed")) or str(tk.get("status") or "").upper() in ("COMPLETED", "APPLIED", "OBSERVED_CONFIRMED")
        rec = {
            "type": str(tk.get("type") or ""),
            "title": str(tk.get("title") or ""),
            "dueDate": str(tk.get("dueDate") or "")[:10],
            "completed": is_completed,
        }
        if is_completed:
            applied_tasks.append(rec)
        else:
            planned_unconfirmed_tasks.append(rec)

    # 5. SoilAnalysis inventory
    valid_soils = [
        {
            "date": str(s.get("date") or "")[:10],
            "texture": s.get("texture"),
            "ph": s.get("ph"),
            "ec": s.get("ec"),
            "organicMatter": s.get("organicMatter"),
            "nitrogen": s.get("nitrogen"),
        }
        for s in soil_analyses or []
        if any(s.get(k) is not None for k in ("texture", "ph", "ec", "organicMatter", "nitrogen"))
    ]

    return {
        "plot_id": plot_id,
        "zero_circularity_enforced": True,
        "sensor_vwc_validation": vwc_summary,
        "mesia_hydrological_validation": {
            "n_evaluated": len(mesia_results),
            "native_sigmf_captures_present": False,
            "evaluations": mesia_results,
        },
        "soil_analyses": valid_soils,
        "scouting_records_audited": len(scouting_audits),
        "scouting_sample": scouting_audits[:5],
        "crop_tasks_summary": {
            "applied_or_completed_count": len(applied_tasks),
            "unconfirmed_planned_ignored_count": len(planned_unconfirmed_tasks),
            "unconfirmed_planned_sample": planned_unconfirmed_tasks[:5],
        },
    }
