"""Chronological Retrovalidation, BMA Expert Comparison, Calibration & Forecast Skill.

Evaluates strictly causal pre-update ASMAE predictions against subsequent held-out
observations in observation space (NDVI, NDMI, SAR VV/VH), compares ASMAE and BMA
experts against persistence, DOY climatology, and damped trend baselines, and scores
PIT/CRPS uncertainty calibration and forecast skill per season/year.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from services.agribrain.layer05_asmae.assimilation.filter import (
    _forecast_elapsed_interval,
    clamp_ensemble,
)
from services.agribrain.layer05_asmae.bma.archive_expert_scoring import ArchiveExpertScoring
from services.agribrain.layer05_asmae.config import STATE_NAMES
from services.agribrain.layer05_asmae.deterministic import make_rng
from services.agribrain.layer05_asmae.observation.index_state_mapping import INDEX_STATE_REGISTRY
from services.agribrain.layer05_asmae.observation.observation_noise import compute_observation_noise
from services.agribrain.layer05_asmae.observation.s1_sar_model import predict_sar_observation
from services.agribrain.layer05_asmae.observation.s2_forward_model import predict_observation

_INV_SQRT_2 = 1.0 / math.sqrt(2.0)
_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)
_INV_SQRT_PI = 1.0 / math.sqrt(math.pi)


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z * _INV_SQRT_2))


def _norm_pdf(z: float) -> float:
    return _INV_SQRT_2PI * math.exp(-0.5 * z * z)


def _gaussian_crps(y_obs: float, mu: float, sigma: float) -> float:
    """Closed-form Gaussian Continuous Ranked Probability Score (Gneiting et al.)."""
    s = max(float(sigma), 1e-6)
    z = (float(y_obs) - float(mu)) / s
    return s * (z * (2.0 * _norm_cdf(z) - 1.0) + 2.0 * _norm_pdf(z) - _INV_SQRT_PI)


def _doy_circular_distance(doy_a: int, doy_b: int) -> int:
    diff = abs(int(doy_a) - int(doy_b))
    return min(diff, 366 - diff)


def _parse_dt(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _aggregate_regression(y_true: List[float], y_pred: List[float]) -> Dict[str, Optional[float]]:
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return {"n": 0, "rmse": None, "mae": None, "bias": None, "r2": None}
    t = np.asarray(y_true, dtype=np.float64)
    p = np.asarray(y_pred, dtype=np.float64)
    err = p - t
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mae = float(np.mean(np.abs(err)))
    bias = float(np.mean(err))
    ss_tot = float(np.sum((t - np.mean(t)) ** 2))
    r2 = float(1.0 - np.sum(err ** 2) / ss_tot) if ss_tot > 1e-8 else None
    return {
        "n": len(y_true),
        "rmse": round(rmse, 6),
        "mae": round(mae, 6),
        "bias": round(bias, 6),
        "r2": round(r2, 6) if r2 is not None else None,
    }


def _skill_score(model_errs: List[float], ref_errs: List[float]) -> Optional[float]:
    if not model_errs or len(model_errs) != len(ref_errs):
        return None
    mse_model = float(np.mean(np.asarray(model_errs, dtype=np.float64) ** 2))
    mse_ref = float(np.mean(np.asarray(ref_errs, dtype=np.float64) ** 2))
    if mse_ref <= 1e-10:
        return None
    return round(1.0 - (mse_model / mse_ref), 6)


class HistoricalRetrovalidator:
    """Computes strictly causal retrovalidation, BMA expert comparisons, calibration & seasonal skill."""

    def __init__(self, bma_temperature: float = 0.08) -> None:
        self.bma_temperature = bma_temperature
        self.expert_scorer = ArchiveExpertScoring()

    def evaluate(
        self,
        trajectory: List[Dict[str, Any]],
        context_summary: Optional[Dict[str, Any]] = None,
        *,
        evaluate_multi_horizon: bool = True,
    ) -> Dict[str, Any]:
        """Score strictly prior ASMAE + BMA expert forecasts vs baselines by season."""
        ctx = context_summary or {}
        daily_weather: Dict[str, Dict[str, Any]] = dict(ctx.get("daily_weather") or {})
        sorted_traj = sorted(trajectory, key=lambda r: str(r.get("acquisition_time") or ""))

        if len(sorted_traj) < 2:
            return {
                "status": "insufficient_observations",
                "summary": {"n_evaluated_points": 0},
                "baselines": {},
                "bma": {"weights": {}, "archive_bma_status": "diagnostic", "can_promote_to_production": False},
                "seasonal_scorecard": [],
                "multi_horizon": {"status": "insufficient_observations", "by_horizon": {}, "heldout_years": []},
                "qualification": {"passed": False, "block_reasons": ["insufficient_observations"]},
            }

        # History buffers keyed strictly by earlier observations for causal baselines & online bias tracking
        channel_history: Dict[str, List[Tuple[datetime, float]]] = {}
        channel_bias_ema: Dict[str, float] = {}
        channel_bias_count: Dict[str, int] = {}
        expert_names = (
            "optical_physiology",
            "sar_structure",
            "water_balance",
            "phenology_memory",
            "asmae_causal_calibrated",
        )

        eval_rows: List[Dict[str, Any]] = []
        expert_running_sq_err: Dict[str, List[float]] = {k: [] for k in expert_names}

        for step in sorted_traj:
            dt = _parse_dt(step["acquisition_time"])
            prior_preds = step.get("prior_predictions") or {}
            prior_state = step.get("prior_state_means") or {}

            for obs_name, p_rec in sorted(prior_preds.items()):
                y_obs = float(p_rec["y_obs"])
                y_asmae_cal = float(p_rec.get("y_pred_calibrated", p_rec["y_pred_prior"]))
                y_asmae_raw = float(p_rec.get("y_pred_raw", p_rec["y_pred_prior"]))
                sigma_cal = float(p_rec["pred_sigma"])
                sigma_raw = float(p_rec.get("raw_pred_sigma", p_rec["pred_sigma"]))

                prev_list = channel_history.get(obs_name, [])

                # 1. Baseline: Persistence (last observation on this channel)
                y_pers: Optional[float] = prev_list[-1][1] if prev_list else None

                # 2. Baseline: Causal DOY Climatology (strictly prior years, ±21 DOY)
                doy = dt.timetuple().tm_yday
                clim_vals = [
                    val for (p_dt, val) in prev_list
                    if p_dt.year < dt.year and _doy_circular_distance(doy, p_dt.timetuple().tm_yday) <= 21
                ]
                y_clim: Optional[float] = float(np.median(clim_vals)) if clim_vals else None

                # 3. Baseline: Damped Linear Trend from prior two observations on channel
                y_trend: Optional[float] = None
                if len(prev_list) >= 2:
                    t1, v1 = prev_list[-2]
                    t2, v2 = prev_list[-1]
                    dt_prev = max(1.0, (t2 - t1).total_seconds() / 86400.0)
                    dt_lead = max(0.0, (dt - t2).total_seconds() / 86400.0)
                    slope = (v2 - v1) / dt_prev
                    raw_extrap = v2 + 0.35 * slope * min(dt_lead, 21.0)
                    lo_b, hi_b = (-1.0, 1.0) if p_rec.get("sensor") == "S2" else (0.0, 1.0)
                    y_trend = float(max(lo_b, min(hi_b, raw_extrap)))

                # 4. Physics Expert Predictions (strictly pre-update from propagated state / weather / climatology)
                rzw = float(prior_state.get("root_zone_water", 0.25))
                vigor = float(prior_state.get("vigor", 0.5))
                w_today = daily_weather.get(dt.strftime("%Y-%m-%d")) or {}
                w_rain = float(w_today.get("precipitation") or 0.0) if isinstance(w_today.get("precipitation"), (int, float)) else 0.0

                lo_b, hi_b = (-1.0, 1.0) if p_rec.get("sensor") == "S2" else (0.0, 1.0)
                bias_offset = channel_bias_ema.get(obs_name, 0.0) if channel_bias_count.get(obs_name, 0) >= 2 else 0.0
                y_raw_plus_ema = float(max(lo_b, min(hi_b, y_asmae_raw + bias_offset)))

                expert_preds: Dict[str, float] = {
                    "optical_physiology": y_asmae_cal if p_rec.get("sensor") == "S2" else 0.5 * y_asmae_cal + 0.5 * max(0.0, min(1.0, 0.35 + 0.4 * vigor)),
                    "sar_structure": y_asmae_cal if p_rec.get("sensor") == "S1" else 0.7 * y_asmae_cal + 0.3 * (y_pers if y_pers is not None else y_asmae_cal),
                    "water_balance": max(
                        lo_b,
                        min(hi_b, 0.8 * y_asmae_cal + 0.2 * max(0.0, min(1.0, rzw + (0.05 if w_rain > 3.0 else -0.02)))),
                    ),
                    "phenology_memory": (
                        0.55 * y_clim + 0.45 * y_asmae_cal if y_clim is not None
                        else (0.55 * (y_pers if y_pers is not None else y_asmae_cal) + 0.45 * y_asmae_cal)
                    ),
                    "asmae_causal_calibrated": y_asmae_cal,
                }

                # Strictly causal BMA weights learned from prior expert errors BEFORE observing y_obs
                prior_rmses = {
                    exp: (
                        float(np.sqrt(np.mean(expert_running_sq_err[exp])))
                        if expert_running_sq_err[exp] else 0.15
                    )
                    for exp in expert_names
                }
                bma_step = self.expert_scorer.compute_bma_weights(prior_rmses, temperature=self.bma_temperature)
                w_map = bma_step.get("weights") or {k: 1.0 / len(expert_names) for k in expert_names}
                y_bma = sum(float(w_map.get(exp, 0.0)) * expert_preds[exp] for exp in expert_names)

                # Record PIT / CRPS / errors strictly when >=1 prior step existed
                if prev_list:
                    z_cal = (y_obs - y_asmae_cal) / max(sigma_cal, 1e-6)
                    z_raw = (y_obs - y_asmae_raw) / max(sigma_raw, 1e-6)
                    lead_days = (dt - prev_list[-1][0]).total_seconds() / 86400.0
                    eval_rows.append({
                        "year": dt.year,
                        "acquisition_time": dt.isoformat(),
                        "lead_days": round(lead_days, 2),
                        "channel": obs_name,
                        "sensor": p_rec.get("sensor"),
                        "y_obs": y_obs,
                        "y_asmae": y_asmae_cal,
                        "y_asmae_raw": y_asmae_raw,
                        "y_debiased": y_raw_plus_ema,
                        "sigma_pred": sigma_cal,
                        "sigma_raw": sigma_raw,
                        "y_bma": y_bma,
                        "y_pers": y_pers,
                        "y_clim": y_clim,
                        "y_trend": y_trend,
                        "abs_z": abs(z_cal),
                        "abs_z_raw": abs(z_raw),
                        "pit": _norm_cdf(z_cal),
                        "crps": _gaussian_crps(y_obs, y_asmae_cal, sigma_cal),
                        "crps_raw": _gaussian_crps(y_obs, y_asmae_raw, sigma_raw),
                        "expert_preds": expert_preds,
                    })

                innov = y_obs - y_asmae_raw
                cnt_prev = channel_bias_count.get(obs_name, 0)
                channel_bias_ema[obs_name] = (
                    innov if cnt_prev == 0 else (0.75 * channel_bias_ema[obs_name] + 0.25 * innov)
                )
                channel_bias_count[obs_name] = cnt_prev + 1
                for exp in expert_names:
                    expert_running_sq_err[exp].append((expert_preds[exp] - y_obs) ** 2)

            for obs_name, p_rec in prior_preds.items():
                channel_history.setdefault(obs_name, []).append((dt, float(p_rec["y_obs"])))

        if not eval_rows:
            return {
                "status": "insufficient_out_of_sample_pairs",
                "summary": {"n_evaluated_points": 0},
                "baselines": {},
                "bma": {"weights": {}, "archive_bma_status": "diagnostic", "can_promote_to_production": False},
                "seasonal_scorecard": [],
                "multi_horizon": {"status": "insufficient_out_of_sample_pairs", "by_horizon": {}, "heldout_years": []},
                "qualification": {"passed": False, "block_reasons": ["insufficient_out_of_sample_pairs"]},
            }

        summary = self._score_subset("all_seasons", eval_rows)
        raw_uncalibrated_summary = {
            **_aggregate_regression([r["y_obs"] for r in eval_rows], [r["y_asmae_raw"] for r in eval_rows]),
            "coverage_1sigma": round(sum(1 for r in eval_rows if r["abs_z_raw"] <= 1.0) / len(eval_rows), 4),
            "coverage_2sigma": round(sum(1 for r in eval_rows if r["abs_z_raw"] <= 2.0) / len(eval_rows), 4),
            "mean_crps": round(float(np.mean([r["crps_raw"] for r in eval_rows])), 6),
        }

        expert_rmses: Dict[str, float] = {
            exp: round(float(np.sqrt(np.mean([(r["expert_preds"][exp] - r["y_obs"]) ** 2 for r in eval_rows]))), 6)
            for exp in expert_names
        }
        bma_summary = self.expert_scorer.compute_bma_weights(expert_rmses, temperature=self.bma_temperature)
        bma_summary["expert_rmses"] = expert_rmses
        bma_summary["bma_consensus_rmse"] = summary.get("bma_rmse")

        pers_rows = [r for r in eval_rows if r["y_pers"] is not None]
        clim_rows = [r for r in eval_rows if r["y_clim"] is not None]
        trend_rows = [r for r in eval_rows if r["y_trend"] is not None]
        baselines = {
            "persistence": _aggregate_regression([r["y_obs"] for r in pers_rows], [r["y_pers"] for r in pers_rows]),
            "doy_climatology": _aggregate_regression([r["y_obs"] for r in clim_rows], [r["y_clim"] for r in clim_rows]),
            "damped_linear_trend": _aggregate_regression([r["y_obs"] for r in trend_rows], [r["y_trend"] for r in trend_rows]),
            "asmae_raw_uncalibrated": _aggregate_regression([r["y_obs"] for r in eval_rows], [r["y_asmae_raw"] for r in eval_rows]),
            "asmae_enkf": _aggregate_regression([r["y_obs"] for r in eval_rows], [r["y_asmae"] for r in eval_rows]),
            "asmae_calibrated": _aggregate_regression([r["y_obs"] for r in eval_rows], [r["y_asmae"] for r in eval_rows]),
            "bma_consensus": _aggregate_regression([r["y_obs"] for r in eval_rows], [r["y_bma"] for r in eval_rows]),
        }

        by_ch_rows: Dict[str, List[Dict[str, Any]]] = {}
        for r in eval_rows:
            by_ch_rows.setdefault(str(r["channel"]), []).append(r)
        by_channel = {
            ch: self._score_subset(ch, ch_rows)
            for ch, ch_rows in sorted(by_ch_rows.items())
        }

        by_year: Dict[int, List[Dict[str, Any]]] = {}
        for r in eval_rows:
            by_year.setdefault(int(r["year"]), []).append(r)
        seasonal_scorecard = [
            {"season_year": yr, **self._score_subset(f"season_{yr}", rows)}
            for yr, rows in sorted(by_year.items())
        ]

        # Predeclared out-of-sample multi-horizon forecast qualification (strictly unknown future weather!)
        multi_horizon = (
            self._evaluate_multi_horizon_forecasts(
                sorted_traj=sorted_traj,
                ctx=ctx,
                all_years=sorted(by_year.keys()),
            )
            if evaluate_multi_horizon
            else {"status": "skipped_for_fast_causal_slice", "by_horizon": {}, "heldout_years": []}
        )

        # Strict Epistemic Qualification Gate (P1-B): NEVER promote ARCHIVE_POSTERIOR_VALIDATED on negative
        # overall persistence skill, miscalibrated spread, or unverified prospective horizons!
        block_reasons: List[str] = []
        n_ev = int(summary.get("n_evaluated_points") or 0)
        cov1 = float(summary.get("coverage_1sigma") or 0.0)
        cov2 = float(summary.get("coverage_2sigma") or 0.0)
        sk_clim = summary.get("skill_vs_climatology")
        sk_pers = summary.get("skill_vs_persistence")
        mh_by_h = multi_horizon.get("by_horizon") or {}
        mh_skills = [
            float(v["skill_vs_persistence"])
            for v in mh_by_h.values()
            if isinstance(v, dict) and isinstance(v.get("skill_vs_persistence"), (int, float))
        ]
        mh_mean_skill = float(np.mean(mh_skills)) if mh_skills else None
        mh_min_skill = min(mh_skills) if mh_skills else None

        if n_ev < 12:
            block_reasons.append(f"insufficient_evaluation_samples:{n_ev}<12")
        if not (0.56 <= cov1 <= 0.80):
            block_reasons.append(f"coverage_1sigma_outside_nominal_band:{cov1:.4f}")
        if cov2 < 0.88:
            block_reasons.append(f"coverage_2sigma_underdispersed:{cov2:.4f}")
        if sk_clim is not None and float(sk_clim) < 0.05:
            block_reasons.append(f"skill_below_climatology:{sk_clim:.4f}")
        if sk_pers is None or float(sk_pers) < 0.0:
            block_reasons.append(f"overall_step_skill_below_persistence:{sk_pers}")
        if evaluate_multi_horizon:
            if mh_mean_skill is None or mh_mean_skill < 0.0:
                block_reasons.append(f"prospective_multi_horizon_mean_skill_below_persistence:{mh_mean_skill}")
            if mh_min_skill is not None and mh_min_skill < -0.10:
                block_reasons.append(f"prospective_horizon_min_skill_below_threshold:{mh_min_skill:.4f}")

        qualification = {
            "passed": len(block_reasons) == 0,
            "qualification_tier": (
                "VALIDATED_PROSPECTIVE_QUALIFIED" if len(block_reasons) == 0
                else "DIAGNOSTIC_HISTORICAL_RECONSTRUCTION"
            ),
            "block_reasons": block_reasons,
            "criteria": {
                "min_eval_points": 12,
                "coverage_1sigma_band": [0.56, 0.80],
                "min_coverage_2sigma": 0.88,
                "min_skill_vs_climatology": 0.05,
                "min_overall_skill_vs_persistence": 0.0,
                "min_prospective_horizon_mean_skill": 0.0,
                "min_prospective_single_horizon_skill": -0.10,
            },
            "observed_values": {
                "n_evaluated_points": n_ev,
                "coverage_1sigma": cov1,
                "coverage_2sigma": cov2,
                "skill_vs_climatology": sk_clim,
                "skill_vs_persistence": sk_pers,
                "prospective_multi_horizon_mean_skill": round(mh_mean_skill, 6) if mh_mean_skill is not None else None,
                "prospective_multi_horizon_best_skill": round(max(mh_skills), 6) if mh_skills else None,
            },
        }

        return {
            "status": "evaluated",
            "summary": summary,
            "raw_uncalibrated_summary": raw_uncalibrated_summary,
            "baselines": baselines,
            "by_channel": by_channel,
            "bma": bma_summary,
            "seasonal_scorecard": seasonal_scorecard,
            "multi_horizon": multi_horizon,
            "qualification": qualification,
        }

    def _evaluate_multi_horizon_forecasts(
        self,
        *,
        sorted_traj: List[Dict[str, Any]],
        ctx: Dict[str, Any],
        all_years: List[int],
    ) -> Dict[str, Any]:
        """Predeclared prospective evaluation across untouched held-out seasons & lead horizons."""
        if not all_years or len(sorted_traj) < 6:
            return {"status": "insufficient_history", "by_horizon": {}, "heldout_years": []}

        # Predeclare last <= 3 years (at least 1, keeping >= 1 burn-in year when multi-year) as untouched held-out seasons
        if len(all_years) >= 5:
            heldout_years = [yr for yr in all_years if yr >= max(2024, all_years[-3])]
        elif len(all_years) >= 2:
            heldout_years = [all_years[-1]]
        else:
            heldout_years = list(all_years)
        heldout_set = set(heldout_years)
        burnin_years = [yr for yr in all_years if yr not in heldout_set]

        daily_weather: Dict[str, Dict[str, Any]] = dict(ctx.get("daily_weather") or {})
        crop_ctx = dict(ctx.get("crop_context") or {"crop_type": "citrus", "crop_coefficient": 0.75})
        soil_ctx = dict(ctx.get("soil_context") or {})

        # Index all real observations strictly by date/time across trajectory
        parsed_steps: List[Tuple[datetime, Dict[str, Any]]] = [
            (_parse_dt(s["acquisition_time"]), s) for s in sorted_traj
        ]
        # Build causal channel history for fair persistence / DOY climatology lookup at t_issue
        all_obs_points: List[Tuple[datetime, str, float]] = []
        for dt, s in parsed_steps:
            for ch, pr in (s.get("prior_predictions") or {}).items():
                all_obs_points.append((dt, str(ch), float(pr["y_obs"])))

        bins = [
            ("short_1_7d", 0.5, 7.0),
            ("medium_8_16d", 7.0, 16.0),
            ("extended_17_35d", 16.0, 35.0),
        ]
        bin_rows: Dict[str, List[Dict[str, Any]]] = {b[0]: [] for b in bins}
        year_rows: Dict[int, List[Dict[str, Any]]] = {yr: [] for yr in heldout_years}

        from services.agribrain.layer05_asmae.history.historical_state_reconstructor import (
            apply_causal_channel_calibration,
            build_prospective_weather_series,
        )

        # Issue causal forecasts at up to ~40 evenly spaced issue points in held-out seasons
        heldout_indices = [idx for idx, (dt, _) in enumerate(parsed_steps) if dt.year in heldout_set]
        stride = max(1, len(heldout_indices) // 40) if heldout_indices else 1
        issue_indices = heldout_indices[::stride]
        hindcast_bin_rows: Dict[str, List[Dict[str, Any]]] = {b[0]: [] for b in bins}

        for idx in issue_indices:
            t_issue, step_i = parsed_steps[idx]
            post_m = step_i.get("posterior_state_means") or {}
            post_s = step_i.get("posterior_state_stds") or {}
            if not post_m:
                continue
            cal_snap = step_i.get("channel_calibration_snapshot") or {}
            step_priors = step_i.get("cross_layer_priors") or {}

            # Find all target observations landing in (0.5d, 35.0d] strictly after t_issue
            targets: List[Tuple[int, datetime, Dict[str, Any]]] = []
            for j in range(idx + 1, len(parsed_steps)):
                t_tgt, step_j = parsed_steps[j]
                lead = (t_tgt - t_issue).total_seconds() / 86400.0
                if lead > 35.0:
                    break
                if lead > 0.5:
                    targets.append((j, t_tgt, step_j))
            if not targets:
                continue

            # Strictly prospective unknown-future-weather series at t_issue (ZERO realized future ERA5 weather!)
            max_tgt_dt = targets[-1][1]
            prosp_weather = build_prospective_weather_series(daily_weather, t_issue, max_tgt_dt)

            def _run_horizon_rollout(weather_map: Dict[str, Dict[str, Any]], out_bins: Dict[str, List[Dict[str, Any]]], record_years: bool) -> None:
                vec_mean = [float(post_m.get(n, 0.25)) for n in STATE_NAMES]
                vec_std = [max(1e-4, float(post_s.get(n, 0.05))) for n in STATE_NAMES]
                rng = make_rng(
                    "mh_eval",
                    str(ctx.get("plot_id") or "plot"),
                    str(ctx.get("geometry_hash") or "geom"),
                    extra=t_issue.isoformat(),
                )
                ens_fc: Dict[str, List[List[float]]] = {
                    "mz_000": [
                        [float(vec_mean[k] + (0.5 * vec_std[k] * ((m - 3.5) / 3.5))) for k in range(len(STATE_NAMES))]
                        for m in range(8)
                    ]
                }
                cur_dt = t_issue
                for _, t_tgt, step_j in targets:
                    lead = (t_tgt - t_issue).total_seconds() / 86400.0
                    if t_tgt > cur_dt:
                        ens_fc, _ = _forecast_elapsed_interval(
                            ensemble=ens_fc,
                            previous_time=cur_dt,
                            current_time=t_tgt,
                            priors=step_priors,
                            crop_context=crop_ctx,
                            rng=rng,
                            scenes=[],
                            weather_daily_series=weather_map,
                            soil_context=soil_ctx,
                            management_events=[],
                        )
                        ens_fc = clamp_ensemble(ens_fc)
                        cur_dt = t_tgt

                    b_name = next((name for name, lo_d, hi_d in bins if lo_d < lead <= hi_d), None)
                    if b_name is None:
                        continue

                    fc_preds_tgt = step_j.get("prior_predictions") or {}
                    for ch, pr_tgt in fc_preds_tgt.items():
                        mapping = INDEX_STATE_REGISTRY.get(ch)
                        if mapping is None:
                            continue
                        y_obs = float(pr_tgt["y_obs"])
                        m_hats = []
                        for member in ens_fc["mz_000"]:
                            yh = predict_sar_observation(ch, member) if mapping.sensor == "S1" else predict_observation(ch, member)
                            if yh is not None and math.isfinite(float(yh)):
                                m_hats.append(float(yh))
                        if not m_hats:
                            continue
                        y_raw = float(np.mean(m_hats))
                        ens_var = float(np.var(m_hats, ddof=1)) if len(m_hats) > 1 else 0.0
                        # Issuance-time nominal clear-sky observation noise ONLY (zero future step_j obs_sigma!)
                        sig_nominal = compute_observation_noise(ch, cloud_fraction=0.10, valid_support_fraction=0.90)
                        cal = apply_causal_channel_calibration(
                            cal_snap.get(ch),
                            obs_name=ch,
                            raw_pred_mean=y_raw,
                            raw_pred_var=ens_var,
                            obs_sigma=sig_nominal,
                            elapsed_days=float(lead),
                            now_dt=t_tgt,
                        )
                        y_cal = cal["cal_pred_mean"]
                        sig_fc = cal["cal_sigma"]

                        # Fair Persistence & Causal Climatology strictly from obs <= t_issue!
                        prior_ch = [(d_o, v_o) for d_o, c_o, v_o in all_obs_points if c_o == ch and d_o <= t_issue]
                        if not prior_ch:
                            continue
                        y_pers = prior_ch[-1][1]
                        t_doy = t_tgt.timetuple().tm_yday
                        clim_vals = [v_o for d_o, v_o in prior_ch if d_o.year < t_tgt.year and _doy_circular_distance(t_doy, d_o.timetuple().tm_yday) <= 21]
                        y_clim = float(np.median(clim_vals)) if clim_vals else None

                        w_clim = min(0.35, 0.015 * max(0.0, lead - 5.0)) if y_clim is not None else 0.0
                        y_joint = (1.0 - w_clim) * y_cal + w_clim * (y_clim if y_clim is not None else y_cal)

                        row = {
                            "channel": ch,
                            "lead_days": round(lead, 2),
                            "year": t_tgt.year,
                            "y_obs": y_obs,
                            "y_asmae_cal": y_cal,
                            "y_joint_bma": y_joint,
                            "y_pers": y_pers,
                            "y_clim": y_clim,
                            "sigma": sig_fc,
                            "abs_z": abs(y_obs - y_joint) / max(sig_fc, 1e-6),
                            "crps": _gaussian_crps(y_obs, y_joint, sig_fc),
                        }
                        out_bins[b_name].append(row)
                        if record_years and t_tgt.year in year_rows:
                            year_rows[t_tgt.year].append(row)

            # Primary: strictly prospective unknown-future-weather evaluation
            _run_horizon_rollout(prosp_weather, bin_rows, record_years=True)
            # Secondary reference: realized-weather hindcast (strictly quarantined from qualification!)
            _run_horizon_rollout(daily_weather, hindcast_bin_rows, record_years=False)

        def _score_mh(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
            if not rows:
                return {"n": 0}
            yt = [r["y_obs"] for r in rows]
            y_cal = [r["y_asmae_cal"] for r in rows]
            y_j = [r["y_joint_bma"] for r in rows]
            y_p = [r["y_pers"] for r in rows]
            reg_cal = _aggregate_regression(yt, y_cal)
            reg_j = _aggregate_regression(yt, y_j)
            reg_p = _aggregate_regression(yt, y_p)
            c_rows = [r for r in rows if r["y_clim"] is not None]
            reg_c = _aggregate_regression([r["y_obs"] for r in c_rows], [r["y_clim"] for r in c_rows])
            return {
                "n": len(rows),
                "asmae_calibrated_rmse": reg_cal["rmse"],
                "joint_forecast_rmse": reg_j["rmse"],
                "persistence_rmse": reg_p["rmse"],
                "climatology_rmse": reg_c["rmse"],
                "skill_vs_persistence": _skill_score([a - b for a, b in zip(y_j, yt)], [p - b for p, b in zip(y_p, yt)]),
                "asmae_only_skill_vs_persistence": _skill_score([a - b for a, b in zip(y_cal, yt)], [p - b for p, b in zip(y_p, yt)]),
                "skill_vs_climatology": _skill_score(
                    [r["y_joint_bma"] - r["y_obs"] for r in c_rows],
                    [r["y_clim"] - r["y_obs"] for r in c_rows],
                ),
                "coverage_1sigma": round(sum(1 for r in rows if r["abs_z"] <= 1.0) / len(rows), 4),
                "coverage_2sigma": round(sum(1 for r in rows if r["abs_z"] <= 2.0) / len(rows), 4),
                "mean_crps": round(float(np.mean([r["crps"] for r in rows])), 6),
            }

        return {
            "status": "evaluated",
            "protocol": "strict_prospective_unknown_future_weather",
            "uses_realized_future_weather": False,
            "uses_issuance_day_complete_daily_weather": False,
            "weather_cutoff_rule": "strict_previous_complete_day_before_issue",
            "uses_target_scene_obs_sigma": False,
            "burnin_calibration_years": burnin_years,
            "heldout_years": heldout_years,
            "by_horizon": {b_name: _score_mh(rows) for b_name, rows in bin_rows.items()},
            "by_heldout_year": {str(yr): _score_mh(rows) for yr, rows in sorted(year_rows.items())},
            "hindcast_realized_weather_reference": {
                "epistemic_scope": "retrospective_hindcast_realized_weather",
                "used_for_qualification": False,
                "by_horizon": {b_name: _score_mh(rows) for b_name, rows in hindcast_bin_rows.items()},
            },
        }

    @staticmethod
    def compare_cross_layer_ablation(
        cross_layer_retro: Dict[str, Any],
        s1_s2_only_retro: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare Combined L2-8 Cross-Layer ASMAE against S1/S2-only ASMAE ablation."""
        cl_sum = cross_layer_retro.get("summary") or {}
        s_sum = s1_s2_only_retro.get("summary") or {}
        cl_rmse = cl_sum.get("rmse")
        s_rmse = s_sum.get("rmse")
        cl_crps = cl_sum.get("mean_crps")
        s_crps = s_sum.get("mean_crps")
        delta_rmse = round(float(cl_rmse) - float(s_rmse), 6) if isinstance(cl_rmse, (int, float)) and isinstance(s_rmse, (int, float)) else None
        skill_gain = round(1.0 - (float(cl_rmse) ** 2) / max(1e-10, float(s_rmse) ** 2), 6) if isinstance(cl_rmse, (int, float)) and isinstance(s_rmse, (int, float)) else None
        return {
            "cross_layer_rmse": cl_rmse,
            "s1_s2_only_rmse": s_rmse,
            "delta_rmse_cross_minus_s1s2": delta_rmse,
            "skill_gain_vs_s1_s2_only": skill_gain,
            "cross_layer_crps": cl_crps,
            "s1_s2_only_crps": s_crps,
            "cross_layer_coverage_1sigma": cl_sum.get("coverage_1sigma"),
            "s1_s2_only_coverage_1sigma": s_sum.get("coverage_1sigma"),
            "cross_layer_multi_horizon": (cross_layer_retro.get("multi_horizon") or {}).get("by_horizon", {}),
            "s1_s2_only_multi_horizon": (s1_s2_only_retro.get("multi_horizon") or {}).get("by_horizon", {}),
        }

    def _score_subset(self, label: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        y_true = [r["y_obs"] for r in rows]
        y_asmae = [r["y_asmae"] for r in rows]
        y_bma = [r["y_bma"] for r in rows]

        reg = _aggregate_regression(y_true, y_asmae)
        bma_reg = _aggregate_regression(y_true, y_bma)

        pers_rows = [r for r in rows if r["y_pers"] is not None]
        clim_rows = [r for r in rows if r["y_clim"] is not None]
        pers_reg = _aggregate_regression([r["y_obs"] for r in pers_rows], [r["y_pers"] for r in pers_rows])
        clim_reg = _aggregate_regression([r["y_obs"] for r in clim_rows], [r["y_clim"] for r in clim_rows])

        skill_pers = _skill_score(
            [r["y_asmae"] - r["y_obs"] for r in pers_rows],
            [r["y_pers"] - r["y_obs"] for r in pers_rows],
        )
        skill_clim = _skill_score(
            [r["y_asmae"] - r["y_obs"] for r in clim_rows],
            [r["y_clim"] - r["y_obs"] for r in clim_rows],
        )
        bma_skill_pers = _skill_score(
            [r["y_bma"] - r["y_obs"] for r in pers_rows],
            [r["y_pers"] - r["y_obs"] for r in pers_rows],
        )

        cov_1s = sum(1 for r in rows if r["abs_z"] <= 1.0) / len(rows)
        cov_2s = sum(1 for r in rows if r["abs_z"] <= 2.0) / len(rows)
        pits = [r["pit"] for r in rows]
        crps_vals = [r["crps"] for r in rows]

        return {
            "label": label,
            "n_evaluated_points": len(rows),
            "rmse": reg["rmse"],
            "mae": reg["mae"],
            "bias": reg["bias"],
            "r2": reg["r2"],
            "bma_rmse": bma_reg["rmse"],
            "bma_mae": bma_reg["mae"],
            "persistence_rmse": pers_reg["rmse"],
            "climatology_rmse": clim_reg["rmse"],
            "skill_vs_persistence": skill_pers,
            "skill_vs_climatology": skill_clim,
            "bma_skill_vs_persistence": bma_skill_pers,
            "coverage_1sigma": round(cov_1s, 4),
            "coverage_2sigma": round(cov_2s, 4),
            "mean_pit": round(float(np.mean(pits)), 4),
            "pit_std": round(float(np.std(pits)), 4),
            "mean_crps": round(float(np.mean(crps_vals)), 6),
        }
