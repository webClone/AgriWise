"""
Farmer Photo — Evidence Calibrator.

Converts raw classifier outputs (scores, classes) into bounded,
uncertainty-aware evidence suitable for Kalman assimilation.

This is the ML-ready seam: when real CNN models replace the heuristic
classifiers, the calibrator maps their logits/softmax into the same
bounded (value, sigma, confidence, reliability) format.

Rules:
  - All sigma values are explicitly set (no bare numbers)
  - Heuristic confidence is capped well below 1.0
  - Disease evidence is gated by crop confidence
  - Organ-invalid combinations suppress output
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .schemas import (
    OrganClass, CropClass, SymptomClass,
    CropResult, OrganResult, SymptomResult, SceneResult,
)
from .preprocess import PreprocessResult


@dataclass
class CalibratedEvidence:
    """Calibrated evidence from one farmer photo."""
    # Scene
    is_field: bool = False
    scene_confidence: float = 0.0

    # Plant identity
    crop_class: str = CropClass.UNKNOWN
    crop_confidence: float = 0.0
    organ_class: str = OrganClass.UNKNOWN
    organ_confidence: float = 0.0

    # Local observations (calibrated for Kalman)
    local_canopy_cover: float = 0.0
    canopy_cover_sigma: float = 0.20
    local_symptom_score: float = 0.0
    symptom_sigma: float = 0.35
    phenology_stage_est: float = 0.0
    phenology_sigma: float = 1.0

    # Disease evidence (always weak)
    disease_symptom_prob: float = 0.0
    disease_sigma: float = 0.40
    primary_symptom: str = SymptomClass.HEALTHY
    disease_candidate: str = ""
    disease_candidate_confidence: float = 0.0

    # Composite reliability
    plant_identity_confidence: float = 0.0


class EvidenceCalibrator:
    """
    Calibrates raw classifier outputs into bounded evidence.

    This module ensures that heuristic-level classifiers cannot
    produce unreasonably high confidence, and that all outputs
    carry appropriate sigma for their source quality.
    """
    VERSION = "calibrator_v1.1"

    # Base sigma values for each output
    CANOPY_COVER_SIGMA = 0.12      # Close-range canopy estimate
    SYMPTOM_SIGMA = 0.35           # Symptom score from color
    PHENOLOGY_SIGMA = 1.0          # Very coarse visual stage hint
    DISEASE_SIGMA = 0.40           # Disease probability — always weak

    # Confidence ceilings for heuristic-only mode
    HEURISTIC_CROP_CEILING = 0.60
    HEURISTIC_ORGAN_CEILING = 0.55
    HEURISTIC_SYMPTOM_CEILING = 0.50
    HEURISTIC_DISEASE_CEILING = 0.40

    def calibrate(
        self,
        features: PreprocessResult,
        scene: SceneResult,
        crop: CropResult,
        organ: OrganResult,
        symptom: SymptomResult,
        qa_sigma_inflation: float = 1.0,
    ) -> CalibratedEvidence:
        """
        Convert classifier outputs into calibrated evidence.

        Args:
            features: preprocessed pixel statistics
            scene: scene classification result
            crop: crop classification result
            organ: organ classification result
            symptom: symptom classification result
            qa_sigma_inflation: sigma multiplier from QA

        Returns:
            CalibratedEvidence with bounded, uncertainty-aware outputs.
        """
        evidence = CalibratedEvidence()

        # --- Scene ---
        evidence.is_field = scene.scene_class in ("field", "crop_closeup")
        evidence.scene_confidence = scene.confidence

        # --- Plant identity ---
        evidence.crop_class = crop.crop_class
        evidence.crop_confidence = min(self.HEURISTIC_CROP_CEILING, crop.confidence)
        evidence.organ_class = organ.organ_class
        evidence.organ_confidence = min(self.HEURISTIC_ORGAN_CEILING, organ.confidence)

        # Composite plant identity confidence
        evidence.plant_identity_confidence = (
            evidence.crop_confidence * 0.6 + evidence.organ_confidence * 0.4
        )

        # --- Local canopy cover (only if canopy-valid organ) ---
        if organ.organ_class in (OrganClass.CANOPY, OrganClass.MIXED):
            evidence.local_canopy_cover = self._estimate_canopy_cover(features)
            evidence.canopy_cover_sigma = self.CANOPY_COVER_SIGMA * qa_sigma_inflation
        else:
            evidence.local_canopy_cover = 0.0
            evidence.canopy_cover_sigma = 0.50  # Very uncertain when not canopy view

        # --- Symptom evidence ---
        evidence.primary_symptom = symptom.primary_symptom
        evidence.local_symptom_score = symptom.severity
        evidence.symptom_sigma = self.SYMPTOM_SIGMA * qa_sigma_inflation

        # Disease probability: gated by crop confidence
        if symptom.has_symptoms:
            evidence.disease_symptom_prob = min(
                1.0,
                symptom.primary_confidence * (0.5 + evidence.crop_confidence * 0.5)
            )
        else:
            evidence.disease_symptom_prob = 0.0
        evidence.disease_sigma = self.DISEASE_SIGMA * qa_sigma_inflation
        evidence.disease_candidate = symptom.disease_candidate
        evidence.disease_candidate_confidence = min(
            self.HEURISTIC_DISEASE_CEILING,
            symptom.disease_confidence
        )

        # --- Phenology hint (very coarse) ---
        evidence.phenology_stage_est = self._estimate_phenology(features)
        evidence.phenology_sigma = self.PHENOLOGY_SIGMA * qa_sigma_inflation

        return evidence

    def _estimate_canopy_cover(self, features: PreprocessResult) -> float:
        """Estimate local canopy cover from green ratio."""
        green_r = features.green_ratio
        # ExG-like: scale green fraction to canopy cover
        cover = max(0.0, min(1.0, (green_r - 0.15) / 0.35))
        return round(cover, 3)

    def _estimate_phenology(self, features: PreprocessResult) -> float:
        """
        Coarse phenology stage hint from color ratios.

        0=dormant, 1=vegetative, 2=flowering, 3=ripening, 4=senescence
        """
        green_r = features.green_ratio
        saturation = features.saturation_mean
        brightness = features.brightness_mean
        yellow_r = features.yellow_ratio

        if green_r > 0.38 and saturation > 80:
            stage = 1.0 + (green_r - 0.38) * 5  # Vegetative
        elif green_r > 0.30:
            stage = 2.0  # Flowering-ish
        elif yellow_r > 0.15 and brightness > 120:
            stage = 3.0  # Ripening
        elif green_r < 0.22:
            stage = 3.5 + (0.22 - green_r) * 5  # Senescence
        else:
            stage = 1.5  # Uncertain mid-season

        return max(0.0, min(4.0, round(stage, 1)))
