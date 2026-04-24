"""
Drone Packetizer.

Converts DroneRGBOutput into standard Layer 0 ObservationPackets.
"""

from typing import List
import datetime

from .schemas import DroneRGBOutput
from .qa import DroneQAOutput
from ...observation_packet import ObservationPacket

class DronePacketizer:
    
    def packetize(self, out: DroneRGBOutput, qa: DroneQAOutput) -> List[ObservationPacket]:
        packets = []
        
        from ...observation_packet import ObservationSource, ObservationType, UncertaintyModel, Provenance, QAMetadata
        
        # We use sigma_inflation from the QA result to adjust uncertainties.
        base_sigma = 0.05
        inflated_sigma = base_sigma * qa.sigma_inflation
        
        sigmas = {}
        payload = {
            "summary_metrics": {},
            "spatial_maps_embedded": {}
        }
        
        if out.canopy_cover_fraction is not None:
            payload["summary_metrics"]["canopy_cover_high_res"] = out.canopy_cover_fraction
            sigmas["canopy_cover_high_res"] = inflated_sigma
            
        if out.bare_soil_fraction is not None:
            payload["summary_metrics"]["bare_soil_fraction_high_res"] = out.bare_soil_fraction
            sigmas["bare_soil_fraction_high_res"] = inflated_sigma
            
        if out.weed_pressure_index is not None:
            payload["summary_metrics"]["weed_pressure_index"] = out.weed_pressure_index
            sigmas["weed_pressure_index"] = inflated_sigma * 1.5
            
        if out.row_azimuth_deg is not None:
            payload["summary_metrics"]["row_azimuth_deg"] = out.row_azimuth_deg
            sigmas["row_azimuth_deg"] = 2.0 * qa.sigma_inflation
            
        if out.row_spacing_cm is not None:
            payload["summary_metrics"]["row_spacing_cm"] = out.row_spacing_cm
            sigmas["row_spacing_cm"] = 5.0 * qa.sigma_inflation
        
        # V1.5 Row continuity metrics
        if out.row_continuity_scores:
            mean_cont = sum(out.row_continuity_scores) / len(out.row_continuity_scores)
            payload["summary_metrics"]["row_continuity_mean"] = mean_cont
            sigmas["row_continuity_mean"] = 0.10 * qa.sigma_inflation
            
        if out.row_breaks:
            payload["summary_metrics"]["row_break_count"] = len(out.row_breaks)
            sigmas["row_break_count"] = 2.0 * qa.sigma_inflation
            
        if out.stand_density_per_row:
            mean_density = sum(out.stand_density_per_row) / len(out.stand_density_per_row)
            payload["summary_metrics"]["stand_density_mean"] = mean_density
            sigmas["stand_density_mean"] = 1.0 * qa.sigma_inflation
            
        # V1.5 Weed separation
        if out.in_row_weed_fraction > 0 or out.inter_row_weed_fraction > 0:
            payload["summary_metrics"]["in_row_weed_fraction"] = out.in_row_weed_fraction
            payload["summary_metrics"]["inter_row_weed_fraction"] = out.inter_row_weed_fraction
            sigmas["in_row_weed_fraction"] = inflated_sigma * 1.5
            sigmas["inter_row_weed_fraction"] = inflated_sigma * 1.5
            
        # V1.5 Orchard metrics
        if out.tree_count > 0:
            payload["summary_metrics"]["tree_count"] = out.tree_count
            payload["summary_metrics"]["missing_tree_count"] = out.missing_tree_count
            payload["summary_metrics"]["canopy_uniformity_cv"] = out.canopy_uniformity_cv
            sigmas["tree_count"] = 3.0 * qa.sigma_inflation
            sigmas["missing_tree_count"] = 2.0 * qa.sigma_inflation
            sigmas["canopy_uniformity_cv"] = 0.10 * qa.sigma_inflation
            
        # Process spatial maps
        for smap in out.spatial_maps:
            grid = smap.data_grid
            h = len(grid)
            w = len(grid[0]) if h > 0 else 0
            
            is_downsampled = False
            downsampled_res = smap.resolution_cm
            max_dim = 128
            
            # Simple downsampling if array exceeds max_dim
            if h > max_dim or w > max_dim:
                is_downsampled = True
                scale_h = max(1, h // max_dim + (1 if h % max_dim else 0))
                scale_w = max(1, w // max_dim + (1 if w % max_dim else 0))
                scale = max(scale_h, scale_w)
                
                new_grid = []
                for y in range(0, h, scale):
                    row = []
                    for x in range(0, w, scale):
                        row.append(grid[y][x])
                    new_grid.append(row)
                
                grid = new_grid
                downsampled_res = smap.resolution_cm * scale
                
            payload["spatial_maps_embedded"][smap.map_type] = {
                "encoding": "inline_array_v1",
                "is_downsampled": is_downsampled,
                "source_resolution_cm": smap.resolution_cm,
                "downsampled_resolution_cm": downsampled_res,
                "bbox": {
                    "top_left_lat": smap.top_left_lat,
                    "top_left_lon": smap.top_left_lon,
                    "bottom_right_lat": smap.bottom_right_lat,
                    "bottom_right_lon": smap.bottom_right_lon
                },
                "data_grid": grid
            }
            
        if not payload["summary_metrics"] and not payload["spatial_maps_embedded"]:
            return []
            
        prov = Provenance(
            processing_chain=["drone_mission_planner", "drone_rgb_structural"],
            source_url=f"drone_mission://{out.mission_id}"
        )
        
        qa_meta = QAMetadata()
        qa_meta.scene_score = out.qa_score
        
        packet = ObservationPacket(
            source=ObservationSource.DRONE,
            obs_type=ObservationType.RASTER,
            timestamp=datetime.datetime.now(),
            payload=payload,
            qa=qa_meta,
            uncertainty=UncertaintyModel(sigmas=sigmas),
            provenance=prov
        )
        
        packets.append(packet)
            
        return packets
