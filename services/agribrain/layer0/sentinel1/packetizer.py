"""
Sentinel-1 SAR Packetizer.

Emits standardized observation packets from a Sentinel1ScenePackage.
UNUSABLE scenes emit QA + PROVENANCE only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from layer0.sentinel1.schemas import (
    SARQualityClass,
    Sentinel1PlotSummary,
    Sentinel1QAResult,
    Sentinel1SceneMetadata,
    Sentinel1ZoneSummary,
)


# Packet type constants
SENTINEL1_SCENE_QA = "SENTINEL1_SCENE_QA"
SENTINEL1_PROVENANCE = "SENTINEL1_PROVENANCE"
SENTINEL1_PLOT_BACKSCATTER = "SENTINEL1_PLOT_BACKSCATTER"
SENTINEL1_ZONE_BACKSCATTER = "SENTINEL1_ZONE_BACKSCATTER"
SENTINEL1_DERIVED_FEATURES = "SENTINEL1_DERIVED_FEATURES"
SENTINEL1_RASTER_STACK_REF = "SENTINEL1_RASTER_STACK_REF"


def _make_packet(
    packet_type: str,
    metadata: Sentinel1SceneMetadata,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a standardized packet envelope."""
    return {
        "packet_type": packet_type,
        "source": "sentinel1_sar_v1",
        "scene_id": metadata.scene_id,
        "product_id": metadata.product_id,
        "acquisition_datetime": (
            metadata.acquisition_datetime.isoformat()
            if metadata.acquisition_datetime else None
        ),
        "orbit_direction": metadata.orbit_direction,
        "relative_orbit": metadata.relative_orbit,
        "platform": metadata.platform,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def emit_sar_packets(
    metadata: Sentinel1SceneMetadata,
    qa: Sentinel1QAResult,
    plot_summary: Optional[Sentinel1PlotSummary],
    zone_summaries: Optional[List[Sentinel1ZoneSummary]],
    feature_names_computed: Optional[List[str]] = None,
    raster_refs: Optional[Dict[str, str]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Emit observation packets from SAR scene results.

    UNUSABLE → QA + PROVENANCE only.
    Usable → all 6 packet types.
    """
    packets = []

    # Always emit QA
    packets.append(_make_packet(
        SENTINEL1_SCENE_QA,
        metadata,
        {
            "usable": qa.usable,
            "quality_class": qa.quality_class.value,
            "valid_fraction": qa.valid_fraction,
            "border_noise_fraction": qa.border_noise_fraction,
            "low_signal_fraction": qa.low_signal_fraction,
            "speckle_score": qa.speckle_score,
            "incidence_angle_mean": qa.incidence_angle_mean,
            "incidence_angle_penalty": qa.incidence_angle_penalty,
            "reliability_weight": qa.reliability_weight,
            "sigma_multiplier": qa.sigma_multiplier,
            "flags": qa.flags,
            "reason": qa.reason,
        },
    ))

    # Always emit provenance
    packets.append(_make_packet(
        SENTINEL1_PROVENANCE,
        metadata,
        provenance if provenance else {
            "scene_id": metadata.scene_id,
            "product_id": metadata.product_id,
            "processing_level": metadata.processing_level,
            "instrument_mode": metadata.instrument_mode,
            "polarization": metadata.polarization,
            "platform": metadata.platform,
            "sar_version": metadata.sar_version,
            "qa_version": metadata.qa_version,
            "feature_version": metadata.feature_version,
        },
    ))

    # UNUSABLE → stop here
    if not qa.usable:
        return packets

    # Plot backscatter
    if plot_summary is not None:
        packets.append(_make_packet(
            SENTINEL1_PLOT_BACKSCATTER,
            metadata,
            {
                "vv_db_mean": plot_summary.vv_db_mean,
                "vv_db_std": plot_summary.vv_db_std,
                "vv_db_p10": plot_summary.vv_db_p10,
                "vv_db_p90": plot_summary.vv_db_p90,
                "vh_db_mean": plot_summary.vh_db_mean,
                "vh_db_std": plot_summary.vh_db_std,
                "vh_db_p10": plot_summary.vh_db_p10,
                "vh_db_p90": plot_summary.vh_db_p90,
                "vv_vh_ratio_mean": plot_summary.vv_vh_ratio_mean,
                "rvi_mean": plot_summary.rvi_mean,
                "span_mean": plot_summary.span_mean,
                "heterogeneity_score": plot_summary.heterogeneity_score,
                "valid_fraction": plot_summary.valid_fraction,
            },
        ))

    # Zone backscatter
    if zone_summaries:
        zone_payloads = []
        for zs in zone_summaries:
            zone_payloads.append({
                "zone_id": zs.zone_id,
                "zone_source": zs.zone_source,
                "area_fraction": zs.area_fraction,
                "valid_fraction": zs.valid_fraction,
                "border_noise_fraction": zs.border_noise_fraction,
                "low_signal_fraction": zs.low_signal_fraction,
                "reliability": zs.reliability,
                "sigma_multiplier": zs.sigma_multiplier,
                "vv_db_mean": zs.vv_db_mean,
                "vh_db_mean": zs.vh_db_mean,
                "vv_vh_ratio_mean": zs.vv_vh_ratio_mean,
                "rvi_mean": zs.rvi_mean,
            })
        packets.append(_make_packet(
            SENTINEL1_ZONE_BACKSCATTER,
            metadata,
            {"zones": zone_payloads},
        ))

    # Derived features (moisture/structure/flood/roughness)
    if plot_summary is not None:
        packets.append(_make_packet(
            SENTINEL1_DERIVED_FEATURES,
            metadata,
            {
                "surface_wetness_proxy_mean": plot_summary.surface_wetness_proxy_mean,
                "structure_proxy_mean": plot_summary.structure_proxy_mean,
                "flood_score": plot_summary.flood_score,
                "roughness_proxy": plot_summary.roughness_proxy,
                "cross_pol_fraction_mean": plot_summary.cross_pol_fraction_mean,
                "vv_minus_vh_db_mean": plot_summary.vv_minus_vh_db_mean,
                "not_calibrated_soil_moisture": True,
                "features_computed": feature_names_computed or [],
            },
        ))

    # Raster stack ref
    if raster_refs:
        packets.append(_make_packet(
            SENTINEL1_RASTER_STACK_REF,
            metadata,
            {"raster_refs": raster_refs},
        ))

    return packets
