"""
Satellite RGB Perception Engine.

The first specialized perception engine — extracts plot-scale
structural intelligence from georeferenced RGB imagery.

Usage:
    from services.agribrain.layer0.perception.satellite_rgb import SatelliteRGBEngine
    from services.agribrain.layer0.perception.satellite_rgb.schemas import SatelliteRGBEngineInput
    
    engine = SatelliteRGBEngine()
    packets = engine.process(SatelliteRGBEngineInput(...))
"""

from .engine import SatelliteRGBEngine
from .schemas import SatelliteRGBEngineInput, SatelliteRGBEngineOutput
