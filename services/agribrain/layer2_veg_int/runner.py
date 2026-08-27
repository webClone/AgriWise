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
from layer2_veg_int.crop_response_profile import (
    CropParameterResolver,
    CropResponseProfile,
    CausalBiologicalProgress,
    CropContextConsistency,
)

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


def _build_crop_season_products(
    orch_inputs: Any,
    tensor: FieldTensor,
    *,
    phenology_posterior: Any = None,
):
    """Build archive/acquisition receipts only from a verified crop ledger.

    This helper is intentionally fail-closed. Layer 2 may still publish a
    degraded phenology result when the archive receipt cannot be constructed,
    but it must not silently re-count unbound Layer-1 rows as independent crop
    acquisitions.
    """
    if orch_inputs is None:
        return None, None, "orchestrator_input_unavailable"
    namespace = getattr(orch_inputs, "plot_namespace", None)
    if namespace is None or not getattr(namespace, "is_valid", lambda: False)():
        return None, None, "plot_namespace_unavailable"
    cfg = getattr(orch_inputs, "crop_config", None)
    cfg = cfg if isinstance(cfg, dict) else {}
    ledger_payload = cfg.get("crop_evidence_ledger")
    if not isinstance(ledger_payload, dict):
        return None, None, "crop_evidence_ledger_unavailable"
    try:
        from services.agribrain.scientific_contracts.crop_evidence import CropEvidenceLedgerV2
        from services.agribrain.scientific_contracts.crop_governance import CropModelReceiptV1
        from services.agribrain.scientific_contracts.crop_season_evidence import (
            build_crop_active_acquisition_plan,
            build_crop_season_evidence_receipt,
        )

        ledger = CropEvidenceLedgerV2.from_dict(ledger_payload)
        ledger_namespace = tuple(ledger.plot_namespace.to_tuple())
        input_namespace = tuple(namespace.to_tuple())
        if ledger_namespace != input_namespace:
            raise ValueError("crop evidence ledger namespace mismatch")
        declared_ledger_hash = str(
            cfg.get("crop_evidence_ledger_hash") or ""
        ).strip()
        if declared_ledger_hash != ledger.ledger_hash:
            raise ValueError("crop evidence ledger identity mismatch")

        cycle_context = getattr(orch_inputs, "crop_cycle_context", None)
        if hasattr(cycle_context, "to_dict"):
            cycle_context = cycle_context.to_dict()
        elif not isinstance(cycle_context, dict):
            cycle_context = {}

        date_range = getattr(orch_inputs, "date_range", None)
        date_range = date_range if isinstance(date_range, dict) else {}
        as_of = str(date_range.get("end") or "").strip()
        if not as_of:
            dated_rows = [
                str(row.get("date") or row.get("sensing_time") or "").strip()
                for row in (tensor.plot_timeseries or [])
                if isinstance(row, dict)
                and (row.get("date") or row.get("sensing_time"))
            ]
            as_of = max(dated_rows) if dated_rows else ""
        if not as_of:
            raise ValueError("crop season receipt requires an explicit as-of time")

        crop_posterior = cfg.get("crop_posterior")
        crop_posterior = (
            crop_posterior if isinstance(crop_posterior, dict) else {}
        )
        model_domain_compatible = False
        raw_model_receipt = crop_posterior.get("crop_model_receipt")
        if isinstance(raw_model_receipt, dict):
            model_receipt = CropModelReceiptV1.from_dict(raw_model_receipt)
            model_domain_compatible = bool(model_receipt.production_eligible)

        season_receipt = build_crop_season_evidence_receipt(
            namespace=namespace,
            observations=[item.to_dict() for item in ledger.observations],
            source_evidence_ledger_hash=ledger.ledger_hash,
            weather_records=list(tensor.plot_timeseries or []),
            crop_cycle_context=cycle_context,
            as_of=as_of,
            model_domain_compatible=model_domain_compatible,
        )
        operational = getattr(orch_inputs, "operational_context", None)
        operational = operational if isinstance(operational, dict) else {}
        opportunities = operational.get("crop_acquisition_opportunities")
        opportunities = opportunities if isinstance(opportunities, list) else []
        acquisition_plan = build_crop_active_acquisition_plan(
            receipt=season_receipt,
            crop_posterior=crop_posterior,
            phenology_posterior=phenology_posterior,
            opportunities=opportunities,
            eig_calibration_receipt_id=(
                str(operational.get("crop_eig_calibration_receipt_id") or "").strip()
                or None
            ),
        )
        return season_receipt.to_dict(), acquisition_plan.to_dict(), None
    except Exception as exc:
        logger.warning("[Layer 2] Crop season receipt unavailable: %s", exc)
        return None, None, f"crop_season_receipt_invalid:{type(exc).__name__}"


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
            replay_crop_config = (
                getattr(orch_inputs, "crop_config", {}) or {}
                if orch_inputs is not None else {}
            )
            replay_crop_posterior = replay_crop_config.get("crop_posterior")
            replay_crop_posterior = (
                replay_crop_posterior
                if isinstance(replay_crop_posterior, dict) else {}
            )
            replay_crop_hash = (
                replay_crop_config.get("crop_posterior_hash")
                or replay_crop_posterior.get("content_hash")
            )
            logger.warning(
                f"[Layer 2] FieldTensor has degraded input ({reason}) — "
                "returning degraded output (no curve/phenology data)."
            )
            season_receipt, acquisition_plan, season_receipt_error = (
                _build_crop_season_products(orch_inputs, tensor)
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
                crop_season_evidence_receipt=season_receipt,
                crop_active_acquisition_plan=acquisition_plan,
                provenance={
                    "engine_version": "3.1.0",
                    "execution_time": datetime.now(timezone.utc).isoformat(),
                    "status": "degraded",
                    "reason": reason,
                    "crop_season_receipt_status": (
                        "available" if season_receipt else "unavailable"
                    ),
                    "crop_season_receipt_error": season_receipt_error,
                    "crop_posterior_lineage": replay_crop_hash,
                    "crop_lineage_id": (
                        replay_crop_config.get("crop_lineage_id")
                        or replay_crop_posterior.get("lineage_id")
                    ),
                },
            )

        # ═══════════════════════════════════════════════════════════════
        # 1. Map to Strict Input Schema (v3.1: + ET0, temp_max, temp_min)
        # ═══════════════════════════════════════════════════════════════
        inputs: List[VegIntInput] = []
        for r in tensor.plot_timeseries:
            val_ndvi = r.get("ndvi_mean") if r.get("ndvi_mean") is not None else r.get("ndvi")
            inputs.append(VegIntInput(
                date=r.get("date", ""),
                ndvi_obs=val_ndvi if r.get("is_observed", True) else None,
                ndvi_unc_obs=r.get("uncertainty", 0.1),
                is_observed=r.get("is_observed", True) if val_ndvi is not None else False,
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
                else (r.get("ndvi_mean") if _finite_value(r.get("ndvi_mean")) is not None else r.get("ndvi"))
            )
            for r in tensor.plot_timeseries
        ])
        if len(signal_to_fit) != len(tensor.plot_timeseries):
            raise ValueError(
                "Layer 2 has observed NDVI metadata but no finite NDVI values"
            )
        unc_series = [i.ndvi_unc_obs for i in inputs]

        # Calculate physical delta_days between dates
        delta_days = []
        if dates and len(dates) > 1:
            for idx in range(1, len(dates)):
                try:
                    d1 = datetime.strptime(str(dates[idx])[:10], "%Y-%m-%d")
                    d0 = datetime.strptime(str(dates[idx-1])[:10], "%Y-%m-%d")
                    delta_days.append(max(1.0, float((d1 - d0).days)))
                except Exception:
                    delta_days.append(1.0)

        # Extract cloud QA mask from tensor
        cloud_qa_series = [
            float(r.get("cloud_prob", r.get("cloud_qa", 1.0 if r.get("is_cloudy") else 0.0)) or 0.0)
            for r in tensor.plot_timeseries
        ]

        # Multi-spectral vectors
        evi_series = [i.evi for i in inputs]
        ndwi_series = [i.ndwi for i in inputs]
        ndmi_series = [i.ndmi for i in inputs]
        temperature_series = [i.tmean for i in inputs]
        et0_series = [i.et0 for i in inputs]
        temp_min_series = [i.temp_min for i in inputs]
        rainfall_series = [i.rain for i in inputs]

        # ═══════════════════════════════════════════════════════════════
        # 1b. Resolve Crop Profile (Hierarchical Partial Pooling)
        # ═══════════════════════════════════════════════════════════════
        crop_config = None
        is_perennial = False
        crop_record = None
        crop_ndvi_sig = None
        crop_raw = ""
        latitude = None
        latitude_source = "missing"
        cfg: Dict[str, Any] = {}
        cycle_context: Dict[str, Any] = {}
        season_initial_gdd = 0.0
        operational = {}

        if orch_inputs is not None:
            cfg = getattr(orch_inputs, 'crop_config', None)
            cfg = cfg if isinstance(cfg, dict) else {}
            raw_cycle_context = getattr(orch_inputs, "crop_cycle_context", None)
            if raw_cycle_context is not None:
                if hasattr(raw_cycle_context, "to_dict"):
                    cycle_context = raw_cycle_context.to_dict()
                elif isinstance(raw_cycle_context, dict):
                    cycle_context = dict(raw_cycle_context)
            operational = getattr(orch_inputs, 'operational_context', None)
            operational = operational if isinstance(operational, dict) else {}

            if isinstance(cfg, dict):
                crop_raw = str(cfg.get('crop', cfg.get('crop_type', ''))).lower()
                crop_config = _resolve_crop_phenology_config(crop_raw)
                arch = get_architecture_class(crop_raw)
                is_perennial = arch in _PERENNIAL_ARCHS

                crop_record = _resolve_crop_record(crop_raw)
                crop_ndvi_sig = _resolve_ndvi_signature(crop_raw)

                raw_initial_gdd = (
                    cycle_context.get("initial_gdd")
                    if cycle_context.get("initial_gdd") is not None
                    else cfg.get("initial_gdd")
                )
                try:
                    candidate_initial_gdd = float(raw_initial_gdd or 0.0)
                    if math.isfinite(candidate_initial_gdd):
                        season_initial_gdd = max(0.0, candidate_initial_gdd)
                except (TypeError, ValueError):
                    season_initial_gdd = 0.0

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

        # Resolve rich CropResponseProfile
        crop_profile = CropParameterResolver.resolve(
            crop_name=crop_raw,
            cultivar=getattr(orch_inputs, 'cultivar', None),
            operational_context=operational,
        )

        # ═══════════════════════════════════════════════════════════════
        # 2. Growth Curve Modeling (v3.2: Ensemble Smoother with QA & Time)
        # ═══════════════════════════════════════════════════════════════
        modeled_ndvi, derivatives, fit_unc = self.growth_engine.fit_growth_curve(
            dates=dates,
            ndvi_values=signal_to_fit,
            uncertainties=unc_series,
            cloud_qa=cloud_qa_series,
            delta_days=delta_days,
        )

        # v3.2: Attempt ensemble blend (Whittaker + SG) with QA and delta_days
        try:
            ens_curve, ens_deriv, ens_unc = self.growth_engine._fit_ensemble(
                ndvi_values=signal_to_fit,
                uncertainties=unc_series,
                dates=dates,
                cloud_qa=cloud_qa_series,
                delta_days=delta_days,
            )
            if ens_curve and len(ens_curve) == len(modeled_ndvi):
                modeled_ndvi = ens_curve
                fit_unc = ens_unc
                if isinstance(ens_deriv, dict):
                    derivatives = ens_deriv
                elif isinstance(ens_deriv, (tuple, list)) and len(ens_deriv) >= 2:
                    derivatives = {
                        "velocity": list(ens_deriv[0]),
                        "acceleration": list(ens_deriv[1]),
                    }
        except Exception:
            pass  # Fall back to Whittaker-only

        # Enforce length consistency
        from .growth_engine import _align_length
        target_len = len(modeled_ndvi)
        fit_unc = _align_length(fit_unc, target_len)
        if "velocity" in derivatives:
            derivatives["velocity"] = _align_length(derivatives["velocity"], target_len, fill_value=0.0)
        if "acceleration" in derivatives:
            derivatives["acceleration"] = _align_length(derivatives.get("acceleration", []), target_len, fill_value=0.0)

        integrals = self.growth_engine.compute_integrals(modeled_ndvi, delta_days=delta_days)

        # Double logistic fitting with physical dates
        dbl_logistic = self.growth_engine.fit_double_logistic(modeled_ndvi, dates=dates)

        # SOS/EOS/LOS from curve
        season_dates = GrowthCurveEngine.extract_season_dates(modeled_ndvi, dates)

        # ═══════════════════════════════════════════════════════════════
        # 3. Biophysical Products (LAI, fPAR, FVC, NPP, SCWA) with crop priors
        # ═══════════════════════════════════════════════════════════════
        lai_series = GrowthCurveEngine.estimate_lai(
            modeled_ndvi,
            k=crop_profile.k_extinction.mean,
            lai_max=crop_profile.lai_max_expected.mean,
        )
        cwsi_series = GrowthCurveEngine.compute_spectral_canopy_water_anomaly(ndwi_series, modeled_ndvi)
        fpar_series = GrowthCurveEngine.compute_fpar(modeled_ndvi)
        fvc_series = GrowthCurveEngine.compute_fvc(
            modeled_ndvi,
            ndvi_soil=crop_profile.fvc_soil_baseline.mean,
            ndvi_veg=crop_profile.fvc_veg_asymptote.mean,
        )

        # NPP: CASA model using pathway-aware LUE and photosynthetic temperature parameters
        start_doy = 1
        if dates and dates[0]:
            try:
                from datetime import date as dt_date
                parts = dates[0].split("-")
                d = dt_date(int(parts[0]), int(parts[1]), int(parts[2]))
                start_doy = d.timetuple().tm_yday
            except Exception:
                pass

        casa_t_opt = crop_profile.t_opt_photo.mean
        casa_t_min = crop_profile.t_min_photo.mean
        casa_t_max = crop_profile.t_max_photo.mean
        casa_lue = crop_profile.lue_max.mean

        npp_detailed = (
            GrowthCurveEngine.compute_npp_casa_detailed(
                fpar_series=fpar_series,
                latitude=latitude,
                start_doy=start_doy,
                temperature_series=temperature_series,
                cwsi_series=cwsi_series,
                t_opt=casa_t_opt,
                t_min=casa_t_min,
                t_max=casa_t_max,
                epsilon_max=casa_lue,
                rs_observed_series=getattr(tensor, "rs_observed_series", None),
            )
            if latitude is not None else {}
        )
        npp_series = npp_detailed.get("npp_spectral_water_adjusted", [])

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
        # 4. Phenology Inference (Viterbi HMM with causal vernalization)
        # ═══════════════════════════════════════════════════════════════

        temp_max_series = [i.temp_max for i in inputs]
        is_short_day = crop_profile.is_short_day
        t_base_gdd = crop_profile.t_base.mean
        t_opt_max_gdd = crop_profile.t_opt_pheno.mean

        photoperiod_engine = PhenologyEngine(
            crop_config,
            is_perennial=crop_profile.is_perennial,
            crop_ndvi_signature=crop_ndvi_sig,
            latitude=latitude,
            requires_vernalization=crop_profile.requires_vernalization,
            stage_graph=crop_profile.stage_graph,
        )
        # Causal daily vernalization progress V_t = f(T_{1:t})
        # (For non-vernalizing crops, f_V(t) = 1.0 unconditionally)
        arch_class = crop_profile.architecture
        vern_daily_series = []
        cu_acc = 0
        req_cu = max(1, int(crop_profile.v_required.mean)) if crop_profile.requires_vernalization else 0
        if not crop_profile.requires_vernalization:
            vern_daily_series = [1.0] * len(inputs)
        else:
            for tm in temp_min_series:
                if tm is not None and crop_profile.v_base < tm < crop_profile.v_max:
                    cu_acc += 1
                vern_daily_series.append(min(1.0, cu_acc / max(1, req_cu)))

        vern_results = {
            "chill_units_accumulated": cu_acc,
            "chill_units_required": req_cu,
            "vernalization_progress": 1.0 if not crop_profile.requires_vernalization else (vern_daily_series[-1] if vern_daily_series else 1.0),
            "vernalization_complete": True if not crop_profile.requires_vernalization else ((vern_daily_series[-1] >= 0.8) if vern_daily_series else True),
            "obligate_vernalization": crop_profile.requires_vernalization,
        }

        # Unified Causal Biological Progress Coordinate D_t and τ_t ∈ [0, 1]
        tau_series = CausalBiologicalProgress.compute_daily_progress(
            t_mean_series=temperature_series,
            dates=dates,
            profile=crop_profile,
            t_max_series=temp_max_series,
            delta_days=delta_days,
            vernalization_series=vern_daily_series,
            initial_gdd=season_initial_gdd,
            day_length_fn=photoperiod_engine._compute_photoperiod,
        )
        d_cycle_total = max(100.0, crop_profile.gdd_total_cycle.mean)
        cumulative_gdd = [round(tau * d_cycle_total, 2) for tau in tau_series]

        # Normalized Crop-Context Consistency Check
        consistency_report = CropContextConsistency.evaluate_consistency(
            observed_ndvi=[i.ndvi_obs for i in inputs],
            tau_series=tau_series,
            profile=crop_profile,
        )

        pheno_engine = photoperiod_engine
        stages, stage_confs = pheno_engine.infer_daily_stages(
            modeled_ndvi, derivatives["velocity"], dates, cumulative_gdd,
            uncertainty=fit_unc, ndwi_series=ndwi_series,
            initial_gdd=season_initial_gdd,
            vernalization_series=vern_daily_series,
        )
        transitions = pheno_engine.extract_transitions(dates, stages)
        sub_stages = pheno_engine.decode_sub_stages(
            stages, cumulative_gdd, total_gdd=crop_profile.gdd_total_cycle.mean,
        )

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
        # P0-2 FIX: Pass zone geometry down to analyze_stability
        zone_centroids = getattr(tensor, "zone_centroids", None) or (
            getattr(orch_inputs, "operational_context", {}) or {}
        ).get("zone_centroids")
        zone_adjacency = getattr(tensor, "zone_adjacency", None) or (
            getattr(orch_inputs, "operational_context", {}) or {}
        ).get("zone_adjacency")

        n_obs_season = sum(1 for i in inputs if i.is_observed)
        spatial_metrics = self.spatial_engine.analyze_stability(
            dates, spatial_std_series, zone_means=zone_means_for_moran,
            phase_variability=phase_var,
            n_season_observations=n_obs_season,
            zone_centroids=zone_centroids,
            zone_adjacency=zone_adjacency,
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
            npp_light_temperature_series=npp_detailed.get("npp_light_temperature", []) if npp_detailed else [],
            npp_spectral_water_adjusted_series=npp_detailed.get("npp_spectral_water_adjusted", []) if npp_detailed else [],
            water_constraint_source=npp_detailed.get("water_constraint_source", "NONE") if npp_detailed else "NONE",
            water_constraint_applied=npp_detailed.get("water_constraint_applied", False) if npp_detailed else False,
            quality=CurveQuality(
                rmse=float(rmse),
                outlier_frac=float(outlier_frac),
                obs_coverage=sum(1 for i in inputs if i.is_observed) / len(inputs),
            ),
        )

        # Publish one Layer-2-owned phenology receipt.  The Viterbi path is a
        # diagnostic candidate until the season clock is anchored; downstream
        # layers are forbidden from reconstructing a stage from NDVI/status.
        plant_date = (
            cycle_context.get("plant_date")
            or cycle_context.get("planting_date")
            or cfg.get("plant_date")
            or cfg.get("planting_date")
        )
        plant_date_status = str(
            cycle_context.get("plant_date_status")
            or cfg.get("plant_date_status")
            or ("unknown" if not plant_date else "estimated")
        ).lower()
        plant_date_min = cycle_context.get("plant_date_min") or cfg.get("plant_date_min")
        plant_date_max = cycle_context.get("plant_date_max") or cfg.get("plant_date_max")
        if plant_date and not plant_date_min:
            plant_date_min = str(plant_date)
        if plant_date and not plant_date_max:
            plant_date_max = str(plant_date)

        def _date_only(value):
            if value is None:
                return None
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
            except (TypeError, ValueError):
                try:
                    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
                except (TypeError, ValueError):
                    return None

        first_observation_date = _date_only(dates[0]) if dates else None
        parsed_plant_date = _date_only(plant_date)
        if is_perennial:
            season_anchor_status = "perennial_cycle_diagnostic"
            season_anchor_sufficient = bool(dates)
        elif parsed_plant_date is None or plant_date_status == "unknown":
            season_anchor_status = "plant_date_unknown"
            season_anchor_sufficient = False
        elif first_observation_date is not None and first_observation_date <= parsed_plant_date:
            season_anchor_status = "weather_window_covers_plant_date"
            season_anchor_sufficient = True
        elif season_initial_gdd > 0.0:
            season_anchor_status = "season_gdd_carried"
            season_anchor_sufficient = True
        else:
            season_anchor_status = "archive_weather_required"
            season_anchor_sufficient = False

        canonical_phenology = None
        namespace = getattr(orch_inputs, "plot_namespace", None) if orch_inputs is not None else None
        if namespace is not None and getattr(namespace, "is_valid", lambda: False)():
            from services.agribrain.scientific_contracts.crop_phenology import CanonicalPhenologyPosteriorV2

            candidate_stage = stages[-1].value if stages else "UNKNOWN"
            candidate_confidence = (
                max(0.0, min(1.0, float(stage_confs[-1])))
                if stage_confs else 0.0
            )
            physical_keys = set()
            evidence_ids = []
            for record in tensor.plot_timeseries or []:
                if not isinstance(record, dict):
                    continue
                key = record.get("physical_acquisition_key")
                if key:
                    physical_keys.add(str(key))
                obs_id = record.get("observation_id") or record.get("scene_id")
                if obs_id:
                    evidence_ids.append(str(obs_id))

            # Confidence has no artificial floor.  The Viterbi margin is
            # reduced by direct, independent season evidence coverage.
            evidence_strength = min(1.0, len(physical_keys) / 6.0)
            published_confidence = candidate_confidence * evidence_strength
            if (
                season_anchor_sufficient
                and candidate_stage != "UNKNOWN"
                and published_confidence > 0.0
            ):
                current_stage = candidate_stage
                posterior = (
                    (candidate_stage, published_confidence),
                    ("UNKNOWN", 1.0 - published_confidence),
                )
                authority = "diagnostic"
                degradation_reasons = ("phenology_model_uncalibrated",)
            else:
                current_stage = "UNKNOWN"
                posterior = (("UNKNOWN", 1.0),)
                authority = "unavailable"
                degradation_reasons = tuple(dict.fromkeys((
                    season_anchor_status,
                    "insufficient_independent_phenology_evidence"
                    if not physical_keys else "",
                )))
                degradation_reasons = tuple(
                    reason for reason in degradation_reasons if reason
                )

            planting_summary = {
                "status": plant_date_status,
                "lower": str(plant_date_min) if plant_date_min else None,
                "upper": str(plant_date_max) if plant_date_max else None,
                "unit": "date",
            }
            biological_gdd_value = (
                season_initial_gdd + (cumulative_gdd[-1] if cumulative_gdd else 0.0)
                if season_anchor_sufficient else None
            )
            harvest_gdd = (
                (crop_config or {}).get("transitions", {}).get("harvest_min_gdd", 1800)
                if isinstance(crop_config, dict) else 1800
            )
            season_progress_value = (
                min(1.0, biological_gdd_value / max(1.0, float(harvest_gdd)))
                if biological_gdd_value is not None else None
            )
            transition_posteriors = {
                stage: {
                    "status": "diagnostic_point",
                    "lower": date,
                    "upper": date,
                    "unit": "date",
                }
                for stage, date in transitions.items()
            }

            import hashlib
            import json
            weather_forcing_hash = hashlib.sha256(json.dumps({
                "dates": dates,
                "tmean": [_finite_value(value) for value in temperature_series],
                "temp_min": [_finite_value(value) for value in temp_min_series],
                "temp_max": [_finite_value(value) for value in temp_max_series],
                "rain": [_finite_value(value) for value in rainfall_series],
            }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()

            canonical_phenology = CanonicalPhenologyPosteriorV2(
                namespace=namespace,
                crop_cycle_id=(
                    cycle_context.get("crop_cycle_id")
                    or cfg.get("crop_cycle_id")
                    or cfg.get("crop_season_id")
                ),
                effective_at=str(dates[-1]) if dates else datetime.now(timezone.utc).isoformat(),
                current_stage=current_stage,
                candidate_stage=candidate_stage,
                stage_posterior=posterior,
                authority=authority,
                stage_authority=authority,
                stage_confidence=(
                    published_confidence if current_stage != "UNKNOWN" else 0.0
                ),
                calibration_status="uncalibrated_hmm_viterbi",
                season_anchor_status=season_anchor_status,
                planting_date_posterior=planting_summary,
                biological_age_gdd={
                    "status": "available" if biological_gdd_value is not None else "unknown",
                    "mean": biological_gdd_value,
                    "unit": "degree_day_c",
                },
                season_progress={
                    "status": "available" if season_progress_value is not None else "unknown",
                    "mean": season_progress_value,
                    "unit": "fraction",
                },
                transition_date_posteriors=transition_posteriors,
                stage_duration_consistency=0.0,
                crop_identity_posterior_hash=str(
                    cfg.get("crop_posterior_hash") or ""
                ),
                evidence_ledger_hash=str(
                    cfg.get("crop_evidence_ledger_hash") or ""
                ),
                weather_forcing_hash=weather_forcing_hash,
                previous_phenology_event_id=(
                    cycle_context.get("previous_phenology_event_id")
                    or cfg.get("previous_phenology_event_id")
                ),
                plant_date_status=plant_date_status,
                plant_date_min=str(plant_date_min) if plant_date_min else None,
                plant_date_max=str(plant_date_max) if plant_date_max else None,
                independent_evidence_count=len(physical_keys),
                evidence_observation_ids=tuple(sorted(set(evidence_ids))),
                degradation_reasons=degradation_reasons,
            ).to_dict()

        pheno_out = PhenologyOutput(
            stage_by_day=[s.value for s in stages],
            confidence_by_day=stage_confs,
            sub_stages_by_day=sub_stages,
            key_dates=transitions,
            canonical_posterior=canonical_phenology,
        )
        season_receipt, acquisition_plan, season_receipt_error = (
            _build_crop_season_products(
                orch_inputs,
                tensor,
                phenology_posterior=canonical_phenology,
            )
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
                    initial_gdd=season_initial_gdd,
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
            crop_season_evidence_receipt=season_receipt,
            crop_active_acquisition_plan=acquisition_plan,
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
                "phenology_posterior_hash": (
                    canonical_phenology.get("content_hash")
                    if isinstance(canonical_phenology, dict) else None
                ),
                "phenology_owner": "layer2",
                "season_anchor_status": season_anchor_status,
                "season_initial_gdd": season_initial_gdd,
                "crop_season_evidence_receipt_hash": (
                    season_receipt.get("content_hash")
                    if isinstance(season_receipt, dict) else None
                ),
                "crop_active_acquisition_plan_hash": (
                    acquisition_plan.get("content_hash")
                    if isinstance(acquisition_plan, dict) else None
                ),
                "crop_season_receipt_status": (
                    "available" if season_receipt else "unavailable"
                ),
                "crop_season_receipt_error": season_receipt_error,
                "crop_context_consistency": consistency_report,
                "crop_response_profile": {
                    "crop_name": crop_profile.crop_code,
                    "cultivar": crop_profile.cultivar,
                    "architecture": crop_profile.architecture,
                    "photosynthetic_pathway": crop_profile.photosynthetic_pathway,
                    "profile_version": crop_profile.profile_version,
                },
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
        recent_cwsi = [c for c in (cwsi_series[-10:] if cwsi_series else []) if c is not None]
        mean_cwsi = statistics.mean(recent_cwsi) if recent_cwsi else None

        # Integrate ET deficit if available
        et_deficit_score = None
        mean_et_deficit = 0.0
        mean_et_actual = 0.0
        if et_deficit_series:
            recent_deficit = [d for d in et_deficit_series[-10:] if d is not None]
            if recent_deficit:
                mean_et_deficit = statistics.mean(recent_deficit)
                et_deficit_score = min(1.0, mean_et_deficit / 5.0)

        if et_actual_series:
            recent_actual = [a for a in et_actual_series[-10:] if a is not None]
            mean_et_actual = statistics.mean(recent_actual) if recent_actual else 0.0

        if mean_cwsi is not None and et_deficit_score is not None:
            water_stress = 0.5 * mean_cwsi + 0.5 * et_deficit_score
        elif mean_cwsi is not None:
            water_stress = mean_cwsi
        elif et_deficit_score is not None:
            water_stress = et_deficit_score
        else:
            water_stress = None

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

        # 5. Composite score with dynamic weight renormalization
        vigor_score = 0.5 + min(0.5, max(-0.5, vigor_slope * 50))  # Map slope to [0, 1]

        components = []
        if ndvi_health is not None:
            components.append(("ndvi_health", 0.25, ndvi_health))
        if water_stress is not None:
            components.append(("water_stress", 0.25, 1.0 - water_stress))
        if vigor_score is not None:
            components.append(("vigor_score", 0.25, vigor_score))
        if anomaly_penalty is not None:
            components.append(("anomaly_penalty", 0.25, 1.0 - anomaly_penalty))

        total_weight = sum(w for _, w, _ in components)
        if total_weight > 0:
            overall = sum(w * score for _, w, score in components) / total_weight
        else:
            overall = 0.5
        overall = max(0.0, min(1.0, overall))

        health_coverage = round(total_weight, 2)
        component_mask = {
            "ndvi_state": "OBSERVED" if ndvi_health is not None else "UNKNOWN",
            "water_state": "OBSERVED" if water_stress is not None else "UNKNOWN",
            "vigor_state": "OBSERVED" if vigor_score is not None else "UNKNOWN",
            "anomaly_state": "OBSERVED" if anomaly_penalty is not None else "UNKNOWN",
        }

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
            water_stress_index=round(water_stress, 3) if water_stress is not None else None,
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
            health_component_coverage=health_coverage,
            component_state_mask=component_mask,
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
