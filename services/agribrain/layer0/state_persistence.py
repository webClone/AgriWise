"""
Layer 0.12: State Persistence — Kalman State Continuity Across Runs

Persists and restores:
  - Last day's Kalman state vector + covariance P per zone
  - Source reliability memory (global + per-zone)
  - Engine version + crop parameter hash (for invalidation)

This ensures the next pipeline run continues from where it left off,
rather than cold-starting from scratch every time.

Storage format: JSON (human-readable, debuggable, git-diffable).
Production note: swap to binary (msgpack/protobuf) if size matters.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib
import json
import os


VERSION = "layer0-v2.0"


def _hash_params(params: Dict) -> str:
    """Deterministic hash of crop parameters for invalidation."""
    raw = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def save_engine_state(
    plot_id: str,
    state_dir: str,
    kalman_zones: Dict[str, Dict[str, Any]],
    validation_state: Dict[str, Any],
    crop_params: Optional[Dict] = None,
    metadata: Optional[Dict] = None,
) -> str:
    """
    Persist the entire Layer 0 engine state for one plot.
    
    Args:
        plot_id: unique plot identifier
        state_dir: directory to write state files
        kalman_zones: {zone_id: {
            "state_values": [...],
            "covariance_diag": [...],
            "last_day": "YYYY-MM-DD",
        }}
        validation_state: from ValidationGraph.to_state_dict()
        crop_params: crop-specific parameters (used for invalidation)
        metadata: any additional metadata
    
    Returns:
        Path to the saved state file.
    """
    os.makedirs(state_dir, exist_ok=True)
    
    state = {
        "version": VERSION,
        "plot_id": plot_id,
        "saved_at": datetime.now().isoformat(),
        "crop_params_hash": _hash_params(crop_params or {}),
        "kalman_zones": kalman_zones,
        "validation": validation_state,
        "metadata": metadata or {},
    }
    
    fname = f"layer0_state_{plot_id}.json"
    fpath = os.path.join(state_dir, fname)
    
    with open(fpath, "w") as f:
        json.dump(state, f, indent=2, default=str)
    
    return fpath


def load_engine_state(
    plot_id: str,
    state_dir: str,
    crop_params: Optional[Dict] = None,
) -> Optional[Dict[str, Any]]:
    """
    Load persisted engine state for a plot.
    
    Returns None if:
      - No state file exists
      - Version mismatch (engine was upgraded)
      - Crop params changed (invalidation)
    
    Returns:
        State dict or None.
    """
    fname = f"layer0_state_{plot_id}.json"
    fpath = os.path.join(state_dir, fname)
    
    if not os.path.exists(fpath):
        return None
    
    try:
        with open(fpath, "r") as f:
            state = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None
    
    # Version check
    if state.get("version") != VERSION:
        print(f" State version mismatch: {state.get('version')} -> {VERSION}, cold start")
        return None
    
    # Crop params check
    if crop_params:
        expected_hash = _hash_params(crop_params)
        if state.get("crop_params_hash") != expected_hash:
            print(f" Crop params changed, cold start")
            return None
    
    return state


def kalman_state_from_filter(zone_filter) -> Dict[str, Any]:
    """
    Extract serializable state from a ZoneKalmanFilter instance.
    
    Args:
        zone_filter: ZoneKalmanFilter with .state and .covariance
    
    Returns:
        Dict ready for save_engine_state.
    """
    sv = zone_filter.state
    cov = zone_filter.covariance
    
    return {
        "state_values": list(sv.values),
        "covariance_diag": list(cov.diagonal()),
        "last_day": sv.day,
        "state_names": list(sv.names) if hasattr(sv, "names") else [],
    }


def restore_kalman_state(zone_filter, saved_zone: Dict[str, Any]) -> bool:
    """
    Restore a ZoneKalmanFilter from persisted state.
    
    Args:
        zone_filter: ZoneKalmanFilter to restore into
        saved_zone: from load_engine_state()["kalman_zones"][zone_id]
    
    Returns:
        True if restoration succeeded.
    """
    try:
        values = saved_zone.get("state_values", [])
        diag = saved_zone.get("covariance_diag", [])
        last_day = saved_zone.get("last_day", "")
        
        if not values or not last_day:
            return False
        
        # Restore state
        zone_filter.state.values = list(values)
        zone_filter.state.day = last_day
        
        # Restore covariance diagonal
        if diag and hasattr(zone_filter, "covariance"):
            zone_filter.covariance.set_diagonal(diag)
        
        return True
    except Exception as e:
        print(f" State restore failed: {e}")
        return False
