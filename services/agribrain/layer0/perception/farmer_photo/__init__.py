"""
Farmer Photo Perception Engine.

Plant recognition + symptom evidence engine.
Accepts close-range phone/camera photos and emits structured,
uncertainty-aware observations about crop identity, organ type,
and visible symptoms.

Usage:
    from services.agribrain.layer0.perception.farmer_photo import FarmerPhotoEngine
    from services.agribrain.layer0.perception.farmer_photo.schemas import FarmerPhotoEngineInput

    engine = FarmerPhotoEngine()
    packets = engine.process(engine_input)
"""

from .engine import FarmerPhotoEngine

__all__ = ["FarmerPhotoEngine"]
