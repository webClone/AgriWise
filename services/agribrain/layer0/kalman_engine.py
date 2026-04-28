"""
Layer 0.5: Kalman Engine — Zone-level state estimation with predict/update cycle

Implements a Kalman-style filter per management zone:
  1. PREDICT: evolve state daily using ProcessModel + weather drivers
  2. UPDATE: correct prediction when satellite/sensor observations arrive
  3. Track uncertainty: grows during data gaps, shrinks on observation days

The filter handles:
  - Irregular observations (S2 every 5d, S1 every 12d, weather daily)
  - Multiple observation types per day (S2 + S1 + weather simultaneously)
  - Dynamic source reliability weighting
  - Per-zone provenance logging

Output: daily state + uncertainty curves per zone, even through clouds.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import math

from layer0.state_vector import (
    StateVector, StateCovariance, ProcessModel,
    N_STATES, STATE_NAMES, IDX_LAI, IDX_SM_0_10,
)
from layer0.observation_model import get_observation_model


# ============================================================================
# Observation record (what the Kalman filter receives)
# ============================================================================

@dataclass
class KalmanObservation:
    """
    A single observation for the Kalman filter.
    
    Attributes:
        obs_type: "ndvi", "evi", "ndmi", "vv", "vh", "soil_moisture", "canopy_cover"
        value: observed value (scalar — per-zone mean or per-pixel)
        sigma: observation noise standard deviation
        reliability: source reliability weight 0–1 (from cross-source validation)
        source: which source produced this ("sentinel2", "sentinel1", "sensor", ...)
        pixel_coords: optional (row, col) if per-pixel observation
    """
    obs_type: str
    value: float
    sigma: float = 0.1
    reliability: float = 1.0
    source: str = ""
    pixel_coords: Optional[Tuple[int, int]] = None
    
    @property
    def R(self) -> float:
        """
        Effective observation noise variance (inflated by low reliability).
        
        Bayesian formulation: R_effective = σ² / w
        When reliability w=1.0 -> R = σ² (normal)
        When reliability w=0.5 -> R = 2σ² (observation down-weighted)
        When reliability w=0.1 -> R = 10σ² (nearly ignored)
        """
        reliability_factor = max(0.1, self.reliability)
        return (self.sigma ** 2) / reliability_factor


# ============================================================================
# Zone Kalman Filter
# ============================================================================

class ZoneKalmanFilter:
    """
    Extended Kalman Filter for a single management zone.
    
    Operates on a StateVector (8 variables) with:
    - Daily predict step (process model + weather)
    - Update step when observations are available
    - Multi-observation support (many obs per day)
    - Uncertainty tracking
    
    Pure Python implementation (no numpy dependency).
    """
    
    def __init__(self, zone_id: str, crop_params: Optional[Dict] = None):
        self.zone_id = zone_id
        self.process_model = ProcessModel(crop_params)
        
        # Current state
        self.state: Optional[StateVector] = None
        self.covariance: Optional[StateCovariance] = None
        
        # History
        self.state_history: List[StateVector] = []
        self.provenance_history: List[Dict] = []
        
        # Flags
        self.initialized = False
        self.last_obs_day: Optional[str] = None
        self.days_since_obs: int = 0
    
    def initialize(self, day: str, soil_props: Optional[Dict] = None) -> None:
        """Initialize the filter with prior state."""
        self.state = StateVector.initial(day, soil_props)
        self.covariance = StateCovariance.from_diagonal(self.state.variance)
        self.initialized = True
        self.state_history.append(self.state.clone())
    
    def predict(self, day: str, weather: Dict[str, float],
                events: Optional[List[Dict]] = None) -> StateVector:
        """
        Predict step: evolve state to the next day using process model.
        
        Uncertainty GROWS because the model is imperfect.
        """
        if not self.initialized:
            raise RuntimeError("Filter not initialized. Call initialize() first.")
        
        # Run process model
        predicted_state, Q = self.process_model.predict(
            self.state, weather, events
        )
        predicted_state.day = day
        
        # Propagate covariance: P_pred = F * P * F^T + Q
        # For this simplified model, F ≈ I (identity), so:
        # P_pred = P + Q
        self.covariance.add_process_noise(Q)
        
        # Update state
        self.state = predicted_state
        self.days_since_obs += 1
        
        return predicted_state
    
    def update(self, observations: List[KalmanObservation]) -> Dict[str, float]:
        """
        Update step: correct state using observations.
        
        Uncertainty SHRINKS because we got new data.
        Returns source contribution weights for provenance.
        """
        if not self.initialized:
            raise RuntimeError("Filter not initialized.")
        
        source_weights: Dict[str, float] = {}
        total_innovation = 0.0
        
        for obs in observations:
            if obs.reliability < 0.05:
                continue  # Skip unreliable observations
            
            try:
                # Get observation model
                model_fn = get_observation_model(obs.obs_type)
                
                # Forward model: predicted observation
                y_pred, H, R_base = model_fn(self.state.values)
                
                # Use observation's own R (includes reliability weighting)
                R = obs.R
                
                # Innovation (measurement residual)
                innovation = obs.value - y_pred
                
                # Innovation covariance: S = H * P * H^T + R
                # For scalar observation, S is scalar
                S = _dot_HPHt(H, self.covariance.P) + R
                
                if S <= 0:
                    continue
                
                # Kalman gain: K = P * H^T / S
                K = _kalman_gain(self.covariance.P, H, S)
                
                # State update: x = x + K * innovation
                for i in range(N_STATES):
                    self.state.values[i] += K[i] * innovation
                
                # Covariance update: P = (I - K*H) * P
                _update_covariance(self.covariance.P, K, H)
                
                # Track source contribution
                weight = abs(innovation) / max(abs(y_pred), 0.01)
                src = obs.source or obs.obs_type
                source_weights[src] = source_weights.get(src, 0) + weight
                total_innovation += abs(innovation)
                
            except (ValueError, ZeroDivisionError) as e:
                # Skip problematic observations
                continue
        
        # Update variance from covariance diagonal
        self.state.variance = self.covariance.diagonal()
        
        if observations:
            self.last_obs_day = self.state.day
            self.days_since_obs = 0
        
        # Normalize source weights
        total_w = sum(source_weights.values())
        if total_w > 0:
            source_weights = {k: v / total_w for k, v in source_weights.items()}
        
        return source_weights
    
    def step(self, day: str, weather: Dict[str, float],
             observations: Optional[List[KalmanObservation]] = None,
             events: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Full predict+update cycle for one day.
        
        Returns provenance record for this day.
        """
        # Predict
        self.predict(day, weather, events)
        
        # Update (if observations exist)
        source_weights = {}
        conflicts = []
        
        if observations:
            source_weights = self.update(observations)
        
        # Store history
        state_copy = self.state.clone()
        state_copy.day = day
        self.state_history.append(state_copy)
        
        # Build provenance record
        provenance = {
            "day": day,
            "zone": self.zone_id,
            "sources": source_weights,
            "n_obs": len(observations) if observations else 0,
            "days_since_obs": self.days_since_obs,
            "conflicts": conflicts,
            "uncertainty_mean": sum(self.state.variance) / N_STATES,
        }
        self.provenance_history.append(provenance)
        
        return provenance
    
    def get_daily_states(self) -> List[Dict]:
        """Return all historical states as dicts (for FieldTensor.daily_state)."""
        return [s.to_dict() for s in self.state_history]
    
    def get_daily_uncertainty(self) -> List[Dict]:
        """Return all historical uncertainties as dicts."""
        return [s.uncertainty_dict() for s in self.state_history]


# ============================================================================
# Multi-Zone Runner
# ============================================================================

class DailyAssimilationEngine:
    """
    Runs Kalman filters for all zones in a field simultaneously.
    
    Daily pipeline:
      1. Collect weather (shared across zones)
      2. For each zone: predict -> collect zone-level observations -> update
      3. Output daily states + uncertainty + provenance for all zones
    """
    
    def __init__(self, crop_params: Optional[Dict] = None):
        self.filters: Dict[str, ZoneKalmanFilter] = {}
        self.crop_params = crop_params
        self.daily_provenance: List[Dict] = []
    
    def add_zone(self, zone_id: str, soil_props: Optional[Dict] = None,
                 start_day: str = "") -> None:
        """Add a zone to the engine."""
        filt = ZoneKalmanFilter(zone_id, self.crop_params)
        filt.initialize(start_day, soil_props)
        self.filters[zone_id] = filt
    
    def run_day(self, day: str, weather: Dict[str, float],
                zone_observations: Optional[Dict[str, List[KalmanObservation]]] = None,
                events: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Run one day of assimilation for all zones.
        
        Args:
            day: ISO date string
            weather: shared weather drivers (plot-level, not per-pixel)
            zone_observations: {zone_id: [KalmanObservation, ...]}
            events: management events (applied to all zones unless zone-specific)
            
        Returns:
            Daily summary with per-zone state, uncertainty, provenance.
        """
        if not zone_observations:
            zone_observations = {}
        
        day_result = {"day": day, "zones": {}}
        
        for zone_id, filt in self.filters.items():
            obs = zone_observations.get(zone_id, [])
            provenance = filt.step(day, weather, obs, events)
            
            day_result["zones"][zone_id] = {
                "state": filt.state.to_dict(),
                "uncertainty": filt.state.uncertainty_dict(),
                "provenance": provenance,
            }
        
        self.daily_provenance.append(day_result)
        return day_result
    
    def run_period(self, start_date: str, end_date: str,
                   daily_weather: Dict[str, Dict[str, float]],
                   all_observations: Optional[Dict[str, Dict[str, List[KalmanObservation]]]] = None,
                   events_by_day: Optional[Dict[str, List[Dict]]] = None) -> List[Dict]:
        """
        Run assimilation for a date range.
        
        Args:
            start_date: "YYYY-MM-DD"
            end_date: "YYYY-MM-DD"
            daily_weather: {day: {temp_max, temp_min, precipitation, et0, ...}}
            all_observations: {day: {zone_id: [KalmanObservation, ...]}}
            events_by_day: {day: [events]}
            
        Returns:
            List of daily summaries.
        """
        if not all_observations:
            all_observations = {}
        if not events_by_day:
            events_by_day = {}
        
        results = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current <= end:
            day = current.strftime("%Y-%m-%d")
            
            weather = daily_weather.get(day, {
                "temp_max": 20.0, "temp_min": 10.0,
                "precipitation": 0.0, "et0": 3.0
            })
            
            obs = all_observations.get(day, {})
            events = events_by_day.get(day, [])
            
            result = self.run_day(day, weather, obs, events)
            results.append(result)
            
            current += timedelta(days=1)
        
        return results
    
    def to_field_tensor_outputs(self) -> Tuple[Dict, Dict, List[Dict]]:
        """
        Export results in FieldTensor-compatible format.
        
        Returns:
            (daily_state, state_uncertainty, provenance_log)
            
            Where daily_state = {zone_id: [daily_dicts]}
                  state_uncertainty = {zone_id: [daily_sigma_dicts]}
                  provenance_log = [daily_records]
        """
        daily_state: Dict[str, List[Dict]] = {}
        state_uncertainty: Dict[str, List[Dict]] = {}
        
        for zone_id, filt in self.filters.items():
            daily_state[zone_id] = filt.get_daily_states()
            state_uncertainty[zone_id] = filt.get_daily_uncertainty()
        
        return daily_state, state_uncertainty, self.daily_provenance


# ============================================================================
# Matrix operations (pure Python, no numpy)
# ============================================================================

def _dot_HPHt(H: List[float], P: List[List[float]]) -> float:
    """Compute H * P * H^T for a 1×N observation vector H and N×N covariance P."""
    n = len(H)
    # First: PH = P * H^T (N×1 vector)
    PH = [sum(P[i][j] * H[j] for j in range(n)) for i in range(n)]
    # Then: H * PH (scalar)
    return sum(H[i] * PH[i] for i in range(n))


def _kalman_gain(P: List[List[float]], H: List[float], S: float) -> List[float]:
    """Compute Kalman gain K = P * H^T / S for scalar observation."""
    n = len(H)
    PH = [sum(P[i][j] * H[j] for j in range(n)) for i in range(n)]
    return [ph / S for ph in PH]


def _update_covariance(P: List[List[float]], K: List[float], H: List[float]) -> None:
    """
    In-place Joseph form covariance update: P = (I - K*H) * P
    More numerically stable than direct update.
    """
    n = len(K)
    
    # Compute (I - K*H)
    IKH = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            IKH[i][j] = (1.0 if i == j else 0.0) - K[i] * H[j]
    
    # P_new = IKH * P
    P_new = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            P_new[i][j] = sum(IKH[i][k] * P[k][j] for k in range(n))
    
    # Copy back
    for i in range(n):
        for j in range(n):
            P[i][j] = P_new[i][j]
