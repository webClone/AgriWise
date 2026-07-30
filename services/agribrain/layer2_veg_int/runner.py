
"""
Layer 2 Runner: Coordinator (v3.2)

Orchestrates Growth Modeling, Phenology Inference, Anomaly Detection,
Spatial Analysis, and Crop Health Index computation.

Enhancements over v3.1:
  - CASA NPP model with temperature/moisture stress scalars (Potter 1993)
  - Water Use Efficiency (Steduto 2009 AquaCrop)
  - Effective GDD with heat penalty + photoperiod gating (Sánchez 2014)
  - Vernalization chill unit tracking (Richardson 1974)
  - STL-lite spectral decomposition for anomaly residuals (Cleveland 1990)
  - Adaptive CUSUM with phenology-phase variability
  - Ensemble smoother (Whittaker + Savitzky-Golay blend)
"""

from typing import Dict, List, Any
import math
import statistics
from datetime import datetime, timezone

from layer2_veg_int.schema import (
    VegIntOutput, VegIntInput, ModeledCurveOutput, CurveQuality,
    PhenologyOutput, VegetationAnomaly, SpatialMetrics,
    CropHealthIndex, GrowthMetrics,
)
from layer2_veg_int.growth_engine import GrowthCurveEngine
from layer2_veg_int.phenology_engine import (
    PhenologyEngine,
    accumulate_chill_units,
    compute_vernalization_gate,
    compute_effective_gdd,
)
from layer1_fusion.schema import FieldTensor, FieldTensorChannels
from crop_database import get_architecture_class

from layer2_veg_int.anomaly_engine import TemporalAnomalyEngine, spectral_decomposition
from layer2_veg_int.spatial_engine import SpatialAnalysisEngine
from layer2_veg_int.invariants import enforce_layer2_invariants

import logging
logger = logging.getLogger(__name__)

# Architectures that cycle through DORMANCY instead of BARE_SOIL/HARVESTED
_PERENNIAL_ARCHS = {"perennial", "tropical_tree"}


def _finite_value(value: Any):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _fill_supported_signal(values: List[Any]) -> List[float]:
    """Linearly fill internal gaps without converting missing NDVI to zero."""
    clean = [_finite_value(value) for value in values]
    support = [index for index, value in enumerate(clean) if value is not None]
    if not support:
        return []
    for index in range(len(clean)):
        if clean[index] is not None:
            continue
        previous = next(
            (item for item in reversed(support) if item < index), None
        )
        following = next(
            (item for item in support if item > index), None
        )
        if previous is not None and following is not None:
            fraction = (index - previous) / (following - previous)
            clean[index] = float(clean[previous]) + fraction * (
                float(clean[following]) - float(clean[previous])
            )
        elif previous is not None:
            clean[index] = float(clean[previous])
        elif following is not None:
            clean[index] = float(clean[following])
    return [float(value) for value in clean]


class VegetationIntelligenceEngine:

    def __init__(self):
        self.growth_engine = GrowthCurveEngine()
        self.anomaly_engine = TemporalAnomalyEngine()
        self.spatial_engine = SpatialAnalysisEngine()

    def analyze_tensor(self, tensor: FieldTensor, orch_inputs=None) -> VegIntOutput:
        """
        Main Entry Point for Layer 2.
        Strict Contract: FieldTensor → VegIntInput → VegIntOutput

        Gracefully degrades when plot_timeseries is empty.
        """
        def _has_valid_ndvi(r: dict) -> bool:
            if not isinstance(r, dict):
                return False
            val = r.get("ndvi_mean") if r.get("ndvi_mean") is not None else (
                r.get("ndvi") if r.get("ndvi") is not None else (
                    r.get("mean_ndvi") if r.get("mean_ndvi") is not None else r.get("ndvi_clean")
                )
            )
            if val is None or not isinstance(val, (int, float)):
                return False
            if r.get("is_synthetic") is True:
                return False
            source_str = str(r.get("source") or r.get("truth_class") or "").lower()
            return "synthetic" not in source_str or r.get("is_observed") is True or r.get("ndvi_mean") is not None

        observed_count = sum(1 for r in (tensor.plot_timeseries or []) if _has_valid_ndvi(r))

        if not tensor.plot_timeseries or observed_count == 0:
            reason = "empty_plot_timeseries" if not tensor.plot_timeseries else "no_observed_ndvi"
            logger.warning(
                f"[Layer 2] FieldTensor has degraded input ({reason}) — "
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
                    "engine_version": "3.1.0",
                    "execution_time": datetime.now(timezone.utc).isoformat(),
                    "status": "degraded",
                    "reason": reason,
                },
            )

        # ═══════════════════════════════════════════════════════════════
        # 1. Map to Strict Input Schema (v3.1: + ET0, temp_max, temp_min)
        # ═══════════════════════════════════════════════════════════════
        inputs: List[VegIntInput] = []
        for r in tensor.plot_timeseries:
            inputs.append(VegIntInput(
                date=r.get("date", ""),
                ndvi_obs=r.get("ndvi_mean") if r.get("is_observed") else None,
                ndvi_unc_obs=r.get("uncertainty", 0.1),
                is_observed=r.get("is_observed", False),
                rain=r.get("rain"),
                tmean=r.get("tmean"),
                gdd=r.get("gdd"),
                vv=r.get("vv"),
                vh=r.get("vh"),
                # Multi-spectral indices (v3.0)
                evi=r.get("evi"),
                ndwi=r.get("ndwi"),
                ndmi=r.get("ndmi"),
                # v3.1: Weather detail
                et0=r.get("et0"),
                temp_max=r.get("temp_max"),
                temp_min=r.get("temp_min"),
            ))

        # Extract vectors
        dates = [i.date for i in inputs]
        signal_to_fit = _fill_supported_signal([
            (
                r.get("ndvi_interpolated")
                if _finite_value(r.get("ndvi_interpolated")) is not None
                else r.get("ndvi_mean")
            )
            for r in tensor.plot_timeseries
        ])
        if len(signal_to_fit) != len(tensor.plot_timeseries):
            raise ValueError(
                "Layer 2 has observed NDVI metadata but no finite NDVI values"
            )
        unc_series = [i.ndvi_unc_obs for i in inputs]

        # Multi-spectral vectors
        evi_series = [i.evi for i in inputs]
        ndwi_series = [i.ndwi for i in inputs]
        ndmi_series = [i.ndmi for i in inputs]
        temperature_series = [i.tmean for i in inputs]
        et0_series = [i.et0 for i in inputs]
        temp_min_series = [i.temp_min for i in inputs]
        rainfall_series = [i.rain for i in inputs]

        # ═══════════════════════════════════════════════════════════════
        # 1b. Resolve Crop Configuration
        # ═══════════════════════════════════════════════════════════════
        crop_config = None
        is_perennial = False
        crop_record = None
        crop_ndvi_sig = None
        crop_raw = ""
        latitude = None
        latitude_source = "missing"

        if orch_inputs is not None:
            cfg = getattr(orch_inputs, 'crop_config', None)
            if isinstance(cfg, dict):
                crop_raw = str(cfg.get('crop', cfg.get('crop_type', ''))).lower()
                crop_config = _resolve_crop_phenology_config(crop_raw)
                arch = get_architecture_class(crop_raw)
                is_perennial = arch in _PERENNIAL_ARCHS

                # Resolve CropRecord for Kc, temp thresholds
                crop_record = _resolve_crop_record(crop_raw)

                # Resolve NDVI signature for crop-specific emissions
                crop_ndvi_sig = _resolve_ndvi_signature(crop_raw)

            # Location authority lives in operational_context. crop_config is
            # accepted only as an explicitly supplied compatibility source.
            operational = getattr(orch_inputs, 'operational_context', None)
            operational = operational if isinstance(operational, dict) else {}
            lat = operational.get('lat', operational.get('latitude'))
            if lat is not None:
                latitude_source = "operational_context"
            elif isinstance(cfg, dict):
                lat = cfg.get('latitude')
                if lat is not None:
                    latitude_source = "crop_config"
            try:
                candidate_latitude = float(lat) if lat is not None else None
                if (
                    candidate_latitude is not None
                    and math.isfinite(candidate_latitude)
                    and -90.0 <= candidate_latitude <= 90.0
                ):
                    latitude = candidate_latitude
                else:
                    latitude_source = "missing"
            except (TypeError, ValueError):
                latitude = None
                latitude_source = "missing"

        # ═══════════════════════════════════════════════════════════════
        # 2. Growth Curve Modeling (v3.2: Ensemble Smoother)
        # ═══════════════════════════════════════════════════════════════
        modeled_ndvi, derivatives, fit_unc = self.growth_engine.fit_growth_curve(
            dates, signal_to_fit, unc_series
        )

        # v3.2: Attempt ensemble blend (Whittaker + SG) for better fit
        try:
            ens_curve, ens_deriv, ens_unc = self.growth_engine._fit_ensemble(
                signal_to_fit, unc_series
            )
            if ens_curve and len(ens_curve) == len(modeled_ndvi):
                modeled_ndvi = ens_curve
                fit_unc = ens_unc
                # _fit_ensemble now returns derivatives as dict (V922.2A fix)
                if isinstance(ens_deriv, dict):
                    derivatives = ens_deriv
                elif isinstance(ens_deriv, (tuple, list)) and len(ens_deriv) >= 2:
                    derivatives = {
                        "velocity": list(ens_deriv[0]),
                        "acceleration": list(ens_deriv[1]),
                    }
                # else: keep original derivatives from fit_growth_curve
        except Exception:
            pass  # Fall back to Whittaker-only

        # V922.2A: Enforce length consistency after all curve fitting
        from .growth_engine import _align_length
        target_len = len(modeled_ndvi)
        fit_unc = _align_length(fit_unc, target_len)
        if "velocity" in derivatives:
            derivatives["velocity"] = _align_length(derivatives["velocity"], target_len, fill_value=0.0)
        if "acceleration" in derivatives:
            derivatives["acceleration"] = _align_length(derivatives.get("acceleration", []), target_len, fill_value=0.0)

        integrals = self.growth_engine.compute_integrals(modeled_ndvi)

        # Double logistic fitting (for SOS/EOS/LOS)
        dbl_logistic = self.growth_engine.fit_double_logistic(modeled_ndvi, dates)

        # SOS/EOS/LOS from curve
        season_dates = GrowthCurveEngine.extract_season_dates(modeled_ndvi, dates)

        # ═══════════════════════════════════════════════════════════════
        # 3. Biophysical Products (LAI, fPAR, FVC, NPP, CWSI)
        # ═══════════════════════════════════════════════════════════════
        lai_series = GrowthCurveEngine.estimate_lai(modeled_ndvi)
        cwsi_series = GrowthCurveEngine.compute_cwsi(ndwi_series, modeled_ndvi)
        fpar_series = GrowthCurveEngine.compute_fpar(modeled_ndvi)
        fvc_series = GrowthCurveEngine.compute_fvc(modeled_ndvi)

        # NPP: v3.2 CASA model with stress scalars (Potter 1993)
        # Falls back to simple fPAR × PAR proxy when temperature data unavailable
        start_doy = 1
        if dates and dates[0]:
            try:
                from datetime import date as dt_date
                parts = dates[0].split("-")
                d = dt_date(int(parts[0]), int(parts[1]), int(parts[2]))
                start_doy = d.timetuple().tm_yday
            except Exception:
                pass

        # Determine optimal temp for CASA from crop record
        casa_t_opt = 25.0
        casa_t_min = 5.0
        casa_t_max = 45.0
        if crop_record:
            casa_t_opt = getattr(crop_record, 'optimal_temp_mean', 25.0)
            casa_t_min = getattr(crop_record, 'optimal_temp_min', 5.0)
            casa_t_max = getattr(crop_record, 'optimal_temp_max', 45.0)

        npp_series = (
            GrowthCurveEngine.compute_npp_casa(
                fpar_series=fpar_series,
                latitude=latitude,
                start_doy=start_doy,
                temperature_series=temperature_series,
                cwsi_series=cwsi_series,
                t_opt=casa_t_opt,
                t_min=casa_t_min,
                t_max=casa_t_max,
            )
            if latitude is not None else []
        )

        # ═══════════════════════════════════════════════════════════════
        # 3b. FAO-56 Water Balance (v3.1)
        # ═══════════════════════════════════════════════════════════════
        et_actual_series = []
        et_deficit_series = []

        weather_missing = all(i.tmean is None for i in inputs) or all(i.rain is None for i in inputs)

        if not weather_missing and crop_record and any(et0 is not None for et0 in et0_series):
            # Build stage-dependent Kc series
            # Uses phenology stages once they are computed (chicken-and-egg:
            # we compute a preliminary Kc from NDVI as proxy)
            kc_series = _build_kc_series_from_ndvi(modeled_ndvi, crop_record)
            et_actual_series, et_deficit_series = GrowthCurveEngine.compute_water_balance(
                et0_series, rainfall_series, kc_series
            )

        # ═══════════════════════════════════════════════════════════════
        # 4. Phenology Inference (Viterbi HMM with crop-specific emissions)
        # ═══════════════════════════════════════════════════════════════

        # v3.2: Effective GDD with heat penalty + photoperiod gating
        # Uses Sánchez (2014) stress-corrected thermal time
        temp_max_series = [i.temp_max for i in inputs]
        is_short_day = crop_raw in ("rice", "millet", "sorghum")
        t_base_gdd = 10.0
        t_opt_max_gdd = 35.0
        if crop_config:
            t_base_gdd = crop_config.get("gdd_base_temp", 10.0)
        if crop_record:
            t_opt_max_gdd = getattr(crop_record, 'optimal_temp_max', 35.0)

        photoperiod_engine = PhenologyEngine(
            crop_config,
            is_perennial=is_perennial,
            crop_ndvi_signature=crop_ndvi_sig,
            latitude=latitude,
        )
        cumulative_gdd = []
        acc = 0.0
        for input_index, i in enumerate(inputs):
            if i.tmean is None:
                cumulative_gdd.append(acc)
                continue
            t_max_val = i.temp_max if i.temp_max is not None else i.tmean + 5.0
            eff_gdd = compute_effective_gdd(
                t_mean=i.tmean,
                t_max=t_max_val,
                t_base=t_base_gdd,
                t_opt_max=t_opt_max_gdd,
                day_length=photoperiod_engine._compute_photoperiod(
                    dates[input_index] if input_index < len(dates) else ""
                ),
                is_short_day=is_short_day,
            )
            acc += eff_gdd
            cumulative_gdd.append(acc)

        # v3.2: Vernalization tracking (Richardson 1974)
        arch_class = get_architecture_class(crop_raw) if crop_raw else "cereal"
        vern_results = {"vernalization_progress": 1.0, "vernalization_complete": True,
                        "obligate_vernalization": False}
        tm_series = [t for t in temp_min_series if t is not None]
        if tm_series:
            vern_results = accumulate_chill_units(tm_series, arch_class)

        pheno_engine = photoperiod_engine

        stages, stage_confs = pheno_engine.infer_daily_stages(
            modeled_ndvi, derivatives["velocity"], dates, cumulative_gdd,
            uncertainty=fit_unc, ndwi_series=ndwi_series,
        )
        transitions = pheno_engine.extract_transitions(dates, stages)

        # ═══════════════════════════════════════════════════════════════
        # 5. Anomaly Detection (Multi-Index + Isolation Forest + EWMA)
        # ═══════════════════════════════════════════════════════════════
        obs_series = [
            i.ndvi_obs if i.ndvi_obs is not None else signal_to_fit[idx]
            for idx, i in enumerate(inputs)
        ]
        sar_vv_series = [i.vv for i in inputs]
        sar_vh_series = [i.vh for i in inputs]

        # Crop-specific temperature thresholds
        crop_temp_max = 35.0
        crop_temp_min = 5.0
        if crop_record:
            crop_temp_max = getattr(crop_record, 'optimal_temp_max', 35.0)
            crop_temp_min = getattr(crop_record, 'optimal_temp_min', 5.0)

        anomalies = self.anomaly_engine.detect_anomalies(
            dates=dates,
            observed_ndvi=obs_series,
            modeled_ndvi=modeled_ndvi,
            uncertainties=unc_series,
            rainfall=rainfall_series,
            sar_vv=sar_vv_series,
            sar_vh=sar_vh_series,
            temperature=temperature_series,
            evi_series=evi_series,
            ndwi_series=ndwi_series,
            ndmi_series=ndmi_series,
            crop_temp_max=crop_temp_max,
            crop_temp_min=crop_temp_min,
            temp_min_series=temp_min_series,
        )

        # v3.2: STL-lite spectral decomposition (Cleveland 1990)
        # Separates trend/seasonal/residual so anomalies fire on residual only
        stl_result = None
        if len(obs_series) >= 10 and len(modeled_ndvi) >= 10:
            try:
                stl_result = spectral_decomposition(
                    observed=obs_series,
                    modeled=modeled_ndvi,
                    dates=dates,
                )
            except Exception:
                stl_result = None

        # ═══════════════════════════════════════════════════════════════
        # 6. Spatial Stability + Moran's I + CUSUM + Zone Health
        # ═══════════════════════════════════════════════════════════════
        spatial_std_series = None
        zone_means_for_moran = None

        if hasattr(tensor, "zone_stats") and "ndvi" in tensor.zone_stats:
            zone_ndvi = tensor.zone_stats["ndvi"]
            if zone_ndvi and len(zone_ndvi) >= 2:
                n_ts = len(next(iter(zone_ndvi.values())))
                spatial_std_series = []
                zone_means_for_moran = {}

                for z_id, z_ts in zone_ndvi.items():
                    zone_vals = []
                    for t_idx in range(min(n_ts, len(z_ts))):
                        v = z_ts[t_idx].get("mean") if isinstance(z_ts[t_idx], dict) else None
                        if v is not None and not math.isnan(v):
                            zone_vals.append(v)
                        else:
                            zone_vals.append(0.0)
                    zone_means_for_moran[z_id] = zone_vals

                for t_idx in range(n_ts):
                    vals = []
                    for z_ts in zone_ndvi.values():
                        if t_idx < len(z_ts):
                            v = z_ts[t_idx].get("mean") if isinstance(z_ts[t_idx], dict) else None
                            if v is not None and not math.isnan(v):
                                vals.append(v)
                    if len(vals) >= 2:
                        spatial_std_series.append(statistics.stdev(vals))
                    else:
                        spatial_std_series.append(0.0)

        if not spatial_std_series:
            spatial_std_series = unc_series  # Fallback to uncertainty proxy

        # v3.2: Compute phase variability for adaptive CUSUM
        stage_strs = [s.value if hasattr(s, 'value') else str(s) for s in stages]
        phase_var = SpatialAnalysisEngine.estimate_phase_variability(stage_strs)
        n_obs_season = sum(1 for i in inputs if i.is_observed)

        spatial_metrics = self.spatial_engine.analyze_stability(
            dates, spatial_std_series, zone_means=zone_means_for_moran,
            phase_variability=phase_var,
            n_season_observations=n_obs_season,
        )

        # ═══════════════════════════════════════════════════════════════
        # 7. Quality Metrics
        # ═══════════════════════════════════════════════════════════════
        residuals = []
        for i, obs in enumerate(obs_series):
            if inputs[i].is_observed and obs is not None:
                residuals.append((obs - modeled_ndvi[i])**2)

        rmse = math.sqrt(statistics.mean(residuals)) if residuals else 0.0

        # Outlier fraction (count residuals > 2σ)
        if residuals and len(residuals) > 2:
            res_vals = [math.sqrt(r) for r in residuals]
            mu = statistics.mean(res_vals)
            sigma = statistics.stdev(res_vals) if len(res_vals) > 1 else 0.1
            outlier_frac = sum(1 for r in res_vals if abs(r - mu) > 2 * sigma) / len(res_vals)
        else:
            outlier_frac = 0.0

        # ═══════════════════════════════════════════════════════════════
        # 8. Crop Health Index (Crop-Normalized, Theil-Sen Vigor)
        # ═══════════════════════════════════════════════════════════════
        health_index = self._compute_health_index(
            modeled_ndvi, lai_series, cwsi_series, anomalies,
            integrals, len(inputs), fpar_series, fvc_series,
            et_actual_series, et_deficit_series, crop_ndvi_sig,
        )
        if weather_missing:
            health_index.confidence = min(health_index.confidence, 0.3)

        # v3.2: Water Use Efficiency (Steduto 2009 — AquaCrop)
        if et_actual_series and npp_series:
            # Use NPP as biomass proxy for WUE
            biomass_cumulative = []
            running = 0.0
            for npp_val in npp_series:
                running += npp_val
                biomass_cumulative.append(running)

            wue_result = GrowthCurveEngine.compute_water_use_efficiency(
                biomass_series=biomass_cumulative,
                et_actual_series=et_actual_series,
            )
            health_index.wue = wue_result.get("wue", 0.0)
            health_index.crop_water_productivity = wue_result.get("crop_water_productivity", 0.0)

        # v3.2: Populate vernalization progress
        health_index.vernalization_progress = vern_results.get("vernalization_progress", 1.0)

        # ═══════════════════════════════════════════════════════════════
        # 9. Growth Metrics
        # ═══════════════════════════════════════════════════════════════
        velocity = derivatives["velocity"]
        growth_metrics = GrowthMetrics(
            peak_ndvi=integrals.get("peak_value", 0.0),
            peak_date=season_dates.get("peak_date", ""),
            auc_season=integrals.get("auc_season", 0.0),
            auc_small=integrals.get("auc_small", 0.0),
            max_growth_rate=max(velocity) if velocity else 0.0,
            senescence_rate=min(velocity) if velocity else 0.0,
            sos_date=season_dates.get("sos_date", ""),
            eos_date=season_dates.get("eos_date", ""),
            los_days=season_dates.get("los_days", 0),
        )

        # ═══════════════════════════════════════════════════════════════
        # 10. Pack Output
        # ═══════════════════════════════════════════════════════════════
        curve_out = ModeledCurveOutput(
            ndvi_fit=modeled_ndvi,
            ndvi_fit_d1=derivatives["velocity"],
            ndvi_fit_d2=derivatives.get("acceleration", []),
            ndvi_fit_unc=fit_unc,
            lai_series=lai_series,
            cwsi_series=cwsi_series,
            fpar_series=fpar_series,
            fvc_series=fvc_series,
            npp_series=npp_series,
            quality=CurveQuality(
                rmse=float(rmse),
                outlier_frac=float(outlier_frac),
                obs_coverage=sum(1 for i in inputs if i.is_observed) / len(inputs),
            ),
        )

        pheno_out = PhenologyOutput(
            stage_by_day=[s.value for s in stages],
            confidence_by_day=stage_confs,
            key_dates=transitions,
        )

        # --- SPATIAL EXTENSIONS: Zonal Phenology ---
        zone_metrics = {}
        if hasattr(tensor, "zone_stats") and "ndvi" in tensor.zone_stats:
            for z_id, z_timeseries in tensor.zone_stats["ndvi"].items():
                if not z_timeseries:
                    continue
                z_signal = []
                z_obs = []
                for idx, t_point in enumerate(z_timeseries):
                    if idx >= len(inputs) or idx >= len(signal_to_fit):
                        break
                    mean_val = t_point.get("mean")
                    if mean_val is not None and not math.isnan(mean_val):
                        z_signal.append(mean_val)
                        z_obs.append(mean_val if inputs[idx].is_observed else None)
                    else:
                        z_signal.append(signal_to_fit[idx])
                        z_obs.append(None)

                z_modeled, z_deriv, z_unc = self.growth_engine.fit_growth_curve(
                    dates, z_signal, unc_series,
                )
                # V922.2A: Enforce length consistency for zone fits
                from .growth_engine import _align_length
                z_unc = _align_length(z_unc, len(z_modeled))
                if "velocity" in z_deriv:
                    z_deriv["velocity"] = _align_length(z_deriv["velocity"], len(z_modeled), fill_value=0.0)

                z_pheno_engine = PhenologyEngine(
                    crop_config, is_perennial=is_perennial,
                    crop_ndvi_signature=crop_ndvi_sig, latitude=latitude,
                )
                z_stages, z_stage_confs = z_pheno_engine.infer_daily_stages(
                    z_modeled, z_deriv["velocity"], dates, cumulative_gdd,
                    uncertainty=z_unc,
                )
                z_transitions = z_pheno_engine.extract_transitions(dates, z_stages)

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
                        quality=CurveQuality(rmse=z_rmse, outlier_frac=0.0, obs_coverage=curve_out.quality.obs_coverage),
                    ),
                    "phenology": PhenologyOutput(
                        stage_by_day=[s.value for s in z_stages],
                        confidence_by_day=z_stage_confs,
                        key_dates=z_transitions,
                    ),
                }

        output = VegIntOutput(
            run_id=f"vegint_{tensor.run_id}",
            layer1_run_id=tensor.run_id,
            curve=curve_out,
            phenology=pheno_out,
            anomalies=anomalies,
            stability=spatial_metrics,
            health_index=health_index,
            growth_metrics=growth_metrics,
            zone_metrics=zone_metrics,
            provenance={
                "engine_version": "3.2.0",
                "execution_time": datetime.now(timezone.utc).isoformat(),
                "latitude_context": {
                    "available": latitude is not None,
                    "value": latitude,
                    "source": latitude_source,
                    "photoperiod_used": latitude is not None,
                    "casa_npp_used": latitude is not None,
                },
                "crop_posterior_lineage": (
                    (getattr(orch_inputs, 'crop_config', {}) or {}).get(
                        'crop_posterior_hash'
                    ) if orch_inputs is not None else None
                ),
                "crop_lineage_id": (
                    (getattr(orch_inputs, 'crop_config', {}) or {}).get(
                        'crop_lineage_id'
                    ) if orch_inputs is not None else None
                ),
                "models": {
                    "growth": "Ensemble_Whittaker_SG_v32",
                    "phenology": "Viterbi_HMM_EffectiveGDD_Vernalization_v32",
                    "anomaly": "MultiIndex_IsoForest_EWMA_STL_v32",
                    "spatial": "MoranI_MannKendall_AdaptiveCUSUM_v32",
                    "health": "CropNormalized_FAO56_WUE_v32",
                    "npp": "CASA_Potter1993_v32",
                },
                "features": [
                    "ensemble_smoother",
                    "gcv_adaptive_lambda",
                    "savitzky_golay_derivatives",
                    "crop_specific_emissions",
                    "effective_gdd_sanchez2014",
                    "vernalization_richardson1974",
                    "photoperiod_gating",
                    "ewma_changepoint",
                    "frost_damage_detection",
                    "adaptive_cusum_spatial",
                    "stl_spectral_decomposition",
                    "theil_sen_slope",
                    "fao56_water_balance",
                    "casa_npp_potter1993",
                    "water_use_efficiency_steduto2009",
                    "fpar_estimation",
                    "fvc_estimation",
                    "crop_normalized_health",
                    "isolation_forest",
                    "morans_i",
                    "mann_kendall",
                    "lai_estimation",
                    "cwsi",
                    "crop_health_index",
                ],
                "vernalization": {
                    "progress": vern_results.get("vernalization_progress", 1.0),
                    "complete": vern_results.get("vernalization_complete", True),
                    "chill_units": vern_results.get("chill_units_accumulated", 0),
                },
                "stl_decomposition": "computed" if stl_result else "skipped",
            },
        )

        # ═══════════════════════════════════════════════════════════════
        # 11. Invariant Enforcement
        # ═══════════════════════════════════════════════════════════════
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

    # =====================================================================
    # Crop Health Index Computation (v3.1: Crop-Normalized + Theil-Sen)
    # =====================================================================

    def _compute_health_index(
        self,
        modeled_ndvi: List[float],
        lai_series: List[float],
        cwsi_series: List[float],
        anomalies: List[VegetationAnomaly],
        integrals: Dict,
        total_timesteps: int,
        fpar_series: List[float] = None,
        fvc_series: List[float] = None,
        et_actual_series: List[float] = None,
        et_deficit_series: List[float] = None,
        crop_ndvi_sig: Dict = None,
    ) -> CropHealthIndex:
        """Compute composite crop health from all sub-engine outputs.

        v3.1 enhancements:
          - Crop-specific NDVI normalization (uses peak_ndvi from signature)
          - Theil-Sen robust vigor slope
          - ET deficit integration
          - fPAR/FVC reporting

        Weights:
          - NDVI health:    0.25 (current vigor vs crop-specific optimal)
          - Water stress:   0.25 (CWSI + ET deficit)
          - Vigor trend:    0.25 (Theil-Sen robust trajectory)
          - Anomaly penalty: 0.25 (accumulated anomaly severity)
        """
        if not modeled_ndvi:
            return CropHealthIndex()

        # --- Crop-specific peak NDVI ---
        crop_peak_ndvi = 0.75  # Default (generic crop)
        crop_trough_ndvi = 0.12
        if crop_ndvi_sig:
            crop_peak_ndvi = crop_ndvi_sig.get("peak_ndvi", 0.75)
            crop_trough_ndvi = crop_ndvi_sig.get("trough_ndvi", 0.12)

        # 1. NDVI health: current NDVI vs crop-specific optimal
        latest_ndvi = modeled_ndvi[-1] if modeled_ndvi else 0.0
        ndvi_range = crop_peak_ndvi - crop_trough_ndvi
        if ndvi_range < 0.05:
            ndvi_range = 0.05
        # Normalized: 0 at trough, 1 at peak, >1 if above peak
        ndvi_health = max(0.0, min(1.0, (latest_ndvi - crop_trough_ndvi) / ndvi_range))

        # 2. Water stress: composite of CWSI + ET deficit
        recent_cwsi = cwsi_series[-10:] if cwsi_series else [0.5]
        mean_cwsi = statistics.mean(recent_cwsi) if recent_cwsi else 0.5

        # Integrate ET deficit if available
        et_deficit_score = 0.0
        mean_et_deficit = 0.0
        mean_et_actual = 0.0
        if et_deficit_series:
            recent_deficit = et_deficit_series[-10:]
            mean_et_deficit = statistics.mean(recent_deficit) if recent_deficit else 0.0
            # Normalize: 0mm = no stress, 5mm/day = severe
            et_deficit_score = min(1.0, mean_et_deficit / 5.0)

        if et_actual_series:
            recent_actual = et_actual_series[-10:]
            mean_et_actual = statistics.mean(recent_actual) if recent_actual else 0.0

        # Blend CWSI and ET deficit
        if et_deficit_series:
            water_stress = 0.5 * mean_cwsi + 0.5 * et_deficit_score
        else:
            water_stress = mean_cwsi

        # 3. Vigor trend: Theil-Sen robust slope (last 14 days)
        vigor_slope = 0.0
        vigor_trend = "STABLE"
        window = min(14, len(modeled_ndvi))
        if window >= 5:
            recent = modeled_ndvi[-window:]
            # Theil-Sen: median of all pairwise slopes
            slopes = []
            for i in range(len(recent) - 1):
                for j in range(i + 1, len(recent)):
                    slopes.append((recent[j] - recent[i]) / (j - i))

            if slopes:
                slopes.sort()
                vigor_slope = slopes[len(slopes) // 2]

                if vigor_slope > 0.005:
                    vigor_trend = "IMPROVING"
                elif vigor_slope < -0.005:
                    vigor_trend = "DECLINING"
                else:
                    vigor_trend = "STABLE"

        # 4. Anomaly penalty
        total_severity = sum(a.severity for a in anomalies)
        anomaly_penalty = min(1.0, total_severity * 0.3)

        # 5. Composite score
        vigor_score = 0.5 + min(0.5, max(-0.5, vigor_slope * 50))  # Map slope to [0, 1]
        overall = (
            0.25 * ndvi_health
            + 0.25 * (1.0 - water_stress)
            + 0.25 * vigor_score
            + 0.25 * (1.0 - anomaly_penalty)
        )
        overall = max(0.0, min(1.0, overall))

        # 6. Confidence: based on data availability
        n_obs = len([v for v in modeled_ndvi if v > 0])
        conf = min(1.0, n_obs / max(1, total_timesteps))

        # LAI
        lai_current = lai_series[-1] if lai_series else 0.0
        lai_peak = max(lai_series) if lai_series else 0.0

        # Biomass proxy: normalized AUC
        auc = integrals.get("auc_season", 0.0)
        biomass = min(1.0, auc / max(1, len(modeled_ndvi) * 0.6))

        # FVC and fPAR
        fvc_current = fvc_series[-1] if fvc_series else 0.0
        fpar_current = fpar_series[-1] if fpar_series else 0.0

        return CropHealthIndex(
            overall_score=round(overall, 3),
            ndvi_health=round(ndvi_health, 3),
            water_stress_index=round(water_stress, 3),
            lai_estimate=round(lai_current, 2),
            lai_peak=round(lai_peak, 2),
            biomass_proxy=round(biomass, 3),
            vigor_trend=vigor_trend,
            vigor_slope=round(vigor_slope, 5),
            anomaly_penalty=round(anomaly_penalty, 3),
            confidence=round(conf, 3),
            et_actual=round(mean_et_actual, 2),
            et_deficit=round(mean_et_deficit, 2),
            vegetation_fraction=round(fvc_current, 3),
            fpar_current=round(fpar_current, 3),
        )


# Singleton
veg_int_engine = VegetationIntelligenceEngine()

from orchestrator_v2.schema import OrchestratorInput

def run_layer2_veg(inputs: OrchestratorInput, tensor: FieldTensor) -> VegIntOutput:
    """Standard Entry Point for Layer 2."""
    return veg_int_engine.analyze_tensor(tensor, orch_inputs=inputs)


# ── Crop Phenology Configuration Lookup ─────────────────────────────────────
# Literature-grounded GDD thresholds per crop architecture class.
# Sources: Becker-Reshef et al. (2010), FAO crop calendars,
#          Wardlow & Egbert (2008), Bolton & Friedl (2013).

_CROP_PHENOLOGY_CONFIGS = {
    "cereal": {
        "name": "Generic Cereal",
        "gdd_base_temp": 0.0,
        "transitions": {
            "emergence_min_gdd": 100,
            "vegetative_min_gdd": 300,
            "reproductive_min_gdd": 800,
            "senescence_min_gdd": 1400,
            "harvest_min_gdd": 1800,
        },
    },
    "maize": {
        "name": "Maize/Corn",
        "gdd_base_temp": 10.0,
        "transitions": {
            "emergence_min_gdd": 60,
            "vegetative_min_gdd": 200,
            "reproductive_min_gdd": 600,
            "senescence_min_gdd": 1100,
            "harvest_min_gdd": 1500,
        },
    },
    "rice": {
        "name": "Rice",
        "gdd_base_temp": 10.0,
        "transitions": {
            "emergence_min_gdd": 80,
            "vegetative_min_gdd": 250,
            "reproductive_min_gdd": 700,
            "senescence_min_gdd": 1300,
            "harvest_min_gdd": 1800,
        },
    },
    "legume": {
        "name": "Legume",
        "gdd_base_temp": 10.0,
        "transitions": {
            "emergence_min_gdd": 60,
            "vegetative_min_gdd": 200,
            "reproductive_min_gdd": 500,
            "senescence_min_gdd": 900,
            "harvest_min_gdd": 1200,
        },
    },
    "vegetable": {
        "name": "Vegetable/Horticultural",
        "gdd_base_temp": 10.0,
        "transitions": {
            "emergence_min_gdd": 50,
            "vegetative_min_gdd": 150,
            "reproductive_min_gdd": 500,
            "senescence_min_gdd": 900,
            "harvest_min_gdd": 1200,
        },
    },
    "perennial": {
        "name": "Perennial Tree/Orchard",
        "gdd_base_temp": 10.0,
        "transitions": {
            "emergence_min_gdd": 50,
            "vegetative_min_gdd": 200,
            "reproductive_min_gdd": 600,
            "senescence_min_gdd": 2000,
            "harvest_min_gdd": 9999,
        },
    },
    "cotton": {
        "name": "Cotton/Fiber",
        "gdd_base_temp": 15.6,
        "transitions": {
            "emergence_min_gdd": 50,
            "vegetative_min_gdd": 200,
            "reproductive_min_gdd": 500,
            "senescence_min_gdd": 1000,
            "harvest_min_gdd": 1400,
        },
    },
    "tropical_tree": {
        "name": "Tropical Tree/Plantation",
        "gdd_base_temp": 15.0,
        "transitions": {
            "emergence_min_gdd": 50,
            "vegetative_min_gdd": 200,
            "reproductive_min_gdd": 500,
            "senescence_min_gdd": 2000,
            "harvest_min_gdd": 9999,
        },
    },
}


def _resolve_crop_phenology_config(crop_name: str):
    """Resolve a crop name to its phenology GDD configuration."""
    if not crop_name:
        return None
    arch = get_architecture_class(crop_name)
    return _CROP_PHENOLOGY_CONFIGS.get(arch)


def _resolve_crop_record(crop_name: str):
    """Resolve a crop name to its CropRecord for Kc, temp thresholds."""
    if not crop_name:
        return None
    try:
        from crop_database import get_crop
        return get_crop(crop_name)
    except Exception:
        return None


def _resolve_ndvi_signature(crop_name: str) -> dict:
    """Resolve a crop name to its NDVI signature for emission tuning."""
    if not crop_name:
        return None
    try:
        from layer2_veg_int.crop_science_data import CROP_NDVI_SIGNATURES
        return CROP_NDVI_SIGNATURES.get(crop_name)
    except Exception:
        return None


def _build_kc_series_from_ndvi(
    modeled_ndvi: List[float],
    crop_record,
) -> List[float]:
    """Build stage-dependent Kc series using NDVI as phenology proxy.

    Maps NDVI to crop growth stage and applies FAO-56 Kc values:
      - NDVI < 0.2 → kc_init
      - NDVI 0.2-0.6 → linear ramp kc_init → kc_mid
      - NDVI > 0.6 → kc_mid
      - After peak: ramp kc_mid → kc_end

    This avoids circular dependency with the HMM phenology engine.
    """
    kc_init = getattr(crop_record, 'kc_init', 0.3)
    kc_mid = getattr(crop_record, 'kc_mid', 1.15)
    kc_end = getattr(crop_record, 'kc_end', 0.4)

    n = len(modeled_ndvi)
    if n == 0:
        return []

    # Find peak index
    peak_idx = modeled_ndvi.index(max(modeled_ndvi))

    kc_series = []
    for i, ndvi in enumerate(modeled_ndvi):
        if i <= peak_idx:
            # Green-up phase
            if ndvi < 0.2:
                kc = kc_init
            elif ndvi < 0.6:
                frac = (ndvi - 0.2) / 0.4
                kc = kc_init + frac * (kc_mid - kc_init)
            else:
                kc = kc_mid
        else:
            # Senescence phase
            if ndvi < 0.2:
                kc = kc_end
            elif ndvi < 0.6:
                frac = (ndvi - 0.2) / 0.4
                kc = kc_end + frac * (kc_mid - kc_end)
            else:
                kc = kc_mid

        kc_series.append(round(kc, 3))

    return kc_series
