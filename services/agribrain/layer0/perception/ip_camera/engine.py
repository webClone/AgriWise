"""
IP Camera Engine — top-level orchestrator for fixed-camera perception.

Pipeline:
  1. Registration quality hard gate
  2. Preprocess (real image or mock stats) — includes segmentation + ROI
  3. QA (12 checks including 4 image-structural)
  4. Scene stability (histogram + edge + scalar baseline comparison)
  5. Inference (agronomic variable extraction from crop-region stats)
  6. Cross-source validation (weather + satellite)
  7. Baseline update (histograms + thumbnails + scalars)
  8. Packetize
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from layer0.perception.ip_camera.schemas import IPCameraEngineInput, IPCameraEngineOutput, IPCameraQAResult
from layer0.perception.ip_camera.preprocess import IPCameraPreprocessor, PreprocessResult
from layer0.perception.ip_camera.qa import IPCameraQA
from layer0.perception.ip_camera.scene_stability import SceneStabilityAnalyzer
from layer0.perception.ip_camera.baseline_model import BaselineModel
from layer0.perception.ip_camera.inference import IPCameraInference
from layer0.perception.ip_camera.packetizer import IPCameraPacketizer
from layer0.perception.ip_camera.weather_validation import CameraWeatherValidator
from layer0.perception.ip_camera.satellite_validation import CameraSatelliteValidator

from layer0.perception.common.contracts import PerceptionVariable
try:
    from layer0.observation_packet import ObservationPacket
except ImportError:
    ObservationPacket = None  # type: ignore


class IPCameraEngine:
    """
    Top-level orchestrator for the IP Camera perception domain.
    """

    def __init__(self):
        self.preprocessor = IPCameraPreprocessor()
        self.qa = IPCameraQA()
        self.baseline_model = BaselineModel()
        self.stability_analyzer = SceneStabilityAnalyzer(self.baseline_model)
        self.inference = IPCameraInference()
        self.weather_validator = CameraWeatherValidator()
        self.satellite_validator = CameraSatelliteValidator()
        self.packetizer = IPCameraPacketizer()

    def process(self, input_data: IPCameraEngineInput) -> IPCameraEngineOutput:
        """Process a single frame through the full perception pipeline."""

        # 1. Registration Quality Hard Gate
        registration_quality = input_data.metadata.get("registration_quality_score", 1.0)
        if registration_quality < 0.5:
            qa_result = IPCameraQAResult(
                usable=False,
                qa_score=0.1,
                reliability_weight=0.0,
                sigma_inflation=10.0,
                flags=["low_registration_quality"],
            )
            return self.packetizer.packetize(
                input_data=input_data,
                qa_result=qa_result,
                context=None,
                variables=[],
                validation_checks=[],
            )

        # 2. Preprocess (includes segmentation, ROI, histogram, thumbnail)
        preprocess, context_dict = self.preprocessor.process(input_data)

        # 3. QA (12 checks)
        qa_result = self.qa.assess_quality(input_data, preprocess)

        # 4. Scene Stability (histogram + edge + scalar comparison)
        current_time = input_data.timestamp or datetime.now()
        scene_ctx = self.stability_analyzer.analyze(
            input_data.camera_id, preprocess, current_time
        )

        variables = []
        validation_checks = []

        if qa_result.usable:
            # 5. Inference
            variables = self.inference.run_inference(preprocess, scene_ctx)

            # 6. Validation Intelligence
            weather_val = self.weather_validator.validate(input_data, variables)
            satellite_val = self.satellite_validator.validate(input_data, variables)
            validation_checks.extend(weather_val)
            validation_checks.extend(satellite_val)

            # 7. Update baseline (histograms + thumbnails + scalars)
            self.baseline_model.update_baseline(
                camera_id=input_data.camera_id,
                current_time=current_time,
                green_ratio=preprocess.green_ratio,
                brightness_mean=preprocess.brightness_mean,
                saturation_mean=preprocess.saturation_mean,
                green_coverage_fraction=preprocess.green_coverage_fraction,
                edge_density=preprocess.edge_density,
                hsv_histogram=preprocess.hsv_histogram,
                gray_thumbnail=preprocess.gray_thumbnail_64,
                frame_ref=input_data.frame_ref,
            )
            self.baseline_model.update_seasonal_baseline(
                camera_id=input_data.camera_id,
                green_ratio=preprocess.green_ratio,
                brightness_mean=preprocess.brightness_mean,
                saturation_mean=preprocess.saturation_mean,
            )

        # 8. Packetize
        output = self.packetizer.packetize(
            input_data=input_data,
            qa_result=qa_result,
            context=scene_ctx,
            variables=variables,
            validation_checks=validation_checks,
        )
        output.model_versions = {"inference": self.inference.VERSION, "qa": self.qa.VERSION} if hasattr(self.qa, 'VERSION') else {"inference": "v1", "qa": "v1"}

        return output

    def process_and_packetize(self, input_data: IPCameraEngineInput):
        """
        Convenience: process frame and return a universal ObservationPacket
        ready for the Layer 0 Kalman assimilator.
        """
        output = self.process(input_data)
        return self.packetizer.to_observation_packet(output)
