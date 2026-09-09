"""MESIA Omega Surprise Detector — R6 §16.4 / P14.4.

Detects persistent discrepancies between MESIA multi-radio evidence and ASMAE
biological world-models, flagging them as scientific questions rather than false claims.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ScientificSurpriseHypothesis:
    """Scientific anomaly requiring experimental investigation."""

    hypothesis_id: str
    target_plot_id: str
    observed_residual_error: float
    epistemic_disagreement_score: float
    kl_divergence_bits: float
    candidate_explanations: List[str]
    is_actionable_question: bool
    created_at: datetime

    def content_hash(self) -> str:
        d = {
            "hypothesis_id": self.hypothesis_id,
            "target_plot_id": self.target_plot_id,
            "observed_residual_error": self.observed_residual_error,
            "epistemic_disagreement_score": self.epistemic_disagreement_score,
            "kl_divergence_bits": self.kl_divergence_bits,
            "candidate_explanations": self.candidate_explanations,
            "is_actionable_question": self.is_actionable_question,
            "created_at": self.created_at.isoformat(),
        }
        raw = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class OmegaSurpriseDetector:
    """Detects systematic model-observation mismatch."""

    @staticmethod
    def evaluate_model_disagreement(
        plot_id: str,
        mesia_likelihood_vwc: float,
        asmae_prior_vwc: float,
        mesia_variance: float = 0.001,
        asmae_variance: float = 0.001,
    ) -> Optional[ScientificSurpriseHypothesis]:
        """Flag surprising state disagreement when residual exceeds 3-sigma or high KL divergence."""
        import math
        
        diff = abs(mesia_likelihood_vwc - asmae_prior_vwc)
        combined_std = (mesia_variance + asmae_variance) ** 0.5
        z_score = diff / combined_std

        # Kullback-Leibler Divergence for two univariate Gaussians
        # D_KL(P || Q) = log(sigma_q/sigma_p) + (sigma_p^2 + (mu_p - mu_q)^2)/(2 * sigma_q^2) - 0.5
        sigma_m = math.sqrt(mesia_variance)
        sigma_a = math.sqrt(asmae_variance)
        
        if sigma_a > 0 and sigma_m > 0:
            kl_div_nats = math.log(sigma_a / sigma_m) + (mesia_variance + diff**2) / (2.0 * asmae_variance) - 0.5
            kl_div_bits = kl_div_nats / math.log(2.0)
        else:
            kl_div_bits = 0.0

        if z_score >= 3.0 and kl_div_bits > 1.5:
            now = datetime.now(timezone.utc)
            return ScientificSurpriseHypothesis(
                hypothesis_id=f"hyp-surprise-{plot_id}-{int(now.timestamp())}",
                target_plot_id=plot_id,
                observed_residual_error=diff,
                epistemic_disagreement_score=z_score,
                kl_divergence_bits=kl_div_bits,
                candidate_explanations=[
                    "Subsurface drainage layer compaction anomaly",
                    "Localized root channel preferential water flow",
                    "Unreported drip irrigation emitter clogging",
                ],
                is_actionable_question=True,
                created_at=now,
            )

        return None
