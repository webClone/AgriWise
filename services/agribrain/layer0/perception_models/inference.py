"""
Perception Models — ML inference stubs for image-to-state extraction.

  LEGACY MODULE — These generic heuristic models will be superseded
    by engine-specific inference modules:
      - satellite_rgb/inference.py  -> vegetation/soil seg, anomaly, canopy
      - farmer_photo/inference.py   -> close-range canopy, disease (planned)
      - drone/inference.py          -> ortho segmentation, rows (planned)
      - ip_camera/inference.py      -> temporal canopy tracking (planned)

    Do not add new logic here.

These are structured inference modules that take image metadata/pixel stats
and produce structured outputs with uncertainty. They are designed to be
replaceable with real CNN models when available.

Each model returns:
  - value: estimated quantity
  - sigma: uncertainty estimate
  - confidence: model confidence 0–1
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import math


@dataclass
class PerceptionOutput:
    """Standard output from any perception model."""
    variable: str
    value: float
    sigma: float
    confidence: float
    model_version: str = "heuristic_v1"
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class CanopyCoverModel:
    """
    Canopy cover estimation (0–1) from RGB image.
    
    Maps to state: lai_proxy via observation_model.camera_canopy_cover
    
    Heuristic v1: uses green ratio + brightness as proxy.
    Production: ExGR index or trained segmentation CNN.
    """
    VERSION = "heuristic_v1"
    
    @staticmethod
    def predict(pixel_stats: Dict[str, Any]) -> PerceptionOutput:
        green_ratio = pixel_stats.get("green_ratio", 0.33)
        brightness = pixel_stats.get("brightness_mean", 128)
        saturation = pixel_stats.get("saturation_mean", 100)
        
        # Excess Green index proxy
        # High green ratio + moderate brightness + good saturation = vegetation
        veg_indicator = green_ratio * 2.0  # Scale to ~0–1
        
        # Brightness correction: very bright = bare soil/sky, very dark = shadow
        if brightness > 200:
            veg_indicator *= 0.6
        elif brightness < 50:
            veg_indicator *= 0.5
        
        # Saturation boost: green vegetation is saturated
        if saturation > 80:
            veg_indicator *= 1.1
        
        canopy_cover = max(0.0, min(1.0, veg_indicator))
        
        # Uncertainty: higher if conditions are ambiguous
        sigma = 0.10  # Base
        if brightness > 200 or brightness < 50:
            sigma = 0.20
        if green_ratio < 0.2 or green_ratio > 0.5:
            sigma = 0.15
        
        confidence = 1.0 - sigma / 0.30
        
        return PerceptionOutput(
            variable="canopy_cover",
            value=round(canopy_cover, 3),
            sigma=sigma,
            confidence=round(confidence, 2),
            model_version=CanopyCoverModel.VERSION,
            details={"green_ratio": green_ratio, "brightness": brightness},
        )


class PhenologyStageModel:
    """
    Phenology stage estimation (0–4 float) from RGB image.
    
    Maps to state: phenology_stage (0=dormant, 1=veg, 2=flower, 3=ripen, 4=senescence)
    
    Heuristic v1: uses green/yellow/brown color ratios.
    Production: trained classification CNN with ordinal regression.
    """
    VERSION = "heuristic_v1"
    
    @staticmethod
    def predict(pixel_stats: Dict[str, Any],
                crop_type: str = "wheat") -> PerceptionOutput:
        green_ratio = pixel_stats.get("green_ratio", 0.33)
        saturation = pixel_stats.get("saturation_mean", 100)
        brightness = pixel_stats.get("brightness_mean", 128)
        
        # Color-based stage estimation
        # High green + high saturation = vegetative
        # Moderate green + moderate saturation = flowering/ripening
        # Low green + low saturation + high brightness = senescence/harvest
        
        if green_ratio > 0.4 and saturation > 100:
            stage = 1.0 + (green_ratio - 0.4) * 5  # Vegetative
        elif green_ratio > 0.3:
            stage = 2.0  # Flowering
        elif green_ratio > 0.2 and brightness > 150:
            stage = 3.0  # Ripening
        elif green_ratio < 0.2:
            stage = 3.5 + (0.2 - green_ratio) * 5  # Senescence
        else:
            stage = 0.5  # Early/dormant
        
        stage = max(0.0, min(4.0, stage))
        
        # High uncertainty for heuristic model
        sigma = 0.8
        confidence = 0.4
        
        return PerceptionOutput(
            variable="phenology_stage",
            value=round(stage, 1),
            sigma=sigma,
            confidence=confidence,
            model_version=PhenologyStageModel.VERSION,
            details={"green_ratio": green_ratio, "crop_type": crop_type},
        )


class DiseaseSymptomModel:
    """
    Disease/stress symptom probability (0–1) from RGB image.
    
    Heuristic v1: detects yellowing/browning as stress proxy.
    Production: fine-grained symptom classification CNN (requires training data).
    """
    VERSION = "heuristic_v1"
    
    @staticmethod
    def predict(pixel_stats: Dict[str, Any]) -> PerceptionOutput:
        green_ratio = pixel_stats.get("green_ratio", 0.33)
        brightness = pixel_stats.get("brightness_mean", 128)
        saturation = pixel_stats.get("saturation_mean", 100)
        
        # Stress indicators: low green, moderate brightness, low saturation
        stress_prob = 0.0
        
        # Yellowing: green drops, brightness stays
        if green_ratio < 0.25 and brightness > 100:
            stress_prob = max(stress_prob, (0.25 - green_ratio) * 4)
        
        # Browning: very low saturation
        if saturation < 50:
            stress_prob = max(stress_prob, (50 - saturation) / 50)
        
        stress_prob = max(0.0, min(1.0, stress_prob))
        
        # Very high uncertainty — heuristic disease detection is unreliable
        sigma = 0.30
        confidence = 0.25
        
        return PerceptionOutput(
            variable="disease_symptom_prob",
            value=round(stress_prob, 3),
            sigma=sigma,
            confidence=confidence,
            model_version=DiseaseSymptomModel.VERSION,
            details={"note": "heuristic_only_use_with_caution"},
        )


class DroneWeedRowModel:
    """
    Drone-specific: weed fraction + row detection from orthomosaic stats.
    
    Heuristic v1: uses texture variance + green spatial distribution.
    Production: semantic segmentation CNN on tiles.
    """
    VERSION = "heuristic_v1"
    
    @staticmethod
    def predict(pixel_stats: Dict[str, Any],
                drone_meta: Optional[Dict] = None) -> Dict[str, PerceptionOutput]:
        outputs = {}
        
        # Weed fraction (proxy from texture heterogeneity)
        brightness_std = pixel_stats.get("brightness_std", 30)
        green_ratio = pixel_stats.get("green_ratio", 0.33)
        
        # High texture + high green = potential weeds between rows
        weed_indicator = 0.0
        if brightness_std > 40 and green_ratio > 0.35:
            weed_indicator = min(1.0, (brightness_std - 40) / 60)
        
        outputs["weed_fraction"] = PerceptionOutput(
            variable="weed_fraction",
            value=round(weed_indicator, 3),
            sigma=0.25,  # Very uncertain from heuristics
            confidence=0.3,
            model_version=DroneWeedRowModel.VERSION,
        )
        
        # Row direction (placeholder — needs actual frequency analysis)
        outputs["row_direction"] = PerceptionOutput(
            variable="row_direction_deg",
            value=90.0,  # Default east-west
            sigma=45.0,  # Very uncertain without real analysis
            confidence=0.1,
            model_version=DroneWeedRowModel.VERSION,
            details={"note": "placeholder_needs_fft_analysis"},
        )
        
        return outputs
