"""Chronological Retrovalidation, BMA Expert Comparison, Calibration & Forecast Skill.

Evaluates strictly causal pre-update ASMAE predictions against subsequent held-out
observations in observation space (NDVI, NDMI, SAR VV/VH), compares ASMAE and BMA
experts against persistence, DOY climatology, and damped trend baselines, and scores
PIT/CRPS uncertainty calibration and forecast skill per season/year.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from services.agribrain.layer05_asmae.bma.archive_expert_scoring import ArchiveExpertScoring

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
            "asmae_causal_debiased",
        )

        eval_rows: List[Dict[str, Any]] = []
        expert_running_sq_err: Dict[str, List[float]] = {k: [] for k in expert_names}

        for step in sorted_traj:
            dt = _parse_dt(step["acquisition_time"])
            prior_preds = step.get("prior_predictions") or {}
            prior_state = step.get("prior_state_means") or {}
            post_state = step.get("posterior_state_means") or {}

            for obs_name, p_rec in sorted(prior_preds.items()):
                y_obs = float(p_rec["y_obs"])
                y_asmae = float(p_rec["y_pred_prior"])
                sigma_pred = float(p_rec["pred_sigma"])

                prev_list = channel_history.get(obs_name, [])

                # 1. Baseline: Persistence (last observation on this channel)
                y_pers: Optional[float] = prev_list[-1][1] if prev_list else None

                # 2. Baseline: Causal DOY Climatology (strictly prior years, ±15 DOY)
                doy = dt.timetuple().tm_yday
                clim_vals = [
                    val for (p_dt, val) in prev_list
                    if p_dt.year < dt.year and _doy_circular_distance(doy, p_dt.timetuple().tm_yday) <= 15
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
                    raw_extrap = v2 + 0.5 * slope * min(dt_lead, 30.0)
                    lo_b, hi_b = (-1.0, 1.0) if p_rec.get("sensor") == "S2" else (0.0, 1.0)
                    y_trend = float(max(lo_b, min(hi_b, raw_extrap)))

                # 4. Physics Expert Predictions (strictly pre-update from propagated state / weather / climatology)
                rzw = float(prior_state.get("root_zone_water", 0.25))
                vigor = float(prior_state.get("vigor", 0.5))
                w_today = daily_weather.get(dt.strftime("%Y-%m-%d")) or {}
                w_rain = float(w_today.get("precipitation") or 0.0) if isinstance(w_today.get("precipitation"), (int, float)) else 0.0

                lo_b, hi_b = (-1.0, 1.0) if p_rec.get("sensor") == "S2" else (0.0, 1.0)
                bias_offset = channel_bias_ema.get(obs_name, 0.0) if channel_bias_count.get(obs_name, 0) >= 2 else 0.0
                y_debiased = float(max(lo_b, min(hi_b, y_asmae + bias_offset)))

                expert_preds: Dict[str, float] = {
                    "optical_physiology": y_asmae if p_rec.get("sensor") == "S2" else 0.5 * y_asmae + 0.5 * max(0.0, min(1.0, 0.35 + 0.4 * vigor)),
                    "sar_structure": y_asmae if p_rec.get("sensor") == "S1" else 0.7 * y_asmae + 0.3 * (y_pers if y_pers is not None else y_asmae),
                    "water_balance": max(
                        -1.0 if p_rec.get("sensor") == "S2" else 0.0,
                        min(1.0, 0.8 * y_asmae + 0.2 * max(0.0, min(1.0, rzw + (0.05 if w_rain > 3.0 else -0.02)))),
                    ),
                    "phenology_memory": (
                        0.6 * y_clim + 0.4 * y_asmae if y_clim is not None
                        else (0.65 * (y_pers if y_pers is not None else y_asmae) + 0.35 * y_asmae)
                    ),
                    "asmae_causal_debiased": y_debiased,
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

                # Record PIT / CRPS / errors strictly when at least 1 prior step existed (prevents trivial t_0 bias)
                if prev_list:
                    z = (y_obs - y_asmae) / max(sigma_pred, 1e-6)
                    lead_days = (dt - prev_list[-1][0]).total_seconds() / 86400.0
                    eval_rows.append({
                        "year": dt.year,
                        "acquisition_time": dt.isoformat(),
                        "lead_days": round(lead_days, 2),
                        "channel": obs_name,
                        "sensor": p_rec.get("sensor"),
                        "y_obs": y_obs,
                        "y_asmae": y_asmae,
                        "y_debiased": y_debiased,
                        "sigma_pred": sigma_pred,
                        "y_bma": y_bma,
                        "y_pers": y_pers,
                        "y_clim": y_clim,
                        "y_trend": y_trend,
                        "abs_z": abs(z),
                        "pit": _norm_cdf(z),
                        "crps": _gaussian_crps(y_obs, y_asmae, sigma_pred),
                        "expert_preds": expert_preds,
                    })

                # Now update causal buffers AFTER prediction evaluation
                innov = y_obs - y_asmae
                cnt_prev = channel_bias_count.get(obs_name, 0)
                channel_bias_ema[obs_name] = (
                    innov if cnt_prev == 0 else (0.75 * channel_bias_ema[obs_name] + 0.25 * innov)
                )
                channel_bias_count[obs_name] = cnt_prev + 1
                for exp in expert_names:
                    expert_running_sq_err[exp].append((expert_preds[exp] - y_obs) ** 2)

            # Append observed channel values into causal history AFTER scoring all step channels
            for obs_name, p_rec in prior_preds.items():
                channel_history.setdefault(obs_name, []).append((dt, float(p_rec["y_obs"])))

        if not eval_rows:
            return {
                "status": "insufficient_out_of_sample_pairs",
                "summary": {"n_evaluated_points": 0},
                "baselines": {},
                "bma": {"weights": {}, "archive_bma_status": "diagnostic", "can_promote_to_production": False},
                "seasonal_scorecard": [],
            }

        # Aggregate Global Summary
        summary = self._score_subset("all_seasons", eval_rows)

        # Aggregate BMA diagnostic weights from full historical expert performance
        expert_rmses: Dict[str, float] = {
            exp: round(float(np.sqrt(np.mean([(r["expert_preds"][exp] - r["y_obs"]) ** 2 for r in eval_rows]))), 6)
            for exp in expert_names
        }
        bma_summary = self.expert_scorer.compute_bma_weights(expert_rmses, temperature=self.bma_temperature)
        bma_summary["expert_rmses"] = expert_rmses
        bma_summary["bma_consensus_rmse"] = summary.get("bma_rmse")

        # Baselines global summary
        pers_rows = [r for r in eval_rows if r["y_pers"] is not None]
        clim_rows = [r for r in eval_rows if r["y_clim"] is not None]
        trend_rows = [r for r in eval_rows if r["y_trend"] is not None]
        baselines = {
            "persistence": _aggregate_regression([r["y_obs"] for r in pers_rows], [r["y_pers"] for r in pers_rows]),
            "doy_climatology": _aggregate_regression([r["y_obs"] for r in clim_rows], [r["y_clim"] for r in clim_rows]),
            "damped_linear_trend": _aggregate_regression([r["y_obs"] for r in trend_rows], [r["y_trend"] for r in trend_rows]),
            "asmae_enkf": _aggregate_regression([r["y_obs"] for r in eval_rows], [r["y_asmae"] for r in eval_rows]),
            "asmae_causal_debiased": _aggregate_regression([r["y_obs"] for r in eval_rows], [r["y_debiased"] for r in eval_rows]),
            "bma_consensus": _aggregate_regression([r["y_obs"] for r in eval_rows], [r["y_bma"] for r in eval_rows]),
        }

        by_ch_rows: Dict[str, List[Dict[str, Any]]] = {}
        for r in eval_rows:
            by_ch_rows.setdefault(str(r["channel"]), []).append(r)
        by_channel = {
            ch: self._score_subset(ch, ch_rows)
            for ch, ch_rows in sorted(by_ch_rows.items())
        }

        # Per-season / year scorecard
        by_year: Dict[int, List[Dict[str, Any]]] = {}
        for r in eval_rows:
            by_year.setdefault(int(r["year"]), []).append(r)
        seasonal_scorecard = [
            {"season_year": yr, **self._score_subset(f"season_{yr}", rows)}
            for yr, rows in sorted(by_year.items())
        ]

        return {
            "status": "evaluated",
            "summary": summary,
            "baselines": baselines,
            "by_channel": by_channel,
            "bma": bma_summary,
            "seasonal_scorecard": seasonal_scorecard,
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
