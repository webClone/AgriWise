"""
Farmer Photo Engine — Top-Level Orchestrator.

Plant recognition + symptom evidence engine.

Pipeline:
  validate → cache → preprocess → QA gate → scene classify →
  crop classify → organ classify → symptom classify →
  calibrate → packetize

Key behaviors:
  - NON_FIELD / UNUSABLE → stop, return zero packets
  - GPS far from plot → emit with extreme sigma inflation
  - Always enforces geometry_scope = "point"
  - Disease confidence is gated by crop confidence
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..common.cache import PerceptionCache
from ..common.contracts import PerceptionEngineFamily

from .schemas import (
    FarmerPhotoEngineInput,
    FarmerPhotoEngineOutput,
    SceneClass, CropClass, OrganClass, SymptomClass,
    SceneResult,
)
from .qa import FarmerPhotoQA, FarmerPhotoQAResult, FarmerPhotoQAFlag
from .preprocess import FarmerPhotoPreprocessor
from .crop_classifier import CropClassifier
from .organ_classifier import OrganClassifier
from .symptom_classifier import SymptomClassifier
from .scene_gate import SceneGate
from .calibrator import EvidenceCalibrator
from .packetizer import FarmerPhotoPacketizer


class FarmerPhotoEngine:
    """
    Farmer Photo perception engine.

    Accepts any phone/camera photo and emits structured, uncertainty-aware
    observations about crop identity, organ type, and symptoms.

    Usage:
        engine = FarmerPhotoEngine()
        packets = engine.process(engine_input)
        # or for full typed output:
        output, packets = engine.process_full(engine_input)
    """

    def __init__(self):
        self.cache = PerceptionCache(default_ttl_seconds=1800)  # 30 min
        self.qa = FarmerPhotoQA()
        self.preprocessor = FarmerPhotoPreprocessor()
        self.scene_gate = SceneGate()
        self.crop_classifier = CropClassifier()
        self.organ_classifier = OrganClassifier()
        self.symptom_classifier = SymptomClassifier()
        self.calibrator = EvidenceCalibrator()
        self.packetizer = FarmerPhotoPacketizer()

    def process(self, engine_input: FarmerPhotoEngineInput) -> List:
        """
        Process a farmer photo and return ObservationPackets.

        Returns empty list for non-field / unusable / invalid images.
        """
        result = self.process_full(engine_input)
        if result is None:
            return []
        _, packets = result
        return packets

    def process_full(
        self, engine_input: FarmerPhotoEngineInput
    ) -> Optional[Tuple[FarmerPhotoEngineOutput, List]]:
        """
        Process a farmer photo and return both typed output and packets.

        Returns None for invalid inputs.
        Returns (output, []) for non-field/unusable images.
        """
        processing_steps: List[str] = []

        # --- Step 1: Validate input ---
        is_valid, errors = engine_input.validate()
        if not is_valid:
            return None
        processing_steps.append("validate_input")

        # --- Step 2: Check cache ---
        if engine_input.image_content_hash:
            cache_key = self.cache.make_key(
                engine_family="farmer_photo",
                plot_id=engine_input.plot_id,
                image_content_hash=engine_input.image_content_hash,
                model_version=f"{self.scene_gate.VERSION}_{self.crop_classifier.VERSION}_{self.organ_classifier.VERSION}_{self.symptom_classifier.VERSION}_{self.calibrator.VERSION}",
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        else:
            cache_key = None
        processing_steps.append("cache_check")

        # --- Step 3: Preprocess ---
        features = self.preprocessor.preprocess(
            image_ref=engine_input.image_ref,
            image_bytes=engine_input.image_bytes,
            pixel_stats=engine_input.pixel_stats,
            synthetic_pixels=engine_input.synthetic_pixels,
            exif=engine_input.exif,
            image_width=engine_input.image_width,
            image_height=engine_input.image_height,
        )
        processing_steps.append("preprocess")

        # --- Step 4: Scene classification ---
        scene = self.scene_gate.predict(features, user_label=engine_input.user_label)
        processing_steps.append("scene_classify")

        # --- Step 5: QA gate ---
        # Compute recentness from timestamp
        recentness_days = None
        if engine_input.timestamp:
            delta = datetime.now() - engine_input.timestamp
            recentness_days = max(0, delta.days)

        qa_result = self.qa.assess(
            image_width=engine_input.image_width,
            image_height=engine_input.image_height,
            pixel_stats={
                "green_ratio": features.green_ratio,
                "brightness_mean": features.brightness_mean,
                "brightness_std": features.brightness_std,
                "saturation_mean": features.saturation_mean,
                "laplacian_var": features.laplacian_var,
                "overexposed_pct": features.overexposed_pct,
                "underexposed_pct": features.underexposed_pct,
            },
            exif=engine_input.exif,
            gps_lat=engine_input.gps_lat,
            gps_lng=engine_input.gps_lng,
            plot_centroid_lat=engine_input.plot_centroid_lat,
            plot_centroid_lng=engine_input.plot_centroid_lng,
            recentness_days=recentness_days,
            user_label=engine_input.user_label,
            scene=scene,
            load_error=features.load_error,
        )
        processing_steps.append("qa_gate")

        # Build output (even for non-field, we return the typed output)
        # Map internal sub-types to public SceneClass values
        public_scene = scene.scene_class
        if public_scene == "soil_scene":
            public_scene = SceneClass.FIELD  # Soil is an agricultural scene
        output = FarmerPhotoEngineOutput(
            plot_id=engine_input.plot_id,
            timestamp=engine_input.timestamp,
            qa_score=qa_result.qa_score,
            reliability_weight=qa_result.reliability_weight,
            sigma_inflation=qa_result.sigma_inflation,
            scene_class=public_scene,
            scene_confidence=scene.confidence,
        )
        output.qa_flags = qa_result.flags
        output.qa_details = qa_result.details


        # --- Gate: non-field / unusable → zero packets ---
        if scene.scene_class in (SceneClass.NON_FIELD, SceneClass.UNUSABLE):
            output.variables = []
            result = (output, [])
            if cache_key:
                self.cache.set(cache_key, result)
            return result

        # --- Step 6: Crop classification ---
        crop_result = self.crop_classifier.predict(
            features, crop_hint=engine_input.crop_hint
        )
        output.crop_class = crop_result.crop_class
        output.crop_confidence = crop_result.confidence
        processing_steps.append("crop_classify")

        # --- Step 7: Organ classification ---
        organ_result = self.organ_classifier.predict(
            features, user_label=engine_input.user_label
        )
        output.organ_class = organ_result.organ_class
        output.organ_confidence = organ_result.confidence
        processing_steps.append("organ_classify")

        # Track explicit assist provenance (not just hint presence)
        output.crop_assisted_by_hint = crop_result.assisted_by_hint
        output.organ_from_user_label = organ_result.assisted_by_user_label

        # --- Step 8: Symptom classification ---
        symptom_result = self.symptom_classifier.predict(
            features,
            organ_class=organ_result.organ_class,
            crop_class=crop_result.crop_class,
            crop_confidence=crop_result.confidence,
        )
        output.primary_symptom = symptom_result.primary_symptom
        output.symptom_confidence = symptom_result.primary_confidence
        output.symptom_severity = symptom_result.severity
        output.disease_candidate = symptom_result.disease_candidate
        output.disease_confidence = symptom_result.disease_confidence
        processing_steps.append("symptom_classify")

        # --- Step 9: Calibrate ---
        evidence = self.calibrator.calibrate(
            features=features,
            scene=scene,
            crop=crop_result,
            organ=organ_result,
            symptom=symptom_result,
            qa_sigma_inflation=qa_result.sigma_inflation,
        )
        output.local_canopy_cover = evidence.local_canopy_cover
        output.phenology_stage_est = evidence.phenology_stage_est
        output.plant_identity_confidence = evidence.plant_identity_confidence
        processing_steps.append("calibrate")

        # --- Step 10: Packetize ---
        packetizer_output, packets = self.packetizer.packetize(
            evidence=evidence,
            qa_score=qa_result.qa_score,
            reliability_weight=qa_result.reliability_weight,
            sigma_inflation=qa_result.sigma_inflation,
            plot_id=engine_input.plot_id,
            timestamp=engine_input.timestamp,
            image_content_hash=engine_input.image_content_hash,
            processing_steps=processing_steps,
            qa_flags=output.qa_flags,
            scene_class=scene.scene_class,
            model_versions={
                "crop_classifier": self.crop_classifier.VERSION,
                "organ_classifier": self.organ_classifier.VERSION,
                "symptom_classifier": self.symptom_classifier.VERSION,
                "calibrator": self.calibrator.VERSION,
                "scene_gate": self.scene_gate.VERSION,
            }
        )
        if packetizer_output:
            output.variables = packetizer_output.variables

        processing_steps.append("packetize")

        output.provenance_chain = processing_steps

        result = (output, packets)
        if cache_key:
            self.cache.set(cache_key, result)
        return result


