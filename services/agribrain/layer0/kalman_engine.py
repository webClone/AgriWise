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

from services.agribrain.layer0.event_forcing_admission import (
    classify_management_event_evidence,
)


def _qualified_weather_for_prediction(weather: Optional[Dict[str, float]]):
    """Require complete finite forcing, keeping real zero measurements.

    Partial weather is not a measured dry or 'typical temperature' day.
    Accept only explicit historical API aliases; never interpolate inputs.
    """
    if not isinstance(weather, dict) or not weather:
        return None
    aliases = {
        "temp_max": ("temp_max", "t_max", "temperature_2m_max"),
        "temp_min": ("temp_min", "t_min", "temperature_2m_min"),
        "precipitation": ("precipitation", "rain_mm", "precipitation_sum"),
        "et0": ("et0", "et0_mm", "et0_fao_penman"),
    }
    normalized = dict(weather)
    for name, candidates in aliases.items():
        value = next((weather[k] for k in candidates if k in weather), None)
        if (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            return None
        normalized[name] = float(value)
    if (
        normalized["temp_min"] > normalized["temp_max"]
        or normalized["precipitation"] < 0.0
        or normalized["et0"] < 0.0
    ):
        return None
    return normalized

from services.agribrain.layer0.state_vector import (
    StateVector, StateCovariance, ProcessModel,
    N_STATES, STATE_NAMES, IDX_LAI, IDX_BIOMASS, IDX_SM_0_10, IDX_SM_10_40,
    IDX_CANOPY_STRESS, IDX_PHENO_STAGE, IDX_STRESS_THERMAL, IDX_PHOTO_EFF,
)
from services.agribrain.layer0.observation_model import get_observation_model


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
    
    # Metadata required by V91.1 runtime security
    diagnostic_only: bool = False
    state_update_allowed: bool = True
    spatial_scope_blocked: bool = False
    block_reason: Optional[str] = None
    
    @property
    def R(self) -> float:
        """
        Effective observation noise variance (inflated by low reliability).
        
        Bayesian formulation: R_effective = σ² / w
        When reliability w=1.0 -> R = σ² (normal)
        When reliability w=0.5 -> R = 2σ² (observation down-weighted)
        When reliability w=0.1 -> R = 10σ² (nearly ignored)
        """
        # Do not undo a qualified low QA weight with an implicit 0.1 floor.
        # update() validates inputs before this property is evaluated.
        if (
            isinstance(self.reliability, bool)
            or not math.isfinite(float(self.reliability))
            or not 0.0 < float(self.reliability) <= 1.0
        ):
            raise ValueError("invalid effective observation reliability")
        return (self.sigma ** 2) / float(self.reliability)


# ============================================================================
# Zone Kalman Filter
# ============================================================================

class ZoneKalmanFilter:
    """
    Extended Kalman Filter for a single management zone.
    
    Operates on a StateVector (9 variables) with:
    - Daily predict step (process model + weather)
    - Update step when observations are available
    - Multi-observation support (many obs per day)
    - Uncertainty tracking
    - Adaptive ML recalibration: learns growth rate from observation residuals
    
    Pure Python implementation (no numpy dependency).
    """
    
    def __init__(self, zone_id: str, crop_params: Optional[Dict] = None, observation_model_provider = None):
        self.zone_id = zone_id
        self.process_model = ProcessModel(crop_params)
        self.observation_model_provider = observation_model_provider or get_observation_model
        
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
        # Ephemeral per-filter evidence identity fence. Restart/replay durability
        # is a separate L0-02C4 gate; do not describe this as exactly-once.
        self._event_evidence_seen: set[str] = set()
        self.parent_plot_id = ""
        self.expected_geometry_hash = ""
        self.evidence_cutoff = None
        
        # ── Adaptive ML Recalibration Engine ─────────────────────────
        # Learns optimal LAI growth rate from observation residuals.
        # When S2 arrives, compares predicted LAI to observed LAI.
        # Uses exponential moving average (EMA) of prediction errors
        # to calibrate the process model's growth rate online.
        self._innovation_history: List[Dict] = []  # {day, predicted_lai, observed_lai, error}
        self._adaptive_lai_rate: Optional[float] = None  # Learned growth rate
        self._ema_alpha: float = 0.3  # EMA smoothing factor (higher = more responsive)
        self._ema_error: float = 0.0  # Running EMA of LAI prediction error
        self._recalibration_count: int = 0  # Number of S2 recalibrations
        self._pre_update_lai: float = 0.0  # LAI before Kalman update (for learning)
    
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
        if events:
            # Direct raw event forcing bypasses the canonical evidence router.
            # No trusted L3 infiltration operator is bound yet. Even an event
            # with role='VERIFIED_DELIVERY' in an ordinary dict is not a
            # verified execution receipt. Reject before any state mutation.
            raise ValueError("physical management forcing requires trusted L3 admission")

        # Advance the physical state using the current process model.
        # The matching Jacobian must be derived from the SAME inputs/model;
        # do not independently assume F=I when physical couplings exist.
        predicted_state, Q = self.process_model.predict(
            self.state, weather, events
        )
        F = self.process_model.transition_jacobian(
            self.state, weather, events, predicted_state=predicted_state
        )

        # Stage a complete covariance update before committing anything.
        # If transition differentiation or propagation fails, the previous
        # state, covariance, day and age remain intact.
        candidate_covariance = StateCovariance(
            P=[row[:] for row in self.covariance.P]
        )
        candidate_covariance.propagate(F, Q)
        predicted_state.day = day
        predicted_state.variance = candidate_covariance.diagonal()

        self.covariance = candidate_covariance
        self.state = predicted_state
        self.days_since_obs += 1
        return predicted_state

    def predict_missing_weather(self, day: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict step when weather is missing:
        - evolve state with no weather forcing (skip weather forcing)
        - inflate process covariance (Q multiplied by 5.0)
        - return (state_values, covariance_P)
        """
        import numpy as np
        if not self.initialized:
            raise RuntimeError("Filter not initialized. Call initialize() first.")
        
        predicted_state, Q = self.process_model.predict(
            self.state, {}, None, skip_weather_forcing=True
        )
        predicted_state.day = day
        
        Q_inflated = [q * 5.0 for q in Q]
        self.covariance.add_process_noise(Q_inflated)
        predicted_state.variance = self.covariance.diagonal()

        self.state = predicted_state
        self.days_since_obs += 1
        
        self.provenance_history.append({
            "day": day,
            "weather_update_mode": "missing_weather_high_uncertainty"
        })
        
        return np.array(self.state.values), np.array(self.covariance.P)
    
    def update(self, observations: List[KalmanObservation]) -> Dict[str, float]:
        """
        Update step: correct state using observations.
        
        Uncertainty SHRINKS because we got new data.
        After update, runs adaptive ML recalibration to learn growth rate.
        Returns source contribution weights for provenance.
        """
        if not self.initialized:
            raise RuntimeError("Filter not initialized.")
        
        source_weights: Dict[str, float] = {}
        total_innovation = 0.0
        self.last_update_admitted_count = 0
        
        # ── Capture pre-update LAI for adaptive learning ──────────
        self._pre_update_lai = self.state.values[IDX_LAI]
        had_ndvi_obs = False
        
        admitted_count = 0
        for obs in observations:
            # These flags are authoritative admission controls, not mere
            # diagnostics. Never update from point-only or blocked evidence.
            if obs.diagnostic_only or not obs.state_update_allowed or obs.spatial_scope_blocked:
                continue
            if any(isinstance(v, bool) for v in (obs.value, obs.sigma, obs.reliability)):
                continue
            try:
                if not (
                    math.isfinite(float(obs.value))
                    and math.isfinite(float(obs.sigma))
                    and math.isfinite(float(obs.reliability))
                    and float(obs.sigma) > 0.0
                    and 0.05 <= float(obs.reliability) <= 1.0
                ):
                    continue
            except (TypeError, ValueError, OverflowError):
                continue

            try:
                # Get observation model
                model_fn = self.observation_model_provider(obs.obs_type)
                
                # Forward model: predicted observation
                y_pred, H, R_base = model_fn(self.state.values)
                
                # Use observation's own R (includes reliability weighting).
                # Validate the provider output before it can touch the state.
                if (
                    not isinstance(H, (list, tuple))
                    or len(H) != N_STATES
                    or not math.isfinite(float(y_pred))
                    or any(not math.isfinite(float(h)) for h in H)
                ):
                    continue
                R = obs.R
                if not math.isfinite(R) or R <= 0.0:
                    continue

                # Innovation (measurement residual)
                # Cast to float: upstream sources may pass numeric strings
                obs_val = float(obs.value)
                innovation = obs_val - y_pred
                
                # Innovation covariance: S = H * P * H^T + R
                # For scalar observation, S is scalar
                S = _dot_HPHt(H, self.covariance.P) + R

                if not math.isfinite(S) or S <= 0.0:
                    continue
                
                # Kalman gain: K = P * H^T / S
                K = _kalman_gain(self.covariance.P, H, S)
                
                if not all(math.isfinite(v) for v in K):
                    continue

                # Prepare a complete candidate before committing either state or
                # covariance. Invalid model Jacobians and overflow must not leave
                # half-applied assimilation updates behind.
                proposed_values = [
                    self.state.values[i] + K[i] * innovation
                    for i in range(N_STATES)
                ]
                proposed_covariance = [row[:] for row in self.covariance.P]
                _update_covariance(proposed_covariance, K, H, obs_R=R)
                if (
                    not all(math.isfinite(v) for v in proposed_values)
                    or not _covariance_entries_valid(proposed_covariance)
                ):
                    continue

                self.state.values[:] = proposed_values
                self.covariance.P[:] = proposed_covariance
                
                # Track source contribution
                weight = abs(innovation) / max(abs(y_pred), 0.01)
                src = obs.source or obs.obs_type
                source_weights[src] = source_weights.get(src, 0) + weight
                total_innovation += abs(innovation)
                admitted_count += 1
                if obs.obs_type in ("ndvi", "evi"):
                    had_ndvi_obs = True
                
            except (ValueError, ZeroDivisionError, TypeError, OverflowError):
                # Skip problematic observations
                continue
        
        # Update variance from covariance diagonal
        self.state.variance = self.covariance.diagonal()
        
        # Clamp physically-bounded state variables after update
        # (Kalman update can push values out of physical range)
        self.state.values[IDX_LAI] = max(0.0, min(8.0, self.state.values[IDX_LAI]))
        self.state.values[IDX_BIOMASS] = max(0.0, self.state.values[IDX_BIOMASS])
        self.state.values[IDX_SM_0_10] = max(0.0, min(1.0, self.state.values[IDX_SM_0_10]))
        self.state.values[IDX_SM_10_40] = max(0.0, min(1.0, self.state.values[IDX_SM_10_40]))
        self.state.values[IDX_CANOPY_STRESS] = max(0.0, min(1.0, self.state.values[IDX_CANOPY_STRESS]))
        self.state.values[IDX_PHENO_STAGE] = max(0.0, min(4.0, self.state.values[IDX_PHENO_STAGE]))
        self.state.values[IDX_STRESS_THERMAL] = max(0.0, min(1.0, self.state.values[IDX_STRESS_THERMAL]))
        self.state.values[IDX_PHOTO_EFF] = max(0.0, min(1.0, self.state.values[IDX_PHOTO_EFF]))
        
        if admitted_count:
            self.last_obs_day = self.state.day
            self.days_since_obs = 0
        
        # ── Adaptive ML Recalibration ────────────────────────────
        # When NDVI observation corrects LAI, learn from the error.
        # If model predicted LAI too high → growth rate was too fast → reduce it.
        # If model predicted LAI too low → growth rate was too slow → increase it.
        if had_ndvi_obs and self._pre_update_lai > 0.01:
            post_lai = self.state.values[IDX_LAI]
            lai_error = post_lai - self._pre_update_lai  # Negative = model over-predicted
            relative_error = lai_error / max(self._pre_update_lai, 0.1)
            
            # EMA of relative prediction error
            self._ema_error = (self._ema_alpha * relative_error + 
                              (1 - self._ema_alpha) * self._ema_error)
            
            # Log innovation for analysis
            self._innovation_history.append({
                "day": self.state.day,
                "predicted_lai": round(self._pre_update_lai, 4),
                "corrected_lai": round(post_lai, 4),
                "error": round(lai_error, 4),
                "relative_error": round(relative_error, 4),
                "ema_error": round(self._ema_error, 4),
            })
            
            self._recalibration_count += 1
            
            # After ≥2 observations, start adapting growth rate
            if self._recalibration_count >= 2:
                base_rate = self.process_model.params["lai_growth_rate"]
                
                # Correction: if EMA error is negative (over-prediction),
                # reduce growth rate. If positive, increase it.
                # Bounded to ±50% of base rate to prevent instability.
                correction = 1.0 + max(-0.5, min(0.5, self._ema_error * 2.0))
                new_rate = base_rate * correction
                
                # Hard bounds: never go below 0.002 or above 0.015 LAI/GDD
                new_rate = max(0.002, min(0.015, new_rate))
                
                self._adaptive_lai_rate = new_rate
                self.process_model._adaptive_lai_rate = new_rate
                self.process_model._last_model_error = abs(self._ema_error)
        
        self.last_update_admitted_count = admitted_count

        # Normalize source weights
        total_w = sum(source_weights.values())
        if total_w > 0:
            source_weights = {k: v / total_w for k, v in source_weights.items()}
        
        return source_weights
    
    def step(self, day: str, weather: Optional[Dict[str, float]],
             observations: Optional[List[KalmanObservation]] = None,
             events: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Full predict+update cycle for one day.
        
        Returns provenance record for this day.
        """
        # C1/C2: classify and retain management evidence, but NEVER pass
        # user-declared/planned/claimed-verified events into the proxy water
        # balance. A separate trusted L3 net-infiltration operator/receipt is
        # needed for physical forcing (L0-02C3). This rule applies equally
        # to weather-present and missing-weather days.
        event_dispositions = classify_management_event_evidence(
            events,
            day=day,
            plot_id=self.parent_plot_id,
            zone_id=self.zone_id,
            geometry_hash=self.expected_geometry_hash,
            cutoff=self.evidence_cutoff,
            seen_ids=self._event_evidence_seen,
        )
        qualified_weather = _qualified_weather_for_prediction(weather)
        weather_availability = (
            "COMPLETE" if qualified_weather is not None
            else ("PARTIAL" if weather else "MISSING")
        )

        # A truthy but incomplete weather dictionary is NOT a measured day.
        # On degraded forcing, do not invent temperature or rainfall.
        if qualified_weather is None:
            self.predict_missing_weather(day)
        else:
            self.predict(day, qualified_weather, None)
        
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
            "n_obs": self.last_update_admitted_count if observations else 0,
            "days_since_obs": self.days_since_obs,
            "conflicts": conflicts,
            "uncertainty_mean": sum(self.state.variance) / N_STATES,
            "weather_update_mode": (
                "measured" if qualified_weather is not None
                else "missing_weather_high_uncertainty"
            ),
            "weather_availability": weather_availability,
            "management_event_evidence": event_dispositions,
            "physical_management_events_applied": 0,
            "event_forcing_status": "DEFERRED_UNTIL_TRUSTED_L3_SUPPORT",
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
        # DNA provenance: set by pi_helpers when DNA traits are injected
        self.dna_metadata: Optional[Dict[str, Any]] = None
    
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
            
            weather = daily_weather.get(day)
            
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

def _covariance_entries_valid(P: List[List[float]]) -> bool:
    """Check that a candidate covariance is finite, symmetric and nonnegative.

    This is a fast admission guard, not an eigenvalue/PSD proof. PSD and
    constrained-state uncertainty remain separate L0-02 qualification gates.
    """
    if len(P) != N_STATES or any(len(row) != N_STATES for row in P):
        return False
    for i in range(N_STATES):
        if not math.isfinite(P[i][i]) or P[i][i] < 0.0:
            return False
        for j in range(i + 1, N_STATES):
            a, b = P[i][j], P[j][i]
            if not (math.isfinite(a) and math.isfinite(b)):
                return False
            if abs(a - b) > 1e-9 * max(1.0, abs(a), abs(b)):
                return False
    return True


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


def _update_covariance(P: List[List[float]], K: List[float], H: List[float],
                       obs_R: float = 0.0) -> None:
    """
    ML-2: Full Joseph form covariance update.

    P = (I - K·H) · P · (I - K·H)ᵀ + K · R · Kᵀ

    More numerically stable than the simplified form P = (I - K·H)·P,
    which can cause covariance to drift negative on off-diagonals over
    long assimilation runs (>365 days). The K·R·Kᵀ term guarantees
    positive semi-definiteness of the posterior covariance.

    Args:
        P: Covariance matrix (N×N), modified in-place.
        K: Kalman gain vector (N×1).
        H: Observation model vector (1×N).
        obs_R: Scalar observation noise variance (σ² / reliability).
    """
    n = len(K)

    # Compute (I - K·H)
    IKH = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            IKH[i][j] = (1.0 if i == j else 0.0) - K[i] * H[j]

    # P_temp = (I - K·H) · P
    P_temp = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            P_temp[i][j] = sum(IKH[i][k] * P[k][j] for k in range(n))

    # P_new = P_temp · (I - K·H)ᵀ + K · R · Kᵀ
    P_new = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            # (I-KH)·P·(I-KH)^T term
            P_new[i][j] = sum(P_temp[i][k] * IKH[j][k] for k in range(n))
            # K·R·K^T term (guarantees positive semi-definiteness)
            P_new[i][j] += K[i] * obs_R * K[j]

    # Copy back
    for i in range(n):
        for j in range(n):
            P[i][j] = P_new[i][j]
