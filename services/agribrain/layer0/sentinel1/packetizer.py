"""
Sentinel-1 SAR Packetizer.

Emits standardized ObservationPacket objects from a Sentinel1ScenePackage.
UNUSABLE scenes emit QA + PROVENANCE only.

V2: Converted from dict packets to canonical ObservationPacket objects
    to unify the Layer 0 output contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.agribrain.layer0.observation_packet import (
    ObservationPacket,
    ObservationSource,
    ObservationType,
    DataStatus,
    Provenance,
    QAMetadata,
    QAFlag,
    UncertaintyModel,
)
from services.agribrain.layer0.sentinel1.schemas import (
    SARQualityClass,
    Sentinel1PlotSummary,
    Sentinel1QAResult,
    Sentinel1SceneMetadata,
    Sentinel1ZoneSummary,
)


# Packet type constants (preserved for payload identification)
SENTINEL1_SCENE_QA = "SENTINEL1_SCENE_QA"
SENTINEL1_PROVENANCE = "SENTINEL1_PROVENANCE"
SENTINEL1_PLOT_BACKSCATTER = "SENTINEL1_PLOT_BACKSCATTER"
SENTINEL1_ZONE_BACKSCATTER = "SENTINEL1_ZONE_BACKSCATTER"
SENTINEL1_DERIVED_FEATURES = "SENTINEL1_DERIVED_FEATURES"
SENTINEL1_RASTER_STACK_REF = "SENTINEL1_RASTER_STACK_REF"

# Base uncertainty sigmas for SAR features (dB)
SAR_SIGMAS = {
    "vv_db": 1.5,
    "vh_db": 2.0,
    "vv_vh_ratio": 0.3,
    "rvi": 0.05,
    "surface_wetness_proxy": 0.08,
    "structure_proxy": 0.06,
}


def _build_provenance(metadata: Sentinel1SceneMetadata) -> Provenance:
    """Build provenance from SAR scene metadata."""
    return Provenance(
        processing_chain=[
            f"sentinel1_grd_{metadata.processing_level}",
            f"sar_{metadata.sar_version}",
            f"qa_{metadata.qa_version}",
            f"feat_{metadata.feature_version}",
        ],
        software_version="agriwise-sentinel1-v1",
        source_url=metadata.provider if hasattr(metadata, 'provider') else "",
        license="copernicus-open",
    )


def _build_qa_metadata(qa: Sentinel1QAResult, metadata: Sentinel1SceneMetadata) -> QAMetadata:
    """Build QA metadata from SAR QA result."""
    flags = []
    if qa.border_noise_fraction > 0.10:
        flags.append(QAFlag.BORDER_NOISE)
    if qa.valid_fraction < 0.70:
        flags.append(QAFlag.PARTIAL_COVERAGE)
    if qa.incidence_angle_mean and qa.incidence_angle_mean > 40:
        flags.append(QAFlag.HIGH_INCIDENCE_ANGLE)
    if not flags:
        flags.append(QAFlag.CLEAN)

    return QAMetadata(
        flags=flags,
        valid_pixel_fraction=qa.valid_fraction,
        incidence_angle=qa.incidence_angle_mean,
        orbit_direction=metadata.orbit_direction,
        relative_orbit=metadata.relative_orbit,
        scene_score=qa.reliability_weight,
    )


def emit_sar_packets(
    metadata: Sentinel1SceneMetadata,
    qa: Sentinel1QAResult,
    plot_summary: Optional[Sentinel1PlotSummary],
    zone_summaries: Optional[List[Sentinel1ZoneSummary]],
    feature_names_computed: Optional[List[str]] = None,
    raster_refs: Optional[Dict[str, str]] = None,
    provenance: Optional[Dict[str, Any]] = None,
    plot_id: str = "",
    geometry_hash: str = "",
    geometry_version: Optional[int] = None,
) -> List[ObservationPacket]:
    """
    Emit ObservationPacket objects from SAR scene results.

    UNUSABLE → QA + PROVENANCE only.
    Usable → all 6 packet types.
    """
    packets: List[ObservationPacket] = []
    prov = _build_provenance(metadata)
    qa_meta = _build_qa_metadata(qa, metadata)
    ts = metadata.acquisition_datetime

    # Resolve plot_id and geometry_hash (do not conflate them)
    _plot_id = plot_id or getattr(metadata, 'plot_id', '') or ""
    _geom_hash = geometry_hash or getattr(metadata, 'plot_geometry_hash', '') or ""

    # Common kwargs for all packets
    common = dict(
        source=ObservationSource.SENTINEL1,
        obs_type=ObservationType.TABULAR,
        timestamp=ts,
        qa=qa_meta,
        provenance=prov,
        reliability_weight=qa.reliability_weight,
        data_status=DataStatus.OBSERVED,
        plot_id=_plot_id,
        geometry_hash=_geom_hash,
        geometry_version=geometry_version,
    )

    # ---- 1. SENTINEL1_SCENE_QA (always emitted) ----
    packets.append(ObservationPacket(
        **common,
        payload={
            "packet_type": SENTINEL1_SCENE_QA,
            "scene_id": metadata.scene_id,
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

    # ---- 2. SENTINEL1_PROVENANCE (always emitted) ----
    # Preserve SAR-specific metadata inside provenance
    sar_provenance = provenance if provenance else {
        "scene_id": metadata.scene_id,
        "product_id": metadata.product_id,
        "processing_level": metadata.processing_level,
        "instrument_mode": metadata.instrument_mode,
        "polarization": metadata.polarization,
        "platform": metadata.platform,
        "orbit_direction": metadata.orbit_direction,
        "relative_orbit": metadata.relative_orbit,
        "sar_version": metadata.sar_version,
        "qa_version": metadata.qa_version,
        "feature_version": metadata.feature_version,
    }
    packets.append(ObservationPacket(
        **common,
        payload={
            "packet_type": SENTINEL1_PROVENANCE,
            **sar_provenance,
        },
    ))

    # UNUSABLE → stop here
    if not qa.usable:
        return packets

    sigma_mult = qa.sigma_multiplier

    # ---- 3. SENTINEL1_PLOT_BACKSCATTER (usable only) ----
    if plot_summary is not None:
        packets.append(ObservationPacket(
            **common,
            payload={
                "packet_type": SENTINEL1_PLOT_BACKSCATTER,
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
            uncertainty=UncertaintyModel(sigmas={
                k: v * sigma_mult for k, v in SAR_SIGMAS.items()
            }),
        ))

    # ---- 4. SENTINEL1_ZONE_BACKSCATTER (usable only) ----
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
        packets.append(ObservationPacket(
            **common,
            spatial_scope="zone",
            payload={
                "packet_type": SENTINEL1_ZONE_BACKSCATTER,
                "zones": zone_payloads,
            },
        ))

    # ---- 5. SENTINEL1_DERIVED_FEATURES (usable only) ----
    if plot_summary is not None:
        packets.append(ObservationPacket(
            **common,
            payload={
                "packet_type": SENTINEL1_DERIVED_FEATURES,
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

    # ---- 6. SENTINEL1_RASTER_STACK_REF (usable only) ----
    if raster_refs:
        packets.append(ObservationPacket(
            **common,
            obs_type=ObservationType.RASTER,
            payload={
                "packet_type": SENTINEL1_RASTER_STACK_REF,
                "raster_refs": raster_refs,
            },
        ))

    return packets
