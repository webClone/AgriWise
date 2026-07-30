"""
Layer 0 Source Wrappers — Thin adapters that return Layer0SourcePackage.

Each wrapper calls the native engine and converts the native package
into a canonical Layer0SourcePackage. This avoids rewriting engines
while providing a uniform output contract.

Usage:
    from layer0.wrappers import wrap_sentinel2, wrap_sentinel1, ...
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .source_package import Layer0SourcePackage
from .observation_packet import DataStatus, ObservationPacket, ObservationSource


def _selected_consensus_value(variables: Any, *names: str) -> Any:
    """Read a consensus value from either native dataclasses or dictionaries."""
    for name in names:
        entry = variables.get(name) if isinstance(variables, dict) else None
        if entry is None:
            continue
        if isinstance(entry, dict):
            value = entry.get("selected_value")
            if value is None:
                value = entry.get("value")
        else:
            value = getattr(entry, "selected_value", None)
        if value is not None:
            return value
    return None


def _canonical_weather_records(env_package: Any, packets: List[ObservationPacket]) -> List[Dict[str, Any]]:
    """Freeze weather consensus into an evidence-addressed transport contract."""
    packet_ids: Dict[tuple, str] = {}
    for packet in packets:
        raw = packet.payload if isinstance(packet.payload, dict) else {}
        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else raw
        packet_type = str(raw.get("packet_type") or payload.get("packet_type") or "")
        date = str(payload.get("date") or "")[:10]
        if packet_type and date:
            packet_ids[(packet_type, date)] = packet.content_hash

    records: List[Dict[str, Any]] = []
    streams = (
        (getattr(env_package, "weather_consensus", None) or [], "WEATHER_CONSENSUS_DAILY", False),
        (getattr(env_package, "forecast_consensus", None) or [], "WEATHER_FORECAST_CONSENSUS_DAILY", True),
    )
    for daily_records, packet_type, forecast in streams:
        for daily in daily_records:
            if isinstance(daily, dict):
                date = str(daily.get("date") or daily.get("timestamp") or "")[:10]
                variables = daily.get("variable_consensus") or daily.get("variables") or {}
                data_kind = str(daily.get("data_kind") or ("forecast" if forecast else "unknown"))
                confidence = daily.get("overall_confidence")
                if confidence is None:
                    confidence = daily.get("overall_forecast_confidence")
            else:
                date = str(getattr(daily, "date", "") or "")[:10]
                variables = getattr(daily, "variable_consensus", {}) or {}
                data_kind = str(getattr(daily, "data_kind", "") or ("forecast" if forecast else "unknown"))
                confidence = getattr(daily, "overall_confidence", None)
                if confidence is None:
                    confidence = getattr(daily, "overall_forecast_confidence", None)
            if not date:
                continue

            record = {
                "date": date,
                "data_kind": data_kind,
                "packet_type": packet_type,
                "source": "environment_weather_consensus",
                "evidence_id": packet_ids.get((packet_type, date)) or packet_ids.get(("WEATHER_CONSENSUS_DAILY", date)),
                "data_status": "estimated" if forecast else "observed",
                "authority": "process_forcing_only",
                "state_update_allowed": False,
                "overall_confidence": confidence,
                "temp_min_c": _selected_consensus_value(variables, "temp_min", "tmin_c", "temperature_2m_min"),
                "temp_max_c": _selected_consensus_value(variables, "temp_max", "tmax_c", "temperature_2m_max"),
                "temp_mean_c": _selected_consensus_value(variables, "temp_mean", "tmean_c"),
                "precipitation_mm": _selected_consensus_value(variables, "precipitation_sum", "precipitation_sum_mm", "precipitation"),
                "et0_mm": _selected_consensus_value(variables, "et0_mm", "et0_sum_mm", "reference_et0_mm"),
                "humidity_mean_pct": _selected_consensus_value(variables, "relative_humidity_mean", "relative_humidity_mean_pct", "humidity_mean_pct"),
                "wind_speed_m_s": _selected_consensus_value(variables, "wind_speed_max", "wind_speed_mean_10m_ms", "wind_speed_10m_max"),
            }
            if not record["evidence_id"]:
                identity = json.dumps(record, sort_keys=True, default=str)
                record["evidence_id"] = "weather:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
            records.append(record)
    return records


def _extract_timestamp(pkt: Any, fallback: Optional[datetime] = None) -> datetime:
    if isinstance(pkt, dict):
        ts_str = pkt.get("timestamp") or pkt.get("emitted_at") or pkt.get("date")
        if not ts_str and isinstance(pkt.get("payload"), dict):
            pld = pkt["payload"]
            ts_str = pld.get("date") or pld.get("timestamp")
        
        if ts_str:
            try:
                if len(ts_str) == 10 and ts_str[4] == '-' and ts_str[7] == '-':
                    return datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
                else:
                    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                pass
    return fallback or datetime.now(timezone.utc)


def _infer_data_status(payload: dict, source: ObservationSource) -> DataStatus:
    pkt_type = payload.get("packet_type") or payload.get("type") or ""

    if payload.get("source_reality") == "raster_composite_proxy":
        return DataStatus.FALLBACK

    if payload.get("production_usable") is False:
        return DataStatus.FALLBACK

    if (
        payload.get("real_provider_product") is False
        and payload.get("source_reality") != "provider_daily_statistical_aggregate"
    ):
        return DataStatus.FALLBACK

    if payload.get("diagnostic_only") is True:
        return DataStatus.FALLBACK

    if payload.get("data_status"):
        return DataStatus.from_value(payload["data_status"])

    if payload.get("simulated") is True:
        return DataStatus.SIMULATED

    if payload.get("fallback") is True:
        return DataStatus.FALLBACK

    if "FORECAST" in pkt_type or source == ObservationSource.WEATHER_FORECAST:
        return DataStatus.ESTIMATED

    if "CALIBRATION_FAILED" in pkt_type:
        return DataStatus.UNAVAILABLE

    if "DERIVED" in pkt_type or "ESTIMATED" in pkt_type:
        return DataStatus.ESTIMATED

    return DataStatus.OBSERVED


def aggregate_data_status(packets: List[ObservationPacket], available: bool) -> DataStatus:
    if not available or not packets:
        return DataStatus.UNAVAILABLE

    statuses = {p.data_status for p in packets}

    if statuses == {DataStatus.OBSERVED}:
        return DataStatus.OBSERVED

    if DataStatus.SIMULATED in statuses:
        return DataStatus.SIMULATED

    if DataStatus.FALLBACK in statuses:
        return DataStatus.FALLBACK

    if DataStatus.ESTIMATED in statuses or DataStatus.INTERPOLATED in statuses:
        return DataStatus.ESTIMATED

    return DataStatus.OBSERVED


def ensure_observation_packet(
    pkt: Any,
    source: ObservationSource,
    plot_id: str,
    geometry_hash: str,
    geometry_version: Optional[int],
    fallback_timestamp: Optional[datetime] = None,
) -> ObservationPacket:
    if isinstance(pkt, ObservationPacket):
        changed = False
        if not pkt.plot_id and plot_id:
            pkt.plot_id = plot_id
            changed = True
        if not pkt.geometry_hash and geometry_hash:
            pkt.geometry_hash = geometry_hash
            changed = True
        if pkt.geometry_version is None and geometry_version is not None:
            pkt.geometry_version = geometry_version
            changed = True

        # Re-normalize data_status based on updated validation rules
        if pkt.source.value in ("sentinel1", "sentinel2"):
            has_crs = (
                pkt.payload.get("crs") is not None
                and (pkt.payload.get("transform") is not None or pkt.payload.get("affine") is not None)
            )
            if not has_crs:
                if pkt.data_status != DataStatus.FALLBACK:
                    pkt.data_status = DataStatus.FALLBACK
                    changed = True
            else:
                inferred = _infer_data_status(pkt.payload, pkt.source)
                if pkt.data_status != inferred:
                    pkt.data_status = inferred
                    changed = True
        else:
            inferred = _infer_data_status(pkt.payload, pkt.source)
            if pkt.data_status != inferred:
                pkt.data_status = inferred
                changed = True

        if changed:
            pkt.content_hash = pkt._generate_content_hash()
        return pkt

    from .observation_packet import ObservationType, QAMetadata, QAFlag, UncertaintyModel
    
    payload = pkt.copy() if isinstance(pkt, dict) else {}
    
    timestamp_missing = False
    ts_str = payload.get("timestamp") or payload.get("emitted_at") or payload.get("date")
    if not ts_str and isinstance(payload.get("payload"), dict):
        pld = payload["payload"]
        ts_str = pld.get("date") or pld.get("timestamp")
    if not ts_str:
        timestamp_missing = True

    refined_source = source
    pkt_type = payload.get("packet_type") or payload.get("type") or ""
    if source == ObservationSource.WEATHER_REANALYSIS:
        if "SOILGRIDS" in pkt_type:
            refined_source = ObservationSource.SOILGRIDS
        elif "FAO" in pkt_type:
            refined_source = ObservationSource.FAO
        elif "FORECAST" in pkt_type:
            refined_source = ObservationSource.WEATHER_FORECAST
            
    timestamp = _extract_timestamp(payload, fallback_timestamp)
    
    qa_flags = []
    usable = payload.get("usable", True)
    if not usable:
        qa_flags.append(QAFlag.LOW_CONFIDENCE)
    
    quality_class = payload.get("quality_class")
    if quality_class == "unusable":
        qa_flags.append(QAFlag.LOW_CONFIDENCE)
        
    if timestamp_missing:
        payload["missing_timestamp"] = True
        if QAFlag.LOW_CONFIDENCE not in qa_flags:
            qa_flags.append(QAFlag.LOW_CONFIDENCE)
            
    qa = QAMetadata(
        flags=qa_flags,
        scene_score=payload.get("reading_reliability") or payload.get("reliability_weight") or 1.0,
    )
    
    spatial_scope = payload.get("spatial_scope") or "plot"
    if "device_id" in payload:
        spatial_scope = "point"

    data_status = _infer_data_status(payload, refined_source)
    if timestamp_missing and data_status == DataStatus.OBSERVED:
        data_status = DataStatus.FALLBACK

    return ObservationPacket(
        source=refined_source,
        obs_type=ObservationType.TABULAR,
        timestamp=timestamp,
        payload=payload,
        plot_id=plot_id,
        geometry_hash=geometry_hash,
        geometry_version=geometry_version,
        data_status=data_status,
        qa=qa,
        uncertainty=UncertaintyModel(sigmas={
            "observation": float(payload.get("uncertainty"))
        }) if isinstance(payload.get("uncertainty"), (int, float)) else UncertaintyModel(),
        reliability_weight=float(payload.get("reading_reliability") or 1.0),
        spatial_scope=spatial_scope,
    )


# ============================================================================
# Sentinel-2
# ============================================================================

def wrap_sentinel2(
    s2_package,
    plot_id: str = "",
    geometry_hash: str = "",
    geometry_version: Optional[int] = None,
    time_window: Optional[Dict[str, str]] = None,
) -> Layer0SourcePackage:
    """Wrap a Sentinel2ScenePackage into a Layer0SourcePackage."""
    meta = s2_package.metadata
    _plot_id = plot_id or s2_package.plot_id or ""
    _geometry_hash = geometry_hash or getattr(meta, 'plot_geometry_hash', '') or ""

    packets = [
        ensure_observation_packet(
            pkt,
            ObservationSource.SENTINEL2,
            plot_id=_plot_id,
            geometry_hash=_geometry_hash,
            geometry_version=geometry_version,
            fallback_timestamp=meta.acquisition_datetime,
        )
        for pkt in (s2_package.packets or [])
    ]

    existing_prov = s2_package.provenance_report if hasattr(s2_package, 'provenance_report') else {}
    has_raster_data = bool(getattr(s2_package, "local_cache_refs", {}) or getattr(s2_package, "band_arrays", None))
    source_reality = getattr(s2_package, "source_reality", None)
    if not source_reality:
        source_reality = "real_raster" if has_raster_data else "mean_only"
    provenance = {
        **existing_prov,
        "asmae_scene_metadata": {
            "scene_id": getattr(meta, "scene_id", None),
            "acquisition_datetime": meta.acquisition_datetime.isoformat() if meta.acquisition_datetime else None,
            "crs": getattr(meta, "crs", None),
            "transform": getattr(meta, "transform", None),
            "width": getattr(meta, "width", None),
            "height": getattr(meta, "height", None),
            "band_list": getattr(meta, "band_list", []),
            "band_refs": getattr(s2_package, "local_cache_refs", {}),
            "source_reality": source_reality,
        }
    }

    return Layer0SourcePackage(
        source_family="sentinel2",
        plot_id=_plot_id,
        geometry_hash=_geometry_hash,
        geometry_version=geometry_version,
        time_window=time_window or {
            "acquisition": meta.acquisition_datetime.isoformat() if meta.acquisition_datetime else "",
        },
        data_status=aggregate_data_status(packets, s2_package.qa.usable),
        is_available=bool(packets),
        packets=packets,
        kalman_observations=s2_package.kalman_observations if hasattr(s2_package, 'kalman_observations') else [],
        diagnostics=s2_package.diagnostics or {},
        provenance=provenance,
        health={
            "transport_received": bool(packets),
            "quality_admitted": bool(s2_package.qa.usable),
            "state_eligible": any(p.data_status == DataStatus.OBSERVED for p in packets),
            "scientifically_healthy": bool(s2_package.qa.usable) and any(p.data_status == DataStatus.OBSERVED for p in packets),
            "usable": s2_package.qa.usable,
            "quality_class": s2_package.qa.quality_class.value,
            "valid_fraction": s2_package.qa.valid_fraction,
        },
    )


# ============================================================================
# Sentinel-1
# ============================================================================

def wrap_sentinel1(
    s1_package,
    plot_id: str = "",
    geometry_hash: str = "",
    geometry_version: Optional[int] = None,
    time_window: Optional[Dict[str, str]] = None,
) -> Layer0SourcePackage:
    """Wrap a Sentinel1ScenePackage into a Layer0SourcePackage."""
    meta = s1_package.metadata
    _plot_id = plot_id or s1_package.plot_id or ""
    _geometry_hash = geometry_hash or meta.plot_geometry_hash or ""

    packets = [
        ensure_observation_packet(
            pkt,
            ObservationSource.SENTINEL1,
            plot_id=_plot_id,
            geometry_hash=_geometry_hash,
            geometry_version=geometry_version,
            fallback_timestamp=meta.acquisition_datetime,
        )
        for pkt in (s1_package.packets or [])
    ]

    existing_prov = s1_package.provenance if isinstance(s1_package.provenance, dict) else {}
    has_raster_data = bool(getattr(s1_package, "local_cache_refs", {}) or getattr(s1_package, "band_arrays", None))
    source_reality = getattr(s1_package, "source_reality", None)
    if not source_reality:
        source_reality = "real_raster" if has_raster_data else "mean_only"
    provenance = {
        **existing_prov,
        "asmae_scene_metadata": {
            "scene_id": getattr(meta, "scene_id", None),
            "acquisition_datetime": meta.acquisition_datetime.isoformat() if meta.acquisition_datetime else None,
            "crs": getattr(meta, "crs", None),
            "transform": getattr(meta, "transform", None),
            "width": getattr(meta, "width", None),
            "height": getattr(meta, "height", None),
            "band_list": getattr(meta, "band_list", []),
            "band_refs": getattr(s1_package, "local_cache_refs", {}),
            "source_reality": source_reality,
        }
    }

    return Layer0SourcePackage(
        source_family="sentinel1",
        plot_id=_plot_id,
        geometry_hash=_geometry_hash,
        geometry_version=geometry_version,
        time_window=time_window or {
            "acquisition": meta.acquisition_datetime.isoformat() if meta.acquisition_datetime else "",
        },
        data_status=aggregate_data_status(packets, s1_package.qa.usable),
        is_available=bool(packets),
        packets=packets,
        kalman_observations=s1_package.kalman_observations or [],
        diagnostics=s1_package.diagnostics or {},
        provenance=provenance,
        health={
            "transport_received": bool(packets),
            "quality_admitted": bool(s1_package.qa.usable),
            "state_eligible": any(p.data_status == DataStatus.OBSERVED for p in packets),
            "scientifically_healthy": bool(s1_package.qa.usable) and any(p.data_status == DataStatus.OBSERVED for p in packets),
            "usable": s1_package.qa.usable,
            "quality_class": s1_package.qa.quality_class.value,
            "valid_fraction": s1_package.qa.valid_fraction,
        },
    )


# ============================================================================
# Environment
# ============================================================================

def wrap_environment(
    env_package,
    plot_id: str = "",
    geometry_hash: str = "",
    geometry_version: Optional[int] = None,
) -> Layer0SourcePackage:
    """Wrap an EnvironmentalContextPackage into a Layer0SourcePackage."""
    has_data = (
        env_package.soilgrids_profile is not None
        or env_package.fao_context is not None
        or len(env_package.weather_consensus) > 0
    )

    fallback_time = None
    if env_package.timestamp_window and env_package.timestamp_window.get("window_end"):
        try:
            fallback_time = datetime.fromisoformat(env_package.timestamp_window["window_end"].replace("Z", "+00:00"))
        except Exception:
            pass

    packets = [
        ensure_observation_packet(
            pkt,
            ObservationSource.WEATHER_REANALYSIS,
            plot_id=plot_id or env_package.plot_id or "",
            geometry_hash=geometry_hash,
            geometry_version=geometry_version,
            fallback_timestamp=fallback_time,
        )
        for pkt in (env_package.packets or [])
    ]

    return Layer0SourcePackage(
        source_family="environment",
        plot_id=plot_id or env_package.plot_id or "",
        geometry_hash=geometry_hash,
        geometry_version=geometry_version,
        time_window=env_package.timestamp_window or {},
        data_status=aggregate_data_status(packets, has_data),
        is_available=has_data,
        packets=packets,
        kalman_observations=env_package.weak_kalman_observations or [],
        process_forcing=[f for f in (env_package.process_forcing or [])],
        evidence_records=_canonical_weather_records(env_package, packets),
        diagnostics=env_package.diagnostics if isinstance(env_package.diagnostics, dict) else {},
        provenance=env_package.provenance if isinstance(env_package.provenance, dict) else {},
        health={
            "quality_class": env_package.qa.quality_class.value if env_package.qa else "unknown",
            "soil_available": env_package.soilgrids_profile is not None,
            "fao_available": env_package.fao_context is not None,
            "weather_days": len(env_package.weather_consensus),
        },
    )


# ============================================================================
# Sensors
# ============================================================================

def wrap_sensors(
    sensor_package,
    plot_id: str = "",
    geometry_hash: str = "",
    geometry_version: Optional[int] = None,
) -> Layer0SourcePackage:
    """Wrap a SensorContextPackage into a Layer0SourcePackage."""
    has_data = len(sensor_package.readings) > 0

    fallback_time = sensor_package.window_end

    packets = [
        ensure_observation_packet(
            pkt,
            ObservationSource.SENSOR_IOT,
            plot_id=plot_id or sensor_package.plot_id or "",
            geometry_hash=geometry_hash,
            geometry_version=geometry_version,
            fallback_timestamp=fallback_time,
        )
        for pkt in (sensor_package.observation_packets or [])
    ]

    return Layer0SourcePackage(
        source_family="sensor",
        plot_id=plot_id or sensor_package.plot_id or "",
        geometry_hash=geometry_hash,
        geometry_version=geometry_version,
        time_window={
            "start": sensor_package.window_start.isoformat() if sensor_package.window_start else "",
            "end": sensor_package.window_end.isoformat() if sensor_package.window_end else "",
        },
        data_status=aggregate_data_status(packets, has_data),
        is_available=has_data,
        packets=packets,
        kalman_observations=sensor_package.kalman_observations or [],
        process_forcing=sensor_package.process_forcing_events or [],
        diagnostics=sensor_package.diagnostics if isinstance(sensor_package.diagnostics, dict) else {},
        provenance=sensor_package.provenance if isinstance(sensor_package.provenance, dict) else {},
        health={
            "device_count": len(sensor_package.devices),
            "reading_count": len(sensor_package.readings),
            "aggregate_count": len(sensor_package.aggregates),
        },
    )


# ============================================================================
# Geo Context
# ============================================================================

def wrap_geo_context(
    packets: List[ObservationPacket],
    plot_id: str = "",
    geometry_hash: str = "",
    geometry_version: Optional[int] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Layer0SourcePackage:
    """Wrap geo context ObservationPackets into a Layer0SourcePackage.

    Geo Context returns packets directly (no separate package object),
    so this wrapper accepts the packet list.
    """
    has_data = len(packets) > 2  # More than just provenance + diagnostics
    normalized_packets = [
        ensure_observation_packet(
            pkt,
            ObservationSource.GEO_CONTEXT,
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            geometry_version=geometry_version,
        )
        for pkt in packets
    ]
    return Layer0SourcePackage(
        source_family="geo_context",
        plot_id=plot_id,
        geometry_hash=geometry_hash,
        geometry_version=geometry_version,
        data_status=aggregate_data_status(normalized_packets, has_data),
        is_available=has_data,
        packets=normalized_packets,
        diagnostics=diagnostics or {},
        health={"packet_count": len(packets), "has_data": has_data},
    )


# ============================================================================
# Perception
# ============================================================================

def wrap_perception(
    packets: List[ObservationPacket],
    engine_family: str = "perception",
    plot_id: str = "",
    geometry_hash: str = "",
    geometry_version: Optional[int] = None,
    observation_source: ObservationSource = ObservationSource.SATELLITE_RGB,
) -> Layer0SourcePackage:
    """Wrap perception ObservationPackets into a Layer0SourcePackage.

    Perception engines return packets via the shared packet_adapter,
    so this wrapper accepts the packet list.
    """
    has_data = len(packets) > 0
    normalized_packets = [
        ensure_observation_packet(
            pkt,
            observation_source,
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            geometry_version=geometry_version,
        )
        for pkt in packets
    ]
    return Layer0SourcePackage(
        source_family=engine_family,
        plot_id=plot_id,
        geometry_hash=geometry_hash,
        geometry_version=geometry_version,
        data_status=aggregate_data_status(normalized_packets, has_data),
        is_available=has_data,
        packets=normalized_packets,
        health={"packet_count": len(packets), "has_data": has_data},
    )
