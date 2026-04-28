"""
Satellite RGB Perception Engine.

The first specialized perception engine — extracts plot-scale
structural intelligence from georeferenced RGB imagery.

Usage:
    from layer0.perception.satellite_rgb import SatelliteRGBEngine
    from layer0.perception.satellite_rgb.schemas import SatelliteRGBEngineInput
    
    engine = SatelliteRGBEngine()
    packets = engine.process(SatelliteRGBEngineInput(...))
"""

from layer0.perception.satellite_rgb.engine import SatelliteRGBEngine
from layer0.perception.satellite_rgb.schemas import SatelliteRGBEngineInput, SatelliteRGBEngineOutput
