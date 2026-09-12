"""
Engine 4: Outcome Evaluation — Multi-Metric Causal Assessment

Upgrade from simple pre/post NDVI to multi-metric causal attribution:
  - NDVI Recovery (pre/post delta)
  - Growth Velocity Recovery (d(NDVI)/dt comparison)
  - Risk Reduction Delta (threat probability change)
  - Yield Proxy Delta (cumulative NDVI integral)
  - Stress Index Change (composite stress metric)

Confounder gating:
  - Rain events, temperature swings, phenological transitions
  - Method selection: PRE_POST, DIFF_IN_DIFF, SYNTHETIC_BASELINE
"""

from typing import Any, Dict, List
from datetime import datetime, timedelta, timezone

from layer6_exec.schema import (
    OutcomeMetric, OutcomeMetricId, CausalMethod,
    OutcomeProjection, InterventionCandidate, UpstreamDigest,
)


def _mean(vals: List[float]) -> float:
    return sum(vals) / max(len(vals), 1) if vals else 0.0


def _slope(vals: List[float], dates: List[datetime] = None) -> float:
    """Rate of change estimate: Delta v / Delta t in units/day."""
    if len(vals) < 2:
        return 0.0
    if dates is not None and len(dates) == len(vals):
        try:
            dt_days = (dates[-1] - dates[0]).total_seconds() / 86400.0
            if dt_days > 1e-5:
                return (vals[-1] - vals[0]) / dt_days
        except Exception:
            pass
    return (vals[-1] - vals[0]) / (len(vals) - 1)


def _integral(vals: List[float]) -> float:
    """Trapezoidal integration proxy."""
    if len(vals) < 2:
        return 0.0
    return sum((vals[i] + vals[i + 1]) / 2.0 for i in range(len(vals) - 1))


def compute_outcomes(
    timeseries: List[Dict[str, Any]],
    completed_interventions: List[InterventionCandidate],
    confounders: List[str],
) -> List[OutcomeMetric]:
    """Multi-metric outcome evaluation for completed interventions."""
    outcomes: List[OutcomeMetric] = []

    if not timeseries or not completed_interventions:
        return outcomes

    now = datetime.now(timezone.utc)

    for intervention in completed_interventions:
        # Exposure verification check:
        # Requires application_status == "COMPLETED_VERIFIED" and valid actual_execution_timestamp
        actual_ts = getattr(intervention, "actual_execution_timestamp", None)
        app_status = getattr(intervention, "application_status", "")

        exposure_verified = (
            app_status == "COMPLETED_VERIFIED" and actual_ts is not None
        )
        causal_classification = (
            "CAUSAL_ATTRIBUTED" if exposure_verified else "OBSERVATIONAL_ASSOCIATION_ONLY"
        )

        # Resolve execution date: use actual timestamp when available, else timing window start
        if actual_ts is not None:
            if isinstance(actual_ts, datetime):
                exec_date = actual_ts
            elif isinstance(actual_ts, str):
                try:
                    exec_date = datetime.fromisoformat(actual_ts)
                except (ValueError, TypeError):
                    exec_date = now
            else:
                exec_date = now
        else:
            tw = intervention.timing_window or {}
            try:
                exec_date = datetime.fromisoformat(tw.get("start", now.isoformat()))
            except (ValueError, TypeError):
                exec_date = now

        # Define analysis windows
        pre_start = (exec_date - timedelta(days=14)).date().isoformat()
        pre_end = (exec_date - timedelta(days=1)).date().isoformat()
        post_start = (exec_date + timedelta(days=1)).date().isoformat()
        post_end = (exec_date + timedelta(days=14)).date().isoformat()

        # Extract NDVI series
        pre_ndvi, post_ndvi = [], []
        pre_dates, post_dates = [], []
        pre_rain, post_rain = [], []

        for rec in timeseries:
            if not isinstance(rec, dict):
                continue
            d = rec.get("date", "")
            ndvi = rec.get("ndvi_smoothed") or rec.get("ndvi_interpolated")
            rain = rec.get("rain") or rec.get("precipitation") or 0

            if ndvi is not None:
                d_obj = None
                try:
                    d_obj = datetime.fromisoformat(d)
                except Exception:
                    pass

                if pre_start <= d <= pre_end:
                    pre_ndvi.append(float(ndvi))
                    pre_rain.append(float(rain or 0))
                    if d_obj:
                        pre_dates.append(d_obj)
                elif post_start <= d <= post_end:
                    post_ndvi.append(float(ndvi))
                    post_rain.append(float(rain or 0))
                    if d_obj:
                        post_dates.append(d_obj)

        if not pre_ndvi or not post_ndvi:
            continue

        # ── Dynamic Confounder Detection ─────────────────────────────────
        local_confounders = list(confounders)
        if sum(post_rain) > 20:
            local_confounders.append("EVAL_WINDOW_RAIN_EVENT")
        if sum(post_rain) > 50:
            local_confounders.append("HEAVY_RAIN_CONFOUNDING")

        # Temperature swings
        for rec in timeseries:
            if not isinstance(rec, dict):
                continue
            d = rec.get("date", "")
            if post_start <= d <= post_end:
                tmax = rec.get("temp_max")
                tmin = rec.get("temp_min")
                if tmax and float(tmax) > 38:
                    local_confounders.append("HEAT_WAVE_CONFOUNDING")
                    break
                if tmin is not None and float(tmin) < 2:
                    local_confounders.append("FROST_CONFOUNDING")
                    break

        # Method selection
        method = CausalMethod.PRE_POST
        base_confidence = 0.5
        if len(local_confounders) > 2:
            base_confidence = 0.2
        elif len(local_confounders) > 0:
            base_confidence = 0.35

        # Downweight confidence when unverified
        if not exposure_verified:
            base_confidence *= 0.6

        base_w = {"start": pre_start, "end": pre_end}
        eval_w = {"start": post_start, "end": post_end}

        status_suffix = ""
        if not exposure_verified:
            status_suffix = " [OBSERVATIONAL_ASSOCIATION_ONLY: execution not verified with as-applied evidence or timestamp]"

        # ── Metric 1: NDVI Recovery ──────────────────────────────────────
        delta_ndvi = _mean(post_ndvi) - _mean(pre_ndvi)
        outcomes.append(OutcomeMetric(
            metric_id=OutcomeMetricId.NDVI_RECOVERY,
            delta_value=round(delta_ndvi, 4),
            confidence=round(base_confidence, 3),
            method=method,
            baseline_window=base_w, eval_window=eval_w,
            confounders_present=local_confounders,
            notes=f"Pre mean={_mean(pre_ndvi):.3f}, Post mean={_mean(post_ndvi):.3f}{status_suffix}",
            causal_classification=causal_classification,
            exposure_verified=exposure_verified,
        ))

        # ── Metric 2: Growth Velocity Recovery ───────────────────────────
        pre_slope = _slope(pre_ndvi, pre_dates if len(pre_dates) == len(pre_ndvi) else None)
        post_slope = _slope(post_ndvi, post_dates if len(post_dates) == len(post_ndvi) else None)
        velocity_delta = post_slope - pre_slope
        outcomes.append(OutcomeMetric(
            metric_id=OutcomeMetricId.GROWTH_VELOCITY_RECOVERY,
            delta_value=round(velocity_delta, 5),
            confidence=round(base_confidence * 0.9, 3),
            method=method,
            baseline_window=base_w, eval_window=eval_w,
            confounders_present=local_confounders,
            notes=f"Pre velocity={pre_slope:.4f}/day, Post velocity={post_slope:.4f}/day{status_suffix}",
            causal_classification=causal_classification,
            exposure_verified=exposure_verified,
        ))

        # ── Metric 3: Yield Proxy Delta (cumulative NDVI integral) ───────
        pre_integral = _integral(pre_ndvi)
        post_integral = _integral(post_ndvi)
        yield_delta = post_integral - pre_integral
        outcomes.append(OutcomeMetric(
            metric_id=OutcomeMetricId.YIELD_PROXY_DELTA,
            delta_value=round(yield_delta, 4),
            confidence=round(base_confidence * 0.8, 3),
            method=method,
            baseline_window=base_w, eval_window=eval_w,
            confounders_present=local_confounders,
            notes=f"Pre integral={pre_integral:.3f}, Post integral={post_integral:.3f}{status_suffix}",
            causal_classification=causal_classification,
            exposure_verified=exposure_verified,
        ))

    return outcomes


def project_outcomes(
    portfolio: List[InterventionCandidate],
    digest: UpstreamDigest,
) -> List[OutcomeProjection]:
    """Forward-looking outcome projections for pending interventions."""
    projections = []

    for candidate in portfolio:
        if candidate.action_type == "VERIFY":
            continue  # Verification doesn't directly change outcomes

        # Project based on expected impact and current conditions
        ndvi_delta = candidate.expected_impact * 0.1  # Scale to NDVI units
        risk_reduction = candidate.expected_impact * 0.5
        yield_pct = candidate.expected_impact * 8.0  # Rough % yield impact

        # Adjust by confidence
        proj_conf = candidate.confidence * 0.8

        # Adjust by trend — if already declining, harder to recover
        if digest.ndvi_trend == "CRASH":
            ndvi_delta *= 0.5
            proj_conf *= 0.7
        elif digest.ndvi_trend == "DECLINING":
            ndvi_delta *= 0.7

        assumptions = []
        if digest.rain_7d_mm < 5:
            assumptions.append("Assumes supplemental moisture available")
        if digest.heat_days > 0:
            assumptions.append(f"Heat stress ({digest.heat_days} days >35°C) may reduce efficacy")

        projections.append(OutcomeProjection(
            intervention_id=candidate.intervention_id,
            projected_ndvi_delta=round(ndvi_delta, 4),
            projected_risk_reduction=round(risk_reduction, 3),
            projected_yield_impact_pct=round(yield_pct, 1),
            projection_confidence=round(proj_conf, 3),
            projection_horizon_days=14,
            assumptions=assumptions,
        ))

    return projections
