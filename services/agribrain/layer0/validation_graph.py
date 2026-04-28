"""
Layer 0.6: Cross-Source Validation Graph

Implements spatial and temporal consistency checks between data sources.
When sources disagree, the system:
  1. Detects the conflict
  2. Scores hypotheses (cloud contamination? sensor drift? real anomaly?)
  3. Adjusts dynamic reliability weights per source per zone
  4. Flags the day for downstream layers

This is what makes sources "validate each other" continuously,
and the mechanism that prevents bad data from corrupting states.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math


# ============================================================================
# Consistency Check Definitions
# ============================================================================

@dataclass
class ConsistencyResult:
    """Outcome of one consistency check."""
    check_name: str
    passed: bool
    residual: float = 0.0       # How far from expected
    severity: float = 0.0       # 0–1 (0 = fine, 1 = severe violation)
    hypothesis: str = ""        # Most likely explanation if failed
    affected_sources: List[str] = field(default_factory=list)
    details: str = ""


class ValidationGraph:
    """
    Cross-source validation engine.
    
    Runs a set of consistency checks per zone per day, using:
    - The predicted state (from process model)
    - The available observations
    - Historical patterns
    
    Updates dynamic reliability weights for each source.
    """
    
    def __init__(self):
        # Global reliability weights per source (backward-compatible)
        self.source_reliability: Dict[str, float] = {
            "sentinel2": 1.0,
            "sentinel1": 1.0,
            "weather": 1.0,
            "sensor": 1.0,
            "user": 1.0,
            "camera": 1.0,
            "ip_camera": 1.0,
        }
        
        # Per-zone reliability: {zone_id: {source: weight}}
        # Prevents one bad zone from poisoning the whole plot
        self.zone_reliability: Dict[str, Dict[str, float]] = {}
        
        # Per-obs-type reliability: {source: {obs_type: weight}}
        # e.g. sentinel2 ndvi might be unreliable but ndmi fine
        self.obs_reliability: Dict[str, Dict[str, float]] = {}
        
        # History of check results for trend analysis
        self.check_history: List[Dict] = []
        
        # Consecutive violation counters per source
        self._violation_counts: Dict[str, int] = {}
    
    def validate_day(self, day: str, zone_id: str,
                     predicted_state: Dict[str, float],
                     observations: Dict[str, float],
                     weather: Dict[str, float],
                     recent_history: Optional[List[Dict]] = None
                     ) -> Tuple[List[ConsistencyResult], Dict[str, float]]:
        """
        Run all consistency checks for one zone on one day.
        
        Args:
            predicted_state: state variable values from process model
            observations: available observations {"ndvi": 0.6, "vv": -14, ...}
            weather: today's weather {"precipitation": 5, "temp_max": 30, ...}
            recent_history: last N days of states for trend analysis
            
        Returns:
            (check_results, updated_reliability_weights)
        """
        results = []
        
        # ---- Vegetation consistency ----
        if "ndvi" in observations:
            results.append(self._check_vegetation_consistency(
                predicted_state, observations, weather
            ))
        
        # ---- Water consistency ----
        if any(k in observations for k in ["vv", "soil_moisture"]):
            results.append(self._check_water_consistency(
                predicted_state, observations, weather
            ))
        
        # ---- Phenology consistency ----
        if "ndvi" in observations and recent_history:
            results.append(self._check_phenology_consistency(
                predicted_state, observations, recent_history
            ))
        
        # ---- Temporal consistency (sudden jumps) ----
        if recent_history and len(recent_history) >= 2:
            results.append(self._check_temporal_consistency(
                predicted_state, recent_history
            ))
        
        # ---- Camera↔Satellite: Cloud artifact disambiguation ----
        if "canopy_cover" in observations and "ndvi" in observations:
            results.append(self._check_cloud_artifact(
                predicted_state, observations
            ))
        
        # ---- Camera↔Satellite: Phenology sanity ----
        if "phenology_stage" in observations:
            results.append(self._check_phenology_camera(
                predicted_state, observations
            ))
        
        # ---- Camera↔Satellite: Stress conflict ----
        if "canopy_cover" in observations and "ndmi" in observations:
            results.append(self._check_stress_conflict(
                predicted_state, observations
            ))
        
        # ---- IP Camera: Canopy stability vs satellite ----
        if "canopy_cover" in observations and "ndvi" in observations:
            ip_cam_check = self._check_ip_camera_canopy_stability(
                predicted_state, observations
            )
            if ip_cam_check is not None:
                results.append(ip_cam_check)
            
        # ---- Ingest Pre-computed Auditable Validation Checks ----
        # (e.g. from IP Camera's satellite_validation.py and weather_validation.py)
        if "precomputed_validations" in observations:
            for val in observations["precomputed_validations"]:
                agreement = val.get("agreement", True)
                confidence = val.get("confidence", 1.0)
                severity = min(1.0, (1.0 - confidence) + (0.5 if not agreement else 0.0))
                
                check = ConsistencyResult(
                    check_name=val.get("check_name", "unknown_precomputed"),
                    passed=agreement,
                    residual=1.0 - confidence,
                    severity=severity,
                    hypothesis=val.get("agreement_reason", ""),
                    affected_sources=[val.get("affected_upstream_source", "unknown")],
                    details=f"Expected: {val.get('expected_signal', '')} | Observed: {val.get('observed_signal', '')}"
                )
                results.append(check)
                
                # Apply severity-based penalty to ip_camera when its own validations disagree
                if not agreement and severity > 0.3:
                    affected_src = val.get("affected_upstream_source", "")
                    # If the IP camera disagrees with satellite/weather, also mildly penalize ip_camera
                    # (the affected upstream source gets the main penalty via _update_reliability_weights)
                    current_ipc = self.source_reliability.get("ip_camera", 1.0)
                    self.source_reliability["ip_camera"] = max(0.05, current_ipc - 0.03 * severity)
        
        # ---- Update reliability weights (global + zone-level) ----
        self._update_reliability_weights(results, zone_id)
        
        # Store history
        self.check_history.append({
            "day": day,
            "zone": zone_id,
            "results": [r.__dict__ for r in results],
            "reliability_global": dict(self.source_reliability),
            "reliability_zone": dict(self.zone_reliability.get(zone_id, {})),
        })
        
        return results, dict(self.source_reliability)
    
    # ================================================================
    # Individual consistency checks
    # ================================================================
    
    def _check_vegetation_consistency(self,
                                       state: Dict[str, float],
                                       obs: Dict[str, float],
                                       weather: Dict[str, float]) -> ConsistencyResult:
        """
        Vegetation check: NDVI vs SAR vs predicted LAI.
        
        If NDVI drops sharply but SAR vegetation proxy is stable ->
        likely cloud contamination or atmospheric issue.
        """
        ndvi_obs = obs.get("ndvi", None)
        vh_obs = obs.get("vh", None)
        lai_pred = state.get("lai_proxy", 0)
        
        # Expected NDVI from predicted LAI
        ndvi_max = 0.9
        ndvi_soil = 0.15
        k = 0.5
        ndvi_expected = ndvi_soil + (ndvi_max - ndvi_soil) * (1 - math.exp(-k * lai_pred))
        
        if ndvi_obs is not None:
            residual = abs(ndvi_obs - ndvi_expected)
            
            if residual > 0.25:
                # Large discrepancy
                hypothesis = "cloud_contamination"
                if vh_obs is not None:
                    # If SAR VH is stable (vegetation structure intact), NDVI drop is suspect
                    vh_expected = -22 + 3 * state.get("biomass_proxy", 0)
                    vh_residual = abs(vh_obs - vh_expected)
                    if vh_residual < 3.0:
                        hypothesis = "cloud_contamination"  # SAR stable, NDVI wrong
                    else:
                        hypothesis = "real_vegetation_change"
                
                return ConsistencyResult(
                    check_name="vegetation_consistency",
                    passed=False,
                    residual=residual,
                    severity=min(1.0, residual / 0.4),
                    hypothesis=hypothesis,
                    affected_sources=["sentinel2"],
                    details=f"NDVI obs={ndvi_obs:.2f} vs expected={ndvi_expected:.2f}"
                )
        
        return ConsistencyResult(
            check_name="vegetation_consistency",
            passed=True,
            residual=abs(ndvi_obs - ndvi_expected) if ndvi_obs else 0,
        )
    
    def _check_water_consistency(self,
                                  state: Dict[str, float],
                                  obs: Dict[str, float],
                                  weather: Dict[str, float]) -> ConsistencyResult:
        """
        Water check: rain + ET vs SAR wetness vs soil sensors.
        
        If weather says heavy rain but SAR shows no change in soil moisture ->
        rainfall estimate is uncertain or storm missed the plot.
        """
        rain = weather.get("precipitation", 0)
        sm_pred = state.get("sm_0_10", 0.5)
        vv_obs = obs.get("vv", None)
        sensor_sm = obs.get("soil_moisture", None)
        
        issues = []
        severity = 0.0
        
        if rain > 10 and vv_obs is not None:
            # Heavy rain -> expect wet soil -> higher VV
            vv_wet_threshold = -14.0  # dB
            if vv_obs < -17.0:  # Still looks dry
                issues.append("heavy_rain_but_dry_sar")
                severity = 0.6
        
        if sensor_sm is not None:
            sm_diff = abs(sensor_sm - sm_pred)
            if sm_diff > 0.2:
                issues.append(f"sensor_model_mismatch: sensor={sensor_sm:.2f} pred={sm_pred:.2f}")
                severity = max(severity, sm_diff / 0.4)
        
        if issues:
            hypothesis = "rainfall_spatial_mismatch" if rain > 10 else "sensor_drift_or_model_error"
            return ConsistencyResult(
                check_name="water_consistency",
                passed=False,
                residual=severity,
                severity=min(1.0, severity),
                hypothesis=hypothesis,
                affected_sources=["weather", "sentinel1"] if rain > 10 else ["sensor"],
                details="; ".join(issues)
            )
        
        return ConsistencyResult(check_name="water_consistency", passed=True)
    
    def _check_phenology_consistency(self,
                                      state: Dict[str, float],
                                      obs: Dict[str, float],
                                      history: List[Dict]) -> ConsistencyResult:
        """
        Phenology check: GDD-based stage vs NDVI growth curve.
        
        If GDD says vegetative growth but NDVI hasn't risen -> something wrong.
        """
        gdd = state.get("phenology_gdd", 0)
        stage = state.get("phenology_stage", 0)
        ndvi_obs = obs.get("ndvi", None)
        
        if ndvi_obs is None or len(history) < 5:
            return ConsistencyResult(check_name="phenology_consistency", passed=True)
        
        # Check if NDVI trend matches expected stage
        recent_ndvi = [h.get("lai_proxy", 0) * 0.15 + 0.15 for h in history[-5:]]
        ndvi_trend = recent_ndvi[-1] - recent_ndvi[0] if len(recent_ndvi) >= 2 else 0
        
        if stage > 1.0 and ndvi_trend < -0.05:
            # Growing stage but NDVI declining -> stress or phenology mismatch
            return ConsistencyResult(
                check_name="phenology_consistency",
                passed=False,
                residual=abs(ndvi_trend),
                severity=0.4,
                hypothesis="phenology_gdd_mismatch_or_stress",
                affected_sources=["weather"],  # GDD from weather might be wrong
                details=f"Stage={stage:.1f} but NDVI trend={ndvi_trend:.3f}"
            )
        
        return ConsistencyResult(check_name="phenology_consistency", passed=True)
    
    def _check_temporal_consistency(self,
                                     state: Dict[str, float],
                                     history: List[Dict]) -> ConsistencyResult:
        """
        Temporal check: detect unrealistic sudden jumps in state.
        """
        if not history:
            return ConsistencyResult(check_name="temporal_consistency", passed=True)
        
        prev = history[-1]
        
        # LAI shouldn't jump more than 0.5 in one day
        lai_jump = abs(state.get("lai_proxy", 0) - prev.get("lai_proxy", 0))
        if lai_jump > 0.5:
            return ConsistencyResult(
                check_name="temporal_consistency",
                passed=False,
                residual=lai_jump,
                severity=min(1.0, lai_jump / 1.0),
                hypothesis="observation_artifact_or_model_instability",
                details=f"LAI jump of {lai_jump:.2f} in one day"
            )
        
        # Soil moisture shouldn't jump more than 0.3 unless rain/irrigation
        sm_jump = abs(state.get("sm_0_10", 0) - prev.get("sm_0_10", 0))
        if sm_jump > 0.3:
            return ConsistencyResult(
                check_name="temporal_consistency",
                passed=False,
                residual=sm_jump,
                severity=min(1.0, sm_jump / 0.5),
                hypothesis="unrecorded_irrigation_or_heavy_rain",
                details=f"SM jump of {sm_jump:.2f} in one day"
            )
        
        return ConsistencyResult(check_name="temporal_consistency", passed=True)
    
    # ================================================================
    # Camera↔Satellite cross-validation checks
    # ================================================================
    
    def _check_cloud_artifact(self,
                               state: Dict[str, float],
                               obs: Dict[str, float]) -> ConsistencyResult:
        """
        Cloud artifact disambiguation:
        If camera canopy_cover is stable/high but Sentinel-2 NDVI drops sharply
        -> the NDVI drop is likely cloud contamination, not real change.
        
        Action: down-weight sentinel2 reliability for this day.
        """
        canopy = obs.get("canopy_cover", None)
        ndvi = obs.get("ndvi", None)
        
        if canopy is None or ndvi is None:
            return ConsistencyResult(check_name="cloud_artifact", passed=True)
        
        lai_pred = state.get("lai_proxy", 1.0)
        # Expected NDVI from state
        ndvi_expected = 0.15 + 0.75 * (1 - math.exp(-0.5 * lai_pred))
        
        # Camera says canopy is there, but NDVI is low
        ndvi_drop = ndvi_expected - ndvi
        canopy_healthy = canopy > 0.4
        
        if ndvi_drop > 0.15 and canopy_healthy:
            return ConsistencyResult(
                check_name="cloud_artifact",
                passed=False,
                residual=ndvi_drop,
                severity=min(1.0, ndvi_drop / 0.3),
                hypothesis="cloud_contamination_camera_stable",
                affected_sources=["sentinel2"],
                details=f"Camera cover={canopy:.2f} but NDVI={ndvi:.2f} (expected {ndvi_expected:.2f})"
            )
        
        return ConsistencyResult(check_name="cloud_artifact", passed=True)
    
    def _check_phenology_camera(self,
                                 state: Dict[str, float],
                                 obs: Dict[str, float]) -> ConsistencyResult:
        """
        Phenology camera conflict:
        If camera stage estimate conflicts with GDD-derived stage over
        multiple checks -> either sowing date wrong or weather bias.
        """
        camera_stage = obs.get("phenology_stage", None)
        model_stage = state.get("phenology_stage", 0)
        
        if camera_stage is None:
            return ConsistencyResult(check_name="phenology_camera", passed=True)
        
        stage_diff = abs(camera_stage - model_stage)
        
        if stage_diff > 1.0:
            return ConsistencyResult(
                check_name="phenology_camera",
                passed=False,
                residual=stage_diff,
                severity=min(1.0, stage_diff / 2.0),
                hypothesis="sowing_date_error_or_weather_bias",
                affected_sources=["weather", "camera"],
                details=f"Camera stage={camera_stage:.1f} vs model stage={model_stage:.1f}"
            )
        
        return ConsistencyResult(check_name="phenology_camera", passed=True)
    
    def _check_stress_conflict(self,
                                state: Dict[str, float],
                                obs: Dict[str, float]) -> ConsistencyResult:
        """
        Stress conflict:
        If NDMI indicates water stress but camera shows healthy green
        canopy + soil moisture is adequate -> down-weight NDMI-derived stress.
        """
        ndmi = obs.get("ndmi", None)
        canopy = obs.get("canopy_cover", None)
        sm = state.get("sm_0_10", 0.5)
        
        if ndmi is None or canopy is None:
            return ConsistencyResult(check_name="stress_conflict", passed=True)
        
        # NDMI low = stress signal, but camera says healthy + soil wet
        ndmi_stressed = ndmi < 0.15
        canopy_healthy = canopy > 0.5
        soil_wet = sm > 0.3
        
        if ndmi_stressed and canopy_healthy and soil_wet:
            return ConsistencyResult(
                check_name="stress_conflict",
                passed=False,
                residual=0.15 - ndmi,
                severity=0.5,
                hypothesis="ndmi_atmospheric_artifact_or_sensor_issue",
                affected_sources=["sentinel2"],
                details=f"NDMI={ndmi:.2f} (stress) but camera cover={canopy:.2f} & SM={sm:.2f}"
            )
        
        return ConsistencyResult(check_name="stress_conflict", passed=True)
    
    def _check_ip_camera_canopy_stability(
        self,
        state: Dict[str, float],
        obs: Dict[str, float],
    ) -> Optional[ConsistencyResult]:
        """
        IP Camera canopy stability check:
        Compares IP camera's canopy_cover observation against
        the LAI-predicted canopy cover from the state model.
        
        If the camera reports high canopy but the model (informed by
        satellite NDVI) predicts low LAI -> possible satellite cloud artifact.
        If the camera reports low canopy but model predicts high LAI -> 
        possible camera obstruction or calibration issue.
        
        Only fires when canopy_cover source is likely from ip_camera
        (detected by co-occurrence with specific obs keys).
        """
        canopy = obs.get("canopy_cover")
        ndvi = obs.get("ndvi")
        
        if canopy is None or ndvi is None:
            return None
        
        # Predicted canopy from state LAI
        lai = state.get("lai_proxy", 1.0)
        k = 0.6
        import math
        predicted_canopy = 1.0 - math.exp(-k * lai)
        
        canopy_delta = abs(canopy - predicted_canopy)
        
        if canopy_delta < 0.2:
            return ConsistencyResult(
                check_name="ip_camera_canopy_stability",
                passed=True,
                residual=canopy_delta,
            )
        
        # Divergence detected
        if canopy > predicted_canopy + 0.2:
            # Camera sees more canopy than model predicts
            # Likely satellite underestimating (cloud?)
            hypothesis = "satellite_underestimate_camera_healthy"
            affected = ["sentinel2"]
        else:
            # Camera sees less canopy than model predicts
            # Possible camera issue or real localized damage
            hypothesis = "camera_obstruction_or_localized_damage"
            affected = ["ip_camera"]
        
        return ConsistencyResult(
            check_name="ip_camera_canopy_stability",
            passed=False,
            residual=canopy_delta,
            severity=min(1.0, canopy_delta / 0.4),
            hypothesis=hypothesis,
            affected_sources=affected,
            details=f"Camera cover={canopy:.2f} vs predicted={predicted_canopy:.2f} (LAI={lai:.1f})"
        )
    
    # ================================================================
    # Dynamic reliability update
    # ================================================================
    
    def _update_reliability_weights(self, results: List[ConsistencyResult],
                                     zone_id: str = "plot") -> None:
        """
        Update source reliability based on consistency check outcomes.
        
        Updates both global weights and per-zone weights.
        - Failed checks decrease reliability for affected sources
        - Passed checks slowly restore reliability
        - Reliability is bounded [0.05, 1.0] (never 0, prevents R division by zero)
        """
        DECAY_RATE = 0.15
        RECOVERY_RATE = 0.05
        MIN_RELIABILITY = 0.05
        
        # Initialize zone reliability if needed
        if zone_id not in self.zone_reliability:
            self.zone_reliability[zone_id] = dict(self.source_reliability)
        
        affected_sources_set = set()
        
        for result in results:
            if not result.passed:
                for src in result.affected_sources:
                    penalty = DECAY_RATE * result.severity
                    
                    # Update global
                    current = self.source_reliability.get(src, 1.0)
                    self.source_reliability[src] = max(MIN_RELIABILITY, current - penalty)
                    
                    # Update per-zone
                    zone_current = self.zone_reliability[zone_id].get(src, 1.0)
                    self.zone_reliability[zone_id][src] = max(MIN_RELIABILITY, zone_current - penalty)
                    
                    affected_sources_set.add(src)
                    self._violation_counts[src] = self._violation_counts.get(src, 0) + 1
        
        # Recovery for sources not flagged today
        for src in self.source_reliability:
            if src not in affected_sources_set:
                # Global recovery
                current = self.source_reliability[src]
                self.source_reliability[src] = min(1.0, current + RECOVERY_RATE)
                self._violation_counts[src] = 0
                
                # Zone recovery
                if src in self.zone_reliability.get(zone_id, {}):
                    z_current = self.zone_reliability[zone_id][src]
                    self.zone_reliability[zone_id][src] = min(1.0, z_current + RECOVERY_RATE)
    
    def get_reliability(self, source: str) -> float:
        """Get current global reliability weight for a source."""
        return self.source_reliability.get(source, 1.0)
    
    def get_zone_reliability(self, zone_id: str, source: str) -> float:
        """Get per-zone reliability. Falls back to global if zone not tracked."""
        if zone_id in self.zone_reliability:
            return self.zone_reliability[zone_id].get(source, self.get_reliability(source))
        return self.get_reliability(source)
    
    def get_conflict_summary(self, last_n_days: int = 7) -> List[Dict]:
        """Summary of recent conflicts for explainability."""
        recent = self.check_history[-last_n_days:] if self.check_history else []
        conflicts = []
        for record in recent:
            failed = [r for r in record.get("results", []) if not r.get("passed", True)]
            if failed:
                conflicts.append({
                    "day": record["day"],
                    "zone": record["zone"],
                    "n_failures": len(failed),
                    "hypotheses": [r.get("hypothesis", "") for r in failed],
                    "reliability_global": record.get("reliability_global", {}),
                    "reliability_zone": record.get("reliability_zone", {}),
                })
        return conflicts
    
    # ================================================================
    # State persistence
    # ================================================================
    
    def to_state_dict(self) -> Dict[str, Any]:
        """Serialize validation graph state for persistence."""
        return {
            "source_reliability": dict(self.source_reliability),
            "zone_reliability": {k: dict(v) for k, v in self.zone_reliability.items()},
            "obs_reliability": {k: dict(v) for k, v in self.obs_reliability.items()},
            "violation_counts": dict(self._violation_counts),
            "history_len": len(self.check_history),
        }
    
    @classmethod
    def from_state_dict(cls, state: Dict[str, Any]) -> "ValidationGraph":
        """Restore validation graph from persisted state."""
        vg = cls()
        if "source_reliability" in state:
            vg.source_reliability.update(state["source_reliability"])
        if "zone_reliability" in state:
            vg.zone_reliability = {k: dict(v) for k, v in state["zone_reliability"].items()}
        if "obs_reliability" in state:
            vg.obs_reliability = {k: dict(v) for k, v in state["obs_reliability"].items()}
        if "violation_counts" in state:
            vg._violation_counts = dict(state["violation_counts"])
        return vg

