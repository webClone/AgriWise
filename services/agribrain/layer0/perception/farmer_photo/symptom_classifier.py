"""
Farmer Photo — Symptom Classifier.

Symptom-first, not disease-first.

This module detects VISIBLE SYMPTOMS from close-range photos:
  healthy, chlorosis, necrosis, spots, mildew_like, rust_like,
  blight_like, insect_damage, wilt, unknown_stress

It then optionally maps (symptoms + crop class) -> disease candidate.
The disease candidate is ALWAYS a weak suggestion (confidence < 0.40).

Design rules:
  - If crop ID is weak -> disease confidence is downgraded
  - If organ type is wrong for disease -> symptom inference is suppressed
  - Symptom probability is useful evidence; disease name is speculation
  - All outputs carry explicit uncertainty

V1: Heuristic from color/texture features.
V2: Trained symptom classification CNN.
V3: Multi-task: crop + organ + symptom + severity in one model.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import math

from layer0.perception.farmer_photo.schemas import (
    SymptomClass, SymptomResult, OrganClass, CropClass,
    ALL_SYMPTOM_CLASSES,
)
from layer0.perception.farmer_photo.preprocess import PreprocessResult


# ============================================================================
# Symptom -> Disease mapping (weak associations)
# ============================================================================

# Maps (symptom, crop) -> disease candidate name
# These are WEAK suggestions, not diagnoses
SYMPTOM_DISEASE_MAP: Dict[str, Dict[str, str]] = {
    SymptomClass.CHLOROSIS: {
        CropClass.WHEAT: "nitrogen_deficiency_or_yellows",
        CropClass.MAIZE: "nitrogen_deficiency",
        CropClass.TOMATO: "iron_chlorosis_or_virus",
        CropClass.POTATO: "virus_or_nutrient_deficiency",
        CropClass.CITRUS: "iron_chlorosis",
        CropClass.UNKNOWN: "nutrient_deficiency_general",
    },
    SymptomClass.RUST_LIKE: {
        CropClass.WHEAT: "wheat_rust",
        CropClass.MAIZE: "common_rust",
        CropClass.UNKNOWN: "rust_unspecified",
    },
    SymptomClass.MILDEW_LIKE: {
        CropClass.WHEAT: "powdery_mildew",
        CropClass.TOMATO: "downy_or_powdery_mildew",
        CropClass.POTATO: "late_blight_or_mildew",
        CropClass.UNKNOWN: "mildew_unspecified",
    },
    SymptomClass.BLIGHT_LIKE: {
        CropClass.POTATO: "late_blight",
        CropClass.TOMATO: "early_or_late_blight",
        CropClass.UNKNOWN: "blight_unspecified",
    },
    SymptomClass.SPOTS: {
        CropClass.WHEAT: "septoria_or_tan_spot",
        CropClass.TOMATO: "bacterial_spot_or_early_blight",
        CropClass.UNKNOWN: "leaf_spot_unspecified",
    },
    SymptomClass.WILT: {
        CropClass.TOMATO: "fusarium_or_verticillium_wilt",
        CropClass.POTATO: "bacterial_wilt",
        CropClass.UNKNOWN: "wilt_unspecified",
    },
    SymptomClass.INSECT_DAMAGE: {
        CropClass.MAIZE: "stem_borer_or_armyworm",
        CropClass.WHEAT: "aphid_or_cereal_leaf_beetle",
        CropClass.UNKNOWN: "insect_damage_unspecified",
    },
}


class SymptomClassifier:
    """
    Symptom-first plant stress classifier.

    Detects visible symptoms from color/texture features and
    optionally suggests a disease candidate. The disease candidate
    is gated by crop confidence — no crop ID means no specific diagnosis.

    V1.1: ML-ready interface (supports logits/masks).
    V2+: Trained CNN with symptom class softmax.

    Usage:
        classifier = SymptomClassifier()
        result = classifier.predict(features, organ_class="leaf", crop_class="wheat")
    """
    VERSION = "heuristic_v1.1"

    def __init__(self):
        # Placeholder for real PyTorch/ONNX model
        self.model = None

    # Organ types where symptom detection is meaningful
    SYMPTOM_VALID_ORGANS = {
        OrganClass.LEAF,
        OrganClass.CANOPY,
        OrganClass.FRUIT,
        OrganClass.MIXED,
    }

    def predict(
        self,
        features: PreprocessResult,
        organ_class: str = OrganClass.UNKNOWN,
        crop_class: str = CropClass.UNKNOWN,
        crop_confidence: float = 0.0,
    ) -> SymptomResult:
        """
        Classify visible symptoms from image features.

        Args:
            features: normalized pixel statistics
            organ_class: detected organ type
            crop_class: detected crop class
            crop_confidence: crop classification confidence

        Returns:
            SymptomResult with per-class probabilities and disease candidate.
        """
        # --- Gate: suppress if organ is wrong for symptom detection ---
        if organ_class in (OrganClass.SOIL, OrganClass.STEM, OrganClass.UNKNOWN):
            return SymptomResult(
                symptom_scores={SymptomClass.HEALTHY: 1.0},
                primary_symptom=SymptomClass.HEALTHY,
                primary_confidence=0.0,
                severity=0.0,
                disease_candidate="",
                disease_confidence=0.0,
            )

        # --- Compute per-symptom scores ---
        # 1. Try ML model if loaded
        if self.model is not None and features.resized_tensor is not None:
            # logits = self.model.predict(features.resized_tensor)
            # scores = self._softmax_to_dict(logits)
            scores = {}
        else:
            # 2. V1.1 Heuristic fallback
            scores = self._compute_symptom_scores(features, organ_class)

        # Normalize to sum ≈ 1.0
        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        # --- Find primary symptom ---
        primary = max(scores, key=scores.get)
        primary_score = scores[primary]
        
        # Tiebreaking: when symptoms tie, use feature dominance
        if (primary == SymptomClass.CHLOROSIS
                and scores.get(SymptomClass.NECROSIS, 0) >= primary_score * 0.95
                and features.brown_ratio > features.yellow_ratio):
            primary = SymptomClass.NECROSIS
            primary_score = scores[primary]
        
        # Tiebreak: Rust vs Chlorosis/Necrosis — very high red + vivid sat = rust
        if primary in (SymptomClass.CHLOROSIS, SymptomClass.NECROSIS):
            rust_s = scores.get(SymptomClass.RUST_LIKE, 0)
            if (rust_s >= primary_score * 0.85
                    and features.red_ratio > 0.50
                    and features.saturation_mean > 150):
                primary = SymptomClass.RUST_LIKE
                primary_score = scores[primary]
        
        # Tiebreak: Insect vs Spots — high entropy + green + high rel_std = insect
        if primary == SymptomClass.SPOTS:
            insect_s = scores.get(SymptomClass.INSECT_DAMAGE, 0)
            rel_std = features.brightness_std / max(features.brightness_mean, 1)
            if (insect_s >= primary_score * 0.50
                    and features.color_entropy > 2.5
                    and features.green_ratio > 0.35
                    and rel_std > 0.39):
                primary = SymptomClass.INSECT_DAMAGE
                primary_score = scores[primary]

        # --- Severity estimation ---
        severity = self._estimate_severity(features, primary)

        # --- Disease candidate (gated by crop confidence) ---
        disease_candidate = ""
        disease_confidence = 0.0

        if primary != SymptomClass.HEALTHY and crop_confidence > 0.15:
            candidate_map = SYMPTOM_DISEASE_MAP.get(primary, {})
            disease_candidate = candidate_map.get(
                crop_class,
                candidate_map.get(CropClass.UNKNOWN, "")
            )
            # Disease confidence is ALWAYS weak:
            # symptom_confidence * crop_confidence * 0.50 cap
            disease_confidence = min(0.40, primary_score * crop_confidence * 0.8)

        # --- Confidence calibration ---
        # Heuristic symptom detection is inherently weak
        confidence = min(0.50, primary_score)

        return SymptomResult(
            symptom_scores={k: round(v, 3) for k, v in scores.items()},
            primary_symptom=primary,
            primary_confidence=round(confidence, 3),
            severity=round(severity, 3),
            disease_candidate=disease_candidate,
            disease_confidence=round(disease_confidence, 3),
        )

    def _compute_symptom_scores(self, features: PreprocessResult, organ_class: str) -> Dict[str, float]:
        """Compute raw symptom probability scores from color features."""
        scores: Dict[str, float] = {}
        green_r = features.green_ratio
        red_r = features.red_ratio
        yellow_r = features.yellow_ratio
        brown_r = features.brown_ratio
        saturation = features.saturation_mean
        brightness = features.brightness_mean

        # HEALTHY: high green, good saturation, no dominant yellowing
        healthy_score = 0.0
        # Use relative metric: yellowing is concerning only when yellow_ratio
        # approaches or exceeds green_ratio. A green leaf with yellow=0.37 and
        # green=0.54 is clearly healthy (yellow/green = 0.69 << 1.0).
        yellow_to_green = yellow_r / max(green_r, 0.01)
        
        if green_r > 0.33 and saturation > 70 and yellow_to_green < 0.85:
            healthy_score = 0.5 + (green_r - 0.33) * 2
        elif green_r > 0.28 and yellow_to_green < 1.0:
            healthy_score = 0.3
        
        # Global penalty: yellowing that rivals or exceeds green is not healthy.
        # But mature golden canopies are naturally yellow, so exempt them.
        if yellow_to_green > 0.95 and organ_class not in {"canopy", "mixed"}:
            healthy_score = max(0.0, healthy_score - (yellow_to_green - 0.95) * 3.0)
            if yellow_to_green > 1.2:
                healthy_score = min(healthy_score, 0.15)  # Strict cap for clear yellowing
        elif organ_class == "leaf" and yellow_to_green > 0.90:
            healthy_score = max(0.0, healthy_score - (yellow_to_green - 0.90) * 3.0)
            if yellow_to_green > 1.1:
                healthy_score = min(healthy_score, 0.15)  # Strict cap
        
        # E4.3: Fruit organ exemption — redness/yellowness is natural for fruit
        if organ_class == "fruit":
            healthy_score = max(healthy_score, 0.60)
        
        # E4.3: Canopy/mixed golden maturity — high sat yellow canopy is healthy
        # (mature wheat, golden crop). This overrides the y/g penalty for canopy.
        if organ_class in {"canopy", "mixed"} and saturation > 120 and yellow_to_green > 0.90:
            healthy_score = max(healthy_score, 0.50)
        
        scores[SymptomClass.HEALTHY] = min(1.0, healthy_score)

        # CHLOROSIS: yellowing — high yellow_ratio, dropping green
        chlorosis_score = 0.0
        if yellow_r > 0.08:
            chlorosis_score = yellow_r * 3
        if green_r < 0.28 and brightness > 100:
            chlorosis_score += 0.2
            
        if green_r > 0.40:
            # Chlorosis means loss of green. If heavily green, suppress more strictly.
            chlorosis_score *= 0.1
        elif green_r > 0.33:
            # High green shouldn't yield extreme chlorosis regardless of yellow tone
            chlorosis_score *= 0.4

        # Saturation check: real chlorosis causes pigment loss -> low saturation.
        # High saturation + yellow = natural golden maturity (ripe wheat), not disease.
        # BUT: this suppression ONLY applies to canopy or mixed scenes. Single leaves
        # must be allowed to register vibrant saturated chlorosis.
        if saturation > 100 and yellow_r > 0.15 and organ_class in {"canopy", "mixed"}:
            chlorosis_score *= 0.3  # Strong suppression for vibrant golden canopy
        
        # Uniformity check: perfectly uniform brightness (very low std) suggests
        # natural uniform coloring, not patchy chlorosis
        if features.brightness_std < 10 and yellow_r > 0.2:
            chlorosis_score *= 0.5
            
        scores[SymptomClass.CHLOROSIS] = min(1.0, chlorosis_score)

        # NECROSIS: browning — brown patches mixed with remaining green tissue
        necrosis_score = 0.0
        if brown_r > 0.10 and green_r < 0.40:
            necrosis_score = brown_r * 2.5
            # Stronger necrosis signal when green is really low
            if green_r < 0.28:
                necrosis_score += 0.2
        if saturation < 50 and green_r < 0.25:
            necrosis_score += 0.2
        # Guard: if yellow dominates brown, the primary signal is yellowing (chlorosis),
        # not browning (necrosis). True necrosis has brown >= yellow.
        if yellow_r > brown_r and yellow_r > 0.20:
            # Scale suppression by how much yellow exceeds brown
            suppression = min(0.85, (yellow_r - brown_r) / max(brown_r, 0.01) * 0.3)
            necrosis_score *= max(0.15, 1.0 - suppression)
        # Golden canopy/mixed guard: high sat + high yellow on canopy = natural
        # ripening, not pathological necrosis. Suppress strongly.
        if organ_class in {"canopy", "mixed"} and saturation > 120 and yellow_r > 0.35:
            necrosis_score *= 0.2
        scores[SymptomClass.NECROSIS] = min(1.0, necrosis_score)

        # SPOTS: high brightness std (spotted texture) — lesion irregularity
        spots_score = 0.0
        context_available = features.color_entropy > 0
        if features.brightness_std > 25:
            spots_score = (features.brightness_std - 25) / 20
            # Strong combo: high noise on a green surface -> likely actual lesion spots
            # Only apply when context features confirm real pixel data (not defaults)
            # BUT: suppress when rel_std is very high (> 0.35), indicating
            # deep perforations (insect holes) rather than surface lesion spots
            if context_available and green_r > 0.40 and features.brightness_std > 28:
                rel_std = features.brightness_std / max(brightness, 1)
                if rel_std < 0.40:
                    spots_score += 0.40
                else:
                    spots_score += 0.10  # Reduced boost for perforation-like patterns
        scores[SymptomClass.SPOTS] = min(1.0, spots_score)

        # If spots signal is strong (with context confirmation), suppress healthy
        if context_available and spots_score >= 0.50:
            scores[SymptomClass.HEALTHY] = min(
                scores.get(SymptomClass.HEALTHY, 0), spots_score * 0.60
            )

        # MILDEW_LIKE: very high brightness, low saturation (white coating)
        mildew_score = 0.0
        if brightness > 170 and saturation < 50:
            mildew_score = 0.3 + (brightness - 170) / 200
        scores[SymptomClass.MILDEW_LIKE] = min(1.0, mildew_score)

        # RUST_LIKE: high red, moderate saturation, orange-brown tones
        # Rust has distinctive orange-red with high saturation.
        # Key: real rust has vivid orange (high sat > 150), unlike necrosis (low sat).
        rust_score = 0.0
        if red_r > 0.33 and green_r < 0.32 and saturation > 50:
            rust_score = (red_r - 0.33) * 5
            # Saturation boost: vivid orange-red (sat > 150) is classic rust
            if saturation > 150:
                rust_score += 0.25
            # Very red (> 0.50) with moderate sat is almost certainly rust
            if red_r > 0.50:
                rust_score += 0.20
        elif red_r > 0.38 and green_r < 0.35 and saturation > 40:
            rust_score = (red_r - 0.38) * 4
        scores[SymptomClass.RUST_LIKE] = min(1.0, rust_score)

        # BLIGHT_LIKE: rapid necrosis — very low green, low saturation
        blight_score = 0.0
        if green_r < 0.22 and saturation < 40:
            blight_score = (0.22 - green_r) * 5
        scores[SymptomClass.BLIGHT_LIKE] = min(1.0, blight_score)

        # INSECT_DAMAGE: holes = high brightness contrast, moderate green
        # Insect feeding creates jagged holes with high brightness variation.
        # Key: insects create irregular patterns with high entropy + moderate bstd.
        insect_score = 0.0
        if features.brightness_std > 28 and green_r > 0.25:
            insect_score = (features.brightness_std - 28) / 50
            # Relative std: insects create extreme local contrast
            rel_std = features.brightness_std / max(brightness, 1)
            if rel_std > 0.25:
                insect_score += 0.15
            # Entropy boost: high entropy (> 2.5) confirms real pixel variation
            # from holes/damage, not just noise
            if features.color_entropy > 2.5:
                insect_score += 0.15
        scores[SymptomClass.INSECT_DAMAGE] = min(1.0, insect_score)

        # WILT: low saturation with moderate green (turgor loss)
        # Wilt presents as reduced pigment intensity — leaves look faded/dull.
        # Moderately wilted leaves still have sat 70-90.
        wilt_score = 0.0
        if saturation < 90 and 0.25 < green_r < 0.42:
            wilt_score = max(0.35, (90 - saturation) / 70)  # Floor: 0.35 minimum
            # Stronger wilt at lower saturation
            if saturation < 60:
                wilt_score += 0.20
        # Wilt also suppresses healthy: faded pigment is not "healthy"
        if wilt_score > 0.20 and organ_class == "leaf":
            scores[SymptomClass.HEALTHY] = min(
                scores.get(SymptomClass.HEALTHY, 0), 0.20
            )
        scores[SymptomClass.WILT] = min(1.0, wilt_score)

        # --- E4: Organ-aware post-processing ---
        # Fruit organ: redness/yellowness/brownness is NATURAL for fruit.
        # Suppress all disease scores — fruit is healthy unless visibly rotten.
        if organ_class == "fruit":
            for sym in [SymptomClass.CHLOROSIS, SymptomClass.NECROSIS,
                        SymptomClass.RUST_LIKE, SymptomClass.SPOTS,
                        SymptomClass.MILDEW_LIKE, SymptomClass.BLIGHT_LIKE,
                        SymptomClass.INSECT_DAMAGE, SymptomClass.WILT]:
                scores[sym] = min(scores.get(sym, 0), 0.10)

        # --- Chlorosis floor rule ---
        # If we have strong visible yellowing on a leaf and chlorosis was suppressed
        # (e.g., by the green > 0.33 multiplier), enforce a minimum chlorosis
        # score so it never loses to unknown_stress.
        # Guard: only fire when healthy is also weak, to avoid overriding
        # genuinely healthy green leaves that have moderate yellow_ratio.
        healthy_score = scores.get(SymptomClass.HEALTHY, 0)
        if (features.yellow_ratio > 0.30
                and organ_class == "leaf"
                and healthy_score < 0.3):
            current_chlorosis = scores.get(SymptomClass.CHLOROSIS, 0)
            if current_chlorosis < 0.25:
                scores[SymptomClass.CHLOROSIS] = max(current_chlorosis, 0.25)

        # --- E5: Mutual exclusion rules ---
        # Rule E5.1: Rust vs Necrosis — when rust is at least as strong AND
        # the visual evidence strongly favors rust (VERY high sat + very red),
        # suppress necrosis. Must match tiebreak thresholds to avoid
        # suppressing genuine necrosis.
        rust_s = scores.get(SymptomClass.RUST_LIKE, 0)
        necro_s = scores.get(SymptomClass.NECROSIS, 0)
        if rust_s >= necro_s and rust_s > 0.15:
            if saturation > 150 and red_r > 0.50:
                scores[SymptomClass.NECROSIS] = min(necro_s, rust_s * 0.3)
        
        # Rule E5.2: Insect damage vs Spots — insect damage has higher
        # brightness contrast relative to overall brightness (jagged holes).
        # When insect signal is at least as strong, suppress spots.
        insect_s = scores.get(SymptomClass.INSECT_DAMAGE, 0)
        spots_s = scores.get(SymptomClass.SPOTS, 0)
        if insect_s >= spots_s and insect_s > 0.15:
            rel_std = features.brightness_std / max(brightness, 1)
            if rel_std > 0.20 or features.color_entropy > 2.5:
                scores[SymptomClass.SPOTS] = min(spots_s, insect_s * 0.3)

        # UNKNOWN_STRESS: fallback — if nothing is strong
        total_symptoms = sum(v for k, v in scores.items() if k != SymptomClass.HEALTHY)
        if total_symptoms < 0.15 and scores.get(SymptomClass.HEALTHY, 0) < 0.3:
            scores[SymptomClass.UNKNOWN_STRESS] = 0.3
        else:
            scores[SymptomClass.UNKNOWN_STRESS] = 0.05

        return scores

    def _estimate_severity(self, features: PreprocessResult, primary: str) -> float:
        """Estimate symptom severity (0–1)."""
        if primary == SymptomClass.HEALTHY:
            return 0.0

        green_r = features.green_ratio
        saturation = features.saturation_mean

        # Severity increases as green drops and saturation drops
        green_loss = max(0, 0.35 - green_r) / 0.35  # 0 = normal green, 1 = no green
        sat_loss = max(0, 80 - saturation) / 80       # 0 = normal sat, 1 = grayscale

        severity = (green_loss * 0.6 + sat_loss * 0.4)
        
        # Chlorosis / yellowing severity boost:
        # If yellow_ratio is high, severity should reflect the yellowing
        # regardless of green_loss and sat_loss (a leaf can be highly saturated
        # and still have strong chlorosis). Also applies to unknown_stress
        # so that even fallback classifications report nonzero severity.
        if primary in (SymptomClass.CHLOROSIS, SymptomClass.UNKNOWN_STRESS):
            if features.yellow_ratio > 0.15:
                yellow_severity = (features.yellow_ratio - 0.15) * 2
                severity = max(severity, yellow_severity)
            
        return min(1.0, max(0.0, severity))
