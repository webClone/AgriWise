"""
IP Camera Inference — extracts agronomic variables from PreprocessResult stats.

Primary (high confidence):
  - canopy_cover       ← green_coverage_fraction
  - phenology_stage_est ← green/brown ratio heuristic

Secondary (high uncertainty):
  - visible_stress_prob   ← yellow_ratio
  - disease_symptom_prob  ← yellow_ratio * cautious multiplier
"""

from __future__ import annotations
from typing import Any, List

from layer0.perception.common.contracts import PerceptionVariable
from layer0.perception.ip_camera.schemas import IPCameraSceneContext, SceneChangeType
from layer0.perception.ip_camera.preprocess import PreprocessResult


class IPCameraInference:
    """
    Core inference logic for fixed IP cameras.
    Derives agronomic variables from preprocessed frame statistics.
    """

    def run_inference(
        self,
        preprocess: PreprocessResult,
        context: IPCameraSceneContext,
    ) -> List[PerceptionVariable]:
        variables = []

        # --- Confidence modulation from scene stability ---
        # If lighting shifted, color-derived variables are less trustworthy
        confidence_mod = 1.0
        if context.scene_change_type == SceneChangeType.LIGHTING_SHIFT:
            confidence_mod = 0.6
        elif context.scene_change_type == SceneChangeType.CAMERA_SHIFT:
            confidence_mod = 0.3  # camera moved — don't trust anything much

        # === 1. Canopy Cover (primary) ===
        # green_coverage_fraction is the most direct proxy
        canopy = preprocess.green_coverage_fraction
        variables.append(
            PerceptionVariable(
                name="canopy_cover",
                value=canopy,
                sigma=0.08,
                confidence=0.9 * confidence_mod,
                unit="fraction",
            )
        )

        # === 2. Phenology Stage Estimate (primary) ===
        # Heuristic: high green + low brown -> vegetative
        #            declining green + rising brown -> senescence
        green = preprocess.green_ratio
        brown = preprocess.brown_ratio
        yellow = preprocess.yellow_ratio

        # Simple 0-4 staging:
        #   0-1: emergence (low green, some soil)
        #   1-2: vegetative (high green)
        #   2-3: reproductive (green + yellow)
        #   3-4: senescence (brown dominating)
        if green > 0.40:
            stage = 1.5 + min(1.0, green / 0.5)  # 1.5 - 2.5
        elif brown > 0.15:
            stage = 3.0 + min(1.0, brown / 0.3)  # 3.0 - 4.0
        elif yellow > 0.1:
            stage = 2.5 + min(0.5, yellow / 0.2)  # 2.5 - 3.0
        else:
            stage = preprocess.phenology_stage_est  # fallback to mock/prior

        variables.append(
            PerceptionVariable(
                name="phenology_stage_est",
                value=stage,
                sigma=0.50,
                confidence=0.7 * confidence_mod,
                unit="bbch",
            )
        )

        # === 3. Visible Stress Probability (secondary) ===
        stress = yellow + brown * 0.5
        stress = min(1.0, stress)
        variables.append(
            PerceptionVariable(
                name="visible_stress_prob",
                value=stress,
                sigma=0.30,
                confidence=0.7 * confidence_mod,
                unit="probability",
            )
        )

        # === 4. Disease Symptom Probability (cautious) ===
        # Deliberately kept very uncertain — only yellow with high confidence triggers
        disease = yellow * 0.3
        variables.append(
            PerceptionVariable(
                name="disease_symptom_prob",
                value=disease,
                sigma=0.40,
                confidence=0.3 * confidence_mod,
                unit="probability",
            )
        )

        return variables
