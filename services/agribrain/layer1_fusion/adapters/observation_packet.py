"""
ObservationPacket to EvidenceItem Bridge.

Provides canonical translation from Layer 0 ObservationPackets to Layer 1 EvidenceItems.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle
from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAFlag
from layer1_fusion.source_family import normalize_source_family

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real


def observation_packet_to_evidence(
    packet: ObservationPacket,
    bundle: Layer1InputBundle,
    source_family: Optional[str] = None,
    source_package: Optional[Any] = None,
    fallback_source_family: Optional[str] = None,
) -> List[EvidenceItem]:
    """Convert a Layer 0 ObservationPacket to one or more Layer 1 EvidenceItems."""
    items: List[EvidenceItem] = []
    
    # 1. Map ObservationSource -> Layer 1 source family
    sf_map = {
        ObservationSource.SENTINEL2: "sentinel2",
        ObservationSource.SENTINEL1: "sentinel1",
        ObservationSource.SENTINEL5P: "sentinel5p",
        ObservationSource.WEATHER_REANALYSIS: "environment",
        ObservationSource.WEATHER_STATION: "environment",
        ObservationSource.WEATHER_FORECAST: "weather_forecast",
        ObservationSource.SOILGRIDS: "environment",
        ObservationSource.FAO: "environment",
        ObservationSource.SENSOR_IOT: "sensor",
        ObservationSource.USER_EVENT: "user_event",
        ObservationSource.USER_OBSERVATION: "user_event",
        ObservationSource.DRONE: "drone_structural",
        ObservationSource.IP_CAMERA: "perception",
        ObservationSource.SATELLITE_RGB: "perception",
        ObservationSource.FARMER_PHOTO: "perception",
        ObservationSource.GEO_CONTEXT: "geo_context",
        ObservationSource.DEM: "geo_context",
        ObservationSource.LANDCOVER: "geo_context",
        ObservationSource.WAPOR: "geo_context",
    }
    
    mapped_family = sf_map.get(packet.source)
    source_fam = mapped_family or fallback_source_family or source_family or "environment"
    source_fam = normalize_source_family(source_fam)
    
    # 2. Map ObservationType -> Layer 1 observation type
    obs_type = "measurement"
    if packet.data_status == DataStatus.ESTIMATED:
        obs_type = "model_estimate"
    elif packet.data_status == DataStatus.INTERPOLATED:
        obs_type = "derived_feature"
    elif packet.data_status == DataStatus.ASSIMILATED:
        obs_type = "state_estimate"
    elif packet.data_status == DataStatus.FALLBACK:
        obs_type = "diagnostic"
    elif packet.data_status == DataStatus.SIMULATED:
        obs_type = "diagnostic"
    elif packet.data_status == DataStatus.UNAVAILABLE:
        obs_type = "diagnostic"
        
    if source_fam == "weather_forecast":
        obs_type = "forecast"
    elif source_fam in ("geo_context", "soilgrids", "fao"):
        obs_type = "static_prior"
    elif source_fam == "user_event":
        obs_type = "event"

    payload = packet.payload or {}
    
    # 3. Extract common payload variables (agronomic variables)
    PAYLOAD_VARIABLE_MAP = {
        "ndvi_mean": ("ndvi", "index"),
        "evi_mean": ("evi", "index"),
        "ndmi_mean": ("ndmi", "index"),
        "ndre_mean": ("ndre", "index"),
        "bsi_mean": ("bsi", "index"),

        "ndvi": ("ndvi", "index"),
        "evi": ("evi", "index"),
        "ndmi": ("ndmi", "index"),
        "ndre": ("ndre", "index"),
        "bsi": ("bsi", "index"),

        "vv_db_mean": ("sar_vv_db", "dB"),
        "vh_db_mean": ("sar_vh_db", "dB"),
        "surface_wetness_proxy_mean": ("sar_surface_wetness_proxy", "index"),

        "vv_db": ("sar_vv_db", "dB"),
        "vh_db": ("sar_vh_db", "dB"),
        "surface_wetness_proxy": ("sar_surface_wetness_proxy", "index"),

        "soil_moisture_vwc": ("soil_moisture_vwc", "fraction"),
        "vegetation_fraction": ("vegetation_fraction", "fraction"),
        "bare_soil_fraction": ("bare_soil_fraction", "fraction"),

        "temp_max": ("temp_max", "degC"),
        "temp_min": ("temp_min", "degC"),
        "temp_mean": ("temp_mean", "degC"),
        "precipitation": ("precipitation", "mm"),
        "et0": ("et0", "mm"),
        "humidity": ("humidity", "percent"),
        "humidity_mean_pct": ("humidity", "percent"),
        "wind_speed": ("wind_speed", "m_s"),
        "wind_speed_m_s": ("wind_speed", "m_s"),

        "clay_pct": ("soil_clay_pct", "percent"),
        "sand_pct": ("soil_sand_pct", "percent"),
        "soil_clay_pct": ("soil_clay_pct", "percent"),
        "soil_sand_pct": ("soil_sand_pct", "percent"),
        "ph": ("soil_ph", "pH"),
        "soil_ph": ("soil_ph", "pH"),
    }

    fin_scene = finite_real(packet.qa.scene_score) if packet.qa else 0.5
    fin_rel_w = finite_real(getattr(packet, "reliability_weight", 1.0))
    if fin_scene is None or fin_rel_w is None or fin_scene < 0.0 or fin_rel_w < 0.0:
        reliability = 0.0
    elif fin_scene == 0.0 or fin_rel_w == 0.0:
        reliability = 0.0
    else:
        reliability = max(0.0, min(1.0, min(fin_scene, fin_rel_w)))

    cloud_frac = getattr(packet.qa, "cloud_probability", 0.0) or 0.0
    base_confidence = packet.effective_weight()
    
    base_sigma = 0.05
    if packet.uncertainty and packet.uncertainty.sigmas:
        base_sigma = next(iter(packet.uncertainty.sigmas.values()), 0.05)

    flags = [f.value for f in (packet.qa.flags or [])] if packet.qa else []
    
    diagnostic_only = False
    state_update_allowed = True
    
    # Apply status-specific rules and confidence ceilings
    if packet.data_status == DataStatus.SIMULATED:
        diagnostic_only = True
        state_update_allowed = False
        base_confidence = min(base_confidence, 0.20)
        flags.append("SIMULATED_DATA")
    elif packet.data_status == DataStatus.UNAVAILABLE:
        diagnostic_only = True
        state_update_allowed = False
        base_confidence = 0.0
        flags.append("DATA_UNAVAILABLE")
    elif packet.data_status == DataStatus.FALLBACK:
        diagnostic_only = True
        state_update_allowed = False
        base_confidence = min(base_confidence, 0.35)
        flags.append("FALLBACK_DATA")
    elif packet.data_status == DataStatus.INTERPOLATED:
        base_confidence = min(base_confidence, 0.65)
        flags.append("INTERPOLATED_DATA")
    elif packet.data_status == DataStatus.ESTIMATED:
        base_confidence = min(base_confidence, 0.75)
        flags.append("ESTIMATED_DATA")

    from layer1_fusion.truth_bridge import normalize_truth_from_packet

    truth = normalize_truth_from_packet(packet, source_package)

    STATUS_RANKS = {
        "unavailable": 5,
        "simulated": 4,
        "fallback": 3,
        "estimated": 2,
        "interpolated": 1,
        "observed": 0,
    }
    packet_status = packet.data_status.value
    truth_status = truth.data_status
    if STATUS_RANKS.get(packet_status, 0) >= STATUS_RANKS.get(truth_status, 0):
        final_data_status = packet_status
    else:
        final_data_status = truth_status

    fin_base_conf = finite_real(base_confidence)
    if fin_base_conf is None or fin_base_conf < 0.0:
        final_confidence = 0.0
    else:
        final_confidence = fin_base_conf

    if final_data_status == "unavailable":
        final_confidence = 0.0
    elif final_data_status == "simulated":
        final_confidence = min(final_confidence, 0.20)
    elif final_data_status == "fallback":
        final_confidence = min(final_confidence, 0.35)
    elif final_data_status == "interpolated":
        final_confidence = min(final_confidence, 0.65)
    elif final_data_status == "estimated":
        final_confidence = min(final_confidence, 0.75)

    is_zero_confidence_or_reliability = (final_confidence == 0.0) or (reliability == 0.0)
    final_diagnostic_only = bool(truth.diagnostic_only or diagnostic_only or (final_data_status != "observed") or is_zero_confidence_or_reliability)
    final_state_update_allowed = bool(truth.state_update_allowed and state_update_allowed and (final_data_status == "observed") and not is_zero_confidence_or_reliability)

    pkg_hash = getattr(source_package, "package_hash", "") or ""
    pkt_hash = getattr(packet, "content_hash", "") or packet.packet_id
    if pkg_hash:
        provenance_ref = f"pkg_{pkg_hash}_pkt_{pkt_hash}"
    else:
        provenance_ref = f"packet_{pkt_hash}"

    payload_unit = payload.get("unit")
    
    extracted_keys = set()
    for src_key, (target_var, default_unit) in PAYLOAD_VARIABLE_MAP.items():
        if src_key in payload and payload[src_key] is not None:
            var_name = target_var or payload.get("variable") or src_key
            unit_name = payload_unit or default_unit or None
            val = payload[src_key]
            
            if var_name in extracted_keys:
                continue
            extracted_keys.add(var_name)

            item = EvidenceItem(
                evidence_id=f"{source_fam}_{packet.packet_id}_{var_name}",
                plot_id=packet.plot_id or bundle.plot_id,
                variable=var_name,
                value=val,
                unit=unit_name,
                source_family=source_fam,
                source_id=packet.packet_id,
                observation_type=obs_type,
                spatial_scope=packet.spatial_scope or "plot",
                scope_id=payload.get("zone_id") or payload.get("zone") or payload.get("device_id"),
                observed_at=packet.timestamp,
                confidence=final_confidence,
                sigma=base_sigma,
                reliability=reliability,
                freshness_score=0.0,
                provenance_ref=provenance_ref,
                flags=flags.copy(),
                data_status=final_data_status,
                truth_class=truth.truth_class,
                source_reality=truth.source_reality,
                production_usable=truth.production_usable and (final_data_status != "unavailable"),
                real_provider_product=truth.real_provider_product,
                diagnostic_only=final_diagnostic_only,
                state_update_allowed=final_state_update_allowed,
                grounding_class=truth.grounding_class,
                visualization_allowed=truth.visualization_allowed,
                experimental_visual_allowed=truth.experimental_visual_allowed,
                composite_advisory_allowed=truth.composite_advisory_allowed,
                scientific_surface_allowed=truth.scientific_surface_allowed and (final_data_status == "observed"),
                prescription_driver_allowed=truth.prescription_driver_allowed and (final_data_status == "observed"),
                current_1m_approval_allowed=truth.current_1m_approval_allowed and (final_data_status == "observed"),
                temporal_basis=payload.get("temporal_basis"),
                content_hash=payload.get("content_hash") or getattr(packet, "content_hash", None),
                provider_product_id=payload.get("provider_product_id") or payload.get("observation_id"),
                valid_fraction=payload.get("valid_fraction") or payload.get("clear_fraction"),
            )
            items.append(item)
            
    if not items and "value" in payload and payload["value"] is not None:
        var_name = payload.get("variable") or payload.get("type", "").lower() or "value"
        unit_name = payload_unit or payload.get("unit") or None
        items.append(EvidenceItem(
            evidence_id=f"{source_fam}_{packet.packet_id}_{var_name}",
            plot_id=packet.plot_id or bundle.plot_id,
            variable=var_name,
            value=payload["value"],
            unit=unit_name,
            source_family=source_fam,
            source_id=packet.packet_id,
            observation_type=obs_type,
            spatial_scope=packet.spatial_scope or "plot",
            scope_id=payload.get("zone_id") or payload.get("zone") or payload.get("device_id"),
            observed_at=packet.timestamp,
            confidence=final_confidence,
            sigma=base_sigma,
            reliability=reliability,
            freshness_score=0.0,
            provenance_ref=provenance_ref,
            flags=flags.copy(),
            data_status=final_data_status,
            truth_class=truth.truth_class,
            source_reality=truth.source_reality,
            production_usable=truth.production_usable and (final_data_status != "unavailable"),
            real_provider_product=truth.real_provider_product,
            diagnostic_only=final_diagnostic_only,
            state_update_allowed=final_state_update_allowed,
            grounding_class=truth.grounding_class,
            visualization_allowed=truth.visualization_allowed,
            experimental_visual_allowed=truth.experimental_visual_allowed,
            composite_advisory_allowed=truth.composite_advisory_allowed,
            scientific_surface_allowed=truth.scientific_surface_allowed and (final_data_status == "observed"),
            prescription_driver_allowed=truth.prescription_driver_allowed and (final_data_status == "observed"),
            current_1m_approval_allowed=truth.current_1m_approval_allowed and (final_data_status == "observed"),
            temporal_basis=payload.get("temporal_basis"),
            content_hash=payload.get("content_hash") or getattr(packet, "content_hash", None),
            provider_product_id=payload.get("provider_product_id") or payload.get("observation_id"),
            valid_fraction=payload.get("valid_fraction") or payload.get("clear_fraction"),
        ))

    return items
