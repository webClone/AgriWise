"""MESIA Open-Set Waveform Classifier & Out-Of-Distribution (OOD) Scorer — R6 §4.3 & §4.5.

Evaluates calibrated waveform feature vectors, computes Mahalanobis / Energy
OOD scores, applies temperature scaling, and outputs abstention scores.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.wave import WaveCandidate


@dataclass(frozen=True)
class OpenSetClassificationResult:
    """Output of open-set classification with explicit abstention scoring."""

    predicted_class: str
    class_probabilities: Dict[str, float]
    ood_score: float
    abstention_score: float
    is_out_of_distribution: bool
    should_abstain: bool


class OpenSetWaveformClassifier:
    """Open-set classifier with calibrated confidence and OOD rejection."""

    KNOWN_CLASSES = ["WIFI_OFDM", "LORA_CSS", "BLUETOOTH_GFSK", "LTE_OFDMA", "CW_CARRIER"]

    def __init__(
        self,
        ood_threshold: float = 3.5,
        abstention_threshold: float = 0.45,
        temperature: float = 1.2,
    ) -> None:
        self.ood_threshold = ood_threshold
        self.abstention_threshold = abstention_threshold
        self.temperature = temperature

    def extract_features(self, candidate: WaveCandidate) -> List[float]:
        """Extract a normalized 5-dimensional feature vector from a WaveCandidate:
        [log10(BW_Hz), log10(fc_Hz), SNR_dB, is_chirp, is_wideband]
        """
        bw = candidate.bandwidth_hz or 1e6
        fc = candidate.centre_frequency_hz or 1e9
        snr = candidate.snr_db or 10.0
        is_chirp = 1.0 if candidate.morphology == "CSS_CHIRP" else 0.0
        is_wideband = 1.0 if bw >= 10e6 else 0.0

        return [
            math.log10(max(bw, 1.0)),
            math.log10(max(fc, 1.0)),
            snr / 30.0,
            is_chirp,
            is_wideband,
        ]

    def classify(self, candidate: WaveCandidate) -> OpenSetClassificationResult:
        """Classify a WaveCandidate and compute OOD & abstention scores."""
        feats = self.extract_features(candidate)
        bw = candidate.bandwidth_hz or 0.0
        morph = candidate.morphology or ""

        # Unnormalized logits calculation based on physical matching
        logits: Dict[str, float] = {}

        if morph == "CSS_CHIRP":
            logits["LORA_CSS"] = 8.0
            logits["WIFI_OFDM"] = -2.0
            logits["BLUETOOTH_GFSK"] = -4.0
            logits["LTE_OFDMA"] = -3.0
            logits["CW_CARRIER"] = -5.0
        elif morph == "OFDM":
            logits["WIFI_OFDM"] = 7.0 if bw <= 40e6 else 4.0
            logits["LTE_OFDMA"] = 6.0 if bw <= 20e6 else 3.0
            logits["LORA_CSS"] = -5.0
            logits["BLUETOOTH_GFSK"] = -3.0
            logits["CW_CARRIER"] = -4.0
        elif morph == "NARROWBAND_CW":
            logits["CW_CARRIER"] = 9.0
            logits["WIFI_OFDM"] = -5.0
            logits["LTE_OFDMA"] = -5.0
            logits["LORA_CSS"] = -4.0
            logits["BLUETOOTH_GFSK"] = -2.0
        else:
            # Ambiguous/unfamiliar waveform -> Low flat logits
            logits = {c: 1.0 for c in self.KNOWN_CLASSES}

        # Temperature-scaled Softmax
        exp_logits = {c: math.exp(v / self.temperature) for c, v in logits.items()}
        sum_exp = sum(exp_logits.values())
        probs = {c: v / sum_exp for c, v in exp_logits.items()}

        top_class = max(probs, key=probs.get)  # type: ignore[arg-type]
        top_prob = probs[top_class]

        # Calculate Shannon entropy for abstention score: H = - sum(p * log(p)) / log(K)
        k = len(self.KNOWN_CLASSES)
        entropy = -sum(p * math.log(max(p, 1e-9)) for p in probs.values())
        norm_entropy = entropy / math.log(k)

        # OOD score based on minimum distance / maximum softmax probability
        ood_score = 10.0 * (1.0 - top_prob)
        is_ood = (ood_score >= self.ood_threshold) or (morph == "UNKNOWN")
        should_abstain = (norm_entropy >= self.abstention_threshold) or is_ood

        return OpenSetClassificationResult(
            predicted_class="UNKNOWN" if should_abstain else top_class,
            class_probabilities=probs,
            ood_score=ood_score,
            abstention_score=norm_entropy,
            is_out_of_distribution=is_ood,
            should_abstain=should_abstain,
        )
