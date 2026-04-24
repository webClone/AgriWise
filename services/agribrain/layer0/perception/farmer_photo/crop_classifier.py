"""
Farmer Photo — Crop Classifier.

Identifies crop/plant family from close-range photo features.

V1: Heuristic classifier from color/texture statistics.
    Structured so a MobileNetV3 / EfficientNet-B0 can replace
    the predict() method without changing the pipeline.

V2+: Trained CNN on labeled crop image datasets.

Classes:
  wheat, maize, tomato, potato, olive, citrus, unknown_crop

Design rule:
  If crop confidence is low, disease reasoning MUST be downgraded.
  A disease diagnosis without knowing the crop is nearly meaningless.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

from .schemas import CropClass, CropResult
from .preprocess import PreprocessResult


class CropClassifier:
    """
    Crop family classifier.

    V1.1: Partial ML-ready integration with softer user hints.
    Production: swap predict() for a trained CNN.

    Usage:
        classifier = CropClassifier()
        result = classifier.predict(preprocess_result, crop_hint="wheat")
    """
    VERSION = "heuristic_v1.1"

    def __init__(self):
        # Placeholder for real PyTorch/ONNX model
        self.model = None

    def predict(
        self,
        features: PreprocessResult,
        crop_hint: Optional[str] = None,
    ) -> CropResult:
        """
        Classify the visible crop from image features.

        Args:
            features: normalized pixel statistics from preprocessor
            crop_hint: optional plot-level crop type from metadata

        Returns:
            CropResult with crop class, confidence, and top candidates.
        """
        candidates: Dict[str, float] = {}
        assisted = False

        # --- ML Inference ---
        if self.model is not None and features.resized_tensor is not None:
             # Run CNN inference:
             # logits = self.model.predict(features.resized_tensor)
             pass

        green_r = features.green_ratio
        yellow_r = features.yellow_ratio
        red_r = features.red_ratio
        saturation = features.saturation_mean
        brightness = features.brightness_mean

        # --- Heuristic scoring per crop ---
        # V1.3: Multi-feature profiles for hint-free discrimination.
        # Without a CNN, we use saturation, brightness, and green_ratio jointly
        # to separate crops that would otherwise all look "green."

        # Wheat: moderate green, moderate saturation, lighter appearance
        # Vegetative wheat: green 0.35-0.55, sat 120-175, bright > 75
        # Mature wheat: lower green, higher yellow (handled by yellow path)
        wheat_score = 0.0
        if 0.25 < green_r < 0.45 and yellow_r > 0.1:
            wheat_score = 0.4 + yellow_r * 0.3  # Golden/mature wheat
        elif 0.33 < green_r < 0.52 and 120 < saturation < 180 and brightness > 75:
            wheat_score = 0.35  # Vegetative wheat — moderate everything
        elif 0.30 < green_r < 0.45:
            wheat_score = 0.25
        elif 0.45 <= green_r < 0.55:
            wheat_score = 0.20  # Very green wheat — lower confidence
        candidates[CropClass.WHEAT] = min(1.0, wheat_score)

        # Maize: strong green, HIGH saturation, tall canopy
        # Key discriminator: sat > 180 separates maize from wheat/potato
        maize_score = 0.0
        if green_r > 0.50 and saturation > 180:
            maize_score = 0.50 + (green_r - 0.50) * 1.5  # Strong maize signal
        elif green_r > 0.40 and saturation > 160:
            maize_score = 0.30 + (green_r - 0.40) * 1.0  # Moderate maize
        elif green_r > 0.35 and saturation > 80:
            maize_score = 0.20  # Weak maize — could be any green crop
        candidates[CropClass.MAIZE] = min(1.0, maize_score)

        # Tomato: red at fruit stage, green at vegetative
        tomato_score = 0.0
        if red_r > 0.38 and green_r < 0.30:
            tomato_score = 0.5  # Fruit visible
        elif green_r > 0.35 and saturation > 90:
            tomato_score = 0.15  # Could be tomato in veg stage (weak)
        candidates[CropClass.TOMATO] = min(1.0, tomato_score)

        # Potato: moderate green, LOWER saturation (100-155), moderate brightness
        # Key discriminator: sat < 155 separates potato from maize
        potato_score = 0.0
        if 0.35 < green_r < 0.48 and 90 < saturation < 155 and brightness > 70:
            potato_score = 0.30  # Moderate green + lower sat = potato profile
        elif 0.28 < green_r < 0.42 and saturation > 60:
            potato_score = 0.15
        candidates[CropClass.POTATO] = min(1.0, potato_score)

        # Olive: dark green canopy, LOW brightness (< 75), lower saturation
        # Key discriminator: brightness < 75 + moderate sat
        olive_score = 0.0
        if green_r > 0.35 and brightness < 75 and saturation < 160:
            olive_score = 0.35  # Dark green = olive/citrus region
            if saturation < 145:
                olive_score = 0.40  # Lower sat favors olive over citrus
        elif green_r > 0.30 and saturation < 100 and brightness < 140:
            olive_score = 0.20
        candidates[CropClass.OLIVE] = min(1.0, olive_score)

        # Citrus: deep green, LOW brightness (< 75), moderate-high saturation
        # Key discriminator: deeper green than olive, higher sat
        citrus_score = 0.0
        if green_r > 0.42 and brightness < 75 and saturation > 140:
            citrus_score = 0.40  # Deep green + higher sat = citrus
        elif green_r > 0.32 and 70 < saturation < 140:
            citrus_score = 0.15
        candidates[CropClass.CITRUS] = min(1.0, citrus_score)

        # --- Find best candidate ---
        best_class = CropClass.UNKNOWN
        best_score = 0.0
        for cls, score in candidates.items():
            if score > best_score:
                best_score = score
                best_class = cls

        # --- Apply crop hint boost ---
        # Design principle: The hint is a SOFT tiebreaker, not a hard override.
        # When crops are visually ambiguous (wheat vs maize at green canopy),
        # the hint tips the balance. But it should NEVER override a strong
        # visual signal (e.g., hint=wheat on a clearly saturated maize canopy).
        if crop_hint:
            hint_lower = crop_hint.lower()
            for cls in candidates:
                if hint_lower in cls.lower():
                    base_score = candidates[cls]
                    # Soft boost: add 20% of base + small fixed margin
                    # This beats ties but doesn't override strong signals
                    if base_score > 0.10:
                        boosted = base_score * 1.20 + 0.05
                        # Only override visual winner if hint score is within
                        # 60% of the visual winner (i.e., not a strong contradiction)
                        if boosted > best_score or base_score >= best_score * 0.60:
                            candidates[cls] = min(0.75, boosted)
                            assisted = True
                    elif green_r > 0.25:
                        # Hint floor: image is agricultural but no visual match.
                        # Give minimum score to participate in tiebreak.
                        candidates[cls] = min(0.30, best_score * 0.90)
                        assisted = True
                    if candidates[cls] > best_score:
                        best_score = candidates[cls]
                        best_class = cls

        # --- Confidence calibration ---
        # Heuristic: max score capped at 0.60 (no CNN = never high confidence)
        # But if assisted by hint, we can boost the ceiling
        confidence = min(0.60 if not assisted else 0.85, best_score)

        # If nothing scored above 0.15, return unknown
        if best_score < 0.15:
            best_class = CropClass.UNKNOWN
            confidence = 0.0

        return CropResult(
            crop_class=best_class,
            confidence=round(confidence, 3),
            top_candidates={k: round(v, 3) for k, v in
                           sorted(candidates.items(), key=lambda x: -x[1])[:3]},
            assisted_by_hint=assisted
        )
