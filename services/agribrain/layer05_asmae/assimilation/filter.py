"""
V74 + V79A: Ensemble Kalman Filter (EnKF) for ASMAE state estimation.

V79A changes:
  - Hₜ-aware update when operator.H_matrix is available
  - Proxy mean-level update when H_matrix is None (flagged as proxy)
  - Deterministic seeded RNG (SHA-256, never Python hash())
  - Ensemble-space projection (no dense NxN state covariance)
  - enkf_mode in result: "ht_per_pixel" | "proxy_mean_level"
"""

from __future__ import annotations

import logging
import math
import random
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable
import numpy as np

from ..config import (
    ENSEMBLE_SIZE_CERTIFICATION,
    ENSEMBLE_SIZE_LARGE_PLOT,
    ENSEMBLE_SIZE_OFFLINE,
    ENSEMBLE_SIZE_SHADOW,
    ENSEMBLE_SIZE_STANDARD,
    LARGE_PLOT_MICROZONE_THRESHOLD,
    N_STATES,
    STATE_BOUNDS,
    STATE_NAMES,
)
from ..state.descriptors import STATE_DESCRIPTORS, AssimilationPolicy

logger = logging.getLogger(__name__)


def select_ensemble_size(mode: str, n_microzones: int) -> int:
    """Select ensemble size based on mode and plot size."""
    if mode in ("training_export",):
        return ENSEMBLE_SIZE_OFFLINE
    if mode in ("certification", "calibration", "reference_comparison"):
        return ENSEMBLE_SIZE_CERTIFICATION
    if n_microzones > LARGE_PLOT_MICROZONE_THRESHOLD:
        return ENSEMBLE_SIZE_LARGE_PLOT
    if mode == "shadow":
        return ENSEMBLE_SIZE_SHADOW
    return ENSEMBLE_SIZE_STANDARD


def _weather_for_day(weather_daily_series: Optional[dict], day: str) -> dict:
    # Never borrow a later day's forcing for an earlier process interval.
    if not isinstance(weather_daily_series, dict):
        return {}
    direct = weather_daily_series.get(day)
    if isinstance(direct, dict):
        return direct
    for key, value in weather_daily_series.items():
        if str(key)[:10] == day and isinstance(value, dict):
            return value
    return {}


def _management_events_for_segment(
    management_events: List[Any],
    segment_start: datetime,
    segment_end: datetime,
    process_day: str,
) -> List[Any]:
    """Select each management event for at most one elapsed-time segment."""
    selected: List[Any] = []
    completed_day = segment_end.date() > segment_start.date()
    for event in management_events or []:
        if isinstance(event, dict):
            raw = str(event.get("timestamp") or event.get("date") or "")
        elif hasattr(event, "effective_start"):
            start_val = getattr(event, "effective_start")
            raw = start_val.isoformat() if hasattr(start_val, "isoformat") else str(start_val or "")
        elif hasattr(event, "timestamp") or hasattr(event, "time"):
            raw = str(getattr(event, "timestamp", None) or getattr(event, "time", None) or "")
        else:
            continue
        if not raw:
            continue
        if len(raw) <= 10:
            if completed_day and raw[:10] == process_day:
                selected.append(event)
            continue
        try:
            event_time = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if segment_start.tzinfo is not None and event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=segment_start.tzinfo)
            elif segment_start.tzinfo is None and event_time.tzinfo is not None:
                event_time = event_time.replace(tzinfo=None)
        except ValueError:
            continue
        if segment_start < event_time <= segment_end:
            selected.append(event)
    return selected


def _forecast_elapsed_interval(
    ensemble: Dict[str, List[List[float]]],
    previous_time: Any,
    current_time: Any,
    priors: dict,
    crop_context: dict,
    rng: random.Random,
    scenes: list,
    weather_daily_series: Optional[dict],
    soil_context: dict,
    management_events: List[dict],
) -> Tuple[Dict[str, List[List[float]]], List[Dict[str, Any]]]:
    # Split exact elapsed time at day boundaries so forcing stays as-of.
    if not isinstance(previous_time, datetime) or not isinstance(current_time, datetime):
        return ensemble, []
    if previous_time.tzinfo is None and current_time.tzinfo is not None:
        current_time = current_time.replace(tzinfo=None)
    elif previous_time.tzinfo is not None and current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=previous_time.tzinfo)
    if current_time <= previous_time:
        return ensemble, []
    cursor = previous_time
    segments: List[Dict[str, Any]] = []
    while cursor < current_time:
        next_day = datetime.combine(
            cursor.date() + timedelta(days=1),
            time.min,
            tzinfo=cursor.tzinfo,
        )
        segment_end = min(current_time, next_day)
        delta_days = (segment_end - cursor).total_seconds() / 86400.0
        if delta_days <= 0.0:
            break
        process_day = cursor.date().isoformat()
        weather_day = _weather_for_day(weather_daily_series, process_day)
        segment_events = _management_events_for_segment(
            management_events, cursor, segment_end, process_day,
        )
        ensemble = forecast_step(
            ensemble, priors, crop_context, rng,
            scenes=scenes,
            weather_day=weather_day,
            soil_context=soil_context,
            management_events=segment_events,
            process_day=process_day,
            delta_days=delta_days,
        )
        segments.append({
            'process_day': process_day,
            'delta_days': round(delta_days, 9),
            'weather_available': bool(weather_day),
            'management_event_count': len(segment_events),
        })
        cursor = segment_end
    return ensemble, segments


def _scene_has_pixel_obs(scene) -> bool:
    """V79B: Check if scene has real per-pixel observation arrays.

    Returns True only when at least one per-pixel observation has valid,
    finite support. Sensor identity or array length alone is not evidence.
    """
    from ..observation.pixel_extraction import extract_pixel_observations
    pixel_obs = extract_pixel_observations(scene)
    for pix in pixel_obs.values():
        if (
            pix.is_per_pixel
            and pix.n_pixels > 1
            and pix.n_valid > 0
            and math.isfinite(float(pix.mean))
        ):
            return True
    return False


def run_enkf(
    scenes: list,
    operators: list,
    graph: Any,
    priors: dict,
    resolution_m: int,
    mode: str = "shadow",
    crop_context: Optional[dict] = None,
    rng: Optional[random.Random] = None,
    expected_resolution_m: Optional[int] = None,
    weather_daily_series: Optional[dict] = None,
    soil_context: Optional[dict] = None,
    management_events: Optional[List[dict]] = None,
    initial_posterior: Optional[Dict[str, Any]] = None,
    deadline_check: Optional[Callable[[], None]] = None,
) -> dict:
    """Run Ensemble Kalman Filter on the scene stack.

    Args:
        scenes: List of ASMAESceneRuntime objects.
        operators: List of ObservationOperatorRuntime objects.
        graph: MicrozoneGraph from V71.
        priors: Dict of layer priors from V73.
        resolution_m: Selected resolution.
        mode: ASMAE mode.
        crop_context: Crop context dict.
        rng: Seeded Random instance (V79A: deterministic).
        expected_resolution_m: V922 — if set, assert all operators match.

    Returns:
        Dict with raster_maps, uncertainty_maps, state_timeline,
        enkf_mode ("ht_per_pixel" | "proxy_mean_level"), etc.
    """
    # V922: Chain integrity assertion — operators must match resolution
    if expected_resolution_m is not None:
        from ..chain_integrity import assert_operators_match_resolution
        assert_operators_match_resolution(
            operators, expected_resolution_m, stage_name="EnKF",
        )

    if rng is None:
        from ..deterministic import make_rng
        rng = make_rng("enkf_run", str(expected_resolution_m or "default"), "v1")

    # Determine microzone count from graph
    if hasattr(graph, "node_count"):
        n_microzones = graph.node_count
    elif isinstance(graph, dict):
        n_microzones = graph.get("node_count", 100)
    else:
        n_microzones = 100

    n_ensemble = select_ensemble_size(mode, n_microzones)

    logger.info(
        "V74 EnKF: %d microzones, %d ensemble, mode=%s, resolution=%dm",
        n_microzones, n_ensemble, mode, resolution_m,
    )

    # ── Initialize ensemble ─────────────────────────────────────────
    node_ids = _get_node_ids(graph)
    ensemble, memory_blend_weight = initialize_ensemble(
        node_ids=node_ids,
        n_ensemble=n_ensemble,
        priors=priors,
        crop_context=crop_context or {},
        rng=rng,
        scenes=scenes,
        initial_posterior=initial_posterior,
    )

    # ── Track Hₜ usage ──────────────────────────────────────────────
    any_ht_used = False
    all_proxy = True
    any_per_pixel_obs = False  # V79B: track real per-pixel vs scalar mean
    update_counts = {
        "ht_per_pixel": 0,
        "ht_geometry_with_mean_observation": 0,
        "proxy_mean_level": 0,
        "ht_failed_proxy_fallback": 0,
        "ht_update_excluded": 0,
    }
    has_enkf_proxy_fallback = False

    # ── Process each scene (forecast → update) ──────────────────────
    state_timeline: List[Dict[str, Any]] = []
    update_reports: List[Dict[str, Any]] = []
    graph_regularization_reports: List[Dict[str, Any]] = []

    bound_pairs = sorted(
        _pair_scenes_operators(scenes, operators),
        key=lambda pair: str(getattr(pair[0], 'acquisition_time', '') or ''),
    )
    previous_scene_time = None
    for t, (scene, op) in enumerate(bound_pairs):
        scene_time = getattr(scene, "acquisition_time", None)
        if (
            isinstance(ensemble, np.ndarray)
            and isinstance(previous_scene_time, datetime)
            and isinstance(scene_time, datetime)
            and scene_time > previous_scene_time
        ):
            ensemble = dict(zip(node_ids, ensemble.tolist()))
        # Forecast step: propagate state forward over exact daily intervals.
        ensemble, forecast_segments = _forecast_elapsed_interval(
            ensemble=ensemble,
            previous_time=previous_scene_time,
            current_time=scene_time,
            priors=priors,
            crop_context=crop_context or {},
            rng=rng,
            scenes=scenes,
            weather_daily_series=weather_daily_series,
            soil_context=soil_context or {},
            management_events=management_events or [],
        )
        delta_days = sum(segment['delta_days'] for segment in forecast_segments)
        previous_scene_time = scene_time or previous_scene_time

        # Check if operator has real H_matrix
        h_matrix = getattr(op, "H_matrix", None)
        has_real_ht = h_matrix is not None
        update_mode = "proxy_mean_level"
        scene_reports = []

        if has_real_ht:
            try:
                # V79A: Real Hₜ-aware update (ensemble-space projection)
                if not isinstance(ensemble, np.ndarray):
                    ensemble = np.asarray([ensemble[nid] for nid in node_ids], dtype=float)
                ensemble, scene_reports = update_step_ht(
                    ensemble, scene, op, rng, deadline_check=deadline_check, node_ids=node_ids,
                )
                accepted_reports = [
                    rep for rep in scene_reports
                    if isinstance(rep, dict) and rep.get("update_applied") is True
                ]
                if accepted_reports:
                    any_ht_used = True
                    all_proxy = False
                    if _scene_has_pixel_obs(scene):
                        update_mode = "ht_per_pixel"
                    else:
                        update_mode = "ht_geometry_with_mean_observation"
                else:
                    update_mode = "ht_update_excluded"
                    has_enkf_proxy_fallback = True
            except Exception as e:
                # A deadline/lease fence is not a recoverable observation
                # failure.  Let it terminate the obsolete or over-budget run
                # instead of spending the rest of the scene stack before the
                # next outer deadline check notices it.
                if (
                    getattr(e, "worker_lease_lost", False)
                    or "BUDGET OVERRUN" in str(e)
                ):
                    raise
                logger.warning("H_t update failed; scene excluded: %s", e)
                scene_reports = [{
                    "mode": "ht_update_excluded",
                    "update_applied": False,
                    "failure_reason": str(e),
                }]
                update_mode = "ht_update_excluded"
                has_enkf_proxy_fallback = True
        else:
            # Proxy mean-level update (V74 original)
            ensemble, scene_reports = update_step_proxy(ensemble, scene, op, rng)
            update_mode = "proxy_mean_level"

        # Unsupported or failed *individual* features are fail-closed and
        # remain in the evidence ledger, but they are not a proxy fallback.
        # Demote full EnKF credit only when a proxy update was actually
        # applied (or when the whole scene had no accepted H_t update above).
        if any(
            isinstance(rep, dict)
            and rep.get("update_applied") is True
            and "proxy" in str(rep.get("mode", ""))
            for rep in scene_reports
        ):
            has_enkf_proxy_fallback = True

        accepted_target_states = sorted({
            state
            for report in scene_reports
            if isinstance(report, dict) and report.get("update_applied") is True
            for state in (report.get("accepted_target_states") if report.get("accepted_target_states") is not None else report.get("target_states", []))
            if state in STATE_NAMES and state not in report.get("excluded_target_states", [])
        })
        if accepted_target_states:
            from ..graph.spatial_regularization import apply_ensemble_graph_regularization
            ensemble, graph_report = apply_ensemble_graph_regularization(
                ensemble, graph, accepted_target_states,
                deadline_check=deadline_check,
            )
            graph_report["scene_id"] = getattr(scene, "scene_id", f"scene_{t}")
            graph_regularization_reports.append(graph_report)

        # Check deadline between scene iterations
        if deadline_check is not None:
            deadline_check()

        # Clamp to physical bounds
        ensemble = clamp_ensemble(ensemble)

        # V79B: Check if scene had real per-pixel observations
        if has_real_ht and _scene_has_pixel_obs(scene) and update_mode == "ht_per_pixel":
            any_per_pixel_obs = True

        # Increment count
        update_counts[update_mode] += 1

        # Record timeline
        snapshot = compute_ensemble_statistics(ensemble, node_ids)
        snapshot['elapsed_days_since_previous_scene'] = round(delta_days, 6)
        snapshot['forecast_segments'] = forecast_segments
        snapshot["scene_id"] = getattr(scene, "scene_id", f"scene_{t}")
        snapshot["update_mode"] = update_mode
        state_timeline.append(snapshot)

        # Add to overall update reports
        scene_runtime = scene.get("runtime", scene) if isinstance(scene, dict) else scene
        source_reality = str(getattr(scene_runtime, "source_reality", "unknown") or "unknown")
        real_provider_product = bool(getattr(scene_runtime, "real_provider_product", False))
        for rep in scene_reports:
            rep["scene_id"] = snapshot["scene_id"]
            rep["timestamp"] = str(getattr(scene, "acquisition_time", None) or getattr(getattr(scene, "runtime", None), "acquisition_time", ""))
            rep["source_reality"] = source_reality
            rep["real_provider_product"] = real_provider_product
            rep["production_observation"] = bool(
                rep.get("update_applied") is True
                and rep.get("evidence_kind") == "direct_observation"
                and real_provider_product
                and source_reality in {"real_raster", "real_provider_raster", "provider_observation"}
            )
            update_reports.append(rep)

    # ── Final state ─────────────────────────────────────────────────
    final_stats = compute_ensemble_statistics(ensemble, node_ids)

    # Determine overall EnKF mode
    if any_ht_used and any_per_pixel_obs and not all_proxy:
        enkf_mode = "ht_per_pixel"
    elif any_ht_used and not all_proxy:
        enkf_mode = "ht_geometry_with_mean_observation"
    else:
        enkf_mode = "proxy_mean_level"

    full_enkf_credit_allowed = (enkf_mode == "ht_per_pixel") and not has_enkf_proxy_fallback

    result = {
        "raster_maps": final_stats.get("means", {}),
        "uncertainty_maps": final_stats.get("sigmas", {}),
        "state_timeline": state_timeline,
        "ensemble_size": n_ensemble,
        "n_scenes_processed": len(state_timeline),
        "resolution_m": resolution_m,
        "enkf_mode": enkf_mode,
        "status": "success",
        "memory_blend_weight": memory_blend_weight,
        "enkf_update_mode_counts": update_counts,
        "has_enkf_proxy_fallback": has_enkf_proxy_fallback,
        "full_enkf_credit_allowed": full_enkf_credit_allowed,
        "update_report": update_reports,
        "graph_regularization_report": graph_regularization_reports,
        "graph_regularization_applied": any(
            report.get("applied") is True for report in graph_regularization_reports
        ),
        "process_model_inputs": {
            "weather": bool(weather_daily_series),
            "soil": bool(soil_context),
            "management": bool(management_events),
            "crop": bool(crop_context),
            "crop_mixture": bool(
                (crop_context or {}).get("crop_group_posterior")
            ),
            "crop_mixture_known_mass": (
                (crop_context or {}).get("crop_mixture_known_mass", 0.0)
            ),
            "crop_posterior_hash": (
                (crop_context or {}).get("crop_posterior_hash")
            ),
        },
        "initialization_proof": {
            "mode": "resilient_plot_posterior" if initial_posterior else "coarse_priors",
            "states": {
                state: {
                    "status": (initial_posterior or {}).get(state, {}).get("status"),
                    "support": (initial_posterior or {}).get(state, {}).get("support", []),
                }
                for state in STATE_NAMES
                if isinstance((initial_posterior or {}).get(state), dict)
                and isinstance((initial_posterior or {}).get(state, {}).get("mean"), (int, float))
            },
        },
    }

    logger.info(
        "V74 EnKF complete: %d scenes, mode=%s, enkf_mode=%s",
        len(state_timeline), mode, enkf_mode,
    )

    return result


# ── Learning Memory Blending & Observations ─────────────────────────────────

def has_observation_in_stack(scenes: List[Any], state_name: str) -> bool:
    state_to_obs = {
        "vigor": ["ndvi", "evi", "savi", "nbr", "vigor"],
        "lai": ["ndvi", "evi", "lai"],
        "chlorophyll": ["ndre", "reip", "chlorophyll"],
        "canopy_water": ["ndmi", "canopy_water"],
        "root_zone_water": ["ndwi", "sar_vv", "sar_vh", "root_zone_water"],
        "surface_wetness_event": ["ndwi", "sar_vv", "sar_ratio", "surface_wetness_event"],
        "structure": ["sar_vh", "sar_ratio", "structure"],
        "bare_soil_fraction": ["savi", "bsi", "nbr", "bare_soil_fraction"],
        "salinity_stress": ["ndsi", "salinity_stress"],
        "thermal_stress": ["cwsi", "thermal_stress"],
        "biotic_confounder_risk": ["biotic_anomaly", "biotic_confounder_risk"],
        "phenology_progress": ["phenology_index", "crop_stage", "phenology_progress"],
        "stress_memory": ["stress_memory_index", "stress_memory"],
    }
    obs_types = state_to_obs.get(state_name, [state_name])
    from ..observation.pixel_extraction import extract_pixel_observations

    for scene in (scenes or []):
        observations = extract_pixel_observations(scene)
        for obs_type in obs_types:
            observation = observations.get(obs_type)
            if (
                observation is not None
                and observation.n_valid > 0
                and math.isfinite(float(observation.mean))
            ):
                return True
    return False

def blend_learning_memory(
    ensemble: Dict[str, List[List[float]]],
    priors: dict,
    crop_context: dict,
    scenes: Optional[List[Any]] = None,
) -> Tuple[Dict[str, List[List[float]]], float]:
    """Blends the plot learning memory prior into the ensemble states."""
    lm_prior = priors.get("learning_memory", {})
    if not lm_prior or not lm_prior.get("usable_as_prior") or lm_prior.get("status") != "available":
        return ensemble, 0.0

    mdata = lm_prior.get("memory_data", {})
    if not mdata:
        return ensemble, 0.0

    status = mdata.get("memory_status", "candidate")
    status_caps = {
        "candidate": 0.10,
        "provisional": 0.20,
        "validated": 0.30,
        "certified_plot_memory": 0.50,
        "revoked": 0.0
    }
    cap = status_caps.get(status, 0.0)
    if cap <= 0.0:
        return ensemble, 0.0

    # Allowed V87 memory variables and their state mappings
    MEMORY_TO_STATE_MAP = {
        "canopy_water_response": "canopy_water",
        "salinity_persistence": "salinity_stress",
        "root_zone_water_tendency": "root_zone_water",
        "phenology_timing_offset": "phenology_progress",
        "recurring_stress_zone": "stress_memory",
    }

    max_blend_used = 0.0

    for mem_var, state_name in MEMORY_TO_STATE_MAP.items():
        var_data = mdata.get("variables", {}).get(mem_var)
        if not var_data:
            continue

        val = var_data.get("value")
        trust = var_data.get("trust", 0.0)
        confidence = var_data.get("confidence", 0.0)
        ev_count = var_data.get("evidence_count", 0)

        if val is None:
            continue

        try:
            state_idx = STATE_NAMES.index(state_name)
        except ValueError:
            continue

        evidence_factor = min(1.0, ev_count / 5.0)
        variable_factor = 1.0

        blend_weight = min(
            cap,
            trust * confidence * evidence_factor * variable_factor
        )

        # Real-time observations must always dominate after update.
        # Scale down prior weight to <= 0.1 if an active observation is present.
        if scenes and has_observation_in_stack(scenes, state_name):
            blend_weight = min(blend_weight, 0.1)

        # Keep track of max blend weight used for diagnostics
        max_blend_used = max(max_blend_used, blend_weight)

        if blend_weight > 0.0:
            for nid in ensemble:
                for m in range(len(ensemble[nid])):
                    ensemble[nid][m][state_idx] = blend_weight * val + (1.0 - blend_weight) * ensemble[nid][m][state_idx]

    # Geometry memory must be resolved before graph construction, never here.
    return ensemble, max_blend_used


# ── Ensemble Initialization ─────────────────────────────────────────────────


def initialize_ensemble(
    node_ids: List[str],
    n_ensemble: int,
    priors: dict,
    crop_context: dict,
    rng: random.Random,
    scenes: Optional[List[Any]] = None,
    initial_posterior: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, List[List[float]]], float]:
    """Initialize ensemble members for each microzone.

    Uses deterministic seeded RNG for reproducibility.
    """
    l2_prior = priors.get("layer2", {})
    growth_pos = l2_prior.get("growth_position", 0.5) if isinstance(l2_prior, dict) and l2_prior.get("usable_as_prior") else 0.5
    import numpy as np

    mixture_bounds = (
        crop_context.get("crop_mixture_bounds", {})
        if isinstance(crop_context, dict) else {}
    )
    mids = []
    lows = []
    highs = []
    spreads = []
    for name in STATE_NAMES:
        lo, hi = STATE_BOUNDS[name]
        mid = (lo + hi) / 2.0
        if name == "vigor":
            mid = 0.3 + 0.4 * growth_pos
        elif name == "lai":
            bounds = mixture_bounds.get("lai_bounds")
            if (
                isinstance(bounds, (list, tuple)) and len(bounds) == 2
                and all(isinstance(value, (int, float)) for value in bounds)
            ):
                mid = float(bounds[0]) + (float(bounds[1]) - float(bounds[0])) * growth_pos
            else:
                mid = 0.5 + 4.0 * growth_pos
        elif name == "chlorophyll":
            bounds = mixture_bounds.get("chlorophyll_bounds")
            if (
                isinstance(bounds, (list, tuple)) and len(bounds) == 2
                and all(isinstance(value, (int, float)) for value in bounds)
            ):
                mid = float(bounds[0]) + (float(bounds[1]) - float(bounds[0])) * growth_pos
            else:
                mid = 10 + 40 * growth_pos
        elif name == "bare_soil_fraction":
            mid = max(0.0, 0.8 - 0.7 * growth_pos)
        elif name == "phenology_progress":
            mid = growth_pos
        lows.append(float(lo))
        highs.append(float(hi))
        mids.append(float(mid))
        spreads.append(float(hi - lo) * 0.1)

    # One seed draw preserves deterministic orchestration while NumPy performs
    # the millions of independent Gaussian samples in native code.
    generator = np.random.default_rng(rng.getrandbits(128))
    shape = (len(node_ids), n_ensemble, N_STATES)
    values = (
        np.asarray(mids, dtype=float)[None, None, :]
        + generator.standard_normal(shape)
        * np.asarray(spreads, dtype=float)[None, None, :]
    )
    values = np.clip(
        values,
        np.asarray(lows, dtype=float)[None, None, :],
        np.asarray(highs, dtype=float)[None, None, :],
    )
    for state_index, state_name in enumerate(STATE_NAMES):
        posterior = (initial_posterior or {}).get(state_name, {})
        if not isinstance(posterior, dict):
            continue
        mean = posterior.get("mean")
        sigma = posterior.get("sigma")
        if not isinstance(mean, (int, float)):
            continue
        if not isinstance(sigma, (int, float)) or sigma <= 0.0:
            sigma = (STATE_BOUNDS[state_name][1] - STATE_BOUNDS[state_name][0]) * 0.05
        lo, hi = STATE_BOUNDS[state_name]
        values[:, :, state_index] = np.clip(
            generator.normal(float(mean), float(sigma), size=shape[:2]),
            lo,
            hi,
        )
    ensemble: Dict[str, List[List[float]]] = {
        node_id: values[position].tolist()
        for position, node_id in enumerate(node_ids)
    }

    # Blend plot learning memory prior
    ensemble, memory_blend_weight = blend_learning_memory(
        ensemble, priors, crop_context, scenes=scenes,
    )

    return ensemble, memory_blend_weight


def _sample_initial_state(
    growth_position: float,
    crop_context: dict,
    rng: random.Random,
) -> List[float]:
    """Sample one ensemble member's initial state with seeded RNG."""
    state = [0.0] * N_STATES
    mixture_bounds = (
        crop_context.get("crop_mixture_bounds", {})
        if isinstance(crop_context, dict) else {}
    )

    for i, name in enumerate(STATE_NAMES):
        lo, hi = STATE_BOUNDS[name]
        mid = (lo + hi) / 2.0

        if name == "vigor":
            mid = 0.3 + 0.4 * growth_position
        elif name == "lai":
            bounds = mixture_bounds.get("lai_bounds")
            if (
                isinstance(bounds, (list, tuple))
                and len(bounds) == 2
                and all(isinstance(value, (int, float)) for value in bounds)
            ):
                mid = float(bounds[0]) + (
                    float(bounds[1]) - float(bounds[0])
                ) * growth_position
            else:
                mid = 0.5 + 4.0 * growth_position
        elif name == "chlorophyll":
            bounds = mixture_bounds.get("chlorophyll_bounds")
            if (
                isinstance(bounds, (list, tuple))
                and len(bounds) == 2
                and all(isinstance(value, (int, float)) for value in bounds)
            ):
                mid = float(bounds[0]) + (
                    float(bounds[1]) - float(bounds[0])
                ) * growth_position
            else:
                mid = 10 + 40 * growth_position
        elif name == "bare_soil_fraction":
            mid = max(0.0, 0.8 - 0.7 * growth_position)
        elif name == "phenology_progress":
            mid = growth_position

        spread = (hi - lo) * 0.1
        val = mid + rng.gauss(0, spread)
        state[i] = max(lo, min(hi, val))

    return state


# ── Forecast Step ────────────────────────────────────────────────────────────


def forecast_step(
    ensemble: Dict[str, List[List[float]]],
    priors: dict,
    crop_context: dict,
    rng: random.Random,
    scenes: Optional[List[Any]] = None,
    weather_day: Optional[dict] = None,
    soil_context: Optional[dict] = None,
    management_events: Optional[List[dict]] = None,
    process_day: Optional[str] = None,
    delta_days: float = 1.0,
) -> Dict[str, List[List[float]]]:
    """Forecast with weather, soil, irrigation, crop, and management drivers."""
    weather_day = weather_day or {}
    soil_context = soil_context or {}
    management_events = management_events or []
    delta_days = max(0.0, float(delta_days))
    if delta_days <= 0.0:
        return ensemble
    sqrt_delta_days = math.sqrt(delta_days)

    def number(mapping: Any, aliases: Tuple[str, ...]) -> Optional[float]:
        if not isinstance(mapping, dict):
            return None
        queue = [mapping]
        wanted = {alias.lower() for alias in aliases}
        while queue:
            current = queue.pop(0)
            for key, value in current.items():
                if str(key).lower() in wanted:
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        return float(value)
                    if isinstance(value, dict):
                        for scalar_key in ("value", "mean", "estimate", "current"):
                            scalar = value.get(scalar_key)
                            if isinstance(scalar, (int, float)) and not isinstance(scalar, bool):
                                return float(scalar)
                if isinstance(value, dict):
                    queue.append(value)
        return None

    rain = number(weather_day, ("precipitation_mm", "precipitation", "rainfall_mm", "rain"))
    et0 = number(weather_day, ("et0_mm", "et0", "evapotranspiration"))
    temp_max = number(weather_day, ("temp_max_c", "temp_max", "temperature_max", "tmax"))
    temp_mean = number(weather_day, ("temp_mean_c", "temp_mean", "temperature_mean", "tmean"))
    humidity = number(weather_day, ("humidity_mean_pct", "humidity", "relative_humidity", "rh"))
    radiation = number(weather_day, ("solar_radiation_mj_m2", "solar_radiation", "radiation"))
    irrigation = 0.0
    fertilization = 0.0
    for event in management_events or []:
        if hasattr(event, "forcing_type") or (hasattr(event, "event_type") and hasattr(event, "quantity")):
            status = getattr(event, "execution_status", getattr(event, "status", None))
            if status is not None:
                status_str = str(getattr(status, "value", status)).upper()
                if "CONFIRMED" not in status_str and "OBSERVED" not in status_str:
                    continue  # Ignore unconfirmed planned actions during physical transition
            start_dt = getattr(event, "effective_start", getattr(event, "timestamp", None))
            event_day = str(start_dt.isoformat() if hasattr(start_dt, "isoformat") else (start_dt or ""))[:10]
            if process_day and event_day and event_day != process_day:
                continue
            etype = str(getattr(event, "forcing_type", getattr(event, "event_type", ""))).lower()
            qty = float(event.quantity or 0.0)
            unit = str(getattr(event, "units", getattr(event, "unit", "mm")) or "mm").lower()
            if unit in ("m3_ha", "m3/ha"):
                qty_mm = qty * 0.1
            elif unit in ("l", "liters", "litre", "litres"):
                area_m2 = number(soil_context, ("area_m2", "plot_area_m2")) or 10000.0
                qty_mm = qty / area_m2
            else:
                qty_mm = qty

            if "irrig" in etype or "water" in etype:
                irrigation += qty_mm
            elif "fert" in etype or "nutrient" in etype:
                fertilization += qty

        elif isinstance(event, dict):
            status = event.get("status")
            if status:
                status_str = str(getattr(status, "value", status)).upper()
                if (
                    "CONFIRMED" not in status_str
                    and "OBSERVED" not in status_str
                    and status_str not in ("OK", "APPLIED", "EXECUTED")
                ):
                    continue  # Ignore unconfirmed planned actions
            event_day = str(event.get("date") or event.get("timestamp") or "")[:10]
            if process_day and event_day and event_day != process_day:
                continue
            event_type = str(event.get("type") or event.get("event_type") or "").lower()
            if "irrig" in event_type:
                unit = str(event.get("unit") or "mm").lower()
                amt = number(event, ("amount_mm", "water_mm", "irrigation_mm", "amount", "quantity")) or 0.0
                if unit in ("m3_ha", "m3/ha"):
                    amt *= 0.1
                elif unit in ("l", "liters", "litre", "litres"):
                    area_m2 = number(soil_context, ("area_m2", "plot_area_m2")) or 10000.0
                    amt /= area_m2
                irrigation += amt
            if "fert" in event_type or "nutrient" in event_type:
                fertilization += number(event, ("amount_kg_ha", "nitrogen_kg_ha", "amount", "quantity")) or 0.0

    field_capacity = number(soil_context, ("field_capacity", "theta_fc"))
    wilting_point = number(soil_context, ("wilting_point", "theta_wp"))
    rooting_depth = number(soil_context, ("rooting_depth_m", "root_depth_m", "rooting_depth"))
    drainage_fraction = number(soil_context, ("drainage_fraction", "drainage_coefficient"))
    runoff_fraction = number(soil_context, ("runoff_fraction", "runoff_coefficient"))
    soil_salinity = number(soil_context, ("electrical_conductivity", "salinity", "ec_ds_m"))
    crop_coefficient = number(crop_context, ("crop_coefficient", "kc")) or 1.0
    optimal_temperature = number(crop_context, ("t_opt", "optimal_temperature")) or 25.0
    maximum_temperature = max(number(crop_context, ("t_max", "maximum_temperature")) or 40.0, optimal_temperature + 1.0)
    base_temperature = number(crop_context, ("t_base", "base_temperature")) or 5.0

    has_water_drivers = isinstance(rain, (int, float)) and isinstance(et0, (int, float))
    effective_rain = float(rain or 0.0) * (1.0 - max(0.0, min(1.0, runoff_fraction or 0.0)))
    atmospheric_demand = crop_coefficient * float(et0 or 0.0)

    # Physical soil hydrology parameters: Delta theta_v = flux_mm / root_depth_mm
    root_depth_mm = max(100.0, (rooting_depth or 0.4) * 1000.0)
    theta_fc_val = field_capacity or 0.35
    theta_wp_val = wilting_point or 0.12
    theta_sat_val = number(soil_context, ("saturation", "theta_sat")) or (theta_fc_val + 0.10)
    theta_sat_val = min(1.0, max(theta_fc_val + 0.02, theta_sat_val))

    # Volumetric water content increments
    delta_theta_rain = (effective_rain * delta_days) / root_depth_mm
    delta_theta_irrig = irrigation / root_depth_mm

    # FAO-56 Transpiration reduction (Ks factor)
    p_depletion = 0.5
    theta_p = theta_fc_val - p_depletion * (theta_fc_val - theta_wp_val)
    paw_range = max(1e-4, theta_p - theta_wp_val)

    # Relative available water balance metrics for salinity and stress memory
    daily_water_balance = (
        effective_rain - atmospheric_demand
        if (rain is not None or et0 is not None) else 0.0
    )
    paw_capacity_mm = root_depth_mm * max(theta_fc_val - theta_wp_val, 0.05)
    storage_mm = max(25.0, paw_capacity_mm)
    normalized_daily_water_delta = daily_water_balance / storage_mm

    missing_driver_scale = 1.0 if has_water_drivers else 1.8
    import numpy as np

    node_ids = list(ensemble)
    values = np.asarray([ensemble[node] for node in node_ids], dtype=float)
    generator = np.random.default_rng(rng.getrandbits(128))
    member_shape = values.shape[:2]
    for i, name in enumerate(STATE_NAMES):
        lo, hi = STATE_BOUNDS[name]
        current = values[:, :, i]
        if name == "surface_wetness_event":
            wetting = effective_rain * delta_days + irrigation
            rain_pulse = min(1.0, max(0.0, wetting / 20.0)) if wetting > 0.0 else 0.0
            updated = current * (0.65 ** delta_days) + rain_pulse + generator.normal(
                0.0, 0.05 * missing_driver_scale * sqrt_delta_days, member_shape,
            )
        elif name == "root_zone_water":
            # Actual ET based on FAO-56 moisture stress factor Ks
            ks_factor = np.clip((current - theta_wp_val) / paw_range, 0.0, 1.0)
            actual_et_mm = atmospheric_demand * ks_factor * delta_days
            delta_theta_et = actual_et_mm / root_depth_mm

            # Gravity drainage strictly occurs above Field Capacity theta_FC
            excess_water = np.maximum(0.0, current - theta_fc_val)
            drainage_coeff = max(0.0, min(1.0, drainage_fraction if drainage_fraction is not None else 0.5))
            drainage_rate = excess_water * drainage_coeff * delta_days

            updated = (
                current
                + delta_theta_rain
                + delta_theta_irrig
                - delta_theta_et
                - drainage_rate
                + generator.normal(0.0, 0.01 * missing_driver_scale * sqrt_delta_days, member_shape)
            )
            # Clip to physical soil bounds [theta_wp * 0.5, theta_sat]
            updated = np.clip(updated, max(0.01, theta_wp_val * 0.5), theta_sat_val)
        elif name == "canopy_water":
            ks_factor = np.clip((current - theta_wp_val) / paw_range, 0.0, 1.0)
            actual_et_mm = atmospheric_demand * ks_factor * delta_days
            delta_theta_et = actual_et_mm / root_depth_mm
            water_impulse = delta_theta_rain + delta_theta_irrig - delta_theta_et
            updated = (
                current * (0.97 ** delta_days)
                + 0.6 * water_impulse
                + generator.normal(0.0, 0.02 * missing_driver_scale * sqrt_delta_days, member_shape)
            )
        elif name == "thermal_stress":
            heat = max(0.0, min(1.0, (float(temp_max) - optimal_temperature) / (maximum_temperature - optimal_temperature))) if isinstance(temp_max, (int, float)) else current
            decay = 0.8 ** delta_days
            updated = decay * current + (1.0 - decay) * heat + generator.normal(
                0.0, 0.02 * (1.0 if temp_max is not None else 1.8) * sqrt_delta_days, member_shape,
            )
        elif name == "phenology_progress" and temp_mean is not None:
            degree_day_progress = max(0.0, temp_mean - base_temperature) / 1800.0
            updated = current + degree_day_progress * delta_days + generator.normal(
                0.0, 0.005 * sqrt_delta_days, member_shape,
            )
        elif name == "biotic_confounder_risk" and humidity is not None and temp_mean is not None:
            humidity_pressure = max(0.0, min(1.0, (humidity - 60.0) / 35.0))
            temperature_pressure = max(0.0, 1.0 - abs(temp_mean - 24.0) / 16.0)
            decay = 0.85 ** delta_days
            updated = decay * current + (1.0 - decay) * humidity_pressure * temperature_pressure
        elif name == "salinity_stress" and soil_salinity is not None:
            baseline = max(0.0, min(1.0, soil_salinity / 8.0))
            leaching = max(0.0, daily_water_balance * delta_days + irrigation) / max(storage_mm, 1.0)
            decay = 0.9 ** delta_days
            updated = decay * current + (1.0 - decay) * max(0.0, baseline - leaching)
        elif name == "chlorophyll" and fertilization > 0.0:
            updated = current + min(3.0, fertilization / 20.0) + generator.normal(
                0.0, 0.5 * sqrt_delta_days, member_shape,
            )
        elif name == "vigor" and radiation is not None:
            radiation_factor = max(0.0, min(1.0, radiation / 25.0))
            updated = current + delta_days * (
                0.01 * radiation_factor - 0.01 * max(0.0, -normalized_daily_water_delta)
            ) + generator.normal(
                0.0, 0.035 * missing_driver_scale * sqrt_delta_days, member_shape,
            )
        elif name == "stress_memory":
            heat_signal = max(0.0, min(1.0, (float(temp_max) - optimal_temperature) / (maximum_temperature - optimal_temperature))) if temp_max is not None else 0.0
            water_signal = max(0.0, -normalized_daily_water_delta * 5.0)
            decay = 0.97 ** delta_days
            updated = decay * current + (1.0 - decay) * max(heat_signal, water_signal)
        else:
            sigma_q = (hi - lo) * 0.02 * missing_driver_scale
            updated = current + generator.normal(
                0.0, sigma_q * sqrt_delta_days, member_shape,
            )
        values[:, :, i] = np.clip(updated, lo, hi)

    return {
        node_id: values[position].tolist()
        for position, node_id in enumerate(node_ids)
    }


# ── Update Step: Hₜ-Aware (V79A) ────────────────────────────────────────────


def _state_variance_summary(
    ensemble: Any,
    state_indices: List[int],
) -> Dict[str, float]:
    """Return average within-node ensemble variance for named states, isolating
    epistemic uncertainty from between-node spatial heterogeneity."""
    result: Dict[str, float] = {}
    if ensemble is None or len(ensemble) == 0:
        return result
    import numpy as np

    if isinstance(ensemble, np.ndarray):
        values = ensemble
    elif isinstance(ensemble, dict):
        values = np.asarray(list(ensemble.values()), dtype=float)
    else:
        values = np.asarray(ensemble, dtype=float)
    if values.ndim != 3 or values.shape[1] == 0:
        return result
    for state_index in state_indices:
        if state_index < 0 or state_index >= values.shape[2]:
            continue
        state_name = STATE_NAMES[state_index] if state_index < len(STATE_NAMES) else f"state_{state_index}"
        result[state_name] = float(np.mean(np.var(values[:, :, state_index], axis=1)))
    return result


def _state_mean_summary(
    ensemble: Any,
    state_indices: List[int],
) -> Dict[str, float]:
    """Return average within-node ensemble mean for named states."""
    result: Dict[str, float] = {}
    if ensemble is None or len(ensemble) == 0:
        return result
    import numpy as np

    if isinstance(ensemble, np.ndarray):
        values = ensemble
    elif isinstance(ensemble, dict):
        values = np.asarray(list(ensemble.values()), dtype=float)
    else:
        values = np.asarray(ensemble, dtype=float)
    if values.ndim != 3 or values.shape[1] == 0:
        return result
    for state_index in state_indices:
        if state_index < 0 or state_index >= values.shape[2]:
            continue
        state_name = STATE_NAMES[state_index] if state_index < len(STATE_NAMES) else f"state_{state_index}"
        result[state_name] = float(np.mean(values[:, :, state_index]))
    return result


def _legacy_order_dependent_update_step_ht(
    ensemble: Dict[str, List[List[float]]],
    scene: Any,
    operator: Any,
    rng: random.Random,
) -> Tuple[Dict[str, List[List[float]]], List[Dict[str, Any]]]:
    """V79B: Hₜ-aware EnKF update with real per-pixel observations.

    Uses per-pixel observation vectors (not scalar means):
      y_obs = real pixel observation vector from scene bands
      y_pred = H_t @ h(X_f) (projected ensemble predictions)
      Update via ensemble-space inversion (no dense NxN covariance)
    """
    from ..observation.s2_forward_model import predict_observation
    from ..observation.s1_sar_model import predict_sar_observation
    from ..observation.observation_noise import compute_observation_noise
    from ..observation.index_state_mapping import (
        INDEX_STATE_REGISTRY, validate_forbidden_state_update,
    )
    from ..observation.pixel_extraction import extract_pixel_observations

    # V79B: Extract per-pixel observations
    pixel_obs = extract_pixel_observations(scene)
    if not pixel_obs:
        return ensemble, []

    h_matrix = operator.H_matrix
    node_ids = list(ensemble.keys())
    n_nodes = len(node_ids)
    reports = []

    for obs_name, pix_obs in pixel_obs.items():
        mapping = INDEX_STATE_REGISTRY.get(obs_name)
        if mapping is None:
            continue
        target_indices = [
            state_index for state_index in mapping.target_state_indices
            if 0 <= state_index < len(STATE_NAMES)
            and not validate_forbidden_state_update(obs_name, state_index)
        ]
        target_states = [STATE_NAMES[state_index] for state_index in target_indices]

        sigma_obs = compute_observation_noise(
            obs_name,
            crop_stage=str(getattr(scene, "crop_stage", "") or ""),
            cloud_fraction=float(getattr(scene, "cloud_fraction", 0.0) or 0.0),
            valid_support_fraction=float(getattr(scene, "valid_fraction", 1.0) or 0.0),
            registration_uncertainty_m=float(getattr(scene, "registration_uncertainty_m", 0.0) or 0.0),
            temporal_aggregation_days=float(getattr(scene, "temporal_aggregation_days", 1.0) or 1.0),
        )
        r_var = sigma_obs * sigma_obs

        n_ens = len(next(iter(ensemble.values()), []))
        if n_ens == 0:
            continue

        # Compute predicted obs per member per microzone
        h_pred = []
        for nid in node_ids:
            members = ensemble[nid]
            preds = []
            for member in members:
                if mapping.sensor == "S1":
                    pred = predict_sar_observation(obs_name, member)
                else:
                    pred = predict_observation(obs_name, member)
                if pred is None:
                    preds = []
                    break
                preds.append(pred)
            if not preds:
                break
            h_pred.append(preds)

        if len(h_pred) != len(node_ids):
            reports.append({
                "obs_name": obs_name,
                "sensor": mapping.sensor,
                "mode": "excluded_missing_forward_model",
                "update_applied": False,
                "target_states": target_states,
                "failure_reason": "missing_forward_model",
            })
            continue

        try:
            import numpy as np
            h_pred_array = np.array(h_pred)  # (n_nodes, n_ens)

            if hasattr(h_matrix, 'shape') and h_matrix.shape[1] == n_nodes:
                # Project: (n_pixels, n_nodes) @ (n_nodes, n_ens) = (n_pixels, n_ens)
                y_pred_pixel = h_matrix @ h_pred_array  # (n_pixels, n_ens)

                n_pixels_ht = y_pred_pixel.shape[0]

                # V79B: Use real per-pixel observation vector
                if pix_obs.is_per_pixel and pix_obs.n_pixels == n_pixels_ht:
                    y_obs_pixel = np.array(pix_obs.values[:n_pixels_ht])
                    valid_mask = np.array(pix_obs.valid_mask[:n_pixels_ht])
                elif pix_obs.is_per_pixel and pix_obs.n_pixels > 1:
                    # Resample pixel obs to match Hₜ pixel count
                    import math
                    stride = max(1, pix_obs.n_pixels // n_pixels_ht)
                    y_obs_pixel = np.array(pix_obs.values[::stride][:n_pixels_ht])
                    valid_mask = np.array(pix_obs.valid_mask[::stride][:n_pixels_ht])
                    # Pad if short
                    if len(y_obs_pixel) < n_pixels_ht:
                        pad = n_pixels_ht - len(y_obs_pixel)
                        y_obs_pixel = np.concatenate([y_obs_pixel, np.full(pad, pix_obs.mean)])
                        valid_mask = np.concatenate([valid_mask, np.zeros(pad, dtype=bool)])
                else:
                    # Scalar fallback — not true per-pixel
                    y_obs_pixel = np.full(n_pixels_ht, pix_obs.mean)
                    valid_mask = np.ones(n_pixels_ht, dtype=bool)

                # Apply valid mask
                valid_idx = np.where(valid_mask)[0]
                if len(valid_idx) == 0:
                    reports.append({
                        "obs_name": obs_name,
                        "sensor": mapping.sensor,
                        "mode": "excluded_no_valid_pixels",
                        "update_applied": False,
                        "target_states": target_states,
                        "failure_reason": "no_valid_pixels",
                    })
                    continue

                y_obs_valid = y_obs_pixel[valid_idx]
                y_pred_valid = y_pred_pixel[valid_idx]  # (n_valid, n_ens)

                # Ensemble mean of predicted pixel obs
                y_pred_mean = np.mean(y_pred_valid, axis=1)  # (n_valid,)

                # Innovation in pixel space
                innovation_pixel = y_obs_valid - y_pred_mean  # (n_valid,)

                # Anomalies in observation space
                Y_anomaly = y_pred_valid - y_pred_mean[:, None]  # (n_valid, n_ens)

                # Ensemble-space covariance:
                # C = Y^T Y / (N-1) + R*I  (n_ens x n_ens)
                C = Y_anomaly.T @ Y_anomaly / max(n_ens - 1, 1)
                C += r_var * np.eye(n_ens)

                try:
                    C_inv = np.linalg.inv(C)
                except np.linalg.LinAlgError:
                    reports.append({
                        "obs_name": obs_name,
                        "sensor": mapping.sensor,
                        "mode": "excluded_singular_observation_covariance",
                        "update_applied": False,
                        "target_states": target_states,
                        "failure_reason": "singular_observation_covariance",
                    })
                    continue

                # Innovation projected into ensemble space
                innov_ens = Y_anomaly.T @ innovation_pixel / max(n_ens - 1, 1)

                # Update coefficients
                alpha = C_inv @ innov_ens  # (n_ens,)
                prior_variance = _state_variance_summary(ensemble, target_indices)

                # Update each microzone's ensemble
                for ni, nid in enumerate(node_ids):
                    members = ensemble[nid]
                    state_mean = [sum(m[s] for m in members) / n_ens for s in range(N_STATES)]

                    for j, member in enumerate(members):
                        for s_idx in range(N_STATES):
                            if validate_forbidden_state_update(obs_name, s_idx):
                                continue
                            if s_idx not in mapping.target_state_indices:
                                continue

                            update = 0.0
                            for k in range(n_ens):
                                other_anomaly = members[k][s_idx] - state_mean[s_idx]
                                update += alpha[k] * other_anomaly
                            update /= max(n_ens - 1, 1)

                            member[s_idx] += update + rng.gauss(0, sigma_obs * 0.1)

                posterior_variance = _state_variance_summary(ensemble, target_indices)
                information_gain = {
                    state: max(0.0, prior - posterior_variance.get(state, prior))
                    for state, prior in prior_variance.items()
                }
                information_gain_fraction = {
                    state: (gain / prior if prior > 1e-12 else 0.0)
                    for state, gain in information_gain.items()
                    for prior in [prior_variance[state]]
                }

                reports.append({
                    "obs_name": obs_name,
                    "sensor": mapping.sensor,
                    "obs_mean": float(pix_obs.mean),
                    "pred_mean": float(np.mean(y_pred_valid)) if len(valid_idx) > 0 else float(pix_obs.mean),
                    "innovation_mean": float(np.mean(innovation_pixel)) if len(valid_idx) > 0 else 0.0,
                    "n_pixels": int(len(valid_idx)),
                    "sigma_obs": float(sigma_obs),
                    "mode": "ht_per_pixel" if pix_obs.is_per_pixel else "ht_geometry_with_mean_observation",
                    "update_applied": True,
                    "target_states": target_states,
                    "evidence_kind": "direct_observation" if pix_obs.is_per_pixel else "indirect_observation",
                    "prior_variance": prior_variance,
                    "posterior_variance": posterior_variance,
                    "information_gain": information_gain,
                    "information_gain_fraction": information_gain_fraction,
                    "kalman_gain_summary": {
                        "kind": "ensemble_space_update_coefficient",
                        "l2_norm": float(np.linalg.norm(alpha)),
                    },
                })
                continue

        except (ImportError, Exception) as e:
            logger.debug("H_t projection failed for %s; observation excluded: %s", obs_name, e)

        # Fallback: proxy mean-level update
        reports.append({
            "obs_name": obs_name,
            "sensor": mapping.sensor,
            "obs_mean": float(pix_obs.mean),
            "pred_mean": None,
            "innovation_mean": None,
            "n_pixels": 0,
            "sigma_obs": float(sigma_obs),
            "mode": "excluded_ht_projection_failure",
            "update_applied": False,
            "target_states": target_states,
            "failure_reason": "ht_projection_failure",
        })

    return ensemble, reports


# ── Update Step: Proxy Mean-Level (Original V74) ─────────────────────────────


def _etkf_target_update(
    ensemble: Dict[str, List[List[float]]],
    node_ids: List[str],
    target_indices: List[int],
    predicted_observations: Any,
    observed_values: Any,
    observation_variance: float,
) -> Dict[str, List[List[float]]]:
    import numpy as np

    n_ensemble = len(next(iter(ensemble.values()), []))
    if n_ensemble < 2 or not target_indices:
        return ensemble
    state_rows = []
    bindings = []
    for node_id in node_ids:
        members = ensemble[node_id]
        for state_index in target_indices:
            state_rows.append([float(member[state_index]) for member in members])
            bindings.append((node_id, state_index))
    forecast = np.asarray(state_rows, dtype=float)
    forecast_mean = np.mean(forecast, axis=1)
    state_anomalies = forecast - forecast_mean[:, None]

    y_forecast = np.asarray(predicted_observations, dtype=float)
    y_observed = np.asarray(observed_values, dtype=float)
    y_mean = np.mean(y_forecast, axis=1)
    y_anomalies = y_forecast - y_mean[:, None]
    innovation = y_observed - y_mean
    inverse_r = 1.0 / max(float(observation_variance), 1e-12)

    ensemble_system = (
        (n_ensemble - 1) * np.eye(n_ensemble)
        + inverse_r * (y_anomalies.T @ y_anomalies)
    )
    eigenvalues, eigenvectors = np.linalg.eigh(ensemble_system)
    eigenvalues = np.maximum(eigenvalues, 1e-12)
    inverse_system = (
        eigenvectors @ np.diag(1.0 / eigenvalues) @ eigenvectors.T
    )
    mean_weights = inverse_system @ (
        inverse_r * y_anomalies.T @ innovation
    )
    analysis_mean = forecast_mean + state_anomalies @ mean_weights
    transform = (
        eigenvectors
        @ np.diag(np.sqrt((n_ensemble - 1) / eigenvalues))
        @ eigenvectors.T
    )
    analysis = analysis_mean[:, None] + state_anomalies @ transform

    # Commit only after the complete analysis has been calculated from the
    # frozen forecast. No member can influence a later member's anomalies.
    for row, (node_id, state_index) in enumerate(bindings):
        for member_index in range(n_ensemble):
            ensemble[node_id][member_index][state_index] = float(
                analysis[row, member_index]
            )
    return ensemble


def _batch_scalar_etkf_target_update(
    ensemble: Any,
    node_ids: List[str],
    target_indices: List[int],
    predicted_observations: Any,
    observed_values: Any,
    observation_variance: float,
    node_positions: Any,
) -> Any:
    """Apply independent scalar ETKF updates without per-zone eigensolves.

    The local H_t contract collapses correlated pixels to one weighted scalar
    observation per microzone.  For that rank-one observation, the ETKF
    transform has a closed form: only the ensemble-anomaly direction parallel
    to the predicted observation is contracted.  Batching that exact transform
    avoids thousands of identical-size ``eigh`` calls on large plots while
    preserving the result of :func:`_etkf_target_update` for every zone.
    """
    import numpy as np

    positions = np.asarray(node_positions, dtype=int).reshape(-1)
    is_array = isinstance(ensemble, np.ndarray)
    if is_array:
        n_ensemble = ensemble.shape[1]
    else:
        n_ensemble = len(next(iter(ensemble.values()), []))
    if n_ensemble < 2 or not target_indices or positions.size == 0:
        return ensemble

    predicted = np.asarray(predicted_observations, dtype=float)
    observed = np.asarray(observed_values, dtype=float).reshape(-1)
    if predicted.shape != (positions.size, n_ensemble):
        raise ValueError("batched_scalar_etkf_prediction_shape_mismatch")
    if observed.shape != (positions.size,):
        raise ValueError("batched_scalar_etkf_observation_shape_mismatch")

    if is_array:
        forecast = ensemble[positions][:, :, target_indices].transpose(0, 2, 1)
    else:
        forecast = np.asarray(
            [
                [
                    [
                        float(ensemble[node_ids[position]][member][state_index])
                        for member in range(n_ensemble)
                    ]
                    for state_index in target_indices
                ]
                for position in positions
            ],
            dtype=float,
        )
    forecast_mean = np.mean(forecast, axis=2)
    state_anomalies = forecast - forecast_mean[:, :, None]
    predicted_mean = np.mean(predicted, axis=1)
    observation_anomalies = predicted - predicted_mean[:, None]
    innovation = observed - predicted_mean

    inverse_r = 1.0 / max(float(observation_variance), 1e-12)
    anomaly_energy = np.einsum(
        "zn,zn->z", observation_anomalies, observation_anomalies,
    )
    cross_anomaly = np.einsum(
        "ztn,zn->zt", state_anomalies, observation_anomalies,
    )
    denominator = (n_ensemble - 1) + inverse_r * anomaly_energy
    analysis_mean = forecast_mean + (
        cross_anomaly
        * (inverse_r * innovation / denominator)[:, None]
    )

    contraction = np.sqrt((n_ensemble - 1) / denominator)
    projection_scale = np.zeros_like(anomaly_energy)
    nonzero = anomaly_energy > 1e-15
    projection_scale[nonzero] = (
        contraction[nonzero] - 1.0
    ) / anomaly_energy[nonzero]
    analysis_anomalies = state_anomalies + (
        projection_scale[:, None, None]
        * cross_anomaly[:, :, None]
        * observation_anomalies[:, None, :]
    )
    analysis = analysis_mean[:, :, None] + analysis_anomalies

    # Publish only after the entire analysis has been calculated from the
    # frozen forecast, retaining ensemble-member order equivariance.
    if is_array:
        analysis_t = analysis.transpose(0, 2, 1)
        for t_off, s_idx in enumerate(target_indices):
            ensemble[positions, :, s_idx] = analysis_t[:, :, t_off]
    else:
        for zone_offset, position in enumerate(positions):
            node_id = node_ids[int(position)]
            for target_offset, state_index in enumerate(target_indices):
                for member_index in range(n_ensemble):
                    ensemble[node_id][member_index][state_index] = float(
                        analysis[zone_offset, target_offset, member_index]
                    )
    return ensemble


def _predict_observation_array(
    observation_name: str,
    states: Any,
    sensor: str,
):
    """Evaluate the scalar forward-model equations over a state cube.

    ``states`` has shape ``(..., N_STATES)``.  This is deliberately kept in
    this assimilation module so the hot path does not perform a Python call
    for every zone/member pair.  The equations and clipping are identical to
    the authoritative S1/S2 scalar forward models.
    """
    import numpy as np

    values = np.asarray(states, dtype=float)
    if values.ndim < 2 or values.shape[-1] < N_STATES:
        raise ValueError("forward_model_state_cube_shape_mismatch")

    indices = {name: index for index, name in enumerate(STATE_NAMES)}
    name = str(observation_name or "").lower()
    sensor_name = str(sensor or "").upper()

    if sensor_name == "S1":
        surface_wetness = values[..., indices["surface_wetness_event"]]
        root_zone_water = values[..., indices["root_zone_water"]]
        structure = values[..., indices["structure"]]
        bare_soil = values[..., indices["bare_soil_fraction"]]
        if name == "sar_vv":
            prediction = (
                0.35 * structure
                + 0.25 * surface_wetness
                + 0.2 * root_zone_water
                + 0.1 * bare_soil
                + 0.05
            )
        elif name == "sar_vh":
            prediction = 0.6 * structure + 0.2 * surface_wetness + 0.1
        elif name == "sar_ratio":
            prediction = 0.65 * structure + 0.10 * surface_wetness + 0.05
        elif name == "delta_sar":
            prediction = 0.5 * surface_wetness + 0.3 * bare_soil
        else:
            return None
        return np.clip(prediction, 0.0, 1.0)

    vigor = values[..., indices["vigor"]]
    lai = values[..., indices["lai"]]
    chlorophyll = values[..., indices["chlorophyll"]]
    canopy_water = values[..., indices["canopy_water"]]
    surface_wetness = values[..., indices["surface_wetness_event"]]
    bare_soil = values[..., indices["bare_soil_fraction"]]
    if name == "ndvi":
        prediction = (
            0.7 * vigor + 0.2 * np.minimum(lai / 5.0, 1.0)
            - 0.3 * bare_soil + 0.1
        )
    elif name == "evi":
        prediction = (
            0.35 * vigor + 0.15 * np.minimum(lai / 6.0, 1.0)
            - 0.20 * bare_soil + 0.05
        )
    elif name == "ndre":
        prediction = (
            0.30 * np.minimum(chlorophyll / 60.0, 1.0)
            + 0.15 * np.minimum(lai / 5.0, 1.0)
            - 0.15 * bare_soil + 0.05
        )
    elif name == "ndmi":
        prediction = 0.6 * canopy_water + 0.2 * np.minimum(lai / 5.0, 1.0) + 0.05
    elif name == "ndwi":
        prediction = (
            -0.65 * vigor - 0.20 * bare_soil + 0.6 * surface_wetness - 0.05
        )
    elif name == "bsi":
        prediction = 0.6 * bare_soil - 0.3 * vigor
    elif name == "ndsi":
        salinity = values[..., indices["salinity_stress"]]
        prediction = 0.55 * salinity + 0.35 * bare_soil - 0.20 * vigor
    elif name == "cwsi":
        pred_ndvi = (
            0.7 * vigor + 0.2 * np.minimum(lai / 5.0, 1.0)
            - 0.3 * bare_soil + 0.1
        )
        pred_ndmi = 0.6 * canopy_water + 0.2 * np.minimum(lai / 5.0, 1.0) + 0.05
        denom = np.maximum(pred_ndvi, 0.05)
        prediction = 1.0 - (pred_ndmi + 0.2) / denom
    elif name == "phenology_index":
        prediction = (
            0.30 * np.minimum(chlorophyll / 60.0, 1.0)
            + 0.15 * np.minimum(lai / 5.0, 1.0)
            - 0.15 * bare_soil + 0.05
        )
    elif name == "stress_memory_index":
        memory = values[..., indices["stress_memory"]]
        salinity = values[..., indices["salinity_stress"]]
        prediction = 0.65 * memory + 0.35 * salinity
    elif name == "biotic_anomaly":
        biotic = values[..., indices["biotic_confounder_risk"]]
        prediction = 0.75 * biotic - 0.25 * vigor
    else:
        return None
    return np.clip(prediction, -1.0, 1.0)


def update_step_ht(
    ensemble: Any,
    scene: Any,
    operator: Any,
    rng: random.Random,
    deadline_check: Optional[Callable[[], None]] = None,
    node_ids: Optional[List[str]] = None,
) -> Tuple[Any, List[Dict[str, Any]]]:
    import numpy as np

    from ..observation.index_state_mapping import (
        INDEX_STATE_REGISTRY, validate_forbidden_state_update,
    )
    from ..observation.observation_noise import compute_observation_noise
    from ..observation.pixel_extraction import extract_pixel_observations

    if str(getattr(operator, 'scene_id', '')) != str(getattr(scene, 'scene_id', '')):
        raise ValueError('scene_operator_identity_mismatch')
    scene_support = str(getattr(scene, 'valid_support_hash', '') or '')
    if not scene_support or scene_support != str(getattr(operator, 'valid_support_hash', '') or ''):
        raise ValueError('scene_operator_support_mismatch')
    h_matrix = getattr(operator, 'H_matrix', None)
    if h_matrix is None:
        raise ValueError('missing_h_matrix')

    observations = extract_pixel_observations(scene)
    is_ndarray = isinstance(ensemble, np.ndarray)
    if is_ndarray:
        state_cube = ensemble
        n_nodes = state_cube.shape[0]
        n_ensemble = state_cube.shape[1]
        if node_ids is None:
            node_ids = getattr(operator, 'node_ids', None) or [f"mz_{i}" for i in range(n_nodes)]
    else:
        if node_ids is None:
            node_ids = list(ensemble.keys())
        n_nodes = len(node_ids)
        n_ensemble = len(next(iter(ensemble.values()), []))
        state_cube = np.asarray(
            [ensemble[node_id] for node_id in node_ids], dtype=float,
        )
    reports: List[Dict[str, Any]] = []
    for obs_name in sorted(observations):
        if deadline_check is not None:
            deadline_check()
        pixel_observation = observations[obs_name]
        mapping = INDEX_STATE_REGISTRY.get(obs_name)
        if mapping is None:
            continue
        from ..state.descriptors import STATE_DESCRIPTORS, AssimilationPolicy
        target_indices = [
            index for index in mapping.target_state_indices
            if 0 <= index < len(STATE_NAMES)
            and not validate_forbidden_state_update(obs_name, index)
            and STATE_DESCRIPTORS[index].assimilation_policy != AssimilationPolicy.NOT_ASSIMILATED
        ]
        target_states = [STATE_NAMES[index] for index in target_indices]
        if not target_indices:
            reports.append({
                'obs_name': obs_name,
                'sensor': mapping.sensor,
                'mode': 'excluded_forbidden_or_not_assimilated',
                'update_applied': False,
                'target_states': [STATE_NAMES[i] for i in mapping.target_state_indices if 0 <= i < len(STATE_NAMES)],
                'failure_reason': 'forbidden_or_not_assimilated',
            })
            continue
        if not pixel_observation.is_per_pixel or pixel_observation.n_pixels != h_matrix.shape[0]:
            reports.append({
                'obs_name': obs_name,
                'sensor': mapping.sensor,
                'mode': 'excluded_pixel_geometry_mismatch',
                'update_applied': False,
                'target_states': target_states,
                'failure_reason': 'observation_vector_must_exactly_match_h_rows',
            })
            continue

        zone_predictions = _predict_observation_array(
            obs_name, state_cube, mapping.sensor,
        )
        if zone_predictions is None or not np.all(np.isfinite(zone_predictions)):
            reports.append({
                'obs_name': obs_name,
                'sensor': mapping.sensor,
                'mode': 'excluded_missing_forward_model',
                'update_applied': False,
                'target_states': target_states,
                'failure_reason': 'missing_forward_model',
            })
            continue

        zone_predictions = np.asarray(zone_predictions, dtype=float)
        if h_matrix.shape[1] != n_nodes:
            raise ValueError('h_matrix_node_count_mismatch')
        pixel_predictions = np.asarray(h_matrix @ zone_predictions, dtype=float)
        observed = np.asarray(pixel_observation.values, dtype=float)
        valid = np.asarray(pixel_observation.valid_mask, dtype=bool)
        valid &= np.isfinite(observed)
        valid &= np.all(np.isfinite(pixel_predictions), axis=1)
        valid_indices = np.flatnonzero(valid)
        if valid_indices.size == 0:
            reports.append({
                'obs_name': obs_name,
                'sensor': mapping.sensor,
                'mode': 'excluded_no_valid_pixels',
                'update_applied': False,
                'target_states': target_states,
                'failure_reason': 'no_valid_pixels',
            })
            continue

        sigma_observation = compute_observation_noise(
            obs_name,
            crop_stage=str(getattr(scene, 'crop_stage', '') or ''),
            cloud_fraction=float(getattr(scene, 'cloud_fraction', 0.0) or 0.0),
            valid_support_fraction=float(getattr(scene, 'valid_fraction', 0.0) or 0.0),
            registration_uncertainty_m=float(
                getattr(operator, 'registration_uncertainty_m', 0.0) or 0.0
            ),
            temporal_aggregation_days=float(
                getattr(scene, 'temporal_aggregation_days', 1.0) or 1.0
            ),
        )
        prior_variance = _state_variance_summary(state_cube, target_indices)
        prior_mean = _state_mean_summary(state_cube, target_indices)
        valid_predictions = pixel_predictions[valid_indices, :]
        valid_observed = observed[valid_indices]
        prediction_mean = np.mean(valid_predictions, axis=1)
        innovation = valid_observed - prediction_mean
        # Local deterministic ETKF: each zone is conditioned only by pixels
        # whose immutable H_t support overlaps that zone. Pixels are collapsed
        # to one H-weighted observation per zone, avoiding the false precision
        # of treating adjacent raster pixels as independent measurements.
        # Aggregate every zone's immutable H_t support in two sparse/dense
        # matrix products, then apply the exact scalar ETKF transform in one
        # batch. This is mathematically identical to the former per-zone loop
        # but bounded for interactive worker execution.
        local_support = h_matrix[valid_indices, :]
        if hasattr(local_support, "maximum") and hasattr(local_support, "tocsr"):
            local_support = local_support.maximum(0.0).tocsr()
            support_sums = np.asarray(local_support.sum(axis=0)).reshape(-1)
        else:
            local_support = np.maximum(np.asarray(local_support, dtype=float), 0.0)
            support_sums = np.sum(local_support, axis=0)
        active_positions = np.flatnonzero(support_sums > 1e-12)
        localized_updates = int(active_positions.size)
        if localized_updates == 0:
            reports.append({
                'obs_name': obs_name,
                'sensor': mapping.sensor,
                'mode': 'excluded_zero_localized_support',
                'update_applied': False,
                'target_states': target_states,
                'failure_reason': 'zero_localized_support',
            })
            continue

        weighted_observed = np.asarray(
            local_support.T @ valid_observed, dtype=float,
        ).reshape(-1)
        active_sums = support_sums[active_positions]
        # Construct predictions in consistent observation space (H-weighted support matching local_observed)
        # to guarantee that zero innovation produces zero mean adjustment.
        weighted_predictions = np.asarray(
            local_support.T @ valid_predictions, dtype=float,
        )
        local_predictions = (
            weighted_predictions[active_positions, :] / active_sums[:, None]
        )
        local_observed = (
            weighted_observed[active_positions] / active_sums
        )
        step_prior_cube = state_cube.copy()
        state_cube = _batch_scalar_etkf_target_update(
            state_cube,
            node_ids,
            target_indices,
            local_predictions,
            local_observed,
            sigma_observation * sigma_observation,
            active_positions,
        )
        if deadline_check is not None:
            deadline_check()
        posterior_variance = _state_variance_summary(state_cube, target_indices)
        posterior_mean = _state_mean_summary(state_cube, target_indices)
        information_gain = {
            state: max(0.0, prior - posterior_variance.get(state, prior))
            for state, prior in prior_variance.items()
        }

        # Qualify actual per-state influence
        per_state_influence: Dict[str, Dict[str, Any]] = {}
        has_actual_influence = False
        for state_index in target_indices:
            state_name = STATE_NAMES[state_index]
            desc = STATE_DESCRIPTORS[state_index]
            scale = (desc.bounds[1] - desc.bounds[0]) if (desc.bounds and desc.bounds[1] > desc.bounds[0]) else 1.0

            # Per-node spatial evaluation to prevent opposite local innovations cancelling in the global mean
            step_prior_node_means = np.mean(step_prior_cube[:, :, state_index], axis=1)
            post_node_means = np.mean(state_cube[:, :, state_index], axis=1)
            max_node_delta_mean = float(np.max(np.abs(post_node_means - step_prior_node_means)))
            
            step_prior_node_vars = np.var(step_prior_cube[:, :, state_index], axis=1)
            post_node_vars = np.var(state_cube[:, :, state_index], axis=1)
            max_node_var_red = float(np.max(np.maximum(0.0, step_prior_node_vars - post_node_vars)))

            tol_mean = 1e-5 * scale
            tol_var = 1e-7 * (scale ** 2)
            state_influenced = (max_node_delta_mean > tol_mean) or (max_node_var_red > tol_var)
            if state_influenced:
                has_actual_influence = True
            per_state_influence[state_name] = {
                'delta_mean': float(max_node_delta_mean),
                'variance_reduction': float(max_node_var_red),
                'state_influenced': state_influenced,
            }

        if not has_actual_influence:
            reports.append({
                'obs_name': obs_name,
                'sensor': mapping.sensor,
                'mode': 'excluded_negligible_influence',
                'update_applied': False,
                'target_states': target_states,
                'failure_reason': 'negligible_influence',
                'per_state_influence': per_state_influence,
            })
            continue

        # Determine directness from measurement/operator receipt and descriptor policy
        is_receipt_direct = bool(
            getattr(operator, 'is_direct_measurement', False)
            or getattr(pixel_observation, 'is_direct_measurement', False)
        )
        target_descs = [STATE_DESCRIPTORS[idx] for idx in target_indices]
        allows_direct = all(d.assimilation_policy == AssimilationPolicy.DIRECT_OBSERVATION for d in target_descs)
        if is_receipt_direct and allows_direct:
            evidence_kind = 'direct_observation'
        else:
            evidence_kind = 'indirect_observation'

        reports.append({
            'obs_name': obs_name,
            'sensor': mapping.sensor,
            'obs_mean': float(np.mean(valid_observed)),
            'pred_mean': float(np.mean(prediction_mean)),
            'innovation_mean': float(np.mean(innovation)),
            'n_pixels': int(valid_indices.size),
            'sigma_obs': float(sigma_observation),
            'mode': 'ht_per_pixel_ensrf',
            'update_applied': True,
            'target_states': target_states,
            'accepted_target_states': [s for s in target_states if per_state_influence.get(s, {}).get('state_influenced', False)],
            'excluded_target_states': [s for s in target_states if not per_state_influence.get(s, {}).get('state_influenced', False)],
            'evidence_kind': evidence_kind,
            'prior_variance': prior_variance,
            'posterior_variance': posterior_variance,
            'information_gain': information_gain,
            'information_gain_fraction': {
                state: gain / prior_variance[state] if prior_variance[state] > 1e-12 else 0.0
                for state, gain in information_gain.items()
            },
            'kalman_gain_summary': {
                'kind': 'localized_deterministic_etkf_support_aggregate',
                'ensemble_size': n_ensemble,
                'localized_zone_updates': localized_updates,
                'correlated_pixel_policy': 'one_weighted_observation_per_zone',
            },
            'per_state_influence': per_state_influence,
        })

    if is_ndarray:
        return state_cube, reports
    for position, node_id in enumerate(node_ids):
        ensemble[node_id] = state_cube[position].tolist()
    return ensemble, reports


def update_step_proxy(
    ensemble: Dict[str, List[List[float]]],
    scene: Any,
    operator: Any,
    rng: random.Random,
) -> Tuple[Dict[str, List[List[float]]], List[Dict[str, Any]]]:
    """V74 original: Proxy mean-level update (no Hₜ).

    Each microzone is updated independently using global scene means.
    Flagged as proxy_mean_level.
    """
    from ..observation.s2_forward_model import predict_observation
    from ..observation.s1_sar_model import predict_sar_observation
    from ..observation.observation_noise import compute_observation_noise
    from ..observation.index_state_mapping import (
        INDEX_STATE_REGISTRY, validate_forbidden_state_update,
    )

    available_obs = _extract_observations_from_scene(scene)
    if not available_obs:
        return ensemble, []

    node_ids = list(ensemble.keys())
    reports = []

    for obs_name, obs_value in available_obs.items():
        mapping = INDEX_STATE_REGISTRY.get(obs_name)
        if mapping is None:
            continue
        target_indices = [
            state_index for state_index in mapping.target_state_indices
            if 0 <= state_index < len(STATE_NAMES)
            and not validate_forbidden_state_update(obs_name, state_index)
            and STATE_DESCRIPTORS[state_index].assimilation_policy != AssimilationPolicy.NOT_ASSIMILATED
        ]
        if not target_indices:
            reports.append({
                "obs_name": obs_name,
                "sensor": mapping.sensor,
                "mode": "excluded_forbidden_state",
                "update_applied": False,
                "target_states": [STATE_NAMES[s] for s in mapping.target_state_indices if 0 <= s < len(STATE_NAMES)],
                "failure_reason": "not_assimilated_policy",
            })
            continue

        target_states = [STATE_NAMES[state_index] for state_index in target_indices]
        sigma_obs = compute_observation_noise(
            obs_name,
            crop_stage=str(getattr(scene, "crop_stage", "") or ""),
            cloud_fraction=float(getattr(scene, "cloud_fraction", 0.0) or 0.0),
            valid_support_fraction=float(getattr(scene, "valid_fraction", 1.0) or 0.0),
            registration_uncertainty_m=float(getattr(scene, "registration_uncertainty_m", 0.0) or 0.0),
            temporal_aggregation_days=float(getattr(scene, "temporal_aggregation_days", 1.0) or 1.0),
        )
        r_var = sigma_obs * sigma_obs

        # Calculate pred_mean before update
        n_ens = len(next(iter(ensemble.values()), []))
        pred_obs_list = []
        if n_ens > 0:
            for nid in node_ids:
                for member in ensemble[nid]:
                    if mapping.sensor == "S1":
                        pred = predict_sar_observation(obs_name, member)
                    else:
                        pred = predict_observation(obs_name, member)
                    if pred is None:
                        pred_obs_list = []
                        break
                    pred_obs_list.append(pred)
                if not pred_obs_list:
                    break
            if not pred_obs_list:
                reports.append({
                    "obs_name": obs_name,
                    "sensor": mapping.sensor,
                    "mode": "excluded_missing_forward_model",
                    "update_applied": False,
                    "target_states": target_states,
                    "failure_reason": "missing_forward_model",
                })
                continue
            pred_mean = sum(pred_obs_list) / len(pred_obs_list)
        else:
            continue

        prior_mean = _state_mean_summary(ensemble, target_indices)
        prior_variance = _state_variance_summary(ensemble, target_indices)
        step_prior_ensemble = {k: [row[:] for row in v] for k, v in ensemble.items()}
        _proxy_update_single_obs(ensemble, node_ids, obs_name, obs_value,
                                 mapping, sigma_obs, r_var, rng, target_indices=target_indices)
        posterior_mean = _state_mean_summary(ensemble, target_indices)
        posterior_variance = _state_variance_summary(ensemble, target_indices)

        # Qualify actual per-state influence
        per_state_influence: Dict[str, Dict[str, Any]] = {}
        has_actual_influence = False
        for state_index in target_indices:
            state_name = STATE_NAMES[state_index]
            desc = STATE_DESCRIPTORS[state_index]
            scale = (desc.bounds[1] - desc.bounds[0]) if (desc.bounds and desc.bounds[1] > desc.bounds[0]) else 1.0

            # Per-node spatial evaluation for proxy update
            node_prior_means = [sum(row[state_index] for row in step_prior_ensemble[nid]) / len(step_prior_ensemble[nid]) for nid in node_ids]
            node_post_means = [sum(row[state_index] for row in ensemble[nid]) / len(ensemble[nid]) for nid in node_ids]
            max_node_delta_mean = float(max(abs(post_m - pri_m) for post_m, pri_m in zip(node_post_means, node_prior_means)))
            
            node_prior_vars = [sum((row[state_index] - pri_m)**2 for row in step_prior_ensemble[nid]) / len(step_prior_ensemble[nid]) for nid, pri_m in zip(node_ids, node_prior_means)]
            node_post_vars = [sum((row[state_index] - post_m)**2 for row in ensemble[nid]) / len(ensemble[nid]) for nid, post_m in zip(node_ids, node_post_means)]
            max_node_var_red = float(max(max(0.0, pri_v - post_v) for pri_v, post_v in zip(node_prior_vars, node_post_vars)))

            tol_mean = 1e-5 * scale
            tol_var = 1e-7 * (scale ** 2)
            state_influenced = (max_node_delta_mean > tol_mean) or (max_node_var_red > tol_var)
            if state_influenced:
                has_actual_influence = True
            per_state_influence[state_name] = {
                'delta_mean': float(max_node_delta_mean),
                'variance_reduction': float(max_node_var_red),
                'state_influenced': state_influenced,
            }

        if not has_actual_influence:
            reports.append({
                'obs_name': obs_name,
                'sensor': mapping.sensor,
                'mode': 'excluded_negligible_influence',
                'update_applied': False,
                'target_states': target_states,
                'failure_reason': 'negligible_influence',
                'per_state_influence': per_state_influence,
            })
            continue

        reports.append({
            "obs_name": obs_name,
            "sensor": mapping.sensor,
            "obs_mean": float(obs_value),
            "pred_mean": float(pred_mean),
            "innovation_mean": float(obs_value - pred_mean),
            "n_pixels": 1,
            "sigma_obs": float(sigma_obs),
            "mode": "proxy_mean_level",
            "update_applied": True,
            "target_states": target_states,
            "accepted_target_states": [s for s in target_states if per_state_influence.get(s, {}).get('state_influenced', False)],
            "excluded_target_states": [s for s in target_states if not per_state_influence.get(s, {}).get('state_influenced', False)],
            "evidence_kind": "proxy_observation",
            "prior_variance": prior_variance,
            "posterior_variance": posterior_variance,
            "per_state_influence": per_state_influence,
            "information_gain": {
                state: max(0.0, prior - posterior_variance.get(state, prior))
                for state, prior in prior_variance.items()
            },
        })

    return ensemble, reports


def _legacy_stochastic_proxy_update_single_obs(
    ensemble, node_ids, obs_name, obs_value,
    mapping, sigma_obs, r_var, rng,
):
    """Proxy update for a single observation across all microzones."""
    from ..observation.s2_forward_model import predict_observation
    from ..observation.s1_sar_model import predict_sar_observation
    from ..observation.index_state_mapping import validate_forbidden_state_update

    for nid in node_ids:
        members = ensemble[nid]
        n_ens = len(members)
        if n_ens == 0:
            continue

        # Predicted obs per member
        pred_obs = []
        for member in members:
            if mapping.sensor == "S1":
                pred = predict_sar_observation(obs_name, member)
            else:
                pred = predict_observation(obs_name, member)
            pred_obs.append(pred if pred is not None else obs_value)

        pred_mean = sum(pred_obs) / n_ens
        pred_var = sum((p - pred_mean) ** 2 for p in pred_obs) / max(n_ens - 1, 1)

        if pred_var < 1e-10:
            continue

        for s_idx in range(N_STATES):
            if validate_forbidden_state_update(obs_name, s_idx):
                continue
            if s_idx not in mapping.target_state_indices:
                continue

            state_mean = sum(m[s_idx] for m in members) / n_ens
            cross_cov = sum(
                (m[s_idx] - state_mean) * (pred_obs[j] - pred_mean)
                for j, m in enumerate(members)
            ) / max(n_ens - 1, 1)

            k_gain = cross_cov / (pred_var + r_var)

            for j, member in enumerate(members):
                member_innovation = (obs_value + rng.gauss(0, sigma_obs)) - pred_obs[j]
                member[s_idx] += k_gain * member_innovation


# ── Bounds Enforcement ───────────────────────────────────────────────────────


def _proxy_update_single_obs(
    ensemble, node_ids, obs_name, obs_value,
    mapping, sigma_obs, r_var, rng, target_indices=None,
):
    from ..observation.index_state_mapping import validate_forbidden_state_update
    from ..observation.s1_sar_model import predict_sar_observation
    from ..observation.s2_forward_model import predict_observation

    if target_indices is None:
        target_indices = [
            s for s in mapping.target_state_indices
            if 0 <= s < len(STATE_NAMES)
            and not validate_forbidden_state_update(obs_name, s)
            and STATE_DESCRIPTORS[s].assimilation_policy != AssimilationPolicy.NOT_ASSIMILATED
        ]

    for node_id in node_ids:
        members = ensemble[node_id]
        n_ensemble = len(members)
        if n_ensemble < 2:
            continue
        predicted = []
        for member in members:
            value = (
                predict_sar_observation(obs_name, member)
                if mapping.sensor == 'S1'
                else predict_observation(obs_name, member)
            )
            if value is None or not math.isfinite(float(value)):
                predicted = []
                break
            predicted.append(float(value))
        if not predicted:
            continue
        prediction_mean = sum(predicted) / n_ensemble
        prediction_anomalies = [value - prediction_mean for value in predicted]
        prediction_variance = sum(value * value for value in prediction_anomalies) / (
            n_ensemble - 1
        )
        total_variance = prediction_variance + r_var
        if prediction_variance < 1e-12 or total_variance <= 0.0:
            continue
        shrink = 1.0 / (1.0 + math.sqrt(max(r_var, 0.0) / total_variance))
        for state_index in target_indices:
            if validate_forbidden_state_update(obs_name, state_index):
                continue
            if STATE_DESCRIPTORS[state_index].assimilation_policy == AssimilationPolicy.NOT_ASSIMILATED:
                continue
            state_values = [float(member[state_index]) for member in members]
            state_mean = sum(state_values) / n_ensemble
            state_anomalies = [value - state_mean for value in state_values]
            covariance = sum(
                state_anomalies[index] * prediction_anomalies[index]
                for index in range(n_ensemble)
            ) / (n_ensemble - 1)
            gain = covariance / total_variance
            analysis_mean = state_mean + gain * (float(obs_value) - prediction_mean)
            analysis_values = [
                analysis_mean + state_anomalies[index]
                - shrink * gain * prediction_anomalies[index]
                for index in range(n_ensemble)
            ]
            for index, value in enumerate(analysis_values):
                members[index][state_index] = value


_STATE_LOWS = np.array([STATE_BOUNDS[name][0] for name in STATE_NAMES], dtype=float)
_STATE_HIGHS = np.array([STATE_BOUNDS[name][1] for name in STATE_NAMES], dtype=float)


def clamp_ensemble(
    ensemble: Any,
) -> Any:
    """Clamp all ensemble members to physical bounds."""
    if isinstance(ensemble, np.ndarray):
        np.clip(ensemble, _STATE_LOWS, _STATE_HIGHS, out=ensemble)
        return ensemble
    for nid, members in ensemble.items():
        for member in members:
            for i, name in enumerate(STATE_NAMES):
                lo, hi = STATE_BOUNDS[name]
                member[i] = max(lo, min(hi, member[i]))
    return ensemble


# ── Statistics ───────────────────────────────────────────────────────────────


def compute_ensemble_statistics(
    ensemble: Any,
    node_ids: List[str],
) -> dict:
    """Compute means and standard deviations for each state per microzone."""
    if isinstance(ensemble, np.ndarray):
        m_vals = np.mean(ensemble, axis=1)
        s_vals = np.std(ensemble, axis=1, ddof=1) if ensemble.shape[1] > 1 else np.zeros_like(m_vals)
        means = dict(zip(node_ids, m_vals.tolist()))
        sigmas = dict(zip(node_ids, s_vals.tolist()))
        return {"means": means, "sigmas": sigmas}

    means: Dict[str, List[float]] = {}
    sigmas: Dict[str, List[float]] = {}

    for nid in node_ids:
        members = ensemble.get(nid, [])
        n = len(members)
        if n == 0:
            means[nid] = [0.0] * N_STATES
            sigmas[nid] = [0.1] * N_STATES
            continue

        m_vals = [0.0] * N_STATES
        for member in members:
            for s in range(N_STATES):
                m_vals[s] += member[s]
        m_vals = [v / n for v in m_vals]

        s_vals = [0.0] * N_STATES
        for member in members:
            for s in range(N_STATES):
                s_vals[s] += (member[s] - m_vals[s]) ** 2
        s_vals = [math.sqrt(v / max(n - 1, 1)) for v in s_vals]

        means[nid] = [round(v, 6) for v in m_vals]
        sigmas[nid] = [round(v, 6) for v in s_vals]

    return {"means": means, "sigmas": sigmas}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_node_ids(graph: Any) -> List[str]:
    """Extract ordered node IDs from graph."""
    if hasattr(graph, "node_ids_ordered"):
        return graph.node_ids_ordered()
    if isinstance(graph, dict):
        n_rows = graph.get("n_rows", 3)
        n_cols = graph.get("n_cols", 3)
        return [f"mz_{r:03d}_{c:03d}" for r in range(n_rows) for c in range(n_cols)]
    return ["mz_000_000"]


def _pair_scenes_operators(
    scenes: list, operators: list,
) -> List[Tuple[Any, Any]]:
    """Pair scenes with their operators."""
    from ..chain_integrity import assert_scene_operator_binding

    assert_scene_operator_binding(scenes or [], operators or [], stage_name='EnKF')
    return list(zip(scenes, operators))


def _extract_observations_from_scene(scene: Any) -> Dict[str, float]:
    """Extract index observations from a scene."""
    from ..observation.pixel_extraction import extract_pixel_observations

    pixel_observations = extract_pixel_observations(scene)
    return {
        name: float(observation.mean)
        for name, observation in pixel_observations.items()
        if observation.n_valid > 0 and math.isfinite(float(observation.mean))
    }
