from __future__ import annotations
try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from asmae_learn.schemas import ValidationEvent

VARIABLE_THRESHOLDS = {
    "vigor": 0.25,
    "canopy_water": 0.25,
    "salinity_stress": 0.20,
    "biotic_confounder": 0.30,
    "lai": 0.35,
    "chlorophyll": 0.35
}

def parse_iso_time(time_str: str) -> datetime:
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)

def has_zone_data(asmae_output: Dict[str, Any], zone_id: str, var: str) -> bool:
    if not zone_id:
        return False
    # Format 1: zone_states dict
    if "zone_states" in asmae_output:
        zone_states = asmae_output["zone_states"]
        if isinstance(zone_states, dict) and zone_id in zone_states:
            zone_data = zone_states[zone_id]
            if isinstance(zone_data, dict) and var in zone_data:
                return True

    # Format 2: zones list
    if "zones" in asmae_output:
        zones = asmae_output["zones"]
        if isinstance(zones, list):
            for z in zones:
                if isinstance(z, dict) and z.get("zone_id") == zone_id:
                    states = z.get("states", {})
                    if isinstance(states, dict) and var in states:
                        return True
                    if var in z:
                        return True
    return False

def get_zone_asmae_value(asmae_output: Dict[str, Any], zone_id: str, var: str) -> float:
    if "zone_states" in asmae_output:
        zone_states = asmae_output["zone_states"]
        if isinstance(zone_states, dict) and zone_id in zone_states:
            zone_data = zone_states[zone_id]
            if isinstance(zone_data, dict) and var in zone_data:
                return float(zone_data[var])

    if "zones" in asmae_output:
        zones = asmae_output["zones"]
        if isinstance(zones, list):
            for z in zones:
                if isinstance(z, dict) and z.get("zone_id") == zone_id:
                    states = z.get("states", {})
                    if isinstance(states, dict) and var in states:
                        return float(states[var])
                    if var in z:
                        return float(z[var])
    return 0.5

def check_disagreement(asmae_output: Dict[str, Any], validation_events: List[ValidationEvent]) -> Dict[str, Any]:
    contradictions = []
    
    run_timestamp_str = asmae_output.get("generated_at") or asmae_output.get("timestamp")
    run_time = None
    if run_timestamp_str:
        try:
            run_time = datetime.fromisoformat(run_timestamp_str.replace("Z", "+00:00"))
        except Exception:
            pass

    # Helper to extract a mean value from ASMAE raster_maps
    def get_asmae_value(var: str, zone_id: Optional[str] = None) -> float:
        raster_maps = asmae_output.get("raster_maps", {})
        grid = raster_maps.get(var)
        if grid:
            if isinstance(grid, list):
                flat = [val for row in grid for val in row if val is not None]
                if flat:
                    return sum(flat) / len(flat)
            elif isinstance(grid, (int, float)):
                return float(grid)
                
        for feat in asmae_output.get("features", []):
            if feat.get("name") == var or feat.get("variable") == var:
                return float(feat.get("value", 0.0))
        return 0.5

    # Check validation events for conflicts among themselves
    for i, ev1 in enumerate(validation_events):
        for ev2 in validation_events[i+1:]:
            if (ev1.target_variable == ev2.target_variable and
                ev1.spatial_scope == ev2.spatial_scope and
                ev1.zone_id == ev2.zone_id):
                
                val1 = ev1.observed_value
                val2 = ev2.observed_value
                is_conflict = False
                if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                    if abs(val1 - val2) > 0.4:
                        is_conflict = True
                elif isinstance(val1, str) and isinstance(val2, str):
                    if val1.lower() != val2.lower():
                        is_conflict = True
                        
                if is_conflict:
                    con_type = "manual_observation_conflict" if "observation" in ev1.source_type and "observation" in ev2.source_type else "sensor_scope_conflict"
                    contradictions.append({
                        "type": con_type,
                        "variable": ev1.target_variable,
                        "severity": "high",
                        "scope": ev1.spatial_scope,
                        "notes": f"Conflict between validation events: {val1} vs {val2}"
                    })

    # Compare validation events against ASMAE output
    for ev in validation_events:
        var = ev.target_variable
        
        # 1. Temporal mismatch check
        if run_time:
            try:
                ev_time = datetime.fromisoformat(ev.event_time.replace("Z", "+00:00"))
                diff_seconds = abs((run_time - ev_time).total_seconds())
                
                # Base window hours by temporal scope
                scope_windows = {
                    "instant": 12,
                    "daily": 24,
                    "weekly": 168,
                    "season": 2160
                }
                window_hours = scope_windows.get(ev.temporal_scope, 24)

                # Adjust based on source type
                if ev.source_type in ["sensor_reading", "field_scout", "drone_image"]:
                    window_hours = max(4, window_hours // 2)
                elif ev.source_type in ["soil_lab", "harvest_record"] or "season" in str(ev.notes or "").lower():
                    window_hours = window_hours * 2

                if diff_seconds > (window_hours * 3600):
                    contradictions.append({
                        "type": "temporal_mismatch",
                        "variable": var,
                        "severity": "high",
                        "scope": ev.spatial_scope,
                        "temporal_window_hours": window_hours,
                        "temporal_mismatch_reason": f"event_outside_{ev.temporal_scope}_window",
                        "notes": f"Temporal mismatch: run time {run_time.isoformat()} vs event time {ev_time.isoformat()}"
                    })
            except Exception:
                pass

        # 2. Zone scope validation: must have matching zone data
        if ev.spatial_scope == "zone":
            if not ev.zone_id or not has_zone_data(asmae_output, ev.zone_id, var):
                contradictions.append({
                    "type": "spatial_scope_mismatch",
                    "variable": var,
                    "severity": "high",
                    "scope": ev.spatial_scope,
                    "zone_id": ev.zone_id,
                    "notes": f"Zone validation event for '{ev.zone_id}' has no matching zone-specific data in ASMAE output."
                })
                continue # Skip value comparison

        # 3. State value mismatch check
        if ev.spatial_scope == "zone":
            asmae_val = get_zone_asmae_value(asmae_output, ev.zone_id, var)
        else:
            asmae_val = get_asmae_value(var, ev.zone_id)
            
        validated_val = ev.observed_value
        
        threshold = VARIABLE_THRESHOLDS.get(var, 0.30)
        has_mismatch = False
        severity = "minor"

        CONTINUOUS_VARS = {"vigor", "canopy_water", "salinity_stress", "yield_observed"}
        if var in CONTINUOUS_VARS:
            fin_val = finite_real(validated_val)
            if fin_val is None:
                contradictions.append({
                    "type": "malformed_continuous_target",
                    "variable": var,
                    "observed_value": repr(validated_val),
                    "severity": "critical",
                })
                continue
            validated_val = fin_val
        
        if isinstance(validated_val, (int, float)):
            diff = abs(asmae_val - validated_val)
            if diff > threshold:
                has_mismatch = True
                severity = "high" if diff > (threshold + 0.15) else "moderate"
        elif isinstance(validated_val, str):
            val_str = validated_val.lower()
            if val_str == "low" and asmae_val > 0.7:
                has_mismatch = True
                severity = "high"
            elif val_str == "high" and asmae_val < 0.4:
                has_mismatch = True
                severity = "high"
            elif val_str == "medium" and (asmae_val < 0.2 or asmae_val > 0.9):
                has_mismatch = True
                severity = "moderate"

        if has_mismatch:
            contradictions.append({
                "type": "state_value_mismatch",
                "variable": var,
                "asmae_value": asmae_val,
                "validated_value": validated_val,
                "severity": severity,
                "scope": ev.spatial_scope,
                "zone_id": ev.zone_id
            })

    # Compute agreement score
    high_count = sum(1 for c in contradictions if c["severity"] in ["high", "critical"])
    moderate_count = sum(1 for c in contradictions if c["severity"] == "moderate")
    
    score_deduction = (high_count * 0.4) + (moderate_count * 0.15)
    agreement_score = max(0.0, round(1.0 - score_deduction, 4))
    
    candidate_status = "pending"
    if any(c["severity"] in ["high", "critical"] for c in contradictions):
        candidate_status = "rejected"

    return {
        "agreement_score": agreement_score,
        "contradictions": contradictions,
        "candidate_status": candidate_status
    }
