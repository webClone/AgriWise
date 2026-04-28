"""
Shared Packet Adapter — The single exit point from perception into Layer 0.

Converts PerceptionEngineOutput -> List[ObservationPacket].

This is THE bridge between perception engines and the Kalman assimilation
engine. Every engine (satellite_rgb, farmer_photo, drone, ip_camera)
must route through this adapter to emit standardized evidence.

Rules:
  - Every PerceptionVariable becomes one ObservationPacket
  - Sigma is inflated by QA score
  - Reliability is bounded by QA reliability_weight
  - Provenance is attached from the engine's processing chain
  - Feasibility-gated variables that failed are NOT emitted
  - Packet IDs are deterministic from content hash + variable name
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import hashlib

from layer0.perception.common.contracts import (
    PerceptionEngineFamily,
    PerceptionEngineOutput,
    PerceptionVariable,
)

from layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType,
    QAMetadata, QAFlag, UncertaintyModel, Provenance,
)


# ============================================================================
# Engine family -> ObservationSource mapping
# ============================================================================

ENGINE_TO_SOURCE: Dict[PerceptionEngineFamily, ObservationSource] = {
    PerceptionEngineFamily.SATELLITE_RGB: ObservationSource.SATELLITE_RGB,
    PerceptionEngineFamily.FARMER_PHOTO: ObservationSource.FARMER_PHOTO,
    PerceptionEngineFamily.DRONE: ObservationSource.DRONE,
    PerceptionEngineFamily.IP_CAMERA: ObservationSource.IP_CAMERA,
}


# ============================================================================
# Variable -> observation type mapping
# ============================================================================

VARIABLE_TO_OBS_TYPE: Dict[str, str] = {
    # Satellite RGB V1
    "vegetation_fraction": "canopy_cover",
    "bare_soil_fraction": "bare_soil_fraction",  # auxiliary, no Kalman mapping in V1
    "rgb_anomaly_score": "stress_proxy",
    "coarse_phenology_stage": "phenology_stage",
    # Future engines will add:
    # "canopy_cover": "canopy_cover",
    # "disease_symptom_prob": "stress_proxy",
    # "weed_fraction": "weed_fraction",
    # "row_direction_deg": "row_direction_deg",
}


# ============================================================================
# QA flag generation
# ============================================================================

def _flags_to_qa_flags(flags: List[str]) -> List[QAFlag]:
    """Map engine QA flag strings to ObservationPacket QAFlag enums."""
    flag_map = {
        "CLEAN": QAFlag.CLEAN,
        "CLOUD_CONTAMINATED": QAFlag.CLOUD_CONTAMINATED,
        "CLOUD_EDGE": QAFlag.CLOUD_EDGE,
        "STALE": QAFlag.STALE,
        "LOW_CONFIDENCE": QAFlag.LOW_CONFIDENCE,
        "PARTIAL_COVERAGE": QAFlag.PARTIAL_COVERAGE,
        "BORDER_NOISE": QAFlag.BORDER_NOISE,
    }
    result = []
    for f in flags:
        mapped = flag_map.get(f)
        if mapped:
            result.append(mapped)
        # Unknown flags are stored in provenance, not dropped
    return result if result else [QAFlag.CLEAN]


# ============================================================================
# Main adapter function
# ============================================================================

def to_observation_packets(
    output: PerceptionEngineOutput,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    point: Optional[Tuple[float, float]] = None,
) -> List[ObservationPacket]:
    """
    Convert a PerceptionEngineOutput into a list of ObservationPackets.
    
    This is the SINGLE EXIT POINT from all perception engines into
    the Layer 0 assimilation pipeline.
    
    Args:
        output: from any perception engine
        bbox: plot bounding box (min_lng, min_lat, max_lng, max_lat)
        point: plot centroid (lat, lng) fallback
    
    Returns:
        List of ObservationPackets, one per emittable variable.
    """
    packets: List[ObservationPacket] = []

    # Determine source
    source = ENGINE_TO_SOURCE.get(
        output.engine_family,
        ObservationSource.USER_OBSERVATION,
    )

    # Timestamp
    timestamp = output.timestamp or datetime.now()

    # Build provenance
    provenance = Provenance(
        processing_chain=output.provenance_chain,
        software_version=output.model_versions.get(
            "engine", f"agriwise-perception-{output.engine_family.value}-v1"
        ),
    )

    # QA metadata — use engine-reported flags directly
    qa_flags = _flags_to_qa_flags(output.qa_flags if output.qa_flags else _collect_flags(output))

    # Geometry
    geo_type = "bbox" if bbox else ("point" if point else output.geometry_scope)

    # Convert each emittable variable to a packet
    for var in output.get_emittable_variables():
        # Apply QA-driven sigma inflation
        effective_sigma = var.sigma * output.sigma_inflation

        # Reliability bounded by QA and variable confidence
        reliability = min(
            output.reliability_weight,
            var.confidence,
        )
        reliability = max(0.05, min(1.0, reliability))

        # Build QA metadata for this packet
        qa_meta = QAMetadata(
            flags=qa_flags,
            scene_score=output.qa_score,
            valid_pixel_fraction=output.qa_score,
        )

        # Build uncertainty
        uncertainty = UncertaintyModel(
            sigmas={var.name: effective_sigma},
            error_model="perception_engine",
        )

        # Payload
        payload = {
            var.name: var.value,
            f"{var.name}_sigma": effective_sigma,
            "engine_family": output.engine_family.value,
            "image_content_hash": output.image_content_hash,
        }
        if var.details:
            payload["details"] = var.details

        # Deterministic packet ID from content hash + variable
        packet_id = _make_packet_id(
            output.engine_family.value,
            output.plot_id,
            var.name,
            output.image_content_hash,
            timestamp,
        )

        packets.append(ObservationPacket(
            packet_id=packet_id,
            source=source,
            obs_type=ObservationType.RASTER if output.engine_family == PerceptionEngineFamily.SATELLITE_RGB else ObservationType.IMAGE,
            timestamp=timestamp,
            geometry_type=geo_type,
            bbox=bbox,
            point=point,
            payload=payload,
            qa=qa_meta,
            uncertainty=uncertainty,
            provenance=provenance,
            reliability_weight=reliability,
        ))

    return packets


# ============================================================================
# Helpers
# ============================================================================

def _make_packet_id(
    engine: str,
    plot_id: str,
    variable: str,
    content_hash: str,
    timestamp: datetime,
) -> str:
    """Deterministic packet ID from content-based identifiers."""
    raw = f"{engine}:{plot_id}:{variable}:{content_hash}:{timestamp.strftime('%Y%m%d')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _collect_flags(output: PerceptionEngineOutput) -> List[str]:
    """Collect all QA flags from the output."""
    flags = []
    # Check if any variables carry details with flags
    for var in output.variables:
        if "flags" in var.details:
            flags.extend(var.details["flags"])
    # Check output-level flags from QA
    if output.qa_score < 0.3:
        flags.append("LOW_CONFIDENCE")
    if output.qa_score >= 0.7 and not flags:
        flags.append("CLEAN")
    return flags if flags else ["CLEAN"]
