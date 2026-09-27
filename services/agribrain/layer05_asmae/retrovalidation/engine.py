"""
V79A Phase 6: Retrovalidation engine with real holdout scoring.

Replaces proxy scoring with leave-one-out holdout validation.

Status values:
  - success_with_holdouts: real held-out raster scenes were evaluated
  - insufficient_for_holdout: < 2 scenes available
  - no_holdout_possible: no scenes at all
  - degraded_mean_only_holdout: only mean-only scenes (cannot be success_with_holdouts)

6-component scoring formula (weights unchanged):
  retro = 0.30*future + 0.20*radiometric + 0.15*temporal + 0.15*spatial
        + 0.10*causal + 0.10*calibration

Hard rule: success_with_holdouts requires at least one real held-out
scene with pixel/raster observations.
"""

from __future__ import annotations

import logging
import math
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..config import (
    RETRO_SCORE_1M_ADVISORY,
    RETRO_SCORE_1M_CERTIFIED,
    RETRO_WEIGHTS,
)

logger = logging.getLogger(__name__)


def _to_utc_datetime(val: Any) -> Optional[datetime]:
    """Parse any datetime representation into a timezone-aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return None
        try:
            dt = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(val_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass
    return None


def _rebuild_fold_geometry(
    training_scenes: List[Any],
    holdout_scene: Any,
    resolution_m: int,
    geometry_hash: str,
    polygon_geojson: Optional[Dict[str, Any]] = None,
    row_direction_deg: float = 0.0,
) -> tuple:
    from ..chain_integrity import assert_scene_operator_binding
    from ..geometry.coregistration import (
        coregister_scene_to_reference, coregister_stack,
    )
    from ..geometry.operator_builder import (
        build_observation_operator, build_operators_for_stack,
    )
    from ..geometry.spatial_reference import (
        pixel_size_m, target_grid_from_reference,
    )
    from ..graph.microzone_graph import build_microzone_graph

    if not training_scenes:
        raise ValueError('empty_training_scene_set')
    reference = training_scenes[0]
    target_grid = target_grid_from_reference(reference, resolution_m)
    training_coregistration = coregister_stack(training_scenes)
    training_operators = build_operators_for_stack(
        training_scenes,
        resolution_m,
        coreg_results=training_coregistration,
    )
    assert_scene_operator_binding(
        training_scenes, training_operators, stage_name='retro_refit',
    )
    holdout_coregistration = coregister_scene_to_reference(
        holdout_scene, reference,
    )
    holdout_operator = build_observation_operator(
        scene=holdout_scene,
        candidate_resolution_m=resolution_m,
        coreg=holdout_coregistration,
        target_grid=target_grid,
    )
    polygon_points = None
    if isinstance(polygon_geojson, dict):
        try:
            from rasterio.warp import transform_geom
            from ..geometry.spatial_reference import coerce_polygon_geojson

            geometry = coerce_polygon_geojson(polygon_geojson)
            projected = transform_geom(
                'EPSG:4326', target_grid.crs, geometry, precision=9,
            )
            coordinates = projected.get('coordinates', [])
            if projected.get('type') == 'MultiPolygon':
                coordinates = coordinates[0] if coordinates else []
            ring = coordinates[0] if coordinates else []
            polygon_points = [
                (float(point[0]), float(point[1]))
                for point in ring if len(point) >= 2
            ]
        except Exception as exc:
            raise ValueError(f'retro_polygon_projection_failed:{exc}') from exc
    graph = build_microzone_graph(
        resolution_m=resolution_m,
        n_pixel_rows=int(reference.height),
        n_pixel_cols=int(reference.width),
        pixel_size_m=pixel_size_m(reference),
        target_origin_x=target_grid.origin_x,
        target_origin_y=target_grid.origin_y,
        geometry_hash=geometry_hash,
        polygon_points=polygon_points,
        row_direction_deg=float(row_direction_deg or 0.0),
        crs=target_grid.crs,
        n_zone_rows=target_grid.n_rows,
        n_zone_cols=target_grid.n_cols,
    )
    if graph.node_count != training_operators[0].H_matrix.shape[1]:
        raise ValueError('retro_graph_operator_node_mismatch')
    return training_operators, holdout_operator, graph, {
        'reference_scene_id': str(getattr(reference, 'scene_id', '')),
        'training_operator_ids': [operator.operator_id for operator in training_operators],
        'holdout_operator_id': holdout_operator.operator_id,
        'target_grid': {
            'crs': target_grid.crs,
            'transform': target_grid.transform_gdal,
            'rows': target_grid.n_rows,
            'cols': target_grid.n_cols,
        },
    }


def run_retrovalidation(
    state_result: Dict[str, Any],
    scenes: List[Any],
    operators: List[Any],
    graph: Any,
    priors: Dict[str, Any],
    consistency_result: Optional[Dict[str, Any]] = None,
    causal_result: Optional[Dict[str, Any]] = None,
    expected_resolution_m: Optional[int] = None,
    evidence_context: Optional[Dict[str, Any]] = None,
    refit_identity: Optional[Dict[str, str]] = None,
    deadline_check=None,
) -> Dict[str, Any]:
    """Run retrovalidation with real holdout scoring.

    Args:
        state_result: Output from EnKF (raster_maps, uncertainty_maps).
        scenes: Full scene list.
        operators: Observation operators.
        graph: Microzone graph.
        priors: Layer priors.
        consistency_result: From V75 radiometric check.
        causal_result: From V77 causal tracking.
        expected_resolution_m: V922 — if set, assert all operators match.

    Returns:
        Dict with status, per-microzone retro_scores, aggregate, components.
    """
    # V922: Chain integrity assertion — operators must match resolution
    if expected_resolution_m is not None and operators:
        from ..chain_integrity import assert_operators_match_resolution
        assert_operators_match_resolution(
            operators, expected_resolution_m, stage_name="retrovalidation",
        )

    from .holdout_split import leave_one_out_holdout
    from .future_projection import predict_held_out_scene
    from .calibration_score import compute_calibration_score

    means = state_result.get("raster_maps", {})
    sigmas = state_result.get("uncertainty_maps", {})
    n_scenes = state_result.get("n_scenes_processed", 0)

    # ── Determine holdout feasibility ───────────────────────────────
    if not scenes or n_scenes == 0:
        return _no_holdout_result("no_holdout_possible", "no scenes available")

    folds = leave_one_out_holdout(scenes)

    if not folds:
        if len(scenes) < 2:
            return _no_holdout_result(
                "insufficient_for_holdout",
                f"only {len(scenes)} scene(s), need >= 2",
            )
        return _no_holdout_result(
            "degraded_mean_only_holdout",
            "no causal production-authority raster fold qualifies for holdout",
        )

    try:
        max_retro_folds = int(os.environ.get("ASMAE_MAX_RETRO_FOLDS", "2"))
    except (ValueError, TypeError):
        max_retro_folds = 2
    if max_retro_folds > 0 and len(folds) > max_retro_folds:
        # Multi-sensor stratified selection: ensure each sensor family (e.g. S2, S1)
        # represented in the stack has at least one holdout fold so that domain-specific
        # physical experts (optical_physiology, sar_structure) can receive holdout scores.
        sensor_to_folds: Dict[str, List[int]] = {}
        for idx, (trn, hld) in enumerate(folds):
            sens = str(getattr(hld, "sensor", "unknown"))
            sensor_to_folds.setdefault(sens, []).append(idx)

        selected_indices = set()
        # First pass: pick the latest fold for each distinct sensor
        for sens, f_indices in sensor_to_folds.items():
            selected_indices.add(f_indices[-1])

        # If we selected more than max_retro_folds (e.g. >2 sensors), truncate to latest
        if len(selected_indices) > max_retro_folds:
            selected_indices = set(sorted(selected_indices)[-max_retro_folds:])
        else:
            # Fill remaining budget with latest available folds
            remaining = [i for i in range(len(folds)) if i not in selected_indices]
            needed = max_retro_folds - len(selected_indices)
            if needed > 0 and remaining:
                selected_indices.update(remaining[-needed:])

        folds = [folds[i] for i in sorted(selected_indices)]

    # ── Component 1: true leave-one-date-out refitting ──────────────
    holdout_errors: List[Dict[str, float]] = []
    holdout_mean_errors: List[float] = []
    prospective_mean_errors: List[float] = []
    retrospective_mean_errors: List[float] = []
    refit_folds: List[Dict[str, Any]] = []

    from ..assimilation.filter import run_enkf
    from ..deterministic import make_rng
    identity = refit_identity or {}
    resolution_m = int(expected_resolution_m or 10)

    for fold_index, (training_scenes, holdout_scene) in enumerate(folds):
        if deadline_check is not None:
            deadline_check()
        holdout_op = _find_operator_for_scene(holdout_scene, operators)
        training_operators = _operators_for_scenes(training_scenes, operators)
        holdout_id = str(getattr(holdout_scene, "scene_id", f"fold_{fold_index}"))
        fold_proof = {
            "holdout_scene_id": holdout_id,
            "training_scene_ids": [str(getattr(scene, "scene_id", "")) for scene in training_scenes],
            "held_out_scene_removed": all(
                str(getattr(scene, "scene_id", "")) != holdout_id for scene in training_scenes
            ),
            "operators_rebuilt_for_training_subset": False,
            "assimilation_rerun": False,
        }
        try:
            training_operators, holdout_op, fold_graph, geometry_proof = _rebuild_fold_geometry(
                training_scenes,
                holdout_scene,
                resolution_m,
                identity.get('geometry_hash', 'retro'),
                (evidence_context or {}).get('polygon_geojson'),
                (evidence_context or {}).get('crop_context', {}).get(
                    'row_direction_deg', 0.0,
                ),
            )
            fold_proof['geometry_rebuild'] = geometry_proof
            fold_proof['operators_rebuilt_for_training_subset'] = True
        except Exception as exc:
            fold_proof['status'] = 'refit_geometry_rebuild_failed'
            fold_proof['failure_reason'] = str(exc)
            refit_folds.append(fold_proof)
            continue
        if not training_scenes or len(training_operators) != len(training_scenes):
            fold_proof["status"] = "refit_operator_subset_incomplete"
            refit_folds.append(fold_proof)
            continue

        initial_posterior = {}
        asmae_input = (evidence_context or {}).get('asmae_input')
        if asmae_input is not None:
            try:
                from ..resilient_posterior import estimate_resilient_plot_posterior

                training_times = [
                    getattr(scene, 'acquisition_time', None) for scene in training_scenes
                    if getattr(scene, 'acquisition_time', None) is not None
                ]
                cutoff = min(training_times) - timedelta(microseconds=1)
                frozen_initialization = estimate_resilient_plot_posterior(
                    asmae_input, as_of=cutoff,
                )
                initial_posterior = frozen_initialization.get('plot_level_posterior', {})
                fold_proof['initialization_as_of'] = str(cutoff)
                fold_proof['initialization_frozen'] = True
            except Exception as exc:
                fold_proof['initialization_frozen'] = False
                fold_proof['initialization_failure'] = str(exc)
        fold_state = run_enkf(
            scenes=training_scenes,
            operators=training_operators,
            graph=fold_graph,
            priors=_freeze_priors(priors, fold_proof.get('initialization_as_of')),
            resolution_m=resolution_m,
            mode="shadow",
            crop_context=(evidence_context or {}).get("crop_context", {}),
            rng=make_rng(
                run_id=f"{identity.get('run_id', 'retro')}:{holdout_id}",
                plot_id=identity.get("plot_id", "retro"),
                geometry_hash=identity.get("geometry_hash", "retro"),
            ),
            expected_resolution_m=resolution_m,
            weather_daily_series=_training_weather(
                (evidence_context or {}).get("weather_daily_series", {}),
                training_scenes,
                holdout_scene,
            ),
            soil_context=(evidence_context or {}).get("soil_context", {}),
            management_events=_training_management_events(
                (evidence_context or {}).get("management_events", []),
                training_scenes,
                holdout_scene,
            ),
            initial_posterior=initial_posterior,
            deadline_check=deadline_check,
        )
        if deadline_check is not None:
            deadline_check()
        training_state = fold_state.get("raster_maps", {})
        fold_proof["assimilation_rerun"] = bool(training_state)
        fold_proof["training_update_count"] = sum(
            1 for report in fold_state.get("update_report", [])
            if isinstance(report, dict) and report.get("update_applied") is True
        )
        from .future_projection import forecast_held_out_scene, predict_held_out_scene

        # Compute forecast horizon delta_days between last training scene and holdout scene
        delta_days = 1.0
        if training_scenes:
            t_train = getattr(training_scenes[-1], "acquisition_time", None)
            t_holdout = getattr(holdout_scene, "acquisition_time", None)
            if hasattr(t_train, "timestamp") and hasattr(t_holdout, "timestamp"):
                delta_days = max(0.0, (t_holdout.timestamp() - t_train.timestamp()) / 86400.0)
            elif isinstance(t_train, str) and isinstance(t_holdout, str):
                try:
                    from datetime import datetime as dt_cls
                    dt_train = dt_cls.fromisoformat(t_train.replace("Z", "+00:00"))
                    dt_holdout = dt_cls.fromisoformat(t_holdout.replace("Z", "+00:00"))
                    delta_days = max(0.0, (dt_holdout.timestamp() - dt_train.timestamp()) / 86400.0)
                except Exception:
                    pass

        # Weather forcing available at forecast issuance
        holdout_time = getattr(holdout_scene, "acquisition_time", None)
        holdout_date_str = holdout_time.strftime("%Y-%m-%d") if hasattr(holdout_time, "strftime") else (str(holdout_time)[:10] if holdout_time else "")

        t_train_dt = getattr(training_scenes[-1], "acquisition_time", None) if training_scenes else None
        t_holdout_dt = holdout_time if isinstance(holdout_time, datetime) else None

        raw_weather_daily = (evidence_context or {}).get("weather_daily_series", {})
        archived_forecast = (
            (evidence_context or {}).get("weather_forecast")
            or (evidence_context or {}).get("weather_forecast_series")
            or {}
        )
        raw_mgmt_events = (evidence_context or {}).get("management_events", [])

        training_weather_series = _training_weather(
            raw_weather_daily,
            training_scenes,
            holdout_scene,
        )

        # Distinguish archived issuance-time forecast vs declared weather persistence
        # vs retrospective historical reanalysis forcing (R2 §§54 and 86.2)
        interval_weather_series = {}
        forecast_forcing_source = "declared_weather_persistence"
        is_issuance_forecast = True
        forcing_provenance = "issuance_weather_persistence"

        if archived_forecast and isinstance(archived_forecast, dict):
            # Verify issuance cutoff: forecast must have been issued on or before t_train_dt
            raw_issued = (
                archived_forecast.get("issued_at")
                or archived_forecast.get("issuance_time")
                or archived_forecast.get("issue_date")
                or archived_forecast.get("forecast_issued_at")
                or (archived_forecast.get("metadata", {}) if isinstance(archived_forecast.get("metadata"), dict) else {}).get("issued_at")
            )
            issued_dt = _to_utc_datetime(raw_issued)
            train_utc = _to_utc_datetime(t_train_dt)

            interval_weather_series = dict(archived_forecast)
            # Require valid issuance provenance and compare complete timezone-aware timestamps
            if issued_dt is not None and train_utc is not None and issued_dt <= train_utc:
                forecast_forcing_source = "archived_issuance_forecast"
                is_issuance_forecast = True
                forcing_provenance = "archived_issuance_forecast"
            else:
                forecast_forcing_source = "retrieved_historical_forcing"
                is_issuance_forecast = False
                forcing_provenance = "post_cutoff_or_unverified_forecast_reanalysis"

        elif raw_weather_daily and t_train_dt and t_holdout_dt:
            # Check if interval from training day through holdout day consumes observed weather
            d_curr = t_train_dt.date()
            consumed_post_train_obs = False
            last_known_weather = next(iter(reversed(list(training_weather_series.values()))), {}) if training_weather_series else {}

            while d_curr <= t_holdout_dt.date():
                ds = d_curr.strftime("%Y-%m-%d")
                if ds in raw_weather_daily:
                    interval_weather_series[ds] = raw_weather_daily[ds]
                    if d_curr > t_train_dt.date():
                        consumed_post_train_obs = True
                else:
                    # Impute missing day using persistence from training series, NOT future endpoint
                    interval_weather_series[ds] = last_known_weather
                d_curr += timedelta(days=1)

            if consumed_post_train_obs:
                # Consuming ANY post-training observed weather makes this a retrospective hindcast
                forecast_forcing_source = "retrieved_historical_forcing"
                is_issuance_forecast = False
                forcing_provenance = "hindcast_reanalysis_observed_forcing"
            else:
                forecast_forcing_source = "declared_weather_persistence"
                is_issuance_forecast = True
                forcing_provenance = "issuance_weather_persistence"

        # Explicit declared weather-persistence fallback if no forecast was archived
        if not interval_weather_series:
            forecast_forcing_source = "declared_weather_persistence"
            is_issuance_forecast = True
            forcing_provenance = "issuance_weather_persistence"
            last_known_weather = next(iter(reversed(list(training_weather_series.values()))), {}) if training_weather_series else {}
            if t_train_dt and t_holdout_dt:
                d_curr = t_train_dt.date()
                while d_curr <= t_holdout_dt.date():
                    interval_weather_series[d_curr.strftime("%Y-%m-%d")] = last_known_weather
                    d_curr += timedelta(days=1)
            else:
                interval_weather_series[holdout_date_str] = last_known_weather

        weather_day = interval_weather_series.get(holdout_date_str) or next(iter(reversed(list(interval_weather_series.values()))), {})

        # Interval management events
        # Interventions known at issuance vs subsequently observed interventions (R2 §§54 and 86.2)
        train_utc = _to_utc_datetime(t_train_dt)
        condition_on_interventions = bool(
            (evidence_context or {}).get("condition_on_observed_interventions")
            or (evidence_context or {}).get("condition_on_interventions")
        )
        interval_mgmt_events = []
        consumed_post_issuance_interventions = False

        for ev in raw_mgmt_events or []:
            if isinstance(ev, dict):
                raw_d = str(ev.get("effective_start") or ev.get("timestamp") or ev.get("date") or "")[:10]
                in_interval = False
                if t_train_dt and t_holdout_dt:
                    train_str = t_train_dt.strftime("%Y-%m-%d")
                    holdout_str = t_holdout_dt.strftime("%Y-%m-%d")
                    if train_str <= raw_d <= holdout_str:
                        in_interval = True
                elif raw_d == holdout_date_str:
                    in_interval = True

                if not in_interval:
                    continue

                raw_rec = (
                    ev.get("recorded_at")
                    or ev.get("created_at")
                    or ev.get("logged_at")
                    or ev.get("issued_at")
                    or ev.get("known_at")
                    or ev.get("record_time")
                    or (ev.get("metadata", {}) if isinstance(ev.get("metadata"), dict) else {}).get("recorded_at")
                    or (ev.get("metadata", {}) if isinstance(ev.get("metadata"), dict) else {}).get("created_at")
                )
                rec_dt = _to_utc_datetime(raw_rec)

                # Check when this event became known relative to forecast origin (train_utc)
                if rec_dt is not None and train_utc is not None and rec_dt > train_utc:
                    # Learned after issuance!
                    if condition_on_interventions:
                        # Deliberately conditioned on subsequently observed interventions
                        interval_mgmt_events.append(ev)
                        consumed_post_issuance_interventions = True
                    else:
                        # Prospective issuance forecast: exclude interventions learned after issuance
                        continue
                else:
                    # Known on or before issuance (or no post-issuance recording timestamp)
                    interval_mgmt_events.append(ev)

        if consumed_post_issuance_interventions:
            forecast_forcing_source = "retrieved_historical_forcing"
            is_issuance_forecast = False
            forcing_provenance = "intervention_conditioned_reconstruction"

        forecast_rng = make_rng(
            run_id=f"{identity.get('run_id', 'retro')}:forecast:{holdout_id}",
            plot_id=identity.get("plot_id", "retro"),
            geometry_hash=identity.get("geometry_hash", "retro"),
        )

        pred_result = forecast_held_out_scene(
            training_state=training_state,
            holdout_scene=holdout_scene,
            operator=holdout_op,
            weather_day=weather_day,
            crop_context=(evidence_context or {}).get("crop_context", {}),
            soil_context=(evidence_context or {}).get("soil_context", {}),
            delta_days=delta_days,
            rng=forecast_rng,
            previous_time=t_train_dt,
            current_time=t_holdout_dt,
            weather_daily_series=interval_weather_series,
            management_events=interval_mgmt_events,
        )
        fold_proof["forecast_forcing_source"] = forecast_forcing_source
        fold_proof["is_issuance_forecast"] = is_issuance_forecast
        fold_proof["forcing_provenance"] = forcing_provenance
        fold_proof["status"] = pred_result.get("status", "unknown")
        fold_proof["prediction_mode"] = pred_result.get("prediction_mode", "none")
        fold_proof["mean_error"] = pred_result.get("mean_error")
        fold_proof["prospective_forecast_rmse"] = pred_result.get("prospective_forecast_rmse") if is_issuance_forecast else None
        fold_proof["retrospective_reconstruction_rmse"] = pred_result.get("prospective_forecast_rmse") if not is_issuance_forecast else None
        fold_proof["persistence_rmse"] = pred_result.get("persistence_rmse")
        fold_proof["forecast_skill_score"] = pred_result.get("forecast_skill_score")
        fold_proof["per_microzone_error"] = pred_result.get("per_microzone_error", {})
        fold_proof["forecast_state"] = pred_result.get("forecast_state")
        fold_proof["training_state"] = training_state
        fold_proof['training_sigmas'] = fold_state.get('uncertainty_maps', {})
        fold_proof['training_timeline'] = fold_state.get('state_timeline', [])
        fold_proof['training_graph'] = fold_graph
        fold_proof["training_scenes"] = training_scenes
        fold_proof["holdout_scene"] = holdout_scene
        fold_proof["holdout_operator"] = holdout_op
        refit_folds.append(fold_proof)
        if (
            pred_result.get('status') == 'predicted'
            and isinstance(pred_result.get('mean_error'), (int, float))
            and pred_result.get('errors')
        ):
            holdout_errors.append(dict(pred_result['errors']))
            err_val = float(pred_result['mean_error'])
            holdout_mean_errors.append(err_val)
            if is_issuance_forecast:
                prospective_mean_errors.append(err_val)
            else:
                retrospective_mean_errors.append(err_val)

    successful_refits = [
        fold for fold in refit_folds
        if fold.get('assimilation_rerun') and fold.get('status') == 'predicted'
        and isinstance(fold.get('mean_error'), (int, float))
    ]
    if not successful_refits:
        result = _no_holdout_result(
            "refit_failed",
            "no holdout fold completed an independent training-subset assimilation",
        )
        result["refit_proof"] = [_public_refit_proof(fold) for fold in refit_folds]
        return result

    if prospective_mean_errors:
        avg_prospective_error = sum(prospective_mean_errors) / len(prospective_mean_errors)
        future_score = max(0.0, min(1.0, 1.0 - avg_prospective_error))
    else:
        # Zero prospective folds evaluated: future forecast skill is strictly 0.0
        future_score = 0.0

    if retrospective_mean_errors:
        avg_reconstruction_error = sum(retrospective_mean_errors) / len(retrospective_mean_errors)
        reconstruction_score = max(0.0, min(1.0, 1.0 - avg_reconstruction_error))
    else:
        reconstruction_score = 0.0

    # ── Component 2: Radiometric (from V75 result, not internal) ────
    # V922.2A: full credit only when all observations used true Hₜ per-pixel
    # and no shape/scalar/resampling fallback occurred.
    if consistency_result:
        overall_pass = consistency_result.get("overall_pass", False)
        full_credit = consistency_result.get("full_radiometric_credit_allowed", False)
        rad_mode = consistency_result.get("radiometric_mode", "proxy_average")

        if overall_pass:
            if full_credit:
                radiometric_score = 1.0
            elif rad_mode in ("ht_per_pixel", "mixed_ht_modes"):
                # Hₜ was used but with fallbacks — partial credit
                radiometric_score = 0.6
            else:
                radiometric_score = 0.3
        else:
            radiometric_score = 0.0
    else:
        radiometric_score = 0.0

    # ── Component 3: Temporal plausibility ──────────────────────────
    temporal_score = sum(
        _compute_temporal_plausibility(fold.get('training_timeline', []))
        for fold in successful_refits
    ) / len(successful_refits)

    # ── Component 4: Spatial agreement ─────────────────────────────
    spatial_score = sum(
        _compute_spatial_agreement(
            fold.get('training_state', {}), fold.get('training_graph'),
        )
        for fold in successful_refits
    ) / len(successful_refits)

    # ── Component 5: Causal support ────────────────────────────────
    if causal_result:
        hypotheses = causal_result.get("hypotheses", {})
        if hypotheses:
            n_supported = sum(
                1 for h in hypotheses.values()
                if isinstance(h, dict) and h.get("status") not in ("unknown",)
            )
            causal_score = n_supported / max(len(hypotheses), 1)
        else:
            causal_score = 0.0
    else:
        causal_score = 0.0

    # ── Component 6: Calibration (holdout-based) ───────────────────
    fold_sigmas = {
        f'{fold_index}:{node_id}': sigma
        for fold_index, fold in enumerate(successful_refits)
        for node_id, sigma in dict(fold.get('training_sigmas', {}) or {}).items()
    }
    calibration_score = compute_calibration_score(holdout_errors, fold_sigmas)

    # ── Weighted aggregate ─────────────────────────────────────────
    w = RETRO_WEIGHTS
    target_future_component = future_score if prospective_mean_errors else (reconstruction_score if retrospective_mean_errors else 0.0)
    retro_score = (
        w["future"] * target_future_component +
        w["radiometric"] * radiometric_score +
        w["temporal"] * temporal_score +
        w["spatial"] * spatial_score +
        w["causal"] * causal_score +
        w["calibration"] * calibration_score
    )
    retro_score = round(retro_score, 4)

    # ── Per-microzone retro scores ─────────────────────────────────
    per_microzone: Dict[str, Dict[str, Any]] = {}
    node_prospective_errors: Dict[str, List[float]] = {}
    node_retrospective_errors: Dict[str, List[float]] = {}
    for fold in successful_refits:
        is_prospective_fold = bool(fold.get("is_issuance_forecast", False))
        pm_err = fold.get("per_microzone_error") or {}
        for nid, err in pm_err.items():
            if isinstance(err, (int, float)) and math.isfinite(float(err)):
                if is_prospective_fold:
                    node_prospective_errors.setdefault(nid, []).append(float(err))
                else:
                    node_retrospective_errors.setdefault(nid, []).append(float(err))

    for nid in means:
        if prospective_mean_errors:
            if nid in node_prospective_errors and node_prospective_errors[nid]:
                mz_avg_err = sum(node_prospective_errors[nid]) / len(node_prospective_errors[nid])
                mz_future = max(0.0, min(1.0, 1.0 - mz_avg_err))
            else:
                mz_future = future_score
        else:
            mz_future = 0.0

        if retrospective_mean_errors:
            if nid in node_retrospective_errors and node_retrospective_errors[nid]:
                mz_retro_err = sum(node_retrospective_errors[nid]) / len(node_retrospective_errors[nid])
                mz_reconstruction = max(0.0, min(1.0, 1.0 - mz_retro_err))
            else:
                mz_reconstruction = reconstruction_score
        else:
            mz_reconstruction = 0.0

        target_mz_future_component = mz_future if prospective_mean_errors else (mz_reconstruction if retrospective_mean_errors else 0.0)

        mz_retro = (
            w["future"] * target_mz_future_component +
            w["radiometric"] * radiometric_score +
            w["temporal"] * temporal_score +
            w["spatial"] * spatial_score +
            w["causal"] * causal_score +
            w["calibration"] * calibration_score
        )
        per_microzone[nid] = {
            "retro_score": round(mz_retro, 4),
            "future": round(mz_future, 4),
            "reconstruction": round(mz_reconstruction, 4),
            "radiometric": round(radiometric_score, 4),
            "temporal": round(temporal_score, 4),
            "spatial": round(spatial_score, 4),
            "causal": round(causal_score, 4),
            "calibration": round(calibration_score, 4),
        }

    # ── V79B: Produce expert holdout errors for BMA ────────────────
    expert_holdout_errors = _compute_expert_holdout_errors(
        successful_refits, evidence_context or {},
    )

    # ── V79B: Produce holdout observation targets for BMA ──────────
    holdout_targets = _compute_holdout_observation_targets(
        means, folds, operators,
    )

    # ── 1m thresholds ──────────────────────────────────────────────
    tier = "none"
    if retro_score >= RETRO_SCORE_1M_CERTIFIED:
        tier = "certified_display"
    elif retro_score >= RETRO_SCORE_1M_ADVISORY:
        tier = "advisory"

    return {
        "status": "success_with_holdouts",
        "n_holdout_folds": len(successful_refits),
        "n_real_holdout_scenes": len(successful_refits),
        "aggregate": {
            "mean_retro_score": retro_score,
            "components": {
                "future_prediction": round(future_score, 4),
                "retrospective_reconstruction": round(reconstruction_score, 4) if retrospective_mean_errors else None,
                "radiometric": round(radiometric_score, 4),
                "temporal_plausibility": round(temporal_score, 4),
                "spatial_agreement": round(spatial_score, 4),
                "causal_support": round(causal_score, 4),
                "calibration": round(calibration_score, 4),
            },
            "prospective_forecast_score": round(future_score, 4) if prospective_mean_errors else None,
            "retrospective_reconstruction_score": round(reconstruction_score, 4) if retrospective_mean_errors else None,
            "n_prospective_folds": len(prospective_mean_errors),
            "n_retrospective_folds": len(retrospective_mean_errors),
            "weights": w,
        },
        "per_microzone": per_microzone,
        "tier_1m": tier,
        "mean_retro_score": retro_score,
        "expert_holdout_errors": expert_holdout_errors,  # V79B: for BMA
        "holdout_observation_targets": holdout_targets,   # V79B: for BMA
        "retrovalidation_method": "leave_one_date_out_complete_training_only_refit",
        "refit_proof": [_public_refit_proof(fold) for fold in refit_folds],
        "successful_refit_count": len(successful_refits),
    }


def _no_holdout_result(status: str, reason: str) -> Dict[str, Any]:
    """Return a result when holdout is not possible."""
    return {
        "status": status,
        "reason": reason,
        "n_holdout_folds": 0,
        "n_real_holdout_scenes": 0,
        "aggregate": {
            "mean_retro_score": 0.0,
            "components": {
                "future_prediction": 0.0,
                "radiometric": 0.0,
                "temporal_plausibility": 0.0,
                "spatial_agreement": 0.0,
                "causal_support": 0.0,
                "calibration": 0.0,
            },
        },
        "per_microzone": {},
        "tier_1m": "none",
        "mean_retro_score": 0.0,
    }


def _compute_temporal_plausibility(timeline: List[Dict[str, Any]]) -> float:
    """Score elapsed-time-normalized state changes across training events."""
    if not timeline or len(timeline) < 2:
        return 0.5
    rates: List[float] = []
    previous = timeline[0]
    for current in timeline[1:]:
        delta_days = float(current.get('elapsed_days_since_previous_scene', 0.0) or 0.0)
        if delta_days <= 0.0:
            previous = current
            continue
        before = previous.get('means', {}) or {}
        after = current.get('means', {}) or {}
        for node_id in set(before) & set(after):
            left, right = before[node_id], after[node_id]
            if isinstance(left, list) and isinstance(right, list):
                for state_index in (0, 3, 4, 5):
                    if state_index < len(left) and state_index < len(right):
                        rates.append(abs(float(right[state_index]) - float(left[state_index])) / delta_days)
        previous = current
    if not rates:
        return 0.0
    rates.sort()
    p95 = rates[min(len(rates) - 1, int(0.95 * len(rates)))]
    if p95 < 0.03:
        return 0.95
    elif p95 < 0.08:
        return 0.7
    elif p95 < 0.15:
        return 0.4
    return 0.2


def _compute_spatial_agreement(means: Dict[str, Any], graph: Any) -> float:
    """Check neighbor consistency across microzone graph."""
    if not means:
        return 0.0

    # Simple: compute mean pairwise difference for vigor
    vigor = {}
    for nid, state in means.items():
        if isinstance(state, list) and len(state) > 0:
            vigor[nid] = state[0]

    if len(vigor) < 2:
        return 0.5

    pairwise_diffs = []
    edges = graph.edges() if graph is not None and hasattr(graph, 'edges') else []
    for edge in edges:
        if edge.source in vigor and edge.target in vigor:
            pairwise_diffs.append(abs(vigor[edge.source] - vigor[edge.target]))

    if not pairwise_diffs:
        return 0.5

    mean_diff = sum(pairwise_diffs) / len(pairwise_diffs)
    if mean_diff < 0.05:
        return 0.95
    elif mean_diff < 0.15:
        return 0.7
    elif mean_diff < 0.3:
        return 0.4
    return 0.2


def _find_operator_for_scene(scene: Any, operators: list) -> Optional[Any]:
    """Find only the operator immutably bound to this exact scene."""
    if not operators:
        return None
    scene_id = getattr(scene, "scene_id", None)
    if scene_id:
        for op in operators:
            if getattr(op, "scene_id", None) == scene_id:
                return op
    return None


def _operators_for_scenes(scenes: List[Any], operators: List[Any]) -> List[Any]:
    """Return an exact scene/operator subset; never substitute a holdout operator."""
    by_scene = {
        str(getattr(operator, "scene_id", "")): operator
        for operator in operators or []
        if getattr(operator, "scene_id", None)
    }
    result = []
    for scene in scenes:
        operator = by_scene.get(str(getattr(scene, "scene_id", "")))
        if operator is not None:
            result.append(operator)
    return result


def _public_refit_proof(fold: Dict[str, Any]) -> Dict[str, Any]:
    """Remove runtime arrays/objects while retaining independently auditable proof."""
    return {
        key: value for key, value in fold.items()
        if key not in {
            "training_state", "training_sigmas", "training_graph",
            "training_timeline",
            "training_scenes", "holdout_scene", "holdout_operator",
        }
    }


def _freeze_priors(priors: Dict[str, Any], cutoff: Any) -> Dict[str, Any]:
    """Retain only priors demonstrably available before initialization."""
    import copy
    from datetime import datetime

    try:
        cutoff_dt = datetime.fromisoformat(str(cutoff).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        cutoff_dt = None
    frozen: Dict[str, Any] = {}
    for name, prior in dict(priors or {}).items():
        if not isinstance(prior, dict):
            continue
        raw_stamp = prior.get('source_timestamp') or prior.get('generated_at')
        if cutoff_dt is not None and raw_stamp:
            try:
                stamp = datetime.fromisoformat(str(raw_stamp).replace('Z', '+00:00'))
                if stamp > cutoff_dt:
                    continue
            except ValueError:
                continue
        frozen[name] = copy.deepcopy(prior)
    return frozen


def _training_weather(
    weather: Any,
    scenes: List[Any],
    holdout_scene: Any,
) -> Dict[str, Any]:
    if not isinstance(weather, dict):
        return {}
    times = [
        scene.acquisition_time
        for scene in scenes
        if getattr(scene, 'acquisition_time', None) is not None
    ]
    if not times:
        return {}
    start_day = min(times).date().isoformat()
    end_day = max(times).date().isoformat()
    holdout_time = getattr(holdout_scene, 'acquisition_time', None)
    holdout_day = (
        holdout_time.date().isoformat() if holdout_time is not None else None
    )
    return {
        str(day)[:10]: value
        for day, value in weather.items()
        if start_day <= str(day)[:10] <= end_day
        and (holdout_day is None or str(day)[:10] < holdout_day)
    }


def _training_management_events(
    events: Any,
    scenes: List[Any],
    holdout_scene: Any,
) -> List[Dict[str, Any]]:
    training_times = [
        getattr(scene, 'acquisition_time', None) for scene in scenes
        if getattr(scene, 'acquisition_time', None) is not None
    ]
    if not training_times:
        return []
    latest_training = max(training_times)
    latest_day = latest_training.date().isoformat()
    holdout_time = getattr(holdout_scene, 'acquisition_time', None)
    holdout_day = holdout_time.date().isoformat() if holdout_time is not None else None
    result = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        raw_stamp = str(event.get('timestamp') or event.get('date') or '')
        stamp = raw_stamp[:10]
        if not stamp or stamp > latest_day:
            continue
        if holdout_day and stamp >= holdout_day:
            continue
        if len(raw_stamp) > 10 and stamp == latest_day:
            from datetime import datetime
            try:
                event_time = datetime.fromisoformat(
                    raw_stamp.replace('Z', '+00:00'),
                )
                if latest_training.tzinfo is not None and event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=latest_training.tzinfo)
                elif latest_training.tzinfo is None and event_time.tzinfo is not None:
                    event_time = event_time.replace(tzinfo=None)
                if event_time > latest_training:
                    continue
            except ValueError:
                continue
        result.append(dict(event))
    return result


def _compute_expert_holdout_errors(
    refit_folds: List[Dict[str, Any]],
    evidence_context: Dict[str, Any],
) -> Dict[str, float]:
    """Score independent physics experts using only each fold's training evidence."""
    from ..bma.physics_experts import compute_physics_experts
    from .future_projection import predict_held_out_scene

    if not refit_folds:
        return {}

    expert_errors: Dict[str, List[float]] = {}
    for fold in refit_folds:
        training_state = fold.get("training_state", {})
        training_scenes = fold.get("training_scenes", [])
        holdout_scene = fold.get("holdout_scene")
        if not training_state or holdout_scene is None:
            continue
        context = dict(evidence_context)
        context["scenes"] = training_scenes
        expert_specs = compute_physics_experts(training_state, context)
        for expert_name, spec in expert_specs.items():
            prediction = spec.get("predictions", {})
            pred_result = predict_held_out_scene(
                training_state=prediction,
                holdout_scene=holdout_scene,
                operator=fold.get("holdout_operator"),
            )
            if pred_result.get("status") == "predicted" and isinstance(pred_result.get("mean_error"), (int, float)):
                expert_errors.setdefault(expert_name, []).append(float(pred_result["mean_error"]))

    return {
        name: sum(errors) / len(errors)
        for name, errors in expert_errors.items()
        if errors
    }


def _compute_holdout_observation_targets(
    means: Dict[str, Any],
    folds: list,
    operators: list,
) -> Dict[str, List[float]]:
    """V79B: Extract holdout observation targets from held-out scenes.

    These are the real observation-based targets that BMA should weight
    experts against — not the current ASMAE state.

    Returns {microzone_id: [observation-derived target state]}.
    """
    from ..observation.pixel_extraction import extract_pixel_observations

    # Aggregate observations from all holdout scenes
    targets: Dict[str, List[float]] = {}

    for training_scenes, holdout_scene in folds:
        pixel_obs = extract_pixel_observations(holdout_scene)
        if not pixel_obs:
            continue

        # Use observation means as approximate targets per microzone
        for nid in means:
            if nid not in targets:
                if not isinstance(means[nid], list):
                    continue
                base = list(means[nid])
                targets[nid] = base

            # Nudge target toward observed values
            for obs_name, pix_obs in pixel_obs.items():
                # Simple: shift vigor/LAI targets toward observation
                if obs_name == "ndvi":
                    targets[nid][0] = (targets[nid][0] + pix_obs.mean) / 2

    return targets
