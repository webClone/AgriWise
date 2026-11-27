"""Cross-plot Scientific Benchmark Matrix: descriptive summaries, out-of-sample LOPO/LOCSO
transfer learning, counterfactual ablation arms, and Layer 2 crop-detection evaluation.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .historical_crop_fusion import evaluate_crop_detection_benchmark

_EXPERT_NAMES: Tuple[str, ...] = (
    "optical_physiology",
    "sar_structure",
    "water_balance",
    "phenology_memory",
    "asmae_causal_calibrated",
)


def _finite_float(val: Any) -> Optional[float]:
    if isinstance(val, bool) or val is None:
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _mse_skill(model_errs: Sequence[float], ref_errs: Sequence[float]) -> Optional[float]:
    if not model_errs or len(model_errs) != len(ref_errs):
        return None
    mse_model = float(np.mean(np.asarray(model_errs, dtype=np.float64) ** 2))
    mse_ref = float(np.mean(np.asarray(ref_errs, dtype=np.float64) ** 2))
    if mse_ref <= 1e-12:
        return None
    return round(1.0 - (mse_model / mse_ref), 6)


def _rmse_ratio_from_errs(model_errs: Sequence[float], ref_errs: Sequence[float]) -> Optional[float]:
    if not model_errs or len(model_errs) != len(ref_errs):
        return None
    rmse_m = float(np.sqrt(np.mean(np.asarray(model_errs, dtype=np.float64) ** 2)))
    rmse_r = float(np.sqrt(np.mean(np.asarray(ref_errs, dtype=np.float64) ** 2)))
    if rmse_r <= 1e-12:
        return None
    return round(1.0 - (rmse_m / rmse_r), 6)


def _rmse_ratio_scalars(arm_rmse: Optional[float], ref_rmse: Optional[float]) -> Optional[float]:
    if arm_rmse is None or ref_rmse is None or ref_rmse <= 1e-12:
        return None
    return round(1.0 - (arm_rmse / ref_rmse), 6)


def _mse_skill_scalars(arm_rmse: Optional[float], ref_rmse: Optional[float]) -> Optional[float]:
    if arm_rmse is None or ref_rmse is None or ref_rmse <= 1e-12:
        return None
    return round(1.0 - ((arm_rmse / ref_rmse) ** 2), 6)


def _channel_bounds(sensor: Any) -> Tuple[float, float]:
    return (-1.0, 1.0) if str(sensor or "").upper() == "S2" else (0.0, 1.0)


def _compute_expert_preds(sample: Mapping[str, Any], y_cal: float) -> Dict[str, float]:
    sensor = str(sample.get("sensor") or "S2").upper()
    lo_b, hi_b = _channel_bounds(sensor)
    vigor = float(sample.get("vigor", 0.5) or 0.5)
    rzw = float(sample.get("rzw", 0.25) or 0.25)
    w_rain = float(sample.get("w_rain", 0.0) or 0.0)
    y_pers = _finite_float(sample.get("y_pers"))
    y_clim = _finite_float(sample.get("y_clim"))
    return {
        "optical_physiology": (
            y_cal if sensor == "S2" else 0.5 * y_cal + 0.5 * max(0.0, min(1.0, 0.35 + 0.4 * vigor))
        ),
        "sar_structure": (
            y_cal if sensor == "S1" else 0.7 * y_cal + 0.3 * (y_pers if y_pers is not None else y_cal)
        ),
        "water_balance": max(
            lo_b,
            min(hi_b, 0.8 * y_cal + 0.2 * max(0.0, min(1.0, rzw + (0.05 if w_rain > 3.0 else -0.02)))),
        ),
        "phenology_memory": (
            0.55 * y_clim + 0.45 * y_cal
            if y_clim is not None
            else (0.55 * (y_pers if y_pers is not None else y_cal) + 0.45 * y_cal)
        ),
        "asmae_causal_calibrated": y_cal,
    }


def _collect_samples(items: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in items:
        retro = item.get("retrovalidation") or (item.get("reconstruction") or {}).get("retrovalidation") or {}
        samples = item.get("step_transfer_samples") or retro.get("step_transfer_samples") or []
        for s in samples:
            if isinstance(s, Mapping) and _finite_float(s.get("y_obs")) is not None and _finite_float(s.get("y_asmae_raw")) is not None:
                out.append(dict(s))
    return out


def _fit_transfer_model(train_samples: Sequence[Mapping[str, Any]], *, bma_temperature: float = 0.08) -> Dict[str, Any]:
    """Fit ridge-shrunk per-channel affine calibration & BMA weights strictly on training folds."""
    by_channel: Dict[str, List[Tuple[float, float]]] = {}
    for s in train_samples:
        ch = str(s.get("channel") or "")
        xr = _finite_float(s.get("y_asmae_raw"))
        yo = _finite_float(s.get("y_obs"))
        if ch and xr is not None and yo is not None:
            by_channel.setdefault(ch, []).append((xr, yo))

    channel_cal: Dict[str, Dict[str, float]] = {}
    prior_strength = 8.0
    for ch, pairs in by_channel.items():
        xs = np.asarray([p[0] for p in pairs], dtype=np.float64)
        ys = np.asarray([p[1] for p in pairs], dtype=np.float64)
        n = float(len(pairs))
        x_mean = float(np.mean(xs))
        y_mean = float(np.mean(ys))
        var_prior = 0.04
        sxx = float(np.sum((xs - x_mean) ** 2)) + prior_strength * var_prior
        sxy = float(np.sum((xs - x_mean) * (ys - y_mean))) + prior_strength * var_prior * 1.0
        slope = max(0.55, min(1.45, sxy / max(1e-8, sxx)))
        bias = max(-0.35, min(0.35, (n * (y_mean - slope * x_mean)) / (n + prior_strength)))
        channel_cal[ch] = {
            "slope": round(float(slope), 6),
            "bias": round(float(bias), 6),
            "n_train": int(n),
        }

    exp_sq_errs: Dict[str, List[float]] = {exp: [] for exp in _EXPERT_NAMES}
    for s in train_samples:
        ch = str(s.get("channel") or "")
        lo_b, hi_b = _channel_bounds(s.get("sensor"))
        xr = float(s["y_asmae_raw"])
        yo = float(s["y_obs"])
        c = channel_cal.get(ch) or {"slope": 1.0, "bias": 0.0}
        y_cal = max(lo_b, min(hi_b, c["slope"] * xr + c["bias"]))
        experts = _compute_expert_preds(s, y_cal)
        for exp in _EXPERT_NAMES:
            exp_sq_errs[exp].append((experts[exp] - yo) ** 2)

    raw_weights: Dict[str, float] = {}
    for exp in _EXPERT_NAMES:
        rmse_exp = float(np.sqrt(np.mean(exp_sq_errs[exp]))) if exp_sq_errs[exp] else 0.15
        raw_weights[exp] = math.exp(-rmse_exp / max(1e-3, float(bma_temperature)))
    w_sum = sum(raw_weights.values()) or 1.0
    bma_weights = {exp: round(val / w_sum, 6) for exp, val in raw_weights.items()}

    return {
        "train_sample_count": len(train_samples),
        "channel_calibration": channel_cal,
        "bma_weights": bma_weights,
    }


def _predict_transfer_zero_shot(
    model: Mapping[str, Any],
    held_samples: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Predict zero-shot on held-out plot(s) using ONLY parameters learned on training folds."""
    if not held_samples:
        return {"status": "insufficient_heldout_samples", "n_heldout_samples": 0}
    channel_cal = model.get("channel_calibration") or {}
    bma_weights = model.get("bma_weights") or {exp: 1.0 / len(_EXPERT_NAMES) for exp in _EXPERT_NAMES}

    y_true: List[float] = []
    raw_errs: List[float] = []
    cal_errs: List[float] = []
    bma_errs: List[float] = []
    pers_pairs: List[Tuple[float, float, float]] = []
    clim_pairs: List[Tuple[float, float, float]] = []

    for s in held_samples:
        ch = str(s.get("channel") or "")
        lo_b, hi_b = _channel_bounds(s.get("sensor"))
        xr = float(s["y_asmae_raw"])
        yo = float(s["y_obs"])
        c = channel_cal.get(ch) or {"slope": 1.0, "bias": 0.0}
        y_cal = max(lo_b, min(hi_b, float(c["slope"]) * xr + float(c["bias"])))
        experts = _compute_expert_preds(s, y_cal)
        y_bma = sum(float(bma_weights.get(exp, 0.0)) * experts[exp] for exp in _EXPERT_NAMES)

        y_true.append(yo)
        raw_errs.append(xr - yo)
        cal_errs.append(y_cal - yo)
        bma_errs.append(y_bma - yo)

        yp = _finite_float(s.get("y_pers"))
        yc = _finite_float(s.get("y_clim"))
        if yp is not None:
            pers_pairs.append((y_cal - yo, y_bma - yo, yp - yo))
        if yc is not None:
            clim_pairs.append((y_cal - yo, y_bma - yo, yc - yo))

    def _rmse(errs: Sequence[float]) -> Optional[float]:
        return round(float(np.sqrt(np.mean(np.asarray(errs, dtype=np.float64) ** 2))), 6) if errs else None

    cal_rmse = _rmse(cal_errs)
    bma_rmse = _rmse(bma_errs)
    raw_rmse = _rmse(raw_errs)
    pers_rmse = _rmse([p[2] for p in pers_pairs])
    clim_rmse = _rmse([c[2] for c in clim_pairs])

    return {
        "status": "evaluated",
        "zero_shot_out_of_sample": True,
        "heldout_parameter_updates": 0,
        "n_heldout_samples": len(y_true),
        "heldout_raw_uncalibrated_rmse": raw_rmse,
        "heldout_zero_shot_cal_rmse": cal_rmse,
        "heldout_zero_shot_bma_rmse": bma_rmse,
        "heldout_persistence_rmse": pers_rmse,
        "heldout_climatology_rmse": clim_rmse,
        "heldout_zero_shot_cal_mse_skill_vs_persistence": _mse_skill([p[0] for p in pers_pairs], [p[2] for p in pers_pairs]),
        "heldout_zero_shot_bma_mse_skill_vs_persistence": _mse_skill([p[1] for p in pers_pairs], [p[2] for p in pers_pairs]),
        "heldout_zero_shot_cal_rmse_ratio_vs_persistence": _rmse_ratio_from_errs([p[0] for p in pers_pairs], [p[2] for p in pers_pairs]),
        "heldout_zero_shot_bma_rmse_ratio_vs_persistence": _rmse_ratio_from_errs([p[1] for p in pers_pairs], [p[2] for p in pers_pairs]),
        "heldout_zero_shot_cal_mse_skill_vs_climatology": _mse_skill([c[0] for c in clim_pairs], [c[2] for c in clim_pairs]),
        "heldout_zero_shot_bma_mse_skill_vs_climatology": _mse_skill([c[1] for c in clim_pairs], [c[2] for c in clim_pairs]),
        "transfer_skill_gain_vs_raw_mse": _mse_skill(bma_errs, raw_errs),
    }


def _evaluate_transfer_folds(
    train_items: Sequence[Mapping[str, Any]],
    held_items: Sequence[Mapping[str, Any]],
    *,
    fold_meta: Dict[str, Any],
) -> Dict[str, Any]:
    train_samples = _collect_samples(train_items)
    held_samples = _collect_samples(held_items)
    if len(train_samples) < 3 or len(held_samples) < 2:
        return {
            **fold_meta,
            "status": "insufficient_step_samples",
            "train_sample_count": len(train_samples),
            "n_heldout_samples": len(held_samples),
        }
    model = _fit_transfer_model(train_samples)
    eval_res = _predict_transfer_zero_shot(model, held_samples)
    return {
        **fold_meta,
        "train_sample_count": model["train_sample_count"],
        "learned_bma_weights": model["bma_weights"],
        "learned_channel_calibration": model["channel_calibration"],
        **eval_res,
    }


def _extract_counterfactual_arms(plot_report: Mapping[str, Any]) -> Dict[str, Any]:
    """Assemble explicit counterfactual ablation arms with unified MSE skill vs RMSE ratio metrics."""
    retro = dict(
        plot_report.get("retrovalidation")
        or (plot_report.get("reconstruction") or {}).get("retrovalidation")
        or {}
    )
    summary = dict(retro.get("summary") or {})
    raw_sum = dict(retro.get("raw_uncalibrated_summary") or {})
    baselines = dict(retro.get("baselines") or {})
    bma = dict(retro.get("bma") or {})
    field_val = dict(plot_report.get("independent_field_validation") or {})
    mesia = dict(field_val.get("mesia_hydrological_validation") or {})
    mh = dict(retro.get("multi_horizon") or {})

    pers_rmse = _finite_float((baselines.get("persistence") or {}).get("rmse") or summary.get("persistence_rmse"))
    clim_rmse = _finite_float((baselines.get("doy_climatology") or {}).get("rmse") or summary.get("climatology_rmse"))
    trend_rmse = _finite_float((baselines.get("damped_linear_trend") or {}).get("rmse"))
    asmae_rmse = _finite_float(summary.get("rmse"))
    asmae_raw_rmse = _finite_float(raw_sum.get("rmse") or (baselines.get("asmae_raw_uncalibrated") or {}).get("rmse"))
    bma_rmse = _finite_float(
        bma.get("bma_consensus_rmse")
        or (baselines.get("bma_consensus") or {}).get("rmse")
        or summary.get("bma_rmse")
        or (bma.get("joint_consensus") or {}).get("rmse")
    )

    native_sigmf = bool(mesia.get("native_sigmf_captures_present", False))
    mesia_status = "evaluated_with_native_sigmf" if native_sigmf else "withheld_no_verified_native_sigmf_captures"

    mse_sk_pers = _finite_float(summary.get("mse_skill_score_vs_persistence") or summary.get("skill_vs_persistence"))
    if mse_sk_pers is None:
        mse_sk_pers = _mse_skill_scalars(asmae_rmse, pers_rmse)
    rmse_rat_pers = _finite_float(summary.get("rmse_skill_ratio_vs_persistence")) or _rmse_ratio_scalars(asmae_rmse, pers_rmse)

    mse_sk_clim = _finite_float(summary.get("mse_skill_score_vs_climatology") or summary.get("skill_vs_climatology"))
    if mse_sk_clim is None:
        mse_sk_clim = _mse_skill_scalars(asmae_rmse, clim_rmse)
    rmse_rat_clim = _finite_float(summary.get("rmse_skill_ratio_vs_climatology")) or _rmse_ratio_scalars(asmae_rmse, clim_rmse)

    bma_mse_pers = _finite_float(summary.get("bma_mse_skill_score_vs_persistence") or summary.get("bma_skill_vs_persistence"))
    if bma_mse_pers is None:
        bma_mse_pers = _mse_skill_scalars(bma_rmse, pers_rmse)

    return {
        "asmae_s1_s2_only_uncalibrated": {
            "rmse": asmae_raw_rmse,
            "mse_skill_score_vs_persistence": _mse_skill_scalars(asmae_raw_rmse, pers_rmse),
            "rmse_skill_ratio_vs_persistence": _rmse_ratio_scalars(asmae_raw_rmse, pers_rmse),
            "skill_vs_persistence": _mse_skill_scalars(asmae_raw_rmse, pers_rmse),
        },
        "cross_layer_l2_l8_coupled": {
            "rmse": asmae_rmse,
            "skill_vs_persistence": mse_sk_pers,
            "mse_skill_score_vs_persistence": mse_sk_pers,
            "rmse_skill_ratio_vs_persistence": rmse_rat_pers,
            "skill_vs_climatology": mse_sk_clim,
            "mse_skill_score_vs_climatology": mse_sk_clim,
            "rmse_skill_ratio_vs_climatology": rmse_rat_clim,
            "mse_skill_score_vs_damped_trend": _mse_skill_scalars(asmae_rmse, trend_rmse),
            "rmse_skill_ratio_vs_damped_trend": _rmse_ratio_scalars(asmae_rmse, trend_rmse),
            "coverage_1sigma": _finite_float(summary.get("coverage_1sigma")),
            "coverage_2sigma": _finite_float(summary.get("coverage_2sigma")),
        },
        "bma_consensus": {
            "rmse": bma_rmse,
            "skill_vs_persistence": bma_mse_pers,
            "mse_skill_score_vs_persistence": bma_mse_pers,
            "rmse_skill_ratio_vs_persistence": _finite_float(summary.get("bma_rmse_skill_ratio_vs_persistence")) or _rmse_ratio_scalars(bma_rmse, pers_rmse),
            "mse_skill_score_vs_climatology": _mse_skill_scalars(bma_rmse, clim_rmse),
            "rmse_skill_ratio_vs_climatology": _rmse_ratio_scalars(bma_rmse, clim_rmse),
            "expert_weights": bma.get("weights") or bma.get("expert_weights") or {},
        },
        "mesia_assisted": {
            "status": mesia_status,
            "native_sigmf_captures_present": native_sigmf,
            "rmse": None if not native_sigmf else _finite_float((mesia.get("summary") or {}).get("rmse")),
        },
        "baselines": {
            "persistence_rmse": pers_rmse,
            "doy_climatology_rmse": clim_rmse,
            "damped_linear_trend_rmse": trend_rmse,
        },
        "prospective_horizons": {
            **(mh.get("by_horizon") or {}),
            **{
                k: v
                for k, v in (mh.get("exploratory_by_horizon") or {}).items()
                if isinstance(v, Mapping)
            },
        },
        "diagnostic_backfill_horizon_reference": mh.get("diagnostic_backfill_horizon_reference") or {},
    }


def _aggregate_transfer_summary(folds: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    eval_folds = [f for f in folds if f.get("status") == "evaluated"]
    if not eval_folds:
        return {"evaluated_fold_count": 0}
    bma_rmses = [float(f["heldout_zero_shot_bma_rmse"]) for f in eval_folds if isinstance(f.get("heldout_zero_shot_bma_rmse"), (int, float))]
    bma_pers_skills = [
        float(f["heldout_zero_shot_bma_mse_skill_vs_persistence"])
        for f in eval_folds
        if isinstance(f.get("heldout_zero_shot_bma_mse_skill_vs_persistence"), (int, float))
    ]
    bma_clim_skills = [
        float(f["heldout_zero_shot_bma_mse_skill_vs_climatology"])
        for f in eval_folds
        if isinstance(f.get("heldout_zero_shot_bma_mse_skill_vs_climatology"), (int, float))
    ]
    return {
        "evaluated_fold_count": len(eval_folds),
        "total_heldout_samples": sum(int(f.get("n_heldout_samples") or 0) for f in eval_folds),
        "mean_heldout_zero_shot_bma_rmse": round(float(np.mean(bma_rmses)), 6) if bma_rmses else None,
        "mean_heldout_zero_shot_bma_mse_skill_vs_persistence": round(float(np.mean(bma_pers_skills)), 6) if bma_pers_skills else None,
        "mean_heldout_zero_shot_bma_mse_skill_vs_climatology": round(float(np.mean(bma_clim_skills)), 6) if bma_clim_skills else None,
    }


def evaluate_cross_plot_matrix(
    cohort_items: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Compute descriptive per-plot/crop summaries, true out-of-sample LOPO/LOCSO transfer, and L2 crop detection."""
    rows: List[Dict[str, Any]] = []
    verified_crop_rows: List[Dict[str, Any]] = []
    item_by_plot_id: Dict[str, Mapping[str, Any]] = {}

    for item in cohort_items:
        pid = str(item.get("plot_id") or "")
        item_by_plot_id[pid] = item
        dom = dict(item.get("domain_identity") or {})
        retro = dict(
            item.get("retrovalidation")
            or (item.get("reconstruction") or {}).get("retrovalidation")
            or {}
        )
        qual = dict(retro.get("qualification") or item.get("qualification") or {})
        arms = _extract_counterfactual_arms(item)
        diag = dict(retro.get("scientific_failure_diagnosis") or item.get("scientific_failure_diagnosis") or {})
        fusion = dict(item.get("crop_fusion") or {})
        latest_crop_post = dict(fusion.get("latest_crop_posterior") or {})

        row = {
            "plot_id": pid,
            "plot_name": dom.get("plot_name") or item.get("plot_name") or pid,
            "crop_code": dom.get("resolved_crop_code") or "unknown",
            "crop_declaration_authority": dom.get("crop_declaration_authority") or "UNKNOWN_UNDECLARED",
            "crop_identity_verified": bool(dom.get("crop_identity_verified", False)),
            "tenant_identity_verified": bool(dom.get("tenant_identity_verified", False)),
            "tenant_ownership_source": dom.get("tenant_resolution_source") or dom.get("tenant_ownership_source") or "unverified",
            "is_isolated_dev_fixture": bool(dom.get("is_isolated_dev_fixture", False)),
            "synthetic_label_rejected": bool(dom.get("synthetic_label_rejected", False)),
            "eo_top_crop_group": latest_crop_post.get("top_group") or "unknown",
            "eo_unknown_probability": _finite_float(latest_crop_post.get("unknown_probability")),
            "soil_texture": dom.get("soil_texture") or "loam",
            "qualification_passed": bool(qual.get("passed", False)),
            "qualification_tier": qual.get("qualification_tier") or "DIAGNOSTIC_HISTORICAL_RECONSTRUCTION",
            "block_reasons": list(qual.get("block_reasons") or []),
            "primary_failure_cause": diag.get("primary_cause"),
            "failure_causes": list(diag.get("causes") or []),
            "recommended_evidence_to_unblock": list(diag.get("recommended_evidence_to_unblock") or []),
            "n_eval_points": int(
                (retro.get("summary") or {}).get("n_evaluated_points")
                or (retro.get("summary") or {}).get("n_points")
                or 0
            ),
            "evaluation_scope": "descriptive_in_sample_plot_summary",
            "counterfactual_arms": arms,
        }
        rows.append(row)
        if row["crop_identity_verified"]:
            verified_crop_rows.append(row)

    # 1. Descriptive per-crop-group summary (explicitly NOT out-of-sample transfer!)
    desc_crop_groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        desc_crop_groups.setdefault(str(r["crop_code"]), []).append(r)
    descriptive_crop_group_summary = [
        {
            "crop_group": cg,
            "evaluation_scope": "descriptive_in_sample_plot_summary",
            "plot_count": len(grp_rows),
            "verified_crop_plot_count": sum(1 for r in grp_rows if r["crop_identity_verified"]),
            "qualified_count": sum(1 for r in grp_rows if r["qualification_passed"]),
            "plot_ids": [r["plot_id"] for r in grp_rows],
            "mean_mse_skill_vs_climatology": (
                round(
                    sum(vals) / len(vals),
                    6,
                )
                if (
                    vals := [
                        v
                        for r in grp_rows
                        if (v := _finite_float((r["counterfactual_arms"]["cross_layer_l2_l8_coupled"] or {}).get("mse_skill_score_vs_climatology"))) is not None
                    ]
                )
                else None
            ),
        }
        for cg, grp_rows in sorted(desc_crop_groups.items())
    ]

    # 2. Genuine out-of-sample Leave-One-Plot-Out (trained strictly on training plots, zero-shot on held-out plot)
    def _trained_lopo(subset_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        folds: List[Dict[str, Any]] = []
        for idx, held_row in enumerate(subset_rows):
            train_items = [item_by_plot_id[r["plot_id"]] for j, r in enumerate(subset_rows) if j != idx]
            held_item = item_by_plot_id[held_row["plot_id"]]
            folds.append(
                _evaluate_transfer_folds(
                    train_items,
                    [held_item],
                    fold_meta={
                        "fold_protocol": "trained_transfer_lopo",
                        "heldout_plot_id": held_row["plot_id"],
                        "heldout_plot_name": held_row["plot_name"],
                        "heldout_crop": held_row["crop_code"],
                        "heldout_crop_verified": held_row["crop_identity_verified"],
                        "train_plot_ids": [r["plot_id"] for j, r in enumerate(subset_rows) if j != idx],
                    },
                )
            )
        return {
            "aggregate": _aggregate_transfer_summary(folds),
            "folds": folds,
        }

    # 3. Genuine out-of-sample Leave-One-Crop-System-Out (prefer verified crops; also expose full diagnostic crop-system splits)
    def _trained_locso(subset_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        by_crop: Dict[str, List[Mapping[str, Any]]] = {}
        for r in subset_rows:
            by_crop.setdefault(str(r["crop_code"]), []).append(r)
        folds: List[Dict[str, Any]] = []
        for held_crop, held_rows in sorted(by_crop.items()):
            train_rows = [r for r in subset_rows if str(r["crop_code"]) != held_crop]
            folds.append(
                _evaluate_transfer_folds(
                    [item_by_plot_id[r["plot_id"]] for r in train_rows],
                    [item_by_plot_id[r["plot_id"]] for r in held_rows],
                    fold_meta={
                        "fold_protocol": "trained_transfer_locso",
                        "heldout_crop_system": held_crop,
                        "heldout_plot_ids": [r["plot_id"] for r in held_rows],
                        "train_crop_systems": sorted({str(r["crop_code"]) for r in train_rows}),
                        "train_plot_ids": [r["plot_id"] for r in train_rows],
                    },
                )
            )
        return {
            "aggregate": _aggregate_transfer_summary(folds),
            "folds": folds,
        }

    trained_lopo_verified = _trained_lopo(verified_crop_rows)
    trained_lopo_full = _trained_lopo(rows)
    trained_locso_verified = _trained_locso(verified_crop_rows)
    trained_locso_full = _trained_locso(rows)

    # 4. Layer 2 Crop-Detection Benchmark (full multiclass calibration, coverage, conditional accuracy, abstention & non-crop recall)
    crop_bench = evaluate_crop_detection_benchmark(cohort_items)

    scientifically_qualified_count = sum(1 for r in rows if r["qualification_passed"])
    production_eligible_verified_count = sum(
        1 for r in rows
        if r["qualification_passed"] and r["tenant_identity_verified"] and r["crop_identity_verified"]
    )
    return {
        "matrix_version": "asmae_world_model_v2_benchmark_matrix",
        "cohort_size": len(rows),
        "verified_crop_plot_count": len(verified_crop_rows),
        "verified_tenant_plot_count": sum(1 for r in rows if r["tenant_identity_verified"]),
        "scientifically_qualified_model_count": scientifically_qualified_count,
        "production_eligible_verified_count": production_eligible_verified_count,
        "qualified_verified_crop_count": sum(1 for r in verified_crop_rows if r["qualification_passed"]),
        "metric_definitions": {
            "mse_skill_score": "1 - (MSE_model / MSE_ref); 0 = equals baseline, >0 = lower MSE than baseline.",
            "rmse_skill_ratio": "1 - (RMSE_model / RMSE_ref); linear RMSE fractional reduction vs baseline.",
            "descriptive_summary_scope": "Descriptive in-sample summary of each plot's individual chronological evaluation.",
            "trained_transfer_scope": "Out-of-sample transfer: channel affine calibration and BMA weights fitted strictly on training folds and evaluated zero-shot with 0 parameter updates on held-out plot(s).",
        },
        "descriptive_per_plot_summary": rows,
        "descriptive_crop_group_summary": descriptive_crop_group_summary,
        "per_plot_benchmark": rows,
        "trained_transfer_lopo": {
            "verified_crop_only": trained_lopo_verified,
            "full_cohort_diagnostic": trained_lopo_full,
        },
        "trained_transfer_locso": {
            "verified_crop_only": trained_locso_verified,
            "full_cohort_diagnostic": trained_locso_full,
        },
        "crop_detection_benchmark": crop_bench,
    }


__all__ = ["evaluate_cross_plot_matrix"]
