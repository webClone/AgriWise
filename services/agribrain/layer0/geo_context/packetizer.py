"""
Geo Context Packetizer.

Emits ObservationPacket objects from geo context analysis.
All-fail rule: provenance + diagnostics only.

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
from services.agribrain.layer0.geo_context.dem.schemas import DEMContext
from services.agribrain.layer0.geo_context.landcover.schemas import LandCoverContext
from services.agribrain.layer0.geo_context.wapor.schemas import WaPORContext
from services.agribrain.layer0.geo_context.schemas import (
    PlotValidityAssessment,
    SensorPlacementGuidance,
    SatelliteTrustModifiers,
)


# Packet type constants (preserved for payload identification)
DEM_TERRAIN_CONTEXT = "DEM_TERRAIN_CONTEXT"
DEM_DRAINAGE_CONTEXT = "DEM_DRAINAGE_CONTEXT"
DEM_SENSOR_PLACEMENT_GUIDANCE = "DEM_SENSOR_PLACEMENT_GUIDANCE"
LANDCOVER_BASELINE_CONTEXT = "LANDCOVER_BASELINE_CONTEXT"
LANDCOVER_DYNAMIC_CONTEXT = "LANDCOVER_DYNAMIC_CONTEXT"
LANDCOVER_BOUNDARY_CONTAMINATION = "LANDCOVER_BOUNDARY_CONTAMINATION"
PLOT_VALIDITY_CONTEXT = "PLOT_VALIDITY_CONTEXT"
WAPOR_WATER_PRODUCTIVITY_CONTEXT = "WAPOR_WATER_PRODUCTIVITY_CONTEXT"
WAPOR_ET_BIOMASS_CONTEXT = "WAPOR_ET_BIOMASS_CONTEXT"
GEO_CONTEXT_PROVENANCE = "GEO_CONTEXT_PROVENANCE"
GEO_CONTEXT_DIAGNOSTICS = "GEO_CONTEXT_DIAGNOSTICS"


def _build_provenance(prov_dict: Optional[Dict[str, Any]] = None) -> Provenance:
    """Build provenance from geo context metadata."""
    return Provenance(
        processing_chain=["geo_context_v1"],
        software_version="agriwise-geocontext-v1",
        source_url="",
        license="mixed",
    )


def _make_packet(
    packet_type: str,
    payload: Dict[str, Any],
    source: ObservationSource = ObservationSource.GEO_CONTEXT,
    data_status: DataStatus = DataStatus.OBSERVED,
    plot_id: str = "",
    geometry_hash: str = "",
    geometry_version: Optional[int] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> ObservationPacket:
    """Create a standardized ObservationPacket for geo context data."""
    prov = _build_provenance(provenance)

    return ObservationPacket(
        source=source,
        obs_type=ObservationType.TABULAR,
        timestamp=datetime.now(timezone.utc),
        payload={"packet_type": packet_type, **payload},
        qa=QAMetadata(flags=[QAFlag.CLEAN]),
        provenance=prov,
        data_status=data_status,
        plot_id=plot_id,
        geometry_hash=geometry_hash,
        geometry_version=geometry_version,
        spatial_scope="plot",
    )


def emit_geo_context_packets(
    dem: Optional[DEMContext] = None,
    landcover: Optional[LandCoverContext] = None,
    wapor: Optional[WaPORContext] = None,
    sensor_placement: Optional[SensorPlacementGuidance] = None,
    plot_validity: Optional[PlotValidityAssessment] = None,
    satellite_trust: Optional[SatelliteTrustModifiers] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
    plot_id: str = "",
    geometry_hash: str = "",
    geometry_version: Optional[int] = None,
) -> List[ObservationPacket]:
    """Emit geo context ObservationPackets.

    All-fail rule: if all sources are None, emit only provenance + diagnostics.
    """
    packets: List[ObservationPacket] = []
    all_failed = dem is None and landcover is None and (wapor is None or not wapor.wapor_available)

    common = dict(
        plot_id=plot_id,
        geometry_hash=geometry_hash,
        geometry_version=geometry_version,
        provenance=provenance,
    )

    # Always emit provenance
    packets.append(_make_packet(
        GEO_CONTEXT_PROVENANCE,
        provenance or {"status": "all_failed" if all_failed else "partial_or_complete"},
        **common,
    ))

    # Always emit diagnostics
    packets.append(_make_packet(
        GEO_CONTEXT_DIAGNOSTICS,
        diagnostics or {},
        **common,
    ))

    if all_failed:
        return packets  # Only audit packets

    # DEM packets — source=DEM for terrain-specific data
    if dem is not None:
        packets.append(_make_packet(DEM_TERRAIN_CONTEXT, {
            "elevation_mean": dem.elevation_mean,
            "elevation_range": (dem.elevation_max or 0) - (dem.elevation_min or 0) if dem.elevation_min is not None else None,
            "slope_mean": dem.slope_mean,
            "slope_p90": dem.slope_p90,
            "aspect_dominant": dem.aspect_dominant,
            "runoff_risk_score": dem.runoff_risk_score,
            "erosion_risk_score": dem.erosion_risk_score,
            "source": dem.source,
            "resolution_m": dem.resolution_m,
        }, source=ObservationSource.DEM, **common))

        packets.append(_make_packet(DEM_DRAINAGE_CONTEXT, {
            "topographic_wetness_proxy": dem.topographic_wetness_proxy,
            "low_spot_fraction": dem.low_spot_fraction,
            "cold_air_pooling_risk": dem.cold_air_pooling_risk,
            "irrigation_uniformity_risk": dem.irrigation_uniformity_risk,
        }, source=ObservationSource.DEM,
           data_status=DataStatus.ESTIMATED,
           **common))

    # Sensor placement packet (from DEM + landcover)
    if sensor_placement is not None and sensor_placement.recommended_zones:
        packets.append(_make_packet(DEM_SENSOR_PLACEMENT_GUIDANCE, {
            "recommended": [{
                "zone_id": z.zone_id,
                "sensor_type": z.sensor_type,
                "placement_confidence": z.placement_confidence,
                "representativeness_scope": z.representativeness_scope,
                "recommended_depths_cm": z.recommended_depths_cm,
                "reason_codes": z.reason_codes,
                "source_drivers": z.source_drivers,
            } for z in sensor_placement.recommended_zones],
            "avoid": [{
                "zone_id": z.zone_id,
                "reason_codes": z.reason_codes,
            } for z in sensor_placement.avoid_zones],
            "reasoning": sensor_placement.reasoning,
        }, source=ObservationSource.DEM,
           data_status=DataStatus.ESTIMATED,
           **common))

    # Land cover packets — source=LANDCOVER
    if landcover is not None:
        if landcover.worldcover is not None:
            wc = landcover.worldcover
            packets.append(_make_packet(LANDCOVER_BASELINE_CONTEXT, {
                "cropland_fraction": wc.cropland_fraction,
                "non_ag_fraction": wc.non_ag_fraction,
                "majority_class": wc.landcover_majority_class,
                "purity_score": wc.landcover_purity_score,
                "confidence": wc.landcover_confidence,
                "unknown_fraction": wc.unknown_fraction,
                "valid_fraction": wc.landcover_valid_fraction,
            }, source=ObservationSource.LANDCOVER, **common))

        if landcover.dynamic_world is not None:
            dw = landcover.dynamic_world
            packets.append(_make_packet(LANDCOVER_DYNAMIC_CONTEXT, {
                "crop_probability": dw.crop_probability_mean,
                "tree_probability": dw.tree_probability_mean,
                "entropy": dw.class_entropy,
                "confidence": dw.dynamic_landcover_confidence,
                "non_crop_alert": dw.recent_non_crop_alert,
            }, source=ObservationSource.LANDCOVER, **common))

        if landcover.contamination is not None:
            c = landcover.contamination
            packets.append(_make_packet(LANDCOVER_BOUNDARY_CONTAMINATION, {
                "tree_edge_contamination": c.tree_edge_contamination_score,
                "water_contamination": c.water_edge_contamination_score,
                "builtup_contamination": c.builtup_edge_contamination_score,
                "boundary_mismatch": c.boundary_mismatch_score,
                "flags": c.flags,
            }, source=ObservationSource.LANDCOVER, **common))

    # Plot validity (always if any source available)
    if plot_validity is not None:
        packets.append(_make_packet(PLOT_VALIDITY_CONTEXT, {
            "cropland_confidence": plot_validity.cropland_confidence,
            "non_ag_contamination": plot_validity.non_ag_contamination_score,
            "boundary_mismatch": plot_validity.boundary_mismatch_score,
            "water_contamination": plot_validity.water_contamination_score,
            "tree_edge_contamination": plot_validity.tree_edge_contamination_score,
            "flags": plot_validity.flags,
        }, **common))

    # WaPOR packets — source=WAPOR
    if wapor is not None and wapor.wapor_available:
        packets.append(_make_packet(WAPOR_WATER_PRODUCTIVITY_CONTEXT, {
            "water_productivity_score": wapor.water_productivity_score,
            "land_productivity_score": wapor.land_productivity_score,
            "irrigation_performance_proxy": wapor.irrigation_performance_proxy,
            "confidence": wapor.wapor_confidence,
            "level": wapor.wapor_level,
        }, source=ObservationSource.WAPOR, **common))

        packets.append(_make_packet(WAPOR_ET_BIOMASS_CONTEXT, {
            "actual_et_10d": wapor.actual_et_10d,
            "reference_et_10d": wapor.reference_et_10d,
            "et_ratio": wapor.et_ratio,
            "biomass_trend": wapor.biomass_trend,
        }, source=ObservationSource.WAPOR, **common))

    return packets
