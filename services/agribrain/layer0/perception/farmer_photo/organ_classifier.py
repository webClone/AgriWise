"""
Farmer Photo — Organ Classifier.

Identifies what part of the plant is visible in the photo.
This determines which inference models run:

  CANOPY  -> canopy cover + phenology
  LEAF    -> symptom detection (primary disease evidence source)
  FRUIT   -> maturity hint + fruit symptom detection
  STEM    -> structural symptoms only
  SOIL    -> bare soil confirmation (auxiliary)
  MIXED   -> all models, lower confidence
  UNKNOWN -> all models, very low confidence

V1: Heuristic from image features (FOV, texture, color composition).
V2: Trained CNN on organ-labeled crop image datasets.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

from layer0.perception.farmer_photo.schemas import OrganClass, OrganResult
from layer0.perception.farmer_photo.preprocess import PreprocessResult


class OrganClassifier:
    """
    Organ/context classifier: what part of the crop is visible.

    V1: Heuristic from image-level statistics.
    V1.1: Partial ML-ready integration with softer user hints.
    Production: swap predict() for a trained CNN.

    Usage:
        classifier = OrganClassifier()
        result = classifier.predict(preprocess_result)
    """
    VERSION = "heuristic_v1.1"

    def __init__(self):
        # Placeholder for real PyTorch/ONNX model
        self.model = None

    def predict(
        self,
        features: PreprocessResult,
        user_label: Optional[str] = None,
    ) -> OrganResult:
        """
        Classify the visible organ/context from image features.

        Args:
            features: normalized pixel statistics from preprocessor
            user_label: optional user-provided label hint

        Returns:
            OrganResult with organ class and confidence.
        """
        assisted = False
        if user_label:
            label = user_label.lower()
            label_map = {
                "leaf": OrganClass.LEAF,
                "canopy": OrganClass.CANOPY,
                "fruit": OrganClass.FRUIT,
                "stem": OrganClass.STEM,
                "soil": OrganClass.SOIL,
            }
            if label in label_map:
                assisted = True
                user_target = label_map[label]
            else:
                user_target = None
        else:
            user_target = None

        # --- ML Inference ---
        if self.model is not None and features.resized_tensor is not None:
             # Run CNN inference:
             # logits = self.model.predict(features.resized_tensor)
             pass
             
        # --- Heuristic classification from features ---
        green_r = features.green_ratio
        saturation = features.saturation_mean
        brightness = features.brightness_mean
        brightness_std = features.brightness_std
        megapixels = features.megapixels
        red_r = features.red_ratio

        scores: Dict[str, float] = {}

        # CANOPY: high green, moderate field of view, moderate texture
        canopy_score = 0.0
        if green_r > 0.30 and saturation > 60:
            canopy_score = 0.35
            if brightness_std > 20:
                canopy_score += 0.15  # Texture from mixed canopy
        # E2.2: green_coverage_fraction boost — high gcf means green fills the frame
        # (canopy view), not a single leaf on a background
        gcf = features.green_coverage_fraction
        if gcf > 0.50 and green_r > 0.35:
            canopy_score += 0.25  # Strong canopy signal from field-of-view context
        elif gcf > 0.30 and green_r > 0.35:
            canopy_score += 0.10  # Moderate canopy signal
        # D2.2C: Suppress canopy when brown dominates and green is low (soil scene)
        if features.brown_ratio > 0.25 and green_r < 0.30:
            canopy_score *= 0.2
        # Golden/senescent canopy: high yellow + moderate green + texture = harvest-ready
        # field, not a leaf closeup. Yellow dominance at field scale = mature canopy.
        if features.yellow_ratio > 0.35 and green_r > 0.30 and brightness_std > 15:
            canopy_score = max(canopy_score, 0.55)
        scores[OrganClass.CANOPY] = canopy_score

        # LEAF: high green, high saturation, typically close-up
        leaf_score = 0.0
        if green_r > 0.33 and saturation > 80:
            leaf_score = 0.30
            if brightness_std < 40:
                leaf_score += 0.15  # Lower texture = single leaf surface
        # D2.2C: Suppress leaf when brown dominates and texture is very low (soil, not leaf)
        if features.brown_ratio > 0.25 and green_r < 0.30 and brightness_std < 15:
            leaf_score *= 0.1
        scores[OrganClass.LEAF] = leaf_score

        # FRUIT: higher red or yellow, lower green dominance
        fruit_score = 0.0
        if red_r > 0.35 and green_r < 0.35:
            fruit_score = 0.40  # Red/orange fruit visible
        elif features.yellow_ratio > 0.15:
            fruit_score = 0.25  # Small yellow signal
        scores[OrganClass.FRUIT] = fruit_score

        # STEM: low saturation, brownish, linear texture
        stem_score = 0.0
        if saturation < 60 and features.brown_ratio > 0.3:
            stem_score = 0.25
        scores[OrganClass.STEM] = stem_score

        # SOIL: primary signal is brown_ratio (R-dominant, reddish-brown earth tones)
        # Also requires low green — soil has minimal visible chlorophyll.
        soil_score = 0.0
        if features.brown_ratio >= 0.25 and green_r <= 0.35:
            # Margin-safe composite soil gate (texture agnostic — real soil is cloddy)
            soil_score = 0.50 + features.brown_ratio * 0.4
        elif features.brown_ratio > 0.60 and green_r < 0.38:
            # Strong brown soil
            soil_score = 0.60 + features.brown_ratio * 0.3
        elif features.brown_ratio > 0.50 and green_r <= 0.34:
            # Strong brown dominance
            soil_score = 0.50 + features.brown_ratio * 0.3
        elif features.brown_ratio > 0.30 and green_r < 0.25:
            soil_score = 0.45 + features.brown_ratio * 0.3
        elif green_r < 0.25 and saturation < 80:
            soil_score = 0.35  # Fallback: low green + low sat
            if features.brown_ratio > 0.15:
                soil_score += 0.20
        if green_r < 0.20:
            soil_score += 0.20
        # E2: Context-based soil tier — sandy/pale soils with moderate brown
        # but near-zero green coverage (no real vegetation visible)
        if gcf < 0.10 and features.brown_ratio >= 0.15 and green_r < 0.38:
            soil_score = max(soil_score, 0.50)
        scores[OrganClass.SOIL] = min(1.0, soil_score)

        # Soft constraint: If user passed a hint, we boost it heavily.
        # User explicitly labeling an organ is strong first-person evidence.
        if assisted and user_target in scores:
            scores[user_target] += 0.80
            # If user says leaf/fruit/stem, suppress soil — the brown pixels
            # are from the specimen (rust, ripe fruit), not bare earth.
            if user_target in (OrganClass.LEAF, OrganClass.FRUIT, OrganClass.STEM):
                scores[OrganClass.SOIL] = min(scores.get(OrganClass.SOIL, 0), 0.15)

        # --- Best candidate ---
        best_class = OrganClass.UNKNOWN
        best_score = 0.0
        for cls, score in scores.items():
            if score > best_score:
                best_score = score
                best_class = cls

        # If multiple classes are close, call it MIXED
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2:
            gap = sorted_scores[0] - sorted_scores[1]
            # Don't demote to mixed if:
            # 1) The user-assisted class cleanly won as top score, OR
            # 2) The user-assisted class is within the gap threshold of top score
            #    (user domain knowledge should resolve near-ties, not create MIXED)
            user_within_gap = (
                assisted and user_target in scores
                and (scores.get(user_target, 0) >= sorted_scores[0] - 0.08)
            )
            if gap < 0.08 and sorted_scores[0] > 0.2:
                if not ((assisted and best_class == user_target) or user_within_gap):
                    best_class = OrganClass.MIXED
                    best_score = sorted_scores[0] * 0.8  # Lower confidence
                elif user_within_gap:
                    # Trust the user label
                    best_class = user_target
                    best_score = scores[user_target]

        # If nothing scored above 0.15, return UNKNOWN
        if best_score < 0.15:
            best_class = OrganClass.UNKNOWN
            best_score = 0.0

        # Cap confidence for heuristic-only
        confidence = min(0.55 if not assisted else 0.70, best_score)

        return OrganResult(
            organ_class=best_class if (user_target is None or best_score >= 0.3) else user_target,
            confidence=round(confidence, 3),
            assisted_by_user_label=(user_target == best_class) or (best_score < 0.3 and assisted)
        )
