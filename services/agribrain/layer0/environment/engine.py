"""
Environmental Context Engine V1.

Top-level orchestrator. Pipeline:
  1. Validate provenance (coordinates, providers)
  2. Build SoilGrids profile → QA → derived hydraulics
  3. Build FAO context → QA → fallback mapping
  4. Normalize weather providers → consensus → derived features
  5. Fuse soil + weather → ProcessParameters + ProcessForcing
  6. Build packets
  7. Build weak Kalman observations
  8. Build diagnostics + provenance
  9. Return EnvironmentalContextPackage
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.schemas import (
    EnvironmentalContextPackage,
    EnvironmentalQA,
    EnvironmentalQualityClass,
    ProcessForcing,
)
from layer0.environment.soilgrids.normalizer import normalize_soilgrids_response
from layer0.environment.soilgrids.qa import evaluate_soilgrids_qa
from layer0.environment.soilgrids.profile_builder import build_derived_hydraulics
from layer0.environment.soilgrids.schemas import SoilGridsProfile, SoilGridsQAResult
from layer0.environment.fao.normalizer import normalize_fao_response
from layer0.environment.fao.qa import evaluate_fao_qa
from layer0.environment.fao.fallback_mapper import map_fao_risk_flags
from layer0.environment.fao.schemas import FAOSoilContext, FAOQAResult
from layer0.environment.weather.normalizer import build_weather_timeseries
from layer0.environment.weather.schemas import WeatherDailyRecord, WeatherConsensusDaily
from layer0.environment.weather.consensus import build_daily_consensus
from layer0.environment.weather.derived import (
    compute_daily_forcing,
    compute_multi_day_features,
)
from layer0.environment.weather.qa import evaluate_weather_qa
from layer0.environment.fusion import build_process_parameters
from layer0.environment.packetizer import emit_environment_packets
from layer0.environment.state_adapter import create_weak_kalman_observations
from layer0.environment.provenance import build_provenance, EnvironmentalProvenanceError
from layer0.environment.diagnostics import build_diagnostics


class EnvironmentalEngine:
    """Environmental Context Engine V1."""

    def process(
        self,
        latitude: float,
        longitude: float,
        plot_id: str = "",
        soilgrids_data: Optional[Dict[str, Any]] = None,
        fao_data: Optional[Dict[str, Any]] = None,
        open_meteo_data: Optional[Dict[str, Any]] = None,
        openweather_data: Optional[Dict[str, Any]] = None,
        # V1.1 Forecast inputs
        open_meteo_forecast_data: Optional[Dict[str, Any]] = None,
        openweather_forecast_data: Optional[Dict[str, Any]] = None,
        chirps_data: Optional[Dict[str, Any]] = None,
        nasa_power_data: Optional[Dict[str, Any]] = None,
        era5_data: Optional[Dict[str, Any]] = None,
        timezone: str = "UTC",
        t_base: float = 5.0,
        forecast_retrieval_time: Optional[str] = None,
    ) -> EnvironmentalContextPackage:
        """Process all environmental data sources into a context package.

        All data inputs are pre-fetched/mocked dicts. No live API calls.
        Partial provider failure: continues with available data.
        All providers fail: returns provenance + diagnostics only.

        V1.1: adds forecast pipeline after V1 historical pipeline.
        """
        # 1. Provenance (fatal if coordinates missing)
        provenance = build_provenance(
            latitude=latitude,
            longitude=longitude,
            weather_providers=self._list_providers(open_meteo_data, openweather_data),
            timezone=timezone,
        )

        # 2. SoilGrids
        soilgrids_profile = None
        soilgrids_qa = None
        derived_hydraulics = None

        if soilgrids_data:
            try:
                soilgrids_profile = normalize_soilgrids_response(
                    soilgrids_data, latitude, longitude
                )
                soilgrids_qa = evaluate_soilgrids_qa(soilgrids_profile)
                derived_hydraulics = build_derived_hydraulics(soilgrids_profile)
            except Exception:
                soilgrids_profile = None
                soilgrids_qa = None

        # 3. FAO
        fao_context = None
        fao_qa = None
        fao_risk_flags = {}

        if fao_data:
            try:
                fao_context = normalize_fao_response(fao_data)
                fao_qa = evaluate_fao_qa(fao_context)
                fao_risk_flags = map_fao_risk_flags(fao_context)
            except Exception:
                fao_context = None
                fao_qa = None

        # 4. Weather
        all_weather_records: List[WeatherDailyRecord] = []
        open_meteo_records: List[WeatherDailyRecord] = []

        if open_meteo_data:
            from layer0.environment.weather.open_meteo import normalize_open_meteo_daily
            try:
                om_records = normalize_open_meteo_daily(open_meteo_data)
                all_weather_records.extend(om_records)
                open_meteo_records = om_records
            except Exception:
                pass

        if openweather_data:
            from layer0.environment.weather.openweather import normalize_openweather_daily
            try:
                ow_records = normalize_openweather_daily(openweather_data)
                all_weather_records.extend(ow_records)
            except Exception:
                pass

        weather_timeseries = build_weather_timeseries(all_weather_records, timezone)
        weather_qa_result = evaluate_weather_qa(weather_timeseries)

        # 5. Weather consensus (per-day, per-variable)
        weather_consensus: List[WeatherConsensusDaily] = []
        if all_weather_records:
            weather_consensus = self._build_consensus(all_weather_records)

        # 6. Process forcing
        process_forcing: List[ProcessForcing] = []
        for daily_consensus in weather_consensus:
            forcing = compute_daily_forcing(
                daily_consensus, latitude_deg=latitude, t_base=t_base
            )
            process_forcing.append(forcing)

        derived_features = compute_multi_day_features(process_forcing)

        # 7. Process parameters (from soil)
        process_parameters = build_process_parameters(
            soilgrids_profile, soilgrids_qa, derived_hydraulics, fao_context
        )

        # 8. Weak Kalman observations
        weather_failed = len(all_weather_records) == 0
        weak_obs = create_weak_kalman_observations(
            open_meteo_records, weather_provider_failed=weather_failed
        )

        # 9. Packets (V1)
        packets = emit_environment_packets(
            soilgrids_profile=soilgrids_profile,
            soilgrids_qa=soilgrids_qa,
            derived_hydraulics=derived_hydraulics,
            fao_context=fao_context,
            fao_qa=fao_qa,
            weather_timeseries=weather_timeseries,
            weather_consensus=weather_consensus,
            process_forcing=process_forcing,
            process_parameters=process_parameters,
            derived_features=derived_features,
            provenance=provenance,
        )

        # 10. QA
        qa = self._build_qa(soilgrids_qa, fao_qa, weather_qa_result)

        # 11. Diagnostics (V1)
        diagnostics = build_diagnostics(
            soilgrids_qa=soilgrids_qa,
            fao_qa=fao_qa,
            weather_qa=weather_qa_result,
            weather_consensus=weather_consensus,
            process_forcing=process_forcing,
            weak_observations=weak_obs,
        )

        # =============================================================
        # V1.1: Forecast Pipeline (steps 12-21)
        # =============================================================
        forecast_ts = None
        forecast_consensus_list = []
        forecast_derived_summary = None
        risk_windows_list = []
        forecast_forcing_list = []
        forecast_diag = {}
        wind_features_by_day = {}

        try:
            forecast_result = self._process_forecast(
                open_meteo_forecast_data=open_meteo_forecast_data,
                openweather_forecast_data=openweather_forecast_data,
                chirps_data=chirps_data,
                nasa_power_data=nasa_power_data,
                era5_data=era5_data,
                timezone=timezone,
                retrieval_time=forecast_retrieval_time,
                latitude=latitude,
            )
            forecast_ts = forecast_result.get("forecast_timeseries")
            forecast_consensus_list = forecast_result.get("forecast_consensus", [])
            forecast_derived_summary = forecast_result.get("forecast_derived")
            risk_windows_list = forecast_result.get("risk_windows", [])
            forecast_forcing_list = forecast_result.get("forecast_forcing", [])
            forecast_diag = forecast_result.get("forecast_diagnostics", {})
            wind_features_by_day = forecast_result.get("wind_features_by_day", {})

            # Add forecast packets
            forecast_pkts = forecast_result.get("forecast_packets", [])
            packets.extend(forecast_pkts)
        except Exception:
            # Revision 9: no forecast data degrades, not crashes
            forecast_diag = {"flags": ["FORECAST_ENGINE_ERROR"], "forecast_not_used_for_kalman": True}

        # Build window metadata
        timestamp_window = {
            "window_start": weather_timeseries.window_start,
            "window_end": weather_timeseries.window_end,
            "historical_days": str(weather_timeseries.historical_days),
            "forecast_days": str(weather_timeseries.forecast_days),
            "timezone": timezone,
        }

        return EnvironmentalContextPackage(
            plot_id=plot_id,
            timestamp_window=timestamp_window,
            soilgrids_profile=soilgrids_profile,
            fao_context=fao_context,
            weather_timeseries=weather_timeseries,
            weather_consensus=weather_consensus,
            derived_features=derived_features,
            process_forcing=process_forcing,
            process_parameters=process_parameters,
            forecast_timeseries=forecast_ts,
            forecast_consensus=forecast_consensus_list,
            forecast_derived=forecast_derived_summary,
            risk_windows=risk_windows_list,
            forecast_process_forcing=forecast_forcing_list,
            forecast_diagnostics=forecast_diag,
            qa=qa,
            packets=packets,
            weak_kalman_observations=weak_obs,
            diagnostics=diagnostics,
            provenance=provenance,
        )

    def _list_providers(
        self,
        open_meteo: Optional[Dict],
        openweather: Optional[Dict],
    ) -> List[str]:
        providers = []
        if open_meteo:
            providers.append("open_meteo")
        if openweather:
            providers.append("openweather")
        return providers

    def _build_consensus(
        self,
        records: List[WeatherDailyRecord],
    ) -> List[WeatherConsensusDaily]:
        """Group records by date, separate forecast from historical, build consensus."""
        from collections import defaultdict

        # Group by date
        by_date: Dict[str, Dict[str, WeatherDailyRecord]] = defaultdict(dict)
        for rec in records:
            if rec.date and rec.data_kind != "forecast":
                by_date[rec.date][rec.provider] = rec

        consensus_list: List[WeatherConsensusDaily] = []
        for date in sorted(by_date.keys()):
            providers = by_date[date]
            daily = build_daily_consensus(providers, date)
            consensus_list.append(daily)

        return consensus_list

    def _process_forecast(
        self,
        open_meteo_forecast_data: Optional[Dict[str, Any]] = None,
        openweather_forecast_data: Optional[Dict[str, Any]] = None,
        chirps_data: Optional[Dict[str, Any]] = None,
        nasa_power_data: Optional[Dict[str, Any]] = None,
        era5_data: Optional[Dict[str, Any]] = None,
        timezone: str = "UTC",
        retrieval_time: Optional[str] = None,
        latitude: float = 0.0,
    ) -> Dict[str, Any]:
        """V1.1 Forecast Pipeline.

        Steps 12-21: normalize → validate → consensus → confidence →
        wind → derived → risk windows → forcing → packets → diagnostics.
        """
        from layer0.environment.weather.forecast_normalizer import (
            build_forecast_timeseries,
            validate_forecast_horizon,
            validate_forecast_hourly_horizon,
        )
        from layer0.environment.weather.forecast_consensus import build_forecast_consensus
        from layer0.environment.weather.forecast_derived import (
            compute_forecast_7day_summary,
            compute_forecast_daily_ag_summaries,
        )
        from layer0.environment.weather.wind import compute_daily_wind_features
        from layer0.environment.weather.risk_windows import detect_risk_windows
        from layer0.environment.weather.forecast_packets import emit_forecast_packets
        from layer0.environment.weather.forecast_diagnostics import build_forecast_diagnostics
        from layer0.environment.state_adapter import create_forecast_process_forcing
        from layer0.environment.weather.forecast_schemas import ForecastRiskConfig
        from collections import defaultdict

        # 12. Normalize forecast providers
        all_hourly = []
        all_daily = []

        if open_meteo_forecast_data:
            from layer0.environment.weather.open_meteo import (
                normalize_open_meteo_forecast_hourly,
                normalize_open_meteo_forecast_daily,
            )
            try:
                hourly = normalize_open_meteo_forecast_hourly(
                    open_meteo_forecast_data, timezone=timezone,
                    retrieval_time=retrieval_time,
                )
                all_hourly.extend(hourly)
            except Exception:
                pass
            try:
                daily = normalize_open_meteo_forecast_daily(
                    open_meteo_forecast_data, timezone=timezone,
                    retrieval_time=retrieval_time,
                )
                all_daily.extend(daily)
            except Exception:
                pass

        if openweather_forecast_data:
            from layer0.environment.weather.openweather import (
                normalize_openweather_forecast_daily,
                normalize_openweather_forecast_hourly,
            )
            try:
                ow_daily = normalize_openweather_forecast_daily(
                    openweather_forecast_data, timezone=timezone,
                    retrieval_time=retrieval_time,
                )
                all_daily.extend(ow_daily)
            except Exception:
                pass
            try:
                ow_hourly = normalize_openweather_forecast_hourly(
                    openweather_forecast_data, timezone=timezone,
                    retrieval_time=retrieval_time,
                )
                all_hourly.extend(ow_hourly)
            except Exception:
                pass

        # No forecast data → return minimal result (Revision 9)
        if not all_daily and not all_hourly:
            empty_diag = build_forecast_diagnostics()
            empty_packets = emit_forecast_packets()
            return {
                "forecast_timeseries": None,
                "forecast_consensus": [],
                "forecast_derived": None,
                "risk_windows": [],
                "forecast_forcing": [],
                "forecast_diagnostics": empty_diag,
                "wind_features_by_day": {},
                "forecast_packets": empty_packets,
            }

        # 13. Build forecast timeseries + validate horizon
        forecast_ts = build_forecast_timeseries(
            hourly_records=all_hourly,
            daily_records=all_daily,
            timezone_str=timezone,
            retrieval_time=retrieval_time,
        )

        daily_valid, daily_warnings = validate_forecast_horizon(all_daily)
        hourly_valid, hourly_warnings = validate_forecast_hourly_horizon(all_hourly)

        if not daily_valid or not hourly_valid:
            all_warnings = daily_warnings + hourly_warnings
            raise ValueError(f"Forecast validation failed: {'; '.join(all_warnings)}")

        # 14. Build per-day forecast consensus
        forecast_consensus = build_forecast_consensus(all_daily)

        # 15. Compute wind features per day from hourly data
        wind_features_by_day: Dict[str, Dict] = {}
        config = ForecastRiskConfig()

        hourly_by_date = defaultdict(list)
        for hr in all_hourly:
            if hr.date:
                hourly_by_date[hr.date].append(hr)

        for date, hours in hourly_by_date.items():
            wind_features_by_day[date] = compute_daily_wind_features(hours, config)

        # 16. Compute forecast derived features
        forecast_derived = compute_forecast_7day_summary(
            forecast_consensus, wind_features_by_day, config
        )

        # 17. Compute daily ag summaries
        daily_ag = compute_forecast_daily_ag_summaries(
            forecast_consensus, wind_features_by_day, config
        )

        # 18. Detect risk windows
        risk_windows = detect_risk_windows(
            daily_ag, forecast_consensus, wind_features_by_day, config
        )

        # 19. Build forecast process forcing
        forecast_forcing = create_forecast_process_forcing(forecast_consensus)

        # 20. Build forecast diagnostics
        forecast_diag = build_forecast_diagnostics(
            forecast_timeseries=forecast_ts,
            forecast_consensus=forecast_consensus,
            risk_windows=risk_windows,
            kalman_observations_created=0,  # HARD RULE
        )

        # 21. Emit forecast packets
        forecast_packets = emit_forecast_packets(
            forecast_timeseries=forecast_ts,
            forecast_consensus=forecast_consensus,
            forecast_derived=forecast_derived,
            risk_windows=risk_windows,
            forecast_forcing=forecast_forcing,
            wind_features_by_day=wind_features_by_day,
            forecast_diagnostics=forecast_diag,
            chirps_data=chirps_data,
            era5_data=era5_data,
            nasa_power_data=nasa_power_data,
        )

        return {
            "forecast_timeseries": forecast_ts,
            "forecast_consensus": forecast_consensus,
            "forecast_derived": forecast_derived,
            "risk_windows": risk_windows,
            "forecast_forcing": forecast_forcing,
            "forecast_diagnostics": forecast_diag,
            "wind_features_by_day": wind_features_by_day,
            "forecast_packets": forecast_packets,
        }

    def _build_qa(
        self,
        soilgrids_qa: Optional[SoilGridsQAResult],
        fao_qa: Optional[FAOQAResult],
        weather_qa: Optional[Dict[str, Any]],
    ) -> EnvironmentalQA:
        """Build overall environmental QA."""
        flags: List[str] = []

        soil_available = soilgrids_qa is not None
        fao_available = fao_qa is not None
        weather_count = weather_qa.get("provider_count", 0) if weather_qa else 0
        weather_quality = weather_qa.get("quality", "unusable") if weather_qa else "unusable"

        if not soil_available and not fao_available and weather_count == 0:
            return EnvironmentalQA(
                quality_class=EnvironmentalQualityClass.UNUSABLE,
                flags=["ALL_PROVIDERS_FAILED"],
                reason="No environmental data available",
            )

        # Determine quality
        if soil_available and weather_quality == "good":
            quality = EnvironmentalQualityClass.GOOD
        elif soil_available or weather_count > 0:
            quality = EnvironmentalQualityClass.DEGRADED
            if not soil_available:
                flags.append("NO_SOIL_DATA")
            if weather_count == 0:
                flags.append("NO_WEATHER_DATA")
        else:
            quality = EnvironmentalQualityClass.DEGRADED

        return EnvironmentalQA(
            quality_class=quality,
            soil_provider_available=soil_available,
            fao_provider_available=fao_available,
            weather_provider_count=weather_count,
            weather_consensus_available=weather_count > 0,
            soil_quality=soilgrids_qa.quality_class.value if soilgrids_qa else None,
            fao_quality=fao_qa.quality_class.value if fao_qa else None,
            weather_temporal_completeness=weather_qa.get("temporal_completeness", 0) if weather_qa else 0,
            flags=flags,
        )
