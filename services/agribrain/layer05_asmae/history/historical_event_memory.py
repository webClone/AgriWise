"""Historical Event Reconstruction & Scientific Memory (Observations vs Hypotheses + Outcomes).

Detects multi-year agronomic events chronologically across assimilated 13-state trajectories,
ERA5 weather series, and optional external management logs while strictly separating
direct observed triggers from model-inferred hypotheses and measuring subsequent outcomes.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _parse_dt(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _extract_mgmt_days(management_events: Optional[List[Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Index qualified applied external management records by YYYY-MM-DD."""
    by_day: Dict[str, List[Dict[str, Any]]] = {}
    for ev in management_events or []:
        if isinstance(ev, dict):
            ev_type = str(ev.get("type") or ev.get("event_type") or "").lower()
            status = str(ev.get("status") or ev.get("execution_status") or "applied").lower()
            raw_dt = ev.get("effective_start") or ev.get("timestamp") or ev.get("date")
            amt = ev.get("amount_mm") or ev.get("volume_mm") or ev.get("quantity")
        else:
            ev_type = str(getattr(ev, "event_type", None) or getattr(ev, "type", "") or "").lower()
            status = str(getattr(ev, "execution_status", None) or getattr(ev, "status", "applied") or "applied").lower()
            raw_dt = getattr(ev, "effective_start", None) or getattr(ev, "timestamp", None) or getattr(ev, "date", None)
            amt = getattr(ev, "quantity", None) or getattr(ev, "amount_mm", None)
        if not raw_dt or status in {"planned", "cancelled", "canceled", "draft", "proposed", "pending", "failed"}:
            continue
        day_str = raw_dt.strftime("%Y-%m-%d") if hasattr(raw_dt, "strftime") else str(raw_dt)[:10]
        by_day.setdefault(day_str, []).append({
            "type": ev_type,
            "status": status,
            "amount_mm": float(amt) if isinstance(amt, (int, float)) else None,
        })
    return by_day


@dataclass
class ReconstructedMemoryEvent:
    event_id: str
    event_category: str          # planting_emergence | candidate_irrigation | irrigation | rainfall_response | canopy_change | stress_onset | recovery
    epistemic_class: str         # "observed_event" | "model_hypothesis"
    hypothesis_status: str       # "observed" | "suspected" | "supported" | "contradicted" | "unresolved_insufficient_followup"
    start_time: str
    peak_time: str
    end_time: str
    season_year: int
    severity: float
    confidence: float
    trigger_evidence: Dict[str, Any] = field(default_factory=dict)
    outcome_measurement: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HistoricalEventMemory:
    """Reconstructs chronological agronomic events and measures post-event outcomes."""

    def __init__(
        self,
        rain_threshold_mm: float = 8.0,
        irrigation_sar_jump_db: float = 1.6,
        canopy_change_threshold: float = 0.12,
        followup_days: int = 21,
    ) -> None:
        self.rain_threshold_mm = rain_threshold_mm
        self.irrigation_sar_jump_db = irrigation_sar_jump_db
        self.canopy_change_threshold = canopy_change_threshold
        self.followup_days = followup_days

    def reconstruct_memory(
        self,
        trajectory: List[Dict[str, Any]],
        context_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Detect observed events & hypotheses across trajectory and score outcomes."""
        ctx = context_summary or {}
        daily_weather: Dict[str, Dict[str, Any]] = dict(ctx.get("daily_weather") or {})
        mgmt_by_day = _extract_mgmt_days(ctx.get("management_events"))

        if not trajectory:
            return {
                "events": [],
                "summary": {
                    "total_events": 0,
                    "observed_events_count": 0,
                    "hypothesis_events_count": 0,
                    "supported_hypotheses_count": 0,
                    "contradicted_hypotheses_count": 0,
                    "by_category": {},
                },
            }

        sorted_traj = sorted(trajectory, key=lambda r: str(r.get("acquisition_time") or ""))
        parsed_times = [_parse_dt(r["acquisition_time"]) for r in sorted_traj]
        t_min, t_max = parsed_times[0], parsed_times[-1]

        events: List[ReconstructedMemoryEvent] = []
        seq_counter = 1

        # 1. Observed rainfall pulses & meteorological water-deficit stress windows
        cur_day = t_min.date()
        end_day = t_max.date()
        deficit_streak = 0
        deficit_accum = 0.0
        deficit_start: Optional[datetime] = None

        while cur_day <= end_day:
            d_str = cur_day.isoformat()
            w = daily_weather.get(d_str)
            day_dt = datetime.combine(cur_day, datetime.min.time(), tzinfo=timezone.utc)
            if isinstance(w, dict):
                precip = w.get("precipitation")
                et0 = w.get("et0")
                if isinstance(precip, (int, float)) and float(precip) >= self.rain_threshold_mm:
                    # Group daily heavy rain pulses without over-counting adjacent days unless separated
                    if not (events and events[-1].event_category == "rainfall_response"
                            and (_parse_dt(events[-1].end_time).date() >= cur_day - timedelta(days=1))):
                        events.append(ReconstructedMemoryEvent(
                            event_id=f"mem_rain_{seq_counter:04d}",
                            event_category="rainfall_response",
                            epistemic_class="observed_event",
                            hypothesis_status="observed",
                            start_time=day_dt.isoformat(),
                            peak_time=day_dt.isoformat(),
                            end_time=(day_dt + timedelta(days=1)).isoformat(),
                            season_year=cur_day.year,
                            severity=round(min(1.0, float(precip) / 40.0), 4),
                            confidence=0.95,
                            trigger_evidence={
                                "source": "era5_reanalysis_precipitation",
                                "precipitation_mm": round(float(precip), 2),
                                "et0_mm": round(float(et0), 2) if isinstance(et0, (int, float)) else None,
                            },
                        ))
                        seq_counter += 1
                    if float(precip) >= 12.0:
                        deficit_streak = 0
                        deficit_accum = 0.0
                        deficit_start = None

                if isinstance(precip, (int, float)) and isinstance(et0, (int, float)):
                    net_def = max(0.0, float(et0) - float(precip))
                    if net_def >= 2.0:
                        if deficit_streak == 0:
                            deficit_start = day_dt
                        deficit_streak += 1
                        deficit_accum += net_def
                    else:
                        if deficit_streak >= 10 and deficit_accum >= 40.0 and deficit_start is not None:
                            mid_dt = deficit_start + timedelta(days=deficit_streak // 2)
                            events.append(ReconstructedMemoryEvent(
                                event_id=f"mem_stress_{seq_counter:04d}",
                                event_category="stress_onset",
                                epistemic_class="model_hypothesis",
                                hypothesis_status="suspected",
                                start_time=deficit_start.isoformat(),
                                peak_time=mid_dt.isoformat(),
                                end_time=day_dt.isoformat(),
                                season_year=deficit_start.year,
                                severity=round(min(1.0, deficit_accum / 100.0), 4),
                                confidence=0.72,
                                trigger_evidence={
                                    "deficit_days": deficit_streak,
                                    "cumulative_et0_minus_precip_mm": round(deficit_accum, 2),
                                },
                            ))
                            seq_counter += 1
                        deficit_streak = 0
                        deficit_accum = 0.0
                        deficit_start = None
            else:
                deficit_streak = 0
                deficit_accum = 0.0
                deficit_start = None
            cur_day += timedelta(days=1)

        if deficit_streak >= 10 and deficit_accum >= 40.0 and deficit_start is not None:
            mid_dt = deficit_start + timedelta(days=deficit_streak // 2)
            events.append(ReconstructedMemoryEvent(
                event_id=f"mem_stress_{seq_counter:04d}",
                event_category="stress_onset",
                epistemic_class="model_hypothesis",
                hypothesis_status="suspected",
                start_time=deficit_start.isoformat(),
                peak_time=mid_dt.isoformat(),
                end_time=datetime.combine(end_day, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
                season_year=deficit_start.year,
                severity=round(min(1.0, deficit_accum / 100.0), 4),
                confidence=0.72,
                trigger_evidence={
                    "deficit_days": deficit_streak,
                    "cumulative_et0_minus_precip_mm": round(deficit_accum, 2),
                },
            ))
            seq_counter += 1

        # Admitted external management events (planting / irrigation)
        for d_str, entries in sorted(mgmt_by_day.items()):
            day_dt = _parse_dt(f"{d_str}T12:00:00+00:00")
            for entry in entries:
                etype = entry.get("type", "")
                if "plant" in etype or "sow" in etype:
                    events.append(ReconstructedMemoryEvent(
                        event_id=f"mem_plant_obs_{seq_counter:04d}",
                        event_category="planting_emergence",
                        epistemic_class="observed_event",
                        hypothesis_status="observed",
                        start_time=day_dt.isoformat(),
                        peak_time=day_dt.isoformat(),
                        end_time=(day_dt + timedelta(days=3)).isoformat(),
                        season_year=day_dt.year,
                        severity=0.5,
                        confidence=0.98,
                        trigger_evidence={"source": "management_log", **entry},
                    ))
                    seq_counter += 1
                elif "irrig" in etype:
                    events.append(ReconstructedMemoryEvent(
                        event_id=f"mem_irrig_obs_{seq_counter:04d}",
                        event_category="irrigation",
                        epistemic_class="observed_event",
                        hypothesis_status="observed",
                        start_time=day_dt.isoformat(),
                        peak_time=day_dt.isoformat(),
                        end_time=(day_dt + timedelta(days=1)).isoformat(),
                        season_year=day_dt.year,
                        severity=round(min(1.0, float(entry.get("amount_mm") or 20.0) / 50.0), 4),
                        confidence=0.96,
                        trigger_evidence={"source": "management_log", **entry},
                    ))
                    seq_counter += 1

        # 2. Trajectory state & SAR/Optical hypothesis detection
        s2_steps = [r for r in sorted_traj if "ndvi" in (r.get("obs_channels") or {})]
        s1_steps = [r for r in sorted_traj if "sar_vv" in (r.get("obs_channels") or {})]

        # Candidate irrigation from SAR dry-weather backscatter jump
        for i in range(1, len(s1_steps)):
            prev_r, curr_r = s1_steps[i - 1], s1_steps[i]
            prev_vv_db = prev_r.get("raw_metrics", {}).get("vv_mean_db")
            curr_vv_db = curr_r.get("raw_metrics", {}).get("vv_mean_db")
            if not isinstance(prev_vv_db, (int, float)) or not isinstance(curr_vv_db, (int, float)):
                continue
            delta_vv = float(curr_vv_db) - float(prev_vv_db)
            dt_curr = _parse_dt(curr_r["acquisition_time"])
            dt_prev = _parse_dt(prev_r["acquisition_time"])
            if (dt_curr - dt_prev).days > 24 or delta_vv < self.irrigation_sar_jump_db:
                continue
            recent_rain = 0.0
            for d_off in range(4):
                w = daily_weather.get((dt_curr - timedelta(days=d_off)).strftime("%Y-%m-%d")) or {}
                if isinstance(w.get("precipitation"), (int, float)):
                    recent_rain += float(w["precipitation"])
            if recent_rain < 2.0:
                has_mgmt = any(
                    any("irrig" in m.get("type", "") for m in mgmt_by_day.get((dt_curr - timedelta(days=d)).strftime("%Y-%m-%d"), []))
                    for d in range(4)
                )
                if not has_mgmt:
                    events.append(ReconstructedMemoryEvent(
                        event_id=f"mem_cand_irrig_{seq_counter:04d}",
                        event_category="candidate_irrigation",
                        epistemic_class="model_hypothesis",
                        hypothesis_status="suspected",
                        start_time=dt_prev.isoformat(),
                        peak_time=dt_curr.isoformat(),
                        end_time=(dt_curr + timedelta(days=2)).isoformat(),
                        season_year=dt_curr.year,
                        severity=round(min(1.0, delta_vv / 4.0), 4),
                        confidence=0.68,
                        trigger_evidence={
                            "source": "sentinel1_sar_delta_vv_without_rain",
                            "delta_vv_db": round(delta_vv, 3),
                            "preceding_3d_rain_mm": round(recent_rain, 2),
                            "surface_wetness_post": curr_r["posterior_state_means"].get("surface_wetness_event"),
                        },
                    ))
                    seq_counter += 1

        # Optical/state canopy_change, planting_emergence & post-stress recovery
        in_stressed_regime = False
        for i in range(1, len(sorted_traj)):
            prev_r, curr_r = sorted_traj[i - 1], sorted_traj[i]
            dt_prev = _parse_dt(prev_r["acquisition_time"])
            dt_curr = _parse_dt(curr_r["acquisition_time"])
            gap_days = (dt_curr - dt_prev).days
            if gap_days <= 0 or gap_days > 45:
                continue

            v_prev = float(prev_r["posterior_state_means"].get("vigor", 0.5))
            v_curr = float(curr_r["posterior_state_means"].get("vigor", 0.5))
            cw_prev = float(prev_r["posterior_state_means"].get("canopy_water", 0.5))
            cw_curr = float(curr_r["posterior_state_means"].get("canopy_water", 0.5))
            bs_prev = float(prev_r["posterior_state_means"].get("bare_soil_fraction", 0.3))
            sm_curr = float(curr_r["posterior_state_means"].get("stress_memory", 0.0))
            dv = v_curr - v_prev

            # Planting/emergence transition: low vigor / high bare soil -> strong green-up
            if v_prev < 0.36 and dv >= 0.09 and bs_prev >= 0.35:
                events.append(ReconstructedMemoryEvent(
                    event_id=f"mem_emerg_{seq_counter:04d}",
                    event_category="planting_emergence",
                    epistemic_class="model_hypothesis",
                    hypothesis_status="suspected",
                    start_time=dt_prev.isoformat(),
                    peak_time=dt_curr.isoformat(),
                    end_time=(dt_curr + timedelta(days=3)).isoformat(),
                    season_year=dt_curr.year,
                    severity=round(min(1.0, dv / 0.25), 4),
                    confidence=0.70,
                    trigger_evidence={
                        "vigor_prior": round(v_prev, 4),
                        "vigor_post": round(v_curr, 4),
                        "bare_soil_prior": round(bs_prev, 4),
                    },
                ))
                seq_counter += 1

            # Significant canopy change (flush or sudden senescence/pruning/harvest drop)
            if abs(dv) >= self.canopy_change_threshold:
                subtype = "canopy_flush" if dv > 0 else "canopy_decline_or_cut"
                events.append(ReconstructedMemoryEvent(
                    event_id=f"mem_canopy_{seq_counter:04d}",
                    event_category="canopy_change",
                    epistemic_class="model_hypothesis",
                    hypothesis_status="suspected",
                    start_time=dt_prev.isoformat(),
                    peak_time=dt_curr.isoformat(),
                    end_time=(dt_curr + timedelta(days=2)).isoformat(),
                    season_year=dt_curr.year,
                    severity=round(min(1.0, abs(dv) / 0.3), 4),
                    confidence=0.74,
                    trigger_evidence={
                        "subtype": subtype,
                        "delta_vigor": round(dv, 4),
                        "gap_days": gap_days,
                    },
                ))
                seq_counter += 1

            # State-based stress onset & subsequent recovery
            if (cw_curr - cw_prev <= -0.05 and dv <= -0.03) or sm_curr >= 0.45:
                if not in_stressed_regime and not any(
                    e.event_category == "stress_onset"
                    and _parse_dt(e.start_time) <= dt_curr <= _parse_dt(e.end_time)
                    for e in events
                ):
                    events.append(ReconstructedMemoryEvent(
                        event_id=f"mem_stress_state_{seq_counter:04d}",
                        event_category="stress_onset",
                        epistemic_class="model_hypothesis",
                        hypothesis_status="suspected",
                        start_time=dt_prev.isoformat(),
                        peak_time=dt_curr.isoformat(),
                        end_time=(dt_curr + timedelta(days=3)).isoformat(),
                        season_year=dt_curr.year,
                        severity=round(min(1.0, max(sm_curr, abs(dv) * 3.0)), 4),
                        confidence=0.70,
                        trigger_evidence={
                            "delta_canopy_water": round(cw_curr - cw_prev, 4),
                            "delta_vigor": round(dv, 4),
                            "stress_memory": round(sm_curr, 4),
                        },
                    ))
                    seq_counter += 1
                in_stressed_regime = True
            elif in_stressed_regime and dv >= 0.04 and (cw_curr - cw_prev) >= 0.015:
                events.append(ReconstructedMemoryEvent(
                    event_id=f"mem_recov_{seq_counter:04d}",
                    event_category="recovery",
                    epistemic_class="model_hypothesis",
                    hypothesis_status="suspected",
                    start_time=dt_prev.isoformat(),
                    peak_time=dt_curr.isoformat(),
                    end_time=(dt_curr + timedelta(days=3)).isoformat(),
                    season_year=dt_curr.year,
                    severity=round(min(1.0, max(dv, cw_curr - cw_prev) / 0.2), 4),
                    confidence=0.70,
                    trigger_evidence={
                        "delta_vigor": round(dv, 4),
                        "delta_canopy_water": round(cw_curr - cw_prev, 4),
                    },
                ))
                seq_counter += 1
                in_stressed_regime = False

        # 3. Sort chronologically & measure subsequent outcomes against independent future steps
        events.sort(key=lambda e: (e.start_time, e.event_id))
        for ev in events:
            ev.outcome_measurement, ev.hypothesis_status = self._measure_subsequent_outcome(
                ev, sorted_traj, parsed_times
            )

        by_cat: Dict[str, int] = {}
        for ev in events:
            by_cat[ev.event_category] = by_cat.get(ev.event_category, 0) + 1

        observed_cnt = sum(1 for e in events if e.epistemic_class == "observed_event")
        hypo_cnt = sum(1 for e in events if e.epistemic_class == "model_hypothesis")
        supported_cnt = sum(1 for e in events if e.hypothesis_status == "supported")
        contradicted_cnt = sum(1 for e in events if e.hypothesis_status == "contradicted")

        return {
            "events": [e.to_dict() for e in events],
            "summary": {
                "total_events": len(events),
                "observed_events_count": observed_cnt,
                "hypothesis_events_count": hypo_cnt,
                "supported_hypotheses_count": supported_cnt,
                "contradicted_hypotheses_count": contradicted_cnt,
                "by_category": by_cat,
                "years_covered": sorted({e.season_year for e in events}),
            },
        }

    def _measure_subsequent_outcome(
        self,
        event: ReconstructedMemoryEvent,
        sorted_traj: List[Dict[str, Any]],
        parsed_times: List[datetime],
    ) -> Tuple[Dict[str, Any], str]:
        """Measure state & independent observation evolution after event.peak_time."""
        peak_dt = _parse_dt(event.peak_time)
        follow_end = _parse_dt(event.end_time) + timedelta(days=self.followup_days)

        # Nearest pre/at-peak step & nearest prior optical/SAR observations
        pre_step: Optional[Dict[str, Any]] = None
        pre_ndvi: Optional[float] = None
        pre_vv_db: Optional[float] = None
        followup_steps: List[Dict[str, Any]] = []
        for step, dt in zip(sorted_traj, parsed_times):
            if dt <= peak_dt:
                pre_step = step
                raw_m = step.get("raw_metrics") or {}
                if isinstance(raw_m.get("ndvi_mean"), (int, float)):
                    pre_ndvi = float(raw_m["ndvi_mean"])
                if isinstance(raw_m.get("vv_mean_db"), (int, float)):
                    pre_vv_db = float(raw_m["vv_mean_db"])
            elif peak_dt < dt <= follow_end:
                followup_steps.append(step)

        if pre_step is None or not followup_steps:
            status = "observed" if event.epistemic_class == "observed_event" else "unresolved_insufficient_followup"
            return {"status": "insufficient_post_event_observations"}, status

        pre_m = pre_step["posterior_state_means"]
        post_m = followup_steps[-1]["posterior_state_means"]

        d_vigor = round(float(post_m["vigor"]) - float(pre_m["vigor"]), 5)
        d_lai = round(float(post_m["lai"]) - float(pre_m["lai"]), 5)
        d_cw = round(float(post_m["canopy_water"]) - float(pre_m["canopy_water"]), 5)
        d_rzw = round(float(post_m["root_zone_water"]) - float(pre_m["root_zone_water"]), 5)

        post_ndvi = next(
            (s.get("raw_metrics", {}).get("ndvi_mean") for s in reversed(followup_steps)
             if isinstance(s.get("raw_metrics", {}).get("ndvi_mean"), (int, float))),
            None,
        )
        d_obs_ndvi = (
            round(float(post_ndvi) - float(pre_ndvi), 5)
            if isinstance(pre_ndvi, (int, float)) and isinstance(post_ndvi, (int, float))
            else None
        )
        post_vv = next(
            (s.get("raw_metrics", {}).get("vv_mean_db") for s in reversed(followup_steps)
             if isinstance(s.get("raw_metrics", {}).get("vv_mean_db"), (int, float))),
            None,
        )
        d_obs_vv = (
            round(float(post_vv) - float(pre_vv_db), 5)
            if isinstance(pre_vv_db, (int, float)) and isinstance(post_vv, (int, float))
            else None
        )

        # Consistency scoring by event expectation
        verdict = "observed_response_measured" if event.epistemic_class == "observed_event" else "supported"
        new_status = event.hypothesis_status
        if event.epistemic_class == "model_hypothesis":
            if event.event_category in ("candidate_irrigation", "recovery", "planting_emergence"):
                # Expected positive vigor or water/canopy stabilization/rebound
                positive = (d_vigor > -0.02 and (d_rzw >= -0.03 or d_cw >= -0.02 or d_vigor >= 0.02))
                new_status = "supported" if positive else "contradicted"
                verdict = "outcome_consistent_supported" if positive else "outcome_contradicted"
            elif event.event_category == "stress_onset":
                stress_persist = (d_vigor <= 0.03 or d_cw <= 0.02 or d_rzw <= 0.02)
                new_status = "supported" if stress_persist else "contradicted"
                verdict = "outcome_consistent_supported" if stress_persist else "outcome_contradicted"
            elif event.event_category == "canopy_change":
                subtype = str(event.trigger_evidence.get("subtype") or "")
                consistent = (d_vigor >= -0.05) if "flush" in subtype else True
                new_status = "supported" if consistent else "contradicted"
                verdict = "outcome_consistent_supported" if consistent else "outcome_contradicted"

        return {
            "status": verdict,
            "followup_observations_count": len(followup_steps),
            "followup_horizon_days": (_parse_dt(followup_steps[-1]["acquisition_time"]) - peak_dt).days,
            "delta_vigor": d_vigor,
            "delta_lai": d_lai,
            "delta_canopy_water": d_cw,
            "delta_root_zone_water": d_rzw,
            "delta_obs_ndvi": d_obs_ndvi,
            "delta_obs_vv_db": d_obs_vv,
        }, new_status
