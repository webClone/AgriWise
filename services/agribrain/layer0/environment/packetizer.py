"""
Environmental Context Packetizer.

Emits 10 packet types. Partial provider failure emits available packets.
All providers fail → ENVIRONMENT_PROVENANCE + diagnostics only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from layer0.environment.schemas import ProcessForcing, ProcessParameters
from layer0.environment.soilgrids.schemas import (
    SoilGridsDerivedHydraulics,
    SoilGridsProfile,
    SoilGridsQAResult,
)
from layer0.environment.fao.schemas import FAOSoilContext, FAOQAResult
from layer0.environment.weather.schemas import WeatherConsensusDaily, WeatherTimeSeries


# Packet type constants
SOILGRIDS_PROFILE_PRIOR = "SOILGRIDS_PROFILE_PRIOR"
SOILGRIDS_DERIVED_HYDRAULICS = "SOILGRIDS_DERIVED_HYDRAULICS"
FAO_SOIL_CONTEXT = "FAO_SOIL_CONTEXT"
FAO_AGROECOLOGICAL_CONTEXT = "FAO_AGROECOLOGICAL_CONTEXT"
WEATHER_PROVIDER_OBSERVATION = "WEATHER_PROVIDER_OBSERVATION"
WEATHER_CONSENSUS_DAILY = "WEATHER_CONSENSUS_DAILY"
WEATHER_FORCING_DAILY = "WEATHER_FORCING_DAILY"
WEATHER_FORECAST = "WEATHER_FORECAST"
WEATHER_DERIVED_FEATURES = "WEATHER_DERIVED_FEATURES"
ENVIRONMENT_PROVENANCE = "ENVIRONMENT_PROVENANCE"


def _make_packet(
    packet_type: str,
    payload: Dict[str, Any],
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a standardized packet envelope."""
    return {
        "packet_type": packet_type,
        "source": "environment_v1",
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "provenance": provenance or {},
        "payload": payload,
    }


def emit_environment_packets(
    soilgrids_profile: Optional[SoilGridsProfile] = None,
    soilgrids_qa: Optional[SoilGridsQAResult] = None,
    derived_hydraulics: Optional[SoilGridsDerivedHydraulics] = None,
    fao_context: Optional[FAOSoilContext] = None,
    fao_qa: Optional[FAOQAResult] = None,
    weather_timeseries: Optional[WeatherTimeSeries] = None,
    weather_consensus: Optional[List[WeatherConsensusDaily]] = None,
    process_forcing: Optional[List[ProcessForcing]] = None,
    process_parameters: Optional[ProcessParameters] = None,
    derived_features: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Emit environmental observation packets.

    Partial provider failure: emit what is available.
    All providers fail: only ENVIRONMENT_PROVENANCE.
    """
    packets: List[Dict[str, Any]] = []

    # Always emit provenance
    packets.append(_make_packet(
        ENVIRONMENT_PROVENANCE,
        provenance or {"status": "partial_or_complete"},
        provenance,
    ))

    # SoilGrids packets (if available)
    if soilgrids_profile is not None and soilgrids_qa is not None:
        packets.append(_make_packet(
            SOILGRIDS_PROFILE_PRIOR,
            {
                "quality_class": soilgrids_qa.quality_class.value,
                "depth_completeness": soilgrids_qa.depth_completeness,
                "property_completeness": soilgrids_qa.property_completeness,
                "water_property_available": soilgrids_qa.water_property_available,
                "texture_sum_consistent": soilgrids_qa.texture_sum_consistent,
                "provider": soilgrids_profile.provider,
                "resolution_m": soilgrids_profile.source_resolution_m,
                "label": "soil_prior",
                "flags": soilgrids_qa.flags,
            },
            provenance,
        ))

        if derived_hydraulics is not None:
            packets.append(_make_packet(
                SOILGRIDS_DERIVED_HYDRAULICS,
                {
                    "texture_class": derived_hydraulics.texture_class,
                    "root_zone_awc_mm_0_30": derived_hydraulics.root_zone_awc_mm_0_30,
                    "root_zone_awc_mm_0_60": derived_hydraulics.root_zone_awc_mm_0_60,
                    "root_zone_awc_mm_0_100": derived_hydraulics.root_zone_awc_mm_0_100,
                    "drainage_risk": derived_hydraulics.drainage_risk,
                    "water_holding_capacity_class": derived_hydraulics.water_holding_capacity_class,
                    "coarse_fragment_correction_applied": derived_hydraulics.coarse_fragment_correction_applied,
                    "label": "derived_proxy",
                },
                provenance,
            ))

    # FAO packets (if available)
    if fao_context is not None:
        packets.append(_make_packet(
            FAO_SOIL_CONTEXT,
            {
                "dominant_soil_type": fao_context.dominant_soil_type,
                "topsoil_texture": fao_context.topsoil_texture,
                "subsoil_texture": fao_context.subsoil_texture,
                "soil_depth_class": fao_context.soil_depth_class,
                "resolution_m": fao_context.resolution_m,
                "label": "soil_context",
            },
            provenance,
        ))

        if fao_context.agro_ecological_flags:
            packets.append(_make_packet(
                FAO_AGROECOLOGICAL_CONTEXT,
                {
                    "salinity_risk": fao_context.salinity_risk,
                    "sodicity_risk": fao_context.sodicity_risk,
                    "calcareous_lime_risk": fao_context.calcareous_lime_risk,
                    "gypsum_risk": fao_context.gypsum_risk,
                    "drainage_limitation": fao_context.drainage_limitation,
                    "agro_ecological_flags": fao_context.agro_ecological_flags,
                },
                provenance,
            ))

    # Weather packets (if available)
    if weather_timeseries is not None and weather_timeseries.daily_records:
        for provider in weather_timeseries.providers:
            provider_records = [
                r for r in weather_timeseries.daily_records if r.provider == provider
            ]
            packets.append(_make_packet(
                WEATHER_PROVIDER_OBSERVATION,
                {
                    "provider": provider,
                    "record_count": len(provider_records),
                    "date_range": [provider_records[0].date, provider_records[-1].date]
                    if provider_records else [],
                    "data_kinds": sorted(set(r.data_kind for r in provider_records)),
                },
                provenance,
            ))

            forecast_records = [r for r in provider_records if r.data_kind == "forecast"]
            if forecast_records:
                packets.append(_make_packet(
                    WEATHER_FORECAST,
                    {
                        "provider": provider,
                        "record_count": len(forecast_records),
                        "date_range": [forecast_records[0].date, forecast_records[-1].date],
                        "forecast_data": [
                            {
                                "date": r.date,
                                "temp_min": r.temp_min,
                                "temp_max": r.temp_max,
                                "precipitation_sum": r.precipitation_sum,
                            } for r in forecast_records
                        ]
                    },
                    provenance,
                ))

    if weather_consensus:
        for daily_consensus in weather_consensus:
            packets.append(_make_packet(
                WEATHER_CONSENSUS_DAILY,
                {
                    "date": daily_consensus.date,
                    "data_kind": daily_consensus.data_kind,
                    "overall_confidence": daily_consensus.overall_confidence,
                    "flags": daily_consensus.flags,
                    "variables": {
                        var: {
                            "value": vc.selected_value,
                            "confidence": vc.confidence,
                            "source": vc.source,
                            "flags": vc.flags,
                        }
                        for var, vc in daily_consensus.variable_consensus.items()
                    },
                },
                provenance,
            ))

    if process_forcing:
        for forcing in process_forcing:
            packets.append(_make_packet(
                WEATHER_FORCING_DAILY,
                {
                    "date": forcing.date,
                    "gdd": forcing.gdd,
                    "precipitation_mm": forcing.precipitation_mm,
                    "et0_mm": forcing.et0_mm,
                    "et0_source": forcing.et0_source,
                    "water_balance_mm": forcing.water_balance_mm,
                    "frost_flag": forcing.frost_flag,
                    "thermal_stress_flag": forcing.thermal_stress_flag,
                    "rainfall_confidence": forcing.rainfall_confidence,
                },
                provenance,
            ))

    if derived_features:
        packets.append(_make_packet(
            WEATHER_DERIVED_FEATURES,
            derived_features,
            provenance,
        ))

    return packets
