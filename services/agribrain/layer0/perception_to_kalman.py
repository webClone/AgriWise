"""
Layer 0.10: Perception -> Kalman Bridge

Converts PerceptionPacketFactory outputs (ObservationPackets from images)
into KalmanObservations compatible with the DailyAssimilationEngine.

Handles:
  - Zone aggregation using PlotGrid α-weighted means (when zones available)
  - Plot-level fallback for ungeolocated images
  - Sigma inflation from image QA
  - Reliability inherited from QA + model confidence
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime

from layer0.observation_packet import ObservationPacket
from layer0.kalman_engine import KalmanObservation


# Mapping: perception variable -> KalmanObservation obs_type
PERCEPTION_OBS_TYPE_MAP = {
    "canopy_cover": "canopy_cover",
    "phenology_stage": "phenology_stage",
    "disease_symptom_prob": "stress_proxy",
    "weed_fraction": "weed_fraction",
    # Satellite RGB engine V1
    "vegetation_fraction": "vegetation_fraction",
    "rgb_anomaly_score": "rgb_anomaly_score",
    "coarse_phenology_stage": "phenology_stage",
    # Farmer Photo engine V1
    "local_canopy_cover": "farmer_photo_canopy",
    "disease_symptom_prob": "stress_proxy",
    "phenology_stage_est": "phenology_stage",
    # IP Camera engine V1
    "visible_stress_prob": "stress_proxy",
    "phenology_stage_camera": "phenology_stage_camera",
    # Sentinel-5P / Sentinel-2 photosynthetic activity V1
    "sif": "sif",
    "pri": "pri",
}

# Base sigma for each perception type (before QA inflation)
BASE_SIGMA = {
    "canopy_cover": 0.10,
    "phenology_stage": 0.80,
    "stress_proxy": 0.30,
    "weed_fraction": 0.25,
    # Satellite RGB engine V1 — intentionally higher sigma
    "vegetation_fraction": 0.12,
    "rgb_anomaly_score": 0.40,    # weak structural proxy, high uncertainty
    # Farmer Photo engine V1 — point scope, higher sigma
    "farmer_photo_canopy": 0.12,
    "farmer_photo_symptom": 0.35,  # symptom-first, not disease diagnosis
    # IP Camera engine V1
    "phenology_stage_camera": 0.50,
    # Sentinel-5P SIF / Sentinel-2 PRI
    "sif": 0.15,               # coarse spatial resolution but strong physical signal
    "pri": 0.08,               # pseudo-PRI from S2 bands, moderate noise
}


def packets_to_kalman_observations(
    packets: List[ObservationPacket],
    zone_id: str = "plot",
) -> List[KalmanObservation]:
    """
    Convert perception ObservationPackets into KalmanObservations.
    
    Args:
        packets: from PerceptionPacketFactory.process_image()
        zone_id: target zone (default "plot" for ungeolocated images)
    
    Returns:
        List of KalmanObservation ready for DailyAssimilationEngine.
    """
    observations = []
    
    for packet in packets:
        payload = packet.payload or {}
        
        for var_name, obs_type in PERCEPTION_OBS_TYPE_MAP.items():
            if var_name in payload:
                value = payload[var_name]
                
                # Get sigma from packet uncertainty or use base
                sigma_key = f"{var_name}_sigma"
                sigma = payload.get(sigma_key, BASE_SIGMA.get(obs_type, 0.2))
                
                # Reliability from packet
                reliability = getattr(packet, "reliability_weight", 0.5)
                
                observations.append(KalmanObservation(
                    obs_type=obs_type,
                    value=float(value),
                    sigma=float(sigma),
                    reliability=float(reliability),
                    source=f"perception_{packet.source.value if hasattr(packet.source, 'value') else packet.source}",
                ))
    
    return observations


def aggregate_zone_perception(
    packets: List[ObservationPacket],
    zone_pixel_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, List[KalmanObservation]]:
    """
    Aggregate perception packets per zone.
    
    If zone_pixel_weights provided, weight contributions by α mask.
    Otherwise, assign all packets to "plot" zone.
    
    Args:
        packets: list of ObservationPackets
        zone_pixel_weights: {zone_id: weight} from PlotGrid
    
    Returns:
        {zone_id: [KalmanObservation, ...]}
    """
    if not zone_pixel_weights:
        # Single-zone fallback
        return {"plot": packets_to_kalman_observations(packets, "plot")}
    
    result = {}
    for zone_id, weight in zone_pixel_weights.items():
        if weight > 0.01:  # Skip negligible zones
            obs_list = packets_to_kalman_observations(packets, zone_id)
            # Scale reliability by zone weight
            for obs in obs_list:
                obs.reliability = obs.reliability * weight
            result[zone_id] = obs_list
    
    return result
