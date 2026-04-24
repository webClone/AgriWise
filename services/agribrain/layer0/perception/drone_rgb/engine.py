"""
Drone RGB Perception Engine.

Dual-mode Layer 0 perception engine for drone imagery.
1. Mapping Mode: Extracts structural features from orthomosaics.
2. Command/Revisit Mode: Routes low-altitude frames to Farmer Photo.
"""

from typing import Tuple, List, Optional
import logging

from .schemas import DroneRGBInput, DroneRGBOutput
from .qa import DroneQAOutput, evaluate_drone_qa
from .structural import DroneStructuralAnalyzer
from .packetizer import DronePacketizer

from ...observation_packet import ObservationPacket
from ..farmer_photo.engine import FarmerPhotoEngine
from ..farmer_photo.schemas import FarmerPhotoEngineInput
from ....drone_mission.schemas import FlightMode

logger = logging.getLogger(__name__)


class DroneRGBEngine:
    """The Layer 0 dual-mode drone engine."""
    
    def __init__(self):
        self.structural_analyzer = DroneStructuralAnalyzer()
        self.packetizer = DronePacketizer()
        self.farmer_photo_engine = FarmerPhotoEngine()
        
    def process_full(self, inp: DroneRGBInput) -> Tuple[Optional[DroneRGBOutput], List[ObservationPacket]]:
        """
        Process drone imagery and return structural outputs + observation packets.
        """
        # 1. Feasibility & Mode Split
        if inp.flight_mode == FlightMode.COMMAND_REVISIT_MODE:
            return self._process_command_mode(inp)
        elif inp.flight_mode == FlightMode.MAPPING_MODE:
            return self._process_mapping_mode(inp)
        else:
            logger.error(f"Unknown flight mode: {inp.flight_mode}")
            return None, []
            
    def _process_command_mode(self, inp: DroneRGBInput) -> Tuple[DroneRGBOutput, List[ObservationPacket]]:
        """Route low-altitude frames to Farmer Photo Engine."""
        out = DroneRGBOutput(plot_id=inp.plot_id, mission_id=inp.mission_id)
        packets: List[ObservationPacket] = []
        
        # In a real scenario, we'd loop over raw_frames_urls or synthetic_frame_pixels
        frames = inp.synthetic_frame_pixels if inp.synthetic_frame_pixels else []
        if not frames and inp.raw_frames_urls:
            frames = [{"url": url} for url in inp.raw_frames_urls] # Mock up for real urls
            
        out.routed_frame_count = len(frames)
        out.routed_to_farmer_photo = True
        
        for idx, frame_data in enumerate(frames):
            # Preserve Drone Provenance
            fp_inp = FarmerPhotoEngineInput(
                plot_id=inp.plot_id,
                image_ref=f"mock_drone_cmd_{inp.mission_id}_{idx}",
                user_label="drone_close_up",
                synthetic_pixels=frame_data if isinstance(frame_data, dict) and "red" in frame_data else None,
                # Here we pass the provenance via metadata or kwargs if supported, 
                # but FarmerPhotoEngineInput might not natively support all drone fields yet.
                # We encode it in the image_ref for traceability.
            )
            
            fp_result = self.farmer_photo_engine.process_full(fp_inp)
            if fp_result:
                _, fp_packets = fp_result
                # Optionally inject drone metadata into the packets before yielding them
                for packet in fp_packets:
                    if not isinstance(packet.payload, dict):
                        packet.payload = {}
                    packet.payload["capture_source"] = "drone"
                    packet.payload["mission_id"] = inp.mission_id
                    packet.payload["target_zone_id"] = inp.target_zone_id
                    packet.payload["commanded_altitude_m"] = inp.commanded_altitude_m
                
                packets.extend(fp_packets)
                
        # V1.5B: Aggregate multi-frame results into a hotspot summary
        if packets:
            from ....drone_mission.hotspot_summarizer import HotspotSummarizer
            summarizer = HotspotSummarizer()
            out.hotspot_summary = summarizer.summarize(
                packets,
                zone_id=inp.target_zone_id or inp.plot_id,
                mission_id=inp.mission_id,
            )
                
        return out, packets
        
    def _process_mapping_mode(self, inp: DroneRGBInput) -> Tuple[Optional[DroneRGBOutput], List[ObservationPacket]]:
        """Process full-plot structural orthomosaics.
        
        Accepts data from two sources:
        1. Photogrammetry subsystem (inp.orthomosaic_output) — primary
        2. Direct synthetic pixels (inp.synthetic_ortho_pixels) — benchmark fallback
        """
        # 0. Photogrammetry bridge: extract pixel data + metadata from
        #    OrthomosaicOutput if provided
        ortho_provenance = None
        if inp.orthomosaic_output is not None:
            ortho = inp.orthomosaic_output
            # Check usability — don't process unusable mosaics
            if hasattr(ortho, 'usable') and not ortho.usable:
                out = DroneRGBOutput(
                    plot_id=inp.plot_id,
                    mission_id=inp.mission_id,
                    is_valid=False,
                    qa_score=0.0,
                    rejection_reason=f"Photogrammetry mosaic unusable: {getattr(ortho, 'rejection_reason', 'unknown')}",
                )
                return out, []
            
            # Extract pixel data for structural analysis
            if hasattr(ortho, '_benchmark_pixels') and ortho._benchmark_pixels:
                inp.synthetic_ortho_pixels = ortho._benchmark_pixels
            
            # Extract metadata
            if hasattr(ortho, 'ground_resolution_cm'):
                inp.orthomosaic_metadata = inp.orthomosaic_metadata or {}
                inp.orthomosaic_metadata['achieved_gsd_cm'] = ortho.ground_resolution_cm
                inp.orthomosaic_metadata['coverage_completeness'] = getattr(ortho, 'coverage_completeness', 1.0)
                inp.orthomosaic_metadata['crs'] = getattr(ortho, 'crs', 'EPSG:4326')
            
            # Extract provenance for traceability
            if hasattr(ortho, 'provenance'):
                prov = ortho.provenance
                ortho_provenance = {
                    'pipeline_version': getattr(prov, 'pipeline_version', ''),
                    'alignment_method': getattr(prov, 'alignment_method', ''),
                    'surface_model_type': getattr(prov, 'surface_model_type', ''),
                    'frames_used': getattr(prov, 'frames_used_in_mosaic', 0),
                    'georef_confidence': getattr(prov, 'georef_confidence', 0),
                }
            
            logger.info(
                f"[DroneRGBEngine] Using photogrammetry output: "
                f"qa={getattr(ortho, 'qa_score', 0):.2f}, "
                f"coverage={getattr(ortho, 'coverage_completeness', 0):.1%}"
            )
        
        # 1. Quality Assurance
        qa_result = evaluate_drone_qa(inp)
        if not qa_result.is_usable:
            out = DroneRGBOutput(
                plot_id=inp.plot_id, 
                mission_id=inp.mission_id,
                is_valid=False,
                qa_score=qa_result.overall_score,
                rejection_reason=qa_result.rejection_reason
            )
            return out, []
            
        # 2. Structural Analysis
        out = DroneRGBOutput(
            plot_id=inp.plot_id,
            mission_id=inp.mission_id,
            qa_score=qa_result.overall_score
        )
        
        # Attach photogrammetry provenance
        if ortho_provenance:
            out.orthomosaic_provenance = ortho_provenance
        
        # Analyze the synthetic matrix (or real ortho)
        struct_result = self.structural_analyzer.analyze(inp)
        
        # Populate output
        out.row_azimuth_deg = struct_result.row_azimuth_deg
        out.row_spacing_cm = struct_result.row_spacing_cm
        out.canopy_cover_fraction = struct_result.canopy_cover_fraction
        out.bare_soil_fraction = struct_result.bare_soil_fraction
        out.weed_pressure_index = struct_result.weed_pressure_index
        out.spatial_maps = struct_result.spatial_maps
        
        # V1.5 Row continuity
        out.row_count = struct_result.row_count
        out.row_continuity_scores = struct_result.row_continuity_scores
        out.row_breaks = struct_result.row_breaks
        out.stand_density_per_row = struct_result.stand_density_per_row
        
        # V1.5 Weed separation
        out.in_row_weed_fraction = struct_result.in_row_weed_fraction
        out.inter_row_weed_fraction = struct_result.inter_row_weed_fraction
        
        # V1.5 Orchard
        out.tree_count = struct_result.tree_count
        out.missing_tree_count = struct_result.missing_tree_count
        out.canopy_diameters_cm = struct_result.canopy_diameters_cm
        out.canopy_uniformity_cv = struct_result.canopy_uniformity_cv
        
        # 3. Packetization
        packets = self.packetizer.packetize(out, qa_result)
        
        return out, packets
