"""
Module 4: Vegetation Stress Chronology
Catalogs every stress event from the ProcessModel simulation trajectory,
builds a monthly risk calendar, and identifies compound stress events.

Data Integrity Notes:
  - Accepts null_fill_days mask to tag null-filled weather days in the daily array.
    Null-filled days are included in the simulation (for continuity) but flagged
    so the risk calendar reports only real-data stress frequencies.
  - Thermal onset is parameterizable (default 32°C for temperate wheat;
    should be raised for tropical crops).
"""
import math
import logging
from typing import Dict, List, FrozenSet
from collections import defaultdict

logger = logging.getLogger("agribrain.stress_chronology")


def analyze_stress_chronology(weather: List[Dict], sim_lai: List[float], 
                               sim_biomass: List[float],
                               null_fill_days: FrozenSet[str] = frozenset(),
                               thermal_onset_c: float = 32.0) -> Dict:
    """
    Detect and catalog stress events from the ProcessModel trajectory.
    
    Args:
        weather: daily weather records (aligned 1:1 with sim arrays)
        sim_lai: simulated LAI trajectory from inversion
        sim_biomass: simulated biomass trajectory from inversion
        null_fill_days: set of day strings where weather was null-filled
        thermal_onset_c: temperature (°C) at which thermal stress begins
                         (default 32°C for temperate wheat; raise to ~38°C for tropical)
    """
    n = min(len(weather), len(sim_lai), len(sim_biomass))
    if n < 90:
        return {"status": "insufficient_data"}

    # Compute daily stress indicators
    daily = []
    null_count = 0
    for i in range(n):
        w = weather[i]
        day_str = w.get("day", "")
        is_null_filled = day_str in null_fill_days
        if is_null_filled:
            null_count += 1
        
        t_max = w.get("temp_max", 20)
        t_min = w.get("temp_min", 10)
        precip = w.get("precipitation", 0)
        et0 = w.get("et0", 3.0)

        # P3 FIX: Parameterized thermal stress onset
        thermal = max(0, min(1, (t_max - thermal_onset_c) / 8.0))
        
        # Water deficit stress: cumulative deficit proxy
        deficit = max(0, (et0 or 3.0) - (precip or 0))
        water_stress = min(1, deficit / 6.0)

        # LAI drop detection
        lai_drop = 0
        if i > 0 and sim_lai[i-1] > 0.5:
            lai_drop = max(0, (sim_lai[i-1] - sim_lai[i]) / sim_lai[i-1])

        daily.append({
            "day": day_str,
            "thermal": thermal,
            "water": water_stress,
            "compound": min(1, thermal + water_stress),
            "lai_drop": lai_drop,
            "month": _month(day_str),
            "_null_filled": is_null_filled,  # P1 FIX: Track for quality filtering
        })

    # ---- Detect Stress Events (>0.3 compound for >5 days) ----
    events = []
    current_event = None

    for i, d in enumerate(daily):
        is_stressed = d["compound"] > 0.3
        if is_stressed:
            if current_event is None:
                current_event = {
                    "start_idx": i, "start_day": d["day"],
                    "peak_severity": 0, "thermal_sum": 0, "water_sum": 0,
                    "lai_drop_max": 0, "null_filled_days_in_event": 0,
                }
            current_event["peak_severity"] = max(current_event["peak_severity"], d["compound"])
            current_event["thermal_sum"] += d["thermal"]
            current_event["water_sum"] += d["water"]
            current_event["lai_drop_max"] = max(current_event["lai_drop_max"], d["lai_drop"])
            if d["_null_filled"]:
                current_event["null_filled_days_in_event"] += 1
        else:
            if current_event and (i - current_event["start_idx"]) >= 5:
                duration = i - current_event["start_idx"]
                is_compound = (current_event["thermal_sum"] > duration * 0.2 and 
                              current_event["water_sum"] > duration * 0.2)
                
                if current_event["thermal_sum"] > current_event["water_sum"] * 1.5:
                    stress_type = "Heat"
                elif current_event["water_sum"] > current_event["thermal_sum"] * 1.5:
                    stress_type = "Drought"
                else:
                    stress_type = "Compound"

                # P1 FIX: Flag events that are primarily composed of null-filled data
                nf_ratio = current_event["null_filled_days_in_event"] / max(1, duration)
                confidence = "low" if nf_ratio > 0.5 else "moderate" if nf_ratio > 0.2 else "high"

                events.append({
                    "start": current_event["start_day"],
                    "end": daily[i-1]["day"],
                    "duration_days": duration,
                    "type": stress_type,
                    "is_compound": is_compound,
                    "peak_severity": round(current_event["peak_severity"], 2),
                    "lai_impact_pct": round(current_event["lai_drop_max"] * 100, 1),
                    "confidence": confidence,
                })
            current_event = None

    # ---- Monthly Risk Profile ----
    # P1 FIX: Only count real (non-null-filled) days for frequency calculation
    monthly_stress = defaultdict(lambda: {"count": 0, "severity_sum": 0, "compound_count": 0})
    monthly_real_days = defaultdict(int)
    
    for d in daily:
        m = d["month"]
        if not d["_null_filled"]:
            monthly_real_days[m] += 1
            if d["compound"] > 0.3:
                monthly_stress[m]["count"] += 1
                monthly_stress[m]["severity_sum"] += d["compound"]
            if d["thermal"] > 0.2 and d["water"] > 0.2:
                monthly_stress[m]["compound_count"] += 1

    calendar = []
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    for m in range(1, 13):
        ms = monthly_stress[m]
        real_count = monthly_real_days[m]
        freq = ms["count"] / max(1, real_count)
        calendar.append({
            "month": m,
            "month_name": month_names[m-1],
            "stress_frequency": round(freq, 2),
            "avg_severity": round(ms["severity_sum"] / max(1, ms["count"]), 2) if ms["count"] else 0,
            "compound_days": ms["compound_count"],
            "risk_level": "Critical" if freq > 0.4 else "High" if freq > 0.25 else "Moderate" if freq > 0.1 else "Low",
            "real_days_sampled": real_count,
        })

    compound_events = sum(1 for e in events if e["is_compound"])
    low_confidence_events = sum(1 for e in events if e.get("confidence") == "low")

    result = {
        "status": "ok",
        "total_stress_events": len(events),
        "compound_events": compound_events,
        "events": events[:20],  # Cap for frontend
        "monthly_calendar": calendar,
        "worst_month": max(calendar, key=lambda x: x["stress_frequency"])["month_name"] if calendar else None,
        "safest_month": min(calendar, key=lambda x: x["stress_frequency"])["month_name"] if calendar else None,
        "thermal_onset_c": thermal_onset_c,
        "null_filled_days_excluded": null_count,
    }
    if low_confidence_events > 0:
        result["quality_note"] = f"{low_confidence_events} of {len(events)} stress events have low confidence (>50% null-filled weather data)."
    return result


def _month(day_str: str) -> int:
    try:
        return int(day_str.split("-")[1])
    except:
        return 1
