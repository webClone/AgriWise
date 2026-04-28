"""
Sentinel-2 Packetizer — Converts ScenePackage into ObservationPacket family.

5 packet types in V1:
  SENTINEL2_SCENE_QA       — always emitted (even UNUSABLE)
  SENTINEL2_PROVENANCE     — always emitted (even UNUSABLE)
  SENTINEL2_PLOT_INDICES   — only if usable
  SENTINEL2_ZONE_INDICES   — only if usable
  SENTINEL2_RASTER_STACK_REF — raster references, only if usable
"""

from __future__ import annotations

from typing import Any, Dict, List

from layer0.observation_packet import (
    ObservationPacket,
    ObservationSource,
    ObservationType,
    Provenance,
    QAMetadata,
    QAFlag,
    UncertaintyModel,
)
from layer0.sentinel2.schemas import Sentinel2ScenePackage


# Base uncertainty sigmas per index
INDEX_SIGMAS = {
    "ndvi": 0.025,
    "evi": 0.035,
    "ndmi": 0.045,
    "ndre": 0.060,
    "bsi": 0.080,
}


def _build_provenance(pkg: Sentinel2ScenePackage) -> Provenance:
    """Build provenance from scene metadata."""
    meta = pkg.metadata
    return Provenance(
        processing_chain=[
            f"sentinel2_l2a_{meta.processing_level}",
            f"qa_{meta.qa_version}",
            f"idx_{meta.index_version}",
        ],
        software_version="agriwise-sentinel2-v1",
        source_url=meta.provider,
        license="copernicus-open",
    )


def _build_qa_metadata(pkg: Sentinel2ScenePackage) -> QAMetadata:
    """Build QA metadata from scene QA result."""
    qa = pkg.qa
    flags = []
    if qa.cloud_fraction > 0.10:
        flags.append(QAFlag.CLOUD_CONTAMINATED)
    if qa.shadow_fraction > 0.10:
        flags.append(QAFlag.CLOUD_EDGE)
    if qa.valid_fraction < 0.70:
        flags.append(QAFlag.PARTIAL_COVERAGE)
    if not flags:
        flags.append(QAFlag.CLEAN)

    return QAMetadata(
        flags=flags,
        cloud_probability=qa.cloud_fraction,
        shadow_probability=qa.shadow_fraction,
        valid_pixel_fraction=qa.valid_fraction,
        scene_score=qa.overall_score,
    )


def packetize(pkg: Sentinel2ScenePackage) -> List[ObservationPacket]:
    """
    Convert a Sentinel2ScenePackage into ObservationPackets.

    UNUSABLE scenes emit QA + PROVENANCE only (zero index packets).
    """
    packets: List[ObservationPacket] = []
    meta = pkg.metadata
    prov = _build_provenance(pkg)
    qa_meta = _build_qa_metadata(pkg)
    ts = meta.acquisition_datetime

    # ---- 1. SENTINEL2_SCENE_QA (always emitted) ----
    packets.append(ObservationPacket(
        source=ObservationSource.SENTINEL2,
        obs_type=ObservationType.TABULAR,
        timestamp=ts,
        payload={
            "packet_type": "SENTINEL2_SCENE_QA",
            "scene_id": meta.scene_id,
            "usable": pkg.qa.usable,
            "quality_class": pkg.qa.quality_class.value,
            "valid_fraction": pkg.qa.valid_fraction,
            "cloud_fraction": pkg.qa.cloud_fraction,
            "shadow_fraction": pkg.qa.shadow_fraction,
            "snow_fraction": pkg.qa.snow_fraction,
            "reliability_weight": pkg.qa.reliability_weight,
            "sigma_multiplier": pkg.qa.sigma_multiplier,
            "flags": pkg.qa.flags,
            "reason": pkg.qa.reason,
        },
        qa=qa_meta,
        provenance=prov,
        reliability_weight=pkg.qa.reliability_weight,
    ))

    # ---- 2. SENTINEL2_PROVENANCE (always emitted) ----
    packets.append(ObservationPacket(
        source=ObservationSource.SENTINEL2,
        obs_type=ObservationType.TABULAR,
        timestamp=ts,
        payload={
            "packet_type": "SENTINEL2_PROVENANCE",
            "scene_id": meta.scene_id,
            "product_id": meta.product_id,
            "provider": meta.provider,
            "processing_level": meta.processing_level,
            "band_list": meta.band_list,
            "scale": meta.scale,
            "qa_version": meta.qa_version,
            "index_version": meta.index_version,
            "plot_geometry_hash": meta.plot_geometry_hash,
            "grid_alignment_hash": meta.grid_alignment_hash,
        },
        qa=qa_meta,
        provenance=prov,
        reliability_weight=pkg.qa.reliability_weight,
    ))

    # Stop here for unusable scenes
    if not pkg.qa.usable:
        return packets

    summary = pkg.plot_summary
    sigma_mult = pkg.qa.sigma_multiplier

    # ---- 3. SENTINEL2_PLOT_INDICES (usable only) ----
    index_payload: Dict[str, Any] = {"packet_type": "SENTINEL2_PLOT_INDICES"}
    sigmas: Dict[str, float] = {}

    for idx_name, attr_mean, attr_std in [
        ("ndvi", "ndvi_mean", "ndvi_std"),
        ("evi", "evi_mean", "evi_std"),
        ("ndmi", "ndmi_mean", "ndmi_std"),
        ("ndre", "ndre_mean", "ndre_std"),
        ("bsi", "bsi_mean", "bsi_std"),
    ]:
        mean_val = getattr(summary, attr_mean, None)
        if mean_val is not None:
            index_payload[f"{idx_name}_mean"] = mean_val
            std_val = getattr(summary, attr_std, None)
            if std_val is not None:
                index_payload[f"{idx_name}_std"] = std_val
            sigmas[idx_name] = INDEX_SIGMAS.get(idx_name, 0.05) * sigma_mult

    index_payload["valid_fraction"] = summary.valid_fraction
    index_payload["cloud_fraction"] = summary.cloud_fraction

    packets.append(ObservationPacket(
        source=ObservationSource.SENTINEL2,
        obs_type=ObservationType.TABULAR,
        timestamp=ts,
        payload=index_payload,
        qa=qa_meta,
        uncertainty=UncertaintyModel(sigmas=sigmas),
        provenance=prov,
        reliability_weight=pkg.qa.reliability_weight,
    ))

    # ---- 4. SENTINEL2_ZONE_INDICES (usable only) ----
    for zs in pkg.zone_summaries:
        zone_payload: Dict[str, Any] = {
            "packet_type": "SENTINEL2_ZONE_INDICES",
            "zone_id": zs.zone_id,
            "zone_source": zs.zone_source,
            "zone_confidence": zs.zone_confidence,
        }
        for attr in ["ndvi_mean", "ndmi_mean", "ndre_mean", "bsi_mean",
                      "valid_fraction", "cloud_fraction"]:
            val = getattr(zs, attr, None)
            if val is not None:
                zone_payload[attr] = val

        packets.append(ObservationPacket(
            source=ObservationSource.SENTINEL2,
            obs_type=ObservationType.TABULAR,
            timestamp=ts,
            payload=zone_payload,
            qa=qa_meta,
            uncertainty=UncertaintyModel(sigmas={
                k: v * sigma_mult for k, v in INDEX_SIGMAS.items()
            }),
            provenance=prov,
            reliability_weight=zs.reliability,
        ))

    # ---- 5. SENTINEL2_RASTER_STACK_REF (usable only) ----
    raster_refs: Dict[str, str] = {}
    for idx_name, raster in pkg.indices.items():
        if raster.content_hash:
            raster_refs[idx_name] = raster.content_hash
        elif raster.raster_ref:
            raster_refs[idx_name] = raster.raster_ref

    if raster_refs:
        packets.append(ObservationPacket(
            source=ObservationSource.SENTINEL2,
            obs_type=ObservationType.RASTER,
            timestamp=ts,
            payload={
                "packet_type": "SENTINEL2_RASTER_STACK_REF",
                "index_refs": raster_refs,
                "grid_shape": list(next(iter(pkg.indices.values())).grid_shape) if pkg.indices else [],
                "crs": meta.crs,
            },
            qa=qa_meta,
            provenance=prov,
            reliability_weight=pkg.qa.reliability_weight,
        ))

    return packets
