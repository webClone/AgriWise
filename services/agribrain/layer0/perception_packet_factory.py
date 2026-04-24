"""
Layer 0.9: Perception Packet Factory — Image → ObservationPacket

⚠️  LEGACY MODULE — Deprecated in favor of engine-specific pipelines.
    See: services/agribrain/layer0/perception/satellite_rgb/engine.py
         services/agribrain/layer0/perception/farmer_photo/  (planned)
         services/agribrain/layer0/perception/drone/          (planned)
         services/agribrain/layer0/perception/ip_camera/      (planned)

    This generic path is preserved for backward compatibility during
    migration. Do not add new logic here. New perception features
    should be implemented in the appropriate engine module.

Original pipeline:
  1. Receive image metadata + optional pixel stats
  2. Run ImageQA gating
  3. Run perception models (canopy, phenology, disease, weed)
  4. Package results as ObservationPackets with uncertainty + reliability

Never emits raw ML outputs. Always wraps them in the universal
ObservationPacket schema with QA-adjusted sigma and reliability.
"""

from __future__ import annotations

__legacy__ = True  # This module is deprecated — use engine-specific pipelines
from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib

from .image_qa import ImageQAEngine, ImageQAResult
from .perception_models.inference import (
    CanopyCoverModel, PhenologyStageModel,
    DiseaseSymptomModel, DroneWeedRowModel, PerceptionOutput
)
from .observation_packet import (
    ObservationPacket, ObservationSource, ObservationType,
    QAMetadata, QAFlag, UncertaintyModel, Provenance
)


class PerceptionPacketFactory:
    """
    Converts raw image inputs into ObservationPackets.
    
    Orchestrates: ImageQA → perception models → packet creation.
    Each packet flows through the same pipeline as satellite observations.
    """
    
    def __init__(self):
        self.qa_engine = ImageQAEngine()
        self._inference_cache: Dict[str, List[ObservationPacket]] = {}
    
    def process_image(
        self,
        image_metadata: Dict[str, Any],
        plot_context: Optional[Dict[str, Any]] = None,
        run_models: Optional[List[str]] = None,
    ) -> List[ObservationPacket]:
        """
        Full pipeline: QA → inference → packets.
        
        Args:
            image_metadata: see ImageQAEngine.assess() for schema
            plot_context: {lat, lng, area_ha, current_date, plot_id}
            run_models: which models to run ["canopy", "phenology", "disease", "drone"]
                        None = auto-select based on source_type
        
        Returns:
            List of ObservationPackets (one per extracted variable).
        """
        source_type = image_metadata.get("source_type", "phone")
        
        # Auto-select models
        if run_models is None:
            if source_type in ("drone_ortho", "drone_frame"):
                run_models = ["canopy", "phenology", "disease", "drone"]
            else:
                run_models = ["canopy", "phenology", "disease"]
        
        # --- Step 1: QA gating ---
        qa_result = self.qa_engine.assess(image_metadata, plot_context)
        
        # --- Step 2: Check inference cache ---
        cache_key = qa_result.image_hash
        if cache_key in self._inference_cache:
            return self._inference_cache[cache_key]
        
        # --- Step 3: Run perception models ---
        pixel_stats = image_metadata.get("pixel_stats", {})
        perception_outputs: List[PerceptionOutput] = []
        
        if "canopy" in run_models and pixel_stats:
            perception_outputs.append(CanopyCoverModel.predict(pixel_stats))
        
        if "phenology" in run_models and pixel_stats:
            crop = image_metadata.get("crop_type", "wheat")
            perception_outputs.append(PhenologyStageModel.predict(pixel_stats, crop))
        
        if "disease" in run_models and pixel_stats:
            perception_outputs.append(DiseaseSymptomModel.predict(pixel_stats))
        
        drone_outputs = {}
        if "drone" in run_models and pixel_stats:
            drone_meta = image_metadata.get("drone", {})
            drone_outputs = DroneWeedRowModel.predict(pixel_stats, drone_meta)
            for po in drone_outputs.values():
                perception_outputs.append(po)
        
        # --- Step 4: Convert to ObservationPackets ---
        packets = []
        for po in perception_outputs:
            packet = self._to_observation_packet(
                po, qa_result, image_metadata, plot_context
            )
            packets.append(packet)
        
        # Cache results
        self._inference_cache[cache_key] = packets
        
        return packets
    
    def _to_observation_packet(
        self,
        output: PerceptionOutput,
        qa: ImageQAResult,
        meta: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> ObservationPacket:
        """Convert one perception output into an ObservationPacket."""
        
        # Source mapping — use actual ObservationSource enum values
        source_map = {
            "phone": ObservationSource.USER_OBSERVATION,
            "ip_camera": ObservationSource.IP_CAMERA,
            "drone_ortho": ObservationSource.DRONE,
            "drone_frame": ObservationSource.DRONE,
        }
        source = source_map.get(meta.get("source_type", ""), ObservationSource.USER_OBSERVATION)
        
        # Timestamp
        ts = meta.get("timestamp", datetime.now().isoformat())
        try:
            timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            timestamp = datetime.now()
        
        # Build QA metadata — use QAFlag enum values and scene_score
        qa_flags = []
        if qa.overall_score < 0.5:
            qa_flags.append(QAFlag.LOW_CONFIDENCE)
        
        qa_meta = QAMetadata(
            flags=qa_flags,
            scene_score=qa.overall_score,
        )
        # Store extra details in valid_pixel_fraction
        qa_meta.valid_pixel_fraction = qa.overall_score
        
        # Build uncertainty — sigma inflated by QA
        effective_sigma = output.sigma * qa.sigma_inflation
        uncertainty = UncertaintyModel(
            sigmas={output.variable: effective_sigma},
            error_model="perception_heuristic",
        )
        
        # Build provenance — use processing_chain (correct field name)
        provenance = Provenance(
            processing_chain=[
                f"image_qa:{qa.source_type}",
                f"model:{output.model_version}",
                f"qa_score:{qa.overall_score:.2f}",
            ],
            software_version=output.model_version,
        )
        
        # Reliability: combine QA reliability with model confidence
        reliability = qa.reliability_weight * output.confidence
        reliability = max(0.05, min(1.0, reliability))
        
        # Geometry
        geometry = {}
        geo_type = "plot"
        point_val = None
        if meta.get("gps_lat") is not None:
            geo_type = "point"
            point_val = (meta["gps_lat"], meta["gps_lng"])
        elif context and "lat" in context:
            geo_type = "point"
            point_val = (context["lat"], context["lng"])
        
        # Payload
        payload = {
            output.variable: output.value,
            f"{output.variable}_sigma": effective_sigma,
            "model_details": output.details,
            "image_hash": qa.image_hash,
        }
        
        packet_id = f"perception_{output.variable}_{qa.image_hash}_{timestamp.strftime('%Y%m%d')}"
        
        return ObservationPacket(
            packet_id=packet_id,
            source=source,
            obs_type=ObservationType.IMAGE,
            timestamp=timestamp,
            geometry_type=geo_type,
            point=point_val,
            payload=payload,
            qa=qa_meta,
            uncertainty=uncertainty,
            provenance=provenance,
            reliability_weight=reliability,
        )
    
    def clear_cache(self) -> None:
        """Clear inference cache."""
        self._inference_cache.clear()
