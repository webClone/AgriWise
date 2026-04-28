"""
Farmer Photo — Scene Classifier (Gate).

Classifies the scene to gate out bad photos before processing.
Replaces the old pure QA-heuristic field gate.

Classes:
  - field_crop: Valid open field photo
  - crop_closeup: Valid close range shot (leaf, fruit, stem)
  - leaf_closeup: Specialized closeup
  - fruit_closeup: Specialized closeup
  - soil_scene: Valid bare soil
  - indoor_nonfield: Invalid indoor/selfie/junk
  - unusable: Invalid blurry/corrupted

V1.1: Fallback heuristic using image stats
V2: ONNX/TensorRT PyTorch CNN model.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

from layer0.perception.farmer_photo.schemas import SceneClass, SceneResult
from layer0.perception.farmer_photo.preprocess import PreprocessResult
from layer0.perception.farmer_photo.qa import FarmerPhotoQAResult, FarmerPhotoQAFlag

class SceneGate:
    """
    Classifies the overall image scene.
    
    Provides an ML-ready interface that can accept `image_array` or `resized_tensor`.
    """
    VERSION = "heuristic_v1.1"

    def __init__(self):
        self.model = None  # Placeholder for real CNN

    def predict(
        self,
        features: PreprocessResult,
        user_label: Optional[str] = None,
    ) -> SceneResult:
        """
        Predict the semantic scene class from image features.
        
        Args:
            features: Result from preprocessor (contains image stats and tensor)
            user_label: Optional user-provided label ("leaf", "fruit", etc.)
        """
        # If we had a loaded CNN model:
        if self.model and features.resized_tensor is not None:
             # Run CNN inference:
             # logits = self.model.predict(features.resized_tensor)
             # return self._map_logits(logits)
             pass 

        # V1.1 Fallback: Use image stats
        return self._heuristic_fallback(features, user_label=user_label)

    def _heuristic_fallback(
        self,
        features: PreprocessResult,
        user_label: Optional[str] = None,
    ) -> SceneResult:
        """Fallback rule-based semantic scene detection for V1.1.

        Decision cascade (D2 hardened):
          0. Synthetic/tarp rejection: extreme uniformity with no texture
          1. Early terminal NON_FIELD: indoor gray wall / dull neutral
          1a. Explicit green tarp rejection (D2.3A)
          1b. Isolated green on neutral (potted plant) rejection (D2.4A)
          2. CROP_CLOSEUP: high sat + high green + real texture
          3. soil_scene: R-dominant brown + low green
          4. FIELD: strong agricultural green with context, or true soil brown
          5. Default: NON_FIELD (not FIELD — ambiguous scenes must not leak)
        """
        green = features.green_ratio
        sat = features.saturation_mean
        brown = features.brown_ratio
        bstd = features.brightness_std
        gcf = features.green_coverage_fraction
        entropy = features.color_entropy
        uniformity = features.uniformity_score
        context_available = entropy > 0  # Only true when _from_synthetic or _load_real_image ran

        # --- Rule 0: Synthetic / tarp / test-card rejection ---
        # Perfectly uniform images (bstd ≈ 0) with extreme saturation are never
        # real agricultural scenes — UNLESS they're brown (soil has high sat from
        # R-G-B separation but is legitimately agricultural).
        if bstd < 3 and sat > 150 and brown < 0.20:
            return SceneResult(
                scene_class=SceneClass.NON_FIELD,
                confidence=0.7,
            )

        # --- Rule 1 (D2.1B): Terminal indoor/non-field rejection ---
        # Gray walls, documents, indoor junk: very low saturation, low texture,
        # and no strong green/brown signal.  TERMINAL — fires before anything else.
        if sat < 25 and green < 0.36 and brown < 0.15 and bstd < 12:
            return SceneResult(
                scene_class=SceneClass.NON_FIELD,
                confidence=0.6,
            )

        # --- Rule 1a (D2.3A): Explicit green tarp rejection ---
        # Vivid synthetic green but lacking true canopy texture.
        # Must fire BEFORE crop-closeup to prevent tarps from entering that path.
        # Two-tier threshold:
        #   - Without context (pixel_stats only): bstd < 20 (aggressive)
        #   - With context (synthetic pixels): bstd < 12 (precise —
        #     real canopies like olive=14, citrus=16 have natural variation)
        tarp_bstd_threshold = 12 if context_available else 20
        if green > 0.45 and sat > 120 and bstd < tarp_bstd_threshold and brown < 0.12:
            return SceneResult(
                scene_class=SceneClass.NON_FIELD,
                confidence=0.7,
            )

        # --- Rule 1b (D2.4A): Isolated green on neutral (potted plant) ---
        # Weak green on a neutral background. A true field has either
        # high green (>0.45) or visible soil (brown>0.15), and field-level
        # saturation. This catches isolated houseplants on gray backgrounds.
        if brown < 0.12 and green < 0.42 and sat < 65:
            return SceneResult(
                scene_class=SceneClass.NON_FIELD,
                confidence=0.55,
                details={"subclass": "potted_garden"},
            )

        # --- Rule 1c (E1.1): Red/brown OOD rejection ---
        # Uniform non-green brown/red surfaces: red objects, red walls, clothing.
        # Key signal: high brown_ratio but near-zero green coverage (real soil
        # always has some green from weeds/moss, or higher entropy from clods).
        if (context_available and brown >= 0.25 and gcf < 0.05
                and entropy < 1.5
                and bstd < 12 and green < 0.30):
            return SceneResult(
                scene_class=SceneClass.NON_FIELD,
                confidence=0.6,
                details={"subclass": "red_object"},
            )

        # --- Rule 2 (D2.3B): Crop close-up ---
        # Requires strong texture (20 < bstd < 40) — real leaves have veins,
        # shadows, light variation. Synthetic green is already filtered above.
        if sat > 85 and green > 0.35 and bstd > 20 and bstd < 40:
            return SceneResult(
                scene_class=SceneClass.CROP_CLOSEUP,
                confidence=0.65,
            )

        # --- Rule 2b (E1): Manufactured brown surface rejection ---
        # Brown objects like wood, furniture, packaging: moderate brown, near-zero
        # green coverage, very low texture (smooth surface), and low entropy.
        # Real soil has higher bstd (cloddy) and typically some green (weeds).
        if (context_available and brown >= 0.20 and gcf < 0.01 and bstd < 8
                and entropy < 1.2 and green < 0.35):
            return SceneResult(
                scene_class=SceneClass.NON_FIELD,
                confidence=0.55,
                details={"subclass": "indoor_gray"},
            )

        # --- Rule 3 (D2.2B): Soil scene ---
        # Inclusive soil gate using true earth-tone brown_ratio.
        # No texture restriction — real soil is cloddy and highly textured.
        # OVERRIDE: When user explicitly labels the image as leaf/fruit/stem,
        # brown dominance is from the specimen (rust, ripe fruit), not soil.
        label_is_crop_organ = user_label and user_label.lower() in ("leaf", "fruit", "stem")
        if brown >= 0.25 and green <= 0.35 and not label_is_crop_organ:
            return SceneResult(
                scene_class="soil_scene",
                confidence=0.6,
                details={"subclass": "soil_scene"},
            )
        # Second tier: very brown, very uniform reddish soils
        if brown >= 0.60 and bstd < 10 and green < 0.38:
            return SceneResult(
                scene_class="soil_scene",
                confidence=0.55,
                details={"subclass": "soil_scene"},
            )
        # Third tier (E1): Sandy/pale soils with moderate brown + near-zero green coverage.
        # Sandy soil has lower brown_ratio due to lighter colors, but still no real vegetation.
        if context_available and brown >= 0.18 and gcf < 0.10 and green < 0.38 and sat < 100:
            return SceneResult(
                scene_class="soil_scene",
                confidence=0.50,
                details={"subclass": "soil_scene"},
            )

        # --- Rule 4 (D2.1A, D2.4B): Agricultural field ---
        # FIELD requires STRONG evidence:
        #   - Green dominant WITH context (sat > 40 or visible soil brown > 0.15)
        #   - OR true agricultural brownness
        # DELETED: has_color_saturation (sat >= 40 and green < 0.36)
        # DELETED: has_moderate_field_signal (sat > 45 and green > 0.30)
        # Those weak fallbacks let indoor walls and ambiguous scenes leak in.
        is_green_dominant_with_context = green > 0.36 and (sat > 40 or brown > 0.15)
        has_brown = brown >= 0.20

        if is_green_dominant_with_context or has_brown:
            return SceneResult(
                scene_class=SceneClass.FIELD,
                confidence=0.5,
            )

        # --- Default (D2.1C): Not enough evidence -> NON_FIELD ---
        # Ambiguous scenes MUST NOT become FIELD.
        return SceneResult(
            scene_class=SceneClass.NON_FIELD,
            confidence=0.5,
        )
