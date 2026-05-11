
"""
Layer 2 Runner: Coordinator
Orchestrates Growth Modeling and Phenology Inference.
"""

from typing import Dict, List, Any
import math
import statistics
from datetime import datetime, timezone

from layer2_veg_int.schema import (
    VegIntOutput, VegIntInput, ModeledCurveOutput, CurveQuality, 
    PhenologyOutput, VegetationAnomaly, SpatialMetrics
)
from layer2_veg_int.growth_engine import GrowthCurveEngine
from layer2_veg_int.phenology_engine import PhenologyEngine
from layer1_fusion.schema import FieldTensor, FieldTensorChannels

from layer2_veg_int.anomaly_engine import TemporalAnomalyEngine
from layer2_veg_int.spatial_engine import SpatialProxyStabilityEngine
from layer2_veg_int.invariants import enforce_layer2_invariants

import logging
logger = logging.getLogger(__name__)

class VegetationIntelligenceEngine:
    
    def __init__(self):
        self.growth_engine = GrowthCurveEngine()
        self.phenology_engine = PhenologyEngine()
        self.anomaly_engine = TemporalAnomalyEngine()
        self.spatial_engine = SpatialProxyStabilityEngine()
        
    def analyze_tensor(self, tensor: FieldTensor) -> VegIntOutput:
        """
        Main Entry Point for Layer 2.
        Strict Contract: FieldTensor -> VegIntInput -> VegIntOutput

        Gracefully degrades when plot_timeseries is empty — returns a
        minimal output so downstream layers can still run in diagnostic mode.
        """
        if not tensor.plot_timeseries:
            logger.warning(
                "[Layer 2] FieldTensor has empty plot_timeseries — "
                "returning degraded output (no curve/phenology data)."
            )
            return VegIntOutput(
                run_id=f"vegint_{tensor.run_id}_degraded",
                layer1_run_id=tensor.run_id,
                curve=ModeledCurveOutput(
                    ndvi_fit=[], ndvi_fit_d1=[], ndvi_fit_unc=[],
                    quality=CurveQuality(rmse=0.0, outlier_frac=0.0, obs_coverage=0.0),
                ),
                phenology=PhenologyOutput(
                    stage_by_day=[], confidence_by_day=[], key_dates={},
                ),
                anomalies=[],
                stability=SpatialMetrics(
                    mean_spatial_var=0.0, std_spatial_var=0.0,
                    stability_class="UNKNOWN", confidence=0.0,
                ),
                provenance={
                    "engine_version": "2.2.0-uncertainty",
                    "execution_time": datetime.now(timezone.utc).isoformat(),
                    "status": "degraded",
                    "reason": "empty_plot_timeseries",
                },
            )
            
        # 1. Map to Strict Input Schema
        inputs: List[VegIntInput] = []
        for r in tensor.plot_timeseries:
            inputs.append(VegIntInput(
                date=r.get("date", ""),
                ndvi_obs=r.get("ndvi_mean") if r.get("is_observed") else None,
                # Use raw 'ndvi_mean' for fitting if observed, or 'ndvi_interpolated' ?
                # The contract says: ndvi_obs (raw observed if exists else None)
                # But growth engine needs a continuous series usually. 
                # We will extract continuous series for the engine below.
                ndvi_unc_obs=r.get("uncertainty", 0.1),
                is_observed=r.get("is_observed", False),
                rain=r.get("rain", 0.0),
                tmean=r.get("tmean", 20.0),
                gdd=r.get("gdd", 0.0),
                vv=r.get("vv"),
                vh=r.get("vh")
            ))
            
        # Extract Vectors for Vectorized Engines
        dates = [i.date for i in inputs]
        # Use interpolated values from Layer 1 for fitting if obs is missing?
        # Layer 1 provides 'ndvi_interpolated'. Runner should probably use that as the base signal 
        # but weighting by is_observed.
        # Let's check what Layer 1 provides in 'ndvi_mean' vs 'ndvi_interpolated'.
        # Layer 1 'ndvi_mean' is None if not observed. 'ndvi_interpolated' is always full.
        # We will use 'ndvi_interpolated' as the signal to fit, but trust it less where is_observed=False.
        
        # NOTE: tensor.plot_timeseries has 'ndvi_interpolated' or 'ndvi_smoothed'
        signal_to_fit = [r.get("ndvi_interpolated", 0.0) for r in tensor.plot_timeseries]
        unc_series = [i.ndvi_unc_obs for i in inputs]
        
        # 2. Growth Curve Modeling
        modeled_ndvi, derivatives, fit_unc = self.growth_engine.fit_growth_curve(
            dates, signal_to_fit, unc_series
        )
        
        integrals = self.growth_engine.compute_integrals(modeled_ndvi)
        
        # 3. Phenology Inference
        # Calculate Cumulative GDD
        cumulative_gdd = []
        acc = 0.0
        for i in inputs:
            acc += i.gdd
            cumulative_gdd.append(acc)

        stages, stage_confs = self.phenology_engine.infer_daily_stages(
            modeled_ndvi, derivatives["velocity"], dates, cumulative_gdd, uncertainty=fit_unc
        )
        transitions = self.phenology_engine.extract_transitions(dates, stages)
        
        # 4. Anomaly Detection (Compare Obs vs Fit)
        # We used interpolated for fitting, but we detect anomalies on Observed vs Fit
        # If no observation, no anomaly detection (usually).
        # existing anomaly engine handles this logic currently.
        obs_series = [i.ndvi_obs if i.ndvi_obs is not None else signal_to_fit[idx] for idx, i in enumerate(inputs)]
        rainfall_series = [i.rain for i in inputs]
        
        # Enhanced inputs (SAR + GDD)
        sar_vv_series = [i.vv for i in inputs]
        sar_vh_series = [i.vh for i in inputs]
        
        anomalies = self.anomaly_engine.detect_anomalies(
            dates=dates, 
            observed_ndvi=obs_series, 
            modeled_ndvi=modeled_ndvi, 
            uncertainties=unc_series, 
            rainfall=rainfall_series,
            sar_vv=sar_vv_series,
            sar_vh=sar_vh_series
        )
        
        # 5. Spatial Stability (Updated with Confidence)
        spatial_metrics = self.spatial_engine.analyze_stability(dates, unc_series)
        
        # 6. Quality Metrics
        # Simple RMSE of fit vs obs
        residuals = []
        for i, obs in enumerate(obs_series):
            if inputs[i].is_observed and obs is not None:
                residuals.append((obs - modeled_ndvi[i])**2)
        
        if residuals:
            mse = statistics.mean(residuals)
            rmse = math.sqrt(mse)
        else:
            rmse = 0.0
        
        # 7. Pack Output
        curve_out = ModeledCurveOutput(
            ndvi_fit=modeled_ndvi,
            ndvi_fit_d1=derivatives["velocity"],
            ndvi_fit_unc=fit_unc,
            quality=CurveQuality(
                rmse=float(rmse),
                outlier_frac=0.0, # Placeholder until robust loss implemented
                obs_coverage=sum(1 for i in inputs if i.is_observed) / len(inputs)
            )
        )
        
        pheno_out = PhenologyOutput(
            stage_by_day=[s.value for s in stages],
            confidence_by_day=stage_confs,
            key_dates=transitions
        )

        # --- SPATIAL EXTENSIONS (Phase 11): Zonal Phenology ---
        zone_metrics = {}
        if hasattr(tensor, "zone_stats") and "ndvi" in tensor.zone_stats:
            for z_id, z_timeseries in tensor.zone_stats["ndvi"].items():
                if not z_timeseries: continue
                # Extract Zonal Signal
                z_signal = []
                z_obs = []
                for idx, t_point in enumerate(z_timeseries):
                    mean_val = t_point.get("mean")
                    if mean_val is not None and not math.isnan(mean_val):
                        z_signal.append(mean_val)
                        if inputs[idx].is_observed:
                            z_obs.append(mean_val)
                        else:
                            z_obs.append(None)
                    else:
                        z_signal.append(signal_to_fit[idx]) # Fallback to plot mean
                        z_obs.append(None)
                        
                # Model Zonal Curve
                z_modeled, z_deriv, z_unc = self.growth_engine.fit_growth_curve(
                    dates, z_signal, unc_series
                )
                
                # Zonal Phenology
                z_stages, z_stage_confs = self.phenology_engine.infer_daily_stages(
                    z_modeled, z_deriv["velocity"], dates, cumulative_gdd, uncertainty=z_unc
                )
                z_transitions = self.phenology_engine.extract_transitions(dates, z_stages)
                
                # Zonal RMSE
                z_res = []
                for i, obs in enumerate(z_obs):
                    if obs is not None:
                        z_res.append((obs - z_modeled[i])**2)
                z_rmse = math.sqrt(statistics.mean(z_res)) if z_res else 0.0
                
                zone_metrics[z_id] = {
                    "curve": ModeledCurveOutput(
                        ndvi_fit=z_modeled,
                        ndvi_fit_d1=z_deriv["velocity"],
                        ndvi_fit_unc=z_unc,
                        quality=CurveQuality(rmse=z_rmse, outlier_frac=0.0, obs_coverage=curve_out.quality.obs_coverage)
                    ),
                    "phenology": PhenologyOutput(
                        stage_by_day=[s.value for s in z_stages],
                        confidence_by_day=z_stage_confs,
                        key_dates=z_transitions
                    )
                }

        output = VegIntOutput(
            run_id=f"vegint_{tensor.run_id}",
            layer1_run_id=tensor.run_id,
            curve=curve_out,
            phenology=pheno_out,
            anomalies=anomalies,
            stability=spatial_metrics,
            zone_metrics=zone_metrics,
            provenance={
                "engine_version": "2.2.0-uncertainty",
                "execution_time": datetime.now(timezone.utc).isoformat(),
                "models": {
                    "growth": "RobustSpline_v2_Unc", 
                    "phenology": "GDD_Probabilistic_v1",
                    "anomaly": "TemporalZScore_v1",
                    "spatial": "ZoneCheck_Prob_v1"
                }
            }
        )

        # Invariant Enforcement (Mandatory Gate)
        violations = enforce_layer2_invariants(output)
        errors = [v for v in violations if v.severity == "error"]
        if errors:
            logger.error(
                f"[Layer 2] {len(errors)} invariant error(s) detected — "
                f"output returned with violations logged"
            )
        elif violations:
            logger.info(f"[Layer 2] {len(violations)} invariant warning(s)")

        return output

# Singleton
veg_int_engine = VegetationIntelligenceEngine()

from orchestrator_v2.schema import OrchestratorInput

def run_layer2_veg(inputs: OrchestratorInput, tensor: FieldTensor) -> VegIntOutput:
    """
    Standard Entry Point for Layer 2.
    """
    return veg_int_engine.analyze_tensor(tensor)
