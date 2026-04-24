"""
Satellite RGB Engine — Top-level orchestrator.

Pipeline: validate input → preprocess → QA → inference → packetize.

This is the single entry point for satellite RGB perception.
All other modules in this package are internal implementation details.

Usage:
    engine = SatelliteRGBEngine()
    packets = engine.process(input)
    # or
    result = engine.process_full(input)  # returns typed output + packets
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from .schemas import SatelliteRGBEngineInput, SatelliteRGBEngineOutput
from .qa import SatelliteRGBQA, SatelliteRGBQAResult
from .preprocess import SatelliteRGBPreprocessor, PlotImageContext
from .inference import SatelliteRGBInference, SatelliteRGBInferenceResult
from .packetizer import packetize, build_engine_output
from ..common.cache import PerceptionCache
from ..common.contracts import PerceptionEngineFamily, PerceptionEngineOutput

from services.agribrain.layer0.observation_packet import ObservationPacket


class SatelliteRGBEngine:
    """
    Satellite RGB perception engine.
    
    Extracts plot-scale structural intelligence from georeferenced RGB imagery.
    Provider-agnostic: accepts Sentinel-2, Landsat 8/9, or any georeferenced RGB.
    
    V1 outputs:
      - Vegetation fraction (→ LAI proxy via Kalman)
      - Bare soil fraction (auxiliary)
      - RGB anomaly score (→ weak canopy stress proxy via Kalman)
      - Coarse phenology stage
      - Boundary contamination score
      - Zone-level aggregates
      - Artifact references (vegetation mask, anomaly map, confidence map)
    
    Does NOT:
      - Output NDVI (no NIR band)
      - Output disease type
      - Output water content index
      - Output fertilizer recommendation
      - Detect rows (deferred to V1.5)
    """

    def __init__(self, cache: Optional[PerceptionCache] = None):
        self.qa = SatelliteRGBQA()
        self.preprocessor = SatelliteRGBPreprocessor()
        self.inference = SatelliteRGBInference()
        self.cache = cache or PerceptionCache()

    def process(
        self,
        engine_input: SatelliteRGBEngineInput,
    ) -> List[ObservationPacket]:
        """
        Process a satellite RGB image and return ObservationPackets.
        
        This is the standard entry point for Layer 0 integration.
        The packets are ready for Kalman assimilation.
        
        Args:
            engine_input: SatelliteRGBEngineInput with required fields
        
        Returns:
            List of ObservationPackets (one per emittable variable).
            Empty list if input validation fails or image is unusable.
        """
        result = self.process_full(engine_input)
        if result is None:
            return []
        return result[1]

    def process_full(
        self,
        engine_input: SatelliteRGBEngineInput,
    ) -> Optional[Tuple[SatelliteRGBEngineOutput, List[ObservationPacket]]]:
        """
        Process a satellite RGB image and return both typed output and packets.
        
        Use this when you need the full engine output for UI/API responses
        in addition to the Kalman-ready packets.
        
        Returns:
            (SatelliteRGBEngineOutput, List[ObservationPacket]) or None on failure.
        """
        processing_steps = []

        # --- Step 0: Validate input ---
        is_valid, errors = engine_input.validate()
        if not is_valid:
            print(f"❌ [SatelliteRGBEngine] Input validation failed: {errors}")
            return None
        processing_steps.append("validate_input")

        # --- Step 1: Check cache ---
        if engine_input.image_content_hash:
            cache_key = self.cache.make_key(
                "satellite_rgb",
                engine_input.plot_id,
                engine_input.image_content_hash,
                "v1",
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                print(f"✅ [SatelliteRGBEngine] Cache hit for plot {engine_input.plot_id}")
                processing_steps.append("cache_hit")
                return cached

        # --- Step 2: Preprocess ---
        ctx = self.preprocessor.preprocess(
            image_width=engine_input.image_width,
            image_height=engine_input.image_height,
            ground_resolution_m=engine_input.ground_resolution_m,
            plot_polygon=engine_input.plot_polygon,
            synthetic_pixels=engine_input.synthetic_pixels,
        )
        processing_steps.append("preprocess_crop_mask")

        # --- Step 3: QA ---
        # Compute plot area from input (prefer explicit, fall back to bbox)
        plot_area_ha = engine_input.plot_area_ha
        if plot_area_ha is None and engine_input.bbox:
            min_lng, min_lat, max_lng, max_lat = engine_input.bbox
            lat_km = abs(max_lat - min_lat) * 111.0
            lng_km = abs(max_lng - min_lng) * 111.0 * abs(
                __import__('math').cos(__import__('math').radians((min_lat + max_lat) / 2))
            )
            plot_area_ha = lat_km * lng_km * 100  # km² → ha

        qa_result = self.qa.assess(
            ground_resolution_m=engine_input.ground_resolution_m,
            image_width=engine_input.image_width,
            image_height=engine_input.image_height,
            cloud_estimate=engine_input.cloud_estimate,
            haze_score=engine_input.haze_score,
            recentness_days=engine_input.recentness_days,
            plot_area_ha=plot_area_ha,
            coverage_fraction=None,  # Could be computed from masks
            boundary_pixel_fraction=ctx.masks.boundary_fraction if ctx.masks else None,
            sun_angle=engine_input.sun_angle,
            view_angle=engine_input.view_angle,
        )
        processing_steps.append(f"qa_satellite:score={qa_result.qa_score:.2f}")

        # --- Step 4: Check usability ---
        if not qa_result.usable:
            print(f"⚠️ [SatelliteRGBEngine] Image not usable: qa_score={qa_result.qa_score:.2f}, flags={qa_result.flags}")
            # Still return a minimal output with QA info
            minimal = SatelliteRGBEngineOutput(
                plot_id=engine_input.plot_id,
                timestamp=engine_input.timestamp,
                qa_score=qa_result.qa_score,
                reliability_weight=qa_result.reliability_weight,
                sigma_inflation=qa_result.sigma_inflation,
            )
            return (minimal, [])

        # --- Step 5: Inference ---
        inference_result = self.inference.run(
            ctx=ctx,
            resolution_m=engine_input.ground_resolution_m,
        )
        processing_steps.append("inference_segmentation_v1")
        processing_steps.append("inference_anomaly_v1")
        processing_steps.append("inference_phenology_v1")

        # --- Step 6: Packetize ---
        packets = packetize(
            inference_result=inference_result,
            qa_result=qa_result,
            engine_input=engine_input,
            processing_steps=processing_steps,
        )
        processing_steps.append(f"packetize:{len(packets)}_packets")

        # Build full output
        engine_output = build_engine_output(
            inference_result=inference_result,
            qa_result=qa_result,
            engine_input=engine_input,
            processing_steps=processing_steps,
        )

        # --- Step 7: Cache result ---
        if engine_input.image_content_hash:
            cache_key = self.cache.make_key(
                "satellite_rgb",
                engine_input.plot_id,
                engine_input.image_content_hash,
                "v1",
            )
            self.cache.set(cache_key, (engine_output, packets))

        print(f"✅ [SatelliteRGBEngine] Processed plot {engine_input.plot_id}: "
              f"veg={engine_output.vegetation_fraction:.2f}, "
              f"soil={engine_output.bare_soil_fraction:.2f}, "
              f"anomaly={engine_output.anomaly_fraction:.2f}, "
              f"qa={qa_result.qa_score:.2f}, "
              f"{len(packets)} packets")

        return (engine_output, packets)
