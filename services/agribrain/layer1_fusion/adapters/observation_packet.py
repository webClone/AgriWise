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
    
    # Authenticated publication verification (R10-02, RC2)
    from layer1_fusion.truth_bridge import verify_publication_receipt, PublicationAttestationReceipt, compute_reading_content_digest
    pub_receipt_candidate = (
        getattr(packet, "receipt", None)
        or getattr(source_package, "receipt", None)
        or payload.get("publication_receipt")
        or getattr(getattr(packet, "provenance", None), "receipt", None)
        or getattr(getattr(packet, "provenance", None), "receipt_ref", None)
        or getattr(getattr(source_package, "provenance", None), "receipt_ref", None)
    )

    inst_id = payload.get("instrument_id") or payload.get("device_id") or getattr(packet, "instrument_id", None)
    pkg_plot = getattr(source_package, "plot_id", None) if source_package else None
    effective_plot_id = (packet.plot_id if packet.plot_id and str(packet.plot_id).strip() else None) or (pkg_plot if pkg_plot and str(pkg_plot).strip() else None)
    pkt_time = packet.timestamp

    # Derive measurement digest from the actual canonical reading, not caller payload["content_hash"] (RC2)
    def _safe_reading_digest(dev_id, p_id, var, val, unit, t):
        try:
            return compute_reading_content_digest(dev_id, p_id, var, val, unit, t)
        except Exception:
            return None

    canonical_reading_digest = None
    if source_fam == "sensor":
        first_var = payload.get("variable") or next((k for k in PAYLOAD_VARIABLE_MAP if k in payload and payload[k] is not None), None)
        first_val = payload.get("value")
        if first_val is None and first_var and first_var in payload:
            first_val = payload[first_var]
        first_unit = payload.get("unit")
        if first_val is not None and first_var and effective_plot_id:
            canonical_reading_digest = _safe_reading_digest(
                dev_id=inst_id or packet.packet_id,
                p_id=effective_plot_id,
                var=first_var,
                val=first_val,
                unit=first_unit,
                t=pkt_time,
            )

    expected_pub_hash = canonical_reading_digest if (source_fam == "sensor" and canonical_reading_digest) else payload.get("content_hash")

    is_verified_publication, pub_reason, v_published = verify_publication_receipt(
        pub_receipt_candidate,
        source_family=source_fam,
        acquisition_id=packet.packet_id,
        content_hash=expected_pub_hash,
    )
    if is_verified_publication and v_published is not None:
        p_str = v_published.isoformat()
        flags.append(f"PUBLISHED_AT:{p_str}")
        flags.append("VERIFIED_PUBLICATION_RECEIPT")
    else:
        # Raw caller claims are recorded as claims only; NOT verified
        raw_pub = (
            getattr(source_package, "published_at", None)
            or getattr(packet, "published_at", None)
            or payload.get("published_at")
            or getattr(source_package, "recorded_at", None)
            or getattr(packet, "recorded_at", None)
            or payload.get("recorded_at")
        )
        if raw_pub:
            p_str = raw_pub.isoformat() if hasattr(raw_pub, "isoformat") else str(raw_pub)
            flags.append(f"PUBLISHED_AT:{p_str}")
            flags.append("CALLER_CLAIMED_PUBLICATION_TIME")
        is_verified_publication = False
        v_published = None

    if "flags" in payload and isinstance(payload["flags"], list):
        _reserved_flags = {"VERIFIED_PUBLICATION_RECEIPT", "AUTHENTICATED_SENSOR_RECEIPT", "AUTHENTICATED_PUBLICATION_RECORD"}
        flags.extend([f for f in payload["flags"] if f not in _reserved_flags])
    
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
    explicit_prov = (
        payload.get("provenance_ref")
        or getattr(packet, "provenance_ref", None)
        or (getattr(getattr(packet, "provenance", None), "receipt_ref", None) if getattr(packet, "provenance", None) else None)
    )
    if explicit_prov:
        provenance_ref = str(explicit_prov)
    elif pkg_hash:
        provenance_ref = f"pkg_{pkg_hash}_pkt_{pkt_hash}"
    else:
        provenance_ref = f"packet_{pkt_hash}"

    payload_unit = payload.get("unit")
    
    pkt_time = packet.timestamp

    inst_id = payload.get("instrument_id") or payload.get("device_id") or getattr(packet, "instrument_id", None)
    cal_ver = payload.get("calibration_version") or (getattr(packet.qa, "calibration_version", None) if packet.qa else None)

    pkg_plot = getattr(source_package, "plot_id", None) if source_package else None
    # R8-04 / R8-G06: Require non-empty plot identity on packet or source_package; do not synthesize from bundle.plot_id
    effective_plot_id = (packet.plot_id if packet.plot_id and str(packet.plot_id).strip() else None) or (pkg_plot if pkg_plot and str(pkg_plot).strip() else None)

    parent_acq_id = (
        payload.get("parent_acquisition_id")
        or getattr(getattr(packet, "provenance", None), "acquisition_id", None)
        or getattr(source_package, "package_id", None)
        or packet.packet_id
    )

    if v_published is not None and not isinstance(v_published, datetime):
        try:
            from layer1_fusion.temporal_alignment import ensure_utc
            v_published = ensure_utc(datetime.fromisoformat(str(v_published)))
        except Exception:
            v_published = None
    elif isinstance(v_published, datetime):
        from layer1_fusion.temporal_alignment import ensure_utc
        v_published = ensure_utc(v_published)

    active_receipt = getattr(packet, "receipt", None) or getattr(source_package, "receipt", None)
    if source_fam == "sensor":
        from layer1_fusion.truth_bridge import get_sensor_receipt, SensorAttestationReceipt, compute_reading_content_digest
        if isinstance(active_receipt, PublicationAttestationReceipt) or not isinstance(active_receipt, SensorAttestationReceipt):
            resolved_sensor_rcpt = get_sensor_receipt(str(provenance_ref or "").strip())
            if resolved_sensor_rcpt is not None:
                active_receipt = resolved_sensor_rcpt

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
                plot_id=effective_plot_id,
                variable=var_name,
                value=val,
                unit=unit_name,
                source_family=source_fam,
                source_id=packet.packet_id,
                observation_type=obs_type,
                spatial_scope=packet.spatial_scope or "plot",
                scope_id=payload.get("zone_id") or payload.get("zone") or payload.get("device_id"),
                observed_at=pkt_time,
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
                content_hash=(
                    (canonical_reading_digest or _safe_reading_digest(inst_id or packet.packet_id, effective_plot_id, var_name, val, unit_name, pkt_time))
                    if source_fam == "sensor"
                    else (payload.get("content_hash") or getattr(packet, "content_hash", None))
                ),
                provider_product_id=payload.get("provider_product_id") or payload.get("observation_id"),
                valid_fraction=payload.get("valid_fraction") or payload.get("clear_fraction"),
                instrument_id=inst_id,
                calibration_version=cal_ver,
                parent_acquisition_id=parent_acq_id,
                receipt=active_receipt,
                publication_receipt=pub_receipt_candidate if is_verified_publication else None,
                publication_receipt_verified=is_verified_publication,
                verified_published_at=v_published,
            )
            items.append(item)
            
    if not items and "value" in payload and payload["value"] is not None:
        var_name = payload.get("variable") or payload.get("type", "").lower() or "value"
        unit_name = payload_unit or payload.get("unit") or None
        items.append(EvidenceItem(
            evidence_id=f"{source_fam}_{packet.packet_id}_{var_name}",
            plot_id=effective_plot_id,
            variable=var_name,
            value=payload["value"],
            unit=unit_name,
            source_family=source_fam,
            source_id=packet.packet_id,
            observation_type=obs_type,
            spatial_scope=packet.spatial_scope or "plot",
            scope_id=payload.get("zone_id") or payload.get("zone") or payload.get("device_id"),
            observed_at=pkt_time,
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
            content_hash=(
                (canonical_reading_digest or _safe_reading_digest(inst_id or packet.packet_id, effective_plot_id, var_name, payload["value"], unit_name, pkt_time))
                if source_fam == "sensor"
                else (payload.get("content_hash") or getattr(packet, "content_hash", None))
            ),
            provider_product_id=payload.get("provider_product_id") or payload.get("observation_id"),
            valid_fraction=payload.get("valid_fraction") or payload.get("clear_fraction"),
            instrument_id=inst_id,
            calibration_version=cal_ver,
            parent_acquisition_id=parent_acq_id,
            receipt=active_receipt,
            publication_receipt=pub_receipt_candidate if is_verified_publication else None,
            publication_receipt_verified=is_verified_publication,
            verified_published_at=v_published,
        ))

    return items
