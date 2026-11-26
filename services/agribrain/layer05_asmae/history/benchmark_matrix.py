"""W7: Scientific Benchmark Matrix across crops, climates, horizons (incl. exploratory 36-90d),
leave-one-plot-out, leave-one-crop-system-out, counterfactual arms, and Layer 2 crop detection.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .historical_crop_fusion import evaluate_crop_detection_benchmark


def _finite_float(val: Any) -> Optional[float]:
    if isinstance(val, bool) or val is None:
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _extract_counterfactual_arms(plot_report: Mapping[str, Any]) -> Dict[str, Any]:
    """Assemble explicit counterfactual ablation arms from retrovalidation + independent validation."""
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

    pers_rmse = _finite_float((baselines.get("persistence") or {}).get("rmse"))
    clim_rmse = _finite_float((baselines.get("doy_climatology") or {}).get("rmse"))
    trend_rmse = _finite_float((baselines.get("damped_linear_trend") or {}).get("rmse"))
    asmae_rmse = _finite_float(summary.get("rmse"))
    asmae_raw_rmse = _finite_float(raw_sum.get("rmse"))
    bma_rmse = _finite_float(
        bma.get("bma_consensus_rmse")
        or (baselines.get("bma_consensus") or {}).get("rmse")
        or summary.get("bma_rmse")
        or (bma.get("joint_consensus") or {}).get("rmse")
    )

    def _rel_skill(arm_rmse: Optional[float], ref_rmse: Optional[float]) -> Optional[float]:
        if arm_rmse is None or ref_rmse is None or ref_rmse <= 1e-12:
            return None
        return round(1.0 - (arm_rmse / ref_rmse), 6)

    native_sigmf = bool(mesia.get("native_sigmf_captures_present", False))
    mesia_status = "evaluated_with_native_sigmf" if native_sigmf else "withheld_no_verified_native_sigmf_captures"

    return {
        "asmae_s1_s2_only_uncalibrated": {
            "rmse": asmae_raw_rmse,
            "skill_vs_persistence": _rel_skill(asmae_raw_rmse, pers_rmse),
        },
        "cross_layer_l2_l8_coupled": {
            "rmse": asmae_rmse,
            "skill_vs_persistence": _finite_float(summary.get("skill_vs_persistence")),
            "skill_vs_climatology": _finite_float(summary.get("skill_vs_climatology")),
            "skill_vs_damped_trend": _rel_skill(asmae_rmse, trend_rmse),
            "coverage_1sigma": _finite_float(summary.get("coverage_1sigma")),
            "coverage_2sigma": _finite_float(summary.get("coverage_2sigma")),
        },
        "bma_consensus": {
            "rmse": bma_rmse,
            "skill_vs_persistence": _finite_float(summary.get("bma_skill_vs_persistence"))
            if summary.get("bma_skill_vs_persistence") is not None
            else _rel_skill(bma_rmse, pers_rmse),
            "skill_vs_climatology": _rel_skill(bma_rmse, clim_rmse),
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
    }


def evaluate_cross_plot_matrix(
    cohort_items: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Compute generalized multi-crop, leave-one-plot-out, leave-one-crop-system-out, and crop-detection matrix."""
    rows: List[Dict[str, Any]] = []
    verified_crop_rows: List[Dict[str, Any]] = []

    for item in cohort_items:
        pid = str(item.get("plot_id") or "")
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
            "crop_identity_verified": bool(dom.get("crop_identity_verified", False)),
            "tenant_identity_verified": bool(dom.get("tenant_identity_verified", False)),
            "is_isolated_dev_fixture": bool(dom.get("is_isolated_dev_fixture", True)),
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
            "counterfactual_arms": arms,
        }
        rows.append(row)
        if row["crop_identity_verified"]:
            verified_crop_rows.append(row)

    # 1. Leave-One-Plot-Out across verified crop plots (also reporting full-cohort diagnostic LOPO)
    def _lopo_folds(subset: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        folds: List[Dict[str, Any]] = []
        for idx, held in enumerate(subset):
            train = [r for j, r in enumerate(subset) if j != idx]
            train_skills = [
                _finite_float((r["counterfactual_arms"]["cross_layer_l2_l8_coupled"] or {}).get("skill_vs_climatology"))
                for r in train
            ]
            valid_train_sk = [s for s in train_skills if s is not None]
            train_bma_w: Dict[str, float] = {}
            for r in train:
                for exp, wt in ((r["counterfactual_arms"].get("bma_consensus") or {}).get("expert_weights") or {}).items():
                    train_bma_w[exp] = train_bma_w.get(exp, 0.0) + float(wt or 0.0)
            w_tot = sum(train_bma_w.values()) or 1.0
            consensus_prior_weights = {k: round(v / w_tot, 4) for k, v in sorted(train_bma_w.items())}

            held_l2 = held["counterfactual_arms"]["cross_layer_l2_l8_coupled"]
            held_bma = held["counterfactual_arms"]["bma_consensus"]
            folds.append({
                "heldout_plot_id": held["plot_id"],
                "heldout_crop": held["crop_code"],
                "heldout_crop_verified": held["crop_identity_verified"],
                "train_plot_count": len(train),
                "train_mean_skill_vs_climatology": round(sum(valid_train_sk) / len(valid_train_sk), 4) if valid_train_sk else None,
                "train_transferred_bma_weights": consensus_prior_weights,
                "heldout_l2_l8_rmse": held_l2.get("rmse"),
                "heldout_l2_l8_skill_vs_climatology": held_l2.get("skill_vs_climatology"),
                "heldout_bma_skill_vs_climatology": held_bma.get("skill_vs_climatology"),
                "heldout_qualification_passed": held["qualification_passed"],
                "heldout_failure_cause": held["primary_failure_cause"],
            })
        return folds

    # 2. Leave-One-Crop-System-Out across verified crops
    crop_groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in verified_crop_rows:
        crop_groups.setdefault(str(r["crop_code"]), []).append(r)

    locso_folds: List[Dict[str, Any]] = []
    for held_crop, held_list in sorted(crop_groups.items()):
        train_other = [r for r in verified_crop_rows if r["crop_code"] != held_crop]
        train_sk = [
            _finite_float((r["counterfactual_arms"]["cross_layer_l2_l8_coupled"] or {}).get("skill_vs_climatology"))
            for r in train_other
        ]
        train_sk = [s for s in train_sk if s is not None]
        held_sk = [
            _finite_float((r["counterfactual_arms"]["cross_layer_l2_l8_coupled"] or {}).get("skill_vs_climatology"))
            for r in held_list
        ]
        held_sk = [s for s in held_sk if s is not None]
        locso_folds.append({
            "heldout_crop_system": held_crop,
            "heldout_plots": [r["plot_id"] for r in held_list],
            "train_other_crop_systems": sorted({r["crop_code"] for r in train_other}),
            "train_mean_skill_vs_climatology": round(sum(train_sk) / len(train_sk), 4) if train_sk else None,
            "heldout_mean_skill_vs_climatology": round(sum(held_sk) / len(held_sk), 4) if held_sk else None,
            "verified_crop_qualification_count": sum(1 for r in held_list if r["qualification_passed"]),
        })

    # 3. Layer 2 Crop-Detection Benchmark across verified non-synthetic labels
    crop_bench = evaluate_crop_detection_benchmark(cohort_items)

    return {
        "matrix_version": "asmae_world_model_v1_benchmark_matrix",
        "cohort_size": len(rows),
        "verified_crop_plot_count": len(verified_crop_rows),
        "verified_tenant_plot_count": sum(1 for r in rows if r["tenant_identity_verified"]),
        "qualified_production_identity_count": sum(1 for r in rows if r["qualification_passed"]),
        "qualified_verified_crop_count": sum(1 for r in verified_crop_rows if r["qualification_passed"]),
        "per_plot_benchmark": rows,
        "leave_one_plot_out": {
            "verified_crop_only_folds": _lopo_folds(verified_crop_rows),
            "full_cohort_diagnostic_folds": _lopo_folds(rows),
        },
        "leave_one_crop_system_out": locso_folds,
        "crop_detection_benchmark": crop_bench,
    }


__all__ = ["evaluate_cross_plot_matrix"]
